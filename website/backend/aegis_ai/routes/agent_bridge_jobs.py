from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    AgentBridgeExecuteRequest,
    AgentBridgeJobInfo,
    AgentBridgeJobResponse,
    AgentBridgeJobsResponse,
)


def register_agent_bridge_job_routes(
    app: FastAPI,
    *,
    start_job: Callable[[AgentBridgeExecuteRequest], Awaitable[AgentBridgeJobResponse]],
    list_jobs: Callable[[int], list[AgentBridgeJobInfo]],
    get_job: Callable[[str], AgentBridgeJobInfo],
    cancel_job: Callable[[str], Awaitable[AgentBridgeJobResponse]],
    retry_job: Callable[[str], Awaitable[AgentBridgeJobResponse]],
) -> None:
    @app.post("/api/agent-bridges/jobs", response_model=AgentBridgeJobResponse)
    async def start_agent_bridge_job(request: AgentBridgeExecuteRequest) -> AgentBridgeJobResponse:
        return await start_job(request)

    @app.get("/api/agent-bridges/jobs", response_model=AgentBridgeJobsResponse)
    async def list_agent_bridge_jobs(limit: int = Query(default=25, ge=1, le=100)) -> AgentBridgeJobsResponse:
        return AgentBridgeJobsResponse(jobs=list_jobs(limit))

    @app.get("/api/agent-bridges/jobs/{job_id}", response_model=AgentBridgeJobResponse)
    async def get_agent_bridge_job(job_id: str) -> AgentBridgeJobResponse:
        return AgentBridgeJobResponse(job=get_job(job_id))

    @app.post("/api/agent-bridges/jobs/{job_id}/cancel", response_model=AgentBridgeJobResponse)
    async def cancel_agent_bridge_job(job_id: str) -> AgentBridgeJobResponse:
        return await cancel_job(job_id)

    @app.post("/api/agent-bridges/jobs/{job_id}/retry", response_model=AgentBridgeJobResponse)
    async def retry_agent_bridge_job(job_id: str) -> AgentBridgeJobResponse:
        return await retry_job(job_id)
