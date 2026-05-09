# Ecosystem Stabilization Notes

This document tracks the practical quality pass for the Auralith ecosystem. The goal is reliability, consistency, and daily-driver usefulness, not new product expansion.

## Stabilization Scope

- Aegis Core remains the shared local runtime.
- Desktop, VS Code, Visual Studio, and Website keep their own UI and platform-specific responsibilities.
- Shared memory, settings, diagnostics, client registration, and task visibility should flow through Aegis Core when it is available.
- All edit workflows remain approval-based with backups and rollback.

## Cross-Client Smoke Matrix

| Area | Status | Notes |
| --- | --- | --- |
| Aegis Core health | Pass | `/v1/health` responds through FastAPI TestClient and CLI. |
| Ollama model routing | Pass | Core detects `qwen3-coder:30b` with configured fallbacks available. |
| Shared client registration | Pass | Desktop, VS Code, and Visual Studio now have Core registration paths. |
| Shared task visibility | Pass | VS Code creates and updates Core tasks during agent mode; Core dashboard displays active/recent tasks. |
| Desktop dashboard bridge | Pass | Desktop has `core_api_base_url` and an Auralith Ecosystem card backed by `/v1/ecosystem/dashboard`. |
| VS Code health check | Improved | Health check now warns when Aegis Core is offline and registers the VS Code client when Core is reachable. |
| Visual Studio health check | Improved | Health check now verifies Aegis Core and registers the Visual Studio client. |
| Website integration | Partial | Website has its own mature local backend. For this phase it remains documented as a client and should migrate incrementally to `/v1` Core contracts. |
| Workspace scan performance | Improved | Core scan results are cached when the workspace fingerprint is unchanged, skipping repeated expensive symbol/dependency/TODO passes. |
| Path safety | Improved | Core now evaluates ignored folders relative to the workspace and blocks secret-like filenames case-insensitively. |
| Shared settings | Improved | Core config loading falls back to defaults for malformed numeric, boolean, string-list, and blank string settings. |
| Shared task API | Improved | Bad task status updates return `400`; missing task IDs return `404`. |
| Memory resilience | Improved | Dashboard and task reads now tolerate unreadable `.aegis` JSON/markdown files. |
| Validation detection | Improved | Core now lists JS test/build validation commands only when matching package scripts exist. |
| Validation execution | Improved | Core blocks unsafe custom validation commands and returns structured missing-tool/timeout failures. |
| Diagnostics | Improved | Core dashboard now surfaces stale tasks and suggested actions. |

## Verification Run

Ran during this pass:

- `python -m pytest tests -q` in Aegis Core: 11 tests passed
- `python -m compileall aegis_core`: pass
- Aegis Core `/v1` TestClient smoke for settings, memory, diagnostics, roadmap, tasks, task status: pass
- Core scan twice: second scan returned `cache_hit: true`
- `npm run lint` in VS Code extension: pass
- `npm run package` in VS Code extension: pass, regenerated `release/aegis-local-autopilot-0.1.1.vsix`
- Desktop `.\build.ps1`: pass, 0 warnings, 0 errors
- Visual Studio extension `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Website frontend tests: 21 files / 169 tests passed
- Website frontend production build: pass, Vite reported the existing large main chunk warning
- Website backend tests: 739 tests and 155 subtests passed

## Fixes Made In This Pass

- Added VS Code setting: `aegisLocalAutopilot.coreUrl`.
- Added VS Code Core registration on startup and workspace-folder changes.
- Added VS Code Core task creation/status updates for agent proposals, approvals, and rejections.
- Added Visual Studio setting: `Aegis Core URL`.
- Added Visual Studio Core health/registration check to the native health command.
- Added Core scan cache through `.aegis/scan-cache.json`.
- Added Core dashboard stale-task detection and suggested actions.
- Hardened Core scan safety for mixed-case ignored folders, token/password/auth-like files, and Windows workspaces under temp-style parent directories.

## Daily Driver Friction To Watch

- If Core is offline, editor clients still work locally but shared task/dashboard sync is degraded.
- Website still uses its internal `/api` runtime. Avoid forcing a risky migration until the `/v1` Core contracts have been dogfooded longer.
- Core scan cache relies on a practical file-count/mtime/size fingerprint. It is fast and useful, but a future content-hash mode may be useful for unusual filesystems.
- Long-running agent tasks should be reviewed from the Desktop dashboard so stale work does not accumulate.

## Quality Rules

- Do not auto-apply edits across clients.
- Do not store secrets in shared memory or logs.
- Prefer small task records over broad ambiguous task state.
- Keep Core API responses stable and versioned under `/v1`.
- Treat unavailable Core as degraded mode, not a client crash.
