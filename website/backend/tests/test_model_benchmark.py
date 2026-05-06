from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.model_benchmark import BENCHMARK_SUITES, ModelBenchmarkManager
from aegis_ai.schemas import ModelBenchmarkJobInfo, ModelBenchmarkResult, ModelRegistryProvider, ModelRegistryResponse
from aegis_ai.settings import Settings


class FakeRegistry:
    def snapshot(self) -> ModelRegistryResponse:
        return ModelRegistryResponse(
            active_provider_id="ollama:test",
            active_model="qwen-test:7b",
            providers=[
                ModelRegistryProvider(
                    id="ollama:test",
                    label="Ollama Test",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="qwen-test:7b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "code", "reasoning", "structured_json"],
                    roles=["chat", "code", "reasoning"],
                    health="available",
                )
            ],
        )


class ModelBenchmarkTests(unittest.TestCase):
    def test_score_payload_rewards_expected_terms_and_confidence(self) -> None:
        settings = Settings(_env_file=None)
        manager = ModelBenchmarkManager(Path("."), settings, FakeRegistry())  # type: ignore[arg-type]
        suite = next(item for item in BENCHMARK_SUITES if item.id == "chat")

        score, metadata = manager.score_payload(
            suite,
            {"answer": "11, 12, 13, 14, 15, 16, 17, 18, 19, 20", "confidence": 0.9},
            latency_ms=1000,
        )

        self.assertGreater(score, 0.85)
        self.assertEqual(metadata["expected_hits"], 10)
        self.assertEqual(metadata["confidence"], 0.9)

    def test_snapshot_aggregates_provider_scores_and_suite_winners(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelBenchmarkManager(Path(temp_dir), settings, FakeRegistry())  # type: ignore[arg-type]
            manager._append_results(
                [
                    ModelBenchmarkResult(
                        id="result-1",
                        created_at="2026-04-29T00:00:00Z",
                        provider_id="ollama:test",
                        provider_label="Ollama Test",
                        api="ollama",
                        model_name="qwen-test:7b",
                        suite_id="chat",
                        suite_label="General Chat",
                        status="succeeded",
                        score=0.9,
                        latency_ms=1000,
                    ),
                    ModelBenchmarkResult(
                        id="result-2",
                        created_at="2026-04-29T00:01:00Z",
                        provider_id="ollama:test",
                        provider_label="Ollama Test",
                        api="ollama",
                        model_name="qwen-test:7b",
                        suite_id="code",
                        suite_label="Coding",
                        status="succeeded",
                        score=0.8,
                        latency_ms=2000,
                    ),
                ]
            )

            snapshot = manager.snapshot()

        self.assertEqual(snapshot.results_total, 2)
        self.assertEqual(snapshot.provider_scores[0].provider_id, "ollama:test")
        self.assertAlmostEqual(snapshot.provider_scores[0].overall_score, 0.85)
        self.assertEqual(snapshot.suite_summaries[0].best_model_name, "qwen-test:7b")

    def test_cancel_job_marks_active_job_canceled_without_task_handle(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelBenchmarkManager(Path(temp_dir), settings, FakeRegistry())  # type: ignore[arg-type]
            manager._upsert_job(
                ModelBenchmarkJobInfo(
                    id="bench-test",
                    status="running",
                    message="Benchmark job is running.",
                    created_at="2026-04-29T00:00:00Z",
                    started_at="2026-04-29T00:00:01Z",
                    total_runs=2,
                    completed_runs=1,
                    current_provider_id="ollama:test",
                    current_model_name="qwen-test:7b",
                    current_suite_id="chat",
                )
            )

            job = manager.cancel_job("bench-test")

        self.assertEqual(job.status, "canceled")
        self.assertEqual(job.completed_runs, 1)
        self.assertEqual(job.current_model_name, "")
        self.assertIn("canceled", job.message)


if __name__ == "__main__":
    unittest.main()
