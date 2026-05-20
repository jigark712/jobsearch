"""Component 9: Location / remote feasibility. Max 6."""
from __future__ import annotations

import re

from src.config_loader import preferences
from src.schema import JobPosting

_REMOTE_US = re.compile(r"\bremote\s*-?\s*(?:us|usa|united\s*states)\b|\bus[-\s]*remote\b", re.IGNORECASE)


def score(posting: JobPosting, track: str = "full_time") -> tuple[int, str]:
    loc = posting.location or ""
    loc_low = loc.lower()
    prefs = preferences()
    if track == "fall_2026_internship":
        return 6, "boston-resident (gate already enforced)"
    allowed = [a.lower() for a in prefs["locations"]["allowed_full_time"]]
    if _REMOTE_US.search(loc_low) or "remote" in loc_low and "us" in loc_low:
        return 6, "remote-US"
    for a in allowed:
        if a in loc_low:
            return 6, f"allowed: {a}"
    # Reachable via relocation (any US city)
    if re.search(r",\s*(?:al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|"
                 r"ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|"
                 r"tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b", loc, re.IGNORECASE):
        return 4, "US city outside top list (relocation)"
    return 2, "location unclear"
