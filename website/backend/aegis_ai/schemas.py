# backend/schemas.py
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ModeName = Literal["build", "develop", "review", "chat"]
ChangeAction = Literal["create", "update", "append", "delete"]
MediaKind = Literal[
    "image",
    "video",
    "animation",
    "gif",
    "video_edit",
    "music_beat",
    "psd_template",
    "brand_kit",
    "thumbnail",
    "icon_set",
    "sticker_pack",
]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class ModeOption(BaseModel):
    id: ModeName
    label: str
    description: str


class WorkspaceFile(BaseModel):
    path: str
    size: int
    kind: str
    is_large: bool = False
    estimated_lines: int = 0
    large_file_strategy: str = ""


class WorkspaceInstructionFile(BaseModel):
    path: str
    title: str = ""
    kind: str = "instruction"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    pending_count: int = 0
    completed_count: int = 0
    total_items: int = 0
    pending_items: list[str] = Field(default_factory=list)
    summary: str = ""
    excerpt: str = ""


class WorkspaceInstructionStatusFile(BaseModel):
    path: str = ""
    title: str = ""
    kind: str = "instruction"
    score: float = 0.0
    open_items: int = 0
    completed_items: int = 0
    total_items: int = 0
    pending_items: list[str] = Field(default_factory=list)
    summary: str = ""


class WorkspaceInstructionStatusInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="", alias="schema")
    updated_at: str = ""
    source_message: str = ""
    instruction_file_count: int = 0
    open_items: int = 0
    completed_items: int = 0
    total_items: int = 0
    files: list[WorkspaceInstructionStatusFile] = Field(default_factory=list)
    last_validation: dict[str, Any] = Field(default_factory=dict)
    completion: dict[str, Any] = Field(default_factory=dict)
    applied: list[str] = Field(default_factory=list)
    recommendation: str = ""


class WorkspaceValidationPlanStep(BaseModel):
    id: str = ""
    phase: str = ""
    command: str = ""
    label: str = ""
    required: bool = True
    source_command: str = ""
    chain_index: int = 0
    chain_total: int = 0


class WorkspaceValidationPlanInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="", alias="schema")
    updated_at: str = ""
    project_name: str = ""
    preset_id: str = ""
    preset_label: str = ""
    install_command: str = ""
    validation_command: str = ""
    steps: list[WorkspaceValidationPlanStep] = Field(default_factory=list)
    last_run: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class WorkspaceReadinessInfo(BaseModel):
    status: Literal["ready", "needs_work", "needs_validation", "needs_repair", "unconfigured"] = "unconfigured"
    score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    next_action: str = ""
    blockers: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class WorkspaceProjectManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="", alias="schema")
    project_name: str = ""
    title: str = ""
    preset_id: str = ""
    preset_label: str = ""
    framework: str = ""
    language: str = ""
    package_manager: str = ""
    install_command: str = ""
    validation_command: str = ""
    original_prompt: str = ""
    tags: list[str] = Field(default_factory=list)
    generated_by: str = ""
    mission_contract: dict[str, Any] = Field(default_factory=dict)
    agent_handoff: dict[str, Any] = Field(default_factory=dict)


class WorkspaceDependency(BaseModel):
    name: str
    version: str = ""
    source: str = ""
    group: str = "runtime"


class WorkspaceScript(BaseModel):
    name: str
    command: str
    source: str = ""


class WorkspaceDependencyProfile(BaseModel):
    project_type: str = ""
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    install_commands: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    scripts: list[WorkspaceScript] = Field(default_factory=list)
    dependencies: list[WorkspaceDependency] = Field(default_factory=list)
    dev_dependencies: list[WorkspaceDependency] = Field(default_factory=list)
    database_tools: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkspaceProfileResponse(BaseModel):
    workspace_root: str
    manifest: WorkspaceProjectManifest | None = None
    has_manifest: bool = False
    dependency_profile: WorkspaceDependencyProfile = Field(default_factory=WorkspaceDependencyProfile)
    instruction_status: WorkspaceInstructionStatusInfo = Field(default_factory=WorkspaceInstructionStatusInfo)
    has_instruction_status: bool = False
    validation_plan: WorkspaceValidationPlanInfo = Field(default_factory=WorkspaceValidationPlanInfo)
    has_validation_plan: bool = False
    readiness: WorkspaceReadinessInfo = Field(default_factory=WorkspaceReadinessInfo)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceAutopilotStatusResponse(BaseModel):
    workspace_root: str
    phase: Literal["ready", "work", "validate", "repair", "unconfigured"] = "unconfigured"
    should_continue: bool = False
    recommended_mode: ModeName = "build"
    suggested_prompt: str = ""
    next_action: str = ""
    stop_reason: str = ""
    pass_budget: int = Field(default=0, ge=0, le=50)
    run_validation: bool = False
    max_repair_attempts: int = Field(default=0, ge=0, le=5)
    complexity: Literal["focused", "standard", "large", "epic"] = "focused"
    large_task_mode: bool = False
    estimated_passes_remaining: int = 0
    execution_lanes: list[str] = Field(default_factory=list)
    readiness: WorkspaceReadinessInfo = Field(default_factory=WorkspaceReadinessInfo)
    open_items: int = 0
    completed_items: int = 0
    total_items: int = 0
    validation_command: str = ""
    latest_validation_status: str = ""
    failed_step: str = ""
    failed_step_command: str = ""
    first_diagnostic: str = ""
    repair_brief: str = ""
    blockers: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    instruction_files: list[WorkspaceInstructionStatusFile] = Field(default_factory=list)
    next_open_items: list[str] = Field(default_factory=list)
    instruction_source: str = ""


class CommandRun(BaseModel):
    command: str
    cwd: str
    allowed: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    reason: str = ""
    category: str = ""
    summary: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    failed_step: str = ""
    failed_step_command: str = ""
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class ToolEvent(BaseModel):
    kind: str
    title: str
    status: Literal["ok", "warning", "error"] = "ok"
    detail: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class TaskSummary(BaseModel):
    id: str
    created_at: str
    finished_at: str | None = None
    mode: str
    workspace_root: str
    message: str
    status: str


class FixMemoryEntry(BaseModel):
    id: str
    created_at: str
    project_root: str
    error_signature: str
    fix_summary: str
    evidence: str
    confidence: float
    category: str = "unknown"


