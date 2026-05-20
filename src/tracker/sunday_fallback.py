"""Sunday email fallback for untracked applications.

Sends owner a list of recent applications that don't have detected status
updates, asking them to reply with corrections in plain English. A separate
inbound-reply parser (not yet built) would consume the response.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from src.config_loader import preferences
from src.emailer import send_email
from src.logging_setup import configure_logging
from src.tracker.sheet_client import _open_sheet

log = configure_logging("tracker.sunday")


def build_fallback_message() -> str | None:
    ws = _open_sheet()
    if ws is None:
        return None
    records = ws.get_all_records()
    cutoff = date.today() - timedelta(days=10)
    candidates = []
    for r in records:
        applied = r.get("applied_date") or ""
        if not applied:
            continue
        try:
            d = datetime.fromisoformat(applied).date()
        except ValueError:
            continue
        if d < cutoff:
            continue
        # Untracked if no follow-up activity detected
        no_activity = not any(r.get(c) for c in (
            "recruiter_screen_date", "OA_date", "phone_screen_date",
            "tech_interview_dates", "onsite_date", "outcome",
        ))
        if no_activity:
            candidates.append(r)
    if not candidates:
        return None
    lines = [
        "Subject context: Job tracker — items needing manual confirmation",
        "",
        "These applications are missing follow-up data. Reply in plain English",
        "(e.g., 'A1: applied to Decagon AI Engineer Tuesday; A2: phone screen with",
        "Cresta scheduled for Thursday') and I'll update the tracker.",
        "",
    ]
    for i, r in enumerate(candidates[:10], 1):
        lines.append(f"A{i}. {r.get('company','?')} — {r.get('title','?')} (applied {r.get('applied_date')})")
    return "\n".join(lines)


def send_fallback_email() -> bool:
    body = build_fallback_message()
    if not body:
        log.info("no fallback items this week")
        return False
    to = os.environ.get("OWNER_EMAIL") or preferences()["owner"]["email"]
    return send_email(to, f"Job tracker — items needing manual confirmation ({date.today().isoformat()})", body)
