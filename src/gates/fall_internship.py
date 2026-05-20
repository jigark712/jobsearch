"""Fall 2026 Boston part-time internship gates."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from src.classify_track import BOSTON_RE, PART_TIME_KWS
from src.schema import JobPosting


def check_location_boston(posting: JobPosting) -> tuple[bool, str]:
    loc = posting.location or ""
    if BOSTON_RE.search(loc):
        return True, ""
    for ln in posting.location_normalized or []:
        if BOSTON_RE.search(ln):
            return True, ""
    return False, f"location:not_boston:{loc[:40]}"


def check_part_time(posting: JobPosting) -> tuple[bool, str]:
    text = (posting.title + " " + (posting.jd_text or ""))[:5000]
    if PART_TIME_KWS.search(text):
        return True, ""
    return False, "part_time:not_explicit"


def check_start_window(posting: JobPosting) -> tuple[bool, str]:
    text = (posting.jd_text or "").lower()
    signals = ["august 2026", "aug 2026", "september 2026", "sep 2026", "sept 2026",
               "fall 2026", "fall'26", "fall '26"]
    if any(s in text for s in signals):
        return True, ""
    return False, "start_window:no_fall_2026_signal"


def check_freshness(posting: JobPosting) -> tuple[bool, str]:
    seen = posting.posted_date or posting.first_seen_date
    if isinstance(seen, datetime):
        seen_d = seen.date()
    else:
        seen_d = seen
    age = (date.today() - seen_d).days
    if age > 14:
        return False, f"freshness:{age}d>14"
    return True, ""


GATES = [check_location_boston, check_part_time, check_start_window, check_freshness]


def run(posting: JobPosting) -> tuple[bool, str]:
    for gate in GATES:
        ok, reason = gate(posting)
        if not ok:
            return False, reason
    return True, ""
