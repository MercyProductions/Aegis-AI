# backend/main.py
from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .adaptive_intelligence import AdaptiveIntelligenceEngine
from .agent import AgentEngine, MODE_OPTIONS
from .auth import AccountStore
from .autonomous_engineering import AutonomousEngineeringEngine
from .chat_streaming import (
    chat_stream_contract_response,
    preview_delta_counts_as_streamed,
    preview_delta_payload,
    response_with_reconciliation,
    sse_event,
    structured_stream_intro,
    structured_stream_reconciliation,
    structured_stream_summary,
)
from .continuity import AegisContinuityEngine
from .core_bridge import AegisCoreBridge
from .creative_media import CreativeMediaEngine
from .distributed_runtime import DistributedRuntimeManager
from .ecosystem import ECOSYSTEM_API_VERSION, EcosystemEngine
from .model_benchmark import ModelBenchmarkManager
from .model_manager import ModelManager
from .model_registry import ModelRegistryManager
from .operating_environment import OperatingEnvironmentEngine
from .platform_discipline import PlatformDisciplineEngine
from .productization import ProductizationEngine
from .providers.accounts import ProviderAccountManager
from .providers.accounts.agent_bridge import AgentBridgeRunner
from .project_intelligence import ProjectIntelligenceEngine
from .routes import (
    register_adaptive_intelligence_routes,
    build_workspace_profile,
    register_agent_bridge_execution_routes,
    register_agent_bridge_job_routes,
    register_agent_bridge_streaming_routes,
    register_agent_supervision_routes,
    register_autonomous_engineering_routes,
    register_autopilot_routes,
    register_auth_routes,
    register_chat_routes,
    register_checkpoint_routes,
    register_collaboration_routes,
    register_config_routes,
    register_distributed_runtime_routes,
    register_ecosystem_routes,
    register_file_routes,
    register_governance_routes,
    register_history_task_routes,
    register_media_routes,
    register_model_registry_routes,
    register_onboarding_settings_routes,
    register_provider_account_routes,
    register_productization_routes,
    register_project_builder_routes,
    register_project_intelligence_routes,
    register_quality_evaluation_routes,
    register_routing_apply_routes,
    register_runtime_convergence_routes,
    register_runtime_routes,
    register_telemetry_routes,
    register_utility_routes,
    register_validation_routes,
    register_workspace_intelligence_routes,
    register_workspace_profile_routes,
)
from .project_scaffolder import ProjectScaffolder
from .services.core_client import (
    AegisCoreClient,
    CoreDelegationResult,
    checkpoint_summary_from_core,
)
from .services.core_delegation import (
    apply_response_from_core as _apply_response_from_core,
    checkpoint_list_response_from_core as _checkpoint_list_response_from_core,
    core_contract_version as _core_contract_version,
    core_delegation_data as _core_delegation_data,
    core_delegation_error as _core_delegation_error,
    core_result_data as _core_result_data,
    core_route_message as _core_route_message,
    core_route_status as _core_route_status,
    record_core_fallback,
    restore_response_from_core as _restore_response_from_core,
    validate_response_from_core as _validate_response_from_core,
)
from .services.agent_bridge_service import AgentBridgeService
from .services.distributed_runtime_service import DistributedRuntimeService
from .services.model_inventory_service import ModelInventoryService, merge_core_model_registry
from .services.project_builder_service import ProjectBuilderService
from .services.runtime_health_service import RuntimeHealthService
from .services.route_preview_service import (
    core_route_request_kwargs as _core_route_request_kwargs,
    route_preview_from_core as _route_preview_from_core,
)
from .services.settings_service import SettingsService
from .services.utility_service import UtilityService
from .services.workspace_intelligence_service import WorkspaceIntelligenceService
from .unified_context import UnifiedContextEngine
from .unified_runtime import RuntimeSignalCounts, UnifiedRuntimeEngine
from .workspace_autopilot import (
    build_workspace_autopilot_status,
)
from .workspace_operations import WorkspaceOperationsEngine
from .schemas import (
    AdaptiveBenchmarkReport,
    AdaptiveBenchmarkRunRequest,
    AdaptiveIntelligenceRefreshRequest,
    AdaptiveIntelligenceSnapshot,
    AdaptivePolicyProfileUpdateRequest,
    AdaptivePolicyRollbackRequest,
    AdaptiveReplayRequest,
    AgentBridgeExecuteRequest,
    AgentBridgeExecuteResponse,
    AgentBridgeJobInfo,
    AgentBridgeJobResponse,
    AgentBridgePreflightResponse,
    AgentRequest,
    AgentResponse,
    AegisContinuitySnapshot,
    AppConfig,
    ApplyRequest,
    ApplyResponse,
    AutonomousApprovalActionRequest,
    AutonomousApprovalGate,
    AutonomousEngineeringSnapshot,
    AutonomousObjective,
    AutonomousObjectiveActionRequest,
    AutonomousObjectiveCreateRequest,
    AutonomousObjectiveDetail,
    AutonomousObjectiveIterationRequest,
    AutonomousSimulationEstimate,
    ChatStreamContractResponse,
    CheckpointCreateRequest,
    CheckpointListResponse,
    CheckpointSummary,
    ConfigUpdateRequest,
    DistributedRuntimeSnapshot,
    EcosystemAuditEvent,
    EcosystemPackageActionRequest,
    EcosystemPackageLifecycleRequest,
    EcosystemPackageLifecycleResponse,
    EcosystemPackageManifest,
    EcosystemPackageRegistrationRequest,
    EcosystemPackageValidationRequest,
    EcosystemPackageValidationResult,
    EcosystemRefreshRequest,
    EcosystemSearchRequest,
    EcosystemSearchResponse,
    EcosystemSnapshot,
    EcosystemWorkflowDefinition,
    EnterprisePolicyProfile,
    EnterprisePolicyUpdateRequest,
    ExecutionDispatchRequest,
    ExecutionDispatchResponse,
    ExecutionQueueActionRequest,
    ExecutionQueueCreateRequest,
    ExecutionQueueItem,
    FallbackInspectorResponse,
    FeedbackTelemetryResponse,
    EvaluationReplayResult,
    GlobalCommandRequest,
    GlobalCommandResponse,
    HistoryResponse,
    HybridRouteDecision,
    HybridRouteRequest,
    IntelligencePolicyProfile,
    KnowledgeGraphSnapshot,
    ModelBenchmarkJobInfo,
    ModelBenchmarkRunRequest,
    ModelBenchmarkSnapshot,
    ModelDeleteRequest,
    ModelAdapterHealthInfo,
    ModelInventoryResponse,
    ModelManagerResponse,
    ModelOperationInfo,
    ModelPullRequest,
    ModelRegistryAuditResponse,
    ModelRegistryCheckpointCreateRequest,
    ModelRegistryCheckpointDiffResponse,
    ModelRegistryCheckpointInfo,
    ModelRegistryCheckpointListResponse,
    ModelRegistryBenchmarkPreviewResponse,
    ModelRegistryProviderUpsertRequest,
    ModelRouteHealthInfo,
    PluginActionRequest,
    PluginLifecycleActionRequest,
    PluginLifecycleActionResponse,
    PluginManifest,
    PluginRegistrationRequest,
    PluginValidationRequest,
    PluginValidationResult,
    OrganizationPolicyProfile,
    OrganizationPolicyUpdateRequest,
    OperatingEnvironmentActionRequest,
    OperatingEnvironmentActionResponse,
    OperatingEnvironmentSnapshot,
    PlatformDisciplineSnapshot,
    ProjectContextSelectionRequest,
    ProjectContextSelectionResponse,
    ProjectIntelligenceReindexRequest,
    ProjectIntelligenceSnapshot,
    RecommendationActionRequest,
    RecommendationFixRequest,
    RecommendationFixResponse,
    RemoteWorkspaceSyncManifest,
    RemoteWorkspaceSyncRequest,
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProductizationRefreshRequest,
    ProductizationSnapshot,
    ReproducibilityRecord,
    ReproducibilityRequest,
    RestoreCheckpointRequest,
    RestoreCheckpointResponse,
    ReliabilityMetric,
    RoutePreviewRequest,
    RoutePreviewResponse,
    RouteQualityResponse,
    RoutePolicyDiffResponse,
    RuntimeObservabilitySnapshot,
    RuntimeHealthResponse,
    RuntimeRecoverySnapshot,
    StableApiContract,
    TaskActionRequest,
    TaskActionResponse,
    TaskArtifactsResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskListResponse,
    TaskOutcomeRecord,
    TaskTimelineResponse,
    ScheduledIntelligenceJob,
    ScheduledJobRunRequest,
    ScheduledJobRunResponse,
    SharedIntelligenceProfile,
    SharedIntelligenceProfileExportResponse,
    SharedIntelligenceProfileImportRequest,
    TelemetryResponse,
    TelemetrySnapshot,
    TelemetrySnapshotPruneInfo,
    TelemetrySnapshotResponse,
    TimelineSearchRequest,
    TimelineSearchResponse,
    UnifiedContextSearchRequest,
    UnifiedContextSearchResponse,
    UnifiedContextSnapshot,
    UnifiedRuntimeSnapshot,
    ValidationProfileResponse,
    ValidationProfileUpdateRequest,
    ValidateRequest,
    ValidateResponse,
    VerificationRequest,
    VerificationResponse,
    WorkspaceAutopilotStatusResponse,
    WorkspaceOperationsScanRequest,
    WorkspaceOperationsSnapshot,
    WorkspaceProfileResponse,
    WorkspaceRecommendation,
    WorkspaceSetupRequest,
    WorkspaceSetupResponse,
    WorkspaceWatchEvent,
    WorkerActionRequest,
    WorkerAuditEvent,
    WorkerHeartbeatRequest,
    WorkerRegistrationRequest,
    WorkerRuntimeInfo,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from .settings import PROJECT_ROOT, clear_settings_cache, get_settings, has_env_file, update_env
from .security import install_security_middleware, trust_status
from .storage import utc_now
from .workspace import WorkspaceManager
from .workspace_cache import (
    ProjectPlanCache,
    WorkspaceStatusSnapshot,
    WorkspaceStatusSnapshotCache,
    cache_paths_are_related,
    normalized_cache_path,
    project_plan_cache_key,
)


settings = get_settings()
workspace_manager = WorkspaceManager(PROJECT_ROOT, settings)
agent = AgentEngine(PROJECT_ROOT, settings)
core_bridge = AegisCoreBridge.from_settings(settings)
core_runtime_client = AegisCoreClient.from_settings(settings)
creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
provider_accounts = ProviderAccountManager(PROJECT_ROOT, settings)
agent_bridge_runner = AgentBridgeRunner(provider_accounts.cli_bridge, provider_accounts.execution_environment)
model_manager = ModelManager(PROJECT_ROOT, settings, model_registry)
model_benchmarks = ModelBenchmarkManager(PROJECT_ROOT, settings, model_registry)
project_intelligence = ProjectIntelligenceEngine()
workspace_operations = WorkspaceOperationsEngine()
distributed_runtime = DistributedRuntimeManager(settings)
adaptive_intelligence = AdaptiveIntelligenceEngine()
productization = ProductizationEngine(settings)
ecosystem = EcosystemEngine(settings)
autonomous_engineering = AutonomousEngineeringEngine()
unified_runtime = UnifiedRuntimeEngine()
operating_environment = OperatingEnvironmentEngine()
unified_context = UnifiedContextEngine()
continuity = AegisContinuityEngine()
platform_discipline = PlatformDisciplineEngine()
account_store = AccountStore(PROJECT_ROOT, settings)


_WORKSPACE_SNAPSHOT_TTL_SECONDS = 2.0
_WORKSPACE_SNAPSHOT_CACHE_MAX = 64
_PROJECT_PLAN_CACHE_TTL_SECONDS = 30.0
_PROJECT_PLAN_CACHE_MAX = 128


_workspace_status_cache = WorkspaceStatusSnapshotCache(
    ttl_seconds=_WORKSPACE_SNAPSHOT_TTL_SECONDS,
    max_size=_WORKSPACE_SNAPSHOT_CACHE_MAX,
)
_project_plan_cache = ProjectPlanCache(
    ttl_seconds=_PROJECT_PLAN_CACHE_TTL_SECONDS,
    max_size=_PROJECT_PLAN_CACHE_MAX,
)
_agent_bridge_jobs_path = PROJECT_ROOT / "data" / "agent_bridge_jobs.json"
_agent_bridge_jobs_lock = threading.RLock()


def _workspace_intelligence_service() -> WorkspaceIntelligenceService:
    return WorkspaceIntelligenceService(
        workspace_manager_factory=lambda: workspace_manager,
        agent_factory=lambda: agent,
        project_intelligence_factory=lambda: project_intelligence,
        workspace_operations_factory=lambda: workspace_operations,
        model_benchmarks_factory=lambda: model_benchmarks,
        workspace_status_cache=_workspace_status_cache,
        workspace_resolver=_resolve_workspace_or_400,
        workspace_profile_builder=build_workspace_profile,
        invalidate_workspace_caches=_invalidate_workspace_caches,
    )


def _normalized_cache_path(path: Path) -> str:
    return normalized_cache_path(path)


def _cache_paths_are_related(left: str, right: str) -> bool:
    return cache_paths_are_related(left, right)


def _clear_workspace_status_cache(root: Path | None = None) -> None:
    _workspace_intelligence_service().clear_workspace_status_cache(root)


def _clear_project_plan_cache() -> None:
    _project_plan_cache.clear()


def _invalidate_workspace_caches(root: Path | None = None) -> None:
    _clear_workspace_status_cache(root)
    _clear_project_plan_cache()


def _prune_workspace_status_cache() -> None:
    _workspace_intelligence_service().prune_workspace_status_cache()


def _prune_project_plan_cache() -> None:
    _project_plan_cache.prune()


def _workspace_status_snapshot(root: Path) -> WorkspaceStatusSnapshot:
    return _workspace_intelligence_service().workspace_status_snapshot(root)


def _build_project_intelligence(
    root: Path,
    *,
    clear_memory: bool = False,
    rebuild_memory: bool = False,
) -> ProjectIntelligenceSnapshot:
    return _workspace_intelligence_service().build_project_intelligence(
        root,
        clear_memory=clear_memory,
        rebuild_memory=rebuild_memory,
    )


def _project_intelligence_snapshot(root: Path, *, rebuild: bool = False) -> ProjectIntelligenceSnapshot:
    return _workspace_intelligence_service().project_intelligence_snapshot(root, rebuild=rebuild)


def _build_workspace_operations(
    root: Path,
    *,
    refresh_project_intelligence: bool = True,
    generate_recommendations: bool = True,
    include_git: bool = True,
) -> WorkspaceOperationsSnapshot:
    return _workspace_intelligence_service().build_workspace_operations(
        root,
        refresh_project_intelligence=refresh_project_intelligence,
        generate_recommendations=generate_recommendations,
        include_git=include_git,
    )


def _workspace_operations_snapshot(root: Path, *, rebuild: bool = False) -> WorkspaceOperationsSnapshot:
    return _workspace_intelligence_service().workspace_operations_snapshot(root, rebuild=rebuild)


def _run_scheduled_intelligence_jobs(root: Path, request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
    return _workspace_intelligence_service().run_scheduled_intelligence_jobs(root, request)


def _project_plan_cache_key(request: ProjectScaffoldPlanRequest) -> str:
    return project_plan_cache_key(request)


def _cached_project_plan(request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
    cached = _project_plan_cache.get(request)
    if cached is not None:
        return cached

    response = project_scaffolder().plan_from_prompt(request)
    _project_plan_cache.set(request, response)
    return response


def project_scaffolder() -> ProjectScaffolder:
    return ProjectScaffolder(
        workspace_manager,
        agent.validation,
        commands=agent.commands,
        sandbox_profile=agent.approvals.sandbox,
    )


def refresh_runtime() -> None:
    global settings, workspace_manager, agent, core_bridge, core_runtime_client, creative_media, model_registry, provider_accounts, agent_bridge_runner, model_manager, model_benchmarks, workspace_operations, distributed_runtime, adaptive_intelligence, productization, ecosystem, autonomous_engineering, unified_runtime, operating_environment, unified_context, continuity, platform_discipline
    clear_settings_cache()
    _invalidate_workspace_caches()
    settings = get_settings()
    workspace_manager = WorkspaceManager(PROJECT_ROOT, settings)
    agent = AgentEngine(PROJECT_ROOT, settings)
    core_bridge = AegisCoreBridge.from_settings(settings)
    core_runtime_client = AegisCoreClient.from_settings(settings)
    creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
    model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
    provider_accounts = ProviderAccountManager(PROJECT_ROOT, settings)
    agent_bridge_runner = AgentBridgeRunner(provider_accounts.cli_bridge, provider_accounts.execution_environment)
    model_manager = ModelManager(PROJECT_ROOT, settings, model_registry)
    model_benchmarks = ModelBenchmarkManager(PROJECT_ROOT, settings, model_registry)
    workspace_operations = WorkspaceOperationsEngine()
    distributed_runtime = DistributedRuntimeManager(settings)
    adaptive_intelligence = AdaptiveIntelligenceEngine()
    productization = ProductizationEngine(settings)
    ecosystem = EcosystemEngine(settings)
    autonomous_engineering = AutonomousEngineeringEngine()
    unified_runtime = UnifiedRuntimeEngine()
    operating_environment = OperatingEnvironmentEngine()
    unified_context = UnifiedContextEngine()
    continuity = AegisContinuityEngine()
    platform_discipline = PlatformDisciplineEngine()


app = FastAPI(title="Auralith OS", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:5176",
        "http://localhost:5176",
        "http://127.0.0.1:5177",
        "http://localhost:5177",
        "http://127.0.0.1:5193",
        "http://localhost:5193",
        "http://127.0.0.1:5194",
        "http://localhost:5194",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_security_middleware(app, settings)
register_auth_routes(app, account_store_factory=lambda: account_store)


def _resolve_workspace_or_400(workspace_root: str | None) -> Path:
    try:
        return workspace_manager.resolve_workspace(workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_workspace_path_for_config(workspace_root: str | None) -> Path:
    try:
        return workspace_manager.resolve_workspace(workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_database_path(database_path: str) -> Path:
    candidate = Path(database_path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _dump_runtime_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump_runtime_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _dump_runtime_payload(item) for key, item in value.items()}
    return value


def _runtime_workers(root: Path) -> list[WorkerRuntimeInfo]:
    return _distributed_runtime_service().workers(root)


def _runtime_jobs(
    root: Path,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[ExecutionQueueItem]:
    return _distributed_runtime_service().jobs(root, status=status, limit=limit)


def _runtime_audit_events(
    *,
    worker_id: str = "",
    job_id: str = "",
    limit: int = 100,
) -> list[WorkerAuditEvent]:
    return _distributed_runtime_service().audit_events(worker_id=worker_id, job_id=job_id, limit=limit)


def _record_runtime_audit(event: WorkerAuditEvent) -> WorkerAuditEvent:
    return _distributed_runtime_service().record_audit(event)


def _runtime_snapshot(root: Path, routing: HybridRouteDecision | None = None) -> DistributedRuntimeSnapshot:
    return _distributed_runtime_service().snapshot(root, routing=routing)


def _runtime_snapshot_from_core(root: Path, result: CoreDelegationResult) -> DistributedRuntimeSnapshot | None:
    return _distributed_runtime_service().snapshot_from_core(root, result)


def _core_node_to_worker(node: dict[str, Any]) -> WorkerRuntimeInfo:
    return _distributed_runtime_service().core_node_to_worker(node)


def _core_supported_job_kinds(capabilities: set[str]) -> list[str]:
    return _distributed_runtime_service().core_supported_job_kinds(capabilities)


def _core_workload_to_queue_item(root: Path, workload: dict[str, Any]) -> ExecutionQueueItem:
    return _distributed_runtime_service().core_workload_to_queue_item(root, workload)


def _core_audit_to_worker_event(event: dict[str, Any]) -> WorkerAuditEvent:
    return _distributed_runtime_service().core_audit_to_worker_event(event)


def _core_observability_to_runtime(observability: dict[str, Any], generated_at: str) -> RuntimeObservabilitySnapshot:
    return _distributed_runtime_service().core_observability_to_runtime(observability, generated_at)


def _productization_snapshot(root: Path, *, refresh_metrics: bool = True) -> ProductizationSnapshot:
    return productization.snapshot(
        agent.store,
        project_root=root,
        checkpoints=workspace_manager.list_checkpoints(root, limit=100),
        runtime=_runtime_snapshot(root),
        refresh_metrics=refresh_metrics,
    )


def _ecosystem_snapshot(
    root: Path,
    *,
    rebuild_graph: bool = False,
    include_search_query: str = "",
) -> EcosystemSnapshot:
    intelligence = _project_intelligence_snapshot(root, rebuild=rebuild_graph)
    return ecosystem.snapshot(
        agent.store,
        project_root=root,
        project_intelligence=intelligence,
        refresh=EcosystemRefreshRequest(
            workspace_root=str(root),
            rebuild_graph=rebuild_graph,
            include_search_query=include_search_query,
        ),
    )


def _autonomous_snapshot(root: Path) -> AutonomousEngineeringSnapshot:
    return autonomous_engineering.snapshot(agent.store, project_root=root)


def _unified_runtime_snapshot(root: Path) -> UnifiedRuntimeSnapshot:
    tasks = agent.store.list_tasks(project_root=root, limit=200, include_subtasks=False)
    active_tasks = [task for task in tasks if task.status not in {"completed", "failed", "canceled"}]
    runtime = _runtime_snapshot(root)
    autonomous = _autonomous_snapshot(root)
    creative_library = creative_media.asset_library(limit=200)
    project_memory = agent.store.project_memory(project_root=root, limit=200)
    fix_memory = agent.store.fix_history(project_root=root, limit=200)
    project_snapshot = agent.store.project_intelligence(project_root=root)
    operations = _workspace_operations_snapshot(root)
    counts = RuntimeSignalCounts(
        task_count=len(tasks),
        active_task_count=len(active_tasks),
        project_memory_count=len(project_memory),
        fix_memory_count=len(fix_memory),
        creative_job_count=len(creative_library.jobs),
        creative_asset_count=creative_library.total_assets,
        worker_count=len(runtime.workers),
        queue_job_count=len(runtime.queue),
        objective_count=len(autonomous.objectives),
        pending_approval_count=len([gate for gate in autonomous.approval_gates if gate.status == "pending"]),
        recommendation_count=len(operations.recommendations),
        project_intelligence_ready=project_snapshot is not None,
    )
    return unified_runtime.snapshot(workspace_root=root, counts=counts)


def _operating_environment_snapshot(root: Path) -> OperatingEnvironmentSnapshot:
    return operating_environment.snapshot(workspace_root=root)


def _unified_context_snapshot(root: Path) -> UnifiedContextSnapshot:
    tasks = agent.store.list_tasks(project_root=root, limit=120, include_subtasks=True)
    task_events: dict[str, list[Any]] = {}
    for task in tasks[:40]:
        try:
            task_events[task.id] = agent.store.task_events(task.id)
        except KeyError:
            task_events[task.id] = []

    return unified_context.snapshot(
        workspace_root=root,
        tasks=tasks,
        task_events=task_events,
        project_intelligence=agent.store.project_intelligence(project_root=root),
        project_memory=agent.store.project_memory(project_root=root, limit=120),
        fix_memory=agent.store.fix_history(project_root=root, limit=80),
        creative_library=creative_media.asset_library(limit=120),
        workspace_operations=agent.store.workspace_operations_snapshot(project_root=root),
        operating_environment=_operating_environment_snapshot(root),
        distributed_runtime=_runtime_snapshot(root),
    )


def _global_command_preview(root: Path, request: GlobalCommandRequest) -> GlobalCommandResponse:
    snapshot = _unified_context_snapshot(root)
    return unified_context.preview_command(workspace_root=root, request=request, snapshot=snapshot)


def _continuity_snapshot(root: Path) -> AegisContinuitySnapshot:
    return continuity.snapshot(workspace_root=root, context=_unified_context_snapshot(root))


def _platform_discipline_snapshot(root: Path) -> PlatformDisciplineSnapshot:
    runtime = _unified_runtime_snapshot(root)
    continuity_snapshot = _continuity_snapshot(root)
    return platform_discipline.snapshot(workspace_root=root, runtime=runtime, continuity=continuity_snapshot)


def _task_transition_or_event(
    task_id: str,
    status: str,
    *,
    title: str,
    detail: str = "",
    error_summary: str = "",
    final_summary: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    if not task_id:
        return
    try:
        agent.store.transition_task(
            task_id,
            status,
            title=title,
            detail=detail,
            error_summary=error_summary,
            final_summary=final_summary,
            payload=payload,
        )
    except (KeyError, ValueError):
        agent.store.record_event(
            task_id,
            kind="distributed-runtime",
            title=title,
            status="error" if status == "failed" else "warning" if status in {"blocked", "needs_approval"} else "ok",
            detail=detail,
            payload={"requested_status": status, **(payload or {})},
        )


def _remote_sync_payload(root: Path, sections: list[str]) -> dict[str, Any]:
    return _distributed_runtime_service().remote_sync_payload(root, sections)


def _save_remote_sync_manifest(root: Path, request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
    return _distributed_runtime_service().save_remote_sync_manifest(root, request)


def _run_command_job(job: ExecutionQueueItem, root: Path, *, allow_commands: bool) -> tuple[str, str, dict[str, Any]]:
    return _distributed_runtime_service().run_command_job(job, root, allow_commands=allow_commands)


def _queue_repair_after_validation_failure(job: ExecutionQueueItem, root: Path, summary: str) -> ExecutionQueueItem:
    return _distributed_runtime_service().queue_repair_after_validation_failure(job, root, summary)


def _execute_runtime_job(job: ExecutionQueueItem, worker: WorkerRuntimeInfo, *, allow_commands: bool) -> tuple[ExecutionQueueItem, list[WorkerAuditEvent]]:
    return _distributed_runtime_service().execute_job(job, worker, allow_commands=allow_commands)


def _telemetry_snapshot_recommendations(snapshot: TelemetrySnapshot | None) -> list[str]:
    if snapshot is None:
        return [
            "No materialized telemetry snapshot exists for this workspace and window yet; refresh the snapshot before relying on cached dashboard data."
        ]
    recommendations: list[str] = []
    if snapshot.is_stale:
        recommendations.append(
            "The telemetry snapshot is stale; refresh it before using route quality for provider or policy decisions."
        )
    if snapshot.route_quality.overview.model_attempt_count == 0:
        recommendations.append(
            "The snapshot has no model-attempt telemetry yet; run routed tasks before using reliability or fallback rates."
        )
    if snapshot.feedback.summary.feedback_count == 0:
        recommendations.append(
            "The snapshot has no user feedback telemetry yet; feedback-aware route scoring will remain advisory."
        )
    return recommendations


def _telemetry_snapshot_prune_recommendations(prune: TelemetrySnapshotPruneInfo) -> list[str]:
    if prune.retention_max_snapshots <= 0:
        return []
    if prune.deleted_count > 0:
        return [prune.recommendation]
    if prune.retained_count >= prune.retention_max_snapshots:
        return [prune.recommendation]
    return []


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return sse_event(event, data)


def _structured_stream_intro(request: AgentRequest) -> str:
    return structured_stream_intro(request)


def _structured_stream_summary(response: AgentResponse) -> str:
    return structured_stream_summary(response)


def _structured_stream_reconciliation(response: AgentResponse, *, preview_was_streamed: bool) -> str:
    return structured_stream_reconciliation(response, preview_was_streamed=preview_was_streamed)


def _response_with_reconciliation(response: AgentResponse, notice: str) -> AgentResponse:
    return response_with_reconciliation(response, notice)


def _chat_stream_workspace_root(request: AgentRequest) -> str:
    resolver = getattr(agent, "stream_meta_workspace_root", None)
    if callable(resolver):
        try:
            return str(resolver(request))
        except Exception:
            pass
    return request.workspace_root or ""


async def _chat_stream_events(request: AgentRequest) -> AsyncIterator[str]:
    direct_stream = False
    response: AgentResponse | None = None
    try:
        direct_stream = await agent.can_stream_direct_chat(request)
    except Exception:
        direct_stream = False

    stream_mode = "chat-delta-final" if direct_stream else "structured-delta-final"
    yield _sse_event(
        "meta",
        {
            "type": "meta",
            "schema_version": "aegis.chat.stream.v1",
            "stream_mode": stream_mode,
            "workspace_root": _chat_stream_workspace_root(request),
            "mode": request.mode or "auto",
            "provider_id": request.selected_provider_id,
            "provider_label": request.selected_provider_label,
            "provider_api": request.selected_provider_api,
            "endpoint": request.selected_provider_endpoint,
            "model": request.selected_provider_model,
        },
    )
    try:
        if direct_stream:
            async for event, payload in agent.stream_direct_chat_events(request):
                yield _sse_event(event, payload)
            yield _sse_event("done", {"type": "done"})
            return

        yield _sse_event("status", {"type": "status", "stage": "planning", "message": "Preparing task context."})
        yield _sse_event(
            "delta",
            {
                "type": "delta",
                "delta": _structured_stream_intro(request),
                "stream_mode": stream_mode,
            },
        )
        yield _sse_event(
            "status",
            {
                "type": "status",
                "stage": "structured_model",
                "message": "Assembling the structured draft internally.",
            },
        )
        preview_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        preview_delta_count = 0

        def queue_preview_delta(event: Any) -> None:
            nonlocal preview_delta_count
            payload = preview_delta_payload(event, stream_mode=stream_mode)
            if payload is None:
                return
            if preview_delta_counts_as_streamed(payload):
                preview_delta_count += 1
            preview_queue.put_nowait(payload)

        run_task = asyncio.create_task(agent.run(request, stream_delta_callback=queue_preview_delta))
        try:
            while True:
                if run_task.done():
                    while not preview_queue.empty():
                        yield _sse_event("delta", preview_queue.get_nowait())
                    response = await run_task
                    break
                try:
                    yield _sse_event("delta", await asyncio.wait_for(preview_queue.get(), timeout=0.25))
                except asyncio.TimeoutError:
                    continue
        except Exception:
            if not run_task.done():
                run_task.cancel()
            raise

        reconciliation_notice = _structured_stream_reconciliation(
            response,
            preview_was_streamed=preview_delta_count > 0,
        )
        if reconciliation_notice:
            response = _response_with_reconciliation(response, reconciliation_notice)
            yield _sse_event(
                "status",
                {
                    "type": "status",
                    "stage": "preview_reconciliation",
                    "message": "Reconciling live preview with final structured response.",
                    "task_id": response.task_id,
                },
            )
            yield _sse_event(
                "delta",
                {
                    "type": "delta",
                    "delta": reconciliation_notice + "\n\n",
                    "stream_mode": stream_mode,
                    "source": "structured_preview_reconciliation",
                    "task_id": response.task_id,
                },
            )

        yield _sse_event(
            "delta",
            {
                "type": "delta",
                "delta": _structured_stream_summary(response),
                "stream_mode": stream_mode,
                "task_id": response.task_id,
            },
        )
        yield _sse_event(
            "status",
            {
                "type": "status",
                "stage": "finalizing",
                "message": "Final structured response is ready.",
                "task_id": response.task_id,
            },
        )
        yield _sse_event(
            "final",
            {
                "type": "final",
                "task_id": response.task_id,
                "response": response.model_dump(mode="json"),
            },
        )
        yield _sse_event("done", {"type": "done", "task_id": response.task_id})
    except Exception as exc:
        yield _sse_event(
            "error",
            {
                "type": "error",
                "message": "Aegis could not complete this streamed chat turn.",
                "detail": str(exc),
            },
        )
        yield _sse_event("done", {"type": "done"})
    finally:
        if request.workspace_root:
            _invalidate_workspace_caches(Path(request.workspace_root))
        if response is not None and response.workspace_root:
            _invalidate_workspace_caches(Path(response.workspace_root))


def _workspace_adapter_health(root: Path) -> list[ModelAdapterHealthInfo]:
    return model_registry.adapter_health(
        model_attempts=agent.store.recent_model_attempts(project_root=root, limit=200),
        route_health=agent.store.route_health_signals(project_root=root, limit=200),
    )


def _enrich_fallback_with_adapter_health(
    root: Path,
    fallback: FallbackInspectorResponse,
) -> FallbackInspectorResponse:
    return agent.store.fallback_inspector(
        project_root=root,
        limit=fallback.limit,
        adapter_health=_workspace_adapter_health(root),
    )


def _enrich_snapshot_with_adapter_health(root: Path, snapshot: TelemetrySnapshot | None) -> TelemetrySnapshot | None:
    if snapshot is None:
        return None
    snapshot.fallback_inspector = _enrich_fallback_with_adapter_health(root, snapshot.fallback_inspector)
    return snapshot


def _record_core_fallback(workflow: str, result: CoreDelegationResult) -> None:
    record_core_fallback(core_runtime_client, workflow, result)


def _settings_service() -> SettingsService:
    return SettingsService(
        settings_factory=lambda: settings,
        agent_factory=lambda: agent,
        core_bridge_factory=lambda: core_bridge,
        core_runtime_client_factory=lambda: core_runtime_client,
        workspace_manager_factory=lambda: workspace_manager,
        workspace_resolver=_resolve_workspace_or_400,
        config_workspace_resolver=_resolve_workspace_path_for_config,
        database_path_resolver=_resolve_database_path,
        update_env=update_env,
        refresh_runtime=refresh_runtime,
        has_env_file=has_env_file,
        core_result_data=_core_result_data,
        core_route_message=_core_route_message,
        core_route_status=_core_route_status,
        core_contract_version=_core_contract_version,
        core_delegation_data=_core_delegation_data,
        record_core_fallback=_record_core_fallback,
        mode_options=MODE_OPTIONS,
    )


def _runtime_health_service() -> RuntimeHealthService:
    return RuntimeHealthService(
        app_title=app.title,
        app_version=app.version,
        project_root_factory=lambda: PROJECT_ROOT,
        settings_factory=lambda: settings,
        agent_factory=lambda: agent,
        core_bridge_factory=lambda: core_bridge,
        model_registry_factory=lambda: model_registry,
        workspace_resolver=_resolve_workspace_path_for_config,
        database_path_resolver=_resolve_database_path,
        has_env_file=has_env_file,
    )


def _model_inventory_service() -> ModelInventoryService:
    return ModelInventoryService(
        settings_factory=lambda: settings,
        agent_factory=lambda: agent,
        model_registry_factory=lambda: model_registry,
        core_bridge_factory=lambda: core_bridge,
        workspace_resolver=_resolve_workspace_path_for_config,
        core_route_status=_core_route_status,
        core_contract_version=_core_contract_version,
        core_route_message=_core_route_message,
    )


def _distributed_runtime_service() -> DistributedRuntimeService:
    return DistributedRuntimeService(
        settings_factory=lambda: settings,
        agent_factory=lambda: agent,
        workspace_manager_factory=lambda: workspace_manager,
        distributed_runtime_factory=lambda: distributed_runtime,
        model_registry_factory=lambda: model_registry,
        model_benchmarks_factory=lambda: model_benchmarks,
        workspace_resolver=_resolve_workspace_or_400,
        runtime_payload_dumper=_dump_runtime_payload,
        project_intelligence_builder=_build_project_intelligence,
        task_transition_or_event=_task_transition_or_event,
    )


def _project_builder_service() -> ProjectBuilderService:
    return ProjectBuilderService(
        scaffolder_factory=project_scaffolder,
        plan_cache=_project_plan_cache,
        invalidate_workspace_caches=lambda root: _invalidate_workspace_caches(root),
    )


async def config_snapshot() -> AppConfig:
    return await _settings_service().config_snapshot()


async def runtime_health_snapshot() -> RuntimeHealthResponse:
    return await _runtime_health_service().snapshot()


register_runtime_routes(
    app,
    settings_factory=lambda: settings,
    core_bridge_factory=lambda: core_bridge,
    core_runtime_client_factory=lambda: core_runtime_client,
    workspace_resolver=_resolve_workspace_path_for_config,
    runtime_health_factory=runtime_health_snapshot,
    core_data_extractor=_core_delegation_data,
)


async def onboarding_status(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
    return await _settings_service().onboarding_status(workspace_root)


async def update_onboarding(request: dict[str, Any]) -> dict[str, Any]:
    return await _settings_service().update_onboarding(request)


async def run_onboarding_first_workflow(request: dict[str, Any]) -> dict[str, Any]:
    return await _settings_service().run_onboarding_first_workflow(request)


async def export_runtime_settings(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
    return await _settings_service().export_runtime_settings(workspace_root)


async def import_runtime_settings(request: dict[str, Any]) -> dict[str, Any]:
    return await _settings_service().import_runtime_settings(request)


register_onboarding_settings_routes(
    app,
    onboarding_status=lambda workspace_root: onboarding_status(workspace_root),
    update_onboarding=lambda request: update_onboarding(request),
    run_onboarding_first_workflow=lambda request: run_onboarding_first_workflow(request),
    export_runtime_settings=lambda workspace_root: export_runtime_settings(workspace_root),
    import_runtime_settings=lambda request: import_runtime_settings(request),
)


def _delegated_dict(result: CoreDelegationResult | None) -> dict[str, Any]:
    if result is not None and result.delegated and isinstance(result.data, dict):
        return result.data
    return {}


def _delegated_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _workflow_id(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("id") or value.get("workflow_id") or "").strip()


def _workflow_task_counts(workflow: dict[str, Any] | None) -> dict[str, int]:
    counts = {
        "queued": 0,
        "completed": 0,
        "failed": 0,
        "paused": 0,
        "waiting_input": 0,
        "approval_requests": 0,
    }
    tasks = workflow.get("tasks", []) if isinstance(workflow, dict) else []
    for task in tasks if isinstance(tasks, list) else []:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "unknown")
        if status in counts:
            counts[status] += 1
        if task.get("approval_required") or task.get("approval_gates") or status == "waiting_input":
            counts["approval_requests"] += 1
    return counts


def _first_core_error(*results: CoreDelegationResult | None) -> str:
    return next((str(result.error) for result in results if result is not None and result.error), "")


def _supervision_events_url(workflow_id: str, root: Path) -> str:
    if not workflow_id:
        return ""
    return f"/api/agent-supervision/workflows/{workflow_id}/events?{urlencode({'workspace_root': str(root)})}"


async def agent_supervision_status(
    workspace_root: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    runtime_result = await core_runtime_client.agent_runtime(root)
    workflows_result = await core_runtime_client.list_workflows(root, include_completed=False, limit=limit)
    runtime_data = _delegated_dict(runtime_result)
    workflows_data = _delegated_dict(workflows_result)
    workflows = _delegated_list(workflows_data.get("workflows"))
    active_workflows = _delegated_list(workflows_data.get("active_workflows"))

    requested_workflow_id = (workflow_id or "").strip()
    if not requested_workflow_id:
        requested_workflow_id = _workflow_id(active_workflows[0] if active_workflows else None) or _workflow_id(
            workflows[0] if workflows else None
        )

    dashboard_result: CoreDelegationResult | None = None
    coordination_result: CoreDelegationResult | None = None
    dashboard_data: dict[str, Any] = {}
    coordination_data: dict[str, Any] = {}
    active_workflow: dict[str, Any] | None = None
    if requested_workflow_id:
        dashboard_result = await core_runtime_client.workflow_dashboard(root, requested_workflow_id)
        coordination_result = await core_runtime_client.workflow_agent_coordination(root, requested_workflow_id)
        dashboard_data = _delegated_dict(dashboard_result)
        coordination_data = _delegated_dict(coordination_result)
        active_workflow = dashboard_data.get("workflow") if isinstance(dashboard_data.get("workflow"), dict) else None
        if active_workflow is None:
            active_workflow = next((item for item in workflows if _workflow_id(item) == requested_workflow_id), None)
    elif active_workflows:
        active_workflow = active_workflows[0]

    if not coordination_data and isinstance(dashboard_data.get("agent_coordination"), dict):
        coordination_data = dashboard_data["agent_coordination"]

    timeline = []
    if isinstance(coordination_data.get("execution_timeline"), list):
        timeline = coordination_data["execution_timeline"]
    elif isinstance(dashboard_data.get("timeline"), list):
        timeline = dashboard_data["timeline"]

    runtime_status = await core_runtime_client.runtime_status(root)
    if hasattr(core_runtime_client, "security_status"):
        security_result = await core_runtime_client.security_status(root)
    else:
        security_result = CoreDelegationResult(
            delegated=False,
            ok=False,
            reachable=False,
            status_code=None,
            kind="security.status",
            error="",
        )
    security_data = _core_delegation_data(security_result, "security.status") if security_result.delegated else {}
    core_connected = any(
        result is not None and result.delegated
        for result in (runtime_result, workflows_result, dashboard_result, coordination_result, security_result)
    )
    last_error = _first_core_error(security_result, coordination_result, dashboard_result, workflows_result, runtime_result)
    fallback_mode = not core_connected or bool(runtime_status.get("fallback_mode_active"))
    selected_workflow_id = _workflow_id(active_workflow) or requested_workflow_id
    return {
        "workspace_root": str(root),
        "core_connected": core_connected,
        "delegated_workflows_enabled": core_runtime_client.delegated_workflows_enabled,
        "fallback_mode_active": fallback_mode,
        "last_core_error": last_error or runtime_status.get("last_core_error", ""),
        "runtime_status": runtime_status,
        "security_status": trust_status(settings, core_status=security_data),
        "runtime": runtime_data,
        "workflows": workflows,
        "active_workflows": active_workflows,
        "active_workflow": active_workflow,
        "coordination": coordination_data,
        "timeline": timeline,
        "task_counts": _workflow_task_counts(active_workflow),
        "safety": coordination_data.get("safety", runtime_data.get("safety_controls", {})),
        "events_url": _supervision_events_url(selected_workflow_id, root),
    }


async def agent_supervision_workflow_agents(
    workflow_id: str,
    workspace_root: str | None = Query(default=None),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.workflow_agent_coordination(root, workflow_id)
    if not result.delegated:
        return {
            "ok": False,
            "delegated": False,
            "core_connected": result.reachable,
            "workflow_id": workflow_id,
            "workspace_root": str(root),
            "error": result.error or "Aegis Core agent coordination is unavailable.",
            "coordination": {},
        }
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workflow_id": workflow_id,
        "workspace_root": str(root),
        "coordination": _core_delegation_data(result, "agent.coordination"),
    }


async def agent_supervision_workflow_step(
    workflow_id: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.step_workflow(
        root,
        workflow_id,
        action=str(request.get("action") or "advance"),
        task_id=str(request.get("task_id") or "").strip() or None,
        approval=bool(request.get("approval", False)),
        summary=str(request.get("summary") or "").strip() or None,
        payload=request.get("payload") if isinstance(request.get("payload"), dict) else {},
    )
    if not result.delegated:
        _record_core_fallback("workflow.step", result)
        return {
            "ok": False,
            "delegated": False,
            "core_connected": result.reachable,
            "workflow_id": workflow_id,
            "workspace_root": str(root),
            "error": result.error or "Aegis Core workflow control is unavailable.",
        }
    return {"ok": True, "delegated": True, **_core_delegation_data(result, "workflow.step")}


async def agent_supervision_delegate_agent(
    workflow_id: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.delegate_agent_task(
        root,
        workflow_id,
        task_id=str(request.get("task_id") or "").strip(),
        agent_id=str(request.get("agent_id") or "").strip(),
        approval=bool(request.get("approval", False)),
        reason=str(request.get("reason") or "").strip(),
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if not result.delegated:
        _record_core_fallback("agent.delegation", result)
        return {
            "ok": False,
            "delegated": False,
            "core_connected": result.reachable,
            "workflow_id": workflow_id,
            "workspace_root": str(root),
            "error": result.error or "Aegis Core agent delegation is unavailable.",
        }
    return {"ok": True, "delegated": True, **_core_delegation_data(result, "agent.delegation")}


async def agent_supervision_workflow_events(
    workflow_id: str,
    workspace_root: str | None = Query(default=None),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    follow: bool = Query(default=True),
    max_seconds: int = Query(default=30, ge=1, le=120),
) -> StreamingResponse:
    root = _resolve_workspace_or_400(workspace_root)
    url = f"{core_runtime_client.base_url}/v1/workflows/{workflow_id}/events"
    params = {
        "workspace": str(root),
        "since": since,
        "limit": limit,
        "follow": follow,
        "max_seconds": max_seconds,
    }

    async def stream_core_events() -> AsyncIterator[str]:
        if not core_runtime_client.delegated_workflows_enabled:
            yield _sse_event(
                "supervision_error",
                {"type": "supervision_error", "message": "Aegis Core delegated workflows are disabled."},
            )
            return
        try:
            timeout = httpx.Timeout(connect=core_runtime_client.timeout_seconds, read=None, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", url, params=params) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
        except Exception as exc:
            yield _sse_event(
                "supervision_error",
                {"type": "supervision_error", "message": f"Aegis Core workflow event stream unavailable: {exc}"},
            )

    return StreamingResponse(stream_core_events(), media_type="text/event-stream")


register_agent_supervision_routes(
    app,
    agent_supervision_status=lambda workspace_root, workflow_id, limit: agent_supervision_status(
        workspace_root,
        workflow_id,
        limit,
    ),
    agent_supervision_workflow_agents=lambda workflow_id, workspace_root: agent_supervision_workflow_agents(
        workflow_id,
        workspace_root,
    ),
    agent_supervision_workflow_step=lambda workflow_id, request: agent_supervision_workflow_step(workflow_id, request),
    agent_supervision_delegate_agent=lambda workflow_id, request: agent_supervision_delegate_agent(
        workflow_id,
        request,
    ),
    agent_supervision_workflow_events=lambda workflow_id, workspace_root, since, limit, follow, max_seconds: agent_supervision_workflow_events(
        workflow_id,
        workspace_root,
        since,
        limit,
        follow,
        max_seconds,
    ),
)


def _quality_unavailable_payload(root: Path, result: CoreDelegationResult, *, kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    _record_core_fallback(kind, result)
    return {
        "ok": False,
        "delegated": False,
        "core_connected": result.reachable,
        "workspace_root": str(root),
        "error": result.error or "Aegis Core quality gates are unavailable.",
        "fallback_mode_active": True,
        **(extra or {}),
    }


async def quality_gates_status(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.quality_gates(root, limit=limit)
    if not result.delegated:
        return _quality_unavailable_payload(
            root,
            result,
            kind="quality.gates",
            extra={
                "latest": None,
                "recent_runs": [],
                "reports": [],
                "benchmark_history": [],
                "benchmark_suites": [],
                "statistics": {},
            },
        )
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.gates"),
    }


async def evaluate_quality_gates(request: dict[str, Any]) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.evaluate_quality_gates(
        root,
        changes=request.get("changes") if isinstance(request.get("changes"), list) else [],
        workflow_id=str(request.get("workflow_id") or "").strip() or None,
        validation_id=str(request.get("validation_id") or "").strip() or None,
        validation=request.get("validation") if isinstance(request.get("validation"), dict) else None,
        approval=bool(request.get("approval", False)),
        checkpoint_id=str(request.get("checkpoint_id") or "").strip() or None,
        max_files_changed=int(request.get("max_files_changed") or 25),
        restricted_paths=request.get("restricted_paths") if isinstance(request.get("restricted_paths"), list) else [],
        validation_required=bool(request.get("validation_required", False)),
        dry_run=bool(request.get("dry_run", True)),
        persist=bool(request.get("persist", True)),
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="quality.gates.evaluate")
    return {
        "ok": bool(result.ok),
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.gates.evaluate"),
    }


async def workflow_quality_gates(
    workflow_id: str,
    workspace_root: str | None = Query(default=None),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.workflow_quality(root, workflow_id)
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="workflow.quality", extra={"workflow_id": workflow_id})
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "workflow.quality"),
    }


async def quality_benchmarks(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.benchmarks(root, limit=limit)
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="quality.benchmarks", extra={"suites": [], "history": [], "latest": None})
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.benchmarks"),
    }


async def run_quality_benchmark(request: dict[str, Any]) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.run_benchmark(
        root,
        suite_ids=request.get("suite_ids") if isinstance(request.get("suite_ids"), list) else [],
        workflow_id=str(request.get("workflow_id") or "").strip() or None,
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="quality.benchmark.run")
    return {
        "ok": bool(result.ok),
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.benchmark.run"),
    }


async def evaluation_reports(
    workspace_root: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.evaluation_reports(root, workflow_id=workflow_id, limit=limit)
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="quality.evaluation_reports", extra={"reports": [], "latest": None})
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.evaluation_reports"),
    }


async def create_evaluation_report(request: dict[str, Any]) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.create_evaluation_report(
        root,
        workflow_id=str(request.get("workflow_id") or "").strip() or None,
        quality_run_id=str(request.get("quality_run_id") or "").strip() or None,
        title=str(request.get("title") or ""),
        changes=request.get("changes") if isinstance(request.get("changes"), list) else [],
        tests_run=request.get("tests_run") if isinstance(request.get("tests_run"), list) else [],
        repairs_attempted=request.get("repairs_attempted") if isinstance(request.get("repairs_attempted"), list) else [],
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if not result.delegated:
        return _quality_unavailable_payload(root, result, kind="quality.evaluation_report")
    return {
        "ok": bool(result.ok),
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        **_core_delegation_data(result, "quality.evaluation_report"),
    }


register_quality_evaluation_routes(
    app,
    quality_gates_status=lambda workspace_root, limit: quality_gates_status(workspace_root, limit),
    evaluate_quality_gates=lambda request: evaluate_quality_gates(request),
    workflow_quality_gates=lambda workflow_id, workspace_root: workflow_quality_gates(workflow_id, workspace_root),
    quality_benchmarks=lambda workspace_root, limit: quality_benchmarks(workspace_root, limit),
    run_quality_benchmark=lambda request: run_quality_benchmark(request),
    evaluation_reports=lambda workspace_root, workflow_id, limit: evaluation_reports(workspace_root, workflow_id, limit),
    create_evaluation_report=lambda request: create_evaluation_report(request),
)


async def unified_runtime_status(workspace_root: str | None = Query(default=None)) -> UnifiedRuntimeSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _unified_runtime_snapshot(root)


async def operating_environment_status(workspace_root: str | None = Query(default=None)) -> OperatingEnvironmentSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _operating_environment_snapshot(root)


async def operating_environment_action_preview(
    request: OperatingEnvironmentActionRequest,
) -> OperatingEnvironmentActionResponse:
    if request.workspace_root:
        _resolve_workspace_or_400(request.workspace_root)
    return operating_environment.preview_action(request)


async def unified_context_status(workspace_root: str | None = Query(default=None)) -> UnifiedContextSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _unified_context_snapshot(root)


async def unified_context_search(request: UnifiedContextSearchRequest) -> UnifiedContextSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    snapshot = _unified_context_snapshot(root)
    return unified_context.search(snapshot, request.model_copy(update={"workspace_root": str(root)}))


async def global_command_preview(request: GlobalCommandRequest) -> GlobalCommandResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _global_command_preview(root, request)


async def global_command_submit(request: GlobalCommandRequest) -> GlobalCommandResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    response = _global_command_preview(root, request)
    if not request.create_task or not response.route.creates_task:
        return response

    task_id = agent.store.create_task(
        mode="develop" if response.route.task_kind == "coding" else "build",
        workspace_root=root,
        message=request.command,
        title=f"Global command: {response.route.intent.replace('_', ' ')}",
        user_goal=request.command,
        assigned_agent_role=response.route.target_system,
        related_files=[
            path
            for result in response.context_results[:8]
            for path in result.record.related_files[:4]
        ],
        validation_commands=[],
    )
    event = agent.store.record_event(
        task_id,
        kind="global_command",
        title="Global command routed to task",
        detail=response.route.reason,
        payload={
            "entrypoint": request.entrypoint,
            "intent": response.route.intent,
            "target_system": response.route.target_system,
            "approval_required": response.route.approval_required,
            "endpoint": response.route.endpoint,
        },
    )
    return response.model_copy(update={"task": agent.store.task(task_id), "event": event})


async def continuity_status(workspace_root: str | None = Query(default=None)) -> AegisContinuitySnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _continuity_snapshot(root)


async def continuity_timeline_search(request: TimelineSearchRequest) -> TimelineSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    snapshot = _continuity_snapshot(root)
    return continuity.search_timeline(snapshot, request.model_copy(update={"workspace_root": str(root)}))


async def platform_discipline_status(workspace_root: str | None = Query(default=None)) -> PlatformDisciplineSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _platform_discipline_snapshot(root)


async def models() -> ModelInventoryResponse:
    return await _model_inventory_service().models()


register_runtime_convergence_routes(
    app,
    unified_runtime_status=lambda workspace_root: unified_runtime_status(workspace_root),
    operating_environment_status=lambda workspace_root: operating_environment_status(workspace_root),
    operating_environment_action_preview=lambda request: operating_environment_action_preview(request),
    unified_context_status=lambda workspace_root: unified_context_status(workspace_root),
    unified_context_search=lambda request: unified_context_search(request),
    global_command_preview=lambda request: global_command_preview(request),
    global_command_submit=lambda request: global_command_submit(request),
    continuity_status=lambda workspace_root: continuity_status(workspace_root),
    continuity_timeline_search=lambda request: continuity_timeline_search(request),
    platform_discipline_status=lambda workspace_root: platform_discipline_status(workspace_root),
    models=lambda: models(),
)


register_model_registry_routes(
    app,
    project_root=PROJECT_ROOT,
    model_registry_factory=lambda: model_registry,
    model_benchmarks_factory=lambda: model_benchmarks,
    model_manager_factory=lambda: model_manager,
    agent_factory=lambda: agent,
    core_runtime_client_factory=lambda: core_runtime_client,
    workspace_resolver=_resolve_workspace_or_400,
    core_registry_merger=merge_core_model_registry,
)


register_provider_account_routes(
    app,
    provider_accounts_factory=lambda: provider_accounts,
)


async def _create_agent_bridge_checkpoint(root: Path, provider_label: str) -> CheckpointSummary:
    summary = f"Before {provider_label} bridge execution"
    core_result = await core_runtime_client.create_checkpoint(root, paths=[], summary=summary)
    if core_result.delegated:
        return checkpoint_summary_from_core(_core_delegation_data(core_result, "checkpoints.create"))
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "checkpoints.create")
    _record_core_fallback("checkpoints.create", core_result)
    return workspace_manager.create_checkpoint(root, paths=[], summary=summary)


def _agent_bridge_service() -> AgentBridgeService:
    return AgentBridgeService(
        settings_factory=lambda: settings,
        workspace_manager_factory=lambda: workspace_manager,
        workspace_operations_factory=lambda: workspace_operations,
        agent_factory=lambda: agent,
        provider_accounts_factory=lambda: provider_accounts,
        agent_bridge_runner_factory=lambda: agent_bridge_runner,
        workspace_resolver=_resolve_workspace_or_400,
        checkpoint_creator=_create_agent_bridge_checkpoint,
        runtime_payload_dumper=_dump_runtime_payload,
        jobs_path=_agent_bridge_jobs_path,
        jobs_lock=_agent_bridge_jobs_lock,
    )


def _agent_bridge_workspace_state(root: Path, *, max_files: int = 5000) -> dict[str, dict[str, Any]]:
    return _agent_bridge_service().workspace_state(root, max_files=max_files)


def _agent_bridge_workspace_changes(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return _agent_bridge_service().workspace_changes(before, after)


def _augment_agent_bridge_response(
    response: AgentBridgeExecuteResponse,
    *,
    checkpoint: CheckpointSummary | None,
    before_state: dict[str, dict[str, Any]],
    after_state: dict[str, dict[str, Any]],
) -> AgentBridgeExecuteResponse:
    return _agent_bridge_service().augment_response(
        response,
        checkpoint=checkpoint,
        before_state=before_state,
        after_state=after_state,
    )


def _agent_bridge_response_payload(response: AgentBridgeExecuteResponse) -> dict[str, Any]:
    return _agent_bridge_service().response_payload(response)


def _agent_bridge_job_terminal(status: str) -> bool:
    return _agent_bridge_service().job_terminal(status)


def _trim_agent_bridge_output(value: str) -> str:
    return _agent_bridge_service().trim_output(value)


def _agent_bridge_request_payload(request: AgentBridgeExecuteRequest) -> dict[str, Any]:
    return _agent_bridge_service().request_payload(request)


def _agent_bridge_preflight_signature(request: AgentBridgeExecuteRequest, preflight: AgentBridgePreflightResponse) -> str:
    return _agent_bridge_service().preflight_signature(request, preflight)


def _agent_bridge_preflight_response(
    request: AgentBridgeExecuteRequest,
    manifest: Any,
    root: Path,
) -> AgentBridgePreflightResponse:
    return _agent_bridge_service().preflight_response(request, manifest, root)


def _require_agent_bridge_preflight(
    request: AgentBridgeExecuteRequest,
    manifest: Any,
    root: Path,
) -> AgentBridgePreflightResponse:
    return _agent_bridge_service().require_preflight(request, manifest, root)


def _load_agent_bridge_jobs() -> list[AgentBridgeJobInfo]:
    return _agent_bridge_service().load_jobs()


def _save_agent_bridge_jobs(jobs: list[AgentBridgeJobInfo]) -> None:
    _agent_bridge_service().save_jobs(jobs)


def _upsert_agent_bridge_job(job: AgentBridgeJobInfo) -> None:
    _agent_bridge_service().upsert_job(job)


def _agent_bridge_jobs(limit: int = 25) -> list[AgentBridgeJobInfo]:
    return _agent_bridge_service().jobs(limit)


def _agent_bridge_job_or_404(job_id: str) -> AgentBridgeJobInfo:
    return _agent_bridge_service().job_or_404(job_id)


def _new_agent_bridge_job(request: AgentBridgeExecuteRequest, *, retry_of: str = "") -> AgentBridgeJobInfo:
    return _agent_bridge_service().new_job(request, retry_of=retry_of)


def _agent_bridge_job_from_response(
    job: AgentBridgeJobInfo,
    response: AgentBridgeExecuteResponse,
    *,
    message: str = "",
) -> AgentBridgeJobInfo:
    return _agent_bridge_service().job_from_response(job, response, message=message)


async def _start_agent_bridge_job(request: AgentBridgeExecuteRequest, *, retry_of: str = "") -> AgentBridgeJobResponse:
    return await _agent_bridge_service().start_job(request, retry_of=retry_of)


async def _run_agent_bridge_job(job_id: str, request: AgentBridgeExecuteRequest, cancel_event: asyncio.Event) -> None:
    await _agent_bridge_service().run_job(job_id, request, cancel_event)


def _handle_agent_bridge_job_done(job_id: str, task: asyncio.Task[None]) -> None:
    _agent_bridge_service().handle_job_done(job_id, task)


async def _cancel_agent_bridge_job(job_id: str) -> AgentBridgeJobResponse:
    return await _agent_bridge_service().cancel_job(job_id)


async def _retry_agent_bridge_job(job_id: str) -> AgentBridgeJobResponse:
    return await _agent_bridge_service().retry_job(job_id)

register_agent_bridge_job_routes(
    app,
    start_job=_start_agent_bridge_job,
    list_jobs=_agent_bridge_jobs,
    get_job=_agent_bridge_job_or_404,
    cancel_job=_cancel_agent_bridge_job,
    retry_job=_retry_agent_bridge_job,
)


async def preflight_agent_bridge(request: AgentBridgeExecuteRequest) -> AgentBridgePreflightResponse:
    return await _agent_bridge_service().preflight_agent_bridge(request)


async def execute_agent_bridge(request: AgentBridgeExecuteRequest) -> AgentBridgeExecuteResponse:
    return await _agent_bridge_service().execute_agent_bridge(request)


register_agent_bridge_execution_routes(
    app,
    preflight_bridge=preflight_agent_bridge,
    execute_bridge=execute_agent_bridge,
)


async def _terminate_agent_bridge_process(process: asyncio.subprocess.Process) -> None:
    await _agent_bridge_service().terminate_process(process)


async def _read_agent_bridge_stream(
    reader: asyncio.StreamReader | None,
    stream_name: str,
    queue: asyncio.Queue[tuple[str, str | None]],
) -> None:
    await _agent_bridge_service().read_stream(reader, stream_name, queue)


async def _agent_bridge_stream_events(
    request: AgentBridgeExecuteRequest,
    root: Path,
    manifest: Any,
) -> AsyncIterator[str]:
    async for event in _agent_bridge_service().stream_events(request, root, manifest):
        yield event


async def stream_agent_bridge(request: AgentBridgeExecuteRequest) -> StreamingResponse:
    return await _agent_bridge_service().stream_agent_bridge(request)


register_agent_bridge_streaming_routes(
    app,
    stream_bridge=stream_agent_bridge,
)


register_media_routes(
    app,
    creative_media_factory=lambda: creative_media,
)


async def save_config(request: ConfigUpdateRequest) -> AppConfig:
    return await _settings_service().save_config(request, config_snapshot=config_snapshot)


register_config_routes(
    app,
    config_snapshot=lambda: config_snapshot(),
    save_config=lambda request: save_config(request),
)


register_file_routes(
    app,
    workspace_resolver=_resolve_workspace_or_400,
    workspace_manager_factory=lambda: workspace_manager,
)


async def workspace_profile(workspace_root: str | None = Query(default=None)) -> WorkspaceProfileResponse:
    return await _workspace_intelligence_service().workspace_profile(workspace_root)


register_workspace_profile_routes(
    app,
    workspace_profile=lambda workspace_root: workspace_profile(workspace_root),
)


async def project_intelligence_snapshot(workspace_root: str | None = None) -> ProjectIntelligenceSnapshot:
    return await _workspace_intelligence_service().project_intelligence_snapshot_route(workspace_root)


async def reindex_project_intelligence(request: ProjectIntelligenceReindexRequest) -> ProjectIntelligenceSnapshot:
    return await _workspace_intelligence_service().reindex_project_intelligence(request)


async def project_intelligence_context(request: ProjectContextSelectionRequest) -> ProjectContextSelectionResponse:
    return await _workspace_intelligence_service().project_intelligence_context(request)


register_project_intelligence_routes(
    app,
    project_intelligence_snapshot=lambda workspace_root: project_intelligence_snapshot(workspace_root),
    reindex_project_intelligence=lambda request: reindex_project_intelligence(request),
    project_intelligence_context=lambda request: project_intelligence_context(request),
)


async def workspace_intelligence_snapshot(workspace_root: str | None = None) -> WorkspaceOperationsSnapshot:
    return await _workspace_intelligence_service().workspace_intelligence_snapshot(workspace_root)


async def scan_workspace_intelligence(request: WorkspaceOperationsScanRequest) -> WorkspaceOperationsSnapshot:
    return await _workspace_intelligence_service().scan_workspace_intelligence(request)


async def workspace_intelligence_events(
    workspace_root: str | None = None,
    limit: int = 80,
) -> list[WorkspaceWatchEvent]:
    return await _workspace_intelligence_service().workspace_intelligence_events(workspace_root, limit)


async def workspace_intelligence_recommendations(
    workspace_root: str | None = None,
    include_dismissed: bool = False,
    limit: int = 100,
) -> list[WorkspaceRecommendation]:
    return await _workspace_intelligence_service().workspace_intelligence_recommendations(
        workspace_root,
        include_dismissed,
        limit,
    )


async def dismiss_workspace_recommendation(
    recommendation_id: str,
    request: RecommendationActionRequest | None = None,
) -> RecommendationFixResponse:
    return await _workspace_intelligence_service().dismiss_workspace_recommendation(recommendation_id, request)


async def fix_workspace_recommendation(
    recommendation_id: str,
    request: RecommendationFixRequest | None = None,
) -> RecommendationFixResponse:
    return await _workspace_intelligence_service().fix_workspace_recommendation(recommendation_id, request)


async def workspace_intelligence_jobs(workspace_root: str | None = None) -> list[ScheduledIntelligenceJob]:
    return await _workspace_intelligence_service().workspace_intelligence_jobs(workspace_root)


async def run_workspace_intelligence_jobs(request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
    return await _workspace_intelligence_service().run_workspace_intelligence_jobs(request)


async def workspace_setup(request: WorkspaceSetupRequest) -> WorkspaceSetupResponse:
    return await _workspace_intelligence_service().workspace_setup(request)


register_workspace_intelligence_routes(
    app,
    workspace_intelligence_snapshot=lambda workspace_root: workspace_intelligence_snapshot(workspace_root),
    scan_workspace_intelligence=lambda request: scan_workspace_intelligence(request),
    workspace_intelligence_events=lambda workspace_root, limit: workspace_intelligence_events(workspace_root, limit),
    workspace_intelligence_recommendations=(
        lambda workspace_root, include_dismissed, limit: workspace_intelligence_recommendations(
            workspace_root,
            include_dismissed,
            limit,
        )
    ),
    dismiss_workspace_recommendation=lambda recommendation_id, request: dismiss_workspace_recommendation(
        recommendation_id,
        request,
    ),
    fix_workspace_recommendation=lambda recommendation_id, request: fix_workspace_recommendation(
        recommendation_id,
        request,
    ),
    workspace_intelligence_jobs=lambda workspace_root: workspace_intelligence_jobs(workspace_root),
    run_workspace_intelligence_jobs=lambda request: run_workspace_intelligence_jobs(request),
    workspace_setup=lambda request: workspace_setup(request),
)


async def workspace_autopilot_status(workspace_root: str | None = None) -> WorkspaceAutopilotStatusResponse:
    root = _resolve_workspace_or_400(workspace_root)
    snapshot = _workspace_status_snapshot(root)
    return build_workspace_autopilot_status(
        workspace_root=str(root),
        manifest=snapshot.manifest,
        dependency_profile=snapshot.dependency_profile,
        instruction_status=snapshot.instruction_status,
        validation_plan=snapshot.validation_plan,
        command_history=snapshot.command_history,
        readiness=snapshot.readiness,
    )


def _legacy_workspace_autopilot_payload(root: Path) -> dict[str, Any]:
    snapshot = _workspace_status_snapshot(root)
    status = build_workspace_autopilot_status(
        workspace_root=str(root),
        manifest=snapshot.manifest,
        dependency_profile=snapshot.dependency_profile,
        instruction_status=snapshot.instruction_status,
        validation_plan=snapshot.validation_plan,
        command_history=snapshot.command_history,
        readiness=snapshot.readiness,
    )
    return _dump_runtime_payload(status)


def _autopilot_gateway_response(result: CoreDelegationResult, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if result.delegated:
        return {
            "runtime": "core",
            "fallback": False,
            "core_connected": True,
            "data": result.data or {},
            "last_core_error": "",
        }
    return {
        "runtime": "website_fallback",
        "fallback": True,
        "core_connected": bool(result.reachable),
        "data": fallback or {},
        "last_core_error": result.error or core_runtime_client.last_core_error,
    }


async def api_autopilot_modes() -> dict[str, Any]:
    result = await core_runtime_client.autopilot_modes()
    fallback = {
        "modes": [
            {"id": "suggest_only", "display_name": "Suggest Only"},
            {"id": "semi_autonomous", "display_name": "Semi Autonomous"},
            {"id": "validation_autopilot", "display_name": "Validation Autopilot"},
        ],
        "specializations": [
            {"id": "feature_autopilot", "display_name": "Feature Autopilot"},
            {"id": "repair_autopilot", "display_name": "Repair Autopilot"},
            {"id": "refactor_autopilot", "display_name": "Refactor Autopilot"},
            {"id": "deployment_autopilot", "display_name": "Deployment Autopilot"},
            {"id": "workspace_intelligence_autopilot", "display_name": "Workspace Intelligence Autopilot"},
        ],
        "default_specialization": "feature_autopilot",
        "safety_invariants": ["Core connection required for production Autopilot execution."],
    }
    return _autopilot_gateway_response(result, fallback=fallback)


async def api_autopilot_supervision(
    workspace_root: str | None = None,
    autopilot_id: str | None = None,
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.autopilot_supervision(root, autopilot_id=autopilot_id)
    fallback = {
        "active_run": None,
        "pending_approvals": [],
        "validation_status": "legacy_workspace_status",
        "legacy_status": _legacy_workspace_autopilot_payload(root),
    }
    return _autopilot_gateway_response(result, fallback=fallback)


async def api_start_autopilot(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.start_autopilot(
        root,
        objective=str(payload.get("objective") or payload.get("goal") or "").strip(),
        mode=str(payload.get("mode") or "semi_autonomous"),
        workflow_type=str(payload.get("workflow_type") or payload.get("workflowType") or "generate_feature"),
        roadmap=payload.get("roadmap") if isinstance(payload.get("roadmap"), list) else [],
        target_files=payload.get("target_files") if isinstance(payload.get("target_files"), list) else payload.get("targetFiles") if isinstance(payload.get("targetFiles"), list) else [],
        constraints=payload.get("constraints") if isinstance(payload.get("constraints"), list) else [],
        validation_commands=payload.get("validation_commands") if isinstance(payload.get("validation_commands"), list) else [],
        execution_plan=payload.get("execution_plan") if isinstance(payload.get("execution_plan"), dict) else {},
        specialization=str(payload.get("specialization") or payload.get("autopilot_specialization") or payload.get("autopilotSpecialization") or "").strip() or None,
        approval=bool(payload.get("approval")),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core Autopilot is unavailable.")
    return _autopilot_gateway_response(result)


async def api_autopilot_action(autopilot_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.autopilot_action(
        root,
        autopilot_id,
        action=str(payload.get("action") or "advance"),
        approval=bool(payload.get("approval")),
        summary=str(payload.get("summary") or ""),
        payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core Autopilot action failed.")
    return _autopilot_gateway_response(result)


async def api_autopilot_replay(
    autopilot_id: str,
    workspace_root: str | None = None,
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.autopilot_replay(root, autopilot_id)
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core Autopilot replay is unavailable.")
    return _autopilot_gateway_response(result)


async def api_autopilot_observability(workspace_root: str | None = None) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.autopilot_observability(root)
    return _autopilot_gateway_response(result, fallback={"run_count": 0, "active_count": 0, "blocked_action_count": 0})


async def api_autopilot_memory(workspace_root: str | None = None) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.autopilot_memory(root)
    return _autopilot_gateway_response(result, fallback={"memory": {}, "categories": [], "privacy": {"storage": "core_offline"}})


register_autopilot_routes(
    app,
    workspace_autopilot_status=lambda workspace_root: workspace_autopilot_status(workspace_root),
    api_autopilot_modes=lambda: api_autopilot_modes(),
    api_autopilot_supervision=lambda workspace_root, autopilot_id: api_autopilot_supervision(
        workspace_root,
        autopilot_id,
    ),
    api_start_autopilot=lambda payload: api_start_autopilot(payload),
    api_autopilot_action=lambda autopilot_id, payload: api_autopilot_action(autopilot_id, payload),
    api_autopilot_replay=lambda autopilot_id, workspace_root: api_autopilot_replay(autopilot_id, workspace_root),
    api_autopilot_observability=lambda workspace_root: api_autopilot_observability(workspace_root),
    api_autopilot_memory=lambda workspace_root: api_autopilot_memory(workspace_root),
)


async def api_collaboration_dashboard(
    workspace_root: str | None = None,
    user_id: str | None = None,
    role: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.collaboration_dashboard(root, user_id=user_id, role=role, limit=limit)
    fallback = {
        "workspace": str(root),
        "viewer": {"user_id": user_id or "local-owner", "role": role or "owner"},
        "roles": [],
        "members": [],
        "shared_workflows": [],
        "active_workflows": [],
        "approval_queue": [],
        "roadmap_board": {"lanes": {}, "milestones": {}, "blocked": []},
        "repositories": [],
        "runtime_visibility": {},
        "observability": {"workflow_count": 0, "pending_approval_count": 0, "repository_count": 0},
        "privacy_controls": {"local_first": True, "workspace_isolation": True},
        "audit_events": [],
    }
    return _autopilot_gateway_response(result, fallback=fallback)


async def api_register_collaboration_member(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.register_collaboration_member(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration member registry is unavailable.")
    return _autopilot_gateway_response(result)


async def api_register_collaboration_repository(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.register_collaboration_repository(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration repository registry is unavailable.")
    return _autopilot_gateway_response(result)


async def api_create_collaboration_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.create_collaboration_workflow(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration runtime is unavailable.")
    return _autopilot_gateway_response(result)


async def api_collaboration_workflow_action(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.collaboration_workflow_action(
        root,
        workflow_id,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration workflow action is unavailable.")
    return _autopilot_gateway_response(result)


async def api_create_collaboration_approval(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.create_collaboration_approval(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration approval creation is unavailable.")
    return _autopilot_gateway_response(result)


async def api_decide_collaboration_approval(approval_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.decide_collaboration_approval(
        root,
        approval_id,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaboration approval is unavailable.")
    return _autopilot_gateway_response(result)


async def api_assign_collaboration_roadmap_item(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.assign_collaboration_roadmap_item(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core collaborative roadmap is unavailable.")
    return _autopilot_gateway_response(result)


register_collaboration_routes(
    app,
    api_collaboration_dashboard=lambda workspace_root, user_id, role, limit: api_collaboration_dashboard(
        workspace_root,
        user_id,
        role,
        limit,
    ),
    api_register_collaboration_member=lambda payload: api_register_collaboration_member(payload),
    api_register_collaboration_repository=lambda payload: api_register_collaboration_repository(payload),
    api_create_collaboration_workflow=lambda payload: api_create_collaboration_workflow(payload),
    api_collaboration_workflow_action=lambda workflow_id, payload: api_collaboration_workflow_action(workflow_id, payload),
    api_create_collaboration_approval=lambda payload: api_create_collaboration_approval(payload),
    api_decide_collaboration_approval=lambda approval_id, payload: api_decide_collaboration_approval(approval_id, payload),
    api_assign_collaboration_roadmap_item=lambda payload: api_assign_collaboration_roadmap_item(payload),
)


async def api_governance_dashboard(
    workspace_root: str | None = None,
    include_audit: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.governance_dashboard(root, include_audit=include_audit, limit=limit)
    fallback = {
        "workspace": str(root),
        "policies": [],
        "policy_violations": [],
        "runtime_trust_levels": [],
        "plugin_governance": {"status": "core_offline", "high_risk_plugins": []},
        "runtime_node_governance": {"status": "core_offline", "restricted_nodes": []},
        "deployment_governance": {"status": "core_offline", "production_workflows": []},
        "approval_governance": {"status": "core_offline", "approval_queue": []},
        "compliance": {"audit_ready": False, "local_first": True},
        "ui_summary": {"status": "core_offline", "policy_violations": 0},
        "audit_events": [],
    }
    return _autopilot_gateway_response(result, fallback=fallback)


async def api_governance_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.evaluate_governance_policy(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core governance runtime is unavailable.")
    return _autopilot_gateway_response(result)


async def api_governance_compliance_export(payload: dict[str, Any]) -> dict[str, Any]:
    workspace_value = str(payload.get("workspace_root") or payload.get("workspace") or "").strip() or None
    root = _resolve_workspace_or_400(workspace_value)
    result = await core_runtime_client.export_governance_compliance(
        root,
        {key: value for key, value in payload.items() if key not in {"workspace", "workspace_root"}},
    )
    if not result.delegated:
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core compliance export is unavailable.")
    return _autopilot_gateway_response(result)


register_governance_routes(
    app,
    api_governance_dashboard=lambda workspace_root, include_audit, limit: api_governance_dashboard(
        workspace_root,
        include_audit,
        limit,
    ),
    api_governance_evaluate=lambda payload: api_governance_evaluate(payload),
    api_governance_compliance_export=lambda payload: api_governance_compliance_export(payload),
)


async def chat(request: AgentRequest) -> AgentResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    response: AgentResponse | None = None
    try:
        response = await agent.run(request.model_copy(update={"workspace_root": str(root)}))
        return response
    finally:
        _invalidate_workspace_caches(root)
        if response is not None and response.workspace_root:
            _invalidate_workspace_caches(Path(response.workspace_root))


async def chat_stream_contract() -> ChatStreamContractResponse:
    return chat_stream_contract_response()


async def chat_stream(request: AgentRequest) -> StreamingResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    stream_request = request.model_copy(update={"workspace_root": str(root)})
    return StreamingResponse(
        _chat_stream_events(stream_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


register_chat_routes(
    app,
    chat=lambda request: chat(request),
    chat_stream_contract=lambda: chat_stream_contract(),
    chat_stream=lambda request: chat_stream(request),
)


async def preview_route(request: RoutePreviewRequest) -> RoutePreviewResponse:
    try:
        preview = await agent.preview_route(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = _resolve_workspace_or_400(preview.workspace_root)
    core_result = await core_runtime_client.route_model(
        root,
        **_core_route_request_kwargs(request, preview),
    )
    if core_result.delegated and isinstance(core_result.data, dict):
        return _route_preview_from_core(preview, core_result.data)
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "model.route")
    _record_core_fallback("model.route", core_result)
    return preview


async def apply_changes(request: ApplyRequest) -> ApplyResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    if request.changes:
        core_result = await core_runtime_client.apply_changes(root, request.changes)
        if core_result.delegated:
            _invalidate_workspace_caches(root)
            return _apply_response_from_core(
                root,
                core_result,
                workspace_files=workspace_manager.scan(root, max_files=120),
            )
        if not core_result.should_fallback:
            raise _core_delegation_error(core_result, "changes.apply")
        _record_core_fallback("changes.apply", core_result)
    else:
        core_runtime_client.record_local_only("changes.apply", "No changes were provided.")

    result = workspace_manager.apply_changes(root, request.changes)
    _invalidate_workspace_caches(root)
    return ApplyResponse(
        applied=result.applied,
        warnings=result.warnings,
        checkpoint=result.checkpoint,
        workspace_root=str(root),
        workspace_files=workspace_manager.scan(root, max_files=120),
    )


register_routing_apply_routes(
    app,
    preview_route=lambda request: preview_route(request),
    apply_changes=lambda request: apply_changes(request),
)


register_project_builder_routes(
    app,
    project_builder_presets=lambda: _project_builder_service().presets(),
    plan_project_scaffold=lambda request: _project_builder_service().plan(request),
    preview_project_scaffold=lambda request: _project_builder_service().preview(request),
    scaffold_project=lambda request: _project_builder_service().scaffold(request),
)


async def list_checkpoints(
    workspace_root: str | None = None,
    limit: int = 50,
) -> CheckpointListResponse:
    root = _resolve_workspace_or_400(workspace_root)
    core_result = await core_runtime_client.list_checkpoints(root, limit=limit)
    if core_result.delegated:
        return _checkpoint_list_response_from_core(root, core_result)
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "checkpoints.list")
    _record_core_fallback("checkpoints.list", core_result)
    return CheckpointListResponse(
        workspace_root=str(root),
        checkpoints=workspace_manager.list_checkpoints(root, limit=limit),
    )


async def create_checkpoint(request: CheckpointCreateRequest) -> CheckpointSummary:
    root = _resolve_workspace_or_400(request.workspace_root)
    core_result = await core_runtime_client.create_checkpoint(
        root,
        paths=request.paths,
        summary=request.summary or "Website checkpoint",
    )
    if core_result.delegated:
        data = _core_delegation_data(core_result, "checkpoints.create")
        return checkpoint_summary_from_core(data)
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "checkpoints.create")
    _record_core_fallback("checkpoints.create", core_result)
    try:
        return workspace_manager.create_checkpoint(
            root,
            paths=request.paths,
            summary=request.summary or "Website checkpoint",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"checkpoint could not be created: {exc}") from exc


async def restore_checkpoint(request: RestoreCheckpointRequest) -> RestoreCheckpointResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    core_result = await core_runtime_client.restore_checkpoint(root, request.checkpoint)
    if core_result.delegated:
        _invalidate_workspace_caches(root)
        return _restore_response_from_core(
            root,
            core_result,
            workspace_files=workspace_manager.scan(root, max_files=120),
        )
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "checkpoints.restore")
    _record_core_fallback("checkpoints.restore", core_result)
    try:
        restored = workspace_manager.restore_checkpoint(root, request.checkpoint)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="checkpoint not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RestoreCheckpointResponse(
        restored=restored,
        warnings=[],
        workspace_root=str(root),
        workspace_files=workspace_manager.scan(root, max_files=120),
    )


register_checkpoint_routes(
    app,
    list_checkpoints=lambda workspace_root, limit: list_checkpoints(workspace_root, limit),
    create_checkpoint=lambda request: create_checkpoint(request),
    restore_checkpoint=lambda request: restore_checkpoint(request),
)


async def validate_workspace(request: ValidateRequest) -> ValidateResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    profile_snapshot = agent.validation.profile_snapshot(root)
    core_result = await core_runtime_client.run_validation(
        root,
        command=profile_snapshot.profile.command if profile_snapshot.profile else None,
        timeout_seconds=settings.aegis_command_timeout_seconds,
    )
    if core_result.delegated:
        try:
            return await _validate_response_from_core(
                root,
                core_result,
                validation_profile=profile_snapshot.profile,
                create_repair_workflow=core_runtime_client.create_repair_workflow,
                record_fallback=_record_core_fallback,
            )
        finally:
            _invalidate_workspace_caches(root)
    if not core_result.should_fallback:
        raise _core_delegation_error(core_result, "validation.run")
    _record_core_fallback("validation.run", core_result)
    try:
        return await agent.validate_workspace(str(root))
    finally:
        _invalidate_workspace_caches(root)


async def verify_workspace(request: VerificationRequest) -> VerificationResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    try:
        return await agent.verify_workspace(request.model_copy(update={"workspace_root": str(root)}))
    finally:
        _invalidate_workspace_caches(root)


async def validation_profile(workspace_root: str | None = None) -> ValidationProfileResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.validation.profile_snapshot(root)


async def update_validation_profile(
    request: ValidationProfileUpdateRequest,
    workspace_root: str | None = None,
) -> ValidationProfileResponse:
    root = _resolve_workspace_or_400(workspace_root)

    command = request.command.strip()
    try:
        if command:
            agent.validation.save_profile(
                root,
                command=command,
                label=request.label.strip() or command,
                source="manual",
                notes=request.notes.strip(),
            )
        else:
            agent.validation.clear_profile(root)
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not update {agent.validation.PROFILE_PATH}: {exc}",
        ) from exc

    return agent.validation.profile_snapshot(root)


register_validation_routes(
    app,
    validate_workspace=lambda request: validate_workspace(request),
    verify_workspace=lambda request: verify_workspace(request),
    validation_profile=lambda workspace_root: validation_profile(workspace_root),
    update_validation_profile=lambda request, workspace_root: update_validation_profile(request, workspace_root),
)


async def history(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=25),
) -> HistoryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return HistoryResponse(
        workspace_root=str(root),
        recent_tasks=agent.store.recent_tasks(project_root=root, limit=limit),
        fix_memory=agent.store.fix_history(project_root=root, limit=limit),
        project_memory=agent.store.project_memory(project_root=root, limit=limit),
    )


async def list_tasks(
    workspace_root: str | None = Query(default=None),
    status: str | None = Query(default=None),
    include_subtasks: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> TaskListResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return TaskListResponse(
        workspace_root=str(root),
        tasks=agent.store.list_tasks(
            project_root=root,
            limit=limit,
            status=status,
            include_subtasks=include_subtasks,
        ),
    )


async def create_task(request: TaskCreateRequest) -> TaskDetailResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    task_id = agent.store.create_task(
        mode=str(request.mode),
        workspace_root=root,
        message=request.user_goal or request.title,
        project_id=request.project_id,
        parent_task_id=request.parent_task_id,
        title=request.title,
        user_goal=request.user_goal or request.title,
        priority=request.priority,
        assigned_agent_role=request.assigned_agent_role,
        related_files=request.related_files,
        validation_commands=request.validation_commands,
    )
    agent.store.record_event(
        task_id,
        kind="task",
        title="Task created",
        detail="Task was created through the task graph API.",
    )
    return TaskDetailResponse(task=agent.store.task(task_id), subtasks=agent.store.subtasks(task_id))


async def read_task(task_id: str) -> TaskDetailResponse:
    try:
        return TaskDetailResponse(task=agent.store.task(task_id), subtasks=agent.store.subtasks(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


async def cancel_task(task_id: str, request: TaskActionRequest | None = None) -> TaskActionResponse:
    try:
        event = agent.store.cancel_task(task_id, reason=(request.reason if request else ""))
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def approve_task_action(task_id: str, request: TaskActionRequest) -> TaskActionResponse:
    try:
        event = agent.store.approve_task_action(task_id, reason=request.reason, approved=request.approved)
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


async def retry_task(task_id: str, request: TaskActionRequest | None = None) -> TaskActionResponse:
    try:
        event = agent.store.retry_task(task_id, reason=(request.reason if request else ""))
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def task_timeline(task_id: str) -> TaskTimelineResponse:
    try:
        agent.store.task(task_id)
        return TaskTimelineResponse(task_id=task_id, events=agent.store.task_events(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


async def task_artifacts(task_id: str) -> TaskArtifactsResponse:
    try:
        return agent.store.task_artifacts(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


register_history_task_routes(
    app,
    history=lambda workspace_root, limit: history(workspace_root, limit),
    list_tasks=lambda workspace_root, status, include_subtasks, limit: list_tasks(
        workspace_root,
        status,
        include_subtasks,
        limit,
    ),
    create_task=lambda request: create_task(request),
    read_task=lambda task_id: read_task(task_id),
    cancel_task=lambda task_id, request=None: cancel_task(task_id, request),
    approve_task_action=lambda task_id, request: approve_task_action(task_id, request),
    retry_task=lambda task_id, request=None: retry_task(task_id, request),
    task_timeline=lambda task_id: task_timeline(task_id),
    task_artifacts=lambda task_id: task_artifacts(task_id),
)


async def distributed_runtime_snapshot(workspace_root: str | None = Query(default=None)) -> DistributedRuntimeSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    core_result = await core_runtime_client.distributed_runtime(root, include_audit=True, limit=120)
    core_snapshot = _runtime_snapshot_from_core(root, core_result)
    if core_snapshot is not None:
        return core_snapshot
    core_runtime_client.record_fallback("distributed.runtime", core_result.error or "Core distributed runtime unavailable.")
    return _runtime_snapshot(root)


async def distributed_runtime_observability(workspace_root: str | None = Query(default=None)) -> RuntimeObservabilitySnapshot:
    return (await distributed_runtime_snapshot(workspace_root)).observability


def _runtime_interaction_unavailable(root: Path, result: CoreDelegationResult) -> dict[str, Any]:
    _record_core_fallback("runtime.interaction", result)
    return {
        "ok": False,
        "delegated": False,
        "core_connected": result.reachable,
        "workspace_root": str(root),
        "terminals": [],
        "jobs": [],
        "active_jobs": [],
        "recent_events": [],
        "processes": [],
        "sessions": [],
        "voice": {},
        "observability": {},
        "safety_controls": {},
        "fallback_mode_active": True,
        "error": result.error or "Aegis Core runtime interaction is unavailable.",
        "stream_url": "",
    }


def _runtime_interaction_payload(root: Path, result: CoreDelegationResult) -> dict[str, Any]:
    data = _core_delegation_data(result, result.kind or "runtime.interaction")
    return {
        "ok": True,
        "delegated": True,
        "core_connected": True,
        "workspace_root": str(root),
        "terminals": data.get("terminals", []),
        "jobs": data.get("jobs", []),
        "active_jobs": data.get("active_jobs", []),
        "recent_events": data.get("recent_events", []),
        "processes": data.get("processes", []),
        "sessions": data.get("sessions", []),
        "voice": data.get("voice", {}),
        "observability": data.get("observability", {}),
        "safety_controls": data.get("safety_controls", {}),
        "fallback_mode_active": False,
        "error": "",
        "stream_url": f"/api/runtime-interaction/events?{urlencode({'workspace_root': str(root)})}",
    }


async def runtime_interaction_status(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_interaction(root, limit=limit)
    if result.delegated:
        return _runtime_interaction_payload(root, result)
    if not result.should_fallback:
        raise _core_delegation_error(result, "runtime.interaction")
    return _runtime_interaction_unavailable(root, result)


async def runtime_interaction_jobs(
    workspace_root: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_jobs(root, status=status, limit=limit)
    if result.delegated:
        return {"workspace_root": str(root), "delegated": True, **_core_delegation_data(result, "runtime.jobs")}
    if not result.should_fallback:
        raise _core_delegation_error(result, "runtime.jobs")
    _record_core_fallback("runtime.jobs", result)
    return {"workspace_root": str(root), "delegated": False, "jobs": [], "observability": {}, "error": result.error}


async def launch_runtime_interaction_job(request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.launch_runtime_job(
        root,
        command=request.get("command") or [],
        cwd=request.get("cwd"),
        workflow_id=request.get("workflow_id"),
        task_id=request.get("task_id"),
        terminal_id=request.get("terminal_id"),
        title=str(request.get("title") or ""),
        timeout_seconds=int(request.get("timeout_seconds") or 120),
        approval=bool(request.get("approval", False)),
        dry_run=bool(request.get("dry_run", False)),
        wait=bool(request.get("wait", True)),
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.job.mutation")}
    if result.should_fallback:
        _record_core_fallback("runtime.job.mutation", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core terminal orchestration is unavailable.")
    raise _core_delegation_error(result, "runtime.job.mutation")


async def runtime_interaction_job(job_id: str, workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_job(root, job_id)
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.job")}
    if result.should_fallback:
        _record_core_fallback("runtime.job", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core runtime job lookup is unavailable.")
    raise _core_delegation_error(result, "runtime.job")


async def cancel_runtime_interaction_job(job_id: str, request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.cancel_runtime_job(root, job_id, reason=str(request.get("reason") or "Website cancel request"))
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.job.mutation")}
    if result.should_fallback:
        _record_core_fallback("runtime.job.mutation", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core runtime cancellation is unavailable.")
    raise _core_delegation_error(result, "runtime.job.mutation")


async def retry_runtime_interaction_job(job_id: str, request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.retry_runtime_job(
        root,
        job_id,
        approval=request.get("approval") if request.get("approval") is not None else None,
        wait=bool(request.get("wait", True)),
        timeout_seconds=int(request["timeout_seconds"]) if request.get("timeout_seconds") is not None else None,
        reason=str(request.get("reason") or "Website retry request"),
    )
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.job.mutation")}
    if result.should_fallback:
        _record_core_fallback("runtime.job.mutation", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core runtime retry is unavailable.")
    raise _core_delegation_error(result, "runtime.job.mutation")


async def runtime_interaction_streams(
    workspace_root: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_streams(root, job_id=job_id, workflow_id=workflow_id, since=since, limit=limit)
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.streams")}
    if result.should_fallback:
        _record_core_fallback("runtime.streams", result)
        return {"workspace": str(root), "delegated": False, "events": [], "next_since": since, "error": result.error}
    raise _core_delegation_error(result, "runtime.streams")


async def runtime_interaction_events(
    workspace_root: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    follow: bool = Query(default=True),
    max_seconds: int = Query(default=30, ge=1, le=120),
) -> StreamingResponse:
    root = _resolve_workspace_or_400(workspace_root)
    url = f"{core_runtime_client.base_url}/v1/runtime/streams"
    params = {
        "workspace": str(root),
        "job_id": job_id,
        "workflow_id": workflow_id,
        "since": since,
        "limit": limit,
        "follow": follow,
        "max_seconds": max_seconds,
        "as_sse": True,
    }

    async def stream_core_events() -> AsyncIterator[str]:
        if not core_runtime_client.delegated_workflows_enabled:
            yield _sse_event("runtime_error", {"type": "runtime_error", "message": "Aegis Core delegated workflows are disabled."})
            return
        try:
            timeout = httpx.Timeout(connect=core_runtime_client.timeout_seconds, read=None, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", url, params=params) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
        except Exception as exc:
            yield _sse_event("runtime_error", {"type": "runtime_error", "message": f"Aegis Core runtime event stream unavailable: {exc}"})

    return StreamingResponse(stream_core_events(), media_type="text/event-stream")


async def runtime_interaction_sessions(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_sessions(root)
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.sessions")}
    if result.should_fallback:
        _record_core_fallback("runtime.sessions", result)
        return {"workspace": str(root), "delegated": False, "sessions": [], "active_sessions": [], "recent_events": [], "error": result.error}
    raise _core_delegation_error(result, "runtime.sessions")


async def create_runtime_interaction_session(request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.create_runtime_session(
        root,
        workflow_id=str(request.get("workflow_id") or ""),
        title=str(request.get("title") or ""),
        owner_client_id=str(request.get("owner_client_id") or "website-backend"),
        participants=request.get("participants") if isinstance(request.get("participants"), list) else [],
        spectators=request.get("spectators") if isinstance(request.get("spectators"), list) else [],
        approval_delegates=request.get("approval_delegates") if isinstance(request.get("approval_delegates"), list) else [],
        metadata=request.get("metadata") if isinstance(request.get("metadata"), dict) else {},
    )
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.session.mutation")}
    if result.should_fallback:
        _record_core_fallback("runtime.session.mutation", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core runtime sessions are unavailable.")
    raise _core_delegation_error(result, "runtime.session.mutation")


async def sync_runtime_interaction_session(session_id: str, request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.sync_runtime_session(
        root,
        session_id,
        participants=request.get("participants") if isinstance(request.get("participants"), list) else None,
        spectators=request.get("spectators") if isinstance(request.get("spectators"), list) else None,
        approval_delegates=request.get("approval_delegates") if isinstance(request.get("approval_delegates"), list) else None,
        status=request.get("status"),
        message=str(request.get("message") or ""),
    )
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.session.mutation")}
    if result.should_fallback:
        _record_core_fallback("runtime.session.mutation", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core runtime session sync is unavailable.")
    raise _core_delegation_error(result, "runtime.session.mutation")


async def runtime_interaction_voice(workspace_root: str | None = Query(default=None)) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_voice(root)
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.voice")}
    if result.should_fallback:
        _record_core_fallback("runtime.voice", result)
        return {"workspace": str(root), "delegated": False, "status": "core_unavailable", "warnings": [result.error]}
    raise _core_delegation_error(result, "runtime.voice")


async def runtime_interaction_voice_command(request: dict) -> dict[str, Any]:
    root = _resolve_workspace_or_400(request.get("workspace_root") or request.get("workspace"))
    result = await core_runtime_client.route_voice_command(
        root,
        transcript=str(request.get("transcript") or ""),
        workflow_id=str(request.get("workflow_id") or ""),
        client_id=str(request.get("client_id") or "website-backend"),
        dry_run=bool(request.get("dry_run", True)),
    )
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.voice.command")}
    if result.should_fallback:
        _record_core_fallback("runtime.voice.command", result)
        raise HTTPException(status_code=503, detail=result.error or "Aegis Core voice routing is unavailable.")
    raise _core_delegation_error(result, "runtime.voice.command")


async def runtime_interaction_replay(
    workspace_root: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    root = _resolve_workspace_or_400(workspace_root)
    result = await core_runtime_client.runtime_replay(root, workflow_id=workflow_id, job_id=job_id, limit=limit)
    if result.delegated:
        return {"delegated": True, **_core_delegation_data(result, "runtime.replay")}
    if result.should_fallback:
        _record_core_fallback("runtime.replay", result)
        return {"workspace": str(root), "delegated": False, "timeline": [], "terminal_output": [], "repair_chain": [], "approval_history": [], "sessions": [], "error": result.error}
    raise _core_delegation_error(result, "runtime.replay")


async def list_runtime_workers(workspace_root: str | None = Query(default=None)) -> list[WorkerRuntimeInfo]:
    return await _distributed_runtime_service().list_runtime_workers(workspace_root)


async def register_runtime_worker(request: WorkerRegistrationRequest) -> WorkerRuntimeInfo:
    return await _distributed_runtime_service().register_runtime_worker(request)


async def heartbeat_runtime_worker(worker_id: str, request: WorkerHeartbeatRequest) -> WorkerRuntimeInfo:
    return await _distributed_runtime_service().heartbeat_runtime_worker(worker_id, request)


async def revoke_runtime_worker(worker_id: str, request: WorkerActionRequest | None = None) -> WorkerRuntimeInfo:
    return await _distributed_runtime_service().revoke_runtime_worker(worker_id, request)


async def list_execution_queue(
    workspace_root: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ExecutionQueueItem]:
    return await _distributed_runtime_service().list_execution_queue(workspace_root, status=status, limit=limit)


async def create_execution_queue_item(request: ExecutionQueueCreateRequest) -> ExecutionQueueItem:
    return await _distributed_runtime_service().create_execution_queue_item(request)


async def read_execution_queue_item(job_id: str) -> ExecutionQueueItem:
    return await _distributed_runtime_service().read_execution_queue_item(job_id)


async def cancel_execution_queue_item(job_id: str, request: ExecutionQueueActionRequest | None = None) -> ExecutionQueueItem:
    return await _distributed_runtime_service().cancel_execution_queue_item(job_id, request)


async def retry_execution_queue_item(job_id: str, request: ExecutionQueueActionRequest | None = None) -> ExecutionQueueItem:
    return await _distributed_runtime_service().retry_execution_queue_item(job_id, request)


async def dispatch_execution_queue(request: ExecutionDispatchRequest) -> ExecutionDispatchResponse:
    return await _distributed_runtime_service().dispatch_execution_queue(request)


async def route_distributed_model(request: HybridRouteRequest) -> HybridRouteDecision:
    return await _distributed_runtime_service().route_distributed_model(request)


async def distributed_runtime_audit(
    worker_id: str = Query(default=""),
    job_id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[WorkerAuditEvent]:
    return await _distributed_runtime_service().distributed_runtime_audit(worker_id=worker_id, job_id=job_id, limit=limit)


async def list_remote_sync_manifests(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RemoteWorkspaceSyncManifest]:
    return await _distributed_runtime_service().list_remote_sync_manifests(workspace_root, limit=limit)


async def create_remote_sync_manifest(request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
    return await _distributed_runtime_service().create_remote_sync_manifest(request)


register_distributed_runtime_routes(
    app,
    distributed_runtime_snapshot=lambda workspace_root: distributed_runtime_snapshot(workspace_root),
    distributed_runtime_observability=lambda workspace_root: distributed_runtime_observability(workspace_root),
    runtime_interaction_status=lambda workspace_root, limit: runtime_interaction_status(workspace_root, limit),
    runtime_interaction_jobs=lambda workspace_root, status, limit: runtime_interaction_jobs(workspace_root, status, limit),
    launch_runtime_interaction_job=lambda request: launch_runtime_interaction_job(request),
    runtime_interaction_job=lambda job_id, workspace_root: runtime_interaction_job(job_id, workspace_root),
    cancel_runtime_interaction_job=lambda job_id, request: cancel_runtime_interaction_job(job_id, request),
    retry_runtime_interaction_job=lambda job_id, request: retry_runtime_interaction_job(job_id, request),
    runtime_interaction_streams=lambda workspace_root, job_id, workflow_id, since, limit: runtime_interaction_streams(
        workspace_root,
        job_id,
        workflow_id,
        since,
        limit,
    ),
    runtime_interaction_events=lambda workspace_root, job_id, workflow_id, since, limit, follow, max_seconds: runtime_interaction_events(
        workspace_root,
        job_id,
        workflow_id,
        since,
        limit,
        follow,
        max_seconds,
    ),
    runtime_interaction_sessions=lambda workspace_root: runtime_interaction_sessions(workspace_root),
    create_runtime_interaction_session=lambda request: create_runtime_interaction_session(request),
    sync_runtime_interaction_session=lambda session_id, request: sync_runtime_interaction_session(session_id, request),
    runtime_interaction_voice=lambda workspace_root: runtime_interaction_voice(workspace_root),
    runtime_interaction_voice_command=lambda request: runtime_interaction_voice_command(request),
    runtime_interaction_replay=lambda workspace_root, workflow_id, job_id, limit: runtime_interaction_replay(
        workspace_root,
        workflow_id,
        job_id,
        limit,
    ),
    list_runtime_workers=lambda workspace_root: list_runtime_workers(workspace_root),
    register_runtime_worker=lambda request: register_runtime_worker(request),
    heartbeat_runtime_worker=lambda worker_id, request: heartbeat_runtime_worker(worker_id, request),
    revoke_runtime_worker=lambda worker_id, request=None: revoke_runtime_worker(worker_id, request),
    list_execution_queue=lambda workspace_root, status, limit: list_execution_queue(workspace_root, status, limit),
    create_execution_queue_item=lambda request: create_execution_queue_item(request),
    read_execution_queue_item=lambda job_id: read_execution_queue_item(job_id),
    cancel_execution_queue_item=lambda job_id, request=None: cancel_execution_queue_item(job_id, request),
    retry_execution_queue_item=lambda job_id, request=None: retry_execution_queue_item(job_id, request),
    dispatch_execution_queue=lambda request: dispatch_execution_queue(request),
    route_distributed_model=lambda request: route_distributed_model(request),
    distributed_runtime_audit=lambda worker_id, job_id, limit: distributed_runtime_audit(worker_id, job_id, limit),
    list_remote_sync_manifests=lambda workspace_root, limit: list_remote_sync_manifests(workspace_root, limit),
    create_remote_sync_manifest=lambda request: create_remote_sync_manifest(request),
)


async def telemetry(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> TelemetryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return TelemetryResponse(
        workspace_root=str(root),
        context_budgets=agent.store.recent_context_budgets(project_root=root, limit=limit),
        model_attempts=agent.store.recent_model_attempts(project_root=root, limit=min(limit * 4, 200)),
        feedback_events=agent.store.recent_feedback(project_root=root, limit=min(limit * 4, 200)),
    )


async def route_quality(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> RouteQualityResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.route_quality(project_root=root, limit=limit)


async def route_health(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelRouteHealthInfo]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.route_health_signals(project_root=root, limit=limit)


async def fallback_inspector(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> FallbackInspectorResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.fallback_inspector(
        project_root=root,
        limit=limit,
        adapter_health=_workspace_adapter_health(root),
    )


async def feedback_telemetry(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeedbackTelemetryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.feedback_telemetry(project_root=root, limit=limit)


async def telemetry_snapshot(
    workspace_root: str | None = Query(default=None),
    route_quality_limit: int = Query(default=200, ge=1, le=500),
    fallback_limit: int = Query(default=20, ge=1, le=100),
    feedback_limit: int = Query(default=100, ge=1, le=500),
    stale_after_seconds: int = Query(default=900, ge=60, le=86400),
    refresh: bool = Query(default=False),
    prune: bool = Query(default=False),
    max_snapshots: int = Query(default=12, ge=1, le=250),
    retention_days: int = Query(default=30, ge=1, le=3650),
) -> TelemetrySnapshotResponse:
    root = _resolve_workspace_or_400(workspace_root)
    if refresh:
        snapshot = agent.store.refresh_telemetry_snapshot(
            project_root=root,
            route_quality_limit=route_quality_limit,
            fallback_limit=fallback_limit,
            feedback_limit=feedback_limit,
            stale_after_seconds=stale_after_seconds,
        )
        prune_info = (
            agent.store.prune_telemetry_snapshots(
                project_root=root,
                max_snapshots=max_snapshots,
                retention_days=retention_days,
            )
            if prune
            else TelemetrySnapshotPruneInfo()
        )
        snapshot = _enrich_snapshot_with_adapter_health(root, snapshot)
        recommendations = _telemetry_snapshot_recommendations(snapshot)
        recommendations.extend(_telemetry_snapshot_prune_recommendations(prune_info))
        return TelemetrySnapshotResponse(
            workspace_root=str(root),
            cache_status="refreshed",
            snapshot=snapshot,
            prune=prune_info,
            recommendations=recommendations,
        )

    snapshot = agent.store.telemetry_snapshot(
        project_root=root,
        route_quality_limit=route_quality_limit,
        fallback_limit=fallback_limit,
        feedback_limit=feedback_limit,
        stale_after_seconds=stale_after_seconds,
    )
    prune_info = (
        agent.store.prune_telemetry_snapshots(
            project_root=root,
            max_snapshots=max_snapshots,
            retention_days=retention_days,
        )
        if prune
        else TelemetrySnapshotPruneInfo()
    )
    snapshot = _enrich_snapshot_with_adapter_health(root, snapshot)
    recommendations = _telemetry_snapshot_recommendations(snapshot)
    recommendations.extend(_telemetry_snapshot_prune_recommendations(prune_info))
    return TelemetrySnapshotResponse(
        workspace_root=str(root),
        cache_status="hit" if snapshot else "miss",
        snapshot=snapshot,
        prune=prune_info,
        recommendations=recommendations,
    )


async def refresh_telemetry_snapshot(
    workspace_root: str | None = Query(default=None),
    route_quality_limit: int = Query(default=200, ge=1, le=500),
    fallback_limit: int = Query(default=20, ge=1, le=100),
    feedback_limit: int = Query(default=100, ge=1, le=500),
    stale_after_seconds: int = Query(default=900, ge=60, le=86400),
    prune: bool = Query(default=True),
    max_snapshots: int = Query(default=12, ge=1, le=250),
    retention_days: int = Query(default=30, ge=1, le=3650),
) -> TelemetrySnapshotResponse:
    root = _resolve_workspace_or_400(workspace_root)
    snapshot = agent.store.refresh_telemetry_snapshot(
        project_root=root,
        route_quality_limit=route_quality_limit,
        fallback_limit=fallback_limit,
        feedback_limit=feedback_limit,
        stale_after_seconds=stale_after_seconds,
    )
    prune_info = (
        agent.store.prune_telemetry_snapshots(
            project_root=root,
            max_snapshots=max_snapshots,
            retention_days=retention_days,
        )
        if prune
        else TelemetrySnapshotPruneInfo()
    )
    snapshot = _enrich_snapshot_with_adapter_health(root, snapshot)
    recommendations = _telemetry_snapshot_recommendations(snapshot)
    recommendations.extend(_telemetry_snapshot_prune_recommendations(prune_info))
    return TelemetrySnapshotResponse(
        workspace_root=str(root),
        cache_status="refreshed",
        snapshot=snapshot,
        prune=prune_info,
        recommendations=recommendations,
    )


async def route_policy_diff(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    use_snapshot: bool = Query(default=True),
    stale_after_seconds: int = Query(default=900, ge=60, le=86400),
    min_attempts: int = Query(default=3, ge=1, le=50),
) -> RoutePolicyDiffResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.route_policy_diff(
        project_root=root,
        limit=limit,
        use_snapshot=use_snapshot,
        stale_after_seconds=stale_after_seconds,
        min_attempts=min_attempts,
    )


register_telemetry_routes(
    app,
    telemetry=lambda workspace_root, limit: telemetry(workspace_root, limit),
    route_quality=lambda workspace_root, limit: route_quality(workspace_root, limit),
    route_health=lambda workspace_root, limit: route_health(workspace_root, limit),
    fallback_inspector=lambda workspace_root, limit: fallback_inspector(workspace_root, limit),
    feedback_telemetry=lambda workspace_root, limit: feedback_telemetry(workspace_root, limit),
    telemetry_snapshot=lambda workspace_root, route_quality_limit, fallback_limit, feedback_limit, stale_after_seconds, refresh, prune, max_snapshots, retention_days: telemetry_snapshot(
        workspace_root,
        route_quality_limit,
        fallback_limit,
        feedback_limit,
        stale_after_seconds,
        refresh,
        prune,
        max_snapshots,
        retention_days,
    ),
    refresh_telemetry_snapshot=lambda workspace_root, route_quality_limit, fallback_limit, feedback_limit, stale_after_seconds, prune, max_snapshots, retention_days: refresh_telemetry_snapshot(
        workspace_root,
        route_quality_limit,
        fallback_limit,
        feedback_limit,
        stale_after_seconds,
        prune,
        max_snapshots,
        retention_days,
    ),
    route_policy_diff=lambda workspace_root, limit, use_snapshot, stale_after_seconds, min_attempts: route_policy_diff(
        workspace_root,
        limit,
        use_snapshot,
        stale_after_seconds,
        min_attempts,
    ),
)


async def get_adaptive_intelligence(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    refresh: bool = Query(default=False),
) -> AdaptiveIntelligenceSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return adaptive_intelligence.snapshot(
        agent.store,
        project_root=root,
        limit=limit,
        refresh_outcomes=refresh,
    )


async def refresh_adaptive_intelligence(
    request: AdaptiveIntelligenceRefreshRequest,
) -> AdaptiveIntelligenceSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return adaptive_intelligence.snapshot(
        agent.store,
        project_root=root,
        limit=request.limit,
        refresh_outcomes=request.refresh_outcomes,
    )


async def adaptive_task_outcomes(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    refresh: bool = Query(default=False),
) -> list[TaskOutcomeRecord]:
    root = _resolve_workspace_or_400(workspace_root)
    if refresh:
        return adaptive_intelligence.refresh_outcomes(agent.store, project_root=root, limit=limit)
    return agent.store.adaptive_task_outcomes(project_root=root, limit=limit)


async def adaptive_policy_profiles() -> list[IntelligencePolicyProfile]:
    return adaptive_intelligence.ensure_profiles(agent.store)


async def upsert_adaptive_policy_profile(
    request: AdaptivePolicyProfileUpdateRequest,
) -> IntelligencePolicyProfile:
    return adaptive_intelligence.upsert_profile(agent.store, request)


async def activate_adaptive_policy_profile(
    profile_id: str,
    request: TaskActionRequest | None = None,
    workspace_root: str | None = Query(default=None),
) -> AdaptiveIntelligenceSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    reason = request.reason if request else ""
    adaptive_intelligence.activate_profile(agent.store, profile_id=profile_id, reason=reason)
    return adaptive_intelligence.snapshot(agent.store, project_root=root, refresh_outcomes=False)


async def rollback_adaptive_policy_profile(
    request: AdaptivePolicyRollbackRequest,
) -> AdaptiveIntelligenceSnapshot:
    root = _resolve_workspace_or_400(None)
    adaptive_intelligence.rollback_policy(
        agent.store,
        checkpoint_id=request.checkpoint_id,
        reason=request.reason,
    )
    return adaptive_intelligence.snapshot(agent.store, project_root=root, refresh_outcomes=False)


async def run_adaptive_benchmarks(
    request: AdaptiveBenchmarkRunRequest,
) -> list[AdaptiveBenchmarkReport]:
    root = _resolve_workspace_or_400(request.workspace_root)
    return adaptive_intelligence.run_benchmarks(
        agent.store,
        project_root=root,
        suite_ids=request.suite_ids,
        baseline_score=request.baseline_score,
    )


async def list_adaptive_benchmarks(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AdaptiveBenchmarkReport]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.adaptive_benchmark_reports(project_root=root, limit=limit)


async def replay_adaptive_tasks(
    request: AdaptiveReplayRequest,
) -> list[EvaluationReplayResult]:
    root = _resolve_workspace_or_400(request.workspace_root)
    return adaptive_intelligence.replay(agent.store, project_root=root, request=request)


async def list_adaptive_replay_results(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EvaluationReplayResult]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.adaptive_replay_results(project_root=root, limit=limit)


register_adaptive_intelligence_routes(
    app,
    get_adaptive_intelligence=lambda workspace_root, limit, refresh: get_adaptive_intelligence(
        workspace_root,
        limit,
        refresh,
    ),
    refresh_adaptive_intelligence=lambda request: refresh_adaptive_intelligence(request),
    adaptive_task_outcomes=lambda workspace_root, limit, refresh: adaptive_task_outcomes(
        workspace_root,
        limit,
        refresh,
    ),
    adaptive_policy_profiles=lambda: adaptive_policy_profiles(),
    upsert_adaptive_policy_profile=lambda request: upsert_adaptive_policy_profile(request),
    activate_adaptive_policy_profile=lambda profile_id, request=None, workspace_root=None: activate_adaptive_policy_profile(
        profile_id,
        request,
        workspace_root,
    ),
    rollback_adaptive_policy_profile=lambda request: rollback_adaptive_policy_profile(request),
    run_adaptive_benchmarks=lambda request: run_adaptive_benchmarks(request),
    list_adaptive_benchmarks=lambda workspace_root, limit: list_adaptive_benchmarks(workspace_root, limit),
    replay_adaptive_tasks=lambda request: replay_adaptive_tasks(request),
    list_adaptive_replay_results=lambda workspace_root, limit: list_adaptive_replay_results(workspace_root, limit),
)


async def productization_snapshot(
    workspace_root: str | None = Query(default=None),
    refresh_metrics: bool = Query(default=False),
) -> ProductizationSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=refresh_metrics)


async def refresh_productization_snapshot(request: ProductizationRefreshRequest) -> ProductizationSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _productization_snapshot(root, refresh_metrics=request.refresh_metrics)


async def productization_stable_apis() -> list[StableApiContract]:
    return productization.stable_api_contracts()


async def productization_recovery(workspace_root: str | None = Query(default=None)) -> RuntimeRecoverySnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=False).recovery


async def productization_reliability(workspace_root: str | None = Query(default=None)) -> list[ReliabilityMetric]:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=False).metrics


async def list_productization_plugins(include_disabled: bool = Query(default=True)) -> list[PluginManifest]:
    return agent.store.plugin_manifests(include_disabled=include_disabled)


async def validate_productization_plugin(request: PluginValidationRequest) -> PluginValidationResult:
    return productization.validate_plugin(
        request,
        policy=productization.ensure_enterprise_policy(agent.store),
    )


async def register_productization_plugin(request: PluginRegistrationRequest) -> PluginManifest:
    candidate = request.manifest.model_copy(update={"enabled": request.enable, "trusted": request.trust})
    validation = productization.validate_plugin(
        candidate,
        policy=productization.ensure_enterprise_policy(agent.store),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "plugin manifest is invalid")
    saved = agent.store.upsert_plugin_manifest(validation.normalized_manifest)
    agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.registered",
            detail=f"Plugin {saved.id} registered.",
            metadata={
                "plugin_id": saved.id,
                "enabled": saved.enabled,
                "trusted": saved.trusted,
                "reason": request.reason,
            },
        )
    )
    return saved


async def enable_productization_plugin(plugin_id: str, request: PluginActionRequest | None = None) -> PluginManifest:
    try:
        current = agent.store.plugin_manifest(plugin_id)
        candidate = current.model_copy(update={"enabled": True})
        validation = productization.validate_plugin(
            candidate,
            policy=productization.ensure_enterprise_policy(agent.store),
        )
        if not validation.valid:
            raise HTTPException(status_code=400, detail="; ".join(validation.errors))
        saved = agent.store.update_plugin_state(plugin_id, enabled=True, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.enabled",
            detail=f"Plugin {saved.id} enabled.",
            metadata={"plugin_id": saved.id, "reason": request.reason if request else ""},
        )
    )
    return saved


async def disable_productization_plugin(plugin_id: str, request: PluginActionRequest | None = None) -> PluginManifest:
    try:
        saved = agent.store.update_plugin_state(plugin_id, enabled=False, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.disabled",
            status="warning",
            detail=f"Plugin {saved.id} disabled.",
            metadata={"plugin_id": saved.id, "reason": request.reason if request else ""},
        )
    )
    return saved


async def trust_productization_plugin(plugin_id: str, request: PluginActionRequest | None = None) -> PluginManifest:
    try:
        current = agent.store.plugin_manifest(plugin_id)
        candidate = current.model_copy(update={"trusted": True})
        validation = productization.validate_plugin(
            candidate,
            policy=productization.ensure_enterprise_policy(agent.store),
        )
        if not validation.valid:
            raise HTTPException(status_code=400, detail="; ".join(validation.errors))
        saved = agent.store.update_plugin_state(plugin_id, trusted=True, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.trusted",
            detail=f"Plugin {saved.id} marked trusted.",
            metadata={"plugin_id": saved.id, "reason": request.reason if request else ""},
        )
    )
    return saved


def _plugin_manifest_snapshot(manifest: PluginManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    metadata = dict(payload.get("metadata") or {})
    metadata.pop("previous_manifest", None)
    payload["metadata"] = metadata
    return payload


async def update_productization_plugin(plugin_id: str, request: PluginLifecycleActionRequest) -> PluginLifecycleActionResponse:
    if request.manifest is None:
        raise HTTPException(status_code=400, detail="plugin update requires a replacement manifest")
    try:
        current = agent.store.plugin_manifest(plugin_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    if request.manifest.id != current.id:
        raise HTTPException(status_code=400, detail="replacement plugin manifest id must match the installed plugin")
    metadata = dict(request.manifest.metadata or {})
    metadata.update(
        {
            "previous_manifest": _plugin_manifest_snapshot(current),
            "lifecycle_status": "updated",
            "lifecycle_updated_at": utc_now(),
            "latest_lifecycle_reason": request.reason,
        }
    )
    candidate = request.manifest.model_copy(
        update={
            "created_at": current.created_at,
            "enabled": current.enabled if request.enable is None else bool(request.enable),
            "trusted": current.trusted if request.trust is None else bool(request.trust),
            "metadata": metadata,
        }
    )
    validation = productization.validate_plugin(
        candidate,
        policy=productization.ensure_enterprise_policy(agent.store),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "plugin manifest update is invalid")
    saved = agent.store.upsert_plugin_manifest(validation.normalized_manifest)
    audit = agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.updated",
            detail=f"Plugin {saved.id} updated from {current.version} to {saved.version}.",
            metadata={"plugin_id": saved.id, "from_version": current.version, "to_version": saved.version, "reason": request.reason},
        )
    )
    return PluginLifecycleActionResponse(
        action="update",
        status="updated",
        plugin=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Previous manifest was stored for rollback before the update was saved."],
    )


async def rollback_productization_plugin(plugin_id: str, request: PluginLifecycleActionRequest | None = None) -> PluginLifecycleActionResponse:
    reason = request.reason if request else ""
    try:
        current = agent.store.plugin_manifest(plugin_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    previous_payload = dict(current.metadata or {}).get("previous_manifest")
    if not isinstance(previous_payload, dict):
        raise HTTPException(status_code=400, detail="plugin rollback requires a stored previous manifest")
    previous = PluginManifest.model_validate(previous_payload)
    metadata = dict(previous.metadata or {})
    metadata.update(
        {
            "previous_manifest": _plugin_manifest_snapshot(current),
            "lifecycle_status": "rolled_back",
            "lifecycle_updated_at": utc_now(),
            "latest_lifecycle_reason": reason,
        }
    )
    candidate = previous.model_copy(update={"enabled": current.enabled, "trusted": current.trusted, "metadata": metadata})
    validation = productization.validate_plugin(
        candidate,
        policy=productization.ensure_enterprise_policy(agent.store),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "stored rollback manifest is invalid")
    saved = agent.store.upsert_plugin_manifest(validation.normalized_manifest)
    audit = agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.rolled_back",
            status="warning",
            detail=f"Plugin {saved.id} rolled back from {current.version} to {saved.version}.",
            metadata={"plugin_id": saved.id, "from_version": current.version, "to_version": saved.version, "reason": reason},
        )
    )
    return PluginLifecycleActionResponse(
        action="rollback",
        status="rolled_back",
        plugin=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Rollback restored the stored previous manifest and kept current trust/enable state."],
    )


async def uninstall_productization_plugin(plugin_id: str, request: PluginLifecycleActionRequest | None = None) -> PluginLifecycleActionResponse:
    reason = request.reason if request else ""
    try:
        current = agent.store.plugin_manifest(plugin_id)
        saved = agent.store.update_plugin_state(
            plugin_id,
            enabled=False,
            reason=reason,
            metadata_updates={
                "previous_manifest": _plugin_manifest_snapshot(current),
                "lifecycle_status": "uninstalled",
                "uninstall_mode": "safe_disable",
                "uninstalled_at": utc_now(),
                "latest_lifecycle_reason": reason,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin not found") from exc
    audit = agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="plugin.uninstalled",
            status="warning",
            detail=f"Plugin {saved.id} safe-uninstalled by disabling runtime visibility.",
            metadata={"plugin_id": saved.id, "reason": reason, "uninstall_mode": "safe_disable"},
        )
    )
    return PluginLifecycleActionResponse(
        action="uninstall",
        status="uninstalled",
        plugin=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Safe uninstall disables the plugin and keeps the manifest for rollback/audit review."],
    )


async def get_enterprise_policy() -> EnterprisePolicyProfile:
    return productization.ensure_enterprise_policy(agent.store)


async def update_enterprise_policy(request: EnterprisePolicyUpdateRequest) -> EnterprisePolicyProfile:
    saved = agent.store.save_enterprise_policy(request.profile)
    agent.store.record_worker_audit_event(
        distributed_runtime.audit_event(
            event_type="enterprise.policy.updated",
            detail=f"Enterprise policy {saved.id} saved.",
            metadata={
                "policy_id": saved.id,
                "privacy_mode": saved.privacy_mode,
                "permission_profile": saved.permission_profile,
                "reason": request.reason,
            },
        )
    )
    return saved


register_productization_routes(
    app,
    productization_snapshot=lambda workspace_root, refresh_metrics: productization_snapshot(
        workspace_root,
        refresh_metrics,
    ),
    refresh_productization_snapshot=lambda request: refresh_productization_snapshot(request),
    productization_stable_apis=lambda: productization_stable_apis(),
    productization_recovery=lambda workspace_root: productization_recovery(workspace_root),
    productization_reliability=lambda workspace_root: productization_reliability(workspace_root),
    list_productization_plugins=lambda include_disabled: list_productization_plugins(include_disabled),
    validate_productization_plugin=lambda request: validate_productization_plugin(request),
    register_productization_plugin=lambda request: register_productization_plugin(request),
    enable_productization_plugin=lambda plugin_id, request=None: enable_productization_plugin(plugin_id, request),
    disable_productization_plugin=lambda plugin_id, request=None: disable_productization_plugin(plugin_id, request),
    trust_productization_plugin=lambda plugin_id, request=None: trust_productization_plugin(plugin_id, request),
    update_productization_plugin=lambda plugin_id, request: update_productization_plugin(plugin_id, request),
    rollback_productization_plugin=lambda plugin_id, request=None: rollback_productization_plugin(plugin_id, request),
    uninstall_productization_plugin=lambda plugin_id, request=None: uninstall_productization_plugin(plugin_id, request),
    get_enterprise_policy=lambda: get_enterprise_policy(),
    update_enterprise_policy=lambda request: update_enterprise_policy(request),
)


def _record_ecosystem_audit(action: str, subject_id: str, detail: str, *, status: str = "ok", metadata: dict[str, Any] | None = None) -> EcosystemAuditEvent:
    return agent.store.record_ecosystem_audit_event(
        EcosystemAuditEvent(
            id=str(uuid4()),
            created_at=utc_now(),
            action=action,
            subject_id=subject_id,
            status=status,
            detail=detail,
            metadata=metadata or {},
        )
    )


async def ecosystem_snapshot(
    workspace_root: str | None = Query(default=None),
    rebuild_graph: bool = Query(default=False),
    query: str = Query(default=""),
) -> EcosystemSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _ecosystem_snapshot(root, rebuild_graph=rebuild_graph, include_search_query=query)


async def refresh_ecosystem_snapshot(request: EcosystemRefreshRequest) -> EcosystemSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _ecosystem_snapshot(root, rebuild_graph=request.rebuild_graph, include_search_query=request.include_search_query)


async def ecosystem_marketplace_catalog() -> list[EcosystemPackageManifest]:
    return ecosystem.marketplace_catalog()


async def list_ecosystem_packages(include_disabled: bool = Query(default=True)) -> list[EcosystemPackageManifest]:
    return agent.store.ecosystem_packages(include_disabled=include_disabled)


async def validate_ecosystem_package(request: EcosystemPackageValidationRequest) -> EcosystemPackageValidationResult:
    return ecosystem.validate_package(
        request,
        policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
    )


async def register_ecosystem_package(request: EcosystemPackageRegistrationRequest) -> EcosystemPackageManifest:
    trust_level = request.trust_level or request.manifest.trust_level
    candidate = request.manifest.model_copy(update={"enabled": request.enable, "trust_level": trust_level})
    validation = ecosystem.validate_package(
        candidate,
        policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "ecosystem package manifest is invalid")
    saved = agent.store.upsert_ecosystem_package(validation.normalized_manifest)
    _record_ecosystem_audit(
        "package.registered",
        saved.id,
        f"Ecosystem package {saved.id} registered.",
        metadata={"enabled": saved.enabled, "trust_level": saved.trust_level, "reason": request.reason},
    )
    return saved


async def enable_ecosystem_package(package_id: str, request: EcosystemPackageActionRequest | None = None) -> EcosystemPackageManifest:
    try:
        current = agent.store.ecosystem_package(package_id)
        candidate = current.model_copy(update={"enabled": True})
        validation = ecosystem.validate_package(
            candidate,
            policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
        )
        if not validation.valid:
            raise HTTPException(status_code=400, detail="; ".join(validation.errors))
        saved = agent.store.update_ecosystem_package_state(package_id, enabled=True, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    _record_ecosystem_audit("package.enabled", saved.id, f"Ecosystem package {saved.id} enabled.", metadata={"reason": request.reason if request else ""})
    return saved


async def disable_ecosystem_package(package_id: str, request: EcosystemPackageActionRequest | None = None) -> EcosystemPackageManifest:
    try:
        saved = agent.store.update_ecosystem_package_state(package_id, enabled=False, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    _record_ecosystem_audit(
        "package.disabled",
        saved.id,
        f"Ecosystem package {saved.id} disabled.",
        status="warning",
        metadata={"reason": request.reason if request else ""},
    )
    return saved


async def trust_ecosystem_package(package_id: str, request: EcosystemPackageActionRequest | None = None) -> EcosystemPackageManifest:
    try:
        current = agent.store.ecosystem_package(package_id)
        trust_level = request.trust_level if request and request.trust_level else "trusted"
        candidate = current.model_copy(update={"trust_level": trust_level})
        validation = ecosystem.validate_package(
            candidate,
            policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
        )
        if not validation.valid:
            raise HTTPException(status_code=400, detail="; ".join(validation.errors))
        saved = agent.store.update_ecosystem_package_state(package_id, trust_level=trust_level, reason=request.reason if request else "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    _record_ecosystem_audit(
        "package.trusted",
        saved.id,
        f"Ecosystem package {saved.id} trust set to {saved.trust_level}.",
        metadata={"trust_level": saved.trust_level, "reason": request.reason if request else ""},
    )
    return saved


def _ecosystem_package_snapshot(manifest: EcosystemPackageManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    metadata = dict(payload.get("metadata") or {})
    metadata.pop("previous_manifest", None)
    payload["metadata"] = metadata
    return payload


async def update_ecosystem_package(package_id: str, request: EcosystemPackageLifecycleRequest) -> EcosystemPackageLifecycleResponse:
    if request.manifest is None:
        raise HTTPException(status_code=400, detail="ecosystem package update requires a replacement manifest")
    try:
        current = agent.store.ecosystem_package(package_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    if request.manifest.id != current.id:
        raise HTTPException(status_code=400, detail="replacement package manifest id must match the installed package")
    trust_level = request.trust_level or current.trust_level
    metadata = dict(request.manifest.metadata or {})
    metadata.update(
        {
            "previous_manifest": _ecosystem_package_snapshot(current),
            "lifecycle_status": "updated",
            "lifecycle_updated_at": utc_now(),
            "latest_lifecycle_reason": request.reason,
        }
    )
    candidate = request.manifest.model_copy(
        update={
            "enabled": current.enabled if request.enable is None else bool(request.enable),
            "trust_level": trust_level,
            "installed": True,
            "installed_at": current.installed_at,
            "metadata": metadata,
        }
    )
    validation = ecosystem.validate_package(
        candidate,
        policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "ecosystem package update is invalid")
    saved = agent.store.upsert_ecosystem_package(validation.normalized_manifest)
    audit = _record_ecosystem_audit(
        "package.updated",
        saved.id,
        f"Ecosystem package {saved.id} updated from {current.version} to {saved.version}.",
        metadata={"from_version": current.version, "to_version": saved.version, "reason": request.reason},
    )
    return EcosystemPackageLifecycleResponse(
        action="update",
        status="updated",
        package=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Previous package manifest was stored for rollback before the update was saved."],
    )


async def rollback_ecosystem_package(package_id: str, request: EcosystemPackageLifecycleRequest | None = None) -> EcosystemPackageLifecycleResponse:
    reason = request.reason if request else ""
    try:
        current = agent.store.ecosystem_package(package_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    previous_payload = dict(current.metadata or {}).get("previous_manifest")
    if not isinstance(previous_payload, dict):
        raise HTTPException(status_code=400, detail="ecosystem package rollback requires a stored previous manifest")
    previous = EcosystemPackageManifest.model_validate(previous_payload)
    metadata = dict(previous.metadata or {})
    metadata.update(
        {
            "previous_manifest": _ecosystem_package_snapshot(current),
            "lifecycle_status": "rolled_back",
            "lifecycle_updated_at": utc_now(),
            "latest_lifecycle_reason": reason,
        }
    )
    candidate = previous.model_copy(update={"enabled": current.enabled, "trust_level": current.trust_level, "metadata": metadata})
    validation = ecosystem.validate_package(
        candidate,
        policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
    )
    if not validation.valid or validation.normalized_manifest is None:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors) or "stored rollback package manifest is invalid")
    saved = agent.store.upsert_ecosystem_package(validation.normalized_manifest)
    audit = _record_ecosystem_audit(
        "package.rolled_back",
        saved.id,
        f"Ecosystem package {saved.id} rolled back from {current.version} to {saved.version}.",
        status="warning",
        metadata={"from_version": current.version, "to_version": saved.version, "reason": reason},
    )
    return EcosystemPackageLifecycleResponse(
        action="rollback",
        status="rolled_back",
        package=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Rollback restored the stored previous manifest and kept current trust/enable state."],
    )


async def uninstall_ecosystem_package(package_id: str, request: EcosystemPackageLifecycleRequest | None = None) -> EcosystemPackageLifecycleResponse:
    reason = request.reason if request else ""
    try:
        current = agent.store.ecosystem_package(package_id)
        saved = agent.store.update_ecosystem_package_state(
            package_id,
            enabled=False,
            reason=reason,
            metadata_updates={
                "previous_manifest": _ecosystem_package_snapshot(current),
                "lifecycle_status": "uninstalled",
                "uninstall_mode": "safe_disable",
                "uninstalled_at": utc_now(),
                "latest_lifecycle_reason": reason,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ecosystem package not found") from exc
    audit = _record_ecosystem_audit(
        "package.uninstalled",
        saved.id,
        f"Ecosystem package {saved.id} safe-uninstalled by disabling runtime visibility.",
        status="warning",
        metadata={"reason": reason, "uninstall_mode": "safe_disable"},
    )
    return EcosystemPackageLifecycleResponse(
        action="uninstall",
        status="uninstalled",
        package=saved,
        previous_manifest=current,
        audit_event_id=audit.id,
        notes=["Safe uninstall disables the package and keeps the manifest for rollback/audit review."],
    )


async def list_ecosystem_workflows(include_disabled: bool = Query(default=True)) -> list[EcosystemWorkflowDefinition]:
    ecosystem.ensure_baseline(agent.store)
    return agent.store.ecosystem_workflows(include_disabled=include_disabled)


async def register_ecosystem_workflow(workflow: EcosystemWorkflowDefinition) -> EcosystemWorkflowDefinition:
    if workflow.api_version != ECOSYSTEM_API_VERSION:
        raise HTTPException(status_code=400, detail="workflow API version is not compatible with this Aegis runtime")
    saved = agent.store.upsert_ecosystem_workflow(workflow)
    _record_ecosystem_audit("workflow.registered", saved.id, f"Workflow {saved.id} registered.", metadata={"category": saved.category})
    return saved


async def run_ecosystem_workflow(workflow_id: str, request: WorkflowRunRequest) -> WorkflowRunResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    ecosystem.ensure_baseline(agent.store)
    try:
        workflow = agent.store.ecosystem_workflow(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    try:
        return ecosystem.run_workflow(agent.store, workflow=workflow, project_root=root, request=request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def list_shared_intelligence_profiles(
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SharedIntelligenceProfile]:
    return agent.store.shared_intelligence_profiles(kind=kind, limit=limit)


async def import_shared_intelligence_profile(request: SharedIntelligenceProfileImportRequest) -> SharedIntelligenceProfile:
    saved = agent.store.upsert_shared_intelligence_profile(request.profile)
    _record_ecosystem_audit(
        "shared_profile.imported",
        saved.id,
        f"Shared intelligence profile {saved.id} imported.",
        metadata={"kind": saved.kind, "reason": request.reason},
    )
    return saved


async def export_shared_intelligence_profile(profile_id: str) -> SharedIntelligenceProfileExportResponse:
    try:
        profile = agent.store.shared_intelligence_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="shared intelligence profile not found") from exc
    return SharedIntelligenceProfileExportResponse(profile=profile, checksum=profile.checksum)


async def export_current_project_intelligence(workspace_root: str | None = Query(default=None)) -> SharedIntelligenceProfileExportResponse:
    root = _resolve_workspace_or_400(workspace_root)
    profile = ecosystem.shared_profile_from_project(project_root=root, project_intelligence=_project_intelligence_snapshot(root))
    saved = agent.store.upsert_shared_intelligence_profile(profile)
    _record_ecosystem_audit("shared_profile.exported", saved.id, f"Current project intelligence exported as {saved.id}.")
    return SharedIntelligenceProfileExportResponse(profile=saved, checksum=saved.checksum)


async def get_organization_policy() -> OrganizationPolicyProfile:
    ecosystem.ensure_baseline(agent.store)
    return agent.store.active_organization_policy() or ecosystem.default_organization_policy()


async def update_organization_policy(request: OrganizationPolicyUpdateRequest) -> OrganizationPolicyProfile:
    saved = agent.store.save_organization_policy(request.profile)
    _record_ecosystem_audit(
        "organization_policy.updated",
        saved.id,
        f"Organization policy {saved.id} saved.",
        metadata={"reason": request.reason, "collaboration_mode": saved.collaboration_mode},
    )
    return saved


async def ecosystem_knowledge_graph(
    workspace_root: str | None = Query(default=None),
    rebuild: bool = Query(default=False),
) -> KnowledgeGraphSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    if not rebuild:
        cached = agent.store.knowledge_graph_snapshot(project_root=root)
        if cached is not None:
            return cached
    return _ecosystem_snapshot(root, rebuild_graph=rebuild).knowledge_graph


async def ecosystem_search(request: EcosystemSearchRequest) -> EcosystemSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    graph = agent.store.knowledge_graph_snapshot(project_root=root)
    if graph is None:
        graph = _ecosystem_snapshot(root, rebuild_graph=True).knowledge_graph
    return ecosystem.search(request, store=agent.store, project_root=root, graph=graph)


async def create_reproducibility_record(request: ReproducibilityRequest) -> ReproducibilityRecord:
    root = _resolve_workspace_or_400(request.workspace_root)
    record = ecosystem.create_reproducibility_record(
        store=agent.store,
        project_root=root,
        task_id=request.task_id,
        include_timeline=request.include_timeline,
    )
    _record_ecosystem_audit(
        "reproducibility.created",
        record.id,
        f"Reproducibility record {record.id} created.",
        metadata={"task_id": request.task_id, "status": record.status},
    )
    return record


async def list_reproducibility_records(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ReproducibilityRecord]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.reproducibility_records(project_root=root, limit=limit)


async def list_ecosystem_audit_events(limit: int = Query(default=50, ge=1, le=200)) -> list[EcosystemAuditEvent]:
    return agent.store.ecosystem_audit_events(limit=limit)


register_ecosystem_routes(
    app,
    ecosystem_snapshot=lambda workspace_root, rebuild_graph, query: ecosystem_snapshot(
        workspace_root,
        rebuild_graph,
        query,
    ),
    refresh_ecosystem_snapshot=lambda request: refresh_ecosystem_snapshot(request),
    ecosystem_marketplace_catalog=lambda: ecosystem_marketplace_catalog(),
    list_ecosystem_packages=lambda include_disabled: list_ecosystem_packages(include_disabled),
    validate_ecosystem_package=lambda request: validate_ecosystem_package(request),
    register_ecosystem_package=lambda request: register_ecosystem_package(request),
    enable_ecosystem_package=lambda package_id, request=None: enable_ecosystem_package(package_id, request),
    disable_ecosystem_package=lambda package_id, request=None: disable_ecosystem_package(package_id, request),
    trust_ecosystem_package=lambda package_id, request=None: trust_ecosystem_package(package_id, request),
    update_ecosystem_package=lambda package_id, request: update_ecosystem_package(package_id, request),
    rollback_ecosystem_package=lambda package_id, request=None: rollback_ecosystem_package(package_id, request),
    uninstall_ecosystem_package=lambda package_id, request=None: uninstall_ecosystem_package(package_id, request),
    list_ecosystem_workflows=lambda include_disabled: list_ecosystem_workflows(include_disabled),
    register_ecosystem_workflow=lambda workflow: register_ecosystem_workflow(workflow),
    run_ecosystem_workflow=lambda workflow_id, request: run_ecosystem_workflow(workflow_id, request),
    list_shared_intelligence_profiles=lambda kind, limit: list_shared_intelligence_profiles(kind, limit),
    import_shared_intelligence_profile=lambda request: import_shared_intelligence_profile(request),
    export_shared_intelligence_profile=lambda profile_id: export_shared_intelligence_profile(profile_id),
    export_current_project_intelligence=lambda workspace_root: export_current_project_intelligence(workspace_root),
    get_organization_policy=lambda: get_organization_policy(),
    update_organization_policy=lambda request: update_organization_policy(request),
    ecosystem_knowledge_graph=lambda workspace_root, rebuild: ecosystem_knowledge_graph(workspace_root, rebuild),
    ecosystem_search=lambda request: ecosystem_search(request),
    create_reproducibility_record=lambda request: create_reproducibility_record(request),
    list_reproducibility_records=lambda workspace_root, limit: list_reproducibility_records(workspace_root, limit),
    list_ecosystem_audit_events=lambda limit: list_ecosystem_audit_events(limit),
)


async def autonomous_engineering_snapshot(workspace_root: str | None = Query(default=None)) -> AutonomousEngineeringSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _autonomous_snapshot(root)


async def list_autonomous_objectives(
    workspace_root: str | None = Query(default=None),
    include_completed: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AutonomousObjective]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.autonomous_objectives(project_root=root, include_completed=include_completed, limit=limit)


async def create_autonomous_objective(request: AutonomousObjectiveCreateRequest) -> AutonomousObjectiveDetail:
    root = _resolve_workspace_or_400(request.workspace_root)
    detail = autonomous_engineering.create_objective(
        agent.store,
        project_root=root,
        request=request,
        project_intelligence=_project_intelligence_snapshot(root),
    )
    _record_ecosystem_audit(
        "autonomous.objective.created",
        detail.objective.id,
        f"Autonomous objective {detail.objective.title} created.",
        metadata={"dry_run": request.dry_run, "phase_count": len(detail.phases), "gate_count": len(detail.approval_gates)},
    )
    core_result = await core_runtime_client.create_engineering_execution(
        root,
        goal=request.user_goal,
        mode="safe_assisted",
        constraints=[
            "Preserve Website autonomous-engineering API compatibility.",
            "Use Core checkpoints, validation, repair journals, and approval gates before file mutation.",
        ],
        max_repair_attempts=request.max_iterations,
        metadata={
            "website_objective_id": detail.objective.id,
            "website_objective_title": detail.objective.title,
            "priority": request.priority,
            "dry_run": request.dry_run,
        },
    )
    if core_result.delegated and isinstance(core_result.data, dict):
        execution = core_result.data.get("execution") if isinstance(core_result.data.get("execution"), dict) else {}
        metadata = {
            **detail.objective.metadata,
            "core_engineering_execution_id": execution.get("id", ""),
            "core_workflow_id": execution.get("workflow_id", ""),
            "core_runtime_owner": "aegis-core",
        }
        objective = detail.objective.model_copy(update={"metadata": metadata})
        agent.store.upsert_autonomous_objective(objective)
        detail = agent.store.autonomous_objective_detail(objective.id)
        _record_ecosystem_audit(
            "autonomous.objective.core_execution",
            detail.objective.id,
            "Website autonomous objective linked to Core engineering execution.",
            metadata={"core_engineering_execution_id": execution.get("id", ""), "core_workflow_id": execution.get("workflow_id", "")},
        )
    elif core_result.should_fallback:
        core_runtime_client.record_fallback("engineering.execution", core_result.error or "Core engineering execution unavailable.")
    return detail


async def get_autonomous_objective(objective_id: str) -> AutonomousObjectiveDetail:
    try:
        return agent.store.autonomous_objective_detail(objective_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


async def simulate_autonomous_objective(objective_id: str) -> AutonomousSimulationEstimate:
    try:
        objective = agent.store.autonomous_objective(objective_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc
    root = _resolve_workspace_or_400(objective.workspace_root)
    return autonomous_engineering.simulate_existing(
        agent.store,
        objective_id,
        project_intelligence=_project_intelligence_snapshot(root),
    )


async def start_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.start_objective(agent.store, objective_id, request or AutonomousObjectiveActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def pause_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.pause_objective(agent.store, objective_id, request or AutonomousObjectiveActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


async def cancel_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.cancel_objective(agent.store, objective_id, request or AutonomousObjectiveActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


async def iterate_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveIterationRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.iterate_objective(agent.store, objective_id, request or AutonomousObjectiveIterationRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def list_autonomous_approval_gates(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[AutonomousApprovalGate]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.autonomous_approval_gates(project_root=root, limit=limit)


async def approve_autonomous_gate(
    gate_id: str,
    request: AutonomousApprovalActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.approve_gate(agent.store, gate_id, request or AutonomousApprovalActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous approval gate not found") from exc


async def reject_autonomous_gate(
    gate_id: str,
    request: AutonomousApprovalActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.reject_gate(agent.store, gate_id, request or AutonomousApprovalActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous approval gate not found") from exc


register_autonomous_engineering_routes(
    app,
    autonomous_engineering_snapshot=lambda workspace_root: autonomous_engineering_snapshot(workspace_root),
    list_autonomous_objectives=lambda workspace_root, include_completed, limit: list_autonomous_objectives(
        workspace_root,
        include_completed,
        limit,
    ),
    create_autonomous_objective=lambda request: create_autonomous_objective(request),
    get_autonomous_objective=lambda objective_id: get_autonomous_objective(objective_id),
    simulate_autonomous_objective=lambda objective_id: simulate_autonomous_objective(objective_id),
    start_autonomous_objective=lambda objective_id, request=None: start_autonomous_objective(objective_id, request),
    pause_autonomous_objective=lambda objective_id, request=None: pause_autonomous_objective(objective_id, request),
    cancel_autonomous_objective=lambda objective_id, request=None: cancel_autonomous_objective(objective_id, request),
    iterate_autonomous_objective=lambda objective_id, request=None: iterate_autonomous_objective(objective_id, request),
    list_autonomous_approval_gates=lambda workspace_root, limit: list_autonomous_approval_gates(workspace_root, limit),
    approve_autonomous_gate=lambda gate_id, request=None: approve_autonomous_gate(gate_id, request),
    reject_autonomous_gate=lambda gate_id, request=None: reject_autonomous_gate(gate_id, request),
)


def _utility_service() -> UtilityService:
    return UtilityService(
        settings=settings,
        agent=agent,
        core_runtime_client=core_runtime_client,
        workspace_manager=workspace_manager,
        resolve_workspace=_resolve_workspace_or_400,
        invalidate_workspace_caches=_invalidate_workspace_caches,
        refresh_runtime=refresh_runtime,
        update_env=update_env,
        core_delegation_data=_core_delegation_data,
        core_delegation_error=_core_delegation_error,
        record_core_fallback=_record_core_fallback,
    )


register_utility_routes(
    app,
    root=lambda: _utility_service().root(),
    get_memory_notes=lambda workspace_root, category: _utility_service().get_memory_notes(workspace_root, category),
    get_memory_governance=lambda workspace_root: _utility_service().get_memory_governance(workspace_root),
    export_memory_notes=lambda request, workspace_root: _utility_service().export_memory_notes(request, workspace_root),
    update_memory_governance_controls=lambda request, workspace_root: _utility_service().update_memory_governance_controls(
        request,
        workspace_root,
    ),
    create_memory_note=lambda request, workspace_root: _utility_service().create_memory_note(request, workspace_root),
    record_feedback=lambda request, workspace_root: _utility_service().record_feedback(request, workspace_root),
    update_memory_note=lambda note_id, request, workspace_root: _utility_service().update_memory_note(
        note_id,
        request,
        workspace_root,
    ),
    delete_memory_note=lambda note_id, workspace_root: _utility_service().delete_memory_note(note_id, workspace_root),
    get_approval_settings=lambda workspace_root: _utility_service().get_approval_settings(workspace_root),
    update_approval_settings=lambda request, workspace_root: _utility_service().update_approval_settings(
        request,
        workspace_root,
    ),
    rebuild_index=lambda workspace_root: _utility_service().rebuild_index(workspace_root),
    search_index=lambda request, workspace_root: _utility_service().search_index(request, workspace_root),
    compare_files=lambda request, workspace_root: _utility_service().compare_files(request, workspace_root),
    apply_patch=lambda request, workspace_root: _utility_service().apply_patch(request, workspace_root),
    summarize_diff=lambda request: _utility_service().summarize_diff(request),
)
