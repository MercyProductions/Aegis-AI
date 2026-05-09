from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import memory_dir


GENERATED_START = "<!-- AEGIS_CORE:GENERATED START -->"
GENERATED_END = "<!-- AEGIS_CORE:GENERATED END -->"


class ProjectMemory:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()
        self.root = memory_dir(self.workspace)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("decisions.md", "known-issues.md", "validation-log.md"):
            path = self.root / name
            if not path.exists():
                path.write_text(f"# {name.removesuffix('.md').replace('-', ' ').title()}\n\n", encoding="utf-8")
        history = self.root / "agent-history.json"
        if not history.exists():
            history.write_text("[]\n", encoding="utf-8")

    def write_json(self, name: str, data: Any) -> Path:
        self.ensure()
        path = self.root / name
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_generated_markdown(self, name: str, title: str, body: str) -> Path:
        self.ensure()
        path = self.root / name
        existing = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n\n"
        generated = f"{GENERATED_START}\n\n{body.rstrip()}\n\nGenerated: {utc_now()}\n\n{GENERATED_END}"
        if GENERATED_START in existing and GENERATED_END in existing:
            before = existing.split(GENERATED_START, 1)[0].rstrip()
            after = existing.split(GENERATED_END, 1)[1].lstrip()
            text = f"{before}\n\n{generated}\n\n{after}".rstrip() + "\n"
        else:
            text = f"{existing.rstrip()}\n\n{generated}\n"
        path.write_text(text, encoding="utf-8")
        return path

    def append_decision(self, summary: str, affected_files: list[str] | None = None, validation: str = "not run") -> Path:
        self.ensure()
        path = self.root / "decisions.md"
        files = ", ".join(affected_files or []) or "none"
        entry = f"## {utc_now()}\n\n- What changed: {summary}\n- Affected files: {files}\n- Validation: {validation}\n\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return path


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
