from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Protocol


ProviderMessage = dict[str, str]


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retryable: bool = True,
        status_code: int | None = None,
        provider: str = "",
        safe_message: str = "",
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.provider = provider
        self.safe_message = safe_message or message


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    label: str
    api: str
    endpoint: str
    model: str
    local: bool
    secret_env: str = ""
    enabled: bool = True
    configured: bool = False
    capabilities: list[str] | None = None
    roles: list[str] | None = None
    cost_tier: str = "unknown"
    context_window: int | None = None
    rate_limit_rpm: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None


@dataclass(frozen=True)
class ProviderStatus:
    ready: bool
    message: str


@dataclass(frozen=True)
class ProviderModelRecord:
    id: str
    name: str
    provider: str
    api: str
    endpoint: str
    local: bool
    configured: bool
    available: bool
    ready: bool
    message: str
    size: int | None = None
    modified_at: str = ""
    capabilities: dict[str, bool] | None = None


@dataclass(frozen=True)
class ProviderInventory:
    active_model: str
    active_api: str
    active_endpoint: str
    message: str
    models: list[ProviderModelRecord]


@dataclass(frozen=True)
class ProviderStreamEvent:
    type: str
    delta: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    provider_id: str
    api: str
    endpoint: str
    model: str

    @property
    def label(self) -> str:
        ...

    async def status(self) -> ProviderStatus:
        ...

    async def inventory(self) -> ProviderInventory:
        ...

    async def complete_json(self, messages: list[ProviderMessage]) -> dict[str, Any]:
        ...

    def stream_text(
        self,
        messages: list[ProviderMessage],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        ...


def api_family(api: str) -> str:
    normalized = api.strip().lower()
    if normalized == "ollama":
        return "ollama"
    if normalized in {
        "openai",
        "openai-compatible",
        "lmstudio",
        "openrouter",
        "perplexity",
        "xai",
        "groq",
        "mistral",
        "deepseek",
        "together",
        "cerebras",
        "fireworks",
        "cohere",
        "google",
        "gemini",
        "huggingface",
        "nvidia",
        "sambanova",
    }:
        return "openai"
    if normalized in {"anthropic", "claude"}:
        return "anthropic"
    return "unsupported"


def is_local_endpoint(endpoint: str) -> bool:
    lowered = endpoint.strip().lower()
    return (
        not lowered
        or "127.0.0.1" in lowered
        or "localhost" in lowered
        or "[::1]" in lowered
        or "://::1" in lowered
        or "0.0.0.0" in lowered
    )


CAPABILITY_ALIASES: dict[str, str] = {
    "function_calling": "tools",
    "function-calling": "tools",
    "tool_use": "tools",
    "tool-use": "tools",
    "json": "structured_json",
    "structured_output": "structured_json",
    "structured_outputs": "structured_json",
    "structured-output": "structured_json",
    "multimodal": "vision",
    "image_input": "vision",
    "image-input": "vision",
    "text_embedding": "embeddings",
    "text-embedding": "embeddings",
    "embedding": "embeddings",
    "speech": "audio",
    "tts": "audio",
    "image_generation": "image",
    "image-generation": "image",
    "video_generation": "video",
    "video-generation": "video",
}


def normalize_capability(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return CAPABILITY_ALIASES.get(normalized, normalized)


def provider_capability_tags(
    api: str,
    endpoint: str,
    model: str,
    declared: list[str] | None = None,
) -> list[str]:
    family = api_family(api)
    normalized_api = api.strip().lower()
    haystack = f"{normalized_api} {endpoint} {model}".lower().replace("_", "-")
    tags = {
        normalize_capability(item)
        for item in (declared or [])
        if item and normalize_capability(str(item))
    }

    if family in {"ollama", "openai", "anthropic"}:
        tags.update({"chat", "structured_json"})

    if family == "openai":
        tags.add("streaming")
        if normalized_api not in {"perplexity"}:
            tags.add("tools")
    elif family == "anthropic":
        tags.update({"streaming", "tools"})
    elif family == "ollama":
        tags.add("streaming")

    if any(token in haystack for token in ("coder", "code", "codex", "starcoder", "devstral", "codegemma", "granite-code")):
        tags.update({"code", "debug", "refactor"})
    if any(token in haystack for token in ("reason", "r1", "qwq", "thinking", "opus", "sonnet", "gpt-5")):
        tags.update({"reasoning", "judge"})
    if any(token in haystack for token in ("vision", "llava", "bakllava", "moondream", "qwen-vl", "qwen2.5vl", "pixtral", "gpt-4o", "gemini", "claude")):
        tags.add("vision")
    if any(token in haystack for token in ("embedding", "embed", "text-embedding", "bge-", "e5-", "nomic-embed")):
        tags.add("embeddings")
    if "realtime" in haystack:
        tags.update({"audio", "realtime"})
    if any(token in haystack for token in ("audio", "whisper", "tts", "transcribe", "speech")):
        tags.add("audio")
    if any(token in haystack for token in ("gpt-image", "dall-e", "imagen", "flux", "sdxl", "stable-diffusion", "image")):
        tags.add("image")
    if any(token in haystack for token in ("video", "sora", "veo", "runway", "kling", "pika")):
        tags.add("video")
    if "computer-use" in haystack or "computer_use" in haystack:
        tags.add("computer_use")

    ordered = [
        "chat",
        "code",
        "debug",
        "refactor",
        "reasoning",
        "research",
        "structured_json",
        "streaming",
        "tools",
        "vision",
        "audio",
        "embeddings",
        "image",
        "video",
        "realtime",
        "judge",
        "computer_use",
    ]
    return [tag for tag in ordered if tag in tags] + sorted(tags - set(ordered))


def provider_capability_flags(
    api: str,
    endpoint: str,
    model: str,
    declared: list[str] | None = None,
) -> dict[str, bool]:
    tags = set(provider_capability_tags(api, endpoint, model, declared))
    return {
        "chat": "chat" in tags,
        "code": "code" in tags,
        "debug": "debug" in tags,
        "refactor": "refactor" in tags,
        "reasoning": "reasoning" in tags,
        "research": "research" in tags,
        "streaming": "streaming" in tags,
        "structured_json": "structured_json" in tags,
        "tools": "tools" in tags,
        "vision": "vision" in tags,
        "audio": "audio" in tags,
        "embeddings": "embeddings" in tags,
        "image": "image" in tags,
        "video": "video" in tags,
        "realtime": "realtime" in tags,
        "judge": "judge" in tags,
        "computer_use": "computer_use" in tags,
    }


def secret_env_name(api: str, endpoint: str) -> str:
    normalized = api.strip().lower()
    lowered_endpoint = endpoint.lower()
    if normalized in {"anthropic", "claude"} or "anthropic.com" in lowered_endpoint:
        return "ANTHROPIC_API_KEY"
    if normalized == "xai" or "api.x.ai" in lowered_endpoint:
        return "XAI_API_KEY"
    if normalized == "groq" or "api.groq.com" in lowered_endpoint:
        return "GROQ_API_KEY"
    if normalized == "mistral" or "api.mistral.ai" in lowered_endpoint:
        return "MISTRAL_API_KEY"
    if normalized == "deepseek" or "api.deepseek.com" in lowered_endpoint:
        return "DEEPSEEK_API_KEY"
    if normalized == "together" or "api.together.xyz" in lowered_endpoint:
        return "TOGETHER_API_KEY"
    if normalized == "cerebras" or "api.cerebras.ai" in lowered_endpoint:
        return "CEREBRAS_API_KEY"
    if normalized == "fireworks" or "api.fireworks.ai" in lowered_endpoint:
        return "FIREWORKS_API_KEY"
    if normalized == "cohere" or "api.cohere.com" in lowered_endpoint:
        return "COHERE_API_KEY"
    if normalized in {"google", "gemini"} or "generativelanguage.googleapis.com" in lowered_endpoint:
        return "GEMINI_API_KEY"
    if normalized == "huggingface" or "huggingface.co" in lowered_endpoint:
        return "HUGGINGFACE_API_KEY"
    if normalized == "nvidia" or "api.nvidia.com" in lowered_endpoint:
        return "NVIDIA_API_KEY"
    if normalized == "sambanova" or "api.sambanova.ai" in lowered_endpoint:
        return "SAMBANOVA_API_KEY"
    if normalized == "openrouter" or "openrouter.ai" in lowered_endpoint:
        return "OPENROUTER_API_KEY"
    if normalized == "perplexity" or "perplexity.ai" in lowered_endpoint:
        return "PERPLEXITY_API_KEY"
    if not is_local_endpoint(endpoint):
        return "OPENAI_API_KEY"
    return ""


def provider_label(api: str, endpoint: str) -> str:
    normalized = api.strip().lower()
    lowered_endpoint = endpoint.lower()
    if normalized == "ollama":
        return "Ollama"
    if normalized in {"anthropic", "claude"} or "anthropic.com" in lowered_endpoint:
        return "Anthropic Claude"
    if normalized == "xai" or "api.x.ai" in lowered_endpoint:
        return "xAI"
    if normalized == "groq" or "api.groq.com" in lowered_endpoint:
        return "Groq"
    if normalized == "mistral" or "api.mistral.ai" in lowered_endpoint:
        return "Mistral AI"
    if normalized == "deepseek" or "api.deepseek.com" in lowered_endpoint:
        return "DeepSeek"
    if normalized == "together" or "api.together.xyz" in lowered_endpoint:
        return "Together AI"
    if normalized == "cerebras" or "api.cerebras.ai" in lowered_endpoint:
        return "Cerebras"
    if normalized == "fireworks" or "api.fireworks.ai" in lowered_endpoint:
        return "Fireworks AI"
    if normalized == "cohere" or "api.cohere.com" in lowered_endpoint:
        return "Cohere"
    if normalized in {"google", "gemini"} or "generativelanguage.googleapis.com" in lowered_endpoint:
        return "Google Gemini"
    if normalized == "huggingface" or "huggingface.co" in lowered_endpoint:
        return "Hugging Face"
    if normalized == "nvidia" or "api.nvidia.com" in lowered_endpoint:
        return "NVIDIA NIM"
    if normalized == "sambanova" or "api.sambanova.ai" in lowered_endpoint:
        return "SambaNova"
    if normalized == "openrouter" or "openrouter.ai" in lowered_endpoint:
        return "OpenRouter"
    if normalized == "perplexity" or "perplexity.ai" in lowered_endpoint:
        return "Perplexity"
    if is_local_endpoint(endpoint):
        return "OpenAI-compatible local"
    return "OpenAI-compatible cloud"


def secret_value(env_name: str) -> str:
    env_name = env_name.strip()
    if not env_name:
        return ""
    secret = os.getenv(env_name, "").strip()
    if secret:
        return secret

    env_path = Path(__file__).resolve().parents[3] / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != env_name:
            continue
        return value.strip().strip('"').strip("'").strip()
    return ""


def bearer_headers(api: str, endpoint: str, secret_env: str = "") -> dict[str, str]:
    env_name = secret_env.strip() or secret_env_name(api, endpoint)
    if not env_name:
        return {}
    secret = secret_value(env_name)
    if not secret:
        return {}
    return {"Authorization": f"Bearer {secret}"}


def extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("empty response body")

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(content[:400])
        payload = json.loads(text[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload
