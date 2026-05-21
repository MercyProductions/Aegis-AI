from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from . import dogfooding, plugin_runtime, product_identity, quality_gates, release, runtime_interaction
from .contracts import CONTRACTS
from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .platform_foundation import (
    ecosystem_dependency_management,
    ecosystem_tooling,
    platform_governance,
    platform_health_analytics,
    platform_sustainability,
    release_engineering_status,
    validate_platform_compatibility,
)
from .validation import validation_summary
from .workflow_runtime import workflow_statistics


ECOSYSTEM_SCHEMA_VERSION = "2026.05.12"
ECOSYSTEM_MATURITY_FILE = "ecosystem-maturity.json"
ECOSYSTEM_OBSERVABILITY_FILE = "ecosystem-observability.json"


def ecosystem_strategy() -> dict[str, Any]:
    return {
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "core_audience": [
            {
                "segment": "solo_local_engineers",
                "priority": "primary",
                "need": "Private, project-aware engineering workflows with safe edit/apply/rollback.",
            },
            {
                "segment": "power_user_engineers",
                "priority": "primary",
                "need": "Fast, inspectable orchestration, validation, repair, and roadmap execution.",
            },
            {
                "segment": "trusted_small_teams",
                "priority": "secondary",
                "need": "Local-first workflow supervision, shared compatibility rules, and optional trusted workers.",
            },
            {
                "segment": "plugin_authors",
                "priority": "ecosystem",
                "need": "Clear manifests, permission scopes, compatibility badges, test tools, and stable hooks.",
            },
        ],
        "plugin_ecosystem_direction": [
            "Curated local-first plugins before a broad marketplace.",
            "Manifest-only validation and quality scoring before arbitrary code execution.",
            "Permission transparency, compatibility badges, and review checklists on every plugin surface.",
            "Reference plugins for validators, analyzers, providers, observability widgets, and workflow helpers.",
        ],
        "contributor_strategy": [
            "Make subsystem ownership explicit before accepting large changes.",
            "Require docs, tests, compatibility notes, and rollback behavior for user-visible features.",
            "Prefer small contract-preserving slices over broad rewrites.",
            "Keep experimental work behind stable feature flags and clear release channels.",
        ],
        "positioning": {
            "enthusiast": "A powerful local-first engineering workspace for people who want control and transparency.",
            "enterprise": "A private engineering runtime foundation with inspectable workflows, compatibility rules, and optional trusted-node scaling.",
            "stance": "Start enthusiast/power-user first; enterprise posture depends on signed releases, stronger policy packs, audit export, and support commitments.",
        },
        "local_first_privacy_positioning": [
            "Workspace state stays under .aegis by default.",
            "Local-only mode must remain obvious and viable.",
            "Cloud provider use must explain provider, model, privacy risk, and fallback chain.",
            "Diagnostics and telemetry are inspectable and local-first unless a user explicitly exports them.",
        ],
        "long_term_roadmap_themes": [
            "Workflow excellence over raw feature count.",
            "Plugin ecosystem quality over plugin quantity.",
            "Stable Core contracts before client-specific innovation.",
            "Trust and recovery as product differentiators.",
            "Large-project performance and long-session reliability.",
        ],
    }


def workflow_excellence(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    catalog = product_identity.workflow_catalog()
    workflow_stats = _safe_call("workflow_statistics", lambda: workflow_statistics(root), {})
    validation = _safe_call("validation", lambda: validation_summary(root), {})
    quality = _safe_call("quality_gates", lambda: quality_gates.quality_gate_dashboard(root, limit=50), {})
    workflows = []
    for item in catalog.get("workflows", []):
        if not isinstance(item, dict):
            continue
        workflows.append(_workflow_score(item, workflow_stats, validation, quality))
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "priorities": ["speed", "trust", "clarity", "low friction", "predictability"],
        "workflows": workflows,
        "workflow_statistics": workflow_stats,
        "validation_summary": validation,
        "quality_summary": {
            "latest_status": ((quality.get("statistics") or {}).get("latest_status") if isinstance(quality.get("statistics"), dict) else "unknown"),
            "recent_runs": len(quality.get("recent_runs", []) if isinstance(quality.get("recent_runs"), list) else []),
            "recent_reports": len(quality.get("recent_reports", []) if isinstance(quality.get("recent_reports"), list) else []),
        },
        "improvement_backlog": _workflow_backlog(workflows),
    }


