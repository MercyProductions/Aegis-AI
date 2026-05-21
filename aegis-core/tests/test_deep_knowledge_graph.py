from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "deep-knowledge-project"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}, "dependencies": {"react": "^19.0.0", "vite": "^7.0.0"}}),
        encoding="utf-8",
    )
    (workspace / "src").mkdir()
    (workspace / "src" / "apiClient.ts").write_text(
        "export async function loadUsers() { return fetch('/v1/users').then(r => r.json()) }\n",
        encoding="utf-8",
    )
    (workspace / "src" / "App.tsx").write_text(
        "import { loadUsers } from './apiClient'\n"
        "export function App() { loadUsers(); return <main /> }\n",
        encoding="utf-8",
    )
    (workspace / "backend").mkdir()
    (workspace / "backend" / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/v1/users')\n"
        "def list_users():\n"
        "    return []\n",
        encoding="utf-8",
    )
    (workspace / "native").mkdir()
    (workspace / "native" / "engine.cpp").write_text(
        '#include "engine.h"\nclass Engine : public Runtime { };\nvoid Engine::Tick() { Run(); }\n',
        encoding="utf-8",
    )
    (workspace / "dotnet").mkdir()
    (workspace / "dotnet" / "UserService.cs").write_text(
        "using System;\npublic class UserService : BaseService {\npublic void LoadUsers() { Console.WriteLine(\"ok\"); }\n}\n",
        encoding="utf-8",
    )
    return workspace


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"


def test_deep_knowledge_graph_indexes_symbols_relationships_and_memory(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    assert response.status_code == 200
    assert_contract(response.json(), "knowledge.graph")
    graph = response.json()["data"]
    node_types = {node["type"] for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert {"file", "folder", "module", "class", "function", "method", "api", "config", "build_system", "runtime_boundary"}.issubset(node_types)
    assert {"contains", "imports", "calls", "inherits", "api_consumer", "configures"}.intersection(edge_types)
    assert graph["semantic_index"]["files"]
    assert graph["project_memory"]["generated_at"]
    assert graph["embedding_interfaces"]["enabled"] is False
    assert graph["indexing"]["graph_size"]["nodes"] == len(graph["nodes"])
    assert graph["indexing"]["files_indexed"] >= 5
    assert {"TypeScript", "Python", "C++", "C#"}.issubset(set(graph["indexing"]["language_coverage"]))
    assert (workspace / ".aegis" / "knowledge-index-state.json").is_file()
    assert (workspace / ".aegis" / "semantic-index.json").is_file()
    assert (workspace / ".aegis" / "project-memory.json").is_file()


def test_knowledge_search_symbol_relationships_and_impact_api(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())
    client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    search = client.post("/v1/knowledge/search", json={"workspace": str(workspace), "query": "users", "limit": 10})
    symbol = client.post("/v1/knowledge/symbol", json={"workspace": str(workspace), "symbol": "UserService"})
    relationships = client.post(
        "/v1/knowledge/relationships",
        json={"workspace": str(workspace), "focus": "src/App.tsx", "depth": 2},
    )
    impact = client.post(
        "/v1/knowledge/impact-analysis",
        json={"workspace": str(workspace), "target": "src/apiClient.ts", "change_type": "modify"},
    )
    architecture = client.get("/v1/knowledge/architecture-summary", params={"workspace": str(workspace)})

    assert search.status_code == 200
    assert_contract(search.json(), "knowledge.search")
    assert search.json()["data"]["results"]
    assert symbol.status_code == 200
    assert_contract(symbol.json(), "knowledge.symbol")
    assert symbol.json()["data"]["matches"][0]["label"] == "UserService"
    assert relationships.status_code == 200
    assert_contract(relationships.json(), "knowledge.relationships")
    assert relationships.json()["data"]["focus_node"]["path"] == "src/App.tsx"
    assert relationships.json()["data"]["edges"]
    assert impact.status_code == 200
    assert_contract(impact.json(), "knowledge.impact_analysis")
    assert "src/apiClient.ts" in impact.json()["data"]["affected_files"]
    assert impact.json()["data"]["modification_risk"]["level"] in {"low", "medium", "high"}
    assert impact.json()["data"]["validation_targets"]
    assert architecture.status_code == 200
    assert_contract(architecture.json(), "knowledge.architecture_summary")
    assert architecture.json()["data"]["summary"]["frameworks"]


def test_incremental_indexing_reports_partial_updates(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    first = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})
    assert first.status_code == 200
    assert first.json()["data"]["incremental"]["full_rescan"] is True

    second = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})
    assert second.status_code == 200
    assert second.json()["data"]["cache_hit"] is True
    assert second.json()["data"]["incremental"]["changed_files"] == []

    target = workspace / "src" / "apiClient.ts"
    target.write_text(target.read_text(encoding="utf-8") + "export function saveUser() { return loadUsers() }\n", encoding="utf-8")
    third = client.post("/v1/knowledge/graph", json={"workspace": str(workspace)})

    assert third.status_code == 200
    incremental = third.json()["data"]["incremental"]
    assert incremental["partial_update"] is True
    assert "src/apiClient.ts" in incremental["changed_files"]
    assert "file:src/apiClient.ts" in incremental["invalidated_nodes"]
