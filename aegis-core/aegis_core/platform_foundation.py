from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from . import distributed_runtime, plugin_runtime, release, runtime_interaction, stabilization
from .contracts import CONTRACTS, CONTRACT_DATA_MODELS
from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .model_router import provider_inventory
from .workflow_runtime import workflow_statistics


PLATFORM_SCHEMA_VERSION = "2026.05.12"
PLATFORM_MIGRATIONS_FILE = "platform-migrations.json"
PLATFORM_STATE_FILE = "platform-state.json"
PLATFORM_COMPATIBILITY_FILE = "platform-compatibility-report.json"
PLATFORM_HEALTH_FILE = "platform-health.json"
PLATFORM_SUSTAINABILITY_FILE = "platform-sustainability.json"
PLATFORM_ARCHIVE_DIR = "platform-archives"
MAX_ARCHIVE_FILES = 250
MAX_ARCHIVE_FILE_BYTES = 5_000_000

PLATFORM_MIGRATIONS: list[dict[str, str]] = [
    {
        "id": "platform_state_schema_2026_05_12",
        "category": "aegis-state",
        "description": "Create .aegis/platform-state.json as the long-term platform schema anchor.",
    },
    {
        "id": "memory_manifest_2026_05_12",
        "category": "memory",
        "description": "Create a manifest for memory files so future memory migrations are inspectable.",
    },
    {
        "id": "workflow_history_manifest_2026_05_12",
        "category": "workflow-history",
        "description": "Create a workflow history manifest for archived and active workflow state.",
    },
    {
        "id": "plugin_manifest_index_2026_05_12",
        "category": "plugins",
        "description": "Create a plugin manifest index with dependencies and compatibility warnings.",
    },
    {
        "id": "orchestration_state_manifest_2026_05_12",
        "category": "orchestration",
        "description": "Create an orchestration state manifest for task graph and queue compatibility.",
    },
    {
        "id": "knowledge_graph_manifest_2026_05_12",
        "category": "knowledge-graph",
        "description": "Create a knowledge graph storage manifest for index migrations.",
    },
    {
        "id": "checkpoint_format_manifest_2026_05_12",
        "category": "checkpoints",
        "description": "Create a checkpoint format manifest for backup and restore compatibility.",
    },
]


def platform_governance() -> dict[str, Any]:
    return {
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "purpose": "long_term_platform_foundation",
        "api_stability_guarantees": [
            "Stable /v1 contracts do not remove or rename response fields inside a compatibility window.",
            "Experimental contracts may add optional fields, but breaking changes require explicit descriptor notes.",
            "Deprecated contracts stay callable for at least one minor release and must advertise replacement routes.",
            "All client-visible responses must use the Core contract envelope and registered contract kinds.",
        ],
        "plugin_compatibility_guarantees": [
            "Manifest-only discovery stays backward-compatible for one plugin API generation.",
            "High-risk permission scopes require explicit user approval and remain disabled by default in alpha/beta channels.",
            "Plugins must declare runtime compatibility and dependency metadata before execution hooks are trusted.",
            "Plugin load failures are isolated and reported through observability instead of breaking Core startup.",
        ],
        "deprecation_policy": {
            "minimum_notice": "one minor release for beta/stable APIs",
            "required_metadata": ["replacement", "reason", "first_deprecated_in", "removal_not_before"],
            "client_expectation": "Website, Desktop, VS Code, and Visual Studio keep fallback paths until replacement contracts pass release-candidate validation.",
        },
        "migration_policy": {
            "principles": [
                "Migrations are idempotent.",
                "Dry-run output must describe all writes before applying.",
                "Workspace-local .aegis state is migrated before clients rely on new contracts.",
                "Migration failures must preserve prior state and expose recovery guidance.",
            ],
            "state_categories": [item["category"] for item in PLATFORM_MIGRATIONS],
        },
        "versioning_policy": {
            "core_schema_version": PLATFORM_SCHEMA_VERSION,
            "semantic_components": ["core", "website", "desktop", "vscode-extension", "visual-studio-extension", "plugin-api"],
            "compatibility_windows": {
                "stable": "two minor releases",
                "beta": "one minor release",
                "experimental": "best-effort within the current development cycle",
                "internal": "no external compatibility promise",
            },
        },
        "runtime_compatibility_windows": {
            "core_clients": "clients should support the current Core schema plus the previous stable schema",
            "plugins": "plugin manifests should support the current plugin API generation plus one previous generation",
            "distributed_nodes": "trusted nodes must report exact schema and capability compatibility before accepting workloads",
        },
        "security_review_required_for": [
            "filesystem_write",
            "process_execution",
            "network_access",
            "provider_credentials",
            "remote_node_trust",
            "plugin_permission_scope_expansion",
            "update_package_verification",
            "migration_that_rewrites_state",
        ],
        "governance_sources": {
            "stabilization": stabilization.governance_rules(),
            "release_schema_version": release.RELEASE_SCHEMA_VERSION,
            "core_version": release.CORE_VERSION,
        },
    }


