"""Fetch + normalize SimplifyJobs Summer2026-Internships listings.json.

This is the primary source. The repo's automated pipeline updates this JSON
file daily, so it's the most reliable feed of summer 2026 internships.
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("source.simplify")

URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json"
UA = "internship-notifier/1.0 personal-job-search"


def fetch() -> list[dict]:
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("simplify fetch failed: %s", e)
        return []

    if not isinstance(data, list):
        log.warning("simplify response unexpected shape; got %s", type(data).__name__)
        return []

    out: list[dict] = []
    for raw in data:
        try:
            out.append(_normalize(raw))
        except Exception as e:
            log.warning("simplify normalize failed for id=%s: %s", raw.get("id"), e)
    log.info("simplify fetched: %d listings", len(out))
    return out


def _normalize(raw: dict) -> dict:
    """SimplifyJobs schema observed 2026-05-22:
      keys: active, category (str), company_name, company_url, date_posted,
            date_updated, degrees, id, is_visible, locations, source,
            sponsorship, terms, title, url
    No `categories` list, no `monthly_pay`, no `notes` field — older spec is stale.
    """
    locations = raw.get("locations") or []
    location_str = " / ".join(str(L) for L in locations) if locations else ""
    # Normalize the single `category` string into the list shape the filter expects.
    category = raw.get("category")
    categories = [category] if category else []
    return {
        "id": str(raw.get("id") or ""),
        "source": "simplify",
        "company": raw.get("company_name") or "",
        "title": raw.get("title") or "",
        "location": location_str,
        "url": raw.get("url") or "",
        "posted_ts": int(raw.get("date_updated") or 0),
        "pay": None,  # schema no longer exposes monthly_pay
        "sponsorship": raw.get("sponsorship") or "",
        "raw_notes": "",  # schema no longer exposes notes
        "categories": categories,
        "is_visible": bool(raw.get("is_visible", True)),
        "active": bool(raw.get("active", True)),
    }
