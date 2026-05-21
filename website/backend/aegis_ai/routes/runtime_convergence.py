from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    AegisContinuitySnapshot,
    GlobalCommandRequest,
    GlobalCommandResponse,
    ModelInventoryResponse,
    OperatingEnvironmentActionRequest,
    OperatingEnvironmentActionResponse,
    OperatingEnvironmentSnapshot,
    PlatformDisciplineSnapshot,
    TimelineSearchRequest,
    TimelineSearchResponse,
    UnifiedContextSearchRequest,
    UnifiedContextSearchResponse,
    UnifiedContextSnapshot,
    UnifiedRuntimeSnapshot,
)


def register_runtime_convergence_routes(
    app: FastAPI,
    *,
    unified_runtime_status: Callable[[str | None], Awaitable[UnifiedRuntimeSnapshot]],
    operating_environment_status: Callable[[str | None], Awaitable[OperatingEnvironmentSnapshot]],
    operating_environment_action_preview: Callable[
        [OperatingEnvironmentActionRequest],
        Awaitable[OperatingEnvironmentActionResponse],
    ],
    unified_context_status: Callable[[str | None], Awaitable[UnifiedContextSnapshot]],
    unified_context_search: Callable[[UnifiedContextSearchRequest], Awaitable[UnifiedContextSearchResponse]],
    global_command_preview: Callable[[GlobalCommandRequest], Awaitable[GlobalCommandResponse]],
    global_command_submit: Callable[[GlobalCommandRequest], Awaitable[GlobalCommandResponse]],
    continuity_status: Callable[[str | None], Awaitable[AegisContinuitySnapshot]],
    continuity_timeline_search: Callable[[TimelineSearchRequest], Awaitable[TimelineSearchResponse]],
    platform_discipline_status: Callable[[str | None], Awaitable[PlatformDisciplineSnapshot]],
    models: Callable[[], Awaitable[ModelInventoryResponse]],
) -> None:
    @app.get("/api/unified-runtime", response_model=UnifiedRuntimeSnapshot)
    async def get_unified_runtime_status(
        workspace_root: str | None = Query(default=None),
    ) -> UnifiedRuntimeSnapshot:
        return await unified_runtime_status(workspace_root)

    @app.get("/api/operating-environment", response_model=OperatingEnvironmentSnapshot)
    async def get_operating_environment_status(
        workspace_root: str | None = Query(default=None),
    ) -> OperatingEnvironmentSnapshot:
        return await operating_environment_status(workspace_root)

    @app.post("/api/operating-environment/actions/preview", response_model=OperatingEnvironmentActionResponse)
    async def post_operating_environment_action_preview(
        request: OperatingEnvironmentActionRequest,
    ) -> OperatingEnvironmentActionResponse:
        return await operating_environment_action_preview(request)

    @app.get("/api/unified-context", response_model=UnifiedContextSnapshot)
    async def get_unified_context_status(
        workspace_root: str | None = Query(default=None),
    ) -> UnifiedContextSnapshot:
        return await unified_context_status(workspace_root)

    @app.post("/api/unified-context/search", response_model=UnifiedContextSearchResponse)
    async def post_unified_context_search(request: UnifiedContextSearchRequest) -> UnifiedContextSearchResponse:
        return await unified_context_search(request)

    @app.post("/api/global-command/preview", response_model=GlobalCommandResponse)
    async def post_global_command_preview(request: GlobalCommandRequest) -> GlobalCommandResponse:
        return await global_command_preview(request)

    @app.post("/api/global-command/submit", response_model=GlobalCommandResponse)
    async def post_global_command_submit(request: GlobalCommandRequest) -> GlobalCommandResponse:
        return await global_command_submit(request)

    @app.get("/api/continuity", response_model=AegisContinuitySnapshot)
    async def get_continuity_status(
        workspace_root: str | None = Query(default=None),
    ) -> AegisContinuitySnapshot:
        return await continuity_status(workspace_root)

    @app.post("/api/continuity/timeline/search", response_model=TimelineSearchResponse)
    async def post_continuity_timeline_search(request: TimelineSearchRequest) -> TimelineSearchResponse:
        return await continuity_timeline_search(request)

    @app.get("/api/platform-discipline", response_model=PlatformDisciplineSnapshot)
    async def get_platform_discipline_status(
        workspace_root: str | None = Query(default=None),
    ) -> PlatformDisciplineSnapshot:
        return await platform_discipline_status(workspace_root)

    @app.get("/api/models", response_model=ModelInventoryResponse)
    async def get_models() -> ModelInventoryResponse:
        return await models()
