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
- Workspace scanning, language/framework detection, file index, dependency graph, and symbol index, including C#, F#, and Visual Basic .NET project files
- Project memory files in `.aegis/`
- Auralith personal intelligence memory for user/workspace preferences, project continuity, workflow patterns, validation/repair history, editable lifecycle controls, privacy controls, export/import, and orchestration context
- Roadmap generation from local scan data
- Autonomous task orchestration for large goals, stored as approval-gated local queues
- Unified workflow graph runtime for long-running engineering workflows across Desktop, Website, VS Code, and Visual Studio
- Core-owned engineering execution pipeline for intake, workspace analysis, planning, task decomposition, implementation tracking, validation, bounded repair, review, approval, checkpoint, apply, and completion summary
- Shared client synchronization for active clients, active workflows, operation feeds, and workspace activity
- Event streaming for workflow/task/validation/repair/orchestration updates
- Specialized local agent roles for planning, architecture, coding, review, testing, repair, and documentation
- Safe scheduled and trigger-based maintenance jobs for scans, reports, roadmap refreshes, TODO review, documentation drift, and validation status
- Project health scoring, trend tracking, risk detection, and quality reports
- Persistent workspace knowledge graph for files, folders, modules, classes, functions, methods, APIs, imports/includes, dependencies, services, workflows, build systems, configs, databases, runtime boundaries, project memory, semantic summaries, and historical relationships
- Validation command detection and safe opt-in execution
- Core-owned first-run onboarding status, environment diagnostics, recovery cards, safe settings import/export, and validate-only guided first workflow contracts
- Permission-scoped plugin runtime discovery, manifest validation, enable/disable state, tool contracts, workflow/analyzer/UI extension hooks, observability, and reference plugins
- Local-first distributed runtime node registry, trust classification, workload scheduling, audit, observability, recovery, and worker bootstrap contracts
- Core-owned editing runtime for proposed file changes, patch preview metadata, selected/all apply, mandatory checkpoints, checkpoint restore, validation result storage, operation jobs, and project activity
- Shared workspace intelligence runtime for file indexes, semantic summaries, project metadata, framework/build/dependency detection, quality signals, knowledge graph summaries, validation plans, and generated memory artifacts
- Formal multi-agent engineering runtime with deterministic roles, scoped memory, model routing profiles, task ownership, handoffs, supervision, and structured communication
- Diagnostics and local logs
- Shared configuration defaults
- Versioned `/v1` API contracts for all Auralith clients
- Shared task, client, memory, diagnostics, and dashboard surfaces
- Cached workspace scans when file fingerprints are unchanged

## What Core Does Not Do Yet