class ProjectMemoryEntry(BaseModel):
    id: str
    created_at: str
    updated_at: str
    project_root: str
    category: str
    title: str
    detail: str
    source: str
    confidence: float


class RepairAttempt(BaseModel):
    attempt: int
    category: str
    before_signature: str
    after_signature: str = ""
    outcome: str
    checkpoint: str | None = None
    summary: str = ""
    created_at: str = ""


class RouteCandidateInfo(BaseModel):
    candidate_id: str = ""
    role: str
    provider_hint: str
    required_capabilities: list[str] = Field(default_factory=list)
    privacy_mode: str = "local-first"
    reason: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RoutingDecisionInfo(BaseModel):
    task_role: str
    privacy_mode: str = "local-first"
    candidates: list[RouteCandidateInfo] = Field(default_factory=list)
    fallback_roles: list[str] = Field(default_factory=list)
    requires_tools: bool = False
    requires_workspace: bool = False
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class TaskPlanInfo(BaseModel):
    intent: str
    objective: str
    workflow: str
    complexity: str = "focused"
    estimated_slices: int = 1
    pass_budget_hint: int = 0
    large_task_protocol: list[str] = Field(default_factory=list)
    decomposition_axes: list[str] = Field(default_factory=list)
    route_profile: dict[str, Any] = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    context_requirements: list[str] = Field(default_factory=list)
    tool_requirements: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
    routing: RoutingDecisionInfo | None = None


ModelAttemptStatus = Literal["planned", "skipped", "running", "succeeded", "failed", "canceled", "fallback"]
FeedbackSentiment = Literal["liked", "disliked", "accepted", "rejected", "copied", "revised", "neutral"]
FeedbackAction = Literal[
    "message_feedback",
    "response_feedback",
    "validation_feedback",
    "change_feedback",
    "regenerated",
    "accepted",
    "rejected",
    "applied",
    "rolled_back",
    "corrected",
    "copied",
    "manual",
]


class ModelAttemptInfo(BaseModel):
    attempt: int
    role: str
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    endpoint: str = ""
    privacy_mode: str = "local-first"
    status: ModelAttemptStatus = "planned"
    reason: str = ""
    error: str = ""
    retryable: bool = True
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    started_at: str = ""
    finished_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRouteHealthInfo(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    model: str = ""
    role: str = ""
    attempts: int = 0
    terminal_attempts: int = 0
    successes: int = 0
    failures: int = 0
    fallback_attempts: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    average_latency_ms: float | None = None
    structured_preview_attempts: int = 0
    structured_preview_retired_attempts: int = 0
    structured_preview_reset_count: int = 0
    structured_preview_final_winners: int = 0
    structured_preview_retired_rate: float = 0.0
    penalty: float = 0.0
    cooldown: bool = False
    latest_error: str = ""
    latest_at: str = ""
    recommendation: str = ""


class ContextBudgetItemInfo(BaseModel):
    kind: str
    ref: str
    estimated_tokens: int = 0
    included: bool = True
    reason: str = ""


class ContextBudgetInfo(BaseModel):
    intent: str = ""
    route_role: str = ""
    strategy: str = ""
    privacy_mode: str = "local-first"
    max_context_tokens: int = 0
    estimated_context_tokens: int = 0
    estimated_file_tokens: int = 0
    reserve_response_tokens: int = 0
    max_context_files: int = 0
    selected_file_count: int = 0
    workspace_file_count: int = 0
    selected_memory_count: int = 0
    selected_project_memory_count: int = 0
    omitted_file_count: int = 0
    omitted_memory_count: int = 0
    omitted_project_memory_count: int = 0
    max_file_chars: int = 0
    max_history_turns: int = 0
    notes: list[str] = Field(default_factory=list)
    items: list[ContextBudgetItemInfo] = Field(default_factory=list)


class FileChange(BaseModel):
    action: ChangeAction
    path: str
    content: str | None = None
    summary: str = ""

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip().lstrip("/")
        path = PurePosixPath(normalized)
        parts = path.parts

        if not normalized:
            raise ValueError("path must be a relative path inside the workspace")

        if normalized in {".", ".."}:
            raise ValueError("path must point to a file inside the workspace")

        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("path must be a relative path inside the workspace")

        return str(path)


class AgentRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    workspace_root: str | None = None
    mode: ModeName | None = None
    apply_changes: bool = False
    run_validation: bool = False
    context_paths: list[str] = Field(default_factory=list, max_length=50)
    max_repair_attempts: int = Field(default=1, ge=0, le=5)
    max_files: int = Field(default=120, ge=1, le=5000)
    validation_command_override: str = ""
    validation_label_override: str = ""
    validation_notes_override: str = ""


class RoutePreviewRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    workspace_root: str | None = None
    mode: ModeName | None = None
    context_paths: list[str] = Field(default_factory=list, max_length=50)
    max_files: int = Field(default=120, ge=1, le=5000)


class RoutePreviewResponse(BaseModel):
    workspace_root: str
    mode: ModeName
    task_plan: TaskPlanInfo
    context_budget: ContextBudgetInfo | None = None
    model_attempts: list[ModelAttemptInfo] = Field(default_factory=list)
    primary_attempt: ModelAttemptInfo | None = None
    registry_message: str = ""
    benchmark_message: str = ""
    recommendations: list[str] = Field(default_factory=list)


class CompletionQualityInfo(BaseModel):
    status: Literal["unknown", "needs_work", "ready", "blocked"] = "unknown"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    should_continue: bool = False


class AgentResponse(BaseModel):
    task_id: str
    reply: str
    plan: list[str] = Field(default_factory=list)
    changes: list[FileChange] = Field(default_factory=list)
    applied: list[str] = Field(default_factory=list)
    checkpoint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    events: list[ToolEvent] = Field(default_factory=list)
    validation: CommandRun | None = None
    validation_profile: "ValidationRecipe | None" = None
    task_plan: TaskPlanInfo | None = None
    context_budget: ContextBudgetInfo | None = None
    model_attempts: list[ModelAttemptInfo] = Field(default_factory=list)
    assistant_name: str
    mode: ModeName
    engine: str
    workspace_root: str
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    context_files: list[WorkspaceFile] = Field(default_factory=list)
    memory_hits: list[FixMemoryEntry] = Field(default_factory=list)
    project_memory_hits: list[ProjectMemoryEntry] = Field(default_factory=list)
    recent_tasks: list[TaskSummary] = Field(default_factory=list)
    repair_attempts: list[RepairAttempt] = Field(default_factory=list)
    completion_quality: CompletionQualityInfo = Field(default_factory=CompletionQualityInfo)


class ChatStreamEventInfo(BaseModel):
    event: str
    payload: str
    description: str


class ChatStreamContractResponse(BaseModel):
    schema_version: str = "aegis.chat.stream.v1"
    transport: str = "server-sent-events"
    endpoint: str = "/api/chat/stream"
    method: str = "POST"
    content_type: str = "text/event-stream"
    event_order: list[str] = Field(default_factory=lambda: ["meta", "status", "delta", "final", "error", "done"])
    events: list[ChatStreamEventInfo] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ApplyRequest(BaseModel):
    workspace_root: str | None = None
    changes: list[FileChange]


class ApplyResponse(BaseModel):
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checkpoint: str | None = None
    workspace_root: str
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)


