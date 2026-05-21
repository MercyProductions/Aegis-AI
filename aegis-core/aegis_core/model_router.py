from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AegisConfig, PROVIDER_ALIASES, load_config, workspace_root
from .credentials import CredentialStore, CredentialStoreError
from .diagnostics import redact_inline, scrub
from .ollama import OllamaClient
from .safety import is_safe_to_read
from .security import load_security_settings, redact_prompt_for_cloud, security_audit


CLOUD_PROVIDER_IDS = {"openai", "anthropic", "google", "openrouter", "azure_openai", "bedrock", "vertex_ai"}
LOCAL_PROVIDER_IDS = {"ollama", "lm_studio"}
SUPPORTED_PROVIDER_IDS = CLOUD_PROVIDER_IDS | LOCAL_PROVIDER_IDS
MODEL_ROUTING_MODES = {"local_only", "hybrid", "cloud_allowed"}
SECRET_CONTEXT_WARNING = "Secret-like, ignored, or outside-workspace files were excluded from provider context."

WORKFLOW_TYPES = (
    "chat_request",
    "generate_feature",
    "validate_project",
    "repair_project",
    "continue_roadmap",
    "build_project",
    "scan_workspace",
    "benchmark_models",
    "generate_media",
    "research_task",
)

ROUTING_PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "local_only": {
        "id": "local_only",
        "label": "Local Only",
        "description": "Prefer installed local models and never route workspace context to cloud providers.",
        "privacy_mode": "local-only",
        "cloud_allowed": False,
        "priority": ["ollama", "lm_studio"],
    },
    "balanced": {
        "id": "balanced",
        "label": "Balanced",
        "description": "Use local models first and allow approved cloud fallback for harder work.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["ollama", "lm_studio", "openai", "anthropic", "openrouter", "google"],
    },
    "fastest": {
        "id": "fastest",
        "label": "Fastest",
        "description": "Favor low-latency local or lightweight hosted models when allowed.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["ollama", "lm_studio", "openai", "google", "openrouter"],
    },
    "cheapest": {
        "id": "cheapest",
        "label": "Cheapest",
        "description": "Prefer zero-cost local routes and low-cost cloud fallback only after approval.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["ollama", "lm_studio", "openrouter", "google", "openai"],
    },
    "best_coding": {
        "id": "best_coding",
        "label": "Best Coding",
        "description": "Prefer strong coding models for implementation, repair, and review workflows.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["ollama", "lm_studio", "openai", "anthropic", "openrouter", "google"],
    },
    "best_reasoning": {
        "id": "best_reasoning",
        "label": "Best Reasoning",
        "description": "Prefer reasoning-capable models for hard debugging, architecture, and planning.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["openai", "anthropic", "openrouter", "google", "ollama", "lm_studio"],
    },
    "private_sensitive": {
        "id": "private_sensitive",
        "label": "Private Sensitive",
        "description": "Keep sensitive work local and warn when requested capabilities are missing locally.",
        "privacy_mode": "private-sensitive",
        "cloud_allowed": False,
        "priority": ["ollama", "lm_studio"],
    },
    "creative_media": {
        "id": "creative_media",
        "label": "Creative Media",
        "description": "Prefer vision or media-capable routes for multimodal generation and review.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["openai", "google", "openrouter", "anthropic", "ollama"],
    },
    "fallback_safe": {
        "id": "fallback_safe",
        "label": "Fallback Safe",
        "description": "Use local first, then conservative approved fallback when local execution fails.",
        "privacy_mode": "local-first",
        "cloud_allowed": True,
        "priority": ["ollama", "lm_studio", "openai", "openrouter", "anthropic", "google"],
    },
}

