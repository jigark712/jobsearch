"""Full-time-track hard gates (run after universal).

Returns (passed, reason).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from src.config_loader import preferences
from src.schema import JobPosting

_YOE_RE = re.compile(r"(\d+)\s*\+?\s*(?:to\s*\d+)?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_NEW_GRAD_RE = re.compile(r"\b(new\s*grad|new[-\s]graduate|0\s*[-–]\s*2\s*years?)\b", re.IGNORECASE)
_LOC_REMOTE_US = re.compile(r"\bremote\s*-?\s*(?:us|usa|united\s*states)\b|\bus\s*remote\b", re.IGNORECASE)
_LOC_OUTSIDE_US = re.compile(
    r"\b(uk|united kingdom|england|london|edinburgh|ireland|dublin|germany|berlin|munich|france|paris|"
    r"canada|toronto|vancouver|montreal|india|bangalore|bengaluru|hyderabad|mumbai|delhi|"
    r"israel|tel\s*aviv|singapore|tokyo|japan|"
    r"sydney|melbourne|australia|brazil|sao paulo|mexico|amsterdam|netherlands|spain|madrid|barcelona|"
    r"switzerland|zurich|sweden|stockholm|norway|oslo|denmark|copenhagen|finland|helsinki|poland|warsaw|"
    r"south korea|seoul|china|beijing|shanghai|hong kong|taiwan|emea|apac)\b",
    re.IGNORECASE,
)


def check_seniority(posting: JobPosting) -> tuple[bool, str]:
    text = (posting.title + " " + posting.jd_text)[:5000]
    if _NEW_GRAD_RE.search(text):
        return True, ""
    yoe_matches = _YOE_RE.findall(text)
    for m in yoe_matches:
        try:
            if int(m) > 2:
                return False, f"seniority:{m}+yrs"
        except ValueError:
            continue
    return True, ""


_US_CITIES = [
    "boston", "cambridge", "new york", "nyc", "san francisco", "bay area",
    "seattle", "austin", "los angeles", "chicago", "atlanta", "denver",
    "washington", "palo alto", "mountain view", "sunnyvale", "menlo park",
    "redmond", "bellevue", "santa clara", "san jose", "san mateo", "brooklyn",
    "manhattan", "philadelphia", "pittsburgh", "portland", "miami", "dallas",
    "houston", "phoenix", "minneapolis", "detroit", "raleigh", "durham",
]


_US_STATE_RE = re.compile(
    r",\s*(?:al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|"
    r"ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|"
    r"tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b",
    re.IGNORECASE,
)


def _has_us_signal(loc: str) -> bool:
    loc_low = loc.lower()
    if _LOC_OUTSIDE_US.search(loc_low):
        return False
    if _LOC_REMOTE_US.search(loc_low):
        return True
    if "united states" in loc_low or "usa" in loc_low:
        return True
    if _US_STATE_RE.search(loc):
        return True
    return any(c in loc_low for c in _US_CITIES)


def _location_allowed(posting: JobPosting) -> bool:
    raw = posting.location or ""
    if not raw:
        return True  # unknown — let through; scoring will penalize
    # Split multi-location strings on semicolons/pipes; pass if any part has a
    # US signal AND that part doesn't contain a non-US keyword.
    parts = [p.strip() for p in re.split(r"[;|]", raw) if p.strip()] or [raw]
    return any(_has_us_signal(p) for p in parts)


def check_location(posting: JobPosting) -> tuple[bool, str]:
    if _location_allowed(posting):
        return True, ""
    return False, f"location:not_allowed:{posting.location[:40]}"


def check_freshness(posting: JobPosting) -> tuple[bool, str]:
    if not posting.posted_date:
        # No posted_date → use first_seen.
        seen = posting.first_seen_date
        if isinstance(seen, datetime):
            seen_d = seen.date()
        else:
            seen_d = seen
    else:
        seen_d = posting.posted_date
    age_days = (date.today() - seen_d).days
    if age_days > 30:
        return False, f"freshness:{age_days}d"
    return True, ""


def check_start_date(posting: JobPosting) -> tuple[bool, str]:
    # Heuristic: if JD explicitly says start in 2024/2025 (before owner's window)
    # AND doesn't mention flexible/January 2027/new grad, reject.
    earliest = preferences()["owner"]["earliest_full_time_start"]
    text = (posting.jd_text or "").lower()
    if any(p in text for p in ("start date is flexible", "flexible start", "new grad")):
        return True, ""
    # No strong signal — accept (scoring handles the rest).
    return True, ""


GATES = [check_seniority, check_location, check_freshness, check_start_date]


def run(posting: JobPosting) -> tuple[bool, str]:
    for gate in GATES:
        ok, reason = gate(posting)
        if not ok:
            return False, reason
    return True, ""
