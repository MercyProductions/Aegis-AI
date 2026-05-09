from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .knowledge import knowledge_graph
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .safety import is_safe_to_read
from .validation import detect_validation_commands
from .workspace import BUILD_FILE_SUFFIXES, SOURCE_CODE_SUFFIXES, WorkspaceScanner


DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "requirements.txt",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "CMakeLists.txt",
    "Directory.Build.props",
    "Directory.Build.targets",
}
RISK_ORDER = {"low": 0, "moderate": 1, "high": 2, "dangerous_architectural_change": 3}
ROLLBACK_ORDER = {"simple": 0, "moderate": 1, "complex": 2, "high": 3}
PATH_SUFFIXES = BUILD_FILE_SUFFIXES | SOURCE_CODE_SUFFIXES | {".json", ".md", ".toml", ".yaml", ".yml"}
PATH_EXTENSIONS = tuple(
    suffix.removeprefix(".")
    for suffix in sorted(PATH_SUFFIXES, key=lambda item: (-len(item), item))
)
PATH_PATTERN = re.compile(
    r"([A-Za-z0-9_./\\-]+\.(?:" + "|".join(PATH_EXTENSIONS) + r"))"
)
COMMON_WORDS = {
    "add",
    "and",
    "api",
    "build",
    "change",
    "code",
    "core",
    "file",
    "fix",
    "for",
    "from",
    "into",
    "local",
    "model",
    "plan",
    "project",
    "risk",
    "scan",
    "system",
    "task",
    "test",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def simulate_change(
    workspace: str | Path,
    objective: str,
    *,
    files: list[str] | None = None,
    approach: str | None = None,
    scan: dict[str, Any] | None = None,
    graph: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Forecast the likely impact of a planned change without mutating files."""

    root = Path(workspace).resolve()
    objective_text = scrub(str(objective or "")).strip()
    if not objective_text:
        raise ValueError("A non-empty change objective is required.")

    scan_data = scan or WorkspaceScanner(root).scan(persist=False)
    graph_data = graph or knowledge_graph(root, scan=scan_data)
    quality_data = quality or quality_dashboard(root, scan=scan_data)
    approach_text = scrub(str(approach or "")).strip() or "unspecified"

    focus_files, blocked_context = _focus_files(root, objective_text, files or [], scan_data, graph_data)
    impacted_files = _impacted_files(focus_files, scan_data, graph_data, quality_data)
    affected_systems = _affected_systems(objective_text, impacted_files, scan_data, graph_data)
    history = _history_signals(root, quality_data)
    dependency_ripple = _dependency_ripple(focus_files, impacted_files, graph_data)
    validation = _validation_complexity(root, impacted_files, affected_systems)
    build_risks = _likely_build_risks(objective_text, approach_text, impacted_files, affected_systems, quality_data, validation, dependency_ripple)
    test_risks = _likely_test_failures(impacted_files, scan_data, quality_data, validation, history)
    architecture_drift = _architecture_drift(
        objective_text,
        approach_text,
        affected_systems,
        impacted_files,
        dependency_ripple,
        quality_data,
        history,
    )
    risk = _risk_forecast(
        objective_text,
        approach_text,
        impacted_files,
        affected_systems,
        quality_data,
        history,
        dependency_ripple,
        validation,
        build_risks,
        test_risks,
        architecture_drift,
    )
    rollback = _rollback_complexity(impacted_files, affected_systems, dependency_ripple, risk["risk_level"])
    prediction = _prediction(
        focus_files,
        impacted_files,
        affected_systems,
        scan_data,
        quality_data,
        build_risks,
        test_risks,
        validation,
    )
    roadmap = _roadmap_forecast(risk, impacted_files, affected_systems, build_risks, test_risks, validation, rollback)
    recommended_plan = _recommended_plan(risk, prediction, architecture_drift, validation, rollback)
    confidence = _confidence_score(focus_files, scan_data, graph_data, quality_data, history, validation)

    return {
        "workspace": str(root),
        "objective": objective_text,
        "approach": approach_text,
        "generated_at": utc_now(),
        "risk_level": risk["risk_level"],
        "risk_score": risk["risk_score"],
        "risk_contributors": risk["contributors"],
        "confidence": confidence,
        "affected_systems": affected_systems,
        "focus_files": focus_files,
        "impacted_files": impacted_files,
        "blocked_context": blocked_context,
        "likely_build_risks": build_risks,
        "likely_test_failures": test_risks,
        "dependency_ripple": dependency_ripple,
        "architecture_drift": architecture_drift,
        "prediction": prediction,
        "roadmap_forecast": roadmap,
        "rollback_complexity": rollback,
        "recommended_plan": recommended_plan,
        "history_signals": history,
        "ui": {
            "predicted_impact": _impact_label(risk["risk_level"], impacted_files, affected_systems),
            "likely_affected_systems": affected_systems,
            "confidence_score": confidence,
            "estimated_validation_cost": roadmap["validation_cost"],
            "rollback_complexity": rollback["level"],
            "status_badge": _risk_badge(risk["risk_level"]),
            "top_warnings": _top_warning_text(build_risks, test_risks, architecture_drift),
        },
    }


def compare_scenarios(
    workspace: str | Path,
    objective: str,
    approaches: list[str],
    *,
    files: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    approach_list = [scrub(str(item or "")).strip() for item in approaches if scrub(str(item or "")).strip()]
    if not approach_list:
        raise ValueError("At least one implementation approach is required for scenario comparison.")
    scan = WorkspaceScanner(root).scan(persist=False)
    graph = knowledge_graph(root, scan=scan)
    quality = quality_dashboard(root, scan=scan)
    simulations = [
        simulate_change(root, objective, files=files or [], approach=approach, scan=scan, graph=graph, quality=quality)
        for approach in approach_list[:6]
    ]
    ranked = sorted(simulations, key=_scenario_sort_key)
    for rank, simulation in enumerate(ranked, start=1):
        simulation["rank"] = rank
    comparison = [
        {
            "rank": simulation["rank"],
            "approach": simulation["approach"],
            "risk_level": simulation["risk_level"],
            "risk_score": simulation["risk_score"],
            "confidence": simulation["confidence"],
            "affected_systems": simulation["affected_systems"],
            "impacted_file_count": len(simulation["impacted_files"]),
            "validation_cost": simulation["roadmap_forecast"]["validation_cost"],
            "rollback_complexity": simulation["rollback_complexity"]["level"],
            "reason": _scenario_reason(simulation),
        }
        for simulation in ranked
    ]
    recommended = ranked[0]
    return {
        "workspace": str(root),
        "objective": scrub(str(objective or "")).strip(),
        "generated_at": utc_now(),
        "recommended_approach": recommended["approach"],
        "recommended_reason": _scenario_reason(recommended),
        "comparison": comparison,
        "simulations": simulations,
        "ui": {
            "recommended_approach": recommended["approach"],
            "recommended_risk": recommended["risk_level"],
            "confidence_score": recommended["confidence"],
            "estimated_validation_cost": recommended["roadmap_forecast"]["validation_cost"],
            "rollback_complexity": recommended["rollback_complexity"]["level"],
        },
    }


def planner_simulation_summary(simulation: dict[str, Any] | None) -> dict[str, Any]:
    if not simulation:
        return {}
    recommended = simulation.get("recommended_plan", {}) if isinstance(simulation.get("recommended_plan"), dict) else {}
    roadmap = simulation.get("roadmap_forecast", {}) if isinstance(simulation.get("roadmap_forecast"), dict) else {}
    rollback = simulation.get("rollback_complexity", {}) if isinstance(simulation.get("rollback_complexity"), dict) else {}
    return {
        "risk_level": simulation.get("risk_level"),
        "risk_score": simulation.get("risk_score"),
        "confidence": simulation.get("confidence"),
        "affected_systems": simulation.get("affected_systems", [])[:8],
        "impacted_file_count": len(simulation.get("impacted_files", []) if isinstance(simulation.get("impacted_files"), list) else []),
        "likely_files_needing_edits": simulation.get("prediction", {}).get("files_likely_needing_edits", [])[:8],
        "top_build_risks": simulation.get("likely_build_risks", [])[:3],
        "top_test_risks": simulation.get("likely_test_failures", [])[:3],
        "architecture_drift_warnings": simulation.get("architecture_drift", {}).get("warnings", [])[:4],
        "validation_cost": roadmap.get("validation_cost"),
        "rollback_complexity": rollback.get("level"),
        "split_recommended": bool(recommended.get("split_recommended")),
        "recommended_first_step": (recommended.get("steps") or ["Inspect predicted impact before proposing edits."])[0],
    }


def planner_simulation_guidance(simulation: dict[str, Any] | None) -> list[str]:
    if not simulation:
        return []
    guidance: list[str] = []
    risk = str(simulation.get("risk_level") or "low")
    if risk in {"high", "dangerous_architectural_change"}:
        guidance.append("Split this change into the smallest approved slice before implementation.")
    if simulation.get("architecture_drift", {}).get("warnings"):
        guidance.append("Review architecture drift warnings before the Coder Agent proposes changes.")
    if simulation.get("dependency_ripple", {}).get("cross_system_edges"):
        guidance.append("Validate cross-system dependency ripple before editing shared modules.")
    if simulation.get("rollback_complexity", {}).get("level") in {"complex", "high"}:
        guidance.append("Create a checkpoint and define rollback ownership before approved edits.")
    validation = simulation.get("roadmap_forecast", {}).get("validation_cost")
    if validation:
        guidance.append(f"Budget validation effort as {validation} and avoid skipping tests for this task.")
    return guidance[:6]


def _focus_files(
    root: Path,
    objective: str,
    requested_files: list[str],
    scan: dict[str, Any],
    graph: dict[str, Any],
) -> tuple[list[str], list[dict[str, str]]]:
    all_files = _all_files(scan)
    focus: list[str] = []
    blocked: list[dict[str, str]] = []
    for item in requested_files[:50]:
        relative = str(item or "").strip().replace("\\", "/").lstrip("./")
        if not relative:
            continue
        candidate = (root / relative).resolve()
        if not is_safe_to_read(candidate, root):
            blocked.append({"path": relative, "reason": "secret-like, ignored, or outside workspace"})
            continue
        if not candidate.is_file():
            blocked.append({"path": relative, "reason": "not a readable file"})
            continue
        focus.append(_relative_path(root, candidate))

    for path in _path_mentions(objective, all_files):
        focus.append(path)
    if focus:
        return _dedupe(focus)[:12], blocked

    tokens = _tokens(objective)
    scored: list[tuple[int, str]] = []
    symbols = scan.get("symbol_index") if isinstance(scan.get("symbol_index"), dict) else {}
    for path in all_files:
        lower = path.lower()
        score = sum(3 for token in tokens if token in lower)
        for symbol in symbols.get(path, []) if isinstance(symbols.get(path), list) else []:
            name = str(symbol.get("name") or "").lower() if isinstance(symbol, dict) else ""
            score += sum(2 for token in tokens if token in name)
        if score:
            scored.append((score, path))
    if scored:
        return [path for _, path in sorted(scored, key=lambda item: (-item[0], item[1]))[:8]], blocked

    fallback = []
    for key in ("entry_points", "build_files", "recent_files", "readmes"):
        fallback.extend(str(item) for item in scan.get(key, [])[:4])
    return _dedupe(fallback)[:8], blocked


def _impacted_files(
    focus_files: list[str],
    scan: dict[str, Any],
    graph: dict[str, Any],
    quality: dict[str, Any],
) -> list[dict[str, Any]]:
    impacted: dict[str, dict[str, Any]] = {}
    for path in focus_files:
        impacted[path] = {"path": path, "reason": "focus", "confidence": 0.95}

    nodes = {node.get("id"): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    focus_ids = {f"file:{path}" for path in focus_files}
    related_edges = []
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        edge_type = str(edge.get("type") or "")
        if edge_type not in {"uses", "depends_on", "calls", "tested_by", "implements", "breaks", "related_to"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in focus_ids and target not in focus_ids:
            continue
        related_edges.append(edge)
        for node_id in (source, target):
            node = nodes.get(node_id)
            if isinstance(node, dict) and node.get("type") == "file" and node.get("path"):
                path = str(node["path"])
                impacted.setdefault(path, {"path": path, "reason": f"graph:{edge_type}", "confidence": 0.75})

    focus_stems = {Path(path).stem.lower() for path in focus_files}
    for test_file in scan.get("test_files", []) if isinstance(scan.get("test_files"), list) else []:
        lower = str(test_file).lower()
        if any(stem and stem in lower for stem in focus_stems):
            impacted.setdefault(str(test_file), {"path": str(test_file), "reason": "related test", "confidence": 0.7})

    high_risk = quality.get("high_risk_files") if isinstance(quality.get("high_risk_files"), list) else []
    focus_systems = {_system_for_path(path) for path in focus_files}
    for item in high_risk:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path = str(item["path"])
        if _system_for_path(path) in focus_systems:
            impacted.setdefault(path, {"path": path, "reason": "same high-risk system", "confidence": 0.62})

    return sorted(impacted.values(), key=lambda item: (item.get("reason") != "focus", item.get("path", "")))[:30]


def _affected_systems(objective: str, impacted_files: list[dict[str, Any]], scan: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    systems = [_system_for_path(str(item.get("path") or "")) for item in impacted_files if item.get("path")]
    impacted_ids = {f"file:{item.get('path')}" for item in impacted_files if item.get("path")}
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    lower = objective.lower()
    for framework in scan.get("frameworks", [])[:8]:
        name = str(framework)
        if name.lower() in lower or any(_system_for_path(str(item.get("path") or "")) == _system_for_path(name) for item in impacted_files):
            systems.append(name)
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        if str(edge.get("type") or "") != "contains" or edge.get("target") not in impacted_ids:
            continue
        source = str(edge.get("source") or "")
        node = nodes.get(source)
        if isinstance(node, dict) and node.get("type") == "system":
            systems.append(str(node.get("label") or source.removeprefix("system:")))
    if any(term in lower for term in ("website", "frontend", "backend", "fastapi")):
        systems.append("website")
    if any(term in lower for term in ("desktop", "tauri", "electron")):
        systems.append("desktop-client")
    if any(term in lower for term in ("vscode", "vs code")):
        systems.append("vscode-extension")
    if any(term in lower for term in ("visual studio", "vsix")):
        systems.append("visual-studio-extension")
    return _dedupe([system for system in systems if system and system != "workspace"])[:10] or ["workspace"]


def _dependency_ripple(focus_files: list[str], impacted_files: list[dict[str, Any]], graph: dict[str, Any]) -> dict[str, Any]:
    focus_ids = {f"file:{path}" for path in focus_files}
    impacted_ids = {f"file:{item['path']}" for item in impacted_files if item.get("path")}
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    upstream: list[str] = []
    downstream: list[str] = []
    cross_system_edges: list[dict[str, str]] = []
    direct_edges = 0
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        edge_type = str(edge.get("type") or "")
        if edge_type not in {"uses", "depends_on", "calls"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in impacted_ids or target in impacted_ids:
            direct_edges += 1
        if target in focus_ids:
            upstream.extend(_node_path(nodes.get(source)))
        if source in focus_ids:
            downstream.extend(_node_path(nodes.get(target)))
        source_path = _first(_node_path(nodes.get(source)))
        target_path = _first(_node_path(nodes.get(target)))
        if source_path and target_path and _system_for_path(source_path) != _system_for_path(target_path):
            cross_system_edges.append({"source": source_path, "target": target_path, "type": edge_type})
    upstream = _dedupe(upstream)[:12]
    downstream = _dedupe(downstream)[:12]
    return {
        "direct_edge_count": direct_edges,
        "upstream_dependents": upstream,
        "downstream_dependencies": downstream,
        "cross_system_edges": cross_system_edges[:12],
        "summary": _ripple_summary(direct_edges, upstream, downstream, cross_system_edges),
    }


def _likely_build_risks(
    objective: str,
    approach: str,
    impacted_files: list[dict[str, Any]],
    affected_systems: list[str],
    quality: dict[str, Any],
    validation: dict[str, Any],
    ripple: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    paths = [str(item.get("path") or "") for item in impacted_files]
    statuses = quality.get("statuses") if isinstance(quality.get("statuses"), dict) else {}
    if _status_failed(statuses.get("build")) or _status_failed(statuses.get("validation")):
        risks.append({"title": "Existing validation is already failing", "severity": "high", "evidence": statuses})
    dependency_paths = [path for path in paths if Path(path).name in DEPENDENCY_FILES or Path(path).suffix.lower() in BUILD_FILE_SUFFIXES]
    if dependency_paths:
        risks.append({"title": "Build or dependency manifest may be affected", "severity": "high", "files": dependency_paths[:8]})
    if not validation["commands"]:
        risks.append({"title": "No detected validation command", "severity": "moderate", "evidence": "Manual validation path needed before risky edits."})
    if len(affected_systems) >= 4 or len(ripple.get("cross_system_edges", [])) >= 4:
        risks.append({"title": "Change crosses multiple runtime boundaries", "severity": "moderate", "systems": affected_systems[:8]})
    if any(term in (objective + " " + approach).lower() for term in ("rewrite", "migration", "replace", "remove", "delete")):
        risks.append({"title": "Objective wording suggests migration/removal risk", "severity": "moderate", "evidence": "Prefer staged compatibility shims."})
    return risks[:8]


def _likely_test_failures(
    impacted_files: list[dict[str, Any]],
    scan: dict[str, Any],
    quality: dict[str, Any],
    validation: dict[str, Any],
    history: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    statuses = quality.get("statuses") if isinstance(quality.get("statuses"), dict) else {}
    if _status_failed(statuses.get("test")):
        risks.append({"title": "Existing test status is failing", "severity": "high", "evidence": statuses.get("test")})
    tests = scan.get("test_files") if isinstance(scan.get("test_files"), list) else []
    if not tests:
        risks.append({"title": "No test files detected", "severity": "moderate", "evidence": "Prediction confidence is lower without tests."})
    impacted_paths = [str(item.get("path") or "") for item in impacted_files]
    stems = {Path(path).stem.lower() for path in impacted_paths}
    related_tests = [str(path) for path in tests if any(stem and stem in str(path).lower() for stem in stems)]
    if related_tests:
        risks.append({"title": "Related tests likely need attention", "severity": "moderate", "files": related_tests[:10]})
    if history.get("previous_validation_failures", 0) >= 2:
        risks.append({"title": "Validation has failed repeatedly in project history", "severity": "moderate", "count": history["previous_validation_failures"]})
    if validation["level"] in {"high", "very_high"}:
        risks.append({"title": "Validation path is expensive", "severity": "low", "evidence": validation["summary"]})
    return risks[:8]


def _architecture_drift(
    objective: str,
    approach: str,
    affected_systems: list[str],
    impacted_files: list[dict[str, Any]],
    ripple: dict[str, Any],
    quality: dict[str, Any],
    history: dict[str, Any],
) -> dict[str, Any]:
    text = f"{objective} {approach}".lower()
    warnings: list[dict[str, Any]] = []
    if any(term in text for term in ("rewrite", "replace architecture", "global", "big bang", "massive")):
        warnings.append({"severity": "high", "warning": "Approach suggests a broad rewrite; prefer incremental compatibility slices."})
    if any(term in text for term in ("quick fix", "temporary", "hack", "bypass")):
        warnings.append({"severity": "moderate", "warning": "Temporary-code language increases technical-debt risk."})
    if len(affected_systems) >= 4:
        warnings.append({"severity": "moderate", "warning": "Change spans many systems and can blur runtime ownership."})
    if len(ripple.get("cross_system_edges", [])) >= 4:
        warnings.append({"severity": "moderate", "warning": "Existing dependency graph already has cross-system ripple in the focus area."})
    high_risk_paths = {str(item.get("path") or "") for item in quality.get("high_risk_files", []) if isinstance(item, dict)}
    touched_high_risk = [str(item.get("path")) for item in impacted_files if str(item.get("path") or "") in high_risk_paths]
    if touched_high_risk:
        warnings.append({"severity": "high", "warning": "Predicted edits touch high-risk files.", "files": touched_high_risk[:8]})
    if history.get("repeated_repair_attempts", 0) >= 2:
        warnings.append({"severity": "moderate", "warning": "Repeated repair attempts suggest accumulated fragile fixes."})
    drift_score = min(100, len(warnings) * 18 + len(affected_systems) * 4 + len(ripple.get("cross_system_edges", [])) * 3)
    level = "high" if drift_score >= 65 else "moderate" if drift_score >= 30 else "low"
    return {
        "level": level,
        "score": drift_score,
        "warnings": warnings[:8],
        "coupling_signals": {
            "affected_system_count": len(affected_systems),
            "cross_system_edge_count": len(ripple.get("cross_system_edges", [])),
            "impacted_file_count": len(impacted_files),
        },
    }


def _risk_forecast(
    objective: str,
    approach: str,
    impacted_files: list[dict[str, Any]],
    affected_systems: list[str],
    quality: dict[str, Any],
    history: dict[str, Any],
    ripple: dict[str, Any],
    validation: dict[str, Any],
    build_risks: list[dict[str, Any]],
    test_risks: list[dict[str, Any]],
    architecture_drift: dict[str, Any],
) -> dict[str, Any]:
    score = 10
    contributors: list[dict[str, Any]] = []

    def add(signal: str, weight: int, evidence: Any = None) -> None:
        nonlocal score
        if weight == 0:
            return
        score += weight
        contributors.append({"signal": signal, "weight": weight, "evidence": evidence})

    approach_lower = approach.lower()
    objective_lower = objective.lower()
    if any(term in approach_lower for term in ("minimal", "incremental", "adapter", "shim", "compatibility", "test-first")):
        add("Approach is incremental or compatibility-first", -8, approach)
    if any(term in approach_lower for term in ("rewrite", "replace", "global", "big bang", "remove old", "delete")):
        add("Approach suggests broad replacement", 18, approach)
    if any(term in objective_lower for term in ("delete", "remove", "migration", "auth", "credentials", "install", "installer", "package", "cloud", "secrets")):
        add("Objective includes high-risk operation terms", 28)

    health_score = int(quality.get("score") or 100)
    if health_score < 60:
        add("Project health score is low", 18, health_score)
    elif health_score < 75:
        add("Project health score is below target", 8, health_score)
    if impacted_files and len(impacted_files) > 12:
        add("Many files may be affected", 12, len(impacted_files))
    if len(affected_systems) >= 4:
        add("Many systems may be affected", 14, affected_systems)
    if ripple.get("direct_edge_count", 0) >= 10:
        add("Dependency ripple is broad", 10, ripple.get("direct_edge_count"))
    if ripple.get("cross_system_edges"):
        add("Cross-system dependencies are involved", min(14, len(ripple["cross_system_edges"]) * 3), ripple["cross_system_edges"][:5])
    if validation["level"] in {"high", "very_high"}:
        add("Validation cost is high", 8, validation["summary"])
    if not validation["commands"]:
        add("No automated validation command detected", 8)
    if build_risks:
        add("Build risks predicted", min(18, len(build_risks) * 6), build_risks[:3])
    if test_risks:
        add("Test risks predicted", min(14, len(test_risks) * 5), test_risks[:3])
    if architecture_drift.get("level") == "high":
        add("Architecture drift risk is high", 16, architecture_drift.get("warnings", [])[:3])
    elif architecture_drift.get("level") == "moderate":
        add("Architecture drift risk is moderate", 8, architecture_drift.get("warnings", [])[:3])
    if history.get("previous_validation_failures", 0) >= 3:
        add("Historical validation failures are recurring", 10, history["previous_validation_failures"])
    if history.get("repeated_repair_attempts", 0) >= 2:
        add("Repeated repair attempts indicate fragile area", 8, history["repeated_repair_attempts"])

    score = max(0, min(100, score))
    if score >= 80:
        risk_level = "dangerous_architectural_change"
    elif score >= 55:
        risk_level = "high"
    elif score >= 30:
        risk_level = "moderate"
    else:
        risk_level = "low"
    return {"risk_level": risk_level, "risk_score": score, "contributors": contributors[:12]}


def _prediction(
    focus_files: list[str],
    impacted_files: list[dict[str, Any]],
    affected_systems: list[str],
    scan: dict[str, Any],
    quality: dict[str, Any],
    build_risks: list[dict[str, Any]],
    test_risks: list[dict[str, Any]],
    validation: dict[str, Any],
) -> dict[str, Any]:
    impacted_paths = [str(item.get("path") or "") for item in impacted_files if item.get("path")]
    likely_files = []
    for path in _dedupe([*focus_files, *impacted_paths]):
        reason = "requested/focus file" if path in focus_files else "dependency or graph neighbor"
        likely_files.append({"path": path, "reason": reason})
    high_risk_files = [item for item in quality.get("high_risk_files", []) if isinstance(item, dict)]
    systems_likely_to_break = _dedupe(
        [
            *affected_systems,
            *[str(item.get("system") or _system_for_path(str(item.get("path") or ""))) for item in high_risk_files[:8]],
            *[str(system) for system in quality.get("failing_systems", []) if system],
        ]
    )[:10]
    tests_likely_to_fail = []
    for risk in test_risks:
        for path in risk.get("files", []) if isinstance(risk.get("files"), list) else []:
            tests_likely_to_fail.append({"path": str(path), "reason": risk.get("title", "related test risk")})
    performance_risks = _performance_risks(impacted_paths, scan)
    return {
        "files_likely_needing_edits": likely_files[:14],
        "systems_likely_to_break": systems_likely_to_break,
        "tests_likely_to_fail": tests_likely_to_fail[:10],
        "build_risks": build_risks[:6],
        "performance_risks": performance_risks,
        "validation_complexity": validation,
    }


def _roadmap_forecast(
    risk: dict[str, Any],
    impacted_files: list[dict[str, Any]],
    affected_systems: list[str],
    build_risks: list[dict[str, Any]],
    test_risks: list[dict[str, Any]],
    validation: dict[str, Any],
    rollback: dict[str, Any],
) -> dict[str, Any]:
    risk_level = str(risk.get("risk_level") or "low")
    difficulty = {
        "low": "easy",
        "moderate": "moderate",
        "high": "hard",
        "dangerous_architectural_change": "very_hard",
    }[risk_level]
    if len(impacted_files) <= 4 and len(affected_systems) <= 2:
        task_size = "small"
    elif len(impacted_files) <= 12 and len(affected_systems) <= 4:
        task_size = "medium"
    else:
        task_size = "large"
    blockers = []
    blockers.extend(risk_item.get("title", "Build risk") for risk_item in build_risks[:3])
    blockers.extend(risk_item.get("title", "Test risk") for risk_item in test_risks[:3])
    if rollback.get("level") in {"complex", "high"}:
        blockers.append("Rollback path needs an explicit checkpoint plan.")
    return {
        "implementation_difficulty": difficulty,
        "estimated_task_size": task_size,
        "likely_blockers": _dedupe([str(item) for item in blockers])[:8],
        "systems_involved": affected_systems,
        "validation_cost": validation["summary"],
        "estimated_validation_minutes": validation["estimated_minutes"],
    }


def _recommended_plan(
    risk: dict[str, Any],
    prediction: dict[str, Any],
    drift: dict[str, Any],
    validation: dict[str, Any],
    rollback: dict[str, Any],
) -> dict[str, Any]:
    risk_level = str(risk.get("risk_level") or "low")
    split = risk_level in {"high", "dangerous_architectural_change"} or drift.get("level") == "high"
    steps = [
        "Inspect predicted files and graph neighbors before proposing edits.",
        "Choose the smallest compatibility-preserving change slice.",
        "Prepare a checkpoint before any approved file writes.",
    ]
    if split:
        steps.insert(1, "Split the goal into a first safe slice and defer broad cleanup.")
    if validation["commands"]:
        steps.append("Run the detected validation commands after approved edits.")
    else:
        steps.append("Ask for a manual validation path before risky edits.")
    if rollback.get("level") in {"complex", "high"}:
        steps.append("Confirm rollback owner and restore path before implementation.")
    if prediction.get("tests_likely_to_fail"):
        steps.append("Prioritize related tests while reviewing the proposal.")
    return {
        "split_recommended": split,
        "steps": steps[:7],
        "avoid": _avoidance_guidance(risk_level, drift),
        "approval_reminders": ["file_edit", "file_delete", "build_command", "install_package", "cloud_context"],
    }


def _validation_complexity(root: Path, impacted_files: list[dict[str, Any]], affected_systems: list[str]) -> dict[str, Any]:
    commands = [command.__dict__ for command in detect_validation_commands(root)]
    estimated_minutes = 1 + len(commands) * 3 + min(10, len(impacted_files) // 3) + min(8, len(affected_systems))
    if not commands:
        level = "manual"
        summary = "manual validation needed; no detected build/test/lint command"
        estimated_minutes = 0
    elif estimated_minutes >= 20:
        level = "very_high"
        summary = f"very high ({len(commands)} detected commands, about {estimated_minutes} min)"
    elif estimated_minutes >= 12:
        level = "high"
        summary = f"high ({len(commands)} detected commands, about {estimated_minutes} min)"
    elif estimated_minutes >= 6:
        level = "moderate"
        summary = f"moderate ({len(commands)} detected commands, about {estimated_minutes} min)"
    else:
        level = "low"
        summary = f"low ({len(commands)} detected command, about {estimated_minutes} min)"
    return {
        "level": level,
        "commands": commands,
        "estimated_minutes": estimated_minutes,
        "summary": summary,
    }


def _rollback_complexity(
    impacted_files: list[dict[str, Any]],
    affected_systems: list[str],
    ripple: dict[str, Any],
    risk_level: str,
) -> dict[str, Any]:
    score = len(impacted_files) * 2 + len(affected_systems) * 4 + len(ripple.get("cross_system_edges", [])) * 3
    if risk_level == "dangerous_architectural_change":
        score += 25
    elif risk_level == "high":
        score += 15
    if any(Path(str(item.get("path") or "")).name in DEPENDENCY_FILES for item in impacted_files):
        score += 12
    if score >= 55:
        level = "high"
    elif score >= 32:
        level = "complex"
    elif score >= 14:
        level = "moderate"
    else:
        level = "simple"
    return {
        "level": level,
        "score": min(100, score),
        "checkpoint_required": True,
        "recommended_restore_scope": "workspace checkpoint" if level in {"complex", "high"} else "affected files",
        "notes": [
            "Clients applying patches should create checkpoints before writes.",
            "Core prediction is advisory and does not perform rollback itself.",
        ],
    }


def _history_signals(root: Path, quality: dict[str, Any]) -> dict[str, Any]:
    memory = ProjectMemory(root)
    health_history = quality.get("history") if isinstance(quality.get("history"), list) else _read_json_list(memory.root / "health-history.json")
    validation_text = _read_text(root / "validation-log.md")
    agent_history = _read_json_list(memory.root / "agent-history.json")
    current_snapshot = quality.get("current_snapshot") if isinstance(quality.get("current_snapshot"), dict) else {}
    recurring_errors = []
    if validation_text:
        lines = [
            scrub(line.strip())[:180]
            for line in validation_text.splitlines()
            if any(term in line.lower() for term in ("error", "failed", "exception", "traceback"))
        ]
        recurring_errors = [line for line, _ in Counter(lines).most_common(5) if line]
    return {
        "health_snapshot_count": len(health_history),
        "agent_event_count": len(agent_history),
        "previous_validation_failures": len(re.findall(r"^##\s+.+?\s+-\s+failed\s*$", validation_text, flags=re.MULTILINE)),
        "repeated_repair_attempts": int(current_snapshot.get("repeated_repair_attempts") or 0),
        "repeated_model_failures": int(current_snapshot.get("repeated_model_failures") or 0),
        "frequently_changed_files": current_snapshot.get("files_changed_most_often", [])[:8],
        "recurring_errors": recurring_errors,
        "learning_note": f"Predictions use {len(health_history)} health snapshots, {len(agent_history)} agent events, and recent validation logs.",
    }


def _confidence_score(
    focus_files: list[str],
    scan: dict[str, Any],
    graph: dict[str, Any],
    quality: dict[str, Any],
    history: dict[str, Any],
    validation: dict[str, Any],
) -> int:
    score = 45
    if focus_files:
        score += 12
    if scan.get("file_count", 0) > 0:
        score += 8
    if len(graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []) >= 5:
        score += 10
    if len(graph.get("edges", []) if isinstance(graph.get("edges"), list) else []) >= 3:
        score += 8
    if quality.get("score") is not None:
        score += 6
    if history.get("health_snapshot_count", 0):
        score += 5
    if validation.get("commands"):
        score += 6
    return max(20, min(95, score))


def _performance_risks(impacted_paths: list[str], scan: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    if int(scan.get("file_count") or 0) > 2000:
        risks.append({"title": "Large workspace size may make scans and validation slower", "severity": "low"})
    if any(any(token in path.lower() for token in ("index", "scanner", "graph", "search", "embedding")) for path in impacted_paths):
        risks.append({"title": "Indexing/search path may affect runtime latency", "severity": "moderate"})
    if any(Path(path).name in DEPENDENCY_FILES for path in impacted_paths):
        risks.append({"title": "Dependency changes may alter install or startup time", "severity": "moderate"})
    return risks[:5]


def _all_files(scan: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("build_files", "readmes", "test_files", "entry_points", "recent_files"):
        files.extend(str(item) for item in scan.get(key, []) if item)
    dependency = scan.get("dependency_graph") if isinstance(scan.get("dependency_graph"), dict) else {}
    graph_files = dependency.get("files") if isinstance(dependency.get("files"), dict) else {}
    files.extend(str(path) for path in graph_files.keys())
    symbols = scan.get("symbol_index") if isinstance(scan.get("symbol_index"), dict) else {}
    files.extend(str(path) for path in symbols.keys())
    for item in scan.get("todo_comments", []) if isinstance(scan.get("todo_comments"), list) else []:
        if isinstance(item, dict) and item.get("file"):
            files.append(str(item["file"]))
    return _dedupe(path.replace("\\", "/").lstrip("./") for path in files if path)


def _path_mentions(objective: str, all_files: list[str]) -> list[str]:
    mentioned: list[str] = []
    known = set(all_files)
    for match in PATH_PATTERN.finditer(objective):
        path = match.group(1).replace("\\", "/").lstrip("./")
        if path in known:
            mentioned.append(path)
            continue
        suffix_match = next((item for item in all_files if item.lower().endswith(path.lower())), None)
        if suffix_match:
            mentioned.append(suffix_match)
    return _dedupe(mentioned)


def _tokens(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text.lower())
    return [token for token in tokens if token not in COMMON_WORDS][:20]


def _system_for_path(path: str) -> str:
    lower = path.replace("\\", "/").lower()
    if not lower:
        return "workspace"
    if "aegis-core" in lower or "aegis_core" in lower:
        return "aegis-core"
    if lower.startswith("website/backend") or "/backend/" in lower:
        return "website-backend"
    if lower.startswith("website/frontend") or "/frontend/" in lower or lower.endswith((".tsx", ".jsx", ".css")):
        return "website-frontend"
    if "vscode" in lower or "vs-code" in lower:
        return "vscode-extension"
    if "visualstudio" in lower or "visual-studio" in lower or Path(lower).suffix.lower() in BUILD_FILE_SUFFIXES:
        return "visual-studio-extension"
    if "desktop" in lower or "tauri" in lower or "electron" in lower:
        return "desktop-client"
    if lower.startswith("tests/") or "/tests/" in lower or Path(lower).name.startswith("test_"):
        return "tests"
    if lower.startswith("docs/") or lower.endswith(".md"):
        return "documentation"
    if "/" in lower:
        return lower.split("/", 1)[0]
    return "workspace"


def _status_failed(status: Any) -> bool:
    return isinstance(status, dict) and status.get("status") == "failed"


def _node_path(node: Any) -> list[str]:
    if isinstance(node, dict) and node.get("type") == "file" and node.get("path"):
        return [str(node["path"])]
    return []


def _first(items: list[str]) -> str | None:
    return items[0] if items else None


def _dedupe(items: Any) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else item
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _ripple_summary(direct_edges: int, upstream: list[str], downstream: list[str], cross_system_edges: list[dict[str, str]]) -> str:
    if not direct_edges and not upstream and not downstream:
        return "No dependency ripple detected from the current graph."
    return (
        f"{direct_edges} related dependency edges, "
        f"{len(upstream)} upstream dependents, {len(downstream)} downstream dependencies, "
        f"and {len(cross_system_edges)} cross-system edges."
    )


def _impact_label(risk_level: str, impacted_files: list[dict[str, Any]], systems: list[str]) -> str:
    return f"{_risk_badge(risk_level)} impact across {len(systems)} system(s) and {len(impacted_files)} likely file(s)."


def _risk_badge(risk_level: str) -> str:
    return {
        "low": "Low",
        "moderate": "Moderate",
        "high": "High",
        "dangerous_architectural_change": "Dangerous architectural change",
    }.get(risk_level, "Unknown")


def _top_warning_text(build_risks: list[dict[str, Any]], test_risks: list[dict[str, Any]], drift: dict[str, Any]) -> list[str]:
    warnings = [str(item.get("title") or item.get("warning")) for item in [*build_risks[:2], *test_risks[:2]] if item]
    warnings.extend(str(item.get("warning")) for item in drift.get("warnings", [])[:2] if isinstance(item, dict))
    return _dedupe([warning for warning in warnings if warning])[:5]


def _scenario_sort_key(simulation: dict[str, Any]) -> tuple[int, int, int, int]:
    rollback_level = simulation.get("rollback_complexity", {}).get("level", "simple")
    return (
        RISK_ORDER.get(str(simulation.get("risk_level")), 9),
        int(simulation.get("risk_score") or 100),
        ROLLBACK_ORDER.get(str(rollback_level), 9),
        len(simulation.get("impacted_files", []) if isinstance(simulation.get("impacted_files"), list) else []),
    )


def _scenario_reason(simulation: dict[str, Any]) -> str:
    risk = _risk_badge(str(simulation.get("risk_level") or "low"))
    files = len(simulation.get("impacted_files", []) if isinstance(simulation.get("impacted_files"), list) else [])
    validation = simulation.get("roadmap_forecast", {}).get("validation_cost", "unknown validation cost")
    rollback = simulation.get("rollback_complexity", {}).get("level", "unknown")
    return f"{risk} risk, {files} likely files, {validation}, {rollback} rollback."


def _avoidance_guidance(risk_level: str, drift: dict[str, Any]) -> list[str]:
    avoid = ["Do not bypass approval gates.", "Do not mix unrelated cleanup into the change."]
    if risk_level in {"high", "dangerous_architectural_change"}:
        avoid.append("Avoid broad rewrites until the first safe slice validates.")
    if drift.get("level") in {"moderate", "high"}:
        avoid.append("Avoid adding new dependencies between already-coupled systems.")
    return avoid
