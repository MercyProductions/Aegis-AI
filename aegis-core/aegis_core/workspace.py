from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory
from .safety import IGNORED_DIRS, is_ignored_path, is_safe_to_read


DOTNET_PROJECT_SUFFIXES = {".csproj", ".fsproj", ".vbproj"}
DOTNET_FRAMEWORK_BY_SUFFIX = {
    ".csproj": "C#/.NET",
    ".fsproj": "F#/.NET",
    ".vbproj": "VB.NET",
}
BUILD_FILE_SUFFIXES = {".sln", ".slnx", ".vcxproj"} | DOTNET_PROJECT_SUFFIXES
SOURCE_CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".cs",
    ".fs",
    ".fsi",
    ".fsx",
    ".vb",
    ".cpp",
    ".cxx",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".xaml",
}
DEPENDENCY_GRAPH_SUFFIXES = SOURCE_CODE_SUFFIXES - {".xaml"}
TODO_SCAN_SUFFIXES = SOURCE_CODE_SUFFIXES | {".md"}

TEXT_SUFFIXES = {
    *SOURCE_CODE_SUFFIXES,
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".sln",
    ".slnx",
    ".fsproj",
    ".vbproj",
    ".csproj",
    ".vcxproj",
    ".props",
    ".targets",
    ".cmake",
}


def _is_safe_file(path: Path, workspace: str | Path) -> bool:
    try:
        return path.is_file() and is_safe_to_read(path, workspace)
    except OSError:
        return False


def _is_safe_dir(path: Path, workspace: str | Path) -> bool:
    try:
        return path.is_dir() and not is_ignored_path(path, workspace)
    except OSError:
        return False


LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "React",
    ".ts": "TypeScript",
    ".tsx": "React/TypeScript",
    ".cs": "C#",
    ".fs": "F#",
    ".fsi": "F#",
    ".fsx": "F#",
    ".vb": "Visual Basic",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".c": "C/C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".go": "Go",
    ".rs": "Rust",
    ".xaml": "XAML",
}

BUILD_FILE_NAMES = {
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
    "packages.config",
    "packages.lock.json",
    "Directory.Packages.props",
    "Directory.Build.props",
    "Directory.Build.targets",
    "CMakeLists.txt",
    "Makefile",
}


@dataclass
class ScanOptions:
    max_files: int = 5000
    max_file_bytes: int = 300000


