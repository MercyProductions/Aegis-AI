from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent import AgentEngine
from aegis_ai.schemas import ValidationRecipe, VerificationRequest
from aegis_ai.settings import Settings


class VerificationPipelineTests(unittest.TestCase):
    def test_verify_workspace_reports_python_syntax_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "pyproject.toml").write_text("[project]\nname = \"verify-smoke\"\n", encoding="utf-8")
            (workspace / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="python",
                sandbox_profile="standard",
                approval_tier="guided",
            )
            engine = AgentEngine(project_root, settings)

            response = asyncio.run(
                engine.verify_workspace(
                    VerificationRequest(
                        workspace_root=str(workspace),
                        max_steps=1,
                    )
                )
            )

            self.assertEqual(response.status, "failed")
            self.assertIsNotNone(response.first_failure)
            self.assertEqual(response.first_failure.category, "syntax")
            self.assertEqual(response.steps[0].command, "python -m compileall .")
            self.assertEqual(response.steps[0].status, "failed")
            command_history = json.loads(
                (workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8")
            )
            latest_command = command_history["commands"][-1]
            self.assertEqual(latest_command["kind"], "verification:build")
            self.assertEqual(latest_command["status"], "failed")
            self.assertTrue(latest_command["build_log_path"].startswith(".aegis/build_logs/"))
            self.assertTrue((workspace / latest_command["build_log_path"]).exists())
            known_errors = json.loads((workspace / ".aegis" / "known_errors.json").read_text(encoding="utf-8"))
            latest_error = known_errors["errors"][-1]
            self.assertEqual(latest_error["kind"], "verification:build")
            self.assertEqual(latest_error["build_log_path"], latest_command["build_log_path"])
            self.assertIn("SyntaxError", latest_error["output_excerpt"])
            self.assertTrue(any(event.payload.get("build_log_path") for event in response.events))

    def test_validation_override_runs_requested_command_without_persisting_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "pyproject.toml").write_text("[project]\nname = \"override-smoke\"\n", encoding="utf-8")
            (workspace / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="python",
                sandbox_profile="standard",
                approval_tier="guided",
            )
            engine = AgentEngine(project_root, settings)
            events: list[dict[str, object]] = []

            def emit(kind: str, title: str, **payload: object) -> None:
                events.append({"kind": kind, "title": title, **payload})

            run = engine._run_validation(
                workspace,
                emit,
                override_recipe=ValidationRecipe(
                    command="python -m compileall .",
                    label="Override syntax check",
                    source="request",
                ),
            )

            self.assertIsNotNone(run)
            self.assertEqual(run.command, "python -m compileall .")
            self.assertEqual(run.category, "syntax")
            self.assertTrue(any("(request)" in str(event.get("detail", "")) for event in events))
            self.assertIsNone(engine.validation.load_profile(workspace))


if __name__ == "__main__":
    unittest.main()
