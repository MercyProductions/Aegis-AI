from __future__ import annotations

from .project_status import status_text
from .schemas import WorkspaceInstructionFile, WorkspaceInstructionStatusInfo


def instruction_status_from_discovered_files(
    instruction_files: list[WorkspaceInstructionFile],
    *,
    updated_at: str,
) -> WorkspaceInstructionStatusInfo:
    files: list[dict[str, object]] = []
    for item in instruction_files[:12]:
        files.append(
            {
                "path": item.path,
                "title": item.title,
                "kind": item.kind,
                "score": item.score,
                "open_items": item.pending_count,
                "completed_items": item.completed_count,
                "total_items": item.total_items,
                "pending_items": [
                    status_text(pending, limit=220)
                    for pending in item.pending_items[:10]
                    if status_text(pending, limit=220)
                ],
                "summary": item.summary,
            }
        )

    open_items = sum(item.pending_count for item in instruction_files)
    completed_items = sum(item.completed_count for item in instruction_files)
    total_items = sum(item.total_items for item in instruction_files)
    first_pending = next(
        (
            pending
            for item in instruction_files
            for pending in item.pending_items
            if pending.strip()
        ),
        "",
    )
    recommendation = (
        f"Continue the next open instruction item: {status_text(first_pending, limit=220)}"
        if open_items and first_pending
        else "Continue the next open instruction item."
        if open_items
        else "All discovered instruction items are currently complete; summarize the finished state and propose the next milestone."
    )
    payload = {
        "schema": "aegis.instruction_status.discovered.v1",
        "updated_at": updated_at,
        "source_message": "Discovered workspace instruction files.",
        "instruction_file_count": len(files),
        "open_items": open_items,
        "completed_items": completed_items,
        "total_items": total_items,
        "files": files,
        "last_validation": {"status": "not_run", "command": "", "summary": ""},
        "completion": {
            "status": "needs_work" if open_items else "ready",
            "score": 0.0 if open_items else 1.0,
            "should_continue": bool(open_items),
            "reasons": ["Workspace instruction files were discovered before a saved checkpoint existed."],
            "next_actions": [recommendation] if recommendation else [],
        },
        "applied": [],
        "recommendation": recommendation,
    }
    return WorkspaceInstructionStatusInfo.model_validate(payload)
