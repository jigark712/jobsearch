from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    job_id: str
    source: str
    company: str
    title: str
    location: str = ""
    location_normalized: list[str] = Field(default_factory=list)
    remote_allowed: bool = False
    posted_date: date | None = None
    first_seen_date: datetime
    url_canonical: str
    url_apply: str
    jd_text: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
