from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .config import memory_dir


SECRET_MARKERS = (
    "api_key",
    "apikey",
    "api-key",
    "auth",
    "authorization",
    "bearer",
    "credential",
    "passwd",
    "password",
    "private key",
    "private_key",
    "secret",
    "token",
)

SENSITIVE_QUERY_RE = re.compile(
    r"([?&](?:api[_-]?key|key|token|secret|password|passwd|credential)=)[^&#\s]+",
    re.IGNORECASE,
)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"\b((?:api[_-]?key|token|secret|password|passwd|credential)\s*=\s*)[^\s&]+",
    re.IGNORECASE,
)
BEARER_TOKEN_RE = re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/\-=]+", re.IGNORECASE)


def scrub(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in str(text).splitlines():
        line = _redact_inline_secrets(line)
        lowered = line.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            cleaned_lines.append("[redacted secret-like log line]")
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _redact_inline_secrets(line: str) -> str:
    line = SENSITIVE_QUERY_RE.sub(r"\1[redacted]", line)
    line = SENSITIVE_ASSIGNMENT_RE.sub(r"\1[redacted]", line)
    return BEARER_TOKEN_RE.sub(r"\1[redacted]", line)


class CoreLogger:
    def __init__(self, workspace: str | Path | None = None):
        self.root = Path(workspace or ".").resolve()
        self.path = memory_dir(self.root) / "core-log.md"

    def log(self, event: str, detail: str = "") -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            body = f"- `{stamp}` **{scrub(event)}**"
            if detail:
                body += f"\n  {scrub(detail).replace(chr(10), chr(10) + '  ')}"
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(body + "\n")
        except OSError:
            return
