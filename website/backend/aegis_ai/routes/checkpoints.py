from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    CheckpointCreateRequest,
    CheckpointListResponse,
    CheckpointSummary,
    RestoreCheckpointRequest,
    RestoreCheckpointResponse,
)


def register_checkpoint_routes(
    app: FastAPI,
    *,
    list_checkpoints: Callable[[str | None, int], Awaitable[CheckpointListResponse]],
    create_checkpoint: Callable[[CheckpointCreateRequest], Awaitable[CheckpointSummary]],
    restore_checkpoint: Callable[[RestoreCheckpointRequest], Awaitable[RestoreCheckpointResponse]],
) -> None:
    @app.get("/api/checkpoints", response_model=CheckpointListResponse)
    async def get_checkpoints(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> CheckpointListResponse:
        return await list_checkpoints(workspace_root, limit)

    @app.post("/api/checkpoints", response_model=CheckpointSummary)
    async def post_checkpoint(request: CheckpointCreateRequest) -> CheckpointSummary:
        return await create_checkpoint(request)

    @app.post("/api/restore-checkpoint", response_model=RestoreCheckpointResponse)
    async def post_restore_checkpoint(request: RestoreCheckpointRequest) -> RestoreCheckpointResponse:
        return await restore_checkpoint(request)
