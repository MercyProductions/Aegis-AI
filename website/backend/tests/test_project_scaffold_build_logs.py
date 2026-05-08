from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_build_logs import (
    build_log_content,
    command_log_section,
    write_build_log,
)
from aegis_ai.schemas import CommandRun, ProjectScaffoldPreset


class ProjectScaffoldBuildLogTests(unittest.TestCase):
    def test_command_log_section_records_diagnostics_and_output(self) -> None:
        section = command_log_section(
            "Validation",
            command_run(
                command="npm run build",
                exit_code=2,
                stdout="src/app.tsx(7,12): error TS2304: Cannot find name 'AppShell'.\n",
                reason="Run build/test validation failed.",
                diagnostics=[
                    {
                        "file": "src/app.tsx",
                        "line": 7,
                        "column": 12,
                        "severity": "error",
                        "code": "TS2304",
                        "message": "Cannot find name 'AppShell'.",
                    }
                ],
            ),
        )

        self.assertIn("## Validation", section)
        self.assertIn("Exit code: 2", section)
        self.assertIn("### Diagnostics", section)
        self.assertIn("src/app.tsx:7:12 error TS2304", section)
        self.assertIn("Cannot find name 'AppShell'", section)
        self.assertIn("Run build/test validation failed.", section)

    def test_build_log_content_combines_install_and_validation_sections(self) -> None:
        content = build_log_content(
            preset=scaffold_preset("Vite React TypeScript"),
            project_name="aegis-app",
            checkpoint="checkpoint-123",
            install=command_run(command="npm install", stdout="install ok\n"),
            validation=command_run(command="npm run build", stdout="build ok\n"),
            install_command="npm install",
            validation_command="npm run build",
        )

        self.assertIn("# Aegis Build Log", content)
        self.assertIn("- Project: Aegis App", content)
        self.assertIn("- Preset: Vite React TypeScript", content)
        self.assertIn("- Checkpoint: checkpoint-123", content)
        self.assertIn("## Install", content)
        self.assertIn("install ok", content)
        self.assertIn("## Validation", content)
        self.assertIn("build ok", content)
        self.assertTrue(content.endswith("\n"))

    def test_write_build_log_skips_empty_runs_and_writes_markdown_log(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            preset = scaffold_preset("Python CLI")

            self.assertEqual(
                write_build_log(
                    target,
                    preset=preset,
                    project_name="aegis-tool",
                    checkpoint=None,
                    install=None,
                    validation=None,
                    install_command="",
                    validation_command="python build.py",
                ),
                "",
            )
            self.assertFalse((target / ".aegis").exists())

            relative_path = write_build_log(
                target,
                preset=preset,
                project_name="aegis-tool",
                checkpoint=None,
                install=None,
                validation=command_run(command="python build.py", stdout="ok\n"),
                install_command="",
                validation_command="python build.py",
            )

            self.assertTrue(relative_path.startswith(".aegis/build_logs/"))
            self.assertTrue(relative_path.endswith(".md"))
            content = (target / relative_path).read_text(encoding="utf-8")
            self.assertIn("Python CLI", content)
            self.assertIn("python build.py", content)
            self.assertIn("ok", content)


def command_run(
    *,
    command: str = "npm test",
    exit_code: int | None = 0,
    stdout: str = "",
    stderr: str = "",
    reason: str = "Command finished.",
    diagnostics: list[dict[str, object]] | None = None,
) -> CommandRun:
    return CommandRun(
        command=command,
        cwd="workspace",
        allowed=True,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        reason=reason,
        category="validation",
        summary=reason,
        steps=[],
        failed_step="",
        failed_step_command="",
        diagnostics=diagnostics or [],
    )


def scaffold_preset(label: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id="test-preset",
        label=label,
        framework="test",
        language="test",
    )


if __name__ == "__main__":
    unittest.main()
