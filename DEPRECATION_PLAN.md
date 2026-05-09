# Deprecation Plan

Last updated: 2026-05-09

## Purpose

This plan tracks duplicated runtime logic after the first client and Website migrations toward Aegis Core `/v1`.

Nothing in this phase is removed just because Core has a matching endpoint. Old paths stay until usage, compatibility, and rollback tests prove they can be retired safely.

## Ownership Summary

| Area | Current duplication | Owner target | Current status |
| --- | --- | --- | --- |
| Models | Website provider inventory/routing, VS Code Ollama fallback, Core `/v1/models` | Core owns shared local model inventory; Website owns provider registry/routing | Adapter active for Website `/api/models`; VS Code uses Core with Ollama fallback. |
| Settings | Website `.env`, Core `.aegis/config.json`, client settings | Core owns cross-client shared settings; Website/client settings remain product/UI-owned | Website syncs model settings best-effort to Core; clients keep local UI preferences. |
| Diagnostics | Website observability/telemetry, IDE logs, Core log summaries | Core owns shared diagnostics summaries; Website/clients own app/IDE-specific diagnostics | Website reads Core diagnostics through adapter; no route removed. |
| Memory | Website memory CRUD/SQLite, Core `.aegis` summaries, IDE `.aegis` files | Core owns shared file-backed memory summaries; Website owns memory UX/CRUD and app telemetry | Read-only bridge only. No memory CRUD migration yet. |
| Indexing | Website workspace/profile/project intelligence, VS Code scanner, Visual Studio scanner, Core `WorkspaceScanner` | Core owns lightweight shared scan/index; clients own IDE context; Website owns rich intelligence | VS Code uses Core scan with local fallback. Website/Visual Studio still native. |
| Roadmap | Website/autopilot roadmaps, VS Code local roadmap, Visual Studio roadmap, Core roadmap | Core owns shared roadmap file; clients own UX and proposal flows; Website owns orchestration | VS Code uses Core roadmap with fallback. Others still native. |
| Validation | Website command runner/repair loop, VS Code runner, Visual Studio build integration, Core safe validation | Core owns safe validation primitive; Website/clients own advanced repair and build UX | VS Code can use Core validation with fallback. Website validation is native. |
| Tasks | Website SQLite task graph/artifacts/timeline, Core `.aegis/tasks.json`, VS Code task sync | Core owns cross-client lightweight tasks; Website owns rich task graph until mirrored | VS Code writes Core tasks. Website task mirror not started. |
| Rollback/apply | Website checkpoints, VS Code backups, Visual Studio backups, schema-only Core rollback | Clients/Website own rollback until Core has tested active endpoints | No active Core rollback endpoint. Do not deprecate client rollback. |

## Deprecated Adapter/Shim Candidates

These are candidates only. They are not removal approvals.

| Old API or logic | Replacement | Clients affected | Earliest safe action | Tests required before removal |
| --- | --- | --- | --- | --- |
| VS Code direct Ollama model inventory fallback | `GET /v1/models` | VS Code | Keep fallback until Core launch/install is reliable | VS Code extension-host online/offline model tests; Core install/startup smoke. |
| VS Code local workspace scan fallback | `POST /v1/workspaces/scan` | VS Code | Keep fallback through at least one more client migration | Disposable workspace scan parity tests; offline fallback tests. |
| VS Code local roadmap fallback | `POST /v1/workspaces/roadmap` | VS Code | Keep fallback until Core roadmap quality/parity is proven | Roadmap snapshot tests; extension-host roadmap workflow test. |
| Website `/api/models` native Ollama/provider-only inventory | Core-backed overlay plus Website registry | Website frontend, Desktop | Mark as adapter-backed now; do not remove provider registry | Frontend model selector tests; Desktop model panel smoke; Core offline fallback. |
| Website `.env` model settings as only source for local model status | `POST /v1/settings` best-effort sync | Website frontend, Desktop | Keep `.env` authoritative for Website app settings | Config save tests with Core online/offline; launch smoke. |
| Website workspace scan/profile-only indexing | `POST /v1/workspaces/scan` plus Website enrichment | Website frontend, Desktop | No deprecation yet | Scan parity tests; frontend workspace profile compatibility; Core offline fallback. |
| Website validation command detection only | `POST /v1/validation` summary as hint | Website frontend, Desktop | No deprecation yet | Validation recipe parity; repair loop tests; smoke-web with Core online/offline. |
| Website SQLite task history only | Core `tasks.list` mirror/link | Website frontend, Desktop | No deprecation yet | Task graph mirror tests; artifact/timeline compatibility; rollback/apply safety. |
| Visual Studio local solution scan/roadmap only | Core scan/roadmap read adapters | Visual Studio | No deprecation yet | VSIX host tests for solution detection, scan, roadmap, rollback. |
| Desktop Core dashboard-only usage | Direct Core health/models/tasks reads | Desktop | No deprecation yet | Desktop smoke assertions for Core connected/degraded panels. |

## Old APIs Still In Use

Keep these stable:

- Website `/api/health`, `/api/ready`, `/api/config`, `/api/models`.
- Website `/api/files`, `/api/workspace/*`, `/api/workspace/setup`, `/api/validate`, `/api/verify`, `/api/validation/profile`.
- Website `/api/chat`, `/api/chat/stream`, `/api/apply`, `/api/checkpoints`, `/api/restore-checkpoint`.
- Website `/api/tasks` and task artifacts/timeline/actions.
- Website `/api/memory`.
- Desktop calls to Website `/api` for mature app workflows.
- VS Code and Visual Studio local proposal/apply/rollback logic.

The replacement path is to add adapters first, then mirror/link data, then retire only the duplicate read or write once every current client has migrated.

## Safe Removal Timeline

| Phase | What can change | Removal allowed? |
| --- | --- | --- |
| Phase A: Current cleanup | Document ownership, add tests, keep all old APIs | No. |
| Phase B: Read adapter parity | Add Website scan/roadmap/memory/validation read adapters | No, except trivial unreachable helper code proven unused by tests and search. |
| Phase C: Mirror/link writes | Mirror Website tasks and selected validation summaries into Core | No, keep Website data source authoritative. |
| Phase D: Client parity | Desktop, VS Code, and Visual Studio all consume Core for shared reads with offline tests | Maybe remove duplicate read-only fallbacks case-by-case. |
| Phase E: Write ownership | Core write contracts have rollback, persistence, and recovery tests | Consider deprecating duplicate write paths with one release grace period. |

## Tests Required Before Any Removal

- Core contract tests for the replacement endpoint and malformed request behavior.
- Website adapter tests with Core online, Core offline, `ok: false`, wrong `api_version`, and wrong `kind`.
- Frontend tests/build proving additive fields or translated shapes stay compatible.
- Desktop smoke with Core online/offline.
- VS Code compile/package and extension-host smoke for migrated workflow.
- Visual Studio VSIX build/package and manual host smoke for migrated workflow.
- Rollback/apply tests for any workflow that can touch files.
- Launch smoke and `smoke-web.ps1` for Website route groups.

## Current Decision

No code was removed in this cleanup phase. The duplicated systems are still active compatibility surfaces, and several are user-facing rollback or repair safety paths. The correct next step is parity and fallback tests, not deletion.
