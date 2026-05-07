from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from .schemas import ProjectScaffoldPlanRequest, ProjectScaffoldPlanResponse


@dataclass(frozen=True)
class WorkspaceStatusSnapshot:
    created_at: float
    manifest: Any
    dependency_profile: Any
    instruction_status: Any
    validation_plan: Any
    command_history: dict[str, Any]
    readiness: Any


@dataclass(frozen=True)
class ProjectPlanCacheEntry:
    created_at: float
    response: ProjectScaffoldPlanResponse


def normalized_cache_path(path: Path) -> str:
    return str(path.resolve()).rstrip("\\/").casefold()


def cache_paths_are_related(left: str, right: str) -> bool:
    if left == right:
        return True
    return left.startswith(right + "\\") or right.startswith(left + "\\")


def project_plan_cache_key(request: ProjectScaffoldPlanRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)


class WorkspaceStatusSnapshotCache:
    def __init__(self, *, ttl_seconds: float, max_size: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.entries: dict[str, WorkspaceStatusSnapshot] = {}

    def clear(self, root: Path | None = None) -> None:
        if root is None:
            self.entries.clear()
            return
        target = normalized_cache_path(root)
        for key in list(self.entries):
            if cache_paths_are_related(key, target):
                self.entries.pop(key, None)

    def get(self, root: Path, *, now: float | None = None) -> WorkspaceStatusSnapshot | None:
        key = normalized_cache_path(root)
        current_time = time.monotonic() if now is None else now
        cached = self.entries.get(key)
        if cached is not None and current_time - cached.created_at <= self.ttl_seconds:
            return cached
        return None

    def set(self, root: Path, snapshot: WorkspaceStatusSnapshot) -> None:
        self.entries[normalized_cache_path(root)] = snapshot
        self.prune()

    def prune(self) -> None:
        while len(self.entries) > self.max_size:
            oldest_key = min(self.entries, key=lambda key: self.entries[key].created_at)
            self.entries.pop(oldest_key, None)


class ProjectPlanCache:
    def __init__(self, *, ttl_seconds: float, max_size: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.entries: dict[str, ProjectPlanCacheEntry] = {}

    def clear(self) -> None:
        self.entries.clear()

    def get(
        self,
        request: ProjectScaffoldPlanRequest,
        *,
        now: float | None = None,
    ) -> ProjectScaffoldPlanResponse | None:
        current_time = time.monotonic() if now is None else now
        cached = self.entries.get(project_plan_cache_key(request))
        if cached is not None and current_time - cached.created_at <= self.ttl_seconds:
            return cached.response.model_copy(deep=True)
        return None

    def set(
        self,
        request: ProjectScaffoldPlanRequest,
        response: ProjectScaffoldPlanResponse,
        *,
        now: float | None = None,
    ) -> None:
        current_time = time.monotonic() if now is None else now
        self.entries[project_plan_cache_key(request)] = ProjectPlanCacheEntry(
            created_at=current_time,
            response=response.model_copy(deep=True),
        )
        self.prune()

    def prune(self) -> None:
        while len(self.entries) > self.max_size:
            oldest_key = min(self.entries, key=lambda key: self.entries[key].created_at)
            self.entries.pop(oldest_key, None)
