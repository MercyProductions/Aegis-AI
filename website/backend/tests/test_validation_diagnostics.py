from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.commands import CommandResult
from aegis_ai.validation_diagnostics import (
    diagnostic_brief,
    diagnostic_display,
    extract_validation_diagnostics,
    failed_step_display,
    failed_step_parts_from_steps,
    fenced_log_text,
    first_diagnostic_brief,
    first_diagnostic_display,
    normalize_diagnostic_path,
    repair_target_from_validation,
    status_text,
    strip_ansi,
    to_positive_int,
    validation_diagnostics_log,
    validation_steps_log,
)


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_normalizes_status_text_and_paths(self) -> None:
        self.assertEqual(status_text(" one\r\n two\tthree ", limit=20), "one two three")
        self.assertEqual(status_text("", default="fallback"), "fallback")
        self.assertEqual(strip_ansi("\x1b[31merror\x1b[0m"), "error")
        self.assertEqual(normalize_diagnostic_path(".././src\\main.ts"), "./src/main.ts")
        self.assertEqual(to_positive_int("42"), 42)
        self.assertIsNone(to_positive_int("0"))
        self.assertIsNone(to_positive_int("bad"))

    def test_extracts_msvc_typescript_and_gcc_diagnostics(self) -> None:
        result = command_result(
            stderr="\n".join(
                [
                    "src/app.ts(12,5): error TS2322: Type 'string' is not assignable.",
                    "src/app.ts(12,5): error TS2322: Type 'string' is not assignable.",
                    "src/main.cpp:42:13: fatal error: missing.h: No such file or directory",
                ]
            )
        )

        diagnostics = extract_validation_diagnostics(result)

        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(
            diagnostics[0],
            {
                "file": "src/app.ts",
                "line": 12,
                "column": 5,
                "severity": "error",
                "code": "TS2322",
                "message": "Type 'string' is not assignable.",
                "raw": "src/app.ts(12,5): error TS2322: Type 'string' is not assignable.",
            },
        )
        self.assertEqual(diagnostics[1]["file"], "src/main.cpp")
        self.assertEqual(diagnostics[1]["line"], 42)
        self.assertEqual(diagnostics[1]["column"], 13)
        self.assertEqual(diagnostics[1]["severity"], "error")

    def test_extracts_python_traceback_frames_with_followup_message(self) -> None:
        result = command_result(
            stderr='\n'.join(
                [
                    'Traceback (most recent call last):',
                    '  File "src/app.py", line 8, in main',
                    '    raise ValueError("bad")',
                    'ValueError: bad input',
                ]
            )
        )

        diagnostics = extract_validation_diagnostics(result)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["file"], "src/app.py")
        self.assertEqual(diagnostics[0]["line"], 8)
        self.assertEqual(diagnostics[0]["message"], 'raise ValueError("bad")')

    def test_formats_failed_steps_and_repair_targets(self) -> None:
        steps = [
            {"index": 1, "command": "npm install", "ok": True},
            {"index": 2, "command": "npm run build", "ok": False},
        ]

        self.assertEqual(failed_step_parts_from_steps(steps), ("2", "npm run build"))
        self.assertEqual(failed_step_display({"steps": steps}), "step 2: npm run build")
        self.assertEqual(
            repair_target_from_validation(
                {
                    "failed_step": 2,
                    "failed_step_command": "npm run build",
                    "diagnostics": [
                        {
                            "file": "src/app.ts",
                            "line": 12,
                            "severity": "error",
                            "code": "TS2322",
                            "message": "Bad type",
                        }
                    ],
                }
            ),
            "step 2: npm run build; first diagnostic src/app.ts:12 error TS2322: Bad type",
        )
        self.assertEqual(repair_target_from_validation({}, validation_command="npm test"), "npm test")

    def test_formats_diagnostics_for_display_and_logs(self) -> None:
        diagnostic = {
            "file": "src/app.ts",
            "line": 12,
            "column": 5,
            "severity": "error",
            "code": "TS2322",
            "message": "Bad type",
        }

        self.assertEqual(diagnostic_display(diagnostic), "src/app.ts:12:5 error TS2322: Bad type")
        self.assertEqual(diagnostic_brief(diagnostic), "src/app.ts:12:5 error TS2322")
        self.assertEqual(first_diagnostic_display({"diagnostics": [diagnostic]}), "src/app.ts:12:5 error TS2322: Bad type")
        self.assertEqual(first_diagnostic_brief({"diagnostics": [diagnostic]}), "src/app.ts:12:5 error TS2322")
        self.assertEqual(validation_diagnostics_log([diagnostic]), "- src/app.ts:12:5 error TS2322: Bad type")
        self.assertEqual(validation_diagnostics_log([]), "(none captured)")

    def test_formats_validation_steps_and_fenced_logs(self) -> None:
        self.assertEqual(fenced_log_text("```bad```\n"), "` ` `bad` ` `")
        self.assertEqual(validation_steps_log([]), "(single command)")
        self.assertEqual(
            validation_steps_log(
                [
                    {"index": 1, "command": "npm test", "ok": True, "exit_code": 0, "reason": ""},
                    {"index": 2, "command": "npm run build", "ok": False, "exit_code": 1, "reason": "Build failed."},
                    {"index": 3, "command": "npm run lint", "ok": False, "exit_code": None, "timed_out": True, "reason": "Timeout."},
                    {"index": 4, "command": "npm publish", "ok": False, "exit_code": None, "allowed": False, "reason": "Blocked."},
                ]
            ),
            "\n".join(
                [
                    "1. `npm test` - passed (exit: 0; )",
                    "2. `npm run build` - failed (exit: 1; Build failed.)",
                    "3. `npm run lint` - timed out (exit: n/a; Timeout.)",
                    "4. `npm publish` - blocked (exit: n/a; Blocked.)",
                ]
            ),
        )


def command_result(
    *,
    command: str = "npm run validate",
    stdout: str = "",
    stderr: str = "",
    reason: str = "",
    steps: list[dict[str, object]] | None = None,
) -> CommandResult:
    return CommandResult(
        command=command,
        cwd="workspace",
        allowed=True,
        exit_code=1,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        reason=reason,
        steps=steps or [],
    )


if __name__ == "__main__":
    unittest.main()
