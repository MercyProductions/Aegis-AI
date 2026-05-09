# Website Core Adapter

Last updated: 2026-05-09

## Purpose

The Website backend remains the Auralith OS product/application API on `/api`. Aegis Core is the shared runtime API on `/v1`.

This adapter phase starts routing low-risk Website runtime reads through Aegis Core while keeping the React frontend and Desktop app on their existing Website `/api` contracts.

## Adapter Module

Implementation: `website/backend/aegis_ai/core_bridge.py`

The adapter:

- normalizes `AEGIS_CORE_API_URL`;
- validates Core `api_version: v1`;
- validates the expected Core `kind`;
- preserves Core envelopes for `/api/core-runtime`;
- returns degraded adapter results instead of raising when Core is offline or incompatible;
- redacts secret-like query parameters, bearer tokens, URL credentials, and assignment-style secrets from Core adapter errors before they reach Website `/api` clients;
- provides narrow route helpers for health, models, settings, diagnostics, dashboard, and settings updates.

## Migrated Route Group

| Website route | Core calls | Frontend response compatibility | Fallback |
| --- | --- | --- | --- |
| `GET /api/health`, `GET /api/ready` | `/v1/health`, `/v1/models`, `/v1/settings`, `/v1/diagnostics` | Still returns `RuntimeHealthResponse` | Marks `status: degraded`, keeps `ready: true`, and adds recommendations while local Website health continues. |
| `GET /api/models` | `/v1/models` | Still returns `ModelInventoryResponse` | Uses Website model adapter inventory and annotates Core status when Core is unavailable. |
| `GET /api/config` | `/v1/settings` | Still returns `AppConfig` | Uses Website `.env` settings and reports Core settings adapter status. |
| `POST /api/config` | `/v1/settings` | Still accepts/returns Website config format | Saves Website `.env` first, then best-effort syncs shared model settings to Core. Core sync failure does not fail the Website config save. |
| `GET /api/core-runtime` | `/v1/health`, `/v1/models`, `/v1/settings`, `/v1/memory`, `/v1/diagnostics`, `/v1/ecosystem/dashboard` | Existing bridge wrapper | Returns `reachable: false`/errors when Core is unavailable. |

The compatibility response models now include optional Core adapter status fields:

- `core_runtime_reachable`
- `core_runtime_status`
- `core_contract_version`
- `core_runtime_message`

Existing frontend consumers can ignore these fields.

## Still Native To Website

These routes are intentionally not migrated in this phase:

- chat and streaming;
- generated change apply;
- checkpoint restore;
- workspace file reads;
- workspace scan/profile/readiness;
- roadmap/autopilot;
- validation and repair;
- Website task graph, artifacts, timeline, and approvals;
- model registry, model manager, benchmarks, and route policy;
- auth/session;
- Creative Studio/media;
- productization, autonomous engineering, distributed runtime, adaptive intelligence, and unified context.

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
2. Roadmap adapter: expose Core roadmap path/markdown through an additive Website field or bridge-only route.
3. Memory summary adapter: merge Core `.aegis` summary into Website memory dashboards without replacing Website memory CRUD.
4. Validation summary adapter: use Core command detection as a hint, while Website keeps advanced validation/repair orchestration.
5. Task mirror adapter: link Core task records to Website task graph without replacing SQLite task history.
