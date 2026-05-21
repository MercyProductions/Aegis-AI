from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeVar

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:  # pragma: no cover - import guard mirrors server dependency checks.
    from pydantic import BaseModel, Field  # type: ignore[no-redef]

    ConfigDict = None  # type: ignore[assignment]


CORE_API_VERSION = "v1"
CORE_CONTRACT_VERSION = "2026.05.12"

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


class CoreFileChangeRequest(ContractModel):
    id: str | None = None
    action: Literal["create", "update", "append", "delete"] = "update"
    path: str
    content: str | None = None
    summary: str = ""
    selected: bool = False


class ProposeChangesRequest(ContractModel):
    workspace: str
    changes: list[CoreFileChangeRequest] = Field(default_factory=list)
    summary: str = ""
    source_task_id: str | None = None
    source_client: str = "unknown"
    risk: str = "unknown"
    repair_attempt: dict[str, Any] | None = None


class ApplyChangesRequest(ContractModel):
    workspace: str
    proposal_id: str | None = None
    changes: list[CoreFileChangeRequest] = Field(default_factory=list)
    change_ids: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    apply_all: bool = True
    dry_run: bool = False
    summary: str = ""
    task_id: str | None = None
    source_client: str = "unknown"
    repair_attempt: dict[str, Any] | None = None
    approval: bool = False
    validation_required: bool = False
    quality_gate_required: bool = True
    max_files_changed: int = 25
    allow_quality_override: bool = False


class CheckpointCreateRequest(ContractModel):
    workspace: str
    changes: list[CoreFileChangeRequest] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    summary: str = ""
    source_task_id: str | None = None
    source_client: str = "unknown"


class CheckpointRestoreRequest(ContractModel):
    workspace: str
    checkpoint_id: str | None = None
    checkpoint: str | None = None
    dry_run: bool = False
    source_client: str = "unknown"
    task_id: str | None = None


class ValidationRunRequest(ContractModel):
    workspace: str
    command: list[str] | None = None
    timeout_seconds: int = 120
    dry_run: bool = False
    source_client: str = "unknown"
    task_id: str | None = None
    repair_attempt: dict[str, Any] | None = None


class QualityGateEvaluateRequest(ContractModel):
    workspace: str
    changes: list[CoreFileChangeRequest] = Field(default_factory=list)
    workflow_id: str | None = None
    validation_id: str | None = None
    validation: dict[str, Any] | None = None
    approval: bool = False
    checkpoint_id: str | None = None
    max_files_changed: int = 25
    restricted_paths: list[str] = Field(default_factory=list)
    validation_required: bool = False
    dry_run: bool = True
    persist: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunRequest(ContractModel):
    workspace: str
    suite_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationReportRequest(ContractModel):
    workspace: str
    workflow_id: str | None = None
    quality_run_id: str | None = None
    title: str = ""
    changes: list[CoreFileChangeRequest] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    repairs_attempted: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreateRequest(ContractModel):
    workspace: str
    workflow_type: Literal[
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
    objective: str
    source_client: str = "unknown"
    context_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowActionRequest(ContractModel):
    workspace: str
    action: str = "advance"
    task_id: str | None = None
    approval: bool = False
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentDelegationRequest(ContractModel):
    workspace: str
    task_id: str
    agent_id: str
    approval: bool = False
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EngineeringExecutionCreateRequest(ContractModel):
    workspace: str
    goal: str
    mode: Literal[
        "safe_assisted",
        "approval_every_step",
        "semi_autonomous",
        "autonomous_validate_only",
        "roadmap_execution",
        "repair_only",
    ] = "safe_assisted"
    source_client: str = "unknown"
    constraints: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    validation_command: list[str] | None = None
    max_repair_attempts: int | None = None
    max_file_modifications: int = 25
    approval_requirements: list[str] = Field(default_factory=list)
    roadmap_item_id: str | None = None
    roadmap_phase_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    create_workflow: bool = True


class EngineeringExecutionActionRequest(ContractModel):
    workspace: str
    action: str = "advance"
    stage_key: str | None = None
    approval: bool = False
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EngineeringMemoryRequest(ContractModel):
    workspace: str
    refresh: bool = False
    persist: bool = True


class EngineeringRoadmapExecuteRequest(ContractModel):
    workspace: str
    goal: str = ""
    roadmap_item_id: str = ""
    roadmap_phase_id: str = ""
    source_client: str = "unknown"
    target_files: list[str] = Field(default_factory=list)
    validation_command: list[str] | None = None
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutopilotStartRequest(ContractModel):
    workspace: str
    objective: str
    mode: Literal[
        "suggest_only",
        "approval_each_step",
        "semi_autonomous",
        "roadmap_autopilot",
        "repair_autopilot",
        "validation_autopilot",
        "experimental_full_autopilot",
    ] = "semi_autonomous"
    workflow_type: str = "generate_feature"
    roadmap: list[dict[str, Any]] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    validation_commands: list[dict[str, Any]] = Field(default_factory=list)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    specialization: str | None = None
    client_id: str | None = None
    approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutopilotActionRequest(ContractModel):
    workspace: str
    action: str = "advance"
    approval: bool = False
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    client_id: str | None = None


class ClientSyncRequest(ContractModel):
    workspace: str
    client_id: str
    client_type: str = "unknown"
    name: str = "Unknown Client"
    version: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)
    active_workflow_id: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceIntelligenceRequest(ContractModel):
    workspace: str
    refresh: bool = False
    persist: bool = True


class SettingsRequest(ContractModel):
    workspace: str
    settings: dict[str, Any] = Field(default_factory=dict)


class OnboardingUpdateRequest(ContractModel):
    workspace: str
    completed_steps: list[str] | None = None
    current_step: str | None = None
    preferences: dict[str, Any] | None = None
    first_workflow_completed_steps: list[str] | None = None
    reset: bool = False


class OnboardingFirstWorkflowRequest(ContractModel):
    workspace: str
    action: str
    dry_run: bool = True
    source_client: str = "unknown"


class SettingsImportRequest(ContractModel):
    workspace: str
    settings: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


class PluginStateRequest(ContractModel):
    workspace: str
    plugin_id: str
    enabled: bool | None = None
    trusted: bool | None = None
    approval: bool = False
    reason: str = ""


class PluginToolRunRequest(ContractModel):
    workspace: str
    plugin_id: str
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True
    approval: bool = False
    workflow_type: str | None = None
    source_client: str = "unknown"


class RuntimeNodeRegisterRequest(ContractModel):
    workspace: str
    node_id: str | None = None
    name: str = ""
    node_type: Literal["local", "trusted_remote", "isolated_worker", "validation", "indexing", "gpu_model"] = "trusted_remote"
    endpoint: str = ""
    capabilities: list[str] = Field(default_factory=list)
    cpu: dict[str, Any] = Field(default_factory=dict)
    gpu: dict[str, Any] = Field(default_factory=dict)
    ram_gb: float | None = None
    storage_gb: float | None = None
    supported_workflow_types: list[str] = Field(default_factory=list)
    installed_models: list[str] = Field(default_factory=list)
    installed_plugins: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    max_parallel_workloads: int = 1
    isolation: dict[str, Any] = Field(default_factory=dict)
    auth_token: str | None = None
    approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeNodeHeartbeatRequest(ContractModel):
    workspace: str
    status: str = "online"
    health: dict[str, Any] = Field(default_factory=dict)
    current_workload_ids: list[str] | None = None
    workload_count: int | None = None
    capabilities: list[str] | None = None
    installed_models: list[str] | None = None
    installed_plugins: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeNodeRevokeRequest(ContractModel):
    workspace: str
    reason: str = ""


class RuntimeWorkloadRequest(ContractModel):
    workspace: str
    workload_type: Literal["workflow", "validation", "indexing", "model_inference", "plugin_tool", "repair", "build", "benchmark"] = "workflow"
    workflow_type: str | None = None
    title: str = ""
    priority: int = 50
    required_capabilities: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    allow_remote: bool = False
    preferred_node_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True
    approval: bool = False
    max_attempts: int = 2
    source_client: str = "unknown"


class RuntimeWorkloadActionRequest(ContractModel):
    workspace: str
    approval: bool | None = None
    allow_remote: bool | None = None
    preferred_node_id: str | None = None
    dry_run: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dispatch: bool = False
    reason: str = ""


class RuntimeTerminalJobRequest(ContractModel):
    workspace: str
    command: list[str] | str
    cwd: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    terminal_id: str | None = None
    title: str = ""
    timeout_seconds: int = 120
    approval: bool = False
    dry_run: bool = False
    wait: bool = True
    source_client: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeJobActionRequest(ContractModel):
    workspace: str
    approval: bool | None = None
    wait: bool = True
    timeout_seconds: int | None = None
    reason: str = ""


class RuntimeSessionRequest(ContractModel):
    workspace: str
    workflow_id: str = ""
    title: str = ""
    owner_client_id: str = "unknown"
    participants: list[dict[str, Any]] = Field(default_factory=list)
    spectators: list[dict[str, Any]] = Field(default_factory=list)
    approval_delegates: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeSessionSyncRequest(ContractModel):
    workspace: str
    participants: list[dict[str, Any]] | None = None
    spectators: list[dict[str, Any]] | None = None
    approval_delegates: list[str] | None = None
    status: str | None = None
    message: str = ""


class RuntimeVoiceCommandRequest(ContractModel):
    workspace: str
    transcript: str
    workflow_id: str = ""
    client_id: str = "unknown"
    dry_run: bool = True


class CollaborationMemberRequest(ContractModel):
    workspace: str
    user_id: str
    display_name: str = ""
    role: Literal["owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"] = "reviewer"
    client_id: str = ""
    active: bool = True
    permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationRepositoryRequest(ContractModel):
    workspace: str
    repository_id: str | None = None
    path: str = ""
    name: str = ""
    owner_id: str = "local-owner"
    visibility: Literal["workspace", "restricted", "private"] = "workspace"
    runtime_nodes: list[str] = Field(default_factory=list)
    validation_infrastructure: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationWorkflowRequest(ContractModel):
    workspace: str
    objective: str
    workflow_type: str = "generate_feature"
    owner_id: str = "local-owner"
    owner_role: Literal["owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"] = "owner"
    repository_id: str | None = None
    participants: list[dict[str, Any]] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    visibility: Literal["team", "workspace", "restricted", "private"] = "team"
    approval_chain: list[dict[str, Any] | str] = Field(default_factory=list)
    roadmap_item_ids: list[str] = Field(default_factory=list)
    source_client: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationWorkflowActionRequest(ContractModel):
    workspace: str
    action: str = "delegate"
    actor_id: str = "local-owner"
    actor_role: Literal["owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"] = "owner"
    assignee_id: str = ""
    assignee_role: Literal["owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"] = "maintainer"
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationApprovalRequest(ContractModel):
    workspace: str
    target_type: str = "workflow"
    target_id: str
    approval_type: Literal["workflow", "validation", "deployment", "rollback", "roadmap", "runtime_delegation", "repair"] = "workflow"
    required_roles: list[str] = Field(default_factory=list)
    requested_by: str = "local-owner"
    reason: str = ""
    stage: str = "review"
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    deployment_environment: str = ""
    required_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationApprovalDecisionRequest(ContractModel):
    workspace: str
    decision: Literal["approve", "reject"]
    user_id: str
    role: Literal["owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"]
    comment: str = ""


class CollaborationRoadmapItemRequest(ContractModel):
    workspace: str
    title: str
    item_id: str | None = None
    workflow_id: str = ""
    milestone: str = ""
    owner_id: str = "local-owner"
    assigned_to: str = ""
    status: Literal["planned", "in_progress", "blocked", "completed", "cancelled"] = "planned"
    blockers: list[str] = Field(default_factory=list)
    approval_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyRequest(ContractModel):
    workspace: str
    policy: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = "local-owner"
    reason: str = ""


class GovernancePolicyEvaluationRequest(ContractModel):
    workspace: str
    action_type: str
    workflow_type: str = ""
    target: str = ""
    actor_id: str = "local-owner"
    actor_role: str = "owner"
    context: dict[str, Any] = Field(default_factory=dict)
    approval: bool = False
    dry_run: bool = True


class GovernanceComplianceExportRequest(ContractModel):
    workspace: str
    export_type: str = "full"
    limit: int = 500
    include_sensitive: bool = False


class DeploymentWorkflowRequest(ContractModel):
    workspace: str
    workflow_type: Literal[
        "build_project",
        "package_release",
        "run_ci",
        "validate_pipeline",
        "deploy_staging",
        "deploy_production",
        "rollback_release",
    ] = "validate_pipeline"
    target_environment: str = "staging"
    release_version: str = ""
    approval: bool = False
    production_confirmed: bool = False
    dry_run: bool = True
    source_client: str = "unknown"
    notes: str = ""


class DeploymentWorkflowActionRequest(ContractModel):
    workspace: str
    action: str = "advance"
    approval: bool = False
    production_confirmed: bool = False
    validation_passed: bool = False
    message: str = ""


class DeploymentPipelineValidationRequest(ContractModel):
    workspace: str
    pipeline_id: str = ""
    dry_run: bool = True


class OptimizationExperimentRequest(ContractModel):
    workspace: str
    target_area: Literal[
        "workflow_execution",
        "routing_policy",
        "validation_ordering",
        "repair_strategy",
        "model_selection",
        "context_assembly",
        "agent_coordination",
        "indexing_strategy",
        "plugin_runtime",
    ] = "workflow_execution"
    hypothesis: str
    variants: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_suite_ids: list[str] = Field(default_factory=list)
    sandbox: bool = True
    approval: bool = False
    source_client: str = "unknown"


class OptimizationExperimentRunRequest(ContractModel):
    workspace: str
    dry_run: bool = True
    benchmark_suite_ids: list[str] = Field(default_factory=list)


class OptimizationExperimentAdoptRequest(ContractModel):
    workspace: str
    approval: bool = False
    rollout_stage: Literal["partial_rollout", "adopted"] = "partial_rollout"
    reason: str = ""


class OptimizationExperimentRollbackRequest(ContractModel):
    workspace: str
    reason: str = ""


class RuntimeRecoveryRequest(ContractModel):
    workspace: str
    auto_dispatch: bool = False


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
    route_profile: str | None = None
    workflow_type: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    privacy_sensitive: bool = False


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


class KnowledgeSearchRequest(ContractModel):
    workspace: str
    query: str
    node_type: str | None = None
    limit: int = 25


class KnowledgeRelationshipsRequest(ContractModel):
    workspace: str
    focus: str
    relationship: str | None = None
    depth: int = 1
    direction: Literal["incoming", "outgoing", "both"] = "both"
    limit: int = 50


class KnowledgeSymbolRequest(ContractModel):
    workspace: str
    symbol: str
    limit: int = 20


class KnowledgeImpactAnalysisRequest(ContractModel):
    workspace: str
    target: str
    change_type: str = "modify"
    limit: int = 100


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


class DogfoodingEventRequest(ContractModel):
    workspace: str
    event_type: str = "workflow_event"
    client_id: str = "unknown"
    client_type: str = "unknown"
    workflow_id: str = ""
    workflow_type: str = ""
    action: str = ""
    status: str = "observed"
    duration_ms: int | None = None
    click_count: int | None = None
    friction_tags: list[str] = Field(default_factory=list)
    interruption: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EngineeringWorkspaceSearchRequest(ContractModel):
    workspace: str
    query: str
    mode: str = "architecture"
    focus: str | None = None
    limit: int = 25


class EngineeringIntelligenceRequest(ContractModel):
    workspace: str
    workflow_type: str = "generate_feature"
    objective: str = ""
    target_files: list[str] = Field(default_factory=list)
    focus: str = ""
    token_budget: int = 24000
    latest_validation: dict[str, Any] = Field(default_factory=dict)
    refresh: bool = False
    persist: bool = True


class EngineeringIntelligenceBenchmarkRequest(ContractModel):
    workspace: str
    workflow_type: str = "generate_feature"
    objective: str = ""
    target_files: list[str] = Field(default_factory=list)
    persist: bool = True


class IntelligenceStackRequest(ContractModel):
    workspace: str
    workflow_type: str = "generate_feature"
    objective: str = ""
    target_files: list[str] = Field(default_factory=list)
    refresh: bool = False
    persist: bool = True


class IntelligenceModelLifecycleRequest(ContractModel):
    workspace: str
    action: str = "list"
    model_id: str = ""
    model: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class IntelligenceRetrievalRequest(ContractModel):
    workspace: str
    query: str = ""
    focus: str = ""
    limit: int = 25
    refresh: bool = False
    persist: bool = True


class IntelligenceRoutingRequest(ContractModel):
    workspace: str
    workflow_type: str = "generate_feature"
    objective: str = ""
    target_files: list[str] = Field(default_factory=list)
    route_profile: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    privacy_sensitive: bool = False
    allow_cloud: bool = False
    cloud_approved: bool = False
    context_files: list[str] = Field(default_factory=list)
    local_failure_reason: str | None = None


class IntelligenceBenchmarkRequest(ContractModel):
    workspace: str
    suites: list[str] = Field(default_factory=list)
    workflow_type: str = "generate_feature"
    objective: str = ""
    target_files: list[str] = Field(default_factory=list)
    persist: bool = True


class IntelligenceDatasetRequest(ContractModel):
    workspace: str
    include_sensitive: bool = False
    limit: int = 100
    persist: bool = True


class IntelligenceDistributedInferenceRequest(ContractModel):
    workspace: str
    workflow_type: str = "generate_feature"
    model_id: str = ""
    allow_remote: bool = False
    approval: bool = False
    dry_run: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class AlphaFeatureFlagsRequest(ContractModel):
    workspace: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    release_channel: str | None = None
    reason: str = ""


class AlphaDiagnosticsExportRequest(ContractModel):
    workspace: str
    include_replay: bool = True
    include_plugins: bool = True
    include_validation: bool = True
    reason: str = ""


class AlphaFeedbackRequest(ContractModel):
    workspace: str
    category: str = "other"
    severity: str = "medium"
    message: str = ""
    client_type: str = "unknown"
    workflow_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformMigrationRequest(ContractModel):
    workspace: str
    dry_run: bool = True


class PlatformCompatibilityRequest(ContractModel):
    workspace: str
    client_reports: list[dict[str, Any]] = Field(default_factory=list)
    include_plugins: bool = True
    persist: bool = False


class PlatformArchiveRequest(ContractModel):
    workspace: str
    include_memory: bool = True
    include_workflows: bool = True
    include_knowledge: bool = True
    include_checkpoints: bool = False
    dry_run: bool = False
    reason: str = ""


class PlatformSustainabilityRequest(ContractModel):
    workspace: str
    persist: bool = False


class EcosystemMaturityRequest(ContractModel):
    workspace: str
    persist: bool = False


class EcosystemObservabilityRequest(ContractModel):
    workspace: str
    persist: bool = False


class PersonalIntelligenceRequest(ContractModel):
    workspace: str
    project_roots: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    persist: bool = False


class PersonalMemoryQueryRequest(ContractModel):
    workspace: str
    query: str = ""
    category: str | None = None
    scope: str | None = None
    include_archived: bool = False
    include_disabled: bool = False
    limit: int = 100


class PersonalMemoryCreateRequest(ContractModel):
    workspace: str
    category: str = "project_memory"
    title: str
    content: str
    scope: str = "project"
    tags: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    source: str = "user"
    confidence: float = 0.8
    pinned: bool = False
    expires_at: str | None = None
    privacy: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryUpdateRequest(ContractModel):
    workspace: str
    category: str | None = None
    title: str | None = None
    content: str | None = None
    scope: str | None = None
    tags: list[str] | None = None
    related_files: list[str] | None = None
    confidence: float | None = None
    pinned: bool | None = None
    expires_at: str | None = None
    privacy: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class PersonalMemoryArchiveRequest(ContractModel):
    workspace: str
    reason: str = ""