- It does not replace the existing clients in one jump.
- It does not turn autonomy into uncontrolled file mutation; editing endpoints require explicit client calls, reject unsafe paths, checkpoint before writes, and support dry runs.
- It does not replace Website/Desktop/IDE UX in one jump; those clients should delegate runtime operations to Core while keeping approval UI, editor affordances, and user-facing review flows.
- It does not create hidden autonomous edits; engineering executions remain inspectable, approval-based, checkpointed, journaled, and reversible.
- It does not run scheduled jobs as a hidden daemon; clients or a local host invoke due or trigger-based jobs explicitly.
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
python -m aegis_core.cli jobs --workspace ..
python -m aegis_core.cli jobs --workspace .. --run daily-project-scan
python -m aegis_core.cli quality --workspace .. --record
python -m aegis_core.cli knowledge --workspace .. --record
python -m aegis_core.cli knowledge --workspace .. --query "What systems depend on aegis-core/aegis_core/server.py?"
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
aegis jobs --workspace <path>
aegis jobs --workspace <path> --trigger project_opened
aegis quality --workspace <path> --record
aegis knowledge --workspace <path> --record
aegis knowledge --workspace <path> --query "What areas of the project are most unstable?"
aegis route --workspace <path> --task-type code_completion
aegis orchestrate --workspace <path> --goal "Stabilize one workflow"
```

Validation is conservative. `aegis validate` detects commands. Add `--run` to execute the first safe detected command. Custom validation commands must use bare safe tool names or normal `.cmd`/`.exe` shims; path-qualified wrappers and `.bat` aliases are blocked before execution.

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
GET  /v1/release/manifest
POST /v1/release/compatibility
GET  /v1/release/migrations
POST /v1/release/migrations/run
POST /v1/release/update-plan
GET  /v1/models
GET  /v1/models/registry
GET  /v1/models/routing-profiles
GET  /v1/providers
POST /v1/models/route
POST /v1/models/completions
GET  /v1/settings
POST /v1/workspaces/scan
POST /v1/workspaces/roadmap
GET  /v1/memory
GET  /v1/personal-memory
POST /v1/personal-memory/query
POST /v1/personal-memory
POST /v1/personal-memory/records/{memory_id}
POST /v1/personal-memory/records/{memory_id}/archive
POST /v1/personal-memory/records/{memory_id}/delete
POST /v1/personal-memory/export
POST /v1/personal-memory/import
POST /v1/personal-memory/controls
POST /v1/personal-memory/cleanup
GET  /v1/personal-memory/observability
POST /v1/personal-memory/context
GET  /v1/diagnostics
POST /v1/clients/register
GET  /v1/agents
GET  /v1/agents/runtime
GET  /v1/tasks
POST /v1/tasks
GET  /v1/orchestration
POST /v1/orchestration/plan
POST /v1/orchestration/step
GET  /v1/jobs
POST /v1/jobs/run
GET  /v1/jobs/{job_id}
GET  /v1/distributed-runtime
GET  /v1/distributed-runtime/nodes
POST /v1/distributed-runtime/nodes/register
POST /v1/distributed-runtime/nodes/{node_id}/heartbeat
POST /v1/distributed-runtime/nodes/{node_id}/revoke
GET  /v1/distributed-runtime/workloads
POST /v1/distributed-runtime/workloads
GET  /v1/distributed-runtime/workloads/{workload_id}
POST /v1/distributed-runtime/workloads/{workload_id}/dispatch
POST /v1/distributed-runtime/workloads/{workload_id}/retry
POST /v1/distributed-runtime/workloads/{workload_id}/cancel
POST /v1/distributed-runtime/dispatch
POST /v1/distributed-runtime/recover
GET  /v1/distributed-runtime/observability
GET  /v1/distributed-runtime/audit
GET  /v1/distributed-runtime/deployment/bootstrap
POST /v1/changes/propose
POST /v1/changes/apply
POST /v1/checkpoints/create
GET  /v1/checkpoints
POST /v1/checkpoints/restore
POST /v1/validation/run
GET  /v1/projects/{project_id}/activity
POST /v1/workspaces/intelligence
POST /v1/workflows
GET  /v1/workflows
GET  /v1/workflows/stats
GET  /v1/workflows/agent-runtime
GET  /v1/engineering/modes
POST /v1/engineering/executions
GET  /v1/engineering/executions
GET  /v1/engineering/executions/{execution_id}
POST /v1/engineering/executions/{execution_id}/step
GET  /v1/engineering/executions/{execution_id}/timeline
GET  /v1/engineering/memory
POST /v1/engineering/memory
GET  /v1/engineering/metrics
POST /v1/engineering/roadmap/execute
GET  /v1/workflows/events
GET  /v1/workflows/{workflow_id}
GET  /v1/workflows/{workflow_id}/agents
POST /v1/workflows/{workflow_id}/agents/delegate
POST /v1/workflows/{workflow_id}/step
POST /v1/workflows/{workflow_id}/pause
POST /v1/workflows/{workflow_id}/resume
POST /v1/workflows/{workflow_id}/cancel
POST /v1/workflows/{workflow_id}/retry
GET  /v1/workflows/{workflow_id}/events
POST /v1/clients/sync
GET  /v1/client-sync
GET  /v1/quality
POST /v1/quality/snapshot
GET  /v1/knowledge/graph
POST /v1/knowledge/graph
POST /v1/knowledge/query
POST /v1/knowledge/search
POST /v1/knowledge/relationships
POST /v1/knowledge/symbol
POST /v1/knowledge/impact-analysis
GET  /v1/knowledge/architecture-summary
GET  /v1/ecosystem/dashboard
```

See `docs/API_REFERENCE.md`.

## Release Authority

Aegis Core now exposes the ecosystem release contract. `VERSION.json` defines component versions, package names, minimum compatible clients, and update safety policy. Core serves the manifest, client compatibility checks, workspace migration status, and an inspectable update plan through `/v1/release/*`. State migrations write only under `.aegis` and are dry-run capable.

