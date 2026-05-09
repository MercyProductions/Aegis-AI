from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .branding import branding_tokens
from .clients import list_clients
from .config import load_config, memory_dir
from .diagnostics import scrub
from .ollama import OllamaClient
from .tasks import list_tasks
from .validation import validation_summary


MEMORY_FILES = {
    "project_summary": "project-summary.md",
    "solution_summary": "solution-summary.md",
    "roadmap": "roadmap.md",
    "architecture_map": "architecture-map.md",
    "decisions": "decisions.md",
    "known_issues": "known-issues.md",
    "validation_log": "validation-log.md",
    "jobs_log": "jobs-log.md",
    "daily_health_report": "daily-health-report.md",
    "weekly_quality_summary": "weekly-quality-summary.md",
}


def shared_memory_summary(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    aegis = memory_dir(root)
    entries: dict[str, dict[str, Any]] = {}
    for key, filename in MEMORY_FILES.items():
        path = aegis / filename
        entries[key] = {
            "path": str(path),
            "exists": path.exists(),
            "excerpt": _read_excerpt(path, 2500) if path.exists() else "",
        }
    return {"workspace": str(root), "memory_dir": str(aegis), "entries": entries}


def diagnostics_summary(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    aegis = memory_dir(root)
    log_files = {
        "core_log": "core-log.md",
        "extension_log": "extension-log.md",
        "validation_log": "validation-log.md",
        "jobs_log": "jobs-log.md",
        "health_history": "health-history.json",
        "agent_history": "agent-history.json",
    }
    logs: dict[str, dict[str, Any]] = {}
    for key, filename in log_files.items():
        path = aegis / filename
        logs[key] = {
            "path": str(path),
            "exists": path.exists(),
            "tail": _read_tail(path, 4000) if path.exists() else "",
        }
    return {"workspace": str(root), "logs": logs}


def dashboard_summary(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    config = load_config(root)
    model_status = OllamaClient(config).health().__dict__
    tasks = list_tasks(root)
    memory = shared_memory_summary(root)
    diagnostics = diagnostics_summary(root)
    validation = validation_summary(root)
    active_tasks = [
        task
        for task in tasks
        if task.get("status")
        in {"planned", "running", "waiting_for_approval", "pending", "in_progress", "needs_approval", "validating", "blocked"}
    ]
    stale_tasks = [task for task in active_tasks if _task_age_hours(task) >= 24]
    return {
        "workspace": str(root),
        "clients": list_clients(root),
        "active_projects": [_project_label(root, memory)],
        "active_tasks": active_tasks,
        "stale_tasks": stale_tasks,
        "recent_tasks": tasks[:10],
        "model_status": model_status,
        "diagnostics": diagnostics,
        "roadmap": memory["entries"].get("roadmap", {}),
        "validation": validation,
        "recent_activity": _recent_activity(root),
        "suggested_actions": _suggested_actions(model_status, active_tasks, stale_tasks, diagnostics),
        "branding": branding_tokens(),
    }


def _project_label(root: Path, memory: dict[str, Any]) -> dict[str, Any]:
    summary = memory["entries"].get("project_summary") or memory["entries"].get("solution_summary") or {}
    return {
        "name": root.name,
        "path": str(root),
        "summary_available": bool(summary.get("exists")),
    }


def _recent_activity(root: Path) -> list[dict[str, Any]]:
    history_path = memory_dir(root) / "agent-history.json"
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data[-20:] if isinstance(item, dict)]


def _task_age_hours(task: dict[str, Any]) -> float:
    stamp = str(task.get("updated_at") or task.get("created_at") or "")
    if not stamp:
        return 0.0
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0


def _suggested_actions(
    model_status: dict[str, Any],
    active_tasks: list[dict[str, Any]],
    stale_tasks: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    if not model_status.get("reachable"):
        actions.append("Start Ollama or update the shared Ollama URL before model-backed workflows.")
    if model_status.get("missing_models"):
        actions.append("Install or change missing default/fallback models in shared settings.")
    if stale_tasks:
        actions.append("Review stale cross-client tasks and mark them completed, cancelled, or resumed.")
    if len(active_tasks) >= 5:
        actions.append("Finish or cancel active tasks before starting more cross-client work.")
    core_log = diagnostics.get("logs", {}).get("core_log", {})
    if core_log.get("exists") is False:
        actions.append("Run a Core health check to create the shared diagnostic log.")
    return actions[:6]


def _read_excerpt(path: Path, limit: int) -> str:
    try:
        return scrub(path.read_text(encoding="utf-8", errors="ignore")[:limit])
    except OSError:
        return ""


def _read_tail(path: Path, limit: int) -> str:
    try:
        return scrub(path.read_text(encoding="utf-8", errors="ignore")[-limit:])
    except OSError:
        return ""
