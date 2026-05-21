from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import agent_runtime
from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .personal_memory import memory_orchestration_context
from .safety import is_safe_to_read
from .validation import run_validation, validation_summary
from .workspace_intelligence import workspace_intelligence


WORKFLOWS_FILE = "workflow-runtime.json"
EVENTS_FILE = "workflow-events.json"
CLIENT_SYNC_FILE = "client-sync.json"
AUDIT_FILE = "workflow-audit.md"
MAX_WORKFLOWS = 100
MAX_EVENTS = 1000
MAX_LOGS_PER_WORKFLOW = 300

TASK_STATES = {
    "pending",
    "queued",
    "running",
    "waiting_input",
    "validating",
    "repairing",
    "completed",
    "failed",
    "cancelled",
}
WORKFLOW_STATES = TASK_STATES | {"paused"}
WORKFLOW_TYPES = {
    "chat_request",
    "generate_feature",
    "validate_project",
    "repair_project",
    "continue_roadmap",
    "build_project",
    "scan_workspace",
    "benchmark_models",
    "generate_media",
    "research_task",
}
AGENT_ROLES = {
    "planner": {
        "label": "Planner",
        "purpose": "Break goals into deterministic, inspectable workflow tasks.",
    },
    "coder": {
        "label": "Coder",
        "purpose": "Coordinate proposed code changes and hand off approved writes to Core editing contracts.",
    },
    "validator": {
        "label": "Validator",
        "purpose": "Detect and run approved validation commands with captured results.",
    },
    "repair_agent": {
        "label": "Repair Agent",
        "purpose": "Track validation failures and bounded repair attempts without unapproved mutation.",
    },
    "researcher": {
        "label": "Researcher",
        "purpose": "Structure research tasks and record findings supplied by a client or approved provider.",
    },
    "summarizer": {
        "label": "Summarizer",
        "purpose": "Produce final workflow summaries, metrics, and memory notes.",
    },
}
DEFAULT_SAFETY_CONTROLS = {
    "approval_gates": {
        "file_edit": "File edits require explicit client/user approval.",
        "file_delete": "File deletion requires explicit client/user approval.",
        "validation_command": "Build/test/lint commands require approval before execution.",
        "provider_call": "Provider-backed model/media/research execution requires explicit approval.",
    },
    "max_file_modifications": 25,
    "max_autonomous_iterations": 3,
    "validation_required_before_apply": True,
    "restricted_path_rules": [
        "Paths must stay inside the workspace.",
        "Secret-like paths are rejected by editing contracts.",
        "Ignored generated, dependency, hidden, and VCS folders are not editable workflow targets.",
    ],
}


class WorkflowPersistenceError(RuntimeError):
    """Raised when Core workflow runtime state cannot be persisted."""


class WorkflowNotFoundError(KeyError):
    """Raised when a workflow id is not available in workspace state."""


def agent_runtime_catalog() -> dict[str, Any]:
    return agent_runtime.agent_runtime_catalog()


