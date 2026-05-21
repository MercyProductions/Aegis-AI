# Website Core Adapter

Last updated: 2026-05-12

## Purpose

The Website backend remains the Auralith OS product/application API on `/api`. Aegis Core is the shared runtime API on `/v1`.

This adapter phase starts routing low-risk Website runtime reads through Aegis Core while keeping the React frontend and Desktop app on their existing Website `/api` contracts.

The source-of-truth ownership map now lives in `docs/CORE_WEBSITE_OWNERSHIP.md` and the machine-readable Website matrix in `website/backend/aegis_ai/runtime_ownership.py`. The Website exposes that matrix at `GET /api/runtime/ownership`.

Phase 25 locks this boundary with `evals/phase25-core-website-ownership-contract.json` and `scripts\test-core-website-ownership.ps1`.

## Adapter Module

Implementation:

- `website/backend/aegis_ai/core_bridge.py` for the existing Website `/api/core-runtime` bridge.
- `website/backend/aegis_ai/services/core_client.py` for Core-first runtime workflow delegation helpers.

The adapter:

- normalizes `AEGIS_CORE_API_URL`;
- validates Core `api_version: v1`;
- validates the expected Core `kind`;
- preserves Core envelopes for `/api/core-runtime`;
- returns degraded adapter results instead of raising when Core is offline or incompatible;
- redacts secret-like query parameters, bearer tokens, URL credentials, and assignment-style secrets from Core adapter errors before they reach Website `/api` clients;
- provides narrow route helpers for health, models, model registry, model routing, settings, diagnostics, dashboard, and settings updates.
- provides Core-first runtime helpers for editing, checkpoints, validation, repair workflows, model routing, engineering execution creation/steps, engineering memory, engineering metrics, and workspace knowledge graph queries.

## Migrated Route Group

| Website route | Core calls | Frontend response compatibility | Fallback |
| --- | --- | --- | --- |
| `GET /api/health`, `GET /api/ready` | `/v1/health`, `/v1/models`, `/v1/settings`, `/v1/diagnostics` | Still returns `RuntimeHealthResponse` | Marks `status: degraded`, keeps `ready: true`, and adds recommendations while local Website health continues. |
| `GET /api/models` | `/v1/models` | Still returns `ModelInventoryResponse` | Uses Website model adapter inventory and annotates Core status when Core is unavailable. |
| `GET /api/model-registry` | `/v1/models/registry` | Still returns `ModelRegistryResponse` | Uses Website registry snapshot when Core is unavailable, and logs `model.registry` fallback mode. |
| `GET /api/config` | `/v1/settings` | Still returns `AppConfig` | Uses Website `.env` settings and reports Core settings adapter status. |
| `POST /api/config` | `/v1/settings` | Still accepts/returns Website config format | Saves Website `.env` first, then best-effort syncs shared model settings to Core. Core sync failure does not fail the Website config save. |
| `GET /api/core-runtime` | `/v1/health`, `/v1/models`, `/v1/settings`, `/v1/memory`, `/v1/diagnostics`, `/v1/ecosystem/dashboard` | Existing bridge wrapper | Returns `reachable: false`/errors when Core is unavailable. |
| `POST /api/autonomous-engineering/objectives` | `/v1/engineering/executions` | Still returns `AutonomousObjectiveDetail` | Creates the Website objective locally, then best-effort links a Core engineering execution ID; fallback keeps the Website objective when Core is unavailable. |
| `GET /api/quality-gates` | `/v1/quality-gates` | Compatibility dashboard payload | Shows current gate status, scores, blockers, and degraded Core status when offline. |
| `POST /api/quality-gates/evaluate` | `/v1/quality-gates/evaluate` | Compatibility evaluation payload | Delegates proposed change scoring to Core; Core safety blockers are not bypassed. |
| `GET/POST /api/benchmarks*` and `/api/evaluation-reports*` | `/v1/benchmarks*`, `/v1/evaluation-reports*` | Compatibility quality history payloads | Exposes Core benchmark and evaluation-report history to the Website UI. |
| `POST /api/routing/preview` | `/v1/models/route` | Still returns `RoutePreviewResponse` | Website builds the task/context preview, then maps the Core route decision back into existing model-attempt fields; Website route planning is fallback only. |
| `POST /api/apply` | `/v1/changes/apply` | Still returns `ApplyResponse` | Core applies approved changes first; Website safe apply remains fallback when Core is unavailable. |
| `GET/POST /api/checkpoints`, `POST /api/restore-checkpoint` | `/v1/checkpoints*` | Existing checkpoint response models | Core owns create/list/restore contracts; Website checkpoint manager remains compatibility fallback. |
| `POST /api/validate` | `/v1/validation/run` | Still returns `ValidateResponse` | Core validation runs first; Website validation manager remains fallback and repair orchestration host. |

