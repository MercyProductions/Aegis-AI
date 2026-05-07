from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.context_formatting import (
    format_fix_memory_context,
    format_instruction_file_context,
    format_project_intelligence_context,
    format_project_memory_context,
    format_task_history_context,
)


class ContextFormattingTests(unittest.TestCase):
    def test_formats_fix_memory_context_with_stable_limits(self) -> None:
        entries = [
            SimpleNamespace(
                category=f"cat-{index}",
                confidence=0.75,
                error_signature=f"error line {index}\nwith detail",
                fix_summary=f"fix line {index}\nwith detail",
            )
            for index in range(6)
        ]

        context = format_fix_memory_context(entries)

        self.assertIn("[cat-0] confidence=0.75", context)
        self.assertIn("error line 0 with detail", context)
        self.assertIn("fix line 0 with detail", context)
        self.assertIn("cat-4", context)
        self.assertNotIn("cat-5", context)

    def test_formats_task_history_context_with_recent_task_limits(self) -> None:
        tasks = [
            SimpleNamespace(
                status="completed",
                mode="develop",
                created_at=f"2026-05-0{index}",
                message=f"task {index}\nmessage",
            )
            for index in range(1, 8)
        ]

        context = format_task_history_context(tasks)

        self.assertIn("[completed] develop at 2026-05-01: task 1 message", context)
        self.assertIn("task 6 message", context)
        self.assertNotIn("task 7 message", context)

    def test_formats_project_memory_context(self) -> None:
        entries = [
            SimpleNamespace(category="preference", title="Use pytest", detail="Keep backend tests focused.\nAvoid broad fixtures.")
        ]

        context = format_project_memory_context(entries)

        self.assertEqual(context, "- [preference] Use pytest: Keep backend tests focused. Avoid broad fixtures.")

    def test_formats_project_intelligence_context_with_bounded_sections(self) -> None:
        intelligence = SimpleNamespace(
            profile=SimpleNamespace(
                project_name="",
                stack=[f"stack-{index}" for index in range(11)],
                main_entry_files=[f"entry-{index}.py" for index in range(9)],
                coding_conventions=[f"rule-{index}" for index in range(6)],
            ),
            validation_commands=[f"validate-{index}" for index in range(6)],
            file_importance=[SimpleNamespace(path=f"file-{index}.py") for index in range(11)],
            architecture=SimpleNamespace(
                api_routes=[SimpleNamespace(method="GET", path=f"/route-{index}") for index in range(9)]
            ),
            recommendations=[f"note-{index}" for index in range(5)],
        )

        context = format_project_intelligence_context(intelligence, workspace_name="Workspace")

        self.assertIn("Project intelligence: Workspace", context)
        self.assertIn("stack-9", context)
        self.assertNotIn("stack-10", context)
        self.assertIn("entry-7.py", context)
        self.assertNotIn("entry-8.py", context)
        self.assertIn("rule-4", context)
        self.assertNotIn("rule-5", context)
        self.assertIn("validate-4", context)
        self.assertNotIn("validate-5", context)
        self.assertIn("file-9.py", context)
        self.assertNotIn("file-10.py", context)
        self.assertIn("GET /route-7", context)
        self.assertNotIn("GET /route-8", context)
        self.assertIn("note-3", context)
        self.assertNotIn("note-4", context)

    def test_formats_instruction_file_context_with_rule_and_bounded_pending_items(self) -> None:
        instruction_files = [
            SimpleNamespace(
                path="TODO.md",
                kind="todo",
                score=0.91,
                title="Project TODO",
                summary="Core workflow polish",
                pending_items=[f"item {index}" for index in range(10)],
                excerpt="line one\nline two",
            )
        ]

        context = format_instruction_file_context(instruction_files)

        self.assertIn("- TODO.md [todo, score=0.91]: Project TODO (Core workflow polish)", context)
        self.assertIn("Open items: item 0; item 1", context)
        self.assertIn("item 7", context)
        self.assertNotIn("item 8", context)
        self.assertIn("Excerpt: line one / line two", context)
        self.assertIn("Instruction rule:", context)
        self.assertEqual(format_instruction_file_context([]), "")


if __name__ == "__main__":
    unittest.main()
