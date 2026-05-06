from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.prompt_intent import (
    prompt_has_explanation_prefix,
    prompt_requests_execution_validation,
)


class PromptIntentTests(unittest.TestCase):
    def test_execution_validation_matrix_recognizes_action_phrases(self) -> None:
        true_cases = [
            "build it",
            "build and run it please",
            "launch the app",
            "start the project",
            "execute it please",
            "run the project",
            "verify this",
            "verify the build",
            "check for errors",
            "compile this and make sure there are no errors",
            "compile the app",
            "you didn't build it",
            "fix any errors",
            "continue from the last failed build",
            "rerun the build",
            "rerun validation",
            "try building again",
            "run it again",
        ]

        for prompt in true_cases:
            with self.subTest(prompt=prompt):
                self.assertTrue(prompt_requests_execution_validation(prompt))

    def test_execution_validation_matrix_avoids_explanatory_and_creation_prompts(self) -> None:
        false_cases = [
            "",
            "build a website for a barber shop",
            "create a C++ console project",
            "explain how build systems work",
            "how do I launch it?",
            "show me how to start it",
            "what command should I run?",
        ]

        for prompt in false_cases:
            with self.subTest(prompt=prompt):
                self.assertFalse(prompt_requests_execution_validation(prompt))

    def test_extra_terms_extend_shared_validation_without_changing_base_cases(self) -> None:
        self.assertFalse(prompt_requests_execution_validation("create a service with tests"))
        self.assertTrue(
            prompt_requests_execution_validation(
                "create a service with tests",
                extra_phrases=("with tests",),
            )
        )
        self.assertTrue(
            prompt_requests_execution_validation(
                "Create a full-stack CRUD dashboard with frontend, backend, tests, and validation.",
                extra_phrases=("tests", "and validation"),
            )
        )
        self.assertTrue(prompt_requests_execution_validation("please build/run this"))

    def test_explanation_prefix_detection_is_case_and_spacing_tolerant(self) -> None:
        self.assertTrue(prompt_has_explanation_prefix("  HOW   do   I   run it? "))
        self.assertTrue(prompt_has_explanation_prefix("Can you explain how to validate it?"))
        self.assertFalse(prompt_has_explanation_prefix("please run it"))


if __name__ == "__main__":
    unittest.main()