class ProjectScaffoldPreset(BaseModel):
    id: str
    label: str
    framework: str
    language: str
    package_manager: str = ""
    install_command: str = ""
    validation_command: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ProjectScaffoldRequest(BaseModel):
    target_path: str = Field(min_length=1)
    preset_id: str = "nextjs-ts-tailwind"
    project_name: str = "aegis-app"
    prompt: str = ""
    overwrite: bool = False
    install_command: str = ""
    validation_command: str = ""
    include_gitignore: bool = True
    create_roadmap: bool = True
    run_install: bool = False
    run_validation: bool = False
    max_repair_attempts: int = Field(default=1, ge=0, le=5)


class ProjectScaffoldPlanRequest(BaseModel):
    prompt: str = Field(min_length=1)
    workspace_root: str | None = None
    preferred_target_path: str = ""


class ProjectScaffoldFile(BaseModel):
    path: str
    action: ChangeAction = "create"
    summary: str = ""
    size: int = 0


class ProjectBuildStage(BaseModel):
    id: str
    label: str
    status: Literal["planned", "running", "succeeded", "failed", "blocked", "skipped"] = "planned"
    detail: str = ""
    command: str = ""
    output_excerpt: str = ""
    error: str = ""


class ProjectScaffoldResponse(BaseModel):
    ok: bool = True
    message: str = ""
    execution_mode: Literal["scaffold", "existing_validation"] = "scaffold"
    primary_action: Literal["create_or_update_files", "validate_existing_project"] = "create_or_update_files"
    target_path: str = ""
    preset: ProjectScaffoldPreset
    plan_steps: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    diff_summary: list[str] = Field(default_factory=list)
    memory_paths: list[str] = Field(default_factory=list)
    files: list[ProjectScaffoldFile] = Field(default_factory=list)
    file_change_count: int = 0
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checkpoint: str | None = None
    install_command: str = ""
    validation_command: str = ""
    roadmap_path: str = ""
    build_log_path: str = ""
    stages: list[ProjectBuildStage] = Field(default_factory=list)
    validation: CommandRun | None = None
    next_steps: list[str] = Field(default_factory=list)
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)


class ProjectScaffoldPlanResponse(BaseModel):
    ok: bool = True
    message: str = ""
    prompt: str = ""
    execution_mode: Literal["scaffold", "existing_validation"] = "scaffold"
    primary_action: Literal["create_or_update_files", "validate_existing_project"] = "create_or_update_files"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    preset: ProjectScaffoldPreset
    project_name: str = "aegis-app"
    target_path: str = ""
    install_command: str = ""
    validation_command: str = ""
    overwrite: bool = False
    include_gitignore: bool = True
    plan_steps: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    detected_keywords: list[str] = Field(default_factory=list)
    scaffold_request: ProjectScaffoldRequest


class RestoreCheckpointRequest(BaseModel):
    workspace_root: str | None = None
    checkpoint: str = Field(min_length=1)


class RestoreCheckpointResponse(BaseModel):
    restored: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    workspace_root: str
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)


class CheckpointFileInfo(BaseModel):
    path: str
    state: str


class CheckpointSummary(BaseModel):
    id: str
    created_at: str = ""
    file_count: int = 0
    present_count: int = 0
    missing_count: int = 0
    files: list[CheckpointFileInfo] = Field(default_factory=list)


class CheckpointListResponse(BaseModel):
    workspace_root: str
    checkpoints: list[CheckpointSummary] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    workspace_root: str | None = None


class VerificationRequest(BaseModel):
    workspace_root: str | None = None
    include_install: bool = False
    continue_on_failure: bool = False
    max_steps: int = Field(default=8, ge=1, le=20)


class ValidationRecipe(BaseModel):
    command: str
    label: str = ""
    source: str = ""
    updated_at: str = ""
    notes: str = ""


class ValidationSuggestion(BaseModel):
    command: str
    label: str
    category: str
    reason: str


class ValidationProfileResponse(BaseModel):
    workspace_root: str
    profile: ValidationRecipe | None = None
    suggestions: list[ValidationSuggestion] = Field(default_factory=list)


class ValidationProfileUpdateRequest(BaseModel):
    command: str = ""
    label: str = ""
    notes: str = ""


class WorkspaceSetupRequest(BaseModel):
    workspace_root: str | None = None
    overwrite_manifest: bool = False
    project_name: str = ""
    title: str = ""
    install_command: str = ""
    validation_command: str = ""
    notes: str = ""


class WorkspaceSetupResponse(BaseModel):
    workspace_root: str
    manifest: WorkspaceProjectManifest
    validation_profile: ValidationRecipe | None = None
    profile: WorkspaceProfileResponse
    created_files: list[str] = Field(default_factory=list)
    updated_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidateResponse(BaseModel):
    task_id: str
    workspace_root: str
    events: list[ToolEvent] = Field(default_factory=list)
    validation: CommandRun | None = None
    validation_profile: ValidationRecipe | None = None
    warnings: list[str] = Field(default_factory=list)


class VerificationStep(BaseModel):
    id: str = ""
    phase: str = ""
    command: str
    label: str = ""
    category: str = ""
    required: bool = True
    reason: str = ""
    source_command: str = ""
    chain_index: int = 0
    chain_total: int = 0
    status: Literal["planned", "skipped", "succeeded", "failed", "blocked"] = "planned"
    run: CommandRun | None = None


