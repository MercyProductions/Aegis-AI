from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_stack_rules import (
    preset_stack_locks,
    prompt_allows_stack_switch,
    prompt_negates_web_stack,
    stack_family_for_preset,
    stack_lock_keywords_for_prompt,
    stack_locks_conflict_with_preset,
)


class ProjectScaffoldStackRuleTests(unittest.TestCase):
    def test_prompt_negates_web_stack_detects_preserve_native_language(self) -> None:
        self.assertTrue(prompt_negates_web_stack("Keep this native DLL project and do not make it a website."))
        self.assertTrue(prompt_negates_web_stack("Add a frontend-style diagnostics dashboard, but not a web app."))
        self.assertFalse(prompt_negates_web_stack("Create a polished web app dashboard."))

    def test_preset_stack_locks_cover_core_families(self) -> None:
        self.assertEqual(
            preset_stack_locks("cpp-cmake-dll"),
            {"stack-lock:native-cpp", "stack-lock:native-library"},
        )
        self.assertEqual(
            preset_stack_locks("vite-react-ts"),
            {"stack-lock:web", "stack-lock:web-framework"},
        )
        self.assertIn("stack-lock:solution-refactor", preset_stack_locks("python-sln-refactor-tool"))

    def test_stack_locks_conflict_with_unrelated_preset_families(self) -> None:
        self.assertFalse(stack_locks_conflict_with_preset(["stack-lock:native-cpp"], "cpp-cmake-cli"))
        self.assertTrue(stack_locks_conflict_with_preset(["stack-lock:native-cpp"], "vite-react-ts"))
        self.assertTrue(stack_locks_conflict_with_preset(["stack-lock:native-library"], "cpp-cmake-cli"))
        self.assertFalse(stack_locks_conflict_with_preset([], "vite-react-ts"))

    def test_prompt_allows_stack_switch_only_for_explicit_rebuild_language(self) -> None:
        locks = ["stack-lock:web"]

        self.assertTrue(prompt_allows_stack_switch("Rebuild as a web app from scratch", locks))
        self.assertTrue(prompt_allows_stack_switch("Create a website for the brand", locks))
        self.assertFalse(prompt_allows_stack_switch("Improve this existing project", locks))
        self.assertFalse(prompt_allows_stack_switch("Create a project", []))

    def test_stack_family_for_preset_returns_human_routing_family(self) -> None:
        self.assertEqual(stack_family_for_preset("python-sln-refactor-tool"), "solution-refactor")
        self.assertEqual(stack_family_for_preset("cpp-imgui-win32-dx11"), "desktop")
        self.assertEqual(stack_family_for_preset("nextjs-ts-tailwind"), "web")
        self.assertEqual(stack_family_for_preset("unknown"), "general")

    def test_stack_lock_keywords_respect_web_negation(self) -> None:
        native = stack_lock_keywords_for_prompt("Refine this C++ CMake DLL project; it is not a website.")
        self.assertIn("stack-lock:native-cpp", native)
        self.assertIn("stack-lock:native-library", native)
        self.assertNotIn("stack-lock:web", native)

        web = stack_lock_keywords_for_prompt("Create a Vite React website dashboard.")
        self.assertIn("stack-lock:web", web)
        self.assertIn("stack-lock:web-framework", web)

        solution = stack_lock_keywords_for_prompt("Merge two Visual Studio sln solutions")
        self.assertIn("stack-lock:solution-refactor", solution)


if __name__ == "__main__":
    unittest.main()
