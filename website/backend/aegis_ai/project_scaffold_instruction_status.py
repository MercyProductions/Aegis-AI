from __future__ import annotations

from .project_scaffold_reporting import command_ok, diagnostics_log, status_text
from .schemas import CommandRun, WorkspaceInstructionFile
from .storage import utc_now


def instruction_status_payload(
    instruction_files: list[WorkspaceInstructionFile],
    *,
    prompt: str,
    validation: CommandRun | None,
    validation_command: str,
    build_log_path: str,
    applied: list[str],
) -> dict[str, object]:
    files = instruction_file_payloads(instruction_files)
    open_items = sum(item.pending_count for item in instruction_files)
    completed_items = sum(item.completed_count for item in instruction_files)
    total_items = sum(item.total_items for item in instruction_files)
    first_pending = first_pending_item(instruction_files)
    validation_payload = validation_status_payload(
        validation,
        validation_command=validation_command,
        build_log_path=build_log_path,
    )
    completion = completion_payload(
        open_items=open_items,
        first_pending=first_pending,
        validation=validation,
        validation_command=validation_command,
    )

    return {
        "schema": "aegis.instruction_status.v1",
        "updated_at": utc_now(),
        "source_message": status_text(prompt, limit=500),
        "instruction_file_count": len(files),
        "open_items": open_items,
        "completed_items": completed_items,
        "total_items": total_items,
        "files": files,
        "last_validation": validation_payload,
        "completion": completion,
        "applied": [status_text(path, limit=220) for path in applied[-40:]],
        "recommendation": recommendation_text(
            open_items=open_items,
            first_pending=first_pending,
            validation=validation,
            validation_command=validation_command,
        ),
    }


def instruction_file_payloads(instruction_files: list[WorkspaceInstructionFile]) -> list[dict[str, object]]:
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
                    text
                    for pending in item.pending_items[:10]
                    if (text := status_text(pending, limit=220))
                ],
                "summary": item.summary,
            }
        )
    return files


def validation_status_payload(
    validation: CommandRun | None,
    *,
    validation_command: str,
    build_log_path: str,
) -> dict[str, object]:
    if validation is None:
        return {
            "status": "saved" if validation_command else "not_run",
            "command": validation_command,
            "summary": (
                "Validation command saved for a later build or repair pass."
                if validation_command
                else "No validation command was recorded for this scaffold."
            ),
            "category": "",
            "exit_code": None,
            "build_log_path": build_log_path,
            "diagnostics": [],
        }

    return {
        "status": "passed" if command_ok(validation) else "failed",
        "command": validation.command or validation_command,
        "summary": validation.summary or validation.reason,
        "category": validation.category,
        "exit_code": validation.exit_code,
        "timed_out": validation.timed_out,
        "build_log_path": build_log_path,
        "failed_step": validation.failed_step,
        "failed_step_command": validation.failed_step_command,
        "diagnostics": validation.diagnostics,
    }


def completion_payload(
    *,
    open_items: int,
    first_pending: str,
    validation: CommandRun | None,
    validation_command: str,
) -> dict[str, object]:
    validation_failed = validation is not None and not command_ok(validation)
    validation_passed = validation is not None and command_ok(validation)
    if validation_failed:
        return {
            "status": "blocked",
            "score": 0.2,
            "should_continue": True,
            "reasons": ["Validation failed during scaffold/build, so repair must happen before expanding scope."],
            "next_actions": [
                f"Repair {validation_repair_target(validation, validation_command)}.",
                "Rerun validation after the repair.",
            ],
        }

    if open_items:
        next_actions = [
            f"Continue the next open instruction item: {status_text(first_pending, limit=220)}"
            if first_pending
            else "Continue the next open instruction item.",
        ]
        if validation is None and validation_command:
            next_actions.append(f"Run the saved validation command: `{validation_command}`.")
        return {
            "status": "needs_work",
            "score": 0.72 if validation_passed else 0.55,
            "should_continue": True,
            "reasons": ["Tracked instruction or roadmap items are still open."],
            "next_actions": next_actions[:6],
        }

    return {
        "status": "ready",
        "score": 1.0 if validation_passed else 0.82,
        "should_continue": False,
        "reasons": ["No open instruction items were detected in the tracked files."],
        "next_actions": ["Summarize the current state and propose the next milestone."],
    }


def recommendation_text(
    *,
    open_items: int,
    first_pending: str,
    validation: CommandRun | None,
    validation_command: str,
) -> str:
    if validation is not None and not command_ok(validation):
        repair_target = validation_repair_target(validation, validation_command)
        if repair_target.startswith("the failure from"):
            return f"Repair validation failure from `{validation.command or validation_command}` before expanding scope."
        return f"Repair validation diagnostic: {repair_target}"
    if open_items and first_pending:
        return f"Continue the next open instruction item: {status_text(first_pending, limit=220)}"
    if open_items:
        return "Continue the next open instruction item."
    if validation is None and validation_command:
        return f"Run the saved validation command: `{validation_command}`."
    return "All tracked instruction items are currently complete; summarize the validated state and propose the next milestone."


def validation_repair_target(validation: CommandRun, validation_command: str) -> str:
    first_diagnostic = diagnostics_log(validation.diagnostics).splitlines()[0].removeprefix("- ").strip()
    if first_diagnostic and first_diagnostic != "(none captured)":
        return first_diagnostic
    return f"the failure from `{validation.command or validation_command}`"


def first_pending_item(instruction_files: list[WorkspaceInstructionFile]) -> str:
    return next(
        (
            pending.strip()
            for item in instruction_files
            for pending in item.pending_items
            if pending.strip()
        ),
        "",
    )
