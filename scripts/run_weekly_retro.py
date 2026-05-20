"""Generate and email the Sunday weekly retro."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import preferences
from src.emailer import send_email
from src.logging_setup import configure_logging
from src.retro import build_retro
from src.paths import RETROS_DIR, ensure_data_dirs
from src.tracker.sunday_fallback import send_fallback_email

log = configure_logging("scripts.retro")


def main() -> int:
    ensure_data_dirs()
    md, stats = build_retro()
    path = RETROS_DIR / f"{date.today().isoformat()}.md"
    path.write_text(md)
    log.info("retro written", extra={"path": str(path), **stats})
    to = os.environ.get("OWNER_EMAIL") or preferences()["owner"]["email"]
    send_email(to, f"Weekly Job Retro — {date.today().isoformat()}", md)
    # Also fire the Sunday fallback email asking about untracked apps
    send_fallback_email()
    return 0


if __name__ == "__main__":
    sys.exit(main())
