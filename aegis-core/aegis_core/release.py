from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .memory import ProjectMemory, utc_now


RELEASE_SCHEMA_VERSION = "2026.05.12"
CORE_VERSION = "0.1.0"
MANIFEST_FILE = "VERSION.json"


CLIENT_ALIASES = {
    "core": "aegis-core",
    "aegis-core": "aegis-core",
    "website": "website",
    "website-backend": "website",
    "website-frontend": "website",
    "web": "website",
    "desktop": "desktop",
    "desktop-app": "desktop",
    "native-desktop": "desktop",
    "vscode": "vscode-extension",
    "vscode-extension": "vscode-extension",
    "vs-code": "vscode-extension",
    "visual-studio": "visual-studio-extension",
    "visual-studio-extension": "visual-studio-extension",
    "vs": "visual-studio-extension",
}


MIGRATIONS: list[dict[str, str]] = [
    {
        "id": "release_state_2026_05_12",
        "description": "Create .aegis/release-state.json for version/update/recovery state.",
        "category": "aegis-state",
    },
    {
        "id": "config_schema_2026_05_12",
        "description": "Ensure .aegis/config.json carries the current release schema version.",
        "category": "config",
    },
    {
        "id": "model_registry_state_2026_05_12",
        "description": "Create .aegis/model-registry-state.json as the model registry migration anchor.",
        "category": "model-registry",
    },
    {
        "id": "database_migration_marker_2026_05_12",
        "description": "Record database migration expectations for Website-managed SQLite stores.",
        "category": "database",
    },
]


def release_manifest(workspace: str | Path | None = None) -> dict[str, Any]:
    manifest = _load_manifest()
    manifest.setdefault("manifest_version", 1)
    manifest.setdefault("schema_version", RELEASE_SCHEMA_VERSION)
    manifest.setdefault("release_channel", "local")
    manifest["generated_at"] = manifest.get("generated_at") or utc_now()
    manifest.setdefault("components", {})
    manifest.setdefault("compatibility", {})
    manifest.setdefault("update_policy", {})

    for component_id, component in manifest["components"].items():
        package = component.setdefault("package", {})
        artifact = package.get("artifact") or _default_artifact_name(component_id, component)
        if artifact:
            package.setdefault("artifact", artifact)
        path = package.get("path") or f"release/{artifact}"
        package["path"] = path
        artifact_path = _repo_root() / path
        if not artifact_path.is_file():
            artifact_path = _fallback_artifact_path(component_id, artifact)
        if artifact_path and artifact_path.is_file():
            package["sha256"] = _sha256(artifact_path)
            package["size_bytes"] = artifact_path.stat().st_size
            package["local_path"] = str(artifact_path)
        else:
            package.setdefault("sha256", "")
            package.setdefault("size_bytes", 0)

    if workspace:
        manifest["workspace"] = str(Path(workspace).resolve())
    return manifest


