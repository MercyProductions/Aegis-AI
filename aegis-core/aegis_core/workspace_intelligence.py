from __future__ import annotations

from pathlib import Path
from typing import Any

from .ecosystem import shared_memory_summary
from .knowledge import knowledge_graph
from .memory import ProjectMemory, utc_now
from .quality import quality_dashboard
from .validation import validation_summary
from .workspace import WorkspaceScanner


INTELLIGENCE_FILE = "workspace-intelligence.json"


def workspace_intelligence(
    workspace: str | Path,
    *,
    persist: bool = True,
    refresh: bool = False,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    memory.ensure()
    cache_path = memory.root / INTELLIGENCE_FILE
    if persist and not refresh and cache_path.is_file():
        try:
            cached = cache_path.read_text(encoding="utf-8")
            import json

            payload = json.loads(cached)
            if isinstance(payload, dict):
                payload["cache_hit"] = True
                return payload
        except (OSError, ValueError):
            pass

    scan = WorkspaceScanner(root).scan(persist=persist)
    quality = quality_dashboard(root, scan=scan)
    graph = knowledge_graph(root, scan=scan, persist=persist)
    validation = validation_summary(root)
    memory_summary = shared_memory_summary(root)
    metadata = {
        "workspace_name": scan.get("workspace_name") or root.name,
        "workspace": str(root),
        "generated_at": utc_now(),
        "frameworks": scan.get("frameworks", []),
        "languages": scan.get("languages", {}),
        "file_count": scan.get("file_count", 0),
        "build_files": scan.get("build_files", []),
        "test_files": scan.get("test_files", []),
        "entry_points": scan.get("entry_points", []),
    }
    build_systems = _build_systems(scan, validation)
    result = {
        "workspace": str(root),
        "project_id": _project_id(root),
        "generated_at": metadata["generated_at"],
        "cache_hit": False,
        "metadata": metadata,
        "frameworks": scan.get("frameworks", []),
        "languages": scan.get("languages", {}),
        "file_index": {
            "file_count": scan.get("file_count", 0),
            "recent_files": scan.get("recent_files", []),
            "readmes": scan.get("readmes", []),
            "test_files": scan.get("test_files", []),
            "build_files": scan.get("build_files", []),
            "scan_fingerprint": scan.get("scan_fingerprint", {}),
        },
        "semantic_summaries": {
            "project_summary": memory_summary.get("entries", {}).get("project_summary", {}),
            "architecture_map": memory_summary.get("entries", {}).get("architecture_map", {}),
            "knowledge_summary": memory_summary.get("entries", {}).get("knowledge_summary", {}),
            "roadmap": memory_summary.get("entries", {}).get("roadmap", {}),
        },
        "project_metadata": metadata,
        "dependency_graph": scan.get("dependency_graph", {}),
        "symbol_index": scan.get("symbol_index", {}),
        "build_systems": build_systems,
        "health": {
            "score": quality.get("score", 0),
            "grade": quality.get("grade", ""),
            "warnings": quality.get("warnings", []),
            "failing_systems": quality.get("failing_systems", []),
            "top_risks": quality.get("top_risks", []),
            "recommended_next_improvement": quality.get("recommended_next_improvement", ""),
        },
        "validation": validation,
        "knowledge": {
            "version": graph.get("version", ""),
            "node_count": len(graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []),
            "edge_count": len(graph.get("edges", []) if isinstance(graph.get("edges"), list) else []),
            "clusters": graph.get("clusters", []),
            "unstable_modules": graph.get("unstable_modules", []),
            "graph_path": graph.get("graph_path"),
            "summary_path": graph.get("summary_path"),
            "semantic_index_path": graph.get("semantic_index_path"),
            "project_memory_path": graph.get("project_memory_path"),
            "indexing": graph.get("indexing", {}),
            "architecture_summary": graph.get("architecture_summary", {}),
            "embedding_interfaces": graph.get("embedding_interfaces", {}),
        },
        "memory_paths": {
            key: value.get("path")
            for key, value in memory_summary.get("entries", {}).items()
            if isinstance(value, dict) and value.get("path")
        },
    }
    if persist:
        memory.write_json(INTELLIGENCE_FILE, result)
    return result


def _build_systems(scan: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    systems: list[dict[str, Any]] = []
    build_files = [str(item) for item in scan.get("build_files", []) if str(item).strip()]
    commands = validation.get("commands") if isinstance(validation.get("commands"), list) else []
    for path in build_files:
        label = _build_label(path)
        if label and not any(item["label"] == label for item in systems):
            systems.append({"label": label, "source": path})
    for command in commands:
        if not isinstance(command, dict):
            continue
        name = str(command.get("name") or "").strip()
        if name and not any(item.get("command") == command.get("command") for item in systems):
            systems.append({"label": name, "command": command.get("command"), "reason": command.get("reason", "")})
    return systems[:20]


def _build_label(path: str) -> str:
    lowered = path.lower().replace("\\", "/")
    if lowered.endswith("package.json"):
        return "Node.js package"
    if lowered.endswith("pyproject.toml") or lowered.endswith("requirements.txt"):
        return "Python project"
    if lowered.endswith("cargo.toml"):
        return "Rust project"
    if lowered.endswith("go.mod"):
        return "Go module"
    if lowered.endswith("cmakelists.txt") or lowered.endswith(".vcxproj"):
        return "Native/C++ project"
    if lowered.endswith((".sln", ".slnx", ".csproj", ".fsproj", ".vbproj")):
        return ".NET solution"
    if lowered.endswith(("manifest.json", "packages-lock.json")) and lowered.startswith("packages/"):
        return "Unity project"
    return Path(path).name


def _project_id(root: Path) -> str:
    import hashlib

    return f"project-{hashlib.sha1(str(root).lower().encode('utf-8')).hexdigest()[:12]}"
