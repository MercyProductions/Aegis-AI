from __future__ import annotations

import subprocess
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
    if (root / "package.json").exists():
        commands.extend([
            ValidationCommand("npm test", ["npm", "test"], "package.json detected"),
            ValidationCommand("npm run build", ["npm", "run", "build"], "package.json detected"),
        ])
    if (root / "pnpm-lock.yaml").exists():
        commands.extend([
            ValidationCommand("pnpm test", ["pnpm", "test"], "pnpm lockfile detected"),
            ValidationCommand("pnpm build", ["pnpm", "build"], "pnpm lockfile detected"),
        ])
    if (root / "yarn.lock").exists():
        commands.extend([
            ValidationCommand("yarn test", ["yarn", "test"], "yarn lockfile detected"),
            ValidationCommand("yarn build", ["yarn", "build"], "yarn lockfile detected"),
        ])
    if any(root.glob("*.sln")) or any(root.glob("*.slnx")) or any(root.rglob("*.csproj")):
        commands.append(ValidationCommand("dotnet build", ["dotnet", "build"], ".NET project or solution detected"))
    if (root / "Cargo.toml").exists():
        commands.append(ValidationCommand("cargo check", ["cargo", "check"], "Cargo.toml detected"))
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        commands.append(ValidationCommand("python -m pytest", ["python", "-m", "pytest"], "Python project detected"))
    if (root / "CMakeLists.txt").exists():
        commands.append(ValidationCommand("cmake build", ["cmake", "--build", "build"], "CMakeLists.txt detected"))
    return commands


def validation_summary(workspace: str | Path) -> dict[str, Any]:
    commands = detect_validation_commands(workspace)
    return {"workspace": str(Path(workspace).resolve()), "commands": [command.__dict__ for command in commands]}


def run_validation(workspace: str | Path, command: list[str] | None = None, timeout: int = 120) -> dict[str, Any]:
    root = Path(workspace).resolve()
    selected = command or (detect_validation_commands(root)[0].command if detect_validation_commands(root) else None)
    if not selected:
        return {"ok": False, "command": None, "stdout": "", "stderr": "No validation command detected."}

    completed = subprocess.run(
        selected,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    result = {
        "ok": completed.returncode == 0,
        "command": selected,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
    }
    append_validation_log(root, result)
    return result


def append_validation_log(workspace: str | Path, result: dict[str, Any]) -> None:
    memory = ProjectMemory(workspace)
    memory.ensure()
    command = " ".join(result.get("command") or [])
    status = "passed" if result.get("ok") else "failed"
    output = (result.get("stderr") or result.get("stdout") or "").strip()
    entry = f"## {utc_now()} - {status}\n\nCommand: `{command}`\n\n```text\n{output[:4000]}\n```\n\n"
    with (memory.root / "validation-log.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)
