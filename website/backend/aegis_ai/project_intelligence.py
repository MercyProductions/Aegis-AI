from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Iterable

from .schemas import (
    FixMemoryEntry,
    ProjectApiRoute,
    ProjectArchitectureMap,
    ProjectArchitectureModule,
    ProjectContextSelectionResponse,
    ProjectDependencyEdge,
    ProjectFileImportance,
    ProjectIndexingStatus,
    ProjectIntelligenceSnapshot,
    ProjectMemoryEntry,
    ProjectProfile,
    TaskSummary,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceProjectManifest,
)
from .workspace import IGNORE_NAMES


SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
}

CONFIG_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.ts",
    "CMakeLists.txt",
    "launch.ps1",
}

RISK_MARKERS = {
    "auth",
    "security",
    "secret",
    "credential",
    "token",
    "key",
    "settings",
    "config",
    "database",
    "storage",
    "migration",
    "schema",
    "workspace",
    "approval",
    "sandbox",
    "command",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectIntelligenceEngine:
    """Builds durable project profiles from existing workspace and memory signals."""

    def build_snapshot(
        self,
        *,
        workspace_root: Path,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile,
        manifest: WorkspaceProjectManifest | None,
        project_memory: list[ProjectMemoryEntry],
        recent_tasks: list[TaskSummary],
        fix_memory: list[FixMemoryEntry],
    ) -> ProjectIntelligenceSnapshot:
        indexed_at = utc_now()
        profile = self._build_profile(workspace_root, files, dependency_profile, manifest, indexed_at)
        architecture = self._build_architecture(workspace_root, files, dependency_profile, profile)
        file_importance = self._score_files(
            workspace_root=workspace_root,
            files=files,
            profile=profile,
            architecture=architecture,
            recent_tasks=recent_tasks,
            project_memory=project_memory,
            fix_memory=fix_memory,
        )
        recent_failures = [
            item
            for item in recent_tasks
            if item.status in {"failed", "canceled"} or item.error_summary.strip()
        ][:8]
        validation_commands = self._dedupe(
            [
                *dependency_profile.validation_commands,
                *profile.test_commands,
                *profile.lint_commands,
                *profile.build_commands,
            ],
            limit=20,
        )
        known_todos = self._known_todos(workspace_root, files)

        return ProjectIntelligenceSnapshot(
            workspace_root=str(workspace_root),
            profile=profile,
            architecture=architecture,
            file_importance=file_importance,
            project_memory=project_memory[:20],
            recent_tasks=recent_tasks[:12],
            recent_failures=recent_failures,
            known_todos=known_todos,
            validation_commands=validation_commands,
            indexing=ProjectIndexingStatus(
                status="ready",
                last_indexed_at=indexed_at,
                file_count=len(files),
                ignored_folder_count=len(profile.generated_ignored_folders),
                message=f"Indexed {len(files)} workspace file(s).",
            ),
            recommendations=self._recommendations(profile, architecture, recent_failures, known_todos),
        )

    def select_context(
        self,
        *,
        snapshot: ProjectIntelligenceSnapshot,
        query: str,
        max_files: int = 12,
    ) -> ProjectContextSelectionResponse:
        query_terms = set(self._tokens(query))

        def relevance(item: ProjectFileImportance) -> float:
            text = " ".join([item.path, " ".join(item.reasons)]).lower()
            overlap = sum(1 for term in query_terms if term in text)
            return item.score + overlap * 8.0

        selected = sorted(snapshot.file_importance, key=lambda item: (-relevance(item), item.path))[:max_files]
        failure_notes = [
            item.error_summary or item.final_summary or item.message
            for item in snapshot.recent_failures[:6]
            if item.error_summary or item.final_summary or item.message
        ]
        memory_pitfalls = [
            f"{item.title}: {item.detail}"
            for item in snapshot.project_memory
            if item.category.lower() in {"bug", "fix", "failure", "decision", "todo", "preference"}
        ][:6]

        architecture_notes = [
            *snapshot.architecture.frontend_backend_split[:4],
            *[f"{item.path}: {item.summary}" for item in snapshot.architecture.major_modules[:8]],
            *[f"{item.method} {item.path} in {item.file}" for item in snapshot.architecture.api_routes[:8]],
        ]

        return ProjectContextSelectionResponse(
            workspace_root=snapshot.workspace_root,
            selected_files=selected,
            architecture_notes=architecture_notes[:16],
            project_memory=snapshot.project_memory[:8],
            previous_task_history=snapshot.recent_tasks[:6],
            known_pitfalls=[*failure_notes, *memory_pitfalls][:10],
            validation_requirements=snapshot.validation_commands[:10],
            coding_conventions=snapshot.profile.coding_conventions[:12],
        )

    def memory_notes_for_snapshot(self, snapshot: ProjectIntelligenceSnapshot) -> list[tuple[str, str, str, str, float]]:
        profile = snapshot.profile
        notes: list[tuple[str, str, str, str, float]] = []
        if profile.stack:
            notes.append(
                (
                    "pattern",
                    "Detected project stack",
                    "Stack: " + ", ".join(profile.stack[:12]),
                    "project_intelligence",
                    0.72,
                )
            )
        if profile.coding_conventions:
            notes.append(
                (
                    "preference",
                    "Detected coding conventions",
                    " / ".join(profile.coding_conventions[:8]),
                    "project_intelligence",
                    0.68,
                )
            )
        if snapshot.validation_commands:
            notes.append(
                (
                    "validation",
                    "Known validation commands",
                    " / ".join(snapshot.validation_commands[:8]),
                    "project_intelligence",
                    0.75,
                )
            )
        for todo in snapshot.known_todos[:6]:
            notes.append(("todo", "Tracked TODO", todo, "project_intelligence", 0.62))
        return notes

    def _build_profile(
        self,
        root: Path,
        files: list[WorkspaceFile],
        dependency: WorkspaceDependencyProfile,
        manifest: WorkspaceProjectManifest | None,
        indexed_at: str,
    ) -> ProjectProfile:
        scripts = dependency.scripts
        build_commands = self._script_commands(scripts, {"build", "compile", "bundle", "check", "typecheck"})
        test_commands = self._script_commands(scripts, {"test", "spec", "unit", "e2e", "pytest"})
        lint_commands = self._script_commands(scripts, {"lint", "format", "fmt", "ruff", "eslint"})
        run_commands = self._script_commands(scripts, {"dev", "start", "serve", "run", "preview"})
        if not build_commands:
            build_commands = [cmd for cmd in dependency.validation_commands if "build" in cmd.lower()][:4]
        if not test_commands:
            test_commands = [cmd for cmd in dependency.validation_commands if "test" in cmd.lower()][:4]
        if not lint_commands:
            lint_commands = [cmd for cmd in dependency.validation_commands if "lint" in cmd.lower() or "check" in cmd.lower()][:4]

        project_name = (
            (manifest.title or manifest.project_name if manifest else "")
            or self._package_name(root)
            or root.name
        )
        important_folders = self._important_folders(files)
        generated_ignored = self._generated_ignored_folders(root)
        risk_sensitive_files = self._risk_sensitive_files(files, dependency)
        main_entry_files = self._dedupe([*dependency.entry_points, *self._heuristic_entry_files(files)], limit=40)
        stack = self._dedupe(
            [
                dependency.project_type,
                *dependency.languages,
                *dependency.frameworks,
                *dependency.database_tools,
                *dependency.build_systems,
            ],
            limit=40,
        )

        return ProjectProfile(
            project_name=project_name,
            root_path=str(root),
            stack=stack,
            frameworks=dependency.frameworks,
            package_managers=dependency.package_managers,
            build_commands=self._dedupe(build_commands, limit=16),
            test_commands=self._dedupe(test_commands, limit=16),
            lint_commands=self._dedupe(lint_commands, limit=16),
            run_commands=self._dedupe(run_commands, limit=16),
            main_entry_files=main_entry_files,
            important_folders=important_folders,
            generated_ignored_folders=generated_ignored,
            risk_sensitive_files=risk_sensitive_files,
            coding_conventions=self._coding_conventions(files, dependency),
            last_indexed_at=indexed_at,
        )

    def _build_architecture(
        self,
        root: Path,
        files: list[WorkspaceFile],
        dependency: WorkspaceDependencyProfile,
        profile: ProjectProfile,
    ) -> ProjectArchitectureMap:
        modules = self._major_modules(files, dependency)
        api_routes = self._api_routes(root, files)
        storage_layer = [
            item.path
            for item in files
            if item.kind == "text" and self._path_has_any(item.path, {"storage", "database", "sqlite", "schema", "migration", "prisma"})
        ][:30]
        integration_points = [
            item.path
            for item in files
            if item.kind == "text" and self._path_has_any(item.path, {"api", "route", "provider", "adapter", "validation", "model", "memory", "workspace"})
        ][:40]
        dependency_edges = [
            ProjectDependencyEdge(source=item.source or "manifest", target=item.name, kind=item.group)
            for item in [*dependency.dependencies, *dependency.dev_dependencies]
        ][:80]

        return ProjectArchitectureMap(
            frontend_backend_split=self._frontend_backend_split(profile, files),
            major_modules=modules,
            api_routes=api_routes,
            database_storage_layer=self._dedupe(storage_layer, limit=30),
            config_files=self._dedupe(dependency.config_files, limit=60),
            build_system=self._dedupe([*dependency.build_systems, *profile.build_commands], limit=30),
            dependency_graph=dependency_edges,
            important_integration_points=self._dedupe(integration_points, limit=40),
        )

    def _score_files(
        self,
        *,
        workspace_root: Path,
        files: list[WorkspaceFile],
        profile: ProjectProfile,
        architecture: ProjectArchitectureMap,
        recent_tasks: list[TaskSummary],
        project_memory: list[ProjectMemoryEntry],
        fix_memory: list[FixMemoryEntry],
    ) -> list[ProjectFileImportance]:
        import_counts = self._import_counts(workspace_root, files)
        task_text = " ".join(
            [
                *[task.message for task in recent_tasks],
                *[task.user_goal for task in recent_tasks],
                *[path for task in recent_tasks for path in task.related_files],
            ]
        ).lower()
        memory_text = " ".join([item.title + " " + item.detail + " " + item.source for item in project_memory]).lower()
        failure_text = " ".join(
            [
                *[item.error_signature + " " + item.fix_summary + " " + item.evidence for item in fix_memory],
                *[task.error_summary for task in recent_tasks],
            ]
        ).lower()
        entry_files = set(profile.main_entry_files)
        central_files = set(architecture.important_integration_points + architecture.database_storage_layer)
        api_files = {route.file for route in architecture.api_routes}
        config_files = set(architecture.config_files)
        now_mtime = max((self._mtime(workspace_root / item.path) for item in files), default=0.0)

        scored: list[ProjectFileImportance] = []
        for item in files:
            if item.kind != "text":
                continue
            path = item.path
            path_text = path.lower()
            stem = Path(path).stem.lower()
            reasons: list[str] = []
            entry_score = 0.0
            centrality = 0.0

            if path in entry_files:
                entry_score += 35.0
                reasons.append("entry point")
            if path in config_files or Path(path).name in CONFIG_NAMES:
                centrality += 14.0
                reasons.append("configuration")
            if path in central_files or path in api_files:
                centrality += 18.0
                reasons.append("integration point")
            if self._path_has_any(path, RISK_MARKERS):
                centrality += 12.0
                reasons.append("risk-sensitive")
            if any(part in {"src", "app", "backend", "frontend", "website"} for part in Path(path).parts):
                centrality += 7.0

            imports = import_counts.get(path, 0)
            if imports:
                reasons.append(f"imported {imports} time(s)")
            recent = self._recent_edit_score(workspace_root / path, now_mtime)
            if recent > 0:
                reasons.append("recently edited")
            task_relevance = self._text_mentions(task_text, path, stem) * 6.0
            if task_relevance:
                reasons.append("recent task relevance")
            validation_failures = self._text_mentions(failure_text, path, stem) * 8.0
            if validation_failures:
                reasons.append("validation or repair history")
            user_attention = self._text_mentions(memory_text, path, stem) * 5.0
            if user_attention:
                reasons.append("project memory mention")

            score = entry_score + centrality + min(imports * 5.0, 30.0) + recent + task_relevance + validation_failures + user_attention
            if score <= 0:
                continue
            scored.append(
                ProjectFileImportance(
                    path=path,
                    score=round(score, 2),
                    reasons=self._dedupe(reasons, limit=8),
                    entry_point_importance=round(entry_score, 2),
                    import_frequency=imports,
                    recent_edits=round(recent, 2),
                    task_relevance=round(task_relevance, 2),
                    validation_failures=round(validation_failures, 2),
                    user_attention=round(user_attention, 2),
                    architectural_centrality=round(centrality, 2),
                )
            )

        scored.sort(key=lambda entry: (-entry.score, entry.path))
        return scored[:120]

    def _script_commands(self, scripts: Iterable, names: set[str]) -> list[str]:
        commands: list[str] = []
        for script in scripts:
            name = str(getattr(script, "name", "") or "").lower()
            command = str(getattr(script, "command", "") or "").strip()
            if not command:
                continue
            if name in names or any(marker in name for marker in names):
                commands.append(command)
        return commands

    def _package_name(self, root: Path) -> str:
        package_json = root / "package.json"
        if package_json.exists():
            try:
                match = re.search(r'"name"\s*:\s*"([^"]+)"', package_json.read_text(encoding="utf-8", errors="replace")[:4000])
                if match:
                    return match.group(1)
            except OSError:
                return ""
        return ""

    def _important_folders(self, files: list[WorkspaceFile]) -> list[str]:
        counts: Counter[str] = Counter()
        for item in files:
            parts = Path(item.path).parts
            if not parts:
                continue
            top = parts[0]
            if top in IGNORE_NAMES or top.startswith("."):
                continue
            if top.lower() in {"src", "app", "backend", "frontend", "website", "tests", "docs", "components", "routes", "api", "lib", "scripts"}:
                counts[top] += 8
            counts[top] += 1
        return [folder for folder, _ in counts.most_common(16)]

    def _generated_ignored_folders(self, root: Path) -> list[str]:
        present = [name for name in sorted(IGNORE_NAMES) if (root / name).exists()]
        common_generated = ["dist", "build", "coverage", ".next", "node_modules", "__pycache__", ".aegis", ".git"]
        return self._dedupe([*present, *common_generated], limit=24)

    def _risk_sensitive_files(self, files: list[WorkspaceFile], dependency: WorkspaceDependencyProfile) -> list[str]:
        risky = [
            item.path
            for item in files
            if item.kind == "text" and (Path(item.path).name in CONFIG_NAMES or self._path_has_any(item.path, RISK_MARKERS))
        ]
        return self._dedupe([*dependency.config_files, *risky], limit=60)

    def _heuristic_entry_files(self, files: list[WorkspaceFile]) -> list[str]:
        names = {
            "main.py",
            "app.py",
            "server.py",
            "index.ts",
            "index.tsx",
            "main.ts",
            "main.tsx",
            "App.tsx",
            "Program.cs",
            "main.cpp",
            "main.rs",
            "main.go",
        }
        return [item.path for item in files if Path(item.path).name in names][:40]

    def _coding_conventions(self, files: list[WorkspaceFile], dependency: WorkspaceDependencyProfile) -> list[str]:
        conventions: list[str] = []
        if "TypeScript" in dependency.languages:
            conventions.append("Prefer typed TypeScript contracts and keep frontend types aligned with backend schemas.")
        if "React" in dependency.frameworks:
            conventions.append("Use existing React component and state patterns before adding new UI abstractions.")
        if "Python" in dependency.languages:
            conventions.append("Keep backend behavior covered by pytest and use typed Pydantic request/response models.")
        if any(item.path.endswith(".test.ts") or item.path.endswith(".test.tsx") for item in files):
            conventions.append("Frontend regressions live beside TypeScript utilities/components as Vitest tests.")
        if any("backend/tests" in item.path.replace("\\", "/") for item in files):
            conventions.append("Backend regressions live under backend/tests.")
        if dependency.package_managers:
            conventions.append("Preserve the detected package manager and lockfile conventions.")
        if dependency.validation_commands:
            conventions.append("Run known validation commands before marking project work complete.")
        conventions.append("Ignore generated folders such as node_modules, dist, build, .aegis checkpoints, and cache folders.")
        return self._dedupe(conventions, limit=12)

    def _major_modules(self, files: list[WorkspaceFile], dependency: WorkspaceDependencyProfile) -> list[ProjectArchitectureModule]:
        folders = self._important_folders(files)
        modules: list[ProjectArchitectureModule] = []
        for folder in folders:
            lowered = folder.lower()
            kind = "source"
            if lowered in {"tests", "test"}:
                kind = "tests"
            elif lowered in {"docs", "documentation"}:
                kind = "docs"
            elif lowered in {"backend", "api", "server"}:
                kind = "backend"
            elif lowered in {"frontend", "components", "app"}:
                kind = "frontend"
            modules.append(
                ProjectArchitectureModule(
                    name=folder,
                    path=folder,
                    kind=kind,
                    summary=f"{folder} contains {kind} project files.",
                )
            )
        if dependency.entry_points:
            modules.append(
                ProjectArchitectureModule(
                    name="Entry Points",
                    path=", ".join(dependency.entry_points[:6]),
                    kind="entry",
                    summary="Primary runtime entry files detected from manifests and source conventions.",
                )
            )
        return modules[:24]

    def _api_routes(self, root: Path, files: list[WorkspaceFile]) -> list[ProjectApiRoute]:
        routes: list[ProjectApiRoute] = []
        for item in files:
            if item.kind != "text" or item.size > 180_000:
                continue
            if Path(item.path).suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            text = self._read_small(root / item.path, limit=80_000)
            if not text:
                continue
            for match in re.finditer(r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", text):
                routes.append(ProjectApiRoute(method=match.group(1).upper(), path=match.group(2), file=item.path))
            for match in re.finditer(r"\b(?:router|app)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", text):
                routes.append(ProjectApiRoute(method=match.group(1).upper(), path=match.group(2), file=item.path))
        deduped: list[ProjectApiRoute] = []
        seen: set[tuple[str, str, str]] = set()
        for route in routes:
            key = (route.method, route.path, route.file)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(route)
        return deduped[:120]

    def _frontend_backend_split(self, profile: ProjectProfile, files: list[WorkspaceFile]) -> list[str]:
        paths = {item.path.lower().replace("\\", "/") for item in files}
        split: list[str] = []
        if any(path.startswith(("frontend/", "src/", "app/")) or path.endswith((".tsx", ".jsx", ".css")) for path in paths):
            split.append("Frontend/UI surface detected from React/TypeScript/component files.")
        if any(path.startswith(("backend/", "server/", "api/")) or path.endswith(".py") for path in paths):
            split.append("Backend/API/runtime surface detected from server-side source files.")
        if profile.frameworks:
            split.append("Framework signals: " + ", ".join(profile.frameworks[:8]) + ".")
        if not split:
            split.append("No clear frontend/backend split detected; treat this as a single workspace until more files are indexed.")
        return split

    def _import_counts(self, root: Path, files: list[WorkspaceFile]) -> dict[str, int]:
        source_files = [item for item in files if item.kind == "text" and Path(item.path).suffix.lower() in SOURCE_SUFFIXES and item.size < 120_000]
        path_by_stem = {Path(item.path).stem.lower(): item.path for item in source_files}
        counts: Counter[str] = Counter()
        for item in source_files[:700]:
            text = self._read_small(root / item.path, limit=60_000)
            if not text:
                continue
            for match in re.finditer(r"(?:from|import)\s+[\"']?([A-Za-z0-9_./\-]+)", text):
                stem = Path(match.group(1)).stem.lower()
                target = path_by_stem.get(stem)
                if target and target != item.path:
                    counts[target] += 1
        return dict(counts)

    def _known_todos(self, root: Path, files: list[WorkspaceFile]) -> list[str]:
        todos: list[str] = []
        for item in files:
            if item.kind != "text" or item.size > 120_000:
                continue
            if Path(item.path).suffix.lower() not in {".md", ".txt", ".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            text = self._read_small(root / item.path, limit=40_000)
            for line in text.splitlines():
                stripped = line.strip()
                if re.search(r"\b(TODO|FIXME|NEXT|follow[- ]?up)\b", stripped, re.IGNORECASE) or stripped.startswith("- [ ]"):
                    todos.append(f"{item.path}: {stripped[:220]}")
                    if len(todos) >= 40:
                        return todos
        return todos

    def _recommendations(
        self,
        profile: ProjectProfile,
        architecture: ProjectArchitectureMap,
        failures: list[TaskSummary],
        todos: list[str],
    ) -> list[str]:
        recommendations: list[str] = []
        if not profile.main_entry_files:
            recommendations.append("Identify and pin the primary runtime entry file for sharper context selection.")
        if not profile.test_commands and not profile.lint_commands and not profile.build_commands:
            recommendations.append("Save explicit build/test/lint commands so validation can be planned reliably.")
        if failures:
            recommendations.append("Recent failed tasks exist; prioritize known failure surfaces during context selection.")
        if todos:
            recommendations.append("Open TODOs were found; keep them visible during planning and summarization.")
        if architecture.api_routes and not architecture.database_storage_layer:
            recommendations.append("API routes are detected; confirm whether the persistence layer is external, generated, or currently absent.")
        return recommendations

    def _path_has_any(self, path: str, markers: set[str]) -> bool:
        lowered = path.lower().replace("\\", "/")
        return any(marker in lowered for marker in markers)

    def _read_small(self, path: Path, *, limit: int) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except OSError:
            return ""

    def _mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    def _recent_edit_score(self, path: Path, latest_mtime: float) -> float:
        mtime = self._mtime(path)
        if not mtime or not latest_mtime:
            return 0.0
        age_delta = max(0.0, latest_mtime - mtime)
        if age_delta <= 60 * 60:
            return 10.0
        if age_delta <= 60 * 60 * 24:
            return 7.0
        if age_delta <= 60 * 60 * 24 * 7:
            return 4.0
        return 0.0

    def _text_mentions(self, text: str, path: str, stem: str) -> int:
        if not text:
            return 0
        lowered_path = path.lower()
        count = 0
        if lowered_path and lowered_path in text:
            count += 2
        if stem and re.search(rf"\b{re.escape(stem)}\b", text):
            count += 1
        return count

    def _tokens(self, text: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", text or "")]

    def _dedupe(self, values: Iterable[str], *, limit: int) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
            if len(result) >= limit:
                break
        return result
