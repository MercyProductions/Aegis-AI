from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core import autopilot
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"autopilot-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "README.md").write_text("# Autopilot Fixture\n\nRoadmap-ready workspace.\n", encoding="utf-8")
        (root / "package.json").write_text(
            json.dumps({"scripts": {"test": "python -c \"print('ok')\"", "build": "python -c \"print('build')\""}}),
            encoding="utf-8",
        )
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_autopilot_modes_define_supervised_safety_contract() -> None:
    modes = autopilot.autopilot_modes()
    mode_ids = {item["id"] for item in modes["modes"]}

    assert {
        "suggest_only",
        "approval_each_step",
        "semi_autonomous",
        "roadmap_autopilot",
        "repair_autopilot",
        "validation_autopilot",
        "experimental_full_autopilot",
    }.issubset(mode_ids)
    semi = next(item for item in modes["modes"] if item["id"] == "semi_autonomous")
    assert semi["autonomy_limits"]["allows_apply_without_approval"] is False
    assert any("checkpoint" in item.lower() for item in semi["checkpoint_rules"])
    assert any("never applies file changes" in item for item in modes["safety_invariants"])
    specialization_ids = {item["id"] for item in modes["specializations"]}
    assert {
        "feature_autopilot",
        "repair_autopilot",
        "refactor_autopilot",
        "deployment_autopilot",
        "workspace_intelligence_autopilot",
    }.issubset(specialization_ids)
    feature = next(item for item in modes["specializations"] if item["id"] == "feature_autopilot")
    assert feature["orchestration_strategy"]["name"] == "roadmap_milestone_execution"
    assert "feature_quality" in feature["benchmark_suites"]


def test_feature_autopilot_infers_specialized_roadmap_strategy(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Execute the next roadmap phase with validation gates",
        mode="roadmap_autopilot",
        workflow_type="continue_roadmap",
        roadmap=[{"id": "phase-1", "title": "Improve validation messaging"}],
        target_files=["README.md"],
        client_id="pytest",
    )
    run = result["run"]

    assert run["specialization"] == "feature_autopilot"
    assert run["execution_strategy"]["name"] == "roadmap_milestone_execution"
    assert "roadmap_acceptance" in run["validation_intelligence"]["paths"]
    assert "feature_quality" in run["specialization_benchmarks"]
    assert result["supervision"]["specialization"] == "feature_autopilot"


def test_refactor_autopilot_uses_conservative_dependency_profile(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Safely refactor the app module while preserving references",
        mode="semi_autonomous",
        workflow_type="generate_feature",
        specialization="refactor",
        target_files=["src/app.py"],
        client_id="pytest",
    )
    run = result["run"]

    assert run["specialization"] == "refactor_autopilot"
    assert run["model_routing"]["profile"] == "best_reasoning"
    assert run["validation_strategy"]["name"] == "refactor_regression_ladder"
    assert "symbol_reference_check" in run["validation_intelligence"]["paths"]


def test_deployment_autopilot_rejects_scope_beyond_specialized_limit(workspace_fixture: Path) -> None:
    target_files = [f"release/file-{index}.yml" for index in range(11)]

    with pytest.raises(ValueError, match="deployment_autopilot effective limit"):
        autopilot.start_autopilot(
            workspace_fixture,
            "Prepare a release across too many pipeline files",
            mode="semi_autonomous",
            workflow_type="build_project",
            specialization="deployment_autopilot",
            target_files=target_files,
            client_id="pytest",
        )


def test_suggest_only_run_waits_for_approval_before_mutating_stage(workspace_fixture: Path) -> None:
    client = TestClient(create_app())

    started = client.post(
        "/v1/autopilot/start",
        json={
            "workspace": str(workspace_fixture),
            "objective": "Inspect project and propose a harmless improvement",
            "mode": "suggest_only",
            "workflow_type": "scan_workspace",
            "client_id": "pytest",
        },
    )
    assert started.status_code == 200
    assert_kind(started.json(), "autopilot.run")
    run = started.json()["data"]["run"]

    advanced = client.post(
        f"/v1/autopilot/runs/{run['id']}/action",
        json={"workspace": str(workspace_fixture), "action": "advance"},
    )
    assert advanced.status_code == 200
    assert_kind(advanced.json(), "autopilot.action")
    updated = advanced.json()["data"]["run"]
    assert updated["status"] == "waiting_approval"
    assert updated["pending_approvals"]
    assert updated["pending_approvals"][0]["stage_key"] == "implementation"

    supervision = client.get("/v1/autopilot/supervision", params={"workspace": str(workspace_fixture)})
    assert supervision.status_code == 200
    assert_kind(supervision.json(), "autopilot.supervision")
    assert supervision.json()["data"]["pending_approvals"][0]["autopilot_id"] == run["id"]

    replay = client.get(f"/v1/autopilot/runs/{run['id']}/replay", params={"workspace": str(workspace_fixture)})
    assert replay.status_code == 200
    assert_kind(replay.json(), "autopilot.replay")
    assert replay.json()["data"]["events"]
    assert (workspace_fixture / ".aegis" / "autopilot-runs.json").is_file()
    assert (workspace_fixture / ".aegis" / "autopilot-events.json").is_file()


