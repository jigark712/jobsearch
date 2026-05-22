"""Filter rules for the internship notifier.

Pure rule-based. Owner edits these lists directly to tune the surface.
"""
from __future__ import annotations

PASS_CATEGORIES = [
    # Long-form labels from the spec (still seen on some SimplifyJobs entries)
    "Data Science, AI & Machine Learning",
    "Software Engineering",
    # Short labels SimplifyJobs uses on most current entries (2026-05-22 schema)
    "AI/ML/Data",
    "Software",
]

PASS_TITLE_KEYWORDS = [
    "ai", "ml", "machine learning", "llm", "nlp",
    "applied scientist", "research", "data science",
    "software engineer", "backend", "full stack",
    "fullstack", "platform", "infrastructure",
]

REJECT_SPONSORSHIP_VALUES = [
    "Not available",
    "not available",
]

REJECT_NOTES_KEYWORDS = [
    "us citizen",
    "u.s. citizen",
    "must be a us citizen",
    "no sponsorship",
    "without sponsorship",
    "no cpt",
    "no opt",
    "security clearance",
    "secret clearance",
    "ts/sci",
]

REJECT_TITLE_KEYWORDS = [
    "hardware",
    "fpga",
    "embedded",
    "firmware",
    "electrical",
    "mechanical",
    "civil",
    "sales",
    "marketing",
    "finance",
    "accounting",
    "legal",
    "hr ",
    "recruiter",
]

# Owner-managed: add company names here (case-insensitive substring) to mute
# notifications from specific employers. Empty by default.
REJECT_COMPANIES: list[str] = []


def passes_category(listing: dict) -> bool:
    if listing.get("source") != "simplify":
        return True  # YC and Wellfound: let title filter decide
    return any(cat in PASS_CATEGORIES for cat in (listing.get("categories") or []))


def passes_title(listing: dict) -> bool:
    title_lower = (listing.get("title") or "").lower()
    return any(kw in title_lower for kw in PASS_TITLE_KEYWORDS)


def is_active(listing: dict) -> bool:
    return listing.get("is_visible", True) and listing.get("active", True)


def is_rejected(listing: dict) -> bool:
    if listing.get("sponsorship") in REJECT_SPONSORSHIP_VALUES:
        return True
    notes_lower = (listing.get("raw_notes") or "").lower()
    if any(kw in notes_lower for kw in REJECT_NOTES_KEYWORDS):
        return True
    title_lower = (listing.get("title") or "").lower()
    if any(kw in title_lower for kw in REJECT_TITLE_KEYWORDS):
        return True
    company_lower = (listing.get("company") or "").lower()
    if any(c.lower() in company_lower for c in REJECT_COMPANIES):
        return True
    return False


def should_surface(listing: dict) -> bool:
    if not is_active(listing):
        return False
    if is_rejected(listing):
        return False
    if not passes_category(listing):
        return False
    if not passes_title(listing):
        return False
    return True
