from __future__ import annotations

import ast
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .safety import is_ignored_path, is_safe_to_edit, is_secret_like
from .validation import detect_validation_commands


QUALITY_GATES_FILE = "quality-gate-runs.json"
EVALUATION_REPORTS_FILE = "evaluation-reports.json"
BENCHMARK_HISTORY_FILE = "benchmark-history.json"
MAX_STORED_ITEMS = 200

DEFAULT_MAX_FILES_CHANGED = 25
RESTRICTED_PATH_PREFIXES = (
    ".git/",
    ".aegis/checkpoints/",
    ".aegis/quality-gate-runs.json",
    ".aegis/evaluation-reports.json",
    ".aegis/benchmark-history.json",
)
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "packages.config",
    "packages.lock.json",
    "Directory.Packages.props",
}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".cpp", ".c", ".h", ".hpp"}
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".lib",
    ".a",
    ".obj",
    ".pdb",
}


class QualityGatePersistenceError(RuntimeError):
    """Raised when Core quality gate state cannot be persisted."""


class QualityGateEvaluationNotFoundError(KeyError):
    """Raised when a quality gate run or report cannot be found."""


def evaluate_quality_gates(
    workspace: str | Path,
    *,
    changes: list[dict[str, Any]] | None = None,
    workflow_id: str | None = None,
    validation_id: str | None = None,
    validation: dict[str, Any] | None = None,
    approval: bool = False,
    checkpoint_id: str | None = None,
    max_files_changed: int = DEFAULT_MAX_FILES_CHANGED,
    restricted_paths: list[str] | None = None,
    validation_required: bool = False,
    dry_run: bool = False,
    metadata: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    normalized_changes, path_warnings = _normalize_changes(root, changes or [])
    latest_validation = validation or _latest_validation_result(memory, validation_id=validation_id)
    detected_validation = [item.__dict__ for item in detect_validation_commands(root)]
    changed_paths = [change["path"] for change in normalized_changes]
    file_count = len(changed_paths)
    max_files = max(1, min(250, int(max_files_changed or DEFAULT_MAX_FILES_CHANGED)))
    restricted = _restricted_path_hits(changed_paths, restricted_paths or [])
    unsafe = _unsafe_path_hits(root, changed_paths)
    binary_hits = [path for path in changed_paths if Path(path).suffix.lower() in BINARY_SUFFIXES]
    dependency_hits = [path for path in changed_paths if Path(path).name in DEPENDENCY_FILES]
    source_hits = [path for path in changed_paths if Path(path).suffix.lower() in SOURCE_SUFFIXES]
    delete_hits = [path for path in changed_paths if _change_action(normalized_changes, path) == "delete"]
    validation_state = _validation_state(latest_validation, detected_validation)
    syntax_result = _syntax_gate(root, normalized_changes)

    gates = [
        syntax_result,
        _validation_gate("build_check", "Build check", validation_state, ("build", "dotnet", "cargo", "cmake"), validation_required),
        _validation_gate("test_check", "Test check", validation_state, ("test", "pytest", "ctest"), validation_required),
        _validation_gate("lint_check", "Lint check", validation_state, ("lint", "ruff", "eslint"), False),
        _validation_gate("type_check", "Type check", validation_state, ("typecheck", "type-check", "mypy", "pyright", "tsc"), False),
        _security_gate(unsafe, restricted, binary_hits, normalized_changes),
        _dependency_gate(dependency_hits),
        _file_change_gate(file_count, max_files, source_hits, delete_hits),
        _rollback_gate(checkpoint_id, bool(normalized_changes), dry_run),
        _approval_gate(approval, restricted, unsafe, file_count, max_files, delete_hits),
    ]
    blockers = [
        {
            "gate_id": gate["id"],
            "label": gate["label"],
            "reason": gate["summary"],
            "severity": gate["severity"],
        }
        for gate in gates
        if gate.get("blocks_apply")
    ]
    warnings = path_warnings + [
        gate["summary"]
        for gate in gates
        if gate.get("status") == "warning" and gate.get("summary")
    ]
    scorecard = _scorecard(gates, validation_state, file_count, max_files, dependency_hits, delete_hits, blockers)
    evaluation = {
        "id": f"quality-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "workflow_id": workflow_id,
        "validation_id": validation_id or _record_id(latest_validation),
        "created_at": utc_now(),
        "status": "blocked" if blockers else ("warning" if warnings else "passed"),
        "apply_allowed": not blockers,
        "dry_run": dry_run,
        "checkpoint_id": checkpoint_id,
        "approval": approval,
        "gates": gates,
        "scorecard": scorecard,
        "blockers": blockers,
        "warnings": warnings[:30],
        "changed_files": changed_paths,
        "file_count": file_count,
        "validation": validation_state,
        "metadata": _safe_metadata(metadata),
        "required_actions": _required_actions(blockers, warnings, validation_required, checkpoint_id),
        "summary": _evaluation_summary(blockers, warnings, scorecard),
    }
    if persist:
        _append_json_record(memory, QUALITY_GATES_FILE, evaluation)
    return evaluation


def quality_gate_dashboard(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    runs = _read_json(memory.root / QUALITY_GATES_FILE, [])
    reports = _read_json(memory.root / EVALUATION_REPORTS_FILE, [])
    benchmarks = _read_json(memory.root / BENCHMARK_HISTORY_FILE, [])
    if not isinstance(runs, list):
        runs = []
    if not isinstance(reports, list):
        reports = []
    if not isinstance(benchmarks, list):
        benchmarks = []
    recent_runs = [item for item in runs if isinstance(item, dict)]
    recent_reports = [item for item in reports if isinstance(item, dict)]
    recent_benchmarks = [item for item in benchmarks if isinstance(item, dict)]
    latest = recent_runs[-1] if recent_runs else None
    max_items = max(1, min(200, int(limit)))
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "latest": latest,
        "recent_runs": list(reversed(recent_runs[-max_items:])),
        "reports": list(reversed(recent_reports[-max_items:])),
        "benchmark_history": list(reversed(recent_benchmarks[-max_items:])),
        "benchmark_suites": benchmark_suites(),
        "statistics": _quality_statistics(recent_runs, recent_reports, recent_benchmarks),
    }


def workflow_quality(workspace: str | Path, workflow_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    runs = [
        item
        for item in _read_json(memory.root / QUALITY_GATES_FILE, [])
        if isinstance(item, dict) and str(item.get("workflow_id") or "") == workflow_id
    ]
    reports = [
        item
        for item in _read_json(memory.root / EVALUATION_REPORTS_FILE, [])
        if isinstance(item, dict) and str(item.get("workflow_id") or "") == workflow_id
    ]
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "workflow_id": workflow_id,
        "latest": runs[-1] if runs else None,
        "runs": list(reversed(runs[-50:])),
        "reports": list(reversed(reports[-20:])),
        "statistics": _quality_statistics(runs, reports, []),
    }


def benchmark_suites() -> list[dict[str, Any]]:
    return [
        {
            "id": "coding_task_quality",
            "label": "Coding Task Quality",
            "description": "Scores gate pass rate, file-change risk, and validation readiness for code workflows.",
            "metrics": ["completion_score", "validation_score", "risk_score"],
        },
        {
            "id": "repair_accuracy",
            "label": "Repair Accuracy",
            "description": "Tracks whether repair workflows converge with fewer failed validation loops.",
            "metrics": ["repair_score", "validation_success_rate"],
        },
        {
            "id": "validation_success",
            "label": "Validation Success",
            "description": "Measures recent validation pass/fail outcomes and command availability.",
            "metrics": ["validation_score", "latest_validation_status"],
        },
        {
            "id": "routing_decisions",
            "label": "Routing Decisions",
            "description": "Checks whether model routing and workflow metadata are recorded for inspectability.",
            "metrics": ["model_usage_tracking", "route_explanation_present"],
        },
        {
            "id": "model_provider_performance",
            "label": "Model Provider Performance",
            "description": "Records provider benchmark placeholders and observed route quality metadata when available.",
            "metrics": ["latency_estimate", "provider_reliability"],
        },
        {
            "id": "agent_handoff_reliability",
            "label": "Agent Handoff Reliability",
            "description": "Measures workflow task handoffs, escalation frequency, and completion/blocked rates.",
            "metrics": ["handoff_success_rate", "approval_blockers"],
        },
    ]


def run_benchmark_suite(
    workspace: str | Path,
    *,
    suite_ids: list[str] | None = None,
    workflow_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    requested = {str(item).strip() for item in suite_ids or [] if str(item).strip()}
    suites = [suite for suite in benchmark_suites() if not requested or suite["id"] in requested]
    dashboard = quality_gate_dashboard(root, limit=50)
    health = quality_dashboard(root)
    results = [_benchmark_result(root, suite, dashboard, health, workflow_id) for suite in suites]
    run = {
        "id": f"benchmark-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "workflow_id": workflow_id,
        "created_at": utc_now(),
        "suite_ids": [suite["id"] for suite in suites],
        "status": "passed" if all(result["status"] == "passed" for result in results) else "warning",
        "score": round(sum(result["score"] for result in results) / len(results), 3) if results else 0.0,
        "results": results,
        "metadata": _safe_metadata(metadata),
    }
    _append_json_record(memory, BENCHMARK_HISTORY_FILE, run)
    return run


def benchmark_dashboard(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    history = [item for item in _read_json(memory.root / BENCHMARK_HISTORY_FILE, []) if isinstance(item, dict)]
    max_items = max(1, min(200, int(limit)))
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "suites": benchmark_suites(),
        "history": list(reversed(history[-max_items:])),
        "latest": history[-1] if history else None,
        "statistics": {
            "run_count": len(history),
            "average_score": round(sum(float(item.get("score") or 0.0) for item in history) / len(history), 3) if history else 0.0,
            "latest_status": str(history[-1].get("status") or "") if history else "not_run",
        },
    }


def create_evaluation_report(
    workspace: str | Path,
    *,
    workflow_id: str | None = None,
    quality_run_id: str | None = None,
    title: str = "",
    changes: list[dict[str, Any]] | None = None,
    tests_run: list[str] | None = None,
    repairs_attempted: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    quality_run = _find_quality_run(memory, quality_run_id, workflow_id)
    if quality_run is None:
        quality_run = evaluate_quality_gates(
            root,
            changes=changes or [],
            workflow_id=workflow_id,
            approval=bool((metadata or {}).get("approval")),
            checkpoint_id=str((metadata or {}).get("checkpoint_id") or "") or None,
            persist=True,
        )
    latest_validation = _latest_validation_result(memory)
    changed_files = quality_run.get("changed_files") if isinstance(quality_run.get("changed_files"), list) else []
    tests = tests_run or _tests_from_validation(latest_validation)
    report = {
        "id": f"evaluation-{uuid.uuid4().hex[:12]}",
        "project_id": _project_id(root),
        "workspace": str(root),
        "workflow_id": workflow_id or quality_run.get("workflow_id"),
        "quality_run_id": quality_run.get("id"),
        "created_at": utc_now(),
        "title": title.strip() or "Workflow Evaluation Report",
        "status": "blocked" if quality_run.get("blockers") else ("warning" if quality_run.get("warnings") else "passed"),
        "scorecard": quality_run.get("scorecard", {}),
        "what_changed": _report_changes(changed_files, changes or []),
        "why_changed": str((metadata or {}).get("reason") or (metadata or {}).get("objective") or "No workflow objective was supplied."),
        "tests_run": tests,
        "failures_found": _report_failures(quality_run, latest_validation),
        "repairs_attempted": repairs_attempted or _repair_attempts_from_metadata(metadata or {}),
        "remaining_risks": _remaining_risks(quality_run),
        "rollback_instructions": _rollback_instructions(quality_run),
        "quality_gate": quality_run,
        "metadata": _safe_metadata(metadata),
        "markdown": "",
    }
    report["markdown"] = _render_report_markdown(report)
    _append_json_record(memory, EVALUATION_REPORTS_FILE, report)
    return report


def list_evaluation_reports(workspace: str | Path, *, workflow_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = _memory(root)
    reports = [item for item in _read_json(memory.root / EVALUATION_REPORTS_FILE, []) if isinstance(item, dict)]
    if workflow_id:
        reports = [item for item in reports if str(item.get("workflow_id") or "") == workflow_id]
    max_items = max(1, min(200, int(limit)))
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "reports": list(reversed(reports[-max_items:])),
        "latest": reports[-1] if reports else None,
    }


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
        raise QualityGatePersistenceError(f"Could not create Core quality state directory at {memory.root}: {exc}") from exc
    return memory


def _normalize_changes(root: Path, changes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in changes:
        if not isinstance(item, dict):
            warnings.append("Ignored non-object change while evaluating quality gates.")
            continue
        raw_path = str(item.get("path") or "").strip()
        try:
            path = _normalize_relative_path(raw_path)
        except ValueError as exc:
            normalized.append({"path": raw_path or "<empty>", "action": str(item.get("action") or "update"), "unsafe": True, "error": str(exc)})
            continue
        normalized.append(
            {
                "id": str(item.get("id") or ""),
                "path": path,
                "action": str(item.get("action") or "update").strip().lower() or "update",
                "content": item.get("content"),
                "summary": str(item.get("summary") or ""),
                "unsafe": not _is_safe_change_path(root, path),
            }
        )
    return normalized, warnings


def _normalize_relative_path(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    if not raw:
        raise ValueError("path is empty")
    candidate = Path(raw)
    if candidate.is_absolute() or raw.startswith("/") or ":" in PurePosixPath(raw).parts[0]:
        raise ValueError("path must be relative to the workspace")
    path = PurePosixPath(raw)
    if str(path) in {".", ".."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must not contain dot segments")
    return path.as_posix()


def _is_safe_change_path(root: Path, path: str) -> bool:
    try:
        target = (root / path).resolve()
        target.relative_to(root)
        return not is_ignored_path(target, root) and not is_secret_like(target) and is_safe_to_edit(target, root)
    except (OSError, RuntimeError, ValueError):
        return False


def _unsafe_path_hits(root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if not _is_safe_change_path(root, path)]


def _restricted_path_hits(paths: list[str], extra_restricted: list[str]) -> list[str]:
    normalized_extra = tuple(_normalize_restricted_prefix(item) for item in extra_restricted if str(item).strip())
    restricted: list[str] = []
    for path in paths:
        lowered = path.lower().lstrip("/")
        if any(lowered == prefix.rstrip("/") or lowered.startswith(prefix) for prefix in RESTRICTED_PATH_PREFIXES):
            restricted.append(path)
            continue
        if normalized_extra and any(lowered == prefix.rstrip("/") or lowered.startswith(prefix) for prefix in normalized_extra):
            restricted.append(path)
    return restricted


def _normalize_restricted_prefix(value: str) -> str:
    text = value.replace("\\", "/").strip().lower().lstrip("/")
    return text if text.endswith("/") else text + "/"


def _syntax_gate(root: Path, changes: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    failures: list[str] = []
    skipped = 0
    for change in changes:
        if change.get("action") == "delete":
            continue
        path = str(change.get("path") or "")
        suffix = Path(path).suffix.lower()
        content = change.get("content")
        if content is None:
            target = root / path
            try:
                content = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
            except OSError:
                content = ""
        if suffix == ".py":
            checked += 1
            try:
                ast.parse(str(content))
            except SyntaxError as exc:
                failures.append(f"{path}: {exc.msg} at line {exc.lineno}")
        elif suffix == ".json":
            checked += 1
            try:
                json.loads(str(content) or "{}")
            except json.JSONDecodeError as exc:
                failures.append(f"{path}: {exc.msg} at line {exc.lineno}")
        elif suffix in SOURCE_SUFFIXES:
            skipped += 1
    if failures:
        return _gate("syntax_check", "Syntax check", "failed", "high", "; ".join(failures[:4]), blocks_apply=True)
    if checked:
        return _gate("syntax_check", "Syntax check", "passed", "low", f"Parsed {checked} Python/JSON file(s).")
    if skipped:
        return _gate("syntax_check", "Syntax check", "skipped", "low", f"No built-in parser for {skipped} changed source file(s).")
    return _gate("syntax_check", "Syntax check", "skipped", "low", "No source syntax check was needed.")


def _validation_gate(
    gate_id: str,
    label: str,
    validation_state: dict[str, Any],
    command_tokens: tuple[str, ...],
    required: bool,
) -> dict[str, Any]:
    command = validation_state.get("latest_command", "")
    lowered = str(command).lower()
    matched = command and any(token in lowered for token in command_tokens)
    if matched and validation_state.get("latest_ok") is True:
        return _gate(gate_id, label, "passed", "low", f"Latest `{command}` validation passed.")
    if matched and validation_state.get("latest_ok") is False:
        return _gate(gate_id, label, "failed", "high", f"Latest `{command}` validation failed.", blocks_apply=required)
    available = any(
        any(token in str(item.get("name") or item.get("command") or "").lower() for token in command_tokens)
        for item in validation_state.get("detected_commands", [])
        if isinstance(item, dict)
    )
    if required and available:
        return _gate(gate_id, label, "failed", "high", f"{label} is required but has not passed.", blocks_apply=True)
    if available:
        return _gate(gate_id, label, "warning", "medium", f"{label} command is available but has not run for this gate.")
    return _gate(gate_id, label, "skipped", "low", f"No {label.lower()} command was detected.")


def _security_gate(unsafe: list[str], restricted: list[str], binary_hits: list[str], changes: list[dict[str, Any]]) -> dict[str, Any]:
    content_hits = _secret_content_hits(changes)
    hits = sorted(set(unsafe + restricted + binary_hits + content_hits))
    if hits:
        reason = "Blocked unsafe, restricted, binary, or secret-like change path/content: " + ", ".join(hits[:8])
        return _gate("security_scan", "Security scan", "failed", "critical", reason, blocks_apply=True)
    return _gate("security_scan", "Security scan", "passed", "low", "No unsafe paths or secret-like changes were detected.")


def _dependency_gate(dependency_hits: list[str]) -> dict[str, Any]:
    if dependency_hits:
        return _gate(
            "dependency_risk",
            "Dependency risk",
            "warning",
            "medium",
            "Dependency or lock files are touched: " + ", ".join(dependency_hits[:8]),
        )
    return _gate("dependency_risk", "Dependency risk", "passed", "low", "No dependency manifests or lock files are touched.")


def _file_change_gate(file_count: int, max_files: int, source_hits: list[str], delete_hits: list[str]) -> dict[str, Any]:
    if file_count > max_files:
        return _gate(
            "file_change_risk",
            "File-change risk",
            "failed",
            "high",
            f"{file_count} file(s) exceed the configured limit of {max_files}.",
            blocks_apply=True,
        )
    if delete_hits:
        return _gate(
            "file_change_risk",
            "File-change risk",
            "warning",
            "medium",
            f"{len(delete_hits)} delete operation(s) require careful review.",
        )
    if file_count >= max(8, max_files // 2):
        return _gate("file_change_risk", "File-change risk", "warning", "medium", f"{file_count} files changed; review impact before apply.")
    return _gate("file_change_risk", "File-change risk", "passed", "low", f"{file_count} file(s), {len(source_hits)} source file(s).")


def _rollback_gate(checkpoint_id: str | None, has_changes: bool, dry_run: bool) -> dict[str, Any]:
    if dry_run or not has_changes:
        return _gate("rollback_readiness", "Rollback readiness", "skipped", "low", "No write is happening in this evaluation.")
    if checkpoint_id:
        return _gate("rollback_readiness", "Rollback readiness", "passed", "low", f"Checkpoint `{checkpoint_id}` is available.")
    return _gate("rollback_readiness", "Rollback readiness", "failed", "critical", "Apply is blocked until a checkpoint exists.", blocks_apply=True)


def _approval_gate(
    approval: bool,
    restricted: list[str],
    unsafe: list[str],
    file_count: int,
    max_files: int,
    delete_hits: list[str],
) -> dict[str, Any]:
    requires = bool(restricted or unsafe or file_count > max_files or delete_hits)
    if requires and not approval:
        return _gate("user_approval_required", "User approval", "failed", "high", "High-risk change requires explicit user approval.", blocks_apply=True)
    if requires and approval:
        return _gate("user_approval_required", "User approval", "passed", "medium", "Explicit approval supplied for high-risk change.")
    return _gate("user_approval_required", "User approval", "passed", "low", "No extra approval gate was required.")


def _gate(gate_id: str, label: str, status: str, severity: str, summary: str, *, blocks_apply: bool = False) -> dict[str, Any]:
    return {
        "id": gate_id,
        "label": label,
        "status": status,
        "severity": severity,
        "summary": scrub(summary),
        "blocks_apply": blocks_apply,
        "checked_at": utc_now(),
    }


def _scorecard(
    gates: list[dict[str, Any]],
    validation_state: dict[str, Any],
    file_count: int,
    max_files: int,
    dependency_hits: list[str],
    delete_hits: list[str],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    passed = sum(1 for gate in gates if gate.get("status") == "passed")
    failed = sum(1 for gate in gates if gate.get("status") == "failed")
    warnings = sum(1 for gate in gates if gate.get("status") == "warning")
    scored_count = max(1, sum(1 for gate in gates if gate.get("status") != "skipped"))
    completion = max(0, round((passed / scored_count) * 100 - failed * 8 - warnings * 3))
    validation_gates = [gate for gate in gates if gate["id"] in {"syntax_check", "build_check", "test_check", "lint_check", "type_check"} and gate["status"] != "skipped"]
    validation_passed = sum(1 for gate in validation_gates if gate["status"] == "passed")
    validation_score = round((validation_passed / len(validation_gates)) * 100) if validation_gates else (80 if validation_state.get("latest_ok") else 45)
    risk_score = min(
        100,
        failed * 22
        + warnings * 9
        + (25 if file_count > max_files else min(20, file_count * 2))
        + len(dependency_hits) * 8
        + len(delete_hits) * 12,
    )
    confidence = max(0, min(100, round((completion * 0.45) + (validation_score * 0.35) + ((100 - risk_score) * 0.20))))
    repair_score = 100 if validation_state.get("latest_ok") else (45 if validation_state.get("latest_command") else 60)
    regression_risk = min(100, round(risk_score * 0.7 + (100 - validation_score) * 0.3))
    return {
        "completion_score": completion,
        "validation_score": validation_score,
        "risk_score": risk_score,
        "confidence_score": confidence,
        "repair_score": repair_score,
        "regression_risk": regression_risk,
        "human_review_required": bool(blockers or risk_score >= 55 or validation_score < 60),
        "passed_gates": passed,
        "failed_gates": failed,
        "warning_gates": warnings,
        "skipped_gates": sum(1 for gate in gates if gate.get("status") == "skipped"),
    }


def _validation_state(latest: dict[str, Any] | None, detected: list[dict[str, Any]]) -> dict[str, Any]:
    validation = latest.get("validation") if isinstance(latest, dict) and isinstance(latest.get("validation"), dict) else latest or {}
    command = validation.get("command") if isinstance(validation, dict) else None
    if isinstance(command, list):
        command_text = " ".join(str(part) for part in command)
    else:
        command_text = str(command or "")
    return {
        "latest_id": _record_id(latest),
        "latest_ok": validation.get("ok") if isinstance(validation, dict) and "ok" in validation else None,
        "latest_command": command_text,
        "latest_returncode": validation.get("returncode") if isinstance(validation, dict) else None,
        "latest_stderr": scrub(str(validation.get("stderr") or ""))[-1200:] if isinstance(validation, dict) else "",
        "detected_commands": detected,
        "detected_count": len(detected),
    }


def _latest_validation_result(memory: ProjectMemory, *, validation_id: str | None = None) -> dict[str, Any]:
    data = _read_json(memory.root / "validation-results.json", [])
    if not isinstance(data, list):
        return {}
    records = [item for item in data if isinstance(item, dict)]
    if validation_id:
        return next((item for item in records if str(item.get("id") or "") == validation_id), {})
    return records[-1] if records else {}


def _record_id(value: Any) -> str | None:
    return str(value.get("id")) if isinstance(value, dict) and value.get("id") else None


def _change_action(changes: list[dict[str, Any]], path: str) -> str:
    for change in changes:
        if change.get("path") == path:
            return str(change.get("action") or "update")
    return "update"


def _secret_content_hits(changes: list[dict[str, Any]]) -> list[str]:
    pattern = re.compile(r"(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.IGNORECASE)
    hits: list[str] = []
    for change in changes:
        content = change.get("content")
        if content is not None and pattern.search(str(content)):
            hits.append(str(change.get("path") or "<content>"))
    return hits


def _required_actions(
    blockers: list[dict[str, Any]],
    warnings: list[str],
    validation_required: bool,
    checkpoint_id: str | None,
) -> list[str]:
    actions: list[str] = []
    if not checkpoint_id and any(item["gate_id"] == "rollback_readiness" for item in blockers):
        actions.append("Create a Core checkpoint before applying changes.")
    if any(item["gate_id"] in {"build_check", "test_check", "syntax_check"} for item in blockers) or validation_required:
        actions.append("Run or repair required validation before apply.")
    if any(item["gate_id"] == "user_approval_required" for item in blockers):
        actions.append("Collect explicit user approval or reduce the change risk.")
    if any(item["gate_id"] == "security_scan" for item in blockers):
        actions.append("Remove unsafe, restricted, binary, or secret-like file changes.")
    if warnings and not actions:
        actions.append("Review warnings before completing the workflow.")
    if not actions:
        actions.append("Quality gates allow apply; keep the checkpoint ID for rollback.")
    return actions


def _evaluation_summary(blockers: list[dict[str, Any]], warnings: list[str], scorecard: dict[str, Any]) -> str:
    if blockers:
        return f"Blocked by {len(blockers)} quality gate(s); risk score {scorecard['risk_score']}."
    if warnings:
        return f"Passed with {len(warnings)} warning(s); confidence score {scorecard['confidence_score']}."
    return f"Passed all required gates; confidence score {scorecard['confidence_score']}."


def _quality_statistics(runs: list[dict[str, Any]], reports: list[dict[str, Any]], benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = sum(1 for item in runs if item.get("status") == "blocked")
    passed = sum(1 for item in runs if item.get("status") == "passed")
    warnings = sum(1 for item in runs if item.get("status") == "warning")
    scores = [float((item.get("scorecard") or {}).get("confidence_score") or 0) for item in runs]
    return {
        "run_count": len(runs),
        "passed_count": passed,
        "warning_count": warnings,
        "blocked_count": blocked,
        "block_rate": round(blocked / len(runs), 3) if runs else 0.0,
        "average_confidence": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "report_count": len(reports),
        "benchmark_run_count": len(benchmarks),
    }


def _benchmark_result(
    root: Path,
    suite: dict[str, Any],
    gate_dashboard: dict[str, Any],
    health: dict[str, Any],
    workflow_id: str | None,
) -> dict[str, Any]:
    latest = gate_dashboard.get("latest") if isinstance(gate_dashboard.get("latest"), dict) else {}
    scorecard = latest.get("scorecard") if isinstance(latest.get("scorecard"), dict) else {}
    health_score = float(health.get("score") or 0)
    confidence = float(scorecard.get("confidence_score") or health_score)
    validation = float(scorecard.get("validation_score") or (100 if health.get("statuses", {}).get("validation", {}).get("status") == "passed" else 60))
    risk = float(scorecard.get("risk_score") or 0)
    if suite["id"] == "validation_success":
        score = validation / 100
    elif suite["id"] == "repair_accuracy":
        score = float(scorecard.get("repair_score") or 70) / 100
    elif suite["id"] == "agent_handoff_reliability":
        stats = _read_json(ProjectMemory(root).root / "workflow-runtime.json", [])
        workflow_count = len(stats) if isinstance(stats, list) else 0
        score = 0.9 if workflow_count else 0.65
    elif suite["id"] in {"routing_decisions", "model_provider_performance"}:
        score = 0.75 if workflow_id or latest else 0.6
    else:
        score = max(0.0, min(1.0, (confidence * 0.7 + (100 - risk) * 0.3) / 100))
    return {
        "suite_id": suite["id"],
        "suite_label": suite["label"],
        "status": "passed" if score >= 0.7 else "warning",
        "score": round(score, 3),
        "metrics": {
            "health_score": health_score,
            "confidence_score": confidence,
            "validation_score": validation,
            "risk_score": risk,
        },
        "summary": f"{suite['label']} scored {round(score * 100)}%.",
    }


def _find_quality_run(memory: ProjectMemory, quality_run_id: str | None, workflow_id: str | None) -> dict[str, Any] | None:
    runs = [item for item in _read_json(memory.root / QUALITY_GATES_FILE, []) if isinstance(item, dict)]
    if quality_run_id:
        found = next((item for item in runs if str(item.get("id") or "") == quality_run_id), None)
        if found is None:
            raise QualityGateEvaluationNotFoundError(quality_run_id)
        return found
    if workflow_id:
        workflow_runs = [item for item in runs if str(item.get("workflow_id") or "") == workflow_id]
        if workflow_runs:
            return workflow_runs[-1]
    return runs[-1] if runs else None


def _report_changes(paths: list[Any], changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    if changes:
        return [
            {
                "path": str(change.get("path") or ""),
                "action": str(change.get("action") or "update"),
                "reason": str(change.get("summary") or "Proposed workflow change."),
            }
            for change in changes
            if isinstance(change, dict)
        ]
    return [{"path": str(path), "action": "unknown", "reason": "Captured by quality gate evaluation."} for path in paths]


def _tests_from_validation(latest_validation: dict[str, Any]) -> list[dict[str, Any]]:
    validation = latest_validation.get("validation") if isinstance(latest_validation.get("validation"), dict) else latest_validation
    if not isinstance(validation, dict) or not validation.get("command"):
        return []
    command = validation.get("command")
    return [
        {
            "command": " ".join(str(part) for part in command) if isinstance(command, list) else str(command),
            "ok": bool(validation.get("ok")),
            "returncode": validation.get("returncode"),
        }
    ]


def _report_failures(quality_run: dict[str, Any], latest_validation: dict[str, Any]) -> list[dict[str, str]]:
    failures = [
        {"source": "quality_gate", "summary": str(blocker.get("reason") or blocker.get("label") or "blocked")}
        for blocker in quality_run.get("blockers", [])
        if isinstance(blocker, dict)
    ]
    validation = latest_validation.get("validation") if isinstance(latest_validation.get("validation"), dict) else latest_validation
    if isinstance(validation, dict) and validation.get("ok") is False:
        failures.append({"source": "validation", "summary": scrub(str(validation.get("stderr") or validation.get("stdout") or "Validation failed."))[:1000]})
    return failures


def _repair_attempts_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    repairs = metadata.get("repairs_attempted")
    if isinstance(repairs, list):
        return [item for item in repairs if isinstance(item, dict)]
    repair_attempt = metadata.get("repair_attempt")
    return [repair_attempt] if isinstance(repair_attempt, dict) else []


def _remaining_risks(quality_run: dict[str, Any]) -> list[str]:
    risks = [str(warning) for warning in quality_run.get("warnings", []) if str(warning).strip()]
    for blocker in quality_run.get("blockers", []):
        if isinstance(blocker, dict):
            risks.append(str(blocker.get("reason") or blocker.get("label") or "Blocked gate."))
    scorecard = quality_run.get("scorecard") if isinstance(quality_run.get("scorecard"), dict) else {}
    if scorecard.get("regression_risk", 0) >= 60:
        risks.append(f"Regression risk is {scorecard.get('regression_risk')}.")
    return risks[:12]


def _rollback_instructions(quality_run: dict[str, Any]) -> list[str]:
    checkpoint_id = str(quality_run.get("checkpoint_id") or "")
    if checkpoint_id:
        return [
            f"Restore checkpoint `{checkpoint_id}` through `/v1/checkpoints/restore` if the change regresses.",
            "Keep the quality report with the workflow journal for audit history.",
        ]
    return ["No checkpoint is attached to this report; create one before applying file changes."]


def _render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- Status: {report['status']}",
        f"- Workflow: {report.get('workflow_id') or 'not linked'}",
        f"- Quality run: {report.get('quality_run_id') or 'not linked'}",
        f"- Confidence: {(report.get('scorecard') or {}).get('confidence_score', 'n/a')}",
        f"- Risk: {(report.get('scorecard') or {}).get('risk_score', 'n/a')}",
        "",
        "## What Changed",
    ]
    lines.extend(f"- `{item.get('path')}`: {item.get('action')} - {item.get('reason')}" for item in report.get("what_changed", [])[:20])
    lines.extend(["", "## Tests Run"])
    tests = report.get("tests_run", [])
    lines.extend(f"- `{item.get('command')}`: {'passed' if item.get('ok') else 'failed'}" for item in tests) if tests else lines.append("- No validation command was recorded.")
    lines.extend(["", "## Remaining Risks"])
    risks = report.get("remaining_risks", [])
    lines.extend(f"- {risk}" for risk in risks) if risks else lines.append("- No remaining risk was detected by Core quality gates.")
    lines.extend(["", "## Rollback"])
    lines.extend(f"- {item}" for item in report.get("rollback_instructions", []))
    return "\n".join(lines).rstrip() + "\n"


def _append_json_record(memory: ProjectMemory, name: str, record: dict[str, Any]) -> None:
    data = _read_json(memory.root / name, [])
    if not isinstance(data, list):
        data = []
    data.append(record)
    data = data[-MAX_STORED_ITEMS:]
    memory.write_json(name, data)
    persisted = _read_json(memory.root / name, [])
    if not isinstance(persisted, list) or not any(isinstance(item, dict) and item.get("id") == record.get("id") for item in persisted):
        raise QualityGatePersistenceError(f"Could not persist Core quality record at {memory.root / name}.")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _safe_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        text_key = scrub(str(key))[:80]
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[text_key] = scrub(str(item))[:2000] if isinstance(item, str) else item
        elif isinstance(item, list):
            safe[text_key] = [scrub(str(entry))[:1000] if not isinstance(entry, dict) else _safe_metadata(entry) for entry in item[:50]]
        elif isinstance(item, dict):
            safe[text_key] = _safe_metadata(item)
        else:
            safe[text_key] = scrub(str(item))[:1000]
    return safe


def _project_id(root: Path) -> str:
    try:
        digest = uuid.uuid5(uuid.NAMESPACE_URL, str(root.resolve()).lower())
    except (OSError, RuntimeError):
        digest = uuid.uuid4()
    return f"project-{digest.hex[:12]}"
