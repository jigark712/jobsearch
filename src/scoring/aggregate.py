"""Aggregate the 12 scoring components into a final 0-100 score + bucket.

Spec section 5.3 decision bucket logic:
  apply_today / apply_week / referral_first / watchlist / reject

Boost: +4 if company on priority list (capped at 100).
Penalty: -10 for Twitter-sourced postings.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.config_loader import preferences
from src.scoring import (
    credibility,
    effort,
    freshness,
    location,
    profile_match,
    project_match,
    referral,
    role_quality,
    role_type,
    seniority,
    skill_match,
    sponsorship,
)
from src.scoring.role_quality import _all_priority_companies
from src.schema import JobPosting


def _hours_old(posting: JobPosting) -> float:
    seen = posting.posted_date or posting.first_seen_date
    if isinstance(seen, datetime):
        return (datetime.now(timezone.utc) - seen).total_seconds() / 3600
    return (datetime.now(timezone.utc) - datetime(seen.year, seen.month, seen.day, tzinfo=timezone.utc)).total_seconds() / 3600


def score_posting(posting: JobPosting, track: str = "full_time") -> dict:
    comps: dict[str, dict] = {}

    def add(name, scored):
        comps[name] = {"score": scored[0], "reason": scored[1]}

    add("profile_match", profile_match.score(posting))
    add("skill_match", skill_match.score(posting))
    add("project_match", project_match.score(posting))
    add("seniority", seniority.score(posting))
    add("role_type", role_type.score(posting, track))
    add("freshness", freshness.score(posting, track))
    add("credibility", credibility.score(posting))
    add("role_quality", role_quality.score(posting))
    add("location", location.score(posting, track))
    add("effort", effort.score(posting))
    add("referral", referral.score(posting))
    add("sponsorship", sponsorship.score(posting, track))

    raw_total = sum(c["score"] for c in comps.values())

    # Track-specific summer intern adjustments per spec 5.1
    if track == "summer_2026_internship":
        # Profile match was scored against full-time clusters — be lenient
        pass

    # Boost: priority company
    priority_co = any(p in posting.company.lower() for p in _all_priority_companies())
    if priority_co:
        raw_total = min(100, raw_total + 4)

    # Penalty: Twitter-sourced
    if posting.source.split(":", 1)[0] == "twitter":
        raw_total = max(0, raw_total - 10)

    score = min(100, raw_total)

    # Bucket logic per spec 5.3
    posted_hours = _hours_old(posting)
    posted_days = posted_hours / 24
    if score >= 80 or (score >= 70 and posted_hours < 48) or (score >= 65 and priority_co and posted_days < 7):
        bucket = "apply_today"
    elif score >= 70:
        bucket = "apply_week"
    elif score >= 65 and priority_co:
        bucket = "referral_first"
    elif score >= 55:
        bucket = "watchlist"
    else:
        bucket = "reject"

    # Track surface bars per spec 5.1
    prefs = preferences()
    floor = prefs["quality_floors"]["reject_below_score"]
    if track == "summer_2026_internship" and score < 75:
        bucket = "reject"
    if track == "fall_2026_internship" and score < 65:
        bucket = "reject"
    if score < floor and bucket != "reject":
        bucket = "reject"

    risk_flags = []
    if comps["seniority"]["score"] <= 3:
        risk_flags.append(f"seniority: {comps['seniority']['reason']}")
    if comps["sponsorship"]["score"] == 2:
        risk_flags.append("sponsorship: unknown — verify in screen")
    if comps["project_match"]["score"] <= 5:
        risk_flags.append("weak project evidence vs JD")

    return {
        "score_total": score,
        "score_components": comps,
        "decision_bucket": bucket,
        "risk_flags": risk_flags,
        "track": track,
        "priority_company": priority_co,
    }
