from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import (
    ExecutionQueueItem,
    PluginManifest,
    RemoteWorkspaceSyncManifest,
    TaskSummary,
    WorkerAuditEvent,
    WorkerCapabilitySet,
    WorkerRuntimeInfo,
    WorkspaceRecommendation,
)
from .storage_helpers import parse_json_list, parse_json_payload, task_title_from_message
from .task_engine import normalize_task_status


def task_summary_from_row(row: Any, *, workspace_root: Path | None = None) -> TaskSummary:
    payload = dict(row)
    payload["task_id"] = payload.get("id", "")
    if workspace_root is not None:
        payload["workspace_root"] = str(workspace_root.resolve())
    payload["updated_at"] = payload.get("updated_at") or payload.get("created_at") or ""
    payload["completed_at"] = payload.get("completed_at") or payload.get("finished_at")
    payload["project_id"] = payload.get("project_id") or payload.get("workspace_root") or ""
    payload["title"] = payload.get("title") or task_title_from_message(
        str(payload.get("message") or ""),
        str(payload.get("mode") or "task"),
    )
    payload["user_goal"] = payload.get("user_goal") or payload.get("message") or ""
    payload["priority"] = int(payload.get("priority") or 0)
    payload["assigned_agent_role"] = payload.get("assigned_agent_role") or ""
    payload["related_files"] = parse_json_list(payload.pop("related_files_json", "[]"))
    payload["validation_commands"] = parse_json_list(payload.pop("validation_commands_json", "[]"))
    payload["checkpoints"] = parse_json_list(payload.pop("checkpoints_json", "[]"))
    payload["error_summary"] = payload.get("error_summary") or ""
    payload["final_summary"] = payload.get("final_summary") or ""
    payload["status"] = normalize_task_status(str(payload.get("status") or "queued"))
    return TaskSummary.model_validate(payload)


def workspace_recommendation_from_row(
    row: Any,
    project_root: Path | None = None,
) -> WorkspaceRecommendation:
    workspace_root = str(project_root.resolve()) if project_root else str(row["workspace_root"])
    return WorkspaceRecommendation(
        id=str(row["id"]),
        workspace_root=workspace_root,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        dismissed_at=str(row["dismissed_at"] or ""),
        severity=str(row["severity"]),
        category=str(row["category"]),
        title=str(row["title"]),
        detail=str(row["detail"]),
        rationale=str(row["rationale"]),
        status=str(row["status"]),
        related_files=parse_json_list(str(row["related_files_json"] or "[]")),
        related_tasks=parse_json_list(str(row["related_tasks_json"] or "[]")),
        evidence=parse_json_payload(str(row["evidence_json"] or "{}")),
        fix_prompt=str(row["fix_prompt"]),
        fix_task_id=str(row["fix_task_id"] or ""),
    )


def worker_capabilities_from_json(value: str) -> WorkerCapabilitySet:
    return WorkerCapabilitySet.model_validate(parse_json_payload(value))


def runtime_worker_from_row(row: Any) -> WorkerRuntimeInfo:
    return WorkerRuntimeInfo(
        worker_id=str(row["worker_id"]),
        name=str(row["name"]),
        kind=str(row["kind"]),
        endpoint=str(row["endpoint"] or ""),
        status=str(row["status"]),
        trust_state=str(row["trust_state"]),
        trust_scope=str(row["trust_scope"] or "local"),
        registered_at=str(row["registered_at"] or ""),
        last_heartbeat_at=str(row["last_heartbeat_at"] or ""),
        capabilities=worker_capabilities_from_json(str(row["capabilities_json"] or "{}")),
        current_jobs=int(row["current_jobs"] or 0),
        total_jobs=int(row["total_jobs"] or 0),
        failed_jobs=int(row["failed_jobs"] or 0),
        average_latency_ms=float(row["average_latency_ms"] or 0.0),
        public_key_fingerprint=str(row["public_key_fingerprint"] or ""),
        permission_scopes=parse_json_list(str(row["permission_scopes_json"] or "[]")),
        isolation_level=str(row["isolation_level"] or "process"),
        metadata=parse_json_payload(str(row["metadata_json"] or "{}")),
    )


