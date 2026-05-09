"""Memory editor and knowledge base management system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional
from pathlib import Path
import json
import re


MAX_NOTE_BYTES = 512_000
NOTE_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


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
        self.notes: dict[str, MemoryNote] = {}
        self.storage_warning = ""
        try:
            self._ensure_storage_dir()
        except OSError as exc:
            self.storage_warning = str(exc)
            return
        self._load_all_notes()

    def _load_all_notes(self):
        """Load all notes from storage."""
        for note_file in self.storage_path.glob("*.json"):
            try:
                if not note_file.is_file() or note_file.stat().st_size > MAX_NOTE_BYTES:
                    continue
                data = json.loads(note_file.read_text(encoding="utf-8-sig", errors="replace"))
                if not isinstance(data, dict):
                    continue
                note = self._note_from_payload(data, fallback_id=note_file.stem)
                self.notes[note.id] = note
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue

    def create_note(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str] = None,
        related_files: list[str] = None
    ) -> MemoryNote:
        """Create a new memory note."""
        self._ensure_storage_dir()
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        note_id = self._new_note_id(category, now_dt)

        note = MemoryNote(
            id=note_id,
            title=str(title or "Untitled"),
            content=str(content or ""),
            category=str(category or "insight"),
            created_at=now,
            updated_at=now,
            tags=self._coerce_string_list(tags),
            related_files=self._coerce_string_list(related_files),
        )

        self._save_note(note)
        self.notes[note_id] = note
        return note

    def update_note(self, note_id: str, **kwargs) -> Optional[MemoryNote]:
        """Update a memory note."""
        if note_id not in self.notes:
            return None

        note = self.notes[note_id]
        now = datetime.now(UTC).isoformat()

        for key, value in kwargs.items():
            if key in {"id", "created_at"}:
                continue
            if key == "tags":
                note.tags = self._coerce_string_list(value)
            elif key == "related_files":
                note.related_files = self._coerce_string_list(value)
            elif key == "confidence":
                note.confidence = self._coerce_confidence(value, default=note.confidence)
            elif key == "pinned":
                note.pinned = bool(value)
            elif key in {"title", "content", "category"}:
                setattr(note, key, str(value or ""))

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

        self._ensure_storage_dir()
        try:
            note_file = self._note_path(note_id)
        except ValueError:
            return False
        if note_file.exists():
            if not note_file.is_file():
                return False
            note_file.unlink()

        del self.notes[note_id]

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
        self._ensure_storage_dir()
        note_file = self._note_path(note.id)
        payload = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "category": note.category,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "pinned": note.pinned,
            "tags": note.tags,
            "related_files": note.related_files,
            "confidence": note.confidence,
        }
        tmp = note_file.with_name(f".{note_file.name}.tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            tmp.replace(note_file)
        except OSError:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
            raise

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

    def _ensure_storage_dir(self) -> None:
        try:
            if self.storage_path.exists() and not self.storage_path.is_dir():
                raise OSError(f"{self.storage_path} is not a directory")
            self.storage_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(f"Could not initialize memory storage at {self.storage_path}: {exc}") from exc
        self.storage_warning = ""

    def _new_note_id(self, category: str, now_dt: datetime) -> str:
        base = f"{self._slugify_identifier(category)}_{int(now_dt.timestamp() * 1000)}"
        note_id = base
        suffix = 2
        while note_id in self.notes or self._note_path(note_id).exists():
            note_id = f"{base}_{suffix}"
            suffix += 1
        return note_id

    def _note_path(self, note_id: str) -> Path:
        clean_id = str(note_id or "").strip()
        if not clean_id or clean_id in {".", ".."} or Path(clean_id).name != clean_id:
            raise ValueError("memory note id must be a single file name")
        path = self.storage_path / f"{clean_id}.json"
        try:
            path.resolve().relative_to(self.storage_path.resolve())
        except (OSError, ValueError) as exc:
            raise ValueError("memory note path escaped storage") from exc
        return path

    def _note_from_payload(self, data: dict[str, Any], *, fallback_id: str) -> MemoryNote:
        note_id = str(data.get("id") or fallback_id).strip()
        try:
            self._note_path(note_id)
        except ValueError:
            note_id = fallback_id
        return MemoryNote(
            id=note_id,
            title=str(data.get("title") or "Untitled"),
            content=str(data.get("content") or ""),
            category=str(data.get("category") or "insight"),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            pinned=bool(data.get("pinned", False)),
            tags=self._coerce_string_list(data.get("tags")),
            related_files=self._coerce_string_list(data.get("related_files")),
            confidence=self._coerce_confidence(data.get("confidence"), default=0.8),
        )

    @staticmethod
    def _slugify_identifier(value: Any) -> str:
        cleaned = NOTE_ID_SAFE_RE.sub("_", str(value or "note").strip()).strip("._-")
        return cleaned[:80] or "note"

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple, set)) else [value]
        clean_items = []
        for item in items:
            text = str(item or "").strip()
            if text:
                clean_items.append(text[:500])
        return clean_items

    @staticmethod
    def _coerce_confidence(value: Any, *, default: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = default
        return max(0.0, min(1.0, confidence))
