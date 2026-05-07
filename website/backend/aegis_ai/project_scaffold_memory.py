from __future__ import annotations

import json

from .project_scaffold_targets import title_from_name
from .project_scaffold_validation_plan import validation_plan_payload
from .schemas import ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile
from .storage import utc_now


def project_memory_files(
    preset: ProjectScaffoldPreset,
    project_name: str,
    *,
    prompt: str,
    install_command: str,
    validation_command: str,
    plan_steps: list[str],
    risk_warnings: list[str],
    existing_files: list[WorkspaceFile],
    existing_profile: WorkspaceDependencyProfile,
    planned_files: dict[str, str],
) -> dict[str, str]:
    generated_paths = sorted(planned_files)
    memory_paths = [
        ".aegis/command_history.json",
        ".aegis/decisions.md",
        ".aegis/file_index.json",
        ".aegis/known_errors.json",
        ".aegis/validation_plan.json",
    ]
    indexed_paths = sorted({*generated_paths, *memory_paths})
    file_index = {
        "schema": "aegis.file_index.v1",
        "updated_at": utc_now(),
        "project_name": project_name,
        "preset_id": preset.id,
        "preset_label": preset.label,
        "generated_file_count": len(indexed_paths),
        "generated_files": [
            {
                "path": path,
                "kind": "text",
                "size": len(planned_files.get(path, "").encode("utf-8")),
                "source": "project_builder",
            }
            for path in indexed_paths
        ],
        "existing_workspace_snapshot": {
            "file_count": len(existing_files),
            "files": [file.model_dump() for file in existing_files[:80]],
        },
        "detected_profile": existing_profile.model_dump(),
    }
    command_history = {
        "schema": "aegis.command_history.v1",
        "updated_at": utc_now(),
        "commands": [
            {
                "kind": "install",
                "command": install_command,
                "status": "planned" if install_command else "not-configured",
                "source": "project_builder",
            },
            {
                "kind": "validation",
                "command": validation_command,
                "status": "planned" if validation_command else "not-configured",
                "source": "project_builder",
            },
        ],
    }
    known_errors = {
        "schema": "aegis.known_errors.v1",
        "updated_at": utc_now(),
        "errors": [],
    }
    validation_plan = validation_plan_payload(
        preset,
        project_name,
        install_command=install_command,
        validation_command=validation_command,
        validation=None,
        build_log_path="",
    )
    decisions = _strip(
        f"""
        # Aegis Project Decisions

        Project: {title_from_name(project_name)}
        Preset: {preset.label}
        Created: {utc_now()}

        ## Original Request

        {prompt or "No prompt was attached to this project-builder request."}

        ## Plan

        {markdown_list(plan_steps)}

        ## Risk Notes

        {markdown_list(risk_warnings or ["No special risk notes were detected for this scaffold pass."])}

        ## Commands

        - Install: {install_command or "not configured"}
        - Validate: {validation_command or "not configured"}

        ## Working Agreement

        - Use checkpointed changes before modifying generated files.
        - Record build/test failures in `.aegis/known_errors.json`.
        - Prefer small repair passes that rerun the failing command.
        - Keep user-created files outside generated scaffold paths untouched.
        """
    )
    return {
        ".aegis/command_history.json": json.dumps(command_history, indent=2) + "\n",
        ".aegis/decisions.md": decisions,
        ".aegis/file_index.json": json.dumps(file_index, indent=2) + "\n",
        ".aegis/known_errors.json": json.dumps(known_errors, indent=2) + "\n",
        ".aegis/validation_plan.json": json.dumps(validation_plan, indent=2) + "\n",
    }


def markdown_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _strip(value: str) -> str:
    return "\n".join(line.strip() for line in value.strip().splitlines()) + "\n"
