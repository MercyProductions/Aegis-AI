from pathlib import Path
from typing import Any

from .agent import continue_from_roadmap, repair_from_last_validation
from .branding import branding_tokens
from .clients import list_clients, register_client
from .config import load_config, update_config, write_default_config
from .diagnostics import CoreLogger
from .ecosystem import dashboard_summary, diagnostics_summary, shared_memory_summary
from .ollama import OllamaClient
from .roadmap import generate_roadmap
from .tasks import create_task, list_tasks, update_task_status
from .validation import run_validation, validation_summary
from .workspace import WorkspaceScanner


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("Install Aegis Core API dependencies with `pip install -e .`.") from exc

    class WorkspaceRequest(BaseModel):
        workspace: str

    class ContinueRequest(BaseModel):
        workspace: str
        request: str | None = None

    class ValidateRequest(BaseModel):
        workspace: str
        run: bool = False
        command: list[str] | None = None

    class SettingsRequest(BaseModel):
        workspace: str
        settings: dict[str, Any]

    class ClientRegistrationRequest(BaseModel):
        workspace: str
        client_id: str
        client_type: str
        name: str
        version: str = "unknown"
        capabilities: list[str] | None = None

    class CreateTaskRequest(BaseModel):
        workspace: str
        title: str
        kind: str = "general"
        source_client: str = "unknown"
        request: str | None = None
        metadata: dict[str, Any] | None = None

    class TaskStatusRequest(BaseModel):
        workspace: str
        status: str
        summary: str | None = None

    app = FastAPI(title="Aegis Core", version="0.1.0")

    def envelope(kind: str, data: Any, workspace: str | None = None, ok: bool = True) -> dict[str, Any]:
        return {
            "ok": ok,
            "api_version": "v1",
            "kind": kind,
            "workspace": str(Path(workspace).resolve()) if workspace else None,
            "data": data,
        }

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

    @app.get("/v1/settings")
    def v1_settings(workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace or ".").resolve()
        return envelope("settings", load_config(root).to_dict(), str(root))

    @app.post("/v1/settings")
    def v1_update_settings(request: SettingsRequest) -> dict[str, Any]:
        config = update_config(request.workspace, request.settings)
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
        client = register_client(
            request.workspace,
            request.client_id,
            request.client_type,
            request.name,
            request.version,
            request.capabilities,
        )
        return envelope("client.registered", client, request.workspace)

    @app.get("/v1/clients")
    def v1_clients(workspace: str) -> dict[str, Any]:
        return envelope("clients.list", list_clients(workspace), workspace)

    @app.post("/v1/tasks")
    def v1_create_task(request: CreateTaskRequest) -> dict[str, Any]:
        task = create_task(
            request.workspace,
            request.title,
            kind=request.kind,
            source_client=request.source_client,
            request=request.request,
            metadata=request.metadata,
        )
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
        return envelope("task.updated", task, request.workspace)

    @app.post("/v1/validation")
    def v1_validation(request: ValidateRequest) -> dict[str, Any]:
        data = run_validation(request.workspace, command=request.command) if request.run else validation_summary(request.workspace)
        return envelope("validation", data, request.workspace, ok=bool(data.get("ok", True)))

    @app.post("/v1/agent/continue")
    def v1_continue_agent(request: ContinueRequest) -> dict[str, Any]:
        plan = continue_from_roadmap(request.workspace, request.request)
        task = create_task(
            request.workspace,
            plan.get("task", request.request or "Continue from roadmap"),
            kind="continue",
            source_client="aegis-core",
            request=request.request,
            metadata={"plan_path": ".aegis/active-agent-plan.json", "risk": plan.get("risk")},
        )
        return envelope("agent.continue.plan", {"plan": plan, "task": task}, request.workspace)

    @app.post("/v1/agent/repair")
    def v1_repair(request: WorkspaceRequest) -> dict[str, Any]:
        plan = repair_from_last_validation(request.workspace)
        if plan.get("ok"):
            task = create_task(
                request.workspace,
                "Repair latest validation failure",
                kind="repair",
                source_client="aegis-core",
                metadata={"plan_path": ".aegis/active-repair-plan.json", "repair_attempt_limit": plan.get("repair_attempt_limit")},
            )
        else:
            task = None
        return envelope("agent.repair.plan", {"plan": plan, "task": task}, request.workspace, ok=bool(plan.get("ok")))

    @app.get("/v1/ecosystem/dashboard")
    def v1_dashboard(workspace: str) -> dict[str, Any]:
        return envelope("ecosystem.dashboard", dashboard_summary(workspace), workspace)

    return app
