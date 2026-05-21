from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from ..schemas import (
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
)


def register_project_builder_routes(
    app: FastAPI,
    *,
    project_builder_presets: Callable[[], Awaitable[list[ProjectScaffoldPreset]]],
    plan_project_scaffold: Callable[[ProjectScaffoldPlanRequest], Awaitable[ProjectScaffoldPlanResponse]],
    preview_project_scaffold: Callable[[ProjectScaffoldRequest], Awaitable[ProjectScaffoldResponse]],
    scaffold_project: Callable[[ProjectScaffoldRequest], Awaitable[ProjectScaffoldResponse]],
) -> None:
    @app.get("/api/project-builder/presets", response_model=list[ProjectScaffoldPreset])
    async def get_project_builder_presets() -> list[ProjectScaffoldPreset]:
        return await project_builder_presets()

    @app.post("/api/project-builder/plan", response_model=ProjectScaffoldPlanResponse)
    async def plan_project_builder_scaffold(
        request: ProjectScaffoldPlanRequest,
    ) -> ProjectScaffoldPlanResponse:
        return await plan_project_scaffold(request)

    @app.post("/api/project-builder/preview", response_model=ProjectScaffoldResponse)
    async def preview_project_builder_scaffold(
        request: ProjectScaffoldRequest,
    ) -> ProjectScaffoldResponse:
        return await preview_project_scaffold(request)

    @app.post("/api/project-builder/scaffold", response_model=ProjectScaffoldResponse)
    async def scaffold_project_builder(request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        return await scaffold_project(request)
