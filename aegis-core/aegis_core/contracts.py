from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeVar

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:  # pragma: no cover - import guard mirrors server dependency checks.
    from pydantic import BaseModel, Field  # type: ignore[no-redef]

    ConfigDict = None  # type: ignore[assignment]


CORE_API_VERSION = "v1"
CORE_CONTRACT_VERSION = "2026.05.09"

ContractStability = Literal["stable", "experimental", "deprecated"]


class ContractModel(BaseModel):
    """Base model for backwards-compatible Core contracts.

    Core contracts allow extra fields so older clients keep parsing newer
    responses and newer clients can tolerate older optional-field omissions.
    """

    if ConfigDict is not None:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"


class WorkspaceRequest(ContractModel):
    workspace: str


class ContinueRequest(ContractModel):
    workspace: str
    request: str | None = None


class ValidateRequest(ContractModel):
    workspace: str
    run: bool = False
    command: list[str] | None = None


class SettingsRequest(ContractModel):
    workspace: str
    settings: dict[str, Any] = Field(default_factory=dict)


class ModelRouteRequest(ContractModel):
    workspace: str
    task_type: str = "chat"
    difficulty: str | None = None
    allow_cloud: bool = False
    cloud_approved: bool = False
    context_files: list[str] = Field(default_factory=list)
    local_failure_reason: str | None = None
    provider_id: str | None = None
    model: str | None = None


class ModelCompletionRequest(ModelRouteRequest):
    prompt: str
    timeout_seconds: int = 120


class ProviderKeyRequest(ContractModel):
    api_key: str


class ClientRegistrationRequest(ContractModel):
    workspace: str
    client_id: str
    client_type: str
    name: str
    version: str = "unknown"
    capabilities: list[str] | None = None


class CreateTaskRequest(ContractModel):
    workspace: str
    title: str
    kind: str = "general"
    source_client: str = "unknown"
    request: str | None = None
    metadata: dict[str, Any] | None = None


class TaskStatusRequest(ContractModel):
    workspace: str
    status: str
    summary: str | None = None


class OrchestrationPlanRequest(ContractModel):
    workspace: str
    goal: str
    source_client: str = "unknown"
    context_files: list[str] = Field(default_factory=list)


class OrchestrationStepRequest(ContractModel):
    workspace: str
    task_id: str | None = None
    action: str = "inspect"
    approval: bool = False
    summary: str | None = None
    affected_files: list[str] = Field(default_factory=list)
    validation_command: list[str] | None = None


class JobRunRequest(ContractModel):
    workspace: str
    job_id: str | None = None
    trigger: str | None = None
    approval: bool = False
    run_due: bool = False


class KnowledgeQueryRequest(ContractModel):
    workspace: str
    query: str
    focus: str | None = None


class SimulationRequest(ContractModel):
    workspace: str
    objective: str
    files: list[str] = Field(default_factory=list)
    approach: str | None = None


class SimulationCompareRequest(ContractModel):
    workspace: str
    objective: str
    approaches: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class OperationsRequest(ContractModel):
    workspace: str
    project_roots: list[str] = Field(default_factory=list)


class PersonalIntelligenceRequest(ContractModel):
    workspace: str
    project_roots: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    persist: bool = False


class CoreEnvelope(ContractModel):
    ok: bool = True
    api_version: Literal["v1"] = CORE_API_VERSION
    contract_version: str = CORE_CONTRACT_VERSION
    kind: str
    workspace: str | None = None
    data: Any = Field(default_factory=dict)
    stability: ContractStability = "stable"
    deprecated: bool = False
    deprecations: list[str] = Field(default_factory=list)


class HealthData(ContractModel):
    ok: bool = True
    workspace: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    ollama: dict[str, Any] = Field(default_factory=dict)


class ModelsData(ContractModel):
    reachable: bool = False
    latency_ms: int | None = None
    installed_models: list[str] = Field(default_factory=list)
    selected_model: str | None = None
    missing_models: list[str] = Field(default_factory=list)
    error: str | None = None


