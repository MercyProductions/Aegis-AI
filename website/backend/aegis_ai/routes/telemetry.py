from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    FallbackInspectorResponse,
    FeedbackTelemetryResponse,
    ModelRouteHealthInfo,
    RoutePolicyDiffResponse,
    RouteQualityResponse,
    TelemetryResponse,
    TelemetrySnapshotResponse,
)


def register_telemetry_routes(
    app: FastAPI,
    *,
    telemetry: Callable[[str | None, int], Awaitable[TelemetryResponse]],
    route_quality: Callable[[str | None, int], Awaitable[RouteQualityResponse]],
    route_health: Callable[[str | None, int], Awaitable[list[ModelRouteHealthInfo]]],
    fallback_inspector: Callable[[str | None, int], Awaitable[FallbackInspectorResponse]],
    feedback_telemetry: Callable[[str | None, int], Awaitable[FeedbackTelemetryResponse]],
    telemetry_snapshot: Callable[
        [str | None, int, int, int, int, bool, bool, int, int],
        Awaitable[TelemetrySnapshotResponse],
    ],
    refresh_telemetry_snapshot: Callable[
        [str | None, int, int, int, int, bool, int, int],
        Awaitable[TelemetrySnapshotResponse],
    ],
    route_policy_diff: Callable[[str | None, int, bool, int, int], Awaitable[RoutePolicyDiffResponse]],
) -> None:
    @app.get("/api/telemetry", response_model=TelemetryResponse)
    async def get_telemetry(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> TelemetryResponse:
        return await telemetry(workspace_root, limit)

    @app.get("/api/telemetry/route-quality", response_model=RouteQualityResponse)
    async def get_route_quality(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> RouteQualityResponse:
        return await route_quality(workspace_root, limit)

    @app.get("/api/telemetry/route-health", response_model=list[ModelRouteHealthInfo])
    async def get_route_health(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[ModelRouteHealthInfo]:
        return await route_health(workspace_root, limit)

    @app.get("/api/telemetry/fallback-inspector", response_model=FallbackInspectorResponse)
    async def get_fallback_inspector(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> FallbackInspectorResponse:
        return await fallback_inspector(workspace_root, limit)

    @app.get("/api/telemetry/feedback", response_model=FeedbackTelemetryResponse)
    async def get_feedback_telemetry(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> FeedbackTelemetryResponse:
        return await feedback_telemetry(workspace_root, limit)

    @app.get("/api/telemetry/snapshot", response_model=TelemetrySnapshotResponse)
    async def get_telemetry_snapshot(
        workspace_root: str | None = Query(default=None),
        route_quality_limit: int = Query(default=200, ge=1, le=500),
        fallback_limit: int = Query(default=20, ge=1, le=100),
        feedback_limit: int = Query(default=100, ge=1, le=500),
        stale_after_seconds: int = Query(default=900, ge=60, le=86400),
        refresh: bool = Query(default=False),
        prune: bool = Query(default=False),
        max_snapshots: int = Query(default=12, ge=1, le=250),
        retention_days: int = Query(default=30, ge=1, le=3650),
    ) -> TelemetrySnapshotResponse:
        return await telemetry_snapshot(
            workspace_root,
            route_quality_limit,
            fallback_limit,
            feedback_limit,
            stale_after_seconds,
            refresh,
            prune,
            max_snapshots,
            retention_days,
        )

    @app.post("/api/telemetry/snapshot/refresh", response_model=TelemetrySnapshotResponse)
    async def post_telemetry_snapshot_refresh(
        workspace_root: str | None = Query(default=None),
        route_quality_limit: int = Query(default=200, ge=1, le=500),
        fallback_limit: int = Query(default=20, ge=1, le=100),
        feedback_limit: int = Query(default=100, ge=1, le=500),
        stale_after_seconds: int = Query(default=900, ge=60, le=86400),
        prune: bool = Query(default=True),
        max_snapshots: int = Query(default=12, ge=1, le=250),
        retention_days: int = Query(default=30, ge=1, le=3650),
    ) -> TelemetrySnapshotResponse:
        return await refresh_telemetry_snapshot(
            workspace_root,
            route_quality_limit,
            fallback_limit,
            feedback_limit,
            stale_after_seconds,
            prune,
            max_snapshots,
            retention_days,
        )

    @app.get("/api/telemetry/policy-diff", response_model=RoutePolicyDiffResponse)
    async def get_route_policy_diff(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=500),
        use_snapshot: bool = Query(default=True),
        stale_after_seconds: int = Query(default=900, ge=60, le=86400),
        min_attempts: int = Query(default=3, ge=1, le=50),
    ) -> RoutePolicyDiffResponse:
        return await route_policy_diff(workspace_root, limit, use_snapshot, stale_after_seconds, min_attempts)