def test_validation_autopilot_records_dry_run_validation(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Run validation without modifying files",
        mode="validation_autopilot",
        workflow_type="validate_project",
        validation_commands=[{"command": [sys.executable, "-m", "pytest"]}],
        client_id="pytest",
    )
    run_id = result["run"]["id"]

    updated = autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "run_validation",
        approval=True,
        payload={"command": [sys.executable, "-m", "pytest"], "dry_run": True, "run": True},
    )["run"]

    assert updated["validation_chain"]
    assert updated["validation_status"] == "passed"
    assert updated["validation_chain"][0]["dry_run"] is True
    observability = autopilot.autopilot_observability(workspace_fixture)
    assert observability["validation_success_rate"] == 1.0


def test_autopilot_trust_scorecard_and_simulation_preview(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Plan a dependency-sensitive repair",
        mode="semi_autonomous",
        workflow_type="generate_feature",
        target_files=["requirements.txt", "src/app.py"],
        client_id="pytest",
    )
    run = result["run"]

    assert run["trust_scorecard"]["confidence_score"] > 0
    assert run["execution_risk_level"] in {"medium", "high"}
    assert run["predictions"]["likely_validation_targets"]
    assert run["checkpoint_intelligence"]["risk_triggered_checkpoint_recommended"] is True
    assert run["bounded_autonomy"]["usage"]["files_modified_or_scoped"] == 2
    assert any(item["kind"] == "risk_initialized" for item in run["decision_log"])

    simulated = autopilot.autopilot_action(
        workspace_fixture,
        run["id"],
        "simulate",
        payload={"action": "advance"},
    )["run"]

    assert simulated["last_simulation"]["dry_run"] is True
    assert simulated["last_simulation"]["would_modify_files"] is False
    assert "checkpoint_required_before_apply" in simulated["last_simulation"]["blocked"]
    assert simulated["trust_scorecard"]["rollback_readiness"] < 90


def test_autopilot_bounded_payload_rejection(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Validate bounded context controls",
        mode="semi_autonomous",
        workflow_type="generate_feature",
        target_files=["src/app.py"],
        client_id="pytest",
    )

    with pytest.raises(ValueError, match="bounded context limit"):
        autopilot.autopilot_action(
            workspace_fixture,
            result["run"]["id"],
            "advance",
            payload={"context": "x" * 41000},
        )


def test_repair_autopilot_escalates_after_retry_limit(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Repair a failing validation",
        mode="repair_autopilot",
        workflow_type="repair_project",
        target_files=["src/app.py"],
        client_id="pytest",
    )
    run_id = result["run"]["id"]
    autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "record_validation",
        payload={"result": {"passed": False, "summary": "Simulated failure"}},
    )

    for attempt in range(1, 4):
        repaired = autopilot.autopilot_action(
            workspace_fixture,
            run_id,
            "repair",
            approval=True,
            payload={"repair_attempt": {"summary": f"Repair attempt {attempt}", "success": False}},
        )["run"]
        assert repaired["repair_attempts"] == attempt

    escalated = autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "repair",
        approval=True,
        payload={"repair_attempt": {"summary": "Repair attempt 4", "success": False}},
    )["run"]
    assert escalated["status"] == "waiting_approval"
    assert escalated["pending_approvals"][0]["stage_key"] == "repair"
    assert escalated["trust_scorecard"]["repair_confidence"] < 70


