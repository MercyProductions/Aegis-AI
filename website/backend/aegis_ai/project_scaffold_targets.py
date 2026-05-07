from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .schemas import ProjectScaffoldPreset, ProjectScaffoldRequest


def visible_entries(target: Path) -> list[Path]:
    try:
        return [entry for entry in target.iterdir() if entry.name != ".aegis"]
    except OSError:
        return []


def conflicting_paths(target: Path, files: dict[str, str]) -> list[str]:
    return sorted(relative_path for relative_path in files if (target / relative_path).exists())


def has_non_metadata_entries(target: Path, *, safe_metadata_paths: set[str]) -> bool:
    try:
        for entry in target.iterdir():
            relative = entry.name.replace("\\", "/")
            if entry.is_dir() and relative == ".aegis":
                continue
            if relative not in safe_metadata_paths:
                return True
    except OSError:
        return False
    return False


def next_available_child_target(target: Path, project_name: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-project"
    primary = target / safe_name
    if (primary / ".aegis" / "project.json").exists():
        return primary
    candidates = [primary]
    candidates.extend(target / f"{safe_name}-{index}" for index in range(2, 100))
    for candidate in candidates:
        if not candidate.exists():
            return candidate
    return target / f"{safe_name}-{uuid.uuid4().hex[:8]}"


def is_same_scaffold_project(target: Path, preset_id: str, project_name: str) -> bool:
    manifest_path = target / ".aegis" / "project.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(manifest.get("preset_id", "")) == preset_id and str(manifest.get("project_name", "")) == project_name


def is_metadata_only_refresh(target: Path, conflicting_paths: list[str], *, safe_metadata_paths: set[str]) -> bool:
    if not conflicting_paths:
        return False
    if not (target / ".aegis" / "project.json").exists():
        return False
    normalized = {path.replace("\\", "/") for path in conflicting_paths}
    return normalized.issubset(safe_metadata_paths)


def title_from_name(project_name: str) -> str:
    words = [part for part in re.split(r"[-_]+", project_name) if part]
    return " ".join(word[:1].upper() + word[1:] for word in words) or "Aegis App"


def command_for_project(command: str, project_name: str) -> str:
    return command.replace("{project_name}", project_name).replace("{project_title}", title_from_name(project_name))


def should_install_before_validation(
    preset: ProjectScaffoldPreset,
    target: Path,
    *,
    install_command: str,
    validation_command: str,
    request: ProjectScaffoldRequest,
) -> bool:
    if request.run_install or not request.run_validation or not install_command or not validation_command:
        return False
    package_manager = preset.package_manager.lower()
    normalized_install = " ".join(install_command.lower().split())
    explicit_install_override = bool(request.install_command.strip())
    if "npm" in package_manager:
        return (
            (explicit_install_override or "npm install" in normalized_install)
            and (target / "package.json").exists()
            and not (target / "node_modules").exists()
        )
    if any(token in package_manager for token in ("pip", "python")):
        has_python_manifest = (target / "pyproject.toml").exists() or (target / "requirements.txt").exists()
        return (explicit_install_override or "pip install" in normalized_install) and has_python_manifest and not (target / ".venv").exists()
    if "dotnet" in package_manager:
        has_dotnet_manifest = (target / f"{preset.id}.sln").exists() or any(target.rglob("*.csproj"))
        has_restore_assets = any(target.rglob("project.assets.json"))
        return (explicit_install_override or "dotnet restore" in normalized_install) and has_dotnet_manifest and not has_restore_assets
    if package_manager == "go":
        return (explicit_install_override or "go mod tidy" in normalized_install) and (target / "go.mod").exists() and not (target / "go.sum").exists()
    if package_manager == "cargo":
        return (explicit_install_override or "cargo fetch" in normalized_install) and (target / "Cargo.toml").exists() and not (target / "Cargo.lock").exists()
    return False
