from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .safety import is_safe_to_read
from .validation import validation_summary
from .workspace import SOURCE_CODE_SUFFIXES, WorkspaceScanner


HEALTH_HISTORY_FILE = "health-history.json"
DAILY_REPORT_FILE = "daily-health-report.md"
WEEKLY_REPORT_FILE = "weekly-quality-summary.md"


class QualityPersistenceError(RuntimeError):
    """Raised when quality history cannot be persisted."""


def quality_dashboard(
    workspace: str | Path,
    *,
    record_snapshot: bool = False,
    scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    memory = ProjectMemory(root)
    history = _load_history(memory)
    snapshot = _build_snapshot(root, memory, history, scan=scan, persist=record_snapshot)
    trend = _trend(snapshot, history)
    report_paths: dict[str, str] = {}
    if record_snapshot:
        history = _append_history(memory, history, snapshot)
        report_paths = _write_quality_reports(memory, snapshot, history, trend)
    return {
        "workspace": str(root),
        "score": snapshot["score"],
        "grade": snapshot["grade"],
        "trend": trend,
        "statuses": snapshot["statuses"],
        "warnings": snapshot["warnings"],
        "failing_systems": snapshot["failing_systems"],
        "high_risk_files": snapshot["high_risk_files"],
        "top_risks": snapshot["top_risks"],
        "top_cleanup_tasks": snapshot["top_cleanup_tasks"],
        "recommended_next_improvement": snapshot["recommended_next_improvement"],
        "current_snapshot": snapshot,
        "history": history[-30:],
        "report_paths": report_paths,
        "history_path": str(memory.root / HEALTH_HISTORY_FILE),
    }


def record_quality_snapshot(workspace: str | Path) -> dict[str, Any]:
    return quality_dashboard(workspace, record_snapshot=True)


def planner_quality_summary(quality: dict[str, Any] | None) -> dict[str, Any]:
    if not quality:
        return {}
    return {
        "score": quality.get("score"),
        "grade": quality.get("grade"),
        "trend": quality.get("trend", {}),
        "top_risks": quality.get("top_risks", [])[:5],
        "high_risk_files": quality.get("high_risk_files", [])[:10],
        "recommended_next_improvement": quality.get("recommended_next_improvement"),
    }


def planner_guidance(quality: dict[str, Any] | None) -> list[str]:
    if not quality:
        return []
    guidance: list[str] = []
    statuses = quality.get("statuses", {})
    if _status_failed(statuses.get("build")) or _status_failed(statuses.get("test")):
        guidance.append("Prioritize broken build/test validation before new feature work.")
    if quality.get("top_risks"):
        guidance.append(f"Start with risk: {quality['top_risks'][0]['title']}.")
    if quality.get("high_risk_files"):
        guidance.append("Warn before editing high-risk files listed in the quality dashboard.")
    if quality.get("current_snapshot", {}).get("repeated_repair_attempts", 0) >= 2:
        guidance.append("Limit repair loops and prefer minimal fixes with focused validation.")
    if quality.get("current_snapshot", {}).get("untested_core_modules"):
        guidance.append("Prefer adding or running tests around unstable untested areas.")
    return guidance[:6]


def _build_snapshot(
    root: Path,
    memory: ProjectMemory,
    history: list[dict[str, Any]],
    *,
    scan: dict[str, Any] | None,
    persist: bool,
) -> dict[str, Any]:
    scan_data = scan or WorkspaceScanner(root).scan(persist=persist)
    validation = validation_summary(root)
    latest_validation = _latest_validation(memory)
    known_bugs = _known_bug_count(memory, scan_data)
    repair_attempts = _repair_attempts(memory)
    model_failures = _model_failure_count(memory)
    complexity_hotspots = _complexity_hotspots(scan_data)
    failing_files = _failing_files(latest_validation)
    stale_docs = _stale_documentation(scan_data)
    dependency = _dependency_snapshot(root, scan_data, history)
    diff = _git_diff_summary(root)
    files_changed_most = _files_changed_most(history, scan_data.get("recent_files", []))
    high_risk_files = _high_risk_files(scan_data, complexity_hotspots, failing_files, files_changed_most, diff)
    untested_modules = _untested_modules(scan_data)
    statuses = _statuses(validation, latest_validation)
    warnings = _warnings(scan_data, statuses, dependency, stale_docs, repair_attempts, model_failures, diff, untested_modules)
    top_risks = _top_risks(scan_data, statuses, dependency, stale_docs, repair_attempts, model_failures, complexity_hotspots, diff, untested_modules)
    cleanup_tasks = _cleanup_tasks(scan_data, statuses, dependency, stale_docs, high_risk_files, untested_modules)
    score = _health_score(scan_data, statuses, warnings, top_risks, repair_attempts, model_failures)
    return {
        "timestamp": utc_now(),
        "score": score,
        "grade": _grade(score),
        "workspace_name": root.name,
        "file_count": int(scan_data.get("file_count") or 0),
        "frameworks": scan_data.get("frameworks", []),
        "todo_count": len(scan_data.get("todo_comments", [])),
        "known_bug_count": known_bugs,
        "dependency_manifest_count": len(dependency["manifests"]),
        "dependency_file_count": dependency["dependency_file_count"],
        "dependency_changes": dependency["changes"],
        "statuses": statuses,
        "failing_systems": _failing_systems(statuses, latest_validation),
        "failing_files": failing_files[:10],
        "complexity_hotspots": complexity_hotspots[:10],
        "high_risk_files": high_risk_files[:10],
        "untested_core_modules": untested_modules[:10],
        "repeated_repair_attempts": repair_attempts,
        "repeated_model_failures": model_failures,
        "slow_validation_commands": _slow_validation_commands(memory),
        "files_changed_most_often": files_changed_most[:10],
        "large_risky_diff": diff,
        "stale_documentation": stale_docs,
        "warnings": warnings[:12],
        "top_risks": top_risks[:5],
        "top_cleanup_tasks": cleanup_tasks[:5],
        "recommended_next_improvement": _recommended_next_improvement(top_risks, cleanup_tasks),
    }


def _health_score(
    scan: dict[str, Any],
    statuses: dict[str, Any],
    warnings: list[str],
    risks: list[dict[str, Any]],
    repair_attempts: int,
    model_failures: int,
) -> int:
    score = 100
    if _status_failed(statuses.get("build")):
        score -= 20
    if _status_failed(statuses.get("test")):
        score -= 20
    if _status_failed(statuses.get("lint")):
        score -= 12
    if not statuses.get("validation", {}).get("commands"):
        score -= 8
    if not scan.get("test_files"):
        score -= 12
    if not scan.get("readmes"):
        score -= 8
    score -= min(15, len(scan.get("todo_comments", [])) // 3)
    score -= min(12, repair_attempts * 4)
    score -= min(8, model_failures * 2)
    score -= min(20, sum(int(risk.get("weight", 0)) for risk in risks))
    score -= min(8, max(0, len(warnings) - 3))
    return max(0, min(100, score))


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _statuses(validation: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    commands = validation.get("commands") if isinstance(validation.get("commands"), list) else []
    command_names = [str(command.get("name") or " ".join(command.get("command") or [])) for command in commands if isinstance(command, dict)]
    base = {
        "validation": {"status": "not_configured" if not command_names else "not_run", "commands": command_names},
        "build": {"status": "not_configured"},
        "test": {"status": "not_configured"},
        "lint": {"status": "not_configured"},
    }
    for name in command_names:
        lowered = name.lower()
        if any(token in lowered for token in ("build", "dotnet", "cargo", "cmake")):
            base["build"]["status"] = "not_run"
        if any(token in lowered for token in ("test", "pytest")):
            base["test"]["status"] = "not_run"
        if "lint" in lowered:
            base["lint"]["status"] = "not_run"
    if latest:
        status = "passed" if latest.get("status") == "passed" else "failed"
        command = str(latest.get("command") or "")
        base["validation"].update({"status": status, "latest_command": command, "latest_at": latest.get("timestamp")})
        lowered = command.lower()
        if any(token in lowered for token in ("build", "dotnet", "cargo", "cmake")):
            base["build"].update({"status": status, "latest_command": command})
        if any(token in lowered for token in ("test", "pytest")):
            base["test"].update({"status": status, "latest_command": command})
        if "lint" in lowered:
            base["lint"].update({"status": status, "latest_command": command})
        if all(base[key]["status"] == "not_configured" for key in ("build", "test", "lint")):
            base["build"].update({"status": status, "latest_command": command})
    return base


def _status_failed(status: Any) -> bool:
    return isinstance(status, dict) and status.get("status") == "failed"


def _latest_validation(memory: ProjectMemory) -> dict[str, Any]:
    text = _read_text(memory.root / "validation-log.md")
    if not text:
        return {}
    matches = list(re.finditer(r"^##\s+(.+?)\s+-\s+(passed|failed)\s*$", text, flags=re.MULTILINE))
    if not matches:
        return {}
    match = matches[-1]
    start = match.end()
    end = matches[-2].start() if len(matches) > 1 and matches[-2].start() > start else len(text)
    entry = text[start:end]
    command_match = re.search(r"Command:\s+`([^`]*)`", entry)
    return {
        "timestamp": match.group(1).strip(),
        "status": match.group(2).strip(),
        "command": command_match.group(1).strip() if command_match else "",
        "output": scrub(entry[-4000:]),
    }


def _failing_systems(statuses: dict[str, Any], latest: dict[str, Any]) -> list[str]:
    systems = [name for name in ("build", "test", "lint") if _status_failed(statuses.get(name))]
    if latest.get("status") == "failed" and "validation" not in systems:
        systems.append("validation")
    return systems


def _failing_files(latest: dict[str, Any]) -> list[str]:
    output = str(latest.get("output") or "")
    pattern = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:py|js|jsx|ts|tsx|cs|cpp|c|h|hpp|md))")
    files: list[str] = []
    for match in pattern.finditer(output):
        normalized = match.group(1).replace("\\", "/").lstrip("./")
        if normalized not in files:
            files.append(normalized)
    return files[:20]


def _known_bug_count(memory: ProjectMemory, scan: dict[str, Any]) -> int:
    text = _read_text(memory.root / "known-issues.md")
    issue_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.startswith("#") and any(token in line.lower() for token in ("bug", "issue", "fail", "error", "broken"))
    ]
    fixmes = [
        item
        for item in scan.get("todo_comments", [])
        if any(token in str(item.get("text", "")).lower() for token in ("fixme", "bug", "broken", "fail"))
    ]
    return len(issue_lines) + len(fixmes)


