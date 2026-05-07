from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_python_templates import python_cli_template, python_stdlib_api_template
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldPythonTemplatesTests(unittest.TestCase):
    def test_python_cli_template_matches_project_scaffolder_wrapper(self) -> None:
        files = python_cli_template("Validated Tool")

        self.assertEqual(files, ProjectScaffolder._python_cli_template("Validated Tool"))
        self.assertIn("pyproject.toml", files)
        self.assertIn("src/validated_tool/main.py", files)
        self.assertIn("tests/test_smoke.py", files)
        self.assertIn('name = "validated-tool"', files["pyproject.toml"])
        self.assertIn('validated_tool = "validated_tool.main:main"', files["pyproject.toml"])
        self.assertIn("argparse.ArgumentParser", files["src/validated_tool/main.py"])
        self.assertIn("compileall.compile_dir", files["build.py"])
        self.assertIn("python build.py", files["README.md"])

    def test_python_cli_template_prefixes_numeric_distribution_name(self) -> None:
        files = python_cli_template("123 My Tool")

        self.assertIn('name = "aegis-123-my-tool"', files["pyproject.toml"])
        self.assertIn("src/app_123_my_tool/main.py", files)
        self.assertIn("app_123_my_tool = \"app_123_my_tool.main:main\"", files["pyproject.toml"])

    def test_python_stdlib_api_template_matches_project_scaffolder_wrapper(self) -> None:
        files = python_stdlib_api_template("Inventory Bridge")

        self.assertEqual(files, ProjectScaffolder._python_stdlib_api_template("Inventory Bridge"))
        self.assertIn("pyproject.toml", files)
        self.assertIn("src/inventory_bridge/server.py", files)
        self.assertIn("src/inventory_bridge/store.py", files)
        self.assertIn("tests/test_api.py", files)
        self.assertIn('name = "inventory-bridge"', files["pyproject.toml"])
        self.assertIn("JsonItemStore", files["src/inventory_bridge/store.py"])
        self.assertIn('path == "/health"', files["src/inventory_bridge/server.py"])
        self.assertIn('path != "/api/items"', files["src/inventory_bridge/server.py"])
        self.assertIn("unittest", files["build.py"])
        self.assertIn("python -m inventory_bridge.server", files["README.md"])

    def test_python_stdlib_api_template_prefixes_numeric_distribution_name(self) -> None:
        files = python_stdlib_api_template("123 API")

        self.assertIn('name = "aegis-123-api"', files["pyproject.toml"])
        self.assertIn("src/app_123_api/server.py", files)
        self.assertIn("from app_123_api.server import create_server", files["tests/test_api.py"])


if __name__ == "__main__":
    unittest.main()
