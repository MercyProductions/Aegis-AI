from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_planning import (
    default_plan_steps,
    inspection_detail,
    risk_warnings_for_target,
)
from aegis_ai.schemas import ProjectScaffoldPreset, WorkspaceDependencyProfile, WorkspaceFile


class ProjectScaffoldPlanningTests(unittest.TestCase):
    def test_default_plan_steps_include_command_and_memory_workflow(self) -> None:
        steps = default_plan_steps(
            scaffold_preset("Vite React TypeScript"),
            "aegis-app",
            "npm install",
            "npm run build",
        )

        self.assertIn("Detect project intent", steps[0])
        self.assertIn("Generate the Vite React TypeScript structure", "\n".join(steps))
        self.assertIn("Capture install command `npm install`", "\n".join(steps))
        self.assertIn("Run or save validation command `npm run build`", "\n".join(steps))
        self.assertIn("repair loop", steps[-1])

    def test_default_plan_steps_skip_empty_commands(self) -> None:
        steps = default_plan_steps(scaffold_preset("Static HTML Website"), "site", "", "")
        body = "\n".join(steps)

        self.assertNotIn("Capture install command", body)
        self.assertNotIn("Run or save validation command", body)
        self.assertEqual(steps[-1], "Hand off failed validation output to the repair loop with a bounded retry budget.")

    def test_inspection_detail_summarizes_missing_and_detected_targets(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "missing"
            self.assertIn(
                "does not exist yet",
                inspection_detail(missing, [], WorkspaceDependencyProfile()),
            )

            target = Path(raw)
            files = [workspace_file("package.json"), workspace_file("src/App.tsx")]
            profile = WorkspaceDependencyProfile(
                project_type="web",
                frameworks=["React", "Vite", "Tailwind", "Extra"],
                languages=["TypeScript", "JavaScript"],
            )
            detail = inspection_detail(target, files, profile)

            self.assertIn("Scanned 2 file(s)", detail)
            self.assertIn("web, React, Vite, Tailwind, TypeScript, JavaScript", detail)
            self.assertNotIn("Extra", detail)

    def test_inspection_detail_deduplicates_detected_terms(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            profile = WorkspaceDependencyProfile(project_type="React", frameworks=["React"], languages=["TypeScript"])

            self.assertIn(
                "detected React, TypeScript",
                inspection_detail(target, [], profile),
            )

    def test_risk_warnings_for_target_are_workspace_boundary_focused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "new-project"
            self.assertEqual(
                risk_warnings_for_target(target, overwrite=False),
                ["Target folder will be created inside an allowed workspace root."],
            )

            target.mkdir()
            (target / ".aegis").mkdir()
            self.assertEqual(risk_warnings_for_target(target, overwrite=False), [])

            (target / "src").mkdir()
            self.assertIn(
                "avoid overwriting existing visible files",
                "\n".join(risk_warnings_for_target(target, overwrite=False)),
            )
            self.assertIn(
                "unrelated user files still remain protected",
                "\n".join(risk_warnings_for_target(target, overwrite=True)),
            )


def scaffold_preset(label: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id="test-preset",
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
