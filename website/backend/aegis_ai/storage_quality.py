from __future__ import annotations

from typing import Any

from .schemas import FeedbackRecordRequest, ModelAttemptTelemetryEntry, RouteQualityTokenCalibrationTrendBucket
from .storage_helpers import int_value, optional_bool, rate


def feedback_metadata(request: FeedbackRecordRequest) -> dict[str, Any]:
    metadata = dict(request.metadata or {})
    metadata["content_length"] = len(request.content or "")
    metadata["has_content"] = bool((request.content or "").strip())
    return {
        str(key)[:80]: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }


def attempt_status(entry: ModelAttemptTelemetryEntry) -> str:
    return (entry.attempt.status or "planned").strip().lower()


def is_fallback_attempt(entry: ModelAttemptTelemetryEntry) -> bool:
    attempt = entry.attempt
    return attempt.attempt > 1 or (attempt.status or "").lower() == "fallback" or (attempt.role or "").lower() == "fallback"


def token_estimator_label(metadata: dict[str, Any]) -> str:
    if not isinstance(metadata, dict):
        return ""
    family = str(metadata.get("token_estimator_family") or "").strip()
    source = str(metadata.get("token_estimate_source") or "").strip()
    if family and source:
        return f"{family}:{source}"
    return family or source


def structured_preview_metrics(metadata: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    keys = {
        "structured_preview_delta_count",
        "structured_preview_char_count",
        "structured_preview_reset_count",
        "structured_preview_emitted",
        "structured_preview_retired",
        "structured_preview_final_winner",
        "structured_preview_retired_reason",
    }
    if not any(key in metadata for key in keys):
        return None
    delta_count = int_value(metadata.get("structured_preview_delta_count"))
    char_count = int_value(metadata.get("structured_preview_char_count"))
    reset_count = int_value(metadata.get("structured_preview_reset_count"))
    emitted = optional_bool(metadata.get("structured_preview_emitted"))
    retired = optional_bool(metadata.get("structured_preview_retired"))
    final_winner = optional_bool(metadata.get("structured_preview_final_winner"))
    return {
        "delta_count": max(0, delta_count),
        "char_count": max(0, char_count),
        "reset_count": max(0, reset_count),
        "emitted": bool(emitted) or delta_count > 0 or char_count > 0,
        "retired": bool(retired) or reset_count > 0,
        "final_winner": bool(final_winner),
        "retired_reason": str(metadata.get("structured_preview_retired_reason") or "").strip(),
    }


def structured_preview_status(
    *,
    previewed_attempts: int,
    final_winning_attempts: int,
    retired_attempts: int,
    reset_count: int,
) -> str:
    if previewed_attempts <= 0:
        return "insufficient"
    retired_rate = rate(retired_attempts, previewed_attempts)
    final_winner_rate = rate(final_winning_attempts, previewed_attempts)
    if previewed_attempts >= 2 and (retired_rate >= 0.50 or reset_count >= 2):
        return "unstable"
    if previewed_attempts < 2:
        return "insufficient"
    if retired_rate > 0.0 or final_winner_rate < 0.67:
        return "watch"
    return "stable"


def structured_preview_recommendation(
    *,
    status: str,
    provider_label: str,
    previewed_attempts: int,
    final_winning_attempts: int,
    retired_attempts: int,
    reset_count: int,
) -> str:
    label = provider_label or "provider"
    if status == "unstable":
        return (
            f"{label} retired {retired_attempts}/{previewed_attempts} structured preview attempt(s) "
            f"with {reset_count} reset(s); route policy should prefer a more stable structured-output provider."
        )
    if status == "watch":
        return (
            f"{label} previews are mixed: {final_winning_attempts}/{previewed_attempts} became final output. "
            "Keep collecting samples before promoting this provider for structured workspace streams."
        )
    if status == "stable":
        return f"{label} structured previews are stable enough for normal streamed coding/build routes."
    return f"Collect more structured preview samples for {label} before making route-policy decisions."


def token_calibration_status(
    *,
    calibrated_attempts: int,
    average_input_error: float | None,
    average_output_error: float | None,
    worst_input_error: float | None,
    worst_output_error: float | None,
) -> str:
    if calibrated_attempts <= 0:
        return "insufficient"
    average_error = max(average_input_error or 0.0, average_output_error or 0.0)
    worst_error = max(worst_input_error or 0.0, worst_output_error or 0.0)
    if average_error <= 0.12 and worst_error <= 0.25:
        return "stable"
    if average_error <= 0.25 and worst_error <= 0.45:
        return "watch"
    return "drift"


def token_calibration_recommendation(
    *,
    status: str,
    provider_label: str,
    calibrated_attempts: int,
    average_input_error: float | None,
    average_output_error: float | None,
    reported_sources: list[str],
) -> str:
    label = provider_label or "provider"
    if status == "insufficient":
        return f"Collect provider-reported token usage for {label} before tuning route context budgets from estimator data."
    source = ", ".join(reported_sources[:2]) if reported_sources else "provider usage metadata"
    input_text = f"{average_input_error:.0%}" if average_input_error is not None else "n/a"
    output_text = f"{average_output_error:.0%}" if average_output_error is not None else "n/a"
    if status == "stable":
        return f"{label} calibration is stable across {calibrated_attempts} attempt(s) via {source}; avg error in/out {input_text}/{output_text}."
    if status == "watch":
        return f"{label} token estimates have moderate drift; continue sampling {source} before changing profile overhead."
    return f"{label} token estimates are drifting from reported usage; adjust tokenizer profile or context overhead before relying on tight budgets."


def token_calibration_trend_recommendation(bucket: RouteQualityTokenCalibrationTrendBucket) -> str:
    label = bucket.provider_label or bucket.provider_id or "provider"
    if bucket.calibrated_attempts <= 0:
        return f"No provider-reported usage landed for {label} during {bucket.period_start}; keep collecting samples."
    if bucket.trend_direction == "improving":
        return f"{label} token estimates improved during {bucket.period_start}; keep the current estimator profile under observation."
    if bucket.trend_direction == "worsening":
        return f"{label} token-estimate error worsened during {bucket.period_start}; review recent prompt/context mix before expanding budgets."
    if bucket.calibration_status == "drift":
        return f"{label} is still drifting during {bucket.period_start}; tune estimator overhead before using tight context limits."
    if bucket.calibration_status == "watch":
        return f"{label} is in watch state for {bucket.period_start}; collect more samples before automated routing changes use token cost signals."
    if bucket.trend_direction == "flat":
        return f"{label} calibration stayed flat during {bucket.period_start}; continue sampling before changing the profile."
    return f"{label} established a calibration baseline during {bucket.period_start}."
