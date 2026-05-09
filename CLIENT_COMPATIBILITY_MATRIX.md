# Client Compatibility Matrix

Last updated: 2026-05-09

Core API version: `/v1`  
Core contract version: `2026.05.09`  
Canonical schemas: `aegis-core/aegis_core/contracts.py`

## Contract Rules

- Every active Core `/v1` success response uses the Core envelope: `ok`, `api_version`, `contract_version`, `kind`, `workspace`, `data`, `stability`, `deprecated`, and `deprecations`.
- Current clients read only the fields they need. Unknown fields are safe to ignore.
- Optional `data` fields may be absent. Compatibility tests cover minimal envelopes for Desktop, VS Code, and Visual Studio parsing assumptions.
- Migrated clients must validate `api_version: v1` and the expected `kind` before treating a Core response as authoritative.
- Mutating/sync calls such as client registration and task updates must treat `ok: false` as degraded sync and surface the Core error detail.
- `stable` means safe for existing clients to depend on.
- `experimental` means the shape exists and is tested, but may gain fields or be refined.
- `schema-only` means the model is defined for compatibility planning, but no Core endpoint is active yet.
- No active contract is deprecated in this phase.

## Endpoint Matrix

| Core endpoint | Contract kind | Stability | Desktop App | Website backend | VS Code extension | Visual Studio extension |
| --- | --- | --- | --- | --- | --- | --- |
| `GET /v1/health` | `health` | stable | Not direct today | `/api/core-runtime` and `/api/health` adapter | Direct health check | Direct health check |
| `GET /v1/models` | `models` | stable | Via dashboard model status | `/api/core-runtime` and `/api/models` adapter | Direct model inventory, Ollama fallback | Not direct today |
| `GET /v1/providers` | `model.providers` | experimental | Not direct today | Future adapter candidate | Not direct today | Not direct today |
| `POST /v1/models/route` | `model.route` | experimental | Not direct today | Future routing bridge candidate | Future route preview candidate | Future health/route preview candidate |
| `POST /v1/models/completions` | `model.completion` | experimental | Not direct today | Future gated provider candidate | Not direct today | Not direct today |
| `POST/DELETE /v1/providers/{provider_id}/key` | `provider.key.status` | experimental | Not direct today | Future settings bridge candidate | Not direct today | Not direct today |
| `GET /v1/settings` | `settings` | stable | Not direct today | `/api/core-runtime` and `/api/config` adapter | Direct health/settings check | Not direct today |
| `POST /v1/settings` | `settings.updated` | stable | Not direct today | Best-effort sync after `POST /api/config` | Not direct today | Not direct today |
| `POST /v1/workspaces/scan` | `workspace.scan` | stable | Not direct today | Future bridge candidate | Direct scan metadata, local scan fallback | Not direct today |
| `POST /v1/workspaces/roadmap` | `workspace.roadmap` | stable | Not direct today | Future bridge candidate | Direct project roadmap, local model fallback | Not direct today |
| `GET /v1/memory` | `memory.summary` | stable | Via dashboard roadmap/diagnostics surface | Read through `/api/core-runtime` | Direct memory context, local `.aegis` fallback | Not direct today |
| `GET /v1/diagnostics` | `diagnostics.summary` | stable | Via dashboard diagnostics surface | Read through `/api/core-runtime` | Direct health/diagnostics check | Not direct today |
| `GET /v1/branding` | `branding.tokens` | experimental | Via dashboard branding | Not direct today | Not direct today | Not direct today |
| `POST /v1/clients/register` | `client.registered` | stable | Direct registration | Future bridge candidate | Direct registration | Direct registration |
| `GET /v1/clients` | `clients.list` | stable | Via dashboard client count | Not direct today | Not direct today | Not direct today |
| `POST /v1/tasks` | `task.created` | stable | Not direct today | Future task mirror candidate | Direct task create | Not direct today |
| `GET /v1/tasks` | `tasks.list` | stable | Via dashboard active/recent task counts | Not direct today | Not direct today | Not direct today |
| `POST /v1/tasks/{task_id}/status` | `task.updated` | stable | Not direct today | Future task mirror candidate | Direct task status update | Not direct today |
| `POST /v1/orchestration/plan` | `orchestration.plan` | experimental | Future supervised-goal UI candidate | Future bridge candidate, keep `/api` workflows intact | Future supervised agent-mode candidate | Future supervised agent-mode candidate |
| `GET /v1/orchestration` | `orchestration.dashboard` | experimental | Future dashboard panel candidate | Future `/api/core-runtime` summary candidate | Future status panel candidate | Future tool window status candidate |
| `POST /v1/orchestration/step` | `orchestration.step` | experimental | Future approval UI candidate | Future bridge candidate only after frontend approval UI exists | Future approval step candidate | Future approval step candidate |
| `POST /v1/validation` | `validation` | stable | Via dashboard validation commands | Future validation bridge candidate | Direct validation run, local terminal fallback on Core connection failure | Not direct today |
| `POST /v1/agent/continue` | `agent.continue.plan` | experimental | Not direct today | Future plan-only bridge candidate | Not direct today | Not direct today |
| `POST /v1/agent/repair` | `agent.repair.plan` | experimental | Not direct today | Future plan-only bridge candidate | Not direct today | Not direct today |
| `GET /v1/ecosystem/dashboard` | `ecosystem.dashboard` | stable | Direct dashboard read | Read through `/api/core-runtime` | Not direct today | Not direct today |

