from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now


SCHEMA_VERSION = 1
STATE_FILE = "collaboration-runtime.json"
AUDIT_FILE = "collaboration-audit.jsonl"

ROLES: dict[str, dict[str, Any]] = {
    "owner": {
        "label": "Owner",
        "permissions": ["approve", "delegate", "rollback", "deploy", "manage_members", "view_restricted"],
        "description": "Workspace authority for local state, approvals, rollback, and governance.",
    },
    "maintainer": {
        "label": "Maintainer",
        "permissions": ["approve", "delegate", "rollback", "view_restricted"],
        "description": "Can supervise engineering workflows and approve non-production changes.",
    },
    "reviewer": {
        "label": "Reviewer",
        "permissions": ["approve_validation", "comment", "view"],
        "description": "Can review code, validation, and repair outcomes.",
    },
    "observer": {
        "label": "Observer",
        "permissions": ["view"],
        "description": "Read-only workflow visibility with restricted deployment and private memory details hidden.",
    },
    "deployment_approver": {
        "label": "Deployment Approver",
        "permissions": ["approve_deployment", "rollback", "view_restricted"],
        "description": "Can approve deployment, release, and rollback governance gates.",
    },
    "validation_reviewer": {
        "label": "Validation Reviewer",
        "permissions": ["approve_validation", "view"],
        "description": "Can sign off validation gates and test evidence.",
    },
}

APPROVAL_TYPES = {
    "workflow",
    "validation",
    "deployment",
    "rollback",
    "roadmap",
    "runtime_delegation",
    "repair",
}

ACTIVE_WORKFLOW_STATUSES = {"queued", "active", "running", "waiting_approval", "paused", "validating", "repairing", "blocked"}


class CollaborationRuntimeError(RuntimeError):
    """Raised when collaborative runtime governance cannot be applied safely."""


def collaboration_dashboard(
    workspace: str | Path,
    *,
    user_id: str | None = None,
    role: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    viewer = _viewer_context(state, user_id=user_id, role=role)
    workflows = _visible_workflows(state.get("workflows", []), viewer)
    approvals = _visible_approvals(state.get("approvals", []), viewer)
    roadmap_items = _visible_roadmap(state.get("roadmap_items", []), viewer)
    repositories = _visible_repositories(state.get("repositories", []), viewer)
    active = [item for item in workflows if item.get("status") in ACTIVE_WORKFLOW_STATUSES]
    pending_approvals = [item for item in approvals if item.get("status") == "pending"]
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": utc_now(),
        "viewer": viewer,
        "roles": role_catalog(),
        "members": _visible_members(state.get("members", []), viewer),
        "shared_workflows": workflows[: _limit(limit)],
        "active_workflows": active[: _limit(limit)],
        "approval_queue": pending_approvals[: _limit(limit)],
        "approval_history": approvals[: _limit(limit)],
        "roadmap_board": _roadmap_board(roadmap_items),
        "repositories": repositories[: _limit(limit)],
        "runtime_visibility": _runtime_visibility(root, limit=limit),
        "autopilot_governance": _autopilot_governance(root, state),
        "deployment_governance": _deployment_governance(root, state),
        "observability": _observability(state, workflows, approvals, roadmap_items),
        "privacy_controls": state.get("privacy_controls", _default_privacy_controls()),
        "governance": governance_model(),
        "audit_events": collaboration_audit(root, limit=limit)["events"],
        "state_files": {
            "state": str(_state_path(root)),
            "audit": str(_audit_path(root)),
        },
    }


def role_catalog() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in ROLES.items()]


def governance_model() -> dict[str, Any]:
    return {
        "local_first_authority": True,
        "approval_chains": "Core stores approval gates locally and requires role-eligible decisions.",
        "deployment_governance": "Production deployment and rollback actions require deployment approver or owner authority.",
        "privacy": "Private workflows and restricted deployment details are hidden from observer roles.",
        "audit": "Workflow creation, delegation, approval, rollback, roadmap, repository, and runtime visibility events are audit logged.",
    }


