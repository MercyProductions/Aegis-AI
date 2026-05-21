from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.memory import ProjectMemory
from aegis_core.server import create_app
from aegis_core.stabilization import governance_rules, roadmap_classification, stabilization_audit


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert envelope.api_version == "v1"
    assert payload["ok"] is True


def test_stabilization_audit_detects_repo_risks_and_persists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / "sample-project"
    app_dir = repo / "website" / "frontend" / "src"
    app_dir.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (workspace / "README.md").write_text("# Sample\n", encoding="utf-8")
    (app_dir / "App.tsx").write_text("\n".join("const value = 1;" for _ in range(1305)), encoding="utf-8")

    memory = ProjectMemory(workspace)
    memory.ensure()
    (memory.root / "corrupt.json").write_text("{broken", encoding="utf-8")

    result = stabilization_audit(workspace, repo_root=repo, persist=True)

    categories = {item["category"] for item in result["findings"]}
    assert "oversized_module" in categories
    assert "corrupted_state_file" in categories
    assert result["metrics"]["oversized_module_count"] == 1
    assert result["standardization"]["missing_data_models"] == []
    assert any(item["path"] == "website/frontend/src/App.tsx" for item in result["refactor_candidates"])
    assert (memory.root / "stabilization-audit.json").is_file()
    assert (memory.root / "stabilization-summary.md").is_file()


def test_stabilization_contract_catalog_has_no_unmapped_core_contracts() -> None:
    schema_only = {kind for kind, descriptor in CONTRACTS.items() if descriptor.owner == "schema-only"}
    missing = sorted(set(CONTRACTS) - set(CONTRACT_DATA_MODELS) - schema_only)
    extra = sorted(set(CONTRACT_DATA_MODELS) - set(CONTRACTS))

    assert missing == []
    assert extra == []


def test_stabilization_endpoints_are_contract_wrapped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / "workspace"
    repo.mkdir()
    workspace.mkdir()
    (workspace / "README.md").write_text("# Workspace\n", encoding="utf-8")
    (repo / "small.py").write_text("print('ok')\n", encoding="utf-8")

    client = TestClient(create_app())

    audit = client.get(
        "/v1/stabilization/audit",
        params={"workspace": str(workspace), "repo_root": str(repo), "persist": False},
    )
    assert audit.status_code == 200
    assert_contract(audit.json(), "stabilization.audit")
    assert audit.json()["data"]["repo_root"] == str(repo.resolve())

    governance = client.get("/v1/stabilization/governance")
    assert governance.status_code == 200
    assert_contract(governance.json(), "stabilization.governance")
    assert governance.json()["data"]["security_review_required_for"]

    roadmap = client.get("/v1/stabilization/roadmap")
    assert roadmap.status_code == 200
    assert_contract(roadmap.json(), "stabilization.roadmap")
    assert {"production_ready", "experimental", "prototype", "deprecated", "planned"}.issubset(roadmap.json()["data"])


def test_deployment_and_optimization_contract_surfaces_are_reachable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workflows = workspace / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workspace / "package.json").write_text(
        json.dumps({"scripts": {"test": "node smoke.js", "build": "node smoke.js"}}),
        encoding="utf-8",
    )
    (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
    (workflows / "ci.yml").write_text("name: ci\non: [push]\njobs:\n  test:\n    steps:\n      - run: npm test\n", encoding="utf-8")

    client = TestClient(create_app())

    deployment = client.get("/v1/deployment", params={"workspace": str(workspace)})
    assert deployment.status_code == 200
    assert_contract(deployment.json(), "deployment.dashboard")
    assert deployment.json()["data"]["pipelines"]

    validation = client.post("/v1/deployment/pipelines/validate", json={"workspace": str(workspace), "dry_run": True})
    assert validation.status_code == 200
    assert_contract(validation.json(), "deployment.pipeline.validation")

    optimization = client.get("/v1/optimization", params={"workspace": str(workspace)})
    assert optimization.status_code == 200
    assert_contract(optimization.json(), "optimization.dashboard")
    assert optimization.json()["data"]["safety_controls"]["approval_before_adoption"] is True


def test_governance_and_roadmap_classification_cover_stabilization_states() -> None:
    governance = governance_rules()
    roadmap = roadmap_classification()

    assert governance["release_freeze_rules"]
    assert any(item["system"] == "Core editing/checkpoint runtime" for item in roadmap["production_ready"])
    assert any(item["system"] == "Website-owned apply/checkpoint/validation ownership" for item in roadmap["deprecated"])
