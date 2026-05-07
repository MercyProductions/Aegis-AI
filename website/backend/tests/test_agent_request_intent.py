from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent_request_intent import (
    message_without_explicit_paths,
    request_mentions_cpp_project,
    request_mentions_desktop_project,
    request_mentions_extension_project,
    request_mentions_python_app_project,
    request_mentions_specific_web_framework,
    request_mentions_web_project,
    request_needs_project_shape,
    windows_path_fragments,
)


def simple_clean_fragment(value: str) -> str:
    return value.strip().rstrip(".,;:")


class AgentRequestIntentTests(unittest.TestCase):
    def test_windows_path_fragments_dedupes_and_stops_at_unsafe_delimiters(self) -> None:
        message = "Use C:\\Projects\\App\nthen inspect C:\\Projects\\App\nand ignore C:\\Temp\\Bad|tail"

        self.assertEqual(windows_path_fragments(message, simple_clean_fragment), [r"C:\Projects\App", r"C:\Temp\Bad"])

    def test_message_without_explicit_paths_removes_prompt_location_words(self) -> None:
        message = "At this path C:\\Users\\gabri\\Work\\Sample\ncreate a Python CLI app"

        self.assertEqual(
            message_without_explicit_paths(message, simple_clean_fragment),
            "create a Python CLI app",
        )

    def test_project_shape_detection_ignores_simple_single_file_requests(self) -> None:
        self.assertFalse(request_needs_project_shape("write code to print hello", expects_file_changes=True))
        self.assertTrue(request_needs_project_shape("create a browser extension with manifest v3", expects_file_changes=True))
        self.assertFalse(request_needs_project_shape("create a browser extension", expects_file_changes=False))

    def test_stack_detection_keeps_native_desktop_extension_python_and_web_rules_separate(self) -> None:
        self.assertTrue(request_mentions_cpp_project("refine an existing C++ DLL with CMake"))
        self.assertTrue(request_mentions_desktop_project("create an Electron desktop app"))
        self.assertTrue(request_mentions_extension_project("create a Chrome extension with manifest v3"))
        self.assertTrue(request_mentions_python_app_project("create a Python CLI tool"))
        self.assertFalse(request_mentions_python_app_project("create a Python FastAPI backend service"))
        self.assertTrue(request_mentions_web_project("create a React dashboard", web_stack_negated=False))
        self.assertFalse(request_mentions_web_project("create a React dashboard", web_stack_negated=True))

    def test_specific_web_framework_detection_matches_existing_framework_terms(self) -> None:
        self.assertTrue(request_mentions_specific_web_framework("build a SvelteKit app"))
        self.assertTrue(request_mentions_specific_web_framework("ship an Electron shell"))
        self.assertFalse(request_mentions_specific_web_framework("build a plain HTML page"))


if __name__ == "__main__":
    unittest.main()
