from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import aegis_core.validation as validation_module
from aegis_core.clients import list_clients
from aegis_core.config import AegisConfig, load_config, memory_dir, update_config, write_default_config
from aegis_core.memory import ProjectMemory
from aegis_core.ollama import OllamaClient
from aegis_core.safety import is_ignored_path, is_safe_to_edit, is_safe_to_read, is_secret_like
from aegis_core.server import create_app
from aegis_core.tasks import list_tasks, update_task_status
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


def run_cli_raw(core_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "aegis_core.cli", *args],
        cwd=str(core_root),
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_json_flag_works_before_or_after_subcommand(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    core_root = Path(__file__).resolve().parents[1]

    prefix = run_cli(core_root, "--json", "dashboard", "--workspace", str(workspace))
    suffix = run_cli(core_root, "dashboard", "--workspace", str(workspace), "--json")

    assert prefix["workspace"] == str(workspace.resolve())
    assert suffix["workspace"] == str(workspace.resolve())
    assert prefix["model_status"]["selected_model"] == suffix["model_status"]["selected_model"]


def test_cli_task_create_reports_persistence_failure_without_traceback(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")
    core_root = Path(__file__).resolve().parents[1]

    completed = run_cli_raw(core_root, "--json", "tasks", "--workspace", str(workspace), "--create", "Unwritable task")

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "tasks"
    assert "Could not persist task" in payload["error"]
    assert "Traceback" not in completed.stdout
    assert "Traceback" not in completed.stderr


def test_workspace_scan_cache_reuses_unchanged_scan(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    core_root = Path(__file__).resolve().parents[1]

    first = run_cli(core_root, "--json", "scan", "--workspace", str(workspace))
    second = run_cli(core_root, "--json", "scan", "--workspace", str(workspace))

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["cache_reason"] == "workspace file fingerprint unchanged"
    assert (workspace / ".aegis" / "scan-cache.json").exists()


def test_workspace_scan_handles_malformed_package_dependency_shapes(tmp_path: Path) -> None:
    workspace = tmp_path / "malformed-package-project"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        json.dumps({"dependencies": ["react"], "devDependencies": None}),
        encoding="utf-8",
    )

    result = WorkspaceScanner(workspace).scan(persist=False)

    assert result["workspace"] == str(workspace.resolve())
    assert result["file_count"] == 1
    assert "Unknown" in result["frameworks"]


def test_workspace_scan_detects_frameworks_from_bom_package_json(tmp_path: Path) -> None:
    workspace = tmp_path / "bom-package-project"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        "\ufeff" + json.dumps({"dependencies": {"react": "^19.0.0", "vite": "^7.0.0"}}),
        encoding="utf-8",
    )

    result = WorkspaceScanner(workspace).scan(persist=False)

    assert "React" in result["frameworks"]
    assert "Vite" in result["frameworks"]


def test_workspace_scan_framework_detection_ignores_damaged_marker_shapes(tmp_path: Path) -> None:
    workspace = tmp_path / "damaged-framework-marker-project"
    workspace.mkdir()
    (workspace / "package.json").mkdir()
    (workspace / "Assets").write_text("not a Unity assets directory", encoding="utf-8")
    (workspace / "ProjectSettings").write_text("not a Unity settings directory", encoding="utf-8")

    result = WorkspaceScanner(workspace).scan(persist=False)

    assert result["frameworks"] == ["Unknown"]

    (workspace / "package.json").rmdir()
    (workspace / "package.json").write_text(json.dumps({"dependencies": {"react": "^19.0.0"}}), encoding="utf-8")
    (workspace / "Assets").unlink()
    (workspace / "ProjectSettings").unlink()
    (workspace / "Assets").mkdir()
    (workspace / "ProjectSettings").mkdir()

    result = WorkspaceScanner(workspace).scan(persist=False)

    assert "React" in result["frameworks"]
    assert "Unity" in result["frameworks"]


def test_workspace_scan_recent_files_survives_stat_race(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "stat-race-project"
    workspace.mkdir()
    flaky = workspace / "flaky.py"
    flaky.write_text("print('present during collection')\n", encoding="utf-8")
    scanner = WorkspaceScanner(workspace)
    monkeypatch.setattr(scanner, "_collect_files", lambda: [flaky])
    original_stat = Path.stat

    def stat_race(self, *args, **kwargs):
        if self == flaky:
            raise OSError("file disappeared")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_race)

    result = scanner.scan(persist=False)

    assert result["workspace"] == str(workspace.resolve())
    assert result["recent_files"] == ["flaky.py"]


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


def test_v1_endpoint_family_smoke_contracts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    get_endpoints = [
        ("/v1/health", {"workspace": str(workspace)}, "health"),
        ("/v1/models", {"workspace": str(workspace)}, "models"),
        ("/v1/settings", {"workspace": str(workspace)}, "settings"),
        ("/v1/memory", {"workspace": str(workspace)}, "memory.summary"),
        ("/v1/diagnostics", {"workspace": str(workspace)}, "diagnostics.summary"),
        ("/v1/branding", {}, "branding.tokens"),
        ("/v1/clients", {"workspace": str(workspace)}, "clients.list"),
        ("/v1/tasks", {"workspace": str(workspace)}, "tasks.list"),
        ("/v1/ecosystem/dashboard", {"workspace": str(workspace)}, "ecosystem.dashboard"),
    ]

    for endpoint, params, kind in get_endpoints:
        response = client.get(endpoint, params=params)
        assert response.status_code == 200, endpoint
        payload = response.json()
        assert payload["ok"] is True, endpoint
        assert payload["api_version"] == "v1", endpoint
        assert payload["kind"] == kind, endpoint

    post_endpoints = [
        (
            "/v1/settings",
            {"workspace": str(workspace), "settings": {"auto_scan_on_open": False}},
            "settings.updated",
            True,
        ),
        ("/v1/workspaces/scan", {"workspace": str(workspace)}, "workspace.scan", True),
        ("/v1/workspaces/roadmap", {"workspace": str(workspace)}, "workspace.roadmap", True),
        ("/v1/validation", {"workspace": str(workspace), "run": False}, "validation", True),
        (
            "/v1/clients/register",
            {
                "workspace": str(workspace),
                "client_id": "endpoint-family-client",
                "client_type": "test",
                "name": "Endpoint Family Test",
            },
            "client.registered",
            True,
        ),
        (
            "/v1/tasks",
            {
                "workspace": str(workspace),
                "title": "Endpoint family task",
                "kind": "test",
                "source_client": "pytest",
            },
            "task.created",
            True,
        ),
        ("/v1/agent/continue", {"workspace": str(workspace), "request": "continue safely"}, "agent.continue.plan", True),
        ("/v1/agent/repair", {"workspace": str(workspace)}, "agent.repair.plan", None),
    ]

    created_task_id = None
    for endpoint, body, kind, expected_ok in post_endpoints:
        response = client.post(endpoint, json=body)
        assert response.status_code == 200, endpoint
        payload = response.json()
        assert payload["api_version"] == "v1", endpoint
        assert payload["kind"] == kind, endpoint
        if expected_ok is not None:
            assert payload["ok"] is expected_ok, endpoint
        else:
            assert isinstance(payload["ok"], bool), endpoint
        if kind == "task.created":
            created_task_id = payload["data"]["id"]

    assert created_task_id
    status_response = client.post(
        f"/v1/tasks/{created_task_id}/status",
        json={"workspace": str(workspace), "status": "completed", "summary": "Endpoint family status updated"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["kind"] == "task.updated"
    assert status_response.json()["data"]["status"] == "completed"


def test_shared_mutation_apis_report_unwritable_memory_root(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")
    client = TestClient(create_app())

    registration = client.post(
        "/v1/clients/register",
        json={
            "workspace": str(workspace),
            "client_id": "unwritable-client",
            "client_type": "test",
            "name": "Unwritable Client",
        },
    )
    assert registration.status_code == 503
    assert "Could not persist client registration" in registration.json()["detail"]

    created = client.post(
        "/v1/tasks",
        json={
            "workspace": str(workspace),
            "title": "Should report persistence failure",
            "kind": "test",
        },
    )
    assert created.status_code == 503
    assert "Could not persist task" in created.json()["detail"]

    clients = client.get("/v1/clients", params={"workspace": str(workspace)})
    tasks = client.get("/v1/tasks", params={"workspace": str(workspace)})
    dashboard = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})

    assert clients.status_code == 200
    assert clients.json()["data"] == []
    assert tasks.status_code == 200
    assert tasks.json()["data"] == []
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["active_tasks"] == []


def test_client_listing_normalizes_malformed_client_records(tmp_path: Path) -> None:
    workspace = tmp_path / "malformed-client-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "clients.json").write_text(
        json.dumps(
            {
                "bad-value": "not-a-client",
                "missing-id": {"name": "Missing ID"},
                "client-a": {"client_id": " client-a ", "last_seen": 2, "capabilities": "scan"},
                "client-b": {"client_id": "client-b", "last_seen": "2020-01-01T00:00:00Z", "capabilities": [123, "scan", None, ""]},
            }
        ),
        encoding="utf-8",
    )

    clients = list_clients(workspace)

    assert {client["client_id"] for client in clients} == {"missing-id", "client-a", "client-b"}
    by_id = {client["client_id"]: client for client in clients}
    assert by_id["missing-id"]["name"] == "Missing ID"
    assert by_id["client-a"]["last_seen"] == "2"
    assert by_id["client-a"]["capabilities"] == []
    assert by_id["client-b"]["capabilities"] == ["123", "scan"]


def test_task_listing_normalizes_malformed_task_records(tmp_path: Path) -> None:
    workspace = tmp_path / "malformed-task-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "tasks.json").write_text(
        json.dumps(
            [
                {"id": "task-good", "title": "Good", "status": "running", "updated_at": 2, "metadata": "bad"},
                "not-a-task",
                {"title": "missing id"},
                {"id": "task-old", "updated_at": "2020-01-01T00:00:00Z"},
            ]
        ),
        encoding="utf-8",
    )

    tasks = list_tasks(workspace)

    assert [task["id"] for task in tasks] == ["task-old", "task-good"]
    by_id = {task["id"]: task for task in tasks}
    assert by_id["task-good"]["updated_at"] == "2"
    assert by_id["task-good"]["metadata"] == {}


