# API Reference

Base URL:

```text
http://127.0.0.1:8788
```

Start the server:

```powershell
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

Core is localhost-only by default. Set `AEGIS_CORE_LOCAL_TOKEN` to require `Authorization: Bearer <token>` or `X-Aegis-Local-Token` on Core requests.

## Security And Trust Contracts

```text
GET /v1/security/status
```

Returns local API guardrails, token enforcement state, origin/request limits, workspace edit protections, provider credential policy, privacy mode, update trust policy, and audit log location. Security events are written to `<workspace>/.aegis/security-audit.jsonl`.

## Release And Update Contracts

Core owns release metadata for the local ecosystem.

```text
GET  /v1/release/manifest
POST /v1/release/compatibility
GET  /v1/release/migrations
POST /v1/release/migrations/run
POST /v1/release/update-plan
```

Compatibility request:

```json
{
  "workspace": "C:/path/to/project",
  "client_type": "desktop",
  "client_version": "0.2.0",
  "schema_version": "2026.05.12",
  "capabilities": ["release-compatibility"]
}
```

Migration state is written under `.aegis` and supports dry-run mode. Update plans are inspectable and include checksum, optional signature, backup, apply, smoke check, and rollback steps; the actual package movement is handled by `scripts/aegis-update.ps1`.

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

JavaScript package managers are script-aware: safe `npm`/`pnpm`/`yarn`/`bun` test, lint, typecheck, and build commands are listed only when matching `package.json` scripts exist. Root `build.ps1` guard scripts are listed before lower-level CMake/.NET fallbacks and are constrained to an exact no-profile PowerShell invocation. Visual Studio solution files are treated as .NET validation targets only when they reference `.csproj`, `.fsproj`, or `.vbproj` projects; native C++ `.vcxproj` solutions are not mislabeled as `dotnet build`. Nested subprojects with their own manifests or solution files are treated as validation boundaries so their project files do not leak commands into parent ecosystem workspaces.

Custom commands are still restricted to the built-in safe validation allow-list. Bare tool names and normal `.cmd`/`.exe` shims are accepted for known safe commands, but path-qualified wrappers and `.bat` aliases are blocked so workspace-local executables cannot masquerade as trusted validation tools. Unsafe commands are logged as blocked and are not executed.

## Auralith Intelligence Stack

The Intelligence Stack is Core's local-first layer for specialized engineering intelligence. It manages specialized model lifecycle metadata, retrieval/indexing, workflow-aware routing, lightweight orchestration prediction, local benchmark history, privacy-aware dataset foundations, and distributed inference plans.

```text
GET  /v1/intelligence-stack
POST /v1/intelligence-stack
GET  /v1/intelligence-stack/models
POST /v1/intelligence-stack/models
POST /v1/intelligence-stack/retrieval/index
POST /v1/intelligence-stack/route
POST /v1/intelligence-stack/predict
POST /v1/intelligence-stack/benchmarks/run
GET  /v1/intelligence-stack/benchmarks
POST /v1/intelligence-stack/datasets
POST /v1/intelligence-stack/distributed-inference/plan
```

Model lifecycle requests can `list`, `register`, `archive`, record benchmark metadata, or return a non-executing `plan_install`. Retrieval uses local deterministic hash embeddings plus the knowledge graph today and is ready for future local embedding providers. Distributed inference planning creates supervised `model_inference` workloads while local Core remains the authority for approvals, checkpoints, state, and fallback.

## Deep Engineering Intelligence

Core exposes a deterministic engineering intelligence layer that combines workspace scan data, the knowledge graph, quality gates, validation history, repair memory, roadmap state, and workflow profiles. It improves context assembly, architecture reasoning, validation targeting, repair planning, roadmap ordering, workflow prediction, and benchmark tracking without running commands or editing source files.

```text
GET  /v1/engineering-intelligence
POST /v1/engineering-intelligence/analyze
POST /v1/engineering-intelligence/context
POST /v1/engineering-intelligence/validation-plan
POST /v1/engineering-intelligence/repair-plan
POST /v1/engineering-intelligence/roadmap-plan
POST /v1/engineering-intelligence/predict
POST /v1/engineering-intelligence/benchmarks/run
GET  /v1/engineering-intelligence/benchmarks
```

Analyze request:

```json
{
  "workspace": "C:/path/to/project",
  "workflow_type": "generate_feature",
  "objective": "Add user filtering with safe validation",
  "target_files": ["src/apiClient.ts", "backend/app.py"],
  "focus": "user API runtime boundary",
  "token_budget": 24000,
  "latest_validation": {},
  "refresh": false,
  "persist": true
}
```

Responses include architecture reasoning, selected/excluded context, validation priorities, repair strategy, roadmap decomposition, workflow risk prediction, memory relevance, benchmark scores, and explainability decisions. When persisted, Core writes generated `.aegis/engineering-intelligence.json`, `.aegis/engineering-context-assembly.json`, and `.aegis/engineering-intelligence-benchmarks.json`.

## Autopilot Runtime Contracts

Autopilot is the supervised autonomous engineering runtime. It coordinates Core engineering executions, agents, validation, repair, terminal jobs, checkpoints, rollback state, memory, and replay logs.

```text
GET  /v1/autopilot/modes
POST /v1/autopilot/start
GET  /v1/autopilot/runs
GET  /v1/autopilot/runs/{autopilot_id}
POST /v1/autopilot/runs/{autopilot_id}/action
GET  /v1/autopilot/runs/{autopilot_id}/replay
GET  /v1/autopilot/supervision
GET  /v1/autopilot/observability
GET  /v1/autopilot/memory
GET  /v1/autopilot/client-hooks
```

Autopilot run, supervision, observability, and replay payloads include trust-oriented fields:

- `trust_scorecard`
- `confidence_score`
- `validation_confidence`
- `repair_confidence`
- `regression_risk`
- `rollback_readiness`
- `predictions`
- `validation_intelligence`
- `deep_engineering_intelligence`
- `checkpoint_intelligence`
- `bounded_autonomy`
- `explanations`
- `decision_log`
- `specialization`
- `execution_strategy`
- `validation_strategy`
- `repair_strategy`
- `model_routing`
- `memory_scope`
- `specialization_benchmarks`

Use `POST /v1/autopilot/runs/{autopilot_id}/action` with `{"action": "simulate"}` for a dry-run workflow preview. Simulation never applies changes or executes commands.

Start request:

```json
{
  "workspace": "C:/path/to/project",
  "objective": "Implement the next roadmap item safely",
  "mode": "semi_autonomous",
  "workflow_type": "generate_feature",
  "specialization": "feature_autopilot",
  "target_files": ["src/app.py"],
  "constraints": ["Create checkpoint before apply"],
  "validation_commands": [{"command": ["python", "-m", "pytest"]}],
  "client_id": "desktop"
}
```

`specialization` is optional. When omitted, Core infers one of `feature_autopilot`, `repair_autopilot`, `refactor_autopilot`, `deployment_autopilot`, or `workspace_intelligence_autopilot` from workflow type, objective, target files, roadmap context, and metadata. `GET /v1/autopilot/modes` returns the specialization contracts and their validation/repair/routing/benchmark strategies.

Actions include `advance`, `pause`, `resume`, `cancel`, `approve`, `reject`, `run_validation`, `record_validation`, `repair`, `checkpoint`, `rollback`, and `launch_terminal`. Mutating actions remain checkpoint-backed and approval-gated. See `docs/AURALITH_AUTOPILOT_RUNTIME.md` for the full lifecycle and safety model.

## Collaborative Engineering Runtime

Collaboration is a local-first Core runtime for shared engineering workflows, role-scoped visibility, staged approvals, roadmap ownership, repository coordination, deployment/rollback governance, and audit history.

```text
GET  /v1/collaboration
GET  /v1/collaboration/roles
POST /v1/collaboration/members
POST /v1/collaboration/repositories
POST /v1/collaboration/workflows
POST /v1/collaboration/workflows/{workflow_id}/action
POST /v1/collaboration/approvals
POST /v1/collaboration/approvals/{approval_id}/decision
POST /v1/collaboration/roadmap/items
GET  /v1/collaboration/audit
```

State is stored in `.aegis/collaboration-runtime.json`; accountability events are appended to `.aegis/collaboration-audit.jsonl`. See `docs/COLLABORATIVE_ENGINEERING_RUNTIME.md` for roles, approvals, Autopilot integration, and privacy boundaries.

Mutating endpoints require a `workspace` field in the request body and return the standard Core envelope. Website compatibility routes mirror the same operations under `/api/collaboration/*` and should delegate to Core rather than storing a second approval source of truth.

## Governance Policy Runtime

Governance is the Core-owned policy layer for workflow execution, deployments, plugin permissions, runtime-node access, provider usage, memory access, validation requirements, approval requirements, command execution, and file boundaries.

```text
GET  /v1/governance
GET  /v1/governance/policies
POST /v1/governance/policies
POST /v1/governance/evaluate
GET  /v1/governance/audit
POST /v1/governance/compliance/export
```

State is stored in `.aegis/governance-policies.json`; policy evaluations and compliance exports are appended to `.aegis/governance-audit.jsonl`. Compliance exports are written to `.aegis/governance-export-*.json`.

Policy evaluation returns `allowed`, `needs_approval`, or `blocked` with the matching policy results, approval requirements, restrictions, warnings, compliance tags, and explanation. Autopilot uses the same contract to pause on policy violations and surface a `policy_governance` approval gate.

See `docs/GOVERNANCE_POLICY_RUNTIME.md` for policy scopes, runtime trust levels, plugin governance, compliance exports, and client responsibilities.

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
  "contract_version": "2026.05.11",
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

The canonical schema package is `aegis_core.contracts`. It defines request models, the Core envelope, stable runtime data models, the Core-owned editing runtime shapes, and legacy schema-only experimental shapes for patch proposals and rollback results. Contract additions must be backwards compatible: clients may ignore unknown fields, and optional fields may be absent.

Contract stability:

| Contract kind | Stability | Notes |
| --- | --- | --- |
| `health`, `models`, `settings`, `settings.updated` | stable | Shared runtime status and configuration. |
| `model.registry`, `model.routing_profiles`, `model.providers`, `model.route`, `model.completion`, `provider.key.status` | experimental | Core-owned provider/model registry, routing profiles, provider inventory, route explanations, gated completions, and OS credential status. |
| `workspace.scan`, `workspace.roadmap` | stable | Shared indexing and roadmap outputs. |
| `memory.summary`, `diagnostics.summary` | stable | Shared memory and diagnostics summaries. |
| `client.registered`, `clients.list` | stable | Cross-client registry. |
| `task.created`, `tasks.list`, `task.updated` | stable | Cross-client task record lifecycle. |
| `validation` | stable | Validation discovery/run shape. |
| `ecosystem.dashboard` | stable | Aggregated dashboard for Desktop and Website bridge. |
| `branding.tokens` | experimental | Visual/client token sharing may still change. |
| `agent.continue.plan`, `agent.repair.plan` | experimental | Plan-only agent contracts; no file edits are applied. |
| `agents.roster` | experimental | Specialized local agent roles and coordination rules. |
| `orchestration.plan`, `orchestration.dashboard`, `orchestration.step` | experimental | Supervised autonomous goal queues with approval gates; Core does not blindly edit files. |
| `jobs.dashboard`, `jobs.run` | experimental | Safe scheduled and trigger-based maintenance jobs with approval gates for risky actions. |
| `changes.proposal`, `changes.apply` | experimental | Core-owned editing proposals, patch preview metadata, selected/all apply, dry runs, mandatory checkpoints, task IDs, and job IDs. |
| `checkpoints.create`, `checkpoints.list`, `checkpoints.restore` | experimental | Workspace-local checkpoint creation, listing, and restore with pre-restore backup metadata. |
| `validation.run` | experimental | Core-owned validation execution records with stored command output, task/job IDs, and optional repair attempt metadata. |
| `core.job`, `project.activity` | experimental | Operation job lookup and project activity streams for editing, checkpoint, validation, and repair workflows. |
| `workflow.created`, `workflows.list`, `workflow.dashboard`, `workflow.step` | experimental | Core-owned workflow graph runtime for long-running multi-step work. |
| `client.sync`, `client.sync.dashboard` | experimental | Shared client synchronization for active clients, active workflows, recent operations, and workspace activity. |
| `workspace.intelligence` | experimental | Reusable workspace intelligence combining file index, project metadata, semantic memory, dependency graph, build detection, health, validation, and knowledge summaries. |
| `workflow.statistics`, `agent.runtime`, `agent.coordination`, `agent.delegation` | experimental | Workflow observability metrics, formal deterministic agent runtime, agent handoff dashboards, and approval-aware delegation. |
| `engineering.execution.created`, `engineering.executions.list`, `engineering.execution.dashboard`, `engineering.execution.step`, `engineering.execution.timeline` | experimental | Core-owned engineering execution pipeline, stage graph, task dependency graph, journal, validation chain, repair history, and timeline visualization contracts. |
| `engineering.memory`, `engineering.metrics`, `engineering.modes` | experimental | Reusable workspace intelligence memory, execution metrics, and approval-based execution mode catalog. |
| `engineering.intelligence`, `engineering.context`, `engineering.validation_intelligence`, `engineering.repair_intelligence`, `engineering.roadmap_intelligence`, `engineering.workflow_prediction`, `engineering.intelligence.benchmarks` | experimental | Deep engineering intelligence contracts for architecture reasoning, context assembly, validation targeting, repair strategy, roadmap planning, workflow prediction, explainability, and local benchmark history. |
| `intelligence.stack`, `intelligence.models`, `intelligence.retrieval`, `intelligence.route`, `intelligence.prediction`, `intelligence.benchmarks`, `intelligence.datasets`, `intelligence.distributed_inference` | experimental | Local-first specialized intelligence contracts for model lifecycle metadata, retrieval/indexing, workflow routing, lightweight predictions, evaluation datasets, benchmarks, and trusted distributed inference planning. |
| `quality.dashboard`, `quality.snapshot` | experimental | Project health scoring, trend snapshots, risk detection, quality reports, and Planner guidance. |
| `knowledge.graph`, `knowledge.query`, `knowledge.search`, `knowledge.relationships`, `knowledge.symbol`, `knowledge.impact_analysis`, `knowledge.architecture_summary` | experimental | Persistent workspace graph, deterministic graph queries, search, relationship browsing, symbol lookup, impact analysis, and architecture summaries. |
| `simulation.change`, `simulation.compare` | experimental | Read-only predictive planning, impact forecasting, architecture drift warnings, and scenario comparison. |
| `operations.dashboard` | experimental | Read-only engineering operations dashboard for release planning, technical debt, lifecycle, maintenance, productivity, and cross-project coordination. |
| `personal.intelligence`, `personal.intelligence.reset` | experimental | Local-first personal workflow/style/pattern intelligence with explicit profile persistence and reset controls. |
| `personal.memory`, `personal.memory.record`, `personal.memory.deleted`, `personal.memory.export`, `personal.memory.import`, `personal.memory.controls`, `personal.memory.cleanup`, `personal.memory.observability`, `personal.memory.context` | experimental | Inspectable local-first Auralith memory records, lifecycle controls, export/import, category privacy controls, cleanup, observability, and bounded orchestration context. |
| `runtime.interaction`, `runtime.jobs`, `runtime.job`, `runtime.job.mutation`, `runtime.streams`, `runtime.processes`, `runtime.sessions`, `runtime.session.mutation`, `runtime.voice`, `runtime.voice.command`, `runtime.replay` | experimental | Real-time engineering interaction, terminal orchestration, SSE event streams, process tracking, local collaboration sessions, voice command routing, and execution replay. |
| `patch.proposal`, `rollback.entry`, `rollback.result` | experimental schema-only | Legacy shared shapes kept for compatibility while active editing ownership moves to `changes.*` and `checkpoints.*`. |

Shared request body conventions:

- Workspace operations use `workspace`.
- Website compatibility endpoints may accept `workspace_root` and translate it to Core `workspace`.
- Cross-client task records use `title`, `kind`, `source_client`, optional `request`, and optional `metadata`.
- Shared task status values are `planned`, `running`, `waiting_for_approval`, `pending`, `in_progress`, `needs_approval`, `validating`, `blocked`, `completed`, `failed`, `cancelled`, and `rolled_back`.
- Orchestration queue status values are `pending`, `in_progress`, `blocked`, `needs_approval`, `validating`, `completed`, and `failed`.
- Continue and repair endpoints are plan-only and never apply file edits.
- Orchestration endpoints plan, queue, validate, and update memory; clients still own diff display and approval UI, but approved patch apply, checkpointing, restore, validation result storage, and operation tracking should migrate to the Core editing endpoints.
- Job run requests use `job_id`, `trigger`, or `run_due`. Jobs can scan, summarize, report, and recommend automatically, but risky actions require approval.
- Quality dashboard reads use a `workspace` query parameter. Quality snapshots use a workspace request body and write only generated `.aegis` health history/report files.
- Knowledge graph reads use a `workspace` query parameter. Persisting the graph uses a workspace request body and writes only generated `.aegis` knowledge artifacts.
- Knowledge queries use `workspace`, `query`, and optional `focus` for a file path, API route, or system name.
- Knowledge search/relationships/symbol/impact requests use Core graph state and write only graph/index artifacts when a persisted graph needs to be refreshed. Impact analysis is read-only and feeds dependency-aware execution planning.
- Deep engineering intelligence uses `workspace`, `workflow_type`, `objective`, optional `target_files`, optional `focus`, optional `latest_validation`, and a bounded `token_budget`. It writes only generated `.aegis` intelligence/context/benchmark artifacts when `persist` is enabled.
- Intelligence stack requests use `workspace`, workflow metadata, local model metadata, retrieval queries, routing privacy flags, benchmark suites, dataset privacy flags, and distributed-inference dry-run controls. They write only generated `.aegis` intelligence stack/model/retrieval/benchmark/dataset state unless a separate approved model installer or runtime worker is invoked by a client.
- Change simulations use `workspace`, `objective`, optional `files`, and optional `approach`. They are read-only and do not write source files.
- Scenario comparison uses `workspace`, `objective`, `approaches`, and optional `files`.
- Engineering operations uses `workspace` and optional `project_roots` for additional local project roots. It is read-only and coordinates recommendations rather than executing work.
- Personal intelligence uses `workspace`, optional `project_roots`, optional explicit `preferences`, and `persist`. Read-only calls do not persist profile state.
- Runtime interaction uses `workspace` query parameters for reads and `workspace` request bodies for mutations. Terminal commands are normalized into argument arrays, run with `shell=false`, restricted to workspace cwd, and blocked unless they are safe validation commands or explicitly approved.
- Personal memory uses `workspace`, category IDs, optional `scope`, optional lifecycle metadata, and privacy controls. Records are stored in `.aegis/auralith-memory.json`; audit events are appended to `.aegis/auralith-memory-audit.jsonl`. Memory context responses are bounded advisory inputs for orchestration and never replace approval gates.
- Workflows use `workflow_type`, `objective`, `source_client`, optional `context_files`, and optional metadata. Workflow tasks are deterministic records with dependencies, owner roles, logs, retries, and status. Clients still collect approvals and provide UI-specific context.
- Agent runtime requests use `workspace`, `workflow_id`, `task_id`, `agent_id`, `approval`, and structured metadata. Agents are execution roles with scoped context, model routing profiles, and persisted handoff records; they are not unbounded spawned processes.
- Engineering executions use `goal`, `mode`, optional `target_files`, optional `validation_command`, optional `roadmap_item_id`, and optional `metadata`. They formalize planning/execution/validation/repair/checkpoint/apply state while routing actual file mutation through Core editing contracts.
- Client sync heartbeats use `client_id`, `client_type`, `capabilities`, and optional `active_workflow_id`.

## GET /v1/health

Query:

- `workspace`: optional workspace path

Returns the same health data as `/health` inside the standard envelope.

## GET /v1/models

Returns installed Ollama models, selected model, missing configured models, and latency.

## GET /v1/models/registry

Returns `model.registry`, the Core-owned provider/model source of truth. The response includes provider IDs, model IDs, display names, local/cloud type, context windows, tool and vision support, code/reasoning strength, latency and cost estimates, privacy level, availability status, required auth method, last health check, and supported workflow types.

It also normalizes provider account state: linked/unlinked, key present/missing, auth method availability, reachability, rate-limit/error state, and last successful request metadata when known. Clients should use this endpoint for model pickers, provider health indicators, route-profile display, privacy-mode display, and shared runtime status.

## GET /v1/models/routing-profiles

Returns `model.routing_profiles`. Initial profile IDs are `local_only`, `balanced`, `fastest`, `cheapest`, `best_coding`, `best_reasoning`, `private_sensitive`, `creative_media`, and `fallback_safe`.

## GET /v1/providers

Query:

- `workspace`: optional workspace path

Returns the hybrid provider inventory without secret values. Providers include local Ollama, local LM Studio, OpenAI, Anthropic, Google Gemini, OpenRouter, Azure OpenAI, Amazon Bedrock, and Vertex AI. Cloud providers report whether a supported auth method is available; API keys are never returned. Inventory responses also include `credential_store_healthy` and `credential_store_errors` so clients can distinguish "no key stored" from "the OS credential store could not be inspected."

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
  "model": null,
  "route_profile": "best_coding",
  "workflow_type": "generate_feature",
  "required_capabilities": ["code"],
  "privacy_sensitive": false
}
```

Returns a route plan. Core selects Ollama/local models by default and marks cloud routes as `approval_required` until the client has shown warnings, visible sanitized context, and received explicit approval. Secret-like files, ignored directories, and outside-workspace paths are listed under `context.blocked_files` and are never sent to a provider by Core. Route responses also include `route_profile`, `fallback_chain`, `explanation`, `privacy_risk`, `expected_capability_fit`, `missing_capability_warnings`, `credential_store_healthy`, and `credential_store_errors` when Core cannot inspect OS credential storage while considering cloud fallbacks.

Explicit local provider requests stay local. For example, `provider_id: "lm_studio"` selects the configured local LM Studio OpenAI-compatible server and does not turn into an OpenAI/OpenRouter cloud fallback candidate.

LM Studio settings normalize to the local server base, such as `http://127.0.0.1:1234`, while completion calls use the standard OpenAI-compatible `/v1/chat/completions` path.

CLI route previews use the same planner. Use `python -m aegis_core.cli route --provider lm_studio --model local-model --context-file src/App.tsx --json` to inspect provider selection, approval state, warnings, and sanitized context metadata without making a completion call.

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

Cloud calls return `403` unless `allow_cloud` and `cloud_approved` are true, the Core routing mode allows cloud, and the provider has a key in OS credential storage. `local_only` mode blocks cloud calls even if the request asks for them. Route previews and completion execution use the selected route model. Cloud model overrides stay attached to cloud fallback candidates; Ollama local fallback continues to use configured local models unless a local provider is explicitly selected.

Malformed provider responses, including invalid JSON, non-object payloads, or missing completion text, return bounded provider failures instead of leaking internal parser exceptions or false-success empty completions to clients. Provider and credential diagnostics redact common provider/OAuth secret fields such as `api_key`, `x-api-key`, `client_secret`, `access_token`, `refresh_token`, `private_key`, and `token` across JSON, query-string, and assignment-style errors while preserving actionable context. Bare `token:` parser diagnostics are preserved unless the value looks secret-like, so ordinary errors such as `unexpected token: <` remain readable.

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

Local providers such as `ollama` and `lm_studio` do not use stored API keys. Key storage requests for local providers are rejected before the OS credential store is touched. Provider ids and cloud provider settings accept common casing, spacing, and hyphen aliases such as `LM Studio`, `lm-studio`, `open-router`, and `open router`; key mutations use canonical provider ids.

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

Only known safe configuration keys are applied. The file written is `.aegis/config.json`. Persisted known settings are sanitized before writing so later restarts see canonical settings instead of raw invalid input; unknown client-owned keys are preserved. `model_routing_mode` is restricted to `local_only`, `hybrid`, or `cloud_allowed`. Local provider URL settings are normalized to HTTP(S) service bases, preserve reverse-proxy path prefixes, trim pasted endpoint suffixes such as `/api/...` and `/v1/...`, and reject credentials. `fallback_models` and `validation_preferences` are stored as clean lists. `memory_dir_name` is restricted to one workspace-local folder name; absolute paths, nested paths, and parent traversal fall back to `.aegis`.

`preferred_cloud_provider` is restricted to `openai`, `anthropic`, `google`, or `openrouter`; unsupported values fall back to the default `openai` provider.

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

## GET /v1/agents

Returns the specialized local agent roster:

- Planner Agent
- Architect Agent
- Coder Agent
- Reviewer Agent
- Tester Agent
- Repair Agent
- Documentation Agent

Each agent record includes purpose, responsibilities, approval gates, and expected outputs. The roster is metadata only; it does not grant permission to edit files, run commands, install packages, or call cloud providers.

## GET /v1/agents/runtime

Query:

- `workspace`: optional workspace path

Returns `agent.runtime`, the formal multi-agent engineering runtime catalog. Initial formal agents are:

- `planner_agent`
- `coder_agent`
- `validator_agent`
- `repair_agent`
- `researcher_agent`
- `summarizer_agent`
- `architecture_agent`
- `routing_agent`

Each agent includes role, capabilities, supported workflow types, preferred model profile, execution limits, memory scope, task ownership, status, and recent execution history when a workspace is supplied. The runtime also returns structured communication contracts, safety controls, routing profiles, persistence files, and visualization contract names.

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
- owner agent for each queued task
- active agent and agent pipeline state
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
- active agent
- agent pipeline
- recent agent decisions
- coordination conflicts for overlapping affected files
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

## GET /v1/jobs

Query:

- `workspace`: required workspace path

Returns the maintenance job dashboard:

- `scheduled_jobs`: default job catalog with `last_run`, `next_run`, `due`, last result, warnings, and suggested actions
- `due_jobs`: scheduled jobs that should be run by a client or local host
- `triggers`: trigger names and mapped job ids
- `approval_rules`: what jobs may do automatically and what requires approval
- `history`: recent job runs
- `log_path`: `.aegis/jobs-log.md`

Default jobs include daily project scan, weekly roadmap update, dependency review, build health check, stale TODO scan, documentation drift check, recent changes summary, broken references check, project health report, quality intelligence snapshot, next best task, and validation status check.

## POST /v1/jobs/run

Runs one matching maintenance job group.

Run one job:

```json
{
  "workspace": "C:/path/to/project",
  "job_id": "daily-project-scan"
}
```

Run all jobs for a trigger:

```json
{
  "workspace": "C:/path/to/project",
  "trigger": "project_opened"
}
```

Run due scheduled jobs:

```json
{
  "workspace": "C:/path/to/project",
  "run_due": true
}
```

Approve a risky action such as build/test validation:

```json
{
  "workspace": "C:/path/to/project",
  "job_id": "build-health-check",
  "approval": true
}
```

Jobs may automatically scan, summarize, report, recommend, and write generated `.aegis` memory/log files. Jobs return `needs_approval` instead of running build/test/lint commands without approval. Source edits, file deletion, package installation, and cloud context also remain approval-gated. Job history is appended to `.aegis/jobs-log.md`.

## GET /v1/distributed-runtime

Query:

- `workspace`: required workspace path
- `include_audit`: optional, defaults to `true`
- `limit`: optional audit event limit

Returns Core's local-first distributed runtime dashboard with registered nodes, queued/active workloads, scheduling policy, trust model, isolation profiles, deployment metadata, observability, and recent audit events. Core persists state under `.aegis/distributed-runtime.json` and audit events under `.aegis/distributed-runtime-audit.jsonl`.

## Runtime Node Endpoints

- `GET /v1/distributed-runtime/nodes`
- `POST /v1/distributed-runtime/nodes/register`
- `POST /v1/distributed-runtime/nodes/{node_id}/heartbeat`
- `POST /v1/distributed-runtime/nodes/{node_id}/revoke`

Node registration declares node type, endpoint, capabilities, CPU/GPU/RAM/storage hints, supported workflow types, installed models/plugins, permission scopes, max parallel workloads, isolation metadata, and trust material. Remote nodes are untrusted unless they provide `AEGIS_DISTRIBUTED_NODE_TOKEN`, `AEGIS_CORE_LOCAL_TOKEN`, or explicit user approval.

## Runtime Workload Endpoints

- `GET /v1/distributed-runtime/workloads`
- `POST /v1/distributed-runtime/workloads`
- `GET /v1/distributed-runtime/workloads/{workload_id}`
- `POST /v1/distributed-runtime/workloads/{workload_id}/dispatch`
- `POST /v1/distributed-runtime/workloads/{workload_id}/retry`
- `POST /v1/distributed-runtime/workloads/{workload_id}/cancel`
- `POST /v1/distributed-runtime/dispatch`
- `POST /v1/distributed-runtime/recover`

Supported workload types are `workflow`, `validation`, `indexing`, `model_inference`, `plugin_tool`, `repair`, `build`, and `benchmark`. Scheduling checks trust level, node health, capacity, required capabilities, permission scopes, workflow support, and remote opt-in. Non-dry-run high-risk work requires approval. Remote execution is currently an assignment contract; local Core remains the authority for persisted state, audit, fallback, and recovery.

## Runtime Observability And Deployment

- `GET /v1/distributed-runtime/observability`
- `GET /v1/distributed-runtime/audit`
- `GET /v1/distributed-runtime/deployment/bootstrap`

Observability reports node counts, workload counts by status/type, duration metrics, scheduling rules, and audit summaries. The bootstrap endpoint returns a PowerShell or Bash registration script for trusted workers.

## Real-Time Runtime Interaction Endpoints

- `GET /v1/runtime/terminals`
- `GET /v1/runtime/jobs`
- `POST /v1/runtime/jobs`
- `GET /v1/runtime/jobs/{job_id}`
- `POST /v1/runtime/jobs/{job_id}/cancel`
- `POST /v1/runtime/jobs/{job_id}/retry`
- `GET /v1/runtime/streams`
- `GET /v1/runtime/processes`
- `GET /v1/runtime/sessions`
- `POST /v1/runtime/sessions`
- `POST /v1/runtime/sessions/{session_id}/sync`
- `GET /v1/runtime/voice`
- `POST /v1/runtime/voice/command`
- `GET /v1/runtime/replay`

These endpoints return terminal jobs, live stdout/stderr events, process status, collaboration sessions, voice-command routing metadata, and replay data for workflow timelines. Runtime state is persisted to `.aegis/runtime-interaction.json`.

`GET /v1/runtime/streams` returns server-sent events by default. Pass `as_sse=false` to fetch a bounded JSON event list for polling clients and tests.

Terminal execution is guarded by Core safety controls: no shell execution, cwd must remain inside the workspace, safe validation commands may run directly, non-validation commands require approval, dangerous tokens are blocked even with approval, timeouts are enforced, and all output is scrubbed before persistence.

## GET /v1/quality

Query:

- `workspace`: required workspace path

Returns a project quality dashboard:

- current health score, grade, and trend
- build/test/lint/validation status
- warnings and failing systems
- high-risk files, failing files, complexity hotspots, and untested modules
- dependency drift, repeated repair attempts, repeated model failures, and large risky diffs
- top 5 risks, top 5 cleanup tasks, and a recommended next improvement
- Planner Agent guidance for future orchestration plans

The dashboard is read-only. It may scan the workspace and inspect `.aegis` memory/logs, but it does not write history unless a snapshot is requested.

## POST /v1/quality/snapshot

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Records the current quality dashboard to `.aegis/health-history.json` and writes:

- `.aegis/daily-health-report.md`
- `.aegis/weekly-quality-summary.md`

This endpoint is safe to run from explicit client actions, scheduled jobs, or project-open triggers because it writes only generated `.aegis` health artifacts. It does not edit project source, run build/test/lint commands, install packages, or call cloud providers.

## GET /v1/knowledge/graph

Query:

- `workspace`: required workspace path

Builds a local semantic graph from the current workspace scan and `.aegis` memory without writing the graph to disk. Read-only GET does not create `.aegis`.

Nodes include:

- files, folders, modules, systems, runtime boundaries, build systems, configs, databases, symbols, classes, functions, methods, services, UI components, and APIs
- tasks, previous workflows, roadmap items, architecture decisions, known issues, validation failures, quality risks, repair history, and agent-history events

Edges include:

- `contains`, `owns`, `imports`, `uses`, `depends_on`, `calls`, `inherits`, `implements`, `configures`, `api_consumer`, `breaks`, `related_to`, `tested_by`, and `mentioned_in_roadmap`

The response includes graph clusters, architecture hotspots, unstable modules, semantic summaries, project memory, embedding-ready retrieval metadata, indexing duration, graph size, symbol counts, stale nodes, indexing failures, unsupported language areas, query examples, and a visualization-friendly node/edge subset for future Desktop rendering.

## POST /v1/knowledge/graph

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Builds and persists the knowledge graph. This endpoint writes generated `.aegis` artifacts only:

- `.aegis/knowledge-graph.json`
- `.aegis/knowledge-summary.md`
- `.aegis/knowledge-index-state.json`
- `.aegis/semantic-index.json`
- `.aegis/project-memory.json`

If persisted file fingerprints are unchanged, Core returns the cached graph with `cache_hit: true`. If files changed, the response includes `incremental.changed_files`, `removed_files`, and `invalidated_nodes`.

## POST /v1/knowledge/query

Body:

```json
{
  "workspace": "C:/path/to/project",
  "query": "What systems depend on this file?",
  "focus": "src/service.py"
}
```

Returns deterministic graph-backed answers. Supported query families include:

- dependents for a file/API/system
- unstable project areas
- roadmap items related to a module
- features/tasks tied to an API
- historical decisions, bugs, validation failures, and agent events related to a focus area

## POST /v1/knowledge/search

Body:

```json
{
  "workspace": "C:/path/to/project",
  "query": "user service",
  "node_type": "service",
  "limit": 25
}
```

Returns `knowledge.search`, a keyword/semantic-ready search over graph nodes. `node_type` is optional and can filter to `file`, `class`, `function`, `method`, `service`, `api`, `config`, and other graph node types.

## POST /v1/knowledge/relationships

Body:

```json
{
  "workspace": "C:/path/to/project",
  "focus": "src/service.py",
  "relationship": null,
  "depth": 2,
  "direction": "both",
  "limit": 50
}
```

Returns `knowledge.relationships` for graph browsing around a file, symbol, API route, runtime boundary, system, or graph node. Relationship direction can be `incoming`, `outgoing`, or `both`.

## POST /v1/knowledge/symbol

Body:

```json
{
  "workspace": "C:/path/to/project",
  "symbol": "UserService",
  "limit": 20
}
```

Returns `knowledge.symbol` across classes, functions, methods, services, UI components, symbols, and APIs.

## POST /v1/knowledge/impact-analysis

Body:

```json
{
  "workspace": "C:/path/to/project",
  "target": "src/service.py",
  "change_type": "modify",
  "limit": 100
}
```

Returns `knowledge.impact_analysis` with affected files, likely breakage areas, modification risk, validation targets, related workflows, and relationship edges. Engineering execution plans use this data to avoid unsafe edits, identify circular/risky dependency surfaces, prioritize validation, and scope repair attempts.

## GET /v1/knowledge/architecture-summary

Query:

- `workspace`: required workspace path
- `refresh`: optional, default `false`

Returns `knowledge.architecture_summary` with frameworks, languages, entry points, runtime boundaries, build systems, design-pattern hints, coding conventions, architecture hotspots, risk areas, and indexing observability.

## POST /v1/simulation/change

Body:

```json
{
  "workspace": "C:/path/to/project",
  "objective": "Refactor src/service.py while preserving API behavior",
  "files": ["src/service.py"],
  "approach": "Minimal adapter and focused validation"
}
```

Returns a read-only forecast before edits are applied:

- `risk_level`, `risk_score`, and `confidence`
- affected systems and likely impacted files
- likely build risks, likely test failures, and dependency ripple
- architecture drift warnings and coupling signals
- predicted files/tests/systems likely needing attention
- roadmap difficulty, likely blockers, validation cost, and rollback complexity
- `ui` fields for dashboards: predicted impact, confidence score, validation cost, rollback complexity, and top warnings

The simulation engine reads scan, quality, graph, memory, and validation-log data. It does not write source files, run validation commands, install packages, or call cloud providers.

## POST /v1/simulation/compare

Body:

```json
{
  "workspace": "C:/path/to/project",
  "objective": "Improve planning behavior safely",
  "files": ["src/service.py"],
  "approaches": [
    "Minimal adapter with focused validation",
    "Large rewrite of planning architecture"
  ]
}
```

Ranks implementation approaches by predicted risk, affected systems, impacted file count, validation cost, and rollback complexity. The recommended approach is the lowest-risk forecast, not an automatic edit.

## GET /v1/operations

Query:

- `workspace`: required workspace path

Returns the read-only engineering operations dashboard for a project:

- project health and validation status
- release readiness, release milestones, implementation phases, and validation checkpoints
- technical debt signals, cleanup recommendations, refactor priorities, and stability tasks
- lifecycle stage: `prototype`, `active_development`, `stabilization`, `release_candidate`, or `maintenance_mode`
- long-term risk monitoring for validation failures, dependency risk, complexity spikes, slow validation, and growing instability
- maintenance scheduling recommendations
- productivity intelligence for recurring pain points, bottlenecks, manual tasks, bug categories, and automation opportunities
- suggested next actions and approval policy

Operations may recommend scans, validation sweeps, docs refreshes, refactor windows, and release checkpoints. It does not edit files, run build/test commands, install packages, call cloud providers, or make release decisions.

## POST /v1/operations/dashboard

Body:

```json
{
  "workspace": "C:/path/to/project",
  "project_roots": [
    "C:/path/to/another/project"
  ]
}
```

Returns the same operations dashboard plus cross-project awareness for additional local project roots:

- shared libraries
- shared tooling
- repeated architecture patterns
- repeated systems
- unavailable project roots and coordination notes

## GET /v1/personal-intelligence

Query:

- `workspace`: required workspace path

Returns read-only local personal engineering intelligence:

- preferred project structures, frameworks, naming conventions, architecture styles, validation workflows, and task ordering
- coding style awareness for formatting, abstraction, comments, error handling, UI layout patterns, and architecture decisions
- recurring project systems and reusable template suggestions
- personalized recommendations, engineering habit analysis, workflow optimization, and agent guidance
- context personalization for roadmap generation, diff explanations, planning depth, summaries, and validation detail
- privacy controls, local profile path, and reset endpoint metadata

This endpoint does not persist profile state, write source files, call cloud providers, or store source contents.

## POST /v1/personal-intelligence/profile

Body:

```json
{
  "workspace": "C:/path/to/project",
  "project_roots": ["C:/path/to/another/project"],
  "preferences": {
    "planning_depth": "balanced",
    "validation_detail": "detailed",
    "safety_level": "high"
  },
  "persist": true
}
```

Returns the same `personal.intelligence` contract. When `persist` is true or explicit preferences are supplied, Core writes a local profile summary to `.aegis/personal-engineering-profile.json`. Secret-like preference keys such as keys, tokens, passwords, and credentials are ignored.

## POST /v1/personal-intelligence/reset

Body:

```json
{
  "workspace": "C:/path/to/project"
}
```

Deletes `.aegis/personal-engineering-profile.json` for the workspace and returns `personal.intelligence.reset`. Reset does not remove project memory, tasks, validation logs, health history, knowledge graphs, or source files.

## GET /v1/personal-memory

Query:

- `workspace`: required workspace path
- `query`: optional text search
- `category`: optional Core memory category
- `scope`: optional `user`, `workspace`, `project`, or `workflow`
- `include_archived`: include archived records when true
- `limit`: maximum records, capped by Core

Returns `personal.memory` with categories, controls, records, timeline entries, observability, privacy metadata, export/import endpoints, and recent audit events.

## POST /v1/personal-memory

Creates one inspectable memory record.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "category": "user_preferences",
  "title": "Validation preference",
  "content": "Prefer pytest before applying Python changes.",
  "scope": "project",
  "tags": ["validation"],
  "related_files": ["pyproject.toml"],
  "source": "website-backend",
  "confidence": 0.9,
  "pinned": true,
  "privacy": {"local_only": true},
  "metadata": {"source_workflow": "manual"}
}
```

Supported categories are `user_preferences`, `workspace_preferences`, `project_memory`, `execution_history`, `repair_history`, `validation_history`, `roadmap_history`, `architecture_notes`, `workflow_patterns`, and `ui_preferences`.

## Personal Memory Lifecycle Endpoints

```text
POST   /v1/personal-memory/query
POST   /v1/personal-memory/records/{memory_id}
PATCH  /v1/personal-memory/records/{memory_id}
POST   /v1/personal-memory/records/{memory_id}/archive
POST   /v1/personal-memory/records/{memory_id}/delete
DELETE /v1/personal-memory/records/{memory_id}
POST   /v1/personal-memory/export
POST   /v1/personal-memory/import
POST   /v1/personal-memory/controls
POST   /v1/personal-memory/cleanup
GET    /v1/personal-memory/observability
POST   /v1/personal-memory/context
```

Lifecycle controls allow records to be updated, archived, hard-deleted, exported, imported, expired, pinned, and category-disabled. Controls expose category enablement, retention days, orchestration inclusion, local-only mode, allowed scopes, and encrypted-storage availability. Secret-like text is redacted before persistence/export where possible.

`POST /v1/personal-memory/context` returns a bounded workflow-specific memory snapshot with guidance, privacy state, and observability. Orchestration treats this context as advisory; approvals, quality gates, checkpoints, and path safety still control real work.

## POST /v1/changes/propose

Records a Core-owned proposal without writing source files.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "summary": "Update README copy",
  "source_client": "website",
  "source_task_id": null,
  "risk": "low",
  "changes": [
    {
      "id": "readme-copy",
      "action": "update",
      "path": "README.md",
      "content": "# Updated README\n",
      "summary": "Replace README heading"
    }
  ],
  "repair_attempt": {
    "attempt": 1,
    "category": "validation_failure"
  }
}
```

Returns `changes.proposal` with:

- `proposal.id` for later apply
- normalized file changes
- patch preview metadata, including byte deltas and bounded unified diffs
- `job_id`, `task_id`, and `activity_id`

Core rejects unsafe paths before storing the proposal: absolute paths, dot segments, outside-workspace paths, ignored/generated/dependency folders, hidden directories, and secret-like filenames.

## POST /v1/changes/apply

Applies selected or all proposed changes through Core. This endpoint always creates a checkpoint before writing unless `dry_run` is true.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "proposal_id": "proposal-abc123",
  "change_ids": ["readme-copy"],
  "paths": [],
  "apply_all": false,
  "dry_run": false,
  "source_client": "desktop",
  "task_id": null
}
```

Clients may also send ad hoc `changes` without a stored `proposal_id`. Selection order is:

1. `change_ids`
2. `paths`
3. all changes when `apply_all` is true
4. changes marked with `selected: true`

Returns `changes.apply` with applied operations, warnings, checkpoint metadata, preview metadata, `job_id`, `task_id`, and `activity_id`. Failed file actions are reported as warnings; Core does not silently overwrite files with the wrong action. For example, `create` skips existing files and `update` skips missing files.

## POST /v1/checkpoints/create

Creates a checkpoint under `.aegis/checkpoints/` for explicit paths or proposed changes.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "paths": ["README.md", "src/app.py"],
  "summary": "Before manual apply"
}
```

Returns `checkpoints.create` with checkpoint ID, file counts, file states, and manifest path metadata. Missing files are recorded as `missing`; present files are copied into the checkpoint backup folder.

## GET /v1/checkpoints

Query:

- `workspace`: required workspace path
- `limit`: optional, default `50`

Returns `checkpoints.list` with recent Core checkpoints.

## POST /v1/checkpoints/restore

Restores a checkpoint. Core first creates a pre-restore checkpoint for the current state of the affected files, then restores present files or removes files that were missing at checkpoint time.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "checkpoint_id": "checkpoint-20260511T230000Z-a1b2c3d4",
  "dry_run": false,
  "source_client": "vscode"
}
```

Returns `checkpoints.restore` with restored operations, the pre-restore checkpoint ID, `job_id`, `task_id`, and activity metadata.

## POST /v1/validation/run

Runs or previews a safe validation command and stores the result in `.aegis/validation-results.json` while preserving the existing `.aegis/validation-log.md` append behavior.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "command": ["python", "-m", "pytest"],
  "timeout_seconds": 120,
  "dry_run": false,
  "source_client": "visual-studio",
  "task_id": null,
  "repair_attempt": {
    "attempt": 1,
    "outcome": "rerun_after_patch"
  }
}
```

Returns `validation.run` with the validation result, detected validation commands, `job_id`, `task_id`, optional repair metadata, warnings, and activity ID. Unsafe commands are blocked by the same conservative validation guard as `/v1/validation`.

## GET /v1/jobs/{job_id}

Query:

- `workspace`: required workspace path

Returns `core.job` for Core editing/checkpoint/validation operation jobs. This is separate from the maintenance-job dashboard at `GET /v1/jobs`.

## GET /v1/projects/{project_id}/activity

Query:

- `workspace`: required workspace path
- `limit`: optional, default `50`

Returns `project.activity` with recent Core editing runtime events. Use `project_id` returned by proposal/apply/checkpoint/validation responses, or `current` when the client already supplies the workspace.

## POST /v1/workspaces/intelligence

Builds the shared workspace intelligence package that all clients can reuse.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "refresh": true,
  "persist": true
}
```

Returns `workspace.intelligence` with file indexing, semantic summaries, project metadata, framework and language detection, dependency graph, symbol index, build system detection, quality/health signals, validation commands, knowledge graph metadata, and generated memory paths. When persisted, Core writes `.aegis/workspace-intelligence.json` alongside the normal scan, quality, and knowledge memory artifacts.

## POST /v1/workflows

Creates a Core-owned workflow graph.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "workflow_type": "generate_feature",
  "objective": "Add the export panel safely",
  "source_client": "website",
  "context_files": ["src/App.tsx"],
  "metadata": {
    "request_id": "optional-client-request-id"
  }
}
```

Supported `workflow_type` values:

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

Returns `workflow.created` with the workflow graph, task dependencies, formal agent ownership, scoped memory policies, model profiles, safety controls, timeline, statistics, and internal agent runtime catalog.

## GET /v1/workflows

Query:

- `workspace`: required
- `include_completed`: optional, default `true`
- `limit`: optional, default `50`

Returns `workflows.list` with active and recent Core workflows.

## GET /v1/workflows/{workflow_id}

Query:

- `workspace`: required

Returns `workflow.dashboard` with a single workflow graph, task logs, timeline, statistics, formal agent runtime metadata, and agent coordination summary.

## GET /v1/workflows/{workflow_id}/agents

Query:

- `workspace`: required

Returns `agent.coordination` for workflow visualization and supervision. The response includes active agents, task ownership, handoff chain, workflow graph, dependency graph, execution timeline, scoped memory snapshots, structured communication messages, observability, supervision state, and safety controls.

## POST /v1/workflows/{workflow_id}/agents/delegate

Delegates a workflow task to another formal agent. Delegation into mutating roles or tasks with approval gates records a waiting-input checkpoint until `approval` is true.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "task_id": "task-abc123",
  "agent_id": "architecture_agent",
  "approval": false,
  "reason": "Architecture impact review is needed before implementation.",
  "metadata": {}
}
```

Returns `agent.delegation` with the updated workflow and persisted handoff record.

## POST /v1/workflows/{workflow_id}/step

Advances or records a workflow action.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "action": "advance",
  "task_id": null,
  "approval": false,
  "summary": "Client-visible step summary",
  "payload": {}
}
```

Supported actions include:

- `advance` / `run_next`
- `complete_task`
- `fail_task`
- `retry_task`
- `delegate_task`
- `pause`
- `resume`
- `cancel`
- `record_log`

Core can deterministically execute safe built-in steps such as workspace intelligence refresh, roadmap refresh, and approved validation. Provider/media/research/benchmark/apply tasks wait for explicit client-supplied results or approval-gated handoff to the relevant Core runtime.

## POST /v1/workflows/{workflow_id}/pause

Pauses a workflow. Queued or running tasks are preserved for later resume.

## POST /v1/workflows/{workflow_id}/resume

Resumes a paused workflow and recalculates queued tasks from dependency state.

## POST /v1/workflows/{workflow_id}/cancel

Cancels the workflow and marks unfinished tasks as `cancelled`.

## POST /v1/workflows/{workflow_id}/retry

Queues a failed, cancelled, or waiting-input task for retry, subject to its retry limit.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "task_id": "task-abc123"
}
```

## GET /v1/workflows/{workflow_id}/events

Server-sent event stream for one workflow.

Query:

- `workspace`: required
- `since`: optional event offset
- `limit`: optional, default `100`
- `follow`: optional, default `false`
- `max_seconds`: optional follow timeout

Returns `text/event-stream` events named `workflow_event`. Use `GET /v1/workflows/events` for the workspace-wide stream.

## GET /v1/workflows/stats

Query:

- `workspace`: required

Returns `workflow.statistics` with workflow counts, active counts, status/type counts, average duration, validation success rate, repair tracking, model usage counts, agent observability, event count, and recent events.

## GET /v1/workflows/agent-runtime

Returns `agent.runtime`, the same formal multi-agent runtime catalog exposed at `GET /v1/agents/runtime`. These agents are execution ownership labels, memory scopes, routing policies, and logging boundaries; they do not secretly mutate files, spawn recursively, or call providers.

## GET /v1/engineering/modes

Returns `engineering.modes`, the supported engineering execution modes and their safety rules.

Modes are:

- `safe_assisted`
- `approval_every_step`
- `semi_autonomous`
- `autonomous_validate_only`
- `roadmap_execution`
- `repair_only`

## POST /v1/engineering/executions

Creates a Core-owned engineering execution plan.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "goal": "Implement the export panel safely",
  "mode": "safe_assisted",
  "source_client": "website",
  "constraints": ["Keep the existing API shape stable."],
  "target_files": ["src/export.ts"],
  "context_files": ["README.md"],
  "validation_command": ["python", "-m", "pytest"],
  "max_repair_attempts": 2,
  "max_file_modifications": 25,
  "approval_requirements": ["Product owner approval before apply."],
  "roadmap_item_id": null,
  "roadmap_phase_id": null,
  "metadata": {},
  "create_workflow": true
}
```

Returns `engineering.execution.created`. The payload includes the execution plan, stage graph, task dependency graph, workspace-memory reference, validation checkpoints, repair checkpoints, rollback strategy, approval requirements, safety controls, and optional linked Core workflow ID.

Pipeline stages are `intake`, `workspace_analysis`, `planning`, `task_decomposition`, `implementation`, `validation`, `repair`, `review`, `approval`, `checkpoint`, `apply`, and `completion_summary`. Checkpoint is intentionally before apply to enforce rollback availability.

State is stored under `.aegis/engineering-executions.json`, `.aegis/engineering-events.json`, `.aegis/engineering-journal.json`, `.aegis/engineering-memory.json`, and `.aegis/engineering-audit.md`.

## GET /v1/engineering/executions

Query:

- `workspace`: required
- `include_completed`: optional, default `true`
- `limit`: optional, default `50`

Returns `engineering.executions.list` with active and recent engineering execution records.

## GET /v1/engineering/executions/{execution_id}

Query:

- `workspace`: required

Returns `engineering.execution.dashboard` with one execution, timeline, metrics, and current engineering memory.

## POST /v1/engineering/executions/{execution_id}/step

Advances or records an engineering execution stage.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "action": "advance",
  "stage_key": "validation",
  "approval": true,
  "summary": "Run the approved validation command.",
  "payload": {
    "command": ["python", "-m", "pytest"]
  }
}
```

Supported actions include:

- `advance`
- `pause`
- `resume`
- `cancel`
- `record_log`
- `approve`
- `record_validation`
- `record_repair`
- `record_rollback`
- `complete_stage`
- `fail_stage`
- `run_validation`
- `apply`

Validation runs use Core validation/editing result storage. Apply uses `changes.apply`, so selected file changes still get patch previews, mandatory checkpoints, job IDs, activity records, and dry-run support.

## GET /v1/engineering/executions/{execution_id}/timeline

Query:

- `workspace`: required

Returns `engineering.execution.timeline` with:

- event timeline
- stage timeline
- execution graph
- task dependency graph
- validation chain
- repair history

This contract is intended for future UI timeline, graph, validation-chain, and repair-history views.

## GET /v1/engineering/memory

Query:

- `workspace`: required
- `refresh`: optional, default `false`

Returns `engineering.memory`, a reusable project-understanding layer derived from workspace intelligence. It includes architecture summary, dependency graph, coding conventions, framework usage, entry points, build systems, risk areas, generated knowledge summaries, validation commands, and memory paths.

## POST /v1/engineering/memory

Body:

```json
{
  "workspace": "C:/path/to/project",
  "refresh": true,
  "persist": true
}
```

Refreshes and optionally persists engineering memory. Persisted output includes `.aegis/engineering-memory.json` and `.aegis/engineering-memory.md`.

## GET /v1/engineering/metrics

Query:

- `workspace`: required

Returns `engineering.metrics` with execution counts, validation success rate, repair success rate, average iterations, model usage efficiency, files modified per workflow, rollback frequency, duration metrics, and recent events.

## POST /v1/engineering/roadmap/execute

Creates a roadmap-linked engineering execution.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "goal": "Complete roadmap item 1",
  "roadmap_item_id": "roadmap-item-1",
  "roadmap_phase_id": "phase-1",
  "source_client": "website",
  "target_files": ["README.md"],
  "validation_command": null,
  "constraints": [],
  "metadata": {}
}
```

Returns `engineering.execution.created` with `mode: roadmap_execution` and a `roadmap_link` that clients can use to show completed, in-progress, blocked, checkpointed, and validated roadmap work.

## POST /v1/clients/sync

Records a client heartbeat and active workflow.

Body:

```json
{
  "workspace": "C:/path/to/project",
  "client_id": "desktop-main",
  "client_type": "desktop",
  "name": "Auralith Desktop",
  "version": "0.1.0",
  "capabilities": ["workflow_runtime", "editing_runtime"],
  "active_workflow_id": "workflow-abc123",
  "status": "active",
  "metadata": {}
}
```

Returns `client.sync` and appends a workflow event.

## GET /v1/client-sync

Query:

- `workspace`: required
- `limit`: optional, default `50`

Returns `client.sync.dashboard` with active clients, active workflows, recent operations, and the workspace activity feed.

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
