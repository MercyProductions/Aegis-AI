from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.workspace_autopilot import (
    compact_repair_brief,
    first_diagnostic_brief,
    latest_history_validation,
    status_value,
)


class WorkspaceAutopilotHelperTests(unittest.TestCase):
    def test_latest_history_validation_uses_most_recent_validation_like_command(self) -> None:
        history = {
            "commands": [
                {"kind": "shell", "command": "npm install"},
                {"kind": "validation", "status": "passed", "command": "npm test"},
                {"kind": "verification:smoke", "status": "failed", "command": "npm run smoke"},
                {"kind": "shell", "command": "echo done"},
            ],
        }

        self.assertEqual(
            latest_history_validation(history),
            {"kind": "verification:smoke", "status": "failed", "command": "npm run smoke"},
        )

    def test_latest_history_validation_ignores_malformed_history(self) -> None:
        self.assertEqual(latest_history_validation({"commands": "npm test"}), {})
        self.assertEqual(latest_history_validation({"commands": [None, {"kind": "shell"}]}), {})

    def test_status_value_strips_and_truncates_long_values(self) -> None:
        self.assertEqual(status_value("  ok  "), "ok")
        self.assertEqual(status_value("abcdef", limit=4), "abcd...")
        self.assertEqual(status_value(None), "")

    def test_first_diagnostic_brief_returns_location_and_error_identity(self) -> None:
        payload = {
            "diagnostics": [
                "not-a-diagnostic",
                {},
                {
                    "file": "src/main.cpp",
                    "line": 17,
                    "column": 5,
                    "severity": "error",
                    "code": "C2143",
                    "message": "syntax error",
                },
            ],
        }

        self.assertEqual(first_diagnostic_brief(payload), "src/main.cpp:17:5 error C2143")

    def test_compact_repair_brief_prefers_failed_step_command_then_diagnostic(self) -> None:
        payload = {
            "command": "python build.py",
            "failed_step": "2",
            "failed_step_command": "python build.py --smoke",
            "diagnostics": [
                {
                    "file": "src/main.cpp",
                    "line": 17,
                    "column": 5,
                    "severity": "error",
                    "code": "C2143",
                }
            ],
        }

        self.assertEqual(
            compact_repair_brief(payload, validation_command="python build.py"),
            "Repair step 2: python build.py --smoke; diagnostic src/main.cpp:17:5 error C2143; rerun validation",
        )

    def test_compact_repair_brief_falls_back_to_validation_command(self) -> None:
        self.assertEqual(
            compact_repair_brief({}, validation_command="npm run build"),
            "Repair npm run build; rerun validation",
        )


if __name__ == "__main__":
    unittest.main()
