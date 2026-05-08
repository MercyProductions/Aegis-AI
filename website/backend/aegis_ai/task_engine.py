from __future__ import annotations

from dataclasses import dataclass


TASK_STATUSES = {
    "queued",
    "planning",
    "running",
    "blocked",
    "needs_approval",
    "validating",
    "repairing",
    "completed",
    "failed",
    "canceled",
}

TERMINAL_TASK_STATUSES = {"completed", "failed", "canceled"}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"planning", "running", "blocked", "needs_approval", "completed", "failed", "canceled"},
    "planning": {"running", "blocked", "needs_approval", "failed", "canceled"},
    "running": {"needs_approval", "validating", "repairing", "completed", "failed", "canceled"},
    "blocked": {"planning", "running", "needs_approval", "failed", "canceled"},
    "needs_approval": {"running", "blocked", "canceled"},
    "validating": {"repairing", "completed", "failed", "canceled"},
    "repairing": {"validating", "running", "failed", "canceled"},
    "completed": {"queued"},
    "failed": {"queued", "repairing", "canceled"},
    "canceled": {"queued"},
}

LEGACY_STATUS_MAP = {
    "error": "failed",
    "completed_with_validation_failure": "failed",
}


@dataclass(frozen=True)
class SubtaskSpec:
    title: str
    user_goal: str
    assigned_agent_role: str


DEFAULT_SUBTASKS: tuple[SubtaskSpec, ...] = (
    SubtaskSpec("Inspect project", "Inspect project files, metadata, memory, and readiness.", "architect"),
    SubtaskSpec("Plan changes", "Build an execution plan and select a model route.", "planner"),
    SubtaskSpec("Edit files", "Prepare or apply generated file changes safely.", "code"),
    SubtaskSpec("Review changes", "Check generated changes for fit, risk, and obvious defects.", "review"),
    SubtaskSpec("Run validation", "Run saved or inferred validation commands.", "validation"),
    SubtaskSpec("Repair failures", "Attempt focused repairs when validation fails.", "repair"),
    SubtaskSpec("Update memory", "Record durable project decisions, recurring errors, and intelligence updates.", "memory"),
    SubtaskSpec("Summarize outcome", "Record the final outcome and next safe action.", "memory"),
)


def normalize_task_status(status: str) -> str:
    normalized = (status or "queued").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized.startswith("completed_with_verification_"):
        return "completed" if normalized.endswith("passed") else "failed"
    return LEGACY_STATUS_MAP.get(normalized, normalized if normalized in TASK_STATUSES else "failed")


def can_transition_task(current: str, target: str) -> bool:
    current_status = normalize_task_status(current)
    target_status = normalize_task_status(target)
    if current_status == target_status:
        return True
    return target_status in TASK_TRANSITIONS.get(current_status, set())


def validate_task_transition(current: str, target: str) -> str:
    target_status = normalize_task_status(target)
    if not can_transition_task(current, target_status):
        raise ValueError(f"invalid task state transition: {current} -> {target_status}")
    return target_status
