# API Reference

Last updated: 2026-05-09

This repository currently exposes two API layers:

- Website backend `/api` on `http://127.0.0.1:8787`
- Aegis Core `/v1` on `http://127.0.0.1:8788`

The Website backend is the product/application API. Aegis Core is the shared runtime API.

## Website `/api`

Website `/api` remains backwards compatible for the React UI and Desktop app.

Low-risk Website runtime routes now use the Website Core adapter when Core is available:

- `GET /api/health` and `GET /api/ready` include shared Core runtime status while preserving the existing health shape.
- `GET /api/models` keeps the Website model inventory shape and may annotate/augment local models with Core `/v1/models` state.
- `GET /api/config` keeps Website `.env` settings and includes Core settings adapter status.
- `POST /api/config` saves Website settings first, then best-effort syncs shared model settings to Core `/v1/settings`.

These response models include additive optional fields: `core_runtime_reachable`, `core_runtime_status`, `core_contract_version`, and `core_runtime_message`.

Stable product groups:

- `GET /api/health`, `GET /api/ready`
- `GET/POST /api/config`
- `GET /api/models`
- `GET /api/files`, `GET /api/file`, `GET /api/file/slice`
- `POST /api/chat`, `POST /api/chat/stream`
- `POST /api/routing/preview`
- `POST /api/apply`
- `GET /api/checkpoints`, `POST /api/restore-checkpoint`
- `POST /api/validate`, `POST /api/verify`
- `GET/PUT /api/validation/profile`
- `GET/POST /api/tasks` and task actions/timeline/artifacts
- `GET/POST/PUT/DELETE /api/memory`
- `POST /api/feedback`
- `GET/PUT /api/approval/settings`
- `POST /api/project-builder/plan`, `/preview`, `/scaffold`

Failure behavior:

- Invalid or uncreatable `workspace_root` values should return `400` with a useful `detail` message.
- If Aegis Core is offline, low-risk adapter fields report `core_runtime_status: unavailable` while mature Website `/api` behavior continues where local fallback is safe.
- Website apply/checkpoint restore remains Website-owned. Core rollback contracts are still schema-only.

Product/advanced groups that stay Website-owned for now:

- model registry, model manager, model benchmarks
- workspace/project intelligence
- unified runtime/context, continuity, platform discipline
- distributed runtime, adaptive intelligence, productization, ecosystem, autonomous engineering
- Creative Studio/media
- auth/session APIs

Deprecated/removal status:

- No Website `/api` route is removed or formally deprecated in the current cleanup phase.
- Low-risk runtime routes are adapter-backed where noted, but their `/api` response models remain backwards compatible.
- See `DEPRECATION_PLAN.md` before removing any duplicate Website, Core, Desktop, VS Code, or Visual Studio runtime path.

## Website-to-Core Bridge

`GET /api/core-runtime`

Query:

- `workspace_root`: optional Website workspace path

Returns a Website wrapper around stable Core `/v1` envelopes:

```json
{
  "ok": true,
  "reachable": true,
  "core_url": "http://127.0.0.1:8788",
  "api_version": "v1",
  "contract_version": "2026.05.09",
  "contract_versions": {
    "health": "2026.05.09",
    "models": "2026.05.09"
  },
  "workspace": "C:/path/to/project",
  "ownership": {
    "shared_runtime": "aegis-core",
    "application_runtime": "website-backend",
    "migration_phase": "unified-contract-client-compatibility-phase"
  },
  "health": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "health", "data": {}},
  "models": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "models", "data": {}},
  "settings": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "settings", "data": {}},
  "memory": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "memory.summary", "data": {}},
  "diagnostics": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "diagnostics.summary", "data": {}},
  "dashboard": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "ecosystem.dashboard", "data": {}},
  "errors": []
}
```

This endpoint is read-only. It is the compatibility adapter for observing shared runtime state without breaking Website `/api`.

## Aegis Core `/v1`

