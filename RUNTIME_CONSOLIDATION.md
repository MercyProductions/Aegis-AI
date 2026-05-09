# Runtime Consolidation

Last updated: 2026-05-09

## Goal

Aegis Core should become the reusable shared runtime for all clients. The Website backend should remain the product/application orchestration layer. Consolidation must happen gradually through stable contracts, adapters, and tests.

This phase does not move Website chat, apply, project-builder, Creative Studio, auth, or advanced product surfaces out of Website `/api`. Aegis Core now owns a small local-first hybrid model router contract for shared provider selection, but Website still owns its mature product routing and telemetry until a later adapter phase.

## Current Overlap

| Subsystem | Website backend today | Aegis Core today | Consolidation target |
| --- | --- | --- | --- |
| Health | `/api/health` reports Website readiness, model/provider status, database paths, router state | `/v1/health` reports Core config, workspace, Ollama health | Keep both. Website health is app health; Core health is shared runtime health. Website can surface Core status through bridge. |
| Models | Full model registry, manager, benchmarks, routing, providers, telemetry | Ollama inventory plus local-first hybrid route planning and provider inventory | Core owns shared model visibility and privacy-gated routing contracts. Website owns advanced provider registry, benchmarks, telemetry, and product routing until stable enough to extract. |
| Settings | `.env` and Website settings model | `.aegis/config.json` shared Core settings | Core owns cross-client shared settings. Website owns product/app settings and can read Core settings through bridge. |
| Workspace scan/indexing | `WorkspaceManager`, Project Intelligence, Workspace Operations, unified context | `WorkspaceScanner`, file/dependency/symbol indexes, scan cache | Core owns shared lightweight indexing. Website owns rich app intelligence and should consume Core indexes before adding duplicate scan logic. |
| Roadmap | Website project/autopilot flows and richer task planning | `.aegis/roadmap.md` generation | Core owns shared roadmap file and plan-only continuation source. Website may orchestrate richer plans from it. |
| Memory | SQLite fix/project memory plus Website memory CRUD | `.aegis` memory summaries, decisions, known issues, logs | Core owns shared file-backed client memory. Website owns app telemetry/memory UX and should bridge Core memory for shared state. |
| Diagnostics | Website telemetry, route health, productization, workspace health | Core/extension/validation/agent log summaries | Core owns shared diagnostics summaries. Website owns app observability dashboards. |
| Validation | Website command runner, validation profiles, repair loop, build logs | Safe validation detection/run, validation log | Core owns shared safe validation primitives. Website owns advanced validation/repair orchestration until command semantics converge. |
| Tasks/orchestration | Website SQLite task graph, approvals, artifacts, timeline, rich autonomous engineering | `.aegis/tasks.json` cross-client tasks plus supervised `.aegis/orchestration-queue.json` goal queues with specialized owner agents | Core owns lightweight shared task records, agent roster metadata, and approval-gated orchestration state. Website owns rich app task graph, artifacts, apply/checkpoint workflows, and product autonomous engineering. |
| Workflow automation/jobs | Website benchmark/media/background jobs and rich app workflows | `.aegis/jobs-state.json`, `.aegis/jobs-log.md`, `/v1/jobs`, and safe maintenance workflows | Core owns local maintenance scans, reports, due/trigger state, and approval-gated job execution. Website owns product jobs, cloud/background services, and advanced workflow scheduling. |
| Observability/quality intelligence | Website telemetry, product health, adaptive intelligence, and app observability dashboards | `/v1/quality`, `/v1/quality/snapshot`, `.aegis/health-history.json`, daily/weekly quality reports, and Planner guidance | Core owns local project health trends and risk detection. Website owns product telemetry and rich app dashboards. |
| Knowledge graph/deep understanding | Website project intelligence, adaptive intelligence, and app-specific context systems | `/v1/knowledge/graph`, `/v1/knowledge/query`, `.aegis/knowledge-graph.json`, and generated knowledge summaries | Core owns shared local relationship graph and deterministic queries. Website owns product-specific intelligence UI and advanced app workflows. |
| Client registry/dashboard | Website ecosystem/product surfaces | `/v1/clients/*`, `/v1/ecosystem/dashboard` | Core owns shared client registry and ecosystem dashboard data. |
| Auth/UI/session | Website account/session APIs and frontend state | none | Website only. Do not move to Core. |
| Creative/media | Creative Studio jobs/assets/providers | none | Website only until there is a non-UI shared media runtime need. |
| Productization/adaptive/autonomous | Website advanced app domains | none | Website only for now. |

