from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.plugin_runtime as plugin_runtime
from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "plugin-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Plugin Project\n\nTODO: wire plugin runtime.\n", encoding="utf-8")
    (workspace / "package.json").write_text(json.dumps({"scripts": {"test": "node smoke.js"}}), encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def write_plugin(workspace: Path, plugin_id: str, manifest: dict) -> Path:
    folder = workspace / ".aegis" / "plugins" / plugin_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "aegis-plugin.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def test_plugin_dashboard_discovers_reference_plugins_and_contracts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/plugins", params={"workspace": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == "plugin.dashboard"
    data = payload["data"]
    plugin_ids = {plugin["id"] for plugin in data["plugins"]}
    assert "aegis-architecture-analyzer" in plugin_ids
    assert "aegis-observability-widget" in plugin_ids
    assert any(tool["name"] == "architecture-summary" for tool in data["tool_catalog"])
    assert data["workflow_hooks"]["architecture_analyzers"]
    assert any(item["kind"] == "dashboard_widget" for item in data["ui_extensions"])
    assert data["packaging_format"]["manifest_names"]


def test_high_risk_plugin_enable_requires_approval(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/plugins/state",
        json={"workspace": str(workspace), "plugin_id": "aegis-custom-validator", "enabled": True},
    )
    approved = client.post(
        "/v1/plugins/state",
        json={
            "workspace": str(workspace),
            "plugin_id": "aegis-custom-validator",
            "enabled": True,
            "approval": True,
            "reason": "test approval",
        },
    )

    assert blocked.status_code == 400
    assert "blocked" in blocked.json()["detail"]
    assert approved.status_code == 200
    assert approved.json()["data"]["plugin"]["enabled"] is True
    state = json.loads((workspace / ".aegis" / "plugin-state.json").read_text(encoding="utf-8"))
    assert state["plugins"]["aegis-custom-validator"]["enabled"] is True


def test_tool_execution_blocks_high_risk_without_approval_then_runs_builtin_handler(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    client.post(
        "/v1/plugins/state",
        json={"workspace": str(workspace), "plugin_id": "aegis-custom-validator", "enabled": True, "approval": True},
    )

    blocked = client.post(
        "/v1/plugins/tools/run",
        json={
            "workspace": str(workspace),
            "plugin_id": "aegis-custom-validator",
            "tool_name": "validation-hint",
            "dry_run": True,
        },
    )
    approved = client.post(
        "/v1/plugins/tools/run",
        json={
            "workspace": str(workspace),
            "plugin_id": "aegis-custom-validator",
            "tool_name": "validation-hint",
            "dry_run": True,
            "approval": True,
            "workflow_type": "validate_project",
        },
    )

    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    assert blocked.json()["data"]["blocked"] is True
    assert "approval" in blocked.json()["data"]["errors"][0].lower()
    assert approved.status_code == 200
    assert approved.json()["ok"] is True
    assert approved.json()["data"]["result"]["suggested_commands"]
    observability = plugin_runtime.plugin_observability(workspace)
    assert observability["event_count"] >= 2
    assert observability["permissions_used"]["validation_execution"] >= 2


def test_plugin_failure_isolation_for_bad_manifest_and_external_handler(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    bad_dir = workspace / ".aegis" / "plugins" / "bad-json"
    bad_dir.mkdir(parents=True)
    (bad_dir / "aegis-plugin.json").write_text("{ nope", encoding="utf-8")
    write_plugin(
        workspace,
        "external-runner",
        {
            "id": "external-runner",
            "name": "External Runner",
            "version": "1.0.0",
            "api_version": plugin_runtime.PLUGIN_API_VERSION,
            "category": "observability_tools",
            "capabilities": ["tool"],
            "permission_scopes": ["observability_read"],
            "runtime_compatibility": {"min_core_version": "0.1.0"},
            "tools": [
                {
                    "name": "external",
                    "description": "Should be isolated.",
                    "safety_level": "low",
                    "required_permissions": ["observability_read"],
                    "handler": "python.module:run",
                }
            ],
            "enabled": True,
            "trusted": True,
        },
    )
    client = TestClient(create_app())

    dashboard = client.get("/v1/plugins", params={"workspace": str(workspace)})
    run = client.post(
        "/v1/plugins/tools/run",
        json={"workspace": str(workspace), "plugin_id": "external-runner", "tool_name": "external"},
    )

    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["diagnostics"]["load_failures"]
    assert run.status_code == 200
    assert run.json()["data"]["blocked"] is True
    assert "code execution is disabled" in run.json()["data"]["errors"][0]


def test_compatibility_rejection_and_workflow_hook_filtering(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    write_plugin(
        workspace,
        "future-plugin",
        {
            "id": "future-plugin",
            "name": "Future Plugin",
            "version": "1.0.0",
            "api_version": plugin_runtime.PLUGIN_API_VERSION,
            "category": "workflow_types",
            "capabilities": ["workflow_extension"],
            "permission_scopes": ["workspace_scan"],
            "runtime_compatibility": {"min_core_version": "99.0.0"},
            "workflow_extensions": {
                "workflow_stages": [
                    {"id": "future-stage", "label": "Future Stage", "workflow_types": ["generate_feature"]}
                ]
            },
            "enabled": True,
            "trusted": True,
        },
    )
    client = TestClient(create_app())

    dashboard = client.get("/v1/plugins", params={"workspace": str(workspace)})
    hooks = client.get("/v1/plugins/hooks", params={"workspace": str(workspace), "workflow_type": "generate_feature"})

    assert dashboard.status_code == 200
    rejected = [plugin for plugin in dashboard.json()["data"]["plugins"] if plugin["id"] == "future-plugin"][0]
    assert rejected["load_status"] == "rejected"
    assert any("requires Core" in error for error in rejected["validation"]["errors"])
    assert hooks.status_code == 200
    hook_ids = {hook["id"] for hook in hooks.json()["data"]["hooks"]["workflow_stages"]}
    assert "roadmap-plugin-context" in hook_ids
    assert "future-stage" not in hook_ids
