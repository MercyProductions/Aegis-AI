from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.agent import AgentEngine
from aegis_ai.schemas import WorkspaceSetupRequest
from aegis_ai.settings import Settings
from aegis_ai.workspace import WorkspaceManager


class WorkspaceSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        main._clear_workspace_status_cache()

    def tearDown(self) -> None:
        main._clear_workspace_status_cache()

    def test_workspace_setup_creates_manifest_and_persists_detected_validation_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": "node smoke.js"}}),
                encoding="utf-8",
            )
            (workspace / "smoke.js").write_text("console.log('ok')\n", encoding="utf-8")
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="node,npm",
            )
            manager = WorkspaceManager(project_root, settings)
            engine = AgentEngine(project_root, settings)

            with (
                patch.object(main, "workspace_manager", manager),
                patch.object(main, "agent", engine),
            ):
                response = asyncio.run(main.workspace_setup(WorkspaceSetupRequest(workspace_root=str(workspace))))

            manifest_path = workspace / ".aegis" / "project.json"
            profile_path = workspace / ".aegis" / "validation_profile.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertIn(".aegis/project.json", response.created_files)
        self.assertIn(".aegis/validation_profile.json", response.created_files)
        self.assertEqual(manifest_payload["schema"], "aegis.project.v1")
        self.assertEqual(manifest_payload["validation_command"], "npm test")
        self.assertEqual(profile_payload["command"], "npm test")
        self.assertEqual(profile_payload["source"], "workspace_setup")
        self.assertTrue(response.profile.has_manifest)
        self.assertEqual(response.profile.readiness.status, "needs_validation")

    def test_workspace_setup_preserves_manual_validation_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": "node smoke.js"}}),
                encoding="utf-8",
            )
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="node,npm",
            )
            manager = WorkspaceManager(project_root, settings)
            engine = AgentEngine(project_root, settings)
            engine.validation.save_profile(
                workspace,
                command="npm run custom-check",
                label="Custom check",
                source="manual",
                notes="User selected this recipe.",
            )

            with (
                patch.object(main, "workspace_manager", manager),
                patch.object(main, "agent", engine),
            ):
                response = asyncio.run(main.workspace_setup(WorkspaceSetupRequest(workspace_root=str(workspace))))

            profile_payload = json.loads((workspace / ".aegis" / "validation_profile.json").read_text(encoding="utf-8"))

        self.assertIn("Existing manual validation recipe was kept.", response.warnings)
        self.assertEqual(response.validation_profile.command, "npm run custom-check")
        self.assertEqual(profile_payload["source"], "manual")
        self.assertNotIn(".aegis/validation_profile.json", response.updated_files)

    def test_workspace_setup_warns_when_aegis_root_is_not_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / ".aegis").write_text("not a directory", encoding="utf-8")
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": "node smoke.js"}}),
                encoding="utf-8",
            )
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="node,npm",
            )
            manager = WorkspaceManager(project_root, settings)
            engine = AgentEngine(project_root, settings)

            with (
                patch.object(main, "workspace_manager", manager),
                patch.object(main, "agent", engine),
            ):
                response = asyncio.run(main.workspace_setup(WorkspaceSetupRequest(workspace_root=str(workspace))))

        self.assertEqual(response.manifest.schema_version, "aegis.project.v1")
        self.assertIn("Could not write .aegis/project.json", "\n".join(response.warnings))
        self.assertIn("Could not write .aegis/validation_profile.json", "\n".join(response.warnings))
        self.assertNotIn(".aegis/project.json", response.created_files)
        self.assertNotIn(".aegis/validation_profile.json", response.created_files)

    def test_workspace_setup_warns_when_memory_targets_are_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            workspace = project_root / "workspace"
            aegis_dir = workspace / ".aegis"
            aegis_dir.mkdir(parents=True, exist_ok=True)
            (aegis_dir / "project.json").mkdir()
            (aegis_dir / "validation_profile.json").mkdir()
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": "node smoke.js"}}),
                encoding="utf-8",
            )
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                aegis_command_allowlist="node,npm",
            )
            manager = WorkspaceManager(project_root, settings)
            engine = AgentEngine(project_root, settings)

            with (
                patch.object(main, "workspace_manager", manager),
                patch.object(main, "agent", engine),
            ):
                response = asyncio.run(main.workspace_setup(WorkspaceSetupRequest(workspace_root=str(workspace))))

        warnings = "\n".join(response.warnings)
        self.assertIn("Could not write .aegis/project.json", warnings)
        self.assertIn("Could not write .aegis/validation_profile.json", warnings)
        self.assertNotIn(".aegis/project.json", response.created_files + response.updated_files)
        self.assertNotIn(".aegis/validation_profile.json", response.created_files + response.updated_files)


if __name__ == "__main__":
    unittest.main()
