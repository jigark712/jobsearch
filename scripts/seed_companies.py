"""One-time script: probe Greenhouse / Lever / Ashby for slugs of priority companies.

For each company in preferences.company_priority_list, try common slug variations
on each ATS. If a hit returns >0 jobs, mark it as found and print a YAML snippet
ready to paste into config/companies.yaml.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import preferences
from src.http_client import get


ATS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def variants(name: str) -> list[str]:
    low = name.lower()
    cleaned = (
        low.replace(" ai", "ai")
        .replace(".", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )
    out = {
        cleaned,
        cleaned.replace(" ", ""),
        cleaned.replace(" ", "-"),
        cleaned.replace(" ", "_"),
        cleaned.split(" ")[0],
    }
    return [v for v in out if v]


def jobs_count(ats: str, slug: str) -> int | None:
    url = ATS[ats].format(slug=slug)
    try:
        r = get(url, timeout=15.0, max_retries=1)
    except Exception:
        return None
    try:
        d = r.json()
    except Exception:
        return None
    if ats == "greenhouse":
        return len(d.get("jobs", []))
    if ats == "ashby":
        return len(d.get("jobs", []))
    if ats == "lever":
        return len(d) if isinstance(d, list) else None
    return None


def find(name: str) -> tuple[str, str, int] | None:
    """Return (ats, slug, job_count) or None if no match."""
    for slug in variants(name):
        for ats in ATS:
            n = jobs_count(ats, slug)
            if n and n > 0:
                return (ats, slug, n)
    return None


def main() -> int:
    prefs = preferences()
    plist = prefs["company_priority_list"]
    found_by_ats: dict[str, list[tuple[str, str, int]]] = {ats: [] for ats in ATS}
    missed: list[str] = []

    for group_name, companies in plist.items():
        for co in (companies or []):
            res = find(co)
            if res:
                ats, slug, n = res
                print(f"FOUND  {co:35s} → {ats:10s} {slug:25s} ({n} jobs)")
                found_by_ats[ats].append((co, slug, n))
            else:
                print(f"MISS   {co:35s}")
                missed.append(co)

    print("\n--- companies.yaml snippet ---\n")
    print("ats_feeds:")
    for ats, entries in found_by_ats.items():
        if not entries:
            print(f"  {ats}: []")
            continue
        print(f"  {ats}:")
        for co, slug, n in sorted(entries, key=lambda t: -t[2]):
            print(f"    - \"{slug}\"        # {co} ({n} jobs)")
    if missed:
        print("\n# Not found on Greenhouse/Lever/Ashby (likely on Workday or custom ATS):")
        for co in missed:
            print(f"#   - {co}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
