from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.agent import AgentEngine
from aegis_ai.distributed_runtime import DistributedRuntimeManager
from aegis_ai.model_registry import ModelRegistryManager
from aegis_ai.schemas import ExecutionQueueCreateRequest, WorkerCapabilitySet, WorkerRegistrationRequest
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.workspace import WorkspaceManager


class DistributedRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
            aegis_command_allowlist="python,py",
            sandbox_profile="standard",
        )
        self.workspace_manager = WorkspaceManager(self.project_root, self.settings)
        self.workspace = self.workspace_manager.resolve_workspace("workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "app.py").write_text("print('hello')\n", encoding="utf-8")
        self.agent = AgentEngine(self.project_root, self.settings)
        self.runtime = DistributedRuntimeManager(self.settings)
        self.registry = ModelRegistryManager(self.project_root, self.settings)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_worker_registration_trust_revocation_and_persistence(self) -> None:
        store = EventStore(self.project_root, self.settings)
        public_key = "public-key-for-lan-worker"
        signature = self.runtime.registration_signature(
            worker_id="lan-1",
            name="LAN Builder",
            trust_scope="studio",
            public_key=public_key,
        )
        worker = self.runtime.register_worker(
            WorkerRegistrationRequest(
                worker_id="lan-1",
                name="LAN Builder",
                kind="lan",
                endpoint="https://lan-worker.test",
                public_key=public_key,
                registration_signature=signature,
                trust_scope="studio",
                permission_scopes=["read", "validation"],
                capabilities=WorkerCapabilitySet(
                    installed_sdks=["python"],
                    build_tools=["python"],
                    supported_languages=["python"],
                    available_models=["remote-code"],
                    validation_support=True,
                    supported_job_kinds=["validation"],
                    max_parallel_jobs=2,
                ),
                isolation_level="remote",
            )
        )
        store.upsert_runtime_worker(worker)
        loaded = store.runtime_worker("lan-1")
        revoked = store.revoke_runtime_worker("lan-1", reason="rotated key")

        self.assertEqual(loaded.trust_state, "trusted")
        self.assertEqual(loaded.capabilities.available_models, ["remote-code"])
        self.assertEqual(revoked.trust_state, "revoked")
        self.assertEqual(store.runtime_workers(), [])
        self.assertEqual(store.runtime_workers(include_revoked=True)[0].metadata["revocation_reason"], "rotated key")

    def test_local_task_dispatch_records_timeline_and_observability(self) -> None:
        with self._patched_client() as client:
            task_response = client.post(
                "/api/tasks",
                json={"workspace_root": str(self.workspace), "title": "Queue task", "user_goal": "Exercise local queue"},
            )
            self.assertEqual(task_response.status_code, 200, task_response.text)
            task_id = task_response.json()["task"]["id"]

            queue_response = client.post(
                "/api/distributed-runtime/queue",
                json={
                    "workspace_root": str(self.workspace),
                    "task_id": task_id,
                    "kind": "task",
                    "title": "Local task job",
                    "permission_scope": "task",
                },
            )
            self.assertEqual(queue_response.status_code, 200, queue_response.text)

            dispatch_response = client.post(
                "/api/distributed-runtime/dispatch",
                json={"workspace_root": str(self.workspace), "limit": 1},
            )
            timeline_response = client.get(f"/api/tasks/{task_id}/timeline")
            observability_response = client.get(
                "/api/distributed-runtime/observability",
                params={"workspace_root": str(self.workspace)},
            )

        self.assertEqual(dispatch_response.status_code, 200, dispatch_response.text)
        self.assertEqual(dispatch_response.json()["jobs"][0]["status"], "succeeded")
        self.assertEqual(timeline_response.status_code, 200, timeline_response.text)
        self.assertTrue(any(event["title"] == "Distributed job finished" for event in timeline_response.json()["events"]))
        self.assertEqual(observability_response.status_code, 200, observability_response.text)
        self.assertGreaterEqual(observability_response.json()["succeeded_jobs"], 1)

    def test_validation_failure_is_permission_gated_and_queues_repair(self) -> None:
        with self._patched_client() as client:
            task_id = client.post(
                "/api/tasks",
                json={"workspace_root": str(self.workspace), "title": "Validate", "user_goal": "Fail validation"},
            ).json()["task"]["id"]
            blocked = client.post(
                "/api/distributed-runtime/queue",
                json={
                    "workspace_root": str(self.workspace),
                    "task_id": task_id,
                    "kind": "validation",
                    "title": "Blocked validation",
                    "permission_scope": "validation",
                    "payload": {"command": "python -c \"import sys; sys.exit(1)\""},
                },
            ).json()
            blocked_dispatch = client.post(
                "/api/distributed-runtime/dispatch",
                json={"workspace_root": str(self.workspace), "limit": 1, "allow_commands": False},
            )
            retry_response = client.post(
                f"/api/distributed-runtime/queue/{blocked['id']}/retry",
                json={"reason": "run with explicit command permission"},
            )
            failed_dispatch = client.post(
                "/api/distributed-runtime/dispatch",
                json={"workspace_root": str(self.workspace), "limit": 1, "allow_commands": True},
            )
            queue_response = client.get("/api/distributed-runtime/queue", params={"workspace_root": str(self.workspace)})
            timeline_response = client.get(f"/api/tasks/{task_id}/timeline")

        self.assertEqual(blocked_dispatch.status_code, 200, blocked_dispatch.text)
        self.assertEqual(blocked_dispatch.json()["jobs"][0]["status"], "blocked")
        self.assertEqual(retry_response.status_code, 200, retry_response.text)
        self.assertEqual(failed_dispatch.status_code, 200, failed_dispatch.text)
        self.assertEqual(failed_dispatch.json()["jobs"][0]["status"], "failed")
        self.assertTrue(any(job["kind"] == "repair" for job in queue_response.json()))
        self.assertTrue(any(event["title"] == "Repair queued" for event in timeline_response.json()["events"]))

    def test_queue_cancel_retry_sync_manifest_and_audit_persist(self) -> None:
        with self._patched_client() as client:
            created = client.post(
                "/api/distributed-runtime/queue",
                json={"workspace_root": str(self.workspace), "kind": "indexing", "title": "Index later"},
            ).json()
            canceled = client.post(
                f"/api/distributed-runtime/queue/{created['id']}/cancel",
                json={"reason": "pause work"},
            )
            retried = client.post(
                f"/api/distributed-runtime/queue/{created['id']}/retry",
                json={"reason": "resume work"},
            )
            first_sync = client.post(
                "/api/distributed-runtime/sync/export",
                json={"workspace_root": str(self.workspace), "sections": ["settings"], "encrypted": True},
            )
            second_sync = client.post(
                "/api/distributed-runtime/sync/export",
                json={"workspace_root": str(self.workspace), "sections": ["settings"], "encrypted": True},
            )
            audit = client.get("/api/distributed-runtime/audit")

        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(canceled.json()["status"], "canceled")
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["status"], "retrying")
        self.assertEqual(first_sync.status_code, 200, first_sync.text)
        self.assertEqual(second_sync.status_code, 200, second_sync.text)
        self.assertEqual(first_sync.json()["manifest_hash"], second_sync.json()["manifest_hash"])
        self.assertTrue(any(event["event_type"] == "sync.manifest.created" for event in audit.json()))

    def test_remote_assignment_requires_permission_and_routing_respects_privacy(self) -> None:
        with self._patched_client() as client:
            public_key = "remote-public-key"
            signature = self.runtime.registration_signature(
                worker_id="remote-1",
                name="Remote Validator",
                trust_scope="team",
                public_key=public_key,
            )
            register = client.post(
                "/api/distributed-runtime/workers/register",
                json={
                    "worker_id": "remote-1",
                    "name": "Remote Validator",
                    "kind": "remote",
                    "endpoint": "https://worker.example.test",
                    "public_key": public_key,
                    "registration_signature": signature,
                    "trust_scope": "team",
                    "permission_scopes": ["read", "validation"],
                    "isolation_level": "remote",
                    "capabilities": {
                        "installed_sdks": ["python"],
                        "build_tools": ["python"],
                        "supported_languages": ["python"],
                        "available_models": ["remote-only"],
                        "validation_support": True,
                        "supported_job_kinds": ["validation"],
                        "max_parallel_jobs": 2,
                    },
                },
            )
            self.assertEqual(register.status_code, 200, register.text)
            queued = client.post(
                "/api/distributed-runtime/queue",
                json={
                    "workspace_root": str(self.workspace),
                    "kind": "validation",
                    "title": "Remote validation",
                    "permission_scope": "validation",
                    "required_capabilities": ["remote-only"],
                    "payload": {"command": "python -c \"print('remote')\""},
                },
            ).json()
            without_remote = client.post(
                "/api/distributed-runtime/dispatch",
                json={"workspace_root": str(self.workspace), "limit": 1, "allow_remote": False},
            )
            with_remote = client.post(
                "/api/distributed-runtime/dispatch",
                json={"workspace_root": str(self.workspace), "limit": 1, "allow_remote": True},
            )
            local_only_route = client.post(
                "/api/distributed-runtime/route",
                json={"workspace_root": str(self.workspace), "privacy": "local_only"},
            )
            hybrid_route = client.post(
                "/api/distributed-runtime/route",
                json={"workspace_root": str(self.workspace), "privacy": "hybrid"},
            )

        self.assertEqual(without_remote.status_code, 200, without_remote.text)
        self.assertEqual(without_remote.json()["jobs"], [])
        self.assertIn("No eligible worker", without_remote.json()["warnings"][0])
        self.assertEqual(with_remote.status_code, 200, with_remote.text)
        self.assertEqual(with_remote.json()["jobs"][0]["id"], queued["id"])
        self.assertEqual(with_remote.json()["jobs"][0]["status"], "assigned")
        self.assertEqual(local_only_route.status_code, 200, local_only_route.text)
        self.assertTrue(all(candidate["location"] == "local" for candidate in local_only_route.json()["candidates"]))
        self.assertTrue(any(candidate["worker_id"] == "remote-1" for candidate in hybrid_route.json()["candidates"]))

    def _patched_client(self) -> TestClient:
        stack = (
            patch.object(main, "settings", self.settings),
            patch.object(main, "workspace_manager", self.workspace_manager),
            patch.object(main, "agent", self.agent),
            patch.object(main, "distributed_runtime", self.runtime),
            patch.object(main, "model_registry", self.registry),
        )

        class _PatchedClient:
            def __enter__(inner_self) -> TestClient:
                inner_self.patches = [item.__enter__() for item in stack]
                inner_self.client = TestClient(main.app)
                return inner_self.client.__enter__()

            def __exit__(inner_self, exc_type, exc, tb) -> None:
                inner_self.client.__exit__(exc_type, exc, tb)
                for patcher in reversed(stack):
                    patcher.__exit__(exc_type, exc, tb)

        return _PatchedClient()  # type: ignore[return-value]


if __name__ == "__main__":
    unittest.main()
