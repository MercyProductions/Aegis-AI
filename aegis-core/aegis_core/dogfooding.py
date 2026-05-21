from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import redact_inline, scrub
from .memory import ProjectMemory, utc_now
from .product_identity import workflow_catalog


EVENT_FILE = "dogfooding-events.jsonl"
REPORT_FILE = "dogfooding-report.json"
SUMMARY_FILE = "dogfooding-summary.md"
MAX_EVENTS = 1000

FRICTION_LABELS = {
    "too_many_clicks": "Too many clicks",
    "confusing_terminology": "Confusing terminology",
    "duplicate_action": "Duplicate action",
    "unclear_approval": "Unclear approval",
    "noisy_panel": "Noisy panel",
    "workflow_dead_end": "Workflow dead end",
    "overwhelming_configuration": "Overwhelming configuration",
    "setup_friction": "Setup friction",
    "startup_slow": "Startup slow",
    "slow_workflow": "Slow workflow",
    "validation_pain": "Validation pain",
    "repair_loop": "Repair loop",
    "rollback_unclear": "Rollback unclear",
    "roadmap_unhelpful": "Roadmap unhelpful",
    "diff_unclear": "Diff unclear",
    "diagnostics_unclear": "Diagnostics unclear",
    "error_message_unclear": "Error message unclear",
    "onboarding_friction": "Onboarding friction",
    "model_routing_unclear": "Model routing unclear",
    "plugin_confusion": "Plugin confusion",
    "interrupted_stream": "Interrupted stream",
    "indexing_slow": "Indexing slow",
    "maintainability_drag": "Maintainability drag",
}

FRICTION_RECOMMENDATIONS = {
    "too_many_clicks": "Promote the next likely action and add keyboard shortcuts for repeat steps.",
    "confusing_terminology": "Use Auralith OS, Auralith Prime, Aegis Core, Workflow, Checkpoint, Validation, and Rollback consistently.",
    "duplicate_action": "Merge overlapping commands into one primary action with advanced options hidden.",
    "unclear_approval": "Show what is proposed, what is applied, what is blocked, and why approval is required.",
    "noisy_panel": "Collapse low-signal diagnostics behind details and keep the active workflow first.",
    "workflow_dead_end": "Always offer retry, revise, validate, rollback, or open logs after a failure.",
    "overwhelming_configuration": "Default to local-only Basic Local Assistant and reveal advanced settings progressively.",
    "setup_friction": "Add one-click retry/fix actions for Core, Ollama, provider, model, and workspace setup states.",
    "startup_slow": "Measure Core, Website, client, Ollama, and extension startup separately before changing architecture.",
    "slow_workflow": "Surface progress, duration, cancellation, and the next checkpoint during long operations.",
    "validation_pain": "Remember successful validation commands and recommend focused validation before broad checks.",
    "repair_loop": "Stop after bounded repair attempts and ask for user review with failure evidence.",
    "rollback_unclear": "Always show latest checkpoint, affected files, and restore outcome.",
    "roadmap_unhelpful": "Tie roadmap items to current scan evidence, validation state, risk, and the next smallest useful task.",
    "diff_unclear": "Group diffs by purpose, show new/existing file state, and explain why each path was chosen.",
    "diagnostics_unclear": "Put the failing subsystem, command, endpoint, or client first, then link to logs and retry actions.",
    "error_message_unclear": "Rewrite user-facing errors with the failing operation, likely cause, and next safe action.",
    "onboarding_friction": "Reduce first-run choices and show one recommended local path before advanced configuration.",
    "model_routing_unclear": "Explain selected model, fallback chain, local/cloud status, and missing capability warnings.",
    "plugin_confusion": "Group plugins by permission risk and show compatibility warnings before enablement.",
    "interrupted_stream": "Keep partial output, show the interruption reason, and offer resume or retry.",
    "indexing_slow": "Use incremental indexing, progress counts, and background refresh instead of blocking startup.",
    "maintainability_drag": "Prefer small module extraction, parity guards, and focused tests over broad rewrites.",
}


