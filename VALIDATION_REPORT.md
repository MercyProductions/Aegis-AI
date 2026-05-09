# Validation Report

Date: 2026-05-09  
Scope: focused stabilization of Website `/api`, Aegis Core `/v1`, Desktop, VS Code extension, Visual Studio extension, startup scripts, and dirty repo handling.

## Summary

Overall result: pass with interactive-client caveats.

The mature Website `/api` backend, frontend tests/build, Aegis Core `/v1` contracts, VS Code packaging, Visual Studio VSIX packaging, and Desktop build/smoke all passed. Two high-impact runtime bugs were fixed:

- `website/launch.ps1` failed to restart a same-project stale backend whose health `app` value still used the old name `Aegis Coding AI`, causing a duplicate bind attempt on 8787.
- `/api/productization` crashed when live telemetry existed because productization metrics read model-attempt fields directly from `ModelAttemptTelemetryEntry` instead of its nested `attempt` payload.

## Automated Tests Run

| Area | Command or check | Result |
| --- | --- | --- |
| Aegis Core tests | `python -m pytest tests -q` from `aegis-core` | Passed: 45 tests |
| Website backend | `npm run backend:test` from `website` | Passed: 764 tests, 155 subtests |
| Productization targeted regression | `python -m pytest backend/tests/test_productization.py -q` | Passed: 5 tests |
| Website frontend tests | `npm test -- --run` from `website` | Passed: 21 files, 169 tests |
| Website frontend build | `npm run build` from `website` | Passed, with existing Vite large-chunk warning |
| VS Code extension compile | `npm run compile` | Passed |
| VS Code extension package | `npm run package` | Passed, produced `release/aegis-local-autopilot-0.1.1.vsix` |
| VS Code clean install smoke | `code --install-extension ... --force` into temp dirs | Passed, listed `aegis.aegis-local-autopilot@0.1.1` |
| Visual Studio extension package | `powershell -File .\build.ps1` | Passed, produced `release/AegisLocalAgentVs.vsix` |
| Desktop build | `powershell -File .\build.ps1` | Passed, 0 warnings, 0 errors |
| Desktop smoke | `scripts\smoke-desktop.ps1 -UseIsolatedAppData` | Passed, captured nonblank login/setup/dashboard and backend ready before/after |

## Live API Validation

### Website `/api`

Validated against a disposable workspace under `.tmp`:

- `/api/health`: ready, app `Auralith OS`.
- `/api/files`: workspace scan/list returned files.
- `/api/routing/preview`: selected `ollama:qwen3-coder-30b`.
- `/api/chat`: returned task `b0de2bda-142b-4847-8537-deafbee42b12`.
- `/api/apply`: applied `update: app.txt`.
- `/api/restore-checkpoint`: restored `app.txt` to its original contents.
- `/api/validate`: learned and ran `npm test`, exit code 0.
- `/api/project-builder/plan`: returned a valid static app plan.
- `/api/productization`: returned HTTP 200 after the telemetry nesting fix.

### Aegis Core `/v1`

Validated live on `http://127.0.0.1:8788` against a disposable workspace:

- `GET /v1/health`
- `GET /v1/models`
- `GET /v1/settings`
- `POST /v1/settings`
- `POST /v1/workspaces/scan`
- `POST /v1/workspaces/roadmap`
- `GET /v1/memory`
- `GET /v1/diagnostics`
- `GET /v1/branding`
- `POST /v1/clients/register`
- `GET /v1/clients`
- `POST /v1/tasks`
- `POST /v1/tasks/{task_id}/status`
- `GET /v1/tasks`
- `POST /v1/validation`
- `POST /v1/agent/continue`
- `POST /v1/agent/repair`
- `GET /v1/ecosystem/dashboard`

All returned the expected `api_version: v1` envelope and endpoint `kind`.

## Desktop/Core Integration

Validated:

