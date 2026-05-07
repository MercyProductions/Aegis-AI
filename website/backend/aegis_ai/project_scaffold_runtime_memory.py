from __future__ import annotations

import hashlib

from .project_scaffold_reporting import command_excerpt, command_ok
from .schemas import CommandRun, ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile
from .storage import utc_now


def runtime_file_index_payload(
    preset: ProjectScaffoldPreset,
    project_name: str,
    *,
    files: list[WorkspaceFile],
    profile: WorkspaceDependencyProfile,
) -> dict[str, object]:
    return {
        "schema": "aegis.file_index.v1",
        "updated_at": utc_now(),
        "project_name": project_name,
        "preset_id": preset.id,
        "preset_label": preset.label,
        "workspace_file_count": len(files),
        "files": [file.model_dump() for file in files],
        "detected_profile": profile.model_dump(),
    }


def updated_command_history(
    history: dict[str, object],
    *,
    checkpoint: str | None,
    install: CommandRun | None,
    validation: CommandRun | None,
    install_command: str,
    validation_command: str,
    build_log_path: str,
) -> dict[str, object]:
    commands = history.get("commands")
    if not isinstance(commands, list):
        commands = []

    if install is not None:
        commands.append(
            command_history_entry(
                "install",
                install,
                fallback_command=install_command,
                checkpoint=checkpoint,
                build_log_path=build_log_path,
            )
        )
    if validation is not None:
        commands.append(
            command_history_entry(
                "validation",
                validation,
                fallback_command=validation_command,
                checkpoint=checkpoint,
                build_log_path=build_log_path,
            )
        )
    elif validation_command:
        commands.append(
            {
                "kind": "validation",
                "command": validation_command,
                "status": "saved",
                "summary": "Validation command saved for a later build or repair pass.",
                "checkpoint": checkpoint,
                "created_at": utc_now(),
            }
        )

    if install_command:
        history["install_command"] = install_command
    history["validation_command"] = validation_command
    history["updated_at"] = utc_now()
    history["commands"] = commands[-80:]
    return history


def command_history_entry(
    kind: str,
    run: CommandRun,
    *,
    fallback_command: str,
    checkpoint: str | None,
    build_log_path: str,
) -> dict[str, object]:
    return {
        "kind": kind,
        "command": run.command or fallback_command,
        "cwd": run.cwd,
        "status": "passed" if command_ok(run) else "failed",
        "category": run.category,
        "summary": run.summary or run.reason,
        "exit_code": run.exit_code,
        "timed_out": run.timed_out,
        "steps": run.steps,
        "failed_step": run.failed_step,
        "failed_step_command": run.failed_step_command,
        "diagnostics": run.diagnostics,
        "checkpoint": checkpoint,
        "build_log_path": build_log_path,
        "created_at": utc_now(),
    }


def updated_known_errors(
    known: dict[str, object],
    validation: CommandRun,
    *,
    build_log_path: str,
) -> dict[str, object]:
    errors = known.get("errors")
    if not isinstance(errors, list):
        errors = []
    errors.append(known_error_entry(validation, build_log_path=build_log_path))
    known["updated_at"] = utc_now()
    known["errors"] = errors[-60:]
    return known


def known_error_entry(validation: CommandRun, *, build_log_path: str) -> dict[str, object]:
    return {
        "signature": error_signature(validation),
        "category": validation.category or "unknown",
        "command": validation.command,
        "summary": validation.summary or validation.reason,
        "exit_code": validation.exit_code,
        "failed_step": validation.failed_step,
        "failed_step_command": validation.failed_step_command,
        "diagnostics": validation.diagnostics,
        "output_excerpt": command_excerpt(validation, limit=1400),
        "build_log_path": build_log_path,
        "status": "open",
        "created_at": utc_now(),
    }


def error_signature(validation: CommandRun) -> str:
    text = "|".join(
        [
            validation.category or "unknown",
            validation.command,
            validation.summary or validation.reason,
            command_excerpt(validation, limit=400),
        ]
    )
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
