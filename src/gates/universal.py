"""Universal hard gates applied to every posting regardless of track.

Returns a tuple (passed: bool, reason: str). Reason is empty if passed.
"""
from __future__ import annotations

import re

from src.config_loader import preferences
from src.schema import JobPosting

# Pre-compile blocked-title regex from preferences on first call.
_BLOCKED_TITLES = None
_SPONSORSHIP_PATTERNS = [
    r"no sponsorship now or in the future",
    r"must be a us citizen",
    r"u\.?s\.?\s+citizenship\s+required",
    r"active security clearance required",
    r"clearance\s+required",
    r"\bts/sci\b",
    r"\bsecret clearance\b",
    r"must be authorized to work in the us without sponsorship now and in the future",
    r"we do not sponsor visas",
    r"unable to sponsor",
    r"will not sponsor",
    r"no visa sponsorship",
]
_SPONSORSHIP_RE = re.compile("|".join(_SPONSORSHIP_PATTERNS), re.IGNORECASE)


def _blocked_titles_re():
    global _BLOCKED_TITLES
    if _BLOCKED_TITLES is None:
        words = preferences()["target_roles"]["blocked_titles"]
        # exact-word match for senior/staff/etc.
        _BLOCKED_TITLES = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in words) + r")\b",
            re.IGNORECASE,
        )
    return _BLOCKED_TITLES


def check_title(posting: JobPosting) -> tuple[bool, str]:
    m = _blocked_titles_re().search(posting.title)
    if m:
        return False, f"title:blocked_word:{m.group(1)}"
    return True, ""


def check_sponsorship(posting: JobPosting) -> tuple[bool, str]:
    haystack = (posting.title or "") + "\n" + (posting.jd_text or "")
    m = _SPONSORSHIP_RE.search(haystack)
    if m:
        return False, f"sponsorship:{m.group(0)[:40]}"
    return True, ""


def check_blocklist(posting: JobPosting) -> tuple[bool, str]:
    blocklist = [b.lower() for b in (preferences().get("company_blocklist") or [])]
    if posting.company.lower() in blocklist:
        return False, "company_blocklist"
    return True, ""


GATES = [check_title, check_sponsorship, check_blocklist]


def run(posting: JobPosting) -> tuple[bool, str]:
    for gate in GATES:
        ok, reason = gate(posting)
        if not ok:
            return False, reason
    return True, ""