def dogfooding_workflows() -> dict[str, Any]:
    workflows = workflow_catalog()["workflows"]
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "workflows": [
            {
                "id": "feature_development",
                "title": "Feature development",
                "uses": ["open_workspace", "scan_project", "generate_roadmap", "implement_feature", "validate", "checkpoint"],
                "friction_to_watch": ["too_many_clicks", "unclear_approval", "slow_workflow", "diff_unclear"],
                "success_signal": "A small feature reaches validated proposed/applied state with clear rollback.",
            },
            {
                "id": "bug_fixing",
                "title": "Bug fixing",
                "uses": ["scan_project", "validate", "repair", "validate", "rollback"],
                "friction_to_watch": ["validation_pain", "repair_loop", "workflow_dead_end", "error_message_unclear"],
                "success_signal": "Failure evidence leads to one targeted fix or a clear stop condition.",
            },
            {
                "id": "roadmap_tracking",
                "title": "Roadmap tracking",
                "uses": ["scan_project", "generate_roadmap", "implement_feature", "validate"],
                "friction_to_watch": ["duplicate_action", "noisy_panel", "confusing_terminology", "roadmap_unhelpful"],
                "success_signal": "Roadmap item has visible status, linked checkpoint, and validation outcome.",
            },
            {
                "id": "deployment_validation",
                "title": "Deployment validation",
                "uses": ["scan_project", "deploy", "validate", "rollback"],
                "friction_to_watch": ["overwhelming_configuration", "workflow_dead_end", "unclear_approval", "rollback_unclear"],
                "success_signal": "CI/CD risk and rollback readiness are understandable without deploying production.",
            },
            {
                "id": "plugin_development",
                "title": "Plugin development",
                "uses": ["scan_project", "implement_feature", "validate", "checkpoint"],
                "friction_to_watch": ["plugin_confusion", "validation_pain", "rollback_unclear"],
                "success_signal": "Plugin manifest, permissions, compatibility, tests, and diagnostics are clear.",
            },
        ],
        "core_workflow_catalog": workflows,
        "dogfooding_rule": "Prefer real daily tasks and record friction when a workflow slows down, becomes unclear, or requires a workaround.",
    }


