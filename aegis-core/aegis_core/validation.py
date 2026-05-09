from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .safety import is_ignored_path, is_safe_to_read


VALIDATION_LOG_FILE = "validation-log.md"
DOTNET_PROJECT_SUFFIXES = {".csproj", ".fsproj", ".vbproj"}
PACKAGE_VALIDATION_SCRIPTS = ("test", "lint", "typecheck", "type-check", "build")
NESTED_WORKSPACE_MARKER_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "cargo.toml",
    "cmakelists.txt",
}
NESTED_WORKSPACE_MARKER_SUFFIXES = {".sln", ".slnx"}


@dataclass
class ValidationCommand:
    name: str
    command: list[str]
    reason: str


def detect_validation_commands(workspace: str | Path) -> list[ValidationCommand]:
    root = Path(workspace).resolve()
    commands: list[ValidationCommand] = []
    package_scripts = _package_scripts(root)
    if package_scripts:
        package_manager = _detect_package_manager(root)
        for script in PACKAGE_VALIDATION_SCRIPTS:
            if script in package_scripts:
                commands.append(_package_script_command(package_manager, script))
    if _has_dotnet_solution(root) or _has_project_file(root, DOTNET_PROJECT_SUFFIXES):
        commands.append(ValidationCommand("dotnet build", ["dotnet", "build"], ".NET project or solution detected"))
    if _has_root_file_named(root, "Cargo.toml"):
        commands.append(ValidationCommand("cargo check", ["cargo", "check"], "Cargo.toml detected"))
    if _has_root_file_named(root, "pyproject.toml") or _has_root_file_named(root, "requirements.txt"):
        commands.append(ValidationCommand("python -m pytest", ["python", "-m", "pytest"], "Python project detected"))
    if _has_root_file_named(root, "CMakeLists.txt"):
        commands.append(ValidationCommand("cmake build", ["cmake", "--build", "build"], "CMakeLists.txt detected"))
    return commands


def _package_scripts(root: Path) -> dict[str, str]:
    package_json = root / "package.json"
    if not _is_root_file(package_json, root):
        return {}
    try:
        package = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    return {str(name): str(command) for name, command in scripts.items() if isinstance(command, str) and command.strip()}


def _detect_package_manager(root: Path) -> str:
    if _has_root_file_named(root, "pnpm-lock.yaml"):
        return "pnpm"
    if _has_root_file_named(root, "yarn.lock"):
        return "yarn"
    return "npm"


def _package_script_command(package_manager: str, script: str) -> ValidationCommand:
    if package_manager == "npm":
        if script == "test":
            return ValidationCommand("npm test", ["npm", "test"], "package.json test script detected")
        return ValidationCommand(f"npm run {script}", ["npm", "run", script], f"package.json {script} script detected")
    return ValidationCommand(
        f"{package_manager} {script}",
        [package_manager, script],
        f"package.json {script} script and {package_manager} lockfile detected",
    )


def _has_dotnet_solution(root: Path) -> bool:
    try:
        children = root.iterdir()
    except OSError:
        return False
    for child in children:
        if child.suffix.lower() in {".sln", ".slnx"} and _solution_references_dotnet_project(child, root):
            return True
    return False


def _solution_references_dotnet_project(path: Path, root: Path) -> bool:
    if not _is_root_file(path, root):
        return False
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return False
    lowered = text[:200000].lower()
    return any(suffix in lowered for suffix in DOTNET_PROJECT_SUFFIXES)


def _has_root_file_named(root: Path, name: str) -> bool:
    return _is_root_file(root / name, root)


def _is_root_file(path: Path, root: Path) -> bool:
    try:
        return path.is_file() and is_safe_to_read(path, root)
    except OSError:
        return False


def _has_project_file(root: Path, suffixes: set[str], max_seen: int = 5000) -> bool:
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not is_ignored_path(base / name, root)
            and not _is_nested_workspace_boundary(base / name, root)
        ]
        for filename in filenames:
            seen += 1
            if seen > max_seen:
                return False
            path = base / filename
            if path.suffix.lower() in suffixes and is_safe_to_read(path, root):
                return True
    return False


