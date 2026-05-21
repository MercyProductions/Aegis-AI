from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import editing as editing_runtime
from .config import CONFIG_UPDATE_KEYS, ConfigPersistenceError, load_config, update_config
from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .model_router import model_registry, provider_inventory
from .roadmap import generate_roadmap
from .security import security_status
from .validation import detect_validation_commands
from .workspace import WorkspaceScanner
from .workspace_intelligence import workspace_intelligence
from . import workflow_runtime


ONBOARDING_FILE = "onboarding-state.json"
SETTINGS_IMPORT_FILE = "settings-import-history.json"
SCHEMA_VERSION = 1

ONBOARDING_STEPS: tuple[dict[str, Any], ...] = (
    {"id": "welcome", "label": "Welcome", "required": True, "summary": "Confirm this machine is the local Aegis runtime host."},
    {"id": "privacy", "label": "Privacy Mode", "required": True, "summary": "Choose local-only or cloud-enabled routing before any provider work."},
    {"id": "local_models", "label": "Local Models", "required": True, "summary": "Detect Ollama and installed local models."},
    {"id": "providers", "label": "Provider Linking", "required": False, "summary": "Link cloud providers only when cloud routing is enabled."},
    {"id": "workspace", "label": "Workspace", "required": True, "summary": "Select a writable workspace root and initialize .aegis state."},
    {"id": "safety", "label": "Safety Settings", "required": True, "summary": "Keep checkpoints, validation, and approval gates enabled by default."},
    {"id": "theme", "label": "Theme And Branding", "required": False, "summary": "Store UI preferences separately from credentials."},
    {"id": "first_workflow", "label": "First Workflow", "required": True, "summary": "Run a safe scan, roadmap, architecture, proposal, and validation preview."},
    {"id": "finish", "label": "Finish Checklist", "required": True, "summary": "Review remaining blockers before applying real changes."},
)

FIRST_WORKFLOW_STEPS: tuple[dict[str, str], ...] = (
    {"id": "scan_project", "label": "Scan Project", "summary": "Index files, build files, language mix, and project metadata."},
    {"id": "generate_roadmap", "label": "Generate Roadmap", "summary": "Create a Core-owned roadmap under .aegis."},
    {"id": "explain_architecture", "label": "Explain Architecture", "summary": "Use workspace intelligence and the knowledge graph summary."},
    {"id": "propose_small_improvement", "label": "Propose Small Improvement", "summary": "Prepare a low-risk proposal without applying files."},
    {"id": "validate_only", "label": "Validate Only", "summary": "Detect and preview the safest validation command."},
    {"id": "checkpoint_rollback_demo", "label": "Checkpoint And Rollback", "summary": "Show rollback readiness and optionally create a real checkpoint."},
)

RECOVERY_CARDS: tuple[dict[str, Any], ...] = (
    {
        "id": "backend_down",
        "title": "Website Backend Down",
        "summary": "The Website compatibility gateway has not synced with Core for this workspace.",
        "actions": ["Start the Website backend", "Open the Website health route", "Use Core-owned workflows while compatibility routes recover"],
    },
    {
        "id": "core_offline",
        "title": "Core Offline",
        "summary": "Start the Aegis Core service and retry the health check.",
        "actions": ["Run the Core launcher", "Check /v1/health", "Review .aegis/security-audit.jsonl if requests are rejected"],
    },
    {
        "id": "ollama_offline",
        "title": "Ollama Offline",
        "summary": "Local model routing needs Ollama or another local model server.",
        "actions": ["Install or start Ollama", "Pull a coding model", "Refresh model diagnostics"],
    },
    {
        "id": "provider_missing",
        "title": "Provider Missing",
        "summary": "Cloud providers are optional and should only be linked through the credential store.",
        "actions": ["Choose local-only mode", "Link an API key through provider settings", "Avoid plaintext key files"],
    },
    {
        "id": "key_missing",
        "title": "Provider Key Missing",
        "summary": "Cloud routing needs a provider key in the credential store, not in workspace files.",
        "actions": ["Stay in local-only mode", "Link the provider key through account settings", "Do not import plaintext provider secrets"],
    },
    {
        "id": "model_unavailable",
        "title": "Model Unavailable",
        "summary": "The selected model is not currently reachable.",
        "actions": ["Select an installed model", "Pull the missing local model", "Use a configured fallback route"],
    },
    {
        "id": "workspace_blocked",
        "title": "Workspace Blocked",
        "summary": "Aegis needs a real writable directory and a writable .aegis folder.",
        "actions": ["Select a project folder", "Check file permissions", "Avoid system or dependency directories"],
    },
    {
        "id": "update_failed",
        "title": "Update Failed",
        "summary": "Use release recovery before continuing with workflows.",
        "actions": ["Open release status", "Restore the previous package", "Collect update logs"],
    },
    {
        "id": "validation_failed",
        "title": "Validation Failed",
        "summary": "Keep work in proposal mode and inspect validation logs before apply.",
        "actions": ["Run validation-only", "Review first diagnostic", "Create a repair workflow after approval"],
    },
    {
        "id": "extension_disconnected",
        "title": "Extension Disconnected",
        "summary": "Editor extensions have not synced with Core for this workspace yet.",
        "actions": ["Open the workspace in VS Code or Visual Studio", "Run the extension health check", "Confirm the extension can reach Core"],
    },
    {
        "id": "desktop_blank_state",
        "title": "Desktop Blank State",
        "summary": "The Desktop client has not synced with Core or has no selected workspace.",
        "actions": ["Open Desktop setup", "Select a workspace", "Refresh Core runtime status"],
    },
)


