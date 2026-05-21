from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.memory import ProjectMemory
from aegis_core.platform_foundation import (
    create_platform_archive,
    ecosystem_dependency_management,
    platform_governance,
    platform_health_analytics,
    platform_migration_status,
    platform_sustainability,
    roadmap_governance,
    run_platform_migrations,
    subsystem_ownership,
    validate_platform_compatibility,
)
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"platform-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "package.json").write_text(
            json.dumps({"name": "platform-test", "scripts": {"test": "pytest", "build": "echo build"}}),
            encoding="utf-8",
        )
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def main():\n    return 42\n", encoding="utf-8")
        memory = ProjectMemory(root)
        memory.write_json("workflow-history.json", [{"id": "wf-1", "status": "completed"}])
        memory.write_generated_markdown("roadmap.md", "Roadmap", "- Keep platform sustainable.")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_platform_governance_and_ownership_define_boundaries() -> None:
    governance = platform_governance()
    ownership = subsystem_ownership()
    roadmap = roadmap_governance()

    assert governance["versioning_policy"]["core_schema_version"] == "2026.05.12"
    assert "migration_that_rewrites_state" in governance["security_review_required_for"]
    assert any(item["id"] == "stable_core_runtime" for item in ownership["subsystems"])
    assert "Website-owned apply/checkpoint/validation authority" in roadmap["deprecated_systems"]


def test_platform_migrations_support_dry_run_and_apply(workspace_fixture: Path) -> None:
    initial = platform_migration_status(workspace_fixture)
    dry_run = run_platform_migrations(workspace_fixture, dry_run=True)
    applied = run_platform_migrations(workspace_fixture, dry_run=False)
    final = platform_migration_status(workspace_fixture)

    assert initial["pending"]
    assert dry_run["dry_run"] is True
    assert dry_run["pending"]
    assert applied["migration_count"] >= 7
    assert not final["pending"]
    assert (ProjectMemory(workspace_fixture).root / "platform-state.json").is_file()
    assert (ProjectMemory(workspace_fixture).root / "checkpoint-format-manifest.json").is_file()


def test_platform_compatibility_dependencies_and_health(workspace_fixture: Path) -> None:
    compatibility = validate_platform_compatibility(
        workspace_fixture,
        client_reports=[
            {
                "client_type": "website",
                "client_version": "0.1.0",
                "schema_version": "2026.05.12",
                "capabilities": ["release-compatibility"],
            }
        ],
        include_plugins=True,
        persist=True,
    )
    dependencies = ecosystem_dependency_management(workspace_fixture)
    health = platform_health_analytics(workspace_fixture, persist=True)

    check_ids = {check["id"] for check in compatibility["checks"]}
    assert {"api_compatibility", "client_compatibility", "plugin_compatibility", "orchestration_compatibility", "runtime_compatibility"}.issubset(check_ids)
    assert compatibility["summary"]["blocked"] == 0
    assert (ProjectMemory(workspace_fixture).root / "platform-compatibility-report.json").is_file()
    assert "plugin_dependencies" in dependencies
    assert health["overall_status"] in {"pass", "warning", "blocked"}
    assert (ProjectMemory(workspace_fixture).root / "platform-health.json").is_file()


def test_platform_archive_creates_recovery_manifest(workspace_fixture: Path) -> None:
    archive = create_platform_archive(
        workspace_fixture,
        include_memory=True,
        include_workflows=True,
        include_knowledge=False,
        dry_run=False,
        reason="sustainability test with token=secret-value",
    )

    assert archive["persisted"] is True
    assert archive["entry_count"] >= 1
    manifest = Path(archive["archive_path"]) / "manifest.json"
    text = manifest.read_text(encoding="utf-8")
    assert "secret-value" not in text
    assert "recovery_guidance" in archive


def test_platform_sustainability_aggregates_foundation(workspace_fixture: Path) -> None:
    dashboard = platform_sustainability(workspace_fixture, persist=True)

    assert dashboard["governance"]["purpose"] == "long_term_platform_foundation"
    assert dashboard["migrations"]["pending"]
    assert dashboard["compatibility"]["checks"]
    assert dashboard["archival"]["endpoint"] == "/v1/platform/archive"
    assert (ProjectMemory(workspace_fixture).root / "platform-sustainability.json").is_file()


def test_platform_endpoints_are_contract_wrapped(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    endpoints = [
        ("/v1/platform/governance", {}, "platform.governance"),
        ("/v1/platform/migrations", {"workspace": str(workspace_fixture)}, "platform.migrations"),
        ("/v1/platform/ownership", {}, "platform.ownership"),
        ("/v1/platform/dependencies", {"workspace": str(workspace_fixture)}, "platform.dependencies"),
        ("/v1/platform/release-engineering", {"workspace": str(workspace_fixture)}, "platform.release_engineering"),
        ("/v1/platform/health", {"workspace": str(workspace_fixture)}, "platform.health"),
        ("/v1/platform/tooling", {"workspace": str(workspace_fixture)}, "platform.tooling"),
        ("/v1/platform/roadmap", {}, "platform.roadmap"),
    ]
    for path, params, kind in endpoints:
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        assert_kind(response.json(), kind)

    compatibility = client.post(
        "/v1/platform/compatibility/validate",
        json={"workspace": str(workspace_fixture), "client_reports": [{"client_type": "website", "client_version": "0.1.0", "schema_version": "2026.05.12"}]},
    )
    assert compatibility.status_code == 200
    assert_kind(compatibility.json(), "platform.compatibility")

    migrations = client.post("/v1/platform/migrations/run", json={"workspace": str(workspace_fixture), "dry_run": True})
    assert migrations.status_code == 200
    assert_kind(migrations.json(), "platform.migrations")

    archive = client.post("/v1/platform/archive", json={"workspace": str(workspace_fixture), "dry_run": True})
    assert archive.status_code == 200
    assert_kind(archive.json(), "platform.archive")

    sustainability = client.post("/v1/platform/sustainability", json={"workspace": str(workspace_fixture), "persist": False})
    assert sustainability.status_code == 200
    assert_kind(sustainability.json(), "platform.sustainability")


def test_platform_contracts_are_registered() -> None:
    required = {
        "platform.governance",
        "platform.migrations",
        "platform.compatibility",
        "platform.ownership",
        "platform.dependencies",
        "platform.release_engineering",
        "platform.health",
        "platform.tooling",
        "platform.roadmap",
        "platform.archive",
        "platform.sustainability",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
