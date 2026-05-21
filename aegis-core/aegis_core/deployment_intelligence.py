from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .validation import detect_validation_commands


STATE_FILE = "deployment-workflows.json"
SCAN_FILE = "deployment-intelligence.json"
MEMORY_FILE = "deployment-environment-memory.json"
AUDIT_FILE = "deployment-audit.jsonl"

WORKFLOW_TYPES = {
    "build_project",
    "package_release",
    "run_ci",
    "validate_pipeline",
    "deploy_staging",
    "deploy_production",
    "rollback_release",
}

DEPLOYMENT_WORKFLOWS = {"deploy_staging", "deploy_production", "rollback_release"}
PRODUCTION_ENVIRONMENTS = {"prod", "production", "live"}
SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_dsa",
    "credentials",
    "credentials.json",
    "service-account.json",
}
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|credential|client[_-]?secret)\b\s*[:=]\s*['\"]?([^'\"\s${}][^'\"\s]{7,})"
)


class DeploymentIntelligenceError(RuntimeError):
    """Raised when deployment intelligence cannot safely inspect or mutate state."""


def deployment_dashboard(workspace: str | Path, *, refresh: bool = False, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = ProjectMemory(root)
    memory.ensure()
    scan = scan_environment(root, persist=refresh or not (memory.root / SCAN_FILE).is_file())
    state = _read_state(root)
    workflows = _sorted_workflows(state.get("workflows", []))[: max(1, min(300, int(limit)))]
    active = [item for item in workflows if item.get("status") in {"queued", "running", "waiting_approval", "paused", "validating"}]
    history = _sorted_history(state.get("release_history", []))[: max(1, min(300, int(limit)))]
    return {
        "schema_version": 1,
        "workspace": str(root),
        "generated_at": utc_now(),
        "environment": scan["environment"],
        "pipelines": scan["pipelines"],
        "infrastructure": scan["infrastructure"],
        "secrets": scan["secrets"],
        "validation": scan["validation"],
        "risk_summary": scan["risk_summary"],
        "suggestions": scan["suggestions"],
        "workflows": workflows,
        "active_workflows": active,
        "release_history": history,
        "rollback_readiness": _rollback_readiness(scan, history),
        "observability": deployment_observability(root, scan=scan, state=state),
        "plugin_hooks": _plugin_hooks(root),
        "safety_controls": _safety_controls(),
        "state_files": {
            "scan": str(memory.root / SCAN_FILE),
            "workflows": str(memory.root / STATE_FILE),
            "memory": str(memory.root / MEMORY_FILE),
            "audit": str(memory.root / AUDIT_FILE),
        },
    }


def scan_environment(workspace: str | Path, *, persist: bool = True) -> dict[str, Any]:
    root = _workspace_root(workspace)
    files = _candidate_files(root)
    pipelines = _detect_pipelines(root, files)
    infrastructure = _detect_infrastructure(root, files)
    environment = _environment_model(root, files, pipelines, infrastructure)
    secrets = _secret_boundaries(root, files, pipelines, infrastructure)
    validation = _validation_model(root, pipelines)
    risk_summary = _deployment_risks(pipelines, infrastructure, secrets, validation)
    suggestions = _suggestions(pipelines, infrastructure, secrets, validation, risk_summary)
    result = {
        "schema_version": 1,
        "workspace": str(root),
        "generated_at": utc_now(),
        "environment": environment,
        "pipelines": pipelines,
        "infrastructure": infrastructure,
        "secrets": secrets,
        "validation": validation,
        "risk_summary": risk_summary,
        "suggestions": suggestions,
        "observability": {
            "file_count": len(files),
            "pipeline_count": len(pipelines),
            "infrastructure_file_count": len(infrastructure.get("artifacts", [])),
            "secret_boundary_count": len(secrets.get("boundaries", [])),
            "risk_count": len(risk_summary.get("risks", [])),
        },
    }
    if persist:
        memory = ProjectMemory(root)
        memory.write_json(SCAN_FILE, result)
        _update_environment_memory(root, result)
        _audit(root, "deployment.scan", "completed", f"Detected {len(pipelines)} pipeline(s) and {len(infrastructure.get('artifacts', []))} infrastructure artifact(s).")
    return result


def validate_pipeline(workspace: str | Path, *, pipeline_id: str = "", dry_run: bool = True) -> dict[str, Any]:
    root = _workspace_root(workspace)
    scan = scan_environment(root, persist=True)
    pipelines = scan["pipelines"]
    if pipeline_id:
        pipelines = [item for item in pipelines if item["id"] == _safe_id(pipeline_id)]
    evaluations = [_pipeline_evaluation(item, scan) for item in pipelines]
    blockers = [risk for item in evaluations for risk in item["risks"] if risk.get("severity") in {"high", "critical"}]
    warnings = [risk for item in evaluations for risk in item["risks"] if risk.get("severity") == "medium"]
    result = {
        "workspace": str(root),
        "pipeline_id": _safe_id(pipeline_id) if pipeline_id else "",
        "dry_run": bool(dry_run),
        "evaluated_at": utc_now(),
        "ok": bool(evaluations) and not blockers,
        "evaluations": evaluations,
        "blockers": blockers,
        "warnings": warnings[:20],
        "recommended_validations": scan["validation"].get("recommended_commands", []),
        "deployment_readiness": _readiness_score(scan, blockers),
        "writes_performed": False,
    }
    _audit(root, "deployment.pipeline.validated", "blocked" if blockers else "completed", f"Validated {len(evaluations)} pipeline(s).", {"pipeline_id": pipeline_id})
    return result


def create_deployment_workflow(
    workspace: str | Path,
    workflow_type: str,
    *,
    target_environment: str = "staging",
    release_version: str = "",
    approval: bool = False,
    production_confirmed: bool = False,
    dry_run: bool = True,
    source_client: str = "unknown",
    notes: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    kind = _workflow_type(workflow_type)
    target = scrub(target_environment or "staging").lower()
    scan = scan_environment(root, persist=True)
    validation = validate_pipeline(root, dry_run=True)
    safety = _workflow_safety(kind, target, approval=approval, production_confirmed=production_confirmed, dry_run=dry_run, scan=scan, validation=validation)
    now = utc_now()
    workflow = {
        "workflow_id": f"deploy-{uuid.uuid4().hex[:12]}",
        "workflow_type": kind,
        "target_environment": target,
        "release_version": scrub(release_version),
        "status": _initial_status(safety),
        "created_at": now,
        "updated_at": now,
        "source_client": scrub(source_client or "unknown"),
        "dry_run": bool(dry_run),
        "approval": bool(approval),
        "production_confirmed": bool(production_confirmed),
        "notes": scrub(notes),
        "safety": safety,
        "environment_summary": _environment_summary(scan),
        "pipeline_validation": validation,
        "release_checkpoint": _release_checkpoint(scan, kind, target, release_version),
        "rollback_strategy": _rollback_strategy(scan, kind, target),
        "steps": _workflow_steps(kind, target, safety),
        "timeline": [
            {
                "event_id": f"deploy-event-{uuid.uuid4().hex[:10]}",
                "event_type": "deployment.workflow.created",
                "status": _initial_status(safety),
                "message": f"{kind} workflow created for {target}.",
                "created_at": now,
            }
        ],
    }
    state = _mutate_state(root, lambda state: state.setdefault("workflows", []).append(workflow))
    _audit(root, "deployment.workflow.created", workflow["status"], workflow["timeline"][0]["message"], {"workflow_id": workflow["workflow_id"], "workflow_type": kind})
    return {"workspace": str(root), "workflow": workflow, "dashboard": _workflow_dashboard(root, workflow["workflow_id"], state=state)}


def step_deployment_workflow(
    workspace: str | Path,
    workflow_id: str,
    *,
    action: str = "advance",
    approval: bool = False,
    production_confirmed: bool = False,
    validation_passed: bool = False,
    message: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_id(workflow_id)
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        workflow = _find_workflow(state, clean_id)
        previous = workflow.get("status", "queued")
        next_status = _next_status(workflow, action, approval=approval, production_confirmed=production_confirmed, validation_passed=validation_passed)
        workflow["status"] = next_status
        workflow["updated_at"] = now
        if approval:
            workflow["approval"] = True
        if production_confirmed:
            workflow["production_confirmed"] = True
        event = {
            "event_id": f"deploy-event-{uuid.uuid4().hex[:10]}",
            "event_type": f"deployment.workflow.{action}",
            "status": next_status,
            "previous_status": previous,
            "message": scrub(message or f"Action {action} moved workflow to {next_status}."),
            "created_at": now,
        }
        workflow.setdefault("timeline", []).append(event)
        if next_status in {"completed", "failed", "rolled_back"}:
            state.setdefault("release_history", []).append(_history_event(workflow, next_status, event))

    state = _mutate_state(root, update)
    workflow = _find_workflow(state, clean_id)
    _audit(root, f"deployment.workflow.{action}", workflow.get("status", "unknown"), message or action, {"workflow_id": clean_id})
    return {"workspace": str(root), "workflow": workflow, "dashboard": _workflow_dashboard(root, clean_id, state=state)}


def deployment_release_history(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _read_state(root)
    scan = _read_scan(root) or scan_environment(root, persist=True)
    history = _sorted_history(state.get("release_history", []))[: max(1, min(300, int(limit)))]
    return {
        "workspace": str(root),
        "release_history": history,
        "active_workflows": [item for item in _sorted_workflows(state.get("workflows", [])) if item.get("status") in {"queued", "running", "waiting_approval", "paused", "validating"}],
        "rollback_readiness": _rollback_readiness(scan, history),
        "release_notes_draft": _release_notes_draft(history, scan),
        "observability": deployment_observability(root, scan=scan, state=state),
    }


def deployment_observability(workspace: str | Path, *, scan: dict[str, Any] | None = None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    root = _workspace_root(workspace)
    scan = scan or _read_scan(root) or scan_environment(root, persist=True)
    state = state or _read_state(root)
    workflows = state.get("workflows", [])
    history = state.get("release_history", [])
    statuses = Counter(str(item.get("status") or "unknown") for item in workflows)
    release_statuses = Counter(str(item.get("status") or "unknown") for item in history)
    failed_pipelines = [item for item in scan.get("pipelines", []) if _pipeline_evaluation(item, scan)["risks"]]
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "workflow_count": len(workflows),
        "active_workflows": sum(statuses[status] for status in ("queued", "running", "waiting_approval", "paused", "validating")),
        "completed_workflows": statuses["completed"],
        "failed_workflows": statuses["failed"],
        "rollback_workflows": statuses["rolled_back"],
        "release_count": len(history),
        "deployment_successes": release_statuses["completed"],
        "deployment_failures": release_statuses["failed"],
        "rollback_count": release_statuses["rolled_back"],
        "pipeline_count": len(scan.get("pipelines", [])),
        "pipelines_with_risks": len(failed_pipelines),
        "flaky_validation_candidates": _flaky_candidates(history),
        "recurring_deployment_failures": _recurring_failures(history),
        "risk_count": len(scan.get("risk_summary", {}).get("risks", [])),
    }


def compact_summary(workspace: str | Path) -> dict[str, Any]:
    try:
        dashboard = deployment_dashboard(workspace, refresh=False, limit=25)
    except Exception as exc:
        return {"status": "error", "pipeline_count": 0, "active_workflows": 0, "risk_count": 0, "error": scrub(str(exc))}
    observability = dashboard.get("observability", {}) if isinstance(dashboard.get("observability"), dict) else {}
    return {
        "status": "ready",
        "pipeline_count": int(observability.get("pipeline_count") or len(dashboard.get("pipelines", []))),
        "active_workflows": int(observability.get("active_workflows") or 0),
        "risk_count": int(observability.get("risk_count") or len(dashboard.get("risk_summary", {}).get("risks", []))),
        "release_count": int(observability.get("release_count") or 0),
        "rollback_ready": bool(dashboard.get("rollback_readiness", {}).get("ready")),
    }


def _detect_pipelines(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    pipelines: list[dict[str, Any]] = []
    for path in files:
        rel = _rel(root, path)
        lower = rel.lower().replace("\\", "/")
        if lower.startswith(".github/workflows/") and lower.endswith((".yml", ".yaml")):
            pipelines.append(_pipeline(root, path, "github_actions"))
        elif lower == ".gitlab-ci.yml":
            pipelines.append(_pipeline(root, path, "gitlab_ci"))
        elif lower.startswith("azure-pipelines") and lower.endswith((".yml", ".yaml")):
            pipelines.append(_pipeline(root, path, "azure_pipelines"))
        elif lower.endswith("jenkinsfile") or lower == "jenkinsfile":
            pipelines.append(_pipeline(root, path, "jenkins"))
        elif lower == "package.json":
            pipelines.extend(_package_scripts(root, path))
        elif lower in {"build.ps1", "build.sh", "makefile"} or lower.startswith("scripts/"):
            if any(token in path.name.lower() for token in ("build", "test", "deploy", "release", "ci", "package")):
                pipelines.append(_pipeline(root, path, "local_script"))
    pipelines.sort(key=lambda item: item["id"])
    return pipelines


def _detect_infrastructure(root: Path, files: list[Path]) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    container_systems: set[str] = set()
    deployment_targets: set[str] = set()
    runtime_dependencies: set[str] = set()
    for path in files:
        rel = _rel(root, path)
        lower = rel.lower().replace("\\", "/")
        text = _read_text(path, limit=120000)
        if path.name.lower().startswith("dockerfile"):
            container_systems.add("docker")
            runtime_dependencies.update(_docker_dependencies(text))
            artifacts.append(_infra_artifact(root, path, "dockerfile", text))
        elif lower in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
            container_systems.add("docker_compose")
            deployment_targets.add("container_stack")
            artifacts.append(_infra_artifact(root, path, "docker_compose", text))
        elif lower.endswith((".yml", ".yaml")) and ("apiversion:" in text.lower() and "kind:" in text.lower()):
            deployment_targets.add("kubernetes")
            artifacts.append(_infra_artifact(root, path, "kubernetes_manifest", text))
        elif any(token in lower for token in ("terraform", ".tf")) and lower.endswith(".tf"):
            deployment_targets.add("terraform")
            artifacts.append(_infra_artifact(root, path, "terraform", text))
        elif any(token in lower for token in ("deploy", "release", "publish")) and lower.endswith((".ps1", ".sh", ".cmd", ".bat")):
            deployment_targets.add("scripted_deployment")
            artifacts.append(_infra_artifact(root, path, "deployment_script", text))
    return {
        "artifacts": artifacts,
        "container_systems": sorted(container_systems),
        "deployment_targets": sorted(deployment_targets),
        "runtime_dependencies": sorted(runtime_dependencies),
        "summaries": [_artifact_summary(item) for item in artifacts[:20]],
    }


def _environment_model(root: Path, files: list[Path], pipelines: list[dict[str, Any]], infrastructure: dict[str, Any]) -> dict[str, Any]:
    names = {_rel(root, path).lower().replace("\\", "/") for path in files}
    build_systems = []
    if "package.json" in names:
        build_systems.append("node")
    if "pyproject.toml" in names or "requirements.txt" in names:
        build_systems.append("python")
    if any(name.endswith(".sln") or name.endswith(".csproj") for name in names):
        build_systems.append("dotnet")
    if "cmakelists.txt" in names:
        build_systems.append("cmake")
    if "makefile" in names:
        build_systems.append("make")
    config_files = sorted(name for name in names if name.endswith((".env", ".json", ".toml", ".ini", ".yml", ".yaml")) and any(token in name for token in ("config", "settings", "env", "appsettings")))
    return {
        "development_environments": _development_environments(names),
        "build_systems": sorted(set(build_systems)),
        "ci_providers": sorted({pipeline["provider"] for pipeline in pipelines if pipeline["provider"] not in {"local_script", "package_script"}}),
        "deployment_targets": infrastructure.get("deployment_targets", []),
        "container_systems": infrastructure.get("container_systems", []),
        "runtime_dependencies": infrastructure.get("runtime_dependencies", []),
        "config_boundaries": _config_boundaries(config_files),
        "workspace_root": str(root),
    }


def _secret_boundaries(root: Path, files: list[Path], pipelines: list[dict[str, Any]], infrastructure: dict[str, Any]) -> dict[str, Any]:
    boundaries: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []
    for path in files:
        rel = _rel(root, path)
        name = path.name.lower()
        lower = rel.lower().replace("\\", "/")
        if name in SENSITIVE_FILE_NAMES or lower.endswith((".pem", ".key", ".p12", ".pfx")):
            boundaries.append({"path": rel, "kind": "sensitive_file", "risk": "high" if path.is_file() else "medium", "recommendation": "Keep this file out of generated model context and deployment artifacts."})
        if path.suffix.lower() in {".yml", ".yaml", ".json", ".env", ".toml", ".ini", ".ps1", ".sh"}:
            text = _read_text(path, limit=80000)
            for match in SECRET_VALUE_RE.finditer(text):
                token, value = match.group(1), match.group(2)
                if "secrets." in value.lower() or value.startswith("${"):
                    continue
                exposures.append({"path": rel, "key": scrub(token), "sample": scrub(value[:4] + "***"), "severity": "high"})
    for pipeline in pipelines:
        text = pipeline.get("raw_excerpt", "")
        if re.search(r"(?i)echo\s+.*(secret|token|password|\${{\s*secrets\.)", text):
            exposures.append({"path": pipeline["path"], "key": "pipeline_echo", "sample": "secret output risk", "severity": "high"})
    for artifact in infrastructure.get("artifacts", []):
        if any("secret" in risk.get("title", "").lower() for risk in artifact.get("risks", [])):
            exposures.append({"path": artifact["path"], "key": "infrastructure_secret", "sample": "secret reference risk", "severity": "medium"})
    return {
        "boundaries": boundaries[:50],
        "possible_exposures": exposures[:50],
        "policy": {
            "send_to_cloud_default": "blocked_for_sensitive_files",
            "deployment_logs": "redacted",
            "provider_credentials": "os_credential_store_only",
        },
    }


def _validation_model(root: Path, pipelines: list[dict[str, Any]]) -> dict[str, Any]:
    commands = detect_validation_commands(root)
    recommended = []
    for command in commands[:8]:
        if isinstance(command, dict):
            recommended.append({"name": command.get("name") or " ".join(command.get("command", [])), "command": command.get("command", []), "source": "core_validation"})
    coverage = {
        "has_build": any(item.get("has_build") for item in pipelines) or any("build" in " ".join(item.get("command", [])).lower() for item in recommended),
        "has_tests": any(item.get("has_tests") for item in pipelines) or any("test" in " ".join(item.get("command", [])).lower() for item in recommended),
        "has_lint": any(item.get("has_lint") for item in pipelines),
        "has_typecheck": any(item.get("has_typecheck") for item in pipelines),
    }
    return {"recommended_commands": recommended, "coverage": coverage, "missing": [key for key, value in coverage.items() if not value]}


def _deployment_risks(pipelines: list[dict[str, Any]], infrastructure: dict[str, Any], secrets: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    if not pipelines:
        risks.append(_risk("missing_ci", "high", "No CI pipeline or local build script was detected.", "Add at least build and test validation before release orchestration."))
    if validation.get("missing"):
        risks.append(_risk("missing_validation", "medium", f"Missing validation coverage: {', '.join(validation['missing'])}.", "Add build/test/lint/typecheck coverage where applicable."))
    for exposure in secrets.get("possible_exposures", []):
        risks.append(_risk("secret_exposure", exposure.get("severity", "high"), f"Possible secret exposure in {exposure.get('path')}.", "Move secrets to provider secret stores and redact deployment logs."))
    for pipeline in pipelines:
        risks.extend(pipeline.get("risks", []))
    for artifact in infrastructure.get("artifacts", []):
        risks.extend(artifact.get("risks", []))
    score = max(0, 100 - sum({"critical": 30, "high": 20, "medium": 9, "low": 3}.get(risk.get("severity"), 5) for risk in risks[:20]))
    return {
        "score": score,
        "level": "critical" if any(r.get("severity") == "critical" for r in risks) else "high" if any(r.get("severity") == "high" for r in risks) else "medium" if risks else "low",
        "risks": risks[:80],
    }


def _suggestions(
    pipelines: list[dict[str, Any]],
    infrastructure: dict[str, Any],
    secrets: dict[str, Any],
    validation: dict[str, Any],
    risk_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    suggestions = []
    if not pipelines:
        suggestions.append({"title": "Create a CI validation pipeline", "priority": "high", "action": "Add build and test checks before deployment workflows."})
    if validation.get("missing"):
        suggestions.append({"title": "Fill validation coverage gaps", "priority": "medium", "action": f"Add {', '.join(validation['missing'])} checks."})
    if secrets.get("possible_exposures"):
        suggestions.append({"title": "Move exposed secrets behind secret stores", "priority": "high", "action": "Use CI/provider secret references and redact logs."})
    if "docker" in infrastructure.get("container_systems", []) and not any(artifact.get("kind") == "docker_compose" for artifact in infrastructure.get("artifacts", [])):
        suggestions.append({"title": "Document container runtime invocation", "priority": "low", "action": "Add compose/devcontainer notes or release packaging metadata."})
    if risk_summary.get("level") in {"high", "critical"}:
        suggestions.append({"title": "Keep deployment workflows in dry-run mode", "priority": "high", "action": "Resolve high-risk findings before approving deployment."})
    return suggestions[:12]


def _pipeline(root: Path, path: Path, provider: str) -> dict[str, Any]:
    text = _read_text(path, limit=120000)
    rel = _rel(root, path)
    lower = text.lower()
    deploy_target = "production" if re.search(r"(?i)\b(prod|production|live)\b", text) else "staging" if "staging" in lower else ""
    pipeline = {
        "id": _safe_id(f"{provider}-{rel}"),
        "provider": provider,
        "path": rel,
        "name": path.stem or provider,
        "trigger_summary": _trigger_summary(provider, text),
        "has_build": "build" in lower,
        "has_tests": any(token in lower for token in ("test", "pytest", "vitest", "jest", "dotnet test", "go test")),
        "has_lint": "lint" in lower,
        "has_typecheck": any(token in lower for token in ("typecheck", "tsc", "mypy", "pyright")),
        "has_deploy": any(token in lower for token in ("deploy", "release", "publish", "kubectl", "helm", "az webapp", "aws ", "gcloud ")),
        "deployment_target": deploy_target,
        "raw_excerpt": scrub(text[:6000]),
        "risks": [],
        "best_practice_gaps": [],
    }
    _annotate_pipeline_risks(pipeline)
    return pipeline


def _package_scripts(root: Path, path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
    if not isinstance(scripts, dict):
        return []
    results = []
    for name, command in sorted(scripts.items()):
        if not any(token in str(name).lower() for token in ("build", "test", "lint", "type", "deploy", "release", "package", "ci")):
            continue
        pseudo = {
            "id": _safe_id(f"package-script-{name}"),
            "provider": "package_script",
            "path": _rel(root, path),
            "name": f"npm script: {name}",
            "trigger_summary": "manual/local script",
            "has_build": "build" in name.lower() or "build" in str(command).lower(),
            "has_tests": "test" in name.lower() or "test" in str(command).lower(),
            "has_lint": "lint" in name.lower() or "lint" in str(command).lower(),
            "has_typecheck": "type" in name.lower() or "tsc" in str(command).lower(),
            "has_deploy": "deploy" in name.lower() or "release" in name.lower(),
            "deployment_target": "production" if "prod" in str(command).lower() else "",
            "command": scrub(str(command)),
            "raw_excerpt": scrub(str(command)),
            "risks": [],
            "best_practice_gaps": [],
        }
        _annotate_pipeline_risks(pseudo)
        results.append(pseudo)
    return results


def _annotate_pipeline_risks(pipeline: dict[str, Any]) -> None:
    text = str(pipeline.get("raw_excerpt") or "").lower()
    risks = pipeline.setdefault("risks", [])
    gaps = pipeline.setdefault("best_practice_gaps", [])
    if pipeline.get("has_deploy") and pipeline.get("deployment_target") == "production":
        risks.append(_risk("production_deploy", "high", f"{pipeline['path']} appears to deploy to production.", "Require environment approvals and manual production confirmation."))
    if "pull_request_target" in text:
        risks.append(_risk("pull_request_target", "high", "GitHub Actions uses pull_request_target.", "Avoid running untrusted code with privileged tokens."))
    if re.search(r"curl .*\\|.*(sh|bash)", text) or re.search(r"wget .*\\|.*(sh|bash)", text):
        risks.append(_risk("pipe_to_shell", "high", "Pipeline pipes remote content into a shell.", "Pin checksums or vendor installer scripts."))
    if "secrets." in text and re.search(r"(?i)echo|write-host|printf", text):
        risks.append(_risk("secret_logging", "high", "Pipeline may echo secret references.", "Remove secret logging and rely on provider masking."))
    if "timeout-minutes" not in text and pipeline.get("provider") == "github_actions":
        gaps.append("No job timeout detected.")
    if not pipeline.get("has_tests"):
        gaps.append("No test step detected.")
    if not pipeline.get("has_build"):
        gaps.append("No build step detected.")


def _infra_artifact(root: Path, path: Path, kind: str, text: str) -> dict[str, Any]:
    lower = text.lower()
    risks = []
    if kind == "dockerfile" and re.search(r"(?i)from\s+.*:latest", text):
        risks.append(_risk("unpinned_image", "medium", f"{_rel(root, path)} uses a latest base image tag.", "Pin base image versions or digests for reproducible releases."))
    if kind in {"dockerfile", "deployment_script"} and re.search(r"curl .*\\|.*(sh|bash)|wget .*\\|.*(sh|bash)", lower):
        risks.append(_risk("pipe_to_shell", "high", f"{_rel(root, path)} pipes remote content into a shell.", "Use pinned installer artifacts with checksum verification."))
    if kind == "kubernetes_manifest" and "imagepullpolicy: always" in lower:
        risks.append(_risk("image_pull_policy", "medium", f"{_rel(root, path)} uses imagePullPolicy Always.", "Confirm release rollback can restore a known image digest."))
    if re.search(r"(?i)(password|token|secret)\s*[:=]\s*['\"]?[^'\"\s${}]{8,}", text):
        risks.append(_risk("inline_secret", "high", f"{_rel(root, path)} may include inline secret values.", "Move secrets to secret references and redact manifests."))
    return {
        "id": _safe_id(f"{kind}-{_rel(root, path)}"),
        "kind": kind,
        "path": _rel(root, path),
        "summary": _artifact_summary({"kind": kind, "path": _rel(root, path), "risks": risks}),
        "risks": risks,
    }


def _pipeline_evaluation(pipeline: dict[str, Any], scan: dict[str, Any]) -> dict[str, Any]:
    risks = list(pipeline.get("risks", []))
    if not pipeline.get("has_tests"):
        risks.append(_risk("missing_tests", "medium", f"{pipeline['path']} does not expose a test step.", "Add test validation before release."))
    if not pipeline.get("has_build"):
        risks.append(_risk("missing_build", "medium", f"{pipeline['path']} does not expose a build step.", "Add build validation before packaging."))
    gates = [
        {"id": "build", "passed": bool(pipeline.get("has_build")), "required": True},
        {"id": "tests", "passed": bool(pipeline.get("has_tests")), "required": True},
        {"id": "secrets", "passed": not scan.get("secrets", {}).get("possible_exposures"), "required": True},
        {"id": "production_approval", "passed": pipeline.get("deployment_target") != "production", "required": pipeline.get("deployment_target") == "production"},
    ]
    return {
        "pipeline_id": pipeline["id"],
        "provider": pipeline["provider"],
        "path": pipeline["path"],
        "ok": not any(risk.get("severity") in {"high", "critical"} for risk in risks),
        "gates": gates,
        "risks": risks,
        "best_practice_gaps": pipeline.get("best_practice_gaps", []),
    }


def _workflow_safety(
    workflow_type: str,
    target: str,
    *,
    approval: bool,
    production_confirmed: bool,
    dry_run: bool,
    scan: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    blockers = []
    warnings = []
    approval_required = workflow_type in DEPLOYMENT_WORKFLOWS or bool(validation.get("blockers"))
    if validation.get("blockers"):
        blockers.append("Pipeline validation has high-risk blockers.")
    if scan.get("secrets", {}).get("possible_exposures"):
        blockers.append("Possible secret exposure must be resolved before deployment.")
    if workflow_type == "deploy_production":
        approval_required = True
        if target not in PRODUCTION_ENVIRONMENTS:
            warnings.append("Production workflow target was not named production/live; confirm environment selection.")
        if not production_confirmed:
            blockers.append("Production deployment requires explicit production confirmation.")
    if workflow_type == "deploy_staging" and not dry_run and not approval:
        blockers.append("Non-dry-run staging deploy requires approval.")
    if workflow_type == "rollback_release" and not approval:
        blockers.append("Rollback coordination requires approval.")
    if approval_required and not approval:
        warnings.append("Approval is required before this workflow can leave dry-run/supervision mode.")
    return {
        "allowed": not blockers and (not approval_required or approval),
        "approval_required": approval_required,
        "production_confirmation_required": workflow_type == "deploy_production",
        "dry_run_required_until_approved": approval_required and not approval,
        "blockers": blockers,
        "warnings": warnings,
        "validation_before_deploy": True,
        "rollback_strategy_required": workflow_type in DEPLOYMENT_WORKFLOWS,
        "secret_scan_required": True,
    }


def _workflow_steps(workflow_type: str, target: str, safety: dict[str, Any]) -> list[dict[str, Any]]:
    stages = [
        ("intake", "Capture release/deployment intent."),
        ("environment_analysis", "Analyze CI/CD, infrastructure, dependencies, and secret boundaries."),
        ("pipeline_validation", "Validate detected pipelines and local validation commands."),
        ("approval", "Collect required approval gates."),
    ]
    if workflow_type in {"build_project", "run_ci", "validate_pipeline"}:
        stages.extend([("run_validation", "Run approved build/test/lint/type checks."), ("summary", "Record validation summary and risks.")])
    elif workflow_type == "package_release":
        stages.extend([("build_artifact", "Track release artifact plan."), ("release_notes", "Draft release notes from local history."), ("summary", "Record packaging readiness.")])
    elif workflow_type in {"deploy_staging", "deploy_production"}:
        stages.extend([("dry_run_deploy", "Perform dry-run or planned deployment preview."), ("deploy", f"Deploy to {target} only after approval."), ("post_deploy_validation", "Run validation after deploy."), ("rollback_ready", "Confirm rollback plan and checkpoint.")])
    else:
        stages.extend([("rollback_plan", "Plan rollback to prior known release."), ("rollback", "Coordinate approved rollback."), ("post_rollback_validation", "Validate rollback result.")])
    return [
        {
            "id": stage,
            "title": title,
            "status": "blocked" if stage == "approval" and safety.get("blockers") else "waiting_approval" if stage == "approval" and safety.get("approval_required") else "pending",
            "approval_required": stage in {"approval", "deploy", "rollback"} or safety.get("approval_required", False),
        }
        for stage, title in stages
    ]


def _next_status(workflow: dict[str, Any], action: str, *, approval: bool, production_confirmed: bool, validation_passed: bool) -> str:
    normalized = scrub(action or "advance").lower()
    if normalized == "cancel":
        return "cancelled"
    if normalized == "pause":
        return "paused"
    if normalized == "resume":
        return "queued"
    if normalized == "fail":
        return "failed"
    if normalized == "rollback":
        return "rolled_back" if approval else "waiting_approval"
    if normalized == "complete":
        if workflow.get("workflow_type") == "deploy_production" and not (approval and production_confirmed):
            return "waiting_approval"
        if workflow.get("safety", {}).get("blockers") and not approval:
            return "waiting_approval"
        return "completed" if validation_passed or workflow.get("dry_run") else "validating"
    if normalized == "approve":
        return "queued" if approval else "waiting_approval"
    current = workflow.get("status", "queued")
    if current == "queued":
        return "running"
    if current == "running":
        return "validating"
    if current == "validating":
        return "completed" if validation_passed else "waiting_approval"
    return current


def _initial_status(safety: dict[str, Any]) -> str:
    if safety.get("blockers") or safety.get("approval_required"):
        return "waiting_approval"
    return "queued"


def _workflow_dashboard(root: Path, workflow_id: str, *, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or _read_state(root)
    workflow = _find_workflow(state, workflow_id)
    return {
        "workspace": str(root),
        "workflow": workflow,
        "timeline": workflow.get("timeline", []),
        "release_history": _sorted_history(state.get("release_history", []))[:50],
        "observability": deployment_observability(root, state=state),
    }


def _candidate_files(root: Path) -> list[Path]:
    result: list[Path] = []
    skip_dirs = {".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".pytest_cache"}
    for path in root.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.is_file():
            try:
                if path.stat().st_size <= 1_500_000:
                    result.append(path)
            except OSError:
                continue
    return result[:5000]


def _read_state(root: Path) -> dict[str, Any]:
    path = ProjectMemory(root).root / STATE_FILE
    if not path.exists():
        return {"schema_version": 1, "workspace": str(root), "workflows": [], "release_history": [], "updated_at": utc_now()}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentIntelligenceError(f"Could not read deployment workflow state: {scrub(str(exc))}") from exc
    if not isinstance(data, dict):
        return {"schema_version": 1, "workspace": str(root), "workflows": [], "release_history": [], "updated_at": utc_now()}
    data.setdefault("workflows", [])
    data.setdefault("release_history", [])
    return data


def _write_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    ProjectMemory(root).write_json(STATE_FILE, state)


def _mutate_state(root: Path, mutator) -> dict[str, Any]:
    state = _read_state(root)
    mutator(state)
    state["workflows"] = _sorted_workflows(state.get("workflows", []))[:250]
    state["release_history"] = _sorted_history(state.get("release_history", []))[:500]
    _write_state(root, state)
    return state


def _read_scan(root: Path) -> dict[str, Any] | None:
    path = ProjectMemory(root).root / SCAN_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _update_environment_memory(root: Path, scan: dict[str, Any]) -> None:
    memory = {
        "workspace": str(root),
        "updated_at": utc_now(),
        "deployment_history_summary": "Release/deployment state is tracked through deployment workflows and release history.",
        "environment_configs": scan.get("environment", {}).get("config_boundaries", []),
        "recurring_failures": [],
        "infrastructure_decisions": scan.get("infrastructure", {}).get("summaries", []),
        "release_patterns": [pipeline.get("provider") for pipeline in scan.get("pipelines", [])],
    }
    ProjectMemory(root).write_json(MEMORY_FILE, memory)


def _audit(root: Path, event_type: str, status: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
    memory = ProjectMemory(root)
    memory.ensure()
    event = {
        "event_id": f"deploy-audit-{uuid.uuid4().hex[:12]}",
        "event_type": scrub(event_type),
        "status": scrub(status),
        "detail": scrub(detail),
        "metadata": _safe_metadata(metadata or {}),
        "created_at": utc_now(),
    }
    try:
        with (memory.root / AUDIT_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        return


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise DeploymentIntelligenceError(f"workspace does not exist or is not a directory: {scrub(str(root))}")
    return root


def _workflow_type(value: str) -> str:
    normalized = scrub(value or "").lower()
    if normalized not in WORKFLOW_TYPES:
        raise DeploymentIntelligenceError(f"unsupported deployment workflow type: {normalized}")
    return normalized


def _find_workflow(state: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    clean = _safe_id(workflow_id)
    for workflow in state.get("workflows", []):
        if workflow.get("workflow_id") == clean:
            return workflow
    raise DeploymentIntelligenceError(f"deployment workflow not found: {scrub(clean)}")


def _history_event(workflow: dict[str, Any], status: str, event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"release-{uuid.uuid4().hex[:12]}",
        "workflow_id": workflow.get("workflow_id"),
        "workflow_type": workflow.get("workflow_type"),
        "target_environment": workflow.get("target_environment"),
        "release_version": workflow.get("release_version"),
        "status": status,
        "summary": event.get("message", ""),
        "validation_summary": workflow.get("pipeline_validation", {}).get("deployment_readiness", {}),
        "rollback_strategy": workflow.get("rollback_strategy", {}),
        "created_at": utc_now(),
    }


def _rollback_readiness(scan: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    has_artifacts = bool(scan.get("infrastructure", {}).get("artifacts")) or bool(scan.get("pipelines"))
    prior_release = next((item for item in history if item.get("status") == "completed"), None)
    risks = scan.get("risk_summary", {}).get("risks", [])
    blockers = [risk for risk in risks if risk.get("severity") in {"critical", "high"}]
    return {
        "ready": bool(has_artifacts and not blockers),
        "has_prior_release": bool(prior_release),
        "latest_release_id": prior_release.get("id") if prior_release else "",
        "strategy": "Use release history plus deployment workflow rollback plan; execute only with approval.",
        "blockers": blockers[:8],
    }


def _release_checkpoint(scan: dict[str, Any], workflow_type: str, target: str, release_version: str) -> dict[str, Any]:
    return {
        "id": f"release-checkpoint-{uuid.uuid4().hex[:10]}",
        "release_version": scrub(release_version),
        "workflow_type": workflow_type,
        "target_environment": target,
        "pipeline_count": len(scan.get("pipelines", [])),
        "infrastructure_count": len(scan.get("infrastructure", {}).get("artifacts", [])),
        "created_at": utc_now(),
        "note": "Checkpoint records deployment metadata only; source rollback still uses Core editing/checkpoint contracts.",
    }


def _rollback_strategy(scan: dict[str, Any], workflow_type: str, target: str) -> dict[str, Any]:
    return {
        "required": workflow_type in DEPLOYMENT_WORKFLOWS,
        "target_environment": target,
        "steps": [
            "Confirm last known good release artifact or image digest.",
            "Run validation before rollback if the current environment is healthy enough.",
            "Apply rollback through the deployment provider only after explicit approval.",
            "Run post-rollback validation and record release history.",
        ],
        "readiness": _rollback_readiness(scan, []),
    }


def _readiness_score(scan: dict[str, Any], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    score = int(scan.get("risk_summary", {}).get("score") or 0) - min(40, len(blockers) * 12)
    score = max(0, min(100, score))
    return {"score": score, "status": "blocked" if blockers else "ready" if score >= 80 else "needs_review"}


def _release_notes_draft(history: list[dict[str, Any]], scan: dict[str, Any]) -> dict[str, Any]:
    latest = history[0] if history else {}
    return {
        "title": f"Release notes for {latest.get('release_version') or 'next local release'}",
        "sections": [
            {"title": "Deployment target", "body": latest.get("target_environment") or "No completed deployment recorded yet."},
            {"title": "Validation", "body": f"{len(scan.get('pipelines', []))} pipeline(s) detected; {scan.get('validation', {}).get('missing', [])} missing checks."},
            {"title": "Rollback", "body": "Rollback must be approved and recorded through Core deployment workflows."},
        ],
    }


def _flaky_candidates(history: list[dict[str, Any]]) -> list[str]:
    counts = Counter(str(item.get("workflow_type") or "unknown") for item in history if item.get("status") == "failed")
    return [key for key, count in counts.items() if count >= 2][:8]


def _recurring_failures(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(item.get("target_environment") or "unknown") for item in history if item.get("status") == "failed")
    return [{"environment": key, "failures": count} for key, count in counts.items() if count >= 2][:8]


def _development_environments(names: set[str]) -> list[str]:
    envs = []
    if ".devcontainer/devcontainer.json" in names:
        envs.append("devcontainer")
    if "docker-compose.yml" in names or "compose.yml" in names:
        envs.append("docker_compose")
    if "package.json" in names:
        envs.append("node")
    if "requirements.txt" in names or "pyproject.toml" in names:
        envs.append("python")
    if any(name.endswith(".sln") for name in names):
        envs.append("visual_studio")
    return sorted(set(envs)) or ["local_workspace"]


def _config_boundaries(files: list[str]) -> list[dict[str, Any]]:
    return [{"path": path, "boundary": "environment_config" if "env" in path else "runtime_config", "cloud_share": "redact_before_cloud"} for path in files[:80]]


def _docker_dependencies(text: str) -> set[str]:
    deps = set()
    for match in re.finditer(r"(?im)^\s*from\s+([^\s]+)", text):
        image = match.group(1)
        deps.add(image.split(":")[0].split("@")[0])
    return deps


def _trigger_summary(provider: str, text: str) -> str:
    lower = text.lower()
    if provider == "github_actions":
        if "pull_request" in lower and "push" in lower:
            return "push and pull_request"
        if "pull_request" in lower:
            return "pull_request"
        if "push" in lower:
            return "push"
    if "schedule" in lower or "cron" in lower:
        return "scheduled"
    return "manual or unspecified"


def _artifact_summary(item: dict[str, Any]) -> str:
    risk_count = len(item.get("risks", []))
    return f"{item.get('kind', 'artifact')} at {item.get('path', '')}" + (f" with {risk_count} risk(s)" if risk_count else "")


def _environment_summary(scan: dict[str, Any]) -> dict[str, Any]:
    env = scan.get("environment", {})
    return {
        "ci_providers": env.get("ci_providers", []),
        "build_systems": env.get("build_systems", []),
        "deployment_targets": env.get("deployment_targets", []),
        "risk_level": scan.get("risk_summary", {}).get("level", "unknown"),
    }


def _plugin_hooks(root: Path) -> dict[str, Any]:
    try:
        from . import plugin_runtime

        dashboard = plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=False)
    except Exception as exc:
        return {"status": "error", "error": scrub(str(exc)), "deployment_tools": [], "validators": [], "ui_extensions": []}
    plugins = dashboard.get("plugins", [])
    deployment_tools = [plugin for plugin in plugins if plugin.get("category") == "deployment_tools" or "deployment_tool" in plugin.get("capabilities", [])]
    hooks = dashboard.get("workflow_hooks", {}) if isinstance(dashboard.get("workflow_hooks"), dict) else {}
    return {
        "status": dashboard.get("diagnostics", {}).get("status", "ok"),
        "deployment_tools": [{"id": item.get("id"), "name": item.get("name"), "enabled": item.get("enabled")} for item in deployment_tools],
        "validators": hooks.get("validators", []),
        "ui_extensions": [item for item in dashboard.get("ui_extensions", []) if item.get("data_contract") in {"deployment.dashboard", "deployment.observability"}],
        "extension_points": ["ci_provider", "deployment_target", "container_analyzer", "infrastructure_validator", "observability_widget"],
    }


def _safety_controls() -> dict[str, Any]:
    return {
        "production_deploy": "requires approval and production_confirmed",
        "non_dry_run_deploy": "requires explicit approval",
        "secrets": "possible secret exposures block deployment workflows",
        "validation": "pipeline validation runs before deployment approval",
        "rollback": "rollback strategy is required for deployment workflows",
        "execution": "Core creates supervised workflow records; external deployment execution remains plugin/client-approved",
    }


def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[scrub(str(key))[:80]] = scrub(str(item))[:500] if isinstance(item, str) else item
    return result


def _risk(risk_id: str, severity: str, title: str, recommendation: str) -> dict[str, Any]:
    return {"id": risk_id, "severity": severity, "title": scrub(title), "recommendation": scrub(recommendation)}


def _safe_id(value: str) -> str:
    text = scrub(str(value or "")).strip().lower().replace("\\", "/").replace(" ", "-").replace("_", "-")
    clean = "".join(char for char in text if char.isalnum() or char in {"-", ".", "/"})
    return clean.replace("/", "-").strip("-.") or "deployment"


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return scrub(str(path))


def _read_text(path: Path, *, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _sorted_workflows(workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([item for item in workflows if isinstance(item, dict)], key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)


def _sorted_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([item for item in history if isinstance(item, dict)], key=lambda item: str(item.get("created_at") or ""), reverse=True)