class SettingsData(ContractModel):
    ollama_url: str | None = None
    lm_studio_url: str | None = None
    default_model: str | None = None
    default_local_model: str | None = None
    local_small_model: str | None = None
    local_coder_model: str | None = None
    local_embedding_model: str | None = None
    preferred_cloud_provider: str | None = None
    preferred_cloud_model: str | None = None
    model_routing_mode: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    max_context_chars: int | None = None
    cloud_cost_warnings: bool | None = None
    safety_mode: str | None = None
    auto_scan_on_open: bool | None = None
    validation_preferences: list[str] = Field(default_factory=list)
    memory_dir_name: str | None = None


class ProviderData(ContractModel):
    id: str
    label: str = ""
    api: str = ""
    local: bool = True
    endpoint: str = ""
    default_model: str = ""
    configured: bool = False
    enabled: bool = True
    requires_key: bool = False
    key_stored: bool = False
    supports_chat: bool = True
    supports_embeddings: bool = False
    cost_warning: str | None = None


class ProviderInventoryData(ContractModel):
    mode: str = "local_only"
    local_only: bool = True
    credential_store_available: bool = False
    credential_store_healthy: bool = True
    credential_store_errors: list[dict[str, str]] = Field(default_factory=list)
    providers: list[ProviderData] = Field(default_factory=list)


class ProviderKeyStatusData(ContractModel):
    provider_id: str
    key_stored: bool | None = None
    removed: bool | None = None
    credential_store: str = "os"


class ModelRouteCandidateData(ContractModel):
    provider_id: str
    provider_label: str = ""
    api: str = ""
    local: bool = True
    model: str = ""
    status: str = "available"
    reason: str = ""
    cost_warning: str | None = None


class ModelRouteContextData(ContractModel):
    max_context_chars: int = 0
    included_files: list[str] = Field(default_factory=list)
    blocked_files: list[dict[str, str]] = Field(default_factory=list)
    included: list[dict[str, str]] = Field(default_factory=list)


class ModelRouteData(ContractModel):
    workspace: str | None = None
    task_type: str = "chat"
    difficulty: str = "simple"
    mode: str = "local_only"
    local_only: bool = True
    selected: ModelRouteCandidateData | dict[str, Any] = Field(default_factory=dict)
    fallback_order: list[ModelRouteCandidateData | dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    cloud_ready: bool = False
    cloud_reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    context: ModelRouteContextData | dict[str, Any] = Field(default_factory=dict)
    credential_store_healthy: bool = True
    credential_store_errors: list[dict[str, str]] = Field(default_factory=list)
    ollama: ModelsData | dict[str, Any] = Field(default_factory=dict)
    providers: list[ProviderData | dict[str, Any]] = Field(default_factory=list)


class ModelCompletionData(ContractModel):
    workspace: str | None = None
    provider_id: str = ""
    model: str = ""
    local: bool = True
    latency_ms: int | None = None
    response: str = ""
    route: ModelRouteData | dict[str, Any] = Field(default_factory=dict)


class WorkspaceScanData(ContractModel):
    workspace: str | None = None
    workspace_name: str | None = None
    frameworks: list[str] = Field(default_factory=list)
    languages: dict[str, int] = Field(default_factory=dict)
    file_count: int | None = None
    build_files: list[str] = Field(default_factory=list)
    readmes: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    todo_comments: list[dict[str, Any]] = Field(default_factory=list)
    recent_files: list[str] = Field(default_factory=list)
    ignored_dirs: list[str] = Field(default_factory=list)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    symbol_index: dict[str, Any] = Field(default_factory=dict)
    scan_fingerprint: dict[str, Any] = Field(default_factory=dict)
    cache_hit: bool = False
    cache_reason: str | None = None


class RoadmapData(ContractModel):
    workspace: str | None = None
    roadmap_path: str | None = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    markdown: str = ""


class MemoryEntryData(ContractModel):
    path: str | None = None
    exists: bool = False
    excerpt: str = ""


class MemorySummaryData(ContractModel):
    workspace: str | None = None
    memory_dir: str | None = None
    entries: dict[str, MemoryEntryData] = Field(default_factory=dict)


class DiagnosticLogData(ContractModel):
    path: str | None = None
    exists: bool = False
    tail: str = ""


class DiagnosticsSummaryData(ContractModel):
    workspace: str | None = None
    logs: dict[str, DiagnosticLogData] = Field(default_factory=dict)


class BrandingData(ContractModel):
    pass


class ClientData(ContractModel):
    client_id: str
    client_type: str = "unknown"
    name: str = "Unknown Client"
    version: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)
    last_seen: str = ""


