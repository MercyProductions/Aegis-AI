from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query


def register_quality_evaluation_routes(
    app: FastAPI,
    *,
    quality_gates_status: Callable[[str | None, int], Awaitable[dict[str, Any]]],
    evaluate_quality_gates: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    workflow_quality_gates: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    quality_benchmarks: Callable[[str | None, int], Awaitable[dict[str, Any]]],
    run_quality_benchmark: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    evaluation_reports: Callable[[str | None, str | None, int], Awaitable[dict[str, Any]]],
    create_evaluation_report: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/quality-gates")
    async def get_quality_gates_status(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return await quality_gates_status(workspace_root, limit)

    @app.post("/api/quality-gates/evaluate")
    async def post_quality_gates_evaluate(request: dict[str, Any]) -> dict[str, Any]:
        return await evaluate_quality_gates(request)

    @app.get("/api/quality-gates/workflows/{workflow_id}")
    async def get_workflow_quality_gates(
        workflow_id: str,
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await workflow_quality_gates(workflow_id, workspace_root)

    @app.get("/api/benchmarks")
    async def get_quality_benchmarks(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return await quality_benchmarks(workspace_root, limit)

    @app.post("/api/benchmarks/run")
    async def post_quality_benchmark_run(request: dict[str, Any]) -> dict[str, Any]:
        return await run_quality_benchmark(request)

    @app.get("/api/evaluation-reports")
    async def get_evaluation_reports(
        workspace_root: str | None = Query(default=None),
        workflow_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return await evaluation_reports(workspace_root, workflow_id, limit)

    @app.post("/api/evaluation-reports")
    async def post_evaluation_report(request: dict[str, Any]) -> dict[str, Any]:
        return await create_evaluation_report(request)
