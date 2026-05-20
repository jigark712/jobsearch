"""Classify a Gmail message into a status update.

Returns one of:
  APPLIED_CONFIRMATION | OA_INVITATION | PHONE_SCREEN_INVITATION |
  INTERVIEW_INVITATION | REJECTION | OFFER | UNKNOWN

Heuristics first; LLM fallback for ambiguous cases.
"""
from __future__ import annotations

import re

CATEGORIES = (
    "APPLIED_CONFIRMATION",
    "OA_INVITATION",
    "PHONE_SCREEN_INVITATION",
    "INTERVIEW_INVITATION",
    "REJECTION",
    "OFFER",
    "UNKNOWN",
)

_RULES = [
    ("APPLIED_CONFIRMATION", re.compile(
        r"thank you for applying|application received|we received your application|"
        r"received your submission|your application has been received",
        re.IGNORECASE)),
    ("OA_INVITATION", re.compile(
        r"online assessment|coding assessment|hackerrank invitation|codesignal invitation|"
        r"take[-\s]?home|coding challenge",
        re.IGNORECASE)),
    ("PHONE_SCREEN_INVITATION", re.compile(
        r"phone screen|initial conversation|schedule a (?:call|chat|conversation)|"
        r"calendly|recruiter (?:screen|chat)|intro(?:ductory)? call",
        re.IGNORECASE)),
    ("INTERVIEW_INVITATION", re.compile(
        r"technical interview|onsite|final round|virtual onsite|loop interview|"
        r"superday|panel interview",
        re.IGNORECASE)),
    ("OFFER", re.compile(
        r"pleased to extend|formally offer|offer letter|we'd like to make you an offer",
        re.IGNORECASE)),
    ("REJECTION", re.compile(
        r"unfortunately|moved forward with other candidates|regret to inform|"
        r"not be moving forward|will not be progressing|other applicants",
        re.IGNORECASE)),
]


def classify_rule_based(subject: str, sender: str, snippet: str = "") -> str:
    haystack = f"{subject}\n{snippet}".lower()
    for cat, pattern in _RULES:
        if pattern.search(haystack):
            return cat
    return "UNKNOWN"


def classify_with_llm_fallback(subject: str, sender: str, snippet: str = "") -> str:
    """Call LLM only if rule-based returns UNKNOWN."""
    cat = classify_rule_based(subject, sender, snippet)
    if cat != "UNKNOWN":
        return cat
    # Cheap LLM disambiguation
    from src.llm import call as llm_call
    system = "Classify the email category. Output JSON only."
    user_msg = (
        f"Subject: {subject}\nFrom: {sender}\nSnippet: {snippet[:400]}\n\n"
        "Categories: " + ", ".join(CATEGORIES) + "\n"
        "Return: {\"category\": \"...\"}"
    )
    res = llm_call("email_classifier", system, user_msg)
    cat = res.get("category", "UNKNOWN")
    return cat if cat in CATEGORIES else "UNKNOWN"
