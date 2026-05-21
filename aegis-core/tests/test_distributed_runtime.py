from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "distributed-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Distributed Project\n\nTODO: validate distributed runtime.\n", encoding="utf-8")
    (workspace / "package.json").write_text(json.dumps({"scripts": {"test": "node smoke.js"}}), encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def test_runtime_dashboard_persists_local_authority_node(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/distributed-runtime", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_contract(response.json(), "distributed.runtime")
    data = response.json()["data"]
    local = next(node for node in data["nodes"] if node["node_id"] == "local")
    assert local["trust_level"] == "local"
    assert "validation_execution" in local["capabilities"]
    assert data["local_authority"]["node_id"] == "local"
    assert (workspace / ".aegis" / "distributed-runtime.json").is_file()


def test_node_registration_trust_and_heartbeat(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    monkeypatch.setenv("AEGIS_DISTRIBUTED_NODE_TOKEN", "trusted-token")

    untrusted = client.post(
        "/v1/distributed-runtime/nodes/register",
        json={
            "workspace": str(workspace),
            "node_id": "remote-gpu",
            "node_type": "gpu_model",
            "endpoint": "http://worker.internal:8765",
            "capabilities": ["model_inference", "gpu"],
            "permission_scopes": ["model_access"],
        },
    )
    trusted = client.post(
        "/v1/distributed-runtime/nodes/register",
        json={
            "workspace": str(workspace),
            "node_id": "remote-gpu",
            "node_type": "gpu_model",
            "endpoint": "https://worker.internal:8765",
            "auth_token": "trusted-token",
            "capabilities": ["model_inference", "gpu"],
            "permission_scopes": ["model_access"],
            "installed_models": ["llama3.1:8b"],
            "max_parallel_workloads": 2,
        },
    )
    heartbeat = client.post(
        "/v1/distributed-runtime/nodes/remote-gpu/heartbeat",
        json={"workspace": str(workspace), "status": "idle", "health": {"latency_ms": 12}},
    )

    assert untrusted.status_code == 200
    assert_contract(untrusted.json(), "distributed.node.registered")
    assert untrusted.json()["ok"] is False
    assert untrusted.json()["data"]["node"]["trust_level"] == "untrusted"
    assert trusted.status_code == 200
    assert trusted.json()["ok"] is True
    assert trusted.json()["data"]["node"]["trust_level"] == "trusted"
    assert heartbeat.status_code == 200
    assert_contract(heartbeat.json(), "distributed.node.heartbeat")
    assert heartbeat.json()["data"]["node"]["status"] == "idle"


def test_remote_workload_requires_opt_in_and_recovers_to_local_queue(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    monkeypatch.setenv("AEGIS_DISTRIBUTED_NODE_TOKEN", "trusted-token")
    client.post(
        "/v1/distributed-runtime/nodes/register",
        json={
            "workspace": str(workspace),
            "node_id": "gpu-node",
            "node_type": "gpu_model",
            "endpoint": "https://gpu-node.local",
            "auth_token": "trusted-token",
            "capabilities": ["model_inference", "gpu"],
            "permission_scopes": ["model_access"],
            "max_parallel_workloads": 1,
        },
    )
    created = client.post(
        "/v1/distributed-runtime/workloads",
        json={
            "workspace": str(workspace),
            "workload_type": "model_inference",
            "title": "GPU route",
            "required_capabilities": ["gpu"],
            "permission_scopes": ["model_access"],
            "dry_run": True,
        },
    )
    workload_id = created.json()["data"]["workload"]["workload_id"]

    blocked = client.post(
        f"/v1/distributed-runtime/workloads/{workload_id}/dispatch",
        json={"workspace": str(workspace), "allow_remote": False},
    )
    assigned = client.post(
        f"/v1/distributed-runtime/workloads/{workload_id}/dispatch",
        json={"workspace": str(workspace), "allow_remote": True, "approval": True},
    )
    client.post("/v1/distributed-runtime/nodes/gpu-node/heartbeat", json={"workspace": str(workspace), "status": "offline"})
    recovered = client.post("/v1/distributed-runtime/recover", json={"workspace": str(workspace)})

    assert created.status_code == 200
    assert_contract(created.json(), "distributed.workload.created")
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    assert "remote dispatch is not enabled" in str(blocked.json()["data"]["rejected_nodes"])
    assert assigned.status_code == 200
    assert assigned.json()["data"]["remote_dispatch"] is True
    assert assigned.json()["data"]["workload"]["status"] == "assigned"
    assert recovered.status_code == 200
    assert workload_id in recovered.json()["data"]["requeued_workload_ids"]
    lookup = client.get(f"/v1/distributed-runtime/workloads/{workload_id}", params={"workspace": str(workspace)})
    assert lookup.json()["data"]["workload"]["status"] == "queued"
    assert "local" in lookup.json()["data"]["workload"]["fallback_node_ids"]


def test_validation_workload_approval_gate_and_result_capture(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    created = client.post(
        "/v1/distributed-runtime/workloads",
        json={
            "workspace": str(workspace),
            "workload_type": "validation",
            "title": "Run validation safely",
            "dry_run": False,
            "payload": {"allow_process_execution": True, "command": ["npm", "test"], "timeout_seconds": 15},
        },
    )
    workload_id = created.json()["data"]["workload"]["workload_id"]

    waiting = client.post(
        f"/v1/distributed-runtime/workloads/{workload_id}/dispatch",
        json={"workspace": str(workspace), "approval": False},
    )
    captured = client.post(
        "/v1/distributed-runtime/dispatch",
        json={
            "workspace": str(workspace),
            "workload_type": "validation",
            "title": "Dry-run validation discovery",
            "dry_run": True,
        },
    )

    assert waiting.status_code == 200
    assert waiting.json()["data"]["workload"]["status"] == "waiting_approval"
    assert "approval" in waiting.json()["data"]["reason"].lower()
    assert captured.status_code == 200
    assert_contract(captured.json(), "distributed.workload.dispatch")
    assert captured.json()["data"]["workload"]["status"] == "completed"
    assert captured.json()["data"]["workload"]["result"]["validation_summary"]["commands"]


def test_observability_audit_deployment_and_ecosystem_hooks(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    client.post(
        "/v1/distributed-runtime/dispatch",
        json={"workspace": str(workspace), "workload_type": "indexing", "title": "Index workspace", "dry_run": True},
    )

    observability = client.get("/v1/distributed-runtime/observability", params={"workspace": str(workspace)})
    audit = client.get("/v1/distributed-runtime/audit", params={"workspace": str(workspace), "limit": 20})
    bootstrap = client.get(
        "/v1/distributed-runtime/deployment/bootstrap",
        params={"workspace": str(workspace), "node_type": "validation", "shell": "powershell"},
    )
    ecosystem = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})

    assert observability.status_code == 200
    assert_contract(observability.json(), "distributed.observability")
    assert observability.json()["data"]["observability"]["workloads"]["completed"] >= 1
    assert audit.status_code == 200
    assert_contract(audit.json(), "distributed.audit")
    assert any(event["event_type"] == "runtime.workload.completed" for event in audit.json()["data"]["audit_events"])
    assert bootstrap.status_code == 200
    assert_contract(bootstrap.json(), "distributed.deployment")
    assert "nodes/register" in bootstrap.json()["data"]["script"]
    assert ecosystem.status_code == 200
    assert ecosystem.json()["data"]["distributed_runtime"]["node_count"] >= 1
