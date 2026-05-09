# backend/agent.py
from __future__ import annotations

from pathlib import Path
import json
import re
import time
from typing import Any, AsyncIterator, Callable, Literal

from pydantic import ValidationError

from .approval_sandbox import ApprovalManager
from .agent_request_intent import (
    message_without_explicit_paths as request_message_without_explicit_paths,
    request_mentions_cpp_project,
    request_mentions_desktop_project,
    request_mentions_extension_project,
    request_mentions_python_app_project,
    request_mentions_specific_web_framework,
    request_mentions_web_project,
    request_needs_project_shape,
    windows_path_fragments as request_windows_path_fragments,
)
from .agent_runtime import (
    AgentDraft,
    DOTNET_SUFFIXES as RUNTIME_DOTNET_SUFFIXES,
    MissionAnchor,
    draft_change_paths as runtime_draft_change_paths,
    draft_change_payload_size as runtime_draft_change_payload_size,
    draft_has_concrete_source_surface as runtime_draft_has_concrete_source_surface,
    draft_has_desktop_host_surface as runtime_draft_has_desktop_host_surface,
    draft_stack_families as runtime_draft_stack_families,
    important_project_path as runtime_important_project_path,
    looks_like_next_workspace as runtime_looks_like_next_workspace,
    manifest_contract_value as runtime_manifest_contract_value,
    manifest_stack_family as runtime_manifest_stack_family,
    sanitize_model_change_paths,
    stack_family_label as runtime_stack_family_label,
    workspace_stack_family as runtime_workspace_stack_family,
)
from .commands import CommandResult, CommandRunner
from .context_budget import ContextBudgetManager, ContextBudgetResult
from .context_formatting import (
    format_fix_memory_context,
    format_instruction_file_context,
    format_project_intelligence_context_for_workspace,
    format_project_memory_context,
    format_task_history_context,
)
from .creative_chat import CreativeChatOrchestrator
from .fallback import FallbackEngine
from .instruction_status import instruction_status_from_discovered_files
from .llm import LocalModelClient, LocalModelError, LocalModelInventory, LocalModelStatus
from .mission_continuity import (
    mission_anchor_context,
    mission_anchor_from_history,
    mission_aware_message,
    parse_mission_anchor,
    request_is_broad_mission_followup,
)
from .agent_native_validation import (
    cmake_build_py_content as native_cmake_build_py_content,
    drop_shell_only_cpp_validation_changes as native_drop_shell_only_cpp_validation_changes,
    harden_native_cpp_draft as native_harden_cpp_draft,
    prefer_python_build_command as native_prefer_python_build_command,
)
from .model_benchmark import ModelBenchmarkManager
from .model_attempt_executor import ModelAttemptExecutor
from .model_costing import ModelCostEstimator
from .model_execution import ModelExecutionPlan, ModelExecutionPlanner
from .model_registry import ModelRegistryManager
from .multi_agent import MultiAgentCoordinator
from .project_indexer import ProjectIndexer
from .project_memory_notes import (
    extract_project_notes as memory_extract_project_notes,
    memory_title_for as memory_note_title_for,
)
from .project_status import (
    display_workspace_relative_path as project_display_workspace_relative_path,
    latest_project_build_log as project_latest_build_log,
    read_aegis_json as project_read_aegis_json,
    read_text_tail as project_read_text_tail,
    redact_project_status_text as project_redact_status_text,
    safe_log_display_path as project_safe_log_display_path,
    safe_project_build_log_path as project_safe_build_log_path,
    status_text as project_status_text,
)
from .prompt_intent import (
    prompt_requests_creative_media,
    prompt_requests_execution_validation,
)
from .providers import ProviderError, build_provider_adapter, provider_config_from_attempt
from .providers.base import extract_json_object
from .routing import ModelRouter
from .schemas import (
    AgentRequest,
    AgentResponse,
    CommandRun,
    CompletionQualityInfo,
    ContextBudgetInfo,
    FileChange,
    FixMemoryEntry,
    ModeName,
    ModelAttemptInfo,
    ModelRegistryProvider,
    ProjectIntelligenceSnapshot,
    ProjectMemoryEntry,
    RepairAttempt,
    RoutePreviewRequest,
    RoutePreviewResponse,
    TaskSummary,
    TaskPlanInfo,
    ToolEvent,
    ValidateResponse,
    ValidationRecipe,
    VerificationRequest,
    VerificationResponse,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceInstructionFile,
    WorkspaceInstructionStatusInfo,
    WorkspaceProjectManifest,
    WorkspaceReadinessInfo,
    WorkspaceValidationPlanInfo,
)
from .settings import Settings
from .storage import EventStore, utc_now
from .structured_streaming import StructuredReplyDeltaExtractor
from .task_planner import TaskPlan, TaskPlanner
from .validation import ValidationManager
from .validation_commands import (
    POWERSHELL_BUILD_COMMAND_MARKERS,
    is_blocked_validation_launcher_command,
)
from .validation_diagnostics import (
    diagnostic_brief as validation_diagnostic_brief,
    diagnostic_display as validation_diagnostic_display,
    extract_validation_diagnostics,
    failed_step_display as validation_failed_step_display,
    failed_step_parts_from_steps as validation_failed_step_parts_from_steps,
    fenced_log_text as validation_fenced_log_text,
    first_diagnostic_brief as validation_first_diagnostic_brief,
    first_diagnostic_display as validation_first_diagnostic_display,
    normalize_diagnostic_path as validation_normalize_diagnostic_path,
    repair_target_from_validation as validation_repair_target,
    strip_ansi as validation_strip_ansi,
    to_positive_int as validation_to_positive_int,
    validation_diagnostics_log,
    validation_steps_log,
)
from .validation_outcome import (
    categorize_command_result as outcome_categorize_command_result,
    categorize_validation_failure as outcome_categorize_validation_failure,
    error_signature as outcome_error_signature,
    repair_outcome as outcome_repair_outcome,
    repair_strategy_hint as outcome_repair_strategy_hint,
    repair_summary as outcome_repair_summary,
    summarize_command_result as outcome_summarize_command_result,
    validation_ok as outcome_validation_ok,
    validation_score as outcome_validation_score,
)
from .workspace import WorkspaceManager
from .workspace_autopilot import (
    compact_validation_repair_brief as workspace_compact_validation_repair_brief,
    latest_history_validation as workspace_latest_history_validation,
    remembered_validation_command as workspace_remembered_validation_command,
)


MODE_OPTIONS: list[tuple[ModeName, str, str]] = [
    ("build", "Build", "Create or scaffold the next working slice."),
    ("develop", "Develop", "Implement, refine, and extend the current workspace."),
    ("review", "Review", "Inspect the workspace, spot gaps, and propose next steps."),
    ("chat", "Chat", "Talk through ideas, tradeoffs, and direction without forcing edits."),
]

EmitEvent = Callable[[str, str], None]
StreamDeltaCallback = Callable[[dict[str, Any]], None]


