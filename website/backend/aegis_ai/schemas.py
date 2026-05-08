# backend/schemas.py
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ModeName = Literal["build", "develop", "review", "chat"]
ChangeAction = Literal["create", "update", "append", "delete"]
MediaKind = Literal[
    "image",
    "image_to_image",
    "logo",
    "ui_mockup",
    "icon",
    "product_mockup",
    "style_transfer",
    "background_removal",
    "upscale",
    "variation",
    "video",
    "text_to_video",
    "image_to_video",
    "promo_video",
    "logo_intro",
    "app_showcase",
    "social_clip",
    "storyboard_video",
    "animation",
    "gif",
    "video_edit",
    "music_beat",
    "music",
    "drum_loop",
    "melody",
    "loop",
    "arrangement",
    "voice",
    "voiceover",
    "narration",
    "sound_effect",
    "audio_cleanup",
    "psd_template",
    "brand_kit",
    "thumbnail",
    "icon_set",
    "sticker_pack",
]
MediaJobStatus = Literal["queued", "generating", "failed", "completed", "canceled"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class ModeOption(BaseModel):
    id: ModeName
    label: str
    description: str


class AuthUser(BaseModel):
    id: str
    name: str
    email: str
    created_at: str
    plan: str = "free"
    role: Literal["user", "admin"] | str = "user"
    status: Literal["active", "banned", "disabled"] | str = "active"


class AuthRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    confirm_password: str = Field(min_length=8, max_length=256)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class AuthForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class AuthSessionResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: AuthUser
    expires_at: str


class AuthMessageResponse(BaseModel):
    ok: bool = True
    message: str


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


RuntimeCapabilityStatus = Literal["ready", "partial", "planned", "blocked", "disabled"]


class RuntimeCapabilityPillar(BaseModel):
    id: str
    name: str
    status: RuntimeCapabilityStatus = "partial"
    summary: str = ""
    privacy_scope: str = "local-first"
    modules: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    primary_surfaces: list[str] = Field(default_factory=list)
    active_items: int = 0
    signals: list[str] = Field(default_factory=list)
    next_workflows: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class RuntimeModalityCapability(BaseModel):
    id: str
    label: str
    status: RuntimeCapabilityStatus = "partial"
    input_supported: bool = False
    output_supported: bool = False
    analyzers: list[str] = Field(default_factory=list)
    generators: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeToolContract(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "ready"
    permission_scope: str = ""
    approval_required: bool = False
    sandboxed: bool = False
    rollback_supported: bool = False
    timeout_seconds: int = 0
    tracked_by_tasks: bool = True
    endpoints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeWorkflowEntry(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "ready"
    trigger: str = "manual"
    description: str = ""
    endpoints: list[str] = Field(default_factory=list)
    safety_profile: str = "approval-gated"
    task_tracked: bool = True


class UnifiedRuntimeSnapshot(BaseModel):
    generated_at: str
    api_version: str
    workspace_root: str
    runtime_name: str = "Auralith Runtime"
    mode: str = "local-first"
    pillars: list[RuntimeCapabilityPillar] = Field(default_factory=list)
    modalities: list[RuntimeModalityCapability] = Field(default_factory=list)
    tools: list[RuntimeToolContract] = Field(default_factory=list)
    workflows: list[RuntimeWorkflowEntry] = Field(default_factory=list)
    memory_summary: dict[str, Any] = Field(default_factory=dict)
    safety_summary: list[str] = Field(default_factory=list)
    active_counts: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


OperatingActionStatus = Literal["preview", "needs_approval", "blocked", "accepted", "failed"]


class OperatingEnvironmentCapability(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "partial"
    summary: str = ""
    permission_scope: str = ""
    approval_required: bool = False
    sandbox_required: bool = False
    rollback_supported: bool = False
    task_tracked: bool = True
    telemetry_enabled: bool = True
    adapter_ids: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    surfaces: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class OperatingEnvironmentAdapter(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "planned"
    provider: str = "local"
    enabled: bool = False
    permission_scope: str = ""
    capabilities: list[str] = Field(default_factory=list)
    approval_required: bool = True
    sandboxed: bool = True
    reason: str = ""
    notes: list[str] = Field(default_factory=list)
    last_seen_at: str = ""


class OperatingSystemSignal(BaseModel):
    id: str
    label: str
    category: str = "system"
    status: Literal["ok", "warning", "error"] = "ok"
    value: str = ""
    detail: str = ""
    updated_at: str = ""


class OperatingEnvironmentActionRequest(BaseModel):
    capability_id: str
    action: str
    workspace_root: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True
    approval_token: str = ""
    requested_by: str = "user"
    task_id: str = ""


class OperatingEnvironmentActionResponse(BaseModel):
    request_id: str
    capability_id: str
    action: str
    status: OperatingActionStatus = "preview"
    allowed: bool = False
    approval_required: bool = True
    reason: str = ""
    summary: str = ""
    required_permissions: list[str] = Field(default_factory=list)
    rollback_supported: bool = False
    safety_notes: list[str] = Field(default_factory=list)
    event: ToolEvent | None = None


class OperatingEnvironmentSnapshot(BaseModel):
    generated_at: str
    api_version: str
    workspace_root: str
    runtime_name: str = "Auralith OS"
    mode: str = "local-first"
    execution_mode: str = "control-plane"
    capabilities: list[OperatingEnvironmentCapability] = Field(default_factory=list)
    adapters: list[OperatingEnvironmentAdapter] = Field(default_factory=list)
    system_signals: list[OperatingSystemSignal] = Field(default_factory=list)
    permissions_summary: dict[str, Any] = Field(default_factory=dict)
    safety_summary: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TaskSummary(BaseModel):
    id: str
    task_id: str = ""
    project_id: str = ""
    parent_task_id: str | None = None
    title: str = ""
    user_goal: str = ""
    created_at: str
    updated_at: str = ""
    completed_at: str | None = None
    finished_at: str | None = None
    mode: str
    workspace_root: str
    message: str
    status: str
    priority: int = 0
    assigned_agent_role: str = ""
    related_files: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    error_summary: str = ""
    final_summary: str = ""


class TaskCreateRequest(BaseModel):
    workspace_root: str | None = None
    project_id: str = ""
    parent_task_id: str | None = None
    title: str = Field(min_length=1)
    user_goal: str = ""
    mode: ModeName | str = "develop"
    priority: int = 0
    assigned_agent_role: str = ""
    related_files: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)


class TaskActionRequest(BaseModel):
    reason: str = ""
    approval_id: str = ""
    approved: bool = True


class TaskActionResponse(BaseModel):
    task: TaskSummary
    event: ToolEvent | None = None


class TaskListResponse(BaseModel):
    workspace_root: str
    tasks: list[TaskSummary] = Field(default_factory=list)


class TaskDetailResponse(BaseModel):
    task: TaskSummary
    subtasks: list[TaskSummary] = Field(default_factory=list)


class TaskTimelineResponse(BaseModel):
    task_id: str
    events: list[ToolEvent] = Field(default_factory=list)


class TaskArtifactsResponse(BaseModel):
    task_id: str
    related_files: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    repair_attempts: list[RepairAttempt] = Field(default_factory=list)
    command_events: list[ToolEvent] = Field(default_factory=list)
    validation_events: list[ToolEvent] = Field(default_factory=list)


UnifiedContextRecordKind = Literal[
    "conversation",
    "project",
    "architecture",
    "file",
    "task",
    "timeline_event",
    "memory",
    "fix_memory",
    "media_job",
    "media_asset",
    "workflow",
    "automation",
    "research",
    "desktop",
    "system",
    "runtime",
    "recommendation",
    "telemetry",
]


class UnifiedContextRecord(BaseModel):
    id: str
    kind: UnifiedContextRecordKind | str
    title: str
    summary: str = ""
    source: str = ""
    reference: str = ""
    workspace_root: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = ""
    importance: float = 0.0
    tags: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    related_tasks: list[str] = Field(default_factory=list)
    related_assets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedContextRelationship(BaseModel):
    source_id: str
    target_id: str
    kind: str
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)


class UnifiedContextSourceSummary(BaseModel):
    source: str
    records: int = 0
    ready: bool = False
    summary: str = ""


class UnifiedContextSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str = "2026.05.07"
    records: list[UnifiedContextRecord] = Field(default_factory=list)
    relationships: list[UnifiedContextRelationship] = Field(default_factory=list)
    source_summaries: list[UnifiedContextSourceSummary] = Field(default_factory=list)
    timeline: list[UnifiedContextRecord] = Field(default_factory=list)
    cross_module_insights: list[str] = Field(default_factory=list)
    command_entrypoints: list[str] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class UnifiedContextSearchRequest(BaseModel):
    workspace_root: str | None = None
    query: str = ""
    scopes: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    include_relationships: bool = True


class UnifiedContextSearchResult(BaseModel):
    record: UnifiedContextRecord
    score: float = 0.0
    matched_fields: list[str] = Field(default_factory=list)
    relationships: list[UnifiedContextRelationship] = Field(default_factory=list)


class UnifiedContextSearchResponse(BaseModel):
    query: str
    workspace_root: str
    generated_at: str
    results: list[UnifiedContextSearchResult] = Field(default_factory=list)
    scope_summary: dict[str, int] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)


class GlobalCommandRequest(BaseModel):
    workspace_root: str | None = None
    command: str = Field(min_length=1)
    entrypoint: Literal["chat", "command_palette", "desktop_overlay", "voice", "mobile", "api"] | str = "command_palette"
    create_task: bool = False
    dry_run: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class GlobalCommandRoute(BaseModel):
    intent: str
    target_system: str
    task_kind: str = "general"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    creates_task: bool = False
    approval_required: bool = False
    rollback_supported: bool = False
    validation_required: bool = False
    endpoint: str = ""
    reason: str = ""
    safety_notes: list[str] = Field(default_factory=list)


class GlobalCommandResponse(BaseModel):
    workspace_root: str
    generated_at: str
    command: str
    entrypoint: str
    route: GlobalCommandRoute
    plan: list[str] = Field(default_factory=list)
    context_results: list[UnifiedContextSearchResult] = Field(default_factory=list)
    task: TaskSummary | None = None
    event: ToolEvent | None = None
    warnings: list[str] = Field(default_factory=list)


class AmbientPresenceState(BaseModel):
    status: Literal["calm", "focused", "busy", "attention", "degraded"] = "calm"
    active_focus: str = ""
    workload_level: Literal["light", "steady", "heavy", "overloaded"] = "light"
    suggestion_intensity: Literal["quiet", "normal", "reduced", "paused"] = "quiet"
    notification_style: Literal["silent", "subtle", "normal", "urgent_only"] = "subtle"
    continuity_summary: str = ""
    proactive_suggestions: list[str] = Field(default_factory=list)
    active_signals: list[str] = Field(default_factory=list)
    session_handoff: list[str] = Field(default_factory=list)


class OperatingTimelineEntry(BaseModel):
    id: str
    kind: str
    title: str
    summary: str = ""
    source: str = ""
    reference: str = ""
    occurred_at: str = ""
    status: str = ""
    importance: float = 0.0
    related_records: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    related_tasks: list[str] = Field(default_factory=list)
    related_assets: list[str] = Field(default_factory=list)
    replay_hint: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatingMemoryTimeline(BaseModel):
    workspace_root: str
    generated_at: str
    entries: list[OperatingTimelineEntry] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    reconstruction_notes: list[str] = Field(default_factory=list)
    replay_supported: bool = True
    search_supported: bool = True


class TimelineSearchRequest(BaseModel):
    workspace_root: str | None = None
    query: str = ""
    kinds: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class TimelineSearchResponse(BaseModel):
    query: str
    workspace_root: str
    generated_at: str
    results: list[OperatingTimelineEntry] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ForecastSignal(BaseModel):
    id: str
    kind: Literal[
        "architecture_risk",
        "dependency_break",
        "validation_failure",
        "workflow_bottleneck",
        "technical_debt",
        "migration_risk",
        "memory_bloat",
        "runtime_stability",
    ] | str
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    title: str
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    projected_impact: str = ""
    recommended_action: str = ""
    dry_run_available: bool = True
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SimulationForecastSnapshot(BaseModel):
    generated_at: str
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: list[ForecastSignal] = Field(default_factory=list)
    dry_run_modes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class CognitiveAwarenessState(BaseModel):
    load_level: Literal["low", "steady", "high", "overload_risk"] = "low"
    detected_patterns: list[str] = Field(default_factory=list)
    pacing: Literal["normal", "slow_down", "pause_and_summarize", "focus_mode"] = "normal"
    verbosity: Literal["concise", "balanced", "detailed"] = "balanced"
    notification_intensity: Literal["quiet", "normal", "urgent_only"] = "quiet"
    workflow_aggressiveness: Literal["conservative", "normal", "proactive"] = "conservative"
    recommendation_style: str = "calm, specific, and low-noise"
    safeguards: list[str] = Field(default_factory=list)


class HardwareAccelerationProfile(BaseModel):
    status: RuntimeCapabilityStatus = "partial"
    cpu_logical: int = 0
    gpu_available: bool = False
    npu_available: bool = False
    accelerators: list[str] = Field(default_factory=list)
    local_model_optimizations: list[str] = Field(default_factory=list)
    routing_notes: list[str] = Field(default_factory=list)
    power_profile: Literal["unknown", "balanced", "performance", "battery_saver"] = "unknown"
    warnings: list[str] = Field(default_factory=list)


class PersistentWorkspaceState(BaseModel):
    workspace_root: str
    restore_readiness: Literal["ready", "partial", "needs_attention"] = "partial"
    persisted_sections: list[str] = Field(default_factory=list)
    active_task_count: int = 0
    active_workflow_count: int = 0
    memory_record_count: int = 0
    media_asset_count: int = 0
    checkpoint_references: int = 0
    recovery_notes: list[str] = Field(default_factory=list)


class SelfDiagnosticSignal(BaseModel):
    id: str
    category: str
    status: Literal["healthy", "watch", "degraded", "critical", "unknown"] = "unknown"
    title: str
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = ""


class SkillPackInfo(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "planned"
    trust_level: str = "metadata"
    capabilities: list[str] = Field(default_factory=list)
    included_assets: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    lifecycle: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UniversalDataSource(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "partial"
    records_indexed: int = 0
    semantic_index_ready: bool = False
    permission_scope: str = ""
    connectors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PlatformSdkCapability(BaseModel):
    id: str
    name: str
    status: RuntimeCapabilityStatus = "partial"
    api_version: str = "2026.05.07"
    permission_scoped: bool = True
    sandboxed: bool = True
    signing_supported: bool = False
    lifecycle_hooks: list[str] = Field(default_factory=list)
    docs: list[str] = Field(default_factory=list)


class DigitalTwinWorkspaceModel(BaseModel):
    workspace_root: str
    model_version: str = "2026.05.07"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    modeled_entities: dict[str, int] = Field(default_factory=dict)
    architecture_summary: str = ""
    workflow_summary: str = ""
    dependency_summary: str = ""
    preference_summary: str = ""
    recovery_uses: list[str] = Field(default_factory=list)
    predictive_uses: list[str] = Field(default_factory=list)


class ResearchLabEvaluation(BaseModel):
    id: str
    name: str
    category: str
    status: RuntimeCapabilityStatus = "partial"
    metric: str = ""
    last_result: str = ""
    next_run_hint: str = ""
    controlled: bool = True


class MemoryDistillationSnapshot(BaseModel):
    generated_at: str
    raw_memory_records: int = 0
    distilled_themes: list[str] = Field(default_factory=list)
    archive_candidates: list[str] = Field(default_factory=list)
    compression_ratio_estimate: float = 0.0
    pruning_recommendations: list[str] = Field(default_factory=list)
    continuity_preserved: bool = True


class AegisContinuitySnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str = "2026.05.07"
    presence: AmbientPresenceState
    timeline: OperatingMemoryTimeline
    forecasts: SimulationForecastSnapshot
    cognitive: CognitiveAwarenessState
    hardware: HardwareAccelerationProfile
    workspace_state: PersistentWorkspaceState
    self_diagnostics: list[SelfDiagnosticSignal] = Field(default_factory=list)
    skill_packs: list[SkillPackInfo] = Field(default_factory=list)
    universal_data_sources: list[UniversalDataSource] = Field(default_factory=list)
    platform_sdk: list[PlatformSdkCapability] = Field(default_factory=list)
    digital_twin: DigitalTwinWorkspaceModel
    research_lab: list[ResearchLabEvaluation] = Field(default_factory=list)
    memory_distillation: MemoryDistillationSnapshot
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


PlatformDomainFocus = Literal["primary", "secondary", "experimental"]
PlatformFeatureStatus = Literal["production_ready", "beta", "experimental", "internal_only", "deprecated"]
PlatformStabilityTierName = Literal["stable_runtime", "experimental_runtime", "sandbox_features", "unsafe_research"]
PlatformLayerName = Literal["layer_1_core_runtime", "layer_2_task_memory_orchestration", "layer_3_domain_systems", "layer_4_intelligence_surfaces", "layer_5_ecosystem_distribution"]


class PlatformDomainStrategy(BaseModel):
    id: str
    name: str
    focus: PlatformDomainFocus
    rationale: str
    mastery_goal: str = ""
    success_metrics: list[str] = Field(default_factory=list)
    active_systems: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)


class PlatformRoadmapItem(BaseModel):
    id: str
    title: str
    category: Literal["mvp_workflow", "stable_core", "long_term", "experimental", "deprecated"] | str
    status: PlatformFeatureStatus
    domain: str = ""
    summary: str = ""
    owner_layer: PlatformLayerName | str = ""
    exit_criteria: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    complexity_cost: Literal["low", "medium", "high"] = "medium"
    ux_impact: Literal["positive", "neutral", "risky"] = "neutral"


class PlatformStabilityTier(BaseModel):
    id: PlatformStabilityTierName | str
    name: str
    description: str
    allowed_statuses: list[PlatformFeatureStatus] = Field(default_factory=list)
    entry_requirements: list[str] = Field(default_factory=list)
    release_rules: list[str] = Field(default_factory=list)
    user_visibility: Literal["default", "visible_with_label", "hidden_by_default", "blocked"] = "default"


class PlatformFeedbackLoop(BaseModel):
    id: str
    name: str
    status: RuntimeCapabilityStatus = "partial"
    signal: str = ""
    metric: str = ""
    source: str = ""
    cadence: str = ""
    improvement_rule: str = ""
    current_value: float | None = None
    target_value: float | None = None
    notes: list[str] = Field(default_factory=list)


class PlatformDesignStandard(BaseModel):
    id: str
    category: str
    rule: str
    rationale: str = ""
    applies_to: list[str] = Field(default_factory=list)
    enforcement: Literal["documented", "tested", "review_required", "blocked"] = "documented"


class PlatformBehaviorPrinciple(BaseModel):
    id: str
    principle: str
    do: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    enforcement: str = ""


class PlatformPerformanceBudget(BaseModel):
    id: str
    name: str
    category: str
    target: str
    warning_threshold: str = ""
    hard_limit: str = ""
    measurement: str = ""
    status: Literal["healthy", "watch", "unknown", "exceeded"] = "unknown"
    rationale: str = ""


class PlatformSecurityFoundation(BaseModel):
    id: str
    name: str
    status: RuntimeCapabilityStatus = "partial"
    policy: str
    enforcement_points: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class PlatformLayerDefinition(BaseModel):
    id: PlatformLayerName | str
    name: str
    responsibility: str
    systems: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)
    forbidden_dependencies: list[str] = Field(default_factory=list)
    stability_expectation: PlatformStabilityTierName | str = "stable_runtime"


class MaintainabilityPractice(BaseModel):
    id: str
    practice: str
    cadence: str = ""
    signal: str = ""
    expected_outcome: str = ""


class PlatformStewardshipPosture(BaseModel):
    id: str = "platform_stewardship"
    name: str = "Platform Stewardship"
    summary: str
    preserve: list[str] = Field(default_factory=list)
    improve: list[str] = Field(default_factory=list)
    reduce: list[str] = Field(default_factory=list)
    product_feel: list[str] = Field(default_factory=list)
    operating_rules: list[str] = Field(default_factory=list)
    success_metric: str = ""
    review_cadence: str = ""


class PlatformFeatureAdmissionCriterion(BaseModel):
    id: str
    question: str
    pass_requirement: str
    reject_when: str
    protects: list[str] = Field(default_factory=list)
    required: bool = True


class PlatformFeatureAdmissionPolicy(BaseModel):
    id: str = "feature_admission_gate"
    name: str = "Feature Admission Gate"
    default_decision: Literal["reject_when_unclear", "review_candidate", "allow"] = "reject_when_unclear"
    summary: str
    criteria: list[PlatformFeatureAdmissionCriterion] = Field(default_factory=list)
    hard_no_rules: list[str] = Field(default_factory=list)
    promotion_requirements: list[str] = Field(default_factory=list)
    review_cadence: str = ""


class PlatformDisciplineSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str = "2026.05.07"
    core_identity: str
    stewardship: PlatformStewardshipPosture
    feature_admission: PlatformFeatureAdmissionPolicy
    primary_domains: list[PlatformDomainStrategy] = Field(default_factory=list)
    secondary_domains: list[PlatformDomainStrategy] = Field(default_factory=list)
    experimental_domains: list[PlatformDomainStrategy] = Field(default_factory=list)
    roadmap: list[PlatformRoadmapItem] = Field(default_factory=list)
    stability_tiers: list[PlatformStabilityTier] = Field(default_factory=list)
    feedback_loops: list[PlatformFeedbackLoop] = Field(default_factory=list)
    design_standards: list[PlatformDesignStandard] = Field(default_factory=list)
    behavior_principles: list[PlatformBehaviorPrinciple] = Field(default_factory=list)
    performance_budgets: list[PlatformPerformanceBudget] = Field(default_factory=list)
    security_foundations: list[PlatformSecurityFoundation] = Field(default_factory=list)
    layers: list[PlatformLayerDefinition] = Field(default_factory=list)
    maintainability_practices: list[MaintainabilityPractice] = Field(default_factory=list)
    production_ready_count: int = 0
    beta_count: int = 0
    experimental_count: int = 0
    deprecated_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


class ProjectProfile(BaseModel):
    project_name: str = ""
    root_path: str = ""
    stack: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    lint_commands: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    main_entry_files: list[str] = Field(default_factory=list)
    important_folders: list[str] = Field(default_factory=list)
    generated_ignored_folders: list[str] = Field(default_factory=list)
    risk_sensitive_files: list[str] = Field(default_factory=list)
    coding_conventions: list[str] = Field(default_factory=list)
    last_indexed_at: str = ""


class ProjectArchitectureModule(BaseModel):
    name: str
    path: str
    kind: str = ""
    summary: str = ""


class ProjectApiRoute(BaseModel):
    method: str
    path: str
    file: str
    handler: str = ""


class ProjectDependencyEdge(BaseModel):
    source: str
    target: str
    kind: str = "dependency"


class ProjectArchitectureMap(BaseModel):
    frontend_backend_split: list[str] = Field(default_factory=list)
    major_modules: list[ProjectArchitectureModule] = Field(default_factory=list)
    api_routes: list[ProjectApiRoute] = Field(default_factory=list)
    database_storage_layer: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    build_system: list[str] = Field(default_factory=list)
    dependency_graph: list[ProjectDependencyEdge] = Field(default_factory=list)
    important_integration_points: list[str] = Field(default_factory=list)


class ProjectFileImportance(BaseModel):
    path: str
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    entry_point_importance: float = 0.0
    import_frequency: int = 0
    recent_edits: float = 0.0
    task_relevance: float = 0.0
    validation_failures: float = 0.0
    user_attention: float = 0.0
    architectural_centrality: float = 0.0


class ProjectIndexingStatus(BaseModel):
    status: Literal["not_indexed", "indexing", "ready", "failed"] = "not_indexed"
    last_indexed_at: str = ""
    file_count: int = 0
    ignored_folder_count: int = 0
    message: str = ""


class ProjectIntelligenceSnapshot(BaseModel):
    workspace_root: str
    profile: ProjectProfile = Field(default_factory=ProjectProfile)
    architecture: ProjectArchitectureMap = Field(default_factory=ProjectArchitectureMap)
    file_importance: list[ProjectFileImportance] = Field(default_factory=list)
    project_memory: list[ProjectMemoryEntry] = Field(default_factory=list)
    recent_tasks: list[TaskSummary] = Field(default_factory=list)
    recent_failures: list[TaskSummary] = Field(default_factory=list)
    known_todos: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    indexing: ProjectIndexingStatus = Field(default_factory=ProjectIndexingStatus)
    recommendations: list[str] = Field(default_factory=list)


class ProjectIntelligenceReindexRequest(BaseModel):
    workspace_root: str | None = None
    rebuild_architecture: bool = True
    rebuild_memory: bool = False
    clear_memory: bool = False


class ProjectContextSelectionRequest(BaseModel):
    workspace_root: str | None = None
    query: str = ""
    max_files: int = Field(default=12, ge=1, le=40)


class ProjectContextSelectionResponse(BaseModel):
    workspace_root: str
    selected_files: list[ProjectFileImportance] = Field(default_factory=list)
    architecture_notes: list[str] = Field(default_factory=list)
    project_memory: list[ProjectMemoryEntry] = Field(default_factory=list)
    previous_task_history: list[TaskSummary] = Field(default_factory=list)
    known_pitfalls: list[str] = Field(default_factory=list)
    validation_requirements: list[str] = Field(default_factory=list)
    coding_conventions: list[str] = Field(default_factory=list)


RecommendationSeverity = Literal["info", "low", "medium", "high", "critical"]
RecommendationStatus = Literal["active", "dismissed", "completed"]
WorkspaceEventSeverity = Literal["info", "low", "medium", "high", "critical"]
ScheduledJobStatus = Literal["idle", "running", "completed", "failed", "skipped"]


class WorkspaceFileState(BaseModel):
    path: str
    size: int = 0
    kind: str = ""
    modified_at: float = 0.0
    fingerprint: str = ""


class WorkspaceWatchEvent(BaseModel):
    id: str
    workspace_root: str
    created_at: str
    kind: str
    severity: WorkspaceEventSeverity = "info"
    title: str
    detail: str = ""
    path: str = ""
    related_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GitCommitSummary(BaseModel):
    sha: str = ""
    subject: str = ""
    author: str = ""
    created_at: str = ""


class GitFileChangeSummary(BaseModel):
    path: str
    status: str = ""
    additions: int = 0
    deletions: int = 0


class GitIntelligenceSummary(BaseModel):
    is_repository: bool = False
    branch: str = ""
    upstream: str = ""
    branch_count: int = 0
    branches: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    risky_diffs: list[GitFileChangeSummary] = Field(default_factory=list)
    change_heatmap: list[GitFileChangeSummary] = Field(default_factory=list)
    recent_commits: list[GitCommitSummary] = Field(default_factory=list)
    task_commit_links: list[str] = Field(default_factory=list)
    summary: str = ""


class WorkspaceWatcherSnapshot(BaseModel):
    workspace_root: str
    scanned_at: str
    file_count: int = 0
    fingerprint: str = ""
    dependency_fingerprint: str = ""
    file_states: list[WorkspaceFileState] = Field(default_factory=list)
    events: list[WorkspaceWatchEvent] = Field(default_factory=list)
    validation_drift: list[str] = Field(default_factory=list)
    git: GitIntelligenceSummary = Field(default_factory=GitIntelligenceSummary)


class ProjectHealthMetric(BaseModel):
    name: str
    status: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)


class ProjectHealthSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    score: int = Field(default=0, ge=0, le=100)
    status: Literal["healthy", "watch", "attention", "critical"] = "watch"
    metrics: list[ProjectHealthMetric] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)


