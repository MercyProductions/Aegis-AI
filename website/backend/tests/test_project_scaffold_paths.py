from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_paths import (
    clean_windows_path_fragment,
    extract_windows_path_from_prompt,
    prompt_without_windows_paths,
    trim_path_fragment,
)


class ProjectScaffoldPathTests(unittest.TestCase):
    def test_extract_windows_path_stops_before_action_instruction(self) -> None:
        prompt = "at this path C:\\Projects\\Aegis Tool create a C++ console project"

        self.assertEqual(extract_windows_path_from_prompt(prompt), r"C:\Projects\Aegis Tool")

    def test_clean_windows_path_preserves_action_word_inside_existing_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "Aegis Build Tools New"
            target.mkdir()

            cleaned = clean_windows_path_fragment(f"{target} create a C++ app")

        self.assertEqual(cleaned, str(target))

    def test_prompt_without_windows_paths_removes_location_language(self) -> None:
        prompt = "at this path C:\\Projects\\Aegis Tool create a C++ console project"

        self.assertEqual(
            prompt_without_windows_paths(prompt, target_path=r"C:\Projects\Aegis Tool"),
            "create a C++ console project",
        )

    def test_trim_path_fragment_preserves_balanced_wrapper(self) -> None:
        self.assertEqual(trim_path_fragment(r"C:\Projects\Aegis Tool (1),"), r"C:\Projects\Aegis Tool (1)")
        self.assertEqual(trim_path_fragment(r"C:\Projects\Aegis Tool)."), r"C:\Projects\Aegis Tool")


if __name__ == "__main__":
    unittest.main()
