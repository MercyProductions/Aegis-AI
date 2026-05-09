from __future__ import annotations

import re
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".aegis",
    ".vs",
    ".vscode",
    ".idea",
    ".pytest_cache",
    ".tmp",
    ".venv",
    "venv",
    "py-probe-dir",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "bin",
    "obj",
    "packages",
    "Library",
    "Temp",
    "Logs",
    "Generated",
    "x64",
    "Debug",
    "Release",
    "release",
    "smoke-artifacts",
    "stress-artifacts",
    "__pycache__",
}

BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

BLOCKED_SUFFIXES = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".keystore",
}

IGNORED_DIRS_NORMALIZED = {name.lower() for name in IGNORED_DIRS}
BLOCKED_NAMES_NORMALIZED = {name.lower() for name in BLOCKED_NAMES}
SECRET_NAME_PATTERN = re.compile(
    r"(^|[._\-\s])"
    r"(secret|secrets|credential|credentials|password|passwd|token|tokens|private|private-key|apikey|api-key|api_key|auth)"
    r"([._\-\s]|$)",
    re.IGNORECASE,
)


def path_parts_for_safety(path: Path, workspace: str | Path | None = None) -> tuple[str, ...]:
    if workspace is None:
        return path.parts
    try:
        return path.resolve().relative_to(Path(workspace).resolve()).parts
    except ValueError:
        return path.parts


def is_ignored_path(path: Path, workspace: str | Path | None = None) -> bool:
    return any(part.lower() in IGNORED_DIRS_NORMALIZED for part in path_parts_for_safety(path, workspace))


def is_secret_like(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in BLOCKED_NAMES_NORMALIZED:
        return True
    if any(name.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        return True
    return bool(SECRET_NAME_PATTERN.search(name))


def is_safe_to_read(path: Path, workspace: str | Path | None = None) -> bool:
    return not is_ignored_path(path, workspace) and not is_secret_like(path)


def is_safe_to_edit(path: Path, workspace: str | Path | None = None) -> bool:
    return is_safe_to_read(path, workspace)