class WorkspaceRecommendation(BaseModel):
    id: str
    workspace_root: str
    created_at: str
    updated_at: str
    dismissed_at: str = ""
    severity: RecommendationSeverity = "info"
    category: str = ""
    title: str
    detail: str = ""
    rationale: str = ""
    status: RecommendationStatus = "active"
    related_files: list[str] = Field(default_factory=list)
    related_tasks: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    fix_prompt: str = ""
    fix_task_id: str = ""


class ScheduledIntelligenceJob(BaseModel):
    id: str
    name: str
    kind: str
    schedule_label: str = ""
    enabled: bool = True
    safe_by_default: bool = True
    last_run_at: str = ""
    next_run_hint: str = ""
    status: ScheduledJobStatus = "idle"
    summary: str = ""


class WorkspaceOperationsSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    watcher: WorkspaceWatcherSnapshot
    health: ProjectHealthSnapshot
    recommendations: list[WorkspaceRecommendation] = Field(default_factory=list)
    scheduled_jobs: list[ScheduledIntelligenceJob] = Field(default_factory=list)
    git: GitIntelligenceSummary = Field(default_factory=GitIntelligenceSummary)
    long_term_memory: list[str] = Field(default_factory=list)
    recent_events: list[WorkspaceWatchEvent] = Field(default_factory=list)


