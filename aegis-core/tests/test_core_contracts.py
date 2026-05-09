from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import aegis_core.model_router as model_router_module
import aegis_core.validation as validation_module
from aegis_core.clients import list_clients
from aegis_core.config import AegisConfig, ConfigPersistenceError, load_config, memory_dir, update_config, write_default_config
from aegis_core.contracts import (
    CORE_CONTRACT_VERSION,
    CONTRACTS,
    PatchProposalData,
    RollbackEntryData,
    RollbackResultData,
    make_envelope,
    model_dump,
    validate_contract_envelope,
)
from aegis_core.credentials import CredentialStore, CredentialStoreError
from aegis_core.diagnostics import redact_inline, scrub
from aegis_core.memory import ProjectMemory
from aegis_core.model_router import provider_inventory, route_model
from aegis_core.ollama import OllamaClient, OllamaStatus
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


def assert_core_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.api_version == "v1"
    assert envelope.contract_version == CORE_CONTRACT_VERSION
    assert envelope.kind == kind
    assert envelope.stability in {"stable", "experimental", "deprecated"}
    assert isinstance(envelope.deprecations, list)
    assert envelope.deprecated is (envelope.stability == "deprecated")


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


def test_cli_roadmap_reports_persistence_failure_without_traceback(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "roadmap.md").mkdir()
    core_root = Path(__file__).resolve().parents[1]

    completed = run_cli_raw(core_root, "--json", "roadmap", "--workspace", str(workspace))

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "roadmap"
    assert "Could not persist roadmap" in payload["error"]
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
    assert_core_contract(registration.json(), "client.registered")
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
    assert_core_contract(created.json(), "task.created")
    task_id = created.json()["data"]["id"]

    dashboard = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})
    assert dashboard.status_code == 200
    assert_core_contract(dashboard.json(), "ecosystem.dashboard")
    data = dashboard.json()["data"]
    assert any(item["client_id"] == "contract-test-client" for item in data["clients"])
    assert any(item["id"] == task_id for item in data["active_tasks"])

    updated = client.post(
        f"/v1/tasks/{task_id}/status",
        json={"workspace": str(workspace), "status": "completed", "summary": "contract passed"},
    )
    assert updated.status_code == 200
    assert_core_contract(updated.json(), "task.updated")
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
        ("/v1/agents", {}, "agents.roster"),
        ("/v1/orchestration", {"workspace": str(workspace)}, "orchestration.dashboard"),
        ("/v1/jobs", {"workspace": str(workspace)}, "jobs.dashboard"),
        ("/v1/quality", {"workspace": str(workspace)}, "quality.dashboard"),
        ("/v1/knowledge/graph", {"workspace": str(workspace)}, "knowledge.graph"),
        ("/v1/operations", {"workspace": str(workspace)}, "operations.dashboard"),
        ("/v1/personal-intelligence", {"workspace": str(workspace)}, "personal.intelligence"),
        ("/v1/ecosystem/dashboard", {"workspace": str(workspace)}, "ecosystem.dashboard"),
    ]

    for endpoint, params, kind in get_endpoints:
        response = client.get(endpoint, params=params)
        assert response.status_code == 200, endpoint
        payload = response.json()
        assert payload["ok"] is True, endpoint
        assert payload["api_version"] == "v1", endpoint
        assert payload["contract_version"] == CORE_CONTRACT_VERSION, endpoint
        assert payload["deprecated"] is False, endpoint
        assert payload["deprecations"] == [], endpoint
        assert payload["kind"] == kind, endpoint
        assert_core_contract(payload, kind)

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
        (
            "/v1/orchestration/plan",
            {"workspace": str(workspace), "goal": "Stabilize one safe workflow", "source_client": "pytest"},
            "orchestration.plan",
            True,
        ),
        (
            "/v1/jobs/run",
            {"workspace": str(workspace), "job_id": "validation-status-check"},
            "jobs.run",
            True,
        ),
        ("/v1/quality/snapshot", {"workspace": str(workspace)}, "quality.snapshot", True),
        ("/v1/knowledge/graph", {"workspace": str(workspace)}, "knowledge.graph", True),
        (
            "/v1/knowledge/query",
            {"workspace": str(workspace), "query": "What areas of the project are most unstable?"},
            "knowledge.query",
            True,
        ),
        (
            "/v1/simulation/change",
            {
                "workspace": str(workspace),
                "objective": "Safely update README.md validation notes",
                "files": ["README.md"],
                "approach": "Minimal documentation update",
            },
            "simulation.change",
            True,
        ),
        (
            "/v1/simulation/compare",
            {
                "workspace": str(workspace),
                "objective": "Improve validation workflow without broad rewrites",
                "approaches": ["Minimal adapter and focused test", "Large rewrite of validation runtime"],
            },
            "simulation.compare",
            True,
        ),
        (
            "/v1/operations/dashboard",
            {"workspace": str(workspace), "project_roots": []},
            "operations.dashboard",
            True,
        ),
        (
            "/v1/personal-intelligence/profile",
            {"workspace": str(workspace), "project_roots": [], "preferences": {"planning_depth": "balanced"}},
            "personal.intelligence",
            True,
        ),
        ("/v1/personal-intelligence/reset", {"workspace": str(workspace)}, "personal.intelligence.reset", True),
    ]

    created_task_id = None
    for endpoint, body, kind, expected_ok in post_endpoints:
        response = client.post(endpoint, json=body)
        assert response.status_code == 200, endpoint
        payload = response.json()
        assert payload["api_version"] == "v1", endpoint
        assert payload["contract_version"] == CORE_CONTRACT_VERSION, endpoint
        assert payload["kind"] == kind, endpoint
        assert_core_contract(payload, kind)
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
    assert_core_contract(status_response.json(), "task.updated")
    assert status_response.json()["kind"] == "task.updated"
    assert status_response.json()["data"]["status"] == "completed"


def test_contract_catalog_covers_unified_phase_runtime_shapes() -> None:
    required = {
        "health",
        "models",
        "settings",
        "workspace.scan",
        "workspace.roadmap",
        "memory.summary",
        "diagnostics.summary",
        "task.created",
        "tasks.list",
        "validation",
        "agent.continue.plan",
        "agent.repair.plan",
        "agents.roster",
        "orchestration.plan",
        "orchestration.dashboard",
        "orchestration.step",
        "jobs.dashboard",
        "jobs.run",
        "quality.dashboard",
        "quality.snapshot",
        "knowledge.graph",
        "knowledge.query",
        "simulation.change",
        "simulation.compare",
        "operations.dashboard",
        "personal.intelligence",
        "personal.intelligence.reset",
        "patch.proposal",
        "rollback.entry",
        "rollback.result",
    }

    assert required.issubset(CONTRACTS)
    assert CONTRACTS["patch.proposal"].stability == "experimental"
    assert CONTRACTS["rollback.result"].owner == "schema-only"


