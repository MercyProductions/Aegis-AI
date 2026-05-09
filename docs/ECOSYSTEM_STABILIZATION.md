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
| Ollama model routing | Pass | Core detects `qwen3-coder:30b` with configured fallbacks available, and malformed URLs or model inventory payloads degrade to health/config diagnostics. |
| Shared client registration | Pass | Desktop, VS Code, and Visual Studio now have Core registration paths. |
| Shared task visibility | Pass | VS Code creates and updates Core tasks during agent mode; Core dashboard displays active/recent tasks. |
| Shared client registry resilience | Improved | Core normalizes malformed local client records before dashboard sorting. |
| Desktop dashboard bridge | Pass | Desktop has `core_api_base_url` and an Auralith Ecosystem card backed by `/v1/ecosystem/dashboard`. |
| VS Code health check | Improved | Health check now warns when Aegis Core is offline and registers the VS Code client when Core is reachable. |
| Visual Studio health check | Improved | Health check now verifies Aegis Core and registers the Visual Studio client. |
| Website integration | Partial | Website has its own mature local backend. For this phase it remains documented as a client and should migrate incrementally to `/v1` Core contracts. |
| Workspace scan performance | Improved | Core scan results are cached when the workspace fingerprint is unchanged, skipping repeated expensive symbol/dependency/TODO passes. |
| Workspace scan resilience | Improved | Core scans tolerate malformed package dependency metadata, BOM-prefixed `package.json` files, and files disappearing during scan sorting. |
| Path safety | Improved | Core now evaluates ignored folders relative to the workspace, blocks secret-like filenames case-insensitively, and rejects paths resolving outside the workspace. |
| Shared settings | Improved | Core config loading falls back to defaults for malformed values, unsafe memory directory names, and damaged `.aegis/config.json` paths. |
| Desktop settings | Improved | Backend and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before config writes or runtime requests. |
| VS Code settings | Improved | Ollama and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before model or shared-runtime requests. |
| Visual Studio settings | Improved | Ollama and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before model or shared-runtime requests. |
| Shared task API | Improved | Bad task status updates return `400`, missing task IDs return `404`, and malformed local task records are normalized on read. |
| Memory resilience | Improved | Dashboard/task reads, agent plan reads, and generated-memory writes now tolerate unreadable or damaged `.aegis` JSON/markdown paths. |
| VS Code memory resilience | Improved | Workspace startup and later index/history/log writes skip damaged `.aegis` paths instead of breaking scans or post-apply bookkeeping. |
| VS Code rollback safety | Improved | Rollback validates timestamp-like backup IDs, workspace roots, and backup file paths before restoring files; incomplete backup files are skipped with visible output details. |
| Visual Studio memory init | Improved | Solution memory reads and writes are best-effort, so damaged `.aegis` paths do not crash memory-backed workflows. |
| Visual Studio rollback | Improved | Backup manifests now carry explicit IDs, rollback rejects cross-solution manifests, and manifest/backup paths are validated before touching solution files. |
| Website workspace setup | Improved | Damaged `.aegis` project and validation profile paths now return warnings instead of breaking setup. |
| Website checkpoint restore | Improved | Restore now validates checkpoint IDs, damaged manifests, backup paths, and missing backup files before touching workspace files. |
| Website safe apply | Improved | Apply refuses to edit when checkpoint creation fails and reports later write/delete failures with checkpoint context. |
| Validation detection | Improved | Core now lists JS test/build validation commands only when matching package scripts exist. |
| Validation execution | Improved | Core blocks unsafe custom validation commands and returns structured missing-tool/start-failed/timeout failures. |
| Validation logging | Improved | Validation output is redacted before API responses and disk writes; log write failures do not crash validation. |
| Diagnostics | Improved | Core dashboard now surfaces stale tasks and suggested actions; diagnostic log write failures do not crash health checks. |

## Verification Run

Ran during this pass:

