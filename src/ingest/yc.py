"""YC Work at a Startup ingestor.

workatastartup.com requires a logged-in YC account to view full job listings
via the official UI, BUT it exposes a public Algolia search endpoint that
companies feed when they post jobs. We use the company directory pages which
are public, then fetch /jobs/{id} for each role.

This is fragile — YC redesigns the site periodically. If parsing breaks,
disable this source in companies.yaml and fall back to GitHub repos which
mirror many YC postings.
"""
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.yc")

BASE = "https://www.workatastartup.com"


def fetch_jobs_page() -> list[JobPosting]:
    """Pull the public /jobs index page.

    NOTE: The public page is heavily JS-rendered; without a headless browser we
    will get limited results. For now we extract whatever appears in the initial
    HTML. Owner can supplement via the GitHub-curated YC lists (SimplifyJobs etc).
    """
    url = f"{BASE}/jobs"
    try:
        resp = get(url, timeout=30.0, headers=BROWSER_HEADERS)
    except Exception as e:
        log.warning("yc fetch failed", extra={"err": str(e)})
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[JobPosting] = []
    # Server-rendered job cards (best-effort selectors; YC changes these)
    for card in soup.select("a[href^='/jobs/']"):
        href = card.get("href", "")
        if not href.startswith("/jobs/"):
            continue
        link = BASE + href
        title = card.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        # Walk up to find company + location text
        parent = card.find_parent()
        company = ""
        location = ""
        if parent:
            company_el = parent.select_one("[class*='company']") or parent.find("h3")
            if company_el:
                company = company_el.get_text(strip=True)
            location_el = parent.select_one("[class*='location']")
            if location_el:
                location = location_el.get_text(strip=True)
        out.append(
            build_posting(
                source="yc",
                company=company or "(unknown YC company)",
                title=title,
                location=location,
                url_canonical=link,
                url_apply=link,
                jd_text="",  # fetched lazily by scorer if needed
                posted_date=None,
                raw_payload={"href": href},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("yc fetched", extra={"count": len(out)})
    return out


def fetch_all() -> list[JobPosting]:
    return fetch_jobs_page()
