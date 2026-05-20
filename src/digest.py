"""Daily digest generator.

Reads: today's deduped JSONL → runs gates → scores → groups by track + bucket
→ writes markdown to digests/YYYY-MM-DD.md → optionally emails.

The digest format follows spec section 6.1.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from src.config_loader import companies, preferences
from src.dedupe import dedupe
from src.gates import evaluate
from src.paths import DIGESTS_DIR, ensure_data_dirs
from src.schema import JobPosting
from src.scoring.aggregate import score_posting
from src.storage import iter_postings


def _hours_ago(posting: JobPosting) -> str:
    seen = posting.posted_date or posting.first_seen_date
    if isinstance(seen, datetime):
        secs = (datetime.now(timezone.utc) - seen).total_seconds()
    else:
        secs = (datetime.now(timezone.utc) - datetime(seen.year, seen.month, seen.day, tzinfo=timezone.utc)).total_seconds()
    if secs < 3600:
        return f"{int(secs / 60)}m ago"
    if secs < 86400:
        return f"{int(secs / 3600)}h ago"
    return f"{int(secs / 86400)}d ago"


def _format_full_time_entry(p: JobPosting, scored: dict, detailed: bool) -> str:
    s = scored
    head = f"- **{p.company} — {p.title}** · {p.location} · Posted {_hours_ago(p)} · **Score {s['score_total']}**"
    if not detailed:
        return head + f"  \n  [Apply →]({p.url_apply})"
    components = s["score_components"]
    skill_reason = components["skill_match"]["reason"]
    project_reason = components["project_match"]["reason"]
    spons_reason = components["sponsorship"]["reason"]
    flags = ", ".join(s["risk_flags"]) if s["risk_flags"] else "—"
    lines = [
        head,
        f"  - Skills: {skill_reason}",
        f"  - Projects: {project_reason}",
        f"  - Sponsorship: {spons_reason}",
        f"  - Source: {p.source}",
        f"  - Risk flags: {flags}",
        f"  - [Apply →]({p.url_apply})",
    ]
    return "\n".join(lines)


def _format_summer_entry(p: JobPosting, scored: dict) -> str:
    lines = [
        f"- **{p.company} — {p.title}** · {p.location} · Posted {_hours_ago(p)} · **Score {scored['score_total']}**",
        f"  - Apply method: {p.source}",
        f"  - [Apply →]({p.url_apply})",
    ]
    return "\n".join(lines)


def _format_fall_entry(p: JobPosting, scored: dict) -> str:
    return _format_full_time_entry(p, scored, detailed=False)


def _linkedin_manual_block() -> str:
    cfg = companies()["linkedin"]
    if not cfg.get("manual_check_prompts_daily"):
        return ""
    searches = cfg.get("manual_check_searches") or []
    if not searches:
        return ""
    lines = ["## 📋 LINKEDIN — Manual Check Today",
             "> Spend ~10 minutes on these LinkedIn searches with the \"Posted in last 24 hours\" filter:"]
    for s in searches:
        url = s.get("url") or ""
        label = s.get("label", "search")
        if url:
            lines.append(f"> - [{label}]({url})")
        else:
            lines.append(f"> - {label} (URL not yet configured)")
    lines.append("> Reply to this digest with any URLs worth tracking.")
    return "\n".join(lines)


def _capacity_warning(apply_today: int, apply_week: int, prefs: dict) -> str:
    cap = prefs["application_capacity"]["hard_cap_per_day_total"]
    total = apply_today + apply_week
    if total <= cap:
        return ""
    return (f"> ⚠️ {total} jobs surfaced today, exceeds your daily cap of {cap}. "
            f"The bottom {total - cap} are deferred (summer-intern postings are never deferred per policy).\n")


def build_digest(day: str | None = None) -> tuple[str, dict]:
    """Build the markdown digest for `day` (default: today UTC).

    Returns (markdown_string, summary_stats_dict).
    """
    ensure_data_dirs()
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = list(iter_postings(day))
    deduped, _ = dedupe(raw)

    by_bucket: dict[str, list[tuple[JobPosting, str, dict]]] = defaultdict(list)
    gate_drops: Counter = Counter()
    track_counts: Counter = Counter()
    score_drops = 0

    for p in deduped:
        gate_result = evaluate(p)
        if not gate_result["passed"]:
            gate_drops[gate_result["reason"].split(":", 1)[0]] += 1
            continue
        track = gate_result["track"]
        track_counts[track] += 1
        scored = score_posting(p, track)
        bucket = scored["decision_bucket"]
        if bucket == "reject":
            score_drops += 1
            continue
        by_bucket[bucket].append((p, track, scored))

    for bucket in by_bucket:
        by_bucket[bucket].sort(key=lambda t: t[2]["score_total"], reverse=True)

    prefs = preferences()
    ft_today = [x for x in by_bucket.get("apply_today", []) if x[1] == "full_time"]
    ft_week = [x for x in by_bucket.get("apply_week", []) if x[1] == "full_time"]
    ft_ref = [x for x in by_bucket.get("referral_first", []) if x[1] == "full_time"]
    summer = [x for x in by_bucket.get("apply_today", []) + by_bucket.get("apply_week", []) if x[1] == "summer_2026_internship"]
    fall = [x for x in by_bucket.get("apply_today", []) + by_bucket.get("apply_week", []) if x[1] == "fall_2026_internship"]
    watchlist = by_bucket.get("watchlist", [])

    parts = [f"# Job Digest — {day}\n"]

    warn = _capacity_warning(len(ft_today), len(ft_week), prefs)
    if warn:
        parts.append(warn)

    parts.append(f"## 🟢 FULL-TIME — Apply Today ({len(ft_today)})\n")
    if ft_today:
        for p, _, s in ft_today:
            parts.append(_format_full_time_entry(p, s, detailed=True))
    else:
        parts.append("_None today._\n")

    parts.append(f"\n## 🟢 FULL-TIME — Apply This Week ({len(ft_week)})\n")
    if ft_week:
        for p, _, s in ft_week:
            parts.append(_format_full_time_entry(p, s, detailed=False))
    else:
        parts.append("_None this week._\n")

    parts.append(f"\n## 🟡 FULL-TIME — Referral First ({len(ft_ref)})\n")
    if ft_ref:
        for p, _, s in ft_ref:
            parts.append(_format_full_time_entry(p, s, detailed=False))
    else:
        parts.append("_None._\n")

    parts.append(f"\n## 🔥 SUMMER 2026 INTERNSHIP — Apply NOW ({len(summer)})\n")
    parts.append("> {} late-cycle summer postings scored ≥75. Only realistic at small startups / YC companies. Apply within 24 hours or it's gone. If 0 today, that's normal.\n".format(len(summer)))
    if summer:
        for p, _, s in summer:
            parts.append(_format_summer_entry(p, s))
    else:
        parts.append("_No summer postings today._\n")

    parts.append(f"\n## 🔵 FALL 2026 INTERNSHIP (Boston part-time, CPT) ({len(fall)})\n")
    parts.append("_Reminder: requires CPT filing 2-3 weeks before start date._\n")
    if fall:
        for p, _, s in fall:
            parts.append(_format_fall_entry(p, s))
    else:
        parts.append("_None today._\n")

    li_block = _linkedin_manual_block()
    if li_block:
        parts.append("\n" + li_block + "\n")

    parts.append(f"\n## Watchlist ({len(watchlist)}, collapsed)\n")
    parts.append("<details><summary>Show watchlist</summary>\n")
    for p, _, s in watchlist[:50]:
        parts.append(_format_full_time_entry(p, s, detailed=False))
    parts.append("\n</details>\n")

    # Summary
    summary_stats = {
        "total_ingested": len(raw),
        "deduped": len(deduped),
        "passed_gates": sum(track_counts.values()),
        "by_track": dict(track_counts),
        "rejected_at_gates": sum(gate_drops.values()),
        "gate_drops": dict(gate_drops.most_common()),
        "rejected_at_score": score_drops,
        "surfaced": sum(len(by_bucket[b]) for b in ("apply_today", "apply_week", "referral_first", "watchlist")),
    }

    parts.append("\n## Summary\n")
    parts.append(f"- Ingested today: {summary_stats['total_ingested']}")
    parts.append(f"- After dedup: {summary_stats['deduped']}")
    parts.append(f"- Passed gates: {summary_stats['passed_gates']}")
    parts.append(f"- By track: " + ", ".join(f"{k}={v}" for k, v in track_counts.items()))
    parts.append(f"- Dropped at gates: {summary_stats['rejected_at_gates']} (top: " + ", ".join(f"{k}={v}" for k, v in list(gate_drops.most_common(5))) + ")")
    parts.append(f"- Dropped at score: {summary_stats['rejected_at_score']}")
    parts.append(f"- Surfaced: {summary_stats['surfaced']}")
    parts.append("")

    return "\n".join(parts), summary_stats


def write_digest(day: str | None = None) -> Path:
    md, _stats = build_digest(day)
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = DIGESTS_DIR / f"{day}.md"
    path.write_text(md)
    return path
