from __future__ import annotations

from typing import Any
import re

from .commands import CommandResult
from .diagnostic_redaction import redact_inline


def status_text(value: Any, *, default: str = "", limit: int = 500) -> str:
    if value is None:
        return default
    text = redact_inline(str(value)).replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return default
    return text[:limit]


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text or "")


def normalize_diagnostic_path(path: str) -> str:
    clean = strip_ansi(path).strip().strip("\"'")
    clean = clean.replace("\\", "/")
    clean = re.sub(r"^\./+", "", clean)
    while clean.startswith("../"):
        clean = clean[3:]
    if len(clean) > 260:
        clean = clean[-260:]
    return clean


def to_positive_int(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def extract_validation_diagnostics(result: CommandResult, *, limit: int = 12) -> list[dict[str, Any]]:
    text = "\n".join(part for part in (result.stderr, result.stdout, result.reason) if part).strip()
    if not text:
        return []

    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, int | None, str, str]] = set()

    def add(
        *,
        file: str,
        line: str | int | None = None,
        column: str | int | None = None,
        severity: str = "error",
        code: str = "",
        message: str = "",
        raw: str = "",
    ) -> None:
        if len(diagnostics) >= limit:
            return
        clean_file = normalize_diagnostic_path(file)
        if not clean_file:
            return
        line_no = to_positive_int(line)
        column_no = to_positive_int(column)
        clean_severity = (severity or "error").lower().replace("fatal error", "error")
        clean_code = status_text(code, limit=40)
        clean_message = status_text(message or raw, limit=260)
        key = (clean_file.lower(), line_no, column_no, clean_code.lower(), clean_message.lower())
        if key in seen:
            return
        seen.add(key)
        diagnostics.append(
            {
                "file": clean_file,
                "line": line_no,
                "column": column_no,
                "severity": clean_severity,
                "code": clean_code,
                "message": clean_message,
                "raw": status_text(raw, limit=360),
            }
        )

    lines = [line.rstrip() for line in text.splitlines()]
    msvc_or_ts = re.compile(
        r"^\s*(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*"
        r"(?P<severity>fatal error|error|warning|note)\s*"
        r"(?:(?P<code>[A-Za-z]{1,8}\d{2,6})\s*:)?\s*(?P<message>.+)\s*$",
        re.IGNORECASE,
    )
    gcc_or_clang = re.compile(
        r"^\s*(?P<file>(?:[A-Za-z]:)?[^:\n]+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
        r"(?P<severity>fatal error|error|warning|note)\s*:?\s*"
        r"(?:(?P<code>[A-Za-z]{1,8}\d{2,6})\s*:)?\s*(?P<message>.+)\s*$",
        re.IGNORECASE,
    )
    python_traceback = re.compile(
        r'^\s*File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<message>.+))?\s*$',
        re.IGNORECASE,
    )

    for index, raw_line in enumerate(lines):
        line = strip_ansi(raw_line).strip()
        if not line:
            continue
        match = msvc_or_ts.match(line) or gcc_or_clang.match(line)
        if match:
            add(raw=line, **match.groupdict())
            continue
        match = python_traceback.match(line)
        if match:
            next_message = ""
            for followup in lines[index + 1 : index + 4]:
                candidate = strip_ansi(followup).strip()
                if candidate and not candidate.startswith("File "):
                    next_message = candidate
                    break
            groups = match.groupdict()
            add(
                file=groups.get("file") or "",
                line=groups.get("line"),
                severity="error",
                message=next_message or groups.get("message") or "Python traceback frame",
                raw=line,
            )

    return diagnostics


def failed_step_parts_from_steps(steps: list[dict[str, Any]]) -> tuple[str, str]:
    for raw_step in steps:
        if raw_step.get("ok"):
            continue
        step_index = status_text(raw_step.get("index"), limit=20)
        command = status_text(raw_step.get("command"), limit=260)
        return step_index, command
    return "", ""


def failed_step_display(payload: dict[str, Any]) -> str:
    step_index = status_text(payload.get("failed_step"), limit=40)
    command = status_text(payload.get("failed_step_command"), limit=260)
    if not command and isinstance(payload.get("steps"), list):
        step_index, command = failed_step_parts_from_steps(
            [item for item in payload["steps"] if isinstance(item, dict)]
        )
    if step_index and command:
        return f"step {step_index}: {command}"
    return command or step_index


def diagnostic_display(diagnostic: dict[str, Any]) -> str:
    file = status_text(diagnostic.get("file"), limit=180)
    if not file:
        return ""
    line = status_text(diagnostic.get("line"), limit=20)
    column = status_text(diagnostic.get("column"), limit=20)
    location = file
    if line:
        location += f":{line}"
    if column:
        location += f":{column}"
    severity = status_text(diagnostic.get("severity"), limit=40)
    code = status_text(diagnostic.get("code"), limit=40)
    message = status_text(diagnostic.get("message"), limit=220)
    detail = " ".join(part for part in (severity, code) if part)
    if detail and message:
        return f"{location} {detail}: {message}"
    if detail:
        return f"{location} {detail}"
    if message:
        return f"{location}: {message}"
    return location


def diagnostic_brief(diagnostic: dict[str, Any]) -> str:
    file = status_text(diagnostic.get("file"), limit=150)
    if not file:
        return ""
    line = status_text(diagnostic.get("line"), limit=20)
    column = status_text(diagnostic.get("column"), limit=20)
    location = file
    if line:
        location += f":{line}"
    if column:
        location += f":{column}"
    severity = status_text(diagnostic.get("severity"), limit=24)
    code = status_text(diagnostic.get("code"), limit=32)
    detail = " ".join(part for part in (severity, code) if part)
    return f"{location} {detail}".strip()


def first_diagnostic_display(payload: dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return ""
    for diagnostic in diagnostics:
        if isinstance(diagnostic, dict):
            display = diagnostic_display(diagnostic)
            if display:
                return display
    return ""


def first_diagnostic_brief(payload: dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return ""
    for diagnostic in diagnostics:
        if isinstance(diagnostic, dict):
            brief = diagnostic_brief(diagnostic)
            if brief:
                return brief
    return ""


def repair_target_from_validation(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = failed_step_display(payload)
    diagnostic = first_diagnostic_display(payload)
    failed_command = str(payload.get("command") or validation_command).strip()
    if failed_step and diagnostic:
        return f"{failed_step}; first diagnostic {diagnostic}"
    return diagnostic or failed_step or failed_command or "the failed validation step"


def fenced_log_text(text: str) -> str:
    if not text:
        return ""
    return redact_inline(text).replace("```", "` ` `").strip()


def validation_steps_log(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "(single command)"

    lines: list[str] = []
    for raw_step in steps:
        index = raw_step.get("index", len(lines) + 1)
        command = status_text(raw_step.get("command"), limit=260)
        reason = status_text(raw_step.get("reason"), limit=220)
        exit_code = raw_step.get("exit_code")
        status = "passed" if raw_step.get("ok") else "failed"
        if raw_step.get("timed_out"):
            status = "timed out"
        elif raw_step.get("allowed") is False:
            status = "blocked"
        lines.append(f"{index}. `{command}` - {status} (exit: {exit_code if exit_code is not None else 'n/a'}; {reason})")
    return "\n".join(lines)


def validation_diagnostics_log(diagnostics: list[dict[str, Any]]) -> str:
    if not diagnostics:
        return "(none captured)"

    lines: list[str] = []
    for diagnostic in diagnostics[:12]:
        display = diagnostic_display(diagnostic)
        if display:
            lines.append(f"- {display}")
    return "\n".join(lines) if lines else "(none captured)"
