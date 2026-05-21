from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import memory_dir
from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .validation import detect_validation_commands
from .workspace import WorkspaceScanner


PLUGIN_API_VERSION = "2026.05.12"
CORE_RUNTIME_VERSION = "0.1.0"
PLUGIN_STATE_FILE = "plugin-state.json"
PLUGIN_OBSERVABILITY_FILE = "plugin-observability.jsonl"
PLUGIN_MANIFEST_NAMES = ("aegis-plugin.json", "plugin.json", "manifest.json")

PLUGIN_CATEGORIES = (
    "model_providers",
    "workflow_types",
    "analyzers",
    "validators",
    "repair_strategies",
    "project_templates",
    "media_generators",
    "ide_integrations",
    "deployment_tools",
    "observability_tools",
)

PERMISSION_SCOPES = {
    "filesystem_read": {"risk": "low", "description": "Read normalized files inside approved workspace roots."},
    "filesystem_write": {"risk": "high", "description": "Request file changes through Core editing contracts."},
    "network_access": {"risk": "high", "description": "Reach local or remote network services."},
    "model_access": {"risk": "medium", "description": "Use model/provider routing contracts."},
    "workspace_scan": {"risk": "low", "description": "Read workspace index and intelligence summaries."},
    "process_execution": {"risk": "high", "description": "Run external processes through explicit validation/execution gates."},
    "validation_execution": {"risk": "high", "description": "Run validation commands through Core validation contracts."},
    "ui_extension": {"risk": "low", "description": "Contribute panels, dashboard widgets, and visualization descriptors."},
    "observability_read": {"risk": "low", "description": "Read runtime metrics and plugin observability summaries."},
    "provider_credentials": {"risk": "high", "description": "Request provider credential status through OS credential-store contracts."},
}

HIGH_RISK_SCOPES = {scope for scope, meta in PERMISSION_SCOPES.items() if meta["risk"] == "high"}

CAPABILITY_PERMISSION_HINTS: dict[str, set[str]] = {
    "tool": {"workspace_scan"},
    "model_provider": {"model_access"},
    "workflow_extension": {"workspace_scan"},
    "analyzer": {"filesystem_read", "workspace_scan"},
    "validator": {"filesystem_read", "validation_execution"},
    "repair_strategy": {"filesystem_read", "filesystem_write", "validation_execution"},
    "project_template": {"filesystem_read", "filesystem_write"},
    "media_generator": {"model_access", "filesystem_write"},
    "ide_integration": {"ui_extension"},
    "deployment_tool": {"filesystem_read", "process_execution", "network_access"},
    "observability_widget": {"observability_read", "ui_extension"},
}

BUILTIN_TOOL_HANDLERS = {
    "builtin.echo",
    "builtin.validation_hint",
    "builtin.architecture_summary",
    "builtin.roadmap_hint",
    "builtin.provider_status",
    "builtin.observability_snapshot",
}


class PluginRuntimeError(RuntimeError):
    """Raised when plugin metadata or execution contracts are rejected."""


