from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .diagnostics import scrub
from .engineering_intelligence import engineering_intelligence, run_benchmarks as run_engineering_benchmarks
from .knowledge import architecture_summary, knowledge_graph, search_knowledge
from .memory import ProjectMemory, utc_now
from .model_router import model_registry, route_model
from .safety import is_safe_to_read
from .validation import validation_summary
from .workspace import WorkspaceScanner


STACK_FILE = "auralith-intelligence-stack.json"
MODEL_STATE_FILE = "intelligence-models.json"
RETRIEVAL_INDEX_FILE = "intelligence-retrieval-index.json"
BENCHMARK_FILE = "intelligence-benchmarks.json"
DATASET_FILE = "intelligence-datasets.json"

INTELLIGENCE_COMPONENTS: dict[str, dict[str, Any]] = {
    "orchestration": {
        "label": "Orchestration Intelligence",
        "purpose": "Workflow state classification, escalation timing, retry selection, and bounded autonomy.",
        "preferred_profile": "local_orchestration",
        "workflow_types": ["generate_feature", "repair_project", "continue_roadmap", "validate_project"],
        "capabilities": ["planning", "risk_prediction", "workflow_state_classification"],
    },
    "planning": {
        "label": "Planning Intelligence",
        "purpose": "Roadmap decomposition, dependency ordering, milestone prediction, and validation planning.",
        "preferred_profile": "local_planner",
        "workflow_types": ["generate_feature", "continue_roadmap", "scan_workspace"],
        "capabilities": ["roadmap_generation", "task_decomposition", "architecture_summarization"],
    },
    "repair": {
        "label": "Repair Intelligence",
        "purpose": "Root-cause classification, repair strategy selection, repeated-failure detection, and rollback recommendation.",
        "preferred_profile": "local_repair",
        "workflow_types": ["repair_project", "build_project", "validate_project"],
        "capabilities": ["repair_reasoning", "validation_reasoning", "code"],
    },
    "retrieval": {
        "label": "Retrieval And Indexing Intelligence",
        "purpose": "Hybrid graph/vector retrieval, workspace embeddings, memory embeddings, and context minimization.",
        "preferred_profile": "local_retrieval",
        "workflow_types": ["scan_workspace", "generate_feature", "repair_project", "research_task"],
        "capabilities": ["embeddings", "semantic_search", "graph_retrieval"],
    },
    "validation_classifier": {
        "label": "Validation Classifier",
        "purpose": "Validation command prioritization, flaky-test detection, failure classification, and confidence scoring.",
        "preferred_profile": "local_validation_classifier",
        "workflow_types": ["validate_project", "repair_project", "build_project"],
        "capabilities": ["classification", "validation_prediction", "failure_triage"],
    },
    "routing": {
        "label": "Routing Intelligence",
        "purpose": "Local/cloud routing, fallback selection, capability matching, latency/cost/privacy tradeoffs.",
        "preferred_profile": "local_routing",
        "workflow_types": ["chat_request", "generate_feature", "repair_project", "research_task", "generate_media"],
        "capabilities": ["model_routing", "capability_matching", "privacy_routing"],
    },
    "summarization": {
        "label": "Summarization Intelligence",
        "purpose": "Architecture summaries, workflow summaries, execution reports, and memory condensation.",
        "preferred_profile": "local_summarizer",
        "workflow_types": ["scan_workspace", "continue_roadmap", "chat_request"],
        "capabilities": ["summarization", "architecture_summarization", "memory_compression"],
    },
}

DEFAULT_LOCAL_MODEL_PROFILES: list[dict[str, Any]] = [
    {
        "model_id": "qwen2.5-coder:7b-instruct-q4",
        "display_name": "Qwen Coder 7B Instruct Q4",
        "provider_id": "ollama",
        "version": "profile",
        "lifecycle_status": "available_if_installed",
        "specializations": ["repair", "planning", "summarization"],
        "capabilities": ["code", "repair_reasoning", "summarization"],
        "quantization": {"format": "q4", "memory_gb_estimate": 6.0, "cpu_usable": True, "gpu_recommended": False},
        "compatibility": {"runtime": "ollama", "minimum_ram_gb": 8, "platforms": ["windows", "linux", "macos"]},
    },
    {
        "model_id": "deepseek-coder:6.7b-instruct-q4",
        "display_name": "DeepSeek Coder 6.7B Instruct Q4",
        "provider_id": "ollama",
        "version": "profile",
        "lifecycle_status": "available_if_installed",
        "specializations": ["repair", "validation_classifier"],
        "capabilities": ["code", "failure_triage", "repair_reasoning"],
        "quantization": {"format": "q4", "memory_gb_estimate": 6.0, "cpu_usable": True, "gpu_recommended": False},
        "compatibility": {"runtime": "ollama", "minimum_ram_gb": 8, "platforms": ["windows", "linux", "macos"]},
    },
    {
        "model_id": "nomic-embed-text:latest",
        "display_name": "Nomic Embed Text",
        "provider_id": "ollama",
        "version": "profile",
        "lifecycle_status": "available_if_installed",
        "specializations": ["retrieval"],
        "capabilities": ["embeddings", "semantic_search", "memory_embeddings"],
        "quantization": {"format": "embedding", "memory_gb_estimate": 2.0, "cpu_usable": True, "gpu_recommended": False},
        "compatibility": {"runtime": "ollama", "minimum_ram_gb": 4, "platforms": ["windows", "linux", "macos"]},
    },
    {
        "model_id": "llama3.2:3b-instruct-q4",
        "display_name": "Llama 3.2 3B Instruct Q4",
        "provider_id": "ollama",
        "version": "profile",
        "lifecycle_status": "available_if_installed",
        "specializations": ["orchestration", "routing", "summarization"],
        "capabilities": ["planning", "classification", "summarization", "model_routing"],
        "quantization": {"format": "q4", "memory_gb_estimate": 3.0, "cpu_usable": True, "gpu_recommended": False},
        "compatibility": {"runtime": "ollama", "minimum_ram_gb": 4, "platforms": ["windows", "linux", "macos"]},
    },
]