def plugin_ecosystem_quality(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    dashboard = _safe_call("plugin_dashboard", lambda: plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True), {})
    plugins = dashboard.get("plugins", []) if isinstance(dashboard.get("plugins"), list) else []
    scored = [_score_plugin(plugin) for plugin in plugins if isinstance(plugin, dict)]
    marketplace = {
        "status": "foundation",
        "listing_source": "workspace plugin manifests plus bundled reference manifests",
        "required_listing_fields": ["id", "name", "version", "category", "description", "permission_scopes", "runtime_compatibility"],
        "not_yet_public": True,
    }
    score_values = [item["quality_score"] for item in scored]
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "marketplace_foundation": marketplace,
        "compatibility_badges": _compatibility_badges(scored),
        "permission_transparency": plugin_runtime.PERMISSION_SCOPES,
        "plugins": scored,
        "quality_summary": {
            "plugin_count": len(scored),
            "average_score": round(sum(score_values) / len(score_values), 2) if score_values else 0,
            "high_quality_count": sum(1 for score in score_values if score >= 85),
            "review_required_count": sum(1 for item in scored if item["review_required"]),
            "high_risk_count": sum(1 for item in scored if item["risk_level"] == "high"),
        },
        "review_tools": [
            {"id": "manifest_validation", "source": "plugin_runtime.validate_manifest"},
            {"id": "permission_review", "source": "plugin_runtime.PERMISSION_SCOPES"},
            {"id": "compatibility_validation", "source": "/v1/platform/compatibility/validate"},
            {"id": "failure_isolation", "source": "plugin observability"},
            {"id": "quality_score", "source": "ecosystem maturity plugin scoring"},
        ],
    }


def api_stability() -> dict[str, Any]:
    stability_counts = Counter(descriptor.stability for descriptor in CONTRACTS.values())
    stable = sorted(kind for kind, descriptor in CONTRACTS.items() if descriptor.stability == "stable")
    experimental = sorted(kind for kind, descriptor in CONTRACTS.items() if descriptor.stability == "experimental")
    deprecated = sorted(kind for kind, descriptor in CONTRACTS.items() if descriptor.stability == "deprecated")
    return {
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stable_apis": stable,
        "experimental_apis": experimental,
        "deprecated_apis": deprecated,
        "stability_counts": dict(stability_counts),
        "stable_workflow_schemas": [
            "workspace scan",
            "roadmap generation",
            "change proposal",
            "checkpoint",
            "validation run",
            "rollback",
        ],
        "stable_orchestration_contracts": [
            "workflow.created",
            "workflow.dashboard",
            "workflow.step",
            "workflow.statistics",
        ],
        "stable_plugin_contracts": [
            "plugin dashboard envelope",
            "manifest metadata",
            "permission scopes",
            "tool input/output schema",
            "runtime compatibility metadata",
        ],
        "compatibility_guarantees": platform_governance().get("api_stability_guarantees", []),
        "stability_rule": "Stable APIs require contract tests, docs, migration notes, fallback behavior, and at least one release-candidate validation pass.",
    }


def contributor_ecosystem(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    tooling = ecosystem_tooling(root)
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "contributor_guides": [
            "docs/LONG_TERM_PLATFORM_FOUNDATION.md",
            "docs/PLUGIN_ECOSYSTEM.md",
            "docs/PLATFORM_STABILIZATION_AND_PRODUCTION_READINESS.md",
            "docs/SECURITY_PRIVACY_TRUST.md",
            "docs/AURALITH_OS_PRODUCT_IDENTITY.md",
        ],
        "plugin_sdk_docs": tooling.get("plugin_sdk", {}),
        "subsystem_ownership_docs": "GET /v1/platform/ownership",
        "debugging_guides": tooling.get("developer_infrastructure", {}).get("debugging_guides", []),
        "architecture_maps": [
            "docs/ARCHITECTURE.md",
            ".aegis/architecture-map.md",
            "GET /v1/engineering-workspace/map",
        ],
        "sample_plugins_and_tools": [
            "custom validator plugin",
            "architecture analyzer plugin",
            "local provider adapter plugin",
            "roadmap enhancement plugin",
            "observability widget plugin",
        ],
        "contribution_rules": [
            "Every user-visible feature needs tests, docs, compatibility notes, and rollback/recovery behavior.",
            "Plugin changes must declare permission scope impact.",
            "Core contract changes must be backward-compatible or explicitly deprecated.",
            "Experimental features stay hidden or opt-in until maturity gates pass.",
        ],
    }


