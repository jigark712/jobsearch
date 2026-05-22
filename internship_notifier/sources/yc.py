"""YC Work at a Startup internships HTML scrape.

Gentle: one request per run with a 2-second sleep before it. The public /jobs
page is JS-heavy so server-rendered content is limited; we extract whatever
appears in the initial HTML.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("source.yc")

URL = "https://www.workatastartup.com/jobs?filters=Internship"
BASE = "https://www.workatastartup.com"
UA = "internship-notifier/1.0 personal-job-search"


def _make_id(company: str, title: str, location: str) -> str:
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{location.lower().strip()}"
    return f"yc:{hashlib.sha1(raw.encode()).hexdigest()[:16]}"


def fetch() -> list[dict]:
    time.sleep(2)
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log.warning("yc fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    out: list[dict] = []
    seen_links: set[str] = set()

    for anchor in soup.select("a[href^='/jobs/']"):
        href = anchor.get("href", "")
        if not href.startswith("/jobs/") or href in seen_links:
            continue
        seen_links.add(href)
        title = anchor.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        parent = anchor.find_parent()
        company = ""
        location = ""
        if parent:
            company_el = parent.select_one("[class*='company']") or parent.find("h3")
            if company_el:
                company = company_el.get_text(strip=True)
            location_el = parent.select_one("[class*='location']")
            if location_el:
                location = location_el.get_text(strip=True)
        if not company:
            company = "(YC company)"
        out.append({
            "id": _make_id(company, title, location),
            "source": "yc",
            "company": company,
            "title": title,
            "location": location,
            "url": BASE + href,
            "posted_ts": int(datetime.now(timezone.utc).timestamp()),
            "pay": None,
            "sponsorship": "",
            "raw_notes": "",
            "is_visible": True,
            "active": True,
        })

    log.info("yc fetched: %d listings", len(out))
    return out
