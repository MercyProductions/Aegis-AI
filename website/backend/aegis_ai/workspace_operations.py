from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import subprocess
from typing import Any, Iterable

from .schemas import (
    FixMemoryEntry,
    GitCommitSummary,
    GitFileChangeSummary,
    GitIntelligenceSummary,
    ProjectHealthMetric,
    ProjectHealthSnapshot,
    ProjectIntelligenceSnapshot,
    ProjectMemoryEntry,
    ScheduledIntelligenceJob,
    TaskSummary,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceFileState,
    WorkspaceOperationsSnapshot,
    WorkspaceRecommendation,
    WorkspaceWatchEvent,
    WorkspaceWatcherSnapshot,
)


SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs"}
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
    "requirements.txt",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceOperationsEngine:
    """Permission-aware watcher, health, recommendation, and scheduled-job logic."""

    DEFAULT_JOBS: tuple[tuple[str, str, str, str], ...] = (
        ("nightly_indexing", "Nightly indexing", "indexing", "Nightly"),
        ("dependency_refresh", "Dependency refresh", "dependency", "Daily"),
        ("validation_snapshot", "Validation snapshot", "validation", "Nightly"),
        ("architecture_refresh", "Architecture refresh", "architecture", "Nightly"),
        ("token_usage_analysis", "Token usage analysis", "telemetry", "Weekly"),
        ("project_compression", "Project compression", "memory", "Weekly"),
        ("benchmark_refresh", "Benchmark refresh", "benchmark", "Weekly"),
        ("telemetry_snapshot", "Telemetry snapshot", "telemetry", "Hourly"),
    )

    def build_snapshot(
        self,
        *,
        workspace_root: Path,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile,
        project_intelligence: ProjectIntelligenceSnapshot | None,
        recent_tasks: list[TaskSummary],
        fix_memory: list[FixMemoryEntry],
        project_memory: list[ProjectMemoryEntry],
        previous_watch: WorkspaceWatcherSnapshot | None = None,
        previous_recommendations: list[WorkspaceRecommendation] | None = None,
        job_runs: list[ScheduledIntelligenceJob] | None = None,
        include_git: bool = True,
    ) -> WorkspaceOperationsSnapshot:
        generated_at = utc_now()
        git = self.git_summary(workspace_root) if include_git else GitIntelligenceSummary()
        watcher = self.watch(
            workspace_root=workspace_root,
            files=files,
            dependency_profile=dependency_profile,
            previous=previous_watch,
            git=git,
        )
        health = self.health(
            workspace_root=workspace_root,
            files=files,
            dependency_profile=dependency_profile,
            project_intelligence=project_intelligence,
            recent_tasks=recent_tasks,
            fix_memory=fix_memory,
        )
        recommendations = self.recommendations(
            workspace_root=workspace_root,
            watcher=watcher,
            health=health,
            dependency_profile=dependency_profile,
            project_intelligence=project_intelligence,
            recent_tasks=recent_tasks,
            previous=previous_recommendations or [],
        )
        return WorkspaceOperationsSnapshot(
            workspace_root=str(workspace_root.resolve()),
            generated_at=generated_at,
            watcher=watcher,
            health=health,
            recommendations=recommendations,
            scheduled_jobs=self.scheduled_jobs(job_runs or []),
            git=git,
            long_term_memory=self.long_term_memory(project_memory, recent_tasks, fix_memory),
            recent_events=watcher.events[:50],
        )

    def watch(
        self,
        *,
        workspace_root: Path,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile,
        previous: WorkspaceWatcherSnapshot | None,
        git: GitIntelligenceSummary,
    ) -> WorkspaceWatcherSnapshot:
        scanned_at = utc_now()
        states = self.file_states(workspace_root, files)
        state_by_path = {item.path: item for item in states}
        previous_by_path = {item.path: item for item in previous.file_states} if previous else {}
        events: list[WorkspaceWatchEvent] = []

        if previous is None:
            events.append(
                self.event(
                    workspace_root,
                    "watcher.baseline",
                    "info",
                    "Workspace baseline captured",
                    f"Watching {len(states)} file(s) for drift and maintenance signals.",
                )
            )
        else:
            for path in sorted(set(state_by_path) - set(previous_by_path))[:50]:
                events.append(self.event(workspace_root, "file.created", "low", "New file detected", path, path=path))
            for path in sorted(set(previous_by_path) - set(state_by_path))[:50]:
                events.append(self.event(workspace_root, "file.deleted", "medium", "File deleted", path, path=path))
            modified = [
                path
                for path in sorted(set(state_by_path) & set(previous_by_path))
                if state_by_path[path].fingerprint != previous_by_path[path].fingerprint
            ]
            for path in modified[:50]:
                severity = "medium" if path in DEPENDENCY_FILES or any(marker in path.lower() for marker in ("config", "schema", "storage")) else "low"
                events.append(self.event(workspace_root, "file.modified", severity, "File changed", path, path=path))

            if previous.dependency_fingerprint and previous.dependency_fingerprint != self.dependency_fingerprint(dependency_profile, states):
                events.append(
                    self.event(
                        workspace_root,
                        "dependency.changed",
                        "medium",
                        "Dependency profile changed",
                        "Dependency manifests, lockfiles, or inferred package metadata changed since the last scan.",
                    )
                )
            if previous.git.branch and git.branch and previous.git.branch != git.branch:
                events.append(
                    self.event(
                        workspace_root,
                        "git.branch_changed",
                        "medium",
                        "Git branch changed",
                        f"{previous.git.branch} -> {git.branch}",
                        metadata={"before": previous.git.branch, "after": git.branch},
                    )
                )

        if git.is_repository and git.changed_files:
            events.append(
                self.event(
                    workspace_root,
                    "git.changed",
                    "low",
                    "Git working tree has changes",
                    f"{len(git.changed_files)} file(s) differ from HEAD.",
                    related_files=git.changed_files[:20],
                    metadata={"branch": git.branch},
                )
            )
        if git.deleted_files:
            events.append(
                self.event(
                    workspace_root,
                    "git.deleted_files",
                    "medium",
                    "Git reports deleted files",
                    f"{len(git.deleted_files)} deleted file(s) are visible in git status.",
                    related_files=git.deleted_files[:20],
                )
            )

        validation_drift = self.validation_drift(previous, events)
        fingerprint = self.workspace_fingerprint(states)
        return WorkspaceWatcherSnapshot(
            workspace_root=str(workspace_root.resolve()),
            scanned_at=scanned_at,
            file_count=len(states),
            fingerprint=fingerprint,
            dependency_fingerprint=self.dependency_fingerprint(dependency_profile, states),
            file_states=states,
            events=events,
            validation_drift=validation_drift,
            git=git,
        )

    def health(
        self,
        *,
        workspace_root: Path,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile,
        project_intelligence: ProjectIntelligenceSnapshot | None,
        recent_tasks: list[TaskSummary],
        fix_memory: list[FixMemoryEntry],
    ) -> ProjectHealthSnapshot:
        metrics = [
            self._failing_tests_metric(recent_tasks),
            self._dependency_metric(workspace_root, dependency_profile),
            self._large_file_metric(files),
            self._dead_code_metric(files, project_intelligence),
            self._todo_metric(workspace_root, files),
            self._validation_instability_metric(recent_tasks, fix_memory),
            self._duplicate_code_metric(workspace_root, files),
            self._architecture_drift_metric(project_intelligence, dependency_profile),
            self._build_performance_metric(recent_tasks),
        ]
        score = max(0, min(100, round(sum(item.score for item in metrics) / max(1, len(metrics)))))
        if any(item.status == "critical" for item in metrics):
            status = "critical"
        elif score < 70 or any(item.status == "warning" for item in metrics):
            status = "attention"
        elif score < 88:
            status = "watch"
        else:
            status = "healthy"
        top_risks = [item.summary for item in metrics if item.status in {"critical", "warning"}][:8]
        return ProjectHealthSnapshot(
            workspace_root=str(workspace_root.resolve()),
            generated_at=utc_now(),
            score=score,
            status=status,
            metrics=metrics,
            top_risks=top_risks,
        )

    def recommendations(
        self,
        *,
        workspace_root: Path,
        watcher: WorkspaceWatcherSnapshot,
        health: ProjectHealthSnapshot,
        dependency_profile: WorkspaceDependencyProfile,
        project_intelligence: ProjectIntelligenceSnapshot | None,
        recent_tasks: list[TaskSummary],
        previous: list[WorkspaceRecommendation],
    ) -> list[WorkspaceRecommendation]:
        dismissed_ids = {item.id for item in previous if item.status == "dismissed"}
        by_id: dict[str, WorkspaceRecommendation] = {item.id: item for item in previous}
        generated: list[WorkspaceRecommendation] = []
        for metric in health.metrics:
            if metric.status not in {"warning", "critical"}:
                continue
            severity = "high" if metric.status == "critical" else "medium"
            generated.append(
                self.recommendation(
                    workspace_root,
                    severity,
                    self._category_from_metric(metric.name),
                    metric.name,
                    metric.summary,
                    related_files=metric.related_files,
                    evidence={"metric": metric.model_dump(mode="json")},
                    fix_prompt=self._fix_prompt(metric),
                )
            )

        failed_tasks = [item for item in recent_tasks if item.status == "failed" or item.error_summary]
        if len(failed_tasks) >= 3:
            generated.append(
                self.recommendation(
                    workspace_root,
                    "high",
                    "validation",
                    "Validation failures are recurring",
                    f"{len(failed_tasks)} recent task(s) ended failed or carried an error summary.",
                    related_tasks=[item.id for item in failed_tasks[:8]],
                    evidence={"task_ids": [item.id for item in failed_tasks[:8]]},
                    fix_prompt="Review recurring validation failures, identify the dominant module, and make the smallest repair with validation.",
                )
            )

        if dependency_profile.warnings:
            generated.append(
                self.recommendation(
                    workspace_root,
                    "medium",
                    "dependency",
                    "Dependency profile has warnings",
                    "; ".join(dependency_profile.warnings[:4]),
                    evidence={"warnings": dependency_profile.warnings[:8]},
                    fix_prompt="Inspect dependency warnings and update manifests or install instructions without changing unrelated code.",
                )
            )

        for event in watcher.events:
            if event.kind in {"file.deleted", "git.deleted_files", "dependency.changed"}:
                generated.append(
                    self.recommendation(
                        workspace_root,
                        "medium" if event.severity != "high" else "high",
                        "watcher",
                        event.title,
                        event.detail,
                        related_files=event.related_files or ([event.path] if event.path else []),
                        evidence={"event": event.model_dump(mode="json")},
                        fix_prompt=f"Investigate workspace watcher event: {event.title}. Preserve user changes and do not modify files without approval.",
                    )
                )

        if project_intelligence and len(project_intelligence.architecture.major_modules) > 18:
            generated.append(
                self.recommendation(
                    workspace_root,
                    "medium",
                    "architecture",
                    "Architecture map is becoming broad",
                    "Project Intelligence detected many major modules; review boundaries before adding more top-level structure.",
                    evidence={"module_count": len(project_intelligence.architecture.major_modules)},
                    fix_prompt="Review architecture modules, identify boundary drift, and propose a minimal consolidation plan without applying changes.",
                )
            )

        active: list[WorkspaceRecommendation] = []
        for item in generated:
            if item.id in dismissed_ids:
                continue
            existing = by_id.get(item.id)
            if existing and existing.status != "active":
                continue
            if existing:
                item = item.model_copy(update={"created_at": existing.created_at, "fix_task_id": existing.fix_task_id})
            active.append(item)
        return active

    def scheduled_jobs(self, previous_runs: list[ScheduledIntelligenceJob]) -> list[ScheduledIntelligenceJob]:
        by_id = {item.id: item for item in previous_runs}
        jobs: list[ScheduledIntelligenceJob] = []
        for job_id, name, kind, schedule in self.DEFAULT_JOBS:
            previous = by_id.get(job_id)
            jobs.append(
                ScheduledIntelligenceJob(
                    id=job_id,
                    name=name,
                    kind=kind,
                    schedule_label=schedule,
                    safe_by_default=kind != "validation",
                    last_run_at=previous.last_run_at if previous else "",
                    next_run_hint=self._next_run_hint(schedule),
                    status=previous.status if previous else "idle",
                    summary=previous.summary if previous else "Not run yet.",
                )
            )
        return jobs

    def git_summary(self, workspace_root: Path) -> GitIntelligenceSummary:
        if not (workspace_root / ".git").exists() and self._git(["rev-parse", "--is-inside-work-tree"], workspace_root).strip() != "true":
            return GitIntelligenceSummary(summary="No git repository detected for this workspace.")
        branch = self._git(["branch", "--show-current"], workspace_root).strip()
        upstream = self._git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], workspace_root).strip()
        branches = [line.strip().lstrip("* ").strip() for line in self._git(["branch", "--format", "%(refname:short)"], workspace_root).splitlines()]
        status_lines = self._git(["status", "--porcelain=v1"], workspace_root).splitlines()
        changed_files: list[str] = []
        staged_files: list[str] = []
        untracked_files: list[str] = []
        deleted_files: list[str] = []
        for line in status_lines:
            if len(line) < 4:
                continue
            code = line[:2]
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            changed_files.append(path)
            if code[0] not in {" ", "?"}:
                staged_files.append(path)
            if code == "??":
                untracked_files.append(path)
            if "D" in code:
                deleted_files.append(path)
        recent_commits = self._recent_commits(workspace_root)
        heatmap = self._git_heatmap(workspace_root)
        risky = [item for item in heatmap if item.additions + item.deletions >= 120 or self._risk_path(item.path)][:12]
        summary = f"{branch or 'detached'} with {len(changed_files)} changed file(s)."
        return GitIntelligenceSummary(
            is_repository=True,
            branch=branch,
            upstream=upstream,
            branch_count=len(branches),
            branches=branches[:40],
            changed_files=changed_files[:100],
            staged_files=staged_files[:100],
            untracked_files=untracked_files[:100],
            deleted_files=deleted_files[:100],
            risky_diffs=risky,
            change_heatmap=heatmap,
            recent_commits=recent_commits,
            task_commit_links=self._task_commit_links(recent_commits),
            summary=summary,
        )

    def file_states(self, workspace_root: Path, files: list[WorkspaceFile]) -> list[WorkspaceFileState]:
        states: list[WorkspaceFileState] = []
        for item in files:
            path = workspace_root / item.path
            try:
                stat = path.stat()
            except OSError:
                continue
            states.append(
                WorkspaceFileState(
                    path=item.path,
                    size=item.size,
                    kind=item.kind,
                    modified_at=stat.st_mtime,
                    fingerprint=self._file_fingerprint(path, item.size),
                )
            )
        return states

    def workspace_fingerprint(self, states: list[WorkspaceFileState]) -> str:
        payload = "\n".join(f"{item.path}:{item.size}:{item.fingerprint}" for item in sorted(states, key=lambda value: value.path))
        return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()

    def dependency_fingerprint(
        self,
        dependency_profile: WorkspaceDependencyProfile,
        states: list[WorkspaceFileState],
    ) -> str:
        dep_states = [item for item in states if Path(item.path).name in DEPENDENCY_FILES]
        payload = {
            "config_files": dependency_profile.config_files,
            "dependencies": [item.model_dump(mode="json") for item in dependency_profile.dependencies],
            "dev_dependencies": [item.model_dump(mode="json") for item in dependency_profile.dev_dependencies],
            "states": [item.model_dump(mode="json") for item in dep_states],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def event(
        self,
        workspace_root: Path,
        kind: str,
        severity: str,
        title: str,
        detail: str,
        *,
        path: str = "",
        related_files: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceWatchEvent:
        created_at = utc_now()
        event_id = hashlib.sha256(
            "|".join([str(workspace_root.resolve()), kind, title, detail, path, created_at[:16]]).encode("utf-8")
        ).hexdigest()[:24]
        return WorkspaceWatchEvent(
            id=event_id,
            workspace_root=str(workspace_root.resolve()),
            created_at=created_at,
            kind=kind,
            severity=severity,  # type: ignore[arg-type]
            title=title,
            detail=detail,
            path=path,
            related_files=related_files or [],
            metadata=metadata or {},
        )

    def recommendation(
        self,
        workspace_root: Path,
        severity: str,
        category: str,
        title: str,
        detail: str,
        *,
        related_files: list[str] | None = None,
        related_tasks: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        fix_prompt: str = "",
    ) -> WorkspaceRecommendation:
        related_files = sorted(set(related_files or []))
        related_tasks = sorted(set(related_tasks or []))
        rec_id = hashlib.sha256(
            json.dumps(
                {
                    "root": str(workspace_root.resolve()),
                    "category": category,
                    "title": title,
                    "files": related_files[:8],
                    "tasks": related_tasks[:8],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:24]
        now = utc_now()
        return WorkspaceRecommendation(
            id=rec_id,
            workspace_root=str(workspace_root.resolve()),
            created_at=now,
            updated_at=now,
            severity=severity,  # type: ignore[arg-type]
            category=category,
            title=title,
            detail=detail,
            rationale=detail,
            related_files=related_files,
            related_tasks=related_tasks,
            evidence=evidence or {},
            fix_prompt=fix_prompt,
        )

    def validation_drift(self, previous: WorkspaceWatcherSnapshot | None, events: list[WorkspaceWatchEvent]) -> list[str]:
        notes: list[str] = []
        if any(event.kind == "dependency.changed" for event in events):
            notes.append("Dependency metadata changed; rerun validation before relying on previous passing state.")
        if any(event.kind == "file.deleted" for event in events):
            notes.append("Files were deleted since the last scan; checkpoints and validation may be stale.")
        if previous and events:
            notes.append(f"{len(events)} watcher event(s) occurred since the previous workspace baseline.")
        return notes

    def long_term_memory(
        self,
        project_memory: list[ProjectMemoryEntry],
        recent_tasks: list[TaskSummary],
        fix_memory: list[FixMemoryEntry],
    ) -> list[str]:
        notes: list[str] = []
        categories = Counter(item.category for item in project_memory)
        if categories:
            top = ", ".join(f"{name}={count}" for name, count in categories.most_common(4))
            notes.append(f"Project memory shape: {top}.")
        failures = [item for item in recent_tasks if item.status == "failed" or item.error_summary]
        if failures:
            notes.append(f"Recent evolution includes {len(failures)} failed or repaired task(s).")
        if fix_memory:
            top_fixes = Counter(item.category for item in fix_memory).most_common(3)
            notes.append("Recurring fix categories: " + ", ".join(f"{name}={count}" for name, count in top_fixes) + ".")
        return notes[:8]

    def job_run_record(self, job: ScheduledIntelligenceJob, *, status: str, summary: str) -> ScheduledIntelligenceJob:
        return job.model_copy(update={"last_run_at": utc_now(), "status": status, "summary": summary})

    def _failing_tests_metric(self, recent_tasks: list[TaskSummary]) -> ProjectHealthMetric:
        failures = [item for item in recent_tasks if item.status == "failed" or item.error_summary]
        if not failures:
            return ProjectHealthMetric(name="Failing tests", status="healthy", score=96, summary="No recent failed tasks are recorded.")
        status = "critical" if len(failures) >= 5 else "warning"
        return ProjectHealthMetric(
            name="Failing tests",
            status=status,
            score=max(20, 90 - len(failures) * 14),
            summary=f"{len(failures)} recent task(s) failed or recorded validation errors.",
            evidence=[item.error_summary or item.final_summary or item.message for item in failures[:6]],
            related_files=sorted({path for item in failures for path in item.related_files})[:12],
        )

    def _dependency_metric(self, workspace_root: Path, dependency: WorkspaceDependencyProfile) -> ProjectHealthMetric:
        floating = self._floating_dependency_specs(workspace_root)
        warnings = [*dependency.warnings, *[f"{name} uses {version}" for name, version in floating[:8]]]
        if not dependency.config_files:
            return ProjectHealthMetric(name="Dependency freshness", status="unknown", score=55, summary="No dependency manifest was detected.")
        if warnings:
            return ProjectHealthMetric(
                name="Dependency freshness",
                status="warning",
                score=72,
                summary="Dependency metadata needs review.",
                evidence=warnings[:10],
                related_files=[path for path in dependency.config_files if Path(path).name in DEPENDENCY_FILES],
            )
        return ProjectHealthMetric(name="Dependency freshness", status="healthy", score=92, summary="Dependency manifests are present with no local warnings.")

    def _large_file_metric(self, files: list[WorkspaceFile]) -> ProjectHealthMetric:
        candidates = [
            item
            for item in files
            if Path(item.path).suffix.lower() in SOURCE_SUFFIXES and (item.estimated_lines >= 900 or item.size >= 180_000)
        ]
        if not candidates:
            return ProjectHealthMetric(name="Large risky files", status="healthy", score=94, summary="No oversized source files were detected.")
        candidates = sorted(candidates, key=lambda item: (item.estimated_lines, item.size), reverse=True)
        return ProjectHealthMetric(
            name="Large risky files",
            status="warning",
            score=max(45, 88 - len(candidates) * 8),
            summary=f"{len(candidates)} source file(s) are large enough to deserve review.",
            evidence=[f"{item.path}: {item.estimated_lines} lines, {item.size} bytes" for item in candidates[:8]],
            related_files=[item.path for item in candidates[:12]],
        )

    def _dead_code_metric(
        self,
        files: list[WorkspaceFile],
        project_intelligence: ProjectIntelligenceSnapshot | None,
    ) -> ProjectHealthMetric:
        if not project_intelligence:
            return ProjectHealthMetric(name="Dead code candidates", status="unknown", score=70, summary="Project Intelligence has not scored files yet.")
        important = {item.path for item in project_intelligence.file_importance if item.import_frequency > 0 or item.entry_point_importance > 0}
        candidates = [
            item.path
            for item in files
            if Path(item.path).suffix.lower() in SOURCE_SUFFIXES
            and item.path not in important
            and "test" not in item.path.lower()
            and "spec" not in item.path.lower()
        ][:20]
        if len(candidates) < 8:
            return ProjectHealthMetric(name="Dead code candidates", status="healthy", score=88, summary="No large cluster of isolated source files was detected.")
        return ProjectHealthMetric(
            name="Dead code candidates",
            status="warning",
            score=68,
            summary=f"{len(candidates)} source file(s) have low import/entry-point signals.",
            evidence=candidates[:10],
            related_files=candidates[:12],
        )

    def _todo_metric(self, workspace_root: Path, files: list[WorkspaceFile]) -> ProjectHealthMetric:
        counts: list[tuple[str, int]] = []
        for item in files[:800]:
            if Path(item.path).suffix.lower() not in SOURCE_SUFFIXES and Path(item.path).suffix.lower() not in {".md", ".txt"}:
                continue
            text = self._safe_read_text(workspace_root / item.path, limit=180_000)
            count = len(re.findall(r"\b(TODO|FIXME|XXX)\b", text, flags=re.IGNORECASE))
            if count:
                counts.append((item.path, count))
        total = sum(count for _, count in counts)
        if total == 0:
            return ProjectHealthMetric(name="TODO/FIXME hotspots", status="healthy", score=94, summary="No TODO/FIXME hotspots were found.")
        counts.sort(key=lambda pair: pair[1], reverse=True)
        status = "warning" if total >= 8 or counts[0][1] >= 3 else "healthy"
        return ProjectHealthMetric(
            name="TODO/FIXME hotspots",
            status=status,
            score=max(55, 95 - total * 3),
            summary=f"{total} TODO/FIXME marker(s) found across {len(counts)} file(s).",
            evidence=[f"{path}: {count}" for path, count in counts[:8]],
            related_files=[path for path, _ in counts[:12]],
        )

    def _validation_instability_metric(
        self,
        recent_tasks: list[TaskSummary],
        fix_memory: list[FixMemoryEntry],
    ) -> ProjectHealthMetric:
        validation_failures = [
            item for item in recent_tasks if item.error_summary or any("test" in command or "build" in command for command in item.validation_commands)
        ]
        if len(validation_failures) < 3:
            return ProjectHealthMetric(name="Validation instability", status="healthy", score=90, summary="Validation history is stable enough for normal work.")
        return ProjectHealthMetric(
            name="Validation instability",
            status="warning",
            score=max(40, 86 - len(validation_failures) * 9),
            summary=f"{len(validation_failures)} validation-linked task(s) need attention.",
            evidence=[item.error_summary or item.final_summary or item.message for item in validation_failures[:8]],
            related_files=sorted({path for item in validation_failures for path in item.related_files})[:12],
        )

    def _duplicate_code_metric(self, workspace_root: Path, files: list[WorkspaceFile]) -> ProjectHealthMetric:
        functions: dict[str, list[str]] = defaultdict(list)
        for item in files[:600]:
            if Path(item.path).suffix.lower() not in SOURCE_SUFFIXES:
                continue
            text = self._safe_read_text(workspace_root / item.path, limit=160_000)
            for match in re.finditer(r"\b(?:def|function|class|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)", text):
                functions[match.group(1)].append(item.path)
        duplicates = {name: paths for name, paths in functions.items() if len(set(paths)) > 1 and not name.startswith("_")}
        if len(duplicates) < 6:
            return ProjectHealthMetric(name="Duplicate code", status="healthy", score=88, summary="No broad duplicate symbol clusters were detected.")
        related = sorted({path for paths in duplicates.values() for path in paths})[:12]
        return ProjectHealthMetric(
            name="Duplicate code",
            status="warning",
            score=70,
            summary=f"{len(duplicates)} repeated symbol name(s) may indicate duplicated APIs or helpers.",
            evidence=[f"{name}: {', '.join(sorted(set(paths))[:3])}" for name, paths in list(duplicates.items())[:8]],
            related_files=related,
        )

    def _architecture_drift_metric(
        self,
        intelligence: ProjectIntelligenceSnapshot | None,
        dependency: WorkspaceDependencyProfile,
    ) -> ProjectHealthMetric:
        if not intelligence:
            return ProjectHealthMetric(name="Architecture drift", status="unknown", score=65, summary="No architecture map is available yet.")
        signals = []
        if len(intelligence.architecture.major_modules) > 18:
            signals.append(f"{len(intelligence.architecture.major_modules)} major modules detected")
        if len(dependency.config_files) > 12:
            signals.append(f"{len(dependency.config_files)} config/build files detected")
        if not signals:
            return ProjectHealthMetric(name="Architecture drift", status="healthy", score=90, summary="Architecture map is within expected bounds.")
        return ProjectHealthMetric(
            name="Architecture drift",
            status="warning",
            score=72,
            summary="Architecture boundaries may need review.",
            evidence=signals,
            related_files=intelligence.architecture.config_files[:12],
        )

    def _build_performance_metric(self, recent_tasks: list[TaskSummary]) -> ProjectHealthMetric:
        timeout_tasks = [
            item
            for item in recent_tasks
            if "timeout" in item.error_summary.lower() or "timed out" in item.error_summary.lower()
        ]
        if not timeout_tasks:
            return ProjectHealthMetric(name="Build performance", status="healthy", score=88, summary="No recent timeout-driven build regressions were recorded.")
        return ProjectHealthMetric(
            name="Build performance",
            status="warning",
            score=66,
            summary=f"{len(timeout_tasks)} recent task(s) mention validation timeout or performance issues.",
            evidence=[item.error_summary or item.message for item in timeout_tasks[:6]],
            related_files=sorted({path for item in timeout_tasks for path in item.related_files})[:12],
        )

    def _floating_dependency_specs(self, workspace_root: Path) -> list[tuple[str, str]]:
        package_json = workspace_root / "package.json"
        if not package_json.exists():
            return []
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return []
        floating: list[tuple[str, str]] = []
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps = payload.get(section)
            if not isinstance(deps, dict):
                continue
            for name, version in deps.items():
                version_text = str(version)
                if version_text in {"*", "latest"} or version_text.startswith((">", ">=", "x", "X")):
                    floating.append((str(name), version_text))
        return floating

    def _git(self, args: list[str], cwd: Path) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(cwd), *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except Exception:
            return ""
        return completed.stdout if completed.returncode == 0 else ""

    def _recent_commits(self, workspace_root: Path) -> list[GitCommitSummary]:
        lines = self._git(["log", "-n", "8", "--pretty=format:%H%x1f%an%x1f%aI%x1f%s"], workspace_root).splitlines()
        commits: list[GitCommitSummary] = []
        for line in lines:
            parts = line.split("\x1f", 3)
            if len(parts) == 4:
                commits.append(GitCommitSummary(sha=parts[0][:12], author=parts[1], created_at=parts[2], subject=parts[3]))
        return commits

    def _git_heatmap(self, workspace_root: Path) -> list[GitFileChangeSummary]:
        lines = self._git(["diff", "--numstat"], workspace_root).splitlines()
        heatmap: list[GitFileChangeSummary] = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            additions = int(parts[0]) if parts[0].isdigit() else 0
            deletions = int(parts[1]) if parts[1].isdigit() else 0
            heatmap.append(GitFileChangeSummary(path=parts[2], status="modified", additions=additions, deletions=deletions))
        return sorted(heatmap, key=lambda item: item.additions + item.deletions, reverse=True)[:40]

    def _task_commit_links(self, commits: list[GitCommitSummary]) -> list[str]:
        links: list[str] = []
        for commit in commits:
            for match in re.finditer(r"\btask[:#\s-]*([0-9a-fA-F-]{8,})", commit.subject, flags=re.IGNORECASE):
                links.append(f"{match.group(1)} -> {commit.sha}")
        return links[:20]

    def _file_fingerprint(self, path: Path, size: int) -> str:
        try:
            stat = path.stat()
            if size <= 2_000_000:
                return hashlib.sha256(path.read_bytes()).hexdigest()
            return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")).hexdigest()
        except OSError:
            return ""

    def _safe_read_text(self, path: Path, *, limit: int) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except OSError:
            return ""

    def _risk_path(self, path: str) -> bool:
        lowered = path.lower()
        return any(marker in lowered for marker in ("auth", "security", "secret", "token", "database", "schema", "storage", "migration", "config"))

    def _category_from_metric(self, name: str) -> str:
        lowered = name.lower()
        if "dependency" in lowered:
            return "dependency"
        if "validation" in lowered or "test" in lowered or "build" in lowered:
            return "validation"
        if "architecture" in lowered or "duplicate" in lowered or "dead code" in lowered:
            return "architecture"
        return "maintainability"

    def _fix_prompt(self, metric: ProjectHealthMetric) -> str:
        files = ", ".join(metric.related_files[:8]) or "the relevant project files"
        return f"Address this workspace recommendation safely: {metric.name}. {metric.summary} Related files: {files}. Do not modify files without normal approval and checkpoint behavior."

    def _next_run_hint(self, schedule: str) -> str:
        return {
            "Hourly": "Next eligible hourly maintenance window.",
            "Daily": "Next daily maintenance window.",
            "Nightly": "Next nightly maintenance window.",
            "Weekly": "Next weekly maintenance window.",
        }.get(schedule, "Next scheduled maintenance window.")
