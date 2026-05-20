"""Summer 2026 internship hard gates."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.config_loader import preferences
from src.schema import JobPosting


def check_freshness_strict(posting: JobPosting) -> tuple[bool, str]:
    max_hours = preferences()["summer_2026_internship_rules"]["freshness_max_hours"]
    seen = posting.posted_date or posting.first_seen_date
    if isinstance(seen, datetime):
        hours_old = (datetime.now(timezone.utc) - seen).total_seconds() / 3600
    else:
        # date only — assume midnight UTC
        hours_old = (datetime.now(timezone.utc) - datetime(seen.year, seen.month, seen.day, tzinfo=timezone.utc)).total_seconds() / 3600
    if hours_old > max_hours:
        return False, f"freshness_strict:{int(hours_old)}h>{max_hours}h"
    return True, ""


def check_start_window(posting: JobPosting) -> tuple[bool, str]:
    rules = preferences()["summer_2026_internship_rules"]
    text = (posting.jd_text or "").lower()
    if "immediate" in text or "asap" in text or "start within 2 weeks" in text:
        return True, ""
    if "summer 2026" in text or "summer'26" in text or "summer '26" in text:
        return True, ""
    # Look for any of June/July/August 2026
    for m in ("june 2026", "july 2026", "august 2026", "jun 2026", "jul 2026", "aug 2026"):
        if m in text:
            return True, ""
    return False, "start_window:no_summer_2026_signal"


def check_company_size(posting: JobPosting) -> tuple[bool, str]:
    # Heuristic blocklist of big companies' summer programs (closed in Jan-Mar)
    big_co = {
        "google", "meta", "facebook", "microsoft", "amazon", "apple", "netflix",
        "nvidia", "tesla", "oracle", "salesforce", "ibm", "intel", "adobe", "cisco",
        "jpmorgan", "goldman", "morgan stanley", "citigroup", "wells fargo", "bank of america",
        "deloitte", "pwc", "ey", "kpmg", "accenture",
    }
    co_low = posting.company.lower()
    for big in big_co:
        if big in co_low:
            return False, f"company_size:large:{big}"
    return True, ""


def check_deadline(posting: JobPosting) -> tuple[bool, str]:
    text = (posting.jd_text or "").lower()
    if "applications closed" in text or "closed for applications" in text:
        return False, "deadline:closed"
    return True, ""


def check_hard_end_date(posting: JobPosting) -> tuple[bool, str]:
    """Auto-disable summer track after 2026-07-15."""
    cutoff_str = preferences()["summer_2026_internship_rules"].get("auto_disable_date", "2026-07-15")
    cutoff = date.fromisoformat(cutoff_str)
    if date.today() > cutoff:
        return False, f"track_auto_disabled:after_{cutoff_str}"
    return True, ""


GATES = [check_hard_end_date, check_freshness_strict, check_start_window, check_company_size, check_deadline]


def run(posting: JobPosting) -> tuple[bool, str]:
    for gate in GATES:
        ok, reason = gate(posting)
        if not ok:
            return False, reason
    return True, ""
