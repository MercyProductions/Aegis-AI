from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .knowledge import agent_knowledge_guidance, agent_knowledge_summary, knowledge_graph
from .memory import ProjectMemory, utc_now
from .multi_agent import (
    active_agent,
    agent_for_order,
    agent_pipeline,
    agent_profile,
    agent_roster,
    append_agent_decision,
    coordination_state,
)
from .quality import planner_guidance, planner_quality_summary, quality_dashboard
from .safety import is_safe_to_read
from .simulation import planner_simulation_guidance, planner_simulation_summary, simulate_change
from .validation import detect_validation_commands, run_validation
from .workspace import WorkspaceScanner


QUEUE_FILE = "orchestration-queue.json"
ACTIVE_FILE = "active-orchestration.json"
QUEUE_STATUSES = {"pending", "in_progress", "blocked", "needs_approval", "validating", "completed", "failed"}
APPROVAL_GATE_LABELS = {
    "file_edit": "File edits require explicit approval.",
    "file_delete": "File deletion requires explicit approval.",
    "build_command": "Build/test/lint commands require explicit approval before execution.",
    "install_package": "Package installation requires explicit approval.",
    "cloud_context": "Sending context to a cloud model requires explicit approval.",
}


class OrchestrationPersistenceError(RuntimeError):
    """Raised when orchestration queue state cannot be persisted."""