class TaskData(ContractModel):
    id: str
    title: str = "Untitled task"
    kind: str = "general"
    source_client: str = "unknown"
    status: str = "planned"
    created_at: str = ""
    updated_at: str = ""
    request: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationCommandData(ContractModel):
    name: str = ""
    command: list[str] = Field(default_factory=list)
    reason: str = ""


class ValidationData(ContractModel):
    workspace: str | None = None
    commands: list[ValidationCommandData] = Field(default_factory=list)
    ok: bool | None = None
    command: list[str] | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    blocked: bool | None = None
    start_failed: bool | None = None
    timed_out: bool | None = None
    validation_log: dict[str, Any] = Field(default_factory=dict)
    memory_warning: str | None = None


class AgentPlanData(ContractModel):
    task: str | None = None
    request: str | None = None
    risk: str | None = None
    approval_required: bool = True
    mode: str | None = None
    steps: list[str] = Field(default_factory=list)
    likely_context: Any = Field(default_factory=list)
    validation: Any = Field(default_factory=list)
    ok: bool | None = None
    message: str | None = None
    summary: str | None = None
    latest_validation_excerpt: str | None = None
    repair_attempt_limit: int | None = None


class AgentTaskEnvelopeData(ContractModel):
    plan: AgentPlanData
    task: TaskData | None = None
    memory_warning: str | None = None


class SpecializedAgentData(ContractModel):
    id: str
    label: str = ""
    purpose: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    approval_gates: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class AgentRosterData(ContractModel):
    agents: list[SpecializedAgentData] = Field(default_factory=list)
    coordination_rules: list[str] = Field(default_factory=list)
    approval_required_for: list[str] = Field(default_factory=list)


class OrchestrationApprovalGateData(ContractModel):
    id: str
    label: str = ""


class OrchestrationTaskData(ContractModel):
    id: str
    title: str = "Untitled orchestration task"
    status: str = "pending"
    active_step: str = "pending"
    order: int | None = None
    step: str | None = None
    detail: str = ""
    objective: str = ""
    risk: str = "unknown"
    owner_agent: str = ""
    owner_agent_label: str = ""
    agent: SpecializedAgentData | dict[str, Any] = Field(default_factory=dict)
    affected_systems: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    approval_required: bool = False
    approval_gates: list[OrchestrationApprovalGateData | dict[str, Any]] = Field(default_factory=list)
    validation_commands: list[ValidationCommandData | dict[str, Any]] = Field(default_factory=list)
    latest_validation: ValidationData | dict[str, Any] = Field(default_factory=dict)
    repair_attempt_limit: int | None = None
    created_at: str = ""
    updated_at: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)


class OrchestrationPlanData(ContractModel):
    id: str | None = None
    workspace: str | None = None
    objective: str | None = None
    status: str = "in_progress"
    risk: str = "unknown"
    quality: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)
    simulation: dict[str, Any] = Field(default_factory=dict)
    planner_guidance: list[str] = Field(default_factory=list)
    source_client: str = "unknown"
    affected_systems: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    blocked_context: list[dict[str, str]] = Field(default_factory=list)
    approval_gates: list[OrchestrationApprovalGateData | dict[str, Any]] = Field(default_factory=list)
    validation_plan: dict[str, Any] = Field(default_factory=dict)
    rollback_plan: dict[str, Any] = Field(default_factory=dict)
    active_task_id: str | None = None
    active_step: str | None = None
    active_agent: SpecializedAgentData | dict[str, Any] | None = None
    agents: list[SpecializedAgentData | dict[str, Any]] = Field(default_factory=list)
    agent_pipeline: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class OrchestrationDashboardData(ContractModel):
    workspace: str | None = None
    current_goal: str | None = None
    plan: OrchestrationPlanData | dict[str, Any] | None = None
    task_list: list[OrchestrationTaskData | dict[str, Any]] = Field(default_factory=list)
    active_task: OrchestrationTaskData | dict[str, Any] | None = None
    active_step: str | None = None
    active_agent: SpecializedAgentData | dict[str, Any] | None = None
    agents: list[SpecializedAgentData | dict[str, Any]] = Field(default_factory=list)
    agent_pipeline: list[dict[str, Any]] = Field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = Field(default_factory=list)
    coordination: dict[str, Any] = Field(default_factory=dict)
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    validation_results: list[ValidationData | dict[str, Any]] = Field(default_factory=list)
    rollback_option: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)


