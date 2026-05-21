from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from ..schemas import (
    AgentBridgeExecuteRequest,
    AgentBridgeExecuteResponse,
    AgentBridgePreflightResponse,
)


def register_agent_bridge_execution_routes(
    app: FastAPI,
    *,
    preflight_bridge: Callable[[AgentBridgeExecuteRequest], Awaitable[AgentBridgePreflightResponse]],
    execute_bridge: Callable[[AgentBridgeExecuteRequest], Awaitable[AgentBridgeExecuteResponse]],
) -> None:
    @app.post("/api/agent-bridges/preflight", response_model=AgentBridgePreflightResponse)
    async def preflight_agent_bridge(request: AgentBridgeExecuteRequest) -> AgentBridgePreflightResponse:
        return await preflight_bridge(request)

    @app.post("/api/agent-bridges/execute", response_model=AgentBridgeExecuteResponse)
    async def execute_agent_bridge(request: AgentBridgeExecuteRequest) -> AgentBridgeExecuteResponse:
        return await execute_bridge(request)
