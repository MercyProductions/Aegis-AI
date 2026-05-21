from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from . import deployment_intelligence, dogfooding, workflow_runtime
from .diagnostics import scrub
from .knowledge import architecture_summary, impact_analysis, knowledge_graph, knowledge_relationships, search_knowledge
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .quality_gates import benchmark_dashboard, benchmark_suites, quality_gate_dashboard
from .validation import validation_summary
from .workspace import WorkspaceScanner


ENGINEERING_WORKSPACE_FILE = "engineering-workspace-dashboard.json"
ENGINEERING_WORKSPACE_SUMMARY = "engineering-workspace-summary.md"

ENGINEERING_WORKFLOWS: tuple[dict[str, Any], ...] = (
    {
        "id": "feature_implementation",
        "label": "Feature Implementation",
        "speed_focus": "Start from impacted systems, target files, validation gates, and checkpoint requirements.",
        "primary_views": ["architecture_map", "impact_visualization", "validation_review", "workflow_continuity"],
    },
    {
        "id": "bug_fixing",
        "label": "Bug Fixing",
        "speed_focus": "Prioritize recurring failure areas, likely breakage edges, and focused validation commands.",
        "primary_views": ["validation_review", "root_cause_candidates", "repair_history", "rollback_readiness"],
    },
    {
        "id": "refactoring",
        "label": "Refactoring",
        "speed_focus": "Use dependency-aware search and impact scoring before touching shared modules.",
        "primary_views": ["dependency_visualization", "symbol_relationships", "technical_debt", "risk_modules"],
    },
    {
        "id": "architecture_exploration",
        "label": "Architecture Exploration",
        "speed_focus": "Move through project maps, services, entry points, runtime boundaries, and call-flow edges.",
        "primary_views": ["project_map", "service_relationships", "call_flow", "entry_points"],
    },
    {
        "id": "deployment_preparation",
        "label": "Deployment Preparation",
        "speed_focus": "Review pipeline risk, release readiness, validation gates, secrets boundaries, and rollback options.",
        "primary_views": ["deployment_readiness", "quality_gates", "environment_risk", "release_history"],
    },
)


