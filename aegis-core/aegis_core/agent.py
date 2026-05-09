from __future__ import annotations

from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory
from .roadmap import generate_roadmap
from .validation import validation_summary
from .workspace import WorkspaceScanner


def continue_from_roadmap(workspace: str | Path, request: str | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    roadmap_path = memory.root / "roadmap.md"
    if not roadmap_path.is_file():
        generate_roadmap(root, persist=True)

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
    memory.write_json("active-agent-plan.json", plan)
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
    memory.write_json("active-repair-plan.json", plan)
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
