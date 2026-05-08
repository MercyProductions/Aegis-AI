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
from aegis_ai.continuity import AegisContinuityEngine
from aegis_ai.creative_media import CreativeMediaEngine
from aegis_ai.distributed_runtime import DistributedRuntimeManager
from aegis_ai.operating_environment import OperatingEnvironmentEngine
from aegis_ai.schemas import ProjectMemoryEntry, TaskSummary, TimelineSearchRequest, ToolEvent, UnifiedContextSearchRequest
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore, utc_now
from aegis_ai.unified_context import UnifiedContextEngine
from aegis_ai.workspace import WorkspaceManager


class ContinuityTests(unittest.TestCase):
    def test_engine_derives_presence_forecasts_timeline_and_diagnostics(self) -> None:
        root = Path("C:/workspace")
        task = TaskSummary(
            id="task-1",
            task_id="task-1",
            created_at=utc_now(),
            mode="develop",
            workspace_root=str(root),
            message="Fix validation failure",
            status="running",
            title="Fix validation failure",
            user_goal="Fix validation failure",
            related_files=["src/App.tsx"],
        )
        memory = ProjectMemoryEntry(
            id="mem-1",
            created_at=utc_now(),
            updated_at=utc_now(),
            project_root=str(root),
            category="preference",
            title="Keep responses concise",
            detail="Prefer concise summaries during repair loops.",
            source="manual",
            confidence=0.9,
        )
        context = UnifiedContextEngine().snapshot(
            workspace_root=root,
            tasks=[task],
            task_events={
                task.id: [
                    ToolEvent(
                        kind="validation",
                        title="Validation failed",
                        status="error",
                        detail="npm run validate failed.",
                        created_at=utc_now(),
                    )
                ]
            },
            project_intelligence=None,
            project_memory=[memory],
            fix_memory=[],
            creative_library=None,
            workspace_operations=None,
            operating_environment=OperatingEnvironmentEngine().snapshot(workspace_root=root),
            distributed_runtime=None,
        )

        engine = AegisContinuityEngine()
        snapshot = engine.snapshot(workspace_root=root, context=context)
        search = engine.search_timeline(snapshot, TimelineSearchRequest(query="validation", limit=5))

        self.assertIn(snapshot.presence.status, {"focused", "busy", "attention"})
        self.assertTrue(snapshot.timeline.entries)
        self.assertTrue(snapshot.forecasts.signals)
        self.assertTrue(snapshot.self_diagnostics)
        self.assertTrue(snapshot.skill_packs)
        self.assertTrue(snapshot.universal_data_sources)
        self.assertGreater(snapshot.digital_twin.confidence, 0)
        self.assertTrue(search.results)

    def test_continuity_api_uses_persisted_context_and_searches_timeline(self) -> None:
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
            store = EventStore(project_root, settings)
            agent = AgentEngine(project_root, settings)
            agent.store = store
            task_id = store.create_task(
                mode="develop",
                workspace_root=workspace,
                message="Validate project",
                title="Validate project",
                user_goal="Validate project",
                related_files=["src/App.tsx"],
            )
            store.record_event(task_id, kind="validation", title="Validation queued", detail="npm run validate")

            with (
                patch.object(main, "settings", settings),
                patch.object(main, "workspace_manager", workspace_manager),
                patch.object(main, "agent", agent),
                patch.object(main, "creative_media", CreativeMediaEngine(project_root, settings)),
                patch.object(main, "distributed_runtime", DistributedRuntimeManager(settings)),
                patch.object(main, "operating_environment", OperatingEnvironmentEngine()),
                patch.object(main, "unified_context", UnifiedContextEngine()),
                patch.object(main, "continuity", AegisContinuityEngine()),
                TestClient(main.app) as client,
            ):
                snapshot_response = client.get("/api/continuity", params={"workspace_root": str(workspace)})
                search_response = client.post(
                    "/api/continuity/timeline/search",
                    json={"workspace_root": str(workspace), "query": "validate", "limit": 5},
                )

        self.assertEqual(snapshot_response.status_code, 200, snapshot_response.text)
        self.assertEqual(search_response.status_code, 200, search_response.text)
        payload = snapshot_response.json()
        self.assertTrue(payload["timeline"]["entries"])
        self.assertTrue(payload["self_diagnostics"])
        self.assertTrue(payload["research_lab"])
        self.assertTrue(search_response.json()["results"])


if __name__ == "__main__":
    unittest.main()
