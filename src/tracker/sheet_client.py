"""Google Sheet client for the Job Tracker.

Reads/writes via gspread + a Google service-account JSON. The sheet must be
shared with the service account email.

Sheet schema per spec section 7.1. Row ordering is by job_id (one row per
unique application). Append-only — no row deletes.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from typing import Any

from src.logging_setup import configure_logging

log = configure_logging("tracker.sheet")

COLUMNS = [
    "job_id", "company", "title", "cluster", "location", "posting_url",
    "source", "posted_date", "score", "score_breakdown", "decision",
    "resume_variant", "applied_date", "referral_status", "referrer_name",
    "recruiter_screen_date", "OA_date", "phone_screen_date",
    "tech_interview_dates", "onsite_date", "offer_date", "outcome",
    "notes", "last_action_date", "follow_up_due",
]


@lru_cache(maxsize=1)
def _open_sheet():
    """Return a gspread Worksheet handle or None if not configured."""
    sheet_id = os.environ.get("JOB_TRACKER_SHEET_ID")
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not sheet_id or not creds_path or not os.path.exists(creds_path):
        log.warning("sheet not configured",
                    extra={"sheet_id_present": bool(sheet_id),
                           "creds_path_present": bool(creds_path)})
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        log.warning("gspread or google-auth not installed")
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    try:
        ws = sheet.worksheet("Job Tracker")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet("Job Tracker", rows=1000, cols=len(COLUMNS))
        ws.append_row(COLUMNS)
    return ws


def _ensure_header(ws) -> None:
    existing = ws.row_values(1)
    if existing != COLUMNS:
        ws.update("A1", [COLUMNS])


def upsert_row(row: dict[str, Any]) -> bool:
    """Insert or update a row keyed on job_id. Returns True if a write happened."""
    ws = _open_sheet()
    if ws is None:
        return False
    _ensure_header(ws)
    job_id = row.get("job_id")
    if not job_id:
        log.warning("upsert_row missing job_id")
        return False
    # Find existing row (gspread is slow on big sheets — OK for personal use).
    job_id_col = COLUMNS.index("job_id") + 1
    cells = ws.col_values(job_id_col)
    try:
        idx = cells.index(job_id)
        row_no = idx + 1
    except ValueError:
        row_no = None
    values = [row.get(c, "") for c in COLUMNS]
    # Serialize complex types
    for i, v in enumerate(values):
        if isinstance(v, (dict, list)):
            values[i] = json.dumps(v)
        elif isinstance(v, date):
            values[i] = v.isoformat()
    if row_no is None:
        ws.append_row(values)
    else:
        ws.update(f"A{row_no}", [values])
    return True


def find_by_company_and_title(company: str, title: str | None = None) -> dict | None:
    """Fuzzy match: case-insensitive company match + optional title fuzzy match.

    Returns first matching row as dict, or None.
    """
    ws = _open_sheet()
    if ws is None:
        return None
    records = ws.get_all_records()
    co_low = company.lower().strip()
    candidates = [r for r in records if (r.get("company") or "").lower().strip() == co_low]
    if not candidates:
        return None
    if not title:
        return candidates[0]
    t_low = title.lower().strip()
    # Best-effort: same title or contained
    for r in candidates:
        rt = (r.get("title") or "").lower().strip()
        if rt == t_low or t_low in rt or rt in t_low:
            return r
    return candidates[0]
