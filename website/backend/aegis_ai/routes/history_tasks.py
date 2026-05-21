from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    HistoryResponse,
    TaskActionRequest,
    TaskActionResponse,
    TaskArtifactsResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskListResponse,
    TaskTimelineResponse,
)


def register_history_task_routes(
    app: FastAPI,
    *,
    history: Callable[[str | None, int], Awaitable[HistoryResponse]],
    list_tasks: Callable[[str | None, str | None, bool, int], Awaitable[TaskListResponse]],
    create_task: Callable[[TaskCreateRequest], Awaitable[TaskDetailResponse]],
    read_task: Callable[[str], Awaitable[TaskDetailResponse]],
    cancel_task: Callable[[str, TaskActionRequest | None], Awaitable[TaskActionResponse]],
    approve_task_action: Callable[[str, TaskActionRequest], Awaitable[TaskActionResponse]],
    retry_task: Callable[[str, TaskActionRequest | None], Awaitable[TaskActionResponse]],
    task_timeline: Callable[[str], Awaitable[TaskTimelineResponse]],
    task_artifacts: Callable[[str], Awaitable[TaskArtifactsResponse]],
) -> None:
    @app.get("/api/history", response_model=HistoryResponse)
    async def get_history(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=8, ge=1, le=25),
    ) -> HistoryResponse:
        return await history(workspace_root, limit)

    @app.get("/api/tasks", response_model=TaskListResponse)
    async def get_tasks(
        workspace_root: str | None = Query(default=None),
        status: str | None = Query(default=None),
        include_subtasks: bool = Query(default=False),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> TaskListResponse:
        return await list_tasks(workspace_root, status, include_subtasks, limit)

    @app.post("/api/tasks", response_model=TaskDetailResponse)
    async def post_task(request: TaskCreateRequest) -> TaskDetailResponse:
        return await create_task(request)

    @app.get("/api/tasks/{task_id}", response_model=TaskDetailResponse)
    async def get_task(task_id: str) -> TaskDetailResponse:
        return await read_task(task_id)

    @app.post("/api/tasks/{task_id}/cancel", response_model=TaskActionResponse)
    async def post_task_cancel(
        task_id: str,
        request: TaskActionRequest | None = None,
    ) -> TaskActionResponse:
        return await cancel_task(task_id, request)

    @app.post("/api/tasks/{task_id}/approve", response_model=TaskActionResponse)
    async def post_task_approve(task_id: str, request: TaskActionRequest) -> TaskActionResponse:
        return await approve_task_action(task_id, request)

    @app.post("/api/tasks/{task_id}/retry", response_model=TaskActionResponse)
    async def post_task_retry(
        task_id: str,
        request: TaskActionRequest | None = None,
    ) -> TaskActionResponse:
        return await retry_task(task_id, request)

    @app.get("/api/tasks/{task_id}/timeline", response_model=TaskTimelineResponse)
    async def get_task_timeline(task_id: str) -> TaskTimelineResponse:
        return await task_timeline(task_id)

    @app.get("/api/tasks/{task_id}/artifacts", response_model=TaskArtifactsResponse)
    async def get_task_artifacts(task_id: str) -> TaskArtifactsResponse:
        return await task_artifacts(task_id)
