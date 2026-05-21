from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    RecommendationActionRequest,
    RecommendationFixRequest,
    RecommendationFixResponse,
    ScheduledIntelligenceJob,
    ScheduledJobRunRequest,
    ScheduledJobRunResponse,
    WorkspaceOperationsScanRequest,
    WorkspaceOperationsSnapshot,
    WorkspaceRecommendation,
    WorkspaceSetupRequest,
    WorkspaceSetupResponse,
    WorkspaceWatchEvent,
)


def register_workspace_intelligence_routes(
    app: FastAPI,
    *,
    workspace_intelligence_snapshot: Callable[[str | None], Awaitable[WorkspaceOperationsSnapshot]],
    scan_workspace_intelligence: Callable[[WorkspaceOperationsScanRequest], Awaitable[WorkspaceOperationsSnapshot]],
    workspace_intelligence_events: Callable[[str | None, int], Awaitable[list[WorkspaceWatchEvent]]],
    workspace_intelligence_recommendations: Callable[
        [str | None, bool, int],
        Awaitable[list[WorkspaceRecommendation]],
    ],
    dismiss_workspace_recommendation: Callable[[str, RecommendationActionRequest | None], Awaitable[RecommendationFixResponse]],
    fix_workspace_recommendation: Callable[[str, RecommendationFixRequest | None], Awaitable[RecommendationFixResponse]],
    workspace_intelligence_jobs: Callable[[str | None], Awaitable[list[ScheduledIntelligenceJob]]],
    run_workspace_intelligence_jobs: Callable[[ScheduledJobRunRequest], Awaitable[ScheduledJobRunResponse]],
    workspace_setup: Callable[[WorkspaceSetupRequest], Awaitable[WorkspaceSetupResponse]],
) -> None:
    @app.get("/api/workspace-intelligence", response_model=WorkspaceOperationsSnapshot)
    async def get_workspace_intelligence(
        workspace_root: str | None = Query(default=None),
    ) -> WorkspaceOperationsSnapshot:
        return await workspace_intelligence_snapshot(workspace_root)

    @app.post("/api/workspace-intelligence/scan", response_model=WorkspaceOperationsSnapshot)
    async def scan_workspace_intelligence_route(
        request: WorkspaceOperationsScanRequest,
    ) -> WorkspaceOperationsSnapshot:
        return await scan_workspace_intelligence(request)

    @app.get("/api/workspace-intelligence/events", response_model=list[WorkspaceWatchEvent])
    async def get_workspace_intelligence_events(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=80, ge=1, le=300),
    ) -> list[WorkspaceWatchEvent]:
        return await workspace_intelligence_events(workspace_root, limit)

    @app.get("/api/workspace-intelligence/recommendations", response_model=list[WorkspaceRecommendation])
    async def get_workspace_intelligence_recommendations(
        workspace_root: str | None = Query(default=None),
        include_dismissed: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=300),
    ) -> list[WorkspaceRecommendation]:
        return await workspace_intelligence_recommendations(workspace_root, include_dismissed, limit)

    @app.post("/api/workspace-intelligence/recommendations/{recommendation_id}/dismiss", response_model=RecommendationFixResponse)
    async def dismiss_workspace_recommendation_route(
        recommendation_id: str,
        request: RecommendationActionRequest | None = None,
    ) -> RecommendationFixResponse:
        return await dismiss_workspace_recommendation(recommendation_id, request)

    @app.post("/api/workspace-intelligence/recommendations/{recommendation_id}/fix", response_model=RecommendationFixResponse)
    async def fix_workspace_recommendation_route(
        recommendation_id: str,
        request: RecommendationFixRequest | None = None,
    ) -> RecommendationFixResponse:
        return await fix_workspace_recommendation(recommendation_id, request)

    @app.get("/api/workspace-intelligence/jobs", response_model=list[ScheduledIntelligenceJob])
    async def get_workspace_intelligence_jobs(
        workspace_root: str | None = Query(default=None),
    ) -> list[ScheduledIntelligenceJob]:
        return await workspace_intelligence_jobs(workspace_root)

    @app.post("/api/workspace-intelligence/jobs/run", response_model=ScheduledJobRunResponse)
    async def run_workspace_intelligence_jobs_route(
        request: ScheduledJobRunRequest,
    ) -> ScheduledJobRunResponse:
        return await run_workspace_intelligence_jobs(request)

    @app.post("/api/workspace/setup", response_model=WorkspaceSetupResponse)
    async def workspace_setup_route(request: WorkspaceSetupRequest) -> WorkspaceSetupResponse:
        return await workspace_setup(request)