def test_repair_autopilot_detects_repetitive_failed_repairs(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Repair the same failing validation repeatedly",
        mode="repair_autopilot",
        workflow_type="repair_project",
        target_files=["src/app.py"],
        client_id="pytest",
    )
    run_id = result["run"]["id"]
    autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "record_validation",
        payload={"result": {"passed": False, "summary": "ImportError: missing widget"}},
    )

    for _ in range(3):
        updated = autopilot.autopilot_action(
            workspace_fixture,
            run_id,
            "repair",
            approval=True,
            payload={"repair_attempt": {"summary": "Try same import fix", "success": False}},
        )["run"]

    assert updated["status"] == "waiting_approval"
    assert updated["blocked_actions"][-1]["action"] == "repair"
    assert "Repeated repair pattern" in updated["pending_approvals"][0]["reason"]
    assert updated["repair_history"][-1]["repeat_count"] >= 3


def test_specialized_autopilot_memory_records_repair_patterns(workspace_fixture: Path) -> None:
    result = autopilot.start_autopilot(
        workspace_fixture,
        "Repair a build failure and remember the repair pattern",
        mode="repair_autopilot",
        workflow_type="repair_project",
        target_files=["src/app.py"],
        client_id="pytest",
    )
    run_id = result["run"]["id"]
    autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "record_validation",
        payload={"result": {"passed": False, "summary": "NameError: missing value"}},
    )
    autopilot.autopilot_action(
        workspace_fixture,
        run_id,
        "repair",
        approval=True,
        payload={"repair_attempt": {"summary": "Add missing value definition", "success": True}},
    )

    memory = autopilot.autopilot_memory(workspace_fixture)["memory"]
    repair_memory = memory["per_specialization"]["repair_autopilot"]
    assert repair_memory["repair_patterns"]
    assert repair_memory["validation_history"]
    assert repair_memory["recurring_validation_failures"]


def test_roadmap_autopilot_tracks_progress_and_lifecycle_actions(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    started = client.post(
        "/v1/autopilot/start",
        json={
            "workspace": str(workspace_fixture),
            "objective": "Execute the first roadmap phase",
            "mode": "roadmap_autopilot",
            "workflow_type": "continue_roadmap",
            "roadmap": [
                {"id": "phase-1", "title": "Improve validation messaging"},
                {"id": "phase-2", "title": "Polish rollback docs"},
            ],
            "target_files": ["README.md"],
            "client_id": "pytest",
        },
    )
    assert started.status_code == 200
    run = started.json()["data"]["run"]
    assert run["roadmap_progress"]["total"] == 2

    paused = client.post(
        f"/v1/autopilot/runs/{run['id']}/action",
        json={"workspace": str(workspace_fixture), "action": "pause"},
    )
    assert paused.status_code == 200
    assert paused.json()["data"]["run"]["status"] == "paused"

    resumed = client.post(
        f"/v1/autopilot/runs/{run['id']}/action",
        json={"workspace": str(workspace_fixture), "action": "resume"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["data"]["run"]["status"] == "running"

    cancelled = client.post(
        f"/v1/autopilot/runs/{run['id']}/action",
        json={"workspace": str(workspace_fixture), "action": "cancel"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["run"]["status"] == "cancelled"


def test_autopilot_contracts_and_client_hooks_are_registered(workspace_fixture: Path) -> None:
    required = {
        "autopilot.modes",
        "autopilot.run",
        "autopilot.runs",
        "autopilot.dashboard",
        "autopilot.action",
        "autopilot.supervision",
        "autopilot.observability",
        "autopilot.memory",
        "autopilot.replay",
        "autopilot.client_hooks",
    }
    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)

    client = TestClient(create_app())
    for path, params, kind in [
        ("/v1/autopilot/modes", {}, "autopilot.modes"),
        ("/v1/autopilot/runs", {"workspace": str(workspace_fixture)}, "autopilot.runs"),
        ("/v1/autopilot/observability", {"workspace": str(workspace_fixture)}, "autopilot.observability"),
        ("/v1/autopilot/memory", {"workspace": str(workspace_fixture)}, "autopilot.memory"),
        ("/v1/autopilot/client-hooks", {}, "autopilot.client_hooks"),
    ]:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_kind(response.json(), kind)

    hooks = client.get("/v1/autopilot/client-hooks")
    actions = {item["id"] for item in hooks.json()["data"]["actions"]}
    assert {"pause", "resume", "approve", "rollback", "run_validation"}.issubset(actions)
