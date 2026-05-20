"""Thin Anthropic SDK wrapper.

Two model tiers per spec:
- Haiku for cheap per-posting calls (project match, ambiguous classifications)
- Sonnet for digest "why this fits" generation

Both calls are cached on (prompt-name, content-hash) so re-runs are free.
Cache lives at data/llm_cache.jsonl (append-only).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.paths import DATA_DIR

CACHE_PATH = DATA_DIR / "llm_cache.jsonl"

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

_cache: dict[str, dict] | None = None


def _load_cache() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    if CACHE_PATH.exists():
        with CACHE_PATH.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    _cache[entry["key"]] = entry["value"]
                except (json.JSONDecodeError, KeyError):
                    continue
    return _cache


def _cache_key(prompt_name: str, content: str) -> str:
    h = hashlib.sha256(f"{prompt_name}|{content}".encode()).hexdigest()
    return f"{prompt_name}:{h[:16]}"


def _cache_save(key: str, value: dict) -> None:
    cache = _load_cache()
    cache[key] = value
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("a") as f:
        f.write(json.dumps({"key": key, "value": value}) + "\n")


def call(prompt_name: str, system: str, user_msg: str, *, model: str = HAIKU_MODEL,
         max_tokens: int = 600, json_mode: bool = True) -> dict[str, Any]:
    """Return the model's parsed JSON response, cached by (prompt_name, user_msg).

    Falls back to {"error": ...} on failure so callers can degrade gracefully.
    """
    key = _cache_key(prompt_name, user_msg)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Degrade silently — scoring components should treat missing LLM as "neutral".
        return {"_no_api_key": True}

    try:
        from anthropic import Anthropic
    except ImportError:
        return {"_no_sdk": True}

    client = Anthropic()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    text = "\n".join(text_parts).strip()

    if json_mode:
        # The prompts ask for JSON-only output; extract the first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
                _cache_save(key, value)
                return value
            except json.JSONDecodeError:
                pass
        result = {"_raw": text}
        _cache_save(key, result)
        return result

    result = {"text": text}
    _cache_save(key, result)
    return result


def load_prompt(name: str) -> str:
    from src.paths import PROMPTS_DIR
    return (PROMPTS_DIR / f"{name}.txt").read_text()
