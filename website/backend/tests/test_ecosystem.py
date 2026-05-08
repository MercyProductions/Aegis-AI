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
from aegis_ai.ecosystem import ECOSYSTEM_API_VERSION, EcosystemEngine
from aegis_ai.project_intelligence import ProjectIntelligenceEngine
from aegis_ai.schemas import (
    EcosystemPackageManifest,
    OrganizationPolicyProfile,
    SharedIntelligenceProfile,
)
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class EcosystemTests(unittest.TestCase):
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
        self.engine = EcosystemEngine(self.settings)
        self.project_intelligence = ProjectIntelligenceEngine()
        self._write_project()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_package_validation_registration_and_policy_persistence(self) -> None:
        policy = self.engine.default_organization_policy().model_copy(update={"require_signed_packages": True})
        self.store.save_organization_policy(policy)
        manifest = self._package_manifest(signature="signed", signing_key_fingerprint="key", trust_level="signed")

        validation = self.engine.validate_package(manifest, policy=policy)
        saved = self.store.upsert_ecosystem_package(validation.normalized_manifest)
        trusted = self.store.update_ecosystem_package_state(saved.id, trust_level="organization", reason="reviewed")

        self.assertTrue(validation.valid, validation.errors)
        self.assertGreaterEqual(validation.trust_score, 0.8)
        self.assertEqual(saved.id, manifest.id)
        self.assertEqual(trusted.trust_level, "organization")
        self.assertTrue(self.store.active_organization_policy().require_signed_packages)

    def test_risky_package_requires_sandbox_and_trust(self) -> None:
        manifest = self._package_manifest(
            permission_scopes=["read_workspace", "write_workspace", "run_commands"],
            sandbox_permissions=["standard"],
            trust_level="reviewed",
            enabled=True,
        )

        validation = self.engine.validate_package(manifest, policy=self.engine.default_organization_policy())

        self.assertFalse(validation.valid)
        self.assertTrue(any("High-risk" in item for item in validation.errors))

    def test_workflow_graph_search_shared_profile_and_reproducibility(self) -> None:
        intelligence = self._project_snapshot()
        self.store.save_project_intelligence(intelligence)
        self.engine.ensure_baseline(self.store)
        workflow = self.store.ecosystem_workflow("debugging_pipeline")

        run = self.engine.run_workflow(
            self.store,
            workflow=workflow,
            project_root=self.workspace,
            request=main.WorkflowRunRequest(user_goal="Debug the API route"),
        )
        graph = self.engine.snapshot(self.store, project_root=self.workspace, project_intelligence=intelligence).knowledge_graph
        search = self.engine.search(
            main.EcosystemSearchRequest(query="api route", workspace_root=str(self.workspace)),
            store=self.store,
            project_root=self.workspace,
            graph=graph,
        )
        profile = self.engine.shared_profile_from_project(project_root=self.workspace, project_intelligence=intelligence)
        saved_profile = self.store.upsert_shared_intelligence_profile(profile)
        record = self.engine.create_reproducibility_record(store=self.store, project_root=self.workspace, task_id=run.task.id)

        self.assertEqual(run.task.title, "Debugging Pipeline")
        self.assertGreaterEqual(len(run.subtasks), 4)
        self.assertTrue(any(node.kind == "api" for node in graph.nodes))
        self.assertTrue(any(result.kind.startswith("graph.") for result in search.results))
        self.assertEqual(saved_profile.kind, "architecture_pattern")
        self.assertEqual(record.status, "ready")
        self.assertTrue(record.artifacts)

    def test_api_ecosystem_snapshot_lifecycle_workflow_policy_and_search(self) -> None:
        agent = AgentEngine(self.project_root, self.settings)
        agent.store = self.store

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", self.workspace_manager),
            patch.object(main, "agent", agent),
            patch.object(main, "ecosystem", EcosystemEngine(self.settings)),
            patch.object(main, "project_intelligence", ProjectIntelligenceEngine()),
            TestClient(main.app) as client,
        ):
            snapshot = client.get("/api/ecosystem", params={"workspace_root": str(self.workspace), "rebuild_graph": True})
            marketplace = client.get("/api/ecosystem/marketplace")
            validate = client.post(
                "/api/ecosystem/packages/validate",
                json={"manifest": self._package_manifest().model_dump(mode="json")},
            )
            register = client.post(
                "/api/ecosystem/packages/register",
                json={"manifest": self._package_manifest().model_dump(mode="json"), "enable": False, "trust_level": "reviewed"},
            )
            package_id = register.json()["id"]
            trusted = client.post(f"/api/ecosystem/packages/{package_id}/trust", json={"trust_level": "trusted", "reason": "test"})
            enabled = client.post(f"/api/ecosystem/packages/{package_id}/enable", json={"reason": "test"})
            disabled = client.post(f"/api/ecosystem/packages/{package_id}/disable", json={"reason": "pause"})
            workflows = client.get("/api/ecosystem/workflows")
            workflow_run = client.post(
                "/api/ecosystem/workflows/debugging_pipeline/run",
                json={"workspace_root": str(self.workspace), "user_goal": "Debug API", "start_immediately": True},
            )
            task_id = workflow_run.json()["task"]["id"]
            export_current = client.post("/api/ecosystem/shared-profiles/export-current", params={"workspace_root": str(self.workspace)})
            imported = client.post(
                "/api/ecosystem/shared-profiles/import",
                json={"profile": self._shared_profile().model_dump(mode="json"), "reason": "test"},
            )
            exported = client.get(f"/api/ecosystem/shared-profiles/{imported.json()['id']}/export")
            policy = client.put(
                "/api/ecosystem/org-policy",
                json={
                    "profile": OrganizationPolicyProfile(
                        id="org_locked",
                        name="Org Locked",
                        require_signed_packages=True,
                        collaboration_mode="organization",
                    ).model_dump(mode="json"),
                    "reason": "test",
                },
            )
            graph = client.get("/api/ecosystem/knowledge-graph", params={"workspace_root": str(self.workspace), "rebuild": True})
            search = client.post("/api/ecosystem/search", json={"workspace_root": str(self.workspace), "query": "api route"})
            reproducibility = client.post(
                "/api/ecosystem/reproducibility",
                json={"workspace_root": str(self.workspace), "task_id": task_id},
            )
            audit = client.get("/api/ecosystem/audit")

        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["api_version"], ECOSYSTEM_API_VERSION)
        self.assertEqual(marketplace.status_code, 200, marketplace.text)
        self.assertGreaterEqual(len(marketplace.json()), 3)
        self.assertEqual(validate.status_code, 200, validate.text)
        self.assertTrue(validate.json()["valid"])
        self.assertEqual(register.status_code, 200, register.text)
        self.assertEqual(trusted.status_code, 200, trusted.text)
        self.assertEqual(trusted.json()["trust_level"], "trusted")
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(enabled.json()["enabled"])
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(disabled.json()["enabled"])
        self.assertEqual(workflows.status_code, 200, workflows.text)
        self.assertTrue(any(item["id"] == "debugging_pipeline" for item in workflows.json()))
        self.assertEqual(workflow_run.status_code, 200, workflow_run.text)
        self.assertGreaterEqual(len(workflow_run.json()["subtasks"]), 4)
        self.assertEqual(export_current.status_code, 200, export_current.text)
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertEqual(policy.status_code, 200, policy.text)
        self.assertTrue(policy.json()["require_signed_packages"])
        self.assertEqual(graph.status_code, 200, graph.text)
        self.assertTrue(graph.json()["nodes"])
        self.assertEqual(search.status_code, 200, search.text)
        self.assertTrue(search.json()["results"])
        self.assertEqual(reproducibility.status_code, 200, reproducibility.text)
        self.assertEqual(reproducibility.json()["status"], "ready")
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(any(item["action"] == "package.registered" for item in audit.json()))

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

    def _package_manifest(self, **overrides) -> EcosystemPackageManifest:
        payload = {
            "id": "sample-debug-workflow-pack",
            "name": "Sample Debug Workflow Pack",
            "kind": "workflow",
            "version": "0.1.0",
            "api_version": ECOSYSTEM_API_VERSION,
            "description": "A reusable debugging workflow pack.",
            "author": "Aegis",
            "trust_level": "reviewed",
            "sandbox_permissions": ["isolated"],
            "permission_scopes": ["task_graph", "approval", "run_validation"],
            "update_channel": "stable",
            "signature": "signed",
            "signing_key_fingerprint": "sample-key",
        }
        payload.update(overrides)
        return EcosystemPackageManifest(**payload)

    def _shared_profile(self) -> SharedIntelligenceProfile:
        return SharedIntelligenceProfile(
            id="shared-validation-profile",
            name="Shared Validation Profile",
            kind="validation_profile",
            version="1.0.0",
            description="Reusable validation commands.",
            payload={"commands": ["npm run validate"]},
            checksum="abc123",
        )

    def _write_project(self) -> None:
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "backend").mkdir(parents=True, exist_ok=True)
        (self.workspace / "package.json").write_text(
            """
{
  "name": "ecosystem-demo",
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
