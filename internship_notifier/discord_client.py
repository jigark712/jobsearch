"""Thin wrapper around a Discord channel webhook.

Uses DISCORD_WEBHOOK_URL from env. Failures are logged and swallowed so a bad
send doesn't crash the run (notifier decides whether to mark the listing as
seen based on the return value).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger("discord")


def _webhook_url() -> str | None:
    return os.environ.get("DISCORD_WEBHOOK_URL")


def _format_time_ago(posted_ts: int | None) -> str:
    if not posted_ts:
        return "unknown"
    delta = datetime.now(timezone.utc) - datetime.fromtimestamp(posted_ts, tz=timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds ago"
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        return f"{seconds // 3600} hours ago"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


def send_listing(listing: dict) -> bool:
    """Send one formatted listing as a Discord embed (clickable, neat layout).

    Returns True on success.
    """
    pay = listing.get("pay") or "Pay not listed"
    sponsorship = listing.get("sponsorship") or "Unknown"
    location = listing.get("location") or "Location not listed"
    posted = _format_time_ago(listing.get("posted_ts"))

    embed = {
        "title": f"🔥 {listing['company']} — {listing['title']}"[:256],
        "url": listing["url"],
        "description": (
            f"📍 {location}\n"
            f"💰 {pay}\n"
            f"🛂 Sponsorship: {sponsorship}\n"
            f"📅 Posted: {posted}"
        )[:4096],
        "color": 0xE74C3C,  # red, matches 🔥
        "footer": {"text": f"source: {listing.get('source', 'unknown')}"},
    }
    return _send({"embeds": [embed]})


def send_text(text: str) -> bool:
    """Send raw text content (no embed)."""
    return _send({"content": text[:2000]})


def _send(payload: dict) -> bool:
    url = _webhook_url()
    if not url:
        log.warning("DISCORD_WEBHOOK_URL missing; would have sent: %s", str(payload)[:120])
        return False
    # Discord rate limits are generous for webhooks (~30 msgs/min) but enforced
    # per-webhook. Honor retry_after on 429.
    for attempt in range(2):
        try:
            r = requests.post(url, json=payload, timeout=15)
        except Exception as e:
            log.warning("discord send failed: %s", e)
            return False
        if r.status_code in (200, 204):
            return True
        if r.status_code == 429 and attempt == 0:
            try:
                retry_after = float(r.json().get("retry_after", 2))
            except Exception:
                retry_after = 2.0
            time.sleep(min(retry_after, 10))
            continue
        log.warning("discord non-2xx: %s %s", r.status_code, r.text[:200])
        return False
    return False
