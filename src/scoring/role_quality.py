"""Component 8: Role quality (company priority list + tech signals). Max 6.

Without a real comp/Glassdoor API we proxy quality with: is company on the
priority list? Are there hints of recent tech investment in the JD?
"""
from __future__ import annotations

from src.config_loader import preferences
from src.schema import JobPosting


def _all_priority_companies() -> set[str]:
    plist = preferences().get("company_priority_list") or {}
    out: set[str] = set()
    for group in plist.values():
        for c in group or []:
            out.add(c.lower())
    return out


def score(posting: JobPosting) -> tuple[int, str]:
    co_low = posting.company.lower()
    priority = _all_priority_companies()
    for p in priority:
        if p in co_low or co_low in p:
            return 6, f"priority company: {posting.company}"
    # Tech-signal proxies in JD: GenAI, agentic, RAG, vector → high
    jd_low = (posting.jd_text or "").lower()
    if any(k in jd_low for k in ("agentic", "agent framework", "rag", "vector db", "vllm")):
        return 4, "modern AI stack signals in JD"
    if any(k in jd_low for k in ("microservices", "kafka", "kubernetes", "scaling")):
        return 3, "modern infra signals in JD"
    return 0, "no quality signals"
