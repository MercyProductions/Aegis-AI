from __future__ import annotations

from collections.abc import Sequence


POWERSHELL_BUILD_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"
PWSH_BUILD_COMMAND = "pwsh -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"

POWERSHELL_BUILD_COMMAND_MARKERS = (
    POWERSHELL_BUILD_COMMAND.lower(),
    "powershell -noprofile -executionpolicy bypass -file .\\build.ps1",
    PWSH_BUILD_COMMAND.lower(),
    "pwsh -noprofile -executionpolicy bypass -file .\\build.ps1",
)


def is_root_powershell_build_command(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    if not normalized.startswith(("powershell ", "pwsh ")):
        return False
    return any(
        marker in f" {normalized} "
        for marker in (" -file ./build.ps1 ", " -file .\\build.ps1 ", " -file build.ps1 ")
    )


def is_safe_powershell_build_guard_argv(argv: Sequence[str]) -> bool:
    if len(argv) != 6:
        return False
    args = [str(item).strip("\"'").lower() for item in argv[1:]]
    script = args[4].replace("\\", "/").rstrip("/")
    return args[:4] == ["-noprofile", "-executionpolicy", "bypass", "-file"] and script in {
        "./build.ps1",
        "build.ps1",
    }
