"""Component 1: Profile / role cluster match. Max 12."""
from __future__ import annotations

import re

from src.config_loader import preferences
from src.schema import JobPosting

# Pre-compile cluster keyword regex from preferences.
_CLUSTER_PATTERNS: dict[str, re.Pattern] | None = None


def _patterns() -> dict[str, re.Pattern]:
    global _CLUSTER_PATTERNS
    if _CLUSTER_PATTERNS is not None:
        return _CLUSTER_PATTERNS
    prefs = preferences()["target_roles"]
    _CLUSTER_PATTERNS = {}
    for cluster in ("primary_cluster", "secondary_cluster", "opportunistic_cluster", "occasional"):
        words = prefs.get(cluster) or []
        # Each entry like "AI Engineer" → match as phrase
        if not words:
            continue
        pattern = "|".join(re.escape(w) for w in words)
        _CLUSTER_PATTERNS[cluster] = re.compile(pattern, re.IGNORECASE)
    return _CLUSTER_PATTERNS


def score(posting: JobPosting) -> tuple[int, str]:
    pats = _patterns()
    title = posting.title
    for cluster, score_val, label in (
        ("primary_cluster", 12, "primary"),
        ("secondary_cluster", 9, "secondary"),
        ("opportunistic_cluster", 6, "opportunistic"),
        ("occasional", 3, "occasional"),
    ):
        if cluster in pats and pats[cluster].search(title):
            return score_val, f"title matches {label} cluster"
    return 0, "no cluster match"
