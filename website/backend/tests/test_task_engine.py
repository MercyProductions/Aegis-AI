from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.schemas import ExecutionQueueItem, RepairAttempt
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class TaskEngineTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_task_creation_state_transitions_and_default_subtasks(self) -> None:
        task_id = self.store.create_task(
            mode="develop",
            workspace_root=self.workspace,
            message="Refactor the runtime",
            title="Refactor runtime",
            user_goal="Make runtime modular",
        )

        self.store.transition_task(task_id, "planning")
        self.store.create_default_subtasks(
            parent_task_id=task_id,
            workspace_root=self.workspace,
            mode="develop",
            user_goal="Make runtime modular",
        )
        self.store.transition_task(task_id, "running")
        self.store.transition_task(task_id, "validating")
        self.store.transition_task(task_id, "completed", final_summary="Validation passed.")

        task = self.store.task(task_id)
        subtasks = self.store.subtasks(task_id)
        timeline = self.store.task_events(task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.title, "Refactor runtime")
        self.assertEqual(len(subtasks), 8)
        self.assertIn("review", {item.assigned_agent_role for item in subtasks})
        self.assertIn("memory", {item.assigned_agent_role for item in subtasks})
        self.assertGreaterEqual(len(timeline), 4)
        self.assertTrue(any(event.title == "Task completed" for event in timeline))

    def test_task_cancellation_approval_and_retry_flow(self) -> None:
        task_id = self.store.create_task(mode="develop", workspace_root=self.workspace, message="Edit guarded file")
        self.store.transition_task(task_id, "planning")
        self.store.transition_task(task_id, "running")
        self.store.transition_task(task_id, "needs_approval", title="Approval requested")

        approval_event = self.store.approve_task_action(task_id, reason="Approved safe edit", approved=True)
        self.store.transition_task(task_id, "failed", error_summary="Validation still failed")
        retry_event = self.store.retry_task(task_id, reason="Try again after user review")
        cancel_event = self.store.cancel_task(task_id, reason="User stopped the run")

        self.assertEqual(approval_event.kind, "approval")
        self.assertEqual(retry_event.title, "Task queued for retry")
        self.assertEqual(cancel_event.title, "Task canceled")
        self.assertEqual(self.store.task(task_id).status, "canceled")

    def test_validation_failure_repair_checkpoint_and_timeline_persist(self) -> None:
        task_id = self.store.create_task(mode="develop", workspace_root=self.workspace, message="Fix failing validation")
        self.store.transition_task(task_id, "planning")
        self.store.transition_task(task_id, "running")
        self.store.transition_task(task_id, "validating", title="Validation failed", error_summary="pytest failed")
        self.store.add_task_artifacts(
            task_id,
            related_files=["src/app.py"],
            validation_commands=["pytest"],
            checkpoints=["checkpoint-123"],
            error_summary="pytest failed",
        )
        self.store.record_repair_attempt(
            task_id,
            RepairAttempt(
                attempt=1,
                category="test",
                before_signature="pytest failed",
                after_signature="pytest passed",
                outcome="repaired",
                checkpoint="checkpoint-123",
                summary="Adjusted src/app.py and reran pytest.",
            ),
        )
        self.store.transition_task(task_id, "repairing")
        self.store.transition_task(task_id, "validating")
        self.store.transition_task(task_id, "completed", final_summary="pytest passed")

        reopened = EventStore(self.project_root, self.settings)
        artifacts = reopened.task_artifacts(task_id)
        timeline = reopened.task_events(task_id)

        self.assertIn("src/app.py", artifacts.related_files)
        self.assertIn("pytest", artifacts.validation_commands)
        self.assertIn("checkpoint-123", artifacts.checkpoints)
        self.assertEqual(artifacts.repair_attempts[0].outcome, "repaired")
        self.assertTrue(any(event.title == "Task completed" for event in timeline))

    def test_task_and_execution_summaries_redact_secret_values(self) -> None:
        secret = "oauth-access-token-1234567890"
        task_id = self.store.create_task(mode="develop", workspace_root=self.workspace, message="Fix secret-bearing error")
        self.store.transition_task(task_id, "planning")
        self.store.transition_task(task_id, "running")
        self.store.transition_task(task_id, "validating")
        self.store.transition_task(
            task_id,
            "failed",
            error_summary=f"SyntaxError: unexpected token: < access_token={secret}",
            final_summary=f"client_secret={secret}",
            detail=f"refresh_token={secret}",
        )
        task = self.store.task(task_id)
        timeline = self.store.task_events(task_id)

        self.assertNotIn(secret, task.error_summary)
        self.assertNotIn(secret, task.final_summary)
        self.assertIn("access_token=[redacted]", task.error_summary)
        self.assertIn("unexpected token: <", task.error_summary)
        self.assertIn("client_secret=[redacted]", task.final_summary)
        self.assertTrue(any("refresh_token=[redacted]" in event.detail for event in timeline))

        job = self.store.create_execution_job(
            ExecutionQueueItem(
                id="job-secret",
                task_id=task_id,
                workspace_root=str(self.workspace),
                title="Validate",
                user_goal="Run validation",
                created_at="now",
                error_summary=f"access_token={secret}",
                result_summary=f"client_secret={secret}",
            )
        )
        updated = self.store.update_execution_job(
            job.id,
            status="failed",
            error_summary=f"refresh_token={secret}",
            result_summary=f"private_key={secret}",
        )

        self.assertNotIn(secret, job.error_summary)
        self.assertNotIn(secret, job.result_summary)
        self.assertNotIn(secret, updated.error_summary)
        self.assertNotIn(secret, updated.result_summary)
        self.assertIn("access_token=[redacted]", job.error_summary)
        self.assertIn("client_secret=[redacted]", job.result_summary)
        self.assertIn("refresh_token=[redacted]", updated.error_summary)
        self.assertIn("private_key=[redacted]", updated.result_summary)

    def test_task_event_ledger_redacts_detail_and_nested_payload_secrets(self) -> None:
        secret = "oauth-access-token-1234567890"
        task_id = self.store.create_task(mode="develop", workspace_root=self.workspace, message="Audit provider call")

        event = self.store.record_event(
            task_id,
            kind="provider.call",
            title="Provider call failed",
            status="warning",
            detail=f"refresh_token={secret}; unexpected token: <",
            payload={
                "api_key": secret,
                "headers": {"Authorization": f"Bearer {secret}"},
                "callback": f"https://provider.test/callback?access_token={secret}&state=ok",
                "diagnostics": [
                    f'Provider rejected {{"client_secret":"{secret}"}}',
                    "SyntaxError: unexpected token: <",
                ],
                "secret_env": "OPENAI_API_KEY",
            },
        )
        persisted = self.store.task_events(task_id)[0]

        self.assertNotIn(secret, event.detail)
        self.assertNotIn(secret, str(event.payload))
        self.assertNotIn(secret, persisted.detail)
        self.assertNotIn(secret, str(persisted.payload))
        self.assertIn("refresh_token=[redacted]", persisted.detail)
        self.assertIn("unexpected token: <", persisted.detail)
        self.assertEqual(persisted.payload["api_key"], "[redacted]")
        self.assertEqual(persisted.payload["headers"]["Authorization"], "[redacted]")
        self.assertIn("access_token=[redacted]", persisted.payload["callback"])
        self.assertIn('"client_secret":"[redacted]"', persisted.payload["diagnostics"][0])
        self.assertEqual(persisted.payload["diagnostics"][1], "SyntaxError: unexpected token: <")
        self.assertEqual(persisted.payload["secret_env"], "OPENAI_API_KEY")

    def test_task_api_endpoints(self) -> None:
        workspace_manager = WorkspaceManager(self.project_root, self.settings)

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", workspace_manager),
            patch.object(main.agent, "store", self.store),
            TestClient(main.app) as client,
        ):
            create_response = client.post(
                "/api/tasks",
                json={
                    "workspace_root": str(self.workspace),
                    "title": "API task",
                    "user_goal": "Exercise task endpoints",
                    "mode": "develop",
                    "related_files": ["src/main.py"],
                    "validation_commands": ["pytest"],
                },
            )
            self.assertEqual(create_response.status_code, 200, create_response.text)
            task_id = create_response.json()["task"]["id"]

            list_response = client.get("/api/tasks", params={"workspace_root": str(self.workspace)})
            detail_response = client.get(f"/api/tasks/{task_id}")
            timeline_response = client.get(f"/api/tasks/{task_id}/timeline")
            artifacts_response = client.get(f"/api/tasks/{task_id}/artifacts")
            cancel_response = client.post(f"/api/tasks/{task_id}/cancel", json={"reason": "stop"})

        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertEqual(timeline_response.status_code, 200, timeline_response.text)
        self.assertEqual(artifacts_response.status_code, 200, artifacts_response.text)
        self.assertEqual(cancel_response.status_code, 200, cancel_response.text)
        self.assertEqual(cancel_response.json()["task"]["status"], "canceled")
        self.assertEqual(artifacts_response.json()["related_files"], ["src/main.py"])


if __name__ == "__main__":
    unittest.main()