## Ownership Decisions

| Subsystem | Owner now | Target owner | Migration type |
| --- | --- | --- | --- |
| Core health envelope | Aegis Core | Aegis Core | API-only |
| Website app health | Website backend | Website backend | API-only |
| Core status inside Website | new bridge | Website consumes Core | adapter/shim |
| Local Ollama inventory | Aegis Core and Website provider stack | Aegis Core for shared status and route planning, Website for advanced product routing | adapter first |
| Hybrid provider selection | Aegis Core | Aegis Core | experimental API-only |
| Shared settings | Aegis Core | Aegis Core | API-only |
| App settings | Website backend | Website backend | no migration |
| Shared indexing | Aegis Core | Aegis Core | shared runtime |
| Rich project intelligence | Website backend | Website backend or future shared library | hold |
| Shared roadmap | Aegis Core | Aegis Core | shared runtime |
| Rich task planning | Website backend | Website backend | hold |
| Shared memory summaries | Aegis Core | Aegis Core | shared runtime |
| App memory CRUD/telemetry | Website backend | Website backend | hold |
| Shared diagnostics | Aegis Core | Aegis Core | shared runtime |
| Product observability | Website backend | Website backend | hold |
| Shared task records | Aegis Core | Aegis Core | shared runtime |
| Specialized local agent roles | Aegis Core | Aegis Core | API-only |
| Supervised orchestration queue | Aegis Core | Aegis Core | shared runtime |
| Safe maintenance jobs | Aegis Core | Aegis Core | shared runtime |
| Project quality intelligence | Aegis Core | Aegis Core | shared runtime |
| Knowledge graph | Aegis Core | Aegis Core | shared runtime |
| Website task graph | Website backend | Website backend, possibly linked to Core tasks | adapter later |
| Shared validation primitive | Aegis Core | Aegis Core | shared runtime |
| Repair orchestration | Website backend | Website backend | hold |

## Post-Migration Ownership Markers

| Area | Core-owned | Website-owned | Client-owned | Deprecated adapter/shim status |
| --- | --- | --- | --- | --- |
| Models | Shared local model inventory, selected/fallback model status, hybrid provider inventory, cloud-approval route plans | Provider registry, model manager, benchmarks, advanced routing policy | UI selection and direct fallback only where needed | Website `/api/models` is adapter-backed but remains stable. VS Code direct Ollama fallback stays for offline use. |
| Settings | Cross-client `.aegis/config.json` settings | Website `.env` app/product settings | IDE/desktop UI preferences | Website model settings sync to Core is best-effort; no removal. |
| Diagnostics | Shared `.aegis` log summaries | Website observability, telemetry, product diagnostics | IDE build/output diagnostics | Core diagnostics are read adapters only. |
| Memory | Shared file-backed memory summaries | Website memory CRUD, SQLite telemetry, memory UX | IDE-local context selection and notes | No memory write deprecation yet. |
| Indexing | Lightweight workspace scan/index | Rich project intelligence and workspace operations | Editor/solution context and local indexes | VS Code scan fallback remains. Website/VS still native. |
| Roadmap | Shared `.aegis/roadmap.md` generation | Autopilot planning/orchestration | IDE roadmap UX and proposal flow | VS Code roadmap fallback remains. |
| Validation | Safe command detection/run primitive | Validation profile, repair loop, verify pipeline | IDE terminal/build validation UX | Core validation is a primitive; Website validation remains native. |
| Tasks/orchestration | Cross-client lightweight task records, specialized owner-agent roles, supervised goal queue state | SQLite task graph, artifacts, timeline, approvals, apply/checkpoint flows | Client task UI/sync, approval surfaces, diff/apply UX | Core orchestration is stateful and approval-gated; clients still own file mutation UX. |
| Workflow automation/jobs | Safe scheduled and trigger-based maintenance jobs, generated `.aegis` reports, approval-gated build health | Product jobs, benchmark jobs, media jobs, cloud/background scheduling | Job dashboard UI, trigger buttons, approval prompts | Core jobs are experimental and client-invoked; no hidden daemon. |
| Observability/quality | Health score, trend snapshots, risk detection, generated daily/weekly quality reports, Planner guidance | Product telemetry, rich app observability, adaptive intelligence dashboards | Quality/risk UI, explicit snapshot buttons, high-risk edit warnings | Core quality is experimental and read/report-oriented; no source edits are implied. |
| Knowledge graph | Shared semantic relationship graph, graph query responses, graph summaries, Planner context guidance | Rich product intelligence and UI-specific context workflows | Graph visualization, impact-query UI, editor-native context selection | Core graph is experimental and generated-artifact only; no edit authority is implied. |
| Rollback | Schema-only future contracts | Checkpoints/restore | IDE backups/rollback | Do not deprecate until active Core rollback exists. |

