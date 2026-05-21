from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now


AUDIT_FILE = "stabilization-audit.json"
SUMMARY_FILE = "stabilization-summary.md"

SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".xaml",
}

SKIP_DIRS = {
    ".aegis",
    ".git",
    ".pytest_cache",
    ".tmp",
    ".venv",
    ".vscode-test",
    "__pycache__",
    "build",
    "Debug",
    "dist",
    "node_modules",
    "obj",
    "release",
    "Release",
    "venv",
    "x64",
}

VENDORED_ROOTS = {"imgui", "release"}
OVERSIZED_WARNING_LINES = 1200
OVERSIZED_CRITICAL_LINES = 5000


def stabilization_audit(
    workspace: str | Path | None = None,
    *,
    repo_root: str | Path | None = None,
    persist: bool = True,
    max_files: int = 8000,
) -> dict[str, Any]:
    """Build an inspectable production-readiness audit for the local repo.

    This is intentionally static and conservative. It does not mutate source
    files, run package managers, or launch clients. The output is meant to guide
    freeze/stabilization work and make architectural risk visible to every
    client through the same Core contract.
    """

    root = _repo_root(repo_root)
    project = _workspace_root(workspace, root)
    source_files = _source_files(root, max_files=max_files)
    findings: list[dict[str, Any]] = []

    module_metrics = _module_metrics(root, source_files)
    findings.extend(_oversized_module_findings(module_metrics))
    findings.extend(_duplication_findings(module_metrics))
    findings.extend(_contract_findings())
    findings.extend(_state_findings(project))
    findings.extend(_security_findings(root, source_files))
    findings.extend(_recovery_findings(project))

    findings = sorted(findings, key=_finding_sort_key)
    metrics = _metrics(root, project, module_metrics, findings)
    roadmap = roadmap_classification()
    governance = governance_rules()
    priorities = _freeze_priorities(findings)

    result = {
        "schema_version": 1,
        "workspace": str(project),
        "repo_root": str(root),
        "generated_at": utc_now(),
        "summary": _summary(metrics, findings, priorities),
        "metrics": metrics,
        "findings": findings,
        "refactor_candidates": _refactor_candidates(module_metrics, findings),
        "standardization": _standardization_snapshot(),
        "observability": _observability_snapshot(root, project),
        "startup_recovery": _startup_recovery_snapshot(project, findings),
        "security_posture": _security_posture_snapshot(findings),
        "performance_scalability": _performance_scalability_snapshot(module_metrics),
        "testing_strategy": testing_strategy(),
        "release_candidate_checklist": release_candidate_checklist(),
        "roadmap_classification": roadmap,
        "governance": governance,
        "freeze_priorities": priorities,
        "state_files": {
            "audit": str(ProjectMemory(project).root / AUDIT_FILE),
            "summary": str(ProjectMemory(project).root / SUMMARY_FILE),
        },
    }

    if persist:
        memory = ProjectMemory(project)
        memory.write_json(AUDIT_FILE, result)
        memory.write_generated_markdown(SUMMARY_FILE, "Platform Stabilization", _summary_markdown(result))
    return result


