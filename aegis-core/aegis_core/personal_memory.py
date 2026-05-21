from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now


SCHEMA_VERSION = 1
MEMORY_FILE = "auralith-memory.json"
AUDIT_FILE = "auralith-memory-audit.jsonl"
MAX_RECORDS = 5000
MAX_CONTENT_CHARS = 20_000
MAX_EXPORT_RECORDS = 5000

MEMORY_CATEGORIES = {
    "user_preferences": {"label": "User Preferences", "default_retention_days": None, "orchestration": True},
    "workspace_preferences": {"label": "Workspace Preferences", "default_retention_days": None, "orchestration": True},
    "project_memory": {"label": "Project Memory", "default_retention_days": None, "orchestration": True},
    "execution_history": {"label": "Execution History", "default_retention_days": 180, "orchestration": True},
    "repair_history": {"label": "Repair History", "default_retention_days": 180, "orchestration": True},
    "validation_history": {"label": "Validation History", "default_retention_days": 180, "orchestration": True},
    "roadmap_history": {"label": "Roadmap History", "default_retention_days": 365, "orchestration": True},
    "architecture_notes": {"label": "Architecture Notes", "default_retention_days": None, "orchestration": True},
    "workflow_patterns": {"label": "Workflow Patterns", "default_retention_days": None, "orchestration": True},
    "ui_preferences": {"label": "UI Preferences", "default_retention_days": None, "orchestration": False},
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|credential|bearer)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
]


class PersonalMemoryPersistenceError(RuntimeError):
    """Raised when personal memory cannot be persisted safely."""


def memory_dashboard(
    workspace: str | Path,
    *,
    query: str = "",
    category: str | None = None,
    scope: str | None = None,
    include_archived: bool = False,
    include_disabled: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    start = time.perf_counter()
    root = _workspace_root(workspace)
    state = _load_state(root)
    records = _filter_records(
        state,
        query=query,
        category=category,
        scope=scope,
        include_archived=include_archived,
        include_disabled=include_disabled,
    )
    records = records[: max(1, min(500, int(limit or 100)))]
    observability = _observability(root, state, latency_ms=_elapsed_ms(start))
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": utc_now(),
        "categories": _category_catalog(state),
        "controls": state.get("controls", {}),
        "records": [_public_record(record) for record in records],
        "timeline": _timeline(state, include_archived=include_archived)[:100],
        "observability": observability,
        "privacy": _privacy_summary(state),
        "export_endpoint": "/v1/personal-memory/export",
        "import_endpoint": "/v1/personal-memory/import",
        "audit_events": _read_audit(root, limit=25),
    }