All Core `/v1` responses use this envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "contract_version": "2026.05.09",
  "kind": "contract.kind",
  "workspace": "C:/path/to/project",
  "data": {},
  "stability": "stable",
  "deprecated": false,
  "deprecations": []
}
```

Client parsing rules:

- Validate `api_version` before trusting the response. Current clients expect `v1`.
- Validate `kind` against the endpoint contract listed below.
- Treat unknown top-level or `data` fields as additive and safe to ignore.
- Treat missing optional `data` fields as a degraded or empty state, not a parser crash.
- For sync/mutation calls, treat `ok: false` as a useful Core error and surface `data.error`, `data.message`, or `deprecations` when present.

Endpoint families:

| Endpoint | Contract kind | Stability | Purpose |
| --- | --- | --- | --- |
| `GET /v1/health` | `health` | stable | Shared Core, workspace, config, and Ollama health |
| `GET /v1/models` | `models` | stable | Shared local model inventory |
| `GET /v1/providers` | `model.providers` | experimental | Hybrid provider inventory without secret values |
| `GET /v1/models/providers` | `model.providers` | experimental | Alias for hybrid provider inventory |
| `POST /v1/models/route` | `model.route` | experimental | Local-first model route plan with cloud approval state and sanitized context metadata |
| `POST /v1/models/completions` | `model.completion` | experimental | Gated local/cloud completion call; cloud requires explicit approval and stored OS credential |
| `POST /v1/providers/{provider_id}/key` | `provider.key.status` | experimental | Store provider API key in OS credential storage, never in `.aegis/config.json` |
| `DELETE /v1/providers/{provider_id}/key` | `provider.key.status` | experimental | Remove provider API key from OS credential storage |
| `GET /v1/settings` | `settings` | stable | Shared Core settings |
| `POST /v1/settings` | `settings.updated` | stable | Update shared Core settings |
| `POST /v1/workspaces/scan` | `workspace.scan` | stable | Shared workspace scan/index |
| `POST /v1/workspaces/roadmap` | `workspace.roadmap` | stable | Shared roadmap generation |
| `GET /v1/memory` | `memory.summary` | stable | Shared memory summary |
| `GET /v1/diagnostics` | `diagnostics.summary` | stable | Shared diagnostics summary |
| `GET /v1/branding` | `branding.tokens` | experimental | Shared product/runtime/client tokens |
| `POST /v1/clients/register` | `client.registered` | stable | Cross-client registration |
| `GET /v1/clients` | `clients.list` | stable | Cross-client list |
| `GET /v1/agents` | `agents.roster` | experimental | Specialized local agent roster and coordination rules |
| `POST /v1/tasks` | `task.created` | stable | Shared task creation |
| `GET /v1/tasks` | `tasks.list` | stable | Shared task list |
| `POST /v1/tasks/{task_id}/status` | `task.updated` | stable | Shared task status update |
| `POST /v1/orchestration/plan` | `orchestration.plan` | experimental | Create supervised autonomous goal plan and local queue |
| `GET /v1/orchestration` | `orchestration.dashboard` | experimental | Current goal, task list, active step, approvals, validation, rollback state |
| `POST /v1/orchestration/step` | `orchestration.step` | experimental | Advance an approval-gated orchestration step |
| `GET /v1/jobs` | `jobs.dashboard` | experimental | Scheduled and trigger-based maintenance job dashboard |
| `POST /v1/jobs/run` | `jobs.run` | experimental | Run one job, due scheduled jobs, or trigger-based jobs with approval gates |
| `GET /v1/quality` | `quality.dashboard` | experimental | Project health score, trend, warnings, risks, cleanup tasks, and Planner guidance |
| `POST /v1/quality/snapshot` | `quality.snapshot` | experimental | Record a project health snapshot and generated daily/weekly quality reports |
| `GET /v1/knowledge/graph` | `knowledge.graph` | experimental | Build a local semantic project graph without writing history |
| `POST /v1/knowledge/graph` | `knowledge.graph` | experimental | Persist the local semantic project graph and generated summary |
| `POST /v1/knowledge/query` | `knowledge.query` | experimental | Query graph relationships for impacted systems, roadmap links, unstable areas, and API ties |
| `POST /v1/simulation/change` | `simulation.change` | experimental | Predict affected systems, risks, validation cost, and rollback complexity before edits |
| `POST /v1/simulation/compare` | `simulation.compare` | experimental | Compare implementation approaches by predicted risk, impact, validation, and rollback cost |
| `GET /v1/operations` | `operations.dashboard` | experimental | Release planning, technical debt, lifecycle, risk monitoring, maintenance, and productivity dashboard |
| `POST /v1/operations/dashboard` | `operations.dashboard` | experimental | Operations dashboard with optional cross-project awareness |
| `GET /v1/personal-intelligence` | `personal.intelligence` | experimental | Read-only local workflow, style, preference, pattern, and habit intelligence |
| `POST /v1/personal-intelligence/profile` | `personal.intelligence` | experimental | Optional local profile persistence with explicit preferences and cross-project pattern inputs |
| `POST /v1/personal-intelligence/reset` | `personal.intelligence.reset` | experimental | Reset workspace-local personal engineering profile memory |
| `POST /v1/validation` | `validation` | stable | Shared validation summary/run |
| `POST /v1/agent/continue` | `agent.continue.plan` | experimental | Plan-only continue from roadmap |
| `POST /v1/agent/repair` | `agent.repair.plan` | experimental | Plan-only repair from validation log |
| `GET /v1/ecosystem/dashboard` | `ecosystem.dashboard` | stable | Shared clients/tasks/model/diagnostics dashboard |

Schema-only experimental contracts are defined in `aegis-core/aegis_core/contracts.py` for `patch.proposal`, `rollback.entry`, and `rollback.result`. They are intentionally not active write endpoints yet.

Hybrid model routing:

- Core defaults to `model_routing_mode: local_only` and routes normal work to Ollama at `http://127.0.0.1:11434`.
- Optional providers are OpenAI, Anthropic, Google, OpenRouter, and local LM Studio.
- Explicit local provider requests such as `ollama` or `lm_studio` stay local; they are not reinterpreted as cloud fallback requests.
- LM Studio settings normalize to the local server base, and completions call its OpenAI-compatible `/v1/chat/completions` endpoint.
- Cloud routes require client-visible warnings, explicit approval, sanitized context metadata, and provider keys stored in OS credential storage.
- `preferred_cloud_provider` is restricted to OpenAI, Anthropic, Google, or OpenRouter.
- Provider key storage is only accepted for cloud providers; local providers such as Ollama and LM Studio do not use stored API keys.
- Secret-like, ignored, and outside-workspace files are excluded from cloud context.
- Provider inventory and route responses include `credential_store_healthy` and `credential_store_errors` so clients can tell the difference between "no cloud key stored" and "the OS credential store could not be inspected."
- Malformed provider responses, including invalid JSON, are returned as bounded provider failures rather than internal parser errors.
- Provider and credential diagnostics redact common colon-form secret assignments such as `api_key: ...`, `x-api-key: ...`, and `token: ...` while preserving actionable error context.
- Settings updates persist sanitized hybrid routing values to `.aegis/config.json`, including canonical routing modes, provider IDs, model lists, context limits, booleans, and local HTTP(S) provider URLs. When settings are saved, existing known settings on disk are normalized while unknown client-owned keys are preserved.
- CLI parity: `python -m aegis_core.cli route --provider lm_studio --model local-model --context-file src/App.tsx --json` previews the same provider selection and sanitized context metadata as `/v1/models/route`.

