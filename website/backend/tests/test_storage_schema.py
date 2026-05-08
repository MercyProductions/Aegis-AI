from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.storage_schema import (
    ensure_fix_memory_category_column,
    ensure_task_columns,
    initialize_event_store_schema,
)


class StorageSchemaTests(unittest.TestCase):
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

    def _columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"pragma table_info({table})").fetchall()}

    def _indexes(self, conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"pragma index_list({table})").fetchall()}

    def test_initialize_event_store_schema_creates_core_tables_and_indexes(self) -> None:
        conn = self._connect()
        try:
            initialize_event_store_schema(conn)
            initialize_event_store_schema(conn)

            tables = {
                str(row["name"])
                for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()
            }
            self.assertTrue(
                {
                    "tasks",
                    "events",
                    "fix_memory",
                    "project_memory",
                    "workspace_events",
                    "execution_queue",
                    "model_attempt_telemetry",
                    "telemetry_snapshots",
                }.issubset(tables)
            )
            self.assertTrue(
                {
                    "updated_at",
                    "completed_at",
                    "project_id",
                    "user_goal",
                    "checkpoints_json",
                    "final_summary",
                }.issubset(self._columns(conn, "tasks"))
            )
            self.assertIn(
                "idx_execution_queue_root_status_priority",
                self._indexes(conn, "execution_queue"),
            )
            self.assertIn(
                "idx_model_attempt_workspace_created",
                self._indexes(conn, "model_attempt_telemetry"),
            )
        finally:
            conn.close()

    def test_task_schema_migration_preserves_legacy_defaults(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                create table tasks (
                    id text primary key,
                    created_at text not null,
                    finished_at text,
                    mode text not null,
                    workspace_root text not null,
                    message text not null,
                    status text not null
                )
                """
            )
            conn.execute(
                """
                insert into tasks (id, created_at, finished_at, mode, workspace_root, message, status)
                values ('task-1', '2026-01-01T00:00:00+00:00', '2026-01-01T00:02:00+00:00', 'code', '/workspace', 'repair failing tests', 'done')
                """
            )

            ensure_task_columns(conn)

            row = conn.execute("select * from tasks where id = 'task-1'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["updated_at"], "2026-01-01T00:00:00+00:00")
            self.assertEqual(row["completed_at"], "2026-01-01T00:02:00+00:00")
            self.assertEqual(row["project_id"], "/workspace")
            self.assertEqual(row["user_goal"], "repair failing tests")
            self.assertEqual(row["title"], "repair failing tests")
            self.assertEqual(row["related_files_json"], "[]")
        finally:
            conn.close()

    def test_fix_memory_category_migration_is_idempotent(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                create table fix_memory (
                    id text primary key,
                    created_at text not null,
                    project_root text not null,
                    error_signature text not null,
                    fix_summary text not null,
                    evidence text not null,
                    confidence real not null
                )
                """
            )
            conn.execute(
                """
                insert into fix_memory (
                    id, created_at, project_root, error_signature, fix_summary, evidence, confidence
                ) values ('fix-1', '2026-01-01T00:00:00+00:00', '/workspace', 'pytest failed', 'rerun tests', 'pytest', 0.75)
                """
            )

            ensure_fix_memory_category_column(conn)
            ensure_fix_memory_category_column(conn)

            row = conn.execute("select category from fix_memory where id = 'fix-1'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["category"], "unknown")
        finally:
            conn.close()