def test_schema_only_patch_and_rollback_contracts_validate() -> None:
    patch = PatchProposalData(
        id="proposal-1",
        workspace="C:/workspace",
        summary="Update one file",
        files=[{"path": "src/example.py", "action": "update", "summary": "Small compatibility change"}],
    )
    rollback = RollbackEntryData(
        id="rollback-1",
        workspace="C:/workspace",
        checkpoint_path=".aegis/checkpoints/rollback-1",
        files=["src/example.py"],
    )
    rollback_result = RollbackResultData(ok=True, workspace="C:/workspace", rollback_id="rollback-1", restored_files=["src/example.py"])

    assert validate_contract_envelope(make_envelope("patch.proposal", model_dump(patch), "C:/workspace")).kind == "patch.proposal"
    assert validate_contract_envelope(make_envelope("rollback.entry", model_dump(rollback), "C:/workspace")).kind == "rollback.entry"
    assert validate_contract_envelope(make_envelope("rollback.result", model_dump(rollback_result), "C:/workspace")).kind == "rollback.result"


def test_specialized_agent_roster_contract_lists_safe_roles() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/agents")

    assert response.status_code == 200
    assert_core_contract(response.json(), "agents.roster")
    data = response.json()["data"]
    agent_ids = [agent["id"] for agent in data["agents"]]
    assert agent_ids == ["planner", "architect", "coder", "reviewer", "tester", "repair", "documentation"]
    coder = next(agent for agent in data["agents"] if agent["id"] == "coder")
    tester = next(agent for agent in data["agents"] if agent["id"] == "tester")
    assert "file_edit" in coder["approval_gates"]
    assert "build_command" in tester["approval_gates"]
    assert "Agents may propose changes, but file edits require approval." in data["coordination_rules"]


def test_jobs_dashboard_lists_scheduled_and_triggered_maintenance(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/jobs", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "jobs.dashboard")
    data = response.json()["data"]
    job_ids = {job["id"] for job in data["scheduled_jobs"]}
    assert {
        "daily-project-scan",
        "weekly-roadmap-update",
        "dependency-review",
        "build-health-check",
        "stale-todo-scan",
        "documentation-drift-check",
    }.issubset(job_ids)
    assert any(job["id"] == "daily-project-scan" for job in data["due_jobs"])
    assert "build_command" in {gate["id"] for gate in data["approval_rules"]["approval_required_for"]}
    assert any(trigger["id"] == "project_opened" for trigger in data["triggers"])


def test_safe_job_run_writes_jobs_log_and_scan_artifacts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "daily-project-scan"},
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "jobs.run")
    result = response.json()["data"]["results"][0]
    assert result["id"] == "daily-project-scan"
    assert result["status"] == "completed"
    assert result["approval_required"] is False
    assert (workspace / ".aegis" / "jobs-log.md").is_file()
    assert "Daily Project Scan" in (workspace / ".aegis" / "jobs-log.md").read_text(encoding="utf-8")
    assert (workspace / ".aegis" / "project-summary.md").is_file()


def test_job_run_reports_state_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "jobs-state.json").mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "daily-project-scan"},
    )

    assert response.status_code == 503
    assert "Could not persist maintenance job state" in response.json()["detail"]


def test_job_run_warns_when_jobs_log_cannot_be_written(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "jobs-log.md").mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "daily-project-scan"},
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert any("Could not write jobs log" in warning for warning in result["warnings"])
    state = json.loads((workspace / ".aegis" / "jobs-state.json").read_text(encoding="utf-8"))
    assert any("Could not write jobs log" in warning for warning in state["jobs"]["daily-project-scan"]["warnings"])


def test_build_health_job_requires_approval_before_validation(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    calls: list[Path] = []

    def fake_validation(root, command=None):
        calls.append(Path(root))
        return {"ok": True, "command": ["npm", "test"], "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr("aegis_core.jobs.run_validation", fake_validation)

    blocked = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "build-health-check"},
    )
    assert blocked.status_code == 200
    blocked_result = blocked.json()["data"]["results"][0]
    assert blocked_result["status"] == "needs_approval"
    assert blocked_result["approval_required"] is True
    assert "build_command" in {gate["id"] for gate in blocked_result["approval_gates"]}
    assert calls == []

    approved = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "build-health-check", "approval": True},
    )
    assert approved.status_code == 200
    approved_result = approved.json()["data"]["results"][0]
    assert approved_result["status"] == "completed"
    assert calls == [workspace.resolve()]


def test_triggered_jobs_run_project_opened_safe_workflows(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "trigger": "project_opened"},
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "jobs.run")
    data = response.json()["data"]
    result_ids = {result["id"] for result in data["results"]}
    assert {"daily-project-scan", "stale-todo-scan", "project-health-report", "next-best-task"}.issubset(result_ids)
    assert data["trigger"] == "project_opened"
    assert (workspace / ".aegis" / "jobs-log.md").is_file()


def test_due_jobs_run_scheduled_workflows_without_risky_command_approval(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "run_due": True},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["run_due"] is True
    by_id = {result["id"]: result for result in data["results"]}
    assert by_id["daily-project-scan"]["status"] == "completed"
    assert by_id["build-health-check"]["status"] == "needs_approval"
    assert by_id["build-health-check"]["approval_required"] is True
    assert (workspace / ".aegis" / "jobs-state.json").is_file()


