from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .quality_gates import evaluate_quality_gates
from .safety import is_ignored_path, is_safe_to_edit, is_secret_like
from .tasks import TaskStorePersistenceError, create_task
from .validation import detect_validation_commands, is_safe_validation_command, run_validation


PROPOSALS_FILE = "editing-proposals.json"
JOBS_FILE = "operation-jobs.json"
ACTIVITY_FILE = "editing-activity.json"
VALIDATION_RESULTS_FILE = "validation-results.json"
EDITING_LOG_FILE = "editing-log.md"
MAX_STORED_ITEMS = 200
MAX_ACTIVITY_ITEMS = 500
MAX_WRITE_BYTES = 1_000_000
MAX_PREVIEW_BYTES = 512_000
MAX_PATCH_CHARS = 16_000


class EditingPersistenceError(RuntimeError):
    """Raised when Core editing runtime state cannot be persisted."""


class UnsafePathError(ValueError):
    """Raised when a requested edit path is not safe for the workspace."""


class CheckpointNotFoundError(FileNotFoundError):
    """Raised when a requested Core checkpoint cannot be found."""


def propose_changes(
    workspace: str | Path,
    changes: list[dict[str, Any]],
    *,
    summary: str = "",
    source_task_id: str | None = None,
    source_client: str = "unknown",
    risk: str = "unknown",
    repair_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    normalized = [_normalize_change(root, item) for item in changes]
    if not normalized:
        raise ValueError("at least one proposed change is required")

    memory = _memory(root)
    job = _start_job(memory, root, "changes.propose", source_client=source_client, task_id=source_task_id)
    task_id, task_warning = _task_for_operation(
        root,
        provided_task_id=source_task_id,
        title=summary or "Review proposed Core file changes",
        kind="changes.propose",
        source_client=source_client,
        metadata={"job_id": job["id"], "risk": risk},
    )
    previews = [_preview_change(root, change) for change in normalized]
    proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
    now = utc_now()
    proposal = {
        "id": proposal_id,
        "project_id": _project_id(root),
        "workspace": str(root),
        "summary": summary.strip() or _proposal_summary(normalized),
        "risk": risk or "unknown",
        "source_task_id": task_id,
        "source_client": source_client or "unknown",
        "status": "proposed",
        "created_at": now,
        "updated_at": now,
        "files": normalized,
        "preview": previews,
        "repair_attempt": _safe_metadata(repair_attempt),
        "job_id": job["id"],
    }
    _store_proposal(memory, proposal)
    activity = _append_activity(
        memory,
        root,
        "changes.proposed",
        "Proposed file changes",
        {
            "proposal_id": proposal_id,
            "job_id": job["id"],
            "task_id": task_id,
            "paths": [change["path"] for change in normalized],
        },
    )
    _complete_job(memory, job["id"], ok=True, result={"proposal_id": proposal_id, "activity_id": activity["id"]})
    _append_log(memory, f"Proposed {len(normalized)} change(s)", proposal["summary"])
    return {
        "ok": True,
        "workspace": str(root),
        "project_id": proposal["project_id"],
        "proposal": proposal,
        "preview": previews,
        "job_id": job["id"],
        "task_id": task_id,
        "activity_id": activity["id"],
        "warnings": [task_warning] if task_warning else [],
    }


def apply_changes(
    workspace: str | Path,
    *,
    proposal_id: str | None = None,
    changes: list[dict[str, Any]] | None = None,
    change_ids: list[str] | None = None,
    paths: list[str] | None = None,
    apply_all: bool = True,
    dry_run: bool = False,
    summary: str = "",
    task_id: str | None = None,
    source_client: str = "unknown",
    repair_attempt: dict[str, Any] | None = None,
    approval: bool = False,
    validation_required: bool = False,
    quality_gate_required: bool = True,
    max_files_changed: int = 25,
    allow_quality_override: bool = False,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    job = _start_job(memory, root, "changes.apply", source_client=source_client, task_id=task_id)
    operation_task_id, task_warning = _task_for_operation(
        root,
        provided_task_id=task_id,
        title=summary or "Apply Core-owned file changes",
        kind="changes.apply",
        source_client=source_client,
        metadata={"job_id": job["id"], "proposal_id": proposal_id},
    )

    proposal = _load_proposal(memory, proposal_id) if proposal_id else None
    if proposal is not None:
        candidate_changes = [dict(item) for item in proposal.get("files", []) if isinstance(item, dict)]
    else:
        candidate_changes = [_normalize_change(root, item) for item in changes or []]
    selected = _select_changes(root, candidate_changes, change_ids=change_ids or [], paths=paths or [], apply_all=apply_all)
    if not selected:
        raise ValueError("no changes matched the apply selection")

    previews = [_preview_change(root, change) for change in selected]
    quality_gate = evaluate_quality_gates(
        root,
        changes=selected,
        workflow_id=None,
        approval=approval,
        checkpoint_id=None,
        max_files_changed=max_files_changed,
        validation_required=validation_required,
        dry_run=True,
        metadata={"operation": "changes.apply.preview", "proposal_id": proposal_id, "source_client": source_client},
        persist=quality_gate_required,
    )
    if dry_run:
        activity = _append_activity(
            memory,
            root,
            "changes.apply.dry_run",
            "Previewed selected file changes",
            {"proposal_id": proposal_id, "job_id": job["id"], "task_id": operation_task_id, "paths": [item["path"] for item in selected]},
        )
        result = {
            "ok": True,
            "workspace": str(root),
            "project_id": _project_id(root),
            "proposal_id": proposal_id,
            "applied": [],
            "warnings": [task_warning] if task_warning else [],
            "checkpoint_id": None,
            "dry_run": True,
            "preview": previews,
            "job_id": job["id"],
            "task_id": operation_task_id,
            "activity_id": activity["id"],
            "repair_attempt": _safe_metadata(repair_attempt),
            "blocked": False,
            "quality_gate": quality_gate,
        }
        _complete_job(memory, job["id"], ok=True, result=result)
        return result

    checkpoint = create_checkpoint(
        root,
        changes=selected,
        summary=summary or f"Before applying {len(selected)} Core change(s)",
        source_task_id=operation_task_id,
        source_client=source_client,
        job_id=job["id"],
    )
    quality_gate = evaluate_quality_gates(
        root,
        changes=selected,
        workflow_id=None,
        approval=approval,
        checkpoint_id=checkpoint["id"],
        max_files_changed=max_files_changed,
        validation_required=validation_required,
        dry_run=False,
        metadata={"operation": "changes.apply", "proposal_id": proposal_id, "source_client": source_client},
        persist=quality_gate_required,
    )
    if quality_gate_required and not quality_gate.get("apply_allowed", True) and not allow_quality_override:
        warnings = [task_warning] if task_warning else []
        warnings.extend(str(item) for item in quality_gate.get("warnings", []) if str(item).strip())
        activity = _append_activity(
            memory,
            root,
            "changes.apply.blocked",
            "Blocked file changes before apply",
            {
                "proposal_id": proposal_id,
                "checkpoint_id": checkpoint["id"],
                "job_id": job["id"],
                "task_id": operation_task_id,
                "paths": [item["path"] for item in selected],
                "quality_gate_id": quality_gate.get("id"),
                "blockers": quality_gate.get("blockers", []),
            },
        )
        result = {
            "ok": False,
            "workspace": str(root),
            "project_id": _project_id(root),
            "proposal_id": proposal_id,
            "applied": [],
            "warnings": warnings,
            "blocked": True,
            "quality_gate": quality_gate,
            "checkpoint_id": checkpoint["id"],
            "checkpoint": checkpoint,
            "dry_run": False,
            "preview": previews,
            "job_id": job["id"],
            "task_id": operation_task_id,
            "activity_id": activity["id"],
            "repair_attempt": _safe_metadata(repair_attempt),
        }
        _complete_job(memory, job["id"], ok=False, result=result, error=quality_gate.get("summary", "Quality gates blocked apply."))
        _append_log(memory, "Blocked apply by quality gates", f"{quality_gate.get('id')}: checkpoint={checkpoint['id']}")
        return result

    applied: list[str] = []
    warnings: list[str] = []
    for change in selected:
        outcome = _apply_one_change(root, change)
        if outcome.get("applied"):
            applied.append(str(outcome["applied"]))
        if outcome.get("warning"):
            warnings.append(str(outcome["warning"]))

    if task_warning:
        warnings.append(task_warning)
    if proposal is not None:
        _mark_proposal_applied(memory, proposal["id"], selected, applied=applied, warnings=warnings)
    activity = _append_activity(
        memory,
        root,
        "changes.applied",
        "Applied selected file changes",
        {
            "proposal_id": proposal_id,
            "checkpoint_id": checkpoint["id"],
            "job_id": job["id"],
            "task_id": operation_task_id,
            "applied": applied,
            "warnings": warnings,
            "paths": [item["path"] for item in selected],
        },
    )
    result = {
        "ok": bool(applied) and not any("checkpoint" in warning.lower() for warning in warnings),
        "workspace": str(root),
        "project_id": _project_id(root),
        "proposal_id": proposal_id,
        "applied": applied,
        "warnings": warnings,
        "blocked": False,
        "quality_gate": quality_gate,
        "checkpoint_id": checkpoint["id"],
        "checkpoint": checkpoint,
        "dry_run": False,
        "preview": previews,
        "job_id": job["id"],
        "task_id": operation_task_id,
        "activity_id": activity["id"],
        "repair_attempt": _safe_metadata(repair_attempt),
    }
    _complete_job(memory, job["id"], ok=result["ok"], result=result)
    _append_log(memory, f"Applied {len(applied)} change(s)", f"checkpoint={checkpoint['id']}")
    return result


def create_checkpoint(
    workspace: str | Path,
    *,
    changes: list[dict[str, Any]] | None = None,
    paths: list[str] | None = None,
    summary: str = "",
    source_task_id: str | None = None,
    source_client: str = "aegis-core",
    job_id: str | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    path_entries = _checkpoint_paths(root, changes=changes or [], paths=paths or [])
    if not path_entries:
        raise ValueError("at least one checkpoint path or change is required")

    checkpoint_id = f"checkpoint-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    checkpoint_root = _checkpoint_root(root, checkpoint_id)
    files_root = checkpoint_root / "files"
    manifest_files: list[dict[str, Any]] = []

    try:
        files_root.mkdir(parents=True, exist_ok=False)
        for relative_path in path_entries:
            target = _safe_target(root, relative_path)
            entry: dict[str, Any] = {"path": relative_path, "state": "missing"}
            if target.exists():
                if not target.is_file():
                    raise ValueError(f"{relative_path}: refusing to checkpoint a non-file path")
                backup = files_root / relative_path
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                entry.update(
                    {
                        "state": "present",
                        "backup_path": str(backup.relative_to(checkpoint_root).as_posix()),
                        "size": target.stat().st_size,
                    }
                )
            manifest_files.append(entry)
        manifest = {
            "id": checkpoint_id,
            "project_id": _project_id(root),
            "workspace": str(root),
            "created_at": utc_now(),
            "summary": summary.strip() or f"Checkpoint for {len(path_entries)} file(s)",
            "source_task_id": source_task_id,
            "source_client": source_client or "aegis-core",
            "job_id": job_id,
            "files": manifest_files,
        }
        _write_json_file(checkpoint_root / "manifest.json", manifest)
    except Exception:
        if checkpoint_root.exists():
            shutil.rmtree(checkpoint_root, ignore_errors=True)
        raise

    _append_activity(
        memory,
        root,
        "checkpoint.created",
        "Created Core checkpoint",
        {"checkpoint_id": checkpoint_id, "job_id": job_id, "task_id": source_task_id, "paths": path_entries},
    )
    _append_log(memory, "Created checkpoint", f"{checkpoint_id}: {', '.join(path_entries[:8])}")
    return _checkpoint_summary_from_manifest(checkpoint_root, manifest)


def list_checkpoints(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    checkpoints_root = root / ".aegis" / "checkpoints"
    checkpoints: list[dict[str, Any]] = []
    if checkpoints_root.is_dir():
        max_items = max(1, min(200, int(limit)))
        for checkpoint_root in sorted((item for item in checkpoints_root.iterdir() if item.is_dir()), key=lambda item: item.name, reverse=True):
            manifest = _read_checkpoint_manifest(checkpoint_root)
            if manifest is None:
                continue
            checkpoints.append(_checkpoint_summary_from_manifest(checkpoint_root, manifest))
            if len(checkpoints) >= max_items:
                break
    return {"workspace": str(root), "project_id": _project_id(root), "checkpoints": checkpoints}


def restore_checkpoint(
    workspace: str | Path,
    checkpoint_id: str,
    *,
    dry_run: bool = False,
    source_client: str = "unknown",
    task_id: str | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    checkpoint_root = _checkpoint_root(root, checkpoint_id)
    manifest = _read_checkpoint_manifest(checkpoint_root)
    if manifest is None:
        raise CheckpointNotFoundError(checkpoint_id)

    job = _start_job(memory, root, "checkpoints.restore", source_client=source_client, task_id=task_id)
    files = _manifest_files(manifest)
    prepared = [_restore_prepare(root, checkpoint_root, entry) for entry in files]
    if dry_run:
        restored_preview = [f"{action}: {relative_path}" for action, relative_path, _target, _backup in prepared]
        activity = _append_activity(
            memory,
            root,
            "checkpoint.restore.dry_run",
            "Previewed checkpoint restore",
            {"checkpoint_id": checkpoint_id, "job_id": job["id"], "task_id": task_id, "restored": restored_preview},
        )
        result = {
            "ok": True,
            "workspace": str(root),
            "project_id": _project_id(root),
            "checkpoint_id": checkpoint_id,
            "restored": [],
            "dry_run": True,
            "pre_restore_checkpoint_id": None,
            "job_id": job["id"],
            "task_id": task_id,
            "activity_id": activity["id"],
            "preview": restored_preview,
            "warnings": [],
        }
        _complete_job(memory, job["id"], ok=True, result=result)
        return result

    current_paths = [relative_path for _action, relative_path, _target, _backup in prepared]
    pre_restore = create_checkpoint(
        root,
        paths=current_paths,
        summary=f"Before restoring {checkpoint_id}",
        source_task_id=task_id,
        source_client=source_client,
        job_id=job["id"],
    )
    restored: list[str] = []
    for action, relative_path, target, backup in prepared:
        if action == "restore":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored.append(f"restore: {relative_path}")
        elif action == "remove" and target.exists():
            if not target.is_file():
                raise ValueError(f"{relative_path}: refusing to remove a non-file path during checkpoint restore")
            target.unlink()
            restored.append(f"remove: {relative_path}")

    activity = _append_activity(
        memory,
        root,
        "checkpoint.restored",
        "Restored Core checkpoint",
        {
            "checkpoint_id": checkpoint_id,
            "pre_restore_checkpoint_id": pre_restore["id"],
            "job_id": job["id"],
            "task_id": task_id,
            "restored": restored,
        },
    )
    result = {
        "ok": True,
        "workspace": str(root),
        "project_id": _project_id(root),
        "checkpoint_id": checkpoint_id,
        "restored": restored,
        "dry_run": False,
        "pre_restore_checkpoint_id": pre_restore["id"],
        "job_id": job["id"],
        "task_id": task_id,
        "activity_id": activity["id"],
        "warnings": [],
    }
    _complete_job(memory, job["id"], ok=True, result=result)
    _append_log(memory, "Restored checkpoint", f"{checkpoint_id}: {len(restored)} operation(s)")
    return result


def run_validation_operation(
    workspace: str | Path,
    *,
    command: list[str] | None = None,
    timeout_seconds: int = 120,
    dry_run: bool = False,
    source_client: str = "unknown",
    task_id: str | None = None,
    repair_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    job = _start_job(memory, root, "validation.run", source_client=source_client, task_id=task_id)
    operation_task_id, task_warning = _task_for_operation(
        root,
        provided_task_id=task_id,
        title="Run Core validation",
        kind="validation.run",
        source_client=source_client,
        metadata={"job_id": job["id"], "command": command or []},
    )
    detected = [item.__dict__ for item in detect_validation_commands(root)]
    selected = command or (detected[0]["command"] if detected else None)

    if dry_run:
        validation = {
            "ok": selected is not None and (is_safe_validation_command(selected) if selected else False),
            "workspace": str(root),
            "command": selected,
            "commands": detected,
            "dry_run": True,
            "blocked": bool(selected and not is_safe_validation_command(selected)),
        }
    else:
        validation = run_validation(root, command=command, timeout=max(1, min(900, int(timeout_seconds))))
        validation["workspace"] = str(root)
        validation["commands"] = detected

    record = {
        "id": f"validation-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "created_at": utc_now(),
        "job_id": job["id"],
        "task_id": operation_task_id,
        "source_client": source_client or "unknown",
        "dry_run": dry_run,
        "validation": validation,
        "repair_attempt": _safe_metadata(repair_attempt),
        "warnings": [task_warning] if task_warning else [],
    }
    _append_validation_result(memory, record)
    activity = _append_activity(
        memory,
        root,
        "validation.run",
        "Ran Core validation" if not dry_run else "Previewed Core validation",
        {
            "validation_id": record["id"],
            "job_id": job["id"],
            "task_id": operation_task_id,
            "ok": validation.get("ok"),
            "command": validation.get("command"),
            "dry_run": dry_run,
        },
    )
    record["activity_id"] = activity["id"]
    _complete_job(memory, job["id"], ok=bool(validation.get("ok")), result=record)
    _append_log(memory, "Validation recorded", f"{record['id']}: ok={validation.get('ok')}")
    return record


def get_operation_job(workspace: str | Path, job_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    job = _job_by_id(memory, job_id)
    if job is None:
        raise KeyError(job_id)
    return {"workspace": str(root), "project_id": _project_id(root), "job": job}


def project_activity(workspace: str | Path, project_id: str, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    resolved_project_id = _project_id(root)
    if project_id not in {resolved_project_id, "current", "default"}:
        raise KeyError(project_id)
    memory = _memory(root)
    activity = _read_json(memory, ACTIVITY_FILE, [])
    if not isinstance(activity, list):
        activity = []
    max_items = max(1, min(200, int(limit)))
    items = [item for item in activity if isinstance(item, dict) and item.get("project_id") == resolved_project_id]
    items = sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:max_items]
    return {"workspace": str(root), "project_id": resolved_project_id, "activity": items}


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {root}")
    return root


def _memory(root: Path) -> ProjectMemory:
    memory = ProjectMemory(root)
    try:
        memory.root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EditingPersistenceError(f"Could not create Core editing state directory at {memory.root}: {exc}") from exc
    return memory


def _normalize_change(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("each change must be an object")
    action = str(item.get("action") or "update").strip().lower()
    if action not in {"create", "update", "append", "delete"}:
        raise ValueError(f"unsupported change action: {action}")
    relative_path = _normalize_relative_path(str(item.get("path") or ""))
    _safe_target(root, relative_path)
    content = item.get("content")
    if content is not None:
        content = str(content)
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ValueError(f"{relative_path}: content exceeds the Core write limit")
    if action in {"create", "update", "append"} and content is None:
        raise ValueError(f"{relative_path}: {action} requires content")
    return {
        "id": str(item.get("id") or f"change-{uuid.uuid4().hex[:12]}"),
        "action": action,
        "path": relative_path,
        "content": content,
        "summary": str(item.get("summary") or "").strip(),
        "selected": bool(item.get("selected", False)),
    }


def _normalize_relative_path(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    if not raw:
        raise UnsafePathError("path is empty")
    candidate = Path(raw)
    if candidate.is_absolute() or raw.startswith("/") or ":" in PurePosixPath(raw).parts[0]:
        raise UnsafePathError("path must be relative to the workspace")
    path = PurePosixPath(raw)
    if str(path) in {".", ".."}:
        raise UnsafePathError("path must point to a file inside the workspace")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafePathError("path must not contain dot segments")
    if any(part.startswith(".") for part in path.parts[:-1]):
        raise UnsafePathError("path points into a hidden directory")
    return path.as_posix()


def _safe_target(root: Path, relative_path: str) -> Path:
    relative_path = _normalize_relative_path(relative_path)
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError("file change points outside the workspace") from exc
    if target == root:
        raise UnsafePathError("path must point to a file inside the workspace")
    if is_ignored_path(target, root):
        raise UnsafePathError("path points into an ignored generated or dependency folder")
    if is_secret_like(target):
        raise UnsafePathError("path points to a secret-like file")
    if not is_safe_to_edit(target, root):
        raise UnsafePathError("path is not safe to edit")
    return target


def _preview_change(root: Path, change: dict[str, Any]) -> dict[str, Any]:
    relative_path = change["path"]
    target = _safe_target(root, relative_path)
    before_exists = target.exists()
    before_text = ""
    before_bytes = 0
    warnings: list[str] = []
    can_diff = True
    if before_exists:
        if not target.is_file():
            warnings.append("target exists but is not a file")
            can_diff = False
        else:
            before_bytes = target.stat().st_size
            if before_bytes <= MAX_PREVIEW_BYTES:
                before_text = target.read_text(encoding="utf-8", errors="replace")
            else:
                warnings.append("existing file is too large for full patch preview")
                can_diff = False
    after_text = _after_text(change, before_text, before_exists=before_exists)
    after_bytes = len(after_text.encode("utf-8")) if change["action"] != "delete" else 0
    patch = ""
    patch_truncated = False
    if can_diff:
        diff = "".join(
            difflib.unified_diff(
                before_text.splitlines(keepends=True),
                after_text.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
        if len(diff) > MAX_PATCH_CHARS:
            patch = diff[:MAX_PATCH_CHARS] + "\n... patch truncated ...\n"
            patch_truncated = True
        else:
            patch = diff
    return {
        "change_id": change["id"],
        "path": relative_path,
        "action": change["action"],
        "summary": change.get("summary", ""),
        "exists": before_exists,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "delta_bytes": after_bytes - before_bytes,
        "patch": patch,
        "patch_truncated": patch_truncated,
        "warnings": warnings,
    }


def _after_text(change: dict[str, Any], before_text: str, *, before_exists: bool) -> str:
    action = change["action"]
    content = change.get("content") or ""
    if action == "delete":
        return ""
    if action == "append" and before_exists:
        return before_text + content
    return content


def _apply_one_change(root: Path, change: dict[str, Any]) -> dict[str, str]:
    relative_path = change["path"]
    target = _safe_target(root, relative_path)
    action = change["action"]
    if target.exists() and not target.is_file():
        return {"warning": f"{relative_path}: target exists but is not a file"}
    if action == "create" and target.exists():
        return {"warning": f"{relative_path}: skipped create because the file already exists"}
    if action == "update" and not target.exists():
        return {"warning": f"{relative_path}: skipped update because the file does not exist"}
    if action == "append" and not target.exists():
        return {"warning": f"{relative_path}: skipped append because the file does not exist"}
    if action == "delete":
        if not target.exists():
            return {"warning": f"{relative_path}: file does not exist"}
        target.unlink()
        return {"applied": f"delete: {relative_path}"}
    content = str(change.get("content") or "")
    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        return {"warning": f"{relative_path}: skipped because it exceeds the Core write limit"}
    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "append":
        with target.open("a", encoding="utf-8", newline="") as handle:
            handle.write(content)
    else:
        target.write_text(content, encoding="utf-8")
    return {"applied": f"{action}: {relative_path}"}


def _checkpoint_paths(root: Path, *, changes: list[dict[str, Any]], paths: list[str]) -> list[str]:
    out: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("each checkpoint change must be an object")
        relative_path = _normalize_relative_path(str(change.get("path") or ""))
        _safe_target(root, relative_path)
        if relative_path not in out:
            out.append(relative_path)
    for path in paths:
        relative_path = _normalize_relative_path(str(path))
        _safe_target(root, relative_path)
        if relative_path not in out:
            out.append(relative_path)
    return out


def _checkpoint_root(root: Path, checkpoint_id: str) -> Path:
    raw = str(checkpoint_id).strip()
    if not raw:
        raise ValueError("checkpoint id is empty")
    candidate = Path(raw)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.parts[0] in {".", ".."}:
        raise ValueError("checkpoint id must be a checkpoint folder name")
    checkpoints_root = (root / ".aegis" / "checkpoints").resolve()
    checkpoint_root = (checkpoints_root / raw).resolve()
    try:
        checkpoint_root.relative_to(checkpoints_root)
    except ValueError as exc:
        raise ValueError("checkpoint points outside the workspace checkpoint folder") from exc
    return checkpoint_root


def _read_checkpoint_manifest(checkpoint_root: Path) -> dict[str, Any] | None:
    manifest_path = checkpoint_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _manifest_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    files = manifest.get("files")
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def _checkpoint_summary_from_manifest(checkpoint_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    files = _manifest_files(manifest)
    present = [item for item in files if item.get("state") == "present"]
    missing = [item for item in files if item.get("state") == "missing"]
    return {
        "id": str(manifest.get("id") or checkpoint_root.name),
        "project_id": str(manifest.get("project_id") or ""),
        "workspace": str(manifest.get("workspace") or ""),
        "created_at": str(manifest.get("created_at") or ""),
        "summary": str(manifest.get("summary") or ""),
        "file_count": len(files),
        "present_count": len(present),
        "missing_count": len(missing),
        "files": [{"path": str(item.get("path") or ""), "state": str(item.get("state") or "missing")} for item in files],
        "checkpoint_path": str(checkpoint_root),
        "job_id": manifest.get("job_id"),
        "source_task_id": manifest.get("source_task_id"),
    }


def _restore_prepare(root: Path, checkpoint_root: Path, entry: dict[str, Any]) -> tuple[str, str, Path, Path]:
    relative_path = _normalize_relative_path(str(entry.get("path") or ""))
    target = _safe_target(root, relative_path)
    files_root = (checkpoint_root / "files").resolve()
    backup = (files_root / relative_path).resolve()
    try:
        backup.relative_to(files_root)
    except ValueError as exc:
        raise ValueError("checkpoint backup path points outside the checkpoint files folder") from exc
    state = str(entry.get("state") or "missing")
    if state == "present":
        if not backup.is_file():
            raise ValueError(f"{relative_path}: checkpoint backup file is missing")
        return ("restore", relative_path, target, backup)
    if state == "missing":
        return ("remove", relative_path, target, backup)
    raise ValueError(f"{relative_path}: unsupported checkpoint file state")


def _select_changes(
    root: Path,
    changes: list[dict[str, Any]],
    *,
    change_ids: list[str],
    paths: list[str],
    apply_all: bool,
) -> list[dict[str, Any]]:
    normalized = [_normalize_change(root, item) for item in changes]
    ids = {str(item).strip() for item in change_ids if str(item).strip()}
    normalized_paths = {_normalize_relative_path(str(path)) for path in paths if str(path).strip()}
    if ids:
        return [item for item in normalized if item["id"] in ids]
    if normalized_paths:
        return [item for item in normalized if item["path"] in normalized_paths]
    if apply_all:
        return normalized
    return [item for item in normalized if item.get("selected")]


def _store_proposal(memory: ProjectMemory, proposal: dict[str, Any]) -> None:
    proposals = _read_json(memory, PROPOSALS_FILE, [])
    if not isinstance(proposals, list):
        proposals = []
    proposals = [item for item in proposals if isinstance(item, dict) and item.get("id") != proposal.get("id")]
    proposals.append(proposal)
    proposals = sorted(proposals, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:MAX_STORED_ITEMS]
    _write_json(memory, PROPOSALS_FILE, proposals)


def _load_proposal(memory: ProjectMemory, proposal_id: str | None) -> dict[str, Any] | None:
    if not proposal_id:
        return None
    proposals = _read_json(memory, PROPOSALS_FILE, [])
    if isinstance(proposals, list):
        for proposal in proposals:
            if isinstance(proposal, dict) and proposal.get("id") == proposal_id:
                return proposal
    raise KeyError(proposal_id)


def _mark_proposal_applied(memory: ProjectMemory, proposal_id: str, selected: list[dict[str, Any]], *, applied: list[str], warnings: list[str]) -> None:
    proposals = _read_json(memory, PROPOSALS_FILE, [])
    if not isinstance(proposals, list):
        return
    selected_ids = {item["id"] for item in selected}
    for proposal in proposals:
        if not isinstance(proposal, dict) or proposal.get("id") != proposal_id:
            continue
        for file_entry in proposal.get("files", []):
            if isinstance(file_entry, dict) and file_entry.get("id") in selected_ids:
                file_entry["status"] = "applied"
        proposal["status"] = "applied" if len(selected_ids) == len(proposal.get("files", [])) else "partially_applied"
        proposal["updated_at"] = utc_now()
        proposal["last_apply"] = {"applied": applied, "warnings": warnings}
        break
    _write_json(memory, PROPOSALS_FILE, proposals)


def _start_job(memory: ProjectMemory, root: Path, kind: str, *, source_client: str, task_id: str | None) -> dict[str, Any]:
    job = {
        "id": f"job-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "kind": kind,
        "status": "running",
        "ok": None,
        "source_client": source_client or "unknown",
        "task_id": task_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "started_at": utc_now(),
        "finished_at": None,
        "result": {},
        "error": None,
    }
    _upsert_job(memory, job)
    return job


def _complete_job(memory: ProjectMemory, job_id: str, *, ok: bool, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    job = _job_by_id(memory, job_id)
    if job is None:
        return
    job["status"] = "completed" if ok else "failed"
    job["ok"] = bool(ok)
    job["updated_at"] = utc_now()
    job["finished_at"] = utc_now()
    job["result"] = result or {}
    job["error"] = scrub(error) if error else None
    _upsert_job(memory, job)


def _upsert_job(memory: ProjectMemory, job: dict[str, Any]) -> None:
    jobs = _read_json(memory, JOBS_FILE, [])
    if not isinstance(jobs, list):
        jobs = []
    jobs = [item for item in jobs if isinstance(item, dict) and item.get("id") != job.get("id")]
    jobs.append(job)
    jobs = sorted(jobs, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[:MAX_STORED_ITEMS]
    _write_json(memory, JOBS_FILE, jobs)


def _job_by_id(memory: ProjectMemory, job_id: str) -> dict[str, Any] | None:
    jobs = _read_json(memory, JOBS_FILE, [])
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and job.get("id") == job_id:
                return job
    return None


def _append_validation_result(memory: ProjectMemory, record: dict[str, Any]) -> None:
    records = _read_json(memory, VALIDATION_RESULTS_FILE, [])
    if not isinstance(records, list):
        records = []
    records.append(record)
    records = sorted(records, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:MAX_STORED_ITEMS]
    _write_json(memory, VALIDATION_RESULTS_FILE, records)


def _append_activity(memory: ProjectMemory, root: Path, event: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    activity = _read_json(memory, ACTIVITY_FILE, [])
    if not isinstance(activity, list):
        activity = []
    entry = {
        "id": f"activity-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "event": event,
        "summary": scrub(summary),
        "created_at": utc_now(),
        "payload": _safe_metadata(payload),
    }
    activity.append(entry)
    activity = sorted(activity, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:MAX_ACTIVITY_ITEMS]
    _write_json(memory, ACTIVITY_FILE, activity)
    return entry


def _task_for_operation(
    root: Path,
    *,
    provided_task_id: str | None,
    title: str,
    kind: str,
    source_client: str,
    metadata: dict[str, Any],
) -> tuple[str | None, str | None]:
    if provided_task_id:
        return provided_task_id, None
    try:
        task = create_task(root, title, kind=kind, source_client=source_client or "aegis-core", metadata=metadata)
        return str(task.get("id") or ""), None
    except TaskStorePersistenceError as exc:
        return None, str(exc)


def _proposal_summary(changes: list[dict[str, Any]]) -> str:
    paths = [change["path"] for change in changes[:3]]
    suffix = "" if len(changes) <= 3 else f" and {len(changes) - 3} more"
    return f"Proposed {len(changes)} file change(s): {', '.join(paths)}{suffix}"


def _project_id(root: Path) -> str:
    digest = hashlib.sha1(str(root).lower().encode("utf-8")).hexdigest()[:12]
    return f"project-{digest}"


def _safe_metadata(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {scrub(str(key)): _safe_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return scrub(str(value)) if isinstance(value, str) else value
    return scrub(str(value))


def _read_json(memory: ProjectMemory, name: str, default: Any) -> Any:
    path = memory.root / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(memory: ProjectMemory, name: str, data: Any) -> None:
    _write_json_file(memory.root / name, data)


def _write_json_file(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise EditingPersistenceError(f"Could not persist Core editing state at {path}: {exc}") from exc


def _append_log(memory: ProjectMemory, event: str, detail: str = "") -> None:
    path = memory.root / EDITING_LOG_FILE
    line = f"- `{utc_now()}` **{scrub(event)}**"
    if detail:
        line += f"\n  {scrub(detail).replace(chr(10), chr(10) + '  ')}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return
