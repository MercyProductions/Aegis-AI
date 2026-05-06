# backend/main.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent import AgentEngine, MODE_OPTIONS
from .creative_media import CreativeMediaEngine
from .model_benchmark import ModelBenchmarkManager
from .model_manager import ModelManager
from .model_registry import ModelRegistryManager
from .project_scaffolder import ProjectScaffolder
from .schemas import (
    AgentRequest,
    AgentResponse,
    AppConfig,
    ApplyRequest,
    ApplyResponse,
    ChatStreamContractResponse,
    ChatStreamEventInfo,
    CheckpointListResponse,
    ConfigUpdateRequest,
    FallbackInspectorResponse,
    FeedbackRecordRequest,
    FeedbackRecordResponse,
    FeedbackTelemetryResponse,
    HistoryResponse,
    MediaCapabilitiesResponse,
    MediaCreativeRequest,
    MediaJobResponse,
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
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
    RestoreCheckpointRequest,
    RestoreCheckpointResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
    RouteQualityResponse,
    RoutePolicyDiffResponse,
    RuntimeHealthResponse,
    TelemetryResponse,
    TelemetrySnapshot,
    TelemetrySnapshotPruneInfo,
    TelemetrySnapshotResponse,
    ValidationProfileResponse,
    ValidationProfileUpdateRequest,
    ValidateRequest,
    ValidateResponse,
    VerificationRequest,
    VerificationResponse,
    WorkspaceAutopilotStatusResponse,
    WorkspaceProfileResponse,
    WorkspaceProjectManifest,
    WorkspaceSetupRequest,
    WorkspaceSetupResponse,
)
from .settings import PROJECT_ROOT, clear_settings_cache, get_settings, has_env_file, update_env
from .workspace import WorkspaceManager


settings = get_settings()
workspace_manager = WorkspaceManager(PROJECT_ROOT, settings)
agent = AgentEngine(PROJECT_ROOT, settings)
creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
model_manager = ModelManager(PROJECT_ROOT, settings, model_registry)
model_benchmarks = ModelBenchmarkManager(PROJECT_ROOT, settings, model_registry)


_WORKSPACE_SNAPSHOT_TTL_SECONDS = 2.0
_WORKSPACE_SNAPSHOT_CACHE_MAX = 64
_PROJECT_PLAN_CACHE_TTL_SECONDS = 30.0
_PROJECT_PLAN_CACHE_MAX = 128


@dataclass(frozen=True)
class _WorkspaceStatusSnapshot:
    created_at: float
    manifest: Any
    dependency_profile: Any
    instruction_status: Any
    validation_plan: Any
    command_history: dict[str, Any]
    readiness: Any


@dataclass(frozen=True)
class _ProjectPlanCacheEntry:
    created_at: float
    response: ProjectScaffoldPlanResponse


_workspace_status_cache: dict[str, _WorkspaceStatusSnapshot] = {}
_project_plan_cache: dict[str, _ProjectPlanCacheEntry] = {}


def _normalized_cache_path(path: Path) -> str:
    return str(path.resolve()).rstrip("\\/").casefold()


def _cache_paths_are_related(left: str, right: str) -> bool:
    if left == right:
        return True
    return left.startswith(right + "\\") or right.startswith(left + "\\")


def _clear_workspace_status_cache(root: Path | None = None) -> None:
    if root is None:
        _workspace_status_cache.clear()
        return
    target = _normalized_cache_path(root)
    for key in list(_workspace_status_cache):
        if _cache_paths_are_related(key, target):
            _workspace_status_cache.pop(key, None)


def _clear_project_plan_cache() -> None:
    _project_plan_cache.clear()


def _invalidate_workspace_caches(root: Path | None = None) -> None:
    _clear_workspace_status_cache(root)
    _clear_project_plan_cache()


def _prune_workspace_status_cache() -> None:
    while len(_workspace_status_cache) > _WORKSPACE_SNAPSHOT_CACHE_MAX:
        oldest_key = min(_workspace_status_cache, key=lambda key: _workspace_status_cache[key].created_at)
        _workspace_status_cache.pop(oldest_key, None)


def _prune_project_plan_cache() -> None:
    while len(_project_plan_cache) > _PROJECT_PLAN_CACHE_MAX:
        oldest_key = min(_project_plan_cache, key=lambda key: _project_plan_cache[key].created_at)
        _project_plan_cache.pop(oldest_key, None)


