from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import CORE_CONTRACT_VERSION
from aegis_core.release import check_compatibility, migration_status, release_manifest, run_migrations, update_plan
from aegis_core.server import create_app


def test_release_manifest_contains_all_client_components() -> None:
    manifest = release_manifest()

    assert manifest["schema_version"] == CORE_CONTRACT_VERSION
    assert set(manifest["components"]).issuperset(
        {"aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension"}
    )
    assert manifest["compatibility"]["minimum_clients"]["desktop"] == "0.2.0"
    assert manifest["update_policy"]["rollback_on_failure"] is True


def test_release_compatibility_blocks_old_client() -> None:
    result = check_compatibility("desktop", "0.0.1", schema_version=CORE_CONTRACT_VERSION)

    assert result["compatible"] is False
    assert result["status"] == "blocked"
    assert any("minimum compatible version" in blocker for blocker in result["blockers"])


def test_release_migrations_dry_run_and_apply(tmp_path: Path) -> None:
    workspace = tmp_path / "release-workspace"
    workspace.mkdir()

    dry_run = run_migrations(workspace, dry_run=True)
    assert dry_run["dry_run"] is True
    assert len(dry_run["pending"]) == 4
    assert not (workspace / ".aegis" / "release-migrations.json").exists()

    applied = run_migrations(workspace)
    assert applied["dry_run"] is False
    assert len(applied["applied"]) == 4
    assert (workspace / ".aegis" / "release-state.json").is_file()
    assert (workspace / ".aegis" / "config.json").is_file()
    assert (workspace / ".aegis" / "model-registry-state.json").is_file()
    assert (workspace / ".aegis" / "database-migrations.json").is_file()

    after = migration_status(workspace)
    assert after["pending"] == []


def test_release_update_plan_requires_checksum_and_lists_rollback() -> None:
    blocked = update_plan("not-a-component")

    assert blocked["status"] == "blocked"
    assert any("unknown component" in blocker.lower() for blocker in blocked["blockers"])
    assert blocked["rollback"]["available"] is True

    ready = update_plan("desktop", sha256="1" * 64)
    assert ready["status"] == "ready"
    assert [step["id"] for step in ready["steps"]][:3] == ["inspect_manifest", "download_package", "verify_package"]
    assert ready["trust"]["checksum_required"] is True
    assert ready["trust"]["downgrade_protection"] is True


def test_release_update_plan_blocks_bad_checksums_and_downgrades() -> None:
    bad_checksum = update_plan("desktop", current_version="0.2.0", target_version="0.2.0", sha256="not-a-hash")
    downgrade = update_plan("desktop", current_version="9.0.0", target_version="0.2.0", sha256="2" * 64)

    assert bad_checksum["status"] == "blocked"
    assert any("sha256" in blocker.lower() for blocker in bad_checksum["blockers"])
    assert downgrade["status"] == "blocked"
    assert any("downgrade protection" in blocker.lower() for blocker in downgrade["blockers"])


def test_release_endpoints_return_versioned_contracts(tmp_path: Path) -> None:
    workspace = tmp_path / "api-release-workspace"
    workspace.mkdir()
    client = TestClient(create_app())

    manifest = client.get("/v1/release/manifest", params={"workspace": str(workspace)})
    assert manifest.status_code == 200
    assert manifest.json()["kind"] == "release.manifest"

    compatibility = client.post(
        "/v1/release/compatibility",
        json={
            "workspace": str(workspace),
            "client_type": "vscode-extension",
            "client_version": "0.1.8",
            "schema_version": CORE_CONTRACT_VERSION,
            "capabilities": ["release-compatibility"],
        },
    )
    assert compatibility.status_code == 200
    assert compatibility.json()["kind"] == "release.compatibility"
    assert compatibility.json()["data"]["compatible"] is True

    migrations = client.post("/v1/release/migrations/run", json={"workspace": str(workspace), "dry_run": True})
    assert migrations.status_code == 200
    assert migrations.json()["kind"] == "release.migrations.run"
