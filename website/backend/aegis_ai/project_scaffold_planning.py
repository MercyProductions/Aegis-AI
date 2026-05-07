from __future__ import annotations

from pathlib import Path

from .schemas import ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile


def default_plan_steps(
    preset: ProjectScaffoldPreset,
    project_name: str,
    install_command: str,
    validation_command: str,
) -> list[str]:
    steps = [
        "Detect project intent, requested path, and target stack from the prompt.",
        "Inspect the target folder before deciding whether to update in place or create a clean child project.",
        f"Generate the {preset.label} structure for `{project_name}` with Aegis metadata.",
        "Prepare a file diff preview so the user can see creates versus updates.",
        "Apply files through a checkpointed workspace write.",
    ]
    if install_command:
        steps.append(f"Capture install command `{install_command}` for the dependency pass.")
    if validation_command:
        steps.append(f"Run or save validation command `{validation_command}` and capture stdout/stderr.")
    steps.extend(
        [
            "Record command history, file index, known errors, and project decisions under `.aegis`.",
            "Hand off failed validation output to the repair loop with a bounded retry budget.",
        ]
    )
    return steps


def inspection_detail(
    target: Path,
    existing_files: list[WorkspaceFile],
    profile: WorkspaceDependencyProfile,
) -> str:
    if not target.exists():
        return "Target folder does not exist yet; Aegis will create it as a new project workspace."
    detected: list[str] = []
    if profile.project_type:
        detected.append(profile.project_type)
    detected.extend(profile.frameworks[:3])
    detected.extend(profile.languages[:3])
    detected_text = ", ".join(dict.fromkeys(detected)) if detected else "no framework manifest detected"
    return f"Scanned {len(existing_files)} file(s); detected {detected_text}."


def risk_warnings_for_target(target: Path, *, overwrite: bool) -> list[str]:
    warnings: list[str] = []
    if target.exists():
        visible = []
        try:
            visible = [entry for entry in target.iterdir() if entry.name != ".aegis"]
        except OSError:
            visible = []
        if visible and not overwrite:
            warnings.append(
                "Target folder is not empty; Aegis will avoid overwriting existing visible files and may create a child project."
            )
        elif visible and overwrite:
            warnings.append(
                "Overwrite is enabled for scaffold-owned paths; unrelated user files still remain protected."
            )
    else:
        warnings.append("Target folder will be created inside an allowed workspace root.")
    return warnings
