from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.commands import CommandResult
from aegis_ai.project_scaffold_reporting import (
    diagnostic_display,
    diagnostics_log,
    extract_validation_diagnostics,
    failed_step_parts_from_steps,
    log_text,
    normalize_diagnostic_path,
    status_text,
    strip_ansi,
    to_positive_int,
)


class ProjectScaffoldReportingTests(unittest.TestCase):
    def test_status_and_log_text_match_scaffold_reporting_contract(self) -> None:
        self.assertEqual(status_text(" one\r\n two\tthree ", limit=20), "one two three")
        self.assertEqual(status_text("", default="fallback"), "fallback")
        self.assertEqual(status_text("abcdef", limit=4), "abc...")
        self.assertEqual(log_text(""), "(empty)")
        self.assertEqual(log_text("abcdef", limit=3), "abc\n... output truncated ...")

    def test_failed_step_parts_select_first_failed_step(self) -> None:
        self.assertEqual(
            failed_step_parts_from_steps(
                [
                    {"index": 1, "command": "npm install", "ok": True},
                    {"index": 2, "command": "npm run build", "ok": False},
                ]
            ),
            ("2", "npm run build"),
        )
        self.assertEqual(failed_step_parts_from_steps([{"index": 1, "command": "npm test", "ok": True}]), ("", ""))

    def test_normalizes_diagnostic_primitives(self) -> None:
        self.assertEqual(strip_ansi("\x1b[31merror\x1b[0m"), "error")
        self.assertEqual(normalize_diagnostic_path(".././src\\main.ts"), "./src/main.ts")
        self.assertEqual(to_positive_int("12"), 12)
        self.assertIsNone(to_positive_int("0"))
        self.assertIsNone(to_positive_int("bad"))

    def test_extracts_and_formats_validation_diagnostics(self) -> None:
        result = command_result(
            stderr="\n".join(
                [
                    "app/page.tsx(7,12): error TS2304: Cannot find name 'AppShell'.",
                    "app/page.tsx(7,12): error TS2304: Cannot find name 'AppShell'.",
                    "src/main.cpp:42:13: fatal error: missing.h: No such file or directory",
                ]
            )
        )

        diagnostics = extract_validation_diagnostics(result)

        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(diagnostics[0]["file"], "app/page.tsx")
        self.assertEqual(diagnostics[0]["line"], 7)
        self.assertEqual(diagnostics[0]["column"], 12)
        self.assertEqual(diagnostics[0]["severity"], "error")
        self.assertEqual(diagnostics[0]["code"], "TS2304")
        self.assertIn("AppShell", diagnostics[0]["message"])
        self.assertEqual(diagnostic_display(diagnostics[0]), "app/page.tsx:7:12 error TS2304: Cannot find name 'AppShell'.")
        self.assertIn("- app/page.tsx:7:12 error TS2304", diagnostics_log(diagnostics))

    def test_extracts_python_traceback_frame(self) -> None:
        result = command_result(
            stderr="\n".join(
                [
                    "Traceback (most recent call last):",
                    '  File "src/app.py", line 8, in main',
                    "    raise ValueError('bad')",
                    "ValueError: bad",
                ]
            )
        )

        diagnostics = extract_validation_diagnostics(result)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["file"], "src/app.py")
        self.assertEqual(diagnostics[0]["line"], 8)
        self.assertEqual(diagnostics[0]["message"], "raise ValueError('bad')")


def command_result(*, stdout: str = "", stderr: str = "", reason: str = "") -> CommandResult:
    return CommandResult(
        command="npm run build",
        cwd="workspace",
        allowed=True,
        exit_code=1,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        reason=reason,
        steps=[],
    )


if __name__ == "__main__":
    unittest.main()