def onboarding_status(workspace: str | Path | None = None) -> dict[str, Any]:
    root = Path(workspace or ".").expanduser().resolve()
    exists = root.exists() and root.is_dir()
    state = _load_state(root) if exists else {}
    config = load_config(root)
    diagnostics = _diagnostics(root, exists=exists)
    completed_steps = {str(item) for item in state.get("completed_steps", []) if str(item).strip()}
    first_workflow_state = state.get("first_workflow") if isinstance(state.get("first_workflow"), dict) else {}
    first_workflow_completed = {
        str(item)
        for item in first_workflow_state.get("completed_steps", [])
        if str(item).strip()
    }

    steps = [
        _step_status(step, diagnostics, config.to_dict(), completed_steps, first_workflow_completed)
        for step in ONBOARDING_STEPS
    ]
    required_done = all(step["status"] == "complete" for step in steps if step["required"])
    current_step = str(state.get("current_step") or next((step["id"] for step in steps if step["status"] != "complete"), "finish"))
    completed = bool(state.get("completed", False)) or required_done
    if completed:
        current_step = "finish"

    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(root),
        "generated_at": utc_now(),
        "completed": completed,
        "current_step": current_step,
        "steps": steps,
        "diagnostics": diagnostics,
        "privacy": _privacy_summary(root, config.to_dict()),
        "recommended_defaults": _recommended_defaults(),
        "first_workflow": {
            "completed_steps": sorted(first_workflow_completed),
            "steps": [_first_workflow_step(step, first_workflow_completed) for step in FIRST_WORKFLOW_STEPS],
            "latest_result": first_workflow_state.get("latest_result", {}),
        },
        "recovery": _recovery_cards(diagnostics),
        "settings": _safe_onboarding_preferences(state, config.to_dict()),
        "state_path": str(_state_path(root)) if exists else "",
    }