def _repair_attempts(memory: ProjectMemory) -> int:
    history = _read_json(memory.root / "agent-history.json", default=[])
    if not isinstance(history, list):
        return 0
    return sum(
        1
        for item in history[-100:]
        if isinstance(item, dict)
        and (
            str(item.get("agent_id", "")).lower() == "repair"
            or "repair" in str(item.get("event", "")).lower()
            or "repair" in str(item.get("summary", "")).lower()
        )
    )


def _model_failure_count(memory: ProjectMemory) -> int:
    text = _read_text(memory.root / "core-log.md")[-12000:]
    count = 0
    for line in text.splitlines():
        lowered = line.lower()
        if ("model" in lowered or "ollama" in lowered) and any(token in lowered for token in ("false", "fail", "error", "timeout", "unreachable")):
            count += 1
    return count


def _slow_validation_commands(memory: ProjectMemory) -> list[dict[str, str]]:
    text = _read_text(memory.root / "validation-log.md")[-20000:]
    slow: list[dict[str, str]] = []
    for entry in re.split(r"(?=^##\s+)", text, flags=re.MULTILINE):
        if "timed out" not in entry.lower() and "timeout" not in entry.lower():
            continue
        command = re.search(r"Command:\s+`([^`]*)`", entry)
        slow.append({"command": command.group(1) if command else "unknown", "reason": "Validation timeout detected."})
    return slow[-5:]


