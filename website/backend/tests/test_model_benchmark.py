from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.model_benchmark import BENCHMARK_SUITES, ModelBenchmarkManager
from aegis_ai.schemas import (
    ModelBenchmarkJobInfo,
    ModelBenchmarkResult,
    ModelBenchmarkRunRequest,
    ModelRegistryProvider,
    ModelRegistryResponse,
)
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

    def test_snapshot_ignores_damaged_result_and_job_paths(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelBenchmarkManager(Path(temp_dir), settings, FakeRegistry())  # type: ignore[arg-type]
            manager.results_path.mkdir(parents=True)
            manager.jobs_path.mkdir(parents=True)

            snapshot = manager.snapshot()

        self.assertEqual(snapshot.results_total, 0)
        self.assertEqual(snapshot.recent_results, [])
        self.assertEqual(snapshot.jobs, [])

    def test_loaders_skip_invalid_records(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelBenchmarkManager(Path(temp_dir), settings, FakeRegistry())  # type: ignore[arg-type]
            manager.results_path.parent.mkdir(parents=True)
            manager.results_path.write_text(
                "[{\"id\":\"valid-result\",\"created_at\":\"2026-04-29T00:00:00Z\"}, {\"score\": 2}, 7]",
                encoding="utf-8",
            )
            manager.jobs_path.write_text(
                "[{\"id\":\"valid-job\",\"created_at\":\"2026-04-29T00:00:00Z\"}, {\"timeout_seconds\": 1}, false]",
                encoding="utf-8",
            )

            results = manager._load_results()
            jobs = manager._load_jobs()

        self.assertEqual([result.id for result in results], ["valid-result"])
        self.assertEqual([job.id for job in jobs], ["valid-job"])

    def test_benchmark_json_writes_are_atomic(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelBenchmarkManager(Path(temp_dir), settings, FakeRegistry())  # type: ignore[arg-type]
            manager._append_results(
                [
                    ModelBenchmarkResult(
                        id="result-atomic",
                        created_at="2026-04-29T00:00:00Z",
                        provider_id="ollama:test",
                        provider_label="Ollama Test",
                        api="ollama",
                        model_name="qwen-test:7b",
                        suite_id="chat",
                        suite_label="General Chat",
                    )
                ]
            )
            manager._upsert_job(
                ModelBenchmarkJobInfo(
                    id="job-atomic",
                    status="queued",
                    message="Queued.",
                    created_at="2026-04-29T00:00:00Z",
                )
            )

            results_payload = manager.results_path.read_text(encoding="utf-8")
            jobs_payload = manager.jobs_path.read_text(encoding="utf-8")
            temp_files = list(manager.results_path.parent.glob(".*.tmp"))

        self.assertIn("result-atomic", results_payload)
        self.assertIn("job-atomic", jobs_payload)
        self.assertEqual(temp_files, [])

    def test_benchmark_jobs_api_reports_persistence_failure(self) -> None:
        settings = Settings(_env_file=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "data").write_text("damaged data path", encoding="utf-8")
            manager = ModelBenchmarkManager(project_root, settings, FakeRegistry())  # type: ignore[arg-type]

            with (
                patch.object(main, "model_benchmarks", manager),
                TestClient(main.app) as client,
            ):
                response = client.post(
                    "/api/model-benchmarks/jobs",
                    json=ModelBenchmarkRunRequest(
                        suite_ids=["chat"],
                        provider_ids=["ollama:test"],
                        max_models=1,
                        local_only=True,
                        timeout_seconds=5.0,
                    ).model_dump(),
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Could not update model benchmark records", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