The Website backend mirrors release status for UI/API consumers, while Desktop, VS Code, and Visual Studio report their client version and schema support directly to Core. Packaging and rollback details live in `../docs/RELEASE_PACKAGING_AND_UPDATES.md`.

## Core Model Registry And Router

Aegis Core is now the shared source of truth for model/provider discovery, provider status, routing profiles, capability metadata, and route explanations. The default routing mode remains `local_only`, so normal chat, explanations, code completion, code review, roadmap generation, and smaller fixes stay on Ollama at `http://127.0.0.1:11434` unless a client asks for an approved cloud route.

`GET /v1/models/registry` returns the Core-owned registry contract:

- provider and model IDs, display names, local/cloud type, context window, tool/vision support, code/reasoning strength, latency/cost estimates, privacy level, availability, required auth method, last health check, and supported workflow types
- normalized provider account status: linked/unlinked, key present/missing, auth method availability, reachability, rate-limit/error state, and last successful request metadata when known
- routing profiles such as `local_only`, `balanced`, `fastest`, `cheapest`, `best_coding`, `best_reasoning`, `private_sensitive`, `creative_media`, and `fallback_safe`

Optional providers are exposed as inspectable route candidates:

- Ollama
- LM Studio local server at `http://127.0.0.1:1234`
- OpenAI
- Anthropic
- Google Gemini
- OpenRouter
- Azure OpenAI
- Amazon Bedrock
- Vertex AI

`POST /v1/models/route` chooses the model for a workflow and explains the choice: selected provider/model, reason selected, fallback chain, privacy risk, expected capability fit, missing capability warnings, and provider health. Clients should call this endpoint instead of duplicating route policy decisions.

Cloud providers require all of the following before Core will execute a completion:

- `model_routing_mode` set to `hybrid` or `cloud_allowed`
- the client requests cloud consideration
- the client confirms user approval after showing sanitized files/context
- a supported auth method, such as an API key stored in OS credential storage or a configured environment/profile provider

Core excludes secret-like, ignored, and outside-workspace files from cloud context and redacts secret-like lines before context is sent.

## Auralith Memory And Personal Intelligence

Core now owns the persistent personal intelligence memory layer used by orchestration, agents, Website compatibility routes, and future Desktop memory views. Records live under each workspace in `.aegis/auralith-memory.json`, with audit events in `.aegis/auralith-memory-audit.jsonl`.

The memory system is local-first and user-controlled. It supports user preferences, workspace preferences, project memory, execution history, repair history, validation history, roadmap history, architecture notes, workflow patterns, and UI preferences. Every record can be created, updated, archived, deleted, exported, imported, pinned, expired, and excluded from orchestration by category.

`POST /v1/personal-memory/context` gives workflows a bounded, task-relevant memory snapshot. Memory is advisory only: it can improve planning, validation choices, repair strategy selection, and routing defaults, but it never bypasses approvals, checkpoints, quality gates, or workspace safety rules.

Privacy controls expose local-only mode, per-project isolation, sensitive-memory redaction, disabled categories, category retention, and optional encrypted-storage readiness. Current JSON storage remains inspectable; encrypted storage is reported as active only when an encryption key/provider is configured.

The Website `/api/memory` route delegates to these Core contracts when available and keeps the old response shape for Website/Desktop clients. If Core is offline, Website falls back to its legacy `MemoryManager` files.

See `../docs/AURALITH_MEMORY_AND_PERSONAL_INTELLIGENCE.md`.

## Engineering Execution Pipeline

Core now exposes a formal engineering execution runtime for supervised autonomous engineering. It is not a code-writing black box. It creates an inspectable plan, decomposes work into dependency-aware stages, stores reusable workspace memory under `.aegis`, records prompts/models/files/validation/repair/approval/rollback signals in a journal, and routes all mutation through the Core editing runtime.

Pipeline stages are:

- intake
- workspace analysis
- planning
- task decomposition
- implementation
- validation
- repair
- review
- approval
- checkpoint
- apply
- completion summary

Checkpoint intentionally runs before apply in Core, even though clients may present approval/apply together in UI. Safety controls require normalized workspace-local paths, restricted directory checks, binary-file protection, max file modification limits, dry-run/diff preview support, validation records, and rollback availability.

Execution modes:

- `safe_assisted`
- `approval_every_step`
- `semi_autonomous`
- `autonomous_validate_only`
- `roadmap_execution`
- `repair_only`

