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
