from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from ..schemas import ApplyRequest, ApplyResponse, RoutePreviewRequest, RoutePreviewResponse


def register_routing_apply_routes(
    app: FastAPI,
    *,
    preview_route: Callable[[RoutePreviewRequest], Awaitable[RoutePreviewResponse]],
    apply_changes: Callable[[ApplyRequest], Awaitable[ApplyResponse]],
) -> None:
    @app.post("/api/routing/preview", response_model=RoutePreviewResponse)
    async def preview_routing(request: RoutePreviewRequest) -> RoutePreviewResponse:
        return await preview_route(request)

    @app.post("/api/apply", response_model=ApplyResponse)
    async def apply_file_changes(request: ApplyRequest) -> ApplyResponse:
        return await apply_changes(request)
