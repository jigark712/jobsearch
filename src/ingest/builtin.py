"""BuiltIn Boston ingestor.

builtinboston.com renders job cards server-side on /jobs. We scrape the listing
page. For full JD text the scorer can fetch the individual job page on demand.
"""
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.builtin")

BASE = "https://www.builtinboston.com"
LISTING_URL = f"{BASE}/jobs"


def fetch_all() -> list[JobPosting]:
    try:
        resp = get(LISTING_URL, timeout=30.0, headers=BROWSER_HEADERS)
    except Exception as e:
        log.warning("builtin fetch failed", extra={"err": str(e)})
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[JobPosting] = []
    # BuiltIn uses data-id'd job cards
    for card in soup.select("[data-id][class*='job']"):
        title_el = card.select_one("h2") or card.select_one("h3") or card.select_one("a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        company_el = card.select_one("[class*='company']")
        company = company_el.get_text(strip=True) if company_el else ""
        location_el = card.select_one("[class*='location']")
        location = location_el.get_text(strip=True) if location_el else "Boston, MA"
        link_el = card.find("a", href=True)
        if not link_el:
            continue
        link = link_el["href"]
        if link.startswith("/"):
            link = BASE + link
        if not title or not company:
            continue
        out.append(
            build_posting(
                source="builtin",
                company=company,
                title=title,
                location=location,
                url_canonical=link,
                url_apply=link,
                jd_text="",
                posted_date=None,
                raw_payload={"data_id": card.get("data-id")},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("builtin fetched", extra={"count": len(out)})
    return out
