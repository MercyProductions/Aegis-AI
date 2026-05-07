from __future__ import annotations

import re
import uuid
from pathlib import Path

from .project_scaffold_reporting import diagnostics_log, log_text
from .project_scaffold_targets import title_from_name
from .schemas import CommandRun, ProjectScaffoldPreset
from .storage import utc_now


def write_build_log(
    target: Path,
    *,
    preset: ProjectScaffoldPreset,
    project_name: str,
    checkpoint: str | None,
    install: CommandRun | None,
    validation: CommandRun | None,
    install_command: str,
    validation_command: str,
) -> str:
    if install is None and validation is None:
        return ""

    timestamp = re.sub(r"[^0-9A-Za-z]+", "-", utc_now()).strip("-") or "now"
    log_name = f"{timestamp}-{uuid.uuid4().hex[:8]}.md"
    relative_path = f".aegis/build_logs/{log_name}"
    path = target / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_log_content(
        preset=preset,
        project_name=project_name,
        checkpoint=checkpoint,
        install=install,
        validation=validation,
        install_command=install_command,
        validation_command=validation_command,
    )
    path.write_text(content, encoding="utf-8")
    return relative_path


def build_log_content(
    *,
    preset: ProjectScaffoldPreset,
    project_name: str,
    checkpoint: str | None,
    install: CommandRun | None,
    validation: CommandRun | None,
    install_command: str,
    validation_command: str,
) -> str:
    sections = [
        "# Aegis Build Log",
        "",
        f"- Created: {utc_now()}",
        f"- Project: {title_from_name(project_name)}",
        f"- Preset: {preset.label}",
        f"- Checkpoint: {checkpoint or 'none'}",
        f"- Install command: {install_command or 'not configured'}",
        f"- Validation command: {validation_command or 'not configured'}",
        "",
    ]
    if install is not None:
        sections.append(command_log_section("Install", install))
    if validation is not None:
        sections.append(command_log_section("Validation", validation))
    return "\n".join(sections).rstrip() + "\n"


def command_log_section(title: str, run: CommandRun) -> str:
    return "\n".join(
        [
            f"## {title}",
            "",
            f"- Command: {run.command}",
            f"- CWD: {run.cwd}",
            f"- Allowed: {str(run.allowed).lower()}",
            f"- Exit code: {run.exit_code if run.exit_code is not None else 'none'}",
            f"- Timed out: {str(run.timed_out).lower()}",
            f"- Category: {run.category or 'unknown'}",
            f"- Summary: {run.summary or run.reason or 'No summary was provided.'}",
            "",
            "### Diagnostics",
            "",
            diagnostics_log(run.diagnostics),
            "",
            "### Stdout",
            "",
            "```text",
            log_text(run.stdout),
            "```",
            "",
            "### Stderr",
            "",
            "```text",
            log_text(run.stderr),
            "```",
            "",
            "### Reason",
            "",
            "```text",
            log_text(run.reason),
            "```",
            "",
        ]
    )
