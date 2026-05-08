from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.agent import AgentEngine
from aegis_ai.autonomous_engineering import AutonomousEngineeringEngine
from aegis_ai.creative_media import CreativeMediaEngine
from aegis_ai.distributed_runtime import DistributedRuntimeManager
from aegis_ai.schemas import MediaCreativeRequest
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.unified_runtime import RuntimeSignalCounts, UnifiedRuntimeEngine
from aegis_ai.workspace import WorkspaceManager
from aegis_ai.workspace_operations import WorkspaceOperationsEngine


class UnifiedRuntimeTests(unittest.TestCase):
    def test_engine_snapshot_maps_core_pillars_and_safety_contracts(self) -> None:
        engine = UnifiedRuntimeEngine()
        snapshot = engine.snapshot(
            workspace_root=Path("C:/workspace"),
            counts=RuntimeSignalCounts(
                task_count=4,
                active_task_count=1,
                project_memory_count=2,
                creative_job_count=1,
                creative_asset_count=5,
                worker_count=1,
                queue_job_count=2,
                objective_count=1,
                pending_approval_count=1,
                project_intelligence_ready=True,
            ),
        )

        pillar_ids = {pillar.id for pillar in snapshot.pillars}
        tool_ids = {tool.id for tool in snapshot.tools}

        self.assertIn("conversation_reasoning", pillar_ids)
        self.assertIn("creative_studio", pillar_ids)
        self.assertIn("agent_runtime", pillar_ids)
        self.assertIn("security_safety", pillar_ids)
        self.assertIn("filesystem", tool_ids)
        self.assertIn("creative_media", tool_ids)
        self.assertEqual(snapshot.active_counts["creative_assets"], 5)
        self.assertTrue(any("Local-first" in item for item in snapshot.safety_summary))

    def test_unified_runtime_api_aggregates_existing_runtime_counts(self) -> None:
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
            (workspace / "package.json").write_text('{"scripts":{"test":"echo ok"}}', encoding="utf-8")
            store = EventStore(project_root, settings)
            agent = AgentEngine(project_root, settings)
            agent.store = store
            creative = CreativeMediaEngine(project_root, settings)
            creative.create_job(MediaCreativeRequest(kind="logo", prompt="Create a logo"))

            with (
                patch.object(main, "settings", settings),
                patch.object(main, "workspace_manager", workspace_manager),
                patch.object(main, "agent", agent),
                patch.object(main, "creative_media", creative),
                patch.object(main, "distributed_runtime", DistributedRuntimeManager(settings)),
                patch.object(main, "workspace_operations", WorkspaceOperationsEngine()),
                patch.object(main, "autonomous_engineering", AutonomousEngineeringEngine()),
                patch.object(main, "unified_runtime", UnifiedRuntimeEngine()),
                TestClient(main.app) as client,
            ):
                response = client.get("/api/unified-runtime", params={"workspace_root": str(workspace)})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "local-first")
        self.assertTrue(payload["pillars"])
        self.assertGreaterEqual(payload["active_counts"]["creative_assets"], 1)
        self.assertTrue(any(tool["id"] == "filesystem" for tool in payload["tools"]))


if __name__ == "__main__":
    unittest.main()
