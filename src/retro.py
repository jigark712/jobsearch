"""Weekly retrospective generator.

Reads:
- Job Tracker sheet → applications + funnel state
- data/logs/*.jsonl → system health stats
- data/digests/*.md → digest counts (loose proxy)
- data/jobs/raw-*.jsonl → ingestion stats

Writes retros/YYYY-MM-DD.md and emails it.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from src.config_loader import preferences
from src.paths import LOGS_DIR, RETROS_DIR, ensure_data_dirs


def _iter_log_files(days: int) -> Iterable[Path]:
    if not LOGS_DIR.exists():
        return
    cutoff = date.today() - timedelta(days=days)
    for p in sorted(LOGS_DIR.glob("*.jsonl"), reverse=True):
        try:
            d = datetime.strptime(p.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < cutoff:
            break
        yield p


def _read_log_lines(days: int = 7) -> list[dict]:
    out = []
    for p in _iter_log_files(days):
        with p.open() as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _read_tracker_records() -> list[dict]:
    from src.tracker.sheet_client import _open_sheet
    ws = _open_sheet()
    if ws is None:
        return []
    return ws.get_all_records()


def _within(days: int, date_str: str) -> bool:
    if not date_str:
        return False
    try:
        d = datetime.fromisoformat(date_str).date()
    except ValueError:
        return False
    return (date.today() - d).days <= days


def build_retro(weeks: int = 1) -> tuple[str, dict]:
    days = weeks * 7
    records = _read_tracker_records()
    logs = _read_log_lines(days)

    # Applications this week
    apps_this_week = [r for r in records if _within(days, r.get("applied_date") or "")]
    by_score_band = Counter()
    for r in apps_this_week:
        try:
            s = int(r.get("score") or 0)
        except (TypeError, ValueError):
            s = 0
        if s >= 80:
            by_score_band["80+"] += 1
        elif s >= 70:
            by_score_band["70-79"] += 1
        elif s >= 65:
            by_score_band["65-69"] += 1
        else:
            by_score_band["<65"] += 1

    # Responses (any of OA/phone/interview/onsite within window)
    responded = [r for r in apps_this_week if any(
        r.get(c) for c in ("recruiter_screen_date", "OA_date", "phone_screen_date",
                           "tech_interview_dates", "onsite_date", "offer_date"))]
    callback_pct = (len(responded) / len(apps_this_week) * 100) if apps_this_week else 0.0

    # Funnel snapshot (all-time, not week-bounded)
    funnel = {
        "active": sum(1 for r in records if r.get("applied_date") and not r.get("outcome")),
        "oa": sum(1 for r in records if r.get("OA_date")),
        "phone_screens": sum(1 for r in records if r.get("phone_screen_date")),
        "onsites": sum(1 for r in records if r.get("onsite_date")),
        "offers": sum(1 for r in records if r.get("offer_date")),
        "rejections": sum(1 for r in records if (r.get("outcome") or "").lower() == "rejected"),
    }

    # System health from logs
    ingested = sum(L.get("count", 0) for L in logs
                   if L.get("logger") == "scripts.tier1" and L.get("msg") == "written")
    digests = sum(1 for L in logs if L.get("logger") == "scripts.digest" and L.get("msg") == "digest written")

    # Auto-recommendations
    recs: list[str] = []
    if apps_this_week and len(responded) / len(apps_this_week) < 0.05:
        recs.append("Callback rate below 5% — review whether scoring threshold is too low or resume needs tuning for this cluster.")
    low_apps = sum(1 for r in apps_this_week if 0 < int(r.get("score") or 0) < 65)
    if low_apps >= 5:
        recs.append(f"{low_apps} applications below score 65 this week. Consider raising the floor.")
    if funnel["active"] > 20 and funnel["phone_screens"] == 0:
        recs.append("Many active applications, no phone screens. Check that Gmail label filter is catching responses.")

    # Action items
    actions: list[str] = []
    for r in records:
        applied = r.get("applied_date") or ""
        if not applied:
            continue
        try:
            d = datetime.fromisoformat(applied).date()
        except ValueError:
            continue
        if (date.today() - d).days >= 14 and not r.get("outcome") and not r.get("phone_screen_date"):
            actions.append(f"Follow up on {r.get('company','?')} — {r.get('title','?')} (applied {applied})")
        if len(actions) >= 10:
            break

    today = date.today().isoformat()
    md_parts = [
        f"# Weekly Retro — Week of {today}",
        "",
        "## Applications",
        f"- Sent this week: {len(apps_this_week)}",
    ]
    by_cluster = Counter(r.get("cluster") or "—" for r in apps_this_week)
    if by_cluster:
        md_parts.append(f"- By cluster: " + ", ".join(f"{k}={v}" for k, v in by_cluster.most_common()))
    md_parts.append(f"- By score band: " + ", ".join(f"{k}={v}" for k, v in by_score_band.most_common()))
    md_parts.append("")
    md_parts.append("## Responses")
    md_parts.append(f"- Detected: {len(responded)}")
    md_parts.append(f"- Callback rate: {callback_pct:.1f}%")
    md_parts.append("")
    md_parts.append("## Funnel snapshot (all-time)")
    for k, v in funnel.items():
        md_parts.append(f"- {k}: {v}")
    md_parts.append("")
    md_parts.append("## System health")
    md_parts.append(f"- Ingestion writes (logged): {ingested}")
    md_parts.append(f"- Digests generated this week: {digests}")
    md_parts.append("")
    if recs:
        md_parts.append("## Recommendations")
        for r in recs:
            md_parts.append(f"- {r}")
        md_parts.append("")
    if actions:
        md_parts.append("## Action items")
        for a in actions:
            md_parts.append(f"- {a}")
        md_parts.append("")

    summary = {
        "applications_this_week": len(apps_this_week),
        "responses": len(responded),
        "callback_pct": callback_pct,
        "funnel": funnel,
        "digests_this_week": digests,
    }
    return "\n".join(md_parts), summary


def write_retro() -> Path:
    ensure_data_dirs()
    md, _ = build_retro()
    path = RETROS_DIR / f"{date.today().isoformat()}.md"
    path.write_text(md)
    return path
