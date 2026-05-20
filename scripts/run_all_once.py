"""One-shot orchestrator: ingest → digest → tracker poll.

For local development / first-time validation. In production, schedule each
script independently per SETUP.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.logging_setup import configure_logging

log = configure_logging("scripts.all")


def main() -> int:
    # 1. Tier 1 ingest (the workhorse)
    from scripts.run_ingest_tier1 import main as tier1
    log.info("step: tier1 ingest")
    tier1(["--source", "all"])

    # 2. Tier 2/3 (degrades cleanly if cookies missing)
    from scripts.run_ingest_tier2 import main as tier2
    log.info("step: tier2 ingest")
    tier2()

    # 3. Twitter (degrades cleanly if no LLM key)
    from scripts.run_ingest_twitter import main as twitter
    log.info("step: twitter ingest")
    twitter()

    # 4. Build digest
    from scripts.run_digest import main as digest
    log.info("step: digest")
    digest(["--no-email"])

    # 5. Gmail tracker poll
    from scripts.run_gmail_watcher import main as gmail
    log.info("step: gmail watcher")
    gmail()

    log.info("all done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
