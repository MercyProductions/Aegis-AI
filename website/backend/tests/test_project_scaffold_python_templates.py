from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_python_templates import (
    fastapi_template,
    python_cli_template,
    python_stdlib_api_template,
    python_tkinter_desktop_template,
    sqlite_python_db_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldPythonTemplatesTests(unittest.TestCase):
    def test_fastapi_template_matches_project_scaffolder_wrapper(self) -> None:
        files = fastapi_template("Agent Runtime API")

        self.assertEqual(files, ProjectScaffolder._fastapi_template("Agent Runtime API"))
        self.assertIn("pyproject.toml", files)
        self.assertIn("src/agent_runtime_api/settings.py", files)
        self.assertIn("src/agent_runtime_api/main.py", files)
        self.assertIn("tests/test_health.py", files)
        self.assertIn(".env.example", files)
        self.assertIn('name = "agent-runtime-api"', files["pyproject.toml"])
        self.assertIn('"fastapi>=0.115"', files["pyproject.toml"])
        self.assertIn("SettingsConfigDict", files["src/agent_runtime_api/settings.py"])
        self.assertIn("def create_app() -> FastAPI", files["src/agent_runtime_api/main.py"])
        self.assertIn('client.get("/health")', files["tests/test_health.py"])
        self.assertIn("uvicorn agent_runtime_api.main:app --reload", files["README.md"])

    def test_fastapi_template_prefixes_numeric_distribution_name(self) -> None:
        files = fastapi_template("123 API")

        self.assertIn('name = "aegis-123-api"', files["pyproject.toml"])
        self.assertIn("src/app_123_api/main.py", files)
        self.assertIn("from app_123_api.main import create_app", files["tests/test_health.py"])

    def test_sqlite_python_db_template_matches_project_scaffolder_wrapper(self) -> None:
        files = sqlite_python_db_template("Parts Ledger")

        self.assertEqual(files, ProjectScaffolder._sqlite_python_db_template("Parts Ledger"))
        self.assertIn("schema.sql", files)
        self.assertIn("seed.sql", files)
        self.assertIn("queries/report.sql", files)
        self.assertIn("src/parts_ledger/database.py", files)
        self.assertIn("src/parts_ledger/cli.py", files)
        self.assertIn("tests/test_database.py", files)
        self.assertIn("build.py", files)
        self.assertIn("inventory_items", files["schema.sql"])
        self.assertIn("inventory_summary", files["schema.sql"])
        self.assertIn("VALUES ('project_name', 'Parts Ledger');", files["seed.sql"])
        self.assertIn("initialize_database", files["src/parts_ledger/database.py"])
        self.assertIn("command_validate", files["src/parts_ledger/cli.py"])
        self.assertIn("python -m parts_ledger.cli summary", files["README.md"])
        self.assertIn("data/*.sqlite3", files[".gitignore"])

    def test_sqlite_python_db_template_prefixes_numeric_package_name(self) -> None:
        files = sqlite_python_db_template("123 Ledger")

        self.assertIn("src/app_123_ledger/database.py", files)
        self.assertIn("from app_123_ledger.database import", files["tests/test_database.py"])
        self.assertIn("python -m app_123_ledger.cli summary", files["README.md"])

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

    def test_python_tkinter_desktop_template_matches_project_scaffolder_wrapper(self) -> None:
        files = python_tkinter_desktop_template("Task Pad")

        self.assertEqual(files, ProjectScaffolder._python_tkinter_desktop_template("Task Pad"))
        self.assertIn("pyproject.toml", files)
        self.assertIn("src/task_pad/state.py", files)
        self.assertIn("src/task_pad/app.py", files)
        self.assertIn("src/task_pad/main.py", files)
        self.assertIn("tests/test_state.py", files)
        self.assertIn("build.py", files)
        self.assertIn('name = "task-pad"', files["pyproject.toml"])
        self.assertIn('task_pad = "task_pad.main:main"', files["pyproject.toml"])
        self.assertIn("TaskStore", files["src/task_pad/state.py"])
        self.assertIn("import tkinter as tk", files["src/task_pad/app.py"])
        self.assertIn("compileall.compile_dir", files["build.py"])
        self.assertIn("python -m task_pad.main", files["README.md"])

    def test_python_tkinter_desktop_template_prefixes_numeric_distribution_name(self) -> None:
        files = python_tkinter_desktop_template("123 Desktop")

        self.assertIn('name = "aegis-123-desktop"', files["pyproject.toml"])
        self.assertIn("src/app_123_desktop/app.py", files)
        self.assertIn("app_123_desktop = \"app_123_desktop.main:main\"", files["pyproject.toml"])

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
