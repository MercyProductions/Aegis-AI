from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .knowledge import architecture_summary, impact_analysis
from .memory import ProjectMemory, utc_now
from .model_router import routing_profiles


AGENT_RUNTIME_VERSION = "2026.05.12"
AGENT_HISTORY_FILE = "agent-history.json"
WORKFLOWS_FILE = "workflow-runtime.json"

TERMINAL_TASK_STATES = {"completed", "failed", "cancelled"}
MUTATING_AGENT_IDS = {"coder_agent", "repair_agent"}
ROLE_TO_AGENT_ID = {
    "planner": "planner_agent",
    "coder": "coder_agent",
    "validator": "validator_agent",
    "repair_agent": "repair_agent",
    "researcher": "researcher_agent",
    "summarizer": "summarizer_agent",
    "architecture": "architecture_agent",
    "architect": "architecture_agent",
    "routing": "routing_agent",
}

FORMAL_AGENTS: dict[str, dict[str, Any]] = {
    "planner_agent": {
        "role": "planner",
        "label": "Planner Agent",
        "capabilities": ["intake", "task_decomposition", "dependency_scheduling", "approval_planning", "roadmap_execution"],
        "supported_workflow_types": ["chat_request", "generate_feature", "validate_project", "continue_roadmap", "build_project", "scan_workspace"],
        "preferred_model_profile": {"route_profile": "best_reasoning", "task_type": "repo_wide_planning", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 1, "max_parallel_tasks": 4, "max_context_files": 20, "requires_approval_for": ["provider_call"]},
        "memory_scope": "workflow",
        "communication_outputs": ["execution_plan", "risk_assessment", "dependency_schedule", "approval_checkpoints"],
    },
    "coder_agent": {
        "role": "coder",
        "label": "Coder Agent",
        "capabilities": ["change_proposal", "patch_preview", "implementation_notes", "safe_apply_handoff"],
        "supported_workflow_types": ["generate_feature", "repair_project", "continue_roadmap", "build_project"],
        "preferred_model_profile": {"route_profile": "best_coding", "task_type": "code_completion", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 1, "max_file_modifications": 25, "max_context_files": 18, "requires_approval_for": ["file_edit", "file_delete"]},
        "memory_scope": "file_scoped",
        "communication_outputs": ["change_summary", "affected_files", "risk_notes", "apply_request"],
    },
    "validator_agent": {
        "role": "validator",
        "label": "Validator Agent",
        "capabilities": ["validation_planning", "validation_execution", "result_capture", "failure_classification"],
        "supported_workflow_types": ["validate_project", "repair_project", "generate_feature", "build_project"],
        "preferred_model_profile": {"route_profile": "local_only", "task_type": "validation", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 2, "max_validation_commands": 3, "max_context_files": 12, "requires_approval_for": ["validation_command"]},
        "memory_scope": "validation_scoped",
        "communication_outputs": ["validation_report", "failure_summary", "repair_recommendation"],
    },
    "repair_agent": {
        "role": "repair_agent",
        "label": "Repair Agent",
        "capabilities": ["failure_analysis", "bounded_repair_planning", "repair_recommendations", "escalation"],
        "supported_workflow_types": ["repair_project", "generate_feature", "validate_project", "build_project"],
        "preferred_model_profile": {"route_profile": "best_coding", "task_type": "hard_debugging", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 2, "max_repair_attempts": 3, "max_context_files": 16, "requires_approval_for": ["file_edit", "validation_command"]},
        "memory_scope": "dependency_scoped",
        "communication_outputs": ["repair_plan", "root_cause", "risk_notes", "escalation_reason"],
    },
    "researcher_agent": {
        "role": "researcher",
        "label": "Researcher Agent",
        "capabilities": ["research_questions", "source_synthesis", "structured_findings"],
        "supported_workflow_types": ["research_task", "benchmark_models", "generate_feature"],
        "preferred_model_profile": {"route_profile": "best_reasoning", "task_type": "research_task", "privacy_sensitive": False},
        "execution_limits": {"max_retries": 1, "max_context_files": 10, "requires_approval_for": ["provider_call", "cloud_context"]},
        "memory_scope": "task_specific",
        "communication_outputs": ["structured_findings", "open_questions", "source_notes"],
    },
    "summarizer_agent": {
        "role": "summarizer",
        "label": "Summarizer Agent",
        "capabilities": ["completion_summary", "memory_update", "handoff_summary", "timeline_summary"],
        "supported_workflow_types": ["chat_request", "generate_feature", "validate_project", "repair_project", "continue_roadmap", "build_project", "scan_workspace", "benchmark_models", "generate_media", "research_task"],
        "preferred_model_profile": {"route_profile": "fastest", "task_type": "summarization", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 1, "max_context_files": 12, "requires_approval_for": []},
        "memory_scope": "workflow_summary",
        "communication_outputs": ["completion_summary", "known_limitations", "next_steps"],
    },
    "architecture_agent": {
        "role": "architecture",
        "label": "Architecture Agent",
        "capabilities": ["architecture_review", "boundary_analysis", "impact_analysis", "dependency_risk_assessment"],
        "supported_workflow_types": ["generate_feature", "repair_project", "continue_roadmap", "scan_workspace", "build_project"],
        "preferred_model_profile": {"route_profile": "best_reasoning", "task_type": "repo_wide_planning", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 1, "max_context_files": 24, "requires_approval_for": ["provider_call"]},
        "memory_scope": "dependency_scoped",
        "communication_outputs": ["architecture_notes", "risk_assessment", "dependency_constraints", "validation_targets"],
    },
    "routing_agent": {
        "role": "routing",
        "label": "Routing Agent",
        "capabilities": ["model_route_selection", "capability_matching", "privacy_review", "fallback_chain_selection"],
        "supported_workflow_types": ["chat_request", "generate_feature", "validate_project", "repair_project", "research_task", "generate_media", "benchmark_models"],
        "preferred_model_profile": {"route_profile": "fallback_safe", "task_type": "model_routing", "privacy_sensitive": True},
        "execution_limits": {"max_retries": 1, "max_context_files": 0, "requires_approval_for": ["cloud_context"]},
        "memory_scope": "routing_metadata",
        "communication_outputs": ["route_explanation", "fallback_chain", "privacy_risk", "missing_capabilities"],
    },
}


