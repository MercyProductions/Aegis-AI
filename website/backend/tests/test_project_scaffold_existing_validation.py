from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_existing_validation import (
    EXISTING_PROJECT_MODE_WARNING,
    existing_project_install_stage,
    existing_project_memory_stage,
    existing_project_next_steps,
    existing_project_preamble_stages,
    existing_project_repair_stage,
    existing_project_skipped_validation_stage,
)
from aegis_ai.schemas import CommandRun


class ProjectScaffoldExistingValidationTests(unittest.TestCase):
    def test_existing_project_preamble_stages_make_no_file_changes(self) -> None:
        stages = existing_project_preamble_stages()

        self.assertIn("skipped starter-file generation", EXISTING_PROJECT_MODE_WARNING)
        self.assertEqual([stage.id for stage in stages], ["structure", "diff", "apply"])
        self.assertEqual([stage.status for stage in stages], ["skipped", "succeeded", "skipped"])
        self.assertIn("No starter files", stages[1].detail)
        self.assertIn("No file changes", stages[2].detail)

    def test_install_and_skipped_validation_stages_capture_commands(self) -> None:
        install = existing_project_install_stage("npm install")
        no_install = existing_project_install_stage("")
        validation = existing_project_skipped_validation_stage("npm run build")
        unknown_validation = existing_project_skipped_validation_stage("")

        self.assertEqual(install.status, "skipped")
        self.assertIn("captured but not run", install.detail)
        self.assertEqual(no_install.status, "planned")
        self.assertEqual(validation.status, "skipped")
        self.assertIn("saved", validation.detail)
        self.assertEqual(unknown_validation.status, "planned")
        self.assertIn("could be inferred", unknown_validation.detail)

    def test_repair_stage_tracks_failed_passed_and_missing_validation(self) -> None:
        failed = existing_project_repair_stage(
            command_run(exit_code=1, summary="Validation failed.", stdout="failure output"),
            validation_command="npm test",
        )
        blocked = existing_project_repair_stage(
            command_run(exit_code=None, allowed=False, summary="Command blocked."),
            validation_command="git reset --hard",
        )
        passed = existing_project_repair_stage(
            command_run(exit_code=0, summary="Validation completed successfully."),
            validation_command="npm test",
        )
        missing = existing_project_repair_stage(None, validation_command="npm test")

        self.assertEqual(failed.status, "planned")
        self.assertEqual(failed.error, "Validation failed.")
        self.assertIn("failure output", failed.output_excerpt)
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(passed.status, "skipped")
        self.assertIn("passed", passed.detail)
        self.assertEqual(missing.status, "skipped")
        self.assertIn("No validation output", missing.detail)

    def test_memory_stage_and_next_steps_reflect_validation_state(self) -> None:
        clean_memory = existing_project_memory_stage(apply=True, warnings=[])
        warning_memory = existing_project_memory_stage(apply=True, warnings=["file index failed", "history failed", "extra"])
        preview_memory = existing_project_memory_stage(apply=False, warnings=[])
        passed_steps = existing_project_next_steps(Path("workspace"), command_run(exit_code=0))
        failed_steps = existing_project_next_steps(Path("workspace"), command_run(exit_code=1))

        self.assertEqual(clean_memory.status, "succeeded")
        self.assertIn("known-error memory", clean_memory.detail)
        self.assertIn("file index failed; history failed", warning_memory.detail)
        self.assertNotIn("extra", warning_memory.detail)
        self.assertEqual(preview_memory.status, "skipped")
        self.assertIn("Validation passed", passed_steps[1])
        self.assertIn("repair loop", failed_steps[1])
        self.assertIn("workspace", passed_steps[0])


def command_run(
    *,
    exit_code: int | None,
    allowed: bool = True,
    summary: str = "Command finished.",
    stdout: str = "",
) -> CommandRun:
    return CommandRun(
        command="npm test",
        cwd="workspace",
        allowed=allowed,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        timed_out=False,
        reason=summary,
        category="success" if exit_code == 0 else "test",
        summary=summary,
    )


if __name__ == "__main__":
    unittest.main()
