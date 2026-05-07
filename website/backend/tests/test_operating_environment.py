from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.operating_environment import OperatingEnvironmentEngine
from aegis_ai.schemas import OperatingEnvironmentActionRequest
from aegis_ai.settings import Settings
from aegis_ai.workspace import WorkspaceManager


class OperatingEnvironmentTests(unittest.TestCase):
    def test_snapshot_registers_os_capabilities_with_safe_defaults(self) -> None:
        engine = OperatingEnvironmentEngine()

        with tempfile.TemporaryDirectory() as tmp:
            snapshot = engine.snapshot(workspace_root=Path(tmp))

        capability_ids = {capability.id for capability in snapshot.capabilities}
        adapter_ids = {adapter.id for adapter in snapshot.adapters}
        signal_ids = {signal.id for signal in snapshot.system_signals}

        self.assertIn("desktop_control", capability_ids)
        self.assertIn("live_screen_understanding", capability_ids)
        self.assertIn("automation_studio", capability_ids)
        self.assertIn("system_intelligence", capability_ids)
        self.assertIn("security_analysis_workspace", capability_ids)
        self.assertIn("desktop_automation_adapter", adapter_ids)
        self.assertIn("readonly_system_probe", adapter_ids)
        self.assertIn("os", signal_ids)
        self.assertEqual(snapshot.permissions_summary["desktop_control_default"], "blocked")

    def test_action_preview_blocks_desktop_control_without_adapter(self) -> None:
        engine = OperatingEnvironmentEngine()
        response = engine.preview_action(
            OperatingEnvironmentActionRequest(
                capability_id="desktop_control",
                action="launch_app",
                parameters={"app": "notepad"},
            )
        )

        self.assertEqual(response.status, "blocked")
        self.assertFalse(response.allowed)
        self.assertTrue(response.approval_required)
        self.assertIn("keyboard_mouse", response.required_permissions)
        self.assertIsNotNone(response.event)

    def test_operating_environment_api_exposes_snapshot_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                approval_tier="guided",
                sandbox_profile="standard",
            )
            workspace_manager = WorkspaceManager(project_root, settings)
            workspace = workspace_manager.resolve_workspace("workspace")

            with (
                patch.object(main, "settings", settings),
                patch.object(main, "workspace_manager", workspace_manager),
                patch.object(main, "operating_environment", OperatingEnvironmentEngine()),
                TestClient(main.app) as client,
            ):
                snapshot_response = client.get(
                    "/api/operating-environment",
                    params={"workspace_root": str(workspace)},
                )
                action_response = client.post(
                    "/api/operating-environment/actions/preview",
                    json={
                        "workspace_root": str(workspace),
                        "capability_id": "system_intelligence",
                        "action": "refresh_snapshot",
                    },
                )

        self.assertEqual(snapshot_response.status_code, 200, snapshot_response.text)
        self.assertEqual(action_response.status_code, 200, action_response.text)
        self.assertTrue(any(item["id"] == "system_intelligence" for item in snapshot_response.json()["capabilities"]))
        self.assertEqual(action_response.json()["status"], "preview")
        self.assertTrue(action_response.json()["allowed"])


if __name__ == "__main__":
    unittest.main()
