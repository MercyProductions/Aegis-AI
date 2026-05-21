from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.repositories import ProjectMemoryRepository
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore


class ProjectMemoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name).resolve()
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_event_store_keeps_project_memory_compatibility_methods(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        self.assertIsInstance(store.project_memory_repository, ProjectMemoryRepository)

        store.remember_project_note(
            project_root=workspace,
            category="constraint",
            title="Windows first",
            detail="Use PowerShell-safe commands for generated validation scripts.",
            source="test",
            confidence=0.7,
        )
        store.remember_project_note(
            project_root=workspace,
            category="constraint",
            title="Windows first",
            detail="Use PowerShell-safe commands for generated validation scripts.",
            source="test",
            confidence=0.95,
        )

        notes = store.project_memory(project_root=workspace, limit=5)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, "Windows first")
        self.assertGreaterEqual(notes[0].confidence, 0.95)

        hits = store.relevant_project_memory(project_root=workspace, query="PowerShell validation", limit=3)
        self.assertEqual([hit.id for hit in hits], [notes[0].id])
        self.assertEqual(store.clear_project_memory(project_root=workspace), 1)
        self.assertEqual(store.project_memory(project_root=workspace, limit=5), [])

    def test_repository_reads_legacy_workspace_aliases_without_duplicate_notes(self) -> None:
        store = EventStore(self.project_root, self.settings)
        current_workspace = (self.project_root / "workspace").resolve()
        legacy_workspace = (self.project_root / "backend" / "workspace").resolve()
        current_workspace.mkdir(parents=True, exist_ok=True)
        legacy_workspace.mkdir(parents=True, exist_ok=True)

        store.project_memory_repository.remember_project_note(
            project_root=current_workspace,
            category="architecture",
            title="Shared note",
            detail="Keep frontend and extension contracts aligned.",
            source="current",
            confidence=0.8,
        )
        store.project_memory_repository.remember_project_note(
            project_root=legacy_workspace,
            category="architecture",
            title="Shared note",
            detail="Keep frontend and extension contracts aligned.",
            source="legacy",
            confidence=0.9,
        )

        notes = store.project_memory_repository.project_memory(project_root=current_workspace, limit=5)

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].project_root, str(current_workspace))
        self.assertEqual(notes[0].source, "legacy")