def register_member(
    workspace: str | Path,
    *,
    user_id: str,
    display_name: str = "",
    role: str = "reviewer",
    client_id: str = "",
    active: bool = True,
    permissions: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_user = _safe_id(user_id, prefix="user")
    clean_role = _role(role)
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        members = state.setdefault("members", [])
        existing = next((item for item in members if item.get("user_id") == clean_user), None)
        member = {
            "user_id": clean_user,
            "display_name": scrub(display_name or clean_user),
            "role": clean_role,
            "client_id": scrub(client_id),
            "active": bool(active),
            "permissions": _clean_list(permissions) or list(ROLES[clean_role]["permissions"]),
            "metadata": _safe_mapping(metadata or {}),
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        if existing:
            existing.update(member)
        else:
            members.append(member)

    state = _mutate_state(root, update)
    _audit(root, "collaboration.member.registered", actor=clean_user, target_id=clean_user, details={"role": clean_role})
    return {"workspace": str(root), "member": _member_lookup(state, clean_user), "dashboard": collaboration_dashboard(root, user_id=clean_user, role=clean_role, limit=25)}


def register_repository(
    workspace: str | Path,
    *,
    repository_id: str | None = None,
    path: str = "",
    name: str = "",
    owner_id: str = "local-owner",
    visibility: str = "workspace",
    runtime_nodes: list[str] | None = None,
    validation_infrastructure: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    repo_path = _normalize_repo_path(root, path)
    repo_id = _safe_id(repository_id or name or repo_path.name or "repository", prefix="repo")
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        repos = state.setdefault("repositories", [])
        existing = next((item for item in repos if item.get("repository_id") == repo_id), None)
        repo = {
            "repository_id": repo_id,
            "name": scrub(name or repo_path.name or repo_id),
            "path": str(repo_path),
            "owner_id": _safe_id(owner_id, prefix="user"),
            "visibility": visibility if visibility in {"workspace", "restricted", "private"} else "workspace",
            "runtime_nodes": _clean_list(runtime_nodes),
            "validation_infrastructure": _clean_list(validation_infrastructure),
            "metadata": _safe_mapping(metadata or {}),
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        if existing:
            existing.update(repo)
        else:
            repos.append(repo)

    state = _mutate_state(root, update)
    _audit(root, "collaboration.repository.registered", actor=owner_id, target_id=repo_id, details={"path": str(repo_path)})
    return {"workspace": str(root), "repository": _repository_lookup(state, repo_id), "dashboard": collaboration_dashboard(root, user_id=owner_id, limit=25)}


def create_shared_workflow(
    workspace: str | Path,
    *,
    objective: str,
    workflow_type: str = "generate_feature",
    owner_id: str = "local-owner",
    owner_role: str = "owner",
    repository_id: str | None = None,
    participants: list[dict[str, Any]] | None = None,
    reviewers: list[str] | None = None,
    visibility: str = "team",
    approval_chain: list[dict[str, Any] | str] | None = None,
    roadmap_item_ids: list[str] | None = None,
    source_client: str = "unknown",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_owner = _safe_id(owner_id, prefix="user")
    clean_role = _role(owner_role)
    now = utc_now()
    workflow_id = f"collab-wf-{uuid.uuid4().hex[:12]}"
    chain = _approval_chain(approval_chain, workflow_type=workflow_type)
    workflow = {
        "workflow_id": workflow_id,
        "workflow_type": scrub(workflow_type or "generate_feature"),
        "objective": scrub(objective or "Collaborative engineering workflow"),
        "status": "waiting_approval" if chain else "active",
        "owner_id": clean_owner,
        "owner_role": clean_role,
        "assignee_id": clean_owner,
        "repository_id": _safe_id(repository_id, prefix="repo") if repository_id else "",
        "participants": _participants(participants, clean_owner),
        "reviewers": _clean_list(reviewers),
        "visibility": visibility if visibility in {"team", "workspace", "restricted", "private"} else "team",
        "approval_ids": [],
        "approval_status": "pending" if chain else "not_required",
        "roadmap_item_ids": _clean_list(roadmap_item_ids),
        "source_client": scrub(source_client or "unknown"),
        "ownership_history": [
            {
                "timestamp": now,
                "actor_id": clean_owner,
                "event": "workflow_created",
                "owner_id": clean_owner,
                "role": clean_role,
            }
        ],
        "created_at": now,
        "updated_at": now,
        "metadata": _safe_mapping(metadata or {}),
    }

    def update(state: dict[str, Any]) -> None:
        _ensure_member(state, clean_owner, clean_role)
        approvals = []
        for stage in chain:
            approvals.append(
                _new_approval_record(
                    target_type="workflow",
                    target_id=workflow_id,
                    approval_type=str(stage.get("approval_type") or "workflow"),
                    required_roles=list(stage.get("required_roles") or []),
                    requested_by=clean_owner,
                    reason=str(stage.get("reason") or f"{workflow['workflow_type']} requires collaborative approval."),
                    stage=str(stage.get("stage") or "review"),
                    risk_level=str(stage.get("risk_level") or "medium"),
                    deployment_environment=str(stage.get("deployment_environment") or ""),
                    required_count=int(stage.get("required_count") or 0),
                    metadata=stage.get("metadata") if isinstance(stage.get("metadata"), Mapping) else {},
                )
            )
        workflow["approval_ids"] = [item["approval_id"] for item in approvals]
        state.setdefault("workflows", []).append(workflow)
        state.setdefault("approvals", []).extend(approvals)

    state = _mutate_state(root, update)
    _audit(root, "collaboration.workflow.created", actor=clean_owner, target_id=workflow_id, details={"approval_count": len(chain), "workflow_type": workflow_type})
    return {
        "workspace": str(root),
        "workflow": _workflow_lookup(state, workflow_id),
        "approvals": [item for item in state.get("approvals", []) if item.get("target_id") == workflow_id],
        "dashboard": collaboration_dashboard(root, user_id=clean_owner, role=clean_role, limit=25),
    }


def workflow_action(
    workspace: str | Path,
    workflow_id: str,
    *,
    action: str = "delegate",
    actor_id: str = "local-owner",
    actor_role: str = "owner",
    assignee_id: str = "",
    assignee_role: str = "maintainer",
    reason: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_workflow = _safe_id(workflow_id, prefix="collab-wf")
    clean_actor = _safe_id(actor_id, prefix="user")
    clean_role = _role(actor_role)
    clean_action = (action or "delegate").strip().lower()
    now = utc_now()
    created_approval: dict[str, Any] | None = None

    def update(state: dict[str, Any]) -> None:
        nonlocal created_approval
        workflow = _workflow_lookup(state, clean_workflow)
        if clean_action in {"delegate", "assign"}:
            _require_permission(clean_role, "delegate")
            workflow["assignee_id"] = _safe_id(assignee_id or workflow.get("assignee_id") or clean_actor, prefix="user")
            workflow["assignee_role"] = _role(assignee_role)
            workflow["status"] = "active" if workflow.get("status") == "queued" else workflow.get("status", "active")
        elif clean_action in {"pause", "resume", "cancel", "complete", "block"}:
            _require_permission(clean_role, "approve")
            workflow["status"] = {
                "pause": "paused",
                "resume": "active",
                "cancel": "cancelled",
                "complete": "completed",
                "block": "blocked",
            }[clean_action]
        elif clean_action in {"request_rollback", "rollback"}:
            _require_permission(clean_role, "rollback")
            created_approval = _new_approval_record(
                target_type="workflow",
                target_id=clean_workflow,
                approval_type="rollback",
                required_roles=["owner", "maintainer", "deployment_approver"],
                requested_by=clean_actor,
                reason=reason or "Rollback requires collaborative authorization.",
                stage="rollback",
                risk_level="high",
                deployment_environment="",
                required_count=1,
                metadata=metadata or {},
            )
            state.setdefault("approvals", []).append(created_approval)
            workflow.setdefault("approval_ids", []).append(created_approval["approval_id"])
            workflow["approval_status"] = "pending"
            workflow["status"] = "waiting_approval"
        else:
            raise CollaborationRuntimeError(f"unsupported collaboration workflow action: {scrub(clean_action)}")
        workflow["updated_at"] = now
        workflow.setdefault("ownership_history", []).append(
            {
                "timestamp": now,
                "actor_id": clean_actor,
                "actor_role": clean_role,
                "event": clean_action,
                "assignee_id": workflow.get("assignee_id", ""),
                "reason": scrub(reason),
            }
        )

    state = _mutate_state(root, update)
    _audit(root, f"collaboration.workflow.{clean_action}", actor=clean_actor, target_id=clean_workflow, details={"reason": reason})
    return {
        "workspace": str(root),
        "workflow": _workflow_lookup(state, clean_workflow),
        "approval": created_approval,
        "dashboard": collaboration_dashboard(root, user_id=clean_actor, role=clean_role, limit=25),
    }


def create_approval(
    workspace: str | Path,
    *,
    target_type: str,
    target_id: str,
    approval_type: str = "workflow",
    required_roles: list[str] | None = None,
    requested_by: str = "local-owner",
    reason: str = "",
    stage: str = "review",
    risk_level: str = "medium",
    deployment_environment: str = "",
    required_count: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    approval = _new_approval_record(
        target_type=target_type,
        target_id=target_id,
        approval_type=approval_type,
        required_roles=required_roles or _default_required_roles(approval_type),
        requested_by=requested_by,
        reason=reason,
        stage=stage,
        risk_level=risk_level,
        deployment_environment=deployment_environment,
        required_count=required_count,
        metadata=metadata or {},
    )

    def update(state: dict[str, Any]) -> None:
        state.setdefault("approvals", []).append(approval)
        if approval["target_type"] == "workflow":
            try:
                workflow = _workflow_lookup(state, approval["target_id"])
                workflow.setdefault("approval_ids", []).append(approval["approval_id"])
                workflow["approval_status"] = "pending"
                workflow["status"] = "waiting_approval"
                workflow["updated_at"] = utc_now()
            except CollaborationRuntimeError:
                pass

    state = _mutate_state(root, update)
    _audit(root, "collaboration.approval.requested", actor=requested_by, target_id=approval["approval_id"], details={"approval_type": approval_type})
    return {"workspace": str(root), "approval": _approval_lookup(state, approval["approval_id"]), "dashboard": collaboration_dashboard(root, limit=25)}


def decide_approval(
    workspace: str | Path,
    approval_id: str,
    *,
    decision: str,
    user_id: str,
    role: str,
    comment: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_approval = _safe_id(approval_id, prefix="approval")
    clean_user = _safe_id(user_id, prefix="user")
    clean_role = _role(role)
    clean_decision = (decision or "").strip().lower()
    if clean_decision not in {"approve", "reject"}:
        raise CollaborationRuntimeError("approval decision must be approve or reject")
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        approval = _approval_lookup(state, clean_approval)
        if not _role_can_decide(approval, clean_role, clean_user):
            raise CollaborationRuntimeError(f"role {clean_role!r} cannot decide approval {clean_approval!r}")
        approval.setdefault("decisions", []).append(
            {
                "decision_id": f"approval-decision-{uuid.uuid4().hex[:10]}",
                "user_id": clean_user,
                "role": clean_role,
                "decision": clean_decision,
                "comment": scrub(comment),
                "decided_at": now,
            }
        )
        approval["updated_at"] = now
        _refresh_approval_status(approval)
        if approval.get("target_type") == "workflow":
            _refresh_workflow_approval_status(state, str(approval.get("target_id")))

    state = _mutate_state(root, update)
    approval = _approval_lookup(state, clean_approval)
    _audit(root, f"collaboration.approval.{clean_decision}", actor=clean_user, target_id=clean_approval, details={"status": approval.get("status")})
    return {
        "workspace": str(root),
        "approval": approval,
        "target_workflow": _maybe_workflow(state, str(approval.get("target_id"))) if approval.get("target_type") == "workflow" else None,
        "dashboard": collaboration_dashboard(root, user_id=clean_user, role=clean_role, limit=25),
    }


def assign_roadmap_item(
    workspace: str | Path,
    *,
    title: str,
    item_id: str | None = None,
    workflow_id: str = "",
    milestone: str = "",
    owner_id: str = "local-owner",
    assigned_to: str = "",
    status: str = "planned",
    blockers: list[str] | None = None,
    approval_required: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_item = _safe_id(item_id or f"roadmap-{uuid.uuid4().hex[:10]}", prefix="roadmap")
    now = utc_now()
    created_approval: dict[str, Any] | None = None

    def update(state: dict[str, Any]) -> None:
        nonlocal created_approval
        items = state.setdefault("roadmap_items", [])
        existing = next((item for item in items if item.get("item_id") == clean_item), None)
        record = {
            "item_id": clean_item,
            "title": scrub(title or clean_item),
            "workflow_id": _safe_id(workflow_id, prefix="collab-wf") if workflow_id else "",
            "milestone": scrub(milestone),
            "owner_id": _safe_id(owner_id, prefix="user"),
            "assigned_to": _safe_id(assigned_to or owner_id, prefix="user"),
            "status": status if status in {"planned", "in_progress", "blocked", "completed", "cancelled"} else "planned",
            "blockers": _clean_list(blockers),
            "approval_required": bool(approval_required),
            "approval_ids": list(existing.get("approval_ids", [])) if existing else [],
            "metadata": _safe_mapping(metadata or {}),
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        if approval_required and not record["approval_ids"]:
            created_approval = _new_approval_record(
                target_type="roadmap_item",
                target_id=clean_item,
                approval_type="roadmap",
                required_roles=["owner", "maintainer", "reviewer"],
                requested_by=record["owner_id"],
                reason="Roadmap phase requires collaborative signoff before execution.",
                stage="roadmap",
                risk_level="medium",
                deployment_environment="",
                required_count=1,
                metadata={},
            )
            state.setdefault("approvals", []).append(created_approval)
            record["approval_ids"].append(created_approval["approval_id"])
        if existing:
            existing.update(record)
        else:
            items.append(record)

    state = _mutate_state(root, update)
    _audit(root, "collaboration.roadmap.assigned", actor=owner_id, target_id=clean_item, details={"status": status, "workflow_id": workflow_id})
    return {
        "workspace": str(root),
        "roadmap_item": _roadmap_lookup(state, clean_item),
        "approval": created_approval,
        "dashboard": collaboration_dashboard(root, user_id=owner_id, limit=25),
    }


def collaboration_audit(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    events: list[dict[str, Any]] = []
    path = _audit_path(root)
    try:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        events = []
    events = sorted(events, key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"workspace": str(root), "events": events[: _limit(limit)], "event_count": len(events)}


def autopilot_context(workspace: str | Path, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    meta = metadata or {}
    collab_meta = meta.get("collaboration") if isinstance(meta.get("collaboration"), Mapping) else {}
    workflow_id = str(collab_meta.get("workflow_id") or meta.get("collaboration_workflow_id") or "").strip()
    workflow = _maybe_workflow(state, workflow_id) if workflow_id else None
    if workflow is None:
        active = [item for item in state.get("workflows", []) if item.get("status") in ACTIVE_WORKFLOW_STATUSES]
        workflow = sorted(active, key=lambda item: item.get("updated_at", ""), reverse=True)[0] if active else None
    approvals = [
        item
        for item in state.get("approvals", [])
        if item.get("status") == "pending" and (not workflow or item.get("target_id") == workflow.get("workflow_id"))
    ]
    reviewers = [item for item in state.get("members", []) if item.get("role") in {"reviewer", "validation_reviewer", "deployment_approver", "maintainer", "owner"} and item.get("active", True)]
    return {
        "enabled": bool(workflow or approvals),
        "workflow_id": workflow.get("workflow_id") if workflow else "",
        "owner_id": workflow.get("owner_id") if workflow else "",
        "approval_chain": approvals,
        "required_roles": sorted({role for approval in approvals for role in approval.get("required_roles", [])}),
        "reviewers": reviewers[:20],
        "requires_approval": bool(approvals),
        "escalation_rules": [
            "Pause Autopilot at collaborative approval gates.",
            "Notify role-eligible reviewers through client surfaces.",
            "Deployment and rollback workflows require deployment approver, maintainer, or owner authority.",
        ],
    }


def _runtime_visibility(root: Path, *, limit: int) -> dict[str, Any]:
    distributed = _safe_external(lambda: __import__("aegis_core.distributed_runtime", fromlist=["runtime_dashboard"]).runtime_dashboard(root, include_audit=False, limit=limit))
    runtime = _safe_external(lambda: __import__("aegis_core.runtime_interaction", fromlist=["runtime_dashboard"]).runtime_dashboard(root, limit=limit))
    return {
        "distributed_runtime": {
            "available": bool(distributed),
            "nodes": distributed.get("nodes", [])[: _limit(limit)] if distributed else [],
            "active_workloads": distributed.get("active_workloads", [])[: _limit(limit)] if distributed else [],
            "queued_workloads": distributed.get("queued_workloads", [])[: _limit(limit)] if distributed else [],
            "observability": distributed.get("observability", {}) if distributed else {},
        },
        "runtime_sessions": runtime.get("sessions", [])[: _limit(limit)] if runtime else [],
        "active_terminal_jobs": runtime.get("active_jobs", [])[: _limit(limit)] if runtime else [],
        "stream_endpoint": runtime.get("stream_endpoint", "/v1/runtime/streams") if runtime else "/v1/runtime/streams",
    }


def _autopilot_governance(root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    supervision = _safe_external(lambda: __import__("aegis_core.autopilot", fromlist=["autopilot_supervision"]).autopilot_supervision(root))
    active = supervision.get("active_run") if supervision else None
    context = autopilot_context(root, {"collaboration_workflow_id": active.get("collaboration", {}).get("workflow_id", "")} if isinstance(active, Mapping) else {})
    return {
        "available": bool(supervision),
        "active_run_id": active.get("id") if isinstance(active, Mapping) else "",
        "active_workflow": supervision.get("active_workflow") if supervision else "",
        "pending_approvals": supervision.get("pending_approvals", []) if supervision else [],
        "collaboration_context": context,
    }


def _deployment_governance(root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    deployment = _safe_external(lambda: __import__("aegis_core.deployment_intelligence", fromlist=["deployment_dashboard"]).deployment_dashboard(root, refresh=False, limit=25))
    approvals = [
        item for item in state.get("approvals", [])
        if item.get("approval_type") in {"deployment", "rollback"} and item.get("status") == "pending"
    ]
    return {
        "available": bool(deployment),
        "active_deployment_workflows": deployment.get("active_workflows", []) if deployment else [],
        "rollback_readiness": deployment.get("rollback_readiness", {}) if deployment else {},
        "pending_deployment_approvals": approvals,
    }


def _safe_external(callback: Any) -> dict[str, Any]:
    try:
        result = callback()
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _observability(
    state: Mapping[str, Any],
    workflows: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    roadmap_items: list[dict[str, Any]],
) -> dict[str, Any]:
    active = [item for item in workflows if item.get("status") in ACTIVE_WORKFLOW_STATUSES]
    pending = [item for item in approvals if item.get("status") == "pending"]
    approved = [item for item in approvals if item.get("status") == "approved"]
    rejected = [item for item in approvals if item.get("status") == "rejected"]
    owner_counts = Counter(str(item.get("owner_id") or "unassigned") for item in workflows)
    role_counts = Counter(str(item.get("role") or "unknown") for item in state.get("members", []))
    return {
        "member_count": len(state.get("members", [])),
        "workflow_count": len(workflows),
        "active_workflow_count": len(active),
        "approval_count": len(approvals),
        "pending_approval_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "roadmap_item_count": len(roadmap_items),
        "blocked_roadmap_count": len([item for item in roadmap_items if item.get("status") == "blocked"]),
        "repository_count": len(state.get("repositories", [])),
        "workflow_owners": dict(owner_counts),
        "role_distribution": dict(role_counts),
    }


def _roadmap_board(items: list[dict[str, Any]]) -> dict[str, Any]:
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        lanes[str(item.get("status") or "planned")].append(item)
    return {
        "lanes": {key: sorted(value, key=lambda item: item.get("updated_at", ""), reverse=True) for key, value in lanes.items()},
        "milestones": dict(Counter(str(item.get("milestone") or "unassigned") for item in items)),
        "blocked": [item for item in items if item.get("status") == "blocked"],
    }


def _approval_chain(chain: list[dict[str, Any] | str] | None, *, workflow_type: str) -> list[dict[str, Any]]:
    if chain:
        result: list[dict[str, Any]] = []
        for item in chain:
            if isinstance(item, str):
                result.append({"stage": item, "approval_type": "workflow", "required_roles": ["owner", "maintainer"], "required_count": 1})
            elif isinstance(item, Mapping):
                approval_type = str(item.get("approval_type") or "workflow")
                result.append(
                    {
                        "stage": str(item.get("stage") or approval_type),
                        "approval_type": approval_type if approval_type in APPROVAL_TYPES else "workflow",
                        "required_roles": [_role(role) for role in item.get("required_roles", [])] or _default_required_roles(approval_type),
                        "required_count": max(0, int(item.get("required_count") or 0)),
                        "risk_level": str(item.get("risk_level") or "medium"),
                        "reason": str(item.get("reason") or ""),
                        "deployment_environment": str(item.get("deployment_environment") or ""),
                        "metadata": item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {},
                    }
                )
        return result
    lowered = (workflow_type or "").lower()
    if "deploy" in lowered or "release" in lowered:
        return [
            {
                "stage": "deployment_approval",
                "approval_type": "deployment",
                "required_roles": ["deployment_approver", "owner"],
                "required_count": 1,
                "risk_level": "high",
                "reason": "Deployment workflow requires release governance approval.",
                "deployment_environment": "staging_or_production",
                "metadata": {},
            }
        ]
    return []


def _new_approval_record(
    *,
    target_type: str,
    target_id: str,
    approval_type: str,
    required_roles: list[str],
    requested_by: str,
    reason: str,
    stage: str,
    risk_level: str,
    deployment_environment: str,
    required_count: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    clean_type = approval_type if approval_type in APPROVAL_TYPES else "workflow"
    roles = [_role(role) for role in required_roles] or _default_required_roles(clean_type)
    now = utc_now()
    return {
        "approval_id": f"approval-{uuid.uuid4().hex[:12]}",
        "target_type": scrub(target_type or "workflow"),
        "target_id": _safe_id(target_id, prefix="target"),
        "approval_type": clean_type,
        "stage": scrub(stage or clean_type),
        "status": "pending",
        "required_roles": roles,
        "required_count": max(0, int(required_count or 0)),
        "requested_by": _safe_id(requested_by, prefix="user"),
        "reason": scrub(reason or f"{clean_type} approval requested."),
        "risk_level": risk_level if risk_level in {"low", "medium", "high", "critical"} else "medium",
        "deployment_environment": scrub(deployment_environment),
        "decisions": [],
        "created_at": now,
        "updated_at": now,
        "metadata": _safe_mapping(metadata),
    }


def _refresh_approval_status(approval: dict[str, Any]) -> None:
    decisions = [item for item in approval.get("decisions", []) if isinstance(item, Mapping)]
    if any(item.get("decision") == "reject" for item in decisions):
        approval["status"] = "rejected"
        return
    approved = [item for item in decisions if item.get("decision") == "approve"]
    required_count = int(approval.get("required_count") or 0)
    if required_count > 0 and len({item.get("user_id") for item in approved}) >= required_count:
        approval["status"] = "approved"
        return
    approved_roles = {str(item.get("role")) for item in approved}
    required_roles = set(approval.get("required_roles") or [])
    approval["status"] = "approved" if required_roles.issubset(approved_roles) else "pending"


def _refresh_workflow_approval_status(state: dict[str, Any], workflow_id: str) -> None:
    workflow = _workflow_lookup(state, workflow_id)
    approval_ids = set(workflow.get("approval_ids") or [])
    approvals = [item for item in state.get("approvals", []) if item.get("approval_id") in approval_ids]
    if approvals and any(item.get("status") == "rejected" for item in approvals):
        workflow["approval_status"] = "rejected"
        workflow["status"] = "blocked"
    elif approvals and all(item.get("status") == "approved" for item in approvals):
        workflow["approval_status"] = "approved"
        if workflow.get("status") == "waiting_approval":
            workflow["status"] = "active"
    elif approvals:
        workflow["approval_status"] = "pending"
        workflow["status"] = "waiting_approval"
    else:
        workflow["approval_status"] = "not_required"
    workflow["updated_at"] = utc_now()


def _role_can_decide(approval: Mapping[str, Any], role: str, user_id: str) -> bool:
    if role in {"owner", "maintainer"}:
        return True
    if approval.get("approval_type") in {"deployment", "rollback"} and role == "deployment_approver":
        return True
    return role in set(approval.get("required_roles") or [])


def _require_permission(role: str, permission: str) -> None:
    permissions = set(ROLES.get(role, {}).get("permissions", []))
    if permission not in permissions:
        raise CollaborationRuntimeError(f"role {role!r} does not have {permission!r} permission")


def _default_required_roles(approval_type: str) -> list[str]:
    if approval_type == "deployment":
        return ["deployment_approver", "owner"]
    if approval_type == "rollback":
        return ["owner", "maintainer", "deployment_approver"]
    if approval_type == "validation":
        return ["validation_reviewer", "reviewer", "maintainer"]
    if approval_type == "runtime_delegation":
        return ["owner", "maintainer"]
    return ["owner", "maintainer", "reviewer"]


def _viewer_context(state: Mapping[str, Any], *, user_id: str | None, role: str | None) -> dict[str, Any]:
    clean_user = _safe_id(user_id or "local-owner", prefix="user")
    member = next((item for item in state.get("members", []) if item.get("user_id") == clean_user), None)
    clean_role = _role(role or (member or {}).get("role") or "owner")
    return {
        "user_id": clean_user,
        "role": clean_role,
        "permissions": list(ROLES[clean_role]["permissions"]),
        "restricted_visibility": clean_role == "observer",
    }


def _visible_workflows(workflows: Iterable[dict[str, Any]], viewer: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for workflow in workflows:
        item = dict(workflow)
        if not _can_view(item, viewer):
            continue
        result.append(_redact_if_needed(item, viewer))
    return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)


def _visible_approvals(approvals: Iterable[dict[str, Any]], viewer: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for approval in approvals:
        item = dict(approval)
        if viewer.get("role") == "observer" and item.get("approval_type") in {"deployment", "rollback"}:
            item = {**item, "reason": "Restricted deployment governance detail.", "metadata": {}}
        result.append(item)
    return sorted(result, key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)


def _visible_roadmap(items: Iterable[dict[str, Any]], viewer: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in items], key=lambda item: item.get("updated_at", ""), reverse=True)


def _visible_repositories(repositories: Iterable[dict[str, Any]], viewer: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for repo in repositories:
        item = dict(repo)
        if viewer.get("role") == "observer" and item.get("visibility") in {"restricted", "private"}:
            item["path"] = "<restricted>"
            item["metadata"] = {}
        result.append(item)
    return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)


def _visible_members(members: Iterable[dict[str, Any]], viewer: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(item) for item in members if item.get("active", True)], key=lambda item: item.get("role", ""))


def _can_view(workflow: Mapping[str, Any], viewer: Mapping[str, Any]) -> bool:
    if viewer.get("role") != "observer":
        return True
    if workflow.get("visibility") not in {"private", "restricted"}:
        return True
    if workflow.get("owner_id") == viewer.get("user_id") or workflow.get("assignee_id") == viewer.get("user_id"):
        return True
    return any(item.get("user_id") == viewer.get("user_id") for item in workflow.get("participants", []) if isinstance(item, Mapping))


def _redact_if_needed(workflow: dict[str, Any], viewer: Mapping[str, Any]) -> dict[str, Any]:
    if viewer.get("role") == "observer" and workflow.get("visibility") in {"restricted", "private"}:
        workflow["metadata"] = {}
        if workflow.get("workflow_type", "").startswith("deploy"):
            workflow["objective"] = "Restricted deployment workflow"
    return workflow


def _participants(participants: list[dict[str, Any]] | None, owner_id: str) -> list[dict[str, Any]]:
    result = [{"user_id": owner_id, "role": "owner"}]
    for item in participants or []:
        if not isinstance(item, Mapping):
            continue
        user_id = _safe_id(str(item.get("user_id") or item.get("id") or ""), prefix="user")
        if not user_id:
            continue
        result.append({"user_id": user_id, "role": _role(str(item.get("role") or "reviewer")), "display_name": scrub(str(item.get("display_name") or user_id))})
    seen: set[str] = set()
    deduped = []
    for item in result:
        if item["user_id"] in seen:
            continue
        seen.add(item["user_id"])
        deduped.append(item)
    return deduped


def _default_privacy_controls() -> dict[str, Any]:
    return {
        "local_first": True,
        "workspace_isolation": True,
        "private_memory_scopes": True,
        "restricted_deployment_visibility": True,
        "role_scoped_observability": True,
        "cloud_sync": False,
    }


def _load_state(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    path = memory.root / STATE_FILE
    default = _default_state(root)
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                merged = {**default, **raw}
                for key in ("members", "workflows", "approvals", "roadmap_items", "repositories"):
                    merged[key] = raw.get(key) if isinstance(raw.get(key), list) else default[key]
                merged["privacy_controls"] = raw.get("privacy_controls") if isinstance(raw.get("privacy_controls"), dict) else default["privacy_controls"]
                return merged
    except (OSError, json.JSONDecodeError):
        pass
    memory.write_json(STATE_FILE, default)
    return default


def _default_state(root: Path) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "created_at": now,
        "updated_at": now,
        "members": [
            {
                "user_id": "local-owner",
                "display_name": "Local Owner",
                "role": "owner",
                "client_id": "local-core",
                "active": True,
                "permissions": list(ROLES["owner"]["permissions"]),
                "metadata": {"local_authority": True},
                "created_at": now,
                "updated_at": now,
            }
        ],
        "workflows": [],
        "approvals": [],
        "roadmap_items": [],
        "repositories": _detect_repositories(root, now),
        "privacy_controls": _default_privacy_controls(),
    }


def _mutate_state(root: Path, callback: Any) -> dict[str, Any]:
    state = _load_state(root)
    callback(state)
    state["updated_at"] = utc_now()
    ProjectMemory(root).write_json(STATE_FILE, state)
    return state


def _state_path(root: Path) -> Path:
    return ProjectMemory(root).root / STATE_FILE


def _audit_path(root: Path) -> Path:
    return ProjectMemory(root).root / AUDIT_FILE


def _audit(root: Path, event_type: str, *, actor: str, target_id: str, details: Mapping[str, Any] | None = None) -> None:
    memory = ProjectMemory(root)
    memory.ensure()
    event = {
        "event_id": f"collab-event-{uuid.uuid4().hex[:12]}",
        "timestamp": utc_now(),
        "event_type": event_type,
        "actor_id": _safe_id(actor, prefix="user"),
        "target_id": scrub(target_id),
        "details": _safe_mapping(details or {}),
    }
    try:
        with _audit_path(root).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        return


def _detect_repositories(root: Path, now: str) -> list[dict[str, Any]]:
    repos = []
    if (root / ".git").exists():
        repos.append(
            {
                "repository_id": "repo-workspace",
                "name": root.name,
                "path": str(root),
                "owner_id": "local-owner",
                "visibility": "workspace",
                "runtime_nodes": ["local"],
                "validation_infrastructure": [],
                "metadata": {"detected": True},
                "created_at": now,
                "updated_at": now,
            }
        )
    return repos


def _ensure_member(state: dict[str, Any], user_id: str, role: str) -> None:
    if any(item.get("user_id") == user_id for item in state.setdefault("members", [])):
        return
    now = utc_now()
    state["members"].append(
        {
            "user_id": user_id,
            "display_name": user_id,
            "role": role,
            "client_id": "",
            "active": True,
            "permissions": list(ROLES[role]["permissions"]),
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
    )


def _workspace_root(workspace: str | Path) -> Path:
    return Path(workspace or ".").resolve()


def _normalize_repo_path(root: Path, path: str) -> Path:
    candidate = Path(path).expanduser() if path else root
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate.absolute()
    return resolved


def _safe_id(value: Any, *, prefix: str) -> str:
    text = scrub(str(value or "")).strip()
    if not text:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    allowed = []
    for char in text:
        allowed.append(char if char.isalnum() or char in {"-", "_", ".", "@"} else "-")
    clean = "".join(allowed).strip("-._")[:96]
    return clean or f"{prefix}-{uuid.uuid4().hex[:8]}"


def _role(role: Any) -> str:
    key = scrub(str(role or "reviewer")).strip().lower().replace("-", "_").replace(" ", "_")
    if key not in ROLES:
        raise CollaborationRuntimeError(f"unsupported collaboration role: {scrub(str(role))}")
    return key


def _clean_list(values: Iterable[Any] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = scrub(str(value or "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:256])
    return result


def _safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, raw in dict(value).items():
        clean_key = scrub(str(key))[:80]
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            safe[clean_key] = scrub(str(raw)) if isinstance(raw, str) else raw
        elif isinstance(raw, list):
            safe[clean_key] = _clean_list(raw)[:50]
        elif isinstance(raw, Mapping):
            safe[clean_key] = {scrub(str(k))[:80]: scrub(str(v))[:500] for k, v in dict(raw).items() if isinstance(v, (str, int, float, bool))}
        else:
            safe[clean_key] = scrub(str(raw))[:500]
    return safe


def _limit(limit: int) -> int:
    return max(1, min(500, int(limit or 100)))


def _member_lookup(state: Mapping[str, Any], user_id: str) -> dict[str, Any]:
    for item in state.get("members", []):
        if item.get("user_id") == user_id:
            return item
    raise CollaborationRuntimeError(f"member not found: {scrub(user_id)}")


def _repository_lookup(state: Mapping[str, Any], repository_id: str) -> dict[str, Any]:
    for item in state.get("repositories", []):
        if item.get("repository_id") == repository_id:
            return item
    raise CollaborationRuntimeError(f"repository not found: {scrub(repository_id)}")


def _workflow_lookup(state: Mapping[str, Any], workflow_id: str) -> dict[str, Any]:
    for item in state.get("workflows", []):
        if item.get("workflow_id") == workflow_id:
            return item
    raise CollaborationRuntimeError(f"collaborative workflow not found: {scrub(workflow_id)}")


def _maybe_workflow(state: Mapping[str, Any], workflow_id: str) -> dict[str, Any] | None:
    try:
        return _workflow_lookup(state, workflow_id)
    except CollaborationRuntimeError:
        return None


def _approval_lookup(state: Mapping[str, Any], approval_id: str) -> dict[str, Any]:
    for item in state.get("approvals", []):
        if item.get("approval_id") == approval_id:
            return item
    raise CollaborationRuntimeError(f"approval not found: {scrub(approval_id)}")


def _roadmap_lookup(state: Mapping[str, Any], item_id: str) -> dict[str, Any]:
    for item in state.get("roadmap_items", []):
        if item.get("item_id") == item_id:
            return item
    raise CollaborationRuntimeError(f"roadmap item not found: {scrub(item_id)}")