def governance_rules() -> dict[str, Any]:
    return {
        "api_stability": [
            "Every new /v1 response must use a registered contract kind and backward-compatible envelope.",
            "Experimental contracts may add optional fields, but must not remove or rename existing fields without a deprecation period.",
            "Client-facing route shape changes require Website, Desktop, VS Code, and Visual Studio compatibility notes.",
        ],
        "subsystem_ownership": [
            {"subsystem": "Core runtime contracts", "owner": "aegis-core", "stability_gate": "contract catalog and endpoint smoke tests"},
            {"subsystem": "Website gateway/API compatibility", "owner": "website/backend", "stability_gate": "Core delegation and fallback tests"},
            {"subsystem": "Desktop runtime client", "owner": "src desktop client", "stability_gate": "Release build and offline fallback smoke"},
            {"subsystem": "IDE clients", "owner": "vscode and visual-studio extensions", "stability_gate": "package/build plus Core-offline behavior"},
            {"subsystem": "Plugins/distributed runtime", "owner": "aegis-core experimental", "stability_gate": "permission, isolation, and trust tests"},
        ],
        "migration_policy": [
            "Prefer Core-owned runtime behavior with client fallback until two release candidates pass.",
            "Mark Website-owned runtime code as compatibility fallback, not the source of truth.",
            "Add migration docs before turning off any legacy path.",
        ],
        "deprecation_policy": [
            "Deprecated routes stay available for at least one minor release.",
            "Deprecation metadata must be visible in the Core contract envelope.",
            "Docs must list replacement endpoints and client migration expectations.",
        ],
        "security_review_required_for": [
            "filesystem write permissions",
            "process execution",
            "provider credential handling",
            "remote node trust changes",
            "update package verification",
            "plugin permission scope expansion",
        ],
        "release_freeze_rules": [
            "No new major subsystem during stabilization freeze.",
            "Only bug fixes, contract standardization, tests, docs, and targeted refactors are allowed.",
            "Release candidate requires Core tests, Website backend tests, frontend build, desktop build, extension package checks, and rollback/update smoke documentation.",
        ],
    }


def roadmap_classification() -> dict[str, list[dict[str, str]]]:
    return {
        "production_ready": [
            {"system": "Core contract envelope", "reason": "Stable response wrapper with versioned contracts."},
            {"system": "Core editing/checkpoint runtime", "reason": "Checkpoint-before-apply and unsafe path rejection are covered by tests."},
            {"system": "Validation command safety", "reason": "Command allowlist and output redaction are tested."},
            {"system": "Website Core gateway fallback", "reason": "Compatibility path keeps existing routes stable when Core is offline."},
        ],
        "experimental": [
            {"system": "Orchestration/task graph", "reason": "Useful contracts exist, but long-workflow stress coverage should expand."},
            {"system": "Multi-agent runtime", "reason": "Structured roles exist, but production autonomy remains approval-gated."},
            {"system": "Knowledge graph/workspace intelligence", "reason": "Indexing works locally, but large workspace performance needs baseline budgets."},
            {"system": "Quality gates and evaluation reports", "reason": "Blocking semantics exist, but gate policy tuning should continue."},
            {"system": "Deployment intelligence and optimization", "reason": "Core services exist and should stay advisory until release candidates prove reliability."},
        ],
        "prototype": [
            {"system": "Distributed remote execution", "reason": "Trust and fallback contracts exist, but real remote isolation needs a security pass."},
            {"system": "Voice interaction", "reason": "Provider-neutral contracts exist; provider implementation is optional and not release-critical."},
            {"system": "Collaboration/session supervision", "reason": "Local-first session contracts exist without SaaS-grade multi-user guarantees."},
        ],
        "deprecated": [
            {"system": "Website-owned apply/checkpoint/validation ownership", "reason": "Website should remain compatibility gateway while Core owns runtime state."},
            {"system": "Client-specific model/provider truth", "reason": "Clients should consume the Core registry and routing explanation contract."},
        ],
        "planned": [
            {"system": "Automated release candidate matrix", "reason": "Needs one-command validation across Core, Website, Desktop, and extensions."},
            {"system": "Installer/update smoke harness", "reason": "Release package rollback should be tested in clean environments."},
            {"system": "Large workspace performance budgets", "reason": "Indexing, graph queries, memory, streaming, and plugin counts need repeatable baselines."},
        ],
    }