## Schema-Only Matrix

| Contract kind | Stability | Current consumers | Notes |
| --- | --- | --- | --- |
| `patch.proposal` | experimental schema-only | none | Defines a future shared proposal shape. VS Code and Visual Studio still own their current IDE-specific proposal/apply UX. |
| `rollback.entry` | experimental schema-only | none | Defines a future shared rollback checkpoint listing shape. Website and IDE rollback remain client/application-owned. |
| `rollback.result` | experimental schema-only | none | Defines a future shared rollback result shape. No Core rollback endpoint is active yet. |

## Client Notes

### Desktop App

Current direct Core calls:

- `POST /v1/clients/register`
- `GET /v1/ecosystem/dashboard?workspace=...`

Compatibility expectation:

- Validates `client.registered` and `ecosystem.dashboard` envelopes before trusting Core sync/dashboard data.
- Can parse dashboard envelopes with missing optional dashboard fields.
- Keeps using Website `/api` for mature chat, apply, validation, checkpoint, routing, and project-builder workflows.
- Should continue gracefully if Core is offline.

### Website Backend

Current Core bridge:

- `GET /api/core-runtime` reads `health`, `models`, `settings`, `memory.summary`, `diagnostics.summary`, and `ecosystem.dashboard`.
- `GET /api/health` and `GET /api/ready` read low-risk Core runtime status and preserve the Website health shape.
- `GET /api/models` overlays Core model inventory with Website provider inventory and preserves the Website model shape.
- `GET /api/config` reads Core settings adapter status and preserves Website `.env` config values.
- `POST /api/config` saves Website config first, then best-effort syncs shared model settings to Core.

Compatibility expectation:

- Does not require Core for `/api/health`, `/api/chat`, `/api/apply`, `/api/validate`, or frontend startup.
- Preserves Core envelopes in bridge output.
- Uses adapter helpers for Core task, validation, and dashboard summaries before any `/api` format shim is added.
- Additive Core adapter fields are optional and may be ignored by older frontend/Desktop clients.

### VS Code Extension

Current direct Core calls:

- `GET /v1/health`
- `GET /v1/models`
- `GET /v1/settings`
- `POST /v1/workspaces/scan`
- `POST /v1/workspaces/roadmap`
- `GET /v1/memory`
- `GET /v1/diagnostics`
- `POST /v1/clients/register`
- `POST /v1/tasks`
- `POST /v1/tasks/{task_id}/status`
- `POST /v1/validation`

Compatibility expectation:

- Task creation reads `data.id`; other fields are optional for current behavior.
- Registration and task-sync responses must match the expected Core envelope and `ok` state.
- Registration failures are logged and skipped rather than blocking IDE workflows.
- Core health/models/settings/scan/roadmap/memory/diagnostics/validation failures degrade to existing VS Code local or direct Ollama fallbacks where available.
- Hybrid model router endpoints are not consumed yet; when adopted, VS Code must show Core `context.included_files`, `context.blocked_files`, warnings, and require explicit approval before cloud fallback.
- Orchestration endpoints are not consumed yet; when adopted, VS Code must keep diff preview/apply/rollback local to the extension and use Core only for staged queue state, approval metadata, validation summaries, and memory updates.
- Proposal, apply, rollback, and workspace-specific UX remain extension-owned.

### Visual Studio Extension

Current direct Core calls:

- `GET /v1/health`
- `POST /v1/clients/register`

Compatibility expectation:

- Health requires the expected Core `health` envelope.
- Registration requires the expected `client.registered` envelope and `ok` state.
- Registration failures surface as health-check warnings.
- Solution detection, selected code review, build/error workflow, approval, rollback, and local intelligence remain extension-owned.

## Next Migration Candidates

Low-risk candidates:

- Website task graph can mirror or link Core `tasks.list` records without replacing SQLite task history.
- Visual Studio can add read-only `workspace.scan`, `workspace.roadmap`, and `validation` calls.
- Desktop smoke can assert Core dashboard loaded/degraded fields in the UI.
- Website workspace scan and validation can consume Core summaries as hints without replacing Website orchestration.

Hold candidates:

- Chat, streaming, model routing, generated changes, apply, checkpoint restore, repair execution, project builder, Creative Studio, auth/session, and advanced product workflows remain Website or client-owned until their contracts stop changing.
- Local client rollback/apply implementations remain active until Core rollback moves from schema-only to active tested endpoints.
