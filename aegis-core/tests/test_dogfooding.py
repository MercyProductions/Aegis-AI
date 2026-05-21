from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.dogfooding import dogfooding_dashboard, dogfooding_workflows, production_confidence, record_dogfooding_event
from aegis_core.memory import ProjectMemory
from aegis_core.server import create_app


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert payload["ok"] is True


def test_record_dogfooding_event_persists_local_redacted_signal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = record_dogfooding_event(
        workspace,
        event_type="validation_failed",
        client_id="desktop",
        client_type="desktop",
        workflow_type="validate",
        action="run validation",
        status="failed",
        duration_ms=75_000,
        friction_tags=["unclear_approval", "not-real"],
        notes="Validation failed with api_key=secret-token-value",
        metadata={"api_key": "secret-token-value", "safe": "visible"},
    )

    event = result["event"]
    assert event["friction_tags"] == ["unclear_approval", "validation_pain", "slow_workflow"]
    assert event["metadata"]["api_key"] == "[redacted]"
    assert event["metadata"]["safe"] == "visible"
    assert "secret-token-value" not in event["notes"]
    assert (ProjectMemory(workspace).root / "dogfooding-events.jsonl").is_file()


def test_dogfooding_dashboard_summarizes_friction_confidence_and_persists_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    record_dogfooding_event(workspace, event_type="session_start", status="completed")
    record_dogfooding_event(workspace, event_type="workflow_completed", workflow_type="implement_feature", action="apply", status="completed")
    record_dogfooding_event(workspace, event_type="workflow_abandoned", workflow_type="repair", action="repair", status="abandoned")
    record_dogfooding_event(workspace, event_type="rollback_restored", workflow_type="rollback", action="restore", status="restored")

    dashboard = dogfooding_dashboard(workspace, persist=True)
    tags = {item["tag"] for item in dashboard["friction"]["pain_points"]}

    assert dashboard["event_count"] == 4
    assert "workflow_dead_end" in tags
    assert dashboard["confidence"]["score"] > 0
    assert dashboard["systems_to_simplify"]
    assert dashboard["recommended_polish_priorities"]
    assert (ProjectMemory(workspace).root / "dogfooding-report.json").is_file()
    assert (ProjectMemory(workspace).root / "dogfooding-summary.md").is_file()


def test_production_confidence_counts_real_workflow_outcomes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    record_dogfooding_event(workspace, event_type="workflow_completed", workflow_type="implement_feature", status="completed")
    record_dogfooding_event(workspace, event_type="validation_run", workflow_type="validate", status="passed")
    record_dogfooding_event(workspace, event_type="rollback_restored", workflow_type="rollback", status="restored")

    confidence = production_confidence(workspace)

    assert confidence["metrics"]["successful_workflow_completion"] == 1.0
    assert confidence["metrics"]["validation_reliability"] == 1.0
    assert confidence["metrics"]["rollback_recovery_success"] == 1.0
    assert confidence["status"] in {"improving", "needs_real_usage_data"}


def test_dogfooding_accepts_weekly_workflow_review_friction_tags(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    record_dogfooding_event(
        workspace,
        event_type="workflow_observed",
        workflow_type="weekly_review",
        status="observed",
        friction_tags=[
            "startup_slow",
            "roadmap-unhelpful",
            "diff_unclear",
            "diagnostics_unclear",
            "error_message_unclear",
            "onboarding_friction",
            "maintainability_drag",
        ],
    )

    friction = dogfooding_dashboard(workspace)["friction"]
    tags = {item["tag"] for item in friction["pain_points"]}

    assert {
        "startup_slow",
        "roadmap_unhelpful",
        "diff_unclear",
        "diagnostics_unclear",
        "error_message_unclear",
        "onboarding_friction",
        "maintainability_drag",
    }.issubset(tags)


def test_dogfooding_workflows_cover_daily_product_use() -> None:
    workflows = dogfooding_workflows()
    ids = {item["id"] for item in workflows["workflows"]}

    assert {"feature_development", "bug_fixing", "roadmap_tracking", "deployment_validation", "plugin_development"}.issubset(ids)
    assert workflows["dogfooding_rule"].startswith("Prefer real daily tasks")


def test_dogfooding_endpoints_are_contract_wrapped(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    client = TestClient(create_app())

    event = client.post(
        "/v1/dogfooding/events",
        json={
            "workspace": str(workspace),
            "event_type": "workflow_abandoned",
            "workflow_type": "repair",
            "status": "abandoned",
            "duration_ms": 120000,
            "friction_tags": ["repair_loop"],
        },
    )
    assert event.status_code == 200
    assert_contract(event.json(), "dogfooding.event")

    endpoints = [
        ("/v1/dogfooding", {"workspace": str(workspace)}, "dogfooding.dashboard"),
        ("/v1/dogfooding/friction", {"workspace": str(workspace)}, "dogfooding.friction"),
        ("/v1/dogfooding/confidence", {"workspace": str(workspace)}, "dogfooding.confidence"),
        ("/v1/dogfooding/workflows", {}, "dogfooding.workflows"),
        ("/v1/dogfooding/long-session-plan", {"workspace": str(workspace)}, "dogfooding.long_session_plan"),
    ]
    for path, params, kind in endpoints:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_contract(response.json(), kind)


def test_dogfooding_contracts_are_registered() -> None:
    required = {
        "dogfooding.dashboard",
        "dogfooding.event",
        "dogfooding.friction",
        "dogfooding.confidence",
        "dogfooding.workflows",
        "dogfooding.long_session_plan",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