State is stored in `.aegis/engineering-executions.json`, `.aegis/engineering-events.json`, `.aegis/engineering-journal.json`, `.aegis/engineering-memory.json`, and `.aegis/engineering-audit.md`. Clients should use `/v1/engineering/executions`, `/v1/engineering/executions/{execution_id}/step`, `/v1/engineering/memory`, and `/v1/engineering/metrics` for future autonomous engineering UI instead of duplicating execution plans locally.

## Workspace Knowledge Graph

Core persists deep project understanding in `.aegis/knowledge-graph.json`, `.aegis/knowledge-index-state.json`, `.aegis/semantic-index.json`, and `.aegis/project-memory.json`.

The graph is designed for dependency-aware edits and multi-session continuity. It tracks symbols, folders/modules, runtime boundaries, config/build systems, API providers/consumers, imports/includes, calls, inheritance, route bindings, validation failures, repaired issues, roadmap items, decisions, and previous workflow outcomes.

Use these APIs for client integration:

- `POST /v1/knowledge/search`
- `POST /v1/knowledge/relationships`
- `POST /v1/knowledge/symbol`
- `POST /v1/knowledge/impact-analysis`
- `GET /v1/knowledge/architecture-summary`

The graph supports incremental indexing metadata. When persisted fingerprints are unchanged, Core returns the cached graph. When files change, Core reports changed files, removed files, invalidated nodes, stale-node count, indexing duration, graph size, symbol counts, failures, and unsupported language areas. See `docs/WORKSPACE_KNOWLEDGE_GRAPH.md`.

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

## Workflow Automation

Core exposes safe maintenance jobs through `/v1/jobs`, `POST /v1/jobs/run`, and `aegis jobs`.

Default jobs cover daily project scans, weekly roadmap updates, dependency review, build health checks, stale TODO scans, documentation drift checks, recent-change summaries, broken-reference checks, project health reports, quality intelligence snapshots, next-best-task suggestions, and validation status checks.

Jobs may automatically scan, summarize, report, recommend, and write generated `.aegis` memory/log files. They still require approval before editing project files, deleting files, installing packages, running build/test/lint commands, or sending context to cloud models. Job history is appended to `.aegis/jobs-log.md`.

## Core-Owned Editing Runtime

Core now owns the first shared editing contract for all clients. Website, Desktop, VS Code, and Visual Studio can continue using their existing flows, but the migration target is:

1. Clients ask Core to record proposed changes with `POST /v1/changes/propose`.
2. Clients show Core preview metadata and collect user approval in their own UI.
3. Clients call `POST /v1/changes/apply` for selected or all approved changes.
4. Core creates a checkpoint before writing, stores operation jobs, logs activity, and records task IDs.
5. Clients use `GET /v1/checkpoints`, `POST /v1/checkpoints/restore`, `POST /v1/validation/run`, `GET /v1/jobs/{job_id}`, and `GET /v1/projects/{project_id}/activity` for shared rollback, validation, progress, and audit state.

Editing state is workspace-local under `.aegis/`: proposals in `editing-proposals.json`, operation jobs in `operation-jobs.json`, activity in `editing-activity.json`, validation runs in `validation-results.json`, checkpoints in `.aegis/checkpoints/`, and operation notes in `editing-log.md`.

This layer is intentionally conservative. It rejects outside-workspace, ignored, hidden-directory, dependency/generated, and secret-like paths; limits write size; supports dry runs; and never overwrites or deletes a file without a checkpoint.

## Unified Workflow Runtime

Core now has an additive workflow graph runtime for long-running cross-client work. It does not replace the older `/v1/orchestration/*` plan queue or the Website backend yet; it gives every client a common execution authority to migrate toward.

Supported workflow types:

- `chat_request`
- `generate_feature`
- `validate_project`
- `repair_project`
- `continue_roadmap`
- `build_project`
- `scan_workspace`
- `benchmark_models`
- `generate_media`
- `research_task`

Each workflow stores parent/child task relationships, dependency chains, retries, cancellation, pause/resume state, execution status, progress, timestamps, structured logs, safety controls, timelines, and metrics in `.aegis/workflow-runtime.json`. Event history is written to `.aegis/workflow-events.json`; client sync state is written to `.aegis/client-sync.json`; audit history is appended to `.aegis/workflow-audit.md`.

