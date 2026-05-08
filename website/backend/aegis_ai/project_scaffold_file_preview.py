from __future__ import annotations

from pathlib import Path

from .schemas import FileChange, ProjectBuildStage, ProjectScaffoldFile, ProjectScaffoldPreset


def scaffold_file_change_preview(
    target: Path,
    preset: ProjectScaffoldPreset,
    files: dict[str, str],
) -> tuple[list[FileChange], list[ProjectScaffoldFile]]:
    changes: list[FileChange] = []
    file_infos: list[ProjectScaffoldFile] = []
    for relative_path, content in files.items():
        target_file = target / relative_path
        action = "update" if target_file.exists() else "create"
        changes.append(
            FileChange(
                action=action,
                path=relative_path,
                content=content,
                summary=f"{action.title()} {relative_path} for the {preset.label} preset.",
            )
        )
        file_infos.append(
            ProjectScaffoldFile(
                path=relative_path,
                action=action,
                summary=f"{action.title()} scaffold file.",
                size=len(content.encode("utf-8")),
            )
        )
    return changes, file_infos


def diff_summary(files: list[ProjectScaffoldFile]) -> list[str]:
    creates = sum(1 for file in files if file.action == "create")
    updates = sum(1 for file in files if file.action == "update")
    deletes = sum(1 for file in files if file.action == "delete")
    summary: list[str] = []
    if creates:
        summary.append(f"+ {creates} create")
    if updates:
        summary.append(f"~ {updates} update")
    if deletes:
        summary.append(f"- {deletes} delete")
    return summary


def diff_preview_stage(files: list[ProjectScaffoldFile]) -> ProjectBuildStage:
    summary = diff_summary(files)
    return ProjectBuildStage(
        id="diff",
        label="Prepare file diff preview",
        status="succeeded",
        detail=", ".join(summary) if summary else "No file changes are planned.",
    )
