from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import AegisConfig, load_config, workspace_root
from .credentials import CredentialStore, CredentialStoreError
from .diagnostics import redact_inline, scrub
from .ollama import OllamaClient
from .safety import is_safe_to_read


CLOUD_PROVIDER_IDS = {"openai", "anthropic", "google", "openrouter"}
LOCAL_PROVIDER_IDS = {"ollama", "lm_studio"}
SUPPORTED_PROVIDER_IDS = CLOUD_PROVIDER_IDS | LOCAL_PROVIDER_IDS
MODEL_ROUTING_MODES = {"local_only", "hybrid", "cloud_allowed"}
SECRET_CONTEXT_WARNING = "Secret-like, ignored, or outside-workspace files were excluded from provider context."


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def provider_catalog(
    config: AegisConfig,
    credentials: CredentialStore | None = None,
    credential_errors: list[dict[str, str]] | None = None,
) -> list[ProviderSpec]:
    store = credentials or CredentialStore()
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
        ),
        _cloud_provider("openai", "OpenAI", "openai", "https://api.openai.com/v1", config.preferred_cloud_model, store, credential_errors),
        _cloud_provider("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com/v1", "claude-3-5-sonnet-latest", store, credential_errors),
        _cloud_provider("google", "Google", "google", "https://generativelanguage.googleapis.com/v1beta", "gemini-1.5-pro", store, credential_errors),
        _cloud_provider("openrouter", "OpenRouter", "openai-compatible", "https://openrouter.ai/api/v1", config.preferred_cloud_model, store, credential_errors),
    ]


def provider_inventory(workspace: str | Path | None = None, credentials: CredentialStore | None = None) -> dict[str, Any]:
    config = load_config(workspace)
    store = credentials or CredentialStore()
    credential_errors: list[dict[str, str]] = []
    providers = provider_catalog(config, store, credential_errors)
    return {
        "mode": config.model_routing_mode,
        "local_only": config.model_routing_mode == "local_only",
        "credential_store_available": store.available,
        "credential_store_healthy": not credential_errors,
        "credential_store_errors": credential_errors,
        "providers": [provider.to_dict() for provider in providers],
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
    credentials: CredentialStore | None = None,
) -> dict[str, Any]:
    root = workspace_root(workspace)
    config = load_config(root)
    ollama_status = OllamaClient(config).health()
    credential_errors: list[dict[str, str]] = []
    providers = {provider.id: provider for provider in provider_catalog(config, credentials, credential_errors)}
    role = _normalize_task_type(task_type)
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

    should_consider_cloud = cloud_candidate is not None and (role in {"hard_debugging", "repo_wide_planning"} or difficulty_label == "hard")
    if cloud_candidate is not None and should_consider_cloud:
        fallback_order.append(cloud_candidate)

    selected = local_candidate
    approval_required = False
    cloud_ready = False
    cloud_reason = ""
    mode = config.model_routing_mode if config.model_routing_mode in MODEL_ROUTING_MODES else "local_only"

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
        elif not providers[cloud_candidate["provider_id"]].key_stored:
            warnings.append(f"{providers[cloud_candidate['provider_id']].label} is not configured in OS credential storage.")
            cloud_reason = "missing_provider_key"
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

    return {
        "workspace": str(root),
        "task_type": role,
        "difficulty": difficulty_label,
        "mode": mode,
        "local_only": mode == "local_only",
        "selected": selected,
        "fallback_order": fallback_order,
        "approval_required": approval_required,
        "cloud_ready": cloud_ready,
        "cloud_reason": cloud_reason,
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
        credentials=credentials,
    )
    selected = route["selected"]
    provider = selected["provider_id"]
    selected_model = model or selected["model"]
    started = time.perf_counter()

    if provider in CLOUD_PROVIDER_IDS:
        if route["approval_required"] or not route["cloud_ready"]:
            raise PermissionError("Cloud provider calls require explicit approval, visible sanitized context, and a stored provider key.")
        if route["context"]["blocked_files"]:
            route["warnings"].append(SECRET_CONTEXT_WARNING)
    messages = _messages(prompt, route["context"]["included"])
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
    _validate_provider_id(provider_id)
    store = credentials or CredentialStore()
    store.write_provider_key(provider_id, api_key)
    return {"provider_id": provider_id.strip().lower(), "key_stored": True, "credential_store": "os"}


