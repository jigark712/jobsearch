"""Workday tenant ingestor.

Workday tenants expose a JSON search endpoint at
  {base}/wday/cxs/{tenant}/{site}/jobs
that accepts a POST with a JSON body. The URL stored in companies.yaml is the
user-facing site like https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
which we have to translate into the cxs endpoint.

We use cautiously, per spec — every 12h, one request at a time.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from src.http_client import _polite_wait
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.workday")

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _derive_cxs(site_url: str) -> tuple[str, str, str] | None:
    """From https://{tenant}.{wdN}.myworkdayjobs.com/{site} derive (host, tenant, site)."""
    parsed = urlparse(site_url)
    host = parsed.netloc
    parts = parsed.path.strip("/").split("/")
    if not host.endswith(".myworkdayjobs.com") or not parts:
        return None
    tenant = host.split(".")[0]
    site = parts[-1]
    return host, tenant, site


# Workday rejects limit > 20 with HTTP 400. Max safe page size = 20.
_PAGE_LIMIT = 20
_MAX_PAGES = 25  # cap at 500 postings per tenant per run


def fetch_tenant(entry: dict) -> list[JobPosting]:
    """entry is {company: 'nvidia', url: '...'}.

    Posts to {base}/wday/cxs/{tenant}/{site}/jobs and pages until exhausted.
    """
    company = entry.get("company", "")
    raw_url = entry.get("url", "")
    derived = _derive_cxs(raw_url)
    if not derived:
        log.warning("workday url not parseable", extra={"company": company, "url": raw_url})
        return []
    host, tenant, site = derived
    cxs = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    site_url = f"https://{host}/{site}"
    # Workday is finicky: richer headers (Accept-Language, etc) get parsed as
    # the client locale and the request 400s. Keep headers minimal.
    headers = {
        "User-Agent": _BROWSER_UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": f"https://{host}",
        "Referer": site_url,
    }
    out: list[JobPosting] = []
    for page in range(_MAX_PAGES):
        offset = page * _PAGE_LIMIT
        payload = {"appliedFacets": {}, "limit": _PAGE_LIMIT, "offset": offset, "searchText": ""}
        _polite_wait(cxs)
        try:
            resp = httpx.post(cxs, json=payload, headers=headers, timeout=30.0)
            resp.raise_for_status()
        except Exception as e:
            log.warning("workday fetch failed",
                        extra={"company": company, "cxs": cxs, "offset": offset,
                               "err": f"{type(e).__name__}: {e}"})
            break
        data = resp.json() or {}
        postings = data.get("jobPostings", []) or []
        if not postings:
            break
        for j in postings:
            title = (j.get("title") or "").strip()
            if not title:
                continue
            location = j.get("locationsText") or ""
            ext_path = j.get("externalPath", "")
            link = f"https://{host}{ext_path}" if ext_path else site_url
            posted_str = j.get("postedOn", "") or ""
            posted = _approx_posted(posted_str)
            out.append(
                build_posting(
                    source="workday",
                    company=company,
                    title=title,
                    location=location,
                    url_canonical=link,
                    url_apply=link,
                    jd_text="",
                    posted_date=posted,
                    raw_payload=j,
                    first_seen=datetime.now(timezone.utc),
                )
            )
        total = data.get("total", 0)
        if offset + _PAGE_LIMIT >= total:
            break
    log.info("workday fetched", extra={"company": company, "count": len(out)})
    return out


_RELATIVE = re.compile(r"posted\s+(\d+)\+?\s+(day|week|month)s?\s+ago", re.IGNORECASE)


def _approx_posted(s: str):
    if not s:
        return None
    s_low = s.lower()
    if "today" in s_low:
        return datetime.now(timezone.utc).date()
    if "yesterday" in s_low:
        from datetime import timedelta
        return (datetime.now(timezone.utc) - timedelta(days=1)).date()
    m = _RELATIVE.search(s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    from datetime import timedelta
    delta = {"day": timedelta(days=n), "week": timedelta(weeks=n), "month": timedelta(days=30 * n)}[unit]
    return (datetime.now(timezone.utc) - delta).date()


def fetch_all(entries: list[dict]) -> list[JobPosting]:
    out: list[JobPosting] = []
    for entry in entries:
        if isinstance(entry, dict):
            out.extend(fetch_tenant(entry))
    return out
