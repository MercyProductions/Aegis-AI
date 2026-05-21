from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import editing as editing_runtime
from . import workflow_runtime
from .diagnostics import scrub
from .knowledge import impact_analysis
from .memory import ProjectMemory, utc_now
from .safety import is_ignored_path, is_safe_to_edit, is_secret_like
from .validation import detect_validation_commands
from .workspace_intelligence import workspace_intelligence


EXECUTIONS_FILE = "engineering-executions.json"
EVENTS_FILE = "engineering-events.json"
JOURNAL_FILE = "engineering-journal.json"
MEMORY_FILE = "engineering-memory.json"
AUDIT_FILE = "engineering-audit.md"
MAX_EXECUTIONS = 100
MAX_EVENTS = 1500
MAX_LOGS_PER_EXECUTION = 500
MAX_JOURNAL_ENTRIES = 750
MAX_TARGET_FILES = 100

PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("intake", "Intake"),
    ("workspace_analysis", "Workspace Analysis"),
    ("planning", "Planning"),
    ("task_decomposition", "Task Decomposition"),
    ("implementation", "Implementation"),
    ("validation", "Validation"),
    ("repair", "Repair"),
    ("review", "Review"),
    ("approval", "Approval"),
    ("checkpoint", "Checkpoint"),
    ("apply", "Apply"),
    ("completion_summary", "Completion Summary"),
)
PREP_STAGES = {"intake", "workspace_analysis", "planning", "task_decomposition"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
EXECUTION_MODES = {
    "safe_assisted",
    "approval_every_step",
    "semi_autonomous",
    "autonomous_validate_only",
    "roadmap_execution",
    "repair_only",
}
MUTATING_STAGES = {"implementation", "checkpoint", "apply"}
DEFAULT_RESTRICTED_DIRS = [
    ".git",
    ".aegis",
    ".env",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "bin",
    "obj",
    "Library",
    "Temp",
]


class EngineeringExecutionPersistenceError(RuntimeError):
    """Raised when Core engineering execution state cannot be persisted."""


class EngineeringExecutionNotFoundError(KeyError):
    """Raised when an engineering execution id is not available."""


def execution_modes() -> dict[str, Any]:
    return {
        "modes": [
            {
                "id": "safe_assisted",
                "label": "Safe Assisted",
                "description": "Plan and track work with approval-gated validation, checkpoint, and apply stages.",
            },
            {
                "id": "approval_every_step",
                "label": "Approval Every Step",
                "description": "Every stage waits for explicit approval before it can complete.",
            },
            {
                "id": "semi_autonomous",
                "label": "Semi Autonomous",
                "description": "Non-mutating stages can advance; file writes still require approval and checkpoints.",
            },
            {
                "id": "autonomous_validate_only",
                "label": "Autonomous Validate Only",
                "description": "Core may run validation loops, but implementation and apply remain skipped.",
            },
            {
                "id": "roadmap_execution",
                "label": "Roadmap Execution",
                "description": "Execution is linked to roadmap phase/item state and roadmap-specific checkpoints.",
            },
            {
                "id": "repair_only",
                "label": "Repair Only",
                "description": "Focus the pipeline on validation failure capture, bounded repair, review, and rollback.",
            },
        ],
        "rules": [
            "All file mutation is inspectable and approval-gated.",
            "Checkpoint creation must precede apply.",
            "Validation and repair loops have bounded retry counts.",
            "Execution records are stored under the workspace .aegis folder.",
        ],
    }


def create_execution(
    workspace: str | Path,
    goal: str,
    *,
    mode: str = "safe_assisted",
    source_client: str = "unknown",
    constraints: list[str] | None = None,
    target_files: list[str] | None = None,
    context_files: list[str] | None = None,
    validation_command: list[str] | None = None,
    max_repair_attempts: int | None = None,
    max_file_modifications: int = 25,
    approval_requirements: list[str] | None = None,
    roadmap_item_id: str | None = None,
    roadmap_phase_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    create_workflow: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    normalized_mode = _normalize_mode(mode)
    cleaned_goal = scrub(goal).strip()
    if not cleaned_goal:
        raise ValueError("engineering execution goal is required")

    normalized_targets = _normalize_target_files(root, target_files or [])
    normalized_context = _normalize_context_files(root, context_files or [])
    file_limit = max(1, min(100, int(max_file_modifications or 25)))
    repair_limit = _mode_repair_limit(normalized_mode, max_repair_attempts)
    if len(normalized_targets) > file_limit:
        raise ValueError(f"target file count exceeds max_file_modifications ({file_limit})")

    memory_snapshot = engineering_memory(root, refresh=False, persist=True)
    validation_requirements = _validation_requirements(root, validation_command)
    risk = _estimate_risk(cleaned_goal, normalized_targets, memory_snapshot, file_limit)
    knowledge_impacts = _knowledge_impacts(root, normalized_targets)
    if knowledge_impacts:
        impacted_count = sum(len(item.get("affected_files", [])) for item in knowledge_impacts)
        if impacted_count > file_limit:
            risk["level"] = "high"
            risk.setdefault("reasons", []).append("Knowledge graph impact exceeds the configured file modification limit.")
    now = utc_now()
    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    workflow_id = None
    workflow_link: dict[str, Any] = {}
    warnings: list[str] = []
    if create_workflow:
        try:
            workflow_dashboard = workflow_runtime.create_workflow(
                root,
                _workflow_type_for_mode(normalized_mode, cleaned_goal),
                cleaned_goal,
                source_client=source_client or "unknown",
                context_files=normalized_context,
                metadata={
                    "engineering_execution_id": execution_id,
                    "mode": normalized_mode,
                    "roadmap_item_id": roadmap_item_id or "",
                },
            )
            workflow = workflow_dashboard.get("workflow", {}) if isinstance(workflow_dashboard, dict) else {}
            workflow_id = str(workflow.get("id") or "") or None
            workflow_link = {
                "workflow_id": workflow_id,
                "workflow_type": workflow.get("workflow_type"),
                "status": workflow.get("status"),
            }
        except Exception as exc:  # pragma: no cover - defensive compatibility guard.
            warnings.append(f"workflow graph link could not be created: {scrub(str(exc))}")

    stages = _initial_stages(normalized_mode, now)
    subtasks = _decompose_subtasks(execution_id, stages, normalized_targets, validation_requirements, now)
    active_stage_key = _first_active_stage(stages)
    plan = {
        "goals": [cleaned_goal],
        "constraints": [scrub(item).strip() for item in constraints or [] if str(item).strip()],
        "target_files": normalized_targets,
        "estimated_risk": risk,
        "dependencies": _dependency_edges(subtasks),
        "validation_requirements": validation_requirements,
        "knowledge_impact": knowledge_impacts,
        "rollback_strategy": _rollback_strategy(normalized_targets),
        "approval_requirements": _approval_requirements(
            normalized_mode,
            approval_requirements or [],
            validation_requirements,
        ),
        "progress_tracking": {
            "stage_count": len(stages),
            "subtask_count": len(subtasks),
            "active_stage": active_stage_key,
            "completed_stage_count": sum(1 for stage in stages if stage.get("status") == "completed"),
        },
        "implementation_phases": _implementation_phases(normalized_targets, cleaned_goal),
        "validation_checkpoints": _validation_checkpoints(validation_requirements),
        "repair_checkpoints": _repair_checkpoints(repair_limit),
    }
    execution = {
        "id": execution_id,
        "project_id": _project_id(root),
        "workspace": str(root),
        "goal": cleaned_goal,
        "mode": normalized_mode,
        "status": "queued",
        "progress": 0,
        "active_stage_key": active_stage_key,
        "workflow_id": workflow_id,
        "workflow_link": workflow_link,
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "finished_at": None,
        "source_client": source_client or "unknown",
        "stages": stages,
        "subtasks": subtasks,
        "execution_graph": _execution_graph(stages),
        "task_dependency_graph": _task_dependency_graph(subtasks),
        "execution_plan": plan,
        "workspace_memory": _memory_ref(memory_snapshot),
        "safety": _safety_controls(normalized_mode, file_limit, repair_limit),
        "roadmap_link": _roadmap_link(roadmap_item_id, roadmap_phase_id, normalized_mode),
        "validation_chain": [],
        "repair_history": [],
        "approvals": [],
        "rollbacks": [],
        "modified_files": [],
        "checkpoints": [],
        "warnings": warnings,
        "errors": [],
        "journal": [],
        "logs": [],
        "metrics": _execution_metrics_empty(repair_limit),
        "metadata": _safe_metadata(metadata or {}),
    }
    _refresh_execution_state(execution)
    _append_execution_log(execution, "execution.created", f"Created {normalized_mode} engineering execution.", {"risk": risk})
    memory = _memory(root)
    _persist_execution(memory, execution)
    event = _record_event(memory, execution, "execution.created", "Engineering execution plan created.", {"risk": risk})
    _append_global_journal(memory, execution, event)
    return execution_dashboard(root, execution_id)


def list_executions(workspace: str | Path, *, include_completed: bool = True, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    executions = _load_executions(memory)
    if not include_completed:
        executions = [item for item in executions if item.get("status") not in TERMINAL_STATUSES]
    max_items = max(1, min(200, int(limit)))
    executions = sorted(executions, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:max_items]
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "executions": executions,
        "active_executions": [item for item in executions if item.get("status") not in TERMINAL_STATUSES],
    }


def execution_dashboard(workspace: str | Path, execution_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    execution = _get_execution(memory, execution_id)
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "execution": execution,
        "timeline": _execution_timeline(memory, execution_id),
        "metrics": execution_metrics(root),
        "memory": engineering_memory(root, refresh=False, persist=True),
    }


def step_execution(
    workspace: str | Path,
    execution_id: str,
    *,
    action: str = "advance",
    stage_key: str | None = None,
    approval: bool = False,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    execution = _get_execution(memory, execution_id)
    action_name = _normalize_action(action)
    safe_payload = _safe_metadata(payload or {})

    if execution.get("status") in TERMINAL_STATUSES and action_name not in {"record_log"}:
        raise ValueError(f"engineering execution is already {execution.get('status')}")

    if action_name == "pause":
        execution["status"] = "paused"
        _append_execution_log(execution, "execution.paused", summary or "Engineering execution paused.")
    elif action_name == "resume":
        if execution.get("status") != "paused":
            raise ValueError("only paused executions can be resumed")
        execution["status"] = "queued"
        _append_execution_log(execution, "execution.resumed", summary or "Engineering execution resumed.")
    elif action_name == "cancel":
        _cancel_execution(execution, summary or "Engineering execution cancelled.")
    elif action_name == "record_log":
        _append_execution_log(execution, "execution.log", summary or "Client log recorded.", safe_payload)
    elif action_name == "approve":
        _record_approval(execution, stage_key or execution.get("active_stage_key"), summary or "Approval recorded.", safe_payload)
    elif action_name == "record_validation":
        _record_validation_result(execution, safe_payload, summary=summary or "Validation result recorded.")
    elif action_name == "record_repair":
        _record_repair_attempt(execution, safe_payload, summary=summary or "Repair attempt recorded.")
    elif action_name == "record_rollback":
        _record_rollback(execution, safe_payload, summary=summary or "Rollback recorded.")
    elif action_name == "complete_stage":
        stage = _select_stage(execution, stage_key)
        _complete_stage(execution, stage, summary or f"{stage['label']} completed.", safe_payload)
    elif action_name == "fail_stage":
        stage = _select_stage(execution, stage_key)
        _fail_stage(execution, stage, summary or f"{stage['label']} failed.", safe_payload)
    elif action_name == "run_validation":
        stage = _select_stage(execution, stage_key or "validation")
        _run_validation_stage(root, execution, stage, approval=approval, summary=summary, payload=safe_payload)
    elif action_name == "apply":
        stage = _select_stage(execution, stage_key or "apply")
        _run_apply_stage(root, execution, stage, approval=approval, summary=summary, payload=safe_payload)
    else:
        stage = _select_stage(execution, stage_key)
        _advance_stage(root, execution, stage, approval=approval, summary=summary, payload=safe_payload)

    _refresh_execution_state(execution)
    _persist_execution(memory, execution)
    event = _record_event(
        memory,
        execution,
        f"execution.{action_name}",
        summary or f"Engineering execution action `{action_name}` recorded.",
        {"stage_key": stage_key or execution.get("active_stage_key"), "approval": approval, "payload": safe_payload},
    )
    _append_global_journal(memory, execution, event)
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "execution": execution,
        "event": event,
        "timeline": _execution_timeline(memory, execution_id),
    }


def execution_timeline(workspace: str | Path, execution_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    execution = _get_execution(memory, execution_id)
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "execution_id": execution_id,
        "timeline": _execution_timeline(memory, execution_id),
        "stage_timeline": [
            {
                "stage_key": stage.get("key"),
                "label": stage.get("label"),
                "status": stage.get("status"),
                "started_at": stage.get("started_at"),
                "finished_at": stage.get("finished_at"),
                "logs": stage.get("logs", []),
            }
            for stage in execution.get("stages", [])
            if isinstance(stage, dict)
        ],
        "execution_graph": execution.get("execution_graph", {}),
        "task_dependency_graph": execution.get("task_dependency_graph", {}),
        "validation_chain": execution.get("validation_chain", []),
        "repair_history": execution.get("repair_history", []),
    }


def engineering_memory(workspace: str | Path, *, refresh: bool = False, persist: bool = True) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    cache_path = memory.root / MEMORY_FILE
    if persist and not refresh and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                cached["cache_hit"] = True
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    intelligence = workspace_intelligence(root, persist=True, refresh=refresh)
    metadata = intelligence.get("metadata") if isinstance(intelligence.get("metadata"), dict) else {}
    health = intelligence.get("health") if isinstance(intelligence.get("health"), dict) else {}
    semantic = intelligence.get("semantic_summaries") if isinstance(intelligence.get("semantic_summaries"), dict) else {}
    result = {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": utc_now(),
        "cache_hit": False,
        "architecture_summary": _architecture_summary(intelligence),
        "dependency_graph": intelligence.get("dependency_graph", {}),
        "coding_conventions": _coding_conventions(root, intelligence),
        "framework_usage": _framework_usage(intelligence),
        "entry_points": metadata.get("entry_points") or intelligence.get("project_metadata", {}).get("entry_points", []),
        "build_systems": intelligence.get("build_systems", []),
        "risk_areas": _risk_areas(health),
        "generated_knowledge_summaries": {
            "project_summary": semantic.get("project_summary", {}),
            "architecture_map": semantic.get("architecture_map", {}),
            "knowledge_summary": semantic.get("knowledge_summary", {}),
            "roadmap": semantic.get("roadmap", {}),
        },
        "validation_commands": [
            {"name": command.name, "command": command.command, "reason": command.reason}
            for command in detect_validation_commands(root)
        ],
        "memory_paths": intelligence.get("memory_paths", {}),
    }
    if persist:
        memory.write_json(MEMORY_FILE, result)
        memory.write_generated_markdown("engineering-memory.md", "Engineering Memory", _render_memory_markdown(result))
    return result


def execution_metrics(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    executions = _load_executions(memory)
    status_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    durations: list[float] = []
    validation_runs = 0
    validation_passes = 0
    repair_attempts = 0
    repair_successes = 0
    iterations: list[int] = []
    model_usage: dict[str, int] = {}
    modified_counts: list[int] = []
    rollback_count = 0
    for execution in executions:
        status = str(execution.get("status") or "unknown")
        mode = str(execution.get("mode") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        duration = _duration_seconds(execution.get("started_at"), execution.get("finished_at") or execution.get("updated_at"))
        if duration is not None:
            durations.append(duration)
        validation_chain = execution.get("validation_chain", []) if isinstance(execution.get("validation_chain"), list) else []
        validation_runs += len(validation_chain)
        validation_passes += sum(1 for item in validation_chain if isinstance(item, dict) and item.get("ok"))
        repairs = execution.get("repair_history", []) if isinstance(execution.get("repair_history"), list) else []
        repair_attempts += len(repairs)
        repair_successes += sum(1 for item in repairs if isinstance(item, dict) and item.get("status") in {"completed", "successful", "success"})
        iterations.append(int((execution.get("metrics") or {}).get("iteration_count") or len(validation_chain) + len(repairs)))
        modified = execution.get("modified_files", []) if isinstance(execution.get("modified_files"), list) else []
        modified_counts.append(len(set(str(item) for item in modified)))
        rollbacks = execution.get("rollbacks", []) if isinstance(execution.get("rollbacks"), list) else []
        rollback_count += len(rollbacks)
        for entry in execution.get("journal", []) if isinstance(execution.get("journal"), list) else []:
            payload = entry.get("payload") if isinstance(entry, dict) and isinstance(entry.get("payload"), dict) else {}
            model = payload.get("model") or payload.get("model_id")
            if model:
                key = str(model)
                model_usage[key] = model_usage.get(key, 0) + 1
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "execution_count": len(executions),
        "active_execution_count": sum(1 for item in executions if item.get("status") not in TERMINAL_STATUSES),
        "status_counts": status_counts,
        "mode_counts": mode_counts,
        "average_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0,
        "validation": {
            "runs": validation_runs,
            "passes": validation_passes,
            "success_rate": round(validation_passes / validation_runs, 3) if validation_runs else None,
        },
        "repair": {
            "attempts": repair_attempts,
            "successes": repair_successes,
            "success_rate": round(repair_successes / repair_attempts, 3) if repair_attempts else None,
        },
        "average_iterations": round(sum(iterations) / len(iterations), 3) if iterations else 0,
        "model_usage": model_usage,
        "model_usage_efficiency": _model_efficiency(model_usage, validation_passes, validation_runs),
        "files_modified_per_workflow": round(sum(modified_counts) / len(modified_counts), 3) if modified_counts else 0,
        "rollback_frequency": round(rollback_count / len(executions), 3) if executions else 0,
        "recent_events": _load_events(memory)[:25],
    }


def create_roadmap_execution(
    workspace: str | Path,
    *,
    goal: str,
    roadmap_item_id: str = "",
    roadmap_phase_id: str = "",
    source_client: str = "unknown",
    target_files: list[str] | None = None,
    validation_command: list[str] | None = None,
    constraints: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned_goal = goal.strip() or f"Execute roadmap item {roadmap_item_id or 'next'}"
    return create_execution(
        workspace,
        cleaned_goal,
        mode="roadmap_execution",
        source_client=source_client,
        constraints=constraints or ["Keep roadmap item state synchronized with validation and checkpoint history."],
        target_files=target_files or [],
        validation_command=validation_command,
        roadmap_item_id=roadmap_item_id or None,
        roadmap_phase_id=roadmap_phase_id or None,
        metadata={"roadmap_execution": True, **_safe_metadata(metadata or {})},
    )


def _advance_stage(
    root: Path,
    execution: dict[str, Any],
    stage: dict[str, Any],
    *,
    approval: bool,
    summary: str | None,
    payload: dict[str, Any],
) -> None:
    key = str(stage.get("key") or "")
    if key == "validation":
        _run_validation_stage(root, execution, stage, approval=approval, summary=summary, payload=payload)
        return
    if key == "checkpoint":
        _run_checkpoint_stage(root, execution, stage, approval=approval, summary=summary, payload=payload)
        return
    if key == "apply":
        _run_apply_stage(root, execution, stage, approval=approval, summary=summary, payload=payload)
        return
    if _requires_stage_approval(execution, stage) and not approval and not payload.get("approved"):
        _wait_for_input(execution, stage, summary or f"{stage['label']} is waiting for approval.")
        return
    if key == "workspace_analysis":
        snapshot = engineering_memory(root, refresh=bool(payload.get("refresh", False)), persist=True)
        execution["workspace_memory"] = _memory_ref(snapshot)
        _complete_stage(execution, stage, summary or "Workspace intelligence memory refreshed.", {"memory": execution["workspace_memory"]})
        return
    if key == "repair":
        if _last_validation_ok(execution):
            _skip_stage(execution, stage, summary or "Repair skipped because validation passed.")
            return
        if not execution.get("validation_chain"):
            _wait_for_input(execution, stage, summary or "Repair requires a validation result first.")
            return
        if payload.get("repair_attempt"):
            _record_repair_attempt(execution, payload, summary=summary or "Repair attempt recorded.")
            _complete_stage(execution, stage, summary or "Repair checkpoint recorded.", payload)
            return
        _wait_for_input(execution, stage, summary or "Repair is waiting for a proposed repair attempt.")
        return
    if key == "approval":
        if approval or payload.get("approved"):
            _record_approval(execution, key, summary or "Approval gate completed.", payload)
            _complete_stage(execution, stage, summary or "Approval gate completed.", payload)
        else:
            _wait_for_input(execution, stage, summary or "Approval is required before checkpoint/apply.")
        return
    if key == "implementation" and not payload.get("complete"):
        _wait_for_input(execution, stage, summary or "Implementation is waiting for proposed changes or client-supplied results.")
        return
    if key == "completion_summary":
        execution["finished_at"] = execution.get("finished_at") or utc_now()
    _complete_stage(execution, stage, summary or f"{stage['label']} completed.", payload)


def _run_validation_stage(
    root: Path,
    execution: dict[str, Any],
    stage: dict[str, Any],
    *,
    approval: bool,
    summary: str | None,
    payload: dict[str, Any],
) -> None:
    if _requires_stage_approval(execution, stage) and not approval and not payload.get("approved"):
        _wait_for_input(execution, stage, summary or "Validation is waiting for approval.")
        return
    command = payload.get("command") or (execution.get("execution_plan", {}).get("validation_requirements", {}).get("primary_command"))
    should_run = bool(payload.get("run", False) or command)
    if not should_run:
        _wait_for_input(execution, stage, summary or "Validation requires a command or recorded result.")
        return
    record = editing_runtime.run_validation_operation(
        root,
        command=command if isinstance(command, list) else None,
        timeout_seconds=int(payload.get("timeout_seconds") or 120),
        dry_run=bool(payload.get("dry_run", False)),
        source_client=str(execution.get("source_client") or "aegis-core"),
        task_id=str(payload.get("task_id") or "") or None,
        repair_attempt=payload.get("repair_attempt") if isinstance(payload.get("repair_attempt"), dict) else None,
    )
    _record_validation_result(execution, {"record": record}, summary=summary or "Validation executed through Core editing runtime.")
    _complete_stage(execution, stage, summary or ("Validation passed." if record.get("validation", {}).get("ok") else "Validation failed."), {"validation_id": record.get("id")})
    if not record.get("validation", {}).get("ok"):
        repair_stage = _stage_by_key(execution, "repair")
        if repair_stage and repair_stage.get("status") in {"pending", "skipped"}:
            repair_stage["status"] = "queued"
            repair_stage["updated_at"] = utc_now()


def _run_checkpoint_stage(
    root: Path,
    execution: dict[str, Any],
    stage: dict[str, Any],
    *,
    approval: bool,
    summary: str | None,
    payload: dict[str, Any],
) -> None:
    if _requires_stage_approval(execution, stage) and not approval and not payload.get("approved"):
        _wait_for_input(execution, stage, summary or "Checkpoint creation is waiting for approval.")
        return
    paths = [str(item) for item in payload.get("paths", [])] if isinstance(payload.get("paths"), list) else []
    if not paths:
        paths = list(execution.get("execution_plan", {}).get("target_files", []))
    if not paths:
        _wait_for_input(execution, stage, summary or "Checkpoint requires target paths.")
        return
    checkpoint = editing_runtime.create_checkpoint(
        root,
        paths=paths,
        summary=summary or f"Engineering execution checkpoint for {execution.get('id')}",
        source_task_id=str(payload.get("task_id") or "") or None,
        source_client=str(execution.get("source_client") or "aegis-core"),
    )
    execution.setdefault("checkpoints", []).append(
        {
            "id": checkpoint.get("id"),
            "created_at": checkpoint.get("created_at"),
            "paths": [item.get("path") for item in checkpoint.get("files", []) if isinstance(item, dict)],
            "roadmap_item_id": execution.get("roadmap_link", {}).get("roadmap_item_id"),
        }
    )
    execution["safety"]["rollback_available"] = True
    _complete_stage(execution, stage, summary or "Checkpoint created.", {"checkpoint_id": checkpoint.get("id")})


def _run_apply_stage(
    root: Path,
    execution: dict[str, Any],
    stage: dict[str, Any],
    *,
    approval: bool,
    summary: str | None,
    payload: dict[str, Any],
) -> None:
    if _requires_stage_approval(execution, stage) and not approval and not payload.get("approved"):
        _wait_for_input(execution, stage, summary or "Apply is waiting for approval.")
        return
    changes = payload.get("changes") if isinstance(payload.get("changes"), list) else []
    proposal_id = str(payload.get("proposal_id") or "").strip() or None
    if not proposal_id and not changes:
        _wait_for_input(execution, stage, summary or "Apply requires a proposal_id or explicit changes.")
        return
    result = editing_runtime.apply_changes(
        root,
        proposal_id=proposal_id,
        changes=changes,
        change_ids=[str(item) for item in payload.get("change_ids", [])] if isinstance(payload.get("change_ids"), list) else [],
        paths=[str(item) for item in payload.get("paths", [])] if isinstance(payload.get("paths"), list) else [],
        apply_all=bool(payload.get("apply_all", True)),
        dry_run=bool(payload.get("dry_run", False)),
        summary=summary or f"Engineering execution apply for {execution.get('id')}",
        task_id=str(payload.get("task_id") or "") or None,
        source_client=str(execution.get("source_client") or "aegis-core"),
        repair_attempt=payload.get("repair_attempt") if isinstance(payload.get("repair_attempt"), dict) else None,
    )
    if result.get("checkpoint_id"):
        execution.setdefault("checkpoints", []).append({"id": result.get("checkpoint_id"), "created_at": utc_now(), "paths": result.get("applied", [])})
        execution["safety"]["rollback_available"] = True
    applied_paths = _applied_paths(result.get("applied", []))
    execution["modified_files"] = sorted(set([*execution.get("modified_files", []), *applied_paths]))
    _complete_stage(execution, stage, summary or "Applied approved changes through Core editing runtime.", {"apply_result": result})


def _record_validation_result(execution: dict[str, Any], payload: dict[str, Any], *, summary: str) -> None:
    record = payload.get("record") if isinstance(payload.get("record"), dict) else payload
    validation = record.get("validation") if isinstance(record.get("validation"), dict) else record
    ok = bool(validation.get("ok", False))
    entry = {
        "id": str(record.get("id") or f"validation-{uuid.uuid4().hex[:12]}"),
        "created_at": str(record.get("created_at") or utc_now()),
        "ok": ok,
        "command": validation.get("command"),
        "returncode": validation.get("returncode"),
        "stdout_excerpt": _excerpt(validation.get("stdout")),
        "stderr_excerpt": _excerpt(validation.get("stderr")),
        "dry_run": bool(record.get("dry_run", validation.get("dry_run", False))),
        "job_id": record.get("job_id"),
        "activity_id": record.get("activity_id"),
        "roadmap_item_id": execution.get("roadmap_link", {}).get("roadmap_item_id"),
    }
    execution.setdefault("validation_chain", []).append(entry)
    metrics = execution.setdefault("metrics", _execution_metrics_empty(_repair_limit(execution)))
    metrics["validation_runs"] = int(metrics.get("validation_runs") or 0) + 1
    metrics["validation_passes"] = int(metrics.get("validation_passes") or 0) + int(ok)
    metrics["iteration_count"] = int(metrics.get("iteration_count") or 0) + 1
    metrics["validation_success_rate"] = round(metrics["validation_passes"] / metrics["validation_runs"], 3)
    if not ok:
        execution["status"] = "repairing"
        execution.setdefault("warnings", []).append("Validation failed; repair stage is available within retry limits.")
        _ensure_repair_stage_ready(execution)
    _append_execution_log(execution, "validation.recorded", summary, {"validation_id": entry["id"], "ok": ok})


def _record_repair_attempt(execution: dict[str, Any], payload: dict[str, Any], *, summary: str) -> None:
    limit = _repair_limit(execution)
    attempts = execution.get("repair_history", []) if isinstance(execution.get("repair_history"), list) else []
    if len(attempts) >= limit:
        execution.setdefault("warnings", []).append("Repair attempt limit reached; execution requires user approval before more repair.")
        execution["status"] = "waiting_input"
        _append_execution_log(execution, "repair.limit_reached", "Repair attempt limit reached.", {"limit": limit})
        return
    repair_payload = payload.get("repair_attempt") if isinstance(payload.get("repair_attempt"), dict) else payload
    entry = {
        "id": str(repair_payload.get("id") or f"repair-{uuid.uuid4().hex[:12]}"),
        "created_at": utc_now(),
        "attempt": len(attempts) + 1,
        "status": str(repair_payload.get("status") or "recorded"),
        "summary": scrub(str(repair_payload.get("summary") or summary)),
        "target_files": [str(item) for item in repair_payload.get("target_files", [])] if isinstance(repair_payload.get("target_files"), list) else [],
        "validation_id": repair_payload.get("validation_id") or (_last_validation(execution) or {}).get("id"),
        "model": repair_payload.get("model") or repair_payload.get("model_id"),
        "checkpoint_id": repair_payload.get("checkpoint_id"),
        "warnings": [scrub(str(item)) for item in repair_payload.get("warnings", [])] if isinstance(repair_payload.get("warnings"), list) else [],
    }
    execution.setdefault("repair_history", []).append(entry)
    metrics = execution.setdefault("metrics", _execution_metrics_empty(limit))
    metrics["repair_attempts"] = int(metrics.get("repair_attempts") or 0) + 1
    if entry["status"] in {"completed", "successful", "success"}:
        metrics["repair_successes"] = int(metrics.get("repair_successes") or 0) + 1
    metrics["repair_success_rate"] = round(metrics["repair_successes"] / metrics["repair_attempts"], 3) if metrics["repair_attempts"] else None
    _append_execution_log(execution, "repair.recorded", summary, entry)


def _record_approval(execution: dict[str, Any], stage_key: str | None, summary: str, payload: dict[str, Any]) -> None:
    entry = {
        "id": f"approval-{uuid.uuid4().hex[:12]}",
        "stage_key": stage_key or execution.get("active_stage_key"),
        "created_at": utc_now(),
        "summary": scrub(summary),
        "approved_by": scrub(str(payload.get("approved_by") or payload.get("client_id") or execution.get("source_client") or "unknown")),
        "payload": _safe_metadata(payload),
    }
    execution.setdefault("approvals", []).append(entry)
    stage = _stage_by_key(execution, entry["stage_key"])
    if stage and stage.get("status") == "waiting_input":
        stage["status"] = "queued"
        stage["updated_at"] = utc_now()
    _append_execution_log(execution, "approval.recorded", summary, entry)


def _record_rollback(execution: dict[str, Any], payload: dict[str, Any], *, summary: str) -> None:
    entry = {
        "id": f"rollback-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "checkpoint_id": payload.get("checkpoint_id") or payload.get("checkpoint"),
        "summary": scrub(summary),
        "restored_files": [str(item) for item in payload.get("restored_files", [])] if isinstance(payload.get("restored_files"), list) else [],
        "payload": _safe_metadata(payload),
    }
    execution.setdefault("rollbacks", []).append(entry)
    metrics = execution.setdefault("metrics", _execution_metrics_empty(_repair_limit(execution)))
    metrics["rollback_count"] = int(metrics.get("rollback_count") or 0) + 1
    _append_execution_log(execution, "rollback.recorded", summary, entry)


def _complete_stage(execution: dict[str, Any], stage: dict[str, Any], summary: str, payload: dict[str, Any]) -> None:
    stage["status"] = "completed"
    stage["progress"] = 100
    stage["updated_at"] = utc_now()
    stage["started_at"] = stage.get("started_at") or utc_now()
    stage["finished_at"] = utc_now()
    stage.setdefault("logs", []).append({"event": "completed", "summary": scrub(summary), "created_at": utc_now(), "payload": _safe_metadata(payload)})
    _append_execution_log(execution, f"stage.{stage.get('key')}.completed", summary, payload)


def _skip_stage(execution: dict[str, Any], stage: dict[str, Any], summary: str) -> None:
    stage["status"] = "skipped"
    stage["progress"] = 100
    stage["updated_at"] = utc_now()
    stage["finished_at"] = utc_now()
    stage.setdefault("logs", []).append({"event": "skipped", "summary": scrub(summary), "created_at": utc_now(), "payload": {}})
    _append_execution_log(execution, f"stage.{stage.get('key')}.skipped", summary)


def _fail_stage(execution: dict[str, Any], stage: dict[str, Any], summary: str, payload: dict[str, Any]) -> None:
    stage["status"] = "failed"
    stage["error"] = scrub(summary)
    stage["updated_at"] = utc_now()
    stage["finished_at"] = utc_now()
    execution.setdefault("errors", []).append({"stage_key": stage.get("key"), "summary": scrub(summary), "created_at": utc_now()})
    _append_execution_log(execution, f"stage.{stage.get('key')}.failed", summary, payload)


def _wait_for_input(execution: dict[str, Any], stage: dict[str, Any], summary: str) -> None:
    stage["status"] = "waiting_input"
    stage["updated_at"] = utc_now()
    stage.setdefault("logs", []).append({"event": "waiting_input", "summary": scrub(summary), "created_at": utc_now(), "payload": {}})
    _append_execution_log(execution, f"stage.{stage.get('key')}.waiting_input", summary)


def _cancel_execution(execution: dict[str, Any], summary: str) -> None:
    for stage in execution.get("stages", []):
        if isinstance(stage, dict) and stage.get("status") not in {"completed", "failed", "cancelled", "skipped"}:
            stage["status"] = "cancelled"
            stage["updated_at"] = utc_now()
    execution["status"] = "cancelled"
    execution["finished_at"] = execution.get("finished_at") or utc_now()
    _append_execution_log(execution, "execution.cancelled", summary)


def _refresh_execution_state(execution: dict[str, Any]) -> None:
    stages = [stage for stage in execution.get("stages", []) if isinstance(stage, dict)]
    by_key = {stage.get("key"): stage for stage in stages}
    for stage in stages:
        deps = [str(item) for item in stage.get("depends_on", []) if str(item).strip()]
        if stage.get("status") == "pending" and all(by_key.get(dep, {}).get("status") in {"completed", "skipped"} for dep in deps):
            stage["status"] = "queued"
            stage["updated_at"] = utc_now()
    completed = sum(1 for stage in stages if stage.get("status") in {"completed", "skipped"})
    total = len(stages) or 1
    execution["progress"] = int((completed / total) * 100)
    active = None
    for state in ("running", "validating", "repairing", "waiting_input", "queued"):
        active = next((stage for stage in stages if stage.get("status") == state), None)
        if active:
            break
    execution["active_stage_key"] = active.get("key") if active else None
    if execution.get("status") not in {"paused", "cancelled", "failed", "completed"}:
        if all(stage.get("status") in {"completed", "skipped"} for stage in stages):
            execution["status"] = "completed"
            execution["finished_at"] = execution.get("finished_at") or utc_now()
        elif any(stage.get("status") == "failed" for stage in stages):
            execution["status"] = "failed"
            execution["finished_at"] = execution.get("finished_at") or utc_now()
        elif any(stage.get("status") == "repairing" for stage in stages) or execution.get("status") == "repairing":
            execution["status"] = "repairing"
        elif any(stage.get("status") == "validating" for stage in stages):
            execution["status"] = "validating"
        elif any(stage.get("status") == "waiting_input" for stage in stages):
            execution["status"] = "waiting_input"
        elif any(stage.get("status") == "running" for stage in stages):
            execution["status"] = "running"
        else:
            execution["status"] = "queued"
    execution["updated_at"] = utc_now()
    execution.setdefault("execution_plan", {}).setdefault("progress_tracking", {})["active_stage"] = execution.get("active_stage_key")
    execution["execution_plan"]["progress_tracking"]["completed_stage_count"] = completed
    execution["metrics"] = _refresh_plan_metrics(execution)


def _initial_stages(mode: str, now: str) -> list[dict[str, Any]]:
    active = "validation" if mode in {"autonomous_validate_only", "repair_only"} else "implementation"
    skipped = set()
    if mode == "autonomous_validate_only":
        skipped.update({"implementation", "review", "approval", "checkpoint", "apply"})
    if mode == "repair_only":
        skipped.add("implementation")
    stages: list[dict[str, Any]] = []
    previous_key: str | None = None
    for order, (key, label) in enumerate(PIPELINE_STAGES, start=1):
        if key in PREP_STAGES:
            status = "completed"
            progress = 100
            started_at = now
            finished_at = now
        elif key in skipped:
            status = "skipped"
            progress = 100
            started_at = None
            finished_at = now
        elif key == active:
            status = "queued"
            progress = 0
            started_at = None
            finished_at = None
        else:
            status = "pending"
            progress = 0
            started_at = None
            finished_at = None
        stage = {
            "id": f"stage-{uuid.uuid4().hex[:10]}",
            "key": key,
            "label": label,
            "status": status,
            "order": order,
            "progress": progress,
            "depends_on": [previous_key] if previous_key else [],
            "approval_required": _stage_approval_required(mode, key),
            "created_at": now,
            "updated_at": now,
            "started_at": started_at,
            "finished_at": finished_at,
            "logs": [],
            "result": {},
            "error": None,
        }
        stages.append(stage)
        previous_key = key
    return stages


def _decompose_subtasks(
    execution_id: str,
    stages: list[dict[str, Any]],
    targets: list[str],
    validation_requirements: dict[str, Any],
    now: str,
) -> list[dict[str, Any]]:
    subtasks: list[dict[str, Any]] = []
    previous_id: str | None = None
    for stage in stages:
        key = str(stage.get("key"))
        title = _subtask_title(key, targets, validation_requirements)
        subtask = {
            "id": f"eng-task-{uuid.uuid4().hex[:12]}",
            "execution_id": execution_id,
            "stage_key": key,
            "title": title,
            "status": stage.get("status"),
            "order": stage.get("order"),
            "parent_id": previous_id,
            "depends_on": [previous_id] if previous_id else [],
            "agent_role": _agent_role_for_stage(key),
            "validation_checkpoint": key == "validation",
            "repair_checkpoint": key == "repair",
            "target_files": targets if key in MUTATING_STAGES or key in {"review", "repair"} else [],
            "created_at": now,
            "updated_at": now,
        }
        subtasks.append(subtask)
        previous_id = subtask["id"]
    return subtasks


def _subtask_title(stage_key: str, targets: list[str], validation_requirements: dict[str, Any]) -> str:
    if stage_key == "implementation":
        return f"Prepare proposed changes for {len(targets)} target file(s)" if targets else "Prepare proposed changes"
    if stage_key == "validation":
        command = validation_requirements.get("primary_command")
        return f"Run validation checkpoint: {' '.join(command)}" if isinstance(command, list) else "Run validation checkpoint"
    if stage_key == "repair":
        return "Record bounded targeted repair attempt if validation fails"
    if stage_key == "checkpoint":
        return "Create rollback checkpoint before apply"
    if stage_key == "apply":
        return "Apply approved Core change proposal"
    return f"{stage_key.replace('_', ' ').title()} stage"


def _agent_role_for_stage(stage_key: str) -> str:
    if stage_key in {"intake", "planning", "task_decomposition", "approval"}:
        return "planner"
    if stage_key in {"implementation", "checkpoint", "apply"}:
        return "coder"
    if stage_key == "validation":
        return "validator"
    if stage_key == "repair":
        return "repair_agent"
    return "summarizer"


def _execution_graph(stages: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": stage["key"], "label": stage["label"], "status": stage["status"]} for stage in stages]
    edges = []
    for stage in stages:
        for dep in stage.get("depends_on", []):
            edges.append({"from": dep, "to": stage["key"]})
    return {"nodes": nodes, "edges": edges}


def _task_dependency_graph(subtasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nodes": [{"id": task["id"], "label": task["title"], "stage_key": task["stage_key"], "status": task["status"]} for task in subtasks],
        "edges": [
            {"from": dep, "to": task["id"]}
            for task in subtasks
            for dep in task.get("depends_on", [])
            if dep
        ],
    }


def _dependency_edges(subtasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"from": dep, "to": task["id"]}
        for task in subtasks
        for dep in task.get("depends_on", [])
        if dep
    ]


def _implementation_phases(targets: list[str], goal: str) -> list[dict[str, Any]]:
    if targets:
        return [
            {
                "id": f"phase-{index}",
                "title": f"Modify {path}",
                "status": "pending",
                "target_files": [path],
                "goal": goal,
            }
            for index, path in enumerate(targets, start=1)
        ]
    return [{"id": "phase-1", "title": "Prepare proposed implementation", "status": "pending", "target_files": [], "goal": goal}]


def _validation_checkpoints(requirements: dict[str, Any]) -> list[dict[str, Any]]:
    commands = requirements.get("commands") if isinstance(requirements.get("commands"), list) else []
    if not commands:
        return [{"id": "validation-1", "status": "pending", "command": None, "required": True, "reason": "No validation command detected yet."}]
    return [
        {
            "id": f"validation-{index}",
            "status": "pending",
            "command": item.get("command") if isinstance(item, dict) else item,
            "required": index == 1,
            "reason": item.get("reason", "") if isinstance(item, dict) else "",
        }
        for index, item in enumerate(commands, start=1)
    ]


def _repair_checkpoints(limit: int) -> list[dict[str, Any]]:
    return [
        {
            "id": f"repair-{index}",
            "status": "available",
            "attempt": index,
            "requires_validation_failure": True,
        }
        for index in range(1, max(0, limit) + 1)
    ]


def _approval_requirements(mode: str, explicit: list[str], validation_requirements: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        {"stage": "implementation", "required": mode == "approval_every_step", "reason": "Client must approve generated plan before file proposals are considered."},
        {"stage": "validation", "required": _stage_approval_required(mode, "validation"), "reason": "Commands run locally and must remain inspectable."},
        {"stage": "checkpoint", "required": True, "reason": "Checkpoint is mandatory before apply."},
        {"stage": "apply", "required": True, "reason": "File mutation requires explicit approval and a rollback path."},
    ]
    for value in explicit:
        text = scrub(str(value)).strip()
        if text:
            items.append({"stage": "custom", "required": True, "reason": text})
    if not validation_requirements.get("commands"):
        items.append({"stage": "validation", "required": True, "reason": "No validation command is detected; user confirmation is required."})
    return items


def _safety_controls(mode: str, max_files: int, repair_limit: int) -> dict[str, Any]:
    return {
        "mode": mode,
        "checkpoint_required_before_apply": True,
        "max_file_modifications": max_files,
        "restricted_directories": DEFAULT_RESTRICTED_DIRS,
        "binary_file_protection": True,
        "diff_preview_required": True,
        "rollback_available": False,
        "max_repair_attempts": repair_limit,
        "max_autonomous_iterations": 1 if mode == "autonomous_validate_only" else max(1, repair_limit + 1),
        "operation_audit_history": AUDIT_FILE,
        "validation_required_before_apply": mode != "repair_only",
    }


def _rollback_strategy(targets: list[str]) -> dict[str, Any]:
    return {
        "checkpoint_before_apply": True,
        "restore_endpoint": "/v1/checkpoints/restore",
        "target_files": targets,
        "backup_scope": "target_files" if targets else "proposal_files",
        "notes": [
            "Apply must use Core editing runtime so checkpoint creation is automatic.",
            "Checkpoint restore creates a pre-restore checkpoint before mutating files.",
        ],
    }


def _roadmap_link(roadmap_item_id: str | None, roadmap_phase_id: str | None, mode: str) -> dict[str, Any]:
    if mode != "roadmap_execution" and not roadmap_item_id and not roadmap_phase_id:
        return {}
    return {
        "roadmap_item_id": roadmap_item_id or "",
        "roadmap_phase_id": roadmap_phase_id or "",
        "state": "in_progress",
        "checkpoint_ids": [],
        "validation_ids": [],
    }


def _validation_requirements(root: Path, validation_command: list[str] | None) -> dict[str, Any]:
    detected = [{"name": item.name, "command": item.command, "reason": item.reason} for item in detect_validation_commands(root)]
    primary = validation_command or (detected[0]["command"] if detected else None)
    commands = [{"name": "requested", "command": validation_command, "reason": "Requested by client"}] if validation_command else detected
    return {
        "primary_command": primary,
        "commands": commands,
        "requires_success_before_apply": True,
        "capture_stdout_stderr": True,
        "store_results": True,
    }


def _knowledge_impacts(root: Path, targets: list[str]) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    for target in targets[:20]:
        try:
            impact = impact_analysis(root, target, limit=50)
        except Exception:
            continue
        impacts.append(
            {
                "target": target,
                "affected_files": impact.get("affected_files", [])[:25],
                "likely_breakage_areas": impact.get("likely_breakage_areas", [])[:10],
                "modification_risk": impact.get("modification_risk", {}),
                "validation_targets": impact.get("validation_targets", [])[:10],
                "related_workflows": impact.get("related_workflows", [])[:10],
            }
        )
    return impacts


def _architecture_summary(intelligence: dict[str, Any]) -> dict[str, Any]:
    metadata = intelligence.get("metadata") if isinstance(intelligence.get("metadata"), dict) else {}
    health = intelligence.get("health") if isinstance(intelligence.get("health"), dict) else {}
    return {
        "workspace_name": metadata.get("workspace_name", ""),
        "languages": intelligence.get("languages", {}),
        "frameworks": intelligence.get("frameworks", []),
        "entry_points": metadata.get("entry_points", []),
        "build_files": metadata.get("build_files", []),
        "health_grade": health.get("grade", ""),
        "health_score": health.get("score", 0),
    }


def _coding_conventions(root: Path, intelligence: dict[str, Any]) -> list[dict[str, Any]]:
    conventions: list[dict[str, Any]] = []
    languages = intelligence.get("languages") if isinstance(intelligence.get("languages"), dict) else {}
    build_files = {str(item).lower() for item in intelligence.get("file_index", {}).get("build_files", [])} if isinstance(intelligence.get("file_index"), dict) else set()
    if "python" in {key.lower() for key in languages} or (root / "pyproject.toml").is_file():
        conventions.append({"scope": "python", "summary": "Prefer module tests via python -m pytest when available."})
    if any(item.endswith("package.json") for item in build_files) or (root / "package.json").is_file():
        conventions.append({"scope": "javascript", "summary": "Use package scripts for build/test/lint validation when detected."})
    if any(item.endswith((".sln", ".csproj", ".fsproj", ".vbproj")) for item in build_files):
        conventions.append({"scope": "dotnet", "summary": "Use solution/project aware validation and preserve startup project context."})
    if not conventions:
        conventions.append({"scope": "general", "summary": "Keep edits small, checkpointed, validated, and documented in .aegis memory."})
    return conventions


def _framework_usage(intelligence: dict[str, Any]) -> list[dict[str, Any]]:
    frameworks = intelligence.get("frameworks") if isinstance(intelligence.get("frameworks"), list) else []
    return [{"name": str(item), "usage": "detected"} for item in frameworks]


def _risk_areas(health: dict[str, Any]) -> list[dict[str, Any]]:
    risks = health.get("top_risks") if isinstance(health.get("top_risks"), list) else []
    warnings = health.get("warnings") if isinstance(health.get("warnings"), list) else []
    out = [{"kind": "health_risk", "summary": scrub(str(item))} for item in risks[:10]]
    out.extend({"kind": "warning", "summary": scrub(str(item))} for item in warnings[:10])
    return out


def _render_memory_markdown(memory: dict[str, Any]) -> str:
    architecture = memory.get("architecture_summary", {})
    lines = [
        "## Architecture",
        "",
        f"- Workspace: {architecture.get('workspace_name') or Path(str(memory.get('workspace') or '.')).name}",
        f"- Frameworks: {', '.join(str(item) for item in architecture.get('frameworks', []) or []) or 'none detected'}",
        f"- Entry points: {', '.join(str(item) for item in architecture.get('entry_points', []) or []) or 'none detected'}",
        "",
        "## Safety Notes",
        "",
        "- File mutation must go through Core editing contracts.",
        "- Checkpoints are required before apply.",
        "- Validation and repair loops are bounded and journaled.",
    ]
    return "\n".join(lines)


def _normalize_target_files(root: Path, paths: list[str]) -> list[str]:
    if len(paths) > MAX_TARGET_FILES:
        raise ValueError(f"target_files exceeds maximum of {MAX_TARGET_FILES}")
    out: list[str] = []
    for value in paths:
        relative = _normalize_relative_path(str(value))
        target = _safe_target(root, relative)
        if target.exists() and target.is_file() and _is_binary_file(target):
            raise ValueError(f"{relative}: binary files are protected")
        if relative not in out:
            out.append(relative)
    return out


def _normalize_context_files(root: Path, paths: list[str]) -> list[str]:
    out: list[str] = []
    for value in paths:
        try:
            relative = _normalize_relative_path(str(value))
            target = _safe_target(root, relative, must_be_editable=False)
        except ValueError:
            continue
        if target.exists() and target.is_file() and relative not in out:
            out.append(relative)
    return out


def _normalize_relative_path(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    if not raw:
        raise ValueError("path is empty")
    candidate = Path(raw)
    first = PurePosixPath(raw).parts[0] if PurePosixPath(raw).parts else ""
    if candidate.is_absolute() or raw.startswith("/") or ":" in first:
        raise ValueError("path must be relative to the workspace")
    path = PurePosixPath(raw)
    if str(path) in {".", ".."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must not contain dot segments")
    if any(part.startswith(".") for part in path.parts[:-1]):
        raise ValueError("path points into a hidden directory")
    return path.as_posix()


def _safe_target(root: Path, relative_path: str, *, must_be_editable: bool = True) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("path points outside the workspace") from exc
    if target == root:
        raise ValueError("path must point to a file inside the workspace")
    if is_ignored_path(target, root):
        raise ValueError("path points into an ignored generated or dependency folder")
    if is_secret_like(target):
        raise ValueError("path points to a secret-like file")
    if must_be_editable and not is_safe_to_edit(target, root):
        raise ValueError("path is not safe to edit")
    return target


def _is_binary_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" in chunk


def _estimate_risk(goal: str, targets: list[str], memory: dict[str, Any], max_files: int) -> dict[str, Any]:
    lowered = goal.lower()
    reasons: list[str] = []
    score = 0.2
    if any(term in lowered for term in ("auth", "security", "database", "migration", "dependency", "upgrade", "delete", "release")):
        score += 0.35
        reasons.append("Goal mentions high-risk engineering surface.")
    if targets:
        score += min(0.25, len(targets) / max(1, max_files) * 0.25)
        reasons.append(f"{len(targets)} target file(s) supplied.")
    if memory.get("risk_areas"):
        score += 0.15
        reasons.append("Workspace memory includes risk areas.")
    score = max(0.0, min(1.0, score))
    level = "low" if score < 0.35 else "medium" if score < 0.7 else "high"
    return {"level": level, "score": round(score, 3), "reasons": reasons or ["No elevated risk signals detected."]}


def _normalize_mode(mode: str) -> str:
    value = str(mode or "safe_assisted").strip().lower().replace("-", "_").replace(" ", "_")
    if value not in EXECUTION_MODES:
        raise ValueError(f"unsupported engineering execution mode: {mode}")
    return value


def _normalize_action(action: str) -> str:
    value = str(action or "advance").strip().lower().replace("-", "_").replace(" ", "_")
    allowed = {
        "advance",
        "pause",
        "resume",
        "cancel",
        "record_log",
        "approve",
        "record_validation",
        "record_repair",
        "record_rollback",
        "complete_stage",
        "fail_stage",
        "run_validation",
        "apply",
    }
    if value not in allowed:
        raise ValueError(f"unsupported engineering execution action: {action}")
    return value


def _workflow_type_for_mode(mode: str, goal: str) -> str:
    lowered = goal.lower()
    if mode == "roadmap_execution":
        return "continue_roadmap"
    if mode == "repair_only" or any(term in lowered for term in ("repair", "fix build", "fix test")):
        return "repair_project"
    if mode == "autonomous_validate_only" or any(term in lowered for term in ("validate", "test", "build")):
        return "validate_project"
    return "generate_feature"


def _mode_repair_limit(mode: str, requested: int | None) -> int:
    if requested is not None:
        return max(0, min(10, int(requested)))
    if mode == "autonomous_validate_only":
        return 0
    if mode == "repair_only":
        return 3
    return 2


def _stage_approval_required(mode: str, stage_key: str) -> bool:
    if mode == "approval_every_step":
        return True
    if stage_key in {"approval", "checkpoint", "apply"}:
        return True
    if stage_key == "validation":
        return mode not in {"autonomous_validate_only", "semi_autonomous"}
    if stage_key == "implementation":
        return mode in {"safe_assisted", "roadmap_execution", "repair_only"}
    return False


def _requires_stage_approval(execution: dict[str, Any], stage: dict[str, Any]) -> bool:
    return bool(stage.get("approval_required"))


def _first_active_stage(stages: list[dict[str, Any]]) -> str | None:
    for status in ("running", "validating", "repairing", "waiting_input", "queued"):
        for stage in stages:
            if stage.get("status") == status:
                return str(stage.get("key"))
    return None


def _select_stage(execution: dict[str, Any], stage_key: str | None) -> dict[str, Any]:
    if stage_key:
        stage = _stage_by_key(execution, stage_key)
        if stage is None:
            raise ValueError(f"stage not found: {stage_key}")
        return stage
    active_key = execution.get("active_stage_key")
    if active_key:
        stage = _stage_by_key(execution, str(active_key))
        if stage is not None:
            return stage
    raise ValueError("no active engineering execution stage is available")


def _stage_by_key(execution: dict[str, Any], key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    for stage in execution.get("stages", []):
        if isinstance(stage, dict) and stage.get("key") == key:
            return stage
    return None


def _last_validation(execution: dict[str, Any]) -> dict[str, Any] | None:
    chain = execution.get("validation_chain", [])
    if isinstance(chain, list) and chain:
        last = chain[-1]
        return last if isinstance(last, dict) else None
    return None


def _last_validation_ok(execution: dict[str, Any]) -> bool:
    last = _last_validation(execution)
    return bool(last and last.get("ok"))


def _ensure_repair_stage_ready(execution: dict[str, Any]) -> None:
    stage = _stage_by_key(execution, "repair")
    if stage and stage.get("status") in {"pending", "skipped"}:
        stage["status"] = "queued"
        stage["updated_at"] = utc_now()


def _repair_limit(execution: dict[str, Any]) -> int:
    return int(execution.get("safety", {}).get("max_repair_attempts") or 0)


def _refresh_plan_metrics(execution: dict[str, Any]) -> dict[str, Any]:
    existing = execution.get("metrics") if isinstance(execution.get("metrics"), dict) else {}
    validation_runs = len(execution.get("validation_chain", [])) if isinstance(execution.get("validation_chain"), list) else 0
    validation_passes = sum(1 for item in execution.get("validation_chain", []) if isinstance(item, dict) and item.get("ok"))
    repair_attempts = len(execution.get("repair_history", [])) if isinstance(execution.get("repair_history"), list) else 0
    repair_successes = sum(
        1
        for item in execution.get("repair_history", [])
        if isinstance(item, dict) and item.get("status") in {"completed", "successful", "success"}
    )
    duration = _duration_seconds(execution.get("started_at"), execution.get("finished_at") or execution.get("updated_at"))
    return {
        **existing,
        "duration_seconds": duration,
        "validation_runs": validation_runs,
        "validation_passes": validation_passes,
        "validation_success_rate": round(validation_passes / validation_runs, 3) if validation_runs else None,
        "repair_attempts": repair_attempts,
        "repair_successes": repair_successes,
        "repair_success_rate": round(repair_successes / repair_attempts, 3) if repair_attempts else None,
        "files_modified_count": len(set(str(item) for item in execution.get("modified_files", []) if str(item).strip())),
        "rollback_count": len(execution.get("rollbacks", [])) if isinstance(execution.get("rollbacks"), list) else 0,
        "iteration_count": max(int(existing.get("iteration_count") or 0), validation_runs + repair_attempts),
        "journal_entry_count": len(execution.get("journal", [])) if isinstance(execution.get("journal"), list) else 0,
    }


def _execution_metrics_empty(repair_limit: int) -> dict[str, Any]:
    return {
        "duration_seconds": None,
        "validation_runs": 0,
        "validation_passes": 0,
        "validation_success_rate": None,
        "repair_attempts": 0,
        "repair_successes": 0,
        "repair_success_rate": None,
        "iteration_count": 0,
        "max_repair_attempts": repair_limit,
        "files_modified_count": 0,
        "rollback_count": 0,
        "journal_entry_count": 0,
    }


def _model_efficiency(model_usage: dict[str, int], validation_passes: int, validation_runs: int) -> dict[str, Any]:
    total_model_uses = sum(model_usage.values())
    return {
        "model_call_count": total_model_uses,
        "validation_passes_per_model_call": round(validation_passes / total_model_uses, 3) if total_model_uses else None,
        "validation_success_rate": round(validation_passes / validation_runs, 3) if validation_runs else None,
    }


def _applied_paths(applied: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(applied, list):
        return paths
    for item in applied:
        text = str(item)
        if ":" in text:
            paths.append(text.split(":", 1)[1].strip())
    return paths


def _memory_ref(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": snapshot.get("generated_at"),
        "project_id": snapshot.get("project_id"),
        "architecture_summary": snapshot.get("architecture_summary", {}),
        "risk_area_count": len(snapshot.get("risk_areas", []) if isinstance(snapshot.get("risk_areas"), list) else []),
        "validation_command_count": len(snapshot.get("validation_commands", []) if isinstance(snapshot.get("validation_commands"), list) else []),
        "memory_file": MEMORY_FILE,
    }


def _append_execution_log(execution: dict[str, Any], event: str, summary: str, payload: dict[str, Any] | None = None) -> None:
    entry = {
        "id": f"log-{uuid.uuid4().hex[:10]}",
        "event": scrub(event),
        "summary": scrub(summary),
        "created_at": utc_now(),
        "payload": _safe_metadata(payload or {}),
    }
    logs = execution.setdefault("logs", [])
    logs.append(entry)
    execution["logs"] = logs[-MAX_LOGS_PER_EXECUTION:]
    journal = execution.setdefault("journal", [])
    journal.append(entry)
    execution["journal"] = journal[-MAX_JOURNAL_ENTRIES:]


def _record_event(memory: ProjectMemory, execution: dict[str, Any], event: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": f"event-{uuid.uuid4().hex[:12]}",
        "project_id": execution.get("project_id") or _project_id(Path(str(execution.get("workspace") or memory.workspace))),
        "workspace": execution.get("workspace") or str(memory.workspace),
        "execution_id": execution.get("id"),
        "workflow_id": execution.get("workflow_id"),
        "mode": execution.get("mode"),
        "event": scrub(event),
        "summary": scrub(summary),
        "created_at": utc_now(),
        "payload": _safe_metadata(payload),
    }
    events = _load_events(memory)
    events.append(entry)
    events = sorted(events, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:MAX_EVENTS]
    _write_json(memory, EVENTS_FILE, events)
    _append_audit(memory, execution, event, summary)
    return entry


def _append_global_journal(memory: ProjectMemory, execution: dict[str, Any], event: dict[str, Any]) -> None:
    journal = _read_json(memory, JOURNAL_FILE, [])
    if not isinstance(journal, list):
        journal = []
    journal.append(
        {
            "id": f"journal-{uuid.uuid4().hex[:12]}",
            "execution_id": execution.get("id"),
            "workflow_id": execution.get("workflow_id"),
            "event_id": event.get("id"),
            "event": event.get("event"),
            "summary": event.get("summary"),
            "created_at": utc_now(),
            "prompts_used": event.get("payload", {}).get("prompts_used", []),
            "models_used": event.get("payload", {}).get("models_used", []),
            "files_modified": execution.get("modified_files", []),
            "validation_outcomes": execution.get("validation_chain", []),
            "repair_attempts": execution.get("repair_history", []),
            "approvals": execution.get("approvals", []),
            "rollbacks": execution.get("rollbacks", []),
            "warnings": execution.get("warnings", []),
            "errors": execution.get("errors", []),
        }
    )
    journal = sorted(journal, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:MAX_JOURNAL_ENTRIES]
    _write_json(memory, JOURNAL_FILE, journal)


def _append_audit(memory: ProjectMemory, execution: dict[str, Any], event: str, detail: str) -> None:
    line = f"- `{utc_now()}` **{scrub(event)}** execution={execution.get('id')} status={execution.get('status')}"
    if detail:
        line += f"\n  {scrub(detail).replace(chr(10), chr(10) + '  ')}"
    path = memory.root / AUDIT_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _execution_timeline(memory: ProjectMemory, execution_id: str) -> list[dict[str, Any]]:
    return [event for event in _load_events(memory) if event.get("execution_id") == execution_id][:200]


def _load_events(memory: ProjectMemory) -> list[dict[str, Any]]:
    events = _read_json(memory, EVENTS_FILE, [])
    return [item for item in events if isinstance(item, dict)] if isinstance(events, list) else []


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {root}")
    return root


def _memory(root: Path) -> ProjectMemory:
    memory = ProjectMemory(root)
    try:
        memory.root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EngineeringExecutionPersistenceError(f"Could not create engineering execution state directory at {memory.root}: {exc}") from exc
    return memory


def _load_executions(memory: ProjectMemory) -> list[dict[str, Any]]:
    payload = _read_json(memory, EXECUTIONS_FILE, [])
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _write_executions(memory: ProjectMemory, executions: list[dict[str, Any]]) -> None:
    executions = sorted(executions, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:MAX_EXECUTIONS]
    _write_json(memory, EXECUTIONS_FILE, executions)


def _get_execution(memory: ProjectMemory, execution_id: str) -> dict[str, Any]:
    for execution in _load_executions(memory):
        if execution.get("id") == execution_id:
            return execution
    raise EngineeringExecutionNotFoundError(execution_id)


def _persist_execution(memory: ProjectMemory, execution: dict[str, Any]) -> None:
    executions = _load_executions(memory)
    executions = [item for item in executions if item.get("id") != execution.get("id")]
    executions.append(execution)
    _write_executions(memory, executions)


def _read_json(memory: ProjectMemory, name: str, default: Any) -> Any:
    path = memory.root / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(memory: ProjectMemory, name: str, data: Any) -> None:
    path = memory.root / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise EngineeringExecutionPersistenceError(f"Could not persist engineering execution state at {path}: {exc}") from exc


def _safe_metadata(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {scrub(str(key)): _safe_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return scrub(str(value)) if isinstance(value, str) else value
    return scrub(str(value))


def _excerpt(value: Any, limit: int = 4000) -> str:
    text = scrub(str(value or ""))
    return text if len(text) <= limit else text[-limit:]


def _duration_seconds(start: Any, end: Any) -> float | None:
    if not start or not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max(0.0, (end_dt - start_dt).total_seconds()), 3)


def _project_id(root: Path) -> str:
    digest = hashlib.sha1(str(root).lower().encode("utf-8")).hexdigest()[:12]
    return f"project-{digest}"
