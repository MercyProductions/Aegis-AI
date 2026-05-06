from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from ..settings import Settings
from ..schemas import ModelAttemptInfo, ModelRegistryProvider
from .base import (
    ProviderAdapter,
    ProviderConfig,
    ProviderError,
    ProviderInventory,
    ProviderMessage,
    ProviderModelRecord,
    ProviderStatus,
    ProviderStreamEvent,
    api_family,
    bearer_headers,
    extract_json_object,
    is_local_endpoint,
    provider_capability_flags,
    provider_capability_tags,
    provider_label,
    secret_value,
    secret_env_name,
)


@dataclass
class BaseHttpProviderAdapter:
    settings: Settings
    config: ProviderConfig | None = None

    def __post_init__(self) -> None:
        config = self.config or provider_config_from_settings(self.settings)
        self.provider_id = config.provider_id
        self.provider_label = config.label
        self.api = config.api.strip().lower()
        self.endpoint = config.endpoint.rstrip("/")
        self.model = config.model.strip()
        self.secret_env = config.secret_env.strip()
        self.configured = config.configured
        self.enabled = config.enabled
        self.capabilities = config.capabilities or []
        self.roles = config.roles or []
        self.cost_tier = config.cost_tier
        self.context_window = config.context_window
        self.rate_limit_rpm = config.rate_limit_rpm
        self.input_cost_per_million = config.input_cost_per_million
        self.output_cost_per_million = config.output_cost_per_million
        self.local_override = config.local
        self.last_completion_metadata: dict[str, Any] = {}

    @property
    def label(self) -> str:
        return self.model or self.provider_label or "Local model"

    @property
    def provider_name(self) -> str:
        return self.provider_label or provider_label(self.api, self.endpoint)

    @property
    def local(self) -> bool:
        return self.local_override if self.config is not None else is_local_endpoint(self.endpoint)

    def record(
        self,
        name: str,
        *,
        configured: bool,
        available: bool,
        ready: bool,
        message: str,
        size: int | None = None,
        modified_at: str = "",
    ) -> ProviderModelRecord:
        return ProviderModelRecord(
            id=f"{self.provider_id}:{name}" if self.provider_id else f"{self.api}:{name}",
            name=name,
            provider=self.provider_name,
            api=self.api,
            endpoint=self.endpoint,
            local=self.local,
            configured=configured,
            available=available,
            ready=ready,
            message=message,
            size=size,
            modified_at=modified_at,
            capabilities=provider_capability_flags(
                self.api,
                self.endpoint,
                name,
                self.capabilities,
            ),
        )

    async def complete_json(self, messages: list[ProviderMessage]) -> dict[str, Any]:
        if not self.model:
            raise ProviderError(
                "No model is configured.",
                code="model_not_configured",
                retryable=False,
                provider=self.provider_name,
            )
        self.last_completion_metadata = {}
        try:
            content = await self.complete(messages)
            return extract_json_object(content)
        except httpx.HTTPError as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise ProviderError(
                f"Model request failed: {exc}",
                code="provider_http_error",
                retryable=status_code is None or status_code >= 500 or status_code == 429,
                status_code=status_code,
                provider=self.provider_name,
                safe_message=f"{self.provider_name} request failed.",
            ) from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Model returned an invalid response: {exc}",
                code="provider_invalid_response",
                retryable=False,
                provider=self.provider_name,
                safe_message=f"{self.provider_name} returned an invalid response.",
            ) from exc

    async def complete(self, messages: list[ProviderMessage]) -> str:
        raise ProviderError(f"Provider adapter does not implement complete: {self.api}")

    def completion_metadata(self) -> dict[str, Any]:
        return dict(self.last_completion_metadata)

    async def stream_text(
        self,
        messages: list[ProviderMessage],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(type="start", metadata=self._stream_metadata())
        content = await self.complete(messages)
        for chunk in self._chunk_text(content):
            yield ProviderStreamEvent(type="delta", delta=chunk)
        metadata = self.completion_metadata()
        if metadata:
            yield ProviderStreamEvent(type="metadata", metadata=metadata)
        yield ProviderStreamEvent(type="done", metadata=self._stream_metadata())

    def _stream_metadata(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_label": self.provider_name,
            "provider_api": self.api,
            "endpoint": self.endpoint,
            "model": self.model,
            "streaming": "streaming" in provider_capability_tags(
                self.api,
                self.endpoint,
                self.model,
                self.capabilities,
            ),
        }

    def _chunk_text(self, content: str, *, chunk_size: int = 480) -> list[str]:
        text = content or ""
        if not text:
            return []
        chunks: list[str] = []
        while text:
            if len(text) <= chunk_size:
                chunks.append(text)
                break
            split_at = max(text.rfind("\n", 0, chunk_size), text.rfind(" ", 0, chunk_size))
            if split_at < chunk_size // 2:
                split_at = chunk_size
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip()
        return chunks

    def _record_token_usage(
        self,
        *,
        input_tokens: Any = None,
        output_tokens: Any = None,
        total_tokens: Any = None,
        source: str,
    ) -> None:
        reported_input = self._positive_int(input_tokens)
        reported_output = self._positive_int(output_tokens)
        reported_total = self._positive_int(total_tokens)
        if reported_total is None and (reported_input is not None or reported_output is not None):
            reported_total = (reported_input or 0) + (reported_output or 0)
        if reported_input is None and reported_output is None and reported_total is None:
            return
        metadata: dict[str, Any] = {"reported_token_source": source}
        if reported_input is not None:
            metadata["reported_input_tokens"] = reported_input
        if reported_output is not None:
            metadata["reported_output_tokens"] = reported_output
        if reported_total is not None:
            metadata["reported_total_tokens"] = reported_total
        self.last_completion_metadata.update(metadata)

    def _record_openai_usage(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return
        self._record_token_usage(
            input_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
            output_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
            source=f"{self.api or 'openai'}:usage",
        )

    def _record_ollama_usage(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        self._record_token_usage(
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
            total_tokens=payload.get("total_count"),
            source="ollama:chat",
        )

    def _record_anthropic_usage(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return
        self._record_token_usage(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            source="anthropic:messages",
        )

    def _positive_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None


class UnsupportedProviderAdapter(BaseHttpProviderAdapter):
    async def status(self) -> ProviderStatus:
        return ProviderStatus(False, f"Unsupported local model API: {self.api}")

    async def inventory(self) -> ProviderInventory:
        return ProviderInventory(
            active_model=self.model,
            active_api=self.api,
            active_endpoint=self.endpoint,
            message=f"Unsupported local model API: {self.api}",
            models=[
                self.record(
                    self.model or "unconfigured",
                    configured=bool(self.model),
                    available=False,
                    ready=False,
                    message=f"Unsupported local model API: {self.api}",
                )
            ],
        )


class CloudConfiguredProviderAdapter(BaseHttpProviderAdapter):
    async def status(self) -> ProviderStatus:
        if not self.model:
            return ProviderStatus(False, "No local model is configured.")
        env_name = self.secret_env or secret_env_name(self.api, self.endpoint)
        if env_name and not secret_value(env_name):
            return ProviderStatus(False, f"{self.provider_name} is configured, but {env_name} is not set.")
        return ProviderStatus(
            True,
            f"{self.provider_name} is configured for {self.model}. Live requests will validate the remote provider.",
        )

    async def inventory(self) -> ProviderInventory:
        status = await self.status()
        return ProviderInventory(
            active_model=self.model,
            active_api=self.api,
            active_endpoint=self.endpoint,
            message=status.message,
            models=[
                self.record(
                    self.model or "unconfigured",
                    configured=bool(self.model),
                    available=status.ready,
                    ready=status.ready,
                    message=status.message,
                )
            ],
        )


class OpenAICompatibleProviderAdapter(CloudConfiguredProviderAdapter):
    def openai_base(self) -> str:
        if self.api == "perplexity":
            return self.endpoint
        if self.endpoint.endswith("/v1"):
            return self.endpoint
        return f"{self.endpoint}/v1"

    async def status(self) -> ProviderStatus:
        if self.local:
            return await self._local_status()
        return await super().status()

    async def inventory(self) -> ProviderInventory:
        if not self.local:
            return await super().inventory()

        if not self.model:
            base_message = "No local model is configured."
        else:
            base_message = f"Configured model: {self.model}."

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                records = await self._inventory_records(client)
        except Exception as exc:  # pragma: no cover - depends on local runtime
            return ProviderInventory(
                active_model=self.model,
                active_api=self.api,
                active_endpoint=self.endpoint,
                message=f"Local model server is not reachable: {exc}",
                models=[
                    self.record(
                        self.model or "unconfigured",
                        configured=bool(self.model),
                        available=False,
                        ready=False,
                        message=f"Local model server is not reachable: {exc}",
                    )
                ],
            )

        found_configured = any(record.configured for record in records)
        if self.model and not found_configured:
            records.append(
                self.record(
                    self.model,
                    configured=True,
                    available=False,
                    ready=False,
                    message=f"Configured model '{self.model}' was not found on the local model server.",
                )
            )

        records.sort(key=lambda record: (not record.configured, record.name.lower()))
        ready_count = sum(1 for record in records if record.ready)
        return ProviderInventory(
            active_model=self.model,
            active_api=self.api,
            active_endpoint=self.endpoint,
            message=f"{base_message} {ready_count} available model(s) discovered.",
            models=records,
        )

    async def complete(self, messages: list[ProviderMessage]) -> str:
        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.settings.aegis_model_temperature,
        }
        if self.api != "perplexity" and "perplexity.ai" not in self.endpoint.lower():
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.openai_base()}/chat/completions",
                headers=bearer_headers(self.api, self.endpoint, self.secret_env),
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
            self._record_openai_usage(payload)
            return self._extract_content(payload)

    async def stream_text(
        self,
        messages: list[ProviderMessage],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        if not self.model:
            raise ProviderError(
                "No model is configured.",
                code="model_not_configured",
                retryable=False,
                provider=self.provider_name,
            )
        self.last_completion_metadata = {}
        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.settings.aegis_model_temperature,
            "stream": True,
        }
        if structured_json and self.api != "perplexity" and "perplexity.ai" not in self.endpoint.lower():
            body["response_format"] = {"type": "json_object"}
        yield ProviderStreamEvent(type="start", metadata=self._stream_metadata())
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.openai_base()}/chat/completions",
                    headers=bearer_headers(self.api, self.endpoint, self.secret_env),
                    json=body,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        chunk = self._openai_stream_delta(line)
                        if chunk == "[DONE]":
                            break
                        if chunk:
                            yield ProviderStreamEvent(type="delta", delta=chunk)
        except httpx.HTTPError as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise ProviderError(
                f"Streaming model request failed: {exc}",
                code="provider_stream_http_error",
                retryable=status_code is None or status_code >= 500 or status_code == 429,
                status_code=status_code,
                provider=self.provider_name,
                safe_message=f"{self.provider_name} streaming request failed.",
            ) from exc
        metadata = self.completion_metadata()
        if metadata:
            yield ProviderStreamEvent(type="metadata", metadata=metadata)
        yield ProviderStreamEvent(type="done", metadata=self._stream_metadata())

    def _openai_stream_delta(self, line: str) -> str:
        raw = line.strip()
        if not raw or not raw.startswith("data:"):
            return ""
        data = raw[5:].strip()
        if data == "[DONE]":
            return "[DONE]"
        payload = json.loads(data)
        self._record_openai_usage(payload)
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ""
        delta = first_choice.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return delta["content"]
        message = first_choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        return ""

    async def _local_status(self) -> ProviderStatus:
        if not self.model:
            return ProviderStatus(False, "No local model is configured.")

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                records = await self._inventory_records(client)
        except Exception as exc:  # pragma: no cover - depends on local runtime
            return ProviderStatus(False, f"Local model server is not reachable: {exc}")

        available = {record.name for record in records if record.available}
        if self.model not in available:
            return ProviderStatus(False, f"Configured model '{self.model}' was not found on the local model server.")
        return ProviderStatus(True, f"Local model server is reachable for {self.model}.")

    async def _inventory_records(self, client: httpx.AsyncClient) -> list[ProviderModelRecord]:
        response = await client.get(f"{self.openai_base()}/models")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("OpenAI-compatible model server returned an invalid response")

        models = payload.get("data", [])
        if not isinstance(models, list):
            raise TypeError("OpenAI-compatible model server returned an invalid models list")

        records: list[ProviderModelRecord] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id", "")).strip()
            if not model_id:
                continue
            records.append(
                self.record(
                    model_id,
                    configured=model_id == self.model,
                    available=True,
                    ready=True,
                    message="Available from the OpenAI-compatible model server.",
                )
            )
        return records

    def _extract_content(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("OpenAI-compatible response was not a JSON object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise KeyError("OpenAI-compatible response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise TypeError("OpenAI-compatible choice was not an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise KeyError("OpenAI-compatible response missing message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenAI-compatible response contained empty message content")
        return content


class OllamaProviderAdapter(BaseHttpProviderAdapter):
    async def status(self) -> ProviderStatus:
        if not self.model:
            return ProviderStatus(False, "No local model is configured.")

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                records = await self._inventory_records(client)
        except Exception as exc:  # pragma: no cover - depends on local runtime
            return ProviderStatus(False, f"Local model server is not reachable: {exc}")

        available = {record.name for record in records if record.available}
        if self.model not in available:
            return ProviderStatus(False, f"Configured model '{self.model}' was not found on the local model server.")
        return ProviderStatus(True, f"Local model server is reachable for {self.model}.")

    async def inventory(self) -> ProviderInventory:
        if not self.model:
            base_message = "No local model is configured."
        else:
            base_message = f"Configured model: {self.model}."

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                records = await self._inventory_records(client)
        except Exception as exc:  # pragma: no cover - depends on local runtime
            return ProviderInventory(
                active_model=self.model,
                active_api=self.api,
                active_endpoint=self.endpoint,
                message=f"Local model server is not reachable: {exc}",
                models=[
                    self.record(
                        self.model or "unconfigured",
                        configured=bool(self.model),
                        available=False,
                        ready=False,
                        message=f"Local model server is not reachable: {exc}",
                    )
                ],
            )

        found_configured = any(record.configured for record in records)
        if self.model and not found_configured:
            records.append(
                self.record(
                    self.model,
                    configured=True,
                    available=False,
                    ready=False,
                    message=f"Configured model '{self.model}' was not found on the local model server.",
                )
            )
        records.sort(key=lambda record: (not record.configured, record.name.lower()))
        ready_count = sum(1 for record in records if record.ready)
        return ProviderInventory(
            active_model=self.model,
            active_api=self.api,
            active_endpoint=self.endpoint,
            message=f"{base_message} {ready_count} available model(s) discovered.",
            models=records,
        )

    async def complete(self, messages: list[ProviderMessage]) -> str:
        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.endpoint}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": self.settings.aegis_model_temperature},
                },
            )
            response.raise_for_status()
            payload = response.json()
            self._record_ollama_usage(payload)
            return self._extract_content(payload)

    async def stream_text(
        self,
        messages: list[ProviderMessage],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        if not self.model:
            raise ProviderError(
                "No model is configured.",
                code="model_not_configured",
                retryable=False,
                provider=self.provider_name,
            )
        self.last_completion_metadata = {}
        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        yield ProviderStreamEvent(type="start", metadata=self._stream_metadata())
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                body: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": self.settings.aegis_model_temperature},
                }
                if structured_json:
                    body["format"] = "json"
                async with client.stream(
                    "POST",
                    f"{self.endpoint}/api/chat",
                    json=body,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        payload = self._ollama_stream_payload(line)
                        if not payload:
                            continue
                        if isinstance(payload, dict):
                            self._record_ollama_usage(payload)
                            message = payload.get("message")
                            if isinstance(message, dict) and isinstance(message.get("content"), str):
                                yield ProviderStreamEvent(type="delta", delta=message["content"])
                            if payload.get("done") is True:
                                break
        except httpx.HTTPError as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise ProviderError(
                f"Streaming model request failed: {exc}",
                code="provider_stream_http_error",
                retryable=status_code is None or status_code >= 500 or status_code == 429,
                status_code=status_code,
                provider=self.provider_name,
                safe_message=f"{self.provider_name} streaming request failed.",
            ) from exc
        metadata = self.completion_metadata()
        if metadata:
            yield ProviderStreamEvent(type="metadata", metadata=metadata)
        yield ProviderStreamEvent(type="done", metadata=self._stream_metadata())

    def _ollama_stream_payload(self, line: str) -> dict[str, Any] | None:
        raw = line.strip()
        if not raw:
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None

    async def _inventory_records(self, client: httpx.AsyncClient) -> list[ProviderModelRecord]:
        response = await client.get(f"{self.endpoint}/api/tags")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Ollama server returned an invalid response")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise TypeError("Ollama server returned an invalid models list")

        records: list[ProviderModelRecord] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            size = item.get("size")
            records.append(
                self.record(
                    name,
                    configured=name == self.model,
                    available=True,
                    ready=True,
                    message="Available locally through Ollama.",
                    size=size if isinstance(size, int) else None,
                    modified_at=str(item.get("modified_at", "") or ""),
                )
            )
        return records

    def _extract_content(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("Ollama response was not a JSON object")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise KeyError("Ollama response missing message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response contained empty message content")
        return content


class AnthropicProviderAdapter(CloudConfiguredProviderAdapter):
    async def complete(self, messages: list[ProviderMessage]) -> str:
        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content", "") or "")
            if not content.strip():
                continue
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": "Respond with a JSON object for the requested Aegis task."})

        env_name = self.secret_env or secret_env_name(self.api, self.endpoint)
        secret = secret_value(env_name) if env_name else ""
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if secret:
            headers["x-api-key"] = secret

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._anthropic_base()}/messages",
                headers=headers,
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "temperature": self.settings.aegis_model_temperature,
                    "system": "\n\n".join(system_parts),
                    "messages": anthropic_messages,
                },
            )
            response.raise_for_status()
            payload = response.json()
            self._record_anthropic_usage(payload)
            return self._extract_content(payload)

    async def stream_text(
        self,
        messages: list[ProviderMessage],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        if not self.model:
            raise ProviderError(
                "No model is configured.",
                code="model_not_configured",
                retryable=False,
                provider=self.provider_name,
            )
        self.last_completion_metadata = {}
        system_parts, anthropic_messages = self._anthropic_messages(messages)
        env_name = self.secret_env or secret_env_name(self.api, self.endpoint)
        secret = secret_value(env_name) if env_name else ""
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if secret:
            headers["x-api-key"] = secret

        timeout = httpx.Timeout(self.settings.aegis_model_timeout_seconds)
        yield ProviderStreamEvent(type="start", metadata=self._stream_metadata())
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._anthropic_base()}/messages",
                    headers=headers,
                    json={
                        "model": self.model,
                        "max_tokens": 4096,
                        "temperature": self.settings.aegis_model_temperature,
                        "system": "\n\n".join(system_parts),
                        "messages": anthropic_messages,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        event = self._anthropic_stream_event(line)
                        if event is None:
                            continue
                        if event.type == "delta" and event.delta:
                            yield event
                        elif event.type == "done":
                            break
        except httpx.HTTPError as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise ProviderError(
                f"Streaming model request failed: {exc}",
                code="provider_stream_http_error",
                retryable=status_code is None or status_code >= 500 or status_code == 429,
                status_code=status_code,
                provider=self.provider_name,
                safe_message=f"{self.provider_name} streaming request failed.",
            ) from exc
        metadata = self.completion_metadata()
        if metadata:
            yield ProviderStreamEvent(type="metadata", metadata=metadata)
        yield ProviderStreamEvent(type="done", metadata=self._stream_metadata())

    def _anthropic_messages(self, messages: list[ProviderMessage]) -> tuple[list[str], list[dict[str, str]]]:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content", "") or "")
            if not content.strip():
                continue
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": "Respond with a concise answer."})
        return system_parts, anthropic_messages

    def _anthropic_stream_event(self, line: str) -> ProviderStreamEvent | None:
        raw = line.strip()
        if not raw or not raw.startswith("data:"):
            return None
        payload = json.loads(raw[5:].strip())
        if not isinstance(payload, dict):
            return None
        event_type = str(payload.get("type", "") or "")
        if event_type == "content_block_delta":
            delta = payload.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("text"), str):
                return ProviderStreamEvent(type="delta", delta=delta["text"])
        if event_type == "message_delta":
            self._record_anthropic_usage(payload)
            return ProviderStreamEvent(type="metadata", metadata=self.completion_metadata())
        if event_type == "message_stop":
            return ProviderStreamEvent(type="done")
        return None

    def _anthropic_base(self) -> str:
        if self.endpoint.endswith("/v1"):
            return self.endpoint
        return f"{self.endpoint}/v1"

    def _extract_content(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("Anthropic response was not a JSON object")
        content_blocks = payload.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise KeyError("Anthropic response missing content")
        parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        content = "\n".join(part.strip() for part in parts if part.strip()).strip()
        if not content:
            raise ValueError("Anthropic response contained empty text content")
        return content


def provider_config_from_settings(settings: Settings) -> ProviderConfig:
    api = settings.aegis_model_api.strip().lower() or "ollama"
    endpoint = settings.aegis_model_endpoint.rstrip("/")
    model = settings.aegis_model_name.strip()
    return ProviderConfig(
        provider_id=f"{api}:active",
        label=provider_label(api, endpoint),
        api=api,
        endpoint=endpoint,
        model=model,
        local=is_local_endpoint(endpoint),
        secret_env=secret_env_name(api, endpoint),
        enabled=True,
        configured=bool(model),
        capabilities=provider_capability_tags(api, endpoint, model, ["chat", "code", "structured_json"]),
        roles=["chat", "code", "reasoning", "fallback"],
        cost_tier="low" if is_local_endpoint(endpoint) else "unknown",
    )


def provider_config_from_registry_provider(
    provider: ModelRegistryProvider,
    settings: Settings,
    *,
    model_hint: str = "",
) -> ProviderConfig:
    endpoint = provider.endpoint.rstrip("/") if provider.endpoint else settings.aegis_model_endpoint.rstrip("/")
    api = provider.api.strip().lower() or settings.aegis_model_api.strip().lower() or "ollama"
    settings_api = settings.aegis_model_api.strip().lower() or "ollama"
    settings_endpoint = settings.aegis_model_endpoint.rstrip("/")
    active_provider_id = f"{settings_api}:active"
    is_active_provider = (
        provider.id == active_provider_id
        or (api == settings_api and endpoint == settings_endpoint)
    )
    model = model_hint.strip() or provider.model_name.strip()
    if not model and is_active_provider:
        model = settings.aegis_model_name.strip()
    return ProviderConfig(
        provider_id=provider.id,
        label=provider.label or provider.id,
        api=api,
        endpoint=endpoint,
        model=model,
        local=provider.local,
        secret_env=provider.secret_env.strip() or secret_env_name(api, endpoint),
        enabled=provider.enabled,
        configured=provider.configured or bool(model),
        capabilities=provider.capabilities,
        roles=provider.roles,
        cost_tier=provider.cost_tier,
        context_window=provider.context_window,
        rate_limit_rpm=provider.rate_limit_rpm,
        input_cost_per_million=provider.input_cost_per_million,
        output_cost_per_million=provider.output_cost_per_million,
    )


def provider_config_from_attempt(
    attempt: ModelAttemptInfo,
    settings: Settings,
    provider: ModelRegistryProvider | None = None,
) -> ProviderConfig:
    if provider is not None:
        return provider_config_from_registry_provider(provider, settings, model_hint=attempt.model)

    api = attempt.provider_api.strip().lower() or settings.aegis_model_api.strip().lower() or "ollama"
    endpoint = attempt.endpoint.rstrip("/") if attempt.endpoint else settings.aegis_model_endpoint.rstrip("/")
    model = attempt.model.strip() or settings.aegis_model_name.strip()
    return ProviderConfig(
        provider_id=attempt.provider_id or f"{api}:attempt",
        label=attempt.provider_label or provider_label(api, endpoint),
        api=api,
        endpoint=endpoint,
        model=model,
        local=is_local_endpoint(endpoint),
        secret_env=secret_env_name(api, endpoint),
        enabled=True,
        configured=bool(model),
        capabilities=list(attempt.metadata.get("required_capabilities", []))
        if isinstance(attempt.metadata.get("required_capabilities"), list)
        else [],
        roles=[attempt.role] if attempt.role else [],
    )


def build_provider_adapter(settings: Settings, config: ProviderConfig | None = None) -> ProviderAdapter:
    provider_config = config or provider_config_from_settings(settings)
    family = api_family(provider_config.api)
    if family == "ollama":
        return OllamaProviderAdapter(settings, provider_config)
    if family == "openai":
        return OpenAICompatibleProviderAdapter(settings, provider_config)
    if family == "anthropic":
        return AnthropicProviderAdapter(settings, provider_config)
    return UnsupportedProviderAdapter(settings, provider_config)
