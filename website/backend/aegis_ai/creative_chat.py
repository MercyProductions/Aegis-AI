from __future__ import annotations

from pathlib import Path
from typing import Any

from .creative_media import CreativeMediaEngine
from .prompt_intent import creative_media_studio_for_kind, infer_creative_media_kind, prompt_requests_execution_validation
from .schemas import (
    AgentRequest,
    AgentResponse,
    CompletionQualityInfo,
    MediaCreativeRequest,
    ModeName,
    TaskPlanInfo,
    ToolEvent,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceProjectManifest,
)
from .settings import Settings
from .storage import EventStore
from .task_planner import TaskPlanner
from .validation import ValidationManager


class CreativeChatOrchestrator:
    """Routes chat-originated media requests into Creative Studio without patching code."""

    def __init__(
        self,
        project_root: Path,
        settings: Settings,
        *,
        store: EventStore,
        task_planner: TaskPlanner,
        validation: ValidationManager,
    ):
        self.settings = settings
        self.store = store
        self.task_planner = task_planner
        self.validation = validation
        self.media = CreativeMediaEngine(project_root, settings)

    def run(
        self,
        request: AgentRequest,
        *,
        mode: ModeName,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None,
        dependency_profile: WorkspaceDependencyProfile,
        task_id: str,
        original_message: str,
    ) -> AgentResponse:
        events: list[ToolEvent] = []
        warnings = self._request_warnings(request)

        def emit(
            kind: str,
            title: str,
            *,
            status: str = "ok",
            detail: str = "",
            payload: dict[str, Any] | None = None,
        ) -> None:
            events.append(
                self.store.record_event(
                    task_id,
                    kind=kind,
                    title=title,
                    status=status,
                    detail=detail,
                    payload=payload,
                )
            )

        state_event = self.store.transition_task(
            task_id,
            "planning",
            title="Creative media planning started",
            detail="Auralith Prime routed this request to Creative Studio instead of the coding workspace.",
        )
        if state_event is not None:
            events.append(state_event)

        task_plan = self.task_planner.build_plan(
            message=request.message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=[],
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        media_kind = infer_creative_media_kind(request.message) or "image"
        studio = creative_media_studio_for_kind(media_kind)
        emit(
            "creative.intent",
            "Creative Studio route selected",
            detail=f"Detected {media_kind.replace('_', ' ')} generation for the {studio} studio.",
            payload={
                "kind": media_kind,
                "studio": studio,
                "routing_task_role": task_plan.routing.task_role if task_plan.routing else "",
                "apply_changes_ignored": request.apply_changes,
            },
        )
        state_event = self.store.transition_task(
            task_id,
            "running",
            title="Creative media generation started",
            detail=f"Generating a local {media_kind.replace('_', ' ')} asset package.",
        )
        if state_event is not None:
            events.append(state_event)

        try:
            media_job = self.media.create_job(
                MediaCreativeRequest(
                    prompt=original_message or request.message,
                    kind=media_kind,  # type: ignore[arg-type]
                    studio=studio,
                    operation="generate",
                    **self._size_update(media_kind),
                )
            )
        except ValueError as exc:
            return self._blocked_response(
                exc,
                request=request,
                mode=mode,
                workspace_root=workspace_root,
                workspace_files=workspace_files,
                task_id=task_id,
                task_plan=task_plan,
                media_kind=media_kind,
                studio=studio,
                warnings=warnings,
                events=events,
                emit=emit,
            )

        for timeline_event in media_job.timeline:
            emit(
                timeline_event.kind,
                timeline_event.title,
                status=timeline_event.status,
                detail=timeline_event.detail,
                payload={
                    **timeline_event.payload,
                    "job_id": media_job.id,
                    "kind": media_job.kind,
                    "studio": media_job.studio,
                },
            )

        reply = self._success_reply(media_job)
        if media_job.warnings:
            warnings.extend(media_job.warnings)
        self.store.add_task_artifacts(
            task_id,
            related_files=[asset.path for asset in media_job.assets],
            checkpoints=[],
            validation_commands=[],
            error_summary="",
            final_summary=reply,
        )
        state_event = self.store.transition_task(
            task_id,
            "completed",
            title="Creative media task completed",
            detail=f"Creative Studio saved {len(media_job.assets)} asset(s) for job {media_job.id}.",
            final_summary=reply,
        )
        if state_event is not None:
            events.append(state_event)

        return AgentResponse(
            task_id=task_id,
            reply=reply,
            plan=[
                "Detect creative media intent.",
                f"Generate a local {media_job.kind.replace('_', ' ')} Creative Studio job.",
                "Save editable source assets, previews, prompt metadata, and export-ready files to the asset library.",
            ],
            changes=[],
            applied=[],
            checkpoint=None,
            warnings=warnings,
            events=events,
            validation=None,
            validation_profile=self.validation.profile_snapshot(workspace_root).profile,
            task_plan=TaskPlanInfo.model_validate(task_plan.to_event_payload()),
            context_budget=None,
            model_attempts=[],
            assistant_name=self.settings.aegis_assistant_name,
            mode=mode,
            engine="Auralith Creative Studio",
            workspace_root=str(workspace_root),
            workspace_files=workspace_files,
            context_files=[],
            memory_hits=[],
            project_memory_hits=[],
            recent_tasks=[],
            repair_attempts=[],
            completion_quality=CompletionQualityInfo(
                status="ready",
                score=1.0,
                reasons=["Creative media request completed without code workspace patches."],
                should_continue=False,
            ),
        )

    def _blocked_response(
        self,
        exc: ValueError,
        *,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
        task_id: str,
        task_plan: Any,
        media_kind: str,
        studio: str,
        warnings: list[str],
        events: list[ToolEvent],
        emit: Any,
    ) -> AgentResponse:
        error_summary = str(exc)
        emit(
            "creative.error",
            "Creative media generation blocked",
            status="error",
            detail=error_summary,
            payload={"kind": media_kind, "studio": studio},
        )
        state_event = self.store.transition_task(
            task_id,
            "failed",
            title="Creative media task failed",
            detail=error_summary,
            error_summary=error_summary,
            final_summary=error_summary,
        )
        if state_event is not None:
            events.append(state_event)
        return AgentResponse(
            task_id=task_id,
            reply=f"Creative Studio could not start this generation job: {error_summary}",
            plan=[
                "Detect creative media intent.",
                "Check provider and safety requirements.",
                "Stop safely if approval or provider requirements are missing.",
            ],
            changes=[],
            applied=[],
            checkpoint=None,
            warnings=warnings,
            events=events,
            validation=None,
            validation_profile=self.validation.profile_snapshot(workspace_root).profile,
            task_plan=TaskPlanInfo.model_validate(task_plan.to_event_payload()),
            context_budget=None,
            model_attempts=[],
            assistant_name=self.settings.aegis_assistant_name,
            mode=mode,
            engine="Auralith Creative Studio",
            workspace_root=str(workspace_root),
            workspace_files=workspace_files,
            context_files=[],
            memory_hits=[],
            project_memory_hits=[],
            recent_tasks=[],
            repair_attempts=[],
            completion_quality=CompletionQualityInfo(
                status="blocked",
                score=0.0,
                reasons=[error_summary],
                should_continue=False,
            ),
        )

    @staticmethod
    def _request_warnings(request: AgentRequest) -> list[str]:
        warnings: list[str] = []
        if request.apply_changes:
            warnings.append(
                "Apply changes was ignored for this creative media prompt; Creative Studio assets are generated in the local media library instead of patching project files."
            )
        if request.run_validation or prompt_requests_execution_validation(request.message):
            warnings.append("Validation was skipped because creative media generation does not run project build/test commands.")
        return warnings

    @staticmethod
    def _size_update(media_kind: str) -> dict[str, Any]:
        if media_kind in {"logo", "icon", "brand_kit"}:
            return {"width": 1024, "height": 1024, "aspect_ratio": "1:1"}
        return {}

    @staticmethod
    def _success_reply(media_job: Any) -> str:
        asset_lines = [f"- {asset.role}: `{asset.path}`" for asset in media_job.assets[:8]]
        if len(media_job.assets) > 8:
            asset_lines.append(f"- plus {len(media_job.assets) - 8} more asset(s) in the job folder")
        return "\n".join(
            [
                f"Auralith Prime generated a {media_job.kind.replace('_', ' ')} package in Creative Studio.",
                "",
                f"Job: `{media_job.id}`",
                f"Provider: {media_job.provider_name}",
                f"Theme: `{media_job.theme_color}`",
                f"Saved {len(media_job.assets)} asset(s):",
                *asset_lines,
                "",
                "Open Creative Studio or Asset Library to preview, revise, or export the generated PNG/SVG package.",
            ]
        )
