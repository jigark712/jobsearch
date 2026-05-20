"""Component 7: Company / source credibility. Max 8."""
from __future__ import annotations

from src.schema import JobPosting

_SOURCE_SCORE = {
    "greenhouse": 8,
    "lever": 8,
    "ashby": 8,
    "workday": 8,
    "handshake": 7,
    "yc": 7,
    "wellfound": 7,
    "builtin": 5,
    "jobright": 4,
    "linkedin_rss": 5,
    "twitter": 2,
}


def score(posting: JobPosting) -> tuple[int, str]:
    src = posting.source.split(":", 1)[0]
    if src.startswith("github_repo"):
        return 7, f"github repo: {posting.source}"
    val = _SOURCE_SCORE.get(src, 0)
    return val, f"source={src}"
