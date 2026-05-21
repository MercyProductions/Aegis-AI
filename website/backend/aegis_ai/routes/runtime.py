from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query

from ..core_bridge import AegisCoreBridge
from ..runtime_ownership import OWNERSHIP_SCHEMA_VERSION, ownership_matrix
from ..schemas import RuntimeHealthResponse
from ..security import trust_status
from ..services.core_client import AegisCoreClient, CoreDelegationResult
from ..settings import Settings


RuntimeHealthFactory = Callable[[], Awaitable[RuntimeHealthResponse]]
WorkspaceResolver = Callable[[str | None], Path]
CoreDataExtractor = Callable[[CoreDelegationResult, str], dict[str, Any]]


def register_runtime_routes(
    app: FastAPI,
    *,
    settings_factory: Callable[[], Settings],
    core_bridge_factory: Callable[[], AegisCoreBridge],
    core_runtime_client_factory: Callable[[], AegisCoreClient],
    workspace_resolver: WorkspaceResolver,
    runtime_health_factory: RuntimeHealthFactory,
    core_data_extractor: CoreDataExtractor,
) -> None:
    @app.get("/health", response_model=RuntimeHealthResponse, include_in_schema=False)
    @app.get("/api/health", response_model=RuntimeHealthResponse)
    async def health() -> RuntimeHealthResponse:
        return await runtime_health_factory()

    @app.get("/ready", response_model=RuntimeHealthResponse, include_in_schema=False)
    @app.get("/api/ready", response_model=RuntimeHealthResponse)
    async def ready() -> RuntimeHealthResponse:
        return await runtime_health_factory()

    @app.get("/api/core-runtime")
    async def core_runtime_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        status = await core_bridge_factory().shared_runtime_status(workspace)
        status["delegation"] = await core_runtime_client_factory().runtime_status(workspace)
        return status

    @app.get("/api/runtime/delegation")
    async def runtime_delegation_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        return await core_runtime_client_factory().runtime_status(workspace)

    @app.get("/api/runtime/ownership")
    async def runtime_ownership_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        return {
            "schema_version": OWNERSHIP_SCHEMA_VERSION,
            "workspace_root": str(workspace),
            "policy": {
                "core_api": "/v1",
                "website_api": "/api",
                "rule": "New shared runtime behavior starts in Aegis Core and is exposed through Website compatibility routes.",
                "compatibility": "Website /api response shapes remain stable while clients migrate to Core-owned contracts.",
            },
            "records": ownership_matrix(),
        }

    @app.get("/api/security/status")
    async def security_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        core_client = core_runtime_client_factory()
        if hasattr(core_client, "security_status"):
            core_result = await core_client.security_status(workspace)
        else:
            core_result = CoreDelegationResult(
                delegated=False,
                ok=False,
                reachable=False,
                status_code=None,
                kind="security.status",
                error="Aegis Core client does not expose security status yet.",
            )
        core_data = (
            core_data_extractor(core_result, "security.status")
            if core_result.delegated
            else {
                "connected": core_result.reachable,
                "error": core_result.error,
            }
        )
        return trust_status(settings_factory(), core_status=core_data)

    @app.get("/api/release/manifest")
    async def release_manifest_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        core_client = core_runtime_client_factory()
        result = await core_client.release_manifest(workspace)
        if not result.delegated:
            core_client.record_fallback("release.manifest", result.error or "Aegis Core release manifest is unavailable.")
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "error": result.error or "Aegis Core release manifest is unavailable.",
                "manifest": {},
            }
        return {"ok": bool(result.ok), "delegated": True, "manifest": core_data_extractor(result, "release.manifest")}

    @app.get("/api/release/compatibility")
    async def release_compatibility_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        workspace = workspace_resolver(workspace_root)
        core_client = core_runtime_client_factory()
        result = await core_client.check_compatibility(workspace)
        if not result.delegated:
            core_client.record_fallback("release.compatibility", result.error or "Aegis Core release compatibility is unavailable.")
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "compatible": False,
                "status": "unknown",
                "error": result.error or "Aegis Core release compatibility is unavailable.",
            }
        data = core_data_extractor(result, "release.compatibility")
        return {"ok": bool(result.ok), "delegated": True, **data}
