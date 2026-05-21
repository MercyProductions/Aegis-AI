from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.server import create_app


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "runtime-workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    return workspace


def test_terminal_execution_streams_output_and_cleans_process(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    client = TestClient(create_app())

    launched = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "command": [sys.executable, "-c", "print('hello runtime')"],
            "approval": True,
            "wait": True,
            "timeout_seconds": 10,
            "source_client": "pytest",
        },
    )

    assert launched.status_code == 200
    payload = launched.json()
    assert payload["kind"] == "runtime.job.mutation"
    job = payload["data"]["job"]
    assert job["status"] == "completed"
    assert job["exit_code"] == 0
    assert "hello runtime" in job["stdout_tail"]

    events = client.get(
        "/v1/runtime/streams",
        params={"workspace": str(workspace), "job_id": job["job_id"], "as_sse": False},
    )
    assert events.status_code == 200
    assert any("hello runtime" in event.get("chunk", "") for event in events.json()["data"]["events"])

    processes = client.get("/v1/runtime/processes", params={"workspace": str(workspace)})
    assert processes.status_code == 200
    assert processes.json()["data"]["active_count"] == 0


def test_runtime_blocks_unapproved_and_dangerous_commands(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    client = TestClient(create_app())

    unapproved = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "command": [sys.executable, "-c", "print('needs approval')"],
            "wait": True,
            "source_client": "pytest",
        },
    )
    assert unapproved.status_code == 200
    assert unapproved.json()["ok"] is False
    assert unapproved.json()["data"]["job"]["status"] == "blocked"
    assert "approval" in unapproved.json()["data"]["job"]["safety"]["reason"].lower()

    dangerous = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "command": ["powershell", "-NoProfile", "-Command", "Remove-Item -Recurse ."],
            "approval": True,
            "wait": True,
            "source_client": "pytest",
        },
    )
    assert dangerous.status_code == 200
    assert dangerous.json()["ok"] is False
    assert dangerous.json()["data"]["job"]["status"] == "blocked"
    assert dangerous.json()["data"]["job"]["safety"]["blocked_tokens"]


def test_terminal_timeout_and_retry_capture_result(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    client = TestClient(create_app())

    timed_out = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "command": [sys.executable, "-c", "import time; time.sleep(2)"],
            "approval": True,
            "wait": True,
            "timeout_seconds": 1,
            "source_client": "pytest",
        },
    )
    assert timed_out.status_code == 200
    job = timed_out.json()["data"]["job"]
    assert job["status"] == "timed_out"
    assert job["timed_out"] is True

    retried = client.post(
        f"/v1/runtime/jobs/{job['job_id']}/retry",
        json={"workspace": str(workspace), "approval": True, "wait": True, "timeout_seconds": 3, "reason": "increase timeout"},
    )
    assert retried.status_code == 200
    assert retried.json()["data"]["job"]["restart_of"] == job["job_id"]


def test_process_cancel_marks_job_cancelled(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    client = TestClient(create_app())

    launched = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "command": [sys.executable, "-c", "import time; time.sleep(10)"],
            "approval": True,
            "wait": False,
            "timeout_seconds": 30,
            "source_client": "pytest",
        },
    )
    assert launched.status_code == 200
    job_id = launched.json()["data"]["job"]["job_id"]
    time.sleep(0.3)

    cancelled = client.post(
        f"/v1/runtime/jobs/{job_id}/cancel",
        json={"workspace": str(workspace), "reason": "test cleanup"},
    )
    assert cancelled.status_code == 200

    final_status = ""
    for _ in range(20):
        lookup = client.get(f"/v1/runtime/jobs/{job_id}", params={"workspace": str(workspace)})
        final_status = lookup.json()["data"]["job"]["status"]
        if final_status in {"cancelled", "failed", "timed_out"}:
            break
        time.sleep(0.2)
    assert final_status == "cancelled"


def test_collaboration_session_voice_and_replay_contracts(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    client = TestClient(create_app())

    session = client.post(
        "/v1/runtime/sessions",
        json={
            "workspace": str(workspace),
            "workflow_id": "workflow-test",
            "title": "Review roadmap",
            "owner_client_id": "website",
            "participants": [{"client_id": "website", "name": "Website", "can_approve": True}],
            "spectators": [{"client_id": "desktop", "name": "Desktop"}],
            "approval_delegates": ["website"],
        },
    )
    assert session.status_code == 200
    session_id = session.json()["data"]["session"]["session_id"]

    synced = client.post(
        f"/v1/runtime/sessions/{session_id}/sync",
        json={"workspace": str(workspace), "status": "active", "message": "spectator joined"},
    )
    assert synced.status_code == 200
    assert synced.json()["data"]["session"]["status"] == "active"

    voice = client.post(
        "/v1/runtime/voice/command",
        json={"workspace": str(workspace), "workflow_id": "workflow-test", "client_id": "desktop", "transcript": "pause this workflow"},
    )
    assert voice.status_code == 200
    assert voice.json()["data"]["command"]["intent"] == "pause_workflow"

    replay = client.get("/v1/runtime/replay", params={"workspace": str(workspace), "workflow_id": "workflow-test"})
    assert replay.status_code == 200
    assert any(event["event_type"] == "runtime.voice.command" for event in replay.json()["data"]["terminal_output"])


def test_rejects_cwd_outside_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/runtime/jobs",
        json={
            "workspace": str(workspace),
            "cwd": str(outside),
            "command": [sys.executable, "-c", "print('bad cwd')"],
            "approval": True,
        },
    )

    assert response.status_code == 400
    assert "cwd must stay inside" in response.json()["detail"]
