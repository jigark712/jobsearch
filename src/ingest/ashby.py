"""Ashby public job board API.

API: https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true
"""
from datetime import datetime, timezone

from src.http_client import get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.ashby")


def fetch_company(slug: str) -> list[JobPosting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    try:
        resp = get(url)
    except Exception as e:
        log.warning("ashby fetch failed", extra={"slug": slug, "err": str(e)})
        return []
    data = resp.json() or {}
    jobs = data.get("jobs", [])
    out: list[JobPosting] = []
    for j in jobs:
        title = (j.get("title") or "").strip()
        if not title:
            continue
        location = j.get("location") or ""
        # secondaryLocations is a list; concatenate for visibility
        sec = j.get("secondaryLocations") or []
        if sec:
            sec_str = "; ".join(s.get("location", "") for s in sec if s.get("location"))
            if sec_str:
                location = f"{location}; {sec_str}" if location else sec_str
        url_canonical = j.get("jobUrl", "")
        url_apply = j.get("applyUrl") or url_canonical
        posted = None
        if j.get("publishedAt"):
            try:
                posted = datetime.fromisoformat(j["publishedAt"].replace("Z", "+00:00")).date()
            except ValueError:
                posted = None
        jd_text = j.get("descriptionPlain") or j.get("descriptionHtml") or ""
        out.append(
            build_posting(
                source="ashby",
                company=slug,
                title=title,
                location=location,
                url_canonical=url_canonical,
                url_apply=url_apply,
                jd_text=jd_text,
                posted_date=posted,
                raw_payload=j,
            )
        )
    log.info("ashby fetched", extra={"slug": slug, "count": len(out)})
    return out


def fetch_all(slugs: list[str]) -> list[JobPosting]:
    out: list[JobPosting] = []
    for slug in slugs:
        out.extend(fetch_company(slug))
    return out
