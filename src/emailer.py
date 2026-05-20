"""Gmail-based digest emailer.

Reuses the same OAuth setup as the tracker (src/tracker/gmail_watcher.py).
On first run, prompts the user to authorize via browser — subsequent runs
read the saved token at .secrets/gmail_oauth_token.json.

If the user has not set up OAuth yet, send_digest() logs a warning and
returns False. The digest file is still written either way.
"""
from __future__ import annotations

import base64
import os
from email.mime.text import MIMEText
from pathlib import Path

from src.logging_setup import configure_logging
from src.paths import SECRETS_DIR

log = configure_logging("emailer")

_OAUTH_TOKEN_PATH = SECRETS_DIR / "gmail_oauth_token.json"
_OAUTH_CLIENT_PATH = SECRETS_DIR / "gmail_oauth_client.json"
_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _gmail_service():
    """Return an authenticated Gmail API client, or None if OAuth not set up."""
    if not _OAUTH_TOKEN_PATH.exists() and not _OAUTH_CLIENT_PATH.exists():
        log.warning("gmail oauth not configured", extra={
            "hint": f"place oauth client JSON at {_OAUTH_CLIENT_PATH} and run the watcher setup"
        })
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


def send_email(to: str, subject: str, body_markdown: str, *, from_addr: str | None = None) -> bool:
    svc = _gmail_service()
    if svc is None:
        return False
    msg = MIMEText(body_markdown, "plain", "utf-8")
    msg["to"] = to
    msg["from"] = from_addr or to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        log.info("digest emailed", extra={"to": to, "subject": subject})
        return True
    except Exception as e:
        log.warning("gmail send failed", extra={"err": f"{type(e).__name__}: {e}"})
        return False