PROVIDER_METADATA: dict[str, dict[str, Any]] = {
    "ollama": {
        "auth_methods": ["none"],
        "required_auth_method": "none",
        "capabilities": ["chat", "code", "reasoning", "embeddings", "streaming"],
        "roles": ["chat", "code", "reasoning", "embeddings", "judge"],
        "privacy_level": "local",
        "latency_estimate": "local-runtime-dependent",
        "cost_estimate": "no provider cost",
        "context_window": 32768,
        "code_strength": "high",
        "reasoning_strength": "medium",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "lm_studio": {
        "auth_methods": ["none"],
        "required_auth_method": "none",
        "capabilities": ["chat", "code", "reasoning", "streaming", "openai_compatible"],
        "roles": ["chat", "code", "reasoning", "judge"],
        "privacy_level": "local",
        "latency_estimate": "local-runtime-dependent",
        "cost_estimate": "no provider cost",
        "context_window": 32768,
        "code_strength": "medium",
        "reasoning_strength": "medium",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "openai": {
        "auth_methods": ["api_key"],
        "required_auth_method": "api_key",
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming", "structured_json", "media"],
        "roles": ["chat", "code", "reasoning", "vision", "creative", "judge"],
        "privacy_level": "cloud",
        "latency_estimate": "medium",
        "cost_estimate": "paid usage",
        "context_window": 128000,
        "code_strength": "high",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "anthropic": {
        "auth_methods": ["api_key", "bedrock", "vertex_ai"],
        "required_auth_method": "api_key",
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming"],
        "roles": ["chat", "code", "reasoning", "review", "judge"],
        "privacy_level": "cloud",
        "latency_estimate": "medium",
        "cost_estimate": "paid usage",
        "context_window": 200000,
        "code_strength": "high",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "google": {
        "auth_methods": ["api_key", "oauth_browser", "env_profile"],
        "required_auth_method": "api_key",
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming", "structured_json", "long_context"],
        "roles": ["chat", "code", "reasoning", "research", "vision", "creative"],
        "privacy_level": "cloud",
        "latency_estimate": "low-medium",
        "cost_estimate": "paid usage",
        "context_window": 1000000,
        "code_strength": "medium",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "openrouter": {
        "auth_methods": ["api_key"],
        "required_auth_method": "api_key",
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming", "model_routing"],
        "roles": ["chat", "code", "reasoning", "research", "vision", "creative", "fallback"],
        "privacy_level": "cloud-router",
        "latency_estimate": "variable",
        "cost_estimate": "paid usage by upstream model",
        "context_window": 128000,
        "code_strength": "high",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "azure_openai": {
        "auth_methods": ["api_key", "env_profile", "managed_identity"],
        "required_auth_method": "api_key_or_env_profile",
        "credential_env_vars": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"],
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming", "structured_json", "enterprise"],
        "roles": ["chat", "code", "reasoning", "vision", "enterprise"],
        "privacy_level": "enterprise-cloud",
        "latency_estimate": "region-dependent",
        "cost_estimate": "paid Azure usage",
        "context_window": 128000,
        "code_strength": "high",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "bedrock": {
        "auth_methods": ["env_profile", "iam"],
        "required_auth_method": "env_profile",
        "credential_env_vars": ["AWS_PROFILE", "AWS_REGION", "AWS_ACCESS_KEY_ID"],
        "capabilities": ["chat", "code", "reasoning", "streaming", "enterprise"],
        "roles": ["chat", "code", "reasoning", "enterprise"],
        "privacy_level": "enterprise-cloud",
        "latency_estimate": "region-dependent",
        "cost_estimate": "paid AWS usage",
        "context_window": 200000,
        "code_strength": "high",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
    "vertex_ai": {
        "auth_methods": ["env_profile", "oauth_browser"],
        "required_auth_method": "env_profile",
        "credential_env_vars": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "CLOUD_ML_REGION"],
        "capabilities": ["chat", "code", "reasoning", "tools", "vision", "streaming", "structured_json", "enterprise", "long_context"],
        "roles": ["chat", "code", "reasoning", "vision", "enterprise"],
        "privacy_level": "enterprise-cloud",
        "latency_estimate": "region-dependent",
        "cost_estimate": "paid Google Cloud usage",
        "context_window": 1000000,
        "code_strength": "medium",
        "reasoning_strength": "high",
        "supported_workflow_types": WORKFLOW_TYPES,
    },
}


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    api: str
    local: bool
    endpoint: str
    default_model: str
    configured: bool = False
    enabled: bool = True
    requires_key: bool = False
    key_stored: bool = False
    supports_chat: bool = True
    supports_embeddings: bool = False
    cost_warning: str | None = None
    auth_methods: tuple[str, ...] = ()
    default_auth_method: str = ""
    required_auth_method: str = ""
    credential_env_vars: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    context_window: int | None = None
    tool_support: bool = False
    vision_support: bool = False
    code_strength: str = "medium"
    reasoning_strength: str = "medium"
    latency_estimate: str = "unknown"
    cost_estimate: str = "unknown"
    privacy_level: str = "unknown"
    availability_status: str = "unknown"
    provider_reachable: bool = False
    rate_limit_or_error_state: str = "unknown"
    last_health_check: str | None = None
    last_successful_request: str | None = None
    supported_workflow_types: tuple[str, ...] = ()
    models: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def provider_catalog(
    config: AegisConfig,
    credentials: CredentialStore | None = None,
    credential_errors: list[dict[str, str]] | None = None,
    ollama_status: Any | None = None,
) -> list[ProviderSpec]:
    store = credentials or CredentialStore()
    checked_at = _utc_now() if ollama_status is not None else None
    ollama_models = _catalog_models("ollama", config, ollama_status)
    lm_studio_models = _catalog_models("lm_studio", config, None)
    return [
        ProviderSpec(
            id="ollama",
            label="Ollama",
            api="ollama",
            local=True,
            endpoint=config.ollama_url,
            default_model=config.default_local_model or config.default_model,
            configured=True,
            requires_key=False,
            key_stored=False,
            supports_embeddings=True,
            models=tuple(ollama_models),
            availability_status=_local_availability_status(ollama_status),
            provider_reachable=bool(getattr(ollama_status, "reachable", False)) if ollama_status is not None else True,
            last_health_check=checked_at,
            **_provider_spec_metadata("ollama"),
        ),
        ProviderSpec(
            id="lm_studio",
            label="LM Studio",
            api="openai-compatible",
            local=True,
            endpoint=config.lm_studio_url,
            default_model=config.default_local_model or config.default_model,
            configured=True,
            requires_key=False,
            key_stored=False,
            models=tuple(lm_studio_models),
            availability_status="configured",
            provider_reachable=True,
            last_health_check=checked_at,
            **_provider_spec_metadata("lm_studio"),
        ),
        _cloud_provider("openai", "OpenAI", "openai", "https://api.openai.com/v1", config.preferred_cloud_model, store, credential_errors),
        _cloud_provider("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com/v1", "claude-3-5-sonnet-latest", store, credential_errors),
        _cloud_provider("google", "Google Gemini", "google", "https://generativelanguage.googleapis.com/v1beta", "gemini-1.5-pro", store, credential_errors),
        _cloud_provider("openrouter", "OpenRouter", "openai-compatible", "https://openrouter.ai/api/v1", config.preferred_cloud_model, store, credential_errors),
        _cloud_provider("azure_openai", "Azure OpenAI", "azure-openai", "https://{resource}.openai.azure.com/openai", config.preferred_cloud_model, store, credential_errors),
        _cloud_provider("bedrock", "Amazon Bedrock", "bedrock", "https://bedrock-runtime.{region}.amazonaws.com", "anthropic.claude-3-5-sonnet-20240620-v1:0", store, credential_errors),
        _cloud_provider("vertex_ai", "Vertex AI", "vertex-ai", "https://{region}-aiplatform.googleapis.com/v1", "gemini-1.5-pro", store, credential_errors),
    ]


def provider_inventory(workspace: str | Path | None = None, credentials: CredentialStore | None = None) -> dict[str, Any]:
    config = load_config(workspace)
    store = credentials or CredentialStore()
    security_settings = load_security_settings()
    credential_errors: list[dict[str, str]] = []
    providers = provider_catalog(config, store, credential_errors)
    return {
        "mode": config.model_routing_mode,
        "local_only": config.model_routing_mode == "local_only",
        "privacy_mode": security_settings.privacy_mode,
        "cloud_disabled": security_settings.cloud_disabled,
        "credential_store_available": store.available,
        "credential_store_healthy": not credential_errors,
        "credential_store_errors": credential_errors,
        "providers": [provider.to_dict() for provider in providers],
        "routing_profiles": routing_profiles(),
    }


def routing_profiles() -> list[dict[str, Any]]:
    return [dict(ROUTING_PROFILE_DEFINITIONS[key]) for key in ROUTING_PROFILE_DEFINITIONS]


def model_registry(
    workspace: str | Path | None = None,
    credentials: CredentialStore | None = None,
    *,
    check_health: bool = True,
) -> dict[str, Any]:
    root = workspace_root(workspace)
    config = load_config(root)
    store = credentials or CredentialStore()
    credential_errors: list[dict[str, str]] = []
    ollama_status = OllamaClient(config).health() if check_health else None
    providers = provider_catalog(config, store, credential_errors, ollama_status=ollama_status)
    provider_status = [_provider_status(provider) for provider in providers]
    models = [model for provider in providers for model in provider.models]
    selected = _selected_registry_model(models, config, ollama_status)
    profile_id = _profile_id_for_mode(config.model_routing_mode)
    fallback = _registry_fallback_chain(models, selected)
    return {
        "workspace": str(root),
        "generated_at": _utc_now(),
        "mode": config.model_routing_mode,
        "active_profile": profile_id,
        "routing_profiles": routing_profiles(),
        "selected_model": selected,
        "fallback_models": fallback,
        "providers": [provider.to_dict() for provider in providers],
        "models": models,
        "provider_status": provider_status,
        "credential_store_available": store.available,
        "credential_store_healthy": not credential_errors,
        "credential_store_errors": credential_errors,
        "ollama": ollama_status.__dict__ if ollama_status is not None else {},
        "client_guidance": {
            "source_of_truth": "aegis-core",
            "clients_should_route_through": "/v1/models/route",
            "clients_should_read_registry_from": "/v1/models/registry",
        },
    }


def route_model(
    workspace: str | Path | None,
    task_type: str = "chat",
    difficulty: str | None = None,
    *,
    allow_cloud: bool = False,
    cloud_approved: bool = False,
    context_files: list[str] | None = None,
    local_failure_reason: str | None = None,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
    route_profile: str | None = None,
    workflow_type: str | None = None,
    required_capabilities: list[str] | None = None,
    privacy_sensitive: bool = False,
    credentials: CredentialStore | None = None,
) -> dict[str, Any]:
    root = workspace_root(workspace)
    config = load_config(root)
    security_settings = load_security_settings()
    ollama_status = OllamaClient(config).health()
    credential_errors: list[dict[str, str]] = []
    providers = {provider.id: provider for provider in provider_catalog(config, credentials, credential_errors, ollama_status=ollama_status)}
    explicit_route_profile = bool((route_profile or "").strip())
    profile = _routing_profile(route_profile, config.model_routing_mode)
    profile_id = str(profile.get("id") or "balanced")
    role = _normalize_task_type(workflow_type or task_type)
    if profile_id == "best_coding" and role == "chat":
        role = "code_completion"
    elif profile_id == "best_reasoning" and role == "chat":
        role = "hard_debugging"
    elif profile_id == "creative_media":
        role = "generate_media"
    difficulty_label = _normalize_difficulty(difficulty, role)
    requested_provider = _normalize_provider_id(preferred_provider)
    local_candidate = _local_candidate(config, providers, role, ollama_status.installed_models, requested_provider, preferred_model)
    context = collect_cloud_context(root, context_files or [], max_chars=config.max_context_chars)
    cloud_candidate = _cloud_candidate(config, providers, role, difficulty_label, requested_provider, preferred_model)
    warnings: list[str] = []
    fallback_order = [local_candidate]

    if context["blocked_files"]:
        warnings.append(SECRET_CONTEXT_WARNING)
    if requested_provider and requested_provider not in SUPPORTED_PROVIDER_IDS:
        warnings.append(f"Requested provider '{scrub(requested_provider)}' is unsupported; using local Ollama.")
    if credential_errors:
        warnings.append("OS credential store could not be inspected for one or more cloud providers.")
    if security_settings.cloud_disabled:
        warnings.append("Cloud providers are disabled by Aegis privacy controls; routing is local-only.")

    profile_forces_local = security_settings.cloud_disabled or privacy_sensitive or profile_id == "private_sensitive" or (
        explicit_route_profile and (profile_id == "local_only" or not bool(profile.get("cloud_allowed", True)))
    )
    should_consider_cloud = cloud_candidate is not None and not profile_forces_local and (
        role in {"hard_debugging", "repo_wide_planning", "generate_media", "research_task"}
        or difficulty_label == "hard"
        or profile_id in {"best_reasoning", "creative_media"}
    )
    if cloud_candidate is not None and should_consider_cloud:
        fallback_order.append(cloud_candidate)

    selected = local_candidate
    approval_required = False
    cloud_ready = False
    cloud_reason = ""
    mode = config.model_routing_mode if config.model_routing_mode in MODEL_ROUTING_MODES else "local_only"
    if profile_forces_local:
        mode = "local_only"

    if cloud_candidate is not None and should_consider_cloud:
        if mode == "local_only":
            warnings.append("Cloud fallback is blocked because model_routing_mode is local_only.")
            cloud_reason = "local_only"
        elif not allow_cloud:
            approval_required = True
            warnings.append("Cloud fallback is available only after the client shows context and requests approval.")
            cloud_reason = "client_approval_required"
        elif not cloud_approved:
            approval_required = True
            warnings.append("Cloud fallback was requested but not approved for this task.")
            cloud_reason = "cloud_approval_required"
        elif not providers[cloud_candidate["provider_id"]].configured:
            warnings.append(f"{providers[cloud_candidate['provider_id']].label} is not configured with a supported auth method.")
            cloud_reason = "missing_provider_auth"
        else:
            cloud_ready = True

    if cloud_ready and (mode == "cloud_allowed" or local_failure_reason or role in {"hard_debugging", "repo_wide_planning"}):
        selected = {**cloud_candidate, "status": "selected"}
        warnings.append("Cloud model selected after explicit approval; only sanitized context should be sent.")
    elif cloud_candidate is not None and should_consider_cloud and approval_required:
        cloud_candidate["status"] = "approval_required"

    if local_failure_reason:
        warnings.append(f"Local model fallback reason: {scrub(local_failure_reason)}")
    if config.cloud_cost_warnings and selected.get("provider_id") in CLOUD_PROVIDER_IDS:
        warnings.append("Cost warning: this provider may bill per token or request.")

    missing_capabilities = _missing_capabilities(selected, providers, required_capabilities or [], role)
    warnings.extend(missing_capabilities)
    explanation = _route_explanation(
        selected,
        fallback_order,
        providers,
        profile,
        role,
        difficulty_label,
        privacy_sensitive,
        missing_capabilities,
        cloud_reason,
    )

    return {
        "workspace": str(root),
        "task_type": role,
        "workflow_type": workflow_type or role,
        "difficulty": difficulty_label,
        "mode": mode,
        "local_only": mode == "local_only",
        "route_profile": profile,
        "route_profile_id": profile_id,
        "selected": selected,
        "fallback_order": fallback_order,
        "fallback_chain": explanation["fallback_chain"],
        "approval_required": approval_required,
        "cloud_ready": cloud_ready,
        "cloud_reason": cloud_reason,
        "required_capabilities": required_capabilities or [],
        "missing_capability_warnings": missing_capabilities,
        "explanation": explanation,
        "warnings": warnings,
        "context": context,
        "credential_store_healthy": not credential_errors,
        "credential_store_errors": credential_errors,
        "ollama": ollama_status.__dict__,
        "providers": [provider.to_dict() for provider in providers.values()],
    }


def complete_with_route(
    workspace: str | Path | None,
    prompt: str,
    task_type: str = "chat",
    difficulty: str | None = None,
    *,
    allow_cloud: bool = False,
    cloud_approved: bool = False,
    context_files: list[str] | None = None,
    local_failure_reason: str | None = None,
    provider_id: str | None = None,
    model: str | None = None,
    route_profile: str | None = None,
    workflow_type: str | None = None,
    required_capabilities: list[str] | None = None,
    privacy_sensitive: bool = False,
    credentials: CredentialStore | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    root = workspace_root(workspace)
    route = route_model(
        root,
        task_type,
        difficulty,
        allow_cloud=allow_cloud,
        cloud_approved=cloud_approved,
        context_files=context_files,
        local_failure_reason=local_failure_reason,
        preferred_provider=provider_id,
        preferred_model=model,
        route_profile=route_profile,
        workflow_type=workflow_type,
        required_capabilities=required_capabilities,
        privacy_sensitive=privacy_sensitive,
        credentials=credentials,
    )
    selected = route["selected"]
    provider = selected["provider_id"]
    selected_model = selected["model"]
    started = time.perf_counter()

    if provider in CLOUD_PROVIDER_IDS:
        if route["approval_required"] or not route["cloud_ready"]:
            security_audit(root, "provider.call", "blocked", "Cloud provider call missing approval or ready state.", {"provider_id": provider, "model": selected_model})
            raise PermissionError("Cloud provider calls require explicit approval, visible sanitized context, and a stored provider key.")
        if route["context"]["blocked_files"]:
            route["warnings"].append(SECRET_CONTEXT_WARNING)
        prompt = redact_prompt_for_cloud(prompt)
    messages = _messages(prompt, route["context"]["included"])
    security_audit(
        root,
        "provider.call",
        "allowed",
        "Model completion routed through Core.",
        {"provider_id": provider, "model": selected_model, "local": provider in LOCAL_PROVIDER_IDS, "context_files": route["context"]["included_files"]},
    )
    response_text = _complete(provider, selected_model, messages, load_config(root), credentials or CredentialStore(), timeout)
    return {
        "workspace": str(root),
        "provider_id": provider,
        "model": selected_model,
        "local": provider in LOCAL_PROVIDER_IDS,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "response": response_text,
        "route": route,
    }


def collect_cloud_context(root: Path, context_files: list[str], max_chars: int) -> dict[str, Any]:
    included: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    remaining = max(0, max_chars)
    for item in context_files[:50]:
        relative = str(item).strip().replace("\\", "/")
        if not relative:
            continue
        candidate = (root / relative).resolve()
        reason = ""
        if not is_safe_to_read(candidate, root):
            reason = "secret-like, ignored, or outside workspace"
        elif not candidate.is_file():
            reason = "not a readable file"
        if reason:
            blocked.append({"path": relative, "reason": reason})
            continue
        if remaining <= 0:
            blocked.append({"path": relative, "reason": "context budget exhausted"})
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            blocked.append({"path": relative, "reason": "read failed"})
            continue
        cleaned = scrub(text)
        clipped = cleaned[:remaining]
        remaining -= len(clipped)
        included.append({"path": relative, "content": clipped})
    return {
        "max_context_chars": max_chars,
        "included_files": [item["path"] for item in included],
        "blocked_files": blocked,
        "included": included,
    }


def store_provider_key(provider_id: str, api_key: str, credentials: CredentialStore | None = None) -> dict[str, Any]:
    provider = _validate_cloud_provider_id(provider_id)
    store = credentials or CredentialStore()
    store.write_provider_key(provider, api_key)
    return {"provider_id": provider, "key_stored": True, "credential_store": "os"}


def delete_provider_key(provider_id: str, credentials: CredentialStore | None = None) -> dict[str, Any]:
    provider = _validate_provider_id(provider_id)
    store = credentials or CredentialStore()
    removed = store.delete_provider_key(provider)
    return {"provider_id": provider, "removed": removed, "credential_store": "os"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _provider_spec_metadata(provider_id: str) -> dict[str, Any]:
    metadata = PROVIDER_METADATA.get(provider_id, {})
    capabilities = tuple(metadata.get("capabilities", ()))
    return {
        "auth_methods": tuple(metadata.get("auth_methods", ())),
        "default_auth_method": str(metadata.get("default_auth_method") or (metadata.get("auth_methods", [""])[0] if metadata.get("auth_methods") else "")),
        "required_auth_method": str(metadata.get("required_auth_method") or ""),
        "credential_env_vars": tuple(metadata.get("credential_env_vars", ())),
        "capabilities": capabilities,
        "roles": tuple(metadata.get("roles", ())),
        "context_window": metadata.get("context_window"),
        "tool_support": "tools" in capabilities,
        "vision_support": "vision" in capabilities,
        "code_strength": str(metadata.get("code_strength") or "medium"),
        "reasoning_strength": str(metadata.get("reasoning_strength") or "medium"),
        "latency_estimate": str(metadata.get("latency_estimate") or "unknown"),
        "cost_estimate": str(metadata.get("cost_estimate") or "unknown"),
        "privacy_level": str(metadata.get("privacy_level") or "unknown"),
        "supported_workflow_types": tuple(metadata.get("supported_workflow_types", ())),
    }


def _env_auth_available(provider_id: str) -> bool:
    env_vars = PROVIDER_METADATA.get(provider_id, {}).get("credential_env_vars", ())
    return any(os.environ.get(name) for name in env_vars)


def _provider_status(provider: ProviderSpec) -> dict[str, Any]:
    auth_available = (
        not provider.requires_key
        or provider.key_stored
        or _env_auth_available(provider.id)
        or provider.required_auth_method in {"none", ""}
    )
    linked = "linked" if provider.local or auth_available else "unlinked"
    return {
        "provider_id": provider.id,
        "linked": linked,
        "key_present": bool(provider.key_stored),
        "auth_method_available": bool(auth_available),
        "auth_methods": list(provider.auth_methods),
        "required_auth_method": provider.required_auth_method,
        "provider_reachable": bool(provider.provider_reachable),
        "availability_status": provider.availability_status,
        "rate_limit_or_error_state": provider.rate_limit_or_error_state,
        "last_health_check": provider.last_health_check,
        "last_successful_request": provider.last_successful_request,
        "privacy_level": provider.privacy_level,
    }


def _local_availability_status(ollama_status: Any | None) -> str:
    if ollama_status is None:
        return "configured"
    return "available" if bool(getattr(ollama_status, "reachable", False)) else "unreachable"


def _profile_id_for_mode(mode: str) -> str:
    return "local_only" if mode == "local_only" else "balanced"


def _routing_profile(profile_id: str | None, mode: str) -> dict[str, Any]:
    key = (profile_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        key = _profile_id_for_mode(mode)
    return dict(ROUTING_PROFILE_DEFINITIONS.get(key) or ROUTING_PROFILE_DEFINITIONS["balanced"])


def _catalog_models(provider_id: str, config: AegisConfig, ollama_status: Any | None) -> list[dict[str, Any]]:
    metadata = _provider_spec_metadata(provider_id)
    base = {
        "provider_id": provider_id,
        "type": "local" if provider_id in LOCAL_PROVIDER_IDS else "cloud",
        "context_window": metadata.get("context_window"),
        "tool_support": metadata.get("tool_support", False),
        "vision_support": metadata.get("vision_support", False),
        "code_strength": metadata.get("code_strength", "medium"),
        "reasoning_strength": metadata.get("reasoning_strength", "medium"),
        "latency_estimate": metadata.get("latency_estimate", "unknown"),
        "cost_estimate": metadata.get("cost_estimate", "unknown"),
        "privacy_level": metadata.get("privacy_level", "unknown"),
        "required_auth_method": metadata.get("required_auth_method", ""),
        "supported_workflow_types": list(metadata.get("supported_workflow_types", ())),
        "capabilities": list(metadata.get("capabilities", ())),
    }
    if provider_id == "ollama":
        installed = list(getattr(ollama_status, "installed_models", []) or [])
        selected = getattr(ollama_status, "selected_model", None)
        reachable = bool(getattr(ollama_status, "reachable", False)) if ollama_status is not None else True
        names = installed or [config.default_local_model or config.default_model, *config.fallback_models]
        return [
            {
                **base,
                "model_id": name,
                "display_name": name,
                "availability_status": "available" if reachable and (name in installed or not installed) else "missing" if reachable else "unreachable",
                "last_health_check": _utc_now() if ollama_status is not None else None,
                "selected": bool(selected and selected == name),
            }
            for name in names
            if name
        ]
    if provider_id == "lm_studio":
        model = config.default_local_model or config.default_model
        return [{**base, "model_id": model, "display_name": model, "availability_status": "configured", "last_health_check": None}]

    catalogs: dict[str, list[tuple[str, str, int | None, bool, bool, str, str, str, str]]] = {
        "openai": [
            ("gpt-4.1", "OpenAI GPT-4.1", 128000, True, True, "high", "high", "medium", "paid usage"),
            ("gpt-4.1-mini", "OpenAI GPT-4.1 Mini", 128000, True, True, "medium", "medium", "low", "lower paid usage"),
        ],
        "anthropic": [
            ("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet", 200000, True, True, "high", "high", "medium", "paid usage"),
        ],
        "google": [
            ("gemini-1.5-pro", "Gemini 1.5 Pro", 1000000, True, True, "medium", "high", "medium", "paid usage"),
            ("gemini-1.5-flash", "Gemini 1.5 Flash", 1000000, True, True, "medium", "medium", "low", "lower paid usage"),
        ],
        "openrouter": [
            (config.preferred_cloud_model or "openrouter/auto", "OpenRouter Preferred Route", 128000, True, True, "high", "high", "variable", "paid upstream usage"),
            ("openrouter/auto", "OpenRouter Auto", 128000, True, True, "medium", "medium", "variable", "paid upstream usage"),
        ],
        "azure_openai": [
            (config.preferred_cloud_model or "azure-openai-deployment", "Azure OpenAI Deployment", 128000, True, True, "high", "high", "region-dependent", "paid Azure usage"),
        ],
        "bedrock": [
            ("anthropic.claude-3-5-sonnet-20240620-v1:0", "Bedrock Claude Sonnet", 200000, False, False, "high", "high", "region-dependent", "paid AWS usage"),
        ],
        "vertex_ai": [
            ("gemini-1.5-pro", "Vertex Gemini 1.5 Pro", 1000000, True, True, "medium", "high", "region-dependent", "paid Google Cloud usage"),
        ],
    }
    status = "available" if provider_id in {"openai", "anthropic", "google", "openrouter"} else "requires_env_profile"
    return [
        {
            **base,
            "model_id": model_id,
            "display_name": display_name,
            "context_window": context_window or base["context_window"],
            "tool_support": tool_support,
            "vision_support": vision_support,
            "code_strength": code_strength,
            "reasoning_strength": reasoning_strength,
            "latency_estimate": latency,
            "cost_estimate": cost,
            "availability_status": status,
            "last_health_check": None,
            "selected": False,
        }
        for model_id, display_name, context_window, tool_support, vision_support, code_strength, reasoning_strength, latency, cost in catalogs.get(provider_id, [])
    ]


def _selected_registry_model(models: list[dict[str, Any]], config: AegisConfig, ollama_status: Any | None) -> dict[str, Any] | None:
    selected = getattr(ollama_status, "selected_model", None)
    if selected:
        return next((model for model in models if model.get("provider_id") == "ollama" and model.get("model_id") == selected), None)
    preferred = config.default_local_model or config.default_model
    return next((model for model in models if model.get("provider_id") == "ollama" and model.get("model_id") == preferred), None)


def _registry_fallback_chain(models: list[dict[str, Any]], selected: dict[str, Any] | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    if selected:
        chain.append(selected)
    for model in models:
        if len(chain) >= 5:
            break
        if selected and model.get("provider_id") == selected.get("provider_id") and model.get("model_id") == selected.get("model_id"):
            continue
        if model.get("availability_status") in {"available", "configured"}:
            chain.append(model)
    return chain


def _missing_capabilities(
    selected: dict[str, Any],
    providers: dict[str, ProviderSpec],
    required: list[str],
    role: str,
) -> list[str]:
    required_set = {
        str(item).strip().lower().replace("-", "_").replace(" ", "_")
        for item in required
        if str(item).strip()
    }
    if role == "generate_media":
        required_set.add("vision")
    if not required_set:
        return []
    provider = providers.get(selected.get("provider_id", ""))
    capabilities = set(provider.capabilities if provider else ())
    missing = sorted(required_set - capabilities)
    return [f"Selected route is missing capability '{item}'." for item in missing]


def _route_explanation(
    selected: dict[str, Any],
    fallback_order: list[dict[str, Any]],
    providers: dict[str, ProviderSpec],
    profile: dict[str, Any],
    role: str,
    difficulty: str,
    privacy_sensitive: bool,
    missing_capability_warnings: list[str],
    cloud_reason: str,
) -> dict[str, Any]:
    provider = providers.get(selected.get("provider_id", ""))
    provider_status = _provider_status(provider) if provider is not None else {}
    fallback_chain = [
        {
            "provider_id": candidate.get("provider_id", ""),
            "model": candidate.get("model", ""),
            "status": candidate.get("status", ""),
            "reason": candidate.get("reason", ""),
        }
        for candidate in fallback_order
    ]
    selected_provider = selected.get("provider_id", "")
    local = bool(selected.get("local", selected_provider in LOCAL_PROVIDER_IDS))
    privacy_risk = "low" if local else "medium" if not privacy_sensitive else "blocked"
    capability_fit = "partial" if missing_capability_warnings else "good"
    reason = selected.get("reason") or f"{selected_provider or 'model'} selected for {role}."
    if cloud_reason:
        reason = f"{reason} Cloud gate: {cloud_reason}."
    return {
        "selected_provider": selected_provider,
        "selected_model": selected.get("model", ""),
        "reason_selected": reason,
        "fallback_chain": fallback_chain,
        "privacy_risk": privacy_risk,
        "expected_capability_fit": capability_fit,
        "missing_capability_warnings": missing_capability_warnings,
        "route_profile": profile,
        "workflow_fit": role,
        "difficulty": difficulty,
        "provider_health": provider_status,
        "selected_capabilities": list(provider.capabilities) if provider is not None else [],
    }


def _validate_provider_id(provider_id: str) -> str:
    provider = _normalize_provider_id(provider_id)
    if provider not in SUPPORTED_PROVIDER_IDS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDER_IDS))
        raise ValueError(f"Unsupported provider '{provider or ''}'. Supported providers: {supported}.")
    return provider


def _validate_cloud_provider_id(provider_id: str) -> str:
    provider = _validate_provider_id(provider_id)
    if provider in LOCAL_PROVIDER_IDS:
        supported = ", ".join(sorted(CLOUD_PROVIDER_IDS))
        raise ValueError(f"Provider '{provider}' does not use stored API keys. Key storage is supported for: {supported}.")
    return provider


def _cloud_provider(
    provider_id: str,
    label: str,
    api: str,
    endpoint: str,
    default_model: str,
    store: CredentialStore,
    credential_errors: list[dict[str, str]] | None = None,
) -> ProviderSpec:
    key_stored = False
    try:
        key_stored = store.has_provider_key(provider_id)
    except Exception as exc:
        if credential_errors is not None:
            credential_errors.append({"provider_id": provider_id, "error": scrub(str(exc))})
        key_stored = False
    env_available = _env_auth_available(provider_id)
    configured = key_stored or env_available
    availability = "available" if configured else "auth_missing"
    metadata = _provider_spec_metadata(provider_id)
    models = _catalog_models(provider_id, AegisConfig(preferred_cloud_model=default_model), None)
    for model in models:
        model["availability_status"] = availability
    return ProviderSpec(
        id=provider_id,
        label=label,
        api=api,
        local=False,
        endpoint=endpoint,
        default_model=default_model,
        configured=configured,
        requires_key=True,
        key_stored=key_stored,
        cost_warning=f"{label} may bill per token or request.",
        models=tuple(models),
        availability_status=availability,
        provider_reachable=configured,
        rate_limit_or_error_state="unknown" if configured else "auth_missing",
        **metadata,
    )


def _candidate(provider: ProviderSpec, model: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "provider_id": provider.id,
        "provider_label": provider.label,
        "api": provider.api,
        "local": provider.local,
        "model": model,
        "model_id": model,
        "status": status,
        "reason": reason,
        "cost_warning": provider.cost_warning,
        "privacy_level": provider.privacy_level,
        "availability_status": provider.availability_status,
        "capabilities": list(provider.capabilities),
        "code_strength": provider.code_strength,
        "reasoning_strength": provider.reasoning_strength,
        "tool_support": provider.tool_support,
        "vision_support": provider.vision_support,
    }


def _cloud_candidate(
    config: AegisConfig,
    providers: dict[str, ProviderSpec],
    role: str,
    difficulty: str,
    preferred_provider: str | None,
    preferred_model: str | None,
) -> dict[str, Any] | None:
    if preferred_provider in LOCAL_PROVIDER_IDS or (preferred_provider is not None and preferred_provider not in CLOUD_PROVIDER_IDS):
        return None
    provider_id = (preferred_provider or config.preferred_cloud_provider or "openai").strip().lower()
    if provider_id not in CLOUD_PROVIDER_IDS:
        provider_id = "openai"
    provider = providers.get(provider_id)
    if provider is None:
        return None
    model = preferred_model or config.preferred_cloud_model or provider.default_model
    reason = f"Optional cloud fallback for {role} ({difficulty}) after approval."
    return _candidate(provider, model, "available", reason)


def _local_candidate(
    config: AegisConfig,
    providers: dict[str, ProviderSpec],
    role: str,
    installed: list[str],
    preferred_provider: str | None,
    preferred_model: str | None,
) -> dict[str, Any]:
    provider_id = preferred_provider if preferred_provider in LOCAL_PROVIDER_IDS else "ollama"
    provider = providers.get(provider_id) or providers["ollama"]
    if provider_id == "lm_studio":
        model = preferred_model or config.default_local_model or config.default_model
        return _candidate(provider, model, "selected", f"Preferred local LM Studio route for {role}.")
    model = _local_model_for_role(config, role, installed)
    return _candidate(provider, model, "selected", f"Local-first route for {role}.")


def _normalize_provider_id(provider_id: str | None) -> str | None:
    text = (provider_id or "").strip().lower()
    if not text:
        return None
    canonical = text.replace("-", "_").replace(" ", "_")
    aliases = {
        "lmstudio": "lm_studio",
        "lm_studio": "lm_studio",
        "google_gemini": "google",
        "gemini": "google",
        "google_ai": "google",
        "open_router": "openrouter",
        "azure": "azure_openai",
        "amazon_bedrock": "bedrock",
        "aws_bedrock": "bedrock",
        "vertex": "vertex_ai",
        **PROVIDER_ALIASES,
    }
    return aliases.get(canonical, text)


def _local_model_for_role(config: AegisConfig, role: str, installed: list[str]) -> str:
    if role == "simple_explanation":
        preferred = config.local_small_model
    elif role == "code_completion":
        preferred = config.local_coder_model
    elif role == "embeddings_search":
        preferred = config.local_embedding_model
    else:
        preferred = config.default_local_model or config.default_model
    candidates = [preferred, config.default_model, *config.fallback_models]
    installed_set = set(installed)
    return next((model for model in candidates if model in installed_set), preferred)


def _normalize_task_type(task_type: str) -> str:
    text = (task_type or "chat").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"simple", "explain", "explanation", "simple_explanation"}:
        return "simple_explanation"
    if text in {"complete", "completion", "code", "code_completion"}:
        return "code_completion"
    if text in {"roadmap", "plan", "planning", "repo_planning", "repo_wide_planning"}:
        return "repo_wide_planning"
    if text in {"debug", "debugging", "hard_debugging", "repair", "repair_project", "build_project"}:
        return "hard_debugging"
    if text in {"embedding", "embeddings", "search", "embeddings_search"}:
        return "embeddings_search"
    if text in {"review", "code_review"}:
        return "code_review"
    if text in {"fix", "small_fix", "smaller_fix"}:
        return "smaller_fix"
    if text in {"feature", "generate_feature"}:
        return "code_completion"
    if text in {"continue_roadmap"}:
        return "repo_wide_planning"
    if text in {"research", "research_task"}:
        return "research_task"
    if text in {"media", "creative", "generate_media", "vision"}:
        return "generate_media"
    if text in {"validate", "validate_project"}:
        return "code_review"
    if text in {"scan_workspace", "benchmark_models"}:
        return text
    return "chat"


def _normalize_difficulty(difficulty: str | None, role: str) -> str:
    text = (difficulty or "").strip().lower()
    if text in {"easy", "simple", "medium", "hard"}:
        return "simple" if text == "easy" else text
    if role in {"hard_debugging", "repo_wide_planning", "research_task"}:
        return "hard"
    if role in {"code_completion", "code_review", "smaller_fix", "generate_media"}:
        return "medium"
    return "simple"


def _messages(prompt: str, context: list[dict[str, str]]) -> list[dict[str, str]]:
    context_text = "\n\n".join(f"File: {item['path']}\n{item['content']}" for item in context)
    user = prompt if not context_text else f"{prompt}\n\nSanitized context:\n{context_text}"
    return [
        {"role": "system", "content": "You are Aegis Core, a local-first coding assistant. Do not request secrets."},
        {"role": "user", "content": user},
    ]


def _complete(
    provider_id: str,
    model: str,
    messages: list[dict[str, str]],
    config: AegisConfig,
    credentials: CredentialStore,
    timeout: int,
) -> str:
    if provider_id == "ollama":
        prompt = "\n\n".join(f"{item['role']}: {item['content']}" for item in messages)
        return OllamaClient(config).chat(prompt, model=model, timeout=timeout)
    if provider_id == "lm_studio":
        return _openai_compatible_chat(_lm_studio_openai_base(config.lm_studio_url), model, messages, None, timeout)
    api_key = credentials.read_provider_key(provider_id)
    if not api_key:
        raise PermissionError(f"{provider_id} API key is not stored in OS credential storage.")
    if provider_id == "openai":
        return _openai_compatible_chat("https://api.openai.com/v1", model, messages, api_key, timeout)
    if provider_id == "openrouter":
        return _openai_compatible_chat("https://openrouter.ai/api/v1", model, messages, api_key, timeout)
    if provider_id == "anthropic":
        return _anthropic_chat(model, messages, api_key, timeout)
    if provider_id in {"google", "google_gemini"}:
        return _google_chat(model, messages, api_key, timeout)
    raise ValueError(f"Unsupported provider {provider_id}.")


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> Any:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Provider HTTP {exc.code}: {redact_inline(body)[:240]}") from exc
    except urllib.error.URLError as exc:
        reason = redact_inline(str(exc.reason if hasattr(exc, "reason") else exc))
        raise RuntimeError(f"Provider connection failed: {reason}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Provider returned invalid JSON.") from exc
    except TimeoutError as exc:
        raise RuntimeError("Provider request timed out.") from exc


def _openai_compatible_chat(base_url: str, model: str, messages: list[dict[str, str]], api_key: str | None, timeout: int) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = _request_json(
        f"{base_url.rstrip('/')}/chat/completions",
        {"model": model, "messages": messages, "stream": False},
        headers,
        timeout,
    )
    data = _provider_object(data, "OpenAI-compatible chat")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI-compatible chat response did not include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("OpenAI-compatible chat response choice was not a JSON object.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenAI-compatible chat response did not include a message object.")
    return _provider_text(message.get("content"), "OpenAI-compatible chat")


def _lm_studio_openai_base(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    return cleaned if cleaned.endswith("/v1") else f"{cleaned}/v1"


def _anthropic_chat(model: str, messages: list[dict[str, str]], api_key: str, timeout: int) -> str:
    user_content = "\n\n".join(item["content"] for item in messages if item["role"] != "system")
    system = "\n\n".join(item["content"] for item in messages if item["role"] == "system")
    data = _request_json(
        "https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": 2048, "system": system, "messages": [{"role": "user", "content": user_content}]},
        {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout,
    )
    data = _provider_object(data, "Anthropic chat")
    parts = data.get("content")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Anthropic chat response did not include content parts.")
    return _provider_text_parts(parts, "Anthropic chat")


def _google_chat(model: str, messages: list[dict[str, str]], api_key: str, timeout: int) -> str:
    text = "\n\n".join(f"{item['role']}: {item['content']}" for item in messages)
    data = _request_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        {"contents": [{"parts": [{"text": text}]}]},
        {"Content-Type": "application/json"},
        timeout,
    )
    data = _provider_object(data, "Google chat")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Google chat response did not include candidates.")
    first = candidates[0]
    if not isinstance(first, dict):
        raise RuntimeError("Google chat response candidate was not a JSON object.")
    content = first.get("content")
    if not isinstance(content, dict):
        raise RuntimeError("Google chat response did not include a content object.")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Google chat response did not include content parts.")
    return _provider_text_parts(parts, "Google chat")


def _provider_object(data: Any, label: str) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    raise RuntimeError(f"{label} response was not a JSON object.")


def _provider_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} response did not include completion text.")
    return value.strip()


def _provider_text_parts(parts: list[Any], label: str) -> str:
    text_parts = [item.get("text", "") for item in parts if isinstance(item, dict)]
    text = "\n".join(part.strip() for part in text_parts if isinstance(part, str) and part.strip())
    if not text:
        raise RuntimeError(f"{label} response did not include completion text.")
    return text
