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
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        for name in ("decisions.md", "known-issues.md", "validation-log.md"):
            path = self.root / name
            try:
                if not path.exists():
                    path.write_text(f"# {name.removesuffix('.md').replace('-', ' ').title()}\n\n", encoding="utf-8")
            except OSError:
                continue
        history = self.root / "agent-history.json"
        try:
            if not history.exists():
                history.write_text("[]\n", encoding="utf-8")
        except OSError:
            return

    def write_json(self, name: str, data: Any) -> Path:
        self.ensure()
        path = self.root / name
        self._write_text_best_effort(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
        return path

    def write_generated_markdown(self, name: str, title: str, body: str) -> Path:
        self.ensure()
        path = self.root / name
        try:
            existing = path.read_text(encoding="utf-8") if path.exists() and path.is_file() else f"# {title}\n\n"
        except OSError:
            existing = f"# {title}\n\n"
        generated = f"{GENERATED_START}\n\n{body.rstrip()}\n\nGenerated: {utc_now()}\n\n{GENERATED_END}"
        if GENERATED_START in existing and GENERATED_END in existing:
            before = existing.split(GENERATED_START, 1)[0].rstrip()
            after = existing.split(GENERATED_END, 1)[1].lstrip()
            text = f"{before}\n\n{generated}\n\n{after}".rstrip() + "\n"
        else:
            text = f"{existing.rstrip()}\n\n{generated}\n"
        self._write_text_best_effort(path, text)
        return path

    def append_decision(self, summary: str, affected_files: list[str] | None = None, validation: str = "not run") -> Path:
        self.ensure()
        path = self.root / "decisions.md"
        files = ", ".join(affected_files or []) or "none"
        entry = f"## {utc_now()}\n\n- What changed: {summary}\n- Affected files: {files}\n- Validation: {validation}\n\n"
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(entry)
        except OSError:
            return path
        return path

    def _write_text_best_effort(self, path: Path, text: str) -> None:
        tmp: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except OSError:
            if tmp is not None:
                try:
                    if tmp.is_file():
                        tmp.unlink()
                except OSError:
                    pass
            return


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