def engineering_workspace_dashboard(
    workspace: str | Path,
    *,
    refresh: bool = False,
    persist: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    scan = WorkspaceScanner(root).scan(persist=persist or refresh)
    graph = _knowledge_graph_for_dashboard(root, scan=scan, persist=persist or refresh, refresh=refresh)
    architecture = architecture_summary(root, refresh=False)
    quality = _quality_dashboard_for_dashboard(root, scan=scan, persist=persist)
    gates = quality_gate_dashboard(root, limit=limit)
    validation = validation_review(root, scan=scan, quality=quality, gates=gates)
    deployment = _safe_call("deployment", lambda: deployment_intelligence.deployment_dashboard(root, refresh=refresh, limit=limit), {})
    workflows = _safe_call("workflow_statistics", lambda: workflow_runtime.workflow_statistics(root), {})
    dogfood = _safe_call("dogfooding", lambda: dogfooding.dogfooding_dashboard(root, limit=limit, persist=persist), {})
    benchmarks = _benchmark_comparison(root, gates=gates)
    project_map = engineering_project_map(root, graph=graph, scan=scan, limit=limit)
    continuity = workflow_continuity(root, workflows=workflows, quality=quality, validation=validation)
    large_project = _large_project_profile(scan, graph)
    observability = _engineering_observability(
        scan=scan,
        graph=graph,
        quality=quality,
        validation=validation,
        workflows=workflows,
        dogfood=dogfood,
        benchmarks=benchmarks,
    )
    recommendations = _engineering_recommendations(
        quality=quality,
        validation=validation,
        deployment=deployment,
        continuity=continuity,
        large_project=large_project,
        dogfood=dogfood,
    )
    result = {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": utc_now(),
        "product": "Auralith Engineering Workspace",
        "positioning": "Elite local-first AI engineering environment for real software workflows.",
        "workflow_lanes": list(ENGINEERING_WORKFLOWS),
        "project_map": project_map,
        "architecture": _architecture_focus(architecture),
        "advanced_search": _search_modes(),
        "validation": validation,
        "deployment": _deployment_focus(deployment),
        "large_project": large_project,
        "continuity": continuity,
        "dashboards": _engineering_dashboards(quality, gates, deployment, workflows, benchmarks),
        "observability": observability,
        "benchmark_comparisons": benchmarks,
        "recommendations": recommendations,
        "state_files": _state_files(root),
    }
    if persist:
        memory = ProjectMemory(root)
        memory.write_json(ENGINEERING_WORKSPACE_FILE, result)
        memory.write_generated_markdown(ENGINEERING_WORKSPACE_SUMMARY, "Auralith Engineering Workspace", _summary_markdown(result))
        dashboard_path = Path(result["state_files"]["dashboard"])
        summary_path = Path(result["state_files"]["summary"])
        result["state_files"]["dashboard_persisted"] = dashboard_path.is_file()
        result["state_files"]["summary_persisted"] = summary_path.is_file()
        if not result["state_files"]["dashboard_persisted"] or not result["state_files"]["summary_persisted"]:
            result.setdefault("warnings", []).append("Engineering Workspace state files could not be fully persisted; dashboard data was returned in-memory.")
    return result


def engineering_project_map(
    workspace: str | Path,
    *,
    graph: dict[str, Any] | None = None,
    scan: dict[str, Any] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    scan_data = scan or WorkspaceScanner(root).scan(persist=False)
    graph_data = graph or _knowledge_graph_for_dashboard(root, scan=scan_data, persist=True, refresh=False)
    nodes = [node for node in graph_data.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph_data.get("edges", []) if isinstance(edge, dict)]
    max_items = max(1, min(250, int(limit)))
    degree = Counter()
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source:
            degree[source] += 1
        if target:
            degree[target] += 1
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    hotspots = [
        {
            "node_id": node_id,
            "degree": count,
            "label": str(node_by_id.get(node_id, {}).get("label") or node_id),
            "type": str(node_by_id.get(node_id, {}).get("type") or "unknown"),
            "path": str(node_by_id.get(node_id, {}).get("path") or ""),
        }
        for node_id, count in degree.most_common(max_items)
    ]
    relationship_edges = [
        edge
        for edge in edges
        if edge.get("type") in {"imports", "depends_on", "calls", "api_consumer", "route_binding", "tested_by", "owns"}
    ][:max_items]
    services = [
        _small_node(node)
        for node in nodes
        if node.get("type") in {"service", "module", "api", "runtime_boundary", "build_system", "ui_component"}
    ][:max_items]
    return {
        "workspace": str(root),
        "file_count": int(scan_data.get("file_count") or 0),
        "language_mix": scan_data.get("languages", {}),
        "frameworks": scan_data.get("frameworks", []),
        "entry_points": scan_data.get("entry_points", [])[:25],
        "build_files": scan_data.get("build_files", [])[:25],
        "services": services,
        "dependency_visualization": {
            "nodes": [_small_node(node) for node in nodes[:max_items]],
            "edges": relationship_edges,
            "hotspots": hotspots[:25],
        },
        "service_relationships": {
            "service_count": len(services),
            "edge_types": sorted({str(edge.get("type")) for edge in relationship_edges if edge.get("type")}),
            "edges": relationship_edges[:50],
        },
        "impact_hotspots": hotspots[:15],
        "graph_version": graph_data.get("version"),
        "indexing": graph_data.get("indexing", {}),
    }


def engineering_search(
    workspace: str | Path,
    query: str,
    *,
    mode: str = "architecture",
    focus: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    clean_query = scrub(query).strip()
    search_mode = _normalize_search_mode(mode)
    max_items = max(1, min(100, int(limit)))
    search = search_knowledge(root, clean_query, limit=max_items, persist=True)
    relationship_focus = focus or _first_result_focus(search)
    relationships = (
        knowledge_relationships(root, relationship_focus, depth=2 if search_mode in {"dependency", "architecture"} else 1, limit=max_items, persist=True)
        if relationship_focus
        else {"focus_node": None, "nodes": [], "edges": []}
    )
    impact = (
        impact_analysis(root, relationship_focus, limit=max_items, persist=True)
        if relationship_focus and search_mode in {"dependency", "architecture", "workflow"}
        else None
    )
    return {
        "workspace": str(root),
        "query": clean_query,
        "mode": search_mode,
        "mode_description": _search_mode_description(search_mode),
        "results": search.get("results", []),
        "relationship_focus": relationship_focus or "",
        "relationships": {
            "focus_node": relationships.get("focus_node"),
            "nodes": relationships.get("nodes", [])[:max_items],
            "edges": relationships.get("edges", [])[:max_items],
        },
        "impact": impact,
        "suggested_next_actions": _search_next_actions(search_mode, search, relationships, impact),
        "semantic_note": "Current search is graph/lexical and semantic-ready; vector providers can plug into the same result contract later.",
    }


def validation_review(
    workspace: str | Path,
    *,
    scan: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    scan_data = scan or WorkspaceScanner(root).scan(persist=False)
    quality_data = quality or quality_dashboard(root, scan=scan_data)
    gate_data = gates or quality_gate_dashboard(root)
    summary = validation_summary(root)
    commands = summary.get("commands", []) if isinstance(summary.get("commands"), list) else []
    latest = gate_data.get("latest") if isinstance(gate_data.get("latest"), dict) else None
    current = quality_data.get("current_snapshot", {}) if isinstance(quality_data.get("current_snapshot"), dict) else {}
    slow_commands = current.get("slow_validation_commands", []) if isinstance(current.get("slow_validation_commands"), list) else []
    failing_systems = quality_data.get("failing_systems", []) if isinstance(quality_data.get("failing_systems"), list) else []
    blockers = latest.get("blockers", []) if isinstance(latest, dict) and isinstance(latest.get("blockers"), list) else []
    root_causes = _root_cause_candidates(current, blockers, failing_systems)
    return {
        "workspace": str(root),
        "command_count": len(commands),
        "commands": commands,
        "latest_gate": latest,
        "validation_summary": summary,
        "validation_prioritization": _validation_prioritization(commands, scan_data, slow_commands),
        "repair_explanations": _repair_explanations(current, latest),
        "root_cause_candidates": root_causes,
        "regression_detection": {
            "large_risky_diff": current.get("large_risky_diff", {}),
            "failing_files": current.get("failing_files", []),
            "repeated_repair_attempts": current.get("repeated_repair_attempts", 0),
            "status": "needs_review" if root_causes or blockers else "clear",
        },
        "validation_bottlenecks": slow_commands,
        "recommended_next_validation": _recommended_validation(commands, blockers, slow_commands),
    }


def workflow_continuity(
    workspace: str | Path,
    *,
    workflows: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    workflow_stats = workflows or _safe_call("workflow_statistics", lambda: workflow_runtime.workflow_statistics(root), {})
    quality_data = quality or quality_dashboard(root)
    validation_data = validation or validation_review(root, quality=quality_data)
    recent_events = workflow_stats.get("recent_events", []) if isinstance(workflow_stats.get("recent_events"), list) else []
    interrupted = [
        event
        for event in recent_events
        if str(event.get("event") or "").lower() in {"workflow.paused", "workflow.failed", "workflow.cancelled", "validation.failed"}
        or str(event.get("status") or "").lower() in {"failed", "cancelled", "waiting_input"}
    ][:10]
    return {
        "workspace": str(root),
        "active_workflow_count": int(workflow_stats.get("active_workflow_count") or 0),
        "workflow_count": int(workflow_stats.get("workflow_count") or 0),
        "resume_candidates": _resume_candidates(workflow_stats, interrupted),
        "roadmap_continuation": _roadmap_continuation_hint(quality_data, validation_data),
        "branch_aware_workflows": _branch_awareness(quality_data),
        "checkpoint_linking": {
            "required_before_apply": True,
            "recommendation": "Link every feature, repair, and refactor workflow to a checkpoint before apply.",
        },
        "interrupted_work": interrupted,
    }


def _engineering_dashboards(
    quality: dict[str, Any],
    gates: dict[str, Any],
    deployment: dict[str, Any],
    workflows: dict[str, Any],
    benchmarks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project_health": {
            "score": quality.get("score"),
            "grade": quality.get("grade"),
            "top_risks": quality.get("top_risks", []),
            "technical_debt_indicators": quality.get("top_cleanup_tasks", []),
        },
        "validation_health": {
            "latest": gates.get("latest"),
            "statistics": gates.get("statistics", {}),
            "benchmark_history": gates.get("benchmark_history", []),
        },
        "roadmap_progress": {
            "workflow_count": workflows.get("workflow_count", 0),
            "active_workflow_count": workflows.get("active_workflow_count", 0),
            "status_counts": workflows.get("status_counts", {}),
        },
        "deployment_readiness": _deployment_focus(deployment),
        "benchmark_comparisons": benchmarks,
    }


def _engineering_observability(
    *,
    scan: dict[str, Any],
    graph: dict[str, Any],
    quality: dict[str, Any],
    validation: dict[str, Any],
    workflows: dict[str, Any],
    dogfood: dict[str, Any],
    benchmarks: dict[str, Any],
) -> dict[str, Any]:
    current = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), dict) else {}
    friction = dogfood.get("friction", {}) if isinstance(dogfood.get("friction"), dict) else {}
    return {
        "validation_bottlenecks": validation.get("validation_bottlenecks", []),
        "risky_modules": quality.get("high_risk_files", []),
        "recurring_repair_patterns": {
            "repeated_repair_attempts": current.get("repeated_repair_attempts", 0),
            "repair_success_rate": (workflows.get("repair", {}) or {}).get("success_rate") if isinstance(workflows.get("repair"), dict) else None,
        },
        "architectural_hotspots": graph.get("architecture_hotspots", [])[:15],
        "workflow_efficiency": {
            "average_duration_seconds": workflows.get("average_duration_seconds", 0),
            "event_count": workflows.get("event_count", 0),
            "completion_status_counts": workflows.get("status_counts", {}),
            "dogfooding_friction": friction.get("pain_points", []),
        },
        "indexing": graph.get("indexing", {}),
        "large_project": {
            "file_count": scan.get("file_count", 0),
            "language_count": len(scan.get("languages", {}) if isinstance(scan.get("languages"), dict) else {}),
        },
        "benchmarks": benchmarks.get("statistics", {}),
    }


def _benchmark_comparison(workspace: Path, *, gates: dict[str, Any]) -> dict[str, Any]:
    dashboard = _safe_call("benchmark_dashboard", lambda: benchmark_dashboard(workspace), {})
    history = dashboard.get("history", []) if isinstance(dashboard.get("history"), list) else []
    latest = dashboard.get("latest") if isinstance(dashboard.get("latest"), dict) else None
    gate_stats = gates.get("statistics", {}) if isinstance(gates.get("statistics"), dict) else {}
    return {
        "suites": benchmark_suites(),
        "latest": latest,
        "history": history[:10],
        "statistics": dashboard.get("statistics", {}),
        "comparison_targets": [
            {"id": "workflow_speed", "current": gate_stats.get("run_count", 0), "goal": "more completed workflows with fewer blocked gates"},
            {"id": "validation_reliability", "current": gate_stats.get("pass_rate"), "goal": "higher validation pass rate after focused repair"},
            {"id": "repair_quality", "current": gate_stats.get("repair_score"), "goal": "lower repair-loop frequency"},
            {"id": "indexing_performance", "current": "tracked in knowledge indexing duration", "goal": "stable partial refreshes on large repos"},
            {"id": "orchestration_efficiency", "current": "tracked in workflow statistics", "goal": "shorter blocked/waiting intervals"},
        ],
    }


def _large_project_profile(scan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    languages = scan.get("languages", {}) if isinstance(scan.get("languages"), dict) else {}
    file_count = int(scan.get("file_count") or 0)
    build_files = scan.get("build_files", []) if isinstance(scan.get("build_files"), list) else []
    language_names = {str(name).lower() for name in languages}
    traits = []
    if file_count >= 1000:
        traits.append("large_project")
    if len(languages) >= 4:
        traits.append("mixed_language_repo")
    if any("c++" in name or "c/c++" in name for name in language_names) or any(str(path).endswith((".sln", ".vcxproj", "CMakeLists.txt")) for path in build_files):
        traits.append("large_cpp_ready")
    if len(build_files) >= 5:
        traits.append("monorepo_or_multi_package")
    if graph.get("indexing", {}).get("unsupported_language_areas"):
        traits.append("partial_language_coverage")
    return {
        "file_count": file_count,
        "languages": languages,
        "build_file_count": len(build_files),
        "traits": traits or ["standard_workspace"],
        "large_project_mode": bool(traits),
        "recommendations": _large_project_recommendations(traits, file_count, len(build_files)),
        "indexing": graph.get("indexing", {}),
    }


def _large_project_recommendations(traits: list[str], file_count: int, build_file_count: int) -> list[str]:
    recommendations = []
    if "large_project" in traits:
        recommendations.append("Use incremental indexing and dependency-scoped context before full-workspace prompts.")
    if "mixed_language_repo" in traits:
        recommendations.append("Filter architecture search by language and runtime boundary before applying changes.")
    if "large_cpp_ready" in traits:
        recommendations.append("Prefer build-system-aware validation and startup-project context for C++/Visual Studio workflows.")
    if "monorepo_or_multi_package" in traits:
        recommendations.append("Select package/service scope before feature or refactor workflows.")
    if not recommendations and file_count < 250 and build_file_count < 3:
        recommendations.append("Current workspace can use the standard fast scan and focused validation path.")
    return recommendations


def _engineering_recommendations(
    *,
    quality: dict[str, Any],
    validation: dict[str, Any],
    deployment: dict[str, Any],
    continuity: dict[str, Any],
    large_project: dict[str, Any],
    dogfood: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if quality.get("score", 100) < 75:
        recommendations.append(_recommendation("project_health", "Improve project health before broad feature work", "high", quality.get("recommended_next_improvement") or "Quality dashboard reports elevated project risk."))
    if validation.get("command_count", 0) == 0:
        recommendations.append(_recommendation("validation", "Create a validation baseline", "high", "No validation commands were detected, so safe apply and repair review cannot be proven."))
    if validation.get("validation_bottlenecks"):
        recommendations.append(_recommendation("validation", "Move slow validation behind fast checks", "medium", "Slow commands should run after syntax/type gates for faster feedback."))
    if continuity.get("interrupted_work"):
        recommendations.append(_recommendation("continuity", "Resume or close interrupted workflows", "medium", "Interrupted workflows should have a next action, rollback, or cancellation recorded."))
    if large_project.get("large_project_mode"):
        recommendations.append(_recommendation("large_project", "Use scoped architecture navigation", "medium", "Large or mixed repos should start from service/package scope, not full-workspace context."))
    deployment_risk = deployment.get("risk_summary", {}) if isinstance(deployment.get("risk_summary"), dict) else {}
    if deployment_risk.get("status") in {"warning", "blocked", "high"}:
        recommendations.append(_recommendation("deployment", "Review deployment readiness gates", "medium", "Deployment intelligence reports pipeline or environment risk."))
    friction = dogfood.get("friction", {}) if isinstance(dogfood.get("friction"), dict) else {}
    pain_points = friction.get("pain_points", []) if isinstance(friction.get("pain_points"), list) else []
    if pain_points:
        first = pain_points[0]
        recommendations.append(_recommendation("ergonomics", f"Reduce {first.get('label', 'workflow friction')}", "medium", first.get("recommendation", "Dogfooding reported repeated workflow friction.")))
    if not recommendations:
        recommendations.append(_recommendation("daily_workflow", "Keep engineering workflow focused", "low", "No major blocker was detected; continue collecting real workflow data."))
    return recommendations[:8]


def _architecture_focus(architecture: dict[str, Any]) -> dict[str, Any]:
    summary = architecture.get("summary", {}) if isinstance(architecture.get("summary"), dict) else {}
    return {
        "summary": summary,
        "entry_points": architecture.get("entry_points", []),
        "runtime_boundaries": architecture.get("runtime_boundaries", []),
        "build_systems": architecture.get("build_systems", []),
        "hotspots": architecture.get("hotspots", []),
        "risk_areas": architecture.get("risk_areas", []),
        "coding_conventions": architecture.get("coding_conventions", []),
        "indexing": architecture.get("indexing", {}),
    }


def _deployment_focus(deployment: dict[str, Any]) -> dict[str, Any]:
    return {
        "environment": deployment.get("environment", {}),
        "pipelines": deployment.get("pipelines", []),
        "readiness": deployment.get("readiness", deployment.get("deployment_readiness", {})),
        "risk_summary": deployment.get("risk_summary", {}),
        "rollback": deployment.get("rollback", deployment.get("rollback_strategy", {})),
        "release_history": deployment.get("release_history", []),
    }


def _search_modes() -> list[dict[str, str]]:
    return [
        {"id": "semantic", "label": "Semantic Code Search", "description": "Graph/lexical search with semantic retrieval extension point."},
        {"id": "dependency", "label": "Dependency-Aware Search", "description": "Search plus relationship traversal and impact context."},
        {"id": "architecture", "label": "Architecture-Aware Search", "description": "Search oriented around services, modules, entry points, and runtime boundaries."},
        {"id": "workflow", "label": "Workflow-Aware Search", "description": "Search that returns validation and workflow next actions."},
        {"id": "symbol", "label": "Symbol Relationship Exploration", "description": "Search symbols and inspect nearby graph relationships."},
    ]


def _normalize_search_mode(mode: str) -> str:
    value = str(mode or "architecture").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in {"semantic", "dependency", "architecture", "workflow", "symbol"} else "architecture"


def _search_mode_description(mode: str) -> str:
    return {item["id"]: item["description"] for item in _search_modes()}.get(mode, "Architecture-aware search.")


def _first_result_focus(search: dict[str, Any]) -> str:
    results = search.get("results", []) if isinstance(search.get("results"), list) else []
    for result in results:
        if isinstance(result, dict):
            return str(result.get("path") or result.get("label") or result.get("id") or "")
    return ""


def _search_next_actions(mode: str, search: dict[str, Any], relationships: dict[str, Any], impact: dict[str, Any] | None) -> list[str]:
    actions = []
    if not search.get("results"):
        actions.append("Broaden the query or scan the workspace before searching again.")
    if relationships.get("edges"):
        actions.append("Open relationship edges before editing shared files.")
    if impact and impact.get("modification_risk", {}).get("level") in {"medium", "high"}:
        actions.append("Run impact-targeted validation before applying changes.")
    if mode == "workflow":
        actions.append("Link the selected result to a workflow checkpoint and validation review.")
    if mode == "symbol":
        actions.append("Inspect callers, tests, and imports before refactoring the symbol.")
    return actions[:5] or ["Use the top result as focused context for the next engineering workflow."]


def _validation_prioritization(commands: list[dict[str, Any]], scan: dict[str, Any], slow_commands: list[Any]) -> list[dict[str, Any]]:
    slow_text = {str(item.get("command") if isinstance(item, dict) else item) for item in slow_commands}
    prioritized = []
    for command in commands:
        command_text = " ".join(str(part) for part in command.get("command", [])) if isinstance(command.get("command"), list) else str(command.get("command") or "")
        kind = str(command.get("kind") or command.get("name") or "validation")
        priority = 10
        if any(token in command_text.lower() for token in ["lint", "type", "tsc", "mypy", "pyright"]):
            priority -= 3
        if any(token in command_text.lower() for token in ["test", "pytest", "ctest"]):
            priority -= 1
        if command_text in slow_text:
            priority += 4
        prioritized.append({
            "command": command.get("command", []),
            "kind": kind,
            "priority": priority,
            "reason": "fast feedback first" if priority <= 8 else "run after focused checks",
        })
    prioritized.sort(key=lambda item: (item["priority"], " ".join(str(part) for part in item.get("command", []))))
    if not prioritized and scan.get("test_files"):
        prioritized.append({"command": [], "kind": "test", "priority": 99, "reason": "tests exist but no safe command was detected"})
    return prioritized


def _repair_explanations(current: dict[str, Any], latest: dict[str, Any] | None) -> list[dict[str, Any]]:
    explanations = []
    if current.get("repeated_repair_attempts", 0):
        explanations.append({
            "reason": "Repeated repair attempts detected",
            "next_action": "Prefer smallest failing test or build target before another repair loop.",
        })
    blockers = latest.get("blockers", []) if isinstance(latest, dict) and isinstance(latest.get("blockers"), list) else []
    for blocker in blockers[:5]:
        explanations.append({
            "reason": str(blocker.get("reason") or blocker.get("label") or "Quality gate blocked apply."),
            "next_action": "Resolve this blocker or request explicit approval before apply.",
        })
    return explanations


def _root_cause_candidates(current: dict[str, Any], blockers: list[dict[str, Any]], failing_systems: list[Any]) -> list[dict[str, Any]]:
    candidates = []
    for system in failing_systems[:5]:
        candidates.append({"source": "quality", "candidate": scrub(str(system)), "confidence": 0.7})
    for file in current.get("failing_files", []) if isinstance(current.get("failing_files"), list) else []:
        candidates.append({"source": "validation", "candidate": scrub(str(file)), "confidence": 0.75})
    for blocker in blockers[:5]:
        candidates.append({"source": "quality_gate", "candidate": scrub(str(blocker.get("reason") or blocker.get("label") or "")), "confidence": 0.65})
    return candidates[:10]


def _recommended_validation(commands: list[dict[str, Any]], blockers: list[dict[str, Any]], slow_commands: list[Any]) -> dict[str, Any]:
    if blockers:
        return {"strategy": "blocked_first", "reason": "Resolve blocking quality gates before broad validation.", "command": None}
    prioritized = _validation_prioritization(commands, {}, slow_commands)
    if prioritized and prioritized[0].get("command"):
        return {"strategy": "fast_first", "reason": prioritized[0]["reason"], "command": prioritized[0]["command"]}
    return {"strategy": "baseline_needed", "reason": "No validation command is available yet.", "command": None}


def _resume_candidates(workflows: dict[str, Any], interrupted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for event in interrupted:
        candidates.append({
            "workflow_id": event.get("workflow_id") or "",
            "event": event.get("event") or event.get("status") or "interrupted",
            "next_action": "Open workflow timeline, inspect latest blocker, then resume, rollback, or cancel.",
        })
    if not candidates and int(workflows.get("active_workflow_count") or 0):
        candidates.append({"workflow_id": "", "event": "active_workflow", "next_action": "Resume active workflow from the latest timeline event."})
    return candidates[:10]


def _roadmap_continuation_hint(quality: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    if validation.get("root_cause_candidates"):
        return {"status": "blocked_by_validation", "next_action": "Fix validation root cause before continuing roadmap phase."}
    if quality.get("recommended_next_improvement"):
        return {"status": "ready_with_quality_focus", "next_action": quality.get("recommended_next_improvement")}
    return {"status": "ready", "next_action": "Continue the next scoped roadmap item with checkpoint and validation."}


def _branch_awareness(quality: dict[str, Any]) -> dict[str, Any]:
    current = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), dict) else {}
    diff = current.get("large_risky_diff", {}) if isinstance(current.get("large_risky_diff"), dict) else {}
    return {
        "diff_detected": bool(diff.get("changed_files") or diff.get("file_count")),
        "changed_files": diff.get("changed_files", []),
        "recommendation": "Create or verify a checkpoint before continuing on this branch." if diff else "No branch-risk signal was detected in the quality snapshot.",
    }


def _state_files(root: Path) -> dict[str, str]:
    memory = ProjectMemory(root)
    return {
        "dashboard": str(memory.root / ENGINEERING_WORKSPACE_FILE),
        "summary": str(memory.root / ENGINEERING_WORKSPACE_SUMMARY),
    }


def _knowledge_graph_for_dashboard(root: Path, *, scan: dict[str, Any], persist: bool, refresh: bool) -> dict[str, Any]:
    try:
        return knowledge_graph(root, persist=persist, scan=scan, refresh=refresh)
    except Exception as exc:
        fallback = knowledge_graph(root, persist=False, scan=scan, refresh=False)
        warnings = fallback.setdefault("dashboard_warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"Knowledge graph persistence unavailable; using in-memory graph. {scrub(str(exc))}")
        fallback.setdefault("indexing", {})["persistence_degraded"] = True
        return fallback


def _quality_dashboard_for_dashboard(root: Path, *, scan: dict[str, Any], persist: bool) -> dict[str, Any]:
    try:
        return quality_dashboard(root, record_snapshot=persist, scan=scan)
    except Exception as exc:
        fallback = quality_dashboard(root, record_snapshot=False, scan=scan)
        warnings = fallback.setdefault("dashboard_warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"Quality history persistence unavailable; using in-memory snapshot. {scrub(str(exc))}")
        current = fallback.setdefault("current_snapshot", {})
        if isinstance(current, dict):
            current["persistence_degraded"] = True
        return fallback


def _summary_markdown(result: dict[str, Any]) -> str:
    lines = [
        "## Engineering Workspace Snapshot",
        "",
        f"- Project health: {result.get('dashboards', {}).get('project_health', {}).get('score', 'unknown')}",
        f"- Validation commands: {result.get('validation', {}).get('command_count', 0)}",
        f"- Large project mode: {result.get('large_project', {}).get('large_project_mode', False)}",
        f"- Active workflows: {result.get('continuity', {}).get('active_workflow_count', 0)}",
        "",
        "## Top Recommendations",
        "",
    ]
    for item in result.get("recommendations", [])[:8]:
        lines.append(f"- {item['priority']}: {item['title']} - {item['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def _recommendation(area: str, title: str, priority: str, reason: str) -> dict[str, str]:
    return {"area": area, "title": title, "priority": priority, "reason": scrub(str(reason))}


def _small_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(node.get("id") or ""),
        "type": str(node.get("type") or "unknown"),
        "label": str(node.get("label") or ""),
        "path": str(node.get("path") or ""),
    }


def _project_id(root: Path) -> str:
    return f"project-{abs(hash(str(root).lower())) % 10_000_000:07d}"


def _safe_call(label: str, func: Any, default: Any) -> Any:
    try:
        return func()
    except Exception as exc:  # pragma: no cover - keeps dashboard compositional.
        return {"error": f"{label} unavailable: {scrub(str(exc))}", **(default if isinstance(default, dict) else {})}
