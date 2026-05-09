from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.workspace_autopilot import (
    build_workspace_autopilot_status,
    compact_repair_brief,
    compact_validation_repair_brief,
    first_diagnostic_brief,
    latest_history_validation,
    remembered_validation_command,
    status_value,
)
from aegis_ai.schemas import (
    WorkspaceDependencyProfile,
    WorkspaceInstructionStatusFile,
    WorkspaceInstructionStatusInfo,
    WorkspaceProjectManifest,
    WorkspaceReadinessInfo,
    WorkspaceValidationPlanInfo,
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

    def test_latest_history_validation_skips_unsafe_validation_commands(self) -> None:
        history = {
            "validation_command": "npm.cmd install",
            "commands": [
                {"kind": "validation", "status": "passed", "command": "npm test"},
                {"kind": "validation", "status": "passed", "command": "cmd.exe /c npm install"},
            ],
        }

        self.assertEqual(
            latest_history_validation(history),
            {"kind": "validation", "status": "passed", "command": "npm test"},
        )
        self.assertEqual(remembered_validation_command(history), "")

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

    def test_compact_validation_repair_brief_preserves_planner_failed_step_wording(self) -> None:
        self.assertEqual(
            compact_validation_repair_brief(
                {
                    "failed_step": "2",
                    "failed_step_command": "npm run build",
                    "diagnostics": [
                        {
                            "file": "src/app.ts",
                            "line": 10,
                            "severity": "error",
                            "code": "TS2322",
                        }
                    ],
                }
            ),
            "Repair step 2: npm run build; diagnostic src/app.ts:10 error TS2322; rerun validation",
        )

    def test_compact_validation_repair_brief_keeps_step_only_legacy_fallback(self) -> None:
        self.assertEqual(
            compact_validation_repair_brief({"failed_step": "2"}, validation_command="npm run build"),
            "Repair 2; rerun validation",
        )

    def test_build_workspace_autopilot_status_summarizes_repair_state(self) -> None:
        status = build_workspace_autopilot_status(
            workspace_root="C:/work/app",
            manifest=WorkspaceProjectManifest(
                schema="aegis.project.v1",
                project_name="app",
                framework="React + FastAPI",
                language="TypeScript + Python",
                validation_command="npm run build",
                tags=["database"],
            ),
            dependency_profile=WorkspaceDependencyProfile(
                frameworks=["React", "FastAPI"],
                database_tools=["sqlite"],
                validation_commands=["npm run build"],
            ),
            instruction_status=WorkspaceInstructionStatusInfo(
                open_items=2,
                completed_items=1,
                total_items=3,
                files=[
                    WorkspaceInstructionStatusFile(
                        path="TODO.md",
                        title="Plan",
                        kind="instruction",
                        open_items=2,
                        completed_items=1,
                        total_items=3,
                        pending_items=["Repair validation.", "Repair validation.", "Update docs."],
                    )
                ],
            ),
            validation_plan=WorkspaceValidationPlanInfo(validation_command="npm run build"),
            command_history={
                "commands": [
                    {
                        "kind": "validation",
                        "status": "failed",
                        "command": "npm run build",
                        "failed_step": "2",
                        "failed_step_command": "npm test",
                        "diagnostics": [
                            {
                                "file": "src/app.ts",
                                "line": 10,
                                "severity": "error",
                                "code": "TS2322",
                            }
                        ],
                    }
                ],
            },
            readiness=WorkspaceReadinessInfo(
                status="needs_repair",
                score=28,
                summary="Validation failed.",
                next_action="Repair npm test.",
            ),
        )

        self.assertEqual(status.phase, "repair")
        self.assertTrue(status.should_continue)
        self.assertEqual(status.validation_command, "npm run build")
        self.assertEqual(status.first_diagnostic, "src/app.ts:10 error TS2322")
        self.assertIn("Repair step 2: npm test", status.repair_brief)
        self.assertEqual(status.next_open_items, ["Repair validation.", "Update docs."])
        self.assertIn("frontend", status.execution_lanes)
        self.assertIn("backend", status.execution_lanes)
        self.assertIn("database", status.execution_lanes)
        self.assertIn("roadmap", status.execution_lanes)


if __name__ == "__main__":
    unittest.main()
