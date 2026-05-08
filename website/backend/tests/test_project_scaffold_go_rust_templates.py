from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_go_rust_templates import (
    go_http_api_template,
    rust_cli_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldGoRustTemplatesTests(unittest.TestCase):
    def test_rust_cli_template_matches_project_scaffolder_wrapper(self) -> None:
        files = rust_cli_template("42 relay tool")

        self.assertEqual(files, ProjectScaffolder._rust_cli_template("42 relay tool"))
        self.assertIn("Cargo.toml", files)
        self.assertIn("src/lib.rs", files)
        self.assertIn("src/main.rs", files)
        self.assertIn('name = "aegis-42-relay-tool"', files["Cargo.toml"])
        self.assertIn("name = \"app_42_relay_tool\"", files["Cargo.toml"])
        self.assertIn("cargo test", files["README.md"])

    def test_go_http_api_template_matches_project_scaffolder_wrapper(self) -> None:
        files = go_http_api_template("Relay Service")

        self.assertEqual(files, ProjectScaffolder._go_http_api_template("Relay Service"))
        self.assertIn("go.mod", files)
        self.assertIn("cmd/server/main.go", files)
        self.assertIn("internal/api/router.go", files)
        self.assertIn("internal/api/router_test.go", files)
        self.assertIn("module example.com/relay-service", files["go.mod"])
        self.assertIn('mux.HandleFunc("GET /health"', files["internal/api/router.go"])
        self.assertIn("httptest.NewRecorder", files["internal/api/router_test.go"])


if __name__ == "__main__":
    unittest.main()
