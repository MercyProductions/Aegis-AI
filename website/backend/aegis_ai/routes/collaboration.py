from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query


def register_collaboration_routes(
    app: FastAPI,
    *,
    api_collaboration_dashboard: Callable[[str | None, str | None, str | None, int], Awaitable[dict[str, Any]]],
    api_register_collaboration_member: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_register_collaboration_repository: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_create_collaboration_workflow: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_collaboration_workflow_action: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    api_create_collaboration_approval: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_decide_collaboration_approval: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    api_assign_collaboration_roadmap_item: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/collaboration")
    async def get_collaboration_dashboard(
        workspace_root: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        role: str | None = Query(default=None),
        limit: int = Query(default=100),
    ) -> dict[str, Any]:
        return await api_collaboration_dashboard(workspace_root, user_id, role, limit)

    @app.post("/api/collaboration/members")
    async def register_collaboration_member(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_register_collaboration_member(payload)

    @app.post("/api/collaboration/repositories")
    async def register_collaboration_repository(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_register_collaboration_repository(payload)

    @app.post("/api/collaboration/workflows")
    async def create_collaboration_workflow(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_create_collaboration_workflow(payload)

    @app.post("/api/collaboration/workflows/{workflow_id}/action")
    async def collaboration_workflow_action(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await api_collaboration_workflow_action(workflow_id, payload)

    @app.post("/api/collaboration/approvals")
    async def create_collaboration_approval(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_create_collaboration_approval(payload)

    @app.post("/api/collaboration/approvals/{approval_id}/decision")
    async def decide_collaboration_approval(approval_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await api_decide_collaboration_approval(approval_id, payload)

    @app.post("/api/collaboration/roadmap/items")
    async def assign_collaboration_roadmap_item(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_assign_collaboration_roadmap_item(payload)
