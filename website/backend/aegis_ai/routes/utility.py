from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import FeedbackRecordRequest, FeedbackRecordResponse


def register_utility_routes(
    app: FastAPI,
    *,
    root: Callable[[], Awaitable[dict]],
    get_memory_notes: Callable[[str | None, str | None], Awaitable[dict]],
    get_memory_governance: Callable[[str | None], Awaitable[dict]],
    export_memory_notes: Callable[[dict, str | None], Awaitable[dict]],
    update_memory_governance_controls: Callable[[dict, str | None], Awaitable[dict]],
    create_memory_note: Callable[[dict, str | None], Awaitable[dict]],
    record_feedback: Callable[[FeedbackRecordRequest, str | None], Awaitable[FeedbackRecordResponse]],
    update_memory_note: Callable[[str, dict, str | None], Awaitable[dict]],
    delete_memory_note: Callable[[str, str | None], Awaitable[dict]],
    get_approval_settings: Callable[[str | None], Awaitable[dict]],
    update_approval_settings: Callable[[dict, str | None], Awaitable[dict]],
    rebuild_index: Callable[[str | None], Awaitable[dict]],
    search_index: Callable[[dict, str | None], Awaitable[dict]],
    compare_files: Callable[[dict, str | None], Awaitable[dict]],
    apply_patch: Callable[[dict, str | None], Awaitable[dict]],
    summarize_diff: Callable[[dict], Awaitable[dict]],
) -> None:
    @app.get("/")
    async def get_root() -> dict:
        return await root()

    @app.get("/api/memory")
    async def get_memory(
        workspace_root: str | None = Query(default=None),
        category: str | None = Query(default=None),
    ) -> dict:
        return await get_memory_notes(workspace_root, category)

    @app.post("/api/memory")
    async def post_memory(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await create_memory_note(request, workspace_root)

    @app.get("/api/memory/governance")
    async def get_memory_governance_route(
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await get_memory_governance(workspace_root)

    @app.post("/api/memory/export")
    async def post_memory_export(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await export_memory_notes(request, workspace_root)

    @app.post("/api/memory/controls")
    async def post_memory_controls(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await update_memory_governance_controls(request, workspace_root)

    @app.post("/api/feedback", response_model=FeedbackRecordResponse)
    async def post_feedback(
        request: FeedbackRecordRequest,
        workspace_root: str | None = Query(default=None),
    ) -> FeedbackRecordResponse:
        return await record_feedback(request, workspace_root)

    @app.put("/api/memory/{note_id}")
    async def put_memory(
        note_id: str,
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await update_memory_note(note_id, request, workspace_root)

    @app.delete("/api/memory/{note_id}")
    async def delete_memory(
        note_id: str,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await delete_memory_note(note_id, workspace_root)

    @app.get("/api/approval/settings")
    async def get_approval_settings_route(
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await get_approval_settings(workspace_root)

    @app.put("/api/approval/settings")
    async def put_approval_settings(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await update_approval_settings(request, workspace_root)

    @app.post("/api/index/rebuild")
    async def post_index_rebuild(
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await rebuild_index(workspace_root)

    @app.post("/api/index/search")
    async def post_index_search(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await search_index(request, workspace_root)

    @app.post("/api/diff/compare")
    async def post_diff_compare(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await compare_files(request, workspace_root)

    @app.post("/api/diff/apply")
    async def post_diff_apply(
        request: dict,
        workspace_root: str | None = Query(default=None),
    ) -> dict:
        return await apply_patch(request, workspace_root)

    @app.post("/api/diff/summarize")
    async def post_diff_summarize(request: dict) -> dict:
        return await summarize_diff(request)