class PersonalMemoryDeleteRequest(ContractModel):
    workspace: str
    hard_delete: bool = False
    reason: str = ""


class PersonalMemoryExportRequest(ContractModel):
    workspace: str
    categories: list[str] = Field(default_factory=list)
    include_archived: bool = False
    redact_sensitive: bool = True
    include_controls: bool = True


class PersonalMemoryImportRequest(ContractModel):
    workspace: str
    payload: dict[str, Any] | list[Any] = Field(default_factory=dict)
    merge_strategy: str = "append"
    dry_run: bool = True
    source: str = "import"


class PersonalMemoryControlsRequest(ContractModel):
    workspace: str
    category: str | None = None
    enabled: bool | None = None
    retention_days: int | None = None
    include_in_orchestration: bool | None = None
    encrypted: bool | None = None
    local_only: bool | None = None
    disabled_categories: list[str] | None = None
    allowed_scopes: list[str] | None = None


class PersonalMemoryCleanupRequest(ContractModel):
    workspace: str
    dry_run: bool = True
    archive_stale: bool = True


class PersonalMemoryContextRequest(ContractModel):
    workspace: str
    workflow_type: str = ""
    objective: str = ""
    max_items: int = 12
    record_usage: bool = True


class ReleaseCompatibilityRequest(ContractModel):
    workspace: str | None = None
    client_type: str
    client_version: str = ""
    schema_version: str = ""
    core_version: str = ""
    capabilities: list[str] = Field(default_factory=list)


class ReleaseMigrationRequest(ContractModel):
    workspace: str
    dry_run: bool = False


class ReleaseUpdatePlanRequest(ContractModel):
    component_id: str
    current_version: str = ""
    target_version: str = ""
    package_uri: str = ""
    sha256: str = ""


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


class SecurityStatusData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    local_api: dict[str, Any] = Field(default_factory=dict)
    workspace_access: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    updates: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)


class ReleaseManifestData(ContractModel):
    manifest_version: int = 1
    schema_version: str = ""
    release_channel: str = "local"
    generated_at: str = ""
    components: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    update_policy: dict[str, Any] = Field(default_factory=dict)


class ReleaseCompatibilityData(ContractModel):
    compatible: bool = False
    client_type: str = ""
    client_version: str = ""
    core_version: str = ""
    schema_version: str = ""
    required_core_version: str = ""
    required_schema_version: str = ""
    status: str = ""
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ReleaseMigrationData(ContractModel):
    workspace: str = ""
    schema_version: str = ""
    dry_run: bool = False
    applied: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[dict[str, Any]] = Field(default_factory=list)
    state_path: str = ""


class ReleaseUpdatePlanData(ContractModel):
    component_id: str = ""
    current_version: str = ""
    target_version: str = ""
    status: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    rollback: dict[str, Any] = Field(default_factory=dict)


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


class OnboardingStepData(ContractModel):
    id: str
    label: str = ""
    required: bool = False
    summary: str = ""
    status: str = "pending"
    detail: str = ""
    action: dict[str, Any] = Field(default_factory=dict)


class OnboardingDiagnosticCheckData(ContractModel):
    id: str
    label: str = ""
    status: str = "warn"
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OnboardingStatusData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    completed: bool = False
    current_step: str = "welcome"
    steps: list[OnboardingStepData | dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    recommended_defaults: dict[str, Any] = Field(default_factory=dict)
    first_workflow: dict[str, Any] = Field(default_factory=dict)
    recovery: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    state_path: str = ""


class OnboardingFirstWorkflowData(ContractModel):
    workspace: str | None = None
    action: str = ""
    dry_run: bool = True
    completed: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)


class SettingsExportData(ContractModel):
    schema_version: int = 1
    exported_at: str = ""
    workspace: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    provider_config_metadata: list[dict[str, Any]] = Field(default_factory=list)
    ui_preferences: dict[str, Any] = Field(default_factory=dict)
    runtime_urls: dict[str, Any] = Field(default_factory=dict)
    workspace_preferences: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SettingsImportData(ContractModel):
    workspace: str | None = None
    dry_run: bool = True
    imported_keys: list[str] = Field(default_factory=list)
    ignored_keys: list[str] = Field(default_factory=list)
    ui_preference_keys: list[str] = Field(default_factory=list)
    settings_preview: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PluginDashboardData(ContractModel):
    schema_version: int = 1
    api_version: str = ""
    workspace: str | None = None
    generated_at: str = ""
    plugin_root: str = ""
    state_path: str = ""
    categories: list[dict[str, Any]] = Field(default_factory=list)
    permission_scopes: list[dict[str, Any]] = Field(default_factory=list)
    plugins: list[dict[str, Any]] = Field(default_factory=list)
    enabled_plugins: list[str] = Field(default_factory=list)
    disabled_plugins: list[str] = Field(default_factory=list)
    tool_catalog: list[dict[str, Any]] = Field(default_factory=list)
    workflow_hooks: dict[str, Any] = Field(default_factory=dict)
    ui_extensions: list[dict[str, Any]] = Field(default_factory=list)
    packaging_format: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)


class PluginStateData(ContractModel):
    workspace: str | None = None
    plugin: dict[str, Any] = Field(default_factory=dict)
    state_path: str = ""


class PluginToolRunData(ContractModel):
    run_id: str = ""
    workspace: str | None = None
    plugin_id: str = ""
    tool_name: str = ""
    ok: bool = False
    blocked: bool = False
    dry_run: bool = True
    duration_ms: int = 0
    permissions_used: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PluginHooksData(ContractModel):
    workspace: str | None = None
    workflow_type: str | None = None
    hooks: dict[str, Any] = Field(default_factory=dict)
    tool_catalog: list[dict[str, Any]] = Field(default_factory=list)
    ui_extensions: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeNodeData(ContractModel):
    node_id: str = ""
    name: str = ""
    node_type: str = "trusted_remote"
    endpoint: str = ""
    status: str = "offline"
    trust_level: str = "untrusted"
    trust_scope: str = ""
    registered_at: str = ""
    last_heartbeat_at: str = ""
    capabilities: list[str] = Field(default_factory=list)
    cpu: dict[str, Any] = Field(default_factory=dict)
    gpu: dict[str, Any] = Field(default_factory=dict)
    ram_gb: float | None = None
    storage_gb: float | None = None
    supported_workflow_types: list[str] = Field(default_factory=list)
    installed_models: list[str] = Field(default_factory=list)
    installed_plugins: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    current_workload_count: int = 0
    current_workload_ids: list[str] = Field(default_factory=list)
    max_parallel_workloads: int = 1
    isolation: dict[str, Any] = Field(default_factory=dict)
    transport: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    eligible: bool = False
    updated_at: str = ""


class RuntimeWorkloadData(ContractModel):
    workload_id: str = ""
    workspace: str | None = None
    workload_type: str = "workflow"
    workflow_type: str = ""
    title: str = ""
    status: str = "queued"
    priority: int = 50
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    assigned_node_id: str | None = None
    attempts: int = 0
    max_attempts: int = 1
    required_capabilities: list[str] = Field(default_factory=list)
    permission_scopes: list[str] = Field(default_factory=list)
    allow_remote: bool = False
    preferred_node_id: str | None = None
    fallback_node_ids: list[str] = Field(default_factory=list)
    dry_run: bool = True
    approval: bool = False
    authorization: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scheduling_reason: str = ""
    source_client: str = "unknown"
    operation_log: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeAuditEventData(ContractModel):
    event_id: str = ""
    event_type: str = ""
    severity: str = "info"
    workspace: str | None = None
    node_id: str | None = None
    workload_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class DistributedRuntimeData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    local_authority: dict[str, Any] = Field(default_factory=dict)
    nodes: list[RuntimeNodeData | dict[str, Any]] = Field(default_factory=list)
    workloads: list[RuntimeWorkloadData | dict[str, Any]] = Field(default_factory=list)
    queued_workloads: list[RuntimeWorkloadData | dict[str, Any]] = Field(default_factory=list)
    active_workloads: list[RuntimeWorkloadData | dict[str, Any]] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)
    scheduling_policy: dict[str, Any] = Field(default_factory=dict)
    trust_model: dict[str, Any] = Field(default_factory=dict)
    isolation_profiles: list[dict[str, Any]] = Field(default_factory=list)
    deployment: dict[str, Any] = Field(default_factory=dict)
    audit_events: list[RuntimeAuditEventData | dict[str, Any]] = Field(default_factory=list)


class RuntimeNodesData(ContractModel):
    workspace: str | None = None
    nodes: list[RuntimeNodeData | dict[str, Any]] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)
    trust_model: dict[str, Any] = Field(default_factory=dict)


class RuntimeNodeMutationData(ContractModel):
    workspace: str | None = None
    node: RuntimeNodeData | dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    requeued_workload_ids: list[str] = Field(default_factory=list)
    audit_events: list[RuntimeAuditEventData | dict[str, Any]] = Field(default_factory=list)


class RuntimeWorkloadMutationData(ContractModel):
    workspace: str | None = None
    workload: RuntimeWorkloadData | dict[str, Any] = Field(default_factory=dict)
    dashboard: DistributedRuntimeData | dict[str, Any] = Field(default_factory=dict)
    dispatched: bool | None = None
    remote_dispatch: bool | None = None
    node: RuntimeNodeData | dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    rejected_nodes: list[dict[str, Any]] = Field(default_factory=list)
    retried: bool | None = None
    cancelled: bool | None = None


class RuntimeWorkloadsData(ContractModel):
    workspace: str | None = None
    workloads: list[RuntimeWorkloadData | dict[str, Any]] = Field(default_factory=list)


class RuntimeTerminalJobData(ContractModel):
    job_id: str = ""
    terminal_id: str = ""
    workflow_id: str = ""
    task_id: str = ""
    title: str = ""
    command: list[str] = Field(default_factory=list)
    command_text: str = ""
    cwd: str = ""
    status: str = "queued"
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    timeout_seconds: int = 120
    exit_code: int | None = None
    timed_out: bool = False
    approval_required: bool = False
    approved: bool = False
    dry_run: bool = False
    source_client: str = "unknown"
    stdout_tail: str = ""
    stderr_tail: str = ""
    output_event_count: int = 0
    safety: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionEventData(ContractModel):
    event_id: str = ""
    event_type: str = ""
    workspace: str | None = None
    job_id: str = ""
    terminal_id: str = ""
    workflow_id: str = ""
    stream: str = ""
    chunk: str = ""
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"
    created_at: str = ""


class RuntimeTerminalData(ContractModel):
    terminal_id: str = ""
    title: str = ""
    status: str = "idle"
    job_count: int = 0
    active_job_ids: list[str] = Field(default_factory=list)
    latest_job_id: str = ""
    latest_output: str = ""
    updated_at: str = ""


class RuntimeSessionData(ContractModel):
    session_id: str = ""
    workflow_id: str = ""
    title: str = ""
    owner_client_id: str = "unknown"
    participants: list[dict[str, Any]] = Field(default_factory=list)
    spectators: list[dict[str, Any]] = Field(default_factory=list)
    approval_delegates: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    last_sync_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    terminals: list[RuntimeTerminalData | dict[str, Any]] = Field(default_factory=list)
    jobs: list[RuntimeTerminalJobData | dict[str, Any]] = Field(default_factory=list)
    active_jobs: list[RuntimeTerminalJobData | dict[str, Any]] = Field(default_factory=list)
    recent_events: list[RuntimeInteractionEventData | dict[str, Any]] = Field(default_factory=list)
    processes: list[dict[str, Any]] = Field(default_factory=list)
    sessions: list[RuntimeSessionData | dict[str, Any]] = Field(default_factory=list)
    voice: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    safety_controls: dict[str, Any] = Field(default_factory=dict)
    stream_endpoint: str = ""


class RuntimeInteractionJobsData(ContractModel):
    workspace: str | None = None
    jobs: list[RuntimeTerminalJobData | dict[str, Any]] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionJobMutationData(ContractModel):
    workspace: str | None = None
    action: str = ""
    job: RuntimeTerminalJobData | dict[str, Any] = Field(default_factory=dict)
    dashboard: RuntimeInteractionDashboardData | dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionJobLookupData(ContractModel):
    workspace: str | None = None
    job: RuntimeTerminalJobData | dict[str, Any] = Field(default_factory=dict)
    events: list[RuntimeInteractionEventData | dict[str, Any]] = Field(default_factory=list)
    process: dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionStreamsData(ContractModel):
    workspace: str | None = None
    events: list[RuntimeInteractionEventData | dict[str, Any]] = Field(default_factory=list)
    next_since: int = 0


class RuntimeInteractionProcessesData(ContractModel):
    workspace: str | None = None
    processes: list[dict[str, Any]] = Field(default_factory=list)
    active_count: int = 0


class RuntimeInteractionSessionsData(ContractModel):
    workspace: str | None = None
    sessions: list[RuntimeSessionData | dict[str, Any]] = Field(default_factory=list)
    active_sessions: list[RuntimeSessionData | dict[str, Any]] = Field(default_factory=list)
    recent_events: list[RuntimeInteractionEventData | dict[str, Any]] = Field(default_factory=list)


class RuntimeInteractionSessionMutationData(ContractModel):
    workspace: str | None = None
    session: RuntimeSessionData | dict[str, Any] = Field(default_factory=dict)
    dashboard: RuntimeInteractionSessionsData | dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionVoiceData(ContractModel):
    workspace: str | None = None
    push_to_talk: dict[str, Any] = Field(default_factory=dict)
    speech_to_text: dict[str, Any] = Field(default_factory=dict)
    text_to_speech: dict[str, Any] = Field(default_factory=dict)
    voice_commands: list[str] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)
    status: str = ""
    warnings: list[str] = Field(default_factory=list)


class RuntimeInteractionVoiceCommandData(ContractModel):
    workspace: str | None = None
    command: dict[str, Any] = Field(default_factory=dict)
    voice: RuntimeInteractionVoiceData | dict[str, Any] = Field(default_factory=dict)


class RuntimeInteractionReplayData(ContractModel):
    workspace: str | None = None
    workflow_id: str = ""
    job_id: str = ""
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    terminal_output: list[RuntimeInteractionEventData | dict[str, Any]] = Field(default_factory=list)
    repair_chain: list[dict[str, Any]] = Field(default_factory=list)
    approval_history: list[dict[str, Any]] = Field(default_factory=list)
    sessions: list[RuntimeSessionData | dict[str, Any]] = Field(default_factory=list)


class CollaborationDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    viewer: dict[str, Any] = Field(default_factory=dict)
    roles: list[dict[str, Any]] = Field(default_factory=list)
    members: list[dict[str, Any]] = Field(default_factory=list)
    shared_workflows: list[dict[str, Any]] = Field(default_factory=list)
    active_workflows: list[dict[str, Any]] = Field(default_factory=list)
    approval_queue: list[dict[str, Any]] = Field(default_factory=list)
    approval_history: list[dict[str, Any]] = Field(default_factory=list)
    roadmap_board: dict[str, Any] = Field(default_factory=dict)
    repositories: list[dict[str, Any]] = Field(default_factory=list)
    runtime_visibility: dict[str, Any] = Field(default_factory=dict)
    autopilot_governance: dict[str, Any] = Field(default_factory=dict)
    deployment_governance: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    privacy_controls: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    state_files: dict[str, Any] = Field(default_factory=dict)


class CollaborationRolesData(ContractModel):
    roles: list[dict[str, Any]] = Field(default_factory=list)
    governance: dict[str, Any] = Field(default_factory=dict)


class CollaborationMemberMutationData(ContractModel):
    workspace: str | None = None
    member: dict[str, Any] = Field(default_factory=dict)
    dashboard: CollaborationDashboardData | dict[str, Any] = Field(default_factory=dict)


class CollaborationRepositoryMutationData(ContractModel):
    workspace: str | None = None
    repository: dict[str, Any] = Field(default_factory=dict)
    dashboard: CollaborationDashboardData | dict[str, Any] = Field(default_factory=dict)


class CollaborationWorkflowMutationData(ContractModel):
    workspace: str | None = None
    workflow: dict[str, Any] = Field(default_factory=dict)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    approval: dict[str, Any] | None = None
    dashboard: CollaborationDashboardData | dict[str, Any] = Field(default_factory=dict)


class CollaborationApprovalMutationData(ContractModel):
    workspace: str | None = None
    approval: dict[str, Any] = Field(default_factory=dict)
    target_workflow: dict[str, Any] | None = None
    dashboard: CollaborationDashboardData | dict[str, Any] = Field(default_factory=dict)


class CollaborationRoadmapMutationData(ContractModel):
    workspace: str | None = None
    roadmap_item: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] | None = None
    dashboard: CollaborationDashboardData | dict[str, Any] = Field(default_factory=dict)


class CollaborationAuditData(ContractModel):
    workspace: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    event_count: int = 0


class DeploymentPipelineData(ContractModel):
    id: str = ""
    provider: str = ""
    path: str = ""
    name: str = ""
    trigger_summary: str = ""
    has_build: bool = False
    has_tests: bool = False
    has_lint: bool = False
    has_typecheck: bool = False
    has_deploy: bool = False
    deployment_target: str = ""
    risks: list[dict[str, Any]] = Field(default_factory=list)
    best_practice_gaps: list[str] = Field(default_factory=list)


class DeploymentWorkflowData(ContractModel):
    workflow_id: str = ""
    workflow_type: str = ""
    target_environment: str = ""
    release_version: str = ""
    status: str = ""
    created_at: str = ""
    updated_at: str = ""
    source_client: str = "unknown"
    dry_run: bool = True
    approval: bool = False
    production_confirmed: bool = False
    safety: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    rollback_strategy: dict[str, Any] = Field(default_factory=dict)


class DeploymentDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    environment: dict[str, Any] = Field(default_factory=dict)
    pipelines: list[DeploymentPipelineData | dict[str, Any]] = Field(default_factory=list)
    infrastructure: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    workflows: list[DeploymentWorkflowData | dict[str, Any]] = Field(default_factory=list)
    active_workflows: list[DeploymentWorkflowData | dict[str, Any]] = Field(default_factory=list)
    release_history: list[dict[str, Any]] = Field(default_factory=list)
    rollback_readiness: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    plugin_hooks: dict[str, Any] = Field(default_factory=dict)
    safety_controls: dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, Any] = Field(default_factory=dict)


class DeploymentPipelineValidationData(ContractModel):
    workspace: str | None = None
    pipeline_id: str = ""
    dry_run: bool = True
    ok: bool = False
    evaluated_at: str = ""
    evaluations: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    recommended_validations: list[dict[str, Any]] = Field(default_factory=list)
    deployment_readiness: dict[str, Any] = Field(default_factory=dict)
    writes_performed: bool = False


class DeploymentWorkflowMutationData(ContractModel):
    workspace: str | None = None
    workflow: DeploymentWorkflowData | dict[str, Any] = Field(default_factory=dict)
    dashboard: dict[str, Any] = Field(default_factory=dict)


class DeploymentReleaseHistoryData(ContractModel):
    workspace: str | None = None
    release_history: list[dict[str, Any]] = Field(default_factory=list)
    active_workflows: list[DeploymentWorkflowData | dict[str, Any]] = Field(default_factory=list)
    rollback_readiness: dict[str, Any] = Field(default_factory=dict)
    release_notes_draft: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)


class DeploymentObservabilityData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    workflow_count: int = 0
    active_workflows: int = 0
    completed_workflows: int = 0
    failed_workflows: int = 0
    rollback_workflows: int = 0
    release_count: int = 0
    deployment_successes: int = 0
    deployment_failures: int = 0
    rollback_count: int = 0
    pipeline_count: int = 0
    pipelines_with_risks: int = 0
    flaky_validation_candidates: list[str] = Field(default_factory=list)
    recurring_deployment_failures: list[dict[str, Any]] = Field(default_factory=list)
    risk_count: int = 0


