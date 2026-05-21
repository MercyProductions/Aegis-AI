from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.validation as validation_module
from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "engineering-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Engineering Project\n\nRoadmap item.\n", encoding="utf-8")
    (workspace / "package.json").write_text('{"scripts":{"test":"node smoke.js","build":"node smoke.js"},"dependencies":{"vite":"^7.0.0"}}\n', encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.ts").write_text("export const value = 1\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def create_execution(client: TestClient, workspace: Path, **extra) -> dict:
    payload = {
        "workspace": str(workspace),
        "goal": "Add a small inspectable engineering change",
        "mode": "safe_assisted",
        "source_client": "test-client",
        "target_files": ["src/app.ts"],
        "context_files": ["README.md"],
        "constraints": ["Keep the change local-first and reversible."],
        "validation_command": [sys.executable, "-m", "pytest"],
    }
    payload.update(extra)
    response = client.post("/v1/engineering/executions", json=payload)
    assert response.status_code == 200
    assert_contract(response.json(), "engineering.execution.created")
    return response.json()["data"]["execution"]


def test_core_creates_formal_engineering_execution_plan(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    execution = create_execution(client, workspace)

    assert execution["id"].startswith("exec-")
    assert execution["workflow_id"].startswith("workflow-")
    assert execution["mode"] == "safe_assisted"
    stage_keys = [stage["key"] for stage in execution["stages"]]
    assert stage_keys == [
        "intake",
        "workspace_analysis",
        "planning",
        "task_decomposition",
        "implementation",
        "validation",
        "repair",
        "review",
        "approval",
        "checkpoint",
        "apply",
        "completion_summary",
    ]
    assert execution["execution_plan"]["target_files"] == ["src/app.ts"]
    assert execution["execution_plan"]["estimated_risk"]["level"] in {"low", "medium", "high"}
    assert execution["safety"]["checkpoint_required_before_apply"] is True
    assert execution["safety"]["binary_file_protection"] is True
    assert execution["task_dependency_graph"]["edges"]
    assert (workspace / ".aegis" / "engineering-executions.json").is_file()
    assert (workspace / ".aegis" / "engineering-memory.json").is_file()
    assert (workspace / ".aegis" / "engineering-journal.json").is_file()


def test_core_rejects_unsafe_engineering_target_paths(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    outside = client.post(
        "/v1/engineering/executions",
        json={"workspace": str(workspace), "goal": "Bad target", "target_files": ["../outside.txt"]},
    )
    secret = client.post(
        "/v1/engineering/executions",
        json={"workspace": str(workspace), "goal": "Bad secret", "target_files": [".env"]},
    )

    assert outside.status_code == 400
    assert secret.status_code == 400
    assert not (workspace.parent / "outside.txt").exists()


def test_engineering_memory_can_refresh_and_persist(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post("/v1/engineering/memory", json={"workspace": str(workspace), "refresh": True})

    assert response.status_code == 200
    assert_contract(response.json(), "engineering.memory")
    data = response.json()["data"]
    assert data["architecture_summary"]["workspace_name"] == workspace.name
    assert data["build_systems"]
    assert data["validation_commands"]
    assert (workspace / ".aegis" / "engineering-memory.md").is_file()


def test_validation_failure_records_repair_loop_and_metrics(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    execution = create_execution(client, workspace, mode="semi_autonomous")

    def return_failure(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="captured stdout", stderr="captured stderr")

    monkeypatch.setattr(validation_module.subprocess, "run", return_failure)
    response = client.post(
        f"/v1/engineering/executions/{execution['id']}/step",
        json={
            "workspace": str(workspace),
            "action": "run_validation",
            "stage_key": "validation",
            "payload": {"command": [sys.executable, "-m", "pytest"]},
        },
    )

    assert response.status_code == 200
    assert_contract(response.json(), "engineering.execution.step")
    updated = response.json()["data"]["execution"]
    assert updated["validation_chain"][0]["ok"] is False
    assert updated["validation_chain"][0]["stderr_excerpt"] == "captured stderr"
    repair_stage = next(stage for stage in updated["stages"] if stage["key"] == "repair")
    assert repair_stage["status"] == "queued"

    repair = client.post(
        f"/v1/engineering/executions/{execution['id']}/step",
        json={
            "workspace": str(workspace),
            "action": "record_repair",
            "payload": {"repair_attempt": {"summary": "Fix failing assertion", "target_files": ["src/app.ts"], "status": "recorded"}},
        },
    )
    assert repair.status_code == 200
    assert repair.json()["data"]["execution"]["repair_history"][0]["attempt"] == 1

    metrics = client.get("/v1/engineering/metrics", params={"workspace": str(workspace)})
    assert metrics.status_code == 200
    assert_contract(metrics.json(), "engineering.metrics")
    assert metrics.json()["data"]["validation"]["runs"] == 1
    assert metrics.json()["data"]["repair"]["attempts"] == 1


def test_timeline_and_roadmap_execution_contracts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    execution = create_execution(client, workspace)

    timeline = client.get(
        f"/v1/engineering/executions/{execution['id']}/timeline",
        params={"workspace": str(workspace)},
    )
    assert timeline.status_code == 200
    assert_contract(timeline.json(), "engineering.execution.timeline")
    assert timeline.json()["data"]["execution_graph"]["nodes"]
    assert timeline.json()["data"]["task_dependency_graph"]["edges"]

    roadmap = client.post(
        "/v1/engineering/roadmap/execute",
        json={
            "workspace": str(workspace),
            "goal": "Complete roadmap phase 1",
            "roadmap_item_id": "roadmap-item-1",
            "roadmap_phase_id": "phase-1",
            "target_files": ["README.md"],
        },
    )
    assert roadmap.status_code == 200
    assert_contract(roadmap.json(), "engineering.execution.created")
    roadmap_execution = roadmap.json()["data"]["execution"]
    assert roadmap_execution["mode"] == "roadmap_execution"
    assert roadmap_execution["roadmap_link"]["roadmap_item_id"] == "roadmap-item-1"

    stored = json.loads((workspace / ".aegis" / "engineering-executions.json").read_text(encoding="utf-8"))
    assert {item["id"] for item in stored} >= {execution["id"], roadmap_execution["id"]}