Autonomous task orchestration:

- Core stores staged goal queues in `.aegis/orchestration-queue.json`.
- Specialized owner agents are Planner, Architect, Coder, Reviewer, Tester, Repair, and Documentation.
- Queue statuses are `pending`, `in_progress`, `blocked`, `needs_approval`, `validating`, `completed`, and `failed`.
- File edits, deletes, package installs, validation/build commands, and cloud context require explicit approval gates.
- Core updates roadmap, decisions, validation log, and agent history, while clients still own diff display, patch apply, and rollback execution.

Workflow automation:

- Core exposes safe maintenance jobs for project scans, roadmap updates, dependency review, health reports, TODO scans, documentation drift checks, broken references, next-best-task suggestions, and validation status.
- Jobs may scan, summarize, report, recommend, and write generated `.aegis` memory/log files.
- Jobs require approval before source edits, deletes, package installs, build/test/lint commands, or cloud context.
- Job state is stored in `.aegis/jobs-state.json`; job history is appended to `.aegis/jobs-log.md`.

Quality intelligence:

- Core exposes a read-only quality dashboard at `/v1/quality` and an explicit snapshot writer at `/v1/quality/snapshot`.
- Snapshots track validation status, TODOs, known bugs, dependency drift, risky diffs, stale docs, repeated repairs, repeated model failures, complexity hotspots, and frequently changed files.
- Snapshot history is stored in `.aegis/health-history.json`; generated reports are written to `.aegis/daily-health-report.md` and `.aegis/weekly-quality-summary.md`.
- Planner Agent uses the quality dashboard during orchestration planning so broken validation, repeated failures, high-risk files, and missing tests can influence task order.

