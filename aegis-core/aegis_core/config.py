from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AegisConfig:
    ollama_url: str = "http://127.0.0.1:11434"
    default_model: str = "qwen3-coder:30b"
    fallback_models: tuple[str, ...] = ("qwen2.5-coder:7b", "granite-code:8b")
    max_context_chars: int = 62000
    safety_mode: str = "strict"
    auto_scan_on_open: bool = False
    validation_preferences: tuple[str, ...] = ()
    memory_dir_name: str = ".aegis"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fallback_models"] = list(self.fallback_models)
        data["validation_preferences"] = list(self.validation_preferences)
        return data


def workspace_root(path: str | Path | None = None) -> Path:
    return Path(path or os.getcwd()).expanduser().resolve()


def memory_dir(workspace: str | Path | None = None, config: AegisConfig | None = None) -> Path:
    cfg = config or AegisConfig()
    return workspace_root(workspace) / cfg.memory_dir_name


def load_config(workspace: str | Path | None = None) -> AegisConfig:
    root = workspace_root(workspace)
    config_path = root / ".aegis" / "config.json"
    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    env_url = os.environ.get("AEGIS_OLLAMA_URL")
    if env_url:
        data["ollama_url"] = env_url

    fallbacks = data.get("fallback_models", AegisConfig.fallback_models)
    if isinstance(fallbacks, str):
        fallbacks = [item.strip() for item in fallbacks.split(",") if item.strip()]

    preferences = data.get("validation_preferences", AegisConfig.validation_preferences)
    if isinstance(preferences, str):
        preferences = [item.strip() for item in preferences.split(",") if item.strip()]

    return AegisConfig(
        ollama_url=str(data.get("ollama_url", AegisConfig.ollama_url)).rstrip("/"),
        default_model=str(data.get("default_model", AegisConfig.default_model)),
        fallback_models=tuple(fallbacks),
        max_context_chars=int(data.get("max_context_chars", AegisConfig.max_context_chars)),
        safety_mode=str(data.get("safety_mode", AegisConfig.safety_mode)),
        auto_scan_on_open=bool(data.get("auto_scan_on_open", AegisConfig.auto_scan_on_open)),
        validation_preferences=tuple(preferences),
        memory_dir_name=str(data.get("memory_dir_name", AegisConfig.memory_dir_name)),
    )


def write_default_config(workspace: str | Path | None = None) -> Path:
    root = workspace_root(workspace)
    path = root / ".aegis" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(AegisConfig().to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def update_config(workspace: str | Path | None, updates: dict[str, Any]) -> AegisConfig:
    allowed = {
        "ollama_url",
        "default_model",
        "fallback_models",
        "max_context_chars",
        "safety_mode",
        "auto_scan_on_open",
        "validation_preferences",
        "memory_dir_name",
    }
    root = workspace_root(workspace)
    path = write_default_config(root)
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        current = {}
    for key, value in updates.items():
        if key in allowed:
            current[key] = value
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return load_config(root)