class WorkspaceOperationsScanRequest(BaseModel):
    workspace_root: str | None = None
    refresh_project_intelligence: bool = True
    generate_recommendations: bool = True
    include_git: bool = True


class RecommendationActionRequest(BaseModel):
    reason: str = ""


class RecommendationFixRequest(BaseModel):
    reason: str = ""
    create_task: bool = True


class RecommendationFixResponse(BaseModel):
    recommendation: WorkspaceRecommendation
    task: TaskSummary | None = None
    event: ToolEvent | None = None
    message: str = ""


class ScheduledJobRunRequest(BaseModel):
    workspace_root: str | None = None
    job_ids: list[str] = Field(default_factory=list)
    allow_commands: bool = False


class ScheduledJobRunResponse(BaseModel):
    workspace_root: str
    jobs: list[ScheduledIntelligenceJob] = Field(default_factory=list)
    snapshot: WorkspaceOperationsSnapshot | None = None
    warnings: list[str] = Field(default_factory=list)


WorkerKind = Literal["local", "lan", "remote", "sandbox"]
WorkerStatus = Literal["available", "busy", "offline", "disabled", "untrusted", "revoked"]
WorkerTrustState = Literal["trusted", "untrusted", "revoked"]
ExecutionJobKind = Literal["task", "validation", "build", "indexing", "repair", "benchmark", "telemetry", "sync"]
ExecutionJobStatus = Literal["queued", "assigned", "running", "succeeded", "failed", "canceled", "retrying", "blocked"]
ExecutionMode = Literal["local", "remote", "hybrid", "sandbox"]
SandboxIsolationLevel = Literal["none", "process", "workspace_copy", "container", "remote"]


