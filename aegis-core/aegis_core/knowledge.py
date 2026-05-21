from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .safety import is_safe_to_read
from .workspace import SOURCE_CODE_SUFFIXES, WorkspaceScanner


KNOWLEDGE_GRAPH_FILE = "knowledge-graph.json"
KNOWLEDGE_SUMMARY_FILE = "knowledge-summary.md"
KNOWLEDGE_INDEX_STATE_FILE = "knowledge-index-state.json"
SEMANTIC_INDEX_FILE = "semantic-index.json"
PROJECT_MEMORY_FILE = "project-memory.json"
GRAPH_VERSION = "2026.05.12"
PATH_CANDIDATE_SUFFIXES = [
    "",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".cs",
    ".fs",
    ".fsi",
    ".fsx",
    ".vb",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
]

COMMON_WORDS = {
    "about",
    "after",
    "agent",
    "also",
    "and",
    "before",
    "build",
    "change",
    "check",
    "code",
    "core",
    "file",
    "fix",
    "from",
    "into",
    "item",
    "local",
    "module",
    "plan",
    "project",
    "roadmap",
    "system",
    "task",
    "test",
    "that",
    "this",
    "with",
}


class KnowledgePersistenceError(RuntimeError):
    """Raised when persisted knowledge graph artifacts cannot be written."""


def knowledge_graph(
    workspace: str | Path,
    *,
    persist: bool = False,
    scan: dict[str, Any] | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    if persist:
        memory.ensure()
    scan_data = scan or WorkspaceScanner(root).scan(persist=persist)
    manifest = _file_manifest(root, scan_data)
    previous_state = _load_index_state(memory)
    cached = _load_persisted_graph(root)
    incremental = _incremental_status(previous_state, manifest)
    if persist and not refresh and cached and incremental["changed_files"] == [] and incremental["removed_files"] == []:
        cached["cache_hit"] = True
        cached["incremental"] = incremental
        cached.setdefault("indexing", {})["cache_hit"] = True
        return cached

    started = time.perf_counter()
    builder = _GraphBuilder(root, scan_data)
    graph = builder.build()
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    graph["graph_path"] = str(memory.root / KNOWLEDGE_GRAPH_FILE)
    graph["summary_path"] = str(memory.root / KNOWLEDGE_SUMMARY_FILE)
    graph["semantic_index_path"] = str(memory.root / SEMANTIC_INDEX_FILE)
    graph["project_memory_path"] = str(memory.root / PROJECT_MEMORY_FILE)
    graph["cache_hit"] = False
    graph["file_fingerprints"] = manifest
    graph["incremental"] = incremental
    graph["indexing"] = _indexing_observability(graph, incremental, duration_ms, builder.indexing_failures, builder.unsupported_language_areas)
    graph["semantic_index"] = _semantic_index(root, scan_data, graph)
    graph["architecture_summary"] = _architecture_summary_from_graph(root, scan_data, graph)
    graph["project_memory"] = _project_memory_summary(memory)
    graph["embedding_interfaces"] = _embedding_interfaces()
    if persist:
        memory.write_json(KNOWLEDGE_INDEX_STATE_FILE, {"generated_at": utc_now(), "file_fingerprints": manifest})
        memory.write_json(SEMANTIC_INDEX_FILE, graph["semantic_index"])
        memory.write_json(PROJECT_MEMORY_FILE, graph["project_memory"])
        _persist_knowledge_graph(memory, graph)
    return graph


def query_knowledge_graph(
    workspace: str | Path,
    query: str,
    *,
    focus: str | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = _load_persisted_graph(root) or knowledge_graph(root)
    return _query_graph(graph, query, focus=focus)


def search_knowledge(
    workspace: str | Path,
    query: str,
    *,
    node_type: str | None = None,
    limit: int = 25,
    persist: bool = True,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = _load_persisted_graph(root) or knowledge_graph(root, persist=persist)
    terms = _tokens(query)
    max_items = max(1, min(100, int(limit)))
    results: list[dict[str, Any]] = []
    for node in graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []:
        if not isinstance(node, dict):
            continue
        if node_type and node.get("type") != node_type:
            continue
        node_terms = _node_terms(node)
        score = len(terms.intersection(node_terms)) if terms else 0
        exact = str(query).strip().lower() in " ".join(str(node.get(key) or "") for key in ("label", "path", "id")).lower()
        if score or exact:
            results.append({"score": score + (3 if exact else 0), **_small_node(node), "metadata": node.get("metadata", {})})
    results.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("label") or "")), reverse=True)
    return {
        "workspace": str(root),
        "query": scrub(query),
        "node_type": node_type,
        "results": results[:max_items],
        "graph_version": graph.get("version"),
        "indexing": graph.get("indexing", {}),
    }


def knowledge_relationships(
    workspace: str | Path,
    focus: str,
    *,
    relationship: str | None = None,
    depth: int = 1,
    direction: str = "both",
    limit: int = 50,
    persist: bool = True,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = _load_persisted_graph(root) or knowledge_graph(root, persist=persist)
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    node_by_id = {node.get("id"): node for node in nodes}
    focus_node = _find_focus_node(focus, nodes)
    if focus_node is None:
        return {"workspace": str(root), "focus": focus, "focus_node": None, "relationships": [], "nodes": [], "edges": [], "graph_version": graph.get("version")}
    max_depth = max(1, min(4, int(depth)))
    max_items = max(1, min(200, int(limit)))
    allowed_direction = direction if direction in {"incoming", "outgoing", "both"} else "both"
    visited = {str(focus_node["id"])}
    frontier = {str(focus_node["id"])}
    selected_edges: list[dict[str, Any]] = []
    for _ in range(max_depth):
        next_frontier: set[str] = set()
        for edge in edges:
            if relationship and edge.get("type") != relationship:
                continue
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            outgoing = allowed_direction in {"outgoing", "both"} and source in frontier
            incoming = allowed_direction in {"incoming", "both"} and target in frontier
            if not outgoing and not incoming:
                continue
            selected_edges.append(edge)
            other = target if outgoing else source
            if other and other not in visited:
                visited.add(other)
                next_frontier.add(other)
            if len(selected_edges) >= max_items:
                break
        frontier = next_frontier
        if not frontier or len(selected_edges) >= max_items:
            break
    related_nodes = [_small_node(node_by_id[node_id]) for node_id in visited if node_id in node_by_id]
    return {
        "workspace": str(root),
        "focus": focus,
        "focus_node": _small_node(focus_node),
        "relationships": sorted({str(edge.get("type")) for edge in selected_edges if edge.get("type")}),
        "nodes": related_nodes[:max_items],
        "edges": selected_edges[:max_items],
        "graph_version": graph.get("version"),
    }


def knowledge_symbol(workspace: str | Path, symbol: str, *, limit: int = 20) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = _load_persisted_graph(root) or knowledge_graph(root, persist=True)
    terms = _tokens(symbol)
    max_items = max(1, min(100, int(limit)))
    matches: list[dict[str, Any]] = []
    for node in graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []:
        if not isinstance(node, dict) or node.get("type") not in {"class", "function", "method", "service", "ui_component", "symbol", "api"}:
            continue
        exact = str(node.get("label") or "").lower() == str(symbol).strip().lower()
        score = len(terms.intersection(_node_terms(node))) + (5 if exact else 0)
        if score:
            matches.append({"score": score, **_small_node(node), "metadata": node.get("metadata", {})})
    matches.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("path") or "")), reverse=True)
    return {
        "workspace": str(root),
        "symbol": scrub(symbol),
        "matches": matches[:max_items],
        "graph_version": graph.get("version"),
    }


