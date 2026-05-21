from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    AutonomousApprovalActionRequest,
    AutonomousApprovalGate,
    AutonomousEngineeringSnapshot,
    AutonomousObjective,
    AutonomousObjectiveActionRequest,
    AutonomousObjectiveCreateRequest,
    AutonomousObjectiveDetail,
    AutonomousObjectiveIterationRequest,
    AutonomousSimulationEstimate,
)


def register_autonomous_engineering_routes(
    app: FastAPI,
    *,
    autonomous_engineering_snapshot: Callable[[str | None], Awaitable[AutonomousEngineeringSnapshot]],
    list_autonomous_objectives: Callable[[str | None, bool, int], Awaitable[list[AutonomousObjective]]],
    create_autonomous_objective: Callable[[AutonomousObjectiveCreateRequest], Awaitable[AutonomousObjectiveDetail]],
    get_autonomous_objective: Callable[[str], Awaitable[AutonomousObjectiveDetail]],
    simulate_autonomous_objective: Callable[[str], Awaitable[AutonomousSimulationEstimate]],
    start_autonomous_objective: Callable[[str, AutonomousObjectiveActionRequest | None], Awaitable[AutonomousObjectiveDetail]],
    pause_autonomous_objective: Callable[[str, AutonomousObjectiveActionRequest | None], Awaitable[AutonomousObjectiveDetail]],
    cancel_autonomous_objective: Callable[[str, AutonomousObjectiveActionRequest | None], Awaitable[AutonomousObjectiveDetail]],
    iterate_autonomous_objective: Callable[
        [str, AutonomousObjectiveIterationRequest | None],
        Awaitable[AutonomousObjectiveDetail],
    ],
    list_autonomous_approval_gates: Callable[[str | None, int], Awaitable[list[AutonomousApprovalGate]]],
    approve_autonomous_gate: Callable[[str, AutonomousApprovalActionRequest | None], Awaitable[AutonomousObjectiveDetail]],
    reject_autonomous_gate: Callable[[str, AutonomousApprovalActionRequest | None], Awaitable[AutonomousObjectiveDetail]],
) -> None:
    @app.get("/api/autonomous-engineering", response_model=AutonomousEngineeringSnapshot)
    async def get_autonomous_engineering_snapshot(
        workspace_root: str | None = Query(default=None),
    ) -> AutonomousEngineeringSnapshot:
        return await autonomous_engineering_snapshot(workspace_root)

    @app.get("/api/autonomous-engineering/objectives", response_model=list[AutonomousObjective])
    async def get_autonomous_objectives(
        workspace_root: str | None = Query(default=None),
        include_completed: bool = Query(default=True),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[AutonomousObjective]:
        return await list_autonomous_objectives(workspace_root, include_completed, limit)

    @app.post("/api/autonomous-engineering/objectives", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_objective(
        request: AutonomousObjectiveCreateRequest,
    ) -> AutonomousObjectiveDetail:
        return await create_autonomous_objective(request)

    @app.get("/api/autonomous-engineering/objectives/{objective_id}", response_model=AutonomousObjectiveDetail)
    async def get_autonomous_objective_detail(objective_id: str) -> AutonomousObjectiveDetail:
        return await get_autonomous_objective(objective_id)

    @app.post("/api/autonomous-engineering/objectives/{objective_id}/simulate", response_model=AutonomousSimulationEstimate)
    async def post_autonomous_objective_simulation(objective_id: str) -> AutonomousSimulationEstimate:
        return await simulate_autonomous_objective(objective_id)

    @app.post("/api/autonomous-engineering/objectives/{objective_id}/start", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_objective_start(
        objective_id: str,
        request: AutonomousObjectiveActionRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await start_autonomous_objective(objective_id, request)

    @app.post("/api/autonomous-engineering/objectives/{objective_id}/pause", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_objective_pause(
        objective_id: str,
        request: AutonomousObjectiveActionRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await pause_autonomous_objective(objective_id, request)

    @app.post("/api/autonomous-engineering/objectives/{objective_id}/cancel", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_objective_cancel(
        objective_id: str,
        request: AutonomousObjectiveActionRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await cancel_autonomous_objective(objective_id, request)

    @app.post("/api/autonomous-engineering/objectives/{objective_id}/iterate", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_objective_iteration(
        objective_id: str,
        request: AutonomousObjectiveIterationRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await iterate_autonomous_objective(objective_id, request)

    @app.get("/api/autonomous-engineering/approval-gates", response_model=list[AutonomousApprovalGate])
    async def get_autonomous_approval_gates(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=300),
    ) -> list[AutonomousApprovalGate]:
        return await list_autonomous_approval_gates(workspace_root, limit)

    @app.post("/api/autonomous-engineering/approval-gates/{gate_id}/approve", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_gate_approval(
        gate_id: str,
        request: AutonomousApprovalActionRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await approve_autonomous_gate(gate_id, request)

    @app.post("/api/autonomous-engineering/approval-gates/{gate_id}/reject", response_model=AutonomousObjectiveDetail)
    async def post_autonomous_gate_rejection(
        gate_id: str,
        request: AutonomousApprovalActionRequest | None = None,
    ) -> AutonomousObjectiveDetail:
        return await reject_autonomous_gate(gate_id, request)
