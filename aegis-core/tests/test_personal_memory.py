from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path, name: str = "memory-project") -> Path:
    workspace = tmp_path / name
    workspace.mkdir()
    (workspace / "README.md").write_text("# Memory Project\n\nTODO: remember safely.\n", encoding="utf-8")
    (workspace / "package.json").write_text('{"scripts":{"test":"node smoke.js"}}\n', encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def test_personal_memory_persistence_lifecycle_and_observability(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    created = client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace),
            "category": "user_preferences",
            "scope": "user",
            "title": "Validation style",
            "content": "Prefer small changes and run npm test before apply.",
            "tags": ["validation", "safety"],
            "pinned": True,
        },
    )
    memory_id = created.json()["data"]["record"]["id"]
    listed = client.get("/v1/personal-memory", params={"workspace": str(workspace), "query": "npm test"})
    updated = client.patch(
        f"/v1/personal-memory/records/{memory_id}",
        json={"workspace": str(workspace), "confidence": 0.95, "tags": ["validation", "approval"]},
    )
    archived = client.post(
        f"/v1/personal-memory/records/{memory_id}/archive",
        json={"workspace": str(workspace), "reason": "covered by newer note"},
    )
    observability = client.get("/v1/personal-memory/observability", params={"workspace": str(workspace)})

    assert created.status_code == 200
    assert_contract(created.json(), "personal.memory.record")
    assert (workspace / ".aegis" / "auralith-memory.json").is_file()
    assert listed.status_code == 200
    assert_contract(listed.json(), "personal.memory")
    assert listed.json()["data"]["records"][0]["id"] == memory_id
    assert updated.json()["data"]["record"]["confidence"] == 0.95
    assert archived.json()["data"]["record"]["status"] == "archived"
    assert observability.status_code == 200
    assert_contract(observability.json(), "personal.memory.observability")
    assert observability.json()["data"]["observability"]["records"]["archived"] == 1


def test_memory_privacy_controls_secret_redaction_and_disabled_category(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    controls = client.post(
        "/v1/personal-memory/controls",
        json={"workspace": str(workspace), "category": "repair_history", "enabled": False},
    )
    blocked = client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace),
            "category": "repair_history",
            "title": "Should be blocked",
            "content": "Do not store this.",
        },
    )
    secret = client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace),
            "category": "user_preferences",
            "title": "Provider habit",
            "content": "Use local models; api_key=super-secret-value should never be stored.",
            "privacy": {"local_only": True},
        },
    )
    exported = client.post(
        "/v1/personal-memory/export",
        json={"workspace": str(workspace), "redact_sensitive": True},
    )

    assert controls.status_code == 200
    assert_contract(controls.json(), "personal.memory.controls")
    assert blocked.status_code == 400
    record = secret.json()["data"]["record"]
    assert "[redacted" in record["content"]
    assert record["privacy"]["sensitive"] is True
    exported_record = exported.json()["data"]["export"]["records"][0]
    assert exported_record["content"] == "[redacted sensitive memory]"


def test_memory_export_import_and_project_isolation(tmp_path: Path) -> None:
    workspace_a = make_workspace(tmp_path, "project-a")
    workspace_b = make_workspace(tmp_path, "project-b")
    client = TestClient(create_app())
    client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace_a),
            "category": "architecture_notes",
            "title": "Adapter boundary",
            "content": "Keep Core contracts separate from UI adapters.",
            "tags": ["architecture"],
        },
    )

    exported = client.post("/v1/personal-memory/export", json={"workspace": str(workspace_a)})
    dry_run = client.post(
        "/v1/personal-memory/import",
        json={"workspace": str(workspace_b), "payload": exported.json()["data"]["export"], "dry_run": True},
    )
    imported = client.post(
        "/v1/personal-memory/import",
        json={"workspace": str(workspace_b), "payload": exported.json()["data"]["export"], "dry_run": False},
    )
    list_a = client.get("/v1/personal-memory", params={"workspace": str(workspace_a)})
    list_b = client.get("/v1/personal-memory", params={"workspace": str(workspace_b)})

    assert exported.status_code == 200
    assert_contract(exported.json(), "personal.memory.export")
    assert dry_run.json()["data"]["preview_count"] == 1
    assert imported.json()["data"]["imported_count"] == 1
    assert list_a.json()["data"]["workspace"] != list_b.json()["data"]["workspace"]
    assert len(list_a.json()["data"]["records"]) == 1
    assert len(list_b.json()["data"]["records"]) == 1


def test_memory_cleanup_archives_expired_records_and_delete_hard_removes(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    created = client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace),
            "category": "execution_history",
            "title": "Old execution",
            "content": "This execution history can expire.",
            "expires_at": past,
        },
    )
    memory_id = created.json()["data"]["record"]["id"]

    preview = client.post("/v1/personal-memory/cleanup", json={"workspace": str(workspace), "dry_run": True})
    cleanup = client.post("/v1/personal-memory/cleanup", json={"workspace": str(workspace), "dry_run": False})
    deleted = client.request(
        "DELETE",
        f"/v1/personal-memory/records/{memory_id}",
        json={"workspace": str(workspace), "hard_delete": True, "reason": "test cleanup"},
    )
    listed = client.get("/v1/personal-memory", params={"workspace": str(workspace), "include_archived": True})

    assert preview.json()["data"]["expired_ids"] == [memory_id]
    assert cleanup.json()["data"]["expired_ids"] == [memory_id]
    assert deleted.json()["data"]["deleted"] is True
    assert listed.json()["data"]["records"] == []


def test_memory_aware_workflow_uses_prior_context_and_records_usage(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    created = client.post(
        "/v1/personal-memory",
        json={
            "workspace": str(workspace),
            "category": "workflow_patterns",
            "title": "Vite validation workflow",
            "content": "For Vite work, inspect package.json and run npm test before apply.",
            "tags": ["vite", "validation"],
        },
    )
    memory_id = created.json()["data"]["record"]["id"]

    workflow = client.post(
        "/v1/workflows",
        json={
            "workspace": str(workspace),
            "workflow_type": "generate_feature",
            "objective": "Add a small Vite validation improvement",
        },
    )
    context = client.post(
        "/v1/personal-memory/context",
        json={
            "workspace": str(workspace),
            "workflow_type": "generate_feature",
            "objective": "Vite validation",
            "record_usage": False,
        },
    )
    listed = client.get("/v1/personal-memory", params={"workspace": str(workspace), "query": "Vite"})

    assert workflow.status_code == 200
    assert_contract(workflow.json(), "workflow.created")
    memory_context = workflow.json()["data"]["workflow"]["personal_memory_context"]
    assert memory_context["used"] is True
    assert memory_context["records"][0]["id"] == memory_id
    assert context.json()["data"]["guidance"]
    record = listed.json()["data"]["records"][0]
    assert record["usage"]["retrieval_count"] >= 1
