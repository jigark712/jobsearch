"""Otta / Welcome to the Jungle session-cookie scraper.

Owner must place a session cookie at .secrets/otta_session.txt. Extract via:
1. Log in to https://app.welcometothejungle.com/
2. DevTools → Application → Cookies → app.welcometothejungle.com
3. Copy the full `cookie:` header from a Network request (Headers → Request Headers)
4. Save to .secrets/otta_session.txt

Otta uses GraphQL under the hood. We hit their public-after-login jobs endpoint.
If the schema changes (likely), fallback to scraping the SPA HTML — limited but works.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.paths import SECRETS_DIR
from src.schema import JobPosting

log = configure_logging("ingest.otta")

COOKIE_PATH = SECRETS_DIR / "otta_session.txt"
JOB_LIST_URL = "https://app.welcometothejungle.com/jobs"


def _load_cookie() -> str | None:
    if not COOKIE_PATH.exists():
        log.warning("otta cookie missing", extra={
            "path": str(COOKIE_PATH),
            "hint": "log into welcometothejungle.com and export Cookie header"
        })
        return None
    raw = COOKIE_PATH.read_text().strip()
    return raw if raw else None


def fetch_all() -> list[JobPosting]:
    cookie = _load_cookie()
    if not cookie:
        return []
    headers = dict(BROWSER_HEADERS)
    headers["Cookie"] = cookie.removeprefix("Cookie:").strip()
    try:
        resp = get(JOB_LIST_URL, headers=headers, timeout=30.0)
    except Exception as e:
        log.warning("otta fetch failed", extra={"err": str(e)})
        return []
    if resp.status_code in (401, 403) or "login" in resp.text[:5000].lower():
        log.warning("otta cookie expired or invalid — owner must refresh")
        return []
    # Otta is an SPA — initial HTML has the bootstrapped __NEXT_DATA__ blob
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[JobPosting] = []
    # Best-effort: scrape any job links in the HTML
    for a in soup.select("a[href*='/companies/'][href*='/jobs/']"):
        href = a.get("href", "")
        if not href:
            continue
        link = href if href.startswith("http") else f"https://app.welcometothejungle.com{href}"
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        # extract company from URL: /companies/{slug}/jobs/{job-slug}
        parts = href.split("/")
        company = parts[parts.index("companies") + 1] if "companies" in parts else ""
        out.append(
            build_posting(
                source="otta",
                company=company or "(otta unknown)",
                title=title[:200],
                location="",
                url_canonical=link,
                url_apply=link,
                jd_text="",
                posted_date=None,
                raw_payload={"href": href},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("otta fetched", extra={"count": len(out)})
    return out