def formal_agent_id(role_or_agent_id: str | None) -> str:
    value = str(role_or_agent_id or "").strip().lower()
    if value in FORMAL_AGENTS:
        return value
    return ROLE_TO_AGENT_ID.get(value, "planner_agent")


def formal_agent(agent_id: str | None) -> dict[str, Any]:
    resolved = formal_agent_id(agent_id)
    profile = FORMAL_AGENTS[resolved]
    return {
        "id": resolved,
        **profile,
        "runtime_version": AGENT_RUNTIME_VERSION,
    }


def agent_runtime_catalog(workspace: str | Path | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve() if workspace else None
    history = _agent_history(root) if root else []
    workflows = _workflow_records(root) if root else []
    active = _active_task_index(workflows)
    agents = []
    for agent_id in FORMAL_AGENTS:
        agent = formal_agent(agent_id)
        agent["task_ownership"] = active.get(agent_id, [])
        agent["status"] = "active" if active.get(agent_id) else "idle"
        agent["execution_history"] = _history_for_agent(history, agent_id)
        agents.append(agent)
    coordination_rules = [
        "Every workflow task has one explicit owner agent.",
        "Agents exchange structured records: findings, validation reports, repair recommendations, architecture notes, risk assessments, and summaries.",
        "Handoffs follow dependency order and are persisted in workflow logs/events.",
        "File mutation, validation commands, provider calls, and cloud context remain approval-gated.",
        "Agents receive scoped memory contexts instead of unrestricted workspace context.",
        "Runaway execution is prevented by retry limits, iteration limits, approval gates, and deterministic task ownership.",
    ]
    return {
        "runtime_version": AGENT_RUNTIME_VERSION,
        "workspace": str(root) if root else None,
        "agents": agents,
        "roles": agents,
        "routing_profiles": routing_profiles(),
        "coordination_rules": coordination_rules,
        "rules": coordination_rules,
        "communication_contracts": _communication_contracts(),
        "safety_controls": _agent_safety_controls(),
        "visualization_contracts": ["workflow_graph", "active_agents", "handoff_chain", "execution_timeline", "dependency_graph"],
        "persistence": {
            "agent_history": ".aegis/agent-history.json",
            "workflow_runtime": ".aegis/workflow-runtime.json",
            "workflow_events": ".aegis/workflow-events.json",
        },
        "observability": _runtime_observability(workflows),
    }


def enrich_workflow(root: str | Path, workflow: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(root).resolve()
    workflow["agent_runtime_version"] = AGENT_RUNTIME_VERSION
    workflow["agent_roles"] = [formal_agent(agent_id) for agent_id in FORMAL_AGENTS]
    for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
        if not isinstance(task, dict):
            continue
        agent_id = formal_agent_id(task.get("agent_id") or task.get("agent_role"))
        profile = formal_agent(agent_id)
        task["agent_id"] = agent_id
        task["agent_profile"] = _task_agent_profile(profile)
        task["memory_scope"] = _memory_scope_for_task(workflow, task, profile)
        task["context_policy"] = _context_policy_for_task(workspace, workflow, task, profile)
        task["communication_contract"] = _communication_contract_for_agent(profile)
        task["model_profile"] = _model_profile_for_task(workflow, task, profile)
        task.setdefault("messages", [])
    workflow["agent_coordination"] = coordination_summary(workspace, workflow)
    workflow["agent_observability"] = agent_observability(workflow)
    return workflow


def coordination_summary(root: str | Path, workflow: dict[str, Any]) -> dict[str, Any]:
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    return {
        "workflow_id": workflow.get("id"),
        "dependency_schedule": _dependency_schedule(tasks),
        "handoff_chain": _handoff_chain(tasks),
        "parallel_safe_tasks": _parallel_safe_tasks(tasks),
        "validation_batches": _validation_batches(tasks),
        "approval_checkpoints": _approval_checkpoints(tasks),
        "failure_escalations": workflow.get("failure_escalations", []),
        "context_minimization": {
            "default_scope": "task_specific",
            "cached_workspace_intelligence": ".aegis/workspace-intelligence.json",
            "knowledge_graph": ".aegis/knowledge-graph.json",
            "project_memory": ".aegis/project-memory.json",
        },
        "safety": _agent_safety_controls(),
    }


def workflow_agent_coordination(root: str | Path, workflow: dict[str, Any], events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    workspace = Path(root).resolve()
    enriched = enrich_workflow(workspace, workflow)
    tasks = [task for task in enriched.get("tasks", []) if isinstance(task, dict)]
    architecture = _safe_architecture_summary(workspace)
    context_snapshots = [_task_context_snapshot(workspace, enriched, task, architecture) for task in tasks]
    agents = _agents_for_workflow(tasks)
    return {
        "workspace": str(workspace),
        "project_id": enriched.get("project_id", ""),
        "workflow_id": enriched.get("id"),
        "workflow_type": enriched.get("workflow_type"),
        "active_agents": [agent for agent in agents if agent.get("status") in {"active", "waiting_input"}],
        "agents": agents,
        "task_ownership": _task_ownership(tasks),
        "handoff_chain": _handoff_chain(tasks),
        "workflow_graph": {
            "nodes": [{"id": task.get("id"), "label": task.get("title"), "agent_id": task.get("agent_id"), "status": task.get("status")} for task in tasks],
            "edges": [{"from": dep, "to": task.get("id"), "type": "depends_on"} for task in tasks for dep in task.get("depends_on", [])],
        },
        "dependency_graph": {
            "edges": enriched.get("dependencies", []),
            "parallel_safe_tasks": _parallel_safe_tasks(tasks),
            "validation_batches": _validation_batches(tasks),
        },
        "execution_timeline": events or [],
        "context_snapshots": context_snapshots,
        "communication": _communication_state(tasks),
        "observability": agent_observability(enriched),
        "supervision": _supervision_state(enriched),
        "safety": _agent_safety_controls(),
    }


def delegate_task(workflow: dict[str, Any], *, task_id: str, agent_id: str, reason: str, approval: bool = False, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved_agent_id = formal_agent_id(agent_id)
    task = _find_task(workflow, task_id)
    if task.get("status") in TERMINAL_TASK_STATES:
        raise ValueError("completed, failed, or cancelled tasks cannot be delegated")
    profile = formal_agent(resolved_agent_id)
    reason_text = scrub(reason).strip() or "Task delegated by client."
    requires_approval = resolved_agent_id in MUTATING_AGENT_IDS or bool(task.get("approval_gates"))
    handoff = {
        "timestamp": utc_now(),
        "from_agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
        "to_agent_id": resolved_agent_id,
        "task_id": task.get("id"),
        "reason": reason_text,
        "approval_required": requires_approval,
        "approved": bool(approval),
        "metadata": _safe_metadata(metadata or {}),
    }
    if requires_approval and not approval:
        task["status"] = "waiting_input"
        task["pending_delegation"] = handoff
        _append_agent_message(task, "approval_checkpoint", "Delegation requires approval.", {"handoff": handoff})
    else:
        task["agent_id"] = resolved_agent_id
        task["agent_role"] = profile["role"]
        task["agent_profile"] = _task_agent_profile(profile)
        task["memory_scope"] = _memory_scope_for_task(workflow, task, profile)
        task["context_policy"] = _context_policy_for_task(Path(str(workflow.get("workspace") or ".")).resolve(), workflow, task, profile)
        task["communication_contract"] = _communication_contract_for_agent(profile)
        task["model_profile"] = _model_profile_for_task(workflow, task, profile)
        task.pop("pending_delegation", None)
        if task.get("status") == "waiting_input":
            task["status"] = "queued"
        _append_agent_message(task, "handoff", "Task ownership delegated.", {"handoff": handoff})
    workflow.setdefault("handoffs", []).append(handoff)
    workflow["agent_coordination"] = coordination_summary(Path(str(workflow.get("workspace") or ".")).resolve(), workflow)
    workflow["agent_observability"] = agent_observability(workflow)
    return {"task": task, "handoff": handoff, "workflow": workflow}


def record_agent_message(task: dict[str, Any], message_type: str, summary: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _append_agent_message(task, message_type, summary, payload or {})


def apply_failure_escalation(workflow: dict[str, Any], task: dict[str, Any], summary: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    escalation = {
        "timestamp": utc_now(),
        "workflow_id": workflow.get("id"),
        "task_id": task.get("id"),
        "agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
        "reason": scrub(summary),
        "retry_count": int(task.get("retry_count") or 0),
        "max_retries": int(task.get("max_retries") or 0),
        "payload": _safe_metadata(payload or {}),
        "requires_user_attention": int(task.get("retry_count") or 0) >= int(task.get("max_retries") or 0),
    }
    workflow.setdefault("failure_escalations", []).append(escalation)
    _append_agent_message(task, "failure_escalation", summary, escalation)
    return escalation


def agent_observability(workflow: dict[str, Any]) -> dict[str, Any]:
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    by_agent: dict[str, dict[str, Any]] = {}
    for task in tasks:
        agent_id = str(task.get("agent_id") or formal_agent_id(task.get("agent_role")))
        metrics = by_agent.setdefault(
            agent_id,
            {
                "agent_id": agent_id,
                "owned_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "waiting_tasks": 0,
                "retry_count": 0,
                "validation_successes": 0,
                "validation_failures": 0,
                "repair_successes": 0,
                "repair_failures": 0,
                "escalation_count": 0,
                "model_usage": {},
                "duration_seconds": 0,
            },
        )
        metrics["owned_tasks"] += 1
        status = str(task.get("status") or "")
        if status == "completed":
            metrics["completed_tasks"] += 1
        if status == "failed":
            metrics["failed_tasks"] += 1
        if status == "waiting_input":
            metrics["waiting_tasks"] += 1
        metrics["retry_count"] += int(task.get("retry_count") or 0)
        if task.get("execution_mode") == "validation":
            ok = bool((task.get("result") or {}).get("ok"))
            if status == "completed" and ok:
                metrics["validation_successes"] += 1
            elif status in {"completed", "failed"}:
                metrics["validation_failures"] += 1
        if agent_id == "repair_agent":
            if status == "completed":
                metrics["repair_successes"] += 1
            if status == "failed":
                metrics["repair_failures"] += 1
        route = task.get("model_profile") if isinstance(task.get("model_profile"), dict) else {}
        profile = str(route.get("route_profile") or "unknown")
        metrics["model_usage"][profile] = metrics["model_usage"].get(profile, 0) + 1
    for escalation in workflow.get("failure_escalations", []) if isinstance(workflow.get("failure_escalations"), list) else []:
        agent_id = str(escalation.get("agent_id") or "unknown")
        if agent_id in by_agent:
            by_agent[agent_id]["escalation_count"] += 1
    return {
        "agents": list(by_agent.values()),
        "workflow_ownership": _task_ownership(tasks),
        "handoff_count": len(workflow.get("handoffs", []) if isinstance(workflow.get("handoffs"), list) else []),
        "escalation_frequency": len(workflow.get("failure_escalations", []) if isinstance(workflow.get("failure_escalations"), list) else []),
        "failure_patterns": _failure_patterns(tasks),
        "token_usage": {"tracked": False, "reason": "Provider token accounting is recorded when model providers return usage metadata."},
    }


def append_agent_history(root: str | Path, event: dict[str, Any]) -> None:
    memory = ProjectMemory(root)
    memory.ensure()
    history = _agent_history(Path(root).resolve())
    history.append({"timestamp": utc_now(), **_safe_metadata(event)})
    memory.write_json(AGENT_HISTORY_FILE, history[-1000:])


def _task_agent_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile["id"],
        "role": profile["role"],
        "label": profile["label"],
        "capabilities": profile.get("capabilities", []),
        "supported_workflow_types": profile.get("supported_workflow_types", []),
    }


def _memory_scope_for_task(workflow: dict[str, Any], task: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    scope = str(profile.get("memory_scope") or "task_specific")
    files = _task_files(workflow, task)
    if scope == "workflow":
        files = list(dict.fromkeys([*workflow.get("context_files", []), *files]))[:20]
    elif scope == "dependency_scoped":
        files = files[:16]
    elif scope == "file_scoped":
        files = files[:18]
    else:
        files = files[:10]
    return {
        "scope": scope,
        "files": files,
        "roadmap_scope": workflow.get("metadata", {}).get("roadmap_item_id") if isinstance(workflow.get("metadata"), dict) else None,
        "workflow_memory_snapshot": {
            "workflow_id": workflow.get("id"),
            "workflow_type": workflow.get("workflow_type"),
            "objective": workflow.get("objective"),
        },
    }


def _context_policy_for_task(root: Path, workflow: dict[str, Any], task: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    files = _task_files(workflow, task)
    return {
        "max_context_files": int(profile.get("execution_limits", {}).get("max_context_files") or 0),
        "context_files": files[: int(profile.get("execution_limits", {}).get("max_context_files") or 0) or 0],
        "knowledge_sources": ["architecture_summary", "impact_analysis", "project_memory", "previous_execution_history"],
        "impact_analysis_targets": files[:5],
        "dependency_scope": "direct_and_second_order" if files else "workflow",
        "redaction": "secret-like and unsafe files are excluded before provider context",
        "workspace": str(root),
    }


def _communication_contract_for_agent(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "structured_agent_message",
        "allowed_message_types": profile.get("communication_outputs", []),
        "required_fields": ["type", "summary", "created_at", "payload"],
        "freeform_agent_chat": False,
    }


def _model_profile_for_task(workflow: dict[str, Any], task: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    base = dict(profile.get("preferred_model_profile", {}))
    base["workflow_type"] = workflow.get("workflow_type")
    base["task_key"] = task.get("key")
    base["fallback_chain_policy"] = "local_first_then_approved_profile_fallback"
    base["clients_should_route_through"] = "/v1/models/route"
    return base


def _task_context_snapshot(root: Path, workflow: dict[str, Any], task: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    files = _task_files(workflow, task)
    impacts = []
    for target in files[:3]:
        try:
            impacts.append(impact_analysis(root, target, persist=False, limit=25))
        except Exception as exc:  # pragma: no cover - defensive best-effort context.
            impacts.append({"target": target, "error": scrub(str(exc))})
    return {
        "task_id": task.get("id"),
        "agent_id": task.get("agent_id"),
        "memory_scope": task.get("memory_scope", {}),
        "architecture_summary": {
            "frameworks": architecture.get("summary", {}).get("frameworks", []),
            "runtime_boundaries": architecture.get("runtime_boundaries", [])[:10],
            "risk_areas": architecture.get("risk_areas", [])[:10],
        },
        "impact_analysis": impacts,
        "project_memory": {"path": ".aegis/project-memory.json", "scope": "summary"},
        "previous_execution_history": {"path": ".aegis/agent-history.json", "scope": task.get("agent_id")},
    }


def _safe_architecture_summary(root: Path) -> dict[str, Any]:
    try:
        return architecture_summary(root, refresh=False)
    except Exception as exc:  # pragma: no cover - defensive dashboard path.
        return {"summary": {}, "error": scrub(str(exc))}


def _agents_for_workflow(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agents = []
    for agent_id in FORMAL_AGENTS:
        owned = [task for task in tasks if task.get("agent_id") == agent_id]
        active = [task for task in owned if task.get("status") in {"running", "validating", "repairing", "waiting_input", "queued"}]
        profile = formal_agent(agent_id)
        profile["task_ownership"] = [{"task_id": task.get("id"), "title": task.get("title"), "status": task.get("status")} for task in owned]
        profile["status"] = "waiting_input" if any(task.get("status") == "waiting_input" for task in owned) else "active" if active else "idle"
        profile["execution_history"] = [
            message
            for task in owned
            for message in task.get("messages", []) if isinstance(task.get("messages"), list)
        ][-20:]
        agents.append(profile)
    return agents


def _task_ownership(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ownership: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        agent_id = str(task.get("agent_id") or formal_agent_id(task.get("agent_role")))
        ownership.setdefault(agent_id, []).append({"task_id": task.get("id"), "key": task.get("key"), "status": task.get("status")})
    return ownership


def _handoff_chain(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {task.get("id"): task for task in tasks}
    chain = []
    for task in sorted(tasks, key=lambda item: int(item.get("order") or 0)):
        for dep in task.get("depends_on", []) if isinstance(task.get("depends_on"), list) else []:
            source = by_id.get(dep)
            if source:
                chain.append(
                    {
                        "from_task_id": dep,
                        "from_agent_id": source.get("agent_id") or formal_agent_id(source.get("agent_role")),
                        "to_task_id": task.get("id"),
                        "to_agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
                        "requires_validation": task.get("execution_mode") in {"validation", "apply"},
                        "approval_gates": task.get("approval_gates", []),
                    }
                )
    return chain


def _dependency_schedule(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": task.get("id"),
            "order": task.get("order"),
            "agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
            "depends_on": task.get("depends_on", []),
            "status": task.get("status"),
        }
        for task in sorted(tasks, key=lambda item: int(item.get("order") or 0))
    ]


def _parallel_safe_tasks(tasks: list[dict[str, Any]]) -> list[list[str]]:
    queued = [task for task in tasks if task.get("status") in {"queued", "pending"} and not task.get("approval_gates")]
    groups: list[list[str]] = []
    used: set[str] = set()
    for task in queued:
        task_id = str(task.get("id") or "")
        if not task_id or task_id in used:
            continue
        files = set(_task_files({}, task))
        group = [task_id]
        used.add(task_id)
        for other in queued:
            other_id = str(other.get("id") or "")
            if not other_id or other_id in used:
                continue
            if set(other.get("depends_on", [])).intersection(group):
                continue
            if files.intersection(_task_files({}, other)):
                continue
            group.append(other_id)
            used.add(other_id)
        if len(group) > 1:
            groups.append(group)
    return groups


def _validation_batches(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validation_tasks = [task for task in tasks if task.get("execution_mode") == "validation"]
    return [
        {
            "batch_id": f"validation-batch-{index}",
            "task_ids": [task.get("id")],
            "agent_id": task.get("agent_id"),
            "approval_required": bool(task.get("approval_gates")),
        }
        for index, task in enumerate(validation_tasks, start=1)
    ]


def _approval_checkpoints(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": task.get("id"),
            "agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
            "gates": task.get("approval_gates", []),
            "status": task.get("status"),
        }
        for task in tasks
        if task.get("approval_gates")
    ]


def _communication_state(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [message for task in tasks for message in task.get("messages", []) if isinstance(task.get("messages"), list)]
    return {
        "message_count": len(messages),
        "messages": messages[-100:],
        "freeform_agent_chat": False,
        "supported_types": sorted({item for agent in FORMAL_AGENTS.values() for item in agent.get("communication_outputs", [])}),
    }


def _supervision_state(workflow: dict[str, Any]) -> dict[str, Any]:
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    return {
        "approval_gates": _approval_checkpoints(tasks),
        "retry_limits": [{"task_id": task.get("id"), "retry_count": task.get("retry_count", 0), "max_retries": task.get("max_retries", 0)} for task in tasks],
        "validation_before_handoff": True,
        "repair_escalation": workflow.get("failure_escalations", []),
        "unsafe_operation_blocking": _agent_safety_controls()["blocked_operations"],
        "runaway_execution_prevention": _agent_safety_controls()["runaway_prevention"],
    }


def _append_agent_message(task: dict[str, Any], message_type: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    message = {
        "id": f"agent-msg-{len(task.get('messages', []) if isinstance(task.get('messages'), list) else []) + 1}",
        "type": scrub(message_type),
        "agent_id": task.get("agent_id") or formal_agent_id(task.get("agent_role")),
        "task_id": task.get("id"),
        "summary": scrub(summary),
        "created_at": utc_now(),
        "payload": _safe_metadata(payload),
    }
    task.setdefault("messages", []).append(message)
    task["messages"] = task["messages"][-100:]
    return message


def _task_files(workflow: dict[str, Any], task: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for source in (workflow.get("context_files", []), task.get("affected_files", []), task.get("context_files", [])):
        if isinstance(source, list):
            for item in source:
                value = str(item).replace("\\", "/").strip()
                if value and value not in files:
                    files.append(value)
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    for key in ("affected_files", "files", "target_files"):
        values = result.get(key) if isinstance(result, dict) else []
        if isinstance(values, list):
            for item in values:
                value = str(item).replace("\\", "/").strip()
                if value and value not in files:
                    files.append(value)
    return files


def _find_task(workflow: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
        if isinstance(task, dict) and task.get("id") == task_id:
            return task
    raise ValueError(f"task not found: {task_id}")


def _agent_history(root: Path | None) -> list[dict[str, Any]]:
    if root is None:
        return []
    path = ProjectMemory(root).root / AGENT_HISTORY_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _workflow_records(root: Path | None) -> list[dict[str, Any]]:
    if root is None:
        return []
    path = ProjectMemory(root).root / WORKFLOWS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _active_task_index(workflows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for workflow in workflows:
        if workflow.get("status") in {"completed", "failed", "cancelled"}:
            continue
        for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            agent_id = str(task.get("agent_id") or formal_agent_id(task.get("agent_role")))
            if task.get("status") in {"queued", "running", "waiting_input", "validating", "repairing"}:
                index.setdefault(agent_id, []).append({"workflow_id": workflow.get("id"), "task_id": task.get("id"), "status": task.get("status")})
    return index


def _history_for_agent(history: list[dict[str, Any]], agent_id: str) -> list[dict[str, Any]]:
    role = FORMAL_AGENTS[agent_id]["role"]
    matches = [
        item
        for item in history
        if str(item.get("agent_id") or "").lower() in {agent_id, role}
    ]
    return matches[-20:]


def _runtime_observability(workflows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [workflow for workflow in workflows if workflow.get("status") not in {"completed", "failed", "cancelled"}]
    escalations = sum(len(workflow.get("failure_escalations", []) if isinstance(workflow.get("failure_escalations"), list) else []) for workflow in workflows)
    handoffs = sum(len(workflow.get("handoffs", []) if isinstance(workflow.get("handoffs"), list) else []) for workflow in workflows)
    return {
        "workflow_count": len(workflows),
        "active_workflow_count": len(active),
        "handoff_count": handoffs,
        "escalation_count": escalations,
    }


def _communication_contracts() -> dict[str, Any]:
    return {
        "message_shape": {"type": "string", "summary": "string", "created_at": "iso8601", "payload": "object"},
        "allowed_outputs": sorted({item for agent in FORMAL_AGENTS.values() for item in agent.get("communication_outputs", [])}),
        "freeform_agent_chat": False,
    }


def _agent_safety_controls() -> dict[str, Any]:
    return {
        "approval_required_for": ["file_edit", "file_delete", "validation_command", "provider_call", "cloud_context", "agent_reassignment_to_mutating_role"],
        "blocked_operations": ["unbounded_agent_spawn", "recursive_workflow_creation", "unapproved_apply", "unapproved_cloud_context", "unsafe_path_modification"],
        "runaway_prevention": {"max_autonomous_iterations": 3, "max_retries_per_task": 2, "max_agents_per_workflow": len(FORMAL_AGENTS), "recursive_spawning": False},
        "audit_history": ".aegis/workflow-audit.md",
    }


def _failure_patterns(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns: dict[str, int] = {}
    for task in tasks:
        if task.get("status") == "failed":
            key = str(task.get("execution_mode") or task.get("agent_id") or "unknown")
            patterns[key] = patterns.get(key, 0) + 1
    return [{"pattern": key, "count": value} for key, value in sorted(patterns.items())]


def _safe_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {scrub(str(k)): _safe_metadata(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value[:100]]
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return scrub(str(value))
