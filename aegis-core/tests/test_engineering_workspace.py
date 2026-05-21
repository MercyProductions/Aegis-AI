from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import aegis_core.engineering_workspace as engineering_workspace_module
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.engineering_workspace import (
    engineering_project_map,
    engineering_search,
    engineering_workspace_dashboard,
    validation_review,
    workflow_continuity,
)
from aegis_core.memory import ProjectMemory
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"engineering-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert payload["ok"] is True


def write_workspace(root: Path) -> None:
    (root / "src" / "services").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "engineering-workspace-test",
                "scripts": {
                    "build": "tsc --noEmit",
                    "test": "vitest run",
                    "lint": "eslint src",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "src" / "app.ts").write_text(
        "import { AuthService } from './services/auth';\n"
        "export function start() { return new AuthService().login('demo'); }\n",
        encoding="utf-8",
    )
    (root / "src" / "services" / "auth.ts").write_text(
        "export class AuthService {\n"
        "  login(user: string) { return `hello ${user}`; }\n"
        "}\n",
        encoding="utf-8",
    )
    (root / "tests" / "auth.test.ts").write_text(
        "import { start } from '../src/app';\n"
        "test('starts', () => { expect(start()).toContain('demo'); });\n",
        encoding="utf-8",
    )


def test_engineering_workspace_dashboard_persists_flagship_summary(workspace_fixture: Path) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)

    dashboard = engineering_workspace_dashboard(workspace, persist=True)

    assert dashboard["product"] == "Auralith Engineering Workspace"
    assert dashboard["project_map"]["file_count"] >= 1
    assert dashboard["validation"]["command_count"] >= 3
    assert dashboard["continuity"]["checkpoint_linking"]["required_before_apply"] is True
    assert dashboard["recommendations"]
    assert dashboard["state_files"]["dashboard_persisted"] is True
    assert dashboard["state_files"]["summary_persisted"] is True
    assert (ProjectMemory(workspace).root / "engineering-workspace-dashboard.json").is_file()
    assert (ProjectMemory(workspace).root / "engineering-workspace-summary.md").is_file()


def test_project_map_and_search_return_navigation_context(workspace_fixture: Path) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)

    project_map = engineering_project_map(workspace)
    search = engineering_search(workspace, "AuthService", mode="dependency")

    assert project_map["dependency_visualization"]["nodes"]
    assert "dependency" in search["mode"]
    assert search["results"]
    assert "semantic-ready" in search["semantic_note"]
    assert search["suggested_next_actions"]


def test_validation_review_and_continuity_are_engineering_focused(workspace_fixture: Path) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)

    review = validation_review(workspace)
    continuity = workflow_continuity(workspace)

    assert review["validation_prioritization"]
    assert review["recommended_next_validation"]["strategy"] in {"fast_first", "baseline_needed", "blocked_first"}
    assert continuity["roadmap_continuation"]["status"] in {"ready", "ready_with_quality_focus", "blocked_by_validation"}
    assert continuity["checkpoint_linking"]["required_before_apply"] is True


def test_dashboard_degrades_when_knowledge_persistence_is_unavailable(workspace_fixture: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)
    real_knowledge_graph = engineering_workspace_module.knowledge_graph

    def flaky_knowledge_graph(root: Path, *, persist: bool = False, scan: dict | None = None, refresh: bool = False) -> dict:
        if persist:
            raise RuntimeError("simulated persistence failure")
        return real_knowledge_graph(root, persist=False, scan=scan, refresh=refresh)

    monkeypatch.setattr(engineering_workspace_module, "knowledge_graph", flaky_knowledge_graph)

    dashboard = engineering_workspace_dashboard(workspace, persist=True)

    assert dashboard["project_map"]["indexing"]["persistence_degraded"] is True
    assert dashboard["recommendations"]


def test_dashboard_degrades_when_quality_history_is_unavailable(workspace_fixture: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)
    real_quality_dashboard = engineering_workspace_module.quality_dashboard

    def flaky_quality_dashboard(root: Path, *, record_snapshot: bool = False, scan: dict | None = None) -> dict:
        if record_snapshot:
            raise RuntimeError("simulated quality history failure")
        return real_quality_dashboard(root, record_snapshot=False, scan=scan)

    monkeypatch.setattr(engineering_workspace_module, "quality_dashboard", flaky_quality_dashboard)

    dashboard = engineering_workspace_dashboard(workspace, persist=True)

    assert dashboard["dashboards"]["project_health"]["score"] is not None
    assert dashboard["recommendations"]


def test_engineering_workspace_endpoints_are_contract_wrapped(workspace_fixture: Path) -> None:
    workspace = workspace_fixture
    write_workspace(workspace)
    client = TestClient(create_app())

    endpoints = [
        ("/v1/engineering-workspace", {"workspace": str(workspace)}, "engineering_workspace.dashboard"),
        ("/v1/engineering-workspace/map", {"workspace": str(workspace)}, "engineering_workspace.map"),
        ("/v1/engineering-workspace/validation", {"workspace": str(workspace)}, "engineering_workspace.validation"),
        ("/v1/engineering-workspace/continuity", {"workspace": str(workspace)}, "engineering_workspace.continuity"),
        ("/v1/engineering-workspace/benchmarks", {"workspace": str(workspace)}, "engineering_workspace.benchmarks"),
    ]
    for path, params, kind in endpoints:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_contract(response.json(), kind)

    search = client.post(
        "/v1/engineering-workspace/search",
        json={"workspace": str(workspace), "query": "AuthService", "mode": "architecture"},
    )
    assert search.status_code == 200
    assert_contract(search.json(), "engineering_workspace.search")


def test_engineering_workspace_contracts_are_registered() -> None:
    required = {
        "engineering_workspace.dashboard",
        "engineering_workspace.map",
        "engineering_workspace.search",
        "engineering_workspace.validation",
        "engineering_workspace.continuity",
        "engineering_workspace.benchmarks",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
