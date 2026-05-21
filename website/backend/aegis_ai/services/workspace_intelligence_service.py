from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import time
from typing import Any

from fastapi import HTTPException

from ..schemas import (
    ProjectContextSelectionRequest,
    ProjectContextSelectionResponse,
    ProjectIntelligenceReindexRequest,
    ProjectIntelligenceSnapshot,
    RecommendationActionRequest,
    RecommendationFixRequest,
    RecommendationFixResponse,
    ScheduledIntelligenceJob,
    ScheduledJobRunRequest,
    ScheduledJobRunResponse,
    WorkspaceOperationsScanRequest,
    WorkspaceOperationsSnapshot,
    WorkspaceProfileResponse,
    WorkspaceProjectManifest,
    WorkspaceRecommendation,
    WorkspaceSetupRequest,
    WorkspaceSetupResponse,
    WorkspaceWatchEvent,
)
from ..workspace_cache import WorkspaceStatusSnapshot, WorkspaceStatusSnapshotCache
from ..workspace_setup import merge_missing_manifest_fields, workspace_setup_manifest


class WorkspaceIntelligenceService:
    def __init__(
        self,
        *,
        workspace_manager_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        project_intelligence_factory: Callable[[], Any],
        workspace_operations_factory: Callable[[], Any],
        model_benchmarks_factory: Callable[[], Any],
        workspace_status_cache: WorkspaceStatusSnapshotCache,
        workspace_resolver: Callable[[str | None], Path],
        workspace_profile_builder: Callable[..., WorkspaceProfileResponse],
        invalidate_workspace_caches: Callable[[Path | None], None],
    ) -> None:
        self._workspace_manager_factory = workspace_manager_factory
        self._agent_factory = agent_factory
        self._project_intelligence_factory = project_intelligence_factory
        self._workspace_operations_factory = workspace_operations_factory
        self._model_benchmarks_factory = model_benchmarks_factory
        self._workspace_status_cache = workspace_status_cache
        self._workspace_resolver = workspace_resolver
        self._workspace_profile_builder = workspace_profile_builder
        self._invalidate_workspace_caches = invalidate_workspace_caches

    @property
    def workspace_manager(self) -> Any:
        return self._workspace_manager_factory()

    @property
    def agent(self) -> Any:
        return self._agent_factory()

    @property
    def project_intelligence(self) -> Any:
        return self._project_intelligence_factory()

    @property
    def workspace_operations(self) -> Any:
        return self._workspace_operations_factory()

    @property
    def model_benchmarks(self) -> Any:
        return self._model_benchmarks_factory()

    def clear_workspace_status_cache(self, root: Path | None = None) -> None:
        self._workspace_status_cache.clear(root)

    def prune_workspace_status_cache(self) -> None:
        self._workspace_status_cache.prune()

    def workspace_status_snapshot(self, root: Path) -> WorkspaceStatusSnapshot:
        now = time.monotonic()
        cached = self._workspace_status_cache.get(root, now=now)
        if cached is not None:
            return cached

        workspace_manager = self.workspace_manager
        agent = self.agent
        manifest = workspace_manager.load_project_manifest(root)
        dependency_profile = workspace_manager.inspect_dependency_profile(root)
        instruction_status = agent.instruction_status_snapshot(root)
        validation_plan = agent.validation_plan_snapshot(root)
        command_history = agent.command_history_snapshot(root)
        readiness = agent.workspace_readiness_snapshot(
            manifest=manifest,
            dependency_profile=dependency_profile,
            instruction_status=instruction_status,
            validation_plan=validation_plan,
            command_history=command_history,
        )
        snapshot = WorkspaceStatusSnapshot(
            created_at=now,
            manifest=manifest,
            dependency_profile=dependency_profile,
            instruction_status=instruction_status,
            validation_plan=validation_plan,
            command_history=command_history,
            readiness=readiness,
        )
        self._workspace_status_cache.set(root, snapshot)
        return snapshot

    def build_project_intelligence(
        self,
        root: Path,
        *,
        clear_memory: bool = False,
        rebuild_memory: bool = False,
    ) -> ProjectIntelligenceSnapshot:
        agent = self.agent
        if clear_memory:
            agent.store.clear_project_memory(project_root=root)

        self.clear_workspace_status_cache(root)
        snapshot = self.workspace_status_snapshot(root)
        files = self.workspace_manager.scan(root, max_files=1500)
        project_memory = agent.store.project_memory(project_root=root, limit=80)
        recent_tasks = agent.store.list_tasks(project_root=root, limit=80, include_subtasks=False)
        fix_memory = agent.store.fix_history(project_root=root, limit=80)
        project_intelligence = self.project_intelligence
        intelligence = project_intelligence.build_snapshot(
            workspace_root=root,
            files=files,
            dependency_profile=snapshot.dependency_profile,
            manifest=snapshot.manifest,
            project_memory=project_memory,
            recent_tasks=recent_tasks,
            fix_memory=fix_memory,
        )
        agent.store.save_project_intelligence(intelligence)

        if rebuild_memory:
            for category, title, detail, source, confidence in project_intelligence.memory_notes_for_snapshot(intelligence):
                agent.store.remember_project_note(
                    project_root=root,
                    category=category,
                    title=title,
                    detail=detail,
                    source=source,
                    confidence=confidence,
                )
            intelligence = intelligence.model_copy(update={"project_memory": agent.store.project_memory(project_root=root, limit=80)})
            agent.store.save_project_intelligence(intelligence)

        return intelligence

    def project_intelligence_snapshot(self, root: Path, *, rebuild: bool = False) -> ProjectIntelligenceSnapshot:
        if not rebuild:
            cached = self.agent.store.project_intelligence(project_root=root)
            if cached is not None:
                return cached
        return self.build_project_intelligence(root)

    def build_workspace_operations(
        self,
        root: Path,
        *,
        refresh_project_intelligence: bool = True,
        generate_recommendations: bool = True,
        include_git: bool = True,
    ) -> WorkspaceOperationsSnapshot:
        agent = self.agent
        workspace_operations = self.workspace_operations
        self.clear_workspace_status_cache(root)
        status = self.workspace_status_snapshot(root)
        files = self.workspace_manager.scan(root, max_files=1500)
        intelligence = (
            self.build_project_intelligence(root)
            if refresh_project_intelligence
            else agent.store.project_intelligence(project_root=root)
        )
        snapshot = workspace_operations.build_snapshot(
            workspace_root=root,
            files=files,
            dependency_profile=status.dependency_profile,
            project_intelligence=intelligence,
            recent_tasks=agent.store.list_tasks(project_root=root, limit=100, include_subtasks=False),
            fix_memory=agent.store.fix_history(project_root=root, limit=80),
            project_memory=agent.store.project_memory(project_root=root, limit=100),
            previous_watch=agent.store.workspace_watch_snapshot(project_root=root),
            previous_recommendations=agent.store.workspace_recommendations(project_root=root, include_dismissed=True, limit=200),
            job_runs=workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root)),
            include_git=include_git,
        )
        agent.store.save_workspace_watch_snapshot(snapshot.watcher)
        agent.store.record_workspace_events(snapshot.watcher.events)
        if generate_recommendations:
            agent.store.upsert_workspace_recommendations(snapshot.recommendations)
        for note in snapshot.long_term_memory[:6]:
            agent.store.remember_project_note(
                project_root=root,
                category="operations",
                title="Workspace operations signal",
                detail=note,
                source="workspace_operations",
                confidence=0.62,
            )
        persisted_recommendations = agent.store.workspace_recommendations(project_root=root, include_dismissed=False, limit=100)
        recent_events = agent.store.workspace_events(project_root=root, limit=80)
        snapshot = snapshot.model_copy(
            update={
                "recommendations": persisted_recommendations,
                "recent_events": recent_events,
                "scheduled_jobs": workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root)),
            }
        )
        agent.store.save_workspace_operations_snapshot(snapshot)
        return snapshot

    def workspace_operations_snapshot(self, root: Path, *, rebuild: bool = False) -> WorkspaceOperationsSnapshot:
        if not rebuild:
            cached = self.agent.store.workspace_operations_snapshot(project_root=root)
            if cached is not None:
                return cached
        return self.build_workspace_operations(root)

    def run_scheduled_intelligence_jobs(self, root: Path, request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
        agent = self.agent
        workspace_operations = self.workspace_operations
        existing_jobs = workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root))
        selected_ids = set(request.job_ids or [item.id for item in existing_jobs])
        jobs_by_id = {item.id: item for item in existing_jobs}
        warnings: list[str] = []
        completed: list[ScheduledIntelligenceJob] = []

        for job_id in selected_ids:
            job = jobs_by_id.get(job_id)
            if job is None:
                warnings.append(f"Unknown scheduled intelligence job: {job_id}")
                continue
            summary = "Workspace intelligence scan completed."
            status = "completed"
            try:
                if job.kind in {"indexing", "architecture"}:
                    self.build_project_intelligence(root)
                    summary = "Project Intelligence was refreshed."
                elif job.kind == "telemetry":
                    agent.store.refresh_telemetry_snapshot(project_root=root)
                    summary = "Telemetry snapshot was refreshed."
                elif job.kind == "validation" and not request.allow_commands:
                    status = "skipped"
                    summary = "Validation snapshot skipped command execution because allow_commands was false."
                elif job.kind == "validation":
                    validation = agent._run_validation(root, lambda *_args, **_kwargs: None, manual=True)
                    summary = (
                        f"Validation command `{validation.command}` exited with {validation.exit_code}."
                        if validation
                        else "No validation command was available."
                    )
                elif job.kind == "benchmark":
                    self.model_benchmarks.snapshot()
                    summary = "Benchmark metadata was inspected; no benchmark command was run automatically."
                elif job.kind == "memory":
                    summary = "Workspace operations memory signals were summarized."
                elif job.kind == "dependency":
                    summary = "Dependency manifests were inspected for drift and local freshness warnings."
            except Exception as exc:
                status = "failed"
                summary = f"{type(exc).__name__}: {exc}"
            record = workspace_operations.job_run_record(job, status=status, summary=summary)
            agent.store.record_scheduled_intelligence_job(project_root=root, job=record)
            completed.append(record)

        snapshot = self.build_workspace_operations(root, refresh_project_intelligence=True)
        return ScheduledJobRunResponse(workspace_root=str(root), jobs=completed, snapshot=snapshot, warnings=warnings)

    async def workspace_profile(self, workspace_root: str | None = None) -> WorkspaceProfileResponse:
        root = self._workspace_resolver(workspace_root)
        return self._workspace_profile_builder(
            root,
            workspace_status_snapshot=self.workspace_status_snapshot,
            project_intelligence_snapshot=self.project_intelligence_snapshot,
        )

    async def workspace_setup(self, request: WorkspaceSetupRequest) -> WorkspaceSetupResponse:
        root = self._workspace_resolver(request.workspace_root)
        workspace_manager = self.workspace_manager
        agent = self.agent
        dependency_profile = workspace_manager.inspect_dependency_profile(root)
        validation_snapshot = agent.validation.profile_snapshot(root)
        persisted_recipe = agent.validation.load_profile(root)
        detected_recipe = validation_snapshot.profile
        install_command = request.install_command.strip() or (
            dependency_profile.install_commands[0] if dependency_profile.install_commands else ""
        )
        validation_command = request.validation_command.strip() or (
            detected_recipe.command if detected_recipe is not None else ""
        ) or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
        generated_manifest = workspace_setup_manifest(
            root,
            request,
            dependency_profile=dependency_profile,
            install_command=install_command,
            validation_command=validation_command,
        )
        existing_manifest = workspace_manager.load_project_manifest(root)
        created_files: list[str] = []
        updated_files: list[str] = []
        warnings: list[str] = []
        manifest_path = workspace_manager.PROJECT_MANIFEST_PATH

        def save_manifest_safely(candidate: WorkspaceProjectManifest) -> tuple[WorkspaceProjectManifest, bool]:
            try:
                return workspace_manager.save_project_manifest(root, candidate), True
            except OSError as exc:
                warnings.append(f"Could not write {manifest_path}: {exc}")
                return candidate, False

        if existing_manifest is None:
            manifest, saved = save_manifest_safely(generated_manifest)
            if saved:
                created_files.append(manifest_path)
        elif request.overwrite_manifest:
            manifest, saved = save_manifest_safely(generated_manifest)
            if saved:
                updated_files.append(manifest_path)
        else:
            manifest, changed = merge_missing_manifest_fields(existing_manifest, generated_manifest)
            if changed:
                manifest, saved = save_manifest_safely(manifest)
                if saved:
                    updated_files.append(manifest_path)
            else:
                manifest = existing_manifest

        saved_recipe = persisted_recipe
        profile_path = agent.validation.PROFILE_PATH
        if validation_command:
            if persisted_recipe and persisted_recipe.source == "manual" and not request.validation_command.strip():
                warnings.append("Existing manual validation recipe was kept.")
            elif persisted_recipe and persisted_recipe.command == validation_command and not request.validation_command.strip():
                saved_recipe = persisted_recipe
            else:
                profile_existed = (root / profile_path).exists()
                try:
                    saved_recipe = agent.validation.save_profile(
                        root,
                        command=validation_command,
                        label=(
                            detected_recipe.label
                            if detected_recipe and detected_recipe.command == validation_command
                            else ""
                        )
                        or "Workspace validation",
                        source="workspace_setup",
                        notes=request.notes.strip()
                        or (
                            detected_recipe.notes
                            if detected_recipe and detected_recipe.command == validation_command
                            else ""
                        )
                        or "Saved by Aegis workspace setup from detected project files.",
                    )
                except OSError as exc:
                    warnings.append(f"Could not write {profile_path}: {exc}")
                else:
                    (updated_files if profile_existed else created_files).append(profile_path)
        else:
            warnings.append("No validation command was detected; manifest was created without a validation recipe.")

        self._invalidate_workspace_caches(root)
        profile = await self.workspace_profile(str(root))
        return WorkspaceSetupResponse(
            workspace_root=str(root),
            manifest=manifest,
            validation_profile=saved_recipe,
            profile=profile,
            created_files=created_files,
            updated_files=updated_files,
            warnings=warnings,
        )

    async def project_intelligence_snapshot_route(self, workspace_root: str | None = None) -> ProjectIntelligenceSnapshot:
        root = self._workspace_resolver(workspace_root)
        return self.project_intelligence_snapshot(root)

    async def reindex_project_intelligence(self, request: ProjectIntelligenceReindexRequest) -> ProjectIntelligenceSnapshot:
        root = self._workspace_resolver(request.workspace_root)
        return self.build_project_intelligence(
            root,
            clear_memory=request.clear_memory,
            rebuild_memory=request.rebuild_memory,
        )

    async def project_intelligence_context(
        self,
        request: ProjectContextSelectionRequest,
    ) -> ProjectContextSelectionResponse:
        root = self._workspace_resolver(request.workspace_root)
        snapshot = self.project_intelligence_snapshot(root)
        return self.project_intelligence.select_context(snapshot=snapshot, query=request.query, max_files=request.max_files)

    async def workspace_intelligence_snapshot(self, workspace_root: str | None = None) -> WorkspaceOperationsSnapshot:
        root = self._workspace_resolver(workspace_root)
        return self.workspace_operations_snapshot(root)

    async def scan_workspace_intelligence(self, request: WorkspaceOperationsScanRequest) -> WorkspaceOperationsSnapshot:
        root = self._workspace_resolver(request.workspace_root)
        return self.build_workspace_operations(
            root,
            refresh_project_intelligence=request.refresh_project_intelligence,
            generate_recommendations=request.generate_recommendations,
            include_git=request.include_git,
        )

    async def workspace_intelligence_events(
        self,
        workspace_root: str | None = None,
        limit: int = 80,
    ) -> list[WorkspaceWatchEvent]:
        root = self._workspace_resolver(workspace_root)
        return self.agent.store.workspace_events(project_root=root, limit=limit)

    async def workspace_intelligence_recommendations(
        self,
        workspace_root: str | None = None,
        include_dismissed: bool = False,
        limit: int = 100,
    ) -> list[WorkspaceRecommendation]:
        root = self._workspace_resolver(workspace_root)
        return self.agent.store.workspace_recommendations(project_root=root, include_dismissed=include_dismissed, limit=limit)

    async def dismiss_workspace_recommendation(
        self,
        recommendation_id: str,
        request: RecommendationActionRequest | None = None,
    ) -> RecommendationFixResponse:
        try:
            recommendation = self.agent.store.dismiss_workspace_recommendation(
                recommendation_id,
                reason=(request.reason if request else ""),
            )
            return RecommendationFixResponse(
                recommendation=recommendation,
                message="Recommendation dismissed.",
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="recommendation not found") from exc

    async def fix_workspace_recommendation(
        self,
        recommendation_id: str,
        request: RecommendationFixRequest | None = None,
    ) -> RecommendationFixResponse:
        agent = self.agent
        action = request or RecommendationFixRequest()
        try:
            recommendation = agent.store.workspace_recommendation(recommendation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="recommendation not found") from exc
        if not action.create_task:
            return RecommendationFixResponse(
                recommendation=recommendation,
                message="No task created; recommendation remains active.",
            )
        root = self._workspace_resolver(recommendation.workspace_root)
        user_goal = recommendation.fix_prompt or recommendation.detail or recommendation.title
        task_id = agent.store.create_task(
            mode="develop",
            workspace_root=root,
            message=user_goal,
            title=f"Fix recommendation: {recommendation.title}",
            user_goal=user_goal,
            status="queued",
            assigned_agent_role="planner",
            related_files=recommendation.related_files,
            validation_commands=[],
        )
        event = agent.store.record_event(
            task_id,
            kind="recommendation.fix_requested",
            title="Recommendation fix task created",
            status="warning",
            detail=(
                "Workspace Intelligence created a tracked task only. No autonomous file edits were applied; "
                "normal approval, checkpoint, validation, and rollback rules still apply."
            ),
            payload={
                "recommendation_id": recommendation.id,
                "severity": recommendation.severity,
                "reason": action.reason,
                "related_files": recommendation.related_files,
            },
        )
        recommendation = agent.store.link_recommendation_task(recommendation_id, task_id)
        return RecommendationFixResponse(
            recommendation=recommendation,
            task=agent.store.task(task_id),
            event=event,
            message="Fix task created. No files were modified automatically.",
        )

    async def workspace_intelligence_jobs(self, workspace_root: str | None = None) -> list[ScheduledIntelligenceJob]:
        root = self._workspace_resolver(workspace_root)
        return self.workspace_operations.scheduled_jobs(self.agent.store.scheduled_intelligence_jobs(project_root=root))

    async def run_workspace_intelligence_jobs(self, request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
        root = self._workspace_resolver(request.workspace_root)
        return self.run_scheduled_intelligence_jobs(root, request)
