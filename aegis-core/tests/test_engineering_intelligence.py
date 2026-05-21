from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core import autopilot
from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


@pytest.fixture
def intelligence_workspace() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"engineering-intelligence-{uuid.uuid4().hex[:10]}"
    (root / "src").mkdir(parents=True)
    (root / "backend").mkdir()
    (root / "tests").mkdir()
    try:
        (root / "README.md").write_text(
            "# Intelligence Fixture\n\nA small full-stack project for engineering reasoning tests.\n",
            encoding="utf-8",
        )
        (root / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {
                        "test": "vitest run",
                        "build": "tsc -p tsconfig.json",
                        "lint": "eslint src",
                    },
                    "dependencies": {"@vitejs/plugin-react": "^5.0.0", "fastapi": "^0.1.0"},
                    "devDependencies": {"typescript": "^5.8.0", "vitest": "^3.0.0"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (root / "tsconfig.json").write_text(
            json.dumps({"compilerOptions": {"jsx": "react-jsx", "strict": True}, "include": ["src"]}, indent=2),
            encoding="utf-8",
        )
        (root / "src" / "apiClient.ts").write_text(
            "export async function loadUsers() {\n"
            "  const response = await fetch('/v1/users');\n"
            "  return response.json();\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "src" / "App.tsx").write_text(
            "import { loadUsers } from './apiClient';\n"
            "export function App() {\n"
            "  void loadUsers();\n"
            "  return <main>Users</main>;\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "backend" / "app.py").write_text(
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n\n"
            "@app.get('/v1/users')\n"
            "def users():\n"
            "    return [{'id': 'user-1'}]\n",
            encoding="utf-8",
        )
        (root / "tests" / "app.test.ts").write_text(
            "import { describe, it, expect } from 'vitest';\n"
            "describe('users', () => { it('loads', () => expect(true).toBe(true)); });\n",
            encoding="utf-8",
        )
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_engineering_intelligence_analyze_builds_context_validation_and_prediction(intelligence_workspace: Path) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/engineering-intelligence/analyze",
        json={
            "workspace": str(intelligence_workspace),
            "workflow_type": "generate_feature",
            "objective": "Add user filtering to the React user list and backend API.",
            "target_files": ["src/apiClient.ts", "backend/app.py"],
            "focus": "user API runtime boundary",
            "token_budget": 12000,
        },
    )

    assert response.status_code == 200, response.text
    assert_kind(response.json(), "engineering.intelligence")
    data = response.json()["data"]
    selected_paths = {item["path"] for item in data["context_assembly"]["selected_context"]}

    assert "src/apiClient.ts" in selected_paths
    assert "backend/app.py" in selected_paths
    assert data["architecture_reasoning"]["confidence"]["score"] >= 20
    assert data["validation_intelligence"]["prioritized_validations"]
    assert data["workflow_prediction"]["execution_risk"]["level"] in {"low", "medium", "high", "critical"}
    assert data["benchmarks"]["scores"]["feature_quality"] >= 0
    assert data["explainability"]["decisions"]
    assert (intelligence_workspace / ".aegis" / "engineering-intelligence.json").exists()


def test_repair_intelligence_extracts_root_cause_and_rollback_guidance(intelligence_workspace: Path) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/engineering-intelligence/repair-plan",
        json={
            "workspace": str(intelligence_workspace),
            "workflow_type": "repair_project",
            "objective": "Repair failing user API validation.",
            "target_files": ["src/apiClient.ts"],
            "latest_validation": {
                "passed": False,
                "stderr": "ImportError: cannot find module user_client",
                "summary": "Validation failed during API client import.",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert_kind(response.json(), "engineering.repair_intelligence")
    data = response.json()["data"]
    causes = {item["cause"] for item in data["root_cause_candidates"]}

    assert "import_or_module_resolution" in causes
    assert data["strategy_selection"]
    assert "rollback_recommendation" in data
    assert data["repair_confidence"]["level"] in {"low", "medium", "high"}


def test_context_roadmap_and_benchmark_contracts_persist_history(intelligence_workspace: Path) -> None:
    client = TestClient(create_app())
    request = {
        "workspace": str(intelligence_workspace),
        "workflow_type": "continue_roadmap",
        "objective": "Continue the user management roadmap safely.",
        "target_files": ["src/App.tsx", "src/apiClient.ts"],
        "token_budget": 10000,
    }

    context = client.post("/v1/engineering-intelligence/context", json=request)
    roadmap = client.post("/v1/engineering-intelligence/roadmap-plan", json=request)
    prediction = client.post("/v1/engineering-intelligence/predict", json=request)
    benchmark = client.post("/v1/engineering-intelligence/benchmarks/run", json=request)
    dashboard = client.get("/v1/engineering-intelligence/benchmarks", params={"workspace": str(intelligence_workspace)})

    assert context.status_code == 200, context.text
    assert roadmap.status_code == 200, roadmap.text
    assert prediction.status_code == 200, prediction.text
    assert benchmark.status_code == 200, benchmark.text
    assert dashboard.status_code == 200, dashboard.text
    assert_kind(context.json(), "engineering.context")
    assert_kind(roadmap.json(), "engineering.roadmap_intelligence")
    assert_kind(prediction.json(), "engineering.workflow_prediction")
    assert_kind(benchmark.json(), "engineering.intelligence.benchmarks")
    assert_kind(dashboard.json(), "engineering.intelligence.benchmarks")
    assert context.json()["data"]["selected_context"]
    assert roadmap.json()["data"]["task_decomposition"]
    assert prediction.json()["data"]["duration_estimate"]["label"]
    assert benchmark.json()["data"]["benchmark_run"]["scores"]["roadmap_quality"] >= 0
    assert dashboard.json()["data"]["history"]
    assert (intelligence_workspace / ".aegis" / "engineering-intelligence-benchmarks.json").exists()


def test_autopilot_exposes_deep_engineering_intelligence_to_supervision(intelligence_workspace: Path) -> None:
    result = autopilot.start_autopilot(
        intelligence_workspace,
        "Implement safe user filtering with validation and rollback awareness.",
        mode="semi_autonomous",
        workflow_type="generate_feature",
        target_files=["src/apiClient.ts"],
        client_id="pytest",
    )
    run = result["run"]
    supervision = autopilot.autopilot_supervision(intelligence_workspace, autopilot_id=run["id"])

    assert run["deep_engineering_intelligence"]["status"] == "ready"
    assert run["deep_engineering_intelligence"]["context_assembly"]["selected_context"]
    assert supervision["deep_engineering_intelligence"]["workflow_prediction"]["execution_risk"]["level"] in {
        "low",
        "medium",
        "high",
        "critical",
    }
