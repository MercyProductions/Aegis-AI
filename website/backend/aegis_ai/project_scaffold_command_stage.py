from __future__ import annotations

from pathlib import Path

from .commands import CommandRunner
from .project_scaffold_reporting import command_excerpt, command_ok, command_run
from .schemas import CommandRun, ProjectBuildStage


def run_command_stage(
    commands: CommandRunner | None,
    *,
    sandbox_profile: str | None,
    stage_id: str,
    label: str,
    command: str,
    target: Path,
) -> tuple[ProjectBuildStage, CommandRun | None]:
    if commands is None:
        return (
            ProjectBuildStage(
                id=stage_id,
                label=label,
                status="blocked",
                detail="Command runner is not available in this runtime.",
                command=command,
                error="Command runner unavailable.",
            ),
            None,
        )

    result = commands.run(command, target, sandbox_profile=sandbox_profile)
    run = command_run(result, label=label)
    ok = command_ok(run)
    status = "succeeded" if ok else ("blocked" if not run.allowed else "failed")
    return (
        ProjectBuildStage(
            id=stage_id,
            label=label,
            status=status,
            detail=run.summary or run.reason,
            command=command,
            output_excerpt=command_excerpt(run),
            error="" if ok else (run.summary or run.reason),
        ),
        run,
    )
