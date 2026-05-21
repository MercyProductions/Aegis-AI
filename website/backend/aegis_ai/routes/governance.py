from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query


def register_governance_routes(
    app: FastAPI,
    *,
    api_governance_dashboard: Callable[[str | None, bool, int], Awaitable[dict[str, Any]]],
    api_governance_evaluate: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    api_governance_compliance_export: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/governance")
    async def get_governance_dashboard(
        workspace_root: str | None = Query(default=None),
        include_audit: bool = Query(default=True),
        limit: int = Query(default=100),
    ) -> dict[str, Any]:
        return await api_governance_dashboard(workspace_root, include_audit, limit)

    @app.post("/api/governance/evaluate")
    async def evaluate_governance(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_governance_evaluate(payload)

    @app.post("/api/governance/compliance/export")
    async def export_governance_compliance(payload: dict[str, Any]) -> dict[str, Any]:
        return await api_governance_compliance_export(payload)
