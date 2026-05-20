"""Component 10: Application effort. Max 5.

Detect 'quick apply' patterns vs. essay-heavy.
"""
from __future__ import annotations

from src.schema import JobPosting


def score(posting: JobPosting) -> tuple[int, str]:
    src = posting.source.split(":", 1)[0]
    # Direct ATS = mostly quick apply
    if src in ("greenhouse", "lever", "ashby"):
        jd_low = (posting.jd_text or "").lower()
        if "take-home" in jd_low or "take home" in jd_low:
            return 1, "take-home pre-screen"
        if "cover letter" in jd_low or "describe a time" in jd_low or "essay" in jd_low:
            return 2, "essay/long-form"
        return 5, "ATS quick-apply"
    if src == "workday":
        return 3, "Workday standard"
    if src == "handshake":
        return 4, "Handshake quick"
    if src in ("yc", "wellfound"):
        return 4, "startup quick"
    return 3, "unknown effort"
