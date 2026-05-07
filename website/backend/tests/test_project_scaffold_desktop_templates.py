from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_desktop_templates import (
    electron_react_template,
    tauri_react_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldDesktopTemplatesTests(unittest.TestCase):
    def test_electron_template_matches_project_scaffolder_wrapper(self) -> None:
        files = electron_react_template("Ops Desk")

        self.assertEqual(files, ProjectScaffolder._electron_react_template("Ops Desk"))
        self.assertIn("src/main/index.ts", files)
        self.assertIn("src/preload/index.ts", files)
        self.assertIn("src/renderer/index.html", files)
        package_json = json.loads(files["package.json"])
        self.assertEqual(package_json["name"], "ops-desk")
        self.assertEqual(package_json["scripts"]["build"], "tsc --noEmit && electron-vite build")
        self.assertEqual(package_json["devDependencies"]["electron-vite"], "^5.0.0")
        self.assertIn("@swc/core", package_json["devDependencies"])
        self.assertIn('src="/src/main.tsx"', files["src/renderer/index.html"])
        self.assertNotIn("/src/renderer/src/main.tsx", files["src/renderer/index.html"])

    def test_tauri_template_matches_project_scaffolder_wrapper(self) -> None:
        files = tauri_react_template("123 Control Deck")

        self.assertEqual(files, ProjectScaffolder._tauri_react_template("123 Control Deck"))
        self.assertIn("src-tauri/tauri.conf.json", files)
        self.assertIn("src-tauri/src/main.rs", files)
        self.assertIn("src/App.tsx", files)
        package_json = json.loads(files["package.json"])
        self.assertEqual(package_json["name"], "aegis-123-control-deck")
        self.assertEqual(package_json["scripts"]["build"], "vite build && tauri build")
        tauri_config = json.loads(files["src-tauri/tauri.conf.json"])
        self.assertEqual(tauri_config["productName"], "123 Control Deck")
        self.assertEqual(tauri_config["build"]["frontendDist"], "../dist")
        self.assertIn("invoke<string>('greet'", files["src/App.tsx"])


if __name__ == "__main__":
    unittest.main()