class WorkerCapabilitySet(BaseModel):
    installed_sdks: list[str] = Field(default_factory=list)
    build_tools: list[str] = Field(default_factory=list)
    supported_languages: list[str] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)
    gpu_available: bool = False
    ram_gb: float = 0.0
    cpu_cores: int = 0
    validation_support: bool = False
    sandbox_profiles: list[str] = Field(default_factory=list)
    supported_job_kinds: list[ExecutionJobKind | str] = Field(default_factory=list)
    supports_remote_sync: bool = False
    max_parallel_jobs: int = Field(default=1, ge=1, le=64)


class WorkerRuntimeInfo(BaseModel):
    worker_id: str
    name: str
    kind: WorkerKind = "local"
    endpoint: str = ""
    status: WorkerStatus = "available"
    trust_state: WorkerTrustState = "trusted"
    trust_scope: str = "local"
    registered_at: str = ""
    last_heartbeat_at: str = ""
    capabilities: WorkerCapabilitySet = Field(default_factory=WorkerCapabilitySet)
    current_jobs: int = 0
    total_jobs: int = 0
    failed_jobs: int = 0
    average_latency_ms: float = 0.0
    public_key_fingerprint: str = ""
    permission_scopes: list[str] = Field(default_factory=list)
    isolation_level: SandboxIsolationLevel = "process"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerRegistrationRequest(BaseModel):
    worker_id: str = ""
    name: str = ""
    kind: WorkerKind = "local"
    endpoint: str = ""
    capabilities: WorkerCapabilitySet = Field(default_factory=WorkerCapabilitySet)
    public_key: str = ""
    registration_signature: str = ""
    trust_scope: str = "local"
    permission_scopes: list[str] = Field(default_factory=list)
    isolation_level: SandboxIsolationLevel = "process"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerHeartbeatRequest(BaseModel):
    status: WorkerStatus = "available"
    current_jobs: int = Field(default=0, ge=0)
    capabilities: WorkerCapabilitySet | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerActionRequest(BaseModel):
    reason: str = ""


class ExecutionQueueItem(BaseModel):
    id: str
    task_id: str = ""
    workspace_root: str
    kind: ExecutionJobKind = "task"
    title: str = ""
    user_goal: str = ""
    status: ExecutionJobStatus = "queued"
    priority: int = 0
    created_at: str
    updated_at: str = ""
    assigned_worker_id: str = ""
    attempts: int = 0
    max_attempts: int = Field(default=3, ge=1, le=10)
    depends_on: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    permission_scope: str = "read"
    sandbox_profile: str = "safe"
    payload: dict[str, Any] = Field(default_factory=dict)
    error_summary: str = ""
    result_summary: str = ""
    lease_expires_at: str = ""


class ExecutionQueueCreateRequest(BaseModel):
    workspace_root: str | None = None
    task_id: str = ""
    kind: ExecutionJobKind = "task"
    title: str = ""
    user_goal: str = ""
    priority: int = 0
    max_attempts: int = Field(default=3, ge=1, le=10)
    depends_on: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    permission_scope: str = "read"
    sandbox_profile: str = "safe"
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionQueueActionRequest(BaseModel):
    reason: str = ""


class ExecutionDispatchRequest(BaseModel):
    workspace_root: str | None = None
    worker_id: str = ""
    limit: int = Field(default=1, ge=1, le=20)
    allow_commands: bool = False
    allow_remote: bool = False


