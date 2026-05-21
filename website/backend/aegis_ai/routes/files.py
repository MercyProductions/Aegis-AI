from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from ..workspace import WorkspaceManager


WorkspaceResolver = Callable[[str | None], Path]


def register_file_routes(
    app: FastAPI,
    *,
    workspace_resolver: WorkspaceResolver,
    workspace_manager_factory: Callable[[], WorkspaceManager],
) -> None:
    def manager() -> WorkspaceManager:
        return workspace_manager_factory()

    @app.get("/api/files")
    async def files(
        workspace_root: str | None = Query(default=None),
        max_files: int = Query(default=120, ge=1, le=5000),
    ) -> dict[str, Any]:
        root = workspace_resolver(workspace_root)
        return {"workspace_root": str(root), "files": manager().scan(root, max_files=max_files)}

    @app.get("/api/file")
    async def file_content(
        path: str = Query(min_length=1),
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, str]:
        root = workspace_resolver(workspace_root)
        try:
            content = manager().read_file(root, path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"workspace_root": str(root), "path": path, "content": content}

    @app.get("/api/file/slice")
    async def file_slice(
        path: str = Query(min_length=1),
        workspace_root: str | None = Query(default=None),
        start_line: int = Query(default=1, ge=1),
        max_lines: int = Query(default=400, ge=1, le=2000),
    ) -> dict[str, Any]:
        root = workspace_resolver(workspace_root)
        try:
            payload = manager().read_file_slice(root, path, start_line=start_line, max_lines=max_lines)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"workspace_root": str(root), **payload}
