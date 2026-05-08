from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.agent import AgentEngine
from aegis_ai.distributed_runtime import DistributedRuntimeManager
from aegis_ai.productization import PRODUCTIZATION_API_VERSION, ProductizationEngine
from aegis_ai.schemas import EnterprisePolicyProfile, ExecutionQueueItem, PluginManifest
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore, utc_now
from aegis_ai.workspace import WorkspaceManager


class ProductizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
            aegis_command_allowlist="python,py",
            approval_tier="guided",
            sandbox_profile="standard",
        )
        self.workspace_manager = WorkspaceManager(self.project_root, self.settings)
        self.workspace = self.workspace_manager.resolve_workspace("workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = EventStore(self.project_root, self.settings)
        self.engine = ProductizationEngine(self.settings)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_plugin_validation_registration_and_policy_persistence(self) -> None:
        policy = self.engine.ensure_enterprise_policy(self.store)
        manifest = self._plugin_manifest()
        validation = self.engine.validate_plugin(manifest, policy=policy)

        saved = self.store.upsert_plugin_manifest(validation.normalized_manifest)
        trusted = self.store.update_plugin_state(saved.id, trusted=True, reason="reviewed")
        updated_policy = self.store.save_enterprise_policy(
            policy.model_copy(update={"plugin_signing_required": True, "name": "Locked Policy"})
        )

        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(saved.id, manifest.id)
        self.assertTrue(trusted.trusted)
        self.assertEqual(self.store.plugin_manifest(saved.id).metadata["latest_state_change_reason"], "reviewed")
        self.assertTrue(self.store.active_enterprise_policy().plugin_signing_required)
        self.assertEqual(updated_policy.name, "Locked Policy")

    def test_plugin_validation_blocks_risky_unsandboxed_manifest(self) -> None:
        manifest = self._plugin_manifest(
            permissions=["read_workspace", "write_workspace", "run_commands"],
            sandbox_profile="standard",
            capabilities=["workspace_analyzer"],
            enabled=True,
        )
        validation = self.engine.validate_plugin(manifest, policy=self.engine.ensure_enterprise_policy(self.store))

        self.assertFalse(validation.valid)
        self.assertTrue(any("High-risk" in item for item in validation.errors))

    def test_recovery_snapshot_and_reliability_metrics_persist(self) -> None:
        task_id = self.store.create_task(
            mode="develop",
            workspace_root=self.workspace,
            message="Interrupted task",
            title="Interrupted task",
            user_goal="Recover this task",
        )
        self.store.transition_task(task_id, "planning")
        self.store.transition_task(task_id, "running")
        self.store.create_execution_job(
            ExecutionQueueItem(
                id="job-recover",
                task_id=task_id,
                workspace_root=str(self.workspace),
                kind="validation",
                title="Recover validation",
                user_goal="Run validation",
                status="blocked",
                created_at=utc_now(),
                updated_at=utc_now(),
                permission_scope="validation",
            )
        )

        snapshot = self.engine.snapshot(
            self.store,
            project_root=self.workspace,
            checkpoints=[SimpleNamespace(id="checkpoint-1")],
            refresh_metrics=True,
        )
        saved = self.store.reliability_metric_snapshots(project_root=self.workspace, limit=5)

        self.assertFalse(snapshot.recovery.safe_shutdown_ready)
        self.assertEqual(snapshot.recovery.interrupted_tasks[0].id, task_id)
        self.assertTrue(any(metric.name == "database_integrity" for metric in snapshot.metrics))
        self.assertEqual(saved[0].api_version, PRODUCTIZATION_API_VERSION)

    def test_api_hardening_snapshot_plugin_lifecycle_and_policy(self) -> None:
        workspace_manager = WorkspaceManager(self.project_root, self.settings)
        agent = AgentEngine(self.project_root, self.settings)
        agent.store = self.store

        with (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", workspace_manager),
            patch.object(main, "agent", agent),
            patch.object(main, "distributed_runtime", DistributedRuntimeManager(self.settings)),
            patch.object(main, "productization", ProductizationEngine(self.settings)),
            TestClient(main.app) as client,
        ):
            snapshot = client.get("/api/productization", params={"workspace_root": str(self.workspace)})
            stable_apis = client.get("/api/productization/stable-apis")
            validate = client.post(
                "/api/productization/plugins/validate",
                json={"manifest": self._plugin_manifest().model_dump(mode="json")},
            )
            register = client.post(
                "/api/productization/plugins/register",
                json={"manifest": self._plugin_manifest().model_dump(mode="json"), "enable": False, "trust": False},
            )
            plugin_id = register.json()["id"]
            enabled = client.post(f"/api/productization/plugins/{plugin_id}/enable", json={"reason": "test"})
            trusted = client.post(f"/api/productization/plugins/{plugin_id}/trust", json={"reason": "reviewed"})
            disabled = client.post(f"/api/productization/plugins/{plugin_id}/disable", json={"reason": "pause"})
            policy = client.put(
                "/api/productization/enterprise-policy",
                json={
                    "profile": EnterprisePolicyProfile(
                        id="enterprise_locked",
                        name="Enterprise Locked",
                        privacy_mode="enterprise_locked",
                        plugin_signing_required=True,
                        provider_allowlist=["ollama"],
                    ).model_dump(mode="json"),
                    "reason": "test",
                },
            )
            recovery = client.get("/api/productization/recovery", params={"workspace_root": str(self.workspace)})
            reliability = client.get("/api/productization/reliability", params={"workspace_root": str(self.workspace)})

        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["api_version"], PRODUCTIZATION_API_VERSION)
        self.assertEqual(stable_apis.status_code, 200, stable_apis.text)
        self.assertTrue(any(item["id"] == "plugin.sdk.v1" for item in stable_apis.json()))
        self.assertEqual(validate.status_code, 200, validate.text)
        self.assertTrue(validate.json()["valid"])
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(enabled.json()["enabled"])
        self.assertEqual(trusted.status_code, 200, trusted.text)
        self.assertTrue(trusted.json()["trusted"])
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(disabled.json()["enabled"])
        self.assertEqual(policy.status_code, 200, policy.text)
        self.assertTrue(policy.json()["plugin_signing_required"])
        self.assertEqual(recovery.status_code, 200, recovery.text)
        self.assertEqual(reliability.status_code, 200, reliability.text)
        self.assertTrue(any(item["name"] == "database_integrity" for item in reliability.json()))

    def _plugin_manifest(self, **overrides) -> PluginManifest:
        payload = {
            "id": "sample-observability-panel",
            "name": "Sample Observability Panel",
            "version": "0.1.0",
            "api_version": PRODUCTIZATION_API_VERSION,
            "description": "Read-only sample extension.",
            "author": "Aegis",
            "capabilities": ["ui_panel", "telemetry_processor"],
            "permissions": ["ui_panel", "telemetry"],
            "sandbox_profile": "isolated",
            "ui_panel_route": "/plugins/sample-observability-panel",
        }
        payload.update(overrides)
        return PluginManifest(**payload)


if __name__ == "__main__":
    unittest.main()
