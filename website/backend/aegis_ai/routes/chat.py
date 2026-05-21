from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from ..schemas import AgentRequest, AgentResponse, ChatStreamContractResponse


def register_chat_routes(
    app: FastAPI,
    *,
    chat: Callable[[AgentRequest], Awaitable[AgentResponse]],
    chat_stream_contract: Callable[[], Awaitable[ChatStreamContractResponse]],
    chat_stream: Callable[[AgentRequest], Awaitable[StreamingResponse]],
) -> None:
    @app.post("/api/chat", response_model=AgentResponse)
    async def post_chat(request: AgentRequest) -> AgentResponse:
        return await chat(request)

    @app.get("/api/chat/stream/contract", response_model=ChatStreamContractResponse)
    async def get_chat_stream_contract() -> ChatStreamContractResponse:
        return await chat_stream_contract()

    @app.post("/api/chat/stream")
    async def post_chat_stream(request: AgentRequest) -> StreamingResponse:
        return await chat_stream(request)
