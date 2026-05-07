# Auralith OS Stabilization Roadmap

Last updated: May 7, 2026

This document captures the current stabilization pass for the public website plus protected Auralith OS app shell. The goal is not feature expansion. The goal is to keep the platform fast, reliable, explainable, polished, and safe to trust every day.

## Audit Scope

The stabilization pass covered:

- Public-to-protected route flow.
- Authentication bootstrap for automated tests.
- Protected app shell routing and sidebar navigation.
- Project history and saved session interactions.
- Model selector and settings modal behavior.
- Streaming chat cancellation.
- Workspace setup/profile API contracts.
- Config mutation and restore safety.
- Validation command inference.
- Generated diff/apply/read flows.
- Compact laptop/mobile app shell behavior.
- Public marketing/auth route responsiveness.
- Initial bundle shape and optional panel loading.
- Lazy-surface crash containment.
- Live frontend/backend identity checks.
- Frontend unit tests, production build, and backend pytest suite.

## Fixes Completed

- Updated E2E bootstrapping so protected app tests register a throwaway account and enter `/app` instead of assuming the public homepage is the workspace.
- Added E2E failure artifacts for future debugging: screenshot, HTML, and text summary are written to the temporary test workspace when a browser test fails.
- Fixed a workspace-open race where delayed project file refreshes could pull the user back into the session view after they had navigated elsewhere.
- Fixed model settings routing so opening model settings from the header lands on the Models tab instead of being reset by the `/app/settings` route effect.
- Fixed settings modal close behavior so closing from `/app/settings` returns to `/app` and does not leave a stale route/modal combination.
- Fixed saved session rail layout on shorter viewports by allowing the rail to keep natural height and visible overflow.
- Fixed saved session delete hit targets by making session rows full-width two-column grids with the delete action above neighboring interactive layers.
- Aligned user-facing language around Auralith OS, Auralith Prime, sessions, and Aegis Core across runtime summaries, transcripts, validation scripts, and E2E checks.
- Aligned streaming stop language to `Session request stopped.` in both UI behavior and E2E expectations.
- Added compact app-shell layout behavior so the sidebar becomes a bounded top rail and the right observability column is suppressed on narrow viewports.
- Added E2E resize coverage for laptop and mobile widths, including horizontal-overflow detection and command-input visibility checks.
- Lazy-loaded public-site, observability, memory, and approval-control panels so optional surfaces no longer ship in the initial app chunk.
- Split React and icon vendor code into stable Vite chunks.
- Removed an unreachable legacy settings modal block from `App.tsx`.
- Added a reusable lazy-panel error boundary so public-site, observability, memory, and approval surfaces fail into retryable UI instead of blanking the shell.
- Added public website E2E coverage for home, features, pricing, security, login, and register routes on a mobile viewport.

## Current Validation Baseline

The following checks passed in this stabilization pass:

- `npm run validate`
- `powershell -ExecutionPolicy Bypass -File .\website\scripts\doctor-web.ps1 -FrontendUrl http://127.0.0.1:5177 -BackendUrl http://127.0.0.1:8793`
- `powershell -ExecutionPolicy Bypass -File .\website\scripts\smoke-web.ps1 -FrontendUrl http://127.0.0.1:5177 -BackendUrl http://127.0.0.1:8793`
- `powershell -ExecutionPolicy Bypass -File .\website\scripts\e2e-web.ps1 -FrontendUrl http://127.0.0.1:5177 -BackendUrl http://127.0.0.1:8793`

Validation details:

- Frontend unit tests: 119 passed.
- Frontend production build: passed.
- Backend tests: 494 passed, 108 subtests passed.
- Live doctor check: passed.
- Live smoke check: passed.
- Browser E2E: passed, including public mobile route checks and protected laptop/mobile responsive shell checks.

Known warning:

- Vite still reports one generated JavaScript chunk above 500 kB. The initial app chunk remains far below the original baseline but is currently about 509.9 kB after adding lazy-surface error containment. Removing the warning cleanly requires more behavior-preserving extraction from `App.tsx`, not simply hiding the warning.

## Critical Next Fixes

- Extract the largest protected workspace sections from `App.tsx` into dedicated modules so route-level code splitting can finish the initial bundle reduction without hiding warnings.
- Extend responsive E2E coverage to the settings modal, authenticated overlays, and tablet-specific dimensions.
- Add a focused visual regression pass for the public site, protected workspace shell, right observability panel, and auth pages.
- Add auth-session cleanup or database isolation for repeated E2E account registration runs.
- Standardize script default ports or document the live validation port strategy to avoid confusion between `5173/8787` defaults and active `5177/8793` runs.

## High-Priority Refinements

- Continue extracting `App.tsx` into stable components without changing behavior: app shell, sidebar, settings modal, command surface, project history, observability panel, and workspace center.
- Memoize derived sidebar/history collections and expensive panel data to reduce avoidable React rerenders during streaming and rapid navigation.
- Add explicit loading, retry, and empty states to workspace file refreshes, task timelines, memory panels, and model provider status.
- Tighten streaming state transitions so stop, retry, provider fallback, and network interruption states remain visually and semantically distinct.
- Add regression tests for route/modal interactions so `/app/settings`, header actions, and sidebar navigation cannot desync again.

## Medium-Priority Refinements

- Create a small polished UI primitive layer for buttons, panels, badges, field shells, status rows, and empty states.
- Add stress coverage for long saved-session histories and large workspace file lists.
- Add browser checks for rapid model switching while a stream is pending.
- Add backend contract snapshots for auth responses, config update responses, workspace setup, validation, and streaming event shapes.
- Review telemetry panels for density and remove or collapse low-signal noise by default.

## Architecture Stewardship

- Keep the stable app shell intact. Changes should improve modularity and polish without moving core workflows unpredictably.
- Avoid feature expansion until the current workflows feel consistently fast, trustworthy, and clear.
- Keep Auralith OS as the public product, Auralith Prime as the assistant identity, and Aegis Core as the runtime identity.
- Preserve existing backend endpoints, desktop client expectations, config formats, SQLite schemas, streaming behavior, validation behavior, checkpointing, rollback, and provider registry behavior.

## Performance Budget Targets

- Initial protected app route should become code-split enough to remove the current Vite chunk warning.
- Sidebar interactions should feel immediate during streaming and large history states.
- Workspace file refreshes should avoid blocking route changes.
- Background observability updates should not visibly disturb the active command/session workflow.

## Product Quality Standard

Auralith OS should feel cohesive and calm under stress. The highest-value improvements are the ones that make existing workflows more dependable: faster startup, clearer task state, cleaner recovery from errors, sharper context, lower visual noise, and fewer surprises.
