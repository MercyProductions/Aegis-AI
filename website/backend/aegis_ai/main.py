# backend/main.py
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import time
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .adaptive_intelligence import AdaptiveIntelligenceEngine
from .agent import AgentEngine, MODE_OPTIONS
from .auth import AccountStore
from .autonomous_engineering import AutonomousEngineeringEngine
from .continuity import AegisContinuityEngine
from .creative_media import CreativeMediaEngine
from .distributed_runtime import DistributedRuntimeManager
from .ecosystem import ECOSYSTEM_API_VERSION, EcosystemEngine
from .model_benchmark import ModelBenchmarkManager
from .model_manager import ModelManager
from .model_registry import ModelRegistryManager
from .operating_environment import OperatingEnvironmentEngine
from .platform_discipline import PlatformDisciplineEngine
from .productization import ProductizationEngine
from .project_intelligence import ProjectIntelligenceEngine
from .project_scaffolder import ProjectScaffolder
from .unified_context import UnifiedContextEngine
from .unified_runtime import RuntimeSignalCounts, UnifiedRuntimeEngine
from .workspace_autopilot import (
    build_workspace_autopilot_status,
)
from .workspace_operations import WorkspaceOperationsEngine
from .workspace_setup import (
    merge_missing_manifest_fields,
    workspace_setup_manifest,
)
from .schemas import (
    AdaptiveBenchmarkReport,
    AdaptiveBenchmarkRunRequest,
    AdaptiveIntelligenceRefreshRequest,
    AdaptiveIntelligenceSnapshot,
    AdaptivePolicyProfileUpdateRequest,
    AdaptivePolicyRollbackRequest,
    AdaptiveReplayRequest,
    AgentRequest,
    AgentResponse,
    AegisContinuitySnapshot,
    AppConfig,
    ApplyRequest,
    ApplyResponse,
    AuthForgotPasswordRequest,
    AuthLoginRequest,
    AuthMessageResponse,
    AuthRegisterRequest,
    AuthSessionResponse,
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
    ChatStreamEventInfo,
    CheckpointListResponse,
    ConfigUpdateRequest,
    DistributedRuntimeSnapshot,
    EcosystemAuditEvent,
    EcosystemPackageActionRequest,
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
    FeedbackRecordRequest,
    FeedbackRecordResponse,
    FeedbackTelemetryResponse,
    EvaluationReplayResult,
    GlobalCommandRequest,
    GlobalCommandResponse,
    HistoryResponse,
    HybridRouteDecision,
    HybridRouteRequest,
    IntelligencePolicyProfile,
    KnowledgeGraphSnapshot,
    MediaAssetLibraryResponse,
    MediaCapabilitiesResponse,
    MediaCreativeRequest,
    MediaExportRequest,
    MediaExportResponse,
    MediaJobResponse,
    MediaPromptPreset,
    MediaProviderInfo,
    ModelBenchmarkJobInfo,
    ModelBenchmarkRunRequest,
    ModelBenchmarkSnapshot,
    ModelCapabilities,
    ModelDeleteRequest,
    ModelAdapterHealthInfo,
    ModelInfo,
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
    ModelRegistryResponse,
    ModelRouteHealthInfo,
    ModeOption,
    PluginActionRequest,
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
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
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
creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
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


def _normalized_cache_path(path: Path) -> str:
    return normalized_cache_path(path)


def _cache_paths_are_related(left: str, right: str) -> bool:
    return cache_paths_are_related(left, right)


def _clear_workspace_status_cache(root: Path | None = None) -> None:
    _workspace_status_cache.clear(root)


def _clear_project_plan_cache() -> None:
    _project_plan_cache.clear()


def _invalidate_workspace_caches(root: Path | None = None) -> None:
    _clear_workspace_status_cache(root)
    _clear_project_plan_cache()


def _prune_workspace_status_cache() -> None:
    _workspace_status_cache.prune()


def _prune_project_plan_cache() -> None:
    _project_plan_cache.prune()


def _workspace_status_snapshot(root: Path) -> WorkspaceStatusSnapshot:
    now = time.monotonic()
    cached = _workspace_status_cache.get(root, now=now)
    if cached is not None:
        return cached

    manifest = workspace_manager.load_project_manifest(root)
    dependency_profile = workspace_manager.inspect_dependency_profile(root)
    instruction_status = agent.instruction_status_snapshot(root)
    validation_plan = agent.validation_plan_snapshot(root)
    command_history = agent.command_history_snapshot(root)
    readiness = agent.workspace_readiness_snapshot(
        manifest=manifest,
        dependency_profile=dependency_profile,
        instruction_status=instruction_status,
        validation_plan=validation_plan,
        command_history=command_history,
    )
    snapshot = WorkspaceStatusSnapshot(
        created_at=now,
        manifest=manifest,
        dependency_profile=dependency_profile,
        instruction_status=instruction_status,
        validation_plan=validation_plan,
        command_history=command_history,
        readiness=readiness,
    )
    _workspace_status_cache.set(root, snapshot)
    return snapshot


def _build_project_intelligence(
    root: Path,
    *,
    clear_memory: bool = False,
    rebuild_memory: bool = False,
) -> ProjectIntelligenceSnapshot:
    if clear_memory:
        agent.store.clear_project_memory(project_root=root)

    _clear_workspace_status_cache(root)
    snapshot = _workspace_status_snapshot(root)
    files = workspace_manager.scan(root, max_files=1500)
    project_memory = agent.store.project_memory(project_root=root, limit=80)
    recent_tasks = agent.store.list_tasks(project_root=root, limit=80, include_subtasks=False)
    fix_memory = agent.store.fix_history(project_root=root, limit=80)
    intelligence = project_intelligence.build_snapshot(
        workspace_root=root,
        files=files,
        dependency_profile=snapshot.dependency_profile,
        manifest=snapshot.manifest,
        project_memory=project_memory,
        recent_tasks=recent_tasks,
        fix_memory=fix_memory,
    )
    agent.store.save_project_intelligence(intelligence)

    if rebuild_memory:
        for category, title, detail, source, confidence in project_intelligence.memory_notes_for_snapshot(intelligence):
            agent.store.remember_project_note(
                project_root=root,
                category=category,
                title=title,
                detail=detail,
                source=source,
                confidence=confidence,
            )
        intelligence = intelligence.model_copy(update={"project_memory": agent.store.project_memory(project_root=root, limit=80)})
        agent.store.save_project_intelligence(intelligence)

    return intelligence


def _project_intelligence_snapshot(root: Path, *, rebuild: bool = False) -> ProjectIntelligenceSnapshot:
    if not rebuild:
        cached = agent.store.project_intelligence(project_root=root)
        if cached is not None:
            return cached
    return _build_project_intelligence(root)


def _build_workspace_operations(
    root: Path,
    *,
    refresh_project_intelligence: bool = True,
    generate_recommendations: bool = True,
    include_git: bool = True,
) -> WorkspaceOperationsSnapshot:
    _clear_workspace_status_cache(root)
    status = _workspace_status_snapshot(root)
    files = workspace_manager.scan(root, max_files=1500)
    intelligence = (
        _build_project_intelligence(root)
        if refresh_project_intelligence
        else agent.store.project_intelligence(project_root=root)
    )
    snapshot = workspace_operations.build_snapshot(
        workspace_root=root,
        files=files,
        dependency_profile=status.dependency_profile,
        project_intelligence=intelligence,
        recent_tasks=agent.store.list_tasks(project_root=root, limit=100, include_subtasks=False),
        fix_memory=agent.store.fix_history(project_root=root, limit=80),
        project_memory=agent.store.project_memory(project_root=root, limit=100),
        previous_watch=agent.store.workspace_watch_snapshot(project_root=root),
        previous_recommendations=agent.store.workspace_recommendations(project_root=root, include_dismissed=True, limit=200),
        job_runs=workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root)),
        include_git=include_git,
    )
    agent.store.save_workspace_watch_snapshot(snapshot.watcher)
    agent.store.record_workspace_events(snapshot.watcher.events)
    if generate_recommendations:
        agent.store.upsert_workspace_recommendations(snapshot.recommendations)
    for note in snapshot.long_term_memory[:6]:
        agent.store.remember_project_note(
            project_root=root,
            category="operations",
            title="Workspace operations signal",
            detail=note,
            source="workspace_operations",
            confidence=0.62,
        )
    persisted_recommendations = agent.store.workspace_recommendations(project_root=root, include_dismissed=False, limit=100)
    recent_events = agent.store.workspace_events(project_root=root, limit=80)
    snapshot = snapshot.model_copy(
        update={
            "recommendations": persisted_recommendations,
            "recent_events": recent_events,
            "scheduled_jobs": workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root)),
        }
    )
    agent.store.save_workspace_operations_snapshot(snapshot)
    return snapshot


def _workspace_operations_snapshot(root: Path, *, rebuild: bool = False) -> WorkspaceOperationsSnapshot:
    if not rebuild:
        cached = agent.store.workspace_operations_snapshot(project_root=root)
        if cached is not None:
            return cached
    return _build_workspace_operations(root)


def _run_scheduled_intelligence_jobs(root: Path, request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
    existing_jobs = workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root))
    selected_ids = set(request.job_ids or [item.id for item in existing_jobs])
    jobs_by_id = {item.id: item for item in existing_jobs}
    warnings: list[str] = []
    completed: list[ScheduledIntelligenceJob] = []

    for job_id in selected_ids:
        job = jobs_by_id.get(job_id)
        if job is None:
            warnings.append(f"Unknown scheduled intelligence job: {job_id}")
            continue
        summary = "Workspace intelligence scan completed."
        status = "completed"
        try:
            if job.kind in {"indexing", "architecture"}:
                _build_project_intelligence(root)
                summary = "Project Intelligence was refreshed."
            elif job.kind == "telemetry":
                agent.store.refresh_telemetry_snapshot(project_root=root)
                summary = "Telemetry snapshot was refreshed."
            elif job.kind == "validation" and not request.allow_commands:
                status = "skipped"
                summary = "Validation snapshot skipped command execution because allow_commands was false."
            elif job.kind == "validation":
                validation = agent._run_validation(root, lambda *_args, **_kwargs: None, manual=True)
                summary = (
                    f"Validation command `{validation.command}` exited with {validation.exit_code}."
                    if validation
                    else "No validation command was available."
                )
            elif job.kind == "benchmark":
                model_benchmarks.snapshot()
                summary = "Benchmark metadata was inspected; no benchmark command was run automatically."
            elif job.kind == "memory":
                summary = "Workspace operations memory signals were summarized."
            elif job.kind == "dependency":
                summary = "Dependency manifests were inspected for drift and local freshness warnings."
        except Exception as exc:
            status = "failed"
            summary = f"{type(exc).__name__}: {exc}"
        record = workspace_operations.job_run_record(job, status=status, summary=summary)
        agent.store.record_scheduled_intelligence_job(project_root=root, job=record)
        completed.append(record)

    snapshot = _build_workspace_operations(root, refresh_project_intelligence=True)
    return ScheduledJobRunResponse(workspace_root=str(root), jobs=completed, snapshot=snapshot, warnings=warnings)


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


_FEEDBACK_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        re.compile(
            r"(?i)\b((?:api[_-]?key|secret|token|password|passwd|pwd|authorization)\s*[:=]\s*)"
            r"(['\"]?)[^\s'\",;]+",
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)([?&](?:token|key|secret|password|signature)=)[^&\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[REDACTED_EMAIL]"),
)


def refresh_runtime() -> None:
    global settings, workspace_manager, agent, creative_media, model_registry, model_manager, model_benchmarks, workspace_operations, distributed_runtime, adaptive_intelligence, productization, ecosystem, autonomous_engineering, unified_runtime, operating_environment, unified_context, continuity, platform_discipline
    clear_settings_cache()
    _invalidate_workspace_caches()
    settings = get_settings()
    workspace_manager = WorkspaceManager(PROJECT_ROOT, settings)
    agent = AgentEngine(PROJECT_ROOT, settings)
    creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
    model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
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
    distributed_runtime.ensure_local_worker(agent.store, root)
    return agent.store.runtime_workers()