def test_broken_references_job_reports_missing_markdown_targets(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / "docs.md").write_text("[Missing](missing-file.md)\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "broken-references-check"},
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert result["status"] == "completed"
    assert result["metrics"]["broken_references"][0]["target"] == "missing-file.md"


def test_quality_dashboard_reports_score_risks_and_statuses(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".aegis").mkdir(exist_ok=True)
    (workspace / ".aegis" / "validation-log.md").write_text(
        "## 2026-05-09T00:00:00Z - failed\n\nCommand: `npm test`\n\n```text\nsrc/app.ts: failed assertion\n```\n\n",
        encoding="utf-8",
    )
    (workspace / "src").mkdir()
    (workspace / "src" / "app.ts").write_text("export function run() {\n  // FIXME: broken path\n}\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/v1/quality", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "quality.dashboard")
    data = response.json()["data"]
    assert data["score"] < 100
    assert data["statuses"]["test"]["status"] == "failed"
    assert "validation" in data["failing_systems"]
    assert any(item["path"].endswith("src/app.ts") for item in data["high_risk_files"])
    assert data["recommended_next_improvement"]


def test_quality_dashboard_does_not_record_history_without_snapshot(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/quality", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "quality.dashboard")
    assert not (workspace / ".aegis" / "health-history.json").exists()
    assert not (workspace / ".aegis" / "daily-health-report.md").exists()


def test_quality_snapshot_records_history_and_reports(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post("/v1/quality/snapshot", json={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "quality.snapshot")
    data = response.json()["data"]
    assert (workspace / ".aegis" / "health-history.json").is_file()
    assert (workspace / ".aegis" / "daily-health-report.md").is_file()
    assert (workspace / ".aegis" / "weekly-quality-summary.md").is_file()
    history = json.loads((workspace / ".aegis" / "health-history.json").read_text(encoding="utf-8"))
    assert history[-1]["score"] == data["score"]
    assert data["report_paths"]["daily_health_report"].endswith("daily-health-report.md")


def test_quality_snapshot_reports_history_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "health-history.json").mkdir()
    client = TestClient(create_app())

    response = client.post("/v1/quality/snapshot", json={"workspace": str(workspace)})

    assert response.status_code == 503
    assert "Could not persist quality health history" in response.json()["detail"]
    assert not (workspace / ".aegis" / "daily-health-report.md").exists()


def test_quality_trend_detects_degrading_snapshot(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    first = client.post("/v1/quality/snapshot", json={"workspace": str(workspace)})
    assert first.status_code == 200
    for index in range(20):
        (workspace / f"todo_{index}.py").write_text(f"# TODO: cleanup {index}\n", encoding="utf-8")
    second = client.post("/v1/quality/snapshot", json={"workspace": str(workspace)})

    assert second.status_code == 200
    trend = second.json()["data"]["trend"]
    assert trend["direction"] in {"degrading", "stable"}
    assert trend["score_delta"] <= 0


def test_quality_job_records_snapshot_and_reports(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "quality-intelligence-snapshot"},
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert result["id"] == "quality-intelligence-snapshot"
    assert result["status"] == "completed"
    assert "score" in result["metrics"]
    assert (workspace / ".aegis" / "health-history.json").is_file()


def test_quality_job_reports_history_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "health-history.json").mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/jobs/run",
        json={"workspace": str(workspace), "job_id": "quality-intelligence-snapshot"},
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert result["status"] == "failed"
    assert any("Could not persist quality health history" in warning for warning in result["warnings"])


def test_knowledge_graph_links_files_apis_docs_and_validation(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    src.mkdir()
    (src / "service.py").write_text(
        "class ItemService:\n    def list_items(self):\n        return []\n",
        encoding="utf-8",
    )
    (src / "api.py").write_text(
        "from fastapi import FastAPI\nfrom .service import ItemService\napp = FastAPI()\n@app.get('/v1/items')\ndef list_items():\n    return ItemService().list_items()\n",
        encoding="utf-8",
    )
    (src / "ui.tsx").write_text(
        "export function ItemsPanel() {\n  fetch('/v1/items');\n  return null;\n}\n",
        encoding="utf-8",
    )
    tests = workspace / "tests"
    tests.mkdir()
    (tests / "test_service.py").write_text("from src.service import ItemService\n", encoding="utf-8")
    (workspace / ".aegis").mkdir(exist_ok=True)
    (workspace / ".aegis" / "roadmap.md").write_text("- Build item API workflow for ItemsPanel\n", encoding="utf-8")
    (workspace / ".aegis" / "decisions.md").write_text("## API Boundary\n\n- What changed: ItemService backs the item API.\n", encoding="utf-8")
    (workspace / ".aegis" / "known-issues.md").write_text("- bug: /v1/items fails when src/api.py changes\n", encoding="utf-8")
    (workspace / ".aegis" / "validation-log.md").write_text(
        "## 2026-05-09T00:00:00Z - failed\n\nCommand: `pytest`\n\n```text\nsrc/api.py: failed\n```\n",
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "knowledge.graph")
    data = response.json()["data"]
    node_ids = {node["id"] for node in data["nodes"]}
    edge_types = {(edge["source"], edge["target"], edge["type"]) for edge in data["edges"]}
    assert "file:src/api.py" in node_ids
    assert "api:get:/v1/items" in node_ids
    assert any(source == "file:src/api.py" and target == "file:src/service.py" and edge_type == "uses" for source, target, edge_type in edge_types)
    assert any(target == "api:get:/v1/items" and edge_type == "implements" for _, target, edge_type in edge_types)
    assert any(edge_type == "mentioned_in_roadmap" for _, _, edge_type in edge_types)
    assert any(edge_type == "breaks" for _, _, edge_type in edge_types)
    assert (workspace / ".aegis" / "knowledge-graph.json").is_file()
    assert (workspace / ".aegis" / "knowledge-summary.md").is_file()


def test_knowledge_graph_reports_graph_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "knowledge-graph.json").mkdir()
    client = TestClient(create_app())

    response = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    assert response.status_code == 503
    assert "Could not persist knowledge graph" in response.json()["detail"]
    assert not (aegis_dir / "knowledge-graph.json").is_file()
    assert not (aegis_dir / "knowledge-summary.md").exists()


def test_knowledge_graph_reports_summary_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "knowledge-summary.md").mkdir()
    client = TestClient(create_app())

    response = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    assert response.status_code == 503
    assert "Could not persist knowledge graph" in response.json()["detail"]
    assert not (aegis_dir / "knowledge-graph.json").exists()


def test_knowledge_graph_get_is_read_only(tmp_path: Path) -> None:
    workspace = tmp_path / "knowledge-readonly"
    workspace.mkdir()
    (workspace / "src.py").write_text("def run():\n    return True\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/v1/knowledge/graph", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "knowledge.graph")
    assert not (workspace / ".aegis").exists()


def test_knowledge_query_answers_dependents_and_unstable_modules(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    src.mkdir()
    (src / "service.py").write_text("class ItemService:\n    pass\n", encoding="utf-8")
    (src / "api.py").write_text("from .service import ItemService\n", encoding="utf-8")
    (workspace / ".aegis").mkdir(exist_ok=True)
    (workspace / ".aegis" / "validation-log.md").write_text(
        "## 2026-05-09T00:00:00Z - failed\n\nCommand: `pytest`\n\n```text\nsrc/service.py: failed\n```\n",
        encoding="utf-8",
    )
    client = TestClient(create_app())
    client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    dependents = client.post(
        "/v1/knowledge/query",
        json={"workspace": str(workspace), "query": "What systems depend on this file?", "focus": "src/service.py"},
    )
    unstable = client.post(
        "/v1/knowledge/query",
        json={"workspace": str(workspace), "query": "What areas of the project are most unstable?"},
    )

    assert dependents.status_code == 200
    assert_core_contract(dependents.json(), "knowledge.query")
    assert any(answer["title"] == "src/api.py" for answer in dependents.json()["data"]["answers"])
    assert unstable.status_code == 200
    assert_core_contract(unstable.json(), "knowledge.query")
    assert unstable.json()["data"]["answers"]


def test_change_simulation_forecasts_risk_and_impact(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    src.mkdir()
    (src / "service.py").write_text(
        "class ItemService:\n    def list_items(self):\n        return []\n",
        encoding="utf-8",
    )
    (src / "api.py").write_text("from .service import ItemService\n", encoding="utf-8")
    tests = workspace / "tests"
    tests.mkdir()
    (tests / "test_service.py").write_text("from src.service import ItemService\n", encoding="utf-8")
    append_validation_log(
        workspace,
        {
            "ok": False,
            "command": ["python", "-m", "pytest"],
            "stderr": "src/service.py: failed: ItemService regression",
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/v1/simulation/change",
        json={
            "workspace": str(workspace),
            "objective": "Refactor src/service.py while preserving API behavior",
            "files": ["src/service.py"],
            "approach": "Minimal adapter and focused test-first fix",
        },
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "simulation.change")
    data = response.json()["data"]
    assert data["focus_files"] == ["src/service.py"]
    assert data["risk_level"] in {"moderate", "high", "dangerous_architectural_change"}
    assert data["confidence"] >= 60
    assert any(item["path"] == "src/service.py" for item in data["impacted_files"])
    assert data["dependency_ripple"]["summary"]
    assert data["roadmap_forecast"]["implementation_difficulty"] in {"moderate", "hard", "very_hard"}
    assert data["ui"]["predicted_impact"]
    assert data["rollback_complexity"]["checkpoint_required"] is True


def test_simulation_compare_ranks_incremental_approach_over_rewrite(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    src.mkdir()
    (src / "service.py").write_text("class PlannerService:\n    pass\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/simulation/compare",
        json={
            "workspace": str(workspace),
            "objective": "Improve src/service.py planning behavior safely",
            "files": ["src/service.py"],
            "approaches": [
                "Minimal adapter with focused validation",
                "Large rewrite and replace the planning architecture",
            ],
        },
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "simulation.compare")
    data = response.json()["data"]
    assert data["recommended_approach"] == "Minimal adapter with focused validation"
    simulations = {item["approach"]: item for item in data["simulations"]}
    assert simulations["Large rewrite and replace the planning architecture"]["risk_score"] >= simulations["Minimal adapter with focused validation"]["risk_score"]
    assert data["comparison"][0]["approach"] == "Minimal adapter with focused validation"


def test_operations_dashboard_coordinates_release_debt_and_lifecycle(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    src.mkdir()
    for index in range(12):
        (src / f"module_{index}.py").write_text(
            f"def run_{index}():\n    return {index}\n# FIXME quick fix: stabilize this path\n",
            encoding="utf-8",
        )
    append_validation_log(
        workspace,
        {
            "ok": False,
            "command": ["python", "-m", "pytest"],
            "stderr": "src/module_1.py: failed validation",
        },
    )
    (workspace / ".aegis" / "agent-history.json").write_text(
        json.dumps(
            [
                {"event": "repair_attempt", "agent_id": "repair", "summary": "temporary workaround"},
                {"event": "repair_attempt", "agent_id": "repair", "summary": "quick fix follow-up"},
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.get("/v1/operations", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "operations.dashboard")
    data = response.json()["data"]
    assert data["lifecycle"]["stage"] in {"prototype", "active_development", "stabilization", "release_candidate", "maintenance_mode"}
    assert data["release_readiness"]["status"] in {"blocked", "not_ready", "nearly_ready", "ready"}
    assert data["release_plan"]["milestones"]
    assert data["release_plan"]["validation_checkpoints"]
    assert data["technical_debt"]["signals"]
    assert data["technical_debt"]["cleanup_recommendations"]
    assert data["task_coordination"]["validation_tasks"]
    assert data["maintenance_schedule"]["validation_sweeps"]
    assert data["productivity_intelligence"]["automation_opportunities"]
    assert data["operations_dashboard"]["next_action"]
    assert data["approval_policy"]["uncontrolled_autonomy"] is False


def test_operations_dashboard_surfaces_cross_project_awareness(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    other = tmp_path / "other-project"
    other.mkdir()
    (other / "README.md").write_text("# Other Project\n", encoding="utf-8")
    (other / "package.json").write_text(
        json.dumps({"scripts": {"test": "node smoke.js"}, "dependencies": {"vite": "^7.0.0", "react": "^19.0.0"}}, indent=2),
        encoding="utf-8",
    )
    (other / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/operations/dashboard",
        json={
            "workspace": str(workspace),
            "project_roots": [str(other), str(tmp_path / "missing-project")],
        },
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "operations.dashboard")
    cross_project = response.json()["data"]["cross_project_awareness"]
    assert len(cross_project["projects"]) == 2
    assert cross_project["unavailable_projects"]
    assert "Vite" in cross_project["shared_tooling"]
    assert cross_project["coordination_notes"]


def test_personal_intelligence_learns_style_preferences_and_resets_profile(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    src = workspace / "src"
    components = src / "components"
    services = src / "services"
    api = src / "api"
    components.mkdir(parents=True)
    services.mkdir(parents=True)
    api.mkdir(parents=True)
    (services / "ProjectService.ts").write_text(
        "export class ProjectService {\n"
        "  loadProject(id: string) {\n"
        "    if (!id) return null;\n"
        "    return { id };\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (components / "DashboardPanel.tsx").write_text(
        "export function DashboardPanel() {\n"
        "  return <section className=\"panel\">Ready</section>;\n"
        "}\n",
        encoding="utf-8",
    )
    (api / "routes.ts").write_text("export const route = '/v1/projects';\n", encoding="utf-8")
    ProjectMemory(workspace).append_decision("Use approval-gated small tasks for stabilization.", affected_files=["src/services/ProjectService.ts"])
    client = TestClient(create_app())

    readonly = client.get("/v1/personal-intelligence", params={"workspace": str(workspace)})

    assert readonly.status_code == 200
    assert_core_contract(readonly.json(), "personal.intelligence")
    assert readonly.json()["data"]["preference_memory"]["persisted"] is False

    response = client.post(
        "/v1/personal-intelligence/profile",
        json={
            "workspace": str(workspace),
            "preferences": {
                "planning_depth": "deep",
                "validation_detail": "detailed",
                "keyboard_layout": "default",
                "preferred_models": {"local": "qwen2.5-coder"},
                "api_key": "should-not-be-stored",
            },
            "persist": True,
        },
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "personal.intelligence")
    data = response.json()["data"]
    preferences = data["preference_memory"]["stored_preferences"]
    assert preferences["planning_depth"] == "deep"
    assert preferences["validation_detail"] == "detailed"
    assert preferences["keyboard_layout"] == "default"
    assert preferences["preferred_models"]["local"] == "qwen2.5-coder"
    assert "api_key" not in preferences
    assert data["learned_signals"]["preferred_frameworks"]
    assert data["coding_style_awareness"]["formatting_tendencies"]["indentation"] in {"spaces", "tabs", "mixed"}
    assert data["context_personalization"]["planning_depth"] == "deep"
    assert data["privacy"]["local_first"] is True
    profile_path = Path(data["preference_memory"]["profile_path"])
    assert profile_path.exists()
    assert "should-not-be-stored" not in profile_path.read_text(encoding="utf-8")

    reset = client.post("/v1/personal-intelligence/reset", json={"workspace": str(workspace)})

    assert reset.status_code == 200
    assert_core_contract(reset.json(), "personal.intelligence.reset")
    assert reset.json()["data"]["reset"] is True
    assert not profile_path.exists()


def test_personal_intelligence_reports_profile_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "personal-engineering-profile.json").mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/personal-intelligence/profile",
        json={"workspace": str(workspace), "preferences": {"planning_depth": "deep"}, "persist": True},
    )

    assert response.status_code == 503
    assert "Could not persist personal engineering profile" in response.json()["detail"]
    assert not (aegis_dir / "personal-engineering-profile.json").is_file()


def test_personal_intelligence_reset_reports_damaged_profile_path(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    profile_path = aegis_dir / "personal-engineering-profile.json"
    profile_path.mkdir()
    client = TestClient(create_app())

    response = client.post("/v1/personal-intelligence/reset", json={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_core_contract(response.json(), "personal.intelligence.reset")
    assert response.json()["ok"] is False
    assert response.json()["data"]["reset"] is False
    assert "Could not reset personal engineering profile" in response.json()["data"]["error"]
    assert profile_path.is_dir()


def test_personal_intelligence_surfaces_cross_project_patterns(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    other = tmp_path / "other-pattern-project"
    other.mkdir()
    for root in (workspace, other):
        (root / "src" / "auth").mkdir(parents=True, exist_ok=True)
        (root / "src" / "api").mkdir(parents=True, exist_ok=True)
        (root / "tests").mkdir(exist_ok=True)
        (root / "src" / "auth" / "LoginService.ts").write_text(
            "export class LoginService {\n  signIn(user: string) { return Boolean(user); }\n}\n",
            encoding="utf-8",
        )
        (root / "src" / "api" / "client.ts").write_text("export const clientRoute = '/api/login';\n", encoding="utf-8")
        (root / "tests" / "login.test.ts").write_text("test('login', () => expect(true).toBe(true));\n", encoding="utf-8")
    (other / "README.md").write_text("# Other Pattern Project\n", encoding="utf-8")
    (other / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest"}, "dependencies": {"vite": "^7.0.0", "react": "^19.0.0"}}, indent=2),
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.post(
        "/v1/personal-intelligence/profile",
        json={"workspace": str(workspace), "project_roots": [str(other), str(tmp_path / "missing")]},
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "personal.intelligence")
    patterns = response.json()["data"]["project_pattern_recognition"]
    system_names = {item["system"] for item in patterns["recurring_systems"]}
    assert {"auth", "api", "validation"}.intersection(system_names)
    assert len(patterns["projects_analyzed"]) == 2
    assert patterns["unavailable_projects"]
    assert patterns["suggested_templates"]


def test_roadmap_endpoint_reports_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    roadmap_path = aegis_dir / "roadmap.md"
    roadmap_path.mkdir()
    client = TestClient(create_app())

    response = client.post("/v1/workspaces/roadmap", json={"workspace": str(workspace)})

    assert response.status_code == 503
    assert "Could not persist roadmap" in response.json()["detail"]
    assert roadmap_path.is_dir()


def test_known_client_contract_parsing_tolerates_missing_optional_fields() -> None:
    desktop_dashboard = make_envelope("ecosystem.dashboard", {}, "C:/workspace")
    vscode_task = make_envelope("task.created", {"id": "task-compat"}, "C:/workspace")
    visual_studio_health = make_envelope("health", {}, "C:/workspace")

    assert_core_contract(desktop_dashboard, "ecosystem.dashboard")
    assert_core_contract(vscode_task, "task.created")
    assert_core_contract(visual_studio_health, "health")

    dashboard_data = desktop_dashboard.get("data") if isinstance(desktop_dashboard.get("data"), dict) else {}
    assert len(dashboard_data.get("clients") or []) == 0
    assert len(dashboard_data.get("active_tasks") or []) == 0
    assert (vscode_task.get("data") or {}).get("id") == "task-compat"
    assert visual_studio_health["ok"] is True


def test_v1_invalid_requests_return_useful_errors(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    missing_workspace = client.post("/v1/workspaces/scan", json={})
    assert missing_workspace.status_code == 422
    assert "detail" in missing_workspace.json()

    missing_task = client.post("/v1/tasks/task-missing/status", json={"workspace": str(workspace), "status": "completed"})
    assert missing_task.status_code == 404
    assert "Task not found" in missing_task.json()["detail"]

    bad_status = client.post("/v1/tasks/task-missing/status", json={"workspace": str(workspace), "status": "made-up-status"})
    assert bad_status.status_code == 400
    assert "Unsupported task status" in bad_status.json()["detail"]


def test_v1_known_client_contracts_match_desktop_vscode_and_visual_studio(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    desktop_registration = client.post(
        "/v1/clients/register",
        json={
            "workspace": str(workspace),
            "client_id": "auralith-desktop",
            "client_type": "desktop-app",
            "name": "Auralith Desktop",
            "version": "0.1.0",
            "capabilities": ["ecosystem-dashboard", "memory-browser", "workflow-orchestration"],
        },
    )
    assert desktop_registration.status_code == 200

    vscode_health = client.get("/v1/health", params={"workspace": str(workspace)})
    assert vscode_health.status_code == 200
    assert vscode_health.json()["kind"] == "health"

    vscode_registration = client.post(
        "/v1/clients/register",
        json={
            "workspace": str(workspace),
            "client_id": "aegis-vscode",
            "client_type": "vscode-extension",
            "name": "Aegis Local Agent for VS Code",
            "version": "0.1.1",
            "capabilities": ["workspace-scan", "diff-preview"],
        },
    )
    assert vscode_registration.status_code == 200

    vscode_task = client.post(
        "/v1/tasks",
        json={
            "workspace": str(workspace),
            "title": "VS Code proposal",
            "kind": "vscode-agent",
            "source_client": "vscode-extension",
            "request": "Draft a safe proposal",
            "metadata": {"command": "aegisLocalAutopilot.runAgentMode"},
        },
    )
    assert vscode_task.status_code == 200
    task_id = vscode_task.json()["data"]["id"]

    waiting = client.post(
        f"/v1/tasks/{task_id}/status",
        json={"workspace": str(workspace), "status": "waiting_for_approval", "summary": "Proposal ready."},
    )
    assert waiting.status_code == 200
    assert waiting.json()["data"]["status"] == "waiting_for_approval"

    visual_studio_registration = client.post(
        "/v1/clients/register",
        json={
            "workspace": str(workspace),
            "client_id": "aegis-visual-studio",
            "client_type": "visual-studio-extension",
            "name": "Aegis Local Agent for Visual Studio",
            "version": "0.1.1",
            "capabilities": ["solution-scan", "build-validation"],
        },
    )
    assert visual_studio_registration.status_code == 200

    dashboard = client.get("/v1/ecosystem/dashboard", params={"workspace": str(workspace)})
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    client_ids = {item["client_id"] for item in data["clients"]}
    assert {"auralith-desktop", "aegis-vscode", "aegis-visual-studio"}.issubset(client_ids)
    assert any(item["id"] == task_id for item in data["active_tasks"])


def test_orchestration_plan_creates_safe_queue_and_memory(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/orchestration/plan",
        json={
            "workspace": str(workspace),
            "goal": "Install package, remove dead code, and use OpenAI only if approved",
            "source_client": "pytest",
            "context_files": ["README.md", ".env"],
        },
    )

    assert response.status_code == 200
    assert_core_contract(response.json(), "orchestration.plan")
    data = response.json()["data"]
    assert data["current_goal"].startswith("Install package")
    assert data["plan"]["risk"] == "high"
    assert data["plan"]["quality"]["score"] <= 100
    assert data["plan"]["quality"]["top_risks"]
    assert data["plan"]["knowledge"]["node_count"] > 0
    assert data["plan"]["simulation"]["risk_level"] in {"high", "dangerous_architectural_change"}
    assert data["plan"]["simulation"]["split_recommended"] is True
    assert data["plan"]["planner_guidance"]
    assert data["task_list"][0]["status"] == "in_progress"
    assert data["task_list"][0]["active_step"] == "inspect"
    assert len(data["task_list"]) == 8
    assert data["active_agent"]["id"] == "planner"
    assert [task["owner_agent"] for task in data["task_list"]] == [
        "planner",
        "architect",
        "planner",
        "coder",
        "reviewer",
        "tester",
        "repair",
        "documentation",
    ]
    assert len(data["agent_pipeline"]) == 7
    gate_ids = {gate["id"] for gate in data["plan"]["approval_gates"]}
    assert {"file_edit", "file_delete", "build_command", "install_package", "cloud_context"}.issubset(gate_ids)
    assert data["plan"]["blocked_context"][0]["path"] == ".env"
    assert (workspace / ".aegis" / "orchestration-queue.json").is_file()
    assert "Active Orchestration" in (workspace / ".aegis" / "roadmap.md").read_text(encoding="utf-8")
    history = json.loads((workspace / ".aegis" / "agent-history.json").read_text(encoding="utf-8"))
    assert any(item.get("event") == "orchestration_created" for item in history)
    assert any(item.get("event") == "agent_decision" and item.get("agent_id") == "planner" for item in history)


def test_orchestration_plan_reports_queue_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "orchestration-queue.json").mkdir()
    client = TestClient(create_app())

    response = client.post(
        "/v1/orchestration/plan",
        json={"workspace": str(workspace), "goal": "Stabilize queue persistence", "source_client": "pytest"},
    )

    assert response.status_code == 503
    assert "Could not persist orchestration state" in response.json()["detail"]
    assert not (aegis_dir / "active-orchestration.json").exists()


def test_orchestration_step_reports_active_state_persistence_failure(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    plan_response = client.post(
        "/v1/orchestration/plan",
        json={"workspace": str(workspace), "goal": "Stabilize active queue state", "source_client": "pytest"},
    )
    assert plan_response.status_code == 200
    active_path = workspace / ".aegis" / "active-orchestration.json"
    active_path.unlink()
    active_path.mkdir()
    task_id = plan_response.json()["data"]["task_list"][0]["id"]

    response = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": task_id, "action": "inspect"},
    )

    assert response.status_code == 503
    assert "Could not persist orchestration state" in response.json()["detail"]


def test_orchestration_step_requires_approval_before_apply_and_validation(tmp_path: Path, monkeypatch) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    plan_response = client.post(
        "/v1/orchestration/plan",
        json={"workspace": str(workspace), "goal": "Stabilize build workflow", "source_client": "pytest"},
    )
    tasks = plan_response.json()["data"]["task_list"]
    apply_task_id = next(task["id"] for task in tasks if task["owner_agent"] == "coder")
    validation_task_id = next(task["id"] for task in tasks if task["owner_agent"] == "tester")

    proposal = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": apply_task_id, "action": "propose"},
    )
    assert proposal.status_code == 200
    assert_core_contract(proposal.json(), "orchestration.step")
    assert proposal.json()["data"]["pending_approvals"][0]["task_id"] == apply_task_id

    blocked_apply = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": apply_task_id, "action": "apply"},
    )
    assert blocked_apply.status_code == 200
    assert blocked_apply.json()["data"]["pending_approvals"][0]["active_step"] == "wait_for_approval"

    approved = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": apply_task_id, "action": "approve", "approval": True},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["active_task"]["active_step"] == "apply_approved_changes"

    applied = client.post(
        "/v1/orchestration/step",
        json={
            "workspace": str(workspace),
            "task_id": apply_task_id,
            "action": "apply",
            "approval": True,
            "affected_files": ["src/app.py"],
        },
    )
    assert applied.status_code == 200
    apply_task = next(task for task in applied.json()["data"]["task_list"] if task["id"] == apply_task_id)
    assert apply_task["status"] == "validating"
    assert apply_task["affected_files"] == ["src/app.py"]

    validation_block = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": validation_task_id, "action": "validate"},
    )
    assert validation_block.status_code == 200
    assert validation_block.json()["data"]["pending_approvals"][0]["active_step"] == "wait_for_validation_approval"

    monkeypatch.setattr(
        "aegis_core.orchestration.run_validation",
        lambda workspace, command=None: {"ok": True, "command": ["npm", "test"], "returncode": 0, "stdout": "ok", "stderr": ""},
    )
    validation_run = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": validation_task_id, "action": "validate", "approval": True},
    )
    assert validation_run.status_code == 200
    validation_task = next(task for task in validation_run.json()["data"]["task_list"] if task["id"] == validation_task_id)
    assert validation_task["latest_validation"]["ok"] is True
    assert validation_task["active_step"] == "summarize"

    completed = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": validation_task_id, "action": "complete", "summary": "Validated staged workflow."},
    )
    assert completed.status_code == 200
    assert "Validated staged workflow" in (workspace / ".aegis" / "decisions.md").read_text(encoding="utf-8")
    assert "orchestration task passed" in (workspace / ".aegis" / "validation-log.md").read_text(encoding="utf-8")
    history = json.loads((workspace / ".aegis" / "agent-history.json").read_text(encoding="utf-8"))
    assert any(item.get("event") == "agent_decision" and item.get("agent_id") == "coder" for item in history)
    assert any(item.get("event") == "agent_decision" and item.get("agent_id") == "tester" for item in history)


def test_orchestration_dashboard_surfaces_agent_file_conflicts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    plan_response = client.post(
        "/v1/orchestration/plan",
        json={"workspace": str(workspace), "goal": "Coordinate a risky shared file edit", "source_client": "pytest"},
    )
    tasks = plan_response.json()["data"]["task_list"]
    coder_task_id = next(task["id"] for task in tasks if task["owner_agent"] == "coder")
    repair_task_id = next(task["id"] for task in tasks if task["owner_agent"] == "repair")

    for task_id in (coder_task_id, repair_task_id):
        response = client.post(
            "/v1/orchestration/step",
            json={
                "workspace": str(workspace),
                "task_id": task_id,
                "action": "apply",
                "approval": True,
                "affected_files": ["src/shared.py"],
            },
        )
        assert response.status_code == 200

    dashboard = client.get("/v1/orchestration", params={"workspace": str(workspace)})

    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    conflict = data["coordination"]["conflicts"][0]
    assert conflict["path"] == "src/shared.py"
    assert {claim["agent_id"] for claim in conflict["claims"]} == {"coder", "repair"}


def test_orchestration_validation_requires_approval_for_detected_commands(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    plan_response = client.post(
        "/v1/orchestration/plan",
        json={"workspace": str(workspace), "goal": "Inspect and validate safely", "source_client": "pytest"},
    )
    first_task_id = plan_response.json()["data"]["task_list"][0]["id"]

    response = client.post(
        "/v1/orchestration/step",
        json={"workspace": str(workspace), "task_id": first_task_id, "action": "validate"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pending_approvals"][0]["task_id"] == first_task_id
    assert data["pending_approvals"][0]["active_step"] == "wait_for_validation_approval"


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


def test_diagnostics_scrub_redacts_provider_query_keys_without_losing_context() -> None:
    secret = "AIzaSyVerySecretProviderKey"
    message = (
        "Provider connection failed: https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-1.5-pro:generateContent?key={secret}&alt=json"
    )

    cleaned = scrub(message)

    assert secret not in cleaned
    assert "key=[redacted]" in cleaned
    assert "Provider connection failed" in cleaned


def test_diagnostics_redact_inline_preserves_provider_auth_context() -> None:
    secret = "basic-secret-token"
    message = f"Provider rejected Authorization: Basic {secret}"

    cleaned = redact_inline(message)

    assert secret not in cleaned
    assert "Authorization: [redacted]" in cleaned
    assert "Provider rejected" in cleaned


def test_diagnostics_redact_inline_handles_json_keys_and_url_credentials() -> None:
    secret = "secret-token-value"
    message = (
        f'Provider HTTP 401: {{"api_key":"{secret}","error":"invalid_api_key"}} '
        "via https://user:password@example.test/v1"
    )

    cleaned = redact_inline(message)

    assert secret not in cleaned
    assert "user:password" not in cleaned
    assert '"api_key":"[redacted]"' in cleaned
    assert "invalid_api_key" in cleaned
    assert "https://[redacted]@example.test/v1" in cleaned


def test_provider_connection_errors_redact_query_api_keys(monkeypatch) -> None:
    secret = "AIzaSyVerySecretProviderKey"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini:generateContent?key={secret}"

    def failing_urlopen(request, timeout=0):
        raise urllib.error.URLError(f"unreachable {url}")

    monkeypatch.setattr(model_router_module.urllib.request, "urlopen", failing_urlopen)

    with pytest.raises(RuntimeError) as excinfo:
        model_router_module._request_json(url, {"contents": []}, {"Content-Type": "application/json"}, 1)

    message = str(excinfo.value)
    assert secret not in message
    assert "key=[redacted]" in message


def test_provider_connection_errors_redact_authorization_without_losing_context(monkeypatch) -> None:
    secret = "basic-secret-token"

    def failing_urlopen(request, timeout=0):
        raise urllib.error.URLError(f"Provider rejected Authorization: Basic {secret}")

    monkeypatch.setattr(model_router_module.urllib.request, "urlopen", failing_urlopen)

    with pytest.raises(RuntimeError) as excinfo:
        model_router_module._request_json("https://provider.example/v1/chat", {"messages": []}, {"Content-Type": "application/json"}, 1)

    message = str(excinfo.value)
    assert secret not in message
    assert "Provider rejected" in message
    assert "Authorization: [redacted]" in message
    assert "[redacted secret-like log line]" not in message


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
    assert config.model_routing_mode == "local_only"
    assert config.lm_studio_url == AegisConfig.lm_studio_url
    assert config.cloud_cost_warnings is True
    assert config.auto_scan_on_open is False
    assert config.validation_preferences == ("npm test", "npm run build")
    assert config.memory_dir_name == AegisConfig.memory_dir_name


def test_hybrid_model_settings_are_sanitized(tmp_path: Path) -> None:
    workspace = tmp_path / "hybrid-settings-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").write_text(
        json.dumps(
            {
                "lm_studio_url": "127.0.0.1:1234/v1/chat/completions",
                "model_routing_mode": "cloud-allowed",
                "default_local_model": "local-default",
                "local_small_model": "local-small",
                "local_coder_model": "local-coder",
                "local_embedding_model": "local-embed",
                "preferred_cloud_provider": "OpenRouter",
                "preferred_cloud_model": "openrouter-model",
                "cloud_cost_warnings": "false",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(workspace)

    assert config.lm_studio_url == "http://127.0.0.1:1234"
    assert config.model_routing_mode == "cloud_allowed"
    assert config.default_local_model == "local-default"
    assert config.local_small_model == "local-small"
    assert config.local_coder_model == "local-coder"
    assert config.local_embedding_model == "local-embed"
    assert config.preferred_cloud_provider == "openrouter"
    assert config.preferred_cloud_model == "openrouter-model"
    assert config.cloud_cost_warnings is False


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


class DummyCredentialStore:
    available = True

    def __init__(self, keys: dict[str, str] | None = None):
        self.keys = keys or {}

    def has_provider_key(self, provider_id: str) -> bool:
        return provider_id in self.keys

    def read_provider_key(self, provider_id: str) -> str | None:
        return self.keys.get(provider_id)


class BrokenCredentialStore(DummyCredentialStore):
    def has_provider_key(self, provider_id: str) -> bool:
        raise RuntimeError("credential backend unavailable")


class BrokenReadKeyring:
    def get_password(self, service_name: str, provider_id: str) -> None:
        raise RuntimeError("Provider rejected Authorization: Bearer read-secret-token")


class BrokenWriteKeyring:
    def set_password(self, service_name: str, provider_id: str, api_key: str) -> None:
        raise RuntimeError(f"Backend echoed {api_key} with api_key={api_key}")


class MissingDeleteKeyring:
    def get_password(self, service_name: str, provider_id: str) -> None:
        return None

    def delete_password(self, service_name: str, provider_id: str) -> None:
        raise AssertionError("delete_password should not run for missing keys")


class BrokenDeleteKeyring:
    def get_password(self, service_name: str, provider_id: str) -> str:
        return "stored-key"

    def delete_password(self, service_name: str, provider_id: str) -> None:
        raise RuntimeError("credential backend unavailable")


def test_credential_store_delete_missing_key_returns_false(monkeypatch) -> None:
    store = CredentialStore(service_name="aegis-core-test")
    monkeypatch.setattr(store, "_keyring", MissingDeleteKeyring())

    assert store.delete_provider_key("openai") is False


def test_credential_store_read_redacts_backend_secret(monkeypatch) -> None:
    store = CredentialStore(service_name="aegis-core-test")
    monkeypatch.setattr(store, "_keyring", BrokenReadKeyring())

    with pytest.raises(CredentialStoreError) as excinfo:
        store.read_provider_key("openai")

    message = str(excinfo.value)
    assert "read-secret-token" not in message
    assert "Authorization: [redacted]" in message


def test_credential_store_write_redacts_backend_secret(monkeypatch) -> None:
    secret = "sk-live-secret-token"
    store = CredentialStore(service_name="aegis-core-test")
    monkeypatch.setattr(store, "_keyring", BrokenWriteKeyring())

    with pytest.raises(CredentialStoreError) as excinfo:
        store.write_provider_key("openai", secret)

    message = str(excinfo.value)
    assert secret not in message
    assert "api_key=[redacted]" in message


def test_credential_store_delete_reports_backend_failure(monkeypatch) -> None:
    store = CredentialStore(service_name="aegis-core-test")
    monkeypatch.setattr(store, "_keyring", BrokenDeleteKeyring())

    with pytest.raises(CredentialStoreError) as excinfo:
        store.delete_provider_key("openai")

    assert "OS credential store delete failed" in str(excinfo.value)
    assert "credential backend unavailable" in str(excinfo.value)


def test_model_router_is_local_first_and_blocks_secret_context(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "router-local-project"
    workspace.mkdir()
    (workspace / "src.py").write_text("print('ok')\n", encoding="utf-8")
    (workspace / ".env").write_text("API_KEY=secret\n", encoding="utf-8")

    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 3, ["qwen3-coder:30b", "qwen2.5-coder:7b"], "qwen3-coder:30b", []),
    )

    route = route_model(workspace, "code_completion", context_files=["src.py", ".env"], credentials=DummyCredentialStore())

    assert route["selected"]["provider_id"] == "ollama"
    assert route["selected"]["model"] == "qwen3-coder:30b"
    assert route["approval_required"] is False
    assert route["context"]["included_files"] == ["src.py"]
    assert route["context"]["blocked_files"][0]["path"] == ".env"
    assert "Secret-like" in route["warnings"][0]


def test_model_router_requires_cloud_approval_in_hybrid_mode(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "router-hybrid-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").write_text(
        json.dumps({"model_routing_mode": "hybrid", "preferred_cloud_provider": "openai"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 4, ["qwen3-coder:30b"], "qwen3-coder:30b", []),
    )

    route = route_model(workspace, "hard_debugging", credentials=DummyCredentialStore({"openai": "stored"}))

    assert route["selected"]["provider_id"] == "ollama"
    assert route["approval_required"] is True
    assert route["fallback_order"][1]["provider_id"] == "openai"
    assert route["fallback_order"][1]["status"] == "approval_required"
    assert route["cloud_reason"] == "client_approval_required"


def test_model_router_selects_approved_cloud_when_allowed(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "router-cloud-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").write_text(
        json.dumps(
            {
                "model_routing_mode": "cloud_allowed",
                "preferred_cloud_provider": "openrouter",
                "preferred_cloud_model": "anthropic/claude-sonnet",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 4, ["qwen3-coder:30b"], "qwen3-coder:30b", []),
    )

    route = route_model(
        workspace,
        "hard_debugging",
        allow_cloud=True,
        cloud_approved=True,
        local_failure_reason="local model could not explain the failing trace",
        credentials=DummyCredentialStore({"openrouter": "stored"}),
    )

    assert route["selected"]["provider_id"] == "openrouter"
    assert route["selected"]["model"] == "anthropic/claude-sonnet"
    assert route["cloud_ready"] is True
    assert route["approval_required"] is False
    assert any("Cost warning" in warning for warning in route["warnings"])


def test_model_router_selects_approved_cloud_for_repo_planning(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "router-planning-project"
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir(parents=True)
    (aegis_dir / "config.json").write_text(
        json.dumps({"model_routing_mode": "hybrid", "preferred_cloud_provider": "openai", "preferred_cloud_model": "gpt-4.1"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 4, ["qwen3-coder:30b"], "qwen3-coder:30b", []),
    )

    route = route_model(
        workspace,
        "repo_wide_planning",
        allow_cloud=True,
        cloud_approved=True,
        credentials=DummyCredentialStore({"openai": "stored"}),
    )

    assert route["selected"]["provider_id"] == "openai"
    assert route["task_type"] == "repo_wide_planning"
    assert route["cloud_ready"] is True
    assert route["approval_required"] is False


def test_model_router_contract_endpoint_returns_versioned_route(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "router-api-project"
    workspace.mkdir()
    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 5, ["qwen3-coder:30b"], "qwen3-coder:30b", []),
    )
    client = TestClient(create_app())

    response = client.post("/v1/models/route", json={"workspace": str(workspace), "task_type": "simple_explanation"})

    assert response.status_code == 200
    assert_core_contract(response.json(), "model.route")
    data = response.json()["data"]
    assert data["selected"]["provider_id"] == "ollama"
    assert data["mode"] == "local_only"


def test_provider_inventory_reports_credential_store_read_failures(tmp_path: Path) -> None:
    workspace = tmp_path / "provider-inventory-project"
    workspace.mkdir()

    inventory = provider_inventory(workspace, credentials=BrokenCredentialStore())

    assert inventory["credential_store_available"] is True
    assert inventory["credential_store_healthy"] is False
    assert inventory["credential_store_errors"]
    assert {item["provider_id"] for item in inventory["credential_store_errors"]} == {"openai", "anthropic", "google", "openrouter"}
    assert all(item["error"] for item in inventory["credential_store_errors"])
    assert all("secret-like" in item["error"] for item in inventory["credential_store_errors"])
    assert all(not item["key_stored"] for item in inventory["providers"] if item["requires_key"])


def test_model_route_reports_credential_store_read_failures(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "route-credential-failure-project"
    workspace.mkdir()
    monkeypatch.setattr(
        "aegis_core.model_router.OllamaClient.health",
        lambda self: OllamaStatus(True, 4, ["qwen3-coder:30b"], "qwen3-coder:30b", []),
    )

    route = route_model(
        workspace,
        "hard_debugging",
        allow_cloud=True,
        cloud_approved=True,
        credentials=BrokenCredentialStore(),
    )

    assert route["selected"]["provider_id"] == "ollama"
    assert route["cloud_ready"] is False
    assert route["credential_store_healthy"] is False
    assert route["credential_store_errors"]
    assert any("credential store could not be inspected" in warning.lower() for warning in route["warnings"])
    assert route["cloud_reason"] == "local_only"


def test_provider_key_endpoint_rejects_unknown_provider() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/providers/not-a-provider/key", json={"api_key": "dummy"})

    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["detail"]


def test_provider_key_endpoint_redacts_backend_write_secret(monkeypatch) -> None:
    secret = "sk-endpoint-secret-token"
    monkeypatch.setattr(CredentialStore, "_load_keyring", lambda self: BrokenWriteKeyring())
    client = TestClient(create_app())

    response = client.post("/v1/providers/openai/key", json={"api_key": secret})

    assert response.status_code == 503
    assert secret not in response.json()["detail"]
    assert "api_key=[redacted]" in response.json()["detail"]


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
    with pytest.raises(ConfigPersistenceError):
        update_config(workspace, {"default_model": "granite-code:8b"})

    client = TestClient(create_app())
    get_response = client.get("/v1/settings", params={"workspace": str(workspace)})
    post_response = client.post(
        "/v1/settings",
        json={"workspace": str(workspace), "settings": {"default_model": "qwen2.5-coder:7b"}},
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 503
    assert "Could not persist Aegis Core settings" in post_response.json()["detail"]


def test_config_write_survives_memory_root_file(tmp_path: Path) -> None:
    workspace = tmp_path / "config-root-file-project"
    workspace.mkdir()
    (workspace / ".aegis").write_text("not a directory", encoding="utf-8")

    assert load_config(workspace).default_model == AegisConfig.default_model
    assert write_default_config(workspace) == workspace / ".aegis" / "config.json"
    with pytest.raises(ConfigPersistenceError):
        update_config(workspace, {"default_model": "granite-code:8b"})


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


def test_validation_runner_resolves_windows_package_manager_shims(monkeypatch) -> None:
    monkeypatch.setattr(validation_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        validation_module.shutil,
        "which",
        lambda name: "C:/tools/npm.cmd" if str(name).lower() in {"npm", "npm.cmd"} else None,
    )

    assert validation_module._resolve_validation_command(["npm", "test"]) == ["C:/tools/npm.cmd", "test"]
    assert validation_module._resolve_validation_command(["npm.cmd", "test"]) == ["C:/tools/npm.cmd", "test"]


def test_validation_runner_allows_windows_package_manager_shims() -> None:
    assert validation_module.is_safe_validation_command(["npm.cmd", "test"])
    assert validation_module.is_safe_validation_command(["pnpm.cmd", "build"])
    assert validation_module.is_safe_validation_command(["yarn.cmd", "typecheck"])
    assert validation_module.is_safe_validation_command(["dotnet.exe", "build"])
    assert validation_module.is_safe_validation_command(["cmake.exe", "--build", "build"])
    assert not validation_module.is_safe_validation_command(["npm.cmd", "install"])


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


def test_validation_runner_surfaces_log_persistence_failure(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "validation-log-warning-project"
    workspace.mkdir()
    aegis_dir = workspace / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "validation-log.md").mkdir()

    def return_success(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(validation_module.subprocess, "run", return_success)

    result = run_validation(workspace, command=[sys.executable, "-m", "pytest"])

    assert result["ok"] is True
    assert result["validation_log"]["persisted"] is False
    assert "Could not persist validation log" in result["memory_warning"]


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

    result = append_validation_log(workspace, {"ok": False, "command": ["npm", "test"], "stderr": "still returns"})

    assert result["persisted"] is False
    assert "Could not persist validation log" in result["warning"]


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
    assert "Could not persist roadmap" in data["plan"]["memory_warning"]
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
