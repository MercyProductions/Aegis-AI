from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse


def register_agent_supervision_routes(
    app: FastAPI,
    *,
    agent_supervision_status: Callable[[str | None, str | None, int], Awaitable[dict[str, Any]]],
    agent_supervision_workflow_agents: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    agent_supervision_workflow_step: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    agent_supervision_delegate_agent: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    agent_supervision_workflow_events: Callable[
        [str, str | None, int, int, bool, int],
        Awaitable[StreamingResponse],
    ],
) -> None:
    @app.get("/api/agent-supervision")
    async def get_agent_supervision_status(
        workspace_root: str | None = Query(default=None),
        workflow_id: str | None = Query(default=None),
        limit: int = Query(default=30, ge=1, le=200),
    ) -> dict[str, Any]:
        return await agent_supervision_status(workspace_root, workflow_id, limit)

    @app.get("/api/agent-supervision/workflows/{workflow_id}/agents")
    async def get_agent_supervision_workflow_agents(
        workflow_id: str,
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await agent_supervision_workflow_agents(workflow_id, workspace_root)

    @app.post("/api/agent-supervision/workflows/{workflow_id}/step")
    async def post_agent_supervision_workflow_step(
        workflow_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        return await agent_supervision_workflow_step(workflow_id, request)

    @app.post("/api/agent-supervision/workflows/{workflow_id}/agents/delegate")
    async def post_agent_supervision_delegate_agent(
        workflow_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        return await agent_supervision_delegate_agent(workflow_id, request)

    @app.get("/api/agent-supervision/workflows/{workflow_id}/events")
    async def get_agent_supervision_workflow_events(
        workflow_id: str,
        workspace_root: str | None = Query(default=None),
        since: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        follow: bool = Query(default=True),
        max_seconds: int = Query(default=30, ge=1, le=120),
    ) -> StreamingResponse:
        return await agent_supervision_workflow_events(
            workflow_id,
            workspace_root,
            since,
            limit,
            follow,
            max_seconds,
        )