def impact_analysis(
    workspace: str | Path,
    target: str,
    *,
    change_type: str = "modify",
    limit: int = 100,
    persist: bool = True,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = _load_persisted_graph(root) or knowledge_graph(root, persist=persist)
    relationships = knowledge_relationships(root, target, depth=2, limit=limit, persist=persist)
    nodes = relationships.get("nodes", []) if isinstance(relationships.get("nodes"), list) else []
    edges = relationships.get("edges", []) if isinstance(relationships.get("edges"), list) else []
    affected_files = sorted(
        {
            str(node.get("path") or node.get("label"))
            for node in nodes
            if isinstance(node, dict) and node.get("type") == "file" and (node.get("path") or node.get("label"))
        }
    )
    validation_targets = _validation_targets_for_files(graph, affected_files)
    risky_edges = [edge for edge in edges if edge.get("type") in {"depends_on", "calls", "api_consumer", "tested_by", "breaks", "inherits"}]
    likely_breakage = _likely_breakage_areas(graph, nodes, edges)
    related_workflows = _related_workflows(graph, nodes)
    risk_score = min(1.0, 0.15 + len(affected_files) * 0.04 + len(risky_edges) * 0.03 + (0.2 if change_type in {"delete", "move", "rename"} else 0.0))
    risk_level = "low" if risk_score < 0.35 else "medium" if risk_score < 0.7 else "high"
    return {
        "workspace": str(root),
        "target": scrub(target),
        "change_type": scrub(change_type),
        "focus_node": relationships.get("focus_node"),
        "affected_files": affected_files[:limit],
        "likely_breakage_areas": likely_breakage,
        "modification_risk": {
            "level": risk_level,
            "score": round(risk_score, 3),
            "reasons": _risk_reasons(affected_files, risky_edges, change_type),
        },
        "validation_targets": validation_targets,
        "related_workflows": related_workflows,
        "relationship_edges": edges[:limit],
        "graph_version": graph.get("version"),
    }


def architecture_summary(workspace: str | Path, *, refresh: bool = False) -> dict[str, Any]:
    root = Path(workspace).resolve()
    graph = knowledge_graph(root, persist=True, refresh=True) if refresh else (_load_persisted_graph(root) or knowledge_graph(root, persist=False))
    return {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": utc_now(),
        "summary": graph.get("architecture_summary", {}),
        "clusters": graph.get("clusters", []),
        "runtime_boundaries": [node for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("type") == "runtime_boundary"],
        "build_systems": [node for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("type") == "build_system"],
        "entry_points": graph.get("architecture_summary", {}).get("entry_points", []),
        "hotspots": graph.get("architecture_hotspots", []),
        "risk_areas": graph.get("architecture_summary", {}).get("risk_areas", []),
        "coding_conventions": graph.get("architecture_summary", {}).get("coding_conventions", []),
        "indexing": graph.get("indexing", {}),
        "graph_version": graph.get("version"),
    }


def agent_knowledge_summary(graph: dict[str, Any] | None, focus_files: list[str] | None = None) -> dict[str, Any]:
    if not graph:
        return {}
    focus_files = [item.replace("\\", "/") for item in (focus_files or [])]
    edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
    nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
    node_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    impacted_systems: set[str] = set()
    related_items: list[dict[str, Any]] = []
    suggested_context: list[str] = []
    for path in focus_files:
        file_id = f"file:{path}"
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if file_id not in {edge.get("source"), edge.get("target")}:
                continue
            other_id = edge.get("target") if edge.get("source") == file_id else edge.get("source")
            other = node_by_id.get(other_id)
            if not isinstance(other, dict):
                continue
            if other.get("type") == "system":
                impacted_systems.add(str(other.get("label") or other.get("id")))
            if other.get("type") in {"roadmap_item", "architecture_decision", "task", "bug", "validation_failure"}:
                related_items.append(_small_node(other))
            if other.get("type") == "file" and other.get("path"):
                suggested_context.append(str(other["path"]))
    hotspots = graph.get("architecture_hotspots", [])[:8] if isinstance(graph.get("architecture_hotspots"), list) else []
    return {
        "graph_version": graph.get("version"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "impacted_systems": sorted(impacted_systems),
        "related_items": related_items[:10],
        "architecture_hotspots": hotspots,
        "unstable_modules": graph.get("unstable_modules", [])[:8],
        "suggested_context": _dedupe(suggested_context)[:12],
    }


def agent_knowledge_guidance(summary: dict[str, Any] | None) -> list[str]:
    if not summary:
        return []
    guidance: list[str] = []
    if summary.get("impacted_systems"):
        guidance.append("Check impacted systems before proposing edits: " + ", ".join(summary["impacted_systems"][:5]) + ".")
    if summary.get("related_items"):
        guidance.append("Review related roadmap, decision, issue, or validation nodes before changing the focus area.")
    if summary.get("unstable_modules"):
        guidance.append("Treat unstable modules as higher risk and prefer smaller approved changes.")
    if summary.get("suggested_context"):
        guidance.append("Include graph-suggested context files when preparing a proposal.")
    return guidance[:5]


class _GraphBuilder:
    def __init__(self, root: Path, scan: dict[str, Any]):
        self.root = root
        self.scan = scan
        self.memory = ProjectMemory(root)
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.file_systems: dict[str, str] = {}
        self.api_nodes: dict[str, str] = {}
        self.indexing_failures: list[dict[str, Any]] = []
        self.unsupported_language_areas: list[dict[str, Any]] = []

    def build(self) -> dict[str, Any]:
        self._add_system_nodes()
        self._add_files_symbols_and_services()
        self._add_build_config_and_runtime_nodes()
        self._add_language_semantics()
        self._add_dependency_edges()
        self._add_api_edges()
        self._add_test_edges()
        self._add_tasks()
        self._add_roadmap_items()
        self._add_decisions()
        self._add_known_issues()
        self._add_validation_failures()
        self._add_agent_history()
        self._add_quality_edges()
        clusters = self._clusters()
        hotspots = self._hotspots()
        unstable = self._unstable_modules()
        return {
            "workspace": str(self.root),
            "workspace_name": self.root.name,
            "version": GRAPH_VERSION,
            "generated_at": utc_now(),
            "nodes": sorted(self.nodes.values(), key=lambda item: (item.get("type", ""), item.get("label", ""))),
            "edges": sorted(self.edges.values(), key=lambda item: (item.get("type", ""), item.get("source", ""), item.get("target", ""))),
            "clusters": clusters,
            "architecture_hotspots": hotspots,
            "unstable_modules": unstable,
            "query_examples": [
                "What systems depend on src/service.py?",
                "What changed before this bug appeared?",
                "What areas of the project are most unstable?",
                "Which roadmap items affect website/backend?",
                "What features are tied to /v1/quality?",
            ],
            "visualization": {
                "nodes": self._visual_nodes(clusters, unstable),
                "edges": self._visual_edges(),
            },
            "analyzers": {
                "supported_languages": ["typescript", "javascript", "python", "cpp", "csharp", "json", "yaml"],
                "unsupported_language_areas": self.unsupported_language_areas,
                "failures": self.indexing_failures,
            },
        }

    def _add_system_nodes(self) -> None:
        for framework in self.scan.get("frameworks", []):
            self._node(f"system:{_slug(framework)}", "system", str(framework), metadata={"source": "framework"})

    def _add_files_symbols_and_services(self) -> None:
        paths = set()
        for key in ("build_files", "readmes", "test_files", "entry_points", "recent_files"):
            paths.update(str(item) for item in self.scan.get(key, []))
        if isinstance(self.scan.get("dependency_graph"), dict):
            paths.update(self.scan["dependency_graph"].get("files", {}).keys())
        if isinstance(self.scan.get("symbol_index"), dict):
            paths.update(self.scan["symbol_index"].keys())
        for item in self.scan.get("todo_comments", []):
            if isinstance(item, dict) and item.get("file"):
                paths.add(str(item["file"]))

        for path in sorted(paths):
            self._add_file(path)
        for path, symbols in (self.scan.get("symbol_index") or {}).items():
            if not isinstance(symbols, list):
                continue
            file_id = self._add_file(path)
            for symbol in symbols[:150]:
                if not isinstance(symbol, dict):
                    continue
                name = str(symbol.get("name") or "").strip()
                if not name:
                    continue
                kind = str(symbol.get("kind") or "symbol")
                node_type = "ui_component" if kind == "component" else "symbol"
                if name.endswith(("Service", "Manager", "Client", "Store", "Router", "Provider")):
                    node_type = "service"
                symbol_id = f"{node_type}:{path}:{name}"
                self._node(
                    symbol_id,
                    node_type,
                    name,
                    path=path,
                    metadata={"kind": kind, "line": symbol.get("line")},
                )
                self._edge(file_id, symbol_id, "implements" if node_type in {"service", "ui_component"} else "contains", evidence=f"{path}:{symbol.get('line')}")

    def _add_dependency_edges(self) -> None:
        files = (self.scan.get("dependency_graph") or {}).get("files", {})
        if not isinstance(files, dict):
            return
        for source_path, deps in files.items():
            source_id = self._add_file(source_path)
            for dep in deps if isinstance(deps, list) else []:
                dep_text = str(dep)
                resolved = _resolve_dependency(source_path, dep_text, self.root)
                if resolved:
                    target_id = self._add_file(resolved)
                    self._edge(source_id, target_id, "uses", evidence=dep_text)
                    self._edge(source_id, target_id, "depends_on", evidence=dep_text)
                    self._add_cross_system_dependency(source_path, resolved, dep_text)
                else:
                    dep_id = f"external:{_slug(dep_text)}"
                    self._node(dep_id, "external_dependency", dep_text)
                    self._edge(source_id, dep_id, "depends_on", evidence=dep_text)

    def _add_api_edges(self) -> None:
        for path in self._code_paths():
            text = _read_workspace_text(self.root, path)
            if not text:
                continue
            file_id = self._add_file(path)
            for method, route in _implemented_routes(text):
                api_id = f"api:{method}:{route}"
                self.api_nodes[route] = api_id
                self._node(api_id, "api", f"{method.upper()} {route}", metadata={"method": method.upper(), "route": route})
                self._edge(file_id, api_id, "implements", evidence=path)
            for route in _called_routes(text):
                api_id = self.api_nodes.get(route) or f"api:unknown:{route}"
                self._node(api_id, "api", route, metadata={"route": route})
                self._edge(file_id, api_id, "calls", evidence=path)

    def _add_test_edges(self) -> None:
        tests = [str(path) for path in self.scan.get("test_files", [])]
        file_paths = [node.get("path") for node in self.nodes.values() if node.get("type") == "file" and node.get("path")]
        for test in tests:
            test_id = self._add_file(test)
            test_tokens = _tokens(Path(test).stem)
            for path in file_paths:
                if not path or path == test:
                    continue
                stem_tokens = _tokens(Path(str(path)).stem)
                if stem_tokens and test_tokens and stem_tokens.intersection(test_tokens):
                    self._edge(f"file:{path}", test_id, "tested_by", evidence=test)

    def _add_tasks(self) -> None:
        for task in _load_tasks(self.memory)[:100]:
            task_id = f"task:{task.get('id')}"
            label = str(task.get("title") or task.get("id"))
            self._node(task_id, "task", label, metadata={k: task.get(k) for k in ("status", "kind", "source_client", "updated_at")})
            self._link_text_node(task_id, label + " " + str(task.get("request") or ""), "related_to")

    def _add_roadmap_items(self) -> None:
        for index, text in enumerate(_roadmap_items(_read_text(self.memory.root / "roadmap.md")), start=1):
            node_id = f"roadmap:{index}"
            self._node(node_id, "roadmap_item", text[:140], metadata={"source": "roadmap.md"})
            self._link_text_node(node_id, text, "mentioned_in_roadmap")

    def _add_decisions(self) -> None:
        for index, text in enumerate(_decision_items(_read_text(self.memory.root / "decisions.md")), start=1):
            node_id = f"decision:{index}"
            self._node(node_id, "architecture_decision", text[:140], metadata={"source": "decisions.md"})
            self._link_text_node(node_id, text, "related_to")

    def _add_known_issues(self) -> None:
        for index, text in enumerate(_issue_items(_read_text(self.memory.root / "known-issues.md")), start=1):
            node_id = f"bug:{index}"
            self._node(node_id, "bug", text[:140], metadata={"source": "known-issues.md"})
            self._link_text_node(node_id, text, "breaks")

    def _add_validation_failures(self) -> None:
        for index, failure in enumerate(_validation_failures(_read_text(self.memory.root / "validation-log.md")), start=1):
            node_id = f"validation:{index}"
            self._node(node_id, "validation_failure", failure["label"], metadata={"command": failure.get("command"), "timestamp": failure.get("timestamp")})
            for path in failure.get("files", []):
                self._edge(node_id, self._add_file(path), "breaks", evidence=failure.get("command") or "validation-log.md")
            self._link_text_node(node_id, failure.get("output", ""), "related_to")

    def _add_agent_history(self) -> None:
        data = _read_json(self.memory.root / "agent-history.json", default=[])
        if not isinstance(data, list):
            return
        for index, item in enumerate(data[-100:], start=1):
            if not isinstance(item, dict):
                continue
            label = scrub(str(item.get("event") or item.get("summary") or "Agent event"))[:140]
            if not label:
                continue
            node_id = f"history:{index}"
            self._node(node_id, "history_event", label, metadata={"timestamp": item.get("timestamp"), "event": item.get("event")})
            text = json.dumps(item, default=str)
            self._link_text_node(node_id, text, "related_to")

    def _add_quality_edges(self) -> None:
        try:
            quality = quality_dashboard(self.root, scan=self.scan)
        except Exception:
            quality = {}
        for index, item in enumerate(quality.get("high_risk_files", [])[:20], start=1):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            risk_id = f"risk:{index}:{_slug(str(item['path']))}"
            self._node(risk_id, "risk", f"High risk: {item['path']}", metadata={"score": item.get("score"), "reasons": item.get("reasons", [])})
            self._edge(risk_id, self._add_file(str(item["path"])), "related_to", evidence="quality.dashboard")

    def _link_text_node(self, source_id: str, text: str, relation: str) -> None:
        terms = _tokens(text)
        if not terms:
            return
        for node in list(self.nodes.values()):
            if node.get("id") == source_id:
                continue
            if node.get("type") not in {"file", "system", "api", "service", "ui_component"}:
                continue
            node_terms = _node_terms(node)
            if len(terms.intersection(node_terms)) >= 1:
                self._edge(source_id, str(node["id"]), relation, evidence="text match")

    def _add_file(self, path: str) -> str:
        normalized = path.replace("\\", "/").lstrip("./")
        system = _system_for_path(normalized, self.scan.get("frameworks", []))
        self.file_systems[normalized] = system
        system_id = f"system:{_slug(system)}"
        self._node(system_id, "system", system, metadata={"source": "path"})
        file_id = f"file:{normalized}"
        self._node(file_id, "file", normalized, path=normalized, metadata={"suffix": Path(normalized).suffix.lower()})
        parent_id = self._ensure_folder_chain(normalized, system_id)
        self._edge(parent_id or system_id, file_id, "contains", evidence="path")
        return file_id

    def _ensure_folder_chain(self, path: str, system_id: str) -> str | None:
        parent = Path(path).parent
        if str(parent) in {"", "."}:
            return None
        current_parent = system_id
        accumulated: list[str] = []
        for part in parent.parts:
            accumulated.append(part)
            folder_path = "/".join(accumulated)
            folder_id = f"folder:{folder_path}"
            self._node(folder_id, "folder", folder_path, path=folder_path, metadata={"depth": len(accumulated)})
            self._edge(current_parent, folder_id, "contains", evidence="folder")
            current_parent = folder_id
        module_id = f"module:{parent.as_posix()}"
        self._node(module_id, "module", parent.as_posix(), path=parent.as_posix(), metadata={"source": "folder"})
        self._edge(current_parent, module_id, "owns", evidence="module boundary")
        return module_id

    def _add_build_config_and_runtime_nodes(self) -> None:
        for path in self.scan.get("build_files", []):
            rel = str(path)
            file_id = self._add_file(rel)
            kind = _config_kind(rel)
            config_id = f"config:{rel}"
            self._node(config_id, "config", rel, path=rel, metadata={"kind": kind})
            self._edge(file_id, config_id, "configures", evidence=rel)
            build_id = f"build_system:{_slug(kind)}"
            self._node(build_id, "build_system", kind, metadata={"source": rel})
            self._edge(config_id, build_id, "configures", evidence=rel)
        for system in sorted(set(self.file_systems.values())):
            boundary_id = f"runtime_boundary:{_slug(system)}"
            self._node(boundary_id, "runtime_boundary", system, metadata={"source": "system"})
            self._edge(boundary_id, f"system:{_slug(system)}", "owns", evidence="runtime boundary")

    def _add_language_semantics(self) -> None:
        for path in self._all_semantic_paths():
            text = _read_workspace_text(self.root, path)
            if not text:
                continue
            try:
                analysis = _analyze_semantic_file(path, text)
            except Exception as exc:  # pragma: no cover - defensive analyzer boundary.
                self.indexing_failures.append({"path": path, "error": scrub(str(exc))})
                continue
            if analysis.get("unsupported"):
                self.unsupported_language_areas.append({"path": path, "suffix": Path(path).suffix.lower()})
            file_id = self._add_file(path)
            last_owner_id = file_id
            named_nodes: dict[str, str] = {}
            for symbol in analysis.get("symbols", []):
                if not isinstance(symbol, dict):
                    continue
                name = str(symbol.get("name") or "").strip()
                if not name:
                    continue
                node_type = str(symbol.get("type") or "symbol")
                line = symbol.get("line")
                symbol_id = f"{node_type}:{path}:{name}:{line or 0}"
                self._node(symbol_id, node_type, name, path=path, metadata={k: v for k, v in symbol.items() if k != "name"})
                self._edge(file_id, symbol_id, "contains", evidence=f"{path}:{line or ''}".rstrip(":"))
                if node_type in {"class", "service", "api"}:
                    last_owner_id = symbol_id
                elif node_type in {"method", "function"} and last_owner_id != file_id:
                    self._edge(last_owner_id, symbol_id, "contains", evidence=f"{path}:{line or ''}".rstrip(":"))
                named_nodes[name] = symbol_id
                for parent in symbol.get("inherits", []) if isinstance(symbol.get("inherits"), list) else []:
                    parent_id = f"external:{_slug(str(parent))}"
                    self._node(parent_id, "external_dependency", str(parent))
                    self._edge(symbol_id, parent_id, "inherits", evidence=f"{path}:{line or ''}".rstrip(":"))
            for imported in analysis.get("imports", []):
                dep = str(imported)
                import_id = f"import:{path}:{_slug(dep)}"
                self._node(import_id, "import", dep, path=path)
                self._edge(file_id, import_id, "imports", evidence=dep)
            for call in analysis.get("calls", [])[:100]:
                call_name = str(call)
                target_id = self._find_symbol_by_name(call_name) or f"call:{_slug(call_name)}"
                if target_id.startswith("call:"):
                    self._node(target_id, "function", call_name)
                self._edge(file_id, target_id, "calls", evidence=path, weight=1)
            for api in analysis.get("api_consumers", []):
                route = str(api)
                api_id = self.api_nodes.get(route) or f"api:unknown:{route}"
                self._node(api_id, "api", route, metadata={"route": route})
                self._edge(file_id, api_id, "api_consumer", evidence=path)
            for database in analysis.get("databases", []):
                db_id = f"database:{_slug(str(database))}"
                self._node(db_id, "database", str(database), metadata={"source": path})
                self._edge(file_id, db_id, "uses", evidence=path)

    def _all_semantic_paths(self) -> list[str]:
        paths = set(self._code_paths())
        for key in ("build_files", "entry_points", "test_files"):
            paths.update(str(item) for item in self.scan.get(key, []))
        return sorted(path for path in paths if Path(path).suffix.lower() in SOURCE_CODE_SUFFIXES | {".json", ".yaml", ".yml", ".toml"})

    def _find_symbol_by_name(self, name: str) -> str | None:
        lowered = name.lower()
        for node in self.nodes.values():
            if node.get("type") in {"class", "function", "method", "service", "ui_component", "symbol"} and str(node.get("label") or "").lower() == lowered:
                return str(node.get("id"))
        return None

    def _add_cross_system_dependency(self, source_path: str, target_path: str, evidence: str) -> None:
        source_system = self.file_systems.get(source_path) or _system_for_path(source_path, self.scan.get("frameworks", []))
        target_system = self.file_systems.get(target_path) or _system_for_path(target_path, self.scan.get("frameworks", []))
        if source_system != target_system:
            self._edge(f"system:{_slug(source_system)}", f"system:{_slug(target_system)}", "depends_on", evidence=evidence)

    def _node(self, node_id: str, node_type: str, label: str, *, path: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        existing = self.nodes.get(node_id)
        if existing:
            if metadata:
                existing.setdefault("metadata", {}).update({k: v for k, v in metadata.items() if v is not None})
            return node_id
        self.nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": scrub(label)[:220],
            "path": path,
            "metadata": metadata or {},
        }
        return node_id

    def _edge(self, source: str, target: str, edge_type: str, *, evidence: str = "", weight: int = 1) -> None:
        if source == target:
            return
        key = (source, target, edge_type)
        existing = self.edges.get(key)
        if existing:
            existing["weight"] = int(existing.get("weight", 1)) + weight
            if evidence and evidence not in existing.setdefault("evidence", []):
                existing["evidence"].append(scrub(evidence)[:220])
            return
        self.edges[key] = {
            "source": source,
            "target": target,
            "type": edge_type,
            "weight": weight,
            "evidence": [scrub(evidence)[:220]] if evidence else [],
        }

    def _code_paths(self) -> list[str]:
        paths = set()
        if isinstance(self.scan.get("symbol_index"), dict):
            paths.update(self.scan["symbol_index"].keys())
        if isinstance(self.scan.get("dependency_graph"), dict):
            paths.update(self.scan["dependency_graph"].get("files", {}).keys())
        return sorted(path for path in paths if Path(path).suffix.lower() in SOURCE_CODE_SUFFIXES)

    def _clusters(self) -> list[dict[str, Any]]:
        cluster_nodes: dict[str, list[str]] = defaultdict(list)
        for node in self.nodes.values():
            if node.get("type") == "file" and node.get("path"):
                cluster_nodes[self.file_systems.get(str(node["path"]), "workspace")].append(node["id"])
        return [{"system": system, "node_count": len(nodes), "nodes": nodes[:80]} for system, nodes in sorted(cluster_nodes.items())]

    def _hotspots(self) -> list[dict[str, Any]]:
        counts = Counter()
        for edge in self.edges.values():
            counts[str(edge["source"])] += int(edge.get("weight", 1))
            counts[str(edge["target"])] += int(edge.get("weight", 1))
        hotspots = []
        for node_id, degree in counts.most_common(20):
            node = self.nodes.get(node_id)
            if node and node.get("type") in {"file", "system", "api", "service"}:
                hotspots.append({"id": node_id, "label": node.get("label"), "type": node.get("type"), "degree": degree})
        return hotspots[:10]

    def _unstable_modules(self) -> list[dict[str, Any]]:
        unstable: Counter[str] = Counter()
        for edge in self.edges.values():
            if edge.get("type") not in {"breaks", "related_to"}:
                continue
            target = self.nodes.get(str(edge.get("target")))
            if not target or target.get("type") != "file":
                continue
            system = self.file_systems.get(str(target.get("path")), "workspace")
            unstable[system] += int(edge.get("weight", 1))
        return [{"system": system, "weight": weight} for system, weight in unstable.most_common(10)]

    def _visual_nodes(self, clusters: list[dict[str, Any]], unstable: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unstable_systems = {item["system"] for item in unstable}
        visual = []
        for node in self.nodes.values():
            if node.get("type") in {"system", "api", "service", "ui_component", "roadmap_item", "bug", "validation_failure"}:
                visual.append({
                    "id": node["id"],
                    "label": node["label"],
                    "type": node["type"],
                    "unstable": node.get("label") in unstable_systems,
                })
        for cluster in clusters:
            visual.append({"id": f"cluster:{_slug(cluster['system'])}", "label": cluster["system"], "type": "cluster", "node_count": cluster["node_count"]})
        return visual[:250]

    def _visual_edges(self) -> list[dict[str, Any]]:
        return [
            {"source": edge["source"], "target": edge["target"], "type": edge["type"], "weight": edge.get("weight", 1)}
            for edge in self.edges.values()
            if edge.get("type") in {"depends_on", "implements", "calls", "breaks", "mentioned_in_roadmap", "related_to"}
        ][:500]


def _query_graph(graph: dict[str, Any], query: str, *, focus: str | None) -> dict[str, Any]:
    text = scrub(query).strip()
    focus = (focus or _extract_focus(text, graph)).strip() if (focus or text) else ""
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    node_by_id = {node.get("id"): node for node in nodes}
    focus_node = _find_focus_node(focus, nodes)
    intent = _intent(text)
    answers: list[dict[str, Any]] = []
    related_edges: list[dict[str, Any]] = []

    if intent == "dependents" and focus_node:
        focus_id = str(focus_node["id"])
        for edge in edges:
            if edge.get("target") == focus_id and edge.get("type") in {"uses", "depends_on", "tested_by", "contains"}:
                source = node_by_id.get(edge.get("source"))
                if source:
                    answers.append({"title": source.get("label"), "type": source.get("type"), "relationship": edge.get("type"), "node_id": source.get("id")})
                    related_edges.append(edge)
    elif intent == "unstable":
        answers.extend({"title": item.get("system"), "type": "unstable_module", "weight": item.get("weight")} for item in graph.get("unstable_modules", [])[:10])
        answers.extend({"title": item.get("label"), "type": item.get("type"), "degree": item.get("degree")} for item in graph.get("architecture_hotspots", [])[:5])
    elif intent == "roadmap" and focus_node:
        answers, related_edges = _related_by_type(focus_node, nodes, edges, {"roadmap_item"})
    elif intent == "api_features" and focus_node:
        answers, related_edges = _related_by_type(focus_node, nodes, edges, {"roadmap_item", "task", "architecture_decision", "ui_component", "service", "file"})
    elif intent == "history" and focus_node:
        answers, related_edges = _related_by_type(focus_node, nodes, edges, {"history_event", "architecture_decision", "bug", "validation_failure", "task"})
    else:
        terms = _tokens(text + " " + focus)
        for node in nodes:
            if terms and terms.intersection(_node_terms(node)):
                answers.append({"title": node.get("label"), "type": node.get("type"), "node_id": node.get("id")})

    return {
        "workspace": graph.get("workspace"),
        "query": text,
        "focus": focus or None,
        "intent": intent,
        "answers": answers[:25],
        "nodes": [_small_node(node_by_id[edge["source"]]) for edge in related_edges if edge.get("source") in node_by_id][:20],
        "edges": related_edges[:30],
        "suggested_followups": _followups(intent, focus_node),
        "graph_version": graph.get("version"),
    }


def _related_by_type(
    focus_node: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    node_types: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    node_by_id = {node.get("id"): node for node in nodes}
    focus_id = str(focus_node["id"])
    answers: list[dict[str, Any]] = []
    related_edges: list[dict[str, Any]] = []
    for edge in edges:
        if focus_id not in {edge.get("source"), edge.get("target")}:
            continue
        other_id = edge.get("target") if edge.get("source") == focus_id else edge.get("source")
        other = node_by_id.get(other_id)
        if other and other.get("type") in node_types:
            answers.append({"title": other.get("label"), "type": other.get("type"), "relationship": edge.get("type"), "node_id": other.get("id")})
            related_edges.append(edge)
    if not answers:
        terms = _node_terms(focus_node)
        for node in nodes:
            if node.get("type") in node_types and terms.intersection(_node_terms(node)):
                answers.append({"title": node.get("label"), "type": node.get("type"), "relationship": "text_match", "node_id": node.get("id")})
    return answers, related_edges


def _load_persisted_graph(root: Path) -> dict[str, Any] | None:
    data = _read_json(ProjectMemory(root).root / KNOWLEDGE_GRAPH_FILE, default=None)
    return data if isinstance(data, dict) and isinstance(data.get("nodes"), list) and isinstance(data.get("edges"), list) else None


def _persist_knowledge_graph(memory: ProjectMemory, graph: dict[str, Any]) -> None:
    graph_path = memory.root / KNOWLEDGE_GRAPH_FILE
    summary_path = memory.root / KNOWLEDGE_SUMMARY_FILE
    _ensure_output_target(graph_path)
    _ensure_output_target(summary_path)
    memory.write_json(KNOWLEDGE_GRAPH_FILE, graph)
    persisted = _load_persisted_graph(memory.workspace)
    if persisted != graph:
        raise KnowledgePersistenceError(
            f"Could not persist knowledge graph at {graph_path}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    summary_body = _render_knowledge_summary(graph)
    memory.write_generated_markdown(KNOWLEDGE_SUMMARY_FILE, "Knowledge Summary", summary_body)
    try:
        summary_text = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgePersistenceError(f"Could not persist knowledge summary at {summary_path}.") from exc
    if summary_body.rstrip() not in summary_text:
        raise KnowledgePersistenceError(f"Could not persist knowledge summary at {summary_path}.")


def _ensure_output_target(path: Path) -> None:
    if path.parent.exists() and not path.parent.is_dir():
        raise KnowledgePersistenceError(
            f"Could not persist knowledge graph because {path.parent} is not a directory."
        )
    if path.exists() and not path.is_file():
        raise KnowledgePersistenceError(
            f"Could not persist knowledge graph because {path} is not a writable file."
        )


def _load_tasks(memory: ProjectMemory) -> list[dict[str, Any]]:
    data = _read_json(memory.root / "tasks.json", default=[])
    if not isinstance(data, list):
        return []
    tasks = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            tasks.append(item)
    return tasks


def _render_knowledge_summary(graph: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Workspace: `{graph.get('workspace_name')}`",
            f"Graph version: `{graph.get('version')}`",
            f"Nodes: {len(graph.get('nodes', []))}",
            f"Edges: {len(graph.get('edges', []))}",
            "",
            "## Architecture Hotspots",
            "",
            *[f"- {item['label']} ({item['type']}, degree {item['degree']})" for item in graph.get("architecture_hotspots", [])[:10]],
            "",
            "## Unstable Modules",
            "",
            *[f"- {item['system']} ({item['weight']})" for item in graph.get("unstable_modules", [])[:10]],
            "",
            "## Query Examples",
            "",
            *[f"- {item}" for item in graph.get("query_examples", [])],
        ]
    )


def _implemented_routes(text: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    patterns = [
        re.compile(r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"\b(?:app|router)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            results.append((match.group(1).lower(), match.group(2)))
    return _dedupe_pairs(results)


def _called_routes(text: str) -> list[str]:
    routes = []
    for pattern in (
        re.compile(r"\bfetch\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"\b(?:axios|get|post|put|delete)\(\s*['\"]([^'\"]+)['\"]"),
    ):
        for match in pattern.finditer(text):
            route = match.group(1)
            if route.startswith(("/api", "/v1")):
                routes.append(route)
    return _dedupe(routes)


def _resolve_dependency(source_path: str, dep: str, root: Path) -> str | None:
    source_dir = Path(source_path).parent
    candidates: list[Path] = []
    if dep.startswith("."):
        normalized = dep.replace("\\", "/")
        if normalized.startswith(("./", "../")):
            base = source_dir / Path(normalized)
        else:
            base = source_dir / Path(normalized.lstrip(".").replace(".", "/"))
        candidates.extend(_path_candidates(base))
    elif dep.startswith(("/", "~")):
        candidates.extend(_path_candidates(Path(dep.lstrip("/~"))))
    elif "." in dep:
        candidates.extend(_path_candidates(Path(dep.replace(".", "/"))))
    for candidate in candidates:
        full = (root / candidate).resolve()
        if is_safe_to_read(full, root) and full.is_file():
            try:
                return full.relative_to(root).as_posix()
            except ValueError:
                return None
    return None


def _path_candidates(path: Path) -> list[Path]:
    candidates = [Path(str(path) + suffix) for suffix in PATH_CANDIDATE_SUFFIXES if suffix or not path.suffix]
    candidates.extend(path / f"index{suffix}" for suffix in [".ts", ".tsx", ".js", ".jsx"])
    return candidates


def _system_for_path(path: str, frameworks: list[str] | None = None) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("website/backend/"):
        return "website-backend"
    if normalized.startswith("website/frontend/"):
        return "website-frontend"
    if normalized.startswith("aegis-core/"):
        return "aegis-core"
    if normalized.startswith("vscode-plugins/"):
        return "vscode-extension"
    if normalized.startswith("visual-studio-extensions/"):
        return "visual-studio-extension"
    if normalized.startswith("desktop") or normalized.startswith("src/"):
        if frameworks and any("C++" in item or "Visual Studio" in item for item in frameworks):
            return "desktop-client"
    parts = normalized.split("/")
    return parts[0] if len(parts) > 1 else "workspace"


def _roadmap_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:\d+\.|-)\s+(.{8,240})", line)
        if match:
            items.append(scrub(match.group(1)).strip())
    return items[:80]


def _decision_items(text: str) -> list[str]:
    items = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                items.append(" ".join(current))
            current = [line.lstrip("# ").strip()]
        elif "What changed:" in line or "Affected files:" in line or "Validation:" in line:
            current.append(line.strip("- ").strip())
    if current:
        items.append(" ".join(current))
    return [scrub(item) for item in items if len(item) >= 8][:80]


def _issue_items(text: str) -> list[str]:
    return [
        scrub(line.strip("- ").strip())
        for line in text.splitlines()
        if line.strip() and not line.startswith("#") and any(token in line.lower() for token in ("bug", "issue", "fail", "error", "broken", "fixme"))
    ][:80]


def _validation_failures(text: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    matches = list(re.finditer(r"^##\s+(.+?)\s+-\s+failed\s*$", text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entry = text[start:end]
        command = re.search(r"Command:\s+`([^`]*)`", entry)
        files = _mentioned_files(entry)
        failures.append(
            {
                "timestamp": match.group(1).strip(),
                "command": command.group(1).strip() if command else "",
                "files": files,
                "label": f"Validation failed: {command.group(1).strip() if command else match.group(1).strip()}",
                "output": scrub(entry[-3000:]),
            }
        )
    return failures[-50:]


def _mentioned_files(text: str) -> list[str]:
    pattern = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:py|js|jsx|ts|tsx|cs|cpp|c|h|hpp|md|json|toml|yaml|yml))")
    return _dedupe(match.group(1).replace("\\", "/").lstrip("./") for match in pattern.finditer(text))[:50]


def _find_focus_node(focus: str, nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not focus:
        return None
    normalized = focus.replace("\\", "/").strip()
    candidates = [
        f"file:{normalized}",
        normalized,
    ]
    for node in nodes:
        if node.get("id") in candidates or node.get("path") == normalized:
            return node
        metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        if metadata.get("route") == normalized or str(node.get("label", "")).endswith(normalized):
            return node
    terms = _tokens(normalized)
    for node in nodes:
        if terms and terms.intersection(_node_terms(node)):
            return node
    return None


def _extract_focus(query: str, graph: dict[str, Any]) -> str:
    file_match = re.search(r"([A-Za-z0-9_./\\-]+\.(?:py|js|jsx|ts|tsx|cs|cpp|c|h|hpp|md|json|toml|yaml|yml))", query)
    if file_match:
        return file_match.group(1).replace("\\", "/")
    route_match = re.search(r"(/(?:api|v1)/[A-Za-z0-9_./{}:-]+)", query)
    if route_match:
        return route_match.group(1)
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "system" and str(node.get("label", "")).lower() in query.lower():
            return str(node["label"])
    return ""


def _intent(query: str) -> str:
    lowered = query.lower()
    if "depend" in lowered or "uses this file" in lowered:
        return "dependents"
    if "unstable" in lowered or "risk" in lowered or "fragile" in lowered:
        return "unstable"
    if "roadmap" in lowered:
        return "roadmap"
    if "api" in lowered or "feature" in lowered:
        return "api_features"
    if "changed before" in lowered or "history" in lowered or "bug appeared" in lowered or "previous fix" in lowered:
        return "history"
    return "search"


def _followups(intent: str, focus_node: dict[str, Any] | None) -> list[str]:
    label = focus_node.get("label") if focus_node else "this area"
    if intent == "dependents":
        return [f"Which validation failures mention {label}?", f"Which roadmap items affect {label}?"]
    if intent == "unstable":
        return ["Which files are high-risk?", "Which validation failures repeat most often?"]
    if intent == "roadmap":
        return [f"What files are tied to {label}?", f"What decisions mention {label}?"]
    if intent == "api_features":
        return [f"Which UI components call {label}?", f"Which tasks mention {label}?"]
    return ["What areas of the project are most unstable?", "What systems depend on this file?"]


def _node_terms(node: dict[str, Any]) -> set[str]:
    pieces = [str(node.get("label") or ""), str(node.get("path") or "")]
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    pieces.extend(str(value) for value in metadata.values() if isinstance(value, (str, int, float)))
    return _tokens(" ".join(pieces))


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    normalized = re.sub(r"[-_/\\.]+", " ", str(text).lower())
    for token in re.findall(r"[a-z0-9]+", normalized):
        if len(token) <= 2 or token in COMMON_WORDS:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    return tokens


def _small_node(node: dict[str, Any]) -> dict[str, Any]:
    return {key: node.get(key) for key in ("id", "type", "label", "path") if node.get(key) is not None}


def _read_workspace_text(root: Path, relative_path: str) -> str:
    path = (root / relative_path).resolve()
    if not is_safe_to_read(path, root) or not path.is_file():
        return ""
    return _read_text(path)


def _read_text(path: Path) -> str:
    try:
        return scrub(path.read_text(encoding="utf-8", errors="ignore")) if path.is_file() else ""
    except OSError:
        return ""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-") or "unknown"


def _dedupe(values: Any) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _analyze_semantic_file(path: str, text: str) -> dict[str, Any]:
    suffix = Path(path).suffix.lower()
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return _analyze_ts_js(path, text)
    if suffix == ".py":
        return _analyze_python(path, text)
    if suffix in {".cpp", ".cxx", ".cc", ".c", ".h", ".hpp"}:
        return _analyze_cpp(path, text)
    if suffix == ".cs":
        return _analyze_csharp(path, text)
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return _analyze_config(path, text)
    return {"unsupported": True, "symbols": [], "imports": [], "calls": [], "api_consumers": [], "databases": []}


def _analyze_ts_js(path: str, text: str) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    imports: list[str] = []
    api_consumers: list[str] = []
    calls: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        import_match = re.search(r"\bimport\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]", line)
        if import_match:
            imports.append(import_match.group(1))
        class_match = re.search(r"\bclass\s+([A-Za-z_][\w]*)(?:\s+extends\s+([A-Za-z_][\w]*))?", line)
        if class_match:
            symbol_type = "service" if class_match.group(1).endswith(("Service", "Client", "Provider", "Store")) else "class"
            symbols.append({"type": symbol_type, "name": class_match.group(1), "line": number, "inherits": [class_match.group(2)] if class_match.group(2) else []})
        function_match = re.search(r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)\s*\(", line)
        arrow_match = re.search(r"\b(?:export\s+)?(?:const|let)\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", line)
        for match in (function_match, arrow_match):
            if match:
                name = match.group(1)
                symbols.append({"type": "ui_component" if name[:1].isupper() and path.endswith((".tsx", ".jsx")) else "function", "name": name, "line": number})
        for route in re.findall(r"['\"]((?:/api|/v1)/[^'\"]+)['\"]", line):
            api_consumers.append(route)
        calls.extend(_line_calls(line))
    return {
        "language": "typescript" if path.endswith((".ts", ".tsx")) else "javascript",
        "symbols": symbols,
        "imports": _dedupe(imports),
        "calls": _dedupe(calls),
        "api_consumers": _dedupe(api_consumers),
        "databases": _database_mentions(text),
    }


def _analyze_python(path: str, text: str) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    current_class: tuple[str, int] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        import_match = re.match(r"(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", stripped)
        if import_match:
            imports.append(next(group for group in import_match.groups() if group))
        class_match = re.match(r"class\s+([A-Za-z_][\w]*)(?:\(([^)]*)\))?:", stripped)
        if class_match:
            bases = [item.strip() for item in (class_match.group(2) or "").split(",") if item.strip()]
            name = class_match.group(1)
            symbol_type = "service" if name.endswith(("Service", "Client", "Manager", "Store")) else "class"
            symbols.append({"type": symbol_type, "name": name, "line": number, "inherits": bases})
            current_class = (name, len(line) - len(line.lstrip()))
        def_match = re.match(r"(?:async\s+)?def\s+([A-Za-z_][\w]*)\s*\(", stripped)
        if def_match:
            indent = len(line) - len(line.lstrip())
            symbols.append({"type": "method" if current_class and indent > current_class[1] else "function", "name": def_match.group(1), "line": number})
        calls.extend(_line_calls(line))
    return {
        "language": "python",
        "symbols": symbols,
        "imports": _dedupe(imports),
        "calls": _dedupe(calls),
        "api_consumers": _dedupe(re.findall(r"['\"]((?:/api|/v1)/[^'\"]+)['\"]", text)),
        "databases": _database_mentions(text),
    }


def _analyze_cpp(path: str, text: str) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        include_match = re.match(r"\s*#include\s+[<\"](.+?)[>\"]", line)
        if include_match:
            imports.append(include_match.group(1))
        class_match = re.search(r"\b(?:class|struct)\s+([A-Za-z_][\w]*)(?:\s*:\s*(?:public|private|protected)?\s*([A-Za-z_][\w:]*))?", line)
        if class_match:
            symbols.append({"type": "class", "name": class_match.group(1), "line": number, "inherits": [class_match.group(2)] if class_match.group(2) else []})
        method_match = re.search(r"\b([A-Za-z_][\w:]*)::([A-Za-z_][\w]*)\s*\(", line)
        function_match = re.search(r"^\s*(?:[\w:<>\*&]+\s+)+([A-Za-z_][\w]*)\s*\([^;]*\)\s*\{?", line)
        if method_match:
            symbols.append({"type": "method", "name": method_match.group(2), "line": number, "owner": method_match.group(1)})
        elif function_match and function_match.group(1) not in {"if", "for", "while", "switch"}:
            symbols.append({"type": "function", "name": function_match.group(1), "line": number})
        calls.extend(_line_calls(line))
    return {"language": "cpp", "symbols": symbols, "imports": _dedupe(imports), "calls": _dedupe(calls), "api_consumers": [], "databases": _database_mentions(text)}


def _analyze_csharp(path: str, text: str) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        using_match = re.match(r"\s*using\s+([\w.]+)\s*;", line)
        if using_match:
            imports.append(using_match.group(1))
        class_match = re.search(r"\b(?:class|interface|record|struct)\s+([A-Za-z_][\w]*)(?:\s*:\s*([A-Za-z_][\w.,\s<>]*))?", line)
        if class_match:
            bases = [item.strip() for item in (class_match.group(2) or "").split(",") if item.strip()]
            name = class_match.group(1)
            symbols.append({"type": "service" if name.endswith(("Service", "Client", "Provider", "Store")) else "class", "name": name, "line": number, "inherits": bases})
        method_match = re.search(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+|async\s+|virtual\s+|override\s+)*[\w<>\[\],]+\s+([A-Za-z_][\w]*)\s*\(", line)
        if method_match and method_match.group(1) not in {"if", "for", "while", "switch"}:
            symbols.append({"type": "method", "name": method_match.group(1), "line": number})
        calls.extend(_line_calls(line))
    return {"language": "csharp", "symbols": symbols, "imports": _dedupe(imports), "calls": _dedupe(calls), "api_consumers": [], "databases": _database_mentions(text)}


def _analyze_config(path: str, text: str) -> dict[str, Any]:
    symbols = [{"type": "config", "name": Path(path).name, "line": 1, "kind": _config_kind(path)}]
    deps: list[str] = []
    if path.endswith("package.json"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                for section in ("dependencies", "devDependencies", "peerDependencies"):
                    values = payload.get(section)
                    if isinstance(values, dict):
                        deps.extend(str(key) for key in values)
        except json.JSONDecodeError:
            pass
    return {"language": "config", "symbols": symbols, "imports": _dedupe(deps), "calls": [], "api_consumers": [], "databases": _database_mentions(text)}


def _line_calls(line: str) -> list[str]:
    clean = re.sub(r"//.*$|#.*$", "", line)
    ignored = {"if", "for", "while", "switch", "catch", "return", "sizeof", "typeof", "new", "function", "def"}
    return [
        match.group(1)
        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", clean)
        if match.group(1) not in ignored
    ]


def _database_mentions(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for name in ("sqlite", "postgres", "postgresql", "mysql", "mongodb", "redis", "prisma", "dbcontext", "sqlalchemy"):
        if name in lowered:
            found.append(name)
    return _dedupe(found)


def _config_kind(path: str) -> str:
    lowered = path.lower().replace("\\", "/")
    if lowered.endswith("package.json"):
        return "Node.js package"
    if lowered.endswith(("pyproject.toml", "requirements.txt")):
        return "Python config"
    if lowered.endswith((".sln", ".csproj", ".fsproj", ".vbproj")):
        return ".NET build"
    if lowered.endswith((".vcxproj", "cmakelists.txt")):
        return "Native build"
    if lowered.endswith((".yaml", ".yml")):
        return "YAML config"
    if lowered.endswith(".json"):
        return "JSON config"
    return "Config"


def _file_manifest(root: Path, scan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths: set[str] = set()
    for key in ("build_files", "readmes", "test_files", "entry_points", "recent_files"):
        paths.update(str(item) for item in scan.get(key, []) if str(item).strip())
    if isinstance(scan.get("dependency_graph"), dict):
        paths.update(str(item) for item in scan["dependency_graph"].get("files", {}).keys())
    if isinstance(scan.get("symbol_index"), dict):
        paths.update(str(item) for item in scan["symbol_index"].keys())
    for item in scan.get("todo_comments", []) if isinstance(scan.get("todo_comments"), list) else []:
        if isinstance(item, dict) and item.get("file"):
            paths.add(str(item["file"]))
    manifest: dict[str, dict[str, Any]] = {}
    for relative in sorted(paths):
        path = (root / relative).resolve()
        try:
            if not path.is_file() or not is_safe_to_read(path, root):
                continue
            stat = path.stat()
            manifest[relative.replace("\\", "/")] = {
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
                "fingerprint": _quick_file_fingerprint(path, stat.st_size, int(stat.st_mtime)),
            }
        except OSError:
            continue
    return manifest


def _quick_file_fingerprint(path: Path, size: int, modified: int) -> str:
    import hashlib

    try:
        data = path.read_bytes()[:8192]
    except OSError:
        data = b""
    return hashlib.sha1(data + str(size).encode("ascii") + str(modified).encode("ascii")).hexdigest()[:16]


def _load_index_state(memory: ProjectMemory) -> dict[str, Any]:
    state = _read_json(memory.root / KNOWLEDGE_INDEX_STATE_FILE, default={})
    return state if isinstance(state, dict) else {}


def _incremental_status(previous_state: dict[str, Any], manifest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    previous = previous_state.get("file_fingerprints") if isinstance(previous_state.get("file_fingerprints"), dict) else {}
    previous_keys = set(previous)
    current_keys = set(manifest)
    changed = sorted(path for path in current_keys if previous.get(path) != manifest.get(path))
    removed = sorted(previous_keys - current_keys)
    unchanged = sorted(current_keys - set(changed))
    return {
        "enabled": True,
        "changed_files": changed,
        "removed_files": removed,
        "unchanged_file_count": len(unchanged),
        "invalidated_nodes": [f"file:{path}" for path in [*changed, *removed]],
        "partial_update": bool(previous) and bool(changed or removed),
        "full_rescan": not bool(previous),
        "background_refresh_jobs": ["knowledge-incremental-refresh", "workspace-intelligence-refresh"],
        "last_indexed_at": previous_state.get("generated_at"),
    }


def _indexing_observability(
    graph: dict[str, Any],
    incremental: dict[str, Any],
    duration_ms: float,
    failures: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
    stale_nodes = set(incremental.get("invalidated_nodes", []))
    file_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "file"]
    symbol_count = sum(1 for node in nodes if isinstance(node, dict) and node.get("type") in {"class", "function", "method", "service", "ui_component", "symbol"})
    language_coverage = sorted(
        {
            _language_for_path(str(node.get("path") or ""))
            for node in file_nodes
            if _language_for_path(str(node.get("path") or "")) != "text"
        }
    )
    return {
        "duration_ms": duration_ms,
        "graph_size": {"nodes": len(nodes), "edges": len(edges)},
        "files_indexed": len(file_nodes),
        "language_coverage": language_coverage,
        "symbol_count": symbol_count,
        "stale_node_count": len(stale_nodes),
        "stale_nodes": sorted(stale_nodes)[:100],
        "indexing_failures": failures[:50],
        "unsupported_language_areas": unsupported[:50],
        "incremental": incremental,
        "cache_hit": False,
    }


def _semantic_index(root: Path, scan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    file_nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("type") == "file"]
    files: list[dict[str, Any]] = []
    edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
    for node in file_nodes[:500]:
        path = str(node.get("path") or "")
        related = [edge for edge in edges if node.get("id") in {edge.get("source"), edge.get("target")}]
        files.append(
            {
                "path": path,
                "purpose": _file_purpose_summary(path, related),
                "language": _language_for_path(path),
                "relationship_count": len(related),
                "symbols": [
                    related_node.get("label")
                    for related_node in graph.get("nodes", [])
                    if isinstance(related_node, dict) and related_node.get("path") == path and related_node.get("type") in {"class", "function", "method", "service", "ui_component"}
                ][:30],
            }
        )
    return {
        "version": GRAPH_VERSION,
        "generated_at": utc_now(),
        "files": files,
        "architecture": _architecture_summary_from_graph(root, scan, graph),
        "retrieval": {
            "mode": "graph_keyword",
            "vector_search_ready": False,
            "embedding_provider": None,
        },
    }


def _file_purpose_summary(path: str, related_edges: list[dict[str, Any]]) -> str:
    suffix = Path(path).suffix.lower()
    if path.lower().endswith("package.json"):
        return "Package manifest and dependency/configuration boundary."
    if any(edge.get("type") == "implements" for edge in related_edges):
        return "Implements symbols, services, APIs, or components used by the project."
    if any(edge.get("type") in {"tested_by", "validates"} for edge in related_edges):
        return "Participates in validation or test coverage."
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return "Frontend or JavaScript/TypeScript module."
    if suffix == ".py":
        return "Python module."
    if suffix in {".cpp", ".c", ".h", ".hpp"}:
        return "Native C/C++ source or header."
    if suffix == ".cs":
        return ".NET/C# source module."
    return "Workspace file indexed for graph relationships."


def _language_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".ts": "TypeScript",
        ".tsx": "React/TypeScript",
        ".js": "JavaScript",
        ".jsx": "React/JavaScript",
        ".py": "Python",
        ".cpp": "C++",
        ".c": "C/C++",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
    }.get(suffix, suffix.lstrip(".") or "unknown")


def _architecture_summary_from_graph(root: Path, scan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
    type_counts = Counter(str(node.get("type") or "unknown") for node in nodes if isinstance(node, dict))
    return {
        "workspace_name": root.name,
        "frameworks": scan.get("frameworks", []),
        "languages": scan.get("languages", {}),
        "entry_points": scan.get("entry_points", []),
        "build_systems": [_config_kind(str(path)) for path in scan.get("build_files", [])],
        "runtime_boundaries": [node.get("label") for node in nodes if isinstance(node, dict) and node.get("type") == "runtime_boundary"],
        "node_type_counts": dict(type_counts),
        "architecture_hotspots": graph.get("architecture_hotspots", []),
        "risk_areas": graph.get("unstable_modules", []),
        "coding_conventions": _coding_conventions_from_scan(scan),
        "design_patterns": _design_patterns(nodes),
    }


def _coding_conventions_from_scan(scan: dict[str, Any]) -> list[dict[str, Any]]:
    languages = {str(key).lower() for key in (scan.get("languages") or {}).keys()} if isinstance(scan.get("languages"), dict) else set()
    conventions = []
    if any("typescript" in item or "javascript" in item or "react" in item for item in languages):
        conventions.append({"scope": "typescript/javascript", "summary": "Prefer package script validation and component/service boundaries from imports."})
    if "python" in languages:
        conventions.append({"scope": "python", "summary": "Prefer module-level functions/classes and pytest-compatible validation."})
    if any(item in languages for item in {"c++", "c/c++", "c#"}):
        conventions.append({"scope": "native/dotnet", "summary": "Preserve project/solution build boundaries and header/source relationships."})
    return conventions or [{"scope": "general", "summary": "Use small dependency-aware edits with validation and rollback."}]


def _design_patterns(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = [str(node.get("label") or "") for node in nodes if isinstance(node, dict)]
    patterns = []
    for suffix, label in (("Service", "Service layer"), ("Client", "Client adapter"), ("Provider", "Provider pattern"), ("Store", "State store"), ("Controller", "Controller layer")):
        count = sum(1 for item in labels if item.endswith(suffix))
        if count:
            patterns.append({"pattern": label, "count": count})
    return patterns


def _project_memory_summary(memory: ProjectMemory) -> dict[str, Any]:
    workflows = _read_json(memory.root / "workflow-runtime.json", default=[])
    engineering = _read_json(memory.root / "engineering-executions.json", default=[])
    validation_results = _read_json(memory.root / "validation-results.json", default=[])
    preferences = _read_json(memory.root / "personal-intelligence.json", default={})
    return {
        "previous_workflows": _compact_records(workflows, ("id", "workflow_type", "status", "objective", "updated_at"), 40),
        "execution_outcomes": _compact_records(engineering, ("id", "mode", "status", "goal", "updated_at"), 40),
        "roadmap_history": _roadmap_items(_read_text(memory.root / "roadmap.md"))[:40],
        "repaired_issues": _compact_repairs(engineering),
        "recurring_failures": _recurring_failures(validation_results, _read_text(memory.root / "validation-log.md")),
        "architectural_decisions": _decision_items(_read_text(memory.root / "decisions.md"))[:40],
        "user_preferences": preferences if isinstance(preferences, dict) else {},
        "generated_at": utc_now(),
    }


def _compact_records(value: Any, keys: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records = []
    for item in value[:limit]:
        if isinstance(item, dict):
            records.append({key: item.get(key) for key in keys if item.get(key) is not None})
    return records


def _compact_repairs(executions: Any) -> list[dict[str, Any]]:
    repairs = []
    if not isinstance(executions, list):
        return repairs
    for execution in executions:
        if not isinstance(execution, dict):
            continue
        for repair in execution.get("repair_history", []) if isinstance(execution.get("repair_history"), list) else []:
            if isinstance(repair, dict):
                repairs.append({"execution_id": execution.get("id"), "summary": repair.get("summary"), "status": repair.get("status"), "target_files": repair.get("target_files", [])})
    return repairs[:40]


def _recurring_failures(validation_results: Any, validation_log: str) -> list[dict[str, Any]]:
    failures: Counter[str] = Counter()
    if isinstance(validation_results, list):
        for item in validation_results:
            if not isinstance(item, dict):
                continue
            validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
            if validation.get("ok") is False:
                signature = str(validation.get("stderr") or validation.get("command") or "validation failure")[:180]
                failures[signature] += 1
    for failure in _validation_failures(validation_log):
        failures[str(failure.get("label") or "validation failure")] += 1
    return [{"signature": key, "count": count} for key, count in failures.most_common(20)]


def _embedding_interfaces() -> dict[str, Any]:
    return {
        "enabled": False,
        "interfaces": [
            {"id": "local_embedding_model", "status": "planned", "privacy": "local"},
            {"id": "hybrid_graph_vector_search", "status": "planned", "privacy": "configurable"},
        ],
        "current_retrieval": "keyword_graph",
        "notes": "Graph records include stable IDs and semantic summaries so embeddings can be added without changing client contracts.",
    }


def _validation_targets_for_files(graph: dict[str, Any], affected_files: list[str]) -> list[dict[str, Any]]:
    validation = graph.get("project_memory", {}).get("recurring_failures", []) if isinstance(graph.get("project_memory"), dict) else []
    targets = []
    for path in affected_files:
        if any(part in path.lower() for part in ("test", "spec")):
            targets.append({"kind": "test_file", "path": path, "reason": "Affected file is itself a test/validation file."})
        elif path.endswith((".ts", ".tsx", ".js", ".jsx")):
            targets.append({"kind": "package_script", "command": ["npm", "test"], "reason": f"{path} is JavaScript/TypeScript."})
        elif path.endswith(".py"):
            targets.append({"kind": "python", "command": ["python", "-m", "pytest"], "reason": f"{path} is Python."})
        elif path.endswith((".cs", ".cpp", ".c", ".h", ".hpp")):
            targets.append({"kind": "build", "command": ["dotnet", "build"] if path.endswith(".cs") else ["cmake", "--build", "build"], "reason": f"{path} is compiled code."})
    if validation:
        targets.append({"kind": "recurring_failures", "reason": "Previous recurring validation failures exist.", "failures": validation[:5]})
    return targets[:20]


def _likely_breakage_areas(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    areas: Counter[str] = Counter()
    node_by_id = {node.get("id"): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    for edge in edges:
        for endpoint in (edge.get("source"), edge.get("target")):
            node = node_by_id.get(endpoint)
            if not node:
                continue
            if node.get("type") in {"system", "runtime_boundary", "build_system", "api", "service"}:
                areas[str(node.get("label") or node.get("id"))] += int(edge.get("weight") or 1)
    return [{"area": area, "weight": weight} for area, weight in areas.most_common(10)]


def _related_workflows(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = set()
    for node in nodes:
        if isinstance(node, dict):
            terms.update(_node_terms(node))
    workflows = graph.get("project_memory", {}).get("previous_workflows", []) if isinstance(graph.get("project_memory"), dict) else []
    out = []
    for workflow in workflows:
        text = " ".join(str(value) for value in workflow.values())
        if terms.intersection(_tokens(text)):
            out.append(workflow)
    return out[:10]


def _risk_reasons(affected_files: list[str], risky_edges: list[dict[str, Any]], change_type: str) -> list[str]:
    reasons = []
    if affected_files:
        reasons.append(f"{len(affected_files)} affected file(s) found through graph relationships.")
    if risky_edges:
        reasons.append(f"{len(risky_edges)} high-signal relationship edge(s) are involved.")
    if change_type in {"delete", "move", "rename"}:
        reasons.append(f"{change_type} changes are higher risk because dependents may break.")
    return reasons or ["No broad dependent surface found."]


def _project_id(root: Path) -> str:
    import hashlib

    return f"project-{hashlib.sha1(str(root).lower().encode('utf-8')).hexdigest()[:12]}"
