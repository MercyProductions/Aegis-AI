from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.model_registry import ModelRegistryManager
from aegis_ai.schemas import (
    ModelBenchmarkProviderScore,
    ModelAttemptInfo,
    ModelAttemptTelemetryEntry,
    ModelRegistryProviderUpsertRequest,
    ModelRouteHealthInfo,
    RoutePolicyDiffResponse,
    RoutePolicyProviderProposal,
    RoutePolicyRoleProposal,
)
from aegis_ai.settings import Settings


class ModelRegistryTests(unittest.TestCase):
    def test_apply_benchmark_winners_updates_roles_and_provider_traits(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:qwen-code",
                    label="Qwen Code",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="qwen2.5-coder:7b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat", "fallback"],
                )
            )

            snapshot = manager.apply_benchmark_winners(
                [
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:qwen-code",
                        provider_label="Qwen Code",
                        api="ollama",
                        model_name="qwen2.5-coder:7b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.93,
                        chat_score=0.88,
                        code_score=0.96,
                        reasoning_score=0.78,
                        avg_latency_ms=1200,
                        run_count=3,
                    )
                ]
            )

        role_by_id = {role.id: role for role in snapshot.roles}
        provider = next(item for item in snapshot.providers if item.id == "ollama:qwen-code")
        self.assertEqual(role_by_id["code"].primary_model, "qwen2.5-coder:7b")
        self.assertIn("qwen2.5-coder:7b", role_by_id["code"].fallback_models)
        self.assertIn("code", provider.roles)
        self.assertIn("structured_json", provider.capabilities)
        self.assertTrue(snapshot.router_enabled)

    def test_apply_benchmark_winners_demotes_cooled_down_route(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:fast-chat",
                    label="Fast Chat",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="codegemma:2b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:steady-chat",
                    label="Steady Chat",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="llama3.2:3b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )

            snapshot = manager.apply_benchmark_winners(
                [
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:fast-chat",
                        provider_label="Fast Chat",
                        api="ollama",
                        model_name="codegemma:2b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.96,
                        chat_score=0.97,
                        avg_latency_ms=900,
                        run_count=4,
                    ),
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:steady-chat",
                        provider_label="Steady Chat",
                        api="ollama",
                        model_name="llama3.2:3b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.86,
                        chat_score=0.86,
                        avg_latency_ms=1200,
                        run_count=4,
                    ),
                ],
                route_health=[
                    ModelRouteHealthInfo(
                        provider_id="ollama:fast-chat",
                        provider_label="Fast Chat",
                        model="codegemma:2b",
                        role="chat",
                        terminal_attempts=3,
                        failures=3,
                        failure_rate=1.0,
                        penalty=6000.0,
                        cooldown=True,
                        recommendation="Cooldown after repeated failures.",
                    )
                ],
            )

        role_by_id = {role.id: role for role in snapshot.roles}
        self.assertEqual(role_by_id["chat"].primary_model, "llama3.2:3b")
        self.assertNotIn("codegemma:2b", role_by_id["chat"].fallback_models)
        self.assertIn("health-aware", snapshot.message)

    def test_preview_benchmark_winners_does_not_mutate_registry_file(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:qwen-code",
                    label="Qwen Code",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="qwen2.5-coder:7b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat", "fallback"],
                )
            )
            before = manager.registry_path.read_text(encoding="utf-8")

            preview = manager.preview_benchmark_winners(
                [
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:qwen-code",
                        provider_label="Qwen Code",
                        api="ollama",
                        model_name="qwen2.5-coder:7b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.93,
                        chat_score=0.88,
                        code_score=0.96,
                        reasoning_score=0.78,
                        avg_latency_ms=1200,
                        run_count=3,
                    )
                ]
            )
            after = manager.registry_path.read_text(encoding="utf-8")

        self.assertTrue(preview.applicable)
        self.assertEqual(before, after)
        self.assertTrue(any(diff.role == "code" and diff.action == "switch_primary" for diff in preview.role_diffs))

    def test_preview_benchmark_winners_demotes_cooled_down_route(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:fast-chat",
                    label="Fast Chat",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="codegemma:2b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:steady-chat",
                    label="Steady Chat",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="llama3.2:3b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )

            preview = manager.preview_benchmark_winners(
                [
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:fast-chat",
                        provider_label="Fast Chat",
                        api="ollama",
                        model_name="codegemma:2b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.96,
                        chat_score=0.97,
                        avg_latency_ms=900,
                        run_count=4,
                    ),
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:steady-chat",
                        provider_label="Steady Chat",
                        api="ollama",
                        model_name="llama3.2:3b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.86,
                        chat_score=0.86,
                        avg_latency_ms=1200,
                        run_count=4,
                    ),
                ],
                route_health=[
                    ModelRouteHealthInfo(
                        provider_id="ollama:fast-chat",
                        provider_label="Fast Chat",
                        model="codegemma:2b",
                        role="chat",
                        terminal_attempts=3,
                        failures=3,
                        failure_rate=1.0,
                        penalty=6000.0,
                        cooldown=True,
                        recommendation="Cooldown after repeated failures.",
                    )
                ],
            )

        chat_diff = next(diff for diff in preview.role_diffs if diff.role == "chat")
        self.assertTrue(preview.applicable)
        self.assertEqual(chat_diff.proposed_primary_model, "llama3.2:3b")
        self.assertNotIn("codegemma:2b", chat_diff.proposed_fallback_models)
        self.assertIn(chat_diff.action, {"keep", "switch_primary", "update_fallbacks"})

    def test_registry_checkpoints_restore_previous_provider_state(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Original Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="original-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Changed Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="changed-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "reasoning"],
                    roles=["chat", "reasoning"],
                )
            )

            checkpoints = manager.checkpoints(limit=5).checkpoints
            restored = manager.restore_checkpoint(checkpoints[0].id)

        provider = next(item for item in restored.providers if item.id == "cloud:test")
        self.assertGreaterEqual(len(checkpoints), 2)
        self.assertEqual(provider.label, "Original Provider")
        self.assertEqual(provider.model_name, "original-model")
        self.assertIn("Restored model registry checkpoint", restored.message)

    def test_manual_registry_checkpoint_creates_baseline_without_mutation(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            before = manager.snapshot()
            checkpoint = manager.create_checkpoint("Baseline before provider experiments.")
            after = manager.snapshot()
            checkpoints = manager.checkpoints(limit=5).checkpoints

        self.assertEqual(checkpoint.reason, "Baseline before provider experiments.")
        self.assertEqual(checkpoint.provider_count, len(before.providers))
        self.assertEqual(checkpoint.role_count, len(before.roles))
        self.assertEqual(before.active_provider_id, after.active_provider_id)
        self.assertEqual(len(before.providers), len(after.providers))
        self.assertEqual(checkpoints[0].id, checkpoint.id)
        self.assertEqual(checkpoint.restore_total_change_count, 0)
        self.assertEqual(checkpoint.restore_summary, "Matches current registry.")

    def test_registry_audit_reports_route_coverage_and_provider_issues(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:missing-secret",
                    label="Missing Secret",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="secret-model",
                    secret_env="AEGIS_TEST_PROVIDER_KEY",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "research"],
                    roles=["chat", "research"],
                )
            )
            audit = manager.audit()

        chat_coverage = next(route for route in audit.route_coverages if route.role == "chat")
        self.assertGreaterEqual(audit.provider_count, 1)
        self.assertGreaterEqual(audit.configured_provider_count, 1)
        self.assertGreaterEqual(chat_coverage.configured_provider_count, 1)
        self.assertTrue(any(issue.category == "provider_secret" for issue in audit.issues))
        secret_actions = [action for action in audit.setup_actions if action.kind == "secret"]
        self.assertTrue(secret_actions)
        self.assertEqual(secret_actions[0].env_var, "AEGIS_TEST_PROVIDER_KEY")
        self.assertIn("SetEnvironmentVariable", secret_actions[0].command)
        self.assertIn("cloud:missing-secret", secret_actions[0].provider_ids)
        self.assertIn(audit.status, {"ready", "attention", "blocked"})

    def test_registry_audit_includes_adapter_health_from_preflight_and_route_telemetry(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:missing-secret",
                    label="Missing Secret",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="secret-model",
                    secret_env="AEGIS_TEST_PROVIDER_KEY",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:unstable",
                    label="Unstable Local",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="unstable:latest",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                    context_window=8192,
                )
            )
            attempts = [
                ModelAttemptTelemetryEntry(
                    task_id="task-1",
                    created_at="2026-04-29T00:00:00Z",
                    workspace_root=str(Path(temp_dir).resolve()),
                    attempt=ModelAttemptInfo(
                        attempt=1,
                        role="chat",
                        provider_id="cloud:missing-secret",
                        provider_label="Missing Secret",
                        provider_api="openai-compatible",
                        model="secret-model",
                        status="skipped",
                        error="Missing Secret requires AEGIS_TEST_PROVIDER_KEY before it can execute.",
                        retryable=False,
                        metadata={"preflight": True, "error_code": "missing_provider_secret"},
                    ),
                ),
                ModelAttemptTelemetryEntry(
                    task_id="task-2",
                    created_at="2026-04-29T00:02:00Z",
                    workspace_root=str(Path(temp_dir).resolve()),
                    attempt=ModelAttemptInfo(
                        attempt=1,
                        role="chat",
                        provider_id="ollama:unstable",
                        provider_label="Unstable Local",
                        provider_api="ollama",
                        model="unstable:latest",
                        status="succeeded",
                        input_tokens=3200,
                        output_tokens=120,
                        metadata={
                            "token_estimator_family": "local_open_weights",
                            "token_estimate_source": "provider_profile",
                            "estimated_input_tokens": 3200,
                            "estimated_output_tokens": 120,
                            "reported_input_tokens": 3000,
                            "reported_output_tokens": 118,
                            "reported_token_source": "ollama:chat",
                            "context_window": 8192,
                            "context_window_utilization": 0.405,
                        },
                    ),
                ),
            ]
            route_health = [
                ModelRouteHealthInfo(
                    provider_id="ollama:unstable",
                    provider_label="Unstable Local",
                    model="unstable:latest",
                    role="chat",
                    attempts=4,
                    terminal_attempts=4,
                    failures=4,
                    failure_rate=1.0,
                    cooldown=True,
                    latest_error="Connection refused",
                    latest_at="2026-04-29T00:01:00Z",
                )
            ]
            audit = manager.audit(model_attempts=attempts, route_health=route_health)

        health_by_id = {item.provider_id: item for item in audit.adapter_health}
        self.assertEqual(health_by_id["cloud:missing-secret"].status, "missing_secret")
        self.assertEqual(health_by_id["cloud:missing-secret"].preflight_skips, 1)
        self.assertEqual(health_by_id["cloud:missing-secret"].secret_env, "AEGIS_TEST_PROVIDER_KEY")
        self.assertEqual(health_by_id["ollama:unstable"].status, "cooldown")
        self.assertTrue(health_by_id["ollama:unstable"].cooldown)
        self.assertIn("Connection refused", health_by_id["ollama:unstable"].latest_error)
        tokenizer_by_id = {item.provider_id: item for item in audit.tokenizer_diagnostics}
        self.assertEqual(tokenizer_by_id["ollama:unstable"].status, "profiled")
        self.assertEqual(tokenizer_by_id["ollama:unstable"].profiled_attempts, 1)
        self.assertEqual(tokenizer_by_id["ollama:unstable"].context_window, 8192)
        self.assertAlmostEqual(tokenizer_by_id["ollama:unstable"].average_context_utilization, 0.405)
        self.assertEqual(tokenizer_by_id["ollama:unstable"].calibration_status, "stable")
        self.assertEqual(tokenizer_by_id["ollama:unstable"].calibrated_attempts, 1)
        self.assertIn("ollama:chat", tokenizer_by_id["ollama:unstable"].reported_token_sources)
        self.assertAlmostEqual(tokenizer_by_id["ollama:unstable"].average_input_token_error or 0.0, 200 / 3000)
        self.assertEqual(tokenizer_by_id["cloud:missing-secret"].status, "missing")
        self.assertEqual(tokenizer_by_id["cloud:missing-secret"].calibration_status, "insufficient")

    def test_apply_policy_diff_updates_safe_route_primary_and_provider_traits(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:qwen-code",
                    label="Qwen Code",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="qwen2.5-coder:7b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            snapshot = manager.apply_policy_diff(
                RoutePolicyDiffResponse(
                    workspace_root=str(Path(temp_dir).resolve()),
                    generated_at="2026-04-29T00:00:00Z",
                    limit=50,
                    provider_proposals=[
                        RoutePolicyProviderProposal(
                            provider_id="ollama:qwen-code",
                            provider_label="Qwen Code",
                            provider_api="ollama",
                            model="qwen2.5-coder:7b",
                            action="promote",
                            risk_level="low",
                            confidence=0.88,
                            attempts=10,
                            success_rate=0.9,
                        )
                    ],
                    role_proposals=[
                        RoutePolicyRoleProposal(
                            role="code",
                            action="switch_primary",
                            observed_primary_provider="old-provider",
                            proposed_primary_provider="ollama:qwen-code",
                            confidence=0.9,
                            attempts=12,
                            success_rate=0.92,
                            candidate_provider_ids=["ollama:qwen-code"],
                            reasons=["Qwen Code has better recent code-route reliability."],
                        )
                    ],
                ),
                min_confidence=0.55,
            )

        role_by_id = {role.id: role for role in snapshot.roles}
        provider = next(item for item in snapshot.providers if item.id == "ollama:qwen-code")
        self.assertEqual(role_by_id["code"].primary_model, "qwen2.5-coder:7b")
        self.assertIn("qwen2.5-coder:7b", role_by_id["code"].fallback_models)
        self.assertIn("code", provider.roles)
        self.assertIn("structured_json", provider.capabilities)
        self.assertTrue(snapshot.router_enabled)
        self.assertIn("Applied safe route policy diff", snapshot.message)

    def test_registry_checkpoint_reports_restore_impact(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Original Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="original-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            baseline = manager.create_checkpoint("Baseline before routing experiment.")
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Changed Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="changed-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "reasoning"],
                    roles=["chat", "reasoning"],
                )
            )

            checkpoint = next(item for item in manager.checkpoints(limit=10).checkpoints if item.id == baseline.id)

        self.assertEqual(checkpoint.restore_provider_change_count, 1)
        self.assertEqual(checkpoint.restore_total_change_count, 1)
        self.assertIn("providers +0/-0/~1", checkpoint.restore_summary)

    def test_registry_checkpoint_diff_lists_changed_provider_names(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Original Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="original-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat"],
                    roles=["chat"],
                )
            )
            baseline = manager.create_checkpoint("Baseline before provider rename.")
            manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="cloud:test",
                    label="Changed Provider",
                    api="openai-compatible",
                    endpoint="https://example.invalid/v1",
                    model_name="changed-model",
                    local=False,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "reasoning"],
                    roles=["chat", "reasoning"],
                )
            )

            diff = manager.checkpoint_diff(baseline.id)

        provider_diff = next(item for item in diff.provider_diffs if item.id == "cloud:test")
        self.assertEqual(provider_diff.action, "change_on_restore")
        self.assertIn("Changed Provider", provider_diff.current_summary)
        self.assertIn("Original Provider", provider_diff.checkpoint_summary)
        self.assertEqual(diff.checkpoint.restore_total_change_count, 1)


if __name__ == "__main__":
    unittest.main()