def _workspace_status_snapshot(root: Path) -> _WorkspaceStatusSnapshot:
    key = _normalized_cache_path(root)
    now = time.monotonic()
    cached = _workspace_status_cache.get(key)
    if cached is not None and now - cached.created_at <= _WORKSPACE_SNAPSHOT_TTL_SECONDS:
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
    snapshot = _WorkspaceStatusSnapshot(
        created_at=now,
        manifest=manifest,
        dependency_profile=dependency_profile,
        instruction_status=instruction_status,
        validation_plan=validation_plan,
        command_history=command_history,
        readiness=readiness,
    )
    _workspace_status_cache[key] = snapshot
    _prune_workspace_status_cache()
    return snapshot


def _project_plan_cache_key(request: ProjectScaffoldPlanRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)


def _cached_project_plan(request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
    key = _project_plan_cache_key(request)
    now = time.monotonic()
    cached = _project_plan_cache.get(key)
    if cached is not None and now - cached.created_at <= _PROJECT_PLAN_CACHE_TTL_SECONDS:
        return cached.response.model_copy(deep=True)

    response = project_scaffolder().plan_from_prompt(request)
    _project_plan_cache[key] = _ProjectPlanCacheEntry(created_at=now, response=response.model_copy(deep=True))
    _prune_project_plan_cache()
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
    global settings, workspace_manager, agent, creative_media, model_registry, model_manager, model_benchmarks
    clear_settings_cache()
    _invalidate_workspace_caches()
    settings = get_settings()
    workspace_manager = WorkspaceManager(PROJECT_ROOT, settings)
    agent = AgentEngine(PROJECT_ROOT, settings)
    creative_media = CreativeMediaEngine(PROJECT_ROOT, settings)
    model_registry = ModelRegistryManager(PROJECT_ROOT, settings)
    model_manager = ModelManager(PROJECT_ROOT, settings, model_registry)
    model_benchmarks = ModelBenchmarkManager(PROJECT_ROOT, settings, model_registry)


app = FastAPI(title="Aegis Coding AI", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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


@app.get("/health", response_model=RuntimeHealthResponse, include_in_schema=False)
@app.get("/api/health", response_model=RuntimeHealthResponse)
async def health() -> RuntimeHealthResponse:
    return await runtime_health_snapshot()


@app.get("/ready", response_model=RuntimeHealthResponse, include_in_schema=False)
@app.get("/api/ready", response_model=RuntimeHealthResponse)
async def ready() -> RuntimeHealthResponse:
    return await runtime_health_snapshot()


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


@app.get("/api/media/jobs", response_model=list[MediaJobResponse])
async def list_media_jobs(
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


@app.post("/api/media/jobs", response_model=MediaJobResponse)
async def create_media_job(request: MediaCreativeRequest) -> MediaJobResponse:
    return creative_media.create_job(request)


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


def _workspace_setup_project_name(root: Path, requested: str = "") -> str:
    name = requested.strip() or root.name.strip() or "workspace"
    name = re.sub(r"[^A-Za-z0-9_. -]+", "", name).strip(" ._-")
    return name[:80] or "workspace"


def _workspace_setup_title(project_name: str, requested: str = "") -> str:
    title = requested.strip()
    if title:
        return title[:120]
    words = [word for word in re.split(r"[-_\s]+", project_name) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words)[:120] or "Workspace"


def _workspace_setup_stack_value(values: list[str], *, limit: int = 3) -> str:
    return " + ".join(item for item in values[:limit] if item)


def _workspace_setup_preset_id(project_type: str) -> str:
    text = project_type.strip().lower() or "detected-workspace"
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or "detected-workspace"


def _workspace_setup_manifest(
    root: Path,
    request: WorkspaceSetupRequest,
    *,
    dependency_profile: Any,
    install_command: str,
    validation_command: str,
) -> WorkspaceProjectManifest:
    project_name = _workspace_setup_project_name(root, request.project_name)
    project_type = str(getattr(dependency_profile, "project_type", "") or "").strip()
    preset_label = project_type or "Detected workspace"
    language = _workspace_setup_stack_value(list(getattr(dependency_profile, "languages", []) or []))
    framework = _workspace_setup_stack_value(list(getattr(dependency_profile, "frameworks", []) or []))
    package_manager = _workspace_setup_stack_value(list(getattr(dependency_profile, "package_managers", []) or []), limit=2)
    tags = ["workspace-setup"]
    for item in [project_type, language, framework, package_manager]:
        if item:
            tags.extend(part.strip().lower() for part in item.split("+") if part.strip())

    return WorkspaceProjectManifest(
        schema="aegis.project.v1",
        project_name=project_name,
        title=_workspace_setup_title(project_name, request.title),
        preset_id=_workspace_setup_preset_id(project_type),
        preset_label=preset_label,
        framework=framework,
        language=language,
        package_manager=package_manager,
        install_command=install_command,
        validation_command=validation_command,
        original_prompt="Workspace setup generated from detected project files.",
        tags=list(dict.fromkeys(tags))[:24],
        generated_by="Aegis Workspace Setup",
        mission_contract={
            "setup_source": "workspace_profile",
            "validation_command": validation_command,
            "install_command": install_command,
        },
        agent_handoff={
            "next_action": "Run validation and continue from the workspace readiness panel.",
        },
    )


def _merge_missing_manifest_fields(
    existing: WorkspaceProjectManifest,
    generated: WorkspaceProjectManifest,
) -> tuple[WorkspaceProjectManifest, bool]:
    payload = existing.model_dump(mode="json", by_alias=True)
    changed = False
    for key, value in generated.model_dump(mode="json", by_alias=True).items():
        if key in {"mission_contract", "agent_handoff", "tags"}:
            continue
        if value and not payload.get(key):
            payload[key] = value
            changed = True
    if generated.tags:
        tags = [str(item).strip() for item in payload.get("tags", []) if str(item).strip()]
        for tag in generated.tags:
            if tag not in tags:
                tags.append(tag)
                changed = True
        payload["tags"] = tags[:24]
    return WorkspaceProjectManifest(**payload), changed


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
    generated_manifest = _workspace_setup_manifest(
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
        manifest, changed = _merge_missing_manifest_fields(existing_manifest, generated_manifest)
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


def _latest_history_validation(command_history: dict[str, Any]) -> dict[str, Any]:
    commands = command_history.get("commands") if isinstance(command_history, dict) else []
    if not isinstance(commands, list):
        return {}
    for item in reversed(commands):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "validation" or kind.startswith("verification:"):
            return item
    return {}


def _status_value(value: Any, *, limit: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _first_diagnostic_brief(payload: dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return ""
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        file = _status_value(diagnostic.get("file"), limit=150)
        if not file:
            continue
        line = _status_value(diagnostic.get("line"), limit=20)
        column = _status_value(diagnostic.get("column"), limit=20)
        location = file
        if line:
            location += f":{line}"
        if column:
            location += f":{column}"
        severity = _status_value(diagnostic.get("severity"), limit=24)
        code = _status_value(diagnostic.get("code"), limit=32)
        detail = " ".join(part for part in (severity, code) if part)
        return f"{location} {detail}".strip()
    return ""


def _compact_repair_brief(payload: dict[str, Any], *, validation_command: str = "") -> str:
    failed_step = _status_value(payload.get("failed_step"), limit=40)
    failed_step_command = _status_value(payload.get("failed_step_command"), limit=220)
    failed_command = _status_value(payload.get("command") or validation_command, limit=220)
    diagnostic = _first_diagnostic_brief(payload)

    parts: list[str] = []
    if failed_step and failed_step_command:
        parts.append(f"Repair step {failed_step}: {failed_step_command}")
    elif failed_step_command:
        parts.append(f"Repair {failed_step_command}")
    elif diagnostic:
        parts.append(f"Repair diagnostic {diagnostic}")
    elif failed_command:
        parts.append(f"Repair {failed_command}")
    else:
        parts.append("Repair failed validation")

    if diagnostic and not parts[0].endswith(diagnostic):
        parts.append(f"diagnostic {diagnostic}")
    parts.append("rerun validation")
    return "; ".join(parts)


@app.get("/api/workspace/autopilot-status", response_model=WorkspaceAutopilotStatusResponse)
async def workspace_autopilot_status(workspace_root: str | None = Query(default=None)) -> WorkspaceAutopilotStatusResponse:
    root = _resolve_workspace_or_400(workspace_root)
    snapshot = _workspace_status_snapshot(root)
    manifest = snapshot.manifest
    dependency_profile = snapshot.dependency_profile
    instruction_status = snapshot.instruction_status
    validation_plan = snapshot.validation_plan
    command_history = snapshot.command_history
    readiness = snapshot.readiness

    validation_command = (
        validation_plan.validation_command
        or (manifest.validation_command if manifest else "")
        or (dependency_profile.validation_commands[0] if dependency_profile.validation_commands else "")
        or str(command_history.get("validation_command") or "").strip()
    )
    last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
    instruction_last_validation = (
        instruction_status.last_validation
        if isinstance(instruction_status.last_validation, dict)
        else {}
    )
    latest_validation = _latest_history_validation(command_history) or last_run or instruction_last_validation
    latest_validation_status = str(latest_validation.get("status") or "").strip()
    failed_step = str(latest_validation.get("failed_step") or "").strip()
    failed_step_command = str(latest_validation.get("failed_step_command") or "").strip()
    first_diagnostic = _first_diagnostic_brief(latest_validation)
    repair_brief = ""
    instruction_source = (
        instruction_status.schema_version
        or instruction_status.source_message
        or ("workspace instructions" if instruction_status.files else "")
    )
    next_open_items: list[str] = []
    seen_open_items: set[str] = set()
    for instruction_file in instruction_status.files:
        for item in instruction_file.pending_items:
            text = item.strip()
            key = text.casefold()
            if not text or key in seen_open_items:
                continue
            next_open_items.append(text)
            seen_open_items.add(key)
            if len(next_open_items) >= 12:
                break
        if len(next_open_items) >= 12:
            break

    dependency_signals = {
        str(value).strip().lower()
        for values in (
            dependency_profile.languages,
            dependency_profile.frameworks,
            dependency_profile.package_managers,
            dependency_profile.build_systems,
            dependency_profile.database_tools,
            dependency_profile.config_files,
        )
        for value in values
        if str(value).strip()
    }
    open_items_count = max(0, int(instruction_status.open_items or 0))
    total_items_count = max(0, int(instruction_status.total_items or 0))
    large_task_mode = (
        open_items_count >= 12
        or total_items_count >= 18
        or len(dependency_signals) >= 8
        or (readiness.status in {"needs_repair", "needs_validation"} and total_items_count >= 14)
    )
    if large_task_mode:
        complexity = "epic" if open_items_count >= 24 or total_items_count >= 32 or len(dependency_signals) >= 12 else "large"
    elif open_items_count >= 6 or total_items_count >= 10 or len(dependency_signals) >= 5:
        complexity = "standard"
    else:
        complexity = "focused"

    execution_lanes: list[str] = []

    def add_lane(value: str) -> None:
        if value and value not in execution_lanes:
            execution_lanes.append(value)

    stack_text = " ".join(
        [
            manifest.framework if manifest else "",
            manifest.language if manifest else "",
            manifest.package_manager if manifest else "",
            " ".join(manifest.tags) if manifest else "",
            " ".join(dependency_signals),
        ]
    ).lower()
    if any(term in stack_text for term in ("react", "vite", "next", "vue", "svelte", "frontend", "web")):
        add_lane("frontend")
    if any(term in stack_text for term in ("fastapi", "express", "django", "api", "server", "backend")):
        add_lane("backend")
    if any(term in stack_text for term in ("sqlite", "postgres", "mysql", "database", "prisma", "drizzle")):
        add_lane("database")
    if any(term in stack_text for term in ("c++", "cpp", "cmake", "msbuild", "sln", "vcxproj", "native", "dll", "exe")):
        add_lane("native")
    if any(term in stack_text for term in ("pytest", "vitest", "ctest", "test", "validation", "build")) or validation_command:
        add_lane("validation")
    if instruction_status.files:
        add_lane("roadmap")
    if not execution_lanes:
        execution_lanes = ["source", "validation", "handoff"]

    phase = "unconfigured"
    should_continue = False
    recommended_mode = "build"
    run_validation = False
    max_repair_attempts = 0
    pass_budget = 0
    stop_reason = ""
    next_action = readiness.next_action.strip()

    if readiness.status == "needs_repair":
        phase = "repair"
        should_continue = True
        recommended_mode = "develop"
        run_validation = True
        max_repair_attempts = 3
        pass_budget = 6
    elif readiness.status == "needs_validation":
        phase = "validate"
        should_continue = True
        recommended_mode = "develop"
        run_validation = True
        max_repair_attempts = 2
        pass_budget = 4
    elif readiness.status == "needs_work":
        phase = "work"
        should_continue = True
        recommended_mode = "build"
        run_validation = bool(validation_command)
        max_repair_attempts = 2 if validation_command else 0
        pass_budget = max(4, min(18, open_items_count + 4))
    elif readiness.status == "ready":
        phase = "ready"
        stop_reason = "Workspace readiness is ready; no open tracked work or failed validation is blocking handoff."
        pass_budget = 0
    else:
        stop_reason = "Workspace is not configured enough for safe autopilot continuation."
        pass_budget = 0

    if should_continue and large_task_mode:
        if phase == "work":
            if complexity == "epic":
                pass_budget = max(pass_budget, min(50, max(30, open_items_count + 12, total_items_count)))
            else:
                pass_budget = max(pass_budget, min(36, max(22, open_items_count + 8)))
        elif phase == "repair":
            pass_budget = max(pass_budget, 14 if complexity == "epic" else 10)
            max_repair_attempts = max(max_repair_attempts, 4)
        elif phase == "validate":
            pass_budget = max(pass_budget, 10 if complexity == "epic" else 7)
            max_repair_attempts = max(max_repair_attempts, 3)

    if not next_action:
        if phase == "repair":
            next_action = "Repair the captured validation failure and rerun validation."
        elif phase == "validate":
            next_action = f"Run validation command: {validation_command}" if validation_command else "Infer and run validation."
        elif phase == "work":
            next_action = "Continue the next open project instruction item, then validate."
        elif phase == "ready":
            next_action = "Summarize the finished state and suggest the next milestone."
        else:
            next_action = "Add project metadata and a validation command."

    if phase == "repair" and latest_validation:
        repair_brief = _compact_repair_brief(latest_validation, validation_command=validation_command)

    suggested_prompt = next_action
    if should_continue:
        suggested_prompt = (
            "Continue autopilot from the current workspace state.\n\n"
            f"Objective: {next_action}\n"
            f"Phase: {phase}\n"
            f"Validation command: {validation_command or 'infer if needed'}"
        )
        if repair_brief:
            suggested_prompt += f"\nRepair brief: {repair_brief}"
        if large_task_mode:
            suggested_prompt += (
                "\nLarge-task protocol:\n"
                "- Keep the current target path, stack, and project type pinned.\n"
                "- Complete one coherent vertical slice before broadening scope.\n"
                "- Update TODO/roadmap/checklist state as items are completed.\n"
                "- Capture validation output, repair obvious failures, and summarize remaining blockers.\n"
                f"- Execution lanes: {', '.join(execution_lanes)}"
            )
        if next_open_items:
            suggested_prompt += "\nNext open instruction items:\n" + "\n".join(
                f"- {item}" for item in next_open_items[:6]
            )

    recommendations: list[str] = []
    if should_continue:
        recommendations.append(f"Autopilot can continue for up to {pass_budget} pass(es) before reassessing readiness.")
    if repair_brief:
        recommendations.append(f"Repair brief: {repair_brief}.")
    if phase == "repair" and failed_step:
        recommendations.append(f"Start with failed validation step: {failed_step}.")
    if phase == "repair" and failed_step_command:
        recommendations.append(f"Failed command: {failed_step_command}.")
    if phase == "repair" and first_diagnostic:
        recommendations.append(f"First diagnostic: {first_diagnostic}.")
    if validation_command and run_validation:
        recommendations.append(f"Run validation after implementation or repair: {validation_command}.")
    if instruction_status.open_items:
        recommendations.append(f"Work through {instruction_status.open_items} open instruction item(s) before adding unrelated scope.")
    if large_task_mode:
        recommendations.append(
            f"Large-task mode is active ({complexity}); continue in vertical slices across {', '.join(execution_lanes)}."
        )
    if stop_reason:
        recommendations.append(stop_reason)

    return WorkspaceAutopilotStatusResponse(
        workspace_root=str(root),
        phase=phase,
        should_continue=should_continue,
        recommended_mode=recommended_mode,
        suggested_prompt=suggested_prompt,
        next_action=next_action,
        stop_reason=stop_reason,
        pass_budget=pass_budget,
        run_validation=run_validation,
        max_repair_attempts=max_repair_attempts,
        complexity=complexity,
        large_task_mode=large_task_mode,
        estimated_passes_remaining=pass_budget if should_continue else 0,
        execution_lanes=execution_lanes,
        readiness=readiness,
        open_items=instruction_status.open_items,
        completed_items=instruction_status.completed_items,
        total_items=instruction_status.total_items,
        validation_command=validation_command,
        latest_validation_status=latest_validation_status,
        failed_step=failed_step,
        failed_step_command=failed_step_command,
        first_diagnostic=first_diagnostic,
        repair_brief=repair_brief,
        blockers=readiness.blockers,
        signals=readiness.signals,
        recommendations=recommendations,
        instruction_files=instruction_status.files[:12],
        next_open_items=next_open_items,
        instruction_source=instruction_source,
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


@app.get("/")
async def root() -> dict:
    return {"message": "Aegis Coding AI API is running.", "ui": "http://127.0.0.1:5173"}


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
