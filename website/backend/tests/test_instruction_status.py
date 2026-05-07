from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.instruction_status import instruction_status_from_discovered_files
from aegis_ai.schemas import WorkspaceInstructionFile


class InstructionStatusTests(unittest.TestCase):
    def test_instruction_status_from_discovered_files_tracks_open_items_and_recommendation(self) -> None:
        snapshot = instruction_status_from_discovered_files(
            [
                instruction_file(
                    path="TODO.md",
                    pending_count=2,
                    completed_count=1,
                    total_items=3,
                    pending_items=[
                        "  Add build command  ",
                        "Validate release build",
                    ],
                    summary="Launch plan",
                )
            ],
            updated_at="2026-05-07T10:00:00Z",
        )

        self.assertEqual(snapshot.schema_version, "aegis.instruction_status.discovered.v1")
        self.assertEqual(snapshot.updated_at, "2026-05-07T10:00:00Z")
        self.assertEqual(snapshot.source_message, "Discovered workspace instruction files.")
        self.assertEqual(snapshot.instruction_file_count, 1)
        self.assertEqual(snapshot.open_items, 2)
        self.assertEqual(snapshot.completed_items, 1)
        self.assertEqual(snapshot.total_items, 3)
        self.assertEqual(snapshot.files[0].path, "TODO.md")
        self.assertEqual(snapshot.files[0].pending_items, ["Add build command", "Validate release build"])
        self.assertEqual(snapshot.last_validation, {"status": "not_run", "command": "", "summary": ""})
        self.assertEqual(snapshot.completion["status"], "needs_work")
        self.assertTrue(snapshot.completion["should_continue"])
        self.assertIn("Add build command", snapshot.recommendation)
        self.assertEqual(snapshot.completion["next_actions"], [snapshot.recommendation])

    def test_instruction_status_from_discovered_files_marks_complete_when_no_open_items(self) -> None:
        snapshot = instruction_status_from_discovered_files(
            [
                instruction_file(
                    path="DONE.md",
                    pending_count=0,
                    completed_count=3,
                    total_items=3,
                    pending_items=[],
                )
            ],
            updated_at="2026-05-07T10:00:00Z",
        )

        self.assertEqual(snapshot.open_items, 0)
        self.assertEqual(snapshot.completed_items, 3)
        self.assertEqual(snapshot.total_items, 3)
        self.assertEqual(snapshot.completion["status"], "ready")
        self.assertFalse(snapshot.completion["should_continue"])
        self.assertIn("summarize the finished state", snapshot.recommendation)

    def test_instruction_status_from_discovered_files_caps_files_and_pending_items(self) -> None:
        files = [
            instruction_file(
                path=f"TODO-{index}.md",
                pending_count=1,
                total_items=1,
                pending_items=[f"item {index}-{pending}" for pending in range(12)],
            )
            for index in range(14)
        ]

        snapshot = instruction_status_from_discovered_files(files, updated_at="now")

        self.assertEqual(snapshot.instruction_file_count, 12)
        self.assertEqual(len(snapshot.files), 12)
        self.assertEqual(snapshot.open_items, 14)
        self.assertEqual(snapshot.total_items, 14)
        self.assertEqual(len(snapshot.files[0].pending_items), 10)
        self.assertIn("item 0-0", snapshot.recommendation)
        self.assertNotIn("item 12", "\n".join(item.path for item in snapshot.files))

    def test_instruction_status_from_discovered_files_uses_generic_recommendation_when_counts_are_stale(self) -> None:
        snapshot = instruction_status_from_discovered_files(
            [
                instruction_file(
                    path="STALE.md",
                    pending_count=2,
                    completed_count=0,
                    total_items=2,
                    pending_items=["  ", "\t"],
                )
            ],
            updated_at="now",
        )

        self.assertEqual(snapshot.recommendation, "Continue the next open instruction item.")
        self.assertEqual(snapshot.completion["next_actions"], ["Continue the next open instruction item."])


def instruction_file(
    *,
    path: str,
    title: str = "Project TODO",
    kind: str = "todo",
    score: float = 0.9,
    pending_count: int = 0,
    completed_count: int = 0,
    total_items: int = 0,
    pending_items: list[str] | None = None,
    summary: str = "Project instructions",
) -> WorkspaceInstructionFile:
    return WorkspaceInstructionFile(
        path=path,
        title=title,
        kind=kind,
        score=score,
        pending_count=pending_count,
        completed_count=completed_count,
        total_items=total_items,
        pending_items=pending_items or [],
        summary=summary,
    )


if __name__ == "__main__":
    unittest.main()
