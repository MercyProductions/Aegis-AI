from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from ..schemas import (
    DistributedRuntimeSnapshot,
    ExecutionDispatchRequest,
    ExecutionDispatchResponse,
    ExecutionQueueActionRequest,
    ExecutionQueueCreateRequest,
    ExecutionQueueItem,
    HybridRouteDecision,
    HybridRouteRequest,
    RemoteWorkspaceSyncManifest,
    RemoteWorkspaceSyncRequest,
    RuntimeObservabilitySnapshot,
    WorkerActionRequest,
    WorkerAuditEvent,
    WorkerHeartbeatRequest,
    WorkerRegistrationRequest,
    WorkerRuntimeInfo,
)


def register_distributed_runtime_routes(
    app: FastAPI,
    *,
    distributed_runtime_snapshot: Callable[[str | None], Awaitable[DistributedRuntimeSnapshot]],
    distributed_runtime_observability: Callable[[str | None], Awaitable[RuntimeObservabilitySnapshot]],
    runtime_interaction_status: Callable[[str | None, int], Awaitable[dict[str, Any]]],
    runtime_interaction_jobs: Callable[[str | None, str | None, int], Awaitable[dict[str, Any]]],
    launch_runtime_interaction_job: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    runtime_interaction_job: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    cancel_runtime_interaction_job: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    retry_runtime_interaction_job: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    runtime_interaction_streams: Callable[
        [str | None, str | None, str | None, int, int],
        Awaitable[dict[str, Any]],
    ],
    runtime_interaction_events: Callable[
        [str | None, str | None, str | None, int, int, bool, int],
        Awaitable[StreamingResponse],
    ],
    runtime_interaction_sessions: Callable[[str | None], Awaitable[dict[str, Any]]],
    create_runtime_interaction_session: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    sync_runtime_interaction_session: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    runtime_interaction_voice: Callable[[str | None], Awaitable[dict[str, Any]]],
    runtime_interaction_voice_command: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    runtime_interaction_replay: Callable[[str | None, str | None, str | None, int], Awaitable[dict[str, Any]]],
    list_runtime_workers: Callable[[str | None], Awaitable[list[WorkerRuntimeInfo]]],
    register_runtime_worker: Callable[[WorkerRegistrationRequest], Awaitable[WorkerRuntimeInfo]],
    heartbeat_runtime_worker: Callable[[str, WorkerHeartbeatRequest], Awaitable[WorkerRuntimeInfo]],
    revoke_runtime_worker: Callable[[str, WorkerActionRequest | None], Awaitable[WorkerRuntimeInfo]],
    list_execution_queue: Callable[[str | None, str | None, int], Awaitable[list[ExecutionQueueItem]]],
    create_execution_queue_item: Callable[[ExecutionQueueCreateRequest], Awaitable[ExecutionQueueItem]],
    read_execution_queue_item: Callable[[str], Awaitable[ExecutionQueueItem]],
    cancel_execution_queue_item: Callable[[str, ExecutionQueueActionRequest | None], Awaitable[ExecutionQueueItem]],
    retry_execution_queue_item: Callable[[str, ExecutionQueueActionRequest | None], Awaitable[ExecutionQueueItem]],
    dispatch_execution_queue: Callable[[ExecutionDispatchRequest], Awaitable[ExecutionDispatchResponse]],
    route_distributed_model: Callable[[HybridRouteRequest], Awaitable[HybridRouteDecision]],
    distributed_runtime_audit: Callable[[str, str, int], Awaitable[list[WorkerAuditEvent]]],
    list_remote_sync_manifests: Callable[[str | None, int], Awaitable[list[RemoteWorkspaceSyncManifest]]],
    create_remote_sync_manifest: Callable[[RemoteWorkspaceSyncRequest], Awaitable[RemoteWorkspaceSyncManifest]],
) -> None:
    @app.get("/api/distributed-runtime", response_model=DistributedRuntimeSnapshot)
    async def get_distributed_runtime_snapshot(
        workspace_root: str | None = Query(default=None),
    ) -> DistributedRuntimeSnapshot:
        return await distributed_runtime_snapshot(workspace_root)

    @app.get("/api/distributed-runtime/observability", response_model=RuntimeObservabilitySnapshot)
    async def get_distributed_runtime_observability(
        workspace_root: str | None = Query(default=None),
    ) -> RuntimeObservabilitySnapshot:
        return await distributed_runtime_observability(workspace_root)

    @app.get("/api/runtime-interaction")
    async def get_runtime_interaction_status(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=300),
    ) -> dict[str, Any]:
        return await runtime_interaction_status(workspace_root, limit)

    @app.get("/api/runtime-interaction/jobs")
    async def get_runtime_interaction_jobs(
        workspace_root: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=300),
    ) -> dict[str, Any]:
        return await runtime_interaction_jobs(workspace_root, status, limit)

    @app.post("/api/runtime-interaction/jobs")
    async def post_runtime_interaction_job(request: dict[str, Any]) -> dict[str, Any]:
        return await launch_runtime_interaction_job(request)

    @app.get("/api/runtime-interaction/jobs/{job_id}")
    async def get_runtime_interaction_job(
        job_id: str,
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await runtime_interaction_job(job_id, workspace_root)

    @app.post("/api/runtime-interaction/jobs/{job_id}/cancel")
    async def post_runtime_interaction_job_cancel(job_id: str, request: dict[str, Any]) -> dict[str, Any]:
        return await cancel_runtime_interaction_job(job_id, request)

    @app.post("/api/runtime-interaction/jobs/{job_id}/retry")
    async def post_runtime_interaction_job_retry(job_id: str, request: dict[str, Any]) -> dict[str, Any]:
        return await retry_runtime_interaction_job(job_id, request)

    @app.get("/api/runtime-interaction/streams")
    async def get_runtime_interaction_streams(
        workspace_root: str | None = Query(default=None),
        job_id: str | None = Query(default=None),
        workflow_id: str | None = Query(default=None),
        since: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        return await runtime_interaction_streams(workspace_root, job_id, workflow_id, since, limit)

    @app.get("/api/runtime-interaction/events")
    async def get_runtime_interaction_events(
        workspace_root: str | None = Query(default=None),
        job_id: str | None = Query(default=None),
        workflow_id: str | None = Query(default=None),
        since: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        follow: bool = Query(default=True),
        max_seconds: int = Query(default=30, ge=1, le=120),
    ) -> StreamingResponse:
        return await runtime_interaction_events(workspace_root, job_id, workflow_id, since, limit, follow, max_seconds)

    @app.get("/api/runtime-interaction/sessions")
    async def get_runtime_interaction_sessions(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await runtime_interaction_sessions(workspace_root)

    @app.post("/api/runtime-interaction/sessions")
    async def post_runtime_interaction_session(request: dict[str, Any]) -> dict[str, Any]:
        return await create_runtime_interaction_session(request)

    @app.post("/api/runtime-interaction/sessions/{session_id}/sync")
    async def post_runtime_interaction_session_sync(
        session_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        return await sync_runtime_interaction_session(session_id, request)

    @app.get("/api/runtime-interaction/voice")
    async def get_runtime_interaction_voice(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return await runtime_interaction_voice(workspace_root)

    @app.post("/api/runtime-interaction/voice/command")
    async def post_runtime_interaction_voice_command(request: dict[str, Any]) -> dict[str, Any]:
        return await runtime_interaction_voice_command(request)

    @app.get("/api/runtime-interaction/replay")
    async def get_runtime_interaction_replay(
        workspace_root: str | None = Query(default=None),
        workflow_id: str | None = Query(default=None),
        job_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        return await runtime_interaction_replay(workspace_root, workflow_id, job_id, limit)

    @app.get("/api/distributed-runtime/workers", response_model=list[WorkerRuntimeInfo])
    async def get_runtime_workers(
        workspace_root: str | None = Query(default=None),
    ) -> list[WorkerRuntimeInfo]:
        return await list_runtime_workers(workspace_root)

    @app.post("/api/distributed-runtime/workers/register", response_model=WorkerRuntimeInfo)
    async def post_runtime_worker(request: WorkerRegistrationRequest) -> WorkerRuntimeInfo:
        return await register_runtime_worker(request)

    @app.post("/api/distributed-runtime/workers/{worker_id}/heartbeat", response_model=WorkerRuntimeInfo)
    async def post_runtime_worker_heartbeat(
        worker_id: str,
        request: WorkerHeartbeatRequest,
    ) -> WorkerRuntimeInfo:
        return await heartbeat_runtime_worker(worker_id, request)

    @app.post("/api/distributed-runtime/workers/{worker_id}/revoke", response_model=WorkerRuntimeInfo)
    async def post_runtime_worker_revoke(
        worker_id: str,
        request: WorkerActionRequest | None = None,
    ) -> WorkerRuntimeInfo:
        return await revoke_runtime_worker(worker_id, request)

    @app.get("/api/distributed-runtime/queue", response_model=list[ExecutionQueueItem])
    async def get_execution_queue(
        workspace_root: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[ExecutionQueueItem]:
        return await list_execution_queue(workspace_root, status, limit)

    @app.post("/api/distributed-runtime/queue", response_model=ExecutionQueueItem)
    async def post_execution_queue_item(request: ExecutionQueueCreateRequest) -> ExecutionQueueItem:
        return await create_execution_queue_item(request)

    @app.get("/api/distributed-runtime/queue/{job_id}", response_model=ExecutionQueueItem)
    async def get_execution_queue_item(job_id: str) -> ExecutionQueueItem:
        return await read_execution_queue_item(job_id)

    @app.post("/api/distributed-runtime/queue/{job_id}/cancel", response_model=ExecutionQueueItem)
    async def post_execution_queue_item_cancel(
        job_id: str,
        request: ExecutionQueueActionRequest | None = None,
    ) -> ExecutionQueueItem:
        return await cancel_execution_queue_item(job_id, request)

    @app.post("/api/distributed-runtime/queue/{job_id}/retry", response_model=ExecutionQueueItem)
    async def post_execution_queue_item_retry(
        job_id: str,
        request: ExecutionQueueActionRequest | None = None,
    ) -> ExecutionQueueItem:
        return await retry_execution_queue_item(job_id, request)

    @app.post("/api/distributed-runtime/dispatch", response_model=ExecutionDispatchResponse)
    async def post_execution_queue_dispatch(request: ExecutionDispatchRequest) -> ExecutionDispatchResponse:
        return await dispatch_execution_queue(request)

    @app.post("/api/distributed-runtime/route", response_model=HybridRouteDecision)
    async def post_distributed_model_route(request: HybridRouteRequest) -> HybridRouteDecision:
        return await route_distributed_model(request)

    @app.get("/api/distributed-runtime/audit", response_model=list[WorkerAuditEvent])
    async def get_distributed_runtime_audit(
        worker_id: str = Query(default=""),
        job_id: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[WorkerAuditEvent]:
        return await distributed_runtime_audit(worker_id, job_id, limit)

    @app.get("/api/distributed-runtime/sync/manifests", response_model=list[RemoteWorkspaceSyncManifest])
    async def get_remote_sync_manifests(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[RemoteWorkspaceSyncManifest]:
        return await list_remote_sync_manifests(workspace_root, limit)

    @app.post("/api/distributed-runtime/sync/export", response_model=RemoteWorkspaceSyncManifest)
    async def post_remote_sync_manifest(request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
        return await create_remote_sync_manifest(request)
