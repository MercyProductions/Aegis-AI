from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core.alpha import (
    alpha_feature_flags,
    alpha_handoff_summary,
    alpha_readiness,
    export_diagnostics_bundle,
    feature_classification,
    feedback_summary,
    record_feedback,
    alpha_simulations,
    update_feature_flags,
)
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.memory import ProjectMemory
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"alpha-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "package.json").write_text(
            json.dumps({"name": "alpha-test", "scripts": {"test": "vitest run", "build": "tsc --noEmit"}}),
            encoding="utf-8",
        )
        (root / "src").mkdir()
        (root / "src" / "app.ts").write_text("export const value = 42;\n", encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_alpha_readiness_collects_checklist_safe_defaults_and_risks(workspace_fixture: Path) -> None:
    readiness = alpha_readiness(workspace_fixture, persist=True)

    assert readiness["alpha_phase"] == "controlled_external_alpha"
    assert readiness["checklist"]
    assert readiness["alpha_safe_defaults"]["approval_required"] is True
    assert readiness["feature_classification"]["disabled_by_default_systems"]
    assert readiness["handoff_summary"]["phase"] == "phase35_alpha_readiness_polish"
    assert readiness["recommended_alpha_scope"]["tester_count"] == "3-8 trusted technical users"
    assert (ProjectMemory(workspace_fixture).root / "alpha-readiness.json").is_file()


def test_feature_flags_keep_alpha_locked_safety_defaults(workspace_fixture: Path) -> None:
    flags = update_feature_flags(
        workspace_fixture,
        overrides={"local_only_mode": False, "high_risk_plugin_enablement": True, "distributed_runtime": True},
        release_channel="experimental",
        reason="test locked flags",
    )

    assert flags["release_channel"] == "experimental"
    assert flags["flags"]["local_only_mode"]["enabled"] is True
    assert flags["flags"]["high_risk_plugin_enablement"]["enabled"] is False
    assert flags["flags"]["distributed_runtime"]["enabled"] is True
    assert alpha_feature_flags(workspace_fixture)["flags"]["approval_required_mode"]["enabled"] is True


def test_diagnostics_export_is_local_and_redacted(workspace_fixture: Path) -> None:
    exported = export_diagnostics_bundle(
        workspace_fixture,
        include_replay=False,
        reason="alpha test with api_key=secret-value",
    )

    assert exported["persisted"] is True
    assert Path(exported["path"]).is_file()
    text = Path(exported["path"]).read_text(encoding="utf-8")
    assert "secret-value" not in text
    assert exported["privacy"]["local_only"] is True
    assert exported["bundle"]["export"]["external_upload"] is False


def test_feedback_capture_redacts_and_summarizes(workspace_fixture: Path) -> None:
    recorded = record_feedback(
        workspace_fixture,
        category="plugin_issue",
        severity="high",
        message="Plugin failed with token=secret-value",
        client_type="vscode",
        metadata={"api_key": "secret-value", "plugin_id": "demo"},
    )
    summary = feedback_summary(workspace_fixture)

    assert recorded["feedback"]["category"] == "plugin_issue"
    assert "secret-value" not in recorded["feedback"]["message"]
    assert recorded["feedback"]["metadata"]["api_key"] == "[redacted]"
    assert summary["category_counts"]["plugin_issue"] == 1


def test_feature_classification_matches_controlled_alpha_scope() -> None:
    classification = feature_classification()

    assert "Core contract envelope" in classification["stable_features"]
    assert "Auralith Engineering Workspace" in classification["beta_features"]
    assert "distributed remote execution" in classification["disabled_by_default_systems"]


def test_alpha_handoff_summary_labels_default_path_and_blockers() -> None:
    summary = alpha_handoff_summary()
    tiers = {tier["id"]: tier for tier in summary["feature_tiers"]}
    path_ids = {step["id"] for step in summary["default_alpha_path"]}

    assert tiers["stable_alpha"]["default_visibility"] == "visible"
    assert tiers["beta"]["default_visibility"] == "visible_with_label"
    assert tiers["experimental"]["default_visibility"] == "opt_in"
    assert tiers["internal_only"]["default_visibility"] == "hidden"
    assert {
        "verify_checksums",
        "provider_setup",
        "local_model_setup",
        "validate_only_first_workflow",
        "diagnostics_export",
        "feedback_capture",
    }.issubset(path_ids)
    assert "external telemetry upload" in summary["hidden_by_default"]
    assert "docs/EXTERNAL_ALPHA_RELEASE_NOTES.md" in summary["tester_handoff"]["required_docs"]
    assert summary["broad_alpha_blockers"]


def test_alpha_simulations_cover_recovery_hardening(workspace_fixture: Path) -> None:
    simulations = alpha_simulations(workspace_fixture)
    scenario_ids = {scenario["id"] for scenario in simulations["scenarios"]}

    assert {
        "interrupted_update",
        "rollback_failure",
        "stale_plugin_state",
        "incompatible_versions",
        "partial_runtime_failure",
    }.issubset(scenario_ids)


def test_alpha_endpoints_are_contract_wrapped(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    endpoints = [
        ("/v1/alpha/readiness", {"workspace": str(workspace_fixture)}, "alpha.readiness"),
        ("/v1/alpha/features", {}, "alpha.feature_classification"),
        ("/v1/alpha/feature-flags", {"workspace": str(workspace_fixture)}, "alpha.feature_flags"),
        ("/v1/alpha/diagnostics", {"workspace": str(workspace_fixture), "include_replay": False}, "alpha.diagnostics"),
        ("/v1/alpha/feedback", {"workspace": str(workspace_fixture)}, "alpha.feedback_summary"),
        ("/v1/alpha/observability", {"workspace": str(workspace_fixture)}, "alpha.observability"),
        ("/v1/alpha/release-channels", {}, "alpha.release_channels"),
        ("/v1/alpha/simulations", {"workspace": str(workspace_fixture)}, "alpha.simulations"),
    ]
    for path, params, kind in endpoints:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_kind(response.json(), kind)

    flags = client.post(
        "/v1/alpha/feature-flags",
        json={"workspace": str(workspace_fixture), "overrides": {"experimental_workflows": True}},
    )
    assert flags.status_code == 200
    assert_kind(flags.json(), "alpha.feature_flags")

    feedback = client.post(
        "/v1/alpha/feedback",
        json={"workspace": str(workspace_fixture), "category": "workflow_pain", "message": "too many clicks"},
    )
    assert feedback.status_code == 200
    assert_kind(feedback.json(), "alpha.feedback")

    diagnostics = client.post(
        "/v1/alpha/diagnostics/export",
        json={"workspace": str(workspace_fixture), "include_replay": False, "reason": "endpoint test"},
    )
    assert diagnostics.status_code == 200
    assert_kind(diagnostics.json(), "alpha.diagnostics_export")


def test_alpha_contracts_are_registered() -> None:
    required = {
        "alpha.readiness",
        "alpha.feature_flags",
        "alpha.feature_classification",
        "alpha.diagnostics",
        "alpha.diagnostics_export",
        "alpha.feedback",
        "alpha.feedback_summary",
        "alpha.observability",
        "alpha.release_channels",
        "alpha.simulations",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
