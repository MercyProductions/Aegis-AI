from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import (
    FeedbackAttributionRollup,
    ModelAttemptInfo,
    ModelAttemptTelemetryEntry,
    RouteQualityOverview,
    RouteQualityProviderRollup,
    RouteQualityResponse,
    RouteQualityRoleRollup,
)
from aegis_ai.storage_route_policy import (
    route_policy_provider_proposals,
    route_policy_recommendations,
    route_policy_role_proposals,
    route_policy_warnings,
)


class StorageRoutePolicyTests(unittest.TestCase):
    def _route_quality(self) -> RouteQualityResponse:
        return RouteQualityResponse(
            workspace_root="/workspace",
            limit=20,
            overview=RouteQualityOverview(
                model_attempt_count=12,
                feedback_count=4,
            ),
            providers=[
                RouteQualityProviderRollup(
                    provider_id="openai:primary",
                    provider_label="OpenAI Primary",
                    provider_api="openai",
                    model="gpt",
                    attempts=6,
                    successes=2,
                    failures=4,
                    fallback_attempts=3,
                    success_rate=0.33,
                    fallback_rate=0.50,
                    average_latency_ms=32000,
                    average_context_utilization=0.84,
                    estimated_cost_usd=0.42,
                ),
                RouteQualityProviderRollup(
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen",
                    attempts=8,
                    successes=7,
                    failures=1,
                    fallback_attempts=1,
                    success_rate=0.875,
                    fallback_rate=0.125,
                    average_latency_ms=2500,
                    average_context_utilization=0.52,
                    estimated_cost_usd=0.0,
                ),
            ],
            roles=[
                RouteQualityRoleRollup(
                    role="code",
                    task_count=5,
                    attempts=8,
                    successes=5,
                    failures=3,
                    fallback_attempts=2,
                    success_rate=0.625,
                )
            ],
            feedback_rollups=[
                FeedbackAttributionRollup(
                    dimension="provider",
                    key="openai:primary",
                    label="OpenAI Primary",
                    feedback_count=2,
                    positive_count=0,
                    negative_count=2,
                    positive_rate=0.0,
                    negative_rate=1.0,
                ),
                FeedbackAttributionRollup(
                    dimension="provider",
                    key="ollama:qwen",
                    label="Qwen Local",
                    feedback_count=2,
                    positive_count=2,
                    negative_count=0,
                    positive_rate=1.0,
                    negative_rate=0.0,
                ),
            ],
        )

    def test_provider_proposals_rank_reliable_local_provider_first(self) -> None:
        proposals = route_policy_provider_proposals(self._route_quality(), min_attempts=3)

        self.assertEqual([proposal.provider_id for proposal in proposals], ["ollama:qwen", "openai:primary"])
        self.assertEqual(proposals[0].action, "promote")
        self.assertEqual(proposals[0].risk_level, "low")
        self.assertEqual(proposals[0].proposed_rank, 1)
        self.assertEqual(proposals[1].action, "deprioritize")
        self.assertEqual(proposals[1].risk_level, "high")
        self.assertTrue(any("Negative feedback" in risk for risk in proposals[1].risks))

    def test_role_proposals_switch_primary_when_better_provider_has_clear_score_delta(self) -> None:
        route_quality = self._route_quality()
        provider_proposals = route_policy_provider_proposals(route_quality, min_attempts=3)
        model_attempts = [
            ModelAttemptTelemetryEntry(
                task_id=f"old-{index}",
                created_at="2026-01-01T00:00:00+00:00",
                workspace_root="/workspace",
                attempt=ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id="openai:primary",
                    provider_label="OpenAI Primary",
                    provider_api="openai",
                    model="gpt",
                    status="failed" if index < 4 else "succeeded",
                    latency_ms=31000,
                ),
            )
            for index in range(5)
        ] + [
            ModelAttemptTelemetryEntry(
                task_id=f"new-{index}",
                created_at="2026-01-01T00:01:00+00:00",
                workspace_root="/workspace",
                attempt=ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen",
                    status="succeeded",
                    latency_ms=2500,
                ),
            )
            for index in range(3)
        ]

        proposals = route_policy_role_proposals(
            route_quality,
            model_attempts,
            provider_proposals,
            min_attempts=3,
        )

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].role, "code")
        self.assertEqual(proposals[0].action, "switch_primary")
        self.assertEqual(proposals[0].observed_primary_provider, "openai:primary")
        self.assertEqual(proposals[0].proposed_primary_provider, "ollama:qwen")
        self.assertGreaterEqual(proposals[0].score_delta, 8.0)

    def test_warnings_and_recommendations_explain_non_actionable_policy_windows(self) -> None:
        route_quality = RouteQualityResponse(
            workspace_root="/workspace",
            limit=20,
            overview=RouteQualityOverview(model_attempt_count=0, feedback_count=0),
            providers=[
                RouteQualityProviderRollup(
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen",
                    attempts=1,
                    successes=0,
                    failures=1,
                    success_rate=0.0,
                )
            ],
        )

        warnings = route_policy_warnings(route_quality, source_snapshot_stale=True, min_attempts=3)
        recommendations = route_policy_recommendations([], [], warnings)

        self.assertTrue(any("stale snapshot" in warning for warning in warnings))
        self.assertTrue(any("No model-attempt telemetry" in warning for warning in warnings))
        self.assertEqual(recommendations, [])
