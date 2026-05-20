"""Component 6: Posting freshness. Max 10 (full-time) / rescaled for summer."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.schema import JobPosting


def _age_hours(posting: JobPosting) -> float:
    seen = posting.posted_date or posting.first_seen_date
    if isinstance(seen, datetime):
        return (datetime.now(timezone.utc) - seen).total_seconds() / 3600
    return (datetime.now(timezone.utc) - datetime(seen.year, seen.month, seen.day, tzinfo=timezone.utc)).total_seconds() / 3600


def score(posting: JobPosting, track: str = "full_time") -> tuple[int, str]:
    hours = _age_hours(posting)
    days = hours / 24
    if track == "summer_2026_internship":
        # Gate guarantees <=72h
        if hours < 12:
            return 10, f"{int(hours)}h old"
        if hours < 36:
            return 7, f"{int(hours)}h old"
        return 4, f"{int(hours)}h old"
    # Full-time / fall-intern: 10/8/5/2/0 by 24h/3d/7d/14d/30d
    if hours <= 24:
        return 10, "<24h"
    if days <= 3:
        return 8, f"{int(days)}d"
    if days <= 7:
        return 5, f"{int(days)}d"
    if days <= 14:
        return 2, f"{int(days)}d"
    return 0, f"{int(days)}d"
