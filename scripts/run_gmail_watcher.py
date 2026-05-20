"""Poll Gmail and update Job Tracker sheet."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.logging_setup import configure_logging
from src.tracker.gmail_watcher import poll_and_update

log = configure_logging("scripts.gmail")


def main() -> int:
    counts = poll_and_update()
    log.info("gmail watcher run complete", extra=counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
