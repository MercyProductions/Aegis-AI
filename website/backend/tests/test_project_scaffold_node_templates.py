from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_node_templates import express_ts_template
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


if __name__ == "__main__":
    unittest.main()
