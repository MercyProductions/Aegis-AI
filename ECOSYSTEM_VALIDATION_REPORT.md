# Ecosystem Validation Report

Last updated: 2026-05-09

## Summary

The consolidated Auralith/Aegis ecosystem is stable enough for daily dogfooding with the current runtime boundary:

- Aegis Core `/v1` is the shared runtime for contracts, memory summaries, diagnostics, clients, tasks, roadmap, validation, and model/settings state.
- Website backend `/api` remains the mature product/application layer for chat, apply, checkpoint restore, task UX, memory CRUD, auth, and advanced workflows.
- Desktop, Website, and VS Code have practical daily-use validation coverage.
- Visual Studio VSIX build/package is valid; automated interactive tool-window load was not executed in this pass.

Recommended next release version: `0.1.2-rc.1`.

## What Passed

Startup:

- Aegis Core started on `http://127.0.0.1:8788`.
- Website backend started on `http://127.0.0.1:8787`.
- Website frontend started on `http://127.0.0.1:5173`.
- Ollama was reachable on `http://127.0.0.1:11434`.
- Website `/api/health` reported `status: ready`, `model_ready: true`, and `core_runtime_status: connected`.
- Desktop app built and launched through the smoke script, with nonblank login/setup/dashboard captures.

End-to-end workflows:

- Web smoke passed with a real chat turn.
- Website workspace setup, file listing, validation profile inference, diff compare, apply, read-back, validation, and readiness checks passed.
- Website UI E2E passed after fixing the route-mock matcher.
- Core workspace scan generated shared `.aegis` memory artifacts.
- Core roadmap generation produced shared roadmap tasks.
- Core memory summary exposed the generated roadmap.
- Website `/api/core-runtime` saw the same shared Core state.
- Website memory write/read passed through `/api/memory`.
- Website diff/apply/checkpoint restore passed.
- Website task create/approval flow returned a running approved task.

Cross-client/shared runtime checks:

- Core registered four RC clients: Website, Desktop, VS Code, and Visual Studio.
- Core dashboard listed the registered clients.
- Website `/api/core-runtime` exposed the Core dashboard state.
- Core settings, clients, tasks, roadmap, memory summary, diagnostics, validation, and continue plan endpoints returned valid envelopes.

Failure/degraded mode:

- Core offline: Website backend stayed ready and reported `core_runtime_status: unavailable`.
- Backend offline: Vite frontend stayed reachable with HTTP `200`, while backend API health was unreachable.
- Invalid workspace: Website `/api/files` returned `400` with a useful detail instead of an internal error.
- Simulated Ollama failure: workspace-local Core settings pointed to an invalid Ollama URL and `/v1/models` returned `reachable: false` with an error detail.
- Broken validation command: detected safe `npm test` failure returned nonzero validation results in both Core and Website without crashing.
- Rollback after failed edit: Website checkpoint restore restored the original tracked file.

Packaging/build:

- Aegis Core tests: `51 passed`.
- Aegis Core wheel build: passed for `aegis_core-0.1.0-py3-none-any.whl`.
- Aegis Core CLI health: passed.
- Website backend tests: `776 passed, 155 subtests passed`.
- Website frontend tests: `21 passed`, `169 tests passed`.
- Website frontend build: passed.
- Website smoke script: passed.
- Website UI E2E script: passed.
- VS Code extension lint/package: passed.
- VS Code VSIX install through `code --install-extension --force`: passed; installed id `aegis.aegis-local-autopilot`.
- Visual Studio extension build/package: passed; VSIX copied to `visual-studio-extensions/aegis-local-agent-vs/release/AegisLocalAgentVs.vsix`.
- Desktop build/smoke: passed with `0` warnings and `0` errors.

## What Failed And Was Fixed

1. Website UI E2E mocks only intercepted absolute backend URLs.

The app correctly uses the Vite `/api` proxy in dev. The E2E harness only mocked `http://127.0.0.1:8787/api/...`, so model and stream mocks could miss real app requests. The harness now uses shared globbed `/api/...` route helpers that catch both relative proxy calls and direct backend calls.

2. Invalid workspace paths returned `500`.

`WorkspaceManager.resolve_workspace()` allowed filesystem `mkdir()` failures to escape as server errors. Workspace creation failures now become `ValueError`, which the Website API wrapper returns as `400`.

## Known Limitations

- Visual Studio interactive tool-window load was not automated. The VSIX build/package, manifest version check, command resource check, and release copy all passed.
- Website memory CRUD is still Website-owned and is not mirrored into Core memory summaries yet.
- Core `patch.proposal`, `rollback.entry`, and `rollback.result` remain schema-only contracts. Active rollback remains Website/client-owned.
- The Website production build still emits a Vite chunk-size warning for the main app chunk; build output succeeds.
- Core blocks arbitrary validation command overrides by design. Use detected safe commands or configured validation preferences.

## Remaining Risks

- Visual Studio host smoke should be manually repeated after installing the VSIX into the target Visual Studio profile.
- Website task graph mirroring into Core has not started, so task consistency is not yet full two-way cross-client state.
- Desktop direct Core use is limited to dashboard/client registration style reads; mature workflows still rely on Website `/api`.
- Large model availability depends on the local Ollama installation. The RC pass found Ollama reachable with `qwen2.5-coder:7b` configured and many local models installed.

## Recommended Next Steps

- Dogfood `0.1.2-rc.1` daily with Core, Website, Desktop, and VS Code installed.
- Manually install and open the Visual Studio VSIX, then verify tool window load, solution detection, selected-code review, build/error workflow, approval, rollback, and Core health.
- Add automated Visual Studio host smoke coverage if the environment can run an experimental instance reliably.
- Add Website task mirror/read adapters only after daily use confirms the current RC is stable.
- Keep `/api` and `/v1` compatibility shims until another full RC validation pass proves each removal safe.
