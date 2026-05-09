from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .ecosystem import shared_memory_summary
from .memory import ProjectMemory, utc_now
from .quality import record_quality_snapshot
from .roadmap import generate_roadmap, next_best_tasks
from .safety import is_ignored_path, is_safe_to_read
from .validation import detect_validation_commands, run_validation, validation_summary
from .workspace import SOURCE_CODE_SUFFIXES, WorkspaceScanner


JOBS_STATE_FILE = "jobs-state.json"
JOBS_LOG_FILE = "jobs-log.md"
APPROVAL_GATES = {
    "file_edit": "File edits require explicit approval.",
    "file_delete": "File deletion requires explicit approval.",
    "build_command": "Build/test/lint commands require explicit approval.",
    "install_package": "Package installation requires explicit approval.",
    "cloud_context": "Sending context to a cloud model requires explicit approval.",
}


class JobPersistenceError(RuntimeError):
    """Raised when maintenance job state cannot be persisted."""


@dataclass(frozen=True)
class MaintenanceJob:
    id: str
    title: str
    workflow: str
    schedule: str
    triggers: list[str]
    description: str
    approval_gates: list[str]
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_JOBS: list[MaintenanceJob] = [
    MaintenanceJob(
        id="daily-project-scan",
        title="Daily Project Scan",
        workflow="project_scan",
        schedule="daily",
        triggers=["project_opened", "many_files_changed"],
        description="Refresh the local workspace index, project summary, and architecture map.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="weekly-roadmap-update",
        title="Weekly Roadmap Update",
        workflow="roadmap_update",
        schedule="weekly",
        triggers=["roadmap_changed"],
        description="Refresh the generated roadmap from the latest scan and memory state.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="dependency-review",
        title="Dependency Review",
        workflow="dependency_review",
        schedule="weekly",
        triggers=["new_dependency_added"],
        description="Summarize dependency manifests and flag dependency-heavy risk areas.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="build-health-check",
        title="Build Health Check",
        workflow="build_health_check",
        schedule="daily",
        triggers=["build_failed", "test_failed"],
        description="Detect validation commands and run them only after explicit approval.",
        approval_gates=["build_command"],
    ),
    MaintenanceJob(
        id="stale-todo-scan",
        title="Stale TODO Scan",
        workflow="stale_todo_scan",
        schedule="daily",
        triggers=["project_opened", "many_files_changed"],
        description="Summarize TODO/FIXME comments without editing source files.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="documentation-drift-check",
        title="Documentation Drift Check",
        workflow="documentation_drift_check",
        schedule="weekly",
        triggers=["roadmap_changed", "many_files_changed"],
        description="Compare README/docs presence with recent project activity.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="recent-changes-summary",
        title="Recent Changes Summary",
        workflow="recent_changes_summary",
        schedule="manual",
        triggers=["many_files_changed", "project_opened"],
        description="Summarize recently changed safe files.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="broken-references-check",
        title="Broken References Check",
        workflow="broken_references_check",
        schedule="manual",
        triggers=["project_opened", "many_files_changed"],
        description="Detect missing relative markdown references in safe documentation files.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="project-health-report",
        title="Project Health Report",
        workflow="project_health_report",
        schedule="daily",
        triggers=["project_opened", "build_failed", "test_failed", "many_files_changed"],
        description="Generate a project health snapshot with warnings and recommended actions.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="quality-intelligence-snapshot",
        title="Quality Intelligence Snapshot",
        workflow="quality_intelligence_snapshot",
        schedule="daily",
        triggers=["project_opened", "build_failed", "test_failed", "many_files_changed"],
        description="Record health history and generate daily/weekly quality reports.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="next-best-task",
        title="Suggest Next Best Task",
        workflow="next_best_task",
        schedule="manual",
        triggers=["project_opened", "roadmap_changed"],
        description="Recommend the next safe maintenance task from the current scan.",
        approval_gates=[],
    ),
    MaintenanceJob(
        id="validation-status-check",
        title="Validation Status Check",
        workflow="validation_status_check",
        schedule="manual",
        triggers=["build_failed", "test_failed", "project_opened"],
        description="Report detected validation commands without executing them.",
        approval_gates=[],
    ),
]


