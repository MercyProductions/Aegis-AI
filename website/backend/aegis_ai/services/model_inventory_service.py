from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..core_bridge import CoreBridgeResult
from ..schemas import (
    ModelCapabilities,
    ModelInfo,
    ModelInventoryResponse,
    ModelRegistryProvider,
    ModelRegistryResponse,
    ModelRoutingPreset,
)
from .runtime_health_service import core_models_from_result


class ModelInventoryService:
    def __init__(
        self,
        *,
        settings_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        model_registry_factory: Callable[[], Any],
        core_bridge_factory: Callable[[], Any],
        workspace_resolver: Callable[[str | None], Path],
        core_route_status: Callable[[CoreBridgeResult | None], str],
        core_contract_version: Callable[[CoreBridgeResult | None], str],
        core_route_message: Callable[[CoreBridgeResult | None, str], str],
    ) -> None:
        self._settings_factory = settings_factory
        self._agent_factory = agent_factory
        self._model_registry_factory = model_registry_factory
        self._core_bridge_factory = core_bridge_factory
        self._workspace_resolver = workspace_resolver
        self._core_route_status = core_route_status
        self._core_contract_version = core_contract_version
        self._core_route_message = core_route_message

    async def models(self) -> ModelInventoryResponse:
        settings = self._settings_factory()
        inventory = await self._agent_factory().model_inventory()
        registry = self._model_registry_factory().snapshot()
        default_workspace = self._workspace_resolver(None)
        core_models = await self._core_bridge_factory().model_status(default_workspace)
        core_installed, core_selected, core_reachable = core_models_from_result(core_models)
        seen_model_names: set[str] = set()
        model_records: list[ModelInfo] = []
        for item in inventory.models:
            seen_model_names.add(item.name)
            core_available = item.name in core_installed or item.id in core_installed
            core_ready = core_reachable and bool(core_selected) and item.name == core_selected
            message = item.message
            if core_available and not item.available:
                message = "Available via Aegis Core shared model inventory."
            model_records.append(
                ModelInfo(
                    id=item.id,
                    name=item.name,
                    provider=item.provider,
                    api=item.api,
                    endpoint=item.endpoint,
                    local=item.local,
                    configured=item.configured,
                    available=item.available or core_available,
                    ready=item.ready or core_ready,
                    message=message,
                    size=item.size,
                    modified_at=item.modified_at,
                    capabilities=ModelCapabilities(**(item.capabilities or {})),
                )
            )

        if core_models.ok:
            for model_name in sorted(name for name in core_installed if name not in seen_model_names):
                model_records.append(
                    ModelInfo(
                        id=f"aegis-core:{model_name}",
                        name=model_name,
                        provider="Aegis Core",
                        api="ollama",
                        endpoint=settings.aegis_model_endpoint,
                        local=True,
                        configured=model_name in {settings.aegis_model_name, core_selected},
                        available=True,
                        ready=core_reachable and model_name == core_selected,
                        message="Detected by Aegis Core shared model inventory.",
                        capabilities=core_model_capabilities(model_name),
                    )
                )

        message = inventory.message
        if core_models.ok:
            message = f"{message} Aegis Core model inventory is connected."
        elif core_models.error:
            message = f"{message} Aegis Core model inventory is unavailable; using Website model adapter fallback."

        return ModelInventoryResponse(
            active_model=inventory.active_model,
            active_api=inventory.active_api,
            active_endpoint=inventory.active_endpoint,
            router_enabled=registry.router_enabled,
            fallback_supported=registry.fallback_supported,
            message=message,
            models=model_records,
            core_runtime_reachable=core_models.reachable,
            core_runtime_status=self._core_route_status(core_models),
            core_contract_version=self._core_contract_version(core_models),
            core_runtime_message=self._core_route_message(core_models, "models"),
        )