class JobData(ContractModel):
    id: str
    title: str = ""
    workflow: str = ""
    schedule: str = "manual"
    triggers: list[str] = Field(default_factory=list)
    description: str = ""
    approval_gates: list[dict[str, str]] = Field(default_factory=list)
    enabled: bool = True
    last_run: str | None = None
    next_run: str | None = None
    due: bool = False
    last_result: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)


class JobResultData(ContractModel):
    id: str = ""
    title: str = ""
    workflow: str = ""
    status: str = "completed"
    ok: bool = True
    trigger: str | None = None
    started_at: str = ""
    finished_at: str = ""
    approval_required: bool = False
    approval_gates: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    report: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class JobsDashboardData(ContractModel):
    workspace: str | None = None
    scheduled_jobs: list[JobData | dict[str, Any]] = Field(default_factory=list)
    due_jobs: list[JobData | dict[str, Any]] = Field(default_factory=list)
    triggers: list[dict[str, Any]] = Field(default_factory=list)
    approval_rules: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    log_path: str | None = None


class JobRunData(ContractModel):
    workspace: str | None = None
    trigger: str | None = None
    run_due: bool = False
    results: list[JobResultData | dict[str, Any]] = Field(default_factory=list)
    dashboard: JobsDashboardData | dict[str, Any] = Field(default_factory=dict)


class QualitySnapshotData(ContractModel):
    timestamp: str = ""
    score: int = 0
    grade: str = ""
    workspace_name: str = ""
    file_count: int = 0
    frameworks: list[str] = Field(default_factory=list)
    todo_count: int = 0
    known_bug_count: int = 0
    dependency_manifest_count: int = 0
    dependency_file_count: int = 0
    dependency_changes: list[str] = Field(default_factory=list)
    statuses: dict[str, Any] = Field(default_factory=dict)
    failing_systems: list[str] = Field(default_factory=list)
    failing_files: list[str] = Field(default_factory=list)
    complexity_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    high_risk_files: list[dict[str, Any]] = Field(default_factory=list)
    untested_core_modules: list[dict[str, Any]] = Field(default_factory=list)
    repeated_repair_attempts: int = 0
    repeated_model_failures: int = 0
    slow_validation_commands: list[dict[str, Any]] = Field(default_factory=list)
    files_changed_most_often: list[dict[str, Any]] = Field(default_factory=list)
    large_risky_diff: dict[str, Any] = Field(default_factory=dict)
    stale_documentation: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    top_risks: list[dict[str, Any]] = Field(default_factory=list)
    top_cleanup_tasks: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_improvement: str = ""


class QualityDashboardData(ContractModel):
    workspace: str | None = None
    score: int = 0
    grade: str = ""
    trend: dict[str, Any] = Field(default_factory=dict)
    statuses: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failing_systems: list[str] = Field(default_factory=list)
    high_risk_files: list[dict[str, Any]] = Field(default_factory=list)
    top_risks: list[dict[str, Any]] = Field(default_factory=list)
    top_cleanup_tasks: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_improvement: str = ""
    current_snapshot: QualitySnapshotData | dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    report_paths: dict[str, str] = Field(default_factory=dict)
    history_path: str | None = None