- Desktop build succeeded.
- Desktop GUI smoke launched the native executable and captured nonblank login/setup/dashboard screens.
- Desktop saw Website backend ready before and after smoke.
- Aegis Core was started on 8788 after removing a stale same-project Website backend that had been occupying the Core port.
- Core client registration and ecosystem dashboard calls returned shared clients, tasks, model status, diagnostics, roadmap, validation summary, and branding.

Known caveat:

- The smoke script validates Desktop UI rendering and Website backend reachability. It does not yet assert Desktop's Core dashboard fields from inside the GUI. Core dashboard was validated through the same `/v1` endpoints the Desktop client calls.

## VS Code Extension Validation

Validated:

- JavaScript syntax compile.
- Release package creation.
- Clean install into isolated VS Code user-data/extensions directories.
- Core endpoints used by the extension are live and passing: health, client registration, task create, task status.
- Ollama is reachable and Core reports the selected local model.

Known caveat:

- Interactive VS Code commands such as current-file review, propose patch, approve/apply, rollback, and health-check UI were not clicked in an extension host during this pass. Packaging and endpoint contracts passed.

## Visual Studio Extension Validation

Validated:

- Solution restore/build/package through `dotnet msbuild`.
- VSIX manifest/package checks from the build script.
- Core endpoints used by the extension are live and passing: health and client registration.

Known caveat:

- Visual Studio UI workflows such as tool-window load, selected-code review, build Error List repair, roadmap generation, approval, rollback, and Core sync were not manually clicked in Visual Studio during this pass.

## Dirty Repo Handling

- Preserved tracked inspiration PNG files by restoring the pre-existing deletions.
- Kept `.gitignore` update for `.aegis/`, which is generated local runtime memory and should not be committed.
- Generated `.tmp`, `smoke-artifacts`, `stress-artifacts`, `website/logs`, `website/data`, `website/workspace`, `x64`, build output, frontend `dist`, and release package outputs are ignored or already part of release folders as appropriate.

## Fixes Made

- Added root architecture docs:
  - `SYSTEM_ARCHITECTURE.md`
  - `CLIENT_RESPONSIBILITIES.md`
  - `API_BOUNDARIES.md`
- Added Aegis Core endpoint-family smoke coverage in `aegis-core/tests/test_core_contracts.py`.
- Hardened `aegis-core/scripts/start-core.ps1` so 8788 conflicts report a clear "not Aegis Core /v1" error.
- Fixed `website/launch.ps1` stale same-project backend restart logic.
- Fixed Website productization telemetry metric access.
- Added a regression test for nested model-attempt telemetry in productization metrics.

## Remaining Risk

- There is still architectural overlap: Website `/api` owns mature rich workflows while Core `/v1` owns only the smaller shared runtime. That split is now documented, but not yet fully migrated.
- VS Code and Visual Studio full interactive workflows still need manual IDE smoke passes.
- Desktop Core dashboard rendering should get a script-level assertion once the smoke tool can read or image-match the relevant panel state.
- Website repair flow was covered by backend tests and validation smoke, but not by a live model-driven repair smoke in this pass.

## Recommended Next Step

Add small client smoke commands that can be run headlessly or semi-headlessly:

- VS Code extension host smoke that runs `Aegis: Run Health Check`, generates a roadmap in a disposable workspace, applies a tiny approved patch, and rolls it back.
- Visual Studio experimental instance smoke that opens a tiny solution and verifies tool window, health, solution detection, and rollback.
- Desktop smoke assertion for Core dashboard loaded/degraded states.

## Runtime Consolidation Phase 1

Date: 2026-05-09

Changes validated:

- Added `website/backend/aegis_ai/core_bridge.py` as a read-only Website-to-Core adapter.
- Added `GET /api/core-runtime` to surface Core `/v1` health, models, settings, memory, diagnostics, and dashboard envelopes through Website `/api`.
- Added `AEGIS_CORE_API_URL` to Website settings and `.env.example`.
- Added Core contract coverage for known Desktop, VS Code, and Visual Studio client payloads.
- Added consolidation docs: `RUNTIME_CONSOLIDATION.md` and root `API_REFERENCE.md`.

