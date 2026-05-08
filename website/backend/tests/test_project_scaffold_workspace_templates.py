from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_workspace_templates import (
    python_game_file_analyzer_template,
    python_sln_refactor_tool_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldWorkspaceTemplatesTests(unittest.TestCase):
    def test_game_file_analyzer_template_matches_project_scaffolder_wrapper(self) -> None:
        files = python_game_file_analyzer_template("42 Asset Scanner")

        self.assertEqual(files, ProjectScaffolder._python_game_file_analyzer_template("42 Asset Scanner"))
        self.assertIn("app_42_asset_scanner/analyzer.py", files)
        self.assertIn("app_42_asset_scanner/cli.py", files)
        self.assertIn("tests/test_analyzer.py", files)
        self.assertIn("samples/sample_asset.bin", files)
        self.assertIn("def analyze_tree", files["app_42_asset_scanner/analyzer.py"])
        self.assertIn("Game file analyzer validation passed", files["build.py"])
        self.assertIn("AEGIS_SAMPLE_ASSET", files["samples/sample_asset.bin"])

    def test_solution_refactor_template_matches_project_scaffolder_wrapper(self) -> None:
        files = python_sln_refactor_tool_template("Solution Surgeon")

        self.assertEqual(files, ProjectScaffolder._python_sln_refactor_tool_template("Solution Surgeon"))
        self.assertIn("solution_surgeon/sln.py", files)
        self.assertIn("solution_surgeon/cli.py", files)
        self.assertIn("tests/test_sln.py", files)
        self.assertIn("samples/AppOne.sln", files)
        self.assertIn("samples/AppOne/AppOne.vcxproj", files)
        self.assertIn("def build_solution_graph", files["solution_surgeon/sln.py"])
        self.assertIn("def materialize_split", files["solution_surgeon/sln.py"])
        self.assertIn("Visual Studio solution refactor validation passed", files["build.py"])
        self.assertIn("d3d11.lib", files["samples/AppOne/AppOne.vcxproj"])


if __name__ == "__main__":
    unittest.main()
