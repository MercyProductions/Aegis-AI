# Core And Website Ownership

Generated: 2026-05-21

This is the Phase 2 ownership map for the ChatBot project. Aegis Core is the shared runtime API on `/v1`; the Website backend is the product and compatibility API on `/api`.

Machine-readable source: `website/backend/aegis_ai/runtime_ownership.py`.

Runtime endpoint: `GET /api/runtime/ownership`.

Phase 25 evidence: `docs/CORE_WEBSITE_OWNERSHIP_EVIDENCE.md`.

Validation command: `scripts\test-core-website-ownership.ps1`.

## Decision Rule

New shared runtime behavior starts in Aegis Core. Website may expose it through `/api` compatibility wrappers so the React app, native desktop shell, and legacy clients keep their existing response shapes while they migrate.

Website-only behavior stays in Website when it is product UI, account/session UX, media/creative UX, app telemetry, or a compatibility response model that has no cross-client runtime need.

## Ownership Matrix

| Domain | Owner | Core routes | Website routes | Fallback policy |
| --- | --- | --- | --- | --- |
| Health/readiness | Compatibility | `/v1/health`, `/v1/security/status`, `/v1/release/compatibility` | `/api/health`, `/api/ready`, `/api/core-runtime`, `/api/runtime/delegation` | Website remains usable and marks shared runtime degraded. |
| Settings/config | Compatibility | `/v1/settings`, `/v1/settings/export`, `/v1/settings/import` | `/api/config`, `/api/settings/export`, `/api/settings/import` | Website saves app settings even when Core sync fails. |
| Memory | Compatibility | `/v1/memory`, `/v1/personal-memory`, `/v1/engineering/memory` | `/api/memory` | Website memory CRUD stays local while shared Core memory is unavailable. |
| Changes/apply | Aegis Core | `/v1/changes/propose`, `/v1/changes/apply` | `/api/apply`, `/api/diff/apply` | Website safe apply is compatibility fallback only. |
| Checkpoints/rollback | Aegis Core | `/v1/checkpoints/create`, `/v1/checkpoints`, `/v1/checkpoints/restore` | `/api/checkpoints`, `/api/restore-checkpoint` | Website checkpoint manager remains fallback until all clients use Core. |
| Validation | Aegis Core | `/v1/validation/run`, `/v1/validation` | `/api/validate`, `/api/verify`, `/api/validation/profile` | Website validation manager can run when Core is offline. |
| Model routing | Aegis Core | `/v1/models`, `/v1/providers`, `/v1/models/route`, `/v1/models/registry` | `/api/models`, `/api/routing/preview`, `/api/model-registry` | Website model inventory and preview remain fallback. |
| Provider accounts | Website | `/v1/providers`, `/v1/providers/{provider_id}/key` | `/api/provider-accounts`, provider-account child routes | Website owns setup UX and secure linking flows. |
| Model registry | Compatibility | `/v1/models/registry`, `/v1/models/routing-profiles` | `/api/model-registry`, `/api/model-benchmarks`, `/api/model-manager` | Website registry snapshots and benchmarks stay available. |
| Diagnostics | Compatibility | `/v1/diagnostics`, `/v1/ecosystem/dashboard`, `/v1/quality`, `/v1/quality-gates` | `/api/core-runtime`, `/api/telemetry`, `/api/quality-gates`, `/api/productization` | Website telemetry annotates Core adapter status. |
| Tasks/workflows | Compatibility | `/v1/tasks`, `/v1/workflows`, `/v1/engineering/executions` | `/api/tasks`, `/api/agent-supervision`, `/api/autonomous-engineering/objectives` | Website task graph records Core fallback mode. |
| Agent runtime | Aegis Core | `/v1/agents/runtime`, workflow agent routes | `/api/agent-supervision`, agent-supervision child routes | Website shows degraded supervision instead of separate agent state. |
| Workspace intelligence | Compatibility | `/v1/workspaces/scan`, `/v1/workspaces/roadmap`, `/v1/workspaces/intelligence`, `/v1/knowledge/search` | `/api/workspace/profile`, `/api/workspace-intelligence`, `/api/project-intelligence` | Website operations scans continue locally while Core knowledge adapters are unavailable. |

## Migration Rules

- Core-owned domains must add or extend `/v1` contracts first.
- Website adapters must preserve `/api` response compatibility and explicitly record Core fallback mode.
- Compatibility domains must name which parts are Core-owned and which parts remain Website-owned.
- Website-owned domains should not grow hidden shared-runtime behavior. If a second client needs the same behavior, promote the contract to Core.
- Client migration should be guarded by tests that cover Core `/v1`, Website `/api`, frontend `api.ts`, and extension Core clients.

## Current Client Posture

- React frontend uses Website `/api` as the compatibility surface.
- React frontend has a typed `getRuntimeOwnership` client for the ownership matrix.
- Native desktop still uses Website `/api` for several compatibility workflows while it also has direct Core paths for migrated runtime workflows.
- Visual Studio extension uses Core `/v1` for workspace scan, routing, proposed changes, apply, checkpoints, validation, workflows, and agent runtime.
- VS Code extension already uses Core `/v1/tasks` for task records and should migrate more shared workflow behavior through Core.