def create_orchestration_plan(
    workspace: str | Path,
    goal: str,
    *,
    source_client: str = "aegis-core",
    context_files: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    objective = scrub(goal).strip()
    if not objective:
        raise ValueError("A non-empty orchestration goal is required.")

    memory = ProjectMemory(root)
    memory.ensure()
    scan = WorkspaceScanner(root).scan(persist=True)
    commands = [command.__dict__ for command in detect_validation_commands(root)]
    context = _collect_context_files(root, context_files or [])
    required_files = _required_files(scan, context)
    affected_systems = _affected_systems(scan, objective, required_files)
    quality = quality_dashboard(root, scan=scan)
    graph = knowledge_graph(root, scan=scan)
    knowledge_summary = agent_knowledge_summary(graph, required_files)
    knowledge_guidance = agent_knowledge_guidance(knowledge_summary)
    simulation = simulate_change(root, objective, files=required_files, scan=scan, graph=graph, quality=quality)
    simulation_summary = planner_simulation_summary(simulation)
    risk = _risk_level(objective, affected_systems, required_files)
    risk = _risk_with_quality(risk, quality, required_files)
    risk = _risk_with_knowledge(risk, knowledge_summary)
    risk = _risk_with_simulation(risk, simulation_summary)
    quality_summary = planner_quality_summary(quality)
    guidance = planner_guidance(quality)
    guidance = _merge_lists(guidance, knowledge_guidance)
    guidance = _merge_lists(guidance, planner_simulation_guidance(simulation))
    gates = _approval_gates(objective, commands)
    validation_plan = _validation_plan(commands)
    rollback_plan = _rollback_plan(root, required_files)
    now = utc_now()
    plan_id = f"orch-{uuid.uuid4().hex[:12]}"
    queue_tasks = _task_breakdown(
        objective,
        affected_systems=affected_systems,
        required_files=required_files,
        risk=risk,
        gates=gates,
        validation_commands=commands,
        simulation=simulation_summary,
        now=now,
    )
    if queue_tasks:
        queue_tasks[0]["status"] = "in_progress"
        queue_tasks[0]["active_step"] = "inspect"

    plan = {
        "id": plan_id,
        "workspace": str(root),
        "objective": objective,
        "status": "in_progress",
        "risk": risk,
        "quality": quality_summary,
        "knowledge": knowledge_summary,
        "simulation": simulation_summary,
        "planner_guidance": guidance,
        "source_client": source_client,
        "affected_systems": affected_systems,
        "required_files": required_files,
        "blocked_context": context["blocked_files"],
        "approval_gates": gates,
        "validation_plan": validation_plan,
        "rollback_plan": rollback_plan,
        "active_task_id": queue_tasks[0]["id"] if queue_tasks else None,
        "active_step": queue_tasks[0]["active_step"] if queue_tasks else "complete",
        "active_agent": active_agent(queue_tasks[0]) if queue_tasks else None,
        "agents": agent_roster()["agents"],
        "agent_pipeline": agent_pipeline(queue_tasks),
        "created_at": now,
        "updated_at": now,
    }
    state = {
        "plan": plan,
        "tasks": queue_tasks,
        "validation_results": [],
        "agent_decisions": [],
        "history": [{"timestamp": now, "event": "orchestration_created", "plan_id": plan_id, "objective": objective}],
    }
    append_agent_decision(
        memory,
        state,
        agent_id="planner",
        task_id=queue_tasks[0]["id"] if queue_tasks else None,
        plan_id=plan_id,
        summary="Created supervised multi-agent orchestration plan.",
        details={
            "risk": risk,
            "affected_systems": affected_systems,
            "validation_commands": commands,
            "quality": quality_summary,
            "knowledge": knowledge_summary,
            "simulation": simulation_summary,
            "planner_guidance": guidance,
        },
    )
    _write_state(memory, state)
    _append_history(memory, {"event": "orchestration_created", "plan": plan})
    _write_orchestration_roadmap(memory, state)
    return orchestration_dashboard(root)


def orchestration_dashboard(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    state = _load_state(memory)
    if not state:
        return {
            "workspace": str(root),
            "current_goal": None,
            "plan": None,
            "task_list": [],
            "active_task": None,
            "active_step": None,
            "active_agent": None,
            "agents": agent_roster()["agents"],
            "agent_pipeline": [],
            "agent_decisions": [],
            "coordination": {"file_claims": {}, "conflicts": []},
            "pending_approvals": [],
            "validation_results": [],
            "rollback_option": _rollback_option(root),
            "safety": _safety_summary(),
        }
    plan = state["plan"]
    tasks = state["tasks"]
    active_task = _find_task(tasks, plan.get("active_task_id")) if plan.get("active_task_id") else _first_active_task(tasks)
    active_step = active_task.get("active_step") if active_task else plan.get("active_step")
    current_agent = active_agent(active_task)
    plan["active_agent"] = current_agent
    plan["agent_pipeline"] = agent_pipeline(tasks)
    return {
        "workspace": str(root),
        "current_goal": plan.get("objective"),
        "plan": plan,
        "task_list": tasks,
        "active_task": active_task,
        "active_step": active_step,
        "active_agent": current_agent,
        "agents": agent_roster()["agents"],
        "agent_pipeline": agent_pipeline(tasks),
        "agent_decisions": state.get("agent_decisions", [])[-25:],
        "coordination": coordination_state(tasks),
        "pending_approvals": _pending_approvals(tasks),
        "validation_results": state.get("validation_results", [])[-10:],
        "rollback_option": _rollback_option(root),
        "safety": _safety_summary(),
    }


def advance_orchestration_step(
    workspace: str | Path,
    *,
    task_id: str | None = None,
    action: str = "inspect",
    approval: bool = False,
    summary: str | None = None,
    affected_files: list[str] | None = None,
    validation_command: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    state = _load_state(memory)
    if not state:
        raise ValueError("No active orchestration plan exists for this workspace.")
    plan = state["plan"]
    tasks = state["tasks"]
    task = _find_task(tasks, task_id or plan.get("active_task_id")) or _first_active_task(tasks)
    if task is None:
        raise ValueError("No active orchestration task is available.")

    action_name = _normalize_action(action)
    transition_summary = summary or ""
    if action_name == "inspect":
        transition_summary = summary or "Inspection step recorded."
        _transition(task, "in_progress", "plan", transition_summary)
    elif action_name == "plan":
        transition_summary = summary or "Plan step recorded."
        _transition(task, "in_progress", "propose_changes", transition_summary)
    elif action_name == "propose_changes":
        if task.get("approval_gates"):
            transition_summary = summary or "Proposal is ready for explicit approval before edits or risky commands."
            _transition(task, "needs_approval", "wait_for_approval", transition_summary)
        else:
            transition_summary = summary or "Proposal step recorded; no risky gate is attached to this task."
            _transition(task, "in_progress", "apply_approved_changes", transition_summary)
    elif action_name == "approve":
        if not approval:
            transition_summary = summary or "Approval is required before this task can continue."
            _transition(task, "needs_approval", "wait_for_approval", transition_summary)
        else:
            transition_summary = summary or "Approved changes may now be applied by the client."
            task.setdefault("approvals", []).append({"timestamp": utc_now(), "summary": summary or "Approved by client/user."})
            _transition(task, "in_progress", "apply_approved_changes", transition_summary)
    elif action_name == "apply_approved_changes":
        if task.get("approval_gates") and not approval and not task.get("approvals"):
            transition_summary = summary or "File edits require explicit approval before apply."
            _transition(task, "needs_approval", "wait_for_approval", transition_summary)
        else:
            if affected_files:
                task["affected_files"] = _merge_lists(task.get("affected_files", []), affected_files)
            transition_summary = summary or "Approved changes were marked as applied by the client."
            _transition(task, "validating", "validate", transition_summary)
    elif action_name == "validate":
        requires_validation_approval = bool(validation_command or task.get("validation_commands"))
        if requires_validation_approval and not approval:
            transition_summary = summary or "Validation command approval is required before execution."
            _transition(task, "needs_approval", "wait_for_validation_approval", transition_summary)
        else:
            transition_summary = summary or "Running approved validation."
            _transition(task, "validating", "validate", transition_summary)
            result = run_validation(root, command=validation_command)
            validation_record = {"task_id": task["id"], "timestamp": utc_now(), **result}
            state.setdefault("validation_results", []).append(validation_record)
            task["latest_validation"] = validation_record
            transition_summary = "Validation passed." if result.get("ok") else "Validation failed; repair proposal required."
            _transition(task, "validating" if result.get("ok") else "failed", "summarize" if result.get("ok") else "repair", transition_summary)
    elif action_name in {"summarize", "complete"}:
        transition_summary = summary or "Task completed and memory updated."
        _complete_task(memory, state, task, summary=summary, affected_files=affected_files or [])
    elif action_name == "block":
        transition_summary = summary or "Task blocked."
        _transition(task, "blocked", task.get("active_step") or "blocked", transition_summary)
    elif action_name == "fail":
        transition_summary = summary or "Task failed."
        _transition(task, "failed", task.get("active_step") or "failed", transition_summary)
        plan["status"] = "blocked"
    else:
        raise ValueError(f"Unsupported orchestration action: {action}.")

    plan["updated_at"] = utc_now()
    active = task if task.get("status") in {"in_progress", "needs_approval", "validating", "blocked", "failed"} else _first_active_task(tasks)
    plan["active_task_id"] = active.get("id") if active else None
    plan["active_step"] = active.get("active_step") if active else "complete"
    plan["active_agent"] = active_agent(active)
    plan["agent_pipeline"] = agent_pipeline(tasks)
    if active is None and all(task.get("status") == "completed" for task in tasks):
        plan["status"] = "completed"
    elif any(task.get("status") == "failed" for task in tasks):
        plan["status"] = "blocked"
    append_agent_decision(
        memory,
        state,
        agent_id=str(task.get("owner_agent") or "planner"),
        task_id=task.get("id"),
        plan_id=plan.get("id"),
        summary=transition_summary,
        details={"action": action_name, "status": task.get("status"), "active_step": task.get("active_step")},
    )
    state.setdefault("history", []).append({"timestamp": utc_now(), "event": f"orchestration_{action_name}", "task_id": task["id"]})
    _write_state(memory, state)
    _append_history(memory, {"event": f"orchestration_{action_name}", "task": task, "plan_id": plan.get("id")})
    _write_orchestration_roadmap(memory, state)
    return orchestration_dashboard(root)


def _task_breakdown(
    objective: str,
    *,
    affected_systems: list[str],
    required_files: list[str],
    risk: str,
    gates: list[dict[str, str]],
    validation_commands: list[dict[str, Any]],
    simulation: dict[str, Any] | None,
    now: str,
) -> list[dict[str, Any]]:
    short_goal = objective[:90] + ("..." if len(objective) > 90 else "")
    task_specs = [
        (
            f"Plan task order for: {short_goal}",
            "development_task",
            "Break the objective into safe task order, risk, required files, validation plan, and rollback expectations.",
            {"cloud_context"},
            "planner",
        ),
        (
            f"Review architecture boundaries for: {short_goal}",
            "development_task",
            "Check ownership boundaries, existing patterns, duplication risk, and rewrite risk before implementation.",
            set(),
            "architect",
        ),
        (
            f"Prepare focused approved changes for: {short_goal}",
            "development_task",
            "Draft the smallest safe change set, wait for approval, then let the client apply approved edits.",
            {"file_edit", "file_delete", "install_package", "cloud_context"},
            "coder",
        ),
        (
            f"Review proposed changes for: {short_goal}",
            "development_task",
            "Look for bugs, safety violations, overengineering, and unapproved scope expansion.",
            set(),
            "reviewer",
        ),
        (
            f"Validate result for: {short_goal}",
            "development_task",
            "Run detected validation only after approval and summarize failures.",
            {"build_command"},
            "tester",
        ),
        (
            f"Repair failed validation for: {short_goal}",
            "development_task",
            "Analyze failed builds/tests and propose minimal bounded repairs with an attempt limit.",
            {"file_edit", "file_delete", "build_command"},
            "repair",
        ),
        (
            f"Update documentation and memory for: {short_goal}",
            "development_task",
            "Record decisions, documentation notes, validation outcome, roadmap progress, and the next recommendation.",
            {"file_edit"},
            "documentation",
        ),
    ]
    if risk == "high" or (simulation and simulation.get("split_recommended")):
        task_specs.insert(
            2,
            (
                f"Split predicted high-risk work for: {short_goal}",
                "development_task",
                "Use the simulation forecast to choose the first smallest safe slice and defer broader edits.",
                set(),
                "planner",
            ),
        )
    tasks: list[dict[str, Any]] = []
    for index, (title, step, detail, gate_filter, agent_id) in enumerate(task_specs, start=1):
        agent = agent_profile(agent_id) or agent_for_order(index)
        task_gates = [gate for gate in gates if gate.get("id") in gate_filter]
        tasks.append(
            {
                "id": f"orch-task-{uuid.uuid4().hex[:10]}",
                "title": title,
                "status": "pending",
                "active_step": "pending",
                "order": index,
                "step": step,
                "detail": detail,
                "objective": objective,
                "risk": risk,
                "owner_agent": agent_id,
                "owner_agent_label": agent["label"],
                "agent": agent,
                "affected_systems": affected_systems,
                "required_files": required_files,
                "affected_files": [],
                "approval_required": bool(task_gates),
                "approval_gates": task_gates,
                "validation_commands": validation_commands,
                "repair_attempt_limit": 3 if agent_id == "repair" else None,
                "created_at": now,
                "updated_at": now,
                "history": [],
            }
        )
    return tasks


def _collect_context_files(root: Path, context_files: list[str]) -> dict[str, list[dict[str, str]]]:
    included: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for item in context_files[:50]:
        relative = str(item).strip().replace("\\", "/")
        if not relative:
            continue
        candidate = (root / relative).resolve()
        if not is_safe_to_read(candidate, root):
            blocked.append({"path": relative, "reason": "secret-like, ignored, or outside workspace"})
            continue
        if not candidate.is_file():
            blocked.append({"path": relative, "reason": "not a readable file"})
            continue
        included.append({"path": relative})
    return {"included_files": included, "blocked_files": blocked}


def _required_files(scan: dict[str, Any], context: dict[str, list[dict[str, str]]]) -> list[str]:
    files: list[str] = [item["path"] for item in context.get("included_files", [])]
    for key in ("build_files", "readmes", "test_files", "entry_points"):
        files.extend(str(item) for item in scan.get(key, [])[:6])
    return _merge_lists([], files)[:24]


def _affected_systems(scan: dict[str, Any], objective: str, required_files: list[str]) -> list[str]:
    systems = [str(item) for item in scan.get("frameworks", [])[:8]]
    language_names = [str(name) for name in (scan.get("languages") or {}).keys()]
    systems.extend(language_names[:8])
    lower_goal = objective.lower()
    if any(term in lower_goal for term in ("extension", "vscode", "visual studio", "vsix")):
        systems.append("editor-extension")
    if any(term in lower_goal for term in ("desktop", "tauri", "electron")):
        systems.append("desktop-client")
    if any(term in lower_goal for term in ("website", "frontend", "backend", "fastapi")):
        systems.append("website")
    if any("package.json" in item for item in required_files):
        systems.append("node")
    if any(item.endswith((".sln", ".csproj")) for item in required_files):
        systems.append(".net")
    return _merge_lists([], systems) or ["workspace"]


def _risk_level(objective: str, affected_systems: list[str], required_files: list[str]) -> str:
    text = objective.lower()
    high_terms = ("delete", "remove", "migration", "credentials", "auth", "installer", "package install", "cloud", "secrets")
    if any(term in text for term in high_terms):
        return "high"
    if len(affected_systems) > 4 or len(required_files) > 10:
        return "medium"
    medium_terms = ("refactor", "build", "validation", "rollback", "extension", "desktop", "website")
    if any(term in text for term in medium_terms):
        return "medium"
    return "low"


def _risk_with_quality(risk: str, quality: dict[str, Any], required_files: list[str]) -> str:
    if risk == "high":
        return risk
    score = int(quality.get("score") or 100)
    statuses = quality.get("statuses", {})
    high_risk_paths = {str(item.get("path") or "") for item in quality.get("high_risk_files", []) if isinstance(item, dict)}
    touches_high_risk = bool(high_risk_paths.intersection(required_files))
    validation_failed = any(
        isinstance(statuses.get(name), dict) and statuses[name].get("status") == "failed"
        for name in ("build", "test", "lint", "validation")
    )
    if score < 50 or validation_failed or touches_high_risk:
        return "high"
    if score < 70 and risk == "low":
        return "medium"
    return risk


def _risk_with_knowledge(risk: str, knowledge: dict[str, Any]) -> str:
    if risk == "high":
        return risk
    if knowledge.get("related_items") and any(item.get("type") in {"bug", "validation_failure"} for item in knowledge["related_items"]):
        return "high"
    if knowledge.get("unstable_modules") and risk == "low":
        return "medium"
    if len(knowledge.get("impacted_systems", [])) >= 3 and risk == "low":
        return "medium"
    return risk


def _risk_with_simulation(risk: str, simulation: dict[str, Any]) -> str:
    forecast = str(simulation.get("risk_level") or "low")
    if forecast in {"high", "dangerous_architectural_change"}:
        return "high"
    if forecast == "moderate" and risk == "low":
        return "medium"
    return risk


def _approval_gates(objective: str, validation_commands: list[dict[str, Any]]) -> list[dict[str, str]]:
    text = objective.lower()
    gates = [{"id": "file_edit", "label": APPROVAL_GATE_LABELS["file_edit"]}]
    if any(term in text for term in ("delete", "remove", "cleanup dead code")):
        gates.append({"id": "file_delete", "label": APPROVAL_GATE_LABELS["file_delete"]})
    if validation_commands:
        gates.append({"id": "build_command", "label": APPROVAL_GATE_LABELS["build_command"]})
    if any(term in text for term in ("install", "package", "dependency", "npm i", "pip install")):
        gates.append({"id": "install_package", "label": APPROVAL_GATE_LABELS["install_package"]})
    if any(term in text for term in ("cloud", "openai", "anthropic", "google", "openrouter")):
        gates.append({"id": "cloud_context", "label": APPROVAL_GATE_LABELS["cloud_context"]})
    return _dedupe_gates(gates)


def _validation_plan(commands: list[dict[str, Any]]) -> dict[str, Any]:
    if not commands:
        return {"commands": [], "summary": "No validation command detected; client should request a manual validation path before risky edits."}
    return {
        "commands": commands,
        "summary": "Run detected validation after approved edits. Build/test/lint commands require approval before execution.",
    }


def _rollback_plan(root: Path, required_files: list[str]) -> dict[str, Any]:
    return {
        "strategy": "Create or use a client checkpoint before applying approved edits; restore checkpoint or revert affected files if validation fails.",
        "checkpoint_dir": str(root / ".aegis" / "checkpoints"),
        "files": required_files,
        "notes": [
            "Core orchestration records rollback metadata but does not blindly mutate files.",
            "Clients that apply patches should create checkpoints before writing.",
        ],
    }


def _rollback_option(root: Path) -> dict[str, Any]:
    checkpoints_root = root / ".aegis" / "checkpoints"
    checkpoints: list[str] = []
    if checkpoints_root.is_dir():
        try:
            checkpoints = [item.name for item in sorted(checkpoints_root.iterdir(), key=lambda path: path.name, reverse=True) if item.is_dir()][:10]
        except OSError:
            checkpoints = []
    return {
        "available": bool(checkpoints),
        "checkpoint_dir": str(checkpoints_root),
        "checkpoints": checkpoints,
        "label": "Restore latest checkpoint" if checkpoints else "No checkpoint available yet",
    }


def _safety_summary() -> dict[str, Any]:
    return {
        "uncontrolled_autonomy": False,
        "approval_required_for": ["file_edit", "file_delete", "build_command", "install_package", "cloud_context"],
        "notes": [
            "Core plans, queues, validates, and records memory.",
            "Specialized agents coordinate through shared .aegis memory and one owner_agent per task.",
            "File edits and risky commands stay approval-gated and client-mediated.",
        ],
    }


def _normalize_action(action: str) -> str:
    text = (action or "inspect").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "propose": "propose_changes",
        "proposal": "propose_changes",
        "approval": "approve",
        "apply": "apply_approved_changes",
        "applied": "apply_approved_changes",
        "validation": "validate",
        "summary": "summarize",
        "done": "complete",
    }
    return aliases.get(text, text)


def _transition(task: dict[str, Any], status: str, active_step: str, summary: str) -> None:
    if status not in QUEUE_STATUSES:
        raise ValueError(f"Unsupported orchestration status: {status}")
    task["status"] = status
    task["active_step"] = active_step
    task["updated_at"] = utc_now()
    task.setdefault("history", []).append({"timestamp": utc_now(), "status": status, "active_step": active_step, "summary": scrub(summary)})


def _complete_task(
    memory: ProjectMemory,
    state: dict[str, Any],
    task: dict[str, Any],
    *,
    summary: str | None = None,
    affected_files: list[str] | None = None,
) -> None:
    files = _merge_lists(task.get("affected_files", []), affected_files or [])
    if files:
        task["affected_files"] = files
    latest_validation = task.get("latest_validation") or {}
    validation_status = "passed" if latest_validation.get("ok") else "failed" if latest_validation else "not run"
    _transition(task, "completed", "summarize", summary or "Task completed and memory updated.")
    memory.append_decision(summary or f"Completed orchestration task: {task.get('title')}", files, validation_status)
    _append_validation_note(memory, task, validation_status)
    next_task = _next_pending_task(state["tasks"])
    if next_task is not None:
        _transition(next_task, "in_progress", "inspect", "Continuing to next queued task.")


def _append_validation_note(memory: ProjectMemory, task: dict[str, Any], validation_status: str) -> None:
    path = memory.root / "validation-log.md"
    entry = (
        f"## {utc_now()} - orchestration task {validation_status}\n\n"
        f"Task: `{scrub(str(task.get('title') or task.get('id'))).strip()}`\n\n"
        f"Status: `{validation_status}`\n\n"
    )
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except OSError:
        return


def _write_orchestration_roadmap(memory: ProjectMemory, state: dict[str, Any]) -> None:
    plan = state["plan"]
    lines = [
        "## Active Orchestration",
        "",
        f"- Objective: {plan.get('objective')}",
        f"- Risk: {plan.get('risk')}",
        f"- Status: {plan.get('status')}",
        f"- Active step: {plan.get('active_step')}",
    ]
    quality = plan.get("quality") if isinstance(plan.get("quality"), dict) else {}
    if quality:
        lines.extend(
            [
                f"- Health score: {quality.get('score')} ({quality.get('grade')})",
                f"- Recommended improvement: {quality.get('recommended_next_improvement')}",
            ]
        )
    knowledge = plan.get("knowledge") if isinstance(plan.get("knowledge"), dict) else {}
    if knowledge:
        impacted = ", ".join(knowledge.get("impacted_systems", [])[:6]) or "none detected"
        lines.append(f"- Knowledge graph impacted systems: {impacted}")
    simulation = plan.get("simulation") if isinstance(plan.get("simulation"), dict) else {}
    if simulation:
        lines.extend(
            [
                f"- Simulation forecast: {simulation.get('risk_level')} ({simulation.get('risk_score')}/100, confidence {simulation.get('confidence')}%)",
                f"- Validation cost: {simulation.get('validation_cost')}",
                f"- Rollback complexity: {simulation.get('rollback_complexity')}",
                f"- First safe step: {simulation.get('recommended_first_step')}",
            ]
        )
    guidance = plan.get("planner_guidance") if isinstance(plan.get("planner_guidance"), list) else []
    if guidance:
        lines.extend(["", "## Planner Health Guidance", "", *[f"- {item}" for item in guidance]])
    lines.extend(["", "## Task Queue", ""])
    for task in state.get("tasks", []):
        lines.append(f"{task.get('order')}. {task.get('title')} [{task.get('status')}]")
        lines.append(f"   - Agent: {task.get('owner_agent_label') or task.get('owner_agent')}")
        lines.append(f"   - Step: {task.get('active_step')}")
        if task.get("approval_gates"):
            gates = ", ".join(gate.get("id", "") for gate in task["approval_gates"])
            lines.append(f"   - Approval gates: {gates}")
    lines.extend(["", "## Rollback Plan", "", f"- {plan.get('rollback_plan', {}).get('strategy', 'Use checkpoints before edits.')}"])
    memory.write_generated_markdown("roadmap.md", "Roadmap", "\n".join(lines))


def _load_state(memory: ProjectMemory) -> dict[str, Any] | None:
    path = memory.root / QUEUE_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("plan"), dict) or not isinstance(data.get("tasks"), list):
        return None
    data["tasks"] = [_normalize_task(task) for task in data["tasks"] if isinstance(task, dict)]
    data["validation_results"] = data.get("validation_results") if isinstance(data.get("validation_results"), list) else []
    data["history"] = data.get("history") if isinstance(data.get("history"), list) else []
    return data


def _write_state(memory: ProjectMemory, state: dict[str, Any]) -> None:
    queue_path = memory.root / QUEUE_FILE
    active_path = memory.root / ACTIVE_FILE
    _ensure_json_target(queue_path)
    _ensure_json_target(active_path)
    memory.write_json(QUEUE_FILE, state)
    memory.write_json(ACTIVE_FILE, state.get("plan", {}))
    persisted = _load_state(memory)
    if persisted != state:
        raise OrchestrationPersistenceError(
            f"Could not persist orchestration queue at {queue_path}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationPersistenceError(
            f"Could not persist active orchestration state at {active_path}."
        ) from exc
    if active != state.get("plan", {}):
        raise OrchestrationPersistenceError(
            f"Could not persist active orchestration state at {active_path}."
        )


def _ensure_json_target(path: Path) -> None:
    if path.parent.exists() and not path.parent.is_dir():
        raise OrchestrationPersistenceError(
            f"Could not persist orchestration state because {path.parent} is not a directory."
        )
    if path.exists() and not path.is_file():
        raise OrchestrationPersistenceError(
            f"Could not persist orchestration state because {path} is not a writable file."
        )


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    task["id"] = str(task.get("id") or f"orch-task-{uuid.uuid4().hex[:10]}")
    task["title"] = str(task.get("title") or "Untitled orchestration task")
    task["status"] = str(task.get("status") or "pending")
    if task["status"] not in QUEUE_STATUSES:
        task["status"] = "pending"
    task["active_step"] = str(task.get("active_step") or "pending")
    task["created_at"] = str(task.get("created_at") or now)
    task["updated_at"] = str(task.get("updated_at") or task["created_at"])
    task["history"] = task.get("history") if isinstance(task.get("history"), list) else []
    task["approval_gates"] = task.get("approval_gates") if isinstance(task.get("approval_gates"), list) else []
    task["affected_files"] = task.get("affected_files") if isinstance(task.get("affected_files"), list) else []
    order = int(task.get("order") or 1)
    owner = str(task.get("owner_agent") or "").strip().lower()
    agent = agent_profile(owner) or agent_for_order(order)
    task["owner_agent"] = agent["id"]
    task["owner_agent_label"] = agent["label"]
    existing_agent = task.get("agent")
    task["agent"] = (
        existing_agent
        if isinstance(existing_agent, dict) and existing_agent.get("id") == agent["id"]
        else agent
    )
    return task


def _find_task(tasks: list[dict[str, Any]], task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def _first_active_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for status in ("in_progress", "needs_approval", "validating", "blocked", "failed"):
        for task in sorted(tasks, key=lambda item: int(item.get("order") or 0)):
            if task.get("status") == status:
                return task
    return None


def _next_pending_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for task in sorted(tasks, key=lambda item: int(item.get("order") or 0)):
        if task.get("status") == "pending":
            return task
    return None


def _pending_approvals(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    approvals: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("status") == "needs_approval":
            approvals.append(
                {
                    "task_id": task.get("id"),
                    "title": task.get("title"),
                    "active_step": task.get("active_step"),
                    "approval_gates": task.get("approval_gates", []),
                    "summary": (task.get("history") or [{}])[-1].get("summary", "Approval required."),
                }
            )
    return approvals


def _dedupe_gates(gates: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for gate in gates:
        gate_id = gate.get("id", "").strip()
        if gate_id and gate_id not in seen:
            seen.add(gate_id)
            result.append(gate)
    return result


def _merge_lists(existing: list[Any], incoming: list[Any]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*existing, *incoming]:
        text = scrub(str(item)).strip().replace("\\", "/")
        if text and text not in seen:
            seen.add(text)
            merged.append(text)
    return merged


def _append_history(memory: ProjectMemory, event: dict[str, Any]) -> None:
    path = memory.root / "agent-history.json"
    try:
        history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, json.JSONDecodeError):
        history = []
    if not isinstance(history, list):
        history = []
    history.append({"timestamp": utc_now(), **event})
    try:
        path.write_text(json.dumps(history[-500:], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        return
