from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import memory_dir


SECRET_MARKERS = ("api_key", "apikey", "token", "secret", "password", "private key")


def scrub(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in str(text).splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            cleaned_lines.append("[redacted secret-like log line]")
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


class CoreLogger:
    def __init__(self, workspace: str | Path | None = None):
        self.root = Path(workspace or ".").resolve()
        self.path = memory_dir(self.root) / "core-log.md"

    def log(self, event: str, detail: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = f"- `{stamp}` **{scrub(event)}**"
        if detail:
            body += f"\n  {scrub(detail).replace(chr(10), chr(10) + '  ')}"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(body + "\n")
