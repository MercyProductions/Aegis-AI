from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SUPPORTED_CLOUD_PROVIDERS = {"openai", "anthropic", "google", "openrouter"}


@dataclass
class AegisConfig:
    ollama_url: str = "http://127.0.0.1:11434"
    lm_studio_url: str = "http://127.0.0.1:1234"
    default_model: str = "qwen3-coder:30b"
    default_local_model: str = "qwen3-coder:30b"
    local_small_model: str = "qwen2.5-coder:7b"
    local_coder_model: str = "qwen3-coder:30b"
    local_embedding_model: str = "nomic-embed-text"
    preferred_cloud_provider: str = "openai"
    preferred_cloud_model: str = "gpt-4.1"
    model_routing_mode: str = "local_only"
    fallback_models: tuple[str, ...] = ("qwen2.5-coder:7b", "granite-code:8b")
    max_context_chars: int = 62000
    cloud_cost_warnings: bool = True
    safety_mode: str = "strict"
    auto_scan_on_open: bool = False
    validation_preferences: tuple[str, ...] = ()
    memory_dir_name: str = ".aegis"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fallback_models"] = list(self.fallback_models)
        data["validation_preferences"] = list(self.validation_preferences)
        return data


class ConfigPersistenceError(RuntimeError):
    """Raised when a settings update cannot be persisted."""


def workspace_root(path: str | Path | None = None) -> Path:
    return Path(path or os.getcwd()).expanduser().resolve()


def memory_dir(workspace: str | Path | None = None, config: AegisConfig | None = None) -> Path:
    cfg = config or AegisConfig()
    return workspace_root(workspace) / _clean_memory_dir_name(cfg.memory_dir_name)


def _clean_string(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _clean_http_base_url(value: Any, default: str) -> str:
    text = _clean_string(value, default).rstrip("/")
    if "://" in text and not text.startswith(("http://", "https://")):
        return default
    if not text.startswith(("http://", "https://")):
        text = f"http://{text}"
    parsed = urlparse(text)
    try:
        parsed.port
    except ValueError:
        return default
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or "@" in parsed.netloc
        or any(char.isspace() for char in parsed.netloc)
    ):
        return default
    return f"{parsed.scheme}://{parsed.netloc}"


def _clean_ollama_url(value: Any) -> str:
    return _clean_http_base_url(value, AegisConfig.ollama_url)


def _clean_lm_studio_url(value: Any) -> str:
    return _clean_http_base_url(value, AegisConfig.lm_studio_url)


def _clean_routing_mode(value: Any) -> str:
    text = _clean_string(value, AegisConfig.model_routing_mode).lower().replace("-", "_")
    return text if text in {"local_only", "hybrid", "cloud_allowed"} else AegisConfig.model_routing_mode


def _clean_cloud_provider(value: Any) -> str:
    text = _clean_string(value, AegisConfig.preferred_cloud_provider).lower().replace("-", "_")
    return text if text in SUPPORTED_CLOUD_PROVIDERS else AegisConfig.preferred_cloud_provider


def _clean_memory_dir_name(value: Any) -> str:
    text = _clean_string(value, AegisConfig.memory_dir_name)
    if any(separator in text for separator in ("/", "\\", ":")):
        return AegisConfig.memory_dir_name
    candidate = Path(text)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.parts[0] in {".", ".."}:
        return AegisConfig.memory_dir_name
    return text


def _clean_string_list(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple)):
        candidates = value
    else:
        candidates = default
    cleaned = [str(item).strip() for item in candidates if str(item).strip()]
    return tuple(cleaned) if cleaned else tuple(default)


def _clean_int(value: Any, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _clean_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int):
        return bool(value)
    return default


def load_config(workspace: str | Path | None = None) -> AegisConfig:
    root = workspace_root(workspace)
    config_path = root / ".aegis" / "config.json"
    data = _read_config_data(config_path)

    env_url = os.environ.get("AEGIS_OLLAMA_URL")
    if env_url:
        data["ollama_url"] = env_url

    return AegisConfig(
        ollama_url=_clean_ollama_url(data.get("ollama_url")),
        lm_studio_url=_clean_lm_studio_url(data.get("lm_studio_url")),
        default_model=_clean_string(data.get("default_model"), AegisConfig.default_model),
        default_local_model=_clean_string(data.get("default_local_model", data.get("default_model")), AegisConfig.default_local_model),
        local_small_model=_clean_string(data.get("local_small_model"), AegisConfig.local_small_model),
        local_coder_model=_clean_string(data.get("local_coder_model", data.get("default_model")), AegisConfig.local_coder_model),
        local_embedding_model=_clean_string(data.get("local_embedding_model"), AegisConfig.local_embedding_model),
        preferred_cloud_provider=_clean_cloud_provider(data.get("preferred_cloud_provider")),
        preferred_cloud_model=_clean_string(data.get("preferred_cloud_model"), AegisConfig.preferred_cloud_model),
        model_routing_mode=_clean_routing_mode(data.get("model_routing_mode")),
        fallback_models=_clean_string_list(data.get("fallback_models"), AegisConfig.fallback_models),
        max_context_chars=_clean_int(data.get("max_context_chars"), AegisConfig.max_context_chars, minimum=1000),
        cloud_cost_warnings=_clean_bool(data.get("cloud_cost_warnings"), AegisConfig.cloud_cost_warnings),
        safety_mode=_clean_string(data.get("safety_mode"), AegisConfig.safety_mode),
        auto_scan_on_open=_clean_bool(data.get("auto_scan_on_open"), AegisConfig.auto_scan_on_open),
        validation_preferences=_clean_string_list(data.get("validation_preferences"), AegisConfig.validation_preferences),
        memory_dir_name=_clean_memory_dir_name(data.get("memory_dir_name")),
    )


def write_default_config(workspace: str | Path | None = None) -> Path:
    root = workspace_root(workspace)
    path = root / ".aegis" / "config.json"
    if not path.exists():
        _write_json_best_effort(path, AegisConfig().to_dict())
    return path


def update_config(workspace: str | Path | None, updates: dict[str, Any]) -> AegisConfig:
    allowed = {
        "ollama_url",
        "lm_studio_url",
        "default_model",
        "default_local_model",
        "local_small_model",
        "local_coder_model",
        "local_embedding_model",
        "preferred_cloud_provider",
        "preferred_cloud_model",
        "model_routing_mode",
        "fallback_models",
        "max_context_chars",
        "cloud_cost_warnings",
        "safety_mode",
        "auto_scan_on_open",
        "validation_preferences",
        "memory_dir_name",
    }
    root = workspace_root(workspace)
    path = write_default_config(root)
    current = _read_config_data(path)
    for key, value in updates.items():
        if key in allowed:
            current[key] = _clean_memory_dir_name(value) if key == "memory_dir_name" else value
    if not _write_json_best_effort(path, current):
        raise ConfigPersistenceError(f"Could not persist Aegis Core settings to {path}.")
    return load_config(root)


def _read_config_data(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_best_effort(path: Path, data: dict[str, Any]) -> bool:
    tmp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not path.is_file():
            return False
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        if tmp is not None:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
        return False
