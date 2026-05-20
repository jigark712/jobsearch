"""Cross-source deduplication.

Two postings with the same fingerprint are the same job. When both appear,
keep the one with the most authoritative source.
"""
from src.schema import JobPosting

# Higher = more authoritative
SOURCE_PRIORITY = {
    "greenhouse": 100,
    "lever": 100,
    "ashby": 100,
    "workday": 90,
    "handshake": 85,
    "yc": 70,
    "wellfound": 65,
    "builtin": 60,
    "jobright": 50,
    "twitter": 30,
    "linkedin_rss": 40,
}


def _priority(source: str) -> int:
    base = source.split(":", 1)[0]
    if base.startswith("github_repo"):
        return 70
    return SOURCE_PRIORITY.get(base, 0)


def dedupe(postings: list[JobPosting]) -> tuple[list[JobPosting], list[JobPosting]]:
    """Returns (kept, discarded). Discarded retained so caller can log them."""
    by_fp: dict[str, JobPosting] = {}
    discarded: list[JobPosting] = []
    for p in postings:
        existing = by_fp.get(p.fingerprint)
        if existing is None:
            by_fp[p.fingerprint] = p
            continue
        if _priority(p.source) > _priority(existing.source):
            discarded.append(existing)
            by_fp[p.fingerprint] = p
        else:
            discarded.append(p)
    return list(by_fp.values()), discarded
