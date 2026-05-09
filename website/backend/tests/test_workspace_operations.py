from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.agent import AgentEngine
from aegis_ai.schemas import FileChange
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager
from aegis_ai.workspace_operations import WorkspaceOperationsEngine


class WorkspaceOperationsTests(unittest.TestCase):
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
        self.engine = WorkspaceOperationsEngine()
        self._write_project()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_watcher_events_health_recommendations_and_persistence(self) -> None:
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        first = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=None,
            previous_recommendations=[],
            include_git=False,
        )
        self.store.save_workspace_watch_snapshot(first.watcher)
        self.store.record_workspace_events(first.watcher.events)
        self.store.upsert_workspace_recommendations(first.recommendations)

        (self.workspace / "src" / "large.py").write_text(
            "\n".join(f"# TODO item {index}\nvalue_{index} = {index}" for index in range(950)),
            encoding="utf-8",
        )
        (self.workspace / "package.json").write_text(
            json.dumps({"dependencies": {"demo": "latest"}}, indent=2),
            encoding="utf-8",
        )
        second_files = self.workspace_manager.scan(self.workspace, max_files=500)
        second_dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        second = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=second_files,
            dependency_profile=second_dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=self.store.workspace_watch_snapshot(project_root=self.workspace),
            previous_recommendations=self.store.workspace_recommendations(project_root=self.workspace, include_dismissed=True),
            include_git=False,
        )
        self.store.save_workspace_operations_snapshot(second)
        self.store.record_workspace_events(second.watcher.events)
        self.store.upsert_workspace_recommendations(second.recommendations)

        persisted = self.store.workspace_operations_snapshot(project_root=self.workspace)
        recommendations = self.store.workspace_recommendations(project_root=self.workspace)
        events = self.store.workspace_events(project_root=self.workspace)

        self.assertIsNotNone(persisted)
        self.assertTrue(any(event.kind in {"file.created", "file.modified", "dependency.changed"} for event in second.watcher.events))
        self.assertLess(second.health.score, 100)
        self.assertTrue(any("TODO" in item.title or "Large" in item.title or item.category == "dependency" for item in recommendations))
        self.assertGreaterEqual(len(events), len(second.watcher.events))

    def test_watcher_treats_bun_lockfile_changes_as_dependency_drift(self) -> None:
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        first = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=None,
            previous_recommendations=[],
            include_git=False,
        )
        self.store.save_workspace_watch_snapshot(first.watcher)

        (self.workspace / "bun.lock").write_text("", encoding="utf-8")
        next_files = self.workspace_manager.scan(self.workspace, max_files=500)
        next_dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        second = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=next_files,
            dependency_profile=next_dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=self.store.workspace_watch_snapshot(project_root=self.workspace),
            previous_recommendations=[],
            include_git=False,
        )

        self.assertIn("bun", next_dependency.package_managers)
        self.assertTrue(any(event.kind == "dependency.changed" for event in second.watcher.events))

    def test_watcher_treats_python_lockfile_changes_as_dependency_drift(self) -> None:
        (self.workspace / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        first = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=None,
            previous_recommendations=[],
            include_git=False,
        )
        self.store.save_workspace_watch_snapshot(first.watcher)

        (self.workspace / "uv.lock").write_text("", encoding="utf-8")
        next_files = self.workspace_manager.scan(self.workspace, max_files=500)
        next_dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        second = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=next_files,
            dependency_profile=next_dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=self.store.workspace_watch_snapshot(project_root=self.workspace),
            previous_recommendations=[],
            include_git=False,
        )

        self.assertIn("uv", next_dependency.package_managers)
        self.assertTrue(any(event.kind == "dependency.changed" for event in second.watcher.events))

    def test_watcher_treats_dotnet_nuget_metadata_as_dependency_drift(self) -> None:
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        first = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=None,
            previous_recommendations=[],
            include_git=False,
        )
        self.store.save_workspace_watch_snapshot(first.watcher)

        (self.workspace / "Directory.Packages.props").write_text("<Project />\n", encoding="utf-8")
        (self.workspace / "packages.lock.json").write_text("{}\n", encoding="utf-8")
        next_files = self.workspace_manager.scan(self.workspace, max_files=500)
        next_dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        self.assertIn("dotnet", next_dependency.package_managers)
        self.assertIn("Directory.Packages.props", next_dependency.config_files)
        self.assertIn("packages.lock.json", next_dependency.config_files)
        second = self.engine.build_snapshot(
            workspace_root=self.workspace,
            files=next_files,
            dependency_profile=next_dependency,
            project_intelligence=None,
            recent_tasks=[],
            fix_memory=[],
            project_memory=[],
            previous_watch=self.store.workspace_watch_snapshot(project_root=self.workspace),
            previous_recommendations=[],
            include_git=False,
        )

        dependency_events = [event for event in second.watcher.events if event.kind == "dependency.changed"]
        self.assertTrue(dependency_events)
        self.assertTrue(
            any(
                "Directory.Packages.props" in event.related_files or "packages.lock.json" in event.related_files
                for event in dependency_events
            )
        )

    @unittest.skipIf(shutil.which("git") is None, "git is not available")
    def test_git_event_processing(self) -> None:
        subprocess.run(["git", "init"], cwd=self.workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "config", "user.email", "aegis@example.test"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=self.workspace, check=True)
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "-m", "initial task abcdef12"], cwd=self.workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        (self.workspace / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
        (self.workspace / "new_file.py").write_text("print('new')\n", encoding="utf-8")

        git = self.engine.git_summary(self.workspace)

        self.assertTrue(git.is_repository)
        self.assertTrue(git.branch)
        self.assertIn("src/app.py", git.changed_files)
        self.assertIn("new_file.py", git.untracked_files)
        self.assertTrue(git.recent_commits)
        self.assertTrue(any("abcdef12" in link for link in git.task_commit_links))

    def test_api_scan_jobs_recommendation_fix_and_dismiss_are_permission_gated(self) -> None:
        agent = AgentEngine(self.project_root, self.settings)
        original = (self.workspace / "src" / "app.py").read_text(encoding="utf-8")
        (self.workspace / "src" / "large.py").write_text(
            "\n".join(f"# TODO item {index}\nvalue_{index} = {index}" for index in range(950)),
            encoding="utf-8",
        )

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", self.workspace_manager),
            patch.object(main, "agent", agent),
            patch.object(main, "workspace_operations", WorkspaceOperationsEngine()),
            TestClient(main.app) as client,
        ):
            scan_response = client.post(
                "/api/workspace-intelligence/scan",
                json={"workspace_root": str(self.workspace), "include_git": False},
            )
            self.assertEqual(scan_response.status_code, 200, scan_response.text)
            recommendations = scan_response.json()["recommendations"]
            self.assertTrue(recommendations)
            recommendation_id = recommendations[0]["id"]

            fix_response = client.post(
                f"/api/workspace-intelligence/recommendations/{recommendation_id}/fix",
                json={"reason": "test fix task"},
            )
            self.assertEqual(fix_response.status_code, 200, fix_response.text)
            payload = fix_response.json()
            self.assertIn("No files were modified", payload["message"])
            self.assertEqual((self.workspace / "src" / "app.py").read_text(encoding="utf-8"), original)
            self.assertEqual(payload["task"]["status"], "queued")
            self.assertEqual(payload["event"]["kind"], "recommendation.fix_requested")

            dismiss_response = client.post(
                f"/api/workspace-intelligence/recommendations/{recommendation_id}/dismiss",
                json={"reason": "not now"},
            )
            self.assertEqual(dismiss_response.status_code, 200, dismiss_response.text)
            self.assertEqual(dismiss_response.json()["recommendation"]["status"], "dismissed")

            jobs_response = client.post(
                "/api/workspace-intelligence/jobs/run",
                json={"workspace_root": str(self.workspace), "job_ids": ["validation_snapshot"], "allow_commands": False},
            )
            self.assertEqual(jobs_response.status_code, 200, jobs_response.text)
            self.assertEqual(jobs_response.json()["jobs"][0]["status"], "skipped")

    def test_scheduled_jobs_and_checkpoint_rollback_safety(self) -> None:
        jobs = self.engine.scheduled_jobs([])
        validation_job = next(item for item in jobs if item.id == "validation_snapshot")
        skipped = self.engine.job_run_record(
            validation_job,
            status="skipped",
            summary="Validation command execution requires explicit permission.",
        )
        self.store.record_scheduled_intelligence_job(project_root=self.workspace, job=skipped)
        loaded = self.store.scheduled_intelligence_jobs(project_root=self.workspace)
        self.assertEqual(loaded[0].status, "skipped")

        result = self.workspace_manager.apply_changes(
            self.workspace,
            [
                FileChange(
                    action="update",
                    path="src/app.py",
                    content="print('checkpointed')\n",
                    summary="simulate approved autonomous task write",
                )
            ],
        )
        self.assertTrue(result.checkpoint)
        self.assertEqual((self.workspace / "src" / "app.py").read_text(encoding="utf-8"), "print('checkpointed')\n")
        restored = self.workspace_manager.restore_checkpoint(self.workspace, result.checkpoint)
        self.assertTrue(any("src/app.py" in item for item in restored))
        self.assertEqual((self.workspace / "src" / "app.py").read_text(encoding="utf-8"), "print('hello')\n")

    def _write_project(self) -> None:
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
        (self.workspace / "src" / "todo.py").write_text("# TODO: cover this module\n", encoding="utf-8")
        (self.workspace / "package.json").write_text(
            json.dumps({"scripts": {"test": "python -m pytest"}, "dependencies": {"left-pad": "1.0.0"}}, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
