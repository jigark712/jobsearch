"""Generate and (optionally) email the daily digest."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import preferences
from src.digest import build_digest
from src.emailer import send_email
from src.logging_setup import configure_logging
from src.paths import DIGESTS_DIR, ensure_data_dirs

log = configure_logging("scripts.digest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate daily digest")
    parser.add_argument("--day", help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--no-email", action="store_true", help="skip the email send")
    parser.add_argument("--print", action="store_true", help="print digest to stdout")
    args = parser.parse_args(argv)

    ensure_data_dirs()
    md, stats = build_digest(args.day)

    day = args.day
    if not day:
        from datetime import datetime, timezone
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = DIGESTS_DIR / f"{day}.md"
    path.write_text(md)
    log.info("digest written", extra={"path": str(path), **stats})

    if args.print:
        print(md)

    if not args.no_email:
        to_addr = os.environ.get("OWNER_EMAIL") or preferences()["owner"]["email"]
        from_addr = os.environ.get("DIGEST_FROM_EMAIL") or to_addr
        ok = send_email(
            to_addr,
            f"Job Digest — {day}",
            md,
            from_addr=from_addr,
        )
        if ok:
            log.info("digest emailed")
        else:
            log.info("digest email skipped or failed; file still saved at " + str(path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