class OptimizationExperimentData(ContractModel):
    experiment_id: str = ""
    target_area: str = ""
    hypothesis: str = ""
    status: str = "proposal"
    rollout_stage: str = "proposal"
    created_at: str = ""
    updated_at: str = ""
    source_client: str = "unknown"
    sandbox: bool = True
    approval: bool = False
    variants: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_suite_ids: list[str] = Field(default_factory=list)
    baseline_metrics: dict[str, Any] = Field(default_factory=dict)
    latest_result: dict[str, Any] = Field(default_factory=dict)
    adoption: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


class OptimizationDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    experiments: list[OptimizationExperimentData | dict[str, Any]] = Field(default_factory=list)
    active_experiments: list[OptimizationExperimentData | dict[str, Any]] = Field(default_factory=list)
    adopted_optimizations: list[dict[str, Any]] = Field(default_factory=list)
    regression_warnings: list[dict[str, Any]] = Field(default_factory=list)
    staged_rollout: dict[str, Any] = Field(default_factory=dict)
    self_analysis: dict[str, Any] = Field(default_factory=dict)
    safety_controls: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, Any] = Field(default_factory=dict)


class OptimizationExperimentMutationData(ContractModel):
    workspace: str | None = None
    experiment: OptimizationExperimentData | dict[str, Any] = Field(default_factory=dict)
    dashboard: dict[str, Any] = Field(default_factory=dict)


class OptimizationRecommendationsData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    safety: str = ""


class OptimizationObservabilityData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    experiment_count: int = 0
    active_experiments: int = 0
    adopted_count: int = 0
    rolled_back_count: int = 0
    regression_count: int = 0
    targets: dict[str, Any] = Field(default_factory=dict)
    average_candidate_score: float = 0.0
    workflow_efficiency_score: int = 0
    bottlenecks: list[dict[str, Any]] = Field(default_factory=list)
    audit_path: str = ""


class StabilizationAuditData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    repo_root: str = ""
    generated_at: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    refactor_candidates: list[dict[str, Any]] = Field(default_factory=list)
    standardization: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    startup_recovery: dict[str, Any] = Field(default_factory=dict)
    security_posture: dict[str, Any] = Field(default_factory=dict)
    performance_scalability: dict[str, Any] = Field(default_factory=dict)
    testing_strategy: dict[str, Any] = Field(default_factory=dict)
    release_candidate_checklist: list[dict[str, Any]] = Field(default_factory=list)
    roadmap_classification: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    freeze_priorities: list[dict[str, Any]] = Field(default_factory=list)
    state_files: dict[str, Any] = Field(default_factory=dict)


class StabilizationGovernanceData(ContractModel):
    api_stability: list[str] = Field(default_factory=list)
    subsystem_ownership: list[dict[str, Any]] = Field(default_factory=list)
    migration_policy: list[str] = Field(default_factory=list)
    deprecation_policy: list[str] = Field(default_factory=list)
    security_review_required_for: list[str] = Field(default_factory=list)
    release_freeze_rules: list[str] = Field(default_factory=list)


class StabilizationRoadmapData(ContractModel):
    production_ready: list[dict[str, str]] = Field(default_factory=list)
    experimental: list[dict[str, str]] = Field(default_factory=list)
    prototype: list[dict[str, str]] = Field(default_factory=list)
    deprecated: list[dict[str, str]] = Field(default_factory=list)
    planned: list[dict[str, str]] = Field(default_factory=list)


class ProductIdentityData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    product: dict[str, Any] = Field(default_factory=dict)
    is_: list[str] = Field(default_factory=list, alias="is")
    is_not: list[str] = Field(default_factory=list)
    target_users: list[dict[str, Any]] = Field(default_factory=list)
    primary_workflows: list[str] = Field(default_factory=list)
    supported_environments: list[str] = Field(default_factory=list)
    local_first_philosophy: dict[str, Any] = Field(default_factory=dict)
    privacy_security_positioning: list[str] = Field(default_factory=list)
    terminology: dict[str, str] = Field(default_factory=dict)
    client_positioning: dict[str, str] = Field(default_factory=dict)


class ProductFeatureCatalogData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    classification: dict[str, Any] = Field(default_factory=dict)
    default_visible_categories: list[str] = Field(default_factory=list)
    hidden_by_default: list[str] = Field(default_factory=list)
    product_rule: str = ""


class ProductModeCatalogData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    default_mode: str = ""
    recommended_daily_mode: str = ""
    modes: list[dict[str, Any]] = Field(default_factory=list)


class ProductWorkflowCatalogData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    workflow_order: list[str] = Field(default_factory=list)
    simplification_rule: str = ""


class ProductShowcaseData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    showcase_workflows: list[dict[str, Any]] = Field(default_factory=list)


class ProductLaunchScopeData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    recommended_launch_scope: dict[str, Any] = Field(default_factory=dict)
    showcase_workflows: list[dict[str, Any]] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    launch_readiness_gates: list[str] = Field(default_factory=list)


class ProductRoadmapData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    stable_roadmap: list[str] = Field(default_factory=list)
    experimental_roadmap: list[str] = Field(default_factory=list)
    research_ideas: list[str] = Field(default_factory=list)
    future_concepts: list[str] = Field(default_factory=list)
    governance_rule: str = ""


class DogfoodingWorkflowsData(ContractModel):
    schema_version: int = 1
    generated_at: str = ""
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    core_workflow_catalog: list[dict[str, Any]] = Field(default_factory=list)
    dogfooding_rule: str = ""


class DogfoodingFrictionData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    pain_points: list[dict[str, Any]] = Field(default_factory=list)
    workflow_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    repeated_actions: list[dict[str, Any]] = Field(default_factory=list)
    abandoned_workflows: list[dict[str, Any]] = Field(default_factory=list)
    local_only: bool = True
    privacy: str = ""


class DogfoodingConfidenceData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    score: int = 0
    status: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    event_counts: dict[str, Any] = Field(default_factory=dict)
    sample_size: int = 0
    confidence_warning: str = ""


class DogfoodingLongSessionPlanData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    record_events: list[str] = Field(default_factory=list)
    pass_condition: str = ""


class DogfoodingDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    event_count: int = 0
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    workflows: dict[str, Any] = Field(default_factory=dict)
    friction: DogfoodingFrictionData | dict[str, Any] = Field(default_factory=dict)
    confidence: DogfoodingConfidenceData | dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    trust: dict[str, Any] = Field(default_factory=dict)
    ux_simplifications: list[dict[str, Any]] = Field(default_factory=list)
    systems_to_simplify: list[dict[str, Any]] = Field(default_factory=list)
    recommended_polish_priorities: list[dict[str, Any]] = Field(default_factory=list)
    long_session_plan: DogfoodingLongSessionPlanData | dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, Any] = Field(default_factory=dict)


class DogfoodingEventData(ContractModel):
    workspace: str | None = None
    event: dict[str, Any] = Field(default_factory=dict)
    dashboard: DogfoodingDashboardData | dict[str, Any] = Field(default_factory=dict)


class EngineeringWorkspaceMapData(ContractModel):
    workspace: str | None = None
    file_count: int = 0
    language_mix: dict[str, Any] = Field(default_factory=dict)
    frameworks: list[Any] = Field(default_factory=list)
    entry_points: list[Any] = Field(default_factory=list)
    build_files: list[Any] = Field(default_factory=list)
    services: list[dict[str, Any]] = Field(default_factory=list)
    dependency_visualization: dict[str, Any] = Field(default_factory=dict)
    service_relationships: dict[str, Any] = Field(default_factory=dict)
    impact_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    graph_version: str | None = None
    indexing: dict[str, Any] = Field(default_factory=dict)


class EngineeringWorkspaceSearchData(ContractModel):
    workspace: str | None = None
    query: str = ""
    mode: str = "architecture"
    mode_description: str = ""
    results: list[dict[str, Any]] = Field(default_factory=list)
    relationship_focus: str = ""
    relationships: dict[str, Any] = Field(default_factory=dict)
    impact: dict[str, Any] | None = None
    suggested_next_actions: list[str] = Field(default_factory=list)
    semantic_note: str = ""


class EngineeringWorkspaceValidationData(ContractModel):
    workspace: str | None = None
    command_count: int = 0
    commands: list[dict[str, Any]] = Field(default_factory=list)
    latest_gate: dict[str, Any] | None = None
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    validation_prioritization: list[dict[str, Any]] = Field(default_factory=list)
    repair_explanations: list[dict[str, Any]] = Field(default_factory=list)
    root_cause_candidates: list[dict[str, Any]] = Field(default_factory=list)
    regression_detection: dict[str, Any] = Field(default_factory=dict)
    validation_bottlenecks: list[Any] = Field(default_factory=list)
    recommended_next_validation: dict[str, Any] = Field(default_factory=dict)


class EngineeringWorkspaceContinuityData(ContractModel):
    workspace: str | None = None
    active_workflow_count: int = 0
    workflow_count: int = 0
    resume_candidates: list[dict[str, Any]] = Field(default_factory=list)
    roadmap_continuation: dict[str, Any] = Field(default_factory=dict)
    branch_aware_workflows: dict[str, Any] = Field(default_factory=dict)
    checkpoint_linking: dict[str, Any] = Field(default_factory=dict)
    interrupted_work: list[dict[str, Any]] = Field(default_factory=list)


class EngineeringWorkspaceBenchmarksData(ContractModel):
    suites: list[dict[str, Any]] = Field(default_factory=list)
    latest: dict[str, Any] | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    comparison_targets: list[dict[str, Any]] = Field(default_factory=list)


class EngineeringWorkspaceDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    product: str = "Auralith Engineering Workspace"
    positioning: str = ""
    workflow_lanes: list[dict[str, Any]] = Field(default_factory=list)
    project_map: EngineeringWorkspaceMapData | dict[str, Any] = Field(default_factory=dict)
    architecture: dict[str, Any] = Field(default_factory=dict)
    advanced_search: list[dict[str, Any]] = Field(default_factory=list)
    validation: EngineeringWorkspaceValidationData | dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    large_project: dict[str, Any] = Field(default_factory=dict)
    continuity: EngineeringWorkspaceContinuityData | dict[str, Any] = Field(default_factory=dict)
    dashboards: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    benchmark_comparisons: EngineeringWorkspaceBenchmarksData | dict[str, Any] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    state_files: dict[str, Any] = Field(default_factory=dict)


class AlphaFeatureFlagsData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    release_channel: str = "beta"
    flags: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    state_path: str = ""


class AlphaFeatureClassificationData(ContractModel):
    stable_features: list[str] = Field(default_factory=list)
    beta_features: list[str] = Field(default_factory=list)
    experimental_features: list[str] = Field(default_factory=list)
    hidden_internal_systems: list[str] = Field(default_factory=list)
    disabled_by_default_systems: list[str] = Field(default_factory=list)


class AlphaObservabilityData(ContractModel):
    workspace: str | None = None
    crash_frequency: int = 0
    failed_workflows: int = 0
    plugin_failures: int = 0
    onboarding_failures: int = 0
    rollback_frequency: Any = None
    validation_failures: int = 0
    update_failures: int = 0
    feedback_count: int = 0
    feedback_hotspots: dict[str, Any] = Field(default_factory=dict)
    dogfooding_confidence: dict[str, Any] = Field(default_factory=dict)


class AlphaReadinessData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    alpha_phase: str = "controlled_external_alpha"
    ready: bool = False
    status: str = ""
    score: int = 0
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    feature_classification: AlphaFeatureClassificationData | dict[str, Any] = Field(default_factory=dict)
    feature_flags: AlphaFeatureFlagsData | dict[str, Any] = Field(default_factory=dict)
    alpha_safe_defaults: dict[str, Any] = Field(default_factory=dict)
    observability: AlphaObservabilityData | dict[str, Any] = Field(default_factory=dict)
    support_tooling: dict[str, Any] = Field(default_factory=dict)
    release_channels: dict[str, Any] = Field(default_factory=dict)
    handoff_summary: dict[str, Any] = Field(default_factory=dict)
    telemetry_controls: dict[str, Any] = Field(default_factory=dict)
    simulation_plan: dict[str, Any] = Field(default_factory=dict)
    highest_risk_systems: list[dict[str, Any]] = Field(default_factory=list)
    recommended_alpha_scope: dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, Any] = Field(default_factory=dict)


class AlphaDiagnosticsData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    privacy: str = ""
    security: dict[str, Any] = Field(default_factory=dict)
    release: dict[str, Any] = Field(default_factory=dict)
    onboarding: dict[str, Any] = Field(default_factory=dict)
    plugins: dict[str, Any] = Field(default_factory=dict)
    plugin_failures: dict[str, Any] = Field(default_factory=dict)
    distributed_runtime: dict[str, Any] = Field(default_factory=dict)
    runtime_interaction: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    quality_gates: dict[str, Any] = Field(default_factory=dict)
    workflows: dict[str, Any] = Field(default_factory=dict)
    dogfooding: dict[str, Any] = Field(default_factory=dict)
    workflow_replay: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class AlphaDiagnosticsExportData(ContractModel):
    workspace: str | None = None
    bundle: AlphaDiagnosticsData | dict[str, Any] = Field(default_factory=dict)
    path: str = ""
    persisted: bool = False
    privacy: dict[str, Any] = Field(default_factory=dict)


class AlphaFeedbackData(ContractModel):
    workspace: str | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class AlphaFeedbackSummaryData(ContractModel):
    workspace: str | None = None
    categories: list[str] = Field(default_factory=list)
    event_count: int = 0
    category_counts: dict[str, Any] = Field(default_factory=dict)
    severity_counts: dict[str, Any] = Field(default_factory=dict)
    recent_feedback: list[dict[str, Any]] = Field(default_factory=list)
    privacy: str = ""


class AlphaReleaseChannelsData(ContractModel):
    channels: list[dict[str, Any]] = Field(default_factory=list)
    default_alpha_channel: str = "beta"
    promotion_rules: list[str] = Field(default_factory=list)


class AlphaSimulationsData(ContractModel):
    workspace: str | None = None
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)


class PlatformGovernanceData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    purpose: str = ""
    api_stability_guarantees: list[str] = Field(default_factory=list)
    plugin_compatibility_guarantees: list[str] = Field(default_factory=list)
    deprecation_policy: dict[str, Any] = Field(default_factory=dict)
    migration_policy: dict[str, Any] = Field(default_factory=dict)
    versioning_policy: dict[str, Any] = Field(default_factory=dict)
    runtime_compatibility_windows: dict[str, Any] = Field(default_factory=dict)
    security_review_required_for: list[str] = Field(default_factory=list)
    governance_sources: dict[str, Any] = Field(default_factory=dict)


class PlatformMigrationData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    dry_run: bool = False
    applied: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[dict[str, Any]] = Field(default_factory=list)
    state_path: str = ""
    supported_categories: list[str] = Field(default_factory=list)
    recovery_guidance: list[str] = Field(default_factory=list)
    migration_count: int = 0


class PlatformCompatibilityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    compatible: bool = False
    overall_status: str = ""
    checks: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)
    state_path: str = ""


class PlatformOwnershipData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    subsystems: list[dict[str, Any]] = Field(default_factory=list)
    boundary_rules: list[str] = Field(default_factory=list)
    review_gates: dict[str, Any] = Field(default_factory=dict)


class PlatformDependenciesData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    plugin_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    provider_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    runtime_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    update_compatibility_risks: list[dict[str, Any]] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)


class PlatformReleaseEngineeringData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    reproducible_builds: dict[str, Any] = Field(default_factory=dict)
    release_verification: dict[str, Any] = Field(default_factory=dict)
    compatibility_matrix: list[dict[str, Any]] = Field(default_factory=list)
    staged_rollout_channels: list[dict[str, Any]] = Field(default_factory=list)
    rollback_requirements: list[str] = Field(default_factory=list)


class PlatformHealthData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    overall_status: str = ""
    subsystems: list[dict[str, Any]] = Field(default_factory=list)
    analytics: dict[str, Any] = Field(default_factory=dict)
    regression_watchlist: list[dict[str, Any]] = Field(default_factory=list)
    state_path: str = ""


class PlatformToolingData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    plugin_sdk: dict[str, Any] = Field(default_factory=dict)
    validators: list[dict[str, Any]] = Field(default_factory=list)
    runtime_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    developer_infrastructure: dict[str, Any] = Field(default_factory=dict)


class PlatformRoadmapData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    production_roadmap: list[str] = Field(default_factory=list)
    experimental_roadmap: list[str] = Field(default_factory=list)
    research_initiatives: list[str] = Field(default_factory=list)
    deprecated_systems: list[str] = Field(default_factory=list)
    ecosystem_initiatives: list[str] = Field(default_factory=list)
    promotion_rule: str = ""


class PlatformArchiveData(ContractModel):
    archive_id: str = ""
    workspace: str | None = None
    schema_version: str = ""
    created_at: str = ""
    dry_run: bool = False
    reason: str = ""
    includes: dict[str, Any] = Field(default_factory=dict)
    entry_count: int = 0
    entries: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    archive_path: str = ""
    recovery_guidance: list[str] = Field(default_factory=list)
    persisted: bool = False


class PlatformSustainabilityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    governance: PlatformGovernanceData | dict[str, Any] = Field(default_factory=dict)
    migrations: PlatformMigrationData | dict[str, Any] = Field(default_factory=dict)
    compatibility: PlatformCompatibilityData | dict[str, Any] = Field(default_factory=dict)
    ownership: PlatformOwnershipData | dict[str, Any] = Field(default_factory=dict)
    dependencies: PlatformDependenciesData | dict[str, Any] = Field(default_factory=dict)
    release_engineering: PlatformReleaseEngineeringData | dict[str, Any] = Field(default_factory=dict)
    health: PlatformHealthData | dict[str, Any] = Field(default_factory=dict)
    tooling: PlatformToolingData | dict[str, Any] = Field(default_factory=dict)
    roadmap: PlatformRoadmapData | dict[str, Any] = Field(default_factory=dict)
    archival: dict[str, Any] = Field(default_factory=dict)
    recommended_long_term_priorities: list[str] = Field(default_factory=list)


class EcosystemStrategyData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    core_audience: list[dict[str, Any]] = Field(default_factory=list)
    plugin_ecosystem_direction: list[str] = Field(default_factory=list)
    contributor_strategy: list[str] = Field(default_factory=list)
    positioning: dict[str, Any] = Field(default_factory=dict)
    local_first_privacy_positioning: list[str] = Field(default_factory=list)
    long_term_roadmap_themes: list[str] = Field(default_factory=list)


class EcosystemWorkflowExcellenceData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    priorities: list[str] = Field(default_factory=list)
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    workflow_statistics: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    improvement_backlog: list[dict[str, Any]] = Field(default_factory=list)


class EcosystemPluginQualityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    marketplace_foundation: dict[str, Any] = Field(default_factory=dict)
    compatibility_badges: dict[str, Any] = Field(default_factory=dict)
    permission_transparency: dict[str, Any] = Field(default_factory=dict)
    plugins: list[dict[str, Any]] = Field(default_factory=list)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    review_tools: list[dict[str, Any]] = Field(default_factory=list)


class EcosystemApiStabilityData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    stable_apis: list[str] = Field(default_factory=list)
    experimental_apis: list[str] = Field(default_factory=list)
    deprecated_apis: list[str] = Field(default_factory=list)
    stability_counts: dict[str, Any] = Field(default_factory=dict)
    stable_workflow_schemas: list[str] = Field(default_factory=list)
    stable_orchestration_contracts: list[str] = Field(default_factory=list)
    stable_plugin_contracts: list[str] = Field(default_factory=list)
    compatibility_guarantees: list[str] = Field(default_factory=list)
    stability_rule: str = ""


