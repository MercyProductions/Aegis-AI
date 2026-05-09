from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory import ProjectMemory, utc_now


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
        if "test" in package_scripts:
            commands.append(_package_script_command(package_manager, "test"))
        if "build" in package_scripts:
            commands.append(_package_script_command(package_manager, "build"))
    if any(root.glob("*.sln")) or any(root.glob("*.slnx")) or any(root.rglob("*.csproj")):
        commands.append(ValidationCommand("dotnet build", ["dotnet", "build"], ".NET project or solution detected"))
    if (root / "Cargo.toml").exists():
        commands.append(ValidationCommand("cargo check", ["cargo", "check"], "Cargo.toml detected"))
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        commands.append(ValidationCommand("python -m pytest", ["python", "-m", "pytest"], "Python project detected"))
    if (root / "CMakeLists.txt").exists():
        commands.append(ValidationCommand("cmake build", ["cmake", "--build", "build"], "CMakeLists.txt detected"))
    return commands


def _package_scripts(root: Path) -> dict[str, str]:
    package_json = root / "package.json"
    if not package_json.exists():
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
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
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


def validation_summary(workspace: str | Path) -> dict[str, Any]:
    commands = detect_validation_commands(workspace)
    return {"workspace": str(Path(workspace).resolve()), "commands": [command.__dict__ for command in commands]}


def run_validation(workspace: str | Path, command: list[str] | None = None, timeout: int = 120) -> dict[str, Any]:
    root = Path(workspace).resolve()
    selected = command or (detect_validation_commands(root)[0].command if detect_validation_commands(root) else None)
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
        append_validation_log(root, result)
        return result

    try:
        completed = subprocess.run(
            selected,
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
        append_validation_log(root, result)
        return result
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "command": selected,
            "returncode": None,
            "stdout": _decode_output(exc.stdout)[-12000:],
            "stderr": f"Validation timed out after {timeout} seconds.\n{_decode_output(exc.stderr)[-12000:]}".strip(),
            "timed_out": True,
        }
        append_validation_log(root, result)
        return result
    result = {
        "ok": completed.returncode == 0,
        "command": selected,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
    }
    append_validation_log(root, result)
    return result


def is_safe_validation_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(str(command[0])).name.lower()
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


def _decode_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def append_validation_log(workspace: str | Path, result: dict[str, Any]) -> None:
    memory = ProjectMemory(workspace)
    memory.ensure()
    command = " ".join(result.get("command") or [])
    status = "passed" if result.get("ok") else "failed"
    output = (result.get("stderr") or result.get("stdout") or "").strip()
    entry = f"## {utc_now()} - {status}\n\nCommand: `{command}`\n\n```text\n{output[:4000]}\n```\n\n"
    with (memory.root / "validation-log.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)
