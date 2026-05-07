from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .schemas import ToolEvent
from .storage import EventStore


AgentRole = Literal["planner", "architect", "code", "review", "validation", "repair", "memory"]

AGENT_CHAIN: tuple[AgentRole, ...] = (
    "planner",
    "architect",
    "code",
    "review",
    "validation",
    "repair",
    "memory",
)

ROLE_LABELS: dict[AgentRole, str] = {
    "planner": "Planner Agent",
    "architect": "Architect Agent",
    "code": "Code Agent",
    "review": "Review Agent",
    "validation": "Validation Agent",
    "repair": "Repair Agent",
    "memory": "Memory Agent",
}

DEFAULT_AGENT_ITERATION_LIMITS: dict[AgentRole, int] = {
    "planner": 1,
    "architect": 1,
    "code": 2,
    "review": 2,
    "validation": 3,
    "repair": 5,
    "memory": 2,
}


@dataclass(frozen=True)
class AgentExecutionLimits:
    max_iterations_by_role: dict[AgentRole, int]

    @classmethod
    def defaults(cls) -> "AgentExecutionLimits":
        return cls(max_iterations_by_role=dict(DEFAULT_AGENT_ITERATION_LIMITS))

    def max_iterations(self, role: AgentRole) -> int:
        return max(1, int(self.max_iterations_by_role.get(role, 1)))


class MultiAgentCoordinator:
    """Records deterministic internal-agent handoffs into the task timeline."""

    def __init__(self, store: EventStore, limits: AgentExecutionLimits | None = None):
        self.store = store
        self.limits = limits or AgentExecutionLimits.defaults()

    def start_chain(self, task_id: str, *, workspace_root: Path, user_goal: str) -> ToolEvent:
        return self.store.record_event(
            task_id,
            kind="agent.chain",
            title="Multi-agent chain started",
            detail="Planner, Architect, Code, Review, Validation, Repair, and Memory agents will coordinate this task.",
            payload={
                "workspace_root": str(workspace_root.resolve()),
                "user_goal": user_goal,
                "agent_chain": list(AGENT_CHAIN),
                "max_iterations_by_role": dict(self.limits.max_iterations_by_role),
            },
        )

    def agent_output(
        self,
        task_id: str,
        role: AgentRole,
        title: str,
        *,
        summary: str = "",
        status: Literal["ok", "warning", "error"] = "ok",
        outputs: dict[str, Any] | None = None,
        iteration: int = 1,
    ) -> ToolEvent:
        max_iterations = self.limits.max_iterations(role)
        safe_iteration = max(1, int(iteration))
        event_status = status
        event_title = title
        event_summary = summary
        if safe_iteration > max_iterations:
            event_status = "error"
            event_title = f"{ROLE_LABELS[role]} iteration limit reached"
            event_summary = (
                summary
                or f"{ROLE_LABELS[role]} stopped at iteration {safe_iteration}; max allowed is {max_iterations}."
            )
        return self.store.record_event(
            task_id,
            kind=f"agent.{role}",
            title=event_title,
            status=event_status,
            detail=event_summary,
            payload={
                "agent_role": role,
                "agent_label": ROLE_LABELS[role],
                "iteration": safe_iteration,
                "max_iterations": max_iterations,
                "outputs": outputs or {},
            },
        )

    def handoff(
        self,
        task_id: str,
        from_role: AgentRole,
        to_role: AgentRole,
        *,
        reason: str = "",
        artifacts: dict[str, Any] | None = None,
    ) -> ToolEvent:
        return self.store.record_event(
            task_id,
            kind="agent.handoff",
            title=f"{ROLE_LABELS[from_role]} handed off to {ROLE_LABELS[to_role]}",
            detail=reason,
            payload={
                "from_agent_role": from_role,
                "from_agent_label": ROLE_LABELS[from_role],
                "to_agent_role": to_role,
                "to_agent_label": ROLE_LABELS[to_role],
                "artifacts": artifacts or {},
            },
        )

    def failure(
        self,
        task_id: str,
        role: AgentRole,
        *,
        summary: str,
        outputs: dict[str, Any] | None = None,
        iteration: int = 1,
    ) -> ToolEvent:
        return self.agent_output(
            task_id,
            role,
            f"{ROLE_LABELS[role]} failed",
            status="error",
            summary=summary,
            outputs=outputs,
            iteration=iteration,
        )

    def approval_requested(
        self,
        task_id: str,
        role: AgentRole,
        *,
        reason: str,
        blocked_paths: list[str],
    ) -> ToolEvent:
        return self.store.record_event(
            task_id,
            kind="agent.approval",
            title=f"{ROLE_LABELS[role]} requested approval",
            status="warning",
            detail=reason,
            payload={
                "agent_role": role,
                "agent_label": ROLE_LABELS[role],
                "blocked_paths": blocked_paths,
            },
        )

    def canceled(self, task_id: str, role: AgentRole, *, reason: str = "") -> ToolEvent:
        return self.store.record_event(
            task_id,
            kind="agent.control",
            title=f"{ROLE_LABELS[role]} observed task cancellation",
            status="warning",
            detail=reason or "Task was canceled before this agent could continue.",
            payload={"agent_role": role, "agent_label": ROLE_LABELS[role], "canceled": True},
        )

    def should_continue(self, task_id: str, role: AgentRole) -> bool:
        try:
            task = self.store.task(task_id)
        except KeyError:
            return False
        if task.status == "canceled":
            self.canceled(task_id, role)
            return False
        return True