class EcosystemContributorData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    contributor_guides: list[str] = Field(default_factory=list)
    plugin_sdk_docs: dict[str, Any] = Field(default_factory=dict)
    subsystem_ownership_docs: str = ""
    debugging_guides: list[str] = Field(default_factory=list)
    architecture_maps: list[str] = Field(default_factory=list)
    sample_plugins_and_tools: list[str] = Field(default_factory=list)
    contribution_rules: list[str] = Field(default_factory=list)


class EcosystemReputationData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    release_quality_standards: list[str] = Field(default_factory=list)
    compatibility_guarantees: dict[str, Any] = Field(default_factory=dict)
    migration_guarantees: list[str] = Field(default_factory=list)
    rollback_reliability: list[str] = Field(default_factory=list)
    security_review_standards: list[str] = Field(default_factory=list)
    current_reputation_signals: dict[str, Any] = Field(default_factory=dict)


class EcosystemReleaseCadenceData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    channels: list[dict[str, Any]] = Field(default_factory=list)
    cadence: dict[str, Any] = Field(default_factory=dict)
    promotion_requirements: list[str] = Field(default_factory=list)


class EcosystemObservabilityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    plugin_health: dict[str, Any] = Field(default_factory=dict)
    workflow_success_rates: dict[str, Any] = Field(default_factory=dict)
    runtime_reliability: dict[str, Any] = Field(default_factory=dict)
    onboarding_success: dict[str, Any] = Field(default_factory=dict)
    ecosystem_compatibility_issues: list[dict[str, Any]] = Field(default_factory=list)
    local_first: bool = True


class EcosystemMaintainabilityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    reduce: list[str] = Field(default_factory=list)
    current_signals: dict[str, Any] = Field(default_factory=dict)
    recommended_refactors: list[str] = Field(default_factory=list)


class EcosystemShowcasesData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    showcases: list[dict[str, Any]] = Field(default_factory=list)
    demo_quality_bar: list[str] = Field(default_factory=list)


class EcosystemTrustData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    always_explain: list[str] = Field(default_factory=list)
    trust_surfaces: list[str] = Field(default_factory=list)
    local_cloud_disclosure: list[str] = Field(default_factory=list)
    rollback_expectation: str = ""


class EcosystemSustainabilityPlanData(ContractModel):
    schema_version: str = ""
    generated_at: str = ""
    long_term_maintenance: list[str] = Field(default_factory=list)
    compatibility_support_windows: dict[str, Any] = Field(default_factory=dict)
    plugin_migration_strategy: list[str] = Field(default_factory=list)
    governance_structure: list[str] = Field(default_factory=list)
    roadmap_review_process: list[str] = Field(default_factory=list)


class EcosystemMaturityData(ContractModel):
    workspace: str | None = None
    schema_version: str = ""
    generated_at: str = ""
    strategy: EcosystemStrategyData | dict[str, Any] = Field(default_factory=dict)
    workflow_excellence: EcosystemWorkflowExcellenceData | dict[str, Any] = Field(default_factory=dict)
    plugin_quality: EcosystemPluginQualityData | dict[str, Any] = Field(default_factory=dict)
    api_stability: EcosystemApiStabilityData | dict[str, Any] = Field(default_factory=dict)
    contributor_ecosystem: EcosystemContributorData | dict[str, Any] = Field(default_factory=dict)
    platform_reputation: EcosystemReputationData | dict[str, Any] = Field(default_factory=dict)
    release_cadence: EcosystemReleaseCadenceData | dict[str, Any] = Field(default_factory=dict)
    observability: EcosystemObservabilityData | dict[str, Any] = Field(default_factory=dict)
    maintainability: EcosystemMaintainabilityData | dict[str, Any] = Field(default_factory=dict)
    showcases: EcosystemShowcasesData | dict[str, Any] = Field(default_factory=dict)
    trust_transparency: EcosystemTrustData | dict[str, Any] = Field(default_factory=dict)
    sustainability_plan: EcosystemSustainabilityPlanData | dict[str, Any] = Field(default_factory=dict)
    maturity_scores: dict[str, Any] = Field(default_factory=dict)
    adoption_blockers: list[dict[str, Any]] = Field(default_factory=list)
    recommended_long_term_focus: list[str] = Field(default_factory=list)


class AutopilotModesData(ContractModel):
    modes: list[dict[str, Any]] = Field(default_factory=list)
    specializations: list[dict[str, Any]] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    default_mode: str = "semi_autonomous"
    default_specialization: str = "feature_autopilot"
    safety_invariants: list[str] = Field(default_factory=list)


class AutopilotRunData(ContractModel):
    run: dict[str, Any] = Field(default_factory=dict)
    supervision: dict[str, Any] = Field(default_factory=dict)
    modes: dict[str, Any] = Field(default_factory=dict)


class AutopilotListData(ContractModel):
    runs: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)


class AutopilotDashboardData(ContractModel):
    run: dict[str, Any] = Field(default_factory=dict)


class AutopilotActionData(ContractModel):
    run: dict[str, Any] = Field(default_factory=dict)
    supervision: dict[str, Any] = Field(default_factory=dict)
    event: dict[str, Any] | None = None


class AutopilotSupervisionData(ContractModel):
    active_run: dict[str, Any] | None = None
    active_workflow: str | None = None
    active_agent: str | None = None
    current_task: str | None = None
    files_being_modified: list[str] = Field(default_factory=list)
    specialization: str | None = None
    execution_strategy: dict[str, Any] = Field(default_factory=dict)
    validation_strategy: dict[str, Any] = Field(default_factory=dict)
    repair_strategy: dict[str, Any] = Field(default_factory=dict)
    model_routing: dict[str, Any] = Field(default_factory=dict)
    memory_scope: dict[str, Any] = Field(default_factory=dict)
    specialized_observability: dict[str, Any] = Field(default_factory=dict)
    specialization_benchmarks: list[str] = Field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    validation_status: str = "idle"
    repair_attempts: int = 0
    rollback_available: bool = False
    execution_risk_level: str = "none"
    confidence_score: int = 0
    validation_confidence: int = 0
    repair_confidence: int = 0
    regression_risk: int = 0
    rollback_readiness: int = 0
    trust_scorecard: dict[str, Any] = Field(default_factory=dict)
    predictions: dict[str, Any] = Field(default_factory=dict)
    validation_intelligence: dict[str, Any] = Field(default_factory=dict)
    checkpoint_intelligence: dict[str, Any] = Field(default_factory=dict)
    bounded_autonomy: dict[str, Any] = Field(default_factory=dict)
    explanations: list[dict[str, Any]] = Field(default_factory=list)
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    running_runs: list[dict[str, Any]] = Field(default_factory=list)
    paused_runs: list[dict[str, Any]] = Field(default_factory=list)
    failed_runs: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    runtime_status: dict[str, Any] = Field(default_factory=dict)
    client_actions: list[dict[str, Any]] = Field(default_factory=list)
    safety_visibility: dict[str, Any] = Field(default_factory=dict)


class AutopilotObservabilityData(ContractModel):
    run_count: int = 0
    active_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    workflow_completion_rate: float = 0.0
    validation_success_rate: float = 0.0
    repair_success_rate: float = 0.0
    rollback_frequency: int = 0
    approval_interruptions: int = 0
    average_confidence_score: float = 0.0
    average_regression_risk: float = 0.0
    blocked_action_count: int = 0
    average_execution_duration_seconds: float = 0.0
    failure_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    unstable_workflows: list[dict[str, Any]] = Field(default_factory=list)
    recurring_repair_failures: list[dict[str, Any]] = Field(default_factory=list)
    risky_execution_paths: list[dict[str, Any]] = Field(default_factory=list)
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    specialization_distribution: dict[str, int] = Field(default_factory=dict)
    specialization_benchmarks: dict[str, list[str]] = Field(default_factory=dict)
    mode_distribution: dict[str, int] = Field(default_factory=dict)
    workflow_distribution: dict[str, int] = Field(default_factory=dict)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class AutopilotMemoryData(ContractModel):
    memory: dict[str, Any] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)


class AutopilotReplayData(ContractModel):
    run: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    execution_timeline: dict[str, Any] = Field(default_factory=dict)
    validation_chain: list[dict[str, Any]] = Field(default_factory=list)
    repair_chain: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    decision_log: list[dict[str, Any]] = Field(default_factory=list)
    trust_scorecard: dict[str, Any] = Field(default_factory=dict)
    predictions: dict[str, Any] = Field(default_factory=dict)
    last_simulation: dict[str, Any] | None = None
    rollbacks: list[dict[str, Any]] = Field(default_factory=list)
    terminal_jobs: list[dict[str, Any]] = Field(default_factory=list)


class AutopilotClientHooksData(ContractModel):
    actions: list[dict[str, Any]] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    client_surfaces: dict[str, Any] = Field(default_factory=dict)
    contract_version: str = "1.0"


class RuntimeRecoveryData(ContractModel):
    workspace: str | None = None
    offline_node_ids: list[str] = Field(default_factory=list)
    requeued_workload_ids: list[str] = Field(default_factory=list)
    auto_dispatch: bool = False
    dispatch_results: list[dict[str, Any]] = Field(default_factory=list)
    dashboard: DistributedRuntimeData | dict[str, Any] = Field(default_factory=dict)


class RuntimeObservabilityData(ContractModel):
    workspace: str | None = None
    observability: dict[str, Any] = Field(default_factory=dict)
    audit_summary: dict[str, Any] = Field(default_factory=dict)
    recent_audit_events: list[RuntimeAuditEventData | dict[str, Any]] = Field(default_factory=list)


class RuntimeAuditData(ContractModel):
    workspace: str | None = None
    audit_events: list[RuntimeAuditEventData | dict[str, Any]] = Field(default_factory=list)
    audit_summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeDeploymentData(ContractModel):
    workspace: str | None = None
    node_type: str = "validation"
    shell: str = "powershell"
    base_url: str = ""
    script: str = ""
    requirements: list[str] = Field(default_factory=list)
    config_keys: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyData(ContractModel):
    policy_id: str = ""
    name: str = ""
    enabled: bool = True
    scope: str = "workspace"
    target: str = "workflow_execution"
    effect: str = "require_approval"
    severity: str = "medium"
    required_roles: list[str] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)
    compliance_tags: list[str] = Field(default_factory=list)
    rationale: str = ""
    custom: bool = False


class GovernanceDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    policies: list[GovernancePolicyData | dict[str, Any]] = Field(default_factory=list)
    policy_scopes: list[str] = Field(default_factory=list)
    policy_targets: list[str] = Field(default_factory=list)
    runtime_trust_levels: list[dict[str, Any]] = Field(default_factory=list)
    execution_boundaries: dict[str, Any] = Field(default_factory=dict)
    plugin_governance: dict[str, Any] = Field(default_factory=dict)
    runtime_node_governance: dict[str, Any] = Field(default_factory=dict)
    deployment_governance: dict[str, Any] = Field(default_factory=dict)
    approval_governance: dict[str, Any] = Field(default_factory=dict)
    security_governance: dict[str, Any] = Field(default_factory=dict)
    compliance: dict[str, Any] = Field(default_factory=dict)
    policy_violations: list[dict[str, Any]] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    state_files: dict[str, Any] = Field(default_factory=dict)
    ui_summary: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyCatalogData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    policies: list[GovernancePolicyData | dict[str, Any]] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    trust_levels: list[dict[str, Any]] = Field(default_factory=list)
    lifecycle: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyMutationData(ContractModel):
    workspace: str | None = None
    policy: GovernancePolicyData | dict[str, Any] = Field(default_factory=dict)
    dashboard: GovernanceDashboardData | dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyEvaluationData(ContractModel):
    evaluation_id: str = ""
    workspace: str | None = None
    evaluated_at: str = ""
    action_type: str = ""
    workflow_type: str = ""
    target: str = ""
    actor_id: str = ""
    actor_role: str = ""
    approval: bool = False
    dry_run: bool = True
    status: str = "allowed"
    allowed: bool = True
    policy_results: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    approval_requirements: list[dict[str, Any]] = Field(default_factory=list)
    restrictions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    compliance_tags: list[str] = Field(default_factory=list)
    explanation: str = ""


class GovernanceAuditData(ContractModel):
    workspace: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    audit_path: str = ""


class GovernanceComplianceExportData(ContractModel):
    workspace: str | None = None
    export: dict[str, Any] = Field(default_factory=dict)
    path: str = ""


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
    auth_methods: list[str] = Field(default_factory=list)
    default_auth_method: str = ""
    required_auth_method: str = ""
    credential_env_vars: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    context_window: int | None = None
    tool_support: bool = False
    vision_support: bool = False
    code_strength: str = "medium"
    reasoning_strength: str = "medium"
    latency_estimate: str = "unknown"
    cost_estimate: str = "unknown"
    privacy_level: str = "unknown"
    availability_status: str = "unknown"
    provider_reachable: bool = False
    rate_limit_or_error_state: str = "unknown"
    last_health_check: str | None = None
    last_successful_request: str | None = None
    supported_workflow_types: list[str] = Field(default_factory=list)
    models: list[dict[str, Any]] = Field(default_factory=list)


class ProviderInventoryData(ContractModel):
    mode: str = "local_only"
    local_only: bool = True
    credential_store_available: bool = False
    credential_store_healthy: bool = True
    credential_store_errors: list[dict[str, str]] = Field(default_factory=list)
    providers: list[ProviderData] = Field(default_factory=list)
    routing_profiles: list[dict[str, Any]] = Field(default_factory=list)


class ModelRegistryModelData(ContractModel):
    provider_id: str
    model_id: str
    display_name: str = ""
    type: str = "local"
    context_window: int | None = None
    tool_support: bool = False
    vision_support: bool = False
    code_strength: str = "medium"
    reasoning_strength: str = "medium"
    latency_estimate: str = "unknown"
    cost_estimate: str = "unknown"
    privacy_level: str = "unknown"
    availability_status: str = "unknown"
    required_auth_method: str = ""
    last_health_check: str | None = None
    supported_workflow_types: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    selected: bool = False


class ModelProviderStatusData(ContractModel):
    provider_id: str
    linked: str = "unlinked"
    key_present: bool = False
    auth_method_available: bool = False
    auth_methods: list[str] = Field(default_factory=list)
    required_auth_method: str = ""
    provider_reachable: bool = False
    availability_status: str = "unknown"
    rate_limit_or_error_state: str = "unknown"
    last_health_check: str | None = None
    last_successful_request: str | None = None
    privacy_level: str = "unknown"


class ModelRoutingProfileData(ContractModel):
    id: str
    label: str = ""
    description: str = ""
    privacy_mode: str = "local-first"
    cloud_allowed: bool = True
    priority: list[str] = Field(default_factory=list)


class ModelRegistryData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    mode: str = "local_only"
    active_profile: str = "local_only"
    routing_profiles: list[ModelRoutingProfileData | dict[str, Any]] = Field(default_factory=list)
    selected_model: ModelRegistryModelData | dict[str, Any] | None = None
    fallback_models: list[ModelRegistryModelData | dict[str, Any]] = Field(default_factory=list)
    providers: list[ProviderData | dict[str, Any]] = Field(default_factory=list)
    models: list[ModelRegistryModelData | dict[str, Any]] = Field(default_factory=list)
    provider_status: list[ModelProviderStatusData | dict[str, Any]] = Field(default_factory=list)
    credential_store_available: bool = False
    credential_store_healthy: bool = True
    credential_store_errors: list[dict[str, str]] = Field(default_factory=list)
    ollama: ModelsData | dict[str, Any] = Field(default_factory=dict)
    client_guidance: dict[str, Any] = Field(default_factory=dict)


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
    model_id: str = ""
    status: str = "available"
    reason: str = ""
    cost_warning: str | None = None
    privacy_level: str = "unknown"
    availability_status: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)
    code_strength: str = "medium"
    reasoning_strength: str = "medium"
    tool_support: bool = False
    vision_support: bool = False


class ModelRouteContextData(ContractModel):
    max_context_chars: int = 0
    included_files: list[str] = Field(default_factory=list)
    blocked_files: list[dict[str, str]] = Field(default_factory=list)
    included: list[dict[str, str]] = Field(default_factory=list)


class ModelRouteData(ContractModel):
    workspace: str | None = None
    task_type: str = "chat"
    workflow_type: str = "chat"
    difficulty: str = "simple"
    mode: str = "local_only"
    local_only: bool = True
    route_profile: ModelRoutingProfileData | dict[str, Any] = Field(default_factory=dict)
    route_profile_id: str = ""
    selected: ModelRouteCandidateData | dict[str, Any] = Field(default_factory=dict)
    fallback_order: list[ModelRouteCandidateData | dict[str, Any]] = Field(default_factory=list)
    fallback_chain: list[dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    cloud_ready: bool = False
    cloud_reason: str = ""
    required_capabilities: list[str] = Field(default_factory=list)
    missing_capability_warnings: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
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
    memory_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    memory_warnings: list[str] = Field(default_factory=list)


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
    memory_warning: str | None = None


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


class QualityGateData(ContractModel):
    id: str = ""
    label: str = ""
    status: str = "skipped"
    severity: str = "low"
    summary: str = ""
    blocks_apply: bool = False
    checked_at: str = ""


class QualityScorecardData(ContractModel):
    completion_score: int = 0
    validation_score: int = 0
    risk_score: int = 0
    confidence_score: int = 0
    repair_score: int = 0
    regression_risk: int = 0
    human_review_required: bool = False
    passed_gates: int = 0
    failed_gates: int = 0
    warning_gates: int = 0
    skipped_gates: int = 0


class QualityGateEvaluationData(ContractModel):
    id: str = ""
    project_id: str = ""
    workspace: str | None = None
    workflow_id: str | None = None
    validation_id: str | None = None
    created_at: str = ""
    status: str = "passed"
    apply_allowed: bool = True
    dry_run: bool = False
    checkpoint_id: str | None = None
    approval: bool = False
    gates: list[QualityGateData | dict[str, Any]] = Field(default_factory=list)
    scorecard: QualityScorecardData | dict[str, Any] = Field(default_factory=dict)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    file_count: int = 0
    validation: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    required_actions: list[str] = Field(default_factory=list)
    summary: str = ""


class QualityGateDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    latest: QualityGateEvaluationData | dict[str, Any] | None = None
    recent_runs: list[QualityGateEvaluationData | dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_history: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_suites: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)


class QualityBenchmarkRunData(ContractModel):
    id: str = ""
    project_id: str = ""
    workspace: str | None = None
    workflow_id: str | None = None
    created_at: str = ""
    suite_ids: list[str] = Field(default_factory=list)
    status: str = "not_run"
    score: float = 0.0
    results: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityBenchmarkDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    suites: list[dict[str, Any]] = Field(default_factory=list)
    history: list[QualityBenchmarkRunData | dict[str, Any]] = Field(default_factory=list)
    latest: QualityBenchmarkRunData | dict[str, Any] | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)


class EvaluationReportData(ContractModel):
    id: str = ""
    project_id: str = ""
    workspace: str | None = None
    workflow_id: str | None = None
    quality_run_id: str | None = None
    created_at: str = ""
    title: str = ""
    status: str = "passed"
    scorecard: dict[str, Any] = Field(default_factory=dict)
    what_changed: list[dict[str, Any]] = Field(default_factory=list)
    why_changed: str = ""
    tests_run: list[dict[str, Any]] = Field(default_factory=list)
    failures_found: list[dict[str, Any]] = Field(default_factory=list)
    repairs_attempted: list[dict[str, Any]] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    rollback_instructions: list[str] = Field(default_factory=list)
    quality_gate: QualityGateEvaluationData | dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""


