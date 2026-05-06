from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .model_execution import ModelExecutionPlan
from .providers import ProviderError, build_provider_adapter, provider_config_from_attempt
from .providers.base import ProviderConfig, api_family, extract_json_object, secret_env_name, secret_value
from .schemas import ModelAttemptInfo, ModelRegistryProvider
from .settings import Settings
from .structured_streaming import StructuredReplyDeltaExtractor


@dataclass(frozen=True)
class ModelAttemptExecution:
    payload: dict[str, Any] | None = None
    attempts: list[ModelAttemptInfo] = field(default_factory=list)
    succeeded: bool = False
    error: str = ""


class ModelAttemptExecutor:
    """Executes a planned non-streaming model fallback chain.

    This service is intentionally separate from AgentEngine so fallback execution can
    be introduced behind a feature flag or route policy without reshaping chat flow.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        plan: ModelExecutionPlan,
        providers: list[ModelRegistryProvider],
    ) -> ModelAttemptExecution:
        executed: list[ModelAttemptInfo] = []
        provider_lookup = {provider.id: provider for provider in providers}

        for planned in plan.attempts:
            if planned.provider_api in {"internal", "router"} or not planned.retryable:
                executed.append(
                    planned.model_copy(
                        update={
                            "status": "skipped",
                            "reason": planned.reason or "No executable provider adapter is available for this planned attempt.",
                            "finished_at": self._now(),
                        }
                    )
                )
                continue

            provider = provider_lookup.get(planned.provider_id)
            config = provider_config_from_attempt(planned, self.settings, provider)
            preflight_issue = self._preflight_issue(config)
            if preflight_issue is not None:
                executed.append(
                    planned.model_copy(
                        update={
                            "status": "skipped",
                            "provider_id": config.provider_id,
                            "provider_label": config.label,
                            "provider_api": config.api,
                            "endpoint": config.endpoint,
                            "model": config.model,
                            "error": preflight_issue["message"],
                            "retryable": False,
                            "finished_at": self._now(),
                            "metadata": {
                                **planned.metadata,
                                "registry_resolved": provider is not None,
                                "preflight": True,
                                "error_code": preflight_issue["code"],
                                "secret_env": preflight_issue.get("secret_env", ""),
                            },
                        }
                    )
                )
                continue

            adapter = build_provider_adapter(self.settings, config)
            started = self._now()
            start_time = time.perf_counter()
            running = planned.model_copy(
                update={
                    "status": "running",
                    "provider_id": config.provider_id,
                    "provider_label": config.label,
                    "provider_api": config.api,
                    "endpoint": config.endpoint,
                    "model": config.model,
                    "started_at": started,
                    "metadata": {
                        **planned.metadata,
                        "registry_resolved": provider is not None,
                        "adapter": adapter.__class__.__name__,
                    },
                }
            )

            try:
                payload = await adapter.complete_json(messages)
            except ProviderError as exc:
                executed.append(
                    running.model_copy(
                        update={
                            "status": "failed",
                            "error": exc.safe_message,
                            "retryable": exc.retryable,
                            "latency_ms": self._elapsed_ms(start_time),
                            "finished_at": self._now(),
                            "metadata": {
                                **running.metadata,
                                "error_code": exc.code,
                                "status_code": exc.status_code,
                                "developer_error": exc.message,
                            },
                        }
                    )
                )
                if not exc.retryable:
                    continue
                continue
            except Exception as exc:
                executed.append(
                    running.model_copy(
                        update={
                            "status": "failed",
                            "error": "Provider attempt failed before returning a usable response.",
                            "retryable": True,
                            "latency_ms": self._elapsed_ms(start_time),
                            "finished_at": self._now(),
                            "metadata": {
                                **running.metadata,
                                "error_code": "unexpected_provider_error",
                                "developer_error": str(exc),
                            },
                        }
                    )
                )
                continue

            executed.append(
                running.model_copy(
                    update={
                        "status": "succeeded",
                        "latency_ms": self._elapsed_ms(start_time),
                        "finished_at": self._now(),
                        "metadata": {
                            **running.metadata,
                            **self._completion_metadata(adapter),
                        },
                    }
                )
            )
            return ModelAttemptExecution(payload=payload, attempts=executed, succeeded=True)

        return ModelAttemptExecution(
            payload=None,
            attempts=executed,
            succeeded=False,
            error="All planned model attempts failed or were skipped.",
        )

    async def stream_json(
        self,
        *,
        messages: list[dict[str, str]],
        plan: ModelExecutionPlan,
        providers: list[ModelRegistryProvider],
        on_preview_delta: Callable[[dict[str, Any]], None] | None = None,
    ) -> ModelAttemptExecution:
        executed: list[ModelAttemptInfo] = []
        provider_lookup = {provider.id: provider for provider in providers}

        for planned in plan.attempts:
            if planned.provider_api in {"internal", "router"} or not planned.retryable:
                executed.append(
                    planned.model_copy(
                        update={
                            "status": "skipped",
                            "reason": planned.reason or "No executable provider adapter is available for this planned attempt.",
                            "finished_at": self._now(),
                        }
                    )
                )
                continue

            provider = provider_lookup.get(planned.provider_id)
            config = provider_config_from_attempt(planned, self.settings, provider)
            preflight_issue = self._preflight_issue(config)
            if preflight_issue is not None:
                executed.append(
                    planned.model_copy(
                        update={
                            "status": "skipped",
                            "provider_id": config.provider_id,
                            "provider_label": config.label,
                            "provider_api": config.api,
                            "endpoint": config.endpoint,
                            "model": config.model,
                            "error": preflight_issue["message"],
                            "retryable": False,
                            "finished_at": self._now(),
                            "metadata": {
                                **planned.metadata,
                                "registry_resolved": provider is not None,
                                "preflight": True,
                                "error_code": preflight_issue["code"],
                                "secret_env": preflight_issue.get("secret_env", ""),
                            },
                        }
                    )
                )
                continue

            adapter = build_provider_adapter(self.settings, config)
            started = self._now()
            start_time = time.perf_counter()
            running = planned.model_copy(
                update={
                    "status": "running",
                    "provider_id": config.provider_id,
                    "provider_label": config.label,
                    "provider_api": config.api,
                    "endpoint": config.endpoint,
                    "model": config.model,
                    "started_at": started,
                    "metadata": {
                        **planned.metadata,
                        "registry_resolved": provider is not None,
                        "adapter": adapter.__class__.__name__,
                        "streamed_structured_preview": on_preview_delta is not None,
                    },
                }
            )

            content_parts: list[str] = []
            extractor = StructuredReplyDeltaExtractor()
            preview_emitted = False
            preview_delta_count = 0
            preview_char_count = 0
            preview_reset_count = 0
            preview_retired_reason = ""
            preview_base = {
                "preview_attempt": planned.attempt,
                "provider_id": config.provider_id,
                "provider_label": config.label,
                "provider_api": config.api,
                "model": config.model,
            }
            try:
                async for event in adapter.stream_text(messages, structured_json=True):
                    if event.type == "delta" and event.delta:
                        content_parts.append(event.delta)
                        preview = extractor.feed(event.delta)
                        if preview and on_preview_delta is not None:
                            preview_emitted = True
                            preview_delta_count += 1
                            preview_char_count += len(preview)
                            on_preview_delta(
                                {
                                    **preview_base,
                                    "preview_action": "append",
                                    "delta": preview,
                                }
                            )
            except ProviderError as exc:
                if preview_emitted and on_preview_delta is not None:
                    preview_reset_count += 1
                    preview_retired_reason = "provider_error"
                    on_preview_delta(
                        {
                            **preview_base,
                            "preview_action": "reset",
                            "delta": "",
                            "message": f"{config.label or config.provider_id} preview was retired because the attempt failed.",
                        }
                    )
                executed.append(
                    running.model_copy(
                        update={
                            "status": "failed",
                            "error": exc.safe_message,
                            "retryable": exc.retryable,
                            "latency_ms": self._elapsed_ms(start_time),
                            "finished_at": self._now(),
                            "metadata": {
                                **running.metadata,
                                "error_code": exc.code,
                                "status_code": exc.status_code,
                                "developer_error": exc.message,
                                **self._structured_preview_metadata(
                                    delta_count=preview_delta_count,
                                    char_count=preview_char_count,
                                    reset_count=preview_reset_count,
                                    final_winner=False,
                                    retired_reason=preview_retired_reason,
                                ),
                            },
                        }
                    )
                )
                continue
            except Exception as exc:
                if preview_emitted and on_preview_delta is not None:
                    preview_reset_count += 1
                    preview_retired_reason = "unexpected_stream_error"
                    on_preview_delta(
                        {
                            **preview_base,
                            "preview_action": "reset",
                            "delta": "",
                            "message": f"{config.label or config.provider_id} preview was retired because the attempt failed.",
                        }
                    )
                executed.append(
                    running.model_copy(
                        update={
                            "status": "failed",
                            "error": "Provider stream failed before returning a usable response.",
                            "retryable": True,
                            "latency_ms": self._elapsed_ms(start_time),
                            "finished_at": self._now(),
                            "metadata": {
                                **running.metadata,
                                "error_code": "unexpected_provider_stream_error",
                                "developer_error": str(exc),
                                **self._structured_preview_metadata(
                                    delta_count=preview_delta_count,
                                    char_count=preview_char_count,
                                    reset_count=preview_reset_count,
                                    final_winner=False,
                                    retired_reason=preview_retired_reason,
                                ),
                            },
                        }
                    )
                )
                continue

            try:
                payload = extract_json_object("".join(content_parts))
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                if preview_emitted and on_preview_delta is not None:
                    preview_reset_count += 1
                    preview_retired_reason = "invalid_structured_json"
                    on_preview_delta(
                        {
                            **preview_base,
                            "preview_action": "reset",
                            "delta": "",
                            "message": f"{config.label or config.provider_id} preview was retired because the stream did not produce valid structured JSON.",
                        }
                    )
                executed.append(
                    running.model_copy(
                        update={
                            "status": "failed",
                            "error": "Provider stream did not contain a usable structured response.",
                            "retryable": False,
                            "latency_ms": self._elapsed_ms(start_time),
                            "finished_at": self._now(),
                            "metadata": {
                                **running.metadata,
                                "error_code": "provider_invalid_stream_response",
                                "developer_error": str(exc),
                                **self._structured_preview_metadata(
                                    delta_count=preview_delta_count,
                                    char_count=preview_char_count,
                                    reset_count=preview_reset_count,
                                    final_winner=False,
                                    retired_reason=preview_retired_reason,
                                ),
                            },
                        }
                    )
                )
                continue

            executed.append(
                running.model_copy(
                    update={
                        "status": "succeeded",
                        "latency_ms": self._elapsed_ms(start_time),
                        "finished_at": self._now(),
                        "metadata": {
                            **running.metadata,
                            **self._completion_metadata(adapter),
                            **self._structured_preview_metadata(
                                delta_count=preview_delta_count,
                                char_count=preview_char_count,
                                reset_count=preview_reset_count,
                                final_winner=True,
                                retired_reason=preview_retired_reason,
                            ),
                        },
                    }
                )
            )
            return ModelAttemptExecution(payload=payload, attempts=executed, succeeded=True)

        return ModelAttemptExecution(
            payload=None,
            attempts=executed,
            succeeded=False,
            error="All planned model stream attempts failed or were skipped.",
        )

    def _structured_preview_metadata(
        self,
        *,
        delta_count: int,
        char_count: int,
        reset_count: int,
        final_winner: bool,
        retired_reason: str = "",
    ) -> dict[str, Any]:
        return {
            "structured_preview_delta_count": max(0, delta_count),
            "structured_preview_char_count": max(0, char_count),
            "structured_preview_reset_count": max(0, reset_count),
            "structured_preview_emitted": delta_count > 0,
            "structured_preview_retired": reset_count > 0,
            "structured_preview_final_winner": final_winner,
            "structured_preview_retired_reason": retired_reason,
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _elapsed_ms(self, start_time: float) -> int:
        return max(0, int((time.perf_counter() - start_time) * 1000))

    def _completion_metadata(self, adapter: Any) -> dict[str, Any]:
        metadata_fn = getattr(adapter, "completion_metadata", None)
        if not callable(metadata_fn):
            return {}
        try:
            metadata = metadata_fn()
        except Exception:
            return {}
        return metadata if isinstance(metadata, dict) else {}

    def _preflight_issue(self, config: ProviderConfig) -> dict[str, str] | None:
        if not config.enabled:
            return {
                "code": "provider_disabled",
                "message": f"{config.label or config.provider_id} is disabled in the provider registry.",
            }
        if not config.model.strip():
            return {
                "code": "model_not_configured",
                "message": f"{config.label or config.provider_id} does not have a model configured.",
            }

        family = api_family(config.api)
        if family == "unsupported":
            return {
                "code": "unsupported_provider_api",
                "message": f"{config.label or config.provider_id} uses unsupported provider API '{config.api}'.",
            }

        if not config.local:
            env_name = config.secret_env.strip() or secret_env_name(config.api, config.endpoint)
            if env_name and not secret_value(env_name):
                return {
                    "code": "missing_provider_secret",
                    "message": f"{config.label or config.provider_id} requires {env_name} before it can execute.",
                    "secret_env": env_name,
                }
        return None
