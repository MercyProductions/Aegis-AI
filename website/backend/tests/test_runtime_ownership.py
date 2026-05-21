from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.runtime_ownership import OWNERSHIP_SCHEMA_VERSION, ownership_matrix, ownership_records
from aegis_ai.services.core_client import DELEGATED_WORKFLOWS


REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_PHASE_TWO_DOMAINS = {
    "memory",
    "validation",
    "checkpoints",
    "changes-apply",
    "model-routing",
    "model-registry",
    "diagnostics",
    "tasks-workflows",
    "agent-runtime",
    "workspace-intelligence",
}


def test_runtime_ownership_matrix_covers_phase_two_domains() -> None:
    records = ownership_records()
    domains = {record.domain for record in records}

    assert REQUIRED_PHASE_TWO_DOMAINS.issubset(domains)
    assert len(domains) == len(records)

    for record in records:
        assert record.owner in {"aegis-core", "website", "compatibility"}
        assert record.summary
        assert record.fallback
        assert record.migration_rule
        assert record.website_routes
        assert all(route.startswith("/api/") for route in record.website_routes)
        assert all(route.startswith("/v1/") for route in record.core_routes)


def test_delegated_workflows_declared_by_ownership_matrix_are_supported() -> None:
    delegated = {
        workflow
        for record in ownership_records()
        for workflow in record.delegated_workflows
    }

    missing = delegated.difference(DELEGATED_WORKFLOWS)

    assert not missing


def test_runtime_ownership_endpoint_returns_static_contract(tmp_path: Path) -> None:
    client = TestClient(main.app)
    response = client.get("/api/runtime/ownership", params={"workspace_root": str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == OWNERSHIP_SCHEMA_VERSION
    assert payload["workspace_root"] == str(tmp_path.resolve())
    assert payload["policy"]["core_api"] == "/v1"
    assert payload["policy"]["website_api"] == "/api"
    assert payload["records"] == ownership_matrix()


def test_ownership_docs_link_machine_readable_source() -> None:
    ownership_doc = (REPO_ROOT / "docs" / "CORE_WEBSITE_OWNERSHIP.md").read_text(encoding="utf-8")
    adapter_doc = (REPO_ROOT / "WEBSITE_CORE_ADAPTER.md").read_text(encoding="utf-8")
    consolidation_doc = (REPO_ROOT / "RUNTIME_CONSOLIDATION.md").read_text(encoding="utf-8")

    assert "website/backend/aegis_ai/runtime_ownership.py" in ownership_doc
    assert "GET /api/runtime/ownership" in ownership_doc
    assert "docs/CORE_WEBSITE_OWNERSHIP.md" in adapter_doc
    assert "GET /api/runtime/ownership" in adapter_doc
    assert "docs/CORE_WEBSITE_OWNERSHIP.md" in consolidation_doc


def test_client_surfaces_align_with_current_migration_posture() -> None:
    frontend_api = (REPO_ROOT / "website" / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
    desktop_client = (REPO_ROOT / "src" / "AegisClient.cpp").read_text(encoding="utf-8")
    vscode_extension = (REPO_ROOT / "vscode-plugins" / "aegis-local-autopilot" / "extension.js").read_text(encoding="utf-8")
    visual_studio_core_client = (
        REPO_ROOT
        / "visual-studio-extensions"
        / "aegis-local-agent-vs"
        / "src"
        / "AegisLocalAgentVs"
        / "Services"
        / "AegisCoreClient.cs"
    ).read_text(encoding="utf-8")

    for route in ("/api/apply", "/api/checkpoints", "/api/validate", "/api/models", "/api/memory"):
        assert route in frontend_api
        assert route in desktop_client

    for route in (
        "/v1/workspaces/scan",
        "/v1/models/route",
        "/v1/changes/apply",
        "/v1/checkpoints",
        "/v1/checkpoints/restore",
        "/v1/validation/run",
    ):
        assert route in visual_studio_core_client

    assert "/v1/tasks" in vscode_extension
