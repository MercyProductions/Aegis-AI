from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.commands import CommandResult
from aegis_ai.project_scaffold_command_stage import run_command_stage


class ProjectScaffoldCommandStageTests(unittest.TestCase):
    def test_run_command_stage_blocks_when_runner_is_unavailable(self) -> None:
        stage, run = run_command_stage(
            None,
            sandbox_profile=None,
            stage_id="validate",
            label="Validation",
            command="npm run build",
            target=Path("workspace"),
        )

        self.assertIsNone(run)
        self.assertEqual(stage.status, "blocked")
        self.assertEqual(stage.error, "Command runner unavailable.")
        self.assertEqual(stage.command, "npm run build")

    def test_run_command_stage_records_successful_command(self) -> None:
        runner = FakeCommandRunner(
            CommandResult(
                command="python build.py",
                cwd="workspace",
                allowed=True,
                exit_code=0,
                stdout="ok",
                stderr="",
                timed_out=False,
                reason="Command finished.",
            )
        )

        stage, run = run_command_stage(
            runner,
            sandbox_profile="local",
            stage_id="validate",
            label="Validation",
            command="python build.py",
            target=Path("workspace"),
        )

        self.assertIsNotNone(run)
        self.assertEqual(runner.calls, [("python build.py", Path("workspace"), "local")])
        self.assertEqual(stage.status, "succeeded")
        self.assertEqual(stage.error, "")
        self.assertEqual(stage.output_excerpt, "ok")
        self.assertEqual(run.category, "success")

    def test_run_command_stage_records_blocked_command_result(self) -> None:
        runner = FakeCommandRunner(
            CommandResult(
                command="git reset --hard",
                cwd="workspace",
                allowed=False,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                reason="Command matched the destructive-command denylist.",
            )
        )

        stage, run = run_command_stage(
            runner,
            sandbox_profile=None,
            stage_id="validate",
            label="Validation",
            command="git reset --hard",
            target=Path("workspace"),
        )

        self.assertIsNotNone(run)
        self.assertEqual(stage.status, "blocked")
        self.assertIn("denylist", stage.detail.lower())
        self.assertIn("denylist", stage.error.lower())
        self.assertFalse(run.allowed)


class FakeCommandRunner:
    def __init__(self, result: CommandResult):
        self.result = result
        self.calls: list[tuple[str, Path, str | None]] = []

    def run(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int | None = None,
        sandbox_profile: str | None = None,
    ) -> CommandResult:
        self.calls.append((command, cwd, sandbox_profile))
        return self.result


if __name__ == "__main__":
    unittest.main()