- `python -m pytest tests/test_core_contracts.py -q` in Aegis Core: 38 tests passed
- `python -m compileall aegis_core`: pass
- Core BOM-prefixed package framework detection regression test: pass
- Core malformed client registry regression test: pass
- Core malformed task record regression tests: pass
- Core outside-workspace path and symlink scan safety regression tests: pass
- Core workspace scan malformed package/stat-race regression tests: pass
- Core validation startup-failure regression test: pass
- Core Ollama URL normalization, API-path trimming, credential rejection, and malformed-health regression tests: pass
- Core malformed Ollama model inventory regression tests: pass
- Aegis Core `/v1` TestClient smoke for settings, memory, diagnostics, roadmap, tasks, task status, agent continue, and agent repair: pass
- Core scan twice: second scan returned `cache_hit: true`
- `npm run lint` in VS Code extension: pass
- VS Code memory-write hardening lint: pass
- VS Code rollback manifest hardening lint and package: pass
- VS Code rollback incomplete-backup hardening lint and package: pass
- `npm run package` in VS Code extension: pass, regenerated `release/aegis-local-autopilot-0.1.1.vsix`
- Desktop `.\build.ps1`: pass, 0 warnings, 0 errors
- Visual Studio extension `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Visual Studio rollback hardening `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Visual Studio rollback cross-solution/path hardening `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Website frontend tests: 21 files / 169 tests passed
- Website frontend production build: pass, Vite reported the existing large main chunk warning
- Website backend tests: 739 tests and 155 subtests passed
- Website workspace setup regression and helper tests for damaged `.aegis` paths: 8 tests passed
- Website checkpoint restore and apply safety tests: 53 storage tests passed
- Website backend `python -m compileall aegis_ai`: pass

## Fixes Made In This Pass

- Added VS Code setting: `aegisLocalAutopilot.coreUrl`.
- Added VS Code Core registration on startup and workspace-folder changes.
- Added VS Code Core task creation/status updates for agent proposals, approvals, and rejections.
- Added Visual Studio setting: `Aegis Core URL`.
- Added Visual Studio Core health/registration check to the native health command.
- Added Core scan cache through `.aegis/scan-cache.json`.
- Added Core dashboard stale-task detection and suggested actions.
- Hardened shared client registry loading so malformed client records, bad capabilities, and mixed timestamp types do not break dashboard sorting.
- Hardened shared task loading so malformed local task metadata and timestamps do not break dashboard or status workflows.
- Hardened Core scan safety for mixed-case ignored folders, token/password/auth-like files, and Windows workspaces under temp-style parent directories.
- Hardened Core read/edit safety so files resolving outside the workspace, including symlinked files, are excluded from scans.
- Hardened Core workspace scans against malformed `package.json` dependency shapes and file stat races during recent-file sorting.
- Hardened Core framework detection so UTF-8 BOM-prefixed `package.json` files still detect React/Vite/Next dependencies.
- Hardened shared Ollama URL settings so common local inputs are normalized, pasted API paths are trimmed, credential-like URLs are rejected, and malformed URLs surface as health diagnostics.
- Hardened Ollama model inventory parsing so malformed `/api/tags` payloads surface as health diagnostics.
- Made generated-memory writes best-effort and atomic where possible, so damaged `.aegis` paths do not crash scans.
- Made shared settings reads/writes best-effort, so damaged config paths do not crash health or settings APIs.
- Restricted shared memory directory settings to one workspace-local folder name, preventing config from pointing memory outside the project.
- Hardened agent continue/repair planning so damaged roadmap or validation-log paths degrade to safe responses instead of server errors.
- Hardened Core validation startup failures so OS-level command launch errors return structured validation results instead of backend exceptions.
- Hardened VS Code `.aegis` initialization so damaged memory files are left untouched and reported in the output channel.
- Hardened VS Code index, managed-section, recovery, validation-log, decision-log, and dogfooding-note writes so damaged memory targets remain degraded instead of crashing workflows.
- Hardened VS Code rollback manifest validation so corrupted backup IDs, mismatched workspace roots, or unsafe backup paths cannot restore outside the current workspace backup folder.
- Tightened VS Code rollback backup ID validation to reject dot and hidden-folder aliases.
- Hardened VS Code rollback failure handling so missing or unreadable backup files are skipped with output-channel details and manifest-level rollback errors are reported cleanly.
- Hardened Visual Studio `.aegis` solution memory so damaged memory files are skipped and health checks surface the degraded state.
- Hardened Visual Studio rollback so it resolves backups by explicit ID and skips unsafe or incomplete rollback manifest entries.
- Tightened Visual Studio rollback so shared backup folders cannot restore another solution's manifest, invalid backup IDs do not fall back to the newest backup folder, and proposed edit paths cannot contain traversal or secret-like path segments.
- Hardened Website workspace setup so damaged `.aegis/project.json` and `.aegis/validation_profile.json` paths return warnings instead of crashing setup.
- Hardened Website checkpoint restore so invalid checkpoint IDs, non-file manifests, and escaped backup paths fail safely before workspace files are restored or removed.
- Hardened Website checkpoint restore preflight so missing backup files fail clearly before any workspace files are restored or removed.
- Hardened Website apply changes so failed checkpoint creation stops the apply before file writes and file write/delete failures are reported as warnings tied to the checkpoint.
- Hardened Desktop backend/Core URL settings so common local inputs normalize to clean base URLs before requests are sent.
- Hardened VS Code Ollama/Core URL settings so common local inputs normalize before model scans, health checks, and shared task updates.
- Hardened Visual Studio Ollama/Core URL settings so common local inputs normalize before model calls, health checks, and shared client registration.

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