class WorkspaceScanner:
    def __init__(self, workspace: str | Path, options: ScanOptions | None = None):
        self.workspace = Path(workspace).resolve()
        self.options = options or ScanOptions()

    def scan(self, persist: bool = True) -> dict[str, Any]:
        files = self._collect_files()
        fingerprint = self._scan_fingerprint(files)
        if persist:
            cached = self._load_cached_scan(fingerprint)
            if cached:
                cached["cache_hit"] = True
                cached["cache_reason"] = "workspace file fingerprint unchanged"
                return cached

        language_counts = Counter(LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), path.suffix.lower() or "other") for path in files)
        build_files = [self._rel(path) for path in files if path.name in BUILD_FILE_NAMES or path.suffix.lower() in BUILD_FILE_SUFFIXES]
        readmes = [self._rel(path) for path in files if path.name.lower().startswith("readme")]
        tests = [self._rel(path) for path in files if self._is_test_file(path)]
        recent = sorted(files, key=self._mtime_or_zero, reverse=True)[:20]
        todo_comments = self._find_todos(files)
        dependency_graph = self._dependency_graph(files)
        symbol_index = self._symbol_index(files)
        frameworks = self._detect_frameworks(files)

        result = {
            "workspace": str(self.workspace),
            "workspace_name": self.workspace.name,
            "frameworks": frameworks,
            "languages": dict(language_counts.most_common()),
            "file_count": len(files),
            "build_files": build_files,
            "readmes": readmes[:20],
            "test_files": tests[:50],
            "entry_points": self._entry_points(files),
            "todo_comments": todo_comments[:100],
            "recent_files": [self._rel(path) for path in recent],
            "ignored_dirs": sorted(IGNORED_DIRS),
            "dependency_graph": dependency_graph,
            "symbol_index": symbol_index,
            "scan_fingerprint": fingerprint,
            "cache_hit": False,
        }

        if persist:
            memory = ProjectMemory(self.workspace)
            memory.ensure()
            artifacts = self._persist_scan_artifacts(memory, files, dependency_graph, symbol_index, fingerprint, result)
            result["memory_artifacts"] = artifacts
            warnings = [str(item["warning"]) for item in artifacts if item.get("warning")]
            if warnings:
                result["memory_warnings"] = warnings

        return result

    def _collect_files(self) -> list[Path]:
        collected: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.workspace):
            base = Path(dirpath)
            dirnames[:] = [name for name in dirnames if not is_ignored_path(base / name, self.workspace)]
            for filename in filenames:
                if len(collected) >= self.options.max_files:
                    return collected
                path = base / filename
                if not is_safe_to_read(path, self.workspace):
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in BUILD_FILE_NAMES:
                    continue
                try:
                    if path.stat().st_size > self.options.max_file_bytes:
                        continue
                except OSError:
                    continue
                collected.append(path)
        return collected

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.workspace).as_posix()
        except ValueError:
            return str(path)

    def _file_index(self, files: list[Path]) -> list[dict[str, Any]]:
        index = []
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            index.append({
                "path": self._rel(path),
                "suffix": path.suffix.lower(),
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
            })
        return index

    def _mtime_or_zero(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    def _scan_fingerprint(self, files: list[Path]) -> dict[str, Any]:
        max_mtime = 0
        total_size = 0
        suffix_counts = Counter()
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            max_mtime = max(max_mtime, int(stat.st_mtime))
            total_size += stat.st_size
            suffix_counts[path.suffix.lower() or path.name] += 1
        return {
            "file_count": len(files),
            "max_modified": max_mtime,
            "total_size": total_size,
            "suffixes": dict(sorted(suffix_counts.items())),
        }

    def _load_cached_scan(self, fingerprint: dict[str, Any]) -> dict[str, Any] | None:
        cache_path = ProjectMemory(self.workspace).root / "scan-cache.json"
        if not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if cached.get("fingerprint") != fingerprint:
            return None
        result = cached.get("result")
        return result if isinstance(result, dict) else None

    def _persist_scan_artifacts(
        self,
        memory: ProjectMemory,
        files: list[Path],
        dependency_graph: dict[str, Any],
        symbol_index: dict[str, Any],
        fingerprint: dict[str, Any],
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        artifacts = [
            self._write_json_artifact(memory, "file-index.json", self._file_index(files)),
            self._write_json_artifact(memory, "dependency-graph.json", dependency_graph),
            self._write_json_artifact(memory, "symbol-index.json", symbol_index),
            self._write_markdown_artifact(memory, "project-summary.md", "Project Summary", render_project_summary(result)),
            self._write_markdown_artifact(memory, "architecture-map.md", "Architecture Map", render_architecture_map(result)),
        ]
        cached_result = dict(result)
        cached_result["memory_artifacts"] = artifacts
        warnings = [str(item["warning"]) for item in artifacts if item.get("warning")]
        if warnings:
            cached_result["memory_warnings"] = warnings
        cache_payload = {"fingerprint": fingerprint, "result": cached_result}
        artifacts.append(self._write_json_artifact(memory, "scan-cache.json", cache_payload))
        return artifacts

    def _write_json_artifact(self, memory: ProjectMemory, name: str, payload: Any) -> dict[str, Any]:
        path = memory.root / name
        warning = _target_warning(path)
        if warning:
            return _artifact_status(path, False, warning)
        memory.write_json(name, payload)
        try:
            persisted = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        except (OSError, json.JSONDecodeError) as exc:
            return _artifact_status(path, False, f"Could not persist scan artifact at {path}: {exc}")
        if persisted != payload:
            return _artifact_status(path, False, f"Could not persist scan artifact at {path}.")
        return _artifact_status(path, True)

    def _write_markdown_artifact(self, memory: ProjectMemory, name: str, title: str, body: str) -> dict[str, Any]:
        path = memory.root / name
        warning = _target_warning(path)
        if warning:
            return _artifact_status(path, False, warning)
        memory.write_generated_markdown(name, title, body)
        try:
            persisted = path.read_text(encoding="utf-8") if path.is_file() else ""
        except OSError as exc:
            return _artifact_status(path, False, f"Could not persist scan artifact at {path}: {exc}")
        if body.rstrip() not in persisted:
            return _artifact_status(path, False, f"Could not persist scan artifact at {path}.")
        return _artifact_status(path, True)

    def _detect_frameworks(self, files: list[Path]) -> list[str]:
        names = {path.name for path in files}
        rels = {self._rel(path) for path in files}
        lower_rels = {item.lower() for item in rels}
        frameworks: set[str] = set()
        package_json = self.workspace / "package.json"
        if _is_safe_file(package_json, self.workspace):
            try:
                package = json.loads(package_json.read_text(encoding="utf-8-sig"))
                dependencies = package.get("dependencies", {}) if isinstance(package, dict) else {}
                dev_dependencies = package.get("devDependencies", {}) if isinstance(package, dict) else {}
                deps = {
                    **(dependencies if isinstance(dependencies, dict) else {}),
                    **(dev_dependencies if isinstance(dev_dependencies, dict) else {}),
                }
                if "next" in deps:
                    frameworks.add("Next.js")
                if "vite" in deps:
                    frameworks.add("Vite")
                if "react" in deps:
                    frameworks.add("React")
                if "express" in deps:
                    frameworks.add("Node/Express")
            except (OSError, json.JSONDecodeError):
                frameworks.add("Node")
        if any(item.endswith(".sln") or item.endswith(".slnx") for item in lower_rels):
            frameworks.add("Visual Studio Solution")
        for suffix, framework in DOTNET_FRAMEWORK_BY_SUFFIX.items():
            if any(item.endswith(suffix) for item in lower_rels):
                frameworks.add(framework)
        if any(item.endswith(".vcxproj") for item in lower_rels):
            frameworks.add("C++/MSBuild")
        if "ProjectSettings.asset" in names or (
            _is_safe_dir(self.workspace / "Assets", self.workspace)
            and _is_safe_dir(self.workspace / "ProjectSettings", self.workspace)
        ):
            frameworks.add("Unity")
        if "pyproject.toml" in names or "requirements.txt" in names:
            frameworks.add("Python")
        if "Cargo.toml" in names:
            frameworks.add("Rust")
        if "CMakeLists.txt" in names:
            frameworks.add("CMake")
        return sorted(frameworks) or ["Unknown"]

    def _entry_points(self, files: list[Path]) -> list[str]:
        candidates = []
        for path in files:
            rel = self._rel(path)
            lower = rel.lower()
            if lower in {"main.py", "app.py", "program.cs", "program.fs", "program.vb", "index.js", "server.js"}:
                candidates.append(rel)
            elif lower.endswith(("/program.cs", "/program.fs", "/program.vb", "/main.py", "/main.ts", "/main.tsx", "/app.tsx", "/index.tsx")):
                candidates.append(rel)
        return candidates[:50]

    def _is_test_file(self, path: Path) -> bool:
        rel = self._rel(path).lower()
        name = path.name.lower()
        return (
            "/test/" in rel
            or "/tests/" in rel
            or name.startswith("test_")
            or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", "tests.cs", "tests.fs", "tests.vb"))
            or "test" in name and path.suffix.lower() in {".cs", ".fs", ".vb", ".py", ".js", ".ts", ".tsx"}
        )

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _find_todos(self, files: list[Path]) -> list[dict[str, Any]]:
        todos = []
        for path in files:
            if path.suffix.lower() not in TODO_SCAN_SUFFIXES:
                continue
            for number, line in enumerate(self._read_text(path).splitlines(), start=1):
                lowered = line.lower()
                if "todo" in lowered or "fixme" in lowered:
                    todos.append({"file": self._rel(path), "line": number, "text": line.strip()[:220]})
                    if len(todos) >= 100:
                        return todos
        return todos

    def _dependency_graph(self, files: list[Path]) -> dict[str, Any]:
        graph: dict[str, list[str]] = defaultdict(list)
        import_patterns = [
            re.compile(r"^\s*import\s+.+?from\s+[\"'](.+?)[\"']"),
            re.compile(r"^\s*import\s+[\"'](.+?)[\"']"),
            re.compile(r"^\s*from\s+([\w.]+)\s+import\s+"),
            re.compile(r"^\s*using\s+([\w.]+)\s*;"),
            re.compile(r"^\s*open\s+([\w.]+)"),
            re.compile(r"^\s*Imports\s+([\w.]+)", re.IGNORECASE),
            re.compile(r"^\s*#include\s+[<\"](.+?)[>\"]"),
        ]
        for path in files:
            if path.suffix.lower() not in DEPENDENCY_GRAPH_SUFFIXES:
                continue
            deps: list[str] = []
            for line in self._read_text(path).splitlines()[:500]:
                for pattern in import_patterns:
                    match = pattern.search(line)
                    if match:
                        deps.append(match.group(1))
                        break
            if deps:
                graph[self._rel(path)] = sorted(set(deps))
        return {"files": graph}

    def _symbol_index(self, files: list[Path]) -> dict[str, list[dict[str, Any]]]:
        symbols: dict[str, list[dict[str, Any]]] = defaultdict(list)
        patterns = {
            "module": re.compile(r"^\s*(?:(?:public|private|friend|protected)\s+)*(?:module|namespace)\s+([A-Za-z_][\w.]*)", re.IGNORECASE),
            "class": re.compile(r"\b(?:class|interface|struct|enum|type)\s+([A-Za-z_][\w]*)", re.IGNORECASE),
            "function": re.compile(
                r"\b(?:function|def)\s+([A-Za-z_][\w]*)"
                r"|^\s*(?:(?:public|private|protected|internal|friend)\s+)*"
                r"(?:(?:static|shared|async|virtual|override)\s+)*[\w<>\[\],]+\s+([A-Za-z_][\w]*)\s*\("
                r"|^\s*let\s+(?:private\s+|rec\s+|inline\s+)*([A-Za-z_][\w]*)\b",
                re.IGNORECASE,
            ),
            "component": re.compile(r"\b(?:export\s+default\s+)?function\s+([A-Z][A-Za-z0-9_]*)\s*\("),
        }
        for path in files:
            if path.suffix.lower() not in SOURCE_CODE_SUFFIXES:
                continue
            text = self._read_text(path)
            for number, line in enumerate(text.splitlines(), start=1):
                for kind, pattern in patterns.items():
                    match = pattern.search(line)
                    if match:
                        name = next((group for group in match.groups() if group), None)
                        if name:
                            symbols[self._rel(path)].append({"kind": kind, "name": name, "line": number})
        return symbols


def render_project_summary(scan: dict[str, Any]) -> str:
    languages = ", ".join(f"{name} ({count})" for name, count in scan["languages"].items())
    frameworks = ", ".join(scan["frameworks"])
    return "\n".join([
        f"Workspace: `{scan['workspace_name']}`",
        "",
        f"Detected frameworks: {frameworks}",
        f"Indexed files: {scan['file_count']}",
        f"Languages: {languages or 'none detected'}",
        "",
        "Build/project files:",
        *[f"- `{item}`" for item in scan["build_files"][:30]],
        "",
        "Likely entry points:",
        *[f"- `{item}`" for item in scan["entry_points"][:30]],
    ])


def render_architecture_map(scan: dict[str, Any]) -> str:
    return "\n".join([
        f"Workspace: `{scan['workspace_name']}`",
        "",
        "Major systems inferred from local files:",
        *[f"- {item}" for item in scan["frameworks"]],
        "",
        "Tests:",
        *[f"- `{item}`" for item in scan["test_files"][:30]],
        "",
        "Risk areas to review first:",
        "- Build files and package configuration",
        "- Files with TODO/FIXME comments",
        "- Recent modified files",
        "- Areas with no nearby tests",
    ])


def _target_warning(path: Path) -> str | None:
    if path.parent.exists() and not path.parent.is_dir():
        return f"Could not persist scan artifact because {path.parent} is not a directory."
    if path.exists() and not path.is_file():
        return f"Could not persist scan artifact because {path} is not a writable file."
    return None


def _artifact_status(path: Path, persisted: bool, warning: str | None = None) -> dict[str, Any]:
    return {
        "path": str(path),
        "persisted": persisted,
        "warning": scrub(warning) if warning else None,
    }
