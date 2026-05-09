# Aegis Core

Aegis Core is the shared local-first runtime layer for the Auralith ecosystem.

It is meant to power:

- Auralith Desktop App
- Auralith Website client
- Aegis VS Code Extension
- Aegis Visual Studio Extension

This first pass is intentionally small. It consolidates common backend responsibilities into reusable service modules, a local FastAPI API, and an optional CLI. Client-specific UX stays in each client.

## What Core Owns

- Ollama model detection, health checks, routing defaults, fallback metadata, and local-first hybrid model route planning
- Workspace scanning, language/framework detection, file index, dependency graph, and symbol index
- Project memory files in `.aegis/`
- Roadmap generation from local scan data
- Autonomous task orchestration for large goals, stored as approval-gated local queues
- Specialized local agent roles for planning, architecture, coding, review, testing, repair, and documentation
- Validation command detection and safe opt-in execution
- Agent planning placeholders that propose next steps without applying edits
- Diagnostics and local logs
- Shared configuration defaults
- Versioned `/v1` API contracts for all Auralith clients
- Shared task, client, memory, diagnostics, and dashboard surfaces
- Cached workspace scans when file fingerprints are unchanged

## What Core Does Not Do Yet

- It does not replace the existing clients in one jump.
- It does not auto-edit files.
- It does not turn autonomy into uncontrolled file mutation; orchestration pauses for approval before edits and risky commands.
- It does not send data to cloud models unless a client explicitly approves a sanitized context plan.
- It does not store provider API keys in plaintext config files; optional provider keys must live in OS credential storage.
- It does not implement cloud accounts, licensing, or update infrastructure.
- It does not run destructive commands.

## CLI

From this folder:

```powershell
python -m aegis_core.cli health --workspace ..
python -m aegis_core.cli scan --workspace ..
python -m aegis_core.cli roadmap --workspace ..
python -m aegis_core.cli validate --workspace ..
python -m aegis_core.cli continue --workspace ..
python -m aegis_core.cli repair --workspace ..
python -m aegis_core.cli dashboard --workspace ..
python -m aegis_core.cli tasks --workspace ..
python -m aegis_core.cli providers --workspace ..
python -m aegis_core.cli agents --workspace ..
python -m aegis_core.cli route --workspace .. --task-type hard_debugging
python -m aegis_core.cli orchestrate --workspace .. --goal "Stabilize the extension packaging flow"
```

After installing the package, the same commands are available through:

```powershell
aegis scan --workspace <path>
aegis roadmap --workspace <path>
aegis validate --workspace <path>
aegis continue --workspace <path>
aegis repair --workspace <path>
aegis dashboard --workspace <path>
aegis tasks --workspace <path>
aegis providers --workspace <path>
aegis agents --workspace <path>
aegis route --workspace <path> --task-type code_completion
aegis orchestrate --workspace <path> --goal "Stabilize one workflow"
```

Validation is conservative. `aegis validate` detects commands. Add `--run` to execute the first safe detected command.

For machine-readable output, use `--json` before or after the subcommand:

```powershell
python -m aegis_core.cli --json dashboard --workspace ..
python -m aegis_core.cli dashboard --workspace .. --json
```

## API

Install dependencies, then run:

```powershell
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

Core API base URL:

```text
http://127.0.0.1:8788
```

Use the versioned client contract for new integrations:

```text
GET  /v1/health
GET  /v1/models
GET  /v1/providers
POST /v1/models/route
POST /v1/models/completions
GET  /v1/settings
POST /v1/workspaces/scan
POST /v1/workspaces/roadmap
GET  /v1/memory
GET  /v1/diagnostics
POST /v1/clients/register
GET  /v1/agents
GET  /v1/tasks
POST /v1/tasks
GET  /v1/orchestration
POST /v1/orchestration/plan
POST /v1/orchestration/step
GET  /v1/ecosystem/dashboard
```

See `docs/API_REFERENCE.md`.

## Hybrid Model Router

Aegis Core is local-first. The default routing mode is `local_only`, so normal chat, explanations, code completion, code review, roadmap generation, and smaller fixes stay on Ollama at `http://127.0.0.1:11434`.

Optional providers are exposed as route candidates only:

- OpenAI
- Anthropic
- Google
- OpenRouter
- LM Studio local server at `http://127.0.0.1:1234`

Cloud providers require all of the following before Core will call them:

- `model_routing_mode` set to `hybrid` or `cloud_allowed`
- the client requests cloud consideration
- the client confirms user approval after showing sanitized files/context
- a provider API key stored in OS credential storage

Core excludes secret-like, ignored, and outside-workspace files from cloud context and redacts secret-like lines before context is sent.

## Autonomous Task Orchestration

Core can turn a larger development goal into a local staged queue. The queue is intentionally supervised:

- Each goal records an objective, affected systems, required files, risk level, validation plan, rollback plan, and approval gates.
- Each queued task has one owner agent: Planner, Architect, Coder, Reviewer, Tester, Repair, or Documentation.
- Queue statuses are `pending`, `in_progress`, `blocked`, `needs_approval`, `validating`, `completed`, and `failed`.
- Each task moves through inspect, plan, propose changes, wait for approval, apply approved changes, validate, and summarize.
- Core records state and memory, but clients remain responsible for showing diffs/context and applying approved file edits.
- Validation commands only run after approval when the step involves build/test/lint execution.
- Agent decisions are appended to `agent-history.json` so clients can show who made each recommendation.

Orchestration state is written to `.aegis/orchestration-queue.json` and `.aegis/active-orchestration.json`. Progress updates `roadmap.md`, `decisions.md`, `validation-log.md`, and `agent-history.json`.

## Memory

Workspace-local memory lives under:

```text
.aegis/
```

Core writes generated files such as `project-summary.md`, `roadmap.md`, `file-index.json`, `dependency-graph.json`, `symbol-index.json`, `validation-log.md`, and `core-log.md`.

Shared ecosystem files include `clients.json` for connected client registrations, `tasks.json` for cross-client task visibility, `orchestration-queue.json` for staged autonomous goals, and `scan-cache.json` for faster repeated workspace scans.

## Migration Direction

Existing clients should migrate one responsibility at a time:

1. Use Aegis Core for Ollama model detection and health checks.
2. Use Core scanning and memory files instead of duplicating scanner logic.
3. Use Core roadmap and validation APIs.
4. Register each client through `/v1/clients/register`.
5. Show shared tasks, memory, diagnostics, and model status from `/v1/ecosystem/dashboard`.
6. Move agent planning and approval workflows onto Core API/CLI contracts.
7. Keep client-specific UI, editor APIs, and IDE build/error integrations in the clients.