def jobs_dashboard(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    state = _load_state(memory)
    jobs = [_job_dashboard_entry(job, state.get("jobs", {}).get(job.id, {})) for job in DEFAULT_JOBS]
    history = state.get("history") if isinstance(state.get("history"), list) else []
    due_jobs = [job for job in jobs if job.get("enabled") and job.get("due")]
    return {
        "workspace": str(root),
        "scheduled_jobs": jobs,
        "due_jobs": due_jobs,
        "triggers": _trigger_catalog(),
        "approval_rules": _approval_rules(),
        "history": history[-25:],
        "log_path": str(memory.root / JOBS_LOG_FILE),
    }


def run_job(
    workspace: str | Path,
    *,
    job_id: str | None = None,
    trigger: str | None = None,
    approval: bool = False,
    run_due: bool = False,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    state = _load_state(memory)
    selected = _select_jobs(job_id=job_id, trigger=trigger, run_due=run_due, state=state)
    if not selected:
        raise ValueError("No matching maintenance jobs found.")

    results = [_execute_job(root, memory, state, job, trigger=trigger, approval=approval) for job in selected]
    _write_state(memory, state)
    return {
        "workspace": str(root),
        "trigger": trigger,
        "run_due": run_due,
        "results": results,
        "dashboard": jobs_dashboard(root),
    }


def _execute_job(
    root: Path,
    memory: ProjectMemory,
    state: dict[str, Any],
    job: MaintenanceJob,
    *,
    trigger: str | None,
    approval: bool,
) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = _run_workflow(root, job, approval=approval)
    except Exception as exc:  # pragma: no cover - defensive boundary for job runners.
        result = {
            "status": "failed",
            "ok": False,
            "approval_required": False,
            "warnings": [scrub(str(exc))],
            "suggested_actions": ["Review the job error and run diagnostics before retrying."],
            "report": f"{job.title} failed before producing a report.",
            "artifacts": {},
        }
    finished_at = utc_now()
    result.update(
        {
            "id": job.id,
            "title": job.title,
            "workflow": job.workflow,
            "trigger": trigger,
            "started_at": started_at,
            "finished_at": finished_at,
            "approval_gates": [_gate(gate) for gate in job.approval_gates],
        }
    )
    _record_result(memory, state, job, result)
    return result


def _run_workflow(root: Path, job: MaintenanceJob, *, approval: bool) -> dict[str, Any]:
    if job.workflow == "project_scan":
        return _workflow_project_scan(root)
    if job.workflow == "roadmap_update":
        return _workflow_roadmap_update(root)
    if job.workflow == "dependency_review":
        return _workflow_dependency_review(root)
    if job.workflow == "build_health_check":
        return _workflow_build_health_check(root, approval=approval)
    if job.workflow == "stale_todo_scan":
        return _workflow_stale_todo_scan(root)
    if job.workflow == "documentation_drift_check":
        return _workflow_documentation_drift_check(root)
    if job.workflow == "recent_changes_summary":
        return _workflow_recent_changes_summary(root)
    if job.workflow == "broken_references_check":
        return _workflow_broken_references_check(root)
    if job.workflow == "project_health_report":
        return _workflow_project_health_report(root)
    if job.workflow == "quality_intelligence_snapshot":
        return _workflow_quality_intelligence_snapshot(root)
    if job.workflow == "next_best_task":
        return _workflow_next_best_task(root)
    if job.workflow == "validation_status_check":
        return _workflow_validation_status_check(root)
    return _result("failed", f"Unknown workflow: {job.workflow}", warnings=[f"Unsupported workflow `{job.workflow}`."])


def _workflow_project_scan(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    warnings = _scan_warnings(scan)
    return _result(
        "completed",
        f"Scanned {scan.get('file_count', 0)} files in {scan.get('workspace_name')}.",
        warnings=warnings,
        suggested_actions=_scan_actions(scan),
        artifacts={
            "project_summary": ".aegis/project-summary.md",
            "architecture_map": ".aegis/architecture-map.md",
            "file_index": ".aegis/file-index.json",
        },
        metrics=_scan_metrics(scan),
    )


def _workflow_roadmap_update(root: Path) -> dict[str, Any]:
    roadmap = generate_roadmap(root, persist=True)
    tasks = roadmap.get("tasks") or []
    return _result(
        "completed",
        f"Updated roadmap with {len(tasks)} recommended tasks.",
        suggested_actions=[str(task.get("title")) for task in tasks[:5] if task.get("title")],
        artifacts={"roadmap": ".aegis/roadmap.md"},
        metrics={"task_count": len(tasks)},
    )


def _workflow_dependency_review(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    manifests = _dependency_manifests(root)
    dependency_files = scan.get("dependency_graph", {}).get("files", {})
    warnings: list[str] = []
    if not manifests:
        warnings.append("No dependency manifest found.")
    if len(dependency_files) > 100:
        warnings.append("Large dependency graph; review tightly coupled modules first.")
    actions = ["Review dependency manifests before adding new packages."] if manifests else []
    return _result(
        "completed",
        f"Found {len(manifests)} dependency manifests and {len(dependency_files)} indexed dependency-bearing files.",
        warnings=warnings,
        suggested_actions=actions,
        artifacts={"dependency_graph": ".aegis/dependency-graph.json"},
        metrics={"manifest_count": len(manifests), "dependency_file_count": len(dependency_files), "manifests": manifests},
    )


def _workflow_build_health_check(root: Path, *, approval: bool) -> dict[str, Any]:
    commands = [command.__dict__ for command in detect_validation_commands(root)]
    if not commands:
        return _result(
            "completed",
            "No validation command detected.",
            warnings=["No build/test/lint command is currently known for this project."],
            suggested_actions=["Add or document a validation command before relying on automated health checks."],
            metrics={"commands": []},
        )
    if not approval:
        return _result(
            "needs_approval",
            "Validation command detected but not run because build/test commands require approval.",
            approval_required=True,
            approval_gates=[_gate("build_command")],
            warnings=["Approval required before running build/test/lint commands."],
            suggested_actions=[f"Approve and rerun to execute `{commands[0]['name']}`."],
            metrics={"commands": commands},
        )
    validation = run_validation(root)
    status = "completed" if validation.get("ok") else "failed"
    return _result(
        status,
        "Validation passed." if validation.get("ok") else "Validation failed.",
        warnings=[] if validation.get("ok") else [scrub(validation.get("stderr") or validation.get("stdout") or "Validation failed.")[:500]],
        suggested_actions=[] if validation.get("ok") else ["Inspect validation-log.md and create a repair task if needed."],
        artifacts={"validation_log": ".aegis/validation-log.md"},
        metrics={"commands": commands, "validation": validation},
    )


def _workflow_stale_todo_scan(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    todos = scan.get("todo_comments") or []
    warnings = [f"{len(todos)} TODO/FIXME comments found."] if todos else []
    actions = ["Triage TODO/FIXME comments into bugs, cleanup, and future work."] if todos else []
    return _result(
        "completed",
        f"Found {len(todos)} TODO/FIXME comments.",
        warnings=warnings,
        suggested_actions=actions,
        metrics={"todo_count": len(todos), "sample": todos[:10]},
    )


def _workflow_documentation_drift_check(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    warnings: list[str] = []
    actions: list[str] = []
    readmes = scan.get("readmes") or []
    if not readmes:
        warnings.append("No README found.")
        actions.append("Create a README with setup, run, and validation instructions.")
    if scan.get("file_count", 0) > 100 and len(readmes) <= 1:
        warnings.append("Large project with minimal documentation surface.")
    recent_code = [path for path in scan.get("recent_files", []) if Path(path).suffix.lower() in SOURCE_CODE_SUFFIXES]
    if len(recent_code) >= 10:
        actions.append("Review whether recent code changes require README or architecture-map updates.")
    return _result(
        "completed",
        f"Documentation check found {len(readmes)} README-like files and {len(recent_code)} recently changed code files.",
        warnings=warnings,
        suggested_actions=actions,
        metrics={"readmes": readmes, "recent_code_files": recent_code[:20]},
    )


def _workflow_recent_changes_summary(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    recent = scan.get("recent_files", [])[:20]
    return _result(
        "completed",
        f"Most recent safe files: {', '.join(recent[:5]) if recent else 'none detected'}.",
        suggested_actions=["Review recent files before starting roadmap or repair work."] if recent else [],
        metrics={"recent_files": recent},
    )


def _workflow_broken_references_check(root: Path) -> dict[str, Any]:
    broken = _detect_broken_markdown_references(root)
    warnings = [f"{len(broken)} missing relative documentation references found."] if broken else []
    actions = ["Fix broken relative documentation links after approval."] if broken else []
    return _result(
        "completed",
        f"Checked markdown references and found {len(broken)} missing targets.",
        warnings=warnings,
        suggested_actions=actions,
        metrics={"broken_references": broken[:50]},
    )


def _workflow_project_health_report(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    validation = validation_summary(root)
    memory = shared_memory_summary(root)
    warnings = _scan_warnings(scan)
    if not validation.get("commands"):
        warnings.append("No validation commands detected.")
    if not any(entry.get("exists") for entry in memory.get("entries", {}).values()):
        warnings.append("Shared project memory is mostly empty.")
    actions = _scan_actions(scan)
    if validation.get("commands"):
        actions.append("Run an approved build health check before applying risky edits.")
    report_path = ProjectMemory(root).write_generated_markdown(
        "project-health-report.md",
        "Project Health Report",
        _render_health_report(scan, validation, warnings, actions),
    )
    return _result(
        "completed",
        f"Generated project health report with {len(warnings)} warnings.",
        warnings=warnings,
        suggested_actions=actions,
        artifacts={"project_health_report": str(report_path)},
        metrics={"scan": _scan_metrics(scan), "validation_commands": validation.get("commands", [])},
    )


def _workflow_quality_intelligence_snapshot(root: Path) -> dict[str, Any]:
    quality = record_quality_snapshot(root)
    return _result(
        "completed",
        f"Recorded quality snapshot: score {quality.get('score')} ({quality.get('grade')}).",
        warnings=quality.get("warnings", []),
        suggested_actions=[quality.get("recommended_next_improvement", "Review quality dashboard.")],
        artifacts=quality.get("report_paths", {}),
        metrics={
            "score": quality.get("score"),
            "grade": quality.get("grade"),
            "trend": quality.get("trend"),
            "top_risks": quality.get("top_risks", [])[:5],
            "high_risk_files": quality.get("high_risk_files", [])[:5],
        },
    )


def _workflow_next_best_task(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=True)
    tasks = next_best_tasks(scan)
    top = tasks[0] if tasks else {}
    return _result(
        "completed",
        f"Next best task: {top.get('title', 'Review project health')}.",
        suggested_actions=[str(task.get("title")) for task in tasks[:5] if task.get("title")],
        metrics={"tasks": tasks},
    )


def _workflow_validation_status_check(root: Path) -> dict[str, Any]:
    validation = validation_summary(root)
    commands = validation.get("commands") or []
    warnings = [] if commands else ["No validation commands detected."]
    return _result(
        "completed",
        f"Detected {len(commands)} validation commands. No command was run.",
        warnings=warnings,
        suggested_actions=["Approve build-health-check to run validation."] if commands else ["Document or add a validation command."],
        metrics={"commands": commands},
    )


def _result(
    status: str,
    report: str,
    *,
    ok: bool | None = None,
    approval_required: bool = False,
    approval_gates: list[dict[str, str]] | None = None,
    warnings: list[str] | None = None,
    suggested_actions: list[str] | None = None,
    artifacts: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "ok": status not in {"failed"} if ok is None else ok,
        "approval_required": approval_required,
        "approval_gates": approval_gates or [],
        "warnings": [scrub(item) for item in warnings or []],
        "suggested_actions": [scrub(item) for item in suggested_actions or []],
        "report": scrub(report),
        "artifacts": artifacts or {},
        "metrics": metrics or {},
    }


def _select_jobs(
    *,
    job_id: str | None,
    trigger: str | None,
    run_due: bool,
    state: dict[str, Any],
) -> list[MaintenanceJob]:
    if job_id:
        return [job for job in DEFAULT_JOBS if job.id == job_id]
    if trigger:
        normalized = _normalize_token(trigger)
        return [job for job in DEFAULT_JOBS if normalized in {_normalize_token(item) for item in job.triggers}]
    if run_due:
        due: list[MaintenanceJob] = []
        for job in DEFAULT_JOBS:
            if job.enabled and _is_due(job, state.get("jobs", {}).get(job.id, {})):
                due.append(job)
        return due
    return []


def _job_dashboard_entry(job: MaintenanceJob, job_state: dict[str, Any]) -> dict[str, Any]:
    last_run = str(job_state.get("last_run") or "")
    next_run = _next_run(job, last_run)
    return {
        **job.to_dict(),
        "approval_gates": [_gate(gate) for gate in job.approval_gates],
        "last_run": last_run or None,
        "next_run": next_run,
        "due": _is_due(job, job_state),
        "last_result": job_state.get("last_result") if isinstance(job_state.get("last_result"), dict) else None,
        "warnings": job_state.get("warnings") if isinstance(job_state.get("warnings"), list) else [],
        "suggested_actions": job_state.get("suggested_actions") if isinstance(job_state.get("suggested_actions"), list) else [],
    }


def _next_run(job: MaintenanceJob, last_run: str) -> str | None:
    if job.schedule == "manual":
        return None
    parsed = _parse_utc(last_run)
    if parsed is None:
        return utc_now()
    delta = timedelta(days=7 if job.schedule == "weekly" else 1)
    return _format_utc(parsed + delta)


def _is_due(job: MaintenanceJob, job_state: dict[str, Any]) -> bool:
    if job.schedule == "manual":
        return False
    last_run = _parse_utc(str(job_state.get("last_run") or ""))
    if last_run is None:
        return True
    delta = timedelta(days=7 if job.schedule == "weekly" else 1)
    return datetime.now(timezone.utc) >= last_run + delta


def _record_result(memory: ProjectMemory, state: dict[str, Any], job: MaintenanceJob, result: dict[str, Any]) -> None:
    if not _append_jobs_log(memory, result):
        result.setdefault("warnings", []).append(
            f"Could not write jobs log at {memory.root / JOBS_LOG_FILE}."
        )
        result.setdefault("suggested_actions", []).append(
            "Repair the workspace .aegis jobs log path before relying on scheduled job history."
        )
    jobs = state.setdefault("jobs", {})
    jobs[job.id] = {
        "last_run": result["finished_at"],
        "last_result": {
            "status": result.get("status"),
            "ok": result.get("ok"),
            "report": result.get("report"),
        },
        "warnings": result.get("warnings", []),
        "suggested_actions": result.get("suggested_actions", []),
    }
    history = state.setdefault("history", [])
    history.append(
        {
            "timestamp": result["finished_at"],
            "event": "job_run",
            "job_id": job.id,
            "status": result.get("status"),
            "trigger": result.get("trigger"),
            "approval_required": result.get("approval_required", False),
            "report": result.get("report"),
        }
    )
    state["history"] = history[-200:]


def _append_jobs_log(memory: ProjectMemory, result: dict[str, Any]) -> bool:
    memory.ensure()
    warnings = "\n".join(f"- {item}" for item in result.get("warnings", [])) or "- none"
    actions = "\n".join(f"- {item}" for item in result.get("suggested_actions", [])) or "- none"
    entry = (
        f"## {result.get('finished_at')} - {result.get('title')} [{result.get('status')}]\n\n"
        f"- Job: `{result.get('id')}`\n"
        f"- Workflow: `{result.get('workflow')}`\n"
        f"- Trigger: `{result.get('trigger') or 'manual'}`\n"
        f"- Approval required: `{str(result.get('approval_required', False)).lower()}`\n\n"
        f"Report: {result.get('report')}\n\n"
        f"Warnings:\n{warnings}\n\n"
        f"Suggested actions:\n{actions}\n\n"
    )
    path = memory.root / JOBS_LOG_FILE
    try:
        if not path.exists():
            path.write_text("# Jobs Log\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return True
    except OSError:
        return False


def _load_state(memory: ProjectMemory) -> dict[str, Any]:
    path = memory.root / JOBS_STATE_FILE
    if not path.is_file():
        return {"jobs": {}, "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"jobs": {}, "history": []}
    if not isinstance(data, dict):
        return {"jobs": {}, "history": []}
    data["jobs"] = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    data["history"] = data.get("history") if isinstance(data.get("history"), list) else []
    return data


def _write_state(memory: ProjectMemory, state: dict[str, Any]) -> None:
    memory.write_json(JOBS_STATE_FILE, state)
    persisted = _load_state(memory)
    if persisted != state:
        raise JobPersistenceError(
            f"Could not persist maintenance job state at {memory.root / JOBS_STATE_FILE}. "
            "Check that the workspace .aegis path is a writable directory."
        )


def _trigger_catalog() -> list[dict[str, Any]]:
    triggers = sorted({trigger for job in DEFAULT_JOBS for trigger in job.triggers})
    return [
        {
            "id": trigger,
            "jobs": [job.id for job in DEFAULT_JOBS if trigger in job.triggers],
        }
        for trigger in triggers
    ]


def _approval_rules() -> dict[str, Any]:
    return {
        "automatic": ["scan", "summarize", "report", "recommend"],
        "approval_required_for": [_gate(gate_id) for gate_id in APPROVAL_GATES],
        "notes": [
            "Jobs may write generated Aegis memory and logs under .aegis.",
            "Jobs do not edit project source files, delete files, install packages, run build commands, or send cloud context without approval.",
        ],
    }


def _gate(gate_id: str) -> dict[str, str]:
    return {"id": gate_id, "label": APPROVAL_GATES.get(gate_id, "Explicit approval required.")}


def _scan_metrics(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_count": scan.get("file_count", 0),
        "frameworks": scan.get("frameworks", []),
        "build_file_count": len(scan.get("build_files", [])),
        "test_file_count": len(scan.get("test_files", [])),
        "todo_count": len(scan.get("todo_comments", [])),
        "cache_hit": bool(scan.get("cache_hit")),
    }


def _scan_warnings(scan: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not scan.get("readmes"):
        warnings.append("No README detected.")
    if not scan.get("test_files"):
        warnings.append("No test files detected.")
    if len(scan.get("todo_comments", [])) >= 25:
        warnings.append("Many TODO/FIXME comments detected.")
    if not scan.get("build_files"):
        warnings.append("No build/project files detected.")
    return warnings


def _scan_actions(scan: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if not scan.get("readmes"):
        actions.append("Document setup, run, and validation in a README.")
    if not scan.get("test_files"):
        actions.append("Add or document at least one validation path.")
    if scan.get("todo_comments"):
        actions.append("Triage TODO/FIXME comments into concrete tasks.")
    if scan.get("build_files"):
        actions.append("Run an approved validation health check.")
    return actions[:6]


def _dependency_manifests(root: Path) -> list[str]:
    names = {
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "packages.config",
    }
    manifests: list[str] = []
    for name in sorted(names):
        path = root / name
        if path.is_file() and is_safe_to_read(path, root):
            manifests.append(name)
    return manifests


def _detect_broken_markdown_references(root: Path, max_files: int = 100) -> list[dict[str, Any]]:
    broken: list[dict[str, Any]] = []
    checked = 0
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        dirnames[:] = [name for name in dirnames if not is_ignored_path(base / name, root)]
        for filename in filenames:
            if checked >= max_files:
                return broken
            if not filename.lower().endswith(".md"):
                continue
            path = base / filename
            if not is_safe_to_read(path, root):
                continue
            checked += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for match in pattern.finditer(line):
                    target = match.group(1).split("#", 1)[0].strip()
                    if not target or "://" in target or target.startswith(("mailto:", "#")):
                        continue
                    target_path = (path.parent / target).resolve()
                    try:
                        target_path.relative_to(root)
                    except ValueError:
                        continue
                    if target_path.exists():
                        continue
                    broken.append(
                        {
                            "file": path.relative_to(root).as_posix(),
                            "line": line_no,
                            "target": target,
                        }
                    )
                    if len(broken) >= 50:
                        return broken
    return broken


def _render_health_report(scan: dict[str, Any], validation: dict[str, Any], warnings: list[str], actions: list[str]) -> str:
    return "\n".join(
        [
            "## Summary",
            "",
            f"- Workspace: `{scan.get('workspace_name')}`",
            f"- Frameworks: {', '.join(scan.get('frameworks', []))}",
            f"- Indexed files: {scan.get('file_count', 0)}",
            f"- Build files: {len(scan.get('build_files', []))}",
            f"- Test files: {len(scan.get('test_files', []))}",
            f"- TODO/FIXME comments: {len(scan.get('todo_comments', []))}",
            f"- Validation commands: {len(validation.get('commands', []))}",
            "",
            "## Warnings",
            "",
            *(f"- {item}" for item in warnings[:20]),
            "",
            "## Suggested Actions",
            "",
            *(f"- {item}" for item in actions[:20]),
            "",
            "## Safety",
            "",
            "- This report is generated from local scans only.",
            "- Project source edits, deletes, package installs, build commands, and cloud context require approval.",
        ]
    )


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
