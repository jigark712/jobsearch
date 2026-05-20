"""Component 5: Full-time relevance / contract type. Max 5."""
from __future__ import annotations

import re

from src.schema import JobPosting

_CONTRACT = re.compile(r"\bcontract(?:[\s-]to[\s-]hire)?\b|\b(c2h|c2c)\b", re.IGNORECASE)
_INTERN = re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE)


def score(posting: JobPosting, track: str | None = None) -> tuple[int, str]:
    text = (posting.title + " " + (posting.jd_text or ""))[:3000].lower()
    if _INTERN.search(text):
        if track and "intern" in track:
            return 5, "intern role matches intern track"
        return 0, "intern role outside intern track"
    if "contract-to-hire" in text or "c2h" in text or "contract to hire" in text:
        return 3, "contract-to-hire"
    if _CONTRACT.search(text):
        return 1, "contract role"
    return 5, "full-time permanent"