class EvaluationReportsData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    reports: list[EvaluationReportData | dict[str, Any]] = Field(default_factory=list)
    latest: EvaluationReportData | dict[str, Any] | None = None


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
    semantic_index_path: str | None = None
    project_memory_path: str | None = None
    cache_hit: bool = False
    incremental: dict[str, Any] = Field(default_factory=dict)
    indexing: dict[str, Any] = Field(default_factory=dict)
    semantic_index: dict[str, Any] = Field(default_factory=dict)
    architecture_summary: dict[str, Any] = Field(default_factory=dict)
    project_memory: dict[str, Any] = Field(default_factory=dict)
    embedding_interfaces: dict[str, Any] = Field(default_factory=dict)


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


class KnowledgeSearchData(ContractModel):
    workspace: str | None = None
    query: str = ""
    node_type: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    graph_version: str | None = None
    indexing: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRelationshipsData(ContractModel):
    workspace: str | None = None
    focus: str = ""
    focus_node: dict[str, Any] | None = None
    relationships: list[str] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[KnowledgeEdgeData | dict[str, Any]] = Field(default_factory=list)
    graph_version: str | None = None


class KnowledgeSymbolData(ContractModel):
    workspace: str | None = None
    symbol: str = ""
    matches: list[dict[str, Any]] = Field(default_factory=list)
    graph_version: str | None = None


class KnowledgeImpactAnalysisData(ContractModel):
    workspace: str | None = None
    target: str = ""
    change_type: str = "modify"
    focus_node: dict[str, Any] | None = None
    affected_files: list[str] = Field(default_factory=list)
    likely_breakage_areas: list[dict[str, Any]] = Field(default_factory=list)
    modification_risk: dict[str, Any] = Field(default_factory=dict)
    validation_targets: list[dict[str, Any]] = Field(default_factory=list)
    related_workflows: list[dict[str, Any]] = Field(default_factory=list)
    relationship_edges: list[KnowledgeEdgeData | dict[str, Any]] = Field(default_factory=list)
    graph_version: str | None = None


class KnowledgeArchitectureSummaryData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    runtime_boundaries: list[dict[str, Any]] = Field(default_factory=list)
    build_systems: list[dict[str, Any]] = Field(default_factory=list)
    entry_points: list[Any] = Field(default_factory=list)
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    risk_areas: list[dict[str, Any]] = Field(default_factory=list)
    coding_conventions: list[dict[str, Any]] = Field(default_factory=list)
    indexing: dict[str, Any] = Field(default_factory=dict)
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
    memory_system: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)


class PersonalIntelligenceResetData(ContractModel):
    workspace: str | None = None
    reset: bool = False
    profile_path: str | None = None
    existed: bool | None = None
    error: str | None = None
    privacy: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryRecordData(ContractModel):
    id: str = ""
    version: int = 1
    category: str = "project_memory"
    scope: str = "project"
    title: str = ""
    content: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    source: str = "user"
    confidence: float = 0.8
    status: str = "active"
    pinned: bool = False
    expires_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    archived_at: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    redaction_count: int = 0
    fingerprint: str = ""
    warnings: list[str] = Field(default_factory=list)


class PersonalMemoryDashboardData(ContractModel):
    schema_version: int = 1
    workspace: str | None = None
    generated_at: str = ""
    categories: list[dict[str, Any]] = Field(default_factory=list)
    controls: dict[str, Any] = Field(default_factory=dict)
    records: list[PersonalMemoryRecordData | dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    export_endpoint: str = ""
    import_endpoint: str = ""
    audit_events: list[dict[str, Any]] = Field(default_factory=list)


class PersonalMemoryMutationData(ContractModel):
    workspace: str | None = None
    record: PersonalMemoryRecordData | dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryDeleteData(ContractModel):
    workspace: str | None = None
    memory_id: str = ""
    deleted: bool = False
    hard_delete: bool = False
    observability: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryExportData(ContractModel):
    workspace: str | None = None
    export: dict[str, Any] = Field(default_factory=dict)
    record_count: int = 0


class PersonalMemoryImportData(ContractModel):
    workspace: str | None = None
    dry_run: bool = True
    merge_strategy: str = "append"
    imported_count: int = 0
    preview_count: int = 0
    records: list[PersonalMemoryRecordData | dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryControlsData(ContractModel):
    workspace: str | None = None
    controls: dict[str, Any] = Field(default_factory=dict)
    categories: list[dict[str, Any]] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryCleanupData(ContractModel):
    workspace: str | None = None
    dry_run: bool = True
    expired_ids: list[str] = Field(default_factory=list)
    stale_ids: list[str] = Field(default_factory=list)
    observability: dict[str, Any] = Field(default_factory=dict)


class PersonalMemoryObservabilityData(ContractModel):
    workspace: str | None = None
    observability: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    audit_summary: dict[str, Any] = Field(default_factory=dict)
    recent_audit_events: list[dict[str, Any]] = Field(default_factory=list)


class PersonalMemoryContextData(ContractModel):
    workspace: str | None = None
    workflow_type: str = ""
    objective: str = ""
    records: list[PersonalMemoryRecordData | dict[str, Any]] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0


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
    plugins: dict[str, Any] = Field(default_factory=dict)
    distributed_runtime: dict[str, Any] = Field(default_factory=dict)
    personal_memory: dict[str, Any] = Field(default_factory=dict)
    runtime_interaction: dict[str, Any] = Field(default_factory=dict)
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


class ChangePreviewData(ContractModel):
    change_id: str = ""
    path: str = ""
    action: Literal["create", "update", "append", "delete"] = "update"
    summary: str = ""
    exists: bool = False
    before_bytes: int = 0
    after_bytes: int = 0
    delta_bytes: int = 0
    patch: str = ""
    patch_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class ProposedChangeData(ContractModel):
    id: str
    action: Literal["create", "update", "append", "delete"] = "update"
    path: str
    content: str | None = None
    summary: str = ""
    selected: bool = False
    status: str | None = None


class ChangeProposalRecordData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    summary: str = ""
    risk: str = "unknown"
    source_task_id: str | None = None
    source_client: str = "unknown"
    status: str = "proposed"
    created_at: str = ""
    updated_at: str = ""
    files: list[ProposedChangeData | dict[str, Any]] = Field(default_factory=list)
    preview: list[ChangePreviewData | dict[str, Any]] = Field(default_factory=list)
    repair_attempt: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None


class ChangesProposeData(ContractModel):
    ok: bool = True
    workspace: str | None = None
    project_id: str = ""
    proposal: ChangeProposalRecordData | dict[str, Any] = Field(default_factory=dict)
    preview: list[ChangePreviewData | dict[str, Any]] = Field(default_factory=list)
    job_id: str | None = None
    task_id: str | None = None
    activity_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CheckpointFileData(ContractModel):
    path: str = ""
    state: str = "missing"


class CheckpointRecordData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    created_at: str = ""
    summary: str = ""
    file_count: int = 0
    present_count: int = 0
    missing_count: int = 0
    files: list[CheckpointFileData | dict[str, Any]] = Field(default_factory=list)
    checkpoint_path: str | None = None
    job_id: str | None = None
    source_task_id: str | None = None


class ChangesApplyData(ContractModel):
    ok: bool = False
    workspace: str | None = None
    project_id: str = ""
    proposal_id: str | None = None
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked: bool = False
    quality_gate: dict[str, Any] = Field(default_factory=dict)
    checkpoint_id: str | None = None
    checkpoint: CheckpointRecordData | dict[str, Any] | None = None
    dry_run: bool = False
    preview: list[ChangePreviewData | dict[str, Any]] = Field(default_factory=list)
    job_id: str | None = None
    task_id: str | None = None
    activity_id: str | None = None
    repair_attempt: dict[str, Any] = Field(default_factory=dict)


class CheckpointsListData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    checkpoints: list[CheckpointRecordData | dict[str, Any]] = Field(default_factory=list)


class CheckpointRestoreData(ContractModel):
    ok: bool = False
    workspace: str | None = None
    project_id: str = ""
    checkpoint_id: str | None = None
    restored: list[str] = Field(default_factory=list)
    dry_run: bool = False
    pre_restore_checkpoint_id: str | None = None
    job_id: str | None = None
    task_id: str | None = None
    activity_id: str | None = None
    preview: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationRunData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    created_at: str = ""
    job_id: str | None = None
    task_id: str | None = None
    source_client: str = "unknown"
    dry_run: bool = False
    validation: ValidationData | dict[str, Any] = Field(default_factory=dict)
    repair_attempt: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    activity_id: str | None = None


class CoreOperationJobData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    kind: str = ""
    status: str = "running"
    ok: bool | None = None
    source_client: str = "unknown"
    task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    started_at: str = ""
    finished_at: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class CoreJobLookupData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    job: CoreOperationJobData | dict[str, Any] = Field(default_factory=dict)


class ProjectActivityEntryData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    event: str = ""
    summary: str = ""
    created_at: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ProjectActivityData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    activity: list[ProjectActivityEntryData | dict[str, Any]] = Field(default_factory=list)


class WorkflowTaskData(ContractModel):
    id: str
    workflow_id: str = ""
    key: str = ""
    title: str = ""
    status: str = "pending"
    order: int | None = None
    parent_id: str | None = None
    child_task_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    agent_role: str = "planner"
    agent_id: str | None = None
    agent_profile: dict[str, Any] = Field(default_factory=dict)
    execution_mode: str = "manual"
    approval_gates: list[str] = Field(default_factory=list)
    memory_scope: dict[str, Any] = Field(default_factory=dict)
    context_policy: dict[str, Any] = Field(default_factory=dict)
    communication_contract: dict[str, Any] = Field(default_factory=dict)
    model_profile: dict[str, Any] = Field(default_factory=dict)
    progress: int = 0
    retry_count: int = 0
    max_retries: int = 0
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WorkflowData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    workflow_type: str = ""
    objective: str = ""
    source_client: str = "unknown"
    status: str = "queued"
    progress: int = 0
    active_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    context_files: list[str] = Field(default_factory=list)
    blocked_context: list[dict[str, str]] = Field(default_factory=list)
    tasks: list[WorkflowTaskData | dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    agent_roles: list[dict[str, Any]] = Field(default_factory=list)
    agent_runtime_version: str | None = None
    agent_coordination: dict[str, Any] = Field(default_factory=dict)
    agent_observability: dict[str, Any] = Field(default_factory=dict)
    handoffs: list[dict[str, Any]] = Field(default_factory=list)
    failure_escalations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowEventData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    workflow_id: str | None = None
    workflow_type: str | None = None
    event: str = ""
    summary: str = ""
    created_at: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    workflow: WorkflowData | dict[str, Any] = Field(default_factory=dict)
    timeline: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    agent_runtime: dict[str, Any] = Field(default_factory=dict)
    agent_coordination: dict[str, Any] = Field(default_factory=dict)


class WorkflowListData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    workflows: list[WorkflowData | dict[str, Any]] = Field(default_factory=list)
    active_workflows: list[WorkflowData | dict[str, Any]] = Field(default_factory=list)


class WorkflowActionData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    workflow: WorkflowData | dict[str, Any] = Field(default_factory=dict)
    event: WorkflowEventData | dict[str, Any] = Field(default_factory=dict)
    timeline: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)


class AgentCoordinationData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    workflow_id: str = ""
    workflow_type: str | None = None
    active_agents: list[dict[str, Any]] = Field(default_factory=list)
    agents: list[dict[str, Any]] = Field(default_factory=list)
    task_ownership: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    handoff_chain: list[dict[str, Any]] = Field(default_factory=list)
    workflow_graph: dict[str, Any] = Field(default_factory=dict)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    execution_timeline: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)
    context_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    communication: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    supervision: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


class ClientSyncRecordData(ContractModel):
    client_id: str
    client_type: str = "unknown"
    name: str = "Unknown Client"
    version: str = "unknown"
    workspace: str | None = None
    project_id: str = ""
    capabilities: list[str] = Field(default_factory=list)
    active_workflow_id: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_seen: str = ""


class ClientSyncData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    client: ClientSyncRecordData | dict[str, Any] = Field(default_factory=dict)
    event: WorkflowEventData | dict[str, Any] = Field(default_factory=dict)


class ClientSyncDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    active_clients: list[ClientSyncRecordData | dict[str, Any]] = Field(default_factory=list)
    active_workflows: list[WorkflowData | dict[str, Any]] = Field(default_factory=list)
    recent_operations: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)
    workspace_activity_feed: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)


class WorkspaceIntelligenceData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    cache_hit: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    frameworks: list[str] = Field(default_factory=list)
    languages: dict[str, int] = Field(default_factory=dict)
    file_index: dict[str, Any] = Field(default_factory=dict)
    semantic_summaries: dict[str, Any] = Field(default_factory=dict)
    project_metadata: dict[str, Any] = Field(default_factory=dict)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    symbol_index: dict[str, Any] = Field(default_factory=dict)
    build_systems: list[dict[str, Any]] = Field(default_factory=list)
    health: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)
    memory_paths: dict[str, str] = Field(default_factory=dict)


class EngineeringContextAssemblyData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "generate_feature"
    token_budget: int = 24000
    estimated_chars: int = 0
    estimated_tokens: int = 0
    budget_used_percent: float = 0.0
    candidate_count: int = 0
    selected_context: list[dict[str, Any]] = Field(default_factory=list)
    excluded_context: list[dict[str, Any]] = Field(default_factory=list)
    blocked_context: list[dict[str, Any]] = Field(default_factory=list)
    context_groups: dict[str, Any] = Field(default_factory=dict)
    token_efficiency: dict[str, Any] = Field(default_factory=dict)
    assembly_strategy: dict[str, Any] = Field(default_factory=dict)


class EngineeringValidationIntelligenceData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "generate_feature"
    strategy: str = ""
    detected_commands: list[dict[str, Any]] = Field(default_factory=list)
    impact_validation_targets: list[dict[str, Any]] = Field(default_factory=list)
    prioritized_validations: list[dict[str, Any]] = Field(default_factory=list)
    validation_confidence: dict[str, Any] = Field(default_factory=dict)
    regression_prediction: dict[str, Any] = Field(default_factory=dict)
    flaky_test_detection: dict[str, Any] = Field(default_factory=dict)
    escalation_rules: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""


class EngineeringRepairIntelligenceData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "repair_project"
    latest_validation: dict[str, Any] = Field(default_factory=dict)
    root_cause_candidates: list[dict[str, Any]] = Field(default_factory=list)
    strategy_selection: list[dict[str, Any]] = Field(default_factory=list)
    failed_repair_detection: dict[str, Any] = Field(default_factory=dict)
    architecture_aware_scope: dict[str, Any] = Field(default_factory=dict)
    rollback_recommendation: dict[str, Any] = Field(default_factory=dict)
    repair_confidence: dict[str, Any] = Field(default_factory=dict)
    stopping_conditions: list[str] = Field(default_factory=list)
    explanation: str = ""


class EngineeringRoadmapIntelligenceData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "continue_roadmap"
    task_decomposition: list[dict[str, Any]] = Field(default_factory=list)
    dependency_planning: dict[str, Any] = Field(default_factory=dict)
    milestone_prediction: dict[str, Any] = Field(default_factory=dict)
    risk_estimation: dict[str, Any] = Field(default_factory=dict)
    architecture_aware_planning: dict[str, Any] = Field(default_factory=dict)
    memory_guidance: list[str] = Field(default_factory=list)
    explanation: str = ""


class EngineeringWorkflowPredictionData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "generate_feature"
    execution_risk: dict[str, Any] = Field(default_factory=dict)
    likely_failures: list[dict[str, Any]] = Field(default_factory=list)
    validation_scope: dict[str, Any] = Field(default_factory=dict)
    rollback_probability: float = 0.0
    deployment_risk: dict[str, Any] = Field(default_factory=dict)
    duration_estimate: dict[str, Any] = Field(default_factory=dict)
    execution_reliability: dict[str, Any] = Field(default_factory=dict)
    prediction_confidence: dict[str, Any] = Field(default_factory=dict)


class EngineeringIntelligenceData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    workflow_type: str = "generate_feature"
    workflow_profile: dict[str, Any] = Field(default_factory=dict)
    objective: str = ""
    focus: str = ""
    target_files: list[str] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    architecture_reasoning: dict[str, Any] = Field(default_factory=dict)
    context_assembly: EngineeringContextAssemblyData | dict[str, Any] = Field(default_factory=dict)
    validation_intelligence: EngineeringValidationIntelligenceData | dict[str, Any] = Field(default_factory=dict)
    repair_intelligence: EngineeringRepairIntelligenceData | dict[str, Any] = Field(default_factory=dict)
    roadmap_intelligence: EngineeringRoadmapIntelligenceData | dict[str, Any] = Field(default_factory=dict)
    workflow_prediction: EngineeringWorkflowPredictionData | dict[str, Any] = Field(default_factory=dict)
    knowledge_graph_intelligence: dict[str, Any] = Field(default_factory=dict)
    memory_intelligence: dict[str, Any] = Field(default_factory=dict)
    benchmarks: dict[str, Any] = Field(default_factory=dict)
    explainability: dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, str] = Field(default_factory=dict)


class EngineeringIntelligenceBenchmarkData(ContractModel):
    workspace: str | None = None
    benchmark_run: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_suites: list[dict[str, Any]] = Field(default_factory=list)
    trends: dict[str, Any] = Field(default_factory=dict)
    path: str = ""


class IntelligenceStackData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    local_first: bool = True
    components: list[dict[str, Any]] = Field(default_factory=list)
    architecture: dict[str, Any] = Field(default_factory=dict)
    model_lifecycle: dict[str, Any] = Field(default_factory=dict)
    retrieval_stack: dict[str, Any] = Field(default_factory=dict)
    routing_intelligence: dict[str, Any] = Field(default_factory=dict)
    orchestration_prediction: dict[str, Any] = Field(default_factory=dict)
    distributed_inference: dict[str, Any] = Field(default_factory=dict)
    dataset_foundations: dict[str, Any] = Field(default_factory=dict)
    benchmarking: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    ui_visibility: dict[str, Any] = Field(default_factory=dict)
    state_files: dict[str, str] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class IntelligenceModelLifecycleData(ContractModel):
    workspace: str | None = None
    action: str = "list"
    state: dict[str, Any] = Field(default_factory=dict)
    recommended_profiles: list[dict[str, Any]] = Field(default_factory=list)
    registry_snapshot: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    install_plan: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class IntelligenceRetrievalData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    query: str = ""
    index_status: dict[str, Any] = Field(default_factory=dict)
    semantic_index: dict[str, Any] = Field(default_factory=dict)
    graph_aware_retrieval: dict[str, Any] = Field(default_factory=dict)
    hybrid_retrieval: dict[str, Any] = Field(default_factory=dict)
    workspace_embeddings: dict[str, Any] = Field(default_factory=dict)
    memory_embeddings: dict[str, Any] = Field(default_factory=dict)
    architecture_embeddings: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    state_file: str = ""


class IntelligenceRoutingData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    workflow_type: str = "generate_feature"
    objective: str = ""
    component: dict[str, Any] = Field(default_factory=dict)
    selected_intelligence_model: dict[str, Any] = Field(default_factory=dict)
    route: dict[str, Any] = Field(default_factory=dict)
    routing_quality: dict[str, Any] = Field(default_factory=dict)
    fallback_chain: list[dict[str, Any]] = Field(default_factory=list)
    privacy: dict[str, Any] = Field(default_factory=dict)
    explanation: dict[str, Any] = Field(default_factory=dict)


class IntelligencePredictionData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "generate_feature"
    generated_at: str = ""
    prediction: dict[str, Any] = Field(default_factory=dict)
    lightweight_models: dict[str, Any] = Field(default_factory=dict)
    validation_classification: dict[str, Any] = Field(default_factory=dict)
    repair_classification: dict[str, Any] = Field(default_factory=dict)
    execution_guidance: list[str] = Field(default_factory=list)


class IntelligenceBenchmarkData(ContractModel):
    workspace: str | None = None
    benchmark_run: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_suites: list[dict[str, Any]] = Field(default_factory=list)
    trends: dict[str, Any] = Field(default_factory=dict)
    path: str = ""