class VerificationResponse(BaseModel):
    task_id: str
    workspace_root: str
    status: Literal["passed", "failed", "blocked", "skipped"] = "skipped"
    steps: list[VerificationStep] = Field(default_factory=list)
    events: list[ToolEvent] = Field(default_factory=list)
    validation_profile: ValidationRecipe | None = None
    first_failure: CommandRun | None = None
    warnings: list[str] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    workspace_root: str
    recent_tasks: list[TaskSummary] = Field(default_factory=list)
    fix_memory: list[FixMemoryEntry] = Field(default_factory=list)
    project_memory: list[ProjectMemoryEntry] = Field(default_factory=list)


class ContextBudgetTelemetryEntry(BaseModel):
    task_id: str
    created_at: str
    workspace_root: str
    intent: str = ""
    route_role: str = ""
    strategy: str = ""
    privacy_mode: str = "local-first"
    max_context_tokens: int = 0
    estimated_context_tokens: int = 0
    estimated_file_tokens: int = 0
    reserve_response_tokens: int = 0
    selected_file_count: int = 0
    omitted_file_count: int = 0
    payload: ContextBudgetInfo = Field(default_factory=ContextBudgetInfo)


class ModelAttemptTelemetryEntry(BaseModel):
    task_id: str
    created_at: str
    workspace_root: str
    attempt: ModelAttemptInfo


class FeedbackRecordRequest(BaseModel):
    sentiment: FeedbackSentiment = "neutral"
    action: FeedbackAction = "manual"
    target: str = "assistant_response"
    task_id: str = ""
    content: str = ""
    context: str = ""
    model_label: str = ""
    route_role: str = ""
    candidate_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, value: Any) -> str:
        sentiment = str(value or "neutral").strip().lower()
        allowed = {"liked", "disliked", "accepted", "rejected", "copied", "revised", "neutral"}
        return sentiment if sentiment in allowed else "neutral"

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, value: Any) -> str:
        action = str(value or "manual").strip().lower().replace("-", "_")
        allowed = {
            "message_feedback",
            "response_feedback",
            "validation_feedback",
            "change_feedback",
            "regenerated",
            "accepted",
            "rejected",
            "applied",
            "rolled_back",
            "corrected",
            "copied",
            "manual",
        }
        return action if action in allowed else "manual"


class FeedbackTelemetryEntry(BaseModel):
    id: str
    created_at: str
    workspace_root: str
    task_id: str = ""
    sentiment: FeedbackSentiment = "neutral"
    action: FeedbackAction = "manual"
    target: str = "assistant_response"
    model_label: str = ""
    route_role: str = ""
    candidate_id: str = ""
    content_hash: str = ""
    context: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackTelemetrySummary(BaseModel):
    feedback_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    copied_count: int = 0
    revised_count: int = 0
    regenerated_count: int = 0
    applied_count: int = 0
    rolled_back_count: int = 0
    corrected_count: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0


class FeedbackAttributionRollup(BaseModel):
    dimension: str = ""
    key: str = ""
    label: str = ""
    feedback_count: int = 0
    task_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    copied_count: int = 0
    revised_count: int = 0
    regenerated_count: int = 0
    applied_count: int = 0
    rolled_back_count: int = 0
    corrected_count: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0
    latest_at: str = ""


class FeedbackTrendBucket(BaseModel):
    period_start: str = ""
    feedback_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    copied_count: int = 0
    revised_count: int = 0
    regenerated_count: int = 0
    applied_count: int = 0
    rolled_back_count: int = 0
    corrected_count: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0


class FeedbackRecordResponse(BaseModel):
    ok: bool = True
    workspace_root: str
    event: FeedbackTelemetryEntry


class FeedbackTelemetryResponse(BaseModel):
    workspace_root: str
    limit: int
    summary: FeedbackTelemetrySummary = Field(default_factory=FeedbackTelemetrySummary)
    events: list[FeedbackTelemetryEntry] = Field(default_factory=list)
    rollups: list[FeedbackAttributionRollup] = Field(default_factory=list)
    trends: list[FeedbackTrendBucket] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class TelemetryResponse(BaseModel):
    workspace_root: str
    context_budgets: list[ContextBudgetTelemetryEntry] = Field(default_factory=list)
    model_attempts: list[ModelAttemptTelemetryEntry] = Field(default_factory=list)
    feedback_events: list[FeedbackTelemetryEntry] = Field(default_factory=list)


class FallbackInspectorCandidate(BaseModel):
    index: int
    candidate_id: str = ""
    role: str = ""
    provider_hint: str = ""
    required_capabilities: list[str] = Field(default_factory=list)
    privacy_mode: str = "local-first"
    reason: str = ""
    confidence: float = 0.0
    status: str = "not-planned"
    matched_attempt_number: int | None = None
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    registry_resolved: bool | None = None
    retryable: bool | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    token_estimator_source: str = ""
    context_window: int | None = None
    context_window_utilization: float | None = None
    error: str = ""
    adapter_status: str = ""
    adapter_message: str = ""
    adapter_recommendation: str = ""
    adapter_secret_env: str = ""
    adapter_secret_present: bool = False
    adapter_cooldown: bool = False
    adapter_preflight_skips: int = 0
    adapter_recent_failures: int = 0
    adapter_latest_error: str = ""


class FallbackInspectorTask(BaseModel):
    task_id: str
    created_at: str
    finished_at: str | None = None
    mode: str
    workspace_root: str
    message: str
    status: str
    task_plan: TaskPlanInfo | None = None
    context_budget: ContextBudgetTelemetryEntry | None = None
    attempts: list[ModelAttemptTelemetryEntry] = Field(default_factory=list)
    candidates: list[FallbackInspectorCandidate] = Field(default_factory=list)
    fallback_roles: list[str] = Field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)


