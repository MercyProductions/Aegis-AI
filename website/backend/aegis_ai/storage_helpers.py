from __future__ import annotations

import hashlib
import json
from typing import Any


def parse_json_list(raw: Any) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def merge_json_list(raw: Any, additions: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*parse_json_list(raw), *additions]:
        cleaned = str(item).strip()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    return merged


def task_title_from_message(message: str, mode: str) -> str:
    cleaned = " ".join((message or "").split())
    if cleaned:
        return cleaned[:80]
    return f"{mode.title()} task"


def parse_json_payload(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def tokenize(value: str) -> set[str]:
    cleaned = [
        "".join(character for character in chunk.lower() if character.isalnum())
        for chunk in value.split()
    ]
    return {token for token in cleaned if len(token) >= 3}


def memory_match_score(query: str, *parts: str) -> float:
    query_tokens = tokenize(query)
    memory_tokens = tokenize("\n".join(parts))
    if not query_tokens or not memory_tokens:
        return 0.0

    overlap = len(query_tokens & memory_tokens)
    if overlap == 0:
        return 0.0

    return overlap / max(len(query_tokens), 1)


def fingerprint(*parts: str) -> str:
    normalized = "\n".join(part.strip().lower() for part in parts if part.strip())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
