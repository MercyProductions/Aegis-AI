from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from fastapi import HTTPException

from ..schemas import FeedbackRecordRequest, FeedbackRecordResponse
from ..storage import utc_now
from .core_client import AegisCoreClient, CoreDelegationResult


_LEGACY_TO_CORE_MEMORY_CATEGORY = {
    "preference": "user_preferences",
    "preferences": "user_preferences",
    "user_preference": "user_preferences",
    "workspace": "workspace_preferences",
    "workspace_preference": "workspace_preferences",
    "project": "project_memory",
    "note": "project_memory",
    "insight": "project_memory",
    "feature": "project_memory",
    "fix": "repair_history",
    "bug": "repair_history",
    "repair": "repair_history",
    "validation": "validation_history",
    "roadmap": "roadmap_history",
    "architecture": "architecture_notes",
    "decision": "architecture_notes",
    "pattern": "workflow_patterns",
    "workflow": "workflow_patterns",
    "ui": "ui_preferences",
}

_CORE_TO_LEGACY_MEMORY_CATEGORY = {
    "user_preferences": "preference",
    "workspace_preferences": "workspace",
    "project_memory": "insight",
    "execution_history": "workflow",
    "repair_history": "fix",
    "validation_history": "validation",
    "roadmap_history": "roadmap",
    "architecture_notes": "architecture",
    "workflow_patterns": "pattern",
    "ui_preferences": "ui",
}

_FEEDBACK_SECRET_FIELD = (
    r"x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"client[_-]?secret|secret|token|password|passwd|pwd|credential|authorization|private[_-]?key"
)

_FEEDBACK_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        re.compile(
            rf"(?i)\b((?:{_FEEDBACK_SECRET_FIELD})\s*[:=]\s*)"
            r"(['\"]?)[^\s'\"&,;]+",
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED_JWT]"),
    (re.compile(rf"(?i)([?&](?:{_FEEDBACK_SECRET_FIELD}|key|signature)=)[^&\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[REDACTED_EMAIL]"),
)


def redact_feedback_text(content: str) -> tuple[str, int]:
    redacted = content
    redaction_count = 0
    for pattern, replacement in _FEEDBACK_REDACTION_PATTERNS:
        redacted, count = pattern.subn(replacement, redacted)
        redaction_count += count
    return redacted, redaction_count


