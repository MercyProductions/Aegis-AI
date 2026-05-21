from __future__ import annotations

from typing import Any

from ..schemas import ModelAttemptInfo, RoutePreviewRequest, RoutePreviewResponse


def core_route_request_kwargs(request: RoutePreviewRequest, preview: RoutePreviewResponse) -> dict[str, Any]:
    return {
        "task_type": preview.task_plan.intent or "chat",
        "workflow_type": preview.task_plan.workflow or None,
        "difficulty": preview.task_plan.complexity or None,
        "route_profile": _route_profile_id(preview),
        "required_capabilities": preview.task_plan.tool_requirements,
        "privacy_sensitive": _route_preview_requires_private_context(preview),
        "provider_id": request.selected_provider_id or None,
        "model": request.selected_provider_model or None,
        "context_files": _route_preview_context_files(request, preview),
    }


def route_preview_from_core(
    preview: RoutePreviewResponse,
    core_route: dict[str, Any],
) -> RoutePreviewResponse:
    role = str(
        core_route.get("workflow_type")
        or core_route.get("task_type")
        or preview.task_plan.workflow
        or preview.task_plan.intent
        or "chat"
    )
    attempts: list[ModelAttemptInfo] = []
    selected_attempt = _model_attempt_from_core_candidate(
        core_route.get("selected"),
        attempt=1,
        role=role,
        status="planned",
    )
    if selected_attempt is not None:
        attempts.append(selected_attempt)

    selected_key = (
        selected_attempt.provider_id if selected_attempt is not None else "",
        selected_attempt.model if selected_attempt is not None else "",
    )
    for candidate in core_route.get("fallback_order") if isinstance(core_route.get("fallback_order"), list) else []:
        if not isinstance(candidate, dict):
            continue
        candidate_key = (
            str(candidate.get("provider_id") or "").strip(),
            str(candidate.get("model") or candidate.get("model_id") or "").strip(),
        )
        if candidate_key == selected_key:
            continue
        fallback_attempt = _model_attempt_from_core_candidate(
            candidate,
            attempt=len(attempts) + 1,
            role=role,
            status="fallback",
        )
        if fallback_attempt is not None:
            attempts.append(fallback_attempt)

    if not attempts:
        return preview

    recommendations = list(preview.recommendations)
    primary = attempts[0]
    selected_label = " / ".join(filter(None, [primary.provider_label or primary.provider_id, primary.model]))
    if selected_label:
        recommendations.insert(0, f"Core model routing selected {selected_label}.")
    for warning in core_route.get("warnings") if isinstance(core_route.get("warnings"), list) else []:
        text = str(warning).strip()
        if text:
            recommendations.append(f"Core route warning: {text}")

    registry_message = preview.registry_message
    mode = str(core_route.get("mode") or "").strip()
    profile_id = str(core_route.get("route_profile_id") or "").strip()
    core_message = " ".join(
        filter(None, [f"Core route mode: {mode}." if mode else "", f"Profile: {profile_id}." if profile_id else ""])
    )
    if core_message:
        registry_message = " ".join(filter(None, [registry_message, core_message]))

    return preview.model_copy(
        update={
            "model_attempts": attempts,
            "primary_attempt": attempts[0],
            "registry_message": registry_message,
            "recommendations": recommendations,
        }
    )


def _route_preview_context_files(request: RoutePreviewRequest, preview: RoutePreviewResponse) -> list[str]:
    refs: list[str] = []
    for path in request.context_paths:
        text = str(path).strip()
        if text and text not in refs:
            refs.append(text)

    if preview.context_budget is not None:
        for item in preview.context_budget.items:
            if item.included:
                text = str(item.ref).strip()
                if text and text not in refs:
                    refs.append(text)
    return refs


def _route_profile_id(preview: RoutePreviewResponse) -> str | None:
    profile = preview.task_plan.route_profile
    if not isinstance(profile, dict):
        return None
    value = profile.get("id") or profile.get("profile_id") or profile.get("name")
    text = str(value or "").strip()
    return text or None


def _route_preview_requires_private_context(preview: RoutePreviewResponse) -> bool:
    privacy_mode = ""
    if preview.context_budget is not None:
        privacy_mode = preview.context_budget.privacy_mode.lower()
    return "private" in privacy_mode or "sensitive" in privacy_mode


def _model_attempt_from_core_candidate(
    candidate: Any,
    *,
    attempt: int,
    role: str,
    status: str,
) -> ModelAttemptInfo | None:
    if not isinstance(candidate, dict):
        return None
    provider_id = str(candidate.get("provider_id") or "").strip()
    model = str(candidate.get("model") or candidate.get("model_id") or "").strip()
    if not provider_id and not model:
        return None
    return ModelAttemptInfo(
        attempt=attempt,
        role=role,
        provider_id=provider_id,
        provider_label=str(candidate.get("provider_label") or provider_id),
        provider_api=str(candidate.get("api") or ""),
        model=model,
        privacy_mode=str(candidate.get("privacy_level") or "local-first"),
        status=status,  # type: ignore[arg-type]
        reason=str(candidate.get("reason") or candidate.get("status") or ""),
        metadata={
            "core_runtime_owner": "aegis-core",
            "core_route_status": str(candidate.get("status") or ""),
            "availability_status": str(candidate.get("availability_status") or ""),
            "capabilities": candidate.get("capabilities") if isinstance(candidate.get("capabilities"), list) else [],
        },
    )