def create_memory(
    workspace: str | Path,
    *,
    category: str,
    title: str,
    content: str,
    scope: str = "project",
    tags: list[str] | None = None,
    related_files: list[str] | None = None,
    source: str = "user",
    confidence: float = 0.8,
    pinned: bool = False,
    expires_at: str | None = None,
    privacy: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    clean_category = _normalize_category(category)
    _require_category_enabled(state, clean_category)
    now = utc_now()
    text, redactions = _sanitize_content(content)
    title_text, title_redactions = _sanitize_content(title, max_chars=240)
    redactions += title_redactions
    record_id = f"mem-{uuid4().hex[:12]}"
    record_privacy = _record_privacy(state, clean_category, privacy or {}, bool(redactions))
    record = {
        "id": record_id,
        "version": 1,
        "category": clean_category,
        "scope": _normalize_scope(scope),
        "title": title_text.strip() or "Untitled memory",
        "content": text,
        "summary": _summary(text),
        "tags": _clean_list(tags),
        "related_files": _clean_paths(related_files),
        "source": source or "user",
        "confidence": _confidence(confidence),
        "status": "active",
        "pinned": bool(pinned),
        "expires_at": _normalize_expires_at(expires_at, state, clean_category),
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
        "usage": {
            "retrieval_count": 0,
            "last_retrieved_at": None,
            "used_by_workflows": [],
        },
        "privacy": record_privacy,
        "metadata": _sanitize_metadata(metadata or {}),
        "redaction_count": redactions,
        "fingerprint": _fingerprint(clean_category, title_text, text),
    }
    if record_privacy.get("encrypted_requested") and not record_privacy.get("encrypted_storage_active"):
        record.setdefault("warnings", []).append("Encrypted storage was requested, but no AEGIS_MEMORY_ENCRYPTION_KEY is configured.")
    state["records"].append(record)
    state["records"] = _dedupe_records(state["records"])[-MAX_RECORDS:]
    _append_audit(root, state, "memory.created", record_id=record_id, details={"category": clean_category, "scope": record["scope"]})
    _save_state(root, state)
    return {"workspace": str(root), "record": _public_record(record), "warnings": record.get("warnings", []), "observability": _observability(root, state)}


def update_memory(
    workspace: str | Path,
    memory_id: str,
    *,
    category: str | None = None,
    title: str | None = None,
    content: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    related_files: list[str] | None = None,
    confidence: float | None = None,
    pinned: bool | None = None,
    expires_at: str | None = None,
    privacy: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    record = _get_record(state, memory_id)
    redactions = 0
    if category is not None:
        clean_category = _normalize_category(category)
        _require_category_enabled(state, clean_category)
        record["category"] = clean_category
    if title is not None:
        record["title"], count = _sanitize_content(title, max_chars=240)
        redactions += count
    if content is not None:
        record["content"], count = _sanitize_content(content)
        record["summary"] = _summary(record["content"])
        redactions += count
    if scope is not None:
        record["scope"] = _normalize_scope(scope)
    if tags is not None:
        record["tags"] = _clean_list(tags)
    if related_files is not None:
        record["related_files"] = _clean_paths(related_files)
    if confidence is not None:
        record["confidence"] = _confidence(confidence)
    if pinned is not None:
        record["pinned"] = bool(pinned)
    if expires_at is not None:
        record["expires_at"] = _normalize_expires_at(expires_at, state, record["category"])
    if privacy is not None:
        record["privacy"] = _record_privacy(state, record["category"], privacy, record.get("privacy", {}).get("sensitive", False) or bool(redactions))
    if metadata is not None:
        record["metadata"] = _sanitize_metadata(metadata)
    record["redaction_count"] = int(record.get("redaction_count") or 0) + redactions
    record["fingerprint"] = _fingerprint(record["category"], record["title"], record["content"])
    record["updated_at"] = utc_now()
    _append_audit(root, state, "memory.updated", record_id=record["id"], details={"category": record["category"]})
    _save_state(root, state)
    return {"workspace": str(root), "record": _public_record(record), "warnings": record.get("warnings", []), "observability": _observability(root, state)}


def archive_memory(workspace: str | Path, memory_id: str, *, reason: str = "") -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    record = _get_record(state, memory_id)
    record["status"] = "archived"
    record["archived_at"] = utc_now()
    record["updated_at"] = record["archived_at"]
    if reason:
        record.setdefault("metadata", {})["archive_reason"] = scrub(reason)
    _append_audit(root, state, "memory.archived", record_id=record["id"], details={"reason": scrub(reason)})
    _save_state(root, state)
    return {"workspace": str(root), "record": _public_record(record), "observability": _observability(root, state)}


def delete_memory(workspace: str | Path, memory_id: str, *, hard_delete: bool = False, reason: str = "") -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    record = _get_record(state, memory_id)
    if hard_delete:
        state["records"] = [item for item in state.get("records", []) if item.get("id") != record["id"]]
        deleted = True
    else:
        record["status"] = "deleted"
        record["deleted_at"] = utc_now()
        record["updated_at"] = record["deleted_at"]
        record["content"] = ""
        record["summary"] = "Deleted memory placeholder."
        record.setdefault("metadata", {})["delete_reason"] = scrub(reason)
        deleted = True
    _append_audit(root, state, "memory.deleted", record_id=record["id"], details={"hard_delete": hard_delete, "reason": scrub(reason)})
    _save_state(root, state)
    return {"workspace": str(root), "memory_id": record["id"], "deleted": deleted, "hard_delete": hard_delete, "observability": _observability(root, state)}


def export_memory(
    workspace: str | Path,
    *,
    categories: list[str] | None = None,
    include_archived: bool = False,
    redact_sensitive: bool = True,
    include_controls: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    wanted = {_normalize_category(item) for item in categories or []}
    records = []
    for record in state.get("records", []):
        if record.get("status") == "deleted":
            continue
        if record.get("status") == "archived" and not include_archived:
            continue
        if wanted and record.get("category") not in wanted:
            continue
        exported = _public_record(record)
        if redact_sensitive and exported.get("privacy", {}).get("sensitive"):
            exported["content"] = "[redacted sensitive memory]"
            exported["summary"] = "[redacted sensitive memory]"
        records.append(exported)
        if len(records) >= MAX_EXPORT_RECORDS:
            break
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": utc_now(),
        "workspace": str(root),
        "local_first": True,
        "redacted_sensitive": bool(redact_sensitive),
        "records": records,
        "controls": state.get("controls", {}) if include_controls else {},
        "privacy": _privacy_summary(state),
    }
    _append_audit(root, state, "memory.exported", details={"record_count": len(records), "redacted_sensitive": redact_sensitive})
    _save_state(root, state)
    return {"workspace": str(root), "export": bundle, "record_count": len(records)}


def import_memory(
    workspace: str | Path,
    payload: dict[str, Any] | list[Any],
    *,
    merge_strategy: str = "append",
    dry_run: bool = True,
    source: str = "import",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    incoming = _records_from_import_payload(payload)
    normalized: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in incoming:
        try:
            normalized.append(_normalize_import_record(state, item, source=source))
        except ValueError as exc:
            warnings.append(scrub(str(exc)))
    preview = [_public_record(item) for item in normalized]
    if dry_run:
        return {
            "workspace": str(root),
            "dry_run": True,
            "merge_strategy": merge_strategy,
            "imported_count": 0,
            "preview_count": len(preview),
            "records": preview,
            "warnings": warnings,
        }
    strategy = merge_strategy if merge_strategy in {"append", "upsert", "replace"} else "append"
    if strategy == "replace":
        state["records"] = [item for item in state.get("records", []) if item.get("pinned")]
    if strategy == "upsert":
        by_id = {item.get("id"): item for item in state.get("records", []) if item.get("id")}
        for item in normalized:
            by_id[item["id"]] = item
        state["records"] = list(by_id.values())[-MAX_RECORDS:]
    else:
        existing_ids = {item.get("id") for item in state.get("records", [])}
        for item in normalized:
            if item["id"] in existing_ids:
                item["id"] = f"mem-{uuid4().hex[:12]}"
            state["records"].append(item)
        state["records"] = _dedupe_records(state["records"])[-MAX_RECORDS:]
    _append_audit(root, state, "memory.imported", details={"count": len(normalized), "merge_strategy": strategy, "source": source})
    _save_state(root, state)
    return {
        "workspace": str(root),
        "dry_run": False,
        "merge_strategy": strategy,
        "imported_count": len(normalized),
        "records": preview,
        "warnings": warnings,
        "observability": _observability(root, state),
    }


def update_memory_controls(
    workspace: str | Path,
    *,
    category: str | None = None,
    enabled: bool | None = None,
    retention_days: int | None = None,
    include_in_orchestration: bool | None = None,
    encrypted: bool | None = None,
    local_only: bool | None = None,
    disabled_categories: list[str] | None = None,
    allowed_scopes: list[str] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    controls = state.setdefault("controls", _default_controls())
    if disabled_categories is not None:
        for item in MEMORY_CATEGORIES:
            controls["categories"].setdefault(item, _default_category_control(item))
            controls["categories"][item]["enabled"] = item not in {_normalize_category(value) for value in disabled_categories}
    if allowed_scopes is not None:
        controls["allowed_scopes"] = [_normalize_scope(item) for item in allowed_scopes]
    if local_only is not None:
        controls["local_only"] = bool(local_only)
    if category:
        clean_category = _normalize_category(category)
        cat = controls["categories"].setdefault(clean_category, _default_category_control(clean_category))
        if enabled is not None:
            cat["enabled"] = bool(enabled)
        if retention_days is not None:
            cat["retention_days"] = max(1, int(retention_days)) if int(retention_days) > 0 else None
        if include_in_orchestration is not None:
            cat["include_in_orchestration"] = bool(include_in_orchestration)
        if encrypted is not None:
            cat["encrypted"] = bool(encrypted)
            cat["encrypted_storage_active"] = bool(encrypted and _encryption_available())
            if encrypted and not cat["encrypted_storage_active"]:
                cat["encryption_warning"] = "Set AEGIS_MEMORY_ENCRYPTION_KEY to activate encrypted JSON payload storage."
    controls["updated_at"] = utc_now()
    _append_audit(root, state, "memory.controls.updated", details={"category": category or "all"})
    _save_state(root, state)
    return {"workspace": str(root), "controls": controls, "categories": _category_catalog(state), "privacy": _privacy_summary(state)}


def cleanup_memory(workspace: str | Path, *, dry_run: bool = True, archive_stale: bool = True) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    stale: list[str] = []
    for record in state.get("records", []):
        if record.get("status") != "active":
            continue
        expires_at = _parse_time(record.get("expires_at"))
        if expires_at and expires_at <= now:
            expired.append(record["id"])
            if not dry_run:
                record["status"] = "archived" if archive_stale else "deleted"
                record["archived_at"] = utc_now()
                record["updated_at"] = record["archived_at"]
        elif _is_stale(record, state, now):
            stale.append(record["id"])
            if not dry_run and archive_stale:
                record["status"] = "archived"
                record["archived_at"] = utc_now()
                record["updated_at"] = record["archived_at"]
    if not dry_run:
        _append_audit(root, state, "memory.cleanup", details={"expired": expired, "stale": stale, "archive_stale": archive_stale})
        _save_state(root, state)
    return {"workspace": str(root), "dry_run": dry_run, "expired_ids": expired, "stale_ids": stale, "observability": _observability(root, state)}


def memory_observability(workspace: str | Path) -> dict[str, Any]:
    start = time.perf_counter()
    root = _workspace_root(workspace)
    state = _load_state(root)
    return {
        "workspace": str(root),
        "observability": _observability(root, state, latency_ms=_elapsed_ms(start)),
        "privacy": _privacy_summary(state),
        "conflicts": _conflicting_memories(state),
        "audit_summary": _audit_summary(root),
        "recent_audit_events": _read_audit(root, limit=25),
    }


def memory_orchestration_context(
    workspace: str | Path,
    *,
    workflow_type: str = "",
    objective: str = "",
    max_items: int = 12,
    record_usage: bool = True,
) -> dict[str, Any]:
    start = time.perf_counter()
    root = _workspace_root(workspace)
    state = _load_state(root)
    query = " ".join([workflow_type, objective]).strip()
    records = _filter_records(state, query=query, include_archived=False, orchestration_only=True, limit=max_items)
    if record_usage and records:
        now = utc_now()
        for record in records:
            usage = record.setdefault("usage", {})
            usage["retrieval_count"] = int(usage.get("retrieval_count") or 0) + 1
            usage["last_retrieved_at"] = now
            workflow_key = workflow_type or "workflow"
            used = list(usage.get("used_by_workflows") or [])
            if workflow_key not in used:
                used.append(workflow_key)
            usage["used_by_workflows"] = used[-20:]
        _append_audit(root, state, "memory.retrieved", details={"workflow_type": workflow_type, "record_count": len(records)})
        _save_state(root, state)
    guidance = _memory_guidance(records, state, workflow_type)
    return {
        "workspace": str(root),
        "workflow_type": workflow_type,
        "objective": scrub(objective)[:500],
        "records": [_public_record(item, include_content=False) for item in records],
        "guidance": guidance,
        "privacy": _privacy_summary(state),
        "latency_ms": _elapsed_ms(start),
    }


def compact_memory_summary(workspace: str | Path) -> dict[str, Any]:
    try:
        root = _workspace_root(workspace)
        state = _load_state(root)
        obs = _observability(root, state)
    except Exception as exc:
        return {"status": "error", "error": scrub(str(exc)), "record_count": 0}
    return {
        "status": "ok",
        "record_count": obs["records"]["total"],
        "active_count": obs["records"]["active"],
        "pinned_count": obs["records"]["pinned"],
        "stale_count": obs["records"]["stale"],
        "category_counts": obs["records"]["by_category"],
        "privacy": _privacy_summary(state),
    }


def _load_state(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    memory.ensure()
    path = memory.root / MEMORY_FILE
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            state = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise PersonalMemoryPersistenceError(f"Could not read personal memory at {path}: {scrub(str(exc))}") from exc
    else:
        state = {}
    if state.get("schema_version") != SCHEMA_VERSION:
        state = _new_state(root)
    state.setdefault("records", [])
    state.setdefault("controls", _default_controls())
    _normalize_controls(state)
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    memory = ProjectMemory(root)
    memory.ensure()
    path = memory.root / MEMORY_FILE
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise PersonalMemoryPersistenceError(f"Could not write personal memory at {path}: {scrub(str(exc))}") from exc


def _new_state(root: Path) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "created_at": now,
        "updated_at": now,
        "records": [],
        "controls": _default_controls(),
    }


def _default_controls() -> dict[str, Any]:
    return {
        "local_only": True,
        "cloud_memory_sharing": False,
        "sensitive_memory_exclusions": True,
        "allowed_scopes": ["user", "workspace", "project", "workflow"],
        "categories": {category: _default_category_control(category) for category in MEMORY_CATEGORIES},
        "transparency": {
            "inspectable": True,
            "editable": True,
            "exportable": True,
            "deletable": True,
            "category_controls": True,
        },
        "updated_at": utc_now(),
    }


def _default_category_control(category: str) -> dict[str, Any]:
    spec = MEMORY_CATEGORIES.get(category, {})
    return {
        "enabled": True,
        "retention_days": spec.get("default_retention_days"),
        "include_in_orchestration": bool(spec.get("orchestration", True)),
        "encrypted": False,
        "encrypted_storage_active": False,
    }


def _normalize_controls(state: dict[str, Any]) -> None:
    controls = state.setdefault("controls", _default_controls())
    categories = controls.setdefault("categories", {})
    for category in MEMORY_CATEGORIES:
        categories.setdefault(category, _default_category_control(category))
    controls.setdefault("local_only", True)
    controls.setdefault("cloud_memory_sharing", False)
    controls.setdefault("sensitive_memory_exclusions", True)
    controls.setdefault("allowed_scopes", ["user", "workspace", "project", "workflow"])
    controls.setdefault("transparency", _default_controls()["transparency"])


def _filter_records(
    state: dict[str, Any],
    *,
    query: str = "",
    category: str | None = None,
    scope: str | None = None,
    include_archived: bool = False,
    include_disabled: bool = False,
    orchestration_only: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    tokens = _query_tokens(query)
    clean_category = _normalize_category(category) if category else None
    clean_scope = _normalize_scope(scope) if scope else None
    records: list[tuple[int, dict[str, Any]]] = []
    controls = state.get("controls", {})
    category_controls = controls.get("categories", {})
    for record in state.get("records", []):
        if record.get("status") == "deleted":
            continue
        if record.get("status") == "archived" and not include_archived:
            continue
        if clean_category and record.get("category") != clean_category:
            continue
        if clean_scope and record.get("scope") != clean_scope:
            continue
        cat = category_controls.get(record.get("category"), {})
        if not include_disabled and not cat.get("enabled", True):
            continue
        if orchestration_only and not cat.get("include_in_orchestration", True):
            continue
        if _is_expired(record):
            continue
        score = _record_score(record, tokens)
        if tokens and score <= 0 and not record.get("pinned"):
            continue
        records.append((score, record))
    records.sort(key=lambda item: (bool(item[1].get("pinned")), item[0], str(item[1].get("updated_at") or "")), reverse=True)
    output = [item[1] for item in records]
    if limit is not None:
        output = output[: max(1, int(limit))]
    return output


def _record_score(record: dict[str, Any], tokens: set[str]) -> int:
    score = 20 if record.get("pinned") else 0
    if not tokens:
        return score + 1
    haystack = " ".join(
        [
            str(record.get("title") or ""),
            str(record.get("summary") or ""),
            str(record.get("content") or ""),
            " ".join(str(item) for item in record.get("tags", [])),
            str(record.get("category") or ""),
        ]
    ).lower()
    for token in tokens:
        if token in haystack:
            score += 5 if token in str(record.get("title", "")).lower() else 2
    return score


def _public_record(record: dict[str, Any], *, include_content: bool = True) -> dict[str, Any]:
    result = dict(record)
    if not include_content:
        result.pop("content", None)
    return result


def _category_catalog(state: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for record in state.get("records", []):
        if record.get("status") != "deleted":
            counts[record.get("category", "project_memory")] = counts.get(record.get("category", "project_memory"), 0) + 1
    controls = state.get("controls", {}).get("categories", {})
    return [
        {
            "id": category,
            "label": spec["label"],
            "record_count": counts.get(category, 0),
            **controls.get(category, _default_category_control(category)),
        }
        for category, spec in MEMORY_CATEGORIES.items()
    ]


def _observability(root: Path, state: dict[str, Any], *, latency_ms: int = 0) -> dict[str, Any]:
    active = [item for item in state.get("records", []) if item.get("status") == "active" and not _is_expired(item)]
    archived = [item for item in state.get("records", []) if item.get("status") == "archived"]
    deleted = [item for item in state.get("records", []) if item.get("status") == "deleted"]
    by_category: dict[str, int] = {}
    by_scope: dict[str, int] = {}
    usage_count = 0
    stale_count = 0
    for record in state.get("records", []):
        if record.get("status") == "deleted":
            continue
        by_category[record.get("category", "project_memory")] = by_category.get(record.get("category", "project_memory"), 0) + 1
        by_scope[record.get("scope", "project")] = by_scope.get(record.get("scope", "project"), 0) + 1
        usage_count += int((record.get("usage") or {}).get("retrieval_count") or 0)
        if _is_stale(record, state, datetime.now(timezone.utc)):
            stale_count += 1
    size_bytes = 0
    try:
        size_bytes = (ProjectMemory(root).root / MEMORY_FILE).stat().st_size
    except OSError:
        pass
    conflicts = _conflicting_memories(state)
    return {
        "records": {
            "total": len([item for item in state.get("records", []) if item.get("status") != "deleted"]),
            "active": len(active),
            "archived": len(archived),
            "deleted_placeholders": len(deleted),
            "pinned": len([item for item in active if item.get("pinned")]),
            "stale": stale_count,
            "by_category": by_category,
            "by_scope": by_scope,
        },
        "usage": {
            "total_retrievals": usage_count,
            "most_used": _most_used(state),
            "retrieval_latency_ms": latency_ms,
        },
        "storage": {
            "state_file": str(ProjectMemory(root).root / MEMORY_FILE),
            "audit_file": str(ProjectMemory(root).root / AUDIT_FILE),
            "size_bytes": size_bytes,
            "encrypted_storage_available": _encryption_available(),
        },
        "quality": {
            "conflicting_memories": conflicts[:20],
            "conflict_count": len(conflicts),
            "disabled_categories": [
                key
                for key, value in state.get("controls", {}).get("categories", {}).items()
                if not value.get("enabled", True)
            ],
        },
    }


def _privacy_summary(state: dict[str, Any]) -> dict[str, Any]:
    controls = state.get("controls", {})
    encrypted_requested = [
        category
        for category, control in controls.get("categories", {}).items()
        if control.get("encrypted")
    ]
    encrypted_active = [
        category
        for category, control in controls.get("categories", {}).items()
        if control.get("encrypted_storage_active")
    ]
    return {
        "local_only": bool(controls.get("local_only", True)),
        "cloud_memory_sharing": bool(controls.get("cloud_memory_sharing", False)),
        "sensitive_memory_exclusions": bool(controls.get("sensitive_memory_exclusions", True)),
        "per_project_isolation": True,
        "inspectable": True,
        "editable": True,
        "exportable": True,
        "deletable": True,
        "encrypted_storage_requested_categories": encrypted_requested,
        "encrypted_storage_active_categories": encrypted_active,
        "encrypted_storage_available": _encryption_available(),
        "encryption_note": "Set AEGIS_MEMORY_ENCRYPTION_KEY to activate optional encrypted payload handling." if not _encryption_available() else "Optional memory encryption key is configured.",
    }


def _memory_guidance(records: list[dict[str, Any]], state: dict[str, Any], workflow_type: str) -> list[str]:
    guidance: list[str] = []
    categories = {record.get("category") for record in records}
    if "validation_history" in categories:
        guidance.append("Prefer validation commands that previously succeeded in this workspace.")
    if "repair_history" in categories:
        guidance.append("Check prior repair notes before proposing a new repair strategy.")
    if "user_preferences" in categories or "workflow_patterns" in categories:
        guidance.append("Follow stored user workflow preferences where they do not conflict with safety gates.")
    if "architecture_notes" in categories:
        guidance.append("Respect stored architecture decisions and call out any proposed deviation.")
    disabled = [
        key
        for key, value in state.get("controls", {}).get("categories", {}).items()
        if not value.get("include_in_orchestration", True)
    ]
    if disabled:
        guidance.append(f"Memory categories excluded from orchestration: {', '.join(disabled[:6])}.")
    if workflow_type in {"repair_project", "validate_project"}:
        guidance.append("Keep repair and validation loops bounded; memory is advisory, not approval.")
    return guidance[:8]


def _timeline(state: dict[str, Any], *, include_archived: bool) -> list[dict[str, Any]]:
    entries = []
    for record in state.get("records", []):
        if record.get("status") == "deleted":
            continue
        if record.get("status") == "archived" and not include_archived:
            continue
        entries.append(
            {
                "id": record.get("id"),
                "title": record.get("title"),
                "category": record.get("category"),
                "status": record.get("status"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "pinned": record.get("pinned", False),
            }
        )
    return sorted(entries, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)


def _append_audit(
    root: Path,
    state: dict[str, Any],
    event_type: str,
    *,
    record_id: str | None = None,
    details: dict[str, Any] | None = None,
    severity: str = "info",
) -> None:
    event = {
        "event_id": f"memory-event-{uuid4().hex[:12]}",
        "event_type": event_type,
        "severity": severity,
        "workspace": str(root),
        "memory_id": record_id,
        "details": _sanitize_metadata(details or {}),
        "created_at": utc_now(),
    }
    path = ProjectMemory(root).root / AUDIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    state["last_audit_event"] = event


def _read_audit(root: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    path = ProjectMemory(root).root / AUDIT_FILE
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in reversed(lines[-max(1, int(limit or 100)) :]):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _audit_summary(root: Path) -> dict[str, Any]:
    events = _read_audit(root, limit=1000)
    by_type: dict[str, int] = {}
    for event in events:
        key = str(event.get("event_type") or "unknown")
        by_type[key] = by_type.get(key, 0) + 1
    return {"event_count": len(events), "by_type": by_type}


def _records_from_import_payload(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        records = payload.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
        if payload.get("title") or payload.get("content"):
            return [payload]
    return []


def _normalize_import_record(state: dict[str, Any], item: dict[str, Any], *, source: str) -> dict[str, Any]:
    category = _normalize_category(item.get("category") or "project_memory")
    _require_category_enabled(state, category)
    content, redactions = _sanitize_content(str(item.get("content") or item.get("summary") or ""))
    title, title_redactions = _sanitize_content(str(item.get("title") or "Imported memory"), max_chars=240)
    redactions += title_redactions
    now = utc_now()
    return {
        "id": _safe_memory_id(str(item.get("id") or f"mem-{uuid4().hex[:12]}")),
        "version": 1,
        "category": category,
        "scope": _normalize_scope(item.get("scope") or "project"),
        "title": title,
        "content": content,
        "summary": _summary(content),
        "tags": _clean_list(item.get("tags") if isinstance(item.get("tags"), list) else []),
        "related_files": _clean_paths(item.get("related_files") if isinstance(item.get("related_files"), list) else []),
        "source": source,
        "confidence": _confidence(item.get("confidence", 0.7)),
        "status": "active",
        "pinned": bool(item.get("pinned", False)),
        "expires_at": item.get("expires_at") if isinstance(item.get("expires_at"), str) else None,
        "created_at": item.get("created_at") if isinstance(item.get("created_at"), str) else now,
        "updated_at": now,
        "archived_at": None,
        "usage": {"retrieval_count": 0, "last_retrieved_at": None, "used_by_workflows": []},
        "privacy": _record_privacy(state, category, item.get("privacy") if isinstance(item.get("privacy"), dict) else {}, bool(redactions)),
        "metadata": _sanitize_metadata(item.get("metadata") if isinstance(item.get("metadata"), dict) else {}),
        "redaction_count": redactions,
        "fingerprint": _fingerprint(category, title, content),
    }


def _record_privacy(state: dict[str, Any], category: str, privacy: dict[str, Any], sensitive: bool) -> dict[str, Any]:
    controls = state.get("controls", {})
    cat = controls.get("categories", {}).get(category, {})
    encrypted_requested = bool(privacy.get("encrypted") or cat.get("encrypted"))
    return {
        "local_only": bool(privacy.get("local_only", controls.get("local_only", True))),
        "sensitive": bool(sensitive or privacy.get("sensitive", False)),
        "excluded_from_cloud": True if sensitive else bool(privacy.get("excluded_from_cloud", True)),
        "scope_restriction": privacy.get("scope_restriction") or category,
        "encrypted_requested": encrypted_requested,
        "encrypted_storage_active": bool(encrypted_requested and _encryption_available()),
    }


def _require_category_enabled(state: dict[str, Any], category: str) -> None:
    control = state.get("controls", {}).get("categories", {}).get(category, {})
    if not control.get("enabled", True):
        raise PersonalMemoryPersistenceError(f"memory category is disabled: {category}")


def _get_record(state: dict[str, Any], memory_id: str) -> dict[str, Any]:
    clean_id = _safe_memory_id(memory_id)
    for record in state.get("records", []):
        if record.get("id") == clean_id and record.get("status") != "deleted":
            return record
    raise PersonalMemoryPersistenceError(f"memory record not found: {scrub(clean_id)}")


def _normalize_category(category: Any) -> str:
    text = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text if text in MEMORY_CATEGORIES else "project_memory"


def _normalize_scope(scope: Any) -> str:
    text = str(scope or "").strip().lower().replace("-", "_")
    if text in {"user", "workspace", "project", "workflow"}:
        return text
    return "project"


def _normalize_expires_at(value: str | None, state: dict[str, Any], category: str) -> str | None:
    if value:
        parsed = _parse_time(value)
        if parsed:
            return parsed.isoformat()
    retention = state.get("controls", {}).get("categories", {}).get(category, {}).get("retention_days")
    if retention:
        return (datetime.now(timezone.utc) + timedelta(days=max(1, int(retention)))).isoformat()
    return None


def _sanitize_content(value: Any, *, max_chars: int = MAX_CONTENT_CHARS) -> tuple[str, int]:
    text = scrub(str(value or ""))[:max_chars]
    redactions = 1 if "[redacted" in text.lower() else 0
    for pattern in SECRET_PATTERNS:
        text, count = pattern.subn("[redacted-secret]", text)
        redactions += count
    return text, redactions


def _sanitize_metadata(data: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        key_text = str(key)
        if any(token in key_text.lower() for token in ["token", "secret", "password", "api_key", "apikey", "credential"]):
            sanitized[key_text] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key_text] = _sanitize_metadata(value)
        elif isinstance(value, list):
            sanitized[key_text] = [_sanitize_metadata(item) if isinstance(item, dict) else scrub(str(item)) for item in value[:100]]
        elif isinstance(value, str):
            sanitized[key_text] = _sanitize_content(value, max_chars=2000)[0]
        else:
            sanitized[key_text] = value
    return sanitized


def _clean_list(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = scrub(str(value)).strip()[:160]
        if text and text not in result:
            result.append(text)
    return result[:50]


def _clean_paths(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value).replace("\\", "/").strip().lstrip("/")
        if not text or ".." in Path(text).parts:
            continue
        if text not in result:
            result.append(text[:240])
    return result[:100]


def _safe_memory_id(value: str) -> str:
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text).strip("-._")
    if not clean:
        return f"mem-{uuid4().hex[:12]}"
    return clean[:96]


def _confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 0.8
    return round(max(0.0, min(1.0, parsed)), 3)


def _summary(text: str) -> str:
    collapsed = " ".join(str(text or "").split())
    return collapsed[:360]


def _fingerprint(category: str, title: str, content: str) -> str:
    digest = hashlib.sha256(f"{category}\n{title.strip().lower()}\n{content.strip().lower()}".encode("utf-8")).hexdigest()
    return digest[:24]


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        fingerprint = str(record.get("fingerprint") or record.get("id") or "")
        if fingerprint and fingerprint in seen and not record.get("pinned"):
            continue
        seen.add(fingerprint)
        result.append(record)
    return result


def _query_tokens(query: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z0-9_]{3,}", str(query or "").lower()) if token not in {"the", "and", "with", "from"}}


def _is_expired(record: dict[str, Any]) -> bool:
    expires = _parse_time(record.get("expires_at"))
    return bool(expires and expires <= datetime.now(timezone.utc) and not record.get("pinned"))


def _is_stale(record: dict[str, Any], state: dict[str, Any], now: datetime) -> bool:
    if record.get("pinned") or record.get("status") != "active":
        return False
    if _is_expired(record):
        return True
    retention = state.get("controls", {}).get("categories", {}).get(record.get("category"), {}).get("retention_days")
    if not retention:
        return False
    updated = _parse_time(record.get("updated_at") or record.get("created_at"))
    return bool(updated and now - updated > timedelta(days=max(1, int(retention))))


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _most_used(state: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(
        [item for item in state.get("records", []) if item.get("status") == "active"],
        key=lambda item: int((item.get("usage") or {}).get("retrieval_count") or 0),
        reverse=True,
    )
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "retrieval_count": int((item.get("usage") or {}).get("retrieval_count") or 0),
        }
        for item in ranked[:10]
        if int((item.get("usage") or {}).get("retrieval_count") or 0) > 0
    ]


def _conflicting_memories(state: dict[str, Any]) -> list[dict[str, Any]]:
    by_title: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in state.get("records", []):
        if record.get("status") != "active":
            continue
        key = (str(record.get("category") or ""), str(record.get("title") or "").strip().lower())
        if key[1]:
            by_title.setdefault(key, []).append(record)
    conflicts: list[dict[str, Any]] = []
    for (category, title), records in by_title.items():
        fingerprints = {item.get("fingerprint") for item in records}
        if len(records) > 1 and len(fingerprints) > 1:
            conflicts.append(
                {
                    "category": category,
                    "title": title,
                    "record_ids": [item["id"] for item in records],
                    "reason": "Multiple active memories share a title but differ in content.",
                }
            )
    return conflicts


def _encryption_available() -> bool:
    return bool(os.getenv("AEGIS_MEMORY_ENCRYPTION_KEY"))


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise PersonalMemoryPersistenceError(f"workspace does not exist or is not a directory: {scrub(str(root))}")
    return root
