from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re


BUILD_LOG_EXTENSIONS = {".md", ".txt", ".log"}
MAX_AEGIS_JSON_BYTES = 256_000
SENSITIVE_FIELD = (
    r"x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"client[_-]?secret|secret|token|password|passwd|pwd|credential|authorization|private[_-]?key"
)

SECRET_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED_JWT]"),
    (
        re.compile(
            rf"(?i)\b((?:{SENSITIVE_FIELD})\s*[:=]\s*)"
            r"([\"']?)[^\s\"'&,;]+"
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
    (re.compile(rf"(?i)([?&](?:{SENSITIVE_FIELD}|key|signature)=)[^&\s]+"), r"\1[REDACTED]"),
)


def read_aegis_json(workspace_root: Path, filename: str) -> dict[str, Any]:
    if "/" in filename or "\\" in filename:
        return {}
    path = workspace_root / ".aegis" / filename
    try:
        if not path.exists() or path.stat().st_size > MAX_AEGIS_JSON_BYTES:
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_project_build_log(workspace_root: Path, references: list[str]) -> tuple[str, Path] | None:
    candidates: dict[str, tuple[str, Path]] = {}
    for reference in references:
        candidate = safe_project_build_log_path(workspace_root, reference)
        if candidate is not None and candidate.exists():
            display = safe_log_display_path(workspace_root, reference)
            candidates[str(candidate.resolve())] = (display, candidate)

    logs_dir = workspace_root / ".aegis" / "build_logs"
    try:
        if logs_dir.exists():
            for path in logs_dir.iterdir():
                if path.is_file() and path.suffix.lower() in BUILD_LOG_EXTENSIONS:
                    display = display_workspace_relative_path(workspace_root, path)
                    candidates[str(path.resolve())] = (display, path)
    except OSError:
        pass

    latest: tuple[str, Path] | None = None
    latest_mtime = -1.0
    for display, path in candidates.values():
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > latest_mtime:
            latest = (display, path)
            latest_mtime = mtime
    return latest


def safe_project_build_log_path(workspace_root: Path, value: Any) -> Path | None:
    text = status_text(value, limit=260)
    if not text:
        return None
    normalized = text.replace("\\", "/").strip()
    if normalized.startswith(".aegis/build_logs/"):
        candidate = workspace_root / Path(*normalized.split("/"))
    else:
        candidate = Path(text)
        if not candidate.is_absolute():
            return None

    try:
        resolved = candidate.resolve()
        build_log_root = (workspace_root / ".aegis" / "build_logs").resolve()
        resolved.relative_to(build_log_root)
    except (OSError, ValueError):
        return None
    if resolved.suffix.lower() not in BUILD_LOG_EXTENSIONS:
        return None
    return resolved


def safe_log_display_path(workspace_root: Path, value: Any) -> str:
    path = safe_project_build_log_path(workspace_root, value)
    if path is None:
        return status_text(value, limit=180)
    return display_workspace_relative_path(workspace_root, path)


def display_workspace_relative_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def read_text_tail(path: Path, *, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        text = text[-max_chars:]
        text = "[truncated to latest output]\n" + text
    return text.strip()[:max_chars]


def status_text(value: Any, *, default: str = "", limit: int = 500) -> str:
    if value is None:
        return default
    text = str(value).replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return default
    return text[:limit]


def redact_project_status_text(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
