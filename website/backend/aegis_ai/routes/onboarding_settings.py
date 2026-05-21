from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query


def register_onboarding_settings_routes(
    app: FastAPI,
    *,
    onboarding_status: Callable[[str | None], Awaitable[dict[str, Any]]],
    update_onboarding: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    run_onboarding_first_workflow: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    export_runtime_settings: Callable[[str | None], Awaitable[dict[str, Any]]],
    import_runtime_settings: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/onboarding/status")
    async def get_onboarding_status(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await onboarding_status(workspace_root)

    @app.post("/api/onboarding")
    async def post_onboarding(request: dict[str, Any]) -> dict[str, Any]:
        return await update_onboarding(request)

    @app.post("/api/onboarding/first-workflow")
    async def post_onboarding_first_workflow(request: dict[str, Any]) -> dict[str, Any]:
        return await run_onboarding_first_workflow(request)

    @app.get("/api/settings/export")
    async def get_runtime_settings_export(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await export_runtime_settings(workspace_root)

    @app.post("/api/settings/import")
    async def post_runtime_settings_import(request: dict[str, Any]) -> dict[str, Any]:
        return await import_runtime_settings(request)
