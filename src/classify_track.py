"""Classify a JobPosting into one of three tracks (or REJECT).

Tracks: full_time | summer_2026_internship | fall_2026_internship | REJECT.
"""
from __future__ import annotations

import re
from datetime import date

from src.config_loader import preferences
from src.schema import JobPosting

INTERNSHIP_KWS = re.compile(r"\b(intern(ship)?|co[-\s]?op)\b", re.IGNORECASE)
PART_TIME_KWS = re.compile(r"\b(part[-\s]?time|20\s*(?:hours|hrs)/?(?:week|wk)?)\b", re.IGNORECASE)
IMMEDIATE_KWS = re.compile(r"\b(immediate(?:ly)?|asap|start(?:ing)?\s+(?:within\s+\d+\s+weeks?|now)|join\s+now)\b", re.IGNORECASE)

BOSTON_RE = re.compile(r"\b(boston|cambridge|somerville|brookline|greater\s+boston|massachusetts|MA)\b", re.IGNORECASE)


def _start_window_overlap(jd_text: str, start: date, end: date) -> bool:
    """Best-effort: does the JD reference a month/year in the window?"""
    months = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
    text = jd_text.lower()
    cur = date(start.year, start.month, 1)
    while cur <= end:
        for short in (months[cur.month - 1], cur.strftime("%B").lower()):
            if f"{short} {cur.year}" in text or f"{short}, {cur.year}" in text or f"{short} {cur.year % 100:02d}" in text:
                return True
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return False


def is_boston(posting: JobPosting) -> bool:
    if posting.location and BOSTON_RE.search(posting.location):
        return True
    for loc in posting.location_normalized or []:
        if BOSTON_RE.search(loc):
            return True
    return False


def classify(posting: JobPosting) -> str:
    """Return track name or 'REJECT'."""
    prefs = preferences()
    summer = prefs["summer_2026_internship_rules"]
    fall = prefs["fall_2026_internship_rules"]

    title_low = posting.title.lower()
    jd_low = (posting.jd_text or "").lower()
    is_internship = bool(INTERNSHIP_KWS.search(posting.title)) or bool(INTERNSHIP_KWS.search(jd_low[:2000]))
    is_part_time = bool(PART_TIME_KWS.search(jd_low)) or "part-time" in title_low

    if is_internship:
        boston = is_boston(posting)
        if is_part_time and boston:
            return "fall_2026_internship"
        # check summer 2026 window
        summer_start = date.fromisoformat(summer["start_date_window"][0])
        summer_end = date.fromisoformat(summer["start_date_window"][1])
        if _start_window_overlap(jd_low, summer_start, summer_end) or "summer 2026" in jd_low or "summer'26" in jd_low or "summer '26" in jd_low:
            return "summer_2026_internship"
        # check fall 2026 window
        fall_start = date.fromisoformat(fall["start_date_window"][0])
        fall_end = date.fromisoformat(fall["start_date_window"][1])
        if (_start_window_overlap(jd_low, fall_start, fall_end) and boston and is_part_time):
            return "fall_2026_internship"
        # Could be summer 2027 or off-window — drop.
        return "REJECT"

    # Full-time path
    if "full-time" in jd_low or "full time" in jd_low or not is_internship:
        return "full_time"

    return "REJECT"
