from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.adaptive_intelligence import AdaptiveIntelligenceEngine
from aegis_ai.schemas import (
    AdaptiveReplayRequest,
    ContextBudgetInfo,
    ContextBudgetItemInfo,
    FeedbackRecordRequest,
    ModelAttemptInfo,
    RepairAttempt,
)
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class AdaptiveIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.workspace = self.project_root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
        )
        self.store = EventStore(self.project_root, self.settings)
        self.engine = AdaptiveIntelligenceEngine()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_outcome_tracking_and_learning_persistence(self) -> None:
        success_task = self._seed_task("Refactor module", "completed", validation_exit=0, provider_id="local-code")
        failed_task = self._seed_task(
            "Fix failing tests",
            "failed",
            validation_exit=1,
            provider_id="cloud-code",
            error_summary="pytest failed in src/app.py",
            repair=True,
        )

        snapshot = self.engine.snapshot(self.store, project_root=self.workspace, refresh_outcomes=True)
        reopened = EventStore(self.project_root, self.settings)
        outcomes = reopened.adaptive_task_outcomes(project_root=self.workspace, limit=20)

        self.assertEqual({item.task_id for item in outcomes}, {success_task, failed_task})
        self.assertTrue(any(item.dimension == "task_completion" for item in snapshot.quality_scores))
        self.assertTrue(any(item.category.startswith("repair") for item in snapshot.repair_insights))
        self.assertEqual(reopened.active_adaptive_policy_profile().id, "local_privacy_first")

    def test_adaptive_routing_stability_and_policy_rollback(self) -> None:
        self._seed_task("Build feature", "completed", validation_exit=0, provider_id="local-code")
        first = self.engine.snapshot(self.store, project_root=self.workspace, refresh_outcomes=True)
        second = self.engine.snapshot(self.store, project_root=self.workspace, refresh_outcomes=True)
        self.assertEqual(
            [(item.provider_id, item.action, round(item.score, 4)) for item in first.route_recommendations],
            [(item.provider_id, item.action, round(item.score, 4)) for item in second.route_recommendations],
        )

        checkpoint = self.store.create_adaptive_policy_checkpoint("before test activation")
        activated = self.engine.activate_profile(self.store, profile_id="balanced_hybrid", reason="test activation")
        self.assertEqual(activated.id, "balanced_hybrid")
        restored = self.engine.rollback_policy(self.store, checkpoint_id=checkpoint.id, reason="test rollback")
        self.assertEqual(next(item for item in restored if item.active).id, "local_privacy_first")

    def test_replay_consistency_and_benchmark_reproducibility(self) -> None:
        task_id = self._seed_task("Review architecture", "completed", validation_exit=0, provider_id="local-code")
        self.engine.refresh_outcomes(self.store, project_root=self.workspace)

        first_replay = self.engine.replay(
            self.store,
            project_root=self.workspace,
            request=AdaptiveReplayRequest(workspace_root=str(self.workspace), task_ids=[task_id], limit=1),
        )
        second_replay = self.engine.replay(
            self.store,
            project_root=self.workspace,
            request=AdaptiveReplayRequest(workspace_root=str(self.workspace), task_ids=[task_id], limit=1),
        )
        self.assertEqual(first_replay[0].replay_score, second_replay[0].replay_score)

        first_reports = self.engine.run_benchmarks(self.store, project_root=self.workspace, suite_ids=["validation_success"])
        second_reports = self.engine.run_benchmarks(self.store, project_root=self.workspace, suite_ids=["validation_success"])
        self.assertEqual(first_reports[0].candidate_score, second_reports[0].candidate_score)
        self.assertEqual(first_reports[0].reproducibility_key, second_reports[0].reproducibility_key)

    def test_benchmark_regression_detection(self) -> None:
        self._seed_task("Repair broken route", "failed", validation_exit=1, provider_id="local-code", repair=True)
        self.engine.refresh_outcomes(self.store, project_root=self.workspace)

        reports = self.engine.run_benchmarks(
            self.store,
            project_root=self.workspace,
            suite_ids=["repair_quality"],
            baseline_score=0.95,
        )

        self.assertTrue(reports[0].regression_detected)
        self.assertEqual(reports[0].status, "regressed")

    def test_api_snapshot_benchmark_replay_and_profile_flow(self) -> None:
        self._seed_task("API adaptive task", "completed", validation_exit=0, provider_id="local-code")
        workspace_manager = WorkspaceManager(self.project_root, self.settings)

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", workspace_manager),
            patch.object(main.agent, "store", self.store),
            patch.object(main, "adaptive_intelligence", AdaptiveIntelligenceEngine()),
            TestClient(main.app) as client,
        ):
            snapshot = client.post(
                "/api/adaptive-intelligence/refresh",
                json={"workspace_root": str(self.workspace), "limit": 50, "refresh_outcomes": True},
            )
            activate = client.post(
                "/api/adaptive-intelligence/policies/balanced_hybrid/activate",
                params={"workspace_root": str(self.workspace)},
                json={"reason": "test activate"},
            )
            benchmark = client.post(
                "/api/adaptive-intelligence/benchmarks/run",
                json={"workspace_root": str(self.workspace), "suite_ids": ["reasoning"]},
            )
            replay = client.post(
                "/api/adaptive-intelligence/replay",
                json={"workspace_root": str(self.workspace), "limit": 1},
            )

        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertTrue(snapshot.json()["quality_scores"])
        self.assertEqual(activate.status_code, 200, activate.text)
        self.assertEqual(activate.json()["active_profile"]["id"], "balanced_hybrid")
        self.assertEqual(benchmark.status_code, 200, benchmark.text)
        self.assertEqual(benchmark.json()[0]["suite_id"], "reasoning")
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json())

    def _seed_task(
        self,
        title: str,
        final_status: str,
        *,
        validation_exit: int,
        provider_id: str,
        error_summary: str = "",
        repair: bool = False,
    ) -> str:
        task_id = self.store.create_task(
            mode="develop",
            workspace_root=self.workspace,
            message=title,
            title=title,
            user_goal=title,
        )
        self.store.transition_task(task_id, "planning")
        self.store.transition_task(task_id, "running")
        self.store.record_context_budget(
            task_id=task_id,
            workspace_root=self.workspace,
            context_budget=ContextBudgetInfo(
                intent="code",
                route_role="code",
                strategy="project-intelligence",
                max_context_tokens=8000,
                estimated_context_tokens=3200,
                estimated_file_tokens=2200,
                selected_file_count=1,
                omitted_file_count=2,
                items=[
                    ContextBudgetItemInfo(kind="file", ref="src/app.py", estimated_tokens=500, included=True),
                    ContextBudgetItemInfo(kind="project_memory", ref="memory:pytest", estimated_tokens=80, included=True),
                ],
            ),
        )
        self.store.record_model_attempts(
            task_id=task_id,
            workspace_root=self.workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id=provider_id,
                    provider_label=provider_id.replace("-", " ").title(),
                    provider_api="ollama" if provider_id.startswith("local") else "openai",
                    model=f"{provider_id}-model",
                    endpoint="http://127.0.0.1:11434",
                    status="succeeded" if final_status == "completed" else "failed",
                    input_tokens=1200,
                    output_tokens=600,
                    estimated_cost_usd=0.01 if provider_id.startswith("local") else 0.25,
                    latency_ms=900 if provider_id.startswith("local") else 1400,
                )
            ],
        )
        self.store.transition_task(task_id, "validating", error_summary=error_summary)
        self.store.record_event(
            task_id,
            kind="command",
            title="Validation command run",
            status="ok" if validation_exit == 0 else "error",
            detail="pytest",
            payload={"command": "pytest", "exit_code": validation_exit},
        )
        if repair:
            self.store.record_repair_attempt(
                task_id,
                RepairAttempt(
                    attempt=1,
                    category="validation",
                    before_signature=error_summary or "validation failed",
                    after_signature="",
                    outcome="failed" if final_status != "completed" else "fixed",
                    summary="Repair attempt recorded for adaptive learning.",
                ),
            )
            self.store.remember_fix(
                project_root=self.workspace,
                error_signature=error_summary or "validation failed",
                fix_summary="Use the known pytest repair before broad edits.",
                evidence="test evidence",
                confidence=0.8,
                category="validation",
            )
        if final_status == "completed":
            self.store.transition_task(task_id, "completed", final_summary="Completed with validation.")
            self.store.record_feedback(
                project_root=self.workspace,
                request=FeedbackRecordRequest(
                    task_id=task_id,
                    sentiment="accepted",
                    action="accepted",
                    target="changes",
                    model_label=provider_id,
                    route_role="code",
                    candidate_id=provider_id,
                ),
            )
        else:
            self.store.transition_task(task_id, "failed", error_summary=error_summary or "validation failed")
            self.store.record_feedback(
                project_root=self.workspace,
                request=FeedbackRecordRequest(
                    task_id=task_id,
                    sentiment="rejected",
                    action="rejected",
                    target="changes",
                    model_label=provider_id,
                    route_role="code",
                    candidate_id=provider_id,
                ),
            )
        return task_id


if __name__ == "__main__":
    unittest.main()
