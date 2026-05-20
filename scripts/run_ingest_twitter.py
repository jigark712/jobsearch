"""Twitter watch via Nitter RSS (every 2h per spec)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dedupe import dedupe
from src.ingest import twitter_nitter
from src.logging_setup import configure_logging
from src.storage import append_postings

log = configure_logging("scripts.twitter")


def main() -> int:
    postings = twitter_nitter.fetch_all()
    log.info("twitter ingested", extra={"count": len(postings)})
    kept, _ = dedupe(postings)
    n = append_postings(kept)
    log.info("written", extra={"count": n})
    return 0


if __name__ == "__main__":
    sys.exit(main())
