from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_names import (
    has_explicit_project_name,
    looks_like_instructional_project_name,
    preset_default_project_name_if_needed,
    project_name,
    project_name_from_prompt,
    should_use_target_leaf_project_name,
    target_leaf_is_specific,
)


class ProjectScaffoldNameTests(unittest.TestCase):
    def test_project_name_sanitizes_titles_and_falls_back(self) -> None:
        self.assertEqual(project_name(" 123 Rick Cullers Website "), "123-rick-cullers-website")
        self.assertEqual(project_name(""), "aegis-app")

    def test_project_name_from_prompt_prefers_explicit_name(self) -> None:
        self.assertTrue(has_explicit_project_name("Create a Python CLI called Launch Tool"))
        self.assertEqual(project_name_from_prompt("Create a Python CLI called Launch Tool with tests"), "Launch Tool")

    def test_project_name_from_prompt_handles_kernel_driver_special_case(self) -> None:
        self.assertEqual(project_name_from_prompt("Create a kernel driver"), "kernel-driver")
        self.assertEqual(
            project_name_from_prompt("Create a kernel driver controller desktop app"),
            "kernel-driver-controller",
        )

    def test_project_name_from_prompt_filters_instruction_words(self) -> None:
        self.assertEqual(project_name_from_prompt("Create a FastAPI backend for telemetry ingestion"), "telemetry-ingestion")
        self.assertEqual(project_name_from_prompt("Create a website"), "aegis-app")

    def test_preset_default_replaces_generic_or_instructional_names(self) -> None:
        self.assertEqual(preset_default_project_name_if_needed("cpp-imgui-win32-dx11", "app"), "imgui-tool")
        self.assertEqual(
            preset_default_project_name_if_needed("python-sln-refactor-tool", "split solution"),
            "solution-refactor-tool",
        )
        self.assertEqual(preset_default_project_name_if_needed("python-cli", "app"), "app")

    def test_target_leaf_specificity_for_web_presets(self) -> None:
        self.assertTrue(target_leaf_is_specific("Rick Cullers Website"))
        self.assertFalse(target_leaf_is_specific("website"))
        self.assertTrue(should_use_target_leaf_project_name("vite-react-ts", "Rick Cullers Website"))
        self.assertFalse(should_use_target_leaf_project_name("cpp-cmake-cli", "Rick Cullers Website"))

    def test_instructional_slug_detection_matches_existing_rules(self) -> None:
        self.assertTrue(looks_like_instructional_project_name("project-build-tool"))
        self.assertTrue(looks_like_instructional_project_name("merge-solution"))
        self.assertFalse(looks_like_instructional_project_name("inventory-gateway"))


if __name__ == "__main__":
    unittest.main()
