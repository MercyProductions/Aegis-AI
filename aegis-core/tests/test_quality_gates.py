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
    workspace = tmp_path / "quality-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Quality Project\n\nOriginal text.\n", encoding="utf-8")
    (workspace / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (workspace / "package.json").write_text('{"scripts":{"test":"node smoke.js","build":"node smoke.js"}}\n', encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def test_quality_gate_evaluation_passes_low_risk_change(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/quality-gates/evaluate",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "app.py", "content": "print('new')\n"}],
            "checkpoint_id": "checkpoint-test",
            "approval": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract(payload, "quality.gates.evaluate")
    data = payload["data"]
    assert data["apply_allowed"] is True
    assert data["status"] in {"passed", "warning"}
    assert data["scorecard"]["confidence_score"] > 0
    assert (workspace / ".aegis" / "quality-gate-runs.json").is_file()


def test_quality_gate_blocks_unsafe_path_and_apply_preserves_file(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/changes/apply",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "app.py", "content": "def broken(:\n"}],
            "quality_gate_required": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract(payload, "changes.apply")
    data = payload["data"]
    assert data["ok"] is False
    assert data["blocked"] is True
    assert data["applied"] == []
    assert data["checkpoint_id"].startswith("checkpoint-")
    assert any(item["gate_id"] == "syntax_check" for item in data["quality_gate"]["blockers"])
    assert (workspace / "app.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_quality_gate_rejects_too_many_files(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    for index in range(4):
        (workspace / f"file_{index}.txt").write_text("old\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/quality-gates/evaluate",
        json={
            "workspace": str(workspace),
            "changes": [
                {"action": "update", "path": f"file_{index}.txt", "content": "new\n"}
                for index in range(4)
            ],
            "checkpoint_id": "checkpoint-test",
            "max_files_changed": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["apply_allowed"] is False
    assert any(item["gate_id"] == "file_change_risk" for item in data["blockers"])


def test_quality_gate_validation_failure_can_block_when_required(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    def return_failure(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="tests failed")

    monkeypatch.setattr(validation_module.subprocess, "run", return_failure)
    validation = client.post(
        "/v1/validation/run",
        json={"workspace": str(workspace), "command": [sys.executable, "-m", "pytest"]},
    )
    assert validation.status_code == 200

    response = client.post(
        "/v1/quality-gates/evaluate",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "README.md", "content": "# Quality Project\n"}],
            "checkpoint_id": "checkpoint-test",
            "validation_required": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["apply_allowed"] is False
    assert any(item["gate_id"] == "test_check" for item in data["blockers"])


def test_benchmark_and_evaluation_report_are_recorded(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    evaluation = client.post(
        "/v1/quality-gates/evaluate",
        json={
            "workspace": str(workspace),
            "workflow_id": "workflow-test",
            "changes": [{"action": "update", "path": "README.md", "content": "# Updated\n"}],
            "checkpoint_id": "checkpoint-test",
        },
    ).json()["data"]

    benchmark = client.post(
        "/v1/benchmarks/run",
        json={"workspace": str(workspace), "suite_ids": ["coding_task_quality"], "workflow_id": "workflow-test"},
    )
    assert benchmark.status_code == 200
    assert_contract(benchmark.json(), "quality.benchmark.run")
    assert benchmark.json()["data"]["results"][0]["suite_id"] == "coding_task_quality"

    report = client.post(
        "/v1/evaluation-reports",
        json={
            "workspace": str(workspace),
            "workflow_id": "workflow-test",
            "quality_run_id": evaluation["id"],
            "title": "Quality report",
            "metadata": {"reason": "test report"},
        },
    )
    assert report.status_code == 200
    assert_contract(report.json(), "quality.evaluation_report")
    assert report.json()["data"]["quality_run_id"] == evaluation["id"]
    assert "Rollback" in report.json()["data"]["markdown"]

    dashboard = client.get("/v1/quality-gates", params={"workspace": str(workspace)})
    assert dashboard.status_code == 200
    assert_contract(dashboard.json(), "quality.gates")
    assert dashboard.json()["data"]["statistics"]["run_count"] >= 1

    workflow_quality = client.get("/v1/workflows/workflow-test/quality", params={"workspace": str(workspace)})
    assert workflow_quality.status_code == 200
    assert_contract(workflow_quality.json(), "workflow.quality")
    assert workflow_quality.json()["data"]["latest"]["workflow_id"] == "workflow-test"

    stored_reports = json.loads((workspace / ".aegis" / "evaluation-reports.json").read_text(encoding="utf-8"))
    assert stored_reports[0]["id"] == report.json()["data"]["id"]