class KnowledgeNodeData(ContractModel):
    id: str
    type: str = ""
    label: str = ""
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeEdgeData(ContractModel):
    source: str
    target: str
    type: str = ""
    weight: int = 1
    evidence: list[str] = Field(default_factory=list)


class KnowledgeGraphData(ContractModel):
    workspace: str | None = None
    workspace_name: str = ""
    version: str = ""
    generated_at: str = ""
    nodes: list[KnowledgeNodeData | dict[str, Any]] = Field(default_factory=list)
    edges: list[KnowledgeEdgeData | dict[str, Any]] = Field(default_factory=list)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    architecture_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    unstable_modules: list[dict[str, Any]] = Field(default_factory=list)
    query_examples: list[str] = Field(default_factory=list)
    visualization: dict[str, Any] = Field(default_factory=dict)
    graph_path: str | None = None
    summary_path: str | None = None


class KnowledgeQueryData(ContractModel):
    workspace: str | None = None
    query: str = ""
    focus: str | None = None
    intent: str = "search"
    answers: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[KnowledgeEdgeData | dict[str, Any]] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    graph_version: str | None = None


class SimulationData(ContractModel):
    workspace: str | None = None
    objective: str = ""
    approach: str = ""
    generated_at: str = ""
    risk_level: str = "low"
    risk_score: int = 0
    risk_contributors: list[dict[str, Any]] = Field(default_factory=list)
    confidence: int = 0
    affected_systems: list[str] = Field(default_factory=list)
    focus_files: list[str] = Field(default_factory=list)
    impacted_files: list[dict[str, Any]] = Field(default_factory=list)
    blocked_context: list[dict[str, str]] = Field(default_factory=list)
    likely_build_risks: list[dict[str, Any]] = Field(default_factory=list)
    likely_test_failures: list[dict[str, Any]] = Field(default_factory=list)
    dependency_ripple: dict[str, Any] = Field(default_factory=dict)
    architecture_drift: dict[str, Any] = Field(default_factory=dict)
    prediction: dict[str, Any] = Field(default_factory=dict)
    roadmap_forecast: dict[str, Any] = Field(default_factory=dict)
    rollback_complexity: dict[str, Any] = Field(default_factory=dict)
    recommended_plan: dict[str, Any] = Field(default_factory=dict)
    history_signals: dict[str, Any] = Field(default_factory=dict)
    ui: dict[str, Any] = Field(default_factory=dict)


class SimulationComparisonData(ContractModel):
    workspace: str | None = None
    objective: str = ""
    generated_at: str = ""
    recommended_approach: str = ""
    recommended_reason: str = ""
    comparison: list[dict[str, Any]] = Field(default_factory=list)
    simulations: list[SimulationData | dict[str, Any]] = Field(default_factory=list)
    ui: dict[str, Any] = Field(default_factory=dict)


class OperationsDashboardData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    lifecycle: dict[str, Any] = Field(default_factory=dict)
    project_health: dict[str, Any] = Field(default_factory=dict)
    release_readiness: dict[str, Any] = Field(default_factory=dict)
    release_plan: dict[str, Any] = Field(default_factory=dict)
    technical_debt: dict[str, Any] = Field(default_factory=dict)
    task_coordination: dict[str, Any] = Field(default_factory=dict)
    risk_monitoring: dict[str, Any] = Field(default_factory=dict)
    maintenance_schedule: dict[str, Any] = Field(default_factory=dict)
    productivity_intelligence: dict[str, Any] = Field(default_factory=dict)
    cross_project_awareness: dict[str, Any] = Field(default_factory=dict)
    operations_dashboard: dict[str, Any] = Field(default_factory=dict)
    suggested_next_actions: list[dict[str, Any]] = Field(default_factory=list)
    approval_policy: dict[str, Any] = Field(default_factory=dict)


class PersonalIntelligenceData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    profile_version: str = ""
    preference_memory: dict[str, Any] = Field(default_factory=dict)
    learned_signals: dict[str, Any] = Field(default_factory=dict)
    coding_style_awareness: dict[str, Any] = Field(default_factory=dict)
    project_pattern_recognition: dict[str, Any] = Field(default_factory=dict)
    personalized_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    engineering_habit_analysis: dict[str, Any] = Field(default_factory=dict)
    workflow_optimization: dict[str, Any] = Field(default_factory=dict)
    context_personalization: dict[str, Any] = Field(default_factory=dict)
    agent_guidance: list[str] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)


