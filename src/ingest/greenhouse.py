"""Greenhouse job board API ingestor.

API: https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
content=true gives the JD HTML in the same call.
"""
from datetime import datetime, timezone

from src.http_client import get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.greenhouse")


def fetch_company(slug: str) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        resp = get(url)
    except Exception as e:
        log.warning("greenhouse fetch failed", extra={"slug": slug, "err": str(e)})
        return []
    data = resp.json()
    jobs = data.get("jobs", [])
    out: list[JobPosting] = []
    for j in jobs:
        title = j.get("title", "").strip()
        if not title:
            continue
        location = (j.get("location") or {}).get("name", "")
        url_canonical = j.get("absolute_url", "")
        posted = None
        if j.get("updated_at"):
            try:
                posted = datetime.fromisoformat(j["updated_at"].replace("Z", "+00:00")).date()
            except ValueError:
                posted = None
        out.append(
            build_posting(
                source="greenhouse",
                company=slug,  # actual company name often differs; refine later via metadata call
                title=title,
                location=location,
                url_canonical=url_canonical,
                url_apply=url_canonical,
                jd_text=j.get("content", "") or "",
                posted_date=posted,
                raw_payload=j,
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("greenhouse fetched", extra={"slug": slug, "count": len(out)})
    return out


def fetch_all(slugs: list[str]) -> list[JobPosting]:
    out: list[JobPosting] = []
    for slug in slugs:
        out.extend(fetch_company(slug))
    return out
