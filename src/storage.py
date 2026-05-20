"""JSONL-per-day storage for ingested postings.

Writes append to data/jobs/raw-YYYY-MM-DD.jsonl. Each line is a JobPosting JSON.
Idempotency is the caller's responsibility (use dedupe.py).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from src.paths import JOBS_DIR, ensure_data_dirs
from src.schema import JobPosting


def _raw_path(day: str | None = None) -> Path:
    ensure_data_dirs()
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return JOBS_DIR / f"raw-{day}.jsonl"


def append_postings(postings: Iterable[JobPosting], day: str | None = None) -> int:
    path = _raw_path(day)
    n = 0
    with path.open("a") as f:
        for p in postings:
            f.write(p.model_dump_json() + "\n")
            n += 1
    return n


def iter_postings(day: str | None = None) -> Iterator[JobPosting]:
    path = _raw_path(day)
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield JobPosting.model_validate(json.loads(line))


def iter_all_postings(days: int = 30) -> Iterator[JobPosting]:
    """Iterate all raw-*.jsonl files (most recent N days)."""
    ensure_data_dirs()
    files = sorted(JOBS_DIR.glob("raw-*.jsonl"), reverse=True)[:days]
    for path in files:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield JobPosting.model_validate(json.loads(line))
