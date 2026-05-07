from __future__ import annotations

import re

from .schemas import CommandRun


def split_safe_command_chain(command: str) -> list[str]:
    stripped = command.strip()
    if not stripped:
        return []

    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(stripped):
        char = stripped[index]
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue

        if char in ("'", '"'):
            quote = char
            current.append(char)
            index += 1
            continue

        if char == "&":
            if index + 1 < len(stripped) and stripped[index + 1] == "&":
                segment = "".join(current).strip()
                if not segment:
                    return [stripped]
                segments.append(segment)
                current = []
                index += 2
                continue
            return [stripped]

        if char in "|;<>":
            return [stripped]

        current.append(char)
        index += 1

    if quote is not None:
        return [stripped]

    segment = "".join(current).strip()
    if not segment:
        return [stripped]
    segments.append(segment)

    if len(segments) <= 1:
        return [stripped]
    return segments


def validation_step_phase(command: str) -> str:
    lowered = command.lower()
    spaced = f" {lowered} "
    if "cmake" in lowered and " -s " in spaced:
        return "configure"
    if ("cmake" in lowered and "--build" in lowered) or "msbuild" in lowered or "dotnet build" in lowered:
        return "build"
    if any(token in lowered for token in ("npm run build", "pnpm build", "yarn build", "vite build", "cargo check")):
        return "build"
    if any(
        token in lowered
        for token in ("npm test", "pnpm test", "yarn test", "pytest", "vitest", "jest", "ctest", "cargo test", "go test")
    ):
        return "test"
    if any(token in lowered for token in ("typecheck", "type-check", "tsc --noemit", "mypy", "pyright")):
        return "typecheck"
    if any(token in lowered for token in ("prisma", "sqlfluff", "migration", "schema")):
        return "database"
    if any(token in lowered for token in ("lint", "ruff", "eslint", "clippy")):
        return "lint"
    return "validation"


def validation_step_label(command: str, *, index: int, total: int) -> str:
    lowered = command.lower()
    if " -s " in f" {lowered} " and " -b " in f" {lowered} " and "cmake" in lowered:
        return "Configure CMake build directory"
    if "cmake --build" in lowered:
        return "Build CMake project"
    if lowered.startswith("ctest "):
        return "Run CTest suite"
    if "npm run build" in lowered or "pnpm build" in lowered or "yarn build" in lowered:
        return "Build web project"
    if "npm test" in lowered or "pnpm test" in lowered or "pytest" in lowered:
        return "Run test suite"
    if total > 1:
        return f"Validation step {index}"
    return "Run validation command"


def failed_chain_step(validation: CommandRun) -> str:
    if validation.failed_step:
        return validation.failed_step
    match = re.search(r"step\s+(\d+)", validation.reason or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""