class AgentEngine:
    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root
        self.settings = settings
        self.workspace = WorkspaceManager(project_root, settings)
        self.model = LocalModelClient(settings)
        self.commands = CommandRunner(settings)
        self.approvals = ApprovalManager(settings.approval_tier, settings.sandbox_profile)
        self.store = EventStore(project_root, settings)
        self.validation = ValidationManager()
        self.fallback = FallbackEngine(settings)
        self.router = ModelRouter(settings)
        self.task_planner = TaskPlanner(self.router)
        self.context_budgeter = ContextBudgetManager(settings)
        self.model_execution_planner = ModelExecutionPlanner()
        self.model_cost_estimator = ModelCostEstimator()
        self.model_attempt_executor = ModelAttemptExecutor(settings)
        self.model_registry = ModelRegistryManager(project_root, settings)
        self.model_benchmarks = ModelBenchmarkManager(project_root, settings, self.model_registry)
        self.creative_chat = CreativeChatOrchestrator(
            project_root,
            settings,
            store=self.store,
            task_planner=self.task_planner,
            validation=self.validation,
        )

    def _mission_anchor_from_history(self, history: list[Any]) -> MissionAnchor | None:
        return mission_anchor_from_history(history)

    def _parse_mission_anchor(self, content: str) -> MissionAnchor | None:
        return parse_mission_anchor(content)

    def _request_is_broad_mission_followup(self, message: str) -> bool:
        cleaned = self._message_without_explicit_paths(message).strip().lower()
        return request_is_broad_mission_followup(
            cleaned,
            has_explicit_workspace=bool(self._explicit_prompt_workspace(message)),
        )

    def _mission_anchor_context(self, anchor: MissionAnchor | None) -> str:
        return mission_anchor_context(anchor)

    def _mission_aware_message(self, message: str, anchor: MissionAnchor | None) -> str:
        return mission_aware_message(
            message,
            anchor,
            is_broad_followup=self._request_is_broad_mission_followup(message),
        )

    async def model_status(self) -> LocalModelStatus:
        return await self.model.status()

    async def model_inventory(self) -> LocalModelInventory:
        return await self.model.inventory()

    def instruction_status_snapshot(self, workspace_root: Path) -> WorkspaceInstructionStatusInfo:
        payload = self._read_aegis_json(workspace_root, "instruction_status.json")
        if payload:
            try:
                return WorkspaceInstructionStatusInfo.model_validate(payload)
            except ValidationError:
                pass

        instruction_files = self.workspace.discover_instruction_files(workspace_root)
        if not instruction_files:
            return WorkspaceInstructionStatusInfo()
        return self._instruction_status_from_discovered_files(instruction_files)

    def _instruction_status_from_discovered_files(
        self,
        instruction_files: list[WorkspaceInstructionFile],
    ) -> WorkspaceInstructionStatusInfo:
        return instruction_status_from_discovered_files(instruction_files, updated_at=utc_now())

    def validation_plan_snapshot(self, workspace_root: Path) -> WorkspaceValidationPlanInfo:
        payload = self._read_aegis_json(workspace_root, "validation_plan.json")
        if not payload:
            return WorkspaceValidationPlanInfo()
        try:
            return WorkspaceValidationPlanInfo.model_validate(payload)
        except ValidationError:
            return WorkspaceValidationPlanInfo()

    def command_history_snapshot(self, workspace_root: Path) -> dict[str, Any]:
        return self._read_aegis_json(workspace_root, "command_history.json")

    def workspace_readiness_snapshot(
        self,
        *,
        manifest: WorkspaceProjectManifest | None,
        dependency_profile: WorkspaceDependencyProfile,
        instruction_status: WorkspaceInstructionStatusInfo,
        validation_plan: WorkspaceValidationPlanInfo,
        command_history: dict[str, Any] | None = None,
    ) -> WorkspaceReadinessInfo:
        signals: list[str] = []
        blockers: list[str] = []
        command_history = command_history if isinstance(command_history, dict) else {}
        history_validation_command = workspace_remembered_validation_command(command_history)
        latest_history_validation = workspace_latest_history_validation(command_history)

        if manifest is not None:
            project_label = manifest.title or manifest.project_name or "Aegis workspace"
            signals.append(f"Manifest found for {project_label}.")
        else:
            blockers.append("No .aegis/project.json manifest is present.")

        if dependency_profile.config_files:
            signals.append(f"Detected build/config files: {', '.join(dependency_profile.config_files[:4])}.")
        else:
            blockers.append("No dependency or build manifest was detected.")

        validation_command = (
            validation_plan.validation_command
            or (manifest.validation_command if manifest else "")
            or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
            or history_validation_command
        )
        if validation_command:
            signals.append(f"Validation command available: {validation_command}.")
        else:
            blockers.append("No validation command is configured or inferred.")

        plan_last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
        instruction_last_validation = (
            instruction_status.last_validation
            if isinstance(instruction_status.last_validation, dict)
            else {}
        )
        effective_last_validation = latest_history_validation or plan_last_run or instruction_last_validation
        effective_validation_status = str(effective_last_validation.get("status") or "").strip().lower()
        failed_statuses = {"failed", "blocked", "needs_attention", "error"}
        passed_statuses = {"passed", "success", "succeeded"}
        validation_failed = effective_validation_status in failed_statuses
        validation_passed = effective_validation_status in passed_statuses

        if validation_passed:
            signals.append("Latest validation passed.")
        elif validation_failed:
            detail = self._repair_target_from_validation(effective_last_validation, validation_command=validation_command)
            blockers.append(f"Validation failed at {detail}.")
        elif validation_command:
            blockers.append("Validation has not passed yet in the saved project memory.")

        completion = instruction_status.completion if isinstance(instruction_status.completion, dict) else {}
        should_continue = bool(completion.get("should_continue"))
        open_items = int(instruction_status.open_items or 0)
        if open_items > 0:
            blockers.append(f"{open_items} tracked instruction item(s) are still open.")
        elif instruction_status.total_items:
            signals.append("Tracked instruction items are complete.")
        if should_continue and open_items <= 0:
            blockers.append("Completion scoring recommends one more implementation pass.")

        score = 35
        if manifest is not None:
            score += 10
        if dependency_profile.config_files:
            score += 10
        if validation_command:
            score += 10
        if validation_passed:
            score += 25
        if instruction_status.total_items and open_items <= 0 and not should_continue:
            score += 10
        if validation_failed:
            score -= 35
        score -= min(open_items * 4, 20)
        if not validation_command:
            score -= 10
        score = max(0, min(100, score))

        if validation_failed:
            status = "needs_repair"
            score = min(score, 35)
            target = self._repair_target_from_validation(effective_last_validation, validation_command=validation_command)
            summary = "Validation failed and the workspace should stay in repair mode."
            next_action = f"Repair {target}, inspect the captured build output, and rerun validation."
        elif open_items > 0 or should_continue:
            status = "needs_work"
            score = min(score, 75)
            summary = "The workspace has tracked project work left for autopilot."
            next_action = instruction_status.recommendation or "Continue the next open instruction item, then rerun validation."
        elif not validation_command:
            status = "unconfigured"
            score = min(score, 35)
            summary = "Aegis does not have a safe validation command for this workspace."
            next_action = "Add, generate, or save a safe validation command before marking the workspace ready."
        elif validation_command and not validation_passed:
            status = "needs_validation"
            score = min(score, 65)
            summary = "A validation plan exists, but the saved memory does not show a passing run yet."
            next_action = f"Run validation command: {validation_command}"
        else:
            status = "ready"
            score = max(score, 85)
            summary = "The workspace is validated and has no open tracked instruction items."
            next_action = "Summarize the finished state or start the next requested feature."

        return WorkspaceReadinessInfo(
            status=status,
            score=score,
            summary=summary,
            next_action=next_action,
            blockers=blockers[:8],
            signals=signals[:8],
        )

    def workspace_readiness_for_workspace(self, workspace_root: Path) -> WorkspaceReadinessInfo:
        return self.workspace_readiness_snapshot(
            manifest=self.workspace.load_project_manifest(workspace_root),
            dependency_profile=self.workspace.inspect_dependency_profile(workspace_root),
            instruction_status=self.instruction_status_snapshot(workspace_root),
            validation_plan=self.validation_plan_snapshot(workspace_root),
            command_history=self.command_history_snapshot(workspace_root),
        )

    async def validate_workspace(self, workspace_root_value: str | None) -> ValidateResponse:
        workspace_root = self.workspace.resolve_workspace(workspace_root_value)
        task_id = self.store.create_task(mode="validate", workspace_root=workspace_root, message="Manual validation")
        profile_snapshot = self.validation.profile_snapshot(workspace_root)
        events: list[ToolEvent] = []

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

        emit("workspace", "Workspace selected", detail=str(workspace_root))
        validation = self._run_validation(workspace_root, emit, manual=True)
        final_status = "completed" if not validation or self._validation_ok(validation) else "completed_with_validation_failure"
        self.store.finish_task(task_id, final_status)
        return ValidateResponse(
            task_id=task_id,
            workspace_root=str(workspace_root),
            events=events,
            validation=validation,
            validation_profile=profile_snapshot.profile,
            warnings=[] if validation else ["No validation command was detected for this workspace."],
        )

    async def verify_workspace(self, request: VerificationRequest) -> VerificationResponse:
        workspace_root = self.workspace.resolve_workspace(request.workspace_root)
        task_id = self.store.create_task(mode="verify", workspace_root=workspace_root, message="Full verification")
        profile_snapshot = self.validation.profile_snapshot(workspace_root)
        events: list[ToolEvent] = []
        warnings: list[str] = []
        first_failure: CommandRun | None = None

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

        emit("workspace", "Workspace selected", detail=str(workspace_root))
        steps = self.validation.verification_plan(
            workspace_root,
            include_install=request.include_install,
            max_steps=request.max_steps,
        )
        if not steps:
            warnings.append("No verification commands were detected for this workspace.")
            emit(
                "verification",
                "No verification steps detected",
                status="warning",
                detail="Aegis could not infer install, configure, build, type-check, lint, database, or test commands.",
            )
            self.store.finish_task(task_id, "completed")
            return VerificationResponse(
                task_id=task_id,
                workspace_root=str(workspace_root),
                status="skipped",
                steps=[],
                events=events,
                validation_profile=profile_snapshot.profile,
                warnings=warnings,
            )

        emit(
            "verification",
            "Verification plan prepared",
            detail=f"{len(steps)} step(s) selected.",
            payload={"steps": [step.model_dump(exclude={"run"}) for step in steps]},
        )

        for step in steps:
            recipe = ValidationRecipe(
                command=step.command,
                label=step.label or step.command,
                source="verification",
                notes=step.reason,
            )
            emit(
                "verification",
                f"Running {step.phase}: {step.label or step.command}",
                detail=step.command,
                payload=step.model_dump(exclude={"run"}),
            )

            allowed_to_run, approval_reason = self.approvals.should_auto_run_command(step.command, manual=True)
            if not allowed_to_run:
                run = CommandRun(
                    command=step.command,
                    cwd=str(workspace_root),
                    allowed=False,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    timed_out=False,
                    reason=approval_reason,
                    category="permission",
                    summary=approval_reason,
                )
                step.run = run
                step.status = "blocked"
                first_failure = first_failure or run
                emit(
                    "approval",
                    "Verification step blocked",
                    status="warning",
                    detail=approval_reason,
                    payload=run.model_dump(),
                )
                if not request.continue_on_failure:
                    break
                continue

            result = self.commands.run(step.command, workspace_root, sandbox_profile=self.approvals.sandbox)
            run = self._command_run(result, recipe=recipe)
            step.run = run
            step.status = "succeeded" if self._validation_ok(run) else ("blocked" if not run.allowed else "failed")
            build_log_path = self._persist_validation_run(
                workspace_root,
                run,
                recipe=recipe,
                kind=f"verification:{step.phase or 'step'}",
            )
            payload = {**run.model_dump(), "phase": step.phase, "required": step.required}
            if build_log_path:
                payload["build_log_path"] = build_log_path
            emit(
                "command",
                f"Verification command {step.status}",
                status="ok" if step.status == "succeeded" else "error",
                detail=run.summary or run.reason,
                payload=payload,
            )

            if step.status != "succeeded":
                first_failure = first_failure or run
                if not request.continue_on_failure:
                    break

        status = self._verification_status(steps)
        if status == "passed" and profile_snapshot.profile is not None:
            self.validation.remember_success(workspace_root, profile_snapshot.profile)
        if any(step.status == "failed" and not step.required for step in steps):
            warnings.append("One or more optional verification steps failed; required steps still passed.")
        if any(step.status == "planned" for step in steps):
            warnings.append("Verification stopped before all planned steps ran.")

        self.store.finish_task(task_id, "completed" if status == "passed" else f"completed_with_verification_{status}")
        return VerificationResponse(
            task_id=task_id,
            workspace_root=str(workspace_root),
            status=status,
            steps=steps,
            events=events,
            validation_profile=profile_snapshot.profile,
            first_failure=first_failure,
            warnings=warnings,
        )

    async def preview_route(self, request: RoutePreviewRequest) -> RoutePreviewResponse:
        mode = self._resolve_mode(request.mode)
        mission_anchor = self._mission_anchor_from_history(request.history)
        effective_message = self._mission_aware_message(request.message, mission_anchor)
        workspace_root, _ = self._resolve_workspace_for_prompted_request(
            request.workspace_root,
            effective_message,
            mode,
            create=False,
        )
        workspace_files = self.workspace.scan(workspace_root, request.max_files)
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        instruction_files = self.workspace.discover_instruction_files(
            workspace_root,
            referenced_text=effective_message,
        )
        planner_message = self._planner_message_with_workspace_readiness(
            effective_message,
            workspace_root,
            instruction_files,
        )

        memory_hits = self.store.relevant_fix_history(project_root=workspace_root, query=effective_message, limit=3)
        project_memory_hits = self.store.relevant_project_memory(project_root=workspace_root, query=effective_message, limit=4)
        context_query = "\n".join(
            filter(
                None,
                [
                    planner_message,
                    self._mission_anchor_context(mission_anchor),
                    " ".join(item.content for item in request.history[-3:]),
                    " ".join(item.title for item in project_memory_hits[:3]),
                    " ".join(item.title for item in instruction_files[:4]),
                    " ".join(item.summary for item in instruction_files[:4]),
                    self._project_manifest_context(project_manifest),
                    self._dependency_profile_context(dependency_profile),
                    self._project_intelligence_context(workspace_root),
                ],
            )
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=[],
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        initial_profile = self.context_budgeter.profile_for(task_plan)
        context_files = self._select_context_files(
            workspace_root,
            workspace_files,
            context_query,
            limit=initial_profile.max_context_files,
            context_paths=request.context_paths,
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=context_files,
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )

        model_registry_snapshot = self.model_registry.snapshot()
        model_benchmark_snapshot = self.model_benchmarks.snapshot()
        route_health = self.store.route_health_signals(project_root=workspace_root, limit=200)
        model_execution_plan = self.model_execution_planner.build_plan(
            task_plan,
            providers=model_registry_snapshot.providers,
            roles=model_registry_snapshot.roles,
            benchmark_scores=model_benchmark_snapshot.provider_scores,
            route_health=route_health,
        )
        context_budget = self.context_budgeter.build_budget(
            task_plan=task_plan,
            workspace_files=workspace_files,
            context_files=context_files,
            memory_hits=memory_hits,
            project_memory_hits=project_memory_hits,
            history=request.history,
            provider_context_window=self._primary_context_window(model_execution_plan),
        )
        model_execution_plan = self.model_cost_estimator.estimate_plan(model_execution_plan, context_budget)

        return RoutePreviewResponse(
            workspace_root=str(workspace_root),
            mode=mode,
            task_plan=TaskPlanInfo.model_validate(task_plan.to_event_payload()),
            context_budget=ContextBudgetInfo.model_validate(context_budget.to_event_payload()),
            model_attempts=model_execution_plan.attempts,
            primary_attempt=model_execution_plan.primary,
            registry_message=model_registry_snapshot.message,
            benchmark_message=model_benchmark_snapshot.message,
            recommendations=self._route_preview_recommendations(
                task_plan=task_plan,
                model_execution_plan=model_execution_plan,
                workspace_file_count=len(workspace_files),
                registry_router_enabled=model_registry_snapshot.router_enabled,
                project_manifest=project_manifest,
                instruction_files=instruction_files,
            ),
        )

    async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
        mode = self._resolve_mode(request.mode)
        mission_anchor = self._mission_anchor_from_history(request.history)
        effective_message = self._mission_aware_message(request.message, mission_anchor)
        if prompt_requests_creative_media(effective_message):
            return False
        if (
            mission_anchor is not None
            and self._request_is_broad_mission_followup(request.message)
            and (
                self._request_expects_file_changes(effective_message, mode)
                or self._request_asks_for_validation(effective_message)
            )
        ):
            return False
        workspace_root, used_prompt_workspace = self._resolve_workspace_for_prompted_request(
            request.workspace_root,
            effective_message,
            mode,
            create=False,
        )
        if used_prompt_workspace and self._request_expects_file_changes(effective_message, mode):
            return False
        if (
            request.apply_changes
            or request.run_validation
            or self._request_asks_for_validation(effective_message)
            or request.validation_command_override.strip()
            or request.validation_label_override.strip()
            or request.validation_notes_override.strip()
        ):
            return False

        workspace_files = self.workspace.scan(workspace_root, request.max_files)
        instruction_files = self.workspace.discover_instruction_files(
            workspace_root,
            referenced_text=effective_message,
        )
        if self._broad_continue_should_follow_instruction_files(
            effective_message,
            instruction_files,
        ) or self._broad_continue_should_follow_workspace_readiness(effective_message, workspace_root):
            return False
        planner_message = self._planner_message_with_workspace_readiness(
            effective_message,
            workspace_root,
            instruction_files,
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=[],
            project_manifest=self.workspace.load_project_manifest(workspace_root),
            dependency_profile=self.workspace.inspect_dependency_profile(workspace_root),
        )
        return self._can_stream_direct_chat(request, mode, task_plan)

    async def stream_direct_chat_events(self, request: AgentRequest) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        mode = self._resolve_mode(request.mode)
        workspace_root, _ = self._resolve_workspace_for_prompted_request(
            request.workspace_root,
            request.message,
            mode,
            create=False,
        )
        request = request.model_copy(update={"workspace_root": str(workspace_root)})
        workspace_files = self.workspace.scan(workspace_root, request.max_files)
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        instruction_files = self.workspace.discover_instruction_files(
            workspace_root,
            referenced_text=request.message,
        )
        planner_message = self._planner_message_with_workspace_readiness(
            request.message,
            workspace_root,
            instruction_files,
        )
        task_id = self.store.create_task(mode=mode, workspace_root=workspace_root, message=request.message)
        events: list[ToolEvent] = []
        warnings: list[str] = []
        validation_profile = self.validation.profile_snapshot(workspace_root).profile

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

        emit(
            "workspace",
            "Workspace scanned",
            detail=f"{len(workspace_files)} file(s) found.",
            payload={"workspace_root": str(workspace_root), "file_count": len(workspace_files), "streaming": True},
        )
        yield (
            "status",
            {
                "type": "status",
                "stage": "planning",
                "message": "Preparing direct chat context.",
                "task_id": task_id,
            },
        )

        recent_tasks = [item for item in self.store.recent_tasks(project_root=workspace_root, limit=6) if item.id != task_id]
        memory_hits = self.store.relevant_fix_history(project_root=workspace_root, query=request.message, limit=3)
        project_memory_hits = self.store.relevant_project_memory(project_root=workspace_root, query=request.message, limit=4)

        context_query = "\n".join(
            filter(
                None,
                [
                    planner_message,
                    " ".join(item.content for item in request.history[-3:]),
                    " ".join(item.title for item in project_memory_hits[:3]),
                    " ".join(item.title for item in instruction_files[:4]),
                    " ".join(item.summary for item in instruction_files[:4]),
                    self._project_manifest_context(project_manifest),
                    self._dependency_profile_context(dependency_profile),
                    self._project_intelligence_context(workspace_root),
                ],
            )
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=[],
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        initial_profile = self.context_budgeter.profile_for(task_plan)
        context_files = self._select_context_files(
            workspace_root,
            workspace_files,
            context_query,
            limit=initial_profile.max_context_files,
            context_paths=request.context_paths,
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=context_files,
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        if not self._can_stream_direct_chat(request, mode, task_plan):
            self.store.finish_task(task_id, "canceled")
            raise RuntimeError("Direct chat streaming was requested for a task that needs the structured agent path.")

        emit("planner", "Direct chat stream plan prepared", detail=task_plan.summary, payload=task_plan.to_event_payload())
        model_registry_snapshot = self.model_registry.snapshot()
        model_benchmark_snapshot = self.model_benchmarks.snapshot()
        route_health = self.store.route_health_signals(project_root=workspace_root, limit=200)
        model_execution_plan = self.model_execution_planner.build_plan(
            task_plan,
            providers=model_registry_snapshot.providers,
            roles=model_registry_snapshot.roles,
            benchmark_scores=model_benchmark_snapshot.provider_scores,
            route_health=route_health,
        )
        context_budget = self.context_budgeter.build_budget(
            task_plan=task_plan,
            workspace_files=workspace_files,
            context_files=context_files,
            memory_hits=memory_hits,
            project_memory_hits=project_memory_hits,
            history=request.history,
            provider_context_window=self._primary_context_window(model_execution_plan),
        )
        context_files = context_budget.context_files
        memory_hits = context_budget.memory_hits
        project_memory_hits = context_budget.project_memory_hits
        model_execution_plan = self.model_cost_estimator.estimate_plan(model_execution_plan, context_budget)
        context_budget_info = ContextBudgetInfo.model_validate(context_budget.to_event_payload())
        self.store.record_context_budget(task_id=task_id, workspace_root=workspace_root, context_budget=context_budget_info)
        self.store.record_model_attempts(task_id=task_id, workspace_root=workspace_root, attempts=model_execution_plan.attempts)
        emit(
            "context",
            "Direct chat context budget prepared",
            detail=f"{context_budget.estimated_context_tokens} estimated token(s) for a read-only chat answer.",
            payload={**context_budget.to_event_payload(), "paths": [item.path for item in context_files]},
        )
        emit(
            "model-router",
            "Direct chat streaming route prepared",
            detail=f"{len(model_execution_plan.attempts)} planned model attempt(s).",
            payload={
                **model_execution_plan.to_event_payload(),
                "streaming": True,
                "router_execution_enabled": self.settings.aegis_router_execution_enabled,
            },
        )

        messages = self._direct_chat_messages(
            request,
            mode,
            workspace_root,
            workspace_files,
            context_files,
            memory_hits,
            project_memory_hits,
            recent_tasks,
            task_plan,
            context_budget,
        )
        yield (
            "status",
            {
                "type": "status",
                "stage": "model_stream",
                "message": "Streaming the assistant answer.",
                "task_id": task_id,
            },
        )

        reply_parts: list[str] = []
        live_model_attempts: list[ModelAttemptInfo] | None = None
        provider_lookup = {provider.id: provider for provider in model_registry_snapshot.providers}

        if self.settings.aegis_router_execution_enabled:
            live_model_attempts = []
            for planned in model_execution_plan.attempts:
                if planned.provider_api in {"internal", "router"} or not planned.retryable:
                    live_model_attempts.append(
                        planned.model_copy(
                            update={
                                "status": "skipped",
                                "reason": planned.reason
                                or "No executable provider adapter is available for this planned attempt.",
                                "finished_at": utc_now(),
                            }
                        )
                    )
                    continue

                provider = provider_lookup.get(planned.provider_id)
                config = provider_config_from_attempt(planned, self.settings, provider)
                preflight_issue = self.model_attempt_executor._preflight_issue(config)
                if preflight_issue is not None:
                    live_model_attempts.append(
                        planned.model_copy(
                            update={
                                "status": "skipped",
                                "provider_id": config.provider_id,
                                "provider_label": config.label,
                                "provider_api": config.api,
                                "endpoint": config.endpoint,
                                "model": config.model,
                                "error": preflight_issue["message"],
                                "retryable": False,
                                "finished_at": utc_now(),
                                "metadata": {
                                    **planned.metadata,
                                    "registry_resolved": provider is not None,
                                    "preflight": True,
                                    "error_code": preflight_issue["code"],
                                    "secret_env": preflight_issue.get("secret_env", ""),
                                    "streaming": True,
                                },
                            }
                        )
                    )
                    continue

                adapter = build_provider_adapter(self.settings, config)
                started = utc_now()
                start_time = time.perf_counter()
                running = planned.model_copy(
                    update={
                        "status": "running",
                        "provider_id": config.provider_id,
                        "provider_label": config.label,
                        "provider_api": config.api,
                        "endpoint": config.endpoint,
                        "model": config.model,
                        "started_at": started,
                        "metadata": {
                            **planned.metadata,
                            "registry_resolved": provider is not None,
                            "adapter": adapter.__class__.__name__,
                            "streaming": True,
                        },
                    }
                )
                yield (
                    "status",
                    {
                        "type": "status",
                        "stage": "provider_stream",
                        "message": f"Streaming with {config.label or config.provider_id}.",
                        "task_id": task_id,
                        "provider_id": config.provider_id,
                        "model": config.model,
                    },
                )
                candidate_parts: list[str] = []
                try:
                    async for event in adapter.stream_text(messages):
                        if event.type == "delta" and event.delta:
                            candidate_parts.append(event.delta)
                            yield (
                                "delta",
                                {
                                    "type": "delta",
                                    "delta": event.delta,
                                    "task_id": task_id,
                                    "provider_id": config.provider_id,
                                    "model": config.model,
                                },
                            )
                except ProviderError as exc:
                    live_model_attempts.append(
                        running.model_copy(
                            update={
                                "status": "failed",
                                "error": exc.safe_message,
                                "retryable": exc.retryable,
                                "latency_ms": max(0, int((time.perf_counter() - start_time) * 1000)),
                                "finished_at": utc_now(),
                                "metadata": {
                                    **running.metadata,
                                    "error_code": exc.code,
                                    "status_code": exc.status_code,
                                    "developer_error": exc.message,
                                },
                            }
                        )
                    )
                    if not exc.retryable:
                        continue
                    continue
                except Exception as exc:
                    live_model_attempts.append(
                        running.model_copy(
                            update={
                                "status": "failed",
                                "error": "Provider stream failed before returning a complete response.",
                                "retryable": True,
                                "latency_ms": max(0, int((time.perf_counter() - start_time) * 1000)),
                                "finished_at": utc_now(),
                                "metadata": {
                                    **running.metadata,
                                    "error_code": "unexpected_provider_stream_error",
                                    "developer_error": str(exc),
                                },
                            }
                        )
                    )
                    continue

                metadata_fn = getattr(adapter, "completion_metadata", None)
                completion_metadata = metadata_fn() if callable(metadata_fn) else {}
                reply_parts = candidate_parts
                live_model_attempts.append(
                    running.model_copy(
                        update={
                            "status": "succeeded",
                            "latency_ms": max(0, int((time.perf_counter() - start_time) * 1000)),
                            "finished_at": utc_now(),
                            "output_tokens": self._estimate_text_tokens("".join(candidate_parts)),
                            "metadata": {
                                **running.metadata,
                                **(completion_metadata if isinstance(completion_metadata, dict) else {}),
                            },
                        }
                    )
                )
                break
        else:
            status = await self.model.status()
            emit(
                "model",
                "Local model status checked for direct chat stream",
                status="ok" if status.ready else "warning",
                detail=status.message,
                payload={"model": self.model.label, "endpoint": self.model.endpoint, "api": self.model.api},
            )
            if status.ready:
                start_time = time.perf_counter()
                try:
                    async for event in self.model.stream_text(messages):
                        if event.type == "delta" and event.delta:
                            reply_parts.append(event.delta)
                            yield ("delta", {"type": "delta", "delta": event.delta, "task_id": task_id})
                    model_execution_plan = ModelExecutionPlan(
                        attempts=[
                            item.model_copy(
                                update={
                                    "status": "succeeded" if index == 0 else item.status,
                                    "latency_ms": max(0, int((time.perf_counter() - start_time) * 1000)) if index == 0 else item.latency_ms,
                                    "finished_at": utc_now() if index == 0 else item.finished_at,
                                    "output_tokens": self._estimate_text_tokens("".join(reply_parts)) if index == 0 else item.output_tokens,
                                    "metadata": {**item.metadata, "streaming": index == 0},
                                }
                            )
                            for index, item in enumerate(model_execution_plan.attempts)
                        ]
                    )
                except Exception as exc:
                    warnings.append(str(exc))
                    emit("model", "Local model stream failed", status="error", detail=str(exc))
            else:
                warnings.append("Local model was unavailable, so Aegis used the deterministic fallback engine.")

        if live_model_attempts is not None:
            model_execution_plan = ModelExecutionPlan(
                attempts=self._merge_model_attempts(model_execution_plan.attempts, live_model_attempts)
            )
            self.store.record_model_attempts(
                task_id=task_id,
                workspace_root=workspace_root,
                attempts=model_execution_plan.attempts,
                replace_for_task=True,
            )

        reply = "".join(reply_parts).strip()
        if not reply:
            fallback = self._fallback_draft(request.message, "chat", workspace_root, context_files or workspace_files)
            reply = fallback.reply
            warnings.extend(fallback.warnings)
            if reply:
                yield ("delta", {"type": "delta", "delta": reply, "task_id": task_id, "source": "fallback"})
            emit(
                "model",
                "Direct chat stream used fallback",
                status="warning",
                detail="No provider produced streamed text for this turn.",
            )
        else:
            emit(
                "model",
                "Direct chat stream completed",
                detail=f"Streamed {len(reply)} character(s) for a read-only chat answer.",
            )

        self.store.finish_task(task_id, "completed")
        response = AgentResponse(
            task_id=task_id,
            reply=reply,
            plan=task_plan.steps or ["Answer the prompt directly."],
            changes=[],
            applied=[],
            checkpoint=None,
            warnings=warnings,
            events=events,
            validation=None,
            validation_profile=validation_profile,
            task_plan=TaskPlanInfo.model_validate(task_plan.to_event_payload()),
            context_budget=context_budget_info,
            model_attempts=model_execution_plan.attempts,
            assistant_name=self.settings.aegis_assistant_name,
            mode=mode,
            engine=self._engine_label(model_execution_plan),
            workspace_root=str(workspace_root),
            workspace_files=workspace_files,
            context_files=context_files,
            memory_hits=memory_hits,
            project_memory_hits=project_memory_hits,
            recent_tasks=recent_tasks,
            repair_attempts=[],
            completion_quality=CompletionQualityInfo(
                status="ready",
                score=1.0,
                reasons=["Direct chat answer completed without workspace edits."],
                should_continue=False,
            ),
        )
        yield (
            "status",
            {
                "type": "status",
                "stage": "finalizing",
                "message": "Final streamed chat response is ready.",
                "task_id": task_id,
            },
        )
        yield ("final", {"type": "final", "task_id": task_id, "response": response.model_dump(mode="json")})

    async def run(
        self,
        request: AgentRequest,
        stream_delta_callback: StreamDeltaCallback | None = None,
    ) -> AgentResponse:
        mode = self._resolve_mode(request.mode)
        original_message = request.message
        mission_anchor = self._mission_anchor_from_history(request.history)
        effective_message = self._mission_aware_message(request.message, mission_anchor)
        workspace_root, used_prompt_workspace = self._resolve_workspace_for_prompted_request(
            request.workspace_root,
            effective_message,
            mode,
            create=True,
        )
        request = request.model_copy(update={"workspace_root": str(workspace_root), "message": effective_message})
        workspace_files = self.workspace.scan(workspace_root, request.max_files)
        if self._request_asks_for_validation(request.message) and not request.run_validation:
            request = request.model_copy(update={"run_validation": True})
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        task_id = self.store.create_task(mode=mode, workspace_root=workspace_root, message=original_message)
        if prompt_requests_creative_media(request.message):
            return self.creative_chat.run(
                request,
                mode=mode,
                workspace_root=workspace_root,
                workspace_files=workspace_files,
                project_manifest=project_manifest,
                dependency_profile=dependency_profile,
                task_id=task_id,
                original_message=original_message,
            )
        tracks_project_work = (
            self._request_expects_file_changes(request.message, mode)
            or request.apply_changes
            or request.run_validation
            or self.settings.aegis_auto_run_validation
        )
        context_files: list[WorkspaceFile] = []

        events: list[ToolEvent] = []
        warnings: list[str] = []
        applied: list[str] = []
        checkpoint: str | None = None
        validation: CommandRun | None = None
        validation_profile = self.validation.profile_snapshot(workspace_root).profile
        repair_attempts: list[RepairAttempt] = []
        approval_pending = False
        multi_agent = MultiAgentCoordinator(self.store)

        state_event = self.store.transition_task(
            task_id,
            "planning",
            title="Task planning started",
            detail="Aegis created a structured task graph for this request.",
        )
        if state_event is not None:
            events.append(state_event)
        if tracks_project_work:
            self.store.create_default_subtasks(
                parent_task_id=task_id,
                workspace_root=workspace_root,
                mode=mode,
                user_goal=original_message,
            )

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

        def agent_output(
            role,
            title: str,
            *,
            summary: str = "",
            status: str = "ok",
            outputs: dict[str, Any] | None = None,
            iteration: int = 1,
        ) -> None:
            if not tracks_project_work:
                return
            events.append(
                multi_agent.agent_output(
                    task_id,
                    role,
                    title,
                    summary=summary,
                    status=status,
                    outputs=outputs,
                    iteration=iteration,
                )
            )

        def agent_handoff(from_role, to_role, *, reason: str = "", artifacts: dict[str, Any] | None = None) -> None:
            if not tracks_project_work:
                return
            events.append(
                multi_agent.handoff(
                    task_id,
                    from_role,
                    to_role,
                    reason=reason,
                    artifacts=artifacts,
                )
            )

        def agent_approval(role, *, reason: str, blocked_paths: list[str]) -> None:
            if not tracks_project_work:
                return
            events.append(
                multi_agent.approval_requested(
                    task_id,
                    role,
                    reason=reason,
                    blocked_paths=blocked_paths,
                )
            )

        if tracks_project_work:
            events.append(
                multi_agent.start_chain(
                    task_id,
                    workspace_root=workspace_root,
                    user_goal=original_message,
                )
            )
            agent_output(
                "planner",
                "Planner Agent accepted goal",
                summary="Planner Agent is shaping the user request into a task plan and context requirements.",
                outputs={"mode": mode, "workspace_root": str(workspace_root)},
            )

        emit(
            "workspace",
            "Workspace scanned",
            detail=f"{len(workspace_files)} file(s) found.",
            payload={"workspace_root": str(workspace_root), "file_count": len(workspace_files)},
        )
        if tracks_project_work:
            self.store.transition_subtask(task_id, "Inspect project", "completed", detail=f"{len(workspace_files)} file(s) inspected.")
        if used_prompt_workspace:
            emit(
                "workspace",
                "Explicit prompt workspace selected",
                detail=f"Using the path from the user request: {workspace_root}",
                payload={"workspace_root": str(workspace_root), "source": "prompt_path"},
            )
        if project_manifest is not None:
            emit(
                "workspace",
                "Aegis project manifest loaded",
                detail=(
                    f"{project_manifest.title or project_manifest.project_name or 'Workspace'} "
                    f"uses {project_manifest.framework or project_manifest.preset_label or 'a manifest-defined stack'}."
                ),
                payload={
                    "project_name": project_manifest.project_name,
                    "preset": project_manifest.preset_label or project_manifest.preset_id,
                    "framework": project_manifest.framework,
                    "language": project_manifest.language,
                    "validation_command": project_manifest.validation_command,
                },
            )
        if dependency_profile.config_files:
            emit(
                "workspace",
                "Dependency profile detected",
                detail=(
                    f"{', '.join(dependency_profile.languages[:3]) or 'Project'} "
                    f"with {len(dependency_profile.config_files)} manifest/config file(s)."
                ),
                payload={
                    "languages": dependency_profile.languages,
                    "frameworks": dependency_profile.frameworks,
                    "package_managers": dependency_profile.package_managers,
                    "build_systems": dependency_profile.build_systems,
                    "validation_commands": dependency_profile.validation_commands,
                    "config_files": dependency_profile.config_files,
                },
            )
        instruction_files = self.workspace.discover_instruction_files(
            workspace_root,
            referenced_text=request.message,
        )
        planner_message = self._planner_message_with_workspace_readiness(
            request.message,
            workspace_root,
            instruction_files,
        )
        if instruction_files:
            emit(
                "context",
                "Project instruction files loaded",
                detail=f"{len(instruction_files)} todo/roadmap-style file(s) will guide this pass.",
                payload={
                    "paths": [item.path for item in instruction_files],
                    "open_items": sum(item.pending_count for item in instruction_files),
                },
            )
        project_status_context = self._project_status_context(workspace_root)
        if project_status_context:
            emit(
                "context",
                "Project build state loaded",
                detail="Recent commands, open validation errors, and the latest build log excerpt were added to context.",
                payload={"has_build_log": ".aegis/build_logs/" in project_status_context},
            )

        stored_note_count = self._store_project_notes_from_message(workspace_root, original_message)
        recent_tasks = [item for item in self.store.recent_tasks(project_root=workspace_root, limit=6) if item.id != task_id]
        memory_hits = self.store.relevant_fix_history(project_root=workspace_root, query=request.message, limit=3)
        project_memory_hits = self.store.relevant_project_memory(project_root=workspace_root, query=request.message, limit=4)

        if stored_note_count:
            emit(
                "memory",
                "Project notes recorded",
                detail=f"{stored_note_count} durable project note(s) were extracted from the request.",
            )

        if recent_tasks:
            emit(
                "history",
                "Recent task history loaded",
                detail=f"{len(recent_tasks)} recent task(s) added to context.",
            )
        if memory_hits:
            emit(
                "memory",
                "Repair memory loaded",
                detail=f"{len(memory_hits)} prior fix pattern(s) added to context.",
                payload={"memory_ids": [item.id for item in memory_hits]},
            )
        if project_memory_hits:
            emit(
                "memory",
                "Project memory loaded",
                detail=f"{len(project_memory_hits)} project note(s) added to context.",
                payload={"project_memory_ids": [item.id for item in project_memory_hits]},
            )

        context_query = "\n".join(
            filter(
                None,
                [
                    planner_message,
                    " ".join(item.content for item in request.history[-3:]),
                    " ".join(item.title for item in project_memory_hits[:3]),
                    " ".join(item.title for item in instruction_files[:4]),
                    " ".join(item.summary for item in instruction_files[:4]),
                    self._project_manifest_context(project_manifest),
                    self._dependency_profile_context(dependency_profile),
                    project_status_context,
                ],
            )
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=[],
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        initial_profile = self.context_budgeter.profile_for(task_plan)
        context_files = self._select_context_files(
            workspace_root,
            workspace_files,
            context_query,
            limit=initial_profile.max_context_files,
            context_paths=request.context_paths,
        )
        task_plan = self.task_planner.build_plan(
            message=planner_message,
            mode=mode,
            workspace_files=workspace_files,
            context_files=context_files,
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        emit(
            "planner",
            "Task plan prepared",
            detail=task_plan.summary,
            payload=task_plan.to_event_payload(),
        )
        agent_output(
            "planner",
            "Planner Agent created task plan",
            summary=task_plan.summary,
            outputs={
                "intent": task_plan.intent,
                "objective": task_plan.objective,
                "steps": task_plan.steps,
                "risks": task_plan.risks,
                "context_requirements": task_plan.context_requirements,
                "selected_context_files": [item.path for item in context_files],
            },
        )
        agent_handoff(
            "planner",
            "architect",
            reason="Plan is ready for architecture consistency review.",
            artifacts={"step_count": len(task_plan.steps), "risk_count": len(task_plan.risks)},
        )
        agent_output(
            "architect",
            "Architect Agent reviewed project structure",
            summary="Architecture review checked detected stack, config files, module boundaries, and selected context before code generation.",
            outputs={
                "frameworks": dependency_profile.frameworks,
                "languages": dependency_profile.languages,
                "config_files": dependency_profile.config_files,
                "entry_points": dependency_profile.entry_points,
                "important_context_files": [item.path for item in context_files[:8]],
            },
        )
        agent_handoff(
            "architect",
            "code",
            reason="Architecture constraints and relevant files are ready for implementation.",
            artifacts={"context_files": [item.path for item in context_files]},
        )
        if tracks_project_work:
            self.store.transition_subtask(task_id, "Plan changes", "completed", detail=task_plan.summary)
        state_event = self.store.transition_task(
            task_id,
            "running",
            title="Task execution started",
            detail=task_plan.summary,
            payload={"assigned_agent_role": task_plan.route_profile.get("role", "") if isinstance(task_plan.route_profile, dict) else ""},
        )
        if state_event is not None:
            events.append(state_event)
        model_registry_snapshot = self.model_registry.snapshot()
        model_benchmark_snapshot = self.model_benchmarks.snapshot()
        route_health = self.store.route_health_signals(project_root=workspace_root, limit=200)
        model_execution_plan = self.model_execution_planner.build_plan(
            task_plan,
            providers=model_registry_snapshot.providers,
            roles=model_registry_snapshot.roles,
            benchmark_scores=model_benchmark_snapshot.provider_scores,
            route_health=route_health,
        )
        context_budget = self.context_budgeter.build_budget(
            task_plan=task_plan,
            workspace_files=workspace_files,
            context_files=context_files,
            memory_hits=memory_hits,
            project_memory_hits=project_memory_hits,
            history=request.history,
            provider_context_window=self._primary_context_window(model_execution_plan),
        )
        context_files = context_budget.context_files
        memory_hits = context_budget.memory_hits
        project_memory_hits = context_budget.project_memory_hits
        model_execution_plan = self.model_cost_estimator.estimate_plan(model_execution_plan, context_budget)
        context_budget_info = ContextBudgetInfo.model_validate(context_budget.to_event_payload())
        self.store.record_context_budget(
            task_id=task_id,
            workspace_root=workspace_root,
            context_budget=context_budget_info,
        )
        self.store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace_root,
            attempts=model_execution_plan.attempts,
        )
        emit(
            "context",
            "Context budget prepared",
            detail=(
                f"{context_budget.estimated_context_tokens} estimated token(s) across "
                f"{len(context_files)} file(s), {len(memory_hits)} repair memory item(s), "
                f"and {len(project_memory_hits)} project memory item(s)."
            ),
            payload={
                **context_budget.to_event_payload(),
                "paths": [item.path for item in context_files],
            },
        )
        emit(
            "model-router",
            "Model execution plan prepared",
            detail=f"{len(model_execution_plan.attempts)} planned model attempt(s).",
            payload={
                **model_execution_plan.to_event_payload(),
                "router_execution_enabled": self.settings.aegis_router_execution_enabled,
                "benchmark_results_total": model_benchmark_snapshot.results_total,
                "benchmark_latest_at": model_benchmark_snapshot.latest_at,
            },
        )
        agent_output(
            "code",
            "Code Agent started implementation draft",
            summary="Code Agent is using the selected context and model route to produce the smallest useful change set.",
            outputs={
                "context_files": [item.path for item in context_files],
                "planned_model_attempts": len(model_execution_plan.attempts),
                "apply_changes": request.apply_changes,
            },
        )

        try:
            draft, live_model_attempts = await self._draft_response(
                request,
                mode,
                workspace_root,
                workspace_files,
                context_files,
                memory_hits,
                project_memory_hits,
                recent_tasks,
                task_plan,
                context_budget,
                model_execution_plan,
                model_registry_snapshot.providers,
                emit,
                stream_delta_callback,
            )
            if live_model_attempts is not None:
                model_execution_plan = ModelExecutionPlan(attempts=live_model_attempts)
                self.store.record_model_attempts(
                    task_id=task_id,
                    workspace_root=workspace_root,
                    attempts=model_execution_plan.attempts,
                    replace_for_task=True,
                )
            warnings.extend(draft.warnings)
            self._record_command_proposals(draft, emit)
            agent_output(
                "code",
                "Code Agent produced draft",
                summary=f"Draft contains {len(draft.changes)} file change(s), {len(draft.plan)} plan step(s), and {len(draft.proposed_commands)} proposed command(s).",
                outputs={
                    "changed_paths": [change.path for change in draft.changes],
                    "change_actions": [change.action for change in draft.changes],
                    "proposed_commands": [
                        str(command.get("command") or command.get("label") or command)
                        if isinstance(command, dict)
                        else str(command)
                        for command in draft.proposed_commands
                    ],
                    "warning_count": len(draft.warnings),
                },
            )
            agent_handoff(
                "code",
                "review",
                reason="Implementation draft is ready for deterministic review before apply or validation.",
                artifacts={"changed_paths": [change.path for change in draft.changes]},
            )
            review_findings = self._review_agent_findings(draft, request=request, mode=mode)
            agent_output(
                "review",
                "Review Agent checked implementation draft",
                status="warning" if review_findings else "ok",
                summary="; ".join(review_findings[:3]) if review_findings else "No obvious draft-level issues were found.",
                outputs={
                    "findings": review_findings,
                    "changed_paths": [change.path for change in draft.changes],
                    "change_count": len(draft.changes),
                    "matches_requested_file_work": bool(draft.changes) or not self._turn_expects_file_work(request, mode, task_plan),
                },
            )
            if tracks_project_work:
                self.store.transition_subtask(
                    task_id,
                    "Review changes",
                    "completed" if not review_findings else "blocked" if request.apply_changes and not draft.changes else "completed",
                    detail="; ".join(review_findings[:2]) if review_findings else "Review Agent found no obvious draft-level issues.",
                )
            validation_override_recipe = None
            if request.run_validation or self.settings.aegis_auto_run_validation:
                validation_override_recipe = self._turn_validation_override_recipe(request, draft, workspace_root)
            if validation_override_recipe and validation_override_recipe.source == "draft-proposal":
                emit(
                    "validation",
                    "Draft validation command selected",
                    detail=validation_override_recipe.command,
                    payload={"recipe": validation_override_recipe.model_dump()},
                )
            if request.run_validation or self.settings.aegis_auto_run_validation:
                selected_validation_command = (
                    validation_override_recipe.command
                    if validation_override_recipe
                    else validation_profile.command
                    if validation_profile
                    else ""
                )
                selected_validation_source = (
                    validation_override_recipe.source
                    if validation_override_recipe
                    else validation_profile.source
                    if validation_profile
                    else ""
                )
                selected_validation_label = (
                    validation_override_recipe.label
                    if validation_override_recipe
                    else validation_profile.label
                    if validation_profile
                    else ""
                )
                agent_handoff(
                    "review",
                    "validation",
                    reason="Draft review is complete and validation was requested for this turn.",
                    artifacts={
                        "selected_command": selected_validation_command,
                        "source": selected_validation_source,
                    },
                )
                agent_output(
                    "validation",
                    "Validation Agent selected command",
                    summary=selected_validation_command or "No validation command selected yet.",
                    status="ok" if selected_validation_command else "warning",
                    outputs={
                        "command": selected_validation_command,
                        "source": selected_validation_source,
                        "label": selected_validation_label,
                    },
                )

            if request.apply_changes and draft.changes:
                auto_applied_changes, blocked_changes = self.approvals.partition_auto_apply_changes(draft.changes)

                if blocked_changes:
                    approval_pending = True
                    warnings.append(
                        "Some generated changes require manual approval under the current approval tier, so they were kept as preview-only."
                    )
                    emit(
                        "approval",
                        "Manual approval required",
                        status="warning",
                        detail=f"{len(blocked_changes)} change(s) require manual review before they can be applied automatically.",
                        payload={
                            "tier": self.approvals.tier.value,
                            "blocked_paths": [change.path for change, _ in blocked_changes],
                            "reasons": [
                                {
                                    "path": decision.path,
                                    "reason": decision.reason,
                                    "risk_level": decision.risk_level,
                                }
                                for _, decision in blocked_changes
                            ],
                        },
                    )
                    agent_approval(
                        "code",
                        reason=f"{len(blocked_changes)} generated change(s) require manual approval before automatic apply.",
                        blocked_paths=[change.path for change, _ in blocked_changes],
                    )
                    try:
                        state_event = self.store.transition_task(
                            task_id,
                            "needs_approval",
                            title="Task waiting for approval",
                            detail=f"{len(blocked_changes)} generated change(s) require manual approval.",
                            payload={"blocked_paths": [change.path for change, _ in blocked_changes]},
                        )
                        if state_event is not None:
                            events.append(state_event)
                    except ValueError:
                        pass

                if auto_applied_changes:
                    if approval_pending:
                        try:
                            state_event = self.store.transition_task(
                                task_id,
                                "running",
                                title="Task continued with approved subset",
                                detail="Aegis continued with changes allowed by the current approval tier.",
                            )
                            if state_event is not None:
                                events.append(state_event)
                        except ValueError:
                            pass
                    apply_result = self.workspace.apply_changes(workspace_root, auto_applied_changes)
                    applied = apply_result.applied
                    checkpoint = apply_result.checkpoint
                    warnings.extend(apply_result.warnings)
                    workspace_files = self.workspace.scan(workspace_root, request.max_files)
                    self.store.add_task_artifacts(
                        task_id,
                        related_files=[change.path for change in auto_applied_changes],
                        checkpoints=[apply_result.checkpoint] if apply_result.checkpoint else [],
                    )
                    if tracks_project_work:
                        self.store.transition_subtask(task_id, "Edit files", "completed", detail=f"{len(applied)} change(s) applied.")
                    emit(
                        "write",
                        "Preview changes applied",
                        detail=f"{len(applied)} change(s) applied.",
                        payload={"applied": applied, "checkpoint": apply_result.checkpoint},
                    )

                    if request.run_validation or self.settings.aegis_auto_run_validation:
                        validation, repair_attempts, memory_hits = await self._validate_and_repair(
                            task_id=task_id,
                            request=request,
                            mode=mode,
                            workspace_root=workspace_root,
                            workspace_files=workspace_files,
                            draft=draft,
                            memory_hits=memory_hits,
                            project_memory_hits=project_memory_hits,
                            warnings=warnings,
                            applied=applied,
                            emit=emit,
                            validation_override=validation_override_recipe,
                            multi_agent=multi_agent if tracks_project_work else None,
                            agent_events=events,
                        )
                        validation_profile = self.validation.profile_snapshot(workspace_root).profile
                elif blocked_changes:
                    if tracks_project_work:
                        self.store.transition_subtask(task_id, "Edit files", "blocked", detail="Generated changes require approval.")
                    emit(
                        "write",
                        "Automatic apply paused",
                        status="warning",
                        detail="The current approval tier kept all generated changes in preview mode.",
                        payload={"tier": self.approvals.tier.value},
                    )

            validation_requested = request.run_validation or self.settings.aegis_auto_run_validation
            preview_only_changes = bool(draft.changes) and not applied
            if validation_requested and validation is None and not preview_only_changes:
                if request.apply_changes and request.max_repair_attempts > 0:
                    validation, repair_attempts, memory_hits = await self._validate_and_repair(
                        task_id=task_id,
                        request=request,
                        mode=mode,
                        workspace_root=workspace_root,
                        workspace_files=workspace_files,
                        draft=draft,
                        memory_hits=memory_hits,
                        project_memory_hits=project_memory_hits,
                        warnings=warnings,
                        applied=applied,
                        emit=emit,
                        validation_override=validation_override_recipe,
                        multi_agent=multi_agent if tracks_project_work else None,
                        agent_events=events,
                    )
                else:
                    emit(
                        "validation",
                        "Validation requested for current workspace",
                        detail="No file changes were applied in this turn, so Aegis is validating the existing workspace state.",
                    )
                    state_event = self.store.transition_task(
                        task_id,
                        "validating",
                        title="Task validation started",
                        detail="Running validation against the current workspace.",
                    )
                    if state_event is not None:
                        events.append(state_event)
                    validation = self._run_validation(
                        workspace_root,
                        emit,
                        override_recipe=validation_override_recipe,
                    )
                    if validation is not None:
                        agent_output(
                            "validation",
                            "Validation Agent interpreted result",
                            status="ok" if self._validation_ok(validation) else "error",
                            summary=validation.summary or validation.reason or validation.command,
                            outputs={
                                "command": validation.command,
                                "exit_code": validation.exit_code,
                                "allowed": validation.allowed,
                                "timed_out": validation.timed_out,
                                "category": self._categorize_validation_failure(validation)
                                if not self._validation_ok(validation)
                                else "passed",
                            },
                        )
                    if validation is not None:
                        self.store.add_task_artifacts(
                            task_id,
                            validation_commands=[validation.command] if validation.command else [],
                            error_summary=self._error_signature(validation) if not self._validation_ok(validation) else "",
                        )
                        if tracks_project_work:
                            self.store.transition_subtask(
                                task_id,
                                "Run validation",
                                "completed" if self._validation_ok(validation) else "failed",
                                detail=validation.summary or validation.reason,
                            )
                validation_profile = self.validation.profile_snapshot(workspace_root).profile
            elif validation_requested and validation is None and preview_only_changes:
                warnings.append(
                    "Validation was requested, but generated changes are still preview-only; apply the changes before validating that draft."
                )
                emit(
                    "validation",
                    "Validation deferred until changes are applied",
                    status="warning",
                    detail="Aegis kept validation on hold because the generated file changes were not applied to the workspace.",
                )

            if validation is not None:
                validation_profile = self.validation.profile_snapshot(workspace_root).profile

            completion_quality = self._completion_quality(
                request=request.model_copy(update={"message": planner_message}),
                mode=mode,
                draft=draft,
                applied=applied,
                validation=validation,
                workspace_root=workspace_root,
                workspace_files=workspace_files,
            )
            emit(
                "quality",
                "Completion quality assessed",
                status="warning" if completion_quality.should_continue else "ok",
                detail="; ".join(completion_quality.reasons[:2]) or completion_quality.status,
                payload=completion_quality.model_dump(mode="json"),
            )
            final_instruction_files = self.workspace.discover_instruction_files(
                workspace_root,
                max_files=12,
                referenced_text=request.message,
            )
            instruction_status = self._record_instruction_status(
                workspace_root,
                final_instruction_files,
                request_message=request.message,
                validation=validation,
                completion_quality=completion_quality,
                applied=applied,
            )
            if instruction_status is not None:
                emit(
                    "memory",
                    "Instruction status checkpoint saved",
                    status="warning" if instruction_status.get("open_items") else "ok",
                    detail=(
                        f"{instruction_status.get('open_items', 0)} open item(s), "
                        f"{instruction_status.get('completed_items', 0)} completed item(s) tracked for future autopilot passes."
                    ),
                    payload={
                        "path": ".aegis/instruction_status.json",
                        "open_items": instruction_status.get("open_items", 0),
                        "completed_items": instruction_status.get("completed_items", 0),
                        "recommendation": instruction_status.get("recommendation", ""),
                    },
                )
            agent_handoff(
                "validation" if validation_requested else "review",
                "memory",
                reason="Execution results are ready to persist into project memory and task artifacts.",
                artifacts={
                    "validation_status": "passed"
                    if validation and self._validation_ok(validation)
                    else "failed"
                    if validation
                    else "not_run",
                    "applied": applied,
                    "repair_attempt_count": len(repair_attempts),
                },
            )
            agent_output(
                "memory",
                "Memory Agent recorded outcome context",
                summary="Memory Agent updated task artifacts, instruction status, repair memory, and project continuity where applicable.",
                outputs={
                    "stored_project_note_count": stored_note_count,
                    "project_memory_hits": [item.id for item in project_memory_hits],
                    "repair_attempt_count": len(repair_attempts),
                    "instruction_status_saved": instruction_status is not None,
                },
            )
            if tracks_project_work:
                self.store.transition_subtask(
                    task_id,
                    "Update memory",
                    "completed",
                    detail="Memory Agent recorded durable task and project context.",
                )

            final_summary = self._final_reply(
                draft.reply,
                applied=applied,
                validation=validation,
                completion_quality=completion_quality,
            )
            self.store.add_task_artifacts(
                task_id,
                related_files=[change.path for change in draft.changes],
                checkpoints=[checkpoint] if checkpoint else [],
                validation_commands=[validation.command] if validation and validation.command else [],
                error_summary=self._error_signature(validation) if validation and not self._validation_ok(validation) else "",
                final_summary=final_summary,
            )
            if tracks_project_work:
                self.store.transition_subtask(task_id, "Summarize outcome", "completed", detail=completion_quality.status)

            if approval_pending and not applied:
                state_event = None
            else:
                state_event = self.store.transition_task(
                    task_id,
                    "failed" if validation and not self._validation_ok(validation) else "completed",
                    title="Task failed" if validation and not self._validation_ok(validation) else "Task completed",
                    detail=final_summary[:500],
                    error_summary=self._error_signature(validation) if validation and not self._validation_ok(validation) else "",
                    final_summary=final_summary,
                )
            if state_event is not None:
                events.append(state_event)

            return AgentResponse(
                task_id=task_id,
                reply=final_summary,
                plan=draft.plan,
                changes=draft.changes,
                applied=applied,
                checkpoint=checkpoint,
                warnings=warnings,
                events=events,
                validation=validation,
                validation_profile=validation_profile,
                task_plan=TaskPlanInfo.model_validate(task_plan.to_event_payload()),
                context_budget=context_budget_info,
                model_attempts=model_execution_plan.attempts,
                assistant_name=self.settings.aegis_assistant_name,
                mode=mode,
                engine=self._engine_label(model_execution_plan),
                workspace_root=str(workspace_root),
                workspace_files=workspace_files,
                context_files=context_files,
                memory_hits=memory_hits,
                project_memory_hits=project_memory_hits,
                recent_tasks=recent_tasks,
                repair_attempts=repair_attempts,
                completion_quality=completion_quality,
            )
        except Exception as exc:
            if tracks_project_work:
                try:
                    events.append(
                        multi_agent.failure(
                            task_id,
                            "code",
                            summary=f"Multi-agent execution stopped: {type(exc).__name__}: {exc}",
                            outputs={"exception_type": type(exc).__name__},
                        )
                    )
                except Exception:
                    pass
            self.store.finish_task(task_id, "error")
            raise

    def _review_agent_findings(self, draft: AgentDraft, *, request: AgentRequest, mode: ModeName) -> list[str]:
        findings: list[str] = []
        expects_file_work = self._request_expects_file_changes(request.message, mode) or request.apply_changes
        if expects_file_work and not draft.changes:
            findings.append("The draft did not include file changes for a project-work request.")
        if any(change.action == "delete" for change in draft.changes):
            findings.append("The draft includes delete operations and should stay visible in review.")
        if any(not change.summary.strip() for change in draft.changes):
            findings.append("Some generated file changes do not include summaries.")
        duplicate_paths = {
            change.path
            for change in draft.changes
            if sum(1 for candidate in draft.changes if candidate.path == change.path) > 1
        }
        if duplicate_paths:
            findings.append(f"Multiple generated changes target the same path: {', '.join(sorted(duplicate_paths)[:5])}.")
        if draft.warnings:
            findings.append(f"The draft carried {len(draft.warnings)} warning(s).")
        return findings

    def _final_reply(
        self,
        draft_reply: str,
        *,
        applied: list[str],
        validation: CommandRun | None,
        completion_quality: CompletionQualityInfo,
    ) -> str:
        if not applied:
            if validation is not None and self._validation_ok(validation):
                command = validation.command or "validation"
                prefix = f"Auralith Prime ran validation and `{command}` passed."
                return prefix if not draft_reply.strip() else f"{prefix}\n\n{draft_reply}"
            if validation is not None and not self._validation_ok(validation):
                command = validation.command or "validation"
                detail = validation.summary or validation.reason or "Review the captured validation output and continue the repair loop."
                prefix = f"Auralith Prime ran validation and `{command}` still needs repair.\n\n{detail}"
                return prefix if not draft_reply.strip() else f"{prefix}\n\n{draft_reply}"
            return draft_reply

        changed = len(applied)
        noun = "change" if changed == 1 else "changes"
        if validation is not None and self._validation_ok(validation):
            command = validation.command or "validation"
            return (
                f"Auralith Prime applied {changed} file {noun} and validation passed with `{command}`.\n\n"
                f"Completion quality: {completion_quality.status} ({completion_quality.score:.0%})."
            )

        if validation is not None and not self._validation_ok(validation):
            command = validation.command or "validation"
            detail = validation.summary or "Review the captured validation output and continue the repair loop."
            return (
                f"Auralith Prime applied {changed} file {noun}, but `{command}` still needs repair.\n\n"
                f"{detail}"
            )

        return f"Auralith Prime applied {changed} file {noun} to the workspace."

    def _resolve_mode(self, requested: ModeName | None) -> ModeName:
        if requested in {"build", "develop", "review", "chat"}:
            return requested
        configured = self.settings.default_mode.strip().lower()
        if configured in {"build", "develop", "review", "chat"}:
            return configured  # type: ignore[return-value]
        return "build"

    def stream_meta_workspace_root(self, request: AgentRequest) -> str:
        mode = self._resolve_mode(request.mode)
        mission_anchor = self._mission_anchor_from_history(request.history)
        effective_message = self._mission_aware_message(request.message, mission_anchor)
        workspace_root, _ = self._resolve_workspace_for_prompted_request(
            request.workspace_root,
            effective_message,
            mode,
            create=False,
        )
        return str(workspace_root)

    def _merge_model_attempts(
        self,
        planned: list[ModelAttemptInfo],
        executed: list[ModelAttemptInfo],
    ) -> list[ModelAttemptInfo]:
        if not executed:
            return planned

        executed_by_number = {attempt.attempt: attempt for attempt in executed if attempt.attempt > 0}
        merged: list[ModelAttemptInfo] = []
        seen: set[int] = set()
        for attempt in planned:
            replacement = executed_by_number.get(attempt.attempt, attempt)
            merged.append(replacement)
            if replacement.attempt > 0:
                seen.add(replacement.attempt)

        for attempt in executed:
            if attempt.attempt <= 0 or attempt.attempt in seen:
                continue
            merged.append(attempt)
            seen.add(attempt.attempt)
        return merged

    def _engine_label(self, model_execution_plan: ModelExecutionPlan) -> str:
        attempt = next(
            (item for item in model_execution_plan.attempts if item.status == "succeeded"),
            model_execution_plan.primary,
        )
        if attempt is None:
            return f"Aegis Core / {self.model.label}"

        role = attempt.role.strip() or "auto"
        provider = attempt.provider_label.strip() or attempt.provider_id.strip() or self.model.label
        model = attempt.model.strip() or self.settings.aegis_model_name.strip()
        parts = ["Aegis Core", role, provider]
        if model and model.lower() not in provider.lower():
            parts.append(model)
        return " / ".join(parts)

    def _model_reply_is_empty_fallback(self, draft: AgentDraft) -> bool:
        return (
            not draft.changes
            and not draft.proposed_commands
            and draft.reply.strip() == "Aegis did not receive actionable file changes from the model."
        )

    def _sanitize_model_change_paths(self, draft: AgentDraft, workspace_root: Path) -> AgentDraft:
        return sanitize_model_change_paths(draft, workspace_root)

    def _fallback_mode_for_request(self, message: str, mode: ModeName) -> ModeName:
        return mode if self._request_expects_file_changes(message, mode) else "chat"

    def _planner_message_with_instruction_files(
        self,
        message: str,
        instruction_files: list[WorkspaceInstructionFile],
    ) -> str:
        if not self._broad_continue_should_follow_instruction_files(message, instruction_files):
            return message

        open_items: list[str] = []
        for item in instruction_files[:5]:
            for pending in item.pending_items[:6]:
                if pending and pending not in open_items:
                    open_items.append(pending)
            if len(open_items) >= 12:
                break

        if not open_items:
            for item in instruction_files[:3]:
                excerpt = item.excerpt.strip().replace("\n", " ")
                if excerpt:
                    open_items.append(excerpt[:220])

        todo_context = "; ".join(open_items[:12]) or "open project instruction file items"
        return (
            f"{message}\n\n"
            "Autopilot continuation context: implement and validate the open project instruction file tasks. "
            f"Open tasks: {todo_context}. "
            "When an open checkbox item is truly completed, update the instruction/TODO file in the same pass by changing only that item from [ ] to [x]."
        )

    def _planner_message_with_workspace_readiness(
        self,
        message: str,
        workspace_root: Path,
        instruction_files: list[WorkspaceInstructionFile],
    ) -> str:
        planner_message = self._planner_message_with_instruction_files(message, instruction_files)
        readiness = self._workspace_readiness_for_broad_continue(message, workspace_root)
        if readiness is None:
            return planner_message

        context_lines = [
            f"{planner_message}\n",
            "Workspace readiness continuation context: Treat this saved readiness next action as the active objective for this turn.",
            f"Readiness status: {readiness.status} ({readiness.score}/100).",
        ]
        if readiness.summary:
            context_lines.append(f"Readiness summary: {readiness.summary}.")
        if readiness.next_action:
            context_lines.append(f"Readiness next action: {readiness.next_action}.")
        repair_brief = self._workspace_repair_brief(workspace_root, readiness=readiness)
        if repair_brief:
            context_lines.append(f"Repair brief: {repair_brief}")
        if readiness.blockers:
            context_lines.append(f"Known blockers: {'; '.join(readiness.blockers[:4])}.")
        if readiness.signals:
            context_lines.append(f"Useful signals: {'; '.join(readiness.signals[:4])}.")
        context_lines.append(
            "Continue from the existing workspace state; do not create unrelated starter files or switch stacks unless the readiness action explicitly says to."
        )
        return "\n".join(line for line in context_lines if line.strip())

    def _instruction_files_have_open_autopilot_work(
        self,
        instruction_files: list[WorkspaceInstructionFile],
    ) -> bool:
        for item in instruction_files[:5]:
            if item.pending_count > 0:
                return True
            if item.total_items > 0:
                continue
            if item.score >= 0.42 and item.excerpt.strip():
                return True
        return False

    def _broad_continue_should_follow_instruction_files(
        self,
        message: str,
        instruction_files: list[WorkspaceInstructionFile],
    ) -> bool:
        if not instruction_files:
            return False
        if not self._instruction_files_have_open_autopilot_work(instruction_files):
            return False
        return self._looks_like_broad_project_continuation(message)

    def _broad_continue_should_follow_workspace_readiness(
        self,
        message: str,
        workspace_root: Path,
    ) -> bool:
        return self._workspace_readiness_for_broad_continue(message, workspace_root) is not None

    def _workspace_readiness_for_broad_continue(
        self,
        message: str,
        workspace_root: Path,
    ) -> WorkspaceReadinessInfo | None:
        if not self._looks_like_broad_project_continuation(message):
            return None
        readiness = self.workspace_readiness_for_workspace(workspace_root)
        if readiness.status not in {"needs_work", "needs_validation", "needs_repair"}:
            return None
        if not readiness.next_action.strip():
            return None
        return readiness

    def _workspace_repair_brief(self, workspace_root: Path, *, readiness: WorkspaceReadinessInfo | None = None) -> str:
        readiness = readiness or self.workspace_readiness_for_workspace(workspace_root)
        if readiness.status != "needs_repair":
            return ""

        history = self.command_history_snapshot(workspace_root)
        validation_plan = self.validation_plan_snapshot(workspace_root)
        instruction_status = self.instruction_status_snapshot(workspace_root)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        manifest = self.workspace.load_project_manifest(workspace_root)
        validation_command = (
            validation_plan.validation_command
            or (manifest.validation_command if manifest else "")
            or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
            or workspace_remembered_validation_command(history)
        )

        latest_history_validation = self._latest_history_validation(history)
        plan_last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
        instruction_last_validation = (
            instruction_status.last_validation if isinstance(instruction_status.last_validation, dict) else {}
        )
        payload = latest_history_validation or plan_last_run or instruction_last_validation
        if not payload:
            return ""
        return self._compact_repair_brief_from_validation(payload, validation_command=validation_command)

    def _latest_history_validation(self, command_history: dict[str, Any]) -> dict[str, Any]:
        return workspace_latest_history_validation(command_history)

    def _compact_repair_brief_from_validation(self, payload: dict[str, Any], *, validation_command: str = "") -> str:
        return workspace_compact_validation_repair_brief(payload, validation_command=validation_command)

    def _looks_like_broad_project_continuation(self, message: str) -> bool:
        normalized = " ".join(message.strip().lower().split())
        if not normalized:
            return False

        continuation_phrases = (
            "continue",
            "continue working",
            "continue building",
            "continue testing",
            "continue with your suggestions",
            "go ahead",
            "keep going",
            "next",
            "next pass",
            "finish",
            "finish it",
            "finish the project",
            "complete it",
            "complete the project",
            "autopilot",
            "run autopilot",
            "build it",
            "build this",
            "build the project",
            "run it",
            "run this",
            "run the app",
            "run the project",
            "run validation",
            "run the build",
            "validate it",
            "validate this",
            "test it",
            "test this",
            "compile it",
            "compile this",
            "you didn't build",
            "you didnt build",
            "didn't build",
            "didnt build",
            "not built",
            "fix the build",
            "repair the build",
        )
        if not any(phrase in normalized for phrase in continuation_phrases):
            return False

        specific_new_request_markers = (
            " at this path ",
            " at this location ",
            " create a ",
            " create an ",
            " create me ",
            " build a ",
            " build an ",
            " make a ",
            " make an ",
            " write a ",
            " write an ",
            " generate a ",
            " generate an ",
            " convert ",
            " split ",
            " separate ",
        )
        padded = f" {normalized} "
        if any(marker in padded for marker in specific_new_request_markers):
            return False
        if len(normalized.split()) <= 12:
            return True

        broad_continuation_markers = (
            "bug hunting",
            "continue working",
            "continue testing",
            "continue with",
            "finish up",
            "go all out",
            "improve",
            "improving",
            "keep going",
            "next best",
            "suggestions",
            "stress test",
            "stress testing",
            "testing to ensure",
        )
        return any(marker in normalized for marker in broad_continuation_markers)

    def _effective_request_message(self, message: str, mode: ModeName, task_plan: TaskPlan) -> str:
        if self._request_expects_file_changes(message, mode):
            return message
        if task_plan.intent not in {"implementation", "debug_and_repair"}:
            return message

        parts = [message, task_plan.objective, " ".join(task_plan.steps[:8])]
        route_profile = task_plan.route_profile if isinstance(task_plan.route_profile, dict) else {}
        profile_label = str(route_profile.get("label") or route_profile.get("id") or "").strip()
        if profile_label:
            parts.append(profile_label)
        return "\n".join(part for part in parts if part.strip())

    def _harden_native_cpp_draft(
        self,
        draft: AgentDraft,
        message: str,
        workspace_root: Path,
    ) -> AgentDraft:
        return native_harden_cpp_draft(
            draft,
            request_mentions_cpp_project=self._request_mentions_cpp_project(message),
            workspace_root=workspace_root,
            change_paths=self._change_paths(draft),
        )

    def _drop_shell_only_cpp_validation_changes(self, draft: AgentDraft) -> list[str]:
        return native_drop_shell_only_cpp_validation_changes(draft)

    def _prefer_python_build_command(self, draft: AgentDraft) -> None:
        native_prefer_python_build_command(draft)

    def _existing_project_no_change_continuation_draft(
        self,
        *,
        original_draft: AgentDraft,
        fallback: AgentDraft,
        message: str,
        mode: ModeName,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> AgentDraft | None:
        if mode == "chat" and not self._request_expects_file_changes(message, mode):
            return None
        if not self._workspace_has_existing_project_surface(workspace_files, project_manifest):
            return None

        stack_family = self._workspace_stack_family(workspace_files)
        project_label = "existing project"
        if project_manifest is not None:
            project_label = project_manifest.title or project_manifest.project_name or project_label
            stack_family = stack_family or str(project_manifest.mission_contract.get("stack_family") or "").strip()
        if not stack_family:
            stack_family = "detected workspace"

        warnings = [
            *original_draft.warnings,
            *fallback.warnings,
            (
                "The model returned no file changes for an existing-project implementation request; "
                "Aegis preserved the workspace and prepared a strict existing-project continuation pass."
            ),
        ]
        proposed_commands: list[dict[str, str]] = []
        validation_command = self._existing_project_continuation_validation_command(
            workspace_root,
            workspace_files,
            project_manifest,
        )
        if validation_command:
            proposed_commands.append(
                {
                    "command": validation_command,
                    "reason": "Validate the preserved existing workspace before the next additive patch.",
                }
            )

        plan = [
            f"Keep working inside the current {project_label} without switching stacks.",
            f"Preserve the detected stack family: {stack_family}.",
            "Inspect existing source, project, and build files before generating the next patch.",
            "Use update actions for existing files and create actions only for genuinely new support files.",
            "Avoid starter templates, unrelated website files, and language/framework changes unless the user explicitly asks to convert the project.",
        ]
        if validation_command:
            plan.append(f"Run validation with `{validation_command}` and repair the first captured error.")
        else:
            plan.append("Infer or add a stack-native validation command before final handoff.")

        return AgentDraft(
            reply=(
                "Aegis preserved the existing project stack and queued a strict existing-project continuation pass. "
                "The next pass should update the real source/build files directly instead of creating a starter."
            ),
            plan=plan,
            changes=[],
            warnings=warnings,
            proposed_commands=proposed_commands,
        )

    def _existing_project_continuation_validation_command(
        self,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> str:
        if project_manifest is not None and project_manifest.validation_command:
            return project_manifest.validation_command.strip()

        paths = {item.path.replace("\\", "/").lower().strip("/") for item in workspace_files}
        if "build.py" in paths or (workspace_root / "build.py").exists():
            return "python build.py"
        if "build.ps1" in paths or (workspace_root / "build.ps1").exists():
            return self.validation.POWERSHELL_BUILD_COMMAND
        if "package.json" in paths or (workspace_root / "package.json").exists():
            return "npm run build"
        if "pyproject.toml" in paths or "pytest.ini" in paths or (workspace_root / "pyproject.toml").exists():
            return "python -m pytest"
        if "cargo.toml" in paths or (workspace_root / "Cargo.toml").exists():
            return "cargo test"
        if "go.mod" in paths or (workspace_root / "go.mod").exists():
            return "go test ./..."
        if "cmakelists.txt" in paths or (workspace_root / "CMakeLists.txt").exists():
            return "cmake -S . -B build && cmake --build build --config Release"

        solution = next((item.path for item in workspace_files if item.path.lower().endswith(".sln")), "")
        if not solution:
            try:
                solution_path = next(workspace_root.glob("*.sln"), None)
            except OSError:
                solution_path = None
            if solution_path is not None:
                solution = solution_path.name
        if solution:
            return f'msbuild "{Path(solution).name}" /m /p:Configuration=Release'
        return ""

    def _cmake_build_py_content(self) -> str:
        return native_cmake_build_py_content()

    def _workspace_has_any(self, workspace_root: Path, relative_paths: tuple[str, ...]) -> bool:
        return any((workspace_root / relative_path).exists() for relative_path in relative_paths)

    _WINDOWS_PATH_STOP_PHRASES: tuple[str, ...] = (
        " here ",
        " i want",
        " i need",
        " i'm ",
        " im ",
        " can you",
        " could you",
        " please",
        " at this path",
        " at this location",
        " in this folder",
        " in this directory",
        " and then ",
        " then ",
        " so ",
        " but ",
        " because ",
        " with ",
        " using ",
        " for me",
        " if ",
        " launch ",
        " execute ",
        " run ",
        " validate ",
        " verify ",
        " check ",
        " ensure ",
        " test ",
        " compile ",
        " create ",
        " build ",
        " make ",
        " complete ",
        " finish ",
        " develop ",
        " ship ",
        " generate ",
        " scaffold ",
        " set up ",
        " setup ",
        " start ",
        " write ",
        " add ",
        " implement ",
        " update ",
        " modify ",
        " work on ",
    )

    _PROMPT_WORKSPACE_MARKERS: tuple[str, ...] = (
        " at this path ",
        " at this location ",
        " at this folder ",
        " in this folder ",
        " in this directory ",
        " in this path ",
        " at the path ",
        " in the folder ",
        " in the directory ",
        " work on ",
        " work inside ",
        " inside ",
        " under ",
    )

    def _resolve_workspace_for_prompted_request(
        self,
        requested_root: str | None,
        message: str,
        mode: ModeName,
        *,
        create: bool,
    ) -> tuple[Path, bool]:
        workspace_root = self.workspace.resolve_workspace(requested_root, create=create)
        prompt_root = self._explicit_prompt_workspace(message)
        if not prompt_root:
            return workspace_root, False
        if not self._should_use_prompt_workspace(message, mode):
            return workspace_root, False

        prompt_workspace = self.workspace.resolve_workspace(prompt_root, migrate_legacy=False, create=create)
        return prompt_workspace, prompt_workspace != workspace_root

    def _explicit_prompt_workspace(self, message: str) -> str:
        fragments = self._windows_path_fragments(message)
        return fragments[0] if fragments else ""

    def _should_use_prompt_workspace(self, message: str, mode: ModeName) -> bool:
        normalized = f" {' '.join(message.lower().split())} "
        if self._request_expects_file_changes(message, mode) or self._request_asks_for_validation(message):
            return True
        if mode in {"build", "develop"} and any(marker in normalized for marker in self._PROMPT_WORKSPACE_MARKERS):
            return True
        return False

    def _message_without_explicit_paths(self, message: str) -> str:
        return request_message_without_explicit_paths(message, self._clean_windows_path_fragment)

    def _windows_path_fragments(self, message: str) -> list[str]:
        return request_windows_path_fragments(message, self._clean_windows_path_fragment)

    def _clean_windows_path_fragment(self, value: str) -> str:
        from .project_scaffolder import ProjectScaffolder

        return ProjectScaffolder._clean_windows_path_fragment(value)

    def _request_needs_project_shape(self, message: str, mode: ModeName) -> bool:
        return request_needs_project_shape(
            self._message_without_explicit_paths(message),
            expects_file_changes=self._request_expects_file_changes(message, mode),
        )

    def _change_paths(self, draft: AgentDraft) -> set[str]:
        return runtime_draft_change_paths(draft)

    def _change_payload_size(self, draft: AgentDraft) -> int:
        return runtime_draft_change_payload_size(draft)

    def _draft_has_concrete_source_surface(self, draft: AgentDraft) -> bool:
        return runtime_draft_has_concrete_source_surface(draft)

    def _manifest_contract_value(self, manifest: WorkspaceProjectManifest, key: str) -> str:
        return runtime_manifest_contract_value(manifest, key)

    def _manifest_stack_family(self, manifest: WorkspaceProjectManifest | None) -> str:
        return runtime_manifest_stack_family(manifest)

    def _draft_stack_families(self, draft: AgentDraft) -> set[str]:
        return runtime_draft_stack_families(draft)

    def _workspace_stack_family(self, files: list[WorkspaceFile]) -> str:
        return runtime_workspace_stack_family(files)

    def _family_label(self, family: str) -> str:
        return runtime_stack_family_label(family)

    def _prompt_allows_manifest_stack_switch(self, message: str) -> bool:
        lower = self._message_without_explicit_paths(message).lower()
        switch_terms = (
            "convert",
            "migrate",
            "rewrite as",
            "turn this into",
            "turn it into",
            "replace the stack",
            "change the stack",
            "switch to",
            "port to",
            "move this to",
            "make this a website instead",
            "make this a web app instead",
        )
        return any(term in lower for term in switch_terms)

    def _prompt_explicitly_allows_destructive_changes(self, message: str) -> bool:
        lower = self._message_without_explicit_paths(message).lower()
        destructive_terms = (
            "delete",
            "remove",
            "drop",
            "prune",
            "purge",
            "wipe",
            "erase",
            "clear out",
            "overwrite",
            "reset",
            "replace",
            "recreate",
            "rewrite from scratch",
            "rebuild from scratch",
            "rename",
            "move",
            "split out",
            "extract",
            "merge projects",
            "merge the projects",
            "combine projects",
            "consolidate",
        )
        return any(term in lower for term in destructive_terms)

    def _important_project_path(self, path: str) -> bool:
        return runtime_important_project_path(path)

    def _draft_destructive_change_reasons(
        self,
        draft: AgentDraft,
        message: str,
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> list[str]:
        if not draft.changes:
            return []

        explicit_permission = self._prompt_explicitly_allows_destructive_changes(message)
        project_label = "the active workspace"
        if project_manifest is not None:
            project_label = project_manifest.title or project_manifest.project_name or project_label

        reasons: list[str] = []
        for change in draft.changes:
            path = change.path.replace("\\", "/").strip("/")
            if not path:
                continue
            normalized = path.lower()
            important = self._important_project_path(path)

            if change.action == "delete" and not explicit_permission:
                if important:
                    reasons.append(
                        f"The draft deletes important project file '{path}' from {project_label} without an explicit delete/remove instruction."
                    )
                else:
                    reasons.append(
                        f"The draft deletes '{path}' without an explicit delete/remove instruction."
                    )
                continue

            if (
                change.action == "update"
                and important
                and not explicit_permission
                and (change.content is None or not change.content.strip())
            ):
                reasons.append(
                    f"The draft would empty important project file '{path}' without an explicit rewrite/reset instruction."
                )

        return reasons

    def _draft_existing_file_overwrite_reasons(
        self,
        draft: AgentDraft,
        message: str,
        files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> list[str]:
        if not draft.changes or not files:
            return []
        if self._prompt_explicitly_allows_destructive_changes(
            message
        ) or self._prompt_allows_fresh_scaffold_in_existing_project(message):
            return []

        existing_paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        if not existing_paths:
            return []

        project_label = "the active workspace"
        if project_manifest is not None:
            project_label = project_manifest.title or project_manifest.project_name or project_label

        reasons: list[str] = []
        for change in draft.changes:
            path = change.path.replace("\\", "/").strip("/")
            if not path or change.action != "create":
                continue
            if path.lower() not in existing_paths or not self._important_project_path(path):
                continue
            reasons.append(
                f"The draft uses create on existing important file '{path}' in {project_label}; use update for continuation work or ask explicitly before replacing existing files."
            )

        return reasons

    def _workspace_has_existing_project_surface(
        self,
        files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> bool:
        if project_manifest is not None:
            return True
        paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        if not paths:
            return False
        project_markers = {
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "cargo.toml",
            "go.mod",
            "cmakelists.txt",
            "makefile",
            "build.py",
            "build.ps1",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.mjs",
            "next.config.js",
            "next.config.ts",
        }
        if paths.intersection(project_markers):
            return True
        if any(path.endswith((".sln", ".vcxproj", ".csproj", ".fsproj", ".vbproj", ".psm1", ".psd1")) for path in paths):
            return True
        source_prefixes = ("src/", "app/", "pages/", "components/", "driver/", "controller/", "host/", "library/")
        source_count = sum(1 for path in paths if path.startswith(source_prefixes))
        return source_count >= 2

    def _prompt_allows_fresh_scaffold_in_existing_project(self, message: str) -> bool:
        lower = self._message_without_explicit_paths(message).lower()
        fresh_terms = (
            "new project",
            "new app",
            "fresh project",
            "fresh app",
            "starter",
            "scaffold",
            "from scratch",
            "start over",
            "rebuild from scratch",
            "rewrite from scratch",
            "replace the project",
            "replace everything",
            "reset the project",
            "convert",
            "migrate",
            "switch to",
        )
        return any(term in lower for term in fresh_terms)

    def _starter_scaffold_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lower().strip("/")
        starter_exact = {
            ".gitignore",
            "readme.md",
            "package.json",
            "index.html",
            "styles.css",
            "style.css",
            "app.js",
            "script.js",
            "main.py",
            "pyproject.toml",
            "requirements.txt",
            "cargo.toml",
            "go.mod",
            "cmakelists.txt",
            "build.py",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.mjs",
            "next.config.js",
            "next.config.ts",
        }
        if normalized in starter_exact:
            return True
        starter_suffixes = (
            "/main.cpp",
            "/main.c",
            "/main.cxx",
            "/main.rs",
            "/main.go",
            "/main.py",
            "/app.py",
            "/app.tsx",
            "/app.jsx",
            "/index.tsx",
            "/index.jsx",
            "/index.html",
            "/globals.css",
            "/styles.css",
        )
        return normalized.endswith(starter_suffixes) or normalized == "app/page.tsx"

    def _draft_existing_project_scaffold_drift_reasons(
        self,
        draft: AgentDraft,
        message: str,
        files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> list[str]:
        if not draft.changes:
            return []
        if not self._workspace_has_existing_project_surface(files, project_manifest):
            return []
        if self._prompt_allows_fresh_scaffold_in_existing_project(message):
            return []

        lower = self._message_without_explicit_paths(message).lower()
        broad_continuation = self._looks_like_broad_project_continuation(message) or any(
            term in lower
            for term in (
                "continue",
                "keep going",
                "work on",
                "improve",
                "improving",
                "fix",
                "fixing",
                "debug",
                "repair",
                "build it",
                "run it",
                "you didn't build",
                "validate",
            )
        )
        if not broad_continuation and project_manifest is None:
            return []

        existing_paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        create_changes = [change for change in draft.changes if change.action == "create"]
        starter_creates = [
            change.path.replace("\\", "/").strip("/")
            for change in create_changes
            if self._starter_scaffold_path(change.path)
        ]
        overwritten_starter_creates = [
            path
            for path in starter_creates
            if path.lower() in existing_paths or self._important_project_path(path)
        ]
        updates_existing_source = any(
            change.action == "update"
            and change.path.replace("\\", "/").lower().strip("/") in existing_paths
            and self._important_project_path(change.path)
            and bool((change.content or "").strip())
            for change in draft.changes
        )

        reasons: list[str] = []
        if len(starter_creates) >= 3 and not updates_existing_source:
            preview = ", ".join(starter_creates[:5])
            reasons.append(
                "The draft looks like a fresh starter scaffold for an existing project instead of a continuation patch"
                f" ({preview})."
            )
        elif len(overwritten_starter_creates) >= 2 and not updates_existing_source:
            preview = ", ".join(overwritten_starter_creates[:4])
            reasons.append(
                "The draft would recreate core starter files in an existing project without updating the existing implementation"
                f" ({preview})."
            )

        return reasons

    def _draft_manifest_contract_mismatch_reasons(
        self,
        draft: AgentDraft,
        message: str,
        project_manifest: WorkspaceProjectManifest | None,
    ) -> list[str]:
        if project_manifest is None or not draft.changes:
            return []
        target_family = self._manifest_stack_family(project_manifest)
        if not target_family or self._prompt_allows_manifest_stack_switch(message):
            return []
        families = self._draft_stack_families(draft)
        if not families or target_family in families:
            return []

        project_label = project_manifest.title or project_manifest.project_name or "the active workspace"
        family_label = self._family_label(target_family)
        drafted = ", ".join(sorted(families))
        return [
            f"The draft changes look like {drafted} files, but {project_label} is locked to a {family_label} mission contract."
        ]

    def _looks_like_next_workspace(self, files: list[WorkspaceFile]) -> bool:
        return runtime_looks_like_next_workspace(files)

    def _request_mentions_cpp_project(self, message: str) -> bool:
        return request_mentions_cpp_project(self._message_without_explicit_paths(message))

    def _request_mentions_extension_project(self, message: str) -> bool:
        return request_mentions_extension_project(self._message_without_explicit_paths(message))

    def _request_mentions_python_app_project(self, message: str) -> bool:
        return request_mentions_python_app_project(self._message_without_explicit_paths(message))

    def _request_mentions_web_project(self, message: str) -> bool:
        without_paths = self._message_without_explicit_paths(message)
        return request_mentions_web_project(
            without_paths,
            web_stack_negated=self._prompt_negates_web_stack(without_paths),
        )

    def _request_mentions_desktop_project(self, message: str) -> bool:
        return request_mentions_desktop_project(self._message_without_explicit_paths(message))

    def _prompt_negates_web_stack(self, message: str) -> bool:
        from .project_scaffolder import ProjectScaffolder

        return ProjectScaffolder._prompt_negates_web_stack(self._message_without_explicit_paths(message))

    def _request_mentions_specific_web_framework(self, message: str) -> bool:
        return request_mentions_specific_web_framework(self._message_without_explicit_paths(message))

    def _draft_is_static_site_shape(self, draft: AgentDraft) -> bool:
        paths = self._change_paths(draft)
        has_html = "index.html" in paths
        has_style = any(path in paths for path in ("styles.css", "style.css", "app.css"))
        has_script = any(path in paths for path in ("app.js", "script.js", "main.js"))
        has_validator = "build.js" in paths
        return has_html and has_style and has_script and has_validator

    def _draft_stack_mismatch_reasons(self, draft: AgentDraft, message: str) -> list[str]:
        paths = self._change_paths(draft)
        lower = self._message_without_explicit_paths(message).lower()

        def any_path(predicate: Callable[[str], bool]) -> bool:
            return any(predicate(path) for path in paths)

        web_indicators = {
            "package.json",
            "index.html",
            "styles.css",
            "style.css",
            "app.css",
            "app.js",
            "script.js",
            "next.config.js",
            "next.config.mjs",
            "next.config.ts",
            "vite.config.js",
            "vite.config.ts",
            "vite.config.mjs",
            "tailwind.config.js",
            "tailwind.config.ts",
        }
        has_web = any(path in web_indicators for path in paths) or any_path(
            lambda path: path.startswith(("app/", "pages/", "components/", "public/"))
            or path.endswith((".tsx", ".jsx", ".html", ".css"))
        )
        has_native_source = any_path(lambda path: path.endswith((".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".asm", ".rc")))
        has_native_build = any_path(
            lambda path: path in {"cmakelists.txt", "build.py", "build.ps1"}
            or path.endswith((".sln", ".vcxproj", ".vcxproj.filters"))
        )
        has_python = any_path(lambda path: path.endswith(".py") or path in {"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"})
        has_dotnet = any_path(lambda path: path.endswith(RUNTIME_DOTNET_SUFFIXES) or path.endswith(".sln"))
        has_rust = any_path(lambda path: path == "cargo.toml" or path.endswith(".rs"))
        has_go = any_path(lambda path: path == "go.mod" or path.endswith(".go"))

        reasons: list[str] = []
        if self._request_mentions_cpp_project(message):
            if has_web and not (has_native_source and has_native_build):
                reasons.append("The draft looks like a web stack, but the prompt requested a native C++/Visual Studio/CMake project.")
            if any(term in lower for term in ("driver", "kernel")):
                has_driver_source = any_path(lambda path: path.startswith("driver/") and path.endswith((".c", ".cpp", ".h", ".inf", ".vcxproj")))
                has_controller_source = any_path(lambda path: path.startswith("controller/") and path.endswith((".cpp", ".h", ".vcxproj")))
                if not (has_driver_source and has_controller_source):
                    reasons.append("The draft does not contain both driver and controller project surfaces requested by the prompt.")
            if any(term in lower for term in ("dll", "shared library", "dynamic library", "plugin library")):
                has_library_source = any_path(lambda path: "library" in path and path.endswith((".cpp", ".h", ".hpp")))
                has_host_loader = any_path(lambda path: path.startswith("host/") and path.endswith((".cpp", ".h", ".hpp")))
                if not (has_library_source and has_host_loader):
                    reasons.append("The draft does not include both the shared-library implementation and host-loader validation surface.")
            if any(term in lower for term in ("press enter", "user input", "wait for input", "pause before closing")):
                cpp_text = "\n".join(
                    (change.content or "").lower()
                    for change in draft.changes
                    if change.action in {"create", "update"} and change.path.replace("\\", "/").lower().endswith((".cpp", ".cxx", ".cc"))
                )
                if cpp_text and not any(token in cpp_text for token in ("std::cin", "cin.get", "getchar", "system(\"pause\")", "system('pause')")):
                    reasons.append("The C++ entry point does not wait for user input even though the prompt requested it.")

        if self._request_mentions_web_project(message):
            has_web_entry = has_web and any_path(lambda path: path.endswith((".html", ".tsx", ".jsx", ".css", ".js", ".ts")) or path in web_indicators)
            if (has_native_source or has_native_build) and not has_web_entry:
                reasons.append("The draft looks like a native project, but the prompt requested a website or web app.")

        if self._request_mentions_desktop_project(message):
            if has_web and not self._draft_has_desktop_host_surface(draft):
                reasons.append("The draft looks like a website/static frontend, but the prompt requested a packaged desktop or GUI application.")

        if self._request_mentions_python_app_project(message):
            if has_web and not has_python:
                reasons.append("The draft looks like a web stack, but the prompt requested a Python app/tool/script project.")

        if "rust" in lower and (has_web or has_native_source) and not has_rust:
            reasons.append("The draft does not contain Rust project files requested by the prompt.")
        if ("golang" in lower or re.search(r"\bgo\b", lower)) and (has_web or has_native_source) and not has_go:
            reasons.append("The draft does not contain Go project files requested by the prompt.")
        if any(term in lower for term in ("c#", "csharp", "f#", "fsharp", "visual basic", "vb.net", "dotnet", ".net", "wpf")) and (has_web or has_native_source) and not has_dotnet:
            reasons.append("The draft does not contain .NET project files requested by the prompt.")

        return reasons

    def _draft_has_desktop_host_surface(self, draft: AgentDraft) -> bool:
        return runtime_draft_has_desktop_host_surface(draft)

    def _draft_task_adherence_reasons(
        self,
        draft: AgentDraft,
        message: str,
        files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> list[str]:
        if not draft.changes:
            return []

        reasons: list[str] = []
        families = self._draft_stack_families(draft)
        if self._prompt_negates_web_stack(message) and "web" in families:
            web_paths = [
                path
                for path in sorted(self._change_paths(draft))
                if path in {"package.json", "index.html"}
                or path.startswith(("app/", "pages/", "components/", "public/"))
                or path.endswith((".tsx", ".jsx", ".html", ".css"))
            ]
            preview = ", ".join(web_paths[:5]) or "web-stack files"
            reasons.append(
                "The latest request explicitly said not to make a website/web app, but the draft introduced web-stack files"
                f" ({preview})."
            )

        target_family = self._manifest_stack_family(project_manifest) or self._workspace_stack_family(files)
        if (
            target_family
            and families
            and target_family not in families
            and not self._prompt_allows_manifest_stack_switch(message)
        ):
            broad_existing_work = (
                project_manifest is not None
                or self._workspace_has_existing_project_surface(files, project_manifest)
                or self._looks_like_broad_project_continuation(message)
                or any(term in self._message_without_explicit_paths(message).lower() for term in ("existing", "continue", "refine", "improve", "fix", "debug"))
            )
            if broad_existing_work:
                drafted = ", ".join(sorted(families))
                reasons.append(
                    f"The draft changed {drafted} files, but the active workspace/request is anchored to {self._family_label(target_family)}."
                )

        deduped: list[str] = []
        for reason in reasons:
            if reason not in deduped:
                deduped.append(reason)
        return deduped

    def _draft_is_weak_project_shape(
        self,
        draft: AgentDraft,
        message: str,
        mode: ModeName,
        files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
    ) -> bool:
        if not self._request_needs_project_shape(message, mode):
            return False
        material_changes = [change for change in draft.changes if change.action in {"create", "update"}]
        if len(material_changes) < 3:
            return True

        paths = self._change_paths(draft)
        payload_size = self._change_payload_size(draft)

        if not self._draft_has_concrete_source_surface(draft):
            return True

        if self._draft_manifest_contract_mismatch_reasons(draft, message, project_manifest):
            return True

        if self._draft_stack_mismatch_reasons(draft, message):
            return True

        explicit_project_weakness = self._explicit_project_shape_weakness(draft, message, payload_size)
        if explicit_project_weakness is not None:
            return explicit_project_weakness

        if self._request_mentions_cpp_project(message):
            has_entry = any(path.endswith("main.cpp") or path.endswith("main.cxx") for path in paths)
            has_build_file = any(path == "cmakelists.txt" or path.endswith(".sln") or path.endswith(".vcxproj") for path in paths)
            return not (has_entry and has_build_file)

        if self._request_mentions_extension_project(message):
            if any(term in self._message_without_explicit_paths(message).lower() for term in ("vscode", "vs code", "visual studio code")):
                has_extension_entry = "extension.js" in paths
                has_manifest = "package.json" in paths
                has_validator = "build.py" in paths
                return not (has_extension_entry and has_manifest and has_validator) or payload_size < 900
            has_manifest = "manifest.json" in paths
            has_background = "src/background.js" in paths
            has_popup = "popup/popup.html" in paths
            has_content = "src/content.js" in paths
            has_validator = "build.py" in paths
            return not (has_manifest and has_background and has_popup and has_content and has_validator) or payload_size < 1200

        if self._request_mentions_python_app_project(message):
            has_entry = any(path.startswith("src/") and path.endswith(".py") for path in paths) or "main.py" in paths
            has_build_runner = "build.py" in paths
            has_package_metadata = any(path in paths for path in ("pyproject.toml", "setup.py", "setup.cfg"))
            has_smoke_test = any(path.startswith("tests/") and path.endswith(".py") for path in paths)
            return not (has_entry and has_build_runner and has_package_metadata and has_smoke_test) or payload_size < 900

        existing_next = self._looks_like_next_workspace(files)
        next_visual_paths = (
            "app/page.tsx",
            "app/layout.tsx",
            "app/globals.css",
        )
        has_next_visual_change = any(path in paths for path in next_visual_paths) or any(
            path.startswith("components/") for path in paths
        )
        if existing_next:
            static_only = paths.issubset({"index.html", "styles.css", "style.css", "app.css", "app.js", "script.js", "README.md".lower()})
            if static_only or not has_next_visual_change:
                return True
            return payload_size < 1200

        if self._request_mentions_web_project(message):
            package_dependent_paths = {
                "package.json",
                "next.config.js",
                "next.config.mjs",
                "next.config.ts",
                "vite.config.js",
                "vite.config.ts",
                "tsconfig.json",
            }
            if (
                not self._request_mentions_specific_web_framework(message)
                and any(path in paths for path in package_dependent_paths)
                and not self._draft_is_static_site_shape(draft)
            ):
                return True
            has_markup = any(path.endswith((".html", ".tsx", ".jsx")) for path in paths)
            has_style = any(path.endswith(".css") or "tailwind.config" in path for path in paths)
            has_script_or_component = any(
                path.endswith((".js", ".ts", ".tsx", ".jsx")) or path.startswith("components/") for path in paths
            )
            return not (has_markup and has_style and has_script_or_component) or payload_size < 1200

        return payload_size < 900

    def _explicit_project_shape_weakness(
        self,
        draft: AgentDraft,
        message: str,
        payload_size: int,
    ) -> bool | None:
        lower = self._message_without_explicit_paths(message).lower()
        preset_id = self.fallback._explicit_project_preset(lower)
        if not preset_id:
            return None

        paths = self._change_paths(draft)

        def has(path: str) -> bool:
            return path.lower() in paths

        def any_path(predicate: Callable[[str], bool]) -> bool:
            return any(predicate(path) for path in paths)

        required_by_preset: dict[str, tuple[tuple[str, ...], int]] = {
            "nextjs-ts-tailwind": (("package.json",), 1200),
            "vite-react-ts": (("package.json", "vite.config.ts", "src/main.tsx", "src/app.tsx", "src/styles.css"), 1200),
            "browser-extension-mv3": (("manifest.json", "src/background.js", "src/content.js", "popup/popup.html", "build.py"), 1200),
            "vscode-extension-js": (("package.json", "extension.js", "build.py", ".vscode/launch.json"), 900),
            "electron-react-ts": (
                ("package.json", "electron.vite.config.ts", "src/main/index.ts", "src/preload/index.ts", "src/renderer/src/app.tsx"),
                1200,
            ),
            "expo-react-native-ts": (("package.json", "app.json", "app.tsx", "src/screens/homescreen.tsx"), 1000),
            "tauri-react-ts": (("package.json", "src-tauri/cargo.toml", "src-tauri/src/main.rs", "src/app.tsx"), 1200),
            "fastapi-python-api": (("pyproject.toml", "tests/test_health.py"), 900),
            "django-python-web": (("requirements.txt", "manage.py"), 900),
            "express-ts-api": (("package.json", "tsconfig.json", "src/server.ts"), 900),
            "node-http-api-js": (("package.json", "src/server.js", "build.js"), 900),
            "node-fullstack-js": (("package.json", "src/server.js", "public/index.html", "build.js"), 1100),
            "node-cli-js": (("package.json", "bin/cli.js", "src/commands.js", "build.js"), 800),
            "powershell-module": (("build.ps1",), 800),
            "sqlite-python-db": (("build.py",), 900),
            "rust-cli": (("cargo.toml", "src/main.rs", "src/lib.rs"), 600),
            "go-http-api": (("go.mod", "cmd/server/main.go", "internal/api/router.go"), 700),
            "dotnet-console-csharp": (("build.py",), 900),
            "dotnet-webapi-csharp": ((), 900),
            "dotnet-wpf-csharp": (("build.py",), 900),
            "cpp-windows-service": (("cmakelists.txt", "src/service_main.cpp", "build.py"), 900),
            "cpp-cmake-dll": (("cmakelists.txt", "src/library.cpp", "tests/smoke.cpp", "build.py"), 900),
            "cpp-imgui-win32-dx11": (("cmakelists.txt", "src/main.cpp", "src/app_state.cpp", "vendor/imgui_shim/imgui.h", "build.py"), 900),
            "cpp-game-loop-cmake": (("cmakelists.txt", "src/main.cpp", "src/engine.cpp", "tests/smoke.cpp", "build.py"), 900),
            "python-game-file-analyzer": (("build.py", "tests/test_analyzer.py"), 900),
            "cpp-windows-internals-hooking": (
                ("cmakelists.txt", "src/main.cpp", "src/instrumentation.cpp", "build.py"),
                900,
            ),
            "python-sln-refactor-tool": (("build.py", "tests/test_sln.py"), 900),
            "windows-kernel-driver-controller": (("driver/driver.c", "controller/main.cpp", "build.py"), 900),
        }
        required, min_payload = required_by_preset.get(preset_id, ((), 900))
        if required and not all(has(path) for path in required):
            return True

        if preset_id == "nextjs-ts-tailwind":
            has_next_config = any(path in paths for path in ("next.config.js", "next.config.mjs", "next.config.ts"))
            has_route = any(
                path.endswith((".tsx", ".jsx"))
                and (path.startswith("app/") or path.startswith("pages/") or path.startswith("src/pages/") or path.startswith("src/app/"))
                for path in paths
            )
            has_style = any(path.endswith(".css") or "tailwind.config" in path for path in paths)
            if not (has_next_config and has_route and has_style):
                return True

        if preset_id.startswith("dotnet-"):
            has_project = any_path(lambda path: path.endswith(".csproj"))
            if not has_project:
                return True
            if preset_id == "dotnet-wpf-csharp" and not any_path(lambda path: path.endswith("mainwindow.xaml")):
                return True
            if preset_id == "dotnet-webapi-csharp":
                has_solution = any_path(lambda path: path.endswith(".sln"))
                has_api_program = any_path(lambda path: path.endswith("/program.cs") and ".api/" in path)
                has_test_project = any_path(lambda path: path.startswith("tests/") and path.endswith(".csproj"))
                if not (has_solution and has_api_program and has_test_project):
                    return True

        if preset_id == "fastapi-python-api":
            has_app_entry = any_path(lambda path: path.startswith("src/") and path.endswith("/main.py"))
            if not has_app_entry:
                return True

        if preset_id == "sqlite-python-db":
            has_sql = any_path(lambda path: path.endswith(".sql"))
            has_py = any_path(lambda path: path.endswith(".py"))
            if not (has_sql and has_py):
                return True

        if preset_id == "powershell-module":
            has_module = any_path(lambda path: path.endswith(".psm1") or path.endswith(".psd1"))
            if not has_module:
                return True

        return payload_size < min_payload

    def _completion_quality(
        self,
        *,
        request: AgentRequest,
        mode: ModeName,
        draft: AgentDraft,
        applied: list[str],
        validation: CommandRun | None,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
    ) -> CompletionQualityInfo:
        expects_changes = self._request_expects_file_changes(request.message, mode)
        needs_project_shape = self._request_needs_project_shape(request.message, mode)
        reasons: list[str] = []
        next_actions: list[str] = []

        if not expects_changes:
            return CompletionQualityInfo(
                status="ready",
                score=1.0,
                reasons=["Request was answered as chat or review work without expected file edits."],
                should_continue=False,
            )

        open_instruction_files = self._open_instruction_files_for_completion(
            request.message,
            workspace_root,
        )
        project_manifest = self.workspace.load_project_manifest(workspace_root)

        material_changes = [change for change in draft.changes if change.action in {"create", "update"}]
        payload_size = self._change_payload_size(draft)

        if validation is not None and not self._validation_ok(validation):
            command = validation.command or "selected validation command"
            reasons.append(f"Validation failed for {command}.")
            if validation.summary:
                reasons.append(validation.summary)
            first_diagnostic = self._validation_diagnostics_log(validation.diagnostics).splitlines()[0].removeprefix("- ").strip()
            if first_diagnostic and first_diagnostic != "(none captured)":
                next_actions.append(f"Repair first diagnostic: {first_diagnostic}")
            next_actions.extend(
                [
                    "Inspect the captured validation output.",
                    "Repair the failing build/test/type-check issue.",
                    "Run validation again after the repair.",
                ]
            )
            return CompletionQualityInfo(
                status="blocked",
                score=0.2,
                reasons=reasons,
                next_actions=next_actions,
                should_continue=True,
            )

        if not draft.changes and not applied:
            return CompletionQualityInfo(
                status="needs_work",
                score=0.1,
                reasons=["The pass produced no file changes for an implementation request."],
                next_actions=[
                    "Create or update the concrete source files requested by the user.",
                    "Capture a validation command or build/test profile.",
                ],
                should_continue=True,
            )

        score = 0.35
        if material_changes:
            score += 0.15
        if applied:
            score += 0.1
        if payload_size >= 1200:
            score += 0.15
        if payload_size >= 3200:
            score += 0.1
        if validation is not None and self._validation_ok(validation):
            score += 0.25

        should_continue = False
        status: Literal["unknown", "needs_work", "ready", "blocked"] = "ready"
        validated_static_site = (
            self._request_mentions_web_project(request.message)
            and self._draft_is_static_site_shape(draft)
            and validation is not None
            and self._validation_ok(validation)
        )
        explicit_project_preset = self.fallback._explicit_project_preset(
            self._message_without_explicit_paths(request.message).lower()
        )
        destructive_reasons = self._draft_destructive_change_reasons(draft, request.message, project_manifest)
        if destructive_reasons:
            reasons.extend(destructive_reasons[:2])
            next_actions.append("Regenerate the draft as additive edits, or ask explicitly before deleting/emptying project files.")
            should_continue = True
            status = "needs_work"
            score = min(score, 0.3)
        starter_drift_reasons = self._draft_existing_project_scaffold_drift_reasons(
            draft,
            request.message,
            workspace_files,
            project_manifest,
        )
        if starter_drift_reasons:
            reasons.extend(starter_drift_reasons[:2])
            next_actions.append("Continue by modifying the existing stack-native files instead of recreating a starter scaffold.")
            should_continue = True
            status = "needs_work"
            score = min(score, 0.35)
        existing_file_overwrite_reasons = self._draft_existing_file_overwrite_reasons(
            draft,
            request.message,
            workspace_files,
            project_manifest,
        )
        if existing_file_overwrite_reasons:
            reasons.extend(existing_file_overwrite_reasons[:2])
            next_actions.append("Regenerate existing-file changes with action=update, or ask explicitly before replacing files.")
            should_continue = True
            status = "needs_work"
            score = min(score, 0.32)

        task_adherence_reasons = self._draft_task_adherence_reasons(
            draft,
            request.message,
            workspace_files,
            project_manifest,
        )
        if task_adherence_reasons:
            reasons.extend(task_adherence_reasons[:2])
            next_actions.append("Regenerate the pass so it preserves the requested target path, stack, artifact type, and validation intent.")
            should_continue = True
            status = "needs_work"
            score = min(score, 0.34)

        if needs_project_shape:
            stack_mismatch_reasons = [
                *self._draft_stack_mismatch_reasons(draft, request.message),
                *self._draft_manifest_contract_mismatch_reasons(draft, request.message, project_manifest),
            ]
            if stack_mismatch_reasons:
                reasons.extend(stack_mismatch_reasons[:2])
                next_actions.append("Regenerate or continue with the requested stack and replace unrelated starter files.")
                should_continue = True
                status = "needs_work"
                score = min(score, 0.35)

            if not validated_static_site and self._draft_is_weak_project_shape(
                draft,
                request.message,
                mode,
                workspace_files,
                project_manifest=project_manifest,
            ):
                if not stack_mismatch_reasons:
                    reasons.append("The generated project shape is still too thin for the requested app/project.")
                next_actions.append("Expand the scaffold into a complete usable project slice with entry points, styling/config, and docs.")
                should_continue = True
                status = "needs_work"
                score = min(score, 0.45)

            if (
                len(material_changes) < 6
                and not self._request_mentions_cpp_project(request.message)
                and not validated_static_site
                and not explicit_project_preset
            ):
                reasons.append("The pass changed only a small number of project files for a full app/site request.")
                next_actions.append("Continue with a larger coherent feature/UI/content pass.")
                should_continue = True
                status = "needs_work"
                score = min(score, 0.6)

            if request.run_validation and validation is None:
                reasons.append("No validation result was captured for this project pass.")
                next_actions.append("Infer or create a validation command and run it before final handoff.")
                should_continue = True
                status = "needs_work"
                score = min(score, 0.65)

        elif request.run_validation and validation is None:
            reasons.append("No validation result was captured after implementation work.")
            next_actions.append("Run the detected or requested validation command.")
            should_continue = True
            status = "needs_work"
            score = min(score, 0.65)

        if open_instruction_files:
            open_count = sum(item.pending_count for item in open_instruction_files)
            names = ", ".join(item.path for item in open_instruction_files[:3])
            first_pending = next(
                (
                    pending
                    for item in open_instruction_files
                    for pending in item.pending_items
                    if pending
                ),
                "",
            )
            reasons.append(
                f"Workspace instruction files still have {open_count} open tracked item(s): {names}."
            )
            next_actions.append(
                "Complete or mark done: " + first_pending
                if first_pending
                else "Continue the next open item from the workspace TODO/roadmap file."
            )
            should_continue = True
            status = "needs_work"
            score = min(score, 0.72)

        if validation is not None and self._validation_ok(validation) and not should_continue:
            reasons.append("Validation passed for the latest implementation pass.")
        elif not reasons:
            reasons.append("Implementation pass produced concrete file changes.")

        if not next_actions and not should_continue:
            next_actions.append("Summarize the validated changes and suggest the next feature or polish pass.")

        return CompletionQualityInfo(
            status=status,
            score=max(0.0, min(1.0, score)),
            reasons=reasons[:5],
            next_actions=next_actions[:5],
            should_continue=should_continue,
        )

    def _open_instruction_files_for_completion(
        self,
        message: str,
        workspace_root: Path,
    ) -> list[WorkspaceInstructionFile]:
        instruction_files = self.workspace.discover_instruction_files(
            workspace_root,
            max_files=6,
            referenced_text=message,
        )
        open_files = [item for item in instruction_files if item.pending_count > 0]
        if not open_files:
            return []

        lowered = " ".join(message.lower().split())
        autopilot_or_continue = (
            "autopilot continuation context" in lowered
            or "autopilot full-build directive" in lowered
            or self._broad_continue_should_follow_instruction_files(message, instruction_files)
        )
        if not autopilot_or_continue:
            return []

        return open_files

    async def _draft_response(
        self,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        memory_hits: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        recent_tasks: list[TaskSummary],
        task_plan: TaskPlan,
        context_budget: ContextBudgetResult,
        model_execution_plan: ModelExecutionPlan,
        model_registry_providers: list[ModelRegistryProvider],
        emit,
        stream_delta_callback: StreamDeltaCallback | None = None,
    ) -> tuple[AgentDraft, list[ModelAttemptInfo] | None]:
        messages = self._model_messages(
            request,
            mode,
            workspace_root,
            files,
            context_files,
            memory_hits,
            project_memory_hits,
            recent_tasks,
            task_plan,
            context_budget,
        )

        live_model_attempts: list[ModelAttemptInfo] | None = None
        fallback_mode = (
            mode
            if task_plan.intent in {"implementation", "debug_and_repair"}
            else self._fallback_mode_for_request(request.message, mode)
        )
        if self.settings.aegis_router_execution_enabled:
            try:
                if stream_delta_callback is not None:
                    execution = await self.model_attempt_executor.stream_json(
                        messages=messages,
                        plan=model_execution_plan,
                        providers=model_registry_providers,
                        on_preview_delta=stream_delta_callback,
                    )
                else:
                    execution = await self.model_attempt_executor.complete_json(
                        messages=messages,
                        plan=model_execution_plan,
                        providers=model_registry_providers,
                    )
            except Exception as exc:
                emit("model-router", "Router execution crashed", status="error", detail=str(exc))
                draft = self._fallback_draft(request.message, fallback_mode, workspace_root, context_files or files)
                draft.warnings.extend(
                    [
                        str(exc),
                        "Router execution failed before producing a draft, so Aegis used the deterministic fallback engine.",
                    ]
                )
                return draft, model_execution_plan.attempts
            live_model_attempts = self._merge_model_attempts(model_execution_plan.attempts, execution.attempts)
            emit(
                "model-router",
                "Router execution completed" if execution.succeeded else "Router execution failed",
                status="ok" if execution.succeeded else "error",
                detail=(
                    f"{len(execution.attempts)} routed attempt(s) executed."
                    if execution.succeeded
                    else execution.error
                ),
                payload={
                    "router_execution_enabled": True,
                    "attempts": [attempt.model_dump() for attempt in live_model_attempts],
                },
            )
            if execution.succeeded and execution.payload is not None:
                payload = execution.payload
                emit("model", "Routed model draft received", payload={"keys": sorted(payload.keys())})
            else:
                draft = self._fallback_draft(request.message, fallback_mode, workspace_root, context_files or files)
                draft.warnings.append(
                    "Router execution did not produce a usable draft, so Aegis used the deterministic fallback engine."
                )
                return draft, live_model_attempts
        else:
            status = await self.model.status()
            emit(
                "model",
                "Local model status checked",
                status="ok" if status.ready else "warning",
                detail=status.message,
                payload={"model": self.model.label, "endpoint": self.model.endpoint, "api": self.model.api},
            )

            if not status.ready:
                draft = self._fallback_draft(request.message, fallback_mode, workspace_root, context_files or files)
                draft.warnings.append("Local model was unavailable, so Aegis used the deterministic fallback engine.")
                return draft, live_model_attempts

            try:
                if stream_delta_callback is not None:
                    payload = await self._local_complete_json_with_preview(messages, stream_delta_callback)
                else:
                    payload = await self.model.complete_json(messages)
            except (LocalModelError, ProviderError, ValueError, KeyError, IndexError, TypeError) as exc:
                emit("model", "Local model draft failed", status="error", detail=str(exc))
                draft = self._fallback_draft(request.message, fallback_mode, workspace_root, context_files or files)
                draft.warnings.extend([str(exc), "Aegis used the deterministic fallback engine for this turn."])
                return draft, live_model_attempts

            emit("model", "Local model draft received", payload={"keys": sorted(payload.keys())})
        draft = self._parse_model_payload(payload, request_message=request.message, mode=mode)
        draft = self._sanitize_model_change_paths(draft, workspace_root)
        effective_message = self._effective_request_message(request.message, mode, task_plan)
        draft = self._harden_native_cpp_draft(draft, effective_message, workspace_root)
        direct_fallback = self._fallback_draft(request.message, "chat", workspace_root, context_files or files)
        if task_plan.intent == "conversation" and self._direct_answer_fallback_is_more_specific(
            draft.reply,
            direct_fallback.reply,
        ):
            direct_fallback.warnings.extend(draft.warnings)
            direct_fallback.warnings.append(
                "The selected model produced a low-detail direct answer, so Aegis used the direct-answer fallback for this turn."
            )
            return direct_fallback, live_model_attempts

        expects_file_changes = task_plan.intent in {"implementation", "debug_and_repair"} or self._request_expects_file_changes(
            effective_message,
            mode,
        )
        workspace_files = files or context_files
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        if expects_file_changes and not draft.changes:
            fallback = self._fallback_draft(effective_message, mode, workspace_root, workspace_files)
            if fallback.changes:
                emit(
                    "model",
                    "Model returned no file changes",
                    status="warning",
                    detail="Aegis used the deterministic starter generator so the request still produces files.",
                )
                fallback.warnings.extend(draft.warnings)
                fallback.warnings.append(
                    "The model returned no file changes for a create/build request, so Aegis used the deterministic starter generator."
                )
                return fallback, live_model_attempts
            continuation = self._existing_project_no_change_continuation_draft(
                original_draft=draft,
                fallback=fallback,
                message=effective_message,
                mode=mode,
                workspace_root=workspace_root,
                workspace_files=workspace_files,
                project_manifest=project_manifest,
            )
            if continuation is not None:
                emit(
                    "model",
                    "Model returned no file changes",
                    status="warning",
                    detail=(
                        "Aegis preserved the existing project and prepared a strict existing-project "
                        "continuation pass instead of creating unrelated starter files."
                    ),
                )
                return continuation, live_model_attempts
        elif expects_file_changes and draft.changes:
            draft_contract_issues = self._draft_manifest_contract_mismatch_reasons(
                draft,
                effective_message,
                project_manifest,
            )
            draft_destructive_issues = self._draft_destructive_change_reasons(
                draft,
                effective_message,
                project_manifest,
            )
            draft_starter_drift_issues = self._draft_existing_project_scaffold_drift_reasons(
                draft,
                effective_message,
                workspace_files,
                project_manifest,
            )
            draft_overwrite_issues = self._draft_existing_file_overwrite_reasons(
                draft,
                effective_message,
                workspace_files,
                project_manifest,
            )
            draft_is_weak = self._draft_is_weak_project_shape(
                draft,
                effective_message,
                mode,
                workspace_files,
                project_manifest=project_manifest,
            )
            if (
                not draft_is_weak
                and not draft_destructive_issues
                and not draft_starter_drift_issues
                and not draft_overwrite_issues
            ):
                return draft, live_model_attempts

            fallback = self._fallback_draft(effective_message, mode, workspace_root, workspace_files)
            fallback_contract_issues = self._draft_manifest_contract_mismatch_reasons(
                fallback,
                effective_message,
                project_manifest,
            )
            fallback_destructive_issues = self._draft_destructive_change_reasons(
                fallback,
                effective_message,
                project_manifest,
            )
            fallback_starter_drift_issues = self._draft_existing_project_scaffold_drift_reasons(
                fallback,
                effective_message,
                workspace_files,
                project_manifest,
            )
            fallback_overwrite_issues = self._draft_existing_file_overwrite_reasons(
                fallback,
                effective_message,
                workspace_files,
                project_manifest,
            )
            fallback_is_weak = self._draft_is_weak_project_shape(
                fallback,
                effective_message,
                mode,
                workspace_files,
                project_manifest=project_manifest,
            )
            if (
                fallback.changes
                and not fallback_contract_issues
                and not fallback_destructive_issues
                and not fallback_starter_drift_issues
                and not fallback_overwrite_issues
                and (not fallback_is_weak or bool(draft_contract_issues or draft_starter_drift_issues or draft_overwrite_issues))
            ):
                title = (
                    "Model draft violated the workspace mission contract"
                    if draft_contract_issues
                    else "Model draft contained destructive file changes"
                    if draft_destructive_issues
                    else "Model draft would overwrite existing project files"
                    if draft_overwrite_issues
                    else "Model draft tried to restart an existing project"
                    if draft_starter_drift_issues
                    else "Model draft was too small for the project request"
                )
                detail = (
                    "Aegis replaced the off-stack draft with a stack-aware fallback before applying files."
                    if draft_contract_issues
                    else "Aegis replaced the destructive draft with a safer additive fallback before applying files."
                    if draft_destructive_issues
                    else "Aegis replaced the create-as-overwrite draft with a safer continuation patch before applying files."
                    if draft_overwrite_issues
                    else "Aegis replaced the fresh-starter draft with a safer continuation patch before applying files."
                    if draft_starter_drift_issues
                    else "Aegis replaced the undersized draft with a fuller stack-aware project scaffold."
                )
                emit(
                    "model",
                    title,
                    status="warning",
                    detail=detail,
                )
                fallback.warnings.extend(draft.warnings)
                if draft_contract_issues:
                    fallback.warnings.extend(draft_contract_issues[:2])
                    fallback.warnings.append(
                        "The model draft did not match the saved workspace mission contract, so Aegis used the stack-aware generator instead."
                    )
                elif draft_destructive_issues:
                    fallback.warnings.extend(draft_destructive_issues[:2])
                    fallback.warnings.append(
                        "The model draft tried to delete or empty important project files without explicit instruction, so Aegis used a safer additive generator instead."
                    )
                elif draft_overwrite_issues:
                    fallback.warnings.extend(draft_overwrite_issues[:2])
                    fallback.warnings.append(
                        "The model draft used create on existing project files, so Aegis used a safer continuation path instead."
                    )
                elif draft_starter_drift_issues:
                    fallback.warnings.extend(draft_starter_drift_issues[:2])
                    fallback.warnings.append(
                        "The model draft looked like a fresh starter scaffold for an existing project, so Aegis used a safer continuation path instead."
                    )
                else:
                    fallback.warnings.append(
                        "The model draft was too small for an app/site/project request, so Aegis used the fuller stack-aware generator."
                    )
                return fallback, live_model_attempts
            if draft_contract_issues or draft_destructive_issues or draft_starter_drift_issues or draft_overwrite_issues:
                safe_draft = AgentDraft(
                    reply=(
                        "Aegis rejected a risky model draft before applying files. "
                        "The next pass should regenerate additive, stack-native changes for this workspace mission."
                    ),
                    plan=[
                        "Keep the saved workspace stack and mission contract.",
                        "Avoid deleting or emptying project files unless the user explicitly asks for that.",
                        "Use update, not create, when modifying existing project files.",
                        "Regenerate concrete source changes in the requested stack.",
                        "Run the workspace validation command after applying changes.",
                    ],
                    changes=[],
                    warnings=[
                        *draft.warnings,
                        *draft_contract_issues[:2],
                        *draft_destructive_issues[:2],
                        *draft_starter_drift_issues[:2],
                        *draft_overwrite_issues[:2],
                    ],
                )
                return safe_draft, live_model_attempts
        elif self._model_reply_is_empty_fallback(draft):
            fallback = self._fallback_draft(request.message, "chat", workspace_root, workspace_files)
            fallback.warnings.extend(draft.warnings)
            fallback.warnings.append(
                "The selected model returned no usable answer, so Aegis used the direct chat fallback for this turn."
            )
            return fallback, live_model_attempts
        return draft, live_model_attempts

    async def _local_complete_json_with_preview(
        self,
        messages: list[dict[str, str]],
        on_preview_delta: StreamDeltaCallback,
    ) -> dict[str, Any]:
        content_parts: list[str] = []
        extractor = StructuredReplyDeltaExtractor()

        async for event in self.model.stream_text(messages, structured_json=True):
            if event.type != "delta" or not event.delta:
                continue
            content_parts.append(event.delta)
            preview = extractor.feed(event.delta)
            if preview:
                on_preview_delta(
                    {
                        "preview_action": "append",
                        "preview_attempt": 1,
                        "provider_label": self.model.label,
                        "provider_api": self.model.api,
                        "model": self.model.model,
                        "delta": preview,
                    }
                )

        try:
            return extract_json_object("".join(content_parts))
        except (ValueError, KeyError, IndexError, TypeError):
            on_preview_delta(
                {
                    "preview_action": "reset",
                    "preview_attempt": 1,
                    "provider_label": self.model.label,
                    "provider_api": self.model.api,
                    "model": self.model.model,
                    "delta": "",
                    "message": f"{self.model.label} preview was retired because the stream did not produce valid structured JSON.",
                }
            )
            raise

    def _direct_answer_fallback_is_more_specific(self, model_reply: str, fallback_reply: str) -> bool:
        fallback = fallback_reply.strip()
        if not fallback:
            return False
        parts = [part.strip() for part in fallback.split(",")]
        is_numeric_sequence = len(parts) > 1 and all(part.lstrip("-").isdigit() for part in parts)
        if not is_numeric_sequence:
            return False
        reply = model_reply.strip()
        if not reply:
            return True
        expected_prefix = parts[: min(5, len(parts))]
        return not all(part in reply for part in expected_prefix)

    async def _validate_and_repair(
        self,
        *,
        task_id: str,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        workspace_files: list[WorkspaceFile],
        draft: AgentDraft,
        memory_hits: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        warnings: list[str],
        applied: list[str],
        emit,
        validation_override: ValidationRecipe | None = None,
        multi_agent: MultiAgentCoordinator | None = None,
        agent_events: list[ToolEvent] | None = None,
    ) -> tuple[CommandRun | None, list[RepairAttempt], list[FixMemoryEntry]]:
        def record_agent(event: ToolEvent) -> None:
            if agent_events is not None:
                agent_events.append(event)

        validation_override = self._validation_override_recipe(request) or validation_override
        install_run = self._maybe_install_dependencies(workspace_root, emit)
        if install_run is not None and not self._validation_ok(install_run):
            warnings.append(install_run.summary or install_run.reason or "Dependency installation failed before validation.")
            if multi_agent is not None:
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "validation",
                        "Validation Agent stopped before validation",
                        status="error",
                        summary=install_run.summary or install_run.reason,
                        outputs={"command": install_run.command, "exit_code": install_run.exit_code},
                    )
                )
            return install_run, [], memory_hits

        try:
            self.store.transition_task(task_id, "validating", title="Task validation started", detail="Running validation after file changes.")
            self.store.transition_subtask(task_id, "Run validation", "running", detail="Validation started.")
        except ValueError:
            pass
        validation = self._run_validation(workspace_root, emit, override_recipe=validation_override)
        if validation is not None and multi_agent is not None:
            record_agent(
                multi_agent.agent_output(
                    task_id,
                    "validation",
                    "Validation Agent interpreted result",
                    status="ok" if self._validation_ok(validation) else "error",
                    summary=validation.summary or validation.reason or validation.command,
                    outputs={
                        "command": validation.command,
                        "exit_code": validation.exit_code,
                        "allowed": validation.allowed,
                        "timed_out": validation.timed_out,
                        "category": self._categorize_validation_failure(validation)
                        if not self._validation_ok(validation)
                        else "passed",
                    },
                )
            )
        if validation is not None:
            self.store.add_task_artifacts(
                task_id,
                validation_commands=[validation.command] if validation.command else [],
                error_summary=self._error_signature(validation) if not self._validation_ok(validation) else "",
            )
        original_failure_signature: str | None = None
        repair_attempts: list[RepairAttempt] = []

        if validation and not validation.allowed:
            warnings.append(validation.reason or "Validation could not run under the current approval or sandbox settings.")
            emit(
                "repair",
                "Repair skipped",
                status="warning",
                detail="Aegis skipped automatic repair because validation could not run under the current control settings.",
            )
            if multi_agent is not None:
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "repair",
                        "Repair Agent skipped",
                        status="warning",
                        summary="Validation could not run under the current approval or sandbox settings.",
                        outputs={"reason": validation.reason, "allowed": validation.allowed},
                    )
                )
            return validation, repair_attempts, memory_hits

        original_failure_category = "unknown"
        if validation and not self._validation_ok(validation):
            original_failure_signature = self._error_signature(validation)
            original_failure_category = self._categorize_validation_failure(validation)
            try:
                self.store.transition_subtask(task_id, "Run validation", "failed", detail=validation.summary or validation.reason)
            except ValueError:
                pass

        attempt = 0
        while validation and not self._validation_ok(validation) and attempt < request.max_repair_attempts:
            attempt += 1
            if multi_agent is not None:
                record_agent(
                    multi_agent.handoff(
                        task_id,
                        "validation",
                        "repair",
                        reason=f"Validation failed; repair attempt {attempt} is allowed by the current iteration budget.",
                        artifacts={
                            "failure_category": self._categorize_validation_failure(validation),
                            "failure_signature": self._error_signature(validation),
                            "max_repair_attempts": request.max_repair_attempts,
                        },
                    )
                )
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "repair",
                        "Repair Agent started attempt",
                        summary=f"Repair attempt {attempt} started after validation failure.",
                        outputs={
                            "attempt": attempt,
                            "max_attempts": request.max_repair_attempts,
                            "failure_category": self._categorize_validation_failure(validation),
                        },
                        iteration=attempt,
                    )
                )
            try:
                self.store.transition_task(
                    task_id,
                    "repairing",
                    title="Task repair started",
                    detail=f"Repair attempt {attempt} started after validation failure.",
                )
                self.store.transition_subtask(task_id, "Repair failures", "running", detail=f"Repair attempt {attempt} started.")
            except ValueError:
                pass
            failure_category = self._categorize_validation_failure(validation)
            relevant_repairs = self.store.relevant_fix_history(
                project_root=workspace_root,
                query="\n".join(filter(None, [request.message, self._error_signature(validation), failure_category])),
                limit=3,
            )
            memory_hits = self._merge_memory_hits(memory_hits, relevant_repairs)
            repair = await self._draft_repair(
                request,
                mode,
                workspace_root,
                workspace_files,
                validation,
                attempt,
                relevant_repairs,
                project_memory_hits,
                emit,
            )
            warnings.extend(repair.warnings)

            if not repair.changes:
                attempt_record = RepairAttempt(
                    attempt=attempt,
                    category=failure_category,
                    before_signature=self._error_signature(validation),
                    outcome="no_patch",
                    summary="The model did not propose a concrete repair patch.",
                    created_at=utc_now(),
                )
                self.store.record_repair_attempt(task_id, attempt_record)
                repair_attempts.append(attempt_record)
                emit(
                    "repair",
                    "Repair stopped",
                    status="warning",
                    detail="The local model did not propose a concrete repair patch.",
                )
                if multi_agent is not None:
                    record_agent(
                        multi_agent.failure(
                            task_id,
                            "repair",
                            summary="Repair Agent stopped because the model did not propose a concrete repair patch.",
                            outputs={"attempt": attempt, "failure_category": failure_category},
                            iteration=attempt,
                        )
                    )
                break

            before_validation = validation
            approved_repairs, blocked_repairs = self.approvals.partition_auto_apply_changes(repair.changes)
            if blocked_repairs:
                warnings.append(
                    "Some repair edits required manual approval, so Aegis only applied the lower-risk subset automatically."
                )
                emit(
                    "approval",
                    "Repair changes filtered by approval tier",
                    status="warning",
                    detail=f"{len(blocked_repairs)} repair change(s) were kept in preview because they require manual approval.",
                    payload={"blocked_paths": [change.path for change, _ in blocked_repairs]},
                )
                if multi_agent is not None:
                    record_agent(
                        multi_agent.approval_requested(
                            task_id,
                            "repair",
                            reason=f"{len(blocked_repairs)} repair change(s) require manual approval.",
                            blocked_paths=[change.path for change, _ in blocked_repairs],
                        )
                    )
            if blocked_repairs and not approved_repairs:
                attempt_record = RepairAttempt(
                    attempt=attempt,
                    category=failure_category,
                    before_signature=self._error_signature(validation),
                    outcome="approval_blocked",
                    summary="Repair patch required manual approval under the current control settings.",
                    created_at=utc_now(),
                )
                self.store.record_repair_attempt(task_id, attempt_record)
                repair_attempts.append(attempt_record)
                emit(
                    "repair",
                    "Repair paused for approval",
                    status="warning",
                    detail="The proposed repair patch was kept in preview because it requires manual approval.",
                    payload={"blocked_paths": [change.path for change, _ in blocked_repairs]},
                )
                if multi_agent is not None:
                    record_agent(
                        multi_agent.agent_output(
                            task_id,
                            "repair",
                            "Repair Agent paused for approval",
                            status="warning",
                            summary="Repair patch required manual approval under the current control settings.",
                            outputs={"blocked_paths": [change.path for change, _ in blocked_repairs]},
                            iteration=attempt,
                        )
                    )
                break

            repair_result = self.workspace.apply_changes(workspace_root, approved_repairs)
            warnings.extend(repair_result.warnings)
            workspace_files[:] = self.workspace.scan(workspace_root, request.max_files)
            self.store.add_task_artifacts(
                task_id,
                related_files=[change.path for change in approved_repairs],
                checkpoints=[repair_result.checkpoint] if repair_result.checkpoint else [],
            )
            emit(
                "repair",
                "Repair patch applied",
                detail=f"{len(repair_result.applied)} repair change(s) applied.",
                payload={"applied": repair_result.applied, "checkpoint": repair_result.checkpoint},
            )
            if multi_agent is not None:
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "repair",
                        "Repair Agent applied patch",
                        summary=f"{len(repair_result.applied)} repair change(s) applied.",
                        outputs={"applied": repair_result.applied, "checkpoint": repair_result.checkpoint},
                        iteration=attempt,
                    )
                )

            try:
                self.store.transition_task(
                    task_id,
                    "validating",
                    title="Task validation restarted",
                    detail=f"Running validation after repair attempt {attempt}.",
                )
            except ValueError:
                pass
            if multi_agent is not None:
                record_agent(
                    multi_agent.handoff(
                        task_id,
                        "repair",
                        "validation",
                        reason=f"Repair attempt {attempt} was applied; validation will rerun.",
                        artifacts={"checkpoint": repair_result.checkpoint},
                    )
                )
            next_validation = self._run_validation(workspace_root, emit, override_recipe=validation_override)
            if next_validation is not None and multi_agent is not None:
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "validation",
                        "Validation Agent interpreted repair result",
                        status="ok" if self._validation_ok(next_validation) else "error",
                        summary=next_validation.summary or next_validation.reason or next_validation.command,
                        outputs={
                            "command": next_validation.command,
                            "exit_code": next_validation.exit_code,
                            "attempt": attempt,
                            "category": self._categorize_validation_failure(next_validation)
                            if not self._validation_ok(next_validation)
                            else "passed",
                        },
                        iteration=min(attempt + 1, multi_agent.limits.max_iterations("validation")),
                    )
                )
            if next_validation is not None:
                self.store.add_task_artifacts(
                    task_id,
                    validation_commands=[next_validation.command] if next_validation.command else [],
                    error_summary=self._error_signature(next_validation) if not self._validation_ok(next_validation) else "",
                )
            attempt_record = RepairAttempt(
                attempt=attempt,
                category=failure_category,
                before_signature=self._error_signature(before_validation),
                after_signature=self._error_signature(next_validation) if next_validation else "",
                checkpoint=repair_result.checkpoint,
                outcome=self._repair_outcome(before_validation, next_validation),
                summary=self._repair_summary(before_validation, next_validation, repair),
            )

            if attempt_record.outcome in {"worse", "unchanged", "sideways"} and repair_result.checkpoint:
                restored = self.workspace.restore_checkpoint(workspace_root, repair_result.checkpoint)
                workspace_files[:] = self.workspace.scan(workspace_root, request.max_files)
                emit(
                    "repair",
                    "Repair rollback applied",
                    status="warning",
                    detail=f"Rolled back {len(restored)} file(s) after a non-improving repair attempt.",
                    payload={"restored": restored, "checkpoint": repair_result.checkpoint},
                )
                if multi_agent is not None:
                    record_agent(
                        multi_agent.agent_output(
                            task_id,
                            "repair",
                            "Repair Agent rolled back attempt",
                            status="warning",
                            summary="Repair attempt did not improve validation, so Aegis restored the prior checkpoint.",
                            outputs={"restored": restored, "checkpoint": repair_result.checkpoint},
                            iteration=attempt,
                        )
                    )
                validation = self._run_validation(workspace_root, emit, override_recipe=validation_override)
                attempt_record.after_signature = self._error_signature(validation) if validation else ""
                attempt_record.outcome = "rolled_back"
                attempt_record.summary = "Repair attempt did not improve validation, so Aegis restored the prior checkpoint."
            else:
                validation = next_validation
                applied.extend(repair_result.applied)
                draft.changes.extend(repair.changes)

            attempt_record.created_at = utc_now()
            self.store.record_repair_attempt(task_id, attempt_record)
            repair_attempts.append(attempt_record)

        if validation and not self._validation_ok(validation) and attempt >= request.max_repair_attempts and multi_agent is not None:
            record_agent(
                multi_agent.failure(
                    task_id,
                    "repair",
                    summary=f"Repair Agent stopped after {attempt} attempt(s); validation is still failing.",
                    outputs={
                        "attempts": attempt,
                        "max_repair_attempts": request.max_repair_attempts,
                        "failure_signature": self._error_signature(validation),
                    },
                    iteration=max(1, attempt),
                )
            )

        if validation and self._validation_ok(validation) and attempt > 0 and original_failure_signature:
            try:
                self.store.transition_subtask(task_id, "Repair failures", "completed", detail="Repair loop produced a passing validation run.")
                self.store.transition_subtask(task_id, "Run validation", "completed", detail=validation.summary or validation.reason)
            except ValueError:
                pass
            if multi_agent is not None:
                record_agent(
                    multi_agent.agent_output(
                        task_id,
                        "repair",
                        "Repair Agent completed failure recovery",
                        summary="Repair loop produced a passing validation run.",
                        outputs={"attempts": attempt, "command": validation.command},
                        iteration=max(1, attempt),
                    )
                )
            self.store.remember_fix(
                project_root=workspace_root,
                error_signature=original_failure_signature,
                fix_summary="Local repair loop produced a passing validation run.",
                evidence=f"{validation.command} exited with {validation.exit_code}",
                confidence=0.82,
                category=original_failure_category,
            )
        elif validation and self._validation_ok(validation):
            try:
                self.store.transition_subtask(task_id, "Run validation", "completed", detail=validation.summary or validation.reason)
            except ValueError:
                pass
        elif validation and not self._validation_ok(validation):
            try:
                self.store.transition_subtask(task_id, "Repair failures", "failed", detail=validation.summary or validation.reason)
            except ValueError:
                pass

        return validation, repair_attempts, memory_hits

    def _dependency_install_recipe(self, workspace_root: Path) -> ValidationRecipe | None:
        package_json = workspace_root / "package.json"
        if package_json.exists() and not (workspace_root / "node_modules").exists():
            command = self.validation._inferred_install_command(workspace_root)
            if command:
                return ValidationRecipe(
                    command=command,
                    label="Install dependencies",
                    source="install",
                    notes="Node dependency manifest exists and node_modules is missing.",
                )
        return None

    def _maybe_install_dependencies(self, workspace_root: Path, emit) -> CommandRun | None:
        recipe = self._dependency_install_recipe(workspace_root)
        if recipe is None:
            return None

        emit(
            "install",
            "Dependency install selected",
            detail=recipe.command,
            payload={"recipe": recipe.model_dump()},
        )
        allowed_to_run, approval_reason = self.approvals.should_auto_run_command(recipe.command, manual=False)
        if not allowed_to_run:
            run = CommandRun(
                command=recipe.command,
                cwd=str(workspace_root),
                allowed=False,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                reason=approval_reason,
                category="permission",
                summary=approval_reason,
            )
            emit(
                "approval",
                "Dependency install requires manual confirmation",
                status="warning",
                detail=approval_reason,
                payload=run.model_dump(),
            )
            return run

        result = self.commands.run(recipe.command, workspace_root, sandbox_profile=self.approvals.sandbox)
        run = self._command_run(result, recipe=recipe)
        emit(
            "command",
            "Dependency install command executed",
            status="ok" if run.exit_code == 0 else "error",
            detail=run.summary or result.reason,
            payload=run.model_dump(),
        )
        return run

    async def _draft_repair(
        self,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
        validation: CommandRun,
        attempt: int,
        repair_memory: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        emit,
    ) -> AgentDraft:
        memory_context = self._memory_context(repair_memory)
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        failure = {
            "role": "user",
            "content": (
                "Validation failed. Return JSON with the smallest complete-file repair patch.\n"
                f"Repair attempt: {attempt}\n"
                f"Failure category: {self._categorize_validation_failure(validation)}\n"
                f"Failure summary: {validation.summary}\n"
                f"Repair strategy: {self._repair_strategy_hint(validation)}\n"
                f"Command: {validation.command}\n"
                f"Exit code: {validation.exit_code}\n"
                f"Relevant prior fixes:\n{memory_context or '(none)'}\n"
                f"STDOUT:\n{validation.stdout[-6000:]}\n"
                f"STDERR:\n{validation.stderr[-6000:]}\n"
            ),
        }
        repair_context_files = self._select_context_files(
            workspace_root,
            files,
            "\n".join(
                filter(
                    None,
                    [
                        request.message,
                        validation.command,
                        self._error_signature(validation),
                        self._categorize_validation_failure(validation),
                        self._project_manifest_context(project_manifest),
                        self._dependency_profile_context(dependency_profile),
                        self._project_intelligence_context(workspace_root),
                    ],
                )
            ),
            context_paths=request.context_paths,
        )
        repair_task_plan = self.task_planner.build_plan(
            message=f"{request.message}\n\nRepair validation failure: {validation.summary}",
            mode=mode,
            workspace_files=files,
            context_files=repair_context_files,
            project_manifest=project_manifest,
            dependency_profile=dependency_profile,
        )
        try:
            payload = await self.model.complete_json(
                [
                    *self._model_messages(
                        request,
                        mode,
                        workspace_root,
                        files,
                        repair_context_files,
                        repair_memory,
                        project_memory_hits,
                        [],
                        repair_task_plan,
                    ),
                    failure,
                ]
            )
        except LocalModelError as exc:
            emit("repair", "Repair model call failed", status="error", detail=str(exc))
            return AgentDraft(reply="", warnings=[str(exc)])

        emit("repair", "Repair draft received", payload={"keys": sorted(payload.keys())})
        draft = self._parse_model_payload(payload, request_message=request.message, mode=mode)
        return self._sanitize_model_change_paths(draft, workspace_root)

    def _can_stream_direct_chat(self, request: AgentRequest, mode: ModeName, task_plan: TaskPlan) -> bool:
        if task_plan.intent != "conversation":
            return False
        if self._request_expects_file_changes(request.message, mode):
            return False
        if self._request_asks_for_validation(request.message):
            return False
        if (
            request.apply_changes
            or request.run_validation
            or request.validation_command_override.strip()
            or request.validation_label_override.strip()
            or request.validation_notes_override.strip()
        ):
            return False
        return True

    def _direct_chat_messages(
        self,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        memory_hits: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        recent_tasks: list[TaskSummary],
        task_plan: TaskPlan,
        context_budget: ContextBudgetResult | None = None,
    ) -> list[dict[str, str]]:
        messages = self._model_messages(
            request,
            mode,
            workspace_root,
            files,
            context_files,
            memory_hits,
            project_memory_hits,
            recent_tasks,
            task_plan,
            context_budget,
        )
        return [{"role": "system", "content": self._direct_chat_system_prompt()}, *messages[1:]]

    def _model_messages(
        self,
        request: AgentRequest,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        memory_hits: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        recent_tasks: list[TaskSummary],
        task_plan: TaskPlan,
        context_budget: ContextBudgetResult | None = None,
    ) -> list[dict[str, str]]:
        selected_context_files = context_files if context_budget is not None else (context_files or files)
        context = self.workspace.context_for_model(
            workspace_root,
            selected_context_files,
            max_chars=context_budget.max_context_chars if context_budget else None,
            max_file_chars=context_budget.max_file_chars if context_budget else 4_000,
        )
        file_map = "\n".join(self._workspace_file_line(item) for item in files[:120])
        relevant_file_map = "\n".join(
            self._workspace_file_line(item) for item in selected_context_files[:16]
        )
        large_file_inventory = self._large_file_context(workspace_root, files)
        history_limit = context_budget.profile.max_history_turns if context_budget else 8
        history = "\n".join(f"{item.role}: {item.content}" for item in request.history[-history_limit:])
        task_history = self._task_history_context(recent_tasks)
        memory_context = self._memory_context(memory_hits)
        project_memory_context = self._project_memory_context(project_memory_hits)
        instruction_file_context = self._instruction_file_context(
            self.workspace.discover_instruction_files(
                workspace_root,
                referenced_text=request.message,
            )
        )
        project_manifest = self.workspace.load_project_manifest(workspace_root)
        project_manifest_context = self._project_manifest_context(project_manifest)
        dependency_profile = self.workspace.inspect_dependency_profile(workspace_root)
        dependency_profile_context = self._dependency_profile_context(dependency_profile)
        project_status_context = self._project_status_context(workspace_root)
        user_content = f"""
Mode: {mode}
Workspace root: {workspace_root}

Recent conversation:
{history or "(none)"}

Recent task history:
{task_history or "(none)"}

Relevant prior successful fixes:
{memory_context or "(none)"}

Project notes and preferences:
{project_memory_context or "(none)"}

Project instruction files:
{instruction_file_context or "(none)"}

Aegis project manifest:
{project_manifest_context or "(none)"}

Workspace dependency profile:
{dependency_profile_context or "(none)"}

Project build and validation state:
{project_status_context or "(none)"}

Aegis execution plan:
{task_plan.to_prompt_context()}

Mission continuity contract:
{self._mission_continuity_contract_context(request, mode, task_plan, files, dependency_profile, project_manifest)}

Full-build contract:
{self._full_build_contract_context(request, mode, task_plan, files, dependency_profile)}

Context budget:
{self._context_budget_prompt(context_budget)}

Workspace files:
{file_map or "(workspace is empty)"}

Large file inventory:
{large_file_inventory or "(no large text files detected in the scanned workspace)"}

Indexed relevant files:
{relevant_file_map or "(no focused files were selected)"}

Relevant file snippets:
{context or "(no text files loaded)"}

User request:
{request.message}
""".strip()
        return [{"role": "system", "content": self._system_prompt()}, {"role": "user", "content": user_content}]

    def _project_manifest_context(self, manifest: WorkspaceProjectManifest | None) -> str:
        if manifest is None:
            return ""

        lines = [
            f"- Project: {manifest.title or manifest.project_name or '(unnamed)'}",
            f"- Preset: {manifest.preset_label or manifest.preset_id or '(unknown)'}",
            f"- Stack: {manifest.framework or '(unknown framework)'} / {manifest.language or '(unknown language)'}",
        ]
        if manifest.package_manager:
            lines.append(f"- Package manager: {manifest.package_manager}")
        if manifest.install_command:
            lines.append(f"- Install command: {manifest.install_command}")
        if manifest.validation_command:
            lines.append(f"- Validation command: {manifest.validation_command}")
        if manifest.tags:
            lines.append(f"- Tags: {', '.join(manifest.tags[:12])}")

        mission = manifest.mission_contract if isinstance(manifest.mission_contract, dict) else {}
        mission_preset = str(mission.get("preset_id") or manifest.preset_id or "").strip()
        mission_family = str(mission.get("stack_family") or self._manifest_stack_family(manifest) or "").strip()
        mission_artifact = str(mission.get("artifact_type") or "").strip()
        mission_prompt = str(mission.get("original_prompt") or manifest.original_prompt or "").strip()
        if mission_preset or mission_family or mission_artifact:
            bits = []
            if mission_preset:
                bits.append(f"preset={mission_preset}")
            if mission_family:
                bits.append(f"stack_family={mission_family}")
            if mission_artifact:
                bits.append(f"artifact={mission_artifact}")
            lines.append("- Mission contract: " + "; ".join(bits))
            lines.append(
                "- Mission rule: preserve this stack on continue/build/repair prompts unless the latest user explicitly asks to convert, migrate, or switch stacks."
            )
        if mission_prompt:
            lines.append(f"- Original task: {mission_prompt[:280]}")

        handoff = manifest.agent_handoff if isinstance(manifest.agent_handoff, dict) else {}
        primary_goal = str(handoff.get("primary_goal", "")).strip()
        if primary_goal:
            lines.append(f"- Handoff goal: {primary_goal}")

        for key, label in (("first_pass", "First pass"), ("safety", "Safety")):
            values = handoff.get(key)
            if not isinstance(values, list):
                continue
            cleaned = [str(item).strip() for item in values if str(item).strip()]
            if cleaned:
                lines.append(f"- {label}: " + "; ".join(cleaned[:5]))

        return "\n".join(lines)

    def _dependency_profile_context(self, profile: WorkspaceDependencyProfile | None) -> str:
        if profile is None:
            return ""

        lines: list[str] = []

        def add_list(label: str, values: list[str], limit: int = 10) -> None:
            cleaned = [str(item).strip() for item in values if str(item).strip()]
            if cleaned:
                lines.append(f"- {label}: {', '.join(cleaned[:limit])}")

        add_list("Languages", profile.languages)
        add_list("Frameworks", profile.frameworks)
        add_list("Package managers", profile.package_managers)
        add_list("Build systems", profile.build_systems)
        add_list("Config files", profile.config_files, limit=12)
        add_list("Install commands", profile.install_commands, limit=5)
        add_list("Validation commands", profile.validation_commands, limit=8)
        add_list("Database tools", profile.database_tools)

        if profile.scripts:
            script_bits = [f"{item.name}={item.command}" for item in profile.scripts[:10]]
            lines.append(f"- Package scripts: {'; '.join(script_bits)}")
        if profile.dependencies:
            dependencies = [item.name for item in profile.dependencies[:16]]
            lines.append(f"- Runtime dependencies: {', '.join(dependencies)}")
        if profile.dev_dependencies:
            dependencies = [item.name for item in profile.dev_dependencies[:16]]
            lines.append(f"- Development dependencies: {', '.join(dependencies)}")
        if profile.warnings:
            lines.append(f"- Profile warnings: {'; '.join(profile.warnings[:4])}")

        return "\n".join(lines)

    def _turn_expects_file_work(self, request: AgentRequest, mode: ModeName, task_plan: TaskPlan) -> bool:
        if self._request_expects_file_changes(request.message, mode):
            return True
        if task_plan.intent in {"implementation", "debug_and_repair"}:
            return True
        if (
            request.apply_changes
            or request.run_validation
            or request.validation_command_override.strip()
            or request.validation_label_override.strip()
            or request.validation_notes_override.strip()
        ):
            return True
        return False

    def _mission_continuity_contract_context(
        self,
        request: AgentRequest,
        mode: ModeName,
        task_plan: TaskPlan,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile | None,
        project_manifest: WorkspaceProjectManifest | None,
    ) -> str:
        if not self._turn_expects_file_work(request, mode, task_plan):
            return "- No mutation contract is active for this turn."

        mission_anchor = self._mission_anchor_from_history(request.history)
        explicit_workspace = self._explicit_prompt_workspace(request.message)
        manifest_family = self._manifest_stack_family(project_manifest)
        workspace_family = self._workspace_stack_family(files)
        request_family = self._request_stack_family(request.message)
        target_family = manifest_family or workspace_family or request_family
        family_label = self._family_label(target_family) if target_family else "infer from request and workspace"
        artifact_label = self._artifact_label_for_request_or_manifest(request.message, project_manifest)

        lines = [
            f"- Active target family: {family_label}.",
            "- The latest user request controls the target path and artifact type; older chat examples do not override it.",
            "- If the user says continue, build, repair, validate, or autopilot, continue the current mission contract instead of choosing a new stack.",
            "- Do not add starter/template files from a different project type just because the model needs more output.",
        ]
        anchor_context = self._mission_anchor_context(mission_anchor)
        if anchor_context:
            lines.append(anchor_context)
        if artifact_label:
            lines.append(f"- Active artifact intent: {artifact_label}.")
        if explicit_workspace:
            lines.extend(
                [
                    f"- Explicit path resolved from the prompt: {explicit_workspace}.",
                    "- Words after that explicit path are instructions, not part of the folder name; never create a sibling folder containing trailing instruction text.",
                ]
            )
        if project_manifest is not None:
            project_label = project_manifest.title or project_manifest.project_name or "the active workspace"
            lines.append(f"- Workspace manifest is authoritative for continuation: {project_label}.")
            if project_manifest.validation_command:
                lines.append(f"- Preserve the manifest validation command unless the user explicitly replaces it: {project_manifest.validation_command}.")
        if workspace_family and workspace_family != manifest_family:
            lines.append(f"- Workspace files currently look like {self._family_label(workspace_family)}; prefer extending those files over scaffolding beside them.")

        if target_family == "native-cpp":
            lines.extend(
                [
                    "- Native/C++ guardrail: do not create package.json, index.html, styles.css, app.js, app/*.tsx, Next/Vite/Tailwind config, or static website files unless the latest user explicitly asks to convert this native project to web.",
                    "- Native/C++ required surface: edit or create C/C++ headers/source plus CMakeLists.txt, .sln/.vcxproj, build.py, or MSBuild/CMake validation as appropriate.",
                    "- Native/C++ continuation rule: preserve DLL/EXE/driver/console intent from the manifest or latest prompt and repair/build that artifact directly.",
                ]
            )
            if "dll" in (artifact_label or "").lower() or "library" in (artifact_label or "").lower():
                lines.append("- DLL/shared-library guardrail: include library source/header changes and a host-loader, smoke harness, or build validation path when creating or repairing the project.")
            if "driver" in (artifact_label or "").lower():
                lines.append("- Driver guardrail: keep driver and user-mode controller/build surfaces distinct and validate with Windows-native build commands when available.")
        elif target_family == "desktop":
            lines.extend(
                [
                    "- Desktop guardrail: a desktop app can use Electron/Tauri/WPF/WinForms/Tkinter/ImGui, but it must include a packaged desktop host surface.",
                    "- Desktop guardrail: static-only index.html/styles.css/app.js output is a failed answer for a desktop request.",
                ]
            )
        elif target_family == "web":
            lines.append("- Web/frontend guardrail: keep the implementation browser/web-focused and include real UI, styling, and validation for the detected framework.")
        elif target_family in {"python", "dotnet", "rust", "go"}:
            lines.append(f"- {self._family_label(target_family)} guardrail: stay in this language/runtime and include stack-native source, manifest, docs, and validation.")

        if dependency_profile is not None:
            if dependency_profile.validation_commands:
                lines.append(f"- Known validation commands for this mission: {', '.join(dependency_profile.validation_commands[:5])}.")
            if dependency_profile.entry_points:
                lines.append(f"- Existing entry points to prefer: {', '.join(dependency_profile.entry_points[:6])}.")

        return "\n".join(lines)

    def _request_stack_family(self, message: str) -> str:
        if self._request_mentions_cpp_project(message):
            return "native-cpp"
        if self._request_mentions_desktop_project(message):
            return "desktop"
        if self._request_mentions_python_app_project(message):
            return "python"
        lower = self._message_without_explicit_paths(message).lower()
        if any(term in lower for term in ("c#", "dotnet", ".net", "wpf", "winforms")):
            return "dotnet"
        if "rust" in lower or "cargo" in lower:
            return "rust"
        if "golang" in lower or re.search(r"\bgo\b", lower):
            return "go"
        if self._request_mentions_web_project(message):
            return "web"
        return ""

    def _artifact_label_for_request_or_manifest(
        self,
        message: str,
        manifest: WorkspaceProjectManifest | None,
    ) -> str:
        mission = manifest.mission_contract if manifest is not None and isinstance(manifest.mission_contract, dict) else {}
        manifest_artifact = str(mission.get("artifact_type") or "").strip()
        if manifest_artifact:
            return manifest_artifact

        lower = self._message_without_explicit_paths(message).lower()
        if any(term in lower for term in ("kernel driver", "driver")):
            return "kernel driver"
        if any(term in lower for term in ("dll", "shared library", "dynamic library", "plugin library")):
            return "dll/shared library"
        if any(term in lower for term in ("console app", "console project", "cli", "command line", "command-line")):
            return "console/CLI app"
        if any(term in lower for term in ("desktop app", "desktop application", "gui app", "imgui", "wpf", "winforms")):
            return "desktop GUI app"
        if any(term in lower for term in ("website", "web site", "web app", "frontend", "landing")):
            return "website/web app"
        if any(term in lower for term in ("api", "backend", "service")):
            return "backend service/API"
        return ""

    def _full_build_contract_context(
        self,
        request: AgentRequest,
        mode: ModeName,
        task_plan: TaskPlan,
        files: list[WorkspaceFile],
        dependency_profile: WorkspaceDependencyProfile | None,
    ) -> str:
        if not self._turn_expects_file_work(request, mode, task_plan):
            return "- This is not a file-build turn; answer directly unless the user asks to edit files."

        lower = request.message.lower()
        full_build = any(
            term in lower
            for term in (
                "full",
                "complete",
                "finish",
                "build out",
                "from scratch",
                "single prompt",
                "entire",
                "whole",
                "production",
            )
        )
        workspace_empty = not files
        stack_bits: list[str] = []
        if dependency_profile is not None:
            stack_bits.extend(dependency_profile.frameworks[:4])
            stack_bits.extend(dependency_profile.languages[:4])
            stack_bits.extend(dependency_profile.package_managers[:3])
        stack = ", ".join(dict.fromkeys(bit for bit in stack_bits if bit)) or "infer from the request and workspace"

        lines = [
            "- Treat the latest User request as the authoritative task contract: target path, language/stack, artifact type, and requested validation override older chat history or stale project notes.",
            "- When the latest request only says continue, build, repair, or validate, preserve the saved workspace manifest stack and do not migrate the project type.",
            "- Return concrete complete-file changes in the JSON `changes` array; do not only describe what should be built.",
            "- Use paths relative to the active workspace and keep every generated path inside that workspace.",
            "- If an existing stack is detected, extend that stack instead of creating an unrelated starter beside it.",
            "- Honor Project instruction files from the prompt context as the active todo/roadmap, even when the user only says continue.",
            f"- Detected/target stack: {stack}.",
            "- Include or update validation/build scripts when the stack needs them.",
            "- On Windows-native or C++ CMake projects, prefer `build.py` plus `python build.py` over shell-only `.sh` validation.",
            "- Include docs or run instructions when creating a new runnable project.",
        ]
        if full_build or workspace_empty or task_plan.intent == "implementation":
            lines.extend(
                [
                    "- Build a complete usable first version, not a placeholder or one-file sketch.",
                    "- Cover the main entry point, reusable components/modules, styling/configuration, data/content, and smoke validation where appropriate.",
                    "- Prefer one coherent project-wide patch set over several tiny continuation-only edits.",
                    "- If this is a website/app request, include real sections/screens, responsive layout, domain-specific copy, and meaningful interactions.",
                    "- If this is a CLI/service/native/database request, include source, manifest/build files, usage docs, and at least one smoke test or validation path.",
                ]
            )
        if dependency_profile is not None and dependency_profile.validation_commands:
            lines.append(f"- Known validation commands: {', '.join(dependency_profile.validation_commands[:5])}.")
        if dependency_profile is not None and dependency_profile.install_commands:
            lines.append(f"- Known install commands: {', '.join(dependency_profile.install_commands[:3])}.")
        return "\n".join(lines)

    def _route_preview_recommendations(
        self,
        *,
        task_plan: TaskPlan,
        model_execution_plan: ModelExecutionPlan,
        workspace_file_count: int,
        registry_router_enabled: bool,
        project_manifest: WorkspaceProjectManifest | None = None,
        instruction_files: list[WorkspaceInstructionFile] | None = None,
    ) -> list[str]:
        recommendations: list[str] = []
        routing = task_plan.routing
        if routing is None:
            return ["No routing decision was available; Aegis would fall back to deterministic local handling."]

        if project_manifest is not None:
            project_label = project_manifest.title or project_manifest.project_name or "the active workspace"
            stack_label = " / ".join(
                item
                for item in (
                    project_manifest.framework or project_manifest.preset_label,
                    project_manifest.language,
                )
                if item
            )
            if stack_label:
                recommendations.append(
                    f"Workspace manifest detected: {project_label} is a {stack_label} project, so routing and context should stay stack-aware."
                )
            else:
                recommendations.append(
                    f"Workspace manifest detected for {project_label}; routing should use its scaffold metadata before guessing."
                )
            if project_manifest.validation_command:
                recommendations.append(
                    f"Manifest validation command is available for validation-aware work: {project_manifest.validation_command}."
                )
        if instruction_files:
            names = ", ".join(item.path for item in instruction_files[:4])
            open_count = sum(item.pending_count for item in instruction_files[:4])
            if open_count:
                recommendations.append(
                    f"Project instruction files detected for autopilot continuity: {names} ({open_count} open item(s))."
                )
            elif self._instruction_files_have_open_autopilot_work(instruction_files):
                recommendations.append(
                    f"Project guidance files detected for autopilot continuity: {names}."
                )
            else:
                recommendations.append(
                    f"Project instruction files detected but tracked checklist items are complete: {names}. Aegis will not force autopilot."
                )
        route_profile = task_plan.route_profile if isinstance(task_plan.route_profile, dict) else {}
        if route_profile:
            profile_label = str(route_profile.get("label") or route_profile.get("id") or "workspace").strip()
            category = str(route_profile.get("category") or "").strip()
            preferred_roles = route_profile.get("preferred_roles")
            role_text = ""
            if isinstance(preferred_roles, list):
                cleaned_roles = [str(item).strip() for item in preferred_roles if str(item).strip()]
                if cleaned_roles:
                    role_text = f" Preferred roles: {', '.join(cleaned_roles[:4])}."
            recommendations.append(
                f"Route profile active: {profile_label}{f' ({category})' if category else ''}.{role_text}"
            )

        recommendations.append(
            f"Prompt classified as {task_plan.intent}; routing role is {routing.task_role} with {routing.privacy_mode} privacy."
        )
        if routing.task_role == "chat":
            recommendations.append("This prompt can be answered as normal chat and should not require file changes.")
        if routing.requires_workspace and workspace_file_count == 0:
            recommendations.append("This route expects workspace context, but no workspace files were found.")
        if not registry_router_enabled:
            recommendations.append("The registry router is not marked enabled; apply benchmark winners or enable routing policies.")

        primary = model_execution_plan.primary
        if primary is None:
            recommendations.append("No model attempt could be planned for this prompt.")
            return recommendations

        model_label = primary.model or primary.provider_label or primary.provider_id or "unresolved model"
        recommendations.append(f"Primary route: {primary.role} -> {model_label}.")
        metadata = primary.metadata if isinstance(primary.metadata, dict) else {}
        if metadata.get("registry_resolved") is False:
            recommendations.append("The primary route did not resolve to a configured provider; add or enable a provider for this role.")
        registry_primary = str(metadata.get("registry_role_primary_model") or "").strip()
        if registry_primary:
            recommendations.append(f"Registry role preference is active: {registry_primary}.")
        benchmark_suite = str(metadata.get("benchmark_suite") or "").strip()
        benchmark_score = metadata.get("benchmark_suite_score")
        if benchmark_suite and benchmark_score is not None:
            try:
                score_text = f"{float(benchmark_score):.0%}"
            except (TypeError, ValueError):
                score_text = str(benchmark_score)
            recommendations.append(f"Benchmark ranking contributed to this route using the {benchmark_suite} suite at {score_text}.")
        if metadata.get("route_health_cooldown"):
            recommendations.append("Route health cooldown is active for this provider; Aegis should prefer a fallback until health recovers.")
        elif float(metadata.get("route_health_penalty") or 0.0) > 0:
            recommendations.append(str(metadata.get("route_health_recommendation") or "Recent route health reduced this provider's ranking."))
        return recommendations

    def _normalize_context_paths(self, paths: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for raw_path in paths:
            candidate = str(raw_path).strip().strip("`'\"").replace("\\", "/")
            candidate = re.sub(r"^@+", "", candidate)
            candidate = re.sub(r"^\./+", "", candidate)
            if not candidate or candidate.startswith("/") or re.match(r"^[A-Za-z]:/", candidate):
                continue

            parts = [part for part in candidate.split("/") if part]
            if not parts or any(part in {".", ".."} for part in parts):
                continue

            safe_path = "/".join(parts)
            if safe_path in seen:
                continue
            seen.add(safe_path)
            normalized.append(safe_path)

        return normalized

    def _select_context_files(
        self,
        workspace_root: Path,
        files: list[WorkspaceFile],
        query: str,
        *,
        limit: int = 10,
        context_paths: list[str] | None = None,
    ) -> list[WorkspaceFile]:
        if not files:
            return []

        file_lookup = {item.path: item for item in files}
        selected: list[WorkspaceFile] = []
        seen: set[str] = set()

        def add(path: str) -> None:
            item = file_lookup.get(path)
            if not item or item.path in seen or item.kind != "text":
                return
            seen.add(item.path)
            selected.append(item)

        for path in self._normalize_context_paths(context_paths or []):
            add(path)
            if len(selected) >= limit:
                return selected

        intelligence = self.store.project_intelligence(project_root=workspace_root)
        if intelligence is not None:
            for path in self._project_intelligence_context_paths(intelligence, query):
                add(path)
                if len(selected) >= limit:
                    return selected

        indexer = ProjectIndexer()
        indexer.build_from_workspace(workspace_root, files)
        ranked = indexer.find_relevant_files(query, max_results=max(limit * 2, 12))

        for path in (
            "README.md",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "src/App.tsx",
            "backend/aegis_ai/main.py",
        ):
            add(path)
            if len(selected) >= limit:
                return selected

        for entry in ranked:
            add(entry.path)
            if len(selected) >= limit:
                return selected

        for item in files:
            add(item.path)
            if len(selected) >= limit:
                break

        return selected

    def _project_intelligence_context_paths(self, intelligence: ProjectIntelligenceSnapshot, query: str) -> list[str]:
        query_terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", query or "")
            if token.strip()
        }

        def score(item) -> float:
            text = " ".join([item.path, " ".join(item.reasons)]).lower()
            overlap = sum(1 for term in query_terms if term in text)
            return float(item.score or 0.0) + overlap * 8.0

        selected: list[str] = []
        seen: set[str] = set()
        for path in [
            *intelligence.profile.main_entry_files,
            *[item.path for item in sorted(intelligence.file_importance, key=lambda entry: (-score(entry), entry.path))],
            *intelligence.profile.risk_sensitive_files,
        ]:
            normalized = str(path or "").strip().replace("\\", "/")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            selected.append(normalized)
            if len(selected) >= 40:
                break
        return selected

    def _workspace_file_line(self, item: WorkspaceFile) -> str:
        bits = [item.kind, f"{item.size} bytes"]
        if bool(getattr(item, "is_large", False)):
            line_count = int(getattr(item, "estimated_lines", 0) or 0)
            if line_count:
                bits.append(f"~{line_count} lines")
            strategy = str(getattr(item, "large_file_strategy", "") or "").strip()
            if strategy:
                bits.append(strategy)
            else:
                bits.append("large-file chunk mode")
        return f"- {item.path} ({', '.join(bits)})"

    def _large_file_context(self, workspace_root: Path, files: list[WorkspaceFile]) -> str:
        inventory = self.workspace.large_file_inventory(workspace_root, files)
        if not inventory:
            return ""
        lines = [
            "- Large-file mode is active. Use summaries and line slices; avoid whole-file rewrites.",
        ]
        for item in inventory[:12]:
            lines.append(
                "- {path} ({size} bytes, ~{lines} lines): {strategy}".format(
                    path=item.get("path", ""),
                    size=item.get("size", 0),
                    lines=item.get("estimated_lines", 0),
                    strategy=item.get("strategy", "chunked inspection"),
                )
            )
        if len(inventory) > 12:
            lines.append(f"- {len(inventory) - 12} more large file(s) omitted from the prompt inventory.")
        return "\n".join(lines)

    def _primary_context_window(self, model_execution_plan: Any) -> int | None:
        primary = getattr(model_execution_plan, "primary", None)
        if primary is None:
            return None
        value = primary.metadata.get("context_window") if isinstance(primary.metadata, dict) else None
        try:
            context_window = int(value)
        except (TypeError, ValueError):
            return None
        return context_window if context_window > 0 else None

    def _context_budget_prompt(self, context_budget: ContextBudgetResult | None) -> str:
        if context_budget is None:
            return "- Strategy: default workspace context\n- Budget: configured backend defaults"
        payload = context_budget.to_event_payload()
        return "\n".join(
            [
                f"- Strategy: {payload['strategy']}",
                f"- Privacy mode: {payload['privacy_mode']}",
                f"- Estimated context tokens: {payload['estimated_context_tokens']} / {payload['max_context_tokens']}",
                f"- Reserved response tokens: {payload['reserve_response_tokens']}",
                f"- Selected files: {payload['selected_file_count']} of max {payload['max_context_files']}",
                f"- Selected memory: {payload['selected_memory_count']} repair, {payload['selected_project_memory_count']} project",
            ]
        )

    def _direct_chat_system_prompt(self) -> str:
        return """
You are Auralith Prime, the assistant identity inside Auralith OS. You run on Aegis Core, the private self-hosted runtime.
Answer the user's normal question directly in natural language.
Do not return JSON. Do not claim that files were edited, created, applied, validated, or inspected unless the context explicitly shows that happened.
If code is useful, provide a concise snippet in Markdown and explain where it would fit, but keep this turn read-only.
If the user asks for a risky action, explain safe boundaries and ask for the missing authorization or project context.
""".strip()

    def _system_prompt(self) -> str:
        return """
You are Auralith Prime, the assistant identity inside Auralith OS. You run on Aegis Core, the private self-hosted runtime.
You MUST return ONLY valid JSON in this exact format, with no other text:

{
  "reply": "short explanation for the user",
  "plan": ["step 1", "step 2"],
  "changes": [
    {"action": "create|update|append|delete", "path": "relative/path", "summary": "why", "content": "complete file text or null"}
  ],
  "commands": [
    {"command": "npm run build", "reason": "why this validates the work"}
  ]
}

For simple code requests like "create a batch script", use:
- "reply": brief description of the prepared file change; do not claim it has been created, written, or applied
- "plan": ["Create the requested file"]
- "changes": single change object with action="create", appropriate path, and complete file content
- "commands": [] (empty array)

For normal questions, explanations, brainstorming, or requests that do not need file edits:
- answer directly in "reply"
- use "changes": []
- use "commands": []
- do not claim file changes are missing

Do not return any other JSON structure. Do not wrap the JSON in markdown. Markdown is allowed inside the "reply" string when it helps the user read code or lists.

Full-build behavior:
- When the user asks to build, complete, finish, ship, or create a full app/site/tool/service/driver/library/database project, return a real multi-file implementation.
- Do not return only a plan, checklist, or tiny placeholder unless the request is explicitly read-only.
- For existing projects, modify the existing stack-native files instead of dropping unrelated starter files into the root.
- For frontend apps, include screen structure, components, styling, responsive behavior, realistic domain content, and build scripts/config when missing.
- For backend, CLI, desktop, native, database, and systems projects, include source, manifests/build files, usage docs, and validation or smoke-test files when practical.
- If validation/build errors are known in the prompt, repair those first and include the exact files needed for the fix.

Large-file behavior:
- If the workspace contains million-byte or 100k+ line files, treat them as chunked assets.
- Use the large file inventory and sampled snippets to choose targeted symbols or regions; do not invent unseen middle-file content.
- Avoid replacing a giant file wholesale. Prefer small focused edits, helper modules, or clearly scoped integration files.
- If a giant-file change needs lines not present in context, state the exact file and line slice needed in the plan before editing.
- For newly generated giant files, write the file in coherent chunks with create followed by append actions across passes instead of one massive JSON payload.
""".strip()

    def _parse_model_payload(
        self,
        payload: dict[str, Any],
        *,
        request_message: str = "",
        mode: ModeName = "chat",
    ) -> AgentDraft:
        reply = self._payload_reply(payload)
        plan = self._payload_plan(payload)
        expects_file_changes = self._request_expects_file_changes(request_message, mode)
        warnings: list[str] = []
        changes: list[FileChange] = []

        # Handle alternative model response formats
        if "code" in payload:
            # Model returned {"code": "...", "language": "..."} or a similar snippet format.
            code_content = str(payload.get("code", "")).strip()
            language = self._payload_code_language(payload)

            if code_content:
                # Clean up the code content - remove language prefix if present.
                if language and code_content.startswith(language + "\n"):
                    code_content = code_content[len(language) + 1:]
                elif language and code_content.startswith(language):
                    code_content = code_content[len(language):].strip()

                explicit_path = self._payload_code_path(payload)
                if explicit_path or expects_file_changes:
                    file_path = explicit_path or self._default_code_path(language)
                    language_label = language or "code"
                    changes.append(FileChange(
                        action="create",
                        path=file_path,
                        summary=f"Create a {language_label} script",
                        content=code_content
                    ))
                    if not reply:
                        reply = f"Prepared a {language_label} script file for review."
                    if not plan:
                        plan = [f"Create {file_path}"]
                elif not reply:
                    fence = language or "text"
                    reply = f"```{fence}\n{code_content}\n```"

        raw_changes = payload.get("changes", [])
        if isinstance(raw_changes, list):
            for raw in raw_changes:
                if not isinstance(raw, dict):
                    if expects_file_changes:
                        warnings.append("Skipped a model change because it was not an object.")
                    continue
                try:
                    changes.append(FileChange.model_validate(raw))
                except ValidationError as exc:
                    if expects_file_changes:
                        warnings.append(f"Skipped invalid model change: {exc.errors()[0]['msg']}")
        else:
            if expects_file_changes:
                warnings.append("Model returned changes in the wrong format.")

        proposed_commands: list[dict[str, str]] = []
        raw_commands = payload.get("commands", [])
        if isinstance(raw_commands, list):
            for raw in raw_commands:
                if isinstance(raw, dict) and raw.get("command"):
                    proposed_commands.append(
                        {
                            "command": str(raw.get("command", "")),
                            "reason": str(raw.get("reason", "")),
                        }
                    )

        if not reply:
            if changes:
                reply = f"Prepared {len(changes)} file change(s) for the selected workspace."
            elif proposed_commands:
                reply = "Prepared command suggestions for the selected workspace."
            else:
                reply = "Aegis did not receive actionable file changes from the model."

        return AgentDraft(
            reply=reply,
            plan=plan,
            changes=changes,
            warnings=warnings,
            proposed_commands=proposed_commands,
        )

    def _payload_reply(self, payload: dict[str, Any]) -> str:
        for key in ("reply", "answer", "response", "message", "content", "text", "output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested = self._payload_reply(value)
                if nested:
                    return nested
            if isinstance(value, list):
                parts: list[str] = []
                for item in value:
                    if isinstance(item, str) and item.strip():
                        parts.append(item.strip())
                    elif isinstance(item, dict):
                        nested = self._payload_reply(item)
                        if nested:
                            parts.append(nested)
                if parts:
                    return "\n".join(parts).strip()
        return ""

    def _payload_plan(self, payload: dict[str, Any]) -> list[str]:
        raw_plan = payload.get("plan", [])
        if isinstance(raw_plan, list):
            return [str(item).strip() for item in raw_plan if str(item).strip()]
        if isinstance(raw_plan, str):
            return [line.strip(" -\t") for line in raw_plan.splitlines() if line.strip(" -\t")]
        return []

    def _payload_code_language(self, payload: dict[str, Any]) -> str:
        for key in ("language", "lang", "file_type", "syntax"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return ""

    def _payload_code_path(self, payload: dict[str, Any]) -> str:
        for key in ("path", "filename", "file_path", "file"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().replace("\\", "/")
            if isinstance(value, dict):
                nested = value.get("path") or value.get("filename")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip().replace("\\", "/")
        return ""

    def _default_code_path(self, language: str) -> str:
        normalized = "".join(ch for ch in language.lower() if ch.isascii() and (ch.isalnum() or ch in {"_", "-"}))
        language_paths = {
            "batch": "hello.bat",
            "bat": "hello.bat",
            "cmd": "hello.cmd",
            "powershell": "script.ps1",
            "ps1": "script.ps1",
            "python": "script.py",
            "py": "script.py",
            "javascript": "script.js",
            "js": "script.js",
            "typescript": "script.ts",
            "ts": "script.ts",
            "html": "index.html",
            "css": "style.css",
            "cpp": "main.cpp",
            "cxx": "main.cpp",
            "c": "main.c",
            "csharp": "Program.cs",
            "cs": "Program.cs",
            "go": "main.go",
            "rust": "main.rs",
            "rs": "main.rs",
        }
        if normalized in language_paths:
            return language_paths[normalized]
        if normalized:
            return f"script.{normalized[:16]}"
        return "snippet.txt"

    def _request_expects_file_changes(self, message: str, mode: ModeName) -> bool:
        if prompt_requests_creative_media(message):
            return False
        lower = message.lower()
        action_terms = (
            "create",
            "build",
            "make",
            "generate",
            "scaffold",
            "write",
            "add",
            "implement",
            "complete",
            "finish",
            "build out",
            "flesh out",
            "develop",
            "ship",
            "set up",
            "setup",
            "refine",
            "improve",
            "improving",
            "optimize",
            "optimizing",
            "repair",
            "debug",
            "fix",
            "fixing",
            "work on",
            "clean up",
            "cleanup",
            "polish",
            "modernize",
            "enhance",
        )
        artifact_terms = (
            "website",
            "web site",
            "app",
            "page",
            "file",
            "project",
            "component",
            "dashboard",
            "api",
            "script",
            "template",
            "tool",
            "folder",
            "database",
            "migration",
            "schema",
            "kernel",
            "driver",
            "dll",
            "exe",
            "executable",
            "library",
            "service",
            "bot",
            "cli",
            "extension",
            "module",
            "package",
        )
        if mode == "review" and not any(term in lower for term in ("create", "build", "make", "generate", "scaffold")):
            return False
        return any(term in lower for term in action_terms) and any(term in lower for term in artifact_terms)

    def _request_asks_for_validation(self, message: str) -> bool:
        return prompt_requests_execution_validation(message)

    def _estimate_text_tokens(self, text: str) -> int:
        cleaned = text.strip()
        if not cleaned:
            return 0
        return max(1, (len(cleaned) + 3) // 4)

    def _record_command_proposals(self, draft: AgentDraft, emit) -> None:
        for command in draft.proposed_commands:
            emit(
                "command-proposal",
                "Model proposed a command",
                status="warning",
                detail=command.get("reason", ""),
                payload={"command": command.get("command", "")},
            )

    def _validation_override_recipe(self, request: AgentRequest) -> ValidationRecipe | None:
        command = request.validation_command_override.strip()
        if not command:
            return None
        return ValidationRecipe(
            command=command,
            label=request.validation_label_override.strip() or "Requested validation command",
            source="request",
            notes=request.validation_notes_override.strip()
            or "Temporary validation command supplied for this repair turn.",
        )

    def _turn_validation_override_recipe(
        self,
        request: AgentRequest,
        draft: AgentDraft,
        workspace_root: Path,
    ) -> ValidationRecipe | None:
        request_recipe = self._validation_override_recipe(request)
        if request_recipe is not None:
            return request_recipe
        if self.validation.load_profile(workspace_root) is not None:
            return None
        return self._draft_validation_override_recipe(draft)

    def _draft_validation_override_recipe(self, draft: AgentDraft) -> ValidationRecipe | None:
        for item in draft.proposed_commands:
            command = str(item.get("command") or "").strip()
            if not command:
                continue
            reason = str(item.get("reason") or "").strip()
            if not self._is_draft_validation_command(command, reason):
                continue
            return ValidationRecipe(
                command=command,
                label="Draft validation command",
                source="draft-proposal",
                notes=reason or "One-turn validation command proposed by the accepted agent draft.",
            )
        return None

    def _is_draft_validation_command(self, command: str, reason: str = "") -> bool:
        normalized = " ".join(command.strip().lower().split())
        reason_normalized = " ".join(reason.strip().lower().split())
        if not normalized:
            return False

        if normalized.startswith(("powershell ", "powershell.exe ", "pwsh ", "pwsh.exe ")) and (
            normalized not in POWERSHELL_BUILD_COMMAND_MARKERS
        ):
            return False
        if is_blocked_validation_launcher_command(command):
            return False

        blocked_prefixes = (
            "npm install",
            "npm i",
            "pnpm install",
            "yarn install",
            "bun install",
            "pip install",
            "python -m pip install",
            "py -m pip install",
            "cargo fetch",
            "git clean",
            "git reset",
            "rm ",
            "del ",
            "erase ",
            "rmdir ",
            "remove-item",
        )
        if normalized.startswith(blocked_prefixes):
            return False

        validation_terms = (
            "build",
            "compile",
            "test",
            "typecheck",
            "type-check",
            "lint",
            "validate",
            "validation",
            "verify",
            "smoke",
            "run",
            "launch",
        )
        if any(term in reason_normalized for term in validation_terms):
            return True

        command_markers = (
            "python build.py",
            "py build.py",
            *POWERSHELL_BUILD_COMMAND_MARKERS,
            "python -m pytest",
            "py -m pytest",
            "pytest",
            "npm run build",
            "npm run test",
            "npm test",
            "npm run typecheck",
            "npm run type-check",
            "npm run lint",
            "npm run validate",
            "pnpm run build",
            "pnpm test",
            "yarn build",
            "yarn test",
            "bun run build",
            "bun test",
            "node build.js",
            "cargo build",
            "cargo test",
            "cargo check",
            "go build",
            "go test",
            "dotnet build",
            "dotnet test",
            "msbuild",
            "devenv",
            "cmake ",
            "ctest",
            "make",
            "ninja",
            "gradle",
            "gradlew",
            "mvn ",
        )
        return any(normalized.startswith(marker) for marker in command_markers)

    def _run_validation(
        self,
        workspace_root: Path,
        emit,
        *,
        manual: bool = False,
        override_recipe: ValidationRecipe | None = None,
    ) -> CommandRun | None:
        profile_snapshot = self.validation.profile_snapshot(workspace_root)
        recipe = override_recipe or profile_snapshot.profile
        if not recipe:
            emit(
                "validation",
                "No validation command detected",
                status="warning",
                detail="Aegis could not infer a build, test, or type-check command for this workspace.",
                payload={"suggestions": [item.model_dump() for item in profile_snapshot.suggestions[:5]]},
            )
            return None

        emit(
            "validation",
            "Validation recipe selected",
            detail=f"{recipe.command} ({recipe.source or 'detected'})",
            payload={"recipe": recipe.model_dump(), "suggestions": [item.model_dump() for item in profile_snapshot.suggestions[:5]]},
        )

        allowed_to_run, approval_reason = self.approvals.should_auto_run_command(recipe.command, manual=manual)
        if not allowed_to_run:
            run = CommandRun(
                command=recipe.command,
                cwd=str(workspace_root),
                allowed=False,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                reason=approval_reason,
                category="permission",
                summary=approval_reason,
            )
            build_log_path = self._persist_validation_run(workspace_root, run, recipe=recipe)
            payload = run.model_dump()
            if build_log_path:
                payload["build_log_path"] = build_log_path
            emit(
                "approval",
                "Validation requires manual confirmation",
                status="warning",
                detail=approval_reason,
                payload=payload,
            )
            return run

        result = self.commands.run(recipe.command, workspace_root, sandbox_profile=self.approvals.sandbox)
        run = self._command_run(result, recipe=recipe)
        if self._validation_ok(run) and self._should_remember_validation_recipe(override_recipe):
            learned_recipe = self.validation.remember_success(workspace_root, recipe)
            if learned_recipe.source == "learned":
                emit(
                    "validation",
                    "Validation command learned",
                    detail=learned_recipe.command,
                    payload={"recipe": learned_recipe.model_dump()},
                )
        build_log_path = self._persist_validation_run(workspace_root, run, recipe=recipe)
        payload = run.model_dump()
        if build_log_path:
            payload["build_log_path"] = build_log_path
        emit(
            "command",
            "Validation command executed",
            status="ok" if run.exit_code == 0 else "error",
            detail=run.summary or result.reason,
            payload=payload,
        )
        return run

    def _should_remember_validation_recipe(self, override_recipe: ValidationRecipe | None) -> bool:
        if override_recipe is None:
            return True
        return override_recipe.source == "draft-proposal"

    def _persist_validation_run(
        self,
        workspace_root: Path,
        run: CommandRun,
        *,
        recipe: ValidationRecipe | None,
        kind: str = "validation",
    ) -> str:
        try:
            build_log_path = self._write_agent_build_log(workspace_root, run, recipe=recipe, kind=kind)
            self._append_agent_command_history(
                workspace_root,
                run,
                recipe=recipe,
                build_log_path=build_log_path,
                kind=kind,
            )
            if not self._validation_ok(run):
                self._append_agent_known_error(workspace_root, run, build_log_path=build_log_path, kind=kind)
            return build_log_path
        except OSError:
            return ""

    def _write_agent_build_log(
        self,
        workspace_root: Path,
        run: CommandRun,
        *,
        recipe: ValidationRecipe | None,
        kind: str = "validation",
    ) -> str:
        created_at = utc_now()
        safe_stamp = re.sub(r"[^0-9A-Za-z_-]+", "-", created_at).strip("-")
        safe_stamp = safe_stamp or str(int(time.time()))
        logs_dir = workspace_root / ".aegis" / "build_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        safe_kind = re.sub(r"[^0-9A-Za-z_-]+", "-", kind).strip("-") or "validation"
        path = logs_dir / f"{safe_stamp}-agent-{safe_kind}.md"
        status = "passed" if self._validation_ok(run) else "failed"
        if not run.allowed:
            status = "blocked"
        elif run.timed_out:
            status = "timed_out"
        stdout = self._fenced_log_text(run.stdout)
        stderr = self._fenced_log_text(run.stderr)
        command_steps = self._validation_steps_log(run.steps)
        diagnostics = self._validation_diagnostics_log(run.diagnostics)
        content = f"""# Aegis Build Log

- Created: {created_at}
- Source: agent {kind}
- Workspace: {workspace_root}
- Command: `{run.command}`
- Status: {status}
- Exit code: {run.exit_code if run.exit_code is not None else "(none)"}
- Category: {run.category or "unknown"}
- Summary: {run.summary or run.reason or "(none)"}
- Validation source: {(recipe.source if recipe else "") or "detected"}
- Failed step: {self._failed_step_display(run.model_dump()) or "(none)"}

## Command Steps

{command_steps}

## Diagnostics

{diagnostics}

## Stdout

```text
{stdout or "(empty)"}
```

## Stderr

```text
{stderr or "(empty)"}
```
"""
        path.write_text(self._redact_project_status_text(content), encoding="utf-8")
        return self._display_workspace_relative_path(workspace_root, path)

    def _append_agent_command_history(
        self,
        workspace_root: Path,
        run: CommandRun,
        *,
        recipe: ValidationRecipe | None,
        build_log_path: str,
        kind: str = "validation",
    ) -> None:
        history = self._read_aegis_json(workspace_root, "command_history.json")
        commands = history.get("commands")
        if not isinstance(commands, list):
            commands = []
        commands.append(
            {
                "kind": kind,
                "command": run.command,
                "cwd": run.cwd,
                "status": "passed" if self._validation_ok(run) else "failed",
                "category": run.category or "unknown",
                "summary": run.summary or run.reason,
                "exit_code": run.exit_code,
                "timed_out": run.timed_out,
                "allowed": run.allowed,
                "steps": run.steps,
                "failed_step": run.failed_step,
                "failed_step_command": run.failed_step_command,
                "diagnostics": run.diagnostics,
                "source": (recipe.source if recipe else "") or "detected",
                "build_log_path": build_log_path,
                "created_at": utc_now(),
            }
        )
        history["schema"] = "aegis.command_history.v1"
        history["updated_at"] = utc_now()
        history["validation_command"] = run.command
        history["commands"] = commands[-80:]
        self._write_aegis_json(workspace_root, "command_history.json", history)

    def _append_agent_known_error(
        self,
        workspace_root: Path,
        run: CommandRun,
        *,
        build_log_path: str,
        kind: str = "validation",
    ) -> None:
        known = self._read_aegis_json(workspace_root, "known_errors.json")
        errors = known.get("errors")
        if not isinstance(errors, list):
            errors = []
        errors.append(
            {
                "signature": self._error_signature(run),
                "category": run.category or self._categorize_validation_failure(run),
                "kind": kind,
                "command": run.command,
                "summary": run.summary or run.reason,
                "exit_code": run.exit_code,
                "failed_step": run.failed_step,
                "failed_step_command": run.failed_step_command,
                "diagnostics": run.diagnostics,
                "output_excerpt": self._validation_output_excerpt(run, limit=1400),
                "build_log_path": build_log_path,
                "status": "open",
                "created_at": utc_now(),
            }
        )
        known["schema"] = "aegis.known_errors.v1"
        known["updated_at"] = utc_now()
        known["errors"] = errors[-60:]
        self._write_aegis_json(workspace_root, "known_errors.json", known)

    def _write_aegis_json(self, workspace_root: Path, filename: str, payload: dict[str, Any]) -> None:
        if "/" in filename or "\\" in filename:
            raise OSError("invalid .aegis filename")
        path = workspace_root / ".aegis" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _record_instruction_status(
        self,
        workspace_root: Path,
        instruction_files: list[WorkspaceInstructionFile],
        *,
        request_message: str,
        validation: CommandRun | None,
        completion_quality: CompletionQualityInfo,
        applied: list[str],
    ) -> dict[str, Any] | None:
        if not instruction_files:
            return None

        files: list[dict[str, Any]] = []
        for item in instruction_files[:12]:
            files.append(
                {
                    "path": item.path,
                    "title": item.title,
                    "kind": item.kind,
                    "score": item.score,
                    "open_items": item.pending_count,
                    "completed_items": item.completed_count,
                    "total_items": item.total_items,
                    "pending_items": [
                        self._status_text(pending, limit=220)
                        for pending in item.pending_items[:10]
                        if self._status_text(pending, limit=220)
                    ],
                    "summary": item.summary,
                }
            )

        open_items = sum(item.pending_count for item in instruction_files)
        completed_items = sum(item.completed_count for item in instruction_files)
        total_items = sum(item.total_items for item in instruction_files)
        first_pending = next(
            (
                pending
                for item in instruction_files
                for pending in item.pending_items
                if pending.strip()
            ),
            "",
        )
        if validation is None:
            validation_payload = {"status": "not_run", "command": "", "summary": ""}
        else:
            validation_payload = {
                "status": "passed" if self._validation_ok(validation) else "failed",
                "command": validation.command,
                "summary": validation.summary or validation.reason,
                "category": validation.category or self._categorize_validation_failure(validation),
                "exit_code": validation.exit_code,
            }

        next_actions = [
            self._status_text(action, limit=260)
            for action in completion_quality.next_actions[:6]
            if self._status_text(action, limit=260)
        ]
        recommendation = (
            f"Continue the next open instruction item: {self._status_text(first_pending, limit=220)}"
            if open_items and first_pending
            else "Continue the next open instruction item."
            if open_items
            else "All tracked instruction items are currently complete; summarize the validated state and propose the next milestone."
        )
        payload = {
            "schema": "aegis.instruction_status.v1",
            "updated_at": utc_now(),
            "source_message": self._status_text(request_message, limit=500),
            "instruction_file_count": len(files),
            "open_items": open_items,
            "completed_items": completed_items,
            "total_items": total_items,
            "files": files,
            "last_validation": validation_payload,
            "completion": {
                "status": completion_quality.status,
                "score": completion_quality.score,
                "should_continue": completion_quality.should_continue,
                "reasons": [
                    self._status_text(reason, limit=260)
                    for reason in completion_quality.reasons[:6]
                    if self._status_text(reason, limit=260)
                ],
                "next_actions": next_actions,
            },
            "applied": [self._status_text(path, limit=220) for path in applied[-40:]],
            "recommendation": recommendation,
        }
        self._write_aegis_json(workspace_root, "instruction_status.json", payload)
        return payload

    def _validation_output_excerpt(self, run: CommandRun, *, limit: int) -> str:
        text = "\n".join(part for part in (run.stderr, run.stdout, run.reason) if part).strip()
        if len(text) > limit:
            return text[:limit] + "\n... output truncated ..."
        return text

    def _extract_validation_diagnostics(self, result: CommandResult, *, limit: int = 12) -> list[dict[str, Any]]:
        return extract_validation_diagnostics(result, limit=limit)

    def _normalize_diagnostic_path(self, path: str) -> str:
        return validation_normalize_diagnostic_path(path)

    def _to_positive_int(self, value: str | int | None) -> int | None:
        return validation_to_positive_int(value)

    def _strip_ansi(self, text: str) -> str:
        return validation_strip_ansi(text)

    def _failed_step_parts_from_steps(self, steps: list[dict[str, Any]]) -> tuple[str, str]:
        return validation_failed_step_parts_from_steps(steps)

    def _failed_step_display(self, payload: dict[str, Any]) -> str:
        return validation_failed_step_display(payload)

    def _first_diagnostic_display(self, payload: dict[str, Any]) -> str:
        return validation_first_diagnostic_display(payload)

    def _first_diagnostic_brief(self, payload: dict[str, Any]) -> str:
        return validation_first_diagnostic_brief(payload)

    def _repair_target_from_validation(self, payload: dict[str, Any], *, validation_command: str = "") -> str:
        return validation_repair_target(payload, validation_command=validation_command)

    def _diagnostic_display(self, diagnostic: dict[str, Any]) -> str:
        return validation_diagnostic_display(diagnostic)

    def _diagnostic_brief(self, diagnostic: dict[str, Any]) -> str:
        return validation_diagnostic_brief(diagnostic)

    def _fenced_log_text(self, text: str) -> str:
        return validation_fenced_log_text(text)

    def _validation_steps_log(self, steps: list[dict[str, Any]]) -> str:
        return validation_steps_log(steps)

    def _validation_diagnostics_log(self, diagnostics: list[dict[str, Any]]) -> str:
        return validation_diagnostics_log(diagnostics)

    def _command_run(self, result: CommandResult, *, recipe=None) -> CommandRun:
        category = self._categorize_command_result(result, recipe=recipe)
        summary = self._summarize_command_result(result, category=category, recipe=recipe)
        failed_step, failed_step_command = self._failed_step_parts_from_steps(list(result.steps))
        diagnostics = self._extract_validation_diagnostics(result)
        return CommandRun(
            command=result.command,
            cwd=result.cwd,
            allowed=result.allowed,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            reason=result.reason,
            category=category,
            summary=summary,
            steps=list(result.steps),
            failed_step=failed_step,
            failed_step_command=failed_step_command,
            diagnostics=diagnostics,
        )

    def _validation_ok(self, validation: CommandRun) -> bool:
        return outcome_validation_ok(validation)

    def _verification_status(self, steps) -> str:
        if not steps or all(step.status == "planned" for step in steps):
            return "skipped"
        if any(step.status == "blocked" for step in steps):
            return "blocked"
        if any(step.status == "failed" and step.required for step in steps):
            return "failed"
        return "passed"

    def _error_signature(self, validation: CommandRun) -> str:
        return outcome_error_signature(validation)

    def _categorize_validation_failure(self, validation: CommandRun) -> str:
        return outcome_categorize_validation_failure(validation)

    def _categorize_command_result(self, result: CommandResult, *, recipe=None) -> str:
        return outcome_categorize_command_result(result, recipe=recipe)

    def _summarize_command_result(self, result: CommandResult, *, category: str, recipe=None) -> str:
        return outcome_summarize_command_result(result, category=category, recipe=recipe)

    def _repair_outcome(self, before: CommandRun, after: CommandRun | None) -> str:
        return outcome_repair_outcome(before, after)

    def _validation_score(self, validation: CommandRun) -> int:
        return outcome_validation_score(validation)

    def _memory_context(self, memory_hits: list[FixMemoryEntry]) -> str:
        return format_fix_memory_context(memory_hits)

    def _task_history_context(self, recent_tasks: list[TaskSummary]) -> str:
        return format_task_history_context(recent_tasks)

    def _project_memory_context(self, project_memory_hits: list[ProjectMemoryEntry]) -> str:
        return format_project_memory_context(project_memory_hits)

    def _project_intelligence_context(self, workspace_root: Path) -> str:
        intelligence = self.store.project_intelligence(project_root=workspace_root)
        return format_project_intelligence_context_for_workspace(intelligence, workspace_root)

    def _instruction_file_context(self, instruction_files: list[WorkspaceInstructionFile]) -> str:
        return format_instruction_file_context(instruction_files)

    def _project_status_context(self, workspace_root: Path) -> str:
        history = self._read_aegis_json(workspace_root, "command_history.json")
        known = self._read_aegis_json(workspace_root, "known_errors.json")
        instruction_status = self._read_aegis_json(workspace_root, "instruction_status.json")
        validation_plan = self._read_aegis_json(workspace_root, "validation_plan.json")
        readiness = self.workspace_readiness_snapshot(
            manifest=self.workspace.load_project_manifest(workspace_root),
            dependency_profile=self.workspace.inspect_dependency_profile(workspace_root),
            instruction_status=self.instruction_status_snapshot(workspace_root),
            validation_plan=self.validation_plan_snapshot(workspace_root),
            command_history=history,
        )
        raw_commands = history.get("commands") if isinstance(history, dict) else []
        raw_errors = known.get("errors") if isinstance(known, dict) else []
        raw_instruction_files = instruction_status.get("files") if isinstance(instruction_status, dict) else []
        raw_validation_steps = validation_plan.get("steps") if isinstance(validation_plan, dict) else []
        commands = [item for item in raw_commands if isinstance(item, dict)] if isinstance(raw_commands, list) else []
        errors = [item for item in raw_errors if isinstance(item, dict)] if isinstance(raw_errors, list) else []
        instruction_files = (
            [item for item in raw_instruction_files if isinstance(item, dict)]
            if isinstance(raw_instruction_files, list)
            else []
        )
        validation_steps = (
            [item for item in raw_validation_steps if isinstance(item, dict)]
            if isinstance(raw_validation_steps, list)
            else []
        )
        build_log_refs: list[str] = []
        lines: list[str] = []
        has_build_state = False
        has_instruction_state = False

        if readiness.status and readiness.status != "unconfigured":
            lines.append(f"Workspace readiness: {readiness.status} ({readiness.score}/100)")
            if readiness.summary:
                lines.append(f"- Readiness summary: {readiness.summary}")
            if readiness.next_action:
                lines.append(f"- Readiness next action: {readiness.next_action}")
            for blocker in readiness.blockers[:4]:
                blocker_text = self._status_text(blocker, limit=220)
                if blocker_text:
                    lines.append(f"- Readiness blocker: {blocker_text}")
            for signal in readiness.signals[:4]:
                signal_text = self._status_text(signal, limit=220)
                if signal_text:
                    lines.append(f"- Readiness signal: {signal_text}")
            has_instruction_state = readiness.status == "needs_work"
            has_build_state = readiness.status in {"needs_repair", "needs_validation", "ready"}

        intelligence_context = self._project_intelligence_context(workspace_root)
        if intelligence_context:
            lines.append(intelligence_context)
            has_build_state = True

        if instruction_files:
            has_instruction_state = True
            open_items = self._status_text(instruction_status.get("open_items"), default="0", limit=40)
            completed_items = self._status_text(instruction_status.get("completed_items"), default="0", limit=40)
            total_items = self._status_text(instruction_status.get("total_items"), default="0", limit=40)
            updated_at = self._status_text(instruction_status.get("updated_at"), limit=80)
            header = f"Instruction file status: {open_items} open / {completed_items} completed / {total_items} tracked"
            if updated_at:
                header += f" (updated {updated_at})"
            lines.append(header)

            last_validation = instruction_status.get("last_validation")
            if isinstance(last_validation, dict):
                validation_status = self._status_text(last_validation.get("status"), limit=40)
                validation_command = self._status_text(last_validation.get("command"), limit=220)
                validation_summary = self._status_text(last_validation.get("summary"), limit=260)
                if validation_status and validation_status != "not_run":
                    parts = [f"[{validation_status}]"]
                    if validation_command:
                        parts.append(validation_command)
                    if validation_summary:
                        parts.append(f"summary={validation_summary}")
                    lines.append("- Last validation: " + " | ".join(parts))

            completion = instruction_status.get("completion")
            if isinstance(completion, dict):
                completion_status = self._status_text(completion.get("status"), limit=40)
                completion_score = self._status_text(completion.get("score"), limit=40)
                should_continue = bool(completion.get("should_continue"))
                if completion_status:
                    suffix = "continue recommended" if should_continue else "ready"
                    score_text = f", score={completion_score}" if completion_score else ""
                    lines.append(f"- Completion status: {completion_status}{score_text}, {suffix}")

            for item in instruction_files[:5]:
                parts = [
                    self._status_text(item.get("path"), default="(instruction file)", limit=180),
                    f"open={self._status_text(item.get('open_items'), default='0', limit=40)}",
                    f"done={self._status_text(item.get('completed_items'), default='0', limit=40)}",
                ]
                summary = self._status_text(item.get("summary"), limit=220)
                if summary:
                    parts.append(summary)
                lines.append("- " + " | ".join(parts))
                pending_items = item.get("pending_items")
                if isinstance(pending_items, list):
                    pending_text = "; ".join(
                        self._status_text(pending, limit=180)
                        for pending in pending_items[:3]
                        if self._status_text(pending, limit=180)
                    )
                    if pending_text:
                        lines.append(f"  next: {pending_text}")

            recommendation = self._status_text(instruction_status.get("recommendation"), limit=320)
            if recommendation:
                lines.append(f"- Recommendation: {recommendation}")

        if validation_steps:
            has_build_state = True
            plan_command = self._status_text(validation_plan.get("validation_command"), limit=260)
            lines.append("Validation plan:")
            if plan_command:
                lines.append(f"- Command: {plan_command}")
            for item in validation_steps[:6]:
                parts = [
                    self._status_text(item.get("id"), default="validation-step", limit=80),
                    self._status_text(item.get("phase"), default="validation", limit=80),
                    self._status_text(item.get("command"), default="(command not captured)", limit=220),
                ]
                label = self._status_text(item.get("label"), limit=160)
                if label:
                    parts.append(f"label={label}")
                chain_index = self._status_text(item.get("chain_index"), limit=20)
                chain_total = self._status_text(item.get("chain_total"), limit=20)
                if chain_index and chain_total and chain_total != "1":
                    parts.append(f"chain={chain_index}/{chain_total}")
                lines.append("- " + " | ".join(parts))

            last_run = validation_plan.get("last_run")
            if isinstance(last_run, dict):
                log_ref = self._status_text(last_run.get("build_log_path"), limit=180)
                if log_ref:
                    build_log_refs.append(log_ref)
                parts = [
                    f"[{self._status_text(last_run.get('status'), default='unknown', limit=40)}]",
                    self._status_text(last_run.get("command"), default="(command not captured)", limit=220),
                ]
                failed_step = self._failed_step_display(last_run)
                if failed_step:
                    parts.append(f"failed_step={failed_step}")
                diagnostic = self._first_diagnostic_display(last_run)
                if diagnostic:
                    parts.append(f"diagnostic={diagnostic}")
                summary = self._status_text(last_run.get("summary"), limit=260)
                if summary:
                    parts.append(f"summary={summary}")
                if log_ref:
                    parts.append(f"log={self._safe_log_display_path(workspace_root, log_ref)}")
                lines.append("- Last validation-plan run: " + " | ".join(parts))

        if commands:
            has_build_state = True
            lines.append("Recent command history:")
            for item in reversed(commands[-4:]):
                log_ref = self._status_text(item.get("build_log_path"), limit=180)
                if log_ref:
                    build_log_refs.append(log_ref)
                parts = [
                    f"[{self._status_text(item.get('status'), default='unknown', limit=40)}]",
                    self._status_text(item.get("kind"), default="command", limit=80),
                    self._status_text(item.get("command"), default="(command not captured)", limit=220),
                ]
                exit_code = self._status_text(item.get("exit_code"), limit=40)
                if exit_code:
                    parts.append(f"exit={exit_code}")
                category = self._status_text(item.get("category"), limit=80)
                if category:
                    parts.append(f"category={category}")
                failed_step = self._failed_step_display(item)
                if failed_step:
                    parts.append(f"failed_step={failed_step}")
                diagnostic = self._first_diagnostic_display(item)
                if diagnostic:
                    parts.append(f"diagnostic={diagnostic}")
                summary = self._status_text(item.get("summary"), limit=260)
                if summary:
                    parts.append(f"summary={summary}")
                if log_ref:
                    parts.append(f"log={self._safe_log_display_path(workspace_root, log_ref)}")
                lines.append("- " + " | ".join(parts))

        open_errors = [
            item
            for item in errors
            if self._status_text(item.get("status"), default="open", limit=40).lower()
            not in {"closed", "resolved", "fixed", "ignored"}
        ]
        if open_errors:
            has_build_state = True
            lines.append("Open known errors:")
            for item in reversed(open_errors[-3:]):
                log_ref = self._status_text(item.get("build_log_path"), limit=180)
                if log_ref:
                    build_log_refs.append(log_ref)
                parts = [
                    f"[{self._status_text(item.get('category'), default='unknown', limit=80)}]",
                    self._status_text(item.get("command"), default="(command not captured)", limit=220),
                ]
                exit_code = self._status_text(item.get("exit_code"), limit=40)
                if exit_code:
                    parts.append(f"exit={exit_code}")
                failed_step = self._failed_step_display(item)
                if failed_step:
                    parts.append(f"failed_step={failed_step}")
                diagnostic = self._first_diagnostic_display(item)
                if diagnostic:
                    parts.append(f"diagnostic={diagnostic}")
                summary = self._status_text(item.get("summary"), limit=260)
                if summary:
                    parts.append(f"summary={summary}")
                if log_ref:
                    parts.append(f"log={self._safe_log_display_path(workspace_root, log_ref)}")
                lines.append("- " + " | ".join(parts))
                excerpt = self._status_text(item.get("output_excerpt"), limit=700)
                if excerpt:
                    lines.append(f"  excerpt: {excerpt}")

        latest_log = self._latest_project_build_log(workspace_root, build_log_refs)
        if latest_log is not None:
            display_path, log_path = latest_log
            excerpt = self._read_text_tail(log_path, max_chars=2_800)
            if excerpt:
                has_build_state = True
                lines.append(f"Latest build log excerpt ({display_path}):")
                lines.append(excerpt)

        if not lines:
            return ""

        if has_instruction_state:
            lines.append(
                "Instruction-state rule: Continue from the open instruction/TODO items before inventing unrelated work. When an item is genuinely complete and validated, update its checkbox in the source instruction file."
            )
        if has_build_state:
            lines.append(
                "Build-state rule: Continue from these captured failures before changing stacks or creating unrelated starter files. Prefer repairing the exact command/error or failed validation-plan step, then rerun validation."
            )
        return self._redact_project_status_text("\n".join(lines))[:7_000]

    def _read_aegis_json(self, workspace_root: Path, filename: str) -> dict[str, Any]:
        return project_read_aegis_json(workspace_root, filename)

    def _latest_project_build_log(self, workspace_root: Path, references: list[str]) -> tuple[str, Path] | None:
        return project_latest_build_log(workspace_root, references)

    def _safe_project_build_log_path(self, workspace_root: Path, value: Any) -> Path | None:
        return project_safe_build_log_path(workspace_root, value)

    def _safe_log_display_path(self, workspace_root: Path, value: Any) -> str:
        return project_safe_log_display_path(workspace_root, value)

    def _display_workspace_relative_path(self, workspace_root: Path, path: Path) -> str:
        return project_display_workspace_relative_path(workspace_root, path)

    def _read_text_tail(self, path: Path, *, max_chars: int) -> str:
        return project_read_text_tail(path, max_chars=max_chars)

    def _status_text(self, value: Any, *, default: str = "", limit: int = 500) -> str:
        return project_status_text(value, default=default, limit=limit)

    def _redact_project_status_text(self, text: str) -> str:
        return project_redact_status_text(text)

    def _merge_memory_hits(
        self,
        current: list[FixMemoryEntry],
        new_items: list[FixMemoryEntry],
    ) -> list[FixMemoryEntry]:
        merged: dict[str, FixMemoryEntry] = {item.id: item for item in current}
        for item in new_items:
            merged[item.id] = item
        return list(merged.values())

    def _store_project_notes_from_message(self, workspace_root: Path, message: str) -> int:
        notes = self._extract_project_notes(message)
        for note in notes:
            self.store.remember_project_note(
                project_root=workspace_root,
                category=note["category"],
                title=note["title"],
                detail=note["detail"],
                source="user_request",
                confidence=note["confidence"],
            )
        return len(notes)

    def _extract_project_notes(self, message: str) -> list[dict[str, Any]]:
        return list(memory_extract_project_notes(message))

    def _memory_title_for(self, category: str, detail: str) -> str:
        return memory_note_title_for(category, detail)

    def _repair_summary(self, before: CommandRun, after: CommandRun | None, repair: AgentDraft) -> str:
        return outcome_repair_summary(before, after, repair.plan)

    def _repair_strategy_hint(self, validation: CommandRun) -> str:
        return outcome_repair_strategy_hint(validation)

    def _fallback_draft(
        self,
        message: str,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
    ) -> AgentDraft:
        reply, plan, changes, warnings = self.fallback.respond(message, mode, workspace_root, files)
        return AgentDraft(reply=reply, plan=plan, changes=changes, warnings=warnings)
