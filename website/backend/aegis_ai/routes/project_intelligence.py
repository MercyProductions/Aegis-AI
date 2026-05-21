from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    ProjectContextSelectionRequest,
    ProjectContextSelectionResponse,
    ProjectIntelligenceReindexRequest,
    ProjectIntelligenceSnapshot,
)


def register_project_intelligence_routes(
    app: FastAPI,
    *,
    project_intelligence_snapshot: Callable[[str | None], Awaitable[ProjectIntelligenceSnapshot]],
    reindex_project_intelligence: Callable[[ProjectIntelligenceReindexRequest], Awaitable[ProjectIntelligenceSnapshot]],
    project_intelligence_context: Callable[[ProjectContextSelectionRequest], Awaitable[ProjectContextSelectionResponse]],
) -> None:
    @app.get("/api/project-intelligence", response_model=ProjectIntelligenceSnapshot)
    async def get_project_intelligence(
        workspace_root: str | None = Query(default=None),
    ) -> ProjectIntelligenceSnapshot:
        return await project_intelligence_snapshot(workspace_root)

    @app.post("/api/project-intelligence/reindex", response_model=ProjectIntelligenceSnapshot)
    async def reindex_project_intelligence_route(
        request: ProjectIntelligenceReindexRequest,
    ) -> ProjectIntelligenceSnapshot:
        return await reindex_project_intelligence(request)

    @app.post("/api/project-intelligence/context", response_model=ProjectContextSelectionResponse)
    async def project_intelligence_context_route(
        request: ProjectContextSelectionRequest,
    ) -> ProjectContextSelectionResponse:
        return await project_intelligence_context(request)
