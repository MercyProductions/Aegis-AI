from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from aegis_ai.agent import AgentEngine
from aegis_ai.diff_engine import DiffEngine
from aegis_ai.llm import LocalModelStatus
from aegis_ai.project_scaffolder import ProjectScaffolder
from aegis_ai.schemas import AgentRequest, FileChange, ProjectScaffoldRequest, RepairAttempt
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.validation import ValidationManager
from aegis_ai.workspace import WorkspaceManager


class FakeQuestionModel:
    label = "Fake Question Model"
    endpoint = "memory://fake-question"
    api = "fake"
    model = "fake-question"

    async def status(self) -> LocalModelStatus:
        return LocalModelStatus(ready=True, message="ready")

    async def complete_json(self, messages):
        return {
            "answer": "Aegis is ready to answer without touching files.",
            "changes": [],
            "commands": [],
        }


class GoldenWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
            aegis_router_execution_enabled=False,
        )
        self.workspace_manager = WorkspaceManager(self.project_root, self.settings)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_normal_question_does_not_generate_file_changes(self) -> None:
        engine = AgentEngine(self.project_root, self.settings)
        engine.model = FakeQuestionModel()  # type: ignore[assignment]

        response = asyncio.run(
            engine.run(
                AgentRequest(
                    message="What is Aegis?",
                    mode="chat",
                    apply_changes=False,
                    run_validation=False,
                )
            )
        )

        self.assertEqual(response.changes, [])
        self.assertEqual(response.applied, [])
        self.assertIsNone(response.checkpoint)
        self.assertIn("without touching files", response.reply)

    def test_create_vite_app_generates_expected_project_files(self) -> None:
        scaffolder = ProjectScaffolder(self.workspace_manager, ValidationManager())
        target = self.project_root / "workspace" / "vite-golden"

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vite-react-ts",
                project_name="Vite Golden",
                run_install=False,
                run_validation=False,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.checkpoint)
        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "src" / "App.tsx").exists())
        self.assertIn("create: package.json", result.applied)
        self.assertIn(".aegis/ROADMAP.md", [file.path for file in result.files])

    def test_modify_existing_file_produces_diff_and_checkpoint_then_rollback_restores(self) -> None:
        workspace = self.workspace_manager.resolve_workspace("workspace")
        source = workspace / "src" / "main.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("print('before')\n", encoding="utf-8")

        diff = DiffEngine.compare_files(
            old_content="print('before')\n",
            new_content="print('after')\n",
            path="src/main.py",
            action="update",
        )
        result = self.workspace_manager.apply_changes(
            workspace,
            [
                FileChange(
                    action="update",
                    path="src/main.py",
                    summary="Update the smoke output.",
                    content="print('after')\n",
                )
            ],
        )

        self.assertGreater(diff.added_lines, 0)
        self.assertGreater(diff.removed_lines, 0)
        self.assertEqual(source.read_text(encoding="utf-8"), "print('after')\n")
        self.assertIsNotNone(result.checkpoint)

        restored = self.workspace_manager.restore_checkpoint(workspace, result.checkpoint or "")

        self.assertIn("restore: src/main.py", restored)
        self.assertEqual(source.read_text(encoding="utf-8"), "print('before')\n")

    def test_validation_failure_repair_attempt_and_project_memory_persist(self) -> None:
        workspace = self.workspace_manager.resolve_workspace("workspace")
        store = EventStore(self.project_root, self.settings)

        store.record_repair_attempt(
            "golden-task",
            RepairAttempt(
                attempt=1,
                category="validation",
                before_signature="pytest failed: AssertionError",
                after_signature="pytest passed",
                outcome="repaired",
                checkpoint="checkpoint-1",
                summary="Adjusted failing assertion and reran validation.",
            ),
        )
        store.remember_project_note(
            project_root=workspace,
            category="architecture",
            title="Golden memory",
            detail="Persist this note across EventStore instances.",
            source="test",
            confidence=1.0,
        )

        reopened_store = EventStore(self.project_root, self.settings)

        attempts = reopened_store.repair_attempts("golden-task")
        memories = reopened_store.project_memory(project_root=workspace, limit=5)

        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].outcome, "repaired")
        self.assertTrue(any(memory.title == "Golden memory" for memory in memories))

    def test_workspace_safety_rejects_parent_directory_file_changes(self) -> None:
        with self.assertRaises(ValidationError):
            FileChange(
                action="create",
                path="../escape.txt",
                summary="Attempt path escape.",
                content="nope\n",
            )

        self.assertFalse((self.project_root / "escape.txt").exists())

    def test_workspace_safety_warns_when_runtime_change_points_outside_workspace(self) -> None:
        workspace = self.workspace_manager.resolve_workspace("workspace")
        unsafe_change = FileChange.model_construct(
            action="create",
            path="../escape.txt",
            summary="Attempt path escape.",
            content="nope\n",
        )

        result = self.workspace_manager.apply_changes(workspace, [unsafe_change])

        self.assertEqual(result.applied, [])
        self.assertIsNone(result.checkpoint)
        self.assertTrue(any("outside the workspace" in warning for warning in result.warnings))
        self.assertFalse((self.project_root / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