class IntelligenceDatasetData(ContractModel):
    workspace: str | None = None
    generated_at: str = ""
    privacy: dict[str, Any] = Field(default_factory=dict)
    records: list[dict[str, Any]] = Field(default_factory=list)
    record_count: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    dataset_schema: dict[str, Any] = Field(default_factory=dict)
    export_path: str = ""


class IntelligenceDistributedInferenceData(ContractModel):
    workspace: str | None = None
    workflow_type: str = "generate_feature"
    model_id: str = ""
    dry_run: bool = True
    allow_remote: bool = False
    approval: bool = False
    workload: dict[str, Any] = Field(default_factory=dict)
    eligible_nodes: list[dict[str, Any]] = Field(default_factory=list)
    fallback: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class WorkflowStatisticsData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    workflow_count: int = 0
    active_workflow_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    workflow_type_counts: dict[str, int] = Field(default_factory=dict)
    average_duration_seconds: float | int | None = 0
    validation: dict[str, Any] = Field(default_factory=dict)
    repair: dict[str, Any] = Field(default_factory=dict)
    model_usage: dict[str, int] = Field(default_factory=dict)
    event_count: int = 0
    recent_events: list[WorkflowEventData | dict[str, Any]] = Field(default_factory=list)


class EngineeringStageData(ContractModel):
    id: str
    key: str = ""
    label: str = ""
    status: str = "pending"
    order: int = 0
    progress: int = 0
    depends_on: list[str] = Field(default_factory=list)
    approval_required: bool = False
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EngineeringSubtaskData(ContractModel):
    id: str
    execution_id: str = ""
    stage_key: str = ""
    title: str = ""
    status: str = "pending"
    order: int | None = None
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    agent_role: str = "planner"
    validation_checkpoint: bool = False
    repair_checkpoint: bool = False
    target_files: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class EngineeringExecutionData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    goal: str = ""
    mode: str = "safe_assisted"
    status: str = "queued"
    progress: int = 0
    active_stage_key: str | None = None
    workflow_id: str | None = None
    workflow_link: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    source_client: str = "unknown"
    stages: list[EngineeringStageData | dict[str, Any]] = Field(default_factory=list)
    subtasks: list[EngineeringSubtaskData | dict[str, Any]] = Field(default_factory=list)
    execution_graph: dict[str, Any] = Field(default_factory=dict)
    task_dependency_graph: dict[str, Any] = Field(default_factory=dict)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    workspace_memory: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    roadmap_link: dict[str, Any] = Field(default_factory=dict)
    validation_chain: list[dict[str, Any]] = Field(default_factory=list)
    repair_history: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    rollbacks: list[dict[str, Any]] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    journal: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EngineeringExecutionEventData(ContractModel):
    id: str
    project_id: str = ""
    workspace: str | None = None
    execution_id: str | None = None
    workflow_id: str | None = None
    mode: str | None = None
    event: str = ""
    summary: str = ""
    created_at: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class EngineeringExecutionDashboardData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    execution: EngineeringExecutionData | dict[str, Any] = Field(default_factory=dict)
    timeline: list[EngineeringExecutionEventData | dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)


class EngineeringExecutionListData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    executions: list[EngineeringExecutionData | dict[str, Any]] = Field(default_factory=list)
    active_executions: list[EngineeringExecutionData | dict[str, Any]] = Field(default_factory=list)


class EngineeringExecutionStepData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    execution: EngineeringExecutionData | dict[str, Any] = Field(default_factory=dict)
    event: EngineeringExecutionEventData | dict[str, Any] = Field(default_factory=dict)
    timeline: list[EngineeringExecutionEventData | dict[str, Any]] = Field(default_factory=list)


class EngineeringTimelineData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    execution_id: str = ""
    timeline: list[EngineeringExecutionEventData | dict[str, Any]] = Field(default_factory=list)
    stage_timeline: list[dict[str, Any]] = Field(default_factory=list)
    execution_graph: dict[str, Any] = Field(default_factory=dict)
    task_dependency_graph: dict[str, Any] = Field(default_factory=dict)
    validation_chain: list[dict[str, Any]] = Field(default_factory=list)
    repair_history: list[dict[str, Any]] = Field(default_factory=list)


class EngineeringMemoryData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    generated_at: str = ""
    cache_hit: bool = False
    architecture_summary: dict[str, Any] = Field(default_factory=dict)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    coding_conventions: list[dict[str, Any]] = Field(default_factory=list)
    framework_usage: list[dict[str, Any]] = Field(default_factory=list)
    entry_points: list[Any] = Field(default_factory=list)
    build_systems: list[dict[str, Any]] = Field(default_factory=list)
    risk_areas: list[dict[str, Any]] = Field(default_factory=list)
    generated_knowledge_summaries: dict[str, Any] = Field(default_factory=dict)
    validation_commands: list[dict[str, Any]] = Field(default_factory=list)
    memory_paths: dict[str, Any] = Field(default_factory=dict)


class EngineeringMetricsData(ContractModel):
    workspace: str | None = None
    project_id: str = ""
    execution_count: int = 0
    active_execution_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    mode_counts: dict[str, int] = Field(default_factory=dict)
    average_duration_seconds: float | int | None = 0
    validation: dict[str, Any] = Field(default_factory=dict)
    repair: dict[str, Any] = Field(default_factory=dict)
    average_iterations: float | int = 0
    model_usage: dict[str, int] = Field(default_factory=dict)
    model_usage_efficiency: dict[str, Any] = Field(default_factory=dict)
    files_modified_per_workflow: float | int = 0
    rollback_frequency: float | int = 0
    recent_events: list[EngineeringExecutionEventData | dict[str, Any]] = Field(default_factory=list)


class EngineeringModesData(ContractModel):
    modes: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


class AgentRuntimeData(ContractModel):
    runtime_version: str = ""
    workspace: str | None = None
    agents: list[dict[str, Any]] = Field(default_factory=list)
    roles: list[dict[str, Any]] = Field(default_factory=list)
    routing_profiles: list[dict[str, Any]] = Field(default_factory=list)
    coordination_rules: list[str] = Field(default_factory=list)
    communication_contracts: dict[str, Any] = Field(default_factory=dict)
    safety_controls: dict[str, Any] = Field(default_factory=dict)
    visualization_contracts: list[str] = Field(default_factory=list)
    persistence: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)


class ContractDescriptor(ContractModel):
    kind: str
    stability: ContractStability
    owner: Literal["aegis-core", "website-backend", "schema-only"] = "aegis-core"
    notes: str = ""


DataModel = TypeVar("DataModel", bound=ContractModel)


