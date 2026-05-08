from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_memory_notes import extract_project_notes, memory_title_for


class ProjectMemoryNoteTests(unittest.TestCase):
    def test_extracts_constraints_preferences_architecture_and_environment_notes(self) -> None:
        notes = extract_project_notes(
            "\n".join(
                [
                    "Do not change the authentication flow without explicit approval.",
                    "Prefer pytest tests for backend validation around repair loops.",
                    "The backend API should stay FastAPI with SQLite storage.",
                    "Windows PowerShell commands are the local validation shell.",
                ]
            )
        )

        self.assertEqual([note["category"] for note in notes], ["constraint", "preference", "architecture", "environment"])
        self.assertEqual([note["title"] for note in notes], ["Constraint", "Preference", "Architecture", "Environment"])
        self.assertEqual(notes[0]["confidence"], 0.86)
        self.assertEqual(notes[1]["confidence"], 0.78)
        self.assertEqual(notes[2]["confidence"], 0.68)
        self.assertEqual(notes[3]["confidence"], 0.66)

    def test_extract_project_notes_filters_short_long_unclassified_and_duplicate_segments(self) -> None:
        long_segment = "x" * 221
        notes = extract_project_notes(
            "\n".join(
                [
                    "Use rust",
                    "This sentence does not contain a tracked project memory marker.",
                    long_segment,
                    "Never rewrite the runtime during a UI polish pass.",
                    "Never rewrite the runtime during a UI polish pass.",
                    "Keep validation output concise for repair summaries.",
                    "Windows PowerShell command examples are required locally.",
                    "The React frontend workspace panels remain calm and focused.",
                    "Do not add new platform concepts during hardening.",
                    "Prefer small modular changes over broad rewrites.",
                ]
            )
        )

        self.assertEqual(len(notes), 4)
        self.assertEqual(notes[0]["detail"], "Never rewrite the runtime during a UI polish pass")
        self.assertEqual(notes[1]["category"], "preference")
        self.assertEqual(notes[2]["category"], "environment")
        self.assertEqual(notes[3]["category"], "architecture")

    def test_memory_title_for_uses_category_labels_and_generic_fallback(self) -> None:
        self.assertEqual(memory_title_for("constraint", "Never rewrite runtime"), "Constraint")
        self.assertEqual(memory_title_for("preference", "Prefer pytest"), "Preference")
        self.assertEqual(memory_title_for("architecture", "React frontend"), "Architecture")
        self.assertEqual(memory_title_for("environment", "Windows PowerShell"), "Environment")
        self.assertEqual(memory_title_for("decision", 'Use "typed" helpers for routing behavior'), "Use 'typed' helpers for")
        self.assertEqual(memory_title_for("decision", ""), "Note")


if __name__ == "__main__":
    unittest.main()
