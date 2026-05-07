from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_node_templates import (
    express_ts_template,
    node_http_api_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldNodeTemplatesTests(unittest.TestCase):
    def test_express_ts_template_matches_project_scaffolder_wrapper(self) -> None:
        files = express_ts_template("Runtime Bridge")

        self.assertEqual(files, ProjectScaffolder._express_ts_template("Runtime Bridge"))
        self.assertIn("package.json", files)
        self.assertIn("tsconfig.json", files)
        self.assertIn("src/config.ts", files)
        self.assertIn("src/routes/health.ts", files)
        self.assertIn("src/server.ts", files)
        self.assertIn(".env.example", files)
        self.assertIn('"name": "runtime-bridge"', files["package.json"])
        self.assertIn('"express": "^4.21.2"', files["package.json"])
        self.assertIn('appName: process.env.APP_NAME ?? "Runtime Bridge"', files["src/config.ts"])
        self.assertIn('healthRouter.get("/health"', files["src/routes/health.ts"])
        self.assertIn("export function createApp()", files["src/server.ts"])
        self.assertIn("npm run build", files["README.md"])

    def test_express_ts_template_prefixes_numeric_package_name(self) -> None:
        files = express_ts_template("123 API")

        self.assertIn('"name": "aegis-123-api"', files["package.json"])
        self.assertIn('APP_NAME="123 API"', files[".env.example"])

    def test_node_http_api_template_matches_project_scaffolder_wrapper(self) -> None:
        files = node_http_api_template("Inventory Gateway")

        self.assertEqual(files, ProjectScaffolder._node_http_api_template("Inventory Gateway"))
        self.assertIn("package.json", files)
        self.assertIn("src/store.js", files)
        self.assertIn("src/server.js", files)
        self.assertIn("tests/api.test.js", files)
        self.assertIn("build.js", files)
        self.assertIn('"name": "inventory-gateway"', files["package.json"])
        self.assertIn('"validate": "node build.js"', files["package.json"])
        self.assertIn("createItemStore", files["src/store.js"])
        self.assertIn("export function createApiServer", files["src/server.js"])
        self.assertIn("'--test', 'tests/api.test.js'", files["build.js"])
        self.assertIn("GET /api/items", files["README.md"])

    def test_node_http_api_template_uses_default_package_name_when_blank(self) -> None:
        files = node_http_api_template("!!!")

        self.assertIn('"name": "aegis-node-api"', files["package.json"])
        self.assertIn("Dependency-free Node.js HTTP API scaffold", files["README.md"])


if __name__ == "__main__":
    unittest.main()
