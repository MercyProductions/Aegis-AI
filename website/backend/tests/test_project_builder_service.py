from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import (
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
)
from aegis_ai.services.project_builder_service import ProjectBuilderService
from aegis_ai.workspace_cache import ProjectPlanCache


def _preset() -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id="python-cli",
        label="Python CLI",
        framework="Python",
        language="Python",
    )


def _scaffold_request(tmp_path: Path) -> ProjectScaffoldRequest:
    return ProjectScaffoldRequest(
        target_path=str(tmp_path / "sample-tool"),
        preset_id="python-cli",
        project_name="sample-tool",
    )


class FakeScaffolder:
    def __init__(self, tmp_path: Path, *, fail: bool = False) -> None:
        self.tmp_path = tmp_path
        self.fail = fail
        self.plan_calls = 0
        self.preview_calls = 0
        self.scaffold_calls = 0

    def plan_from_prompt(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
        self.plan_calls += 1
        if self.fail:
            raise ValueError("bad plan")
        scaffold_request = _scaffold_request(self.tmp_path)
        return ProjectScaffoldPlanResponse(
            prompt=request.prompt,
            preset=_preset(),
            target_path=scaffold_request.target_path,
            scaffold_request=scaffold_request,
        )

    def preview(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        self.preview_calls += 1
        if self.fail:
            raise ValueError("bad preview")
        return ProjectScaffoldResponse(
            message="preview",
            target_path=request.target_path,
            preset=_preset(),
        )

    def scaffold(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        self.scaffold_calls += 1
        if self.fail:
            raise ValueError("bad scaffold")
        return ProjectScaffoldResponse(
            message="scaffolded",
            target_path=request.target_path,
            preset=_preset(),
        )


def test_project_builder_service_uses_plan_cache(tmp_path: Path) -> None:
    fake = FakeScaffolder(tmp_path)
    service = ProjectBuilderService(
        scaffolder_factory=lambda: fake,  # type: ignore[arg-type]
        plan_cache=ProjectPlanCache(ttl_seconds=60, max_size=10),
        invalidate_workspace_caches=lambda root: None,
    )
    request = ProjectScaffoldPlanRequest(prompt="build a python cli")

    first = asyncio.run(service.plan(request))
    second = asyncio.run(service.plan(request))

    assert first == second
    assert fake.plan_calls == 1


def test_project_builder_service_invalidates_after_scaffold(tmp_path: Path) -> None:
    fake = FakeScaffolder(tmp_path)
    invalidated: list[Path] = []
    service = ProjectBuilderService(
        scaffolder_factory=lambda: fake,  # type: ignore[arg-type]
        plan_cache=ProjectPlanCache(ttl_seconds=60, max_size=10),
        invalidate_workspace_caches=lambda root: invalidated.append(root),
    )
    request = _scaffold_request(tmp_path)

    response = asyncio.run(service.scaffold(request))

    assert response.message == "scaffolded"
    assert fake.scaffold_calls == 1
    assert invalidated == [Path(request.target_path)]


def test_project_builder_service_converts_value_errors_to_http_400(tmp_path: Path) -> None:
    fake = FakeScaffolder(tmp_path, fail=True)
    service = ProjectBuilderService(
        scaffolder_factory=lambda: fake,  # type: ignore[arg-type]
        plan_cache=ProjectPlanCache(ttl_seconds=60, max_size=10),
        invalidate_workspace_caches=lambda root: None,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.preview(_scaffold_request(tmp_path)))

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad preview"
