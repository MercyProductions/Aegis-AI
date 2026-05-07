from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import ExecutionQueueItem
from aegis_ai.storage_records import (
    execution_job_from_row,
    execution_job_values,
    plugin_manifest_from_row,
    runtime_worker_from_row,
    task_summary_from_row,
    worker_audit_event_from_row,
    workspace_recommendation_from_row,
    workspace_sync_manifest_from_row,
)


class StorageRecordMapperTests(unittest.TestCase):
    def test_task_summary_from_row_preserves_legacy_defaults(self) -> None:
        task = task_summary_from_row(
            {
                "id": "task-1",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "",
                "finished_at": "2026-01-01T00:10:00Z",
                "completed_at": None,
                "mode": "develop",
                "workspace_root": "C:/work/app",
                "message": "Fix parser error in workspace",
                "status": "completed",
                "project_id": "",
                "parent_task_id": None,
                "title": "",
                "user_goal": "",
                "priority": None,
                "assigned_agent_role": None,
                "related_files_json": '["src/app.py"]',
                "validation_commands_json": '["pytest"]',
                "checkpoints_json": '["before-edit"]',
                "error_summary": None,
                "final_summary": None,
            }
        )

        self.assertEqual(task.task_id, "task-1")
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.project_id, "C:/work/app")
        self.assertEqual(task.user_goal, "Fix parser error in workspace")
        self.assertEqual(task.related_files, ["src/app.py"])
        self.assertEqual(task.validation_commands, ["pytest"])
        self.assertEqual(task.checkpoints, ["before-edit"])

    def test_runtime_worker_and_execution_queue_rows_parse_json_fields(self) -> None:
        worker = runtime_worker_from_row(
            {
                "worker_id": "worker-1",
                "name": "Local worker",
                "kind": "local",
                "endpoint": None,
                "status": "available",
                "trust_state": "trusted",
                "trust_scope": "",
                "registered_at": "now",
                "last_heartbeat_at": "later",
                "capabilities_json": '{"build_tools": ["pytest"], "supported_languages": ["python"], "validation_support": true}',
                "current_jobs": None,
                "total_jobs": 2,
                "failed_jobs": 1,
                "average_latency_ms": 12.5,
                "public_key_fingerprint": None,
                "permission_scopes_json": '["read", "write"]',
                "isolation_level": "",
                "metadata_json": '{"region": "local"}',
            }
        )
        job = execution_job_from_row(
            {
                "id": "job-1",
                "task_id": "task-1",
                "workspace_root": "C:/work/app",
                "kind": "",
                "title": "Validate",
                "user_goal": "Run tests",
                "status": "",
                "priority": 4,
                "created_at": "now",
                "updated_at": "",
                "assigned_worker_id": None,
                "attempts": None,
                "max_attempts": None,
                "depends_on_json": '["job-0"]',
                "required_capabilities_json": '["validation"]',
                "permission_scope": "",
                "sandbox_profile": "",
                "payload_json": '{"command": "pytest"}',
                "error_summary": None,
                "result_summary": None,
                "lease_expires_at": None,
            }
        )

        self.assertTrue(worker.capabilities.validation_support)
        self.assertEqual(worker.capabilities.build_tools, ["pytest"])
        self.assertEqual(worker.permission_scopes, ["read", "write"])
        self.assertEqual(worker.metadata["region"], "local")
        self.assertEqual(job.kind, "task")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.depends_on, ["job-0"])
        self.assertEqual(job.payload["command"], "pytest")

    def test_execution_job_values_serializes_lists_and_payloads(self) -> None:
        item = ExecutionQueueItem(
            id="job-2",
            task_id="task-2",
            workspace_root="C:/work/app",
            title="Repair",
            user_goal="Fix failing test",
            created_at="now",
            depends_on=["job-1"],
            required_capabilities=["commands"],
            payload={"command": "pytest"},
        )

        values = execution_job_values(item)

        self.assertEqual(values[0], "job-2")
        self.assertEqual(values[13], '["job-1"]')
        self.assertEqual(values[14], '["commands"]')
        self.assertEqual(values[17], '{"command": "pytest"}')

    def test_workspace_and_plugin_rows_preserve_database_overrides(self) -> None:
        recommendation = workspace_recommendation_from_row(
            {
                "id": "rec-1",
                "workspace_root": "C:/work/app",
                "created_at": "now",
                "updated_at": "later",
                "dismissed_at": None,
                "severity": "high",
                "category": "validation",
                "title": "Run tests",
                "detail": "No recent validation",
                "rationale": "Trust needs proof",
                "status": "active",
                "related_files_json": '["src/app.py"]',
                "related_tasks_json": '["task-1"]',
                "evidence_json": '{"source": "scan"}',
                "fix_prompt": "Run pytest",
                "fix_task_id": None,
            }
        )
        manifest = workspace_sync_manifest_from_row(
            {
                "id": "manifest-1",
                "workspace_root": "C:/work/app",
                "created_at": "now",
                "encrypted": 1,
                "encryption_label": None,
                "included_sections_json": '["settings"]',
                "manifest_hash": "abc",
                "payload_json": '{"safe": true}',
            }
        )
        plugin = plugin_manifest_from_row(
            {
                "id": "plugin-1",
                "name": "Database Name",
                "version": "1.0.0",
                "api_version": "v1",
                "enabled": 1,
                "trusted": 0,
                "created_at": "created",
                "updated_at": "updated",
                "capabilities_json": '["validator"]',
                "permission_scopes_json": '["read_workspace"]',
                "manifest_json": '{"name": "Payload Name", "version": "0.0.1", "api_version": "old"}',
            }
        )
        audit_event = worker_audit_event_from_row(
            {
                "id": "audit-1",
                "created_at": "now",
                "worker_id": None,
                "job_id": "job-1",
                "event_type": "heartbeat",
                "status": "ok",
                "detail": None,
                "metadata_json": '{"latency": 3}',
            }
        )

        self.assertEqual(recommendation.related_files, ["src/app.py"])
        self.assertEqual(recommendation.evidence["source"], "scan")
        self.assertTrue(manifest.encrypted)
        self.assertEqual(manifest.included_sections, ["settings"])
        self.assertEqual(plugin.name, "Database Name")
        self.assertEqual(plugin.version, "1.0.0")
        self.assertTrue(plugin.enabled)
        self.assertFalse(plugin.trusted)
        self.assertEqual(audit_event.worker_id, "")
        self.assertEqual(audit_event.metadata["latency"], 3)


if __name__ == "__main__":
    unittest.main()