class PersonalIntelligenceResetData(ContractModel):
    workspace: str | None = None
    reset: bool = False
    profile_path: str | None = None
    existed: bool | None = None
    error: str | None = None
    privacy: dict[str, Any] = Field(default_factory=dict)


class EcosystemDashboardData(ContractModel):
    workspace: str | None = None
    clients: list[ClientData] = Field(default_factory=list)
    active_projects: list[dict[str, Any]] = Field(default_factory=list)
    active_tasks: list[TaskData] = Field(default_factory=list)
    stale_tasks: list[TaskData] = Field(default_factory=list)
    recent_tasks: list[TaskData] = Field(default_factory=list)
    model_status: ModelsData | dict[str, Any] = Field(default_factory=dict)
    diagnostics: DiagnosticsSummaryData | dict[str, Any] = Field(default_factory=dict)
    roadmap: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationData | dict[str, Any] = Field(default_factory=dict)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    branding: dict[str, Any] = Field(default_factory=dict)


class PatchFileChangeData(ContractModel):
    path: str
    action: Literal["create", "update", "delete"] = "update"
    summary: str = ""
    patch: str | None = None


class PatchProposalData(ContractModel):
    id: str | None = None
    workspace: str | None = None
    source_task_id: str | None = None
    summary: str = ""
    risk: str = "unknown"
    approval_required: bool = True
    files: list[PatchFileChangeData] = Field(default_factory=list)
    validation: ValidationData | None = None


class RollbackEntryData(ContractModel):
    id: str | None = None
    workspace: str | None = None
    source_task_id: str | None = None
    checkpoint_path: str | None = None
    files: list[str] = Field(default_factory=list)
    created_at: str = ""
    summary: str = ""


class RollbackResultData(ContractModel):
    ok: bool = False
    workspace: str | None = None
    rollback_id: str | None = None
    restored_files: list[str] = Field(default_factory=list)
    error: str | None = None


class ContractDescriptor(ContractModel):
    kind: str
    stability: ContractStability
    owner: Literal["aegis-core", "website-backend", "schema-only"] = "aegis-core"
    notes: str = ""


DataModel = TypeVar("DataModel", bound=ContractModel)