def update_onboarding(
    workspace: str | Path,
    *,
    completed_steps: list[str] | None = None,
    current_step: str | None = None,
    preferences: dict[str, Any] | None = None,
    first_workflow_completed_steps: list[str] | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    state = {} if reset else _load_state(root)
    now = utc_now()
    state.setdefault("created_at", now)
    state["updated_at"] = now
    if completed_steps is not None:
        allowed = {step["id"] for step in ONBOARDING_STEPS}
        state["completed_steps"] = sorted({step for step in _clean_strings(completed_steps) if step in allowed})
    if current_step is not None:
        state["current_step"] = _clean_step(current_step, default="welcome")
    if preferences is not None:
        state["preferences"] = _clean_preferences(preferences)
    if first_workflow_completed_steps is not None:
        first = state.get("first_workflow") if isinstance(state.get("first_workflow"), dict) else {}
        allowed = {step["id"] for step in FIRST_WORKFLOW_STEPS}
        first["completed_steps"] = sorted({step for step in _clean_strings(first_workflow_completed_steps) if step in allowed})
        state["first_workflow"] = first
    status_preview = onboarding_status(root)
    required_ids = {step["id"] for step in status_preview["steps"] if step["required"]}
    completed_ids = set(state.get("completed_steps", []))
    first_completed = set((state.get("first_workflow") or {}).get("completed_steps", [])) if isinstance(state.get("first_workflow"), dict) else set()
    if first_completed == {step["id"] for step in FIRST_WORKFLOW_STEPS}:
        completed_ids.add("first_workflow")
        state["completed_steps"] = sorted(completed_ids)
    state["completed"] = required_ids.issubset(completed_ids)
    _write_state(root, state)
    return onboarding_status(root)


def export_settings(workspace: str | Path) -> dict[str, Any]:
    root = _require_workspace(workspace)
    config = load_config(root).to_dict()
    state = _load_state(root)
    providers = provider_inventory(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": utc_now(),
        "workspace": str(root),
        "settings": _exportable_config(config),
        "privacy": _privacy_summary(root, config),
        "provider_config_metadata": _provider_metadata(providers),
        "ui_preferences": _clean_preferences(state.get("preferences") if isinstance(state.get("preferences"), dict) else {}),
        "runtime_urls": {
            "ollama_url": config.get("ollama_url"),
            "lm_studio_url": config.get("lm_studio_url"),
        },
        "workspace_preferences": {
            "workspace": str(root),
            "auto_scan_on_open": bool(config.get("auto_scan_on_open", False)),
            "memory_dir_name": config.get("memory_dir_name") or ".aegis",
            "validation_preferences": config.get("validation_preferences") or [],
        },
        "notes": [
            "Provider secrets are never exported.",
            "Import writes only safe config metadata, UI preferences, runtime URLs, and workspace preferences.",
        ],
    }


def import_settings(workspace: str | Path, payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    root = _require_workspace(workspace)
    if not isinstance(payload, dict):
        raise ValueError("settings import payload must be an object")
    source_settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    runtime_urls = payload.get("runtime_urls") if isinstance(payload.get("runtime_urls"), dict) else {}
    workspace_preferences = payload.get("workspace_preferences") if isinstance(payload.get("workspace_preferences"), dict) else {}
    ui_preferences = payload.get("ui_preferences") if isinstance(payload.get("ui_preferences"), dict) else payload.get("preferences", {})
    merged_source = {**source_settings, **runtime_urls, **workspace_preferences}
    config_updates = {key: merged_source[key] for key in CONFIG_UPDATE_KEYS if key in merged_source}
    ignored_keys = sorted(str(key) for key in merged_source if key not in CONFIG_UPDATE_KEYS)
    preview_config = load_config(root).to_dict()
    preview_config.update(config_updates)
    state = _load_state(root)
    preferences = _clean_preferences(ui_preferences if isinstance(ui_preferences, dict) else {})

    if not dry_run:
        try:
            updated = update_config(root, config_updates) if config_updates else load_config(root)
        except ConfigPersistenceError:
            raise
        state["preferences"] = {**_clean_preferences(state.get("preferences", {})), **preferences}
        history = _read_json(root, SETTINGS_IMPORT_FILE, [])
        history = history if isinstance(history, list) else []
        history.insert(
            0,
            {
                "imported_at": utc_now(),
                "imported_keys": sorted(config_updates),
                "ignored_keys": ignored_keys,
                "ui_preference_keys": sorted(preferences),
            },
        )
        _write_state(root, state)
        _write_json(root, SETTINGS_IMPORT_FILE, history[:50])
        preview_config = updated.to_dict()

    return {
        "workspace": str(root),
        "dry_run": dry_run,
        "imported_keys": sorted(config_updates),
        "ignored_keys": ignored_keys,
        "ui_preference_keys": sorted(preferences),
        "settings_preview": _exportable_config(preview_config),
        "warnings": _import_warnings(config_updates, ignored_keys),
    }


def run_first_workflow(
    workspace: str | Path,
    action: str,
    *,
    dry_run: bool = True,
    source_client: str = "unknown",
) -> dict[str, Any]:
    root = _require_workspace(workspace)
    action_id = str(action or "").strip().lower().replace("-", "_")
    allowed = {step["id"] for step in FIRST_WORKFLOW_STEPS}
    if action_id not in allowed:
        raise ValueError(f"unsupported first workflow action: {scrub(action_id)}")

    if action_id == "scan_project":
        result = WorkspaceScanner(root).scan(persist=not dry_run)
    elif action_id == "generate_roadmap":
        result = generate_roadmap(root, persist=not dry_run)
    elif action_id == "explain_architecture":
        result = _architecture_explanation(root, dry_run=dry_run)
    elif action_id == "propose_small_improvement":
        result = _small_improvement_proposal(root, dry_run=dry_run, source_client=source_client)
    elif action_id == "validate_only":
        result = editing_runtime.run_validation_operation(root, dry_run=True, source_client=source_client)
    else:
        result = _checkpoint_rollback_demo(root, dry_run=dry_run, source_client=source_client)

    if not dry_run or action_id in {"scan_project", "generate_roadmap", "explain_architecture", "validate_only"}:
        _record_first_workflow_result(root, action_id, result)

    return {
        "workspace": str(root),
        "action": action_id,
        "dry_run": dry_run,
        "completed": action_id,
        "result": result,
        "next_actions": _first_workflow_next_actions(action_id),
    }


def _diagnostics(root: Path, *, exists: bool) -> dict[str, Any]:
    config = load_config(root)
    checks: list[dict[str, Any]] = []
    checks.append(_check("core_running", "Core Running", "pass", "Aegis Core handled this onboarding request."))

    security = security_status(root)
    token_enforced = bool(security.get("local_api", {}).get("token_enforced", False))
    checks.append(
        _check(
            "local_api_auth",
            "Local API Auth",
            "pass" if token_enforced else "warn",
            "Bearer token is enforced for local Core requests."
            if token_enforced
            else "Compatibility mode is active; set AEGIS_CORE_LOCAL_TOKEN for stricter first-run security.",
        )
    )

    if not exists:
        checks.extend(
            [
                _check("workspace_selected", "Workspace Selected", "fail", f"Workspace does not exist: {root}"),
                _check("workspace_permissions", "Workspace Permissions", "fail", "Select an existing project folder."),
                _check("aegis_state", "Aegis State", "fail", "No .aegis folder can be initialized until the workspace exists."),
            ]
        )
        model_data = _offline_model_data(config)
        provider_data = _offline_provider_data(config)
        client_data = {}
    else:
        checks.append(_check("workspace_selected", "Workspace Selected", "pass", str(root)))
        checks.append(_workspace_permission_check(root))
        checks.append(_aegis_state_check(root))
        model_data = _safe_model_registry(root)
        provider_data = _safe_provider_inventory(root)
        client_data = _safe_client_sync(root)

    ollama = model_data.get("ollama") if isinstance(model_data.get("ollama"), dict) else {}
    ollama_reachable = bool(ollama.get("reachable", False))
    models = ollama.get("installed_models") if isinstance(ollama.get("installed_models"), list) else []
    checks.append(
        _check(
            "ollama_running",
            "Ollama Running",
            "pass" if ollama_reachable else "warn",
            f"Ollama responded with {len(models)} model(s)." if ollama_reachable else str(ollama.get("error") or "Ollama is not reachable."),
            {"endpoint": config.ollama_url, "latency_ms": ollama.get("latency_ms")},
        )
    )
    checks.append(
        _check(
            "models_available",
            "Models Available",
            "pass" if models else "warn",
            f"{len(models)} local model(s) available." if models else "No local models were discovered yet.",
            {"installed_models": models[:20], "selected_model": ollama.get("selected_model")},
        )
    )

    cloud_enabled = config.model_routing_mode != "local_only" and not bool(provider_data.get("cloud_disabled", False))
    cloud_providers = [
        item
        for item in provider_data.get("providers", [])
        if isinstance(item, dict) and not bool(item.get("local", False))
    ]
    linked_cloud = [item for item in cloud_providers if bool(item.get("configured") or item.get("key_stored") or item.get("provider_reachable"))]
    checks.append(
        _check(
            "provider_linking",
            "Provider Linking",
            "pass" if not cloud_enabled or linked_cloud else "warn",
            "Local-only mode does not require cloud provider linking."
            if not cloud_enabled
            else f"{len(linked_cloud)} cloud provider(s) appear configured."
            if linked_cloud
            else "Cloud routing is enabled but no cloud provider is linked.",
            {"cloud_enabled": cloud_enabled, "linked_provider_ids": [str(item.get("id")) for item in linked_cloud]},
        )
    )

    clients = client_data.get("active_clients") if isinstance(client_data.get("active_clients"), list) else []
    checks.extend(_extension_install_checks())
    checks.extend(_client_checks(clients))
    checks.append(
        _check(
            "release_recovery",
            "Release Recovery",
            "pass",
            "Release manifest, migration, and rollback contracts are available from Core.",
        )
    )
    return {
        "generated_at": utc_now(),
        "summary": _diagnostic_summary(checks),
        "checks": checks,
        "model_registry": _diagnostic_model_excerpt(model_data),
        "provider_status": _diagnostic_provider_excerpt(provider_data),
        "client_sync": {
            "active_clients": clients,
            "active_workflows": client_data.get("active_workflows", []),
            "recent_operations": client_data.get("recent_operations", []),
        },
    }


def _step_status(
    step: dict[str, Any],
    diagnostics: dict[str, Any],
    config: dict[str, Any],
    completed_steps: set[str],
    first_workflow_completed: set[str],
) -> dict[str, Any]:
    step_id = str(step["id"])
    diagnostic_map = {item["id"]: item for item in diagnostics.get("checks", []) if isinstance(item, dict)}
    status = "pending"
    detail = str(step.get("summary") or "")
    if step_id in completed_steps:
        status = "complete"
    elif step_id == "welcome":
        status = "complete"
        detail = "Core is reachable and the first-run contract is available."
    elif step_id == "privacy":
        status = "complete" if config.get("model_routing_mode") in {"local_only", "hybrid", "cloud_allowed"} else "blocked"
        detail = f"Current routing mode: {config.get('model_routing_mode') or 'local_only'}."
    elif step_id == "local_models":
        model_check = diagnostic_map.get("models_available", {})
        status = "complete" if model_check.get("status") == "pass" else "needs_attention"
        detail = str(model_check.get("detail") or detail)
    elif step_id == "providers":
        provider_check = diagnostic_map.get("provider_linking", {})
        status = "complete" if provider_check.get("status") == "pass" else "needs_attention"
        detail = str(provider_check.get("detail") or detail)
    elif step_id == "workspace":
        workspace_ok = diagnostic_map.get("workspace_permissions", {}).get("status") == "pass"
        state_ok = diagnostic_map.get("aegis_state", {}).get("status") == "pass"
        status = "complete" if workspace_ok and state_ok else "blocked"
        detail = "Workspace root and .aegis state are writable." if status == "complete" else "Select a writable workspace."
    elif step_id == "safety":
        status = "complete" if config.get("safety_mode", "strict") else "needs_attention"
        detail = "Strict safety mode keeps checkpoints, validation, and approval gates visible."
    elif step_id == "theme":
        status = "complete" if step_id in completed_steps else "optional"
    elif step_id == "first_workflow":
        required = {item["id"] for item in FIRST_WORKFLOW_STEPS}
        status = "complete" if required.issubset(first_workflow_completed) else "pending"
        detail = f"{len(first_workflow_completed)}/{len(required)} first workflow step(s) completed."
    elif step_id == "finish":
        blocking = [item for item in diagnostics.get("checks", []) if isinstance(item, dict) and item.get("status") == "fail"]
        status = "complete" if not blocking and step_id in completed_steps else "blocked" if blocking else "pending"
        detail = "No blocking setup diagnostics remain." if not blocking else f"{len(blocking)} blocking diagnostic(s) remain."
    return {
        **step,
        "status": status,
        "detail": detail,
        "action": _step_action(step_id, status),
    }


def _first_workflow_step(step: dict[str, str], completed: set[str]) -> dict[str, str]:
    return {**step, "status": "complete" if step["id"] in completed else "pending"}


def _privacy_summary(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    security = security_status(root)
    privacy = security.get("privacy", {}) if isinstance(security.get("privacy"), dict) else {}
    return {
        "mode": privacy.get("mode", "local-first"),
        "model_routing_mode": config.get("model_routing_mode", "local_only"),
        "local_only": bool(privacy.get("local_only", config.get("model_routing_mode") == "local_only")),
        "cloud_disabled": bool(privacy.get("cloud_disabled", False)),
        "provider_usage_warnings": True,
        "sensitive_file_detection": True,
        "prompt_redaction_before_cloud": True,
    }


def _recommended_defaults() -> dict[str, Any]:
    return {
        "privacy_mode": "local-first",
        "model_routing_mode": "local_only",
        "checkpoint_before_apply": True,
        "validation_before_apply": True,
        "approval_required_for_apply": True,
        "max_files_changed": 25,
        "auto_apply": False,
        "first_workflow_mode": "validate_only",
    }


def _recovery_cards(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    check_status = {str(item.get("id")): str(item.get("status")) for item in diagnostics.get("checks", []) if isinstance(item, dict)}
    cards: list[dict[str, Any]] = []
    for card in RECOVERY_CARDS:
        active = False
        if card["id"] == "backend_down":
            active = check_status.get("website_backend") in {"warn", "fail"}
        elif card["id"] == "ollama_offline":
            active = check_status.get("ollama_running") in {"warn", "fail"}
        elif card["id"] == "model_unavailable":
            active = check_status.get("models_available") in {"warn", "fail"}
        elif card["id"] in {"provider_missing", "key_missing"}:
            active = check_status.get("provider_linking") in {"warn", "fail"}
        elif card["id"] == "workspace_blocked":
            active = check_status.get("workspace_permissions") == "fail" or check_status.get("aegis_state") == "fail"
        elif card["id"] == "extension_disconnected":
            active = check_status.get("vscode_extension") in {"warn", "fail"} or check_status.get("visual_studio_extension") in {"warn", "fail"}
        elif card["id"] == "desktop_blank_state":
            active = check_status.get("desktop_client") in {"warn", "fail"}
        cards.append({**card, "active": active})
    return cards


def _architecture_explanation(root: Path, *, dry_run: bool) -> dict[str, Any]:
    intelligence = workspace_intelligence(root, persist=not dry_run, refresh=not dry_run)
    architecture = intelligence.get("knowledge", {}).get("architecture_summary", {}) if isinstance(intelligence.get("knowledge"), dict) else {}
    metadata = intelligence.get("metadata", {}) if isinstance(intelligence.get("metadata"), dict) else {}
    return {
        "workspace": str(root),
        "dry_run": dry_run,
        "summary": architecture.get("summary") or f"{metadata.get('workspace_name') or root.name} has {metadata.get('file_count', 0)} indexed file(s).",
        "frameworks": intelligence.get("frameworks", []),
        "build_systems": intelligence.get("build_systems", []),
        "entry_points": metadata.get("entry_points", []),
        "risk_areas": architecture.get("risk_areas", []),
    }


def _small_improvement_proposal(root: Path, *, dry_run: bool, source_client: str) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=False)
    readme = next((path for path in scan.get("readmes", []) if isinstance(path, str) and path.strip()), "")
    target_path = readme or "AEGIS_ONBOARDING_NOTES.md"
    action = "append" if readme else "create"
    content = (
        "\n\n## Aegis First Workflow Note\n\n"
        "- Aegis scanned this workspace in validate-only onboarding mode.\n"
        "- Keep first applied changes small, checkpointed, and validated.\n"
    )
    change = {
        "action": action,
        "path": target_path,
        "content": content if action == "append" else content.lstrip(),
        "summary": "Document the safe first workflow checkpoint and validation habit.",
        "selected": False,
    }
    if dry_run:
        return {
            "workspace": str(root),
            "dry_run": True,
            "proposal": None,
            "preview_change": change,
            "risk": "low",
            "applies_files": False,
            "approval_required": True,
        }
    return editing_runtime.propose_changes(
        root,
        [change],
        summary="Aegis onboarding safe first improvement",
        source_client=source_client,
        risk="low",
    )


def _checkpoint_rollback_demo(root: Path, *, dry_run: bool, source_client: str) -> dict[str, Any]:
    scan = WorkspaceScanner(root).scan(persist=False)
    candidates = [
        path
        for path in [*(scan.get("readmes", []) or []), *(scan.get("build_files", []) or []), *(scan.get("entry_points", []) or [])]
        if isinstance(path, str) and path.strip()
    ]
    checkpoints = editing_runtime.list_checkpoints(root, limit=5)
    if dry_run or not candidates:
        return {
            "workspace": str(root),
            "dry_run": True,
            "candidate_paths": candidates[:5],
            "checkpoint_available": bool(checkpoints.get("checkpoints")),
            "checkpoints": checkpoints.get("checkpoints", []),
            "rollback_demo": "A real apply will create a checkpoint first; restore previews are available from /v1/checkpoints/restore.",
        }
    checkpoint = editing_runtime.create_checkpoint(
        root,
        paths=[candidates[0]],
        summary="Aegis first-run rollback demonstration checkpoint",
        source_client=source_client,
    )
    return {
        "workspace": str(root),
        "dry_run": False,
        "checkpoint": checkpoint,
        "checkpoints": editing_runtime.list_checkpoints(root, limit=5).get("checkpoints", []),
    }


def _record_first_workflow_result(root: Path, action_id: str, result: dict[str, Any]) -> None:
    state = _load_state(root)
    first = state.get("first_workflow") if isinstance(state.get("first_workflow"), dict) else {}
    completed = {str(item) for item in first.get("completed_steps", []) if str(item).strip()}
    completed.add(action_id)
    first["completed_steps"] = sorted(completed)
    first["latest_result"] = {
        "action": action_id,
        "recorded_at": utc_now(),
        "summary": _result_summary(action_id, result),
    }
    state["first_workflow"] = first
    completed_steps = {str(item) for item in state.get("completed_steps", []) if str(item).strip()}
    if completed == {step["id"] for step in FIRST_WORKFLOW_STEPS}:
        completed_steps.add("first_workflow")
    state["completed_steps"] = sorted(completed_steps)
    state["updated_at"] = utc_now()
    _write_state(root, state)


def _result_summary(action_id: str, result: dict[str, Any]) -> str:
    if action_id == "scan_project":
        return f"Indexed {result.get('file_count', 0)} file(s)."
    if action_id == "generate_roadmap":
        return f"Generated {len(result.get('tasks', []) if isinstance(result.get('tasks'), list) else [])} roadmap task(s)."
    if action_id == "explain_architecture":
        return str(result.get("summary") or "Architecture summary prepared.")
    if action_id == "propose_small_improvement":
        proposal = result.get("proposal") if isinstance(result.get("proposal"), dict) else {}
        return f"Prepared proposal {proposal.get('id') or 'preview'}."
    if action_id == "validate_only":
        validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
        return f"Validation preview command: {validation.get('command') or 'none detected'}."
    return "Checkpoint and rollback readiness reviewed."


def _first_workflow_next_actions(action_id: str) -> list[str]:
    order = [step["id"] for step in FIRST_WORKFLOW_STEPS]
    try:
        index = order.index(action_id)
    except ValueError:
        return []
    if index + 1 >= len(order):
        return ["Review finish checklist", "Keep apply disabled until checkpoints and validation are visible"]
    return [f"Run {order[index + 1].replace('_', ' ')}"]


def _workspace_permission_check(root: Path) -> dict[str, Any]:
    probe = root / ".aegis-permission-check.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _check("workspace_permissions", "Workspace Permissions", "pass", "Workspace root is writable.")
    except OSError as exc:
        return _check("workspace_permissions", "Workspace Permissions", "fail", f"Workspace is not writable: {scrub(str(exc))}")


def _aegis_state_check(root: Path) -> dict[str, Any]:
    try:
        memory = ProjectMemory(root)
        memory.ensure()
        probe = memory.root / ".onboarding-write-check.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _check("aegis_state", "Aegis State", "pass", f"State directory is writable: {memory.root}")
    except OSError as exc:
        return _check("aegis_state", "Aegis State", "fail", f"Could not write .aegis state: {scrub(str(exc))}")


def _client_checks(clients: list[Any]) -> list[dict[str, Any]]:
    normalized = [item for item in clients if isinstance(item, dict)]
    type_text = " ".join(str(item.get("client_type") or item.get("name") or "").lower() for item in normalized)
    checks = []
    expectations = (
        ("website_backend", "Website Backend", ("website", "backend")),
        ("desktop_client", "Desktop Connected", ("desktop", "native")),
        ("vscode_extension", "VS Code Extension", ("vscode", "vs code")),
        ("visual_studio_extension", "Visual Studio Extension", ("visual studio", "vs extension")),
    )
    for check_id, label, tokens in expectations:
        found = any(token in type_text for token in tokens)
        checks.append(
            _check(
                check_id,
                label,
                "pass" if found else "warn",
                f"{label} has synced with Core." if found else f"{label} has not synced with Core for this workspace yet.",
            )
        )
    return checks


def _extension_install_checks() -> list[dict[str, Any]]:
    vscode_found = _vscode_extension_installed()
    vs_found = _visual_studio_extension_installed()
    return [
        _check(
            "vscode_extension_installed",
            "VS Code Extension Installed",
            "pass" if vscode_found else "warn",
            "Aegis Local Agent appears in the VS Code extension folder."
            if vscode_found
            else "VS Code extension install was not detected locally. Install the Aegis VSIX or let the extension register with Core.",
        ),
        _check(
            "visual_studio_extension_installed",
            "Visual Studio Extension Installed",
            "pass" if vs_found else "warn",
            "Aegis Local Agent appears in the Visual Studio extension folder."
            if vs_found
            else "Visual Studio extension install was not detected locally. Install the Aegis VSIX or use the VS extension source package.",
        ),
    ]


def _vscode_extension_installed() -> bool:
    candidates = [
        Path.home() / ".vscode" / "extensions",
        Path.home() / ".vscode-insiders" / "extensions",
    ]
    tokens = ("aegis-local-autopilot", "aegis.local-agent", "aegis-local-agent")
    for folder in candidates:
        try:
            if folder.is_dir() and any(any(token in child.name.lower() for token in tokens) for child in folder.iterdir()):
                return True
        except OSError:
            continue
    return False


def _visual_studio_extension_installed() -> bool:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return False
    root = Path(local_app_data) / "Microsoft" / "VisualStudio"
    checked = 0
    try:
        manifests = root.rglob("extension.vsixmanifest") if root.is_dir() else []
        for manifest in manifests:
            checked += 1
            if checked > 250:
                break
            try:
                text = manifest.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            if "aegis local agent" in text or "aegislocalagentvs" in text:
                return True
    except OSError:
        return False
    return False


def _diagnostic_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        status = str(check.get("status") or "warn")
        if status in counts:
            counts[status] += 1
    return {
        "status": "fail" if counts["fail"] else "warn" if counts["warn"] else "pass",
        "pass_count": counts["pass"],
        "warning_count": counts["warn"],
        "failure_count": counts["fail"],
    }


def _diagnostic_model_excerpt(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_profile": data.get("active_profile") or data.get("mode") or "local_only",
        "selected_model": data.get("selected_model"),
        "fallback_models": data.get("fallback_models", []),
        "ollama": data.get("ollama", {}),
    }


def _diagnostic_provider_excerpt(data: dict[str, Any]) -> dict[str, Any]:
    providers = [item for item in data.get("providers", []) if isinstance(item, dict)]
    return {
        "mode": data.get("mode", "local_only"),
        "local_only": data.get("local_only", True),
        "privacy_mode": data.get("privacy_mode", "local-first"),
        "cloud_disabled": data.get("cloud_disabled", False),
        "providers": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "local": item.get("local", False),
                "configured": item.get("configured", False),
                "key_stored": item.get("key_stored", False),
                "availability_status": item.get("availability_status", "unknown"),
            }
            for item in providers
        ],
    }


def _safe_model_registry(root: Path) -> dict[str, Any]:
    try:
        return model_registry(root)
    except Exception as exc:
        config = load_config(root)
        data = _offline_model_data(config)
        data["ollama"]["error"] = scrub(str(exc))
        return data


def _safe_provider_inventory(root: Path) -> dict[str, Any]:
    try:
        return provider_inventory(root)
    except Exception as exc:
        data = _offline_provider_data(load_config(root))
        data["credential_store_errors"] = [{"error": scrub(str(exc))}]
        return data


def _offline_model_data(config: Any) -> dict[str, Any]:
    return {
        "active_profile": "local_only",
        "selected_model": None,
        "fallback_models": [],
        "providers": [],
        "models": [],
        "ollama": {
            "reachable": False,
            "installed_models": [],
            "selected_model": None,
            "missing_models": [config.default_model, *config.fallback_models],
            "error": "Model registry was not queried because the workspace is not ready.",
        },
    }


def _offline_provider_data(config: Any) -> dict[str, Any]:
    return {
        "mode": config.model_routing_mode,
        "local_only": True,
        "cloud_disabled": True,
        "providers": [],
        "credential_store_healthy": False,
        "credential_store_errors": [],
    }


def _safe_client_sync(root: Path) -> dict[str, Any]:
    try:
        return workflow_runtime.sync_dashboard(root, limit=50)
    except Exception:
        return {"active_clients": [], "active_workflows": [], "recent_operations": []}


def _provider_metadata(data: dict[str, Any]) -> list[dict[str, Any]]:
    providers = data.get("providers", []) if isinstance(data.get("providers"), list) else []
    result: list[dict[str, Any]] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        result.append(
            {
                "id": provider.get("id"),
                "label": provider.get("label"),
                "local": bool(provider.get("local", False)),
                "configured": bool(provider.get("configured", False)),
                "requires_key": bool(provider.get("requires_key", False)),
                "key_present": bool(provider.get("key_stored", False)),
                "auth_methods": provider.get("auth_methods", []),
                "availability_status": provider.get("availability_status", "unknown"),
            }
        )
    return result


def _safe_onboarding_preferences(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "preferences": _clean_preferences(state.get("preferences", {}) if isinstance(state.get("preferences"), dict) else {}),
        "config": _exportable_config(config),
    }


def _exportable_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "ollama_url",
        "lm_studio_url",
        "default_model",
        "default_local_model",
        "local_small_model",
        "local_coder_model",
        "local_embedding_model",
        "preferred_cloud_provider",
        "preferred_cloud_model",
        "model_routing_mode",
        "fallback_models",
        "max_context_chars",
        "cloud_cost_warnings",
        "safety_mode",
        "auto_scan_on_open",
        "validation_preferences",
        "memory_dir_name",
    }
    return {key: config.get(key) for key in sorted(allowed) if key in config}


