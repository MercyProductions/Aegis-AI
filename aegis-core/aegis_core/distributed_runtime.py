from __future__ import annotations

import hmac
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .config import memory_dir
from .diagnostics import scrub
from .plugin_runtime import PluginRuntimeError, plugin_dashboard, run_tool
from .validation import run_validation, validation_summary
from .workspace import WorkspaceScanner


SCHEMA_VERSION = 1
STATE_FILE = "distributed-runtime.json"
AUDIT_FILE = "distributed-runtime-audit.jsonl"
STALE_NODE_SECONDS = 180

NODE_TYPES = {
    "local",
    "trusted_remote",
    "isolated_worker",
    "validation",
    "indexing",
    "gpu_model",
}

TRUST_LEVELS = {"local", "trusted", "untrusted", "revoked"}
NODE_ACTIVE_STATUSES = {"online", "idle", "busy"}

HIGH_RISK_SCOPES = {
    "filesystem_write",
    "process_execution",
    "validation_execution",
    "plugin_execution",
    "model_access",
}

WORKLOAD_CAPABILITIES = {
    "workflow": ["workflow_execution"],
    "validation": ["validation_execution"],
    "indexing": ["indexing"],
    "model_inference": ["model_inference"],
    "plugin_tool": ["plugin_execution"],
    "repair": ["repair"],
    "build": ["validation_execution"],
    "benchmark": ["benchmark"],
}

WORKLOAD_PERMISSION_SCOPES = {
    "workflow": ["workspace_scan"],
    "validation": ["validation_execution"],
    "indexing": ["workspace_scan"],
    "model_inference": ["model_access"],
    "plugin_tool": ["plugin_execution"],
    "repair": ["workspace_scan"],
    "build": ["validation_execution"],
    "benchmark": ["validation_execution"],
}

LOCAL_CAPABILITIES = [
    "workflow_execution",
    "validation_execution",
    "indexing",
    "workspace_scan",
    "plugin_execution",
    "repair",
    "build",
    "benchmark",
    "model_inference",
]

LOCAL_PERMISSION_SCOPES = [
    "filesystem_read",
    "workspace_scan",
    "validation_execution",
    "process_execution",
    "plugin_execution",
    "model_access",
]


class DistributedRuntimeError(RuntimeError):
    """Raised when distributed runtime state cannot be used safely."""


def runtime_dashboard(workspace: str | Path, *, include_audit: bool = True, limit: int = 50) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    changed = _refresh_runtime_state(root, state)
    if changed or not _state_path(root).exists():
        _save_state(root, state)
    nodes = _node_list(state)
    workloads = _workload_list(state)
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": _utc_now(),
        "local_authority": {
            "node_id": "local",
            "description": "The local Core runtime remains the authority for approvals, checkpoints, state, and fallback.",
            "state_path": str(_state_path(root)),
            "audit_path": str(_audit_path(root)),
        },
        "nodes": nodes,
        "workloads": workloads,
        "queued_workloads": [item for item in workloads if item.get("status") == "queued"],
        "active_workloads": [
            item for item in workloads if item.get("status") in {"dispatching", "assigned", "running", "waiting_approval"}
        ],
        "observability": _observability(state),
        "scheduling_policy": _scheduling_policy(),
        "trust_model": _trust_model(),
        "isolation_profiles": _isolation_profiles(),
        "deployment": _deployment_summary(root),
        "audit_events": _read_audit(root, limit=limit) if include_audit else [],
    }


def list_nodes(workspace: str | Path) -> dict[str, Any]:
    dashboard = runtime_dashboard(workspace, include_audit=False)
    return {
        "workspace": dashboard["workspace"],
        "nodes": dashboard["nodes"],
        "observability": dashboard["observability"],
        "trust_model": dashboard["trust_model"],
    }


