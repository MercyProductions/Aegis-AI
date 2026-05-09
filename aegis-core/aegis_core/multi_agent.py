from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .memory import ProjectMemory, utc_now


@dataclass(frozen=True)
class AgentProfile:
    id: str
    label: str
    purpose: str
    responsibilities: list[str]
    approval_gates: list[str]
    outputs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


AGENT_SEQUENCE = ["planner", "architect", "coder", "reviewer", "tester", "repair", "documentation"]

AGENT_PROFILES: dict[str, AgentProfile] = {
    "planner": AgentProfile(
        id="planner",
        label="Planner Agent",
        purpose="Break larger goals into ordered, safe tasks.",
        responsibilities=[
            "define objective",
            "estimate risk",
            "choose task order",
            "create validation plan",
        ],
        approval_gates=["cloud_context"],
        outputs=["task breakdown", "risk estimate", "validation plan"],
    ),
    "architect": AgentProfile(
        id="architect",
        label="Architect Agent",
        purpose="Protect architecture consistency and clear runtime boundaries.",
        responsibilities=[
            "check system boundaries",
            "prevent messy rewrites",
            "recommend clean structure",
            "flag duplicated responsibility",
        ],
        approval_gates=[],
        outputs=["architecture notes", "boundary warnings"],
    ),
    "coder": AgentProfile(
        id="coder",
        label="Coder Agent",
        purpose="Prepare focused changes and apply only approved work.",
        responsibilities=[
            "propose file changes",
            "keep diffs focused",
            "respect existing patterns",
            "avoid unrelated rewrites",
        ],
        approval_gates=["file_edit", "file_delete", "install_package", "cloud_context"],
        outputs=["change proposal", "affected files"],
    ),
    "reviewer": AgentProfile(
        id="reviewer",
        label="Reviewer Agent",
        purpose="Review proposed changes for bugs, safety, and unnecessary complexity.",
        responsibilities=[
            "detect bugs",
            "check safety rules",
            "catch overengineering",
            "verify scope discipline",
        ],
        approval_gates=[],
        outputs=["review findings", "risk notes"],
    ),
    "tester": AgentProfile(
        id="tester",
        label="Tester Agent",
        purpose="Identify and run approved validation commands.",
        responsibilities=[
            "identify tests and builds",
            "run validation after approval",
            "summarize failures",
            "record validation results",
        ],
        approval_gates=["build_command"],
        outputs=["validation summary", "failure notes"],
    ),
    "repair": AgentProfile(
        id="repair",
        label="Repair Agent",
        purpose="Analyze failed validation and propose minimal bounded repairs.",
        responsibilities=[
            "inspect failed builds or tests",
            "propose minimal fixes",
            "limit repair attempts",
            "stop when repair risk grows",
        ],
        approval_gates=["file_edit", "file_delete", "build_command"],
        outputs=["repair proposal", "attempt summary"],
    ),
    "documentation": AgentProfile(
        id="documentation",
        label="Documentation Agent",
        purpose="Update shared memory and explain completed changes.",
        responsibilities=[
            "update docs and roadmaps",
            "record decisions",
            "explain changes",
            "maintain onboarding notes",
        ],
        approval_gates=["file_edit"],
        outputs=["documentation notes", "decision log entry"],
    ),
}


def agent_roster() -> dict[str, Any]:
    return {
        "agents": [AGENT_PROFILES[agent_id].to_dict() for agent_id in AGENT_SEQUENCE],
        "coordination_rules": [
            "Agents share project memory under .aegis.",
            "Every queued task has one owner_agent.",
            "Agents may propose changes, but file edits require approval.",
            "Risky commands and cloud calls require explicit approval.",
            "Overlapping affected files are surfaced as coordination conflicts.",
        ],
        "approval_required_for": ["file_edit", "file_delete", "build_command", "install_package", "cloud_context"],
    }


def agent_profile(agent_id: str | None) -> dict[str, Any] | None:
    if not agent_id:
        return None
    profile = AGENT_PROFILES.get(str(agent_id).strip().lower())
    return profile.to_dict() if profile else None


def agent_for_order(order: int) -> dict[str, Any]:
    index = max(0, min(order - 1, len(AGENT_SEQUENCE) - 1))
    return AGENT_PROFILES[AGENT_SEQUENCE[index]].to_dict()


def agent_pipeline(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = []
    by_agent: dict[str, dict[str, Any]] = {}
    for task in sorted(tasks, key=lambda item: int(item.get("order") or 0)):
        agent_id = str(task.get("owner_agent") or "").strip().lower()
        if agent_id and agent_id not in by_agent:
            by_agent[agent_id] = task
    for agent_id in AGENT_SEQUENCE:
        task = by_agent.get(agent_id)
        profile = AGENT_PROFILES[agent_id]
        pipeline.append(
            {
                "agent_id": agent_id,
                "label": profile.label,
                "status": task.get("status", "pending") if task else "pending",
                "task_id": task.get("id") if task else None,
                "task_title": task.get("title") if task else None,
                "active_step": task.get("active_step") if task else "pending",
            }
        )
    return pipeline


def active_agent(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not task:
        return None
    agent = agent_profile(str(task.get("owner_agent") or ""))
    if agent is None:
        return None
    return {
        **agent,
        "task_id": task.get("id"),
        "task_title": task.get("title"),
        "active_step": task.get("active_step"),
        "status": task.get("status"),
    }


def coordination_state(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    claims: dict[str, list[dict[str, str]]] = {}
    for task in tasks:
        owner = str(task.get("owner_agent") or "unknown")
        for path in task.get("affected_files") or []:
            key = str(path).replace("\\", "/")
            claims.setdefault(key, []).append(
                {
                    "task_id": str(task.get("id") or ""),
                    "agent_id": owner,
                    "status": str(task.get("status") or ""),
                }
            )
    conflicts = [
        {"path": path, "claims": claim_list}
        for path, claim_list in sorted(claims.items())
        if len({claim.get("agent_id") for claim in claim_list}) > 1
    ]
    return {"file_claims": claims, "conflicts": conflicts}


def append_agent_decision(
    memory: ProjectMemory,
    state: dict[str, Any],
    *,
    agent_id: str,
    task_id: str | None,
    plan_id: str | None,
    summary: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = AGENT_PROFILES.get(agent_id, AGENT_PROFILES["planner"])
    decision = {
        "timestamp": utc_now(),
        "event": "agent_decision",
        "agent_id": profile.id,
        "agent_label": profile.label,
        "task_id": task_id,
        "plan_id": plan_id,
        "summary": summary,
        "details": details or {},
    }
    state.setdefault("agent_decisions", []).append(decision)
    _append_history(memory, decision)
    return decision


def _append_history(memory: ProjectMemory, event: dict[str, Any]) -> None:
    path = memory.root / "agent-history.json"
    try:
        history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, json.JSONDecodeError):
        history = []
    if not isinstance(history, list):
        history = []
    history.append(event)
    try:
        path.write_text(json.dumps(history[-500:], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        return
