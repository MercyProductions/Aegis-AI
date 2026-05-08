from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.commands import CommandResult
from aegis_ai.project_scaffold_reporting import (
    categorize_command_result,
    command_excerpt,
    command_ok,
    command_run,
    diagnostic_display,
    diagnostics_log,
    extract_validation_diagnostics,
    failed_step_parts_from_steps,
    log_text,
    normalize_diagnostic_path,
    status_text,
    strip_ansi,
    summarize_command_result,
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

    def test_command_run_classifies_summarizes_and_keeps_failed_step(self) -> None:
        result = command_result(
            command="npx tsc --noEmit",
            stderr="src/app.ts(3,4): error TS2322: Type 'string' is not assignable.",
            steps=[
                {"index": 1, "command": "npm install", "ok": True},
                {"index": 2, "command": "npm run build", "ok": False},
            ],
        )

        run = command_run(result, label="Validation")

        self.assertFalse(command_ok(run))
        self.assertEqual(run.category, "typecheck")
        self.assertEqual(run.summary, "Validation failed with a type-checking error.")
        self.assertEqual(run.failed_step, "2")
        self.assertEqual(run.failed_step_command, "npm run build")
        self.assertIn("[stderr]", command_excerpt(run))
        self.assertEqual(len(run.diagnostics), 1)

    def test_command_result_categories_cover_terminal_states(self) -> None:
        self.assertEqual(categorize_command_result(command_result(exit_code=0)), "success")
        self.assertEqual(categorize_command_result(command_result(timed_out=True, reason="timeout")), "timeout")
        self.assertEqual(categorize_command_result(command_result(allowed=False, reason="blocked")), "permission")
        self.assertEqual(categorize_command_result(command_result(stderr="Module not found: react")), "dependency")
        self.assertEqual(categorize_command_result(command_result(stderr="SyntaxError: bad token")), "syntax")
        self.assertEqual(categorize_command_result(command_result(stderr="AssertionError: expected true")), "test")
        self.assertEqual(categorize_command_result(command_result(command="python app.py", stderr="Traceback ValueError")), "runtime")

    def test_summarize_command_result_uses_label_and_block_reason(self) -> None:
        self.assertEqual(
            summarize_command_result(command_result(exit_code=0), category="success", label="Validation"),
            "Validation completed successfully.",
        )
        self.assertEqual(
            summarize_command_result(command_result(timed_out=True), category="timeout", label="Validation"),
            "Validation timed out before finishing.",
        )
        self.assertEqual(
            summarize_command_result(command_result(allowed=False, reason="Blocked by policy"), category="permission", label="Install"),
            "Blocked by policy",
        )


def command_result(
    *,
    command: str = "npm run build",
    stdout: str = "",
    stderr: str = "",
    reason: str = "",
    allowed: bool = True,
    exit_code: int | None = 1,
    timed_out: bool = False,
    steps: list[dict[str, object]] | None = None,
) -> CommandResult:
    return CommandResult(
        command=command,
        cwd="workspace",
        allowed=allowed,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        reason=reason,
        steps=steps or [],
    )


if __name__ == "__main__":
    unittest.main()