def record_dogfooding_event(
    workspace: str | Path,
    *,
    event_type: str,
    client_id: str = "unknown",
    client_type: str = "unknown",
    workflow_id: str = "",
    workflow_type: str = "",
    action: str = "",
    status: str = "observed",
    duration_ms: int | None = None,
    click_count: int | None = None,
    friction_tags: list[str] | None = None,
    interruption: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    tags = _normalize_friction_tags(friction_tags or [])
    inferred = _infer_friction(event_type, status, duration_ms, interruption)
    for tag in inferred:
        if tag not in tags:
            tags.append(tag)
    event = {
        "event_id": f"dogfood-{uuid.uuid4().hex[:12]}",
        "timestamp": utc_now(),
        "event_type": _safe_token(event_type, "workflow_event"),
        "client_id": _safe_token(client_id, "unknown"),
        "client_type": _safe_token(client_type, "unknown"),
        "workflow_id": scrub(workflow_id),
        "workflow_type": _safe_token(workflow_type, ""),
        "action": scrub(action),
        "status": _safe_token(status, "observed"),
        "duration_ms": _safe_int(duration_ms),
        "click_count": _safe_int(click_count),
        "friction_tags": tags,
        "interruption": scrub(interruption),
        "notes": redact_inline(notes)[:600],
        "metadata": _safe_metadata(metadata or {}),
    }
    _append_event(root, event)
    dashboard = dogfooding_dashboard(root, persist=True)
    return {"workspace": str(root), "event": event, "dashboard": dashboard}


def dogfooding_dashboard(workspace: str | Path, *, limit: int = 250, persist: bool = False) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    events = _read_events(root, limit=max(1, min(MAX_EVENTS, limit)))
    friction = friction_report(root, events=events)
    confidence = production_confidence(root, events=events)
    workflows = dogfooding_workflows()
    performance = _performance_summary(events)
    trust = _trust_summary(events)
    simplifications = _ux_simplifications(friction)
    priorities = _polish_priorities(friction, performance, confidence)
    result = {
        "schema_version": 1,
        "workspace": str(root),
        "generated_at": utc_now(),
        "event_count": len(events),
        "recent_events": events[:50],
        "workflows": workflows,
        "friction": friction,
        "confidence": confidence,
        "performance": performance,
        "trust": trust,
        "ux_simplifications": simplifications,
        "systems_to_simplify": systems_to_simplify(),
        "recommended_polish_priorities": priorities,
        "long_session_plan": long_session_plan(root),
        "state_files": _state_files(root),
    }
    if persist:
        memory = ProjectMemory(root)
        memory.write_json(REPORT_FILE, result)
        memory.write_generated_markdown(SUMMARY_FILE, "Auralith OS Dogfooding", _summary_markdown(result))
    return result


def friction_report(workspace: str | Path, *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    events = events if events is not None else _read_events(root)
    tag_counts: Counter[str] = Counter()
    workflow_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    for event in events:
        for tag in event.get("friction_tags", []) or []:
            tag_counts[tag] += 1
        if event.get("workflow_type"):
            workflow_counts[event["workflow_type"]] += len(event.get("friction_tags", []) or [])
        if event.get("action"):
            action_counts[event["action"]] += 1
    pain_points = [
        {
            "tag": tag,
            "label": FRICTION_LABELS.get(tag, tag.replace("_", " ").title()),
            "count": count,
            "recommendation": FRICTION_RECOMMENDATIONS.get(tag, "Review the recorded workflow and remove avoidable friction."),
        }
        for tag, count in tag_counts.most_common(12)
    ]
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "pain_points": pain_points,
        "workflow_hotspots": [{"workflow_type": key, "friction_count": value} for key, value in workflow_counts.most_common(10)],
        "repeated_actions": [{"action": key, "count": value} for key, value in action_counts.most_common(10) if value > 1],
        "abandoned_workflows": [event for event in events if event.get("status") in {"abandoned", "dead_end"}][:20],
        "local_only": True,
        "privacy": "Dogfooding events are stored locally under .aegis with notes and metadata redacted.",
    }


def production_confidence(workspace: str | Path, *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    events = events if events is not None else _read_events(root)
    statuses = Counter(event.get("status", "observed") for event in events)
    workflow_events = [event for event in events if event.get("event_type") in {"workflow", "workflow_completed", "workflow_failed", "workflow_abandoned"} or event.get("workflow_type")]
    validation_events = [event for event in events if "validation" in event.get("event_type", "") or event.get("workflow_type") == "validate"]
    rollback_events = [event for event in events if "rollback" in event.get("event_type", "") or event.get("workflow_type") == "rollback"]
    update_events = [event for event in events if "update" in event.get("event_type", "")]
    crash_events = [event for event in events if event.get("event_type") in {"crash", "startup_crash", "client_crash"} or event.get("status") == "crashed"]
    session_events = [event for event in events if event.get("event_type") in {"session_start", "session_end", "long_session"}]
    workflow_success = _rate(workflow_events, {"completed", "success", "validated", "passed", "restored"})
    validation_success = _rate(validation_events, {"passed", "success", "completed"})
    rollback_success = _rate(rollback_events, {"restored", "success", "completed"})
    update_success = _rate(update_events, {"success", "completed"})
    crash_free = 1.0 if not session_events and not crash_events else max(0.0, 1.0 - (len(crash_events) / max(1, len(session_events))))
    orchestration_stability = _rate(workflow_events, {"completed", "success", "validated", "waiting_approval"})
    score = round(
        (
            crash_free * 0.20
            + workflow_success * 0.25
            + validation_success * 0.20
            + rollback_success * 0.15
            + orchestration_stability * 0.15
            + update_success * 0.05
        )
        * 100
    )
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "score": score,
        "status": "needs_real_usage_data" if not events else "improving" if score >= 70 else "needs_attention",
        "metrics": {
            "crash_free_sessions": crash_free,
            "successful_workflow_completion": workflow_success,
            "rollback_recovery_success": rollback_success,
            "validation_reliability": validation_success,
            "orchestration_stability": orchestration_stability,
            "update_reliability": update_success,
        },
        "event_counts": dict(statuses),
        "sample_size": len(events),
        "confidence_warning": "Low sample size; dogfooding confidence improves after repeated real workflows." if len(events) < 20 else "",
    }


def long_session_plan(workspace: str | Path | None = None) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve() if workspace else None
    return {
        "workspace": str(root) if root else None,
        "generated_at": utc_now(),
        "scenarios": [
            {
                "id": "multi_hour_daily_driver",
                "title": "Multi-hour daily driver session",
                "duration_minutes": 180,
                "steps": ["open workspace", "scan", "chat", "roadmap item", "validate", "repair or rollback"],
                "signals": ["crash-free session", "memory growth", "streaming responsiveness", "workflow continuity"],
            },
            {
                "id": "large_project_session",
                "title": "Large project indexing and navigation",
                "duration_minutes": 90,
                "steps": ["scan large workspace", "query architecture", "impact analysis", "focused validation"],
                "signals": ["index duration", "graph size", "stale nodes", "UI remains responsive"],
            },
            {
                "id": "many_workflows_session",
                "title": "Many workflow session",
                "duration_minutes": 120,
                "steps": ["run roadmap", "feature", "validation", "repair", "deployment validation", "rollback"],
                "signals": ["workflow completion", "approval clarity", "event stream consistency", "activity feed usefulness"],
            },
            {
                "id": "plugin_heavy_session",
                "title": "Plugin-heavy session",
                "duration_minutes": 90,
                "steps": ["discover plugin", "review permissions", "enable", "run validator", "disable"],
                "signals": ["permission clarity", "load failures isolated", "plugin overhead", "compatibility warnings"],
            },
            {
                "id": "distributed_runtime_session",
                "title": "Trusted node session",
                "duration_minutes": 90,
                "steps": ["register local/trusted node", "dispatch validation", "disconnect node", "recover locally"],
                "signals": ["trust clarity", "fallback correctness", "workload history", "no lost checkpoints"],
            },
        ],
        "record_events": ["session_start", "workflow_completed", "workflow_abandoned", "validation_failed", "rollback_restored", "slow_workflow", "session_end"],
        "pass_condition": "No crash, no lost state, clear rollback path, and no workflow dead end without a next action.",
    }


def systems_to_simplify() -> list[dict[str, str]]:
    return [
        {"system": "Website protected app shell", "reason": "Large shell increases UI coupling and makes friction fixes harder to isolate.", "action": "Continue extracting primary workflow surfaces."},
        {"system": "Desktop command surface", "reason": "Native shell holds many runtime panels and labels in one file.", "action": "Split Workspace, Runtime, Changes, Validate, and Memory panels."},
        {"system": "VS Code extension monolith", "reason": "Command handling, Core client logic, safety, and UI remain too coupled.", "action": "Keep command IDs but move behavior into Core-backed modules."},
        {"system": "Website runtime fallback paths", "reason": "Compatibility is useful, but users should not have to understand duplicate owners.", "action": "Label as fallback and prefer Core-owned operations."},
        {"system": "Experimental Labs", "reason": "Distributed runtime, plugins, optimization, voice, and collaboration compete for attention.", "action": "Hide by default and expose only when explicitly enabled."},
    ]


def _performance_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [int(event.get("duration_ms") or 0) for event in events if int(event.get("duration_ms") or 0) > 0]
    slow_tags = {"slow_workflow", "startup_slow", "indexing_slow"}
    slow = [event for event in events if slow_tags & set(event.get("friction_tags") or [])]
    return {
        "sample_count": len(durations),
        "average_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
        "max_duration_ms": max(durations) if durations else 0,
        "slow_event_count": len(slow),
        "bottlenecks": _slow_bottlenecks(slow),
        "profile_next": ["large workspace indexing", "long-running workflows", "streaming responsiveness", "memory growth", "orchestration latency", "plugin overhead"],
    }


def _trust_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    unclear_tags = {
        "unclear_approval",
        "rollback_unclear",
        "model_routing_unclear",
        "diff_unclear",
        "diagnostics_unclear",
        "error_message_unclear",
    }
    unclear = [event for event in events if set(event.get("friction_tags") or []) & unclear_tags]
    return {
        "trust_friction_count": len(unclear),
        "required_explanations": [
            "what agents are doing",
            "why a model was selected",
            "why validation failed",
            "why repair was attempted",
            "what changed",
            "how to rollback",
        ],
        "recent_trust_friction": unclear[:20],
    }


def _ux_simplifications(friction: dict[str, Any]) -> list[dict[str, str]]:
    tags = {item["tag"] for item in friction.get("pain_points", [])}
    suggestions: list[dict[str, str]] = []
    if "too_many_clicks" in tags:
        suggestions.append({"title": "Add command-palette first actions", "detail": "Expose scan, validate, checkpoint, apply, rollback, and continue roadmap as keyboard-first actions."})
    if "unclear_approval" in tags:
        suggestions.append({"title": "Unify approval copy", "detail": "Use one approval panel that names changed files, risk, validation, checkpoint, and rollback."})
    if "noisy_panel" in tags:
        suggestions.append({"title": "Collapse secondary diagnostics", "detail": "Show only active workflow, safety state, validation, and next action by default."})
    if "overwhelming_configuration" in tags or "setup_friction" in tags:
        suggestions.append({"title": "Reduce setup choices", "detail": "Start with local-only mode, Ollama status, workspace selection, and one recommended model path."})
    if "onboarding_friction" in tags:
        suggestions.append({"title": "Tighten first-run guidance", "detail": "Show one local-first setup path, one health action, and one validation action before advanced settings."})
    if "roadmap_unhelpful" in tags:
        suggestions.append({"title": "Ground roadmap items", "detail": "Require each roadmap item to cite scan evidence, risk, validation target, and the next small action."})
    if "diff_unclear" in tags:
        suggestions.append({"title": "Clarify diffs before approval", "detail": "Group changes by purpose and show why each destination file was selected."})
    if "diagnostics_unclear" in tags or "error_message_unclear" in tags:
        suggestions.append({"title": "Make failures actionable", "detail": "Lead with the failing operation, likely cause, relevant log, and retry or rollback action."})
    if not suggestions:
        suggestions.append({"title": "Keep observing real use", "detail": "No dominant UX friction has enough local evidence yet."})
    return suggestions


def _polish_priorities(friction: dict[str, Any], performance: dict[str, Any], confidence: dict[str, Any]) -> list[dict[str, str]]:
    priorities: list[dict[str, str]] = []
    top = friction.get("pain_points", [])[:3]
    for item in top:
        priorities.append({"priority": "P1", "title": item["label"], "reason": item["recommendation"]})
    if performance.get("slow_event_count", 0):
        priorities.append({"priority": "P1", "title": "Speed up slow workflows", "reason": "Profile the slowest dogfooded paths before adding new automation."})
    if confidence.get("score", 0) < 70:
        priorities.append({"priority": "P0", "title": "Raise production confidence", "reason": "Improve crash-free sessions, workflow completion, validation reliability, rollback recovery, and orchestration stability."})
    if not priorities:
        priorities.append({"priority": "P2", "title": "Expand dogfooding sample size", "reason": "Run more real workflows before making broad UX changes."})
    return priorities[:8]


def _append_event(root: Path, event: dict[str, Any]) -> None:
    memory = ProjectMemory(root)
    memory.ensure()
    path = memory.root / EVENT_FILE
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _read_events(root: Path, *, limit: int = MAX_EVENTS) -> list[dict[str, Any]]:
    path = ProjectMemory(root).root / EVENT_FILE
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    for line in reversed(lines[-limit:]):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _normalize_friction_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    for tag in tags[:12]:
        clean = _safe_token(tag, "").replace("-", "_")
        if clean in FRICTION_LABELS and clean not in result:
            result.append(clean)
    return result


def _infer_friction(event_type: str, status: str, duration_ms: int | None, interruption: str) -> list[str]:
    tags: list[str] = []
    event = event_type.lower()
    clean_status = status.lower()
    if clean_status in {"abandoned", "dead_end"}:
        tags.append("workflow_dead_end")
    if clean_status in {"interrupted", "cancelled"} or interruption:
        tags.append("interrupted_stream")
    if "validation" in event and clean_status in {"failed", "failure"}:
        tags.append("validation_pain")
    if ("startup" in event or "launch" in event) and duration_ms is not None and duration_ms >= 15_000:
        tags.append("startup_slow")
    if ("index" in event or "scan" in event) and duration_ms is not None and duration_ms >= 30_000:
        tags.append("indexing_slow")
    if "repair" in event and clean_status in {"retried", "failed", "escalated"}:
        tags.append("repair_loop")
    if "rollback" in event and clean_status not in {"restored", "success", "completed"}:
        tags.append("rollback_unclear")
    if duration_ms is not None and duration_ms >= 60_000:
        tags.append("slow_workflow")
    return tags


def _rate(events: list[dict[str, Any]], success_statuses: set[str]) -> float:
    if not events:
        return 1.0
    success = sum(1 for event in events if str(event.get("status", "")).lower() in success_statuses)
    return round(success / len(events), 3)


def _slow_bottlenecks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_workflow: Counter[str] = Counter()
    for event in events:
        key = event.get("workflow_type") or event.get("event_type") or "unknown"
        by_workflow[str(key)] += 1
    return [{"workflow": key, "slow_count": value} for key, value in by_workflow.most_common(8)]


def _state_files(root: Path) -> dict[str, str]:
    memory = ProjectMemory(root)
    return {
        "events": str(memory.root / EVENT_FILE),
        "report": str(memory.root / REPORT_FILE),
        "summary": str(memory.root / SUMMARY_FILE),
    }


def _summary_markdown(result: dict[str, Any]) -> str:
    confidence = result.get("confidence", {})
    lines = [
        "## Dogfooding Snapshot",
        "",
        f"- Event count: {result.get('event_count', 0)}",
        f"- Production confidence: {confidence.get('score', 0)}",
        f"- Confidence status: {confidence.get('status', 'unknown')}",
        "",
        "## Biggest Friction",
        "",
    ]
    for item in result.get("friction", {}).get("pain_points", [])[:8]:
        lines.append(f"- {item['label']}: {item['count']} - {item['recommendation']}")
    lines.extend(["", "## Polish Priorities", ""])
    for item in result.get("recommended_polish_priorities", [])[:8]:
        lines.append(f"- {item['priority']}: {item['title']} - {item['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def _safe_token(value: Any, default: str) -> str:
    text = scrub(str(value or default)).strip().lower().replace(" ", "_")
    clean = "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-", "."})
    return clean[:80] or default


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in list(metadata.items())[:30]:
        clean_key = _safe_key(key, "metadata")
        if any(secret in clean_key for secret in ["secret", "token", "password", "api_key", "credential", "authorization"]):
            safe[clean_key] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[clean_key] = redact_inline(str(value))[:300] if isinstance(value, str) else value
        elif isinstance(value, list):
            safe[clean_key] = [redact_inline(str(item))[:160] for item in value[:12]]
        else:
            safe[clean_key] = scrub(str(value))[:300]
    return safe


def _safe_key(value: Any, default: str) -> str:
    text = str(value or default).strip().lower().replace(" ", "_")
    clean = "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-", "."})
    return clean[:80] or default
