from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query

from ..schemas import WorkspaceAutopilotStatusResponse


def register_autopilot_routes(
    app: FastAPI,
    *,
    workspace_autopilot_status: Callable[[str | None], Awaitable[WorkspaceAutopilotStatusResponse]],
    api_autopilot_modes: Callable[[], Awaitable[dict[str, Any]]],
    api_autopilot_supervision: Callable[[str | None, str | None], Awaitable[dict[str, Any]]],
    api_start_autopilot: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_autopilot_action: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    api_autopilot_replay: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    api_autopilot_observability: Callable[[str | None], Awaitable[dict[str, Any]]],
    api_autopilot_memory: Callable[[str | None], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/workspace/autopilot-status", response_model=WorkspaceAutopilotStatusResponse)
    async def get_workspace_autopilot_status(
        workspace_root: str | None = Query(default=None),
    ) -> WorkspaceAutopilotStatusResponse:
        return await workspace_autopilot_status(workspace_root)

    @app.get("/api/autopilot/modes")
    async def get_autopilot_modes() -> dict[str, Any]:
        return await api_autopilot_modes()

    @app.get("/api/autopilot/supervision")
    async def get_autopilot_supervision(
        workspace_root: str | None = Query(default=None),
        autopilot_id: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await api_autopilot_supervision(workspace_root, autopilot_id)

    @app.post("/api/autopilot/start")
    async def start_autopilot(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_start_autopilot(payload)

    @app.post("/api/autopilot/runs/{autopilot_id}/action")
    async def autopilot_action(autopilot_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await api_autopilot_action(autopilot_id, payload)

    @app.get("/api/autopilot/runs/{autopilot_id}/replay")
    async def get_autopilot_replay(
        autopilot_id: str,
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await api_autopilot_replay(autopilot_id, workspace_root)

    @app.get("/api/autopilot/observability")
    async def get_autopilot_observability(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await api_autopilot_observability(workspace_root)

    @app.get("/api/autopilot/memory")
    async def get_autopilot_memory(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
        return await api_autopilot_memory(workspace_root)
