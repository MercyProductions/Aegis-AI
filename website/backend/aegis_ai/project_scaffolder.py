from __future__ import annotations

import json
import re
import textwrap
import uuid
from pathlib import Path
from typing import Callable

from .commands import CommandResult, CommandRunner
from .project_scaffold_build_logs import (
    build_log_content as scaffold_build_log_content,
    command_log_section as scaffold_command_log_section,
    write_build_log as scaffold_write_build_log,
)
from .project_scaffold_command_stage import (
    run_command_stage as scaffold_run_command_stage,
)
from .project_scaffold_cpp_templates import (
    cpp_cmake_dll_template as scaffold_cpp_cmake_dll_template,
    cpp_cmake_template as scaffold_cpp_cmake_template,
    cpp_game_loop_template as scaffold_cpp_game_loop_template,
    cpp_imgui_win32_dx11_template as scaffold_cpp_imgui_win32_dx11_template,
    cpp_msvc_console_template as scaffold_cpp_msvc_console_template,
    cpp_windows_internals_hooking_template as scaffold_cpp_windows_internals_hooking_template,
    cpp_windows_service_template as scaffold_cpp_windows_service_template,
)
from .project_scaffold_desktop_templates import (
    electron_react_template as scaffold_electron_react_template,
    tauri_react_template as scaffold_tauri_react_template,
)
from .project_scaffold_dotnet_templates import (
    dotnet_console_template as scaffold_dotnet_console_template,
    dotnet_webapi_template as scaffold_dotnet_webapi_template,
    dotnet_wpf_template as scaffold_dotnet_wpf_template,
)
from .project_scaffold_go_rust_templates import (
    go_http_api_template as scaffold_go_http_api_template,
    rust_cli_template as scaffold_rust_cli_template,
)
from .project_scaffold_existing_validation import (
    EXISTING_PROJECT_MODE_WARNING as SCAFFOLD_EXISTING_PROJECT_MODE_WARNING,
    existing_project_install_stage as scaffold_existing_project_install_stage,
    existing_project_memory_stage as scaffold_existing_project_memory_stage,
    existing_project_next_steps as scaffold_existing_project_next_steps,
    existing_project_preamble_stages as scaffold_existing_project_preamble_stages,
    existing_project_repair_stage as scaffold_existing_project_repair_stage,
    existing_project_skipped_validation_stage as scaffold_existing_project_skipped_validation_stage,
)
from .project_scaffold_file_preview import (
    diff_preview_stage as scaffold_diff_preview_stage,
    diff_summary as scaffold_diff_summary,
    scaffold_file_change_preview,
)
from .project_scaffold_handoff import (
    aegis_handoff_files as scaffold_aegis_handoff_files,
    first_product_pass_items as scaffold_first_product_pass_items,
    mission_contract as scaffold_mission_contract,
    numbered_list as scaffold_numbered_list,
    roadmap_files as scaffold_roadmap_files,
)
from .project_scaffold_instruction_status import (
    instruction_status_payload as scaffold_instruction_status_payload,
)
from .project_scaffold_memory import (
    markdown_list as scaffold_markdown_list,
    project_memory_files as scaffold_project_memory_files,
)
from .project_scaffold_node_templates import (
    express_ts_template as scaffold_express_ts_template,
    node_cli_template as scaffold_node_cli_template,
    node_fullstack_template as scaffold_node_fullstack_template,
    node_http_api_template as scaffold_node_http_api_template,
)
from .project_scaffold_names import (
    GENERIC_TARGET_NAMES as SCAFFOLD_GENERIC_TARGET_NAMES,
    INSTRUCTIONAL_PROJECT_NAME_TOKENS as SCAFFOLD_INSTRUCTIONAL_PROJECT_NAME_TOKENS,
    PRESET_DEFAULT_PROJECT_NAMES as SCAFFOLD_PRESET_DEFAULT_PROJECT_NAMES,
    PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS as SCAFFOLD_PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS,
    TARGET_NAMED_WEB_PRESETS as SCAFFOLD_TARGET_NAMED_WEB_PRESETS,
    has_explicit_project_name as scaffold_has_explicit_project_name,
    looks_like_instructional_project_name as scaffold_looks_like_instructional_project_name,
    preset_default_project_name_if_needed as scaffold_preset_default_project_name_if_needed,
    project_name as scaffold_project_name,
    project_name_from_prompt as scaffold_project_name_from_prompt,
    should_use_target_leaf_project_name as scaffold_should_use_target_leaf_project_name,
    target_leaf_is_specific as scaffold_target_leaf_is_specific,
)
from .project_scaffold_presets import scaffold_presets
from .project_scaffold_planning import (
    default_plan_steps as scaffold_default_plan_steps,
    inspection_detail as scaffold_inspection_detail,
    risk_warnings_for_target as scaffold_risk_warnings_for_target,
)
from .project_scaffold_powershell_templates import (
    powershell_module_template as scaffold_powershell_module_template,
)
from .project_scaffold_python_templates import (
    fastapi_template as scaffold_fastapi_template,
    python_cli_template as scaffold_python_cli_template,
    python_stdlib_api_template as scaffold_python_stdlib_api_template,
    python_tkinter_desktop_template as scaffold_python_tkinter_desktop_template,
    sqlite_python_db_template as scaffold_sqlite_python_db_template,
)
from .project_scaffold_workspace_templates import (
    python_game_file_analyzer_template as scaffold_python_game_file_analyzer_template,
    python_sln_refactor_tool_template as scaffold_python_sln_refactor_tool_template,
)
from .project_scaffold_paths import (
    WINDOWS_PATH_ACTION_FOLLOWERS as SCAFFOLD_WINDOWS_PATH_ACTION_FOLLOWERS,
    WINDOWS_PATH_CONTEXTUAL_ACTIONS as SCAFFOLD_WINDOWS_PATH_CONTEXTUAL_ACTIONS,
    WINDOWS_PATH_STOP_PHRASES as SCAFFOLD_WINDOWS_PATH_STOP_PHRASES,
    WINDOWS_PATH_STRONG_STOP_PHRASES as SCAFFOLD_WINDOWS_PATH_STRONG_STOP_PHRASES,
    clean_windows_path_fragment as scaffold_clean_windows_path_fragment,
    extract_windows_path_from_prompt as scaffold_extract_windows_path_from_prompt,
    path_action_boundary_preserves_leaf as scaffold_path_action_boundary_preserves_leaf,
    path_action_stop_positions as scaffold_path_action_stop_positions,
    path_fragment_exists as scaffold_path_fragment_exists,
    path_instruction_separator_position as scaffold_path_instruction_separator_position,
    path_stop_phrase_is_boundary as scaffold_path_stop_phrase_is_boundary,
    prompt_without_windows_paths as scaffold_prompt_without_windows_paths,
    trailing_wrapper_belongs_to_path as scaffold_trailing_wrapper_belongs_to_path,
    trim_path_fragment as scaffold_trim_path_fragment,
)
from .project_scaffold_reporting import (
    categorize_command_result as scaffold_categorize_command_result,
    command_excerpt as scaffold_command_excerpt,
    command_ok as scaffold_command_ok,
    command_run as scaffold_command_run,
    diagnostic_display as scaffold_diagnostic_display,
    diagnostics_log as scaffold_diagnostics_log,
    extract_validation_diagnostics as scaffold_extract_validation_diagnostics,
    failed_step_parts_from_steps as scaffold_failed_step_parts_from_steps,
    log_text as scaffold_log_text,
    normalize_diagnostic_path as scaffold_normalize_diagnostic_path,
    status_text as scaffold_status_text,
    strip_ansi as scaffold_strip_ansi,
    summarize_command_result as scaffold_summarize_command_result,
    to_positive_int as scaffold_to_positive_int,
)
from .project_scaffold_runtime_memory import (
    error_signature as scaffold_error_signature,
    runtime_file_index_payload as scaffold_runtime_file_index_payload,
    updated_command_history as scaffold_updated_command_history,
    updated_known_errors as scaffold_updated_known_errors,
)
from .project_scaffold_targets import (
    command_for_project as scaffold_command_for_project,
    conflicting_paths as scaffold_conflicting_paths,
    has_non_metadata_entries as scaffold_has_non_metadata_entries,
    is_metadata_only_refresh as scaffold_is_metadata_only_refresh,
    is_same_scaffold_project as scaffold_is_same_scaffold_project,
    next_available_child_target as scaffold_next_available_child_target,
    should_install_before_validation as scaffold_should_install_before_validation,
    title_from_name as scaffold_title_from_name,
    visible_entries as scaffold_visible_entries,
)
from .project_scaffold_intent import (
    continuity_preset_id as scaffold_continuity_preset_id,
    existing_project_validation_command as scaffold_existing_project_validation_command,
    prompt_is_existing_project_validation_intent as scaffold_prompt_is_existing_project_validation_intent,
    prompt_requests_validation as scaffold_prompt_requests_validation,
    prompt_should_reuse_existing_project as scaffold_prompt_should_reuse_existing_project,
    should_update_existing_scaffold as scaffold_should_update_existing_scaffold,
    should_validate_existing_project_only as scaffold_should_validate_existing_project_only,
)
from .project_scaffold_stack_rules import (
    preset_stack_locks as scaffold_preset_stack_locks,
    prompt_allows_stack_switch as scaffold_prompt_allows_stack_switch,
    prompt_negates_web_stack as scaffold_prompt_negates_web_stack,
    stack_family_for_preset as scaffold_stack_family_for_preset,
    stack_lock_keywords_for_prompt as scaffold_stack_lock_keywords_for_prompt,
    stack_locks_conflict_with_preset as scaffold_stack_locks_conflict_with_preset,
)
from .project_scaffold_validation_plan import (
    failed_chain_step as scaffold_failed_chain_step,
    split_safe_command_chain as scaffold_split_safe_command_chain,
    validation_plan_payload as scaffold_validation_plan_payload,
    validation_step_label as scaffold_validation_step_label,
    validation_step_phase as scaffold_validation_step_phase,
)
from .scaffolding import template_method_name
from .schemas import (
    CommandRun,
    ProjectBuildStage,
    ProjectScaffoldFile,
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceInstructionFile,
    WorkspaceProjectManifest,
)
from .validation import ValidationManager
from .workspace import WorkspaceManager


TemplateBuilder = Callable[[str], dict[str, str]]