def plugin_dashboard(workspace: str | Path, *, include_disabled: bool = True, refresh: bool = True) -> dict[str, Any]:
    root = _require_workspace(workspace)
    discovered = discover_plugins(root, refresh=refresh)
    state = _read_state(root)
    plugins: list[dict[str, Any]] = []
    load_failures: list[dict[str, Any]] = []
    compatibility_warnings: list[dict[str, Any]] = []

    manifest_by_id = {item["manifest"]["id"]: item["manifest"] for item in discovered["manifests"]}
    for item in discovered["manifests"]:
        manifest = _apply_state(item["manifest"], state)
        validation = validate_manifest(manifest, all_manifests=manifest_by_id)
        if validation["errors"]:
            manifest["load_status"] = "rejected"
            load_failures.append({"plugin_id": manifest.get("id"), "errors": validation["errors"], "path": item.get("path")})
        else:
            manifest["load_status"] = "loaded" if manifest.get("enabled") else "disabled"
        manifest["validation"] = validation
        if validation["warnings"]:
            compatibility_warnings.append({"plugin_id": manifest.get("id"), "warnings": validation["warnings"]})
        if include_disabled or manifest.get("enabled"):
            plugins.append(manifest)

    load_failures.extend(discovered["failures"])
    enabled = [plugin for plugin in plugins if plugin.get("enabled") and plugin.get("load_status") == "loaded"]
    tool_catalog = _tool_catalog(enabled)
    hooks = _hooks(enabled)
    ui_extensions = _ui_extensions(enabled)
    observability = plugin_observability(root)
    return {
        "schema_version": 1,
        "api_version": PLUGIN_API_VERSION,
        "workspace": str(root),
        "generated_at": utc_now(),
        "plugin_root": str(_workspace_plugin_root(root)),
        "state_path": str(memory_dir(root) / PLUGIN_STATE_FILE),
        "categories": _category_catalog(),
        "permission_scopes": _permission_catalog(),
        "plugins": plugins,
        "enabled_plugins": [plugin["id"] for plugin in enabled],
        "disabled_plugins": [plugin["id"] for plugin in plugins if not plugin.get("enabled")],
        "tool_catalog": tool_catalog,
        "workflow_hooks": hooks,
        "ui_extensions": ui_extensions,
        "packaging_format": packaging_format(),
        "diagnostics": {
            "status": "error" if load_failures else "warning" if compatibility_warnings else "ok",
            "plugin_count": len(plugins),
            "enabled_count": len(enabled),
            "load_failures": load_failures,
            "compatibility_warnings": compatibility_warnings,
            "isolation": "manifest-only loader; plugin code is not imported or executed",
        },
        "observability": observability,
    }


def discover_plugins(workspace: str | Path, *, refresh: bool = True) -> dict[str, Any]:
    root = _require_workspace(workspace)
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in _manifest_candidates(root):
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": scrub(str(exc)), "status": "failed"})
            continue
        manifest = normalize_manifest(payload, manifest_path=path, builtin=_is_builtin_manifest(path))
        manifests.append({"path": str(path), "manifest": manifest})
    manifests.sort(key=lambda item: str(item["manifest"].get("id")))
    return {"workspace": str(root), "refresh": refresh, "manifests": manifests, "failures": failures}