class UtilityService:
    def __init__(
        self,
        *,
        settings: Any,
        agent: Any,
        core_runtime_client: AegisCoreClient,
        workspace_manager: Any,
        resolve_workspace: Callable[[str | None], Path],
        invalidate_workspace_caches: Callable[[Path | None], None],
        refresh_runtime: Callable[[], None],
        update_env: Callable[[dict[str, str]], None],
        core_delegation_data: Callable[[CoreDelegationResult, str], dict[str, Any]],
        core_delegation_error: Callable[[CoreDelegationResult, str], HTTPException],
        record_core_fallback: Callable[[str, CoreDelegationResult], None],
    ) -> None:
        self.settings = settings
        self.agent = agent
        self.core_runtime_client = core_runtime_client
        self.workspace_manager = workspace_manager
        self._resolve_workspace = resolve_workspace
        self._invalidate_workspace_caches = invalidate_workspace_caches
        self._refresh_runtime = refresh_runtime
        self._update_env = update_env
        self._core_delegation_data = core_delegation_data
        self._core_delegation_error = core_delegation_error
        self._record_core_fallback = record_core_fallback

    async def root(self) -> dict:
        return {"message": "Auralith OS API is running on Aegis Core.", "ui": "http://127.0.0.1:5173"}

    async def get_memory_notes(self, workspace_root: str | None = None, category: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        core_result = await self.core_runtime_client.personal_memory(
            root,
            category=self._memory_category_to_core(category),
            limit=500,
        )
        if core_result.delegated:
            data = self._core_memory_data(core_result, "personal.memory")
            records = data.get("records", []) if isinstance(data.get("records"), list) else []
            notes = [self._memory_note_from_core(record) for record in records if isinstance(record, dict)]
            governance = self._memory_governance_from_core_data(data, runtime="aegis-core")
            return {
                "workspace_root": str(root),
                "warnings": [str(item) for item in data.get("warnings", []) if str(item).strip()]
                if isinstance(data.get("warnings"), list)
                else [],
                "notes": sorted(notes, key=lambda item: (bool(item.get("pinned")), str(item.get("updated_at") or "")), reverse=True),
                "governance": governance,
                "privacy": governance["privacy"],
                "controls": governance["controls"],
                "delegated": True,
                "runtime": "aegis-core",
            }
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory")
        self._record_core_fallback("personal.memory", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        notes = memory.get_notes_by_category(category) if category else list(memory.notes.values())
        governance = self._memory_governance_from_legacy(memory)
        return {
            "workspace_root": str(root),
            "warnings": [memory.storage_warning] if memory.storage_warning else [],
            "notes": [
                {
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
                for note in sorted(notes, key=lambda item: item.pinned, reverse=True)
            ],
            "governance": governance,
            "privacy": governance["privacy"],
            "controls": governance["controls"],
            "delegated": False,
            "runtime": "website-backend",
        }

    async def get_memory_governance(self, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        core_result = await self.core_runtime_client.personal_memory(root, limit=25)
        if core_result.delegated:
            data = self._core_memory_data(core_result, "personal.memory")
            governance = self._memory_governance_from_core_data(data, runtime="aegis-core")
            return {
                "workspace_root": str(root),
                "governance": governance,
                "privacy": governance["privacy"],
                "controls": governance["controls"],
                "categories": governance["categories"],
                "observability": data.get("observability") if isinstance(data.get("observability"), dict) else {},
                "delegated": True,
                "runtime": "aegis-core",
            }
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory")
        self._record_core_fallback("personal.memory", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        governance = self._memory_governance_from_legacy(memory)
        return {
            "workspace_root": str(root),
            "governance": governance,
            "privacy": governance["privacy"],
            "controls": governance["controls"],
            "categories": governance["categories"],
            "observability": {
                "records": {
                    "total": len(memory.notes),
                    "active": len(memory.notes),
                    "archived": 0,
                    "deleted_placeholders": 0,
                },
                "storage": {"path": str(memory.storage_path), "audit_available": False},
            },
            "delegated": False,
            "runtime": "website-backend",
            "warnings": governance["warnings"],
        }

    async def export_memory_notes(self, request: dict, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        raw_categories = request.get("categories", []) if isinstance(request, dict) else []
        categories = [
            category
            for category in (self._memory_category_to_core(str(item)) for item in raw_categories if str(item).strip())
            if category
        ] if isinstance(raw_categories, list) else []
        include_archived = bool(request.get("include_archived", False)) if isinstance(request, dict) else False
        redact_sensitive = bool(request.get("redact_sensitive", True)) if isinstance(request, dict) else True
        core_result = await self.core_runtime_client.export_personal_memory(
            root,
            categories=categories,
            include_archived=include_archived,
            redact_sensitive=redact_sensitive,
        )
        if core_result.delegated:
            data = self._core_memory_data(core_result, "personal.memory.export")
            export = data.get("export") if isinstance(data.get("export"), dict) else {}
            governance = self._memory_governance_from_core_data(export, runtime="aegis-core")
            return {
                "workspace_root": str(root),
                "export": export,
                "record_count": self._memory_export_record_count(data, export),
                "governance": governance,
                "delegated": True,
                "runtime": "aegis-core",
            }
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory.export")
        self._record_core_fallback("personal.memory.export", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        governance = self._memory_governance_from_legacy(memory)
        records = self._legacy_memory_export_records(
            memory,
            categories=[str(item).strip() for item in raw_categories] if isinstance(raw_categories, list) else [],
            redact_sensitive=redact_sensitive,
        )
        export = {
            "schema_version": 1,
            "exported_at": utc_now(),
            "workspace": str(root),
            "local_first": True,
            "redacted_sensitive": redact_sensitive,
            "records": records,
            "controls": governance["controls"],
            "privacy": governance["privacy"],
            "legacy_fallback": True,
        }
        return {
            "workspace_root": str(root),
            "export": export,
            "record_count": len(records),
            "governance": governance,
            "delegated": False,
            "runtime": "website-backend",
            "warnings": governance["warnings"],
        }

    async def update_memory_governance_controls(self, request: dict, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        core_result = await self.core_runtime_client.update_personal_memory_controls(
            root,
            category=self._memory_category_to_core(str(request.get("category"))) if request.get("category") else None,
            enabled=bool(request.get("enabled")) if request.get("enabled") is not None else None,
            retention_days=int(request.get("retention_days")) if request.get("retention_days") is not None else None,
            include_in_orchestration=bool(request.get("include_in_orchestration"))
            if request.get("include_in_orchestration") is not None
            else None,
            encrypted=bool(request.get("encrypted")) if request.get("encrypted") is not None else None,
            local_only=bool(request.get("local_only")) if request.get("local_only") is not None else None,
            disabled_categories=[
                category
                for category in (
                    self._memory_category_to_core(str(item))
                    for item in request.get("disabled_categories", [])
                    if str(item).strip()
                )
                if category
            ]
            if isinstance(request.get("disabled_categories"), list)
            else None,
            allowed_scopes=[str(item).strip() for item in request.get("allowed_scopes", []) if str(item).strip()]
            if isinstance(request.get("allowed_scopes"), list)
            else None,
        )
        if core_result.delegated:
            data = self._core_memory_data(core_result, "personal.memory.controls")
            governance = self._memory_governance_from_core_data(data, runtime="aegis-core")
            return {
                "workspace_root": str(root),
                "governance": governance,
                "privacy": governance["privacy"],
                "controls": governance["controls"],
                "categories": governance["categories"],
                "delegated": True,
                "runtime": "aegis-core",
            }
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory.controls")
        self._record_core_fallback("personal.memory.controls", core_result)
        raise HTTPException(
            status_code=503,
            detail="Memory governance controls require Aegis Core personal-memory controls; legacy Website memory is local-only and inspectable but has no category-control writer.",
        )

    async def create_memory_note(self, request: dict, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        legacy_category = str(request.get("category") or "insight")
        core_result = await self.core_runtime_client.create_personal_memory(
            root,
            category=self._memory_category_to_core(legacy_category) or "project_memory",
            title=str(request.get("title", "Untitled")),
            content=str(request.get("content", "")),
            tags=[str(item) for item in request.get("tags", [])] if isinstance(request.get("tags"), list) else [],
            related_files=[str(item) for item in request.get("related_files", [])]
            if isinstance(request.get("related_files"), list)
            else [],
            pinned=bool(request.get("pinned", False)),
            confidence=self._memory_confidence(request.get("confidence", 0.8)),
            metadata=self._memory_metadata(request, legacy_category),
        )
        if core_result.delegated:
            self._invalidate_workspace_caches(root)
            data = self._core_memory_data(core_result, "personal.memory.record")
            record = data.get("record") if isinstance(data.get("record"), dict) else {}
            return self._memory_note_from_core(record)
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory.record")
        self._record_core_fallback("personal.memory.record", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        try:
            note = memory.create_note(
                title=request.get("title", "Untitled"),
                content=request.get("content", ""),
                category=request.get("category", "insight"),
                tags=request.get("tags", []),
                related_files=request.get("related_files", []),
            )
            note = memory.update_note(
                note.id,
                pinned=bool(request.get("pinned", False)),
                confidence=request.get("confidence", note.confidence),
            ) or note
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update memory notes: {exc}") from exc
        self._invalidate_workspace_caches(root)
        return {
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

    async def update_memory_note(
        self,
        note_id: str,
        request: dict,
        workspace_root: str | None = None,
    ) -> dict:
        root = self._resolve_workspace(workspace_root)
        legacy_category = str(request.get("category")) if request.get("category") is not None else None
        metadata = self._memory_metadata(request, legacy_category) if legacy_category or isinstance(request.get("metadata"), dict) else None
        core_result = await self.core_runtime_client.update_personal_memory(
            root,
            note_id,
            category=self._memory_category_to_core(legacy_category),
            title=str(request.get("title")) if request.get("title") is not None else None,
            content=str(request.get("content")) if request.get("content") is not None else None,
            tags=[str(item) for item in request.get("tags", [])] if isinstance(request.get("tags"), list) else None,
            related_files=[str(item) for item in request.get("related_files", [])]
            if isinstance(request.get("related_files"), list)
            else None,
            pinned=bool(request.get("pinned")) if request.get("pinned") is not None else None,
            confidence=self._memory_confidence(request.get("confidence")) if request.get("confidence") is not None else None,
            metadata=metadata,
        )
        if core_result.delegated:
            self._invalidate_workspace_caches(root)
            data = self._core_memory_data(core_result, "personal.memory.record")
            record = data.get("record") if isinstance(data.get("record"), dict) else {}
            return self._memory_note_from_core(record)
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory.record")
        self._record_core_fallback("personal.memory.record", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        try:
            note = memory.update_note(note_id, **request)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update memory notes: {exc}") from exc
        if not note:
            if memory.storage_warning:
                raise HTTPException(status_code=503, detail=f"Could not read memory notes: {memory.storage_warning}")
            raise HTTPException(status_code=404, detail="Note not found")

        self._invalidate_workspace_caches(root)
        return {
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

    async def delete_memory_note(self, note_id: str, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        core_result = await self.core_runtime_client.delete_personal_memory(root, note_id, hard_delete=True)
        if core_result.delegated:
            self._invalidate_workspace_caches(root)
            data = self._core_memory_data(core_result, "personal.memory.deleted")
            if not bool(data.get("deleted", False)):
                raise HTTPException(status_code=404, detail="Note not found")
            return {"deleted": note_id, "delegated": True, "runtime": "aegis-core"}
        if not core_result.should_fallback:
            raise self._core_memory_error(core_result, "personal.memory.deleted")
        self._record_core_fallback("personal.memory.deleted", core_result)

        from ..memory_manager import MemoryManager

        memory = MemoryManager(root)
        try:
            deleted = memory.delete_note(note_id)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Could not update memory notes: {exc}") from exc
        if not deleted:
            if memory.storage_warning:
                raise HTTPException(status_code=503, detail=f"Could not read memory notes: {memory.storage_warning}")
            raise HTTPException(status_code=404, detail="Note not found")

        self._invalidate_workspace_caches(root)
        return {"deleted": note_id, "delegated": False, "runtime": "website-backend"}

    async def record_feedback(
        self,
        request: FeedbackRecordRequest,
        workspace_root: str | None = None,
    ) -> FeedbackRecordResponse:
        root = self._resolve_workspace(workspace_root)
        privacy_policy = self._feedback_privacy_policy()
        content = request.content.strip()
        excerpt, redaction_count = self._feedback_memory_excerpt(content, privacy_policy)
        feedback_metadata = dict(request.metadata or {})
        feedback_metadata.update(
            {
                "feedback_privacy_shared_workspace": bool(privacy_policy["shared_workspace"]),
                "feedback_privacy_capture_excerpts": bool(privacy_policy["capture_excerpts"]),
                "feedback_privacy_redaction_enabled": bool(privacy_policy["redact_excerpts"]),
                "feedback_privacy_hash_content": bool(privacy_policy["hash_content"]),
                "feedback_privacy_max_excerpt_chars": int(privacy_policy["max_excerpt_chars"]),
                "feedback_privacy_redaction_count": redaction_count,
                "feedback_original_content_length": len(request.content or ""),
            }
        )
        telemetry_request = request.model_copy(
            update={
                "content": request.content if bool(privacy_policy["hash_content"]) else "",
                "metadata": feedback_metadata,
            }
        )
        event = self.agent.store.record_feedback(project_root=root, request=telemetry_request)
        title = f"User {request.sentiment} {request.target or 'Aegis output'}"
        detail_parts = [
            f"Sentiment: {request.sentiment}",
            f"Action: {request.action}",
            f"Target: {request.target or 'assistant_response'}",
            f"Task: {request.task_id or 'unknown'}",
            f"Model: {request.model_label or 'unknown'}",
            f"Context: {request.context or 'assistant_message'}",
            f"Content hash: {event.content_hash or 'empty'}",
            f"Excerpt capture: {'enabled' if privacy_policy['capture_excerpts'] else 'disabled'}",
            f"Redaction: {'enabled' if privacy_policy['redact_excerpts'] else 'disabled'}",
            f"Shared workspace: {'yes' if privacy_policy['shared_workspace'] else 'no'}",
        ]
        if excerpt:
            detail_parts.extend(["Redacted excerpt:" if redaction_count else "Excerpt:", excerpt])
        elif content:
            detail_parts.append("Excerpt: [disabled by feedback privacy policy]")
        self.agent.store.remember_project_note(
            project_root=root,
            category="feedback",
            title=title[:160],
            detail="\n".join(detail_parts),
            source="desktop_feedback",
            confidence=0.86 if request.sentiment in {"liked", "disliked", "accepted", "rejected"} else 0.68,
        )
        self._invalidate_workspace_caches(root)
        return FeedbackRecordResponse(ok=True, workspace_root=str(root), event=event)

    async def get_approval_settings(self, workspace_root: str | None = None) -> dict:
        self._resolve_workspace(workspace_root)
        from ..approval_sandbox import ApprovalManager, SandboxProfileManager

        manager = ApprovalManager(self.settings.approval_tier, self.settings.sandbox_profile)
        return {
            "approval_tier": manager.tier.value,
            "sandbox_profile": manager.sandbox,
            "available_tiers": ["manual", "prompt", "guided", "autonomous"],
            "available_profiles": list(SandboxProfileManager.PROFILES.keys()),
        }

    async def update_approval_settings(self, request: dict, workspace_root: str | None = None) -> dict:
        self._resolve_workspace(workspace_root)
        from ..approval_sandbox import ApprovalManager

        try:
            manager = ApprovalManager(
                request.get("approval_tier", self.settings.approval_tier),
                request.get("sandbox_profile", self.settings.sandbox_profile),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        self._update_env(
            {
                "APPROVAL_TIER": manager.tier.value,
                "SANDBOX_PROFILE": manager.sandbox,
            }
        )
        self._refresh_runtime()
        return {
            "approval_tier": manager.tier.value,
            "sandbox_profile": manager.sandbox,
        }

    async def rebuild_index(self, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        from ..project_indexer import ProjectIndexer

        indexer = ProjectIndexer()
        files = self.workspace_manager.scan(root, max_files=500)
        indexer.build_from_workspace(root, files)
        return {
            "indexed": len(indexer.index),
            "files": list(indexer.index.keys())[:10],
            "workspace": str(root),
        }

    async def search_index(self, request: dict, workspace_root: str | None = None) -> dict:
        root = self._resolve_workspace(workspace_root)
        from ..project_indexer import ProjectIndexer

        indexer = ProjectIndexer()
        query = request.get("query", "")
        top_k = request.get("top_k", 5)
        if not query:
            return {"results": [], "query": query}

        files = self.workspace_manager.scan(root, max_files=500)
        indexer.build_from_workspace(root, files)
        relevant_files = indexer.find_relevant_files(query, max_results=top_k)
        return {
            "query": query,
            "indexed": len(indexer.index),
            "results": [
                {
                    "path": str(file.path),
                    "kind": file.kind,
                    "size": file.size,
                    "relevance": file.relevance_score,
                }
                for file in relevant_files
            ],
            "workspace": str(root),
        }

    async def compare_files(self, request: dict, workspace_root: str | None = None) -> dict:
        from ..diff_engine import DiffEngine

        old_content = request.get("old_content")
        new_content = request.get("new_content")
        path = request.get("path", "file")
        action = request.get("action", "update")
        if action == "create":
            if new_content is None:
                raise HTTPException(status_code=400, detail="new_content required for create diffs")
        elif action == "delete":
            if old_content is None:
                raise HTTPException(status_code=400, detail="old_content required for delete diffs")
        elif old_content is None or new_content is None:
            raise HTTPException(status_code=400, detail="old_content and new_content required")

        diff = DiffEngine.compare_files(old_content, new_content, path, action)
        return {
            "path": diff.path,
            "action": diff.action,
            "patch": diff.get_patch(),
            "added_lines": diff.added_lines,
            "removed_lines": diff.removed_lines,
            "modified_lines": diff.modified_lines,
        }

    async def apply_patch(self, request: dict, workspace_root: str | None = None) -> dict:
        from ..diff_engine import DiffEngine

        original_content = request.get("original_content")
        patch_content = request.get("patch_content")
        if original_content is None or patch_content is None:
            raise HTTPException(status_code=400, detail="original_content and patch_content required")

        try:
            patched = DiffEngine.apply_patch(original_content, patch_content)
            if patched is None:
                raise HTTPException(status_code=400, detail="Failed to apply patch")
            return {
                "applied": True,
                "patched_content": patched,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to apply patch: {str(exc)}")

    async def summarize_diff(self, request: dict) -> dict:
        from ..diff_engine import DiffEngine

        path = request.get("path", "file")
        action = request.get("action", "update")
        old_content = request.get("old_content")
        new_content = request.get("new_content")
        if not all([path, action, new_content is not None]):
            raise HTTPException(status_code=400, detail="path, action, and new_content required")

        diff = DiffEngine.compare_files(old_content, new_content, path, action)
        summary = DiffEngine.summarize_diff(diff)
        return {
            "summary": summary,
            "path": path,
        }

    def _memory_category_to_core(self, category: str | None) -> str | None:
        if not category:
            return None
        clean = str(category).strip().lower().replace("-", "_").replace(" ", "_")
        return _LEGACY_TO_CORE_MEMORY_CATEGORY.get(clean, clean if clean in _CORE_TO_LEGACY_MEMORY_CATEGORY else "project_memory")

    def _memory_category_from_core(self, record: dict[str, Any]) -> str:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        legacy_category = str(metadata.get("legacy_category") or "").strip()
        if legacy_category:
            return legacy_category
        category = str(record.get("category") or "project_memory")
        return _CORE_TO_LEGACY_MEMORY_CATEGORY.get(category, "insight")

    def _memory_note_from_core(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(record.get("id") or ""),
            "title": str(record.get("title") or "Untitled"),
            "content": str(record.get("content") or ""),
            "category": self._memory_category_from_core(record),
            "created_at": str(record.get("created_at") or ""),
            "updated_at": str(record.get("updated_at") or record.get("created_at") or ""),
            "pinned": bool(record.get("pinned", False)),
            "tags": [str(item) for item in record.get("tags", []) if str(item).strip()],
            "related_files": [str(item) for item in record.get("related_files", []) if str(item).strip()],
            "confidence": self._memory_confidence(record.get("confidence", 0.8)),
        }

    def _memory_governance_from_core_data(self, data: dict[str, Any], *, runtime: str) -> dict[str, Any]:
        controls = data.get("controls") if isinstance(data.get("controls"), dict) else {}
        privacy = data.get("privacy") if isinstance(data.get("privacy"), dict) else {}
        observability = data.get("observability") if isinstance(data.get("observability"), dict) else {}
        raw_categories = data.get("categories") if isinstance(data.get("categories"), list) else []
        categories = self._memory_category_items(controls, raw_categories)
        disabled_categories = [item["id"] for item in categories if not bool(item.get("enabled", True))]
        orchestration_excluded = [
            item["id"] for item in categories if not bool(item.get("include_in_orchestration", True))
        ]
        retention_by_category = {
            item["id"]: item.get("retention_days")
            for item in categories
            if item.get("retention_days") not in (None, "")
        }
        local_only = bool(privacy.get("local_only", controls.get("local_only", True)))
        cloud_memory_sharing = bool(privacy.get("cloud_memory_sharing", controls.get("cloud_memory_sharing", False)))
        sensitive_exclusions = bool(
            privacy.get("sensitive_memory_exclusions", controls.get("sensitive_memory_exclusions", True))
        )
        transparency = controls.get("transparency") if isinstance(controls.get("transparency"), dict) else {}
        audit_events = data.get("audit_events") if isinstance(data.get("audit_events"), list) else []
        storage = observability.get("storage") if isinstance(observability.get("storage"), dict) else {}
        safe_privacy = {
            "local_only": local_only,
            "cloud_memory_sharing": cloud_memory_sharing,
            "sensitive_memory_exclusions": sensitive_exclusions,
            "per_project_isolation": bool(privacy.get("per_project_isolation", True)),
            "inspectable": bool(privacy.get("inspectable", transparency.get("inspectable", True))),
            "editable": bool(privacy.get("editable", transparency.get("editable", True))),
            "exportable": bool(privacy.get("exportable", transparency.get("exportable", True))),
            "deletable": bool(privacy.get("deletable", transparency.get("deletable", True))),
            "encrypted_storage_requested_categories": [
                str(item) for item in privacy.get("encrypted_storage_requested_categories", []) if str(item).strip()
            ]
            if isinstance(privacy.get("encrypted_storage_requested_categories"), list)
            else [],
            "encrypted_storage_active_categories": [
                str(item) for item in privacy.get("encrypted_storage_active_categories", []) if str(item).strip()
            ]
            if isinstance(privacy.get("encrypted_storage_active_categories"), list)
            else [],
            "encrypted_storage_available": bool(privacy.get("encrypted_storage_available", storage.get("encrypted_storage_available", False))),
        }
        controls_with_defaults = {
            **controls,
            "local_only": local_only,
            "cloud_memory_sharing": cloud_memory_sharing,
            "sensitive_memory_exclusions": sensitive_exclusions,
            "allowed_scopes": [
                str(item) for item in controls.get("allowed_scopes", ["user", "workspace", "project", "workflow"]) if str(item).strip()
            ],
            "transparency": {
                "inspectable": safe_privacy["inspectable"],
                "editable": safe_privacy["editable"],
                "exportable": safe_privacy["exportable"],
                "deletable": safe_privacy["deletable"],
                "category_controls": bool(transparency.get("category_controls", True)),
            },
        }
        warnings = []
        if safe_privacy["encrypted_storage_requested_categories"] and not safe_privacy["encrypted_storage_active_categories"]:
            warnings.append("Encrypted memory storage was requested, but no active encrypted-storage category is available.")
        return {
            "runtime": runtime,
            "mode": self._memory_governance_mode(local_only, cloud_memory_sharing),
            "local_only": local_only,
            "cloud_memory_sharing": cloud_memory_sharing,
            "cloud_context_requires_consent": not cloud_memory_sharing,
            "sensitive_memory_exclusions": sensitive_exclusions,
            "per_project_isolation": safe_privacy["per_project_isolation"],
            "inspectable": safe_privacy["inspectable"],
            "editable": safe_privacy["editable"],
            "exportable": safe_privacy["exportable"],
            "deletable": safe_privacy["deletable"],
            "allowed_scopes": controls_with_defaults["allowed_scopes"],
            "disabled_categories": disabled_categories,
            "orchestration_excluded_categories": orchestration_excluded,
            "retention_by_category": retention_by_category,
            "sensitive_export_default": "redacted",
            "storage_boundary": "aegis-core-project-memory",
            "audit_available": bool(audit_events or storage.get("audit_file")),
            "audit_event_count": len(audit_events),
            "categories": categories,
            "controls": controls_with_defaults,
            "privacy": safe_privacy,
            "warnings": warnings,
        }

    def _memory_governance_from_legacy(self, memory: Any) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for note in memory.notes.values():
            category = str(note.category or "insight")
            counts[category] = counts.get(category, 0) + 1
        categories = [
            {
                "id": category,
                "label": category.replace("_", " ").replace("-", " ").title(),
                "record_count": count,
                "enabled": True,
                "retention_days": None,
                "include_in_orchestration": True,
                "encrypted": False,
                "encrypted_storage_active": False,
            }
            for category, count in sorted(counts.items())
        ]
        controls = {
            "local_only": True,
            "cloud_memory_sharing": False,
            "sensitive_memory_exclusions": False,
            "allowed_scopes": ["project"],
            "categories": {item["id"]: {key: value for key, value in item.items() if key not in {"id", "label", "record_count"}} for item in categories},
            "transparency": {
                "inspectable": True,
                "editable": True,
                "exportable": True,
                "deletable": True,
                "category_controls": False,
            },
        }
        privacy = {
            "local_only": True,
            "cloud_memory_sharing": False,
            "sensitive_memory_exclusions": False,
            "per_project_isolation": True,
            "inspectable": True,
            "editable": True,
            "exportable": True,
            "deletable": True,
            "encrypted_storage_requested_categories": [],
            "encrypted_storage_active_categories": [],
            "encrypted_storage_available": False,
        }
        warnings = [memory.storage_warning] if getattr(memory, "storage_warning", "") else []
        warnings.append("Legacy Website memory fallback has no category-control writer; reconnect Aegis Core for full memory governance.")
        return {
            "runtime": "website-backend",
            "mode": "local_only",
            "local_only": True,
            "cloud_memory_sharing": False,
            "cloud_context_requires_consent": True,
            "sensitive_memory_exclusions": False,
            "per_project_isolation": True,
            "inspectable": True,
            "editable": True,
            "exportable": True,
            "deletable": True,
            "allowed_scopes": ["project"],
            "disabled_categories": [],
            "orchestration_excluded_categories": [],
            "retention_by_category": {},
            "sensitive_export_default": "redacted",
            "storage_boundary": "website-backend-local-memory-files",
            "audit_available": False,
            "audit_event_count": 0,
            "categories": categories,
            "controls": controls,
            "privacy": privacy,
            "warnings": warnings,
        }

    def _memory_category_items(self, controls: dict[str, Any], raw_categories: list[Any]) -> list[dict[str, Any]]:
        if raw_categories:
            return [
                item
                for item in (
                    category if isinstance(category, dict) else {"id": str(category), "label": str(category)}
                    for category in raw_categories
                )
                if str(item.get("id") or "").strip()
            ]
        category_controls = controls.get("categories") if isinstance(controls.get("categories"), dict) else {}
        return [
            {
                "id": str(category),
                "label": str(category).replace("_", " ").replace("-", " ").title(),
                "record_count": 0,
                **(control if isinstance(control, dict) else {}),
            }
            for category, control in category_controls.items()
        ]

    def _legacy_memory_export_records(self, memory: Any, *, categories: list[str], redact_sensitive: bool) -> list[dict[str, Any]]:
        wanted = {item for item in categories if item}
        records: list[dict[str, Any]] = []
        for note in sorted(memory.notes.values(), key=lambda item: (bool(item.pinned), str(item.updated_at)), reverse=True):
            if wanted and str(note.category) not in wanted:
                continue
            title = str(note.title or "Untitled")
            content = str(note.content or "")
            redactions = 0
            if redact_sensitive:
                title, title_redactions = self._redact_feedback_text(title)
                content, content_redactions = self._redact_feedback_text(content)
                redactions = title_redactions + content_redactions
            records.append(
                {
                    "id": note.id,
                    "category": note.category,
                    "scope": "project",
                    "title": title,
                    "content": content,
                    "summary": content[:240],
                    "tags": note.tags,
                    "related_files": note.related_files,
                    "source": "website-backend",
                    "confidence": note.confidence,
                    "status": "active",
                    "pinned": note.pinned,
                    "created_at": note.created_at,
                    "updated_at": note.updated_at,
                    "privacy": {
                        "local_only": True,
                        "sensitive": redactions > 0,
                        "excluded_from_cloud": True,
                    },
                    "redaction_count": redactions,
                }
            )
        return records

    def _memory_export_record_count(self, data: dict[str, Any], export: dict[str, Any]) -> int:
        try:
            return int(data.get("record_count"))
        except (TypeError, ValueError):
            pass
        records = export.get("records")
        return len(records) if isinstance(records, list) else 0

    def _memory_governance_mode(self, local_only: bool, cloud_memory_sharing: bool) -> str:
        if local_only:
            return "local_only"
        if cloud_memory_sharing:
            return "cloud_allowed"
        return "project_only"

    def _memory_confidence(self, value: Any, default: float = 0.8) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = default
        return max(0.0, min(1.0, confidence))

    def _core_memory_data(self, result: CoreDelegationResult, workflow: str) -> dict[str, Any]:
        return self._core_delegation_data(result, workflow)

    def _core_memory_error(self, result: CoreDelegationResult, workflow: str) -> HTTPException:
        if "not found" in (result.error or "").lower():
            return HTTPException(status_code=404, detail=result.error or "Memory note not found")
        return self._core_delegation_error(result, workflow)

    def _memory_metadata(self, request: dict[str, Any], category: str | None = None) -> dict[str, Any]:
        metadata = dict(request.get("metadata") or {}) if isinstance(request.get("metadata"), dict) else {}
        if category:
            metadata["legacy_category"] = str(category)
        metadata.setdefault("compatibility_surface", "website.api.memory")
        return metadata

    def _redact_feedback_text(self, content: str) -> tuple[str, int]:
        return redact_feedback_text(content)

    def _feedback_privacy_policy(self) -> dict[str, bool | int]:
        shared_workspace = bool(self.settings.aegis_shared_workspace_mode)
        capture_excerpts = bool(self.settings.aegis_feedback_capture_excerpts) and not shared_workspace
        redact_excerpts = bool(self.settings.aegis_feedback_redaction_enabled)
        max_excerpt_chars = max(0, min(2000, int(self.settings.aegis_feedback_max_excerpt_chars or 0)))
        hash_content = bool(self.settings.aegis_feedback_hash_content) and not shared_workspace
        return {
            "shared_workspace": shared_workspace,
            "capture_excerpts": capture_excerpts,
            "redact_excerpts": redact_excerpts,
            "max_excerpt_chars": max_excerpt_chars,
            "hash_content": hash_content,
        }

    def _feedback_memory_excerpt(self, content: str, policy: dict[str, bool | int]) -> tuple[str, int]:
        if not content or not policy["capture_excerpts"] or int(policy["max_excerpt_chars"]) <= 0:
            return "", 0
        if bool(policy["redact_excerpts"]):
            redacted, count = self._redact_feedback_text(content)
            return redacted[: int(policy["max_excerpt_chars"])], count
        return content[: int(policy["max_excerpt_chars"])], 0