def register_node(
    workspace: str | Path,
    *,
    node_id: str | None = None,
    name: str = "",
    node_type: str = "trusted_remote",
    endpoint: str = "",
    capabilities: list[str] | None = None,
    cpu: dict[str, Any] | None = None,
    gpu: dict[str, Any] | None = None,
    ram_gb: float | None = None,
    storage_gb: float | None = None,
    supported_workflow_types: list[str] | None = None,
    installed_models: list[str] | None = None,
    installed_plugins: list[str] | None = None,
    permission_scopes: list[str] | None = None,
    max_parallel_workloads: int = 1,
    isolation: dict[str, Any] | None = None,
    auth_token: str | None = None,
    approval: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_node_id = _safe_id(node_id or f"node-{uuid4().hex[:12]}", prefix="node")
    clean_node_type = node_type if node_type in NODE_TYPES else "trusted_remote"
    transport = _transport_status(endpoint, clean_node_type)
    auth = _auth_status(clean_node_type, endpoint, auth_token, approval)
    warnings: list[str] = []
    if not transport["encrypted_transport"]:
        warnings.append("Remote node endpoint is not HTTPS or local; Core will keep it untrusted until explicitly approved.")
    if auth["trust_level"] == "untrusted":
        warnings.append("Node registered as untrusted. It will not receive workloads until approval or a valid token is provided.")
    now = _utc_now()
    existing = state["nodes"].get(clean_node_id, {})
    node = {
        "node_id": clean_node_id,
        "name": name.strip() or clean_node_id,
        "node_type": clean_node_type,
        "endpoint": endpoint.strip(),
        "status": "online" if auth["eligible"] else "untrusted",
        "trust_level": auth["trust_level"],
        "trust_scope": auth["trust_scope"],
        "registered_at": existing.get("registered_at") or now,
        "last_heartbeat_at": now,
        "capabilities": _clean_list(capabilities),
        "cpu": cpu or {},
        "gpu": gpu or {},
        "ram_gb": ram_gb,
        "storage_gb": storage_gb,
        "supported_workflow_types": _clean_list(supported_workflow_types) or ["all"],
        "installed_models": _clean_list(installed_models),
        "installed_plugins": _clean_list(installed_plugins),
        "permission_scopes": _clean_list(permission_scopes),
        "current_workload_count": int(existing.get("current_workload_count") or 0),
        "current_workload_ids": list(existing.get("current_workload_ids") or []),
        "max_parallel_workloads": max(1, int(max_parallel_workloads or 1)),
        "isolation": isolation or _default_isolation(clean_node_type),
        "transport": transport,
        "auth": auth,
        "metadata": _scrub_mapping(metadata or {}),
        "warnings": warnings,
        "eligible": auth["eligible"] and clean_node_type != "local",
        "updated_at": now,
    }
    state["nodes"][clean_node_id] = node
    state["updated_at"] = now
    _append_audit(root, state, "runtime.node.registered", node_id=clean_node_id, details={"trust_level": node["trust_level"], "warnings": warnings})
    _save_state(root, state)
    return {"workspace": str(root), "node": node, "warnings": warnings, "audit_events": _read_audit(root, limit=10)}


def heartbeat_node(
    workspace: str | Path,
    node_id: str,
    *,
    status: str = "online",
    health: dict[str, Any] | None = None,
    current_workload_ids: list[str] | None = None,
    workload_count: int | None = None,
    capabilities: list[str] | None = None,
    installed_models: list[str] | None = None,
    installed_plugins: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_node_id = _safe_id(node_id, prefix="node")
    node = state["nodes"].get(clean_node_id)
    if not node:
        raise DistributedRuntimeError(f"runtime node not found: {scrub(clean_node_id)}")
    if node.get("trust_level") == "revoked":
        raise DistributedRuntimeError(f"runtime node is revoked: {scrub(clean_node_id)}")
    now = _utc_now()
    node["status"] = status if status in {"online", "idle", "busy", "offline", "degraded"} else "online"
    if node.get("trust_level") in {"local", "trusted"} and node["status"] in NODE_ACTIVE_STATUSES:
        node["eligible"] = True
    node["last_heartbeat_at"] = now
    node["health"] = _scrub_mapping(health or {})
    if current_workload_ids is not None:
        node["current_workload_ids"] = _clean_list(current_workload_ids)
    if workload_count is not None:
        node["current_workload_count"] = max(0, int(workload_count))
    if capabilities is not None:
        node["capabilities"] = _clean_list(capabilities)
    if installed_models is not None:
        node["installed_models"] = _clean_list(installed_models)
    if installed_plugins is not None:
        node["installed_plugins"] = _clean_list(installed_plugins)
    if metadata:
        node["metadata"] = {**node.get("metadata", {}), **_scrub_mapping(metadata)}
    node["updated_at"] = now
    state["updated_at"] = now
    _append_audit(root, state, "runtime.node.heartbeat", node_id=clean_node_id, details={"status": node["status"]})
    _save_state(root, state)
    return {"workspace": str(root), "node": node}


def revoke_node(workspace: str | Path, node_id: str, *, reason: str = "") -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    clean_node_id = _safe_id(node_id, prefix="node")
    node = state["nodes"].get(clean_node_id)
    if not node:
        raise DistributedRuntimeError(f"runtime node not found: {scrub(clean_node_id)}")
    if clean_node_id == "local":
        raise DistributedRuntimeError("local authority node cannot be revoked")
    node["status"] = "revoked"
    node["trust_level"] = "revoked"
    node["eligible"] = False
    node["revoked_at"] = _utc_now()
    node["revoke_reason"] = scrub(reason)
    recovered = _requeue_workloads_for_node(state, clean_node_id, "Node revoked.")
    _append_audit(root, state, "runtime.node.revoked", node_id=clean_node_id, details={"reason": scrub(reason), "requeued": recovered})
    _save_state(root, state)
    return {"workspace": str(root), "node": node, "requeued_workload_ids": recovered}


def create_workload(
    workspace: str | Path,
    *,
    workload_type: str,
    workflow_type: str | None = None,
    title: str = "",
    priority: int = 50,
    required_capabilities: list[str] | None = None,
    permission_scopes: list[str] | None = None,
    allow_remote: bool = False,
    preferred_node_id: str | None = None,
    payload: dict[str, Any] | None = None,
    dry_run: bool = True,
    approval: bool = False,
    max_attempts: int = 2,
    source_client: str = "unknown",
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    normalized_type = _normalize_workload_type(workload_type)
    workload_id = f"workload-{uuid4().hex[:12]}"
    now = _utc_now()
    requested_scopes = _clean_list(permission_scopes) or WORKLOAD_PERMISSION_SCOPES.get(normalized_type, ["workspace_scan"])
    workload = {
        "workload_id": workload_id,
        "workspace": str(root),
        "workload_type": normalized_type,
        "workflow_type": workflow_type or "",
        "title": title.strip() or normalized_type.replace("_", " ").title(),
        "status": "queued",
        "priority": max(0, min(100, int(priority or 50))),
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "assigned_node_id": None,
        "attempts": 0,
        "max_attempts": max(1, int(max_attempts or 1)),
        "required_capabilities": _clean_list(required_capabilities) or WORKLOAD_CAPABILITIES.get(normalized_type, []),
        "permission_scopes": requested_scopes,
        "allow_remote": bool(allow_remote),
        "preferred_node_id": _safe_id(preferred_node_id, prefix="node") if preferred_node_id else None,
        "fallback_node_ids": ["local"],
        "dry_run": bool(dry_run),
        "approval": bool(approval),
        "authorization": _workload_authorization(requested_scopes, bool(dry_run), bool(approval), bool(allow_remote)),
        "payload": _scrub_mapping(payload or {}),
        "result": {},
        "errors": [],
        "warnings": [],
        "scheduling_reason": "",
        "source_client": source_client or "unknown",
        "operation_log": [],
    }
    state["workloads"][workload_id] = workload
    state["updated_at"] = now
    _log_workload(workload, "created", "Workload queued for Core scheduling.")
    _append_audit(root, state, "runtime.workload.created", workload_id=workload_id, details={"workload_type": normalized_type})
    _save_state(root, state)
    return {"workspace": str(root), "workload": workload, "dashboard": _snapshot_from_state(root, state, include_audit=False)}


def list_workloads(workspace: str | Path, *, status: str | None = None, limit: int = 100) -> dict[str, Any]:
    dashboard = runtime_dashboard(workspace, include_audit=False)
    workloads = dashboard["workloads"]
    if status:
        workloads = [item for item in workloads if item.get("status") == status]
    return {"workspace": dashboard["workspace"], "workloads": workloads[: max(1, min(500, int(limit or 100)))]}


def get_workload(workspace: str | Path, workload_id: str) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_id = _safe_id(workload_id, prefix="workload")
    workload = state["workloads"].get(clean_id)
    if not workload:
        raise DistributedRuntimeError(f"distributed workload not found: {scrub(clean_id)}")
    return {"workspace": str(root), "workload": workload}


def dispatch_workload(
    workspace: str | Path,
    workload_id: str,
    *,
    preferred_node_id: str | None = None,
    allow_remote: bool | None = None,
    approval: bool | None = None,
    dry_run: bool | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_id = _safe_id(workload_id, prefix="workload")
    workload = state["workloads"].get(clean_id)
    if not workload:
        raise DistributedRuntimeError(f"distributed workload not found: {scrub(clean_id)}")
    if workload.get("status") in {"completed", "cancelled"}:
        return {"workspace": str(root), "workload": workload, "dispatched": False, "reason": "Workload already terminal."}
    if allow_remote is not None:
        workload["allow_remote"] = bool(allow_remote)
    if approval is not None:
        workload["approval"] = bool(approval)
    if dry_run is not None:
        workload["dry_run"] = bool(dry_run)
    if preferred_node_id:
        workload["preferred_node_id"] = _safe_id(preferred_node_id, prefix="node")
    if payload:
        workload["payload"] = {**workload.get("payload", {}), **_scrub_mapping(payload)}
    workload["authorization"] = _workload_authorization(
        list(workload.get("permission_scopes") or []),
        bool(workload.get("dry_run", True)),
        bool(workload.get("approval", False)),
        bool(workload.get("allow_remote", False)),
    )
    candidate, reason, rejected = _select_node(state, workload)
    if candidate is None:
        workload["status"] = "queued"
        workload["scheduling_reason"] = reason
        workload["errors"].append(reason)
        workload["updated_at"] = _utc_now()
        _log_workload(workload, "schedule_failed", reason)
        _append_audit(root, state, "runtime.workload.schedule_failed", workload_id=clean_id, details={"reason": reason, "rejected": rejected})
        _save_state(root, state)
        return {"workspace": str(root), "workload": workload, "dispatched": False, "reason": reason, "rejected_nodes": rejected}
    result = _execute_or_assign_workload(root, state, workload, candidate, rejected)
    _save_state(root, state)
    return result


def create_and_dispatch_workload(workspace: str | Path, **kwargs: Any) -> dict[str, Any]:
    created = create_workload(workspace, **kwargs)
    workload_id = created["workload"]["workload_id"]
    return dispatch_workload(
        workspace,
        workload_id,
        preferred_node_id=kwargs.get("preferred_node_id"),
        allow_remote=kwargs.get("allow_remote"),
        approval=kwargs.get("approval"),
        dry_run=kwargs.get("dry_run"),
    )


def retry_workload(
    workspace: str | Path,
    workload_id: str,
    *,
    approval: bool | None = None,
    allow_remote: bool | None = None,
    preferred_node_id: str | None = None,
    dispatch: bool = False,
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_id = _safe_id(workload_id, prefix="workload")
    workload = state["workloads"].get(clean_id)
    if not workload:
        raise DistributedRuntimeError(f"distributed workload not found: {scrub(clean_id)}")
    if int(workload.get("attempts") or 0) >= int(workload.get("max_attempts") or 1):
        workload["status"] = "failed"
        workload["errors"].append("Retry limit reached.")
        _append_audit(root, state, "runtime.workload.retry_blocked", workload_id=clean_id, details={"reason": "retry_limit"})
        _save_state(root, state)
        return {"workspace": str(root), "workload": workload, "retried": False, "reason": "Retry limit reached."}
    _release_workload_node(state, workload)
    workload["status"] = "queued"
    workload["assigned_node_id"] = None
    workload["started_at"] = None
    workload["finished_at"] = None
    workload["result"] = {}
    workload["updated_at"] = _utc_now()
    if approval is not None:
        workload["approval"] = bool(approval)
    if allow_remote is not None:
        workload["allow_remote"] = bool(allow_remote)
    if preferred_node_id:
        workload["preferred_node_id"] = _safe_id(preferred_node_id, prefix="node")
    _log_workload(workload, "retry", "Workload returned to queue.")
    _append_audit(root, state, "runtime.workload.retry", workload_id=clean_id)
    _save_state(root, state)
    if dispatch:
        return dispatch_workload(root, clean_id)
    return {"workspace": str(root), "workload": workload, "retried": True}


def cancel_workload(workspace: str | Path, workload_id: str, *, reason: str = "") -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    clean_id = _safe_id(workload_id, prefix="workload")
    workload = state["workloads"].get(clean_id)
    if not workload:
        raise DistributedRuntimeError(f"distributed workload not found: {scrub(clean_id)}")
    _release_workload_node(state, workload)
    workload["status"] = "cancelled"
    workload["updated_at"] = _utc_now()
    workload["finished_at"] = workload["updated_at"]
    workload["errors"].append(scrub(reason) or "Cancelled by user.")
    _log_workload(workload, "cancelled", scrub(reason) or "Cancelled by user.")
    _append_audit(root, state, "runtime.workload.cancelled", workload_id=clean_id, details={"reason": scrub(reason)})
    _save_state(root, state)
    return {"workspace": str(root), "workload": workload, "cancelled": True}


def recover_runtime(workspace: str | Path, *, auto_dispatch: bool = False) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    offline_nodes = [
        node_id
        for node_id, node in state["nodes"].items()
        if node_id != "local" and node.get("status") in {"offline", "revoked"}
    ]
    requeued: list[str] = []
    for node_id in offline_nodes:
        requeued.extend(_requeue_workloads_for_node(state, node_id, "Assigned node unavailable; requeued for local authority fallback."))
    dispatched: list[dict[str, Any]] = []
    _append_audit(root, state, "runtime.recovery", details={"offline_nodes": offline_nodes, "requeued": requeued, "auto_dispatch": auto_dispatch})
    _save_state(root, state)
    if auto_dispatch:
        for workload_id in requeued:
            dispatched.append(dispatch_workload(root, workload_id, allow_remote=False))
    return {
        "workspace": str(root),
        "offline_node_ids": offline_nodes,
        "requeued_workload_ids": requeued,
        "auto_dispatch": auto_dispatch,
        "dispatch_results": dispatched,
        "dashboard": runtime_dashboard(root, include_audit=False),
    }


def observability(workspace: str | Path) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = _load_state(root)
    _refresh_runtime_state(root, state)
    _save_state(root, state)
    return {
        "workspace": str(root),
        "observability": _observability(state),
        "audit_summary": _audit_summary(root),
        "recent_audit_events": _read_audit(root, limit=25),
    }


def audit_events(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = _require_workspace(workspace)
    return {"workspace": str(root), "audit_events": _read_audit(root, limit=limit), "audit_summary": _audit_summary(root)}


def deployment_bootstrap(workspace: str | Path, *, node_type: str = "validation", shell: str = "powershell") -> dict[str, Any]:
    root = _require_workspace(workspace)
    clean_type = node_type if node_type in NODE_TYPES else "validation"
    base_url = os.getenv("AEGIS_CORE_BASE_URL", "http://127.0.0.1:8000")
    token_hint = "$env:AEGIS_DISTRIBUTED_NODE_TOKEN"
    escaped_root = str(root).replace("'", "''")
    if shell.lower() in {"bash", "sh"}:
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'CORE_URL="${{AEGIS_CORE_BASE_URL:-{base_url}}}"',
                f'WORKSPACE="{root}"',
                f'NODE_TYPE="{clean_type}"',
                'NODE_ID="${AEGIS_NODE_ID:-$(hostname)-${NODE_TYPE}}"',
                'TOKEN="${AEGIS_DISTRIBUTED_NODE_TOKEN:-}"',
                'curl -sS -X POST "$CORE_URL/v1/distributed-runtime/nodes/register" \\',
                '  -H "Content-Type: application/json" \\',
                '  -d "{\\"workspace\\":\\"$WORKSPACE\\",\\"node_id\\":\\"$NODE_ID\\",\\"node_type\\":\\"$NODE_TYPE\\",\\"endpoint\\":\\"local://$NODE_ID\\",\\"auth_token\\":\\"$TOKEN\\",\\"capabilities\\":[\\"validation_execution\\",\\"indexing\\",\\"workspace_scan\\"],\\"permission_scopes\\":[\\"workspace_scan\\",\\"validation_execution\\"]}"',
            ]
        )
    else:
        script = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$CoreUrl = $env:AEGIS_CORE_BASE_URL; if (-not $CoreUrl) {{ $CoreUrl = '{base_url}' }}",
                f"$Workspace = '{escaped_root}'",
                f"$NodeType = '{clean_type}'",
                "$NodeId = $env:AEGIS_NODE_ID; if (-not $NodeId) { $NodeId = \"$env:COMPUTERNAME-$NodeType\" }",
                f"$Token = {token_hint}",
                "$Body = @{",
                "  workspace = $Workspace",
                "  node_id = $NodeId",
                "  name = $NodeId",
                "  node_type = $NodeType",
                "  endpoint = \"local://$NodeId\"",
                "  auth_token = $Token",
                "  capabilities = @('validation_execution', 'indexing', 'workspace_scan')",
                "  permission_scopes = @('workspace_scan', 'validation_execution')",
                "  isolation = @{ subprocess = $true; containers = 'planned'; workspace_mount = 'read_only_by_default' }",
                "} | ConvertTo-Json -Depth 8",
                "Invoke-RestMethod -Method Post -Uri \"$CoreUrl/v1/distributed-runtime/nodes/register\" -ContentType 'application/json' -Body $Body",
            ]
        )
    return {
        "workspace": str(root),
        "node_type": clean_type,
        "shell": shell,
        "base_url": base_url,
        "script": script,
        "requirements": [
            "Set AEGIS_DISTRIBUTED_NODE_TOKEN on Core and worker nodes for trusted registration.",
            "Keep remote endpoints HTTPS or local tunnel endpoints before allowing remote workloads.",
            "Approve high-risk permission scopes before process, plugin, model, or write-capable work.",
        ],
        "config_keys": {
            "AEGIS_CORE_BASE_URL": base_url,
            "AEGIS_NODE_ID": "optional stable node id",
            "AEGIS_DISTRIBUTED_NODE_TOKEN": "shared local-first trust token",
        },
    }


def compact_summary(workspace: str | Path) -> dict[str, Any]:
    try:
        dashboard = runtime_dashboard(workspace, include_audit=False)
    except Exception as exc:
        return {
            "status": "error",
            "node_count": 0,
            "active_workload_count": 0,
            "queued_workload_count": 0,
            "error": scrub(str(exc)),
        }
    observability_data = dashboard.get("observability", {})
    return {
        "status": "ok",
        "node_count": len(dashboard.get("nodes", [])),
        "online_node_count": observability_data.get("nodes", {}).get("online", 0),
        "trusted_node_count": observability_data.get("nodes", {}).get("trusted", 0),
        "active_workload_count": len(dashboard.get("active_workloads", [])),
        "queued_workload_count": len(dashboard.get("queued_workloads", [])),
        "completed_workload_count": observability_data.get("workloads", {}).get("completed", 0),
        "failed_workload_count": observability_data.get("workloads", {}).get("failed", 0),
        "last_event": (dashboard.get("audit_events") or [{}])[0],
    }


def _execute_or_assign_workload(
    root: Path,
    state: dict[str, Any],
    workload: dict[str, Any],
    node: dict[str, Any],
    rejected_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    workload["assigned_node_id"] = node["node_id"]
    workload["attempts"] = int(workload.get("attempts") or 0) + 1
    workload["status"] = "dispatching"
    workload["started_at"] = workload.get("started_at") or _utc_now()
    workload["updated_at"] = _utc_now()
    workload["scheduling_reason"] = f"Assigned to {node['node_id']} because {node.get('selection_reason', 'it matched required capabilities')}."
    _claim_workload_node(node, workload["workload_id"])
    _log_workload(workload, "assigned", workload["scheduling_reason"])
    _append_audit(root, state, "runtime.workload.assigned", node_id=node["node_id"], workload_id=workload["workload_id"], details={"rejected": rejected_nodes})

    if node["node_id"] != "local":
        workload["status"] = "assigned"
        workload["result"] = {
            "ok": True,
            "remote_dispatch": True,
            "message": "Workload authorized and assigned to a trusted remote node. External node transport executes out of process.",
            "node_endpoint": node.get("endpoint", ""),
        }
        _log_workload(workload, "remote_dispatch", "Remote node assignment recorded; local Core remains authority.")
        _append_audit(root, state, "runtime.workload.remote_dispatch", node_id=node["node_id"], workload_id=workload["workload_id"])
        return {"workspace": str(root), "workload": workload, "dispatched": True, "node": node, "remote_dispatch": True}

    approval_blocker = _approval_blocker(workload)
    if approval_blocker:
        workload["status"] = "waiting_approval"
        workload["result"] = {"ok": False, "blocked": True, "reason": approval_blocker}
        workload["warnings"].append(approval_blocker)
        _log_workload(workload, "waiting_approval", approval_blocker)
        _append_audit(root, state, "runtime.workload.waiting_approval", node_id="local", workload_id=workload["workload_id"], details={"reason": approval_blocker})
        return {"workspace": str(root), "workload": workload, "dispatched": False, "node": node, "reason": approval_blocker}

    start = time.perf_counter()
    try:
        result = _run_local_workload(root, workload)
        workload["result"] = result
        workload["status"] = "completed"
        workload["finished_at"] = _utc_now()
        workload["duration_ms"] = int((time.perf_counter() - start) * 1000)
        _log_workload(workload, "completed", "Local workload completed under Core authority.")
        _append_audit(root, state, "runtime.workload.completed", node_id="local", workload_id=workload["workload_id"], details={"duration_ms": workload["duration_ms"]})
    except Exception as exc:
        workload["status"] = "failed"
        workload["finished_at"] = _utc_now()
        workload["duration_ms"] = int((time.perf_counter() - start) * 1000)
        workload["errors"].append(scrub(str(exc)))
        workload["result"] = {"ok": False, "error": scrub(str(exc))}
        _log_workload(workload, "failed", scrub(str(exc)))
        _append_audit(root, state, "runtime.workload.failed", node_id="local", workload_id=workload["workload_id"], details={"error": scrub(str(exc))}, severity="error")
    finally:
        _release_workload_node(state, workload)
    return {"workspace": str(root), "workload": workload, "dispatched": workload["status"] == "completed", "node": node}


def _run_local_workload(root: Path, workload: dict[str, Any]) -> dict[str, Any]:
    workload_type = workload.get("workload_type")
    payload = workload.get("payload") or {}
    dry_run = bool(workload.get("dry_run", True))
    if workload_type == "indexing":
        scan = WorkspaceScanner(root).scan(persist=not dry_run)
        return {"ok": True, "dry_run": dry_run, "scan": scan}
    if workload_type in {"validation", "build", "benchmark"}:
        if dry_run or not payload.get("allow_process_execution"):
            summary = validation_summary(root)
            return {
                "ok": True,
                "dry_run": True,
                "validation_summary": summary,
                "message": "Validation command discovery completed. Process execution requires explicit approval and allow_process_execution.",
            }
        return {
            "ok": True,
            "dry_run": False,
            "validation": run_validation(
                root,
                command=payload.get("command") if isinstance(payload.get("command"), list) else None,
                timeout=max(1, min(900, int(payload.get("timeout_seconds") or 120))),
            ),
        }
    if workload_type == "plugin_tool":
        plugin_id = str(payload.get("plugin_id") or "")
        tool_name = str(payload.get("tool_name") or "")
        if not plugin_id or not tool_name:
            raise DistributedRuntimeError("plugin_tool workload requires plugin_id and tool_name payload fields")
        return run_tool(
            root,
            plugin_id,
            tool_name,
            payload.get("input") if isinstance(payload.get("input"), dict) else {},
            dry_run=dry_run,
            approval=bool(workload.get("approval", False)),
            workflow_type=workload.get("workflow_type") or None,
            source_client=workload.get("source_client") or "distributed_runtime",
        )
    if workload_type == "model_inference":
        return {
            "ok": True,
            "dry_run": True,
            "message": "Local model execution dispatch contract recorded. Provider invocation remains delegated to Core model routing endpoints.",
            "requested_model": payload.get("model") or payload.get("model_id") or "",
        }
    if workload_type in {"workflow", "repair"}:
        return {
            "ok": True,
            "dry_run": dry_run,
            "message": "Workflow workload accepted by Core scheduler. Existing workflow engine remains the local execution authority.",
            "workflow_type": workload.get("workflow_type") or workload_type,
        }
    return {"ok": True, "dry_run": dry_run, "message": f"Workload type {workload_type} accepted for local authority tracking."}


def _select_node(state: dict[str, Any], workload: dict[str, Any]) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    nodes = list(state["nodes"].values())
    preferred_id = workload.get("preferred_node_id")
    if preferred_id:
        nodes.sort(key=lambda item: 0 if item.get("node_id") == preferred_id else 1)
    else:
        nodes.sort(key=lambda item: (0 if item.get("node_id") == "local" else 1, int(item.get("current_workload_count") or 0), item.get("node_id", "")))
    rejected: list[dict[str, Any]] = []
    for node in nodes:
        ok, reason = _node_can_run(node, workload)
        if ok:
            node["selection_reason"] = reason
            return node, reason, rejected
        rejected.append({"node_id": node.get("node_id"), "reason": reason})
    return None, "No eligible runtime node matched workload trust, capability, permission, remote opt-in, and capacity requirements.", rejected


def _node_can_run(node: dict[str, Any], workload: dict[str, Any]) -> tuple[bool, str]:
    node_id = node.get("node_id")
    if node.get("trust_level") not in {"local", "trusted"}:
        return False, "node is not trusted"
    if node.get("status") not in NODE_ACTIVE_STATUSES:
        return False, f"node status is {node.get('status')}"
    if node_id != "local" and not workload.get("allow_remote"):
        return False, "remote dispatch is not enabled for this workload"
    if int(node.get("current_workload_count") or 0) >= int(node.get("max_parallel_workloads") or 1):
        return False, "node is at capacity"
    required = set(workload.get("required_capabilities") or [])
    capabilities = set(node.get("capabilities") or [])
    if not required.issubset(capabilities):
        return False, f"missing capability: {', '.join(sorted(required - capabilities))}"
    workflow_type = str(workload.get("workflow_type") or "")
    supported = set(node.get("supported_workflow_types") or [])
    if workflow_type and supported and "all" not in supported and workflow_type not in supported:
        return False, "workflow type not supported by node"
    required_scopes = set(workload.get("permission_scopes") or [])
    node_scopes = set(node.get("permission_scopes") or [])
    if not required_scopes.issubset(node_scopes):
        return False, f"missing permission scope: {', '.join(sorted(required_scopes - node_scopes))}"
    return True, "trust, capability, permission, capacity, and workflow constraints matched"


def _approval_blocker(workload: dict[str, Any]) -> str:
    authorization = workload.get("authorization") or {}
    if authorization.get("approval_required") and not workload.get("approval"):
        return "User approval is required before high-risk distributed workload execution."
    if workload.get("workload_type") in {"validation", "build", "benchmark"}:
        payload = workload.get("payload") or {}
        if payload.get("allow_process_execution") and not workload.get("approval"):
            return "Process execution for validation/build workloads requires explicit approval."
    return ""


def _workload_authorization(permission_scopes: list[str], dry_run: bool, approval: bool, allow_remote: bool) -> dict[str, Any]:
    high_risk = sorted(set(permission_scopes) & HIGH_RISK_SCOPES)
    approval_required = bool(high_risk and not dry_run)
    remote_warning = allow_remote and approval_required and not approval
    return {
        "approval_required": approval_required,
        "approval_granted": approval,
        "high_risk_scopes": high_risk,
        "remote_authorized": bool(allow_remote),
        "remote_warning": remote_warning,
        "notes": [
            "Dry-run workloads can be scheduled without approval." if dry_run else "Non-dry-run high-risk workloads require approval.",
            "Remote dispatch is opt-in per workload.",
        ],
    }


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    state: dict[str, Any]
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            state = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise DistributedRuntimeError(f"Unable to read distributed runtime state: {scrub(str(exc))}") from exc
    else:
        state = {}
    if state.get("schema_version") != SCHEMA_VERSION:
        state = _new_state(root)
    state.setdefault("nodes", {})
    state.setdefault("workloads", {})
    _ensure_local_node(root, state)
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _utc_now()
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise DistributedRuntimeError(f"Unable to write distributed runtime state: {scrub(str(exc))}") from exc


def _new_state(root: Path) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "created_at": now,
        "updated_at": now,
        "nodes": {},
        "workloads": {},
        "authority": {"node_id": "local", "local_first": True, "requires_approval_for_high_risk_work": True},
    }


def _refresh_runtime_state(root: Path, state: dict[str, Any]) -> bool:
    changed = False
    _ensure_local_node(root, state)
    now = datetime.now(timezone.utc)
    for node_id, node in state.get("nodes", {}).items():
        if node_id == "local" or node.get("trust_level") in {"revoked", "untrusted"}:
            continue
        heartbeat = _parse_time(node.get("last_heartbeat_at"))
        if heartbeat and (now - heartbeat).total_seconds() > STALE_NODE_SECONDS and node.get("status") != "offline":
            node["status"] = "offline"
            node["eligible"] = False
            changed = True
    return changed


def _ensure_local_node(root: Path, state: dict[str, Any]) -> None:
    now = _utc_now()
    existing = state.get("nodes", {}).get("local", {})
    state.setdefault("nodes", {})["local"] = {
        "node_id": "local",
        "name": "Local Aegis Core",
        "node_type": "local",
        "endpoint": "local://aegis-core",
        "status": "online",
        "trust_level": "local",
        "trust_scope": "full_local_authority",
        "registered_at": existing.get("registered_at") or now,
        "last_heartbeat_at": now,
        "capabilities": LOCAL_CAPABILITIES,
        "cpu": {"logical_cores": os.cpu_count() or 1},
        "gpu": _local_gpu_info(),
        "ram_gb": existing.get("ram_gb"),
        "storage_gb": _local_storage_gb(root),
        "supported_workflow_types": ["all"],
        "installed_models": existing.get("installed_models", []),
        "installed_plugins": _enabled_plugin_ids(root),
        "permission_scopes": LOCAL_PERMISSION_SCOPES,
        "current_workload_count": int(existing.get("current_workload_count") or 0),
        "current_workload_ids": list(existing.get("current_workload_ids") or []),
        "max_parallel_workloads": int(existing.get("max_parallel_workloads") or 2),
        "isolation": _default_isolation("local"),
        "transport": {"encrypted_transport": True, "scheme": "local", "local_only": True},
        "auth": {"eligible": True, "trust_level": "local", "trust_scope": "full_local_authority", "token_present": False, "approval_granted": True},
        "metadata": {"workspace": str(root), "local_first_authority": True},
        "warnings": [],
        "eligible": True,
        "updated_at": now,
    }


def _snapshot_from_state(root: Path, state: dict[str, Any], *, include_audit: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": _utc_now(),
        "nodes": _node_list(state),
        "workloads": _workload_list(state),
        "observability": _observability(state),
        "audit_events": _read_audit(root, limit=25) if include_audit else [],
    }


def _node_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(list(state.get("nodes", {}).values()), key=lambda item: (0 if item.get("node_id") == "local" else 1, item.get("node_id", "")))


def _workload_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        list(state.get("workloads", {}).values()),
        key=lambda item: (int(item.get("priority") or 50) * -1, item.get("created_at", "")),
    )


def _append_audit(
    root: Path,
    state: dict[str, Any],
    event_type: str,
    *,
    node_id: str | None = None,
    workload_id: str | None = None,
    details: dict[str, Any] | None = None,
    severity: str = "info",
) -> None:
    event = {
        "event_id": f"runtime-event-{uuid4().hex[:12]}",
        "event_type": event_type,
        "severity": severity,
        "workspace": str(root),
        "node_id": node_id,
        "workload_id": workload_id,
        "details": _scrub_mapping(details or {}),
        "created_at": _utc_now(),
    }
    path = _audit_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError as exc:
        raise DistributedRuntimeError(f"Unable to write distributed runtime audit event: {scrub(str(exc))}") from exc
    state["last_audit_event"] = event


def _read_audit(root: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    path = _audit_path(root)
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
    by_severity: dict[str, int] = {}
    for event in events:
        by_type[str(event.get("event_type") or "unknown")] = by_type.get(str(event.get("event_type") or "unknown"), 0) + 1
        by_severity[str(event.get("severity") or "info")] = by_severity.get(str(event.get("severity") or "info"), 0) + 1
    return {"event_count": len(events), "by_type": by_type, "by_severity": by_severity}


def _observability(state: dict[str, Any]) -> dict[str, Any]:
    nodes = list(state.get("nodes", {}).values())
    workloads = list(state.get("workloads", {}).values())
    status_counts: dict[str, int] = {}
    trust_counts: dict[str, int] = {}
    workload_status_counts: dict[str, int] = {}
    workload_type_counts: dict[str, int] = {}
    durations: list[int] = []
    for node in nodes:
        status_counts[str(node.get("status") or "unknown")] = status_counts.get(str(node.get("status") or "unknown"), 0) + 1
        trust_counts[str(node.get("trust_level") or "unknown")] = trust_counts.get(str(node.get("trust_level") or "unknown"), 0) + 1
    for workload in workloads:
        workload_status_counts[str(workload.get("status") or "unknown")] = workload_status_counts.get(str(workload.get("status") or "unknown"), 0) + 1
        workload_type_counts[str(workload.get("workload_type") or "unknown")] = workload_type_counts.get(str(workload.get("workload_type") or "unknown"), 0) + 1
        if isinstance(workload.get("duration_ms"), int):
            durations.append(int(workload["duration_ms"]))
    return {
        "nodes": {
            "total": len(nodes),
            "online": status_counts.get("online", 0) + status_counts.get("idle", 0) + status_counts.get("busy", 0),
            "trusted": trust_counts.get("trusted", 0) + trust_counts.get("local", 0),
            "by_status": status_counts,
            "by_trust": trust_counts,
        },
        "workloads": {
            "total": len(workloads),
            "queued": workload_status_counts.get("queued", 0),
            "active": sum(workload_status_counts.get(key, 0) for key in ["dispatching", "assigned", "running", "waiting_approval"]),
            "completed": workload_status_counts.get("completed", 0),
            "failed": workload_status_counts.get("failed", 0),
            "cancelled": workload_status_counts.get("cancelled", 0),
            "by_status": workload_status_counts,
            "by_type": workload_type_counts,
        },
        "latency": {
            "average_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
        },
        "scheduling": {
            "remote_opt_in_required": True,
            "local_fallback_available": True,
            "stale_node_seconds": STALE_NODE_SECONDS,
        },
    }


def _scheduling_policy() -> dict[str, Any]:
    return {
        "default": "prefer_local_authority",
        "remote_dispatch": "opt_in_per_workload",
        "fallback": ["retry_same_node_if_healthy", "reassign_trusted_node", "local_authority"],
        "capacity": "do_not_assign_above max_parallel_workloads",
        "capability_matching": "required_capabilities and permission_scopes must be a subset of node declarations",
        "approval": "non-dry-run high-risk scopes require explicit user approval",
    }


def _trust_model() -> dict[str, Any]:
    return {
        "local": "Full local authority. Owns approvals, checkpoints, audit, and persisted state.",
        "trusted": "Registered with a matching local trust token or explicit user approval.",
        "untrusted": "Visible for diagnostics but never eligible for workload scheduling.",
        "revoked": "Blocked and any assigned workloads are requeued for fallback.",
        "auth_environment": ["AEGIS_DISTRIBUTED_NODE_TOKEN", "AEGIS_CORE_LOCAL_TOKEN"],
        "transport": "Remote endpoints should use HTTPS. Non-HTTPS remote endpoints stay warning-marked.",
    }


def _isolation_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": "local-subprocess",
            "scope": "local",
            "description": "Local process execution is approval-gated and uses existing Core validation safety checks.",
            "workspace_mount": "native",
            "containers": "not_required",
        },
        {
            "id": "remote-worker",
            "scope": "trusted_remote",
            "description": "Remote execution is authorized by Core and performed out of process by the node transport.",
            "workspace_mount": "explicit_sync_or_read_only_mount_required",
            "containers": "recommended",
        },
        {
            "id": "sandboxed-plugin",
            "scope": "plugin_execution",
            "description": "Arbitrary plugin code remains blocked until an external sandbox runner is available.",
            "workspace_mount": "least_privilege",
            "containers": "planned",
        },
    ]


