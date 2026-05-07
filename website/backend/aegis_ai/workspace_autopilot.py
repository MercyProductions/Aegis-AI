from __future__ import annotations

from typing import Any

from .schemas import (
    WorkspaceAutopilotStatusResponse,
    WorkspaceDependencyProfile,
    WorkspaceInstructionStatusInfo,
    WorkspaceProjectManifest,
    WorkspaceReadinessInfo,
    WorkspaceValidationPlanInfo,
)
from .validation_diagnostics import (
    failed_step_display,
    first_diagnostic_brief as validation_first_diagnostic_brief,
)


def latest_history_validation(command_history: dict[str, Any]) -> dict[str, Any]:
    commands = command_history.get("commands") if isinstance(command_history, dict) else []
    if not isinstance(commands, list):
        return {}
    for item in reversed(commands):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "validation" or kind.startswith("verification:"):
            return item
    return {}


def status_value(value: Any, *, limit: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def first_diagnostic_brief(payload: dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return ""
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        file = status_value(diagnostic.get("file"), limit=150)
        if not file:
            continue
        line = status_value(diagnostic.get("line"), limit=20)
        column = status_value(diagnostic.get("column"), limit=20)
        location = file
        if line:
            location += f":{line}"
        if column:
            location += f":{column}"
        severity = status_value(diagnostic.get("severity"), limit=24)
        code = status_value(diagnostic.get("code"), limit=32)
        detail = " ".join(part for part in (severity, code) if part)
        return f"{location} {detail}".strip()
    return ""


def compact_repair_brief(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = status_value(payload.get("failed_step"), limit=40)
    failed_step_command = status_value(payload.get("failed_step_command"), limit=220)
    failed_command = status_value(payload.get("command") or validation_command, limit=220)
    diagnostic = first_diagnostic_brief(payload)

    parts: list[str] = []
    if failed_step and failed_step_command:
        parts.append(f"Repair step {failed_step}: {failed_step_command}")
    elif failed_step_command:
        parts.append(f"Repair {failed_step_command}")
    elif diagnostic:
        parts.append(f"Repair diagnostic {diagnostic}")
    elif failed_command:
        parts.append(f"Repair {failed_command}")
    else:
        parts.append("Repair failed validation")

    if diagnostic and not parts[0].endswith(diagnostic):
        parts.append(f"diagnostic {diagnostic}")
    parts.append("rerun validation")
    return "; ".join(parts)


def compact_validation_repair_brief(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = failed_step_display(payload)
    diagnostic = validation_first_diagnostic_brief(payload)
    failed_command = str(payload.get("command") or validation_command).strip()
    parts: list[str] = []
    if failed_step:
        parts.append(f"Repair {failed_step}")
    elif diagnostic:
        parts.append(f"Repair diagnostic {diagnostic}")
    elif failed_command:
        parts.append(f"Repair {failed_command}")
    else:
        parts.append("Repair failed validation")
    if failed_step and diagnostic:
        parts.append(f"diagnostic {diagnostic}")
    parts.append("rerun validation")
    return "; ".join(parts)


def build_workspace_autopilot_status(
    *,
    workspace_root: str,
    manifest: WorkspaceProjectManifest | None,
    dependency_profile: WorkspaceDependencyProfile,
    instruction_status: WorkspaceInstructionStatusInfo,
    validation_plan: WorkspaceValidationPlanInfo,
    command_history: dict[str, Any],
    readiness: WorkspaceReadinessInfo,
) -> WorkspaceAutopilotStatusResponse:
    validation_command = (
        validation_plan.validation_command
        or (manifest.validation_command if manifest else "")
        or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
        or str(command_history.get("validation_command") or "").strip()
    )
    last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
    instruction_last_validation = (
        instruction_status.last_validation
        if isinstance(instruction_status.last_validation, dict)
        else {}
    )
    latest_validation = latest_history_validation(command_history) or last_run or instruction_last_validation
    latest_validation_status = str(latest_validation.get("status") or "").strip()
    failed_step = str(latest_validation.get("failed_step") or "").strip()
    failed_step_command = str(latest_validation.get("failed_step_command") or "").strip()
    first_diagnostic = first_diagnostic_brief(latest_validation)
    repair_brief = ""
    instruction_source = (
        instruction_status.schema_version
        or instruction_status.source_message
        or ("workspace instructions" if instruction_status.files else "")
    )
    next_open_items = _next_open_instruction_items(instruction_status)
    dependency_signals = _dependency_signals(dependency_profile)

    open_items_count = max(0, int(instruction_status.open_items or 0))
    total_items_count = max(0, int(instruction_status.total_items or 0))
    large_task_mode = (
        open_items_count >= 12
        or total_items_count >= 18
        or len(dependency_signals) >= 8
        or (readiness.status in {"needs_repair", "needs_validation"} and total_items_count >= 14)
    )
    if large_task_mode:
        complexity = "epic" if open_items_count >= 24 or total_items_count >= 32 or len(dependency_signals) >= 12 else "large"
    elif open_items_count >= 6 or total_items_count >= 10 or len(dependency_signals) >= 5:
        complexity = "standard"
    else:
        complexity = "focused"

    execution_lanes = _execution_lanes(
        manifest=manifest,
        dependency_signals=dependency_signals,
        validation_command=validation_command,
        has_instruction_files=bool(instruction_status.files),
    )

    phase = "unconfigured"
    should_continue = False
    recommended_mode = "build"
    run_validation = False
    max_repair_attempts = 0
    pass_budget = 0
    stop_reason = ""
    next_action = readiness.next_action.strip()

    if readiness.status == "needs_repair":
        phase = "repair"
        should_continue = True
        recommended_mode = "develop"
        run_validation = True
        max_repair_attempts = 3
        pass_budget = 6
    elif readiness.status == "needs_validation":
        phase = "validate"
        should_continue = True
        recommended_mode = "develop"
        run_validation = True
        max_repair_attempts = 2
        pass_budget = 4
    elif readiness.status == "needs_work":
        phase = "work"
        should_continue = True
        recommended_mode = "build"
        run_validation = bool(validation_command)
        max_repair_attempts = 2 if validation_command else 0
        pass_budget = max(4, min(18, open_items_count + 4))
    elif readiness.status == "ready":
        phase = "ready"
        stop_reason = "Workspace readiness is ready; no open tracked work or failed validation is blocking handoff."
        pass_budget = 0
    else:
        stop_reason = "Workspace is not configured enough for safe autopilot continuation."
        pass_budget = 0

    if should_continue and large_task_mode:
        if phase == "work":
            if complexity == "epic":
                pass_budget = max(pass_budget, min(50, max(30, open_items_count + 12, total_items_count)))
            else:
                pass_budget = max(pass_budget, min(36, max(22, open_items_count + 8)))
        elif phase == "repair":
            pass_budget = max(pass_budget, 14 if complexity == "epic" else 10)
            max_repair_attempts = max(max_repair_attempts, 4)
        elif phase == "validate":
            pass_budget = max(pass_budget, 10 if complexity == "epic" else 7)
            max_repair_attempts = max(max_repair_attempts, 3)

    if not next_action:
        if phase == "repair":
            next_action = "Repair the captured validation failure and rerun validation."
        elif phase == "validate":
            next_action = f"Run validation command: {validation_command}" if validation_command else "Infer and run validation."
        elif phase == "work":
            next_action = "Continue the next open project instruction item, then validate."
        elif phase == "ready":
            next_action = "Summarize the finished state and suggest the next milestone."
        else:
            next_action = "Add project metadata and a validation command."

    if phase == "repair" and latest_validation:
        repair_brief = compact_repair_brief(latest_validation, validation_command=validation_command)

    suggested_prompt = next_action
    if should_continue:
        suggested_prompt = (
            "Continue autopilot from the current workspace state.\n\n"
            f"Objective: {next_action}\n"
            f"Phase: {phase}\n"
            f"Validation command: {validation_command or 'infer if needed'}"
        )
        if repair_brief:
            suggested_prompt += f"\nRepair brief: {repair_brief}"
        if large_task_mode:
            suggested_prompt += (
                "\nLarge-task protocol:\n"
                "- Keep the current target path, stack, and project type pinned.\n"
                "- Complete one coherent vertical slice before broadening scope.\n"
                "- Update TODO/roadmap/checklist state as items are completed.\n"
                "- Capture validation output, repair obvious failures, and summarize remaining blockers.\n"
                f"- Execution lanes: {', '.join(execution_lanes)}"
            )
        if next_open_items:
            suggested_prompt += "\nNext open instruction items:\n" + "\n".join(
                f"- {item}" for item in next_open_items[:6]
            )

    recommendations: list[str] = []
    if should_continue:
        recommendations.append(f"Autopilot can continue for up to {pass_budget} pass(es) before reassessing readiness.")
    if repair_brief:
        recommendations.append(f"Repair brief: {repair_brief}.")
    if phase == "repair" and failed_step:
        recommendations.append(f"Start with failed validation step: {failed_step}.")
    if phase == "repair" and failed_step_command:
        recommendations.append(f"Failed command: {failed_step_command}.")
    if phase == "repair" and first_diagnostic:
        recommendations.append(f"First diagnostic: {first_diagnostic}.")
    if validation_command and run_validation:
        recommendations.append(f"Run validation after implementation or repair: {validation_command}.")
    if instruction_status.open_items:
        recommendations.append(f"Work through {instruction_status.open_items} open instruction item(s) before adding unrelated scope.")
    if large_task_mode:
        recommendations.append(
            f"Large-task mode is active ({complexity}); continue in vertical slices across {', '.join(execution_lanes)}."
        )
    if stop_reason:
        recommendations.append(stop_reason)

    return WorkspaceAutopilotStatusResponse(
        workspace_root=workspace_root,
        phase=phase,
        should_continue=should_continue,
        recommended_mode=recommended_mode,
        suggested_prompt=suggested_prompt,
        next_action=next_action,
        stop_reason=stop_reason,
        pass_budget=pass_budget,
        run_validation=run_validation,
        max_repair_attempts=max_repair_attempts,
        complexity=complexity,
        large_task_mode=large_task_mode,
        estimated_passes_remaining=pass_budget if should_continue else 0,
        execution_lanes=execution_lanes,
        readiness=readiness,
        open_items=instruction_status.open_items,
        completed_items=instruction_status.completed_items,
        total_items=instruction_status.total_items,
        validation_command=validation_command,
        latest_validation_status=latest_validation_status,
        failed_step=failed_step,
        failed_step_command=failed_step_command,
        first_diagnostic=first_diagnostic,
        repair_brief=repair_brief,
        blockers=readiness.blockers,
        signals=readiness.signals,
        recommendations=recommendations,
        instruction_files=instruction_status.files[:12],
        next_open_items=next_open_items,
        instruction_source=instruction_source,
    )


def _next_open_instruction_items(instruction_status: WorkspaceInstructionStatusInfo) -> list[str]:
    next_open_items: list[str] = []
    seen_open_items: set[str] = set()
    for instruction_file in instruction_status.files:
        for item in instruction_file.pending_items:
            text = item.strip()
            key = text.casefold()
            if not text or key in seen_open_items:
                continue
            next_open_items.append(text)
            seen_open_items.add(key)
            if len(next_open_items) >= 12:
                break
        if len(next_open_items) >= 12:
            break
    return next_open_items


def _dependency_signals(dependency_profile: WorkspaceDependencyProfile) -> set[str]:
    return {
        str(value).strip().lower()
        for values in (
            dependency_profile.languages,
            dependency_profile.frameworks,
            dependency_profile.package_managers,
            dependency_profile.build_systems,
            dependency_profile.database_tools,
            dependency_profile.config_files,
        )
        for value in values
        if str(value).strip()
    }


def _execution_lanes(
    *,
    manifest: WorkspaceProjectManifest | None,
    dependency_signals: set[str],
    validation_command: str,
    has_instruction_files: bool,
) -> list[str]:
    execution_lanes: list[str] = []

    def add_lane(value: str) -> None:
        if value and value not in execution_lanes:
            execution_lanes.append(value)

    stack_text = " ".join(
        [
            manifest.framework if manifest else "",
            manifest.language if manifest else "",
            manifest.package_manager if manifest else "",
            " ".join(manifest.tags) if manifest else "",
            " ".join(dependency_signals),
        ]
    ).lower()
    if any(term in stack_text for term in ("react", "vite", "next", "vue", "svelte", "frontend", "web")):
        add_lane("frontend")
    if any(term in stack_text for term in ("fastapi", "express", "django", "api", "server", "backend")):
        add_lane("backend")
    if any(term in stack_text for term in ("sqlite", "postgres", "mysql", "database", "prisma", "drizzle")):
        add_lane("database")
    if any(term in stack_text for term in ("c++", "cpp", "cmake", "msbuild", "sln", "vcxproj", "native", "dll", "exe")):
        add_lane("native")
    if any(term in stack_text for term in ("pytest", "vitest", "ctest", "test", "validation", "build")) or validation_command:
        add_lane("validation")
    if has_instruction_files:
        add_lane("roadmap")
    return execution_lanes or ["source", "validation", "handoff"]
