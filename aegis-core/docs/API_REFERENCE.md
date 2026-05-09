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
  "contract_version": "2026.05.09",
  "kind": "memory.summary",
  "workspace": "C:/path/to/project",
  "data": {},
  "stability": "stable",
  "deprecated": false,
  "deprecations": []
}
```

The unversioned endpoints above remain for migration compatibility.

Core `/v1` is the shared runtime contract for Desktop, Website, VS Code, and Visual Studio. Website-specific product APIs stay under Website `/api`; when Website needs shared runtime state it should call Core through its read-only bridge (`GET /api/core-runtime`) and preserve these Core envelopes.

The canonical schema package is `aegis_core.contracts`. It defines request models, the Core envelope, stable runtime data models, and schema-only experimental shapes for patch proposals and rollback results. Contract additions must be backwards compatible: clients may ignore unknown fields, and optional fields may be absent.

Contract stability:

| Contract kind | Stability | Notes |
| --- | --- | --- |
| `health`, `models`, `settings`, `settings.updated` | stable | Shared runtime status and configuration. |
| `model.providers`, `model.route`, `model.completion`, `provider.key.status` | experimental | Local-first hybrid model routing, provider inventory, gated completions, and OS credential status. |
| `workspace.scan`, `workspace.roadmap` | stable | Shared indexing and roadmap outputs. |
| `memory.summary`, `diagnostics.summary` | stable | Shared memory and diagnostics summaries. |
| `client.registered`, `clients.list` | stable | Cross-client registry. |
| `task.created`, `tasks.list`, `task.updated` | stable | Cross-client task record lifecycle. |
| `validation` | stable | Validation discovery/run shape. |
| `ecosystem.dashboard` | stable | Aggregated dashboard for Desktop and Website bridge. |
| `branding.tokens` | experimental | Visual/client token sharing may still change. |
| `agent.continue.plan`, `agent.repair.plan` | experimental | Plan-only agent contracts; no file edits are applied. |
| `orchestration.plan`, `orchestration.dashboard`, `orchestration.step` | experimental | Supervised autonomous goal queues with approval gates; Core does not blindly edit files. |
| `patch.proposal`, `rollback.entry`, `rollback.result` | experimental schema-only | Defined for future compatibility; not active Core endpoints yet. |

Shared request body conventions:

- Workspace operations use `workspace`.
- Website compatibility endpoints may accept `workspace_root` and translate it to Core `workspace`.
- Cross-client task records use `title`, `kind`, `source_client`, optional `request`, and optional `metadata`.
- Shared task status values are `planned`, `running`, `waiting_for_approval`, `pending`, `in_progress`, `needs_approval`, `validating`, `blocked`, `completed`, `failed`, `cancelled`, and `rolled_back`.
- Orchestration queue status values are `pending`, `in_progress`, `blocked`, `needs_approval`, `validating`, `completed`, and `failed`.
- Continue and repair endpoints are plan-only and never apply file edits.
- Orchestration endpoints plan, queue, validate, and update memory; clients still own diff display, approval UI, patch apply, and rollback execution.

## GET /v1/health

Query:

- `workspace`: optional workspace path

Returns the same health data as `/health` inside the standard envelope.

## GET /v1/models

Returns installed Ollama models, selected model, missing configured models, and latency.

## GET /v1/providers

Query:

- `workspace`: optional workspace path

Returns the hybrid provider inventory without secret values. Providers include local Ollama, local LM Studio, OpenAI, Anthropic, Google, and OpenRouter. Cloud providers report whether a key is present in OS credential storage; API keys are never returned.

Alias:

- `GET /v1/models/providers`

## POST /v1/models/route

Body:

```json
{
  "workspace": "C:/path/to/project",
  "task_type": "hard_debugging",
  "difficulty": "hard",
  "allow_cloud": false,
  "cloud_approved": false,
  "context_files": ["src/App.tsx", ".env"],
  "local_failure_reason": null,
  "provider_id": null,
  "model": null
}
```

Returns a route plan. Core selects Ollama/local models by default and marks cloud routes as `approval_required` until the client has shown warnings, visible sanitized context, and received explicit approval. Secret-like files, ignored directories, and outside-workspace paths are listed under `context.blocked_files` and are never sent to a provider by Core.

Task routing defaults:

| Task type | Default route |
| --- | --- |
| `simple_explanation` | small local model |
| `code_completion` | local coder model |
| `code_review`, `smaller_fix`, `chat` | default local model |
| `repo_wide_planning` | strongest configured local model; optional approved cloud fallback |
| `hard_debugging` | strongest configured local model; optional approved cloud fallback |
| `embeddings_search` | local embedding model |

## POST /v1/models/completions

Experimental gated completion endpoint. It uses the same route request fields plus:

```json
{
  "prompt": "Explain the failing test.",
  "timeout_seconds": 120
}
```

Cloud calls return `403` unless `allow_cloud` and `cloud_approved` are true, the Core routing mode allows cloud, and the provider has a key in OS credential storage. `local_only` mode blocks cloud calls even if the request asks for them.

## POST /v1/providers/{provider_id}/key

Body:

```json
{
  "api_key": "provider-secret"
}
```

Stores a provider API key in OS credential storage and returns only key status. Core does not write provider secrets to `.aegis/config.json`.

Supported cloud provider ids:

- `openai`
- `anthropic`
- `google`
- `openrouter`

## DELETE /v1/providers/{provider_id}/key

Deletes the provider API key from OS credential storage when available.

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
    "model_routing_mode": "local_only",
    "default_model": "qwen3-coder:30b",
    "default_local_model": "qwen3-coder:30b",
    "local_small_model": "qwen2.5-coder:7b",
    "local_coder_model": "qwen3-coder:30b",
    "local_embedding_model": "nomic-embed-text",
    "preferred_cloud_provider": "openai",
    "preferred_cloud_model": "gpt-4.1",
    "lm_studio_url": "http://127.0.0.1:1234",
    "fallback_models": ["qwen2.5-coder:7b", "granite-code:8b"],
    "max_context_chars": 62000,
    "cloud_cost_warnings": true,
    "safety_mode": "strict"
  }
}
```

