from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core.contracts import validate_contract_envelope
from aegis_core.server import create_app


@pytest.fixture
def intelligence_stack_workspace() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"intelligence-stack-{uuid.uuid4().hex[:10]}"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    try:
        (root / "README.md").write_text(
            "# Intelligence Stack Fixture\n\nLocal-first engineering runtime with roadmap and repair workflows.\n",
            encoding="utf-8",
        )
        (root / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"test": "vitest run", "build": "tsc -p tsconfig.json", "lint": "eslint src"},
                    "dependencies": {"react": "^19.0.0"},
                    "devDependencies": {"typescript": "^5.8.0", "vitest": "^3.0.0"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (root / "src" / "router.ts").write_text(
            "export function selectRoute(workflow: string) {\n"
            "  if (workflow.includes('repair')) return 'local-repair';\n"
            "  return 'local-planner';\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "src" / "repair.ts").write_text(
            "export function classifyFailure(stderr: string) {\n"
            "  return stderr.includes('ImportError') ? 'import_or_module_resolution' : 'unknown';\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "tests" / "repair.test.ts").write_text(
            "import { describe, expect, it } from 'vitest';\n"
            "import { classifyFailure } from '../src/repair';\n"
            "describe('repair', () => { it('classifies imports', () => expect(classifyFailure('ImportError')).toBe('import_or_module_resolution')); });\n",
            encoding="utf-8",
        )
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_intelligence_stack_model_lifecycle_and_dashboard(intelligence_stack_workspace: Path) -> None:
    client = TestClient(create_app())

    registered = client.post(
        "/v1/intelligence-stack/models",
        json={
            "workspace": str(intelligence_stack_workspace),
            "action": "register",
            "model": {
                "model_id": "local-repair-1b-q4",
                "provider_id": "ollama",
                "display_name": "Local Repair 1B Q4",
                "specializations": ["repair", "validation_classifier"],
                "capabilities": ["repair_reasoning", "failure_triage", "code"],
                "quantization": {"format": "q4", "memory_gb_estimate": 1.5, "cpu_usable": True},
            },
        },
    )
    assert registered.status_code == 200, registered.text
    assert_kind(registered.json(), "intelligence.models")
    assert registered.json()["data"]["state"]["models"][0]["model_id"] == "local-repair-1b-q4"

    plan = client.post(
        "/v1/intelligence-stack/models",
        json={"workspace": str(intelligence_stack_workspace), "action": "plan_install", "model_id": "nomic-embed-text:latest"},
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["data"]["install_plan"]["executes_now"] is False

    dashboard = client.post(
        "/v1/intelligence-stack",
        json={
            "workspace": str(intelligence_stack_workspace),
            "workflow_type": "repair_project",
            "objective": "Repair validation classifier route selection.",
            "target_files": ["src/repair.ts"],
        },
    )
    assert dashboard.status_code == 200, dashboard.text
    assert_kind(dashboard.json(), "intelligence.stack")
    data = dashboard.json()["data"]
    assert data["local_first"] is True
    assert data["components"]
    assert data["model_lifecycle"]["installed_or_registered"]
    assert data["ui_visibility"]["selected_intelligence_profile"]
    assert (intelligence_stack_workspace / ".aegis" / "auralith-intelligence-stack.json").exists()


def test_retrieval_routing_and_prediction_contracts(intelligence_stack_workspace: Path) -> None:
    client = TestClient(create_app())

    retrieval = client.post(
        "/v1/intelligence-stack/retrieval/index",
        json={
            "workspace": str(intelligence_stack_workspace),
            "query": "repair route validation classifier",
            "limit": 10,
            "refresh": True,
        },
    )
    assert retrieval.status_code == 200, retrieval.text
    assert_kind(retrieval.json(), "intelligence.retrieval")
    assert retrieval.json()["data"]["hybrid_retrieval"]["results"]
    assert retrieval.json()["data"]["quality"]["score"] > 0

    route = client.post(
        "/v1/intelligence-stack/route",
        json={
            "workspace": str(intelligence_stack_workspace),
            "workflow_type": "repair_project",
            "objective": "Repair local classifier failure.",
            "target_files": ["src/repair.ts"],
            "privacy_sensitive": True,
            "allow_cloud": True,
            "cloud_approved": True,
        },
    )
    assert route.status_code == 200, route.text
    assert_kind(route.json(), "intelligence.route")
    route_data = route.json()["data"]
    assert route_data["component"]["id"] == "repair"
    assert route_data["privacy"]["local_first"] is True
    assert route_data["route"]["local_only"] is True

    prediction = client.post(
        "/v1/intelligence-stack/predict",
        json={
            "workspace": str(intelligence_stack_workspace),
            "workflow_type": "repair_project",
            "objective": "Repair import classification and rerun tests.",
            "target_files": ["src/repair.ts"],
        },
    )
    assert prediction.status_code == 200, prediction.text
    assert_kind(prediction.json(), "intelligence.prediction")
    assert prediction.json()["data"]["lightweight_models"]["risk_classifier"] == "deterministic-local-v1"
    assert prediction.json()["data"]["execution_guidance"]


def test_benchmarks_datasets_and_distributed_inference_plan(intelligence_stack_workspace: Path) -> None:
    client = TestClient(create_app())

    benchmark = client.post(
        "/v1/intelligence-stack/benchmarks/run",
        json={
            "workspace": str(intelligence_stack_workspace),
            "workflow_type": "generate_feature",
            "objective": "Improve local-first routing visibility.",
            "target_files": ["src/router.ts"],
        },
    )
    assert benchmark.status_code == 200, benchmark.text
    assert_kind(benchmark.json(), "intelligence.benchmarks")
    assert benchmark.json()["data"]["benchmark_run"]["scores"]["routing_quality"] >= 0

    dataset = client.post(
        "/v1/intelligence-stack/datasets",
        json={"workspace": str(intelligence_stack_workspace), "include_sensitive": False, "limit": 25},
    )
    assert dataset.status_code == 200, dataset.text
    assert_kind(dataset.json(), "intelligence.datasets")
    assert dataset.json()["data"]["privacy"]["cloud_upload_allowed"] is False

    inference = client.post(
        "/v1/intelligence-stack/distributed-inference/plan",
        json={
            "workspace": str(intelligence_stack_workspace),
            "workflow_type": "generate_feature",
            "model_id": "local-repair-1b-q4",
            "allow_remote": False,
            "dry_run": True,
            "payload": {"prompt_shape": "route classification"},
        },
    )
    assert inference.status_code == 200, inference.text
    assert_kind(inference.json(), "intelligence.distributed_inference")
    assert inference.json()["data"]["workload"]["workload_type"] == "model_inference"
    assert inference.json()["data"]["fallback"]["fallback_node_ids"] == ["local"]
    assert (intelligence_stack_workspace / ".aegis" / "intelligence-benchmarks.json").exists()
    assert (intelligence_stack_workspace / ".aegis" / "intelligence-datasets.json").exists()
