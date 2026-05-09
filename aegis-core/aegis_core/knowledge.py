from __future__ import annotations

import json
import re
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
GRAPH_VERSION = "2026.05.09"
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
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    scan_data = scan or WorkspaceScanner(root).scan(persist=persist)
    builder = _GraphBuilder(root, scan_data)
    graph = builder.build()
    graph["graph_path"] = str(memory.root / KNOWLEDGE_GRAPH_FILE)
    graph["summary_path"] = str(memory.root / KNOWLEDGE_SUMMARY_FILE)
    if persist:
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

    def build(self) -> dict[str, Any]:
        self._add_system_nodes()
        self._add_files_symbols_and_services()
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
        self._edge(system_id, file_id, "contains", evidence="path")
        return file_id

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
        stripped = dep.lstrip(".")
        base = source_dir / Path(stripped.replace(".", "/"))
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
