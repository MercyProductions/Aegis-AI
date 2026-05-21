from pathlib import Path
from typing import Any

from .agent import continue_from_roadmap, repair_from_last_validation
from .branding import branding_tokens
from .clients import ClientRegistryPersistenceError, list_clients, register_client
from .config import ConfigPersistenceError, load_config, update_config, write_default_config
from .contracts import (
    AlphaDiagnosticsExportRequest,
    AlphaFeatureFlagsRequest,
    AlphaFeedbackRequest,
    ApplyChangesRequest,
    AgentDelegationRequest,
    AutopilotActionRequest,
    AutopilotStartRequest,
    BenchmarkRunRequest,
    CheckpointCreateRequest,
    CheckpointRestoreRequest,
    ClientRegistrationRequest,
    ClientSyncRequest,
    CollaborationApprovalDecisionRequest,
    CollaborationApprovalRequest,
    CollaborationMemberRequest,
    CollaborationRepositoryRequest,
    CollaborationRoadmapItemRequest,
    CollaborationWorkflowActionRequest,
    CollaborationWorkflowRequest,
    ContinueRequest,
    CreateTaskRequest,
    DeploymentPipelineValidationRequest,
    DeploymentWorkflowActionRequest,
    DeploymentWorkflowRequest,
    DogfoodingEventRequest,
    EngineeringExecutionActionRequest,
    EngineeringExecutionCreateRequest,
    EngineeringIntelligenceBenchmarkRequest,
    EngineeringIntelligenceRequest,
    EngineeringMemoryRequest,
    EngineeringRoadmapExecuteRequest,
    EngineeringWorkspaceSearchRequest,
    EcosystemMaturityRequest,
    EcosystemObservabilityRequest,
    EvaluationReportRequest,
    GovernanceComplianceExportRequest,
    GovernancePolicyEvaluationRequest,
    GovernancePolicyRequest,
    IntelligenceBenchmarkRequest,
    IntelligenceDatasetRequest,
    IntelligenceDistributedInferenceRequest,
    IntelligenceModelLifecycleRequest,
    IntelligenceRetrievalRequest,
    IntelligenceRoutingRequest,
    IntelligenceStackRequest,
    JobRunRequest,
    KnowledgeImpactAnalysisRequest,
    KnowledgeQueryRequest,
    KnowledgeRelationshipsRequest,
    KnowledgeSearchRequest,
    KnowledgeSymbolRequest,
    ModelCompletionRequest,
    ModelRouteRequest,
    OnboardingFirstWorkflowRequest,
    OnboardingUpdateRequest,
    OptimizationExperimentAdoptRequest,
    OptimizationExperimentRequest,
    OptimizationExperimentRollbackRequest,
    OptimizationExperimentRunRequest,
    OperationsRequest,
    OrchestrationPlanRequest,
    OrchestrationStepRequest,
    PlatformArchiveRequest,
    PlatformCompatibilityRequest,
    PlatformMigrationRequest,
    PlatformSustainabilityRequest,
    PersonalMemoryArchiveRequest,
    PersonalMemoryCleanupRequest,
    PersonalMemoryContextRequest,
    PersonalMemoryControlsRequest,
    PersonalMemoryCreateRequest,
    PersonalMemoryDeleteRequest,
    PersonalMemoryExportRequest,
    PersonalMemoryImportRequest,
    PersonalMemoryQueryRequest,
    PersonalMemoryUpdateRequest,
    PersonalIntelligenceRequest,
    PluginStateRequest,
    PluginToolRunRequest,
    ProposeChangesRequest,
    ProviderKeyRequest,
    QualityGateEvaluateRequest,
    ReleaseCompatibilityRequest,
    ReleaseMigrationRequest,
    ReleaseUpdatePlanRequest,
    RuntimeNodeHeartbeatRequest,
    RuntimeNodeRegisterRequest,
    RuntimeNodeRevokeRequest,
    RuntimeJobActionRequest,
    RuntimeRecoveryRequest,
    RuntimeSessionRequest,
    RuntimeSessionSyncRequest,
    RuntimeTerminalJobRequest,
    RuntimeVoiceCommandRequest,
    RuntimeWorkloadActionRequest,
    RuntimeWorkloadRequest,
    SimulationCompareRequest,
    SimulationRequest,
    SettingsImportRequest,
    SettingsRequest,
    TaskStatusRequest,
    ValidateRequest,
    ValidationRunRequest,
    WorkflowActionRequest,
    WorkflowCreateRequest,
    WorkspaceIntelligenceRequest,
    WorkspaceRequest,
    make_envelope,
)
from .credentials import CredentialStoreError
from .diagnostics import CoreLogger
from . import alpha as alpha_runtime
from . import agent_runtime
from . import autopilot as autopilot_runtime
from . import collaboration_runtime
from .collaboration_runtime import CollaborationRuntimeError
from . import deployment_intelligence
from .deployment_intelligence import DeploymentIntelligenceError
from . import dogfooding as dogfooding_runtime
from . import distributed_runtime
from .distributed_runtime import DistributedRuntimeError
from . import editing as editing_runtime
from .editing import CheckpointNotFoundError, EditingPersistenceError, UnsafePathError
from . import engineering_execution
from .engineering_execution import EngineeringExecutionNotFoundError, EngineeringExecutionPersistenceError
from . import engineering_intelligence
from . import engineering_workspace
from . import intelligence_stack
from . import ecosystem_maturity
from .ecosystem import dashboard_summary, diagnostics_summary, shared_memory_summary
from .jobs import JobPersistenceError, jobs_dashboard, run_job
from .knowledge import (
    KnowledgePersistenceError,
    architecture_summary,
    impact_analysis,
    knowledge_graph,
    knowledge_relationships,
    knowledge_symbol,
    query_knowledge_graph,
    search_knowledge,
)
from .model_router import (
    complete_with_route,
    delete_provider_key,
    model_registry,
    provider_inventory,
    route_model,
    routing_profiles,
    store_provider_key,
)
from .multi_agent import agent_roster
from . import onboarding as onboarding_runtime
from .ollama import OllamaClient
from .operations import engineering_operations_dashboard
from .orchestration import OrchestrationPersistenceError, advance_orchestration_step, create_orchestration_plan, orchestration_dashboard
from .personal_intelligence import PersonalIntelligencePersistenceError, adaptive_personal_intelligence, reset_personal_intelligence
from . import personal_memory
from .personal_memory import PersonalMemoryPersistenceError
from . import platform_foundation
from . import plugin_runtime
from .plugin_runtime import PluginRuntimeError
from . import product_identity
from .quality import QualityPersistenceError, quality_dashboard, record_quality_snapshot
from . import quality_gates
from .quality_gates import QualityGateEvaluationNotFoundError, QualityGatePersistenceError
from . import release as release_runtime
from .roadmap import RoadmapPersistenceError, generate_roadmap
from . import runtime_interaction
from .runtime_interaction import RuntimeInteractionError, RuntimeJobNotFoundError
from . import security as security_runtime
from . import stabilization as stabilization_runtime
from .simulation import compare_scenarios, simulate_change
from . import system_optimization
from .system_optimization import OptimizationExperimentNotFoundError, SystemOptimizationError
from .tasks import TaskStorePersistenceError, create_task, list_tasks, update_task_status
from .validation import run_validation, validation_summary
from .workflow_runtime import WorkflowNotFoundError, WorkflowPersistenceError
from . import workflow_runtime
from . import governance_runtime
from .governance_runtime import GovernanceRuntimeError
from .workspace_intelligence import workspace_intelligence
from .workspace import WorkspaceScanner


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install Aegis Core API dependencies with `pip install -e .`.") from exc

    app = FastAPI(title="Aegis Core", version="0.1.0")
    security_runtime.install_security_middleware(app)

    def envelope(kind: str, data: Any, workspace: str | None = None, ok: bool = True) -> dict[str, Any]:
        return make_envelope(kind, data, workspace, ok)

    @app.get("/health")
    def health(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        config = load_config(root)
        ollama = OllamaClient(config).health()
        log = CoreLogger(root)
        log.log("health", f"ollama_reachable={ollama.reachable}")
        return {
            "ok": True,
            "workspace": str(root),
            "config": config.to_dict(),
            "ollama": ollama.__dict__,
        }

    @app.get("/models")
    def models(workspace: str | None = None) -> dict[str, Any]:
        config = load_config(workspace)
        return OllamaClient(config).health().__dict__

    @app.post("/workspace/scan")
    def scan(request: WorkspaceRequest) -> dict[str, Any]:
        return WorkspaceScanner(request.workspace).scan(persist=True)

    @app.post("/workspace/roadmap")
    def roadmap(request: WorkspaceRequest) -> dict[str, Any]:
        try:
            return generate_roadmap(request.workspace, persist=True)
        except RoadmapPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/validation")
    def validate(request: ValidateRequest) -> dict[str, Any]:
        if request.run:
            return run_validation(request.workspace, command=request.command)
        return validation_summary(request.workspace)

    @app.post("/agent/continue")
    def continue_agent(request: ContinueRequest) -> dict[str, Any]:
        return continue_from_roadmap(request.workspace, request.request)

    @app.post("/agent/repair")
    def repair(request: WorkspaceRequest) -> dict[str, Any]:
        return repair_from_last_validation(request.workspace)

    @app.post("/config/init")
    def init_config(request: WorkspaceRequest) -> dict[str, Any]:
        path = write_default_config(request.workspace)
        return {"path": str(path)}

    @app.get("/v1/health")
    def v1_health(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("health", health(str(root)), str(root))

    @app.get("/v1/security/status")
    def v1_security_status(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("security.status", security_runtime.security_status(str(root)), str(root))

    @app.get("/v1/release/manifest")
    def v1_release_manifest(workspace: str | None = None) -> dict[str, Any]:
        return envelope("release.manifest", release_runtime.release_manifest(workspace), workspace)

    @app.post("/v1/release/compatibility")
    def v1_release_compatibility(request: ReleaseCompatibilityRequest) -> dict[str, Any]:
        data = release_runtime.check_compatibility(
            request.client_type,
            request.client_version,
            schema_version=request.schema_version,
            core_version=request.core_version,
            capabilities=request.capabilities,
            workspace=request.workspace,
        )
        return envelope("release.compatibility", data, request.workspace, ok=bool(data.get("compatible", False)))

    @app.get("/v1/release/migrations")
    def v1_release_migrations(workspace: str) -> dict[str, Any]:
        try:
            data = release_runtime.migration_status(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("release.migrations", data, workspace)

    @app.post("/v1/release/migrations/run")
    def v1_release_run_migrations(request: ReleaseMigrationRequest) -> dict[str, Any]:
        try:
            data = release_runtime.run_migrations(request.workspace, dry_run=request.dry_run)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("release.migrations.run", data, request.workspace)

    @app.post("/v1/release/update-plan")
    def v1_release_update_plan(request: ReleaseUpdatePlanRequest) -> dict[str, Any]:
        data = release_runtime.update_plan(
            request.component_id,
            current_version=request.current_version,
            target_version=request.target_version,
            package_uri=request.package_uri,
            sha256=request.sha256,
        )
        return envelope("release.update_plan", data, ok=not data.get("blockers"))

    @app.get("/v1/models")
    def v1_models(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("models", models(str(root)), str(root))

    @app.get("/v1/providers")
    def v1_providers(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("model.providers", provider_inventory(str(root)), str(root))

    @app.get("/v1/models/providers")
    def v1_model_providers(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("model.providers", provider_inventory(str(root)), str(root))

    @app.get("/v1/models/registry")
    def v1_model_registry(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("model.registry", model_registry(str(root)), str(root))

    @app.get("/v1/models/routing-profiles")
    def v1_model_routing_profiles() -> dict[str, Any]:
        return envelope("model.routing_profiles", routing_profiles())

    @app.post("/v1/models/route")
    def v1_model_route(request: ModelRouteRequest) -> dict[str, Any]:
        data = route_model(
            request.workspace,
            request.task_type,
            request.difficulty,
            allow_cloud=request.allow_cloud,
            cloud_approved=request.cloud_approved,
            context_files=request.context_files,
            local_failure_reason=request.local_failure_reason,
            preferred_provider=request.provider_id,
            preferred_model=request.model,
            route_profile=request.route_profile,
            workflow_type=request.workflow_type,
            required_capabilities=request.required_capabilities,
            privacy_sensitive=request.privacy_sensitive,
        )
        return envelope("model.route", data, request.workspace)

    @app.post("/v1/models/completions")
    def v1_model_completion(request: ModelCompletionRequest) -> dict[str, Any]:
        try:
            data = complete_with_route(
                request.workspace,
                request.prompt,
                request.task_type,
                request.difficulty,
                allow_cloud=request.allow_cloud,
                cloud_approved=request.cloud_approved,
                context_files=request.context_files,
                local_failure_reason=request.local_failure_reason,
                provider_id=request.provider_id,
                model=request.model,
                route_profile=request.route_profile,
                workflow_type=request.workflow_type,
                required_capabilities=request.required_capabilities,
                privacy_sensitive=request.privacy_sensitive,
                timeout=max(1, min(900, request.timeout_seconds)),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (CredentialStoreError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("model.completion", data, request.workspace)

    @app.post("/v1/providers/{provider_id}/key")
    def v1_store_provider_key(provider_id: str, request: ProviderKeyRequest) -> dict[str, Any]:
        try:
            data = store_provider_key(provider_id, request.api_key)
        except CredentialStoreError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("provider.key.status", data)

    @app.delete("/v1/providers/{provider_id}/key")
    def v1_delete_provider_key(provider_id: str) -> dict[str, Any]:
        try:
            data = delete_provider_key(provider_id)
        except CredentialStoreError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("provider.key.status", data)

    @app.get("/v1/settings")
    def v1_settings(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("settings", load_config(root).to_dict(), str(root))

    @app.post("/v1/settings")
    def v1_update_settings(request: SettingsRequest) -> dict[str, Any]:
        try:
            config = update_config(request.workspace, request.settings)
        except ConfigPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("settings.updated", config.to_dict(), request.workspace)

    @app.get("/v1/onboarding/status")
    def v1_onboarding_status(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("onboarding.status", onboarding_runtime.onboarding_status(str(root)), str(root))

    @app.post("/v1/onboarding")
    def v1_update_onboarding(request: OnboardingUpdateRequest) -> dict[str, Any]:
        try:
            data = onboarding_runtime.update_onboarding(
                request.workspace,
                completed_steps=request.completed_steps,
                current_step=request.current_step,
                preferences=request.preferences,
                first_workflow_completed_steps=request.first_workflow_completed_steps,
                reset=request.reset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("onboarding.updated", data, request.workspace)

    @app.post("/v1/onboarding/first-workflow")
    def v1_onboarding_first_workflow(request: OnboardingFirstWorkflowRequest) -> dict[str, Any]:
        try:
            data = onboarding_runtime.run_first_workflow(
                request.workspace,
                request.action,
                dry_run=request.dry_run,
                source_client=request.source_client,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("onboarding.first_workflow", data, request.workspace)

    @app.get("/v1/settings/export")
    def v1_export_settings(workspace: str) -> dict[str, Any]:
        try:
            data = onboarding_runtime.export_settings(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("settings.export", data, workspace)

    @app.post("/v1/settings/import")
    def v1_import_settings(request: SettingsImportRequest) -> dict[str, Any]:
        try:
            data = onboarding_runtime.import_settings(request.workspace, request.settings, dry_run=request.dry_run)
        except ConfigPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("settings.import", data, request.workspace)

    @app.get("/v1/plugins")
    def v1_plugins(workspace: str, include_disabled: bool = True, refresh: bool = True) -> dict[str, Any]:
        try:
            data = plugin_runtime.plugin_dashboard(workspace, include_disabled=include_disabled, refresh=refresh)
        except PluginRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("plugin.dashboard", data, workspace)

    @app.post("/v1/plugins/state")
    def v1_plugin_state(request: PluginStateRequest) -> dict[str, Any]:
        try:
            data = plugin_runtime.set_plugin_state(
                request.workspace,
                request.plugin_id,
                enabled=request.enabled,
                trusted=request.trusted,
                approval=request.approval,
                reason=request.reason,
            )
        except PluginRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("plugin.state", data, request.workspace)

    @app.get("/v1/plugins/hooks")
    def v1_plugin_hooks(workspace: str, workflow_type: str | None = None) -> dict[str, Any]:
        try:
            data = plugin_runtime.plugin_hooks(workspace, workflow_type=workflow_type)
        except PluginRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("plugin.hooks", data, workspace)

    @app.post("/v1/plugins/tools/run")
    def v1_plugin_tool_run(request: PluginToolRunRequest) -> dict[str, Any]:
        try:
            data = plugin_runtime.run_tool(
                request.workspace,
                request.plugin_id,
                request.tool_name,
                request.input,
                dry_run=request.dry_run,
                approval=request.approval,
                workflow_type=request.workflow_type,
                source_client=request.source_client,
            )
        except PluginRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("plugin.tool.run", data, request.workspace, ok=bool(data.get("ok", False)))

    @app.get("/v1/distributed-runtime")
    def v1_distributed_runtime(workspace: str, include_audit: bool = True, limit: int = 50) -> dict[str, Any]:
        try:
            data = distributed_runtime.runtime_dashboard(workspace, include_audit=include_audit, limit=limit)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.runtime", data, workspace)

    @app.get("/v1/distributed-runtime/nodes")
    def v1_distributed_nodes(workspace: str) -> dict[str, Any]:
        try:
            data = distributed_runtime.list_nodes(workspace)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.nodes", data, workspace)

    @app.post("/v1/distributed-runtime/nodes/register")
    def v1_register_runtime_node(request: RuntimeNodeRegisterRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.register_node(
                request.workspace,
                node_id=request.node_id,
                name=request.name,
                node_type=request.node_type,
                endpoint=request.endpoint,
                capabilities=request.capabilities,
                cpu=request.cpu,
                gpu=request.gpu,
                ram_gb=request.ram_gb,
                storage_gb=request.storage_gb,
                supported_workflow_types=request.supported_workflow_types,
                installed_models=request.installed_models,
                installed_plugins=request.installed_plugins,
                permission_scopes=request.permission_scopes,
                max_parallel_workloads=request.max_parallel_workloads,
                isolation=request.isolation,
                auth_token=request.auth_token,
                approval=request.approval,
                metadata=request.metadata,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.node.registered", data, request.workspace, ok=bool(data.get("node", {}).get("eligible", False)))

    @app.post("/v1/distributed-runtime/nodes/{node_id}/heartbeat")
    def v1_runtime_node_heartbeat(node_id: str, request: RuntimeNodeHeartbeatRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.heartbeat_node(
                request.workspace,
                node_id,
                status=request.status,
                health=request.health,
                current_workload_ids=request.current_workload_ids,
                workload_count=request.workload_count,
                capabilities=request.capabilities,
                installed_models=request.installed_models,
                installed_plugins=request.installed_plugins,
                metadata=request.metadata,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.node.heartbeat", data, request.workspace)

    @app.post("/v1/distributed-runtime/nodes/{node_id}/revoke")
    def v1_runtime_node_revoke(node_id: str, request: RuntimeNodeRevokeRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.revoke_node(request.workspace, node_id, reason=request.reason)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.node.revoked", data, request.workspace)

    @app.get("/v1/distributed-runtime/workloads")
    def v1_distributed_workloads(workspace: str, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        try:
            data = distributed_runtime.list_workloads(workspace, status=status, limit=limit)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workloads", data, workspace)

    @app.post("/v1/distributed-runtime/workloads")
    def v1_create_distributed_workload(request: RuntimeWorkloadRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.create_workload(
                request.workspace,
                workload_type=request.workload_type,
                workflow_type=request.workflow_type,
                title=request.title,
                priority=request.priority,
                required_capabilities=request.required_capabilities,
                permission_scopes=request.permission_scopes,
                allow_remote=request.allow_remote,
                preferred_node_id=request.preferred_node_id,
                payload=request.payload,
                dry_run=request.dry_run,
                approval=request.approval,
                max_attempts=request.max_attempts,
                source_client=request.source_client,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workload.created", data, request.workspace)

    @app.post("/v1/distributed-runtime/dispatch")
    def v1_create_and_dispatch_distributed_workload(request: RuntimeWorkloadRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.create_and_dispatch_workload(
                request.workspace,
                workload_type=request.workload_type,
                workflow_type=request.workflow_type,
                title=request.title,
                priority=request.priority,
                required_capabilities=request.required_capabilities,
                permission_scopes=request.permission_scopes,
                allow_remote=request.allow_remote,
                preferred_node_id=request.preferred_node_id,
                payload=request.payload,
                dry_run=request.dry_run,
                approval=request.approval,
                max_attempts=request.max_attempts,
                source_client=request.source_client,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workload.dispatch", data, request.workspace, ok=bool(data.get("dispatched", False)))

    @app.get("/v1/distributed-runtime/workloads/{workload_id}")
    def v1_distributed_workload(workload_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = distributed_runtime.get_workload(workspace, workload_id)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return envelope("distributed.workload.lookup", data, workspace)

    @app.post("/v1/distributed-runtime/workloads/{workload_id}/dispatch")
    def v1_dispatch_distributed_workload(workload_id: str, request: RuntimeWorkloadActionRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.dispatch_workload(
                request.workspace,
                workload_id,
                preferred_node_id=request.preferred_node_id,
                allow_remote=request.allow_remote,
                approval=request.approval,
                dry_run=request.dry_run,
                payload=request.payload,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workload.dispatch", data, request.workspace, ok=bool(data.get("dispatched", False)))

    @app.post("/v1/distributed-runtime/workloads/{workload_id}/retry")
    def v1_retry_distributed_workload(workload_id: str, request: RuntimeWorkloadActionRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.retry_workload(
                request.workspace,
                workload_id,
                approval=request.approval,
                allow_remote=request.allow_remote,
                preferred_node_id=request.preferred_node_id,
                dispatch=request.dispatch,
            )
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workload.action", data, request.workspace, ok=bool(data.get("retried", False) or data.get("dispatched", False)))

    @app.post("/v1/distributed-runtime/workloads/{workload_id}/cancel")
    def v1_cancel_distributed_workload(workload_id: str, request: RuntimeWorkloadActionRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.cancel_workload(request.workspace, workload_id, reason=request.reason)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.workload.action", data, request.workspace, ok=bool(data.get("cancelled", False)))

    @app.post("/v1/distributed-runtime/recover")
    def v1_recover_distributed_runtime(request: RuntimeRecoveryRequest) -> dict[str, Any]:
        try:
            data = distributed_runtime.recover_runtime(request.workspace, auto_dispatch=request.auto_dispatch)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.recovery", data, request.workspace)

    @app.get("/v1/distributed-runtime/observability")
    def v1_distributed_observability(workspace: str) -> dict[str, Any]:
        try:
            data = distributed_runtime.observability(workspace)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.observability", data, workspace)

    @app.get("/v1/distributed-runtime/audit")
    def v1_distributed_audit(workspace: str, limit: int = 100) -> dict[str, Any]:
        try:
            data = distributed_runtime.audit_events(workspace, limit=limit)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.audit", data, workspace)

    @app.get("/v1/distributed-runtime/deployment/bootstrap")
    def v1_distributed_bootstrap(workspace: str, node_type: str = "validation", shell: str = "powershell") -> dict[str, Any]:
        try:
            data = distributed_runtime.deployment_bootstrap(workspace, node_type=node_type, shell=shell)
        except DistributedRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("distributed.deployment", data, workspace)

    @app.get("/v1/runtime/terminals")
    def v1_runtime_terminals(workspace: str, limit: int = 100) -> dict[str, Any]:
        try:
            data = runtime_interaction.runtime_dashboard(workspace, limit=limit)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.interaction", data, workspace)

    @app.get("/v1/runtime/jobs")
    def v1_runtime_jobs(workspace: str, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        try:
            data = runtime_interaction.list_jobs(workspace, status=status, limit=limit)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.jobs", data, workspace)

    @app.post("/v1/runtime/jobs")
    def v1_launch_runtime_job(request: RuntimeTerminalJobRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.launch_terminal_job(
                request.workspace,
                request.command,
                cwd=request.cwd,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                terminal_id=request.terminal_id,
                title=request.title,
                timeout_seconds=request.timeout_seconds,
                approval=request.approval,
                dry_run=request.dry_run,
                wait=request.wait,
                source_client=request.source_client,
                metadata=request.metadata,
            )
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = data.get("job", {}) if isinstance(data.get("job"), dict) else {}
        return envelope("runtime.job.mutation", data, request.workspace, ok=job.get("status") not in {"blocked", "failed", "timed_out"})

    @app.get("/v1/runtime/jobs/{job_id}")
    def v1_runtime_job(job_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = runtime_interaction.get_job(workspace, job_id)
        except RuntimeJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="runtime job not found") from exc
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.job", data, workspace)

    @app.post("/v1/runtime/jobs/{job_id}/cancel")
    def v1_cancel_runtime_job(job_id: str, request: RuntimeJobActionRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.cancel_job(request.workspace, job_id, reason=request.reason)
        except RuntimeJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="runtime job not found") from exc
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.job.mutation", data, request.workspace)

    @app.post("/v1/runtime/jobs/{job_id}/retry")
    def v1_retry_runtime_job(job_id: str, request: RuntimeJobActionRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.retry_job(
                request.workspace,
                job_id,
                approval=request.approval,
                wait=request.wait,
                timeout_seconds=request.timeout_seconds,
                reason=request.reason,
            )
        except RuntimeJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="runtime job not found") from exc
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.job.mutation", data, request.workspace)

    @app.get("/v1/runtime/streams")
    def v1_runtime_streams(
        workspace: str,
        job_id: str | None = None,
        workflow_id: str | None = None,
        since: int = 0,
        limit: int = 100,
        follow: bool = False,
        max_seconds: int = 30,
        as_sse: bool = True,
    ):
        try:
            if not as_sse:
                data = runtime_interaction.list_stream_events(
                    workspace,
                    job_id=job_id,
                    workflow_id=workflow_id,
                    since=since,
                    limit=limit,
                )
                return envelope("runtime.streams", data, workspace)
            stream = runtime_interaction.stream_events(
                workspace,
                job_id=job_id,
                workflow_id=workflow_id,
                since=since,
                limit=limit,
                follow=follow,
                max_seconds=max_seconds,
            )
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        from fastapi.responses import StreamingResponse

        return StreamingResponse(stream, media_type="text/event-stream")

    @app.get("/v1/runtime/processes")
    def v1_runtime_processes(workspace: str) -> dict[str, Any]:
        try:
            data = runtime_interaction.runtime_processes(workspace)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.processes", data, workspace)

    @app.get("/v1/runtime/sessions")
    def v1_runtime_sessions(workspace: str) -> dict[str, Any]:
        try:
            data = runtime_interaction.sessions_dashboard(workspace)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.sessions", data, workspace)

    @app.post("/v1/runtime/sessions")
    def v1_create_runtime_session(request: RuntimeSessionRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.create_session(
                request.workspace,
                workflow_id=request.workflow_id,
                title=request.title,
                owner_client_id=request.owner_client_id,
                participants=request.participants,
                spectators=request.spectators,
                approval_delegates=request.approval_delegates,
                metadata=request.metadata,
            )
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.session.mutation", data, request.workspace)

    @app.post("/v1/runtime/sessions/{session_id}/sync")
    def v1_sync_runtime_session(session_id: str, request: RuntimeSessionSyncRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.sync_session(
                request.workspace,
                session_id,
                participants=request.participants,
                spectators=request.spectators,
                approval_delegates=request.approval_delegates,
                status=request.status,
                message=request.message,
            )
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.session.mutation", data, request.workspace)

    @app.get("/v1/runtime/voice")
    def v1_runtime_voice(workspace: str) -> dict[str, Any]:
        try:
            data = runtime_interaction.voice_status(workspace)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.voice", data, workspace)

    @app.post("/v1/runtime/voice/command")
    def v1_runtime_voice_command(request: RuntimeVoiceCommandRequest) -> dict[str, Any]:
        try:
            data = runtime_interaction.route_voice_command(
                request.workspace,
                request.transcript,
                workflow_id=request.workflow_id,
                client_id=request.client_id,
                dry_run=request.dry_run,
            )
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.voice.command", data, request.workspace)

    @app.get("/v1/runtime/replay")
    def v1_runtime_replay(workspace: str, workflow_id: str | None = None, job_id: str | None = None, limit: int = 200) -> dict[str, Any]:
        try:
            data = runtime_interaction.execution_replay(workspace, workflow_id=workflow_id, job_id=job_id, limit=limit)
        except RuntimeInteractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("runtime.replay", data, workspace)

    @app.get("/v1/collaboration")
    def v1_collaboration_dashboard(
        workspace: str,
        user_id: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            data = collaboration_runtime.collaboration_dashboard(workspace, user_id=user_id, role=role, limit=limit)
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.dashboard", data, workspace)

    @app.get("/v1/collaboration/roles")
    def v1_collaboration_roles() -> dict[str, Any]:
        return envelope("collaboration.roles", {"roles": collaboration_runtime.role_catalog(), "governance": collaboration_runtime.governance_model()})

    @app.post("/v1/collaboration/members")
    def v1_collaboration_member(request: CollaborationMemberRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.register_member(
                request.workspace,
                user_id=request.user_id,
                display_name=request.display_name,
                role=request.role,
                client_id=request.client_id,
                active=request.active,
                permissions=request.permissions,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.member", data, request.workspace)

    @app.post("/v1/collaboration/repositories")
    def v1_collaboration_repository(request: CollaborationRepositoryRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.register_repository(
                request.workspace,
                repository_id=request.repository_id,
                path=request.path,
                name=request.name,
                owner_id=request.owner_id,
                visibility=request.visibility,
                runtime_nodes=request.runtime_nodes,
                validation_infrastructure=request.validation_infrastructure,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.repository", data, request.workspace)

    @app.post("/v1/collaboration/workflows")
    def v1_collaboration_workflow(request: CollaborationWorkflowRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.create_shared_workflow(
                request.workspace,
                objective=request.objective,
                workflow_type=request.workflow_type,
                owner_id=request.owner_id,
                owner_role=request.owner_role,
                repository_id=request.repository_id,
                participants=request.participants,
                reviewers=request.reviewers,
                visibility=request.visibility,
                approval_chain=request.approval_chain,
                roadmap_item_ids=request.roadmap_item_ids,
                source_client=request.source_client,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.workflow", data, request.workspace)

    @app.post("/v1/collaboration/workflows/{workflow_id}/action")
    def v1_collaboration_workflow_action(workflow_id: str, request: CollaborationWorkflowActionRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.workflow_action(
                request.workspace,
                workflow_id,
                action=request.action,
                actor_id=request.actor_id,
                actor_role=request.actor_role,
                assignee_id=request.assignee_id,
                assignee_role=request.assignee_role,
                reason=request.reason,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.workflow", data, request.workspace)

    @app.post("/v1/collaboration/approvals")
    def v1_collaboration_approval(request: CollaborationApprovalRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.create_approval(
                request.workspace,
                target_type=request.target_type,
                target_id=request.target_id,
                approval_type=request.approval_type,
                required_roles=request.required_roles,
                requested_by=request.requested_by,
                reason=request.reason,
                stage=request.stage,
                risk_level=request.risk_level,
                deployment_environment=request.deployment_environment,
                required_count=request.required_count,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.approval", data, request.workspace)

    @app.post("/v1/collaboration/approvals/{approval_id}/decision")
    def v1_collaboration_approval_decision(approval_id: str, request: CollaborationApprovalDecisionRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.decide_approval(
                request.workspace,
                approval_id,
                decision=request.decision,
                user_id=request.user_id,
                role=request.role,
                comment=request.comment,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.approval", data, request.workspace)

    @app.post("/v1/collaboration/roadmap/items")
    def v1_collaboration_roadmap_item(request: CollaborationRoadmapItemRequest) -> dict[str, Any]:
        try:
            data = collaboration_runtime.assign_roadmap_item(
                request.workspace,
                title=request.title,
                item_id=request.item_id,
                workflow_id=request.workflow_id,
                milestone=request.milestone,
                owner_id=request.owner_id,
                assigned_to=request.assigned_to,
                status=request.status,
                blockers=request.blockers,
                approval_required=request.approval_required,
                metadata=request.metadata,
            )
        except CollaborationRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("collaboration.roadmap", data, request.workspace)

    @app.get("/v1/collaboration/audit")
    def v1_collaboration_audit(workspace: str, limit: int = 100) -> dict[str, Any]:
        return envelope("collaboration.audit", collaboration_runtime.collaboration_audit(workspace, limit=limit), workspace)

    @app.get("/v1/governance")
    def v1_governance_dashboard(workspace: str, include_audit: bool = True, limit: int = 100) -> dict[str, Any]:
        try:
            data = governance_runtime.governance_dashboard(workspace, include_audit=include_audit, limit=limit)
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.dashboard", data, workspace)

    @app.get("/v1/governance/policies")
    def v1_governance_policies(workspace: str | None = None) -> dict[str, Any]:
        try:
            data = governance_runtime.policy_catalog(workspace)
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.policies", data, workspace)

    @app.post("/v1/governance/policies")
    def v1_governance_policy(request: GovernancePolicyRequest) -> dict[str, Any]:
        try:
            data = governance_runtime.upsert_policy(
                request.workspace,
                request.policy,
                actor_id=request.actor_id,
                reason=request.reason,
            )
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.policy", data, request.workspace)

    @app.post("/v1/governance/evaluate")
    def v1_governance_evaluate(request: GovernancePolicyEvaluationRequest) -> dict[str, Any]:
        try:
            data = governance_runtime.evaluate_policy(
                request.workspace,
                action_type=request.action_type,
                workflow_type=request.workflow_type,
                target=request.target,
                actor_id=request.actor_id,
                actor_role=request.actor_role,
                context=request.context,
                approval=request.approval,
                dry_run=request.dry_run,
            )
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.evaluation", data, request.workspace, ok=bool(data.get("status") != "blocked"))

    @app.get("/v1/governance/audit")
    def v1_governance_audit(workspace: str, limit: int = 100) -> dict[str, Any]:
        try:
            data = governance_runtime.audit_events(workspace, limit=limit)
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.audit", data, workspace)

    @app.post("/v1/governance/compliance/export")
    def v1_governance_compliance_export(request: GovernanceComplianceExportRequest) -> dict[str, Any]:
        try:
            data = governance_runtime.compliance_export(
                request.workspace,
                export_type=request.export_type,
                limit=request.limit,
                include_sensitive=request.include_sensitive,
            )
        except GovernanceRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("governance.compliance_export", data, request.workspace)

    @app.get("/v1/deployment")
    def v1_deployment_dashboard(workspace: str, refresh: bool = False, limit: int = 100) -> dict[str, Any]:
        try:
            data = deployment_intelligence.deployment_dashboard(workspace, refresh=refresh, limit=limit)
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.dashboard", data, workspace)

    @app.post("/v1/deployment/scan")
    def v1_deployment_scan(request: WorkspaceRequest) -> dict[str, Any]:
        try:
            data = deployment_intelligence.scan_environment(request.workspace, persist=True)
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.scan", data, request.workspace)

    @app.post("/v1/deployment/pipelines/validate")
    def v1_deployment_pipeline_validation(request: DeploymentPipelineValidationRequest) -> dict[str, Any]:
        try:
            data = deployment_intelligence.validate_pipeline(request.workspace, pipeline_id=request.pipeline_id, dry_run=request.dry_run)
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.pipeline.validation", data, request.workspace)

    @app.post("/v1/deployment/workflows")
    def v1_deployment_workflow(request: DeploymentWorkflowRequest) -> dict[str, Any]:
        try:
            data = deployment_intelligence.create_deployment_workflow(
                request.workspace,
                request.workflow_type,
                target_environment=request.target_environment,
                release_version=request.release_version,
                approval=request.approval,
                production_confirmed=request.production_confirmed,
                dry_run=request.dry_run,
                source_client=request.source_client,
                notes=request.notes,
            )
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.workflow", data, request.workspace)

    @app.post("/v1/deployment/workflows/{workflow_id}/step")
    def v1_deployment_workflow_step(workflow_id: str, request: DeploymentWorkflowActionRequest) -> dict[str, Any]:
        try:
            data = deployment_intelligence.step_deployment_workflow(
                request.workspace,
                workflow_id,
                action=request.action,
                approval=request.approval,
                production_confirmed=request.production_confirmed,
                validation_passed=request.validation_passed,
                message=request.message,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.workflow.step", data, request.workspace)

    @app.get("/v1/deployment/releases")
    def v1_deployment_releases(workspace: str, limit: int = 100) -> dict[str, Any]:
        try:
            data = deployment_intelligence.deployment_release_history(workspace, limit=limit)
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.release_history", data, workspace)

    @app.get("/v1/deployment/observability")
    def v1_deployment_observability(workspace: str) -> dict[str, Any]:
        try:
            data = deployment_intelligence.deployment_observability(workspace)
        except DeploymentIntelligenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("deployment.observability", data, workspace)

    @app.get("/v1/optimization")
    def v1_optimization_dashboard(workspace: str, refresh: bool = False, limit: int = 100) -> dict[str, Any]:
        try:
            data = system_optimization.optimization_dashboard(workspace, refresh=refresh, limit=limit)
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.dashboard", data, workspace)

    @app.get("/v1/optimization/recommendations")
    def v1_optimization_recommendations(workspace: str) -> dict[str, Any]:
        try:
            data = system_optimization.optimization_recommendations(workspace)
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.recommendations", data, workspace)

    @app.get("/v1/optimization/observability")
    def v1_optimization_observability(workspace: str) -> dict[str, Any]:
        try:
            data = system_optimization.optimization_observability(workspace)
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.observability", data, workspace)

    @app.post("/v1/optimization/experiments")
    def v1_optimization_experiment(request: OptimizationExperimentRequest) -> dict[str, Any]:
        try:
            data = system_optimization.create_experiment(
                request.workspace,
                target_area=request.target_area,
                hypothesis=request.hypothesis,
                variants=request.variants,
                benchmark_suite_ids=request.benchmark_suite_ids,
                sandbox=request.sandbox,
                approval=request.approval,
                source_client=request.source_client,
            )
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.experiment", data, request.workspace)

    @app.post("/v1/optimization/experiments/{experiment_id}/run")
    def v1_optimization_experiment_run(experiment_id: str, request: OptimizationExperimentRunRequest) -> dict[str, Any]:
        try:
            data = system_optimization.run_experiment(request.workspace, experiment_id, dry_run=request.dry_run, benchmark_suite_ids=request.benchmark_suite_ids)
        except OptimizationExperimentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.experiment", data, request.workspace)

    @app.post("/v1/optimization/experiments/{experiment_id}/adopt")
    def v1_optimization_experiment_adopt(experiment_id: str, request: OptimizationExperimentAdoptRequest) -> dict[str, Any]:
        try:
            data = system_optimization.adopt_experiment(
                request.workspace,
                experiment_id,
                approval=request.approval,
                rollout_stage=request.rollout_stage,
                reason=request.reason,
            )
        except OptimizationExperimentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.experiment", data, request.workspace)

    @app.post("/v1/optimization/experiments/{experiment_id}/rollback")
    def v1_optimization_experiment_rollback(experiment_id: str, request: OptimizationExperimentRollbackRequest) -> dict[str, Any]:
        try:
            data = system_optimization.rollback_experiment(request.workspace, experiment_id, reason=request.reason)
        except OptimizationExperimentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SystemOptimizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("optimization.experiment", data, request.workspace)

    @app.get("/v1/stabilization/audit")
    def v1_stabilization_audit(workspace: str | None = None, repo_root: str | None = None, persist: bool = True, max_files: int = 8000) -> dict[str, Any]:
        data = stabilization_runtime.stabilization_audit(workspace, repo_root=repo_root, persist=persist, max_files=max_files)
        return envelope("stabilization.audit", data, data["workspace"])

    @app.get("/v1/stabilization/governance")
    def v1_stabilization_governance() -> dict[str, Any]:
        return envelope("stabilization.governance", stabilization_runtime.governance_rules())

    @app.get("/v1/stabilization/roadmap")
    def v1_stabilization_roadmap() -> dict[str, Any]:
        return envelope("stabilization.roadmap", stabilization_runtime.roadmap_classification())

    @app.get("/v1/product/identity")
    def v1_product_identity() -> dict[str, Any]:
        return envelope("product.identity", product_identity.product_identity())

    @app.get("/v1/product/features")
    def v1_product_features() -> dict[str, Any]:
        return envelope("product.features", product_identity.feature_catalog())

    @app.get("/v1/product/modes")
    def v1_product_modes() -> dict[str, Any]:
        return envelope("product.modes", product_identity.product_modes())

    @app.get("/v1/product/workflows")
    def v1_product_workflows() -> dict[str, Any]:
        return envelope("product.workflows", product_identity.workflow_catalog())

    @app.get("/v1/product/showcase")
    def v1_product_showcase() -> dict[str, Any]:
        return envelope("product.showcase", product_identity.showcase_workflows())

    @app.get("/v1/product/launch-scope")
    def v1_product_launch_scope() -> dict[str, Any]:
        return envelope("product.launch_scope", product_identity.launch_scope())

    @app.get("/v1/product/roadmap")
    def v1_product_roadmap() -> dict[str, Any]:
        return envelope("product.roadmap", product_identity.roadmap_governance())

    @app.get("/v1/dogfooding")
    def v1_dogfooding_dashboard(workspace: str, limit: int = 250, persist: bool = False) -> dict[str, Any]:
        data = dogfooding_runtime.dogfooding_dashboard(workspace, limit=limit, persist=persist)
        return envelope("dogfooding.dashboard", data, workspace)

    @app.post("/v1/dogfooding/events")
    def v1_dogfooding_event(request: DogfoodingEventRequest) -> dict[str, Any]:
        data = dogfooding_runtime.record_dogfooding_event(
            request.workspace,
            event_type=request.event_type,
            client_id=request.client_id,
            client_type=request.client_type,
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            action=request.action,
            status=request.status,
            duration_ms=request.duration_ms,
            click_count=request.click_count,
            friction_tags=request.friction_tags,
            interruption=request.interruption,
            notes=request.notes,
            metadata=request.metadata,
        )
        return envelope("dogfooding.event", data, request.workspace)

    @app.get("/v1/dogfooding/friction")
    def v1_dogfooding_friction(workspace: str) -> dict[str, Any]:
        return envelope("dogfooding.friction", dogfooding_runtime.friction_report(workspace), workspace)

    @app.get("/v1/dogfooding/confidence")
    def v1_dogfooding_confidence(workspace: str) -> dict[str, Any]:
        return envelope("dogfooding.confidence", dogfooding_runtime.production_confidence(workspace), workspace)

    @app.get("/v1/dogfooding/workflows")
    def v1_dogfooding_workflows() -> dict[str, Any]:
        return envelope("dogfooding.workflows", dogfooding_runtime.dogfooding_workflows())

    @app.get("/v1/dogfooding/long-session-plan")
    def v1_dogfooding_long_session_plan(workspace: str | None = None) -> dict[str, Any]:
        return envelope("dogfooding.long_session_plan", dogfooding_runtime.long_session_plan(workspace), workspace)

    @app.get("/v1/engineering-workspace")
    def v1_engineering_workspace_dashboard(
        workspace: str,
        refresh: bool = False,
        persist: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        data = engineering_workspace.engineering_workspace_dashboard(
            workspace,
            refresh=refresh,
            persist=persist,
            limit=limit,
        )
        return envelope("engineering_workspace.dashboard", data, workspace)

    @app.get("/v1/engineering-workspace/map")
    def v1_engineering_workspace_map(workspace: str, limit: int = 100) -> dict[str, Any]:
        data = engineering_workspace.engineering_project_map(workspace, limit=limit)
        return envelope("engineering_workspace.map", data, workspace)

    @app.post("/v1/engineering-workspace/search")
    def v1_engineering_workspace_search(request: EngineeringWorkspaceSearchRequest) -> dict[str, Any]:
        data = engineering_workspace.engineering_search(
            request.workspace,
            request.query,
            mode=request.mode,
            focus=request.focus,
            limit=request.limit,
        )
        return envelope("engineering_workspace.search", data, request.workspace)

    @app.get("/v1/engineering-workspace/validation")
    def v1_engineering_workspace_validation(workspace: str) -> dict[str, Any]:
        data = engineering_workspace.validation_review(workspace)
        return envelope("engineering_workspace.validation", data, workspace)

    @app.get("/v1/engineering-workspace/continuity")
    def v1_engineering_workspace_continuity(workspace: str) -> dict[str, Any]:
        data = engineering_workspace.workflow_continuity(workspace)
        return envelope("engineering_workspace.continuity", data, workspace)

    @app.get("/v1/engineering-workspace/benchmarks")
    def v1_engineering_workspace_benchmarks(workspace: str) -> dict[str, Any]:
        data = engineering_workspace.engineering_workspace_dashboard(workspace, limit=25).get("benchmark_comparisons", {})
        return envelope("engineering_workspace.benchmarks", data, workspace)

    @app.get("/v1/alpha/readiness")
    def v1_alpha_readiness(workspace: str, persist: bool = False) -> dict[str, Any]:
        data = alpha_runtime.alpha_readiness(workspace, persist=persist)
        return envelope("alpha.readiness", data, workspace, ok=bool(data.get("ready", False)))

    @app.get("/v1/alpha/features")
    def v1_alpha_features() -> dict[str, Any]:
        return envelope("alpha.feature_classification", alpha_runtime.feature_classification())

    @app.get("/v1/alpha/feature-flags")
    def v1_alpha_feature_flags(workspace: str) -> dict[str, Any]:
        return envelope("alpha.feature_flags", alpha_runtime.alpha_feature_flags(workspace), workspace)

    @app.post("/v1/alpha/feature-flags")
    def v1_alpha_update_feature_flags(request: AlphaFeatureFlagsRequest) -> dict[str, Any]:
        data = alpha_runtime.update_feature_flags(
            request.workspace,
            overrides=request.overrides,
            release_channel=request.release_channel,
            reason=request.reason,
        )
        return envelope("alpha.feature_flags", data, request.workspace)

    @app.get("/v1/alpha/diagnostics")
    def v1_alpha_diagnostics(workspace: str, include_replay: bool = True) -> dict[str, Any]:
        data = alpha_runtime.runtime_diagnostics_snapshot(workspace, include_replay=include_replay)
        return envelope("alpha.diagnostics", data, workspace)

    @app.post("/v1/alpha/diagnostics/export")
    def v1_alpha_diagnostics_export(request: AlphaDiagnosticsExportRequest) -> dict[str, Any]:
        data = alpha_runtime.export_diagnostics_bundle(
            request.workspace,
            include_replay=request.include_replay,
            include_plugins=request.include_plugins,
            include_validation=request.include_validation,
            reason=request.reason,
        )
        return envelope("alpha.diagnostics_export", data, request.workspace, ok=bool(data.get("persisted", False)))

    @app.post("/v1/alpha/feedback")
    def v1_alpha_feedback(request: AlphaFeedbackRequest) -> dict[str, Any]:
        data = alpha_runtime.record_feedback(
            request.workspace,
            category=request.category,
            severity=request.severity,
            message=request.message,
            client_type=request.client_type,
            workflow_id=request.workflow_id,
            metadata=request.metadata,
        )
        return envelope("alpha.feedback", data, request.workspace)

    @app.get("/v1/alpha/feedback")
    def v1_alpha_feedback_summary(workspace: str, limit: int = 100) -> dict[str, Any]:
        return envelope("alpha.feedback_summary", alpha_runtime.feedback_summary(workspace, limit=limit), workspace)

    @app.get("/v1/alpha/observability")
    def v1_alpha_observability(workspace: str) -> dict[str, Any]:
        return envelope("alpha.observability", alpha_runtime.alpha_observability(workspace), workspace)

    @app.get("/v1/alpha/release-channels")
    def v1_alpha_release_channels() -> dict[str, Any]:
        return envelope("alpha.release_channels", alpha_runtime.release_channels())

    @app.get("/v1/alpha/simulations")
    def v1_alpha_simulations(workspace: str) -> dict[str, Any]:
        return envelope("alpha.simulations", alpha_runtime.alpha_simulations(workspace), workspace)

    @app.get("/v1/platform/governance")
    def v1_platform_governance() -> dict[str, Any]:
        return envelope("platform.governance", platform_foundation.platform_governance())

    @app.get("/v1/platform/migrations")
    def v1_platform_migrations(workspace: str) -> dict[str, Any]:
        return envelope("platform.migrations", platform_foundation.platform_migration_status(workspace), workspace)

    @app.post("/v1/platform/migrations/run")
    def v1_platform_run_migrations(request: PlatformMigrationRequest) -> dict[str, Any]:
        data = platform_foundation.run_platform_migrations(request.workspace, dry_run=request.dry_run)
        return envelope("platform.migrations", data, request.workspace)

    @app.post("/v1/platform/compatibility/validate")
    def v1_platform_compatibility(request: PlatformCompatibilityRequest) -> dict[str, Any]:
        data = platform_foundation.validate_platform_compatibility(
            request.workspace,
            client_reports=request.client_reports,
            include_plugins=request.include_plugins,
            persist=request.persist,
        )
        return envelope("platform.compatibility", data, request.workspace, ok=bool(data.get("compatible", False)))

    @app.get("/v1/platform/ownership")
    def v1_platform_ownership() -> dict[str, Any]:
        return envelope("platform.ownership", platform_foundation.subsystem_ownership())

    @app.get("/v1/platform/dependencies")
    def v1_platform_dependencies(workspace: str) -> dict[str, Any]:
        return envelope("platform.dependencies", platform_foundation.ecosystem_dependency_management(workspace), workspace)

    @app.get("/v1/platform/release-engineering")
    def v1_platform_release_engineering(workspace: str | None = None) -> dict[str, Any]:
        return envelope("platform.release_engineering", platform_foundation.release_engineering_status(workspace), workspace)

    @app.get("/v1/platform/health")
    def v1_platform_health(workspace: str, persist: bool = False) -> dict[str, Any]:
        data = platform_foundation.platform_health_analytics(workspace, persist=persist)
        return envelope("platform.health", data, workspace, ok=data.get("overall_status") != "blocked")

    @app.get("/v1/platform/tooling")
    def v1_platform_tooling(workspace: str) -> dict[str, Any]:
        return envelope("platform.tooling", platform_foundation.ecosystem_tooling(workspace), workspace)

    @app.get("/v1/platform/roadmap")
    def v1_platform_roadmap() -> dict[str, Any]:
        return envelope("platform.roadmap", platform_foundation.roadmap_governance())

    @app.post("/v1/platform/archive")
    def v1_platform_archive(request: PlatformArchiveRequest) -> dict[str, Any]:
        data = platform_foundation.create_platform_archive(
            request.workspace,
            include_memory=request.include_memory,
            include_workflows=request.include_workflows,
            include_knowledge=request.include_knowledge,
            include_checkpoints=request.include_checkpoints,
            dry_run=request.dry_run,
            reason=request.reason,
        )
        return envelope("platform.archive", data, request.workspace, ok=bool(data.get("persisted", False) or data.get("dry_run", False)))

    @app.post("/v1/platform/sustainability")
    def v1_platform_sustainability(request: PlatformSustainabilityRequest) -> dict[str, Any]:
        data = platform_foundation.platform_sustainability(request.workspace, persist=request.persist)
        return envelope("platform.sustainability", data, request.workspace)

    @app.get("/v1/ecosystem/strategy")
    def v1_ecosystem_strategy() -> dict[str, Any]:
        return envelope("ecosystem.strategy", ecosystem_maturity.ecosystem_strategy())

    @app.get("/v1/ecosystem/workflow-excellence")
    def v1_ecosystem_workflow_excellence(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.workflow_excellence", ecosystem_maturity.workflow_excellence(workspace), workspace)

    @app.get("/v1/ecosystem/plugin-quality")
    def v1_ecosystem_plugin_quality(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.plugin_quality", ecosystem_maturity.plugin_ecosystem_quality(workspace), workspace)

    @app.get("/v1/ecosystem/api-stability")
    def v1_ecosystem_api_stability() -> dict[str, Any]:
        return envelope("ecosystem.api_stability", ecosystem_maturity.api_stability())

    @app.get("/v1/ecosystem/contributor")
    def v1_ecosystem_contributor(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.contributor", ecosystem_maturity.contributor_ecosystem(workspace), workspace)

    @app.get("/v1/ecosystem/reputation")
    def v1_ecosystem_reputation(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.reputation", ecosystem_maturity.platform_reputation(workspace), workspace)

    @app.get("/v1/ecosystem/release-cadence")
    def v1_ecosystem_release_cadence() -> dict[str, Any]:
        return envelope("ecosystem.release_cadence", ecosystem_maturity.release_cadence())

    @app.get("/v1/ecosystem/observability")
    def v1_ecosystem_observability(workspace: str, persist: bool = False) -> dict[str, Any]:
        return envelope("ecosystem.observability", ecosystem_maturity.ecosystem_observability(workspace, persist=persist), workspace)

    @app.post("/v1/ecosystem/observability")
    def v1_ecosystem_observability_post(request: EcosystemObservabilityRequest) -> dict[str, Any]:
        return envelope("ecosystem.observability", ecosystem_maturity.ecosystem_observability(request.workspace, persist=request.persist), request.workspace)

    @app.get("/v1/ecosystem/maintainability")
    def v1_ecosystem_maintainability(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.maintainability", ecosystem_maturity.maintainability_guidance(workspace), workspace)

    @app.get("/v1/ecosystem/showcases")
    def v1_ecosystem_showcases(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.showcases", ecosystem_maturity.showcase_experiences(workspace), workspace)

    @app.get("/v1/ecosystem/trust")
    def v1_ecosystem_trust(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.trust", ecosystem_maturity.trust_transparency(workspace), workspace)

    @app.get("/v1/ecosystem/sustainability-plan")
    def v1_ecosystem_sustainability_plan() -> dict[str, Any]:
        return envelope("ecosystem.sustainability_plan", ecosystem_maturity.sustainability_plan())

    @app.post("/v1/ecosystem/maturity")
    def v1_ecosystem_maturity(request: EcosystemMaturityRequest) -> dict[str, Any]:
        return envelope("ecosystem.maturity", ecosystem_maturity.ecosystem_maturity(request.workspace, persist=request.persist), request.workspace)

    @app.post("/v1/workspaces/scan")
    def v1_scan(request: WorkspaceRequest) -> dict[str, Any]:
        return envelope("workspace.scan", WorkspaceScanner(request.workspace).scan(persist=True), request.workspace)

    @app.post("/v1/workspaces/roadmap")
    def v1_roadmap(request: WorkspaceRequest) -> dict[str, Any]:
        try:
            data = generate_roadmap(request.workspace, persist=True)
        except RoadmapPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("workspace.roadmap", data, request.workspace)

    @app.get("/v1/memory")
    def v1_memory(workspace: str) -> dict[str, Any]:
        return envelope("memory.summary", shared_memory_summary(workspace), workspace)

    @app.get("/v1/diagnostics")
    def v1_diagnostics(workspace: str) -> dict[str, Any]:
        return envelope("diagnostics.summary", diagnostics_summary(workspace), workspace)

    @app.get("/v1/branding")
    def v1_branding() -> dict[str, Any]:
        return envelope("branding.tokens", branding_tokens())

    @app.post("/v1/clients/register")
    def v1_register_client(request: ClientRegistrationRequest) -> dict[str, Any]:
        try:
            client = register_client(
                request.workspace,
                request.client_id,
                request.client_type,
                request.name,
                request.version,
                request.capabilities,
            )
        except ClientRegistryPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("client.registered", client, request.workspace)

    @app.get("/v1/clients")
    def v1_clients(workspace: str) -> dict[str, Any]:
        return envelope("clients.list", list_clients(workspace), workspace)

    @app.get("/v1/agents")
    def v1_agents() -> dict[str, Any]:
        return envelope("agents.roster", agent_roster())

    @app.get("/v1/agents/runtime")
    def v1_agents_runtime(workspace: str | None = None) -> dict[str, Any]:
        return envelope("agent.runtime", agent_runtime.agent_runtime_catalog(workspace), workspace)

    @app.post("/v1/orchestration/plan")
    def v1_orchestration_plan(request: OrchestrationPlanRequest) -> dict[str, Any]:
        try:
            data = create_orchestration_plan(
                request.workspace,
                request.goal,
                source_client=request.source_client,
                context_files=request.context_files,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OrchestrationPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("orchestration.plan", data, request.workspace)

    @app.get("/v1/orchestration")
    def v1_orchestration_dashboard(workspace: str) -> dict[str, Any]:
        return envelope("orchestration.dashboard", orchestration_dashboard(workspace), workspace)

    @app.post("/v1/orchestration/step")
    def v1_orchestration_step(request: OrchestrationStepRequest) -> dict[str, Any]:
        try:
            data = advance_orchestration_step(
                request.workspace,
                task_id=request.task_id,
                action=request.action,
                approval=request.approval,
                summary=request.summary,
                affected_files=request.affected_files,
                validation_command=request.validation_command,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OrchestrationPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("orchestration.step", data, request.workspace)

    @app.get("/v1/jobs")
    def v1_jobs(workspace: str) -> dict[str, Any]:
        return envelope("jobs.dashboard", jobs_dashboard(workspace), workspace)

    @app.post("/v1/jobs/run")
    def v1_run_job(request: JobRunRequest) -> dict[str, Any]:
        try:
            data = run_job(
                request.workspace,
                job_id=request.job_id,
                trigger=request.trigger,
                approval=request.approval,
                run_due=request.run_due,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except JobPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("jobs.run", data, request.workspace)

    @app.get("/v1/jobs/{job_id}")
    def v1_operation_job(job_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = editing_runtime.get_operation_job(workspace, job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("core.job", data, workspace)

    @app.post("/v1/changes/propose")
    def v1_propose_changes(request: ProposeChangesRequest) -> dict[str, Any]:
        try:
            data = editing_runtime.propose_changes(
                request.workspace,
                [item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict() for item in request.changes],
                summary=request.summary,
                source_task_id=request.source_task_id,
                source_client=request.source_client,
                risk=request.risk,
                repair_attempt=request.repair_attempt,
            )
        except UnsafePathError as exc:
            security_runtime.security_audit(request.workspace, "workspace.unsafe_path", "blocked", str(exc), {"operation": "changes.propose"})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("changes.proposal", data, request.workspace)

    @app.post("/v1/changes/apply")
    def v1_apply_changes(request: ApplyChangesRequest) -> dict[str, Any]:
        try:
            data = editing_runtime.apply_changes(
                request.workspace,
                proposal_id=request.proposal_id,
                changes=[item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict() for item in request.changes],
                change_ids=request.change_ids,
                paths=request.paths,
                apply_all=request.apply_all,
                dry_run=request.dry_run,
                summary=request.summary,
                task_id=request.task_id,
                source_client=request.source_client,
                repair_attempt=request.repair_attempt,
                approval=request.approval,
                validation_required=request.validation_required,
                quality_gate_required=request.quality_gate_required,
                max_files_changed=request.max_files_changed,
                allow_quality_override=request.allow_quality_override,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="proposal not found") from exc
        except UnsafePathError as exc:
            security_runtime.security_audit(request.workspace, "workspace.unsafe_path", "blocked", str(exc), {"operation": "changes.apply"})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("changes.apply", data, request.workspace, ok=bool(data.get("ok", False)))

    @app.post("/v1/checkpoints/create")
    def v1_create_checkpoint(request: CheckpointCreateRequest) -> dict[str, Any]:
        try:
            data = editing_runtime.create_checkpoint(
                request.workspace,
                changes=[item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict() for item in request.changes],
                paths=request.paths,
                summary=request.summary,
                source_task_id=request.source_task_id,
                source_client=request.source_client,
            )
        except UnsafePathError as exc:
            security_runtime.security_audit(request.workspace, "workspace.unsafe_path", "blocked", str(exc), {"operation": "checkpoints.create"})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("checkpoints.create", data, request.workspace)

    @app.get("/v1/checkpoints")
    def v1_list_checkpoints(workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = editing_runtime.list_checkpoints(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("checkpoints.list", data, workspace)

    @app.post("/v1/checkpoints/restore")
    def v1_restore_checkpoint(request: CheckpointRestoreRequest) -> dict[str, Any]:
        checkpoint_id = request.checkpoint_id or request.checkpoint
        if not checkpoint_id:
            raise HTTPException(status_code=400, detail="checkpoint_id is required")
        try:
            data = editing_runtime.restore_checkpoint(
                request.workspace,
                checkpoint_id,
                dry_run=request.dry_run,
                source_client=request.source_client,
                task_id=request.task_id,
            )
        except CheckpointNotFoundError as exc:
            raise HTTPException(status_code=404, detail="checkpoint not found") from exc
        except UnsafePathError as exc:
            security_runtime.security_audit(request.workspace, "workspace.unsafe_path", "blocked", str(exc), {"operation": "checkpoints.restore"})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("checkpoints.restore", data, request.workspace, ok=bool(data.get("ok", False)))

    @app.post("/v1/validation/run")
    def v1_run_validation_operation(request: ValidationRunRequest) -> dict[str, Any]:
        try:
            data = editing_runtime.run_validation_operation(
                request.workspace,
                command=request.command,
                timeout_seconds=request.timeout_seconds,
                dry_run=request.dry_run,
                source_client=request.source_client,
                task_id=request.task_id,
                repair_attempt=request.repair_attempt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EditingPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        validation_ok = bool(data.get("validation", {}).get("ok", False))
        security_runtime.security_audit(
            request.workspace,
            "validation.run",
            "completed" if validation_ok else "failed",
            "Validation command captured by Core.",
            {"job_id": data.get("job_id", ""), "validation_id": data.get("id", "")},
        )
        return envelope("validation.run", data, request.workspace, ok=bool(data.get("validation", {}).get("ok", False)))

    @app.get("/v1/projects/{project_id}/activity")
    def v1_project_activity(project_id: str, workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = editing_runtime.project_activity(workspace, project_id, limit=limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="project activity not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("project.activity", data, workspace)

    @app.post("/v1/workspaces/intelligence")
    def v1_workspace_intelligence(request: WorkspaceIntelligenceRequest) -> dict[str, Any]:
        try:
            data = workspace_intelligence(request.workspace, persist=request.persist, refresh=request.refresh)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workspace.intelligence", data, request.workspace)

    @app.get("/v1/engineering-intelligence")
    def v1_engineering_intelligence_dashboard(
        workspace: str,
        workflow_type: str = "generate_feature",
        objective: str = "",
        focus: str = "",
        token_budget: int = 24000,
        refresh: bool = False,
        persist: bool = True,
    ) -> dict[str, Any]:
        data = engineering_intelligence.engineering_intelligence(
            workspace,
            workflow_type=workflow_type,
            objective=objective,
            focus=focus,
            token_budget=token_budget,
            refresh=refresh,
            persist=persist,
        )
        return envelope("engineering.intelligence", data, workspace)

    @app.post("/v1/engineering-intelligence/analyze")
    def v1_engineering_intelligence_analyze(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        data = engineering_intelligence.engineering_intelligence(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            focus=request.focus,
            token_budget=request.token_budget,
            latest_validation=request.latest_validation,
            refresh=request.refresh,
            persist=request.persist,
        )
        return envelope("engineering.intelligence", data, request.workspace)

    @app.post("/v1/engineering-intelligence/context")
    def v1_engineering_intelligence_context(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        data = engineering_intelligence.assemble_context(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            focus=request.focus,
            token_budget=request.token_budget,
            persist=request.persist,
        )
        return envelope("engineering.context", data, request.workspace)

    @app.post("/v1/engineering-intelligence/validation-plan")
    def v1_engineering_intelligence_validation_plan(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        data = engineering_intelligence.validation_plan(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
        )
        return envelope("engineering.validation_intelligence", data, request.workspace)

    @app.post("/v1/engineering-intelligence/repair-plan")
    def v1_engineering_intelligence_repair_plan(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        data = engineering_intelligence.repair_plan(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            latest_validation=request.latest_validation,
        )
        return envelope("engineering.repair_intelligence", data, request.workspace)

    @app.post("/v1/engineering-intelligence/roadmap-plan")
    def v1_engineering_intelligence_roadmap_plan(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        intelligence = engineering_intelligence.engineering_intelligence(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            focus=request.focus,
            token_budget=request.token_budget,
            latest_validation=request.latest_validation,
            refresh=request.refresh,
            persist=request.persist,
        )
        return envelope("engineering.roadmap_intelligence", intelligence.get("roadmap_intelligence", {}), request.workspace)

    @app.post("/v1/engineering-intelligence/predict")
    def v1_engineering_intelligence_prediction(request: EngineeringIntelligenceRequest) -> dict[str, Any]:
        intelligence = engineering_intelligence.engineering_intelligence(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            focus=request.focus,
            token_budget=request.token_budget,
            latest_validation=request.latest_validation,
            refresh=request.refresh,
            persist=request.persist,
        )
        return envelope("engineering.workflow_prediction", intelligence.get("workflow_prediction", {}), request.workspace)

    @app.post("/v1/engineering-intelligence/benchmarks/run")
    def v1_engineering_intelligence_benchmark_run(request: EngineeringIntelligenceBenchmarkRequest) -> dict[str, Any]:
        data = engineering_intelligence.run_benchmarks(
            request.workspace,
            workflow_type=request.workflow_type,
            objective=request.objective,
            target_files=request.target_files,
            persist=request.persist,
        )
        return envelope("engineering.intelligence.benchmarks", data, request.workspace)

    @app.get("/v1/engineering-intelligence/benchmarks")
    def v1_engineering_intelligence_benchmarks(workspace: str, limit: int = 50) -> dict[str, Any]:
        data = engineering_intelligence.benchmark_dashboard(workspace, limit=limit)
        return envelope("engineering.intelligence.benchmarks", data, workspace)

    @app.get("/v1/intelligence-stack")
    def v1_intelligence_stack(
        workspace: str,
        workflow_type: str = "generate_feature",
        objective: str = "",
        refresh: bool = False,
        persist: bool = True,
    ) -> dict[str, Any]:
        try:
            data = intelligence_stack.intelligence_stack_dashboard(
                workspace,
                workflow_type=workflow_type,
                objective=objective,
                refresh=refresh,
                persist=persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.stack", data, workspace)

    @app.post("/v1/intelligence-stack")
    def v1_intelligence_stack_analyze(request: IntelligenceStackRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.intelligence_stack_dashboard(
                request.workspace,
                workflow_type=request.workflow_type,
                objective=request.objective,
                target_files=request.target_files,
                refresh=request.refresh,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.stack", data, request.workspace)

    @app.get("/v1/intelligence-stack/models")
    def v1_intelligence_stack_models(workspace: str) -> dict[str, Any]:
        try:
            data = intelligence_stack.model_lifecycle(workspace, action="list")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.models", data, workspace)

    @app.post("/v1/intelligence-stack/models")
    def v1_intelligence_stack_model_lifecycle(request: IntelligenceModelLifecycleRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.model_lifecycle(
                request.workspace,
                action=request.action,
                model=request.model,
                model_id=request.model_id,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.models", data, request.workspace)

    @app.post("/v1/intelligence-stack/retrieval/index")
    def v1_intelligence_stack_retrieval(request: IntelligenceRetrievalRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.retrieval_index(
                request.workspace,
                query=request.query,
                focus=request.focus,
                limit=request.limit,
                refresh=request.refresh,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.retrieval", data, request.workspace)

    @app.post("/v1/intelligence-stack/route")
    def v1_intelligence_stack_route(request: IntelligenceRoutingRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.route_intelligence(
                request.workspace,
                workflow_type=request.workflow_type,
                objective=request.objective,
                target_files=request.target_files,
                route_profile=request.route_profile,
                required_capabilities=request.required_capabilities,
                privacy_sensitive=request.privacy_sensitive,
                allow_cloud=request.allow_cloud,
                cloud_approved=request.cloud_approved,
                context_files=request.context_files,
                local_failure_reason=request.local_failure_reason,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.route", data, request.workspace)

    @app.post("/v1/intelligence-stack/predict")
    def v1_intelligence_stack_predict(request: IntelligenceStackRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.orchestration_prediction(
                request.workspace,
                workflow_type=request.workflow_type,
                objective=request.objective,
                target_files=request.target_files,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.prediction", data, request.workspace)

    @app.post("/v1/intelligence-stack/benchmarks/run")
    def v1_intelligence_stack_benchmark_run(request: IntelligenceBenchmarkRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.run_benchmarks(
                request.workspace,
                suites=request.suites,
                workflow_type=request.workflow_type,
                objective=request.objective,
                target_files=request.target_files,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.benchmarks", data, request.workspace)

    @app.get("/v1/intelligence-stack/benchmarks")
    def v1_intelligence_stack_benchmarks(workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = intelligence_stack.benchmark_dashboard(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.benchmarks", data, workspace)

    @app.post("/v1/intelligence-stack/datasets")
    def v1_intelligence_stack_datasets(request: IntelligenceDatasetRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.dataset_foundations(
                request.workspace,
                include_sensitive=request.include_sensitive,
                limit=request.limit,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.datasets", data, request.workspace)

    @app.post("/v1/intelligence-stack/distributed-inference/plan")
    def v1_intelligence_stack_distributed_inference(request: IntelligenceDistributedInferenceRequest) -> dict[str, Any]:
        try:
            data = intelligence_stack.distributed_inference_plan(
                request.workspace,
                workflow_type=request.workflow_type,
                model_id=request.model_id,
                allow_remote=request.allow_remote,
                approval=request.approval,
                dry_run=request.dry_run,
                payload=request.payload,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("intelligence.distributed_inference", data, request.workspace)

    @app.post("/v1/workflows")
    def v1_create_workflow(request: WorkflowCreateRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.create_workflow(
                request.workspace,
                request.workflow_type,
                request.objective,
                source_client=request.source_client,
                context_files=request.context_files,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except WorkflowPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("workflow.created", data, request.workspace)

    @app.get("/v1/workflows")
    def v1_list_workflows(workspace: str, include_completed: bool = True, limit: int = 50) -> dict[str, Any]:
        try:
            data = workflow_runtime.list_workflows(workspace, include_completed=include_completed, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflows.list", data, workspace)

    @app.get("/v1/workflows/stats")
    def v1_workflow_statistics(workspace: str) -> dict[str, Any]:
        try:
            data = workflow_runtime.workflow_statistics(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.statistics", data, workspace)

    @app.get("/v1/workflows/agent-runtime")
    def v1_agent_runtime(workspace: str | None = None) -> dict[str, Any]:
        return envelope("agent.runtime", agent_runtime.agent_runtime_catalog(workspace), workspace)

    @app.get("/v1/engineering/modes")
    def v1_engineering_modes() -> dict[str, Any]:
        return envelope("engineering.modes", engineering_execution.execution_modes())

    @app.post("/v1/engineering/executions")
    def v1_create_engineering_execution(request: EngineeringExecutionCreateRequest) -> dict[str, Any]:
        try:
            data = engineering_execution.create_execution(
                request.workspace,
                request.goal,
                mode=request.mode,
                source_client=request.source_client,
                constraints=request.constraints,
                target_files=request.target_files,
                context_files=request.context_files,
                validation_command=request.validation_command,
                max_repair_attempts=request.max_repair_attempts,
                max_file_modifications=request.max_file_modifications,
                approval_requirements=request.approval_requirements,
                roadmap_item_id=request.roadmap_item_id,
                roadmap_phase_id=request.roadmap_phase_id,
                metadata=request.metadata,
                create_workflow=request.create_workflow,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EngineeringExecutionPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("engineering.execution.created", data, request.workspace)

    @app.get("/v1/engineering/executions")
    def v1_list_engineering_executions(workspace: str, include_completed: bool = True, limit: int = 50) -> dict[str, Any]:
        try:
            data = engineering_execution.list_executions(workspace, include_completed=include_completed, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("engineering.executions.list", data, workspace)

    @app.get("/v1/engineering/executions/{execution_id}/timeline")
    def v1_engineering_execution_timeline(execution_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = engineering_execution.execution_timeline(workspace, execution_id)
        except EngineeringExecutionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="engineering execution not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("engineering.execution.timeline", data, workspace)

    @app.get("/v1/engineering/executions/{execution_id}")
    def v1_engineering_execution(execution_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = engineering_execution.execution_dashboard(workspace, execution_id)
        except EngineeringExecutionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="engineering execution not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("engineering.execution.dashboard", data, workspace)

    @app.post("/v1/engineering/executions/{execution_id}/step")
    def v1_step_engineering_execution(execution_id: str, request: EngineeringExecutionActionRequest) -> dict[str, Any]:
        try:
            data = engineering_execution.step_execution(
                request.workspace,
                execution_id,
                action=request.action,
                stage_key=request.stage_key,
                approval=request.approval,
                summary=request.summary,
                payload=request.payload,
            )
        except EngineeringExecutionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="engineering execution not found") from exc
        except (ValueError, EngineeringExecutionPersistenceError, EditingPersistenceError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("engineering.execution.step", data, request.workspace)

    @app.get("/v1/engineering/memory")
    def v1_engineering_memory(workspace: str, refresh: bool = False) -> dict[str, Any]:
        try:
            data = engineering_execution.engineering_memory(workspace, refresh=refresh, persist=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EngineeringExecutionPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("engineering.memory", data, workspace)

    @app.post("/v1/engineering/memory")
    def v1_refresh_engineering_memory(request: EngineeringMemoryRequest) -> dict[str, Any]:
        try:
            data = engineering_execution.engineering_memory(request.workspace, refresh=request.refresh, persist=request.persist)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EngineeringExecutionPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("engineering.memory", data, request.workspace)

    @app.get("/v1/engineering/metrics")
    def v1_engineering_metrics(workspace: str) -> dict[str, Any]:
        try:
            data = engineering_execution.execution_metrics(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("engineering.metrics", data, workspace)

    @app.post("/v1/engineering/roadmap/execute")
    def v1_engineering_roadmap_execute(request: EngineeringRoadmapExecuteRequest) -> dict[str, Any]:
        try:
            data = engineering_execution.create_roadmap_execution(
                request.workspace,
                goal=request.goal,
                roadmap_item_id=request.roadmap_item_id,
                roadmap_phase_id=request.roadmap_phase_id,
                source_client=request.source_client,
                target_files=request.target_files,
                validation_command=request.validation_command,
                constraints=request.constraints,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EngineeringExecutionPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("engineering.execution.created", data, request.workspace)

    @app.get("/v1/autopilot/modes")
    def v1_autopilot_modes() -> dict[str, Any]:
        return envelope("autopilot.modes", autopilot_runtime.autopilot_modes())

    @app.post("/v1/autopilot/start")
    def v1_start_autopilot(request: AutopilotStartRequest) -> dict[str, Any]:
        try:
            data = autopilot_runtime.start_autopilot(
                request.workspace,
                request.objective,
                mode=request.mode,
                workflow_type=request.workflow_type,
                roadmap=request.roadmap,
                target_files=request.target_files,
                constraints=request.constraints,
                validation_commands=request.validation_commands,
                execution_plan=request.execution_plan,
                specialization=request.specialization,
                client_id=request.client_id,
                approval=request.approval,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EngineeringExecutionPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("autopilot.run", data, request.workspace)

    @app.get("/v1/autopilot/runs")
    def v1_autopilot_runs(
        workspace: str,
        status: str | None = None,
        mode: str | None = None,
        workflow_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            data = autopilot_runtime.list_autopilot_runs(
                workspace,
                status=status,
                mode=mode,
                workflow_type=workflow_type,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("autopilot.runs", data, workspace)

    @app.get("/v1/autopilot/runs/{autopilot_id}")
    def v1_autopilot_run(autopilot_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = {"run": autopilot_runtime.get_autopilot_run(workspace, autopilot_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return envelope("autopilot.dashboard", data, workspace)

    @app.post("/v1/autopilot/runs/{autopilot_id}/action")
    def v1_autopilot_action(autopilot_id: str, request: AutopilotActionRequest) -> dict[str, Any]:
        try:
            data = autopilot_runtime.autopilot_action(
                request.workspace,
                autopilot_id,
                request.action,
                approval=request.approval,
                payload=request.payload,
                summary=request.summary,
                client_id=request.client_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("autopilot.action", data, request.workspace)

    @app.get("/v1/autopilot/runs/{autopilot_id}/replay")
    def v1_autopilot_replay(autopilot_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = autopilot_runtime.autopilot_replay(workspace, autopilot_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return envelope("autopilot.replay", data, workspace)

    @app.get("/v1/autopilot/supervision")
    def v1_autopilot_supervision(workspace: str, autopilot_id: str | None = None) -> dict[str, Any]:
        try:
            data = autopilot_runtime.autopilot_supervision(workspace, autopilot_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return envelope("autopilot.supervision", data, workspace)

    @app.get("/v1/autopilot/observability")
    def v1_autopilot_observability(workspace: str) -> dict[str, Any]:
        data = autopilot_runtime.autopilot_observability(workspace)
        return envelope("autopilot.observability", data, workspace)

    @app.get("/v1/autopilot/memory")
    def v1_autopilot_memory(workspace: str) -> dict[str, Any]:
        data = autopilot_runtime.autopilot_memory(workspace)
        return envelope("autopilot.memory", data, workspace)

    @app.get("/v1/autopilot/client-hooks")
    def v1_autopilot_client_hooks() -> dict[str, Any]:
        return envelope("autopilot.client_hooks", autopilot_runtime.autopilot_client_hooks())

    @app.get("/v1/workflows/events")
    def v1_all_workflow_events(
        workspace: str,
        since: int = 0,
        limit: int = 100,
        follow: bool = False,
        max_seconds: int = 30,
    ):
        from fastapi.responses import StreamingResponse

        try:
            stream = workflow_runtime.event_stream(
                workspace,
                since=since,
                limit=limit,
                follow=follow,
                max_seconds=max_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(stream, media_type="text/event-stream")

    @app.get("/v1/workflows/{workflow_id}")
    def v1_workflow(workflow_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = workflow_runtime.workflow_dashboard(workspace, workflow_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.dashboard", data, workspace)

    @app.get("/v1/workflows/{workflow_id}/agents")
    def v1_workflow_agents(workflow_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = workflow_runtime.workflow_agent_dashboard(workspace, workflow_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("agent.coordination", data, workspace)

    @app.post("/v1/workflows/{workflow_id}/agents/delegate")
    def v1_workflow_agent_delegate(workflow_id: str, request: AgentDelegationRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.step_workflow(
                request.workspace,
                workflow_id,
                action="delegate_task",
                task_id=request.task_id,
                approval=request.approval,
                summary=request.reason,
                payload={"agent_id": request.agent_id, **request.metadata},
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except (ValueError, WorkflowPersistenceError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("agent.delegation", data, request.workspace)

    @app.post("/v1/workflows/{workflow_id}/step")
    def v1_step_workflow(workflow_id: str, request: WorkflowActionRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.step_workflow(
                request.workspace,
                workflow_id,
                action=request.action,
                task_id=request.task_id,
                approval=request.approval,
                summary=request.summary,
                payload=request.payload,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except (ValueError, WorkflowPersistenceError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.step", data, request.workspace)

    @app.post("/v1/workflows/{workflow_id}/pause")
    def v1_pause_workflow(workflow_id: str, request: WorkflowActionRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.pause_workflow(request.workspace, workflow_id, summary=request.summary or "")
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.step", data, request.workspace)

    @app.post("/v1/workflows/{workflow_id}/resume")
    def v1_resume_workflow(workflow_id: str, request: WorkflowActionRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.resume_workflow(request.workspace, workflow_id, summary=request.summary or "")
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.step", data, request.workspace)

    @app.post("/v1/workflows/{workflow_id}/cancel")
    def v1_cancel_workflow(workflow_id: str, request: WorkflowActionRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.cancel_workflow(request.workspace, workflow_id, summary=request.summary or "")
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.step", data, request.workspace)

    @app.post("/v1/workflows/{workflow_id}/retry")
    def v1_retry_workflow_task(workflow_id: str, request: WorkflowActionRequest) -> dict[str, Any]:
        if not request.task_id:
            raise HTTPException(status_code=400, detail="task_id is required")
        try:
            data = workflow_runtime.retry_workflow_task(
                request.workspace,
                workflow_id,
                task_id=request.task_id,
                summary=request.summary or "",
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.step", data, request.workspace)

    @app.get("/v1/workflows/{workflow_id}/events")
    def v1_workflow_events(
        workflow_id: str,
        workspace: str,
        since: int = 0,
        limit: int = 100,
        follow: bool = False,
        max_seconds: int = 30,
    ):
        from fastapi.responses import StreamingResponse

        try:
            stream = workflow_runtime.event_stream(
                workspace,
                workflow_id=workflow_id,
                since=since,
                limit=limit,
                follow=follow,
                max_seconds=max_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(stream, media_type="text/event-stream")

    @app.post("/v1/clients/sync")
    def v1_client_sync(request: ClientSyncRequest) -> dict[str, Any]:
        try:
            data = workflow_runtime.sync_client(
                request.workspace,
                client_id=request.client_id,
                client_type=request.client_type,
                name=request.name,
                version=request.version,
                capabilities=request.capabilities,
                active_workflow_id=request.active_workflow_id,
                status=request.status,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except WorkflowPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("client.sync", data, request.workspace)

    @app.get("/v1/client-sync")
    def v1_client_sync_dashboard(workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = workflow_runtime.sync_dashboard(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("client.sync.dashboard", data, workspace)

    @app.get("/v1/quality")
    def v1_quality(workspace: str) -> dict[str, Any]:
        return envelope("quality.dashboard", quality_dashboard(workspace), workspace)

    @app.post("/v1/quality/snapshot")
    def v1_quality_snapshot(request: WorkspaceRequest) -> dict[str, Any]:
        try:
            data = record_quality_snapshot(request.workspace)
        except QualityPersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("quality.snapshot", data, request.workspace)

    @app.get("/v1/quality-gates")
    def v1_quality_gates(workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = quality_gates.quality_gate_dashboard(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("quality.gates", data, workspace)

    @app.post("/v1/quality-gates/evaluate")
    def v1_evaluate_quality_gates(request: QualityGateEvaluateRequest) -> dict[str, Any]:
        try:
            data = quality_gates.evaluate_quality_gates(
                request.workspace,
                changes=[item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict() for item in request.changes],
                workflow_id=request.workflow_id,
                validation_id=request.validation_id,
                validation=request.validation,
                approval=request.approval,
                checkpoint_id=request.checkpoint_id,
                max_files_changed=request.max_files_changed,
                restricted_paths=request.restricted_paths,
                validation_required=request.validation_required,
                dry_run=request.dry_run,
                metadata=request.metadata,
                persist=request.persist,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except QualityGatePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("quality.gates.evaluate", data, request.workspace, ok=bool(data.get("apply_allowed", False)))

    @app.get("/v1/workflows/{workflow_id}/quality")
    def v1_workflow_quality(workflow_id: str, workspace: str) -> dict[str, Any]:
        try:
            data = quality_gates.workflow_quality(workspace, workflow_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("workflow.quality", data, workspace)

    @app.get("/v1/benchmarks")
    def v1_quality_benchmarks(workspace: str, limit: int = 50) -> dict[str, Any]:
        try:
            data = quality_gates.benchmark_dashboard(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("quality.benchmarks", data, workspace)

    @app.post("/v1/benchmarks/run")
    def v1_run_quality_benchmark(request: BenchmarkRunRequest) -> dict[str, Any]:
        try:
            data = quality_gates.run_benchmark_suite(
                request.workspace,
                suite_ids=request.suite_ids,
                workflow_id=request.workflow_id,
                metadata=request.metadata,
            )
        except QualityGatePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("quality.benchmark.run", data, request.workspace, ok=data.get("status") != "failed")

    @app.get("/v1/evaluation-reports")
    def v1_evaluation_reports(workspace: str, workflow_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        try:
            data = quality_gates.list_evaluation_reports(workspace, workflow_id=workflow_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("quality.evaluation_reports", data, workspace)

    @app.post("/v1/evaluation-reports")
    def v1_create_evaluation_report(request: EvaluationReportRequest) -> dict[str, Any]:
        try:
            data = quality_gates.create_evaluation_report(
                request.workspace,
                workflow_id=request.workflow_id,
                quality_run_id=request.quality_run_id,
                title=request.title,
                changes=[item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict() for item in request.changes],
                tests_run=request.tests_run,
                repairs_attempted=request.repairs_attempted,
                metadata=request.metadata,
            )
        except QualityGateEvaluationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="quality gate evaluation not found") from exc
        except QualityGatePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("quality.evaluation_report", data, request.workspace, ok=data.get("status") != "blocked")

    @app.get("/v1/knowledge/graph")
    def v1_knowledge_graph(workspace: str) -> dict[str, Any]:
        return envelope("knowledge.graph", knowledge_graph(workspace), workspace)

    @app.post("/v1/knowledge/graph")
    def v1_record_knowledge_graph(request: WorkspaceRequest) -> dict[str, Any]:
        try:
            data = knowledge_graph(request.workspace, persist=True)
        except KnowledgePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("knowledge.graph", data, request.workspace)

    @app.post("/v1/knowledge/query")
    def v1_knowledge_query(request: KnowledgeQueryRequest) -> dict[str, Any]:
        return envelope("knowledge.query", query_knowledge_graph(request.workspace, request.query, focus=request.focus), request.workspace)

    @app.post("/v1/knowledge/search")
    def v1_knowledge_search(request: KnowledgeSearchRequest) -> dict[str, Any]:
        return envelope(
            "knowledge.search",
            search_knowledge(request.workspace, request.query, node_type=request.node_type, limit=request.limit),
            request.workspace,
        )

    @app.post("/v1/knowledge/relationships")
    def v1_knowledge_relationships(request: KnowledgeRelationshipsRequest) -> dict[str, Any]:
        return envelope(
            "knowledge.relationships",
            knowledge_relationships(
                request.workspace,
                request.focus,
                relationship=request.relationship,
                depth=request.depth,
                direction=request.direction,
                limit=request.limit,
            ),
            request.workspace,
        )

    @app.post("/v1/knowledge/symbol")
    def v1_knowledge_symbol(request: KnowledgeSymbolRequest) -> dict[str, Any]:
        return envelope("knowledge.symbol", knowledge_symbol(request.workspace, request.symbol, limit=request.limit), request.workspace)

    @app.post("/v1/knowledge/impact-analysis")
    def v1_knowledge_impact_analysis(request: KnowledgeImpactAnalysisRequest) -> dict[str, Any]:
        return envelope(
            "knowledge.impact_analysis",
            impact_analysis(request.workspace, request.target, change_type=request.change_type, limit=request.limit),
            request.workspace,
        )

    @app.get("/v1/knowledge/architecture-summary")
    def v1_knowledge_architecture_summary(workspace: str, refresh: bool = False) -> dict[str, Any]:
        return envelope("knowledge.architecture_summary", architecture_summary(workspace, refresh=refresh), workspace)

    @app.post("/v1/simulation/change")
    def v1_simulate_change(request: SimulationRequest) -> dict[str, Any]:
        try:
            data = simulate_change(
                request.workspace,
                request.objective,
                files=request.files,
                approach=request.approach,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("simulation.change", data, request.workspace)

    @app.post("/v1/simulation/compare")
    def v1_compare_simulations(request: SimulationCompareRequest) -> dict[str, Any]:
        try:
            data = compare_scenarios(
                request.workspace,
                request.objective,
                request.approaches,
                files=request.files,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("simulation.compare", data, request.workspace)

    @app.get("/v1/operations")
    def v1_operations(workspace: str) -> dict[str, Any]:
        return envelope("operations.dashboard", engineering_operations_dashboard(workspace), workspace)

    @app.post("/v1/operations/dashboard")
    def v1_operations_dashboard(request: OperationsRequest) -> dict[str, Any]:
        return envelope(
            "operations.dashboard",
            engineering_operations_dashboard(request.workspace, project_roots=request.project_roots),
            request.workspace,
        )

    @app.get("/v1/personal-intelligence")
    def v1_personal_intelligence(workspace: str) -> dict[str, Any]:
        return envelope("personal.intelligence", adaptive_personal_intelligence(workspace), workspace)

    @app.post("/v1/personal-intelligence/profile")
    def v1_personal_intelligence_profile(request: PersonalIntelligenceRequest) -> dict[str, Any]:
        try:
            data = adaptive_personal_intelligence(
                request.workspace,
                project_roots=request.project_roots,
                preferences=request.preferences,
                persist=request.persist,
            )
        except PersonalIntelligencePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope(
            "personal.intelligence",
            data,
            request.workspace,
        )

    @app.post("/v1/personal-intelligence/reset")
    def v1_personal_intelligence_reset(request: WorkspaceRequest) -> dict[str, Any]:
        data = reset_personal_intelligence(request.workspace)
        return envelope("personal.intelligence.reset", data, request.workspace, ok=bool(data.get("reset", False)))

    @app.get("/v1/personal-memory")
    def v1_personal_memory(
        workspace: str,
        query: str = "",
        category: str | None = None,
        scope: str | None = None,
        include_archived: bool = False,
        include_disabled: bool = False,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            data = personal_memory.memory_dashboard(
                workspace,
                query=query,
                category=category,
                scope=scope,
                include_archived=include_archived,
                include_disabled=include_disabled,
                limit=limit,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory", data, workspace)

    @app.post("/v1/personal-memory/query")
    def v1_personal_memory_query(request: PersonalMemoryQueryRequest) -> dict[str, Any]:
        try:
            data = personal_memory.memory_dashboard(
                request.workspace,
                query=request.query,
                category=request.category,
                scope=request.scope,
                include_archived=request.include_archived,
                include_disabled=request.include_disabled,
                limit=request.limit,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory", data, request.workspace)

    @app.post("/v1/personal-memory")
    def v1_create_personal_memory(request: PersonalMemoryCreateRequest) -> dict[str, Any]:
        try:
            data = personal_memory.create_memory(
                request.workspace,
                category=request.category,
                title=request.title,
                content=request.content,
                scope=request.scope,
                tags=request.tags,
                related_files=request.related_files,
                source=request.source,
                confidence=request.confidence,
                pinned=request.pinned,
                expires_at=request.expires_at,
                privacy=request.privacy,
                metadata=request.metadata,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.record", data, request.workspace)

    @app.post("/v1/personal-memory/records/{memory_id}")
    @app.patch("/v1/personal-memory/records/{memory_id}")
    def v1_update_personal_memory(memory_id: str, request: PersonalMemoryUpdateRequest) -> dict[str, Any]:
        try:
            data = personal_memory.update_memory(
                request.workspace,
                memory_id,
                category=request.category,
                title=request.title,
                content=request.content,
                scope=request.scope,
                tags=request.tags,
                related_files=request.related_files,
                confidence=request.confidence,
                pinned=request.pinned,
                expires_at=request.expires_at,
                privacy=request.privacy,
                metadata=request.metadata,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.record", data, request.workspace)

    @app.post("/v1/personal-memory/records/{memory_id}/archive")
    def v1_archive_personal_memory(memory_id: str, request: PersonalMemoryArchiveRequest) -> dict[str, Any]:
        try:
            data = personal_memory.archive_memory(request.workspace, memory_id, reason=request.reason)
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.record", data, request.workspace)

    @app.post("/v1/personal-memory/records/{memory_id}/delete")
    @app.delete("/v1/personal-memory/records/{memory_id}")
    def v1_delete_personal_memory(memory_id: str, request: PersonalMemoryDeleteRequest) -> dict[str, Any]:
        try:
            data = personal_memory.delete_memory(
                request.workspace,
                memory_id,
                hard_delete=request.hard_delete,
                reason=request.reason,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.deleted", data, request.workspace, ok=bool(data.get("deleted", False)))

    @app.post("/v1/personal-memory/export")
    def v1_export_personal_memory(request: PersonalMemoryExportRequest) -> dict[str, Any]:
        try:
            data = personal_memory.export_memory(
                request.workspace,
                categories=request.categories,
                include_archived=request.include_archived,
                redact_sensitive=request.redact_sensitive,
                include_controls=request.include_controls,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.export", data, request.workspace)

    @app.post("/v1/personal-memory/import")
    def v1_import_personal_memory(request: PersonalMemoryImportRequest) -> dict[str, Any]:
        try:
            data = personal_memory.import_memory(
                request.workspace,
                request.payload,
                merge_strategy=request.merge_strategy,
                dry_run=request.dry_run,
                source=request.source,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.import", data, request.workspace)

    @app.post("/v1/personal-memory/controls")
    def v1_personal_memory_controls(request: PersonalMemoryControlsRequest) -> dict[str, Any]:
        try:
            data = personal_memory.update_memory_controls(
                request.workspace,
                category=request.category,
                enabled=request.enabled,
                retention_days=request.retention_days,
                include_in_orchestration=request.include_in_orchestration,
                encrypted=request.encrypted,
                local_only=request.local_only,
                disabled_categories=request.disabled_categories,
                allowed_scopes=request.allowed_scopes,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.controls", data, request.workspace)

    @app.post("/v1/personal-memory/cleanup")
    def v1_personal_memory_cleanup(request: PersonalMemoryCleanupRequest) -> dict[str, Any]:
        try:
            data = personal_memory.cleanup_memory(request.workspace, dry_run=request.dry_run, archive_stale=request.archive_stale)
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.cleanup", data, request.workspace)

    @app.get("/v1/personal-memory/observability")
    def v1_personal_memory_observability(workspace: str) -> dict[str, Any]:
        try:
            data = personal_memory.memory_observability(workspace)
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.observability", data, workspace)

    @app.post("/v1/personal-memory/context")
    def v1_personal_memory_context(request: PersonalMemoryContextRequest) -> dict[str, Any]:
        try:
            data = personal_memory.memory_orchestration_context(
                request.workspace,
                workflow_type=request.workflow_type,
                objective=request.objective,
                max_items=request.max_items,
                record_usage=request.record_usage,
            )
        except PersonalMemoryPersistenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return envelope("personal.memory.context", data, request.workspace)

    @app.post("/v1/tasks")
    def v1_create_task(request: CreateTaskRequest) -> dict[str, Any]:
        try:
            task = create_task(
                request.workspace,
                request.title,
                kind=request.kind,
                source_client=request.source_client,
                request=request.request,
                metadata=request.metadata,
            )
        except TaskStorePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("task.created", task, request.workspace)

    @app.get("/v1/tasks")
    def v1_tasks(workspace: str, include_completed: bool = True) -> dict[str, Any]:
        return envelope("tasks.list", list_tasks(workspace, include_completed=include_completed), workspace)

    @app.post("/v1/tasks/{task_id}/status")
    def v1_update_task(task_id: str, request: TaskStatusRequest) -> dict[str, Any]:
        try:
            task = update_task_status(request.workspace, task_id, request.status, request.summary)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TaskStorePersistenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return envelope("task.updated", task, request.workspace)

    @app.post("/v1/validation")
    def v1_validation(request: ValidateRequest) -> dict[str, Any]:
        data = run_validation(request.workspace, command=request.command) if request.run else validation_summary(request.workspace)
        return envelope("validation", data, request.workspace, ok=bool(data.get("ok", True)))

    @app.post("/v1/agent/continue")
    def v1_continue_agent(request: ContinueRequest) -> dict[str, Any]:
        plan = continue_from_roadmap(request.workspace, request.request)
        try:
            task = create_task(
                request.workspace,
                plan.get("task", request.request or "Continue from roadmap"),
                kind="continue",
                source_client="aegis-core",
                request=request.request,
                metadata={"plan_path": ".aegis/active-agent-plan.json", "risk": plan.get("risk")},
            )
        except TaskStorePersistenceError as exc:
            return envelope("agent.continue.plan", {"plan": plan, "task": None, "memory_warning": str(exc)}, request.workspace, ok=False)
        return envelope("agent.continue.plan", {"plan": plan, "task": task}, request.workspace)

    @app.post("/v1/agent/repair")
    def v1_repair(request: WorkspaceRequest) -> dict[str, Any]:
        plan = repair_from_last_validation(request.workspace)
        if plan.get("ok"):
            try:
                task = create_task(
                    request.workspace,
                    "Repair latest validation failure",
                    kind="repair",
                    source_client="aegis-core",
                    metadata={"plan_path": ".aegis/active-repair-plan.json", "repair_attempt_limit": plan.get("repair_attempt_limit")},
                )
            except TaskStorePersistenceError as exc:
                return envelope("agent.repair.plan", {"plan": plan, "task": None, "memory_warning": str(exc)}, request.workspace, ok=False)
        else:
            task = None
        return envelope("agent.repair.plan", {"plan": plan, "task": task}, request.workspace, ok=bool(plan.get("ok")))

    @app.get("/v1/ecosystem/dashboard")
    def v1_dashboard(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.dashboard", dashboard_summary(workspace), workspace)

    return app
