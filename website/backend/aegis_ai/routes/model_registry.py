from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from ..model_benchmark import ModelBenchmarkManager
from ..model_manager import ModelManager
from ..model_registry import ModelRegistryManager
from ..schemas import (
    ModelBenchmarkJobInfo,
    ModelBenchmarkRunRequest,
    ModelBenchmarkSnapshot,
    ModelDeleteRequest,
    ModelManagerResponse,
    ModelOperationInfo,
    ModelPullRequest,
    ModelRegistryAuditResponse,
    ModelRegistryBenchmarkPreviewResponse,
    ModelRegistryCheckpointCreateRequest,
    ModelRegistryCheckpointDiffResponse,
    ModelRegistryCheckpointInfo,
    ModelRegistryCheckpointListResponse,
    ModelRegistryProviderUpsertRequest,
    ModelRegistryResponse,
)
from ..services.core_client import AegisCoreClient


WorkspaceResolver = Callable[[str | None], Path]
ModelRegistryMerger = Callable[[ModelRegistryResponse, dict[str, Any]], ModelRegistryResponse]


def register_model_registry_routes(
    app: FastAPI,
    *,
    project_root: Path,
    model_registry_factory: Callable[[], ModelRegistryManager],
    model_benchmarks_factory: Callable[[], ModelBenchmarkManager],
    model_manager_factory: Callable[[], ModelManager],
    agent_factory: Callable[[], Any],
    core_runtime_client_factory: Callable[[], AegisCoreClient],
    workspace_resolver: WorkspaceResolver,
    core_registry_merger: ModelRegistryMerger,
) -> None:
    @app.get("/api/model-registry", response_model=ModelRegistryResponse)
    async def model_registry_snapshot() -> ModelRegistryResponse:
        registry = model_registry_factory().snapshot()
        core_client = core_runtime_client_factory()
        core_result = await core_client.model_registry(project_root)
        if core_result.delegated and core_result.ok and isinstance(core_result.data, dict):
            return core_registry_merger(registry, core_result.data)
        if core_result.should_fallback:
            core_client.record_fallback("model.registry", core_result.error or "Core model registry unavailable.")
        return registry

    @app.get("/api/model-registry/audit", response_model=ModelRegistryAuditResponse)
    async def model_registry_audit(workspace_root: str | None = Query(default=None)) -> ModelRegistryAuditResponse:
        root = workspace_resolver(workspace_root)
        store = agent_factory().store
        return model_registry_factory().audit(
            model_attempts=store.recent_model_attempts(project_root=root, limit=200),
            route_health=store.route_health_signals(project_root=root, limit=200),
        )

    @app.post("/api/model-registry/providers", response_model=ModelRegistryResponse)
    async def upsert_model_registry_provider(request: ModelRegistryProviderUpsertRequest) -> ModelRegistryResponse:
        try:
            return model_registry_factory().upsert_provider(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/model-registry/providers/{provider_id}", response_model=ModelRegistryResponse)
    async def delete_model_registry_provider(provider_id: str) -> ModelRegistryResponse:
        try:
            return model_registry_factory().delete_provider(provider_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model registry provider not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/model-registry/apply-benchmark-winners", response_model=ModelRegistryResponse)
    async def apply_benchmark_winners_to_model_registry(
        workspace_root: str | None = Query(default=None),
    ) -> ModelRegistryResponse:
        root = workspace_resolver(workspace_root)
        try:
            route_health = agent_factory().store.route_health_signals(project_root=root, limit=200)
            return model_registry_factory().apply_benchmark_winners(
                model_benchmarks_factory().snapshot().provider_scores,
                route_health=route_health,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/model-registry/benchmark-winners-preview", response_model=ModelRegistryBenchmarkPreviewResponse)
    async def preview_benchmark_winners_for_model_registry(
        workspace_root: str | None = Query(default=None),
    ) -> ModelRegistryBenchmarkPreviewResponse:
        root = workspace_resolver(workspace_root)
        route_health = agent_factory().store.route_health_signals(project_root=root, limit=200)
        return model_registry_factory().preview_benchmark_winners(
            model_benchmarks_factory().snapshot().provider_scores,
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
        root = workspace_resolver(workspace_root)
        diff = agent_factory().store.route_policy_diff(
            project_root=root,
            limit=limit,
            use_snapshot=True,
            stale_after_seconds=900,
            min_attempts=min_attempts,
        )
        return model_registry_factory().apply_policy_diff(
            diff,
            min_confidence=min_confidence,
            allow_high_risk=allow_high_risk,
        )

    @app.get("/api/model-registry/checkpoints", response_model=ModelRegistryCheckpointListResponse)
    async def model_registry_checkpoints(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> ModelRegistryCheckpointListResponse:
        return model_registry_factory().checkpoints(limit=limit)

    @app.post("/api/model-registry/checkpoints", response_model=ModelRegistryCheckpointInfo)
    async def create_model_registry_checkpoint(
        request: ModelRegistryCheckpointCreateRequest,
    ) -> ModelRegistryCheckpointInfo:
        try:
            return model_registry_factory().create_checkpoint(request.reason)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/model-registry/checkpoints/{checkpoint_id}/diff", response_model=ModelRegistryCheckpointDiffResponse)
    async def model_registry_checkpoint_diff(checkpoint_id: str) -> ModelRegistryCheckpointDiffResponse:
        try:
            return model_registry_factory().checkpoint_diff(checkpoint_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model registry checkpoint not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/model-registry/checkpoints/{checkpoint_id}/restore", response_model=ModelRegistryResponse)
    async def restore_model_registry_checkpoint(checkpoint_id: str) -> ModelRegistryResponse:
        try:
            return model_registry_factory().restore_checkpoint(checkpoint_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model registry checkpoint not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/model-manager", response_model=ModelManagerResponse)
    async def model_manager_snapshot(
        minimum_free_gb: float = Query(default=24.0, ge=0.0, le=500.0),
    ) -> ModelManagerResponse:
        return model_manager_factory().snapshot(minimum_free_gb=minimum_free_gb)

    @app.post("/api/model-manager/pull", response_model=ModelOperationInfo)
    async def pull_model(request: ModelPullRequest) -> ModelOperationInfo:
        try:
            return model_manager_factory().pull_model(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/model-manager/delete", response_model=ModelOperationInfo)
    async def delete_local_model(request: ModelDeleteRequest) -> ModelOperationInfo:
        try:
            return model_manager_factory().delete_model(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/model-benchmarks", response_model=ModelBenchmarkSnapshot)
    async def model_benchmark_snapshot() -> ModelBenchmarkSnapshot:
        return model_benchmarks_factory().snapshot()

    @app.post("/api/model-benchmarks/run", response_model=ModelBenchmarkSnapshot)
    async def run_model_benchmarks(request: ModelBenchmarkRunRequest) -> ModelBenchmarkSnapshot:
        try:
            return await model_benchmarks_factory().run(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update model benchmark records: {exc}") from exc

    @app.get("/api/model-benchmarks/jobs", response_model=list[ModelBenchmarkJobInfo])
    async def model_benchmark_jobs() -> list[ModelBenchmarkJobInfo]:
        return model_benchmarks_factory().jobs()

    @app.post("/api/model-benchmarks/jobs", response_model=ModelBenchmarkJobInfo)
    async def start_model_benchmark_job(request: ModelBenchmarkRunRequest) -> ModelBenchmarkJobInfo:
        try:
            return model_benchmarks_factory().start_job(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update model benchmark records: {exc}") from exc

    @app.post("/api/model-benchmarks/jobs/{job_id}/cancel", response_model=ModelBenchmarkJobInfo)
    async def cancel_model_benchmark_job(job_id: str) -> ModelBenchmarkJobInfo:
        try:
            return model_benchmarks_factory().cancel_job(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update model benchmark records: {exc}") from exc