CONTRACTS: dict[str, ContractDescriptor] = {
    "health": ContractDescriptor(kind="health", stability="stable", notes="Core runtime health and Ollama health snapshot."),
    "release.manifest": ContractDescriptor(kind="release.manifest", stability="experimental", notes="Core-owned ecosystem version manifest with package metadata and compatibility rules."),
    "release.compatibility": ContractDescriptor(kind="release.compatibility", stability="experimental", notes="Client/Core/schema compatibility verdict for Website, Desktop, VS Code, and Visual Studio clients."),
    "release.migrations": ContractDescriptor(kind="release.migrations", stability="experimental", notes="Workspace release migration status for .aegis, config, database markers, and model registry state."),
    "release.migrations.run": ContractDescriptor(kind="release.migrations.run", stability="experimental", notes="Idempotent release migration execution with dry-run support and persisted migration records."),
    "release.update_plan": ContractDescriptor(kind="release.update_plan", stability="experimental", notes="Inspectable update launcher plan with checksum, backup, apply, smoke check, and rollback steps."),
    "security.status": ContractDescriptor(kind="security.status", stability="experimental", notes="Core-owned security, privacy, local API, credential, update, and audit status for trust surfaces."),
    "models": ContractDescriptor(kind="models", stability="stable", notes="Shared local model discovery and selected model status."),
    "model.registry": ContractDescriptor(kind="model.registry", stability="experimental", notes="Core-owned provider/model registry, capability catalog, provider status, and routing profile inventory."),
    "model.providers": ContractDescriptor(kind="model.providers", stability="experimental", notes="Hybrid model provider inventory without plaintext secrets."),
    "model.routing_profiles": ContractDescriptor(kind="model.routing_profiles", stability="experimental", notes="Core-owned model routing profiles and privacy/cost/capability priorities."),
    "model.route": ContractDescriptor(kind="model.route", stability="experimental", notes="Local-first route plan with cloud approval and sanitized context metadata."),
    "model.completion": ContractDescriptor(kind="model.completion", stability="experimental", notes="Gated local/cloud completion response; cloud calls require explicit approval."),
    "provider.key.status": ContractDescriptor(kind="provider.key.status", stability="experimental", notes="OS credential-store key mutation result without exposing secret values."),
    "settings": ContractDescriptor(kind="settings", stability="stable", notes="Shared Core runtime settings."),
    "settings.updated": ContractDescriptor(kind="settings.updated", stability="stable", notes="Shared Core runtime settings after update."),
    "onboarding.status": ContractDescriptor(kind="onboarding.status", stability="experimental", notes="Core-owned first-run setup wizard state, environment diagnostics, recovery cards, and safe defaults."),
    "onboarding.updated": ContractDescriptor(kind="onboarding.updated", stability="experimental", notes="Persisted Core onboarding progress and UI preferences under workspace .aegis state."),
    "onboarding.first_workflow": ContractDescriptor(kind="onboarding.first_workflow", stability="experimental", notes="Guided safe first workflow action for scan, roadmap, architecture, proposal, validation-only, and rollback readiness."),
    "settings.export": ContractDescriptor(kind="settings.export", stability="experimental", notes="Safe settings export without provider secrets, including privacy, runtime URL, UI preference, and workspace metadata."),
    "settings.import": ContractDescriptor(kind="settings.import", stability="experimental", notes="Safe settings import preview or apply for allowed Core config keys and onboarding UI preferences."),
    "plugin.dashboard": ContractDescriptor(kind="plugin.dashboard", stability="experimental", notes="Core-owned plugin runtime dashboard with discovery, validation, enablement state, tools, hooks, UI contracts, permissions, diagnostics, and observability."),
    "plugin.state": ContractDescriptor(kind="plugin.state", stability="experimental", notes="Plugin enable, disable, and trust state mutation with high-risk permission approval gates."),
    "plugin.tool.run": ContractDescriptor(kind="plugin.tool.run", stability="experimental", notes="Permission-checked plugin tool execution through whitelisted Core handlers; arbitrary plugin code remains isolated and blocked."),
    "plugin.hooks": ContractDescriptor(kind="plugin.hooks", stability="experimental", notes="Workflow, analyzer, validator, repair, roadmap, architecture, and UI extension hooks contributed by enabled plugins."),
    "distributed.runtime": ContractDescriptor(kind="distributed.runtime", stability="experimental", notes="Core-owned local-first runtime node registry, workload scheduling, trust, isolation, fallback, observability, and audit dashboard."),
    "distributed.nodes": ContractDescriptor(kind="distributed.nodes", stability="experimental", notes="Registered local, trusted remote, isolated worker, validation, indexing, and GPU/model runtime nodes."),
    "distributed.node.registered": ContractDescriptor(kind="distributed.node.registered", stability="experimental", notes="Runtime node registration with token or approval based trust classification."),
    "distributed.node.heartbeat": ContractDescriptor(kind="distributed.node.heartbeat", stability="experimental", notes="Runtime node health, workload, capability, model, and plugin heartbeat update."),
    "distributed.node.revoked": ContractDescriptor(kind="distributed.node.revoked", stability="experimental", notes="Runtime node revocation and workload fallback requeue result."),
    "distributed.workloads": ContractDescriptor(kind="distributed.workloads", stability="experimental", notes="Distributed workload queue for validation, indexing, model, plugin, repair, build, benchmark, and workflow jobs."),
    "distributed.workload.created": ContractDescriptor(kind="distributed.workload.created", stability="experimental", notes="Distributed workload creation under local Core authority."),
    "distributed.workload.lookup": ContractDescriptor(kind="distributed.workload.lookup", stability="experimental", notes="Single distributed workload lookup."),
    "distributed.workload.dispatch": ContractDescriptor(kind="distributed.workload.dispatch", stability="experimental", notes="Capability, trust, permission, and remote opt-in based workload dispatch result."),
    "distributed.workload.action": ContractDescriptor(kind="distributed.workload.action", stability="experimental", notes="Distributed workload retry, cancellation, or user action result."),
    "distributed.recovery": ContractDescriptor(kind="distributed.recovery", stability="experimental", notes="Offline node detection and workload requeue/fallback recovery result."),
    "distributed.observability": ContractDescriptor(kind="distributed.observability", stability="experimental", notes="Runtime node uptime, workload history, latency, failure, model, plugin, and audit metrics."),
    "distributed.audit": ContractDescriptor(kind="distributed.audit", stability="experimental", notes="Runtime node, scheduling, workload, trust, recovery, and security audit events."),
    "distributed.deployment": ContractDescriptor(kind="distributed.deployment", stability="experimental", notes="Runtime worker bootstrap and deployment contract for trusted nodes."),
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
    "quality.gates": ContractDescriptor(kind="quality.gates", stability="experimental", notes="Core-owned quality gate dashboard with recent gate runs, reports, benchmarks, blockers, and score history."),
    "quality.gates.evaluate": ContractDescriptor(kind="quality.gates.evaluate", stability="experimental", notes="Pre-apply gate evaluation for syntax, build/test/lint/type, security, dependency, file-change, rollback, and approval readiness."),
    "workflow.quality": ContractDescriptor(kind="workflow.quality", stability="experimental", notes="Quality gate history and evaluation reports linked to one workflow."),
    "quality.benchmarks": ContractDescriptor(kind="quality.benchmarks", stability="experimental", notes="Deterministic quality benchmark suites and recorded benchmark history."),
    "quality.benchmark.run": ContractDescriptor(kind="quality.benchmark.run", stability="experimental", notes="Run inspectable local quality benchmark suites against recent workflow and gate data."),
    "quality.evaluation_report": ContractDescriptor(kind="quality.evaluation_report", stability="experimental", notes="Workflow evaluation report with changes, validation, repairs, risks, and rollback instructions."),
    "quality.evaluation_reports": ContractDescriptor(kind="quality.evaluation_reports", stability="experimental", notes="Recent workflow evaluation reports for the workspace."),
    "knowledge.graph": ContractDescriptor(kind="knowledge.graph", stability="experimental", notes="Local semantic project knowledge graph across files, systems, APIs, tasks, docs, and history."),
    "knowledge.query": ContractDescriptor(kind="knowledge.query", stability="experimental", notes="Rule-based project knowledge graph query result."),
    "knowledge.search": ContractDescriptor(kind="knowledge.search", stability="experimental", notes="Keyword/semantic-ready search over Core workspace knowledge graph nodes."),
    "knowledge.relationships": ContractDescriptor(kind="knowledge.relationships", stability="experimental", notes="Relationship browsing around a file, symbol, API route, system, or graph node."),
    "knowledge.symbol": ContractDescriptor(kind="knowledge.symbol", stability="experimental", notes="Symbol lookup across classes, functions, methods, services, components, and APIs."),
    "knowledge.impact_analysis": ContractDescriptor(kind="knowledge.impact_analysis", stability="experimental", notes="Graph-driven modification impact, risk, validation target, and related workflow analysis."),
    "knowledge.architecture_summary": ContractDescriptor(kind="knowledge.architecture_summary", stability="experimental", notes="Workspace architecture summary, runtime boundaries, build systems, hotspots, risk areas, and indexing observability."),
    "simulation.change": ContractDescriptor(kind="simulation.change", stability="experimental", notes="Read-only change impact simulation, risk forecast, validation estimate, and rollback complexity."),
    "simulation.compare": ContractDescriptor(kind="simulation.compare", stability="experimental", notes="Read-only comparison of implementation scenarios by predicted risk, impact, validation cost, and rollback complexity."),
    "operations.dashboard": ContractDescriptor(kind="operations.dashboard", stability="experimental", notes="Read-only engineering operations dashboard for release planning, technical debt, lifecycle, scheduling, productivity, and cross-project coordination."),
    "personal.intelligence": ContractDescriptor(kind="personal.intelligence", stability="experimental", notes="Local-first adaptive engineering preferences, workflow patterns, style awareness, and user-controlled profile memory."),
    "personal.intelligence.reset": ContractDescriptor(kind="personal.intelligence.reset", stability="experimental", notes="Reset local personal engineering profile memory for one workspace."),
    "personal.memory": ContractDescriptor(kind="personal.memory", stability="experimental", notes="Auralith local-first memory dashboard with editable categories, records, timeline, controls, privacy, observability, and audit events."),
    "personal.memory.record": ContractDescriptor(kind="personal.memory.record", stability="experimental", notes="Create or update a transparent personal/project/workflow memory record."),
    "personal.memory.deleted": ContractDescriptor(kind="personal.memory.deleted", stability="experimental", notes="Soft or hard deletion of an inspectable memory record."),
    "personal.memory.export": ContractDescriptor(kind="personal.memory.export", stability="experimental", notes="User-controlled memory export bundle with optional sensitive-memory redaction."),
    "personal.memory.import": ContractDescriptor(kind="personal.memory.import", stability="experimental", notes="Dry-run capable memory import with append, upsert, or replace merge strategies."),
    "personal.memory.controls": ContractDescriptor(kind="personal.memory.controls", stability="experimental", notes="Memory category lifecycle, retention, orchestration, scope, privacy, and encryption controls."),
    "personal.memory.cleanup": ContractDescriptor(kind="personal.memory.cleanup", stability="experimental", notes="Dry-run capable expiration and stale-memory cleanup."),
    "personal.memory.observability": ContractDescriptor(kind="personal.memory.observability", stability="experimental", notes="Memory size, usage frequency, stale/conflicting memories, retrieval latency, and audit summary."),
    "personal.memory.context": ContractDescriptor(kind="personal.memory.context", stability="experimental", notes="Memory-aware orchestration context with scoped records and guidance for agents."),
    "runtime.interaction": ContractDescriptor(kind="runtime.interaction", stability="experimental", notes="Live local runtime interaction dashboard for terminal jobs, streams, sessions, voice contracts, safety controls, and replay."),
    "runtime.jobs": ContractDescriptor(kind="runtime.jobs", stability="experimental", notes="Local terminal job list with status, output tails, exit codes, and observability."),
    "runtime.job": ContractDescriptor(kind="runtime.job", stability="experimental", notes="Single terminal job lookup with stream events and process state."),
    "runtime.job.mutation": ContractDescriptor(kind="runtime.job.mutation", stability="experimental", notes="Terminal job launch, retry, cancel, dry-run, blocked, or completed mutation response."),
    "runtime.streams": ContractDescriptor(kind="runtime.streams", stability="experimental", notes="Replayable runtime event stream records for terminal output, workflow visibility, validation, repair, and status events."),
    "runtime.processes": ContractDescriptor(kind="runtime.processes", stability="experimental", notes="Active local subprocesses launched by the runtime interaction layer."),
    "runtime.sessions": ContractDescriptor(kind="runtime.sessions", stability="experimental", notes="Local-first collaboration/session dashboard for workflow spectators, participants, and approval delegation."),
    "runtime.session.mutation": ContractDescriptor(kind="runtime.session.mutation", stability="experimental", notes="Shared workflow session create/sync response."),
    "runtime.voice": ContractDescriptor(kind="runtime.voice", stability="experimental", notes="Push-to-talk, STT/TTS abstraction, provider-neutral voice command, and privacy readiness contract."),
    "runtime.voice.command": ContractDescriptor(kind="runtime.voice.command", stability="experimental", notes="Voice transcript routing result; no audio is stored by Core."),
    "runtime.replay": ContractDescriptor(kind="runtime.replay", stability="experimental", notes="Execution replay contract for workflow timeline, terminal output, repair chain, approvals, and sessions."),
    "collaboration.dashboard": ContractDescriptor(kind="collaboration.dashboard", stability="experimental", notes="Local-first collaborative engineering dashboard for shared workflows, roles, approval chains, roadmap ownership, repositories, runtime visibility, privacy, and audit history."),
    "collaboration.roles": ContractDescriptor(kind="collaboration.roles", stability="experimental", notes="Collaborative engineering roles, permissions, and governance rules."),
    "collaboration.member": ContractDescriptor(kind="collaboration.member", stability="experimental", notes="Team member registration or role update for local collaboration state."),
    "collaboration.repository": ContractDescriptor(kind="collaboration.repository", stability="experimental", notes="Repository/workspace coordination record linked to runtime nodes and validation infrastructure."),
    "collaboration.workflow": ContractDescriptor(kind="collaboration.workflow", stability="experimental", notes="Shared engineering workflow creation or governance mutation with ownership, delegation, approval chains, and audit history."),
    "collaboration.approval": ContractDescriptor(kind="collaboration.approval", stability="experimental", notes="Collaborative approval request or role-checked approval decision for workflow, validation, deployment, rollback, roadmap, runtime delegation, and repair governance."),
    "collaboration.roadmap": ContractDescriptor(kind="collaboration.roadmap", stability="experimental", notes="Collaborative roadmap assignment with owners, assignees, milestones, blockers, and optional approval-linked phases."),
    "collaboration.audit": ContractDescriptor(kind="collaboration.audit", stability="experimental", notes="Audit and accountability events for collaborative workflow ownership, approvals, deployments, rollbacks, repositories, and roadmap state."),
    "governance.dashboard": ContractDescriptor(kind="governance.dashboard", stability="experimental", notes="Core-owned governance, policy, compliance, runtime trust, plugin permission, deployment restriction, approval, and audit dashboard."),
    "governance.policies": ContractDescriptor(kind="governance.policies", stability="experimental", notes="Effective policy catalog with scopes, targets, trust levels, and policy lifecycle metadata."),
    "governance.policy": ContractDescriptor(kind="governance.policy", stability="experimental", notes="Policy upsert result for workflow, deployment, plugin, runtime, provider, memory, validation, approval, command, and file access governance."),
    "governance.evaluation": ContractDescriptor(kind="governance.evaluation", stability="experimental", notes="Policy evaluation result with allowed/needs_approval/blocked status, violations, restrictions, approvals, warnings, and compliance tags."),
    "governance.audit": ContractDescriptor(kind="governance.audit", stability="experimental", notes="Governance policy evaluation, violation, policy mutation, and compliance export audit events."),
    "governance.compliance_export": ContractDescriptor(kind="governance.compliance_export", stability="experimental", notes="Local-first compliance export bundle for workflow, approval, deployment, runtime, plugin, memory, and policy audit history."),
    "deployment.dashboard": ContractDescriptor(kind="deployment.dashboard", stability="experimental", notes="Core-owned environment, CI/CD, infrastructure, deployment workflow, rollback, and release supervision dashboard."),
    "deployment.scan": ContractDescriptor(kind="deployment.scan", stability="experimental", notes="Persisted environment intelligence scan for CI providers, deployment targets, containers, runtime configs, secrets, and risks."),
    "deployment.pipeline.validation": ContractDescriptor(kind="deployment.pipeline.validation", stability="experimental", notes="Dry-run capable CI/CD pipeline validation with safety gates, secret checks, and deployment readiness scoring."),
    "deployment.workflow": ContractDescriptor(kind="deployment.workflow", stability="experimental", notes="Approval-gated deployment workflow creation for build, package, CI, staging, production, and rollback flows."),
    "deployment.workflow.step": ContractDescriptor(kind="deployment.workflow.step", stability="experimental", notes="Deployment workflow pause/resume/approve/complete/fail/rollback state transition."),
    "deployment.release_history": ContractDescriptor(kind="deployment.release_history", stability="experimental", notes="Release history, rollback readiness, release notes draft, and deployment observability."),
    "deployment.observability": ContractDescriptor(kind="deployment.observability", stability="experimental", notes="Deployment workflow counts, release success/failure metrics, flaky validation candidates, and recurring failures."),
    "optimization.dashboard": ContractDescriptor(kind="optimization.dashboard", stability="experimental", notes="Core-owned self-analysis and optimization dashboard for workflows, routing, validation, repair, context, agents, indexing, and plugins."),
    "optimization.experiment": ContractDescriptor(kind="optimization.experiment", stability="experimental", notes="Sandboxed benchmark-driven optimization experiment proposal, run, adoption, or rollback result."),
    "optimization.recommendations": ContractDescriptor(kind="optimization.recommendations", stability="experimental", notes="Inspectible optimization recommendations derived from routing, workflow, validation, plugin, runtime, and quality metrics."),
    "optimization.observability": ContractDescriptor(kind="optimization.observability", stability="experimental", notes="Optimization experiment counts, regression warnings, bottlenecks, rollout state, and audit path."),
    "stabilization.audit": ContractDescriptor(kind="stabilization.audit", stability="experimental", notes="Static Core-owned platform stabilization audit covering contracts, oversized modules, duplicated runtime surfaces, recovery state, security signals, testing, release readiness, and freeze priorities."),
    "stabilization.governance": ContractDescriptor(kind="stabilization.governance", stability="experimental", notes="Production-readiness governance rules for API stability, subsystem ownership, migration, deprecation, release freeze, and security review requirements."),
    "stabilization.roadmap": ContractDescriptor(kind="stabilization.roadmap", stability="experimental", notes="Long-term roadmap classification across production-ready, experimental, prototype, deprecated, and planned systems."),
    "product.identity": ContractDescriptor(kind="product.identity", stability="experimental", notes="Auralith OS product identity, target users, local-first positioning, terminology, and client responsibilities."),
    "product.features": ContractDescriptor(kind="product.features", stability="experimental", notes="Auralith OS feature classification across core, advanced, experimental, developer/internal, and deprecated systems."),
    "product.modes": ContractDescriptor(kind="product.modes", stability="experimental", notes="Stable product modes and tiers from Basic Local Assistant through Experimental Labs."),
    "product.workflows": ContractDescriptor(kind="product.workflows", stability="experimental", notes="Coherent product workflow catalog for workspace open, scan, roadmap, implement, validate, repair, checkpoint, deploy, and rollback."),
    "product.showcase": ContractDescriptor(kind="product.showcase", stability="experimental", notes="Polished demo workflow definitions and success criteria for launch/readiness validation."),
    "product.launch_scope": ContractDescriptor(kind="product.launch_scope", stability="experimental", notes="Recommended Auralith OS launch scope, exclusions, known limitations, and launch readiness gates."),
    "product.roadmap": ContractDescriptor(kind="product.roadmap", stability="experimental", notes="Roadmap governance split into stable roadmap, experimental roadmap, research ideas, and future concepts."),
    "dogfooding.dashboard": ContractDescriptor(kind="dogfooding.dashboard", stability="experimental", notes="Local-first real-world dogfooding dashboard for workflow friction, production confidence, performance signals, trust gaps, long-session plans, and polish priorities."),
    "dogfooding.event": ContractDescriptor(kind="dogfooding.event", stability="experimental", notes="Privacy-aware local dogfooding event capture stored under project .aegis state."),
    "dogfooding.friction": ContractDescriptor(kind="dogfooding.friction", stability="experimental", notes="Aggregated workflow friction pain points, repeated actions, abandoned workflows, and UX simplification guidance."),
    "dogfooding.confidence": ContractDescriptor(kind="dogfooding.confidence", stability="experimental", notes="Production confidence metrics for crash-free sessions, workflow completion, rollback recovery, validation reliability, orchestration stability, and update reliability."),
    "dogfooding.workflows": ContractDescriptor(kind="dogfooding.workflows", stability="experimental", notes="Real-world dogfooding workflow playbook for feature work, bug fixing, roadmap tracking, validation, deployment, repair, and plugin development."),
    "dogfooding.long_session_plan": ContractDescriptor(kind="dogfooding.long_session_plan", stability="experimental", notes="Long-session test scenarios for multi-hour, large-project, many-workflow, plugin-heavy, and distributed runtime dogfooding."),
    "engineering_workspace.dashboard": ContractDescriptor(kind="engineering_workspace.dashboard", stability="experimental", notes="Flagship Auralith Engineering Workspace dashboard composing architecture navigation, validation review, continuity, deployment readiness, observability, and benchmarks."),
    "engineering_workspace.map": ContractDescriptor(kind="engineering_workspace.map", stability="experimental", notes="Project map, dependency visualization, service relationship map, entry points, build files, and architecture hotspots for IDE-quality navigation."),
    "engineering_workspace.search": ContractDescriptor(kind="engineering_workspace.search", stability="experimental", notes="Architecture-aware, dependency-aware, workflow-aware, and semantic-ready engineering search over the Core knowledge graph."),
    "engineering_workspace.validation": ContractDescriptor(kind="engineering_workspace.validation", stability="experimental", notes="Validation review surface with prioritization, root-cause candidates, repair explanations, regression signals, and recommended next checks."),
    "engineering_workspace.continuity": ContractDescriptor(kind="engineering_workspace.continuity", stability="experimental", notes="Workflow continuity surface for resume candidates, roadmap continuation, branch-aware workflow state, and checkpoint-linked work."),
    "engineering_workspace.benchmarks": ContractDescriptor(kind="engineering_workspace.benchmarks", stability="experimental", notes="Engineering benchmark comparison targets for workflow speed, validation reliability, repair quality, indexing performance, and orchestration efficiency."),
    "alpha.readiness": ContractDescriptor(kind="alpha.readiness", stability="experimental", notes="Controlled external alpha readiness checklist, feature classification, safe defaults, observability, support tooling, simulations, and recommended alpha scope."),
    "alpha.feature_flags": ContractDescriptor(kind="alpha.feature_flags", stability="experimental", notes="Alpha runtime feature toggles for safe defaults, experimental workflows, plugin gating, orchestration, distributed runtime, release channels, and local-only telemetry."),
    "alpha.feature_classification": ContractDescriptor(kind="alpha.feature_classification", stability="experimental", notes="Stable, beta, experimental, hidden/internal, and disabled-by-default feature classification for alpha testers."),
    "alpha.diagnostics": ContractDescriptor(kind="alpha.diagnostics", stability="experimental", notes="Privacy-aware local runtime diagnostics snapshot for support, workflow replay, validation, plugins, onboarding, release, security, and distributed runtime."),
    "alpha.diagnostics_export": ContractDescriptor(kind="alpha.diagnostics_export", stability="experimental", notes="Local-only diagnostics bundle export under .aegis for controlled alpha support."),
    "alpha.feedback": ContractDescriptor(kind="alpha.feedback", stability="experimental", notes="Local guided alpha feedback capture for workflow pain, orchestration confusion, plugin issues, performance problems, onboarding friction, and trust concerns."),
    "alpha.feedback_summary": ContractDescriptor(kind="alpha.feedback_summary", stability="experimental", notes="Aggregated local alpha feedback categories, severities, and recent redacted feedback."),
    "alpha.observability": ContractDescriptor(kind="alpha.observability", stability="experimental", notes="Alpha observability counters for crash frequency, workflow failures, plugin failures, onboarding failures, rollback, validation, update, and feedback signals."),
    "alpha.release_channels": ContractDescriptor(kind="alpha.release_channels", stability="experimental", notes="Stable, beta, experimental, and dev release channel policy for controlled external alpha."),
    "alpha.simulations": ContractDescriptor(kind="alpha.simulations", stability="experimental", notes="Planned alpha simulation matrix for clean installs, low-resource systems, plugin-heavy systems, distributed runtimes, long workflows, offline workflows, and interrupted updates."),
    "platform.governance": ContractDescriptor(kind="platform.governance", stability="experimental", notes="Long-term platform governance for API stability, plugin compatibility, deprecation, migration, versioning, runtime compatibility windows, and security review requirements."),
    "platform.migrations": ContractDescriptor(kind="platform.migrations", stability="experimental", notes="Workspace .aegis platform migration status and dry-run capable migration execution for memory, workflows, plugins, orchestration, knowledge graph, and checkpoints."),
    "platform.compatibility": ContractDescriptor(kind="platform.compatibility", stability="experimental", notes="Compatibility validation across plugins, clients, APIs, orchestration, and runtime state."),
    "platform.ownership": ContractDescriptor(kind="platform.ownership", stability="experimental", notes="Subsystem ownership boundaries across Core runtime, orchestration, plugins, experimental systems, infrastructure, IDE integrations, and observability."),
    "platform.dependencies": ContractDescriptor(kind="platform.dependencies", stability="experimental", notes="Ecosystem dependency management for plugin dependency chains, provider dependencies, runtime compatibility, and update risk."),
    "platform.release_engineering": ContractDescriptor(kind="platform.release_engineering", stability="experimental", notes="Release engineering readiness for reproducible builds, release verification, rollback, compatibility matrices, and staged rollout channels."),
    "platform.health": ContractDescriptor(kind="platform.health", stability="experimental", notes="Platform health analytics for subsystem reliability, orchestration stability, plugin health, migration status, update reliability, and regression watchlists."),
    "platform.tooling": ContractDescriptor(kind="platform.tooling", stability="experimental", notes="Contributor and ecosystem tooling catalog for plugin SDKs, compatibility validators, workflow schema validators, runtime diagnostics, and replay tools."),
    "platform.roadmap": ContractDescriptor(kind="platform.roadmap", stability="experimental", notes="Long-term roadmap governance separating production roadmap, experimental roadmap, research initiatives, deprecated systems, and ecosystem initiatives."),
    "platform.archive": ContractDescriptor(kind="platform.archive", stability="experimental", notes="Local archival/recovery snapshot manifest for workflow, memory, knowledge, checkpoint, rollback, and migration recovery state."),
    "platform.sustainability": ContractDescriptor(kind="platform.sustainability", stability="experimental", notes="Aggregated long-term platform foundation dashboard combining governance, migrations, compatibility, ownership, dependencies, release engineering, health, tooling, roadmap, and archival guidance."),
    "ecosystem.strategy": ContractDescriptor(kind="ecosystem.strategy", stability="experimental", notes="Ecosystem growth strategy covering core audience, plugin direction, contributor strategy, positioning, privacy posture, and roadmap themes."),
    "ecosystem.workflow_excellence": ContractDescriptor(kind="ecosystem.workflow_excellence", stability="experimental", notes="Workflow excellence review for feature implementation, validation, repair, deployment, rollback, and roadmap execution flows."),
    "ecosystem.plugin_quality": ContractDescriptor(kind="ecosystem.plugin_quality", stability="experimental", notes="Plugin marketplace foundation, quality scoring, compatibility badges, permission transparency, and review/testing tools."),
    "ecosystem.api_stability": ContractDescriptor(kind="ecosystem.api_stability", stability="experimental", notes="Stable APIs, workflow schemas, orchestration contracts, plugin contracts, and compatibility guarantees."),
    "ecosystem.contributor": ContractDescriptor(kind="ecosystem.contributor", stability="experimental", notes="Contributor ecosystem guidance for docs, plugin SDK, subsystem ownership, debugging, architecture maps, and contribution rules."),
    "ecosystem.reputation": ContractDescriptor(kind="ecosystem.reputation", stability="experimental", notes="Platform reputation standards for release quality, compatibility, migrations, rollback reliability, and security review."),
    "ecosystem.release_cadence": ContractDescriptor(kind="ecosystem.release_cadence", stability="experimental", notes="Stable, beta, experimental, and research release cadence plus promotion requirements."),
    "ecosystem.observability": ContractDescriptor(kind="ecosystem.observability", stability="experimental", notes="Ecosystem observability for plugin health, workflow success, runtime reliability, onboarding success, and compatibility issues."),
    "ecosystem.maintainability": ContractDescriptor(kind="ecosystem.maintainability", stability="experimental", notes="Long-term maintainability guidance for reducing abstractions, duplication, unstable interfaces, feature sprawl, and hidden coupling."),
    "ecosystem.showcases": ContractDescriptor(kind="ecosystem.showcases", stability="experimental", notes="Polished showcase experiences for roadmap execution, autonomous repair, deployment validation, distributed runtime, workspace intelligence, and plugins."),
    "ecosystem.trust": ContractDescriptor(kind="ecosystem.trust", stability="experimental", notes="Trust and transparency contract for explaining actions, model/provider routing, local/cloud data, file changes, and rollback."),
    "ecosystem.sustainability_plan": ContractDescriptor(kind="ecosystem.sustainability_plan", stability="experimental", notes="Long-term maintenance, compatibility windows, plugin migration strategy, governance structure, and roadmap review process."),
    "ecosystem.maturity": ContractDescriptor(kind="ecosystem.maturity", stability="experimental", notes="Aggregated ecosystem growth and maturity dashboard for adoption readiness, workflow quality, plugin health, trust, and long-term focus."),
    "ecosystem.dashboard": ContractDescriptor(kind="ecosystem.dashboard", stability="stable", notes="Aggregated Core dashboard for desktop and website bridge."),
    "autopilot.modes": ContractDescriptor(kind="autopilot.modes", stability="experimental", notes="Formal supervised Autopilot execution modes, approval rules, autonomy limits, validation requirements, and safety invariants."),
    "autopilot.run": ContractDescriptor(kind="autopilot.run", stability="experimental", notes="Production-grade Autopilot run creation backed by Core engineering execution, workflow state, memory, and supervision contracts."),
    "autopilot.runs": ContractDescriptor(kind="autopilot.runs", stability="experimental", notes="Recent and active supervised Autopilot runs with filters for status, mode, and workflow type."),
    "autopilot.dashboard": ContractDescriptor(kind="autopilot.dashboard", stability="experimental", notes="Single Autopilot run dashboard with linked execution snapshot, approvals, validation chain, repair history, and safety status."),
    "autopilot.action": ContractDescriptor(kind="autopilot.action", stability="experimental", notes="Approval-aware Autopilot action mutation for pause, resume, cancel, approve, validation, repair, checkpoint, rollback, simulation, and terminal orchestration."),
    "autopilot.supervision": ContractDescriptor(kind="autopilot.supervision", stability="experimental", notes="Autopilot command-center supervision snapshot for active workflow, active agent, current task, approval queue, trust scorecard, validation, repair, rollback, and runtime status."),
    "autopilot.observability": ContractDescriptor(kind="autopilot.observability", stability="experimental", notes="Autopilot metrics for completion, confidence, regression risk, validation, repair, rollback, approval interruptions, duration, modes, workflow distribution, and failure hotspots."),
    "autopilot.memory": ContractDescriptor(kind="autopilot.memory", stability="experimental", notes="Local execution memory for completed roadmap phases, failures, repair outcomes, validation history, and workflow outcomes."),
    "autopilot.replay": ContractDescriptor(kind="autopilot.replay", stability="experimental", notes="Replayable Autopilot timeline combining Core execution events, validation chain, repair chain, approvals, rollbacks, and terminal jobs."),
    "autopilot.client_hooks": ContractDescriptor(kind="autopilot.client_hooks", stability="experimental", notes="Stable Website, Desktop, VS Code, and Visual Studio integration hook catalog for Autopilot supervision controls."),
    "changes.proposal": ContractDescriptor(kind="changes.proposal", stability="experimental", notes="Core-owned proposed file changes with patch preview metadata and operation tracking."),
    "changes.apply": ContractDescriptor(kind="changes.apply", stability="experimental", notes="Core-owned selected/all change application with mandatory checkpointing and dry-run support."),
    "checkpoints.create": ContractDescriptor(kind="checkpoints.create", stability="experimental", notes="Core-owned checkpoint creation for safe file mutation and restore workflows."),
    "checkpoints.list": ContractDescriptor(kind="checkpoints.list", stability="experimental", notes="Core-owned checkpoint listing from workspace .aegis state."),
    "checkpoints.restore": ContractDescriptor(kind="checkpoints.restore", stability="experimental", notes="Core-owned checkpoint restore with pre-restore backup and operation tracking."),
    "validation.run": ContractDescriptor(kind="validation.run", stability="experimental", notes="Core-owned validation execution record with stored result, task/job ids, and repair metadata."),
    "core.job": ContractDescriptor(kind="core.job", stability="experimental", notes="Core editing/runtime operation job lookup."),
    "project.activity": ContractDescriptor(kind="project.activity", stability="experimental", notes="Core-owned project activity stream for editing, checkpoint, validation, and repair events."),
    "workflow.created": ContractDescriptor(kind="workflow.created", stability="experimental", notes="Core-owned structured workflow graph creation result."),
    "workflows.list": ContractDescriptor(kind="workflows.list", stability="experimental", notes="Core-owned active and recent workflow listing."),
    "workflow.dashboard": ContractDescriptor(kind="workflow.dashboard", stability="experimental", notes="Single workflow graph, timeline, agent runtime, and observability dashboard."),
    "workflow.step": ContractDescriptor(kind="workflow.step", stability="experimental", notes="Workflow task transition, deterministic execution, pause/resume/cancel/retry, or log event."),
    "client.sync": ContractDescriptor(kind="client.sync", stability="experimental", notes="Cross-client active workflow synchronization heartbeat."),
    "client.sync.dashboard": ContractDescriptor(kind="client.sync.dashboard", stability="experimental", notes="Active clients, active workflows, recent operations, and workspace activity feed."),
    "workspace.intelligence": ContractDescriptor(kind="workspace.intelligence", stability="experimental", notes="Shared workspace intelligence runtime combining scan, metadata, dependency graph, health, validation, knowledge, and memory."),
    "workflow.statistics": ContractDescriptor(kind="workflow.statistics", stability="experimental", notes="Workflow duration, validation, repair, model usage, status, and event metrics."),
    "agent.runtime": ContractDescriptor(kind="agent.runtime", stability="experimental", notes="Formal deterministic agent runtime with roles, capabilities, limits, model profiles, memory scopes, task ownership, history, and safety rules."),
    "agent.coordination": ContractDescriptor(kind="agent.coordination", stability="experimental", notes="Workflow agent coordination dashboard with active agents, handoff chain, context snapshots, dependency graph, supervision, and observability."),
    "agent.delegation": ContractDescriptor(kind="agent.delegation", stability="experimental", notes="Approval-aware task ownership handoff between formal workflow agents."),
    "engineering.execution.created": ContractDescriptor(kind="engineering.execution.created", stability="experimental", notes="Core-owned engineering execution pipeline plan with stages, subtasks, safety controls, and workflow linkage."),
    "engineering.executions.list": ContractDescriptor(kind="engineering.executions.list", stability="experimental", notes="Core-owned active and recent engineering execution pipeline records."),
    "engineering.execution.dashboard": ContractDescriptor(kind="engineering.execution.dashboard", stability="experimental", notes="Single engineering execution plan, timeline, memory, metrics, validation chain, and repair history."),
    "engineering.execution.step": ContractDescriptor(kind="engineering.execution.step", stability="experimental", notes="Approval-gated engineering execution stage transition or journal update."),
    "engineering.execution.timeline": ContractDescriptor(kind="engineering.execution.timeline", stability="experimental", notes="Visualization contract for execution timeline, stage graph, task dependency graph, validation chain, and repair history."),
    "engineering.memory": ContractDescriptor(kind="engineering.memory", stability="experimental", notes="Core-owned reusable workspace intelligence memory for engineering execution."),
    "engineering.metrics": ContractDescriptor(kind="engineering.metrics", stability="experimental", notes="Engineering execution validation, repair, iteration, model usage, file modification, rollback, and duration metrics."),
    "engineering.modes": ContractDescriptor(kind="engineering.modes", stability="experimental", notes="Supported approval-based engineering execution modes and safety rules."),
    "engineering.intelligence": ContractDescriptor(kind="engineering.intelligence", stability="experimental", notes="Deep engineering intelligence dashboard combining architecture reasoning, context assembly, validation, repair, roadmap, prediction, memory, and benchmarks."),
    "engineering.context": ContractDescriptor(kind="engineering.context", stability="experimental", notes="Workflow-specific, dependency-aware, memory-aware context assembly with token budget and explainable ranking."),
    "engineering.validation_intelligence": ContractDescriptor(kind="engineering.validation_intelligence", stability="experimental", notes="Targeted validation plan with dependency-aware prioritization, flaky-test signals, confidence, and escalation rules."),
    "engineering.repair_intelligence": ContractDescriptor(kind="engineering.repair_intelligence", stability="experimental", notes="Root-cause, repair strategy, failed-repair detection, architecture-aware scope, and rollback recommendation contract."),
    "engineering.roadmap_intelligence": ContractDescriptor(kind="engineering.roadmap_intelligence", stability="experimental", notes="Architecture-aware roadmap decomposition, dependency planning, milestone prediction, and execution ordering."),
    "engineering.workflow_prediction": ContractDescriptor(kind="engineering.workflow_prediction", stability="experimental", notes="Workflow risk, likely failures, validation scope, rollback probability, deployment risk, duration, and reliability prediction."),
    "engineering.intelligence.benchmarks": ContractDescriptor(kind="engineering.intelligence.benchmarks", stability="experimental", notes="Engineering intelligence benchmark scores and history for feature, repair, validation, roadmap, orchestration, rollback, and reliability quality."),
    "intelligence.stack": ContractDescriptor(kind="intelligence.stack", stability="experimental", notes="Auralith local-first intelligence stack dashboard for specialized models, retrieval, routing, orchestration prediction, datasets, benchmarks, and distributed inference."),
    "intelligence.models": ContractDescriptor(kind="intelligence.models", stability="experimental", notes="Local specialized model lifecycle metadata, install plans, compatibility, quantization awareness, and benchmark records."),
    "intelligence.retrieval": ContractDescriptor(kind="intelligence.retrieval", stability="experimental", notes="Local-first semantic, graph-aware, and hybrid retrieval index with embedding-ready records."),
    "intelligence.route": ContractDescriptor(kind="intelligence.route", stability="experimental", notes="Workflow-specific intelligence route decision with local/cloud/privacy/fallback explanation."),
    "intelligence.prediction": ContractDescriptor(kind="intelligence.prediction", stability="experimental", notes="Lightweight local orchestration, validation, repair, risk, and execution guidance prediction."),
    "intelligence.benchmarks": ContractDescriptor(kind="intelligence.benchmarks", stability="experimental", notes="Benchmark and evaluation history for repair, validation, roadmap, routing, retrieval, context, and execution reliability."),
    "intelligence.datasets": ContractDescriptor(kind="intelligence.datasets", stability="experimental", notes="Privacy-aware local dataset foundations built from workflow traces, repairs, validations, architecture summaries, and roadmap history."),
    "intelligence.distributed_inference": ContractDescriptor(kind="intelligence.distributed_inference", stability="experimental", notes="Distributed inference planning contract for local, GPU, model-worker, embedding, and trusted runtime nodes."),
    "patch.proposal": ContractDescriptor(kind="patch.proposal", stability="experimental", owner="schema-only", notes="Shared shape for approved patch proposals."),
    "rollback.entry": ContractDescriptor(kind="rollback.entry", stability="experimental", owner="schema-only", notes="Shared rollback checkpoint listing shape."),
    "rollback.result": ContractDescriptor(kind="rollback.result", stability="experimental", owner="schema-only", notes="Shared rollback execution result shape."),
}


