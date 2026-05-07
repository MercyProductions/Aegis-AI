from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .schemas import (
    FallbackInspectorResponse,
    FeedbackTelemetryResponse,
    RouteQualityResponse,
    TelemetrySnapshot,
)
from .storage_helpers import parse_json_payload


def bounded_snapshot_limits(
    route_quality_limit: int,
    fallback_limit: int,
    feedback_limit: int,
) -> tuple[int, int, int]:
    return (
        max(1, min(500, route_quality_limit)),
        max(1, min(100, fallback_limit)),
        max(1, min(500, feedback_limit)),
    )


def telemetry_snapshot_key(route_quality_limit: int, fallback_limit: int, feedback_limit: int) -> str:
    return f"route:{route_quality_limit}|fallback:{fallback_limit}|feedback:{feedback_limit}"


def telemetry_snapshot_from_row(
    row: sqlite3.Row,
    project_root: Path,
    stale_after_seconds: int,
) -> TelemetrySnapshot:
    updated_at = str(row["updated_at"])
    age_seconds = snapshot_age_seconds(updated_at)
    stale_after = max(60, stale_after_seconds or int(row["stale_after_seconds"] or 900))
    return TelemetrySnapshot(
        id=str(row["id"]),
        workspace_root=str(project_root.resolve()),
        snapshot_key=str(row["snapshot_key"]),
        created_at=str(row["created_at"]),
        updated_at=updated_at,
        route_quality_limit=int(row["route_quality_limit"]),
        fallback_limit=int(row["fallback_limit"]),
        feedback_limit=int(row["feedback_limit"]),
        stale_after_seconds=stale_after,
        age_seconds=age_seconds,
        is_stale=age_seconds > stale_after,
        route_quality=RouteQualityResponse.model_validate(parse_json_payload(str(row["route_quality_json"]))),
        fallback_inspector=FallbackInspectorResponse.model_validate(
            parse_json_payload(str(row["fallback_inspector_json"]))
        ),
        feedback=FeedbackTelemetryResponse.model_validate(parse_json_payload(str(row["feedback_json"]))),
    )


def snapshot_age_seconds(updated_at: str) -> int:
    parsed = parse_snapshot_timestamp(updated_at)
    if parsed is None:
        return 0
    return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))


def snapshot_updated_before(updated_at: str, cutoff: datetime) -> bool:
    parsed = parse_snapshot_timestamp(updated_at)
    if parsed is None:
        return False
    return parsed.astimezone(timezone.utc) < cutoff.astimezone(timezone.utc)


def parse_snapshot_timestamp(updated_at: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def model_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=True, sort_keys=True)
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
