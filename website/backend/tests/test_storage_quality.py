from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import (
    FeedbackRecordRequest,
    ModelAttemptInfo,
    ModelAttemptTelemetryEntry,
    RouteQualityTokenCalibrationTrendBucket,
)
from aegis_ai.storage_quality import (
    attempt_status,
    feedback_metadata,
    is_fallback_attempt,
    structured_preview_metrics,
    structured_preview_recommendation,
    structured_preview_status,
    token_calibration_recommendation,
    token_calibration_status,
    token_calibration_trend_recommendation,
    token_estimator_label,
)


class StorageQualityTests(unittest.TestCase):
    def test_feedback_metadata_adds_content_flags_and_filters_unstable_values(self) -> None:
        request = FeedbackRecordRequest(
            content=" final answer ",
            metadata={
                "source": "chat",
                "score": 4,
                "ignored": {"nested": True},
                "long-key-" + ("x" * 100): "trimmed",
            },
        )

        metadata = feedback_metadata(request)

        self.assertEqual(metadata["source"], "chat")
        self.assertEqual(metadata["score"], 4)
        self.assertEqual(metadata["content_length"], len(" final answer "))
        self.assertIs(metadata["has_content"], True)
        self.assertNotIn("ignored", metadata)
        self.assertTrue(any(key.startswith("long-key-") and len(key) == 80 for key in metadata))

    def test_attempt_status_and_fallback_detection_normalize_attempt_state(self) -> None:
        self.assertEqual(attempt_status(SimpleNamespace(attempt=SimpleNamespace(status=" Succeeded "))), "succeeded")
        self.assertEqual(attempt_status(SimpleNamespace(attempt=SimpleNamespace(status=""))), "planned")
        self.assertFalse(is_fallback_attempt(attempt_entry(attempt=1, role="code", status="succeeded")))
        self.assertTrue(is_fallback_attempt(attempt_entry(attempt=2, role="code", status="succeeded")))
        self.assertTrue(is_fallback_attempt(attempt_entry(attempt=1, role="fallback", status="planned")))
        self.assertTrue(is_fallback_attempt(attempt_entry(attempt=1, role="code", status="fallback")))

    def test_token_estimator_label_combines_family_and_source(self) -> None:
        self.assertEqual(
            token_estimator_label({"token_estimator_family": "tiktoken", "token_estimate_source": "profile"}),
            "tiktoken:profile",
        )
        self.assertEqual(token_estimator_label({"token_estimator_family": "local"}), "local")
        self.assertEqual(token_estimator_label([]), "")

    def test_structured_preview_metrics_are_normalized_from_metadata(self) -> None:
        self.assertIsNone(structured_preview_metrics({}))
        self.assertIsNone(structured_preview_metrics([]))

        metrics = structured_preview_metrics(
            {
                "structured_preview_delta_count": "3",
                "structured_preview_char_count": "42",
                "structured_preview_reset_count": "1",
                "structured_preview_emitted": "false",
                "structured_preview_retired": "false",
                "structured_preview_final_winner": "yes",
                "structured_preview_retired_reason": "invalid_structured_json",
            }
        )

        self.assertEqual(
            metrics,
            {
                "delta_count": 3,
                "char_count": 42,
                "reset_count": 1,
                "emitted": True,
                "retired": True,
                "final_winner": True,
                "retired_reason": "invalid_structured_json",
            },
        )

    def test_structured_preview_status_and_recommendation_explain_stability(self) -> None:
        self.assertEqual(
            structured_preview_status(
                previewed_attempts=0,
                final_winning_attempts=0,
                retired_attempts=0,
                reset_count=0,
            ),
            "insufficient",
        )
        self.assertEqual(
            structured_preview_status(
                previewed_attempts=2,
                final_winning_attempts=1,
                retired_attempts=1,
                reset_count=2,
            ),
            "unstable",
        )
        self.assertEqual(
            structured_preview_status(
                previewed_attempts=3,
                final_winning_attempts=2,
                retired_attempts=1,
                reset_count=0,
            ),
            "watch",
        )
        self.assertEqual(
            structured_preview_status(
                previewed_attempts=3,
                final_winning_attempts=3,
                retired_attempts=0,
                reset_count=0,
            ),
            "stable",
        )
        self.assertIn(
            "more stable structured-output provider",
            structured_preview_recommendation(
                status="unstable",
                provider_label="Qwen",
                previewed_attempts=2,
                final_winning_attempts=1,
                retired_attempts=1,
                reset_count=2,
            ),
        )

    def test_token_calibration_status_and_recommendation_explain_estimator_quality(self) -> None:
        self.assertEqual(
            token_calibration_status(
                calibrated_attempts=0,
                average_input_error=None,
                average_output_error=None,
                worst_input_error=None,
                worst_output_error=None,
            ),
            "insufficient",
        )
        self.assertEqual(
            token_calibration_status(
                calibrated_attempts=3,
                average_input_error=0.1,
                average_output_error=0.08,
                worst_input_error=0.2,
                worst_output_error=0.1,
            ),
            "stable",
        )
        self.assertEqual(
            token_calibration_status(
                calibrated_attempts=3,
                average_input_error=0.2,
                average_output_error=0.18,
                worst_input_error=0.4,
                worst_output_error=0.2,
            ),
            "watch",
        )
        self.assertEqual(
            token_calibration_status(
                calibrated_attempts=3,
                average_input_error=0.4,
                average_output_error=0.1,
                worst_input_error=0.6,
                worst_output_error=0.2,
            ),
            "drift",
        )
        self.assertIn(
            "avg error in/out 10%/8%",
            token_calibration_recommendation(
                status="stable",
                provider_label="Qwen",
                calibrated_attempts=3,
                average_input_error=0.1,
                average_output_error=0.08,
                reported_sources=["ollama"],
            ),
        )

    def test_token_calibration_trend_recommendation_uses_bucket_state(self) -> None:
        self.assertIn(
            "No provider-reported usage",
            token_calibration_trend_recommendation(
                RouteQualityTokenCalibrationTrendBucket(
                    provider_label="Qwen",
                    period_start="2026-05-07",
                    calibrated_attempts=0,
                )
            ),
        )
        self.assertIn(
            "improved",
            token_calibration_trend_recommendation(
                RouteQualityTokenCalibrationTrendBucket(
                    provider_label="Qwen",
                    period_start="2026-05-07",
                    calibrated_attempts=3,
                    trend_direction="improving",
                )
            ),
        )
        self.assertIn(
            "established a calibration baseline",
            token_calibration_trend_recommendation(
                RouteQualityTokenCalibrationTrendBucket(
                    provider_label="Qwen",
                    period_start="2026-05-07",
                    calibrated_attempts=3,
                    trend_direction="baseline",
                    calibration_status="stable",
                )
            ),
        )


def attempt_entry(
    *,
    attempt: int = 1,
    role: str = "code",
    status: str = "succeeded",
    metadata: dict[str, object] | None = None,
) -> ModelAttemptTelemetryEntry:
    return ModelAttemptTelemetryEntry(
        task_id="task-1",
        created_at="2026-05-07T00:00:00+00:00",
        workspace_root="workspace",
        attempt=ModelAttemptInfo(
            attempt=attempt,
            role=role,
            status=status,
            metadata=metadata or {},
        ),
    )


if __name__ == "__main__":
    unittest.main()