def _runtime_jobs(
    root: Path,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[ExecutionQueueItem]:
    return agent.store.execution_jobs(project_root=root, status=status, limit=limit)


def _runtime_audit_events(
    *,
    worker_id: str = "",
    job_id: str = "",
    limit: int = 100,
) -> list[WorkerAuditEvent]:
    return agent.store.worker_audit_events(worker_id=worker_id, job_id=job_id, limit=limit)


def _record_runtime_audit(event: WorkerAuditEvent) -> WorkerAuditEvent:
    return agent.store.record_worker_audit_event(event)


def _runtime_snapshot(root: Path, routing: HybridRouteDecision | None = None) -> DistributedRuntimeSnapshot:
    workers = _runtime_workers(root)
    jobs = _runtime_jobs(root, limit=200)
    audit_events = _runtime_audit_events(limit=120)
    sync_manifests = agent.store.workspace_sync_manifests(project_root=root, limit=20)
    return distributed_runtime.snapshot(
        workers=workers,
        jobs=jobs,
        audit_events=audit_events,
        sync_manifests=sync_manifests,
        routing=routing,
    )


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
    wanted = set(sections or ["task_history", "checkpoints", "project_memory", "architecture_maps", "validation_profiles", "settings"])
    payload: dict[str, Any] = {}
    if "task_history" in wanted:
        payload["task_history"] = _dump_runtime_payload(agent.store.list_tasks(project_root=root, limit=100, include_subtasks=True))
    if "checkpoints" in wanted:
        payload["checkpoints"] = _dump_runtime_payload(workspace_manager.list_checkpoints(root, limit=50))
    if "project_memory" in wanted:
        payload["project_memory"] = _dump_runtime_payload(agent.store.project_memory(project_root=root, limit=200))
    if "architecture_maps" in wanted:
        intelligence = agent.store.project_intelligence(project_root=root)
        payload["architecture_maps"] = _dump_runtime_payload(intelligence.architecture if intelligence else {})
        payload["project_profile"] = _dump_runtime_payload(intelligence.profile if intelligence else {})
    if "validation_profiles" in wanted:
        payload["validation_profiles"] = _dump_runtime_payload(agent.validation.profile_snapshot(root))
    if "settings" in wanted:
        payload["settings"] = {
            "model_api": settings.aegis_model_api,
            "model_endpoint": settings.aegis_model_endpoint,
            "model_name": settings.aegis_model_name,
            "approval_tier": settings.approval_tier,
            "sandbox_profile": settings.sandbox_profile,
            "router_execution_enabled": settings.aegis_router_execution_enabled,
            "shared_workspace_mode": settings.aegis_shared_workspace_mode,
        }
    return payload


def _save_remote_sync_manifest(root: Path, request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
    payload = _remote_sync_payload(root, request.sections)
    manifest = distributed_runtime.sync_manifest(
        workspace_root=root,
        sections=request.sections,
        encrypted=request.encrypted,
        payload=payload,
    )
    saved = agent.store.save_workspace_sync_manifest(manifest)
    _record_runtime_audit(
        distributed_runtime.audit_event(
            event_type="sync.manifest.created",
            detail=f"Workspace sync manifest {saved.id} captured {len(saved.included_sections)} section(s).",
            metadata={"workspace_root": str(root), "encrypted": saved.encrypted, "manifest_hash": saved.manifest_hash},
        )
    )
    return saved


def _run_command_job(job: ExecutionQueueItem, root: Path, *, allow_commands: bool) -> tuple[str, str, dict[str, Any]]:
    command = str(job.payload.get("command") or "").strip()
    if not allow_commands:
        return "blocked", "Command execution was not allowed for this dispatch.", {"allow_commands": False}

    if command:
        result = agent.commands.run(command, root, sandbox_profile=job.sandbox_profile)
        payload = {
            "command": result.command,
            "cwd": result.cwd,
            "allowed": result.allowed,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "reason": result.reason,
        }
        if job.task_id:
            agent.store.record_event(
                job.task_id,
                kind="command",
                title="Distributed command executed",
                status="ok" if result.ok else "error" if result.allowed else "warning",
                detail=result.reason,
                payload=payload,
            )
        if result.ok:
            return "succeeded", f"Command `{command}` exited with 0.", payload
        if not result.allowed:
            return "blocked", result.reason, payload
        return "failed", f"Command `{command}` exited with {result.exit_code}.", payload

    validation = agent._run_validation(root, lambda *_args, **_kwargs: None, manual=True)
    if validation is None:
        return "blocked", "No validation command was available for this workspace.", {}
    payload = validation.model_dump(mode="json")
    if validation.exit_code == 0:
        return "succeeded", f"Validation command `{validation.command}` exited with 0.", payload
    if not validation.allowed:
        return "blocked", validation.summary or validation.reason, payload
    return "failed", f"Validation command `{validation.command}` exited with {validation.exit_code}.", payload


def _queue_repair_after_validation_failure(job: ExecutionQueueItem, root: Path, summary: str) -> ExecutionQueueItem:
    repair = distributed_runtime.create_queue_item(
        ExecutionQueueCreateRequest(
            workspace_root=str(root),
            task_id=job.task_id,
            kind="repair",
            title=f"Repair after {job.title or job.kind}",
            user_goal=f"Repair validation failure from {job.id}.",
            priority=max(0, job.priority - 1),
            max_attempts=1,
            permission_scope="repair",
            sandbox_profile=job.sandbox_profile,
            payload={"source_validation_job_id": job.id, "failure_summary": summary},
        ),
        root,
    )
    created = agent.store.create_execution_job(repair)
    _record_runtime_audit(
        distributed_runtime.audit_event(
            job_id=created.id,
            event_type="queue.repair.created",
            detail=f"Repair job was queued after validation failure in {job.id}.",
            metadata={"source_job_id": job.id, "task_id": job.task_id},
        )
    )
    if job.task_id:
        agent.store.record_event(
            job.task_id,
            kind="repair",
            title="Repair queued",
            status="warning",
            detail=summary,
            payload={"source_job_id": job.id, "repair_job_id": created.id},
        )
    return created


def _execute_runtime_job(job: ExecutionQueueItem, worker: WorkerRuntimeInfo, *, allow_commands: bool) -> tuple[ExecutionQueueItem, list[WorkerAuditEvent]]:
    started_at = time.monotonic()
    events: list[WorkerAuditEvent] = []
    root = _resolve_workspace_or_400(job.workspace_root)
    assigned = agent.store.update_execution_job(
        job.id,
        status="running",
        assigned_worker_id=worker.worker_id,
        attempts=job.attempts + 1,
    )
    agent.store.heartbeat_runtime_worker(worker.worker_id, status="busy", current_jobs=worker.current_jobs + 1)
    start_event = _record_runtime_audit(
        distributed_runtime.audit_event(
            worker_id=worker.worker_id,
            job_id=job.id,
            event_type="job.started",
            detail=f"{worker.name} started {assigned.kind} job {assigned.id}.",
            metadata={"kind": assigned.kind, "workspace_root": str(root), "sandbox_profile": assigned.sandbox_profile},
        )
    )
    events.append(start_event)
    _task_transition_or_event(
        assigned.task_id,
        "running",
        title="Distributed job started",
        detail=f"{worker.name} started {assigned.kind} job {assigned.id}.",
        payload={"job_id": assigned.id, "worker_id": worker.worker_id, "kind": assigned.kind},
    )
    if assigned.kind == "validation":
        _task_transition_or_event(
            assigned.task_id,
            "validating",
            title="Distributed validation started",
            detail=f"{worker.name} started validation job {assigned.id}.",
            payload={"job_id": assigned.id, "worker_id": worker.worker_id},
        )

    status = "succeeded"
    summary = f"{assigned.kind.title()} job completed."
    payload: dict[str, Any] = {}
    try:
        if assigned.kind in {"validation", "build"}:
            status, summary, payload = _run_command_job(assigned, root, allow_commands=allow_commands)
            if assigned.kind == "validation" and status == "failed" and assigned.task_id:
                _task_transition_or_event(
                    assigned.task_id,
                    "repairing",
                    title="Validation failed",
                    detail=summary,
                    error_summary=summary,
                    payload={"job_id": assigned.id, "validation": payload},
                )
                _queue_repair_after_validation_failure(assigned, root, summary)
        elif assigned.kind == "indexing":
            intelligence = _build_project_intelligence(root)
            summary = f"Project Intelligence indexed {len(intelligence.file_importance)} important file(s)."
            payload = {
                "last_indexed_at": intelligence.profile.last_indexed_at,
                "important_files": [item.path for item in intelligence.file_importance[:12]],
            }
        elif assigned.kind == "telemetry":
            snapshot = agent.store.refresh_telemetry_snapshot(project_root=root)
            summary = "Telemetry snapshot refreshed."
            payload = {
                "model_attempt_count": snapshot.route_quality.overview.model_attempt_count,
                "feedback_count": snapshot.feedback.summary.feedback_count,
                "reliability_score": snapshot.route_quality.overview.reliability_score,
            }
        elif assigned.kind == "benchmark":
            snapshot = model_benchmarks.snapshot()
            summary = "Benchmark state inspected without starting a model benchmark run."
            best_model_name = snapshot.provider_scores[0].model_name if snapshot.provider_scores else ""
            payload = {"best_model_name": best_model_name, "provider_count": len(snapshot.provider_scores)}
        elif assigned.kind == "sync":
            manifest = _save_remote_sync_manifest(root, RemoteWorkspaceSyncRequest(workspace_root=str(root), sections=[], encrypted=True))
            summary = f"Workspace sync manifest {manifest.id} was created."
            payload = manifest.model_dump(mode="json")
        elif assigned.kind == "repair":
            status = "blocked"
            summary = "Repair jobs are recorded and require the task runtime to make code changes with normal approval and checkpoint rules."
            payload = {"source_validation_job_id": assigned.payload.get("source_validation_job_id", "")}
        else:
            summary = "Task job recorded by distributed runtime; no file changes were applied by the queue worker."
            payload = {"local_first": True, "file_changes_applied": False}
    except Exception as exc:
        status = "failed"
        summary = f"{type(exc).__name__}: {exc}"
        payload = {"exception": type(exc).__name__}

    final = agent.store.update_execution_job(
        assigned.id,
        status=status,
        error_summary=summary if status in {"failed", "blocked"} else "",
        result_summary=summary if status == "succeeded" else "",
    )
    agent.store.complete_execution_job_for_worker(worker.worker_id, failed=status != "succeeded", latency_ms=(time.monotonic() - started_at) * 1000)
    finish_event = _record_runtime_audit(
        distributed_runtime.audit_event(
            worker_id=worker.worker_id,
            job_id=assigned.id,
            event_type="job.finished",
            status="ok" if status == "succeeded" else "error" if status == "failed" else "warning",
            detail=summary,
            metadata={"status": status, "payload": payload},
        )
    )
    events.append(finish_event)
    if final.task_id and not (final.kind == "validation" and status == "failed"):
        next_task_status = "completed" if status == "succeeded" else "failed" if status == "failed" else "blocked"
        _task_transition_or_event(
            final.task_id,
            next_task_status,
            title="Distributed job finished",
            detail=summary,
            error_summary=summary if next_task_status in {"failed", "blocked"} else "",
            final_summary=summary if next_task_status == "completed" else "",
            payload={"job_id": final.id, "worker_id": worker.worker_id, "status": status, "result": payload},
        )
    return final, events


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
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _structured_stream_intro(request: AgentRequest) -> str:
    mode = request.mode or "auto"
    parts = [
        f"I'm handling this as a structured {mode} task.",
        "I'll keep provider JSON internal and only stream safe progress here.",
    ]
    if request.apply_changes:
        parts.append("Auto Apply is enabled, so eligible low-risk file changes can be written after the draft is assembled.")
    if request.run_validation:
        parts.append("Validation is enabled, so I'll run the selected check after applicable changes are applied.")
    return " ".join(parts) + "\n\n"


def _structured_stream_summary(response: AgentResponse) -> str:
    details: list[str] = []
    if response.changes:
        details.append(f"prepared {len(response.changes)} file change(s)")
    if response.applied:
        details.append(f"applied {len(response.applied)} file change(s)")
    if response.validation is not None:
        status = "passed" if response.validation.exit_code == 0 else "needs attention"
        details.append(f"validation {status}")
    if response.warnings:
        details.append(f"{len(response.warnings)} warning(s)")
    if not details:
        details.append("prepared a structured response")
    return "Aegis " + ", ".join(details) + ". Finalizing the response now.\n\n"


def _structured_stream_reconciliation(response: AgentResponse, *, preview_was_streamed: bool) -> str:
    if not preview_was_streamed:
        return ""

    warnings_text = "\n".join(response.warnings).lower()
    fallback_markers = (
        "deterministic fallback",
        "deterministic starter generator",
        "model returned no file changes",
        "model returned no usable answer",
        "direct chat fallback",
    )
    if any(marker in warnings_text for marker in fallback_markers):
        return (
            "The live preview came from the model draft, but Aegis replaced it with a safer final response "
            "because that draft did not produce usable workspace changes."
        )

    attempts = response.model_attempts
    first_success_index = next(
        (index for index, attempt in enumerate(attempts) if attempt.status == "succeeded"),
        None,
    )
    if first_success_index is not None and first_success_index > 0:
        prior_attempts = attempts[:first_success_index]
        if any(attempt.status in {"failed", "skipped"} for attempt in prior_attempts):
            return (
                "The live preview came from an earlier provider attempt. Aegis used the later successful "
                "provider response as the final structured answer."
            )

    return ""


def _response_with_reconciliation(response: AgentResponse, notice: str) -> AgentResponse:
    if not notice:
        return response

    warnings = list(response.warnings)
    if notice not in warnings:
        warnings.append(notice)

    reply = response.reply.strip()
    if notice not in reply:
        reply = f"{reply}\n\nNote: {notice}" if reply else f"Note: {notice}"

    return response.model_copy(update={"reply": reply, "warnings": warnings})


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
            if isinstance(event, str):
                event = {"delta": event}
            if not isinstance(event, dict):
                return

            delta = str(event.get("delta") or "")
            preview_action = str(event.get("preview_action") or "append").strip() or "append"
            if preview_action == "append" and delta:
                preview_delta_count += 1
            if preview_action == "append" and not delta:
                return

            preview_queue.put_nowait(
                {
                    "type": "delta",
                    "delta": delta,
                    "stream_mode": stream_mode,
                    "source": "structured_reply_preview",
                    "preview_action": preview_action,
                    "preview_attempt": event.get("preview_attempt"),
                    "provider_id": event.get("provider_id") or "",
                    "provider_label": event.get("provider_label") or "",
                    "provider_api": event.get("provider_api") or "",
                    "model": event.get("model") or "",
                    "message": event.get("message") or "",
                }
            )

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


async def config_snapshot() -> AppConfig:
    default_mode = settings.default_mode.strip().lower()
    if default_mode not in {"build", "develop", "review", "chat"}:
        default_mode = "build"

    model_status = await agent.model_status()
    default_workspace = _resolve_workspace_path_for_config(None)

    return AppConfig(
        assistant_name=settings.aegis_assistant_name,
        assistant_mission=settings.aegis_assistant_mission,
        default_mode=default_mode,  # type: ignore[arg-type]
        modes=[ModeOption(id=mode, label=label, description=description) for mode, label, description in MODE_OPTIONS],
        default_workspace=str(default_workspace),
        engine=f"Aegis Core / {settings.aegis_model_name}",
        engine_ready=True,
        engine_message="The local Aegis backend is ready. No external AI provider is required.",
        model_name=settings.aegis_model_name,
        model_endpoint=settings.aegis_model_endpoint,
        model_api=settings.aegis_model_api,
        model_ready=model_status.ready,
        model_message=model_status.message,
        database_path=str(_resolve_database_path(settings.aegis_database_path)),
        command_allowlist=settings.aegis_command_allowlist,
        command_timeout_seconds=settings.aegis_command_timeout_seconds,
        auto_run_validation=settings.aegis_auto_run_validation,
        router_execution_enabled=settings.aegis_router_execution_enabled,
        shared_workspace_mode=settings.aegis_shared_workspace_mode,
        feedback_capture_excerpts=settings.aegis_feedback_capture_excerpts,
        feedback_redaction_enabled=settings.aegis_feedback_redaction_enabled,
        feedback_max_excerpt_chars=max(0, min(2000, settings.aegis_feedback_max_excerpt_chars)),
        feedback_hash_content=settings.aegis_feedback_hash_content,
        env_exists=has_env_file(),
    )


async def runtime_health_snapshot() -> RuntimeHealthResponse:
    model_status = await agent.model_status()
    default_workspace = _resolve_workspace_path_for_config(None)
    registry = model_registry.snapshot()
    provider_count = len(registry.providers)
    configured_provider_count = sum(1 for provider in registry.providers if provider.configured)
    enabled_provider_count = sum(1 for provider in registry.providers if provider.enabled)
    recommendations: list[str] = []
    if not model_status.ready:
        recommendations.append(model_status.message or "The active model provider is not reporting ready.")
    if configured_provider_count == 0:
        recommendations.append("No configured model providers are registered; configure at least one local or cloud provider.")
    if not registry.router_enabled:
        recommendations.append("Model routing is disabled; enable routing when fallback and role-based selection should be active.")
    if not settings.aegis_router_execution_enabled:
        recommendations.append("Router execution is disabled in settings; routed prompts will not execute provider chains.")

    return RuntimeHealthResponse(
        ok=True,
        ready=True,
        status="ready" if model_status.ready else "degraded",
        app=app.title,
        version=app.version,
        engine=f"Aegis Core / {settings.aegis_model_name}",
        engine_ready=True,
        engine_message="The Aegis backend process is ready.",
        model_name=settings.aegis_model_name,
        model_api=settings.aegis_model_api,
        model_endpoint=settings.aegis_model_endpoint,
        model_ready=model_status.ready,
        model_message=model_status.message,
        project_root=str(PROJECT_ROOT),
        workspace_root=str(default_workspace),
        database_path=str(_resolve_database_path(settings.aegis_database_path)),
        env_exists=has_env_file(),
        router_execution_enabled=settings.aegis_router_execution_enabled,
        router_enabled=registry.router_enabled,
        fallback_supported=registry.fallback_supported,
        provider_count=provider_count,
        configured_provider_count=configured_provider_count,
        enabled_provider_count=enabled_provider_count,
        role_count=len(registry.roles),
        recommendations=recommendations,
    )


def _auth_response(session) -> AuthSessionResponse:
    return AuthSessionResponse(token=session.token, user=session.user, expires_at=session.expires_at)


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def _session_from_authorization(authorization: str | None) -> tuple[Any, str]:
    token = _extract_bearer_token(authorization)
    session = account_store.user_for_token(token)
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
    return session


@app.post("/api/auth/register", response_model=AuthSessionResponse)
async def register_account(request: AuthRegisterRequest) -> AuthSessionResponse:
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    try:
        user = account_store.create_account(name=request.name, email=request.email, password=request.password)
        session = account_store.create_session(user, remember_me=True)
        return _auth_response(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login", response_model=AuthSessionResponse)
async def login_account(request: AuthLoginRequest) -> AuthSessionResponse:
    try:
        session = account_store.authenticate(
            email=request.email,
            password=request.password,
            remember_me=request.remember_me,
        )
        return _auth_response(session)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me", response_model=AuthSessionResponse)
async def current_account(authorization: str | None = Header(default=None)) -> AuthSessionResponse:
    user, expires_at = _session_from_authorization(authorization)
    return AuthSessionResponse(token="", user=user, expires_at=expires_at)


@app.post("/api/auth/logout", response_model=AuthMessageResponse)
async def logout_account(authorization: str | None = Header(default=None)) -> AuthMessageResponse:
    token = _extract_bearer_token(authorization)
    account_store.delete_session(token)
    return AuthMessageResponse(message="Signed out.")


@app.post("/api/auth/forgot-password", response_model=AuthMessageResponse)
async def forgot_password(request: AuthForgotPasswordRequest) -> AuthMessageResponse:
    # The local-first runtime has no outbound email channel yet, so this endpoint
    # intentionally avoids revealing whether an account exists.
    _ = request.email
    return AuthMessageResponse(message="If an account exists, password recovery instructions will be sent when email is configured.")


@app.get("/health", response_model=RuntimeHealthResponse, include_in_schema=False)
@app.get("/api/health", response_model=RuntimeHealthResponse)
async def health() -> RuntimeHealthResponse:
    return await runtime_health_snapshot()


@app.get("/ready", response_model=RuntimeHealthResponse, include_in_schema=False)
@app.get("/api/ready", response_model=RuntimeHealthResponse)
async def ready() -> RuntimeHealthResponse:
    return await runtime_health_snapshot()


@app.get("/api/unified-runtime", response_model=UnifiedRuntimeSnapshot)
async def unified_runtime_status(workspace_root: str | None = Query(default=None)) -> UnifiedRuntimeSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _unified_runtime_snapshot(root)


@app.get("/api/operating-environment", response_model=OperatingEnvironmentSnapshot)
async def operating_environment_status(workspace_root: str | None = Query(default=None)) -> OperatingEnvironmentSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _operating_environment_snapshot(root)


@app.post("/api/operating-environment/actions/preview", response_model=OperatingEnvironmentActionResponse)
async def operating_environment_action_preview(
    request: OperatingEnvironmentActionRequest,
) -> OperatingEnvironmentActionResponse:
    if request.workspace_root:
        _resolve_workspace_or_400(request.workspace_root)
    return operating_environment.preview_action(request)


@app.get("/api/unified-context", response_model=UnifiedContextSnapshot)
async def unified_context_status(workspace_root: str | None = Query(default=None)) -> UnifiedContextSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _unified_context_snapshot(root)


@app.post("/api/unified-context/search", response_model=UnifiedContextSearchResponse)
async def unified_context_search(request: UnifiedContextSearchRequest) -> UnifiedContextSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    snapshot = _unified_context_snapshot(root)
    return unified_context.search(snapshot, request.model_copy(update={"workspace_root": str(root)}))


@app.post("/api/global-command/preview", response_model=GlobalCommandResponse)
async def global_command_preview(request: GlobalCommandRequest) -> GlobalCommandResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _global_command_preview(root, request)


@app.post("/api/global-command/submit", response_model=GlobalCommandResponse)
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


@app.get("/api/continuity", response_model=AegisContinuitySnapshot)
async def continuity_status(workspace_root: str | None = Query(default=None)) -> AegisContinuitySnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _continuity_snapshot(root)


@app.post("/api/continuity/timeline/search", response_model=TimelineSearchResponse)
async def continuity_timeline_search(request: TimelineSearchRequest) -> TimelineSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    snapshot = _continuity_snapshot(root)
    return continuity.search_timeline(snapshot, request.model_copy(update={"workspace_root": str(root)}))


@app.get("/api/platform-discipline", response_model=PlatformDisciplineSnapshot)
async def platform_discipline_status(workspace_root: str | None = Query(default=None)) -> PlatformDisciplineSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _platform_discipline_snapshot(root)


@app.get("/api/config", response_model=AppConfig)
async def config() -> AppConfig:
    return await config_snapshot()


@app.get("/api/models", response_model=ModelInventoryResponse)
async def models() -> ModelInventoryResponse:
    inventory = await agent.model_inventory()
    registry = model_registry.snapshot()
    return ModelInventoryResponse(
        active_model=inventory.active_model,
        active_api=inventory.active_api,
        active_endpoint=inventory.active_endpoint,
        router_enabled=registry.router_enabled,
        fallback_supported=registry.fallback_supported,
        message=inventory.message,
        models=[
            ModelInfo(
                id=item.id,
                name=item.name,
                provider=item.provider,
                api=item.api,
                endpoint=item.endpoint,
                local=item.local,
                configured=item.configured,
                available=item.available,
                ready=item.ready,
                message=item.message,
                size=item.size,
                modified_at=item.modified_at,
                capabilities=ModelCapabilities(**(item.capabilities or {})),
            )
            for item in inventory.models
        ],
    )


@app.get("/api/model-registry", response_model=ModelRegistryResponse)
async def model_registry_snapshot() -> ModelRegistryResponse:
    return model_registry.snapshot()


@app.get("/api/model-registry/audit", response_model=ModelRegistryAuditResponse)
async def model_registry_audit(workspace_root: str | None = Query(default=None)) -> ModelRegistryAuditResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return model_registry.audit(
        model_attempts=agent.store.recent_model_attempts(project_root=root, limit=200),
        route_health=agent.store.route_health_signals(project_root=root, limit=200),
    )


@app.post("/api/model-registry/providers", response_model=ModelRegistryResponse)
async def upsert_model_registry_provider(request: ModelRegistryProviderUpsertRequest) -> ModelRegistryResponse:
    try:
        return model_registry.upsert_provider(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/model-registry/providers/{provider_id}", response_model=ModelRegistryResponse)
async def delete_model_registry_provider(provider_id: str) -> ModelRegistryResponse:
    try:
        return model_registry.delete_provider(provider_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model registry provider not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-registry/apply-benchmark-winners", response_model=ModelRegistryResponse)
async def apply_benchmark_winners_to_model_registry(
    workspace_root: str | None = Query(default=None),
) -> ModelRegistryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    try:
        route_health = agent.store.route_health_signals(project_root=root, limit=200)
        return model_registry.apply_benchmark_winners(
            model_benchmarks.snapshot().provider_scores,
            route_health=route_health,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-registry/benchmark-winners-preview", response_model=ModelRegistryBenchmarkPreviewResponse)
async def preview_benchmark_winners_for_model_registry(
    workspace_root: str | None = Query(default=None),
) -> ModelRegistryBenchmarkPreviewResponse:
    root = _resolve_workspace_or_400(workspace_root)
    route_health = agent.store.route_health_signals(project_root=root, limit=200)
    return model_registry.preview_benchmark_winners(
        model_benchmarks.snapshot().provider_scores,
        route_health=route_health,
    )


@app.post("/api/model-registry/apply-policy-diff", response_model=ModelRegistryResponse)
async def apply_route_policy_diff_to_model_registry(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    min_attempts: int = Query(default=3, ge=1, le=50),
    min_confidence: float = Query(default=0.55, ge=0.0, le=1.0),
    allow_high_risk: bool = Query(default=False),
) -> ModelRegistryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    diff = agent.store.route_policy_diff(
        project_root=root,
        limit=limit,
        use_snapshot=True,
        stale_after_seconds=900,
        min_attempts=min_attempts,
    )
    return model_registry.apply_policy_diff(
        diff,
        min_confidence=min_confidence,
        allow_high_risk=allow_high_risk,
    )


@app.get("/api/model-registry/checkpoints", response_model=ModelRegistryCheckpointListResponse)
async def model_registry_checkpoints(
    limit: int = Query(default=20, ge=1, le=100),
) -> ModelRegistryCheckpointListResponse:
    return model_registry.checkpoints(limit=limit)


@app.post("/api/model-registry/checkpoints", response_model=ModelRegistryCheckpointInfo)
async def create_model_registry_checkpoint(
    request: ModelRegistryCheckpointCreateRequest,
) -> ModelRegistryCheckpointInfo:
    try:
        return model_registry.create_checkpoint(request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-registry/checkpoints/{checkpoint_id}/diff", response_model=ModelRegistryCheckpointDiffResponse)
async def model_registry_checkpoint_diff(checkpoint_id: str) -> ModelRegistryCheckpointDiffResponse:
    try:
        return model_registry.checkpoint_diff(checkpoint_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model registry checkpoint not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-registry/checkpoints/{checkpoint_id}/restore", response_model=ModelRegistryResponse)
async def restore_model_registry_checkpoint(checkpoint_id: str) -> ModelRegistryResponse:
    try:
        return model_registry.restore_checkpoint(checkpoint_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model registry checkpoint not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-manager", response_model=ModelManagerResponse)
async def model_manager_snapshot(
    minimum_free_gb: float = Query(default=24.0, ge=0.0, le=500.0),
) -> ModelManagerResponse:
    return model_manager.snapshot(minimum_free_gb=minimum_free_gb)


@app.post("/api/model-manager/pull", response_model=ModelOperationInfo)
async def pull_model(request: ModelPullRequest) -> ModelOperationInfo:
    try:
        return model_manager.pull_model(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-manager/delete", response_model=ModelOperationInfo)
async def delete_local_model(request: ModelDeleteRequest) -> ModelOperationInfo:
    try:
        return model_manager.delete_model(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-benchmarks", response_model=ModelBenchmarkSnapshot)
async def model_benchmark_snapshot() -> ModelBenchmarkSnapshot:
    return model_benchmarks.snapshot()


@app.post("/api/model-benchmarks/run", response_model=ModelBenchmarkSnapshot)
async def run_model_benchmarks(request: ModelBenchmarkRunRequest) -> ModelBenchmarkSnapshot:
    try:
        return await model_benchmarks.run(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-benchmarks/jobs", response_model=list[ModelBenchmarkJobInfo])
async def model_benchmark_jobs() -> list[ModelBenchmarkJobInfo]:
    return model_benchmarks.jobs()


@app.post("/api/model-benchmarks/jobs", response_model=ModelBenchmarkJobInfo)
async def start_model_benchmark_job(request: ModelBenchmarkRunRequest) -> ModelBenchmarkJobInfo:
    try:
        return model_benchmarks.start_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-benchmarks/jobs/{job_id}/cancel", response_model=ModelBenchmarkJobInfo)
async def cancel_model_benchmark_job(job_id: str) -> ModelBenchmarkJobInfo:
    try:
        return model_benchmarks.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/media/capabilities", response_model=MediaCapabilitiesResponse)
async def media_capabilities() -> MediaCapabilitiesResponse:
    return creative_media.capabilities()


@app.get("/api/creative-studio", response_model=MediaCapabilitiesResponse)
async def creative_studio_capabilities() -> MediaCapabilitiesResponse:
    return creative_media.capabilities()


@app.get("/api/media/providers", response_model=list[MediaProviderInfo])
async def media_providers() -> list[MediaProviderInfo]:
    return creative_media.providers()


@app.get("/api/creative-studio/providers", response_model=list[MediaProviderInfo])
async def creative_studio_providers() -> list[MediaProviderInfo]:
    return creative_media.providers()


@app.get("/api/media/prompt-presets", response_model=list[MediaPromptPreset])
async def media_prompt_presets() -> list[MediaPromptPreset]:
    return creative_media.prompt_presets()


@app.get("/api/creative-studio/prompt-presets", response_model=list[MediaPromptPreset])
async def creative_studio_prompt_presets() -> list[MediaPromptPreset]:
    return creative_media.prompt_presets()


@app.get("/api/media/jobs", response_model=list[MediaJobResponse])
async def list_media_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    kind: str = Query(default=""),
) -> list[MediaJobResponse]:
    return creative_media.list_jobs(limit=limit, kind=kind)


@app.get("/api/creative-studio/jobs", response_model=list[MediaJobResponse])
async def list_creative_studio_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    kind: str = Query(default=""),
) -> list[MediaJobResponse]:
    return creative_media.list_jobs(limit=limit, kind=kind)


@app.get("/api/media/jobs/{job_id}", response_model=MediaJobResponse)
async def get_media_job(job_id: str) -> MediaJobResponse:
    try:
        return creative_media.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="media job not found") from exc


@app.get("/api/creative-studio/jobs/{job_id}", response_model=MediaJobResponse)
async def get_creative_studio_job(job_id: str) -> MediaJobResponse:
    return await get_media_job(job_id)


@app.post("/api/media/jobs", response_model=MediaJobResponse)
async def create_media_job(request: MediaCreativeRequest) -> MediaJobResponse:
    try:
        return creative_media.create_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/creative-studio/jobs", response_model=MediaJobResponse)
async def create_creative_studio_job(request: MediaCreativeRequest) -> MediaJobResponse:
    return await create_media_job(request)


@app.post("/api/media/jobs/{job_id}/cancel", response_model=MediaJobResponse)
async def cancel_media_job(job_id: str) -> MediaJobResponse:
    try:
        return creative_media.cancel_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="media job not found") from exc


@app.post("/api/creative-studio/jobs/{job_id}/cancel", response_model=MediaJobResponse)
async def cancel_creative_studio_job(job_id: str) -> MediaJobResponse:
    return await cancel_media_job(job_id)


@app.get("/api/media/assets", response_model=MediaAssetLibraryResponse)
async def media_asset_library(
    limit: int = Query(default=100, ge=1, le=500),
    kind: str = Query(default=""),
    format: str = Query(default=""),
) -> MediaAssetLibraryResponse:
    return creative_media.asset_library(limit=limit, kind=kind, fmt=format)


@app.get("/api/creative-studio/assets", response_model=MediaAssetLibraryResponse)
async def creative_studio_asset_library(
    limit: int = Query(default=100, ge=1, le=500),
    kind: str = Query(default=""),
    format: str = Query(default=""),
) -> MediaAssetLibraryResponse:
    return creative_media.asset_library(limit=limit, kind=kind, fmt=format)


@app.get("/api/creative-studio/assets/file")
async def creative_studio_asset_file(path: str = Query(min_length=1)) -> FileResponse:
    requested = Path(path).resolve()
    base = creative_media.base_dir.resolve()
    try:
        requested.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="asset path is outside the creative library") from exc
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(requested)


@app.post("/api/media/jobs/{job_id}/export", response_model=MediaExportResponse)
async def export_media_job(job_id: str, request: MediaExportRequest) -> MediaExportResponse:
    try:
        return creative_media.export_job(job_id, request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="media job not found") from exc


@app.post("/api/creative-studio/jobs/{job_id}/export", response_model=MediaExportResponse)
async def export_creative_studio_job(job_id: str, request: MediaExportRequest) -> MediaExportResponse:
    return await export_media_job(job_id, request)


@app.post("/api/config", response_model=AppConfig)
async def save_config(request: ConfigUpdateRequest) -> AppConfig:
    assistant_name = request.assistant_name if request.assistant_name is not None else settings.aegis_assistant_name
    assistant_mission = (
        request.assistant_mission if request.assistant_mission is not None else settings.aegis_assistant_mission
    )
    default_mode = request.default_mode if request.default_mode is not None else settings.default_mode
    if default_mode not in {"build", "develop", "review", "chat"}:
        default_mode = "build"
    default_workspace = (
        request.default_workspace if request.default_workspace is not None else settings.default_workspace
    )
    model_api = request.model_api if request.model_api is not None else settings.aegis_model_api
    model_endpoint = request.model_endpoint if request.model_endpoint is not None else settings.aegis_model_endpoint
    model_name = request.model_name if request.model_name is not None else settings.aegis_model_name
    command_allowlist = (
        request.command_allowlist if request.command_allowlist is not None else settings.aegis_command_allowlist
    )
    command_timeout_seconds = (
        request.command_timeout_seconds
        if request.command_timeout_seconds is not None
        else settings.aegis_command_timeout_seconds
    )
    auto_run_validation = (
        request.auto_run_validation
        if request.auto_run_validation is not None
        else settings.aegis_auto_run_validation
    )
    shared_workspace_mode = (
        request.shared_workspace_mode
        if request.shared_workspace_mode is not None
        else settings.aegis_shared_workspace_mode
    )
    feedback_capture_excerpts = (
        request.feedback_capture_excerpts
        if request.feedback_capture_excerpts is not None
        else settings.aegis_feedback_capture_excerpts
    )
    feedback_redaction_enabled = (
        request.feedback_redaction_enabled
        if request.feedback_redaction_enabled is not None
        else settings.aegis_feedback_redaction_enabled
    )
    feedback_max_excerpt_chars = (
        request.feedback_max_excerpt_chars
        if request.feedback_max_excerpt_chars is not None
        else settings.aegis_feedback_max_excerpt_chars
    )
    feedback_hash_content = (
        request.feedback_hash_content
        if request.feedback_hash_content is not None
        else settings.aegis_feedback_hash_content
    )
    mission = " ".join(part.strip() for part in assistant_mission.splitlines() if part.strip())
    update_env(
        {
            "AEGIS_ASSISTANT_NAME": assistant_name.strip(),
            "AEGIS_ASSISTANT_MISSION": mission or assistant_mission.strip(),
            "DEFAULT_MODE": default_mode,
            "DEFAULT_WORKSPACE": default_workspace.strip(),
            "AEGIS_MODEL_API": model_api.strip().lower(),
            "AEGIS_MODEL_ENDPOINT": model_endpoint.strip().rstrip("/"),
            "AEGIS_MODEL_NAME": model_name.strip(),
            "AEGIS_COMMAND_ALLOWLIST": command_allowlist.strip(),
            "AEGIS_COMMAND_TIMEOUT_SECONDS": str(command_timeout_seconds),
            "AEGIS_AUTO_RUN_VALIDATION": "true" if auto_run_validation else "false",
            "AEGIS_SHARED_WORKSPACE_MODE": "true" if shared_workspace_mode else "false",
            "AEGIS_FEEDBACK_CAPTURE_EXCERPTS": "true" if feedback_capture_excerpts else "false",
            "AEGIS_FEEDBACK_REDACTION_ENABLED": "true" if feedback_redaction_enabled else "false",
            "AEGIS_FEEDBACK_MAX_EXCERPT_CHARS": str(feedback_max_excerpt_chars),
            "AEGIS_FEEDBACK_HASH_CONTENT": "true" if feedback_hash_content else "false",
        }
    )
    refresh_runtime()
    return await config_snapshot()


@app.get("/api/files")
async def files(
    workspace_root: str | None = Query(default=None),
    max_files: int = Query(default=120, ge=1, le=5000),
) -> dict:
    root = _resolve_workspace_or_400(workspace_root)
    return {"workspace_root": str(root), "files": workspace_manager.scan(root, max_files=max_files)}


@app.get("/api/file")
async def file_content(
    path: str = Query(min_length=1),
    workspace_root: str | None = Query(default=None),
) -> dict:
    root = _resolve_workspace_or_400(workspace_root)
    try:
        content = workspace_manager.read_file(root, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workspace_root": str(root), "path": path, "content": content}


@app.get("/api/file/slice")
async def file_slice(
    path: str = Query(min_length=1),
    workspace_root: str | None = Query(default=None),
    start_line: int = Query(default=1, ge=1),
    max_lines: int = Query(default=400, ge=1, le=2000),
) -> dict:
    root = _resolve_workspace_or_400(workspace_root)
    try:
        payload = workspace_manager.read_file_slice(root, path, start_line=start_line, max_lines=max_lines)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workspace_root": str(root), **payload}


@app.get("/api/workspace/profile", response_model=WorkspaceProfileResponse)
async def workspace_profile(workspace_root: str | None = Query(default=None)) -> WorkspaceProfileResponse:
    root = _resolve_workspace_or_400(workspace_root)
    snapshot = _workspace_status_snapshot(root)
    manifest = snapshot.manifest
    dependency_profile = snapshot.dependency_profile
    instruction_status = snapshot.instruction_status
    validation_plan = snapshot.validation_plan
    readiness = snapshot.readiness
    recommendations: list[str] = []
    if manifest is None:
        recommendations.append("No .aegis/project.json manifest was found for this workspace.")
    else:
        if manifest.schema_version != "aegis.project.v1":
            recommendations.append("The project manifest schema is unknown; Aegis will treat it as advisory metadata.")
        if not manifest.validation_command:
            recommendations.append("The project manifest does not define a validation command.")
        if not manifest.install_command:
            recommendations.append("The project manifest does not define an install command.")
    if not dependency_profile.config_files:
        recommendations.append("No dependency or build manifest was detected, so validation planning will rely on file scanning and user guidance.")
    if not dependency_profile.validation_commands and (manifest is None or not manifest.validation_command):
        recommendations.append("No validation command was inferred for this workspace.")
    if instruction_status.open_items:
        recommendations.append(
            f"Instruction checkpoint has {instruction_status.open_items} open tracked item(s); autopilot should continue from the saved recommendation."
        )
    elif instruction_status.total_items:
        recommendations.append("Instruction checkpoint shows all tracked project items are currently complete.")
    if validation_plan.steps:
        recommendations.append(
            f"Validation plan has {len(validation_plan.steps)} step(s); use it as the repair loop source of truth before adding new scope."
        )
        last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
        if str(last_run.get("status") or "").lower() in {"failed", "blocked", "needs_attention"}:
            failed_step = str(last_run.get("failed_step") or "").strip()
            failed_hint = f" step {failed_step}" if failed_step else ""
            command = str(last_run.get("command") or validation_plan.validation_command or "").strip()
            command_hint = f" ({command})" if command else ""
            recommendations.append(f"Repair validation plan{failed_hint}{command_hint} before continuing autopilot expansion.")
    elif validation_plan.validation_command:
        recommendations.append("Validation plan has a command but no expanded steps; refresh project memory before long autopilot runs.")
    if readiness.next_action:
        recommendations.append(f"Readiness next action: {readiness.next_action}")
    try:
        _project_intelligence_snapshot(root)
    except Exception:
        recommendations.append("Project Intelligence indexing is not ready for this workspace yet.")

    return WorkspaceProfileResponse(
        workspace_root=str(root),
        manifest=manifest,
        has_manifest=manifest is not None,
        dependency_profile=dependency_profile,
        instruction_status=instruction_status,
        has_instruction_status=bool(instruction_status.schema_version or instruction_status.files),
        validation_plan=validation_plan,
        has_validation_plan=bool(validation_plan.schema_version or validation_plan.validation_command or validation_plan.steps),
        readiness=readiness,
        recommendations=recommendations,
    )


@app.get("/api/project-intelligence", response_model=ProjectIntelligenceSnapshot)
async def project_intelligence_snapshot(workspace_root: str | None = Query(default=None)) -> ProjectIntelligenceSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _project_intelligence_snapshot(root)


@app.post("/api/project-intelligence/reindex", response_model=ProjectIntelligenceSnapshot)
async def reindex_project_intelligence(request: ProjectIntelligenceReindexRequest) -> ProjectIntelligenceSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _build_project_intelligence(
        root,
        clear_memory=request.clear_memory,
        rebuild_memory=request.rebuild_memory,
    )


@app.post("/api/project-intelligence/context", response_model=ProjectContextSelectionResponse)
async def project_intelligence_context(request: ProjectContextSelectionRequest) -> ProjectContextSelectionResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    snapshot = _project_intelligence_snapshot(root)
    return project_intelligence.select_context(snapshot=snapshot, query=request.query, max_files=request.max_files)


@app.get("/api/workspace-intelligence", response_model=WorkspaceOperationsSnapshot)
async def workspace_intelligence_snapshot(workspace_root: str | None = Query(default=None)) -> WorkspaceOperationsSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _workspace_operations_snapshot(root)


@app.post("/api/workspace-intelligence/scan", response_model=WorkspaceOperationsSnapshot)
async def scan_workspace_intelligence(request: WorkspaceOperationsScanRequest) -> WorkspaceOperationsSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _build_workspace_operations(
        root,
        refresh_project_intelligence=request.refresh_project_intelligence,
        generate_recommendations=request.generate_recommendations,
        include_git=request.include_git,
    )


@app.get("/api/workspace-intelligence/events", response_model=list[WorkspaceWatchEvent])
async def workspace_intelligence_events(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=300),
) -> list[WorkspaceWatchEvent]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.workspace_events(project_root=root, limit=limit)


@app.get("/api/workspace-intelligence/recommendations", response_model=list[WorkspaceRecommendation])
async def workspace_intelligence_recommendations(
    workspace_root: str | None = Query(default=None),
    include_dismissed: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[WorkspaceRecommendation]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.workspace_recommendations(project_root=root, include_dismissed=include_dismissed, limit=limit)


@app.post("/api/workspace-intelligence/recommendations/{recommendation_id}/dismiss", response_model=RecommendationFixResponse)
async def dismiss_workspace_recommendation(
    recommendation_id: str,
    request: RecommendationActionRequest | None = None,
) -> RecommendationFixResponse:
    try:
        recommendation = agent.store.dismiss_workspace_recommendation(
            recommendation_id,
            reason=(request.reason if request else ""),
        )
        return RecommendationFixResponse(
            recommendation=recommendation,
            message="Recommendation dismissed.",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc


@app.post("/api/workspace-intelligence/recommendations/{recommendation_id}/fix", response_model=RecommendationFixResponse)
async def fix_workspace_recommendation(
    recommendation_id: str,
    request: RecommendationFixRequest | None = None,
) -> RecommendationFixResponse:
    action = request or RecommendationFixRequest()
    try:
        recommendation = agent.store.workspace_recommendation(recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc
    if not action.create_task:
        return RecommendationFixResponse(
            recommendation=recommendation,
            message="No task created; recommendation remains active.",
        )
    root = _resolve_workspace_or_400(recommendation.workspace_root)
    user_goal = recommendation.fix_prompt or recommendation.detail or recommendation.title
    task_id = agent.store.create_task(
        mode="develop",
        workspace_root=root,
        message=user_goal,
        title=f"Fix recommendation: {recommendation.title}",
        user_goal=user_goal,
        status="queued",
        assigned_agent_role="planner",
        related_files=recommendation.related_files,
        validation_commands=[],
    )
    event = agent.store.record_event(
        task_id,
        kind="recommendation.fix_requested",
        title="Recommendation fix task created",
        status="warning",
        detail=(
            "Workspace Intelligence created a tracked task only. No autonomous file edits were applied; "
            "normal approval, checkpoint, validation, and rollback rules still apply."
        ),
        payload={
            "recommendation_id": recommendation.id,
            "severity": recommendation.severity,
            "reason": action.reason,
            "related_files": recommendation.related_files,
        },
    )
    recommendation = agent.store.link_recommendation_task(recommendation_id, task_id)
    return RecommendationFixResponse(
        recommendation=recommendation,
        task=agent.store.task(task_id),
        event=event,
        message="Fix task created. No files were modified automatically.",
    )


@app.get("/api/workspace-intelligence/jobs", response_model=list[ScheduledIntelligenceJob])
async def workspace_intelligence_jobs(workspace_root: str | None = Query(default=None)) -> list[ScheduledIntelligenceJob]:
    root = _resolve_workspace_or_400(workspace_root)
    return workspace_operations.scheduled_jobs(agent.store.scheduled_intelligence_jobs(project_root=root))


@app.post("/api/workspace-intelligence/jobs/run", response_model=ScheduledJobRunResponse)
async def run_workspace_intelligence_jobs(request: ScheduledJobRunRequest) -> ScheduledJobRunResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _run_scheduled_intelligence_jobs(root, request)


@app.post("/api/workspace/setup", response_model=WorkspaceSetupResponse)
async def workspace_setup(request: WorkspaceSetupRequest) -> WorkspaceSetupResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    dependency_profile = workspace_manager.inspect_dependency_profile(root)
    validation_snapshot = agent.validation.profile_snapshot(root)
    persisted_recipe = agent.validation.load_profile(root)
    detected_recipe = validation_snapshot.profile
    install_command = request.install_command.strip() or (
        dependency_profile.install_commands[0] if dependency_profile.install_commands else ""
    )
    validation_command = request.validation_command.strip() or (
        detected_recipe.command if detected_recipe is not None else ""
    ) or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
    generated_manifest = workspace_setup_manifest(
        root,
        request,
        dependency_profile=dependency_profile,
        install_command=install_command,
        validation_command=validation_command,
    )
    existing_manifest = workspace_manager.load_project_manifest(root)
    created_files: list[str] = []
    updated_files: list[str] = []
    warnings: list[str] = []
    manifest_path = workspace_manager.PROJECT_MANIFEST_PATH

    if existing_manifest is None:
        manifest = workspace_manager.save_project_manifest(root, generated_manifest)
        created_files.append(manifest_path)
    elif request.overwrite_manifest:
        manifest = workspace_manager.save_project_manifest(root, generated_manifest)
        updated_files.append(manifest_path)
    else:
        manifest, changed = merge_missing_manifest_fields(existing_manifest, generated_manifest)
        if changed:
            manifest = workspace_manager.save_project_manifest(root, manifest)
            updated_files.append(manifest_path)
        else:
            manifest = existing_manifest

    saved_recipe = persisted_recipe
    profile_path = agent.validation.PROFILE_PATH
    if validation_command:
        if persisted_recipe and persisted_recipe.source == "manual" and not request.validation_command.strip():
            warnings.append("Existing manual validation recipe was kept.")
        elif persisted_recipe and persisted_recipe.command == validation_command and not request.validation_command.strip():
            saved_recipe = persisted_recipe
        else:
            profile_existed = (root / profile_path).exists()
            saved_recipe = agent.validation.save_profile(
                root,
                command=validation_command,
                label=(detected_recipe.label if detected_recipe and detected_recipe.command == validation_command else "")
                or "Workspace validation",
                source="workspace_setup",
                notes=request.notes.strip()
                or (detected_recipe.notes if detected_recipe and detected_recipe.command == validation_command else "")
                or "Saved by Aegis workspace setup from detected project files.",
            )
            (updated_files if profile_existed else created_files).append(profile_path)
    else:
        warnings.append("No validation command was detected; manifest was created without a validation recipe.")

    _invalidate_workspace_caches(root)
    profile = await workspace_profile(str(root))
    return WorkspaceSetupResponse(
        workspace_root=str(root),
        manifest=manifest,
        validation_profile=saved_recipe,
        profile=profile,
        created_files=created_files,
        updated_files=updated_files,
        warnings=warnings,
    )


@app.get("/api/workspace/autopilot-status", response_model=WorkspaceAutopilotStatusResponse)
async def workspace_autopilot_status(workspace_root: str | None = Query(default=None)) -> WorkspaceAutopilotStatusResponse:
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


@app.post("/api/chat", response_model=AgentResponse)
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


@app.get("/api/chat/stream/contract", response_model=ChatStreamContractResponse)
async def chat_stream_contract() -> ChatStreamContractResponse:
    return ChatStreamContractResponse(
        events=[
            ChatStreamEventInfo(
                event="meta",
                payload='{"type":"meta","schema_version":"aegis.chat.stream.v1","stream_mode":"chat-delta-final|structured-delta-final"}',
                description="Sent first with schema, stream mode, workspace, and routing hints.",
            ),
            ChatStreamEventInfo(
                event="status",
                payload='{"type":"status","stage":"planning","message":"..."}',
                description="Progress lifecycle updates while Aegis prepares context, routes, reconciles previews, and finalizes output.",
            ),
            ChatStreamEventInfo(
                event="delta",
                payload='{"type":"delta","delta":"partial text","source":"structured_reply_preview","preview_action":"append|reset","preview_attempt":1}',
                description="Provider text deltas for direct chat turns, or safe progress/reply-preview/reconciliation deltas for structured workspace turns. Raw provider JSON is never streamed.",
            ),
            ChatStreamEventInfo(
                event="final",
                payload='{"type":"final","task_id":"...","response":{...}}',
                description="The complete AgentResponse payload, matching /api/chat.",
            ),
            ChatStreamEventInfo(
                event="error",
                payload='{"type":"error","message":"safe error","detail":"developer detail"}',
                description="Recoverable stream error envelope sent before done.",
            ),
            ChatStreamEventInfo(
                event="done",
                payload='{"type":"done","task_id":"..."}',
                description="Terminal event; clients should close readers after receiving it.",
            ),
        ],
        recommendations=[
            "Use fetch with a ReadableStream for POST requests; EventSource cannot POST AgentRequest bodies.",
            "Treat final.response as the source of truth; clients may render delta text optimistically before final arrives.",
            "Keep /api/chat as the compatibility path for clients that do not need streamed status updates.",
        ],
    )


@app.post("/api/chat/stream")
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


@app.post("/api/routing/preview", response_model=RoutePreviewResponse)
async def preview_route(request: RoutePreviewRequest) -> RoutePreviewResponse:
    try:
        return await agent.preview_route(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/apply", response_model=ApplyResponse)
async def apply_changes(request: ApplyRequest) -> ApplyResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    result = workspace_manager.apply_changes(root, request.changes)
    _invalidate_workspace_caches(root)
    return ApplyResponse(
        applied=result.applied,
        warnings=result.warnings,
        checkpoint=result.checkpoint,
        workspace_root=str(root),
        workspace_files=workspace_manager.scan(root, max_files=120),
    )


@app.get("/api/project-builder/presets", response_model=list[ProjectScaffoldPreset])
async def project_builder_presets() -> list[ProjectScaffoldPreset]:
    return ProjectScaffolder.presets()


@app.post("/api/project-builder/plan", response_model=ProjectScaffoldPlanResponse)
async def plan_project_scaffold(request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
    try:
        return _cached_project_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/project-builder/preview", response_model=ProjectScaffoldResponse)
async def preview_project_scaffold(request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
    try:
        return project_scaffolder().preview(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/project-builder/scaffold", response_model=ProjectScaffoldResponse)
async def scaffold_project(request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
    try:
        result = project_scaffolder().scaffold(request)
        _invalidate_workspace_caches(Path(result.target_path))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> CheckpointListResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return CheckpointListResponse(
        workspace_root=str(root),
        checkpoints=workspace_manager.list_checkpoints(root, limit=limit),
    )


@app.post("/api/restore-checkpoint", response_model=RestoreCheckpointResponse)
async def restore_checkpoint(request: RestoreCheckpointRequest) -> RestoreCheckpointResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
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


@app.post("/api/validate", response_model=ValidateResponse)
async def validate_workspace(request: ValidateRequest) -> ValidateResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    try:
        return await agent.validate_workspace(str(root))
    finally:
        _invalidate_workspace_caches(root)


@app.post("/api/verify", response_model=VerificationResponse)
async def verify_workspace(request: VerificationRequest) -> VerificationResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    try:
        return await agent.verify_workspace(request.model_copy(update={"workspace_root": str(root)}))
    finally:
        _invalidate_workspace_caches(root)


@app.get("/api/validation/profile", response_model=ValidationProfileResponse)
async def validation_profile(workspace_root: str | None = Query(default=None)) -> ValidationProfileResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.validation.profile_snapshot(root)


@app.put("/api/validation/profile", response_model=ValidationProfileResponse)
async def update_validation_profile(
    request: ValidationProfileUpdateRequest,
    workspace_root: str | None = Query(default=None),
) -> ValidationProfileResponse:
    root = _resolve_workspace_or_400(workspace_root)

    command = request.command.strip()
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

    return agent.validation.profile_snapshot(root)


@app.get("/api/history", response_model=HistoryResponse)
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


@app.get("/api/tasks", response_model=TaskListResponse)
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


@app.post("/api/tasks", response_model=TaskDetailResponse)
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


@app.get("/api/tasks/{task_id}", response_model=TaskDetailResponse)
async def read_task(task_id: str) -> TaskDetailResponse:
    try:
        return TaskDetailResponse(task=agent.store.task(task_id), subtasks=agent.store.subtasks(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


@app.post("/api/tasks/{task_id}/cancel", response_model=TaskActionResponse)
async def cancel_task(task_id: str, request: TaskActionRequest | None = None) -> TaskActionResponse:
    try:
        event = agent.store.cancel_task(task_id, reason=(request.reason if request else ""))
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/approve", response_model=TaskActionResponse)
async def approve_task_action(task_id: str, request: TaskActionRequest) -> TaskActionResponse:
    try:
        event = agent.store.approve_task_action(task_id, reason=request.reason, approved=request.approved)
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


@app.post("/api/tasks/{task_id}/retry", response_model=TaskActionResponse)
async def retry_task(task_id: str, request: TaskActionRequest | None = None) -> TaskActionResponse:
    try:
        event = agent.store.retry_task(task_id, reason=(request.reason if request else ""))
        return TaskActionResponse(task=agent.store.task(task_id), event=event)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tasks/{task_id}/timeline", response_model=TaskTimelineResponse)
async def task_timeline(task_id: str) -> TaskTimelineResponse:
    try:
        agent.store.task(task_id)
        return TaskTimelineResponse(task_id=task_id, events=agent.store.task_events(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


@app.get("/api/tasks/{task_id}/artifacts", response_model=TaskArtifactsResponse)
async def task_artifacts(task_id: str) -> TaskArtifactsResponse:
    try:
        return agent.store.task_artifacts(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


@app.get("/api/distributed-runtime", response_model=DistributedRuntimeSnapshot)
async def distributed_runtime_snapshot(workspace_root: str | None = Query(default=None)) -> DistributedRuntimeSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _runtime_snapshot(root)


@app.get("/api/distributed-runtime/observability", response_model=RuntimeObservabilitySnapshot)
async def distributed_runtime_observability(workspace_root: str | None = Query(default=None)) -> RuntimeObservabilitySnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _runtime_snapshot(root).observability


@app.get("/api/distributed-runtime/workers", response_model=list[WorkerRuntimeInfo])
async def list_runtime_workers(workspace_root: str | None = Query(default=None)) -> list[WorkerRuntimeInfo]:
    root = _resolve_workspace_or_400(workspace_root)
    return _runtime_workers(root)


@app.post("/api/distributed-runtime/workers/register", response_model=WorkerRuntimeInfo)
async def register_runtime_worker(request: WorkerRegistrationRequest) -> WorkerRuntimeInfo:
    worker = distributed_runtime.register_worker(request)
    agent.store.upsert_runtime_worker(worker)
    _record_runtime_audit(
        distributed_runtime.audit_event(
            worker_id=worker.worker_id,
            event_type="worker.registered",
            status="ok" if worker.trust_state == "trusted" else "warning",
            detail=f"Worker {worker.name} registered as {worker.trust_state}.",
            metadata={
                "kind": worker.kind,
                "trust_scope": worker.trust_scope,
                "permission_scopes": worker.permission_scopes,
                "encrypted_transport_required": worker.metadata.get("encrypted_transport_required", False),
            },
        )
    )
    return worker


@app.post("/api/distributed-runtime/workers/{worker_id}/heartbeat", response_model=WorkerRuntimeInfo)
async def heartbeat_runtime_worker(worker_id: str, request: WorkerHeartbeatRequest) -> WorkerRuntimeInfo:
    capabilities_json = json.dumps(request.capabilities.model_dump(mode="json"), ensure_ascii=True) if request.capabilities else None
    try:
        worker = agent.store.heartbeat_runtime_worker(
            worker_id,
            status=request.status,
            current_jobs=request.current_jobs,
            capabilities_json=capabilities_json,
            metadata=request.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="worker not found") from exc
    _record_runtime_audit(
        distributed_runtime.audit_event(
            worker_id=worker.worker_id,
            event_type="worker.heartbeat",
            detail=f"Worker {worker.name} reported {worker.status}.",
            metadata={"current_jobs": worker.current_jobs},
        )
    )
    return worker


@app.post("/api/distributed-runtime/workers/{worker_id}/revoke", response_model=WorkerRuntimeInfo)
async def revoke_runtime_worker(worker_id: str, request: WorkerActionRequest | None = None) -> WorkerRuntimeInfo:
    try:
        current = agent.store.runtime_worker(worker_id)
        if current.kind == "local":
            raise HTTPException(status_code=400, detail="the local runtime worker cannot be revoked")
        worker = agent.store.revoke_runtime_worker(worker_id, reason=(request.reason if request else ""))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="worker not found") from exc
    _record_runtime_audit(
        distributed_runtime.audit_event(
            worker_id=worker.worker_id,
            event_type="worker.revoked",
            status="warning",
            detail=f"Worker {worker.name} trust was revoked.",
            metadata={"reason": request.reason if request else ""},
        )
    )
    return worker


@app.get("/api/distributed-runtime/queue", response_model=list[ExecutionQueueItem])
async def list_execution_queue(
    workspace_root: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ExecutionQueueItem]:
    root = _resolve_workspace_or_400(workspace_root)
    _runtime_workers(root)
    return _runtime_jobs(root, status=status, limit=limit)


@app.post("/api/distributed-runtime/queue", response_model=ExecutionQueueItem)
async def create_execution_queue_item(request: ExecutionQueueCreateRequest) -> ExecutionQueueItem:
    root = _resolve_workspace_or_400(request.workspace_root)
    _runtime_workers(root)
    item = distributed_runtime.create_queue_item(request, root)
    created = agent.store.create_execution_job(item)
    _record_runtime_audit(
        distributed_runtime.audit_event(
            job_id=created.id,
            event_type="queue.created",
            detail=f"{created.kind.title()} job {created.id} queued.",
            metadata={"workspace_root": str(root), "task_id": created.task_id, "permission_scope": created.permission_scope},
        )
    )
    return created


@app.get("/api/distributed-runtime/queue/{job_id}", response_model=ExecutionQueueItem)
async def read_execution_queue_item(job_id: str) -> ExecutionQueueItem:
    try:
        return agent.store.execution_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution job not found") from exc


@app.post("/api/distributed-runtime/queue/{job_id}/cancel", response_model=ExecutionQueueItem)
async def cancel_execution_queue_item(job_id: str, request: ExecutionQueueActionRequest | None = None) -> ExecutionQueueItem:
    try:
        job = agent.store.cancel_execution_job(job_id, reason=(request.reason if request else ""))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution job not found") from exc
    _record_runtime_audit(
        distributed_runtime.audit_event(
            job_id=job.id,
            event_type="queue.canceled",
            status="warning",
            detail=request.reason if request and request.reason else "Execution job was canceled.",
            metadata={"task_id": job.task_id},
        )
    )
    if job.task_id:
        _task_transition_or_event(job.task_id, "canceled", title="Distributed job canceled", detail=job.error_summary or "Execution job was canceled.")
    return job


@app.post("/api/distributed-runtime/queue/{job_id}/retry", response_model=ExecutionQueueItem)
async def retry_execution_queue_item(job_id: str, request: ExecutionQueueActionRequest | None = None) -> ExecutionQueueItem:
    try:
        job = agent.store.retry_execution_job(job_id, reason=(request.reason if request else ""))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution job not found") from exc
    _record_runtime_audit(
        distributed_runtime.audit_event(
            job_id=job.id,
            event_type="queue.retry",
            detail=request.reason if request and request.reason else "Execution job was queued for retry.",
            metadata={"task_id": job.task_id, "attempts": job.attempts},
        )
    )
    if job.task_id:
        _task_transition_or_event(job.task_id, "queued", title="Distributed job retry queued", detail=job.error_summary or "Execution job was queued for retry.")
    return job


@app.post("/api/distributed-runtime/dispatch", response_model=ExecutionDispatchResponse)
async def dispatch_execution_queue(request: ExecutionDispatchRequest) -> ExecutionDispatchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    workers = _runtime_workers(root)
    jobs = _runtime_jobs(root, limit=300)
    runnable = distributed_runtime.select_runnable_jobs(jobs, limit=request.limit)
    events: list[WorkerAuditEvent] = []
    dispatched: list[ExecutionQueueItem] = []
    warnings: list[str] = []
    if not runnable:
        warnings.append("No queued execution jobs are runnable yet.")

    for job in runnable:
        worker = distributed_runtime.select_worker(
            workers,
            job,
            requested_worker_id=request.worker_id,
            allow_remote=request.allow_remote,
        )
        if worker is None:
            warnings.append(f"No eligible worker is available for job {job.id}.")
            continue
        if worker.kind in {"lan", "remote"}:
            assigned = agent.store.update_execution_job(
                job.id,
                status="assigned",
                assigned_worker_id=worker.worker_id,
                attempts=job.attempts + 1,
            )
            agent.store.heartbeat_runtime_worker(worker.worker_id, status="busy", current_jobs=worker.current_jobs + 1)
            event = _record_runtime_audit(
                distributed_runtime.audit_event(
                    worker_id=worker.worker_id,
                    job_id=job.id,
                    event_type="job.assigned.remote",
                    detail=f"Job {job.id} was assigned to remote worker {worker.name}.",
                    metadata={"allow_remote": request.allow_remote, "endpoint": worker.endpoint},
                )
            )
            events.append(event)
            dispatched.append(assigned)
            if assigned.task_id:
                _task_transition_or_event(
                    assigned.task_id,
                    "running",
                    title="Remote worker assigned",
                    detail=f"Job {assigned.id} was assigned to {worker.name}.",
                    payload={"worker_id": worker.worker_id, "job_id": assigned.id},
                )
            continue
        result, job_events = _execute_runtime_job(job, worker, allow_commands=request.allow_commands)
        events.extend(job_events)
        dispatched.append(result)
        workers = _runtime_workers(root)

    return ExecutionDispatchResponse(jobs=dispatched, workers=_runtime_workers(root), events=events, warnings=warnings)


@app.post("/api/distributed-runtime/route", response_model=HybridRouteDecision)
async def route_distributed_model(request: HybridRouteRequest) -> HybridRouteDecision:
    root = _resolve_workspace_or_400(request.workspace_root)
    decision = distributed_runtime.route_models(
        request,
        workers=_runtime_workers(root),
        registry=model_registry.snapshot(),
    )
    _record_runtime_audit(
        distributed_runtime.audit_event(
            event_type="model.route.selected",
            status="ok" if decision.selected else "warning",
            detail=decision.summary,
            metadata={"fallback_order": decision.fallback_order, "privacy_mode": decision.privacy_mode},
        )
    )
    return decision


@app.get("/api/distributed-runtime/audit", response_model=list[WorkerAuditEvent])
async def distributed_runtime_audit(
    worker_id: str = Query(default=""),
    job_id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[WorkerAuditEvent]:
    return _runtime_audit_events(worker_id=worker_id, job_id=job_id, limit=limit)


@app.get("/api/distributed-runtime/sync/manifests", response_model=list[RemoteWorkspaceSyncManifest])
async def list_remote_sync_manifests(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RemoteWorkspaceSyncManifest]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.workspace_sync_manifests(project_root=root, limit=limit)


@app.post("/api/distributed-runtime/sync/export", response_model=RemoteWorkspaceSyncManifest)
async def create_remote_sync_manifest(request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _save_remote_sync_manifest(root, request)


@app.get("/api/telemetry", response_model=TelemetryResponse)
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


@app.get("/api/telemetry/route-quality", response_model=RouteQualityResponse)
async def route_quality(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> RouteQualityResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.route_quality(project_root=root, limit=limit)


@app.get("/api/telemetry/route-health", response_model=list[ModelRouteHealthInfo])
async def route_health(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelRouteHealthInfo]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.route_health_signals(project_root=root, limit=limit)


@app.get("/api/telemetry/fallback-inspector", response_model=FallbackInspectorResponse)
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


@app.get("/api/telemetry/feedback", response_model=FeedbackTelemetryResponse)
async def feedback_telemetry(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeedbackTelemetryResponse:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.feedback_telemetry(project_root=root, limit=limit)


@app.get("/api/telemetry/snapshot", response_model=TelemetrySnapshotResponse)
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


@app.post("/api/telemetry/snapshot/refresh", response_model=TelemetrySnapshotResponse)
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


@app.get("/api/telemetry/policy-diff", response_model=RoutePolicyDiffResponse)
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


@app.get("/api/adaptive-intelligence", response_model=AdaptiveIntelligenceSnapshot)
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


@app.post("/api/adaptive-intelligence/refresh", response_model=AdaptiveIntelligenceSnapshot)
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


@app.get("/api/adaptive-intelligence/outcomes", response_model=list[TaskOutcomeRecord])
async def adaptive_task_outcomes(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    refresh: bool = Query(default=False),
) -> list[TaskOutcomeRecord]:
    root = _resolve_workspace_or_400(workspace_root)
    if refresh:
        return adaptive_intelligence.refresh_outcomes(agent.store, project_root=root, limit=limit)
    return agent.store.adaptive_task_outcomes(project_root=root, limit=limit)


@app.get("/api/adaptive-intelligence/policies", response_model=list[IntelligencePolicyProfile])
async def adaptive_policy_profiles() -> list[IntelligencePolicyProfile]:
    return adaptive_intelligence.ensure_profiles(agent.store)


@app.post("/api/adaptive-intelligence/policies", response_model=IntelligencePolicyProfile)
async def upsert_adaptive_policy_profile(
    request: AdaptivePolicyProfileUpdateRequest,
) -> IntelligencePolicyProfile:
    return adaptive_intelligence.upsert_profile(agent.store, request)


@app.post("/api/adaptive-intelligence/policies/{profile_id}/activate", response_model=AdaptiveIntelligenceSnapshot)
async def activate_adaptive_policy_profile(
    profile_id: str,
    request: TaskActionRequest | None = None,
    workspace_root: str | None = Query(default=None),
) -> AdaptiveIntelligenceSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    reason = request.reason if request else ""
    adaptive_intelligence.activate_profile(agent.store, profile_id=profile_id, reason=reason)
    return adaptive_intelligence.snapshot(agent.store, project_root=root, refresh_outcomes=False)


@app.post("/api/adaptive-intelligence/policies/rollback", response_model=AdaptiveIntelligenceSnapshot)
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


@app.post("/api/adaptive-intelligence/benchmarks/run", response_model=list[AdaptiveBenchmarkReport])
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


@app.get("/api/adaptive-intelligence/benchmarks", response_model=list[AdaptiveBenchmarkReport])
async def list_adaptive_benchmarks(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AdaptiveBenchmarkReport]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.adaptive_benchmark_reports(project_root=root, limit=limit)


@app.post("/api/adaptive-intelligence/replay", response_model=list[EvaluationReplayResult])
async def replay_adaptive_tasks(
    request: AdaptiveReplayRequest,
) -> list[EvaluationReplayResult]:
    root = _resolve_workspace_or_400(request.workspace_root)
    return adaptive_intelligence.replay(agent.store, project_root=root, request=request)


@app.get("/api/adaptive-intelligence/replay", response_model=list[EvaluationReplayResult])
async def list_adaptive_replay_results(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EvaluationReplayResult]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.adaptive_replay_results(project_root=root, limit=limit)


@app.get("/api/productization", response_model=ProductizationSnapshot)
async def productization_snapshot(
    workspace_root: str | None = Query(default=None),
    refresh_metrics: bool = Query(default=False),
) -> ProductizationSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=refresh_metrics)


@app.post("/api/productization/refresh", response_model=ProductizationSnapshot)
async def refresh_productization_snapshot(request: ProductizationRefreshRequest) -> ProductizationSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _productization_snapshot(root, refresh_metrics=request.refresh_metrics)


@app.get("/api/productization/stable-apis", response_model=list[StableApiContract])
async def productization_stable_apis() -> list[StableApiContract]:
    return productization.stable_api_contracts()


@app.get("/api/productization/recovery", response_model=RuntimeRecoverySnapshot)
async def productization_recovery(workspace_root: str | None = Query(default=None)) -> RuntimeRecoverySnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=False).recovery


@app.get("/api/productization/reliability", response_model=list[ReliabilityMetric])
async def productization_reliability(workspace_root: str | None = Query(default=None)) -> list[ReliabilityMetric]:
    root = _resolve_workspace_or_400(workspace_root)
    return _productization_snapshot(root, refresh_metrics=False).metrics


@app.get("/api/productization/plugins", response_model=list[PluginManifest])
async def list_productization_plugins(include_disabled: bool = Query(default=True)) -> list[PluginManifest]:
    return agent.store.plugin_manifests(include_disabled=include_disabled)


@app.post("/api/productization/plugins/validate", response_model=PluginValidationResult)
async def validate_productization_plugin(request: PluginValidationRequest) -> PluginValidationResult:
    return productization.validate_plugin(
        request,
        policy=productization.ensure_enterprise_policy(agent.store),
    )


@app.post("/api/productization/plugins/register", response_model=PluginManifest)
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


@app.post("/api/productization/plugins/{plugin_id}/enable", response_model=PluginManifest)
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


@app.post("/api/productization/plugins/{plugin_id}/disable", response_model=PluginManifest)
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


@app.post("/api/productization/plugins/{plugin_id}/trust", response_model=PluginManifest)
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


@app.get("/api/productization/enterprise-policy", response_model=EnterprisePolicyProfile)
async def get_enterprise_policy() -> EnterprisePolicyProfile:
    return productization.ensure_enterprise_policy(agent.store)


@app.put("/api/productization/enterprise-policy", response_model=EnterprisePolicyProfile)
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


@app.get("/api/ecosystem", response_model=EcosystemSnapshot)
async def ecosystem_snapshot(
    workspace_root: str | None = Query(default=None),
    rebuild_graph: bool = Query(default=False),
    query: str = Query(default=""),
) -> EcosystemSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _ecosystem_snapshot(root, rebuild_graph=rebuild_graph, include_search_query=query)


@app.post("/api/ecosystem/refresh", response_model=EcosystemSnapshot)
async def refresh_ecosystem_snapshot(request: EcosystemRefreshRequest) -> EcosystemSnapshot:
    root = _resolve_workspace_or_400(request.workspace_root)
    return _ecosystem_snapshot(root, rebuild_graph=request.rebuild_graph, include_search_query=request.include_search_query)


@app.get("/api/ecosystem/marketplace", response_model=list[EcosystemPackageManifest])
async def ecosystem_marketplace_catalog() -> list[EcosystemPackageManifest]:
    return ecosystem.marketplace_catalog()


@app.get("/api/ecosystem/packages", response_model=list[EcosystemPackageManifest])
async def list_ecosystem_packages(include_disabled: bool = Query(default=True)) -> list[EcosystemPackageManifest]:
    return agent.store.ecosystem_packages(include_disabled=include_disabled)


@app.post("/api/ecosystem/packages/validate", response_model=EcosystemPackageValidationResult)
async def validate_ecosystem_package(request: EcosystemPackageValidationRequest) -> EcosystemPackageValidationResult:
    return ecosystem.validate_package(
        request,
        policy=agent.store.active_organization_policy() or ecosystem.default_organization_policy(),
    )


@app.post("/api/ecosystem/packages/register", response_model=EcosystemPackageManifest)
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


@app.post("/api/ecosystem/packages/{package_id}/enable", response_model=EcosystemPackageManifest)
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


@app.post("/api/ecosystem/packages/{package_id}/disable", response_model=EcosystemPackageManifest)
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


@app.post("/api/ecosystem/packages/{package_id}/trust", response_model=EcosystemPackageManifest)
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


@app.get("/api/ecosystem/workflows", response_model=list[EcosystemWorkflowDefinition])
async def list_ecosystem_workflows(include_disabled: bool = Query(default=True)) -> list[EcosystemWorkflowDefinition]:
    ecosystem.ensure_baseline(agent.store)
    return agent.store.ecosystem_workflows(include_disabled=include_disabled)


@app.post("/api/ecosystem/workflows/register", response_model=EcosystemWorkflowDefinition)
async def register_ecosystem_workflow(workflow: EcosystemWorkflowDefinition) -> EcosystemWorkflowDefinition:
    if workflow.api_version != ECOSYSTEM_API_VERSION:
        raise HTTPException(status_code=400, detail="workflow API version is not compatible with this Aegis runtime")
    saved = agent.store.upsert_ecosystem_workflow(workflow)
    _record_ecosystem_audit("workflow.registered", saved.id, f"Workflow {saved.id} registered.", metadata={"category": saved.category})
    return saved


@app.post("/api/ecosystem/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
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


@app.get("/api/ecosystem/shared-profiles", response_model=list[SharedIntelligenceProfile])
async def list_shared_intelligence_profiles(
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SharedIntelligenceProfile]:
    return agent.store.shared_intelligence_profiles(kind=kind, limit=limit)


@app.post("/api/ecosystem/shared-profiles/import", response_model=SharedIntelligenceProfile)
async def import_shared_intelligence_profile(request: SharedIntelligenceProfileImportRequest) -> SharedIntelligenceProfile:
    saved = agent.store.upsert_shared_intelligence_profile(request.profile)
    _record_ecosystem_audit(
        "shared_profile.imported",
        saved.id,
        f"Shared intelligence profile {saved.id} imported.",
        metadata={"kind": saved.kind, "reason": request.reason},
    )
    return saved


@app.get("/api/ecosystem/shared-profiles/{profile_id}/export", response_model=SharedIntelligenceProfileExportResponse)
async def export_shared_intelligence_profile(profile_id: str) -> SharedIntelligenceProfileExportResponse:
    try:
        profile = agent.store.shared_intelligence_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="shared intelligence profile not found") from exc
    return SharedIntelligenceProfileExportResponse(profile=profile, checksum=profile.checksum)


@app.post("/api/ecosystem/shared-profiles/export-current", response_model=SharedIntelligenceProfileExportResponse)
async def export_current_project_intelligence(workspace_root: str | None = Query(default=None)) -> SharedIntelligenceProfileExportResponse:
    root = _resolve_workspace_or_400(workspace_root)
    profile = ecosystem.shared_profile_from_project(project_root=root, project_intelligence=_project_intelligence_snapshot(root))
    saved = agent.store.upsert_shared_intelligence_profile(profile)
    _record_ecosystem_audit("shared_profile.exported", saved.id, f"Current project intelligence exported as {saved.id}.")
    return SharedIntelligenceProfileExportResponse(profile=saved, checksum=saved.checksum)


@app.get("/api/ecosystem/org-policy", response_model=OrganizationPolicyProfile)
async def get_organization_policy() -> OrganizationPolicyProfile:
    ecosystem.ensure_baseline(agent.store)
    return agent.store.active_organization_policy() or ecosystem.default_organization_policy()


@app.put("/api/ecosystem/org-policy", response_model=OrganizationPolicyProfile)
async def update_organization_policy(request: OrganizationPolicyUpdateRequest) -> OrganizationPolicyProfile:
    saved = agent.store.save_organization_policy(request.profile)
    _record_ecosystem_audit(
        "organization_policy.updated",
        saved.id,
        f"Organization policy {saved.id} saved.",
        metadata={"reason": request.reason, "collaboration_mode": saved.collaboration_mode},
    )
    return saved


@app.get("/api/ecosystem/knowledge-graph", response_model=KnowledgeGraphSnapshot)
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


@app.post("/api/ecosystem/search", response_model=EcosystemSearchResponse)
async def ecosystem_search(request: EcosystemSearchRequest) -> EcosystemSearchResponse:
    root = _resolve_workspace_or_400(request.workspace_root)
    graph = agent.store.knowledge_graph_snapshot(project_root=root)
    if graph is None:
        graph = _ecosystem_snapshot(root, rebuild_graph=True).knowledge_graph
    return ecosystem.search(request, store=agent.store, project_root=root, graph=graph)


@app.post("/api/ecosystem/reproducibility", response_model=ReproducibilityRecord)
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


@app.get("/api/ecosystem/reproducibility", response_model=list[ReproducibilityRecord])
async def list_reproducibility_records(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ReproducibilityRecord]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.reproducibility_records(project_root=root, limit=limit)


@app.get("/api/ecosystem/audit", response_model=list[EcosystemAuditEvent])
async def list_ecosystem_audit_events(limit: int = Query(default=50, ge=1, le=200)) -> list[EcosystemAuditEvent]:
    return agent.store.ecosystem_audit_events(limit=limit)


@app.get("/api/autonomous-engineering", response_model=AutonomousEngineeringSnapshot)
async def autonomous_engineering_snapshot(workspace_root: str | None = Query(default=None)) -> AutonomousEngineeringSnapshot:
    root = _resolve_workspace_or_400(workspace_root)
    return _autonomous_snapshot(root)


@app.get("/api/autonomous-engineering/objectives", response_model=list[AutonomousObjective])
async def list_autonomous_objectives(
    workspace_root: str | None = Query(default=None),
    include_completed: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AutonomousObjective]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.autonomous_objectives(project_root=root, include_completed=include_completed, limit=limit)


@app.post("/api/autonomous-engineering/objectives", response_model=AutonomousObjectiveDetail)
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
    return detail


@app.get("/api/autonomous-engineering/objectives/{objective_id}", response_model=AutonomousObjectiveDetail)
async def get_autonomous_objective(objective_id: str) -> AutonomousObjectiveDetail:
    try:
        return agent.store.autonomous_objective_detail(objective_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


@app.post("/api/autonomous-engineering/objectives/{objective_id}/simulate", response_model=AutonomousSimulationEstimate)
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


@app.post("/api/autonomous-engineering/objectives/{objective_id}/start", response_model=AutonomousObjectiveDetail)
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


@app.post("/api/autonomous-engineering/objectives/{objective_id}/pause", response_model=AutonomousObjectiveDetail)
async def pause_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.pause_objective(agent.store, objective_id, request or AutonomousObjectiveActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


@app.post("/api/autonomous-engineering/objectives/{objective_id}/cancel", response_model=AutonomousObjectiveDetail)
async def cancel_autonomous_objective(
    objective_id: str,
    request: AutonomousObjectiveActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.cancel_objective(agent.store, objective_id, request or AutonomousObjectiveActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous objective not found") from exc


@app.post("/api/autonomous-engineering/objectives/{objective_id}/iterate", response_model=AutonomousObjectiveDetail)
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


@app.get("/api/autonomous-engineering/approval-gates", response_model=list[AutonomousApprovalGate])
async def list_autonomous_approval_gates(
    workspace_root: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[AutonomousApprovalGate]:
    root = _resolve_workspace_or_400(workspace_root)
    return agent.store.autonomous_approval_gates(project_root=root, limit=limit)


@app.post("/api/autonomous-engineering/approval-gates/{gate_id}/approve", response_model=AutonomousObjectiveDetail)
async def approve_autonomous_gate(
    gate_id: str,
    request: AutonomousApprovalActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.approve_gate(agent.store, gate_id, request or AutonomousApprovalActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous approval gate not found") from exc


@app.post("/api/autonomous-engineering/approval-gates/{gate_id}/reject", response_model=AutonomousObjectiveDetail)
async def reject_autonomous_gate(
    gate_id: str,
    request: AutonomousApprovalActionRequest | None = None,
) -> AutonomousObjectiveDetail:
    try:
        return autonomous_engineering.reject_gate(agent.store, gate_id, request or AutonomousApprovalActionRequest())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="autonomous approval gate not found") from exc


@app.get("/")
async def root() -> dict:
    return {"message": "Auralith OS API is running on Aegis Core.", "ui": "http://127.0.0.1:5173"}


# Memory Management Endpoints
@app.get("/api/memory")
async def get_memory_notes(
    workspace_root: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict:
    """Get memory notes, optionally filtered by category."""
    root = _resolve_workspace_or_400(workspace_root)
    from .memory_manager import MemoryManager

    memory = MemoryManager(root)

    if category:
        notes = memory.get_notes_by_category(category)
    else:
        notes = list(memory.notes.values())

    return {
        "workspace_root": str(root),
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "category": n.category,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "pinned": n.pinned,
                "tags": n.tags,
                "related_files": n.related_files,
                "confidence": n.confidence
            }
            for n in sorted(notes, key=lambda x: x.pinned, reverse=True)
        ]
    }


@app.post("/api/memory")
async def create_memory_note(request: dict, workspace_root: str | None = Query(default=None)) -> dict:
    """Create a new memory note."""
    root = _resolve_workspace_or_400(workspace_root)
    from .memory_manager import MemoryManager

    memory = MemoryManager(root)
    note = memory.create_note(
        title=request.get("title", "Untitled"),
        content=request.get("content", ""),
        category=request.get("category", "insight"),
        tags=request.get("tags", []),
        related_files=request.get("related_files", [])
    )
    note = memory.update_note(
        note.id,
        pinned=bool(request.get("pinned", False)),
        confidence=float(request.get("confidence", note.confidence) or note.confidence),
    ) or note
    _invalidate_workspace_caches(root)

    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "category": note.category,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "pinned": note.pinned,
        "tags": note.tags,
        "related_files": note.related_files,
        "confidence": note.confidence
    }


def _redact_feedback_text(content: str) -> tuple[str, int]:
    redacted = content
    redaction_count = 0
    for pattern, replacement in _FEEDBACK_REDACTION_PATTERNS:
        redacted, count = pattern.subn(replacement, redacted)
        redaction_count += count
    return redacted, redaction_count


def _feedback_privacy_policy() -> dict[str, bool | int]:
    shared_workspace = bool(settings.aegis_shared_workspace_mode)
    capture_excerpts = bool(settings.aegis_feedback_capture_excerpts) and not shared_workspace
    redact_excerpts = bool(settings.aegis_feedback_redaction_enabled)
    max_excerpt_chars = max(0, min(2000, int(settings.aegis_feedback_max_excerpt_chars or 0)))
    hash_content = bool(settings.aegis_feedback_hash_content) and not shared_workspace
    return {
        "shared_workspace": shared_workspace,
        "capture_excerpts": capture_excerpts,
        "redact_excerpts": redact_excerpts,
        "max_excerpt_chars": max_excerpt_chars,
        "hash_content": hash_content,
    }


def _feedback_memory_excerpt(content: str, policy: dict[str, bool | int]) -> tuple[str, int]:
    if not content or not policy["capture_excerpts"] or int(policy["max_excerpt_chars"]) <= 0:
        return "", 0
    if bool(policy["redact_excerpts"]):
        redacted, count = _redact_feedback_text(content)
        return redacted[: int(policy["max_excerpt_chars"])], count
    return content[: int(policy["max_excerpt_chars"])], 0


@app.post("/api/feedback", response_model=FeedbackRecordResponse)
async def record_feedback(
    request: FeedbackRecordRequest,
    workspace_root: str | None = Query(default=None),
) -> FeedbackRecordResponse:
    """Record structured user feedback for route quality, evals, and preference learning."""
    root = _resolve_workspace_or_400(workspace_root)
    privacy_policy = _feedback_privacy_policy()
    content = request.content.strip()
    excerpt, redaction_count = _feedback_memory_excerpt(content, privacy_policy)
    feedback_metadata = dict(request.metadata or {})
    feedback_metadata.update(
        {
            "feedback_privacy_shared_workspace": bool(privacy_policy["shared_workspace"]),
            "feedback_privacy_capture_excerpts": bool(privacy_policy["capture_excerpts"]),
            "feedback_privacy_redaction_enabled": bool(privacy_policy["redact_excerpts"]),
            "feedback_privacy_hash_content": bool(privacy_policy["hash_content"]),
            "feedback_privacy_max_excerpt_chars": int(privacy_policy["max_excerpt_chars"]),
            "feedback_privacy_redaction_count": redaction_count,
            "feedback_original_content_length": len(request.content or ""),
        }
    )
    telemetry_request = request.model_copy(
        update={
            "content": request.content if bool(privacy_policy["hash_content"]) else "",
            "metadata": feedback_metadata,
        }
    )
    event = agent.store.record_feedback(project_root=root, request=telemetry_request)
    title = f"User {request.sentiment} {request.target or 'Aegis output'}"
    detail_parts = [
        f"Sentiment: {request.sentiment}",
        f"Action: {request.action}",
        f"Target: {request.target or 'assistant_response'}",
        f"Task: {request.task_id or 'unknown'}",
        f"Model: {request.model_label or 'unknown'}",
        f"Context: {request.context or 'assistant_message'}",
        f"Content hash: {event.content_hash or 'empty'}",
        f"Excerpt capture: {'enabled' if privacy_policy['capture_excerpts'] else 'disabled'}",
        f"Redaction: {'enabled' if privacy_policy['redact_excerpts'] else 'disabled'}",
        f"Shared workspace: {'yes' if privacy_policy['shared_workspace'] else 'no'}",
    ]
    if excerpt:
        detail_parts.extend(["Redacted excerpt:" if redaction_count else "Excerpt:", excerpt])
    elif content:
        detail_parts.append("Excerpt: [disabled by feedback privacy policy]")
    agent.store.remember_project_note(
        project_root=root,
        category="feedback",
        title=title[:160],
        detail="\n".join(detail_parts),
        source="desktop_feedback",
        confidence=0.86 if request.sentiment in {"liked", "disliked", "accepted", "rejected"} else 0.68,
    )
    _invalidate_workspace_caches(root)
    return FeedbackRecordResponse(ok=True, workspace_root=str(root), event=event)


@app.put("/api/memory/{note_id}")
async def update_memory_note(
    note_id: str,
    request: dict,
    workspace_root: str | None = Query(default=None)
) -> dict:
    """Update a memory note."""
    root = _resolve_workspace_or_400(workspace_root)
    from .memory_manager import MemoryManager

    memory = MemoryManager(root)
    note = memory.update_note(note_id, **request)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    _invalidate_workspace_caches(root)
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "category": note.category,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "pinned": note.pinned,
        "tags": note.tags,
        "related_files": note.related_files,
        "confidence": note.confidence,
    }


@app.delete("/api/memory/{note_id}")
async def delete_memory_note(note_id: str, workspace_root: str | None = Query(default=None)) -> dict:
    """Delete a memory note."""
    root = _resolve_workspace_or_400(workspace_root)
    from .memory_manager import MemoryManager

    memory = MemoryManager(root)
    if not memory.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")

    _invalidate_workspace_caches(root)
    return {"deleted": note_id}


# Approval & Sandbox Endpoints
@app.get("/api/approval/settings")
async def get_approval_settings(workspace_root: str | None = Query(default=None)) -> dict:
    """Get current approval and sandbox settings."""
    _resolve_workspace_or_400(workspace_root)
    from .approval_sandbox import ApprovalManager, SandboxProfileManager

    manager = ApprovalManager(settings.approval_tier, settings.sandbox_profile)

    return {
        "approval_tier": manager.tier.value,
        "sandbox_profile": manager.sandbox,
        "available_tiers": ["manual", "prompt", "guided", "autonomous"],
        "available_profiles": list(SandboxProfileManager.PROFILES.keys())
    }


@app.put("/api/approval/settings")
async def update_approval_settings(
    request: dict,
    workspace_root: str | None = Query(default=None)
) -> dict:
    """Update approval and sandbox settings."""
    _resolve_workspace_or_400(workspace_root)
    from .approval_sandbox import ApprovalManager

    try:
        manager = ApprovalManager(
            request.get("approval_tier", settings.approval_tier),
            request.get("sandbox_profile", settings.sandbox_profile),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    update_env(
        {
            "APPROVAL_TIER": manager.tier.value,
            "SANDBOX_PROFILE": manager.sandbox,
        }
    )
    refresh_runtime()

    return {
        "approval_tier": manager.tier.value,
        "sandbox_profile": manager.sandbox
    }


# Project Indexing Endpoints
@app.post("/api/index/rebuild")
async def rebuild_index(workspace_root: str | None = Query(default=None)) -> dict:
    """Rebuild project file index."""
    root = _resolve_workspace_or_400(workspace_root)
    from .project_indexer import ProjectIndexer

    indexer = ProjectIndexer()

    files = workspace_manager.scan(root, max_files=500)
    indexer.build_from_workspace(root, files)

    return {
        "indexed": len(indexer.index),
        "files": list(indexer.index.keys())[:10],
        "workspace": str(root)
    }


@app.post("/api/index/search")
async def search_index(
    request: dict,
    workspace_root: str | None = Query(default=None)
) -> dict:
    """Search project index for relevant files."""
    root = _resolve_workspace_or_400(workspace_root)
    from .project_indexer import ProjectIndexer

    indexer = ProjectIndexer()
    query = request.get("query", "")
    top_k = request.get("top_k", 5)

    if not query:
        return {"results": [], "query": query}

    files = workspace_manager.scan(root, max_files=500)
    indexer.build_from_workspace(root, files)
    files = indexer.find_relevant_files(query, max_results=top_k)

    return {
        "query": query,
        "indexed": len(indexer.index),
        "results": [
            {
                "path": str(f.path),
                "kind": f.kind,
                "size": f.size,
                "relevance": f.relevance_score
            }
            for f in files
        ],
        "workspace": str(root)
    }


# Diff Engine Endpoints
@app.post("/api/diff/compare")
async def compare_files(
    request: dict,
    workspace_root: str | None = Query(default=None)
) -> dict:
    """Compare two files and generate unified diff."""
    from .diff_engine import DiffEngine

    old_content = request.get("old_content")
    new_content = request.get("new_content")
    path = request.get("path", "file")
    action = request.get("action", "update")

    if action == "create":
        if new_content is None:
            raise HTTPException(status_code=400, detail="new_content required for create diffs")
    elif action == "delete":
        if old_content is None:
            raise HTTPException(status_code=400, detail="old_content required for delete diffs")
    elif old_content is None or new_content is None:
        raise HTTPException(status_code=400, detail="old_content and new_content required")

    diff = DiffEngine.compare_files(old_content, new_content, path, action)

    return {
        "path": diff.path,
        "action": diff.action,
        "patch": diff.get_patch(),
        "added_lines": diff.added_lines,
        "removed_lines": diff.removed_lines,
        "modified_lines": diff.modified_lines
    }


@app.post("/api/diff/apply")
async def apply_patch(
    request: dict,
    workspace_root: str | None = Query(default=None)
) -> dict:
    """Apply a unified patch to file content."""
    from .diff_engine import DiffEngine

    original_content = request.get("original_content")
    patch_content = request.get("patch_content")

    if original_content is None or patch_content is None:
        raise HTTPException(status_code=400, detail="original_content and patch_content required")

    try:
        patched = DiffEngine.apply_patch(original_content, patch_content)
        if patched is None:
            raise HTTPException(status_code=400, detail="Failed to apply patch")
        return {
            "applied": True,
            "patched_content": patched
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to apply patch: {str(e)}")


@app.post("/api/diff/summarize")
async def summarize_diff(request: dict) -> dict:
    """Generate human-readable summary of a diff."""
    from .diff_engine import DiffEngine, FileDiff

    # Expect either a FileDiff object or the raw components
    path = request.get("path", "file")
    action = request.get("action", "update")
    old_content = request.get("old_content")
    new_content = request.get("new_content")

    if not all([path, action, new_content is not None]):
        raise HTTPException(status_code=400, detail="path, action, and new_content required")

    # Create a FileDiff object
    diff = DiffEngine.compare_files(old_content, new_content, path, action)
    summary = DiffEngine.summarize_diff(diff)

    return {
        "summary": summary,
        "path": path
    }