def _clean_preferences(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "theme": "system",
        "brand_variant": "auralith",
        "setup_progress_visible": True,
        "show_missing_dependency_cards": True,
        "preferred_first_workflow": "validate_only",
        "docs_base_url": "docs/FIRST_RUN_ONBOARDING.md",
    }
    cleaned: dict[str, Any] = {}
    for key, default in allowed.items():
        if key not in value:
            continue
        raw = value[key]
        if isinstance(default, bool):
            cleaned[key] = bool(raw)
        else:
            text = str(raw).strip()
            cleaned[key] = text or default
    return cleaned


def _import_warnings(updates: dict[str, Any], ignored_keys: list[str]) -> list[str]:
    warnings: list[str] = []
    if ignored_keys:
        warnings.append("Ignored unsupported or unsafe settings keys.")
    if "preferred_cloud_provider" in updates or "preferred_cloud_model" in updates:
        warnings.append("Provider metadata was imported, but provider secrets must be linked through the OS credential store.")
    return warnings


def _step_action(step_id: str, status: str) -> dict[str, str]:
    if step_id == "local_models":
        return {"kind": "refresh_models", "label": "Refresh"}
    if step_id == "providers":
        return {"kind": "open_providers", "label": "Open Providers"}
    if step_id == "workspace":
        return {"kind": "select_workspace", "label": "Select Workspace"}
    if step_id == "first_workflow":
        return {"kind": "run_first_workflow", "label": "Run Guide"}
    if status == "complete":
        return {"kind": "review", "label": "Review"}
    return {"kind": "configure", "label": "Configure"}


def _check(check_id: str, label: str, status: str, detail: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": scrub(detail),
        "metadata": metadata or {},
    }


def _clean_strings(values: list[str]) -> list[str]:
    return [str(item).strip() for item in values if str(item).strip()]


def _clean_step(value: str, *, default: str) -> str:
    allowed = {step["id"] for step in ONBOARDING_STEPS}
    text = str(value or "").strip()
    return text if text in allowed else default


def _require_workspace(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {root}")
    return root


def _state_path(root: Path) -> Path:
    return ProjectMemory(root).root / ONBOARDING_FILE


def _load_state(root: Path) -> dict[str, Any]:
    data = _read_json(root, ONBOARDING_FILE, {})
    return data if isinstance(data, dict) else {}


def _write_state(root: Path, state: dict[str, Any]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    _write_json(root, ONBOARDING_FILE, state)


def _read_json(root: Path, name: str, default: Any) -> Any:
    path = ProjectMemory(root).root / name
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(root: Path, name: str, data: Any) -> None:
    ProjectMemory(root).write_json(name, data)
