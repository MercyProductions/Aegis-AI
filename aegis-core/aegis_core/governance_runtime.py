from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now


SCHEMA_VERSION = 1
STATE_FILE = "governance-policies.json"
AUDIT_FILE = "governance-audit.jsonl"
EXPORT_PREFIX = "governance-export"

POLICY_SCOPES = {
    "global",
    "workspace",
    "project",
    "runtime_node",
    "workflow_type",
    "deployment",
}

POLICY_TARGETS = {
    "workflow_execution",
    "deployment",
    "plugin_permissions",
    "runtime_node_access",
    "provider_usage",
    "memory_access",
    "validation_requirements",
    "approval_requirements",
    "command_execution",
    "file_access",
}

TRUST_LEVELS = {
    "trusted": {
        "label": "Trusted Node",
        "allowed_workloads": ["workflow", "validation", "indexing", "model_inference", "plugin_tool", "repair", "build", "benchmark"],
        "requires_approval_for_high_risk": True,
    },
    "restricted": {
        "label": "Restricted Node",
        "allowed_workloads": ["validation", "indexing", "benchmark"],
        "requires_approval_for_high_risk": True,
    },
    "isolated_validation": {
        "label": "Isolated Validation Node",
        "allowed_workloads": ["validation", "build", "benchmark"],
        "requires_approval_for_high_risk": False,
    },
    "deployment_authorized": {
        "label": "Deployment Authorized Node",
        "allowed_workloads": ["validation", "build", "deploy_staging", "deploy_production", "rollback_release"],
        "requires_approval_for_high_risk": True,
    },
    "experimental": {
        "label": "Experimental Node",
        "allowed_workloads": ["indexing", "benchmark"],
        "requires_approval_for_high_risk": True,
    },
}

HIGH_RISK_PLUGIN_SCOPES = {
    "filesystem_write",
    "network_access",
    "process_execution",
    "validation_execution",
    "provider_credentials",
}

HIGH_RISK_RUNTIME_SCOPES = {
    "filesystem_write",
    "process_execution",
    "validation_execution",
    "plugin_execution",
    "model_access",
}

DANGEROUS_COMMAND_TOKENS = {
    "rm",
    "rmdir",
    "del",
    "erase",
    "format",
    "shutdown",
    "reboot",
    "reg",
    "takeown",
    "icacls",
    "curl",
    "wget",
    "invoke-webrequest",
    "iex",
}

SENSITIVE_PATH_PARTS = {
    ".git",
    ".ssh",
    ".aws",
    ".azure",
    ".gcp",
    ".env",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
}

PRODUCTION_TARGETS = {"prod", "production", "live"}


class GovernanceRuntimeError(RuntimeError):
    """Raised when policy state or evaluation cannot be produced safely."""


