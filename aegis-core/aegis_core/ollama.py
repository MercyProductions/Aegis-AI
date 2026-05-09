from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import AegisConfig


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

    def _request_json(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
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
        return sorted(model.get("name", "") for model in data.get("models", []) if model.get("name"))

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
            return OllamaStatus(False, None, [], None, [self.config.default_model, *self.config.fallback_models], str(exc))

    def chat(self, prompt: str, model: str | None = None, timeout: int = 120) -> str:
        selected = model or self.config.default_model
        payload = {
            "model": selected,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        data = self._request_json("/api/chat", payload=payload, timeout=timeout)
        return data.get("message", {}).get("content", "")
