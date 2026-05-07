from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_intelligence import ProjectIntelligenceEngine
from aegis_ai.schemas import TaskSummary
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class ProjectIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
        )
        self.workspace_manager = WorkspaceManager(self.project_root, self.settings)
        self.store = EventStore(self.project_root, self.settings)
        self.workspace = self.workspace_manager.resolve_workspace("workspace")
        self.engine = ProjectIntelligenceEngine()
        self._write_project()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_project_profile_architecture_and_ignored_folders(self) -> None:
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)

        snapshot = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            manifest=None,
            project_memory=[],
            recent_tasks=[],
            fix_memory=[],
        )

        self.assertEqual(snapshot.profile.project_name, "demo-aegis-app")
        self.assertIn("React", snapshot.profile.frameworks)
        self.assertIn("npm", snapshot.profile.package_managers)
        self.assertIn("src/main.tsx", snapshot.profile.main_entry_files)
        self.assertIn("node_modules", snapshot.profile.generated_ignored_folders)
        self.assertFalse(any(item.path.startswith("node_modules/") for item in files))
        self.assertTrue(any(route.method == "GET" and route.path == "/api/items" for route in snapshot.architecture.api_routes))

    def test_file_importance_context_selection_and_persistence(self) -> None:
        task_id = self.store.create_task(
            mode="develop",
            workspace_root=self.workspace,
            message="Fix the API route in backend/main.py",
            related_files=["backend/main.py"],
        )
        self.store.transition_task(task_id, "failed", error_summary="backend/main.py route failed validation")
        self.store.remember_project_note(
            project_root=self.workspace,
            category="decision",
            title="Use FastAPI routes",
            detail="backend/main.py owns API route definitions.",
            source="test",
            confidence=0.9,
        )

        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        recent_tasks = self.store.list_tasks(project_root=self.workspace, limit=10, include_subtasks=False)
        snapshot = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            manifest=None,
            project_memory=self.store.project_memory(project_root=self.workspace, limit=10),
            recent_tasks=recent_tasks,
            fix_memory=self.store.fix_history(project_root=self.workspace, limit=10),
        )
        self.store.save_project_intelligence(snapshot)

        loaded = self.store.project_intelligence(project_root=self.workspace)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.profile.project_name, "demo-aegis-app")
        important_paths = [item.path for item in loaded.file_importance[:8]]
        self.assertIn("backend/main.py", important_paths)

        context = self.engine.select_context(snapshot=loaded, query="change the API items route", max_files=4)
        self.assertTrue(any(item.path == "backend/main.py" for item in context.selected_files))
        self.assertTrue(context.validation_requirements)
        self.assertTrue(context.project_memory)

    def test_memory_clear_and_rebuild_notes_survive_store_restart(self) -> None:
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        snapshot = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            manifest=None,
            project_memory=[],
            recent_tasks=[],
            fix_memory=[],
        )

        for category, title, detail, source, confidence in self.engine.memory_notes_for_snapshot(snapshot):
            self.store.remember_project_note(
                project_root=self.workspace,
                category=category,
                title=title,
                detail=detail,
                source=source,
                confidence=confidence,
            )
        self.assertGreater(len(self.store.project_memory(project_root=self.workspace, limit=20)), 0)
        deleted = self.store.clear_project_memory(project_root=self.workspace)
        self.assertGreater(deleted, 0)
        self.assertEqual(self.store.project_memory(project_root=self.workspace, limit=20), [])

        for category, title, detail, source, confidence in self.engine.memory_notes_for_snapshot(snapshot):
            self.store.remember_project_note(
                project_root=self.workspace,
                category=category,
                title=title,
                detail=detail,
                source=source,
                confidence=confidence,
            )
        restarted = EventStore(self.project_root, self.settings)
        self.assertGreater(len(restarted.project_memory(project_root=self.workspace, limit=20)), 0)

    def _write_project(self) -> None:
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "backend").mkdir(parents=True, exist_ok=True)
        (self.workspace / "node_modules").mkdir(parents=True, exist_ok=True)
        (self.workspace / "package.json").write_text(
            """
{
  "name": "demo-aegis-app",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest run",
    "lint": "eslint src"
  },
  "dependencies": { "@vitejs/plugin-react": "latest", "react": "latest", "vite": "latest" },
  "devDependencies": { "typescript": "latest", "vitest": "latest" }
}
""".strip(),
            encoding="utf-8",
        )
        (self.workspace / "src" / "main.tsx").write_text(
            "import App from './App';\nconsole.log(App);\n",
            encoding="utf-8",
        )
        (self.workspace / "src" / "App.tsx").write_text(
            "export default function App(){ return 'hello'; }\n// TODO: add dashboard\n",
            encoding="utf-8",
        )
        (self.workspace / "backend" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/api/items')\ndef items():\n    return []\n",
            encoding="utf-8",
        )
        (self.workspace / "backend" / "storage.py").write_text("class Store: pass\n", encoding="utf-8")
        (self.workspace / "node_modules" / "ignored.ts").write_text("export const ignored = true;\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