def set_plugin_state(
    workspace: str | Path,
    plugin_id: str,
    *,
    enabled: bool | None = None,
    trusted: bool | None = None,
    approval: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    manifest = _find_manifest(root, plugin_id)
    if manifest is None:
        raise PluginRuntimeError(f"plugin not found: {scrub(plugin_id)}")
    state = _read_state(root)
    current = state.setdefault("plugins", {}).setdefault(manifest["id"], {})
    validation = validate_manifest({**manifest, **current})
    high_risk = sorted(set(manifest["permission_scopes"]) & HIGH_RISK_SCOPES)
    if enabled is True and (validation["errors"] or (high_risk and not (approval or current.get("trusted") or trusted))):
        _record_observability(
            root,
            {
                "event": "plugin.enable_blocked",
                "plugin_id": manifest["id"],
                "status": "blocked",
                "permissions_used": high_risk,
                "detail": "Approval and trust are required for high-risk plugin scopes." if high_risk else "Manifest validation failed.",
                "errors": validation["errors"],
            },
        )
        raise PluginRuntimeError("plugin enable blocked by validation or permission approval policy")
    if trusted is not None:
        current["trusted"] = bool(trusted)
    if enabled is not None:
        current["enabled"] = bool(enabled)
    current["updated_at"] = utc_now()
    current["reason"] = scrub(reason)
    _write_state(root, state)
    saved = _apply_state(manifest, state)
    saved["validation"] = validate_manifest(saved)
    _record_observability(
        root,
        {
            "event": "plugin.state",
            "plugin_id": manifest["id"],
            "status": "updated",
            "permissions_used": high_risk,
            "detail": scrub(reason or "Plugin state updated."),
        },
    )
    return {"workspace": str(root), "plugin": saved, "state_path": str(memory_dir(root) / PLUGIN_STATE_FILE)}


def plugin_hooks(workspace: str | Path, *, workflow_type: str | None = None) -> dict[str, Any]:
    dashboard = plugin_dashboard(workspace, include_disabled=False)
    hooks = dashboard["workflow_hooks"]
    if workflow_type:
        filtered: dict[str, list[dict[str, Any]]] = {}
        for key, values in hooks.items():
            filtered[key] = [
                hook
                for hook in values
                if not hook.get("workflow_types") or workflow_type in hook.get("workflow_types", [])
            ]
        hooks = filtered
    return {
        "workspace": dashboard["workspace"],
        "workflow_type": workflow_type,
        "hooks": hooks,
        "tool_catalog": dashboard["tool_catalog"],
        "ui_extensions": dashboard["ui_extensions"],
    }


def run_tool(
    workspace: str | Path,
    plugin_id: str,
    tool_name: str,
    input_data: dict[str, Any] | None = None,
    *,
    dry_run: bool = True,
    approval: bool = False,
    workflow_type: str | None = None,
    source_client: str = "unknown",
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    start = time.perf_counter()
    plugin = _find_loaded_plugin(root, plugin_id)
    if plugin is None:
        raise PluginRuntimeError(f"plugin is not enabled or could not be loaded: {scrub(plugin_id)}")
    tool = next((item for item in plugin.get("tools", []) if item.get("name") == tool_name), None)
    if not tool:
        raise PluginRuntimeError(f"tool not found on plugin {scrub(plugin_id)}: {scrub(tool_name)}")
    permissions = sorted(set(tool.get("required_permissions", []) or plugin.get("permission_scopes", [])))
    high_risk = sorted(set(permissions) & HIGH_RISK_SCOPES)
    handler = str(tool.get("handler") or "")
    run_id = f"plugin-run-{uuid4().hex[:12]}"
    if handler not in BUILTIN_TOOL_HANDLERS:
        result = {
            "run_id": run_id,
            "workspace": str(root),
            "plugin_id": plugin["id"],
            "tool_name": tool_name,
            "ok": False,
            "blocked": True,
            "dry_run": dry_run,
            "duration_ms": _elapsed_ms(start),
            "permissions_used": permissions,
            "result": {},
            "errors": ["Plugin code execution is disabled until an isolated external sandbox is available."],
            "warnings": [],
        }
        _record_observability(root, _tool_event(result, source_client, workflow_type, "plugin.tool.blocked"))
        return result
    if high_risk and not approval:
        result = {
            "run_id": run_id,
            "workspace": str(root),
            "plugin_id": plugin["id"],
            "tool_name": tool_name,
            "ok": False,
            "blocked": True,
            "dry_run": dry_run,
            "duration_ms": _elapsed_ms(start),
            "permissions_used": permissions,
            "result": {},
            "errors": ["User approval is required before running high-risk plugin tool scopes."],
            "warnings": [f"High-risk scope(s): {', '.join(high_risk)}."],
        }
        _record_observability(root, _tool_event(result, source_client, workflow_type, "plugin.tool.blocked"))
        return result
    try:
        output = _run_builtin_handler(root, handler, input_data or {}, dry_run=dry_run, plugin=plugin, tool=tool)
        result = {
            "run_id": run_id,
            "workspace": str(root),
            "plugin_id": plugin["id"],
            "tool_name": tool_name,
            "ok": True,
            "blocked": False,
            "dry_run": dry_run,
            "duration_ms": _elapsed_ms(start),
            "permissions_used": permissions,
            "result": output,
            "errors": [],
            "warnings": _tool_warnings(plugin, tool, dry_run),
        }
        _record_observability(root, _tool_event(result, source_client, workflow_type, "plugin.tool.completed"))
        return result
    except Exception as exc:
        result = {
            "run_id": run_id,
            "workspace": str(root),
            "plugin_id": plugin["id"],
            "tool_name": tool_name,
            "ok": False,
            "blocked": False,
            "dry_run": dry_run,
            "duration_ms": _elapsed_ms(start),
            "permissions_used": permissions,
            "result": {},
            "errors": [scrub(str(exc))],
            "warnings": [],
        }
        _record_observability(root, _tool_event(result, source_client, workflow_type, "plugin.tool.failed"))
        return result


def validate_manifest(manifest: dict[str, Any], *, all_manifests: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    plugin_id = str(manifest.get("id") or "").strip()
    category = str(manifest.get("category") or "").strip()
    permissions = set(_clean_strings(manifest.get("permission_scopes", [])))
    capabilities = set(_clean_strings(manifest.get("capabilities", [])))
    if not plugin_id:
        errors.append("Plugin id is required.")
    if not str(manifest.get("name") or "").strip():
        errors.append("Plugin name is required.")
    if not str(manifest.get("version") or "").strip():
        errors.append("Plugin version is required.")
    if manifest.get("api_version") != PLUGIN_API_VERSION:
        errors.append(f"Plugin api_version must be {PLUGIN_API_VERSION}.")
    if category not in PLUGIN_CATEGORIES:
        errors.append(f"Plugin category must be one of: {', '.join(PLUGIN_CATEGORIES)}.")
    if not capabilities:
        errors.append("At least one capability is required.")
    unknown_permissions = permissions - set(PERMISSION_SCOPES)
    if unknown_permissions:
        errors.append(f"Unknown permission scope(s): {', '.join(sorted(unknown_permissions))}.")
    hinted = set().union(*(CAPABILITY_PERMISSION_HINTS.get(capability, set()) for capability in capabilities))
    extra = permissions - hinted
    if extra:
        warnings.append("Permission scope is broader than capability hints: " + ", ".join(sorted(extra)) + ".")
    if set(manifest.get("permission_scopes", [])) & HIGH_RISK_SCOPES and manifest.get("enabled") and not manifest.get("trusted"):
        errors.append("Enabled plugins with high-risk scopes must be trusted.")
    compat = manifest.get("runtime_compatibility") if isinstance(manifest.get("runtime_compatibility"), dict) else {}
    min_core = str(compat.get("min_core_version") or "0.0.0")
    if _version_gt(min_core, CORE_RUNTIME_VERSION):
        errors.append(f"Plugin requires Core >= {min_core}.")
    max_core = str(compat.get("max_core_version") or "")
    if max_core and _version_gt(CORE_RUNTIME_VERSION, max_core):
        errors.append(f"Plugin supports Core only through {max_core}.")
    for dep in manifest.get("dependencies", []):
        if not isinstance(dep, dict):
            errors.append("Plugin dependencies must be objects.")
            continue
        dep_id = str(dep.get("id") or "").strip()
        if dep_id and all_manifests is not None and dep_id not in all_manifests:
            warnings.append(f"Dependency {dep_id} is not currently installed.")
    for tool in manifest.get("tools", []):
        _validate_tool(tool, errors, warnings)
    for extension in manifest.get("ui_extensions", []):
        required = set(extension.get("required_permissions", []))
        missing = required - permissions
        if missing:
            errors.append(f"UI extension {extension.get('id')} requires permission scope(s) not granted by the manifest.")
    checksum = str(manifest.get("package", {}).get("checksum") or "")
    actual_checksum = str(manifest.get("package", {}).get("computed_checksum") or "")
    if checksum and checksum not in {"builtin", actual_checksum}:
        errors.append("Plugin manifest checksum does not match package metadata.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "high_risk_scopes": sorted(permissions & HIGH_RISK_SCOPES)}


def normalize_manifest(payload: dict[str, Any], *, manifest_path: Path | None = None, builtin: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    plugin_id = _safe_id(payload.get("id") or (manifest_path.parent.name if manifest_path else "unknown-plugin"))
    category = str(payload.get("category") or "analyzers").strip()
    manifest = {
        "id": plugin_id,
        "name": str(payload.get("name") or plugin_id).strip(),
        "version": str(payload.get("version") or "").strip(),
        "api_version": str(payload.get("api_version") or ""),
        "category": category,
        "description": scrub(str(payload.get("description") or "")),
        "author": scrub(str(payload.get("author") or "")),
        "capabilities": _clean_strings(payload.get("capabilities", [])),
        "dependencies": _clean_dependencies(payload.get("dependencies", [])),
        "permission_scopes": _clean_strings(payload.get("permission_scopes", [])),
        "runtime_compatibility": _clean_dict(payload.get("runtime_compatibility", {})),
        "tools": [_clean_tool(tool) for tool in _list_of_dicts(payload.get("tools", []))],
        "workflow_extensions": _clean_extension_block(payload.get("workflow_extensions", {})),
        "analyzer_extensions": _clean_extension_block(payload.get("analyzer_extensions", {})),
        "provider_extensions": _clean_extension_block(payload.get("provider_extensions", {})),
        "ui_extensions": _clean_ui_extensions(payload.get("ui_extensions", [])),
        "observability": _clean_dict(payload.get("observability", {})),
        "enabled": bool(payload.get("enabled", False)),
        "trusted": bool(payload.get("trusted", builtin)),
        "builtin": builtin,
        "package": _package_metadata(payload.get("package", {}), manifest_path=manifest_path, builtin=builtin, payload=payload),
        "failure_policy": str(payload.get("failure_policy") or "disable_plugin").strip(),
        "isolation": {
            "mode": "manifest_only",
            "code_execution": False,
            "external_processes": False,
            "network_by_default": False,
        },
    }
    return manifest


def plugin_observability(workspace: str | Path, *, limit: int = 50) -> dict[str, Any]:
    root = _require_workspace(workspace)
    path = memory_dir(root) / PLUGIN_OBSERVABILITY_FILE
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        lines = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    failures = [event for event in events if str(event.get("status")) in {"failed", "blocked", "crashed"}]
    durations = [int(event.get("duration_ms") or 0) for event in events if int(event.get("duration_ms") or 0) >= 0]
    permissions: dict[str, int] = {}
    for event in events:
        for scope in event.get("permissions_used", []):
            permissions[str(scope)] = permissions.get(str(scope), 0) + 1
    return {
        "path": str(path),
        "recent_events": events,
        "event_count": len(events),
        "failure_count": len(failures),
        "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
        "permissions_used": permissions,
    }


def packaging_format() -> dict[str, Any]:
    return {
        "manifest_names": list(PLUGIN_MANIFEST_NAMES),
        "required_fields": ["id", "name", "version", "api_version", "category", "capabilities", "permission_scopes"],
        "signature_fields": ["package.checksum", "package.signature", "package.signing_key_fingerprint"],
        "dependency_shape": {"id": "plugin id", "version": "semver or range", "optional": False},
        "update_metadata": ["package.update_channel", "package.update_url", "package.release_notes_url"],
        "loading_policy": "Manifests are loaded and validated; arbitrary plugin code is not imported by Core.",
    }


def _manifest_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    builtin_root = Path(__file__).resolve().parents[1] / "example-plugins"
    workspace_root = _workspace_plugin_root(root)
    for base in (builtin_root, workspace_root):
        if not base.exists():
            continue
        try:
            for name in PLUGIN_MANIFEST_NAMES:
                candidates.extend(path for path in base.rglob(name) if path.is_file())
            candidates.extend(path for path in base.glob("*.json") if path.is_file())
        except OSError:
            continue
    return candidates


def _workspace_plugin_root(root: Path) -> Path:
    return memory_dir(root) / "plugins"


def _is_builtin_manifest(path: Path) -> bool:
    return "example-plugins" in {part.lower() for part in path.parts}


def _find_manifest(root: Path, plugin_id: str) -> dict[str, Any] | None:
    target = _safe_id(plugin_id)
    for item in discover_plugins(root)["manifests"]:
        if item["manifest"].get("id") == target:
            return item["manifest"]
    return None


def _find_loaded_plugin(root: Path, plugin_id: str) -> dict[str, Any] | None:
    target = _safe_id(plugin_id)
    dashboard = plugin_dashboard(root, include_disabled=False)
    for plugin in dashboard["plugins"]:
        if plugin.get("id") == target and plugin.get("load_status") == "loaded":
            return plugin
    return None


def _apply_state(manifest: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    saved = dict(manifest)
    plugin_state = state.get("plugins", {}).get(saved["id"], {}) if isinstance(state.get("plugins"), dict) else {}
    if isinstance(plugin_state, dict):
        if "enabled" in plugin_state:
            saved["enabled"] = bool(plugin_state["enabled"])
        if "trusted" in plugin_state:
            saved["trusted"] = bool(plugin_state["trusted"])
        saved["state"] = {key: plugin_state.get(key) for key in ("updated_at", "reason") if key in plugin_state}
    return saved


def _read_state(root: Path) -> dict[str, Any]:
    path = memory_dir(root) / PLUGIN_STATE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "plugins": {}}
    return data if isinstance(data, dict) else {"schema_version": 1, "plugins": {}}


def _write_state(root: Path, state: dict[str, Any]) -> None:
    state["schema_version"] = 1
    state["updated_at"] = utc_now()
    ProjectMemory(root).write_json(PLUGIN_STATE_FILE, state)


def _record_observability(root: Path, event: dict[str, Any]) -> None:
    record = {
        "timestamp": utc_now(),
        "event": scrub(str(event.get("event") or "plugin.event")),
        "plugin_id": scrub(str(event.get("plugin_id") or "")),
        "tool_name": scrub(str(event.get("tool_name") or "")),
        "status": scrub(str(event.get("status") or "")),
        "duration_ms": int(event.get("duration_ms") or 0),
        "permissions_used": _clean_strings(event.get("permissions_used", [])),
        "workflow_type": scrub(str(event.get("workflow_type") or "")),
        "source_client": scrub(str(event.get("source_client") or "")),
        "detail": scrub(str(event.get("detail") or "")),
        "errors": [scrub(str(item)) for item in event.get("errors", []) if str(item).strip()],
    }
    path = memory_dir(root) / PLUGIN_OBSERVABILITY_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        return


def _run_builtin_handler(root: Path, handler: str, input_data: dict[str, Any], *, dry_run: bool, plugin: dict[str, Any], tool: dict[str, Any]) -> dict[str, Any]:
    if handler == "builtin.echo":
        return {"echo": input_data, "dry_run": dry_run}
    if handler == "builtin.validation_hint":
        commands = detect_validation_commands(root)
        return {"suggested_commands": commands[:5], "dry_run": True, "execution_performed": False}
    if handler == "builtin.architecture_summary":
        scan = WorkspaceScanner(root).scan(persist=False)
        return {
            "workspace_name": root.name,
            "file_count": scan.get("file_count", 0),
            "frameworks": scan.get("frameworks", []),
            "languages": scan.get("languages", []),
            "build_files": scan.get("build_files", [])[:10],
        }
    if handler == "builtin.roadmap_hint":
        scan = WorkspaceScanner(root).scan(persist=False)
        hints = []
        if scan.get("todo_comments"):
            hints.append("Convert TODO hotspots into roadmap items.")
        if detect_validation_commands(root):
            hints.append("Attach validation commands to roadmap phases.")
        hints.append("Keep first plugin-enhanced roadmap runs in proposal mode.")
        return {"hints": hints, "file_count": scan.get("file_count", 0)}
    if handler == "builtin.provider_status":
        return {
            "provider_id": plugin.get("provider_extensions", {}).get("provider_id") or plugin.get("id"),
            "local": True,
            "model_access": "declared" if "model_access" in plugin.get("permission_scopes", []) else "not_declared",
            "network_required": "network_access" in plugin.get("permission_scopes", []),
        }
    if handler == "builtin.observability_snapshot":
        return plugin_observability(root, limit=int(input_data.get("limit") or 20))
    raise PluginRuntimeError(f"unsupported builtin handler: {handler}")


def _tool_event(result: dict[str, Any], source_client: str, workflow_type: str | None, event: str) -> dict[str, Any]:
    return {
        "event": event,
        "plugin_id": result.get("plugin_id"),
        "tool_name": result.get("tool_name"),
        "status": "blocked" if result.get("blocked") else "completed" if result.get("ok") else "failed",
        "duration_ms": result.get("duration_ms", 0),
        "permissions_used": result.get("permissions_used", []),
        "workflow_type": workflow_type or "",
        "source_client": source_client,
        "detail": "; ".join(result.get("warnings", []) or result.get("errors", [])),
        "errors": result.get("errors", []),
    }


def _tool_catalog(plugins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for plugin in plugins:
        for tool in plugin.get("tools", []):
            tools.append({**tool, "plugin_id": plugin["id"], "plugin_name": plugin["name"], "category": plugin["category"]})
    return tools


def _hooks(plugins: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {
        "workflow_stages": [],
        "validators": [],
        "repair_strategies": [],
        "roadmap_analyzers": [],
        "architecture_analyzers": [],
    }
    for plugin in plugins:
        for block_name in ("workflow_extensions", "analyzer_extensions"):
            block = plugin.get(block_name, {}) if isinstance(plugin.get(block_name), dict) else {}
            for key in result:
                for hook in _list_of_dicts(block.get(key, [])):
                    result[key].append({**hook, "plugin_id": plugin["id"], "plugin_name": plugin["name"]})
    return result


def _ui_extensions(plugins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for plugin in plugins:
        for extension in plugin.get("ui_extensions", []):
            result.append({**extension, "plugin_id": plugin["id"], "plugin_name": plugin["name"]})
    return result


def _category_catalog() -> list[dict[str, Any]]:
    return [{"id": category, "label": category.replace("_", " ").title()} for category in PLUGIN_CATEGORIES]


def _permission_catalog() -> list[dict[str, Any]]:
    return [{"id": scope, **meta} for scope, meta in sorted(PERMISSION_SCOPES.items())]


def _clean_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _safe_id(tool.get("name") or "unnamed-tool"),
        "description": scrub(str(tool.get("description") or "")),
        "input_schema": _clean_dict(tool.get("input_schema", {"type": "object"})),
        "output_schema": _clean_dict(tool.get("output_schema", {"type": "object"})),
        "safety_level": str(tool.get("safety_level") or "low").strip().lower(),
        "supported_workflow_types": _clean_strings(tool.get("supported_workflow_types", [])),
        "execution_timeout_seconds": _clean_int(tool.get("execution_timeout_seconds"), 30, minimum=1, maximum=600),
        "retry_policy": _clean_dict(tool.get("retry_policy", {"max_attempts": 1})),
        "required_permissions": _clean_strings(tool.get("required_permissions", [])),
        "handler": str(tool.get("handler") or "").strip(),
    }


def _validate_tool(tool: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if not tool.get("name"):
        errors.append("Tool name is required.")
    if tool.get("safety_level") not in {"low", "medium", "high"}:
        errors.append(f"Tool {tool.get('name')} has unsupported safety_level.")
    unknown = set(tool.get("required_permissions", [])) - set(PERMISSION_SCOPES)
    if unknown:
        errors.append(f"Tool {tool.get('name')} uses unknown permission scope(s): {', '.join(sorted(unknown))}.")
    if tool.get("handler") and tool.get("handler") not in BUILTIN_TOOL_HANDLERS:
        warnings.append(f"Tool {tool.get('name')} declares a non-builtin handler and will be blocked by Core isolation.")


def _clean_extension_block(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {"workflow_stages", "validators", "repair_strategies", "roadmap_analyzers", "architecture_analyzers"}
    return {key: _list_of_dicts(value.get(key, [])) for key in allowed if key in value}


def _clean_ui_extensions(value: Any) -> list[dict[str, Any]]:
    result = []
    for item in _list_of_dicts(value):
        result.append(
            {
                "id": _safe_id(item.get("id") or "panel"),
                "kind": str(item.get("kind") or "panel").strip(),
                "title": scrub(str(item.get("title") or "")),
                "placement": str(item.get("placement") or "dashboard").strip(),
                "route": str(item.get("route") or "").strip(),
                "data_contract": str(item.get("data_contract") or "").strip(),
                "required_permissions": _clean_strings(item.get("required_permissions", [])),
            }
        )
    return result


def _package_metadata(value: Any, *, manifest_path: Path | None, builtin: bool, payload: dict[str, Any]) -> dict[str, Any]:
    data = _clean_dict(value)
    manifest_text = json.dumps({key: payload.get(key) for key in sorted(payload)}, sort_keys=True, ensure_ascii=True, default=str)
    computed = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    return {
        "manifest_path": str(manifest_path) if manifest_path else "",
        "checksum": str(data.get("checksum") or ("builtin" if builtin else "")),
        "computed_checksum": computed,
        "signature": str(data.get("signature") or ("builtin" if builtin else "")),
        "signing_key_fingerprint": str(data.get("signing_key_fingerprint") or ("aegis-builtin" if builtin else "")),
        "update_channel": str(data.get("update_channel") or "local"),
        "update_url": str(data.get("update_url") or ""),
        "release_notes_url": str(data.get("release_notes_url") or ""),
    }


def _clean_dependencies(value: Any) -> list[dict[str, Any]]:
    deps = []
    for item in _list_of_dicts(value):
        deps.append(
            {
                "id": _safe_id(item.get("id") or ""),
                "version": str(item.get("version") or "").strip(),
                "optional": bool(item.get("optional", False)),
            }
        )
    return [item for item in deps if item["id"]]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _clean_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _safe_id(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "-").replace("_", "-")
    cleaned = "".join(char for char in text if char.isalnum() or char in {"-", "."})
    return cleaned.strip("-.") or "unknown-plugin"


def _clean_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _version_gt(left: str, right: str) -> bool:
    def parts(value: str) -> tuple[int, int, int]:
        numbers = []
        for token in value.split(".")[:3]:
            try:
                numbers.append(int("".join(ch for ch in token if ch.isdigit()) or "0"))
            except ValueError:
                numbers.append(0)
        while len(numbers) < 3:
            numbers.append(0)
        return numbers[0], numbers[1], numbers[2]

    return parts(left) > parts(right)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _tool_warnings(plugin: dict[str, Any], tool: dict[str, Any], dry_run: bool) -> list[str]:
    warnings = []
    if dry_run:
        warnings.append("Dry run: no file, process, provider, or network mutation was performed.")
    if tool.get("handler") not in BUILTIN_TOOL_HANDLERS:
        warnings.append("Non-builtin handlers are blocked by Core isolation.")
    if set(tool.get("required_permissions", [])) & HIGH_RISK_SCOPES:
        warnings.append("High-risk tool scope was approved for this run.")
    return warnings


def _require_workspace(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise PluginRuntimeError(f"workspace does not exist or is not a directory: {root}")
    return root
