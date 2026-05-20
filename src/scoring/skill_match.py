"""Component 2: Skill match between JD and master_resume.json. Max 12."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from src.config_loader import preferences
from src.paths import CONFIG_DIR
from src.schema import JobPosting


@lru_cache(maxsize=1)
def _resume_skill_set() -> set[str]:
    with (CONFIG_DIR / "master_resume.json").open() as f:
        resume = json.load(f)
    out: set[str] = set()
    for group in (resume.get("skills") or {}).values():
        for s in group or []:
            out.add(s.lower())
    return out


@lru_cache(maxsize=1)
def _weighted_skills() -> list[tuple[str, int]]:
    w = preferences()["skill_weights"]
    out = []
    for skill in w.get("highest") or []:
        out.append((skill.lower(), 5))
    for skill in w.get("high") or []:
        out.append((skill.lower(), 3))
    for skill in w.get("medium") or []:
        out.append((skill.lower(), 2))
    for skill in w.get("low") or []:
        out.append((skill.lower(), 1))
    return out


def _jd_contains(jd_low: str, skill: str) -> bool:
    # Skills may include slashes ("LangChain / LangGraph") — split + each side
    for part in re.split(r"\s*/\s*", skill):
        part = part.strip()
        if not part:
            continue
        # word-boundary if alphanumeric, else substring
        if re.match(r"^[\w.+\-#]+$", part):
            if re.search(rf"\b{re.escape(part)}\b", jd_low):
                return True
        else:
            if part in jd_low:
                return True
    return False


def score(posting: JobPosting) -> tuple[int, str]:
    jd_low = (posting.jd_text or "").lower()
    title_low = posting.title.lower()
    haystack = f"{title_low} {jd_low}"
    if not haystack.strip():
        return 0, "no JD text"

    resume_set = _resume_skill_set()
    matched_weighted: list[str] = []
    raw_score = 0
    for skill, weight in _weighted_skills():
        if _jd_contains(haystack, skill) and (
            skill in resume_set or any(s in resume_set for s in skill.split(" / "))
        ):
            raw_score += weight
            matched_weighted.append(skill)
    # Cap at 12; saturating at ~3 highest + 2 high.
    capped = min(12, raw_score)
    reason = f"matched skills: {', '.join(matched_weighted[:6]) or 'none'}"
    return capped, reason
