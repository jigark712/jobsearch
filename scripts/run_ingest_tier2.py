"""Tier 2 (Jobright + Handshake) + Tier 3 (LinkedIn RSS) daily runner."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dedupe import dedupe
from src.ingest import handshake, hn_whos_hiring, jobright, linkedin_rss, otta
from src.logging_setup import configure_logging
from src.storage import append_postings

log = configure_logging("scripts.tier2")


def main() -> int:
    all_postings = []
    for name, fn in (("jobright", jobright.fetch_all),
                     ("handshake", handshake.fetch_all),
                     ("otta", otta.fetch_all),
                     ("linkedin_rss", linkedin_rss.fetch_all),
                     ("hn_whos_hiring", hn_whos_hiring.fetch_all)):
        log.info("ingesting", extra={"source": name})
        postings = fn()
        log.info("ingested", extra={"source": name, "count": len(postings)})
        all_postings.extend(postings)
    kept, _ = dedupe(all_postings)
    n = append_postings(kept)
    log.info("written", extra={"count": n})
    return 0


if __name__ == "__main__":
    sys.exit(main())