def execution_job_values(item: ExecutionQueueItem) -> tuple[Any, ...]:
    return (
        item.id,
        item.task_id,
        item.workspace_root,
        item.kind,
        item.title,
        item.user_goal,
        item.status,
        item.priority,
        item.created_at,
        item.updated_at,
        item.assigned_worker_id,
        item.attempts,
        item.max_attempts,
        json.dumps(item.depends_on, ensure_ascii=True),
        json.dumps(item.required_capabilities, ensure_ascii=True),
        item.permission_scope,
        item.sandbox_profile,
        json.dumps(item.payload, ensure_ascii=True),
        item.error_summary,
        item.result_summary,
        item.lease_expires_at,
    )


def execution_job_from_row(
    row: Any,
    *,
    project_root: Path | None = None,
) -> ExecutionQueueItem:
    workspace_root = str(project_root.resolve()) if project_root else str(row["workspace_root"])
    return ExecutionQueueItem(
        id=str(row["id"]),
        task_id=str(row["task_id"] or ""),
        workspace_root=workspace_root,
        kind=str(row["kind"] or "task"),
        title=str(row["title"] or ""),
        user_goal=str(row["user_goal"] or ""),
        status=str(row["status"] or "queued"),
        priority=int(row["priority"] or 0),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
        assigned_worker_id=str(row["assigned_worker_id"] or ""),
        attempts=int(row["attempts"] or 0),
        max_attempts=int(row["max_attempts"] or 1),
        depends_on=parse_json_list(str(row["depends_on_json"] or "[]")),
        required_capabilities=parse_json_list(str(row["required_capabilities_json"] or "[]")),
        permission_scope=str(row["permission_scope"] or "read"),
        sandbox_profile=str(row["sandbox_profile"] or "safe"),
        payload=parse_json_payload(str(row["payload_json"] or "{}")),
        error_summary=str(row["error_summary"] or ""),
        result_summary=str(row["result_summary"] or ""),
        lease_expires_at=str(row["lease_expires_at"] or ""),
    )


def worker_audit_event_from_row(row: Any) -> WorkerAuditEvent:
    return WorkerAuditEvent(
        id=str(row["id"]),
        created_at=str(row["created_at"]),
        worker_id=str(row["worker_id"] or ""),
        job_id=str(row["job_id"] or ""),
        event_type=str(row["event_type"]),
        status=str(row["status"]),
        detail=str(row["detail"] or ""),
        metadata=parse_json_payload(str(row["metadata_json"] or "{}")),
    )


def workspace_sync_manifest_from_row(
    row: Any,
    *,
    project_root: Path | None = None,
) -> RemoteWorkspaceSyncManifest:
    workspace_root = str(project_root.resolve()) if project_root else str(row["workspace_root"])
    return RemoteWorkspaceSyncManifest(
        id=str(row["id"]),
        workspace_root=workspace_root,
        created_at=str(row["created_at"]),
        encrypted=bool(row["encrypted"]),
        encryption_label=str(row["encryption_label"] or ""),
        included_sections=parse_json_list(str(row["included_sections_json"] or "[]")),
        manifest_hash=str(row["manifest_hash"] or ""),
        payload=parse_json_payload(str(row["payload_json"] or "{}")),
    )


def plugin_manifest_from_row(row: Any) -> PluginManifest:
    payload = parse_json_payload(str(row["manifest_json"] or "{}"))
    payload.update(
        {
            "id": str(row["id"]),
            "name": str(row["name"] or payload.get("name") or row["id"]),
            "version": str(row["version"] or payload.get("version") or ""),
            "api_version": str(row["api_version"] or payload.get("api_version") or ""),
            "enabled": bool(row["enabled"]),
            "trusted": bool(row["trusted"]),
            "created_at": str(row["created_at"] or payload.get("created_at") or ""),
            "updated_at": str(row["updated_at"] or payload.get("updated_at") or ""),
            "capabilities": parse_json_list(str(row["capabilities_json"] or "[]")),
            "permissions": parse_json_list(str(row["permission_scopes_json"] or "[]")),
        }
    )
    return PluginManifest.model_validate(payload)
