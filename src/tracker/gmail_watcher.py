"""Gmail watcher.

Polls a labelled Gmail folder, classifies each new message, and updates the
Job Tracker sheet. Idempotent via a processed-message-id log at
data/processed_gmail.txt.

Owner must:
1. Create a Gmail label `job-applications/` and a filter that routes confirmation
   emails to it.
2. Place a Google Cloud OAuth client JSON at .secrets/gmail_oauth_client.json.
3. Run the watcher once to authorize via browser; token saved to .secrets/.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path

from src.logging_setup import configure_logging
from src.paths import DATA_DIR, SECRETS_DIR
from src.tracker.email_classifier import classify_with_llm_fallback
from src.tracker.sheet_client import find_by_company_and_title, upsert_row

log = configure_logging("tracker.gmail")

LABEL = "job-applications"
PROCESSED_LOG = DATA_DIR / "processed_gmail.txt"
_OAUTH_TOKEN_PATH = SECRETS_DIR / "gmail_oauth_token.json"
_OAUTH_CLIENT_PATH = SECRETS_DIR / "gmail_oauth_client.json"
_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
           "https://www.googleapis.com/auth/gmail.send"]

# Category → column to set with the message date
_CATEGORY_TO_COLUMN = {
    "APPLIED_CONFIRMATION": "applied_date",
    "OA_INVITATION": "OA_date",
    "PHONE_SCREEN_INVITATION": "phone_screen_date",
    "INTERVIEW_INVITATION": "tech_interview_dates",
    "REJECTION": "outcome",
    "OFFER": "offer_date",
}


def _load_processed() -> set[str]:
    if not PROCESSED_LOG.exists():
        return set()
    return set(line.strip() for line in PROCESSED_LOG.read_text().splitlines() if line.strip())


def _mark_processed(msg_id: str) -> None:
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_LOG.open("a") as f:
        f.write(msg_id + "\n")


def _gmail_service():
    if not _OAUTH_CLIENT_PATH.exists() and not _OAUTH_TOKEN_PATH.exists():
        log.warning("gmail oauth not configured",
                    extra={"hint": f"place client JSON at {_OAUTH_CLIENT_PATH}"})
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        log.warning("google-api-python-client not installed")
        return None
    creds = None
    if _OAUTH_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_OAUTH_TOKEN_PATH), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif _OAUTH_CLIENT_PATH.exists():
            flow = InstalledAppFlow.from_client_secrets_file(str(_OAUTH_CLIENT_PATH), _SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            return None
        _OAUTH_TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _extract_company(headers: dict, snippet: str) -> str:
    """Best-effort company extraction from sender domain or snippet."""
    sender = headers.get("From", "")
    # First try sender domain: name <foo@company.com>
    m = re.search(r"@([\w\.-]+)", sender)
    if m:
        domain = m.group(1)
        # Strip leading careers./jobs./talent. and TLD
        parts = domain.split(".")
        if len(parts) >= 2:
            # Take the longest meaningful subdomain
            for p in parts[-2::-1]:
                if p not in ("greenhouse", "lever", "ashby", "ashbyhq", "myworkdayjobs",
                             "talent", "careers", "jobs", "hireflow", "no-reply"):
                    return p.capitalize()
            return parts[-2].capitalize()
    # Fallback: try snippet
    m = re.search(r"thank you for applying to ([A-Z][A-Za-z0-9 ]+)", snippet)
    if m:
        return m.group(1).strip()
    return ""


def _extract_title(snippet: str) -> str:
    m = re.search(r"(?:for the |applying to (?:the )?|application to )([A-Z][\w \-/]+? (?:Engineer|Scientist|Developer|Intern|Architect|Analyst|Manager))",
                  snippet)
    return m.group(1).strip() if m else ""


def poll_and_update() -> dict:
    """Poll Gmail label and update sheet for each unprocessed message."""
    svc = _gmail_service()
    if svc is None:
        log.info("gmail service not available; skipping poll")
        return {"polled": 0}

    processed = _load_processed()
    query = f"label:{LABEL}"
    result = svc.users().messages().list(userId="me", q=query, maxResults=200).execute()
    messages = result.get("messages", []) or []

    counts = {"polled": len(messages), "new": 0, "classified": {}, "wrote": 0}

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        if msg_id in processed:
            continue
        counts["new"] += 1
        msg = svc.users().messages().get(userId="me", id=msg_id, format="metadata",
                                         metadataHeaders=["From", "Subject", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        sender = headers.get("From", "")
        snippet = msg.get("snippet", "")
        category = classify_with_llm_fallback(subject, sender, snippet)
        counts["classified"][category] = counts["classified"].get(category, 0) + 1

        if category == "UNKNOWN":
            _mark_processed(msg_id)
            continue

        # Get email date
        internal_ms = int(msg.get("internalDate", "0"))
        msg_date = datetime.fromtimestamp(internal_ms / 1000).date()
        company = _extract_company(headers, snippet)
        title = _extract_title(snippet)
        existing = find_by_company_and_title(company, title) if company else None

        row: dict = existing.copy() if existing else {
            "job_id": f"email_{msg_id[:12]}",
            "company": company,
            "title": title,
            "source": "gmail_detected",
            "notes": "auto-created from Gmail; not in digest",
        }
        col = _CATEGORY_TO_COLUMN.get(category)
        if col:
            if col == "tech_interview_dates":
                existing_dates = row.get(col) or ""
                row[col] = (existing_dates + ";" if existing_dates else "") + msg_date.isoformat()
            elif col == "outcome":
                row[col] = "Rejected"
            elif col == "offer_date":
                # Per spec: do NOT auto-write offer; flag instead
                row["notes"] = (row.get("notes") or "") + f"\n[OFFER detected {msg_date.isoformat()} — confirm manually]"
            else:
                row[col] = msg_date.isoformat()
        row["last_action_date"] = date.today().isoformat()
        if upsert_row(row):
            counts["wrote"] += 1
        _mark_processed(msg_id)

    log.info("gmail poll complete", extra=counts)
    return counts
