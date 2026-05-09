# backend/workspace.py
from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import (
    CheckpointFileInfo,
    CheckpointSummary,
    FileChange,
    WorkspaceDependency,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceInstructionFile,
    WorkspaceProjectManifest,
    WorkspaceScript,
)
from .settings import Settings


IGNORE_NAMES = {
    ".git",
    ".aegis",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

TEXT_SUFFIXES = {
    ".adoc",
    ".asm",
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".cmake",
    ".cmd",
    ".conf",
    ".cpp",
    ".cs",
    ".csv",
    ".css",
    ".cxx",
    ".def",
    ".env",
    ".filters",
    ".fs",
    ".glsl",
    ".go",
    ".gql",
    ".gradle",
    ".graphql",
    ".h",
    ".hh",
    ".hlsl",
    ".hpp",
    ".html",
    ".hxx",
    ".ini",
    ".inl",
    ".ipp",
    ".ixx",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".less",
    ".lua",
    ".m",
    ".mm",
    ".md",
    ".metal",
    ".natvis",
    ".plist",
    ".props",
    ".proto",
    ".ps1",
    ".php",
    ".py",
    ".rb",
    ".rc",
    ".rc2",
    ".rs",
    ".s",
    ".scss",
    ".shader",
    ".sh",
    ".sln",
    ".sql",
    ".swift",
    ".targets",
    ".tsv",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vcxproj",
    ".vue",
    ".xaml",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_NAMES = {
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "CMakeLists.txt",
    "Dockerfile",
    "LICENSE",
    "Makefile",
    "README",
}

LARGE_TEXT_FILE_BYTES = 1_000_000
HUGE_TEXT_FILE_BYTES = 8_000_000
LARGE_FILE_LINE_EXACT_BYTES = 4_000_000
LARGE_FILE_CONTEXT_SAMPLE_CHARS = 12_000
LARGE_FILE_SLICE_MAX_LINES = 2_000
POWERSHELL_BUILD_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"

PRIORITY_NAMES = {
    "README.md",
    "TODO.md",
    "TASKS.md",
    "ROADMAP.md",
    "BACKLOG.md",
    "PROJECT_TODO.md",
    ".aegis/ROADMAP.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "vite.config.ts",
    "src/App.tsx",
    "src/main.tsx",
}

INSTRUCTION_FILE_SUFFIXES = {
    ".adoc",
    ".asciidoc",
    ".md",
    ".markdown",
    ".org",
    ".rst",
    ".taskpaper",
    ".todo",
    ".txt",
}

INSTRUCTION_EXTENSIONLESS_NAMES = {
    "agents",
    "backlog",
    "blueprint",
    "brief",
    "buildplan",
    "checklist",
    "milestones",
    "plan",
    "requirements",
    "roadmap",
    "spec",
    "tasks",
    "tasklist",
    "todo",
    "workplan",
}

INSTRUCTION_NAME_TERMS = {
    "acceptance",
    "agent",
    "agents",
    "backlog",
    "blueprint",
    "brief",
    "bug",
    "bugs",
    "build",
    "checklist",
    "deliverable",
    "deliverables",
    "feature",
    "features",
    "fix",
    "fixes",
    "goal",
    "goals",
    "guide",
    "handoff",
    "instruction",
    "instructions",
    "issue",
    "issues",
    "launch",
    "milestone",
    "milestones",
    "mvp",
    "next",
    "notes",
    "phase",
    "phases",
    "plan",
    "project",
    "release",
    "requirements",
    "roadmap",
    "scope",
    "ship",
    "spec",
    "sprint",
    "task",
    "tasklist",
    "todo",
    "work",
    "workplan",
}

INSTRUCTION_CONTENT_TERMS = {
    "acceptance criteria",
    "agent handoff",
    "app requirements",
    "backlog",
    "build checklist",
    "build plan",
    "completion checklist",
    "definition of done",
    "deliverables",
    "feature list",
    "feature roadmap",
    "fix list",
    "follow-up",
    "implementation plan",
    "known issues",
    "launch plan",
    "milestone",
    "milestones",
    "mvp",
    "next actions",
    "next steps",
    "open tasks",
    "phase 1",
    "phase 2",
    "phase 3",
    "project brief",
    "project goals",
    "project plan",
    "project instructions",
    "requirements",
    "remaining work",
    "release plan",
    "roadmap",
    "ship list",
    "tasks",
    "todo",
    "todo list",
    "validation plan",
    "work items",
}

CHECKBOX_RE = re.compile(r"^\s*(?:(?:[-*+])|(?:\d+[\.)]))?\s*\[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")
BULLET_RE = re.compile(r"^\s*(?P<marker>[-*+]|(?:\d+[\.)]))\s+(?P<text>.+?)\s*$")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")

NODE_FRAMEWORKS = {
    "@angular/core": "Angular",
    "@nestjs/core": "NestJS",
    "@playwright/test": "Playwright",
    "@sveltejs/kit": "SvelteKit",
    "@tailwindcss/vite": "Tailwind CSS",
    "@tauri-apps/api": "Tauri",
    "@vitejs/plugin-react": "Vite",
    "astro": "Astro",
    "bun": "Bun",
    "drizzle-orm": "Drizzle",
    "electron": "Electron",
    "express": "Express",
    "fastify": "Fastify",
    "jest": "Jest",
    "next": "Next.js",
    "playwright": "Playwright",
    "prisma": "Prisma",
    "react": "React",
    "react-native": "React Native",
    "remix": "Remix",
    "svelte": "Svelte",
    "tailwindcss": "Tailwind CSS",
    "typeorm": "TypeORM",
    "typescript": "TypeScript",
    "vite": "Vite",
    "vitest": "Vitest",
    "vue": "Vue",
}

PYTHON_FRAMEWORKS = {
    "alembic": "Alembic",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "litestar": "Litestar",
    "mypy": "mypy",
    "pandas": "pandas",
    "pytest": "pytest",
    "ruff": "Ruff",
    "sqlalchemy": "SQLAlchemy",
    "streamlit": "Streamlit",
}

DATABASE_TOOLS = {
    "alembic": "Alembic",
    "drizzle-orm": "Drizzle",
    "prisma": "Prisma",
    "sequelize": "Sequelize",
    "sqlalchemy": "SQLAlchemy",
    "typeorm": "TypeORM",
}


@dataclass
class ApplyResult:
    applied: list[str]
    warnings: list[str]
    checkpoint: str | None = None


class WorkspaceManager:
    PROJECT_MANIFEST_PATH = ".aegis/project.json"

    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root.resolve()
        self.settings = settings
        self.allowed_roots = [self.project_root]
        configured_root = self._resolve_configured_workspace_root(settings.aegis_workspace_root)
        if configured_root and configured_root not in self.allowed_roots:
            self.allowed_roots.append(configured_root)
        for root in self._resolve_additional_workspace_roots(settings.aegis_additional_workspace_roots):
            if root not in self.allowed_roots:
                self.allowed_roots.append(root)

    def resolve_workspace(self, requested_root: str | None, *, migrate_legacy: bool = True, create: bool = True) -> Path:
        requested_text = (requested_root or "").strip()
        raw = requested_text or self.settings.default_workspace.strip()
        if not raw:
            raw = self.settings.default_workspace

        candidate = Path(raw).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.project_root / candidate).resolve()
        default_candidate = Path(self.settings.default_workspace).expanduser()
        default_resolved = (
            default_candidate.resolve()
            if default_candidate.is_absolute()
            else (self.project_root / default_candidate).resolve()
        )
        is_default_workspace = not requested_text or raw == self.settings.default_workspace or resolved == default_resolved

        self._ensure_within_allowed_roots(resolved)
        if not create:
            return resolved

        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"workspace root could not be created: {resolved}") from exc
        if migrate_legacy and is_default_workspace:
            self._migrate_legacy_workspace_if_needed(resolved)
        return resolved

    def scan(self, root: Path, max_files: int = 80) -> list[WorkspaceFile]:
        files: list[WorkspaceFile] = []
        if not root.exists():
            return files

        for current, dirs, names in os.walk(root):
            dirs[:] = [name for name in dirs if name not in IGNORE_NAMES and not name.startswith(".")]

            for name in sorted(names):
                if len(files) >= max_files:
                    return files
                if name in IGNORE_NAMES:
                    continue

                path = Path(current) / name
                try:
                    relative = path.relative_to(root).as_posix()
                    stat = path.stat()
                except OSError:
                    continue

                kind = self._kind_for(path)
                files.append(self._workspace_file(relative, stat.st_size, kind, path))
        return files

    def context_for_model(
        self,
        root: Path,
        files: list[WorkspaceFile],
        *,
        max_chars: int | None = None,
        max_file_chars: int = 4_000,
    ) -> str:
        budget = max_chars if max_chars is not None else self.settings.max_context_chars
        snippet_limit = max(200, max_file_chars)
        chunks: list[str] = []
        ordered = sorted(
            files,
            key=lambda item: (
                item.path not in PRIORITY_NAMES,
                len(item.path.split("/")),
                item.path,
            ),
        )

        for item in ordered:
            if budget <= 0:
                break

            path = root / item.path
            if item.kind != "text":
                continue

            try:
                if self._is_large_workspace_file(item):
                    block = self._large_file_context_block(path, item, max_chars=min(snippet_limit, LARGE_FILE_CONTEXT_SAMPLE_CHARS))
                    chunk = block[:budget]
                    chunks.append(chunk)
                    budget -= len(chunk)
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if not text.strip():
                continue

            snippet = text[: min(len(text), snippet_limit)]
            block = f"\n--- {item.path} ---\n{snippet}\n"
            chunk = block[:budget]
            chunks.append(chunk)
            budget -= len(chunk)

        return "".join(chunks)

    def discover_instruction_files(
        self,
        root: Path,
        *,
        max_files: int = 8,
        max_bytes: int = 80_000,
        referenced_text: str = "",
    ) -> list[WorkspaceInstructionFile]:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        if not workspace_root.exists() or not workspace_root.is_dir():
            return []

        referenced_keys = self._referenced_instruction_keys(referenced_text)
        candidates: list[WorkspaceInstructionFile] = []
        for current, dirs, names in os.walk(workspace_root):
            current_path = Path(current)
            relative_dir = self._relative_posix(current_path, workspace_root)
            dirs[:] = self._instruction_scan_dirs(relative_dir, dirs)

            for name in sorted(names):
                path = current_path / name
                try:
                    relative = path.relative_to(workspace_root).as_posix()
                    size = path.stat().st_size
                except OSError:
                    continue
                referenced_score = self._instruction_reference_score(relative, referenced_keys)
                if not self._could_be_instruction_file(path, referenced=referenced_score > 0):
                    continue
                if size <= 0 or size > max_bytes:
                    continue

                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                item = self._instruction_file_from_text(
                    relative,
                    text,
                    referenced_score=referenced_score,
                )
                if item is not None:
                    candidates.append(item)

        candidates.sort(
            key=lambda item: (
                -int("referenced by prompt" in item.summary),
                -self._instruction_sort_priority(item.path),
                -item.score,
                -item.pending_count,
                len(item.path.split("/")),
                item.path.lower(),
            )
        )
        return candidates[: max(1, max_files)]

    def read_file(self, root: Path, relative_path: str, max_bytes: int = 120_000) -> str:
        target = self._safe_path(root, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(relative_path)
        if target.stat().st_size > max_bytes:
            raise ValueError(f"{relative_path} exceeds the read limit; use a line slice for large files")
        return target.read_text(encoding="utf-8", errors="replace")

    def read_file_slice(
        self,
        root: Path,
        relative_path: str,
        *,
        start_line: int = 1,
        max_lines: int = 400,
        max_bytes: int = 180_000,
    ) -> dict[str, Any]:
        target = self._safe_path(root, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(relative_path)
        if self._kind_for(target) != "text":
            raise ValueError(f"{relative_path} is not a text file")

        safe_start = max(1, int(start_line))
        safe_max_lines = max(1, min(LARGE_FILE_SLICE_MAX_LINES, int(max_lines)))
        collected: list[str] = []
        bytes_used = 0
        line_number = 0
        truncated = False

        with target.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line_number += 1
                if line_number < safe_start:
                    continue
                encoded_size = len(raw_line.encode("utf-8", errors="replace"))
                if collected and bytes_used + encoded_size > max_bytes:
                    truncated = True
                    break
                collected.append(raw_line)
                bytes_used += encoded_size
                if len(collected) >= safe_max_lines:
                    truncated = True
                    break

        return {
            "path": relative_path,
            "start_line": safe_start,
            "end_line": safe_start + max(0, len(collected) - 1),
            "lines_returned": len(collected),
            "estimated_total_lines": self._estimate_text_lines(target),
            "truncated": truncated,
            "content": "".join(collected),
        }

    def large_file_inventory(
        self,
        root: Path,
        files: list[WorkspaceFile] | None = None,
        *,
        min_bytes: int = LARGE_TEXT_FILE_BYTES,
        max_files: int = 24,
    ) -> list[dict[str, Any]]:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        items = files if files is not None else self.scan(workspace_root, max_files=500)
        inventory: list[dict[str, Any]] = []

        for item in items:
            if item.kind != "text" or item.size < min_bytes:
                continue
            path = workspace_root / item.path
            inventory.append(
                {
                    "path": item.path,
                    "size": item.size,
                    "estimated_lines": item.estimated_lines or self._estimate_text_lines(path),
                    "strategy": item.large_file_strategy or self._large_file_strategy(item.size),
                }
            )
            if len(inventory) >= max_files:
                break

        return inventory

    def load_project_manifest(self, root: Path) -> WorkspaceProjectManifest | None:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        path = workspace_root / self.PROJECT_MANIFEST_PATH
        if not path.exists() or not path.is_file():
            return None

        try:
            if path.stat().st_size > 64_000:
                return None
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        tags = payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        agent_handoff = payload.get("agent_handoff", {})
        if not isinstance(agent_handoff, dict):
            agent_handoff = {}

        mission_contract = payload.get("mission_contract", {})
        if not isinstance(mission_contract, dict):
            mission_contract = {}

        return WorkspaceProjectManifest(
            schema_version=str(payload.get("schema", "")).strip(),
            project_name=str(payload.get("project_name", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            preset_id=str(payload.get("preset_id", "")).strip(),
            preset_label=str(payload.get("preset_label", "")).strip(),
            framework=str(payload.get("framework", "")).strip(),
            language=str(payload.get("language", "")).strip(),
            package_manager=str(payload.get("package_manager", "")).strip(),
            install_command=str(payload.get("install_command", "")).strip(),
            validation_command=str(payload.get("validation_command", "")).strip(),
            original_prompt=str(payload.get("original_prompt", "")).strip(),
            tags=[str(item).strip() for item in tags if str(item).strip()][:24],
            generated_by=str(payload.get("generated_by", "")).strip(),
            mission_contract=mission_contract,
            agent_handoff=agent_handoff,
        )

    def save_project_manifest(self, root: Path, manifest: WorkspaceProjectManifest) -> WorkspaceProjectManifest:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        path = workspace_root / self.PROJECT_MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json", by_alias=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return self.load_project_manifest(workspace_root) or manifest

    def inspect_dependency_profile(self, root: Path) -> WorkspaceDependencyProfile:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        profile = WorkspaceDependencyProfile()
        if not workspace_root.exists() or not workspace_root.is_dir():
            profile.warnings.append("Workspace does not exist or is not a directory.")
            return profile

        self._inspect_workspace_build_runners(workspace_root, profile)
        self._inspect_package_json(workspace_root, profile)
        self._inspect_python_manifests(workspace_root, profile)
        self._inspect_cargo_manifest(workspace_root, profile)
        self._inspect_go_mod(workspace_root, profile)
        self._inspect_dotnet_projects(workspace_root, profile)
        self._inspect_visual_studio_projects(workspace_root, profile)
        self._inspect_cmake(workspace_root, profile)
        self._inspect_native_code_conventions(workspace_root, profile)
        self._inspect_java_manifests(workspace_root, profile)
        self._inspect_database_files(workspace_root, profile)
        self._detect_entry_points(workspace_root, profile)
        self._finalize_dependency_profile(profile)
        return profile

    def apply_changes(self, root: Path, changes: list[FileChange]) -> ApplyResult:
        applied: list[str] = []
        warnings: list[str] = []
        skipped_create_paths: set[str] = set()
        try:
            checkpoint = self._create_checkpoint(root, changes) if changes else None
        except OSError as exc:
            return ApplyResult(
                applied=[],
                warnings=[f"checkpoint could not be created; no files were changed: {exc}"],
                checkpoint=None,
            )

        for change in changes:
            try:
                target = self._safe_path(root, change.path)
            except ValueError as exc:
                warnings.append(f"{change.path}: {exc}")
                continue

            target_key = str(target).casefold()

            if change.action in {"create", "update", "append"}:
                if change.content is None:
                    warnings.append(f"{change.path}: missing file content")
                    if change.action == "create":
                        skipped_create_paths.add(target_key)
                    continue

                if change.action == "create" and target.exists():
                    warnings.append(
                        f"{change.path}: skipped create because the file already exists; use update to modify existing files"
                    )
                    skipped_create_paths.add(target_key)
                    continue

                if change.action == "update" and not target.exists():
                    warnings.append(
                        f"{change.path}: skipped update because the file does not exist; use create to add new files"
                    )
                    continue

                if change.action == "append" and target_key in skipped_create_paths:
                    warnings.append(
                        f"{change.path}: skipped append because the seed create for this file did not apply; use update to modify existing files"
                    )
                    continue

                if change.action == "append" and not target.exists():
                    warnings.append(
                        f"{change.path}: skipped append because the file does not exist; use create before append"
                    )
                    continue

                encoded = change.content.encode("utf-8")
                if len(encoded) > self.settings.max_write_bytes:
                    warnings.append(f"{change.path}: skipped because it exceeds the write limit")
                    if change.action == "create":
                        skipped_create_paths.add(target_key)
                    continue

                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if change.action == "append":
                        with target.open("a", encoding="utf-8", newline="") as handle:
                            handle.write(change.content)
                    else:
                        target.write_text(change.content, encoding="utf-8")
                except OSError as exc:
                    warnings.append(f"{change.path}: file write failed after checkpoint {checkpoint or 'not created'}: {exc}")
                    continue
                applied.append(f"{change.action}: {change.path}")
                continue

            if change.action == "delete":
                if target_key in skipped_create_paths:
                    warnings.append(
                        f"{change.path}: skipped delete because the seed create for this file did not apply; refusing to delete the existing file"
                    )
                    continue

                if target.exists() and target.is_file():
                    try:
                        target.unlink()
                    except OSError as exc:
                        warnings.append(f"{change.path}: file delete failed after checkpoint {checkpoint or 'not created'}: {exc}")
                        continue
                    applied.append(f"delete: {change.path}")
                else:
                    warnings.append(f"{change.path}: file does not exist")

        return ApplyResult(applied=applied, warnings=warnings, checkpoint=checkpoint)

    def restore_checkpoint(self, root: Path, checkpoint_id: str) -> list[str]:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        checkpoint_root = self._safe_checkpoint_root(workspace_root, checkpoint_id)
        manifest_path = checkpoint_root / "manifest.json"

        if manifest_path.exists() and not manifest_path.is_file():
            raise ValueError("checkpoint manifest is not a regular file")
        if not manifest_path.exists():
            raise FileNotFoundError(checkpoint_id)

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("checkpoint manifest is not valid JSON") from exc
        except OSError as exc:
            raise ValueError(f"checkpoint manifest could not be read: {exc}") from exc
        files = payload.get("files", []) if isinstance(payload, dict) else []
        restored: list[str] = []
        files_root = (checkpoint_root / "files").resolve()
        prepared: list[tuple[str, str, Path, Path]] = []

        for entry in files:
            if not isinstance(entry, dict):
                continue

            relative_path = str(entry.get("path", "")).strip()
            state = str(entry.get("state", "missing")).strip()
            if not relative_path:
                continue

            target = self._safe_path(workspace_root, relative_path)
            backup = (files_root / relative_path).resolve()
            try:
                backup.relative_to(files_root)
            except ValueError as exc:
                raise ValueError("checkpoint backup path points outside the checkpoint files folder") from exc

            if state == "present" and not backup.is_file():
                raise ValueError(f"{relative_path}: checkpoint backup file is missing")

            if state == "missing" and target.exists() and not target.is_file():
                raise ValueError(f"{relative_path}: refusing to remove a non-file path during checkpoint restore")

            prepared.append((relative_path, state, target, backup))

        for relative_path, state, target, backup in prepared:
            if state == "present":
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
                restored.append(f"restore: {relative_path}")
                continue

            if state == "missing" and target.exists():
                target.unlink()
                restored.append(f"remove: {relative_path}")

        return restored

    def list_checkpoints(self, root: Path, limit: int = 50) -> list[CheckpointSummary]:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)
        checkpoints_root = workspace_root / ".aegis" / "checkpoints"
        if not checkpoints_root.exists() or not checkpoints_root.is_dir():
            return []

        summaries: list[CheckpointSummary] = []
        max_items = max(1, min(200, limit))
        try:
            candidates = [path for path in checkpoints_root.iterdir() if path.is_dir()]
        except OSError:
            return []

        for checkpoint_root in sorted(candidates, key=lambda item: item.name, reverse=True):
            manifest_path = checkpoint_root / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            if not isinstance(payload, dict):
                continue

            checkpoint_id = str(payload.get("id") or checkpoint_root.name)
            raw_files = payload.get("files", [])
            files: list[CheckpointFileInfo] = []
            if isinstance(raw_files, list):
                for entry in raw_files:
                    if not isinstance(entry, dict):
                        continue
                    relative_path = str(entry.get("path", "")).strip()
                    state = str(entry.get("state", "missing")).strip() or "missing"
                    if not relative_path:
                        continue
                    files.append(CheckpointFileInfo(path=relative_path, state=state))

            present_count = sum(1 for item in files if item.state == "present")
            missing_count = sum(1 for item in files if item.state == "missing")
            summaries.append(
                CheckpointSummary(
                    id=checkpoint_id,
                    created_at=self._checkpoint_created_at(checkpoint_id, checkpoint_root),
                    file_count=len(files),
                    present_count=present_count,
                    missing_count=missing_count,
                    files=files,
                )
            )
            if len(summaries) >= max_items:
                break

        return summaries

    def _inspect_package_json(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        path = root / "package.json"
        payload = self._read_json_object(path)
        if payload is None:
            return

        self._add_unique(profile.config_files, "package.json")
        self._add_unique(profile.languages, "JavaScript")
        if self._path_is_file(root / "tsconfig.json") or "typescript" in self._node_dependency_names(payload):
            self._add_unique(profile.languages, "TypeScript")
            if self._path_is_file(root / "tsconfig.json"):
                self._add_unique(profile.config_files, "tsconfig.json")

        package_manager = self._node_package_manager(root, payload)
        self._add_unique(profile.package_managers, package_manager)
        self._add_unique(profile.build_systems, "Node.js")
        self._add_unique(profile.install_commands, self._node_install_command(package_manager))

        for name, version in self._dependency_items(payload.get("dependencies")):
            profile.dependencies.append(
                WorkspaceDependency(name=name, version=version, source="package.json", group="runtime")
            )
        for name, version in self._dependency_items(payload.get("devDependencies")):
            profile.dev_dependencies.append(
                WorkspaceDependency(name=name, version=version, source="package.json", group="development")
            )

        scripts = payload.get("scripts")
        if isinstance(scripts, dict):
            for name, command in scripts.items():
                script_name = str(name).strip()
                script_command = str(command).strip()
                if script_name and script_command:
                    profile.scripts.append(
                        WorkspaceScript(name=script_name, command=script_command, source="package.json")
                    )
            for command in self._node_validation_commands(package_manager, scripts):
                self._add_unique(profile.validation_commands, command)

        dependency_names = self._node_dependency_names(payload)
        self._add_named_matches(profile.frameworks, dependency_names, NODE_FRAMEWORKS)
        self._add_named_matches(profile.database_tools, dependency_names, DATABASE_TOOLS)

    def _inspect_python_manifests(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        pyproject = root / "pyproject.toml"
        payload = self._read_toml_object(pyproject)
        if payload is not None:
            self._add_unique(profile.config_files, "pyproject.toml")
            self._add_unique(profile.languages, "Python")
            self._add_unique(profile.build_systems, "Python packaging")
            package_manager = self._python_package_manager(root, payload)
            self._add_unique(profile.package_managers, package_manager)
            self._add_unique(profile.install_commands, self._python_install_command(package_manager))

            project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
            for spec in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
                dependency = self._dependency_from_spec(str(spec), "pyproject.toml", "runtime")
                if dependency:
                    profile.dependencies.append(dependency)

            optional = project.get("optional-dependencies") if isinstance(project.get("optional-dependencies"), dict) else {}
            for group, specs in optional.items():
                if not isinstance(specs, list):
                    continue
                for spec in specs:
                    dependency = self._dependency_from_spec(str(spec), "pyproject.toml", str(group) or "optional")
                    if dependency:
                        profile.dev_dependencies.append(dependency)

            tool = payload.get("tool") if isinstance(payload.get("tool"), dict) else {}
            poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
            poetry_deps = poetry.get("dependencies") if isinstance(poetry.get("dependencies"), dict) else {}
            poetry_groups = poetry.get("group") if isinstance(poetry.get("group"), dict) else {}
            for name, version in self._dependency_items(poetry_deps):
                if name.lower() != "python":
                    profile.dependencies.append(
                        WorkspaceDependency(name=name, version=version, source="pyproject.toml", group="runtime")
                    )
            dev_group = poetry_groups.get("dev") if isinstance(poetry_groups.get("dev"), dict) else {}
            dev_deps = dev_group.get("dependencies") if isinstance(dev_group.get("dependencies"), dict) else {}
            for name, version in self._dependency_items(dev_deps):
                profile.dev_dependencies.append(
                    WorkspaceDependency(name=name, version=version, source="pyproject.toml", group="development")
                )

            python_names = self._python_dependency_names(profile)
            self._add_named_matches(profile.frameworks, python_names, PYTHON_FRAMEWORKS)
            self._add_named_matches(profile.database_tools, python_names, DATABASE_TOOLS)
            self._add_python_validation_commands(profile, python_names)

        requirements = root / "requirements.txt"
        if self._path_is_file(requirements):
            self._add_unique(profile.config_files, "requirements.txt")
            self._add_unique(profile.languages, "Python")
            self._add_unique(profile.package_managers, "pip")
            self._add_unique(profile.install_commands, "python -m pip install -r requirements.txt")
            for line in self._read_small_text(requirements).splitlines():
                dependency = self._dependency_from_requirement_line(line, "requirements.txt")
                if dependency:
                    profile.dependencies.append(dependency)

            python_names = self._python_dependency_names(profile)
            self._add_named_matches(profile.frameworks, python_names, PYTHON_FRAMEWORKS)
            self._add_named_matches(profile.database_tools, python_names, DATABASE_TOOLS)
            self._add_python_validation_commands(profile, python_names)

    def _inspect_cargo_manifest(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        path = root / "Cargo.toml"
        payload = self._read_toml_object(path)
        if payload is None:
            return

        self._add_unique(profile.config_files, "Cargo.toml")
        self._add_unique(profile.languages, "Rust")
        self._add_unique(profile.package_managers, "cargo")
        self._add_unique(profile.build_systems, "Cargo")
        self._add_unique(profile.install_commands, "cargo fetch")
        self._add_unique(profile.validation_commands, "cargo build")
        self._add_unique(profile.validation_commands, "cargo test")

        deps = payload.get("dependencies") if isinstance(payload.get("dependencies"), dict) else {}
        dev_deps = payload.get("dev-dependencies") if isinstance(payload.get("dev-dependencies"), dict) else {}
        for name, version in self._dependency_items(deps):
            profile.dependencies.append(
                WorkspaceDependency(name=name, version=version, source="Cargo.toml", group="runtime")
            )
        for name, version in self._dependency_items(dev_deps):
            profile.dev_dependencies.append(
                WorkspaceDependency(name=name, version=version, source="Cargo.toml", group="development")
            )

    def _inspect_go_mod(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        path = root / "go.mod"
        if not self._path_is_file(path):
            return

        self._add_unique(profile.config_files, "go.mod")
        self._add_unique(profile.languages, "Go")
        self._add_unique(profile.package_managers, "go")
        self._add_unique(profile.build_systems, "Go modules")
        self._add_unique(profile.install_commands, "go mod download")
        self._add_unique(profile.validation_commands, "go test ./...")
        self._add_unique(profile.validation_commands, "go build ./...")

        for line in self._read_small_text(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped in {"require (", ")"}:
                continue
            if stripped.startswith("require "):
                stripped = stripped[len("require ") :].strip()
            parts = stripped.split()
            if len(parts) >= 2 and "/" in parts[0]:
                profile.dependencies.append(
                    WorkspaceDependency(name=parts[0], version=parts[1], source="go.mod", group="runtime")
                )

    def _inspect_dotnet_projects(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        for path in self._bounded_glob(root, "*.csproj", max_items=6):
            relative = path.relative_to(root).as_posix()
            self._add_unique(profile.config_files, relative)
            self._add_unique(profile.languages, "C#")
            self._add_unique(profile.package_managers, "dotnet")
            self._add_unique(profile.build_systems, ".NET")
            self._add_unique(profile.install_commands, "dotnet restore")
            self._add_unique(profile.validation_commands, "dotnet build")
            self._add_unique(profile.validation_commands, "dotnet test")
            try:
                tree = ET.parse(path)
            except (ET.ParseError, OSError):
                profile.warnings.append(f"Could not parse {relative}.")
                continue
            for item in [*tree.findall(".//PackageReference"), *tree.findall(".//{*}PackageReference")]:
                name = item.attrib.get("Include") or item.attrib.get("Update") or ""
                version = item.attrib.get("Version") or ""
                if name:
                    profile.dependencies.append(
                        WorkspaceDependency(name=name, version=version, source=relative, group="runtime")
                    )

    def _inspect_workspace_build_runners(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        if self._path_is_file(root / "build.py"):
            self._add_unique(profile.config_files, "build.py")
            self._add_unique(profile.validation_commands, "python build.py")
        if self._path_is_file(root / "build.ps1"):
            self._add_unique(profile.config_files, "build.ps1")
            self._add_unique(profile.validation_commands, POWERSHELL_BUILD_COMMAND)

    def _has_workspace_build_runner(self, root: Path) -> bool:
        return self._path_is_file(root / "build.py") or self._path_is_file(root / "build.ps1")

    def _inspect_cmake(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        path = root / "CMakeLists.txt"
        if not self._path_is_file(path):
            return
        self._add_unique(profile.config_files, "CMakeLists.txt")
        self._add_unique(profile.languages, "C")
        self._add_unique(profile.languages, "C++")
        self._add_unique(profile.package_managers, "cmake")
        self._add_unique(profile.build_systems, "CMake")
        if self._has_workspace_build_runner(root):
            return
        self._add_unique(profile.validation_commands, "cmake --build build")
        self._add_unique(profile.validation_commands, "ctest --test-dir build")

    def _inspect_visual_studio_projects(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        solutions = self._bounded_glob(root, "*.sln", max_items=8)
        native_projects = self._bounded_glob(root, "*.vcxproj", max_items=12)
        if not solutions and not native_projects:
            return

        self._add_unique(profile.languages, "C++")
        self._add_unique(profile.package_managers, "msbuild")
        self._add_unique(profile.build_systems, "Visual Studio / MSBuild")
        has_build_runner = self._has_workspace_build_runner(root)

        for solution in solutions:
            relative = solution.relative_to(root).as_posix()
            self._add_unique(profile.config_files, relative)
            if not has_build_runner:
                self._add_unique(profile.validation_commands, f"msbuild {relative} /m /p:Configuration=Release")

        for project in native_projects:
            relative = project.relative_to(root).as_posix()
            self._add_unique(profile.config_files, relative)
            if not has_build_runner:
                self._add_unique(profile.validation_commands, f"msbuild {relative} /m /p:Configuration=Release")
            filters = project.with_suffix(project.suffix + ".filters")
            if self._path_is_file(filters):
                self._add_unique(profile.config_files, filters.relative_to(root).as_posix())

    def _inspect_native_code_conventions(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        candidates: list[Path] = []
        for relative in ("CMakeLists.txt", "Makefile", "premake5.lua", "xmake.lua"):
            path = root / relative
            if self._path_is_file(path):
                candidates.append(path)
        for pattern in (
            "*.vcxproj",
            "*.props",
            "*.targets",
            "*.cmake",
            "*.def",
            "*.dll",
            "*.lib",
            "*.exp",
            "*.pdb",
            "*.cpp",
            "*.c",
            "*.h",
            "*.hpp",
            "*.rc",
            "*.hlsl",
            "*.glsl",
            "src/**/*.cpp",
            "src/**/*.c",
            "src/**/*.h",
            "src/**/*.hpp",
            "include/**/*.h",
            "include/**/*.hpp",
            "shaders/**/*.*",
        ):
            candidates.extend(self._bounded_glob(root, pattern, max_items=24))

        seen_paths: set[Path] = set()
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            relative = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            text = self._read_small_text(path).lower()

            if suffix in {".c", ".h"}:
                self._add_unique(profile.languages, "C")
            if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hxx", ".inl", ".ipp", ".ixx"}:
                self._add_unique(profile.languages, "C++")
            if suffix == ".rc":
                self._add_unique(profile.languages, "Windows Resource Script")
            if suffix in {".dll", ".lib", ".exp", ".pdb"}:
                self._add_unique(profile.languages, "C++")
                self._add_unique(profile.frameworks, "DLL/Shared Library")
                self._add_native_dependency(profile, "DLL/shared-library artifact", relative)
            if suffix == ".hlsl":
                self._add_unique(profile.languages, "HLSL")
            if suffix == ".glsl":
                self._add_unique(profile.languages, "GLSL")
            if suffix in {".asm", ".s"}:
                self._add_unique(profile.languages, "Assembly")

            if not text:
                continue

            if any(
                token in text
                for token in (
                    "__declspec(dllexport)",
                    "__declspec(dllimport)",
                    "dllmain",
                    "<configurationtype>dynamiclibrary",
                    "add_library",
                    " shared",
                )
            ):
                self._add_unique(profile.frameworks, "DLL/Shared Library")
                self._add_native_dependency(profile, "DLL/shared-library source", relative)
            if any(token in text for token in ("imgui.h", "dear imgui", "imgui::")):
                self._add_native_dependency(profile, "Dear ImGui", relative)
                self._add_unique(profile.frameworks, "Dear ImGui")
            if any(token in text for token in ("windows.h", "winuser.h", "processthreadsapi.h", "tlhelp32.h")):
                self._add_unique(profile.frameworks, "Win32 API")
            if any(token in text for token in ("d3d11.h", "d3d12.h", "dxgi.h", "directx")):
                self._add_native_dependency(profile, "DirectX", relative)
                self._add_unique(profile.frameworks, "DirectX")
            if any(token in text for token in ("vulkan/vulkan.h", "vkcreate", "vkinstance")):
                self._add_native_dependency(profile, "Vulkan", relative)
                self._add_unique(profile.frameworks, "Vulkan")
            if any(token in text for token in ("glfw/glfw3.h", "glfwinit")):
                self._add_native_dependency(profile, "GLFW", relative)
                self._add_unique(profile.frameworks, "GLFW")
            if any(token in text for token in ("sdl.h", "sdl2/sdl.h", "sdl_init")):
                self._add_native_dependency(profile, "SDL", relative)
                self._add_unique(profile.frameworks, "SDL")
            if any(token in text for token in ("minhook.h", "mh_initialize", "mh_createhook")):
                self._add_native_dependency(profile, "MinHook", relative)
                self._add_unique(profile.frameworks, "MinHook")
            if any(token in text for token in ("detours.h", "detourattach", "detourtransactionbegin")):
                self._add_native_dependency(profile, "Microsoft Detours", relative)
                self._add_unique(profile.frameworks, "Microsoft Detours")
            if any(token in text for token in ("capstone/capstone.h", "cs_open(", "cs_disasm")):
                self._add_native_dependency(profile, "Capstone", relative)
                self._add_unique(profile.frameworks, "Capstone")
            if any(token in text for token in ("lief/", "pefile", "image_nt_headers", "image_dos_header")):
                self._add_unique(profile.frameworks, "PE/COFF analysis")
            if any(token in text for token in ("idaapi", "idc.", "ghidra", "yara_rule", "yara.h")):
                self._add_unique(profile.frameworks, "Reverse engineering tooling")

    def _inspect_java_manifests(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        pom = root / "pom.xml"
        if self._path_is_file(pom):
            self._add_unique(profile.config_files, "pom.xml")
            self._add_unique(profile.languages, "Java")
            self._add_unique(profile.package_managers, "maven")
            self._add_unique(profile.build_systems, "Maven")
            self._add_unique(profile.install_commands, "mvn dependency:resolve")
            self._add_unique(profile.validation_commands, "mvn test")
            self._add_unique(profile.validation_commands, "mvn package")
            try:
                tree = ET.parse(pom)
            except (ET.ParseError, OSError):
                profile.warnings.append("Could not parse pom.xml.")
            else:
                for dependency in tree.findall(".//{*}dependency"):
                    group_id = dependency.findtext("{*}groupId") or ""
                    artifact_id = dependency.findtext("{*}artifactId") or ""
                    version = dependency.findtext("{*}version") or ""
                    if artifact_id:
                        name = f"{group_id}:{artifact_id}" if group_id else artifact_id
                        profile.dependencies.append(
                            WorkspaceDependency(name=name, version=version, source="pom.xml", group="runtime")
                        )

        for gradle in ("build.gradle", "build.gradle.kts"):
            path = root / gradle
            if not self._path_is_file(path):
                continue
            self._add_unique(profile.config_files, gradle)
            self._add_unique(profile.languages, "Java")
            if gradle.endswith(".kts"):
                self._add_unique(profile.languages, "Kotlin")
            self._add_unique(profile.package_managers, "gradle")
            self._add_unique(profile.build_systems, "Gradle")
            self._add_unique(profile.validation_commands, "./gradlew test")
            self._add_unique(profile.validation_commands, "./gradlew build")

    def _inspect_database_files(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        prisma = root / "prisma" / "schema.prisma"
        if self._path_is_file(prisma):
            self._add_unique(profile.config_files, "prisma/schema.prisma")
            self._add_unique(profile.database_tools, "Prisma")
            self._add_unique(profile.validation_commands, "npx prisma validate")
        if self._path_is_dir(root / "migrations") or self._workspace_has_suffix(root, ".sql"):
            self._add_unique(profile.languages, "SQL")
            self._add_unique(profile.database_tools, "SQL migrations")

    def _detect_entry_points(self, root: Path, profile: WorkspaceDependencyProfile) -> None:
        candidates = [
            "app/page.tsx",
            "pages/index.tsx",
            "src/main.tsx",
            "src/App.tsx",
            "src/main/index.ts",
            "src/main.ts",
            "src/index.ts",
            "src/index.js",
            "App.tsx",
            "manage.py",
            "main.py",
            "src/main.py",
            "src/main.cpp",
            "main.cpp",
            "src/main.c",
            "main.c",
            "src/main.rs",
            "cmd/server/main.go",
            "main.go",
            "Program.cs",
            "src/Program.cs",
            "controller/main.cpp",
            "driver/driver.c",
        ]
        for relative in candidates:
            if self._path_is_file(root / relative):
                self._add_unique(profile.entry_points, relative)

        for pattern in ("tests/test_*.py", "test_*.py", "src/**/*.test.ts", "src/**/*.test.tsx", "tests/**/*.cs"):
            for path in self._bounded_glob(root, pattern, max_items=16):
                self._add_unique(profile.test_files, path.relative_to(root).as_posix())

    def _finalize_dependency_profile(self, profile: WorkspaceDependencyProfile) -> None:
        profile.project_type = self._infer_project_type(profile)
        profile.languages = self._dedupe(profile.languages, limit=24)
        profile.frameworks = self._dedupe(profile.frameworks, limit=32)
        profile.package_managers = self._dedupe(profile.package_managers, limit=16)
        profile.build_systems = self._dedupe(profile.build_systems, limit=16)
        profile.config_files = self._dedupe(profile.config_files, limit=48)
        profile.entry_points = self._dedupe(profile.entry_points, limit=32)
        profile.test_files = self._dedupe(profile.test_files, limit=32)
        profile.install_commands = self._dedupe(profile.install_commands, limit=16)
        profile.validation_commands = self._dedupe(profile.validation_commands, limit=24)
        profile.database_tools = self._dedupe(profile.database_tools, limit=24)
        profile.warnings = self._dedupe(profile.warnings, limit=12)
        profile.scripts = self._dedupe_scripts(profile.scripts, limit=48)
        profile.dependencies = self._dedupe_dependencies(profile.dependencies, limit=96)
        profile.dev_dependencies = self._dedupe_dependencies(profile.dev_dependencies, limit=96)
        if not profile.config_files:
            profile.warnings.append("No dependency or build manifest was detected.")

    @staticmethod
    def _infer_project_type(profile: WorkspaceDependencyProfile) -> str:
        frameworks = {item.lower() for item in profile.frameworks}
        build_systems = {item.lower() for item in profile.build_systems}
        languages = {item.lower() for item in profile.languages}
        if "electron" in frameworks or "tauri" in frameworks:
            return "desktop-app"
        if "next.js" in frameworks or "vite" in frameworks or "react" in frameworks:
            return "web-app"
        if "fastapi" in frameworks or "express" in frameworks or "asp.net core minimal api" in frameworks:
            return "api-service"
        if "django" in frameworks:
            return "server-rendered-web"
        if "visual studio / msbuild" in build_systems or "cmake" in build_systems:
            return "native-app"
        if "rust" in languages or "go" in languages:
            return "compiled-service"
        if "python" in languages:
            return "python-project"
        if "sql" in languages:
            return "database-project"
        return ""

    def _create_checkpoint(self, root: Path, changes: list[FileChange]) -> str | None:
        checkpoint_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        checkpoint_root = root / ".aegis" / "checkpoints" / checkpoint_id
        manifest: list[dict[str, str]] = []

        for change in changes:
            try:
                target = self._safe_path(root, change.path)
            except ValueError:
                continue

            entry = {"path": change.path, "state": "missing"}
            if target.exists() and target.is_file():
                backup = checkpoint_root / "files" / change.path
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                entry["state"] = "present"
            manifest.append(entry)

        if not manifest:
            return None

        checkpoint_root.mkdir(parents=True, exist_ok=True)
        (checkpoint_root / "manifest.json").write_text(
            json.dumps({"id": checkpoint_id, "files": manifest}, indent=2),
            encoding="utf-8",
        )
        return checkpoint_id

    def _checkpoint_created_at(self, checkpoint_id: str, checkpoint_root: Path) -> str:
        prefix = checkpoint_id.split("-", 1)[0]
        try:
            return datetime.strptime(prefix, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

        try:
            return datetime.fromtimestamp(checkpoint_root.stat().st_mtime, timezone.utc).isoformat()
        except OSError:
            return ""

    def _read_small_text(self, path: Path, max_bytes: int = 512_000) -> str:
        try:
            if not self._path_is_file(path) or path.stat().st_size > max_bytes:
                return ""
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _path_is_file(self, path: Path) -> bool:
        try:
            return path.is_file()
        except OSError:
            return False

    def _path_is_dir(self, path: Path) -> bool:
        try:
            return path.is_dir()
        except OSError:
            return False

    def _instruction_scan_dirs(self, relative_dir: str, dirs: list[str]) -> list[str]:
        allowed: list[str] = []
        in_aegis = relative_dir == ".aegis" or relative_dir.startswith(".aegis/")
        for name in dirs:
            if name in {"checkpoints", "node_modules", "dist", "build", ".next", "__pycache__"}:
                continue
            if name == ".aegis":
                allowed.append(name)
                continue
            if name in IGNORE_NAMES:
                continue
            if name.startswith("."):
                continue
            if in_aegis and name not in {"docs"}:
                continue
            allowed.append(name)
        return allowed

    def _could_be_instruction_file(self, path: Path, *, referenced: bool = False) -> bool:
        name = path.name
        if name in IGNORE_NAMES:
            return False
        suffix = path.suffix.lower()
        extensionless_name = name.lower()
        allowed_suffix = suffix in INSTRUCTION_FILE_SUFFIXES
        allowed_extensionless = extensionless_name in INSTRUCTION_EXTENSIONLESS_NAMES
        if referenced and not suffix and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.()@+\-]{0,119}", name):
            return True
        if not allowed_suffix and not allowed_extensionless:
            return False
        if suffix == ".txt" and path.name.lower().endswith((".log.txt", ".err.txt")):
            return False
        return True

    def _instruction_file_from_text(
        self,
        relative_path: str,
        text: str,
        *,
        referenced_score: float = 0.0,
    ) -> WorkspaceInstructionFile | None:
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        stripped = normalized_text.strip()
        if not stripped:
            return None

        title = self._instruction_title(relative_path, normalized_text)
        pending_items: list[str] = []
        completed_count = 0
        total_items = 0
        content_hits = 0
        heading_hits = 0
        first_relevant_lines: list[str] = []
        section_instruction_context = False

        for raw_line in normalized_text.splitlines():
            line = raw_line.strip()
            lowered = line.lower()
            if not line:
                continue

            checkbox = CHECKBOX_RE.match(line)
            if checkbox:
                total_items += 1
                item_text = self._clean_instruction_item(checkbox.group("text"))
                if checkbox.group("mark").lower() == "x":
                    completed_count += 1
                elif item_text and len(pending_items) < 12:
                    pending_items.append(item_text)
                if item_text and len(first_relevant_lines) < 18:
                    first_relevant_lines.append(raw_line.rstrip())
                continue

            heading = HEADING_RE.match(line)
            if heading:
                section_instruction_context = self._heading_looks_instruction_context(heading.group("title"))
                if section_instruction_context:
                    heading_hits += 1
                    content_hits += 1
                    if len(first_relevant_lines) < 18:
                        first_relevant_lines.append(raw_line.rstrip())
                continue

            bullet = BULLET_RE.match(line)
            if bullet and (
                (section_instruction_context and bullet.group("marker") in {"-", "*", "+"})
                or self._line_looks_actionable(bullet.group("text"))
                or (referenced_score > 0 and self._line_looks_instruction_item(bullet.group("text")))
            ):
                total_items += 1
                item_text = self._clean_instruction_item(bullet.group("text"))
                if item_text and len(pending_items) < 12:
                    pending_items.append(item_text)
                if item_text and len(first_relevant_lines) < 18:
                    first_relevant_lines.append(raw_line.rstrip())
                continue

            if self._line_looks_instruction_context(line):
                content_hits += 1
                section_instruction_context = True
                if len(first_relevant_lines) < 18:
                    first_relevant_lines.append(raw_line.rstrip())
                continue

        pending_count = max(0, total_items - completed_count)
        name_score = self._instruction_name_score(relative_path)
        content_score = min(0.5, (content_hits * 0.08) + (heading_hits * 0.04) + (pending_count * 0.06) + (completed_count * 0.02))
        if pending_count:
            content_score += 0.2
        score = min(1.0, name_score + content_score + referenced_score)

        if score < 0.22 and referenced_score <= 0:
            return None
        if referenced_score > 0:
            score = max(score, 0.64)

        excerpt_source = "\n".join(first_relevant_lines) if first_relevant_lines else stripped
        excerpt = self._bounded_text(excerpt_source, 1800)
        summary_bits: list[str] = []
        if pending_count or completed_count:
            summary_bits.append(f"{pending_count} open / {total_items} tracked item(s)")
        if name_score >= 0.25:
            summary_bits.append("filename suggests project instructions")
        if content_hits:
            summary_bits.append(f"{content_hits} planning keyword hit(s)")
        if heading_hits:
            summary_bits.append(f"{heading_hits} instruction heading(s)")
        if referenced_score > 0:
            summary_bits.append("referenced by prompt")
        if not summary_bits:
            summary_bits.append("content looks like project guidance")

        return WorkspaceInstructionFile(
            path=relative_path,
            title=title,
            kind="todo" if pending_count else "instruction",
            score=round(score, 3),
            pending_count=pending_count,
            completed_count=completed_count,
            total_items=total_items,
            pending_items=pending_items,
            summary="; ".join(summary_bits),
            excerpt=excerpt,
        )

    def _instruction_title(self, relative_path: str, text: str) -> str:
        for line in text.splitlines()[:24]:
            match = HEADING_RE.match(line)
            if match:
                title = match.group("title").strip(" #\t")
                if title:
                    return title[:120]
        return Path(relative_path).stem.replace("_", " ").replace("-", " ").strip().title()[:120]

    def _instruction_name_score(self, relative_path: str) -> float:
        lowered = relative_path.lower().replace("\\", "/")
        stem_text = re.sub(r"[^a-z0-9]+", " ", Path(lowered).stem)
        path_text = re.sub(r"[^a-z0-9/.]+", " ", lowered)
        if lowered == ".aegis/roadmap.md":
            return 0.54
        score = 0.0
        for term in INSTRUCTION_NAME_TERMS:
            if term in stem_text.split():
                score += 0.18
            elif term in path_text:
                score += 0.08
        if Path(lowered).name in {"todo.md", "tasks.md", "roadmap.md", "backlog.md"}:
            score += 0.28
        return min(0.56, score)

    def _instruction_sort_priority(self, relative_path: str) -> int:
        lowered = relative_path.lower().replace("\\", "/")
        basename = lowered.split("/")[-1]
        if lowered == ".aegis/roadmap.md":
            return 4
        if basename in {"todo.md", "tasks.md", "roadmap.md", "backlog.md", "project_todo.md"}:
            return 3
        if basename in {"todo", "tasks", "roadmap", "backlog", "tasklist", "workplan"}:
            return 2
        if any(term in basename for term in ("plan", "blueprint", "checklist", "milestone", "requirements")):
            return 1
        return 0

    def _heading_looks_instruction_context(self, text: str) -> bool:
        lowered = " ".join(text.strip().lower().split())
        if not lowered:
            return False
        if any(term in lowered for term in INSTRUCTION_CONTENT_TERMS):
            return True
        return bool(
            re.search(
                r"\b("
                r"acceptance|backlog|blueprint|build|checklist|deliverables?|features?|fixes?|goals?|"
                r"issues?|launch|milestones?|mvp|next|phase|plan|remaining|requirements?|roadmap|"
                r"scope|ship|sprint|tasks?|todo|validation|work"
                r")\b",
                lowered,
            )
        )

    def _line_looks_instruction_context(self, text: str) -> bool:
        lowered = " ".join(text.strip().lower().strip(":").split())
        if not lowered or self._line_has_metadata_label(lowered):
            return False
        if any(term in lowered for term in INSTRUCTION_CONTENT_TERMS):
            return True
        return bool(
            re.fullmatch(
                r"(?:phase\s+\d+|mvp|next\s+steps?|known\s+issues?|acceptance\s+criteria|"
                r"validation\s+plan|build\s+plan|release\s+plan|launch\s+plan|work\s+items?)",
                lowered,
            )
        )

    def _referenced_instruction_keys(self, text: str) -> set[str]:
        lowered = text.lower().replace("\\", "/")
        if not lowered:
            return set()

        keys: set[str] = set()
        suffix_pattern = "|".join(
            re.escape(suffix.lstrip("."))
            for suffix in sorted(INSTRUCTION_FILE_SUFFIXES, key=len, reverse=True)
        )
        quoted_pattern = re.compile(rf"['\"`](?P<path>[^'\"`]+\.({suffix_pattern}))['\"`]")
        unquoted_pattern = re.compile(rf"(?P<path>[a-z0-9_./()@+\-]+\.({suffix_pattern}))")

        for pattern in (quoted_pattern, unquoted_pattern):
            for match in pattern.finditer(lowered):
                candidate = match.group("path").strip(" \t\r\n'\"`.,:;!?)]}")
                candidate = re.sub(r"\s+", " ", candidate)
                if not candidate or len(candidate) > 220:
                    continue
                keys.add(candidate)
                keys.add(candidate.split("/")[-1])

        extensionless_reference_pattern = re.compile(
            r"(?:from|use|using|follow|open|read|load|recognize)\s+"
            r"(?P<path>[a-z0-9_./()@+\-]{2,160})(?=$|[\s.,:;!?)]| for | as | to )"
        )
        for match in extensionless_reference_pattern.finditer(lowered):
            candidate = match.group("path").strip(" \t\r\n'\"`.,:;!?)]}")
            if not candidate or "." in candidate.split("/")[-1]:
                continue
            keys.add(candidate)
            keys.add(candidate.split("/")[-1])
        return keys

    def _instruction_reference_score(self, relative_path: str, referenced_keys: set[str]) -> float:
        if not referenced_keys:
            return 0.0
        lowered = relative_path.lower().replace("\\", "/")
        basename = lowered.split("/")[-1]
        if lowered in referenced_keys or basename in referenced_keys:
            return 0.44
        if any(key and (lowered.endswith(f"/{key}") or key in lowered) for key in referenced_keys):
            return 0.28
        return 0.0

    def _line_looks_actionable(self, text: str) -> bool:
        lowered = text.strip().lower()
        if len(lowered) < 10 or len(lowered) > 240:
            return False
        if self._line_has_metadata_label(lowered):
            return False
        action_terms = (
            "add",
            "build",
            "create",
            "fix",
            "implement",
            "integrate",
            "make",
            "refactor",
            "remove",
            "replace",
            "test",
            "update",
            "validate",
            "wire",
        )
        return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in action_terms)

    def _line_looks_instruction_item(self, text: str) -> bool:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) < 3 or len(cleaned) > 240:
            return False
        if cleaned.startswith(("http://", "https://", "![", "<img")):
            return False
        if self._line_has_metadata_label(cleaned):
            return False
        return any(char.isalpha() for char in cleaned)

    @staticmethod
    def _line_has_metadata_label(text: str) -> bool:
        cleaned = " ".join(text.strip().split())
        if ":" not in cleaned:
            return False
        label = cleaned.split(":", 1)[0].strip().lower()
        return label in {
            "checkpoint",
            "created",
            "framework",
            "install",
            "install command",
            "language",
            "package",
            "package manager",
            "preset",
            "project",
            "schema",
            "stack",
            "tags",
            "validate",
            "validation",
            "validation command",
        }

    def _clean_instruction_item(self, text: str) -> str:
        cleaned = " ".join(text.strip().split())
        cleaned = re.sub(r"\s+#.*$", "", cleaned).strip()
        return cleaned[:220]

    def _bounded_text(self, text: str, max_chars: int) -> str:
        cleaned = text.strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max(0, max_chars - 14)].rstrip() + "\n... [truncated]"

    def _bounded_tail_text(self, text: str, max_chars: int) -> str:
        cleaned = text.strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return "... [truncated]\n" + cleaned[-max(0, max_chars - 16) :].lstrip()

    def _relative_posix(self, path: Path, root: Path) -> str:
        try:
            relative = path.relative_to(root)
        except ValueError:
            return ""
        value = relative.as_posix()
        return "" if value == "." else value

    def _read_json_object(self, path: Path) -> dict[str, Any] | None:
        text = self._read_small_text(path)
        if not text:
            return None
        try:
            payload = json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _read_toml_object(self, path: Path) -> dict[str, Any] | None:
        try:
            if not self._path_is_file(path) or path.stat().st_size > 512_000:
                return None
            payload = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, tomllib.TOMLDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _bounded_glob(self, root: Path, pattern: str, *, max_items: int = 12) -> list[Path]:
        matches: list[Path] = []
        for path in root.rglob(pattern):
            try:
                relative_parts = path.relative_to(root).parts
            except ValueError:
                continue
            if any(part in IGNORE_NAMES for part in relative_parts):
                continue
            if not self._path_is_file(path):
                continue
            matches.append(path)
            if len(matches) >= max_items:
                break
        return matches

    def _workspace_has_suffix(self, root: Path, suffix: str, *, max_scan: int = 2_000) -> bool:
        scanned = 0
        for current, dirs, names in os.walk(root):
            dirs[:] = [name for name in dirs if name not in IGNORE_NAMES and not name.startswith(".")]
            for name in names:
                scanned += 1
                if scanned > max_scan:
                    return False
                if name.lower().endswith(suffix.lower()):
                    return True
        return False

    def _dependency_items(self, value: Any) -> list[tuple[str, str]]:
        if not isinstance(value, dict):
            return []
        items: list[tuple[str, str]] = []
        for raw_name, raw_version in value.items():
            name = str(raw_name).strip()
            if not name:
                continue
            if isinstance(raw_version, dict):
                version = str(raw_version.get("version") or raw_version.get("path") or raw_version.get("git") or "").strip()
            else:
                version = str(raw_version).strip()
            items.append((name, version))
        return items

    def _dependency_from_spec(self, spec: str, source: str, group: str) -> WorkspaceDependency | None:
        cleaned = spec.split(";", 1)[0].strip()
        if not cleaned:
            return None
        match = re.match(r"^([A-Za-z0-9_.-]+(?:\[[^\]]+\])?)\s*(.*)$", cleaned)
        if not match:
            return None
        name = match.group(1).strip()
        version = match.group(2).strip()
        return WorkspaceDependency(name=name, version=version, source=source, group=group)

    def _dependency_from_requirement_line(self, line: str, source: str) -> WorkspaceDependency | None:
        cleaned = line.split("#", 1)[0].strip()
        if not cleaned or cleaned.startswith(("-", "http:", "https:", "git+")):
            return None
        return self._dependency_from_spec(cleaned, source, "runtime")

    def _node_package_manager(self, root: Path, payload: dict[str, Any]) -> str:
        raw = str(payload.get("packageManager") or "").lower()
        if raw.startswith("pnpm"):
            return "pnpm"
        if raw.startswith("yarn"):
            return "yarn"
        if raw.startswith("bun"):
            return "bun"
        if raw.startswith("npm"):
            return "npm"
        if self._path_is_file(root / "pnpm-lock.yaml"):
            return "pnpm"
        if self._path_is_file(root / "yarn.lock"):
            return "yarn"
        if self._path_is_file(root / "bun.lockb") or self._path_is_file(root / "bun.lock"):
            return "bun"
        return "npm"

    def _node_install_command(self, package_manager: str) -> str:
        if package_manager == "pnpm":
            return "pnpm install"
        if package_manager == "yarn":
            return "yarn install"
        if package_manager == "bun":
            return "bun install"
        return "npm install"

    def _node_run_command(self, package_manager: str, script: str) -> str:
        if package_manager == "pnpm":
            return f"pnpm {script}"
        if package_manager == "yarn":
            return f"yarn {script}"
        if package_manager == "bun":
            return f"bun run {script}"
        return f"npm run {script}"

    def _node_validation_commands(self, package_manager: str, scripts: dict[Any, Any]) -> list[str]:
        preferred = ("check", "typecheck", "lint", "test", "build")
        commands: list[str] = []
        for script in preferred:
            if script in scripts:
                commands.append(self._node_run_command(package_manager, script))
        return commands

    def _node_dependency_names(self, payload: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            for name, _version in self._dependency_items(payload.get(section)):
                names.add(name.lower())
        return names

    def _python_package_manager(self, root: Path, payload: dict[str, Any]) -> str:
        tool = payload.get("tool") if isinstance(payload.get("tool"), dict) else {}
        if self._path_is_file(root / "uv.lock") or "uv" in tool:
            return "uv"
        if self._path_is_file(root / "poetry.lock") or "poetry" in tool:
            return "poetry"
        if self._path_is_file(root / "pdm.lock") or "pdm" in tool:
            return "pdm"
        return "pip"

    def _python_install_command(self, package_manager: str) -> str:
        if package_manager == "uv":
            return "uv sync"
        if package_manager == "poetry":
            return "poetry install"
        if package_manager == "pdm":
            return "pdm install"
        return "python -m pip install -e ."

    def _python_dependency_names(self, profile: WorkspaceDependencyProfile) -> set[str]:
        names: set[str] = set()
        for dependency in [*profile.dependencies, *profile.dev_dependencies]:
            normalized = dependency.name.split("[", 1)[0].lower().replace("_", "-")
            if normalized:
                names.add(normalized)
        return names

    def _add_python_validation_commands(self, profile: WorkspaceDependencyProfile, names: set[str]) -> None:
        if "pytest" in names:
            self._add_unique(profile.validation_commands, "python -m pytest")
        if "ruff" in names:
            self._add_unique(profile.validation_commands, "python -m ruff check .")
        if "mypy" in names:
            self._add_unique(profile.validation_commands, "python -m mypy .")
        if "pyright" in names:
            self._add_unique(profile.validation_commands, "python -m pyright")

    def _add_named_matches(self, target: list[str], names: set[str], mapping: dict[str, str]) -> None:
        for key, label in mapping.items():
            if key.lower() in names:
                self._add_unique(target, label)

    @staticmethod
    def _add_native_dependency(profile: WorkspaceDependencyProfile, name: str, source: str) -> None:
        if any(item.name.lower() == name.lower() and item.group == "native" for item in profile.dependencies):
            return
        profile.dependencies.append(WorkspaceDependency(name=name, source=source, group="native"))

    @staticmethod
    def _add_unique(values: list[str], value: str) -> None:
        cleaned = str(value).strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)

    @staticmethod
    def _dedupe(values: list[str], *, limit: int) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _dedupe_dependencies(dependencies: list[WorkspaceDependency], *, limit: int) -> list[WorkspaceDependency]:
        out: list[WorkspaceDependency] = []
        seen: set[tuple[str, str, str]] = set()
        for dependency in dependencies:
            key = (dependency.name.lower(), dependency.source.lower(), dependency.group.lower())
            if not dependency.name or key in seen:
                continue
            seen.add(key)
            out.append(dependency)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _dedupe_scripts(scripts: list[WorkspaceScript], *, limit: int) -> list[WorkspaceScript]:
        out: list[WorkspaceScript] = []
        seen: set[tuple[str, str]] = set()
        for script in scripts:
            key = (script.name.lower(), script.source.lower())
            if not script.name or key in seen:
                continue
            seen.add(key)
            out.append(script)
            if len(out) >= limit:
                break
        return out

    def _safe_path(self, root: Path, relative_path: str) -> Path:
        workspace_root = root.resolve()
        self._ensure_within_allowed_roots(workspace_root)

        raw = relative_path.strip()
        if not raw:
            raise ValueError("path is empty")

        candidate = Path(raw)
        if candidate.is_absolute():
            raise ValueError("path must be relative to the workspace")

        target = (workspace_root / candidate).resolve()

        try:
            target.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError("file change points outside the workspace") from exc

        if target == workspace_root:
            raise ValueError("path must point to a file inside the workspace, not the workspace root")

        return target

    def _safe_checkpoint_root(self, workspace_root: Path, checkpoint_id: str) -> Path:
        raw = checkpoint_id.strip()
        if not raw:
            raise ValueError("checkpoint id is empty")

        candidate = Path(raw)
        if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.parts[0] in {".", ".."}:
            raise ValueError("checkpoint id must be a checkpoint folder name")

        checkpoints_root = (workspace_root / ".aegis" / "checkpoints").resolve()
        checkpoint_root = (checkpoints_root / candidate).resolve()
        try:
            checkpoint_root.relative_to(checkpoints_root)
        except ValueError as exc:
            raise ValueError("checkpoint points outside the workspace checkpoint folder") from exc
        return checkpoint_root

    def _resolve_configured_workspace_root(self, value: str | None) -> Path | None:
        raw = (value or "").strip()
        if not raw:
            return None
        candidate = Path(raw).expanduser()
        return candidate.resolve() if candidate.is_absolute() else (self.project_root / candidate).resolve()

    def _resolve_additional_workspace_roots(self, value: str | None) -> list[Path]:
        roots: list[Path] = []
        for raw in re.split(r"[;\n\r]+", value or ""):
            item = raw.strip().strip('"')
            if not item:
                continue
            candidate = Path(item).expanduser()
            root = candidate.resolve() if candidate.is_absolute() else (self.project_root / candidate).resolve()
            if root not in roots:
                roots.append(root)
        return roots

    def _ensure_within_allowed_roots(self, path: Path) -> None:
        resolved = path.resolve()
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return
            except ValueError:
                continue

        if self.settings.aegis_allow_explicit_workspace_paths and self._is_safe_explicit_workspace_path(resolved):
            return

        allowed = ", ".join(str(root) for root in self.allowed_roots)
        if self.settings.aegis_allow_explicit_workspace_paths:
            raise ValueError(
                "workspace root must stay inside an allowed workspace root or be an explicit non-system project path "
                f"({allowed})"
            )
        raise ValueError(f"workspace root must stay inside an allowed workspace root ({allowed})")

    def _is_safe_explicit_workspace_path(self, path: Path) -> bool:
        resolved = path.resolve()
        if resolved.anchor:
            anchor = Path(resolved.anchor).resolve()
            if resolved == anchor:
                return False

        home = Path.home().resolve()
        if resolved == home:
            return False

        if str(resolved).startswith("\\\\"):
            return False

        temp_roots = self._environment_roots("TEMP", "TMP")
        if any(self._path_is_relative_to(resolved, root) for root in temp_roots):
            return True

        protected = self._protected_workspace_roots()
        if any(self._path_is_relative_to(resolved, root) for root in protected):
            return False

        return True

    def _protected_workspace_roots(self) -> list[Path]:
        roots: list[Path] = []
        roots.extend(self._environment_roots("SystemRoot", "WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"))
        home = Path.home().resolve()
        roots.extend(
            candidate.resolve()
            for candidate in (
                home / "AppData",
                home / ".ssh",
                home / ".gnupg",
            )
            if candidate.exists()
        )
        return self._dedupe_paths(roots)

    def _environment_roots(self, *names: str) -> list[Path]:
        roots: list[Path] = []
        for name in names:
            value = os.environ.get(name, "").strip()
            if not value:
                continue
            try:
                roots.append(Path(value).expanduser().resolve())
            except OSError:
                continue
        return self._dedupe_paths(roots)

    @staticmethod
    def _dedupe_paths(paths: list[Path]) -> list[Path]:
        out: list[Path] = []
        for path in paths:
            if path not in out:
                out.append(path)
        return out

    @staticmethod
    def _path_is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _migrate_legacy_workspace_if_needed(self, root: Path) -> None:
        legacy_root = (self.project_root / "backend" / "workspace").resolve()
        if root == legacy_root or not legacy_root.exists() or not legacy_root.is_dir():
            return

        try:
            has_current_files = any(root.iterdir())
        except OSError:
            return

        if has_current_files:
            return

        shutil.copytree(legacy_root, root, dirs_exist_ok=True)

    def _workspace_file(self, relative: str, size: int, kind: str, path: Path) -> WorkspaceFile:
        if kind != "text" or size < LARGE_TEXT_FILE_BYTES:
            return WorkspaceFile(path=relative, size=size, kind=kind)

        return WorkspaceFile(
            path=relative,
            size=size,
            kind=kind,
            is_large=True,
            estimated_lines=self._estimate_text_lines(path),
            large_file_strategy=self._large_file_strategy(size),
        )

    @staticmethod
    def _is_large_workspace_file(item: WorkspaceFile) -> bool:
        return bool(item.is_large or item.size >= LARGE_TEXT_FILE_BYTES)

    def _large_file_strategy(self, size: int) -> str:
        if size >= HUGE_TEXT_FILE_BYTES:
            return "huge-file sampled indexing; read targeted line slices before patching"
        return "large-file summarized context; read targeted line slices before patching"

    def _large_file_context_block(self, path: Path, item: WorkspaceFile, *, max_chars: int) -> str:
        estimate = item.estimated_lines or self._estimate_text_lines(path)
        sample = self._sample_large_text(path, max_chars=max(1200, max_chars))
        return (
            f"\n--- {item.path} ---\n"
            f"[large file summary]\n"
            f"size_bytes: {item.size}\n"
            f"estimated_lines: {estimate}\n"
            f"strategy: {item.large_file_strategy or self._large_file_strategy(item.size)}\n"
            "guidance: do not rewrite this file wholesale; inspect targeted line slices and patch the smallest safe region.\n"
            f"{sample}\n"
        )

    def _sample_large_text(self, path: Path, *, max_chars: int = LARGE_FILE_CONTEXT_SAMPLE_CHARS) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return "[sample unavailable]"

        byte_budget = max(1024, min(size, max_chars * 2))
        head_budget = max(512, byte_budget // 2)
        tail_budget = max(512, byte_budget - head_budget)

        try:
            with path.open("rb") as handle:
                head = handle.read(head_budget)
                tail = b""
                if size > head_budget:
                    handle.seek(max(0, size - tail_budget))
                    tail = handle.read(tail_budget)
        except OSError:
            return "[sample unavailable]"

        head_text = head.decode("utf-8", errors="replace")
        if not tail:
            return "[head sample]\n" + self._bounded_text(head_text, max_chars)

        tail_text = tail.decode("utf-8", errors="replace")
        per_side = max(400, max_chars // 2)
        return "\n".join(
            [
                "[head sample]",
                self._bounded_text(head_text, per_side),
                "[tail sample]",
                self._bounded_tail_text(tail_text, per_side),
            ]
        )

    def _estimate_text_lines(self, path: Path) -> int:
        try:
            size = path.stat().st_size
        except OSError:
            return 0
        if size <= 0:
            return 0

        if size <= LARGE_FILE_LINE_EXACT_BYTES:
            line_count = 0
            try:
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        line_count += chunk.count(b"\n")
                return max(1, line_count)
            except OSError:
                return 0

        sample_size = min(size, 256_000)
        try:
            with path.open("rb") as handle:
                start = handle.read(sample_size // 2)
                handle.seek(max(0, size - sample_size // 2))
                end = handle.read(sample_size // 2)
        except OSError:
            return 0

        sample = start + end
        if not sample:
            return 0
        newline_count = max(1, sample.count(b"\n"))
        return max(1, int((newline_count / len(sample)) * size))

    def _kind_for(self, path: Path) -> str:
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            return "text"
        return "binary"
