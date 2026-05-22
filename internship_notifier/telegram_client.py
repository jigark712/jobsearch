"""Thin wrapper around the Telegram Bot API.

Uses the bot token + chat id from env vars. Failures are logged and swallowed
so a bad send doesn't crash the run (notifier.py decides whether to mark the
listing as seen based on the return value).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger("telegram")

API_BASE = "https://api.telegram.org"


def _token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _chat_id() -> str | None:
    return os.environ.get("TELEGRAM_CHAT_ID")


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
    """Send one formatted listing. Returns True on success."""
    pay = listing.get("pay") or "Pay not listed"
    sponsorship = listing.get("sponsorship") or "Unknown"
    body = (
        f"🔥 NEW INTERNSHIP\n\n"
        f"{listing['company']} — {listing['title']}\n"
        f"📍 {listing.get('location') or 'Location not listed'}\n"
        f"💰 {pay}\n"
        f"🛂 Sponsorship: {sponsorship}\n"
        f"📅 Posted: {_format_time_ago(listing.get('posted_ts'))}\n"
        f"🔗 {listing['url']}"
    )
    return send_text(body)


def send_text(text: str) -> bool:
    """Send raw text. parse_mode None to avoid Markdown escaping pain."""
    token = _token()
    chat = _chat_id()
    if not token or not chat:
        log.warning("telegram env vars missing; would have sent: %s", text[:80])
        return False
    url = f"{API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    # Retry once on 429 (rate limit) using the retry_after hint.
    for attempt in range(2):
        try:
            r = requests.post(url, json=payload, timeout=15)
        except Exception as e:
            log.warning("telegram send failed: %s", e)
            return False
        if r.status_code == 200:
            return True
        if r.status_code == 429 and attempt == 0:
            try:
                retry_after = r.json().get("parameters", {}).get("retry_after", 2)
            except Exception:
                retry_after = 2
            time.sleep(min(retry_after, 10))
            continue
        log.warning("telegram non-200: %s %s", r.status_code, r.text[:200])
        return False
    return False
