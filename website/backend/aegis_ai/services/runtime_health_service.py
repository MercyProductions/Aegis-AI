from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..core_bridge import CoreBridgeResult
from ..schemas import RuntimeHealthResponse


def core_models_from_result(result: CoreBridgeResult | None) -> tuple[set[str], str, bool]:
    data = result.data if result is not None and isinstance(result.data, dict) else {}
    installed = (
        {str(name).strip() for name in data.get("installed_models", []) if str(name).strip()}
        if isinstance(data.get("installed_models"), list)
        else set()
    )
    selected = str(data.get("selected_model") or "").strip()
    reachable = bool(data.get("reachable", False))
    return installed, selected, reachable


def _core_contract_version(result: CoreBridgeResult | None) -> str:
    envelope = result.envelope if result is not None else None
    return str(envelope.get("contract_version") or "") if isinstance(envelope, dict) else ""


def _core_route_message(result: CoreBridgeResult | None, route_group: str) -> str:
    if result is not None and result.ok:
        return f"Aegis Core {route_group} adapter is connected."
    if result is not None and result.error:
        return f"Aegis Core {route_group} adapter is unavailable; Website /api is using local fallback behavior. {result.error}"
    return f"Aegis Core {route_group} adapter is unavailable; Website /api is using local fallback behavior."


def _core_status_from_results(results: dict[str, CoreBridgeResult]) -> tuple[bool, str, str, str]:
    primary = results.get("health") or next(iter(results.values()), None)
    reachable = any(result.reachable for result in results.values())
    connected = bool(primary and primary.ok)
    status = "connected" if connected else "degraded" if reachable else "unavailable"
    contract_version = next((_core_contract_version(result) for result in results.values() if _core_contract_version(result)), "")
    message = _core_route_message(primary, "runtime")
    return reachable, status, contract_version, message


class RuntimeHealthService:
    def __init__(
        self,
        *,
        app_title: str,
        app_version: str,
        project_root_factory: Callable[[], Path],
        settings_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        core_bridge_factory: Callable[[], Any],
        model_registry_factory: Callable[[], Any],
        workspace_resolver: Callable[[str | None], Path],
        database_path_resolver: Callable[[str], Path],
        has_env_file: Callable[[], bool],
    ) -> None:
        self.app_title = app_title
        self.app_version = app_version
        self._project_root_factory = project_root_factory
        self._settings_factory = settings_factory
        self._agent_factory = agent_factory
        self._core_bridge_factory = core_bridge_factory
        self._model_registry_factory = model_registry_factory
        self._workspace_resolver = workspace_resolver
        self._database_path_resolver = database_path_resolver
        self._has_env_file = has_env_file

    async def snapshot(self) -> RuntimeHealthResponse:
        settings = self._settings_factory()
        model_status = await self._agent_factory().model_status()
        default_workspace = self._workspace_resolver(None)
        core_results = await self._core_bridge_factory().low_risk_runtime_status(default_workspace)
        core_reachable, core_status, core_contract, core_message = _core_status_from_results(core_results)
        core_models = core_results.get("models")
        _, core_selected_model, core_models_reachable = core_models_from_result(core_models)
        registry = self._model_registry_factory().snapshot()
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
        if core_status != "connected":
            recommendations.append("Aegis Core shared runtime is unavailable; Website /api is running in local fallback mode.")
        elif core_selected_model and core_selected_model != settings.aegis_model_name:
            recommendations.append(
                f"Aegis Core selected shared model {core_selected_model}; Website /api remains configured for {settings.aegis_model_name} during adapter migration."
            )

        model_message = model_status.message
        if core_models is not None and core_models.ok and core_models_reachable:
            model_message = f"{model_message} Aegis Core model inventory is connected."
        elif core_models is not None and core_models.error:
            model_message = f"{model_message} Aegis Core model inventory is unavailable; using Website model adapter fallback."

        return RuntimeHealthResponse(
            ok=True,
            ready=True,
            status="ready" if model_status.ready and core_status == "connected" else "degraded",
            app=self.app_title,
            version=self.app_version,
            engine=f"Aegis Core / {settings.aegis_model_name}",
            engine_ready=True,
            engine_message="The Aegis backend process is ready." if core_status == "connected" else core_message,
            model_name=settings.aegis_model_name,
            model_api=settings.aegis_model_api,
            model_endpoint=settings.aegis_model_endpoint,
            model_ready=model_status.ready,
            model_message=model_message,
            project_root=str(self._project_root_factory()),
            workspace_root=str(default_workspace),
            database_path=str(self._database_path_resolver(settings.aegis_database_path)),
            env_exists=self._has_env_file(),
            router_execution_enabled=settings.aegis_router_execution_enabled,
            router_enabled=registry.router_enabled,
            fallback_supported=registry.fallback_supported,
            provider_count=provider_count,
            configured_provider_count=configured_provider_count,
            enabled_provider_count=enabled_provider_count,
            role_count=len(registry.roles),
            recommendations=recommendations,
            core_runtime_reachable=core_reachable,
            core_runtime_status=core_status,
            core_contract_version=core_contract,
            core_runtime_message=core_message,
        )