CONTRACTS: dict[str, ContractDescriptor] = {
    "health": ContractDescriptor(kind="health", stability="stable", notes="Core runtime health and Ollama health snapshot."),
    "models": ContractDescriptor(kind="models", stability="stable", notes="Shared local model discovery and selected model status."),
    "model.providers": ContractDescriptor(kind="model.providers", stability="experimental", notes="Hybrid model provider inventory without plaintext secrets."),
    "model.route": ContractDescriptor(kind="model.route", stability="experimental", notes="Local-first route plan with cloud approval and sanitized context metadata."),
    "model.completion": ContractDescriptor(kind="model.completion", stability="experimental", notes="Gated local/cloud completion response; cloud calls require explicit approval."),
    "provider.key.status": ContractDescriptor(kind="provider.key.status", stability="experimental", notes="OS credential-store key mutation result without exposing secret values."),
    "settings": ContractDescriptor(kind="settings", stability="stable", notes="Shared Core runtime settings."),
    "settings.updated": ContractDescriptor(kind="settings.updated", stability="stable", notes="Shared Core runtime settings after update."),
    "workspace.scan": ContractDescriptor(kind="workspace.scan", stability="stable", notes="Shared workspace index and framework scan."),
    "workspace.roadmap": ContractDescriptor(kind="workspace.roadmap", stability="stable", notes="Shared roadmap generated from workspace memory."),
    "memory.summary": ContractDescriptor(kind="memory.summary", stability="stable", notes="Shared memory file manifest and excerpts."),
    "diagnostics.summary": ContractDescriptor(kind="diagnostics.summary", stability="stable", notes="Shared diagnostic log manifest and tails."),
    "branding.tokens": ContractDescriptor(kind="branding.tokens", stability="experimental", notes="Shared Auralith visual tokens."),
    "client.registered": ContractDescriptor(kind="client.registered", stability="stable", notes="Shared client registry mutation result."),
    "clients.list": ContractDescriptor(kind="clients.list", stability="stable", notes="Shared client registry listing."),
    "task.created": ContractDescriptor(kind="task.created", stability="stable", notes="Shared cross-client task creation result."),
    "tasks.list": ContractDescriptor(kind="tasks.list", stability="stable", notes="Shared cross-client task listing."),
    "task.updated": ContractDescriptor(kind="task.updated", stability="stable", notes="Shared cross-client task status update result."),
    "validation": ContractDescriptor(kind="validation", stability="stable", notes="Shared validation summary or command result."),
    "agent.continue.plan": ContractDescriptor(kind="agent.continue.plan", stability="experimental", notes="Plan-only continue workflow with task side effect."),
    "agent.repair.plan": ContractDescriptor(kind="agent.repair.plan", stability="experimental", notes="Plan-only repair workflow with task side effect when repair exists."),
    "agents.roster": ContractDescriptor(kind="agents.roster", stability="experimental", notes="Specialized local agent roles and coordination rules."),
    "orchestration.plan": ContractDescriptor(kind="orchestration.plan", stability="experimental", notes="Approval-gated autonomous goal plan and local task queue."),
    "orchestration.dashboard": ContractDescriptor(kind="orchestration.dashboard", stability="experimental", notes="Current orchestration goal, active step, approvals, validation, and rollback UI state."),
    "orchestration.step": ContractDescriptor(kind="orchestration.step", stability="experimental", notes="Approval-gated orchestration step transition."),
    "jobs.dashboard": ContractDescriptor(kind="jobs.dashboard", stability="experimental", notes="Safe scheduled and trigger-based maintenance job dashboard."),
    "jobs.run": ContractDescriptor(kind="jobs.run", stability="experimental", notes="Explicit maintenance job run or trigger result with approval gates for risky actions."),
    "quality.dashboard": ContractDescriptor(kind="quality.dashboard", stability="experimental", notes="Project health score, trends, risks, and recommended quality actions."),
    "quality.snapshot": ContractDescriptor(kind="quality.snapshot", stability="experimental", notes="Recorded project health snapshot and generated quality reports."),
    "knowledge.graph": ContractDescriptor(kind="knowledge.graph", stability="experimental", notes="Local semantic project knowledge graph across files, systems, APIs, tasks, docs, and history."),
    "knowledge.query": ContractDescriptor(kind="knowledge.query", stability="experimental", notes="Rule-based project knowledge graph query result."),
    "simulation.change": ContractDescriptor(kind="simulation.change", stability="experimental", notes="Read-only change impact simulation, risk forecast, validation estimate, and rollback complexity."),
    "simulation.compare": ContractDescriptor(kind="simulation.compare", stability="experimental", notes="Read-only comparison of implementation scenarios by predicted risk, impact, validation cost, and rollback complexity."),
    "operations.dashboard": ContractDescriptor(kind="operations.dashboard", stability="experimental", notes="Read-only engineering operations dashboard for release planning, technical debt, lifecycle, scheduling, productivity, and cross-project coordination."),
    "personal.intelligence": ContractDescriptor(kind="personal.intelligence", stability="experimental", notes="Local-first adaptive engineering preferences, workflow patterns, style awareness, and user-controlled profile memory."),
    "personal.intelligence.reset": ContractDescriptor(kind="personal.intelligence.reset", stability="experimental", notes="Reset local personal engineering profile memory for one workspace."),
    "ecosystem.dashboard": ContractDescriptor(kind="ecosystem.dashboard", stability="stable", notes="Aggregated Core dashboard for desktop and website bridge."),
    "patch.proposal": ContractDescriptor(kind="patch.proposal", stability="experimental", owner="schema-only", notes="Shared shape for approved patch proposals."),
    "rollback.entry": ContractDescriptor(kind="rollback.entry", stability="experimental", owner="schema-only", notes="Shared rollback checkpoint listing shape."),
    "rollback.result": ContractDescriptor(kind="rollback.result", stability="experimental", owner="schema-only", notes="Shared rollback execution result shape."),
}


