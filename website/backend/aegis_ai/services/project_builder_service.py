from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from ..project_scaffolder import ProjectScaffolder
from ..schemas import (
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
)


class ProjectPlanCacheProtocol(Protocol):
    def get(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse | None:
        ...

    def set(self, request: ProjectScaffoldPlanRequest, response: ProjectScaffoldPlanResponse) -> None:
        ...


class ProjectBuilderService:
    """Website API adapter for project builder routes."""

    def __init__(
        self,
        *,
        scaffolder_factory: Callable[[], ProjectScaffolder],
        plan_cache: ProjectPlanCacheProtocol,
        invalidate_workspace_caches: Callable[[Path], None],
    ) -> None:
        self._scaffolder_factory = scaffolder_factory
        self._plan_cache = plan_cache
        self._invalidate_workspace_caches = invalidate_workspace_caches

    async def presets(self) -> list[ProjectScaffoldPreset]:
        return ProjectScaffolder.presets()

    async def plan(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
        try:
            cached = self._plan_cache.get(request)
            if cached is not None:
                return cached
            response = self._scaffolder_factory().plan_from_prompt(request)
            self._plan_cache.set(request, response)
            return response
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def preview(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        try:
            return self._scaffolder_factory().preview(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def scaffold(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        try:
            result = self._scaffolder_factory().scaffold(request)
            self._invalidate_workspace_caches(Path(result.target_path))
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
