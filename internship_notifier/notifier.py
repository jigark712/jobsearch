"""Main entrypoint for the internship notifier.

Run directly: `python internship_notifier/notifier.py`
Requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from internship_notifier.filters import should_surface
from internship_notifier.sources import simplify, wellfound, yc
from internship_notifier.telegram_client import send_listing, send_text

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("notifier")

SEEN_PATH = ROOT / "data" / "seen_ids.json"
MAX_PER_RUN = 10
OVERFLOW_SOURCE_URL = "https://github.com/SimplifyJobs/Summer2026-Internships"
# First-run backfill protection: if seen_ids is empty AND we'd notify > this
# many listings, silently mark them all seen and notify nothing. Prevents a
# launch-day spam blast of old listings.
FIRST_RUN_BACKFILL_THRESHOLD = 25


def load_seen_ids() -> set[str]:
    if not SEEN_PATH.exists():
        log.warning("seen_ids.json missing; starting empty")
        return set()
    try:
        data = json.loads(SEEN_PATH.read_text())
        if not isinstance(data, list):
            raise ValueError("not a list")
        return {str(x) for x in data}
    except Exception as e:
        log.warning("seen_ids.json malformed (%s); starting empty", e)
        return set()


def save_seen_ids(seen: set[str]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(sorted(seen), indent=2) + "\n")


def fetch_all_sources() -> list[dict]:
    listings: list[dict] = []
    for name, fetch_fn in (("simplify", simplify.fetch),
                           ("yc", yc.fetch),
                           ("wellfound", wellfound.fetch)):
        try:
            listings.extend(fetch_fn())
        except Exception as e:
            log.warning("%s source raised unhandled exception: %s", name, e)
    return listings


def main() -> int:
    seen = load_seen_ids()
    log.info("loaded seen ids: %d", len(seen))

    listings = fetch_all_sources()
    log.info("total listings fetched: %d", len(listings))

    filtered = [L for L in listings if L.get("id") and should_surface(L)]
    log.info("after filters: %d", len(filtered))

    new_listings = [L for L in filtered if L["id"] not in seen]
    log.info("new (unseen): %d", len(new_listings))

    new_listings.sort(key=lambda x: x.get("posted_ts") or 0, reverse=True)

    is_first_run = len(seen) == 0
    if is_first_run and len(new_listings) > FIRST_RUN_BACKFILL_THRESHOLD:
        log.warning(
            "first run with %d listings; backfilling seen_ids silently to avoid Telegram spam. "
            "Future runs will only notify on genuinely new postings.",
            len(new_listings)
        )
        for L in new_listings:
            seen.add(L["id"])
        save_seen_ids(seen)
        send_text(
            f"✅ Internship notifier is live. Silently marked {len(new_listings)} existing "
            f"listings as seen so you don't get a spam blast. You'll get a message here "
            f"the next time a fresh internship is posted that matches your filters."
        )
        log.info("run complete (backfill): seen_total=%d", len(seen))
        return 0

    to_notify = new_listings[:MAX_PER_RUN]
    overflow = len(new_listings) - len(to_notify)

    sent = 0
    for listing in to_notify:
        if send_listing(listing):
            seen.add(listing["id"])
            sent += 1
        else:
            log.warning("telegram send failed for %s; will retry next run", listing["id"])

    if overflow > 0 and sent > 0:
        send_text(
            f"... and {overflow} more new listings. "
            f"Check the full list: {OVERFLOW_SOURCE_URL}"
        )

    save_seen_ids(seen)
    log.info("run complete: sent=%d overflow=%d seen_total=%d",
             sent, overflow, len(seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