Knowledge graph:

- Core exposes local semantic project understanding through `/v1/knowledge/graph` and `/v1/knowledge/query`.
- The graph links files, symbols, systems, APIs, UI components, services, tasks, roadmap items, decisions, known issues, validation failures, risks, and agent-history events.
- Relationship types include `uses`, `depends_on`, `calls`, `implements`, `breaks`, `related_to`, `tested_by`, and `mentioned_in_roadmap`.
- Persisted graphs are written to `.aegis/knowledge-graph.json`; summaries are written to `.aegis/knowledge-summary.md`.
- Planner Agent reads graph summaries during orchestration planning so impacted systems, related issues, and context suggestions influence safer task plans.

Predictive planning and change simulation:

- Core exposes read-only forecasts through `/v1/simulation/change` and scenario comparison through `/v1/simulation/compare`.
- Simulations combine workspace scan data, the knowledge graph, quality history, validation logs, dependency ripple, and requested focus files.
- Forecasts return risk level, risk score, confidence, impacted files, affected systems, likely build/test risks, architecture drift warnings, validation cost, rollback complexity, and UI-ready summary fields.
- Planner Agent uses the forecast during orchestration planning and inserts a risk-splitting task when a change is high risk or likely to create architecture drift.
- Simulation endpoints never apply edits, run risky commands, send cloud context, or write project source files.

Autonomous engineering operations:

- Core exposes a read-only engineering operations dashboard through `/v1/operations`.
- Operations combines quality, knowledge, tasks, jobs, validation, roadmap, and simulation-era risk signals into release readiness, milestones, debt tracking, lifecycle stage, maintenance scheduling, productivity intelligence, and suggested next actions.
- `POST /v1/operations/dashboard` accepts additional local project roots for cross-project awareness: shared tooling, dependencies, architecture patterns, and coordination notes.
- Operations may recommend scans, validation sweeps, docs refreshes, refactor windows, and release checkpoints, but file edits, build/test commands, dependency installs, cloud calls, and release decisions remain approval-gated.

Adaptive personal engineering intelligence:

- Core exposes read-only local personalization through `/v1/personal-intelligence`.
- `POST /v1/personal-intelligence/profile` accepts `workspace`, optional `project_roots`, optional explicit `preferences`, and `persist`.
- Persisted profile summaries live in `.aegis/personal-engineering-profile.json` only when explicitly requested or when preferences are supplied.
- `POST /v1/personal-intelligence/reset` clears that local profile.
- The contract returns learned workflow signals, coding style awareness, recurring project patterns, personalized recommendations, habit analysis, workflow optimization, context personalization, and privacy controls.
- Secret-like preference keys are filtered and source file contents are summarized rather than persisted.

Release candidate notes:

- Core `/v1/validation` blocks unsafe command overrides and returns structured `ok: false` results.
- Detected safe validation commands such as `npm test` can return nonzero exit codes without crashing Core or Website clients.
- Simulated Ollama outages through workspace-local Core settings return model health data with `reachable: false` and an error detail.

See `aegis-core/docs/API_REFERENCE.md` for the Core-only details and examples.

## Removal Gate

Before any old route, fallback, or shim is removed:

- the replacement Core endpoint must have contract tests;
- the Website adapter must have online/offline and wrong-kind/wrong-version tests;
- frontend and Desktop compatibility tests must still pass against the old `/api` shape;
- IDE extension package/build checks must pass for affected workflows;
- apply/rollback workflows must have explicit restore tests if files can be changed.