def _deployment_summary(root: Path) -> dict[str, Any]:
    return {
        "bootstrap_endpoint": "/v1/distributed-runtime/deployment/bootstrap",
        "state_path": str(_state_path(root)),
        "audit_path": str(_audit_path(root)),
        "worker_installation": "Run the bootstrap script on a trusted worker and set AEGIS_DISTRIBUTED_NODE_TOKEN.",
        "updates": "Worker update orchestration is represented in node metadata; package transport remains external.",
        "recovery": "Offline or revoked node workloads are requeued for local fallback.",
    }


def _claim_workload_node(node: dict[str, Any], workload_id: str) -> None:
    ids = list(node.get("current_workload_ids") or [])
    if workload_id not in ids:
        ids.append(workload_id)
    node["current_workload_ids"] = ids
    node["current_workload_count"] = len(ids)
    if len(ids) >= int(node.get("max_parallel_workloads") or 1):
        node["status"] = "busy"


def _release_workload_node(state: dict[str, Any], workload: dict[str, Any]) -> None:
    node_id = workload.get("assigned_node_id")
    if not node_id:
        return
    node = state.get("nodes", {}).get(node_id)
    if not node:
        return
    ids = [item for item in list(node.get("current_workload_ids") or []) if item != workload.get("workload_id")]
    node["current_workload_ids"] = ids
    node["current_workload_count"] = len(ids)
    if node.get("status") == "busy" and len(ids) < int(node.get("max_parallel_workloads") or 1):
        node["status"] = "online"


