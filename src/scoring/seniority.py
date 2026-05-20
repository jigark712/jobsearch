"""Component 4: Seniority / new-grad friendliness. Max 12."""
from __future__ import annotations

import re

from src.schema import JobPosting

_NEW_GRAD = re.compile(r"\b(new\s*grad|new\s*graduate|recent\s*graduate|university\s*grad)\b", re.IGNORECASE)
_YOE = re.compile(r"(\d+)\s*\+?\s*(?:to\s*(\d+))?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def score(posting: JobPosting) -> tuple[int, str]:
    text = (posting.title + " " + (posting.jd_text or ""))[:6000]
    if _NEW_GRAD.search(text):
        return 12, "new-grad keyword"
    matches = _YOE.findall(text)
    if not matches:
        return 9, "no YoE requirement detected (treated as 0-2)"
    # Take the smallest stated min YoE
    mins = [int(m[0]) for m in matches if m[0].isdigit()]
    if not mins:
        return 9, "unparseable YoE"
    floor = min(mins)
    if floor <= 0:
        return 12, "0+ years"
    if floor <= 2:
        return 12, f"{floor}+ years (new-grad fit)"
    if floor <= 3:
        return 9, f"{floor}+ years"
    if floor <= 4:
        return 6, f"{floor}+ years"
    if floor <= 5:
        return 3, f"{floor}+ years"
    return 0, f"{floor}+ years (out of range)"
