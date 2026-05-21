from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.validation as validation_module
from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workflow-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Workflow Project\n\nTODO: build the thing.\n", encoding="utf-8")
    (workspace / "package.json").write_text('{"scripts":{"test":"node smoke.js","build":"node smoke.js"},"dependencies":{"vite":"^7.0.0"}}\n', encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.ts").write_text("export const value = 1\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def create_workflow(client: TestClient, workspace: Path, workflow_type: str = "generate_feature") -> dict:
    response = client.post(
        "/v1/workflows",
        json={
            "workspace": str(workspace),
            "workflow_type": workflow_type,
            "objective": "Add a small inspected feature",
            "source_client": "test-client",
            "context_files": ["README.md", ".env"],
        },
    )
    assert response.status_code == 200
    assert_contract(response.json(), "workflow.created")
    return response.json()["data"]["workflow"]


def test_core_creates_structured_workflow_graph(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    workflow = create_workflow(client, workspace, "generate_feature")

    assert workflow["id"].startswith("workflow-")
    assert workflow["workflow_type"] == "generate_feature"
    assert workflow["status"] == "queued"
    assert workflow["context_files"] == ["README.md"]
    assert workflow["blocked_context"][0]["path"] == ".env"
    assert len(workflow["tasks"]) >= 5
    assert any(task["parent_id"] for task in workflow["tasks"])
    assert any(edge["from"] and edge["to"] for edge in workflow["dependencies"])
    assert {"planner", "coder", "validator", "repair_agent", "summarizer"}.issubset(
        {task["agent_role"] for task in workflow["tasks"]}
    )
    assert {"planner_agent", "coder_agent", "validator_agent", "repair_agent", "summarizer_agent"}.issubset(
        {task["agent_id"] for task in workflow["tasks"]}
    )
    assert workflow["agent_runtime_version"]
    assert workflow["agent_coordination"]["handoff_chain"]
    assert all(task["memory_scope"]["scope"] for task in workflow["tasks"])
    assert (workspace / ".aegis" / "workflow-runtime.json").is_file()
    assert (workspace / ".aegis" / "workflow-events.json").is_file()


def test_workflow_step_progress_pause_resume_cancel_and_retry(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    workflow = create_workflow(client, workspace, "scan_workspace")
    workflow_id = workflow["id"]

    first = client.post(
        f"/v1/workflows/{workflow_id}/step",
        json={"workspace": str(workspace), "action": "advance", "summary": "Run scan"},
    )
    assert first.status_code == 200
    assert_contract(first.json(), "workflow.step")
    data = first.json()["data"]["workflow"]
    assert data["progress"] >= 50
    summarize_task = next(task for task in data["tasks"] if task["key"] == "summarize")
    assert summarize_task["status"] == "queued"

    pause = client.post(f"/v1/workflows/{workflow_id}/pause", json={"workspace": str(workspace)})
    assert pause.status_code == 200
    assert pause.json()["data"]["workflow"]["status"] == "paused"
    resume = client.post(f"/v1/workflows/{workflow_id}/resume", json={"workspace": str(workspace)})
    assert resume.status_code == 200
    assert resume.json()["data"]["workflow"]["status"] in {"queued", "waiting_input"}

    fail = client.post(
        f"/v1/workflows/{workflow_id}/step",
        json={"workspace": str(workspace), "action": "fail_task", "task_id": summarize_task["id"], "summary": "Needs retry"},
    )
    assert fail.status_code == 200
    failed_task = next(task for task in fail.json()["data"]["workflow"]["tasks"] if task["id"] == summarize_task["id"])
    assert failed_task["messages"][-1]["type"] == "failure_escalation"
    assert fail.json()["data"]["workflow"]["failure_escalations"]
    retry = client.post(
        f"/v1/workflows/{workflow_id}/retry",
        json={"workspace": str(workspace), "task_id": summarize_task["id"]},
    )
    assert retry.status_code == 200
    retried_task = next(task for task in retry.json()["data"]["workflow"]["tasks"] if task["id"] == summarize_task["id"])
    assert retried_task["status"] == "queued"
    assert retried_task["retry_count"] == 1

    cancel = client.post(f"/v1/workflows/{workflow_id}/cancel", json={"workspace": str(workspace)})
    assert cancel.status_code == 200
    assert cancel.json()["data"]["workflow"]["status"] == "cancelled"


def test_validation_workflow_uses_approval_gate_and_records_stats(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    workflow = create_workflow(client, workspace, "validate_project")
    workflow_id = workflow["id"]

    inspect_response = client.post(f"/v1/workflows/{workflow_id}/step", json={"workspace": str(workspace)})
    assert inspect_response.status_code == 200
    validate_task = next(task for task in inspect_response.json()["data"]["workflow"]["tasks"] if task["key"] == "validate")
    blocked = client.post(
        f"/v1/workflows/{workflow_id}/step",
        json={"workspace": str(workspace), "task_id": validate_task["id"]},
    )
    assert blocked.status_code == 200
    assert next(task for task in blocked.json()["data"]["workflow"]["tasks"] if task["id"] == validate_task["id"])["status"] == "waiting_input"

    def return_success(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(validation_module.subprocess, "run", return_success)
    validated = client.post(
        f"/v1/workflows/{workflow_id}/step",
        json={
            "workspace": str(workspace),
            "task_id": validate_task["id"],
            "approval": True,
            "payload": {"command": [sys.executable, "-m", "pytest"]},
        },
    )
    assert validated.status_code == 200
    validation_result = next(task for task in validated.json()["data"]["workflow"]["tasks"] if task["id"] == validate_task["id"])["result"]
    assert validation_result["ok"] is True

    stats = client.get("/v1/workflows/stats", params={"workspace": str(workspace)})
    assert stats.status_code == 200
    assert_contract(stats.json(), "workflow.statistics")
    assert stats.json()["data"]["validation"]["runs"] == 1
    assert stats.json()["data"]["validation"]["success_rate"] == 1.0
    assert stats.json()["data"]["agent_observability"]["agents"]


def test_agent_coordination_dashboard_and_delegation(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    workflow = create_workflow(client, workspace, "generate_feature")
    workflow_id = workflow["id"]
    propose_task = next(task for task in workflow["tasks"] if task["key"] == "propose_changes")

    dashboard = client.get(f"/v1/workflows/{workflow_id}/agents", params={"workspace": str(workspace)})

    assert dashboard.status_code == 200
    assert_contract(dashboard.json(), "agent.coordination")
    data = dashboard.json()["data"]
    assert "coder_agent" in data["task_ownership"]
    assert data["handoff_chain"]
    assert data["dependency_graph"]["validation_batches"]
    assert data["context_snapshots"]
    assert data["supervision"]["runaway_execution_prevention"]["recursive_spawning"] is False

    blocked = client.post(
        f"/v1/workflows/{workflow_id}/agents/delegate",
        json={
            "workspace": str(workspace),
            "task_id": propose_task["id"],
            "agent_id": "architecture_agent",
            "reason": "Ask architecture agent to assess risk first.",
        },
    )

    assert blocked.status_code == 200
    assert_contract(blocked.json(), "agent.delegation")
    blocked_task = next(task for task in blocked.json()["data"]["workflow"]["tasks"] if task["id"] == propose_task["id"])
    assert blocked_task["status"] == "waiting_input"
    assert blocked_task["pending_delegation"]["to_agent_id"] == "architecture_agent"

    delegated = client.post(
        f"/v1/workflows/{workflow_id}/agents/delegate",
        json={
            "workspace": str(workspace),
            "task_id": propose_task["id"],
            "agent_id": "architecture_agent",
            "approval": True,
            "reason": "Approved architecture review handoff.",
        },
    )

    assert delegated.status_code == 200
    task = next(task for task in delegated.json()["data"]["workflow"]["tasks"] if task["id"] == propose_task["id"])
    assert task["agent_id"] == "architecture_agent"
    assert task["agent_role"] == "architecture"
    assert task["messages"]


def test_workspace_intelligence_and_client_sync_dashboard(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    workflow = create_workflow(client, workspace, "scan_workspace")

    intelligence = client.post("/v1/workspaces/intelligence", json={"workspace": str(workspace), "refresh": True})
    assert intelligence.status_code == 200
    assert_contract(intelligence.json(), "workspace.intelligence")
    data = intelligence.json()["data"]
    assert "Vite" in data["frameworks"]
    assert data["file_index"]["file_count"] >= 3
    assert data["dependency_graph"]
    assert data["health"]["score"] >= 0

    sync = client.post(
        "/v1/clients/sync",
        json={
            "workspace": str(workspace),
            "client_id": "desktop-test",
            "client_type": "desktop",
            "name": "Desktop Test",
            "version": "0.1",
            "capabilities": ["workflow_runtime"],
            "active_workflow_id": workflow["id"],
        },
    )
    assert sync.status_code == 200
    assert_contract(sync.json(), "client.sync")

    dashboard = client.get("/v1/client-sync", params={"workspace": str(workspace)})
    assert dashboard.status_code == 200
    assert_contract(dashboard.json(), "client.sync.dashboard")
    assert dashboard.json()["data"]["active_clients"][0]["client_id"] == "desktop-test"
    assert dashboard.json()["data"]["active_workflows"][0]["id"] == workflow["id"]


def test_workflow_event_stream_returns_sse_events(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    workflow = create_workflow(client, workspace, "scan_workspace")

    response = client.get(
        f"/v1/workflows/{workflow['id']}/events",
        params={"workspace": str(workspace), "limit": 5},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: workflow_event" in response.text
    assert "workflow.created" in response.text


def test_agent_runtime_catalog_contract(tmp_path: Path) -> None:
    client = TestClient(create_app())

    response = client.get("/v1/workflows/agent-runtime")

    assert response.status_code == 200
    assert_contract(response.json(), "agent.runtime")
    role_ids = {role["id"] for role in response.json()["data"]["roles"]}
    assert {
        "planner_agent",
        "coder_agent",
        "validator_agent",
        "repair_agent",
        "researcher_agent",
        "summarizer_agent",
        "architecture_agent",
        "routing_agent",
    } == role_ids
    planner = next(role for role in response.json()["data"]["roles"] if role["id"] == "planner_agent")
    assert planner["preferred_model_profile"]["route_profile"] == "best_reasoning"
    assert response.json()["data"]["communication_contracts"]["freeform_agent_chat"] is False
