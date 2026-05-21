from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .knowledge import knowledge_graph
from .memory import ProjectMemory, utc_now
from .personal_memory import compact_memory_summary, memory_orchestration_context
from .quality import quality_dashboard
from .safety import is_safe_to_read
from .tasks import ACTIVE_STATUSES, list_tasks
from .validation import validation_summary
from .workspace import SOURCE_CODE_SUFFIXES, WorkspaceScanner


PERSONAL_PROFILE_FILE = "personal-engineering-profile.json"
PROFILE_VERSION = "2026.05.09"

SECRET_PREF_TERMS = {"key", "token", "secret", "password", "credential", "apikey", "api_key", "bearer", "private_key"}


class PersonalIntelligencePersistenceError(RuntimeError):
    """Raised when local personal engineering profile memory cannot be persisted."""


def adaptive_personal_intelligence(
    workspace: str | Path,
    *,
    project_roots: list[str] | None = None,
    preferences: dict[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Build local, inspectable personal engineering intelligence for a workspace.

    The default call is read-only. Profile persistence is opt-in through
    ``persist=True`` or by providing explicit user preferences.
    """

    root = Path(workspace).resolve()
    primary = _project_snapshot(root)
    additional = [_safe_project_snapshot(Path(item).resolve()) for item in (project_roots or [])[:8]]
    projects = [primary, *[item for item in additional if item.get("available")]]
    unavailable = [item for item in additional if not item.get("available")]
    memory = ProjectMemory(root)
    stored_profile = _load_profile(memory)
    explicit_preferences = _sanitize_preferences(preferences or {})
    stored_preferences = stored_profile.get("preferences") if isinstance(stored_profile.get("preferences"), dict) else {}
    merged_preferences = _deep_merge(stored_preferences, explicit_preferences)

    learned_signals = _learn_workflow(projects, merged_preferences)
    coding_style = _coding_style(projects, learned_signals)
    project_patterns = _project_patterns(projects, unavailable)
    habits = _engineering_habits(primary)
    workflow = _workflow_optimization(primary, project_patterns, habits, merged_preferences)
    context = _context_personalization(primary, learned_signals, habits, merged_preferences)
    memory_system = _memory_system_summary(root, context)
    recommendations = _personalized_recommendations(primary, learned_signals, project_patterns, habits, workflow, context)

    profile_path = memory.root / PERSONAL_PROFILE_FILE
    updated_profile = False
    if persist or explicit_preferences:
        profile = {
            "version": PROFILE_VERSION,
            "workspace": str(root),
            "updated_at": utc_now(),
            "preferences": merged_preferences,
            "learned_snapshot": _compact_learned_snapshot(learned_signals, coding_style, project_patterns, habits, context),
            "privacy": _privacy_controls(profile_path),
        }
        stored_profile = _persist_profile(memory, profile)
        updated_profile = True

    persisted = profile_path.is_file()
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "profile_version": PROFILE_VERSION,
        "preference_memory": {
            "profile_path": str(profile_path),
            "persisted": persisted,
            "updated": updated_profile,
            "last_updated": stored_profile.get("updated_at"),
            "stored_preferences": merged_preferences,
            "rejected_preference_terms": sorted(SECRET_PREF_TERMS),
            "controls": {
                "inspectable": True,
                "resettable": True,
                "user_controlled": True,
                "reset_endpoint": "/v1/personal-intelligence/reset",
                "persist_requires_explicit_request": True,
            },
        },
        "learned_signals": learned_signals,
        "coding_style_awareness": coding_style,
        "project_pattern_recognition": project_patterns,
        "personalized_recommendations": recommendations,
        "engineering_habit_analysis": habits,
        "workflow_optimization": workflow,
        "context_personalization": context,
        "agent_guidance": _agent_guidance(learned_signals, habits, context),
        "memory_system": memory_system,
        "privacy": _privacy_controls(profile_path),
    }


def reset_personal_intelligence(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    profile_path = ProjectMemory(root).root / PERSONAL_PROFILE_FILE
    exists = profile_path.exists()
    if exists and not profile_path.is_file():
        return {
            "workspace": str(root),
            "reset": False,
            "profile_path": str(profile_path),
            "existed": True,
            "error": scrub(f"Could not reset personal engineering profile because {profile_path} is not a file."),
            "privacy": _privacy_controls(profile_path),
        }
    existed = profile_path.is_file()
    if existed:
        try:
            profile_path.unlink()
        except OSError as exc:
            return {
                "workspace": str(root),
                "reset": False,
                "profile_path": str(profile_path),
                "error": scrub(str(exc)),
                "privacy": _privacy_controls(profile_path),
            }
    return {
        "workspace": str(root),
        "reset": True,
        "profile_path": str(profile_path),
        "existed": existed,
        "privacy": _privacy_controls(profile_path),
    }


def _project_snapshot(root: Path) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=False)
    try:
        quality = quality_dashboard(root, scan=scan)
    except Exception as exc:  # pragma: no cover - defensive data boundary.
        quality = {"error": scrub(str(exc))}
    try:
        graph = knowledge_graph(root, scan=scan)
    except Exception as exc:  # pragma: no cover - defensive data boundary.
        graph = {"error": scrub(str(exc)), "nodes": [], "edges": [], "clusters": []}
    try:
        validation = validation_summary(root)
    except Exception as exc:  # pragma: no cover - defensive data boundary.
        validation = {"commands": [], "error": scrub(str(exc))}
    try:
        tasks = list_tasks(root)
    except Exception:
        tasks = []
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
        "memory": _memory_texts(memory),
        "style": _style_snapshot(root, scan),
    }


def _safe_project_snapshot(root: Path) -> dict[str, Any]:
    if not root.exists() or not root.is_dir():
        return {"available": False, "workspace": str(root), "reason": "not a readable project directory"}
    try:
        return _project_snapshot(root)
    except Exception as exc:  # pragma: no cover - defensive per-project boundary.
        return {"available": False, "workspace": str(root), "reason": scrub(str(exc))}


def _learn_workflow(projects: list[dict[str, Any]], preferences: dict[str, Any]) -> dict[str, Any]:
    top_dirs: Counter[str] = Counter()
    frameworks: Counter[str] = Counter()
    validation: Counter[str] = Counter()
    lifecycle_signals: Counter[str] = Counter()
    file_names: list[str] = []
    symbols: list[str] = []
    for project in projects:
        scan = project.get("scan", {})
        frameworks.update(str(item) for item in scan.get("frameworks", []) if item)
        for path in _scan_paths(scan):
            normalized = path.replace("\\", "/").strip("/")
            if "/" in normalized:
                top_dirs[normalized.split("/", 1)[0]] += 1
            file_names.append(Path(normalized).stem)
        for entries in (scan.get("symbol_index") or {}).values():
            if isinstance(entries, list):
                symbols.extend(str(item.get("name")) for item in entries if isinstance(item, dict) and item.get("name"))
        for command in project.get("validation", {}).get("commands", []) if isinstance(project.get("validation"), dict) else []:
            validation[str(command.get("name") or " ".join(command.get("command") or []))] += 1
        lifecycle_signals[_infer_project_stage(project)] += 1

    return {
        "preferred_project_structures": _counter_items(top_dirs, 10),
        "preferred_frameworks": _counter_items(frameworks, 10),
        "preferred_naming_conventions": _naming_conventions(file_names, symbols),
        "preferred_architecture_styles": _architecture_styles(projects),
        "preferred_validation_workflows": _counter_items(validation, 8),
        "preferred_task_ordering": _task_ordering(projects),
        "observed_project_stages": _counter_items(lifecycle_signals, 5),
        "explicit_preferences": preferences,
        "confidence": _confidence(projects, frameworks, validation),
    }


def _coding_style(projects: list[dict[str, Any]], learned: dict[str, Any]) -> dict[str, Any]:
    aggregate = defaultdict(int)
    suffixes: Counter[str] = Counter()
    service_symbols: Counter[str] = Counter()
    ui_patterns: Counter[str] = Counter()
    architecture_decisions: list[str] = []
    for project in projects:
        style = project.get("style", {})
        for key, value in style.items():
            if isinstance(value, int):
                aggregate[key] += value
        suffixes.update(style.get("suffix_counts", {}))
        service_symbols.update(style.get("service_suffixes", {}))
        ui_patterns.update(style.get("ui_patterns", {}))
        architecture_decisions.extend(_decision_lines(project.get("memory", {}).get("decisions_text", "")))

    line_count = max(1, aggregate["line_count"])
    comment_ratio = round(aggregate["comment_lines"] / line_count, 3)
    indentation = "spaces" if aggregate["space_indents"] >= aggregate["tab_indents"] else "tabs"
    if aggregate["space_indents"] and aggregate["tab_indents"]:
        indentation = "mixed"
    semicolon_ratio = aggregate["semicolon_lines"] / line_count
    if semicolon_ratio >= 0.25:
        semicolon_style = "common"
    elif semicolon_ratio > 0.02:
        semicolon_style = "occasional"
    else:
        semicolon_style = "rare"

    return {
        "formatting_tendencies": {
            "indentation": indentation,
            "semicolon_style": semicolon_style,
            "long_line_ratio": round(aggregate["long_lines"] / line_count, 3),
            "dominant_suffixes": _counter_items(suffixes, 8),
        },
        "abstraction_preferences": {
            "service_like_symbols": _counter_items(service_symbols, 8),
            "function_count": aggregate["function_count"],
            "class_count": aggregate["class_count"],
            "guidance": _abstraction_guidance(aggregate, service_symbols),
        },
        "commenting_style": {
            "comment_ratio": comment_ratio,
            "style": "sparse" if comment_ratio < 0.04 else "pragmatic" if comment_ratio < 0.14 else "comment_heavy",
            "todo_or_fixme_count": aggregate["todo_lines"],
        },
        "error_handling_style": {
            "try_or_catch_count": aggregate["try_count"] + aggregate["catch_count"],
            "guard_clause_count": aggregate["guard_count"],
            "style": _error_style(aggregate),
        },
        "ui_layout_patterns": _counter_items(ui_patterns, 8),
        "architecture_decisions": architecture_decisions[:10],
        "consistency_guidance": _style_guidance(learned, aggregate, comment_ratio),
    }


def _project_patterns(projects: list[dict[str, Any]], unavailable: list[dict[str, Any]]) -> dict[str, Any]:
    systems: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    frameworks: Counter[str] = Counter()
    validation_commands: Counter[str] = Counter()
    for project in projects:
        detected = _detect_recurring_systems(project)
        for name, paths in detected.items():
            systems[name] += 1
            evidence[name].extend(paths[:4])
        frameworks.update(str(item) for item in project.get("scan", {}).get("frameworks", []) if item)
        for command in project.get("validation", {}).get("commands", []) if isinstance(project.get("validation"), dict) else []:
            validation_commands[str(command.get("name") or " ".join(command.get("command") or []))] += 1

    recurring_threshold = 2 if len(projects) > 1 else 1
    recurring_systems = [
        {"system": name, "project_count": count, "evidence": _dedupe(evidence[name])[:8]}
        for name, count in systems.most_common()
        if count >= recurring_threshold
    ]
    return {
        "projects_analyzed": [{"workspace": item["workspace"], "name": item["workspace_name"]} for item in projects],
        "unavailable_projects": unavailable,
        "recurring_systems": recurring_systems[:12],
        "shared_frameworks": _counter_items(frameworks, 10, minimum=recurring_threshold),
        "shared_validation_workflows": _counter_items(validation_commands, 8, minimum=recurring_threshold),
        "suggested_templates": _suggested_templates(recurring_systems, frameworks, validation_commands),
    }


def _engineering_habits(project: dict[str, Any]) -> dict[str, Any]:
    scan = project.get("scan", {})
    quality = project.get("quality", {})
    current = quality.get("current_snapshot", {}) if isinstance(quality.get("current_snapshot"), dict) else {}
    tasks = project.get("tasks", [])
    active = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
    warnings = quality.get("warnings", []) if isinstance(quality.get("warnings"), list) else []
    habits = {
        "recurring_bottlenecks": [],
        "repeated_mistakes": [],
        "overengineering_signals": [],
        "unfinished_tasks": [],
        "unstable_modules": [],
        "ignored_warnings": [],
        "gentle_suggestions": [],
    }

    if not project.get("validation", {}).get("commands"):
        habits["recurring_bottlenecks"].append({"title": "Validation discovery is manual", "severity": "medium"})
    if current.get("slow_validation_commands"):
        habits["recurring_bottlenecks"].append({"title": "Validation commands are slow", "severity": "medium", "evidence": current["slow_validation_commands"][:5]})
    if current.get("repeated_repair_attempts", 0) >= 2:
        habits["repeated_mistakes"].append({"title": "Repair loops are recurring", "severity": "medium"})
    if current.get("repeated_model_failures", 0) >= 2:
        habits["repeated_mistakes"].append({"title": "Model/Ollama failures recur", "severity": "medium"})
    if len(scan.get("todo_comments", [])) >= 5:
        habits["unfinished_tasks"].append({"title": "TODO/FIXME backlog needs triage", "count": len(scan.get("todo_comments", []))})
    if active:
        habits["unfinished_tasks"].append({"title": "Active task queue has open work", "count": len(active)})
    for item in quality.get("high_risk_files", [])[:5] if isinstance(quality.get("high_risk_files"), list) else []:
        habits["unstable_modules"].append({"title": item.get("path"), "score": item.get("score"), "reasons": item.get("reasons", [])})
    for item in project.get("knowledge", {}).get("unstable_modules", [])[:5] if isinstance(project.get("knowledge"), dict) else []:
        habits["unstable_modules"].append({"title": item.get("system"), "weight": item.get("weight")})
    symbols = scan.get("symbol_index", {}) if isinstance(scan.get("symbol_index"), dict) else {}
    service_like = sum(
        1
        for entries in symbols.values()
        if isinstance(entries, list)
        for item in entries
        if isinstance(item, dict) and str(item.get("name", "")).endswith(("Service", "Manager", "Provider", "Coordinator", "Orchestrator"))
    )
    file_count = max(1, int(scan.get("file_count") or 1))
    if service_like >= 8 and service_like / file_count > 0.18:
        habits["overengineering_signals"].append({"title": "Many service-like abstractions relative to project size", "count": service_like})
    habits["ignored_warnings"].extend({"title": str(warning)} for warning in warnings[:8])
    habits["gentle_suggestions"] = _habit_suggestions(habits)
    return habits


def _workflow_optimization(
    project: dict[str, Any],
    patterns: dict[str, Any],
    habits: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    validation_commands = project.get("validation", {}).get("commands", []) if isinstance(project.get("validation"), dict) else []
    opportunities: list[dict[str, Any]] = []
    if habits["recurring_bottlenecks"] and validation_commands:
        opportunities.append({"title": "Run validation earlier in each task", "reason": "Bottlenecks are visible and validation is detectable."})
    if patterns.get("suggested_templates"):
        opportunities.append({"title": "Promote repeated patterns into documented templates", "reason": "Multiple projects share systems or workflows."})
    if habits["unfinished_tasks"]:
        opportunities.append({"title": "Add a short task-pruning pass before new scope", "reason": "Open work is accumulating."})
    if preferences.get("safety_level") in {"high", "strict"}:
        opportunities.append({"title": "Keep approval gates strict for edits and commands", "reason": "Stored safety preference favors conservative workflows."})

    return {
        "automation_opportunities": opportunities[:8],
        "reusable_abstractions": patterns.get("suggested_templates", [])[:8],
        "validation_timing": _validation_timing(project, habits),
        "task_sequencing": _task_sequence(project, habits),
        "architecture_cleanup_timing": _cleanup_timing(project, habits),
    }


def _context_personalization(
    project: dict[str, Any],
    learned: dict[str, Any],
    habits: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    quality = project.get("quality", {})
    risk_count = len(quality.get("top_risks", [])) if isinstance(quality.get("top_risks"), list) else 0
    planning_depth = str(preferences.get("planning_depth") or "").strip().lower()
    if planning_depth not in {"concise", "balanced", "deep"}:
        planning_depth = "deep" if risk_count >= 3 or habits["unstable_modules"] else "balanced"
    validation_detail = str(preferences.get("validation_detail") or "").strip().lower()
    if validation_detail not in {"brief", "standard", "detailed"}:
        validation_detail = "detailed" if _validation_is_failing(project) or habits["recurring_bottlenecks"] else "standard"
    summary_style = str(preferences.get("summary_style") or "decision-first").strip() or "decision-first"
    roadmap_priority = "validation and risk first" if _validation_is_failing(project) or habits["unstable_modules"] else "small validated improvements"
    return {
        "roadmap_generation": {
            "priority": roadmap_priority,
            "preferred_task_granularity": "small staged tasks" if learned.get("confidence", 0) >= 45 else "conservative staged tasks",
        },
        "diff_explanations": {
            "style": "file-by-file with risk notes" if habits["unstable_modules"] else "concise summary plus validation",
            "include_rollback_notes": True,
        },
        "planning_depth": planning_depth,
        "summaries": {
            "style": summary_style,
            "include_validation": True,
            "include_remaining_risk": True,
        },
        "validation_detail": validation_detail,
        "preferred_models": preferences.get("preferred_models", {}),
        "safety_level": preferences.get("safety_level", "approval-gated"),
    }


def _personalized_recommendations(
    project: dict[str, Any],
    learned: dict[str, Any],
    patterns: dict[str, Any],
    habits: dict[str, Any],
    workflow: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if _validation_is_failing(project):
        recommendations.append({"title": "Prioritize the latest validation failure before new scope", "priority": "high", "reason": "Personalized planning keeps trust and build health ahead of feature work."})
    for item in habits.get("unfinished_tasks", [])[:1]:
        recommendations.append({"title": item.get("title"), "priority": "medium", "reason": "Open work is visible in local tasks or TODOs."})
    if patterns.get("suggested_templates"):
        template = patterns["suggested_templates"][0]
        recommendations.append({"title": template["title"], "priority": "low", "reason": template["reason"]})
    if workflow.get("automation_opportunities"):
        item = workflow["automation_opportunities"][0]
        recommendations.append({"title": item["title"], "priority": "medium", "reason": item["reason"]})
    if context.get("planning_depth") == "deep":
        recommendations.append({"title": "Use deeper planning on risky changes", "priority": "medium", "reason": "Detected risk signals make short plans more fragile."})
    if not recommendations:
        recommendations.append({"title": "Continue with small, validated improvements", "priority": "low", "reason": "No urgent personal workflow risk was detected."})
    return _dedupe_dicts(recommendations)[:8]


def _agent_guidance(learned: dict[str, Any], habits: dict[str, Any], context: dict[str, Any]) -> list[str]:
    guidance = [
        f"Use {context.get('planning_depth', 'balanced')} planning depth for this workspace.",
        f"Validation summaries should be {context.get('validation_detail', 'standard')}.",
    ]
    if learned.get("preferred_validation_workflows"):
        guidance.append("Prefer detected validation workflows before inventing new commands.")
    if habits.get("unstable_modules"):
        guidance.append("Warn before editing unstable modules and split risky tasks into smaller approvals.")
    if habits.get("overengineering_signals"):
        guidance.append("Favor simpler structures unless an abstraction clearly removes repeated complexity.")
    return guidance[:6]


def _memory_system_summary(root: Path, context: dict[str, Any]) -> dict[str, Any]:
    summary = compact_memory_summary(root)
    try:
        orchestration = memory_orchestration_context(
            root,
            workflow_type="personal_intelligence",
            objective=f"{context.get('planning_depth', '')} {context.get('validation_detail', '')}",
            max_items=8,
            record_usage=False,
        )
    except Exception as exc:  # pragma: no cover - defensive profile boundary.
        orchestration = {"records": [], "guidance": [], "error": scrub(str(exc))}
    return {
        "summary": summary,
        "orchestration_context": {
            "record_count": len(orchestration.get("records", [])),
            "guidance": orchestration.get("guidance", []),
            "privacy": orchestration.get("privacy", {}),
            "error": orchestration.get("error"),
        },
        "management_endpoints": {
            "dashboard": "/v1/personal-memory",
            "create": "/v1/personal-memory",
            "controls": "/v1/personal-memory/controls",
            "export": "/v1/personal-memory/export",
            "import": "/v1/personal-memory/import",
        },
    }


def _style_snapshot(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    paths = [path for path in _scan_paths(scan) if Path(path).suffix.lower() in SOURCE_CODE_SUFFIXES]
    paths = _dedupe(paths)[:120]
    counts = defaultdict(int)
    suffix_counts: Counter[str] = Counter()
    service_suffixes: Counter[str] = Counter()
    ui_patterns: Counter[str] = Counter()
    symbols = scan.get("symbol_index", {}) if isinstance(scan.get("symbol_index"), dict) else {}
    for path in paths:
        full = (root / path).resolve()
        if not is_safe_to_read(full, root) or not full.is_file():
            continue
        text = _read_text(full)
        if not text:
            continue
        suffix_counts[Path(path).suffix.lower()] += 1
        lowered_path = path.lower()
        if any(token in lowered_path for token in ("component", "page", "view", "xaml", "frontend", "ui")):
            ui_patterns[_ui_pattern_for_path(path)] += 1
        for line in text.splitlines():
            counts["line_count"] += 1
            stripped = line.strip()
            if not stripped:
                counts["blank_lines"] += 1
            if line.startswith("\t"):
                counts["tab_indents"] += 1
            if re.match(r"^ {2,}\S", line):
                counts["space_indents"] += 1
            if len(line) >= 100:
                counts["long_lines"] += 1
            if stripped.endswith(";"):
                counts["semicolon_lines"] += 1
            if stripped.startswith(("#", "//", "/*", "*")):
                counts["comment_lines"] += 1
            if "todo" in stripped.lower() or "fixme" in stripped.lower():
                counts["todo_lines"] += 1
            if re.search(r"\b(try|except|catch|throw|raise)\b", line):
                if re.search(r"\btry\b", line):
                    counts["try_count"] += 1
                if re.search(r"\b(except|catch|throw|raise)\b", line):
                    counts["catch_count"] += 1
            if re.search(r"\bif\s+.*(?:return|throw|raise|continue|break)\b", line):
                counts["guard_count"] += 1
    for entries in symbols.values():
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "")
            name = str(item.get("name") or "")
            if kind == "function":
                counts["function_count"] += 1
            if kind == "class":
                counts["class_count"] += 1
            for suffix in ("Service", "Manager", "Provider", "Controller", "Repository", "Store", "Router", "Orchestrator"):
                if name.endswith(suffix):
                    service_suffixes[suffix] += 1
    return {
        **dict(counts),
        "suffix_counts": dict(suffix_counts),
        "service_suffixes": dict(service_suffixes),
        "ui_patterns": dict(ui_patterns),
    }


def _scan_paths(scan: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("build_files", "readmes", "test_files", "entry_points", "recent_files"):
        paths.extend(str(item) for item in scan.get(key, []) if item)
    if isinstance(scan.get("dependency_graph"), dict):
        paths.extend(str(item) for item in scan["dependency_graph"].get("files", {}).keys())
    if isinstance(scan.get("symbol_index"), dict):
        paths.extend(str(item) for item in scan["symbol_index"].keys())
    for item in scan.get("todo_comments", []) if isinstance(scan.get("todo_comments"), list) else []:
        if isinstance(item, dict) and item.get("file"):
            paths.append(str(item["file"]))
    return _dedupe(path.replace("\\", "/").lstrip("./") for path in paths if path)


def _detect_recurring_systems(project: dict[str, Any]) -> dict[str, list[str]]:
    systems: dict[str, list[str]] = defaultdict(list)
    patterns = {
        "auth": ("auth", "login", "session", "identity", "user"),
        "api": ("api", "route", "router", "controller", "endpoint", "/v1", "/api"),
        "ui": ("component", "page", "view", "xaml", "frontend", "ui"),
        "agent": ("agent", "planner", "orchestration", "repair", "roadmap"),
        "roadmap": ("roadmap", "milestone", "planning"),
        "save_or_persistence": ("save", "storage", "persistence", "repository", "memory"),
        "validation": ("validation", "test", "build", "lint", "pytest", "vitest"),
        "settings": ("config", "settings", "options"),
        "model_runtime": ("model", "ollama", "provider", "embedding"),
    }
    for path in _scan_paths(project.get("scan", {})):
        lowered = path.lower()
        for system, tokens in patterns.items():
            if any(token in lowered for token in tokens):
                systems[system].append(path)
    for node in project.get("knowledge", {}).get("nodes", []) if isinstance(project.get("knowledge"), dict) else []:
        if not isinstance(node, dict):
            continue
        text = f"{node.get('label', '')} {node.get('path', '')}".lower()
        for system, tokens in patterns.items():
            if any(token in text for token in tokens):
                systems[system].append(str(node.get("path") or node.get("label") or system))
    return {key: _dedupe(value) for key, value in systems.items()}


def _suggested_templates(
    recurring_systems: list[dict[str, Any]],
    frameworks: Counter[str],
    validation_commands: Counter[str],
) -> list[dict[str, Any]]:
    names = {item["system"] for item in recurring_systems}
    templates: list[dict[str, Any]] = []
    if "api" in names:
        templates.append({"title": "Create a reusable API adapter checklist", "category": "api", "reason": "API route/client patterns recur across local projects."})
    if "validation" in names or validation_commands:
        templates.append({"title": "Document a shared validation profile", "category": "validation", "reason": "Validation workflows recur and can be easier to run consistently."})
    if "agent" in names:
        templates.append({"title": "Keep agent workflow scaffolding documented", "category": "agent", "reason": "Planner/agent systems recur in this ecosystem."})
    if "save_or_persistence" in names:
        templates.append({"title": "Extract a persistence safety checklist", "category": "persistence", "reason": "Save, memory, or repository flows repeat across projects."})
    if any(name in frameworks for name in ("React", "Vite", "C#/.NET", "F#/.NET", "VB.NET", "Unity")):
        templates.append({"title": "Record framework setup conventions", "category": "onboarding", "reason": "Framework preferences are visible across local workspaces."})
    return _dedupe_dicts(templates)


def _task_ordering(projects: list[dict[str, Any]]) -> dict[str, Any]:
    active_count = 0
    validation_configured = False
    failing_validation = False
    todo_count = 0
    for project in projects:
        active_count += len([task for task in project.get("tasks", []) if task.get("status") in ACTIVE_STATUSES])
        validation_configured = validation_configured or bool(project.get("validation", {}).get("commands"))
        failing_validation = failing_validation or _validation_is_failing(project)
        todo_count += len(project.get("scan", {}).get("todo_comments", []))
    order = ["inspect", "plan", "validate", "change", "document"]
    if failing_validation:
        order = ["inspect latest failure", "repair minimally", "validate", "document", "resume roadmap"]
    elif active_count or todo_count >= 5:
        order = ["triage open work", "choose smallest safe task", "validate", "document"]
    elif not validation_configured:
        order = ["inspect", "document validation path", "plan", "change"]
    return {
        "recommended_order": order,
        "active_task_count": active_count,
        "validation_configured": validation_configured,
        "validation_failing": failing_validation,
    }


def _architecture_styles(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    styles: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    for project in projects:
        scan = project.get("scan", {})
        paths = _scan_paths(scan)
        symbols = scan.get("symbol_index", {}) if isinstance(scan.get("symbol_index"), dict) else {}
        if any("api" in path.lower() or "router" in path.lower() for path in paths):
            styles["api-oriented service boundary"] += 1
            evidence["api-oriented service boundary"].extend(path for path in paths if "api" in path.lower() or "router" in path.lower())
        if any(any(str(item.get("name", "")).endswith(("Service", "Manager", "Provider")) for item in entries if isinstance(item, dict)) for entries in symbols.values() if isinstance(entries, list)):
            styles["service-layer abstractions"] += 1
        if any("component" in path.lower() or path.endswith((".tsx", ".jsx", ".xaml")) for path in paths):
            styles["component-based UI"] += 1
        if (Path(project["workspace"]) / ".aegis").exists():
            styles["local-first project memory"] += 1
    return [{"style": name, "count": count, "evidence": _dedupe(evidence[name])[:6]} for name, count in styles.most_common(8)]


def _naming_conventions(file_names: list[str], symbols: list[str]) -> dict[str, Any]:
    file_counter = Counter(_naming_style(name) for name in file_names if name)
    symbol_counter = Counter(_symbol_style(name) for name in symbols if name)
    return {
        "file_names": _counter_items(file_counter, 6),
        "symbols": _counter_items(symbol_counter, 6),
        "recommended_consistency": _dominant(file_counter) or _dominant(symbol_counter) or "existing local style",
    }


def _memory_texts(memory: ProjectMemory) -> dict[str, str]:
    return {
        "roadmap_text": _read_text(memory.root / "roadmap.md"),
        "decisions_text": _read_text(memory.root / "decisions.md"),
        "known_issues_text": _read_text(memory.root / "known-issues.md"),
        "validation_log_text": _read_text(memory.root / "validation-log.md"),
    }


def _privacy_controls(profile_path: Path) -> dict[str, Any]:
    return {
        "local_first": True,
        "cloud_calls": False,
        "stores_source_content": False,
        "stores_secrets": False,
        "profile_path": str(profile_path),
        "transparent": True,
        "inspectable": True,
        "resettable": True,
        "user_controlled": True,
        "notes": [
            "The default intelligence scan is read-only.",
            "Profile persistence is explicit and local to the workspace .aegis directory.",
            "Secret-like preference keys are rejected and source file contents are summarized, not stored.",
        ],
    }


def _compact_learned_snapshot(
    learned: dict[str, Any],
    coding_style: dict[str, Any],
    patterns: dict[str, Any],
    habits: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "preferred_frameworks": learned.get("preferred_frameworks", [])[:8],
        "preferred_validation_workflows": learned.get("preferred_validation_workflows", [])[:8],
        "architecture_styles": learned.get("preferred_architecture_styles", [])[:8],
        "formatting_tendencies": coding_style.get("formatting_tendencies", {}),
        "recurring_systems": patterns.get("recurring_systems", [])[:8],
        "habit_suggestions": habits.get("gentle_suggestions", [])[:8],
        "context_personalization": context,
    }


def _load_profile(memory: ProjectMemory) -> dict[str, Any]:
    path = memory.root / PERSONAL_PROFILE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _persist_profile(memory: ProjectMemory, profile: dict[str, Any]) -> dict[str, Any]:
    path = memory.root / PERSONAL_PROFILE_FILE
    _ensure_profile_target(path)
    memory.write_json(PERSONAL_PROFILE_FILE, profile)
    persisted = _load_profile(memory)
    if persisted != profile:
        raise PersonalIntelligencePersistenceError(
            f"Could not persist personal engineering profile at {path}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    return persisted


def _ensure_profile_target(path: Path) -> None:
    if path.parent.exists() and not path.parent.is_dir():
        raise PersonalIntelligencePersistenceError(
            f"Could not persist personal engineering profile because {path.parent} is not a directory."
        )
    if path.exists() and not path.is_file():
        raise PersonalIntelligencePersistenceError(
            f"Could not persist personal engineering profile because {path} is not a writable file."
        )


def _sanitize_preferences(value: Any, key_path: str = "") -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_secret_preference_key(key_text):
                continue
            sanitized[key_text] = _sanitize_preferences(child, f"{key_path}.{key_text}" if key_path else key_text)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_preferences(item, key_path) for item in value[:50]]
    if isinstance(value, str):
        return scrub(value)[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return scrub(str(value))[:500]


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_secret_preference_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    tokens = {token for token in normalized.split("_") if token}
    if normalized in SECRET_PREF_TERMS:
        return True
    if tokens.intersection({"token", "secret", "password", "credential", "apikey", "bearer"}):
        return True
    if {"api", "key"}.issubset(tokens) or {"private", "key"}.issubset(tokens):
        return True
    return False


def _infer_project_stage(project: dict[str, Any]) -> str:
    quality = project.get("quality", {})
    score = int(quality.get("score") or 0)
    scan = project.get("scan", {})
    if _validation_is_failing(project) or score < 60:
        return "stabilization"
    if scan.get("file_count", 0) < 12 and not scan.get("test_files"):
        return "prototype"
    if score >= 85 and scan.get("test_files"):
        return "release_candidate"
    return "active_development"


def _validation_is_failing(project: dict[str, Any]) -> bool:
    statuses = project.get("quality", {}).get("statuses", {}) if isinstance(project.get("quality"), dict) else {}
    for key in ("build", "test", "lint", "validation"):
        status = statuses.get(key)
        if isinstance(status, dict) and status.get("status") == "failed":
            return True
    return False


def _validation_timing(project: dict[str, Any], habits: dict[str, Any]) -> str:
    if _validation_is_failing(project):
        return "validate immediately before continuing roadmap work"
    if habits.get("unstable_modules"):
        return "validate after each approved risky change"
    if project.get("validation", {}).get("commands"):
        return "validate after each focused task"
    return "document or configure a validation path first"


def _task_sequence(project: dict[str, Any], habits: dict[str, Any]) -> list[str]:
    if _validation_is_failing(project):
        return ["repair failing validation", "run approved validation", "record decision", "resume smallest roadmap task"]
    if habits.get("unfinished_tasks"):
        return ["triage open work", "choose one small task", "validate", "document"]
    return ["inspect", "plan", "propose", "approve", "validate", "summarize"]


def _cleanup_timing(project: dict[str, Any], habits: dict[str, Any]) -> str:
    if habits.get("overengineering_signals"):
        return "schedule cleanup before adding adjacent abstractions"
    if habits.get("unstable_modules"):
        return "schedule cleanup after stabilizing the riskiest module"
    if len(project.get("scan", {}).get("todo_comments", [])) >= 5:
        return "schedule a short TODO triage pass this week"
    return "fold cleanup into normal small-task validation"


def _habit_suggestions(habits: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if habits["recurring_bottlenecks"]:
        suggestions.append("Keep the next task small enough to validate quickly.")
    if habits["repeated_mistakes"]:
        suggestions.append("Pause repair loops after limited attempts and re-plan from fresh diagnostics.")
    if habits["overengineering_signals"]:
        suggestions.append("Prefer one clear module boundary before introducing another abstraction.")
    if habits["unfinished_tasks"]:
        suggestions.append("Convert lingering TODOs or active tasks into a short prioritized queue.")
    if habits["unstable_modules"]:
        suggestions.append("Treat unstable modules as higher risk and add validation before broad edits.")
    return suggestions or ["Current workflow signals look healthy; keep using small, validated changes."]


def _style_guidance(learned: dict[str, Any], aggregate: dict[str, int], comment_ratio: float) -> list[str]:
    guidance = []
    naming = learned.get("preferred_naming_conventions", {}).get("recommended_consistency")
    if naming:
        guidance.append(f"Match existing {naming} naming where practical.")
    if comment_ratio < 0.04:
        guidance.append("Keep comments sparse and reserve them for non-obvious decisions.")
    else:
        guidance.append("Use comments to explain intent, not line-by-line mechanics.")
    if aggregate.get("guard_count", 0) >= aggregate.get("try_count", 0):
        guidance.append("Favor clear guard clauses and explicit validation around risky inputs.")
    return guidance[:5]


def _abstraction_guidance(aggregate: dict[str, int], service_symbols: Counter[str]) -> str:
    service_count = sum(service_symbols.values())
    if service_count >= 8 and aggregate.get("function_count", 0) < service_count:
        return "Service-style abstractions are common; add new ones only when they reduce real duplication."
    if aggregate.get("function_count", 0) > aggregate.get("class_count", 0) * 3:
        return "Function-focused code is common; keep new abstractions lightweight."
    return "Follow the local module boundary and avoid new layers without clear payoff."


def _error_style(aggregate: dict[str, int]) -> str:
    if aggregate.get("guard_count", 0) >= max(2, aggregate.get("try_count", 0)):
        return "guard-clause oriented"
    if aggregate.get("try_count", 0) + aggregate.get("catch_count", 0) >= 4:
        return "explicit exception handling"
    return "lightweight or not yet visible"


def _decision_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        cleaned = line.strip("- ").strip()
        if not cleaned:
            continue
        if cleaned.startswith("What changed:") or cleaned.startswith("Validation:") or line.startswith("## "):
            lines.append(scrub(cleaned)[:220])
    return lines


def _ui_pattern_for_path(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".xaml"):
        return "xaml tool windows"
    if lowered.endswith(".tsx"):
        return "react typescript components"
    if lowered.endswith(".jsx"):
        return "react javascript components"
    if "component" in lowered:
        return "component folders"
    if "page" in lowered:
        return "page routes"
    return "ui files"


def _naming_style(name: str) -> str:
    if "_" in name:
        return "snake_case"
    if "-" in name:
        return "kebab-case"
    if name and name[0].isupper():
        return "PascalCase"
    if re.search(r"[a-z][A-Z]", name):
        return "camelCase"
    return "lowercase"


def _symbol_style(name: str) -> str:
    if "_" in name:
        return "snake_case"
    if name and name[0].isupper():
        return "PascalCase"
    if re.search(r"[a-z][A-Z]", name):
        return "camelCase"
    return "lowercase"


def _confidence(projects: list[dict[str, Any]], frameworks: Counter[str], validation: Counter[str]) -> int:
    score = 20
    score += min(30, len(projects) * 10)
    score += min(20, sum(frameworks.values()) * 3)
    score += min(20, sum(validation.values()) * 5)
    score += min(10, sum(int(project.get("scan", {}).get("file_count") or 0) for project in projects) // 20)
    return max(10, min(95, score))


def _counter_items(counter: Counter[str], limit: int, *, minimum: int = 1) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit) if name and count >= minimum]


def _dominant(counter: Counter[str]) -> str | None:
    return counter.most_common(1)[0][0] if counter else None


def _dedupe(values: Any) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        key = json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _dedupe_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in _dedupe(values) if isinstance(item, dict)]


def _read_text(path: Path) -> str:
    try:
        return scrub(path.read_text(encoding="utf-8", errors="ignore")) if path.is_file() else ""
    except OSError:
        return ""
