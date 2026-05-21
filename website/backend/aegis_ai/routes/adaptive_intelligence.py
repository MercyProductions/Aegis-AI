from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    AdaptiveBenchmarkReport,
    AdaptiveBenchmarkRunRequest,
    AdaptiveIntelligenceRefreshRequest,
    AdaptiveIntelligenceSnapshot,
    AdaptivePolicyProfileUpdateRequest,
    AdaptivePolicyRollbackRequest,
    AdaptiveReplayRequest,
    EvaluationReplayResult,
    IntelligencePolicyProfile,
    TaskActionRequest,
    TaskOutcomeRecord,
)


def register_adaptive_intelligence_routes(
    app: FastAPI,
    *,
    get_adaptive_intelligence: Callable[[str | None, int, bool], Awaitable[AdaptiveIntelligenceSnapshot]],
    refresh_adaptive_intelligence: Callable[
        [AdaptiveIntelligenceRefreshRequest],
        Awaitable[AdaptiveIntelligenceSnapshot],
    ],
    adaptive_task_outcomes: Callable[[str | None, int, bool], Awaitable[list[TaskOutcomeRecord]]],
    adaptive_policy_profiles: Callable[[], Awaitable[list[IntelligencePolicyProfile]]],
    upsert_adaptive_policy_profile: Callable[
        [AdaptivePolicyProfileUpdateRequest],
        Awaitable[IntelligencePolicyProfile],
    ],
    activate_adaptive_policy_profile: Callable[
        [str, TaskActionRequest | None, str | None],
        Awaitable[AdaptiveIntelligenceSnapshot],
    ],
    rollback_adaptive_policy_profile: Callable[
        [AdaptivePolicyRollbackRequest],
        Awaitable[AdaptiveIntelligenceSnapshot],
    ],
    run_adaptive_benchmarks: Callable[[AdaptiveBenchmarkRunRequest], Awaitable[list[AdaptiveBenchmarkReport]]],
    list_adaptive_benchmarks: Callable[[str | None, int], Awaitable[list[AdaptiveBenchmarkReport]]],
    replay_adaptive_tasks: Callable[[AdaptiveReplayRequest], Awaitable[list[EvaluationReplayResult]]],
    list_adaptive_replay_results: Callable[[str | None, int], Awaitable[list[EvaluationReplayResult]]],
) -> None:
    @app.get("/api/adaptive-intelligence", response_model=AdaptiveIntelligenceSnapshot)
    async def get_adaptive_intelligence_snapshot(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        refresh: bool = Query(default=False),
    ) -> AdaptiveIntelligenceSnapshot:
        return await get_adaptive_intelligence(workspace_root, limit, refresh)

    @app.post("/api/adaptive-intelligence/refresh", response_model=AdaptiveIntelligenceSnapshot)
    async def post_adaptive_intelligence_refresh(
        request: AdaptiveIntelligenceRefreshRequest,
    ) -> AdaptiveIntelligenceSnapshot:
        return await refresh_adaptive_intelligence(request)

    @app.get("/api/adaptive-intelligence/outcomes", response_model=list[TaskOutcomeRecord])
    async def get_adaptive_task_outcomes(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        refresh: bool = Query(default=False),
    ) -> list[TaskOutcomeRecord]:
        return await adaptive_task_outcomes(workspace_root, limit, refresh)

    @app.get("/api/adaptive-intelligence/policies", response_model=list[IntelligencePolicyProfile])
    async def get_adaptive_policy_profiles() -> list[IntelligencePolicyProfile]:
        return await adaptive_policy_profiles()

    @app.post("/api/adaptive-intelligence/policies", response_model=IntelligencePolicyProfile)
    async def post_adaptive_policy_profile(
        request: AdaptivePolicyProfileUpdateRequest,
    ) -> IntelligencePolicyProfile:
        return await upsert_adaptive_policy_profile(request)

    @app.post("/api/adaptive-intelligence/policies/{profile_id}/activate", response_model=AdaptiveIntelligenceSnapshot)
    async def post_adaptive_policy_profile_activation(
        profile_id: str,
        request: TaskActionRequest | None = None,
        workspace_root: str | None = Query(default=None),
    ) -> AdaptiveIntelligenceSnapshot:
        return await activate_adaptive_policy_profile(profile_id, request, workspace_root)

    @app.post("/api/adaptive-intelligence/policies/rollback", response_model=AdaptiveIntelligenceSnapshot)
    async def post_adaptive_policy_profile_rollback(
        request: AdaptivePolicyRollbackRequest,
    ) -> AdaptiveIntelligenceSnapshot:
        return await rollback_adaptive_policy_profile(request)

    @app.post("/api/adaptive-intelligence/benchmarks/run", response_model=list[AdaptiveBenchmarkReport])
    async def post_adaptive_benchmarks_run(
        request: AdaptiveBenchmarkRunRequest,
    ) -> list[AdaptiveBenchmarkReport]:
        return await run_adaptive_benchmarks(request)

    @app.get("/api/adaptive-intelligence/benchmarks", response_model=list[AdaptiveBenchmarkReport])
    async def get_adaptive_benchmarks(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[AdaptiveBenchmarkReport]:
        return await list_adaptive_benchmarks(workspace_root, limit)

    @app.post("/api/adaptive-intelligence/replay", response_model=list[EvaluationReplayResult])
    async def post_adaptive_replay(request: AdaptiveReplayRequest) -> list[EvaluationReplayResult]:
        return await replay_adaptive_tasks(request)

    @app.get("/api/adaptive-intelligence/replay", response_model=list[EvaluationReplayResult])
    async def get_adaptive_replay_results(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[EvaluationReplayResult]:
        return await list_adaptive_replay_results(workspace_root, limit)
