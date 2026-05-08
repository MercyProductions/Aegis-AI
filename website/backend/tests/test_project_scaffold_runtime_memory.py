from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_runtime_memory import (
    command_history_entry,
    error_signature,
    known_error_entry,
    runtime_file_index_payload,
    updated_command_history,
    updated_known_errors,
)
from aegis_ai.schemas import CommandRun, ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile


class ProjectScaffoldRuntimeMemoryTests(unittest.TestCase):
    def test_runtime_file_index_payload_records_workspace_profile(self) -> None:
        payload = runtime_file_index_payload(
            scaffold_preset("vite-react-ts", "Vite React TypeScript"),
            "aegis-app",
            files=[workspace_file("package.json"), workspace_file("src/App.tsx")],
            profile=WorkspaceDependencyProfile(project_type="web", frameworks=["React"]),
        )

        self.assertEqual(payload["schema"], "aegis.file_index.v1")
        self.assertEqual(payload["workspace_file_count"], 2)
        self.assertEqual(payload["files"][0]["path"], "package.json")
        self.assertEqual(payload["detected_profile"]["frameworks"], ["React"])

    def test_command_history_entry_records_passed_and_failed_runs(self) -> None:
        passed = command_history_entry(
            "validation",
            command_run(command="npm run build", exit_code=0, summary="Build passed."),
            fallback_command="npm run build",
            checkpoint="checkpoint-1",
            build_log_path=".aegis/build_logs/passed.md",
        )
        failed = command_history_entry(
            "validation",
            command_run(command="", exit_code=2, summary="Build failed.", timed_out=True),
            fallback_command="npm test",
            checkpoint=None,
            build_log_path=".aegis/build_logs/failed.md",
        )

        self.assertEqual(passed["status"], "passed")
        self.assertEqual(passed["checkpoint"], "checkpoint-1")
        self.assertEqual(passed["build_log_path"], ".aegis/build_logs/passed.md")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["command"], "npm test")
        self.assertTrue(failed["timed_out"])

    def test_updated_command_history_appends_runs_and_trims_to_recent_items(self) -> None:
        history = {
            "schema": "aegis.command_history.v1",
            "commands": [{"kind": "old", "command": f"cmd-{index}"} for index in range(79)],
        }

        updated = updated_command_history(
            history,
            checkpoint="checkpoint-2",
            install=command_run(command="npm install", exit_code=0),
            validation=None,
            install_command="npm install",
            validation_command="npm run build",
            build_log_path=".aegis/build_logs/run.md",
        )

        self.assertEqual(updated["install_command"], "npm install")
        self.assertEqual(updated["validation_command"], "npm run build")
        self.assertEqual(len(updated["commands"]), 80)
        self.assertEqual(updated["commands"][-2]["kind"], "install")
        self.assertEqual(updated["commands"][-1]["status"], "saved")
        self.assertEqual(updated["commands"][-1]["command"], "npm run build")

    def test_updated_command_history_recovers_from_malformed_command_list(self) -> None:
        updated = updated_command_history(
            {"schema": "aegis.command_history.v1", "commands": "bad"},
            checkpoint=None,
            install=None,
            validation=command_run(command="python build.py", exit_code=0),
            install_command="",
            validation_command="python build.py",
            build_log_path="",
        )

        self.assertEqual(len(updated["commands"]), 1)
        self.assertEqual(updated["commands"][0]["status"], "passed")
        self.assertNotIn("install_command", updated)

    def test_known_error_entry_and_update_capture_repair_context(self) -> None:
        validation = command_run(
            command="npm test",
            exit_code=1,
            category="test",
            summary="Test failed.",
            stdout="x" * 1500,
            diagnostics=[{"file": "src/app.ts", "line": 4, "message": "boom"}],
            failed_step="2",
            failed_step_command="npm test",
        )

        entry = known_error_entry(validation, build_log_path=".aegis/build_logs/failing.md")
        updated = updated_known_errors(
            {"schema": "aegis.known_errors.v1", "errors": [{"signature": f"old-{index}"} for index in range(60)]},
            validation,
            build_log_path=".aegis/build_logs/failing.md",
        )

        self.assertEqual(entry["status"], "open")
        self.assertEqual(entry["category"], "test")
        self.assertEqual(entry["failed_step"], "2")
        self.assertEqual(entry["build_log_path"], ".aegis/build_logs/failing.md")
        self.assertIn("output truncated", entry["output_excerpt"])
        self.assertEqual(len(updated["errors"]), 60)
        self.assertEqual(updated["errors"][-1]["signature"], entry["signature"])

    def test_error_signature_is_stable_for_same_failure_signal(self) -> None:
        first = command_run(command="npm test", exit_code=1, summary="failed", stdout="same")
        second = command_run(command="npm test", exit_code=1, summary="failed", stdout="same")
        different = command_run(command="npm test", exit_code=1, summary="failed", stdout="different")

        self.assertEqual(error_signature(first), error_signature(second))
        self.assertNotEqual(error_signature(first), error_signature(different))
        self.assertEqual(len(error_signature(first)), 16)


def command_run(
    *,
    command: str = "npm test",
    exit_code: int | None = 0,
    category: str = "validation",
    summary: str = "Command finished.",
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    diagnostics: list[dict[str, object]] | None = None,
    failed_step: str = "",
    failed_step_command: str = "",
) -> CommandRun:
    return CommandRun(
        command=command,
        cwd="workspace",
        allowed=True,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        reason=summary,
        category=category,
        summary=summary,
        steps=[],
        failed_step=failed_step,
        failed_step_command=failed_step_command,
        diagnostics=diagnostics or [],
    )


def scaffold_preset(preset_id: str, label: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id=preset_id,
        label=label,
        framework="test",
        language="test",
    )


def workspace_file(path: str) -> WorkspaceFile:
    return WorkspaceFile(
        path=path,
        kind="file",
        size=10,
        modified_at="2026-05-07T00:00:00Z",
    )


if __name__ == "__main__":
    unittest.main()
