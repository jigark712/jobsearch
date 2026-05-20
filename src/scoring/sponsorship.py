"""Component 12: H-1B sponsorship signal. Max 6.

Reads config/sponsorship_companies.csv (USCIS H-1B LCA export). If empty,
defaults to "unknown" = 2 for every company.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from src.paths import CONFIG_DIR
from src.schema import JobPosting


@lru_cache(maxsize=1)
def _sponsorship_table() -> dict[str, int]:
    out: dict[str, int] = {}
    path = CONFIG_DIR / "sponsorship_companies.csv"
    if not path.exists():
        return out
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            co = (row.get("company") or "").strip().lower()
            try:
                filings = int(row.get("h1b_filings_last_year") or 0)
            except ValueError:
                filings = 0
            if co:
                out[co] = filings
    return out


def score(posting: JobPosting, track: str = "full_time") -> tuple[int, str]:
    if track == "fall_2026_internship":
        return 4, "CPT — sponsorship n/a"
    table = _sponsorship_table()
    co_low = posting.company.lower()
    filings = None
    for k, v in table.items():
        if k in co_low or co_low in k:
            filings = v
            break
    if filings is None:
        return 2, "sponsorship unknown"
    if filings >= 5:
        return 6, f"sponsors heavily ({filings} H-1Bs/yr)"
    if filings >= 1:
        return 4, f"sponsors lightly ({filings} H-1Bs/yr)"
    return 2, "no recent H-1B filings"
