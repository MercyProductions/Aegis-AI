from __future__ import annotations

import json
from typing import Any

from .schemas import (
    AgentRequest,
    AgentResponse,
    ChatStreamContractResponse,
    ChatStreamEventInfo,
)


def sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def structured_stream_intro(request: AgentRequest) -> str:
    mode = request.mode or "auto"
    parts = [
        f"I'm handling this as a structured {mode} task.",
        "I'll keep provider JSON internal and only stream safe progress here.",
    ]
    if request.apply_changes:
        parts.append("Auto Apply is enabled, so eligible low-risk file changes can be written after the draft is assembled.")
    if request.run_validation:
        parts.append("Validation is enabled, so I'll run the selected check after applicable changes are applied.")
    return " ".join(parts) + "\n\n"


def structured_stream_summary(response: AgentResponse) -> str:
    details: list[str] = []
    if response.changes:
        details.append(f"prepared {len(response.changes)} file change(s)")
    if response.applied:
        details.append(f"applied {len(response.applied)} file change(s)")
    if response.validation is not None:
        status = "passed" if response.validation.exit_code == 0 else "needs attention"
        details.append(f"validation {status}")
    if response.warnings:
        details.append(f"{len(response.warnings)} warning(s)")
    if not details:
        details.append("prepared a structured response")
    return "Aegis " + ", ".join(details) + ". Finalizing the response now.\n\n"


def structured_stream_reconciliation(response: AgentResponse, *, preview_was_streamed: bool) -> str:
    if not preview_was_streamed:
        return ""

    warnings_text = "\n".join(response.warnings).lower()
    fallback_markers = (
        "deterministic fallback",
        "deterministic starter generator",
        "model returned no file changes",
        "model returned no usable answer",
        "direct chat fallback",
    )
    if any(marker in warnings_text for marker in fallback_markers):
        return (
            "The live preview came from the model draft, but Aegis replaced it with a safer final response "
            "because that draft did not produce usable workspace changes."
        )

    attempts = response.model_attempts
    first_success_index = next(
        (index for index, attempt in enumerate(attempts) if attempt.status == "succeeded"),
        None,
    )
    if first_success_index is not None and first_success_index > 0:
        prior_attempts = attempts[:first_success_index]
        if any(attempt.status in {"failed", "skipped"} for attempt in prior_attempts):
            return (
                "The live preview came from an earlier provider attempt. Aegis used the later successful "
                "provider response as the final structured answer."
            )

    return ""


def response_with_reconciliation(response: AgentResponse, notice: str) -> AgentResponse:
    if not notice:
        return response

    warnings = list(response.warnings)
    if notice not in warnings:
        warnings.append(notice)

    reply = response.reply.strip()
    if notice not in reply:
        reply = f"{reply}\n\nNote: {notice}" if reply else f"Note: {notice}"

    return response.model_copy(update={"reply": reply, "warnings": warnings})


def preview_delta_payload(event: Any, *, stream_mode: str) -> dict[str, Any] | None:
    if isinstance(event, str):
        event = {"delta": event}
    if not isinstance(event, dict):
        return None

    delta = str(event.get("delta") or "")
    preview_action = str(event.get("preview_action") or "append").strip() or "append"
    if preview_action == "append" and not delta:
        return None

    return {
        "type": "delta",
        "delta": delta,
        "stream_mode": stream_mode,
        "source": "structured_reply_preview",
        "preview_action": preview_action,
        "preview_attempt": event.get("preview_attempt"),
        "provider_id": event.get("provider_id") or "",
        "provider_label": event.get("provider_label") or "",
        "provider_api": event.get("provider_api") or "",
        "model": event.get("model") or "",
        "message": event.get("message") or "",
    }


def preview_delta_counts_as_streamed(payload: dict[str, Any]) -> bool:
    return payload.get("preview_action") == "append" and bool(payload.get("delta"))


def chat_stream_contract_response() -> ChatStreamContractResponse:
    return ChatStreamContractResponse(
        events=[
            ChatStreamEventInfo(
                event="meta",
                payload='{"type":"meta","schema_version":"aegis.chat.stream.v1","stream_mode":"chat-delta-final|structured-delta-final"}',
                description="Sent first with schema, stream mode, workspace, and routing hints.",
            ),
            ChatStreamEventInfo(
                event="status",
                payload='{"type":"status","stage":"planning","message":"..."}',
                description="Progress lifecycle updates while Aegis prepares context, routes, reconciles previews, and finalizes output.",
            ),
            ChatStreamEventInfo(
                event="delta",
                payload='{"type":"delta","delta":"partial text","source":"structured_reply_preview","preview_action":"append|reset","preview_attempt":1}',
                description="Provider text deltas for direct chat turns, or safe progress/reply-preview/reconciliation deltas for structured workspace turns. Raw provider JSON is never streamed.",
            ),
            ChatStreamEventInfo(
                event="final",
                payload='{"type":"final","task_id":"...","response":{...}}',
                description="The complete AgentResponse payload, matching /api/chat.",
            ),
            ChatStreamEventInfo(
                event="error",
                payload='{"type":"error","message":"safe error","detail":"developer detail"}',
                description="Recoverable stream error envelope sent before done.",
            ),
            ChatStreamEventInfo(
                event="done",
                payload='{"type":"done","task_id":"..."}',
                description="Terminal event; clients should close readers after receiving it.",
            ),
        ],
        recommendations=[
            "Use fetch with a ReadableStream for POST requests; EventSource cannot POST AgentRequest bodies.",
            "Treat final.response as the source of truth; clients may render delta text optimistically before final arrives.",
            "Keep /api/chat as the compatibility path for clients that do not need streamed status updates.",
        ],
    )