class FallbackInspectorResponse(BaseModel):
    workspace_root: str
    limit: int
    task_count: int = 0
    tasks: list[FallbackInspectorTask] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RouteQualityOverview(BaseModel):
    task_count: int = 0
    context_budget_count: int = 0
    model_attempt_count: int = 0
    succeeded_attempts: int = 0
    failed_attempts: int = 0
    planned_attempts: int = 0
    fallback_attempts: int = 0
    retryable_failures: int = 0
    success_rate: float = 0.0
    fallback_rate: float = 0.0
    estimated_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    average_latency_ms: float | None = None
    average_context_utilization: float | None = None
    average_context_tokens: float = 0.0
    average_selected_files: float = 0.0
    average_omitted_files: float = 0.0
    reliability_score: float = 0.0
    feedback_count: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    revised_feedback: int = 0
    regenerated_feedback: int = 0
    applied_feedback: int = 0
    rolled_back_feedback: int = 0
    corrected_feedback: int = 0
    positive_feedback_rate: float = 0.0
    negative_feedback_rate: float = 0.0
    structured_preview_attempts: int = 0
    structured_preview_retired_attempts: int = 0
    structured_preview_reset_count: int = 0
    structured_preview_final_winners: int = 0
    structured_preview_retired_rate: float = 0.0