def testing_strategy() -> dict[str, Any]:
    return {
        "required_before_release_candidate": [
            "Core unit and contract tests",
            "Core runtime editing/checkpoint/validation tests",
            "Website backend delegation and fallback tests",
            "Website frontend build and supervision/quality smoke tests",
            "Desktop Release build and Core-offline smoke",
            "VS Code extension compile/package smoke",
            "Visual Studio VSIX build smoke",
            "Plugin permission/isolation tests",
            "Distributed node registration/fallback tests",
            "Update checksum failure and rollback tests",
        ],
        "stress_targets": [
            {"target": "large workspace indexing", "budget": "record file count, duration, graph size, stale nodes"},
            {"target": "long workflow stability", "budget": "pause/resume/cancel/retry without corrupting .aegis state"},
            {"target": "many plugins", "budget": "load failures isolated and permission usage logged"},
            {"target": "many workflows", "budget": "activity feed and job lookup remain responsive"},
            {"target": "many memories/indexes", "budget": "memory browser and context retrieval stay bounded"},
        ],
        "recovery_cases": [
            "interrupted apply",
            "interrupted validation",
            "stale workflow after restart",
            "remote node disconnect",
            "corrupted .aegis JSON",
            "failed update and rollback",
        ],
    }


def release_candidate_checklist() -> list[dict[str, Any]]:
    return [
        {"id": "contracts", "title": "Contract catalog clean", "required": True, "evidence": "No non-schema contract descriptor lacks a data model."},
        {"id": "core-tests", "title": "Core test suite passes", "required": True, "evidence": "pytest output captured in release notes."},
        {"id": "website-tests", "title": "Website backend/frontend smoke passes", "required": True, "evidence": "backend pytest and frontend build/test output."},
        {"id": "desktop-build", "title": "Desktop Release build passes", "required": True, "evidence": "MSBuild/CMake output and manual offline smoke."},
        {"id": "extension-packages", "title": "IDE extensions package", "required": True, "evidence": "VS Code VSIX and Visual Studio VSIX artifacts."},
        {"id": "security", "title": "Security hardening verified", "required": True, "evidence": "path traversal, token, redaction, unsafe command, and checksum tests."},
        {"id": "update-rollback", "title": "Update rollback smoke passes", "required": True, "evidence": "failed checksum and failed apply restore previous version."},
        {"id": "docs", "title": "Docs match runtime contracts", "required": True, "evidence": "architecture map, migration notes, troubleshooting, and compatibility matrix updated."},
    ]