def check_compatibility(
    client_type: str,
    client_version: str = "",
    *,
    schema_version: str = "",
    core_version: str = "",
    capabilities: list[str] | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    manifest = release_manifest(workspace)
    client = normalize_client_type(client_type)
    compatibility = manifest.get("compatibility", {})
    minimum_clients = compatibility.get("minimum_clients", {})
    components = manifest.get("components", {})
    component = components.get(client, {})

    required_core = component.get("minimum_compatible_core") or compatibility.get("minimum_core_version") or CORE_VERSION
    required_schema = component.get("minimum_compatible_schema") or compatibility.get("core_contract_version") or RELEASE_SCHEMA_VERSION
    required_client = minimum_clients.get(client) or component.get("version", "")
    effective_core = core_version or compatibility.get("minimum_core_version") or CORE_VERSION

    blockers: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if client not in components and client != "aegis-core":
        blockers.append(f"Unknown client type '{client_type}'.")
        recommendations.append("Use one of: website, desktop, vscode-extension, visual-studio-extension.")

    if required_client and client_version:
        if _compare_versions(client_version, required_client) < 0:
            blockers.append(f"{client} {client_version} is older than the minimum compatible version {required_client}.")
    elif required_client:
        warnings.append(f"{client} did not report a client version; minimum compatible version is {required_client}.")

    if required_core and effective_core and _compare_versions(effective_core, required_core) < 0:
        blockers.append(f"Aegis Core {effective_core} is older than required Core version {required_core}.")

    if schema_version:
        if _compare_versions(schema_version, required_schema) < 0:
            blockers.append(f"Schema {schema_version} is older than required schema {required_schema}.")
        elif schema_version != required_schema:
            warnings.append(f"Client schema {schema_version} differs from release schema {required_schema}.")
    else:
        warnings.append(f"Client did not report a schema version; expected {required_schema}.")

    requested_capabilities = set(capabilities or [])
    if client in {"desktop", "vscode-extension", "visual-studio-extension", "website"} and "release-compatibility" not in requested_capabilities:
        recommendations.append("Advertise the release-compatibility capability after wiring update checks in the client.")

    status = "blocked" if blockers else ("warning" if warnings else "compatible")
    if status == "compatible":
        recommendations.append("No release compatibility action is required.")
    elif status == "warning":
        recommendations.append("Continue in compatibility mode and schedule a client manifest/schema refresh.")
    else:
        recommendations.append("Block update/apply operations until the incompatible component is upgraded.")

    return {
        "compatible": not blockers,
        "client_type": client,
        "client_version": client_version,
        "core_version": effective_core,
        "schema_version": schema_version,
        "required_core_version": required_core,
        "required_schema_version": required_schema,
        "minimum_client_version": required_client,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations,
        "release_channel": manifest.get("release_channel", "local"),
        "checked_at": utc_now(),
    }


def migration_status(workspace: str | Path) -> dict[str, Any]:
    memory = ProjectMemory(workspace)
    state_path = memory.root / "release-migrations.json"
    state = _read_json(state_path, {"schema_version": RELEASE_SCHEMA_VERSION, "applied": []})
    applied = state.get("applied", []) if isinstance(state, dict) else []
    applied_ids = {item.get("id") for item in applied if isinstance(item, dict)}
    pending = [migration for migration in MIGRATIONS if migration["id"] not in applied_ids]
    return {
        "workspace": str(Path(workspace).resolve()),
        "schema_version": RELEASE_SCHEMA_VERSION,
        "dry_run": False,
        "applied": applied,
        "pending": pending,
        "state_path": str(state_path),
    }


def run_migrations(workspace: str | Path, dry_run: bool = False) -> dict[str, Any]:
    memory = ProjectMemory(workspace)
    status = migration_status(workspace)
    applied = list(status.get("applied", []))
    pending = list(status.get("pending", []))
    newly_applied: list[dict[str, Any]] = []

    if not dry_run:
        memory.ensure()

    for migration in pending:
        outputs: dict[str, Any] = {}
        if not dry_run:
            outputs = _apply_migration(memory, migration["id"])
        newly_applied.append(
            {
                **migration,
                "applied_at": utc_now() if not dry_run else "",
                "dry_run": dry_run,
                "outputs": outputs,
            }
        )

    if not dry_run and newly_applied:
        record = {
            "schema_version": RELEASE_SCHEMA_VERSION,
            "updated_at": utc_now(),
            "applied": applied + newly_applied,
        }
        memory.write_json("release-migrations.json", record)

    return {
        "workspace": str(Path(workspace).resolve()),
        "schema_version": RELEASE_SCHEMA_VERSION,
        "dry_run": dry_run,
        "applied": applied if dry_run else applied + newly_applied,
        "pending": newly_applied if dry_run else [],
        "state_path": str(memory.root / "release-migrations.json"),
    }


def update_plan(
    component_id: str,
    *,
    current_version: str = "",
    target_version: str = "",
    package_uri: str = "",
    sha256: str = "",
) -> dict[str, Any]:
    manifest = release_manifest()
    component_key = normalize_client_type(component_id)
    component = manifest.get("components", {}).get(component_key)
    blockers: list[str] = []
    if component is None:
        blockers.append(f"Unknown component '{component_id}'.")
        component = {}

    package = component.get("package", {}) if isinstance(component, dict) else {}
    target = target_version or component.get("version", "")
    current = current_version or component.get("version", "")
    uri = package_uri or package.get("local_path") or package.get("path") or package.get("artifact", "")
    checksum = sha256 or package.get("sha256", "")

    if not target:
        blockers.append("Target version is required.")
    if current and target and _compare_versions(target, current) < 0:
        blockers.append(f"Downgrade protection blocked {component_key} {current} -> {target}.")
    if manifest.get("update_policy", {}).get("requires_checksum", True) and not checksum:
        blockers.append("Package checksum is required before apply.")
    if checksum and not _is_sha256(checksum):
        blockers.append("Package checksum must be a 64-character SHA256 hex digest.")
    blockers.extend(_manifest_validation_errors(manifest, component_key, component, package, uri))

    steps = [
        _step("inspect_manifest", "Load VERSION.json and confirm component compatibility.", "ready"),
        _step("download_package", "Download or copy the release package into .aegis/updates/downloads.", "ready" if uri else "blocked"),
        _step("verify_package", "Verify SHA256 and optional signature metadata before extracting.", "ready" if checksum else "blocked"),
        _step("backup_current_install", "Copy the current component install into .aegis/updates/backups.", "ready"),
        _step("mark_pending", "Write .aegis/update-state.json with the pending update and backup path.", "ready"),
        _step("apply_package", "Extract/copy package contents into the component install path.", "requires-approval"),
        _step("run_migrations", "Run release migrations for .aegis, config, database markers, and model registry state.", "ready"),
        _step("smoke_check", "Run component health/smoke checks after apply.", "ready"),
        _step("mark_success", "Record successful update and clear failed-update recovery flags.", "ready"),
    ]

    status = "blocked" if blockers else "ready"
    return {
        "component_id": component_key,
        "current_version": current,
        "target_version": target,
        "status": status,
        "package_uri": uri,
        "sha256": checksum,
        "blockers": blockers,
        "steps": steps,
        "rollback": {
            "available": True,
            "strategy": "Restore the backup directory recorded in .aegis/update-state.json, rerun migrations in safe mode, and mark the failed update as rolled back.",
            "steps": [
                "detect failed or cancelled update from .aegis/update-state.json",
                "restore the component backup from .aegis/updates/backups",
                "collect update logs into .aegis/update-state.json",
                "start in safe mode if smoke validation still fails",
            ],
        },
        "trust": {
            "manifest_validation": True,
            "checksum_required": bool(manifest.get("update_policy", {}).get("requires_checksum", True)),
            "signature_required": not bool(manifest.get("update_policy", {}).get("signature_optional_for_local_builds", True)),
            "downgrade_protection": True,
            "tamper_detection": "manifest package artifact/path and SHA256 are validated before apply",
        },
    }


def _manifest_validation_errors(
    manifest: dict[str, Any],
    component_key: str,
    component: dict[str, Any],
    package: dict[str, Any],
    uri: str,
) -> list[str]:
    errors: list[str] = []
    if int(manifest.get("manifest_version") or 0) < 1:
        errors.append("Release manifest is missing a valid manifest_version.")
    if not str(manifest.get("schema_version") or "").strip():
        errors.append("Release manifest is missing schema_version.")
    if component_key and component:
        artifact = str(package.get("artifact") or "").strip()
        package_path = str(package.get("path") or "").strip()
        if not artifact:
            errors.append(f"{component_key} package artifact is required.")
        if not uri:
            errors.append(f"{component_key} package path or URI is required.")
        if artifact and package_path and not package_path.replace("\\", "/").endswith(artifact):
            errors.append(f"{component_key} package path does not match the declared artifact name.")
    return errors


def _is_sha256(value: str) -> bool:
    text = str(value or "").strip()
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def normalize_client_type(client_type: str) -> str:
    normalized = (client_type or "").strip().lower().replace("_", "-")
    return CLIENT_ALIASES.get(normalized, normalized)


def _apply_migration(memory: ProjectMemory, migration_id: str) -> dict[str, Any]:
    manifest = release_manifest(memory.workspace)
    if migration_id == "release_state_2026_05_12":
        path = memory.write_json(
            "release-state.json",
            {
                "schema_version": RELEASE_SCHEMA_VERSION,
                "updated_at": utc_now(),
                "components": {
                    key: {"version": value.get("version", ""), "type": value.get("type", "")}
                    for key, value in manifest.get("components", {}).items()
                    if isinstance(value, dict)
                },
                "update": {
                    "state": "idle",
                    "pending_component": "",
                    "failed_update_detected": False,
                    "last_error": "",
                    "last_successful_update": "",
                    "rollback_available": False,
                },
                "safe_mode": {"enabled": False, "reason": ""},
            },
        )
        return {"path": str(path)}

    if migration_id == "config_schema_2026_05_12":
        path = memory.root / "config.json"
        config = _read_json(path, {})
        if not isinstance(config, dict):
            config = {}
        config.setdefault("schema_version", RELEASE_SCHEMA_VERSION)
        config.setdefault("release_channel", manifest.get("release_channel", "local"))
        written = memory.write_json("config.json", config)
        return {"path": str(written)}

    if migration_id == "model_registry_state_2026_05_12":
        path = memory.write_json(
            "model-registry-state.json",
            {
                "schema_version": RELEASE_SCHEMA_VERSION,
                "updated_at": utc_now(),
                "source": "/v1/models/registry",
                "migration_anchor": migration_id,
                "notes": "Core owns model/provider registry and routing compatibility for all clients.",
            },
        )
        return {"path": str(path)}

    if migration_id == "database_migration_marker_2026_05_12":
        path = memory.write_json(
            "database-migrations.json",
            {
                "schema_version": RELEASE_SCHEMA_VERSION,
                "updated_at": utc_now(),
                "website_backend": {
                    "owner": "website/backend/aegis_ai/storage_schema.py",
                    "status": "external-managed",
                    "note": "Website SQLite schema migrations still run through the Website backend initializer; Core records compatibility state here.",
                },
            },
        )
        return {"path": str(path)}

    raise ValueError(f"Unknown migration id: {migration_id}")


def _load_manifest() -> dict[str, Any]:
    path = _repo_root() / MANIFEST_FILE
    if not path.is_file():
        return _default_manifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_manifest()
    if not isinstance(data, dict):
        return _default_manifest()
    default = _default_manifest()
    merged = copy.deepcopy(default)
    merged.update(data)
    if isinstance(data.get("components"), dict):
        merged["components"] = data["components"]
    if isinstance(data.get("compatibility"), dict):
        merged["compatibility"] = data["compatibility"]
    if isinstance(data.get("update_policy"), dict):
        merged["update_policy"] = data["update_policy"]
    return merged


def _default_manifest() -> dict[str, Any]:
    return {
        "manifest_version": 1,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_channel": "local",
        "generated_at": "",
        "components": {
            "aegis-core": {"name": "Aegis Core", "type": "python-service", "version": CORE_VERSION},
        },
        "compatibility": {
            "core_api_version": "v1",
            "core_contract_version": RELEASE_SCHEMA_VERSION,
            "minimum_core_version": CORE_VERSION,
            "minimum_clients": {},
        },
        "update_policy": {
            "requires_checksum": True,
            "signature_optional_for_local_builds": True,
            "backup_before_apply": True,
            "rollback_on_failure": True,
            "safe_mode_supported": True,
        },
    }


def _default_artifact_name(component_id: str, component: dict[str, Any]) -> str:
    version = component.get("version", "0.0.0")
    if component_id == "desktop":
        return f"aegis-desktop-{version}-portable.zip"
    if component_id == "website":
        return f"aegis-website-{version}.zip"
    if component_id == "aegis-core":
        return f"aegis-core-{version}.zip"
    if component_id == "vscode-extension":
        return f"aegis-local-autopilot-{version}.vsix"
    if component_id == "visual-studio-extension":
        return "AegisLocalAgentVs.vsix"
    return f"{component_id}-{version}.zip"


def _fallback_artifact_path(component_id: str, artifact: str) -> Path | None:
    root = _repo_root()
    candidates = {
        "vscode-extension": root / "vscode-plugins" / "aegis-local-autopilot" / "release" / artifact,
        "visual-studio-extension": root / "visual-studio-extensions" / "aegis-local-agent-vs" / "release" / artifact,
    }
    return candidates.get(component_id)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.is_file():
            return copy.deepcopy(default)
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    size = max(len(left_parts), len(right_parts), 1)
    left_parts.extend([0] * (size - len(left_parts)))
    right_parts.extend([0] * (size - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _version_parts(value: str) -> list[int]:
    parts: list[int] = []
    current = ""
    for char in str(value):
        if char.isdigit():
            current += char
        elif current:
            parts.append(int(current))
            current = ""
    if current:
        parts.append(int(current))
    return parts or [0]


def _step(step_id: str, description: str, status: str) -> dict[str, str]:
    return {"id": step_id, "description": description, "status": status}
