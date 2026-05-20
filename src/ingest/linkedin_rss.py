"""LinkedIn RSS ingestor (Tier 3).

We ONLY consume RSS feeds the owner has added manually. LinkedIn does not
publish RSS for arbitrary company job pages — only some verified employers.

NO SCRAPING. NO API CALLS to LinkedIn. Per spec section 9 and 2.4.linkedin.
"""
from __future__ import annotations

from datetime import datetime, timezone

import feedparser

from src.config_loader import companies
from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.linkedin_rss")


def fetch_all() -> list[JobPosting]:
    feeds = companies()["linkedin"].get("rss_feeds") or []
    out: list[JobPosting] = []
    for url in feeds:
        try:
            resp = get(url, headers=BROWSER_HEADERS, timeout=20.0)
        except Exception as e:
            log.warning("linkedin rss fetch failed", extra={"url": url, "err": str(e)})
            continue
        parsed = feedparser.parse(resp.text)
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            company = entry.get("author") or ""
            location = ""
            summary = entry.get("summary", "")
            if not title or not link:
                continue
            out.append(
                build_posting(
                    source="linkedin_rss",
                    company=company or "(via LinkedIn RSS)",
                    title=title,
                    location=location,
                    url_canonical=link,
                    url_apply=link,
                    jd_text=summary,
                    posted_date=None,
                    raw_payload={"feed": url, "entry_id": entry.get("id", "")},
                    first_seen=datetime.now(timezone.utc),
                )
            )
    log.info("linkedin rss fetched", extra={"feeds": len(feeds), "count": len(out)})
    return out
