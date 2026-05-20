"""Tier 1 ingestion runner.

Pulls from Greenhouse, Lever, Ashby (JSON APIs — implemented).
TODO next: Workday, YC, Wellfound, BuiltIn, GitHub repos, Handshake.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/run_ingest_tier1.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import companies
from src.dedupe import dedupe
from src.ingest import ashby, builtin, github_repos, greenhouse, lever, wellfound, workday, yc
from src.logging_setup import configure_logging
from src.storage import append_postings

log = configure_logging("scripts.tier1")

# Sources keyed by name. Some take slug lists, some take other inputs — dispatched below.
ATS_SOURCES = {
    "greenhouse": greenhouse.fetch_all,
    "lever": lever.fetch_all,
    "ashby": ashby.fetch_all,
}
ALL_SOURCES = list(ATS_SOURCES.keys()) + ["workday", "github_repos", "yc", "wellfound", "builtin"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tier 1 ingest runner")
    parser.add_argument("--source", choices=ALL_SOURCES + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + dedupe but do not write")
    args = parser.parse_args(argv)

    cfg = companies()
    feeds = cfg["ats_feeds"]
    aggregators = cfg.get("external_aggregators", {}) or {}
    all_postings = []
    sources_to_run = ALL_SOURCES if args.source == "all" else [args.source]

    for src_name in sources_to_run:
        if src_name in ATS_SOURCES:
            slugs = [s for s in (feeds.get(src_name) or []) if isinstance(s, str)]
            if not slugs:
                log.info("no slugs configured", extra={"source": src_name})
                continue
            log.info("ingesting", extra={"source": src_name, "slugs": slugs})
            postings = ATS_SOURCES[src_name](slugs)
        elif src_name == "workday":
            entries = [e for e in (feeds.get("workday") or []) if isinstance(e, dict)]
            if not entries:
                log.info("no workday tenants configured")
                continue
            log.info("ingesting workday", extra={"count": len(entries)})
            postings = workday.fetch_all(entries)
        elif src_name == "github_repos":
            repos = aggregators.get("github_repos") or []
            if not repos:
                log.info("no github repos configured")
                continue
            log.info("ingesting github_repos", extra={"count": len(repos)})
            postings = github_repos.fetch_all(repos)
        elif src_name == "yc":
            log.info("ingesting yc")
            postings = yc.fetch_all()
        elif src_name == "wellfound":
            log.info("ingesting wellfound")
            postings = wellfound.fetch_all()
        elif src_name == "builtin":
            log.info("ingesting builtin")
            postings = builtin.fetch_all()
        else:
            continue
        log.info("ingested", extra={"source": src_name, "count": len(postings)})
        all_postings.extend(postings)

    kept, discarded = dedupe(all_postings)
    log.info("dedup complete", extra={
        "total_in": len(all_postings),
        "kept": len(kept),
        "discarded": len(discarded),
    })

    if args.dry_run:
        log.info("dry-run, not writing")
        for p in kept[:5]:
            print(f"  {p.source:12s} {p.company:20s} {p.title[:60]:60s} {p.location[:30]}")
        return 0

    written = append_postings(kept)
    log.info("written", extra={"count": written})
    return 0


if __name__ == "__main__":
    sys.exit(main())