## Standard Contract Shapes

Core `/v1` responses use a stable envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "contract_version": "2026.05.09",
  "kind": "workspace.scan",
  "workspace": "C:/path/to/project",
  "data": {},
  "stability": "stable",
  "deprecated": false,
  "deprecations": []
}
```

Website `/api` responses remain product-specific Pydantic response models. When Website consumes Core, it should preserve the Core envelope instead of flattening it into app-specific shapes.

The canonical contract package is `aegis-core/aegis_core/contracts.py`. It defines:

- shared request models for workspace, settings, model routing/completion, provider key status, client registration, tasks, orchestration, jobs, quality snapshots, knowledge queries, validation, continue, and repair;
- stable response data models for health, models, settings, workspace scan, roadmap, memory, diagnostics, tasks, validation, and dashboard;
- experimental response data models for hybrid model providers/routes/completions, supervised orchestration, workflow jobs, quality dashboards/snapshots, knowledge graphs/queries, and agent continue/repair;
- schema-only experimental patch proposal and rollback models for future migration.

Compatibility rules:

- Keep `/v1` as the versioned URL namespace.
- Keep `api_version`, `contract_version`, `kind`, `workspace`, and `data` in every successful Core envelope.
- Add fields only in a backwards-compatible way. Clients must ignore unknown fields.
- Optional fields may be absent. Contract tests cover missing optional fields for known Desktop, VS Code, and Visual Studio reads.
- Use `stability`, `deprecated`, and `deprecations` before removing or changing behavior.

Shared request bodies should follow these names:

| Contract | Required fields | Notes |
| --- | --- | --- |
| Workspace request | `workspace` | Core name. Website may accept `workspace_root` at `/api`, then map to Core `workspace`. |
| Settings update | `workspace`, `settings` | Unknown/unsafe settings are ignored by Core config loading. |
| Model route | `workspace`, `task_type`, optional `difficulty`, `context_files`, `allow_cloud`, `cloud_approved`, `local_failure_reason`, `provider_id`, `model` | Cloud routes are never selected for calls unless approval and provider credentials are present. |
| Model completion | Model route fields plus `prompt`, optional `timeout_seconds` | Experimental. Cloud calls are rejected unless routing mode, approval, sanitized context, and OS credential state allow them. |
| Provider key | `api_key` | Stored only in OS credential storage; never written to workspace config. |
| Client registration | `workspace`, `client_id`, `client_type`, `name`, optional `version`, `capabilities` | Used by Desktop, VS Code, Visual Studio, Website later. |
| Task create | `workspace`, `title`, optional `kind`, `source_client`, `request`, `metadata` | Cross-client task record only. |
| Task status | `workspace`, `status`, optional `summary` | Core statuses are `planned`, `running`, `waiting_for_approval`, `pending`, `in_progress`, `needs_approval`, `validating`, `blocked`, `completed`, `failed`, `cancelled`, `rolled_back`. |
| Agents roster | none | Lists Planner, Architect, Coder, Reviewer, Tester, Repair, and Documentation roles. |
| Orchestration plan | `workspace`, `goal`, optional `source_client`, optional `context_files` | Creates a supervised local queue with one owner agent per task; no file edits are applied. |
| Orchestration step | `workspace`, optional `task_id`, `action`, optional `approval`, `summary`, `affected_files`, `validation_command` | File edits, build/test/lint commands, package installs, and cloud context remain approval-gated. |
| Jobs run | `workspace`, optional `job_id`, optional `trigger`, optional `run_due`, optional `approval` | Jobs scan, summarize, report, and recommend automatically; build/test/lint commands and other risky actions require approval. |
| Quality snapshot | `workspace` | Records `.aegis/health-history.json` and generated quality reports only; no source edits, build commands, package installs, or cloud calls. |
| Knowledge query | `workspace`, `query`, optional `focus` | Answers deterministic graph questions using local `.aegis` and scan data; no model call or source edit. |
| Validation | `workspace`, optional `run`, optional `command` | Core executes only safe validation commands. |
| Continue/repair | `workspace`, optional `request` for continue | Plan-only; no file edits. |

## Phase 1 Implemented Boundary

Website now has a small optional Core bridge:

- Module: `website/backend/aegis_ai/core_bridge.py`
- Endpoint: `GET /api/core-runtime`
- Config: `AEGIS_CORE_API_URL`, default `http://127.0.0.1:8788`

