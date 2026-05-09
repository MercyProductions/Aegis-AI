from __future__ import annotations

from pathlib import Path
from typing import Any

from .memory import ProjectMemory
from .workspace import WorkspaceScanner


ROADMAP_FILE = "roadmap.md"


class RoadmapPersistenceError(RuntimeError):
    """Raised when the generated roadmap cannot be persisted."""


def generate_roadmap(workspace: str | Path, scan: dict[str, Any] | None = None, persist: bool = True) -> dict[str, Any]:
    root = Path(workspace).resolve()
    scan_data = scan or WorkspaceScanner(root).scan(persist=persist)
    tasks = next_best_tasks(scan_data)
    markdown = render_roadmap(scan_data, tasks)
    path = None
    if persist:
        path = _persist_roadmap(ProjectMemory(root), markdown)
    return {"workspace": str(root), "roadmap_path": str(path) if path else None, "tasks": tasks, "markdown": markdown}


def next_best_tasks(scan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if not scan.get("readmes"):
        tasks.append(task("Document project entry points", "medium", "Create or update README guidance for setup, run, and validation."))
    if not scan.get("test_files"):
        tasks.append(task("Add first validation test", "medium", "Find the safest tested unit or smoke path and add a minimal test."))
    if scan.get("todo_comments"):
        tasks.append(task("Triage TODO/FIXME comments", "low", "Group existing TODO comments into bugs, cleanup, and future features."))
    if scan.get("build_files"):
        tasks.append(task("Verify build commands", "low", "Confirm detected build files map to working validation commands."))
    if not tasks:
        tasks.append(task("Review architecture map", "low", "Use the generated architecture map to choose one small maintainability improvement."))
    return tasks


def task(title: str, risk: str, reason: str) -> dict[str, str]:
    return {"title": title, "risk": risk, "reason": reason}


def render_roadmap(scan: dict[str, Any], tasks: list[dict[str, str]]) -> str:
    lines = [
        "## Current Project State",
        "",
        f"- Workspace: `{scan['workspace_name']}`",
        f"- Frameworks: {', '.join(scan['frameworks'])}",
        f"- Indexed files: {scan['file_count']}",
        f"- Build files found: {len(scan['build_files'])}",
        f"- Test files found: {len(scan['test_files'])}",
        f"- TODO/FIXME comments found: {len(scan['todo_comments'])}",
        "",
        "## Recommended Priority Order",
        "",
    ]
    for index, item in enumerate(tasks, start=1):
        lines.append(f"{index}. {item['title']} [{item['risk']} risk]")
        lines.append(f"   - Why: {item['reason']}")
    lines.extend([
        "",
        "## Safety Notes",
        "",
        "- Apply no edits without client/user approval.",
        "- Keep changes scoped to one task at a time.",
        "- Run validation after approved edits.",
        "- Use rollback metadata before modifying files.",
    ])
    return "\n".join(lines)


def _persist_roadmap(memory: ProjectMemory, markdown: str) -> Path:
    path = memory.root / ROADMAP_FILE
    _ensure_roadmap_target(path)
    memory.write_generated_markdown(ROADMAP_FILE, "Roadmap", markdown)
    try:
        persisted = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RoadmapPersistenceError(f"Could not persist roadmap at {path}.") from exc
    if markdown.rstrip() not in persisted:
        raise RoadmapPersistenceError(
            f"Could not persist roadmap at {path}. Check that the workspace .aegis path is writable."
        )
    return path


def _ensure_roadmap_target(path: Path) -> None:
    if path.parent.exists() and not path.parent.is_dir():
        raise RoadmapPersistenceError(f"Could not persist roadmap because {path.parent} is not a directory.")
    if path.exists() and not path.is_file():
        raise RoadmapPersistenceError(f"Could not persist roadmap because {path} is not a writable file.")