def test_task_status_update_repairs_non_dict_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / "task-metadata-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "tasks.json").write_text(
        json.dumps([{"id": "task-1", "status": "running", "metadata": "bad"}]),
        encoding="utf-8",
    )

    task = update_task_status(workspace, "task-1", "completed", "fixed")

    assert task["status"] == "completed"
    assert task["metadata"]["summary"] == "fixed"


def test_safety_rules_are_case_insensitive_and_secret_aware(tmp_path: Path) -> None:
    assert is_ignored_path(tmp_path / "Node_Modules" / "package" / "index.js", tmp_path)
    assert is_ignored_path(tmp_path / "LIBRARY" / "metadata.json", tmp_path)
    assert is_secret_like(tmp_path / ".env.example")
    assert is_secret_like(tmp_path / "service-token.json")
    assert is_secret_like(tmp_path / "prod.password.txt")
    assert is_safe_to_read(tmp_path / "src" / "tokenizer.py", tmp_path)
    assert not is_safe_to_read(tmp_path / "Temp" / "cache.json", tmp_path)


def test_safety_blocks_paths_that_resolve_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")

    assert not is_safe_to_read(outside, workspace)
    assert not is_safe_to_edit(outside, workspace)


def test_workspace_scan_skips_file_symlink_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")
    link = workspace / "linked.py"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        return

    result = WorkspaceScanner(workspace).scan(persist=False)

    assert result["file_count"] == 0
    assert not is_safe_to_read(link, workspace)


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