def platform_reputation(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    release_status = release_engineering_status(root)
    compatibility = validate_platform_compatibility(root, include_plugins=True, persist=False)
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "release_quality_standards": [
            "Focused Core tests pass.",
            "Release compatibility matrix is generated.",
            "Update plan includes checksum and rollback checks.",
            "Known limitations are documented.",
            "Core-offline client behavior is smoke-tested.",
        ],
        "compatibility_guarantees": platform_governance().get("versioning_policy", {}).get("compatibility_windows", {}),
        "migration_guarantees": platform_governance().get("migration_policy", {}).get("principles", []),
        "rollback_reliability": release_status.get("rollback_requirements", []),
        "security_review_standards": platform_governance().get("security_review_required_for", []),
        "current_reputation_signals": {
            "compatibility_status": compatibility.get("overall_status"),
            "compatibility_blockers": compatibility.get("summary", {}).get("blocked"),
            "release_component_count": len(release_status.get("compatibility_matrix", [])),
            "release_verification": release_status.get("release_verification", {}),
        },
    }


def release_cadence() -> dict[str, Any]:
    return {
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "channels": [
            {"id": "stable", "audience": "daily users", "gate": "release candidate plus rollback/update validation"},
            {"id": "beta", "audience": "trusted technical users", "gate": "focused tests plus known limitations"},
            {"id": "experimental", "audience": "opt-in subsystem testers", "gate": "feature flag and recovery path"},
            {"id": "research", "audience": "internal only", "gate": "no compatibility promise"},
        ],
        "cadence": {
            "stable": "slow, reliability-driven",
            "beta": "regular validation drops",
            "experimental": "as-needed subsystem cohorts",
            "research": "internal development snapshots",
        },
        "promotion_requirements": [
            "No known compatibility blockers.",
            "Migration dry-run and rollback path documented.",
            "Plugin and client compatibility validation complete.",
            "Security review complete for touched trust boundaries.",
            "Docs and known limitations updated.",
        ],
    }


