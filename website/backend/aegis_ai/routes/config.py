from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from ..schemas import AppConfig, ConfigUpdateRequest


def register_config_routes(
    app: FastAPI,
    *,
    config_snapshot: Callable[[], Awaitable[AppConfig]],
    save_config: Callable[[ConfigUpdateRequest], Awaitable[AppConfig]],
) -> None:
    @app.get("/api/config", response_model=AppConfig)
    async def config() -> AppConfig:
        return await config_snapshot()

    @app.post("/api/config", response_model=AppConfig)
    async def update_config(request: ConfigUpdateRequest) -> AppConfig:
        return await save_config(request)
