from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.onboarding as onboarding
from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "onboarding-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Onboarding Project\n", encoding="utf-8")
    (workspace / "package.json").write_text(json.dumps({"scripts": {"test": "node smoke.js"}}), encoding="utf-8")
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def fake_model_registry(workspace: str | Path) -> dict:
    root = Path(workspace).resolve()
    return {
        "workspace": str(root),
        "active_profile": "local_only",
        "selected_model": {"provider_id": "ollama", "model_id": "qwen3-coder:30b"},
        "fallback_models": [],
        "providers": [],
        "models": [{"provider_id": "ollama", "model_id": "qwen3-coder:30b"}],
        "ollama": {
            "reachable": True,
            "latency_ms": 7,
            "installed_models": ["qwen3-coder:30b"],
            "selected_model": "qwen3-coder:30b",
            "missing_models": [],
        },
    }


def fake_provider_inventory(workspace: str | Path) -> dict:
    return {
        "mode": "local_only",
        "local_only": True,
        "privacy_mode": "local-first",
        "cloud_disabled": False,
        "providers": [
            {
                "id": "ollama",
                "label": "Ollama",
                "local": True,
                "configured": True,
                "requires_key": False,
                "key_stored": False,
                "availability_status": "available",
            },
            {
                "id": "openai",
                "label": "OpenAI",
                "local": False,
                "configured": False,
                "requires_key": True,
                "key_stored": False,
                "availability_status": "missing_auth",
            },
        ],
    }


def patch_fast_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(onboarding, "model_registry", fake_model_registry)
    monkeypatch.setattr(onboarding, "provider_inventory", fake_provider_inventory)


def test_onboarding_status_contract_includes_wizard_diagnostics_and_recovery(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/onboarding/status", params={"workspace": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == "onboarding.status"
    data = payload["data"]
    assert data["workspace"] == str(workspace.resolve())
    assert any(step["id"] == "privacy" for step in data["steps"])
    assert data["diagnostics"]["summary"]["failure_count"] == 0
    assert any(check["id"] == "ollama_running" and check["status"] == "pass" for check in data["diagnostics"]["checks"])
    recovery_ids = {card["id"] for card in data["recovery"]}
    assert {
        "backend_down",
        "core_offline",
        "ollama_offline",
        "model_unavailable",
        "key_missing",
        "provider_missing",
        "workspace_blocked",
        "update_failed",
        "validation_failed",
        "extension_disconnected",
        "desktop_blank_state",
    }.issubset(recovery_ids)


def test_onboarding_status_reports_invalid_workspace_without_creating_state(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    missing = tmp_path / "missing-project"
    client = TestClient(create_app())

    response = client.get("/v1/onboarding/status", params={"workspace": str(missing)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["diagnostics"]["summary"]["failure_count"] >= 1
    assert any(check["id"] == "workspace_selected" and check["status"] == "fail" for check in data["diagnostics"]["checks"])
    assert not missing.exists()


def test_onboarding_status_handles_no_ollama_or_models(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)

    def failing_model_registry(workspace: str | Path) -> dict:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(onboarding, "model_registry", failing_model_registry)
    monkeypatch.setattr(onboarding, "provider_inventory", fake_provider_inventory)
    client = TestClient(create_app())

    response = client.get("/v1/onboarding/status", params={"workspace": str(workspace)})

    assert response.status_code == 200
    checks = response.json()["data"]["diagnostics"]["checks"]
    assert any(check["id"] == "ollama_running" and check["status"] == "warn" for check in checks)
    assert any(check["id"] == "models_available" and check["status"] == "warn" for check in checks)
    recovery = response.json()["data"]["recovery"]
    assert any(card["id"] == "ollama_offline" and card["active"] for card in recovery)


def test_onboarding_update_persists_progress_and_preferences(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/onboarding",
        json={
            "workspace": str(workspace),
            "completed_steps": ["welcome", "privacy", "workspace"],
            "current_step": "local_models",
            "preferences": {"theme": "dark", "brand_variant": "auralith", "ignored": "nope"},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current_step"] == "local_models"
    assert data["settings"]["preferences"]["theme"] == "dark"
    state = json.loads((workspace / ".aegis" / "onboarding-state.json").read_text(encoding="utf-8"))
    assert state["preferences"]["brand_variant"] == "auralith"
    assert "ignored" not in state["preferences"]


def test_settings_export_and_import_do_not_include_plaintext_provider_keys(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").mkdir(exist_ok=True)
    (workspace / ".aegis" / "config.json").write_text(
        json.dumps({"model_routing_mode": "local_only", "default_model": "local-before"}),
        encoding="utf-8",
    )
    client = TestClient(create_app())

    exported = client.get("/v1/settings/export", params={"workspace": str(workspace)})
    imported = client.post(
        "/v1/settings/import",
        json={
            "workspace": str(workspace),
            "dry_run": False,
            "settings": {
                "settings": {"default_model": "local-after", "model_routing_mode": "hybrid", "api_key": "sk-secret"},
                "ui_preferences": {"theme": "light"},
            },
        },
    )

    assert exported.status_code == 200
    assert "sk-" not in json.dumps(exported.json())
    assert imported.status_code == 200
    data = imported.json()["data"]
    assert data["dry_run"] is False
    assert "default_model" in data["imported_keys"]
    assert "api_key" in data["ignored_keys"]
    config = json.loads((workspace / ".aegis" / "config.json").read_text(encoding="utf-8"))
    assert config["default_model"] == "local-after"


def test_settings_import_dry_run_does_not_persist_runtime_settings(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").mkdir(exist_ok=True)
    (workspace / ".aegis" / "config.json").write_text(json.dumps({"default_model": "before"}), encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/settings/import",
        json={
            "workspace": str(workspace),
            "dry_run": True,
            "settings": {"settings": {"default_model": "after"}, "ui_preferences": {"theme": "dark"}},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dry_run"] is True
    assert "default_model" in data["imported_keys"]
    config = json.loads((workspace / ".aegis" / "config.json").read_text(encoding="utf-8"))
    assert config["default_model"] == "before"


def test_first_workflow_actions_capture_scan_validation_and_checkpoint_preview(tmp_path: Path, monkeypatch) -> None:
    patch_fast_diagnostics(monkeypatch)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    scan = client.post(
        "/v1/onboarding/first-workflow",
        json={"workspace": str(workspace), "action": "scan_project", "dry_run": True},
    )
    proposal = client.post(
        "/v1/onboarding/first-workflow",
        json={"workspace": str(workspace), "action": "propose_small_improvement", "dry_run": True},
    )
    validation = client.post(
        "/v1/onboarding/first-workflow",
        json={"workspace": str(workspace), "action": "validate_only", "dry_run": True},
    )
    rollback = client.post(
        "/v1/onboarding/first-workflow",
        json={"workspace": str(workspace), "action": "checkpoint_rollback_demo", "dry_run": True},
    )

    assert scan.status_code == 200
    assert scan.json()["data"]["result"]["file_count"] >= 3
    assert proposal.status_code == 200
    assert proposal.json()["data"]["result"]["applies_files"] is False
    assert validation.status_code == 200
    assert validation.json()["data"]["result"]["dry_run"] is True
    assert rollback.status_code == 200
    assert rollback.json()["data"]["result"]["dry_run"] is True
    state = json.loads((workspace / ".aegis" / "onboarding-state.json").read_text(encoding="utf-8"))
    assert "scan_project" in state["first_workflow"]["completed_steps"]
    assert "validate_only" in state["first_workflow"]["completed_steps"]