def _complexity_hotspots(scan: dict[str, Any]) -> list[dict[str, Any]]:
    symbol_index = scan.get("symbol_index", {}) if isinstance(scan.get("symbol_index"), dict) else {}
    dependency_files = scan.get("dependency_graph", {}).get("files", {}) if isinstance(scan.get("dependency_graph"), dict) else {}
    todos_by_file = Counter(str(item.get("file")) for item in scan.get("todo_comments", []) if isinstance(item, dict))
    hotspots: list[dict[str, Any]] = []
    paths = set(symbol_index) | set(dependency_files) | set(todos_by_file)
    for path in paths:
        symbol_count = len(symbol_index.get(path) or [])
        dependency_count = len(dependency_files.get(path) or [])
        todo_count = todos_by_file.get(path, 0)
        weight = symbol_count + dependency_count + (todo_count * 2)
        if weight < 8:
            continue
        hotspots.append(
            {
                "path": path,
                "weight": weight,
                "symbol_count": symbol_count,
                "dependency_count": dependency_count,
                "todo_count": todo_count,
            }
        )
    return sorted(hotspots, key=lambda item: item["weight"], reverse=True)


def _stale_documentation(scan: dict[str, Any]) -> dict[str, Any]:
    readmes = scan.get("readmes", [])
    recent = scan.get("recent_files", [])
    recent_code = [path for path in recent if Path(path).suffix.lower() in SOURCE_CODE_SUFFIXES]
    recent_docs = [path for path in recent if Path(path).suffix.lower() in {".md", ".txt"}]
    stale = not readmes or (len(recent_code) >= 8 and not recent_docs)
    return {"stale": stale, "readmes": readmes, "recent_code_files": recent_code[:20], "recent_doc_files": recent_docs[:20]}


