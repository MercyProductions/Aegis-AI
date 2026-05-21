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
    workspace = tmp_path / "editing-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Editing Project\n\nOriginal text.\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('old')\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def test_core_proposes_changes_with_patch_preview_and_tracking(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "summary": "Update README",
            "source_client": "test-client",
            "changes": [
                {
                    "id": "readme-change",
                    "action": "update",
                    "path": "README.md",
                    "content": "# Editing Project\n\nUpdated text.\n",
                    "summary": "Replace README body",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract(payload, "changes.proposal")
    data = payload["data"]
    assert data["proposal"]["id"].startswith("proposal-")
    assert data["proposal"]["files"][0]["path"] == "README.md"
    assert data["preview"][0]["change_id"] == "readme-change"
    assert "-Original text." in data["preview"][0]["patch"]
    assert "+Updated text." in data["preview"][0]["patch"]
    assert data["job_id"].startswith("job-")
    assert data["task_id"].startswith("task-")
    assert (workspace / ".aegis" / "editing-proposals.json").is_file()


def test_core_applies_selected_change_with_checkpoint_job_and_activity(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    proposed = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "changes": [
                {"id": "app-change", "action": "update", "path": "src/app.py", "content": "print('new')\n"},
                {"id": "readme-change", "action": "update", "path": "README.md", "content": "# Not applied\n"},
            ],
        },
    ).json()["data"]

    response = client.post(
        "/v1/changes/apply",
        json={
            "workspace": str(workspace),
            "proposal_id": proposed["proposal"]["id"],
            "change_ids": ["app-change"],
            "apply_all": False,
            "source_client": "test-client",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract(payload, "changes.apply")
    data = payload["data"]
    assert data["checkpoint_id"].startswith("checkpoint-")
    assert data["applied"] == ["update: src/app.py"]
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == "print('new')\n"
    assert (workspace / "README.md").read_text(encoding="utf-8").startswith("# Editing Project")
    assert (workspace / ".aegis" / "checkpoints" / data["checkpoint_id"] / "manifest.json").is_file()

    job_response = client.get(f"/v1/jobs/{data['job_id']}", params={"workspace": str(workspace)})
    assert job_response.status_code == 200
    assert_contract(job_response.json(), "core.job")
    assert job_response.json()["data"]["job"]["status"] == "completed"

    activity_response = client.get(
        f"/v1/projects/{data['project_id']}/activity",
        params={"workspace": str(workspace), "limit": 10},
    )
    assert activity_response.status_code == 200
    assert_contract(activity_response.json(), "project.activity")
    events = [item["event"] for item in activity_response.json()["data"]["activity"]]
    assert "changes.applied" in events


def test_core_rejects_unsafe_change_paths(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    outside = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "../outside.txt", "content": "bad"}],
        },
    )
    secret = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": ".env", "content": "SECRET=value"}],
        },
    )

    assert outside.status_code == 400
    assert secret.status_code == 400
    assert not (workspace.parent / "outside.txt").exists()


def test_core_checkpoint_create_list_and_restore(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    created = client.post(
        "/v1/checkpoints/create",
        json={"workspace": str(workspace), "paths": ["README.md"], "summary": "Manual checkpoint"},
    )
    assert created.status_code == 200
    assert_contract(created.json(), "checkpoints.create")
    checkpoint_id = created.json()["data"]["id"]

    listed = client.get("/v1/checkpoints", params={"workspace": str(workspace)})
    assert listed.status_code == 200
    assert_contract(listed.json(), "checkpoints.list")
    assert checkpoint_id in [item["id"] for item in listed.json()["data"]["checkpoints"]]

    (workspace / "README.md").write_text("# Editing Project\n\nChanged after checkpoint.\n", encoding="utf-8")
    restored = client.post(
        "/v1/checkpoints/restore",
        json={"workspace": str(workspace), "checkpoint_id": checkpoint_id},
    )

    assert restored.status_code == 200
    assert_contract(restored.json(), "checkpoints.restore")
    assert restored.json()["data"]["restored"] == ["restore: README.md"]
    assert "Original text." in (workspace / "README.md").read_text(encoding="utf-8")
    assert restored.json()["data"]["pre_restore_checkpoint_id"].startswith("checkpoint-")


def test_core_validation_run_stores_result_and_repair_metadata(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    def return_failure(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="captured stdout", stderr="captured stderr")

    monkeypatch.setattr(validation_module.subprocess, "run", return_failure)
    response = client.post(
        "/v1/validation/run",
        json={
            "workspace": str(workspace),
            "command": [sys.executable, "-m", "pytest"],
            "source_client": "test-client",
            "repair_attempt": {"attempt": 1, "category": "test_failure"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract(payload, "validation.run")
    assert payload["ok"] is False
    data = payload["data"]
    assert data["validation"]["ok"] is False
    assert data["validation"]["stderr"] == "captured stderr"
    assert data["repair_attempt"]["attempt"] == 1
    results = json.loads((workspace / ".aegis" / "validation-results.json").read_text(encoding="utf-8"))
    assert results[0]["id"] == data["id"]
    assert results[0]["job_id"] == data["job_id"]


def test_core_apply_dry_run_does_not_write_or_checkpoint(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/changes/apply",
        json={
            "workspace": str(workspace),
            "dry_run": True,
            "changes": [{"action": "update", "path": "src/app.py", "content": "print('dry')\n"}],
        },
    )

    assert response.status_code == 200
    assert_contract(response.json(), "changes.apply")
    data = response.json()["data"]
    assert data["dry_run"] is True
    assert data["checkpoint_id"] is None
    assert data["applied"] == []
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == "print('old')\n"
    assert not (workspace / ".aegis" / "checkpoints").exists()