def merge_core_model_registry(registry: ModelRegistryResponse, core_data: dict[str, Any]) -> ModelRegistryResponse:
    provider_by_id = {provider.id: provider for provider in registry.providers}
    aliases = {"google": "google_gemini", "google_gemini": "google"}
    for core_provider in core_data.get("providers", []) if isinstance(core_data.get("providers"), list) else []:
        if not isinstance(core_provider, dict):
            continue
        provider_id = str(core_provider.get("id") or "").strip()
        if not provider_id:
            continue
        target = provider_by_id.get(provider_id) or provider_by_id.get(aliases.get(provider_id, ""))
        if target is None:
            target = ModelRegistryProvider(
                id=provider_id,
                label=str(core_provider.get("label") or provider_id),
                api=str(core_provider.get("api") or "unknown"),
                endpoint=str(core_provider.get("endpoint") or ""),
                model_name=str(core_provider.get("default_model") or ""),
                local=bool(core_provider.get("local", False)),
                enabled=bool(core_provider.get("enabled", True)),
                configured=bool(core_provider.get("configured", False)),
                capabilities=[str(item) for item in core_provider.get("capabilities", []) if str(item).strip()],
                roles=[str(item) for item in core_provider.get("roles", []) if str(item).strip()],
                context_window=core_provider.get("context_window") if isinstance(core_provider.get("context_window"), int) else None,
                health=str(core_provider.get("availability_status") or "unknown"),
                auth_modes=[str(item) for item in core_provider.get("auth_methods", []) if str(item).strip()],
                connection_status="connected" if bool(core_provider.get("provider_reachable", False)) else "unavailable",
                notes="Sourced from Aegis Core model registry.",
            )
            registry.providers.append(target)
            provider_by_id[target.id] = target
        else:
            target.configured = bool(core_provider.get("configured", target.configured))
            target.enabled = bool(core_provider.get("enabled", target.enabled))
            target.health = str(core_provider.get("availability_status") or target.health)
            target.connection_status = "connected" if bool(core_provider.get("provider_reachable", False)) else target.connection_status
            target.auth_modes = _merge_strings(target.auth_modes, core_provider.get("auth_methods", []))
            target.capabilities = _merge_strings(target.capabilities, core_provider.get("capabilities", []))
            target.roles = _merge_strings(target.roles, core_provider.get("roles", []))
            if isinstance(core_provider.get("context_window"), int):
                target.context_window = core_provider.get("context_window")
            target.notes = _append_note(target.notes, "Core registry synchronized provider status.")

    existing_presets = {preset.id for preset in registry.presets}
    for profile in core_data.get("routing_profiles", []) if isinstance(core_data.get("routing_profiles"), list) else []:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id") or "").strip()
        if not profile_id or profile_id in existing_presets:
            continue
        registry.presets.append(
            ModelRoutingPreset(
                id=profile_id,
                label=str(profile.get("label") or profile_id),
                description=str(profile.get("description") or "Aegis Core routing profile."),
                role_order=[str(item) for item in profile.get("priority", []) if str(item).strip()],
                privacy_mode=str(profile.get("privacy_mode") or "local-first"),
            )
        )
        existing_presets.add(profile_id)

    selected = core_data.get("selected_model") if isinstance(core_data.get("selected_model"), dict) else {}
    if selected:
        registry.active_provider_id = str(selected.get("provider_id") or registry.active_provider_id)
        registry.active_model = str(selected.get("model_id") or selected.get("display_name") or registry.active_model)
    registry.router_enabled = True
    registry.fallback_supported = True
    registry.message = _append_note(registry.message, "Aegis Core model registry connected.")
    return registry


def core_model_capabilities(name: str) -> ModelCapabilities:
    lowered = name.lower()
    return ModelCapabilities(
        code=any(marker in lowered for marker in ("code", "coder", "devstral", "starcoder")),
        debug=any(marker in lowered for marker in ("code", "coder", "devstral", "starcoder")),
        refactor=any(marker in lowered for marker in ("code", "coder", "devstral", "starcoder")),
        reasoning=any(marker in lowered for marker in ("reason", "qwen3", "deepseek-r1")),
        structured_json=any(marker in lowered for marker in ("code", "coder", "qwen", "granite", "llama", "mistral")),
    )


def _merge_strings(existing: list[str], incoming: Any) -> list[str]:
    values = list(existing or [])
    seen = {item.lower() for item in values}
    for item in incoming if isinstance(incoming, list) else []:
        text = str(item).strip()
        if text and text.lower() not in seen:
            values.append(text)
            seen.add(text.lower())
    return values


def _append_note(current: str, note: str) -> str:
    text = (current or "").strip()
    return note if not text else text if note in text else f"{text} {note}"