def subsystem_ownership() -> dict[str, Any]:
    subsystems = [
        _subsystem("stable_core_runtime", "aegis-core", "stable", ["contracts", "editing", "checkpoints", "validation", "release compatibility"]),
        _subsystem("orchestration", "aegis-core/orchestration", "beta", ["workflow runtime", "task graph", "engineering execution", "agent supervision"]),
        _subsystem("plugins", "aegis-core/plugin_runtime", "beta", ["manifest loading", "permission scopes", "tool contracts", "extension hooks"]),
        _subsystem("experimental_systems", "aegis-core/labs", "experimental", ["multi-agent autonomy", "optimization experiments", "voice/collaboration foundations"]),
        _subsystem("deployment_runtime_infrastructure", "aegis-core/deployment + distributed_runtime", "beta", ["CI/CD intelligence", "runtime nodes", "workload routing"]),
        _subsystem("ide_integrations", "vscode + visual-studio extensions", "beta", ["Core clients", "fallback behavior", "IDE-specific context"]),
        _subsystem("observability_systems", "aegis-core + Website/Desktop surfaces", "beta", ["workflow traces", "quality gates", "alpha diagnostics", "runtime health"]),
        _subsystem("website_gateway", "website/backend", "compatibility", ["auth", "UI-facing API compatibility", "Core delegation fallback"]),
        _subsystem("desktop_client", "src desktop client", "compatibility", ["native runtime panel", "Core-first operations", "Website fallback"]),
    ]
    return {
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "subsystems": subsystems,
        "boundary_rules": [
            "Core owns runtime state and durable contracts.",
            "Clients own presentation, authentication surfaces, and client-specific ergonomics.",
            "Website backend remains a gateway/fallback, not the long-term runtime owner.",
            "Experimental systems cannot become defaults until tests, docs, recovery behavior, and ownership are defined.",
        ],
        "review_gates": {
            "stable_core_runtime": ["contract test", "migration dry-run", "rollback path"],
            "orchestration": ["workflow replay", "pause/resume/cancel", "quality gate integration"],
            "plugins": ["permission validation", "compatibility validation", "failure isolation"],
            "distributed_runtime": ["trust validation", "disconnect recovery", "local fallback"],
            "ide_integrations": ["Core offline smoke", "schema mismatch handling", "safe apply preview"],
        },
    }


