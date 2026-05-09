from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.config import AegisConfig, load_config
from aegis_core.safety import is_ignored_path, is_safe_to_read, is_secret_like
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "sample-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Sample Project\n\nTODO: validate workflow.\n", encoding="utf-8")
    (workspace / "package.json").write_text(
        json.dumps({"scripts": {"test": "node smoke.js", "build": "node smoke.js"}, "dependencies": {"vite": "^7.0.0"}}, indent=2),
        encoding="utf-8",
    )
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    return workspace


def run_cli(core_root: Path, *args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "aegis_core.cli", *args],
        cwd=str(core_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_cli_json_flag_works_before_or_after_subcommand(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    core_root = Path(__file__).resolve().parents[1]

    prefix = run_cli(core_root, "--json", "dashboard", "--workspace", str(workspace))
    suffix = run_cli(core_root, "dashboard", "--workspace", str(workspace), "--json")

    assert prefix["workspace"] == str(workspace.resolve())
    assert suffix["workspace"] == str(workspace.resolve())
    assert prefix["model_status"]["selected_model"] == suffix["model_status"]["selected_model"]


def test_workspace_scan_cache_reuses_unchanged_scan(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    core_root = Path(__file__).resolve().parents[1]

    first = run_cli(core_root, "--json", "scan", "--workspace", str(workspace))
    second = run_cli(core_root, "--json", "scan", "--workspace", str(workspace))

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["cache_reason"] == "workspace file fingerprint unchanged"
    assert (workspace / ".aegis" / "scan-cache.json").exists()


def test_v1_client_task_dashboard_contract(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    registration = client.post(
        "/v1/clients/register",
        json={
            "workspace": str(workspace),
            "client_id": "contract-test-client",
            "client_type": "test",
            "name": "Contract Test Client",
            "version": "0.0.0",
            "capabilities": ["health", "tasks"],
        },
    )
    assert registration.status_code == 200
    assert registration.json()["data"]["client_id"] == "contract-test-client"

    created = client.post(
        "/v1/tasks",
        json={
            "workspace": str(workspace),
            "title": "Contract smoke task",
            "kind": "test",
            "source_client": "pytest",
            "request": "validate shared task flow",
        },
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["id"]

    dashboard = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    assert any(item["client_id"] == "contract-test-client" for item in data["clients"])
    assert any(item["id"] == task_id for item in data["active_tasks"])

    updated = client.post(
        f"/v1/tasks/{task_id}/status",
        json={"workspace": str(workspace), "status": "completed", "summary": "contract passed"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "completed"

    invalid_status = client.post(
        f"/v1/tasks/{task_id}/status",
        json={"workspace": str(workspace), "status": "definitely-not-real"},
    )
    assert invalid_status.status_code == 400

    missing_task = client.post(
        "/v1/tasks/task-missing/status",
        json={"workspace": str(workspace), "status": "completed"},
    )
    assert missing_task.status_code == 404


def test_safety_rules_are_case_insensitive_and_secret_aware(tmp_path: Path) -> None:
    assert is_ignored_path(tmp_path / "Node_Modules" / "package" / "index.js", tmp_path)
    assert is_ignored_path(tmp_path / "LIBRARY" / "metadata.json", tmp_path)
    assert is_secret_like(tmp_path / ".env.example")
    assert is_secret_like(tmp_path / "service-token.json")
    assert is_secret_like(tmp_path / "prod.password.txt")
    assert is_safe_to_read(tmp_path / "src" / "tokenizer.py", tmp_path)
    assert not is_safe_to_read(tmp_path / "Temp" / "cache.json", tmp_path)


def test_invalid_config_values_fall_back_safely(tmp_path: Path) -> None:
    workspace = tmp_path / "config-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").write_text(
        json.dumps(
            {
                "ollama_url": "",
                "default_model": "  ",
                "fallback_models": "",
                "max_context_chars": "not-a-number",
                "auto_scan_on_open": "false",
                "validation_preferences": "npm test, npm run build",
                "memory_dir_name": "",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(workspace)

    assert config.ollama_url == AegisConfig.ollama_url
    assert config.default_model == AegisConfig.default_model
    assert config.fallback_models == AegisConfig.fallback_models
    assert config.max_context_chars == AegisConfig.max_context_chars
    assert config.auto_scan_on_open is False
    assert config.validation_preferences == ("npm test", "npm run build")
    assert config.memory_dir_name == AegisConfig.memory_dir_name


def test_dashboard_survives_unreadable_memory_files(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    for name in ("clients.json", "tasks.json", "agent-history.json", "roadmap.md", "core-log.md"):
        (aegis_dir / name).mkdir()

    client = TestClient(create_app())
    response = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["clients"] == []
    assert data["active_tasks"] == []
    assert data["recent_activity"] == []
    assert data["roadmap"]["excerpt"] == ""