def ecosystem_observability(workspace: str | Path, *, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    health = platform_health_analytics(root, persist=False)
    plugins = plugin_ecosystem_quality(root)
    workflows = workflow_excellence(root)
    dogfood = _safe_call("dogfooding", lambda: dogfooding.dogfooding_dashboard(root), {})
    observability = {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "plugin_health": plugins.get("quality_summary", {}),
        "workflow_success_rates": _workflow_success_rates(workflows.get("workflow_statistics", {})),
        "runtime_reliability": {
            "platform_health": health.get("overall_status"),
            "regression_watchlist_count": len(health.get("regression_watchlist", [])),
            "subsystems": health.get("subsystems", []),
        },
        "onboarding_success": _onboarding_signal(dogfood),
        "ecosystem_compatibility_issues": health.get("regression_watchlist", []),
        "local_first": True,
    }
    if persist:
        ProjectMemory(root).write_json(ECOSYSTEM_OBSERVABILITY_FILE, observability)
        observability["persisted"] = (ProjectMemory(root).root / ECOSYSTEM_OBSERVABILITY_FILE).is_file()
    return observability


def maintainability_guidance(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    sustainability = platform_sustainability(root, persist=False)
    health = sustainability.get("health", {})
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "reduce": [
            "unnecessary abstractions that are not used by stable workflows",
            "duplicate Website/Desktop/IDE runtime ownership",
            "unstable interfaces without contract tests",
            "feature sprawl in default navigation",
            "hidden coupling between experimental systems and stable workflows",
        ],
        "current_signals": {
            "health_status": health.get("overall_status"),
            "migration_success_rate": (health.get("analytics") or {}).get("migration_success_rate") if isinstance(health.get("analytics"), dict) else None,
            "compatibility_warnings": (sustainability.get("compatibility", {}).get("summary") or {}).get("warning")
            if isinstance(sustainability.get("compatibility", {}).get("summary"), dict)
            else None,
        },
        "recommended_refactors": [
            "Keep Core as the single runtime state owner.",
            "Turn client-specific workflow logic into adapters around Core contracts.",
            "Move Experimental Labs behind explicit opt-in routing.",
            "Treat plugin execution as a separate trust boundary.",
            "Run platform compatibility validation before release packaging.",
        ],
    }


def showcase_experiences(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    base = product_identity.showcase_workflows().get("showcase_workflows", [])
    additions = [
        _showcase("distributed_runtime_orchestration", "Distributed runtime orchestration", "Register a trusted local worker, route validation work, simulate disconnect, and show local fallback."),
        _showcase("plugin_workflow", "Plugin workflow", "Install or enable a low-risk plugin, inspect permissions, run a built-in tool, and show compatibility badges."),
        _showcase("workspace_intelligence_navigation", "Workspace intelligence", "Search architecture, inspect impact analysis, and select validation targets before editing."),
    ]
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "showcases": list(base) + additions,
        "demo_quality_bar": [
            "No hidden mutation.",
            "Visible model/provider route.",
            "Visible checkpoint and rollback path.",
            "Validation evidence shown before completion.",
            "Known limitation called out if a subsystem is experimental.",
        ],
    }


def trust_transparency(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    return {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "always_explain": [
            "what the system is doing",
            "why it is doing it",
            "what changed",
            "how to rollback",
            "what data is local",
            "what data may leave the machine",
            "which model/provider is selected",
            "which plugin permissions are active",
        ],
        "trust_surfaces": [
            "runtime status",
            "quality gates",
            "workflow timeline",
            "agent activity",
            "plugin permission panel",
            "route explanation",
            "checkpoint/rollback panel",
            "diagnostics export",
        ],
        "local_cloud_disclosure": [
            "Local-only and cloud-disabled modes must be visible.",
            "Cloud calls require route explanation and provider warning.",
            "Diagnostics are local unless explicitly exported.",
            "Sensitive files and secrets must be redacted or excluded.",
        ],
        "rollback_expectation": "Every file-changing workflow must show checkpoint status and rollback availability before apply.",
    }


def sustainability_plan() -> dict[str, Any]:
    return {
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "long_term_maintenance": [
            "Keep Core contract catalog as the source of truth.",
            "Run compatibility validation during release packaging.",
            "Archive and migrate .aegis state before schema changes.",
            "Limit default UX to stable and advanced workflows.",
        ],
        "compatibility_support_windows": platform_governance().get("versioning_policy", {}).get("compatibility_windows", {}),
        "plugin_migration_strategy": [
            "Require plugin API version metadata.",
            "Warn for one generation before rejecting old manifests.",
            "Provide manifest migration guidance before breaking plugin categories.",
            "Keep high-risk scopes approval-gated.",
        ],
        "governance_structure": [
            "Core runtime owner reviews contracts and migrations.",
            "Plugin/runtime owner reviews permission and compatibility changes.",
            "Client owners review fallback and UI compatibility.",
            "Security review is required for trust-boundary changes.",
        ],
        "roadmap_review_process": [
            "Review production, beta, experimental, and research roadmaps separately.",
            "Promote only workflows that have tests, docs, telemetry/observability, and recovery paths.",
            "Deprecate duplicate client-owned logic once Core migration is proven.",
        ],
    }


def ecosystem_maturity(workspace: str | Path, *, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    strategy = ecosystem_strategy()
    workflows = workflow_excellence(root)
    plugins = plugin_ecosystem_quality(root)
    stability = api_stability()
    observability = ecosystem_observability(root, persist=False)
    maintainability = maintainability_guidance(root)
    maturity_scores = _maturity_scores(workflows, plugins, stability, observability, maintainability)
    result = {
        "workspace": str(root),
        "schema_version": ECOSYSTEM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "strategy": strategy,
        "workflow_excellence": workflows,
        "plugin_quality": plugins,
        "api_stability": stability,
        "contributor_ecosystem": contributor_ecosystem(root),
        "platform_reputation": platform_reputation(root),
        "release_cadence": release_cadence(),
        "observability": observability,
        "maintainability": maintainability,
        "showcases": showcase_experiences(root),
        "trust_transparency": trust_transparency(root),
        "sustainability_plan": sustainability_plan(),
        "maturity_scores": maturity_scores,
        "adoption_blockers": _adoption_blockers(maturity_scores, observability),
        "recommended_long_term_focus": _recommended_focus(maturity_scores),
    }
    if persist:
        ProjectMemory(root).write_json(ECOSYSTEM_MATURITY_FILE, result)
        result["state_path"] = str(ProjectMemory(root).root / ECOSYSTEM_MATURITY_FILE)
        result["persisted"] = (ProjectMemory(root).root / ECOSYSTEM_MATURITY_FILE).is_file()
    return result


def _workflow_score(item: dict[str, Any], workflow_stats: dict[str, Any], validation: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    workflow_id = str(item.get("id") or "")
    score = 70
    blockers: list[str] = []
    if item.get("safety_gates"):
        score += 10
    if validation.get("commands"):
        score += 8
    if quality.get("statistics"):
        score += 7
    if workflow_id in {"implement_feature", "repair", "deploy"}:
        score -= 5
        blockers.append("advanced workflow should remain approval-gated")
    return {
        "id": workflow_id,
        "name": item.get("name", workflow_id),
        "mode": item.get("mode", ""),
        "maturity_score": max(0, min(100, score)),
        "speed": "medium",
        "trust": "high" if item.get("safety_gates") else "medium",
        "clarity": "high" if item.get("steps") else "medium",
        "predictability": "high" if workflow_id in {"scan_project", "validate", "checkpoint", "rollback"} else "medium",
        "pain_points": blockers,
    }


def _workflow_backlog(workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backlog = []
    for workflow in workflows:
        if workflow["maturity_score"] < 85:
            backlog.append(
                {
                    "workflow": workflow["id"],
                    "priority": "high" if workflow["maturity_score"] < 75 else "medium",
                    "recommendation": "Reduce friction, make validation/rollback visible, and keep approval state explicit.",
                }
            )
    return backlog[:10]


def _score_plugin(plugin: dict[str, Any]) -> dict[str, Any]:
    score = 100
    badges: list[str] = []
    review_required = False
    validation = plugin.get("validation", {}) if isinstance(plugin.get("validation"), dict) else {}
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    scopes = list(plugin.get("permission_scopes") or [])
    high_risk = sorted(set(scopes) & plugin_runtime.HIGH_RISK_SCOPES)
    if errors:
        score -= 60
        review_required = True
    if warnings:
        score -= min(25, 8 * len(warnings))
        review_required = True
    if high_risk:
        score -= 20
        review_required = True
    if not plugin.get("runtime_compatibility"):
        score -= 10
        review_required = True
    if plugin.get("load_status") == "loaded":
        badges.append("loaded")
    if not errors:
        badges.append("manifest-valid")
    if not high_risk:
        badges.append("low-risk-permissions")
    if plugin.get("runtime_compatibility"):
        badges.append("runtime-compatible")
    return {
        "id": plugin.get("id", ""),
        "name": plugin.get("name", plugin.get("id", "")),
        "version": plugin.get("version", ""),
        "category": plugin.get("category", ""),
        "load_status": plugin.get("load_status", ""),
        "enabled": bool(plugin.get("enabled")),
        "quality_score": max(0, min(100, score)),
        "badges": badges,
        "permission_scopes": scopes,
        "risk_level": "high" if high_risk else "medium" if warnings else "low",
        "review_required": review_required,
        "review_notes": [*errors, *warnings, *(f"High-risk scope: {scope}" for scope in high_risk)],
    }


def _compatibility_badges(plugins: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    for plugin in plugins:
        for badge in plugin.get("badges", []):
            counts[badge] += 1
    return {
        "available_badges": ["loaded", "manifest-valid", "low-risk-permissions", "runtime-compatible", "review-required"],
        "counts": dict(counts),
    }


def _workflow_success_rates(stats: dict[str, Any]) -> dict[str, Any]:
    total = int(stats.get("workflow_count") or 0) if isinstance(stats, dict) else 0
    completed = int(stats.get("completed_workflow_count") or 0) if isinstance(stats, dict) else 0
    failed = int(stats.get("failed_workflow_count") or 0) if isinstance(stats, dict) else 0
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "completion_rate": round(completed / total, 4) if total else None,
        "failure_rate": round(failed / total, 4) if total else None,
    }


def _onboarding_signal(dogfood: dict[str, Any]) -> dict[str, Any]:
    friction = dogfood.get("friction") if isinstance(dogfood.get("friction"), dict) else {}
    categories = friction.get("category_counts") if isinstance(friction.get("category_counts"), dict) else {}
    return {
        "status": "watch" if categories.get("onboarding") or categories.get("setup") else "unknown",
        "friction_count": int(categories.get("onboarding", 0) or 0) + int(categories.get("setup", 0) or 0),
    }


def _maturity_scores(
    workflows: dict[str, Any],
    plugins: dict[str, Any],
    stability: dict[str, Any],
    observability: dict[str, Any],
    maintainability: dict[str, Any],
) -> dict[str, Any]:
    workflow_scores = [item["maturity_score"] for item in workflows.get("workflows", []) if isinstance(item, dict)]
    plugin_summary = plugins.get("quality_summary", {}) if isinstance(plugins.get("quality_summary"), dict) else {}
    stable_count = int((stability.get("stability_counts") or {}).get("stable", 0)) if isinstance(stability.get("stability_counts"), dict) else 0
    total_contracts = sum(int(value) for value in (stability.get("stability_counts") or {}).values()) if isinstance(stability.get("stability_counts"), dict) else 0
    runtime_status = observability.get("runtime_reliability", {}).get("platform_health") if isinstance(observability.get("runtime_reliability"), dict) else "unknown"
    maintainability_status = maintainability.get("current_signals", {}).get("health_status") if isinstance(maintainability.get("current_signals"), dict) else "unknown"
    scores = {
        "workflow_excellence": round(sum(workflow_scores) / len(workflow_scores), 2) if workflow_scores else 0,
        "plugin_ecosystem": plugin_summary.get("average_score", 0),
        "api_stability": round((stable_count / total_contracts) * 100, 2) if total_contracts else 0,
        "observability": 85 if runtime_status == "pass" else 70 if runtime_status == "warning" else 50,
        "maintainability": 85 if maintainability_status == "pass" else 70 if maintainability_status == "warning" else 50,
    }
    scores["overall"] = round(sum(float(value or 0) for value in scores.values()) / len(scores), 2)
    return scores


def _adoption_blockers(scores: dict[str, Any], observability: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    for key, value in scores.items():
        if key == "overall":
            continue
        if float(value or 0) < 70:
            blockers.append({"area": key, "severity": "high", "reason": f"{key} score is below adoption threshold."})
    for item in observability.get("ecosystem_compatibility_issues", []):
        if isinstance(item, dict):
            blockers.append({"area": item.get("area") or item.get("id") or "compatibility", "severity": item.get("severity", "medium"), "reason": item.get("reason", item.get("evidence", ""))})
    return blockers[:12]


def _recommended_focus(scores: dict[str, Any]) -> list[str]:
    focus = []
    if float(scores.get("workflow_excellence") or 0) < 85:
        focus.append("Polish feature, validation, repair, deployment, rollback, and roadmap execution flows around speed and trust.")
    if float(scores.get("plugin_ecosystem") or 0) < 85:
        focus.append("Improve plugin review tools, compatibility badges, permission explanations, and sample plugin quality.")
    if float(scores.get("api_stability") or 0) < 35:
        focus.append("Promote proven Core contracts from experimental to stable after compatibility validation.")
    focus.append("Keep default UX focused on Engineering Workspace while Experimental Labs remains opt-in.")
    focus.append("Run migration, compatibility, plugin, onboarding, upgrade, and long-session tests before broader adoption.")
    return focus[:8]


def _showcase(showcase_id: str, title: str, description: str) -> dict[str, Any]:
    return {
        "id": showcase_id,
        "title": title,
        "description": description,
        "demo_requirements": ["Core running", "workspace selected", "approval controls visible", "rollback path visible"],
        "success_criteria": ["clear status", "visible trust boundary", "validation evidence", "recovery path"],
    }


def _safe_call(name: str, func, default: Any) -> Any:
    try:
        return func()
    except Exception as exc:
        return {"status": "unavailable", "source": name, "error": scrub(str(exc))} if isinstance(default, dict) else default
