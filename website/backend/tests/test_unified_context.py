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
from aegis_ai.creative_media import CreativeMediaEngine
from aegis_ai.distributed_runtime import DistributedRuntimeManager
from aegis_ai.operating_environment import OperatingEnvironmentEngine
from aegis_ai.schemas import (
    GlobalCommandRequest,
    ProjectIntelligenceSnapshot,
    ProjectMemoryEntry,
    TaskSummary,
    ToolEvent,
    UnifiedContextSearchRequest,
)
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore, utc_now
from aegis_ai.unified_context import UnifiedContextEngine
from aegis_ai.workspace import WorkspaceManager


class UnifiedContextTests(unittest.TestCase):
    def test_engine_links_tasks_memory_project_and_desktop_capabilities(self) -> None:
        engine = UnifiedContextEngine()
        root = Path("C:/workspace")
        task = TaskSummary(
            id="task-1",
            task_id="task-1",
            created_at=utc_now(),
            mode="develop",
            workspace_root=str(root),
            message="Refactor UI with generated mockup",
            status="running",
            title="Refactor UI",
            user_goal="Use generated mockup assets",
            related_files=["src/App.tsx"],
        )
        memory = ProjectMemoryEntry(
            id="mem-1",
            created_at=utc_now(),
            updated_at=utc_now(),
            project_root=str(root),
            category="decision",
            title="Use calm UI",
            detail="Prefer calm premium layouts.",
            source="manual",
            confidence=0.9,
        )

        snapshot = engine.snapshot(
            workspace_root=root,
            tasks=[task],
            task_events={
                task.id: [
                    ToolEvent(
                        kind="planning",
                        title="Plan created",
                        detail="Use the generated mockup as design context.",
                        created_at=utc_now(),
                    )
                ]
            },
            project_intelligence=ProjectIntelligenceSnapshot(workspace_root=str(root)),
            project_memory=[memory],
            fix_memory=[],
            creative_library=None,
            workspace_operations=None,
            operating_environment=OperatingEnvironmentEngine().snapshot(workspace_root=root),
            distributed_runtime=None,
        )
        search = engine.search(snapshot, UnifiedContextSearchRequest(query="mockup", limit=5))
        route = engine.preview_command(
            workspace_root=root,
            request=GlobalCommandRequest(command="Refactor the UI with the generated mockup"),
            snapshot=snapshot,
        )

        self.assertTrue(any(record.kind == "task" for record in snapshot.records))
        self.assertTrue(any(record.source == "operating_environment" for record in snapshot.records))
        self.assertTrue(any(item.kind == "touches_file" for item in snapshot.relationships))
        self.assertTrue(search.results)
        self.assertEqual(route.route.target_system, "task_engine")
        self.assertTrue(route.route.creates_task)

    def test_unified_context_api_searches_and_global_command_submit_creates_task(self) -> None:
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
            store.create_task(
                mode="develop",
                workspace_root=workspace,
                message="Fix project file",
                title="Fix project file",
                user_goal="Fix project file",
                related_files=["src/App.tsx"],
            )

            with (
                patch.object(main, "settings", settings),
                patch.object(main, "workspace_manager", workspace_manager),
                patch.object(main, "agent", agent),
                patch.object(main, "creative_media", CreativeMediaEngine(project_root, settings)),
                patch.object(main, "distributed_runtime", DistributedRuntimeManager(settings)),
                patch.object(main, "operating_environment", OperatingEnvironmentEngine()),
                patch.object(main, "unified_context", UnifiedContextEngine()),
                TestClient(main.app) as client,
            ):
                snapshot_response = client.get("/api/unified-context", params={"workspace_root": str(workspace)})
                search_response = client.post(
                    "/api/unified-context/search",
                    json={"workspace_root": str(workspace), "query": "App.tsx", "limit": 5},
                )
                command_response = client.post(
                    "/api/global-command/submit",
                    json={
                        "workspace_root": str(workspace),
                        "command": "Fix the project file",
                        "create_task": True,
                    },
                )

        self.assertEqual(snapshot_response.status_code, 200, snapshot_response.text)
        self.assertEqual(search_response.status_code, 200, search_response.text)
        self.assertEqual(command_response.status_code, 200, command_response.text)
        self.assertGreaterEqual(snapshot_response.json()["records"].__len__(), 1)
        self.assertTrue(search_response.json()["results"])
        payload = command_response.json()
        self.assertEqual(payload["route"]["target_system"], "task_engine")
        self.assertIsNotNone(payload["task"])
        self.assertEqual(payload["event"]["kind"], "global_command")


if __name__ == "__main__":
    unittest.main()
