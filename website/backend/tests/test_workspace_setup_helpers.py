from __future__ import annotations

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import WorkspaceProjectManifest, WorkspaceSetupRequest
from aegis_ai.workspace_setup import (
    merge_missing_manifest_fields,
    workspace_setup_manifest,
    workspace_setup_preset_id,
    workspace_setup_project_name,
    workspace_setup_stack_value,
    workspace_setup_title,
)


class WorkspaceSetupHelperTests(unittest.TestCase):
    def test_project_name_title_and_preset_id_are_sanitized(self) -> None:
        self.assertEqual(workspace_setup_project_name(Path("C:/work/Bad### Name"), "  ..Bad### Name!!  "), "Bad Name")
        self.assertEqual(workspace_setup_project_name(Path("C:/work/---"), "###"), "workspace")
        self.assertEqual(workspace_setup_title("my_python-app"), "My Python App")
        self.assertEqual(workspace_setup_title("ignored", " Custom Title "), "Custom Title")
        self.assertEqual(workspace_setup_preset_id("React + FastAPI"), "react-fastapi")

    def test_stack_value_keeps_order_and_limit(self) -> None:
        self.assertEqual(workspace_setup_stack_value(["Python", "", "TypeScript", "SQLite"], limit=3), "Python + TypeScript")

    def test_workspace_setup_manifest_uses_detected_profile_without_overexpanding(self) -> None:
        profile = SimpleNamespace(
            project_type="Python API",
            languages=["Python", "TypeScript", "Rust"],
            frameworks=["FastAPI", "React"],
            package_managers=["pip", "npm", "cargo"],
        )

        manifest = workspace_setup_manifest(
            Path("C:/workspace/my-api"),
            WorkspaceSetupRequest(project_name="My API", title="", notes=""),
            dependency_profile=profile,
            install_command="pip install -r requirements.txt",
            validation_command="pytest",
        )

        self.assertEqual(manifest.project_name, "My API")
        self.assertEqual(manifest.title, "My API")
        self.assertEqual(manifest.preset_id, "python-api")
        self.assertEqual(manifest.language, "Python + TypeScript + Rust")
        self.assertEqual(manifest.framework, "FastAPI + React")
        self.assertEqual(manifest.package_manager, "pip + npm")
        self.assertEqual(manifest.validation_command, "pytest")
        self.assertEqual(manifest.mission_contract["setup_source"], "workspace_profile")
        self.assertIn("workspace-setup", manifest.tags)
        self.assertIn("python api", manifest.tags)

    def test_merge_missing_manifest_fields_preserves_user_values_and_adds_missing_tags(self) -> None:
        existing = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="Existing",
            title="User Title",
            preset_id="",
            preset_label="",
            framework="",
            language="",
            package_manager="",
            validation_command="npm test",
            tags=["manual"],
            mission_contract={"keep": "user"},
            agent_handoff={"next_action": "Do not overwrite"},
        )
        generated = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="Generated",
            title="Generated Title",
            preset_id="node-app",
            preset_label="Node app",
            framework="React",
            language="TypeScript",
            package_manager="npm",
            validation_command="npm run check",
            tags=["workspace-setup", "manual"],
            mission_contract={"setup_source": "workspace_profile"},
            agent_handoff={"next_action": "Run validation"},
        )

        merged, changed = merge_missing_manifest_fields(existing, generated)

        self.assertTrue(changed)
        self.assertEqual(merged.project_name, "Existing")
        self.assertEqual(merged.title, "User Title")
        self.assertEqual(merged.preset_id, "node-app")
        self.assertEqual(merged.validation_command, "npm test")
        self.assertEqual(merged.mission_contract, {"keep": "user"})
        self.assertEqual(merged.agent_handoff, {"next_action": "Do not overwrite"})
        self.assertEqual(merged.tags, ["manual", "workspace-setup"])


if __name__ == "__main__":
    unittest.main()