CONTRACT_DATA_MODELS: dict[str, type[BaseModel] | tuple[type[BaseModel], bool]] = {
    "health": HealthData,
    "models": ModelsData,
    "model.providers": ProviderInventoryData,
    "model.route": ModelRouteData,
    "model.completion": ModelCompletionData,
    "provider.key.status": ProviderKeyStatusData,
    "settings": SettingsData,
    "settings.updated": SettingsData,
    "workspace.scan": WorkspaceScanData,
    "workspace.roadmap": RoadmapData,
    "memory.summary": MemorySummaryData,
    "diagnostics.summary": DiagnosticsSummaryData,
    "branding.tokens": BrandingData,
    "client.registered": ClientData,
    "clients.list": (ClientData, True),
    "task.created": TaskData,
    "tasks.list": (TaskData, True),
    "task.updated": TaskData,
    "validation": ValidationData,
    "agent.continue.plan": AgentTaskEnvelopeData,
    "agent.repair.plan": AgentTaskEnvelopeData,
    "agents.roster": AgentRosterData,
    "orchestration.plan": OrchestrationDashboardData,
    "orchestration.dashboard": OrchestrationDashboardData,
    "orchestration.step": OrchestrationDashboardData,
    "jobs.dashboard": JobsDashboardData,
    "jobs.run": JobRunData,
    "quality.dashboard": QualityDashboardData,
    "quality.snapshot": QualityDashboardData,
    "knowledge.graph": KnowledgeGraphData,
    "knowledge.query": KnowledgeQueryData,
    "simulation.change": SimulationData,
    "simulation.compare": SimulationComparisonData,
    "operations.dashboard": OperationsDashboardData,
    "personal.intelligence": PersonalIntelligenceData,
    "personal.intelligence.reset": PersonalIntelligenceResetData,
    "ecosystem.dashboard": EcosystemDashboardData,
    "patch.proposal": PatchProposalData,
    "rollback.entry": RollbackEntryData,
    "rollback.result": RollbackResultData,
}


def contract_descriptor(kind: str) -> ContractDescriptor:
    return CONTRACTS.get(
        kind,
        ContractDescriptor(kind=kind, stability="experimental", notes="Unregistered Core contract kind."),
    )


def make_envelope(
    kind: str,
    data: Any,
    workspace: str | Path | None = None,
    ok: bool = True,
    *,
    deprecations: list[str] | None = None,
) -> dict[str, Any]:
    descriptor = contract_descriptor(kind)
    envelope = CoreEnvelope(
        ok=ok,
        api_version=CORE_API_VERSION,
        contract_version=CORE_CONTRACT_VERSION,
        kind=kind,
        workspace=str(Path(workspace).resolve()) if workspace else None,
        data=data,
        stability=descriptor.stability,
        deprecated=descriptor.stability == "deprecated",
        deprecations=deprecations or [],
    )
    return model_dump(envelope)


def validate_contract_envelope(payload: Any) -> CoreEnvelope:
    envelope = model_validate(CoreEnvelope, payload)
    model_entry = CONTRACT_DATA_MODELS.get(envelope.kind)
    if model_entry is not None:
        model, is_list = model_entry if isinstance(model_entry, tuple) else (model_entry, False)
        if is_list:
            if not isinstance(envelope.data, list):
                raise ValueError(f"Contract {envelope.kind} data must be a list.")
            for item in envelope.data:
                model_validate(model, item)
        else:
            model_validate(model, envelope.data)
    return envelope


def contract_catalog() -> list[dict[str, Any]]:
    return [model_dump(CONTRACTS[key]) for key in sorted(CONTRACTS)]


def model_validate(model: type[DataModel], value: Any) -> DataModel:
    if hasattr(model, "model_validate"):
        return model.model_validate(value)  # type: ignore[attr-defined]
    return model.parse_obj(value)


def model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()
