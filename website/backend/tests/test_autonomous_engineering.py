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
from aegis_ai.autonomous_engineering import AUTONOMOUS_ENGINEERING_API_VERSION, AutonomousEngineeringEngine
from aegis_ai.project_intelligence import ProjectIntelligenceEngine
from aegis_ai.schemas import (
    AutonomousApprovalActionRequest,
    AutonomousObjectiveActionRequest,
    AutonomousObjectiveCreateRequest,
    AutonomousObjectiveIterationRequest,
)
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class AutonomousEngineeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
            approval_tier="guided",
            sandbox_profile="standard",
        )
        self.workspace_manager = WorkspaceManager(self.project_root, self.settings)
        self.workspace = self.workspace_manager.resolve_workspace("workspace")
        self.store = EventStore(self.project_root, self.settings)
        self.project_intelligence = ProjectIntelligenceEngine()
        self.engine = AutonomousEngineeringEngine()
        self._write_project()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_dry_run_objective_approval_gates_and_persistence(self) -> None:
        detail = self.engine.create_objective(
            self.store,
            project_root=self.workspace,
            request=AutonomousObjectiveCreateRequest(
                title="Migrate to Next.js",
                user_goal="Migrate this app to Next.js with dependency changes and architecture changes.",
                dry_run=True,
                max_iterations=8,
            ),
            project_intelligence=self._project_snapshot(),
        )
        restarted = EventStore(self.project_root, self.settings)
        loaded = restarted.autonomous_objective_detail(detail.objective.id)

        self.assertEqual(detail.objective.status, "simulating")
        self.assertEqual(len(detail.phases), 7)
        self.assertTrue(any(gate.kind == "dependency_change" for gate in detail.approval_gates))
        self.assertTrue(any(gate.kind == "architecture_change" for gate in detail.approval_gates))
        self.assertTrue(detail.simulations[0].projected_file_changes)
        self.assertIn("bun.lock", detail.simulations[0].projected_dependency_changes)
        self.assertIn("bun.lockb", detail.simulations[0].projected_dependency_changes)
        self.assertIn("uv.lock", detail.simulations[0].projected_dependency_changes)
        self.assertIn("Cargo.lock", detail.simulations[0].projected_dependency_changes)
        self.assertIn("go.sum", detail.simulations[0].projected_dependency_changes)
        self.assertGreater(detail.simulations[0].predicted_validation_risk, 0.3)
        self.assertEqual(loaded.objective.id, detail.objective.id)
        self.assertTrue(loaded.explanations)

    def test_start_iterate_approval_and_verification_flow(self) -> None:
        detail = self.engine.create_objective(
            self.store,
            project_root=self.workspace,
            request=AutonomousObjectiveCreateRequest(
                title="Improve test coverage",
                user_goal="Improve test coverage for the API route.",
                dry_run=False,
                max_iterations=10,
            ),
            project_intelligence=self._project_snapshot(),
        )
        started = self.engine.start_objective(
            self.store,
            detail.objective.id,
            AutonomousObjectiveActionRequest(reason="begin supervised objective"),
        )
        self.assertEqual(started.objective.status, "needs_approval")
        self.assertTrue(started.objective.task_ids)

        for gate in started.approval_gates:
            self.engine.approve_gate(
                self.store,
                gate.id,
                AutonomousApprovalActionRequest(reason="approved for test", resolved_by="tester"),
            )
        iterated = self.engine.iterate_objective(
            self.store,
            detail.objective.id,
            AutonomousObjectiveIterationRequest(reason="advance", max_steps=7),
        )

        self.assertIn(iterated.objective.status, {"completed", "finalizing"})
        self.assertGreater(iterated.objective.iteration_count, 0)
        self.assertTrue(any(phase.status == "completed" for phase in iterated.phases))
        self.assertTrue(any(signal.kind in {"test", "architecture"} for signal in iterated.verification))
        self.assertTrue(any("completed" in entry.title.lower() for entry in iterated.explanations))

    def test_reject_gate_pauses_objective_and_snapshot_analytics(self) -> None:
        detail = self.engine.create_objective(
            self.store,
            project_root=self.workspace,
            request=AutonomousObjectiveCreateRequest(
                title="Prepare release candidate",
                user_goal="Prepare release candidate and audit security posture.",
                dry_run=False,
            ),
            project_intelligence=self._project_snapshot(),
        )
        rejected = self.engine.reject_gate(
            self.store,
            detail.approval_gates[0].id,
            AutonomousApprovalActionRequest(reason="not safe yet", resolved_by="tester"),
        )
        snapshot = self.engine.snapshot(self.store, project_root=self.workspace)

        self.assertEqual(rejected.objective.status, "paused")
        self.assertTrue(any(gate.status == "rejected" for gate in rejected.approval_gates))
        self.assertTrue(any(metric.name == "approval_gate_clearance" for metric in snapshot.analytics))
        self.assertTrue(snapshot.objectives)

    def test_api_objective_lifecycle(self) -> None:
        agent = AgentEngine(self.project_root, self.settings)
        agent.store = self.store

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", self.workspace_manager),
            patch.object(main, "agent", agent),
            patch.object(main, "project_intelligence", ProjectIntelligenceEngine()),
            patch.object(main, "autonomous_engineering", AutonomousEngineeringEngine()),
            TestClient(main.app) as client,
        ):
            created = client.post(
                "/api/autonomous-engineering/objectives",
                json={
                    "workspace_root": str(self.workspace),
                    "title": "Modernize UI system",
                    "user_goal": "Modernize UI system with architecture changes.",
                    "dry_run": True,
                    "max_iterations": 6,
                },
            )
            objective_id = created.json()["objective"]["id"]
            gate_id = created.json()["approval_gates"][0]["id"]
            snapshot = client.get("/api/autonomous-engineering", params={"workspace_root": str(self.workspace)})
            objectives = client.get("/api/autonomous-engineering/objectives", params={"workspace_root": str(self.workspace)})
            detail = client.get(f"/api/autonomous-engineering/objectives/{objective_id}")
            simulation = client.post(f"/api/autonomous-engineering/objectives/{objective_id}/simulate")
            started = client.post(f"/api/autonomous-engineering/objectives/{objective_id}/start", json={"reason": "start"})
            approved = client.post(f"/api/autonomous-engineering/approval-gates/{gate_id}/approve", json={"reason": "ok"})
            gates = client.get("/api/autonomous-engineering/approval-gates", params={"workspace_root": str(self.workspace)})
            iterated = client.post(
                f"/api/autonomous-engineering/objectives/{objective_id}/iterate",
                json={"reason": "advance", "max_steps": 1},
            )
            paused = client.post(f"/api/autonomous-engineering/objectives/{objective_id}/pause", json={"reason": "pause"})
            canceled = client.post(f"/api/autonomous-engineering/objectives/{objective_id}/cancel", json={"reason": "cancel"})

        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["api_version"], AUTONOMOUS_ENGINEERING_API_VERSION)
        self.assertEqual(objectives.status_code, 200, objectives.text)
        self.assertTrue(objectives.json())
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(simulation.status_code, 200, simulation.text)
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["objective"]["status"], "needs_approval")
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(gates.status_code, 200, gates.text)
        self.assertEqual(iterated.status_code, 200, iterated.text)
        self.assertEqual(paused.status_code, 200, paused.text)
        self.assertEqual(paused.json()["objective"]["status"], "paused")
        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(canceled.json()["objective"]["status"], "canceled")

    def _project_snapshot(self):
        files = self.workspace_manager.scan(self.workspace, max_files=500)
        dependency = self.workspace_manager.inspect_dependency_profile(self.workspace)
        return self.project_intelligence.build_snapshot(
            workspace_root=self.workspace,
            files=files,
            dependency_profile=dependency,
            manifest=None,
            project_memory=self.store.project_memory(project_root=self.workspace, limit=10),
            recent_tasks=self.store.list_tasks(project_root=self.workspace, limit=10, include_subtasks=False),
            fix_memory=self.store.fix_history(project_root=self.workspace, limit=10),
        )

    def _write_project(self) -> None:
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "backend").mkdir(parents=True, exist_ok=True)
        (self.workspace / "package.json").write_text(
            """
{
  "name": "autonomous-demo",
  "scripts": {
    "build": "vite build",
    "test": "vitest run",
    "validate": "npm run test"
  },
  "dependencies": { "react": "latest", "vite": "latest" },
  "devDependencies": { "typescript": "latest", "vitest": "latest" }
}
""".strip(),
            encoding="utf-8",
        )
        (self.workspace / "src" / "main.tsx").write_text("import './App';\n", encoding="utf-8")
        (self.workspace / "src" / "App.tsx").write_text("export default function App(){ return 'demo'; }\n", encoding="utf-8")
        (self.workspace / "backend" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/api/items')\ndef items():\n    return []\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
