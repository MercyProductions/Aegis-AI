from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent import AgentDraft, AgentEngine
from aegis_ai.multi_agent import MultiAgentCoordinator
from aegis_ai.schemas import AgentRequest, CommandRun, FileChange
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore


class MultiAgentCoordinatorTests(unittest.TestCase):
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
        self.coordinator = MultiAgentCoordinator(self.store)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_handoff_approval_retry_cancellation_and_iteration_limits(self) -> None:
        task_id = self.store.create_task(
            mode="develop",
            workspace_root=self.workspace,
            message="Change src/app.py",
        )
        self.store.transition_task(task_id, "planning")
        self.coordinator.start_chain(task_id, workspace_root=self.workspace, user_goal="Change src/app.py")
        handoff = self.coordinator.handoff(task_id, "planner", "architect", reason="Plan ready.")
        approval = self.coordinator.approval_requested(
            task_id,
            "code",
            reason="config.py is risk-sensitive.",
            blocked_paths=["config.py"],
        )
        limit = self.coordinator.agent_output(
            task_id,
            "repair",
            "Repair Agent extra attempt",
            iteration=99,
        )
        self.store.transition_task(task_id, "failed", error_summary="validation failed")
        retry = self.store.retry_task(task_id, reason="try again")
        cancel = self.store.cancel_task(task_id, reason="user stopped it")
        should_continue = self.coordinator.should_continue(task_id, "code")
        events = self.store.task_events(task_id)

        self.assertEqual(handoff.kind, "agent.handoff")
        self.assertEqual(approval.kind, "agent.approval")
        self.assertEqual(limit.status, "error")
        self.assertEqual(retry.title, "Task queued for retry")
        self.assertEqual(cancel.title, "Task canceled")
        self.assertFalse(should_continue)
        self.assertTrue(any(event.kind == "agent.control" for event in events))


class MultiAgentAgentEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.workspace = self.project_root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.engine = AgentEngine(
            self.project_root,
            Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                approval_tier="autonomous",
            ),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_coding_request_records_multi_agent_validation_chain(self) -> None:
        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="Validation checked.", plan=["Inspect", "Validate"], changes=[]), None

        def fake_run_validation(*args, **kwargs):
            return CommandRun(
                command="python -m pytest",
                cwd=str(self.workspace),
                allowed=True,
                exit_code=0,
                stdout="passed\n",
                summary="Validation passed.",
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]
        self.engine._run_validation = fake_run_validation  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="run validation for this project",
                    mode="develop",
                    workspace_root=str(self.workspace),
                    run_validation=True,
                    apply_changes=False,
                )
            )
        )
        timeline = self.engine.store.task_events(response.task_id)
        kinds = [event.kind for event in timeline]
        subtask_roles = {item.assigned_agent_role for item in self.engine.store.subtasks(response.task_id)}

        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("agent.chain", kinds)
        self.assertIn("agent.planner", kinds)
        self.assertIn("agent.architect", kinds)
        self.assertIn("agent.code", kinds)
        self.assertIn("agent.review", kinds)
        self.assertIn("agent.validation", kinds)
        self.assertIn("agent.memory", kinds)
        self.assertIn("review", subtask_roles)
        self.assertIn("memory", subtask_roles)
        self.assertEqual(self.engine.store.task(response.task_id).status, "completed")

    def test_normal_chat_keeps_single_agent_fallback_without_multi_agent_chain(self) -> None:
        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="A vector database stores embeddings for similarity search.", changes=[]), None

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="what is a vector database?",
                    mode="chat",
                    workspace_root=str(self.workspace),
                )
            )
        )
        kinds = [event.kind for event in self.engine.store.task_events(response.task_id)]

        self.assertEqual(response.mode, "chat")
        self.assertFalse(any(kind.startswith("agent.") for kind in kinds))
        self.assertEqual(self.engine.store.subtasks(response.task_id), [])

    def test_validation_failure_flows_to_repair_agent_and_back_to_validation(self) -> None:
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        validation_calls = {"count": 0}

        async def fake_draft_response(*args, **kwargs):
            return (
                AgentDraft(
                    reply="Created app.",
                    plan=["Create file"],
                    changes=[FileChange(action="create", path="src/app.py", content="print('broken')\n", summary="create app")],
                ),
                None,
            )

        def fake_run_validation(*args, **kwargs):
            validation_calls["count"] += 1
            if validation_calls["count"] == 1:
                return CommandRun(
                    command="python -m pytest",
                    cwd=str(self.workspace),
                    allowed=True,
                    exit_code=1,
                    stderr="AssertionError: broken\n",
                    summary="Tests failed.",
                )
            return CommandRun(
                command="python -m pytest",
                cwd=str(self.workspace),
                allowed=True,
                exit_code=0,
                stdout="passed\n",
                summary="Tests passed.",
            )

        async def fake_draft_repair(*args, **kwargs):
            return AgentDraft(
                reply="Fixed app.",
                plan=["Update file"],
                changes=[FileChange(action="update", path="src/app.py", content="print('fixed')\n", summary="fix app")],
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]
        self.engine._run_validation = fake_run_validation  # type: ignore[method-assign]
        self.engine._draft_repair = fake_draft_repair  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="create src/app.py and run validation",
                    mode="develop",
                    workspace_root=str(self.workspace),
                    run_validation=True,
                    apply_changes=True,
                    max_repair_attempts=1,
                )
            )
        )
        timeline = self.engine.store.task_events(response.task_id)

        self.assertEqual(response.validation.exit_code, 0)
        self.assertEqual(validation_calls["count"], 2)
        self.assertTrue(any(event.kind == "agent.repair" and "applied" in event.title.lower() for event in timeline))
        self.assertTrue(any(event.kind == "agent.handoff" and event.payload.get("to_agent_role") == "repair" for event in timeline))
        self.assertTrue(any(event.kind == "agent.validation" and "repair result" in event.title.lower() for event in timeline))
        self.assertEqual((self.workspace / "src" / "app.py").read_text(encoding="utf-8"), "print('fixed')\n")


if __name__ == "__main__":
    unittest.main()
