"""Handshake (BU-specific) session-cookie scraper.

Owner exports a session cookie weekly into .secrets/handshake_session.txt.
We poll their authenticated view of the BU job board, scoped to the owner's
own data (which is permitted use).

This scraper is a skeleton because Handshake redesigns frequently; once owner
provides a cookie + URL, we tune the selectors. For now: returns 0 with a
clear warning if cookie missing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.paths import SECRETS_DIR
from src.schema import JobPosting

log = configure_logging("ingest.handshake")

COOKIE_PATH = SECRETS_DIR / "handshake_session.txt"
JOB_LIST_URL = "https://bu.joinhandshake.com/jobs"


def _load_cookie() -> str | None:
    if not COOKIE_PATH.exists():
        log.warning("handshake cookie missing",
                    extra={"path": str(COOKIE_PATH),
                           "hint": "export Chrome cookie value for _SESSION_ID after logging into bu.joinhandshake.com"})
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
        log.warning("handshake fetch failed", extra={"err": str(e)})
        return []
    if resp.status_code in (401, 403) or "login" in resp.url.path.lower():
        log.warning("handshake cookie expired — owner must refresh")
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[JobPosting] = []
    # Selectors are best-effort; tune after owner exports a real session.
    for card in soup.select("[data-test*='job'], [data-hook*='job'], a[href^='/jobs/']"):
        link = card.get("href") if card.name == "a" else None
        if not link:
            link_el = card.find("a", href=True)
            if link_el:
                link = link_el["href"]
        if not link:
            continue
        if link.startswith("/"):
            link = "https://bu.joinhandshake.com" + link
        title_el = card.find(["h2", "h3"])
        title = title_el.get_text(strip=True) if title_el else card.get_text(strip=True)[:80]
        if not title:
            continue
        company_el = card.select_one("[class*='employer'], [class*='company']")
        company = company_el.get_text(strip=True) if company_el else ""
        location_el = card.select_one("[class*='location']")
        location = location_el.get_text(strip=True) if location_el else ""
        out.append(
            build_posting(
                source="handshake",
                company=company or "(handshake unknown)",
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
    log.info("handshake fetched", extra={"count": len(out)})
    return out
