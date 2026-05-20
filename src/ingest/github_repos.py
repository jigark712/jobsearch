"""GitHub-curated job repos ingestor.

These repos maintain tables of new-grad / internship postings. We pull the raw
README and parse rows. SimplifyJobs uses HTML <table>; older convention was
pipe-markdown. We handle both.

Per-repo configuration includes the raw URL and a 'kind' hint used by track
classification downstream.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from src.http_client import get
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.schema import JobPosting

log = configure_logging("ingest.github_repos")

_REPO_CONFIG: dict[str, dict] = {
    "https://github.com/SimplifyJobs/New-Grad-Positions": {
        "raw": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
        "kind": "new_grad",
    },
    "https://github.com/jobright-ai/2025-Software-Engineer-New-Grad": {
        "raw": "https://raw.githubusercontent.com/jobright-ai/2025-Software-Engineer-New-Grad/master/README.md",
        "kind": "new_grad",
    },
    "https://github.com/SimplifyJobs/Summer2026-Internships": {
        "raw": "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md",
        "kind": "summer_intern",
    },
}

_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_HTML_LINK = re.compile(r'<a\s+href=["\'](https?://[^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
_IMG = re.compile(r"<img[^>]*>|!\[[^\]]*\]\([^)]+\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_md(cell: str) -> str:
    cell = _IMG.sub("", cell)
    cell = _HTML_TAG_RE.sub(" ", cell)
    cell = cell.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", cell).strip()


def _extract_link(cell: str | Tag) -> str | None:
    if isinstance(cell, Tag):
        a = cell.find("a", href=True)
        if a:
            return a["href"]
        text = str(cell)
    else:
        text = cell
    m = _MD_LINK.search(text)
    if m:
        return m.group(2)
    m = _HTML_LINK.search(text)
    if m:
        return m.group(1)
    return None


def _parse_date(s: str):
    import dateparser
    if not s:
        return None
    s = _strip_md(s)
    if not s or s in ("-", "N/A"):
        return None
    try:
        dt = dateparser.parse(s)
        return dt.date() if dt else None
    except Exception:
        return None


def _classify_headers(headers: list[str]) -> dict[str, int] | None:
    """Map normalized header text → column index."""
    idx: dict[str, int] = {}
    for i, h in enumerate(h.lower() for h in headers):
        if "company" in h or h == "name":
            idx.setdefault("company", i)
        elif "role" in h or "position" in h or "title" in h:
            idx.setdefault("title", i)
        elif "location" in h:
            idx.setdefault("location", i)
        elif "link" in h or "apply" in h or "application" in h:
            idx.setdefault("link", i)
        elif "date" in h or "posted" in h or "age" in h:
            idx.setdefault("date", i)
    if "company" in idx and "title" in idx:
        return idx
    return None


def _parse_html_tables(html: str) -> list[tuple[dict[str, int], list[list[Tag]]]]:
    """Return list of (column-index map, rows-of-<td>) for each useful HTML table."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        headers_row = table.find("tr")
        if not headers_row:
            continue
        header_cells = headers_row.find_all(["th", "td"])
        headers_text = [c.get_text(strip=True) for c in header_cells]
        cols = _classify_headers(headers_text)
        if not cols:
            continue
        rows: list[list[Tag]] = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if not cells:
                continue
            rows.append(cells)
        if rows:
            out.append((cols, rows))
    return out


def _parse_pipe_tables(md: str) -> list[tuple[dict[str, int], list[list[str]]]]:
    """Return list of (column-index map, rows-of-cell-strings) for pipe tables."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.lstrip().startswith("|"):
            current.append(line.strip())
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    out = []
    for block in blocks:
        if len(block) < 3:
            continue
        if not re.match(r"^\|[\s\-:|]+\|$", block[1]):
            continue
        header_cells = [c.strip() for c in block[0].strip("|").split("|")]
        cols = _classify_headers(header_cells)
        if not cols:
            continue
        rows = [
            [c.strip() for c in row.strip("|").split("|")]
            for row in block[2:]
        ]
        if rows:
            out.append((cols, rows))
    return out


def _cell_text(cell) -> str:
    if isinstance(cell, Tag):
        return cell.get_text(" ", strip=True)
    return _strip_md(cell)


def fetch_repo(repo_url: str) -> list[JobPosting]:
    cfg = _REPO_CONFIG.get(repo_url)
    if not cfg:
        log.warning("unknown repo", extra={"url": repo_url})
        return []
    try:
        resp = get(cfg["raw"])
    except Exception as e:
        log.warning("github fetch failed", extra={"url": repo_url, "err": str(e)})
        return []

    repo_slug = urlparse(repo_url).path.strip("/")
    source = f"github_repo:{repo_slug}"

    tables: list[tuple[dict[str, int], list]] = []
    if "<table" in resp.text:
        tables.extend(_parse_html_tables(resp.text))
    tables.extend(_parse_pipe_tables(resp.text))

    if not tables:
        log.warning("no usable tables found", extra={"url": repo_url})
        return []

    out: list[JobPosting] = []
    seen: set[tuple[str, str, str]] = set()
    last_company = ""

    for cols, rows in tables:
        for row in rows:
            if max(cols.values()) >= len(row):
                continue
            company_cell = row[cols["company"]]
            company_text = _cell_text(company_cell)
            # SimplifyJobs continuation markers
            if company_text.strip() in ("↳", "↳ ", "&#x21B3;", "↳"):
                company = last_company
            else:
                # strip surrounding link syntax: "[Acme](https://...)" -> "Acme"
                company = company_text
                last_company = company
            if not company:
                continue

            title_cell = row[cols["title"]]
            title = _cell_text(title_cell)
            if not title or title.lower() in ("role", "title", "position"):
                continue

            location = _cell_text(row[cols["location"]]) if "location" in cols else ""

            link = None
            if "link" in cols:
                link = _extract_link(row[cols["link"]])
            if not link:
                link = _extract_link(title_cell) or _extract_link(company_cell)
            if not link:
                continue  # no apply URL = not actionable

            posted = _parse_date(_cell_text(row[cols["date"]])) if "date" in cols else None

            key = (company.lower(), title.lower(), location.lower())
            if key in seen:
                continue
            seen.add(key)

            out.append(
                build_posting(
                    source=source,
                    company=company,
                    title=title,
                    location=location,
                    url_canonical=link,
                    url_apply=link,
                    jd_text="",
                    posted_date=posted,
                    raw_payload={"repo": repo_url},
                    first_seen=datetime.now(timezone.utc),
                )
            )

    log.info("github repo parsed", extra={"url": repo_url, "count": len(out)})
    return out


def fetch_all(repo_urls: list[str]) -> list[JobPosting]:
    out: list[JobPosting] = []
    for url in repo_urls:
        out.extend(fetch_repo(url))
    return out
