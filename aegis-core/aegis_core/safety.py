from __future__ import annotations

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


def is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def is_secret_like(path: Path) -> bool:
    name = path.name.lower()
    if name in BLOCKED_NAMES:
        return True
    if any(name.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        return True
    return any(marker in name for marker in ("secret", "credential", "private-key", "apikey", "api_key"))


def is_safe_to_read(path: Path) -> bool:
    return not is_ignored_path(path) and not is_secret_like(path)


def is_safe_to_edit(path: Path) -> bool:
    return is_safe_to_read(path)
