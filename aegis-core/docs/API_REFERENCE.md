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

JavaScript package managers are script-aware: `npm`/`pnpm`/`yarn` test and build commands are listed only when matching `package.json` scripts exist.

Custom commands are still restricted to the built-in safe validation allow-list. Unsafe commands are logged as blocked and are not executed.

## POST /agent/continue

Body:

```json
{
  "workspace": "C:/path/to/project",
  "request": "optional task request"
}
```

Creates a plan-only continuation workflow from `.aegis/roadmap.md`. It does not edit files. If the roadmap path is missing or damaged, Core falls back to a safe default planning task instead of failing the request.

Writes:

- `.aegis/active-agent-plan.json`

## POST /agent/repair

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Creates a plan-only repair workflow from the latest validation log. It does not edit files. If the validation log is missing, unreadable, or damaged, Core returns a no-context repair response. Validation excerpts are scrubbed before being returned.

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

Core `/v1` is the shared runtime contract for Desktop, Website, VS Code, and Visual Studio. Website-specific product APIs stay under Website `/api`; when Website needs shared runtime state it should call Core through its read-only bridge (`GET /api/core-runtime`) and preserve these Core envelopes.

Shared request body conventions:

- Workspace operations use `workspace`.
- Website compatibility endpoints may accept `workspace_root` and translate it to Core `workspace`.
- Cross-client task records use `title`, `kind`, `source_client`, optional `request`, and optional `metadata`.
- Task status values are `planned`, `running`, `waiting_for_approval`, `blocked`, `completed`, `cancelled`, and `rolled_back`.
- Continue and repair endpoints are plan-only and never apply file edits.

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

Only known safe configuration keys are applied. The file written is `.aegis/config.json`. `memory_dir_name` is restricted to one workspace-local folder name; absolute paths, nested paths, and parent traversal fall back to `.aegis`.

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

Writes or updates `.aegis/clients.json`. If the shared memory root is not writable, returns `503` instead of reporting a registration that other clients cannot see.

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

Creates a shared task in `.aegis/tasks.json`. If the task cannot be persisted to shared memory, returns `503` instead of reporting a phantom task.

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

Returns `400` for unsupported statuses, `404` when the task ID does not exist, and `503` if the task update cannot be persisted to shared memory.

## POST /v1/validation

Detects validation commands or runs a requested safe command, matching `/validation` behavior.

## POST /v1/agent/continue

Creates a plan-only continuation workflow and a shared task. It does not apply edits. Damaged roadmap paths degrade to a safe default plan. If task persistence is unavailable, the response still includes the plan with `ok: false`, `task: null`, and a `memory_warning`.

## POST /v1/agent/repair

Creates a plan-only repair workflow from the latest validation log and a shared task when repair context exists. Missing or unreadable validation logs return a safe no-context response. If task persistence is unavailable, the response still includes the plan with `ok: false`, `task: null`, and a `memory_warning`.

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
