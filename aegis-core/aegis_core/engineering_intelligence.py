from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .diagnostics import scrub
from .knowledge import architecture_summary, impact_analysis, knowledge_graph, knowledge_relationships, search_knowledge
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .quality_gates import quality_gate_dashboard
from .safety import is_safe_to_read
from .validation import validation_summary
from .workspace import WorkspaceScanner


INTELLIGENCE_FILE = "engineering-intelligence.json"
BENCHMARK_HISTORY_FILE = "engineering-intelligence-benchmarks.json"
CONTEXT_FILE = "engineering-context-assembly.json"
MAX_CONTEXT_FILES = 40
DEFAULT_TOKEN_BUDGET = 24000

WORKFLOW_PROFILES: dict[str, dict[str, Any]] = {
    "generate_feature": {
        "label": "Feature Implementation",
        "risk_bias": 0.18,
        "validation_depth": "targeted_then_build",
        "context_roles": ["direct_target", "dependency_neighbor", "api_boundary", "tests", "entry_point"],
    },
    "repair_project": {
        "label": "Repair",
        "risk_bias": 0.24,
        "validation_depth": "reproduce_then_targeted",
        "context_roles": ["failure_signal", "direct_target", "dependency_neighbor", "tests", "build_config"],
    },
    "validate_project": {
        "label": "Validation",
        "risk_bias": 0.08,
        "validation_depth": "validation_first",
        "context_roles": ["tests", "build_config", "direct_target", "entry_point"],
    },
    "continue_roadmap": {
        "label": "Roadmap Execution",
        "risk_bias": 0.2,
        "validation_depth": "milestone_validation",
        "context_roles": ["roadmap", "direct_target", "dependency_neighbor", "architecture_summary"],
    },
    "build_project": {
        "label": "Build",
        "risk_bias": 0.16,
        "validation_depth": "build_first",
        "context_roles": ["build_config", "direct_target", "dependency_neighbor", "tests"],
    },
    "deploy_staging": {
        "label": "Deployment Preparation",
        "risk_bias": 0.28,
        "validation_depth": "pipeline_and_rollback",
        "context_roles": ["deployment_config", "build_config", "tests", "architecture_summary"],
    },
    "deploy_production": {
        "label": "Production Deployment",
        "risk_bias": 0.45,
        "validation_depth": "full_gate_and_rollback",
        "context_roles": ["deployment_config", "build_config", "tests", "rollback_plan", "architecture_summary"],
    },
    "scan_workspace": {
        "label": "Workspace Intelligence",
        "risk_bias": 0.05,
        "validation_depth": "index_freshness",
        "context_roles": ["architecture_summary", "entry_point", "build_config", "readme"],
    },
}