def create_workflow(
    workspace: str | Path,
    workflow_type: str,
    objective: str,
    *,
    source_client: str = "unknown",
    context_files: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    workflow_type = _normalize_workflow_type(workflow_type)
    objective = scrub(objective).strip()
    if not objective:
        raise ValueError("workflow objective is required")

    context = _safe_context_files(root, context_files or [])
    now = utc_now()
    workflow_id = f"workflow-{uuid.uuid4().hex[:12]}"
    task_specs = _workflow_template(workflow_type)
    tasks = _materialize_tasks(task_specs, workflow_id, now)
    memory_context = _workflow_memory_context(root, workflow_type, objective)
    workflow = {
        "id": workflow_id,
        "project_id": _project_id(root),
        "workspace": str(root),
        "workflow_type": workflow_type,
        "objective": objective,
        "source_client": source_client or "unknown",
        "status": "queued",
        "progress": 0,
        "active_task_id": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "context_files": context["included"],
        "blocked_context": context["blocked"],
        "tasks": tasks,
        "dependencies": _dependency_edges(tasks),
        "logs": [],
        "metrics": _empty_metrics(),
        "safety": DEFAULT_SAFETY_CONTROLS,
        "agent_roles": agent_runtime_catalog()["roles"],
        "personal_memory_context": memory_context,
        "metadata": _safe_metadata(metadata or {}),
    }
    agent_runtime.enrich_workflow(root, workflow)
    _refresh_workflow_state(workflow)
    memory = _memory(root)
    workflows = _load_workflows(memory)
    workflows = [item for item in workflows if item.get("id") != workflow_id]
    workflows.append(workflow)
    _write_workflows(memory, workflows)
    _append_workflow_log(workflow, "workflow.created", f"Created {workflow_type} workflow.")
    _persist_workflow(memory, workflow)
    _record_event(memory, workflow, "workflow.created", f"Created {workflow_type} workflow.", {"source_client": source_client})
    _append_audit(memory, workflow, "workflow.created", objective)
    return workflow_dashboard(root, workflow_id)


def list_workflows(workspace: str | Path, *, include_completed: bool = True, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflows = _load_workflows(memory)
    if not include_completed:
        workflows = [item for item in workflows if item.get("status") not in {"completed", "failed", "cancelled"}]
    max_items = max(1, min(200, int(limit)))
    workflows = sorted(workflows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:max_items]
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "workflows": workflows,
        "active_workflows": [item for item in workflows if item.get("status") not in {"completed", "failed", "cancelled"}],
    }


def _workflow_memory_context(root: Path, workflow_type: str, objective: str) -> dict[str, Any]:
    try:
        context = memory_orchestration_context(
            root,
            workflow_type=workflow_type,
            objective=objective,
            max_items=12,
            record_usage=True,
        )
    except Exception as exc:  # pragma: no cover - memory should not block workflow creation.
        return {
            "records": [],
            "guidance": [],
            "error": scrub(str(exc)),
            "used": False,
        }
    return {
        "records": context.get("records", []),
        "guidance": context.get("guidance", []),
        "privacy": context.get("privacy", {}),
        "latency_ms": context.get("latency_ms", 0),
        "used": bool(context.get("records")),
    }


def workflow_dashboard(workspace: str | Path, workflow_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflow = _get_workflow(memory, workflow_id)
    timeline = _workflow_timeline(memory, workflow_id)
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "workflow": workflow,
        "timeline": timeline,
        "statistics": workflow_statistics(root),
        "agent_runtime": agent_runtime.agent_runtime_catalog(root),
        "agent_coordination": agent_runtime.workflow_agent_coordination(root, workflow, timeline),
    }


def workflow_agent_dashboard(workspace: str | Path, workflow_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflow = _get_workflow(memory, workflow_id)
    data = agent_runtime.workflow_agent_coordination(root, workflow, _workflow_timeline(memory, workflow_id))
    data["runtime"] = agent_runtime.agent_runtime_catalog(root)
    return data


def step_workflow(
    workspace: str | Path,
    workflow_id: str,
    *,
    action: str = "advance",
    task_id: str | None = None,
    approval: bool = False,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflow = _get_workflow(memory, workflow_id)
    payload = _safe_metadata(payload or {})
    action_name = _normalize_action(action)
    if workflow.get("status") in {"cancelled", "completed"} and action_name not in {"record_log"}:
        raise ValueError(f"workflow is already {workflow.get('status')}")
    if workflow.get("status") == "paused" and action_name not in {"resume", "cancel", "record_log"}:
        raise ValueError("workflow is paused")

    if action_name == "pause":
        _set_workflow_status(workflow, "paused", summary or "Workflow paused.")
    elif action_name == "resume":
        _set_workflow_status(workflow, "queued", summary or "Workflow resumed.")
        _refresh_workflow_state(workflow)
    elif action_name == "cancel":
        _cancel_workflow(workflow, summary or "Workflow cancelled.")
    elif action_name == "retry_task":
        task = _require_task(workflow, task_id)
        _retry_task(task)
    elif action_name == "delegate_task":
        if not task_id:
            raise ValueError("task_id is required")
        target_agent = str(payload.get("agent_id") or payload.get("target_agent_id") or "")
        if not target_agent:
            raise ValueError("agent_id is required for task delegation")
        result = agent_runtime.delegate_task(
            workflow,
            task_id=task_id,
            agent_id=target_agent,
            reason=summary or str(payload.get("reason") or "Task delegated."),
            approval=approval,
            metadata=payload,
        )
        task = result["task"]
    elif action_name == "record_log":
        _append_workflow_log(workflow, "workflow.log", summary or "Client log recorded.", payload=payload)
    elif action_name == "fail_task":
        task = _require_task(workflow, task_id)
        _fail_task(workflow, task, summary or "Task failed.", payload)
    elif action_name == "complete_task":
        task = _require_task(workflow, task_id)
        _complete_task(workflow, task, summary or "Task completed.", payload)
    else:
        task = _select_task(workflow, task_id)
        _run_task(root, workflow, task, approval=approval, summary=summary, payload=payload)

    agent_runtime.enrich_workflow(root, workflow)
    _refresh_workflow_state(workflow)
    _persist_workflow(memory, workflow)
    event = _record_event(
        memory,
        workflow,
        f"workflow.{action_name}",
        summary or f"Workflow action `{action_name}` recorded.",
        {"task_id": task_id or workflow.get("active_task_id"), "approval": approval, "payload": payload},
    )
    _append_audit(memory, workflow, f"workflow.{action_name}", summary or "")
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "workflow": workflow,
        "event": event,
        "timeline": _workflow_timeline(memory, workflow_id),
    }


def pause_workflow(workspace: str | Path, workflow_id: str, *, summary: str = "") -> dict[str, Any]:
    return step_workflow(workspace, workflow_id, action="pause", summary=summary or "Workflow paused.")


def resume_workflow(workspace: str | Path, workflow_id: str, *, summary: str = "") -> dict[str, Any]:
    return step_workflow(workspace, workflow_id, action="resume", summary=summary or "Workflow resumed.")


def cancel_workflow(workspace: str | Path, workflow_id: str, *, summary: str = "") -> dict[str, Any]:
    return step_workflow(workspace, workflow_id, action="cancel", summary=summary or "Workflow cancelled.")


def retry_workflow_task(workspace: str | Path, workflow_id: str, *, task_id: str, summary: str = "") -> dict[str, Any]:
    return step_workflow(workspace, workflow_id, action="retry_task", task_id=task_id, summary=summary or "Task queued for retry.")


def sync_client(
    workspace: str | Path,
    *,
    client_id: str,
    client_type: str,
    name: str,
    version: str = "unknown",
    capabilities: list[str] | None = None,
    active_workflow_id: str | None = None,
    status: str = "active",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    clients = _load_client_sync(memory)
    now = utc_now()
    record = {
        "client_id": str(client_id or "").strip() or "unknown-client",
        "client_type": str(client_type or "unknown").strip() or "unknown",
        "name": str(name or client_id or "Unknown Client").strip() or "Unknown Client",
        "version": str(version or "unknown").strip() or "unknown",
        "workspace": str(root),
        "project_id": _project_id(root),
        "capabilities": [str(item).strip() for item in capabilities or [] if str(item).strip()],
        "active_workflow_id": active_workflow_id,
        "status": str(status or "active"),
        "metadata": _safe_metadata(metadata or {}),
        "last_seen": now,
    }
    clients = [item for item in clients if item.get("client_id") != record["client_id"]]
    clients.append(record)
    _write_client_sync(memory, clients)
    event = _record_event(
        memory,
        {"id": active_workflow_id, "project_id": _project_id(root), "workspace": str(root), "workflow_type": "client_sync"},
        "client.synced",
        f"Client {record['client_id']} synced.",
        {"client_id": record["client_id"], "active_workflow_id": active_workflow_id},
    )
    return {"workspace": str(root), "project_id": _project_id(root), "client": record, "event": event}


def sync_dashboard(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflows = list_workflows(root, include_completed=False, limit=limit)
    events = _load_events(memory)
    clients = sorted(_load_client_sync(memory), key=lambda item: str(item.get("last_seen") or ""), reverse=True)
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "active_clients": clients,
        "active_workflows": workflows.get("active_workflows", []),
        "recent_operations": events[: max(1, min(200, int(limit)))],
        "workspace_activity_feed": events[: max(1, min(200, int(limit)))],
    }


def workflow_statistics(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    workflows = _load_workflows(memory)
    events = _load_events(memory)
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    durations: list[float] = []
    validation_runs = 0
    validation_passes = 0
    repair_attempts = 0
    repair_successes = 0
    model_usage: dict[str, int] = {}
    for workflow in workflows:
        status = str(workflow.get("status") or "unknown")
        workflow_type = str(workflow.get("workflow_type") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts[workflow_type] = type_counts.get(workflow_type, 0) + 1
        duration = _duration_seconds(workflow.get("started_at"), workflow.get("finished_at") or workflow.get("updated_at"))
        if duration is not None:
            durations.append(duration)
        for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            if task.get("execution_mode") == "validation":
                validation_runs += int(bool(task.get("result")))
                validation_passes += int(bool((task.get("result") or {}).get("ok")))
            if task.get("agent_role") == "repair_agent":
                repair_attempts += int(task.get("retry_count") or 0)
                if task.get("status") == "completed":
                    repair_successes += 1
            model = (task.get("result") or {}).get("model") if isinstance(task.get("result"), dict) else None
            if model:
                model_usage[str(model)] = model_usage.get(str(model), 0) + 1
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "workflow_count": len(workflows),
        "active_workflow_count": sum(1 for item in workflows if item.get("status") not in {"completed", "failed", "cancelled"}),
        "status_counts": status_counts,
        "workflow_type_counts": type_counts,
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
        "model_usage": model_usage,
        "agent_observability": _aggregate_agent_observability(workflows),
        "event_count": len(events),
        "recent_events": events[:25],
    }


def event_stream(
    workspace: str | Path,
    *,
    workflow_id: str | None = None,
    since: int = 0,
    limit: int = 100,
    follow: bool = False,
    max_seconds: int = 30,
) -> Iterable[str]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    started = time.time()
    emitted = 0
    seen: set[str] = set()
    while True:
        events = _load_events(memory)
        if workflow_id:
            events = [event for event in events if event.get("workflow_id") == workflow_id]
        events = list(reversed(events))
        for index, event in enumerate(events):
            if index < since:
                continue
            event_id = str(event.get("id") or "")
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            emitted += 1
            yield _sse("workflow_event", event)
            if emitted >= max(1, min(500, int(limit))):
                return
        if not follow:
            return
        if time.time() - started >= max(1, min(120, int(max_seconds))):
            yield _sse("heartbeat", {"timestamp": utc_now(), "message": "stream timeout"})
            return
        time.sleep(1)


def _run_task(root: Path, workflow: dict[str, Any], task: dict[str, Any], *, approval: bool, summary: str | None, payload: dict[str, Any]) -> None:
    if task.get("status") in {"completed", "cancelled"}:
        return
    now = utc_now()
    workflow["started_at"] = workflow.get("started_at") or now
    mode = task.get("execution_mode") or "manual"
    gates = task.get("approval_gates") if isinstance(task.get("approval_gates"), list) else []
    if gates and not approval and mode in {"validation", "provider", "apply"}:
        task["status"] = "waiting_input"
        task["updated_at"] = now
        agent_runtime.record_agent_message(task, "approval_checkpoint", summary or f"Approval required for {', '.join(gates)}.", {"approval_gates": gates})
        _append_task_log(task, "waiting_input", summary or f"Approval required for {', '.join(gates)}.")
        _append_workflow_log(workflow, "task.waiting_input", summary or f"Task `{task['id']}` is waiting for approval.", {"task_id": task["id"]})
        return

    task["status"] = "validating" if mode == "validation" else "running"
    task["started_at"] = task.get("started_at") or now
    task["updated_at"] = now
    agent_runtime.record_agent_message(task, "task_started", summary or f"Agent started `{task.get('key')}`.", {"execution_mode": mode})
    if mode == "workspace_scan":
        result = workspace_intelligence(root, persist=True, refresh=bool(payload.get("refresh", False)))
        _complete_task(workflow, task, summary or "Workspace intelligence refreshed.", {"intelligence": _compact_intelligence_result(result)})
    elif mode == "validation":
        result = run_validation(root, command=payload.get("command"), timeout=int(payload.get("timeout_seconds") or 120))
        _complete_task(workflow, task, summary or ("Validation passed." if result.get("ok") else "Validation failed."), result)
        if not result.get("ok"):
            workflow["status"] = "repairing"
            _queue_repair_tasks(workflow)
    elif mode == "roadmap":
        from .roadmap import generate_roadmap

        result = generate_roadmap(root, persist=True)
        _complete_task(workflow, task, summary or "Roadmap refreshed.", {"roadmap_path": result.get("roadmap_path"), "task_count": len(result.get("tasks", []))})
    elif mode == "manual":
        if payload.get("complete"):
            _complete_task(workflow, task, summary or "Manual/client task completed.", payload)
        else:
            task["status"] = "waiting_input"
            task["updated_at"] = utc_now()
            agent_runtime.record_agent_message(task, "waiting_input", summary or "Task requires client/user input.", payload)
            _append_task_log(task, "waiting_input", summary or "Task requires client/user input.")
    elif mode in {"provider", "media", "research", "benchmark", "apply"}:
        task["status"] = "waiting_input"
        task["updated_at"] = utc_now()
        agent_runtime.record_agent_message(task, "approval_checkpoint", summary or f"`{mode}` execution is delegated until a client supplies approved results.", {"execution_mode": mode})
        _append_task_log(task, "waiting_input", summary or f"`{mode}` execution is delegated until a client supplies approved results.")
    else:
        _complete_task(workflow, task, summary or "Task completed.", payload)


def _workflow_template(workflow_type: str) -> list[dict[str, Any]]:
    templates: dict[str, list[dict[str, Any]]] = {
        "chat_request": [
            _spec("plan", "Understand chat request", "planner", "manual"),
            _spec("respond", "Produce response", "summarizer", "provider", ["provider_call"], ["plan"]),
            _spec("summarize", "Record conversation summary", "summarizer", "manual", depends_on=["respond"]),
        ],
        "generate_feature": [
            _spec("plan", "Plan feature scope", "planner", "workspace_scan"),
            _spec("propose_changes", "Prepare proposed code changes", "coder", "manual", ["file_edit"], ["plan"]),
            _spec("apply_changes", "Apply approved changes through Core editing", "coder", "apply", ["file_edit"], ["propose_changes"]),
            _spec("validate", "Run approved project validation", "validator", "validation", ["validation_command"], ["apply_changes"]),
            _spec("repair", "Track bounded repair attempt", "repair_agent", "manual", ["file_edit"], ["validate"]),
            _spec("summarize", "Summarize feature workflow", "summarizer", "manual", depends_on=["validate"]),
        ],
        "validate_project": [
            _spec("inspect", "Inspect validation paths", "planner", "workspace_scan"),
            _spec("validate", "Run approved validation command", "validator", "validation", ["validation_command"], ["inspect"]),
            _spec("summarize", "Summarize validation result", "summarizer", "manual", depends_on=["validate"]),
        ],
        "repair_project": [
            _spec("inspect_failure", "Inspect latest validation failure", "repair_agent", "workspace_scan"),
            _spec("propose_repair", "Prepare repair proposal", "repair_agent", "manual", ["file_edit"], ["inspect_failure"]),
            _spec("apply_repair", "Apply approved repair through Core editing", "coder", "apply", ["file_edit"], ["propose_repair"]),
            _spec("validate_repair", "Validate repair result", "validator", "validation", ["validation_command"], ["apply_repair"]),
            _spec("summarize", "Summarize repair workflow", "summarizer", "manual", depends_on=["validate_repair"]),
        ],
        "continue_roadmap": [
            _spec("scan", "Refresh workspace intelligence", "planner", "workspace_scan"),
            _spec("roadmap", "Refresh roadmap", "planner", "roadmap", depends_on=["scan"]),
            _spec("choose_next", "Select next roadmap task", "planner", "manual", depends_on=["roadmap"]),
            _spec("summarize", "Summarize continuation plan", "summarizer", "manual", depends_on=["choose_next"]),
        ],
        "build_project": [
            _spec("inspect", "Inspect build system", "planner", "workspace_scan"),
            _spec("build", "Run approved build command", "validator", "validation", ["validation_command"], ["inspect"]),
            _spec("summarize", "Summarize build result", "summarizer", "manual", depends_on=["build"]),
        ],
        "scan_workspace": [
            _spec("scan", "Refresh workspace intelligence", "planner", "workspace_scan"),
            _spec("summarize", "Summarize workspace intelligence", "summarizer", "manual", depends_on=["scan"]),
        ],
        "benchmark_models": [
            _spec("plan", "Plan model benchmark", "planner", "manual"),
            _spec("run_benchmark", "Record approved benchmark results", "validator", "benchmark", ["provider_call"], ["plan"]),
            _spec("summarize", "Summarize benchmark", "summarizer", "manual", depends_on=["run_benchmark"]),
        ],
        "generate_media": [
            _spec("plan", "Plan media generation", "planner", "manual"),
            _spec("generate", "Record approved media generation result", "coder", "media", ["provider_call"], ["plan"]),
            _spec("summarize", "Summarize media workflow", "summarizer", "manual", depends_on=["generate"]),
        ],
        "research_task": [
            _spec("plan", "Define research questions", "researcher", "manual"),
            _spec("collect", "Collect approved research findings", "researcher", "research", ["provider_call"], ["plan"]),
            _spec("summarize", "Summarize research", "summarizer", "manual", depends_on=["collect"]),
        ],
    }
    return templates[workflow_type]


def _spec(
    key: str,
    title: str,
    agent_role: str,
    execution_mode: str,
    approval_gates: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "agent_role": agent_role,
        "execution_mode": execution_mode,
        "approval_gates": approval_gates or [],
        "depends_on": depends_on or [],
    }


def _materialize_tasks(specs: list[dict[str, Any]], workflow_id: str, now: str) -> list[dict[str, Any]]:
    key_to_id = {spec["key"]: f"task-{uuid.uuid4().hex[:12]}" for spec in specs}
    tasks: list[dict[str, Any]] = []
    for order, spec in enumerate(specs, start=1):
        deps = [key_to_id[key] for key in spec.get("depends_on", []) if key in key_to_id]
        parent_id = deps[0] if deps else None
        tasks.append(
            {
                "id": key_to_id[spec["key"]],
                "workflow_id": workflow_id,
                "key": spec["key"],
                "title": spec["title"],
                "status": "pending",
                "order": order,
                "parent_id": parent_id,
                "child_task_ids": [],
                "depends_on": deps,
                "dependents": [],
                "agent_role": spec["agent_role"],
                "execution_mode": spec["execution_mode"],
                "approval_gates": spec.get("approval_gates", []),
                "progress": 0,
                "retry_count": 0,
                "max_retries": 2 if spec["agent_role"] in {"validator", "repair_agent"} else 1,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "finished_at": None,
                "logs": [],
                "result": {},
                "error": None,
            }
        )
    by_id = {task["id"]: task for task in tasks}
    for task in tasks:
        for dep in task["depends_on"]:
            if dep in by_id:
                by_id[dep]["dependents"].append(task["id"])
                by_id[dep]["child_task_ids"].append(task["id"])
    for task in tasks:
        if not task["depends_on"]:
            task["status"] = "queued"
    return tasks


def _refresh_workflow_state(workflow: dict[str, Any]) -> None:
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    by_id = {task["id"]: task for task in tasks if task.get("id")}
    for task in tasks:
        if task.get("status") == "pending" and all(by_id.get(dep, {}).get("status") == "completed" for dep in task.get("depends_on", [])):
            task["status"] = "queued"
            task["updated_at"] = utc_now()
    completed = sum(1 for task in tasks if task.get("status") == "completed")
    total = len(tasks) or 1
    workflow["progress"] = int((completed / total) * 100)
    active = next((task for task in tasks if task.get("status") in {"running", "validating", "repairing", "waiting_input"}), None)
    if active is None:
        active = next((task for task in tasks if task.get("status") == "queued"), None)
    workflow["active_task_id"] = active.get("id") if active else None
    if workflow.get("status") not in {"paused", "cancelled", "failed", "completed"}:
        if all(task.get("status") == "completed" for task in tasks):
            workflow["status"] = "completed"
            workflow["finished_at"] = workflow.get("finished_at") or utc_now()
        elif any(task.get("status") == "failed" for task in tasks):
            workflow["status"] = "failed"
        elif any(task.get("status") == "repairing" for task in tasks) or workflow.get("status") == "repairing":
            workflow["status"] = "repairing"
        elif any(task.get("status") == "validating" for task in tasks):
            workflow["status"] = "validating"
        elif any(task.get("status") == "waiting_input" for task in tasks):
            workflow["status"] = "waiting_input"
        elif any(task.get("status") == "running" for task in tasks):
            workflow["status"] = "running"
        else:
            workflow["status"] = "queued"
    workflow["updated_at"] = utc_now()
    workflow["metrics"] = _workflow_metrics(workflow)
    workflow["agent_observability"] = agent_runtime.agent_observability(workflow)


def _complete_task(workflow: dict[str, Any], task: dict[str, Any], summary: str, result: dict[str, Any]) -> None:
    task["status"] = "completed"
    task["progress"] = 100
    task["result"] = _safe_metadata(result)
    task["updated_at"] = utc_now()
    task["finished_at"] = utc_now()
    agent_runtime.record_agent_message(task, "structured_result", summary, result)
    _append_task_log(task, "completed", summary, result)
    _append_workflow_log(workflow, "task.completed", summary, {"task_id": task["id"], "result": _safe_metadata(result)})


def _fail_task(workflow: dict[str, Any], task: dict[str, Any], summary: str, payload: dict[str, Any]) -> None:
    task["status"] = "failed"
    task["error"] = scrub(summary)
    task["updated_at"] = utc_now()
    task["finished_at"] = utc_now()
    task["result"] = _safe_metadata(payload)
    agent_runtime.apply_failure_escalation(workflow, task, summary, payload)
    _append_task_log(task, "failed", summary, payload)
    _append_workflow_log(workflow, "task.failed", summary, {"task_id": task["id"], "payload": payload})


def _retry_task(task: dict[str, Any]) -> None:
    retries = int(task.get("retry_count") or 0)
    max_retries = int(task.get("max_retries") or 0)
    if retries >= max_retries:
        raise ValueError("task retry limit reached")
    if task.get("status") not in {"failed", "waiting_input", "cancelled"}:
        raise ValueError("only failed, cancelled, or waiting_input tasks can be retried")
    task["retry_count"] = retries + 1
    task["status"] = "queued"
    task["progress"] = 0
    task["error"] = None
    task["updated_at"] = utc_now()
    task["finished_at"] = None
    _append_task_log(task, "retried", "Task queued for retry.")


def _cancel_workflow(workflow: dict[str, Any], summary: str) -> None:
    for task in workflow.get("tasks", []):
        if isinstance(task, dict) and task.get("status") not in {"completed", "failed", "cancelled"}:
            task["status"] = "cancelled"
            task["updated_at"] = utc_now()
            _append_task_log(task, "cancelled", summary)
    _set_workflow_status(workflow, "cancelled", summary)


def _set_workflow_status(workflow: dict[str, Any], status: str, summary: str) -> None:
    if status not in WORKFLOW_STATES:
        raise ValueError(f"unsupported workflow status: {status}")
    workflow["status"] = status
    workflow["updated_at"] = utc_now()
    if status in {"completed", "failed", "cancelled"}:
        workflow["finished_at"] = workflow.get("finished_at") or utc_now()
    _append_workflow_log(workflow, f"workflow.{status}", summary)


def _queue_repair_tasks(workflow: dict[str, Any]) -> None:
    for task in workflow.get("tasks", []):
        if isinstance(task, dict) and task.get("agent_role") == "repair_agent" and task.get("status") in {"pending", "queued"}:
            task["status"] = "queued"
            task["updated_at"] = utc_now()


def _select_task(workflow: dict[str, Any], task_id: str | None) -> dict[str, Any]:
    if task_id:
        return _require_task(workflow, task_id)
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    for state in ("running", "validating", "repairing", "queued", "waiting_input"):
        task = next((item for item in tasks if item.get("status") == state), None)
        if task:
            return task
    raise ValueError("no runnable workflow task is available")


def _require_task(workflow: dict[str, Any], task_id: str | None) -> dict[str, Any]:
    if not task_id:
        raise ValueError("task_id is required")
    for task in workflow.get("tasks", []):
        if isinstance(task, dict) and task.get("id") == task_id:
            return task
    raise ValueError(f"task not found: {task_id}")


def _dependency_edges(tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for task in tasks:
        for dep in task.get("depends_on", []):
            edges.append({"from": dep, "to": task["id"]})
    return edges


def _workflow_metrics(workflow: dict[str, Any]) -> dict[str, Any]:
    tasks = [task for task in workflow.get("tasks", []) if isinstance(task, dict)]
    status_counts: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "task_count": len(tasks),
        "status_counts": status_counts,
        "duration_seconds": _duration_seconds(workflow.get("started_at"), workflow.get("finished_at") or workflow.get("updated_at")),
        "retry_count": sum(int(task.get("retry_count") or 0) for task in tasks),
        "log_count": len(workflow.get("logs", []) if isinstance(workflow.get("logs"), list) else []),
    }


def _empty_metrics() -> dict[str, Any]:
    return {"task_count": 0, "status_counts": {}, "duration_seconds": None, "retry_count": 0, "log_count": 0}


def _aggregate_agent_observability(workflows: list[dict[str, Any]]) -> dict[str, Any]:
    agents: dict[str, dict[str, Any]] = {}
    handoff_count = 0
    escalation_count = 0
    for workflow in workflows:
        observability = agent_runtime.agent_observability(workflow)
        handoff_count += int(observability.get("handoff_count") or 0)
        escalation_count += int(observability.get("escalation_frequency") or 0)
        for item in observability.get("agents", []) if isinstance(observability.get("agents"), list) else []:
            agent_id = str(item.get("agent_id") or "unknown")
            current = agents.setdefault(
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
                },
            )
            for key in current:
                if key != "agent_id":
                    current[key] += int(item.get(key) or 0)
    return {
        "agents": list(agents.values()),
        "handoff_count": handoff_count,
        "escalation_count": escalation_count,
    }


def _duration_seconds(start: Any, end: Any) -> float | None:
    if not start or not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, round((end_dt.astimezone(timezone.utc) - start_dt.astimezone(timezone.utc)).total_seconds(), 3))


def _safe_context_files(root: Path, paths: list[str]) -> dict[str, list[Any]]:
    included: list[str] = []
    blocked: list[dict[str, str]] = []
    for raw in paths:
        value = str(raw).strip().replace("\\", "/")
        if not value:
            continue
        target = (root / value).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            blocked.append({"path": value, "reason": "outside workspace"})
            continue
        if not is_safe_to_read(target, root):
            blocked.append({"path": value, "reason": "not safe to read"})
            continue
        included.append(value)
    return {"included": included, "blocked": blocked}


def _compact_intelligence_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": result.get("project_id"),
        "frameworks": result.get("frameworks", []),
        "file_count": result.get("file_index", {}).get("file_count"),
        "build_systems": result.get("build_systems", []),
        "health": result.get("health", {}),
    }


def _normalize_workflow_type(workflow_type: str) -> str:
    value = str(workflow_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value not in WORKFLOW_TYPES:
        raise ValueError(f"unsupported workflow type: {workflow_type}")
    return value


def _normalize_action(action: str) -> str:
    value = str(action or "advance").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"run_next": "advance", "start": "advance", "retry": "retry_task", "complete": "complete_task", "fail": "fail_task"}
    return aliases.get(value, value)


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
        raise WorkflowPersistenceError(f"Could not create workflow state directory at {memory.root}: {exc}") from exc
    return memory


def _load_workflows(memory: ProjectMemory) -> list[dict[str, Any]]:
    data = _read_json(memory, WORKFLOWS_FILE, [])
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _write_workflows(memory: ProjectMemory, workflows: list[dict[str, Any]]) -> None:
    workflows = sorted(workflows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:MAX_WORKFLOWS]
    _write_json(memory, WORKFLOWS_FILE, workflows)


def _get_workflow(memory: ProjectMemory, workflow_id: str) -> dict[str, Any]:
    for workflow in _load_workflows(memory):
        if workflow.get("id") == workflow_id:
            return workflow
    raise WorkflowNotFoundError(workflow_id)


def _persist_workflow(memory: ProjectMemory, workflow: dict[str, Any]) -> None:
    workflows = _load_workflows(memory)
    workflows = [item for item in workflows if item.get("id") != workflow.get("id")]
    workflows.append(workflow)
    _write_workflows(memory, workflows)


def _load_events(memory: ProjectMemory) -> list[dict[str, Any]]:
    data = _read_json(memory, EVENTS_FILE, [])
    events = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    return sorted(events, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _record_event(memory: ProjectMemory, workflow: dict[str, Any], event: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    events = _load_events(memory)
    entry = {
        "id": f"event-{uuid.uuid4().hex[:12]}",
        "project_id": workflow.get("project_id") or _project_id(Path(workflow.get("workspace") or memory.workspace)),
        "workspace": workflow.get("workspace") or str(memory.workspace),
        "workflow_id": workflow.get("id"),
        "workflow_type": workflow.get("workflow_type"),
        "event": event,
        "summary": scrub(summary),
        "created_at": utc_now(),
        "payload": _safe_metadata(payload),
    }
    events.append(entry)
    events = sorted(events, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:MAX_EVENTS]
    _write_json(memory, EVENTS_FILE, events)
    return entry


def _workflow_timeline(memory: ProjectMemory, workflow_id: str) -> list[dict[str, Any]]:
    return [event for event in _load_events(memory) if event.get("workflow_id") == workflow_id][:100]


def _load_client_sync(memory: ProjectMemory) -> list[dict[str, Any]]:
    data = _read_json(memory, CLIENT_SYNC_FILE, [])
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _write_client_sync(memory: ProjectMemory, clients: list[dict[str, Any]]) -> None:
    clients = sorted(clients, key=lambda item: str(item.get("last_seen") or ""), reverse=True)[:100]
    _write_json(memory, CLIENT_SYNC_FILE, clients)


def _append_task_log(task: dict[str, Any], event: str, summary: str, payload: dict[str, Any] | None = None) -> None:
    logs = task.setdefault("logs", [])
    logs.append({"timestamp": utc_now(), "event": event, "summary": scrub(summary), "payload": _safe_metadata(payload or {})})
    task["logs"] = logs[-MAX_LOGS_PER_WORKFLOW:]


def _append_workflow_log(workflow: dict[str, Any], event: str, summary: str, payload: dict[str, Any] | None = None) -> None:
    logs = workflow.setdefault("logs", [])
    logs.append({"timestamp": utc_now(), "event": event, "summary": scrub(summary), "payload": _safe_metadata(payload or {})})
    workflow["logs"] = logs[-MAX_LOGS_PER_WORKFLOW:]


def _append_audit(memory: ProjectMemory, workflow: dict[str, Any], event: str, detail: str) -> None:
    path = memory.root / AUDIT_FILE
    line = f"- `{utc_now()}` **{scrub(event)}** workflow={workflow.get('id')} status={workflow.get('status')}"
    if detail:
        line += f"\n  {scrub(detail).replace(chr(10), chr(10) + '  ')}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


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
        raise WorkflowPersistenceError(f"Could not persist workflow state at {path}: {exc}") from exc


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, sort_keys=True)}\n\n"


def _safe_metadata(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {scrub(str(key)): _safe_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value]
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, (int, float, bool)):
        return value
    return scrub(str(value))


def _project_id(root: Path) -> str:
    return f"project-{hashlib.sha1(str(root).lower().encode('utf-8')).hexdigest()[:12]}"