def _dependency_snapshot(root: Path, scan: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    manifests = _dependency_manifests(root)
    dependency_file_count = len(scan.get("dependency_graph", {}).get("files", {})) if isinstance(scan.get("dependency_graph"), dict) else 0
    previous = history[-1] if history else {}
    previous_manifest_count = int(previous.get("dependency_manifest_count") or 0)
    previous_dependency_file_count = int(previous.get("dependency_file_count") or 0)
    changes: list[str] = []
    if previous and previous_manifest_count != len(manifests):
        changes.append(f"Dependency manifest count changed from {previous_manifest_count} to {len(manifests)}.")
    if previous and abs(previous_dependency_file_count - dependency_file_count) >= 10:
        changes.append(f"Dependency-bearing file count changed from {previous_dependency_file_count} to {dependency_file_count}.")
    return {"manifests": manifests, "dependency_file_count": dependency_file_count, "changes": changes}


def _dependency_manifests(root: Path) -> list[str]:
    names = {
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
    }
    manifests = []
    for name in sorted(names):
        path = root / name
        if path.is_file() and is_safe_to_read(path, root):
            manifests.append(name)
    return manifests


def _git_diff_summary(root: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "diff", "--numstat", "--"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "changed_files": 0, "total_added": 0, "total_deleted": 0, "large_files": []}
    if completed.returncode != 0:
        return {"available": False, "changed_files": 0, "total_added": 0, "total_deleted": 0, "large_files": []}
    changed_files = 0
    total_added = 0
    total_deleted = 0
    large_files: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added = _safe_int(parts[0])
        deleted = _safe_int(parts[1])
        path = parts[2]
        changed_files += 1
        total_added += added
        total_deleted += deleted
        if added + deleted >= 300:
            large_files.append({"path": path, "changed_lines": added + deleted})
    return {
        "available": True,
        "changed_files": changed_files,
        "total_added": total_added,
        "total_deleted": total_deleted,
        "large_files": large_files[:10],
    }


def _files_changed_most(history: list[dict[str, Any]], recent_files: list[str]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in history[-30:]:
        for path in item.get("files_changed_most_often", []):
            if isinstance(path, dict):
                counts[str(path.get("path") or "")] += int(path.get("count") or 1)
        for path in item.get("recent_files", []):
            counts[str(path)] += 1
    for path in recent_files:
        counts[str(path)] += 1
    return [{"path": path, "count": count} for path, count in counts.most_common(10) if path]


def _high_risk_files(
    scan: dict[str, Any],
    hotspots: list[dict[str, Any]],
    failing_files: list[str],
    frequent_files: list[dict[str, Any]],
    diff: dict[str, Any],
) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}

    def add(path: str, points: int, reason: str) -> None:
        if not path:
            return
        item = scores.setdefault(path, {"path": path, "score": 0, "reasons": []})
        item["score"] += points
        if reason not in item["reasons"]:
            item["reasons"].append(reason)

    for path in failing_files:
        add(path, 8, "Referenced in latest validation failure.")
    for hotspot in hotspots[:15]:
        add(str(hotspot.get("path")), min(8, int(hotspot.get("weight", 0)) // 3), "Complexity hotspot.")
    todos_by_file = Counter(str(item.get("file")) for item in scan.get("todo_comments", []) if isinstance(item, dict) and item.get("file"))
    for path, count in todos_by_file.items():
        add(path, min(6, count * 2), f"Contains {count} TODO/FIXME note{'s' if count != 1 else ''}.")
    for item in frequent_files[:10]:
        add(str(item.get("path")), min(6, int(item.get("count", 0))), "Frequently appears in recent changes.")
    for item in diff.get("large_files", []):
        add(str(item.get("path")), 8, "Large uncommitted diff.")
    return sorted(scores.values(), key=lambda item: item["score"], reverse=True)[:10]


def _untested_modules(scan: dict[str, Any]) -> list[dict[str, Any]]:
    code_paths = set(scan.get("symbol_index", {}).keys()) if isinstance(scan.get("symbol_index"), dict) else set()
    code_paths |= set(scan.get("dependency_graph", {}).get("files", {}).keys()) if isinstance(scan.get("dependency_graph"), dict) else set()
    tests = [str(path) for path in scan.get("test_files", [])]
    by_area: dict[str, int] = defaultdict(int)
    for path in code_paths:
        area = path.split("/", 1)[0] if "/" in path else "root"
        by_area[area] += 1
    untested = []
    for area, count in by_area.items():
        if not any(path.startswith(area + "/") or (area == "root" and "/" not in path) for path in tests):
            untested.append({"area": area, "code_file_count": count, "reason": "No nearby tests detected."})
    return sorted(untested, key=lambda item: item["code_file_count"], reverse=True)


def _warnings(
    scan: dict[str, Any],
    statuses: dict[str, Any],
    dependency: dict[str, Any],
    stale_docs: dict[str, Any],
    repair_attempts: int,
    model_failures: int,
    diff: dict[str, Any],
    untested_modules: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if _status_failed(statuses.get("build")):
        warnings.append("Latest build validation failed.")
    if _status_failed(statuses.get("test")):
        warnings.append("Latest test validation failed.")
    if not scan.get("test_files"):
        warnings.append("No test files detected.")
    if len(scan.get("todo_comments", [])) >= 10:
        warnings.append("TODO/FIXME backlog is growing.")
    if not dependency["manifests"]:
        warnings.append("No dependency manifest detected.")
    warnings.extend(dependency["changes"])
    if stale_docs.get("stale"):
        warnings.append("Documentation may be stale or missing.")
    if repair_attempts >= 2:
        warnings.append("Repeated repair attempts detected.")
    if model_failures >= 2:
        warnings.append("Repeated model/Ollama failures detected.")
    if diff.get("changed_files", 0) >= 20 or diff.get("total_added", 0) + diff.get("total_deleted", 0) >= 1000:
        warnings.append("Large uncommitted diff detected.")
    if untested_modules:
        warnings.append("Some active code areas have no nearby tests.")
    return warnings


def _top_risks(
    scan: dict[str, Any],
    statuses: dict[str, Any],
    dependency: dict[str, Any],
    stale_docs: dict[str, Any],
    repair_attempts: int,
    model_failures: int,
    hotspots: list[dict[str, Any]],
    diff: dict[str, Any],
    untested_modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    def add(title: str, severity: str, reason: str, weight: int) -> None:
        risks.append({"title": title, "severity": severity, "reason": reason, "weight": weight})

    if _status_failed(statuses.get("build")) or _status_failed(statuses.get("test")):
        add("Broken validation", "high", "Latest validation log reports a failure.", 6)
    if not scan.get("test_files"):
        add("Untested project surface", "high", "No test files were detected by the scanner.", 5)
    if hotspots:
        add("Complexity hotspot", "medium", f"`{hotspots[0]['path']}` has high symbols/dependencies/TODO weight.", 4)
    if stale_docs.get("stale"):
        add("Stale documentation", "medium", "Documentation is missing or recent code changed without recent docs.", 3)
    if dependency["changes"]:
        add("Dependency drift", "medium", dependency["changes"][0], 3)
    if repair_attempts >= 2:
        add("Repeated repairs", "medium", "Repair activity is recurring; prefer smaller fixes with targeted validation.", 4)
    if model_failures >= 2:
        add("Repeated model failures", "medium", "Core logs show repeated model/Ollama failures.", 3)
    if diff.get("changed_files", 0) >= 20 or diff.get("large_files"):
        add("Large risky diff", "high", "Uncommitted changes are broad or include large files.", 5)
    if untested_modules:
        add("Untested active modules", "medium", f"`{untested_modules[0]['area']}` has code but no nearby tests.", 4)
    if len(scan.get("todo_comments", [])) >= 10:
        add("Large TODO backlog", "low", "TODO/FIXME comments need triage.", 2)
    return sorted(risks, key=lambda item: item["weight"], reverse=True)


def _cleanup_tasks(
    scan: dict[str, Any],
    statuses: dict[str, Any],
    dependency: dict[str, Any],
    stale_docs: dict[str, Any],
    high_risk_files: list[dict[str, Any]],
    untested_modules: list[dict[str, Any]],
) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    if _status_failed(statuses.get("build")) or _status_failed(statuses.get("test")):
        tasks.append({"title": "Fix latest validation failure", "reason": "Broken validation should block feature work."})
    if untested_modules:
        tasks.append({"title": f"Add validation around {untested_modules[0]['area']}", "reason": "Active code area has no nearby tests."})
    if high_risk_files:
        tasks.append({"title": f"Review high-risk file {high_risk_files[0]['path']}", "reason": "File combines failure, complexity, TODO, or churn signals."})
    if len(scan.get("todo_comments", [])) > 0:
        tasks.append({"title": "Triage TODO/FIXME backlog", "reason": "Turn stale comments into real tasks or remove obsolete notes."})
    if stale_docs.get("stale"):
        tasks.append({"title": "Refresh README or architecture notes", "reason": "Documentation appears stale relative to code activity."})
    if dependency["changes"]:
        tasks.append({"title": "Review dependency drift", "reason": dependency["changes"][0]})
    if not tasks:
        tasks.append({"title": "Run a quality snapshot after the next change", "reason": "No urgent cleanup task was detected."})
    return tasks[:5]


def _recommended_next_improvement(risks: list[dict[str, Any]], cleanup_tasks: list[dict[str, str]]) -> str:
    if risks:
        return f"{cleanup_tasks[0]['title']}: {cleanup_tasks[0]['reason']}" if cleanup_tasks else str(risks[0]["title"])
    return cleanup_tasks[0]["title"] if cleanup_tasks else "Keep the project stable with small validated changes."


def _trend(snapshot: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"direction": "new", "score_delta": 0, "summary": "No prior health snapshot."}
    previous = history[-1]
    delta = int(snapshot.get("score", 0)) - int(previous.get("score", 0))
    if delta >= 5:
        direction = "improving"
    elif delta <= -5:
        direction = "degrading"
    else:
        direction = "stable"
    return {
        "direction": direction,
        "score_delta": delta,
        "previous_score": previous.get("score"),
        "current_score": snapshot.get("score"),
        "file_count_delta": int(snapshot.get("file_count", 0)) - int(previous.get("file_count", 0)),
        "todo_count_delta": int(snapshot.get("todo_count", 0)) - int(previous.get("todo_count", 0)),
        "summary": f"Health score changed by {delta} points.",
    }


def _append_history(memory: ProjectMemory, history: list[dict[str, Any]], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    compact = {
        key: snapshot[key]
        for key in (
            "timestamp",
            "score",
            "grade",
            "file_count",
            "todo_count",
            "known_bug_count",
            "dependency_manifest_count",
            "dependency_file_count",
            "statuses",
            "failing_files",
            "high_risk_files",
            "files_changed_most_often",
            "warnings",
            "top_risks",
        )
    }
    history.append(compact)
    history = history[-365:]
    _ensure_json_target(memory.root / HEALTH_HISTORY_FILE)
    memory.write_json(HEALTH_HISTORY_FILE, history)
    persisted = _load_history(memory)
    if persisted != history:
        raise QualityPersistenceError(
            f"Could not persist quality health history at {memory.root / HEALTH_HISTORY_FILE}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    return history


def _ensure_json_target(path: Path) -> None:
    if path.parent.exists() and not path.parent.is_dir():
        raise QualityPersistenceError(
            f"Could not persist quality health history because {path.parent} is not a directory."
        )
    if path.exists() and not path.is_file():
        raise QualityPersistenceError(
            f"Could not persist quality health history because {path} is not a writable file."
        )


def _write_quality_reports(
    memory: ProjectMemory,
    snapshot: dict[str, Any],
    history: list[dict[str, Any]],
    trend: dict[str, Any],
) -> dict[str, str]:
    daily = memory.write_generated_markdown(DAILY_REPORT_FILE, "Daily Health Report", _render_daily_report(snapshot, trend))
    weekly = memory.write_generated_markdown(WEEKLY_REPORT_FILE, "Weekly Quality Summary", _render_weekly_report(snapshot, history, trend))
    return {"daily_health_report": str(daily), "weekly_quality_summary": str(weekly)}


def _render_daily_report(snapshot: dict[str, Any], trend: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"## Health Score: {snapshot['score']} ({snapshot['grade']})",
            "",
            f"- Trend: {trend.get('direction')} ({trend.get('score_delta')} points)",
            f"- Files indexed: {snapshot.get('file_count')}",
            f"- TODO/FIXME comments: {snapshot.get('todo_count')}",
            f"- Known bugs: {snapshot.get('known_bug_count')}",
            "",
            "## Top Risks",
            "",
            *[f"- {item['title']} [{item['severity']}]: {item['reason']}" for item in snapshot.get("top_risks", [])],
            "",
            "## Suggested Cleanup",
            "",
            *[f"- {item['title']}: {item['reason']}" for item in snapshot.get("top_cleanup_tasks", [])],
            "",
            f"Recommended next improvement: {snapshot.get('recommended_next_improvement')}",
        ]
    )


def _render_weekly_report(snapshot: dict[str, Any], history: list[dict[str, Any]], trend: dict[str, Any]) -> str:
    recent = history[-7:]
    scores = [int(item.get("score", 0)) for item in recent]
    average = round(sum(scores) / len(scores), 1) if scores else snapshot["score"]
    recurring_failures = sum(1 for item in recent if _status_failed(item.get("statuses", {}).get("validation")))
    return "\n".join(
        [
            f"## Weekly Quality Summary: {snapshot['workspace_name']}",
            "",
            f"- Current score: {snapshot['score']} ({snapshot['grade']})",
            f"- 7-snapshot average: {average}",
            f"- Trend: {trend.get('direction')}",
            f"- Validation failures in recent snapshots: {recurring_failures}",
            "",
            "## Files Changed Most Often",
            "",
            *[f"- `{item['path']}` ({item['count']})" for item in snapshot.get("files_changed_most_often", [])[:5]],
            "",
            "## Top Risks",
            "",
            *[f"- {item['title']}: {item['reason']}" for item in snapshot.get("top_risks", [])],
        ]
    )


def _load_history(memory: ProjectMemory) -> list[dict[str, Any]]:
    data = _read_json(memory.root / HEALTH_HISTORY_FILE, default=[])
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
    except OSError:
        return ""


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
