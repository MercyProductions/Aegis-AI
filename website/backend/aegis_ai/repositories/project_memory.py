from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Callable
from uuid import uuid4

from ..schemas import ProjectMemoryEntry
from ..storage_helpers import fingerprint, memory_match_score, project_root_aliases


SessionFactory = Callable[[], AbstractContextManager[sqlite3.Connection]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectMemoryRepository:
    def __init__(self, *, store_project_root: Path, session_factory: SessionFactory):
        self.store_project_root = store_project_root
        self._session = session_factory

    def remember_project_note(
        self,
        *,
        project_root: Path,
        category: str,
        title: str,
        detail: str,
        source: str,
        confidence: float,
    ) -> None:
        now = utc_now()
        normalized_root = str(project_root.resolve())
        note_fingerprint = fingerprint(category, title, detail)
        with self._session() as conn:
            conn.execute(
                """
                insert into project_memory (
                    id, created_at, updated_at, project_root, category, title, detail, source, confidence, fingerprint
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(project_root, fingerprint) do update set
                    updated_at = excluded.updated_at,
                    category = excluded.category,
                    title = excluded.title,
                    detail = excluded.detail,
                    source = excluded.source,
                    confidence = case
                        when excluded.confidence > project_memory.confidence then excluded.confidence
                        else project_memory.confidence
                    end
                """,
                (
                    str(uuid4()),
                    now,
                    now,
                    normalized_root,
                    category,
                    title,
                    detail,
                    source,
                    confidence,
                    note_fingerprint,
                ),
            )

    def project_memory(self, *, project_root: Path, limit: int = 8) -> list[ProjectMemoryEntry]:
        aliases = project_root_aliases(self.store_project_root, project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, updated_at, project_root, category, title, detail, source, confidence
                from project_memory
                where project_root in ({placeholders})
                order by updated_at desc, created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()

        notes: list[ProjectMemoryEntry] = []
        seen: set[str] = set()
        for row in rows:
            payload = dict(row)
            dedupe_key = fingerprint(payload["category"], payload["title"], payload["detail"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            payload["project_root"] = str(project_root.resolve())
            notes.append(ProjectMemoryEntry.model_validate(payload))
        return notes

    def relevant_project_memory(self, *, project_root: Path, query: str, limit: int = 4) -> list[ProjectMemoryEntry]:
        candidates = self.project_memory(project_root=project_root, limit=40)
        scored = [
            (memory_match_score(query, item.category, item.title, item.detail, item.source), item)
            for item in candidates
        ]
        ranked = [item for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True) if score > 0]
        return ranked[:limit]

    def clear_project_memory(self, *, project_root: Path) -> int:
        aliases = project_root_aliases(self.store_project_root, project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            cursor = conn.execute(f"delete from project_memory where project_root in ({placeholders})", tuple(aliases))
            return int(cursor.rowcount or 0)
