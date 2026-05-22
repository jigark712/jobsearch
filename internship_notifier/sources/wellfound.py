"""Wellfound AI internships HTML scrape.

Gentle: one request per run with a 2-second sleep. Wellfound is heavily
JS-rendered and often blocks generic UAs; if it returns 403/zero results
that's expected — log and move on.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("source.wellfound")

URL = "https://wellfound.com/jobs?roles[]=ai-machine-learning&jobType=internship"
UA = "internship-notifier/1.0 personal-job-search"


def _make_id(company: str, title: str, location: str) -> str:
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{location.lower().strip()}"
    return f"wellfound:{hashlib.sha1(raw.encode()).hexdigest()[:16]}"


def fetch() -> list[dict]:
    time.sleep(2)
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log.warning("wellfound fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    out: list[dict] = []

    # Wellfound's structure varies; best-effort: any anchor whose href looks like a job
    for anchor in soup.select("a[href*='/jobs/']"):
        href = anchor.get("href", "")
        if not href or "/jobs/" not in href:
            continue
        link = href if href.startswith("http") else f"https://wellfound.com{href}"
        title = anchor.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        # Best-effort company extraction
        parent = anchor.find_parent()
        company = ""
        location = ""
        if parent:
            company_el = parent.select_one("[class*='startup']") or parent.select_one("[class*='company']")
            if company_el:
                company = company_el.get_text(strip=True)
            location_el = parent.select_one("[class*='location']")
            if location_el:
                location = location_el.get_text(strip=True)
        if not company:
            company = "(Wellfound)"
        out.append({
            "id": _make_id(company, title, location),
            "source": "wellfound",
            "company": company,
            "title": title,
            "location": location,
            "url": link,
            "posted_ts": int(datetime.now(timezone.utc).timestamp()),
            "pay": None,
            "sponsorship": "",
            "raw_notes": "",
            "is_visible": True,
            "active": True,
        })

    log.info("wellfound fetched: %d listings", len(out))
    return out
