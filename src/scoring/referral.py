"""Component 11: Referral potential. Max 6.

Without the alumni-discovery component (post-MVP), default to:
- 6 if owner notes a referral exists (out of scope here — would need a future flag)
- 2 if priority company (boost potential)
- 2 otherwise
"""
from __future__ import annotations

from src.scoring.role_quality import _all_priority_companies
from src.schema import JobPosting


def score(posting: JobPosting) -> tuple[int, str]:
    co_low = posting.company.lower()
    if any(p in co_low or co_low in p for p in _all_priority_companies()):
        return 4, "priority company — referral worth seeking"
    return 2, "default (no alumni discovery yet)"