Tests run:

| Area | Command or check | Result |
| --- | --- | --- |
| Website Core bridge | `python -m pytest backend/tests/test_core_bridge.py -q` | Passed: 4 tests |
| Aegis Core contracts | `python -m pytest tests/test_core_contracts.py -q` | Passed: 46 tests |
| Website focused config/health | `python -m pytest backend/tests/test_runtime_health.py backend/tests/test_config_update.py -q` | Passed: 3 tests |
| Website backend suite | `npm run backend:test` | Passed: 768 tests, 155 subtests |
| Website frontend tests | `npm test -- --run` | Passed: 21 files, 169 tests |
| Website frontend build | `npm run build` | Passed, with existing Vite large-chunk warning |
| Live Core bridge | `GET /api/core-runtime` against running Website 8787 and Core 8788 | Passed: 200, `health`, `ecosystem.dashboard` envelopes present |

No rich Website workflows were migrated in this phase.

## Unified Contract + Client Compatibility Phase

Date: 2026-05-09

Changes validated:

- Added the shared Core contract package at `aegis-core/aegis_core/contracts.py`.
- Added `contract_version: 2026.05.09`, `stability`, `deprecated`, and `deprecations` to active `/v1` envelopes while preserving existing `ok`, `api_version`, `kind`, `workspace`, and `data`.
- Added schema coverage for health, models, settings, workspace scan, roadmap, memory, diagnostics, tasks, validation, continue/repair, patch proposals, and rollback.
- Added Website Core bridge adapters for Core dashboard, task, and validation compatibility summaries.
- Added `CLIENT_COMPATIBILITY_MATRIX.md` and updated API/runtime architecture docs.

Tests run:

| Area | Command or check | Result |
| --- | --- | --- |
| Aegis Core tests | `python -m pytest tests -q` from `aegis-core` | Passed: 50 tests |
| Website Core bridge targeted tests | `python -m pytest backend/tests/test_core_bridge.py -q` | Passed: 5 tests |
| Website backend suite | `npm run backend:test` from `website` | Passed: 769 tests, 155 subtests |
| Website frontend tests | `npm test -- --run` from `website` | Passed: 21 files, 169 tests |
| Website frontend build | `npm run build` from `website` | Passed, with existing Vite large-chunk warning |
| VS Code extension compile | `npm run compile` | Passed |
| VS Code extension package | `npm run package` | Passed, produced `release/aegis-local-autopilot-0.1.1.vsix` |
| Visual Studio extension package | `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1` | Passed, produced `release/AegisLocalAgentVs.vsix` |
| Desktop build | `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1` | Passed, 0 warnings, 0 errors |
| Website launcher | `powershell -NoProfile -ExecutionPolicy Bypass -File .\launch.ps1` from `website` | Passed; backend 8787 and frontend 5173 responded |
| Live Core/Website contract smoke | Disposable `.tmp/unified-contract-smoke` workspace against 8788 and `/api/core-runtime` | Passed; all active Core endpoint families returned `contract_version: 2026.05.09` |

Compatibility coverage added:

- Core contract validation for every active `/v1` endpoint family.
- Missing optional field compatibility checks for Desktop dashboard parsing, VS Code task ID parsing, and Visual Studio health JSON parsing assumptions.
- Schema-only validation for `patch.proposal`, `rollback.entry`, and `rollback.result`.
- Invalid request checks for missing required request bodies, unsupported task statuses, and missing task IDs.
- Website adapter tests for missing optional Core task/validation/dashboard fields.

Remaining caveats:

- VS Code and Visual Studio interactive commands were not clicked in an IDE host during this phase. Compile/package and direct Core endpoint compatibility passed.
- Desktop Core dashboard UI fields were not image/assertion-smoked; the Desktop build passed and the Core dashboard endpoint it reads passed live contract smoke.
- Patch proposal and rollback contracts are schema-only. Existing client-owned apply/rollback workflows were intentionally not migrated.
