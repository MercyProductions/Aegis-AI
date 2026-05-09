from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .jobs import jobs_dashboard
from .knowledge import knowledge_graph
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .roadmap import next_best_tasks
from .tasks import ACTIVE_STATUSES, list_tasks
from .validation import validation_summary
from .workspace import WorkspaceScanner


def engineering_operations_dashboard(
    workspace: str | Path,
    *,
    project_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Build a read-only engineering operations dashboard for one or more local projects."""

    root = Path(workspace).resolve()
    primary = _project_snapshot(root)
    additional = [_safe_project_snapshot(Path(item).resolve()) for item in (project_roots or [])[:8]]
    projects = [primary, *[item for item in additional if item.get("available")]]
    unavailable = [item for item in additional if not item.get("available")]

    lifecycle = _lifecycle(primary)
    technical_debt = _technical_debt(primary)
    risk_monitoring = _risk_monitoring(primary, technical_debt)
    release_readiness = _release_readiness(primary, technical_debt, risk_monitoring)
    release_plan = _release_plan(primary, release_readiness, technical_debt, risk_monitoring, lifecycle)
    task_coordination = _task_coordination(primary, lifecycle, release_plan, technical_debt)
    maintenance_schedule = _maintenance_schedule(primary, lifecycle, technical_debt, risk_monitoring, release_readiness)
    productivity = _productivity_intelligence(primary, technical_debt, task_coordination)
    cross_project = _cross_project_awareness(projects, unavailable)
    suggested_actions = _suggested_next_actions(
        release_readiness,
        technical_debt,
        risk_monitoring,
        task_coordination,
        maintenance_schedule,
        productivity,
    )

    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "lifecycle": lifecycle,
        "project_health": _project_health(primary),
        "release_readiness": release_readiness,
        "release_plan": release_plan,
        "technical_debt": technical_debt,
        "task_coordination": task_coordination,
        "risk_monitoring": risk_monitoring,
        "maintenance_schedule": maintenance_schedule,
        "productivity_intelligence": productivity,
        "cross_project_awareness": cross_project,
        "operations_dashboard": {
            "project": primary["workspace_name"],
            "health_score": primary["quality"].get("score"),
            "lifecycle_stage": lifecycle["stage"],
            "release_status": release_readiness["status"],
            "active_risk_count": len(risk_monitoring["active_risks"]),
            "technical_debt_score": technical_debt["score"],
            "roadmap_progress": task_coordination["roadmap_progress"],
            "validation_status": _validation_status(primary),
            "next_action": suggested_actions[0]["title"] if suggested_actions else "Review operations dashboard.",
        },
        "suggested_next_actions": suggested_actions,
        "approval_policy": _approval_policy(),
    }


def _project_snapshot(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=False)
    quality = quality_dashboard(root, scan=scan)
    graph = knowledge_graph(root, scan=scan)
    validation = validation_summary(root)
    try:
        tasks = list_tasks(root)
    except Exception:
        tasks = []
    try:
        jobs = jobs_dashboard(root)
    except Exception:
        jobs = {}
    memory = ProjectMemory(root)
    return {
        "available": True,
        "workspace": str(root),
        "workspace_name": root.name,
        "scan": scan,
        "quality": quality,
        "knowledge": graph,
        "validation": validation,
        "tasks": tasks,
        "jobs": jobs,
        "memory": {
            "roadmap_text": _read_text(memory.root / "roadmap.md"),
            "decisions_text": _read_text(memory.root / "decisions.md"),
            "known_issues_text": _read_text(memory.root / "known-issues.md"),
            "validation_log_text": _read_text(memory.root / "validation-log.md"),
            "agent_history": _read_json_list(memory.root / "agent-history.json"),
        },
        "dependencies": _dependency_keys(root),
    }


def _safe_project_snapshot(root: Path) -> dict[str, Any]:
    if not root.exists() or not root.is_dir():
        return {"available": False, "workspace": str(root), "reason": "not a readable project directory"}
    try:
        return _project_snapshot(root)
    except Exception as exc:  # pragma: no cover - defensive per-project boundary.
        return {"available": False, "workspace": str(root), "reason": scrub(str(exc))}


def _project_health(project: dict[str, Any]) -> dict[str, Any]:
    quality = project["quality"]
    scan = project["scan"]
    return {
        "score": quality.get("score"),
        "grade": quality.get("grade"),
        "trend": quality.get("trend", {}),
        "frameworks": scan.get("frameworks", []),
        "file_count": scan.get("file_count", 0),
        "test_file_count": len(scan.get("test_files", [])),
        "todo_count": len(scan.get("todo_comments", [])),
        "validation_status": _validation_status(project),
        "top_risks": quality.get("top_risks", [])[:5],
        "warnings": quality.get("warnings", [])[:8],
    }


def _release_readiness(project: dict[str, Any], debt: dict[str, Any], risk_monitoring: dict[str, Any]) -> dict[str, Any]:
    quality = project["quality"]
    scan = project["scan"]
    score = int(quality.get("score") or 0)
    blockers: list[dict[str, str]] = []

    statuses = quality.get("statuses", {}) if isinstance(quality.get("statuses"), dict) else {}
    if _status_failed(statuses.get("build")) or _status_failed(statuses.get("test")) or _status_failed(statuses.get("validation")):
        blockers.append({"title": "Validation is failing", "severity": "high"})
    if not scan.get("test_files"):
        blockers.append({"title": "No test files detected", "severity": "high"})
    if not scan.get("readmes"):
        blockers.append({"title": "Project documentation is missing", "severity": "medium"})
    if debt["score"] >= 70:
        blockers.append({"title": "Technical debt is high", "severity": "high"})
    if any(item.get("severity") == "high" for item in risk_monitoring["active_risks"]):
        blockers.append({"title": "High-risk monitoring signals are active", "severity": "high"})

    readiness_score = score
    readiness_score -= min(25, len(blockers) * 8)
    readiness_score -= min(15, debt["score"] // 6)
    readiness_score = max(0, min(100, readiness_score))

    if blockers and any(item["severity"] == "high" for item in blockers):
        status = "blocked"
    elif readiness_score >= 85:
        status = "ready"
    elif readiness_score >= 70:
        status = "nearly_ready"
    else:
        status = "not_ready"

    return {
        "score": readiness_score,
        "status": status,
        "blockers": blockers[:8],
        "ready_for_release_candidate": status in {"ready", "nearly_ready"} and not blockers,
        "summary": _release_summary(status, readiness_score, blockers),
    }


def _release_plan(
    project: dict[str, Any],
    readiness: dict[str, Any],
    debt: dict[str, Any],
    risk_monitoring: dict[str, Any],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    validation_commands = project["validation"].get("commands", []) if isinstance(project.get("validation"), dict) else []
    top_risks = project["quality"].get("top_risks", [])[:5]
    milestones = [
        {
            "title": "Stabilize release blockers",
            "phase": "stabilization",
            "readiness_gate": "No high-severity validation or technical debt blockers.",
            "risks": [item.get("title", "Release blocker") for item in readiness.get("blockers", [])[:4]],
        },
        {
            "title": "Complete validation checkpoint",
            "phase": "release_candidate",
            "readiness_gate": "Detected validation path passes or manual validation is documented.",
            "risks": ["No validation command detected."] if not validation_commands else [],
        },
        {
            "title": "Refresh docs and roadmap",
            "phase": "release_candidate",
            "readiness_gate": "README, roadmap, decisions, and troubleshooting notes match current workflows.",
            "risks": [item["title"] for item in debt["signals"] if item.get("category") in {"stale_roadmap", "documentation"}][:4],
        },
    ]
    if lifecycle["stage"] == "maintenance_mode":
        milestones.append(
            {
                "title": "Prepare maintenance patch notes",
                "phase": "maintenance",
                "readiness_gate": "Only approved fixes, validation results, and known limitations are included.",
                "risks": [],
            }
        )

    implementation_phases = [
        {"phase": "triage", "goal": "Address release blockers and high-confidence debt signals first.", "owner": "planner"},
        {"phase": "stabilize", "goal": "Run approved validation and repair only failing workflows.", "owner": "tester"},
        {"phase": "document", "goal": "Record decisions, release notes, and residual risks.", "owner": "documentation"},
    ]
    validation_checkpoints = [
        {
            "name": command.get("name") or " ".join(command.get("command") or []),
            "command": command.get("command", []),
            "reason": command.get("reason", ""),
            "approval_required": True,
        }
        for command in validation_commands[:8]
        if isinstance(command, dict)
    ]
    if not validation_checkpoints:
        validation_checkpoints.append(
            {
                "name": "manual validation plan",
                "command": [],
                "reason": "No automated validation command detected.",
                "approval_required": False,
            }
        )

    return {
        "milestones": milestones,
        "implementation_phases": implementation_phases,
        "validation_checkpoints": validation_checkpoints,
        "risk_summaries": [
            {"title": item.get("title"), "severity": item.get("severity"), "reason": item.get("reason")}
            for item in top_risks
        ]
        + risk_monitoring["active_risks"][:5],
        "technical_debt_warnings": debt["signals"][:8],
        "release_notes_focus": _release_notes_focus(project, readiness, debt),
    }


def _technical_debt(project: dict[str, Any]) -> dict[str, Any]:
    scan = project["scan"]
    quality = project["quality"]
    knowledge = project["knowledge"]
    memory = project["memory"]
    snapshot = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), dict) else {}
    signals: list[dict[str, Any]] = []

    quick_fix_count = _quick_fix_count(scan, memory)
    if quick_fix_count:
        signals.append({"category": "quick_fixes", "title": "Repeated quick-fix language detected", "severity": "medium", "count": quick_fix_count})
    for item in knowledge.get("unstable_modules", [])[:5] if isinstance(knowledge.get("unstable_modules"), list) else []:
        signals.append({"category": "unstable_system", "title": f"Unstable system: {item.get('system')}", "severity": "high", "weight": item.get("weight")})
    for item in quality.get("high_risk_files", [])[:5] if isinstance(quality.get("high_risk_files"), list) else []:
        signals.append({"category": "large_risky_module", "title": f"High-risk file: {item.get('path')}", "severity": "high", "score": item.get("score"), "reasons": item.get("reasons", [])})
    for item in knowledge.get("architecture_hotspots", [])[:5] if isinstance(knowledge.get("architecture_hotspots"), list) else []:
        signals.append({"category": "architecture_drift", "title": f"Architecture hotspot: {item.get('title') or item.get('id')}", "severity": "medium", "evidence": item})
    if not scan.get("test_files"):
        signals.append({"category": "missing_tests", "title": "No test files detected", "severity": "high"})
    for item in snapshot.get("untested_core_modules", [])[:5] if isinstance(snapshot.get("untested_core_modules"), list) else []:
        signals.append({"category": "missing_tests", "title": f"Untested active area: {item.get('area')}", "severity": "medium", "code_file_count": item.get("code_file_count")})
    stale = _stale_roadmap(memory)
    if stale:
        signals.append(stale)
    if quality.get("warnings"):
        for warning in quality["warnings"][:5]:
            if "documentation" in str(warning).lower():
                signals.append({"category": "documentation", "title": str(warning), "severity": "medium"})

    score = min(100, sum(_debt_weight(item) for item in signals))
    cleanup = _cleanup_recommendations(project, signals)
    return {
        "score": score,
        "signals": signals[:18],
        "cleanup_recommendations": cleanup[:10],
        "refactor_priorities": _refactor_priorities(project, signals),
        "stability_tasks": _stability_tasks(project, signals),
    }


def _task_coordination(
    project: dict[str, Any],
    lifecycle: dict[str, Any],
    release_plan: dict[str, Any],
    debt: dict[str, Any],
) -> dict[str, Any]:
    tasks = project.get("tasks", [])
    active = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
    roadmap_tasks = next_best_tasks(project["scan"])
    validation_tasks = [
        {
            "title": f"Validate with {checkpoint['name']}",
            "kind": "validation",
            "approval_required": bool(checkpoint.get("approval_required")),
            "command": checkpoint.get("command", []),
        }
        for checkpoint in release_plan.get("validation_checkpoints", [])
    ]
    repair_tasks = []
    if _validation_status(project) == "failed":
        repair_tasks.append({"title": "Analyze latest validation failure", "kind": "repair", "approval_required": False})
    documentation_tasks = [
        {"title": item["title"], "kind": "documentation", "approval_required": True}
        for item in debt["cleanup_recommendations"]
        if item.get("category") in {"documentation", "stale_roadmap"}
    ][:5]
    testing_tasks = [
        {"title": item["title"], "kind": "testing", "approval_required": True}
        for item in debt["stability_tasks"]
        if item.get("category") == "missing_tests"
    ][:5]
    completed = len([task for task in tasks if task.get("status") == "completed"])
    total = len(tasks)
    return {
        "active_tasks": active[:12],
        "roadmap_tasks": roadmap_tasks[:8],
        "validation_tasks": validation_tasks[:8],
        "repair_tasks": repair_tasks,
        "documentation_tasks": documentation_tasks,
        "testing_tasks": testing_tasks,
        "coordination_notes": _coordination_notes(lifecycle, active, validation_tasks, repair_tasks),
        "roadmap_progress": {
            "tracked_tasks": total,
            "completed_tasks": completed,
            "active_tasks": len(active),
            "completion_ratio": round(completed / total, 2) if total else 0,
        },
    }


def _lifecycle(project: dict[str, Any]) -> dict[str, Any]:
    scan = project["scan"]
    quality = project["quality"]
    tasks = project.get("tasks", [])
    score = int(quality.get("score") or 0)
    validation = _validation_status(project)
    active_count = len([task for task in tasks if task.get("status") in ACTIVE_STATUSES])
    if scan.get("file_count", 0) < 12 and (not scan.get("test_files") or not scan.get("readmes")):
        stage = "prototype"
        confidence = 70
    elif validation == "failed" or score < 60:
        stage = "stabilization"
        confidence = 85
    elif score >= 85 and scan.get("test_files") and not quality.get("top_risks"):
        stage = "release_candidate"
        confidence = 75
    elif score >= 80 and active_count <= 1 and len(scan.get("todo_comments", [])) <= 3:
        stage = "maintenance_mode"
        confidence = 70
    else:
        stage = "active_development"
        confidence = 65
    return {
        "stage": stage,
        "confidence": confidence,
        "recommendation_mode": {
            "prototype": "Favor setup clarity, first tests, and lightweight architecture notes.",
            "active_development": "Coordinate roadmap work while keeping validation and documentation current.",
            "stabilization": "Prioritize broken validation, risky modules, and rollback confidence before new scope.",
            "release_candidate": "Freeze risky scope, validate packaging, and document known limitations.",
            "maintenance_mode": "Prefer small patches, dependency reviews, and scheduled health checks.",
        }[stage],
    }


def _risk_monitoring(project: dict[str, Any], debt: dict[str, Any]) -> dict[str, Any]:
    quality = project["quality"]
    snapshot = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), dict) else {}
    trend = quality.get("trend", {}) if isinstance(quality.get("trend"), dict) else {}
    active_risks: list[dict[str, Any]] = []
    if trend.get("direction") == "degrading":
        active_risks.append({"category": "growing_instability", "severity": "high", "title": "Health trend is degrading", "evidence": trend})
    if _validation_status(project) == "failed":
        active_risks.append({"category": "validation_failures", "severity": "high", "title": "Latest validation failed"})
    if snapshot.get("complexity_hotspots"):
        active_risks.append({"category": "architecture_complexity", "severity": "medium", "title": "Complexity hotspots are active", "files": snapshot.get("complexity_hotspots", [])[:5]})
    if snapshot.get("dependency_changes") or snapshot.get("dependency_manifest_count", 0) >= 3:
        active_risks.append({"category": "dependency_risk", "severity": "medium", "title": "Dependency risk needs review", "evidence": snapshot.get("dependency_changes", [])})
    if snapshot.get("slow_validation_commands"):
        active_risks.append({"category": "performance_regression", "severity": "medium", "title": "Slow validation commands detected", "commands": snapshot.get("slow_validation_commands", [])[:5]})
    if debt["score"] >= 70:
        active_risks.append({"category": "technical_debt", "severity": "high", "title": "Technical debt score is high", "score": debt["score"]})
    return {
        "active_risks": active_risks[:12],
        "growing_instability": trend,
        "validation_failure_count": _validation_failure_count(project),
        "architecture_complexity_spikes": snapshot.get("complexity_hotspots", [])[:8],
        "dependency_risks": {
            "manifest_count": snapshot.get("dependency_manifest_count", 0),
            "dependency_file_count": snapshot.get("dependency_file_count", 0),
            "changes": snapshot.get("dependency_changes", []),
        },
        "performance_regressions": snapshot.get("slow_validation_commands", [])[:8],
    }


def _maintenance_schedule(
    project: dict[str, Any],
    lifecycle: dict[str, Any],
    debt: dict[str, Any],
    risks: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    jobs = project.get("jobs", {})
    scheduled_jobs = jobs.get("scheduled_jobs", []) if isinstance(jobs, dict) else []
    immediate: list[dict[str, str]] = []
    if readiness["status"] == "blocked":
        immediate.append({"title": "Release blocker triage", "reason": readiness["summary"]})
    if risks["performance_regressions"]:
        immediate.append({"title": "Validation performance review", "reason": "Slow validation commands are recurring."})
    return {
        "refactor_windows": _schedule_items(debt["refactor_priorities"], "Refactor window", "weekly"),
        "dependency_updates": _dependency_schedule(project),
        "validation_sweeps": _validation_schedule(project, scheduled_jobs),
        "optimization_passes": immediate[:5],
        "documentation_refreshes": _documentation_schedule(project, debt),
        "lifecycle_cadence": _lifecycle_cadence(lifecycle["stage"]),
    }


def _productivity_intelligence(project: dict[str, Any], debt: dict[str, Any], coordination: dict[str, Any]) -> dict[str, Any]:
    memory = project["memory"]
    validation_log = memory.get("validation_log_text", "")
    pain_points = _pain_points(project, debt)
    slow_workflows = project["quality"].get("current_snapshot", {}).get("slow_validation_commands", []) if isinstance(project["quality"].get("current_snapshot"), dict) else []
    manual_tasks = []
    if not project["validation"].get("commands"):
        manual_tasks.append({"title": "Manual validation discovery", "reason": "No automated validation command is configured."})
    if coordination["documentation_tasks"]:
        manual_tasks.append({"title": "Manual documentation refresh", "reason": "Docs or roadmap need synchronization."})
    bug_categories = _bug_categories(validation_log + "\n" + memory.get("known_issues_text", ""))
    automation = []
    if manual_tasks:
        automation.append({"title": "Create a safe recurring maintenance job", "reason": "Repeated manual checks are visible in operations data."})
    if slow_workflows:
        automation.append({"title": "Add validation timing diagnostics", "reason": "Slow commands are recurring."})
    if debt["signals"]:
        automation.append({"title": "Schedule technical debt review", "reason": "Debt signals are active across code, tests, or docs."})
    return {
        "recurring_pain_points": pain_points[:10],
        "slow_workflows": slow_workflows[:8],
        "repeated_manual_tasks": manual_tasks[:8],
        "bottlenecks": _bottlenecks(project, coordination, debt),
        "repeated_bug_categories": bug_categories,
        "automation_opportunities": automation[:8],
    }


def _cross_project_awareness(projects: list[dict[str, Any]], unavailable: list[dict[str, Any]]) -> dict[str, Any]:
    frameworks: Counter[str] = Counter()
    dependencies: Counter[str] = Counter()
    validation_commands: Counter[str] = Counter()
    systems: Counter[str] = Counter()
    project_summaries = []
    for project in projects:
        scan = project["scan"]
        quality = project["quality"]
        frameworks.update(str(item) for item in scan.get("frameworks", []))
        dependencies.update(project.get("dependencies", []))
        for command in project.get("validation", {}).get("commands", []) if isinstance(project.get("validation"), dict) else []:
            validation_commands[str(command.get("name") or " ".join(command.get("command") or []))] += 1
        for cluster in project.get("knowledge", {}).get("clusters", []) if isinstance(project.get("knowledge"), dict) else []:
            systems[str(cluster.get("system") or "")] += 1
        project_summaries.append(
            {
                "workspace": project["workspace"],
                "name": project["workspace_name"],
                "health_score": quality.get("score"),
                "frameworks": scan.get("frameworks", []),
                "lifecycle_stage": _lifecycle(project)["stage"],
            }
        )
    repeated_frameworks = [name for name, count in frameworks.most_common() if name and count >= 2]
    shared_dependencies = [name for name, count in dependencies.most_common() if name and count >= 2]
    shared_validation = [name for name, count in validation_commands.most_common() if name and count >= 2]
    repeated_systems = [name for name, count in systems.most_common() if name and count >= 2]
    return {
        "projects": project_summaries,
        "unavailable_projects": unavailable,
        "shared_libraries": shared_dependencies[:12],
        "shared_tooling": _dedupe([*repeated_frameworks, *shared_validation])[:12],
        "shared_architecture_patterns": repeated_systems[:12],
        "repeated_systems": repeated_frameworks[:12],
        "coordination_notes": _cross_project_notes(project_summaries, shared_dependencies, repeated_frameworks, unavailable),
    }


def _suggested_next_actions(
    readiness: dict[str, Any],
    debt: dict[str, Any],
    risks: dict[str, Any],
    coordination: dict[str, Any],
    schedule: dict[str, Any],
    productivity: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if readiness.get("blockers"):
        blocker = readiness["blockers"][0]
        actions.append({"title": f"Resolve release blocker: {blocker['title']}", "priority": "high", "approval_required": False})
    if risks.get("active_risks"):
        risk = risks["active_risks"][0]
        actions.append({"title": f"Investigate risk: {risk['title']}", "priority": "high" if risk.get("severity") == "high" else "medium", "approval_required": False})
    if debt.get("cleanup_recommendations"):
        item = debt["cleanup_recommendations"][0]
        actions.append({"title": item["title"], "priority": item.get("priority", "medium"), "approval_required": True})
    if coordination.get("validation_tasks"):
        item = coordination["validation_tasks"][0]
        actions.append({"title": item["title"], "priority": "medium", "approval_required": bool(item.get("approval_required"))})
    if productivity.get("automation_opportunities"):
        item = productivity["automation_opportunities"][0]
        actions.append({"title": item["title"], "priority": "low", "approval_required": False})
    for item in schedule.get("documentation_refreshes", [])[:1]:
        actions.append({"title": item["title"], "priority": "low", "approval_required": True})
    return _dedupe(actions)[:8]


def _approval_policy() -> dict[str, Any]:
    return {
        "uncontrolled_autonomy": False,
        "automatic_actions_allowed": ["scan", "summarize", "report", "recommend"],
        "approval_required_for": ["file_edit", "file_delete", "build_command", "install_package", "cloud_context", "release_decision"],
        "notes": [
            "Operations dashboards coordinate work but do not apply edits.",
            "Release decisions, risky commands, package changes, and cloud calls remain human-approved.",
        ],
    }


def _validation_status(project: dict[str, Any]) -> str:
    statuses = project.get("quality", {}).get("statuses", {}) if isinstance(project.get("quality"), dict) else {}
    for name in ("build", "test", "lint", "validation"):
        status = statuses.get(name)
        if _status_failed(status):
            return "failed"
    if project.get("validation", {}).get("commands"):
        return "configured"
    return "not_configured"


def _status_failed(status: Any) -> bool:
    return isinstance(status, dict) and status.get("status") == "failed"


def _release_summary(status: str, readiness_score: int, blockers: list[dict[str, str]]) -> str:
    if status == "ready":
        return f"Release readiness is strong at {readiness_score}/100."
    if status == "nearly_ready":
        return f"Release readiness is close at {readiness_score}/100; finish validation and docs checks."
    if blockers:
        return f"Release is blocked by {blockers[0]['title']}."
    return f"Release readiness is {readiness_score}/100; continue stabilization before release candidate."


def _quick_fix_count(scan: dict[str, Any], memory: dict[str, Any]) -> int:
    count = 0
    quick_terms = ("quick fix", "temporary", "hack", "workaround", "fixme")
    for item in scan.get("todo_comments", []) if isinstance(scan.get("todo_comments"), list) else []:
        text = str(item.get("text") or "").lower() if isinstance(item, dict) else ""
        if any(term in text for term in quick_terms):
            count += 1
    for item in memory.get("agent_history", [])[-100:]:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(key) or "") for key in ("event", "summary", "title")).lower()
        if any(term in text for term in quick_terms):
            count += 1
    return count


def _stale_roadmap(memory: dict[str, Any]) -> dict[str, Any] | None:
    roadmap = memory.get("roadmap_text", "")
    if not roadmap.strip():
        return {"category": "stale_roadmap", "title": "No roadmap memory found", "severity": "medium"}
    items = [line for line in roadmap.splitlines() if line.strip().startswith(("-", "1.", "2.", "3.", "4.", "5."))]
    if len(items) >= 12:
        return {"category": "stale_roadmap", "title": "Roadmap backlog may need pruning", "severity": "low", "item_count": len(items)}
    return None


def _debt_weight(signal: dict[str, Any]) -> int:
    if signal.get("severity") == "high":
        return 16
    if signal.get("severity") == "medium":
        return 9
    return 4


def _cleanup_recommendations(project: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for item in project["quality"].get("top_cleanup_tasks", [])[:5]:
        recommendations.append({"title": item.get("title"), "priority": item.get("severity", "medium"), "category": item.get("category", "cleanup"), "reason": item.get("reason")})
    for signal in signals:
        category = signal.get("category", "cleanup")
        if category == "missing_tests":
            recommendations.append({"title": "Add or document validation around untested areas", "priority": "high", "category": category})
        elif category == "architecture_drift":
            recommendations.append({"title": "Review architecture hotspot before next feature work", "priority": "medium", "category": category})
        elif category == "quick_fixes":
            recommendations.append({"title": "Convert repeated quick fixes into tracked cleanup tasks", "priority": "medium", "category": category})
        elif category in {"documentation", "stale_roadmap"}:
            recommendations.append({"title": "Refresh roadmap and release documentation", "priority": "low", "category": category})
    return _dedupe(recommendations)


def _refactor_priorities(project: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priorities = []
    for signal in signals:
        if signal.get("category") in {"large_risky_module", "architecture_drift", "unstable_system"}:
            priorities.append({"title": signal.get("title"), "priority": signal.get("severity", "medium"), "category": signal.get("category")})
    if not priorities and project["quality"].get("high_risk_files"):
        item = project["quality"]["high_risk_files"][0]
        priorities.append({"title": f"Review high-risk file {item.get('path')}", "priority": "medium", "category": "large_risky_module"})
    return priorities[:8]


def _stability_tasks(project: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    if _validation_status(project) == "failed":
        tasks.append({"title": "Repair failing validation before new scope", "priority": "high", "category": "validation"})
    for signal in signals:
        if signal.get("category") == "missing_tests":
            tasks.append({"title": signal.get("title"), "priority": signal.get("severity", "medium"), "category": "missing_tests"})
    if project["quality"].get("warnings"):
        tasks.append({"title": "Triage current health warnings", "priority": "medium", "category": "quality"})
    return tasks[:8]


def _coordination_notes(
    lifecycle: dict[str, Any],
    active: list[dict[str, Any]],
    validation_tasks: list[dict[str, Any]],
    repair_tasks: list[dict[str, Any]],
) -> list[str]:
    notes = [f"Lifecycle mode: {lifecycle['recommendation_mode']}"]
    if active:
        notes.append("Keep active tasks ordered by validation and release risk.")
    if repair_tasks:
        notes.append("Run repair planning before continuing roadmap tasks.")
    if validation_tasks:
        notes.append("Validation commands remain approval-gated before execution.")
    return notes


def _validation_failure_count(project: dict[str, Any]) -> int:
    text = project.get("memory", {}).get("validation_log_text", "")
    return len(re.findall(r"^##\s+.+?\s+-\s+failed\s*$", text, flags=re.MULTILINE))


def _schedule_items(items: list[dict[str, Any]], prefix: str, cadence: str) -> list[dict[str, str]]:
    return [{"title": f"{prefix}: {item.get('title')}", "cadence": cadence, "reason": item.get("category", "maintenance")} for item in items[:5]]


def _dependency_schedule(project: dict[str, Any]) -> list[dict[str, str]]:
    dependencies = project.get("dependencies", [])
    if not dependencies:
        return [{"title": "Dependency inventory check", "cadence": "monthly", "reason": "No dependency manifest or dependency keys found."}]
    return [{"title": "Dependency review", "cadence": "weekly", "reason": f"{len(dependencies)} dependency keys detected."}]


def _validation_schedule(project: dict[str, Any], scheduled_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validation_jobs = [job for job in scheduled_jobs if "validation" in str(job.get("workflow", "")).lower() or "build" in str(job.get("workflow", "")).lower()]
    if validation_jobs:
        return [{"title": job.get("title"), "cadence": job.get("schedule"), "approval_required": bool(job.get("approval_gates"))} for job in validation_jobs[:5]]
    commands = project.get("validation", {}).get("commands", [])
    return [{"title": "Validation sweep", "cadence": "daily", "approval_required": bool(commands)}]


def _documentation_schedule(project: dict[str, Any], debt: dict[str, Any]) -> list[dict[str, str]]:
    if any(item.get("category") in {"documentation", "stale_roadmap"} for item in debt.get("signals", [])):
        return [{"title": "Documentation refresh", "cadence": "weekly", "reason": "Documentation or roadmap drift is active."}]
    if not project["scan"].get("readmes"):
        return [{"title": "Create README/update setup docs", "cadence": "this_week", "reason": "No README detected."}]
    return [{"title": "Roadmap and decisions review", "cadence": "monthly", "reason": "Keep memory aligned with release state."}]


def _lifecycle_cadence(stage: str) -> dict[str, str]:
    return {
        "prototype": {"review": "weekly", "focus": "setup, first tests, and architecture notes"},
        "active_development": {"review": "twice_weekly", "focus": "roadmap coordination and validation freshness"},
        "stabilization": {"review": "daily", "focus": "failing validation, risky files, and rollback readiness"},
        "release_candidate": {"review": "daily_until_release", "focus": "release blockers and packaging confidence"},
        "maintenance_mode": {"review": "weekly", "focus": "small fixes, dependency review, and docs freshness"},
    }.get(stage, {"review": "weekly", "focus": "operations hygiene"})


def _pain_points(project: dict[str, Any], debt: dict[str, Any]) -> list[dict[str, Any]]:
    points = []
    if debt.get("signals"):
        points.append({"title": "Technical debt interrupts planning", "count": len(debt["signals"])})
    if project["scan"].get("todo_comments"):
        points.append({"title": "TODO/FIXME backlog needs triage", "count": len(project["scan"]["todo_comments"])})
    if _validation_failure_count(project):
        points.append({"title": "Validation failures recur", "count": _validation_failure_count(project)})
    if project["quality"].get("current_snapshot", {}).get("slow_validation_commands"):
        points.append({"title": "Validation is slow", "count": len(project["quality"]["current_snapshot"]["slow_validation_commands"])})
    return points


def _bug_categories(text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    categories = {
        "validation": ("test", "build", "validation", "pytest", "lint"),
        "runtime": ("exception", "traceback", "crash", "null", "undefined"),
        "integration": ("api", "endpoint", "client", "server", "sync"),
        "model": ("ollama", "model", "provider", "timeout"),
        "rollback": ("rollback", "checkpoint", "restore"),
    }
    results = []
    for category, terms in categories.items():
        count = sum(lowered.count(term) for term in terms)
        if count:
            results.append({"category": category, "count": count})
    return sorted(results, key=lambda item: item["count"], reverse=True)[:8]


def _bottlenecks(project: dict[str, Any], coordination: dict[str, Any], debt: dict[str, Any]) -> list[dict[str, Any]]:
    bottlenecks = []
    if coordination["active_tasks"] and coordination["roadmap_progress"]["completion_ratio"] < 0.5:
        bottlenecks.append({"title": "Active task backlog is outpacing completion", "severity": "medium"})
    if debt["score"] >= 70:
        bottlenecks.append({"title": "Technical debt score is slowing release readiness", "severity": "high"})
    if not project["validation"].get("commands"):
        bottlenecks.append({"title": "No automated validation command", "severity": "medium"})
    return bottlenecks


def _cross_project_notes(
    project_summaries: list[dict[str, Any]],
    shared_dependencies: list[str],
    repeated_frameworks: list[str],
    unavailable: list[dict[str, Any]],
) -> list[str]:
    notes = []
    if len(project_summaries) <= 1:
        notes.append("Only one project is in this operations dashboard.")
    if shared_dependencies:
        notes.append("Shared dependencies suggest coordinated update windows.")
    if repeated_frameworks:
        notes.append("Repeated tooling/frameworks can share validation and onboarding patterns.")
    if unavailable:
        notes.append("Some requested projects were unavailable and skipped.")
    return notes


def _release_notes_focus(project: dict[str, Any], readiness: dict[str, Any], debt: dict[str, Any]) -> list[str]:
    focus = [f"Release readiness: {readiness['status']} ({readiness['score']}/100)."]
    if readiness.get("blockers"):
        focus.append("Known blockers: " + ", ".join(item["title"] for item in readiness["blockers"][:4]) + ".")
    if debt.get("signals"):
        focus.append("Technical debt to mention: " + ", ".join(item["title"] for item in debt["signals"][:3]) + ".")
    validation = _validation_status(project)
    focus.append(f"Validation status: {validation}.")
    return focus


def _dependency_keys(root: Path) -> list[str]:
    package = root / "package.json"
    dependencies: set[str] = set()
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                value = data.get(key)
                if isinstance(value, dict):
                    dependencies.update(str(name) for name in value)
    for name in ("requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"):
        if (root / name).is_file():
            dependencies.add(name)
    return sorted(dependencies)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _dedupe(items: list[dict[str, Any]] | list[str]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