def _repo_root(repo_root: str | Path | None) -> Path:
    if repo_root:
        return Path(repo_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _workspace_root(workspace: str | Path | None, fallback: Path) -> Path:
    return Path(workspace).expanduser().resolve() if workspace else fallback


def _source_files(root: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
        base = Path(current)
        for name in names:
            path = base / name
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            files.append(path)
            if len(files) >= max_files:
                return files
    return files


def _module_metrics(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for path in files:
        rel = _rel(root, path)
        line_count = _line_count(path)
        metrics.append(
            {
                "path": rel,
                "lines": line_count,
                "extension": path.suffix.lower(),
                "role": _module_role(rel),
                "vendor": _is_vendor(rel),
            }
        )
    return sorted(metrics, key=lambda item: int(item["lines"]), reverse=True)


def _oversized_module_findings(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in metrics:
        lines = int(item["lines"])
        if lines < OVERSIZED_WARNING_LINES:
            continue
        vendor = bool(item.get("vendor"))
        severity = "critical" if lines >= OVERSIZED_CRITICAL_LINES and not vendor else "high"
        if vendor:
            severity = "low"
        findings.append(
            _finding(
                "oversized_module",
                severity,
                "Oversized module",
                f"{item['path']} has {lines} lines and should be split or classified as vendored/stable.",
                path=item["path"],
                owner=item["role"],
                recommendation=_refactor_recommendation(item),
            )
        )
    return findings[:40]


def _duplication_findings(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_stem: dict[str, list[str]] = defaultdict(list)
    interesting = re.compile(r"(client|runtime|workflow|validation|model|provider|checkpoint|memory|plugin|release)", re.I)
    for item in metrics:
        path = str(item["path"])
        if item.get("vendor"):
            continue
        stem = Path(path).stem.lower()
        if interesting.search(stem):
            by_stem[stem].append(path)
    findings: list[dict[str, Any]] = []
    for stem, paths in sorted(by_stem.items()):
        roots = {path.split("/")[0].split("\\")[0] for path in paths}
        if len(paths) < 3 or len(roots) < 2:
            continue
        findings.append(
            _finding(
                "duplicated_runtime_surface",
                "medium",
                "Duplicated runtime surface",
                f"{len(paths)} files named around '{stem}' exist across {len(roots)} top-level areas.",
                path="; ".join(paths[:6]),
                owner="cross-client",
                recommendation="Keep Core as source of truth and convert client copies into typed adapters/fallbacks.",
            )
        )
    return findings[:20]


def _contract_findings() -> list[dict[str, Any]]:
    from .contracts import CONTRACTS, CONTRACT_DATA_MODELS

    descriptors = set(CONTRACTS)
    mapped = set(CONTRACT_DATA_MODELS)
    schema_only = {key for key, descriptor in CONTRACTS.items() if descriptor.owner == "schema-only"}
    missing = sorted(descriptors - mapped - schema_only)
    extra = sorted(mapped - descriptors)
    findings: list[dict[str, Any]] = []
    for kind in missing:
        findings.append(
            _finding(
                "contract_missing_data_model",
                "high",
                "Contract descriptor lacks data-model validation",
                f"{kind} is registered but is not mapped in CONTRACT_DATA_MODELS.",
                owner="aegis-core",
                recommendation="Map the descriptor to a response data model or mark it schema-only with explicit compatibility notes.",
            )
        )
    for kind in extra:
        findings.append(
            _finding(
                "contract_model_without_descriptor",
                "medium",
                "Contract data model lacks descriptor",
                f"{kind} has a data model mapping but no contract descriptor.",
                owner="aegis-core",
                recommendation="Add a ContractDescriptor so clients can inspect stability and owner metadata.",
            )
        )
    return findings


def _state_findings(workspace: Path) -> list[dict[str, Any]]:
    memory = ProjectMemory(workspace)
    root = memory.root
    findings: list[dict[str, Any]] = []
    if not root.exists():
        return findings
    for path in list(root.glob("*.json"))[:200]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                _finding(
                    "corrupted_state_file",
                    "high",
                    "Corrupted .aegis JSON state",
                    f"{path.name} could not be parsed: {scrub(str(exc))}",
                    path=str(path),
                    owner="startup-recovery",
                    recommendation="Quarantine or repair the state file during Core startup before workflows resume.",
                )
            )
        except OSError as exc:
            findings.append(
                _finding(
                    "unreadable_state_file",
                    "medium",
                    "Unreadable .aegis state file",
                    f"{path.name} could not be read: {scrub(str(exc))}",
                    path=str(path),
                    owner="startup-recovery",
                    recommendation="Report the state file as degraded and continue in safe mode.",
                )
            )
    return findings


def _security_findings(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    secret_pattern = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\n]{8,}['\"]")
    findings: list[dict[str, Any]] = []
    for path in files[:6000]:
        rel = _rel(root, path)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if _is_vendor(rel) or size > 500_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = secret_pattern.search(text)
        if match:
            role = _module_role(rel)
            context = text[max(0, match.start() - 180) : min(len(text), match.end() + 180)].lower()
            fixture_or_template = (
                role == "test_monolith"
                or "$" in context
                or "[redacted]" in context
                or "regex" in context
                or 'r"(' in context
                or "+ token" in context
                or "authorization: bearer" in context
            )
            severity = "low" if fixture_or_template else "critical"
            title = "Secret-like fixture or template" if fixture_or_template else "Possible inline secret"
            findings.append(
                _finding(
                    "possible_inline_secret",
                    severity,
                    title,
                    f"{rel} contains a secret-like assignment pattern.",
                    path=rel,
                    owner="security",
                    recommendation="Confirm this is a placeholder/test fixture or move real credentials to the OS credential store and redact logs.",
                )
            )
    return findings[:20]


def _recovery_findings(workspace: Path) -> list[dict[str, Any]]:
    memory = ProjectMemory(workspace)
    root = memory.root
    findings: list[dict[str, Any]] = []
    if root.exists():
        tmp_files = sorted(str(path) for path in root.glob("*.tmp"))
        for path in tmp_files[:20]:
            findings.append(
                _finding(
                    "stale_temp_state",
                    "medium",
                    "Stale temporary state file",
                    f"{Path(path).name} is left under .aegis and may indicate an interrupted write.",
                    path=path,
                    owner="startup-recovery",
                    recommendation="Clean up temp state after validating the durable state file.",
                )
            )
    return findings


def _metrics(root: Path, workspace: Path, module_metrics: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, Any]:
    line_total = sum(int(item["lines"]) for item in module_metrics)
    severity_counts = Counter(item["severity"] for item in findings)
    role_counts = Counter(item["role"] for item in module_metrics)
    return {
        "repo_root": str(root),
        "workspace": str(workspace),
        "source_file_count": len(module_metrics),
        "source_line_count": line_total,
        "oversized_module_count": sum(1 for item in module_metrics if int(item["lines"]) >= OVERSIZED_WARNING_LINES and not item.get("vendor")),
        "vendored_large_module_count": sum(1 for item in module_metrics if int(item["lines"]) >= OVERSIZED_WARNING_LINES and item.get("vendor")),
        "finding_count": len(findings),
        "finding_severity_counts": dict(severity_counts),
        "module_role_counts": dict(role_counts),
        "largest_modules": module_metrics[:15],
    }


def _standardization_snapshot() -> dict[str, Any]:
    from .contracts import CONTRACTS, CONTRACT_DATA_MODELS

    descriptors = set(CONTRACTS)
    mapped = set(CONTRACT_DATA_MODELS)
    schema_only = sorted(key for key, descriptor in CONTRACTS.items() if descriptor.owner == "schema-only")
    return {
        "contract_count": len(CONTRACTS),
        "data_model_count": len(CONTRACT_DATA_MODELS),
        "schema_only_contracts": schema_only,
        "missing_data_models": sorted(descriptors - mapped - set(schema_only)),
        "extra_data_models": sorted(mapped - descriptors),
        "stability_counts": dict(Counter(descriptor.stability for descriptor in CONTRACTS.values())),
        "response_envelope_required": True,
    }


def _observability_snapshot(root: Path, workspace: Path) -> dict[str, Any]:
    docs = root / "docs"
    return {
        "structured_logging": True,
        "workflow_tracing": True,
        "runtime_metrics": True,
        "plugin_metrics": True,
        "validation_telemetry": True,
        "crash_reporting": "local logs and recovery state; external crash upload is intentionally absent",
        "docs_present": {
            "security": (docs / "SECURITY_PRIVACY_TRUST.md").is_file(),
            "release": (docs / "RELEASE_PACKAGING_AND_UPDATES.md").is_file(),
            "quality": (docs / "QUALITY_GATES.md").is_file(),
            "runtime": (docs / "REAL_TIME_ENGINEERING_INTERACTION.md").is_file(),
            "stabilization": (docs / "PLATFORM_STABILIZATION_AND_PRODUCTION_READINESS.md").is_file(),
        },
        "aegis_state_root": str(ProjectMemory(workspace).root),
    }


def _startup_recovery_snapshot(workspace: Path, findings: list[dict[str, Any]]) -> dict[str, Any]:
    recovery_findings = [item for item in findings if item["category"] in {"corrupted_state_file", "stale_temp_state", "unreadable_state_file"}]
    return {
        "safe_mode_needed": bool(recovery_findings),
        "state_findings": recovery_findings,
        "recommended_startup_policy": [
            "Parse .aegis state before resuming workflows.",
            "Quarantine corrupt JSON and keep Core online in safe mode.",
            "Require explicit user action before retrying interrupted apply/update flows.",
            "Reconcile active terminal jobs and distributed workloads after restart.",
        ],
    }


def _security_posture_snapshot(findings: list[dict[str, Any]]) -> dict[str, Any]:
    security_findings = [item for item in findings if item.get("owner") == "security"]
    return {
        "critical_findings": [item for item in security_findings if item["severity"] == "critical"],
        "plugin_permission_review_required": True,
        "local_api_review_required": True,
        "distributed_trust_review_required": True,
        "update_verification_review_required": True,
        "credential_storage_review_required": True,
    }


def _performance_scalability_snapshot(module_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    hot_modules = [item for item in module_metrics if not item.get("vendor") and int(item["lines"]) >= OVERSIZED_WARNING_LINES][:12]
    return {
        "profiling_required_for": [
            "workspace indexing",
            "knowledge graph queries",
            "workflow event streaming",
            "frontend rendering",
            "desktop runtime polling",
            "plugin discovery/loading",
            "distributed workload scheduling",
        ],
        "large_workspace_budgets_needed": True,
        "hot_modules": hot_modules,
        "recommended_limits": {
            "default_index_file_limit": "record and enforce per workspace profile",
            "workflow_event_retention": "bounded by workflow and time window",
            "plugin_load_timeout": "required before enabling third-party plugin code",
            "terminal_job_timeout": "required for every workflow-launched process",
        },
    }


def _freeze_priorities(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priorities = [
        {
            "priority": "P0",
            "title": "Keep the contract catalog clean",
            "reason": "Clients cannot safely migrate if Core descriptors and data models drift.",
            "finding_categories": ["contract_missing_data_model", "contract_model_without_descriptor"],
        },
        {
            "priority": "P0",
            "title": "Preserve apply/checkpoint/validation safety",
            "reason": "Runtime trust depends on checkpoint-before-write, unsafe-path rejection, and validation evidence.",
            "finding_categories": ["corrupted_state_file", "stale_temp_state"],
        },
        {
            "priority": "P1",
            "title": "Split client and backend monoliths",
            "reason": "Large modules make regression review and release candidate hardening slower.",
            "finding_categories": ["oversized_module", "duplicated_runtime_surface"],
        },
        {
            "priority": "P1",
            "title": "Expand release candidate automation",
            "reason": "The ecosystem now spans Core, Website, Desktop, VS Code, Visual Studio, plugins, and distributed runtime.",
            "finding_categories": ["missing_release_validation"],
        },
        {
            "priority": "P2",
            "title": "Add performance budgets",
            "reason": "Large workspace indexing, graph queries, and live streaming need repeatable limits before production use.",
            "finding_categories": ["oversized_module"],
        },
    ]
    counts = Counter(item["category"] for item in findings)
    for item in priorities:
        item["matched_findings"] = sum(counts.get(category, 0) for category in item["finding_categories"])
    return priorities


def _refactor_candidates(module_metrics: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paths_with_findings = {item.get("path") for item in findings if item.get("category") == "oversized_module"}
    candidates: list[dict[str, Any]] = []
    for item in module_metrics:
        if item["path"] not in paths_with_findings or item.get("vendor"):
            continue
        candidates.append(
            {
                "path": item["path"],
                "lines": item["lines"],
                "role": item["role"],
                "recommended_split": _split_strategy(item),
                "release_risk": "high" if int(item["lines"]) >= OVERSIZED_CRITICAL_LINES else "medium",
            }
        )
    return candidates[:20]


def _split_strategy(item: dict[str, Any]) -> list[str]:
    role = str(item.get("role", "runtime_service"))
    if role == "frontend_shell":
        return ["routes/views", "data hooks", "feature panels", "shared typed UI contracts"]
    if role == "extension_monolith":
        return ["core client", "command handlers", "views", "safety gates", "logging/state"]
    if role == "desktop_shell":
        return ["runtime status panel", "workflow supervision panel", "Core client adapters", "render helpers"]
    if role == "backend_route_module":
        return ["router modules", "service adapters", "schema-only DTOs", "fallback services"]
    if role == "contract_catalog":
        return ["request models", "response data models", "descriptor registry", "contract tests"]
    return ["feature-owned service", "typed DTOs", "persistence adapter", "focused tests"]


def _summary(metrics: dict[str, Any], findings: list[dict[str, Any]], priorities: list[dict[str, Any]]) -> dict[str, Any]:
    highest = next((item for item in findings if item["severity"] in {"critical", "high"}), None)
    return {
        "status": "blocked" if highest and highest["severity"] == "critical" else "needs_stabilization",
        "headline": "Platform stabilization should freeze new subsystems and focus on contract hygiene, monolith reduction, recovery, and release validation.",
        "top_risk": highest["title"] if highest else "No high-severity static finding detected.",
        "source_files_scanned": metrics["source_file_count"],
        "findings": metrics["finding_count"],
        "top_priorities": priorities[:3],
    }


def _summary_markdown(result: dict[str, Any]) -> str:
    lines = [
        "## Stabilization Snapshot",
        "",
        f"- Repo root: `{result['repo_root']}`",
        f"- Source files scanned: {result['metrics']['source_file_count']}",
        f"- Findings: {result['metrics']['finding_count']}",
        f"- Oversized non-vendor modules: {result['metrics']['oversized_module_count']}",
        "",
        "## Freeze Priorities",
        "",
    ]
    for item in result["freeze_priorities"]:
        lines.append(f"- {item['priority']}: {item['title']} ({item['matched_findings']} matching findings)")
    lines.extend(["", "## Largest Refactor Candidates", ""])
    for item in result["refactor_candidates"][:10]:
        lines.append(f"- `{item['path']}` ({item['lines']} lines): {', '.join(item['recommended_split'])}")
    return "\n".join(lines).rstrip() + "\n"


def _finding(
    category: str,
    severity: str,
    title: str,
    detail: str,
    *,
    path: str = "",
    owner: str = "aegis-core",
    recommendation: str = "",
) -> dict[str, Any]:
    digest = hashlib.sha1(f"{category}|{title}|{path}|{detail}".encode("utf-8")).hexdigest()[:12]
    return {
        "id": f"{category}:{digest}",
        "category": category,
        "severity": severity,
        "title": title,
        "detail": scrub(detail),
        "path": scrub(path),
        "owner": owner,
        "recommendation": recommendation,
    }


def _finding_sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return (order.get(item.get("severity", "low"), 4), str(item.get("category", "")), str(item.get("path", "")))


def _line_count(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _module_role(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("imgui/") or normalized.startswith("release/"):
        return "third_party_or_release_artifact"
    if normalized == "website/frontend/src/App.tsx":
        return "frontend_shell"
    if normalized.endswith("/extension.js"):
        return "extension_monolith"
    if normalized.startswith("src/"):
        return "desktop_shell" if "AegisChatApp" in normalized else "desktop_runtime"
    if "/tests/" in normalized or normalized.startswith("website/backend/tests/") or ".test." in normalized:
        return "test_monolith"
    if normalized.endswith("server.py") or normalized.endswith("main.py"):
        return "backend_route_module"
    if normalized.endswith("contracts.py") or normalized.endswith("schemas.py") or normalized.endswith("types.ts"):
        return "contract_catalog"
    if normalized.startswith("aegis-core/aegis_core/"):
        return "core_runtime_service"
    if normalized.startswith("website/backend/"):
        return "website_backend_service"
    if normalized.startswith("website/frontend/"):
        return "website_frontend"
    if normalized.startswith("visual-studio-extensions/"):
        return "visual_studio_extension"
    if normalized.startswith("vscode-plugins/"):
        return "vscode_extension"
    return "runtime_service"


def _is_vendor(path: str) -> bool:
    first = path.replace("\\", "/").split("/", 1)[0]
    return first in VENDORED_ROOTS


def _refactor_recommendation(item: dict[str, Any]) -> str:
    if item.get("vendor"):
        return "Classify as vendored/stable and exclude from active refactor churn unless patched deliberately."
    return "Split into feature-owned modules with typed contracts and focused tests before adding more behavior."


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
