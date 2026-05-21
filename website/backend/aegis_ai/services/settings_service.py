from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from ..core_bridge import CoreBridgeResult
from ..schemas import AppConfig, ConfigUpdateRequest, ModeOption
from ..services.core_client import CoreDelegationResult
from ..storage import utc_now


class SettingsService:
    def __init__(
        self,
        *,
        settings_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        core_bridge_factory: Callable[[], Any],
        core_runtime_client_factory: Callable[[], Any],
        workspace_manager_factory: Callable[[], Any],
        workspace_resolver: Callable[[str | None], Path],
        config_workspace_resolver: Callable[[str | None], Path],
        database_path_resolver: Callable[[str], Path],
        update_env: Callable[[dict[str, str]], None],
        refresh_runtime: Callable[[], None],
        has_env_file: Callable[[], bool],
        core_result_data: Callable[[CoreBridgeResult | None], dict[str, Any]],
        core_route_message: Callable[[CoreBridgeResult | None, str], str],
        core_route_status: Callable[[CoreBridgeResult | None], str],
        core_contract_version: Callable[[CoreBridgeResult | None], str],
        core_delegation_data: Callable[[CoreDelegationResult, str], dict[str, Any]],
        record_core_fallback: Callable[[str, CoreDelegationResult], None],
        mode_options: Sequence[tuple[str, str, str]],
    ) -> None:
        self._settings_factory = settings_factory
        self._agent_factory = agent_factory
        self._core_bridge_factory = core_bridge_factory
        self._core_runtime_client_factory = core_runtime_client_factory
        self._workspace_manager_factory = workspace_manager_factory
        self._workspace_resolver = workspace_resolver
        self._config_workspace_resolver = config_workspace_resolver
        self._database_path_resolver = database_path_resolver
        self._update_env = update_env
        self._refresh_runtime = refresh_runtime
        self._has_env_file = has_env_file
        self._core_result_data = core_result_data
        self._core_route_message = core_route_message
        self._core_route_status = core_route_status
        self._core_contract_version = core_contract_version
        self._core_delegation_data = core_delegation_data
        self._record_core_fallback = record_core_fallback
        self._mode_options = mode_options

    @property
    def settings(self) -> Any:
        return self._settings_factory()

    @property
    def agent(self) -> Any:
        return self._agent_factory()

    @property
    def core_bridge(self) -> Any:
        return self._core_bridge_factory()

    @property
    def core_runtime_client(self) -> Any:
        return self._core_runtime_client_factory()

    @property
    def workspace_manager(self) -> Any:
        return self._workspace_manager_factory()

    async def config_snapshot(self) -> AppConfig:
        settings = self.settings
        default_mode = settings.default_mode.strip().lower()
        if default_mode not in {"build", "develop", "review", "chat"}:
            default_mode = "build"

        model_status = await self.agent.model_status()
        default_workspace = self._config_workspace_resolver(None)
        core_settings = await self.core_bridge.settings_status(default_workspace)
        core_settings_data = self._core_result_data(core_settings)
        engine_message = "The local Aegis backend is ready. No external AI provider is required."
        model_message = model_status.message
        core_default_model = str(core_settings_data.get("default_model") or "").strip()
        core_ollama_url = str(core_settings_data.get("ollama_url") or "").strip().rstrip("/")
        if core_settings.ok:
            if core_default_model and core_default_model != settings.aegis_model_name:
                model_message = f"{model_message} Shared Core default model: {core_default_model}."
            if core_ollama_url and core_ollama_url != settings.aegis_model_endpoint.strip().rstrip("/"):
                engine_message = f"{engine_message} Shared Core Ollama URL: {core_ollama_url}."
        else:
            engine_message = self._core_route_message(core_settings, "settings")

        return AppConfig(
            assistant_name=settings.aegis_assistant_name,
            assistant_mission=settings.aegis_assistant_mission,
            default_mode=default_mode,  # type: ignore[arg-type]
            modes=[ModeOption(id=mode, label=label, description=description) for mode, label, description in self._mode_options],
            default_workspace=str(default_workspace),
            engine=f"Aegis Core / {settings.aegis_model_name}",
            engine_ready=True,
            engine_message=engine_message,
            model_name=settings.aegis_model_name,
            model_endpoint=settings.aegis_model_endpoint,
            model_api=settings.aegis_model_api,
            model_ready=model_status.ready,
            model_message=model_message,
            database_path=str(self._database_path_resolver(settings.aegis_database_path)),
            command_allowlist=settings.aegis_command_allowlist,
            command_timeout_seconds=settings.aegis_command_timeout_seconds,
            auto_run_validation=settings.aegis_auto_run_validation,
            router_execution_enabled=settings.aegis_router_execution_enabled,
            shared_workspace_mode=settings.aegis_shared_workspace_mode,
            feedback_capture_excerpts=settings.aegis_feedback_capture_excerpts,
            feedback_redaction_enabled=settings.aegis_feedback_redaction_enabled,
            feedback_max_excerpt_chars=max(0, min(2000, settings.aegis_feedback_max_excerpt_chars)),
            feedback_hash_content=settings.aegis_feedback_hash_content,
            env_exists=self._has_env_file(),
            core_runtime_reachable=core_settings.reachable,
            core_runtime_status=self._core_route_status(core_settings),
            core_contract_version=self._core_contract_version(core_settings),
            core_runtime_message=self._core_route_message(core_settings, "settings"),
        )

    async def save_config(
        self,
        request: ConfigUpdateRequest,
        *,
        config_snapshot: Callable[[], Awaitable[AppConfig]] | None = None,
    ) -> AppConfig:
        settings = self.settings
        assistant_name = request.assistant_name if request.assistant_name is not None else settings.aegis_assistant_name
        assistant_mission = (
            request.assistant_mission if request.assistant_mission is not None else settings.aegis_assistant_mission
        )
        default_mode = request.default_mode if request.default_mode is not None else settings.default_mode
        if default_mode not in {"build", "develop", "review", "chat"}:
            default_mode = "build"
        default_workspace = request.default_workspace if request.default_workspace is not None else settings.default_workspace
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
            request.auto_run_validation if request.auto_run_validation is not None else settings.aegis_auto_run_validation
        )
        shared_workspace_mode = (
            request.shared_workspace_mode if request.shared_workspace_mode is not None else settings.aegis_shared_workspace_mode
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
            request.feedback_hash_content if request.feedback_hash_content is not None else settings.aegis_feedback_hash_content
        )
        mission = " ".join(part.strip() for part in assistant_mission.splitlines() if part.strip())
        self._update_env(
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
        self._refresh_runtime()
        await self._sync_website_settings_to_core(default_workspace)
        if config_snapshot is not None:
            return await config_snapshot()
        return await self.config_snapshot()

    async def onboarding_status(self, workspace_root: str | None = None) -> dict[str, Any]:
        root = self._config_workspace_resolver(workspace_root)
        result = await self.core_runtime_client.onboarding_status(root)
        if not result.delegated:
            self._record_core_fallback("onboarding.status", result)
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "last_core_error": result.error,
                **self._onboarding_fallback_status(root, result.error),
            }
        return {
            "ok": bool(result.ok),
            "delegated": True,
            "core_connected": True,
            "fallback_mode_active": False,
            "last_core_error": "",
            **self._core_delegation_data(result, "onboarding.status"),
        }

    async def update_onboarding(self, request: dict[str, Any]) -> dict[str, Any]:
        root = self._workspace_resolver(request.get("workspace_root") or request.get("workspace"))
        result = await self.core_runtime_client.update_onboarding(
            root,
            completed_steps=request.get("completed_steps") if isinstance(request.get("completed_steps"), list) else None,
            current_step=str(request.get("current_step") or "").strip() or None,
            preferences=request.get("preferences") if isinstance(request.get("preferences"), dict) else None,
            first_workflow_completed_steps=request.get("first_workflow_completed_steps")
            if isinstance(request.get("first_workflow_completed_steps"), list)
            else None,
            reset=bool(request.get("reset", False)),
        )
        if not result.delegated:
            self._record_core_fallback("onboarding.updated", result)
            fallback = self._onboarding_fallback_status(root, result.error)
            fallback["last_core_error"] = result.error
            return {"ok": False, "delegated": False, "core_connected": result.reachable, "fallback_mode_active": True, **fallback}
        return {"ok": bool(result.ok), "delegated": True, "core_connected": True, **self._core_delegation_data(result, "onboarding.updated")}

    async def run_onboarding_first_workflow(self, request: dict[str, Any]) -> dict[str, Any]:
        root = self._workspace_resolver(request.get("workspace_root") or request.get("workspace"))
        action = str(request.get("action") or "").strip()
        result = await self.core_runtime_client.run_first_workflow(
            root,
            action=action,
            dry_run=bool(request.get("dry_run", True)),
        )
        if not result.delegated:
            self._record_core_fallback("onboarding.first_workflow", result)
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "workspace": str(root),
                "action": action,
                "dry_run": True,
                "result": {
                    "summary": "First workflow requires Aegis Core. Website fallback keeps apply disabled.",
                    "files": [item.path for item in self.workspace_manager.scan(root, max_files=25)],
                },
                "next_actions": ["Reconnect Aegis Core", "Retry the guided first workflow"],
                "error": result.error,
            }
        return {"ok": bool(result.ok), "delegated": True, "core_connected": True, **self._core_delegation_data(result, "onboarding.first_workflow")}

    async def export_runtime_settings(self, workspace_root: str | None = None) -> dict[str, Any]:
        root = self._config_workspace_resolver(workspace_root)
        result = await self.core_runtime_client.export_settings(root)
        if not result.delegated:
            self._record_core_fallback("settings.export", result)
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "last_core_error": result.error,
                **self._fallback_settings_export(root),
            }
        return {"ok": bool(result.ok), "delegated": True, "core_connected": True, **self._core_delegation_data(result, "settings.export")}

    async def import_runtime_settings(self, request: dict[str, Any]) -> dict[str, Any]:
        root = self._workspace_resolver(request.get("workspace_root") or request.get("workspace"))
        settings_payload = request.get("settings") if isinstance(request.get("settings"), dict) else request
        result = await self.core_runtime_client.import_settings(
            root,
            settings_payload=settings_payload,
            dry_run=bool(request.get("dry_run", True)),
        )
        if not result.delegated:
            self._record_core_fallback("settings.import", result)
            exported = self._fallback_settings_export(root)
            return {
                "ok": False,
                "delegated": False,
                "core_connected": result.reachable,
                "fallback_mode_active": True,
                "workspace": str(root),
                "dry_run": True,
                "imported_keys": [],
                "ignored_keys": sorted(str(key) for key in settings_payload),
                "ui_preference_keys": [],
                "settings_preview": exported["settings"],
                "warnings": ["Aegis Core is offline; Website fallback did not import settings."],
                "error": result.error,
            }
        return {"ok": bool(result.ok), "delegated": True, "core_connected": True, **self._core_delegation_data(result, "settings.import")}

    async def _sync_website_settings_to_core(self, default_workspace: str) -> CoreBridgeResult:
        settings = self.settings
        workspace = self._config_workspace_resolver(default_workspace)
        core_updates: dict[str, Any] = {
            "default_model": settings.aegis_model_name.strip(),
            "max_context_chars": settings.max_context_chars,
        }
        if settings.aegis_model_api.strip().lower() == "ollama":
            core_updates["ollama_url"] = settings.aegis_model_endpoint.strip().rstrip("/")
        try:
            return await self.core_bridge.update_settings(workspace, core_updates)
        except Exception as exc:
            return CoreBridgeResult(
                reachable=False,
                ok=False,
                status_code=None,
                kind="settings.updated",
                data=None,
                error=f"Aegis Core settings sync failed after Website config save: {exc}",
            )

    def _onboarding_fallback_status(self, root: Path, reason: str = "") -> dict[str, Any]:
        settings = self.settings
        workspace_exists = root.exists() and root.is_dir()
        writable = False
        if workspace_exists:
            probe = root / ".aegis-website-onboarding-check.tmp"
            try:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                writable = True
            except OSError:
                writable = False
        model_ready = bool(settings.aegis_model_name.strip())
        checks = [
            {
                "id": "core_running",
                "label": "Core Running",
                "status": "warn",
                "detail": reason or "Aegis Core onboarding contract is unavailable; Website is showing fallback diagnostics.",
            },
            {
                "id": "website_backend",
                "label": "Website Backend",
                "status": "pass",
                "detail": "Website backend is reachable and can keep compatibility routes alive.",
            },
            {
                "id": "workspace_permissions",
                "label": "Workspace Permissions",
                "status": "pass" if workspace_exists and writable else "fail",
                "detail": str(root) if workspace_exists and writable else "Select a writable workspace folder.",
            },
            {
                "id": "ollama_running",
                "label": "Ollama Running",
                "status": "pass" if model_ready else "warn",
                "detail": settings.aegis_model_endpoint,
            },
            {
                "id": "models_available",
                "label": "Models Available",
                "status": "pass" if model_ready else "warn",
                "detail": settings.aegis_model_name,
            },
        ]
        failure_count = sum(1 for item in checks if item["status"] == "fail")
        warning_count = sum(1 for item in checks if item["status"] == "warn")
        return {
            "schema_version": 1,
            "workspace": str(root),
            "generated_at": utc_now(),
            "completed": False,
            "current_step": "workspace" if failure_count else "first_workflow",
            "steps": [
                {"id": "welcome", "label": "Welcome", "required": True, "status": "complete", "detail": "Website backend is ready."},
                {"id": "privacy", "label": "Privacy Mode", "required": True, "status": "pending", "detail": "Core privacy settings will be authoritative when Core reconnects."},
                {"id": "local_models", "label": "Local Models", "required": True, "status": "complete" if model_ready else "needs_attention", "detail": settings.aegis_model_name},
                {"id": "workspace", "label": "Workspace", "required": True, "status": "complete" if workspace_exists and writable else "blocked", "detail": str(root)},
                {"id": "first_workflow", "label": "First Workflow", "required": True, "status": "pending", "detail": "Use Core for the full guided workflow when available."},
                {"id": "finish", "label": "Finish Checklist", "required": True, "status": "pending", "detail": "Reconnect Core before applying changes."},
            ],
            "diagnostics": {
                "summary": {
                    "status": "fail" if failure_count else "warn" if warning_count else "pass",
                    "pass_count": sum(1 for item in checks if item["status"] == "pass"),
                    "warning_count": warning_count,
                    "failure_count": failure_count,
                },
                "checks": checks,
            },
            "privacy": {
                "mode": "local-first",
                "model_routing_mode": "local_only" if settings.aegis_model_api == "ollama" else "hybrid",
                "local_only": settings.aegis_model_api == "ollama",
                "cloud_disabled": settings.aegis_model_api == "ollama",
                "provider_usage_warnings": True,
            },
            "recommended_defaults": {
                "checkpoint_before_apply": True,
                "validation_before_apply": True,
                "approval_required_for_apply": True,
                "auto_apply": False,
            },
            "first_workflow": {
                "completed_steps": [],
                "steps": [
                    {"id": "scan_project", "label": "Scan Project", "status": "pending"},
                    {"id": "generate_roadmap", "label": "Generate Roadmap", "status": "pending"},
                    {"id": "explain_architecture", "label": "Explain Architecture", "status": "pending"},
                    {"id": "propose_small_improvement", "label": "Propose Small Improvement", "status": "pending"},
                    {"id": "validate_only", "label": "Validate Only", "status": "pending"},
                    {"id": "checkpoint_rollback_demo", "label": "Checkpoint And Rollback", "status": "pending"},
                ],
                "latest_result": {},
            },
            "recovery": [
                {"id": "backend_down", "title": "Website Backend Down", "active": False, "summary": "Website backend is serving this fallback response."},
                {"id": "core_offline", "title": "Core Offline", "active": True, "summary": reason or "Core is unavailable."},
                {"id": "ollama_offline", "title": "Ollama Offline", "active": not model_ready, "summary": "Start Ollama or choose an available model."},
                {"id": "model_unavailable", "title": "Model Unavailable", "active": not model_ready, "summary": "Choose an installed local model or refresh model diagnostics."},
                {"id": "key_missing", "title": "Provider Key Missing", "active": settings.aegis_model_api != "ollama", "summary": "Link provider keys through account settings; do not import plaintext secrets."},
                {"id": "provider_missing", "title": "Provider Missing", "active": settings.aegis_model_api != "ollama", "summary": "Stay local-only until provider credentials are linked safely."},
                {"id": "workspace_blocked", "title": "Workspace Blocked", "active": not (workspace_exists and writable), "summary": "Select a writable workspace."},
                {"id": "update_failed", "title": "Update Failed", "active": False, "summary": "Use release recovery if update state reports failure."},
                {"id": "validation_failed", "title": "Validation Failed", "active": False, "summary": "Keep work in proposal mode and run validation-only first."},
                {"id": "extension_disconnected", "title": "Extension Disconnected", "active": False, "summary": "Run the editor extension health check after Core reconnects."},
                {"id": "desktop_blank_state", "title": "Desktop Blank State", "active": False, "summary": "Open Desktop setup, select a workspace, and refresh Core runtime status."},
            ],
            "settings": {
                "config": {
                    "default_model": settings.aegis_model_name,
                    "ollama_url": settings.aegis_model_endpoint,
                    "model_routing_mode": "local_only" if settings.aegis_model_api == "ollama" else "hybrid",
                },
                "preferences": {},
            },
            "state_path": "",
        }

    def _fallback_settings_export(self, root: Path) -> dict[str, Any]:
        settings = self.settings
        return {
            "schema_version": 1,
            "exported_at": utc_now(),
            "workspace": str(root),
            "settings": {
                "default_model": settings.aegis_model_name,
                "ollama_url": settings.aegis_model_endpoint,
                "model_routing_mode": "local_only" if settings.aegis_model_api == "ollama" else "hybrid",
                "auto_scan_on_open": False,
            },
            "privacy": {
                "mode": "local-first",
                "local_only": settings.aegis_model_api == "ollama",
                "cloud_disabled": settings.aegis_model_api == "ollama",
            },
            "provider_config_metadata": [],
            "ui_preferences": {},
            "runtime_urls": {"ollama_url": settings.aegis_model_endpoint},
            "workspace_preferences": {"workspace": str(root), "validation_preferences": []},
            "notes": ["Generated by Website fallback. Provider secrets are not exported."],
        }
