from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from ..schemas import AgentBridgeExecuteRequest


def register_agent_bridge_streaming_routes(
    app: FastAPI,
    *,
    stream_bridge: Callable[[AgentBridgeExecuteRequest], Awaitable[StreamingResponse]],
) -> None:
    @app.post("/api/agent-bridges/stream")
    async def stream_agent_bridge(request: AgentBridgeExecuteRequest) -> StreamingResponse:
        return await stream_bridge(request)