class RouteQualityProviderRollup(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    task_count: int = 0
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    planned: int = 0
    fallback_attempts: int = 0
    success_rate: float = 0.0
    fallback_rate: float = 0.0
    estimated_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    average_latency_ms: float | None = None
    average_context_utilization: float | None = None
    token_estimator_sources: list[str] = Field(default_factory=list)


class RouteQualityTokenCalibrationRollup(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    attempts: int = 0
    calibrated_attempts: int = 0
    calibration_status: str = "insufficient"
    estimated_input_tokens: int = 0
    reported_input_tokens: int = 0
    estimated_output_tokens: int = 0
    reported_output_tokens: int = 0
    average_input_token_error: float | None = None
    worst_input_token_error: float | None = None
    average_output_token_error: float | None = None
    worst_output_token_error: float | None = None
    token_estimator_sources: list[str] = Field(default_factory=list)
    reported_token_sources: list[str] = Field(default_factory=list)
    recommendation: str = ""


class RouteQualityTokenCalibrationTrendBucket(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    period_start: str = ""
    attempts: int = 0
    calibrated_attempts: int = 0
    calibration_status: str = "insufficient"
    trend_direction: str = "baseline"
    estimated_input_tokens: int = 0
    reported_input_tokens: int = 0
    estimated_output_tokens: int = 0
    reported_output_tokens: int = 0
    average_input_token_error: float | None = None
    worst_input_token_error: float | None = None
    average_output_token_error: float | None = None
    worst_output_token_error: float | None = None
    recommendation: str = ""


class RouteQualityStructuredPreviewRollup(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    attempts: int = 0
    previewed_attempts: int = 0
    final_winning_attempts: int = 0
    retired_attempts: int = 0
    reset_count: int = 0
    delta_count: int = 0
    char_count: int = 0
    preview_success_rate: float = 0.0
    retired_rate: float = 0.0
    average_preview_chars: float = 0.0
    preview_status: str = "insufficient"
    retired_reasons: list[str] = Field(default_factory=list)
    recommendation: str = ""


class RouteQualityRoleRollup(BaseModel):
    role: str = ""
    task_count: int = 0
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    planned: int = 0
    fallback_attempts: int = 0
    success_rate: float = 0.0
    estimated_cost_usd: float = 0.0
    average_latency_ms: float | None = None


class RouteQualityContextRollup(BaseModel):
    route_role: str = ""
    intent: str = ""
    budget_count: int = 0
    average_context_tokens: float = 0.0
    average_file_tokens: float = 0.0
    average_reserved_response_tokens: float = 0.0
    average_selected_files: float = 0.0
    average_omitted_files: float = 0.0
    average_budget_utilization: float | None = None


class RouteQualityContextDrilldown(BaseModel):
    task_id: str = ""
    created_at: str = ""
    route_role: str = ""
    intent: str = ""
    strategy: str = ""
    privacy_mode: str = "local-first"
    max_context_tokens: int = 0
    estimated_context_tokens: int = 0
    estimated_file_tokens: int = 0
    reserve_response_tokens: int = 0
    utilization: float | None = None
    selected_file_count: int = 0
    omitted_file_count: int = 0
    selected_memory_count: int = 0
    omitted_memory_count: int = 0
    selected_project_memory_count: int = 0
    omitted_project_memory_count: int = 0
    selected_refs: list[str] = Field(default_factory=list)
    omitted_refs: list[str] = Field(default_factory=list)
    largest_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RouteQualityResponse(BaseModel):
    workspace_root: str
    limit: int
    overview: RouteQualityOverview = Field(default_factory=RouteQualityOverview)
    providers: list[RouteQualityProviderRollup] = Field(default_factory=list)
    token_calibration: list[RouteQualityTokenCalibrationRollup] = Field(default_factory=list)
    token_calibration_trends: list[RouteQualityTokenCalibrationTrendBucket] = Field(default_factory=list)
    structured_preview: list[RouteQualityStructuredPreviewRollup] = Field(default_factory=list)
    roles: list[RouteQualityRoleRollup] = Field(default_factory=list)
    contexts: list[RouteQualityContextRollup] = Field(default_factory=list)
    context_drilldowns: list[RouteQualityContextDrilldown] = Field(default_factory=list)
    feedback_rollups: list[FeedbackAttributionRollup] = Field(default_factory=list)
    feedback_trends: list[FeedbackTrendBucket] = Field(default_factory=list)
    feedback_events: list[FeedbackTelemetryEntry] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


TelemetrySnapshotStatus = Literal["hit", "miss", "refreshed"]


class TelemetrySnapshotPruneInfo(BaseModel):
    retention_max_snapshots: int = 0
    retention_days: int = 0
    deleted_count: int = 0
    retained_count: int = 0
    oldest_retained_at: str = ""
    newest_retained_at: str = ""
    recommendation: str = ""


class TelemetrySnapshot(BaseModel):
    id: str
    workspace_root: str
    snapshot_key: str
    created_at: str
    updated_at: str
    route_quality_limit: int
    fallback_limit: int
    feedback_limit: int
    stale_after_seconds: int = 900
    age_seconds: int = 0
    is_stale: bool = False
    route_quality: RouteQualityResponse
    fallback_inspector: FallbackInspectorResponse
    feedback: FeedbackTelemetryResponse


class TelemetrySnapshotResponse(BaseModel):
    workspace_root: str
    cache_status: TelemetrySnapshotStatus = "miss"
    snapshot: TelemetrySnapshot | None = None
    prune: TelemetrySnapshotPruneInfo = Field(default_factory=TelemetrySnapshotPruneInfo)
    recommendations: list[str] = Field(default_factory=list)


RoutePolicyProviderAction = Literal["promote", "hold", "monitor", "deprioritize"]
RoutePolicyRoleAction = Literal["keep", "switch_primary", "strengthen_fallback", "rebalance"]
RoutePolicyRiskLevel = Literal["low", "medium", "high"]


class RoutePolicyProviderProposal(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    provider_api: str = ""
    model: str = ""
    observed_rank: int = 0
    proposed_rank: int = 0
    action: RoutePolicyProviderAction = "hold"
    risk_level: RoutePolicyRiskLevel = "low"
    confidence: float = 0.0
    score: float = 0.0
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    fallback_rate: float = 0.0
    success_rate: float = 0.0
    positive_feedback_rate: float = 0.0
    negative_feedback_rate: float = 0.0
    average_latency_ms: float | None = None
    average_context_utilization: float | None = None
    estimated_cost_usd: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RoutePolicyRoleProposal(BaseModel):
    role: str = ""
    action: RoutePolicyRoleAction = "keep"
    observed_primary_provider: str = ""
    proposed_primary_provider: str = ""
    confidence: float = 0.0
    task_count: int = 0
    attempts: int = 0
    success_rate: float = 0.0
    fallback_attempts: int = 0
    score_delta: float = 0.0
    candidate_provider_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RoutePolicyDiffResponse(BaseModel):
    workspace_root: str
    generated_at: str
    limit: int
    source: str = "live"
    source_snapshot_id: str = ""
    source_snapshot_age_seconds: int = 0
    source_snapshot_stale: bool = False
    min_attempts: int = 3
    provider_proposals: list[RoutePolicyProviderProposal] = Field(default_factory=list)
    role_proposals: list[RoutePolicyRoleProposal] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeHealthResponse(BaseModel):
    ok: bool = True
    ready: bool = True
    status: Literal["ready", "degraded"] = "ready"
    app: str = "Aegis Coding AI"
    version: str = ""
    engine: str
    engine_ready: bool = True
    engine_message: str = ""
    model_name: str = ""
    model_api: str = ""
    model_endpoint: str = ""
    model_ready: bool = False
    model_message: str = ""
    project_root: str = ""
    workspace_root: str = ""
    database_path: str = ""
    env_exists: bool = False
    router_execution_enabled: bool = False
    router_enabled: bool = False
    fallback_supported: bool = False
    provider_count: int = 0
    configured_provider_count: int = 0
    enabled_provider_count: int = 0
    role_count: int = 0
    recommendations: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    assistant_name: str
    assistant_mission: str
    default_mode: ModeName
    modes: list[ModeOption] = Field(default_factory=list)
    default_workspace: str
    engine: str
    engine_ready: bool
    engine_message: str
    model_name: str
    model_endpoint: str
    model_api: str
    model_ready: bool = False
    model_message: str = ""
    database_path: str
    command_allowlist: str
    command_timeout_seconds: int
    auto_run_validation: bool
    router_execution_enabled: bool = False
    shared_workspace_mode: bool = False
    feedback_capture_excerpts: bool = True
    feedback_redaction_enabled: bool = True
    feedback_max_excerpt_chars: int = 320
    feedback_hash_content: bool = True
    env_exists: bool = False


class ModelCapabilities(BaseModel):
    chat: bool = True
    code: bool = False
    debug: bool = False
    refactor: bool = False
    reasoning: bool = False
    research: bool = False
    streaming: bool = False
    structured_json: bool = False
    tools: bool = False
    vision: bool = False
    audio: bool = False
    embeddings: bool = False
    image: bool = False
    video: bool = False
    realtime: bool = False
    judge: bool = False
    computer_use: bool = False


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    api: str
    endpoint: str
    local: bool = True
    configured: bool = False
    available: bool = False
    ready: bool = False
    message: str = ""
    size: int | None = None
    modified_at: str = ""
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)


class ModelInventoryResponse(BaseModel):
    active_model: str
    active_api: str
    active_endpoint: str
    router_enabled: bool = False
    fallback_supported: bool = False
    message: str = ""
    models: list[ModelInfo] = Field(default_factory=list)


class ModelRegistryProvider(BaseModel):
    id: str
    label: str
    api: str
    endpoint: str
    model_name: str = ""
    model_aliases: list[str] = Field(default_factory=list)
    secret_env: str = ""
    local: bool = True
    enabled: bool = True
    configured: bool = False
    capabilities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    cost_tier: str = "unknown"
    context_window: int | None = None
    rate_limit_rpm: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    health: str = "unknown"
    notes: str = ""


class ModelRegistryProviderUpsertRequest(BaseModel):
    id: str
    label: str = ""
    api: str = "openai-compatible"
    endpoint: str = ""
    model_name: str = ""
    model_aliases: list[str] = Field(default_factory=list)
    secret_env: str = ""
    local: bool = True
    enabled: bool = True
    configured: bool = False
    capabilities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    cost_tier: str = "unknown"
    context_window: int | None = None
    rate_limit_rpm: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    health: str = "unknown"
    notes: str = ""


class ModelRegistryRole(BaseModel):
    id: str
    label: str
    description: str
    primary_model: str = ""
    fallback_models: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    privacy_mode: str = "local-first"
    cost_tier: str = "unknown"
    status: str = "planned"


class ModelRoutingPreset(BaseModel):
    id: str
    label: str
    description: str
    role_order: list[str] = Field(default_factory=list)
    privacy_mode: str = "local-first"


class ModelRegistryResponse(BaseModel):
    version: int = 1
    active_provider_id: str = ""
    active_model: str = ""
    router_enabled: bool = False
    fallback_supported: bool = True
    message: str = ""
    providers: list[ModelRegistryProvider] = Field(default_factory=list)
    roles: list[ModelRegistryRole] = Field(default_factory=list)
    presets: list[ModelRoutingPreset] = Field(default_factory=list)


class ModelRegistryAuditIssue(BaseModel):
    severity: Literal["error", "warning", "info"] = "info"
    category: str = ""
    provider_id: str = ""
    role: str = ""
    message: str = ""
    recommendation: str = ""


class ModelRegistryRouteCoverage(BaseModel):
    role: str = ""
    label: str = ""
    status: Literal["ready", "covered", "partial", "missing"] = "missing"
    primary_model: str = ""
    primary_provider_id: str = ""
    primary_configured: bool = False
    required_capabilities: list[str] = Field(default_factory=list)
    eligible_provider_count: int = 0
    configured_provider_count: int = 0
    enabled_provider_count: int = 0
    fallback_configured_count: int = 0
    candidate_provider_ids: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ModelRegistrySetupAction(BaseModel):
    id: str = ""
    kind: Literal["secret", "route", "provider", "benchmark"] = "provider"
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    title: str = ""
    detail: str = ""
    recommendation: str = ""
    env_var: str = ""
    role: str = ""
    provider_ids: list[str] = Field(default_factory=list)
    command: str = ""


class ModelAdapterHealthInfo(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    api: str = ""
    endpoint: str = ""
    model: str = ""
    local: bool = True
    enabled: bool = True
    configured: bool = False
    status: str = "unknown"
    error_code: str = ""
    message: str = ""
    secret_env: str = ""
    secret_present: bool = False
    capabilities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    recent_attempts: int = 0
    recent_successes: int = 0
    recent_failures: int = 0
    recent_skips: int = 0
    preflight_skips: int = 0
    cooldown: bool = False
    latest_error: str = ""
    latest_at: str = ""
    recommendation: str = ""


class ModelTokenizerDiagnosticInfo(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    api: str = ""
    model: str = ""
    local: bool = True
    enabled: bool = True
    configured: bool = False
    context_window: int | None = None
    status: str = "unobserved"
    recent_attempts: int = 0
    exact_attempts: int = 0
    profiled_attempts: int = 0
    heuristic_attempts: int = 0
    missing_attempts: int = 0
    estimator_sources: list[str] = Field(default_factory=list)
    primary_estimator_source: str = ""
    average_context_utilization: float | None = None
    calibrated_attempts: int = 0
    average_input_token_error: float | None = None
    worst_input_token_error: float | None = None
    average_output_token_error: float | None = None
    worst_output_token_error: float | None = None
    reported_token_sources: list[str] = Field(default_factory=list)
    calibration_status: str = "insufficient"
    calibration_recommendation: str = ""
    recommendation: str = ""


class ModelRegistryAuditResponse(BaseModel):
    generated_at: str = ""
    readiness_score: int = 0
    status: Literal["ready", "attention", "blocked"] = "attention"
    provider_count: int = 0
    enabled_provider_count: int = 0
    configured_provider_count: int = 0
    disabled_provider_count: int = 0
    local_provider_count: int = 0
    cloud_provider_count: int = 0
    role_count: int = 0
    route_coverages: list[ModelRegistryRouteCoverage] = Field(default_factory=list)
    issues: list[ModelRegistryAuditIssue] = Field(default_factory=list)
    setup_actions: list[ModelRegistrySetupAction] = Field(default_factory=list)
    adapter_health: list[ModelAdapterHealthInfo] = Field(default_factory=list)
    tokenizer_diagnostics: list[ModelTokenizerDiagnosticInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ModelRegistryBenchmarkRoleDiff(BaseModel):
    role: str = ""
    action: str = "keep"
    current_primary_model: str = ""
    proposed_primary_model: str = ""
    current_fallback_models: list[str] = Field(default_factory=list)
    proposed_fallback_models: list[str] = Field(default_factory=list)
    winner_provider_id: str = ""
    winner_provider_label: str = ""
    winner_model: str = ""
    winner_score: float = 0.0
    health_penalty: float = 0.0
    health_cooldown: bool = False
    health_recommendation: str = ""
    reasons: list[str] = Field(default_factory=list)


class ModelRegistryBenchmarkPreviewResponse(BaseModel):
    applicable: bool = False
    message: str = ""
    role_diffs: list[ModelRegistryBenchmarkRoleDiff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ModelRegistryCheckpointInfo(BaseModel):
    id: str = ""
    created_at: str = ""
    reason: str = ""
    provider_count: int = 0
    role_count: int = 0
    router_enabled: bool = False
    active_provider_id: str = ""
    message: str = ""
    restore_provider_add_count: int = 0
    restore_provider_remove_count: int = 0
    restore_provider_change_count: int = 0
    restore_role_add_count: int = 0
    restore_role_remove_count: int = 0
    restore_role_change_count: int = 0
    restore_settings_change_count: int = 0
    restore_total_change_count: int = 0
    restore_summary: str = ""


class ModelRegistryCheckpointListResponse(BaseModel):
    checkpoints: list[ModelRegistryCheckpointInfo] = Field(default_factory=list)


class ModelRegistryCheckpointEntityDiff(BaseModel):
    id: str = ""
    label: str = ""
    action: str = "unchanged"
    current_summary: str = ""
    checkpoint_summary: str = ""


class ModelRegistryCheckpointSettingDiff(BaseModel):
    key: str = ""
    current_value: str = ""
    checkpoint_value: str = ""


class ModelRegistryCheckpointDiffResponse(BaseModel):
    checkpoint: ModelRegistryCheckpointInfo = Field(default_factory=ModelRegistryCheckpointInfo)
    provider_diffs: list[ModelRegistryCheckpointEntityDiff] = Field(default_factory=list)
    role_diffs: list[ModelRegistryCheckpointEntityDiff] = Field(default_factory=list)
    setting_diffs: list[ModelRegistryCheckpointSettingDiff] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ModelRegistryCheckpointCreateRequest(BaseModel):
    reason: str = "Manual model registry checkpoint."


class ModelDiskInfo(BaseModel):
    drive_root: str = ""
    project_root: str = ""
    model_store_path: str = ""
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    model_store_bytes: int = 0
    free_percent: float = 0.0
    low_space: bool = False
    minimum_free_bytes: int = 0


class ManagedModelInfo(BaseModel):
    provider_id: str = ""
    label: str = ""
    api: str = ""
    endpoint: str = ""
    name: str = ""
    local: bool = True
    enabled: bool = True
    installed: bool = False
    configured: bool = False
    active: bool = False
    pullable: bool = False
    health: str = "unknown"
    roles: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    size_bytes: int | None = None
    modified_at: str = ""
    estimated_pull_bytes: int | None = None
    notes: str = ""


class ModelOperationInfo(BaseModel):
    id: str = ""
    model_name: str = ""
    action: str = ""
    status: str = ""
    message: str = ""
    pid: int | None = None
    started_at: str = ""
    finished_at: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    minimum_free_bytes: int = 0
    estimated_pull_bytes: int | None = None
    free_bytes_before: int | None = None


class ModelPullLogSummary(BaseModel):
    source: str = ""
    total: int = 0
    pulled: int = 0
    skipped: int = 0
    failed: int = 0
    latest_at: str = ""


class ModelManagerResponse(BaseModel):
    ok: bool = True
    message: str = ""
    disk: ModelDiskInfo = Field(default_factory=ModelDiskInfo)
    active_model: str = ""
    active_provider_id: str = ""
    providers_total: int = 0
    local_total: int = 0
    installed_total: int = 0
    pullable_total: int = 0
    cloud_total: int = 0
    models: list[ManagedModelInfo] = Field(default_factory=list)
    operations: list[ModelOperationInfo] = Field(default_factory=list)
    pull_logs: list[ModelPullLogSummary] = Field(default_factory=list)


class ModelPullRequest(BaseModel):
    model_name: str = Field(min_length=1)
    minimum_free_gb: float = 24.0


class ModelDeleteRequest(BaseModel):
    model_name: str = Field(min_length=1)
    confirm_model_name: str = Field(min_length=1)


class ModelBenchmarkSuiteInfo(BaseModel):
    id: str
    label: str
    description: str = ""


class ModelBenchmarkResult(BaseModel):
    id: str = ""
    created_at: str = ""
    provider_id: str = ""
    provider_label: str = ""
    api: str = ""
    endpoint: str = ""
    model_name: str = ""
    suite_id: str = ""
    suite_label: str = ""
    status: str = "pending"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int | None = None
    error: str = ""
    answer_excerpt: str = ""
    expected: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelBenchmarkProviderScore(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    api: str = ""
    model_name: str = ""
    local: bool = True
    enabled: bool = True
    configured: bool = False
    overall_score: float = 0.0
    chat_score: float | None = None
    code_score: float | None = None
    reasoning_score: float | None = None
    avg_latency_ms: int | None = None
    run_count: int = 0
    latest_at: str = ""
    recommendation: str = ""


class ModelBenchmarkSuiteSummary(BaseModel):
    suite_id: str = ""
    suite_label: str = ""
    best_provider_id: str = ""
    best_provider_label: str = ""
    best_model_name: str = ""
    best_score: float = 0.0
    best_latency_ms: int | None = None
    run_count: int = 0


class ModelBenchmarkRunRequest(BaseModel):
    suite_ids: list[str] = Field(default_factory=list)
    provider_ids: list[str] = Field(default_factory=list)
    max_models: int = Field(default=4, ge=1, le=20)
    local_only: bool = True
    timeout_seconds: float = Field(default=45.0, ge=5.0, le=180.0)


class ModelBenchmarkJobInfo(BaseModel):
    id: str = ""
    status: str = "queued"
    message: str = ""
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    suite_ids: list[str] = Field(default_factory=list)
    provider_ids: list[str] = Field(default_factory=list)
    max_models: int = 0
    local_only: bool = True
    timeout_seconds: float = 45.0
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    current_provider_id: str = ""
    current_model_name: str = ""
    current_suite_id: str = ""
    error: str = ""


class ModelBenchmarkSnapshot(BaseModel):
    ok: bool = True
    message: str = ""
    suites: list[ModelBenchmarkSuiteInfo] = Field(default_factory=list)
    provider_scores: list[ModelBenchmarkProviderScore] = Field(default_factory=list)
    suite_summaries: list[ModelBenchmarkSuiteSummary] = Field(default_factory=list)
    recent_results: list[ModelBenchmarkResult] = Field(default_factory=list)
    jobs: list[ModelBenchmarkJobInfo] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    results_total: int = 0
    latest_at: str = ""


class MediaAsset(BaseModel):
    path: str
    kind: str
    format: str
    role: str
    mime_type: str = ""
    editable: bool = False
    derived_from: str = ""


class MediaCapabilitiesResponse(BaseModel):
    supported_kinds: list[MediaKind] = Field(default_factory=list)
    local_formats: list[str] = Field(default_factory=list)
    provider_formats: list[str] = Field(default_factory=list)
    can_iterate_from_previous: bool = True
    theme_inference: bool = True
    psd_template_strategy: str
    local_renderers: dict[str, bool] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class MediaCreativeRequest(BaseModel):
    prompt: str = Field(min_length=1)
    kind: MediaKind = "image"
    feedback: str = ""
    previous_job_id: str = ""
    theme_color: str = ""
    aspect_ratio: str = "16:9"
    style: str = ""
    duration_seconds: float = Field(default=4.0, ge=0.5, le=120.0)
    fps: int = Field(default=12, ge=1, le=60)
    width: int = Field(default=1280, ge=256, le=4096)
    height: int = Field(default=720, ge=256, le=4096)
    output_formats: list[str] = Field(default_factory=list)


class MediaJobResponse(BaseModel):
    id: str
    created_at: str
    kind: MediaKind
    status: str
    prompt: str
    feedback: str = ""
    previous_job_id: str = ""
    theme_color: str
    palette: list[str] = Field(default_factory=list)
    aspect_ratio: str
    style: str = ""
    plan: list[str] = Field(default_factory=list)
    assets: list[MediaAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    job_dir: str


class ConfigUpdateRequest(BaseModel):
    assistant_name: str | None = Field(default=None, min_length=1)
    assistant_mission: str | None = Field(default=None, min_length=1)
    default_mode: ModeName | None = None
    default_workspace: str | None = Field(default=None, min_length=1)
    model_api: str | None = Field(default=None, min_length=1)
    model_endpoint: str | None = Field(default=None, min_length=1)
    model_name: str | None = Field(default=None, min_length=1)
    command_allowlist: str | None = Field(default=None, min_length=1)
    command_timeout_seconds: int | None = Field(default=None, ge=5, le=3600)
    auto_run_validation: bool | None = None
    shared_workspace_mode: bool | None = None
    feedback_capture_excerpts: bool | None = None
    feedback_redaction_enabled: bool | None = None
    feedback_max_excerpt_chars: int | None = Field(default=None, ge=0, le=2000)
    feedback_hash_content: bool | None = None
