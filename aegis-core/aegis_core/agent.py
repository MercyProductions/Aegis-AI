from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory
from .roadmap import RoadmapPersistenceError, generate_roadmap
from .validation import validation_summary
from .workspace import WorkspaceScanner


ACTIVE_AGENT_PLAN_FILE = "active-agent-plan.json"
ACTIVE_REPAIR_PLAN_FILE = "active-repair-plan.json"


def continue_from_roadmap(workspace: str | Path, request: str | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    roadmap_path = memory.root / "roadmap.md"
    memory_warning = None
    if not roadmap_path.is_file():
        try:
            generate_roadmap(root, persist=True)
        except RoadmapPersistenceError as exc:
            memory_warning = str(exc)

    scan = WorkspaceScanner(root).scan(persist=True)
    roadmap = _read_text_best_effort(roadmap_path)
    task = choose_task(roadmap, request)
    plan = {
        "task": task,
        "request": request or "Continue from roadmap",
        "risk": "low",
        "approval_required": True,
        "mode": "plan-only",
        "steps": [
            "Confirm the chosen task with the user/client.",
            "Build focused context from active file, roadmap, relevant config, tests, and recent validation output.",
            "Ask the model for a minimal change plan.",
            "Generate proposed diffs only after explicit client request.",
            "Wait for approval before edits.",
            "Run detected validation after approved edits.",
        ],
        "likely_context": {
            "build_files": scan.get("build_files", [])[:10],
            "tests": scan.get("test_files", [])[:10],
            "entry_points": scan.get("entry_points", [])[:10],
        },
        "validation": validation_summary(root),
    }
    if memory_warning:
        plan["memory_warning"] = memory_warning
    plan_warning = _persist_plan(memory, ACTIVE_AGENT_PLAN_FILE, plan)
    if plan_warning:
        plan["memory_warning"] = _combine_warnings(plan.get("memory_warning"), plan_warning)
    return plan


def repair_from_last_validation(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    log_path = memory.root / "validation-log.md"
    if not log_path.is_file():
        return {"ok": False, "message": "No validation log exists yet.", "approval_required": True}
    tail = _read_text_best_effort(log_path, limit=6000)
    if not tail.strip():
        return {"ok": False, "message": "No readable validation log exists yet.", "approval_required": True}
    plan = {
        "ok": True,
        "mode": "repair-plan-only",
        "approval_required": True,
        "summary": "Use the latest validation output to propose one minimal repair. Do not edit automatically.",
        "latest_validation_excerpt": tail,
        "repair_attempt_limit": 3,
    }
    plan_warning = _persist_plan(memory, ACTIVE_REPAIR_PLAN_FILE, plan)
    if plan_warning:
        plan["memory_warning"] = plan_warning
    return plan


def choose_task(roadmap: str, request: str | None = None) -> str:
    if request:
        return request
    for line in roadmap.splitlines():
        stripped = line.strip()
        if stripped[:2] in {"1.", "2.", "3."}:
            return stripped
    return "Review architecture map and choose one low-risk improvement."


def _read_text_best_effort(path: Path, limit: int | None = None) -> str:
    try:
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if limit is not None:
        text = text[-limit:]
    return scrub(text)


def _persist_plan(memory: ProjectMemory, name: str, plan: dict[str, Any]) -> str | None:
    path = memory.root / name
    if path.parent.exists() and not path.parent.is_dir():
        return f"Could not persist agent plan because {path.parent} is not a directory."
    if path.exists() and not path.is_file():
        return f"Could not persist agent plan because {path} is not a writable file."
    memory.write_json(name, plan)
    try:
        persisted = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, json.JSONDecodeError) as exc:
        return scrub(f"Could not persist agent plan at {path}: {exc}")
    if persisted != plan:
        return f"Could not persist agent plan at {path}. Check that the workspace .aegis path is writable."
    return None


def _combine_warnings(*warnings: str | None) -> str:
    return "; ".join(scrub(warning) for warning in warnings if warning)
