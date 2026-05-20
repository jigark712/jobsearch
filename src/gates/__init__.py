"""Run universal + per-track gates against a posting.

Returns a dict:
  {"passed": bool, "track": str or "REJECT", "reason": str}

If passed=False, reason is the first failed gate's reason. If track is REJECT
the posting fails before per-track gates.
"""
from __future__ import annotations

from src.classify_track import classify
from src.gates import universal, full_time, summer_internship, fall_internship
from src.schema import JobPosting

TRACK_GATES = {
    "full_time": full_time.run,
    "summer_2026_internship": summer_internship.run,
    "fall_2026_internship": fall_internship.run,
}


def evaluate(posting: JobPosting) -> dict:
    ok, reason = universal.run(posting)
    if not ok:
        return {"passed": False, "track": None, "reason": f"universal:{reason}"}
    track = classify(posting)
    if track == "REJECT":
        return {"passed": False, "track": "REJECT", "reason": "classify:unfit_track"}
    track_run = TRACK_GATES[track]
    ok, reason = track_run(posting)
    if not ok:
        return {"passed": False, "track": track, "reason": f"{track}:{reason}"}
    return {"passed": True, "track": track, "reason": ""}
