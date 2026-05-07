from __future__ import annotations

from typing import Any

from .validation_diagnostics import (
    failed_step_display,
    first_diagnostic_brief as validation_first_diagnostic_brief,
)


def latest_history_validation(command_history: dict[str, Any]) -> dict[str, Any]:
    commands = command_history.get("commands") if isinstance(command_history, dict) else []
    if not isinstance(commands, list):
        return {}
    for item in reversed(commands):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "validation" or kind.startswith("verification:"):
            return item
    return {}


def status_value(value: Any, *, limit: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def first_diagnostic_brief(payload: dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return ""
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        file = status_value(diagnostic.get("file"), limit=150)
        if not file:
            continue
        line = status_value(diagnostic.get("line"), limit=20)
        column = status_value(diagnostic.get("column"), limit=20)
        location = file
        if line:
            location += f":{line}"
        if column:
            location += f":{column}"
        severity = status_value(diagnostic.get("severity"), limit=24)
        code = status_value(diagnostic.get("code"), limit=32)
        detail = " ".join(part for part in (severity, code) if part)
        return f"{location} {detail}".strip()
    return ""


def compact_repair_brief(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = status_value(payload.get("failed_step"), limit=40)
    failed_step_command = status_value(payload.get("failed_step_command"), limit=220)
    failed_command = status_value(payload.get("command") or validation_command, limit=220)
    diagnostic = first_diagnostic_brief(payload)

    parts: list[str] = []
    if failed_step and failed_step_command:
        parts.append(f"Repair step {failed_step}: {failed_step_command}")
    elif failed_step_command:
        parts.append(f"Repair {failed_step_command}")
    elif diagnostic:
        parts.append(f"Repair diagnostic {diagnostic}")
    elif failed_command:
        parts.append(f"Repair {failed_command}")
    else:
        parts.append("Repair failed validation")

    if diagnostic and not parts[0].endswith(diagnostic):
        parts.append(f"diagnostic {diagnostic}")
    parts.append("rerun validation")
    return "; ".join(parts)


def compact_validation_repair_brief(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = failed_step_display(payload)
    diagnostic = validation_first_diagnostic_brief(payload)
    failed_command = str(payload.get("command") or validation_command).strip()
    parts: list[str] = []
    if failed_step:
        parts.append(f"Repair {failed_step}")
    elif diagnostic:
        parts.append(f"Repair diagnostic {diagnostic}")
    elif failed_command:
        parts.append(f"Repair {failed_command}")
    else:
        parts.append("Repair failed validation")
    if failed_step and diagnostic:
        parts.append(f"diagnostic {diagnostic}")
    parts.append("rerun validation")
    return "; ".join(parts)
