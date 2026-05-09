from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .memory import ProjectMemory, utc_now


ACTIVE_STATUSES = {
    "planned",
    "running",
    "waiting_for_approval",
    "pending",
    "in_progress",
    "needs_approval",
    "validating",
    "blocked",
}
VALID_STATUSES = ACTIVE_STATUSES | {"completed", "cancelled", "rolled_back", "failed"}


class TaskStorePersistenceError(RuntimeError):
    """Raised when a shared task mutation cannot be persisted."""


@dataclass
class AegisTask:
    id: str
    title: str
    kind: str
    source_client: str
    status: str
    created_at: str
    updated_at: str
    request: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "source_client": self.source_client,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request": self.request,
            "metadata": self.metadata,
        }


def create_task(
    workspace: str | Path,
    title: str,
    kind: str = "general",
    source_client: str = "unknown",
    request: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = ProjectMemory(workspace)
    memory.ensure()
    tasks = _load_tasks(memory)
    now = utc_now()
    task = AegisTask(
        id=f"task-{uuid.uuid4().hex[:12]}",
        title=title,
        kind=kind,
        source_client=source_client,
        status="planned",
        created_at=now,
        updated_at=now,
        request=request,
        metadata=metadata or {},
    )
    task_data = task.to_dict()
    tasks.append(task_data)
    _write_tasks(memory, tasks)
    persisted = _find_task(_load_tasks(memory), task.id)
    if persisted != task_data:
        raise TaskStorePersistenceError(
            f"Could not persist task at {memory.root / 'tasks.json'}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    _append_history(memory, {"event": "task_created", "task": persisted})
    return persisted


def list_tasks(workspace: str | Path, include_completed: bool = True) -> list[dict[str, Any]]:
    memory = ProjectMemory(workspace)
    memory.ensure()
    tasks = _load_tasks(memory)
    if not include_completed:
        tasks = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
    return sorted(tasks, key=_task_sort_key, reverse=True)


def update_task_status(
    workspace: str | Path,
    task_id: str,
    status: str,
    summary: str | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported task status: {status}")
    memory = ProjectMemory(workspace)
    memory.ensure()
    tasks = _load_tasks(memory)
    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = status
            task["updated_at"] = utc_now()
            if summary:
                if not isinstance(task.get("metadata"), dict):
                    task["metadata"] = {}
                task["metadata"]["summary"] = summary
            _write_tasks(memory, tasks)
            persisted = _find_task(_load_tasks(memory), task_id)
            if persisted != task:
                raise TaskStorePersistenceError(
                    f"Could not persist task update at {memory.root / 'tasks.json'}. "
                    "Check that the workspace .aegis path is a writable directory."
                )
            _append_history(memory, {"event": "task_updated", "task": persisted})
            return persisted
    raise KeyError(f"Task not found: {task_id}")


def _load_tasks(memory: ProjectMemory) -> list[dict[str, Any]]:
    path = memory.root / "tasks.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [task for task in (_normalize_task(item) for item in data) if task is not None]
    return []


def _normalize_task(task: Any) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return None
    now = utc_now()
    metadata = task.get("metadata")
    return {
        "id": task_id,
        "title": str(task.get("title") or "Untitled task"),
        "kind": str(task.get("kind") or "general"),
        "source_client": str(task.get("source_client") or "unknown"),
        "status": str(task.get("status") or "planned"),
        "created_at": str(task.get("created_at") or task.get("updated_at") or now),
        "updated_at": str(task.get("updated_at") or task.get("created_at") or now),
        "request": str(task["request"]) if task.get("request") is not None else None,
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _task_sort_key(task: dict[str, Any]) -> float:
    stamp = str(task.get("updated_at") or task.get("created_at") or "")
    if not stamp:
        return 0.0
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
    try:
        return float(stamp)
    except ValueError:
        return 0.0


def _write_tasks(memory: ProjectMemory, tasks: list[dict[str, Any]]) -> None:
    memory.write_json("tasks.json", tasks)


def _find_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


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