def _requeue_workloads_for_node(state: dict[str, Any], node_id: str, reason: str) -> list[str]:
    requeued: list[str] = []
    for workload in state.get("workloads", {}).values():
        if workload.get("assigned_node_id") != node_id:
            continue
        if workload.get("status") in {"completed", "cancelled"}:
            continue
        workload["status"] = "queued"
        workload["assigned_node_id"] = None
        workload["updated_at"] = _utc_now()
        workload.setdefault("errors", []).append(reason)
        workload.setdefault("fallback_node_ids", [])
        if "local" not in workload["fallback_node_ids"]:
            workload["fallback_node_ids"].append("local")
        _log_workload(workload, "requeued", reason)
        requeued.append(workload["workload_id"])
    node = state.get("nodes", {}).get(node_id)
    if node:
        node["current_workload_ids"] = []
        node["current_workload_count"] = 0
    return requeued


def _log_workload(workload: dict[str, Any], event: str, message: str) -> None:
    workload.setdefault("operation_log", []).append({"event": event, "message": scrub(message), "created_at": _utc_now()})


def _auth_status(node_type: str, endpoint: str, auth_token: str | None, approval: bool) -> dict[str, Any]:
    if node_type == "local" or endpoint.startswith("local://"):
        return {"eligible": True, "trust_level": "local", "trust_scope": "full_local_authority", "token_present": bool(auth_token), "approval_granted": True}
    expected = os.getenv("AEGIS_DISTRIBUTED_NODE_TOKEN") or os.getenv("AEGIS_CORE_LOCAL_TOKEN") or ""
    token_ok = bool(expected and auth_token and hmac.compare_digest(str(auth_token), expected))
    if token_ok or approval:
        return {
            "eligible": True,
            "trust_level": "trusted",
            "trust_scope": "approved_remote_worker" if approval and not token_ok else "token_authenticated_worker",
            "token_present": bool(auth_token),
            "approval_granted": bool(approval),
        }
    return {"eligible": False, "trust_level": "untrusted", "trust_scope": "none", "token_present": bool(auth_token), "approval_granted": False}


