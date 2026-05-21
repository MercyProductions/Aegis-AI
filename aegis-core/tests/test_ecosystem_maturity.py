from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.ecosystem_maturity import (
    api_stability,
    contributor_ecosystem,
    ecosystem_maturity,
    ecosystem_observability,
    ecosystem_strategy,
    maintainability_guidance,
    platform_reputation,
    plugin_ecosystem_quality,
    release_cadence,
    showcase_experiences,
    sustainability_plan,
    trust_transparency,
    workflow_excellence,
)
from aegis_core.memory import ProjectMemory
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"ecosystem-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "package.json").write_text(
            json.dumps({"name": "ecosystem-test", "scripts": {"test": "pytest", "build": "echo build"}}),
            encoding="utf-8",
        )
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def main():\n    return 42\n", encoding="utf-8")
        plugin_root = root / ".aegis" / "plugins" / "quality-plugin"
        plugin_root.mkdir(parents=True)
        (plugin_root / "aegis-plugin.json").write_text(
            json.dumps(
                {
                    "id": "quality-plugin",
                    "name": "Quality Plugin",
                    "version": "1.0.0",
                    "category": "validators",
                    "description": "Test validator plugin.",
                    "permission_scopes": ["filesystem_read", "workspace_scan"],
                    "runtime_compatibility": {"min_core_version": "0.1.0"},
                    "tools": [{"name": "quality.hint", "handler": "builtin.validation_hint", "input_schema": {}, "output_schema": {}}],
                }
            ),
            encoding="utf-8",
        )
        memory = ProjectMemory(root)
        memory.write_json("workflow-history.json", [{"id": "wf-1", "status": "completed"}])
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_ecosystem_strategy_and_api_stability_define_maturity_direction() -> None:
    strategy = ecosystem_strategy()
    stability = api_stability()
    cadence = release_cadence()
    plan = sustainability_plan()

    assert any(item["segment"] == "solo_local_engineers" for item in strategy["core_audience"])
    assert "Curated local-first plugins before a broad marketplace." in strategy["plugin_ecosystem_direction"]
    assert "ecosystem.dashboard" in stability["stable_apis"]
    assert any(channel["id"] == "stable" for channel in cadence["channels"])
    assert "Require plugin API version metadata." in plan["plugin_migration_strategy"]


def test_workflow_plugin_observability_and_maturity_scores(workspace_fixture: Path) -> None:
    workflows = workflow_excellence(workspace_fixture)
    plugins = plugin_ecosystem_quality(workspace_fixture)
    observability = ecosystem_observability(workspace_fixture, persist=True)
    maturity = ecosystem_maturity(workspace_fixture, persist=True)

    assert workflows["workflows"]
    assert any(item["id"] == "implement_feature" for item in workflows["workflows"])
    assert plugins["quality_summary"]["plugin_count"] >= 1
    assert any("manifest-valid" in item["badges"] for item in plugins["plugins"])
    assert observability["local_first"] is True
    assert (ProjectMemory(workspace_fixture).root / "ecosystem-observability.json").is_file()
    assert maturity["maturity_scores"]["overall"] > 0
    assert "workflow_excellence" in maturity
    assert (ProjectMemory(workspace_fixture).root / "ecosystem-maturity.json").is_file()


def test_contributor_reputation_maintainability_showcases_and_trust(workspace_fixture: Path) -> None:
    contributor = contributor_ecosystem(workspace_fixture)
    reputation = platform_reputation(workspace_fixture)
    maintainability = maintainability_guidance(workspace_fixture)
    showcases = showcase_experiences(workspace_fixture)
    trust = trust_transparency(workspace_fixture)

    assert "docs/PLUGIN_ECOSYSTEM.md" in contributor["contributor_guides"]
    assert "release_quality_standards" in reputation
    assert "duplicate Website/Desktop/IDE runtime ownership" in maintainability["reduce"]
    assert any(item["id"] == "plugin_workflow" for item in showcases["showcases"])
    assert "how to rollback" in trust["always_explain"]


def test_ecosystem_endpoints_are_contract_wrapped(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    endpoints = [
        ("/v1/ecosystem/strategy", {}, "ecosystem.strategy"),
        ("/v1/ecosystem/workflow-excellence", {"workspace": str(workspace_fixture)}, "ecosystem.workflow_excellence"),
        ("/v1/ecosystem/plugin-quality", {"workspace": str(workspace_fixture)}, "ecosystem.plugin_quality"),
        ("/v1/ecosystem/api-stability", {}, "ecosystem.api_stability"),
        ("/v1/ecosystem/contributor", {"workspace": str(workspace_fixture)}, "ecosystem.contributor"),
        ("/v1/ecosystem/reputation", {"workspace": str(workspace_fixture)}, "ecosystem.reputation"),
        ("/v1/ecosystem/release-cadence", {}, "ecosystem.release_cadence"),
        ("/v1/ecosystem/observability", {"workspace": str(workspace_fixture)}, "ecosystem.observability"),
        ("/v1/ecosystem/maintainability", {"workspace": str(workspace_fixture)}, "ecosystem.maintainability"),
        ("/v1/ecosystem/showcases", {"workspace": str(workspace_fixture)}, "ecosystem.showcases"),
        ("/v1/ecosystem/trust", {"workspace": str(workspace_fixture)}, "ecosystem.trust"),
        ("/v1/ecosystem/sustainability-plan", {}, "ecosystem.sustainability_plan"),
    ]
    for path, params, kind in endpoints:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_kind(response.json(), kind)

    observability = client.post("/v1/ecosystem/observability", json={"workspace": str(workspace_fixture), "persist": True})
    assert observability.status_code == 200
    assert_kind(observability.json(), "ecosystem.observability")

    maturity = client.post("/v1/ecosystem/maturity", json={"workspace": str(workspace_fixture), "persist": False})
    assert maturity.status_code == 200
    assert_kind(maturity.json(), "ecosystem.maturity")


def test_ecosystem_contracts_are_registered() -> None:
    required = {
        "ecosystem.strategy",
        "ecosystem.workflow_excellence",
        "ecosystem.plugin_quality",
        "ecosystem.api_stability",
        "ecosystem.contributor",
        "ecosystem.reputation",
        "ecosystem.release_cadence",
        "ecosystem.observability",
        "ecosystem.maintainability",
        "ecosystem.showcases",
        "ecosystem.trust",
        "ecosystem.sustainability_plan",
        "ecosystem.maturity",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
