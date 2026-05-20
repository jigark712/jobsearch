"""LinkedIn RSS ingestor (Tier 3).

We ONLY consume RSS feeds the owner has added manually. LinkedIn does not
publish RSS for arbitrary company job pages — only some verified employers.

NO SCRAPING. NO API CALLS to LinkedIn. Per spec section 9 and 2.4.linkedin.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser

from src.config_loader import companies
from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.linkedin_rss")

# RemoteOK: titles look like "Senior Engineer @CompanyName"
_REMOTEOK_AT = re.compile(r"\s*@\s*([A-Za-z][\w &.,'’\-]+?)\s*$")
# WeWorkRemotely: titles look like "CompanyName: Senior Engineer"
_WWR_COLON = re.compile(r"^([A-Za-z][\w &.,'’\-]+?):\s*(.+)$")


def _extract_company_and_clean_title(title: str, feed_url: str) -> tuple[str, str]:
    """Returns (company, clean_title) using per-feed conventions."""
    host = urlparse(feed_url).netloc.lower()
    if "remoteok" in host:
        m = _REMOTEOK_AT.search(title)
        if m:
            return m.group(1).strip(), _REMOTEOK_AT.sub("", title).strip()
    if "weworkremotely" in host:
        m = _WWR_COLON.match(title)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", title


def fetch_all() -> list[JobPosting]:
    feeds = companies()["linkedin"].get("rss_feeds") or []
    out: list[JobPosting] = []
    seen: set[str] = set()
    for url in feeds:
        try:
            resp = get(url, headers=BROWSER_HEADERS, timeout=20.0)
        except Exception as e:
            log.warning("rss fetch failed", extra={"url": url, "err": str(e)})
            continue
        parsed = feedparser.parse(resp.text)
        host = urlparse(url).netloc.lower()
        source_label = "remoteok" if "remoteok" in host else (
            "weworkremotely" if "weworkremotely" in host else "rss")
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue
            if link in seen:
                continue
            seen.add(link)
            company, clean_title = _extract_company_and_clean_title(title, url)
            if not company:
                company = entry.get("author") or "(unknown company)"
            location = "Remote-US"  # these feeds are remote-only by definition
            posted = None
            if entry.get("published_parsed"):
                try:
                    posted = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).date()
                except (TypeError, ValueError):
                    posted = None
            out.append(
                build_posting(
                    source=source_label,
                    company=company,
                    title=clean_title,
                    location=location,
                    url_canonical=link,
                    url_apply=link,
                    jd_text=entry.get("summary", ""),
                    posted_date=posted,
                    raw_payload={"feed": url, "entry_id": entry.get("id", "")},
                    first_seen=datetime.now(timezone.utc),
                )
            )
    log.info("rss fetched", extra={"feeds": len(feeds), "count": len(out)})
    return out
