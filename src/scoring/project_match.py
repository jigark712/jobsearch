"""Component 3: Semantic project match (LLM-backed). Max 12.

Strategy: call Claude Haiku with JD top responsibilities and the project bank.
Cache results per (posting fingerprint, project bank hash).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.config_loader import preferences  # noqa
from src.llm import HAIKU_MODEL, call as llm_call
from src.paths import CONFIG_DIR
from src.schema import JobPosting


@lru_cache(maxsize=1)
def _resume_projects() -> list[dict]:
    with (CONFIG_DIR / "master_resume.json").open() as f:
        resume = json.load(f)
    out = []
    for p in resume.get("projects", []) or []:
        out.append({
            "name": p.get("name"),
            "stack": p.get("stack", []),
            "bullets": [b.get("text", "") for b in p.get("bullets", [])],
            "credibility": p.get("credibility_anchor", ""),
        })
    return out


def _jd_excerpt(text: str, limit: int = 1800) -> str:
    return (text or "")[:limit]


def score(posting: JobPosting) -> tuple[int, str]:
    projects = _resume_projects()
    if not projects:
        return 0, "no projects in master_resume.json"
    if not posting.jd_text:
        # No JD — fall back to title-keyword overlap (cheap).
        title_low = posting.title.lower()
        hits = sum(1 for p in projects for kw in p["stack"] if kw.lower() in title_low)
        return min(6, hits * 2), f"no JD text; title keyword hits={hits}"

    system = "You score project-to-JD evidence matches. Output JSON only."
    user_msg = (
        "JOB:\n" + _jd_excerpt(posting.jd_text) + "\n\n"
        "PROJECTS:\n" + json.dumps(projects, indent=2) + "\n\n"
        "Return JSON: {\"strong_count\": int, \"weak_count\": int, "
        "\"overall\": \"strong_2plus|strong_1|weak_only|none\", "
        "\"projects\": [{\"name\": str, \"match\": \"strong|weak|none\", \"reason\": str}]}"
    )
    result = llm_call("project_match", system, user_msg, model=HAIKU_MODEL, max_tokens=800)

    if "_no_api_key" in result or "_no_sdk" in result or "_error" in result:
        # Degrade: simple keyword overlap.
        jd_low = posting.jd_text.lower()
        hits = sum(1 for p in projects for kw in p["stack"] if kw.lower() in jd_low)
        return min(9, hits * 2), f"LLM unavailable; keyword hits={hits}"

    strong = result.get("strong_count", 0)
    weak = result.get("weak_count", 0)
    if strong >= 2:
        return 12, f"LLM: {strong} strong project matches"
    if strong == 1:
        return 9, "LLM: 1 strong project match"
    if weak >= 1:
        return 5, f"LLM: {weak} weak project match(es)"
    return 0, "LLM: no project match"
