from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from . import distributed_runtime, dogfooding, onboarding, plugin_runtime, release, runtime_interaction
from .diagnostics import redact_inline, scrub
from .memory import ProjectMemory, utc_now
from .quality_gates import quality_gate_dashboard
from .security import security_status
from .stabilization import release_candidate_checklist
from .validation import validation_summary
from .workflow_runtime import workflow_statistics


ALPHA_READINESS_FILE = "alpha-readiness.json"
ALPHA_FEATURE_FLAGS_FILE = "alpha-feature-flags.json"
ALPHA_FEEDBACK_FILE = "alpha-feedback.jsonl"
ALPHA_DIAGNOSTICS_DIR = "alpha-diagnostics"
MAX_FEEDBACK = 500

ALPHA_FEATURE_FLAGS: dict[str, dict[str, Any]] = {
    "local_only_mode": {"default": True, "category": "safety", "alpha_locked": True, "description": "Prefer local model/runtime paths by default."},
    "approval_required_mode": {"default": True, "category": "safety", "alpha_locked": True, "description": "Require approval before mutating workflows."},
    "conservative_orchestration": {"default": True, "category": "orchestration", "alpha_locked": True, "description": "Keep autonomous behavior bounded and inspectable."},
    "validation_before_apply": {"default": True, "category": "safety", "alpha_locked": True, "description": "Require validation review before applying proposed work."},
    "rollback_visibility": {"default": True, "category": "safety", "alpha_locked": True, "description": "Always expose checkpoint and rollback state."},
    "plugin_loading": {"default": True, "category": "plugins", "alpha_locked": False, "description": "Allow manifest-only plugin discovery and validation."},
    "high_risk_plugin_enablement": {"default": False, "category": "plugins", "alpha_locked": True, "description": "Block high-risk plugin scopes unless explicitly approved outside alpha defaults."},
    "distributed_runtime": {"default": False, "category": "distributed", "alpha_locked": False, "description": "Keep remote/distributed execution disabled unless the tester is in that cohort."},
    "experimental_workflows": {"default": False, "category": "workflows", "alpha_locked": False, "description": "Hide experimental workflow types from default alpha UX."},
    "dev_release_channel": {"default": False, "category": "release", "alpha_locked": False, "description": "Expose development channel checks only for internal testers."},
    "telemetry_enabled": {"default": False, "category": "telemetry", "alpha_locked": False, "description": "External telemetry upload stays disabled; local diagnostics remain inspectable."},
    "local_only_diagnostics": {"default": True, "category": "telemetry", "alpha_locked": True, "description": "Diagnostics bundles are generated locally under .aegis."},
}

FEEDBACK_CATEGORIES = {
    "workflow_pain",
    "orchestration_confusion",
    "plugin_issue",
    "performance_problem",
    "onboarding_friction",
    "trust_concern",
    "validation_issue",
    "update_issue",
    "distributed_runtime_issue",
    "other",
}