def governance_dashboard(workspace: str | Path, *, include_audit: bool = True, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    policies = _effective_policies(state)
    audits = audit_events(root, limit=limit)["events"] if include_audit else []
    plugin = _plugin_governance(root)
    distributed = _distributed_governance(root)
    deployment = _deployment_governance(root)
    collaboration = _approval_governance(root)
    security = _security_governance(root)
    violations = [event for event in audits if event.get("status") in {"blocked", "needs_approval"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": utc_now(),
        "policies": policies,
        "policy_scopes": sorted(POLICY_SCOPES),
        "policy_targets": sorted(POLICY_TARGETS),
        "runtime_trust_levels": trust_levels(),
        "execution_boundaries": execution_boundaries(),
        "plugin_governance": plugin,
        "runtime_node_governance": distributed,
        "deployment_governance": deployment,
        "approval_governance": collaboration,
        "security_governance": security,
        "compliance": _compliance_summary(policies, audits, plugin, distributed, deployment, collaboration),
        "policy_violations": violations[: _limit(limit)],
        "audit_events": audits,
        "state_files": {
            "policies": str(_state_path(root)),
            "audit": str(_audit_path(root)),
        },
        "ui_summary": _ui_summary(policies, violations, plugin, distributed, deployment),
    }


def policy_catalog(workspace: str | Path | None = None) -> dict[str, Any]:
    if workspace:
        root = _workspace_root(workspace)
        policies = _effective_policies(_load_state(root))
        workspace_text = str(root)
    else:
        policies = _default_policies()
        workspace_text = None
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": workspace_text,
        "policies": policies,
        "scopes": sorted(POLICY_SCOPES),
        "targets": sorted(POLICY_TARGETS),
        "trust_levels": trust_levels(),
        "lifecycle": {
            "storage": ".aegis/governance-policies.json",
            "audit": ".aegis/governance-audit.jsonl",
            "default_mode": "local-first and approval-gated",
            "customization": "Policies can be disabled, tightened, or overridden per workspace without changing client code.",
        },
    }


def upsert_policy(
    workspace: str | Path,
    policy: Mapping[str, Any],
    *,
    actor_id: str = "local-owner",
    reason: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    incoming = _normalize_policy(policy)
    if not incoming["policy_id"]:
        raise GovernanceRuntimeError("policy_id is required")

    def update(state: dict[str, Any]) -> None:
        policies = state.setdefault("policies", [])
        existing = next((item for item in policies if item.get("policy_id") == incoming["policy_id"]), None)
        if existing:
            existing.update({**incoming, "updated_at": utc_now()})
        else:
            policies.append({**incoming, "created_at": utc_now(), "updated_at": utc_now(), "custom": True})

    state = _mutate_state(root, update)
    _audit(root, "governance.policy.upserted", "completed", f"Policy {incoming['policy_id']} updated.", actor_id=actor_id, details={"reason": reason})
    return {
        "workspace": str(root),
        "policy": next(item for item in _effective_policies(state) if item.get("policy_id") == incoming["policy_id"]),
        "dashboard": governance_dashboard(root, include_audit=True, limit=25),
    }


def evaluate_policy(
    workspace: str | Path,
    *,
    action_type: str,
    workflow_type: str = "",
    target: str = "",
    actor_id: str = "local-owner",
    actor_role: str = "owner",
    context: Mapping[str, Any] | None = None,
    approval: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    policies = _applicable_policies(_effective_policies(state), action_type=action_type, workflow_type=workflow_type, context=context or {})
    context_map = _safe_mapping(context or {})
    results = [_evaluate_one(policy, action_type=action_type, workflow_type=workflow_type, target=target, context=context_map, approval=approval, actor_role=actor_role) for policy in policies]
    blocked = [item for item in results if item["decision"] == "blocked"]
    needs_approval = [item for item in results if item["decision"] == "needs_approval"]
    warnings = [item for item in results if item["decision"] == "warn"]
    status = "blocked" if blocked else "needs_approval" if needs_approval else "allowed"
    evaluation = {
        "evaluation_id": f"policy-eval-{uuid.uuid4().hex[:12]}",
        "workspace": str(root),
        "evaluated_at": utc_now(),
        "action_type": _clean_key(action_type),
        "workflow_type": scrub(workflow_type),
        "target": scrub(target),
        "actor_id": _safe_id(actor_id, prefix="user"),
        "actor_role": _clean_key(actor_role or "owner"),
        "approval": bool(approval),
        "dry_run": bool(dry_run),
        "status": status,
        "allowed": status == "allowed",
        "policy_results": results,
        "violations": blocked + needs_approval,
        "approval_requirements": _approval_requirements(needs_approval),
        "restrictions": _restrictions(blocked),
        "warnings": [item["message"] for item in warnings],
        "compliance_tags": sorted({tag for policy in policies for tag in policy.get("compliance_tags", [])}),
        "explanation": _evaluation_explanation(status, blocked, needs_approval),
    }
    _audit(
        root,
        "governance.policy.evaluated",
        status,
        evaluation["explanation"],
        actor_id=actor_id,
        details={
            "evaluation_id": evaluation["evaluation_id"],
            "action_type": action_type,
            "workflow_type": workflow_type,
            "target": target,
            "violations": [item["policy_id"] for item in blocked + needs_approval],
        },
    )
    return evaluation


def compliance_export(
    workspace: str | Path,
    *,
    export_type: str = "full",
    limit: int = 500,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_type = _clean_key(export_type or "full")
    dashboard = governance_dashboard(root, include_audit=True, limit=limit)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "export_id": f"governance-export-{uuid.uuid4().hex[:12]}",
        "export_type": clean_type,
        "workspace": str(root),
        "generated_at": utc_now(),
        "include_sensitive": bool(include_sensitive),
        "policy_dashboard": _redact_bundle(dashboard, include_sensitive=include_sensitive),
        "audit_sources": {
            "governance": audit_events(root, limit=limit)["events"],
            "security": _read_jsonl(ProjectMemory(root).root / "security-audit.jsonl", limit=limit),
            "collaboration": _read_jsonl(ProjectMemory(root).root / "collaboration-audit.jsonl", limit=limit),
            "distributed_runtime": _read_jsonl(ProjectMemory(root).root / "distributed-runtime-audit.jsonl", limit=limit),
            "deployment": _read_jsonl(ProjectMemory(root).root / "deployment-audit.jsonl", limit=limit),
            "plugin": _read_jsonl(ProjectMemory(root).root / "plugin-observability.jsonl", limit=limit),
            "memory": _read_jsonl(ProjectMemory(root).root / "auralith-memory-audit.jsonl", limit=limit),
        },
        "reports": {
            "workflow_audit": dashboard["approval_governance"],
            "deployment_history": dashboard["deployment_governance"],
            "runtime_activity": dashboard["runtime_node_governance"],
            "plugin_permissions": dashboard["plugin_governance"],
            "policy_violations": dashboard["policy_violations"],
        },
    }
    path = ProjectMemory(root).root / f"{EXPORT_PREFIX}-{clean_type}-{uuid.uuid4().hex[:8]}.json"
    ProjectMemory(root).write_json(path.name, bundle)
    _audit(root, "governance.compliance.exported", "completed", f"Compliance export created: {path.name}", details={"export_type": clean_type, "path": str(path)})
    return {
        "workspace": str(root),
        "export": bundle,
        "path": str(path),
    }


def audit_events(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    return {
        "workspace": str(root),
        "events": _read_jsonl(_audit_path(root), limit=limit),
        "audit_path": str(_audit_path(root)),
    }


def trust_levels() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in TRUST_LEVELS.items()]


def execution_boundaries() -> dict[str, Any]:
    return {
        "dangerous_commands_blocked": sorted(DANGEROUS_COMMAND_TOKENS),
        "sensitive_path_parts": sorted(SENSITIVE_PATH_PARTS),
        "cloud_provider_usage": "requires approval when local-only/cloud-disabled/privacy-sensitive context is active",
        "deployment_targets": "production/live deploy and rollback workflows require deployment approval and validation evidence",
        "plugin_permissions": "high-risk permission scopes require approval and trust before enablement or execution",
        "runtime_nodes": "remote execution requires trust level, capability match, permission scopes, and approval for high-risk work",
        "memory": "sensitive memory export/import/access requires explicit approval and local-first controls",
    }


def autopilot_policy_context(workspace: str | Path, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(metadata or {})
    evaluation = evaluate_policy(
        workspace,
        action_type="autopilot_start",
        workflow_type=str(meta.get("workflow_type") or meta.get("autopilot_workflow_type") or ""),
        target=str(meta.get("target") or meta.get("objective") or ""),
        actor_id=str(meta.get("actor_id") or meta.get("client_id") or "autopilot"),
        actor_role=str(meta.get("actor_role") or "maintainer"),
        context={
            "target_files": meta.get("target_files") or meta.get("autopilot_requested_files") or [],
            "mode": meta.get("mode") or meta.get("autopilot_mode") or "",
            "privacy_sensitive": meta.get("privacy_sensitive", False),
            "validation_passed": meta.get("validation_passed", False),
            "checkpoint_id": meta.get("checkpoint_id", ""),
        },
        approval=bool(meta.get("policy_approval", False)),
        dry_run=True,
    )
    return {
        "enabled": True,
        "evaluation": evaluation,
        "status": evaluation["status"],
        "requires_approval": evaluation["status"] in {"blocked", "needs_approval"},
        "blocked": evaluation["status"] == "blocked",
        "approval_requirements": evaluation.get("approval_requirements", []),
        "violations": evaluation.get("violations", []),
        "explanation": evaluation.get("explanation", ""),
    }


def _default_policies() -> list[dict[str, Any]]:
    now = utc_now()
    return [
        _policy("gov.command.dangerous_tokens", "Dangerous command blocking", "global", "command_execution", "block", "critical", ["security", "local_runtime"], "Block destructive or network bootstrap command tokens."),
        _policy("gov.command.shell_requires_review", "Unrestricted shell execution review", "workspace", "command_execution", "require_approval", "high", ["security"], "Unrestricted shell execution must pause for approval."),
        _policy("gov.path.sensitive_directories", "Sensitive path boundary", "workspace", "file_access", "block", "critical", ["privacy", "workspace"], "Sensitive directories and generated dependency/build outputs are blocked by default."),
        _policy("gov.deployment.production_signoff", "Production deployment signoff", "deployment", "deployment", "require_approval", "critical", ["deployment", "change_control"], "Production deployment, live release, and rollback require deployment-authorized signoff."),
        _policy("gov.workflow.validation_before_apply", "Validation before completion/apply", "workflow_type", "validation_requirements", "require_validation", "high", ["quality", "change_control"], "Feature, refactor, repair, and deployment workflows require validation evidence before completion/apply."),
        _policy("gov.plugin.high_risk_permissions", "High-risk plugin permission gate", "workspace", "plugin_permissions", "require_approval", "high", ["plugin", "permissions"], "Plugins requesting high-risk permissions require approval and trust metadata."),
        _policy("gov.runtime.remote_trust", "Remote runtime trust isolation", "runtime_node", "runtime_node_access", "require_approval", "high", ["runtime", "distributed"], "Remote runtime work must run on trusted or isolated nodes with matching permissions."),
        _policy("gov.provider.cloud_privacy", "Cloud provider privacy boundary", "workspace", "provider_usage", "require_approval", "high", ["privacy", "provider"], "Cloud/provider calls require approval when privacy-sensitive or local-only mode is active."),
        _policy("gov.memory.sensitive_access", "Sensitive memory access control", "workspace", "memory_access", "require_approval", "medium", ["memory", "privacy"], "Sensitive memory import/export/access requires explicit approval and redaction by default."),
        _policy("gov.approval.high_risk_escalation", "High-risk approval escalation", "workspace", "approval_requirements", "require_approval", "high", ["approval", "audit"], "High-risk workflows escalate to owner, maintainer, security, or deployment reviewers."),
    ]


def _policy(policy_id: str, name: str, scope: str, target: str, effect: str, severity: str, tags: list[str], rationale: str) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "name": name,
        "enabled": True,
        "scope": scope,
        "target": target,
        "effect": effect,
        "severity": severity,
        "required_roles": _default_required_roles(target),
        "conditions": {},
        "compliance_tags": tags,
        "rationale": rationale,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "custom": False,
    }


def _evaluate_one(
    policy: Mapping[str, Any],
    *,
    action_type: str,
    workflow_type: str,
    target: str,
    context: Mapping[str, Any],
    approval: bool,
    actor_role: str,
) -> dict[str, Any]:
    policy_id = str(policy.get("policy_id") or "")
    decision = "allowed"
    message = f"Policy {policy_id} passed."
    evidence: dict[str, Any] = {}

    if policy_id == "gov.command.dangerous_tokens":
        command = _command_tokens(context)
        matches = sorted(set(command) & DANGEROUS_COMMAND_TOKENS)
        if matches:
            decision = "blocked"
            message = f"Dangerous command token(s) blocked: {', '.join(matches)}."
            evidence = {"tokens": matches}
    elif policy_id == "gov.command.shell_requires_review":
        if bool(context.get("shell")) or _looks_like_unrestricted_shell(context):
            decision = "allowed" if approval else "needs_approval"
            message = "Shell execution requires explicit approval and inspectable command logging."
            evidence = {"shell": context.get("shell"), "command": context.get("command")}
    elif policy_id == "gov.path.sensitive_directories":
        paths = _paths(context)
        blocked = [path for path in paths if _path_is_sensitive(path)]
        if blocked:
            decision = "blocked"
            message = f"Sensitive path boundary blocked {len(blocked)} path(s)."
            evidence = {"paths": blocked[:20]}
    elif policy_id == "gov.deployment.production_signoff":
        target_env = str(context.get("target_environment") or target or "").lower()
        workflow = (workflow_type or str(context.get("workflow_type") or "")).lower()
        if target_env in PRODUCTION_TARGETS or workflow in {"deploy_production", "rollback_release"}:
            has_validation = bool(context.get("validation_passed") or context.get("validation_id"))
            confirmed = bool(context.get("production_confirmed"))
            role_ok = actor_role in {"owner", "deployment_approver"}
            if not (approval and confirmed and has_validation and role_ok):
                decision = "needs_approval"
                message = "Production deployment or rollback requires validation evidence, production confirmation, and deployment-authorized approval."
                evidence = {"validation_passed": has_validation, "production_confirmed": confirmed, "actor_role": actor_role}
    elif policy_id == "gov.workflow.validation_before_apply":
        workflow = (workflow_type or str(context.get("workflow_type") or "")).lower()
        if action_type in {"apply_changes", "workflow_complete", "autopilot_start"} and workflow in {"generate_feature", "repair_project", "refactor_project", "deploy_staging", "deploy_production", "rollback_release", "build_project"}:
            if action_type == "autopilot_start":
                decision = "warn"
                message = "Autopilot must collect validation evidence before completion/apply."
            elif not bool(context.get("validation_passed") or context.get("validation_id")):
                decision = "needs_approval"
                message = "Validation evidence is required before apply or completion."
            evidence = {"workflow_type": workflow, "validation_passed": bool(context.get("validation_passed"))}
    elif policy_id == "gov.plugin.high_risk_permissions":
        scopes = set(_list(context.get("permission_scopes")))
        high_risk = sorted(scopes & HIGH_RISK_PLUGIN_SCOPES)
        if high_risk and not (approval and bool(context.get("trusted"))):
            decision = "needs_approval"
            message = "High-risk plugin permission scopes require approval and trusted plugin metadata."
            evidence = {"high_risk_scopes": high_risk, "trusted": bool(context.get("trusted"))}
    elif policy_id == "gov.runtime.remote_trust":
        if bool(context.get("allow_remote")) or action_type == "runtime_workload":
            node_trust = str(context.get("node_trust_level") or context.get("trust_level") or "untrusted")
            workload_type = str(context.get("workload_type") or workflow_type or "workflow")
            scopes = set(_list(context.get("permission_scopes")))
            high_risk = sorted(scopes & HIGH_RISK_RUNTIME_SCOPES)
            if node_trust in {"untrusted", "revoked"}:
                decision = "blocked"
                message = "Untrusted or revoked runtime nodes cannot receive workloads."
            elif node_trust == "experimental" and workload_type not in TRUST_LEVELS["experimental"]["allowed_workloads"]:
                decision = "blocked"
                message = "Experimental runtime nodes are restricted to indexing and benchmark workloads."
            elif high_risk and not approval:
                decision = "needs_approval"
                message = "Remote high-risk runtime workloads require explicit approval."
            evidence = {"node_trust_level": node_trust, "workload_type": workload_type, "high_risk_scopes": high_risk}
    elif policy_id == "gov.provider.cloud_privacy":
        if bool(context.get("cloud_provider")) or bool(context.get("allow_cloud")) or action_type == "provider_call":
            if bool(context.get("privacy_sensitive")) or bool(context.get("local_only")) or bool(context.get("cloud_disabled")):
                decision = "allowed" if approval else "needs_approval"
                message = "Cloud provider usage requires approval for privacy-sensitive or local-only workflows."
                evidence = {"privacy_sensitive": bool(context.get("privacy_sensitive")), "local_only": bool(context.get("local_only"))}
    elif policy_id == "gov.memory.sensitive_access":
        operation = str(context.get("operation") or action_type)
        category = str(context.get("category") or "")
        if operation in {"memory_export", "memory_import", "memory_access"} and (bool(context.get("sensitive")) or category in {"user_preferences", "provider_credentials", "private_memory"}):
            decision = "allowed" if approval else "needs_approval"
            message = "Sensitive memory access requires approval and redaction/export controls."
            evidence = {"operation": operation, "category": category}
    elif policy_id == "gov.approval.high_risk_escalation":
        if str(context.get("risk_level") or "").lower() in {"high", "critical"} and not approval:
            decision = "needs_approval"
            message = "High-risk workflows require staged approval before execution continues."
            evidence = {"risk_level": context.get("risk_level"), "required_roles": policy.get("required_roles", [])}

    return {
        "policy_id": policy_id,
        "name": policy.get("name", policy_id),
        "scope": policy.get("scope", "workspace"),
        "target": policy.get("target", ""),
        "effect": policy.get("effect", ""),
        "severity": policy.get("severity", "medium"),
        "decision": decision,
        "message": message,
        "required_roles": list(policy.get("required_roles") or []),
        "compliance_tags": list(policy.get("compliance_tags") or []),
        "evidence": _safe_mapping(evidence),
    }


def _applicable_policies(policies: list[dict[str, Any]], *, action_type: str, workflow_type: str, context: Mapping[str, Any]) -> list[dict[str, Any]]:
    target_map = {
        "command": {"command_execution"},
        "command_execution": {"command_execution"},
        "deployment": {"deployment", "approval_requirements", "validation_requirements"},
        "deploy": {"deployment", "approval_requirements", "validation_requirements"},
        "plugin_enable": {"plugin_permissions"},
        "plugin_tool": {"plugin_permissions"},
        "runtime_workload": {"runtime_node_access"},
        "provider_call": {"provider_usage"},
        "memory_access": {"memory_access"},
        "memory_export": {"memory_access"},
        "apply_changes": {"file_access", "validation_requirements", "approval_requirements"},
        "autopilot_start": {"file_access", "validation_requirements", "approval_requirements", "provider_usage"},
        "workflow_complete": {"validation_requirements", "approval_requirements"},
    }
    wanted = target_map.get(_clean_key(action_type), set(POLICY_TARGETS))
    if context.get("command"):
        wanted.add("command_execution")
    if context.get("paths") or context.get("target_files"):
        wanted.add("file_access")
    return [policy for policy in policies if policy.get("enabled", True) and policy.get("target") in wanted]


def _default_required_roles(target: str) -> list[str]:
    if target == "deployment":
        return ["owner", "deployment_approver"]
    if target == "plugin_permissions":
        return ["owner", "maintainer", "security_reviewer"]
    if target == "runtime_node_access":
        return ["owner", "maintainer"]
    if target == "validation_requirements":
        return ["validation_reviewer", "reviewer", "maintainer"]
    return ["owner", "maintainer"]


def _normalize_policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    policy_id = _clean_policy_id(raw.get("policy_id") or raw.get("id") or "")
    target = _clean_key(raw.get("target") or raw.get("applies_to") or "workflow_execution")
    if target not in POLICY_TARGETS:
        target = "workflow_execution"
    scope = _clean_key(raw.get("scope") or "workspace")
    if scope not in POLICY_SCOPES:
        scope = "workspace"
    effect = _clean_key(raw.get("effect") or "require_approval")
    if effect not in {"allow", "block", "require_approval", "require_validation", "warn"}:
        effect = "require_approval"
    return {
        "policy_id": policy_id,
        "name": scrub(str(raw.get("name") or policy_id)),
        "enabled": bool(raw.get("enabled", True)),
        "scope": scope,
        "target": target,
        "effect": effect,
        "severity": _clean_key(raw.get("severity") or "medium"),
        "required_roles": _list(raw.get("required_roles")) or _default_required_roles(target),
        "conditions": _safe_mapping(raw.get("conditions") if isinstance(raw.get("conditions"), Mapping) else {}),
        "compliance_tags": _list(raw.get("compliance_tags")),
        "rationale": scrub(str(raw.get("rationale") or "")),
        "custom": bool(raw.get("custom", True)),
    }


def _default_state(root: Path) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "created_at": now,
        "updated_at": now,
        "policies": _default_policies(),
    }


def _load_state(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    path = memory.root / STATE_FILE
    default = _default_state(root)
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                policies = raw.get("policies") if isinstance(raw.get("policies"), list) else default["policies"]
                merged = {**default, **raw, "policies": [_normalize_policy(item) for item in policies if isinstance(item, Mapping)]}
                return merged
    except (OSError, json.JSONDecodeError):
        pass
    memory.write_json(STATE_FILE, default)
    return default


def _mutate_state(root: Path, callback: Any) -> dict[str, Any]:
    state = _load_state(root)
    callback(state)
    state["updated_at"] = utc_now()
    ProjectMemory(root).write_json(STATE_FILE, state)
    return state


def _effective_policies(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    existing = {item["policy_id"]: item for item in _default_policies()}
    for item in state.get("policies", []):
        if isinstance(item, Mapping):
            normalized = _normalize_policy(item)
            existing[normalized["policy_id"]] = {**existing.get(normalized["policy_id"], {}), **normalized}
    return sorted(existing.values(), key=lambda item: item.get("policy_id", ""))


def _state_path(root: Path) -> Path:
    return ProjectMemory(root).root / STATE_FILE


def _audit_path(root: Path) -> Path:
    return ProjectMemory(root).root / AUDIT_FILE


def _audit(
    root: Path,
    event_type: str,
    status: str,
    detail: str,
    *,
    actor_id: str = "local-core",
    details: Mapping[str, Any] | None = None,
) -> None:
    event = {
        "event_id": f"governance-event-{uuid.uuid4().hex[:12]}",
        "timestamp": utc_now(),
        "event_type": scrub(event_type),
        "status": scrub(status),
        "actor_id": _safe_id(actor_id, prefix="user"),
        "detail": scrub(detail),
        "details": _safe_mapping(details or {}),
    }
    try:
        memory = ProjectMemory(root)
        memory.ensure()
        with _audit_path(root).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        return


def _plugin_governance(root: Path) -> dict[str, Any]:
    try:
        from . import plugin_runtime

        dashboard = plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True)
    except Exception as exc:
        return {"status": "unavailable", "error": scrub(str(exc)), "plugins": [], "high_risk_plugins": []}
    plugins = dashboard.get("plugins", []) if isinstance(dashboard, Mapping) else []
    high_risk = []
    for plugin in plugins:
        scopes = set(plugin.get("permission_scopes", [])) if isinstance(plugin, Mapping) else set()
        risk = sorted(scopes & HIGH_RISK_PLUGIN_SCOPES)
        if risk:
            high_risk.append({"plugin_id": plugin.get("id"), "scopes": risk, "trusted": bool(plugin.get("trusted")), "enabled": bool(plugin.get("enabled"))})
    return {
        "status": dashboard.get("diagnostics", {}).get("status", "ok"),
        "enabled_count": dashboard.get("diagnostics", {}).get("enabled_count", 0),
        "plugin_count": dashboard.get("diagnostics", {}).get("plugin_count", 0),
        "high_risk_plugins": high_risk,
        "permission_scopes": dashboard.get("permission_scopes", []),
        "load_failures": dashboard.get("diagnostics", {}).get("load_failures", []),
    }


def _distributed_governance(root: Path) -> dict[str, Any]:
    try:
        from . import distributed_runtime

        dashboard = distributed_runtime.runtime_dashboard(root, include_audit=True, limit=50)
    except Exception as exc:
        return {"status": "unavailable", "error": scrub(str(exc)), "nodes": [], "trust_levels": trust_levels()}
    nodes = dashboard.get("nodes", []) if isinstance(dashboard, Mapping) else []
    trust_counts = Counter(str(item.get("trust_level") or "unknown") for item in nodes if isinstance(item, Mapping))
    restricted = [item for item in nodes if isinstance(item, Mapping) and item.get("trust_level") not in {"local", "trusted"}]
    return {
        "status": "ok",
        "node_count": len(nodes),
        "trust_distribution": dict(trust_counts),
        "restricted_nodes": restricted[:20],
        "queued_workload_count": len(dashboard.get("queued_workloads", [])),
        "active_workload_count": len(dashboard.get("active_workloads", [])),
        "trust_model": dashboard.get("trust_model", {}),
    }


def _deployment_governance(root: Path) -> dict[str, Any]:
    try:
        from . import deployment_intelligence

        dashboard = deployment_intelligence.deployment_dashboard(root, refresh=False, limit=50)
    except Exception as exc:
        return {"status": "unavailable", "error": scrub(str(exc)), "active_workflows": []}
    workflows = dashboard.get("workflows", []) if isinstance(dashboard, Mapping) else []
    production_like = [
        item
        for item in workflows
        if isinstance(item, Mapping)
        and (str(item.get("target_environment") or "").lower() in PRODUCTION_TARGETS or item.get("workflow_type") in {"deploy_production", "rollback_release"})
    ]
    return {
        "status": "ok",
        "active_workflows": dashboard.get("active_workflows", []),
        "production_workflows": production_like[:20],
        "rollback_readiness": dashboard.get("rollback_readiness", {}),
        "risk_summary": dashboard.get("risk_summary", {}),
        "safety_controls": dashboard.get("safety_controls", {}),
    }


def _approval_governance(root: Path) -> dict[str, Any]:
    try:
        from . import collaboration_runtime

        dashboard = collaboration_runtime.collaboration_dashboard(root, limit=50)
    except Exception as exc:
        return {"status": "unavailable", "error": scrub(str(exc)), "approval_queue": []}
    return {
        "status": "ok",
        "approval_queue": dashboard.get("approval_queue", []),
        "active_workflows": dashboard.get("active_workflows", []),
        "role_distribution": dashboard.get("observability", {}).get("role_distribution", {}),
        "pending_approval_count": dashboard.get("observability", {}).get("pending_approval_count", 0),
        "governance": dashboard.get("governance", {}),
    }


def _security_governance(root: Path) -> dict[str, Any]:
    try:
        from . import security

        return security.security_status(root)
    except Exception as exc:
        return {"status": "unavailable", "error": scrub(str(exc))}


def _compliance_summary(
    policies: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    plugin: Mapping[str, Any],
    distributed: Mapping[str, Any],
    deployment: Mapping[str, Any],
    collaboration: Mapping[str, Any],
) -> dict[str, Any]:
    violations = [item for item in audits if item.get("status") in {"blocked", "needs_approval"}]
    return {
        "policy_count": len(policies),
        "enabled_policy_count": len([item for item in policies if item.get("enabled")]),
        "recent_violation_count": len(violations),
        "pending_approval_count": int(collaboration.get("pending_approval_count") or 0),
        "high_risk_plugin_count": len(plugin.get("high_risk_plugins", []) if isinstance(plugin.get("high_risk_plugins"), list) else []),
        "restricted_node_count": len(distributed.get("restricted_nodes", []) if isinstance(distributed.get("restricted_nodes"), list) else []),
        "production_workflow_count": len(deployment.get("production_workflows", []) if isinstance(deployment.get("production_workflows"), list) else []),
        "audit_ready": True,
        "local_first": True,
    }


def _ui_summary(
    policies: list[dict[str, Any]],
    violations: list[dict[str, Any]],
    plugin: Mapping[str, Any],
    distributed: Mapping[str, Any],
    deployment: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "status": "blocked" if violations else "review" if plugin.get("high_risk_plugins") or distributed.get("restricted_nodes") else "ok",
        "policy_violations": len(violations),
        "approval_requirements": [item.get("detail", "") for item in violations[:5]],
        "deployment_restrictions": len(deployment.get("production_workflows", []) if isinstance(deployment.get("production_workflows"), list) else []),
        "runtime_trust_warnings": len(distributed.get("restricted_nodes", []) if isinstance(distributed.get("restricted_nodes"), list) else []),
        "plugin_trust_warnings": len(plugin.get("high_risk_plugins", []) if isinstance(plugin.get("high_risk_plugins"), list) else []),
        "enabled_policy_count": len([item for item in policies if item.get("enabled")]),
    }


def _approval_requirements(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "policy_id": item["policy_id"],
            "required_roles": item.get("required_roles", []),
            "reason": item.get("message", ""),
            "severity": item.get("severity", "medium"),
        }
        for item in results
    ]


def _restrictions(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "policy_id": item["policy_id"],
            "reason": item.get("message", ""),
            "severity": item.get("severity", "medium"),
            "evidence": item.get("evidence", {}),
        }
        for item in results
    ]


def _evaluation_explanation(status: str, blocked: list[dict[str, Any]], needs_approval: list[dict[str, Any]]) -> str:
    if blocked:
        return f"Blocked by {len(blocked)} policy rule(s): {', '.join(item['policy_id'] for item in blocked[:3])}."
    if needs_approval:
        return f"Approval required by {len(needs_approval)} policy rule(s): {', '.join(item['policy_id'] for item in needs_approval[:3])}."
    if status == "allowed":
        return "No blocking policy violations were found."
    return "Policy evaluation completed."


def _command_tokens(context: Mapping[str, Any]) -> list[str]:
    raw = context.get("command") or context.get("command_text") or []
    if isinstance(raw, str):
        tokens = raw.replace(";", " ").replace("&", " ").replace("|", " ").split()
    elif isinstance(raw, Iterable):
        tokens = [str(item) for item in raw]
    else:
        tokens = []
    return [_clean_key(Path(token).name if "\\" in token or "/" in token else token).strip(".") for token in tokens if str(token).strip()]


def _looks_like_unrestricted_shell(context: Mapping[str, Any]) -> bool:
    tokens = _command_tokens(context)
    if not tokens:
        return False
    joined = " ".join(tokens)
    return any(shell in tokens[:2] for shell in {"cmd.exe", "cmd", "powershell", "pwsh", "bash", "sh"}) and any(flag in joined for flag in {"/c", "-command", "-c"})


def _paths(context: Mapping[str, Any]) -> list[str]:
    return _list(context.get("paths")) + _list(context.get("target_files")) + _list(context.get("files"))


def _path_is_sensitive(path: str) -> bool:
    parts = [part.lower() for part in Path(path.replace("\\", "/")).parts]
    basename = Path(path.replace("\\", "/")).name.lower()
    if basename in SENSITIVE_PATH_PARTS:
        return True
    return any(part in SENSITIVE_PATH_PARTS for part in parts)


def _redact_bundle(value: Any, *, include_sensitive: bool) -> Any:
    if include_sensitive:
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            clean_key = str(key)
            if any(secret in clean_key.lower() for secret in {"secret", "token", "password", "credential", "key"}):
                result[clean_key] = "<redacted>"
            else:
                result[clean_key] = _redact_bundle(item, include_sensitive=False)
        return result
    if isinstance(value, list):
        return [_redact_bundle(item, include_sensitive=False) for item in value]
    if isinstance(value, str):
        return scrub(value)
    return value


def _read_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        if not path.is_file():
            return []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    except OSError:
        return []
    return events[-_limit(limit):][::-1]


def _workspace_root(workspace: str | Path) -> Path:
    return Path(workspace or ".").expanduser().resolve()


def _clean_key(value: Any) -> str:
    return scrub(str(value or "")).strip().lower().replace("-", "_").replace(" ", "_")[:80]


def _clean_policy_id(value: Any) -> str:
    text = scrub(str(value or "")).strip().lower()
    allowed = []
    for char in text:
        allowed.append(char if char.isalnum() or char in {"-", "_", "."} else "-")
    return "".join(allowed).strip("-._")[:120]


def _safe_id(value: Any, *, prefix: str) -> str:
    text = scrub(str(value or "")).strip()
    if not text:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    allowed = []
    for char in text:
        allowed.append(char if char.isalnum() or char in {"-", "_", ".", "@"} else "-")
    clean = "".join(allowed).strip("-._")[:96]
    return clean or f"{prefix}-{uuid.uuid4().hex[:8]}"


def _safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, raw in dict(value).items():
        clean_key = scrub(str(key))[:80]
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            safe[clean_key] = scrub(raw) if isinstance(raw, str) else raw
        elif isinstance(raw, list):
            safe[clean_key] = _list(raw)[:100]
        elif isinstance(raw, Mapping):
            safe[clean_key] = _safe_mapping(raw)
        else:
            safe[clean_key] = scrub(str(raw))[:500]
    return safe


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    result = []
    seen: set[str] = set()
    for item in values:
        text = scrub(str(item or "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:256])
    return result


def _limit(limit: int) -> int:
    return max(1, min(1000, int(limit or 100)))