class ProjectScaffolder:
    """Deterministic project scaffolding that still uses workspace checkpoints."""

    SAFE_METADATA_REFRESH_PATHS = {
        ".aegis/command_history.json",
        ".aegis/decisions.md",
        ".aegis/file_index.json",
        ".aegis/instruction_status.json",
        ".aegis/known_errors.json",
        ".aegis/ROADMAP.md",
        ".aegis/project.json",
        ".aegis/validation_plan.json",
        ".gitignore",
        "AGENTS.md",
        "README.md",
    }
    WINDOWS_PATH_STOP_PHRASES = SCAFFOLD_WINDOWS_PATH_STOP_PHRASES
    WINDOWS_PATH_STRONG_STOP_PHRASES = SCAFFOLD_WINDOWS_PATH_STRONG_STOP_PHRASES
    WINDOWS_PATH_CONTEXTUAL_ACTIONS = SCAFFOLD_WINDOWS_PATH_CONTEXTUAL_ACTIONS
    WINDOWS_PATH_ACTION_FOLLOWERS = SCAFFOLD_WINDOWS_PATH_ACTION_FOLLOWERS
    TARGET_NAMED_WEB_PRESETS = SCAFFOLD_TARGET_NAMED_WEB_PRESETS
    PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS = SCAFFOLD_PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS
    PRESET_DEFAULT_PROJECT_NAMES = SCAFFOLD_PRESET_DEFAULT_PROJECT_NAMES
    INSTRUCTIONAL_PROJECT_NAME_TOKENS = SCAFFOLD_INSTRUCTIONAL_PROJECT_NAME_TOKENS
    GENERIC_TARGET_NAMES = SCAFFOLD_GENERIC_TARGET_NAMES

    def __init__(
        self,
        workspace: WorkspaceManager,
        validation: ValidationManager,
        *,
        commands: CommandRunner | None = None,
        sandbox_profile: str | None = None,
    ):
        self.workspace = workspace
        self.validation = validation
        self.commands = commands
        self.sandbox_profile = sandbox_profile

    @classmethod
    def presets(cls) -> list[ProjectScaffoldPreset]:
        return scaffold_presets()

    def preview(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        return self._build(request, apply=False)

    def scaffold(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        return self._build(request, apply=True)

    def plan_from_prompt(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
        prompt = " ".join(request.prompt.split())
        if not prompt:
            raise ValueError("prompt is required")

        target_path = self._clean_windows_path_fragment(request.preferred_target_path.strip())
        if not target_path:
            target_path = self._extract_windows_path_from_prompt(prompt)
        intent_prompt = self._prompt_without_windows_paths(prompt, target_path=target_path)

        base_workspace = self.workspace.resolve_workspace(
            request.workspace_root,
            migrate_legacy=False,
            create=False,
        )
        target_probe = self.workspace.resolve_workspace(
            target_path if target_path else str(base_workspace),
            migrate_legacy=False,
            create=False,
        )
        existing_manifest = (
            self.workspace.load_project_manifest(target_probe)
            if target_probe.exists() and target_probe.is_dir()
            else None
        )
        existing_profile = (
            self.workspace.inspect_dependency_profile(target_probe)
            if target_probe.exists() and target_probe.is_dir()
            else WorkspaceDependencyProfile()
        )
        preset, confidence, reasons, detected_keywords = self._select_preset(intent_prompt)
        stack_locks = self._stack_lock_keywords_for_prompt(intent_prompt)
        for item in stack_locks:
            if item not in detected_keywords:
                detected_keywords.insert(0, item)
        continuity_preset_id = self._continuity_preset_id(
            prompt=prompt,
            target=target_probe,
            manifest=existing_manifest,
            profile=existing_profile,
        )
        if continuity_preset_id and self._stack_locks_conflict_with_preset(stack_locks, continuity_preset_id):
            if self._prompt_allows_stack_switch(intent_prompt or prompt, stack_locks):
                reasons.insert(0, "The current prompt declared a different stack than the saved workspace context.")
                detected_keywords.insert(0, "current prompt stack override")
                continuity_preset_id = ""
            else:
                reasons.insert(
                    0,
                    "The saved mission contract kept the existing workspace stack despite ambiguous follow-up wording.",
                )
                detected_keywords.insert(0, "mission-contract:locked-stack")
        if continuity_preset_id:
            preset = self._preset_for(continuity_preset_id)
            confidence = max(confidence, 0.92)
            reasons.insert(0, f"Existing workspace context selected {preset.label}.")
            detected_keywords.insert(0, "mission-contract:reuse")
            detected_keywords.insert(0, "existing workspace continuity")
        raw_name = self._project_name_from_prompt(intent_prompt or prompt)
        if not self._has_explicit_project_name(prompt):
            raw_name = (
                (existing_manifest.project_name or existing_manifest.title)
                if existing_manifest and continuity_preset_id
                else self._preset_default_project_name_if_needed(preset.id, raw_name)
            )
        if target_path and not self._has_explicit_project_name(prompt):
            target_leaf = Path(target_path).name
            target_has_project_manifest = existing_manifest is not None
            if (
                not continuity_preset_id
                and (
                self._should_use_target_leaf_project_name(preset.id, target_leaf)
                or (
                    not target_has_project_manifest
                    and (
                        self._target_leaf_is_specific(target_leaf)
                        or preset.id not in self.PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS
                    )
                )
                )
            ):
                raw_name = target_leaf or raw_name
                if not self._target_leaf_is_specific(target_leaf):
                    raw_name = self._preset_default_project_name_if_needed(preset.id, raw_name)
        elif continuity_preset_id and not self._has_explicit_project_name(prompt):
            raw_name = raw_name or target_probe.name
        project_name = self._project_name(raw_name)
        install_command = self._command_for_project(preset.install_command, project_name)
        validation_command = self._command_for_project(preset.validation_command, project_name)
        if existing_manifest and continuity_preset_id:
            install_command = existing_manifest.install_command or install_command
            validation_command = existing_manifest.validation_command or validation_command
        run_validation = self._prompt_requests_validation(prompt)

        target = self.workspace.resolve_workspace(
            target_path if target_path else (str(target_probe) if continuity_preset_id else str(base_workspace / project_name)),
            migrate_legacy=False,
            create=False,
        )
        overwrite = self._should_update_existing_scaffold(prompt, target)

        scaffold_request = ProjectScaffoldRequest(
            target_path=str(target),
            preset_id=preset.id,
            project_name=project_name,
            prompt=prompt,
            overwrite=overwrite,
            install_command=install_command,
            validation_command=validation_command,
            include_gitignore=True,
            run_validation=run_validation,
        )
        execution_mode = "existing_validation" if self._should_validate_existing_project_only(
            prompt,
            target,
            scaffold_request,
            existing_profile,
        ) else "scaffold"
        if execution_mode == "existing_validation":
            validation_command = self._existing_project_validation_command(
                target,
                existing_profile,
                validation_command,
            )
            scaffold_request = scaffold_request.model_copy(
                update={"validation_command": validation_command}
            )
        primary_action = (
            "validate_existing_project"
            if execution_mode == "existing_validation"
            else "create_or_update_files"
        )
        plan_steps = self._default_plan_steps(preset, project_name, install_command, validation_command)
        risk_warnings = self._risk_warnings_for_target(target, overwrite=overwrite)
        assumptions = [
            "This is a planning result only; use preview or create before files are written.",
            "The target folder passed the configured Aegis workspace allowlist.",
        ]
        if raw_name == "aegis-app":
            assumptions.append("No explicit project name was found, so Aegis used a safe default name.")
        if not target_path:
            assumptions.append("No target folder was supplied, so Aegis placed the project under the active workspace root.")
        if run_validation:
            assumptions.append("The prompt asked Aegis to build, run, test, or validate the project, so validation is enabled for the scaffold request.")
        if continuity_preset_id:
            assumptions.append("Existing workspace manifest or build files were detected, so Aegis reused the current project stack instead of selecting a new scaffold from the follow-up prompt.")
        if execution_mode == "existing_validation":
            assumptions.append("This is an existing-project validation pass; Aegis will not generate starter files before build/test repair.")
        if stack_locks:
            assumptions.append("The prompt included explicit stack language, so Aegis will preserve that stack instead of drifting to a generic starter.")

        return ProjectScaffoldPlanResponse(
            ok=True,
            message=f"Planned {preset.label} from prompt.",
            prompt=prompt,
            execution_mode=execution_mode,
            primary_action=primary_action,
            confidence=confidence,
            preset=preset,
            project_name=project_name,
            target_path=str(target),
            install_command=install_command,
            validation_command=validation_command,
            overwrite=overwrite,
            include_gitignore=True,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            reasons=reasons,
            assumptions=assumptions,
            detected_keywords=detected_keywords,
            scaffold_request=scaffold_request,
        )

    def _build(self, request: ProjectScaffoldRequest, *, apply: bool) -> ProjectScaffoldResponse:
        request = self._normalize_scaffold_request_from_prompt(request)
        preset = self._preset_for(request.preset_id)
        project_name = self._project_name(request.project_name)
        target = self.workspace.resolve_workspace(request.target_path, migrate_legacy=False, create=apply)
        prompt = " ".join(request.prompt.split())
        existing_files = self.workspace.scan(target, max_files=160) if target.exists() else []
        existing_profile = (
            self.workspace.inspect_dependency_profile(target)
            if target.exists() and target.is_dir()
            else WorkspaceDependencyProfile()
        )
        plan_steps = self._default_plan_steps(
            preset,
            project_name,
            self._command_for_project(request.install_command.strip() or preset.install_command, project_name),
            self._command_for_project(request.validation_command.strip() or preset.validation_command, project_name),
        )
        pre_warnings: list[str] = []
        stages: list[ProjectBuildStage] = [
            ProjectBuildStage(
                id="intent",
                label="Read request and create visible plan",
                status="succeeded",
                detail=f"Selected {preset.label} for {project_name} and prepared {len(plan_steps)} execution step(s).",
            ),
            ProjectBuildStage(
                id="inspect",
                label="Inspect target workspace",
                status="succeeded" if target.exists() else "skipped",
                detail=self._inspection_detail(target, existing_files, existing_profile),
            )
        ]

        validation_command = self._command_for_project(request.validation_command.strip() or preset.validation_command, project_name)
        install_command = self._command_for_project(request.install_command.strip() or preset.install_command, project_name)
        if self._should_validate_existing_project_only(prompt, target, request, existing_profile):
            return self._existing_project_validation_response(
                request,
                apply=apply,
                target=target,
                preset=preset,
                project_name=project_name,
                install_command=install_command,
                validation_command=validation_command,
                existing_files=existing_files,
                existing_profile=existing_profile,
                plan_steps=plan_steps,
                stages=stages,
            )

        files = self._template_for(preset.id)(project_name)
        files = self._specialize_template_for_prompt(preset.id, project_name, prompt, files)
        if not request.include_gitignore:
            files.pop(".gitignore", None)
        if request.create_roadmap:
            files.update(
                self._roadmap_files(
                    preset,
                    project_name,
                    prompt=prompt,
                    install_command=install_command,
                    validation_command=validation_command,
                    max_repair_attempts=request.max_repair_attempts,
                )
            )
        files.update(
            self._aegis_handoff_files(
                preset,
                project_name,
                prompt=prompt,
                install_command=install_command,
                validation_command=validation_command,
            )
        )
        existing_entries = self._visible_entries(target)
        conflicting_paths = self._conflicting_paths(target, files)
        metadata_only_refresh = (
            self._is_metadata_only_refresh(target, conflicting_paths)
            and not self._has_non_metadata_entries(target)
        )
        if conflicting_paths and not request.overwrite and not metadata_only_refresh:
            original_target = target
            target = self._next_available_child_target(target, project_name)
            existing_entries = self._visible_entries(target)
            conflicting_paths = self._conflicting_paths(target, files)
            same_child_project = self._is_same_scaffold_project(target, preset.id, project_name)
            metadata_only_refresh = (
                self._is_metadata_only_refresh(target, conflicting_paths)
                and not self._has_non_metadata_entries(target)
            )
            if conflicting_paths and not metadata_only_refresh and not same_child_project:
                target = self._next_available_child_target(original_target, f"{project_name}-{preset.id}")
                existing_entries = self._visible_entries(target)
                conflicting_paths = self._conflicting_paths(target, files)
                same_child_project = self._is_same_scaffold_project(target, preset.id, project_name)
                metadata_only_refresh = (
                    self._is_metadata_only_refresh(target, conflicting_paths)
                    and not self._has_non_metadata_entries(target)
                )
            if same_child_project and conflicting_paths:
                pre_warnings.append(
                    "Requested target already contained another scaffold. Aegis reused the matching child project "
                    f"at {target} and refreshed its generated files."
                )
            else:
                pre_warnings.append(
                    "Requested target already contained scaffold-owned paths from another project. "
                    f"Aegis created a clean child project at {target} instead of stopping or overwriting files."
                )
        if existing_entries and not conflicting_paths:
            pre_warnings.append(
                "Target folder already contained files. Aegis wrote only non-conflicting scaffold files and left existing files untouched."
            )
        elif metadata_only_refresh and not request.overwrite:
            pre_warnings.append(
                "Target folder only contained Aegis scaffold metadata conflicts. Aegis refreshed metadata and left other files untouched."
            )
        elif conflicting_paths and request.overwrite:
            pre_warnings.append(
                "Target folder contained scaffold-owned files. Aegis updated only generated paths for this preset."
            )
        existing_files = self.workspace.scan(target, max_files=160) if target.exists() else []
        existing_profile = (
            self.workspace.inspect_dependency_profile(target)
            if target.exists() and target.is_dir()
            else WorkspaceDependencyProfile()
        )
        risk_warnings = self._risk_warnings_for_target(target, overwrite=request.overwrite)
        memory_files = self._project_memory_files(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            existing_files=existing_files,
            existing_profile=existing_profile,
            planned_files=files,
        )
        files.update(memory_files)
        memory_paths = sorted(memory_files)
        stages.append(
            ProjectBuildStage(
                id="structure",
                label="Generate project structure",
                status="succeeded",
                detail=f"Prepared {len(files)} scaffold file(s), including Aegis handoff metadata.",
            )
        )
        stages.append(
            ProjectBuildStage(
                id="roadmap",
                label="Create roadmap and handoff files",
                status="succeeded" if request.create_roadmap else "skipped",
                detail=(
                    "Added .aegis/ROADMAP.md with the visible plan, validation path, and repair loop expectations."
                    if request.create_roadmap
                    else "Roadmap creation was disabled for this request."
                ),
            )
        )

        changes, file_infos = scaffold_file_change_preview(target, preset, files)
        diff_summary = self._diff_summary(file_infos)
        stages.append(scaffold_diff_preview_stage(file_infos))

        apply_result = None
        validation: CommandRun | None = None
        applied: list[str] = []
        warnings: list[str] = []
        warnings.extend(pre_warnings)
        checkpoint: str | None = None
        if apply:
            apply_result = self.workspace.apply_changes(target, changes)
            applied.extend(apply_result.applied)
            warnings.extend(apply_result.warnings)
            checkpoint = apply_result.checkpoint
            stages.append(
                ProjectBuildStage(
                    id="apply",
                    label="Write files with checkpoint",
                    status="succeeded",
                    detail=f"Applied {len(apply_result.applied)} file change(s).",
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="apply",
                    label="Write files with checkpoint",
                    status="skipped",
                    detail="Preview mode only; no files were written.",
                )
            )

        if apply and validation_command:
            self.validation.save_profile(
                target,
                command=validation_command,
                label=f"{preset.label} validation",
                source="project_builder",
                notes="Generated by the Aegis Project Builder scaffold preset.",
            )

        install_run: CommandRun | None = None
        auto_install_before_validation = self._should_install_before_validation(
            preset,
            target,
            install_command=install_command,
            validation_command=validation_command,
            request=request,
        )
        should_run_install = apply and install_command and (request.run_install or auto_install_before_validation)
        if should_run_install:
            install_stage, install_run = self._run_command_stage(
                stage_id="install",
                label="Install dependencies",
                command=install_command,
                target=target,
            )
            if auto_install_before_validation:
                install_stage.detail = (
                    install_stage.detail.rstrip(".")
                    + ". Auto-ran before validation because this is a fresh dependency-managed scaffold."
                )
            stages.append(install_stage)
        else:
            stages.append(
                ProjectBuildStage(
                    id="install",
                    label="Install dependencies",
                    status="skipped" if install_command else "planned",
                    detail=(
                        "Install command captured but not run automatically."
                        if install_command
                        else "No install command is defined for this preset."
                    ),
                    command=install_command,
                )
            )

        if apply and request.run_validation and validation_command:
            validation_stage, validation = self._run_command_stage(
                stage_id="validate",
                label="Run build/test validation",
                command=validation_command,
                target=target,
            )
            stages.append(validation_stage)
        else:
            stages.append(
                ProjectBuildStage(
                    id="validate",
                    label="Run build/test validation",
                    status="skipped" if validation_command else "planned",
                    detail=(
                        "Validation command saved; enable validation to run it immediately after create."
                        if validation_command
                        else "No validation command is defined for this preset."
                    ),
                    command=validation_command,
                )
            )

        validation_failed = validation is not None and not self._command_ok(validation)
        if validation_failed and request.max_repair_attempts > 0:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="blocked" if validation and not validation.allowed else "planned",
                    detail=(
                        "Captured the failing validation output. The chat agent can now use this workspace, "
                        "the saved validation profile, and the error output for its auto-repair loop."
                    ),
                    command=validation_command,
                    output_excerpt=self._command_excerpt(validation) if validation else "",
                    error=(validation.summary or validation.reason) if validation else "",
                )
            )
            warnings.append(
                "Validation did not pass. Aegis captured the failure so the chat repair loop can work from real output."
            )
        elif validation is not None:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped" if self._command_ok(validation) else "planned",
                    detail=(
                        "Validation passed; no repair loop is needed."
                        if self._command_ok(validation)
                        else "Validation failed, but repair attempts are disabled for this project-builder request."
                    ),
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped",
                    detail="No validation output was produced, so no repair loop was started.",
                )
            )

        build_log_path = ""
        if apply:
            try:
                build_log_path = self._write_build_log(
                    target,
                    preset=preset,
                    project_name=project_name,
                    checkpoint=checkpoint,
                    install=install_run,
                    validation=validation,
                    install_command=install_command,
                    validation_command=validation_command,
                )
                if build_log_path:
                    stages.append(
                        ProjectBuildStage(
                            id="build-log",
                            label="Save build and validation log",
                            status="succeeded",
                            detail=f"Saved command output to {build_log_path}.",
                        )
                    )
            except OSError as exc:
                warnings.append(f"Could not write .aegis build log: {exc}")
                stages.append(
                    ProjectBuildStage(
                        id="build-log",
                        label="Save build and validation log",
                        status="failed",
                        detail="Command output was captured in memory, but the durable build log could not be written.",
                        error=str(exc),
                    )
                )

        if apply:
            memory_warnings = self._record_runtime_memory(
                target,
                preset=preset,
                project_name=project_name,
                checkpoint=checkpoint,
                install=install_run,
                validation=validation,
                install_command=install_command,
                validation_command=validation_command,
                build_log_path=build_log_path,
                prompt=prompt,
                applied=applied,
            )
            warnings.extend(memory_warnings)
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="succeeded",
                    detail=(
                        "Updated .aegis file index, command history, known-error memory, and instruction checkpoint."
                        if not memory_warnings
                        else "Project memory updated with warnings: " + "; ".join(memory_warnings[:2])
                    ),
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="skipped",
                    detail="Preview mode only; project memory files are shown in the diff but not written.",
                )
            )

        next_steps = [
            f"Open the workspace at {target}.",
            (
                f"Install dependencies with `{install_command}`."
                if install_command and not request.run_install
                else "Review dependency install output before adding the first feature."
            ),
            (
                f"Use the saved validation profile: `{validation_command}`."
                if validation_command and not request.run_validation
                else "Review captured validation output and continue the repair loop from the chat workspace."
            ),
            "Ask Auralith Prime for the first feature pass once the scaffold validates or the captured failure is repaired.",
        ]

        return ProjectScaffoldResponse(
            ok=True,
            message=(
                f"Created {preset.label} scaffold with {len(file_infos)} files."
                if apply
                else f"Previewed {preset.label} scaffold with {len(file_infos)} planned files."
            ),
            execution_mode="scaffold",
            primary_action="create_or_update_files",
            target_path=str(target),
            preset=preset,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            diff_summary=diff_summary,
            memory_paths=memory_paths,
            files=file_infos,
            file_change_count=len(file_infos),
            applied=applied,
            warnings=warnings,
            checkpoint=checkpoint,
            install_command=install_command,
            validation_command=validation_command,
            roadmap_path=".aegis/ROADMAP.md" if request.create_roadmap else "",
            build_log_path=build_log_path,
            stages=stages,
            validation=validation,
            next_steps=next_steps,
            workspace_files=self.workspace.scan(target, max_files=160) if target.exists() else [],
        )

    def _normalize_scaffold_request_from_prompt(self, request: ProjectScaffoldRequest) -> ProjectScaffoldRequest:
        prompt = " ".join(request.prompt.split())
        if not prompt:
            return request

        default_preset = ProjectScaffoldRequest.model_fields["preset_id"].default
        default_name = ProjectScaffoldRequest.model_fields["project_name"].default
        looks_unplanned = (
            request.preset_id == default_preset
            and request.project_name == default_name
            and not request.install_command.strip()
            and not request.validation_command.strip()
        )
        if not looks_unplanned:
            return request

        plan = self.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=prompt,
                preferred_target_path=request.target_path,
            )
        )
        planned = plan.scaffold_request
        return planned.model_copy(
            update={
                "target_path": request.target_path or planned.target_path,
                "prompt": request.prompt,
                "overwrite": request.overwrite or planned.overwrite,
                "include_gitignore": request.include_gitignore,
                "create_roadmap": request.create_roadmap,
                "run_install": request.run_install,
                "run_validation": request.run_validation or planned.run_validation,
                "max_repair_attempts": request.max_repair_attempts,
            }
        )

    def _existing_project_validation_response(
        self,
        request: ProjectScaffoldRequest,
        *,
        apply: bool,
        target: Path,
        preset: ProjectScaffoldPreset,
        project_name: str,
        install_command: str,
        validation_command: str,
        existing_files: list[WorkspaceFile],
        existing_profile: WorkspaceDependencyProfile,
        plan_steps: list[str],
        stages: list[ProjectBuildStage],
    ) -> ProjectScaffoldResponse:
        validation_command = self._existing_project_validation_command(
            target,
            existing_profile,
            validation_command,
        )
        warnings = [SCAFFOLD_EXISTING_PROJECT_MODE_WARNING]
        risk_warnings = self._risk_warnings_for_target(target, overwrite=request.overwrite)
        stages.extend(scaffold_existing_project_preamble_stages())

        validation: CommandRun | None = None
        if apply and validation_command:
            self.validation.save_profile(
                target,
                command=validation_command,
                label=f"{preset.label} validation",
                source="project_builder_existing",
                notes="Existing project build/fix pass; no starter scaffold files were generated.",
            )

        stages.append(scaffold_existing_project_install_stage(install_command))

        if apply and request.run_validation and validation_command:
            validation_stage, validation = self._run_command_stage(
                stage_id="validate",
                label="Run existing project validation",
                command=validation_command,
                target=target,
            )
            stages.append(validation_stage)
        else:
            stages.append(scaffold_existing_project_skipped_validation_stage(validation_command))

        if validation is not None and not self._command_ok(validation):
            stages.append(scaffold_existing_project_repair_stage(validation, validation_command=validation_command))
            warnings.append("Validation did not pass. Aegis captured the failure for the repair loop.")
        else:
            stages.append(scaffold_existing_project_repair_stage(validation, validation_command=validation_command))

        build_log_path = ""
        if apply:
            try:
                build_log_path = self._write_build_log(
                    target,
                    preset=preset,
                    project_name=project_name,
                    checkpoint=None,
                    install=None,
                    validation=validation,
                    install_command=install_command,
                    validation_command=validation_command,
                )
                if build_log_path:
                    stages.append(
                        ProjectBuildStage(
                            id="build-log",
                            label="Save build and validation log",
                            status="succeeded",
                            detail=f"Saved command output to {build_log_path}.",
                        )
                    )
            except OSError as exc:
                warnings.append(f"Could not write .aegis build log: {exc}")
                stages.append(
                    ProjectBuildStage(
                        id="build-log",
                        label="Save build and validation log",
                        status="failed",
                        detail="Command output was captured in memory, but the durable build log could not be written.",
                        error=str(exc),
                    )
                )

            memory_warnings = self._record_runtime_memory(
                target,
                preset=preset,
                project_name=project_name,
                checkpoint=None,
                install=None,
                validation=validation,
                install_command=install_command,
                validation_command=validation_command,
                build_log_path=build_log_path,
                prompt=request.prompt,
                applied=[],
            )
            warnings.extend(memory_warnings)
            stages.append(scaffold_existing_project_memory_stage(apply=True, warnings=memory_warnings))
        else:
            stages.append(scaffold_existing_project_memory_stage(apply=False, warnings=[]))

        next_steps = scaffold_existing_project_next_steps(target, validation)

        return ProjectScaffoldResponse(
            ok=True,
            message=(
                "Validated existing project without generating starter files."
                if apply
                else "Previewed existing project validation pass without starter-file generation."
            ),
            execution_mode="existing_validation",
            primary_action="validate_existing_project",
            target_path=str(target),
            preset=preset,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            diff_summary=[],
            memory_paths=[],
            files=[],
            file_change_count=0,
            applied=[],
            warnings=warnings,
            checkpoint=None,
            install_command=install_command,
            validation_command=validation_command,
            roadmap_path="",
            build_log_path=build_log_path,
            stages=stages,
            validation=validation,
            next_steps=next_steps,
            workspace_files=self.workspace.scan(target, max_files=160) if target.exists() else existing_files,
        )

    @classmethod
    def _preset_for(cls, preset_id: str) -> ProjectScaffoldPreset:
        normalized = (preset_id or "").strip()
        for preset in cls.presets():
            if preset.id == normalized:
                return preset
        raise ValueError(f"unknown project scaffold preset: {preset_id}")

    @classmethod
    def _template_for(cls, preset_id: str) -> TemplateBuilder:
        return getattr(cls, template_method_name(preset_id))

    @classmethod
    def _specialize_template_for_prompt(
        cls,
        preset_id: str,
        project_name: str,
        prompt: str,
        files: dict[str, str],
    ) -> dict[str, str]:
        specialized = dict(files)
        if preset_id == "nextjs-ts-tailwind":
            specialized["components/app-shell.tsx"] = cls._nextjs_app_shell(project_name, prompt)
        elif preset_id == "vite-react-ts":
            specialized["src/App.tsx"] = cls._vite_app(project_name, prompt)
            specialized["src/styles.css"] = cls._vite_styles()
        elif preset_id == "static-html-site":
            specialized["index.html"] = cls._static_html_index(project_name, prompt)
        return specialized

    @staticmethod
    def _web_copy_profile(project_name: str, prompt: str) -> dict[str, object]:
        title = _title_from_name(project_name)
        text = f"{project_name} {prompt}".lower()

        if any(term in text for term in ("barber", "barbershop", "haircut", "fade", "beard", "shave")):
            brand = title.replace(" Website", "").replace(" Site", "").strip() or title
            return {
                "brand": brand,
                "eyebrow": "Neighborhood barber studio",
                "headline": f"{brand} keeps every cut sharp, calm, and appointment-ready.",
                "subhead": "A full-service barber site with booking calls to action, service cards, trust signals, hours, and a polished first screen ready for real content.",
                "primaryCta": "Book a chair",
                "secondaryCta": "View services",
                "stats": [
                    {"value": "30 min", "label": "Average cut window"},
                    {"value": "4.9", "label": "Client rating target"},
                    {"value": "6", "label": "Signature services"},
                ],
                "services": [
                    {"name": "Precision Cut", "detail": "Consultation, clipper work, scissor finish, and style check.", "price": "$32+"},
                    {"name": "Skin Fade", "detail": "Tight blend, clean neckline, and camera-ready finish.", "price": "$38+"},
                    {"name": "Beard Shape", "detail": "Line-up, sculpting, warm towel prep, and conditioning.", "price": "$24+"},
                    {"name": "Hot Towel Shave", "detail": "Classic straight-razor service with calm premium care.", "price": "$36+"},
                ],
                "process": [
                    "Choose a service and preferred time.",
                    "Confirm cut notes, beard goals, or photo reference.",
                    "Leave with aftercare tips and an easy rebook path.",
                ],
                "spotlight": "Built for a local shop that needs quick booking, clear services, and a premium but grounded brand presence.",
                "hours": ["Tue-Fri 9:00 AM - 7:00 PM", "Sat 9:00 AM - 4:00 PM", "Sun-Mon by request"],
            }

        if any(term in text for term in ("restaurant", "cafe", "coffee", "food", "menu", "bakery")):
            return {
                "brand": title,
                "eyebrow": "Hospitality website",
                "headline": f"{title} turns menu browsing into a smooth reservation path.",
                "subhead": "A responsive first pass for a venue with menu highlights, booking calls to action, location details, and daily feature content.",
                "primaryCta": "Reserve a table",
                "secondaryCta": "Explore menu",
                "stats": [
                    {"value": "12", "label": "Featured dishes"},
                    {"value": "3", "label": "Service windows"},
                    {"value": "24h", "label": "Booking response"},
                ],
                "services": [
                    {"name": "Seasonal Menu", "detail": "Rotating plates with clear categories and dietary notes.", "price": "Updated weekly"},
                    {"name": "Private Events", "detail": "Request flow for small gatherings and catered experiences.", "price": "Custom"},
                    {"name": "Online Ordering", "detail": "Simple pickup journey with featured specials.", "price": "Ready"},
                    {"name": "Gift Cards", "detail": "Prominent secondary revenue path for loyal guests.", "price": "Any amount"},
                ],
                "process": ["Browse menu highlights.", "Pick pickup, dine-in, or event inquiry.", "Confirm details and collect guest info."],
                "spotlight": "Built for a venue that needs strong visual rhythm, clear conversion paths, and simple content updates.",
                "hours": ["Lunch Tue-Sat", "Dinner Thu-Sun", "Events by inquiry"],
            }

        return {
            "brand": title,
            "eyebrow": "Aegis production scaffold",
            "headline": f"{title} is ready for a real first product pass.",
            "subhead": "A structured app starter with responsive sections, concrete calls to action, validation metadata, and enough surface area for the agent to continue building instead of stopping at a placeholder.",
            "primaryCta": "Start workflow",
            "secondaryCta": "Review roadmap",
            "stats": [
                {"value": "6+", "label": "Core sections"},
                {"value": "1", "label": "Validation profile"},
                {"value": "100%", "label": "Checkpointed writes"},
            ],
            "services": [
                {"name": "Workspace Dashboard", "detail": "Primary screen for status, activity, and next actions.", "price": "Ready"},
                {"name": "Data Model", "detail": "Clear room for entities, relationships, and persistence.", "price": "Planned"},
                {"name": "User Flow", "detail": "A first conversion path that can be made real in the next pass.", "price": "Next"},
                {"name": "Quality Loop", "detail": "Validation, repair, and project memory are wired from the start.", "price": "Active"},
            ],
            "process": ["Inspect the generated structure.", "Install dependencies.", "Run validation and continue the feature pass."],
            "spotlight": "Built to give Aegis enough real project shape to continue autonomously with code, tests, and refinements.",
            "hours": ["Build", "Validate", "Repair"],
        }

    @classmethod
    def _static_html_index(cls, project_name: str, prompt: str) -> str:
        profile = cls._web_copy_profile(project_name, prompt)

        def esc(value: object) -> str:
            return (
                str(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        brand = esc(profile["brand"])
        eyebrow = esc(profile["eyebrow"])
        headline = esc(profile["headline"])
        subhead = esc(profile["subhead"])
        primary_cta = esc(profile["primaryCta"])
        secondary_cta = esc(profile["secondaryCta"])
        spotlight = esc(profile["spotlight"])
        services = profile["services"] if isinstance(profile["services"], list) else []
        process = profile["process"] if isinstance(profile["process"], list) else []
        hours = profile["hours"] if isinstance(profile["hours"], list) else []
        stats = profile["stats"] if isinstance(profile["stats"], list) else []

        service_cards = "\n".join(
            _strip(
                f"""
                <article class="card">
                  <span class="card-kicker">{esc(service.get("price", "Ready"))}</span>
                  <h3>{esc(service.get("name", "Service"))}</h3>
                  <p>{esc(service.get("detail", "Ready to customize."))}</p>
                </article>
                """
            )
            for service in services[:4]
            if isinstance(service, dict)
        )
        feature_items = "\n".join(
            _strip(
                f"""
                <div>
                  <strong>Step {index}</strong>
                  <span>{esc(step)}</span>
                </div>
                """
            )
            for index, step in enumerate(process[:3], start=1)
        )
        stat_items = "\n".join(
            _strip(
                f"""
                <div class="hero-stat">
                  <strong>{esc(stat.get("value", "Ready"))}</strong>
                  <span>{esc(stat.get("label", "Project signal"))}</span>
                </div>
                """
            )
            for stat in stats[:3]
            if isinstance(stat, dict)
        )
        hour_items = "\n".join(f"<span>{esc(item)}</span>" for item in hours[:3])

        return _strip(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <meta name="description" content="{brand} responsive business website generated by Aegis." />
                <title>{brand}</title>
                <link rel="stylesheet" href="styles.css" />
              </head>
              <body>
                <header class="site-header">
                  <a class="brand" href="#top" aria-label="{brand} home">{brand}</a>
                  <nav class="nav" aria-label="Primary navigation">
                    <a href="#services">Services</a>
                    <a href="#work">Work</a>
                    <a href="#booking">Booking</a>
                    <a href="#contact">Contact</a>
                  </nav>
                </header>

                <main id="top">
                  <section class="hero section">
                    <div class="hero-copy">
                      <p class="eyebrow">{eyebrow}</p>
                      <h1>{headline}</h1>
                      <p class="lead">{subhead}</p>
                      <div class="hero-actions" aria-label="Primary actions">
                        <a class="button primary" href="#booking">{primary_cta}</a>
                        <a class="button secondary" href="#services">{secondary_cta}</a>
                      </div>
                    </div>
                    <div class="hero-panel" aria-label="Featured business highlights">
                      <span>Project focus</span>
                      <strong>{brand}</strong>
                      <p>{spotlight}</p>
                      <div class="hero-stats">{stat_items}</div>
                    </div>
                  </section>

                  <section id="services" class="section">
                    <div class="section-heading">
                      <p class="eyebrow">Services</p>
                      <h2>Clear offers, quick decisions, and a direct action path.</h2>
                    </div>
                    <div class="card-grid">
                      {service_cards}
                    </div>
                  </section>

                  <section id="work" class="section split">
                    <div>
                      <p class="eyebrow">Experience</p>
                      <h2>A focused site structure Aegis can keep expanding.</h2>
                    </div>
                    <div class="feature-list">
                      {feature_items}
                    </div>
                  </section>

                  <section id="booking" class="section booking">
                    <div class="section-heading">
                      <p class="eyebrow">Booking</p>
                      <h2>Capture the first customer action.</h2>
                    </div>
                    <form class="booking-form" data-booking-form>
                      <label>
                        Name
                        <input name="name" type="text" autocomplete="name" required />
                      </label>
                      <label>
                        Service
                        <select name="service" required>
                          <option value="">Choose a service</option>
                          <option>Signature Service</option>
                          <option>Express Option</option>
                          <option>Custom Session</option>
                        </select>
                      </label>
                      <label>
                        Preferred date
                        <input name="date" type="date" required />
                      </label>
                      <button class="button primary" type="submit">{primary_cta}</button>
                      <p class="form-status" data-form-status role="status" aria-live="polite"></p>
                    </form>
                  </section>
                </main>

                <footer id="contact" class="site-footer">
                  <div>
                    <strong>{brand}</strong>
                    <span>{hour_items}</span>
                  </div>
                  <a class="button secondary" href="mailto:hello@example.com">hello@example.com</a>
                </footer>

                <script src="scripts.js"></script>
              </body>
            </html>
            """
        )

    @classmethod
    def _nextjs_app_shell(cls, project_name: str, prompt: str) -> str:
        profile = json.dumps(cls._web_copy_profile(project_name, prompt), indent=2)
        return _strip(
            f"""
            const profile = {profile} as const;

            export function AppShell() {{
              return (
                <main className="min-h-screen bg-[#071018] text-slate-100">
                  <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 py-5 sm:px-8 lg:px-10">
                    <nav className="flex items-center justify-between border-b border-white/10 pb-4">
                      <div>
                        <p className="text-xs uppercase tracking-normal text-emerald-300">{{profile.eyebrow}}</p>
                        <p className="mt-1 text-lg font-semibold">{{profile.brand}}</p>
                      </div>
                      <a className="rounded-md border border-white/15 px-3 py-2 text-sm text-slate-200" href="#contact">
                        Contact
                      </a>
                    </nav>

                    <header className="grid flex-1 gap-8 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
                      <div>
                        <p className="text-sm text-cyan-200">Built with Aegis Project Builder</p>
                        <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight tracking-normal sm:text-5xl lg:text-6xl">
                          {{profile.headline}}
                        </h1>
                        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">{{profile.subhead}}</p>
                        <div className="mt-7 flex flex-wrap gap-3">
                          <a className="rounded-md bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950" href="#contact">
                            {{profile.primaryCta}}
                          </a>
                          <a className="rounded-md border border-white/15 px-4 py-3 text-sm text-slate-100" href="#services">
                            {{profile.secondaryCta}}
                          </a>
                        </div>
                      </div>

                      <aside className="border border-white/10 bg-white/[0.045] p-5">
                        <p className="text-sm text-slate-300">{{profile.spotlight}}</p>
                        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                          {{profile.stats.map((stat) => (
                            <div key={{stat.label}} className="border border-white/10 bg-slate-950/60 p-4">
                              <p className="text-3xl font-semibold text-white">{{stat.value}}</p>
                              <p className="mt-2 text-sm text-slate-400">{{stat.label}}</p>
                            </div>
                          ))}}
                        </div>
                      </aside>
                    </header>

                    <section id="services" className="grid gap-4 border-t border-white/10 py-8 md:grid-cols-2 xl:grid-cols-4">
                      {{profile.services.map((service) => (
                        <article key={{service.name}} className="border border-white/10 bg-[#0d1824] p-5">
                          <div className="flex items-start justify-between gap-3">
                            <h2 className="text-lg font-semibold">{{service.name}}</h2>
                            <span className="text-sm text-emerald-300">{{service.price}}</span>
                          </div>
                          <p className="mt-4 text-sm leading-6 text-slate-300">{{service.detail}}</p>
                        </article>
                      ))}}
                    </section>

                    <section className="grid gap-5 pb-10 lg:grid-cols-[0.85fr_1.15fr]">
                      <div className="border border-white/10 bg-white/[0.04] p-5">
                        <h2 className="text-xl font-semibold">How it works</h2>
                        <ol className="mt-5 space-y-3">
                          {{profile.process.map((step, index) => (
                            <li key={{step}} className="flex gap-3 text-sm text-slate-300">
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-400 text-xs font-bold text-slate-950">
                                {{index + 1}}
                              </span>
                              <span className="pt-1">{{step}}</span>
                            </li>
                          ))}}
                        </ol>
                      </div>

                      <div id="contact" className="border border-white/10 bg-[#101b26] p-5">
                        <h2 className="text-xl font-semibold">Contact and availability</h2>
                        <div className="mt-5 grid gap-3 md:grid-cols-3">
                          {{profile.hours.map((item) => (
                            <div key={{item}} className="border border-white/10 bg-slate-950/55 p-4 text-sm text-slate-300">
                              {{item}}
                            </div>
                          ))}}
                        </div>
                        <p className="mt-5 text-sm leading-6 text-slate-300">
                          Replace this panel with live booking, maps, payment, or CRM integration in the next Aegis pass.
                        </p>
                      </div>
                    </section>
                  </section>
                </main>
              );
            }}
            """
        )

    @classmethod
    def _vite_app(cls, project_name: str, prompt: str) -> str:
        profile = json.dumps(cls._web_copy_profile(project_name, prompt), indent=2)
        return _strip(
            f"""
            const profile = {profile} as const;

            export function App() {{
              return (
                <main className="shell">
                  <nav className="topbar">
                    <div>
                      <span>{{profile.eyebrow}}</span>
                      <strong>{{profile.brand}}</strong>
                    </div>
                    <a href="#contact">{{profile.primaryCta}}</a>
                  </nav>

                  <header className="hero">
                    <p>Production starter</p>
                    <h1>{{profile.headline}}</h1>
                    <span>{{profile.subhead}}</span>
                    <div className="heroActions">
                      <a className="primary" href="#services">{{profile.secondaryCta}}</a>
                      <a className="secondary" href="#contact">Contact</a>
                    </div>
                  </header>

                  <section className="stats">
                    {{profile.stats.map((stat) => (
                      <article key={{stat.label}}>
                        <strong>{{stat.value}}</strong>
                        <span>{{stat.label}}</span>
                      </article>
                    ))}}
                  </section>

                  <section id="services" className="services">
                    {{profile.services.map((service) => (
                      <article key={{service.name}}>
                        <div>
                          <h2>{{service.name}}</h2>
                          <span>{{service.price}}</span>
                        </div>
                        <p>{{service.detail}}</p>
                      </article>
                    ))}}
                  </section>

                  <section id="contact" className="handoff">
                    <div>
                      <h2>Next build path</h2>
                      <p>{{profile.spotlight}}</p>
                    </div>
                    <ol>
                      {{profile.process.map((step) => (
                        <li key={{step}}>{{step}}</li>
                      ))}}
                    </ol>
                  </section>
                </main>
              );
            }}
            """
        )

    @staticmethod
    def _vite_styles() -> str:
        return _strip(
            """
            :root {
              color: #eef4fb;
              background: #071018;
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }

            * {
              box-sizing: border-box;
            }

            html {
              scroll-behavior: smooth;
            }

            body {
              min-width: 320px;
              min-height: 100vh;
              margin: 0;
              background:
                radial-gradient(circle at 80% 10%, rgba(39, 221, 123, 0.16), transparent 28rem),
                linear-gradient(135deg, rgba(15, 30, 45, 0.92), rgba(7, 14, 24, 0.98)),
                #071018;
            }

            a {
              color: inherit;
              text-decoration: none;
            }

            .shell {
              width: min(1180px, calc(100vw - 32px));
              margin: 0 auto;
              padding: 24px 0 48px;
            }

            .topbar,
            .hero,
            .stats article,
            .services article,
            .handoff {
              border: 1px solid rgba(255, 255, 255, 0.12);
              background: rgba(255, 255, 255, 0.045);
            }

            .topbar {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 18px;
              padding: 16px;
            }

            .topbar div,
            .topbar strong,
            .topbar span {
              display: block;
            }

            .topbar span {
              color: #7dd3fc;
              font-size: 12px;
              text-transform: uppercase;
            }

            .topbar a,
            .primary,
            .secondary {
              border-radius: 6px;
              padding: 10px 14px;
              font-size: 14px;
              font-weight: 700;
            }

            .topbar a,
            .primary {
              background: #41e08f;
              color: #071018;
            }

            .secondary {
              border: 1px solid rgba(255, 255, 255, 0.16);
            }

            .hero {
              margin-top: 16px;
              padding: clamp(28px, 7vw, 78px);
            }

            .hero p {
              margin: 0 0 16px;
              color: #7dd3fc;
              font-size: 14px;
            }

            .hero h1 {
              max-width: 920px;
              margin: 0;
              font-size: clamp(38px, 7vw, 76px);
              line-height: 1;
              letter-spacing: 0;
            }

            .hero span {
              display: block;
              max-width: 760px;
              margin-top: 22px;
              color: #c1ccd8;
              line-height: 1.65;
            }

            .heroActions {
              display: flex;
              flex-wrap: wrap;
              gap: 12px;
              margin-top: 28px;
            }

            .stats,
            .services,
            .handoff {
              display: grid;
              gap: 14px;
              margin-top: 16px;
            }

            .stats {
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .stats article,
            .services article,
            .handoff {
              padding: 20px;
            }

            .stats strong {
              display: block;
              font-size: 32px;
            }

            .stats span,
            .services p,
            .handoff p,
            .handoff li {
              color: #c1ccd8;
              line-height: 1.6;
            }

            .services {
              grid-template-columns: repeat(4, minmax(0, 1fr));
            }

            .services article div {
              display: flex;
              align-items: start;
              justify-content: space-between;
              gap: 14px;
            }

            .services h2,
            .handoff h2 {
              margin: 0;
              font-size: 20px;
            }

            .services article div span {
              color: #41e08f;
              white-space: nowrap;
            }

            .handoff {
              grid-template-columns: 0.9fr 1.1fr;
            }

            .handoff ol {
              margin: 0;
              padding-left: 22px;
            }

            @media (max-width: 900px) {
              .stats,
              .services,
              .handoff {
                grid-template-columns: 1fr;
              }
            }
            """
        )

    @staticmethod
    def _default_plan_steps(
        preset: ProjectScaffoldPreset,
        project_name: str,
        install_command: str,
        validation_command: str,
    ) -> list[str]:
        return scaffold_default_plan_steps(preset, project_name, install_command, validation_command)

    @staticmethod
    def _inspection_detail(
        target: Path,
        existing_files: list[WorkspaceFile],
        profile: WorkspaceDependencyProfile,
    ) -> str:
        return scaffold_inspection_detail(target, existing_files, profile)

    @classmethod
    def _should_validate_existing_project_only(
        cls,
        prompt: str,
        target: Path,
        request: ProjectScaffoldRequest,
        profile: WorkspaceDependencyProfile,
    ) -> bool:
        return scaffold_should_validate_existing_project_only(
            prompt,
            target,
            run_validation=request.run_validation,
            profile=profile,
        )

    @staticmethod
    def _prompt_is_existing_project_validation_intent(prompt: str) -> bool:
        return scaffold_prompt_is_existing_project_validation_intent(prompt)

    @staticmethod
    def _existing_project_validation_command(
        target: Path,
        profile: WorkspaceDependencyProfile,
        preferred_command: str,
    ) -> str:
        return scaffold_existing_project_validation_command(target, profile, preferred_command)

    @classmethod
    def _continuity_preset_id(
        cls,
        *,
        prompt: str,
        target: Path,
        manifest: WorkspaceProjectManifest | None,
        profile: WorkspaceDependencyProfile,
    ) -> str:
        return scaffold_continuity_preset_id(
            prompt=prompt,
            target=target,
            manifest=manifest,
            profile=profile,
            known_preset_ids=[preset.id for preset in cls.presets()],
        )

    @classmethod
    def _prompt_should_reuse_existing_project(cls, prompt: str) -> bool:
        return scaffold_prompt_should_reuse_existing_project(prompt)

    @classmethod
    def _is_known_preset_id(cls, preset_id: str) -> bool:
        normalized = (preset_id or "").strip()
        if not normalized:
            return False
        return any(preset.id == normalized for preset in cls.presets())

    @staticmethod
    def _should_update_existing_scaffold(prompt: str, target: Path) -> bool:
        return scaffold_should_update_existing_scaffold(prompt, target)

    @staticmethod
    def _prompt_requests_validation(prompt: str) -> bool:
        return scaffold_prompt_requests_validation(prompt)

    @staticmethod
    def _prompt_negates_web_stack(prompt: str) -> bool:
        return scaffold_prompt_negates_web_stack(prompt)

    @staticmethod
    def _preset_stack_locks(preset_id: str) -> set[str]:
        return scaffold_preset_stack_locks(preset_id)

    @classmethod
    def _stack_locks_conflict_with_preset(cls, stack_locks: list[str], preset_id: str) -> bool:
        return scaffold_stack_locks_conflict_with_preset(stack_locks, preset_id)

    @classmethod
    def _prompt_allows_stack_switch(cls, prompt: str, stack_locks: list[str]) -> bool:
        return scaffold_prompt_allows_stack_switch(prompt, stack_locks)

    @classmethod
    def _stack_family_for_preset(cls, preset_id: str) -> str:
        return scaffold_stack_family_for_preset(preset_id)

    @staticmethod
    def _stack_lock_keywords_for_prompt(prompt: str) -> list[str]:
        return scaffold_stack_lock_keywords_for_prompt(prompt)

    @staticmethod
    def _risk_warnings_for_target(target: Path, *, overwrite: bool) -> list[str]:
        return scaffold_risk_warnings_for_target(target, overwrite=overwrite)

    @classmethod
    def _project_memory_files(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
        plan_steps: list[str],
        risk_warnings: list[str],
        existing_files: list[WorkspaceFile],
        existing_profile: WorkspaceDependencyProfile,
        planned_files: dict[str, str],
    ) -> dict[str, str]:
        return scaffold_project_memory_files(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            existing_files=existing_files,
            existing_profile=existing_profile,
            planned_files=planned_files,
        )

    @staticmethod
    def _diff_summary(files: list[ProjectScaffoldFile]) -> list[str]:
        return scaffold_diff_summary(files)

    def _record_runtime_memory(
        self,
        target: Path,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
        build_log_path: str,
        prompt: str,
        applied: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        try:
            files = self.workspace.scan(target, max_files=240)
            profile = self.workspace.inspect_dependency_profile(target)
            file_index = scaffold_runtime_file_index_payload(
                preset,
                project_name,
                files=files,
                profile=profile,
            )
            self._write_json_file(target / ".aegis" / "file_index.json", file_index)
        except OSError as exc:
            warnings.append(f"Could not refresh .aegis/file_index.json: {exc}")

        try:
            history_path = target / ".aegis" / "command_history.json"
            history = self._read_json_object(history_path, default={"schema": "aegis.command_history.v1", "commands": []})
            updated_history = scaffold_updated_command_history(
                history,
                checkpoint=checkpoint,
                install=install,
                validation=validation,
                install_command=install_command,
                validation_command=validation_command,
                build_log_path=build_log_path,
            )
            self._write_json_file(history_path, updated_history)
        except OSError as exc:
            warnings.append(f"Could not update .aegis/command_history.json: {exc}")

        if validation is not None and not self._command_ok(validation):
            try:
                known_path = target / ".aegis" / "known_errors.json"
                known = self._read_json_object(known_path, default={"schema": "aegis.known_errors.v1", "errors": []})
                updated_known_errors = scaffold_updated_known_errors(
                    known,
                    validation,
                    build_log_path=build_log_path,
                )
                self._write_json_file(known_path, updated_known_errors)
            except OSError as exc:
                warnings.append(f"Could not update .aegis/known_errors.json: {exc}")

        try:
            validation_plan = self._validation_plan_payload(
                preset,
                project_name,
                install_command=install_command,
                validation_command=validation_command,
                validation=validation,
                build_log_path=build_log_path,
            )
            self._write_json_file(target / ".aegis" / "validation_plan.json", validation_plan)
        except OSError as exc:
            warnings.append(f"Could not update .aegis/validation_plan.json: {exc}")

        try:
            instruction_files = self.workspace.discover_instruction_files(
                target,
                max_files=12,
                referenced_text=f"{prompt}\nTODO.md\nPROJECT_TODO.md\nTASKS.md\nBACKLOG.md",
            )
            if instruction_files:
                self._write_instruction_status_checkpoint(
                    target,
                    instruction_files,
                    prompt=prompt,
                    validation=validation,
                    validation_command=validation_command,
                    build_log_path=build_log_path,
                    applied=applied,
                )
        except (OSError, ValueError) as exc:
            warnings.append(f"Could not update .aegis/instruction_status.json: {exc}")
        return warnings

    def _write_instruction_status_checkpoint(
        self,
        target: Path,
        instruction_files: list[WorkspaceInstructionFile],
        *,
        prompt: str,
        validation: CommandRun | None,
        validation_command: str,
        build_log_path: str,
        applied: list[str],
    ) -> None:
        payload = scaffold_instruction_status_payload(
            instruction_files,
            prompt=prompt,
            validation=validation,
            validation_command=validation_command,
            build_log_path=build_log_path,
            applied=applied,
        )
        self._write_json_file(target / ".aegis" / "instruction_status.json", payload)

    @classmethod
    def _validation_plan_payload(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        install_command: str,
        validation_command: str,
        validation: CommandRun | None,
        build_log_path: str,
    ) -> dict[str, object]:
        return scaffold_validation_plan_payload(
            preset,
            project_name,
            install_command=install_command,
            validation_command=validation_command,
            validation=validation,
            build_log_path=build_log_path,
        )

    @staticmethod
    def _split_safe_command_chain(command: str) -> list[str]:
        return scaffold_split_safe_command_chain(command)

    @staticmethod
    def _validation_step_phase(command: str) -> str:
        return scaffold_validation_step_phase(command)

    @staticmethod
    def _validation_step_label(command: str, *, index: int, total: int) -> str:
        return scaffold_validation_step_label(command, index=index, total=total)

    @staticmethod
    def _failed_chain_step(validation: CommandRun) -> str:
        return scaffold_failed_chain_step(validation)

    @staticmethod
    def _failed_step_parts_from_steps(steps: list[dict[str, object]]) -> tuple[str, str]:
        return scaffold_failed_step_parts_from_steps(steps)

    @staticmethod
    def _status_text(value: object, *, default: str = "", limit: int = 220) -> str:
        return scaffold_status_text(value, default=default, limit=limit)

    @staticmethod
    def _read_json_object(path: Path, *, default: dict[str, object]) -> dict[str, object]:
        if not path.exists():
            return dict(default)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return dict(default)
        return payload if isinstance(payload, dict) else dict(default)

    @staticmethod
    def _write_json_file(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_build_log(
        self,
        target: Path,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
    ) -> str:
        return scaffold_write_build_log(
            target,
            preset=preset,
            project_name=project_name,
            checkpoint=checkpoint,
            install=install,
            validation=validation,
            install_command=install_command,
            validation_command=validation_command,
        )

    def _build_log_content(
        self,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
    ) -> str:
        return scaffold_build_log_content(
            preset=preset,
            project_name=project_name,
            checkpoint=checkpoint,
            install=install,
            validation=validation,
            install_command=install_command,
            validation_command=validation_command,
        )

    @classmethod
    def _command_log_section(cls, title: str, run: CommandRun) -> str:
        return scaffold_command_log_section(title, run)

    @staticmethod
    def _log_text(value: str, *, limit: int = 20000) -> str:
        return scaffold_log_text(value, limit=limit)

    @staticmethod
    def _diagnostics_log(diagnostics: list[dict[str, object]]) -> str:
        return scaffold_diagnostics_log(diagnostics)

    @staticmethod
    def _diagnostic_display(diagnostic: dict[str, object]) -> str:
        return scaffold_diagnostic_display(diagnostic)

    @staticmethod
    def _extract_validation_diagnostics(result: CommandResult, *, limit: int = 12) -> list[dict[str, object]]:
        return scaffold_extract_validation_diagnostics(result, limit=limit)

    @staticmethod
    def _normalize_diagnostic_path(path: str) -> str:
        return scaffold_normalize_diagnostic_path(path)

    @staticmethod
    def _to_positive_int(value: str | int | None) -> int | None:
        return scaffold_to_positive_int(value)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return scaffold_strip_ansi(text)

    @staticmethod
    def _error_signature(validation: CommandRun) -> str:
        return scaffold_error_signature(validation)

    @staticmethod
    def _markdown_list(items: list[str]) -> str:
        return scaffold_markdown_list(items)

    @staticmethod
    def _roadmap_files(
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
        max_repair_attempts: int,
    ) -> dict[str, str]:
        return scaffold_roadmap_files(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
            max_repair_attempts=max_repair_attempts,
        )

    @staticmethod
    def _aegis_handoff_files(
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
    ) -> dict[str, str]:
        return scaffold_aegis_handoff_files(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
        )

    @classmethod
    def _mission_contract(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
    ) -> dict[str, object]:
        return scaffold_mission_contract(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
        )

    @staticmethod
    def _numbered_list(items: list[str]) -> str:
        return scaffold_numbered_list(items)

    @staticmethod
    def _first_product_pass_items(preset: ProjectScaffoldPreset, prompt: str) -> list[str]:
        return scaffold_first_product_pass_items(preset, prompt)

    def _run_command_stage(
        self,
        *,
        stage_id: str,
        label: str,
        command: str,
        target: Path,
    ) -> tuple[ProjectBuildStage, CommandRun | None]:
        return scaffold_run_command_stage(
            self.commands,
            sandbox_profile=self.sandbox_profile,
            stage_id=stage_id,
            label=label,
            command=command,
            target=target,
        )

    @staticmethod
    def _command_run(result: CommandResult, *, label: str) -> CommandRun:
        return scaffold_command_run(result, label=label)

    @staticmethod
    def _command_ok(run: CommandRun) -> bool:
        return scaffold_command_ok(run)

    @staticmethod
    def _command_excerpt(run: CommandRun, *, limit: int = 1600) -> str:
        return scaffold_command_excerpt(run, limit=limit)

    @staticmethod
    def _categorize_command_result(result: CommandResult) -> str:
        return scaffold_categorize_command_result(result)

    @staticmethod
    def _summarize_command_result(result: CommandResult, *, category: str, label: str) -> str:
        return scaffold_summarize_command_result(result, category=category, label=label)

    @staticmethod
    def _visible_entries(target: Path) -> list[Path]:
        return scaffold_visible_entries(target)

    @staticmethod
    def _conflicting_paths(target: Path, files: dict[str, str]) -> list[str]:
        return scaffold_conflicting_paths(target, files)

    @classmethod
    def _has_non_metadata_entries(cls, target: Path) -> bool:
        return scaffold_has_non_metadata_entries(target, safe_metadata_paths=cls.SAFE_METADATA_REFRESH_PATHS)

    @staticmethod
    def _next_available_child_target(target: Path, project_name: str) -> Path:
        return scaffold_next_available_child_target(target, project_name)

    @staticmethod
    def _is_same_scaffold_project(target: Path, preset_id: str, project_name: str) -> bool:
        return scaffold_is_same_scaffold_project(target, preset_id, project_name)

    @classmethod
    def _is_metadata_only_refresh(cls, target: Path, conflicting_paths: list[str]) -> bool:
        return scaffold_is_metadata_only_refresh(target, conflicting_paths, safe_metadata_paths=cls.SAFE_METADATA_REFRESH_PATHS)

    @staticmethod
    def _command_for_project(command: str, project_name: str) -> str:
        return scaffold_command_for_project(command, project_name)

    @staticmethod
    def _should_install_before_validation(
        preset: ProjectScaffoldPreset,
        target: Path,
        *,
        install_command: str,
        validation_command: str,
        request: ProjectScaffoldRequest,
    ) -> bool:
        return scaffold_should_install_before_validation(
            preset,
            target,
            install_command=install_command,
            validation_command=validation_command,
            request=request,
        )

    @staticmethod
    def _has_explicit_project_name(prompt: str) -> bool:
        return scaffold_has_explicit_project_name(prompt)

    @staticmethod
    def _project_name(value: str) -> str:
        return scaffold_project_name(value)

    @classmethod
    def _preset_default_project_name_if_needed(cls, preset_id: str, raw_name: str) -> str:
        return scaffold_preset_default_project_name_if_needed(preset_id, raw_name)

    @classmethod
    def _looks_like_instructional_project_name(cls, slug: str) -> bool:
        return scaffold_looks_like_instructional_project_name(slug)

    @classmethod
    def _should_use_target_leaf_project_name(cls, preset_id: str, target_leaf: str) -> bool:
        return scaffold_should_use_target_leaf_project_name(preset_id, target_leaf)

    @classmethod
    def _target_leaf_is_specific(cls, target_leaf: str) -> bool:
        return scaffold_target_leaf_is_specific(target_leaf)

    @classmethod
    def _extract_windows_path_from_prompt(cls, prompt: str) -> str:
        return scaffold_extract_windows_path_from_prompt(prompt)

    @classmethod
    def _clean_windows_path_fragment(cls, value: str) -> str:
        return scaffold_clean_windows_path_fragment(value)

    @classmethod
    def _path_action_stop_positions(cls, candidate: str, *, before: int | None = None) -> list[int]:
        return scaffold_path_action_stop_positions(candidate, before=before)

    @classmethod
    def _path_stop_phrase_is_boundary(cls, lowered_candidate: str, position: int, phrase: str) -> bool:
        return scaffold_path_stop_phrase_is_boundary(lowered_candidate, position, phrase)

    @staticmethod
    def _path_action_boundary_preserves_leaf(candidate: str, action_position: int) -> bool:
        return scaffold_path_action_boundary_preserves_leaf(candidate, action_position)

    @classmethod
    def _path_instruction_separator_position(cls, candidate: str) -> int | None:
        return scaffold_path_instruction_separator_position(candidate)

    @classmethod
    def _trim_path_fragment(cls, candidate: str) -> str:
        return scaffold_trim_path_fragment(candidate)

    @staticmethod
    def _trailing_wrapper_belongs_to_path(candidate: str) -> bool:
        return scaffold_trailing_wrapper_belongs_to_path(candidate)

    @staticmethod
    def _path_fragment_exists(candidate: str) -> bool:
        return scaffold_path_fragment_exists(candidate)

    @classmethod
    def _prompt_without_windows_paths(cls, prompt: str, *, target_path: str = "") -> str:
        return scaffold_prompt_without_windows_paths(prompt, target_path=target_path)

    @classmethod
    def _project_name_from_prompt(cls, prompt: str) -> str:
        return scaffold_project_name_from_prompt(prompt)

    @staticmethod
    def _keyword_in_prompt(prompt: str, keyword: str) -> bool:
        term = (keyword or "").strip().lower()
        if not term:
            return False
        if re.fullmatch(r"[a-z0-9+#.]+", term):
            boundary = rf"(?<![a-z0-9+#.]){re.escape(term)}(?![a-z0-9+#.])"
            return re.search(boundary, prompt) is not None
        return term in prompt

    @classmethod
    def _select_preset(cls, prompt: str) -> tuple[ProjectScaffoldPreset, float, list[str], list[str]]:
        lowered = prompt.lower()
        web_negated = cls._prompt_negates_web_stack(prompt)
        rules: dict[str, list[str]] = {
            "nextjs-ts-tailwind": [
                "next",
                "next.js",
                "app router",
                "full stack",
                "full-stack",
                "saas",
                "dashboard",
                "website",
                "web app",
                "landing",
                "auth",
                "production web",
            ],
            "vite-react-ts": [
                "vite",
                "single page",
                "spa",
                "frontend",
                "client app",
                "react app",
                "portfolio",
                "static site",
            ],
            "static-html-site": [
                "static website",
                "static site",
                "html website",
                "html css",
                "plain html",
                "landing page",
                "business website",
                "brochure site",
                "marketing site",
                "portfolio site",
                "barber website",
                "salon website",
                "restaurant website",
                "website",
            ],
            "browser-extension-mv3": [
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "mv3",
                "content script",
                "background service worker",
                "extension popup",
                "popup extension",
            ],
            "vscode-extension-js": [
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "code extension",
                "extension command",
                "extension api",
                "developer extension",
            ],
            "node-cli-js": [
                "node cli",
                "node.js cli",
                "javascript cli",
                "js cli",
                "npm cli",
                "node command line",
                "node command-line",
                "node tool",
                "javascript tool",
                "package bin",
            ],
            "node-http-api-js": [
                "node http api",
                "node.js http api",
                "node api",
                "node.js api",
                "javascript api",
                "js api",
                "rest api",
                "json api",
                "http api",
                "api server",
                "backend api",
                "backend service",
            ],
            "node-fullstack-js": [
                "full stack",
                "full-stack",
                "full stack app",
                "full-stack app",
                "full application",
                "web app with api",
                "frontend and backend",
                "frontend backend",
                "dashboard app",
                "admin dashboard",
                "crud app",
                "crud dashboard",
                "task tracker",
                "project tracker",
                "inventory app",
                "booking app",
            ],
            "powershell-module": [
                "powershell",
                "ps1",
                "psm1",
                "psd1",
                "powershell module",
                "powershell script",
                "windows automation",
                "admin script",
                "automation module",
                "script module",
            ],
            "python-cli": [
                "cli",
                "command line",
                "command-line",
                "terminal",
                "automation",
                "script",
                "local tool",
                "python tool",
            ],
            "python-tkinter-desktop": [
                "tkinter",
                "python desktop",
                "desktop utility",
                "gui utility",
                "local desktop",
                "simple desktop",
                "lightweight desktop",
                "python gui",
                "stdlib gui",
            ],
            "python-stdlib-api": [
                "python rest api",
                "python json api",
                "python http api",
                "python backend api",
                "python backend service",
                "python api server",
                "stdlib api",
                "http.server",
                "no dependency python api",
                "dependency free python api",
            ],
            "fastapi-python-api": [
                "fastapi",
                "python api",
                "rest api",
                "api",
                "backend",
                "service",
                "microservice",
            ],
            "express-ts-api": [
                "express",
                "node",
                "node.js",
                "typescript api",
                "ts api",
                "rest api",
                "api",
                "backend",
                "service",
            ],
            "sqlite-python-db": [
                "database",
                "sqlite",
                "sqlite3",
                "sql",
                "schema",
                "migration",
                "migrations",
                "seed data",
                "data model",
                "crud",
                "queries",
                "tables",
            ],
            "electron-react-ts": [
                "electron",
                "desktop app",
                "desktop",
                "native desktop",
                "windows app",
                "cross-platform desktop",
                "preload",
            ],
            "expo-react-native-ts": [
                "expo",
                "react native",
                "react-native",
                "mobile",
                "ios",
                "android",
                "phone app",
                "tablet",
            ],
            "django-python-web": [
                "django",
                "python web",
                "server rendered",
                "admin panel",
                "cms",
                "models",
                "views",
            ],
            "cpp-cmake-cli": [
                "c++",
                "cpp",
                "cmake",
                "native",
                "binary",
                "desktop cli",
                "console app",
                "console application",
                "command line",
                "command-line",
                "hello world",
            ],
            "cpp-cmake-dll": [
                "dll",
                "shared library",
                "dynamic library",
                "native library",
                "plugin library",
                "library",
                "exports",
                "exported function",
            ],
            "cpp-imgui-win32-dx11": [
                "imgui",
                "dear imgui",
                "immediate mode gui",
                "immediate-mode gui",
                "debug overlay",
                "game editor",
                "editor tool",
                "tooling gui",
                "win32 gui",
                "directx11",
                "directx 11",
            ],
            "cpp-game-loop-cmake": [
                "game loop",
                "game engine",
                "game development",
                "game dev",
                "ecs",
                "entity component",
                "simulation",
                "asset registry",
                "level system",
                "gameplay system",
                "native game",
            ],
            "python-game-file-analyzer": [
                "game file",
                "game files",
                "asset file",
                "asset files",
                "asset bundle",
                "asset bundles",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse-engineer",
                "reverse engineering",
                "pak",
                "wad",
                "bundle",
                "archive",
                "strings",
                "entropy",
                "hex",
            ],
            "cpp-msvc-console-sln": [
                "visual studio",
                ".sln",
                "sln",
                "solution",
                "vcxproj",
                "msbuild",
                "console project",
                "windows console",
            ],
            "cpp-windows-service": [
                "windows service",
                "win32 service",
                "service control manager",
                "scm",
                "background service",
                "system service",
                "service app",
                "service application",
                "install service",
                "uninstall service",
            ],
            "cpp-windows-internals-hooking": [
                "windows internals",
                "win32 internals",
                "ntdll",
                "winapi",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "process modules",
                "module enumeration",
                "export table",
                "iat",
                "eiat",
            ],
            "python-sln-refactor-tool": [
                "merge sln",
                "merge two sln",
                "merge solutions",
                "combine sln",
                "combine projects",
                "combine solutions",
                "split sln",
                "split solution",
                "split a project",
                "separate project",
                "extract project",
                "into its own sln",
                "solution refactor",
                "solution merger",
                "solution splitter",
                "vcxproj refactor",
            ],
            "windows-kernel-driver-controller": [
                "kernel driver",
                "driver",
                "wdk",
                "syscall",
                "syscalls",
                "ioctl",
                "deviceiocontrol",
                "kernel",
                "ring0",
                "desktop app controller",
            ],
            "rust-cli": [
                "rust",
                "cargo",
                "rust cli",
                "native cli",
                "systems",
                "binary",
            ],
            "go-http-api": [
                "golang",
                "go api",
                "go service",
                "go http",
                "net/http",
                "go backend",
            ],
            "dotnet-webapi-csharp": [
                "asp.net",
                "aspnet",
                ".net",
                "dotnet",
                "c#",
                "csharp",
                "minimal api",
                "web api",
            ],
            "dotnet-console-csharp": [
                "c# console",
                "csharp console",
                ".net console",
                "dotnet console",
                "c# cli",
                "csharp cli",
                "dotnet cli",
                "c# exe",
                ".net exe",
                "console app",
                "console application",
            ],
            "dotnet-wpf-csharp": [
                "wpf",
                "xaml",
                "c# desktop",
                "csharp desktop",
                ".net desktop",
                "dotnet desktop",
                "windows desktop app",
                "windows gui",
                "desktop gui",
            ],
            "tauri-react-ts": [
                "tauri",
                "rust desktop",
                "lightweight desktop",
                "small desktop",
                "desktop rust",
            ],
        }
        if web_negated:
            web_terms = {
                "website",
                "web app",
                "landing",
                "landing page",
                "static website",
                "static site",
                "html website",
                "business website",
                "brochure site",
                "marketing site",
                "portfolio site",
                "barber website",
                "salon website",
                "restaurant website",
                "production web",
            }
            for preset_id in ("nextjs-ts-tailwind", "vite-react-ts", "static-html-site", "node-fullstack-js"):
                rules[preset_id] = [term for term in rules.get(preset_id, []) if term not in web_terms]
        scores = {preset.id: 0 for preset in cls.presets()}
        hits: dict[str, list[str]] = {preset_id: [] for preset_id in scores}
        for preset_id, terms in rules.items():
            for term in terms:
                if cls._keyword_in_prompt(lowered, term):
                    scores[preset_id] += 3 if len(term) > 4 else 2
                    hits[preset_id].append(term)

        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "node")
            or cls._keyword_in_prompt(lowered, "express")
            or cls._keyword_in_prompt(lowered, "typescript")
            or cls._keyword_in_prompt(lowered, "ts")
        ):
            scores["express-ts-api"] += 5
            hits["express-ts-api"].append("api + node/typescript")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "python") or cls._keyword_in_prompt(lowered, "fastapi")
        ):
            scores["fastapi-python-api"] += 5
            hits["fastapi-python-api"].append("api + python")
        if (
            cls._keyword_in_prompt(lowered, "python")
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("api", "rest api", "json api", "http api", "backend", "service", "crud")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("fastapi", "django", "flask", "react", "next", "vite", "desktop", "tkinter")
            )
        ):
            scores["python-stdlib-api"] += 14
            hits["python-stdlib-api"].append("dependency-free python api")
        if (
            cls._keyword_in_prompt(lowered, "react")
            and not cls._keyword_in_prompt(lowered, "next")
            and "full stack" not in lowered
            and "full-stack" not in lowered
        ):
            scores["vite-react-ts"] += 3
            hits["vite-react-ts"].append("react client")
        if (
            not web_negated
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "website",
                    "web site",
                    "landing page",
                    "business website",
                    "brochure site",
                    "marketing site",
                    "portfolio site",
                    "barber website",
                    "salon website",
                    "restaurant website",
                    "static site",
                    "static website",
                    "html website",
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "next",
                    "next.js",
                    "react",
                    "vite",
                    "full stack",
                    "full-stack",
                    "dashboard",
                    "saas",
                    "auth",
                    "api",
                    "backend",
                    "electron",
                    "tauri",
                    "mobile",
                    "django",
                )
            )
        ):
            scores["static-html-site"] += 10
            hits["static-html-site"].append("dependency-free website")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "content script",
                "background service worker",
                "extension popup",
            )
        ):
            scores["browser-extension-mv3"] += 16
            hits["browser-extension-mv3"].append("browser extension")
        if (
            cls._keyword_in_prompt(lowered, "extension")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("chrome", "edge", "browser", "web"))
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("vscode", "visual studio code"))
        ):
            scores["browser-extension-mv3"] += 9
            hits["browser-extension-mv3"].append("extension target")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "extension command",
                "extension api",
            )
        ):
            scores["vscode-extension-js"] += 16
            hits["vscode-extension-js"].append("vs code extension")
        if (
            cls._keyword_in_prompt(lowered, "extension")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("vscode", "vs code", "visual studio code"))
        ):
            scores["vscode-extension-js"] += 10
            hits["vscode-extension-js"].append("developer tool extension")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("node", "node.js", "javascript", "js", "npm"))
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("cli", "command line", "command-line", "local tool", "automation", "package bin", "executable")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "express", "web api", "rest api", "browser extension"))
        ):
            scores["node-cli-js"] += 12
            hits["node-cli-js"].append("node cli/tool")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("rest api", "json api", "http api", "api server", "backend api", "backend service")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "express",
                    "typescript",
                    "ts api",
                    "fastapi",
                    "python",
                    "django",
                    "go",
                    "golang",
                    ".net",
                    "dotnet",
                    "c#",
                    "csharp",
                    "asp.net",
                )
            )
        ):
            scores["node-http-api-js"] += 12
            hits["node-http-api-js"].append("dependency-free node api")
        if (
            not web_negated
            and (
                any(
                    cls._keyword_in_prompt(lowered, term)
                    for term in (
                        "full stack",
                        "full-stack",
                        "web app with api",
                        "frontend and backend",
                        "frontend backend",
                        "crud app",
                        "crud dashboard",
                        "task tracker",
                        "project tracker",
                        "inventory app",
                        "booking app",
                    )
                )
                or (
                    any(cls._keyword_in_prompt(lowered, term) for term in ("dashboard", "web app", "admin"))
                    and any(cls._keyword_in_prompt(lowered, term) for term in ("crud", "api", "backend", "database", "json persistence", "tasks"))
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "next",
                    "next.js",
                    "react",
                    "vite",
                    "express",
                    "typescript",
                    "fastapi",
                    "python",
                    "django",
                    "go",
                    "golang",
                    ".net",
                    "dotnet",
                    "c#",
                    "csharp",
                    "electron",
                    "tauri",
                    "mobile",
                    "react native",
                )
            )
        ):
            scores["node-fullstack-js"] += 14
            hits["node-fullstack-js"].append("dependency-free full-stack app")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "powershell",
                    "ps1",
                    "psm1",
                    "psd1",
                    "powershell module",
                    "powershell script",
                    "windows automation",
                    "admin script",
                    "automation module",
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "kernel",
                    "driver",
                    "windows service",
                    "win32 service",
                    "c++",
                    "cpp",
                    "c#",
                    "csharp",
                    ".net",
                    "dotnet",
                    "wpf",
                    "xaml",
                    "api",
                    "web app",
                    "website",
                )
            )
        ):
            scores["powershell-module"] += 14
            hits["powershell-module"].append("powershell automation")
        if cls._keyword_in_prompt(lowered, "react") and (
            cls._keyword_in_prompt(lowered, "electron") or cls._keyword_in_prompt(lowered, "desktop")
        ):
            scores["electron-react-ts"] += 6
            hits["electron-react-ts"].append("react desktop")
        if cls._keyword_in_prompt(lowered, "react") and (
            cls._keyword_in_prompt(lowered, "mobile")
            or cls._keyword_in_prompt(lowered, "native")
            or cls._keyword_in_prompt(lowered, "expo")
        ):
            scores["expo-react-native-ts"] += 6
            hits["expo-react-native-ts"].append("react mobile")
        if cls._keyword_in_prompt(lowered, "python") and (
            cls._keyword_in_prompt(lowered, "django")
            or cls._keyword_in_prompt(lowered, "admin")
            or "server rendered" in lowered
        ):
            scores["django-python-web"] += 6
            hits["django-python-web"].append("python django web")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("tkinter", "python desktop", "python gui", "desktop utility", "gui utility")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react native", "web"))
        ):
            scores["python-tkinter-desktop"] += 12
            hits["python-tkinter-desktop"].append("python desktop gui")
        if (
            cls._keyword_in_prompt(lowered, "desktop")
            and cls._keyword_in_prompt(lowered, "python")
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react"))
        ):
            scores["python-tkinter-desktop"] += 8
            hits["python-tkinter-desktop"].append("python desktop")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "go") or cls._keyword_in_prompt(lowered, "golang")
        ):
            scores["go-http-api"] += 7
            hits["go-http-api"].append("api + go")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("database", "sqlite", "sqlite3", "schema", "migration", "migrations", "crud")
        ):
            scores["sqlite-python-db"] += 10
            hits["sqlite-python-db"].append("database project")
        if cls._keyword_in_prompt(lowered, "sql") and not any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("asp.net", ".net", "dotnet", "c#", "csharp")
        ):
            scores["sqlite-python-db"] += 4
            hits["sqlite-python-db"].append("sql")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, ".net")
            or cls._keyword_in_prompt(lowered, "dotnet")
            or cls._keyword_in_prompt(lowered, "c#")
            or cls._keyword_in_prompt(lowered, "csharp")
        ):
            scores["dotnet-webapi-csharp"] += 7
            hits["dotnet-webapi-csharp"].append("api + dotnet/csharp")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in (".net", "dotnet", "c#", "csharp"))
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("console", "cli", "command line", "command-line", "exe", "executable", "local tool")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "asp.net", "web api", "http"))
        ):
            scores["dotnet-console-csharp"] += 12
            hits["dotnet-console-csharp"].append("c# console/exe")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("wpf", "xaml", "c# desktop", "csharp desktop", ".net desktop", "dotnet desktop"))
            or (
                cls._keyword_in_prompt(lowered, "desktop")
                and any(cls._keyword_in_prompt(lowered, term) for term in ("c#", "csharp", ".net", "dotnet"))
                and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react", "api"))
            )
        ):
            scores["dotnet-wpf-csharp"] += 14
            hits["dotnet-wpf-csharp"].append("c# wpf desktop")
        if cls._keyword_in_prompt(lowered, "react") and cls._keyword_in_prompt(lowered, "tauri"):
            scores["tauri-react-ts"] += 12
            hits["tauri-react-ts"].append("tauri react desktop")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("sln", "solution", "visual studio", "vcxproj", "msbuild")
        ):
            scores["cpp-msvc-console-sln"] += 12
            hits["cpp-msvc-console-sln"].append("c++ visual studio solution")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "dll",
                "dll host",
                "shared library",
                "dynamic library",
                "native library",
                "plugin library",
                "plugin host",
                "exported api",
                "exported symbols",
                "loadlibrary",
                "getprocaddress",
            )
        ):
            scores["cpp-cmake-dll"] += 18
            hits["cpp-cmake-dll"].append("c++ dll/shared library with host loader")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("dll", "shared library", "dynamic library", "native library", "plugin library")
        ) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("native", "plugin", "project", "existing", "library", "refine", "optimize", "clean up")
        ):
            scores["cpp-cmake-dll"] += 14
            hits["cpp-cmake-dll"].append("native dll/plugin library")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "imgui",
                "dear imgui",
                "immediate mode gui",
                "immediate-mode gui",
                "debug overlay",
                "game editor",
                "editor tool",
                "tooling gui",
            )
        ):
            scores["cpp-imgui-win32-dx11"] += 18
            hits["cpp-imgui-win32-dx11"].append("dear imgui game/tooling ui")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("game loop", "game engine", "game development", "game dev", "ecs", "entity component", "simulation")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("website", "web app", "api", "backend", "mobile", "react", "next", "vite")
            )
        ):
            scores["cpp-game-loop-cmake"] += 14
            hits["cpp-game-loop-cmake"].append("native game loop")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "game file",
                "game files",
                "asset file",
                "asset files",
                "asset bundle",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse-engineer",
                "reverse engineering",
                "pak",
                "wad",
                "hex",
                "entropy",
            )
        ):
            scores["python-game-file-analyzer"] += 18
            hits["python-game-file-analyzer"].append("game file/asset analysis")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and cls._keyword_in_prompt(lowered, "console"):
            if any(cls._keyword_in_prompt(lowered, term) for term in ("sln", "solution", "visual studio", "vcxproj", "msbuild")):
                scores["cpp-msvc-console-sln"] += 4
                hits["cpp-msvc-console-sln"].append("c++ console solution")
            else:
                scores["cpp-cmake-cli"] += 14
                hits["cpp-cmake-cli"].append("c++ console app")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "windows service",
                "win32 service",
                "service control manager",
                "background service",
                "system service",
                "install service",
                "uninstall service",
            )
        ):
            scores["cpp-windows-service"] += 16
            hits["cpp-windows-service"].append("windows service")
        if (
            cls._keyword_in_prompt(lowered, "service")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("windows", "win32", "native", "c++", "cpp"))
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "http", "rest", "fastapi", "express"))
        ):
            scores["cpp-windows-service"] += 8
            hits["cpp-windows-service"].append("native service app")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "windows internals",
                "win32 internals",
                "ntdll",
                "winapi",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "process modules",
                "module enumeration",
                "export table",
                "iat",
            )
        ):
            scores["cpp-windows-internals-hooking"] += 18
            hits["cpp-windows-internals-hooking"].append("windows internals/instrumentation")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "merge sln",
                "merge two sln",
                "merge solutions",
                "combine sln",
                "combine projects",
                "combine solutions",
                "split sln",
                "split solution",
                "split a project",
                "separate project",
                "extract project",
                "into its own sln",
                "solution refactor",
                "solution merger",
                "solution splitter",
            )
        ):
            scores["python-sln-refactor-tool"] += 34
            hits["python-sln-refactor-tool"].append("visual studio solution merge/split")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("merge", "combine", "split", "separate", "extract"))
            and any(cls._keyword_in_prompt(lowered, term) for term in ("sln", "solution", "solutions", "vcxproj", "project"))
        ):
            scores["python-sln-refactor-tool"] += 22
            hits["python-sln-refactor-tool"].append("visual studio solution merge/split")
            hits["python-sln-refactor-tool"].append("solution project restructuring")
        if "kernel driver" in lowered or ("driver" in lowered and ("kernel" in lowered or "wdk" in lowered)):
            scores["windows-kernel-driver-controller"] += 16
            hits["windows-kernel-driver-controller"].append("windows kernel driver")
        if ("controller" in lowered or "desktop app" in lowered) and ("kernel" in lowered or "driver" in lowered):
            scores["windows-kernel-driver-controller"] += 8
            hits["windows-kernel-driver-controller"].append("driver controller app")
        if ("syscall" in lowered or "syscalls" in lowered or "communication" in lowered) and ("kernel" in lowered or "driver" in lowered):
            scores["windows-kernel-driver-controller"] += 5
            hits["windows-kernel-driver-controller"].append("user/kernel communication")
        generic_app = re.search(r"\b(app|application|program|software)\b", lowered) is not None
        web_or_service_context = any(
            term in lowered
            for term in (
                "website",
                "web site",
                "web app",
                "frontend",
                "landing",
                "landing page",
                "static website",
                "static site",
                "business website",
                "brochure site",
                "dashboard",
                "saas",
                "api",
                "backend",
                "service",
                "mobile",
                "phone",
                "ios",
                "android",
                "react native",
                "expo",
                "tauri",
                "electron",
                "next",
                "vite",
                "react app",
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "content script",
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "node cli",
                "node.js cli",
                "javascript cli",
                "node tool",
                "powershell",
                "ps1",
                "psm1",
                "powershell module",
                "windows automation",
                "admin script",
                "driver",
                "kernel",
                "wdk",
                "tkinter",
                "python desktop",
                "desktop utility",
                "gui utility",
                "wpf",
                "xaml",
                "c# desktop",
                ".net desktop",
                "windows service",
                "win32 service",
                "background service",
                "system service",
                "windows internals",
                "win32 internals",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "merge sln",
                "merge solutions",
                "combine sln",
                "combine solutions",
                "split sln",
                "split solution",
                "solution refactor",
                "c++",
                "cpp",
                "cmake",
                "console",
                "dll",
                "imgui",
                "dear imgui",
                "game loop",
                "game engine",
                "game development",
                "game dev",
                "asset registry",
                "game file",
                "asset file",
                "asset bundle",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse engineering",
                "full stack",
                "full-stack",
                "crud",
                "task tracker",
                "project tracker",
                "inventory app",
                "booking app",
                "library",
                "shared library",
                "dynamic library",
                "database",
                "sqlite",
                "schema",
                "sql",
            )
        )
        if generic_app and not web_or_service_context:
            scores["electron-react-ts"] += 4
            hits["electron-react-ts"].append("generic application")
        if "full project" in lowered or "full app" in lowered or "from scratch" in lowered:
            scores["nextjs-ts-tailwind"] += 2
            hits["nextjs-ts-tailwind"].append("full project")

        ranked_ids = [
            "windows-kernel-driver-controller",
            "tauri-react-ts",
            "expo-react-native-ts",
            "dotnet-wpf-csharp",
            "electron-react-ts",
            "vscode-extension-js",
            "browser-extension-mv3",
            "dotnet-webapi-csharp",
            "dotnet-console-csharp",
            "go-http-api",
            "sqlite-python-db",
            "python-sln-refactor-tool",
            "python-game-file-analyzer",
            "cpp-windows-internals-hooking",
            "cpp-imgui-win32-dx11",
            "cpp-game-loop-cmake",
            "cpp-windows-service",
            "cpp-msvc-console-sln",
            "cpp-cmake-dll",
            "cpp-cmake-cli",
            "rust-cli",
            "django-python-web",
            "node-fullstack-js",
            "node-http-api-js",
            "powershell-module",
            "express-ts-api",
            "fastapi-python-api",
            "node-cli-js",
            "python-tkinter-desktop",
            "python-stdlib-api",
            "static-html-site",
            "nextjs-ts-tailwind",
            "vite-react-ts",
            "python-cli",
        ]
        best_id = max(ranked_ids, key=lambda preset_id: scores[preset_id])
        if scores[best_id] == 0:
            best_id = "nextjs-ts-tailwind"
            hits[best_id].append("default full project")

        preset = cls._preset_for(best_id)
        best_hits = list(dict.fromkeys(hits[best_id]))
        score = scores[best_id]
        confidence = min(0.94, 0.52 + (score * 0.045))
        reasons = [
            f"Selected {preset.label} because the prompt matched: {', '.join(best_hits)}."
            if best_hits
            else f"Selected {preset.label} as the safest general starter.",
            f"Default install command: {preset.install_command or 'none required'}.",
            f"Default validation command: {preset.validation_command or 'not configured'}.",
        ]
        return preset, confidence, reasons, best_hits

    @staticmethod
    def _python_package_name(project_name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", project_name.replace("-", "_")).strip("_").lower()
        if not cleaned:
            return "aegis_app"
        if cleaned[0].isdigit():
            cleaned = f"app_{cleaned}"
        return cleaned

    @staticmethod
    def _manifest_package_name(project_name: str, fallback_prefix: str = "aegis") -> str:
        cleaned = ProjectScaffolder._project_name(project_name)
        if cleaned[0].isdigit():
            cleaned = f"{fallback_prefix}-{cleaned}"
        return cleaned

    @staticmethod
    def _nextjs_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "scripts": {{
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "lint": "next lint",
                    "typecheck": "tsc --noEmit"
                  }},
                  "dependencies": {{
                    "next": "15.5.15",
                    "react": "19.2.5",
                    "react-dom": "19.2.5"
                  }},
                  "devDependencies": {{
                    "@types/node": "^22.10.1",
                    "@types/react": "^19.2.14",
                    "@types/react-dom": "^19.2.3",
                    "autoprefixer": "^10.4.20",
                    "eslint": "^9.16.0",
                    "eslint-config-next": "15.5.15",
                    "postcss": "^8.4.49",
                    "tailwindcss": "^3.4.19",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2017",
                    "lib": ["dom", "dom.iterable", "esnext"],
                    "allowJs": false,
                    "skipLibCheck": true,
                    "strict": true,
                    "noEmit": true,
                    "esModuleInterop": true,
                    "module": "esnext",
                    "moduleResolution": "bundler",
                    "resolveJsonModule": true,
                    "isolatedModules": true,
                    "jsx": "preserve",
                    "incremental": true,
                    "plugins": [{ "name": "next" }],
                    "paths": { "@/*": ["./*"] }
                  },
                  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
                  "exclude": ["node_modules"]
                }
                """
            ),
            "next.config.mjs": _strip(
                """
                /** @type {import('next').NextConfig} */
                const nextConfig = {
                  reactStrictMode: true
                };

                export default nextConfig;
                """
            ),
            "postcss.config.mjs": _strip(
                """
                const config = {
                  plugins: {
                    tailwindcss: {},
                    autoprefixer: {}
                  }
                };

                export default config;
                """
            ),
            "tailwind.config.ts": _strip(
                """
                import type { Config } from "tailwindcss";

                const config: Config = {
                  content: [
                    "./app/**/*.{js,ts,jsx,tsx,mdx}",
                    "./components/**/*.{js,ts,jsx,tsx,mdx}"
                  ],
                  theme: {
                    extend: {
                      colors: {
                        ink: "#09111d",
                        signal: "#27dd7b",
                        cobalt: "#6aa7ff",
                        amber: "#e0b15f"
                      }
                    }
                  },
                  plugins: []
                };

                export default config;
                """
            ),
            "app/layout.tsx": _strip(
                f"""
                import type {{ Metadata }} from "next";
                import type {{ ReactNode }} from "react";
                import "./globals.css";

                export const metadata: Metadata = {{
                  title: "{title}",
                  description: "A production-ready application scaffold generated by Aegis."
                }};

                export default function RootLayout({{
                  children
                }}: Readonly<{{
                  children: ReactNode;
                }}>) {{
                  return (
                    <html lang="en">
                      <body>{{children}}</body>
                    </html>
                  );
                }}
                """
            ),
            "app/page.tsx": _strip(
                """
                import { AppShell } from "@/components/app-shell";

                export default function Home() {
                  return <AppShell />;
                }
                """
            ),
            "app/globals.css": _strip(
                """
                @tailwind base;
                @tailwind components;
                @tailwind utilities;

                :root {
                  color-scheme: dark;
                  background: #060b12;
                  color: #edf3f8;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  min-height: 100vh;
                  margin: 0;
                  background:
                    linear-gradient(120deg, rgba(21, 34, 51, 0.88), rgba(7, 12, 20, 0.96)),
                    #060b12;
                  font-family: Arial, Helvetica, sans-serif;
                }
                """
            ),
            "components/app-shell.tsx": _strip(
                f"""
                const metrics = [
                  ["Ship readiness", "86%", "Validation profile saved"],
                  ["Open tasks", "12", "Prioritized for the next pass"],
                  ["Latency budget", "240ms", "Client interactions stay fast"]
                ];

                const actions = [
                  "Define the first real user workflow",
                  "Connect authentication and persistence",
                  "Add CI validation before release"
                ];

                export function AppShell() {{
                  return (
                    <main className="min-h-screen px-6 py-6 text-slate-100">
                      <section className="mx-auto flex max-w-6xl flex-col gap-6">
                        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
                          <div>
                            <p className="text-sm text-emerald-300">Aegis project scaffold</p>
                            <h1 className="mt-2 text-4xl font-semibold tracking-normal">{title}</h1>
                            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                              A clean starting point for a real product: typed components, responsive layout,
                              validation wiring, and space for the first feature pass.
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <button className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950">
                              New workflow
                            </button>
                            <button className="rounded-lg border border-white/14 px-4 py-2 text-sm text-slate-200">
                              Review plan
                            </button>
                          </div>
                        </header>

                        <section className="grid gap-3 md:grid-cols-3">
                          {{metrics.map(([label, value, detail]) => (
                            <article key={{label}} className="rounded-lg border border-white/10 bg-white/[0.045] p-4">
                              <p className="text-xs uppercase tracking-normal text-slate-400">{{label}}</p>
                              <p className="mt-3 text-2xl font-semibold">{{value}}</p>
                              <p className="mt-2 text-sm text-slate-300">{{detail}}</p>
                            </article>
                          ))}}
                        </section>

                        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                          <div className="rounded-lg border border-white/10 bg-slate-950/40 p-5">
                            <h2 className="text-lg font-semibold">Product cockpit</h2>
                            <div className="mt-5 grid gap-3">
                              {{["Design the core entity model", "Build the API surface", "Harden permissions"].map((item, index) => (
                                <div key={{item}} className="flex items-center justify-between rounded-lg border border-white/10 bg-slate-900/70 px-4 py-3">
                                  <span className="text-sm text-slate-200">{{item}}</span>
                                  <span className="text-xs text-slate-400">Step {{index + 1}}</span>
                                </div>
                              ))}}
                            </div>
                          </div>

                          <aside className="rounded-lg border border-white/10 bg-white/[0.045] p-5">
                            <h2 className="text-lg font-semibold">Next actions</h2>
                            <ul className="mt-4 space-y-3">
                              {{actions.map((action) => (
                                <li key={{action}} className="rounded-lg bg-slate-950/50 p-3 text-sm text-slate-300">
                                  {{action}}
                                </li>
                              ))}}
                            </ul>
                          </aside>
                        </section>
                      </section>
                    </main>
                  );
                }}
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                .next
                out
                dist
                .env
                .env.local
                npm-debug.log*
                pnpm-debug.log*
                yarn-debug.log*
                yarn-error.log*
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                This project was generated by Aegis Project Builder.

                ## Getting started

                ```bash
                npm install
                npm run dev
                ```

                ## Validation

                ```bash
                npm run build
                ```
                """
            ),
        }

    @staticmethod
    def _vite_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "type": "module",
                  "scripts": {{
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "preview": "vite preview",
                    "typecheck": "tsc -b"
                  }},
                  "dependencies": {{
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0"
                  }},
                  "devDependencies": {{
                    "@vitejs/plugin-react": "^4.3.4",
                    "@types/react": "^19.0.1",
                    "@types/react-dom": "^19.0.1",
                    "vite": "^6.0.3",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                    <title>{title}</title>
                  </head>
                  <body>
                    <div id="root"></div>
                    <script type="module" src="/src/main.tsx"></script>
                  </body>
                </html>
                """
            ),
            "vite.config.ts": _strip(
                """
                import { defineConfig } from "vite";
                import react from "@vitejs/plugin-react";

                export default defineConfig({
                  plugins: [react()]
                });
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": true,
                    "lib": ["DOM", "DOM.Iterable", "ES2020"],
                    "allowJs": false,
                    "skipLibCheck": true,
                    "esModuleInterop": true,
                    "allowSyntheticDefaultImports": true,
                    "strict": true,
                    "forceConsistentCasingInFileNames": true,
                    "module": "ESNext",
                    "moduleResolution": "Node",
                    "resolveJsonModule": true,
                    "isolatedModules": true,
                    "noEmit": true,
                    "jsx": "react-jsx"
                  },
                  "include": ["src"],
                  "references": []
                }
                """
            ),
            "src/main.tsx": _strip(
                """
                import React from "react";
                import ReactDOM from "react-dom/client";
                import { App } from "./App";
                import "./styles.css";

                ReactDOM.createRoot(document.getElementById("root")!).render(
                  <React.StrictMode>
                    <App />
                  </React.StrictMode>
                );
                """
            ),
            "src/App.tsx": _strip(
                f"""
                const workstreams = [
                  ["Architecture", "Define data flows and API boundaries"],
                  ["Interface", "Build the first complete user path"],
                  ["Quality", "Add validation before expanding features"]
                ];

                export function App() {{
                  return (
                    <main className="shell">
                      <header className="hero">
                        <p>Aegis Vite scaffold</p>
                        <h1>{title}</h1>
                        <span>Ready for a focused first implementation pass.</span>
                      </header>

                      <section className="grid">
                        {{workstreams.map(([title, detail]) => (
                          <article key={{title}} className="panel">
                            <strong>{{title}}</strong>
                            <span>{{detail}}</span>
                          </article>
                        ))}}
                      </section>
                    </main>
                  );
                }}
                """
            ),
            "src/styles.css": _strip(
                """
                :root {
                  color: #eef4fb;
                  background: #07101a;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  min-width: 320px;
                  min-height: 100vh;
                  margin: 0;
                  background:
                    linear-gradient(135deg, rgba(31, 46, 66, 0.88), rgba(7, 14, 24, 0.96)),
                    #07101a;
                }

                .shell {
                  width: min(1120px, calc(100vw - 32px));
                  margin: 0 auto;
                  padding: 40px 0;
                }

                .hero {
                  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                  padding-bottom: 28px;
                }

                .hero p {
                  margin: 0 0 12px;
                  color: #43e08b;
                  font-size: 14px;
                }

                .hero h1 {
                  margin: 0;
                  font-size: 48px;
                  line-height: 1.04;
                  letter-spacing: 0;
                }

                .hero span {
                  display: block;
                  max-width: 660px;
                  margin-top: 16px;
                  color: #b9c5d3;
                }

                .grid {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 14px;
                  margin-top: 24px;
                }

                .panel {
                  min-height: 138px;
                  border: 1px solid rgba(255, 255, 255, 0.12);
                  border-radius: 8px;
                  background: rgba(255, 255, 255, 0.045);
                  padding: 18px;
                }

                .panel strong,
                .panel span {
                  display: block;
                }

                .panel span {
                  margin-top: 12px;
                  color: #b9c5d3;
                  line-height: 1.55;
                }

                @media (max-width: 760px) {
                  .grid {
                    grid-template-columns: 1fr;
                  }

                  .hero h1 {
                    font-size: 36px;
                  }
                }
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                .env
                .env.local
                npm-debug.log*
                pnpm-debug.log*
                yarn-debug.log*
                yarn-error.log*
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Generated by Aegis Project Builder.

                ```bash
                npm install
                npm run dev
                ```

                Validate with:

                ```bash
                npm run build
                ```
                """
            ),
        }

    @staticmethod
    def _static_html_site_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-static-site"
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        package_json = {
            "name": package_name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "description": "Dependency-free static website scaffold generated by Aegis.",
            "scripts": {
                "start": "node server.js",
                "validate": "node build.js",
            },
            "engines": {"node": ">=20"},
        }
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <meta name="description" content="{html_title} is a polished responsive business website generated by Aegis." />
                    <title>{html_title}</title>
                    <link rel="stylesheet" href="styles.css" />
                  </head>
                  <body>
                    <header class="site-header">
                      <a class="brand" href="#top" aria-label="{html_title} home">{html_title}</a>
                      <nav class="nav" aria-label="Primary navigation">
                        <a href="#services">Services</a>
                        <a href="#work">Work</a>
                        <a href="#booking">Booking</a>
                        <a href="#contact">Contact</a>
                      </nav>
                    </header>

                    <main id="top">
                      <section class="hero section">
                        <div class="hero-copy">
                          <p class="eyebrow">Premium local service</p>
                          <h1>{html_title}</h1>
                          <p class="lead">A fast, responsive website starter with clear sections, strong calls to action, and no dependency install step.</p>
                          <div class="hero-actions" aria-label="Primary actions">
                            <a class="button primary" href="#booking">Book a visit</a>
                            <a class="button secondary" href="#services">View services</a>
                          </div>
                        </div>
                        <div class="hero-panel" aria-label="Featured business highlights">
                          <span>Open today</span>
                          <strong>9:00 AM - 7:00 PM</strong>
                          <p>Walk-ins, appointments, and private sessions ready to customize.</p>
                        </div>
                      </section>

                      <section id="services" class="section">
                        <div class="section-heading">
                          <p class="eyebrow">Services</p>
                          <h2>Built for repeat customers and first-time visitors.</h2>
                        </div>
                        <div class="card-grid">
                          <article class="card">
                            <span class="card-kicker">01</span>
                            <h3>Signature Service</h3>
                            <p>Clear, premium copy block for the main offer your customer should notice first.</p>
                          </article>
                          <article class="card">
                            <span class="card-kicker">02</span>
                            <h3>Express Option</h3>
                            <p>Fast service path with simple details, pricing room, and a visible booking route.</p>
                          </article>
                          <article class="card">
                            <span class="card-kicker">03</span>
                            <h3>Custom Session</h3>
                            <p>Flexible package for longer appointments, special requests, or premium clients.</p>
                          </article>
                        </div>
                      </section>

                      <section id="work" class="section split">
                        <div>
                          <p class="eyebrow">Experience</p>
                          <h2>Clean layout, strong contrast, and sections users can scan fast.</h2>
                        </div>
                        <div class="feature-list">
                          <div>
                            <strong>Responsive</strong>
                            <span>Desktop and mobile layouts use stable spacing and readable type.</span>
                          </div>
                          <div>
                            <strong>Interactive</strong>
                            <span>Booking form feedback, active navigation, and smooth scrolling are wired in.</span>
                          </div>
                          <div>
                            <strong>Validated</strong>
                            <span>The included Node validator checks required files and JavaScript syntax.</span>
                          </div>
                        </div>
                      </section>

                      <section id="booking" class="section booking">
                        <div class="section-heading">
                          <p class="eyebrow">Booking</p>
                          <h2>Capture the first customer action.</h2>
                        </div>
                        <form class="booking-form" data-booking-form>
                          <label>
                            Name
                            <input name="name" type="text" autocomplete="name" required />
                          </label>
                          <label>
                            Service
                            <select name="service" required>
                              <option value="">Choose a service</option>
                              <option>Signature Service</option>
                              <option>Express Option</option>
                              <option>Custom Session</option>
                            </select>
                          </label>
                          <label>
                            Preferred date
                            <input name="date" type="date" required />
                          </label>
                          <button class="button primary" type="submit">Request booking</button>
                          <p class="form-status" data-form-status role="status" aria-live="polite"></p>
                        </form>
                      </section>
                    </main>

                    <footer id="contact" class="site-footer">
                      <div>
                        <strong>{html_title}</strong>
                        <span>Ready to personalize with real address, hours, images, and service pricing.</span>
                      </div>
                      <a class="button secondary" href="mailto:hello@example.com">hello@example.com</a>
                    </footer>

                    <script src="scripts.js"></script>
                  </body>
                </html>
                """
            ),
            "styles.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  --bg: #07100d;
                  --panel: #111b17;
                  --panel-strong: #17241f;
                  --text: #f4f0e8;
                  --muted: #b7b0a3;
                  --accent: #2bd77f;
                  --accent-strong: #f2c46d;
                  --border: rgba(255, 255, 255, 0.12);
                  font-family: Arial, Helvetica, sans-serif;
                }

                * {
                  box-sizing: border-box;
                }

                html {
                  scroll-behavior: smooth;
                }

                body {
                  min-width: 320px;
                  margin: 0;
                  background:
                    linear-gradient(120deg, rgba(43, 215, 127, 0.08), transparent 38%),
                    linear-gradient(180deg, #0b1411 0%, #050807 100%);
                  color: var(--text);
                }

                a {
                  color: inherit;
                  text-decoration: none;
                }

                .site-header,
                .site-footer,
                .section {
                  width: min(1120px, calc(100vw - 32px));
                  margin: 0 auto;
                }

                .site-header {
                  position: sticky;
                  top: 0;
                  z-index: 10;
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  min-height: 72px;
                  border-bottom: 1px solid var(--border);
                  background: rgba(7, 16, 13, 0.92);
                  backdrop-filter: blur(14px);
                }

                .brand {
                  font-weight: 800;
                  letter-spacing: 0;
                }

                .nav {
                  display: flex;
                  gap: 18px;
                  color: var(--muted);
                  font-size: 14px;
                }

                .nav a:hover,
                .nav a.is-active {
                  color: var(--accent);
                }

                .section {
                  padding: 76px 0;
                }

                .hero {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) 360px;
                  gap: 32px;
                  align-items: end;
                  min-height: calc(100vh - 120px);
                }

                .eyebrow {
                  margin: 0 0 12px;
                  color: var(--accent);
                  font-size: 13px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                h1,
                h2,
                h3,
                p {
                  margin-top: 0;
                }

                h1 {
                  max-width: 780px;
                  margin-bottom: 18px;
                  font-size: clamp(44px, 8vw, 92px);
                  line-height: 0.98;
                  letter-spacing: 0;
                }

                h2 {
                  max-width: 760px;
                  margin-bottom: 0;
                  font-size: clamp(30px, 4vw, 52px);
                  line-height: 1.05;
                  letter-spacing: 0;
                }

                h3 {
                  margin-bottom: 12px;
                  font-size: 20px;
                }

                .lead {
                  max-width: 620px;
                  color: var(--muted);
                  font-size: 18px;
                  line-height: 1.65;
                }

                .hero-actions {
                  display: flex;
                  flex-wrap: wrap;
                  gap: 12px;
                  margin-top: 26px;
                }

                .button {
                  display: inline-flex;
                  align-items: center;
                  justify-content: center;
                  min-height: 44px;
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  padding: 0 18px;
                  font-weight: 700;
                  cursor: pointer;
                }

                .button.primary {
                  border-color: transparent;
                  background: var(--accent);
                  color: #03100a;
                }

                .button.secondary {
                  background: rgba(255, 255, 255, 0.05);
                  color: var(--text);
                }

                .hero-panel,
                .card,
                .booking-form,
                .feature-list div {
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: rgba(255, 255, 255, 0.045);
                }

                .hero-panel {
                  padding: 24px;
                }

                .hero-panel span,
                .site-footer span,
                .feature-list span,
                .card p,
                .form-status {
                  color: var(--muted);
                  line-height: 1.55;
                }

                .hero-panel strong {
                  display: block;
                  margin: 10px 0;
                  color: var(--accent-strong);
                  font-size: 28px;
                }

                .hero-stats {
                  display: grid;
                  gap: 10px;
                  margin-top: 18px;
                }

                .hero-stat {
                  display: flex;
                  justify-content: space-between;
                  gap: 12px;
                  border-top: 1px solid var(--border);
                  padding-top: 10px;
                }

                .hero-stat strong {
                  margin: 0;
                  color: var(--text);
                  font-size: 18px;
                }

                .section-heading {
                  display: grid;
                  gap: 10px;
                  margin-bottom: 24px;
                }

                .card-grid {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 16px;
                }

                .card {
                  min-height: 210px;
                  padding: 22px;
                }

                .card-kicker {
                  display: inline-flex;
                  margin-bottom: 22px;
                  color: var(--accent-strong);
                  font-weight: 800;
                }

                .split {
                  display: grid;
                  grid-template-columns: 0.9fr 1.1fr;
                  gap: 24px;
                  align-items: start;
                }

                .feature-list {
                  display: grid;
                  gap: 12px;
                }

                .feature-list div {
                  padding: 18px;
                }

                .feature-list strong,
                .feature-list span {
                  display: block;
                }

                .feature-list span {
                  margin-top: 8px;
                }

                .booking {
                  border-top: 1px solid var(--border);
                }

                .booking-form {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 14px;
                  padding: 18px;
                }

                label {
                  display: grid;
                  gap: 8px;
                  color: var(--muted);
                  font-size: 14px;
                }

                input,
                select {
                  min-height: 44px;
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: var(--panel);
                  color: var(--text);
                  padding: 0 12px;
                  font: inherit;
                }

                .form-status {
                  grid-column: 1 / -1;
                  min-height: 24px;
                  margin: 0;
                }

                .site-footer {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 16px;
                  border-top: 1px solid var(--border);
                  padding: 28px 0;
                }

                .site-footer strong,
                .site-footer span {
                  display: block;
                }

                .site-footer span {
                  margin-top: 6px;
                }

                @media (max-width: 860px) {
                  .site-header,
                  .site-footer {
                    align-items: flex-start;
                    flex-direction: column;
                    padding: 16px 0;
                  }

                  .nav {
                    flex-wrap: wrap;
                  }

                  .hero,
                  .split,
                  .card-grid,
                  .booking-form {
                    grid-template-columns: 1fr;
                  }

                  .hero {
                    min-height: auto;
                    padding-top: 48px;
                  }
                }
                """
            ),
            "scripts.js": _strip(
                """
                const bookingForm = document.querySelector('[data-booking-form]');
                const formStatus = document.querySelector('[data-form-status]');
                const navLinks = [...document.querySelectorAll('.nav a')];

                bookingForm?.addEventListener('submit', (event) => {
                  event.preventDefault();
                  const data = new FormData(bookingForm);
                  const name = String(data.get('name') || 'there').trim();
                  const service = String(data.get('service') || 'your service').trim();
                  formStatus.textContent = `Thanks, ${name}. Your ${service} request is ready to wire to a backend or booking provider.`;
                  bookingForm.reset();
                });

                const sectionObserver = new IntersectionObserver((entries) => {
                  const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

                  if (!visible) {
                    return;
                  }

                  navLinks.forEach((link) => {
                    link.classList.toggle('is-active', link.hash === `#${visible.target.id}`);
                  });
                }, { threshold: [0.4, 0.65] });

                document.querySelectorAll('main section[id], footer[id]').forEach((section) => {
                  sectionObserver.observe(section);
                });
                """
            ),
            "server.js": _strip(
                """
                import { createServer } from 'node:http';
                import { readFile } from 'node:fs/promises';
                import { extname, join, normalize } from 'node:path';

                const root = process.cwd();
                const port = Number.parseInt(process.env.PORT || '4173', 10);
                const contentTypes = {
                  '.html': 'text/html; charset=utf-8',
                  '.css': 'text/css; charset=utf-8',
                  '.js': 'text/javascript; charset=utf-8',
                  '.json': 'application/json; charset=utf-8'
                };

                createServer(async (request, response) => {
                  try {
                    const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);
                    const safePath = normalize(url.pathname === '/' ? '/index.html' : url.pathname).replace(/^([/\\\\])+/, '');
                    const filePath = join(root, safePath);
                    const data = await readFile(filePath);
                    response.writeHead(200, { 'content-type': contentTypes[extname(filePath)] || 'application/octet-stream' });
                    response.end(data);
                  } catch {
                    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
                    response.end('Not found');
                  }
                }).listen(port, () => {
                  console.log(`Static site available at http://127.0.0.1:${port}`);
                });
                """
            ),
            "build.js": _strip(
                """
                import { spawnSync } from 'node:child_process';
                import { existsSync, readFileSync } from 'node:fs';

                const requiredFiles = [
                  'index.html',
                  'styles.css',
                  'scripts.js',
                  'server.js'
                ];

                for (const file of requiredFiles) {
                  if (!existsSync(file)) {
                    console.error('Missing required file:', file);
                    process.exit(1);
                  }
                }

                const html = readFileSync('index.html', 'utf8');
                const css = readFileSync('styles.css', 'utf8');

                for (const required of ['id="services"', 'id="work"', 'id="booking"', 'id="contact"', 'scripts.js', 'styles.css']) {
                  if (!html.includes(required)) {
                    console.error('index.html is missing:', required);
                    process.exit(1);
                  }
                }

                for (const required of [':root', '.hero', '.card-grid', '@media']) {
                  if (!css.includes(required)) {
                    console.error('styles.css is missing:', required);
                    process.exit(1);
                  }
                }

                const checks = [
                  ['node', ['--check', 'scripts.js']],
                  ['node', ['--check', 'server.js']]
                ];

                for (const [command, args] of checks) {
                  console.log('Running:', command, ...args);
                  const completed = spawnSync(command, args, { stdio: 'inherit' });
                  if (completed.status !== 0) {
                    process.exit(completed.status ?? 1);
                  }
                }

                console.log('Static website scaffold passed validation.');
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                coverage
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free static website scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                node build.js
                ```

                ## Preview

                ```powershell
                node server.js
                ```

                Then open `http://127.0.0.1:4173`.
                """
            ),
        }

    @staticmethod
    def _browser_extension_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        manifest = {
            "manifest_version": 3,
            "name": title,
            "version": "0.1.0",
            "description": "A Manifest V3 browser extension generated by Aegis.",
            "permissions": ["activeTab", "storage", "scripting"],
            "host_permissions": ["<all_urls>"],
            "background": {
                "service_worker": "src/background.js",
                "type": "module",
            },
            "action": {
                "default_title": title,
                "default_popup": "popup/popup.html",
            },
            "options_page": "options/options.html",
            "content_scripts": [
                {
                    "matches": ["<all_urls>"],
                    "js": ["src/content.js"],
                    "run_at": "document_idle",
                }
            ],
        }
        return {
            "manifest.json": json.dumps(manifest, indent=2) + "\n",
            "src/background.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                chrome.runtime.onInstalled.addListener(async () => {
                  const existing = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
                  console.info('Aegis extension installed and settings initialized.');
                });

                chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
                  if (message?.type === 'AEGIS_GET_SETTINGS') {
                    chrome.storage.sync.get(DEFAULT_SETTINGS).then((settings) => {
                      sendResponse({ ok: true, settings });
                    });
                    return true;
                  }

                  if (message?.type === 'AEGIS_SET_BADGE') {
                    chrome.action.setBadgeText({ text: message.text ?? '' });
                    chrome.action.setBadgeBackgroundColor({ color: DEFAULT_SETTINGS.accentColor });
                    sendResponse({ ok: true });
                    return false;
                  }

                  return false;
                });
                """
            ),
            "src/content.js": _strip(
                """
                (() => {
                  const ROOT_ID = 'aegis-extension-marker';

                  const applyMarker = async () => {
                    const response = await chrome.runtime.sendMessage({ type: 'AEGIS_GET_SETTINGS' });
                    const settings = response?.settings ?? {};
                    if (!settings.enabled || document.getElementById(ROOT_ID)) {
                      return;
                    }

                    const marker = document.createElement('div');
                    marker.id = ROOT_ID;
                    marker.textContent = 'Aegis';
                    marker.style.position = 'fixed';
                    marker.style.right = '16px';
                    marker.style.bottom = '16px';
                    marker.style.zIndex = '2147483647';
                    marker.style.padding = '8px 10px';
                    marker.style.borderRadius = '8px';
                    marker.style.background = settings.accentColor ?? '#27de7d';
                    marker.style.color = '#071018';
                    marker.style.font = '600 12px system-ui, sans-serif';
                    marker.style.boxShadow = '0 12px 32px rgba(0, 0, 0, 0.24)';
                    document.documentElement.appendChild(marker);
                  };

                  applyMarker().catch((error) => {
                    console.debug('Aegis marker skipped:', error);
                  });
                })();
                """
            ),
            "popup/popup.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <title>{html_title}</title>
                    <link rel="stylesheet" href="popup.css" />
                  </head>
                  <body>
                    <main>
                      <p class="eyebrow">Browser extension</p>
                      <h1>{html_title}</h1>
                      <p id="status">Loading settings...</p>
                      <label class="toggle">
                        <input id="enabled" type="checkbox" />
                        <span>Enable page marker</span>
                      </label>
                      <button id="save">Save</button>
                    </main>
                    <script src="popup.js"></script>
                  </body>
                </html>
                """
            ),
            "popup/popup.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                  background: #071018;
                  color: #edf7f3;
                }

                body {
                  width: 320px;
                  margin: 0;
                  background: #071018;
                }

                main {
                  padding: 18px;
                }

                .eyebrow {
                  margin: 0 0 6px;
                  color: #27de7d;
                  font-size: 12px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                h1 {
                  margin: 0 0 12px;
                  font-size: 22px;
                }

                p {
                  color: #aab7c4;
                  line-height: 1.5;
                }

                .toggle {
                  display: flex;
                  gap: 10px;
                  align-items: center;
                  margin: 18px 0;
                }

                button {
                  width: 100%;
                  border: 0;
                  border-radius: 8px;
                  padding: 10px 12px;
                  background: #27de7d;
                  color: #071018;
                  font-weight: 700;
                }
                """
            ),
            "popup/popup.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                const enabledInput = document.querySelector('#enabled');
                const statusText = document.querySelector('#status');
                const saveButton = document.querySelector('#save');

                const loadSettings = async () => {
                  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  enabledInput.checked = settings.enabled;
                  statusText.textContent = settings.enabled
                    ? 'The content script marker is enabled.'
                    : 'The content script marker is disabled.';
                };

                const saveSettings = async () => {
                  await chrome.storage.sync.set({
                    ...DEFAULT_SETTINGS,
                    enabled: enabledInput.checked
                  });
                  await chrome.runtime.sendMessage({
                    type: 'AEGIS_SET_BADGE',
                    text: enabledInput.checked ? 'ON' : ''
                  });
                  statusText.textContent = 'Settings saved. Reload the page to apply content-script changes.';
                };

                saveButton.addEventListener('click', () => {
                  saveSettings().catch((error) => {
                    statusText.textContent = `Save failed: ${error.message}`;
                  });
                });

                loadSettings().catch((error) => {
                  statusText.textContent = `Load failed: ${error.message}`;
                });
                """
            ),
            "options/options.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <title>{html_title} Options</title>
                    <link rel="stylesheet" href="options.css" />
                  </head>
                  <body>
                    <main>
                      <p class="eyebrow">Extension options</p>
                      <h1>{html_title}</h1>
                      <label>
                        Accent color
                        <input id="accentColor" type="color" value="#27de7d" />
                      </label>
                      <button id="save">Save Options</button>
                      <p id="status"></p>
                    </main>
                    <script src="options.js"></script>
                  </body>
                </html>
                """
            ),
            "options/options.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                  background: #071018;
                  color: #edf7f3;
                }

                body {
                  margin: 0;
                  min-height: 100vh;
                  background: #071018;
                }

                main {
                  max-width: 720px;
                  padding: 42px;
                }

                .eyebrow {
                  color: #27de7d;
                  font-size: 12px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                label {
                  display: grid;
                  gap: 10px;
                  margin: 24px 0;
                  color: #aab7c4;
                }

                button {
                  border: 0;
                  border-radius: 8px;
                  padding: 10px 14px;
                  background: #27de7d;
                  color: #071018;
                  font-weight: 700;
                }
                """
            ),
            "options/options.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                const colorInput = document.querySelector('#accentColor');
                const statusText = document.querySelector('#status');
                const saveButton = document.querySelector('#save');

                const loadOptions = async () => {
                  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  colorInput.value = settings.accentColor;
                };

                const saveOptions = async () => {
                  await chrome.storage.sync.set({
                    ...DEFAULT_SETTINGS,
                    accentColor: colorInput.value
                  });
                  statusText.textContent = 'Options saved.';
                };

                saveButton.addEventListener('click', () => {
                  saveOptions().catch((error) => {
                    statusText.textContent = `Save failed: ${error.message}`;
                  });
                });

                loadOptions().catch((error) => {
                  statusText.textContent = `Load failed: ${error.message}`;
                });
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import json
                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path, PurePosixPath


                ROOT = Path(__file__).resolve().parent


                def resolve_extension_path(relative: str) -> Path:
                    parts = PurePosixPath(relative).parts
                    if not parts or any(part in ("", ".", "..") for part in parts):
                        raise ValueError(f"invalid extension path: {relative}")
                    path = (ROOT / Path(*parts)).resolve()
                    if not path.is_relative_to(ROOT.resolve()):
                        raise ValueError(f"extension path escapes project root: {relative}")
                    if not path.exists():
                        raise FileNotFoundError(f"manifest references missing file: {relative}")
                    return path


                def validate_manifest() -> list[Path]:
                    manifest_path = ROOT / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest.get("manifest_version") != 3:
                        raise ValueError("manifest_version must be 3")
                    if not manifest.get("name"):
                        raise ValueError("manifest name is required")
                    if not manifest.get("version"):
                        raise ValueError("manifest version is required")

                    referenced: list[Path] = []
                    background = manifest.get("background", {})
                    if "service_worker" not in background:
                        raise ValueError("background.service_worker is required")
                    referenced.append(resolve_extension_path(background["service_worker"]))

                    action = manifest.get("action", {})
                    if "default_popup" not in action:
                        raise ValueError("action.default_popup is required")
                    referenced.append(resolve_extension_path(action["default_popup"]))

                    if "options_page" in manifest:
                        referenced.append(resolve_extension_path(manifest["options_page"]))

                    for content_script in manifest.get("content_scripts", []):
                        for script in content_script.get("js", []):
                            referenced.append(resolve_extension_path(script))

                    for required in [
                        "popup/popup.js",
                        "popup/popup.css",
                        "options/options.js",
                        "options/options.css",
                    ]:
                        referenced.append(resolve_extension_path(required))

                    return referenced


                def syntax_check_javascript() -> int:
                    node = shutil.which("node")
                    if node is None:
                        print("Node.js not found; skipped JavaScript syntax checks.")
                        return 0

                    scripts = [
                        "src/background.js",
                        "src/content.js",
                        "popup/popup.js",
                        "options/options.js",
                    ]
                    for script in scripts:
                        path = resolve_extension_path(script)
                        command = [node, "--check", str(path)]
                        print("Running:", " ".join(command))
                        completed = subprocess.run(command, cwd=str(ROOT), text=True)
                        if completed.returncode != 0:
                            return completed.returncode
                    return 0


                def main() -> int:
                    try:
                        referenced = validate_manifest()
                    except Exception as exc:
                        print(f"Manifest validation failed: {exc}", file=sys.stderr)
                        return 1

                    print(f"Validated manifest with {len(referenced)} referenced file(s).")
                    code = syntax_check_javascript()
                    if code != 0:
                        return code
                    print("Browser extension scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                dist
                *.zip
                .env
                node_modules
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Browser extension scaffold generated by Aegis Project Builder.

                ## What It Includes

                - `manifest.json` using Manifest V3.
                - `src/background.js` service worker.
                - `src/content.js` page content script.
                - `popup/` browser-action popup.
                - `options/` extension options page.
                - `build.py` static validation for manifest references and JavaScript syntax.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Load In Chrome Or Edge

                1. Open the browser extensions page.
                2. Enable developer mode.
                3. Choose "Load unpacked".
                4. Select this project folder.
                """
            ),
        }

    @staticmethod
    def _vscode_extension_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        extension_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-extension"
        command_prefix = extension_name
        config_prefix = extension_name
        package_json = {
            "name": extension_name,
            "displayName": title,
            "description": "A VS Code extension generated by Aegis Project Builder.",
            "version": "0.1.0",
            "publisher": "aegis",
            "engines": {"vscode": "^1.90.0"},
            "categories": ["Other"],
            "activationEvents": [
                f"onCommand:{command_prefix}.hello",
                f"onCommand:{command_prefix}.openPanel",
            ],
            "main": "./extension.js",
            "contributes": {
                "commands": [
                    {
                        "command": f"{command_prefix}.hello",
                        "title": f"{title}: Hello",
                    },
                    {
                        "command": f"{command_prefix}.openPanel",
                        "title": f"{title}: Open Panel",
                    },
                ],
                "configuration": {
                    "title": title,
                    "properties": {
                        f"{config_prefix}.enableStatusBar": {
                            "type": "boolean",
                            "default": True,
                            "description": "Show the extension status bar item.",
                        }
                    },
                },
            },
        }
        js_title = title.replace("\\", "\\\\").replace("'", "\\'")
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "extension.js": _strip(
                f"""
                const vscode = require('vscode');

                const EXTENSION_TITLE = '{js_title}';
                const CONFIG_PREFIX = '{config_prefix}';
                const COMMAND_HELLO = '{command_prefix}.hello';
                const COMMAND_OPEN_PANEL = '{command_prefix}.openPanel';

                function activate(context) {{
                  const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
                  statusItem.text = '$(sparkle) ' + EXTENSION_TITLE;
                  statusItem.tooltip = EXTENSION_TITLE + ' is active';
                  statusItem.command = COMMAND_OPEN_PANEL;

                  const syncStatusItem = () => {{
                    const enabled = vscode.workspace
                      .getConfiguration(CONFIG_PREFIX)
                      .get('enableStatusBar', true);
                    if (enabled) {{
                      statusItem.show();
                    }} else {{
                      statusItem.hide();
                    }}
                  }};

                  context.subscriptions.push(statusItem);
                  context.subscriptions.push(
                    vscode.workspace.onDidChangeConfiguration((event) => {{
                      if (event.affectsConfiguration(CONFIG_PREFIX + '.enableStatusBar')) {{
                        syncStatusItem();
                      }}
                    }})
                  );

                  context.subscriptions.push(
                    vscode.commands.registerCommand(COMMAND_HELLO, () => {{
                      vscode.window.showInformationMessage(EXTENSION_TITLE + ' command is ready.');
                    }})
                  );

                  context.subscriptions.push(
                    vscode.commands.registerCommand(COMMAND_OPEN_PANEL, () => {{
                      openPanel(context.extensionUri);
                    }})
                  );

                  syncStatusItem();
                }}

                function openPanel(extensionUri) {{
                  const panel = vscode.window.createWebviewPanel(
                    '{extension_name}.panel',
                    EXTENSION_TITLE,
                    vscode.ViewColumn.One,
                    {{
                      enableScripts: false,
                      localResourceRoots: [extensionUri]
                    }}
                  );
                  panel.webview.html = getWebviewHtml();
                }}

                function getWebviewHtml() {{
                  return [
                    '<!doctype html>',
                    '<html lang="en">',
                    '<head>',
                    '<meta charset="utf-8" />',
                    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
                    '<style>',
                    ':root {{ color-scheme: dark; font-family: system-ui, sans-serif; background: #071018; color: #edf7f3; }}',
                    'body {{ margin: 0; padding: 28px; }}',
                    '.eyebrow {{ color: #27de7d; font-weight: 700; text-transform: uppercase; font-size: 12px; }}',
                    'h1 {{ margin: 8px 0 12px; }}',
                    'p {{ color: #aab7c4; line-height: 1.6; }}',
                    '</style>',
                    '</head>',
                    '<body>',
                    '<p class="eyebrow">VS Code extension</p>',
                    '<h1>{html_title}</h1>',
                    '<p>This panel is ready for your first command, workspace scan, or project automation feature.</p>',
                    '</body>',
                    '</html>'
                  ].join('');
                }}

                function deactivate() {{
                  // VS Code disposes registered subscriptions automatically.
                }}

                module.exports = {{
                  activate,
                  deactivate,
                  getWebviewHtml
                }};
                """
            ),
            ".vscode/launch.json": _strip(
                """
                {
                  "version": "0.2.0",
                  "configurations": [
                    {
                      "name": "Run Extension",
                      "type": "extensionHost",
                      "request": "launch",
                      "args": ["--extensionDevelopmentPath=${workspaceFolder}"]
                    }
                  ]
                }
                """
            ),
            ".vscodeignore": _strip(
                """
                .vscode/**
                .aegis/**
                build.py
                *.log
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import json
                import shutil
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent


                def validate_package() -> Path:
                    package_path = ROOT / "package.json"
                    package = json.loads(package_path.read_text(encoding="utf-8"))
                    main_value = package.get("main")
                    if not main_value:
                        raise ValueError("package.json main is required")
                    main_path = (ROOT / main_value).resolve()
                    if not main_path.is_relative_to(ROOT.resolve()) or not main_path.exists():
                        raise FileNotFoundError(f"main entry does not exist: {main_value}")
                    if not package.get("engines", {}).get("vscode"):
                        raise ValueError("engines.vscode is required")

                    activation_commands = {
                        event.removeprefix("onCommand:")
                        for event in package.get("activationEvents", [])
                        if isinstance(event, str) and event.startswith("onCommand:")
                    }
                    contributed_commands = {
                        command.get("command")
                        for command in package.get("contributes", {}).get("commands", [])
                        if isinstance(command, dict)
                    }
                    if not contributed_commands:
                        raise ValueError("at least one contributed command is required")
                    missing_activation = contributed_commands - activation_commands
                    if missing_activation:
                        raise ValueError(f"commands missing activation events: {sorted(missing_activation)}")

                    properties = package.get("contributes", {}).get("configuration", {}).get("properties", {})
                    if not properties:
                        raise ValueError("configuration properties are required")
                    return main_path


                def syntax_check(script: Path) -> int:
                    node = shutil.which("node")
                    if node is None:
                        print("Node.js not found; skipped JavaScript syntax check.")
                        return 0
                    command = [node, "--check", str(script)]
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))


                def main() -> int:
                    try:
                        main_path = validate_package()
                    except Exception as exc:
                        print(f"VS Code extension validation failed: {exc}", file=sys.stderr)
                        return 1
                    code = syntax_check(main_path)
                    if code != 0:
                        return code
                    print("VS Code extension scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                VS Code extension scaffold generated by Aegis Project Builder.

                ## What It Includes

                - `package.json` with command, activation, and settings contributions.
                - `extension.js` with command registration, status bar wiring, and a starter webview panel.
                - `.vscode/launch.json` for Extension Host debugging.
                - `build.py` static validation for package metadata and JavaScript syntax.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run In VS Code

                Open this folder in VS Code and press `F5` to launch an Extension Development Host.
                """
            ),
        }

    @staticmethod
    def _node_cli_template(project_name: str) -> dict[str, str]:
        return scaffold_node_cli_template(project_name)


    @staticmethod
    def _node_http_api_template(project_name: str) -> dict[str, str]:
        return scaffold_node_http_api_template(project_name)


    @staticmethod
    def _node_fullstack_template(project_name: str) -> dict[str, str]:
        return scaffold_node_fullstack_template(project_name)


    @staticmethod
    def _python_stdlib_api_template(project_name: str) -> dict[str, str]:
        return scaffold_python_stdlib_api_template(project_name)


    @staticmethod
    def _powershell_module_template(project_name: str) -> dict[str, str]:
        return scaffold_powershell_module_template(project_name)


    @staticmethod
    def _python_cli_template(project_name: str) -> dict[str, str]:
        return scaffold_python_cli_template(project_name)


    @staticmethod
    def _python_tkinter_desktop_template(project_name: str) -> dict[str, str]:
        return scaffold_python_tkinter_desktop_template(project_name)


    @staticmethod
    def _fastapi_template(project_name: str) -> dict[str, str]:
        return scaffold_fastapi_template(project_name)


    @staticmethod
    def _express_ts_template(project_name: str) -> dict[str, str]:
        return scaffold_express_ts_template(project_name)


    @staticmethod
    def _sqlite_python_db_template(project_name: str) -> dict[str, str]:
        return scaffold_sqlite_python_db_template(project_name)


    @staticmethod
    def _cpp_cmake_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_cmake_template(project_name)


    @staticmethod
    def _cpp_cmake_dll_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_cmake_dll_template(project_name)


    @staticmethod
    def _cpp_imgui_win32_dx11_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_imgui_win32_dx11_template(project_name)


    @staticmethod
    def _cpp_game_loop_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_game_loop_template(project_name)

    @staticmethod
    def _python_game_file_analyzer_template(project_name: str) -> dict[str, str]:
        return scaffold_python_game_file_analyzer_template(project_name)

    @staticmethod
    def _cpp_msvc_console_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_msvc_console_template(project_name)


    @staticmethod
    def _cpp_windows_service_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_windows_service_template(project_name)


    @staticmethod
    def _cpp_windows_internals_hooking_template(project_name: str) -> dict[str, str]:
        return scaffold_cpp_windows_internals_hooking_template(project_name)

    @staticmethod
    def _python_sln_refactor_tool_template(project_name: str) -> dict[str, str]:
        return scaffold_python_sln_refactor_tool_template(project_name)

    @staticmethod
    def _windows_kernel_driver_controller_template(project_name: str) -> dict[str, str]:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-driver"
        title = _title_from_name(safe_name)
        pascal_name = re.sub(r"[^A-Za-z0-9]+", " ", safe_name).title().replace(" ", "") or "AegisDriver"
        solution_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.solution.{safe_name}")).upper() + "}"
        driver_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.kernel.{safe_name}")).upper() + "}"
        controller_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.controller.{safe_name}")).upper() + "}"
        driver_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.kernel.{safe_name}.source")).upper() + "}"
        controller_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.controller.{safe_name}.source")).upper() + "}"
        driver_project = f"{safe_name}Driver"
        controller_project = f"{safe_name}Controller"
        return {
            f"{safe_name}.sln": _strip(
                f"""
                Microsoft Visual Studio Solution File, Format Version 12.00
                # Visual Studio Version 17
                VisualStudioVersion = 17.0.31903.59
                MinimumVisualStudioVersion = 10.0.40219.1
                Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{driver_project}", "driver\\{driver_project}.vcxproj", "{driver_guid}"
                EndProject
                Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{controller_project}", "controller\\{controller_project}.vcxproj", "{controller_guid}"
                EndProject
                Global
                    GlobalSection(SolutionConfigurationPlatforms) = preSolution
                        Debug|x64 = Debug|x64
                        Release|x64 = Release|x64
                    EndGlobalSection
                    GlobalSection(ProjectConfigurationPlatforms) = postSolution
                        {driver_guid}.Debug|x64.ActiveCfg = Debug|x64
                        {driver_guid}.Debug|x64.Build.0 = Debug|x64
                        {driver_guid}.Release|x64.ActiveCfg = Release|x64
                        {driver_guid}.Release|x64.Build.0 = Release|x64
                        {controller_guid}.Debug|x64.ActiveCfg = Debug|x64
                        {controller_guid}.Debug|x64.Build.0 = Debug|x64
                        {controller_guid}.Release|x64.ActiveCfg = Release|x64
                        {controller_guid}.Release|x64.Build.0 = Release|x64
                    EndGlobalSection
                    GlobalSection(SolutionProperties) = preSolution
                        HideSolutionNode = FALSE
                    EndGlobalSection
                    GlobalSection(ExtensibilityGlobals) = postSolution
                        SolutionGuid = {solution_guid}
                    EndGlobalSection
                EndGlobal
                """
            ),
            f"driver/{driver_project}.vcxproj": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project DefaultTargets="Build" ToolsVersion="12.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup Label="ProjectConfigurations">
                    <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
                    <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
                  </ItemGroup>
                  <PropertyGroup Label="Globals">
                    <ProjectGuid>{driver_guid}</ProjectGuid>
                    <RootNamespace>{pascal_name}Driver</RootNamespace>
                    <TargetName>{driver_project}</TargetName>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                    <ConfigurationType>Driver</ConfigurationType>
                    <DriverType>WDM</DriverType>
                    <PlatformToolset>WindowsKernelModeDriver10.0</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                    <ConfigurationType>Driver</ConfigurationType>
                    <DriverType>WDM</DriverType>
                    <PlatformToolset>WindowsKernelModeDriver10.0</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
                  <ItemDefinitionGroup>
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <TreatWarningAsError>false</TreatWarningAsError>
                      <PreprocessorDefinitions>_KERNEL_MODE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
                    </ClCompile>
                  </ItemDefinitionGroup>
                  <ItemGroup>
                    <ClCompile Include="driver.c" />
                    <ClInclude Include="public.h" />
                  </ItemGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
                </Project>
                """
            ),
            f"driver/{driver_project}.vcxproj.filters": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup>
                    <Filter Include="Source Files">
                      <UniqueIdentifier>{driver_filter_guid}</UniqueIdentifier>
                      <Extensions>c;cpp;h</Extensions>
                    </Filter>
                  </ItemGroup>
                  <ItemGroup>
                    <ClCompile Include="driver.c"><Filter>Source Files</Filter></ClCompile>
                    <ClInclude Include="public.h"><Filter>Source Files</Filter></ClInclude>
                  </ItemGroup>
                </Project>
                """
            ),
            "driver/public.h": _strip(
                """
                #pragma once

                #ifdef _KERNEL_MODE
                #include <ntddk.h>
                #else
                #include <winioctl.h>
                #endif

                #define AEGIS_DEVICE_NT_NAME L"\\\\Device\\\\AegisKernelBridge"
                #define AEGIS_DEVICE_DOS_NAME L"\\\\DosDevices\\\\AegisKernelBridge"
                #define AEGIS_USER_DEVICE_PATH L"\\\\\\\\.\\\\AegisKernelBridge"
                #define IOCTL_AEGIS_PING CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_READ_DATA | FILE_WRITE_DATA)

                typedef struct _AEGIS_PING_REQUEST {
                    unsigned int version;
                    char message[128];
                } AEGIS_PING_REQUEST;

                typedef struct _AEGIS_PING_RESPONSE {
                    unsigned int version;
                    char message[128];
                } AEGIS_PING_RESPONSE;
                """
            ),
            "driver/driver.c": _strip(
                """
                #include "public.h"
                #include <ntstrsafe.h>

                static void AegisUnload(_In_ PDRIVER_OBJECT DriverObject);
                static NTSTATUS AegisCreateClose(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp);
                static NTSTATUS AegisDeviceControl(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp);
                static void AegisComplete(_Inout_ PIRP Irp, _In_ NTSTATUS Status, _In_ ULONG_PTR Information);

                NTSTATUS DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
                {
                    UNREFERENCED_PARAMETER(RegistryPath);
                    UNICODE_STRING deviceName;
                    UNICODE_STRING symbolicName;
                    PDEVICE_OBJECT deviceObject = NULL;

                    RtlInitUnicodeString(&deviceName, AEGIS_DEVICE_NT_NAME);
                    NTSTATUS status = IoCreateDevice(DriverObject, 0, &deviceName, FILE_DEVICE_UNKNOWN, FILE_DEVICE_SECURE_OPEN, FALSE, &deviceObject);
                    if (!NT_SUCCESS(status)) {
                        return status;
                    }

                    RtlInitUnicodeString(&symbolicName, AEGIS_DEVICE_DOS_NAME);
                    status = IoCreateSymbolicLink(&symbolicName, &deviceName);
                    if (!NT_SUCCESS(status)) {
                        IoDeleteDevice(deviceObject);
                        return status;
                    }

                    for (ULONG i = 0; i <= IRP_MJ_MAXIMUM_FUNCTION; ++i) {
                        DriverObject->MajorFunction[i] = AegisCreateClose;
                    }
                    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = AegisDeviceControl;
                    DriverObject->DriverUnload = AegisUnload;
                    deviceObject->Flags &= ~DO_DEVICE_INITIALIZING;
                    return STATUS_SUCCESS;
                }

                static void AegisUnload(_In_ PDRIVER_OBJECT DriverObject)
                {
                    UNICODE_STRING symbolicName;
                    RtlInitUnicodeString(&symbolicName, AEGIS_DEVICE_DOS_NAME);
                    IoDeleteSymbolicLink(&symbolicName);
                    if (DriverObject->DeviceObject != NULL) {
                        IoDeleteDevice(DriverObject->DeviceObject);
                    }
                }

                static NTSTATUS AegisCreateClose(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
                {
                    UNREFERENCED_PARAMETER(DeviceObject);
                    AegisComplete(Irp, STATUS_SUCCESS, 0);
                    return STATUS_SUCCESS;
                }

                static NTSTATUS AegisDeviceControl(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
                {
                    UNREFERENCED_PARAMETER(DeviceObject);
                    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
                    ULONG code = stack->Parameters.DeviceIoControl.IoControlCode;
                    ULONG outputLength = stack->Parameters.DeviceIoControl.OutputBufferLength;
                    void* systemBuffer = Irp->AssociatedIrp.SystemBuffer;

                    if (code != IOCTL_AEGIS_PING) {
                        AegisComplete(Irp, STATUS_INVALID_DEVICE_REQUEST, 0);
                        return STATUS_INVALID_DEVICE_REQUEST;
                    }
                    if (systemBuffer == NULL || outputLength < sizeof(AEGIS_PING_RESPONSE)) {
                        AegisComplete(Irp, STATUS_BUFFER_TOO_SMALL, 0);
                        return STATUS_BUFFER_TOO_SMALL;
                    }

                    AEGIS_PING_RESPONSE* response = (AEGIS_PING_RESPONSE*)systemBuffer;
                    RtlZeroMemory(response, sizeof(*response));
                    response->version = 1;
                    RtlStringCbCopyA(response->message, sizeof(response->message), "Aegis kernel bridge online");
                    AegisComplete(Irp, STATUS_SUCCESS, sizeof(*response));
                    return STATUS_SUCCESS;
                }

                static void AegisComplete(_Inout_ PIRP Irp, _In_ NTSTATUS Status, _In_ ULONG_PTR Information)
                {
                    Irp->IoStatus.Status = Status;
                    Irp->IoStatus.Information = Information;
                    IoCompleteRequest(Irp, IO_NO_INCREMENT);
                }
                """
            ),
            f"controller/{controller_project}.vcxproj": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup Label="ProjectConfigurations">
                    <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
                    <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
                  </ItemGroup>
                  <PropertyGroup Label="Globals">
                    <VCProjectVersion>17.0</VCProjectVersion>
                    <Keyword>Win32Proj</Keyword>
                    <ProjectGuid>{controller_guid}</ProjectGuid>
                    <RootNamespace>{pascal_name}Controller</RootNamespace>
                    <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>true</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>false</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <WholeProgramOptimization>true</WholeProgramOptimization>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
                  <ItemDefinitionGroup>
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <SDLCheck>true</SDLCheck>
                      <ConformanceMode>true</ConformanceMode>
                      <LanguageStandard>stdcpp17</LanguageStandard>
                      <AdditionalIncludeDirectories>..\\driver;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
                    </ClCompile>
                    <Link>
                      <SubSystem>Console</SubSystem>
                    </Link>
                  </ItemDefinitionGroup>
                  <ItemGroup>
                    <ClCompile Include="main.cpp" />
                  </ItemGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
                </Project>
                """
            ),
            f"controller/{controller_project}.vcxproj.filters": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup>
                    <Filter Include="Source Files">
                      <UniqueIdentifier>{controller_filter_guid}</UniqueIdentifier>
                      <Extensions>cpp;cxx;cc</Extensions>
                    </Filter>
                  </ItemGroup>
                  <ItemGroup>
                    <ClCompile Include="main.cpp"><Filter>Source Files</Filter></ClCompile>
                  </ItemGroup>
                </Project>
                """
            ),
            "controller/main.cpp": _strip(
                """
                #include <windows.h>
                #include <iostream>
                #include <string>
                #include "../driver/public.h"

                int main()
                {
                    std::wcout << L"Aegis driver controller starting..." << std::endl;

                    HANDLE device = CreateFileW(AEGIS_USER_DEVICE_PATH, GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
                    if (device == INVALID_HANDLE_VALUE) {
                        std::wcout << L"Driver device is not open yet. Load the signed driver, then run this controller again." << std::endl;
                        std::wcout << L"Press Enter to close...";
                        std::wstring line;
                        std::getline(std::wcin, line);
                        return 1;
                    }

                    AEGIS_PING_REQUEST request{};
                    request.version = 1;
                    strcpy_s(request.message, "hello from user mode");

                    AEGIS_PING_RESPONSE response{};
                    DWORD bytesReturned = 0;
                    BOOL ok = DeviceIoControl(device, IOCTL_AEGIS_PING, &request, sizeof(request), &response, sizeof(response), &bytesReturned, nullptr);
                    CloseHandle(device);

                    if (!ok) {
                        std::wcout << L"DeviceIoControl failed with error " << GetLastError() << std::endl;
                        std::wcout << L"Press Enter to close...";
                        std::wstring line;
                        std::getline(std::wcin, line);
                        return 2;
                    }

                    std::cout << "Kernel response: " << response.message << std::endl;
                    std::cout << "Bytes returned: " << bytesReturned << std::endl;
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                    return 0;
                }
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import os
                import shutil
                import subprocess
                import sys
                from pathlib import Path

                ROOT = Path(__file__).resolve().parent
                CONTROLLER_PROJECT = ROOT / "controller" / "{controller_project}.vcxproj"
                DRIVER_PROJECT = ROOT / "driver" / "{driver_project}.vcxproj"

                def candidate_msbuild_paths() -> list[Path]:
                    candidates: list[Path] = []
                    explicit = os.environ.get("MSBUILD_EXE")
                    if explicit:
                        candidates.append(Path(explicit))
                    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
                    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
                    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
                    if vswhere.exists():
                        completed = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.Component.MSBuild", "-find", r"MSBuild\\**\\Bin\\MSBuild.exe"], text=True, capture_output=True, check=False)
                        for line in completed.stdout.splitlines():
                            if line.strip():
                                candidates.append(Path(line.strip()))
                    for root in (Path(program_files), Path(program_files_x86)):
                        vs2022 = root / "Microsoft Visual Studio" / "2022"
                        for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "MSBuild.exe")
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "amd64" / "MSBuild.exe")
                    on_path = shutil.which("msbuild")
                    if on_path:
                        candidates.append(Path(on_path))
                    return candidates

                def find_msbuild() -> Path | None:
                    seen: set[str] = set()
                    for candidate in candidate_msbuild_paths():
                        key = str(candidate).lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        if candidate.exists():
                            return candidate
                    return None

                def run_msbuild(msbuild: Path, project: Path) -> int:
                    command = [str(msbuild), str(project), "/p:Configuration=Release", "/p:Platform=x64"]
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))

                def main() -> int:
                    msbuild = find_msbuild()
                    if msbuild is None:
                        print("MSBuild was not found. Set MSBUILD_EXE or install Visual Studio Build Tools.", file=sys.stderr)
                        return 2
                    controller_rc = run_msbuild(msbuild, CONTROLLER_PROJECT)
                    build_driver = "--driver" in sys.argv or os.environ.get("AEGIS_BUILD_DRIVER") == "1"
                    if not build_driver:
                        print("Controller built. Driver project is present; pass --driver or set AEGIS_BUILD_DRIVER=1 for the WDK driver build.")
                        return controller_rc
                    driver_rc = run_msbuild(msbuild, DRIVER_PROJECT)
                    return controller_rc or driver_rc

                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                .vs
                x64
                Debug
                Release
                *.user
                *.obj
                *.pdb
                *.ilk
                *.exe
                *.sys
                *.cat
                *.inf
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Windows driver/controller starter generated by Aegis Project Builder.

                ## Layout

                - `driver/` contains a WDM driver skeleton with a named device and IOCTL handler.
                - `controller/` contains a C++ console controller that opens the device and calls `DeviceIoControl`.
                - `driver/public.h` shares the IOCTL contract between user mode and kernel mode.

                ## Build

                ```powershell
                python build.py
                ```

                `python build.py` builds the user-mode controller and builds the driver automatically when the WDK is detected. Use `python build.py --driver` to force a driver build.
                """
            ),
        }


    @staticmethod
    def _electron_react_template(project_name: str) -> dict[str, str]:
        return scaffold_electron_react_template(project_name)


    @staticmethod
    def _expo_react_native_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "scripts": {{
                    "start": "expo start",
                    "android": "expo start --android",
                    "ios": "expo start --ios",
                    "web": "expo start --web",
                    "typecheck": "tsc --noEmit"
                  }},
                  "dependencies": {{
                    "@expo/vector-icons": "^14.0.4",
                    "expo": "^52.0.20",
                    "expo-status-bar": "~2.0.0",
                    "react": "18.3.1",
                    "react-native": "0.76.5",
                    "react-native-safe-area-context": "4.12.0"
                  }},
                  "devDependencies": {{
                    "@types/react": "~18.3.12",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "app.json": _strip(
                f"""
                {{
                  "expo": {{
                    "name": "{title}",
                    "slug": "{project_name}",
                    "version": "0.1.0",
                    "orientation": "portrait",
                    "userInterfaceStyle": "dark",
                    "splash": {{
                      "backgroundColor": "#071018"
                    }},
                    "assetBundlePatterns": ["**/*"],
                    "ios": {{ "supportsTablet": true }},
                    "android": {{ "adaptiveIcon": {{ "backgroundColor": "#071018" }} }}
                  }}
                }}
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "extends": "expo/tsconfig.base",
                  "compilerOptions": {
                    "strict": true,
                    "noUncheckedIndexedAccess": true
                  }
                }
                """
            ),
            "App.tsx": _strip(
                """
                import { StatusBar } from 'expo-status-bar';
                import { SafeAreaView } from 'react-native-safe-area-context';
                import { HomeScreen } from './src/screens/HomeScreen';
                import { colors } from './src/theme';

                export default function App() {
                  return (
                    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
                      <StatusBar style="light" />
                      <HomeScreen />
                    </SafeAreaView>
                  );
                }
                """
            ),
            "src/theme.ts": _strip(
                """
                export const colors = {
                  background: '#071018',
                  panel: '#0c1620',
                  border: '#203040',
                  text: '#edf7f3',
                  muted: '#9aa8b6',
                  accent: '#27de7d'
                };
                """
            ),
            "src/screens/HomeScreen.tsx": _strip(
                f"""
                import {{ StyleSheet, Text, View }} from 'react-native';
                import {{ colors }} from '../theme';

                const lanes = ['Capture', 'Reason', 'Act'];

                export function HomeScreen() {{
                  return (
                    <View style={{styles.screen}}>
                      <Text style={{styles.eyebrow}}>Mobile workspace</Text>
                      <Text style={{styles.title}}>{title}</Text>
                      <Text style={{styles.subtitle}}>Expo starter ready for iOS, Android, and web.</Text>
                      <View style={{styles.grid}}>
                        {{lanes.map((lane) => (
                          <View key={{lane}} style={{styles.card}}>
                            <Text style={{styles.cardTitle}}>{{lane}}</Text>
                            <Text style={{styles.cardText}}>Connect this lane to your first mobile workflow.</Text>
                          </View>
                        ))}}
                      </View>
                    </View>
                  );
                }}

                const styles = StyleSheet.create({{
                  screen: {{ flex: 1, padding: 24, justifyContent: 'center' }},
                  eyebrow: {{ color: colors.accent, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' }},
                  title: {{ color: colors.text, fontSize: 40, fontWeight: '800', marginTop: 10 }},
                  subtitle: {{ color: colors.muted, fontSize: 16, marginTop: 12, lineHeight: 24 }},
                  grid: {{ gap: 12, marginTop: 28 }},
                  card: {{ backgroundColor: colors.panel, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 16 }},
                  cardTitle: {{ color: colors.text, fontWeight: '800', fontSize: 18 }},
                  cardText: {{ color: colors.muted, marginTop: 6, lineHeight: 20 }}
                }});
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                .expo
                dist
                npm-debug.log*
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Expo React Native app generated by Aegis Project Builder.

                ```bash
                npm install
                npm run start
                npm run typecheck
                ```
                """
            ),
        }


    @staticmethod
    def _django_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        return {
            "requirements.txt": _strip(
                """
                Django>=5.1,<5.2
                """
            ),
            "manage.py": _strip(
                """
                #!/usr/bin/env python
                import os
                import sys

                def main() -> None:
                    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                    from django.core.management import execute_from_command_line
                    execute_from_command_line(sys.argv)

                if __name__ == "__main__":
                    main()
                """
            ),
            "config/__init__.py": "",
            "config/settings.py": _strip(
                f"""
                from pathlib import Path

                BASE_DIR = Path(__file__).resolve().parent.parent
                SECRET_KEY = "django-insecure-change-me"
                DEBUG = True
                ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

                INSTALLED_APPS = [
                    "django.contrib.admin",
                    "django.contrib.auth",
                    "django.contrib.contenttypes",
                    "django.contrib.sessions",
                    "django.contrib.messages",
                    "django.contrib.staticfiles",
                    "core",
                ]

                MIDDLEWARE = [
                    "django.middleware.security.SecurityMiddleware",
                    "django.contrib.sessions.middleware.SessionMiddleware",
                    "django.middleware.common.CommonMiddleware",
                    "django.middleware.csrf.CsrfViewMiddleware",
                    "django.contrib.auth.middleware.AuthenticationMiddleware",
                    "django.contrib.messages.middleware.MessageMiddleware",
                    "django.middleware.clickjacking.XFrameOptionsMiddleware",
                ]

                ROOT_URLCONF = "config.urls"
                TEMPLATES = [
                    {{
                        "BACKEND": "django.template.backends.django.DjangoTemplates",
                        "DIRS": [BASE_DIR / "templates"],
                        "APP_DIRS": True,
                        "OPTIONS": {{"context_processors": [
                            "django.template.context_processors.request",
                            "django.contrib.auth.context_processors.auth",
                            "django.contrib.messages.context_processors.messages",
                        ]}},
                    }}
                ]
                WSGI_APPLICATION = "config.wsgi.application"
                DATABASES = {{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}}}
                LANGUAGE_CODE = "en-us"
                TIME_ZONE = "UTC"
                USE_I18N = True
                USE_TZ = True
                STATIC_URL = "static/"
                DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
                AEGIS_APP_NAME = "{title}"
                """
            ),
            "config/urls.py": _strip(
                """
                from django.contrib import admin
                from django.urls import include, path

                urlpatterns = [
                    path("admin/", admin.site.urls),
                    path("", include("core.urls")),
                ]
                """
            ),
            "config/asgi.py": _strip(
                """
                import os
                from django.core.asgi import get_asgi_application

                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                application = get_asgi_application()
                """
            ),
            "config/wsgi.py": _strip(
                """
                import os
                from django.core.wsgi import get_wsgi_application

                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                application = get_wsgi_application()
                """
            ),
            "core/__init__.py": "",
            "core/apps.py": _strip(
                """
                from django.apps import AppConfig

                class CoreConfig(AppConfig):
                    default_auto_field = "django.db.models.BigAutoField"
                    name = "core"
                """
            ),
            "core/urls.py": _strip(
                """
                from django.urls import path
                from . import views

                urlpatterns = [
                    path("", views.home, name="home"),
                    path("health/", views.health, name="health"),
                ]
                """
            ),
            "core/views.py": _strip(
                """
                from django.conf import settings
                from django.http import JsonResponse
                from django.shortcuts import render

                def home(request):
                    return render(request, "core/home.html", {"app_name": settings.AEGIS_APP_NAME})

                def health(request):
                    return JsonResponse({"ok": True, "app": settings.AEGIS_APP_NAME})
                """
            ),
            "core/tests.py": _strip(
                """
                from django.test import Client, TestCase

                class HealthTests(TestCase):
                    def test_health_route(self):
                        response = Client().get("/health/")
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.json()["ok"])
                """
            ),
            "templates/core/home.html": _strip(
                """
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>{{ app_name }}</title>
                    <style>
                      body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #071018; color: #edf7f3; font-family: system-ui, sans-serif; }
                      main { width: min(720px, calc(100vw - 48px)); }
                      p { color: #9aa8b6; line-height: 1.7; }
                      strong { color: #27de7d; }
                    </style>
                  </head>
                  <body>
                    <main>
                      <strong>Django workspace</strong>
                      <h1>{{ app_name }}</h1>
                      <p>Your server-rendered app is ready for models, views, templates, auth, and admin workflows.</p>
                    </main>
                  </body>
                </html>
                """
            ),
            ".gitignore": _strip(
                """
                __pycache__
                *.pyc
                db.sqlite3
                .env
                .venv
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Django web app generated by Aegis Project Builder.

                ```bash
                python -m pip install -r requirements.txt
                python manage.py migrate
                python manage.py runserver
                python manage.py test
                ```
                """
            ),
        }


    @staticmethod
    def _rust_cli_template(project_name: str) -> dict[str, str]:
        return scaffold_rust_cli_template(project_name)


    @staticmethod
    def _go_http_api_template(project_name: str) -> dict[str, str]:
        return scaffold_go_http_api_template(project_name)


    @staticmethod
    def _dotnet_webapi_template(project_name: str) -> dict[str, str]:
        return scaffold_dotnet_webapi_template(project_name)


    @staticmethod
    def _dotnet_console_template(project_name: str) -> dict[str, str]:
        return scaffold_dotnet_console_template(project_name)


    @staticmethod
    def _dotnet_wpf_template(project_name: str) -> dict[str, str]:
        return scaffold_dotnet_wpf_template(project_name)


    @staticmethod
    def _tauri_react_template(project_name: str) -> dict[str, str]:
        return scaffold_tauri_react_template(project_name)


def _strip(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _title_from_name(project_name: str) -> str:
    return scaffold_title_from_name(project_name)
