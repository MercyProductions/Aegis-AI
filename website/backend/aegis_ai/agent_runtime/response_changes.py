from __future__ import annotations

from pathlib import Path

from ..schemas import FileChange
from .contracts import AgentDraft


def sanitize_model_change_paths(draft: AgentDraft, workspace_root: Path) -> AgentDraft:
    workspace = workspace_root.resolve()
    workspace_posix = workspace.as_posix().rstrip("/")
    workspace_lower = workspace_posix.lower()
    workspace_name = workspace.name.lower()
    sanitized: list[FileChange] = []

    for change in draft.changes:
        original = change.path.replace("\\", "/").strip().lstrip("/")
        candidate = original
        lowered = candidate.lower()

        if lowered.startswith(workspace_lower + "/"):
            candidate = candidate[len(workspace_posix) + 1 :]
        else:
            parts = [part for part in candidate.split("/") if part]
            if parts and parts[0].lower() == workspace_name:
                candidate = "/".join(parts[1:])

        if not candidate.strip() or ":" in candidate:
            draft.warnings.append(f"Skipped model change outside the workspace: {change.path}")
            continue

        if candidate != original:
            draft.warnings.append(f"Normalized model change path `{change.path}` to `{candidate}`.")

        sanitized.append(
            FileChange(
                action=change.action,
                path=candidate,
                content=change.content,
                summary=change.summary,
            )
        )

    draft.changes = sanitized
    return draft