Only known safe configuration keys are applied. The file written is `.aegis/config.json`. `model_routing_mode` is restricted to `local_only`, `hybrid`, or `cloud_allowed`. URL settings are normalized to base HTTP(S) origins and reject credentials. `memory_dir_name` is restricted to one workspace-local folder name; absolute paths, nested paths, and parent traversal fall back to `.aegis`.

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

Supported statuses: `planned`, `running`, `waiting_for_approval`, `pending`, `in_progress`, `needs_approval`, `validating`, `blocked`, `completed`, `failed`, `cancelled`, `rolled_back`.

Returns `400` for unsupported statuses, `404` when the task ID does not exist, and `503` if the task update cannot be persisted to shared memory.

## POST /v1/orchestration/plan

Body:

```json
{
  "workspace": "C:/path/to/project",
  "goal": "Stabilize the VS Code packaging workflow",
  "source_client": "vscode-extension",
  "context_files": ["package.json", ".env"]
}
```

Creates `.aegis/orchestration-queue.json` and `.aegis/active-orchestration.json`, then returns an orchestration dashboard envelope. The plan includes:

- objective
- task breakdown
- affected systems
- risk level
- required files
- blocked context files
- approval gates
- validation plan
- rollback plan

Secret-like, ignored, unreadable, and outside-workspace context files are listed under `plan.blocked_context`.

## GET /v1/orchestration

Query:

- `workspace`: required workspace path

Returns UI-ready orchestration state:

- current goal
- task list
- active task and active step
- pending approvals
- validation results
- rollback option/checkpoint metadata
- safety summary

## POST /v1/orchestration/step

Body:

```json
{
  "workspace": "C:/path/to/project",
  "task_id": "orch-task-123",
  "action": "validate",
  "approval": true,
  "summary": "Validation approved by user.",
  "affected_files": ["src/app.ts"],
  "validation_command": ["npm", "test"]
}
```

Supported actions include `inspect`, `plan`, `propose`, `approve`, `apply`, `validate`, `complete`, `block`, and `fail`.

Approval behavior:

- `propose` moves risky tasks to `needs_approval`.
- `apply` does not proceed past approval gates unless `approval: true` or a previous approval is recorded.
- `validate` requires `approval: true` when a build/test/lint command gate is attached.
- Core records approved progress and validation output but does not apply arbitrary file edits itself.

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