def _is_nested_workspace_boundary(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        resolved_path.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return True
    if resolved_path == resolved_root:
        return False

    try:
        children = path.iterdir()
    except OSError:
        return False
    for child in children:
        if not _is_root_file(child, root):
            continue
        if child.name.lower() in NESTED_WORKSPACE_MARKER_FILES or child.suffix.lower() in NESTED_WORKSPACE_MARKER_SUFFIXES:
            return True
    return False


def validation_summary(workspace: str | Path) -> dict[str, Any]:
    commands = detect_validation_commands(workspace)
    return {"workspace": str(Path(workspace).resolve()), "commands": [command.__dict__ for command in commands]}


def run_validation(workspace: str | Path, command: list[str] | None = None, timeout: int = 120) -> dict[str, Any]:
    root = Path(workspace).resolve()
    detected_commands = [] if command else detect_validation_commands(root)
    selected = command or (detected_commands[0].command if detected_commands else None)
    if not selected:
        return {"ok": False, "command": None, "stdout": "", "stderr": "No validation command detected."}
    if not is_safe_validation_command(selected):
        result = {
            "ok": False,
            "command": selected,
            "returncode": None,
            "stdout": "",
            "stderr": f"Blocked unsafe validation command: {' '.join(selected)}",
            "blocked": True,
        }
        return _record_validation_result(root, result)

    try:
        run_command = _resolve_validation_command(selected)
        completed = subprocess.run(
            run_command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError as exc:
        result = {
            "ok": False,
            "command": selected,
            "returncode": None,
            "stdout": "",
            "stderr": f"Validation executable not found: {exc.filename or selected[0]}",
        }
        return _record_validation_result(root, result)
    except OSError as exc:
        result = {
            "ok": False,
            "command": selected,
            "returncode": None,
            "stdout": "",
            "stderr": f"Validation command failed to start: {exc}",
            "start_failed": True,
        }
        return _record_validation_result(root, result)
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "command": selected,
            "returncode": None,
            "stdout": _scrub_tail(exc.stdout),
            "stderr": f"Validation timed out after {timeout} seconds.\n{_scrub_tail(exc.stderr)}".strip(),
            "timed_out": True,
        }
        return _record_validation_result(root, result)
    result = {
        "ok": completed.returncode == 0,
        "command": selected,
        "returncode": completed.returncode,
        "stdout": _scrub_tail(completed.stdout),
        "stderr": _scrub_tail(completed.stderr),
    }
    return _record_validation_result(root, result)


def _resolve_validation_command(command: list[str]) -> list[str]:
    if os.name != "nt" or not command:
        return command
    executable = str(command[0])
    name = _normalized_executable_name(executable)
    if name in {"npm", "pnpm", "yarn"}:
        resolved = shutil.which(executable) or shutil.which(f"{name}.cmd") or shutil.which(name)
        if resolved:
            return [resolved, *command[1:]]
    return command


def is_safe_validation_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = _normalized_executable_name(str(command[0]))
    args = [str(item) for item in command[1:]]
    if executable == "npm":
        return args in (["test"], ["run", "build"], ["run", "lint"], ["run", "typecheck"], ["run", "type-check"])
    if executable in {"pnpm", "yarn"}:
        return args in (["test"], ["build"], ["lint"], ["typecheck"], ["type-check"])
    if executable == "dotnet":
        return args == ["build"]
    if executable == "cargo":
        return args == ["check"]
    if executable == "go":
        return args == ["test", "./..."]
    if executable == "cmake":
        return args == ["--build", "build"]
    if executable in {"python", "python.exe", "py", "py.exe"} or executable == Path(sys.executable).name.lower():
        return args == ["-m", "pytest"]
    return False


def _normalized_executable_name(executable: str) -> str:
    raw = str(executable).strip().strip('"').strip("'")
    name = raw.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".cmd", ".bat", ".exe"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _decode_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _scrub_tail(value: Any, limit: int = 12000) -> str:
    return scrub(_decode_output(value)[-(limit * 2):])[-limit:]


def append_validation_log(workspace: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    memory = ProjectMemory(workspace)
    memory.ensure()
    path = memory.root / VALIDATION_LOG_FILE
    command = scrub(" ".join(result.get("command") or []))
    status = "passed" if result.get("ok") else "failed"
    output = scrub((result.get("stderr") or result.get("stdout") or "").strip())
    entry = f"## {utc_now()} - {status}\n\nCommand: `{command}`\n\n```text\n{output[:4000]}\n```\n\n"
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except OSError as exc:
        return _validation_log_status(path, False, f"Could not persist validation log at {path}: {exc}")
    if not path.is_file():
        return _validation_log_status(path, False, f"Could not persist validation log at {path}.")
    return _validation_log_status(path, True)


def _record_validation_result(workspace: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    log_status = append_validation_log(workspace, result)
    result["validation_log"] = log_status
    if not log_status.get("persisted"):
        result["memory_warning"] = log_status.get("warning") or "Could not persist validation log."
    return result


def _validation_log_status(path: Path, persisted: bool, warning: str | None = None) -> dict[str, Any]:
    return {
        "path": str(path),
        "persisted": persisted,
        "warning": scrub(warning) if warning else None,
    }
