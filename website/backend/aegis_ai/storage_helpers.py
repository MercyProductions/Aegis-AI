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


def int_value(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_positive_int(value: Any) -> int | None:
    number = optional_int(value)
    if number is None:
        return None
    return number if number >= 0 else None


def optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    return None


def float_value(value: Any, default: float | None = 0.0) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def average(values: list[Any]) -> float | None:
    cleaned = [float_value(value, None) for value in values]
    cleaned = [value for value in cleaned if value is not None]
    if not cleaned:
        return None
    return round(sum(cleaned) / len(cleaned), 4)


def rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def reliability_score(
    success_rate: float,
    fallback_rate: float,
    context_utilization: float | None,
    positive_feedback_rate: float = 0.0,
    negative_feedback_rate: float = 0.0,
) -> float:
    pressure_penalty = max(0.0, ((context_utilization or 0.0) - 0.72) * 0.40)
    feedback_adjustment = (positive_feedback_rate * 0.08) - (negative_feedback_rate * 0.16)
    score = success_rate - (fallback_rate * 0.20) - pressure_penalty + feedback_adjustment
    return round(max(0.0, min(1.0, score)) * 100.0, 2)


def token_metadata_int(metadata: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        value = optional_positive_int(metadata.get(key))
        if value is not None:
            return value
    return None


def token_relative_error(estimated: int | None, reported: int | None) -> float | None:
    if estimated is None or reported is None:
        return None
    return round(abs(estimated - reported) / max(reported, 1), 4)


def context_budget_utilization(entry: Any) -> float | None:
    max_tokens = entry.max_context_tokens or entry.payload.max_context_tokens
    if max_tokens <= 0:
        return None
    requested = (entry.estimated_context_tokens or entry.payload.estimated_context_tokens) + (
        entry.reserve_response_tokens or entry.payload.reserve_response_tokens
    )
    return min(1.0, max(0.0, requested / max_tokens))


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
