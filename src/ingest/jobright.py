"""Jobright.ai session-cookie scraper (Tier 2).

Per spec section 3.1 + 3.2: Jobright aggregates from Greenhouse/Lever/Ashby.
We pull once daily and dedupe aggressively against Tier 1.

Owner must place a session cookie at .secrets/jobright_session.txt. Format:
single line containing the value of the `jobright_session` cookie (or full
`Cookie: ...` header — both supported).

If the cookie file is missing or expired, this source returns 0 and logs
a warning telling the owner to refresh.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.paths import SECRETS_DIR
from src.schema import JobPosting

log = configure_logging("ingest.jobright")

BASE = "https://jobright.ai"
COOKIE_PATH = SECRETS_DIR / "jobright_session.txt"
JOB_LIST_URL = f"{BASE}/jobs/recommend"


def _load_cookie() -> str | None:
    if not COOKIE_PATH.exists():
        log.warning("jobright cookie missing", extra={"path": str(COOKIE_PATH)})
        return None
    raw = COOKIE_PATH.read_text().strip()
    if not raw:
        return None
    return raw


def fetch_all() -> list[JobPosting]:
    cookie = _load_cookie()
    if not cookie:
        return []
    headers = dict(BROWSER_HEADERS)
    # Accept either "name=value" or "Cookie: name=value; other=..."
    headers["Cookie"] = cookie.removeprefix("Cookie:").strip()
    try:
        resp = get(JOB_LIST_URL, headers=headers, timeout=30.0)
    except Exception as e:
        log.warning("jobright fetch failed", extra={"err": str(e)})
        return []
    if "login" in resp.url.path.lower() or resp.status_code == 401:
        log.warning("jobright cookie expired — owner must refresh",
                    extra={"path": str(COOKIE_PATH)})
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[JobPosting] = []
    for card in soup.select("[data-job-id], [class*='job-card'], a[href*='/jobs/info/']"):
        link = card.get("href") if card.name == "a" else None
        if not link:
            link_el = card.find("a", href=True)
            if link_el:
                link = link_el["href"]
        if not link:
            continue
        if link.startswith("/"):
            link = BASE + link
        title_el = card.select_one("[class*='title'], h2, h3")
        title = title_el.get_text(strip=True) if title_el else ""
        company_el = card.select_one("[class*='company']")
        company = company_el.get_text(strip=True) if company_el else ""
        location_el = card.select_one("[class*='location']")
        location = location_el.get_text(strip=True) if location_el else ""
        if not title or not company:
            continue
        out.append(
            build_posting(
                source="jobright",
                company=company,
                title=title,
                location=location,
                url_canonical=link,
                url_apply=link,
                jd_text="",
                posted_date=None,
                raw_payload={"link": link},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("jobright fetched", extra={"count": len(out)})
    return out