The formal internal agent layer is deterministic and inspectable:

- `planner_agent`
- `coder_agent`
- `validator_agent`
- `repair_agent`
- `researcher_agent`
- `summarizer_agent`
- `architecture_agent`
- `routing_agent`

Each agent stores role, capabilities, supported workflow types, preferred model profile, execution limits, memory scope, task ownership, status, structured messages, and execution history. Agents are task owners and logging boundaries. They do not secretly mutate files, recursively spawn more agents, or call providers. File changes flow through the Core editing runtime, validation through approved Core validation steps, model/provider selection through Core routing profiles, and provider/media/research work remains waiting for explicit client/user approval or supplied results.

`GET /v1/workflows/{workflow_id}/agents` returns active agents, handoff chains, dependency graphs, context snapshots, structured communication, observability, supervision state, and safety controls. `POST /v1/workflows/{workflow_id}/agents/delegate` records approval-aware task ownership handoffs.

See `docs/AGENT_RUNTIME.md`.

Clients can subscribe to workflow events with `GET /v1/workflows/{workflow_id}/events` or `GET /v1/workflows/events` using server-sent events. The stream includes workflow updates, task completion, validation progress, repair status, and orchestration events from persisted Core state.

## Quality Intelligence

Core exposes project health through `/v1/quality`, `POST /v1/quality/snapshot`, and `aegis quality`.

Quality snapshots track build/test/lint status, TODO count, known bugs, dependency drift, complexity hotspots, failing files, stale documentation, repeated repair attempts, model failures, large risky diffs, and files that change most often. Recorded snapshots are stored in `.aegis/health-history.json` and generate `.aegis/daily-health-report.md` plus `.aegis/weekly-quality-summary.md`.

Planner Agent reads the quality dashboard when creating an orchestration plan, so broken validation, repeated failures, untested areas, and high-risk files can influence task order and warnings.

## Knowledge Graph

Core exposes semantic project understanding through `/v1/knowledge/graph`, `POST /v1/knowledge/graph`, `/v1/knowledge/query`, and `aegis knowledge`.

The graph links files, symbols, systems, APIs, UI components, services, tasks, roadmap items, architecture decisions, known issues, validation failures, risks, and agent-history events. Relationship types include `uses`, `depends_on`, `calls`, `implements`, `breaks`, `related_to`, `tested_by`, and `mentioned_in_roadmap`.

Recorded graphs are written to `.aegis/knowledge-graph.json` and `.aegis/knowledge-summary.md`. Query support is deterministic and local: it answers relationship questions from graph evidence rather than sending project context to a model.

Planner Agent reads graph summaries while creating orchestration plans so impacted systems, related decisions/issues, and suggested context files can influence task order and risk.

## Memory

Workspace-local memory lives under:

```text
.aegis/
```

Core writes generated files such as `project-summary.md`, `roadmap.md`, `daily-health-report.md`, `weekly-quality-summary.md`, `knowledge-summary.md`, `file-index.json`, `dependency-graph.json`, `symbol-index.json`, `validation-log.md`, `jobs-log.md`, and `core-log.md`.

Shared ecosystem files include `clients.json` for connected client registrations, `tasks.json` for cross-client task visibility, `health-history.json` for quality trends, `knowledge-graph.json` for semantic project relationships, `jobs-state.json` for maintenance job state, `orchestration-queue.json` for staged autonomous goals, and `scan-cache.json` for faster repeated workspace scans.

## Migration Direction

Existing clients should migrate one responsibility at a time:

1. Use Aegis Core for Ollama model detection and health checks.
2. Use Core scanning and memory files instead of duplicating scanner logic.
3. Use Core roadmap and validation APIs.
4. Register each client through `/v1/clients/register`.
5. Show shared tasks, memory, diagnostics, and model status from `/v1/ecosystem/dashboard`.
6. Delegate proposed changes, apply, checkpoint, restore, validation run records, operation jobs, and project activity to the Core-owned editing runtime.
7. Move active engineering work onto Core workflows and client sync so Desktop, Website, VS Code, and Visual Studio share the same workflow IDs, task graph, progress, logs, events, and audit history.
8. Move agent planning and approval workflows onto Core API/CLI contracts.
9. Keep client-specific UI, editor APIs, and IDE build/error integrations in the clients.
