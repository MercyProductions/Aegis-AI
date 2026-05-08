from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.storage_legacy_import import import_legacy_db_if_needed
from aegis_ai.storage_schema import initialize_event_store_schema


class StorageLegacyImportTests(unittest.TestCase):
    def _connect(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _session(self, path: Path):
        conn = self._connect(path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def test_import_legacy_db_normalizes_paths_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            project_root = Path(tempdir).resolve()
            current_db = project_root / "data" / "current.sqlite3"
            current_db.parent.mkdir(parents=True, exist_ok=True)
            legacy_db = project_root / "backend" / "data" / "aegis.sqlite3"
            legacy_db.parent.mkdir(parents=True, exist_ok=True)
            legacy_workspace = (project_root / "backend" / "workspace").resolve()
            current_workspace = (project_root / "workspace").resolve()

            with self._session(current_db) as conn:
                initialize_event_store_schema(conn)

            with self._session(legacy_db) as conn:
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
                    create table events (
                        task_id text not null,
                        created_at text not null,
                        kind text not null,
                        title text not null,
                        status text not null,
                        detail text not null,
                        payload_json text not null
                    )
                    """
                )
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
                    create table repair_attempts (
                        id text primary key,
                        task_id text not null,
                        created_at text not null,
                        attempt_number integer not null,
                        category text not null,
                        before_signature text not null,
                        after_signature text not null,
                        outcome text not null,
                        checkpoint text,
                        summary text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table project_memory (
                        id text primary key,
                        created_at text not null,
                        updated_at text not null,
                        project_root text not null,
                        category text not null,
                        title text not null,
                        detail text not null,
                        source text not null,
                        confidence real not null
                    )
                    """
                )
                conn.execute(
                    """
                    insert into tasks (id, created_at, finished_at, mode, workspace_root, message, status)
                    values ('task-1', '2026-01-01T00:00:00+00:00', null, 'code', ?, 'repair imports', 'done')
                    """,
                    (str(legacy_workspace),),
                )
                conn.execute(
                    """
                    insert into events (task_id, created_at, kind, title, status, detail, payload_json)
                    values ('task-1', '2026-01-01T00:01:00+00:00', 'validation', 'pytest', 'passed', 'ok', '{}')
                    """
                )
                conn.execute(
                    """
                    insert into fix_memory (
                        id, created_at, project_root, error_signature, fix_summary, evidence, confidence
                    ) values ('fix-1', '2026-01-01T00:02:00+00:00', ?, 'import error', 'adjust path', 'pytest', 0.9)
                    """,
                    (str(legacy_workspace),),
                )
                conn.execute(
                    """
                    insert into repair_attempts (
                        id, task_id, created_at, attempt_number, category, before_signature,
                        after_signature, outcome, checkpoint, summary
                    ) values (
                        'repair-1', 'task-1', '2026-01-01T00:03:00+00:00', 1, 'tests',
                        'failed', 'passed', 'success', null, 'fixed imports'
                    )
                    """
                )
                conn.execute(
                    """
                    insert into project_memory (
                        id, created_at, updated_at, project_root, category, title, detail, source, confidence
                    ) values (
                        'memory-1', '2026-01-01T00:04:00+00:00', '2026-01-01T00:04:00+00:00',
                        ?, 'constraint', 'Windows first', 'Use PowerShell-safe commands', 'legacy', 0.8
                    )
                    """,
                    (str(legacy_workspace),),
                )

            for _ in range(2):
                import_legacy_db_if_needed(
                    project_root=project_root,
                    db_path=current_db.resolve(),
                    session=lambda: self._session(current_db),
                )

            with self._session(current_db) as conn:
                task = conn.execute("select workspace_root from tasks where id = 'task-1'").fetchone()
                self.assertIsNotNone(task)
                self.assertEqual(task["workspace_root"], str(current_workspace))
                self.assertEqual(conn.execute("select count(*) from events").fetchone()[0], 1)
                self.assertEqual(conn.execute("select category from fix_memory where id = 'fix-1'").fetchone()[0], "unknown")
                self.assertEqual(
                    conn.execute("select project_root from fix_memory where id = 'fix-1'").fetchone()[0],
                    str(current_workspace),
                )
                self.assertEqual(conn.execute("select count(*) from repair_attempts").fetchone()[0], 1)
                memory = conn.execute("select project_root, fingerprint from project_memory where id = 'memory-1'").fetchone()
                self.assertIsNotNone(memory)
                self.assertEqual(memory["project_root"], str(current_workspace))
                self.assertTrue(memory["fingerprint"])

    def test_import_legacy_db_skips_current_database_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            project_root = Path(tempdir).resolve()
            legacy_db = project_root / "backend" / "data" / "aegis.sqlite3"
            legacy_db.parent.mkdir(parents=True, exist_ok=True)
            legacy_db.touch()

            def fail_session():
                raise AssertionError("current database path should not be imported as legacy")

            import_legacy_db_if_needed(
                project_root=project_root,
                db_path=legacy_db.resolve(),
                session=fail_session,
            )
