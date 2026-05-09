# API Reference

Base URL:

```text
http://127.0.0.1:8788
```

Start the server:

```powershell
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

## GET /health

Checks Core configuration and Ollama reachability.

Query:

- `workspace`: optional workspace path

Returns:

- workspace path
- effective config
- Ollama reachability
- installed models
- selected model
- missing default/fallback models

## GET /models

Returns Ollama model diagnostics for the selected workspace config.

## POST /workspace/scan

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Scans a workspace and writes:

- `.aegis/project-summary.md`
- `.aegis/architecture-map.md`
- `.aegis/file-index.json`
- `.aegis/dependency-graph.json`
- `.aegis/symbol-index.json`

## POST /workspace/roadmap

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Generates or updates `.aegis/roadmap.md` from scan data.

## POST /validation

Body:

```json
{
  "workspace": "C:/path/to/project",
  "run": false,
  "command": null
}
```

When `run` is false, returns detected validation commands.

When `run` is true, runs the provided command or first detected safe command and appends `.aegis/validation-log.md`.

## POST /agent/continue

Body:

```json
{
  "workspace": "C:/path/to/project",
  "request": "optional task request"
}
```

Creates a plan-only continuation workflow from `.aegis/roadmap.md`. It does not edit files.

Writes:

- `.aegis/active-agent-plan.json`

## POST /agent/repair

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Creates a plan-only repair workflow from the latest validation log. It does not edit files.

Writes:

- `.aegis/active-repair-plan.json`

## POST /config/init

Writes a default `.aegis/config.json` if one does not exist.

## Versioned Client API

New clients should use `/v1`. Responses are wrapped in this envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "kind": "memory.summary",
  "workspace": "C:/path/to/project",
  "data": {}
}
```

The unversioned endpoints above remain for migration compatibility.

## GET /v1/health

Query:

- `workspace`: optional workspace path

Returns the same health data as `/health` inside the standard envelope.

## GET /v1/models

Returns installed Ollama models, selected model, missing configured models, and latency.

## GET /v1/settings

Query:

- `workspace`: optional workspace path

Returns effective Core settings.

## POST /v1/settings

Body:

```json
{
  "workspace": "C:/path/to/project",
  "settings": {
    "default_model": "qwen3-coder:30b",
    "fallback_models": ["qwen2.5-coder:7b", "granite-code:8b"],
    "safety_mode": "strict"
  }
}
```

Only known safe configuration keys are applied. The file written is `.aegis/config.json`.

## POST /v1/workspaces/scan

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Scans and updates shared memory/index files.

## POST /v1/workspaces/roadmap

Generates or updates `.aegis/roadmap.md`.

## GET /v1/memory

Query:

- `workspace`: required workspace path

Returns shared memory file paths, existence flags, and short sanitized excerpts.

## GET /v1/diagnostics

Query:

- `workspace`: required workspace path

Returns sanitized tails of Core, extension, validation, and agent-history logs.

## GET /v1/branding

Returns shared Auralith/Aegis naming, colors, typography, terminology, and layout tokens.

## POST /v1/clients/register

Body:

```json
{
  "workspace": "C:/path/to/project",
  "client_id": "vscode-main",
  "client_type": "vscode-extension",
  "name": "Aegis Local Agent for VS Code",
  "version": "0.1.1",
  "capabilities": ["active-file", "diff-preview", "terminal-validation"]
}
```

Writes or updates `.aegis/clients.json`.

## GET /v1/clients

Query:

- `workspace`: required workspace path

Returns clients ordered by last seen time.

## POST /v1/tasks

Body:

```json
{
  "workspace": "C:/path/to/project",
  "title": "Continue roadmap item 1",
  "kind": "continue",
  "source_client": "vscode-extension",
  "request": "Continue from roadmap",
  "metadata": {
    "risk": "low"
  }
}
```

Creates a shared task in `.aegis/tasks.json`.

## GET /v1/tasks

Query:

- `workspace`: required workspace path
- `include_completed`: optional boolean, defaults to `true`

Returns cross-client tasks.

## POST /v1/tasks/{task_id}/status

Body:

```json
{
  "workspace": "C:/path/to/project",
  "status": "waiting_for_approval",
  "summary": "Diff is ready for user review."
}
```

Supported statuses: `planned`, `running`, `waiting_for_approval`, `blocked`, `completed`, `cancelled`, `rolled_back`.

Returns `400` for unsupported statuses and `404` when the task ID does not exist.

## POST /v1/validation

Detects validation commands or runs a requested safe command, matching `/validation` behavior.

## POST /v1/agent/continue

Creates a plan-only continuation workflow and a shared task. It does not apply edits.

## POST /v1/agent/repair

Creates a plan-only repair workflow from the latest validation log and a shared task when repair context exists.

## GET /v1/ecosystem/dashboard

Query:

- `workspace`: required workspace path

Returns dashboard data for the Desktop App:

- connected clients
- active projects
- active and recent tasks
- stale tasks older than 24 hours
- model status
- diagnostics
- roadmap excerpt
- validation command detection
- recent activity
- suggested recovery actions
- shared branding tokens
