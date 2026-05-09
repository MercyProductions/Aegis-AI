from __future__ import annotations

import shlex
from collections.abc import Sequence


POWERSHELL_BUILD_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"
PWSH_BUILD_COMMAND = "pwsh -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"

POWERSHELL_BUILD_COMMAND_MARKERS = (
    POWERSHELL_BUILD_COMMAND.lower(),
    "powershell -noprofile -executionpolicy bypass -file .\\build.ps1",
    "powershell -noprofile -executionpolicy bypass -file build.ps1",
    "powershell.exe -noprofile -executionpolicy bypass -file ./build.ps1",
    "powershell.exe -noprofile -executionpolicy bypass -file .\\build.ps1",
    "powershell.exe -noprofile -executionpolicy bypass -file build.ps1",
    PWSH_BUILD_COMMAND.lower(),
    "pwsh -noprofile -executionpolicy bypass -file .\\build.ps1",
    "pwsh -noprofile -executionpolicy bypass -file build.ps1",
    "pwsh.exe -noprofile -executionpolicy bypass -file ./build.ps1",
    "pwsh.exe -noprofile -executionpolicy bypass -file .\\build.ps1",
    "pwsh.exe -noprofile -executionpolicy bypass -file build.ps1",
)

POWERSHELL_LAUNCHER_PREFIXES = ("powershell ", "powershell.exe ", "pwsh ", "pwsh.exe ")

BLOCKED_REMEMBERED_VALIDATION_PREFIXES = (
    "npm install",
    "npm i ",
    "pnpm install",
    "yarn install",
    "bun install",
    "pip install",
    "python -m pip install",
    "uv add",
    "poetry add",
    "cargo install",
    "winget ",
    "choco ",
    "scoop ",
    "curl ",
    "wget ",
    "irm ",
    "iex ",
    "powershell ",
    "powershell.exe ",
    "pwsh ",
    "pwsh.exe ",
    "cmd /c ",
    "reg ",
    "regedit",
    "del ",
    "erase ",
    "rm ",
    "rmdir ",
    "remove-item",
    "format ",
    "shutdown",
    "taskkill",
    "git clean",
    "git reset",
    "git checkout",
    "git push",
    "npm publish",
    "docker ",
)


def is_root_powershell_build_command(command: str) -> bool:
    return is_safe_powershell_build_guard_command(command)


def is_safe_powershell_build_guard_command(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    return normalized in POWERSHELL_BUILD_COMMAND_MARKERS


def is_safe_powershell_build_guard_argv(argv: Sequence[str]) -> bool:
    if len(argv) != 6:
        return False
    args = [str(item).strip("\"'").lower() for item in argv[1:]]
    script = args[4].replace("\\", "/").rstrip("/")
    return args[:4] == ["-noprofile", "-executionpolicy", "bypass", "-file"] and script in {
        "./build.ps1",
        "build.ps1",
    }


def is_blocked_validation_launcher_command(command: str) -> bool:
    tokens = _validation_command_tokens(command)
    if not tokens:
        return False

    executable = tokens[0].strip("\"'").lower()
    executable = executable.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    for suffix in (".exe", ".cmd", ".bat"):
        if executable.endswith(suffix):
            executable = executable[: -len(suffix)]
            break

    args = [token.strip("\"'").lower() for token in tokens[1:]]
    if executable in {
        "winget",
        "choco",
        "scoop",
        "curl",
        "wget",
        "irm",
        "iex",
        "reg",
        "regedit",
        "del",
        "erase",
        "rm",
        "rmdir",
        "remove-item",
        "format",
        "shutdown",
        "taskkill",
        "docker",
    }:
        return True
    if executable == "cmd" and args[:1] == ["/c"]:
        return True
    if executable == "npm" and args and args[0] in {"install", "i", "publish"}:
        return True
    if executable in {"pnpm", "yarn", "bun"} and args[:1] == ["install"]:
        return True
    if executable == "pip" and args[:1] == ["install"]:
        return True
    if executable == "python" and args[:3] == ["-m", "pip", "install"]:
        return True
    if executable == "uv" and args[:1] == ["add"]:
        return True
    if executable == "poetry" and args[:1] == ["add"]:
        return True
    if executable == "cargo" and args[:1] == ["install"]:
        return True
    if executable == "git" and args and args[0] in {"clean", "reset", "checkout", "push"}:
        return True
    return False


def _validation_command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return command.split()


def is_safe_remembered_validation_command(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    if not normalized or len(command) > 500:
        return False
    if any(char in command for char in ("\n", "\r", "|", ";", "<", ">")):
        return False

    index = 0
    while index < len(command):
        if command[index] == "&":
            if index + 1 < len(command) and command[index + 1] == "&":
                index += 2
                continue
            return False
        index += 1

    if normalized.startswith(POWERSHELL_LAUNCHER_PREFIXES):
        return is_safe_powershell_build_guard_command(command)

    if is_blocked_validation_launcher_command(command):
        return False

    return not any(
        normalized == prefix.strip() or normalized.startswith(prefix)
        for prefix in BLOCKED_REMEMBERED_VALIDATION_PREFIXES
    )