def _transport_status(endpoint: str, node_type: str) -> dict[str, Any]:
    parsed = urlparse(endpoint)
    local = endpoint.startswith("local://") or parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    encrypted = local or parsed.scheme == "https" or node_type == "local"
    return {
        "scheme": parsed.scheme or ("local" if local else "unknown"),
        "hostname": parsed.hostname or "",
        "encrypted_transport": encrypted,
        "local_only": local or node_type == "local",
        "notes": [] if encrypted else ["Use HTTPS or a local tunnel before trusting this node."],
    }


def _default_isolation(node_type: str) -> dict[str, Any]:
    if node_type == "local":
        return {"subprocess": True, "containers": "optional", "workspace_mount": "native", "plugin_code": "builtin_handlers_only"}
    if node_type in {"isolated_worker", "validation"}:
        return {"subprocess": True, "containers": "supported_or_planned", "workspace_mount": "read_only_by_default", "plugin_code": "sandbox_required"}
    return {"subprocess": True, "containers": "recommended", "workspace_mount": "explicit_sync_required", "plugin_code": "sandbox_required"}


def _normalize_workload_type(value: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in WORKLOAD_CAPABILITIES:
        return text
    return "workflow"


def _clean_list(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _safe_id(value: str | None, *, prefix: str) -> str:
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text).strip("-._")
    if not clean:
        return f"{prefix}-{uuid4().hex[:12]}"
    if len(clean) > 96:
        clean = clean[:96]
    return clean


def _scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    scrubbed: dict[str, Any] = {}
    for key, value in data.items():
        key_text = str(key)
        if any(secret in key_text.lower() for secret in ["token", "secret", "password", "api_key", "apikey", "credential"]):
            scrubbed[key_text] = "[redacted]"
        elif isinstance(value, dict):
            scrubbed[key_text] = _scrub_mapping(value)
        elif isinstance(value, list):
            scrubbed[key_text] = [_scrub_mapping(item) if isinstance(item, dict) else scrub(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, str):
            scrubbed[key_text] = scrub(value)
        else:
            scrubbed[key_text] = value
    return scrubbed


def _enabled_plugin_ids(root: Path) -> list[str]:
    try:
        dashboard = plugin_dashboard(root, include_disabled=False, refresh=False)
    except (PluginRuntimeError, OSError, ValueError):
        return []
    return list(dashboard.get("enabled_plugins") or [])


def _local_gpu_info() -> dict[str, Any]:
    gpu_name = os.getenv("AEGIS_LOCAL_GPU_NAME") or ""
    return {"available": bool(gpu_name), "name": gpu_name}


def _local_storage_gb(root: Path) -> float | None:
    try:
        usage = shutil.disk_usage(root)
    except OSError:
        return None
    return round(usage.free / (1024**3), 2)


def _require_workspace(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise DistributedRuntimeError(f"workspace does not exist or is not a directory: {scrub(str(root))}")
    return root


def _state_path(root: Path) -> Path:
    return memory_dir(root) / STATE_FILE


def _audit_path(root: Path) -> Path:
    return memory_dir(root) / AUDIT_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)