def intelligence_stack_dashboard(
    workspace: str | Path,
    *,
    refresh: bool = False,
    persist: bool = True,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    scan = WorkspaceScanner(root).scan(persist=persist or refresh)
    graph = _safe_call(lambda: knowledge_graph(root, persist=persist, scan=scan, refresh=refresh), {"nodes": [], "edges": []})
    registry = _safe_call(lambda: model_registry(root, check_health=True), {})
    model_state = _model_state(root)
    retrieval = retrieval_index(root, query=objective, refresh=refresh, persist=persist, limit=15)
    route = route_intelligence(
        root,
        workflow_type=workflow_type,
        objective=objective,
        target_files=target_files or [],
        allow_cloud=False,
        cloud_approved=False,
        privacy_sensitive=True,
    )
    prediction = orchestration_prediction(root, workflow_type=workflow_type, objective=objective, target_files=target_files or [])
    benchmarks = benchmark_dashboard(root)
    dataset = dataset_foundations(root, include_sensitive=False, limit=50, persist=False)
    distributed = distributed_inference_plan(
        root,
        workflow_type=workflow_type,
        model_id=str(route.get("selected_intelligence_model", {}).get("model_id") or ""),
        allow_remote=False,
        approval=False,
        dry_run=True,
        payload={"objective": objective},
        persist=False,
    )
    dashboard = {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": utc_now(),
        "local_first": True,
        "components": _component_status(model_state, registry),
        "architecture": _architecture(),
        "model_lifecycle": {
            "state_path": str(ProjectMemory(root).root / MODEL_STATE_FILE),
            "installed_or_registered": model_state.get("models", []),
            "recommended_profiles": DEFAULT_LOCAL_MODEL_PROFILES,
            "installable_profiles": _installable_profiles(registry, model_state),
            "compatibility": _model_compatibility_summary(model_state, registry),
        },
        "retrieval_stack": retrieval,
        "routing_intelligence": route,
        "orchestration_prediction": prediction,
        "distributed_inference": distributed,
        "dataset_foundations": dataset,
        "benchmarking": benchmarks,
        "observability": _observability(root, model_state, benchmarks, retrieval, route),
        "ui_visibility": _ui_visibility(route, retrieval, prediction, distributed),
        "state_files": _state_files(root),
        "recommendations": _recommendations(model_state, registry, retrieval, route, dataset),
    }
    if persist:
        ProjectMemory(root).write_json(STACK_FILE, dashboard)
    return dashboard


def model_lifecycle(
    workspace: str | Path,
    *,
    action: str = "list",
    model: Mapping[str, Any] | None = None,
    model_id: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _model_state(root)
    registry = _safe_call(lambda: model_registry(root, check_health=True), {})
    normalized_action = str(action or "list").strip().lower()
    warnings: list[str] = []
    changed = False

    if normalized_action in {"register", "update"}:
        entry = _normalize_model_entry(model or {}, fallback_model_id=model_id)
        if not entry["model_id"]:
            raise ValueError("model_id is required for intelligence model registration")
        models = [item for item in state.get("models", []) if item.get("model_id") != entry["model_id"]]
        entry["updated_at"] = utc_now()
        entry.setdefault("created_at", entry["updated_at"])
        entry["lifecycle_status"] = entry.get("lifecycle_status") or "registered"
        entry["compatibility"] = _compatibility_for_entry(entry, registry)
        models.append(entry)
        state["models"] = sorted(models, key=lambda item: str(item.get("model_id") or ""))
        changed = True
    elif normalized_action == "archive":
        found = False
        for entry in state.get("models", []):
            if entry.get("model_id") == model_id:
                entry["lifecycle_status"] = "archived"
                entry["updated_at"] = utc_now()
                found = True
                changed = True
        if not found:
            warnings.append(f"Model {scrub(model_id)} was not registered.")
    elif normalized_action == "plan_install":
        entry = _profile_for_model(model_id) or _normalize_model_entry(model or {}, fallback_model_id=model_id)
        return {
            "workspace": str(root),
            "action": normalized_action,
            "model": entry,
            "install_plan": _install_plan(entry),
            "warnings": warnings,
            "state": state,
        }
    elif normalized_action == "benchmark_record":
        entry = _normalize_model_entry(model or {}, fallback_model_id=model_id)
        if not entry["model_id"]:
            raise ValueError("model_id is required for benchmark recording")
        benchmark = {
            "id": f"model-bench-{uuid.uuid4().hex[:10]}",
            "model_id": entry["model_id"],
            "created_at": utc_now(),
            "scores": dict(entry.get("benchmark_scores") or {}),
            "latency_ms": entry.get("latency_ms"),
            "workflow_type": entry.get("workflow_type", ""),
            "notes": scrub(str(entry.get("notes") or "")),
        }
        state.setdefault("benchmarks", []).append(benchmark)
        state["benchmarks"] = state["benchmarks"][-200:]
        changed = True
    elif normalized_action != "list":
        warnings.append(f"Unknown lifecycle action {scrub(normalized_action)}; returning current model state.")

    state["updated_at"] = utc_now()
    if persist and changed:
        ProjectMemory(root).write_json(MODEL_STATE_FILE, state)
    return {
        "workspace": str(root),
        "action": normalized_action,
        "state": state,
        "recommended_profiles": DEFAULT_LOCAL_MODEL_PROFILES,
        "registry_snapshot": _registry_summary(registry),
        "compatibility": _model_compatibility_summary(state, registry),
        "warnings": warnings,
    }


def retrieval_index(
    workspace: str | Path,
    *,
    query: str = "",
    focus: str = "",
    limit: int = 25,
    refresh: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    scan = WorkspaceScanner(root).scan(persist=persist or refresh)
    graph = _safe_call(lambda: knowledge_graph(root, persist=persist, scan=scan, refresh=refresh), {"nodes": [], "edges": []})
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
    records = _retrieval_records(root, nodes, scan)
    vector_query = query or focus or root.name
    vector_results = _vector_search(vector_query, records, limit=limit)
    graph_results = _safe_call(lambda: search_knowledge(root, vector_query, limit=limit, persist=persist), {"results": []})
    hybrid = _hybrid_results(vector_results, graph_results.get("results", []), limit=limit)
    index = {
        "workspace": str(root),
        "generated_at": utc_now(),
        "query": scrub(vector_query),
        "index_status": {
            "record_count": len(records),
            "graph_nodes": len(nodes),
            "graph_edges": len(graph.get("edges", []) if isinstance(graph.get("edges"), list) else []),
            "embedding_backend": "deterministic-local-hash",
            "local_embedding_model": _preferred_embedding_model(root),
            "refresh": bool(refresh),
        },
        "semantic_index": {
            "records": records[:500],
            "vector_dimensions": 64,
            "tokenizer": "local-regex",
        },
        "graph_aware_retrieval": {
            "results": graph_results.get("results", []),
            "indexing": graph.get("indexing", {}),
        },
        "hybrid_retrieval": {
            "results": hybrid,
            "strategy": "weighted keyword/vector overlap plus graph node search",
            "context_efficiency": _context_efficiency(hybrid),
        },
        "workspace_embeddings": _embedding_scope("workspace", scan.get("file_count", 0), records),
        "memory_embeddings": _embedding_scope("memory", len(_memory_records(root)), records),
        "architecture_embeddings": _embedding_scope("architecture", len(graph.get("clusters", []) or []), records),
        "quality": _retrieval_quality(vector_query, hybrid, records),
        "state_file": str(ProjectMemory(root).root / RETRIEVAL_INDEX_FILE),
    }
    if persist:
        ProjectMemory(root).write_json(RETRIEVAL_INDEX_FILE, index)
    return index


def route_intelligence(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
    route_profile: str | None = None,
    required_capabilities: list[str] | None = None,
    privacy_sensitive: bool = False,
    allow_cloud: bool = False,
    cloud_approved: bool = False,
    context_files: list[str] | None = None,
    local_failure_reason: str | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    component_id = _component_for_workflow(workflow_type, objective, required_capabilities or [])
    profile = route_profile or _route_profile_for_component(component_id, privacy_sensitive)
    capabilities = _capabilities_for_component(component_id, required_capabilities or [])
    model_state = _model_state(root)
    selected_intel_model = _select_intelligence_model(model_state, component_id, capabilities)
    route = route_model(
        root,
        task_type=_task_type_for_workflow(workflow_type),
        difficulty=_difficulty_for_workflow(workflow_type, objective, target_files or []),
        allow_cloud=allow_cloud,
        cloud_approved=cloud_approved,
        context_files=context_files or target_files or [],
        local_failure_reason=local_failure_reason,
        route_profile=profile,
        workflow_type=workflow_type,
        required_capabilities=capabilities,
        privacy_sensitive=privacy_sensitive,
    )
    result = {
        "workspace": str(root),
        "generated_at": utc_now(),
        "workflow_type": workflow_type,
        "objective": scrub(objective),
        "component": {**INTELLIGENCE_COMPONENTS[component_id], "id": component_id},
        "selected_intelligence_model": selected_intel_model,
        "route": route,
        "routing_quality": _routing_quality(route, selected_intel_model, privacy_sensitive),
        "fallback_chain": _intelligence_fallback_chain(model_state, component_id, route),
        "privacy": {
            "privacy_sensitive": bool(privacy_sensitive),
            "local_first": True,
            "cloud_allowed": bool(allow_cloud and cloud_approved and not privacy_sensitive),
            "warnings": _privacy_warnings(route, privacy_sensitive),
        },
        "explanation": _route_explanation(route, selected_intel_model, component_id),
    }
    return result


def orchestration_prediction(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    intelligence = engineering_intelligence(
        root,
        workflow_type=workflow_type,
        objective=objective,
        target_files=target_files or [],
        persist=True,
    )
    prediction = dict(intelligence.get("workflow_prediction", {}))
    validation = dict(intelligence.get("validation_intelligence", {}))
    repair = dict(intelligence.get("repair_intelligence", {}))
    return {
        "workspace": str(root),
        "workflow_type": workflow_type,
        "generated_at": utc_now(),
        "prediction": prediction,
        "lightweight_models": {
            "risk_classifier": "deterministic-local-v1",
            "validation_classifier": "deterministic-local-v1",
            "repair_strategy_selector": "deterministic-local-v1",
            "future_local_model_profile": "local_orchestration",
        },
        "validation_classification": _validation_classification(validation),
        "repair_classification": _repair_classification(repair),
        "execution_guidance": _execution_guidance(prediction, validation, repair),
    }


def run_benchmarks(
    workspace: str | Path,
    *,
    suites: list[str] | None = None,
    workflow_type: str = "generate_feature",
    objective: str = "",
    target_files: list[str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    selected_suites = _selected_suites(suites)
    engineering = run_engineering_benchmarks(root, workflow_type=workflow_type, objective=objective, target_files=target_files or [], persist=persist)
    retrieval = retrieval_index(root, query=objective, persist=persist, limit=20)
    route = route_intelligence(root, workflow_type=workflow_type, objective=objective, target_files=target_files or [], privacy_sensitive=True)
    prediction = orchestration_prediction(root, workflow_type=workflow_type, objective=objective, target_files=target_files or [])
    scores = {
        "repair_quality": engineering.get("benchmark_run", {}).get("scores", {}).get("repair_quality", 0),
        "validation_prediction": _score_level(prediction.get("validation_classification", {}).get("confidence", {})),
        "roadmap_quality": engineering.get("benchmark_run", {}).get("scores", {}).get("roadmap_quality", 0),
        "orchestration_quality": engineering.get("benchmark_run", {}).get("scores", {}).get("orchestration_efficiency", 0),
        "retrieval_accuracy": retrieval.get("quality", {}).get("score", 0),
        "context_efficiency": retrieval.get("hybrid_retrieval", {}).get("context_efficiency", {}).get("score", 0),
        "routing_quality": route.get("routing_quality", {}).get("score", 0),
        "execution_reliability": engineering.get("benchmark_run", {}).get("scores", {}).get("execution_reliability", 0),
    }
    run = {
        "id": f"intel-bench-{uuid.uuid4().hex[:12]}",
        "workspace": str(root),
        "created_at": utc_now(),
        "workflow_type": workflow_type,
        "suites": selected_suites,
        "scores": {key: int(max(0, min(100, value))) for key, value in scores.items() if key in selected_suites or not suites},
        "summary": _benchmark_summary(scores),
        "inputs": {"objective": scrub(objective), "target_files": target_files or []},
    }
    history = _benchmark_history(root)
    history.append(run)
    history = history[-200:]
    if persist:
        ProjectMemory(root).write_json(BENCHMARK_FILE, history)
    return {"workspace": str(root), "benchmark_run": run, "history": list(reversed(history[-50:])), "benchmark_suites": _benchmark_suites(), "path": str(ProjectMemory(root).root / BENCHMARK_FILE)}


def benchmark_dashboard(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _workspace_root(workspace)
    history = _benchmark_history(root)
    return {
        "workspace": str(root),
        "history": list(reversed(history[-max(1, min(200, int(limit or 50))):])),
        "benchmark_suites": _benchmark_suites(),
        "trends": _benchmark_trends(history),
        "path": str(ProjectMemory(root).root / BENCHMARK_FILE),
    }


def dataset_foundations(
    workspace: str | Path,
    *,
    include_sensitive: bool = False,
    limit: int = 100,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    memory = ProjectMemory(root)
    max_items = max(1, min(500, int(limit or 100)))
    sources = [
        "engineering-executions.json",
        "engineering-journal.json",
        "engineering-intelligence.json",
        "engineering-intelligence-benchmarks.json",
        "quality-gate-runs.json",
        "validation-results.json",
        "autopilot-runs.json",
        "autopilot-memory.json",
        "workflow-runtime.json",
        "knowledge-summary.md",
    ]
    records: list[dict[str, Any]] = []
    for source in sources:
        path = memory.root / source
        if not path.exists() or not path.is_file():
            continue
        records.extend(_dataset_records_from_file(path, include_sensitive=include_sensitive, limit=max_items - len(records)))
        if len(records) >= max_items:
            break
    dataset = {
        "workspace": str(root),
        "generated_at": utc_now(),
        "privacy": {
            "include_sensitive": bool(include_sensitive),
            "default": "redacted-local-only",
            "cloud_upload_allowed": False,
        },
        "records": records[:max_items],
        "record_count": min(len(records), max_items),
        "categories": dict(Counter(record.get("category", "unknown") for record in records)),
        "dataset_schema": {
            "fields": ["id", "category", "source", "created_at", "summary", "features", "labels", "privacy"],
            "purpose": "Evaluation and future local fine-tuning/adapter experiments, not automatic training.",
        },
        "export_path": str(memory.root / DATASET_FILE),
    }
    if persist:
        memory.write_json(DATASET_FILE, dataset)
    return dataset


def distributed_inference_plan(
    workspace: str | Path,
    *,
    workflow_type: str = "generate_feature",
    model_id: str = "",
    allow_remote: bool = False,
    approval: bool = False,
    dry_run: bool = True,
    payload: Mapping[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    try:
        from . import distributed_runtime

        workload_payload = {
            "model_id": model_id,
            "workflow_type": workflow_type,
            "intelligence_stack": True,
            **dict(payload or {}),
        }
        created = distributed_runtime.create_workload(
            root,
            workload_type="model_inference",
            workflow_type=workflow_type,
            title=f"Intelligence model inference: {model_id or 'auto'}",
            required_capabilities=["model_inference"],
            permission_scopes=["model_access"],
            allow_remote=allow_remote,
            payload=workload_payload,
            dry_run=dry_run,
            approval=approval,
            source_client="intelligence_stack",
        ) if persist else {"workload": {"workload_type": "model_inference", "dry_run": dry_run, "payload": workload_payload}}
        dashboard = distributed_runtime.runtime_dashboard(root, include_audit=False) if persist else distributed_runtime.runtime_dashboard(root, include_audit=False)
        nodes = dashboard.get("nodes", [])
        eligible = [
            node for node in nodes
            if "model_inference" in (node.get("capabilities") or []) and node.get("trust_level") in {"local", "trusted"}
        ]
        return {
            "workspace": str(root),
            "workflow_type": workflow_type,
            "model_id": scrub(model_id),
            "dry_run": bool(dry_run),
            "allow_remote": bool(allow_remote),
            "approval": bool(approval),
            "workload": created.get("workload", {}),
            "eligible_nodes": eligible,
            "fallback": {
                "primary": eligible[0].get("node_id") if eligible else "local",
                "fallback_node_ids": ["local"],
                "reason": "Local Core remains authority; remote model nodes require trust, opt-in remote dispatch, and approval where needed.",
            },
            "warnings": [] if eligible else ["No trusted model inference node is currently online; use local Core routing fallback."],
        }
    except Exception as exc:  # pragma: no cover - defensive integration boundary
        return {
            "workspace": str(root),
            "workflow_type": workflow_type,
            "model_id": scrub(model_id),
            "dry_run": bool(dry_run),
            "allow_remote": bool(allow_remote),
            "approval": bool(approval),
            "workload": {},
            "eligible_nodes": [],
            "fallback": {"primary": "local", "fallback_node_ids": ["local"]},
            "warnings": [f"Distributed inference planning unavailable: {scrub(str(exc))}"],
        }


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).resolve()
    if not root.exists():
        raise ValueError(f"workspace does not exist: {scrub(str(root))}")
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {scrub(str(root))}")
    return root


def _project_id(root: Path) -> str:
    return hashlib.sha256(str(root).lower().encode("utf-8")).hexdigest()[:16]


def _state_files(root: Path) -> dict[str, str]:
    memory = ProjectMemory(root)
    return {
        "dashboard": str(memory.root / STACK_FILE),
        "models": str(memory.root / MODEL_STATE_FILE),
        "retrieval": str(memory.root / RETRIEVAL_INDEX_FILE),
        "benchmarks": str(memory.root / BENCHMARK_FILE),
        "datasets": str(memory.root / DATASET_FILE),
    }


def _architecture() -> dict[str, Any]:
    return {
        "layers": [
            {"id": "models", "description": "Local-first specialized model lifecycle metadata and compatibility."},
            {"id": "retrieval", "description": "Hybrid graph/vector retrieval and embedding-ready workspace indexes."},
            {"id": "routing", "description": "Workflow-aware local/cloud route decisions and fallback explanations."},
            {"id": "orchestration", "description": "Lightweight local prediction/classification for workflow control."},
            {"id": "evaluation", "description": "Benchmark and dataset foundations from local workflow traces."},
            {"id": "distributed_inference", "description": "Trusted runtime-node planning for GPU/model/embedding workers."},
        ],
        "non_goals": [
            "No automatic training.",
            "No external model download.",
            "No cloud upload of workspace traces.",
            "No bypass of validation, approval, checkpoint, or governance systems.",
        ],
    }


def _model_state(root: Path) -> dict[str, Any]:
    memory = ProjectMemory(root)
    path = memory.root / MODEL_STATE_FILE
    if path.exists() and path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                state = dict(loaded)
            else:
                state = {}
        except (OSError, json.JSONDecodeError):
            state = {}
    else:
        state = {}
    state.setdefault("schema_version", 1)
    state.setdefault("workspace", str(root))
    state.setdefault("models", [])
    state.setdefault("benchmarks", [])
    state.setdefault("updated_at", utc_now())
    return state


def _normalize_model_entry(model: Mapping[str, Any], *, fallback_model_id: str = "") -> dict[str, Any]:
    model_id = scrub(str(model.get("model_id") or model.get("id") or fallback_model_id or "")).strip()
    provider_id = scrub(str(model.get("provider_id") or "ollama")).strip() or "ollama"
    capabilities = _clean_list(model.get("capabilities") or [])
    specializations = _clean_list(model.get("specializations") or model.get("roles") or [])
    return {
        "model_id": model_id,
        "display_name": scrub(str(model.get("display_name") or model_id)),
        "provider_id": provider_id,
        "version": scrub(str(model.get("version") or "local")),
        "lifecycle_status": scrub(str(model.get("lifecycle_status") or "registered")),
        "specializations": specializations,
        "capabilities": capabilities,
        "quantization": dict(model.get("quantization") or _infer_quantization(model_id)),
        "compatibility": dict(model.get("compatibility") or {}),
        "source": scrub(str(model.get("source") or "manual")),
        "checksum": scrub(str(model.get("checksum") or "")),
        "benchmark_scores": dict(model.get("benchmark_scores") or {}),
        "notes": scrub(str(model.get("notes") or "")),
        "created_at": scrub(str(model.get("created_at") or utc_now())),
    }


def _profile_for_model(model_id: str) -> dict[str, Any] | None:
    clean = str(model_id or "").strip().lower()
    for profile in DEFAULT_LOCAL_MODEL_PROFILES:
        if profile["model_id"].lower() == clean:
            return dict(profile)
    return None


def _infer_quantization(model_id: str) -> dict[str, Any]:
    lowered = model_id.lower()
    match = re.search(r"q(\d+)", lowered)
    if "embed" in lowered:
        return {"format": "embedding", "memory_gb_estimate": 2.0, "cpu_usable": True, "gpu_recommended": False}
    if match:
        bits = int(match.group(1))
        return {"format": f"q{bits}", "memory_gb_estimate": 4.0 if bits <= 4 else 8.0, "cpu_usable": bits <= 5, "gpu_recommended": bits > 5}
    return {"format": "unknown", "memory_gb_estimate": 8.0, "cpu_usable": True, "gpu_recommended": False}


def _compatibility_for_entry(entry: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    installed = {str(model.get("model_id") or model.get("model") or "") for model in registry.get("models", []) if isinstance(model, Mapping)}
    is_installed = str(entry.get("model_id") or "") in installed
    quant = entry.get("quantization") if isinstance(entry.get("quantization"), Mapping) else {}
    return {
        **dict(entry.get("compatibility") or {}),
        "installed": is_installed,
        "runtime_available": bool(registry.get("providers")),
        "quantization_supported": bool(quant.get("format")),
        "status": "installed" if is_installed else "registered_not_installed",
    }


def _install_plan(entry: Mapping[str, Any]) -> dict[str, Any]:
    provider = str(entry.get("provider_id") or "ollama")
    model_id = str(entry.get("model_id") or "")
    commands = []
    if provider == "ollama" and model_id:
        commands.append(["ollama", "pull", model_id])
    return {
        "provider_id": provider,
        "model_id": model_id,
        "commands": commands,
        "approval_required": True,
        "executes_now": False,
        "notes": [
            "Core records the installation plan only; clients must ask before running provider installers.",
            "Verify disk/RAM/GPU suitability before installation.",
        ],
    }


def _registry_summary(registry: Mapping[str, Any]) -> dict[str, Any]:
    models = [model for model in registry.get("models", []) if isinstance(model, Mapping)]
    providers = [provider for provider in registry.get("providers", []) if isinstance(provider, Mapping)]
    return {
        "model_count": len(models),
        "provider_count": len(providers),
        "selected_model": registry.get("selected_model") or {},
        "local_models": [model for model in models if model.get("local")][:20],
    }


def _installable_profiles(registry: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    known = {str(model.get("model_id") or "") for model in state.get("models", []) if isinstance(model, Mapping)}
    installed = {str(model.get("model_id") or model.get("model") or "") for model in registry.get("models", []) if isinstance(model, Mapping)}
    profiles = []
    for profile in DEFAULT_LOCAL_MODEL_PROFILES:
        item = dict(profile)
        item["registered"] = item["model_id"] in known
        item["installed"] = item["model_id"] in installed
        profiles.append(item)
    return profiles


def _model_compatibility_summary(state: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    models = [model for model in state.get("models", []) if isinstance(model, Mapping)]
    installed = {str(model.get("model_id") or model.get("model") or "") for model in registry.get("models", []) if isinstance(model, Mapping)}
    return {
        "registered_count": len(models),
        "installed_registered_count": sum(1 for model in models if model.get("model_id") in installed),
        "missing_registered_models": [model.get("model_id") for model in models if model.get("model_id") not in installed],
        "quantization_awareness": dict(Counter(str((model.get("quantization") or {}).get("format") or "unknown") for model in models)),
    }


def _component_status(state: Mapping[str, Any], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **dict(component),
            "id": component_id,
            "models": _models_for_component(state, component_id),
            "recommended_models": [profile for profile in DEFAULT_LOCAL_MODEL_PROFILES if component_id in profile.get("specializations", [])],
            "status": "ready" if _models_for_component(state, component_id) or component_id == "routing" else "profile_only",
            "registry_model_count": len(registry.get("models", []) if isinstance(registry.get("models"), list) else []),
        }
        for component_id, component in INTELLIGENCE_COMPONENTS.items()
    ]


def _models_for_component(state: Mapping[str, Any], component_id: str) -> list[dict[str, Any]]:
    return [
        dict(model)
        for model in state.get("models", [])
        if isinstance(model, Mapping) and (component_id in (model.get("specializations") or []) or set(INTELLIGENCE_COMPONENTS[component_id]["capabilities"]).intersection(set(model.get("capabilities") or [])))
    ]


def _retrieval_records(root: Path, nodes: list[Mapping[str, Any]], scan: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        path = str(node.get("path") or "")
        label = str(node.get("label") or node.get("id") or path)
        text = " ".join(str(node.get(key) or "") for key in ("id", "label", "type", "path"))
        record_id = str(node.get("id") or path or label)
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        records.append(
            {
                "id": record_id,
                "path": path,
                "label": scrub(label),
                "type": scrub(str(node.get("type") or "node")),
                "tokens": sorted(_tokens(text))[:80],
                "embedding": _hash_embedding(text),
                "source": "knowledge_graph",
            }
        )
    for path in (scan.get("recent_files") or [])[:100]:
        if path in seen:
            continue
        seen.add(str(path))
        preview = _preview(root, str(path), max_chars=500)
        records.append({"id": f"file:{path}", "path": str(path), "label": Path(str(path)).name, "type": "file", "tokens": sorted(_tokens(str(path) + " " + preview))[:80], "embedding": _hash_embedding(str(path) + " " + preview), "source": "workspace_scan"})
    return records


def _vector_search(query: str, records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    query_embedding = _hash_embedding(query)
    results = []
    for record in records:
        token_overlap = len(query_tokens.intersection(set(record.get("tokens") or [])))
        vector_score = _cosine(query_embedding, record.get("embedding") or [])
        score = round(token_overlap * 12 + vector_score * 100, 3)
        if score > 0:
            results.append({k: v for k, v in record.items() if k != "embedding"} | {"score": score, "vector_score": round(vector_score, 3), "token_overlap": token_overlap})
    results.sort(key=lambda item: (float(item.get("score") or 0), str(item.get("label") or "")), reverse=True)
    return results[: max(1, min(100, int(limit or 25)))]


def _hybrid_results(vector_results: list[dict[str, Any]], graph_results: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in vector_results:
        key = str(item.get("id") or item.get("path") or item.get("label"))
        merged[key] = {**item, "hybrid_score": float(item.get("score") or 0), "sources": ["local_vector"]}
    for item in graph_results:
        key = str(item.get("id") or item.get("path") or item.get("label"))
        existing = merged.setdefault(key, {**item, "hybrid_score": 0, "sources": []})
        existing["hybrid_score"] = float(existing.get("hybrid_score") or 0) + float(item.get("score") or 0) * 20 + 15
        if "knowledge_graph" not in existing["sources"]:
            existing.setdefault("sources", []).append("knowledge_graph")
    ranked = sorted(merged.values(), key=lambda item: (float(item.get("hybrid_score") or 0), str(item.get("label") or "")), reverse=True)
    return ranked[: max(1, min(100, int(limit or 25)))]


def _embedding_scope(scope: str, source_count: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scope": scope,
        "source_count": int(source_count or 0),
        "ready": bool(records),
        "backend": "deterministic-local-hash",
        "future_provider_interface": "local embedding model or trusted embedding node",
    }


def _retrieval_quality(query: str, hybrid: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    score = 20
    if records:
        score += 25
    if hybrid:
        score += 35
    if query and hybrid and any(item.get("token_overlap", 0) for item in hybrid):
        score += 15
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high", "result_count": len(hybrid), "record_count": len(records)}


def _context_efficiency(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"score": 0, "basis": "no retrieval results"}
    top = sum(float(item.get("hybrid_score") or item.get("score") or 0) for item in results[:5])
    tail = sum(float(item.get("hybrid_score") or item.get("score") or 0) for item in results[5:20])
    score = int(max(20, min(100, 50 + top / max(1, top + tail) * 50)))
    return {"score": score, "basis": "top retrieval concentration and result availability"}


def _preferred_embedding_model(root: Path) -> dict[str, Any]:
    state = _model_state(root)
    for model in state.get("models", []):
        if isinstance(model, Mapping) and ("embeddings" in (model.get("capabilities") or []) or "retrieval" in (model.get("specializations") or [])):
            return dict(model)
    return next(profile for profile in DEFAULT_LOCAL_MODEL_PROFILES if "retrieval" in profile["specializations"])


def _component_for_workflow(workflow_type: str, objective: str, capabilities: list[str]) -> str:
    text = f"{workflow_type} {objective} {' '.join(capabilities)}".lower()
    if "repair" in text or "fix" in text or "failure" in text:
        return "repair"
    if "validate" in text or "test" in text or "build" in text:
        return "validation_classifier"
    if "roadmap" in text or "plan" in text or "feature" in text:
        return "planning"
    if "search" in text or "retrieve" in text or "index" in text or "embedding" in text:
        return "retrieval"
    if "summary" in text or "architecture" in text:
        return "summarization"
    return "orchestration"


def _route_profile_for_component(component_id: str, privacy_sensitive: bool) -> str:
    if privacy_sensitive:
        return "private_sensitive"
    return {
        "repair": "best_coding",
        "planning": "best_reasoning",
        "retrieval": "local_only",
        "validation_classifier": "local_only",
        "routing": "fallback_safe",
        "summarization": "balanced",
        "orchestration": "local_only",
    }.get(component_id, "balanced")


def _capabilities_for_component(component_id: str, requested: list[str]) -> list[str]:
    return sorted(set(requested) | set(INTELLIGENCE_COMPONENTS[component_id]["capabilities"][:2]))


def _select_intelligence_model(state: Mapping[str, Any], component_id: str, capabilities: list[str]) -> dict[str, Any]:
    candidates = []
    for model in state.get("models", []):
        if not isinstance(model, Mapping) or model.get("lifecycle_status") == "archived":
            continue
        model_caps = set(model.get("capabilities") or [])
        score = len(set(capabilities).intersection(model_caps)) * 20
        if component_id in (model.get("specializations") or []):
            score += 50
        if score:
            candidates.append((score, dict(model)))
    if candidates:
        candidates.sort(key=lambda item: (item[0], str(item[1].get("model_id") or "")), reverse=True)
        selected = candidates[0][1]
        selected["selection_score"] = candidates[0][0]
        return selected
    for profile in DEFAULT_LOCAL_MODEL_PROFILES:
        if component_id in profile.get("specializations", []):
            return {**profile, "selection_score": 25, "lifecycle_status": "profile_only"}
    return {**DEFAULT_LOCAL_MODEL_PROFILES[-1], "selection_score": 10, "lifecycle_status": "profile_only"}


def _intelligence_fallback_chain(state: Mapping[str, Any], component_id: str, route: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = []
    for model in _models_for_component(state, component_id)[:5]:
        chain.append({"type": "specialized_local", "model_id": model.get("model_id"), "provider_id": model.get("provider_id"), "status": model.get("lifecycle_status")})
    selected = route.get("selected") if isinstance(route.get("selected"), Mapping) else {}
    if selected:
        chain.append({"type": "core_model_route", "model_id": selected.get("model_id") or selected.get("model"), "provider_id": selected.get("provider_id"), "status": selected.get("status")})
    return chain


def _routing_quality(route: Mapping[str, Any], selected: Mapping[str, Any], privacy_sensitive: bool) -> dict[str, Any]:
    score = 45
    if selected:
        score += 20
    if route.get("selected"):
        score += 20
    if route.get("approval_required"):
        score -= 12
    if privacy_sensitive and not route.get("local_only", True):
        score -= 30
    if route.get("missing_capability_warnings"):
        score -= min(20, len(route.get("missing_capability_warnings", [])) * 5)
    score = max(0, min(100, score))
    return {"score": score, "level": "low" if score < 45 else "medium" if score < 75 else "high"}


def _route_explanation(route: Mapping[str, Any], selected: Mapping[str, Any], component_id: str) -> dict[str, Any]:
    selected_route = route.get("selected") if isinstance(route.get("selected"), Mapping) else {}
    return {
        "component": component_id,
        "selected_intelligence_model": selected.get("model_id", ""),
        "selected_core_route": {
            "provider_id": selected_route.get("provider_id"),
            "model": selected_route.get("model_id") or selected_route.get("model"),
            "local": selected_route.get("local", True),
        },
        "reason": "Selected a specialized local intelligence profile first, then mapped the workflow to Core model routing for provider execution.",
        "fallback_reason": route.get("cloud_reason") or "local-first route available",
        "missing_capabilities": route.get("missing_capability_warnings", []),
    }


def _privacy_warnings(route: Mapping[str, Any], privacy_sensitive: bool) -> list[str]:
    warnings = []
    if privacy_sensitive and not route.get("local_only", True):
        warnings.append("Privacy-sensitive routing should remain local-only.")
    warnings.extend(str(item) for item in route.get("warnings", []) if "Cloud" in str(item) or "cloud" in str(item))
    return warnings


def _task_type_for_workflow(workflow_type: str) -> str:
    return {
        "repair_project": "hard_debugging",
        "generate_feature": "code_completion",
        "continue_roadmap": "repo_wide_planning",
        "scan_workspace": "summarization",
        "validate_project": "hard_debugging",
        "research_task": "research_task",
        "generate_media": "generate_media",
    }.get(workflow_type, "chat")


def _difficulty_for_workflow(workflow_type: str, objective: str, target_files: list[str]) -> str:
    text = f"{workflow_type} {objective}".lower()
    if len(target_files) > 6 or any(term in text for term in ("architecture", "distributed", "deployment", "repair", "refactor")):
        return "hard"
    if len(target_files) > 2 or any(term in text for term in ("feature", "roadmap", "validate")):
        return "medium"
    return "simple"


def _validation_classification(validation: Mapping[str, Any]) -> dict[str, Any]:
    confidence = validation.get("validation_confidence", {}) if isinstance(validation.get("validation_confidence"), Mapping) else {}
    prioritized = validation.get("prioritized_validations", []) if isinstance(validation.get("prioritized_validations"), list) else []
    return {
        "class": "validation_ready" if prioritized else "validation_command_needed",
        "confidence": confidence,
        "recommended_first_check": prioritized[0] if prioritized else {},
    }


def _repair_classification(repair: Mapping[str, Any]) -> dict[str, Any]:
    roots = repair.get("root_cause_candidates", []) if isinstance(repair.get("root_cause_candidates"), list) else []
    return {
        "class": roots[0].get("cause", "unknown") if roots and isinstance(roots[0], Mapping) else "no_failure_signal",
        "confidence": repair.get("repair_confidence", {}),
        "rollback_recommended": bool(repair.get("rollback_recommendation", {}).get("recommended")) if isinstance(repair.get("rollback_recommendation"), Mapping) else False,
    }


def _execution_guidance(prediction: Mapping[str, Any], validation: Mapping[str, Any], repair: Mapping[str, Any]) -> list[str]:
    guidance = []
    risk = prediction.get("execution_risk", {}) if isinstance(prediction.get("execution_risk"), Mapping) else {}
    if risk.get("level") in {"high", "critical"}:
        guidance.append("Use approval_each_step or semi_autonomous mode with explicit validation before apply.")
    if not validation.get("prioritized_validations"):
        guidance.append("Ask for or configure a validation command before applying generated changes.")
    if repair.get("root_cause_candidates"):
        guidance.append("Start repair with the highest-confidence root cause and stop after repeated failed signatures.")
    return guidance or ["Proceed with local-first routing, bounded context, checkpointing, and targeted validation."]


def _score_level(value: Mapping[str, Any]) -> int:
    if isinstance(value.get("score"), (int, float)):
        return int(value["score"])
    return {"low": 35, "medium": 65, "high": 85}.get(str(value.get("level") or "").lower(), 50)


def _benchmark_suites() -> list[dict[str, Any]]:
    return [
        {"id": "repair_quality", "description": "Root-cause and repair strategy quality."},
        {"id": "validation_prediction", "description": "Validation command prioritization and confidence."},
        {"id": "roadmap_quality", "description": "Roadmap decomposition and dependency ordering."},
        {"id": "orchestration_quality", "description": "Workflow planning and context efficiency."},
        {"id": "retrieval_accuracy", "description": "Hybrid retrieval result quality."},
        {"id": "context_efficiency", "description": "Context relevance per token budget."},
        {"id": "routing_quality", "description": "Capability, privacy, fallback, and availability fit."},
        {"id": "execution_reliability", "description": "Predicted execution reliability."},
    ]


def _selected_suites(suites: list[str] | None) -> list[str]:
    valid = {suite["id"] for suite in _benchmark_suites()}
    selected = [suite for suite in (suites or []) if suite in valid]
    return selected or sorted(valid)


def _benchmark_summary(scores: Mapping[str, Any]) -> dict[str, Any]:
    values = [float(value) for value in scores.values() if isinstance(value, (int, float))]
    average = round(sum(values) / len(values), 2) if values else 0
    return {
        "average_score": average,
        "level": "low" if average < 45 else "medium" if average < 75 else "high",
        "weakest": min(scores, key=lambda key: scores[key]) if scores else "",
        "strongest": max(scores, key=lambda key: scores[key]) if scores else "",
    }


def _benchmark_history(root: Path) -> list[dict[str, Any]]:
    path = ProjectMemory(root).root / BENCHMARK_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _benchmark_trends(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"run_count": 0, "average_scores": {}}
    counters: dict[str, list[float]] = {}
    for run in history:
        for key, value in (run.get("scores") or {}).items():
            if isinstance(value, (int, float)):
                counters.setdefault(key, []).append(float(value))
    return {"run_count": len(history), "average_scores": {key: round(sum(values) / len(values), 2) for key, values in counters.items() if values}}


def _dataset_records_from_file(path: Path, *, include_sensitive: bool, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    redacted = text if include_sensitive else scrub(text)
    records = []
    try:
        parsed = json.loads(redacted)
        entries = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        entries = [{"summary": redacted[:2000]}]
    for entry in entries[:limit]:
        text_value = json.dumps(entry, sort_keys=True, default=str) if isinstance(entry, Mapping) else str(entry)
        records.append(
            {
                "id": f"dataset-{hashlib.sha256((str(path) + text_value[:200]).encode('utf-8')).hexdigest()[:12]}",
                "category": _dataset_category(path.name),
                "source": path.name,
                "created_at": utc_now(),
                "summary": scrub(text_value[:800]) if not include_sensitive else text_value[:800],
                "features": {"tokens": sorted(_tokens(text_value))[:60], "source_size": len(text_value)},
                "labels": _dataset_labels(path.name, text_value),
                "privacy": {"redacted": not include_sensitive, "local_only": True},
            }
        )
    return records


def _dataset_category(name: str) -> str:
    lowered = name.lower()
    if "repair" in lowered:
        return "repair_examples"
    if "validation" in lowered or "quality" in lowered:
        return "validation_outcomes"
    if "workflow" in lowered or "execution" in lowered or "autopilot" in lowered:
        return "workflow_traces"
    if "knowledge" in lowered or "architecture" in lowered:
        return "architecture_summaries"
    return "project_memory"


def _dataset_labels(name: str, text: str) -> dict[str, Any]:
    lowered = text.lower()
    return {
        "success_signal": any(term in lowered for term in ("passed", "completed", "success")),
        "failure_signal": any(term in lowered for term in ("failed", "error", "blocked")),
        "repair_signal": "repair" in lowered,
        "source_type": _dataset_category(name),
    }


def _observability(root: Path, state: Mapping[str, Any], benchmarks: Mapping[str, Any], retrieval: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model_count": len(state.get("models", []) if isinstance(state.get("models"), list) else []),
        "benchmark_runs": len(benchmarks.get("history", []) if isinstance(benchmarks.get("history"), list) else []),
        "retrieval_record_count": retrieval.get("index_status", {}).get("record_count", 0),
        "routing_quality": route.get("routing_quality", {}),
        "state_size_bytes": _state_size(root),
    }


def _ui_visibility(route: Mapping[str, Any], retrieval: Mapping[str, Any], prediction: Mapping[str, Any], distributed: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selected_intelligence_profile": route.get("component", {}).get("preferred_profile", ""),
        "selected_model": route.get("selected_intelligence_model", {}),
        "local_cloud_route": route.get("route", {}).get("mode", "local_only"),
        "embedding_index_status": retrieval.get("index_status", {}),
        "workflow_confidence": prediction.get("prediction", {}).get("prediction_confidence", {}),
        "distributed_inference_status": {
            "eligible_node_count": len(distributed.get("eligible_nodes", []) if isinstance(distributed.get("eligible_nodes"), list) else []),
            "dry_run": distributed.get("dry_run", True),
            "allow_remote": distributed.get("allow_remote", False),
        },
    }


def _recommendations(state: Mapping[str, Any], registry: Mapping[str, Any], retrieval: Mapping[str, Any], route: Mapping[str, Any], dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    if not state.get("models"):
        recommendations.append({"priority": "high", "area": "models", "recommendation": "Register local specialized model profiles before enabling model-backed intelligence."})
    if retrieval.get("quality", {}).get("level") == "low":
        recommendations.append({"priority": "medium", "area": "retrieval", "recommendation": "Refresh the knowledge graph and add an embedding model for better retrieval quality."})
    if route.get("routing_quality", {}).get("level") == "low":
        recommendations.append({"priority": "medium", "area": "routing", "recommendation": "Install or register a local model that matches the selected intelligence component."})
    if not dataset.get("records"):
        recommendations.append({"priority": "low", "area": "datasets", "recommendation": "Run workflows and validations to build local evaluation traces."})
    if not registry.get("models"):
        recommendations.append({"priority": "medium", "area": "local_runtime", "recommendation": "Connect Ollama or another local runtime for local-first provider execution."})
    return recommendations


def _state_size(root: Path) -> int:
    total = 0
    memory = ProjectMemory(root).root
    for name in (STACK_FILE, MODEL_STATE_FILE, RETRIEVAL_INDEX_FILE, BENCHMARK_FILE, DATASET_FILE):
        path = memory / name
        if path.exists() and path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def _memory_records(root: Path) -> list[dict[str, Any]]:
    memory = ProjectMemory(root).root
    records = []
    for path in memory.glob("*.json"):
        try:
            records.append({"path": path.name, "size": path.stat().st_size})
        except OSError:
            continue
    return records


def _preview(root: Path, relative: str, *, max_chars: int) -> str:
    try:
        path = (root / relative).resolve()
        path.relative_to(root)
        if not path.is_file() or not is_safe_to_read(path, root):
            return ""
        return scrub(path.read_text(encoding="utf-8", errors="ignore")[:max_chars])
    except (OSError, RuntimeError, ValueError):
        return ""


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", str(text or "")) if len(token) > 2}


def _hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def _clean_list(values: Any) -> list[str]:
    result = []
    for value in values if isinstance(values, list) else []:
        text = scrub(str(value)).strip()
        if text and text not in result:
            result.append(text)
    return result[:100]


def _safe_call(callback: Any, default: Any) -> Any:
    try:
        return callback()
    except Exception:
        return default
