"""Memory editor and knowledge base management system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional
from pathlib import Path
import json


@dataclass
class MemoryNote:
    """A note or fix stored in agent memory."""
    id: str
    title: str
    content: str
    category: str  # 'fix', 'pattern', 'insight', 'bug', 'feature'
    created_at: str
    updated_at: str
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    confidence: float = 0.8  # 0-1 scale


@dataclass
class MergeConflict:
    """Represents conflicting memory entries."""
    source_id: str
    target_id: str
    field: str
    source_value: str
    target_value: str


class MemoryManager:
    """Manages agent memory and knowledge base."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "memory"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.notes: dict[str, MemoryNote] = {}
        self._load_all_notes()

    def _load_all_notes(self):
        """Load all notes from storage."""
        for note_file in self.storage_path.glob("*.json"):
            try:
                with open(note_file) as f:
                    data = json.load(f)
                    note = MemoryNote(**data)
                    self.notes[note.id] = note
            except Exception:
                pass

    def create_note(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str] = None,
        related_files: list[str] = None
    ) -> MemoryNote:
        """Create a new memory note."""
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        note_id = f"{category}_{int(now_dt.timestamp() * 1000)}"

        note = MemoryNote(
            id=note_id,
            title=title,
            content=content,
            category=category,
            created_at=now,
            updated_at=now,
            tags=tags or [],
            related_files=related_files or []
        )

        self.notes[note_id] = note
        self._save_note(note)
        return note

    def update_note(self, note_id: str, **kwargs) -> Optional[MemoryNote]:
        """Update a memory note."""
        if note_id not in self.notes:
            return None

        note = self.notes[note_id]
        now = datetime.now(UTC).isoformat()

        for key, value in kwargs.items():
            if hasattr(note, key):
                setattr(note, key, value)

        note.updated_at = now
        self._save_note(note)
        return note

    def pin_note(self, note_id: str) -> Optional[MemoryNote]:
        """Pin a note for quick access."""
        return self.update_note(note_id, pinned=True)

    def unpin_note(self, note_id: str) -> Optional[MemoryNote]:
        """Unpin a note."""
        return self.update_note(note_id, pinned=False)

    def delete_note(self, note_id: str) -> bool:
        """Delete a memory note."""
        if note_id not in self.notes:
            return False

        del self.notes[note_id]
        note_file = self.storage_path / f"{note_id}.json"
        if note_file.exists():
            note_file.unlink()

        return True

    def merge_notes(self, source_id: str, target_id: str) -> Optional[MemoryNote]:
        """Merge two notes into one."""
        if source_id not in self.notes or target_id not in self.notes:
            return None

        source = self.notes[source_id]
        target = self.notes[target_id]

        # Combine content
        merged_content = f"{target.content}\n\n--- Merged from {source.title} ---\n{source.content}"

        # Combine tags
        merged_tags = list(set(target.tags + source.tags))

        # Combine related files
        merged_files = list(set(target.related_files + source.related_files))

        # Use highest confidence
        merged_confidence = max(target.confidence, source.confidence)

        # Update target with merged data
        updated = self.update_note(
            target_id,
            content=merged_content,
            tags=merged_tags,
            related_files=merged_files,
            confidence=merged_confidence
        )

        # Delete source
        self.delete_note(source_id)

        return updated

    def get_notes_by_category(self, category: str) -> list[MemoryNote]:
        """Get all notes in a category."""
        return [n for n in self.notes.values() if n.category == category]

    def get_pinned_notes(self) -> list[MemoryNote]:
        """Get all pinned notes."""
        return [n for n in self.notes.values() if n.pinned]

    def search_notes(self, query: str) -> list[MemoryNote]:
        """Search notes by title, content, or tags."""
        query_lower = query.lower()
        results = []

        for note in self.notes.values():
            if (query_lower in note.title.lower() or
                query_lower in note.content.lower() or
                any(query_lower in tag.lower() for tag in note.tags)):
                results.append(note)

        return results

    def _save_note(self, note: MemoryNote):
        """Save a note to storage."""
        note_file = self.storage_path / f"{note.id}.json"
        with open(note_file, "w") as f:
            json.dump({
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "category": note.category,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
                "pinned": note.pinned,
                "tags": note.tags,
                "related_files": note.related_files,
                "confidence": note.confidence
            }, f, indent=2)

    def export_memory(self, format: str = "json") -> str:
        """Export all memory in specified format."""
        if format == "json":
            data = {
                "exported_at": datetime.now(UTC).isoformat(),
                "notes": [
                    {
                        "id": note.id,
                        "title": note.title,
                        "content": note.content,
                        "category": note.category,
                        "pinned": note.pinned,
                        "tags": note.tags
                    }
                    for note in sorted(
                        self.notes.values(),
                        key=lambda x: x.pinned,
                        reverse=True
                    )
                ]
            }
            return json.dumps(data, indent=2)

        return ""