def delete_provider_key(provider_id: str, credentials: CredentialStore | None = None) -> dict[str, Any]:
    _validate_provider_id(provider_id)
    store = credentials or CredentialStore()
    removed = store.delete_provider_key(provider_id)
    return {"provider_id": provider_id.strip().lower(), "removed": removed, "credential_store": "os"}


def _validate_provider_id(provider_id: str) -> None:
    provider = provider_id.strip().lower()
    if provider not in SUPPORTED_PROVIDER_IDS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDER_IDS))
        raise ValueError(f"Unsupported provider '{provider}'. Supported providers: {supported}.")


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
    return ProviderSpec(
        id=provider_id,
        label=label,
        api=api,
        local=False,
        endpoint=endpoint,
        default_model=default_model,
        configured=key_stored,
        requires_key=True,
        key_stored=key_stored,
        cost_warning=f"{label} may bill per token or request.",
    )


def _candidate(provider: ProviderSpec, model: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "provider_id": provider.id,
        "provider_label": provider.label,
        "api": provider.api,
        "local": provider.local,
        "model": model,
        "status": status,
        "reason": reason,
        "cost_warning": provider.cost_warning,
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
    model = preferred_model or _local_model_for_role(config, role, installed)
    return _candidate(provider, model, "selected", f"Local-first route for {role}.")


def _normalize_provider_id(provider_id: str | None) -> str | None:
    text = (provider_id or "").strip().lower()
    return text or None


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
    if text in {"debug", "debugging", "hard_debugging", "repair"}:
        return "hard_debugging"
    if text in {"embedding", "embeddings", "search", "embeddings_search"}:
        return "embeddings_search"
    if text in {"review", "code_review"}:
        return "code_review"
    if text in {"fix", "small_fix", "smaller_fix"}:
        return "smaller_fix"
    return "chat"


def _normalize_difficulty(difficulty: str | None, role: str) -> str:
    text = (difficulty or "").strip().lower()
    if text in {"easy", "simple", "medium", "hard"}:
        return "simple" if text == "easy" else text
    if role in {"hard_debugging", "repo_wide_planning"}:
        return "hard"
    if role in {"code_completion", "code_review", "smaller_fix"}:
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
        return _openai_compatible_chat(config.lm_studio_url, model, messages, None, timeout)
    api_key = credentials.read_provider_key(provider_id)
    if not api_key:
        raise PermissionError(f"{provider_id} API key is not stored in OS credential storage.")
    if provider_id == "openai":
        return _openai_compatible_chat("https://api.openai.com/v1", model, messages, api_key, timeout)
    if provider_id == "openrouter":
        return _openai_compatible_chat("https://openrouter.ai/api/v1", model, messages, api_key, timeout)
    if provider_id == "anthropic":
        return _anthropic_chat(model, messages, api_key, timeout)
    if provider_id == "google":
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
    return str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()


def _anthropic_chat(model: str, messages: list[dict[str, str]], api_key: str, timeout: int) -> str:
    user_content = "\n\n".join(item["content"] for item in messages if item["role"] != "system")
    system = "\n\n".join(item["content"] for item in messages if item["role"] == "system")
    data = _request_json(
        "https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": 2048, "system": system, "messages": [{"role": "user", "content": user_content}]},
        {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout,
    )
    parts = data.get("content", [])
    return "\n".join(str(item.get("text", "")) for item in parts if isinstance(item, dict)).strip()


def _google_chat(model: str, messages: list[dict[str, str]], api_key: str, timeout: int) -> str:
    text = "\n\n".join(f"{item['role']}: {item['content']}" for item in messages)
    data = _request_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        {"contents": [{"parts": [{"text": text}]}]},
        {"Content-Type": "application/json"},
        timeout,
    )
    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(str(item.get("text", "")) for item in parts if isinstance(item, dict)).strip()
