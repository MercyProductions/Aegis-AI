# Client Migration Status

Last updated: 2026-05-09

Goal: migrate clients incrementally toward Aegis Core `/v1` as the shared runtime source of truth while keeping existing Website `/api`, local IDE behavior, and rollback paths intact.

## Migration Order

1. VS Code Extension - migrated to Core contracts for shared runtime reads/tasks; hardening pass complete.
2. Visual Studio Extension - partial Core integration hardened; broader migration not started.
3. Desktop App - partial Core integration hardened; broader migration not started.
4. Website backend/frontend - last; do not migrate until client hardening has more interactive coverage.

## VS Code Extension

Path: `vscode-plugins/aegis-local-autopilot`

### Migrated To Core First

| Workflow | Core endpoint | Fallback |
| --- | --- | --- |
| Health check | `GET /v1/health` | Health check continues with warning when Core is offline. |
| Model detection | `GET /v1/models` | Direct Ollama `/api/tags`. |
| Settings health | `GET /v1/settings` | Existing VS Code workspace/user settings. |
| Workspace scan metadata | `POST /v1/workspaces/scan` | Existing VS Code local scanner. |
| Project roadmap generation | `POST /v1/workspaces/roadmap` | Existing Ollama-generated roadmap flow. |
| Memory context | `GET /v1/memory` | Direct reads from local `.aegis` memory files. |
| Diagnostics health | `GET /v1/diagnostics` | VS Code diagnostics plus local extension log files. |
| Validation | `POST /v1/validation` | Existing local terminal validation runner. |
| Client registration | `POST /v1/clients/register` | Registration failure is logged and skipped. |
| Shared task records | `POST /v1/tasks`, `POST /v1/tasks/{task_id}/status` | Agent Mode continues without shared task sync. |

### Remaining Local Logic

- Prompt construction, focused file context, editor selection context, and diff preview.
- Proposal parsing, staged approval, safe apply, backup creation, and rollback.
- VS Code diagnostics collection from the active workspace.
- Local dependency graph and symbol index enrichment used by the extension UI.
- Direct Ollama chat calls for generation and repair prompts.
- The scratch TODO-roadmap command remains model/local-scan based.
- Extension storage, UI state, webview rendering, and command registration.

### Fallback Behavior

- Core offline during health check is a warning, not a hard failure.
- Model inventory falls back to direct Ollama with an output-channel warning.
- Core workspace scan failures fall back to the local scanner with an output-channel warning.
- Core roadmap failures show a clear warning and then use the existing local model roadmap path.
- Core memory failures fall back to `.aegis` file reads.
- Core validation failures to connect fall back to the local safe validation runner.
- Core task registration/update failures are logged and do not block Agent Mode.
- Core registration and task sync now require the expected `/v1` envelope kind and surface `ok: false` details instead of silently trusting any successful JSON response.

### Broken Workflows

- None found in compile/package validation.

### Validation Results

| Check | Result |
| --- | --- |
| VS Code compile | Passed: `npm run compile` |
| VS Code package | Passed: `npm run package`, produced `release/aegis-local-autopilot-0.1.1.vsix` |
| Core contract regression | Passed: `python -m pytest tests/test_core_contracts.py -q`, 51 tests |
| Live VS Code Core contract smoke | Passed against health, models, settings, workspace scan, roadmap, memory, diagnostics, validation, client registration, task create, and task status |

Issue found and fixed:

- Core validation on Windows detected `npm test` but could fail to launch `npm` because `subprocess.run(..., shell=False)` did not resolve the `npm.cmd` shim. Core now resolves Windows package-manager shims for `npm`, `pnpm`, and `yarn` before running safe validation commands.

Interactive IDE host workflows still need manual follow-up:

- command palette startup/activation
- health check UI rendering
- generate roadmap from the extension host
- propose/apply/rollback against a disposable workspace

## Visual Studio Extension

Status: partial Core integration hardened; broader migration not started.

Current Core use:

- `GET /v1/health`
- `POST /v1/clients/register`

Hardening completed:

- Health now validates the Core `/v1` envelope and expected `health` kind.
- Registration now validates the expected `client.registered` kind and treats `ok: false` as a surfaced warning.
- Existing runtime behavior still degrades to a health-check warning instead of blocking local Visual Studio workflows.

Validation results:

| Check | Result |
| --- | --- |
| VSIX build/package | Passed: `visual-studio-extensions/aegis-local-agent-vs/build.ps1`, produced `release/AegisLocalAgentVs.vsix` |

Planned next migration candidates:

- model/status read through `/v1/models`
- solution/workspace scan through `/v1/workspaces/scan`
- roadmap read/generation through `/v1/workspaces/roadmap`
- validation/build summary through `/v1/validation` where compatible
- diagnostics through `/v1/diagnostics`

## Desktop App

Status: partial Core integration hardened; broader migration not started.

Current Core use:

- `POST /v1/clients/register`
- `GET /v1/ecosystem/dashboard`

Hardening completed:

- Registration now validates the expected `client.registered` envelope before treating Core sync as successful.
- Dashboard reads now validate the expected `ecosystem.dashboard` envelope before parsing shared runtime status.
- Core offline still leaves the desktop usable through the Website backend and shows the Core dashboard as unavailable.

Validation results:

| Check | Result |
| --- | --- |
| Desktop build | Passed: `build.ps1`, produced `x64/Release/AegisChatBotDesktop.exe` |
| Desktop smoke, Core online | Passed with isolated app data and nonblank login/setup/dashboard captures |
| Desktop smoke, Core offline | Passed with isolated app data and nonblank login/setup/dashboard captures |

Planned migration candidates:

- explicit Core health/model status display from `/v1/health` and `/v1/models`
- shared task list actions through `/v1/tasks`
- shared diagnostics and memory panes through `/v1/diagnostics` and `/v1/memory`

## Website Backend/Frontend

Status: adapter layer only; migrate last. No website migration was performed during hardening.

Current Core bridge:

- `GET /api/core-runtime` reads Core health, models, settings, memory, diagnostics, and dashboard.

Hold until clients are stable:

- Website chat, routing, apply, checkpoint restore, project builder, auth/session, Creative Studio, and advanced product workflows.

Website migration safety:

- Not ready for the website migration phase yet. VS Code has the broadest Core coverage, but Visual Studio and Desktop still use only narrow Core surfaces.
- Next hardening should add interactive extension-host/manual workflow coverage for VS Code and Visual Studio before shifting Website `/api` behavior toward Core.