def test_ollama_url_config_normalizes_common_local_values(tmp_path: Path) -> None:
    workspace = tmp_path / "ollama-url-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    config_path = aegis_dir / "config.json"

    config_path.write_text(json.dumps({"ollama_url": "127.0.0.1:11434/"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == "http://127.0.0.1:11434"

    config_path.write_text(json.dumps({"ollama_url": "http://127.0.0.1:11434/api/tags"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == "http://127.0.0.1:11434"

    config_path.write_text(json.dumps({"ollama_url": "not a url"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == AegisConfig.ollama_url

    config_path.write_text(json.dumps({"ollama_url": "ftp://127.0.0.1:11434"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == AegisConfig.ollama_url

    config_path.write_text(json.dumps({"ollama_url": "http://user:secret@127.0.0.1:11434"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == AegisConfig.ollama_url

    config_path.write_text(json.dumps({"ollama_url": "http://127.0.0.1:not-a-port"}), encoding="utf-8")
    assert load_config(workspace).ollama_url == AegisConfig.ollama_url


def test_ollama_health_handles_malformed_direct_url() -> None:
    status = OllamaClient(AegisConfig(ollama_url="not a url")).health()

    assert status.reachable is False
    assert status.selected_model is None
    assert AegisConfig.default_model in status.missing_models
    assert status.error


def test_ollama_model_listing_ignores_malformed_entries(monkeypatch) -> None:
    client = OllamaClient(AegisConfig())

    def malformed_entries(*args, **kwargs):
        return {
            "models": [
                {"name": " qwen3-coder:30b "},
                {"name": "granite-code:8b"},
                {"name": ""},
                {"name": 123},
                "not-a-model",
            ]
        }

    monkeypatch.setattr(client, "_request_json", malformed_entries)

    assert client.list_models() == ["granite-code:8b", "qwen3-coder:30b"]
    assert client.health().selected_model == "qwen3-coder:30b"


def test_ollama_health_handles_malformed_model_payload(monkeypatch) -> None:
    client = OllamaClient(AegisConfig())

    def malformed_payload(*args, **kwargs):
        return {"models": "not-a-list"}

    monkeypatch.setattr(client, "_request_json", malformed_payload)
    status = client.health()

    assert status.reachable is False
    assert status.selected_model is None
    assert AegisConfig.default_model in status.missing_models
    assert "models array" in (status.error or "")


def test_memory_dir_name_is_restricted_to_workspace_local_folder(tmp_path: Path) -> None:
    workspace = tmp_path / "memory-dir-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    config_path = aegis_dir / "config.json"
    unsafe_names = ("..", ".", "../outside", "nested/path", r"nested\path", r"C:\temp\aegis", "/tmp/aegis", "")

    for unsafe_name in unsafe_names:
        config_path.write_text(json.dumps({"memory_dir_name": unsafe_name}), encoding="utf-8")
        config = load_config(workspace)

        assert config.memory_dir_name == AegisConfig.memory_dir_name
        assert memory_dir(workspace, config) == workspace.resolve() / AegisConfig.memory_dir_name

    assert memory_dir(workspace, AegisConfig(memory_dir_name="../outside")) == workspace.resolve() / AegisConfig.memory_dir_name

    config_path.write_text(json.dumps({"memory_dir_name": ".aegis-local"}), encoding="utf-8")
    config = load_config(workspace)

    assert config.memory_dir_name == ".aegis-local"
    assert memory_dir(workspace, config) == workspace.resolve() / ".aegis-local"


def test_settings_api_sanitizes_memory_dir_name(tmp_path: Path) -> None:
    workspace = tmp_path / "settings-memory-dir-project"
    workspace.mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/settings",
        json={"workspace": str(workspace), "settings": {"memory_dir_name": "../outside"}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["memory_dir_name"] == AegisConfig.memory_dir_name
    config_path = workspace / ".aegis" / "config.json"
    assert json.loads(config_path.read_text(encoding="utf-8"))["memory_dir_name"] == AegisConfig.memory_dir_name


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


def test_validation_detection_ignores_project_files_in_ignored_folders(tmp_path: Path) -> None:
    workspace = tmp_path / "ignored-dotnet-project"
    workspace.mkdir()
    dependency_project = workspace / "node_modules" / "cached-package" / "Cached.csproj"
    dependency_project.parent.mkdir(parents=True)
    dependency_project.write_text("<Project />\n", encoding="utf-8")

    assert [item.name for item in detect_validation_commands(workspace)] == []

    app_project = workspace / "src" / "App.csproj"
    app_project.parent.mkdir()
    app_project.write_text("<Project />\n", encoding="utf-8")

    assert "dotnet build" in [item.name for item in detect_validation_commands(workspace)]


def test_validation_detection_ignores_damaged_root_build_markers(tmp_path: Path) -> None:
    workspace = tmp_path / "damaged-root-markers-project"
    workspace.mkdir()
    for name in ("Cargo.toml", "pyproject.toml", "requirements.txt", "CMakeLists.txt", "pnpm-lock.yaml", "yarn.lock"):
        (workspace / name).mkdir()

    assert [item.name for item in detect_validation_commands(workspace)] == []

    (workspace / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8")

    assert [item.name for item in detect_validation_commands(workspace)] == ["npm test"]


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


def test_validation_runner_detects_default_command_once(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "single-detect-validation-project"
    workspace.mkdir()
    calls = 0

    def detect_once(root):
        nonlocal calls
        calls += 1
        return [validation_module.ValidationCommand("python -m pytest", [sys.executable, "-m", "pytest"], "test")]

    def return_success(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(validation_module, "detect_validation_commands", detect_once)
    monkeypatch.setattr(validation_module.subprocess, "run", return_success)

    result = run_validation(workspace)

    assert result["ok"] is True
    assert calls == 1


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


def test_validation_runner_handles_oserror_start_failure(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "oserror-project"
    workspace.mkdir()

    def raise_oserror(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(validation_module.subprocess, "run", raise_oserror)
    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"])

    assert result["ok"] is False
    assert result["returncode"] is None
    assert result["start_failed"] is True
    assert "Validation command failed to start" in result["stderr"]


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


def test_continue_agent_survives_damaged_roadmap_path(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "roadmap.md").mkdir()

    client = TestClient(create_app())
    response = client.post("/v1/agent/continue", json={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan"]["mode"] == "plan-only"
    assert data["plan"]["approval_required"] is True
    assert data["task"]["status"] == "planned"


def test_continue_agent_survives_memory_root_file(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")

    client = TestClient(create_app())
    response = client.post("/v1/agent/continue", json={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert response.json()["ok"] is False
    assert data["plan"]["mode"] == "plan-only"
    assert data["task"] is None
    assert "Could not persist task" in data["memory_warning"]


def test_repair_agent_survives_damaged_validation_log_path(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "validation-log.md").mkdir()

    client = TestClient(create_app())
    response = client.post("/v1/agent/repair", json={"workspace": str(workspace)})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["data"]["plan"]["approval_required"] is True
    assert "No validation log" in response.json()["data"]["plan"]["message"]


def test_repair_agent_redacts_validation_excerpt(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "validation-log.md").write_text(
        "normal failure\nAPI_TOKEN=abc123\nAuthorization: Bearer abc123\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post("/v1/agent/repair", json={"workspace": str(workspace)})

    assert response.status_code == 200
    excerpt = response.json()["data"]["plan"]["latest_validation_excerpt"]
    assert "normal failure" in excerpt
    assert "[redacted secret-like log line]" in excerpt
    assert "abc123" not in excerpt