CONTRACT_DATA_MODELS: dict[str, type[BaseModel] | tuple[type[BaseModel], bool]] = {
    "health": HealthData,
    "security.status": SecurityStatusData,
    "release.manifest": ReleaseManifestData,
    "release.compatibility": ReleaseCompatibilityData,
    "release.migrations": ReleaseMigrationData,
    "release.migrations.run": ReleaseMigrationData,
    "release.update_plan": ReleaseUpdatePlanData,
    "models": ModelsData,
    "model.registry": ModelRegistryData,
    "model.providers": ProviderInventoryData,
    "model.routing_profiles": (ModelRoutingProfileData, True),
    "model.route": ModelRouteData,
    "model.completion": ModelCompletionData,
    "provider.key.status": ProviderKeyStatusData,
    "settings": SettingsData,
    "settings.updated": SettingsData,
    "onboarding.status": OnboardingStatusData,
    "onboarding.updated": OnboardingStatusData,
    "onboarding.first_workflow": OnboardingFirstWorkflowData,
    "settings.export": SettingsExportData,
    "settings.import": SettingsImportData,
    "plugin.dashboard": PluginDashboardData,
    "plugin.state": PluginStateData,
    "plugin.tool.run": PluginToolRunData,
    "plugin.hooks": PluginHooksData,
    "distributed.runtime": DistributedRuntimeData,
    "distributed.nodes": RuntimeNodesData,
    "distributed.node.registered": RuntimeNodeMutationData,
    "distributed.node.heartbeat": RuntimeNodeMutationData,
    "distributed.node.revoked": RuntimeNodeMutationData,
    "distributed.workloads": RuntimeWorkloadsData,
    "distributed.workload.created": RuntimeWorkloadMutationData,
    "distributed.workload.lookup": RuntimeWorkloadMutationData,
    "distributed.workload.dispatch": RuntimeWorkloadMutationData,
    "distributed.workload.action": RuntimeWorkloadMutationData,
    "distributed.recovery": RuntimeRecoveryData,
    "distributed.observability": RuntimeObservabilityData,
    "distributed.audit": RuntimeAuditData,
    "distributed.deployment": RuntimeDeploymentData,
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
    "quality.gates": QualityGateDashboardData,
    "quality.gates.evaluate": QualityGateEvaluationData,
    "workflow.quality": QualityGateDashboardData,
    "quality.benchmarks": QualityBenchmarkDashboardData,
    "quality.benchmark.run": QualityBenchmarkRunData,
    "quality.evaluation_report": EvaluationReportData,
    "quality.evaluation_reports": EvaluationReportsData,
    "knowledge.graph": KnowledgeGraphData,
    "knowledge.query": KnowledgeQueryData,
    "knowledge.search": KnowledgeSearchData,
    "knowledge.relationships": KnowledgeRelationshipsData,
    "knowledge.symbol": KnowledgeSymbolData,
    "knowledge.impact_analysis": KnowledgeImpactAnalysisData,
    "knowledge.architecture_summary": KnowledgeArchitectureSummaryData,
    "simulation.change": SimulationData,
    "simulation.compare": SimulationComparisonData,
    "operations.dashboard": OperationsDashboardData,
    "personal.intelligence": PersonalIntelligenceData,
    "personal.intelligence.reset": PersonalIntelligenceResetData,
    "personal.memory": PersonalMemoryDashboardData,
    "personal.memory.record": PersonalMemoryMutationData,
    "personal.memory.deleted": PersonalMemoryDeleteData,
    "personal.memory.export": PersonalMemoryExportData,
    "personal.memory.import": PersonalMemoryImportData,
    "personal.memory.controls": PersonalMemoryControlsData,
    "personal.memory.cleanup": PersonalMemoryCleanupData,
    "personal.memory.observability": PersonalMemoryObservabilityData,
    "personal.memory.context": PersonalMemoryContextData,
    "runtime.interaction": RuntimeInteractionDashboardData,
    "runtime.jobs": RuntimeInteractionJobsData,
    "runtime.job": RuntimeInteractionJobLookupData,
    "runtime.job.mutation": RuntimeInteractionJobMutationData,
    "runtime.streams": RuntimeInteractionStreamsData,
    "runtime.processes": RuntimeInteractionProcessesData,
    "runtime.sessions": RuntimeInteractionSessionsData,
    "runtime.session.mutation": RuntimeInteractionSessionMutationData,
    "runtime.voice": RuntimeInteractionVoiceData,
    "runtime.voice.command": RuntimeInteractionVoiceCommandData,
    "runtime.replay": RuntimeInteractionReplayData,
    "collaboration.dashboard": CollaborationDashboardData,
    "collaboration.roles": CollaborationRolesData,
    "collaboration.member": CollaborationMemberMutationData,
    "collaboration.repository": CollaborationRepositoryMutationData,
    "collaboration.workflow": CollaborationWorkflowMutationData,
    "collaboration.approval": CollaborationApprovalMutationData,
    "collaboration.roadmap": CollaborationRoadmapMutationData,
    "collaboration.audit": CollaborationAuditData,
    "governance.dashboard": GovernanceDashboardData,
    "governance.policies": GovernancePolicyCatalogData,
    "governance.policy": GovernancePolicyMutationData,
    "governance.evaluation": GovernancePolicyEvaluationData,
    "governance.audit": GovernanceAuditData,
    "governance.compliance_export": GovernanceComplianceExportData,
    "deployment.dashboard": DeploymentDashboardData,
    "deployment.scan": DeploymentDashboardData,
    "deployment.pipeline.validation": DeploymentPipelineValidationData,
    "deployment.workflow": DeploymentWorkflowMutationData,
    "deployment.workflow.step": DeploymentWorkflowMutationData,
    "deployment.release_history": DeploymentReleaseHistoryData,
    "deployment.observability": DeploymentObservabilityData,
    "optimization.dashboard": OptimizationDashboardData,
    "optimization.experiment": OptimizationExperimentMutationData,
    "optimization.recommendations": OptimizationRecommendationsData,
    "optimization.observability": OptimizationObservabilityData,
    "stabilization.audit": StabilizationAuditData,
    "stabilization.governance": StabilizationGovernanceData,
    "stabilization.roadmap": StabilizationRoadmapData,
    "product.identity": ProductIdentityData,
    "product.features": ProductFeatureCatalogData,
    "product.modes": ProductModeCatalogData,
    "product.workflows": ProductWorkflowCatalogData,
    "product.showcase": ProductShowcaseData,
    "product.launch_scope": ProductLaunchScopeData,
    "product.roadmap": ProductRoadmapData,
    "dogfooding.dashboard": DogfoodingDashboardData,
    "dogfooding.event": DogfoodingEventData,
    "dogfooding.friction": DogfoodingFrictionData,
    "dogfooding.confidence": DogfoodingConfidenceData,
    "dogfooding.workflows": DogfoodingWorkflowsData,
    "dogfooding.long_session_plan": DogfoodingLongSessionPlanData,
    "engineering_workspace.dashboard": EngineeringWorkspaceDashboardData,
    "engineering_workspace.map": EngineeringWorkspaceMapData,
    "engineering_workspace.search": EngineeringWorkspaceSearchData,
    "engineering_workspace.validation": EngineeringWorkspaceValidationData,
    "engineering_workspace.continuity": EngineeringWorkspaceContinuityData,
    "engineering_workspace.benchmarks": EngineeringWorkspaceBenchmarksData,
    "alpha.readiness": AlphaReadinessData,
    "alpha.feature_flags": AlphaFeatureFlagsData,
    "alpha.feature_classification": AlphaFeatureClassificationData,
    "alpha.diagnostics": AlphaDiagnosticsData,
    "alpha.diagnostics_export": AlphaDiagnosticsExportData,
    "alpha.feedback": AlphaFeedbackData,
    "alpha.feedback_summary": AlphaFeedbackSummaryData,
    "alpha.observability": AlphaObservabilityData,
    "alpha.release_channels": AlphaReleaseChannelsData,
    "alpha.simulations": AlphaSimulationsData,
    "platform.governance": PlatformGovernanceData,
    "platform.migrations": PlatformMigrationData,
    "platform.compatibility": PlatformCompatibilityData,
    "platform.ownership": PlatformOwnershipData,
    "platform.dependencies": PlatformDependenciesData,
    "platform.release_engineering": PlatformReleaseEngineeringData,
    "platform.health": PlatformHealthData,
    "platform.tooling": PlatformToolingData,
    "platform.roadmap": PlatformRoadmapData,
    "platform.archive": PlatformArchiveData,
    "platform.sustainability": PlatformSustainabilityData,
    "ecosystem.strategy": EcosystemStrategyData,
    "ecosystem.workflow_excellence": EcosystemWorkflowExcellenceData,
    "ecosystem.plugin_quality": EcosystemPluginQualityData,
    "ecosystem.api_stability": EcosystemApiStabilityData,
    "ecosystem.contributor": EcosystemContributorData,
    "ecosystem.reputation": EcosystemReputationData,
    "ecosystem.release_cadence": EcosystemReleaseCadenceData,
    "ecosystem.observability": EcosystemObservabilityData,
    "ecosystem.maintainability": EcosystemMaintainabilityData,
    "ecosystem.showcases": EcosystemShowcasesData,
    "ecosystem.trust": EcosystemTrustData,
    "ecosystem.sustainability_plan": EcosystemSustainabilityPlanData,
    "ecosystem.maturity": EcosystemMaturityData,
    "ecosystem.dashboard": EcosystemDashboardData,
    "autopilot.modes": AutopilotModesData,
    "autopilot.run": AutopilotRunData,
    "autopilot.runs": AutopilotListData,
    "autopilot.dashboard": AutopilotDashboardData,
    "autopilot.action": AutopilotActionData,
    "autopilot.supervision": AutopilotSupervisionData,
    "autopilot.observability": AutopilotObservabilityData,
    "autopilot.memory": AutopilotMemoryData,
    "autopilot.replay": AutopilotReplayData,
    "autopilot.client_hooks": AutopilotClientHooksData,
    "changes.proposal": ChangesProposeData,
    "changes.apply": ChangesApplyData,
    "checkpoints.create": CheckpointRecordData,
    "checkpoints.list": CheckpointsListData,
    "checkpoints.restore": CheckpointRestoreData,
    "validation.run": ValidationRunData,
    "core.job": CoreJobLookupData,
    "project.activity": ProjectActivityData,
    "workflow.created": WorkflowDashboardData,
    "workflows.list": WorkflowListData,
    "workflow.dashboard": WorkflowDashboardData,
    "workflow.step": WorkflowActionData,
    "client.sync": ClientSyncData,
    "client.sync.dashboard": ClientSyncDashboardData,
    "workspace.intelligence": WorkspaceIntelligenceData,
    "workflow.statistics": WorkflowStatisticsData,
    "agent.runtime": AgentRuntimeData,
    "agent.coordination": AgentCoordinationData,
    "agent.delegation": WorkflowActionData,
    "engineering.execution.created": EngineeringExecutionDashboardData,
    "engineering.executions.list": EngineeringExecutionListData,
    "engineering.execution.dashboard": EngineeringExecutionDashboardData,
    "engineering.execution.step": EngineeringExecutionStepData,
    "engineering.execution.timeline": EngineeringTimelineData,
    "engineering.memory": EngineeringMemoryData,
    "engineering.metrics": EngineeringMetricsData,
    "engineering.modes": EngineeringModesData,
    "engineering.intelligence": EngineeringIntelligenceData,
    "engineering.context": EngineeringContextAssemblyData,
    "engineering.validation_intelligence": EngineeringValidationIntelligenceData,
    "engineering.repair_intelligence": EngineeringRepairIntelligenceData,
    "engineering.roadmap_intelligence": EngineeringRoadmapIntelligenceData,
    "engineering.workflow_prediction": EngineeringWorkflowPredictionData,
    "engineering.intelligence.benchmarks": EngineeringIntelligenceBenchmarkData,
    "intelligence.stack": IntelligenceStackData,
    "intelligence.models": IntelligenceModelLifecycleData,
    "intelligence.retrieval": IntelligenceRetrievalData,
    "intelligence.route": IntelligenceRoutingData,
    "intelligence.prediction": IntelligencePredictionData,
    "intelligence.benchmarks": IntelligenceBenchmarkData,
    "intelligence.datasets": IntelligenceDatasetData,
    "intelligence.distributed_inference": IntelligenceDistributedInferenceData,
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