def alpha_readiness(workspace: str | Path, *, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    flags = alpha_feature_flags(root)
    diagnostics = runtime_diagnostics_snapshot(root, include_replay=False)
    checklist = _readiness_checklist(root, diagnostics, flags)
    blockers = [item for item in checklist if item["status"] == "blocked" and item["required"]]
    warnings = [item for item in checklist if item["status"] == "warning"]
    state = {
        "workspace": str(root),
        "generated_at": utc_now(),
        "alpha_phase": "controlled_external_alpha",
        "ready": not blockers,
        "status": "blocked" if blockers else ("warning" if warnings else "ready"),
        "score": _readiness_score(checklist),
        "checklist": checklist,
        "feature_classification": feature_classification(),
        "feature_flags": flags,
        "alpha_safe_defaults": alpha_safe_defaults(),
        "observability": alpha_observability(root, diagnostics=diagnostics),
        "support_tooling": support_tooling_catalog(root),
        "release_channels": release_channels(),
        "handoff_summary": alpha_handoff_summary(),
        "telemetry_controls": telemetry_controls(root, flags=flags),
        "simulation_plan": alpha_simulations(root),
        "highest_risk_systems": _highest_risk_systems(checklist, diagnostics),
        "recommended_alpha_scope": recommended_alpha_scope(checklist, flags),
        "state_files": {
            "readiness": str(ProjectMemory(root).root / ALPHA_READINESS_FILE),
            "feature_flags": str(ProjectMemory(root).root / ALPHA_FEATURE_FLAGS_FILE),
            "feedback": str(ProjectMemory(root).root / ALPHA_FEEDBACK_FILE),
            "diagnostics_dir": str(ProjectMemory(root).root / ALPHA_DIAGNOSTICS_DIR),
        },
    }
    if persist:
        memory = ProjectMemory(root)
        memory.write_json(ALPHA_READINESS_FILE, state)
        state["state_files"]["readiness_persisted"] = (memory.root / ALPHA_READINESS_FILE).is_file()
    return state


def feature_classification() -> dict[str, Any]:
    return {
        "stable_features": [
            "Core contract envelope",
            "local workspace scan",
            "checkpoint creation/list/restore",
            "validation command discovery",
            "local model registry visibility",
            "security/privacy status",
            "release compatibility checks",
        ],
        "beta_features": [
            "Auralith Engineering Workspace",
            "quality gates and evaluation reports",
            "onboarding wizard",
            "Website/Core delegation fallback",
            "Desktop/IDE Core-first runtime surfaces",
            "project knowledge graph",
            "dogfooding friction tracking",
        ],
        "experimental_features": [
            "multi-agent orchestration",
            "engineering execution pipelines",
            "deployment intelligence",
            "system optimization experiments",
            "personal intelligence",
            "real-time terminal orchestration",
        ],
        "hidden_internal_systems": [
            "unrestricted autonomous execution",
            "provider credential internals",
            "raw workflow mutation endpoints",
            "internal dogfooding notes",
            "debug-only route experiments",
        ],
        "disabled_by_default_systems": [
            "distributed remote execution",
            "high-risk plugin enablement",
            "experimental workflow labs",
            "dev release channel",
            "external telemetry upload",
            "production deployment actions",
        ],
    }


def alpha_handoff_summary() -> dict[str, Any]:
    classification = feature_classification()
    return {
        "phase": "phase35_alpha_readiness_polish",
        "default_channel": "beta",
        "feature_tiers": [
            {
                "id": "stable_alpha",
                "label": "Stable Alpha",
                "default_visibility": "visible",
                "tester_copy": "Core contracts, local workspace scan, checkpoints, validation, rollback, local models, release compatibility, and diagnostics export.",
                "features": classification["stable_features"],
            },
            {
                "id": "beta",
                "label": "Beta",
                "default_visibility": "visible_with_label",
                "tester_copy": "Engineering Workspace, onboarding, quality gates, Core delegation fallback, client runtime surfaces, knowledge graph, and dogfooding feedback.",
                "features": classification["beta_features"],
            },
            {
                "id": "experimental",
                "label": "Experimental",
                "default_visibility": "opt_in",
                "tester_copy": "Labs and advanced runtime systems require an explicit tester cohort and should not appear in the default path.",
                "features": classification["experimental_features"],
            },
            {
                "id": "internal_only",
                "label": "Internal Only",
                "default_visibility": "hidden",
                "tester_copy": "Credential internals, unrestricted autonomy, raw mutation surfaces, and debug route experiments stay out of tester handoff.",
                "features": classification["hidden_internal_systems"],
            },
        ],
        "default_alpha_path": [
            {"id": "verify_checksums", "label": "Verify package checksums", "required": True, "evidence": "release/version-manifest.json"},
            {"id": "launch_core", "label": "Launch Aegis Core locally", "required": True, "evidence": "GET /v1/health"},
            {"id": "choose_workspace", "label": "Choose a disposable or backed-up workspace", "required": True, "evidence": "onboarding workspace diagnostics"},
            {"id": "provider_setup", "label": "Keep local-only or link providers through the credential store", "required": True, "evidence": "provider route-safety status"},
            {"id": "local_model_setup", "label": "Confirm local model availability or show recovery", "required": True, "evidence": "model diagnostics"},
            {"id": "validate_only_first_workflow", "label": "Run the guided first workflow in validate-only mode", "required": True, "evidence": "POST /v1/onboarding/first-workflow"},
            {"id": "checkpoint_rollback", "label": "Confirm checkpoint and rollback visibility", "required": True, "evidence": "checkpoint and update rollback state"},
            {"id": "diagnostics_export", "label": "Export local redacted diagnostics", "required": True, "evidence": "POST /v1/alpha/diagnostics/export"},
            {"id": "feedback_capture", "label": "Capture friction using local feedback categories", "required": True, "evidence": "POST /v1/alpha/feedback"},
        ],
        "hidden_by_default": classification["disabled_by_default_systems"] + classification["hidden_internal_systems"],
        "tester_handoff": {
            "required_docs": [
                "docs/EXTERNAL_ALPHA_RELEASE_NOTES.md",
                "docs/FIRST_RUN_ONBOARDING.md",
                "docs/CONTROLLED_EXTERNAL_ALPHA.md",
                "docs/DISTRIBUTION_INSTALLER_UPDATE_EVIDENCE.md",
                "KNOWN_UNSTABLE_SURFACES.md",
            ],
            "required_evidence": [
                ".aegis/alpha-evidence",
                ".aegis/release-notes-limitations",
                ".aegis/distribution-update",
                ".aegis/evidence-ledger",
            ],
        },
        "broad_alpha_blockers": [
            "live smoke gates still skipped in the latest full validation matrix",
            "signed installer and code-signing decision still deferred",
            "worktree commit scope still mixed",
            "live provider/local model health checks still need a fresh pass",
            "client open-logs and diagnostics affordances need visible UI polish",
        ],
        "support_handoff": {
            "diagnostics": "local-only, redacted, manually attachable",
            "rollback": "visible before tester mutation workflows",
            "memory_reset": "workspace .aegis state is inspectable and disposable-workspace testing is recommended",
            "telemetry": "external upload disabled by default",
        },
    }


def alpha_feature_flags(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    stored = _read_json(ProjectMemory(root).root / ALPHA_FEATURE_FLAGS_FILE, {})
    overrides = stored.get("overrides", {}) if isinstance(stored, dict) and isinstance(stored.get("overrides"), dict) else {}
    flags = {}
    for flag_id, definition in ALPHA_FEATURE_FLAGS.items():
        value = bool(overrides.get(flag_id, definition["default"]))
        if definition.get("alpha_locked") and definition["default"] is True:
            value = True
        if definition.get("alpha_locked") and definition["default"] is False:
            value = False
        flags[flag_id] = {
            "id": flag_id,
            "enabled": value,
            "default": bool(definition["default"]),
            "category": definition["category"],
            "alpha_locked": bool(definition["alpha_locked"]),
            "description": definition["description"],
        }
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "release_channel": str(stored.get("release_channel") or "beta") if isinstance(stored, dict) else "beta",
        "flags": flags,
        "overrides": {key: flags[key]["enabled"] for key in flags if flags[key]["enabled"] != flags[key]["default"]},
        "policy": {
            "safe_defaults": True,
            "locked_flags_ignore_unsafe_overrides": True,
            "high_risk_requires_manual_approval": True,
        },
        "state_path": str(ProjectMemory(root).root / ALPHA_FEATURE_FLAGS_FILE),
    }


def update_feature_flags(
    workspace: str | Path,
    *,
    overrides: dict[str, Any] | None = None,
    release_channel: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    clean_channel = _release_channel(release_channel or "beta")
    clean_overrides: dict[str, bool] = {}
    for key, value in (overrides or {}).items():
        flag_id = str(key).strip()
        if flag_id not in ALPHA_FEATURE_FLAGS:
            continue
        definition = ALPHA_FEATURE_FLAGS[flag_id]
        requested = bool(value)
        if definition.get("alpha_locked"):
            requested = bool(definition["default"])
        clean_overrides[flag_id] = requested
    state = {
        "updated_at": utc_now(),
        "release_channel": clean_channel,
        "overrides": clean_overrides,
        "reason": scrub(reason or ""),
    }
    memory = ProjectMemory(root)
    memory.write_json(ALPHA_FEATURE_FLAGS_FILE, state)
    flags = alpha_feature_flags(root)
    flags["requested_overrides"] = clean_overrides
    flags["persisted"] = (memory.root / ALPHA_FEATURE_FLAGS_FILE).is_file()
    return flags


def runtime_diagnostics_snapshot(workspace: str | Path, *, include_replay: bool = True) -> dict[str, Any]:
    root = Path(workspace).resolve()
    snapshot = {
        "workspace": str(root),
        "generated_at": utc_now(),
        "privacy": "local-first diagnostics; provider secrets and raw prompts are not included",
        "security": _safe_call("security", lambda: security_status(root), {}),
        "release": {
            "manifest": _safe_call("release_manifest", lambda: release.release_manifest(root), {}),
            "migrations": _safe_call("migration_status", lambda: release.migration_status(root), {}),
            "update_plan_core": _safe_call("update_plan", lambda: release.update_plan("aegis-core"), {}),
        },
        "onboarding": _safe_call("onboarding", lambda: onboarding.onboarding_status(root), {}),
        "plugins": _safe_call("plugins", lambda: plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True), {}),
        "plugin_failures": _safe_call("plugin_observability", lambda: plugin_runtime.plugin_observability(root), {}),
        "distributed_runtime": _safe_call("distributed_runtime", lambda: distributed_runtime.runtime_dashboard(root, include_audit=False), {}),
        "runtime_interaction": _safe_call("runtime_interaction", lambda: runtime_interaction.compact_summary(root), {}),
        "validation": _safe_call("validation", lambda: validation_summary(root), {}),
        "quality_gates": _safe_call("quality_gates", lambda: quality_gate_dashboard(root), {}),
        "workflows": _safe_call("workflows", lambda: workflow_statistics(root), {}),
        "dogfooding": _safe_call("dogfooding", lambda: dogfooding.dogfooding_dashboard(root, limit=100, persist=False), {}),
    }
    if include_replay:
        snapshot["workflow_replay"] = _safe_call("workflow_replay", lambda: runtime_interaction.execution_replay(root, limit=150), {})
    snapshot["summary"] = _diagnostics_summary(snapshot)
    return _redact_json(snapshot)


def export_diagnostics_bundle(
    workspace: str | Path,
    *,
    include_replay: bool = True,
    include_plugins: bool = True,
    include_validation: bool = True,
    reason: str = "",
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    snapshot = runtime_diagnostics_snapshot(root, include_replay=include_replay)
    if not include_plugins:
        snapshot.pop("plugins", None)
        snapshot.pop("plugin_failures", None)
    if not include_validation:
        snapshot.pop("validation", None)
        snapshot.pop("quality_gates", None)
    snapshot["export"] = {
        "id": f"alpha-diagnostics-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "reason": scrub(reason or ""),
        "local_only": True,
        "external_upload": False,
    }
    memory = ProjectMemory(root)
    path = memory.root / ALPHA_DIAGNOSTICS_DIR / f"{snapshot['export']['id']}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        persisted = True
    except OSError:
        persisted = False
    return {
        "workspace": str(root),
        "bundle": snapshot,
        "path": str(path),
        "persisted": persisted,
        "privacy": {
            "local_only": True,
            "secrets_redacted": True,
            "external_upload": False,
            "user_controls": ["inspect", "delete", "export", "attach manually"],
        },
    }


def record_feedback(
    workspace: str | Path,
    *,
    category: str = "other",
    severity: str = "medium",
    message: str = "",
    client_type: str = "unknown",
    workflow_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    clean_category = category if category in FEEDBACK_CATEGORIES else "other"
    clean_severity = severity if severity in {"low", "medium", "high", "critical"} else "medium"
    record = {
        "id": f"alpha-feedback-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "category": clean_category,
        "severity": clean_severity,
        "message": redact_inline(message or "")[:1000],
        "client_type": scrub(client_type or "unknown"),
        "workflow_id": scrub(workflow_id or ""),
        "metadata": _redact_json(metadata or {}),
    }
    _append_jsonl(ProjectMemory(root).root / ALPHA_FEEDBACK_FILE, record)
    return {"workspace": str(root), "feedback": record, "summary": feedback_summary(root)}


def feedback_summary(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = Path(workspace).resolve()
    events = _read_jsonl(ProjectMemory(root).root / ALPHA_FEEDBACK_FILE)[-MAX_FEEDBACK:]
    category_counts = Counter(str(item.get("category") or "other") for item in events)
    severity_counts = Counter(str(item.get("severity") or "medium") for item in events)
    return {
        "workspace": str(root),
        "categories": sorted(FEEDBACK_CATEGORIES),
        "event_count": len(events),
        "category_counts": dict(category_counts),
        "severity_counts": dict(severity_counts),
        "recent_feedback": list(reversed(events[-max(1, min(250, int(limit))):])),
        "privacy": "Feedback is stored locally under .aegis with messages and metadata redacted.",
    }


def alpha_observability(workspace: str | Path, *, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve()
    data = diagnostics or runtime_diagnostics_snapshot(root, include_replay=False)
    workflows = data.get("workflows", {}) if isinstance(data.get("workflows"), dict) else {}
    quality = data.get("quality_gates", {}) if isinstance(data.get("quality_gates"), dict) else {}
    plugins = data.get("plugin_failures", {}) if isinstance(data.get("plugin_failures"), dict) else {}
    onboarding_data = data.get("onboarding", {}) if isinstance(data.get("onboarding"), dict) else {}
    dogfood = data.get("dogfooding", {}) if isinstance(data.get("dogfooding"), dict) else {}
    dog_confidence = dogfood.get("confidence", {}) if isinstance(dogfood.get("confidence"), dict) else {}
    feedback = feedback_summary(root, limit=25)
    workflow_status = workflows.get("status_counts", {}) if isinstance(workflows.get("status_counts"), dict) else {}
    quality_stats = quality.get("statistics", {}) if isinstance(quality.get("statistics"), dict) else {}
    return {
        "workspace": str(root),
        "crash_frequency": _count_runtime_crash_signals(data),
        "failed_workflows": int(workflow_status.get("failed", 0) or 0),
        "plugin_failures": int(plugins.get("failure_count", 0) or 0),
        "onboarding_failures": _onboarding_failure_count(onboarding_data),
        "rollback_frequency": dog_confidence.get("metrics", {}).get("rollback_recovery_success") if isinstance(dog_confidence.get("metrics"), dict) else None,
        "validation_failures": int(quality_stats.get("blocked_count", 0) or quality_stats.get("failed_count", 0) or 0),
        "update_failures": _count_update_failures(data),
        "feedback_count": int(feedback.get("event_count") or 0),
        "feedback_hotspots": feedback.get("category_counts", {}),
        "dogfooding_confidence": dog_confidence,
    }


def alpha_safe_defaults() -> dict[str, Any]:
    return {
        "privacy_mode": "local-only preferred",
        "approval_required": True,
        "orchestration_mode": "safe_assisted",
        "validation_before_apply": True,
        "checkpoint_before_apply": True,
        "rollback_visible": True,
        "cloud_routing": "disabled unless explicitly enabled by the tester",
        "distributed_runtime": "disabled by default",
        "high_risk_plugins": "blocked by default",
        "telemetry": "local-only diagnostics; no automatic external upload",
    }


def release_channels() -> dict[str, Any]:
    return {
        "channels": [
            {"id": "stable", "label": "Stable", "audience": "post-alpha users", "policy": "security fixes and proven workflows only"},
            {"id": "beta", "label": "Beta", "audience": "controlled external alpha", "policy": "default alpha channel with conservative feature flags"},
            {"id": "experimental", "label": "Experimental", "audience": "trusted technical testers", "policy": "opt-in labs and distributed/plugin cohorts"},
            {"id": "dev", "label": "Dev", "audience": "internal maintainers", "policy": "hidden unless dev_release_channel is enabled"},
        ],
        "default_alpha_channel": "beta",
        "promotion_rules": [
            "No required readiness blockers.",
            "Diagnostics export works locally.",
            "Rollback and validation flows are visible.",
            "Known limitations are documented.",
        ],
    }


def telemetry_controls(workspace: str | Path, *, flags: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve()
    flag_data = flags or alpha_feature_flags(root)
    flag_map = flag_data.get("flags", {}) if isinstance(flag_data.get("flags"), dict) else {}
    return {
        "workspace": str(root),
        "telemetry_enabled": bool(flag_map.get("telemetry_enabled", {}).get("enabled", False)) if isinstance(flag_map.get("telemetry_enabled"), dict) else False,
        "local_only_diagnostics": bool(flag_map.get("local_only_diagnostics", {}).get("enabled", True)) if isinstance(flag_map.get("local_only_diagnostics"), dict) else True,
        "external_upload": False,
        "inspectable_files": [
            str(ProjectMemory(root).root / ALPHA_FEEDBACK_FILE),
            str(ProjectMemory(root).root / ALPHA_DIAGNOSTICS_DIR),
            str(ProjectMemory(root).root / ALPHA_READINESS_FILE),
        ],
        "user_controls": ["disable", "inspect", "export", "delete local files manually", "choose local-only diagnostics"],
    }


def alpha_simulations(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    return {
        "workspace": str(root),
        "scenarios": [
            _scenario("clean_machine_install", "Install from scratch with no prior .aegis state.", ["installer", "onboarding", "local-only defaults"]),
            _scenario("low_resource_system", "Validate startup, scan, and workflows on constrained CPU/RAM.", ["performance", "indexing", "timeouts"]),
            _scenario("plugin_heavy_system", "Load many plugin manifests and verify isolation/permission warnings.", ["plugin loading", "compatibility", "failure isolation"]),
            _scenario("distributed_runtime", "Register local and trusted nodes, then simulate disconnect/recovery.", ["node registration", "fallback", "trust"]),
            _scenario("long_workflow", "Run multi-step feature/validation/repair workflow with pause/resume.", ["orchestration", "workflow replay", "rollback"]),
            _scenario("offline_workflow", "Run local-only with Core available and cloud/providers unavailable.", ["privacy", "fallback", "validation"]),
            _scenario("interrupted_update", "Simulate checksum/apply failure and verify rollback plan.", ["update", "recovery", "safe mode"]),
            _scenario("rollback_failure", "Simulate a failed rollback and verify diagnostics plus manual recovery guidance.", ["rollback", "diagnostics", "support"]),
            _scenario("stale_plugin_state", "Start with stale or incompatible plugin state and verify safe disablement.", ["plugins", "compatibility", "recovery"]),
            _scenario("incompatible_versions", "Run clients against incompatible Core/schema versions and verify compatibility blocking.", ["release channels", "compatibility", "fallback"]),
            _scenario("partial_runtime_failure", "Stop one runtime component during a workflow and verify fallback/recovery state.", ["runtime health", "workflow replay", "fallback"]),
        ],
        "validation_commands": [
            "Core alpha readiness tests",
            "plugin isolation tests",
            "distributed runtime tests",
            "onboarding tests",
            "release update/rollback tests",
            "orchestration stress tests",
        ],
    }


def support_tooling_catalog(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    return {
        "diagnostics_export": {"endpoint": "/v1/alpha/diagnostics/export", "local_only": True},
        "environment_validation": {"endpoint": "/v1/alpha/readiness", "includes": ["onboarding", "security", "release", "validation"]},
        "runtime_health_summary": {"endpoint": "/v1/alpha/diagnostics", "includes": ["runtime interaction", "workflows", "distributed runtime"]},
        "plugin_compatibility_report": {"endpoint": "/v1/alpha/diagnostics", "includes": ["plugin dashboard", "plugin observability"]},
        "workflow_trace_export": {"endpoint": "/v1/alpha/diagnostics/export", "includes": ["workflow replay", "terminal events", "approval history"]},
        "feedback_capture": {"endpoint": "/v1/alpha/feedback", "categories": sorted(FEEDBACK_CATEGORIES)},
        "workspace": str(root),
    }


def recommended_alpha_scope(checklist: list[dict[str, Any]], flags: dict[str, Any]) -> dict[str, Any]:
    blocked = [item["id"] for item in checklist if item["status"] == "blocked"]
    scope = [
        "local-only onboarding",
        "workspace scan and architecture explanation",
        "Engineering Workspace dashboard",
        "proposal/checkpoint/validation/rollback workflows",
        "manifest-only plugin discovery",
        "local diagnostics export",
        "guided feedback capture",
    ]
    exclusions = [
        "mass public launch",
        "production deployment execution",
        "external telemetry upload",
        "unrestricted autonomy",
        "high-risk plugin execution by default",
        "remote distributed execution unless in a dedicated cohort",
    ]
    return {
        "recommended": "start_blocked_items_first" if blocked else "small_trusted_alpha",
        "tester_count": "3-8 trusted technical users",
        "include": scope,
        "exclude": exclusions,
        "blocked_items": blocked,
    }


def _readiness_checklist(root: Path, diagnostics: dict[str, Any], flags: dict[str, Any]) -> list[dict[str, Any]]:
    release_data = diagnostics.get("release", {}) if isinstance(diagnostics.get("release"), dict) else {}
    onboarding_data = diagnostics.get("onboarding", {}) if isinstance(diagnostics.get("onboarding"), dict) else {}
    plugins = diagnostics.get("plugins", {}) if isinstance(diagnostics.get("plugins"), dict) else {}
    distributed = diagnostics.get("distributed_runtime", {}) if isinstance(diagnostics.get("distributed_runtime"), dict) else {}
    validation = diagnostics.get("validation", {}) if isinstance(diagnostics.get("validation"), dict) else {}
    workflows = diagnostics.get("workflows", {}) if isinstance(diagnostics.get("workflows"), dict) else {}
    security = diagnostics.get("security", {}) if isinstance(diagnostics.get("security"), dict) else {}
    quality = diagnostics.get("quality_gates", {}) if isinstance(diagnostics.get("quality_gates"), dict) else {}
    plugin_diagnostics = plugins.get("diagnostics", {}) if isinstance(plugins.get("diagnostics"), dict) else {}
    distributed_observability = distributed.get("observability", {}) if isinstance(distributed.get("observability"), dict) else {}
    update_plan = release_data.get("update_plan_core", {}) if isinstance(release_data.get("update_plan_core"), dict) else {}
    migrations = release_data.get("migrations", {}) if isinstance(release_data.get("migrations"), dict) else {}
    flags_map = flags.get("flags", {}) if isinstance(flags.get("flags"), dict) else {}
    local_api = security.get("local_api", {}) if isinstance(security.get("local_api"), dict) else {}
    privacy = security.get("privacy", {}) if isinstance(security.get("privacy"), dict) else {}
    quality_stats = quality.get("statistics", {}) if isinstance(quality.get("statistics"), dict) else {}
    return [
        _check("installers", "Installers and package manifest", "warning" if _manifest_missing_artifacts(release_data.get("manifest", {})) else "ready", "Release manifest should point at alpha artifacts.", True),
        _check("update_flow", "Update flow", "blocked" if update_plan.get("status") == "blocked" else "ready", "; ".join(update_plan.get("blockers", []) or []) or "Update plan is inspectable.", True),
        _check("rollback_flow", "Rollback flow", "ready" if update_plan.get("rollback", {}).get("available") else "blocked", "Update rollback plan is available." if update_plan.get("rollback", {}).get("available") else "Rollback plan missing.", True),
        _check("onboarding", "Onboarding", "ready" if onboarding_data.get("completed") else "warning", f"Current step: {onboarding_data.get('current_step', 'unknown')}.", True),
        _check("plugin_loading", "Plugin loading", "blocked" if plugin_diagnostics.get("status") == "error" else "ready" if flags_map.get("plugin_loading", {}).get("enabled", True) else "warning", f"Plugin diagnostics: {plugin_diagnostics.get('status', 'unknown')}.", True),
        _check("distributed_runtime", "Distributed runtime stability", "ready" if not flags_map.get("distributed_runtime", {}).get("enabled", False) else "warning", f"Nodes: {(distributed_observability.get('nodes') or {}).get('total', 0) if isinstance(distributed_observability.get('nodes'), dict) else 0}. Disabled by default is alpha-safe.", False),
        _check("memory_persistence", "Memory persistence", _memory_persistence_status(root), "Workspace .aegis state must be writable for alpha diagnostics.", True),
        _check("orchestration_reliability", "Orchestration reliability", "warning" if int(workflows.get("active_workflow_count") or 0) > 10 else "ready", f"Workflow count: {workflows.get('workflow_count', 0)}.", True),
        _check("validation_workflows", "Validation workflows", "ready" if validation.get("commands") else "warning", f"Detected commands: {len(validation.get('commands', []) if isinstance(validation.get('commands'), list) else [])}.", True),
        _check("crash_recovery", "Crash recovery", "ready" if runtime_interaction.compact_summary(root).get("status") == "ready" else "warning", "Runtime diagnostics snapshot and replay export are available.", True),
        _check("security_privacy", "Security and privacy", "warning" if not local_api.get("token_enforced") else "ready", local_api.get("token_warning") or f"Privacy mode: {privacy.get('mode', 'unknown')}.", True),
        _check("quality_gates", "Quality gates", "warning" if quality_stats.get("latest_status") in {"blocked", "failed"} else "ready", f"Latest quality status: {quality_stats.get('latest_status', 'not_run')}.", True),
        _check("release_migrations", "Release migrations", "warning" if migrations.get("pending") else "ready", f"Pending migrations: {len(migrations.get('pending', []) if isinstance(migrations.get('pending'), list) else [])}.", True),
    ]


def _memory_persistence_status(root: Path) -> str:
    memory = ProjectMemory(root)
    probe = memory.root / "alpha-persistence-probe.json"
    memory.write_json("alpha-persistence-probe.json", {"checked_at": utc_now(), "purpose": "controlled alpha readiness"})
    return "ready" if probe.is_file() else "blocked"


def _check(check_id: str, title: str, status: str, evidence: str, required: bool) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status if status in {"ready", "warning", "blocked"} else "warning",
        "required": bool(required),
        "evidence": scrub(evidence),
    }


def _readiness_score(checklist: list[dict[str, Any]]) -> int:
    if not checklist:
        return 0
    score = 0
    for item in checklist:
        score += 100 if item["status"] == "ready" else 55 if item["status"] == "warning" else 0
    return round(score / len(checklist))


def _highest_risk_systems(checklist: list[dict[str, Any]], diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    risks = [
        {"system": item["title"], "reason": item["evidence"], "severity": "high" if item["status"] == "blocked" else "medium"}
        for item in checklist
        if item["status"] in {"blocked", "warning"}
    ]
    plugins = diagnostics.get("plugin_failures", {}) if isinstance(diagnostics.get("plugin_failures"), dict) else {}
    if int(plugins.get("failure_count") or 0):
        risks.append({"system": "Plugin runtime", "reason": "Plugin observability contains failures.", "severity": "medium"})
    return risks[:10]


def _manifest_missing_artifacts(manifest: dict[str, Any]) -> bool:
    components = manifest.get("components", {}) if isinstance(manifest.get("components"), dict) else {}
    if not components:
        return True
    for component in components.values():
        package = component.get("package", {}) if isinstance(component, dict) else {}
        if not package.get("artifact") or not package.get("path"):
            return True
    return False


def _diagnostics_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    plugins = snapshot.get("plugin_failures", {}) if isinstance(snapshot.get("plugin_failures"), dict) else {}
    workflows = snapshot.get("workflows", {}) if isinstance(snapshot.get("workflows"), dict) else {}
    validation = snapshot.get("validation", {}) if isinstance(snapshot.get("validation"), dict) else {}
    return {
        "plugin_failure_count": int(plugins.get("failure_count") or 0),
        "workflow_count": int(workflows.get("workflow_count") or 0),
        "active_workflow_count": int(workflows.get("active_workflow_count") or 0),
        "validation_command_count": len(validation.get("commands", []) if isinstance(validation.get("commands"), list) else []),
    }


def _count_runtime_crash_signals(snapshot: dict[str, Any]) -> int:
    text = json.dumps(snapshot, sort_keys=True).lower()
    return sum(text.count(term) for term in ["traceback", "crash", "exception"])


def _onboarding_failure_count(onboarding_data: dict[str, Any]) -> int:
    recovery = onboarding_data.get("recovery", []) if isinstance(onboarding_data.get("recovery"), list) else []
    steps = onboarding_data.get("steps", []) if isinstance(onboarding_data.get("steps"), list) else []
    return sum(1 for item in recovery if item.get("status") in {"blocked", "warning"}) + sum(1 for item in steps if item.get("status") == "blocked")


def _count_update_failures(snapshot: dict[str, Any]) -> int:
    release_data = snapshot.get("release", {}) if isinstance(snapshot.get("release"), dict) else {}
    plan = release_data.get("update_plan_core", {}) if isinstance(release_data.get("update_plan_core"), dict) else {}
    return len(plan.get("blockers", []) if isinstance(plan.get("blockers"), list) else [])


def _release_channel(channel: str) -> str:
    clean = str(channel or "beta").strip().lower().replace("_", "-")
    return clean if clean in {"stable", "beta", "experimental", "dev"} else "beta"


def _scenario(scenario_id: str, summary: str, validates: list[str]) -> dict[str, Any]:
    return {"id": scenario_id, "summary": summary, "validates": validates, "status": "planned"}


def _safe_call(label: str, func: Any, default: Any) -> Any:
    try:
        return func()
    except Exception as exc:
        if isinstance(default, dict):
            return {"status": "unavailable", "error": f"{label}: {scrub(str(exc))}", **default}
        return default


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        return


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            redact_inline(str(key))[:120]: ("[redacted]" if _secret_key(key) else _redact_json(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(item) for item in value[:500]]
    if isinstance(value, str):
        return redact_inline(value)[:5000]
    return value


def _secret_key(key: Any) -> bool:
    text = str(key).lower()
    return any(term in text for term in ["secret", "token", "password", "api_key", "authorization", "credential"])
