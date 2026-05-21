"""Production-grade supervised Autopilot runtime.

Autopilot is intentionally a coordinator over the existing engineering
execution, editing, agent, terminal, and workflow systems. It does not bypass
checkpoints, validation gates, approvals, or workspace safety checks.
"""

from __future__ import annotations

import time
import uuid
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

from . import agent_runtime, engineering_execution, runtime_interaction
from .memory import ProjectMemory


AUTOPILOT_RUNS_FILE = "autopilot-runs.json"
AUTOPILOT_EVENTS_FILE = "autopilot-events.json"
AUTOPILOT_MEMORY_FILE = "autopilot-memory.json"
AUTOPILOT_AUDIT_FILE = "autopilot-audit.md"


AUTOPILOT_STATES = [
    "queued",
    "running",
    "waiting_approval",
    "paused",
    "validating",
    "repairing",
    "completed",
    "failed",
    "cancelled",
]


_MUTATING_STAGES = {"implementation", "checkpoint", "apply"}
_VALIDATION_STAGES = {"validation"}
_REPAIR_STAGES = {"repair"}
_TERMINAL_ACTIONS = {"launch_terminal", "run_terminal", "run_command"}
_SIMULATION_ACTIONS = {"simulate", "dry_run", "preview"}
_TRUST_DECISION_LIMIT = 200
_MAX_LOGS_PER_RUN = 250
_MAX_ACTION_PAYLOAD_CHARS = 40000
_REPAIR_REPEAT_ESCALATION_THRESHOLD = 3


@dataclass(frozen=True)
class AutopilotMode:
    id: str
    display_name: str
    description: str
    approval_rules: List[str]
    autonomy_limits: Dict[str, Any]
    allowed_workflow_types: List[str]
    validation_requirements: List[str]
    checkpoint_rules: List[str]
    rollback_rules: List[str]
    terminal_rules: List[str]
    default_execution_mode: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "approval_rules": list(self.approval_rules),
            "autonomy_limits": dict(self.autonomy_limits),
            "allowed_workflow_types": list(self.allowed_workflow_types),
            "validation_requirements": list(self.validation_requirements),
            "checkpoint_rules": list(self.checkpoint_rules),
            "rollback_rules": list(self.rollback_rules),
            "terminal_rules": list(self.terminal_rules),
            "default_execution_mode": self.default_execution_mode,
        }


@dataclass(frozen=True)
class AutopilotSpecialization:
    id: str
    display_name: str
    description: str
    workflow_types: List[str]
    recommended_modes: List[str]
    orchestration_strategy: Dict[str, Any]
    validation_strategy: Dict[str, Any]
    repair_strategy: Dict[str, Any]
    safety_rules: List[str]
    approval_rules: List[str]
    model_routing: Dict[str, Any]
    memory_scope: Dict[str, Any]
    observability: Dict[str, Any]
    benchmark_suites: List[str]
    ui: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "workflow_types": list(self.workflow_types),
            "recommended_modes": list(self.recommended_modes),
            "orchestration_strategy": dict(self.orchestration_strategy),
            "validation_strategy": dict(self.validation_strategy),
            "repair_strategy": dict(self.repair_strategy),
            "safety_rules": list(self.safety_rules),
            "approval_rules": list(self.approval_rules),
            "model_routing": dict(self.model_routing),
            "memory_scope": dict(self.memory_scope),
            "observability": dict(self.observability),
            "benchmark_suites": list(self.benchmark_suites),
            "ui": dict(self.ui),
        }


_ALL_WORKFLOW_TYPES = [
    "chat_request",
    "generate_feature",
    "validate_project",
    "repair_project",
    "continue_roadmap",
    "build_project",
    "scan_workspace",
    "benchmark_models",
    "generate_media",
    "research_task",
]


