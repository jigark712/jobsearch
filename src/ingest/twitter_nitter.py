"""Twitter/X founder + recruiter watch via Nitter RSS.

For each curated handle in companies.yaml → twitter_x.watchlist_accounts, we
fetch nitter.net/{handle}/rss, rotating across mirror instances on failure.

For each new tweet (after a `_processed_tweets.txt` log), pre-filter on simple
keyword presence, then call Claude Haiku for actual classification. If the
LLM says it's a job posting with confidence >= 0.7, emit a JobPosting record
with source='twitter' (gets a -10 scoring penalty later).

Daily call cap enforced per spec section 12.5: max 200 LLM calls/day.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import feedparser

from src.config_loader import companies
from src.http_client import BROWSER_HEADERS, get
from src.llm import HAIKU_MODEL, call as llm_call
from src.logging_setup import configure_logging
from src.normalize import build_posting
from src.paths import DATA_DIR
from src.schema import JobPosting

log = configure_logging("ingest.twitter")

PROCESSED_LOG = DATA_DIR / "processed_tweets.txt"
LLM_CALL_LOG = DATA_DIR / "twitter_llm_calls.txt"

_PREFILTER_KWS = re.compile(
    r"hiring|join|open role|we'?re looking for|dm me|apply|engineer|"
    r"internship|founding|first hire|joining the team",
    re.IGNORECASE,
)


def _load_processed() -> set[str]:
    if not PROCESSED_LOG.exists():
        return set()
    return set(line.strip() for line in PROCESSED_LOG.read_text().splitlines() if line.strip())


def _mark_processed(tweet_id: str) -> None:
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_LOG.open("a") as f:
        f.write(tweet_id + "\n")


def _llm_calls_today() -> int:
    if not LLM_CALL_LOG.exists():
        return 0
    today_str = date.today().isoformat()
    return sum(1 for line in LLM_CALL_LOG.read_text().splitlines()
               if line.startswith(today_str))


def _record_llm_call() -> None:
    LLM_CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LLM_CALL_LOG.open("a") as f:
        f.write(f"{date.today().isoformat()} 1\n")


def _fetch_rss(handle: str) -> list[dict]:
    """Try each Nitter instance until one returns RSS items."""
    instances = companies()["twitter_x"]["nitter_instances"]
    for inst in instances:
        url = f"https://{inst}/{handle}/rss"
        try:
            resp = get(url, headers=BROWSER_HEADERS, timeout=20.0)
        except Exception as e:
            log.warning("nitter instance failed", extra={"instance": inst, "err": str(e)})
            continue
        parsed = feedparser.parse(resp.text)
        if parsed.entries:
            return parsed.entries
    log.warning("all nitter instances failed for handle", extra={"handle": handle})
    return []


def _classify_tweet(handle: str, text: str) -> dict:
    system = "You judge whether a tweet announces a currently-open job. Output JSON only."
    user_msg = (
        f"Tweet from @{handle}: \"{text}\"\n\n"
        "Is this announcing a real, currently-open job or internship opportunity "
        "that someone could apply to today? Output JSON:\n"
        "{\"is_job_posting\": true/false, \"company\": str or null, "
        "\"role_title\": str or null, \"is_internship\": true/false, "
        "\"is_immediate_start\": true/false, \"apply_method\": str or null, "
        "\"confidence\": 0.0-1.0}"
    )
    res = llm_call("tweet_classify", system, user_msg, model=HAIKU_MODEL, max_tokens=300)
    _record_llm_call()
    return res


def fetch_all() -> list[JobPosting]:
    cfg = companies()["twitter_x"]
    if not cfg.get("enabled"):
        return []
    accounts: list[str] = []
    for group in (cfg.get("watchlist_accounts") or {}).values():
        accounts.extend(group or [])

    processed = _load_processed()
    daily_cap = cfg.get("daily_llm_call_cap", 200)
    out: list[JobPosting] = []

    for handle in accounts:
        entries = _fetch_rss(handle)
        for entry in entries:
            tweet_id = entry.get("id") or entry.get("link")
            if not tweet_id or tweet_id in processed:
                continue
            text = entry.get("summary") or entry.get("title") or ""
            text = re.sub(r"<[^>]+>", " ", text).strip()
            if not _PREFILTER_KWS.search(text):
                _mark_processed(tweet_id)
                continue
            if _llm_calls_today() >= daily_cap:
                log.warning("twitter LLM call cap reached", extra={"cap": daily_cap})
                return out
            res = _classify_tweet(handle, text)
            _mark_processed(tweet_id)
            if not res.get("is_job_posting"):
                continue
            if (res.get("confidence") or 0) < 0.7:
                continue
            company = res.get("company") or handle
            title = res.get("role_title") or "(role from tweet)"
            link = entry.get("link", "")
            out.append(
                build_posting(
                    source="twitter",
                    company=company,
                    title=title,
                    location="",
                    url_canonical=link,
                    url_apply=link,
                    jd_text=text,
                    posted_date=None,
                    raw_payload={"handle": handle, "tweet_id": tweet_id, "llm": res},
                    first_seen=datetime.now(timezone.utc),
                )
            )
    log.info("twitter watch complete", extra={"count": len(out)})
    return out
