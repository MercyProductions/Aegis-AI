from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.validation as validation_module
from aegis_core.config import AegisConfig, load_config, update_config, write_default_config
from aegis_core.memory import ProjectMemory
from aegis_core.safety import is_ignored_path, is_safe_to_read, is_secret_like
from aegis_core.server import create_app
from aegis_core.validation import append_validation_log, detect_validation_commands, run_validation
from aegis_core.workspace import WorkspaceScanner


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


def test_config_read_write_survives_damaged_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "damaged-config-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").mkdir()

    assert load_config(workspace).default_model == AegisConfig.default_model
    assert write_default_config(workspace) == aegis_dir / "config.json"
    assert update_config(workspace, {"default_model": "granite-code:8b"}).default_model == AegisConfig.default_model

    client = TestClient(create_app())
    get_response = client.get("/v1/settings", params={"workspace": str(workspace)})
    post_response = client.post(
        "/v1/settings",
        json={"workspace": str(workspace), "settings": {"default_model": "qwen2.5-coder:7b"}},
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert post_response.json()["data"]["default_model"] == AegisConfig.default_model


def test_config_write_survives_memory_root_file(tmp_path: Path) -> None:
    workspace = tmp_path / "config-root-file-project"
    workspace.mkdir()
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")

    assert load_config(workspace).default_model == AegisConfig.default_model
    assert write_default_config(workspace) == workspace / ".aegis" / "config.json"
    assert update_config(workspace, {"default_model": "granite-code:8b"}).default_model == AegisConfig.default_model


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


def test_validation_detection_respects_package_scripts(tmp_path: Path) -> None:
    workspace = tmp_path / "node-project"
    workspace.mkdir()
    (workspace / "package.json").write_text(json.dumps({"scripts": {"start": "vite"}}), encoding="utf-8")

    assert [item.name for item in detect_validation_commands(workspace)] == []

    (workspace / "package.json").write_text(
        "\ufeff" + json.dumps({"scripts": {"test": "vitest run", "build": "vite build"}}),
        encoding="utf-8",
    )
    assert [item.name for item in detect_validation_commands(workspace)] == ["npm test", "npm run build"]

    (workspace / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    assert [item.name for item in detect_validation_commands(workspace)] == ["pnpm test", "pnpm build"]


def test_validation_runner_blocks_unsafe_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "validation-project"
    workspace.mkdir()

    result = run_validation(workspace, command=["python", "-c", "print('unsafe')"])

    assert result["ok"] is False
    assert result["blocked"] is True
    assert "Blocked unsafe validation command" in result["stderr"]
    log = workspace / ".aegis" / "validation-log.md"
    assert log.exists()
    assert "Blocked unsafe validation command" in log.read_text(encoding="utf-8")


def test_validation_runner_handles_safe_command_failures(tmp_path: Path) -> None:
    workspace = tmp_path / "pytest-project"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname = \"pytest-project\"\nversion = \"0.0.0\"\n", encoding="utf-8")
    (workspace / "test_failure.py").write_text("def test_failure():\n    assert False\n", encoding="utf-8")

    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"], timeout=30)

    assert result["ok"] is False
    assert result["returncode"] is not None
    assert "test_failure" in (result["stdout"] + result["stderr"])


def test_validation_runner_handles_missing_executable(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "missing-tool-project"
    workspace.mkdir()

    def raise_missing(*args, **kwargs):
        error = FileNotFoundError("missing")
        error.filename = "python"
        raise error

    monkeypatch.setattr(validation_module.subprocess, "run", raise_missing)
    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"])

    assert result["ok"] is False
    assert result["returncode"] is None
    assert "Validation executable not found" in result["stderr"]


def test_validation_runner_handles_timeout(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "timeout-project"
    workspace.mkdir()

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=1, output=b"partial stdout", stderr=b"partial stderr")

    monkeypatch.setattr(validation_module.subprocess, "run", raise_timeout)
    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"], timeout=1)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert "partial stdout" in result["stdout"]
    assert "partial stderr" in result["stderr"]


def test_validation_result_redacts_secret_like_output(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "redacted-result-project"
    workspace.mkdir()

    def return_secret_output(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="normal stdout\nAPI_TOKEN=abc123",
            stderr="normal stderr\nAuthorization: Bearer abc123",
        )

    monkeypatch.setattr(validation_module.subprocess, "run", return_secret_output)
    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"])

    assert "normal stdout" in result["stdout"]
    assert "normal stderr" in result["stderr"]
    assert "[redacted secret-like log line]" in result["stdout"]
    assert "[redacted secret-like log line]" in result["stderr"]
    assert "abc123" not in result["stdout"]
    assert "abc123" not in result["stderr"]


def test_validation_log_redacts_secret_like_lines(tmp_path: Path) -> None:
    workspace = tmp_path / "redaction-project"
    workspace.mkdir()

    append_validation_log(
        workspace,
        {
            "ok": False,
            "command": ["npm", "test"],
            "stderr": "normal failure\nAPI_TOKEN=abc123\nAuthorization: Bearer abc123\npassword=hunter2",
        },
    )

    text = (workspace / ".aegis" / "validation-log.md").read_text(encoding="utf-8")
    assert "normal failure" in text
    assert "[redacted secret-like log line]" in text
    assert "abc123" not in text
    assert "hunter2" not in text


def test_validation_log_write_failures_do_not_crash(tmp_path: Path) -> None:
    workspace = tmp_path / "log-directory-project"
    workspace.mkdir()
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "validation-log.md").mkdir()

    append_validation_log(workspace, {"ok": False, "command": ["npm", "test"], "stderr": "still returns"})


def test_health_survives_unwritable_core_log_path(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "core-log.md").mkdir()

    client = TestClient(create_app())
    response = client.get("/v1/health", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_workspace_scan_survives_damaged_memory_write_targets(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    for name in ("file-index.json", "project-summary.md", "architecture-map.md"):
        (aegis_dir / name).mkdir()

    result = WorkspaceScanner(workspace).scan(persist=True)

    assert result["workspace"] == str(workspace.resolve())
    assert result["file_count"] > 0
    assert not (aegis_dir / ".file-index.json.tmp").exists()
    assert not (aegis_dir / ".project-summary.md.tmp").exists()


def test_project_memory_writes_are_best_effort_when_memory_root_is_file(tmp_path: Path) -> None:
    workspace = tmp_path / "memory-root-file-project"
    workspace.mkdir()
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")

    memory = ProjectMemory(workspace)

    memory.write_json("file-index.json", {"ok": True})
    memory.write_generated_markdown("project-summary.md", "Project Summary", "Still returns.")
    memory.append_decision("No crash when memory root is not writable.")