The bridge reads:

- `/v1/health`
- `/v1/models`
- `/v1/settings`
- `/v1/memory`
- `/v1/diagnostics`
- `/v1/ecosystem/dashboard`

It does not mutate Core state and does not replace existing Website `/api` workflows. If Core is unavailable, Website returns a degraded Core status rather than failing app health.

## Unified Contract Phase

This phase adds versioned contract metadata without changing existing client URLs:

- Core envelopes now include `contract_version: 2026.05.09`, `stability`, `deprecated`, and `deprecations`.
- `aegis_core.contracts` is the source of truth for shared request/response schemas.
- Website `GET /api/core-runtime` now reports the Core contract versions it observed.
- Website bridge adapters translate selected Core task, validation, and dashboard data into Website-friendly compatibility summaries for future `/api` shims.
- Contract tests validate all active `/v1` endpoint families and the schema-only patch/rollback shapes.

No active Website `/api` calls were replaced in this phase. The bridge and adapters are intentionally narrow so the mature frontend contract stays stable.

## Website Runtime Adapter Phase

The Website backend now uses the Core bridge for the first low-risk `/api` route group:

- `GET /api/health` and `GET /api/ready` read Core health, models, settings, and diagnostics to report shared-runtime adapter status while preserving `RuntimeHealthResponse`.
- `GET /api/models` overlays Core `/v1/models` inventory onto the Website model adapter response without replacing the Website provider registry.
- `GET /api/config` reads Core `/v1/settings` and reports adapter status while preserving Website `.env` settings.
- `POST /api/config` saves Website `.env` first, then best-effort syncs shared model settings to Core `/v1/settings`.
- `GET /api/core-runtime` remains the full read-only Core bridge for health, models, settings, memory, diagnostics, and dashboard envelopes.

Core offline or incompatible responses produce degraded adapter status instead of failing the frontend. The Website frontend continues to call existing `/api` routes and can ignore the additive Core status fields.

This phase still holds workspace scan, roadmap, memory CRUD, validation/repair, task graph, chat, apply, checkpoint restore, project builder, model routing, auth, and Creative Studio in Website `/api`.

## Cleanup Phase Decision

No runtime code was removed in the cleanup pass. Remaining duplicate logic is either:

- a backwards-compatible `/api` contract consumed by the React UI or Desktop app;
- an offline fallback path used by a migrated client;
- an IDE-specific context, apply, or rollback implementation;
- a Website product workflow that is still too rich or UI-coupled to move safely.

The removal path is now governed by `DEPRECATION_PLAN.md`.

## Migration Strategy

1. Keep Website `/api` stable and backwards compatible.
2. Route shared read-only status through Core first: health, models, settings, memory, diagnostics, dashboard.
3. Add client-specific contract tests before changing clients.
4. Migrate write flows only after the read contracts are stable: shared tasks, settings update, validation.
5. Keep rich orchestration in Website until a clear cross-client contract exists.
6. Prefer bridge/adapters over direct imports from Website into Core. Core must stay independent of Website backend internals.

## Do Not Migrate Yet

- Chat execution and streaming.
- Apply/checkpoint restore.
- Model routing/provider registry/benchmarks.
- Project builder/scaffolding.
- Creative Studio.
- Auth/accounts/sessions.
- Productization, adaptive intelligence, autonomous engineering, distributed runtime.

These systems are either product-specific, UI-coupled, or still changing too quickly to become shared Core contracts.

## Required Tests For Future Migrations

Every migrated subsystem needs:

- Core endpoint-family tests.
- Website bridge tests.
- Desktop/VS Code/Visual Studio contract tests or smoke checks.
- Backwards compatibility tests for existing Website `/api` and Desktop API calls.
- A degraded-mode test where Core is offline or returns a non-`/v1` response.