def platform_migration_status(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    state = _read_json(memory.root / PLATFORM_MIGRATIONS_FILE, {"schema_version": PLATFORM_SCHEMA_VERSION, "applied": []})
    applied = state.get("applied", []) if isinstance(state, dict) else []
    applied_ids = {item.get("id") for item in applied if isinstance(item, dict)}
    pending = [migration for migration in PLATFORM_MIGRATIONS if migration["id"] not in applied_ids]
    return {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "dry_run": False,
        "applied": applied,
        "pending": pending,
        "state_path": str(memory.root / PLATFORM_MIGRATIONS_FILE),
        "supported_categories": [migration["category"] for migration in PLATFORM_MIGRATIONS],
        "recovery_guidance": [
            "Run dry-run first and inspect planned writes.",
            "Create a platform archive before applying migrations to shared workspaces.",
            "If a migration fails, keep the existing .aegis state and rerun after resolving file permissions.",
        ],
    }


def run_platform_migrations(workspace: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    status = platform_migration_status(root)
    applied = list(status.get("applied", []))
    pending = list(status.get("pending", []))
    newly_applied: list[dict[str, Any]] = []

    if not dry_run:
        memory.ensure()

    for migration in pending:
        outputs = _planned_migration_outputs(memory, migration["id"])
        if not dry_run:
            outputs = _apply_platform_migration(root, memory, migration["id"])
        newly_applied.append(
            {
                **migration,
                "applied_at": "" if dry_run else utc_now(),
                "dry_run": dry_run,
                "outputs": outputs,
            }
        )

    if not dry_run and newly_applied:
        record = {
            "schema_version": PLATFORM_SCHEMA_VERSION,
            "updated_at": utc_now(),
            "applied": applied + newly_applied,
        }
        memory.write_json(PLATFORM_MIGRATIONS_FILE, record)

    return {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "dry_run": dry_run,
        "applied": applied if dry_run else applied + newly_applied,
        "pending": newly_applied if dry_run else [],
        "state_path": str(memory.root / PLATFORM_MIGRATIONS_FILE),
        "migration_count": len(newly_applied),
    }


def validate_platform_compatibility(
    workspace: str | Path,
    *,
    client_reports: list[dict[str, Any]] | None = None,
    include_plugins: bool = True,
    persist: bool = False,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    checks = [
        _api_compatibility_check(),
        _client_compatibility_check(root, client_reports or []),
        _orchestration_compatibility_check(root),
        _runtime_compatibility_check(root),
    ]
    if include_plugins:
        checks.append(_plugin_compatibility_check(root))
    blocked = [check for check in checks if check["status"] == "blocked"]
    warnings = [check for check in checks if check["status"] == "warning"]
    result = {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "compatible": not blocked,
        "overall_status": "blocked" if blocked else ("warning" if warnings else "pass"),
        "checks": checks,
        "summary": {
            "pass": sum(1 for check in checks if check["status"] == "pass"),
            "warning": len(warnings),
            "blocked": len(blocked),
            "checked_categories": [check["id"] for check in checks],
        },
        "recommended_actions": _compatibility_actions(checks),
        "state_path": str(ProjectMemory(root).root / PLATFORM_COMPATIBILITY_FILE),
    }
    if persist:
        ProjectMemory(root).write_json(PLATFORM_COMPATIBILITY_FILE, result)
        result["persisted"] = (ProjectMemory(root).root / PLATFORM_COMPATIBILITY_FILE).is_file()
    return result


def ecosystem_dependency_management(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    plugin_dashboard = _safe_call("plugins", lambda: plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True), {})
    providers = _safe_call("providers", lambda: provider_inventory(root), {})
    release_manifest = _safe_call("release", lambda: release.release_manifest(root), {})
    plugin_dependencies = _plugin_dependencies(plugin_dashboard)
    provider_dependencies = _provider_dependencies(providers)
    runtime_dependencies = _runtime_dependencies(release_manifest)
    risks = _dependency_risks(plugin_dependencies, provider_dependencies, runtime_dependencies)
    return {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "plugin_dependencies": plugin_dependencies,
        "provider_dependencies": provider_dependencies,
        "runtime_dependencies": runtime_dependencies,
        "update_compatibility_risks": risks,
        "policy": {
            "plugin_dependency_cycles": "warn and keep plugin disabled until resolved",
            "provider_dependency_failures": "fall back to local/provider-safe route profiles",
            "runtime_dependency_failures": "block update/apply for incompatible clients",
        },
    }


def release_engineering_status(workspace: str | Path | None = None) -> dict[str, Any]:
    root = Path(workspace).resolve() if workspace else Path(__file__).resolve().parents[2]
    manifest = _safe_call("release_manifest", lambda: release.release_manifest(root), {})
    components = manifest.get("components", {}) if isinstance(manifest.get("components"), dict) else {}
    matrix = []
    for component_id, component in sorted(components.items()):
        package = component.get("package", {}) if isinstance(component, dict) else {}
        matrix.append(
            {
                "component": component_id,
                "version": str(component.get("version", "")) if isinstance(component, dict) else "",
                "minimum_core": str(component.get("minimum_compatible_core", "")) if isinstance(component, dict) else "",
                "minimum_schema": str(component.get("minimum_compatible_schema", "")) if isinstance(component, dict) else "",
                "artifact": package.get("artifact", ""),
                "checksum_present": bool(package.get("sha256")),
                "size_bytes": int(package.get("size_bytes") or 0),
            }
        )
    scripts = [
        _script_status(root, "scripts/build-release.ps1"),
        _script_status(root, "scripts/aegis-update.ps1"),
    ]
    return {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "reproducible_builds": {
            "status": "ready" if all(item["exists"] for item in scripts) else "warning",
            "scripts": scripts,
            "required_outputs": [
                "aegis-core package",
                "website package",
                "desktop package",
                "VS Code VSIX",
                "Visual Studio VSIX",
                "version manifest",
            ],
        },
        "release_verification": {
            "manifest_present": bool(manifest),
            "component_count": len(matrix),
            "checksum_required": bool((manifest.get("update_policy") or {}).get("requires_checksum", True)) if isinstance(manifest, dict) else True,
            "rollback_required": bool((manifest.get("update_policy") or {}).get("rollback_required", True)) if isinstance(manifest, dict) else True,
        },
        "compatibility_matrix": matrix,
        "staged_rollout_channels": [
            {"id": "stable", "purpose": "release-candidate-tested builds only"},
            {"id": "beta", "purpose": "trusted external alpha/beta users"},
            {"id": "experimental", "purpose": "opt-in subsystem validation"},
            {"id": "dev", "purpose": "internal development only"},
        ],
        "rollback_requirements": [
            "checksum verification before apply",
            "backup current install before overwrite",
            "safe-mode marker on failed update",
            "compatibility check before post-update workflows",
        ],
    }


def platform_health_analytics(workspace: str | Path, *, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    compatibility = validate_platform_compatibility(root, include_plugins=True, persist=False)
    migrations = platform_migration_status(root)
    plugins = _safe_call("plugins", lambda: plugin_runtime.plugin_observability(root), {})
    workflows = _safe_call("workflows", lambda: workflow_statistics(root), {})
    runtime = _safe_call("runtime", lambda: runtime_interaction.runtime_dashboard(root, limit=25), {})
    distributed = _safe_call("distributed", lambda: distributed_runtime.observability(root), {})
    subsystems = _subsystem_health(compatibility, migrations, plugins, workflows, runtime, distributed)
    result = {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "overall_status": _overall_health(subsystems),
        "subsystems": subsystems,
        "analytics": {
            "migration_success_rate": _migration_success_rate(migrations),
            "compatibility_blockers": compatibility["summary"]["blocked"],
            "compatibility_warnings": compatibility["summary"]["warning"],
            "plugin_failure_count": int(plugins.get("failure_count") or 0) if isinstance(plugins, dict) else 0,
            "workflow_count": int(workflows.get("workflow_count") or 0) if isinstance(workflows, dict) else 0,
            "active_workflows": int(workflows.get("active_workflow_count") or 0) if isinstance(workflows, dict) else 0,
            "runtime_jobs": int(((runtime.get("observability") or {}).get("job_count") or 0)) if isinstance(runtime.get("observability"), dict) else 0,
            "distributed_nodes": int(((distributed.get("nodes") or {}).get("total") or 0)) if isinstance(distributed.get("nodes"), dict) else 0,
        },
        "regression_watchlist": _regression_watchlist(compatibility, migrations, plugins),
        "state_path": str(ProjectMemory(root).root / PLATFORM_HEALTH_FILE),
    }
    if persist:
        ProjectMemory(root).write_json(PLATFORM_HEALTH_FILE, result)
        result["persisted"] = (ProjectMemory(root).root / PLATFORM_HEALTH_FILE).is_file()
    return result


def ecosystem_tooling(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    return {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "plugin_sdk": {
            "manifest_files": list(plugin_runtime.PLUGIN_MANIFEST_NAMES),
            "api_version": plugin_runtime.PLUGIN_API_VERSION,
            "permission_scopes": sorted(plugin_runtime.PERMISSION_SCOPES),
            "high_risk_scopes": sorted(plugin_runtime.HIGH_RISK_SCOPES),
            "docs": "docs/PLUGIN_ECOSYSTEM.md",
        },
        "validators": [
            {"id": "plugin_compatibility", "endpoint": "/v1/platform/compatibility/validate", "scope": "plugins"},
            {"id": "client_compatibility", "endpoint": "/v1/release/compatibility", "scope": "clients"},
            {"id": "api_contracts", "endpoint": "/v1/contracts", "scope": "Core envelopes"},
            {"id": "workflow_schema", "endpoint": "/v1/workflows/statistics", "scope": "workflow runtime"},
            {"id": "platform_migrations", "endpoint": "/v1/platform/migrations", "scope": ".aegis state"},
        ],
        "runtime_diagnostics": [
            {"id": "alpha_diagnostics", "endpoint": "/v1/alpha/diagnostics/export"},
            {"id": "runtime_replay", "endpoint": "/v1/runtime/replay"},
            {"id": "platform_health", "endpoint": "/v1/platform/health"},
        ],
        "developer_infrastructure": {
            "bootstrap": ["install Python dependencies", "install Website npm dependencies", "run Core focused tests"],
            "debugging_guides": ["docs/PLATFORM_STABILIZATION_AND_PRODUCTION_READINESS.md", "docs/CONTROLLED_EXTERNAL_ALPHA.md"],
            "compatibility_tooling": ["release compatibility checks", "platform compatibility validation", "plugin manifest validation"],
        },
    }


def roadmap_governance() -> dict[str, Any]:
    return {
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "production_roadmap": [
            "Core contract stability and compatibility tooling",
            "Release/migration verification and rollback recovery",
            "Client Core-first parity with documented fallbacks",
            "Large-workspace performance budgets",
        ],
        "experimental_roadmap": [
            "Distributed runtime cohorts",
            "Multi-agent long-session stress validation",
            "Optimization experiment adoption workflows",
            "Voice/collaboration provider integrations",
        ],
        "research_initiatives": [
            "Hybrid graph/vector retrieval quality",
            "Model routing explainability benchmarks",
            "Automated orchestration regression detection",
            "Plugin isolation strategies beyond manifest-only loading",
        ],
        "deprecated_systems": [
            "Website-owned apply/checkpoint/validation authority",
            "Client-owned model/provider truth",
            "Extension monolith runtime ownership",
            "Ad hoc plugin contracts outside Core manifests",
        ],
        "ecosystem_initiatives": [
            "Plugin SDK examples",
            "Compatibility validator CLI",
            "Workflow schema validator",
            "Release candidate matrix automation",
            "Contributor subsystem ownership map",
        ],
        "promotion_rule": "A system moves toward production only after tests, docs, ownership, migration behavior, rollback behavior, and compatibility contracts are all present.",
    }


def create_platform_archive(
    workspace: str | Path,
    *,
    include_memory: bool = True,
    include_workflows: bool = True,
    include_knowledge: bool = True,
    include_checkpoints: bool = False,
    dry_run: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    archive_id = f"platform-archive-{utc_now().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    archive_root = memory.root / PLATFORM_ARCHIVE_DIR / archive_id
    candidates = _archive_candidates(
        memory.root,
        include_memory=include_memory,
        include_workflows=include_workflows,
        include_knowledge=include_knowledge,
        include_checkpoints=include_checkpoints,
    )
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source, category in candidates:
        try:
            size = source.stat().st_size
        except OSError as exc:
            skipped.append({"path": str(source), "reason": scrub(str(exc))})
            continue
        rel = _safe_relative(source, memory.root)
        entry = {
            "source": str(source),
            "relative_path": rel,
            "category": category,
            "size_bytes": size,
            "sha256": _sha256(source),
            "archived_path": str(archive_root / "files" / rel),
        }
        entries.append(entry)
        if not dry_run:
            target = archive_root / "files" / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            except OSError as exc:
                skipped.append({"path": str(source), "reason": scrub(str(exc))})
    manifest = {
        "archive_id": archive_id,
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "created_at": utc_now(),
        "dry_run": dry_run,
        "reason": scrub(reason),
        "includes": {
            "memory": include_memory,
            "workflows": include_workflows,
            "knowledge": include_knowledge,
            "checkpoints": include_checkpoints,
        },
        "entry_count": len(entries),
        "entries": entries,
        "skipped": skipped,
        "archive_path": str(archive_root),
        "recovery_guidance": [
            "Inspect manifest.json before restoring individual files.",
            "Restore only the needed .aegis files and keep the current state backed up.",
            "Run platform compatibility and migration status after any manual recovery.",
        ],
    }
    if not dry_run:
        try:
            archive_root.mkdir(parents=True, exist_ok=True)
            (archive_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            manifest["skipped"].append({"path": str(archive_root / "manifest.json"), "reason": scrub(str(exc))})
    manifest["persisted"] = (archive_root / "manifest.json").is_file() if not dry_run else False
    return manifest


def platform_sustainability(workspace: str | Path, *, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    result = {
        "workspace": str(root),
        "schema_version": PLATFORM_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "governance": platform_governance(),
        "migrations": platform_migration_status(root),
        "compatibility": validate_platform_compatibility(root, persist=False),
        "ownership": subsystem_ownership(),
        "dependencies": ecosystem_dependency_management(root),
        "release_engineering": release_engineering_status(root),
        "health": platform_health_analytics(root, persist=False),
        "tooling": ecosystem_tooling(root),
        "roadmap": roadmap_governance(),
        "archival": {
            "endpoint": "/v1/platform/archive",
            "archive_dir": str(ProjectMemory(root).root / PLATFORM_ARCHIVE_DIR),
            "supports": ["workflow archival", "memory archival", "rollback snapshots", "project recovery manifests", "migration recovery"],
        },
        "recommended_long_term_priorities": [
            "Run and persist platform migrations before the next release candidate.",
            "Automate compatibility validation in release packaging.",
            "Keep distributed runtime and high-risk plugin execution opt-in until trust/isolation tests mature.",
            "Add long-upgrade-chain and corrupted-state recovery tests to CI.",
        ],
    }
    if persist:
        ProjectMemory(root).write_json(PLATFORM_SUSTAINABILITY_FILE, result)
        result["state_path"] = str(ProjectMemory(root).root / PLATFORM_SUSTAINABILITY_FILE)
        result["persisted"] = (ProjectMemory(root).root / PLATFORM_SUSTAINABILITY_FILE).is_file()
    return result


def _subsystem(subsystem_id: str, owner: str, stability: str, responsibilities: list[str]) -> dict[str, Any]:
    return {
        "id": subsystem_id,
        "owner": owner,
        "stability": stability,
        "responsibilities": responsibilities,
    }


def _planned_migration_outputs(memory: ProjectMemory, migration_id: str) -> dict[str, Any]:
    mapping = {
        "platform_state_schema_2026_05_12": [PLATFORM_STATE_FILE],
        "memory_manifest_2026_05_12": ["memory-manifest.json"],
        "workflow_history_manifest_2026_05_12": ["workflow-history-manifest.json"],
        "plugin_manifest_index_2026_05_12": ["plugin-manifest-index.json"],
        "orchestration_state_manifest_2026_05_12": ["orchestration-state-manifest.json"],
        "knowledge_graph_manifest_2026_05_12": ["knowledge-graph-manifest.json"],
        "checkpoint_format_manifest_2026_05_12": ["checkpoint-format-manifest.json"],
    }
    return {"planned_files": [str(memory.root / name) for name in mapping.get(migration_id, [])]}


def _apply_platform_migration(root: Path, memory: ProjectMemory, migration_id: str) -> dict[str, Any]:
    if migration_id == "platform_state_schema_2026_05_12":
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "created_at": utc_now(), "workspace": str(root)}
        memory.write_json(PLATFORM_STATE_FILE, payload)
        return {"files": [str(memory.root / PLATFORM_STATE_FILE)]}
    if migration_id == "memory_manifest_2026_05_12":
        files = _top_level_state_files(memory.root, suffixes={".md", ".json", ".jsonl"})
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "generated_at": utc_now(), "files": files}
        memory.write_json("memory-manifest.json", payload)
        return {"files": [str(memory.root / "memory-manifest.json")], "tracked_files": len(files)}
    if migration_id == "workflow_history_manifest_2026_05_12":
        stats = _safe_call("workflow_statistics", lambda: workflow_statistics(root), {})
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "generated_at": utc_now(), "statistics": stats}
        memory.write_json("workflow-history-manifest.json", payload)
        return {"files": [str(memory.root / "workflow-history-manifest.json")]}
    if migration_id == "plugin_manifest_index_2026_05_12":
        dashboard = _safe_call("plugin_dashboard", lambda: plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True), {})
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "generated_at": utc_now(), "dependencies": _plugin_dependencies(dashboard)}
        memory.write_json("plugin-manifest-index.json", payload)
        return {"files": [str(memory.root / "plugin-manifest-index.json")]}
    if migration_id == "orchestration_state_manifest_2026_05_12":
        state_files = [name for name in ("active-orchestration.json", "orchestration-queue.json", "active-agent-plan.json") if (memory.root / name).exists()]
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "generated_at": utc_now(), "state_files": state_files}
        memory.write_json("orchestration-state-manifest.json", payload)
        return {"files": [str(memory.root / "orchestration-state-manifest.json")], "state_file_count": len(state_files)}
    if migration_id == "knowledge_graph_manifest_2026_05_12":
        files = _knowledge_state_files(memory.root)
        payload = {"schema_version": PLATFORM_SCHEMA_VERSION, "generated_at": utc_now(), "files": files}
        memory.write_json("knowledge-graph-manifest.json", payload)
        return {"files": [str(memory.root / "knowledge-graph-manifest.json")], "tracked_files": len(files)}
    if migration_id == "checkpoint_format_manifest_2026_05_12":
        backups = memory.root / "backups"
        payload = {
            "schema_version": PLATFORM_SCHEMA_VERSION,
            "generated_at": utc_now(),
            "backups_dir": str(backups),
            "exists": backups.is_dir(),
            "format": "directory-backed checkpoints with manifest metadata when available",
        }
        memory.write_json("checkpoint-format-manifest.json", payload)
        return {"files": [str(memory.root / "checkpoint-format-manifest.json")]}
    return {}


def _api_compatibility_check() -> dict[str, Any]:
    missing = [kind for kind in CONTRACTS if kind not in CONTRACT_DATA_MODELS]
    deprecated = [kind for kind, descriptor in CONTRACTS.items() if getattr(descriptor, "stability", "") == "deprecated"]
    return _check(
        "api_compatibility",
        "API compatibility",
        "blocked" if missing else "pass",
        f"{len(CONTRACTS)} contracts; {len(missing)} missing data model mappings; {len(deprecated)} deprecated.",
        {"missing_data_models": missing, "deprecated_contracts": deprecated[:25]},
    )


def _client_compatibility_check(root: Path, client_reports: list[dict[str, Any]]) -> dict[str, Any]:
    reports = client_reports or _default_client_reports(root)
    results = []
    for report in reports:
        client_type = str(report.get("client_type") or report.get("type") or "")
        if not client_type:
            continue
        results.append(
            release.check_compatibility(
                client_type,
                str(report.get("client_version") or report.get("version") or ""),
                schema_version=str(report.get("schema_version") or release.RELEASE_SCHEMA_VERSION),
                core_version=str(report.get("core_version") or release.CORE_VERSION),
                capabilities=list(report.get("capabilities") or ["release-compatibility"]),
                workspace=root,
            )
        )
    blockers = [item for item in results if not item.get("compatible")]
    warnings = [item for item in results if item.get("status") == "warning"]
    return _check(
        "client_compatibility",
        "Client compatibility",
        "blocked" if blockers else "warning" if warnings else "pass",
        f"{len(results)} client report(s); {len(blockers)} blocked; {len(warnings)} warning.",
        {"clients": results},
    )


def _plugin_compatibility_check(root: Path) -> dict[str, Any]:
    dashboard = _safe_call("plugin_dashboard", lambda: plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=True), {})
    diagnostics = dashboard.get("diagnostics", {}) if isinstance(dashboard.get("diagnostics"), dict) else {}
    status = diagnostics.get("status", "unknown")
    mapped = "blocked" if status == "error" else "warning" if status in {"warning", "unknown"} else "pass"
    return _check(
        "plugin_compatibility",
        "Plugin compatibility",
        mapped,
        f"{diagnostics.get('plugin_count', 0)} plugin(s); status={status}.",
        {"diagnostics": diagnostics},
    )


def _orchestration_compatibility_check(root: Path) -> dict[str, Any]:
    stats = _safe_call("workflow_statistics", lambda: workflow_statistics(root), {})
    active = int(stats.get("active_workflow_count") or 0) if isinstance(stats, dict) else 0
    failed = int(stats.get("failed_workflow_count") or 0) if isinstance(stats, dict) else 0
    status = "warning" if active > 20 or failed > 10 else "pass"
    return _check(
        "orchestration_compatibility",
        "Orchestration compatibility",
        status,
        f"Active workflows={active}; failed workflows={failed}.",
        {"statistics": stats},
    )


def _runtime_compatibility_check(root: Path) -> dict[str, Any]:
    distributed = _safe_call("distributed", lambda: distributed_runtime.observability(root), {})
    migrations = _safe_call("release_migrations", lambda: release.migration_status(root), {})
    pending = migrations.get("pending", []) if isinstance(migrations.get("pending"), list) else []
    nodes = distributed.get("nodes", {}) if isinstance(distributed.get("nodes"), dict) else {}
    status = "warning" if pending else "pass"
    return _check(
        "runtime_compatibility",
        "Runtime compatibility",
        status,
        f"Pending release migrations={len(pending)}; distributed nodes={nodes.get('total', 0)}.",
        {"distributed": distributed, "release_migrations": migrations},
    )


def _check(check_id: str, title: str, status: str, evidence: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status if status in {"pass", "warning", "blocked"} else "warning",
        "evidence": scrub(evidence),
        "details": details or {},
    }


def _compatibility_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = []
    for check in checks:
        if check["status"] == "blocked":
            actions.append(f"Resolve blocked {check['title']} before release adoption.")
        elif check["status"] == "warning":
            actions.append(f"Review warning in {check['title']} and decide whether it belongs in beta or experimental scope.")
    return actions or ["No compatibility action required."]


def _default_client_reports(root: Path) -> list[dict[str, Any]]:
    manifest = _safe_call("release_manifest", lambda: release.release_manifest(root), {})
    components = manifest.get("components", {}) if isinstance(manifest.get("components"), dict) else {}
    reports = []
    for client in ("website", "desktop", "vscode-extension", "visual-studio-extension"):
        component = components.get(client, {}) if isinstance(components.get(client), dict) else {}
        reports.append(
            {
                "client_type": client,
                "client_version": component.get("version", ""),
                "schema_version": component.get("minimum_compatible_schema") or release.RELEASE_SCHEMA_VERSION,
                "core_version": release.CORE_VERSION,
                "capabilities": ["release-compatibility"],
            }
        )
    return reports


def _plugin_dependencies(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    plugins = dashboard.get("plugins", []) if isinstance(dashboard.get("plugins"), list) else []
    dependencies = []
    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue
        deps = _dependency_ids(plugin.get("dependencies", []))
        compatibility = plugin.get("runtime_compatibility", {}) if isinstance(plugin.get("runtime_compatibility"), dict) else {}
        dependencies.append(
            {
                "plugin_id": plugin.get("id", ""),
                "enabled": bool(plugin.get("enabled")),
                "dependencies": deps,
                "runtime_compatibility": compatibility,
                "permission_scopes": list(plugin.get("permission_scopes") or []),
                "load_status": plugin.get("load_status", "unknown"),
            }
        )
    return dependencies


def _dependency_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            dep_id = str(item.get("id") or item.get("plugin_id") or item.get("name") or "").strip()
        else:
            dep_id = str(item).strip()
        if dep_id:
            result.append(dep_id)
    return result


def _provider_dependencies(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    providers = inventory.get("providers", []) if isinstance(inventory.get("providers"), list) else []
    results = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        results.append(
            {
                "provider_id": provider.get("id", ""),
                "provider_type": provider.get("provider_type", ""),
                "availability_status": provider.get("availability_status", provider.get("status", "")),
                "required_auth_method": provider.get("required_auth_method", ""),
                "privacy_level": provider.get("privacy_level", ""),
                "model_count": len(provider.get("models", []) if isinstance(provider.get("models"), list) else []),
            }
        )
    return results


def _runtime_dependencies(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    components = manifest.get("components", {}) if isinstance(manifest.get("components"), dict) else {}
    return [
        {
            "component": component_id,
            "version": component.get("version", ""),
            "minimum_core": component.get("minimum_compatible_core", ""),
            "minimum_schema": component.get("minimum_compatible_schema", ""),
        }
        for component_id, component in sorted(components.items())
        if isinstance(component, dict)
    ]


def _dependency_risks(plugins: list[dict[str, Any]], providers: list[dict[str, Any]], runtime: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for plugin in plugins:
        if plugin.get("load_status") == "rejected":
            risks.append({"area": "plugins", "severity": "high", "reason": f"{plugin.get('plugin_id')} is rejected."})
        if plugin.get("dependencies"):
            missing = [dep for dep in plugin["dependencies"] if not any(item.get("plugin_id") == dep for item in plugins)]
            if missing:
                risks.append({"area": "plugins", "severity": "medium", "reason": f"{plugin.get('plugin_id')} has missing dependencies: {', '.join(missing)}."})
    if not any(provider.get("provider_id") in {"ollama", "lm_studio"} and provider.get("availability_status") in {"available", "reachable", "online"} for provider in providers):
        risks.append({"area": "providers", "severity": "medium", "reason": "No reachable local model provider is visible."})
    if not runtime:
        risks.append({"area": "runtime", "severity": "medium", "reason": "Release manifest contains no component compatibility matrix."})
    return risks[:25]


def _script_status(root: Path, path: str) -> dict[str, Any]:
    script = root / path
    return {"path": path, "exists": script.is_file(), "size_bytes": script.stat().st_size if script.is_file() else 0}


def _subsystem_health(
    compatibility: dict[str, Any],
    migrations: dict[str, Any],
    plugins: dict[str, Any],
    workflows: dict[str, Any],
    runtime: dict[str, Any],
    distributed: dict[str, Any],
) -> list[dict[str, Any]]:
    pending = migrations.get("pending", []) if isinstance(migrations.get("pending"), list) else []
    runtime_obs = runtime.get("observability", {}) if isinstance(runtime.get("observability"), dict) else {}
    distributed_nodes = distributed.get("nodes", {}) if isinstance(distributed.get("nodes"), dict) else {}
    return [
        _health("compatibility", compatibility["overall_status"], f"{compatibility['summary']['blocked']} blocker(s), {compatibility['summary']['warning']} warning(s)."),
        _health("migrations", "warning" if pending else "pass", f"{len(pending)} pending platform migration(s)."),
        _health("plugins", "warning" if int(plugins.get("failure_count") or 0) else "pass", f"{int(plugins.get('failure_count') or 0)} plugin failure(s)."),
        _health("orchestration", "warning" if int(workflows.get("active_workflow_count") or 0) > 20 else "pass", f"{int(workflows.get('workflow_count') or 0)} workflow(s)."),
        _health("runtime_interaction", "warning" if int(runtime_obs.get("failed_jobs") or 0) else "pass", f"{int(runtime_obs.get('job_count') or 0)} runtime job(s)."),
        _health("distributed_runtime", "pass", f"{int(distributed_nodes.get('total') or 0)} node(s) registered."),
    ]


def _health(subsystem_id: str, status: str, evidence: str) -> dict[str, Any]:
    return {"id": subsystem_id, "status": status if status in {"pass", "warning", "blocked"} else "warning", "evidence": scrub(evidence)}


def _overall_health(subsystems: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in subsystems):
        return "blocked"
    if any(item["status"] == "warning" for item in subsystems):
        return "warning"
    return "pass"


def _migration_success_rate(migrations: dict[str, Any]) -> float:
    applied = len(migrations.get("applied", []) if isinstance(migrations.get("applied"), list) else [])
    pending = len(migrations.get("pending", []) if isinstance(migrations.get("pending"), list) else [])
    total = applied + pending
    return 1.0 if total == 0 else round(applied / total, 4)


def _regression_watchlist(compatibility: dict[str, Any], migrations: dict[str, Any], plugins: dict[str, Any]) -> list[dict[str, Any]]:
    watch = []
    for check in compatibility.get("checks", []):
        if check.get("status") != "pass":
            watch.append({"area": check.get("id"), "severity": "high" if check.get("status") == "blocked" else "medium", "reason": check.get("evidence", "")})
    pending = migrations.get("pending", []) if isinstance(migrations.get("pending"), list) else []
    if pending:
        watch.append({"area": "migrations", "severity": "medium", "reason": f"{len(pending)} platform migration(s) are pending."})
    if int(plugins.get("failure_count") or 0):
        watch.append({"area": "plugins", "severity": "medium", "reason": "Plugin failures exist in observability."})
    return watch[:25]


def _archive_candidates(
    aegis_root: Path,
    *,
    include_memory: bool,
    include_workflows: bool,
    include_knowledge: bool,
    include_checkpoints: bool,
) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    if not aegis_root.exists():
        return candidates
    skip_dirs = {PLATFORM_ARCHIVE_DIR, "alpha-diagnostics"}
    if not include_checkpoints:
        skip_dirs.add("backups")
    for path in aegis_root.rglob("*"):
        if len(candidates) >= MAX_ARCHIVE_FILES:
            break
        if any(part in skip_dirs for part in path.relative_to(aegis_root).parts):
            continue
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_ARCHIVE_FILE_BYTES:
                continue
        except OSError:
            continue
        category = _archive_category(path)
        if category == "memory" and not include_memory:
            continue
        if category == "workflows" and not include_workflows:
            continue
        if category == "knowledge" and not include_knowledge:
            continue
        if category == "checkpoints" and not include_checkpoints:
            continue
        candidates.append((path, category))
    return candidates


def _archive_category(path: Path) -> str:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if "backups" in parts or "checkpoint" in name:
        return "checkpoints"
    if any(token in name for token in ("workflow", "orchestration", "task", "agent")):
        return "workflows"
    if any(token in name for token in ("knowledge", "index", "graph", "architecture", "dependency", "symbol", "scan-cache")):
        return "knowledge"
    return "memory"


def _top_level_state_files(root: Path, *, suffixes: set[str]) -> list[dict[str, Any]]:
    files = []
    if not root.is_dir():
        return files
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix.lower() in suffixes:
            files.append({"path": path.name, "size_bytes": path.stat().st_size})
    return files


def _knowledge_state_files(root: Path) -> list[dict[str, Any]]:
    names = ("file-index.json", "symbol-index.json", "dependency-graph.json", "knowledge-graph.json", "scan-cache.json", "architecture-map.md")
    files = []
    for name in names:
        path = root / name
        if path.is_file():
            files.append({"path": name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    return files


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _safe_call(name: str, func, default: Any) -> Any:
    try:
        return func()
    except Exception as exc:  # defensive dashboard aggregation; callers get inspectable degradation.
        return {"status": "unavailable", "source": name, "error": scrub(str(exc))} if isinstance(default, dict) else default
