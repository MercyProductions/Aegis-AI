from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.model_attempt_executor import ModelAttemptExecutor
from aegis_ai.model_execution import ModelExecutionPlan, ModelExecutionPlanner
from aegis_ai.providers.base import ProviderStreamEvent
from aegis_ai.routing import RouteCandidate, RoutingDecision
from aegis_ai.schemas import ModelAttemptInfo, ModelBenchmarkProviderScore, ModelRegistryProvider, ModelRegistryRole, ModelRouteHealthInfo
from aegis_ai.settings import Settings
from aegis_ai.task_planner import TaskPlan


class ModelExecutionPlannerTests(unittest.TestCase):
    def test_benchmark_scores_can_promote_best_chat_provider(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="ollama:qwen-coder",
                label="Qwen Coder",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="qwen2.5-coder:7b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "code", "structured_json"],
                roles=["chat", "code", "fallback"],
            ),
            ModelRegistryProvider(
                id="ollama:llama-chat",
                label="Llama Chat",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="llama3.2:3b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "structured_json"],
                roles=["chat", "fallback"],
            ),
        ]
        benchmarks = [
            ModelBenchmarkProviderScore(
                provider_id="ollama:qwen-coder",
                provider_label="Qwen Coder",
                api="ollama",
                model_name="qwen2.5-coder:7b",
                overall_score=0.96,
                chat_score=0.98,
                avg_latency_ms=1200,
                run_count=3,
            ),
            ModelBenchmarkProviderScore(
                provider_id="ollama:llama-chat",
                provider_label="Llama Chat",
                api="ollama",
                model_name="llama3.2:3b",
                overall_score=0.30,
                chat_score=0.25,
                avg_latency_ms=900,
                run_count=3,
            ),
        ]
        plan = TaskPlan(
            intent="conversation",
            objective="count to 10 starting at 11",
            workflow="answer-clarify",
            routing=RoutingDecision(
                task_role="chat",
                privacy_mode="local-first",
                candidates=[
                    RouteCandidate(
                        role="chat",
                        provider_hint="fast configured chat lane",
                        required_capabilities=["chat"],
                        privacy_mode="local-first",
                        reason="Pick the best chat route.",
                        confidence=0.8,
                        candidate_id="primary:chat",
                    )
                ],
                fallback_roles=["chat", "fallback"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers, benchmark_scores=benchmarks)

        self.assertEqual(execution.primary.model, "qwen2.5-coder:7b")
        self.assertEqual(execution.primary.metadata["benchmark_suite"], "chat")
        self.assertAlmostEqual(execution.primary.metadata["benchmark_suite_score"], 0.98)

    def test_registry_role_primary_model_is_honored_before_keyword_defaults(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="ollama:codegemma",
                label="CodeGemma",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="codegemma:2b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "code", "structured_json"],
                roles=["chat", "code", "fallback"],
            ),
            ModelRegistryProvider(
                id="ollama:llama-chat",
                label="Llama Chat",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="llama3.2:3b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "structured_json"],
                roles=["chat", "fallback"],
            ),
        ]
        roles = [
            ModelRegistryRole(
                id="chat",
                label="General Chat",
                description="Benchmark-ranked chat route.",
                primary_model="codegemma:2b",
                fallback_models=["llama3.2:3b"],
                required_capabilities=["chat"],
                privacy_mode="local-first",
                status="active",
            )
        ]
        plan = TaskPlan(
            intent="conversation",
            objective="answer a general question",
            workflow="answer-clarify",
            routing=RoutingDecision(
                task_role="chat",
                privacy_mode="local-first",
                candidates=[
                    RouteCandidate(
                        role="chat",
                        provider_hint="best chat lane",
                        required_capabilities=["chat"],
                        privacy_mode="local-first",
                        reason="Use the configured chat role.",
                        confidence=0.8,
                        candidate_id="primary:chat",
                    )
                ],
                fallback_roles=["chat"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers, roles=roles)

        self.assertEqual(execution.primary.model, "codegemma:2b")
        self.assertEqual(execution.primary.metadata["registry_role_primary_model"], "codegemma:2b")

    def test_registry_role_primary_overrides_active_provider_hint(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="ollama:qwen2.5-coder:7b",
                label="Active Coder",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="qwen2.5-coder:7b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "code", "structured_json"],
                roles=["code", "fallback"],
            ),
            ModelRegistryProvider(
                id="ollama:codegemma",
                label="CodeGemma",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="codegemma:2b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "structured_json"],
                roles=["chat", "fallback"],
            ),
        ]
        roles = [
            ModelRegistryRole(
                id="chat",
                label="General Chat",
                description="Benchmark-ranked chat route.",
                primary_model="codegemma:2b",
                fallback_models=["qwen2.5-coder:7b"],
                required_capabilities=["chat"],
                privacy_mode="local-first",
                status="active",
            )
        ]
        plan = TaskPlan(
            intent="conversation",
            objective="count to 10 starting at 11",
            workflow="answer-clarify",
            routing=RoutingDecision(
                task_role="chat",
                privacy_mode="local-first",
                candidates=[
                    RouteCandidate(
                        role="chat",
                        provider_hint="ollama:qwen2.5-coder:7b",
                        required_capabilities=["chat"],
                        privacy_mode="local-first",
                        reason="Configured active model.",
                        confidence=0.8,
                        candidate_id="primary:chat",
                    )
                ],
                fallback_roles=["chat", "fallback"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers, roles=roles)

        self.assertEqual(execution.primary.model, "codegemma:2b")
        self.assertEqual(execution.primary.metadata["registry_role_primary_model"], "codegemma:2b")

    def test_unhealthy_registry_primary_is_demoted_to_fallback_model(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="ollama:codegemma",
                label="CodeGemma",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="codegemma:2b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "structured_json"],
                roles=["chat", "fallback"],
            ),
            ModelRegistryProvider(
                id="ollama:llama-chat",
                label="Llama Chat",
                api="ollama",
                endpoint="http://127.0.0.1:11434",
                model_name="llama3.2:3b",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "structured_json"],
                roles=["chat", "fallback"],
            ),
        ]
        roles = [
            ModelRegistryRole(
                id="chat",
                label="General Chat",
                description="Benchmark-ranked chat route.",
                primary_model="codegemma:2b",
                fallback_models=["llama3.2:3b"],
                required_capabilities=["chat"],
                privacy_mode="local-first",
                status="active",
            )
        ]
        health = [
            ModelRouteHealthInfo(
                provider_id="ollama:codegemma",
                provider_label="CodeGemma",
                model="codegemma:2b",
                role="chat",
                attempts=3,
                terminal_attempts=3,
                successes=1,
                failures=2,
                success_rate=0.3333,
                failure_rate=0.6667,
                penalty=6000.0,
                cooldown=True,
                recommendation="Cooldown active.",
            )
        ]
        plan = TaskPlan(
            intent="conversation",
            objective="answer a general question",
            workflow="answer-clarify",
            routing=RoutingDecision(
                task_role="chat",
                privacy_mode="local-first",
                candidates=[
                    RouteCandidate(
                        role="chat",
                        provider_hint="best chat lane",
                        required_capabilities=["chat"],
                        privacy_mode="local-first",
                        reason="Use the configured chat role.",
                        confidence=0.8,
                        candidate_id="primary:chat",
                    )
                ],
                fallback_roles=["chat"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers, roles=roles, route_health=health)

        self.assertEqual(execution.primary.model, "llama3.2:3b")
        self.assertNotEqual(execution.primary.model, "codegemma:2b")

    def test_primary_candidate_requires_all_meaningful_capabilities(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="openai-compatible:vision-lite",
                label="Vision Lite",
                api="openai-compatible",
                endpoint="http://127.0.0.1:1234/v1",
                model_name="vision-lite",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "vision", "structured_json"],
                roles=["vision", "fallback"],
            ),
            ModelRegistryProvider(
                id="openai-compatible:vision-tools",
                label="Vision Tools",
                api="openai-compatible",
                endpoint="http://127.0.0.1:1234/v1",
                model_name="vision-tools",
                local=True,
                enabled=True,
                configured=True,
                capabilities=["chat", "vision", "tools", "structured_json"],
                roles=["vision", "fallback"],
            ),
        ]
        plan = TaskPlan(
            intent="analysis",
            objective="inspect an image and call tools",
            workflow="inspect-then-act",
            routing=RoutingDecision(
                task_role="vision",
                privacy_mode="local-first",
                candidates=[
                    RouteCandidate(
                        role="vision",
                        provider_hint="best vision lane",
                        required_capabilities=["chat", "vision", "tools"],
                        privacy_mode="local-first",
                        reason="Needs image understanding and tool use.",
                        confidence=0.9,
                        candidate_id="primary:vision",
                    )
                ],
                fallback_roles=["vision"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers)

        self.assertEqual(execution.primary.model, "vision-tools")
        self.assertTrue(execution.primary.metadata["capability_match"])
        self.assertIn("tools", execution.primary.metadata["provider_capabilities"])

    def test_role_required_capabilities_filter_policy_primary(self) -> None:
        providers = [
            ModelRegistryProvider(
                id="cloud:vision-primary",
                label="Vision Primary",
                api="openai",
                endpoint="https://api.example.test/v1",
                model_name="vision-primary",
                local=False,
                enabled=True,
                configured=True,
                capabilities=["chat", "vision", "structured_json"],
                roles=["vision", "fallback"],
            ),
            ModelRegistryProvider(
                id="cloud:vision-tools",
                label="Vision Tools",
                api="openai",
                endpoint="https://api.example.test/v1",
                model_name="vision-tools",
                local=False,
                enabled=True,
                configured=True,
                capabilities=["chat", "vision", "tools", "structured_json"],
                roles=["vision", "fallback"],
            ),
        ]
        roles = [
            ModelRegistryRole(
                id="vision",
                label="Vision",
                description="Vision route that also needs tools.",
                primary_model="vision-primary",
                fallback_models=["vision-tools"],
                required_capabilities=["vision", "tools"],
                privacy_mode="cloud-allowed",
                status="active",
            )
        ]
        plan = TaskPlan(
            intent="analysis",
            objective="inspect an image and call tools",
            workflow="inspect-then-act",
            routing=RoutingDecision(
                task_role="vision",
                privacy_mode="cloud-allowed",
                candidates=[
                    RouteCandidate(
                        role="vision",
                        provider_hint="best vision lane",
                        required_capabilities=["chat"],
                        privacy_mode="cloud-allowed",
                        reason="Use the configured vision route.",
                        confidence=0.9,
                        candidate_id="primary:vision",
                    )
                ],
                fallback_roles=["vision"],
            ),
        )

        execution = ModelExecutionPlanner().build_plan(plan, providers=providers, roles=roles)

        self.assertEqual(execution.primary.model, "vision-tools")
        self.assertNotEqual(execution.primary.model, "vision-primary")

    def test_executor_preflight_skips_cloud_provider_missing_secret(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        provider = ModelRegistryProvider(
            id="openai:missing-secret",
            label="OpenAI Missing Secret",
            api="openai",
            endpoint="https://api.openai.com/v1",
            model_name="gpt-5-mini",
            secret_env="OPENAI_API_KEY",
            local=False,
            enabled=True,
            configured=True,
            capabilities=["chat", "tools", "structured_json"],
            roles=["chat", "fallback"],
        )
        plan = ModelExecutionPlan(
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id=provider.id,
                    provider_label=provider.label,
                    provider_api=provider.api,
                    model=provider.model_name,
                    endpoint=provider.endpoint,
                    privacy_mode="cloud-allowed",
                    status="planned",
                    reason="Try cloud chat.",
                    retryable=True,
                )
            ]
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            execution = asyncio.run(
                ModelAttemptExecutor(settings).complete_json(
                    messages=[{"role": "user", "content": "hello"}],
                    plan=plan,
                    providers=[provider],
                )
            )

        self.assertFalse(execution.succeeded)
        self.assertEqual(execution.attempts[0].status, "skipped")
        self.assertEqual(execution.attempts[0].metadata["error_code"], "missing_provider_secret")
        self.assertEqual(execution.attempts[0].metadata["secret_env"], "OPENAI_API_KEY")

    def test_executor_persists_provider_reported_token_usage(self) -> None:
        class FakeAdapter:
            async def complete_json(self, messages: list[dict[str, str]]) -> dict[str, object]:
                return {"ok": True}

            def completion_metadata(self) -> dict[str, object]:
                return {
                    "reported_input_tokens": 42,
                    "reported_output_tokens": 7,
                    "reported_total_tokens": 49,
                    "reported_token_source": "fake:usage",
                }

        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        provider = ModelRegistryProvider(
            id="ollama:test",
            label="Ollama Test",
            api="ollama",
            endpoint="http://127.0.0.1:11434",
            model_name="qwen2.5-coder:7b",
            local=True,
            enabled=True,
            configured=True,
            capabilities=["chat", "structured_json"],
            roles=["chat"],
        )
        plan = ModelExecutionPlan(
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id=provider.id,
                    provider_label=provider.label,
                    provider_api=provider.api,
                    model=provider.model_name,
                    endpoint=provider.endpoint,
                    privacy_mode="local-only",
                    status="planned",
                    reason="Try local chat.",
                    retryable=True,
                    metadata={"estimated_input_tokens": 45, "estimated_output_tokens": 8},
                )
            ]
        )

        with patch("aegis_ai.model_attempt_executor.build_provider_adapter", return_value=FakeAdapter()):
            execution = asyncio.run(
                ModelAttemptExecutor(settings).complete_json(
                    messages=[{"role": "user", "content": "hello"}],
                    plan=plan,
                    providers=[provider],
                )
            )

        self.assertTrue(execution.succeeded)
        self.assertEqual(execution.payload, {"ok": True})
        self.assertEqual(execution.attempts[0].status, "succeeded")
        self.assertEqual(execution.attempts[0].metadata["reported_input_tokens"], 42)
        self.assertEqual(execution.attempts[0].metadata["reported_output_tokens"], 7)
        self.assertEqual(execution.attempts[0].metadata["reported_token_source"], "fake:usage")

    def test_stream_executor_records_structured_preview_counters_for_winning_attempt(self) -> None:
        class FakeStreamingAdapter:
            async def stream_text(self, messages: list[dict[str, str]], *, structured_json: bool = False):
                self.structured_json = structured_json
                yield ProviderStreamEvent(type="start")
                yield ProviderStreamEvent(type="delta", delta='{"reply":"Hello')
                yield ProviderStreamEvent(type="delta", delta=' preview","changes":[]}')
                yield ProviderStreamEvent(type="done")

            def completion_metadata(self) -> dict[str, object]:
                return {"reported_output_tokens": 3}

        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        provider = ModelRegistryProvider(
            id="ollama:test",
            label="Ollama Test",
            api="ollama",
            endpoint="http://127.0.0.1:11434",
            model_name="qwen2.5-coder:7b",
            local=True,
            enabled=True,
            configured=True,
            capabilities=["chat", "structured_json", "streaming"],
            roles=["code"],
        )
        plan = ModelExecutionPlan(
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id=provider.id,
                    provider_label=provider.label,
                    provider_api=provider.api,
                    model=provider.model_name,
                    endpoint=provider.endpoint,
                    privacy_mode="local-only",
                    status="planned",
                    retryable=True,
                )
            ]
        )
        preview_events: list[dict[str, object]] = []

        with patch("aegis_ai.model_attempt_executor.build_provider_adapter", return_value=FakeStreamingAdapter()):
            execution = asyncio.run(
                ModelAttemptExecutor(settings).stream_json(
                    messages=[{"role": "user", "content": "hello"}],
                    plan=plan,
                    providers=[provider],
                    on_preview_delta=preview_events.append,
                )
            )

        metadata = execution.attempts[0].metadata
        self.assertTrue(execution.succeeded)
        self.assertEqual(execution.payload, {"reply": "Hello preview", "changes": []})
        self.assertEqual(metadata["structured_preview_delta_count"], 2)
        self.assertEqual(metadata["structured_preview_char_count"], len("Hello preview"))
        self.assertEqual(metadata["structured_preview_reset_count"], 0)
        self.assertTrue(metadata["structured_preview_emitted"])
        self.assertFalse(metadata["structured_preview_retired"])
        self.assertTrue(metadata["structured_preview_final_winner"])
        self.assertEqual(metadata["reported_output_tokens"], 3)
        self.assertTrue(all(event["preview_action"] == "append" for event in preview_events))
        self.assertEqual({event["preview_attempt"] for event in preview_events}, {1})

    def test_stream_executor_resets_and_records_retired_preview_for_invalid_json(self) -> None:
        class FakeInvalidStreamingAdapter:
            async def stream_text(self, messages: list[dict[str, str]], *, structured_json: bool = False):
                yield ProviderStreamEvent(type="start")
                yield ProviderStreamEvent(type="delta", delta='{"reply":"Old preview')
                yield ProviderStreamEvent(type="done")

            def completion_metadata(self) -> dict[str, object]:
                return {}

        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        provider = ModelRegistryProvider(
            id="ollama:test",
            label="Ollama Test",
            api="ollama",
            endpoint="http://127.0.0.1:11434",
            model_name="qwen2.5-coder:7b",
            local=True,
            enabled=True,
            configured=True,
            capabilities=["chat", "structured_json", "streaming"],
            roles=["code"],
        )
        plan = ModelExecutionPlan(
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id=provider.id,
                    provider_label=provider.label,
                    provider_api=provider.api,
                    model=provider.model_name,
                    endpoint=provider.endpoint,
                    privacy_mode="local-only",
                    status="planned",
                    retryable=True,
                )
            ]
        )
        preview_events: list[dict[str, object]] = []

        with patch("aegis_ai.model_attempt_executor.build_provider_adapter", return_value=FakeInvalidStreamingAdapter()):
            execution = asyncio.run(
                ModelAttemptExecutor(settings).stream_json(
                    messages=[{"role": "user", "content": "hello"}],
                    plan=plan,
                    providers=[provider],
                    on_preview_delta=preview_events.append,
                )
            )

        metadata = execution.attempts[0].metadata
        self.assertFalse(execution.succeeded)
        self.assertEqual(execution.attempts[0].status, "failed")
        self.assertEqual(metadata["structured_preview_delta_count"], 1)
        self.assertEqual(metadata["structured_preview_char_count"], len("Old preview"))
        self.assertEqual(metadata["structured_preview_reset_count"], 1)
        self.assertTrue(metadata["structured_preview_emitted"])
        self.assertTrue(metadata["structured_preview_retired"])
        self.assertFalse(metadata["structured_preview_final_winner"])
        self.assertEqual(metadata["structured_preview_retired_reason"], "invalid_structured_json")
        self.assertEqual(preview_events[-1]["preview_action"], "reset")


if __name__ == "__main__":
    unittest.main()