AUTOPILOT_MODES: Dict[str, AutopilotMode] = {
    "suggest_only": AutopilotMode(
        id="suggest_only",
        display_name="Suggest Only",
        description="Plan, analyze, and propose work without applying changes or running mutating steps.",
        approval_rules=[
            "User approval required before implementation, checkpoint, apply, repair, or terminal execution.",
            "Generated changes remain proposed until a client explicitly applies them through Core editing APIs.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 3,
            "max_repair_attempts": 0,
            "max_files_modified": 0,
            "max_terminal_commands": 0,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=[
            "chat_request",
            "generate_feature",
            "continue_roadmap",
            "scan_workspace",
            "research_task",
        ],
        validation_requirements=[
            "Validation may be planned, but command execution requires approval.",
        ],
        checkpoint_rules=[
            "Checkpoint creation requires approval.",
        ],
        rollback_rules=[
            "Rollback is available only for checkpoints created through approved actions.",
        ],
        terminal_rules=[
            "Terminal commands are blocked until approved.",
            "Dangerous commands remain blocked by runtime command safety.",
        ],
        default_execution_mode="safe_assisted",
    ),
    "approval_each_step": AutopilotMode(
        id="approval_each_step",
        display_name="Approval Each Step",
        description="Every execution stage pauses for explicit user approval.",
        approval_rules=[
            "Each pipeline stage requires approval before it can complete.",
            "Apply and terminal execution require approval even after validation passes.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 1,
            "max_repair_attempts": 1,
            "max_files_modified": 8,
            "max_terminal_commands": 3,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=_ALL_WORKFLOW_TYPES,
        validation_requirements=[
            "Validation must complete before workflow completion.",
            "Failed validation escalates to approval before repair.",
        ],
        checkpoint_rules=[
            "Checkpoint required before apply.",
            "Checkpoint creation requires approval.",
        ],
        rollback_rules=[
            "Rollback must remain available for every approved apply.",
        ],
        terminal_rules=[
            "Every terminal command requires approval.",
        ],
        default_execution_mode="approval_every_step",
    ),
    "semi_autonomous": AutopilotMode(
        id="semi_autonomous",
        display_name="Semi Autonomous",
        description="Autonomously handles analysis and planning, then pauses for mutating work and risky operations.",
        approval_rules=[
            "Non-mutating analysis and planning may proceed automatically.",
            "Implementation, checkpoint, apply, repair, and terminal execution require approval.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 6,
            "max_repair_attempts": 2,
            "max_files_modified": 20,
            "max_terminal_commands": 6,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=_ALL_WORKFLOW_TYPES,
        validation_requirements=[
            "Validation required before completion.",
            "Validation failures may trigger bounded repair planning.",
        ],
        checkpoint_rules=[
            "Checkpoint required before apply.",
            "Checkpoint creation requires approval.",
        ],
        rollback_rules=[
            "Rollback checkpoint must be recorded before apply.",
        ],
        terminal_rules=[
            "Safe validation commands can be prepared automatically but require execution approval.",
        ],
        default_execution_mode="semi_autonomous",
    ),
    "roadmap_autopilot": AutopilotMode(
        id="roadmap_autopilot",
        display_name="Roadmap Autopilot",
        description="Executes roadmap phases with milestone checkpoints, validation, and resumable progress.",
        approval_rules=[
            "Roadmap phase start requires approval unless the phase is analysis-only.",
            "Milestone apply, repair, and terminal actions require approval.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 8,
            "max_repair_attempts": 2,
            "max_files_modified": 25,
            "max_phases_per_run": 3,
            "max_terminal_commands": 8,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=[
            "continue_roadmap",
            "generate_feature",
            "validate_project",
            "repair_project",
            "build_project",
            "scan_workspace",
        ],
        validation_requirements=[
            "Validate each roadmap phase before marking it complete.",
            "Checkpoint after completed milestones before continuing.",
        ],
        checkpoint_rules=[
            "Checkpoint required after each applied roadmap milestone.",
        ],
        rollback_rules=[
            "Roadmap-linked checkpoints are retained in execution memory.",
        ],
        terminal_rules=[
            "Build/test commands require approval and are tied to roadmap phase IDs.",
        ],
        default_execution_mode="roadmap_execution",
    ),
    "repair_autopilot": AutopilotMode(
        id="repair_autopilot",
        display_name="Repair Autopilot",
        description="Runs bounded validation and repair loops, escalating after repeated failures.",
        approval_rules=[
            "Repair generation may proceed after failed validation when scope is known.",
            "Applying repair changes still requires checkpoint and approval.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 5,
            "max_repair_attempts": 3,
            "max_files_modified": 12,
            "max_terminal_commands": 6,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=[
            "repair_project",
            "validate_project",
            "build_project",
        ],
        validation_requirements=[
            "Validation must run before and after repairs.",
            "Repair loop stops at retry limit or unresolved unsafe scope.",
        ],
        checkpoint_rules=[
            "Checkpoint required before repair apply.",
        ],
        rollback_rules=[
            "Rollback is required for every repair apply.",
        ],
        terminal_rules=[
            "Build/test commands require approval and are logged with repair attempts.",
        ],
        default_execution_mode="repair_only",
    ),
    "validation_autopilot": AutopilotMode(
        id="validation_autopilot",
        display_name="Validation Autopilot",
        description="Runs supervised validation workflows and produces reports without modifying files.",
        approval_rules=[
            "Safe validation commands may run when explicitly requested by the client.",
            "Any file modification or repair apply requires approval.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 5,
            "max_repair_attempts": 0,
            "max_files_modified": 0,
            "max_terminal_commands": 5,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
        },
        allowed_workflow_types=[
            "validate_project",
            "build_project",
            "scan_workspace",
            "benchmark_models",
        ],
        validation_requirements=[
            "Validation results must be stored in Core.",
            "Failed validation produces a repair recommendation but does not apply changes.",
        ],
        checkpoint_rules=[
            "Checkpoint is optional for validation-only workflows.",
        ],
        rollback_rules=[
            "Rollback is not required unless approved repair changes are applied.",
        ],
        terminal_rules=[
            "Validation commands run through runtime safety checks and logs.",
        ],
        default_execution_mode="autonomous_validate_only",
    ),
    "experimental_full_autopilot": AutopilotMode(
        id="experimental_full_autopilot",
        display_name="Experimental Full Autopilot",
        description="Maximum supervised automation for labs only; apply still requires checkpoint and explicit approval.",
        approval_rules=[
            "Analysis, planning, validation, and bounded repair loops may proceed automatically.",
            "Apply, restricted files, dangerous commands, and production deployment require explicit approval.",
        ],
        autonomy_limits={
            "max_autonomous_iterations": 12,
            "max_repair_attempts": 4,
            "max_files_modified": 35,
            "max_terminal_commands": 12,
            "max_action_payload_chars": _MAX_ACTION_PAYLOAD_CHARS,
            "allows_terminal_without_approval": False,
            "allows_apply_without_approval": False,
            "allows_checkpoint_without_approval": False,
            "requires_experimental_flag": True,
        },
        allowed_workflow_types=_ALL_WORKFLOW_TYPES,
        validation_requirements=[
            "Validation required before completion.",
            "Regression risk must be reported before apply.",
        ],
        checkpoint_rules=[
            "Checkpoint required before apply.",
            "Checkpoint must be tied to workflow and roadmap metadata.",
        ],
        rollback_rules=[
            "Rollback path must be visible before apply.",
        ],
        terminal_rules=[
            "Runtime safety checks still gate every command.",
        ],
        default_execution_mode="semi_autonomous",
    ),
}


AUTOPILOT_SPECIALIZATIONS: Dict[str, AutopilotSpecialization] = {
    "feature_autopilot": AutopilotSpecialization(
        id="feature_autopilot",
        display_name="Feature Autopilot",
        description="Roadmap-aware feature execution with staged implementation, milestone checkpoints, and architecture-aware validation.",
        workflow_types=["generate_feature", "continue_roadmap", "validate_project", "build_project"],
        recommended_modes=["roadmap_autopilot", "semi_autonomous", "approval_each_step"],
        orchestration_strategy={
            "name": "roadmap_milestone_execution",
            "depth": "phase_based",
            "sequencing": ["roadmap_phase", "feature_slice", "targeted_validation", "milestone_checkpoint"],
            "parallelism": "safe_independent_tasks_only",
            "context_scope": "roadmap_and_impacted_files",
        },
        validation_strategy={
            "name": "feature_validation_ladder",
            "paths": ["targeted_file_checks", "unit_or_script_tests", "build_smoke", "roadmap_acceptance"],
            "escalation": "broaden_after_failed_targeted_check",
            "requires_completion_validation": True,
        },
        repair_strategy={
            "name": "feature_slice_repair",
            "depth": "bounded_slice",
            "root_cause_focus": ["new_code_path", "integration_boundary", "acceptance_gap"],
            "rollback_bias": "checkpoint_milestone",
        },
        safety_rules=[
            "Checkpoint after each applied milestone.",
            "Keep feature slices small enough to review.",
            "Escalate before changing architecture boundaries.",
        ],
        approval_rules=[
            "Implementation and apply require approval.",
            "Roadmap milestone completion requires validation evidence.",
        ],
        model_routing={"profile": "best_coding", "fallback_profile": "balanced", "privacy": "workspace_sensitive"},
        memory_scope={
            "categories": ["successful_workflows", "roadmap_history", "architecture_conventions", "validation_history"],
            "retrieval": "roadmap_phase_and_target_files",
        },
        observability={
            "metrics": ["phase_completion_rate", "validation_pass_rate", "files_per_milestone", "checkpoint_count"],
            "timeline_lanes": ["roadmap", "implementation", "validation", "checkpoint"],
        },
        benchmark_suites=["feature_quality", "validation_success", "execution_duration"],
        ui={
            "label": "Feature",
            "primary_panels": ["roadmap_progress", "execution_strategy", "validation_chain", "milestone_checkpoints"],
            "risk_focus": "architecture_and_integration",
        },
    ),
    "repair_autopilot": AutopilotSpecialization(
        id="repair_autopilot",
        display_name="Repair Autopilot",
        description="Build and validation failure repair with root-cause analysis, repeated-failure detection, and rollback recommendations.",
        workflow_types=["repair_project", "validate_project", "build_project"],
        recommended_modes=["repair_autopilot", "approval_each_step", "semi_autonomous"],
        orchestration_strategy={
            "name": "failure_first_repair",
            "depth": "diagnostic_loop",
            "sequencing": ["capture_failure", "root_cause", "targeted_patch", "rerun_failed_check", "broaden_validation"],
            "parallelism": "single_failure_thread_until_stable",
            "context_scope": "diagnostic_output_and_impacted_dependencies",
        },
        validation_strategy={
            "name": "failure_reproduction_ladder",
            "paths": ["rerun_failed_command", "targeted_dependency_check", "build_or_test_subset", "full_validation_after_pass"],
            "escalation": "full_validation_after_second_repair",
            "requires_completion_validation": True,
        },
        repair_strategy={
            "name": "root_cause_repair",
            "depth": "targeted",
            "root_cause_focus": ["failed_step", "first_diagnostic", "dependency_boundary", "recent_change"],
            "rollback_bias": "recommend_after_repeated_failure",
        },
        safety_rules=[
            "Stop repeated repair patterns early.",
            "Prefer rollback after repeated failed attempts.",
            "Do not broaden file scope without approval.",
        ],
        approval_rules=[
            "Applying repairs requires checkpoint and approval.",
            "Repeated failures escalate to user review.",
        ],
        model_routing={"profile": "best_coding", "fallback_profile": "local_only", "privacy": "diagnostic_sensitive"},
        memory_scope={
            "categories": ["repair_patterns", "recurring_validation_failures", "validation_history", "rollback_history"],
            "retrieval": "failed_command_and_impacted_files",
        },
        observability={
            "metrics": ["repair_success_rate", "repeat_failure_count", "rerun_count", "rollback_recommendations"],
            "timeline_lanes": ["failure", "root_cause", "repair", "validation"],
        },
        benchmark_suites=["repair_accuracy", "validation_success", "repair_duration"],
        ui={
            "label": "Repair",
            "primary_panels": ["failed_check", "root_cause", "repair_attempts", "rollback_recommendation"],
            "risk_focus": "repeat_failures",
        },
    ),
    "refactor_autopilot": AutopilotSpecialization(
        id="refactor_autopilot",
        display_name="Refactor Autopilot",
        description="Architecture-aware refactoring with dependency tracking, symbol/reference awareness, and regression prevention.",
        workflow_types=["generate_feature", "validate_project", "build_project", "scan_workspace"],
        recommended_modes=["approval_each_step", "semi_autonomous"],
        orchestration_strategy={
            "name": "dependency_safe_refactor",
            "depth": "impact_analysis_first",
            "sequencing": ["impact_analysis", "small_refactor_step", "reference_update", "targeted_validation", "broader_regression_check"],
            "parallelism": "disabled_for_symbol_moves",
            "context_scope": "dependency_graph_and_symbol_references",
        },
        validation_strategy={
            "name": "refactor_regression_ladder",
            "paths": ["symbol_reference_check", "impacted_file_validation", "build_or_typecheck", "regression_suite"],
            "escalation": "always_broaden_after_reference_update",
            "requires_completion_validation": True,
        },
        repair_strategy={
            "name": "reference_safe_repair",
            "depth": "conservative",
            "root_cause_focus": ["missing_reference", "circular_dependency", "type_or_build_error"],
            "rollback_bias": "high_for_broad_refactors",
        },
        safety_rules=[
            "Prefer approval_each_step for code movement.",
            "Require dependency impact review before apply.",
            "Checkpoint before every applied refactor step.",
        ],
        approval_rules=[
            "Symbol moves and broad file edits require approval.",
            "High impact analysis requires user confirmation.",
        ],
        model_routing={"profile": "best_reasoning", "fallback_profile": "best_coding", "privacy": "workspace_sensitive"},
        memory_scope={
            "categories": ["architecture_conventions", "dependency_graph", "successful_workflows", "validation_history"],
            "retrieval": "dependency_scope",
        },
        observability={
            "metrics": ["impacted_file_count", "reference_update_count", "regression_risk", "validation_coverage"],
            "timeline_lanes": ["impact", "refactor", "references", "validation"],
        },
        benchmark_suites=["refactor_safety", "validation_success", "regression_detection"],
        ui={
            "label": "Refactor",
            "primary_panels": ["impact_analysis", "dependency_map", "reference_updates", "regression_risk"],
            "risk_focus": "dependency_and_reference_integrity",
        },
    ),
    "deployment_autopilot": AutopilotSpecialization(
        id="deployment_autopilot",
        display_name="Deployment Autopilot",
        description="CI/CD and release preparation with environment analysis, deployment verification, release gates, and rollback readiness.",
        workflow_types=["build_project", "validate_project", "repair_project", "continue_roadmap"],
        recommended_modes=["approval_each_step", "semi_autonomous"],
        orchestration_strategy={
            "name": "release_gate_execution",
            "depth": "environment_and_pipeline",
            "sequencing": ["environment_scan", "pipeline_validation", "release_package_check", "deployment_dry_run", "rollback_plan"],
            "parallelism": "validation_batching_only",
            "context_scope": "ci_cd_configs_and_release_artifacts",
        },
        validation_strategy={
            "name": "deployment_gate_ladder",
            "paths": ["ci_config_lint", "build_check", "test_check", "release_dry_run", "rollback_readiness_check"],
            "escalation": "block_on_failed_release_gate",
            "requires_completion_validation": True,
        },
        repair_strategy={
            "name": "pipeline_repair",
            "depth": "gated",
            "root_cause_focus": ["ci_step", "environment_config", "secret_boundary", "artifact_generation"],
            "rollback_bias": "mandatory_for_release_changes",
        },
        safety_rules=[
            "Production deploy remains approval-only.",
            "Secret-bearing files require explicit review.",
            "Rollback plan must be visible before completion.",
        ],
        approval_rules=[
            "Deployment and release actions require approval.",
            "High-risk config changes require approval_each_step.",
        ],
        model_routing={"profile": "private_sensitive", "fallback_profile": "local_only", "privacy": "deployment_sensitive"},
        memory_scope={
            "categories": ["deployment_history", "recurring_validation_failures", "rollback_history", "environment_configs"],
            "retrieval": "pipeline_and_environment",
        },
        observability={
            "metrics": ["gate_pass_rate", "deployment_readiness", "rollback_readiness", "pipeline_failure_rate"],
            "timeline_lanes": ["environment", "ci_cd", "release_gate", "rollback"],
        },
        benchmark_suites=["deployment_reliability", "validation_success", "rollback_readiness"],
        ui={
            "label": "Deployment",
            "primary_panels": ["pipeline_gates", "environment_risk", "release_history", "rollback_plan"],
            "risk_focus": "release_and_secret_safety",
        },
    ),
    "workspace_intelligence_autopilot": AutopilotSpecialization(
        id="workspace_intelligence_autopilot",
        display_name="Workspace Intelligence Autopilot",
        description="Read-mostly architecture intelligence, roadmap generation, dependency analysis, technical debt review, and onboarding documentation.",
        workflow_types=["scan_workspace", "research_task", "continue_roadmap", "validate_project", "chat_request"],
        recommended_modes=["suggest_only", "validation_autopilot", "semi_autonomous"],
        orchestration_strategy={
            "name": "knowledge_first_analysis",
            "depth": "read_mostly",
            "sequencing": ["workspace_scan", "knowledge_graph_refresh", "architecture_summary", "risk_analysis", "roadmap_recommendations"],
            "parallelism": "safe_read_parallelism",
            "context_scope": "workspace_intelligence_memory",
        },
        validation_strategy={
            "name": "analysis_freshness_checks",
            "paths": ["index_freshness", "config_consistency", "documentation_smoke", "optional_validation"],
            "escalation": "ask_before_mutating_docs",
            "requires_completion_validation": False,
        },
        repair_strategy={
            "name": "knowledge_refresh_repair",
            "depth": "read_mostly",
            "root_cause_focus": ["stale_index", "missing_metadata", "unsupported_language"],
            "rollback_bias": "low_without_file_changes",
        },
        safety_rules=[
            "Default to read-only analysis.",
            "Documentation writes require approval and checkpoint.",
            "Do not apply code changes from intelligence-only runs.",
        ],
        approval_rules=[
            "Generated docs or roadmap file writes require approval.",
            "Workspace scan and summaries can run without file mutation.",
        ],
        model_routing={"profile": "best_reasoning", "fallback_profile": "balanced", "privacy": "workspace_sensitive"},
        memory_scope={
            "categories": ["architecture_conventions", "technical_debt", "roadmap_history", "workspace_summaries"],
            "retrieval": "whole_workspace_summaries",
        },
        observability={
            "metrics": ["index_freshness", "summary_coverage", "unsupported_language_count", "roadmap_quality"],
            "timeline_lanes": ["scan", "knowledge", "architecture", "roadmap"],
        },
        benchmark_suites=["roadmap_quality", "architecture_summary_coverage", "indexing_performance"],
        ui={
            "label": "Workspace Intelligence",
            "primary_panels": ["architecture_summary", "dependency_analysis", "technical_debt", "roadmap"],
            "risk_focus": "staleness_and_coverage",
        },
    ),
}


def autopilot_modes() -> Dict[str, Any]:
    """Return formal Autopilot execution mode definitions."""

    return {
        "modes": [mode.as_dict() for mode in AUTOPILOT_MODES.values()],
        "specializations": [profile.as_dict() for profile in AUTOPILOT_SPECIALIZATIONS.values()],
        "states": list(AUTOPILOT_STATES),
        "default_mode": "semi_autonomous",
        "default_specialization": "feature_autopilot",
        "safety_invariants": [
            "Autopilot never applies file changes without Core checkpoint and approval gates.",
            "Autopilot uses existing Core path normalization and workspace restrictions.",
            "Dangerous terminal commands are blocked or escalated by runtime command safety.",
            "Repair loops are bounded and escalate when retry limits are reached.",
            "Every action is journaled for replay and audit.",
            "Every run exposes confidence, validation confidence, regression risk, and rollback readiness.",
            "Autopilot action payloads, terminal commands, retries, and file counts are bounded by mode limits.",
            "Workflow specializations tune orchestration, validation, repair, memory, and UI without weakening mode safety rules.",
        ],
    }


def start_autopilot(
    workspace: Path,
    objective: str,
    *,
    mode: str = "semi_autonomous",
    workflow_type: str = "generate_feature",
    roadmap: Optional[List[Mapping[str, Any]]] = None,
    target_files: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    validation_commands: Optional[List[Mapping[str, Any]]] = None,
    execution_plan: Optional[Mapping[str, Any]] = None,
    specialization: Optional[str] = None,
    client_id: Optional[str] = None,
    approval: bool = False,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a supervised Autopilot run backed by an engineering execution."""

    root = Path(workspace).resolve()
    mode_def = _mode_or_raise(mode)
    workflow_type = _workflow_type_or_raise(workflow_type, mode_def)
    objective = (objective or "").strip()
    if not objective:
        raise ValueError("objective is required")

    requested_files = _dedupe_strings(target_files or [])
    profile = _specialization_or_infer(
        specialization,
        mode=mode_def.id,
        workflow_type=workflow_type,
        objective=objective,
        target_files=requested_files,
        roadmap=roadmap or [],
        metadata=metadata or {},
    )
    _workflow_type_or_raise_for_specialization(workflow_type, profile)
    limits = dict(mode_def.autonomy_limits)
    profile_file_limit = _profile_file_limit(profile)
    effective_file_limit = min(
        int(limits.get("max_files_modified", profile_file_limit) or profile_file_limit),
        profile_file_limit,
    )
    if limits.get("max_files_modified", 0) == 0 and requested_files:
        raise ValueError(f"mode {mode_def.id!r} does not allow target file modifications")
    if effective_file_limit >= 0 and len(requested_files) > effective_file_limit:
        raise ValueError(
            f"target file count exceeds {profile.id} effective limit of {effective_file_limit}"
        )

    execution_metadata = dict(metadata or {})
    execution_metadata.update(
        {
            "autopilot_mode": mode_def.id,
            "autopilot_specialization": profile.id,
            "autopilot_specialization_profile": profile.as_dict(),
            "autopilot_client_id": client_id,
            "autopilot_requested_files": requested_files,
            "autopilot_execution_plan": dict(execution_plan or {}),
            "autopilot_roadmap": [dict(item) for item in roadmap or []],
            "autopilot": True,
        }
    )
    merged_constraints = _dedupe_strings(list(constraints or []) + profile.safety_rules + profile.approval_rules)
    collaboration_context = _collaboration_context(root, metadata or {})
    governance_context = _governance_context(
        root,
        {
            **dict(metadata or {}),
            "action_type": "autopilot_start",
            "workflow_type": workflow_type,
            "mode": mode_def.id,
            "target_files": requested_files,
            "objective": objective,
            "client_id": client_id or "autopilot",
            "actor_role": dict(metadata or {}).get("actor_role", "maintainer"),
        },
        approval=approval,
    )
    deep_intelligence = _deep_engineering_intelligence_context(
        root,
        workflow_type=workflow_type,
        objective=objective,
        target_files=requested_files,
        metadata=metadata or {},
    )

    if roadmap:
        first_item = dict(roadmap[0]) if roadmap else {}
        execution_dashboard = engineering_execution.create_roadmap_execution(
            root,
            goal=objective,
            roadmap_item_id=str(first_item.get("id") or first_item.get("roadmap_item_id") or ""),
            roadmap_phase_id=str(first_item.get("phase_id") or first_item.get("roadmap_phase_id") or ""),
            source_client=client_id or "autopilot",
            target_files=requested_files,
            validation_command=_validation_command(validation_commands),
            constraints=merged_constraints,
            metadata=execution_metadata,
        )
        execution = dict(execution_dashboard["execution"])
        if objective and not execution.get("objective"):
            execution["objective"] = objective
    else:
        execution_dashboard = engineering_execution.create_execution(
            root,
            goal=objective,
            mode=mode_def.default_execution_mode,
            source_client=client_id or "autopilot",
            target_files=requested_files,
            constraints=merged_constraints,
            validation_command=_validation_command(validation_commands),
            metadata=execution_metadata,
        )
        execution = dict(execution_dashboard["execution"])

    now = _now()
    run = {
        "id": _new_id("autopilot"),
        "mode": mode_def.id,
        "workflow_type": workflow_type,
        "specialization": profile.id,
        "specialization_profile": profile.as_dict(),
        "execution_strategy": dict(profile.orchestration_strategy),
        "validation_strategy": dict(profile.validation_strategy),
        "repair_strategy": dict(profile.repair_strategy),
        "approval_strategy": {
            "rules": list(profile.approval_rules),
            "mode_rules": list(mode_def.approval_rules),
            "strategy": "specialization_plus_mode",
        },
        "model_routing": dict(profile.model_routing),
        "memory_scope": dict(profile.memory_scope),
        "specialized_observability": dict(profile.observability),
        "specialization_benchmarks": list(profile.benchmark_suites),
        "status": "running" if approval or mode_def.id != "approval_each_step" else "waiting_approval",
        "objective": objective,
        "workspace": str(root),
        "client_id": client_id,
        "execution_id": execution["id"],
        "workflow_id": execution.get("workflow_id"),
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "finished_at": None,
        "iterations": 0,
        "repair_attempts": 0,
        "rollback_count": 0,
        "approval_interruptions": 0,
        "active_agent": _active_agent_for_stage(_active_stage(execution)),
        "current_task": _current_task(execution),
        "target_files": requested_files,
        "files_being_modified": requested_files,
        "validation_status": "not_started",
        "checkpoint_status": "not_started",
        "rollback_available": False,
        "execution_risk_level": _risk_level(requested_files, mode_def),
        "confidence_score": 0,
        "validation_confidence": 0,
        "repair_confidence": 0,
        "regression_risk": 0,
        "rollback_readiness": 0,
        "trust_scorecard": {},
        "predictions": {},
        "validation_intelligence": {},
        "deep_engineering_intelligence": deep_intelligence,
        "checkpoint_intelligence": {},
        "bounded_autonomy": {},
        "explanations": [],
        "decision_log": [],
        "blocked_actions": [],
        "last_simulation": None,
        "pending_approvals": [],
        "approval_history": [],
        "validation_chain": [],
        "repair_history": [],
        "terminal_jobs": [],
        "roadmap_progress": _roadmap_progress(roadmap or [], execution),
        "collaboration": collaboration_context,
        "governance": governance_context,
        "safety": _safety_summary(mode_def),
        "mode_contract": mode_def.as_dict(),
        "limits": dict(mode_def.autonomy_limits),
        "logs": [
            {
                "timestamp": now,
                "level": "info",
                "message": f"Autopilot run created in {mode_def.id} mode.",
            }
        ],
        "last_operation": "created",
        "metadata": dict(metadata or {}),
    }

    if mode_def.id == "approval_each_step" and not approval:
        _queue_approval(run, "intake", "Approval Each Step mode requires approval before intake.")
    if collaboration_context.get("requires_approval"):
        required_roles = ", ".join(collaboration_context.get("required_roles", [])) or "reviewer"
        _queue_approval(
            run,
            "collaboration_approval",
            f"Collaborative approval chain requires signoff from: {required_roles}.",
        )
    if governance_context.get("requires_approval"):
        run["status"] = "waiting_approval"
        if governance_context.get("blocked"):
            run.setdefault("blocked_actions", []).append(
                {
                    "action": "autopilot_start",
                    "reason": governance_context.get("explanation", "Policy governance blocked the run."),
                    "timestamp": now,
                    "policy_violations": governance_context.get("violations", []),
                }
            )
        _queue_approval(
            run,
            "policy_governance",
            governance_context.get("explanation") or "Policy governance requires approval before Autopilot continues.",
        )

    _record_decision(
        run,
        "mode_selected",
        f"Selected {mode_def.id} because the client requested supervised {workflow_type} execution.",
        evidence={"mode": mode_def.id, "workflow_type": workflow_type, "target_files": requested_files},
    )
    _record_decision(
        run,
        "specialization_selected",
        f"Selected {profile.display_name} for workflow-specific orchestration, validation, repair, memory, and UI strategy.",
        evidence={"specialization": profile.id, "workflow_type": workflow_type, "strategy": profile.orchestration_strategy.get("name")},
    )
    _record_decision(
        run,
        "risk_initialized",
        "Initial risk was estimated from Autopilot mode, target file count, and sensitive path patterns.",
        evidence={"risk_level": run.get("execution_risk_level"), "target_files": requested_files},
    )
    _record_decision(
        run,
        "policy_evaluated",
        governance_context.get("explanation", "Governance policy evaluation completed."),
        evidence={"status": governance_context.get("status"), "violations": governance_context.get("violations", [])},
    )
    _update_reliability_state(root, run, execution)
    _save_run(root, run)
    _append_event(
        root,
        run,
        "autopilot_started",
        {
            "mode": mode_def.id,
            "workflow_type": workflow_type,
            "execution_id": execution["id"],
            "workflow_id": execution.get("workflow_id"),
        },
    )
    _record_memory(root, run, reason="autopilot_started")
    refreshed = _refresh_run(root, run["id"])
    return {
        "run": refreshed,
        "supervision": autopilot_supervision(root, refreshed["id"]),
        "modes": autopilot_modes(),
    }


def list_autopilot_runs(
    workspace: Path,
    *,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    workflow_type: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    root = Path(workspace).resolve()
    runs = _load_runs(root)
    if status:
        runs = [run for run in runs if run.get("status") == status]
    if mode:
        runs = [run for run in runs if run.get("mode") == mode]
    if workflow_type:
        runs = [run for run in runs if run.get("workflow_type") == workflow_type]
    runs = sorted(runs, key=lambda item: item.get("updated_at", ""), reverse=True)
    return {
        "runs": runs[: max(1, int(limit))],
        "total": len(runs),
        "filters": {
            "status": status,
            "mode": mode,
            "workflow_type": workflow_type,
        },
    }


def get_autopilot_run(workspace: Path, autopilot_id: str) -> Dict[str, Any]:
    return _refresh_run(Path(workspace).resolve(), autopilot_id)


def autopilot_action(
    workspace: Path,
    autopilot_id: str,
    action: str,
    *,
    approval: bool = False,
    payload: Optional[Mapping[str, Any]] = None,
    summary: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform a supervised action against an Autopilot run."""

    root = Path(workspace).resolve()
    run = _load_run(root, autopilot_id)
    payload_dict = dict(payload or {})
    action = (action or "advance").strip().lower()
    now = _now()
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    payload_chars = _payload_size(payload_dict)
    max_payload_chars = int(mode_def.autonomy_limits.get("max_action_payload_chars", _MAX_ACTION_PAYLOAD_CHARS))
    if payload_chars > max_payload_chars:
        raise ValueError(
            f"autopilot action payload exceeds bounded context limit ({payload_chars} > {max_payload_chars})"
        )

    if run.get("status") in {"completed", "failed", "cancelled"} and action not in {"replay"}:
        raise ValueError(f"autopilot run {autopilot_id} is already {run.get('status')}")

    run["updated_at"] = now
    run["last_operation"] = action
    run.setdefault("logs", []).append(
        {
            "timestamp": now,
            "level": "info",
            "message": summary or f"Autopilot action requested: {action}",
            "client_id": client_id,
        }
    )

    governance_context = _governance_action_context(root, run, action, payload_dict, approval=approval, client_id=client_id)
    run["governance"] = governance_context
    if _policy_pauses_action(action, governance_context, approval):
        run["status"] = "waiting_approval"
        run.setdefault("blocked_actions", []).append(
            {
                "action": action,
                "reason": governance_context.get("explanation", "Policy governance requires approval."),
                "timestamp": now,
                "policy_violations": governance_context.get("violations", []),
            }
        )
        _queue_approval(
            run,
            "policy_governance",
            governance_context.get("explanation") or f"Policy governance requires approval before `{action}`.",
        )
        _record_decision(
            run,
            "policy_action_paused",
            governance_context.get("explanation", f"Policy governance paused `{action}`."),
            evidence={"action": action, "status": governance_context.get("status"), "violations": governance_context.get("violations", [])},
        )
        _update_reliability_state(root, run)
        _save_run(root, run)
        _append_event(root, run, "autopilot_policy_paused", {"action": action, "approval": approval, "policy": governance_context})
        refreshed = _refresh_run(root, autopilot_id)
        _record_memory(root, refreshed, reason=f"policy-paused:{action}")
        return {
            "run": refreshed,
            "supervision": autopilot_supervision(root, autopilot_id),
            "event": _latest_event(root, autopilot_id),
        }

    if action in {"pause", "resume", "cancel"}:
        _apply_lifecycle_action(root, run, action, payload_dict, approval)
    elif action in {"approve", "reject"}:
        _apply_approval_action(root, run, action, payload_dict, summary, client_id)
    elif action in {"advance", "tick", "step"}:
        _apply_tick(root, run, payload_dict, approval)
    elif action in {"run_validation", "record_validation"}:
        _apply_validation_action(root, run, payload_dict, approval, action)
    elif action in {"record_repair", "repair"}:
        _apply_repair_action(root, run, payload_dict, approval)
    elif action in {"checkpoint", "create_checkpoint"}:
        _apply_checkpoint_action(root, run, payload_dict, approval)
    elif action in {"record_rollback", "rollback"}:
        _apply_rollback_action(root, run, payload_dict)
    elif action in _TERMINAL_ACTIONS:
        _apply_terminal_action(root, run, payload_dict, approval, client_id)
    elif action in _SIMULATION_ACTIONS:
        _apply_simulation_action(root, run, payload_dict)
    elif action in {"complete", "finish"}:
        _complete_run(root, run, payload_dict, summary)
    else:
        raise ValueError(f"unsupported autopilot action: {action}")

    _update_reliability_state(root, run)
    _save_run(root, run)
    _append_event(root, run, f"autopilot_{action}", {"payload": _safe_payload(payload_dict), "approval": approval})
    refreshed = _refresh_run(root, autopilot_id)
    _record_memory(root, refreshed, reason=f"action:{action}")
    return {
        "run": refreshed,
        "supervision": autopilot_supervision(root, autopilot_id),
        "event": _latest_event(root, autopilot_id),
    }


def autopilot_supervision(workspace: Path, autopilot_id: Optional[str] = None) -> Dict[str, Any]:
    """Return the command-center supervision snapshot for active clients."""

    root = Path(workspace).resolve()
    runs = _load_runs(root)
    if autopilot_id:
        runs = [_refresh_run(root, autopilot_id)]
    else:
        runs = [
            run
            for run in runs
            if run.get("status") in {"queued", "running", "waiting_approval", "paused", "validating", "repairing"}
        ]
        runs = sorted(runs, key=lambda item: item.get("updated_at", ""), reverse=True)
    active = runs[0] if runs else None
    return {
        "active_run": active,
        "active_workflow": active.get("workflow_id") if active else None,
        "active_agent": active.get("active_agent") if active else None,
        "current_task": active.get("current_task") if active else None,
        "files_being_modified": active.get("files_being_modified", []) if active else [],
        "specialization": active.get("specialization") if active else None,
        "execution_strategy": active.get("execution_strategy", {}) if active else {},
        "validation_strategy": active.get("validation_strategy", {}) if active else {},
        "repair_strategy": active.get("repair_strategy", {}) if active else {},
        "model_routing": active.get("model_routing", {}) if active else {},
        "memory_scope": active.get("memory_scope", {}) if active else {},
        "governance": active.get("governance", {}) if active else {},
        "specialized_observability": active.get("specialized_observability", {}) if active else {},
        "specialization_benchmarks": active.get("specialization_benchmarks", []) if active else [],
        "pending_approvals": _collect_pending_approvals(runs),
        "validation_status": active.get("validation_status") if active else "idle",
        "repair_attempts": active.get("repair_attempts", 0) if active else 0,
        "rollback_available": bool(active and active.get("rollback_available")),
        "execution_risk_level": active.get("execution_risk_level") if active else "none",
        "confidence_score": active.get("confidence_score", 0) if active else 0,
        "validation_confidence": active.get("validation_confidence", 0) if active else 0,
        "repair_confidence": active.get("repair_confidence", 0) if active else 0,
        "regression_risk": active.get("regression_risk", 0) if active else 0,
        "rollback_readiness": active.get("rollback_readiness", 0) if active else 0,
        "trust_scorecard": active.get("trust_scorecard", {}) if active else {},
        "predictions": active.get("predictions", {}) if active else {},
        "validation_intelligence": active.get("validation_intelligence", {}) if active else {},
        "deep_engineering_intelligence": active.get("deep_engineering_intelligence", {}) if active else {},
        "checkpoint_intelligence": active.get("checkpoint_intelligence", {}) if active else {},
        "bounded_autonomy": active.get("bounded_autonomy", {}) if active else {},
        "explanations": active.get("explanations", []) if active else [],
        "audit_trail": active.get("decision_log", [])[-25:] if active else [],
        "running_runs": [run for run in runs if run.get("status") == "running"],
        "paused_runs": [run for run in runs if run.get("status") == "paused"],
        "failed_runs": [run for run in runs if run.get("status") == "failed"],
        "recent_events": _recent_events(root, autopilot_id=autopilot_id, limit=25),
        "runtime_status": _runtime_status(root),
        "client_actions": autopilot_client_hooks()["actions"],
        "safety_visibility": _safety_visibility(active),
    }


def autopilot_observability(workspace: Path) -> Dict[str, Any]:
    """Return aggregate Autopilot runtime health and execution metrics."""

    root = Path(workspace).resolve()
    runs = []
    for run in _load_runs(root):
        try:
            runs.append(_refresh_run(root, str(run.get("id"))))
        except Exception:
            runs.append(run)
    completed = [run for run in runs if run.get("status") == "completed"]
    failed = [run for run in runs if run.get("status") == "failed"]
    cancelled = [run for run in runs if run.get("status") == "cancelled"]
    durations = [
        _duration_seconds(run.get("started_at"), run.get("finished_at") or run.get("updated_at"))
        for run in runs
        if run.get("started_at") and (run.get("finished_at") or run.get("updated_at"))
    ]
    validation_runs = [
        item
        for run in runs
        for item in run.get("validation_chain", [])
        if isinstance(item, Mapping)
    ]
    validation_success = [item for item in validation_runs if item.get("passed") is True]
    repair_runs = [
        item
        for run in runs
        for item in run.get("repair_history", [])
        if isinstance(item, Mapping)
    ]
    repair_success = [item for item in repair_runs if item.get("success") is True]
    approval_interruptions = sum(int(run.get("approval_interruptions", 0)) for run in runs)
    rollback_frequency = sum(int(run.get("rollback_count", 0)) for run in runs)
    confidence_scores = [float(run.get("confidence_score", 0) or 0) for run in runs if run.get("confidence_score") is not None]
    regression_risks = [float(run.get("regression_risk", 0) or 0) for run in runs if run.get("regression_risk") is not None]
    blocked_action_count = sum(len(run.get("blocked_actions", []) or []) for run in runs)
    hotspots = _failure_hotspots(runs)
    return {
        "run_count": len(runs),
        "active_count": len([run for run in runs if run.get("status") in {"queued", "running", "waiting_approval", "paused", "validating", "repairing"}]),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "cancelled_count": len(cancelled),
        "workflow_completion_rate": _ratio(len(completed), len(runs)),
        "validation_success_rate": _ratio(len(validation_success), len(validation_runs)),
        "repair_success_rate": _ratio(len(repair_success), len(repair_runs)),
        "rollback_frequency": rollback_frequency,
        "approval_interruptions": approval_interruptions,
        "average_confidence_score": round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0,
        "average_regression_risk": round(sum(regression_risks) / len(regression_risks), 2) if regression_risks else 0.0,
        "blocked_action_count": blocked_action_count,
        "average_execution_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0.0,
        "failure_hotspots": hotspots,
        "unstable_workflows": _unstable_workflows(runs),
        "recurring_repair_failures": _recurring_repair_failures(runs),
        "risky_execution_paths": _risky_execution_paths(runs),
        "risk_distribution": _distribution(run.get("execution_risk_level") for run in runs),
        "confidence_distribution": _confidence_distribution(confidence_scores),
        "specialization_distribution": _distribution(run.get("specialization") for run in runs),
        "specialization_benchmarks": _specialization_benchmark_map(runs),
        "mode_distribution": _distribution(run.get("mode") for run in runs),
        "workflow_distribution": _distribution(run.get("workflow_type") for run in runs),
        "recent_events": _recent_events(root, limit=50),
    }


def autopilot_memory(workspace: Path) -> Dict[str, Any]:
    """Return persisted execution memory used by Autopilot planning."""

    root = Path(workspace).resolve()
    memory = _load_autopilot_memory(root)
    return {
        "memory": memory,
        "categories": [
            "completed_roadmap_phases",
            "prior_failures",
            "repair_outcomes",
            "preferred_execution_strategies",
            "validation_history",
            "workflow_outcomes",
            "per_specialization",
        ],
        "privacy": {
            "storage": "local_project_aegis_folder",
            "editable": True,
            "exportable": True,
            "cloud_sync": False,
        },
    }


def autopilot_replay(workspace: Path, autopilot_id: str) -> Dict[str, Any]:
    """Return replayable execution timeline for UI and diagnostics exports."""

    root = Path(workspace).resolve()
    run = _refresh_run(root, autopilot_id)
    events = _recent_events(root, autopilot_id=autopilot_id, limit=500)
    execution_timeline: Dict[str, Any] = {}
    try:
        if run.get("execution_id"):
            execution_timeline = engineering_execution.execution_timeline(root, run["execution_id"])
    except Exception as exc:  # pragma: no cover - defensive replay path
        execution_timeline = {"error": str(exc), "events": []}
    return {
        "run": run,
        "events": events,
        "execution_timeline": execution_timeline,
        "validation_chain": run.get("validation_chain", []),
        "repair_chain": run.get("repair_history", []),
        "approvals": run.get("approval_history", []),
        "decision_log": run.get("decision_log", []),
        "trust_scorecard": run.get("trust_scorecard", {}),
        "predictions": run.get("predictions", {}),
        "last_simulation": run.get("last_simulation"),
        "rollbacks": [
            event for event in events if event.get("type") in {"autopilot_rollback", "autopilot_record_rollback"}
        ],
        "terminal_jobs": run.get("terminal_jobs", []),
    }


def autopilot_client_hooks() -> Dict[str, Any]:
    """Stable integration hooks for Website, Desktop, VS Code, and Visual Studio."""

    actions = [
        {
            "id": "start_autopilot",
            "description": "Start a supervised Autopilot workflow.",
            "requires_approval": False,
        },
        {
            "id": "pause",
            "description": "Pause the active Autopilot run.",
            "requires_approval": False,
        },
        {
            "id": "resume",
            "description": "Resume a paused Autopilot run.",
            "requires_approval": False,
        },
        {
            "id": "approve",
            "description": "Approve the current pending stage or action.",
            "requires_approval": True,
        },
        {
            "id": "reject",
            "description": "Reject the current pending stage or action.",
            "requires_approval": False,
        },
        {
            "id": "inspect_diff",
            "description": "Open the generated diff/proposal before apply.",
            "requires_approval": False,
        },
        {
            "id": "simulate",
            "description": "Preview likely stages, validation targets, risk, and rollback needs without changing files.",
            "requires_approval": False,
        },
        {
            "id": "run_validation",
            "description": "Run validation through Core runtime safety.",
            "requires_approval": True,
        },
        {
            "id": "checkpoint",
            "description": "Create a Core checkpoint before apply.",
            "requires_approval": True,
        },
        {
            "id": "rollback",
            "description": "Restore a Core checkpoint.",
            "requires_approval": True,
        },
        {
            "id": "cancel",
            "description": "Cancel the active Autopilot run.",
            "requires_approval": False,
        },
    ]
    return {
        "actions": actions,
        "events": [
            "autopilot_started",
            "autopilot_advance",
            "autopilot_waiting_approval",
            "autopilot_validation",
            "autopilot_repair",
            "autopilot_checkpoint",
            "autopilot_rollback",
            "autopilot_simulate",
            "autopilot_completed",
            "autopilot_failed",
            "autopilot_cancelled",
        ],
        "client_surfaces": {
            "website": ["Autopilot Center", "approval queue", "timeline", "validation chain", "trust scorecard", "live logs"],
            "desktop": ["runtime status", "active agents", "approval queue", "confidence/risk", "rollback controls"],
            "vscode": ["start/pause/resume", "diff review", "validation result", "risk preview", "rollback checkpoints"],
            "visual_studio": ["solution scan", "build repair", "proposal review", "validation confidence", "rollback checkpoints"],
        },
        "contract_version": "1.0",
    }


def _apply_lifecycle_action(
    root: Path,
    run: MutableMapping[str, Any],
    action: str,
    payload: Mapping[str, Any],
    approval: bool,
) -> None:
    if action == "pause":
        run["status"] = "paused"
        _record_decision(run, "workflow_paused", "User or client paused Autopilot execution.", evidence=dict(payload))
        _step_execution_safe(root, run, "pause", payload=payload, approval=approval)
    elif action == "resume":
        run["status"] = "running"
        _record_decision(run, "workflow_resumed", "Autopilot resumed from a paused state.", evidence=dict(payload))
        _step_execution_safe(root, run, "resume", payload=payload, approval=approval)
    elif action == "cancel":
        run["status"] = "cancelled"
        run["finished_at"] = _now()
        _record_decision(run, "workflow_cancelled", "Autopilot run was cancelled before completion.", evidence=dict(payload))
        _step_execution_safe(root, run, "cancel", payload=payload, approval=approval)


def _apply_approval_action(
    root: Path,
    run: MutableMapping[str, Any],
    action: str,
    payload: Mapping[str, Any],
    summary: Optional[str],
    client_id: Optional[str],
) -> None:
    stage_key = str(payload.get("stage_key") or _active_stage_for_run(root, run) or "unknown")
    approval_record = {
        "id": _new_id("approval"),
        "timestamp": _now(),
        "stage_key": stage_key,
        "action": action,
        "summary": summary or payload.get("summary") or f"{action} at {stage_key}",
        "client_id": client_id,
    }
    run.setdefault("approval_history", []).append(approval_record)
    if action == "approve":
        run["pending_approvals"] = [
            item for item in run.get("pending_approvals", []) if item.get("stage_key") != stage_key
        ]
        run["status"] = "running"
        _record_decision(
            run,
            "approval_granted",
            f"User approved Autopilot to continue at {stage_key}.",
            evidence=approval_record,
        )
        _step_execution_safe(root, run, "approve", payload={"stage_key": stage_key, **dict(payload)}, approval=True)
        if payload.get("advance_after_approval", True):
            _step_execution_safe(
                root,
                run,
                "advance",
                stage_key=stage_key,
                payload={"approval_summary": approval_record["summary"], **dict(payload)},
                approval=True,
            )
    else:
        run["status"] = "waiting_approval"
        _record_decision(
            run,
            "approval_rejected",
            f"User rejected Autopilot continuation at {stage_key}; revision is required.",
            evidence=approval_record,
        )
        _queue_approval(run, stage_key, f"Rejected approval requires revision before continuing: {summary or ''}".strip())


def _apply_tick(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    approval: bool,
) -> None:
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    execution = _linked_execution(root, run)
    stage_key = _active_stage(execution)
    if not stage_key:
        _complete_run(root, run, payload, "Linked execution already completed.")
        return

    run["active_agent"] = _active_agent_for_stage(stage_key)
    run["current_task"] = _stage_title(stage_key)
    run["iterations"] = int(run.get("iterations", 0)) + 1
    if run["iterations"] > int(mode_def.autonomy_limits.get("max_autonomous_iterations", 1)):
        _block_action(
            run,
            "advance",
            f"Autonomy iteration limit reached for {mode_def.id}.",
            evidence={"iterations": run["iterations"], "limit": mode_def.autonomy_limits.get("max_autonomous_iterations")},
        )
        _queue_approval(
            run,
            stage_key,
            f"Autonomy iteration limit reached for {mode_def.id}; approval required to continue.",
        )
        run["status"] = "waiting_approval"
        return

    if _stage_requires_approval(mode_def, stage_key) and not approval:
        _record_decision(
            run,
            "approval_required",
            _approval_reason(mode_def, stage_key),
            stage_key=stage_key,
            evidence={"mode": mode_def.id},
        )
        _queue_approval(run, stage_key, _approval_reason(mode_def, stage_key))
        run["status"] = "waiting_approval"
        return

    if stage_key == "implementation" and not payload.get("complete"):
        _record_decision(
            run,
            "implementation_waiting_review",
            "Implementation was not advanced because no reviewed proposal or completion signal was provided.",
            stage_key=stage_key,
        )
        _queue_approval(run, stage_key, "Implementation requires a reviewed proposal or explicit completion signal.")
        run["status"] = "waiting_approval"
        return

    if stage_key == "validation":
        if payload.get("command") or payload.get("commands"):
            _apply_validation_action(root, run, payload, approval, "run_validation")
        else:
            _record_decision(
                run,
                "validation_waiting_command",
                "Validation stage needs an approved command or recorded result before Autopilot can continue.",
                stage_key=stage_key,
                evidence={"recommended_targets": _validation_targets(root, run, execution)},
            )
            _queue_approval(run, stage_key, "Validation stage needs an approved validation command or recorded result.")
            run["status"] = "waiting_approval"
        return

    if stage_key == "repair":
        if _latest_validation_ok(run, execution):
            _step_execution_safe(
                root,
                run,
                "advance",
                stage_key="repair",
                payload={"summary": "Repair skipped because validation passed."},
                approval=True,
            )
            run["status"] = "running"
            return
        max_repairs = int(mode_def.autonomy_limits.get("max_repair_attempts", 0))
        if int(run.get("repair_attempts", 0)) >= max_repairs:
            _block_action(
                run,
                "repair",
                "Repair retry limit reached; user review required.",
                stage_key=stage_key,
                evidence={"repair_attempts": run.get("repair_attempts", 0), "limit": max_repairs},
            )
            _queue_approval(run, stage_key, "Repair retry limit reached; user review required.")
            run["status"] = "waiting_approval"
            return
        if payload.get("repair_attempt"):
            _apply_repair_action(root, run, payload, approval)
        else:
            _record_decision(
                run,
                "repair_waiting_plan",
                "Repair stage requires a bounded repair plan or user revision before continuing.",
                stage_key=stage_key,
            )
            _queue_approval(run, stage_key, "Repair stage requires a bounded repair plan or user revision.")
            run["status"] = "waiting_approval"
        return

    if stage_key == "checkpoint":
        _apply_checkpoint_action(root, run, payload, approval)
        return

    _step_execution_safe(
        root,
        run,
        "advance",
        stage_key=stage_key,
        payload=dict(payload),
        approval=approval or not _stage_requires_approval(mode_def, stage_key),
    )
    run["status"] = "running"


def _apply_validation_action(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    approval: bool,
    action: str,
) -> None:
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    if action == "run_validation" and _stage_requires_approval(mode_def, "validation") and not approval:
        _record_decision(
            run,
            "validation_approval_required",
            "Validation command execution was paused because this mode requires approval.",
            stage_key="validation",
        )
        _queue_approval(run, "validation", "Validation command execution requires approval in this mode.")
        run["status"] = "waiting_approval"
        return
    run["status"] = "validating"
    result = _step_execution_safe(
        root,
        run,
        "run_validation" if action == "run_validation" else "record_validation",
        stage_key="validation",
        payload=dict(payload),
        approval=approval,
    )
    validation = _extract_validation_result(result, payload)
    if validation:
        validation.setdefault("id", _new_id("validation"))
        validation.setdefault("timestamp", _now())
        validation.setdefault("targeted_validation", _validation_targets(root, run, _linked_execution(root, run)))
        run.setdefault("validation_chain", []).append(validation)
        passed = _validation_passed(validation)
        run["validation_status"] = "passed" if passed else "failed"
        _record_decision(
            run,
            "validation_recorded",
            "Validation result was captured and added to the Autopilot validation chain.",
            stage_key="validation",
            evidence={"passed": passed, "summary": validation.get("summary"), "targeted_validation": validation.get("targeted_validation")},
        )
        if passed is False:
            run["status"] = "repairing" if int(mode_def.autonomy_limits.get("max_repair_attempts", 0)) else "waiting_approval"
            if run["status"] == "waiting_approval":
                _queue_approval(run, "repair", "Validation failed and this mode cannot repair autonomously.")
        else:
            run["status"] = "running"


def _apply_repair_action(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    approval: bool,
) -> None:
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    max_repairs = int(mode_def.autonomy_limits.get("max_repair_attempts", 0))
    if int(run.get("repair_attempts", 0)) >= max_repairs:
        _block_action(
            run,
            "repair",
            "Repair retry limit reached; user approval and revised plan required.",
            stage_key="repair",
            evidence={"repair_attempts": run.get("repair_attempts", 0), "limit": max_repairs},
        )
        _queue_approval(run, "repair", "Repair retry limit reached; user approval and revised plan required.")
        run["status"] = "waiting_approval"
        return
    if _stage_requires_approval(mode_def, "repair") and not approval:
        _record_decision(
            run,
            "repair_approval_required",
            "Repair attempt was paused because this mode requires approval.",
            stage_key="repair",
        )
        _queue_approval(run, "repair", "Repair attempt requires approval in this mode.")
        run["status"] = "waiting_approval"
        return
    run["status"] = "repairing"
    repair_attempt = dict(payload.get("repair_attempt") or payload)
    repair_attempt.setdefault("id", _new_id("repair"))
    repair_attempt.setdefault("timestamp", _now())
    repair_attempt.setdefault("root_cause", _repair_root_cause(repair_attempt, run))
    repair_attempt.setdefault("repeat_count", _repair_repeat_count(run, repair_attempt))
    repair_attempt.setdefault("rollback_recommended", _repair_rollback_recommended(run, repair_attempt))
    if int(repair_attempt.get("repeat_count", 0)) >= _REPAIR_REPEAT_ESCALATION_THRESHOLD and not repair_attempt.get("success"):
        run.setdefault("repair_history", []).append(repair_attempt)
        run["repair_attempts"] = int(run.get("repair_attempts", 0)) + 1
        _block_action(
            run,
            "repair",
            "Repeated repair pattern detected; Autopilot escalated before attempting another similar fix.",
            stage_key="repair",
            evidence={"root_cause": repair_attempt.get("root_cause"), "repeat_count": repair_attempt.get("repeat_count")},
        )
        _queue_approval(run, "repair", "Repeated repair pattern detected; user review or rollback is recommended.")
        run["status"] = "waiting_approval"
        return
    _step_execution_safe(
        root,
        run,
        "record_repair",
        stage_key="repair",
        payload={"repair_attempt": repair_attempt},
        approval=approval,
    )
    run.setdefault("repair_history", []).append(repair_attempt)
    run["repair_attempts"] = int(run.get("repair_attempts", 0)) + 1
    _record_decision(
        run,
        "repair_recorded",
        "Repair attempt was recorded with root-cause and rollback recommendation metadata.",
        stage_key="repair",
        evidence={
            "success": repair_attempt.get("success"),
            "root_cause": repair_attempt.get("root_cause"),
            "rollback_recommended": repair_attempt.get("rollback_recommended"),
        },
    )
    run["status"] = "running"


def _apply_checkpoint_action(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    approval: bool,
) -> None:
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    if _stage_requires_approval(mode_def, "checkpoint") and not approval:
        _record_decision(
            run,
            "checkpoint_approval_required",
            "Checkpoint creation was paused because approval is required before apply.",
            stage_key="checkpoint",
        )
        _queue_approval(run, "checkpoint", "Checkpoint creation requires approval before apply.")
        run["status"] = "waiting_approval"
        return
    raw_paths = payload.get("paths") or payload.get("target_files") or run.get("files_being_modified") or []
    paths = _dedupe_strings([raw_paths] if isinstance(raw_paths, str) else raw_paths)
    if not paths:
        _record_decision(
            run,
            "checkpoint_missing_paths",
            "Checkpoint creation was paused because no target paths were available.",
            stage_key="checkpoint",
        )
        _queue_approval(run, "checkpoint", "Checkpoint needs target paths before apply.")
        run["status"] = "waiting_approval"
        return
    if len(paths) > int(mode_def.autonomy_limits.get("max_files_modified", 0) or 0):
        _block_action(
            run,
            "checkpoint",
            "Checkpoint path count exceeds this Autopilot mode's file modification limit.",
            stage_key="checkpoint",
            evidence={"path_count": len(paths), "limit": mode_def.autonomy_limits.get("max_files_modified")},
        )
        _queue_approval(run, "checkpoint", "Checkpoint scope exceeds the mode file modification limit.")
        run["status"] = "waiting_approval"
        return
    result = _step_execution_safe(
        root,
        run,
        "advance",
        stage_key="checkpoint",
        payload={"paths": list(paths), **dict(payload)},
        approval=True,
    )
    run["checkpoint_status"] = "created"
    run["rollback_available"] = True
    checkpoint_id = _extract_checkpoint_id(result)
    if checkpoint_id:
        run["checkpoint_id"] = checkpoint_id
    _record_decision(
        run,
        "checkpoint_created",
        "Checkpoint was recorded before a potentially mutating apply stage.",
        stage_key="checkpoint",
        evidence={"checkpoint_id": checkpoint_id, "paths": list(paths)},
    )
    run["status"] = "running"


def _apply_rollback_action(root: Path, run: MutableMapping[str, Any], payload: Mapping[str, Any]) -> None:
    rollback = {
        "id": _new_id("rollback"),
        "timestamp": _now(),
        "checkpoint_id": payload.get("checkpoint_id") or run.get("checkpoint_id"),
        "summary": payload.get("summary") or "Rollback recorded for Autopilot run.",
    }
    run.setdefault("approval_history", []).append(
        {
            "id": _new_id("approval"),
            "timestamp": _now(),
            "stage_key": "rollback",
            "action": "rollback_recorded",
            "summary": rollback["summary"],
        }
    )
    run["rollback_count"] = int(run.get("rollback_count", 0)) + 1
    run["rollback_available"] = bool(payload.get("checkpoint_id") or run.get("checkpoint_id"))
    _record_decision(
        run,
        "rollback_recorded",
        "Rollback was recorded for recovery tracking and replay.",
        stage_key="rollback",
        evidence=rollback,
    )
    _step_execution_safe(root, run, "record_rollback", payload={"rollback": rollback})


def _apply_terminal_action(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    approval: bool,
    client_id: Optional[str],
) -> None:
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    max_terminal = int(mode_def.autonomy_limits.get("max_terminal_commands", 0) or 0)
    if len(run.get("terminal_jobs", []) or []) >= max_terminal:
        _block_action(
            run,
            "terminal",
            "Terminal command limit reached for this Autopilot mode.",
            stage_key="terminal",
            evidence={"terminal_jobs": len(run.get("terminal_jobs", []) or []), "limit": max_terminal},
        )
        _queue_approval(run, "terminal", "Terminal command limit reached; user review is required.")
        run["status"] = "waiting_approval"
        return
    if not approval:
        _record_decision(
            run,
            "terminal_approval_required",
            "Terminal/runtime command execution was paused because approval is required.",
            stage_key="terminal",
        )
        _queue_approval(run, "terminal", "Terminal/runtime command execution requires approval.")
        run["status"] = "waiting_approval"
        return
    command = str(payload.get("command") or "").strip()
    if not command:
        raise ValueError("terminal command is required")
    job_result = runtime_interaction.launch_terminal_job(
        root,
        command,
        workflow_id=run.get("workflow_id"),
        task_id=run.get("execution_id"),
        source_client=client_id or run.get("client_id"),
        approval=True,
        dry_run=bool(payload.get("dry_run", True)),
        timeout_seconds=int(payload.get("timeout_seconds", 120)),
        metadata={
            "autopilot_id": run["id"],
            "autopilot_mode": mode_def.id,
            **dict(payload.get("metadata") or {}),
        },
        wait=bool(payload.get("wait", False)),
    )
    run.setdefault("terminal_jobs", []).append(job_result.get("job") or job_result)
    _record_decision(
        run,
        "terminal_job_recorded",
        "Terminal/runtime command was routed through Core runtime safety and linked to this run.",
        stage_key="terminal",
        evidence={"dry_run": bool(payload.get("dry_run", True)), "job_id": (job_result.get("job") or job_result).get("id") if isinstance((job_result.get("job") or job_result), Mapping) else None},
    )
    run["status"] = "running"


def _apply_simulation_action(root: Path, run: MutableMapping[str, Any], payload: Mapping[str, Any]) -> None:
    simulation = _simulate_run(root, run, payload)
    run["last_simulation"] = simulation
    _record_decision(
        run,
        "simulation_recorded",
        "Autopilot generated a dry-run preview without mutating workspace state.",
        evidence={"risk_level": simulation.get("risk_level"), "blocked": simulation.get("blocked")},
    )
    if run.get("status") not in {"paused", "waiting_approval"}:
        run["status"] = "running"


def _complete_run(
    root: Path,
    run: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    summary: Optional[str],
) -> None:
    run["status"] = "completed"
    run["finished_at"] = _now()
    run["completion_summary"] = summary or payload.get("summary") or "Autopilot run completed."
    _record_decision(
        run,
        "workflow_completed",
        "Autopilot completed after recording its final summary and current trust scorecard.",
        stage_key="completion_summary",
        evidence={"summary": run["completion_summary"]},
    )
    _step_execution_safe(root, run, "complete_stage", stage_key="completion_summary", payload=dict(payload), approval=True)


def _step_execution_safe(
    root: Path,
    run: Mapping[str, Any],
    action: str,
    *,
    stage_key: Optional[str] = None,
    payload: Optional[Mapping[str, Any]] = None,
    approval: bool = False,
) -> Dict[str, Any]:
    execution_id = run.get("execution_id")
    if not execution_id:
        return {}
    try:
        return engineering_execution.step_execution(
            root,
            str(execution_id),
            action=action,
            stage_key=stage_key,
            payload=dict(payload or {}),
            approval=approval,
        )
    except Exception as exc:
        return {"error": str(exc)}


def _refresh_run(root: Path, autopilot_id: str) -> Dict[str, Any]:
    run = _load_run(root, autopilot_id)
    execution = _linked_execution(root, run)
    stage_key = _active_stage(execution)
    if execution:
        execution_status = execution.get("status")
        if execution_status in {"completed", "failed", "cancelled"}:
            run["status"] = str(execution_status)
            if not run.get("finished_at"):
                run["finished_at"] = _now()
        elif run.get("status") not in {"paused", "waiting_approval"}:
            if stage_key == "validation":
                run["status"] = "validating"
            elif stage_key == "repair":
                run["status"] = "repairing"
            else:
                run["status"] = "running"
        run["active_agent"] = _active_agent_for_stage(stage_key)
        run["current_task"] = _current_task(execution)
        run["workflow_id"] = execution.get("workflow_id") or run.get("workflow_id")
        run["files_being_modified"] = _files_being_modified(run, execution)
        run["validation_status"] = _validation_status(run, execution)
        run["rollback_available"] = bool(run.get("rollback_available") or run.get("checkpoint_id"))
        run["roadmap_progress"] = _roadmap_progress_from_execution(run, execution)
        run["execution_snapshot"] = {
            "id": execution.get("id"),
            "status": execution.get("status"),
            "active_stage": stage_key,
            "progress": execution.get("progress"),
            "updated_at": execution.get("updated_at"),
        }
    _update_reliability_state(root, run, execution)
    run["updated_at"] = _now()
    _save_run(root, run)
    return dict(run)


def _linked_execution(root: Path, run: Mapping[str, Any]) -> Dict[str, Any]:
    execution_id = run.get("execution_id")
    if not execution_id:
        return {}
    try:
        dashboard = engineering_execution.execution_dashboard(root, str(execution_id))
        return dict(dashboard.get("execution") or {})
    except Exception:
        return {}


def _active_stage_for_run(root: Path, run: Mapping[str, Any]) -> Optional[str]:
    return _active_stage(_linked_execution(root, run))


def _active_stage(execution: Mapping[str, Any]) -> Optional[str]:
    explicit = execution.get("active_stage_key")
    if explicit:
        return str(explicit)
    for stage in execution.get("stages", []) or []:
        if stage.get("status") in {"running", "waiting_input", "validating", "repairing", "queued"}:
            return stage.get("key")
    for stage in execution.get("stages", []) or []:
        if stage.get("status") == "pending":
            return stage.get("key")
    return None


def _active_agent_for_stage(stage_key: Optional[str]) -> Optional[str]:
    mapping = {
        "intake": "planner_agent",
        "workspace_analysis": "architecture_agent",
        "planning": "planner_agent",
        "task_decomposition": "planner_agent",
        "implementation": "coder_agent",
        "validation": "validator_agent",
        "repair": "repair_agent",
        "review": "architecture_agent",
        "approval": "planner_agent",
        "checkpoint": "coder_agent",
        "apply": "coder_agent",
        "completion_summary": "summarizer_agent",
        "terminal": "validator_agent",
    }
    return mapping.get(stage_key or "", "planner_agent")


def _stage_title(stage_key: Optional[str]) -> str:
    if not stage_key:
        return "No active task"
    return stage_key.replace("_", " ").title()


def _current_task(execution: Mapping[str, Any]) -> str:
    stage_key = _active_stage(execution)
    if not stage_key:
        return "Execution complete"
    for stage in execution.get("stages", []) or []:
        if stage.get("key") == stage_key:
            return str(stage.get("name") or _stage_title(stage_key))
    return _stage_title(stage_key)


def _stage_requires_approval(mode_def: AutopilotMode, stage_key: Optional[str]) -> bool:
    stage_key = stage_key or ""
    if mode_def.id == "approval_each_step":
        return True
    if stage_key in _MUTATING_STAGES:
        return True
    if stage_key in _REPAIR_STAGES:
        return mode_def.id not in {"repair_autopilot", "experimental_full_autopilot"}
    if stage_key in _VALIDATION_STAGES:
        return mode_def.id not in {"validation_autopilot", "repair_autopilot", "experimental_full_autopilot"}
    if stage_key == "terminal":
        return True
    if mode_def.id == "suggest_only" and stage_key in {"implementation", "validation", "repair", "checkpoint", "apply"}:
        return True
    return False


def _approval_reason(mode_def: AutopilotMode, stage_key: Optional[str]) -> str:
    stage_key = stage_key or "stage"
    if mode_def.id == "approval_each_step":
        return f"{mode_def.display_name} requires approval before {stage_key}."
    if stage_key in _MUTATING_STAGES:
        return f"{stage_key} can modify workspace state; checkpoint/approval gate is required."
    if stage_key == "validation":
        return "Validation command execution requires approval in this Autopilot mode."
    if stage_key == "repair":
        return "Repair attempt requires approval or a bounded repair plan."
    return f"Approval required before {stage_key}."


def _queue_approval(run: MutableMapping[str, Any], stage_key: str, reason: str) -> None:
    pending = [
        item for item in run.get("pending_approvals", []) if item.get("stage_key") != stage_key
    ]
    pending.append(
        {
            "id": _new_id("approval-request"),
            "stage_key": stage_key,
            "reason": reason,
            "requested_at": _now(),
            "required_action": "approve_or_reject",
            "risk_level": run.get("execution_risk_level", "unknown"),
        }
    )
    run["pending_approvals"] = pending
    run["approval_interruptions"] = int(run.get("approval_interruptions", 0)) + 1
    _record_decision(
        run,
        "approval_queued",
        reason,
        stage_key=stage_key,
        evidence={"risk_level": run.get("execution_risk_level", "unknown")},
    )


def _extract_validation_result(result: Mapping[str, Any], payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if payload.get("result"):
        raw = payload.get("result")
        if isinstance(raw, Mapping):
            return dict(raw)
    execution = result.get("execution") if isinstance(result, Mapping) else None
    if isinstance(execution, Mapping):
        validations = execution.get("validation_history") or []
        validations = validations or execution.get("validation_chain") or []
        if validations:
            raw = validations[-1]
            if isinstance(raw, Mapping):
                normalized = dict(raw)
                if "passed" not in normalized and "ok" in normalized:
                    normalized["passed"] = bool(normalized.get("ok"))
                return normalized
    if payload.get("passed") is not None:
        return {
            "id": _new_id("validation"),
            "timestamp": _now(),
            "passed": bool(payload.get("passed")),
            "summary": payload.get("summary"),
        }
    return None


def _extract_checkpoint_id(result: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(result, Mapping):
        return None
    execution = result.get("execution")
    if isinstance(execution, Mapping):
        checkpoints = execution.get("checkpoint_history") or execution.get("checkpoints") or []
        if checkpoints and isinstance(checkpoints[-1], Mapping):
            return checkpoints[-1].get("checkpoint_id") or checkpoints[-1].get("id")
    return result.get("checkpoint_id") if isinstance(result.get("checkpoint_id"), str) else None


def _update_reliability_state(
    root: Path,
    run: MutableMapping[str, Any],
    execution: Optional[Mapping[str, Any]] = None,
) -> None:
    execution = execution or _linked_execution(root, run)
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    profile = _profile_for_run(run)
    run["specialization"] = profile.id
    run["specialization_profile"] = profile.as_dict()
    run["execution_strategy"] = dict(profile.orchestration_strategy)
    run["validation_strategy"] = dict(profile.validation_strategy)
    run["repair_strategy"] = dict(profile.repair_strategy)
    run["model_routing"] = dict(profile.model_routing)
    run["memory_scope"] = dict(profile.memory_scope)
    run["specialization_benchmarks"] = list(profile.benchmark_suites)
    scorecard = _trust_scorecard(root, run, execution, mode_def)
    run["trust_scorecard"] = scorecard
    run["confidence_score"] = scorecard["confidence_score"]
    run["validation_confidence"] = scorecard["validation_confidence"]
    run["repair_confidence"] = scorecard["repair_confidence"]
    run["regression_risk"] = scorecard["regression_risk"]
    run["rollback_readiness"] = scorecard["rollback_readiness"]
    run["execution_risk_level"] = scorecard["execution_risk_level"]
    run["predictions"] = _workflow_predictions(run, execution, mode_def, scorecard)
    run["validation_intelligence"] = _validation_intelligence(root, run, execution, scorecard, profile)
    run["checkpoint_intelligence"] = _checkpoint_intelligence(run, execution, scorecard)
    run["bounded_autonomy"] = _bounded_autonomy_status(run, mode_def)
    run["explanations"] = _explanations(run, execution, scorecard)
    run["specialized_observability"] = _specialized_observability(run, execution, profile, scorecard)
    run["specialization_memory"] = _specialization_memory_snapshot(root, profile)
    _trim_run_state(run)


def _trust_scorecard(
    root: Path,
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    mode_def: AutopilotMode,
) -> Dict[str, Any]:
    files = _files_being_modified(run, execution)
    risk_level = _risk_level(files, mode_def)
    validations = _all_validations(run, execution)
    repairs = _all_repairs(run)
    pending_count = len(run.get("pending_approvals", []) or [])
    failed_validations = [item for item in validations if item.get("passed") is False]
    passed_validations = [item for item in validations if item.get("passed") is True]
    failed_repairs = [item for item in repairs if item.get("success") is False]
    successful_repairs = [item for item in repairs if item.get("success") is True]
    terminal_failures = [
        item
        for item in run.get("terminal_jobs", []) or []
        if isinstance(item, Mapping) and str(item.get("status") or "").lower() in {"failed", "blocked", "timed_out"}
    ]
    iteration_limit = int(mode_def.autonomy_limits.get("max_autonomous_iterations", 1) or 1)
    iteration_pressure = max(0, int(run.get("iterations", 0) or 0) - max(0, iteration_limit - 2))
    base_penalty = {"none": 0, "low": 4, "medium": 12, "high": 26}.get(risk_level, 10)
    confidence = 90 - base_penalty
    confidence -= pending_count * 4
    confidence -= len(failed_validations) * 12
    confidence -= len(failed_repairs) * 8
    confidence -= len(terminal_failures) * 10
    confidence -= min(18, iteration_pressure * 5)
    confidence += min(8, len(passed_validations) * 4)
    confidence += min(6, len(successful_repairs) * 3)

    if validations:
        latest_validation = validations[-1]
        validation_confidence = 92 if latest_validation.get("passed") is True else 28
        validation_confidence -= max(0, len(failed_validations) - len(passed_validations)) * 8
    elif mode_def.id in {"suggest_only"}:
        validation_confidence = 58
    else:
        validation_confidence = 42

    if failed_validations and not repairs:
        repair_confidence = 35
    elif repairs:
        last_repair = repairs[-1]
        repair_confidence = 82 if last_repair.get("success") is True else 38
        repair_confidence -= max(0, len(failed_repairs) - len(successful_repairs)) * 7
        repair_confidence -= max(0, int(last_repair.get("repeat_count", 0) or 0) - 1) * 12
    else:
        repair_confidence = 72

    regression_risk = base_penalty + len(files) * 2 + len(failed_validations) * 14 + len(failed_repairs) * 8
    if files and not (run.get("rollback_available") or run.get("checkpoint_id")):
        regression_risk += 12
    if terminal_failures:
        regression_risk += 10
    if _sensitive_path_count(files):
        regression_risk += _sensitive_path_count(files) * 10

    rollback_readiness = 100 if run.get("rollback_available") or run.get("checkpoint_id") else (90 if not files else 25)
    if run.get("checkpoint_status") == "created":
        rollback_readiness = max(rollback_readiness, 95)

    regression_risk = _clamp(regression_risk, 0, 100)
    execution_risk_level = _risk_level_from_score(regression_risk, risk_level)
    confidence = _clamp(confidence, 5, 100)
    validation_confidence = _clamp(validation_confidence, 0, 100)
    repair_confidence = _clamp(repair_confidence, 0, 100)
    rollback_readiness = _clamp(rollback_readiness, 0, 100)
    return {
        "confidence_score": confidence,
        "validation_confidence": validation_confidence,
        "repair_confidence": repair_confidence,
        "regression_risk": regression_risk,
        "rollback_readiness": rollback_readiness,
        "execution_risk_level": execution_risk_level,
        "scoring_inputs": {
            "mode": mode_def.id,
            "file_count": len(files),
            "pending_approval_count": pending_count,
            "validation_count": len(validations),
            "failed_validation_count": len(failed_validations),
            "repair_attempt_count": len(repairs),
            "failed_repair_count": len(failed_repairs),
            "terminal_failure_count": len(terminal_failures),
            "iteration_count": int(run.get("iterations", 0) or 0),
            "iteration_limit": iteration_limit,
            "sensitive_path_count": _sensitive_path_count(files),
        },
        "warnings": _trust_warnings(run, execution, files, validations, repairs),
        "generated_at": _now(),
    }


def _workflow_predictions(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    mode_def: AutopilotMode,
    scorecard: Mapping[str, Any],
) -> Dict[str, Any]:
    files = _files_being_modified(run, execution)
    stages_remaining = _remaining_stages(execution)
    estimated_minutes = max(2, len(stages_remaining) * 3 + len(files) * 2)
    if scorecard.get("execution_risk_level") == "high":
        estimated_minutes += 10
    validation_targets = _validation_targets(Path(str(run.get("workspace") or ".")), run, execution)
    likely_rollback_need = "high" if scorecard.get("regression_risk", 0) >= 70 else "medium" if scorecard.get("regression_risk", 0) >= 40 else "low"
    profile = _profile_for_run(run)
    return {
        "specialization": profile.id,
        "orchestration_strategy": profile.orchestration_strategy.get("name"),
        "validation_strategy": profile.validation_strategy.get("name"),
        "likely_duration_minutes": estimated_minutes,
        "likely_risk": scorecard.get("execution_risk_level"),
        "likely_validation_targets": validation_targets,
        "likely_rollback_need": likely_rollback_need,
        "likely_failure_hotspots": _likely_failure_hotspots(run, execution),
        "next_escalation": _next_escalation(run, mode_def, stages_remaining),
        "remaining_stage_count": len(stages_remaining),
    }


def _validation_intelligence(
    root: Path,
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    profile: AutopilotSpecialization,
) -> Dict[str, Any]:
    targets = _validation_targets(root, run, execution)
    risk = str(scorecard.get("execution_risk_level") or "low")
    latest = _all_validations(run, execution)[-1:] or []
    escalation = risk == "high" or (latest and latest[0].get("passed") is False)
    strategy = str(profile.validation_strategy.get("name") or ("risk_based" if risk in {"medium", "high"} else "incremental"))
    return {
        "strategy": strategy,
        "specialization": profile.id,
        "paths": list(profile.validation_strategy.get("paths", [])),
        "targets": targets,
        "coverage": _validation_coverage(run, execution, targets),
        "escalation_required": bool(escalation),
        "escalation_reason": str(profile.validation_strategy.get("escalation") or "High risk or failed validation requires broader checks.") if escalation else "",
        "recommended_order": _validation_order(targets, risk),
        "latest_result": latest[0] if latest else None,
    }


def _checkpoint_intelligence(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> Dict[str, Any]:
    files = _files_being_modified(run, execution)
    checkpoint_id = run.get("checkpoint_id")
    readiness = int(scorecard.get("rollback_readiness", 0) or 0)
    health = "ready" if readiness >= 85 else "not_ready" if files else "not_required"
    return {
        "milestone_checkpoint_recommended": bool(files),
        "risk_triggered_checkpoint_recommended": scorecard.get("execution_risk_level") in {"medium", "high"},
        "rollback_recommended": scorecard.get("regression_risk", 0) >= 70,
        "checkpoint_id": checkpoint_id,
        "checkpoint_health": health,
        "checkpoint_health_score": readiness,
        "comparison_available": bool(checkpoint_id and files),
        "reason": "Checkpoint required before mutating files." if files and not checkpoint_id else "Rollback path is available." if checkpoint_id else "No file modification scope is active.",
    }


def _specialized_observability(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    profile: AutopilotSpecialization,
    scorecard: Mapping[str, Any],
) -> Dict[str, Any]:
    files = _files_being_modified(run, execution)
    validations = _all_validations(run, execution)
    repairs = _all_repairs(run)
    metrics = {
        "file_scope_count": len(files),
        "validation_count": len(validations),
        "repair_attempt_count": len(repairs),
        "confidence_score": scorecard.get("confidence_score", 0),
        "regression_risk": scorecard.get("regression_risk", 0),
        "rollback_readiness": scorecard.get("rollback_readiness", 0),
    }
    if profile.id == "feature_autopilot":
        roadmap = run.get("roadmap_progress", {}) if isinstance(run.get("roadmap_progress"), Mapping) else {}
        metrics["roadmap_phase_count"] = roadmap.get("total", 0)
        metrics["roadmap_completed_count"] = roadmap.get("completed", 0)
    elif profile.id == "repair_autopilot":
        metrics["repeat_failure_count"] = len([item for item in repairs if int(item.get("repeat_count", 0) or 0) >= _REPAIR_REPEAT_ESCALATION_THRESHOLD])
        metrics["rollback_recommendation_count"] = len([item for item in repairs if item.get("rollback_recommended")])
    elif profile.id == "refactor_autopilot":
        metrics["impact_scope_count"] = len(_likely_failure_hotspots(run, execution))
        metrics["reference_sensitive_file_count"] = len([path for path in files if str(path).lower().endswith((".ts", ".tsx", ".py", ".cs", ".cpp", ".h", ".hpp"))])
    elif profile.id == "deployment_autopilot":
        metrics["release_sensitive_file_count"] = _sensitive_path_count(files)
        metrics["rollback_gate_ready"] = scorecard.get("rollback_readiness", 0) >= 85
    elif profile.id == "workspace_intelligence_autopilot":
        metrics["read_mostly"] = len(files) == 0
        metrics["summary_targets"] = len(run.get("predictions", {}).get("likely_validation_targets", []) if isinstance(run.get("predictions"), Mapping) else [])
    return {
        "specialization": profile.id,
        "strategy": dict(profile.observability),
        "metrics": metrics,
        "benchmark_suites": list(profile.benchmark_suites),
        "ui": dict(profile.ui),
    }


def _specialization_memory_snapshot(root: Path, profile: AutopilotSpecialization) -> Dict[str, Any]:
    memory = _load_autopilot_memory(root)
    per_specialization = memory.get("per_specialization", {}) if isinstance(memory.get("per_specialization"), Mapping) else {}
    profile_memory = per_specialization.get(profile.id, {}) if isinstance(per_specialization, Mapping) else {}
    return {
        "specialization": profile.id,
        "memory_scope": dict(profile.memory_scope),
        "successful_workflows": list(profile_memory.get("successful_workflows", []) if isinstance(profile_memory, Mapping) else [])[-10:],
        "repair_patterns": list(profile_memory.get("repair_patterns", []) if isinstance(profile_memory, Mapping) else [])[-10:],
        "architecture_conventions": list(profile_memory.get("architecture_conventions", []) if isinstance(profile_memory, Mapping) else [])[-10:],
        "deployment_history": list(profile_memory.get("deployment_history", []) if isinstance(profile_memory, Mapping) else [])[-10:],
        "recurring_validation_failures": list(profile_memory.get("recurring_validation_failures", []) if isinstance(profile_memory, Mapping) else [])[-10:],
    }


def _bounded_autonomy_status(run: Mapping[str, Any], mode_def: AutopilotMode) -> Dict[str, Any]:
    limits = dict(mode_def.autonomy_limits)
    file_count = len(run.get("files_being_modified", []) or [])
    terminal_count = len(run.get("terminal_jobs", []) or [])
    usage = {
        "iterations": int(run.get("iterations", 0) or 0),
        "repair_attempts": int(run.get("repair_attempts", 0) or 0),
        "files_modified_or_scoped": file_count,
        "terminal_commands": terminal_count,
        "payload_limit_chars": int(limits.get("max_action_payload_chars", _MAX_ACTION_PAYLOAD_CHARS)),
    }
    violations = []
    if usage["iterations"] > int(limits.get("max_autonomous_iterations", 1) or 1):
        violations.append("iteration_limit")
    if usage["repair_attempts"] > int(limits.get("max_repair_attempts", 0) or 0):
        violations.append("repair_limit")
    if file_count > int(limits.get("max_files_modified", 0) or 0):
        violations.append("file_limit")
    if terminal_count > int(limits.get("max_terminal_commands", 0) or 0):
        violations.append("terminal_limit")
    return {
        "mode": mode_def.id,
        "limits": limits,
        "usage": usage,
        "violations": violations,
        "allowed_to_continue": not violations and run.get("status") not in {"failed", "cancelled"},
        "blocked_actions": list(run.get("blocked_actions", []) or [])[-20:],
    }


def _explanations(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    stage = _active_stage(execution)
    explanations = [
        {
            "kind": "task_selection",
            "summary": f"Current task is {_stage_title(stage)} because it is the next unfinished Core execution stage.",
            "evidence": {"active_stage": stage, "workflow_id": run.get("workflow_id")},
        },
        {
            "kind": "risk",
            "summary": f"Execution risk is {scorecard.get('execution_risk_level')} with regression risk {scorecard.get('regression_risk')}.",
            "evidence": scorecard.get("scoring_inputs", {}),
        },
    ]
    if run.get("files_being_modified"):
        explanations.append(
            {
                "kind": "file_scope",
                "summary": "Files are in scope because they were requested by the client or linked execution plan.",
                "evidence": {"files": run.get("files_being_modified", [])},
            }
        )
    if run.get("pending_approvals"):
        explanations.append(
            {
                "kind": "pause_or_escalation",
                "summary": "Autopilot is waiting because at least one safety or approval gate is active.",
                "evidence": {"pending_approvals": run.get("pending_approvals", [])},
            }
        )
    latest_validation = (_all_validations(run, execution) or [None])[-1]
    if isinstance(latest_validation, Mapping) and latest_validation.get("passed") is False:
        explanations.append(
            {
                "kind": "validation_failure",
                "summary": "Validation failed, so repair is bounded and rollback may be recommended.",
                "evidence": latest_validation,
            }
        )
    return explanations


def _simulate_run(root: Path, run: Mapping[str, Any], payload: Mapping[str, Any]) -> Dict[str, Any]:
    execution = _linked_execution(root, run)
    mode_def = _mode_or_raise(str(run.get("mode") or "semi_autonomous"))
    scorecard = _trust_scorecard(root, run, execution, mode_def)
    stages = _remaining_stages(execution)
    validation_targets = _validation_targets(root, run, execution)
    files = _files_being_modified(run, execution)
    blocked = []
    if files and not (run.get("checkpoint_id") or run.get("rollback_available")):
        blocked.append("checkpoint_required_before_apply")
    if scorecard.get("regression_risk", 0) >= 70:
        blocked.append("high_regression_risk_requires_approval")
    if run.get("pending_approvals"):
        blocked.append("pending_approval_required")
    return {
        "id": _new_id("simulation"),
        "timestamp": _now(),
        "dry_run": True,
        "requested_action": payload.get("action") or "advance",
        "mode": mode_def.id,
        "remaining_stages": stages,
        "files_preview": files,
        "validation_targets": validation_targets,
        "risk_level": scorecard.get("execution_risk_level"),
        "confidence_score": scorecard.get("confidence_score"),
        "regression_risk": scorecard.get("regression_risk"),
        "rollback_readiness": scorecard.get("rollback_readiness"),
        "blocked": blocked,
        "recommended_next_actions": _simulation_recommendations(run, scorecard, blocked),
        "would_modify_files": False,
        "would_execute_commands": False,
    }


def _record_decision(
    run: MutableMapping[str, Any],
    kind: str,
    summary: str,
    *,
    stage_key: Optional[str] = None,
    evidence: Optional[Mapping[str, Any]] = None,
) -> None:
    entry = {
        "id": _new_id("decision"),
        "timestamp": _now(),
        "kind": kind,
        "stage_key": stage_key,
        "summary": summary,
        "evidence": _safe_payload(dict(evidence or {})),
    }
    decisions = list(run.get("decision_log", []) or [])
    decisions.append(entry)
    run["decision_log"] = decisions[-_TRUST_DECISION_LIMIT:]


def _block_action(
    run: MutableMapping[str, Any],
    action: str,
    reason: str,
    *,
    stage_key: Optional[str] = None,
    evidence: Optional[Mapping[str, Any]] = None,
) -> None:
    record = {
        "id": _new_id("blocked"),
        "timestamp": _now(),
        "action": action,
        "stage_key": stage_key,
        "reason": reason,
        "evidence": _safe_payload(dict(evidence or {})),
    }
    blocked = list(run.get("blocked_actions", []) or [])
    blocked.append(record)
    run["blocked_actions"] = blocked[-100:]
    _record_decision(run, "action_blocked", reason, stage_key=stage_key, evidence=record)


def _repair_root_cause(repair_attempt: Mapping[str, Any], run: Mapping[str, Any]) -> str:
    explicit = str(repair_attempt.get("root_cause") or repair_attempt.get("failed_step") or "").strip()
    if explicit:
        return explicit[:240]
    for validation in reversed(run.get("validation_chain", []) or []):
        if isinstance(validation, Mapping):
            for key in ("root_cause", "failed_step", "failed_step_command", "summary", "error"):
                value = str(validation.get(key) or "").strip()
                if value:
                    return value[:240]
    return "unknown_validation_failure"


def _repair_repeat_count(run: Mapping[str, Any], repair_attempt: Mapping[str, Any]) -> int:
    root_cause = _repair_root_cause(repair_attempt, run).lower()
    count = 1
    for previous in run.get("repair_history", []) or []:
        if not isinstance(previous, Mapping):
            continue
        if str(previous.get("root_cause") or "").strip().lower() == root_cause:
            count += 1
    return count


def _repair_rollback_recommended(run: Mapping[str, Any], repair_attempt: Mapping[str, Any]) -> bool:
    if repair_attempt.get("success") is True:
        return False
    if int(run.get("repair_attempts", 0) or 0) >= 1:
        return True
    if str(run.get("execution_risk_level") or "").lower() == "high":
        return True
    return bool(run.get("rollback_available") and run.get("validation_status") == "failed")


def _runtime_status(root: Path) -> Dict[str, Any]:
    try:
        summary = runtime_interaction.compact_summary(root)
    except Exception as exc:
        summary = {"status": "unknown", "error": str(exc)}
    agents = agent_runtime.agent_runtime_catalog(root)
    return {
        "runtime_interaction": summary,
        "agents": agents.get("agents", []),
        "agent_count": len(agents.get("agents", [])),
    }


def _collaboration_context(root: Path, metadata: Mapping[str, Any]) -> Dict[str, Any]:
    if not metadata.get("collaboration") and not metadata.get("collaboration_workflow_id"):
        return {
            "enabled": False,
            "requires_approval": False,
            "workflow_id": "",
            "required_roles": [],
            "approval_chain": [],
        }
    try:
        from . import collaboration_runtime

        return collaboration_runtime.autopilot_context(root, metadata)
    except Exception as exc:  # pragma: no cover - defensive cross-runtime integration
        return {
            "enabled": False,
            "requires_approval": False,
            "workflow_id": "",
            "required_roles": [],
            "approval_chain": [],
            "error": str(exc),
        }


def _governance_context(root: Path, metadata: Mapping[str, Any], *, approval: bool = False) -> Dict[str, Any]:
    try:
        from . import governance_runtime

        context = governance_runtime.autopilot_policy_context(root, {**dict(metadata), "policy_approval": approval})
        return context
    except Exception as exc:  # pragma: no cover - defensive cross-runtime integration
        return {
            "enabled": False,
            "status": "unavailable",
            "requires_approval": False,
            "blocked": False,
            "approval_requirements": [],
            "violations": [],
            "explanation": f"Governance policy runtime unavailable: {exc}",
        }


def _deep_engineering_intelligence_context(
    root: Path,
    *,
    workflow_type: str,
    objective: str,
    target_files: Iterable[str],
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    try:
        from . import engineering_intelligence

        latest_validation = metadata.get("latest_validation")
        data = engineering_intelligence.engineering_intelligence(
            root,
            workflow_type=workflow_type,
            objective=objective,
            target_files=list(target_files),
            focus=str(metadata.get("focus") or ""),
            token_budget=int(metadata.get("token_budget") or 24000),
            latest_validation=latest_validation if isinstance(latest_validation, Mapping) else {},
            refresh=bool(metadata.get("refresh_intelligence", False)),
            persist=True,
        )
        return {
            "enabled": True,
            "status": "ready",
            "generated_at": data.get("generated_at"),
            "architecture_reasoning": data.get("architecture_reasoning", {}),
            "context_assembly": data.get("context_assembly", {}),
            "validation_intelligence": data.get("validation_intelligence", {}),
            "repair_intelligence": data.get("repair_intelligence", {}),
            "roadmap_intelligence": data.get("roadmap_intelligence", {}),
            "workflow_prediction": data.get("workflow_prediction", {}),
            "knowledge_graph_intelligence": data.get("knowledge_graph_intelligence", {}),
            "memory_intelligence": data.get("memory_intelligence", {}),
            "benchmarks": data.get("benchmarks", {}),
            "explainability": data.get("explainability", {}),
        }
    except Exception as exc:  # pragma: no cover - defensive cross-runtime integration
        return {
            "enabled": False,
            "status": "unavailable",
            "generated_at": _now(),
            "error": f"Engineering intelligence unavailable: {exc}",
            "architecture_reasoning": {},
            "context_assembly": {},
            "validation_intelligence": {},
            "repair_intelligence": {},
            "roadmap_intelligence": {},
            "workflow_prediction": {},
            "knowledge_graph_intelligence": {},
            "memory_intelligence": {},
            "benchmarks": {},
            "explainability": {"decisions": [], "warnings": [f"Engineering intelligence unavailable: {exc}"]},
        }


def _governance_action_context(
    root: Path,
    run: Mapping[str, Any],
    action: str,
    payload: Mapping[str, Any],
    *,
    approval: bool,
    client_id: Optional[str],
) -> Dict[str, Any]:
    try:
        from . import governance_runtime

        action_type = _policy_action_type(action, payload)
        latest_validation = _latest_validation_record(run)
        evaluation = governance_runtime.evaluate_policy(
            root,
            action_type=action_type,
            workflow_type=str(run.get("workflow_type") or ""),
            target=str(payload.get("target") or run.get("objective") or action),
            actor_id=str(payload.get("actor_id") or client_id or run.get("client_id") or "autopilot"),
            actor_role=str(payload.get("actor_role") or "maintainer"),
            context={
                "command": payload.get("command") or payload.get("command_text") or [],
                "shell": payload.get("shell", False),
                "paths": payload.get("paths") or payload.get("target_files") or run.get("target_files", []),
                "target_files": run.get("target_files", []),
                "workflow_type": run.get("workflow_type", ""),
                "risk_level": run.get("execution_risk_level", ""),
                "validation_passed": bool(latest_validation.get("passed")),
                "validation_id": latest_validation.get("id", ""),
                "checkpoint_id": payload.get("checkpoint_id") or run.get("checkpoint_id") or "",
                "target_environment": payload.get("target_environment", ""),
                "production_confirmed": payload.get("production_confirmed", False),
                "privacy_sensitive": payload.get("privacy_sensitive", False),
                "allow_cloud": payload.get("allow_cloud", False),
            },
            approval=approval,
            dry_run=True,
        )
        return {
            "enabled": True,
            "evaluation": evaluation,
            "status": evaluation.get("status", "allowed"),
            "requires_approval": evaluation.get("status") in {"blocked", "needs_approval"},
            "blocked": evaluation.get("status") == "blocked",
            "approval_requirements": evaluation.get("approval_requirements", []),
            "violations": evaluation.get("violations", []),
            "explanation": evaluation.get("explanation", ""),
        }
    except Exception as exc:  # pragma: no cover - defensive cross-runtime integration
        return {
            "enabled": False,
            "status": "unavailable",
            "requires_approval": False,
            "blocked": False,
            "approval_requirements": [],
            "violations": [],
            "explanation": f"Governance policy runtime unavailable: {exc}",
        }


def _policy_action_type(action: str, payload: Mapping[str, Any]) -> str:
    if action in _TERMINAL_ACTIONS or payload.get("command") or payload.get("command_text"):
        return "command"
    if action in {"complete", "finish"}:
        return "workflow_complete"
    if action in {"checkpoint", "create_checkpoint"}:
        return "apply_changes"
    if action in {"rollback", "record_rollback"}:
        return "deployment"
    if action in {"run_validation", "record_validation"}:
        return "validation_result"
    return action


def _policy_pauses_action(action: str, context: Mapping[str, Any], approval: bool) -> bool:
    if action in {"approve", "reject", "pause", "cancel", "replay", "record_validation"} or action in _SIMULATION_ACTIONS:
        return False
    if approval:
        return False
    return bool(context.get("requires_approval"))


def _latest_validation_record(run: Mapping[str, Any]) -> Mapping[str, Any]:
    chain = [item for item in run.get("validation_chain", []) if isinstance(item, Mapping)]
    return chain[-1] if chain else {}


def _safety_summary(mode_def: AutopilotMode) -> Dict[str, Any]:
    return {
        "checkpoint_before_apply": True,
        "rollback_required": True,
        "workspace_restrictions": True,
        "dangerous_command_approval": True,
        "file_modification_limit": mode_def.autonomy_limits.get("max_files_modified"),
        "validation_before_completion": True,
        "repair_retry_limit": mode_def.autonomy_limits.get("max_repair_attempts"),
        "approval_rules": list(mode_def.approval_rules),
    }


def _safety_visibility(run: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not run:
        return {
            "changes_applied": False,
            "changes_only_proposed": True,
            "checkpoint_status": "none",
            "rollback_available": False,
            "restricted_path_warnings": [],
            "validation_failures": [],
            "fallback_runtime_mode": False,
        }
    validation_failures = [
        item for item in run.get("validation_chain", []) if isinstance(item, Mapping) and item.get("passed") is False
    ]
    return {
        "changes_applied": bool(run.get("applied_at")),
        "changes_only_proposed": not bool(run.get("applied_at")),
        "checkpoint_status": run.get("checkpoint_status", "not_started"),
        "rollback_available": bool(run.get("rollback_available")),
        "restricted_path_warnings": run.get("restricted_path_warnings", []),
        "validation_failures": validation_failures,
        "fallback_runtime_mode": False,
    }


def _files_being_modified(run: Mapping[str, Any], execution: Mapping[str, Any]) -> List[str]:
    files = list(run.get("target_files") or [])
    files.extend(execution.get("target_files") or [])
    plan = execution.get("execution_plan") or {}
    if isinstance(plan, Mapping):
        files.extend(plan.get("target_files") or [])
    return _dedupe_strings(str(item) for item in files if item)


def _validation_status(run: Mapping[str, Any], execution: Mapping[str, Any]) -> str:
    chain = run.get("validation_chain") or []
    if chain:
        latest = chain[-1]
        if isinstance(latest, Mapping):
            return "passed" if _validation_passed(latest) else "failed"
    validation_history = execution.get("validation_history") or execution.get("validation_chain") or []
    if validation_history:
        latest = validation_history[-1]
        if isinstance(latest, Mapping):
            return "passed" if _validation_passed(latest) else "failed"
    return str(run.get("validation_status") or "not_started")


def _validation_passed(validation: Mapping[str, Any]) -> bool:
    if "passed" in validation:
        return bool(validation.get("passed"))
    if "ok" in validation:
        return bool(validation.get("ok"))
    return False


def _all_validations(run: Mapping[str, Any], execution: Mapping[str, Any]) -> List[Dict[str, Any]]:
    validations: List[Dict[str, Any]] = []
    for chain in (run.get("validation_chain"), execution.get("validation_chain"), execution.get("validation_history")):
        if isinstance(chain, list):
            validations.extend(dict(item) for item in chain if isinstance(item, Mapping))
    return validations


def _all_repairs(run: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(item) for item in run.get("repair_history", []) or [] if isinstance(item, Mapping)]


def _latest_validation_ok(run: Mapping[str, Any], execution: Mapping[str, Any]) -> bool:
    for chain in (run.get("validation_chain"), execution.get("validation_chain"), execution.get("validation_history")):
        if isinstance(chain, list) and chain:
            latest = chain[-1]
            if isinstance(latest, Mapping):
                return _validation_passed(latest)
    return False


def _validation_targets(root: Path, run: Mapping[str, Any], execution: Mapping[str, Any]) -> List[Dict[str, Any]]:
    files = _files_being_modified(run, execution)
    plan = execution.get("execution_plan") if isinstance(execution.get("execution_plan"), Mapping) else {}
    requirements = plan.get("validation_requirements", {}) if isinstance(plan, Mapping) else {}
    commands = []
    if isinstance(requirements, Mapping):
        raw_commands = requirements.get("commands") or requirements.get("detected_commands") or []
        if isinstance(raw_commands, list):
            commands.extend(raw_commands[:6])
    if not commands:
        commands.extend(run.get("metadata", {}).get("validation_commands", []) if isinstance(run.get("metadata"), Mapping) else [])
    targets: List[Dict[str, Any]] = []
    if files:
        for path in files[:12]:
            lowered = path.lower()
            if lowered.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".cs", ".cpp", ".h", ".hpp")):
                targets.append(
                    {
                        "kind": "file",
                        "path": path,
                        "reason": "File is in the Autopilot modification scope.",
                        "priority": "high" if _sensitive_path_count([path]) else "normal",
                    }
                )
    if not targets and commands:
        targets.append(
            {
                "kind": "command",
                "command": commands[0],
                "reason": "Detected validation command is the safest initial check.",
                "priority": "normal",
            }
        )
    if not targets:
        targets.append(
            {
                "kind": "workspace",
                "path": str(root),
                "reason": "No file-specific scope is available; use workspace-level validation.",
                "priority": "normal",
            }
        )
    return targets[:12]


def _remaining_stages(execution: Mapping[str, Any]) -> List[Dict[str, Any]]:
    stages = []
    for stage in execution.get("stages", []) or []:
        if not isinstance(stage, Mapping):
            continue
        if stage.get("status") not in {"completed", "skipped"}:
            stages.append(
                {
                    "key": stage.get("key"),
                    "label": stage.get("label") or stage.get("name") or _stage_title(stage.get("key")),
                    "status": stage.get("status"),
                }
            )
    return stages


def _validation_coverage(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    targets: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    validations = _all_validations(run, execution)
    if not validations:
        return {"status": "not_started", "covered_targets": 0, "target_count": len(targets), "coverage_ratio": 0.0}
    latest = validations[-1]
    if latest.get("passed") is True:
        ratio = 1.0 if targets else 0.0
        status = "passed"
    else:
        ratio = 0.35 if targets else 0.0
        status = "failed"
    return {
        "status": status,
        "covered_targets": int(round(len(targets) * ratio)),
        "target_count": len(targets),
        "coverage_ratio": ratio,
    }


def _validation_order(targets: List[Mapping[str, Any]], risk: str) -> List[Dict[str, Any]]:
    ordered = sorted(
        [dict(item) for item in targets],
        key=lambda item: 0 if item.get("priority") == "high" else 1,
    )
    if risk == "high":
        ordered.append(
            {
                "kind": "workspace",
                "reason": "High-risk scope should receive a broad regression check after targeted validation.",
                "priority": "high",
            }
        )
    return ordered[:16]


def _roadmap_progress(roadmap: Iterable[Mapping[str, Any]], execution: Mapping[str, Any]) -> Dict[str, Any]:
    items = [dict(item) for item in roadmap]
    if not items:
        metadata = execution.get("metadata") if isinstance(execution.get("metadata"), Mapping) else {}
        items = list(metadata.get("roadmap") or []) if isinstance(metadata, Mapping) else []
    normalized = []
    for index, item in enumerate(items):
        normalized.append(
            {
                "id": item.get("id") or f"phase-{index + 1}",
                "title": item.get("title") or item.get("summary") or f"Roadmap phase {index + 1}",
                "status": item.get("status") or "pending",
                "checkpoint_id": item.get("checkpoint_id"),
                "validation_status": item.get("validation_status") or "not_started",
            }
        )
    return {
        "items": normalized,
        "completed": len([item for item in normalized if item.get("status") == "completed"]),
        "total": len(normalized),
    }


def _roadmap_progress_from_execution(run: Mapping[str, Any], execution: Mapping[str, Any]) -> Dict[str, Any]:
    progress = run.get("roadmap_progress")
    if isinstance(progress, Mapping) and progress.get("items"):
        items = [dict(item) for item in progress.get("items", [])]
        if execution.get("status") == "completed" and items:
            items[0]["status"] = "completed"
            if run.get("checkpoint_id"):
                items[0]["checkpoint_id"] = run.get("checkpoint_id")
        return {
            "items": items,
            "completed": len([item for item in items if item.get("status") == "completed"]),
            "total": len(items),
        }
    return _roadmap_progress([], execution)


def _risk_level(target_files: List[str], mode_def: AutopilotMode) -> str:
    if mode_def.id in {"experimental_full_autopilot", "roadmap_autopilot"}:
        base = "medium"
    else:
        base = "low"
    high_risk_fragments = [
        ".github/",
        "dockerfile",
        "docker-compose",
        "kubernetes",
        "secrets",
        ".env",
        "package-lock.json",
        "pnpm-lock.yaml",
        "requirements.txt",
        "csproj",
        "sln",
    ]
    lowered = [item.replace("\\", "/").lower() for item in target_files]
    if any(fragment in path for path in lowered for fragment in high_risk_fragments):
        return "high"
    if len(target_files) > 10:
        return "medium" if base == "low" else "high"
    return base


def _risk_level_from_score(score: Any, fallback: str = "low") -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return fallback
    if value >= 70:
        return "high"
    if value >= 40:
        return "medium"
    if value <= 5 and fallback == "none":
        return "none"
    return "low"


def _sensitive_path_count(paths: Iterable[Any]) -> int:
    fragments = [
        ".github/",
        ".env",
        "secrets",
        "dockerfile",
        "docker-compose",
        "kubernetes",
        "package-lock.json",
        "pnpm-lock.yaml",
        "requirements.txt",
        ".csproj",
        ".sln",
    ]
    count = 0
    for path in paths:
        lowered = str(path).replace("\\", "/").lower()
        if any(fragment in lowered for fragment in fragments):
            count += 1
    return count


def _trust_warnings(
    run: Mapping[str, Any],
    execution: Mapping[str, Any],
    files: List[str],
    validations: List[Mapping[str, Any]],
    repairs: List[Mapping[str, Any]],
) -> List[str]:
    warnings: List[str] = []
    if files and not (run.get("rollback_available") or run.get("checkpoint_id")):
        warnings.append("Rollback is not ready for the current file scope.")
    if not validations and run.get("mode") not in {"suggest_only"}:
        warnings.append("No validation result has been recorded for this run.")
    if validations and validations[-1].get("passed") is False:
        warnings.append("Latest validation failed; completion should remain blocked.")
    if repairs and repairs[-1].get("repeat_count", 0):
        repeat = int(repairs[-1].get("repeat_count", 0) or 0)
        if repeat >= _REPAIR_REPEAT_ESCALATION_THRESHOLD:
            warnings.append("Repeated repair pattern detected.")
    if _sensitive_path_count(files):
        warnings.append("Sensitive or high-impact files are in scope.")
    if run.get("pending_approvals"):
        warnings.append("Pending approvals are blocking autonomous progress.")
    if not execution:
        warnings.append("Linked engineering execution could not be refreshed.")
    return warnings


def _likely_failure_hotspots(run: Mapping[str, Any], execution: Mapping[str, Any]) -> List[Dict[str, Any]]:
    hotspots: List[Dict[str, Any]] = []
    files = _files_being_modified(run, execution)
    if _sensitive_path_count(files):
        hotspots.append({"area": "configuration_or_infrastructure", "reason": "High-impact config files are in scope."})
    if any(str(path).lower().endswith((".cpp", ".h", ".hpp", ".cs")) for path in files):
        hotspots.append({"area": "compiled_language_build", "reason": "Compiled project changes often require build validation."})
    if run.get("validation_status") == "failed":
        hotspots.append({"area": "validation", "reason": "Latest validation failed."})
    if run.get("repair_attempts", 0):
        hotspots.append({"area": "repair_loop", "reason": "Repair attempts have already been needed."})
    return hotspots[:8]


def _next_escalation(run: Mapping[str, Any], mode_def: AutopilotMode, stages: List[Mapping[str, Any]]) -> Dict[str, Any]:
    if run.get("pending_approvals"):
        approval = run.get("pending_approvals", [])[0]
        return {"stage_key": approval.get("stage_key"), "reason": approval.get("reason"), "already_waiting": True}
    for stage in stages:
        key = str(stage.get("key") or "")
        if _stage_requires_approval(mode_def, key):
            return {"stage_key": key, "reason": _approval_reason(mode_def, key), "already_waiting": False}
    return {"stage_key": None, "reason": "No immediate escalation predicted.", "already_waiting": False}


def _simulation_recommendations(
    run: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    blocked: List[str],
) -> List[str]:
    recommendations: List[str] = []
    if "checkpoint_required_before_apply" in blocked:
        recommendations.append("Create a checkpoint before approving any apply or repair changes.")
    if "high_regression_risk_requires_approval" in blocked:
        recommendations.append("Run targeted validation first and keep rollback controls visible.")
    if run.get("validation_status") == "failed":
        recommendations.append("Review root cause before another repair attempt.")
    if scorecard.get("confidence_score", 0) < 55:
        recommendations.append("Pause for user review before continuing autonomous execution.")
    if not recommendations:
        recommendations.append("Proceed to the next supervised stage with existing approval gates.")
    return recommendations


def _confidence_distribution(scores: List[float]) -> Dict[str, int]:
    buckets = {"low": 0, "medium": 0, "high": 0}
    for score in scores:
        if score < 50:
            buckets["low"] += 1
        elif score < 75:
            buckets["medium"] += 1
        else:
            buckets["high"] += 1
    return buckets


def _unstable_workflows(runs: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, Dict[str, int]] = {}
    for run in runs:
        key = str(run.get("workflow_type") or "unknown")
        bucket = counts.setdefault(key, {"runs": 0, "failed_or_blocked": 0})
        bucket["runs"] += 1
        if run.get("status") == "failed" or run.get("blocked_actions"):
            bucket["failed_or_blocked"] += 1
    unstable = []
    for key, bucket in counts.items():
        if bucket["runs"] and bucket["failed_or_blocked"] / bucket["runs"] >= 0.5:
            unstable.append({"workflow_type": key, **bucket})
    return unstable[:10]


def _recurring_repair_failures(runs: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for run in runs:
        for repair in run.get("repair_history", []) or []:
            if isinstance(repair, Mapping) and repair.get("success") is False:
                key = str(repair.get("root_cause") or repair.get("summary") or "unknown")[:120]
                counts[key] = counts.get(key, 0) + 1
    return [
        {"root_cause": key, "failure_count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if count > 1
    ][:10]


def _risky_execution_paths(runs: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for run in runs:
        if run.get("execution_risk_level") not in {"medium", "high"}:
            continue
        for path in run.get("files_being_modified", []) or []:
            key = str(path)
            counts[key] = counts.get(key, 0) + 1
    return [
        {"path": key, "risk_count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ][:20]


def _specialization_benchmark_map(runs: List[Mapping[str, Any]]) -> Dict[str, List[str]]:
    benchmarks: Dict[str, List[str]] = {}
    for run in runs:
        key = str(run.get("specialization") or "unknown")
        suites = [str(item) for item in run.get("specialization_benchmarks", []) or [] if str(item).strip()]
        if not suites and key in AUTOPILOT_SPECIALIZATIONS:
            suites = list(AUTOPILOT_SPECIALIZATIONS[key].benchmark_suites)
        if suites:
            existing = benchmarks.setdefault(key, [])
            for suite in suites:
                if suite not in existing:
                    existing.append(suite)
    return benchmarks


def _failure_hotspots(runs: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for run in runs:
        if run.get("status") != "failed":
            continue
        key = run.get("current_task") or run.get("workflow_type") or "unknown"
        counts[str(key)] = counts.get(str(key), 0) + 1
    return [
        {"area": key, "failures": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _distribution(values: Iterable[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _collect_pending_approvals(runs: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    pending: List[Dict[str, Any]] = []
    for run in runs:
        for item in run.get("pending_approvals", []) or []:
            if isinstance(item, Mapping):
                merged = dict(item)
                merged["autopilot_id"] = run.get("id")
                merged["workflow_id"] = run.get("workflow_id")
                pending.append(merged)
    return pending


def _mode_or_raise(mode: str) -> AutopilotMode:
    key = (mode or "semi_autonomous").strip()
    if key not in AUTOPILOT_MODES:
        raise ValueError(f"unsupported Autopilot mode: {mode}")
    return AUTOPILOT_MODES[key]


def _workflow_type_or_raise(workflow_type: str, mode_def: AutopilotMode) -> str:
    key = (workflow_type or "generate_feature").strip()
    if key not in mode_def.allowed_workflow_types:
        raise ValueError(f"workflow type {key!r} is not allowed in {mode_def.id} mode")
    return key


def _workflow_type_or_raise_for_specialization(workflow_type: str, profile: AutopilotSpecialization) -> str:
    key = (workflow_type or "").strip()
    if key not in profile.workflow_types:
        raise ValueError(f"workflow type {key!r} is not supported by {profile.id}")
    return key


def _specialization_or_raise(specialization: str) -> AutopilotSpecialization:
    key = (specialization or "").strip()
    aliases = {
        "feature": "feature_autopilot",
        "repair": "repair_autopilot",
        "refactor": "refactor_autopilot",
        "deployment": "deployment_autopilot",
        "workspace": "workspace_intelligence_autopilot",
        "workspace_intelligence": "workspace_intelligence_autopilot",
        "intelligence": "workspace_intelligence_autopilot",
    }
    key = aliases.get(key, key)
    if key not in AUTOPILOT_SPECIALIZATIONS:
        raise ValueError(f"unsupported Autopilot specialization: {specialization}")
    return AUTOPILOT_SPECIALIZATIONS[key]


def _specialization_or_infer(
    specialization: Optional[str],
    *,
    mode: str,
    workflow_type: str,
    objective: str,
    target_files: List[str],
    roadmap: Iterable[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> AutopilotSpecialization:
    if specialization:
        return _specialization_or_raise(specialization)
    metadata_specialization = str(metadata.get("specialization") or metadata.get("autopilot_specialization") or "").strip()
    if metadata_specialization:
        return _specialization_or_raise(metadata_specialization)
    return AUTOPILOT_SPECIALIZATIONS[
        _infer_specialization_id(
            mode=mode,
            workflow_type=workflow_type,
            objective=objective,
            target_files=target_files,
            roadmap=roadmap,
        )
    ]


def _infer_specialization_id(
    *,
    mode: str,
    workflow_type: str,
    objective: str,
    target_files: List[str],
    roadmap: Iterable[Mapping[str, Any]],
) -> str:
    text = f"{mode} {workflow_type} {objective}".lower()
    files = " ".join(path.replace("\\", "/").lower() for path in target_files)
    repair_terms = ("repair", "fix build", "failing", "failure", "broken")
    if workflow_type == "repair_project" or mode == "repair_autopilot":
        return "repair_autopilot"
    if workflow_type in {"validate_project", "build_project"} and any(term in text for term in repair_terms):
        return "repair_autopilot"
    if any(term in text for term in ("deploy", "release", "ci", "pipeline", "staging", "production")) or any(
        fragment in files for fragment in (".github/", "dockerfile", "docker-compose", "kubernetes", "jenkins", "azure-pipelines", ".gitlab-ci")
    ):
        return "deployment_autopilot"
    if any(term in text for term in ("refactor", "rename", "move", "extract", "restructure", "architecture cleanup")):
        return "refactor_autopilot"
    if workflow_type in {"scan_workspace", "research_task", "chat_request"} or any(
        term in text for term in ("architecture summary", "roadmap", "technical debt", "dependency analysis", "onboarding docs")
    ):
        return "workspace_intelligence_autopilot" if workflow_type in {"scan_workspace", "research_task", "chat_request"} else "feature_autopilot"
    if roadmap or workflow_type == "continue_roadmap":
        return "feature_autopilot"
    return "feature_autopilot"


def _profile_file_limit(profile: AutopilotSpecialization) -> int:
    return {
        "feature_autopilot": 25,
        "repair_autopilot": 12,
        "refactor_autopilot": 15,
        "deployment_autopilot": 10,
        "workspace_intelligence_autopilot": 4,
    }.get(profile.id, 20)


def _profile_for_run(run: Mapping[str, Any]) -> AutopilotSpecialization:
    key = str(run.get("specialization") or "")
    if key in AUTOPILOT_SPECIALIZATIONS:
        return AUTOPILOT_SPECIALIZATIONS[key]
    return _specialization_or_infer(
        None,
        mode=str(run.get("mode") or "semi_autonomous"),
        workflow_type=str(run.get("workflow_type") or "generate_feature"),
        objective=str(run.get("objective") or ""),
        target_files=[str(item) for item in run.get("target_files", []) or []],
        roadmap=(run.get("roadmap_progress", {}) or {}).get("items", []) if isinstance(run.get("roadmap_progress"), Mapping) else [],
        metadata=run.get("metadata", {}) if isinstance(run.get("metadata"), Mapping) else {},
    )


def _memory(root: Path) -> ProjectMemory:
    return ProjectMemory(root)


def _load_runs(root: Path) -> List[Dict[str, Any]]:
    raw = _read_json(root, AUTOPILOT_RUNS_FILE, [])
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _write_runs(root: Path, runs: List[Mapping[str, Any]]) -> None:
    _memory(root).write_json(AUTOPILOT_RUNS_FILE, [dict(run) for run in runs])


def _load_run(root: Path, autopilot_id: str) -> Dict[str, Any]:
    for run in _load_runs(root):
        if run.get("id") == autopilot_id:
            return dict(run)
    raise ValueError(f"unknown Autopilot run: {autopilot_id}")


def _save_run(root: Path, run: Mapping[str, Any]) -> None:
    runs = _load_runs(root)
    saved = False
    for index, existing in enumerate(runs):
        if existing.get("id") == run.get("id"):
            runs[index] = dict(run)
            saved = True
            break
    if not saved:
        runs.append(dict(run))
    _write_runs(root, runs)


def _load_events(root: Path) -> List[Dict[str, Any]]:
    raw = _read_json(root, AUTOPILOT_EVENTS_FILE, [])
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _write_events(root: Path, events: List[Mapping[str, Any]]) -> None:
    _memory(root).write_json(AUTOPILOT_EVENTS_FILE, [dict(item) for item in events])


def _append_event(root: Path, run: Mapping[str, Any], event_type: str, data: Mapping[str, Any]) -> None:
    event = {
        "id": _new_id("autopilot-event"),
        "type": event_type,
        "timestamp": _now(),
        "autopilot_id": run.get("id"),
        "workflow_id": run.get("workflow_id"),
        "execution_id": run.get("execution_id"),
        "mode": run.get("mode"),
        "status": run.get("status"),
        "data": dict(data),
    }
    events = _load_events(root)
    events.append(event)
    _write_events(root, events[-1000:])
    _append_audit(root, event)


def _latest_event(root: Path, autopilot_id: str) -> Optional[Dict[str, Any]]:
    events = [event for event in _load_events(root) if event.get("autopilot_id") == autopilot_id]
    return events[-1] if events else None


def _recent_events(root: Path, *, autopilot_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    events = _load_events(root)
    if autopilot_id:
        events = [event for event in events if event.get("autopilot_id") == autopilot_id]
    return events[-max(1, int(limit)) :]


def _append_audit(root: Path, event: Mapping[str, Any]) -> None:
    memory = _memory(root)
    path = memory.root / AUTOPILOT_AUDIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"- {event.get('timestamp')} `{event.get('type')}` "
        f"run={event.get('autopilot_id')} workflow={event.get('workflow_id')} "
        f"status={event.get('status')}\n"
    )
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Autopilot Audit\n\n"
    path.write_text(existing + line, encoding="utf-8")


def _load_autopilot_memory(root: Path) -> Dict[str, Any]:
    raw = _read_json(
        root,
        AUTOPILOT_MEMORY_FILE,
        {
            "completed_roadmap_phases": [],
            "prior_failures": [],
            "repair_outcomes": [],
            "preferred_execution_strategies": [],
            "validation_history": [],
            "workflow_outcomes": [],
            "per_specialization": {},
            "updated_at": None,
        },
    )
    return dict(raw) if isinstance(raw, Mapping) else {}


def _write_autopilot_memory(root: Path, memory: Mapping[str, Any]) -> None:
    _memory(root).write_json(AUTOPILOT_MEMORY_FILE, dict(memory))


def _read_json(root: Path, name: str, default: Any) -> Any:
    memory = _memory(root)
    memory.ensure()
    path = memory.root / name
    try:
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _memory_record_seen(records: Iterable[Any], candidate: Mapping[str, Any]) -> bool:
    candidate_key = (
        candidate.get("id"),
        candidate.get("timestamp"),
        candidate.get("summary"),
        candidate.get("status"),
        candidate.get("passed"),
        candidate.get("attempt"),
    )
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_key = (
            record.get("id"),
            record.get("timestamp"),
            record.get("summary"),
            record.get("status"),
            record.get("passed"),
            record.get("attempt"),
        )
        if record_key == candidate_key:
            return True
    return False


def _record_memory(root: Path, run: Mapping[str, Any], *, reason: str) -> None:
    memory = _load_autopilot_memory(root)
    memory.setdefault("workflow_outcomes", [])
    memory.setdefault("validation_history", [])
    memory.setdefault("repair_outcomes", [])
    memory.setdefault("prior_failures", [])
    memory.setdefault("completed_roadmap_phases", [])
    memory.setdefault("preferred_execution_strategies", [])
    memory.setdefault("per_specialization", {})

    profile = _profile_for_run(run)
    per_specialization = memory.get("per_specialization")
    if not isinstance(per_specialization, dict):
        per_specialization = {}
        memory["per_specialization"] = per_specialization
    specialization_memory = per_specialization.setdefault(
        profile.id,
        {
            "successful_workflows": [],
            "repair_patterns": [],
            "architecture_conventions": [],
            "deployment_history": [],
            "recurring_validation_failures": [],
            "validation_history": [],
            "roadmap_history": [],
            "preferred_execution_strategies": [],
            "updated_at": None,
        },
    )
    if not isinstance(specialization_memory, dict):
        specialization_memory = {
            "successful_workflows": [],
            "repair_patterns": [],
            "architecture_conventions": [],
            "deployment_history": [],
            "recurring_validation_failures": [],
            "validation_history": [],
            "roadmap_history": [],
            "preferred_execution_strategies": [],
            "updated_at": None,
        }
        per_specialization[profile.id] = specialization_memory
    for key in [
        "successful_workflows",
        "repair_patterns",
        "architecture_conventions",
        "deployment_history",
        "recurring_validation_failures",
        "validation_history",
        "roadmap_history",
        "preferred_execution_strategies",
    ]:
        specialization_memory.setdefault(key, [])

    if reason == "autopilot_started":
        strategy = {
            "timestamp": _now(),
            "mode": run.get("mode"),
            "workflow_type": run.get("workflow_type"),
            "specialization": profile.id,
            "orchestration_strategy": profile.orchestration_strategy.get("name"),
            "validation_strategy": profile.validation_strategy.get("name"),
            "source": "autopilot_start",
        }
        memory["preferred_execution_strategies"].append(strategy)
        specialization_memory["preferred_execution_strategies"].append(dict(strategy))
    if run.get("status") in {"completed", "failed", "cancelled"}:
        outcome = {
            "timestamp": _now(),
            "autopilot_id": run.get("id"),
            "workflow_type": run.get("workflow_type"),
            "mode": run.get("mode"),
            "specialization": profile.id,
            "status": run.get("status"),
            "duration_seconds": _duration_seconds(run.get("started_at"), run.get("finished_at")),
        }
        memory["workflow_outcomes"].append(outcome)
        if run.get("status") == "completed":
            specialization_memory["successful_workflows"].append(dict(outcome))
    if run.get("status") == "failed":
        memory["prior_failures"].append(
            {
                "timestamp": _now(),
                "autopilot_id": run.get("id"),
                "current_task": run.get("current_task"),
                "last_operation": run.get("last_operation"),
            }
        )
    for validation in run.get("validation_chain", [])[-3:]:
        if isinstance(validation, Mapping):
            validation_record = dict(validation)
            validation_record.setdefault("specialization", profile.id)
            if _memory_record_seen(memory["validation_history"], validation_record):
                continue
            memory["validation_history"].append(validation_record)
            specialization_memory["validation_history"].append(dict(validation_record))
            if validation_record.get("passed") is False or validation_record.get("status") in {"failed", "error"}:
                specialization_memory["recurring_validation_failures"].append(dict(validation_record))
    for repair in run.get("repair_history", [])[-3:]:
        if isinstance(repair, Mapping):
            repair_record = dict(repair)
            repair_record.setdefault("specialization", profile.id)
            if _memory_record_seen(memory["repair_outcomes"], repair_record):
                continue
            memory["repair_outcomes"].append(repair_record)
            specialization_memory["repair_patterns"].append(dict(repair_record))
    roadmap = run.get("roadmap_progress", {})
    for item in roadmap.get("items", []) if isinstance(roadmap, Mapping) else []:
        if item.get("status") == "completed" and item not in memory["completed_roadmap_phases"]:
            roadmap_item = dict(item)
            roadmap_item.setdefault("specialization", profile.id)
            memory["completed_roadmap_phases"].append(roadmap_item)
            specialization_memory["roadmap_history"].append(dict(roadmap_item))

    if profile.id == "refactor_autopilot" and run.get("target_files"):
        specialization_memory["architecture_conventions"].append(
            {
                "timestamp": _now(),
                "source": "refactor_scope",
                "target_files": list(run.get("target_files", []))[:20],
                "risk_level": run.get("execution_risk_level"),
            }
        )
    if profile.id == "deployment_autopilot":
        specialization_memory["deployment_history"].append(
            {
                "timestamp": _now(),
                "autopilot_id": run.get("id"),
                "workflow_type": run.get("workflow_type"),
                "validation_status": run.get("validation_status"),
                "rollback_readiness": run.get("rollback_readiness"),
            }
        )

    for key in [
        "completed_roadmap_phases",
        "prior_failures",
        "repair_outcomes",
        "preferred_execution_strategies",
        "validation_history",
        "workflow_outcomes",
    ]:
        memory[key] = list(memory.get(key, []))[-200:]
    for value in per_specialization.values():
        if not isinstance(value, dict):
            continue
        for key, entries in list(value.items()):
            if isinstance(entries, list):
                value[key] = entries[-200:]
        value["updated_at"] = _now()
    memory["updated_at"] = _now()
    _write_autopilot_memory(root, memory)


def _safe_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    redacted = dict(payload)
    for key in list(redacted):
        if "token" in key.lower() or "key" in key.lower() or "secret" in key.lower():
            redacted[key] = "[redacted]"
    return redacted


def _payload_size(payload: Mapping[str, Any]) -> int:
    try:
        return len(json.dumps(payload, default=str))
    except Exception:
        return len(str(payload))


def _trim_run_state(run: MutableMapping[str, Any]) -> None:
    if isinstance(run.get("logs"), list):
        run["logs"] = run["logs"][-_MAX_LOGS_PER_RUN:]
    if isinstance(run.get("decision_log"), list):
        run["decision_log"] = run["decision_log"][-_TRUST_DECISION_LIMIT:]
    if isinstance(run.get("blocked_actions"), list):
        run["blocked_actions"] = run["blocked_actions"][-100:]
    if isinstance(run.get("validation_chain"), list):
        run["validation_chain"] = run["validation_chain"][-100:]
    if isinstance(run.get("repair_history"), list):
        run["repair_history"] = run["repair_history"][-100:]
    if isinstance(run.get("terminal_jobs"), list):
        run["terminal_jobs"] = run["terminal_jobs"][-100:]


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _validation_command(validation_commands: Optional[List[Mapping[str, Any]]]) -> Optional[List[str]]:
    if not validation_commands:
        return None
    first = validation_commands[0]
    command: Any
    if isinstance(first, Mapping):
        command = first.get("command") or first.get("args")
    else:
        command = first
    if isinstance(command, str):
        return [part for part in command.split(" ") if part]
    if isinstance(command, list):
        return [str(part) for part in command if str(part).strip()]
    return None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _clamp(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _duration_seconds(start: Any, end: Any) -> float:
    try:
        if not start or not end:
            return 0.0
        started = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        ended = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=timezone.utc)
        return max(0.0, (ended - started).total_seconds())
    except Exception:
        return 0.0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
