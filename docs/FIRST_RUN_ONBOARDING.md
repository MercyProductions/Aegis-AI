# First-Run Onboarding

Aegis now has a Core-owned first-run setup contract so every client can guide the same safe launch path instead of inventing separate setup checks. The Website shows the full setup surface, the Desktop runtime panel reports the same Core status, and the Website backend keeps compatibility fallback diagnostics when Core is offline.

## What The Wizard Checks

The Core onboarding status lives at:

```text
GET /v1/onboarding/status?workspace=<path>
```

It reports:

- setup steps: welcome, privacy, local models, provider linking, workspace, safety settings, theme, first workflow, finish
- environment diagnostics: Core, local API auth, workspace permissions, `.aegis` state, Ollama, installed models, provider linking, client sync, release recovery
- safe defaults: checkpoint before apply, validation before apply, approval required, auto-apply disabled
- recovery cards for Core offline, Ollama offline, provider missing, model unavailable, workspace blocked, update failed, and validation failed

Core stores progress under:

```text
<workspace>/.aegis/onboarding-state.json
```

Settings import history is stored under:

```text
<workspace>/.aegis/settings-import-history.json
```

Provider keys are never exported or imported through this flow.

## Phase 14 Recovery Contract

The alpha readiness contract (`evals/phase14-alpha-readiness-contract.json`) requires every client to preserve the same recovery state ids so first-run support can be compared across Core, Website, Desktop, VS Code, and Visual Studio:

- `backend_down`: Website compatibility gateway is unavailable or has not synced.
- `core_offline`: Core cannot be reached by a client.
- `ollama_offline`: local model server is unavailable.
- `model_unavailable`: selected model is missing or unreachable.
- `key_missing`: cloud provider key is not safely linked.
- `provider_missing`: cloud provider route is not configured.
- `workspace_blocked`: workspace or `.aegis` state is not writable.
- `update_failed`: release/update state needs recovery before continuing.
- `validation_failed`: validation failed and apply should remain blocked.
- `extension_disconnected`: VS Code or Visual Studio extension has not synced with Core.
- `desktop_blank_state`: Desktop has no usable workspace/runtime state.

## First Launch Flow

Phase 35 private-alpha handoff keeps the first launch path narrow: provider setup and local model setup are checked during onboarding, workspace selection should use a disposable or backed-up folder, and the guided workflow should stay validate-only until checkpoint and rollback visibility are confirmed.

1. Start Aegis Core on localhost:

```powershell
cd aegis-core
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

2. Start the Website backend/frontend:

```powershell
.\website\launch.ps1
```

3. Open the Website Setup section:

```text
/app/onboarding
```

4. Select a workspace and refresh diagnostics.

5. Choose a privacy posture:

- `local_only` for fully local Ollama-first work
- `hybrid` only after provider credentials are linked through the credential store
- cloud-disabled mode through `AEGIS_CLOUD_DISABLED=true` when no cloud calls should be allowed

6. Run the guided first workflow in validate-only mode.

## Guided First Workflow

Core exposes:

```text
POST /v1/onboarding/first-workflow
```

Supported actions:

- `scan_project`: index files, language mix, build files, and project metadata
- `generate_roadmap`: create a Core-owned roadmap preview or persisted roadmap
- `explain_architecture`: summarize architecture from workspace intelligence
- `propose_small_improvement`: prepare a low-risk proposal without applying files by default
- `validate_only`: detect and preview validation safely
- `checkpoint_rollback_demo`: show checkpoint/rollback readiness or create a real checkpoint when explicitly non-dry-run

The Website gateway keeps matching stable routes:

```text
GET  /api/onboarding/status
POST /api/onboarding
POST /api/onboarding/first-workflow
GET  /api/settings/export
POST /api/settings/import
```

If Core is offline, these routes return fallback diagnostics and keep apply-oriented first workflow steps disabled.

## Settings Import And Export

Core exports only safe metadata:

- privacy mode
- model routing metadata
- local runtime URLs
- UI preferences
- workspace preferences

Core imports only allowlisted config keys and UI preferences. API keys, token fields, and unknown keys are ignored. Use `dry_run: true` first to preview imported and ignored keys.

## Recovery Playbook

Core offline:

- Start Core on `127.0.0.1:8788`
- Check `/v1/health`
- Confirm `AEGIS_CORE_LOCAL_TOKEN` matches client configuration when token auth is enabled

Ollama offline:

- Install or start Ollama
- Pull at least one coding model
- Refresh model diagnostics from Setup or Models

No local models:

- Pull the configured default model
- Change `default_model` to an installed model
- Keep routing in `local_only` until local health passes

Provider missing:

- Keep local-only mode, or link provider credentials through the OS credential store
- Do not place provider keys in workspace config or import files

Workspace blocked:

- Choose an existing project folder
- Confirm the folder and `.aegis` are writable
- Avoid dependency, build-output, system, or credential folders as workspace roots

Update failed:

- Use release recovery before applying changes
- Restore the previous package if update state reports failure
- Collect release/update logs for the next pass

Validation failed:

- Keep the workflow in proposal mode
- Review validation output
- Start a repair workflow only after approval

## Client Responsibilities

Website:

- Shows the full setup command center and fallback diagnostics.
- Keeps existing `/api` routes stable while delegating to Core when available.

Desktop:

- Registers as a Core client and shows Core first-run status in the runtime panel and setup check modal.
- Keeps Website API fallback for runtime workflows that are not yet Core-backed.

VS Code and Visual Studio:

- Should consume the same Core onboarding status, diagnostics, provider health, and first workflow contracts.
- Should keep editor-specific safety UI for previews, approvals, validation, and rollback.

## Reset

To reset onboarding for one workspace, remove or edit:

```text
<workspace>/.aegis/onboarding-state.json
```

Do not delete provider credentials from project files because provider credentials should not live there. Use the provider account UI or OS credential manager for credential resets.
