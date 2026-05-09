from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import AegisConfig
from .diagnostics import scrub


@dataclass
class OllamaStatus:
    reachable: bool
    latency_ms: int | None
    installed_models: list[str]
    selected_model: str | None
    missing_models: list[str]
    error: str | None = None


class OllamaClient:
    def __init__(self, config: AegisConfig):
        self.config = config
        self.base_url = config.ollama_url.rstrip("/")

    def _request_json(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 20) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            method = "POST"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def list_models(self) -> list[str]:
        data = self._request_json("/api/tags", timeout=5)
        if not isinstance(data, dict):
            raise ValueError("Ollama model list response was not a JSON object.")
        models = data.get("models", [])
        if not isinstance(models, list):
            raise ValueError("Ollama model list response did not include a models array.")
        names = {
            name.strip()
            for model in models
            if isinstance(model, dict)
            for name in [model.get("name")]
            if isinstance(name, str) and name.strip()
        }
        return sorted(names)

    def health(self) -> OllamaStatus:
        started = time.perf_counter()
        try:
            models = self.list_models()
            latency = int((time.perf_counter() - started) * 1000)
            desired = [self.config.default_model, *self.config.fallback_models]
            selected = next((model for model in desired if model in models), None)
            missing = [model for model in desired if model not in models]
            return OllamaStatus(True, latency, models, selected, missing)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            return OllamaStatus(False, None, [], None, [self.config.default_model, *self.config.fallback_models], scrub(str(exc)))

    def chat(self, prompt: str, model: str | None = None, timeout: int = 120) -> str:
        selected = model or self.config.default_model
        payload = {
            "model": selected,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        data = self._request_json("/api/chat", payload=payload, timeout=timeout)
        return data.get("message", {}).get("content", "")