def engineering_intelligence(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
    focus: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    latest_validation: Mapping[str, Any] | None = None,
    refresh: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    """Compose graph, memory, validation, repair, roadmap, and prediction signals.

    The result is deterministic and inspectable. It does not call models; it prepares better
    inputs and decision support for orchestration and clients.
    """

    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    clean_objective = scrub(objective).strip()
    normalized_targets, target_warnings = _normalize_target_files(root, target_files or [])
    focus_text = scrub(focus).strip() or (normalized_targets[0] if normalized_targets else clean_objective)
    budget = max(2000, min(240000, int(token_budget or DEFAULT_TOKEN_BUDGET)))

    scan = WorkspaceScanner(root).scan(persist=persist or refresh)
    graph = _safe_graph(root, scan=scan, persist=persist, refresh=refresh)
    architecture = _safe_call(lambda: architecture_summary(root, refresh=refresh), {})
    quality = _safe_call(lambda: quality_dashboard(root, scan=scan), {})
    gates = _safe_call(lambda: quality_gate_dashboard(root, limit=50), {})
    validation = _safe_call(lambda: validation_summary(root), {"commands": []})
    memory = _load_memory_sources(root)
    impacts = _impact_map(root, normalized_targets or _focus_candidates(focus_text), persist=persist)

    architecture_reasoning = _architecture_reasoning(
        root,
        scan=scan,
        graph=graph,
        architecture=architecture,
        impacts=impacts,
        focus=focus_text,
    )
    context = assemble_context(
        root,
        workflow_type=profile_id,
        objective=clean_objective,
        target_files=normalized_targets,
        focus=focus_text,
        token_budget=budget,
        scan=scan,
        graph=graph,
        impacts=impacts,
        memory=memory,
        persist=persist,
    )
    validation = validation_plan(
        root,
        workflow_type=profile_id,
        target_files=normalized_targets,
        objective=clean_objective,
        scan=scan,
        graph=graph,
        impacts=impacts,
        quality=quality,
        gates=gates,
        validation_summary_data=validation,
    )
    repair = repair_plan(
        root,
        workflow_type=profile_id,
        target_files=normalized_targets,
        objective=clean_objective,
        latest_validation=latest_validation,
        impacts=impacts,
        quality=quality,
        gates=gates,
        memory=memory,
    )
    roadmap = roadmap_plan(
        root,
        workflow_type=profile_id,
        objective=clean_objective,
        target_files=normalized_targets,
        architecture_reasoning=architecture_reasoning,
        validation=validation,
        repair=repair,
        impacts=impacts,
        memory=memory,
    )
    predictions = workflow_prediction(
        root,
        workflow_type=profile_id,
        target_files=normalized_targets,
        context=context,
        validation=validation,
        repair=repair,
        roadmap=roadmap,
        impacts=impacts,
        quality=quality,
        graph=graph,
    )
    memory_intelligence = _memory_intelligence(memory, workflow_type=profile_id, target_files=normalized_targets, objective=clean_objective)
    benchmarks = _benchmark_scores(
        architecture_reasoning=architecture_reasoning,
        context=context,
        validation=validation,
        repair=repair,
        roadmap=roadmap,
        predictions=predictions,
        memory=memory_intelligence,
    )
    explainability = _explainability(
        workflow_type=profile_id,
        objective=clean_objective,
        target_files=normalized_targets,
        architecture=architecture_reasoning,
        context=context,
        validation=validation,
        repair=repair,
        roadmap=roadmap,
        predictions=predictions,
    )
    result = {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": utc_now(),
        "workflow_type": profile_id,
        "workflow_profile": WORKFLOW_PROFILES[profile_id],
        "objective": clean_objective,
        "focus": focus_text,
        "target_files": normalized_targets,
        "warnings": target_warnings,
        "architecture_reasoning": architecture_reasoning,
        "context_assembly": context,
        "validation_intelligence": validation,
        "repair_intelligence": repair,
        "roadmap_intelligence": roadmap,
        "workflow_prediction": predictions,
        "knowledge_graph_intelligence": _knowledge_graph_intelligence(graph, impacts),
        "memory_intelligence": memory_intelligence,
        "benchmarks": benchmarks,
        "explainability": explainability,
        "state_files": {
            "dashboard": str(ProjectMemory(root).root / INTELLIGENCE_FILE),
            "context": str(ProjectMemory(root).root / CONTEXT_FILE),
            "benchmark_history": str(ProjectMemory(root).root / BENCHMARK_HISTORY_FILE),
        },
    }
    if persist:
        ProjectMemory(root).write_json(INTELLIGENCE_FILE, result)
    return result


def assemble_context(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
    focus: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    scan: Mapping[str, Any] | None = None,
    graph: Mapping[str, Any] | None = None,
    impacts: list[dict[str, Any]] | None = None,
    memory: Mapping[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    scan_data = dict(scan or WorkspaceScanner(root).scan(persist=False))
    graph_data = dict(graph or _safe_graph(root, scan=scan_data, persist=False, refresh=False))
    normalized_targets, warnings = _normalize_target_files(root, target_files or [])
    impact_data = impacts if impacts is not None else _impact_map(root, normalized_targets or _focus_candidates(focus), persist=False)
    memory_data = dict(memory or _load_memory_sources(root))
    budget = max(2000, min(240000, int(token_budget or DEFAULT_TOKEN_BUDGET)))

    candidates: dict[str, dict[str, Any]] = {}

    def add(path: str, score: int, reason: str, source: str, role: str) -> None:
        normalized = _normalize_relative_path(root, path)
        if not normalized:
            return
        existing = candidates.setdefault(
            normalized,
            {
                "path": normalized,
                "score": 0,
                "reasons": [],
                "sources": [],
                "roles": [],
                "estimated_chars": _estimated_chars(root, normalized),
            },
        )
        existing["score"] = max(int(existing.get("score") or 0), int(score))
        if reason and reason not in existing["reasons"]:
            existing["reasons"].append(scrub(reason))
        if source and source not in existing["sources"]:
            existing["sources"].append(source)
        if role and role not in existing["roles"]:
            existing["roles"].append(role)

    for path in normalized_targets:
        add(path, 100, "Direct target requested for this workflow.", "target_files", "direct_target")

    for impact in impact_data:
        target = str(impact.get("target") or "")
        if target:
            add(target, 95, "Impact-analysis focus target.", "impact_analysis", "direct_target")
        for path in impact.get("affected_files", []) if isinstance(impact.get("affected_files"), list) else []:
            add(str(path), 74, f"Dependency or relationship neighbor of {target}.", "impact_analysis", "dependency_neighbor")
        for item in impact.get("validation_targets", []) if isinstance(impact.get("validation_targets"), list) else []:
            if isinstance(item, Mapping) and item.get("path"):
                add(str(item["path"]), 68, str(item.get("reason") or "Validation target."), "impact_validation", "tests")

    for path in scan_data.get("entry_points", []) if isinstance(scan_data.get("entry_points"), list) else []:
        add(str(path), 62, "Entry point helps explain runtime flow.", "workspace_scan", "entry_point")
    for path in scan_data.get("test_files", []) if isinstance(scan_data.get("test_files"), list) else []:
        add(str(path), 54 if _related_to_targets(path, normalized_targets) else 34, "Test file informs validation scope.", "workspace_scan", "tests")
    for path in scan_data.get("build_files", []) if isinstance(scan_data.get("build_files"), list) else []:
        add(str(path), 52, "Build or dependency configuration affects validation reliability.", "workspace_scan", "build_config")
    for path in scan_data.get("readmes", []) if isinstance(scan_data.get("readmes"), list) else []:
        add(str(path), 30, "Project documentation can clarify intent and conventions.", "workspace_scan", "readme")

    objective_terms = _tokens(objective + " " + focus)
    if objective_terms:
        for node in graph_data.get("nodes", []) if isinstance(graph_data.get("nodes"), list) else []:
            if not isinstance(node, Mapping) or not node.get("path"):
                continue
            text = " ".join(str(node.get(key) or "") for key in ("label", "path", "type"))
            overlap = len(objective_terms.intersection(_tokens(text)))
            if overlap:
                add(str(node["path"]), min(70, 30 + overlap * 8), "Graph node text overlaps workflow objective.", "knowledge_graph", "semantic_match")

    for path in _memory_context_files(memory_data):
        add(path, 47, "Memory shows this file was relevant to previous workflows or repairs.", "memory", "memory_relevant")

    for candidate in candidates.values():
        candidate["score"] = _score_candidate(candidate, profile_id)
        candidate["preview"] = _preview_file(root, str(candidate["path"]), max_chars=900)

    ranked = sorted(candidates.values(), key=lambda item: (int(item.get("score") or 0), -int(item.get("estimated_chars") or 0), str(item.get("path") or "")), reverse=True)
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    used = 0
    for candidate in ranked[:MAX_CONTEXT_FILES * 3]:
        estimate = max(200, int(candidate.get("estimated_chars") or 0))
        if len(selected) < MAX_CONTEXT_FILES and used + estimate <= budget:
            selected.append(candidate)
            used += estimate
        else:
            excluded.append({**candidate, "excluded_reason": "context budget exhausted" if used + estimate > budget else "context file limit reached"})

    result = {
        "workspace": str(root),
        "workflow_type": profile_id,
        "token_budget": budget,
        "estimated_chars": used,
        "estimated_tokens": math.ceil(used / 4),
        "budget_used_percent": round((used / budget) * 100, 2) if budget else 0,
        "candidate_count": len(ranked),
        "selected_context": selected,
        "excluded_context": excluded[:50],
        "blocked_context": warnings,
        "context_groups": _context_groups(selected),
        "token_efficiency": _context_efficiency(selected, ranked, used),
        "assembly_strategy": {
            "profile": profile_id,
            "role_order": WORKFLOW_PROFILES[profile_id]["context_roles"],
            "principles": [
                "Prefer direct target files first.",
                "Add dependency neighbors from the knowledge graph.",
                "Reserve budget for validation/build/test context.",
                "Use memory only as a ranking signal, not as a substitute for current files.",
            ],
        },
    }
    if persist:
        ProjectMemory(root).write_json(CONTEXT_FILE, result)
    return result


def validation_plan(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    target_files: list[str] | None = None,
    objective: str = "",
    scan: Mapping[str, Any] | None = None,
    graph: Mapping[str, Any] | None = None,
    impacts: list[dict[str, Any]] | None = None,
    quality: Mapping[str, Any] | None = None,
    gates: Mapping[str, Any] | None = None,
    validation_summary_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    scan_data = dict(scan or WorkspaceScanner(root).scan(persist=False))
    graph_data = dict(graph or _safe_graph(root, scan=scan_data, persist=False, refresh=False))
    quality_data = dict(quality or _safe_call(lambda: quality_dashboard(root, scan=scan_data), {}))
    gate_data = dict(gates or _safe_call(lambda: quality_gate_dashboard(root, limit=50), {}))
    validation_data = dict(validation_summary_data or _safe_call(lambda: validation_summary(root), {"commands": []}))
    normalized_targets, _ = _normalize_target_files(root, target_files or [])
    impact_data = impacts if impacts is not None else _impact_map(root, normalized_targets or _focus_candidates(objective), persist=False)
    commands = _dedupe_commands([item for item in validation_data.get("commands", []) if isinstance(item, Mapping)])
    impact_targets = _impact_validation_targets(impact_data)
    prioritized = _prioritize_validations(profile_id, commands, impact_targets, scan_data, quality_data)
    flaky = _flaky_candidates(quality_data, gate_data)
    regression = _regression_prediction(profile_id, normalized_targets, impact_data, quality_data, graph_data)
    confidence = _validation_confidence(commands, prioritized, impact_data, flaky)
    return {
        "workspace": str(root),
        "workflow_type": profile_id,
        "strategy": WORKFLOW_PROFILES[profile_id]["validation_depth"],
        "detected_commands": commands,
        "impact_validation_targets": impact_targets,
        "prioritized_validations": prioritized,
        "validation_confidence": confidence,
        "regression_prediction": regression,
        "flaky_test_detection": {
            "candidates": flaky,
            "basis": "Slow commands, recurring failure memory, and recent quality-gate blockers.",
        },
        "escalation_rules": _validation_escalation_rules(profile_id, regression),
        "explanation": _validation_explanation(prioritized, regression, confidence),
    }


def repair_plan(
    workspace: str | Path,
    *,
    workflow_type: str = "repair_project",
    target_files: list[str] | None = None,
    objective: str = "",
    latest_validation: Mapping[str, Any] | None = None,
    impacts: list[dict[str, Any]] | None = None,
    quality: Mapping[str, Any] | None = None,
    gates: Mapping[str, Any] | None = None,
    memory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    normalized_targets, _ = _normalize_target_files(root, target_files or [])
    impact_data = impacts if impacts is not None else _impact_map(root, normalized_targets or _focus_candidates(objective), persist=False)
    quality_data = dict(quality or _safe_call(lambda: quality_dashboard(root), {}))
    gate_data = dict(gates or _safe_call(lambda: quality_gate_dashboard(root, limit=50), {}))
    memory_data = dict(memory or _load_memory_sources(root))
    validation_record = dict(latest_validation or _latest_quality_validation(gate_data) or {})
    root_causes = _root_cause_candidates(validation_record, impact_data, quality_data, gate_data)
    failed_patterns = _failed_repair_patterns(memory_data, validation_record, normalized_targets)
    rollback = _rollback_recommendation(profile_id, impact_data, failed_patterns, validation_record)
    strategies = _repair_strategies(profile_id, root_causes, impact_data, failed_patterns, rollback)
    confidence = _repair_confidence(root_causes, failed_patterns, impact_data, validation_record)
    return {
        "workspace": str(root),
        "workflow_type": profile_id,
        "latest_validation": _compact_validation(validation_record),
        "root_cause_candidates": root_causes,
        "strategy_selection": strategies,
        "failed_repair_detection": failed_patterns,
        "architecture_aware_scope": _repair_scope(impact_data, normalized_targets),
        "rollback_recommendation": rollback,
        "repair_confidence": confidence,
        "stopping_conditions": [
            "Escalate after repeated root-cause signatures.",
            "Escalate when the repair scope expands beyond impacted files.",
            "Recommend rollback when validation failures persist after bounded repairs.",
        ],
        "explanation": _repair_explanation(root_causes, strategies, rollback),
    }


def roadmap_plan(
    workspace: str | Path,
    *,
    workflow_type: str = "continue_roadmap",
    objective: str = "",
    target_files: list[str] | None = None,
    architecture_reasoning: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
    repair: Mapping[str, Any] | None = None,
    impacts: list[dict[str, Any]] | None = None,
    memory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    normalized_targets, _ = _normalize_target_files(root, target_files or [])
    impact_data = impacts if impacts is not None else _impact_map(root, normalized_targets or _focus_candidates(objective), persist=False)
    arch = dict(architecture_reasoning or {})
    validation_data = dict(validation or {})
    repair_data = dict(repair or {})
    memory_data = dict(memory or _load_memory_sources(root))
    phases = _roadmap_phases(profile_id, objective, normalized_targets, impact_data, validation_data, repair_data)
    ordering = _execution_ordering(phases, impact_data, arch)
    return {
        "workspace": str(root),
        "workflow_type": profile_id,
        "task_decomposition": phases,
        "dependency_planning": {
            "execution_order": ordering,
            "blocked_by": _roadmap_blockers(impact_data, validation_data, repair_data),
            "parallel_safe_groups": _parallel_safe_groups(phases, impact_data),
        },
        "milestone_prediction": _milestone_prediction(phases, validation_data, impact_data),
        "risk_estimation": _roadmap_risk(phases, impact_data, validation_data),
        "architecture_aware_planning": {
            "runtime_boundaries": arch.get("runtime_boundaries", []),
            "service_interactions": arch.get("service_interactions", [])[:10],
            "impact_hotspots": arch.get("impact_hotspots", [])[:10],
        },
        "memory_guidance": _roadmap_memory_guidance(memory_data),
        "explanation": _roadmap_explanation(phases, ordering),
    }


def workflow_prediction(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    target_files: list[str] | None = None,
    context: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
    repair: Mapping[str, Any] | None = None,
    roadmap: Mapping[str, Any] | None = None,
    impacts: list[dict[str, Any]] | None = None,
    quality: Mapping[str, Any] | None = None,
    graph: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    profile_id = _workflow_profile(workflow_type)
    normalized_targets, _ = _normalize_target_files(root, target_files or [])
    context_data = dict(context or {})
    validation_data = dict(validation or {})
    repair_data = dict(repair or {})
    roadmap_data = dict(roadmap or {})
    quality_data = dict(quality or {})
    graph_data = dict(graph or {})
    impact_data = impacts or []
    risk_score = _execution_risk_score(profile_id, normalized_targets, impact_data, quality_data, validation_data)
    likely_failures = _likely_failures(profile_id, normalized_targets, impact_data, validation_data, quality_data)
    validation_scope = _validation_scope(validation_data, impact_data)
    rollback_probability = min(0.95, round(risk_score * 0.62 + len(repair_data.get("failed_repair_detection", {}).get("patterns", [])) * 0.08, 3))
    deployment_risk = _deployment_risk(profile_id, normalized_targets, impact_data)
    duration = _duration_estimate(profile_id, normalized_targets, context_data, validation_data, roadmap_data, graph_data, risk_score)
    return {
        "workspace": str(root),
        "workflow_type": profile_id,
        "execution_risk": {"score": risk_score, "level": _risk_level(risk_score), "reasons": _risk_reasons(profile_id, normalized_targets, impact_data, quality_data)},
        "likely_failures": likely_failures,
        "validation_scope": validation_scope,
        "rollback_probability": rollback_probability,
        "deployment_risk": deployment_risk,
        "duration_estimate": duration,
        "execution_reliability": _execution_reliability(risk_score, validation_data, repair_data, context_data),
        "prediction_confidence": _prediction_confidence(context_data, validation_data, impact_data, graph_data),
    }


def run_benchmarks(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    intelligence = engineering_intelligence(
        root,
        workflow_type=workflow_type,
        objective=objective,
        target_files=target_files or [],
        persist=persist,
    )
    run = {
        "id": f"eng-intel-bench-{uuid.uuid4().hex[:12]}",
        "workspace": str(root),
        "workflow_type": intelligence["workflow_type"],
        "created_at": utc_now(),
        "scores": intelligence["benchmarks"]["scores"],
        "summary": intelligence["benchmarks"]["summary"],
        "inputs": {
            "objective": scrub(objective),
            "target_files": intelligence.get("target_files", []),
        },
    }
    history = _benchmark_history(root)
    history.append(run)
    history = history[-200:]
    if persist:
        ProjectMemory(root).write_json(BENCHMARK_HISTORY_FILE, history)
    return {
        "workspace": str(root),
        "benchmark_run": run,
        "history": list(reversed(history[-50:])),
        "benchmark_suites": _benchmark_suites(),
    }


def benchmark_dashboard(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    history = _benchmark_history(root)
    return {
        "workspace": str(root),
        "history": list(reversed(history[-max(1, min(200, int(limit))):])),
        "benchmark_suites": _benchmark_suites(),
        "trends": _benchmark_trends(history),
        "path": str(ProjectMemory(root).root / BENCHMARK_HISTORY_FILE),
    }


def _architecture_reasoning(
    root: Path,
    *,
    scan: Mapping[str, Any],
    graph: Mapping[str, Any],
    architecture: Mapping[str, Any],
    impacts: list[dict[str, Any]],
    focus: str,
) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, Mapping)]
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    relationship_counts = Counter(str(edge.get("type") or "unknown") for edge in edges)
    runtime_boundaries = [_small_node(node) for node in nodes if node.get("type") == "runtime_boundary"][:20]
    api_nodes = [_small_node(node) for node in nodes if node.get("type") == "api"][:50]
    service_nodes = [_small_node(node) for node in nodes if node.get("type") in {"service", "module", "ui_component"}][:50]
    service_edges = [
        _edge_summary(edge, node_by_id)
        for edge in edges
        if edge.get("type") in {"depends_on", "uses", "calls", "api_consumer", "route_binding"}
    ][:80]
    impact_hotspots = _impact_hotspots(impacts)
    confidence = _architecture_confidence(nodes, edges, graph)
    focus_relationships = _safe_call(
        lambda: knowledge_relationships(root, focus, depth=2, limit=30, persist=True),
        {"focus_node": None, "edges": [], "nodes": []},
    ) if focus else {"focus_node": None, "edges": [], "nodes": []}
    return {
        "workspace": str(root),
        "confidence": confidence,
        "frameworks": scan.get("frameworks", []),
        "runtime_boundaries": runtime_boundaries,
        "api_relationships": {
            "api_count": len(api_nodes),
            "apis": api_nodes[:20],
            "consumer_edges": [item for item in service_edges if item.get("type") in {"api_consumer", "route_binding"}][:25],
        },
        "service_interactions": service_edges[:50],
        "dependency_understanding": {
            "relationship_counts": dict(relationship_counts),
            "clusters": graph.get("clusters", [])[:20] if isinstance(graph.get("clusters"), list) else [],
            "unstable_modules": graph.get("unstable_modules", [])[:15] if isinstance(graph.get("unstable_modules"), list) else [],
            "hotspots": graph.get("architecture_hotspots", [])[:15] if isinstance(graph.get("architecture_hotspots"), list) else [],
        },
        "project_wide_impact": {
            "affected_files": sorted({path for impact in impacts for path in impact.get("affected_files", [])})[:100],
            "likely_breakage_areas": _merge_weighted(impact.get("likely_breakage_areas", []) for impact in impacts),
            "impact_hotspots": impact_hotspots,
        },
        "focus_relationships": {
            "focus_node": focus_relationships.get("focus_node"),
            "relationship_types": focus_relationships.get("relationships", []),
            "related_node_count": len(focus_relationships.get("nodes", []) if isinstance(focus_relationships.get("nodes"), list) else []),
            "edge_count": len(focus_relationships.get("edges", []) if isinstance(focus_relationships.get("edges"), list) else []),
        },
        "architecture_summary": architecture.get("summary", architecture),
        "reasoning_path": [
            "Read workspace scan for language/framework/build boundaries.",
            "Used knowledge graph nodes and edges for dependency/API/service relationships.",
            "Ran impact analysis around requested target files or focus.",
            "Ranked validation and repair scope from affected files and recurring risk signals.",
        ],
    }


def _knowledge_graph_intelligence(graph: Mapping[str, Any], impacts: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, Mapping)]
    indexing = graph.get("indexing", {}) if isinstance(graph.get("indexing"), Mapping) else {}
    stale = graph.get("incremental", {}) if isinstance(graph.get("incremental"), Mapping) else {}
    return {
        "graph_version": graph.get("version", ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "relationship_quality": _relationship_quality(nodes, edges, indexing),
        "stale_node_cleanup": {
            "removed_files": stale.get("removed_files", []),
            "invalidated_nodes": stale.get("invalidated_nodes", []),
            "partial_update": bool(stale.get("partial_update")),
        },
        "architecture_summarization": graph.get("architecture_summary", {}),
        "impact_prediction": {
            "target_count": len(impacts),
            "affected_file_count": len({path for impact in impacts for path in impact.get("affected_files", [])}),
            "highest_risk": max([float(impact.get("modification_risk", {}).get("score") or 0) for impact in impacts] or [0]),
        },
        "semantic_retrieval": graph.get("embedding_interfaces", {"enabled": False, "current_retrieval": "keyword_graph"}),
    }


def _memory_intelligence(memory: Mapping[str, Any], *, workflow_type: str, target_files: list[str], objective: str) -> dict[str, Any]:
    entries = _memory_entries(memory)
    relevant = []
    terms = _tokens(objective + " " + " ".join(target_files) + " " + workflow_type)
    for entry in entries:
        text = json.dumps(entry, sort_keys=True, default=str)
        score = len(terms.intersection(_tokens(text))) if terms else 0
        if score or any(str(path) in text for path in target_files):
            relevant.append({"score": score, "entry": _shrink(entry)})
    relevant.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    stale = [item for item in entries if _looks_stale(item)][:20]
    conflicts = _memory_conflicts(entries)
    return {
        "relevant_memories": relevant[:20],
        "stale_memory_candidates": [_shrink(item) for item in stale],
        "conflicting_memories": conflicts,
        "workflow_specific_retrieval": {
            "workflow_type": workflow_type,
            "target_files": target_files,
            "retrieval_terms": sorted(terms)[:30],
        },
        "repair_pattern_memory": _repair_memory(memory),
        "architecture_memory": _architecture_memory(memory),
        "quality": {
            "entry_count": len(entries),
            "relevant_count": len(relevant),
            "stale_count": len(stale),
            "conflict_count": len(conflicts),
        },
    }


def _benchmark_scores(
    *,
    architecture_reasoning: Mapping[str, Any],
    context: Mapping[str, Any],
    validation: Mapping[str, Any],
    repair: Mapping[str, Any],
    roadmap: Mapping[str, Any],
    predictions: Mapping[str, Any],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    scores = {
        "feature_quality": _avg(
            architecture_reasoning.get("confidence", {}).get("score", 0),
            context.get("token_efficiency", {}).get("relevance_score", 0),
            validation.get("validation_confidence", {}).get("score", 0),
        ),
        "repair_quality": _avg(
            repair.get("repair_confidence", {}).get("score", 0),
            80 if repair.get("root_cause_candidates") else 40,
            75 if repair.get("rollback_recommendation", {}).get("available") else 55,
        ),
        "validation_accuracy": _avg(
            validation.get("validation_confidence", {}).get("score", 0),
            85 if validation.get("prioritized_validations") else 35,
            75 if validation.get("impact_validation_targets") else 45,
        ),
        "roadmap_quality": _avg(
            85 if roadmap.get("task_decomposition") else 30,
            80 if roadmap.get("dependency_planning", {}).get("execution_order") else 35,
            max(20, 100 - int(roadmap.get("risk_estimation", {}).get("score", 0) * 100)),
        ),
        "orchestration_efficiency": _avg(
            context.get("token_efficiency", {}).get("budget_score", 0),
            predictions.get("execution_reliability", {}).get("score", 0),
            85 if context.get("selected_context") else 30,
        ),
        "rollback_reduction": _avg(
            90 if repair.get("rollback_recommendation", {}).get("available") else 40,
            max(15, 100 - int(float(predictions.get("rollback_probability", 0)) * 100)),
            75 if validation.get("escalation_rules") else 50,
        ),
        "execution_reliability": predictions.get("execution_reliability", {}).get("score", 0),
        "memory_relevance": min(100, 40 + len(memory.get("relevant_memories", [])) * 8 - len(memory.get("stale_memory_candidates", [])) * 2),
    }
    return {
        "scores": {key: int(max(0, min(100, value))) for key, value in scores.items()},
        "summary": _benchmark_summary(scores),
        "suites": _benchmark_suites(),
    }


def _explainability(
    *,
    workflow_type: str,
    objective: str,
    target_files: list[str],
    architecture: Mapping[str, Any],
    context: Mapping[str, Any],
    validation: Mapping[str, Any],
    repair: Mapping[str, Any],
    roadmap: Mapping[str, Any],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    decisions = [
        {
            "decision": "workflow_profile_selected",
            "reason": f"Using {WORKFLOW_PROFILES[workflow_type]['label']} rules for context, validation, repair, and risk.",
            "evidence": {"workflow_type": workflow_type, "objective": objective},
        },
        {
            "decision": "architecture_scope_ranked",
            "reason": "Dependency, API, runtime-boundary, and service edges were used to determine impact.",
            "evidence": {
                "confidence": architecture.get("confidence", {}),
                "affected_files": architecture.get("project_wide_impact", {}).get("affected_files", [])[:10],
            },
        },
        {
            "decision": "context_budget_allocated",
            "reason": "Context was ranked by direct targets, graph neighbors, validation files, build files, and memory relevance.",
            "evidence": {
                "selected": len(context.get("selected_context", []) if isinstance(context.get("selected_context"), list) else []),
                "budget_used_percent": context.get("budget_used_percent"),
            },
        },
        {
            "decision": "validation_strategy_selected",
            "reason": validation.get("explanation", "Validation strategy was selected from detected commands and impact targets."),
            "evidence": {"prioritized_count": len(validation.get("prioritized_validations", []) if isinstance(validation.get("prioritized_validations"), list) else [])},
        },
        {
            "decision": "repair_strategy_selected",
            "reason": repair.get("explanation", "Repair strategy was selected from root-cause and repair-history signals."),
            "evidence": {"root_cause_count": len(repair.get("root_cause_candidates", []) if isinstance(repair.get("root_cause_candidates"), list) else [])},
        },
        {
            "decision": "execution_prediction_created",
            "reason": "Workflow prediction combines impact size, validation coverage, repair history, and quality signals.",
            "evidence": predictions.get("execution_risk", {}),
        },
    ]
    return {
        "reasoning_path": [item["decision"] for item in decisions],
        "decisions": decisions,
        "user_visible_summary": _user_visible_summary(workflow_type, target_files, predictions, validation, repair),
    }


def _workspace_root(workspace: str | Path) -> Path:
    return Path(workspace).resolve()


def _workflow_profile(workflow_type: str) -> str:
    clean = str(workflow_type or "generate_feature").strip().lower()
    aliases = {
        "feature": "generate_feature",
        "bug_fix": "repair_project",
        "repair": "repair_project",
        "refactor": "generate_feature",
        "roadmap": "continue_roadmap",
        "deployment": "deploy_staging",
        "scan": "scan_workspace",
    }
    clean = aliases.get(clean, clean)
    return clean if clean in WORKFLOW_PROFILES else "generate_feature"


def _safe_graph(root: Path, *, scan: Mapping[str, Any], persist: bool, refresh: bool) -> dict[str, Any]:
    try:
        return knowledge_graph(root, scan=dict(scan), persist=persist, refresh=refresh)
    except Exception as exc:
        return {"workspace": str(root), "nodes": [], "edges": [], "warnings": [f"knowledge graph unavailable: {scrub(str(exc))}"]}


def _safe_call(callback: Any, default: Any) -> Any:
    try:
        return callback()
    except Exception:
        return default


def _normalize_target_files(root: Path, paths: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    normalized: list[str] = []
    warnings: list[dict[str, str]] = []
    for item in paths:
        relative = _normalize_relative_path(root, str(item))
        if not relative:
            warnings.append({"path": scrub(str(item)), "reason": "outside workspace or invalid path"})
            continue
        if relative not in normalized:
            normalized.append(relative)
    return normalized[:100], warnings


def _normalize_relative_path(root: Path, path: str) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    try:
        candidate = Path(raw)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / raw).resolve()
        resolved.relative_to(root)
        return resolved.relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return ""


def _focus_candidates(focus: str) -> list[str]:
    text = str(focus or "").strip()
    if not text:
        return []
    matches = re.findall(r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|cs|cpp|c|h|hpp|json|ya?ml|md)", text)
    return matches[:10] or [text]


def _impact_map(root: Path, targets: list[str], *, persist: bool) -> list[dict[str, Any]]:
    impacts = []
    for target in targets[:20]:
        try:
            impacts.append(impact_analysis(root, target, limit=120, persist=persist))
        except Exception as exc:
            impacts.append({"target": scrub(target), "affected_files": [scrub(target)], "validation_targets": [], "error": scrub(str(exc)), "modification_risk": {"level": "unknown", "score": 0.5, "reasons": ["impact analysis unavailable"]}})
    return impacts


def _load_memory_sources(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    sources: dict[str, Any] = {}
    for name in ("engineering-memory.json", "autopilot-memory.json", "project-memory.json", "personal-memory.json", "quality-history.json"):
        path = memory.root / name
        if not path.is_file():
            continue
        try:
            sources[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            sources[name] = {"unavailable": True}
    return sources


def _estimated_chars(root: Path, relative: str) -> int:
    try:
        path = (root / relative).resolve()
        path.relative_to(root)
        if path.is_file():
            return min(120000, max(200, int(path.stat().st_size)))
    except (OSError, RuntimeError, ValueError):
        pass
    return 1600


def _preview_file(root: Path, relative: str, *, max_chars: int) -> str:
    try:
        path = (root / relative).resolve()
        path.relative_to(root)
        if not path.is_file() or not is_safe_to_read(path, root):
            return ""
        return scrub(path.read_text(encoding="utf-8", errors="replace")[:max_chars])
    except (OSError, UnicodeDecodeError, RuntimeError, ValueError):
        return ""


def _score_candidate(candidate: Mapping[str, Any], workflow_type: str) -> int:
    score = int(candidate.get("score") or 0)
    preferred = set(WORKFLOW_PROFILES[workflow_type]["context_roles"])
    roles = set(str(item) for item in candidate.get("roles", []) if str(item))
    score += min(16, len(roles & preferred) * 4)
    if "direct_target" in roles:
        score += 12
    if "tests" in roles and workflow_type in {"repair_project", "validate_project", "build_project"}:
        score += 10
    if "build_config" in roles and workflow_type in {"build_project", "deploy_staging", "deploy_production"}:
        score += 10
    estimate = int(candidate.get("estimated_chars") or 0)
    if estimate > 40000:
        score -= 10
    return max(0, min(130, score))


def _related_to_targets(path: Any, targets: list[str]) -> bool:
    raw = str(path).lower().replace("\\", "/")
    names = {Path(target).stem.lower() for target in targets}
    return any(name and name in raw for name in names)


def _tokens(text: str) -> set[str]:
    return {item.lower() for item in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", str(text)) if item.lower() not in {"the", "and", "for", "with", "from", "this", "that"}}


def _memory_context_files(memory: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for entry in _memory_entries(memory):
        if isinstance(entry, Mapping):
            for key in ("path", "file", "target_file"):
                value = entry.get(key)
                if isinstance(value, str):
                    paths.append(value)
            for key in ("target_files", "files", "changed_files"):
                values = entry.get(key)
                if isinstance(values, list):
                    paths.extend(str(item) for item in values if isinstance(item, str))
    return _dedupe(paths)[:40]


def _memory_entries(memory: Mapping[str, Any]) -> list[Any]:
    entries: list[Any] = []
    for value in memory.values():
        if isinstance(value, Mapping):
            for nested in value.values():
                if isinstance(nested, list):
                    entries.extend(nested)
                elif isinstance(nested, Mapping):
                    entries.append(nested)
        elif isinstance(value, list):
            entries.extend(value)
    return entries


def _context_groups(selected: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for item in selected:
        for role in item.get("roles", []) if isinstance(item.get("roles"), list) else []:
            groups[str(role)].append(str(item.get("path") or ""))
    return {key: _dedupe(value)[:20] for key, value in sorted(groups.items())}


def _context_efficiency(selected: list[dict[str, Any]], ranked: list[dict[str, Any]], used: int) -> dict[str, Any]:
    if not ranked:
        return {"relevance_score": 0, "budget_score": 100, "selected_ratio": 0}
    avg_score = sum(int(item.get("score") or 0) for item in selected) / max(1, len(selected))
    top_possible = sum(int(item.get("score") or 0) for item in ranked[: max(1, len(selected))]) / max(1, len(selected))
    relevance = int(100 * (avg_score / max(1, top_possible)))
    budget_score = int(max(10, min(100, 100 - max(0, used - DEFAULT_TOKEN_BUDGET) / 1000)))
    return {
        "relevance_score": max(0, min(100, relevance)),
        "budget_score": budget_score,
        "selected_ratio": round(len(selected) / max(1, len(ranked)), 3),
    }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _small_node(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(node.get("id") or ""),
        "type": str(node.get("type") or ""),
        "label": str(node.get("label") or ""),
        "path": str(node.get("path") or ""),
    }


def _edge_summary(edge: Mapping[str, Any], node_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    source = node_by_id.get(str(edge.get("source") or ""), {})
    target = node_by_id.get(str(edge.get("target") or ""), {})
    return {
        "type": str(edge.get("type") or ""),
        "source": _small_node(source) if source else {"id": str(edge.get("source") or "")},
        "target": _small_node(target) if target else {"id": str(edge.get("target") or "")},
        "evidence": scrub(str(edge.get("evidence") or ""))[:300],
    }


def _architecture_confidence(nodes: list[Mapping[str, Any]], edges: list[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    failures = graph.get("analyzers", {}).get("failures", []) if isinstance(graph.get("analyzers"), Mapping) else []
    score = 20
    if nodes:
        score += 25
    if edges:
        score += 25
    if any(node.get("type") == "api" for node in nodes):
        score += 10
    if any(node.get("type") == "runtime_boundary" for node in nodes):
        score += 10
    score -= min(25, len(failures) * 5)
    score = max(0, min(100, score))
    return {
        "score": score,
        "level": "low" if score < 45 else "medium" if score < 75 else "high",
        "basis": {"nodes": len(nodes), "edges": len(edges), "indexing_failures": len(failures)},
    }


def _impact_hotspots(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for impact in impacts:
        for path in impact.get("affected_files", []) if isinstance(impact.get("affected_files"), list) else []:
            counts[str(path)] += 1
    return [{"path": path, "weight": weight} for path, weight in counts.most_common(20)]


def _merge_weighted(groups: Any) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for group in groups:
        for item in group if isinstance(group, list) else []:
            if isinstance(item, Mapping):
                label = str(item.get("area") or item.get("path") or item.get("label") or "")
                if label:
                    counts[label] += int(item.get("weight") or 1)
    return [{"area": area, "weight": weight} for area, weight in counts.most_common(20)]


def _dedupe_commands(commands: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in commands:
        command = item.get("command")
        key = json.dumps(command, sort_keys=True) if isinstance(command, list) else str(command)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({"name": scrub(str(item.get("name") or key)), "command": command, "reason": scrub(str(item.get("reason") or ""))})
    return result


def _impact_validation_targets(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for impact in impacts:
        for target in impact.get("validation_targets", []) if isinstance(impact.get("validation_targets"), list) else []:
            if not isinstance(target, Mapping):
                continue
            key = json.dumps(target, sort_keys=True, default=str)
            if key not in seen:
                targets.append(dict(target))
                seen.add(key)
    return targets[:30]


def _prioritize_validations(
    workflow_type: str,
    commands: list[dict[str, Any]],
    impact_targets: list[dict[str, Any]],
    scan: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for target in impact_targets:
        command = target.get("command")
        priority = 95 if command else 75
        items.append({"priority": priority, "kind": target.get("kind", "impact"), "command": command, "reason": target.get("reason", "Impact-based validation target."), "source": "impact_analysis"})
    for command in commands:
        text = " ".join(str(part) for part in command.get("command", []) if part)
        lowered = text.lower()
        priority = 55
        if workflow_type in {"build_project", "deploy_staging", "deploy_production"} and any(term in lowered for term in ("build", "dotnet", "cmake", "cargo")):
            priority = 92
        elif workflow_type in {"repair_project", "generate_feature"} and any(term in lowered for term in ("test", "pytest", "vitest")):
            priority = 88
        elif "lint" in lowered or "type" in lowered:
            priority = 70
        items.append({"priority": priority, "kind": "detected_command", "command": command.get("command"), "reason": command.get("reason", ""), "source": "validation_detection", "name": command.get("name")})
    for risk in quality.get("top_risks", []) if isinstance(quality.get("top_risks"), list) else []:
        if isinstance(risk, Mapping) and risk.get("validation"):
            items.append({"priority": 82, "kind": "quality_risk", "reason": scrub(str(risk.get("summary") or risk.get("label") or risk)), "source": "quality_dashboard"})
    items.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    return items[:20]


def _flaky_candidates(quality: Mapping[str, Any], gates: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    snapshot = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), Mapping) else {}
    for item in snapshot.get("slow_validation_commands", []) if isinstance(snapshot.get("slow_validation_commands"), list) else []:
        if isinstance(item, Mapping):
            candidates.append({"source": "slow_validation", "confidence": "medium", **dict(item)})
    for run in gates.get("recent_runs", []) if isinstance(gates.get("recent_runs"), list) else []:
        if isinstance(run, Mapping) and run.get("status") in {"blocked", "warning"}:
            for blocker in run.get("blockers", []) if isinstance(run.get("blockers"), list) else []:
                candidates.append({"source": "quality_gate_blocker", "confidence": "medium", "blocker": blocker})
    return candidates[:20]


def _regression_prediction(workflow_type: str, targets: list[str], impacts: list[dict[str, Any]], quality: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    impacted = {path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)}
    risk = WORKFLOW_PROFILES[workflow_type]["risk_bias"] + len(impacted) * 0.025 + len(targets) * 0.035
    if any(Path(path).name in {"package.json", "pyproject.toml", "CMakeLists.txt"} for path in targets):
        risk += 0.18
    if quality.get("grade") in {"D", "F"}:
        risk += 0.15
    if graph.get("analyzers", {}).get("failures") if isinstance(graph.get("analyzers"), Mapping) else False:
        risk += 0.08
    risk = round(min(0.98, max(0.02, risk)), 3)
    return {
        "score": risk,
        "level": _risk_level(risk),
        "affected_file_count": len(impacted),
        "reasons": _risk_reasons(workflow_type, targets, impacts, quality),
    }


def _validation_confidence(commands: list[dict[str, Any]], prioritized: list[dict[str, Any]], impacts: list[dict[str, Any]], flaky: list[dict[str, Any]]) -> dict[str, Any]:
    score = 25
    score += min(25, len(commands) * 8)
    score += min(25, len(prioritized) * 5)
    score += 15 if any(impact.get("validation_targets") for impact in impacts) else 0
    score -= min(20, len(flaky) * 4)
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _validation_escalation_rules(workflow_type: str, regression: Mapping[str, Any]) -> list[dict[str, Any]]:
    rules = [
        {"when": "targeted_validation_fails", "then": "rerun the failing check after a root-cause repair"},
        {"when": "second_repair_fails", "then": "broaden validation and ask for user review"},
    ]
    if regression.get("level") in {"high", "critical"}:
        rules.append({"when": "high_regression_risk", "then": "require build/test gate and checkpoint before apply"})
    if workflow_type.startswith("deploy_"):
        rules.append({"when": "deployment_workflow", "then": "require pipeline dry-run and rollback readiness"})
    return rules


def _validation_explanation(prioritized: list[dict[str, Any]], regression: Mapping[str, Any], confidence: Mapping[str, Any]) -> str:
    if not prioritized:
        return "No validation command was detected; ask the user for a validation command before applying changes."
    return f"Validation prioritizes {prioritized[0].get('kind')} first because regression risk is {regression.get('level')} and confidence is {confidence.get('level')}."


def _latest_quality_validation(gates: Mapping[str, Any]) -> Mapping[str, Any] | None:
    latest = gates.get("latest") if isinstance(gates.get("latest"), Mapping) else None
    if latest and isinstance(latest.get("validation"), Mapping):
        return latest["validation"]
    return None


def _root_cause_candidates(validation: Mapping[str, Any], impacts: list[dict[str, Any]], quality: Mapping[str, Any], gates: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    diagnostic = " ".join(str(validation.get(key) or "") for key in ("stderr", "stderr_excerpt", "stdout", "summary", "reason"))
    if diagnostic.strip():
        candidates.extend(_diagnostic_root_causes(diagnostic))
    for impact in impacts:
        for area in impact.get("likely_breakage_areas", []) if isinstance(impact.get("likely_breakage_areas"), list) else []:
            if isinstance(area, Mapping):
                candidates.append({"confidence": 62, "source": "impact_analysis", "cause": f"Breakage may sit near {area.get('area')}.", "evidence": dict(area)})
    for system in quality.get("failing_systems", []) if isinstance(quality.get("failing_systems"), list) else []:
        candidates.append({"confidence": 58, "source": "quality_dashboard", "cause": f"Quality dashboard reports failing system: {system}.", "evidence": {"system": system}})
    latest = gates.get("latest") if isinstance(gates.get("latest"), Mapping) else {}
    for blocker in latest.get("blockers", []) if isinstance(latest.get("blockers"), list) else []:
        candidates.append({"confidence": 66, "source": "quality_gate", "cause": scrub(str(blocker.get("reason") if isinstance(blocker, Mapping) else blocker)), "evidence": blocker})
    candidates.sort(key=lambda item: int(item.get("confidence") or 0), reverse=True)
    return candidates[:12]


def _diagnostic_root_causes(text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    patterns = [
        ("import_or_module_resolution", ("modulenotfound", "importerror", "cannot find module", "missing module"), 84),
        ("type_or_contract_mismatch", ("typeerror", "argument", "property", "attributeerror"), 78),
        ("syntax_or_parse_error", ("syntaxerror", "parse", "unexpected token"), 82),
        ("assertion_failure", ("assert", "expected", "received", "failed"), 70),
        ("build_configuration", ("msbuild", "cmake", "link", "compiler", "tsc"), 72),
        ("timeout_or_flaky_runtime", ("timeout", "timed out", "flaky"), 68),
    ]
    results = []
    for cause, terms, confidence in patterns:
        if any(term in lowered for term in terms):
            results.append({"confidence": confidence, "source": "validation_diagnostic", "cause": cause, "evidence": scrub(text[:700])})
    if not results and text.strip():
        results.append({"confidence": 45, "source": "validation_diagnostic", "cause": "unclassified_validation_failure", "evidence": scrub(text[:700])})
    return results


def _failed_repair_patterns(memory: Mapping[str, Any], validation: Mapping[str, Any], targets: list[str]) -> dict[str, Any]:
    patterns: Counter[str] = Counter()
    target_hits = 0
    validation_terms = _tokens(json.dumps(validation, sort_keys=True, default=str))
    for entry in _memory_entries(memory):
        if not isinstance(entry, Mapping):
            continue
        text = json.dumps(entry, sort_keys=True, default=str).lower()
        if "success" in entry and entry.get("success") is False:
            signature = str(entry.get("root_cause") or entry.get("summary") or "failed_repair")[:120]
            patterns[signature] += 1
        if any(str(target).lower() in text for target in targets):
            target_hits += 1
        elif validation_terms and validation_terms.intersection(_tokens(text)):
            target_hits += 1
    repeated = [{"signature": key, "count": count} for key, count in patterns.most_common(10) if count >= 1]
    return {
        "patterns": repeated,
        "target_history_hits": target_hits,
        "repeated_failure_detected": any(item["count"] >= 2 for item in repeated),
    }


def _rollback_recommendation(workflow_type: str, impacts: list[dict[str, Any]], failed_patterns: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, Any]:
    max_risk = max([float(impact.get("modification_risk", {}).get("score") or 0) for impact in impacts] or [0])
    should = workflow_type.startswith("deploy_") or max_risk >= 0.65 or bool(failed_patterns.get("repeated_failure_detected")) or bool(validation.get("timed_out"))
    return {
        "available": True,
        "recommended": should,
        "reason": "Repeated failures or high impact risk make rollback preferable." if should else "Rollback should remain available but repair can proceed within bounded scope.",
        "checkpoint_required": True,
    }


def _repair_strategies(workflow_type: str, root_causes: list[dict[str, Any]], impacts: list[dict[str, Any]], failed_patterns: Mapping[str, Any], rollback: Mapping[str, Any]) -> list[dict[str, Any]]:
    strategies = [
        {"order": 1, "strategy": "reproduce_failure", "reason": "Confirm the failure signature before editing.", "scope": "validation"},
        {"order": 2, "strategy": "minimal_targeted_patch", "reason": "Patch the smallest affected file set from impact analysis.", "scope": "affected_files"},
        {"order": 3, "strategy": "rerun_targeted_validation", "reason": "Validate the failed path before broader checks.", "scope": "validation"},
    ]
    if root_causes:
        strategies.insert(1, {"order": 2, "strategy": f"address_{root_causes[0].get('cause')}", "reason": "Top root-cause candidate from diagnostics/impact.", "scope": "root_cause"})
    if failed_patterns.get("repeated_failure_detected"):
        strategies.append({"order": 5, "strategy": "escalate_repeated_failure", "reason": "Repair history shows repeated unsuccessful patterns.", "scope": "approval"})
    if rollback.get("recommended"):
        strategies.append({"order": 6, "strategy": "recommend_rollback", "reason": rollback.get("reason", ""), "scope": "rollback"})
    return sorted(strategies, key=lambda item: int(item["order"]))


def _repair_confidence(root_causes: list[dict[str, Any]], failed_patterns: Mapping[str, Any], impacts: list[dict[str, Any]], validation: Mapping[str, Any]) -> dict[str, Any]:
    score = 35
    if root_causes:
        score += min(30, int(root_causes[0].get("confidence") or 0) // 3)
    if validation:
        score += 12
    if impacts:
        score += 12
    if failed_patterns.get("repeated_failure_detected"):
        score -= 25
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _repair_scope(impacts: list[dict[str, Any]], targets: list[str]) -> dict[str, Any]:
    affected = sorted({path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)})
    return {
        "target_files": targets,
        "affected_files": affected[:100],
        "scope_level": "narrow" if len(affected) <= 3 else "moderate" if len(affected) <= 12 else "broad",
        "do_not_broaden_without_approval": len(affected) > max(3, len(targets) * 2),
    }


def _compact_validation(validation: Mapping[str, Any]) -> dict[str, Any]:
    return {key: validation.get(key) for key in ("id", "ok", "passed", "status", "command", "returncode", "stderr", "stderr_excerpt", "summary") if key in validation}


def _repair_explanation(root_causes: list[dict[str, Any]], strategies: list[dict[str, Any]], rollback: Mapping[str, Any]) -> str:
    if not root_causes:
        return "Repair should start by reproducing the failure because no strong root-cause signal is available."
    return f"Repair should first address {root_causes[0].get('cause')} using {strategies[0].get('strategy')}; rollback recommended: {bool(rollback.get('recommended'))}."


def _roadmap_phases(
    workflow_type: str,
    objective: str,
    targets: list[str],
    impacts: list[dict[str, Any]],
    validation: Mapping[str, Any],
    repair: Mapping[str, Any],
) -> list[dict[str, Any]]:
    affected_count = len({path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)})
    phases = [
        {"id": "phase-1", "title": "Confirm architecture and impact", "status": "planned", "risk": "low", "target_files": targets, "validation_required": False},
        {"id": "phase-2", "title": "Implement smallest safe change", "status": "planned", "risk": "medium" if affected_count < 8 else "high", "target_files": targets, "validation_required": True},
        {"id": "phase-3", "title": "Run targeted validation", "status": "planned", "risk": validation.get("regression_prediction", {}).get("level", "medium"), "target_files": [], "validation_required": True},
        {"id": "phase-4", "title": "Review repair and rollback readiness", "status": "planned", "risk": "high" if repair.get("rollback_recommendation", {}).get("recommended") else "medium", "target_files": [], "validation_required": True},
    ]
    if workflow_type.startswith("deploy_"):
        phases.append({"id": "phase-5", "title": "Deployment dry-run and signoff", "status": "planned", "risk": "high", "target_files": [], "validation_required": True})
    if objective:
        phases[0]["objective"] = scrub(objective)
    return phases


def _execution_ordering(phases: list[dict[str, Any]], impacts: list[dict[str, Any]], architecture: Mapping[str, Any]) -> list[dict[str, Any]]:
    order = []
    for index, phase in enumerate(phases, start=1):
        dependencies = [] if index == 1 else [phases[index - 2]["id"]]
        order.append({"phase_id": phase["id"], "order": index, "depends_on": dependencies, "reason": _phase_reason(phase, impacts, architecture)})
    return order


def _phase_reason(phase: Mapping[str, Any], impacts: list[dict[str, Any]], architecture: Mapping[str, Any]) -> str:
    if phase.get("id") == "phase-1":
        return "Architecture/impact must be understood before edits."
    if phase.get("id") == "phase-2":
        return "Implementation waits for impact context and target scope."
    if phase.get("id") == "phase-3":
        return "Validation follows implementation and uses impact-derived targets."
    return "Review/rollback waits for validation and repair outcomes."


def _roadmap_blockers(impacts: list[dict[str, Any]], validation: Mapping[str, Any], repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    if not validation.get("prioritized_validations"):
        blockers.append({"blocker": "missing_validation_command", "reason": "No validation command is available for completion gating."})
    if any(float(impact.get("modification_risk", {}).get("score") or 0) >= 0.7 for impact in impacts):
        blockers.append({"blocker": "high_impact_scope", "reason": "Impact analysis predicts broad or high-risk changes."})
    if repair.get("failed_repair_detection", {}).get("repeated_failure_detected"):
        blockers.append({"blocker": "repeated_repair_pattern", "reason": "Repair history suggests escalation before continuing."})
    return blockers


def _parallel_safe_groups(phases: list[dict[str, Any]], impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    affected = {path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)}
    if len(affected) > 8:
        return []
    return [{"group_id": "analysis-and-validation-prep", "phase_ids": ["phase-1", "phase-3"], "reason": "Read-only analysis and validation planning can happen before edits."}]


def _milestone_prediction(phases: list[dict[str, Any]], validation: Mapping[str, Any], impacts: list[dict[str, Any]]) -> dict[str, Any]:
    risky = sum(1 for phase in phases if phase.get("risk") in {"high", "critical"})
    return {
        "milestone_count": len(phases),
        "high_risk_milestones": risky,
        "recommended_checkpoint_milestones": [phase["id"] for phase in phases if phase.get("validation_required")],
        "expected_validation_count": max(1, min(5, len(validation.get("prioritized_validations", []) or []) or 1)),
    }


def _roadmap_risk(phases: list[dict[str, Any]], impacts: list[dict[str, Any]], validation: Mapping[str, Any]) -> dict[str, Any]:
    score = 0.18 + sum(1 for phase in phases if phase.get("risk") == "high") * 0.12
    score += max([float(impact.get("modification_risk", {}).get("score") or 0) for impact in impacts] or [0]) * 0.35
    if not validation.get("prioritized_validations"):
        score += 0.2
    score = round(min(0.95, score), 3)
    return {"score": score, "level": _risk_level(score)}


def _roadmap_memory_guidance(memory: Mapping[str, Any]) -> list[str]:
    guidance = []
    if _repair_memory(memory).get("patterns"):
        guidance.append("Review prior repair patterns before selecting implementation order.")
    if _architecture_memory(memory).get("entries"):
        guidance.append("Use architecture memory to keep roadmap phases aligned with existing boundaries.")
    return guidance[:5]


def _roadmap_explanation(phases: list[dict[str, Any]], ordering: list[dict[str, Any]]) -> str:
    return f"Roadmap is decomposed into {len(phases)} phase(s), ordered by architecture impact first, implementation second, validation third, and review/rollback last."


def _execution_risk_score(workflow_type: str, targets: list[str], impacts: list[dict[str, Any]], quality: Mapping[str, Any], validation: Mapping[str, Any]) -> float:
    score = WORKFLOW_PROFILES[workflow_type]["risk_bias"] + len(targets) * 0.035
    score += max([float(impact.get("modification_risk", {}).get("score") or 0) for impact in impacts] or [0]) * 0.45
    if not validation.get("prioritized_validations"):
        score += 0.16
    if quality.get("grade") in {"D", "F"}:
        score += 0.12
    return round(min(0.98, max(0.02, score)), 3)


def _risk_level(score: float) -> str:
    return "low" if score < 0.35 else "medium" if score < 0.7 else "high"


def _risk_reasons(workflow_type: str, targets: list[str], impacts: list[dict[str, Any]], quality: Mapping[str, Any]) -> list[str]:
    reasons = [f"Workflow profile {workflow_type} has baseline risk {WORKFLOW_PROFILES[workflow_type]['risk_bias']}."]
    if targets:
        reasons.append(f"{len(targets)} target file(s) requested.")
    affected_count = len({path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)})
    if affected_count:
        reasons.append(f"Knowledge graph predicts {affected_count} affected file(s).")
    if quality.get("top_risks"):
        reasons.append("Quality dashboard has active top-risk signals.")
    return reasons[:8]


def _likely_failures(workflow_type: str, targets: list[str], impacts: list[dict[str, Any]], validation: Mapping[str, Any], quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures = []
    if not validation.get("prioritized_validations"):
        failures.append({"kind": "validation_gap", "probability": "high", "reason": "No validation command was detected."})
    for impact in impacts:
        for area in impact.get("likely_breakage_areas", []) if isinstance(impact.get("likely_breakage_areas"), list) else []:
            if isinstance(area, Mapping):
                failures.append({"kind": "breakage_area", "probability": "medium", "reason": f"{area.get('area')} is connected to the change scope."})
    if any(Path(path).name in {"package.json", "pyproject.toml", "CMakeLists.txt"} for path in targets):
        failures.append({"kind": "dependency_or_build_config", "probability": "medium", "reason": "Build/dependency files are in scope."})
    for system in quality.get("failing_systems", []) if isinstance(quality.get("failing_systems"), list) else []:
        failures.append({"kind": "known_failing_system", "probability": "medium", "reason": str(system)})
    return failures[:12]


def _validation_scope(validation: Mapping[str, Any], impacts: list[dict[str, Any]]) -> dict[str, Any]:
    affected = {path for impact in impacts for path in impact.get("affected_files", []) if isinstance(path, str)}
    return {
        "scope": "targeted" if len(affected) <= 6 else "broad",
        "affected_file_count": len(affected),
        "recommended_commands": [item.get("command") for item in validation.get("prioritized_validations", []) if isinstance(item, Mapping) and item.get("command")][:5],
    }


def _deployment_risk(workflow_type: str, targets: list[str], impacts: list[dict[str, Any]]) -> dict[str, Any]:
    deployment_files = [path for path in targets if any(part in path.lower() for part in ("docker", "compose", ".github/workflows", "azure-pipelines", "jenkins", "deploy", "k8s", "helm"))]
    score = 0.75 if workflow_type == "deploy_production" else 0.45 if workflow_type == "deploy_staging" else 0.18
    score += len(deployment_files) * 0.08
    score = min(0.95, score)
    return {"score": round(score, 3), "level": _risk_level(score), "deployment_files": deployment_files}


def _duration_estimate(workflow_type: str, targets: list[str], context: Mapping[str, Any], validation: Mapping[str, Any], roadmap: Mapping[str, Any], graph: Mapping[str, Any], risk: float) -> dict[str, Any]:
    minutes = 8 + len(targets) * 4 + len(context.get("selected_context", []) or []) * 1.5 + len(validation.get("prioritized_validations", []) or []) * 3
    minutes += len(roadmap.get("task_decomposition", []) or []) * 2
    minutes += risk * 18
    if len(graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []) > 1000:
        minutes += 8
    estimate = int(math.ceil(minutes))
    label = "short" if estimate <= 20 else "moderate" if estimate <= 60 else "long"
    return {
        "estimated_minutes": estimate,
        "label": label,
        "range": [max(3, int(minutes * 0.65)), int(minutes * 1.45)],
        "basis": "target count, context size, validation count, graph size, and risk",
    }


def _execution_reliability(risk: float, validation: Mapping[str, Any], repair: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    score = 85 - int(risk * 45)
    score += 10 if validation.get("prioritized_validations") else -15
    score += 8 if repair.get("rollback_recommendation", {}).get("available") else -8
    score += 5 if context.get("selected_context") else -10
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _prediction_confidence(context: Mapping[str, Any], validation: Mapping[str, Any], impacts: list[dict[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    score = 25
    score += 20 if context.get("selected_context") else 0
    score += 20 if validation.get("prioritized_validations") else 0
    score += 20 if impacts else 0
    score += 15 if graph.get("nodes") and graph.get("edges") else 0
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _relationship_quality(nodes: list[Mapping[str, Any]], edges: list[Mapping[str, Any]], indexing: Mapping[str, Any]) -> dict[str, Any]:
    score = 20 + min(30, len(nodes) // 4) + min(35, len(edges) // 3)
    if indexing.get("failures"):
        score -= min(20, len(indexing.get("failures", [])) * 5)
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _repair_memory(memory: Mapping[str, Any]) -> dict[str, Any]:
    patterns = []
    for entry in _memory_entries(memory):
        if isinstance(entry, Mapping) and any(key in entry for key in ("repair_patterns", "root_cause", "repair_attempts", "repair_history", "success")):
            patterns.append(_shrink(entry))
    return {"patterns": patterns[:20]}


def _architecture_memory(memory: Mapping[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in _memory_entries(memory):
        if isinstance(entry, Mapping) and any(term in json.dumps(entry, default=str).lower() for term in ("architecture", "boundary", "convention", "framework")):
            entries.append(_shrink(entry))
    return {"entries": entries[:20]}


def _looks_stale(entry: Any) -> bool:
    if not isinstance(entry, Mapping):
        return False
    text = json.dumps(entry, default=str).lower()
    return any(term in text for term in ("deprecated", "stale", "obsolete", "removed"))


def _memory_conflicts(entries: list[Any]) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        key = str(entry.get("preference") or entry.get("decision") or entry.get("framework") or "")
        value = str(entry.get("value") or entry.get("status") or entry.get("summary") or "")
        if key and key in seen and seen[key] != value:
            conflicts.append({"key": key, "values": [seen[key], value]})
        elif key:
            seen[key] = value
    return conflicts[:20]


def _shrink(value: Any, limit: int = 900) -> Any:
    text = json.dumps(value, default=str, sort_keys=True)
    if len(text) <= limit:
        return value
    return {"summary": scrub(text[:limit]), "truncated": True}


def _avg(*values: Any) -> int:
    numeric = [float(value or 0) for value in values]
    return int(round(sum(numeric) / max(1, len(numeric))))


def _benchmark_summary(scores: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {key: int(max(0, min(100, value))) for key, value in scores.items()}
    average = int(round(sum(normalized.values()) / max(1, len(normalized))))
    weakest = sorted(normalized.items(), key=lambda item: item[1])[:3]
    strongest = sorted(normalized.items(), key=lambda item: item[1], reverse=True)[:3]
    return {"overall_score": average, "weakest": [{"suite": key, "score": value} for key, value in weakest], "strongest": [{"suite": key, "score": value} for key, value in strongest]}


def _benchmark_suites() -> list[dict[str, str]]:
    return [
        {"id": "feature_quality", "measures": "Architecture-aware context and validation coverage for feature work."},
        {"id": "repair_quality", "measures": "Root-cause clarity, bounded repair strategy, and rollback readiness."},
        {"id": "validation_accuracy", "measures": "Targeted validation, dependency-aware checks, and confidence."},
        {"id": "roadmap_quality", "measures": "Task decomposition, dependencies, milestones, and risk ordering."},
        {"id": "orchestration_efficiency", "measures": "Context budget use, reliability, and selected evidence."},
        {"id": "rollback_reduction", "measures": "Rollback readiness and ability to avoid risky repair churn."},
        {"id": "execution_reliability", "measures": "Predicted stable execution under current validation and risk."},
    ]


def _benchmark_history(root: Path) -> list[dict[str, Any]]:
    path = ProjectMemory(root).root / BENCHMARK_HISTORY_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _benchmark_trends(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"run_count": 0}
    latest = history[-1].get("scores", {}) if isinstance(history[-1].get("scores"), Mapping) else {}
    previous = history[-2].get("scores", {}) if len(history) > 1 and isinstance(history[-2].get("scores"), Mapping) else {}
    return {
        "run_count": len(history),
        "latest_scores": latest,
        "delta": {key: int(latest.get(key, 0)) - int(previous.get(key, 0)) for key in latest.keys() & previous.keys()},
    }


def _user_visible_summary(workflow_type: str, target_files: list[str], predictions: Mapping[str, Any], validation: Mapping[str, Any], repair: Mapping[str, Any]) -> str:
    risk = predictions.get("execution_risk", {}).get("level", "unknown")
    validation_count = len(validation.get("prioritized_validations", []) if isinstance(validation.get("prioritized_validations"), list) else [])
    rollback = "rollback is recommended" if repair.get("rollback_recommendation", {}).get("recommended") else "rollback remains available"
    return f"{WORKFLOW_PROFILES[workflow_type]['label']} is predicted {risk} risk for {len(target_files)} target file(s), with {validation_count} validation step(s); {rollback}."


def _project_id(root: Path) -> str:
    import hashlib

    return f"project-{hashlib.sha1(str(root).lower().encode('utf-8')).hexdigest()[:12]}"
