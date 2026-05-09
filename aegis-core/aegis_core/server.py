from pathlib import Path
from typing import Any

from .agent import continue_from_roadmap, repair_from_last_validation
from .branding import branding_tokens
from .clients import ClientRegistryPersistenceError, list_clients, register_client
from .config import ConfigPersistenceError, load_config, update_config, write_default_config
from .contracts import (
    ClientRegistrationRequest,
    ContinueRequest,
    CreateTaskRequest,
    JobRunRequest,
    KnowledgeQueryRequest,
    ModelCompletionRequest,
    ModelRouteRequest,
    OperationsRequest,
    OrchestrationPlanRequest,
    OrchestrationStepRequest,
    PersonalIntelligenceRequest,
    ProviderKeyRequest,
    SimulationCompareRequest,
    SimulationRequest,
    SettingsRequest,
    TaskStatusRequest,
    ValidateRequest,
    WorkspaceRequest,
    make_envelope,
)
from .credentials import CredentialStoreError
from .diagnostics import CoreLogger
from .ecosystem import dashboard_summary, diagnostics_summary, shared_memory_summary
from .jobs import JobPersistenceError, jobs_dashboard, run_job
from .knowledge import knowledge_graph, query_knowledge_graph
from .model_router import complete_with_route, delete_provider_key, provider_inventory, route_model, store_provider_key
from .multi_agent import agent_roster
from .ollama import OllamaClient
from .operations import engineering_operations_dashboard
from .orchestration import OrchestrationPersistenceError, advance_orchestration_step, create_orchestration_plan, orchestration_dashboard
from .personal_intelligence import adaptive_personal_intelligence, reset_personal_intelligence
from .quality import QualityPersistenceError, quality_dashboard, record_quality_snapshot
from .roadmap import generate_roadmap
from .simulation import compare_scenarios, simulate_change
from .tasks import TaskStorePersistenceError, create_task, list_tasks, update_task_status
from .validation import run_validation, validation_summary
from .workspace import WorkspaceScanner


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install Aegis Core API dependencies with `pip install -e .`.") from exc

    app = FastAPI(title="Aegis Core", version="0.1.0")

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
        return generate_roadmap(request.workspace, persist=True)

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

    @app.post("/v1/workspaces/scan")
    def v1_scan(request: WorkspaceRequest) -> dict[str, Any]:
        return envelope("workspace.scan", WorkspaceScanner(request.workspace).scan(persist=True), request.workspace)

    @app.post("/v1/workspaces/roadmap")
    def v1_roadmap(request: WorkspaceRequest) -> dict[str, Any]:
        return envelope("workspace.roadmap", generate_roadmap(request.workspace, persist=True), request.workspace)

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

    @app.get("/v1/knowledge/graph")
    def v1_knowledge_graph(workspace: str) -> dict[str, Any]:
        return envelope("knowledge.graph", knowledge_graph(workspace), workspace)

    @app.post("/v1/knowledge/graph")
    def v1_record_knowledge_graph(request: WorkspaceRequest) -> dict[str, Any]:
        return envelope("knowledge.graph", knowledge_graph(request.workspace, persist=True), request.workspace)

    @app.post("/v1/knowledge/query")
    def v1_knowledge_query(request: KnowledgeQueryRequest) -> dict[str, Any]:
        return envelope("knowledge.query", query_knowledge_graph(request.workspace, request.query, focus=request.focus), request.workspace)

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
        return envelope(
            "personal.intelligence",
            adaptive_personal_intelligence(
                request.workspace,
                project_roots=request.project_roots,
                preferences=request.preferences,
                persist=request.persist,
            ),
            request.workspace,
        )

    @app.post("/v1/personal-intelligence/reset")
    def v1_personal_intelligence_reset(request: WorkspaceRequest) -> dict[str, Any]:
        data = reset_personal_intelligence(request.workspace)
        return envelope("personal.intelligence.reset", data, request.workspace, ok=bool(data.get("reset", False)))

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
