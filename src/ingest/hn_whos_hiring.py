"""Hacker News "Who is hiring?" monthly thread ingestor.

On the 1st of each month, HN posts a thread titled "Ask HN: Who is hiring?".
Top-level comments are individual job postings, usually in the format:

    Company | Role | Location | (REMOTE) | (INTERN|FT|CONTRACT)
    short description
    https://apply.url

We use the public HN API (no auth) to find the current month's thread, fetch
all top-level comments, and parse each into a JobPosting.

API:
- Search:    https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+hiring&tags=story
- Item:      https://hacker-news.firebaseio.com/v0/item/{id}.json
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.http_client import BROWSER_HEADERS, get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.hn_whos_hiring")

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+hiring&tags=story&hitsPerPage=5"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_REMOTE_RE = re.compile(r"\bREMOTE\b", re.IGNORECASE)


def _find_current_thread_id() -> int | None:
    """Find the most recent 'Who is hiring' thread by author whoishiring."""
    try:
        r = get(ALGOLIA_SEARCH, headers=BROWSER_HEADERS, timeout=15.0)
    except Exception as e:
        log.warning("hn search failed", extra={"err": str(e)})
        return None
    data = r.json()
    for hit in data.get("hits", []):
        title = hit.get("title", "").lower()
        author = (hit.get("author") or "").lower()
        if "who is hiring" in title and author == "whoishiring":
            return int(hit["objectID"])
    return None


def _fetch_item(item_id: int) -> dict | None:
    try:
        r = get(HN_ITEM.format(id=item_id), headers=BROWSER_HEADERS, timeout=15.0, max_retries=1)
    except Exception:
        return None
    return r.json() if r.content else None


def _parse_comment(html: str) -> tuple[str, str, str, str] | None:
    """Return (company, title, location, link) or None if unparseable.

    HN convention: first non-empty line is the metadata pipe-separated, e.g.
       Acme Corp | Senior SWE | San Francisco | ONSITE/REMOTE | FT
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [L.strip() for L in text.split("\n") if L.strip()]
    if not lines:
        return None
    header = lines[0]
    parts = [p.strip() for p in re.split(r"\s*[|·•]\s*", header)]
    if len(parts) < 2:
        return None
    company = parts[0]
    # Walk parts; title is usually parts[1], location is the first part containing a comma or city keyword
    title_candidates = parts[1:]
    title = title_candidates[0] if title_candidates else ""
    location = ""
    for p in parts[1:]:
        if _REMOTE_RE.search(p):
            location = "Remote"
            if "us" in p.lower() or "united states" in p.lower():
                location = "Remote-US"
            break
        if "," in p or any(city in p.lower() for city in
                            ("san francisco", "new york", "boston", "seattle", "austin",
                             "remote", "london", "berlin", "toronto")):
            location = p
            break
    # Find first URL in the entire comment body
    link = ""
    urls = _URL_RE.findall(text)
    for u in urls:
        # Skip HN-internal links
        if "ycombinator.com" in u or "news.ycombinator.com" in u:
            continue
        link = u.rstrip(".,);")
        break
    if not link:
        # Some commenters don't include URLs — skip those (not actionable)
        return None
    return company, title, location, link


def fetch_all() -> list[JobPosting]:
    thread_id = _find_current_thread_id()
    if not thread_id:
        log.warning("could not find current Who is hiring thread")
        return []
    log.info("hn thread found", extra={"id": thread_id})
    thread = _fetch_item(thread_id)
    if not thread:
        return []
    kids = thread.get("kids") or []
    out: list[JobPosting] = []
    posted_date = None
    if thread.get("time"):
        posted_date = datetime.fromtimestamp(thread["time"], tz=timezone.utc).date()
    for kid_id in kids[:300]:  # cap; some threads have 1000+ comments
        item = _fetch_item(kid_id)
        if not item or item.get("deleted") or not item.get("text"):
            continue
        parsed = _parse_comment(item["text"])
        if not parsed:
            continue
        company, title, location, link = parsed
        if not company or not title:
            continue
        comment_posted = datetime.fromtimestamp(item["time"], tz=timezone.utc).date() if item.get("time") else posted_date
        out.append(
            build_posting(
                source="hn_whos_hiring",
                company=company,
                title=title,
                location=location,
                url_canonical=link,
                url_apply=link,
                jd_text=BeautifulSoup(item["text"], "lxml").get_text("\n", strip=True),
                posted_date=comment_posted,
                raw_payload={"hn_comment_id": kid_id, "hn_thread_id": thread_id},
                first_seen=datetime.now(timezone.utc),
            )
        )
    log.info("hn comments parsed", extra={"thread_id": thread_id, "count": len(out)})
    return out
