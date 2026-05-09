# Installation Flow

This document defines the intended local-first setup path. It is not a full cloud installer implementation yet.

## Components

- Aegis Core local runtime
- Auralith Desktop App
- VS Code Extension
- Visual Studio Extension
- Website/download portal
- Ollama
- Recommended local models

The shared component manifest is:

```text
installer/aegis-components.json
```

## First-Run Flow

1. Install or locate Aegis Core.
2. Check whether Ollama is reachable at `http://127.0.0.1:11434`.
3. Detect installed models.
4. Recommend:
   - `qwen3-coder:30b`
   - `qwen2.5-coder:7b`
   - `granite-code:8b`
5. Create workspace `.aegis/config.json` only when a workspace is selected.
6. Run health check.
7. Register the launching client through `/v1/clients/register`.
8. Let the user choose whether to scan immediately.
9. Keep auto-scan disabled by default for large-project reliability.
10. Open the Desktop App dashboard from `/v1/ecosystem/dashboard` when available.

## Update Flow

Future updater should:

- stop Aegis Core cleanly
- preserve workspace `.aegis/` memory
- preserve backups
- install the new runtime
- run health check
- show release notes
- allow rollback to the prior runtime version
- re-register installed clients on next launch
- keep client packages and Core versioned independently

## Rollback Flow

Rollback should preserve:

- `.aegis/backups/`
- `decisions.md`
- `validation-log.md`
- `agent-history.json`

Rollback may regenerate:

- `file-index.json`
- `dependency-graph.json`
- `symbol-index.json`
- generated sections of `project-summary.md`
- generated sections of `architecture-map.md`
- generated sections of `roadmap.md`

## Dependency Setup

Minimal developer setup:

```powershell
cd aegis-core
python -m pip install -e .
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

Future installer setup:

- bundle or locate Python runtime
- install Aegis Core package into an isolated environment
- create a Start Menu/service launcher
- offer Ollama install guidance
- offer model pull actions
- install or update VS Code and Visual Studio VSIX packages when selected
- write shared Core URL defaults for participating clients

## Client Coordination

Default local URLs:

- Aegis Core: `http://127.0.0.1:8788`
- Ollama: `http://127.0.0.1:11434`

Clients should store only their UI-specific settings locally. Model, safety, indexing, validation, and backup preferences should be read from `/v1/settings` when Core is reachable.
