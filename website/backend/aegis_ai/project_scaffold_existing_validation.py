from __future__ import annotations

from pathlib import Path

from .project_scaffold_reporting import command_excerpt, command_ok
from .schemas import CommandRun, ProjectBuildStage


EXISTING_PROJECT_MODE_WARNING = (
    "Existing project mode: Aegis skipped starter-file generation and focused on the current workspace validation state."
)


def existing_project_preamble_stages() -> list[ProjectBuildStage]:
    return [
        ProjectBuildStage(
            id="structure",
            label="Skip scaffold generation",
            status="skipped",
            detail="The target already looks like a project and the prompt asked to build, validate, or repair it.",
        ),
        ProjectBuildStage(
            id="diff",
            label="Prepare file diff preview",
            status="succeeded",
            detail="No starter files are planned for this existing-project pass.",
        ),
        ProjectBuildStage(
            id="apply",
            label="Write files with checkpoint",
            status="skipped",
            detail="No file changes were needed before validation.",
        ),
    ]


def existing_project_install_stage(install_command: str) -> ProjectBuildStage:
    return ProjectBuildStage(
        id="install",
        label="Install dependencies",
        status="skipped" if install_command else "planned",
        detail=(
            "Install command captured but not run automatically for an existing project build/fix pass."
            if install_command
            else "No install command is defined for this project."
        ),
        command=install_command,
    )


def existing_project_skipped_validation_stage(validation_command: str) -> ProjectBuildStage:
    return ProjectBuildStage(
        id="validate",
        label="Run existing project validation",
        status="skipped" if validation_command else "planned",
        detail=(
            "Validation command saved; enable validation to run it immediately."
            if validation_command
            else "No validation command could be inferred for this existing project."
        ),
        command=validation_command,
    )


def existing_project_repair_stage(
    validation: CommandRun | None,
    *,
    validation_command: str,
) -> ProjectBuildStage:
    if validation is not None and not command_ok(validation):
        return ProjectBuildStage(
            id="repair",
            label="Repair loop handoff",
            status="blocked" if not validation.allowed else "planned",
            detail="Captured validation output for the chat repair loop without creating starter files.",
            command=validation_command,
            output_excerpt=command_excerpt(validation),
            error=validation.summary or validation.reason,
        )
    if validation is not None:
        return ProjectBuildStage(
            id="repair",
            label="Repair loop handoff",
            status="skipped",
            detail="Validation passed; no repair loop is needed.",
        )
    return ProjectBuildStage(
        id="repair",
        label="Repair loop handoff",
        status="skipped",
        detail="No validation output was produced.",
    )


def existing_project_memory_stage(*, apply: bool, warnings: list[str]) -> ProjectBuildStage:
    if not apply:
        return ProjectBuildStage(
            id="memory",
            label="Update project memory",
            status="skipped",
            detail="Preview mode only; project memory was not written.",
        )
    return ProjectBuildStage(
        id="memory",
        label="Update project memory",
        status="succeeded",
        detail=(
            "Updated .aegis file index, command history, known-error memory, and instruction checkpoint."
            if not warnings
            else "Project memory updated with warnings: " + "; ".join(warnings[:2])
        ),
    )


def existing_project_next_steps(target: Path, validation: CommandRun | None) -> list[str]:
    return [
        f"Open the workspace at {target}.",
        (
            "Validation passed; continue with the next project task."
            if validation is not None and command_ok(validation)
            else "Review captured validation output and continue the repair loop from the chat workspace."
        ),
        "Ask Auralith Prime to continue from the saved .aegis command history and known-error memory.",
    ]
