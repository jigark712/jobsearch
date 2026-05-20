import hashlib
import re
from datetime import datetime, timezone

from src.schema import JobPosting

_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def clean_text(html_or_text: str) -> str:
    if not html_or_text:
        return ""
    import html as _html
    # Unescape entities first so escaped tags become real tags we can strip.
    text = _html.unescape(html_or_text)
    text = _TAGS.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def normalize_location(raw: str) -> tuple[list[str], bool]:
    """Returns (normalized list, remote_allowed). Coarse — refined later by gates."""
    if not raw:
        return [], False
    low = raw.lower()
    remote = "remote" in low
    if remote and ("us" in low or "united states" in low or "usa" in low or low.strip() in ("remote", "remote-us")):
        return ["Remote-US"], True
    parts = [p.strip() for p in re.split(r"[;|/]| or |,", raw) if p.strip()]
    # crude: collapse "Boston, MA" if split happened on the comma
    out: list[str] = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and len(parts[i + 1]) == 2 and parts[i + 1].isupper():
            out.append(f"{parts[i]}, {parts[i + 1]}")
            i += 2
        else:
            out.append(parts[i])
            i += 1
    return out, remote


def fingerprint(company: str, title: str, location: str) -> str:
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{location.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()


def make_job_id(company: str, title: str, first_seen: datetime) -> str:
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{first_seen.date().isoformat()}"
    return hashlib.sha1(raw.encode()).hexdigest()


def build_posting(
    *,
    source: str,
    company: str,
    title: str,
    location: str,
    url_canonical: str,
    url_apply: str,
    jd_text: str,
    posted_date=None,
    raw_payload: dict | None = None,
    first_seen: datetime | None = None,
) -> JobPosting:
    first_seen = first_seen or datetime.now(timezone.utc)
    loc_norm, remote = normalize_location(location)
    return JobPosting(
        job_id=make_job_id(company, title, first_seen),
        source=source,
        company=company.strip(),
        title=title.strip(),
        location=location,
        location_normalized=loc_norm,
        remote_allowed=remote,
        posted_date=posted_date,
        first_seen_date=first_seen,
        url_canonical=url_canonical,
        url_apply=url_apply,
        jd_text=clean_text(jd_text),
        raw_payload=raw_payload or {},
        fingerprint=fingerprint(company, title, location),
    )
