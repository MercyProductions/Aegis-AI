from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_memory import markdown_list, project_memory_files
from aegis_ai.schemas import ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile


class ProjectScaffoldMemoryTests(unittest.TestCase):
    def test_project_memory_files_emit_local_first_aegis_artifacts(self) -> None:
        files = project_memory_files(
            scaffold_preset("vite-react-ts", "Vite React TypeScript"),
            "aegis-app",
            prompt="Create a polished local-first coding workspace.",
            install_command="npm install",
            validation_command="npm run build",
            plan_steps=["Inspect workspace", "Write checkpointed files"],
            risk_warnings=["Target folder is not empty."],
            existing_files=[workspace_file("package.json")],
            existing_profile=WorkspaceDependencyProfile(project_type="web", frameworks=["React"]),
            planned_files={"src/App.tsx": "export default function App() { return null; }\n"},
        )

        self.assertCountEqual(
            files,
            [
                ".aegis/command_history.json",
                ".aegis/decisions.md",
                ".aegis/file_index.json",
                ".aegis/known_errors.json",
                ".aegis/validation_plan.json",
            ],
        )

        command_history = json.loads(files[".aegis/command_history.json"])
        self.assertEqual(command_history["schema"], "aegis.command_history.v1")
        self.assertEqual(command_history["commands"][0]["status"], "planned")
        self.assertEqual(command_history["commands"][1]["command"], "npm run build")

        known_errors = json.loads(files[".aegis/known_errors.json"])
        self.assertEqual(known_errors["schema"], "aegis.known_errors.v1")
        self.assertEqual(known_errors["errors"], [])

        validation_plan = json.loads(files[".aegis/validation_plan.json"])
        self.assertEqual(validation_plan["schema"], "aegis.validation_plan.v1")
        self.assertEqual(validation_plan["last_run"]["status"], "not_run")
        self.assertIn("npm run build", [step["command"] for step in validation_plan["steps"]])

    def test_project_memory_file_index_tracks_generated_and_existing_files(self) -> None:
        files = project_memory_files(
            scaffold_preset("python-cli", "Python CLI"),
            "aegis-tool",
            prompt="",
            install_command="",
            validation_command="python build.py",
            plan_steps=[],
            risk_warnings=[],
            existing_files=[workspace_file(f"file-{index}.txt") for index in range(90)],
            existing_profile=WorkspaceDependencyProfile(languages=["Python"]),
            planned_files={"main.py": "print('ok')\n", "README.md": "# Tool\n"},
        )

        file_index = json.loads(files[".aegis/file_index.json"])
        generated_paths = [item["path"] for item in file_index["generated_files"]]

        self.assertEqual(file_index["schema"], "aegis.file_index.v1")
        self.assertEqual(file_index["existing_workspace_snapshot"]["file_count"], 90)
        self.assertEqual(len(file_index["existing_workspace_snapshot"]["files"]), 80)
        self.assertIn("main.py", generated_paths)
        self.assertIn(".aegis/validation_plan.json", generated_paths)
        self.assertEqual(file_index["detected_profile"]["languages"], ["Python"])
        self.assertEqual(
            next(item for item in file_index["generated_files"] if item["path"] == "main.py")["size"],
            len("print('ok')\n".encode("utf-8")),
        )

    def test_project_decisions_markdown_has_safe_defaults(self) -> None:
        files = project_memory_files(
            scaffold_preset("static-html-site", "Static HTML Website"),
            "brand-site",
            prompt="",
            install_command="",
            validation_command="",
            plan_steps=[],
            risk_warnings=[],
            existing_files=[],
            existing_profile=WorkspaceDependencyProfile(),
            planned_files={},
        )
        decisions = files[".aegis/decisions.md"]
        command_history = json.loads(files[".aegis/command_history.json"])

        self.assertIn("No prompt was attached", decisions)
        self.assertIn("No special risk notes were detected", decisions)
        self.assertIn("- Install: not configured", decisions)
        self.assertEqual(command_history["commands"][0]["status"], "not-configured")
        self.assertEqual(command_history["commands"][1]["status"], "not-configured")

    def test_markdown_list_formats_empty_and_nonempty_items(self) -> None:
        self.assertEqual(markdown_list([]), "- None")
        self.assertEqual(markdown_list(["One", "Two"]), "- One\n- Two")


def scaffold_preset(preset_id: str, label: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id=preset_id,
        label=label,
        framework="test",
        language="test",
    )


def workspace_file(path: str) -> WorkspaceFile:
    return WorkspaceFile(
        path=path,
        kind="file",
        size=10,
        modified_at="2026-05-07T00:00:00Z",
    )


if __name__ == "__main__":
    unittest.main()