The compatibility response models now include optional Core adapter status fields:

- `core_runtime_reachable`
- `core_runtime_status`
- `core_contract_version`
- `core_runtime_message`

Existing frontend consumers can ignore these fields.

## Knowledge Delegation Hooks

The Website service adapter now exposes Core knowledge helpers for future product routes:

- `knowledge_search` -> `POST /v1/knowledge/search`
- `knowledge_relationships` -> `POST /v1/knowledge/relationships`
- `knowledge_impact_analysis` -> `POST /v1/knowledge/impact-analysis`
- `knowledge_architecture_summary` -> `GET /v1/knowledge/architecture-summary`

These helpers are additive. Existing Website project-intelligence and adaptive-context routes remain native until the frontend has compatibility response models for graph search, relationship browsing, and impact/risk previews.

## Still Native To Website

These routes are intentionally not migrated in this phase:

- chat and streaming;
- advanced repair orchestration;
- workspace file reads;
- workspace scan/profile/readiness;
- roadmap/autopilot;
- knowledge graph search, relationship browsing, and impact-analysis UI routes;
- Website task graph, artifacts, timeline, and approvals;
- model registry write/provider CRUD, model manager, benchmarks, and route policy application;
- auth/session;
- Creative Studio/media;
- productization, autonomous objective iteration UI, distributed runtime, adaptive intelligence, and unified context.

## Engineering Execution Delegation

The Website autonomous-engineering create route now treats Core as the shared execution authority when available:

- Website creates the existing objective, phases, approval gates, simulations, and explanations to preserve `/api` compatibility.
- Website then calls `POST /v1/engineering/executions` with the objective goal and safety constraints.
- On success, Website stores `core_engineering_execution_id`, `core_workflow_id`, and `core_runtime_owner` in objective metadata.
- On failure or offline Core, Website records fallback mode and keeps using the existing Website autonomous engine.

The next Website migration should delegate objective iteration, validation/repair loop state, and apply/checkpoint workflow state to `POST /v1/engineering/executions/{execution_id}/step` while keeping current React response models stable.

## Fallback Rules

Core unavailable:

- Website backend stays usable.
- `/api/health` reports degraded shared runtime status rather than failing the app.
- `/api/models` keeps using Website model adapter inventory.
- `/api/config` keeps using Website `.env` settings.
- `/api/core-runtime` reports adapter errors without crashing.

Core incompatible:

- A response with a non-`v1` `api_version` or unexpected `kind` is treated as degraded adapter state.
- Website `/api` keeps returning its established response model.

Core/provider error text:

- Adapter errors are redacted before being returned through Website `/api`.
- Query-string keys such as `?key=...`, `?token=...`, bearer tokens, URL credentials, and common `api_key=...`-style assignments are replaced with redacted placeholders.

## Next Migration Candidates

Move only after this phase is stable:

1. Read-only workspace scan adapter: map Website `workspace_root` to Core `workspace` and compare Core scan metadata with Website profile data.
2. Knowledge graph adapter: expose Core architecture summaries, impact analysis, and relationship browsing through additive Website fields or bridge-only routes.
3. Roadmap adapter: expose Core roadmap path/markdown through an additive Website field or bridge-only route.
4. Memory summary adapter: merge Core `.aegis` summary into Website memory dashboards without replacing Website memory CRUD.
5. Validation summary adapter: use Core command detection as a hint, while Website keeps advanced validation/repair orchestration.
6. Autonomous objective iteration adapter: advance linked Core engineering executions and mirror validation/repair/checkpoint status into Website objective details.
7. Task mirror adapter: link Core task records to Website task graph without replacing SQLite task history.
