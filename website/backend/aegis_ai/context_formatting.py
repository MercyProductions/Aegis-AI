from __future__ import annotations

from pathlib import Path
from typing import Any


def format_fix_memory_context(memory_hits: list[Any]) -> str:
    lines = []
    for item in memory_hits[:5]:
        signature = item.error_signature.strip().replace("\n", " ")[:180]
        fix = item.fix_summary.strip().replace("\n", " ")[:180]
        lines.append(
            f"- [{item.category}] confidence={item.confidence:.2f} error={signature} | fix={fix}"
        )
    return "\n".join(lines)


def format_task_history_context(recent_tasks: list[Any]) -> str:
    lines = []
    for item in recent_tasks[:6]:
        message = item.message.strip().replace("\n", " ")[:160]
        lines.append(f"- [{item.status}] {item.mode} at {item.created_at}: {message}")
    return "\n".join(lines)


def format_project_memory_context(project_memory_hits: list[Any]) -> str:
    lines = []
    for item in project_memory_hits[:6]:
        detail = item.detail.strip().replace("\n", " ")[:180]
        lines.append(f"- [{item.category}] {item.title}: {detail}")
    return "\n".join(lines)


def format_project_intelligence_context(intelligence: Any | None, *, workspace_name: str) -> str:
    if intelligence is None:
        return ""
    lines = [
        f"Project intelligence: {intelligence.profile.project_name or workspace_name}",
    ]
    if intelligence.profile.stack:
        lines.append(f"- Stack: {', '.join(intelligence.profile.stack[:10])}")
    if intelligence.profile.main_entry_files:
        lines.append(f"- Main entries: {', '.join(intelligence.profile.main_entry_files[:8])}")
    if intelligence.profile.coding_conventions:
        lines.append(f"- Conventions: {' / '.join(intelligence.profile.coding_conventions[:5])}")
    if intelligence.validation_commands:
        lines.append(f"- Validation: {' / '.join(intelligence.validation_commands[:5])}")
    if intelligence.file_importance:
        important = ", ".join(item.path for item in intelligence.file_importance[:10])
        lines.append(f"- Important files: {important}")
    if intelligence.architecture.api_routes:
        routes = ", ".join(f"{route.method} {route.path}" for route in intelligence.architecture.api_routes[:8])
        lines.append(f"- API routes: {routes}")
    for note in intelligence.recommendations[:4]:
        lines.append(f"- Intelligence note: {note}")
    return "\n".join(lines)


def format_project_intelligence_context_for_workspace(intelligence: Any | None, workspace_root: Path) -> str:
    return format_project_intelligence_context(intelligence, workspace_name=workspace_root.name)


def format_instruction_file_context(instruction_files: list[Any]) -> str:
    lines: list[str] = []
    for item in instruction_files[:6]:
        pending = "; ".join(item.pending_items[:8])
        header = (
            f"- {item.path} [{item.kind}, score={item.score:.2f}]: "
            f"{item.title or 'Project instructions'} ({item.summary})"
        )
        lines.append(header)
        if pending:
            lines.append(f"  Open items: {pending}")
        excerpt = item.excerpt.strip()
        if excerpt:
            compact = excerpt.replace("\n", " / ")
            lines.append(f"  Excerpt: {compact[:600]}")
    if lines:
        lines.append(
            "Instruction rule: Treat these files as durable project intent. During autopilot or broad 'continue' prompts, work through their open items by priority and keep the implementation aligned with them. When an open checkbox item is truly completed, update that same instruction/TODO file from [ ] to [x] for the completed item, but never mark unchecked work complete unless the code and validation prove it."
        )
    return "\n".join(lines)