class WorkerAuditEvent(BaseModel):
    id: str
    created_at: str
    worker_id: str = ""
    job_id: str = ""
    event_type: str
    status: str = "ok"
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionDispatchResponse(BaseModel):
    jobs: list[ExecutionQueueItem] = Field(default_factory=list)
    workers: list[WorkerRuntimeInfo] = Field(default_factory=list)
    events: list[WorkerAuditEvent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HybridRouteCandidate(BaseModel):
    provider_id: str = ""
    worker_id: str = ""
    model: str = ""
    location: Literal["local", "cloud", "remote", "offline"] = "local"
    privacy_mode: str = "local-first"
    estimated_latency_ms: int = 0
    estimated_cost_usd: float = 0.0
    reasoning_fit: float = Field(default=0.5, ge=0.0, le=1.0)
    selected: bool = False
    reason: str = ""


class HybridRouteRequest(BaseModel):
    workspace_root: str | None = None
    task_role: str = "code"
    privacy: Literal["local_only", "local_first", "hybrid", "cloud_allowed"] = "local_first"
    context_tokens: int = Field(default=0, ge=0)
    reasoning_difficulty: Literal["low", "medium", "high", "xhigh"] = "medium"
    latency_priority: Literal["low", "medium", "high"] = "medium"
    cost_priority: Literal["low", "medium", "high"] = "medium"
    workspace_sensitivity: Literal["low", "medium", "high"] = "medium"
    required_capabilities: list[str] = Field(default_factory=list)


class HybridRouteDecision(BaseModel):
    selected: HybridRouteCandidate | None = None
    candidates: list[HybridRouteCandidate] = Field(default_factory=list)
    fallback_order: list[str] = Field(default_factory=list)
    privacy_mode: str = "local-first"
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class RemoteWorkspaceSyncRequest(BaseModel):
    workspace_root: str | None = None
    sections: list[str] = Field(default_factory=list)
    encrypted: bool = True


class RemoteWorkspaceSyncManifest(BaseModel):
    id: str
    workspace_root: str
    created_at: str
    encrypted: bool = True
    encryption_label: str = "local-manifest-hash"
    included_sections: list[str] = Field(default_factory=list)
    manifest_hash: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RuntimeObservabilitySnapshot(BaseModel):
    generated_at: str
    workers_total: int = 0
    workers_available: int = 0
    workers_busy: int = 0
    workers_offline: int = 0
    workers_untrusted: int = 0
    queued_jobs: int = 0
    running_jobs: int = 0
    failed_jobs: int = 0
    succeeded_jobs: int = 0
    task_throughput: dict[str, int] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    model_latency_ms: dict[str, float] = Field(default_factory=dict)
    validation_success_rate: float = 0.0
    repair_loop_statistics: dict[str, int] = Field(default_factory=dict)
    queue_latency_ms: float = 0.0


class DistributedRuntimeSnapshot(BaseModel):
    generated_at: str
    execution_mode: ExecutionMode = "local"
    workers: list[WorkerRuntimeInfo] = Field(default_factory=list)
    queue: list[ExecutionQueueItem] = Field(default_factory=list)
    observability: RuntimeObservabilitySnapshot
    audit_events: list[WorkerAuditEvent] = Field(default_factory=list)
    routing: HybridRouteDecision | None = None
    sync_manifests: list[RemoteWorkspaceSyncManifest] = Field(default_factory=list)
    security_summary: list[str] = Field(default_factory=list)


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
    media_job: MediaJobResponse | None = None


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


AdaptiveTaskOutcomeStatus = Literal["success", "failed", "rolled_back", "canceled", "blocked", "unknown"]
AdaptivePolicyProfileId = Literal[
    "local_privacy_first",
    "balanced_hybrid",
    "maximum_reasoning",
    "fast_iterative",
    "low_cost",
    "autonomous_engineering",
    "safe_review_only",
]


class TaskOutcomeRecord(BaseModel):
    id: str = ""
    task_id: str = ""
    project_id: str = ""
    workspace_root: str = ""
    title: str = ""
    status: str = ""
    outcome: AdaptiveTaskOutcomeStatus = "unknown"
    success: bool = False
    repair_count: int = 0
    validation_runs: int = 0
    validation_passes: int = 0
    validation_failures: int = 0
    validation_pass_rate: float = 0.0
    retry_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0
    rollback_count: int = 0
    completion_time_seconds: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_used: str = ""
    provider_id: str = ""
    route_role: str = ""
    routing_path: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    error_summary: str = ""
    final_summary: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptiveQualityScore(BaseModel):
    dimension: str
    key: str = ""
    label: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_size: int = 0
    trend: Literal["improving", "stable", "declining", "unknown"] = "unknown"
    reasons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptiveRouteRecommendation(BaseModel):
    provider_id: str = ""
    provider_label: str = ""
    model: str = ""
    role: str = ""
    profile_id: str = ""
    action: Literal["prefer", "hold", "monitor", "deprioritize"] = "hold"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptiveInsight(BaseModel):
    id: str = ""
    category: str = ""
    key: str = ""
    title: str = ""
    detail: str = ""
    severity: Literal["info", "low", "medium", "high"] = "info"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    related_tasks: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntelligencePolicyProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    privacy_mode: str = "local-first"
    routing_strategy: str = "balanced"
    cost_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    latency_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    max_context_pressure: float = Field(default=0.8, ge=0.0, le=1.0)
    allow_cloud: bool = False
    allow_remote_workers: bool = False
    auto_apply_policy: bool = False
    review_required: bool = True
    active: bool = False
    created_at: str = ""
    updated_at: str = ""
    score_weights: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptivePolicyCheckpoint(BaseModel):
    id: str
    created_at: str
    reason: str = ""
    active_profile_id: str = ""
    profiles: list[IntelligencePolicyProfile] = Field(default_factory=list)


class AdaptiveBenchmarkReport(BaseModel):
    id: str
    workspace_root: str = ""
    created_at: str = ""
    suite_id: str = ""
    suite_label: str = ""
    status: Literal["passed", "regressed", "insufficient"] = "insufficient"
    baseline_score: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_score: float = Field(default=0.0, ge=0.0, le=1.0)
    regression_detected: bool = False
    reproducibility_key: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvaluationReplayResult(BaseModel):
    id: str
    workspace_root: str = ""
    created_at: str = ""
    source_task_id: str = ""
    status: Literal["matched", "improved", "regressed", "insufficient"] = "insufficient"
    previous_score: float = Field(default=0.0, ge=0.0, le=1.0)
    replay_score: float = Field(default=0.0, ge=0.0, le=1.0)
    regression_detected: bool = False
    previous_route: list[str] = Field(default_factory=list)
    replay_route: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptiveIntelligenceRefreshRequest(BaseModel):
    workspace_root: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    refresh_outcomes: bool = True


class AdaptivePolicyProfileUpdateRequest(BaseModel):
    profile: IntelligencePolicyProfile
    reason: str = "Policy profile updated by user."
    activate: bool = False


class AdaptivePolicyRollbackRequest(BaseModel):
    checkpoint_id: str
    reason: str = "Adaptive policy rollback requested."


class AdaptiveBenchmarkRunRequest(BaseModel):
    workspace_root: str | None = None
    suite_ids: list[str] = Field(default_factory=list)
    baseline_score: float | None = Field(default=None, ge=0.0, le=1.0)


class AdaptiveReplayRequest(BaseModel):
    workspace_root: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class AdaptiveIntelligenceSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    active_profile: IntelligencePolicyProfile
    profiles: list[IntelligencePolicyProfile] = Field(default_factory=list)
    outcomes: list[TaskOutcomeRecord] = Field(default_factory=list)
    quality_scores: list[AdaptiveQualityScore] = Field(default_factory=list)
    route_recommendations: list[AdaptiveRouteRecommendation] = Field(default_factory=list)
    repair_insights: list[AdaptiveInsight] = Field(default_factory=list)
    context_insights: list[AdaptiveInsight] = Field(default_factory=list)
    feedback_insights: list[AdaptiveInsight] = Field(default_factory=list)
    benchmark_reports: list[AdaptiveBenchmarkReport] = Field(default_factory=list)
    replay_results: list[EvaluationReplayResult] = Field(default_factory=list)
    policy_checkpoints: list[AdaptivePolicyCheckpoint] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


PluginCapabilityKind = Literal[
    "agent",
    "validator",
    "provider",
    "scaffold_template",
    "telemetry_processor",
    "workspace_analyzer",
    "ui_panel",
]
PluginPermissionScope = Literal[
    "read_workspace",
    "write_workspace",
    "run_validation",
    "run_commands",
    "network",
    "model_access",
    "telemetry",
    "ui_panel",
    "scaffold",
    "provider",
    "analyzer",
]
PluginLifecycleHookName = Literal["install", "enable", "disable", "validate", "uninstall"]


class StableApiContract(BaseModel):
    id: str
    name: str
    version: str
    status: Literal["stable", "beta", "internal", "deprecated"] = "stable"
    owner: str = "core"
    path_prefixes: list[str] = Field(default_factory=list)
    schema_refs: list[str] = Field(default_factory=list)
    compatibility_notes: list[str] = Field(default_factory=list)
    deprecation_policy: str = "No breaking changes without a versioned successor and migration note."


class PluginLifecycleHook(BaseModel):
    name: PluginLifecycleHookName
    command: str = ""
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    required_permissions: list[PluginPermissionScope] = Field(default_factory=list)


class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    api_version: str
    description: str = ""
    author: str = ""
    capabilities: list[PluginCapabilityKind] = Field(default_factory=list)
    permissions: list[PluginPermissionScope] = Field(default_factory=list)
    sandbox_profile: str = "isolated"
    signature: str = ""
    signing_key_fingerprint: str = ""
    lifecycle_hooks: list[PluginLifecycleHook] = Field(default_factory=list)
    entrypoint: str = ""
    ui_panel_route: str = ""
    enabled: bool = False
    trusted: bool = False
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("plugin id is required")
        if any(char in cleaned for char in "\\/: "):
            raise ValueError("plugin id must not contain spaces, slashes, or backslashes")
        return cleaned


class PluginRegistrationRequest(BaseModel):
    manifest: PluginManifest
    enable: bool = False
    trust: bool = False
    reason: str = ""


class PluginValidationRequest(BaseModel):
    manifest: PluginManifest
    require_signature: bool = False


class PluginActionRequest(BaseModel):
    reason: str = ""


class PluginValidationResult(BaseModel):
    valid: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    normalized_manifest: PluginManifest | None = None


class EnterprisePolicyProfile(BaseModel):
    id: str = "local_first_default"
    name: str = "Local-First Default"
    description: str = ""
    active: bool = True
    audit_trails: bool = True
    permission_profile: str = "guided"
    privacy_mode: Literal["local_first", "privacy_first", "balanced", "enterprise_locked", "shared_workspace"] = "local_first"
    encrypted_workspace_storage: bool = False
    provider_allowlist: list[str] = Field(default_factory=list)
    provider_blocklist: list[str] = Field(default_factory=list)
    network_allowlist: list[str] = Field(default_factory=list)
    network_blocklist: list[str] = Field(default_factory=list)
    enforce_local_models: bool = False
    allow_remote_workers: bool = False
    telemetry_retention_days: int = Field(default=30, ge=1, le=3650)
    plugin_signing_required: bool = False
    command_execution_default: Literal["deny", "approval_required", "allow_safe"] = "approval_required"
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnterprisePolicyUpdateRequest(BaseModel):
    profile: EnterprisePolicyProfile
    reason: str = ""


class RuntimeRecoverySnapshot(BaseModel):
    generated_at: str
    database_path: str
    database_ok: bool = True
    database_message: str = ""
    open_tasks: int = 0
    interrupted_tasks: list[TaskSummary] = Field(default_factory=list)
    recoverable_tasks: list[TaskSummary] = Field(default_factory=list)
    stale_workers: list[str] = Field(default_factory=list)
    queue_recovery_items: list[ExecutionQueueItem] = Field(default_factory=list)
    checkpoint_count: int = 0
    latest_checkpoint_id: str = ""
    safe_shutdown_ready: bool = True
    recommended_actions: list[str] = Field(default_factory=list)


class ReliabilityMetric(BaseModel):
    name: str
    value: float = 0.0
    unit: str = "count"
    status: Literal["healthy", "watch", "degraded", "unknown"] = "unknown"
    target: float | None = None
    detail: str = ""
    trend: Literal["improving", "stable", "declining", "unknown"] = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductizationRefreshRequest(BaseModel):
    workspace_root: str | None = None
    refresh_metrics: bool = True


class ProductizationSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str
    stable_apis: list[StableApiContract] = Field(default_factory=list)
    plugins: list[PluginManifest] = Field(default_factory=list)
    plugin_validation: list[PluginValidationResult] = Field(default_factory=list)
    enterprise_policy: EnterprisePolicyProfile
    recovery: RuntimeRecoverySnapshot
    metrics: list[ReliabilityMetric] = Field(default_factory=list)
    performance: dict[str, Any] = Field(default_factory=dict)
    scaling: dict[str, Any] = Field(default_factory=dict)
    packaging: dict[str, Any] = Field(default_factory=dict)
    docs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


EcosystemPackageKind = Literal[
    "agent",
    "validator",
    "scaffold_pack",
    "workflow",
    "routing_profile",
    "telemetry_analyzer",
    "workspace_intelligence_pack",
]
EcosystemUpdateChannel = Literal["stable", "beta", "nightly", "local"]
EcosystemTrustLevel = Literal["untrusted", "reviewed", "trusted", "organization", "signed"]
EcosystemWorkflowStepKind = Literal[
    "inspect",
    "plan",
    "agent",
    "edit",
    "review",
    "validate",
    "repair",
    "approval",
    "memory",
    "summarize",
]
SharedIntelligenceProfileKind = Literal[
    "routing_strategy",
    "validation_profile",
    "repair_heuristics",
    "project_memory_pack",
    "architecture_pattern",
    "benchmark_profile",
]
KnowledgeGraphNodeKind = Literal[
    "project",
    "module",
    "file",
    "api",
    "dependency",
    "decision",
    "failure",
    "task",
    "workflow",
    "package",
]
KnowledgeGraphEdgeKind = Literal[
    "contains",
    "depends_on",
    "exposes",
    "implements",
    "references",
    "failed_in",
    "decided",
    "uses",
    "related_to",
]


class EcosystemPackageManifest(BaseModel):
    id: str
    name: str
    kind: EcosystemPackageKind
    version: str
    api_version: str
    description: str = ""
    author: str = ""
    compatibility: dict[str, Any] = Field(default_factory=dict)
    trust_level: EcosystemTrustLevel = "untrusted"
    sandbox_permissions: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    update_channel: EcosystemUpdateChannel = "stable"
    signature: str = ""
    signing_key_fingerprint: str = ""
    checksum: str = ""
    entrypoint: str = ""
    homepage: str = ""
    enabled: bool = False
    installed: bool = False
    installed_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ecosystem package id is required")
        if any(char in cleaned for char in "\\/: "):
            raise ValueError("ecosystem package id must not contain spaces, slashes, or backslashes")
        return cleaned


class EcosystemPackageValidationResult(BaseModel):
    valid: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trust_score: float = Field(default=0.0, ge=0.0, le=1.0)
    normalized_manifest: EcosystemPackageManifest | None = None


class EcosystemPackageRegistrationRequest(BaseModel):
    manifest: EcosystemPackageManifest
    enable: bool = False
    trust_level: EcosystemTrustLevel | None = None
    reason: str = ""


class EcosystemPackageValidationRequest(BaseModel):
    manifest: EcosystemPackageManifest
    require_signature: bool = False


class EcosystemPackageActionRequest(BaseModel):
    reason: str = ""
    trust_level: EcosystemTrustLevel | None = None


class WorkflowApprovalRequirement(BaseModel):
    id: str
    title: str
    reason: str = ""
    required_before_step: str = ""
    permission_scope: str = "write_workspace"


class WorkflowStepDefinition(BaseModel):
    id: str
    title: str
    kind: EcosystemWorkflowStepKind
    agent_role: str = ""
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    approval_required: bool = False
    max_attempts: int = Field(default=1, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcosystemWorkflowDefinition(BaseModel):
    id: str
    name: str
    version: str
    api_version: str
    category: str = "general"
    description: str = ""
    steps: list[WorkflowStepDefinition] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    approvals: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    package_dependencies: list[str] = Field(default_factory=list)
    signed: bool = False
    signature: str = ""
    trust_level: EcosystemTrustLevel = "reviewed"
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("workflow id is required")
        if any(char in cleaned for char in "\\/: "):
            raise ValueError("workflow id must not contain spaces, slashes, or backslashes")
        return cleaned


class WorkflowRunRequest(BaseModel):
    workspace_root: str | None = None
    user_goal: str = ""
    priority: int = 0
    start_immediately: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    workflow: EcosystemWorkflowDefinition
    task: TaskSummary
    subtasks: list[TaskSummary] = Field(default_factory=list)
    events: list[ToolEvent] = Field(default_factory=list)
    message: str = ""


class SharedIntelligenceProfile(BaseModel):
    id: str
    name: str
    kind: SharedIntelligenceProfileKind
    version: str = "1.0.0"
    description: str = ""
    source: str = "local"
    exported_at: str = ""
    imported_at: str = ""
    trust_level: EcosystemTrustLevel = "reviewed"
    payload: dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""
    signature: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SharedIntelligenceProfileImportRequest(BaseModel):
    profile: SharedIntelligenceProfile
    reason: str = ""


class SharedIntelligenceProfileExportResponse(BaseModel):
    profile: SharedIntelligenceProfile
    export_format: str = "aegis.shared-intelligence+json"
    checksum: str = ""


class TeamCollaborationSummary(BaseModel):
    mode: Literal["local", "shared", "organization"] = "local"
    shared_task_count: int = 0
    shared_checkpoint_count: int = 0
    shared_architecture_notes: int = 0
    pending_approvals: int = 0
    collaborators: list[str] = Field(default_factory=list)
    telemetry_dashboards: list[str] = Field(default_factory=list)
    status: Literal["ready", "limited", "disabled"] = "disabled"
    notes: list[str] = Field(default_factory=list)


class OrganizationPolicyProfile(BaseModel):
    id: str = "local_organization_policy"
    name: str = "Local Organization Policy"
    active: bool = True
    provider_policies: dict[str, Any] = Field(default_factory=dict)
    privacy_policies: dict[str, Any] = Field(default_factory=dict)
    approval_requirements: dict[str, Any] = Field(default_factory=dict)
    validation_standards: dict[str, Any] = Field(default_factory=dict)
    package_restrictions: dict[str, Any] = Field(default_factory=dict)
    audit_requirements: dict[str, Any] = Field(default_factory=dict)
    require_signed_packages: bool = False
    allow_community_packages: bool = True
    collaboration_mode: Literal["local", "shared", "organization"] = "local"
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrganizationPolicyUpdateRequest(BaseModel):
    profile: OrganizationPolicyProfile
    reason: str = ""


class KnowledgeGraphNode(BaseModel):
    id: str
    kind: KnowledgeGraphNodeKind
    label: str
    path: str = ""
    summary: str = ""
    importance: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    kind: KnowledgeGraphEdgeKind
    weight: float = 1.0
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    nodes: list[KnowledgeGraphNode] = Field(default_factory=list)
    edges: list[KnowledgeGraphEdge] = Field(default_factory=list)
    modules_total: int = 0
    api_routes_total: int = 0
    dependencies_total: int = 0
    decisions_total: int = 0
    recurring_failures_total: int = 0
    recommendations: list[str] = Field(default_factory=list)


class CrossProjectInsight(BaseModel):
    id: str
    title: str
    category: Literal["reuse", "duplicate", "recurring_bug", "architecture_pattern", "organization_issue"] = "reuse"
    severity: Literal["low", "medium", "high"] = "low"
    projects: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    detail: str = ""
    recommendation: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class EcosystemSearchRequest(BaseModel):
    workspace_root: str | None = None
    query: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class EcosystemSearchResult(BaseModel):
    id: str
    kind: str
    title: str
    detail: str = ""
    reference: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcosystemSearchResponse(BaseModel):
    query: str
    generated_at: str
    results: list[EcosystemSearchResult] = Field(default_factory=list)
    scope_summary: dict[str, int] = Field(default_factory=dict)
    reconstruction: list[ToolEvent] = Field(default_factory=list)


class ReproducibilityArtifact(BaseModel):
    kind: Literal["task", "validation", "repair", "routing", "checkpoint", "timeline", "context"] = "task"
    reference: str = ""
    checksum: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ReproducibilityRecord(BaseModel):
    id: str
    workspace_root: str
    task_id: str = ""
    created_at: str
    deterministic_hash: str
    status: Literal["ready", "partial", "missing_task"] = "ready"
    artifacts: list[ReproducibilityArtifact] = Field(default_factory=list)
    replay_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReproducibilityRequest(BaseModel):
    workspace_root: str | None = None
    task_id: str = ""
    include_timeline: bool = True


class EcosystemAuditEvent(BaseModel):
    id: str
    created_at: str
    actor: str = "local-user"
    action: str
    subject_id: str = ""
    status: Literal["ok", "warning", "error"] = "ok"
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceTrustSignal(BaseModel):
    id: str
    label: str
    status: Literal["trusted", "review", "blocked"] = "review"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    detail: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class EcosystemRefreshRequest(BaseModel):
    workspace_root: str | None = None
    rebuild_graph: bool = True
    include_search_query: str = ""


class EcosystemSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str
    marketplace_catalog: list[EcosystemPackageManifest] = Field(default_factory=list)
    packages: list[EcosystemPackageManifest] = Field(default_factory=list)
    package_validation: list[EcosystemPackageValidationResult] = Field(default_factory=list)
    workflows: list[EcosystemWorkflowDefinition] = Field(default_factory=list)
    shared_profiles: list[SharedIntelligenceProfile] = Field(default_factory=list)
    team: TeamCollaborationSummary = Field(default_factory=TeamCollaborationSummary)
    organization_policy: OrganizationPolicyProfile = Field(default_factory=OrganizationPolicyProfile)
    knowledge_graph: KnowledgeGraphSnapshot
    cross_project_insights: list[CrossProjectInsight] = Field(default_factory=list)
    search: EcosystemSearchResponse | None = None
    reproducibility: list[ReproducibilityRecord] = Field(default_factory=list)
    governance: list[GovernanceTrustSignal] = Field(default_factory=list)
    audit_events: list[EcosystemAuditEvent] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


AutonomousObjectiveStatus = Literal[
    "simulating",
    "queued",
    "discovery",
    "planning",
    "running",
    "needs_approval",
    "validating",
    "repairing",
    "reviewing",
    "optimizing",
    "finalizing",
    "completed",
    "failed",
    "canceled",
    "paused",
]
AutonomousPhaseKind = Literal["discovery", "planning", "implementation", "validation", "review", "optimization", "finalization"]
AutonomousPhaseStatus = Literal["queued", "running", "needs_approval", "completed", "failed", "skipped", "paused"]
AutonomousApprovalKind = Literal[
    "large_file_change",
    "dependency_change",
    "architecture_change",
    "destructive_action",
    "production_impact",
    "protected_file",
    "command_execution",
]
AutonomousApprovalStatus = Literal["pending", "approved", "rejected", "canceled"]
AutonomousAgentRole = Literal["planner", "architect", "code", "review", "validation", "repair", "memory", "documentation", "performance", "security"]


class AutonomousSafetyLimits(BaseModel):
    max_iterations: int = Field(default=5, ge=1, le=50)
    max_parallel_agents: int = Field(default=4, ge=1, le=12)
    token_budget: int = Field(default=120000, ge=1000, le=5000000)
    max_file_changes: int = Field(default=25, ge=0, le=10000)
    max_dependency_changes: int = Field(default=3, ge=0, le=200)
    max_repair_attempts: int = Field(default=2, ge=0, le=10)
    approval_checkpoint_interval: int = Field(default=1, ge=1, le=20)
    rollback_required: bool = True
    protected_file_zones: list[str] = Field(default_factory=lambda: [".env", "secrets", "production", "deploy", "infra"])
    stop_on_validation_failure: bool = True
    allow_dependency_changes: bool = False
    allow_destructive_actions: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousGoalMemory(BaseModel):
    objective_history: list[str] = Field(default_factory=list)
    completed_phases: list[str] = Field(default_factory=list)
    failed_approaches: list[str] = Field(default_factory=list)
    successful_patterns: list[str] = Field(default_factory=list)
    remaining_work: list[str] = Field(default_factory=list)
    user_preferences: list[str] = Field(default_factory=list)
    updated_at: str = ""


class AutonomousObjective(BaseModel):
    id: str
    workspace_root: str
    title: str
    user_goal: str
    status: AutonomousObjectiveStatus = "queued"
    priority: int = 0
    created_at: str
    updated_at: str
    completed_at: str = ""
    current_phase: AutonomousPhaseKind = "discovery"
    iteration_count: int = 0
    repair_count: int = 0
    assigned_agent_roles: list[AutonomousAgentRole] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    phase_ids: list[str] = Field(default_factory=list)
    approval_gate_ids: list[str] = Field(default_factory=list)
    simulation_ids: list[str] = Field(default_factory=list)
    safety_limits: AutonomousSafetyLimits = Field(default_factory=AutonomousSafetyLimits)
    goal_memory: AutonomousGoalMemory = Field(default_factory=AutonomousGoalMemory)
    final_summary: str = ""
    error_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousPhase(BaseModel):
    id: str
    objective_id: str
    workspace_root: str
    kind: AutonomousPhaseKind
    title: str
    status: AutonomousPhaseStatus = "queued"
    summary: str = ""
    started_at: str = ""
    completed_at: str = ""
    task_ids: list[str] = Field(default_factory=list)
    agent_roles: list[AutonomousAgentRole] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    approval_required: bool = False
    iteration_count: int = 0
    error_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousApprovalGate(BaseModel):
    id: str
    objective_id: str
    phase_id: str = ""
    kind: AutonomousApprovalKind
    title: str
    reason: str
    status: AutonomousApprovalStatus = "pending"
    required: bool = True
    created_at: str
    resolved_at: str = ""
    resolved_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousAgentAssignment(BaseModel):
    id: str
    objective_id: str
    phase_id: str = ""
    role: AutonomousAgentRole
    status: Literal["queued", "running", "completed", "failed", "blocked"] = "queued"
    task_id: str = ""
    summary: str = ""
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousVerificationSignal(BaseModel):
    id: str
    objective_id: str
    phase_id: str = ""
    kind: Literal["build", "test", "lint", "architecture", "policy", "security", "performance"] = "test"
    command: str = ""
    status: Literal["queued", "passed", "failed", "skipped", "warning"] = "queued"
    detail: str = ""
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousSimulationEstimate(BaseModel):
    id: str
    objective_id: str
    workspace_root: str
    created_at: str
    estimated_impact: Literal["low", "medium", "high", "very_high"] = "medium"
    predicted_validation_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    projected_file_changes: list[str] = Field(default_factory=list)
    projected_dependency_changes: list[str] = Field(default_factory=list)
    projected_token_cost: int = 0
    projected_iterations: int = 1
    dry_run_plan: list[str] = Field(default_factory=list)
    approval_gates: list[AutonomousApprovalGate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousRefactorPlan(BaseModel):
    id: str
    objective_id: str
    kind: Literal["import_migration", "api_migration", "architecture_reorg", "naming_normalization", "dependency_upgrade", "ui_modernization", "test_coverage"] = "architecture_reorg"
    title: str
    target_patterns: list[str] = Field(default_factory=list)
    projected_files: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    approval_required: bool = True
    status: Literal["draft", "approved", "running", "completed", "blocked"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousExplainabilityEntry(BaseModel):
    id: str
    objective_id: str
    created_at: str
    category: Literal["planning", "routing", "change", "repair", "validation", "policy", "approval", "simulation"] = "planning"
    title: str
    detail: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class AutonomousAnalyticsMetric(BaseModel):
    name: str
    value: float = 0.0
    unit: str = "count"
    status: Literal["healthy", "watch", "degraded", "unknown"] = "unknown"
    detail: str = ""
    trend: Literal["improving", "stable", "declining", "unknown"] = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousObjectiveCreateRequest(BaseModel):
    workspace_root: str | None = None
    title: str = Field(min_length=1)
    user_goal: str = Field(min_length=1)
    priority: int = 0
    dry_run: bool = True
    max_iterations: int = Field(default=5, ge=1, le=50)
    token_budget: int = Field(default=120000, ge=1000, le=5000000)
    max_parallel_agents: int = Field(default=4, ge=1, le=12)
    protected_file_zones: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousObjectiveActionRequest(BaseModel):
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousObjectiveIterationRequest(BaseModel):
    reason: str = ""
    max_steps: int = Field(default=1, ge=1, le=10)
    allow_repairs: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousApprovalActionRequest(BaseModel):
    reason: str = ""
    resolved_by: str = "local-user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutonomousObjectiveDetail(BaseModel):
    objective: AutonomousObjective
    phases: list[AutonomousPhase] = Field(default_factory=list)
    approval_gates: list[AutonomousApprovalGate] = Field(default_factory=list)
    simulations: list[AutonomousSimulationEstimate] = Field(default_factory=list)
    agents: list[AutonomousAgentAssignment] = Field(default_factory=list)
    verification: list[AutonomousVerificationSignal] = Field(default_factory=list)
    refactor_plans: list[AutonomousRefactorPlan] = Field(default_factory=list)
    explanations: list[AutonomousExplainabilityEntry] = Field(default_factory=list)
    task_events: list[ToolEvent] = Field(default_factory=list)


class AutonomousEngineeringSnapshot(BaseModel):
    workspace_root: str
    generated_at: str
    api_version: str
    objectives: list[AutonomousObjective] = Field(default_factory=list)
    active_objectives: list[AutonomousObjective] = Field(default_factory=list)
    phases: list[AutonomousPhase] = Field(default_factory=list)
    approval_gates: list[AutonomousApprovalGate] = Field(default_factory=list)
    simulations: list[AutonomousSimulationEstimate] = Field(default_factory=list)
    agents: list[AutonomousAgentAssignment] = Field(default_factory=list)
    verification: list[AutonomousVerificationSignal] = Field(default_factory=list)
    refactor_plans: list[AutonomousRefactorPlan] = Field(default_factory=list)
    explanations: list[AutonomousExplainabilityEntry] = Field(default_factory=list)
    analytics: list[AutonomousAnalyticsMetric] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeHealthResponse(BaseModel):
    ok: bool = True
    ready: bool = True
    status: Literal["ready", "degraded"] = "ready"
    app: str = "Auralith OS"
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
    id: str = ""
    path: str
    kind: str
    format: str
    role: str
    mime_type: str = ""
    editable: bool = False
    derived_from: str = ""
    thumbnail_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaProviderInfo(BaseModel):
    id: str
    name: str
    category: str
    location: Literal["local", "cloud", "adapter"] | str = "local"
    supports: list[MediaKind] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=list)
    paid: bool = False
    gpu_intensive: bool = False
    requires_approval: bool = False
    available: bool = True
    notes: str = ""


class MediaPromptPreset(BaseModel):
    id: str
    name: str
    studio: str
    kind: MediaKind
    prompt_template: str
    negative_prompt: str = ""
    default_settings: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class MediaCapabilitiesResponse(BaseModel):
    supported_kinds: list[MediaKind] = Field(default_factory=list)
    local_formats: list[str] = Field(default_factory=list)
    provider_formats: list[str] = Field(default_factory=list)
    providers: list[MediaProviderInfo] = Field(default_factory=list)
    prompt_presets: list[MediaPromptPreset] = Field(default_factory=list)
    can_iterate_from_previous: bool = True
    theme_inference: bool = True
    psd_template_strategy: str
    local_renderers: dict[str, bool] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class MediaCreativeRequest(BaseModel):
    prompt: str = Field(min_length=1)
    kind: MediaKind = "image"
    studio: str = "image"
    operation: str = "generate"
    provider_id: str = "local_creative_renderer"
    feedback: str = ""
    previous_job_id: str = ""
    source_asset_id: str = ""
    theme_color: str = ""
    aspect_ratio: str = "16:9"
    style: str = ""
    negative_prompt: str = ""
    duration_seconds: float = Field(default=4.0, ge=0.5, le=120.0)
    fps: int = Field(default=12, ge=1, le=60)
    width: int = Field(default=1280, ge=256, le=4096)
    height: int = Field(default=720, ge=256, le=4096)
    seed: int | None = None
    bpm: int | None = Field(default=None, ge=40, le=240)
    key: str = ""
    genre: str = ""
    voice: str = ""
    paid_approved: bool = False
    gpu_approved: bool = False
    copyright_style_approved: bool = False
    voice_clone_approved: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)
    output_formats: list[str] = Field(default_factory=list)


class MediaJobResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str = ""
    completed_at: str = ""
    kind: MediaKind
    studio: str = "image"
    operation: str = "generate"
    status: MediaJobStatus | str
    provider_id: str = ""
    provider_name: str = ""
    prompt: str
    effective_prompt: str = ""
    negative_prompt: str = ""
    feedback: str = ""
    previous_job_id: str = ""
    source_asset_id: str = ""
    theme_color: str
    palette: list[str] = Field(default_factory=list)
    aspect_ratio: str
    style: str = ""
    seed: int | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    output_path: str = ""
    cost_estimate_usd: float = 0.0
    time_taken_seconds: float = 0.0
    error: str = ""
    timeline: list[ToolEvent] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    assets: list[MediaAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    job_dir: str


class MediaAssetLibraryResponse(BaseModel):
    generated_at: str
    base_dir: str
    jobs: list[MediaJobResponse] = Field(default_factory=list)
    assets: list[MediaAsset] = Field(default_factory=list)
    total_assets: int = 0
    formats: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)


class MediaExportRequest(BaseModel):
    format: Literal["png", "jpg", "svg", "mp4", "wav", "mp3", "midi", "zip"] | str = "zip"
    asset_ids: list[str] = Field(default_factory=list)
    include_metadata: bool = True


class MediaExportResponse(BaseModel):
    id: str
    created_at: str
    job_id: str
    format: str
    path: str
    assets: list[MediaAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
