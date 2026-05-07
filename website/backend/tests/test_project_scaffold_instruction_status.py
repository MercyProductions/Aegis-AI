from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_instruction_status import (
    first_pending_item,
    instruction_file_payloads,
    instruction_status_payload,
    validation_repair_target,
    validation_status_payload,
)
from aegis_ai.schemas import CommandRun, WorkspaceInstructionFile


class ProjectScaffoldInstructionStatusTests(unittest.TestCase):
    def test_instruction_status_payload_records_saved_validation_and_open_work(self) -> None:
        payload = instruction_status_payload(
            [
                instruction_file(
                    "ROADMAP.md",
                    pending_items=["  Build the first workflow  ", "Run validation"],
                    pending_count=2,
                    completed_count=1,
                    total_items=3,
                )
            ],
            prompt="Create a premium coding workstation",
            validation=None,
            validation_command="npm run build",
            build_log_path=".aegis/build_logs/latest.md",
            applied=[f"file-{index}.txt" for index in range(45)],
        )

        self.assertEqual(payload["schema"], "aegis.instruction_status.v1")
        self.assertEqual(payload["open_items"], 2)
        self.assertEqual(payload["completed_items"], 1)
        self.assertEqual(payload["last_validation"]["status"], "saved")
        self.assertEqual(payload["completion"]["status"], "needs_work")
        self.assertTrue(payload["completion"]["should_continue"])
        self.assertIn("Build the first workflow", payload["recommendation"])
        self.assertEqual(payload["applied"][0], "file-5.txt")
        self.assertEqual(len(payload["applied"]), 40)

    def test_failed_validation_blocks_expansion_with_diagnostic_repair_target(self) -> None:
        validation = command_run(
            command="npm run build",
            exit_code=1,
            diagnostics=[
                {
                    "file": "src/App.tsx",
                    "line": 7,
                    "column": 12,
                    "severity": "error",
                    "code": "TS2304",
                    "message": "Cannot find name AppShell.",
                }
            ],
        )

        payload = instruction_status_payload(
            [instruction_file("TODO.md", pending_items=["Fix build"], pending_count=1, total_items=1)],
            prompt="build it",
            validation=validation,
            validation_command="npm run build",
            build_log_path=".aegis/build_logs/failing.md",
            applied=["src/App.tsx"],
        )

        self.assertEqual(payload["last_validation"]["status"], "failed")
        self.assertEqual(payload["completion"]["status"], "blocked")
        self.assertEqual(payload["completion"]["score"], 0.2)
        self.assertIn("src/App.tsx:7:12 error TS2304", payload["recommendation"])
        self.assertIn("src/App.tsx:7:12 error TS2304", payload["completion"]["next_actions"][0])

    def test_ready_status_is_returned_when_validation_passes_and_no_items_remain(self) -> None:
        payload = instruction_status_payload(
            [instruction_file("ROADMAP.md", pending_items=[], pending_count=0, completed_count=2, total_items=2)],
            prompt="ship it",
            validation=command_run(command="python -m pytest", exit_code=0),
            validation_command="python -m pytest",
            build_log_path=".aegis/build_logs/passing.md",
            applied=["src/main.py"],
        )

        self.assertEqual(payload["last_validation"]["status"], "passed")
        self.assertEqual(payload["completion"]["status"], "ready")
        self.assertFalse(payload["completion"]["should_continue"])
        self.assertIn("All tracked instruction items are currently complete", payload["recommendation"])

    def test_instruction_file_payloads_filter_empty_pending_items_and_cap_files(self) -> None:
        payloads = instruction_file_payloads(
            [
                instruction_file(
                    f"TODO-{index}.md",
                    pending_items=["", "  Keep this  ", "x" * 260],
                    pending_count=2,
                    total_items=2,
                )
                for index in range(14)
            ]
        )

        self.assertEqual(len(payloads), 12)
        self.assertEqual(payloads[0]["pending_items"][0], "Keep this")
        self.assertLessEqual(len(payloads[0]["pending_items"][1]), 222)
        self.assertTrue(payloads[0]["pending_items"][1].endswith("..."))

    def test_validation_helpers_cover_not_run_and_fallback_repair_target(self) -> None:
        saved = validation_status_payload(None, validation_command="", build_log_path="")
        failed = command_run(command="", exit_code=2, diagnostics=[])

        self.assertEqual(saved["status"], "not_run")
        self.assertEqual(first_pending_item([instruction_file("TODO.md", pending_items=["  Next item  "])]), "Next item")
        self.assertEqual(validation_repair_target(failed, "npm test"), "the failure from `npm test`")


def command_run(
    *,
    command: str,
    exit_code: int | None,
    diagnostics: list[dict[str, object]] | None = None,
) -> CommandRun:
    return CommandRun(
        command=command,
        cwd="workspace",
        allowed=True,
        exit_code=exit_code,
        stdout="",
        stderr="",
        timed_out=False,
        reason="Command finished.",
        category="success" if exit_code == 0 else "build",
        summary="Command completed successfully." if exit_code == 0 else "Command failed.",
        steps=[],
        diagnostics=diagnostics or [],
    )


def instruction_file(
    path: str,
    *,
    pending_items: list[str],
    pending_count: int | None = None,
    completed_count: int = 0,
    total_items: int | None = None,
) -> WorkspaceInstructionFile:
    return WorkspaceInstructionFile(
        path=path,
        title=path,
        kind="roadmap",
        score=0.8,
        pending_count=len(pending_items) if pending_count is None else pending_count,
        completed_count=completed_count,
        total_items=len(pending_items) if total_items is None else total_items,
        pending_items=pending_items,
        summary="Tracked work.",
    )


if __name__ == "__main__":
    unittest.main()
