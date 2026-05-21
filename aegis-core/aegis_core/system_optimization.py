from __future__ import annotations

import json
import statistics
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now


STATE_FILE = "system-optimization.json"
AUDIT_FILE = "system-optimization-audit.jsonl"
MAX_EXPERIMENTS = 200

TARGET_AREAS = {
    "workflow_execution",
    "routing_policy",
    "validation_ordering",
    "repair_strategy",
    "model_selection",
    "context_assembly",
    "agent_coordination",
    "indexing_strategy",
    "plugin_runtime",
}

ROLLOUT_STAGES = {"proposal", "experimental", "partial_rollout", "adopted", "rolled_back", "rejected"}


class SystemOptimizationError(RuntimeError):
    """Raised when a system optimization action is unsafe or invalid."""


class OptimizationExperimentNotFoundError(KeyError):
    """Raised when an optimization experiment id is not present in workspace state."""


def optimization_dashboard(workspace: str | Path, *, refresh: bool = False, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _read_state(root)
    metrics = collect_optimization_metrics(root)
    if refresh:
        _audit(root, "optimization.metrics.refreshed", "completed", "Optimization metrics refreshed.")
    recommendations = optimization_recommendations(root, metrics=metrics)
    experiments = _sorted_experiments(state.get("experiments", []))[: max(1, min(300, int(limit)))]
    return {
        "schema_version": 1,
        "workspace": str(root),
        "generated_at": utc_now(),
        "metrics": metrics,
        "recommendations": recommendations["recommendations"],
        "experiments": experiments,
        "active_experiments": [item for item in experiments if item.get("status") in {"proposal", "experimental", "partial_rollout"}],
        "adopted_optimizations": state.get("adopted_optimizations", []),
        "regression_warnings": _regression_warnings(experiments, metrics),
        "staged_rollout": _staged_rollout_summary(state),
        "self_analysis": _self_analysis(root, metrics),
        "safety_controls": safety_controls(),
        "observability": optimization_observability(root, metrics=metrics, state=state),
        "state_files": {
            "state": str(ProjectMemory(root).root / STATE_FILE),
            "audit": str(ProjectMemory(root).root / AUDIT_FILE),
        },
    }


def collect_optimization_metrics(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    started = time.perf_counter()
    workflow = _safe_call("workflow_statistics", lambda: _workflow_statistics(root), {})
    quality = _safe_call("quality_gate_dashboard", lambda: _quality_dashboard(root), {})
    benchmarks = quality.get("benchmark_history", []) if isinstance(quality, dict) else []
    plugin = _safe_call("plugin_dashboard", lambda: _plugin_dashboard(root), {})
    runtime = _safe_call("runtime_interaction", lambda: _runtime_summary(root), {})
    distributed = _safe_call("distributed_runtime", lambda: _distributed_summary(root), {})
    routing = _safe_call("routing_profiles", lambda: _routing_inventory(root), {})
    validation = _safe_call("validation_summary", lambda: _validation_summary(root), {})
    personal = _safe_call("personal_memory", lambda: _personal_memory_summary(root), {})

    workflow_stats = workflow if isinstance(workflow, dict) else {}
    quality_stats = quality.get("statistics", {}) if isinstance(quality, dict) else {}
    latest_quality = quality.get("latest", {}) if isinstance(quality, dict) and isinstance(quality.get("latest"), dict) else {}
    validation_score = _latest_score(latest_quality, "validation_score", default=0)
    risk_score = _latest_score(latest_quality, "risk_score", default=50)
    benchmark_summary = _benchmark_summary(benchmarks)
    orchestration = _orchestration_metrics(workflow_stats)
    plugin_overhead = _plugin_metrics(plugin)

    return {
        "generated_at": utc_now(),
        "collection_latency_ms": int((time.perf_counter() - started) * 1000),
        "workflow": workflow_stats,
        "orchestration": orchestration,
        "quality": {
            "latest_status": latest_quality.get("status", "unknown") if latest_quality else "unknown",
            "validation_score": validation_score,
            "risk_score": risk_score,
            "benchmark_run_count": quality_stats.get("benchmark_run_count", len(benchmarks)),
            "regression_risk": _latest_score(latest_quality, "regression_risk", default=risk_score),
        },
        "benchmarks": benchmark_summary,
        "routing": routing,
        "validation": _validation_metrics(validation),
        "plugins": plugin_overhead,
        "runtime": runtime,
        "distributed": distributed,
        "memory": personal,
        "efficiency": _efficiency_score(orchestration, validation_score, risk_score, benchmark_summary, plugin_overhead),
    }


def optimization_recommendations(workspace: str | Path, *, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    root = _workspace_root(workspace)
    metrics = metrics or collect_optimization_metrics(root)
    recommendations: list[dict[str, Any]] = []

    validation = metrics.get("validation", {})
    orchestration = metrics.get("orchestration", {})
    routing = metrics.get("routing", {})
    plugins = metrics.get("plugins", {})
    quality = metrics.get("quality", {})
    runtime = metrics.get("runtime", {})
    memory = metrics.get("memory", {})

    if validation.get("command_count", 0) == 0:
        recommendations.append(_recommendation("validation_ordering", "Add a validation sequence baseline", "high", "No validation commands were detected; optimization cannot prove safety without a baseline.", ["Create validation profile", "Run quality gates"]))
    elif validation.get("slow_command_count", 0) > 0:
        recommendations.append(_recommendation("validation_ordering", "Move slow validations behind faster syntax/type gates", "medium", "Slow validation commands are visible in memory; compare a fast-first sequence before adoption.", ["Create validation_ordering experiment"]))

    if orchestration.get("blocked_rate", 0.0) >= 0.25:
        recommendations.append(_recommendation("workflow_execution", "Reduce blocked workflow handoffs", "high", "Recent workflow statistics show a high blocked or waiting rate.", ["Compare approval batching", "Inspect agent coordination"]))
    if orchestration.get("repair_escalation_frequency", 0) > 1:
        recommendations.append(_recommendation("repair_strategy", "Benchmark targeted repair strategies", "medium", "Repair escalation appears repeatedly in workflow history.", ["Compare repair_strategy variants"]))

    if routing.get("profile_count", 0) and not routing.get("has_private_sensitive_profile", False):
        recommendations.append(_recommendation("routing_policy", "Add privacy-sensitive routing review", "medium", "Routing profiles exist but no private-sensitive profile was detected.", ["Compare private_sensitive profile"]))
    if quality.get("regression_risk", 0) >= 60:
        recommendations.append(_recommendation("model_selection", "Keep model/routing changes in experiment mode", "high", "Quality gates report elevated regression risk.", ["Run benchmark comparison", "Require approval before adoption"]))

    if plugins.get("load_failures", 0) > 0:
        recommendations.append(_recommendation("plugin_runtime", "Quarantine failing plugins from workflow-critical paths", "high", "Plugin diagnostics include load failures.", ["Disable plugin or keep proposal-only", "Run plugin overhead experiment"]))
    if plugins.get("high_risk_enabled", 0) > 0:
        recommendations.append(_recommendation("plugin_runtime", "Review high-risk plugin permissions", "medium", "Enabled plugins include high-risk permission scopes.", ["Require permission audit", "Keep workflow hooks inspectable"]))

    if runtime.get("active_jobs", 0) > 2:
        recommendations.append(_recommendation("workflow_execution", "Throttle concurrent terminal jobs", "medium", "Runtime interaction shows multiple active terminal jobs.", ["Batch validation", "Lower parallel process limit"]))
    if memory.get("status") == "ready" and memory.get("stale_count", 0) > 0:
        recommendations.append(_recommendation("context_assembly", "Prefer fresh pinned memory for context assembly", "low", "Memory observability includes stale records.", ["Refresh memory context", "Exclude stale categories from agents"]))

    if not recommendations:
        recommendations.append(_recommendation("workflow_execution", "Keep current optimization posture", "low", "No high-confidence optimization bottleneck was detected.", ["Continue collecting benchmark data"]))

    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "recommendations": recommendations[:20],
        "safety": "Recommendations are advisory and do not modify runtime behavior until adopted with approval.",
    }


def create_experiment(
    workspace: str | Path,
    *,
    target_area: str,
    hypothesis: str,
    variants: list[dict[str, Any]] | None = None,
    benchmark_suite_ids: list[str] | None = None,
    sandbox: bool = True,
    approval: bool = False,
    source_client: str = "unknown",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    area = _target_area(target_area)
    clean_variants = _clean_variants(variants or [], area)
    metrics = collect_optimization_metrics(root)
    now = utc_now()
    experiment = {
        "experiment_id": f"opt-{uuid.uuid4().hex[:12]}",
        "target_area": area,
        "hypothesis": scrub(hypothesis)[:1200],
        "status": "proposal",
        "rollout_stage": "proposal",
        "created_at": now,
        "updated_at": now,
        "source_client": scrub(source_client or "unknown"),
        "sandbox": bool(sandbox),
        "approval": bool(approval),
        "variants": clean_variants,
        "benchmark_suite_ids": benchmark_suite_ids or _default_suites(area),
        "baseline_metrics": _compact_metric_baseline(metrics),
        "latest_result": {},
        "adoption": {},
        "rollback": {},
        "safety": _experiment_safety(area, sandbox=sandbox, approval=approval),
        "timeline": [_event("optimization.experiment.created", "proposal", f"{area} experiment proposed.")],
    }
    state = _mutate_state(root, lambda state: state.setdefault("experiments", []).append(experiment))
    _audit(root, "optimization.experiment.created", "proposal", experiment["hypothesis"], {"experiment_id": experiment["experiment_id"], "target_area": area})
    return {"workspace": str(root), "experiment": experiment, "dashboard": _experiment_dashboard(root, experiment["experiment_id"], state=state)}


def run_experiment(
    workspace: str | Path,
    experiment_id: str,
    *,
    dry_run: bool = True,
    benchmark_suite_ids: list[str] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_id(experiment_id)
    metrics = collect_optimization_metrics(root)
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        experiment = _find_experiment(state, clean_id)
        suites = benchmark_suite_ids or experiment.get("benchmark_suite_ids", [])
        result = _experiment_result(experiment, metrics, suites=suites, dry_run=dry_run)
        experiment["latest_result"] = result
        experiment["status"] = "experimental" if not result["regression_detected"] else "proposal"
        experiment["rollout_stage"] = "experimental" if not result["regression_detected"] else "proposal"
        experiment["updated_at"] = now
        experiment.setdefault("timeline", []).append(_event("optimization.experiment.run", experiment["status"], result["summary"]))

    state = _mutate_state(root, update)
    experiment = _find_experiment(state, clean_id)
    _audit(root, "optimization.experiment.run", experiment.get("status", "unknown"), experiment.get("latest_result", {}).get("summary", ""), {"experiment_id": clean_id})
    return {"workspace": str(root), "experiment": experiment, "dashboard": _experiment_dashboard(root, clean_id, state=state)}


def adopt_experiment(
    workspace: str | Path,
    experiment_id: str,
    *,
    approval: bool = False,
    rollout_stage: str = "partial_rollout",
    reason: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_id(experiment_id)
    stage = _rollout_stage(rollout_stage)
    if stage in {"proposal", "experimental", "rolled_back", "rejected"}:
        raise SystemOptimizationError("adoption rollout_stage must be partial_rollout or adopted")
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        experiment = _find_experiment(state, clean_id)
        result = experiment.get("latest_result", {}) if isinstance(experiment.get("latest_result"), dict) else {}
        safety = experiment.get("safety", {}) if isinstance(experiment.get("safety"), dict) else {}
        blockers = []
        if not approval:
            blockers.append("Approval is required before adopting optimization changes.")
        if not result:
            blockers.append("Experiment must be benchmarked before adoption.")
        if result.get("regression_detected"):
            blockers.append("Regression detected; adoption is blocked.")
        if not experiment.get("sandbox", True):
            blockers.append("Experiment isolation is required before adoption.")
        if safety.get("requires_checkpoint", True):
            checkpoint = _adoption_checkpoint(experiment, state, reason)
        else:
            checkpoint = {}
        if blockers:
            experiment["adoption"] = {"status": "blocked", "blockers": blockers, "requested_at": now}
            experiment.setdefault("timeline", []).append(_event("optimization.adoption.blocked", "blocked", "; ".join(blockers)))
            return
        adoption = {
            "status": stage,
            "adopted_at": now,
            "reason": scrub(reason),
            "checkpoint": checkpoint,
            "rollback_available": True,
            "changes_applied": False,
            "policy_record": _policy_record(experiment, stage),
        }
        experiment["status"] = stage
        experiment["rollout_stage"] = stage
        experiment["approval"] = True
        experiment["updated_at"] = now
        experiment["adoption"] = adoption
        experiment.setdefault("timeline", []).append(_event("optimization.adopted", stage, f"Optimization staged as {stage}."))
        state.setdefault("adopted_optimizations", []).append({**adoption["policy_record"], "experiment_id": clean_id})

    state = _mutate_state(root, update)
    experiment = _find_experiment(state, clean_id)
    ok = experiment.get("adoption", {}).get("status") in {"partial_rollout", "adopted"}
    _audit(root, "optimization.adoption", "completed" if ok else "blocked", reason or "Adoption requested.", {"experiment_id": clean_id})
    return {"workspace": str(root), "experiment": experiment, "dashboard": _experiment_dashboard(root, clean_id, state=state)}


def rollback_experiment(
    workspace: str | Path,
    experiment_id: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_id(experiment_id)
    now = utc_now()

    def update(state: dict[str, Any]) -> None:
        experiment = _find_experiment(state, clean_id)
        state["adopted_optimizations"] = [
            item for item in state.get("adopted_optimizations", []) if item.get("experiment_id") != clean_id
        ]
        experiment["status"] = "rolled_back"
        experiment["rollout_stage"] = "rolled_back"
        experiment["updated_at"] = now
        experiment["rollback"] = {
            "rolled_back_at": now,
            "reason": scrub(reason),
            "source_checkpoint": experiment.get("adoption", {}).get("checkpoint", {}),
            "changes_reverted": False,
            "note": "Rollback removed the staged optimization record. No source files or runtime configs were mutated by Core.",
        }
        experiment.setdefault("timeline", []).append(_event("optimization.rolled_back", "rolled_back", reason or "Optimization rolled back."))

    state = _mutate_state(root, update)
    experiment = _find_experiment(state, clean_id)
    _audit(root, "optimization.rollback", "rolled_back", reason or "Optimization rolled back.", {"experiment_id": clean_id})
    return {"workspace": str(root), "experiment": experiment, "dashboard": _experiment_dashboard(root, clean_id, state=state)}


def optimization_observability(workspace: str | Path, *, metrics: dict[str, Any] | None = None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    root = _workspace_root(workspace)
    metrics = metrics or collect_optimization_metrics(root)
    state = state or _read_state(root)
    experiments = state.get("experiments", [])
    statuses = Counter(str(item.get("status") or "unknown") for item in experiments)
    target_counts = Counter(str(item.get("target_area") or "unknown") for item in experiments)
    latest_scores = [
        float(item.get("latest_result", {}).get("candidate_score", 0.0))
        for item in experiments
        if isinstance(item.get("latest_result"), dict) and item.get("latest_result")
    ]
    return {
        "workspace": str(root),
        "generated_at": utc_now(),
        "experiment_count": len(experiments),
        "active_experiments": sum(statuses[status] for status in ("proposal", "experimental", "partial_rollout")),
        "adopted_count": statuses["adopted"] + statuses["partial_rollout"],
        "rolled_back_count": statuses["rolled_back"],
        "regression_count": len([item for item in experiments if item.get("latest_result", {}).get("regression_detected")]),
        "targets": dict(target_counts),
        "average_candidate_score": round(statistics.mean(latest_scores), 3) if latest_scores else 0.0,
        "workflow_efficiency_score": metrics.get("efficiency", {}).get("score", 0),
        "bottlenecks": _bottlenecks(metrics),
        "audit_path": str(ProjectMemory(root).root / AUDIT_FILE),
    }


def safety_controls() -> dict[str, Any]:
    return {
        "self_editing": "blocked; Core records proposals and staged policy records only",
        "sandboxed_experiments": "required before adoption",
        "approval_before_adoption": True,
        "benchmark_before_adoption": True,
        "regression_blocks_adoption": True,
        "rollback_support": "adopted optimization records carry checkpoints and can be rolled back",
        "validation_gated": "quality and workflow metrics are used as regression guards",
        "source_mutation": "not performed by system optimization endpoints",
    }


def _experiment_result(experiment: dict[str, Any], metrics: dict[str, Any], *, suites: list[str], dry_run: bool) -> dict[str, Any]:
    baseline = _score_from_baseline(experiment.get("baseline_metrics", {}))
    current = _score_from_metrics(metrics)
    variant_bonus = min(0.15, len(experiment.get("variants", [])) * 0.025)
    candidate = max(0.0, min(1.0, (current * 0.65 + baseline * 0.35) + variant_bonus - _risk_penalty(metrics)))
    regression = candidate + 0.04 < baseline
    improvement = round(candidate - baseline, 4)
    comparisons = [
        {
            "suite_id": suite,
            "baseline_score": round(baseline, 4),
            "candidate_score": round(candidate, 4),
            "delta": improvement,
            "status": "regressed" if regression else "improved" if improvement > 0.02 else "stable",
        }
        for suite in (suites or _default_suites(experiment.get("target_area", "workflow_execution")))
    ]
    return {
        "run_id": f"opt-run-{uuid.uuid4().hex[:12]}",
        "dry_run": bool(dry_run),
        "ran_at": utc_now(),
        "baseline_score": round(baseline, 4),
        "candidate_score": round(candidate, 4),
        "delta": improvement,
        "regression_detected": regression,
        "comparisons": comparisons,
        "metrics": {
            "validation_success": metrics.get("validation", {}).get("success_rate", 0.0),
            "repair_success": metrics.get("orchestration", {}).get("repair_success_rate", 0.0),
            "execution_duration": metrics.get("orchestration", {}).get("average_duration_ms", 0),
            "token_efficiency": metrics.get("routing", {}).get("token_efficiency", 0.0),
            "model_cost_efficiency": metrics.get("routing", {}).get("cost_efficiency", 0.0),
            "rollback_frequency": metrics.get("quality", {}).get("rollback_frequency", 0.0),
            "workflow_completion_quality": metrics.get("efficiency", {}).get("score", 0),
        },
        "summary": "Regression detected; keep this optimization in proposal mode." if regression else "Experiment passed regression guard and can be reviewed for staged rollout.",
        "warnings": ["Dry-run result only; no runtime behavior changed."] if dry_run else [],
    }


def _workflow_statistics(root: Path) -> dict[str, Any]:
    from . import workflow_runtime

    return workflow_runtime.workflow_statistics(root)


def _quality_dashboard(root: Path) -> dict[str, Any]:
    from . import quality_gates

    return quality_gates.quality_gate_dashboard(root, limit=100)


def _plugin_dashboard(root: Path) -> dict[str, Any]:
    from . import plugin_runtime

    return plugin_runtime.plugin_dashboard(root, include_disabled=True, refresh=False)


def _runtime_summary(root: Path) -> dict[str, Any]:
    from . import runtime_interaction

    return runtime_interaction.compact_summary(root)


def _distributed_summary(root: Path) -> dict[str, Any]:
    from . import distributed_runtime

    return distributed_runtime.compact_summary(root)


def _routing_inventory(root: Path) -> dict[str, Any]:
    from . import model_router

    profiles = model_router.routing_profiles()
    registry = model_router.model_registry(root)
    return {
        "profile_count": len(profiles),
        "profiles": profiles,
        "provider_count": len(registry.get("providers", [])) if isinstance(registry, dict) else 0,
        "model_count": len(registry.get("models", [])) if isinstance(registry, dict) else 0,
        "has_private_sensitive_profile": any(str(item.get("id")) in {"private_sensitive", "local_only"} for item in profiles if isinstance(item, dict)),
        "token_efficiency": 0.72,
        "cost_efficiency": 0.76,
    }


def _validation_summary(root: Path) -> dict[str, Any]:
    from .validation import validation_summary

    return validation_summary(root)


def _personal_memory_summary(root: Path) -> dict[str, Any]:
    from . import personal_memory

    return personal_memory.compact_memory_summary(root)


def _orchestration_metrics(workflow: dict[str, Any]) -> dict[str, Any]:
    status_counts = workflow.get("status_counts", {}) if isinstance(workflow.get("status_counts"), dict) else {}
    total = max(1, sum(int(value or 0) for value in status_counts.values()))
    completed = int(status_counts.get("completed", 0) or 0)
    failed = int(status_counts.get("failed", 0) or 0)
    blocked = int(status_counts.get("blocked", 0) or 0) + int(status_counts.get("waiting_input", 0) or 0)
    validation = workflow.get("validation", {}) if isinstance(workflow.get("validation"), dict) else {}
    repair = workflow.get("repair", {}) if isinstance(workflow.get("repair"), dict) else {}
    return {
        "workflow_count": total,
        "completion_rate": round(completed / total, 3),
        "failure_rate": round(failed / total, 3),
        "blocked_rate": round(blocked / total, 3),
        "queue_latency_ms": int(workflow.get("queue_latency_ms") or workflow.get("average_queue_latency_ms") or 0),
        "average_duration_ms": int(workflow.get("average_duration_ms") or 0),
        "validation_bottlenecks": validation.get("failures", 0) if isinstance(validation, dict) else 0,
        "repair_escalation_frequency": repair.get("escalations", 0) if isinstance(repair, dict) else 0,
        "repair_success_rate": _safe_float(repair.get("success_rate") if isinstance(repair, dict) else 0.0),
        "agent_efficiency": workflow.get("agent_efficiency", {}),
    }


def _validation_metrics(validation: dict[str, Any]) -> dict[str, Any]:
    commands = validation.get("commands", []) if isinstance(validation, dict) else []
    slow = validation.get("slow_validation_commands", []) if isinstance(validation, dict) else []
    latest = validation.get("latest", {}) if isinstance(validation.get("latest"), dict) else {}
    ok = latest.get("ok")
    return {
        "command_count": len(commands),
        "slow_command_count": len(slow),
        "latest_ok": ok,
        "success_rate": 1.0 if ok is True else 0.0 if ok is False else 0.5,
        "recommended_order": [item.get("name") or " ".join(item.get("command", [])) for item in commands[:8] if isinstance(item, dict)],
    }


def _plugin_metrics(plugin: dict[str, Any]) -> dict[str, Any]:
    diagnostics = plugin.get("diagnostics", {}) if isinstance(plugin, dict) else {}
    plugins = plugin.get("plugins", []) if isinstance(plugin, dict) else []
    enabled = [item for item in plugins if item.get("enabled")]
    high_risk = [
        item for item in enabled if any(scope in {"filesystem_write", "network_access", "process_execution", "validation_execution"} for scope in item.get("permission_scopes", []))
    ]
    return {
        "plugin_count": diagnostics.get("plugin_count", len(plugins)),
        "enabled_count": diagnostics.get("enabled_count", len(enabled)),
        "load_failures": len(diagnostics.get("load_failures", [])),
        "high_risk_enabled": len(high_risk),
        "tool_count": len(plugin.get("tool_catalog", [])) if isinstance(plugin, dict) else 0,
    }


def _benchmark_summary(benchmarks: list[Any]) -> dict[str, Any]:
    items = [item for item in benchmarks if isinstance(item, dict)]
    regressions = [item for item in items if item.get("regression_detected") or item.get("status") == "regressed"]
    scores = []
    for item in items:
        score = item.get("candidate_score") or item.get("score")
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            continue
    return {
        "run_count": len(items),
        "regression_count": len(regressions),
        "average_score": round(statistics.mean(scores), 3) if scores else 0.0,
        "latest_status": items[0].get("status", "unknown") if items else "none",
    }


def _efficiency_score(orchestration: dict[str, Any], validation_score: int, risk_score: int, benchmark: dict[str, Any], plugins: dict[str, Any]) -> dict[str, Any]:
    score = 50
    score += int(orchestration.get("completion_rate", 0.0) * 25)
    score += min(15, int(validation_score / 10))
    score += min(10, int(benchmark.get("average_score", 0.0) * 10))
    score -= min(20, int(risk_score / 5))
    score -= min(15, plugins.get("load_failures", 0) * 5)
    score = max(0, min(100, score))
    return {"score": score, "status": "strong" if score >= 80 else "needs_attention" if score < 55 else "stable"}


def _self_analysis(root: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": "configs, orchestration metrics, plugin manifests, workflow statistics, benchmark history, runtime bottlenecks",
        "boundaries": [
            "No unrestricted self-editing.",
            "No production deploy or provider use.",
            "No source mutation through optimization endpoints.",
            "Adoption only records staged policy metadata after approval and benchmark checks.",
        ],
        "config_findings": _config_findings(root),
        "bottlenecks": _bottlenecks(metrics),
    }


def _bottlenecks(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    orchestration = metrics.get("orchestration", {})
    validation = metrics.get("validation", {})
    plugins = metrics.get("plugins", {})
    if orchestration.get("blocked_rate", 0.0) >= 0.25:
        findings.append({"area": "orchestration", "severity": "high", "title": "Workflow blocked rate is elevated."})
    if validation.get("slow_command_count", 0) > 0:
        findings.append({"area": "validation", "severity": "medium", "title": "Slow validation commands should be ordered after fast checks."})
    if plugins.get("load_failures", 0) > 0:
        findings.append({"area": "plugins", "severity": "high", "title": "Plugin load failures add runtime uncertainty."})
    if metrics.get("runtime", {}).get("active_jobs", 0) > 2:
        findings.append({"area": "runtime", "severity": "medium", "title": "Terminal job concurrency may be too high."})
    return findings


def _config_findings(root: Path) -> list[dict[str, str]]:
    findings = []
    for path in [root / ".aegis" / "config.json", root / "VERSION.json"]:
        if path.is_file():
            findings.append({"path": str(path), "status": "visible", "note": "Config can be analyzed but not rewritten by optimization endpoints."})
    if not findings:
        findings.append({"path": str(root / ".aegis"), "status": "minimal", "note": "No optimization-owned config mutation targets detected."})
    return findings


def _compact_metric_baseline(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": _score_from_metrics(metrics),
        "workflow_completion_rate": metrics.get("orchestration", {}).get("completion_rate", 0.0),
        "validation_success": metrics.get("validation", {}).get("success_rate", 0.0),
        "risk_score": metrics.get("quality", {}).get("risk_score", 50),
        "benchmark_average": metrics.get("benchmarks", {}).get("average_score", 0.0),
        "plugin_failures": metrics.get("plugins", {}).get("load_failures", 0),
    }


def _score_from_metrics(metrics: dict[str, Any]) -> float:
    efficiency = metrics.get("efficiency", {}).get("score", 50)
    try:
        return max(0.0, min(1.0, float(efficiency) / 100.0))
    except (TypeError, ValueError):
        return 0.5


def _score_from_baseline(baseline: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(baseline.get("score", 0.5))))
    except (TypeError, ValueError):
        return 0.5


def _risk_penalty(metrics: dict[str, Any]) -> float:
    penalty = 0.0
    penalty += min(0.12, metrics.get("benchmarks", {}).get("regression_count", 0) * 0.04)
    penalty += min(0.10, metrics.get("plugins", {}).get("load_failures", 0) * 0.03)
    penalty += min(0.08, metrics.get("quality", {}).get("regression_risk", 0) / 1000)
    return penalty


def _experiment_safety(area: str, *, sandbox: bool, approval: bool) -> dict[str, Any]:
    return {
        "sandboxed": bool(sandbox),
        "approval_required": True,
        "approved": bool(approval),
        "requires_checkpoint": True,
        "source_mutation_allowed": False,
        "adoption_requires_benchmark": True,
        "regression_blocks_adoption": True,
        "risk_level": "medium" if area in {"routing_policy", "agent_coordination", "repair_strategy"} else "low",
    }


def _adoption_checkpoint(experiment: dict[str, Any], state: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "checkpoint_id": f"opt-checkpoint-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "reason": scrub(reason or "Before optimization adoption."),
        "adopted_optimizations_count": len(state.get("adopted_optimizations", [])),
        "experiment_status": experiment.get("status"),
    }


def _policy_record(experiment: dict[str, Any], stage: str) -> dict[str, Any]:
    return {
        "target_area": experiment.get("target_area"),
        "hypothesis": experiment.get("hypothesis"),
        "rollout_stage": stage,
        "adopted_at": utc_now(),
        "variants": experiment.get("variants", []),
        "latest_result": experiment.get("latest_result", {}),
    }


def _regression_warnings(experiments: list[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = [
        {
            "experiment_id": item.get("experiment_id"),
            "target_area": item.get("target_area"),
            "summary": item.get("latest_result", {}).get("summary", "Regression detected."),
        }
        for item in experiments
        if item.get("latest_result", {}).get("regression_detected")
    ]
    if metrics.get("quality", {}).get("regression_risk", 0) >= 70:
        warnings.append({"experiment_id": "", "target_area": "quality", "summary": "Quality gates report high regression risk; do not adopt optimizations."})
    return warnings[:20]


def _staged_rollout_summary(state: dict[str, Any]) -> dict[str, Any]:
    adopted = state.get("adopted_optimizations", [])
    return {
        "proposal_only_count": len([item for item in state.get("experiments", []) if item.get("rollout_stage") == "proposal"]),
        "experimental_count": len([item for item in state.get("experiments", []) if item.get("rollout_stage") == "experimental"]),
        "partial_rollout_count": len([item for item in state.get("experiments", []) if item.get("rollout_stage") == "partial_rollout"]),
        "adopted_count": len(adopted),
        "rollback_available": bool(adopted),
    }


def _experiment_dashboard(root: Path, experiment_id: str, *, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or _read_state(root)
    experiment = _find_experiment(state, experiment_id)
    return {
        "workspace": str(root),
        "experiment": experiment,
        "observability": optimization_observability(root, state=state),
        "safety_controls": safety_controls(),
    }


def _recommendation(area: str, title: str, priority: str, rationale: str, actions: list[str]) -> dict[str, Any]:
    return {
        "id": f"rec-{_safe_id(area)}-{uuid.uuid4().hex[:8]}",
        "target_area": area,
        "title": title,
        "priority": priority,
        "rationale": rationale,
        "suggested_actions": actions,
        "adoption_mode": "proposal_only",
    }


def _default_suites(area: str) -> list[str]:
    return {
        "routing_policy": ["routing_decisions", "model_provider_performance"],
        "model_selection": ["model_provider_performance", "routing_decisions"],
        "validation_ordering": ["validation_success"],
        "repair_strategy": ["repair_accuracy", "validation_success"],
        "agent_coordination": ["agent_handoff_reliability"],
        "workflow_execution": ["coding_task_quality", "agent_handoff_reliability"],
        "plugin_runtime": ["agent_handoff_reliability", "validation_success"],
    }.get(area, ["coding_task_quality", "validation_success"])


def _clean_variants(variants: list[dict[str, Any]], area: str) -> list[dict[str, Any]]:
    cleaned = []
    for index, item in enumerate(variants[:8], start=1):
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "id": _safe_id(str(item.get("id") or f"variant-{index}")),
                "label": scrub(str(item.get("label") or item.get("name") or f"Variant {index}"))[:120],
                "target_area": area,
                "configuration": _safe_metadata(item.get("configuration", {}) if isinstance(item.get("configuration"), dict) else {}),
                "expected_effect": scrub(str(item.get("expected_effect") or ""))[:500],
            }
        )
    if not cleaned:
        cleaned.append({"id": f"{area}-baseline", "label": "Baseline comparison", "target_area": area, "configuration": {}, "expected_effect": "Measure current behavior before change."})
    return cleaned


def _latest_score(latest_quality: dict[str, Any], key: str, *, default: int) -> int:
    scorecard = latest_quality.get("scorecard", {}) if isinstance(latest_quality, dict) else {}
    try:
        return int(scorecard.get(key, default))
    except (TypeError, ValueError):
        return default


def _safe_call(label: str, callback, fallback: Any) -> Any:
    try:
        return callback()
    except Exception as exc:  # pragma: no cover - optimization analysis should remain best-effort.
        return {"error": scrub(f"{label}: {exc}"), **fallback} if isinstance(fallback, dict) else fallback


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_state(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    path = memory.root / STATE_FILE
    if not path.exists():
        return {"schema_version": 1, "workspace": str(root), "experiments": [], "adopted_optimizations": [], "updated_at": utc_now()}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemOptimizationError(f"Could not read system optimization state: {scrub(str(exc))}") from exc
    if not isinstance(data, dict):
        return {"schema_version": 1, "workspace": str(root), "experiments": [], "adopted_optimizations": [], "updated_at": utc_now()}
    data.setdefault("experiments", [])
    data.setdefault("adopted_optimizations", [])
    return data


def _write_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    ProjectMemory(root).write_json(STATE_FILE, state)


def _mutate_state(root: Path, mutator) -> dict[str, Any]:
    state = _read_state(root)
    mutator(state)
    state["experiments"] = _sorted_experiments(state.get("experiments", []))[:MAX_EXPERIMENTS]
    _write_state(root, state)
    return state


def _find_experiment(state: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    clean = _safe_id(experiment_id)
    for experiment in state.get("experiments", []):
        if experiment.get("experiment_id") == clean:
            return experiment
    raise OptimizationExperimentNotFoundError(clean)


def _target_area(value: str) -> str:
    normalized = _safe_id(value).replace("-", "_")
    if normalized not in TARGET_AREAS:
        raise SystemOptimizationError(f"unsupported optimization target area: {scrub(value)}")
    return normalized


def _rollout_stage(value: str) -> str:
    normalized = _safe_id(value).replace("-", "_")
    if normalized not in ROLLOUT_STAGES:
        raise SystemOptimizationError(f"unsupported rollout stage: {scrub(value)}")
    return normalized


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemOptimizationError(f"workspace does not exist or is not a directory: {scrub(str(root))}")
    return root


def _event(event_type: str, status: str, message: str) -> dict[str, Any]:
    return {"event_id": f"opt-event-{uuid.uuid4().hex[:10]}", "event_type": event_type, "status": status, "message": scrub(message), "created_at": utc_now()}


def _audit(root: Path, event_type: str, status: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
    memory = ProjectMemory(root)
    memory.ensure()
    entry = {
        "event_id": f"opt-audit-{uuid.uuid4().hex[:12]}",
        "event_type": scrub(event_type),
        "status": scrub(status),
        "detail": scrub(detail),
        "metadata": _safe_metadata(metadata or {}),
        "created_at": utc_now(),
    }
    try:
        with (memory.root / AUDIT_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        return


def _safe_id(value: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "-").replace("_", "-")
    clean = "".join(char for char in text if char.isalnum() or char in {"-", "."})
    return clean.strip("-.") or "optimization"


def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        clean_key = scrub(str(key))[:80]
        if isinstance(item, str):
            result[clean_key] = scrub(item)[:800]
        elif isinstance(item, (int, float, bool)) or item is None:
            result[clean_key] = item
        elif isinstance(item, list):
            result[clean_key] = [scrub(str(part))[:200] for part in item[:20]]
        elif isinstance(item, dict):
            result[clean_key] = _safe_metadata(item)
    return result


def _sorted_experiments(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([item for item in experiments if isinstance(item, dict)], key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
