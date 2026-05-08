from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
import sqlite3
from typing import Callable

from .storage_helpers import fingerprint, normalize_legacy_workspace_root

StorageSessionFactory = Callable[[], AbstractContextManager[sqlite3.Connection]]


def import_legacy_db_if_needed(
    *,
    project_root: Path,
    db_path: Path,
    session: StorageSessionFactory,
) -> None:
    legacy_db = (project_root / "backend" / "data" / "aegis.sqlite3").resolve()
    if legacy_db == db_path or not legacy_db.exists():
        return

    legacy_conn = sqlite3.connect(legacy_db)
    legacy_conn.row_factory = sqlite3.Row
    try:
        with session() as conn:
            import_legacy_tasks(conn, legacy_conn, project_root)
            import_legacy_events(conn, legacy_conn)
            import_legacy_fix_memory(conn, legacy_conn, project_root)
            import_legacy_repair_attempts(conn, legacy_conn)
            import_legacy_project_memory(conn, legacy_conn, project_root)
    finally:
        legacy_conn.close()


def import_legacy_tasks(conn: sqlite3.Connection, legacy_conn: sqlite3.Connection, project_root: Path) -> None:
    if not table_exists(legacy_conn, "tasks"):
        return
    rows = legacy_conn.execute(
        "select id, created_at, finished_at, mode, workspace_root, message, status from tasks"
    ).fetchall()
    for row in rows:
        workspace_root = normalize_legacy_workspace_root(project_root, str(row["workspace_root"]))
        conn.execute(
            """
            insert or ignore into tasks (id, created_at, finished_at, mode, workspace_root, message, status)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                str(row["created_at"]),
                str(row["finished_at"]) if row["finished_at"] is not None else None,
                str(row["mode"]),
                workspace_root,
                str(row["message"]),
                str(row["status"]),
            ),
        )


def import_legacy_events(conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
    if not table_exists(legacy_conn, "events"):
        return
    rows = legacy_conn.execute(
        "select task_id, created_at, kind, title, status, detail, payload_json from events"
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            insert into events (task_id, created_at, kind, title, status, detail, payload_json)
            select ?, ?, ?, ?, ?, ?, ?
            where not exists (
                select 1 from events
                where task_id = ? and created_at = ? and kind = ? and title = ? and detail = ?
            )
            """,
            (
                str(row["task_id"]),
                str(row["created_at"]),
                str(row["kind"]),
                str(row["title"]),
                str(row["status"]),
                str(row["detail"]),
                str(row["payload_json"]),
                str(row["task_id"]),
                str(row["created_at"]),
                str(row["kind"]),
                str(row["title"]),
                str(row["detail"]),
            ),
        )


def import_legacy_fix_memory(
    conn: sqlite3.Connection,
    legacy_conn: sqlite3.Connection,
    project_root: Path,
) -> None:
    if not table_exists(legacy_conn, "fix_memory"):
        return
    columns = table_columns(legacy_conn, "fix_memory")
    has_category = "category" in columns
    select_sql = (
        "select id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category from fix_memory"
        if has_category
        else "select id, created_at, project_root, error_signature, fix_summary, evidence, confidence from fix_memory"
    )
    rows = legacy_conn.execute(select_sql).fetchall()
    for row in rows:
        conn.execute(
            """
            insert or ignore into fix_memory (
                id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                str(row["created_at"]),
                normalize_legacy_workspace_root(project_root, str(row["project_root"])),
                str(row["error_signature"]),
                str(row["fix_summary"]),
                str(row["evidence"]),
                float(row["confidence"]),
                str(row["category"]) if has_category else "unknown",
            ),
        )


def import_legacy_repair_attempts(conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
    if not table_exists(legacy_conn, "repair_attempts"):
        return
    rows = legacy_conn.execute(
        """
        select id, task_id, created_at, attempt_number, category, before_signature,
               after_signature, outcome, checkpoint, summary
        from repair_attempts
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            insert or ignore into repair_attempts (
                id, task_id, created_at, attempt_number, category, before_signature,
                after_signature, outcome, checkpoint, summary
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                str(row["task_id"]),
                str(row["created_at"]),
                int(row["attempt_number"]),
                str(row["category"]),
                str(row["before_signature"]),
                str(row["after_signature"]),
                str(row["outcome"]),
                str(row["checkpoint"]) if row["checkpoint"] is not None else None,
                str(row["summary"]),
            ),
        )


def import_legacy_project_memory(
    conn: sqlite3.Connection,
    legacy_conn: sqlite3.Connection,
    project_root: Path,
) -> None:
    if not table_exists(legacy_conn, "project_memory"):
        return
    columns = table_columns(legacy_conn, "project_memory")
    if not {
        "id",
        "created_at",
        "updated_at",
        "project_root",
        "category",
        "title",
        "detail",
        "source",
        "confidence",
    }.issubset(columns):
        return

    rows = legacy_conn.execute(
        """
        select id, created_at, updated_at, project_root, category, title, detail, source, confidence
        from project_memory
        """
    ).fetchall()
    for row in rows:
        note_fingerprint = fingerprint(str(row["category"]), str(row["title"]), str(row["detail"]))
        conn.execute(
            """
            insert or ignore into project_memory (
                id, created_at, updated_at, project_root, category, title, detail, source, confidence, fingerprint
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                str(row["created_at"]),
                str(row["updated_at"]),
                normalize_legacy_workspace_root(project_root, str(row["project_root"])),
                str(row["category"]),
                str(row["title"]),
                str(row["detail"]),
                str(row["source"]),
                float(row["confidence"]),
                note_fingerprint,
            ),
        )


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("select name from sqlite_master where type = 'table' and name = ?", (name,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    return {
        str(row["name"])
        for row in conn.execute(f"pragma table_info({name})").fetchall()
        if row["name"]
    }
