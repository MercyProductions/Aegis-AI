from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import (
    ContextBudgetInfo,
    ContextBudgetItemInfo,
    RoutePreviewRequest,
    RoutePreviewResponse,
    TaskPlanInfo,
)
from aegis_ai.services.route_preview_service import core_route_request_kwargs, route_preview_from_core


def _preview() -> RoutePreviewResponse:
    return RoutePreviewResponse(
        workspace_root="C:/project root",
        mode="develop",
        task_plan=TaskPlanInfo(
            intent="debug",
            objective="Fix failing tests",
            workflow="repair_project",
            complexity="hard",
            route_profile={"id": "best_reasoning"},
            tool_requirements=["code", "tests"],
        ),
        context_budget=ContextBudgetInfo(
            privacy_mode="private-sensitive",
            items=[
                ContextBudgetItemInfo(kind="file", ref="src/app.py", included=True),
                ContextBudgetItemInfo(kind="file", ref="secrets.env", included=False),
                ContextBudgetItemInfo(kind="file", ref="tests/test_app.py", included=True),
            ],
        ),
        registry_message="Website registry ready.",
        recommendations=["Use focused context."],
    )


def test_core_route_request_kwargs_uses_preview_context_without_duplicate_files() -> None:
    request = RoutePreviewRequest(
        message="repair the failing test",
        selected_provider_id="openai",
        selected_provider_model="gpt-5.1",
        context_paths=["README.md", "src/app.py"],
    )

    payload = core_route_request_kwargs(request, _preview())

    assert payload == {
        "task_type": "debug",
        "workflow_type": "repair_project",
        "difficulty": "hard",
        "route_profile": "best_reasoning",
        "required_capabilities": ["code", "tests"],
        "privacy_sensitive": True,
        "provider_id": "openai",
        "model": "gpt-5.1",
        "context_files": ["README.md", "src/app.py", "tests/test_app.py"],
    }


def test_route_preview_from_core_maps_selected_and_fallback_attempts() -> None:
    preview = _preview()
    mapped = route_preview_from_core(
        preview,
        {
            "task_type": "debug",
            "workflow_type": "repair_project",
            "mode": "cloud_allowed",
            "route_profile_id": "best_reasoning",
            "selected": {
                "provider_id": "openai",
                "provider_label": "OpenAI",
                "api": "responses",
                "model": "gpt-5.1",
                "status": "selected",
                "reason": "hard debugging task",
                "privacy_level": "cloud-approved",
                "availability_status": "configured",
                "capabilities": ["code", "reasoning"],
            },
            "fallback_order": [
                {"provider_id": "openai", "provider_label": "OpenAI", "model": "gpt-5.1"},
                {
                    "provider_id": "ollama",
                    "provider_label": "Ollama",
                    "api": "ollama",
                    "model_id": "qwen2.5-coder",
                    "status": "available",
                    "reason": "local fallback",
                },
            ],
            "warnings": ["Cloud approval required before sending context."],
        },
    )

    assert mapped is not preview
    assert mapped.primary_attempt is not None
    assert mapped.primary_attempt.provider_id == "openai"
    assert mapped.primary_attempt.model == "gpt-5.1"
    assert mapped.primary_attempt.metadata["core_runtime_owner"] == "aegis-core"
    assert [attempt.provider_id for attempt in mapped.model_attempts] == ["openai", "ollama"]
    assert mapped.model_attempts[1].status == "fallback"
    assert mapped.registry_message.endswith("Core route mode: cloud_allowed. Profile: best_reasoning.")
    assert mapped.recommendations[0] == "Core model routing selected OpenAI / gpt-5.1."
    assert "Core route warning: Cloud approval required before sending context." in mapped.recommendations


def test_route_preview_from_core_preserves_preview_when_core_has_no_candidate() -> None:
    preview = _preview()

    assert route_preview_from_core(preview, {"selected": {}, "fallback_order": []}) is preview
