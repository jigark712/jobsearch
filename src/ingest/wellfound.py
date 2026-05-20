"""Wellfound (formerly AngelList Talent) ingestor.

Wellfound's public listings live behind heavy Cloudflare + JS rendering;
their official API is gated. For MVP we attempt the public role search
sitemap (returns URLs) and treat each as a stub posting that the scorer
can hydrate on demand.

If sitemap access is blocked, this source returns 0 results — that's fine,
GitHub repos and YC catch most overlap.
"""
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.wellfound")

SITEMAP = "https://wellfound.com/sitemap/jobs.xml"


def fetch_all() -> list[JobPosting]:
    try:
        resp = get(SITEMAP, timeout=30.0, headers=BROWSER_HEADERS)
    except Exception as e:
        log.warning("wellfound sitemap fetch failed", extra={"err": str(e)})
        return []
    soup = BeautifulSoup(resp.text, "xml")
    out: list[JobPosting] = []
    for loc in soup.find_all("loc")[:200]:  # cap; sitemap is huge
        url = loc.get_text(strip=True)
        if "/jobs/" not in url:
            continue
        slug = url.rsplit("/", 1)[-1]
        title = slug.replace("-", " ").title()
        out.append(
            build_posting(
                source="wellfound",
                company="(wellfound — fetch JD to learn company)",
                title=title,
                location="",
                url_canonical=url,
                url_apply=url,
                jd_text="",
                posted_date=None,
                raw_payload={"slug": slug},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("wellfound fetched", extra={"count": len(out)})
    return out
