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
| Aegis Core CLI | Improved | JSON mode is flexible, and task persistence failures return structured nonzero errors instead of tracebacks. |
| Shared client registration | Pass | Desktop, VS Code, and Visual Studio now have Core registration paths. |
| Shared task visibility | Pass | VS Code creates and updates Core tasks during agent mode; Core dashboard displays active/recent tasks. |
| Shared client registry resilience | Improved | Core normalizes malformed local client records before dashboard sorting. |
| Desktop dashboard bridge | Improved | Desktop has `core_api_base_url` and an Auralith Ecosystem card backed by `/v1/ecosystem/dashboard`; registration failures no longer block dashboard reads when Core is reachable. |
| VS Code health check | Improved | Health check now warns when Aegis Core is offline and registers the VS Code client when Core is reachable. |
| Visual Studio health check | Improved | Health check now reports Core reachability separately from shared client registration and preserves useful Core error details. |
| Website integration | Partial | Website has its own mature local backend. For this phase it remains documented as a client and should migrate incrementally to `/v1` Core contracts. |
| Website diagnostics | Improved | Core bridge errors, project-status excerpts, feedback capture, command output, and validation diagnostic formatting now redact OAuth/provider aliases such as `access_token`, `refresh_token`, `client_secret`, `x-api-key`, and `private_key` while preserving non-secret parser context. |
| Workspace scan performance | Improved | Core scan results are cached when the workspace fingerprint is unchanged, skipping repeated expensive symbol/dependency/TODO passes. |
| Workspace scan resilience | Improved | Core scans tolerate malformed package dependency metadata, BOM-prefixed `package.json` files, damaged framework marker paths, Unity project metadata, and files disappearing during scan sorting. |
| Path safety | Improved | Core now evaluates ignored folders relative to the workspace, blocks secret-like filenames case-insensitively, and rejects paths resolving outside the workspace. |
| Shared settings | Improved | Core config loading falls back to defaults for malformed values, unsafe memory directory names, and damaged `.aegis/config.json` paths. |
| Desktop settings | Improved | Backend and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before config writes or runtime requests. |
| VS Code settings | Improved | Ollama and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before model or shared-runtime requests. |
| VS Code diagnostics | Improved | Local API HTTP failures now surface parsed, redacted details instead of raw JSON response bodies, OAuth/provider secret fields are redacted before display or memory writes, blocked proposal warnings/errors name the first unsafe file instead of hiding the path in the output channel, validation summaries classify missing tools/dependencies before repair prompts are generated, and long local model calls update progress/status state while waiting. |
| VS Code packaging | Improved | Release lint now verifies command contribution/activation parity, release metadata, source-only helper exclusions, package hygiene, Python lockfile fallback safety, Unity metadata fallback context, generated/runtime proposal guards, and secret filename guard parity before VSIX creation. |
| Visual Studio settings | Improved | Ollama and Aegis Core URL fields normalize host:port inputs and pasted endpoint paths before model or shared-runtime requests. |
| Shared task API | Improved | Bad task status updates return `400`, missing task IDs return `404`, and malformed local task records are normalized on read. |
| Visual Studio packaging | Improved | VSIX packaging now validates manifest metadata, command resources, VSCT/C# command table parity, diagnostic redaction parity, solution scanner parity, NuGet lockfile filename handling, Unity metadata context, generated/runtime safe-edit guards, scanner/safe-edit secret filename guard parity, and release documentation/license sources before producing the release archive. |
| Shared mutation persistence | Improved | Client registration and task creation/update now verify persistence; unwritable `.aegis` roots return clear failures or degraded plan responses instead of phantom successful writes. |
| Memory resilience | Improved | Dashboard/task reads, agent plan reads, and generated-memory writes now tolerate unreadable or damaged `.aegis` JSON/markdown paths. |
| VS Code memory resilience | Improved | Workspace startup and later index/history/log writes skip damaged `.aegis` paths instead of breaking scans or post-apply bookkeeping. |
| VS Code rollback safety | Improved | Rollback validates timestamp-like backup IDs, workspace roots, and backup file paths before restoring files; incomplete backup files are skipped with visible output details. |
| Visual Studio memory init | Improved | Solution memory reads and writes are best-effort, so damaged `.aegis` paths do not crash memory-backed workflows. |
| Visual Studio rollback | Improved | Backup manifests now carry explicit IDs, rollback rejects cross-solution manifests, and manifest/backup paths are validated before touching solution files. |
| Website workspace setup | Improved | Damaged `.aegis` project and validation profile paths now return warnings instead of breaking setup, generated/dependency folder ignores are matched case-insensitively during scans, and secret-like filenames are excluded from scan/context results. |
| Website validation discovery | Improved | Damaged project marker directories such as `package.json`, `build.py`, or `CMakeLists.txt` no longer create false validation or install suggestions, root `build.ps1` guard scripts are preferred over lower-level native build fallbacks, agent/project-builder continuation proposes the same safe PowerShell guard command, and command execution blocks broader PowerShell invocations. |
| Website validation profiles | Improved | Manual validation profile updates now use atomic writes, clean failed temp files, and report damaged profile paths as clear API errors. |
| Website memory notes | Improved | Memory-note files are confined to the memory directory, damaged memory paths degrade with clear API errors, writes are atomic, malformed confidence input is tolerated, rapid note IDs are collision-safe, and the memory editor uses shared API base discovery for note operations. |
| Website model manager | Improved | Damaged model-operation and pull-log JSON paths are skipped safely, invalid operation records are ignored, and operation history writes are atomic. |
| Website model benchmarks | Improved | Damaged benchmark result/job stores are skipped safely, blank job records are ignored, and benchmark state writes are atomic. |
| Website dependency profiling | Improved | Damaged marker directories and lockfile paths no longer distort onboarding stack, package-manager, entry-point, or database summaries, root `build.py` / `build.ps1` guard scripts are recorded before lower-level native validation fallbacks, Python lockfile drift is tracked by watcher snapshots, and Unity metadata is profiled without scanning generated runtime folders. |
| Dependency lockfile safety | Improved | Core maintenance manifests, Website guided auto-apply scoring, autonomous dependency projections, watcher evidence, and VS Code local fallback proposal guards now treat JS, Python, Go, Rust, .NET/NuGet, and Unity lockfiles or package metadata as dependency-wide surfaces. |
| Website creative assets | Improved | Generated media preview URLs use the shared API resource URL helper, so previews work through the Vite proxy and discovered backend ports instead of assuming `8787`. |
| Website checkpoint restore | Improved | Restore now validates checkpoint IDs, damaged manifests, backup paths, and missing backup files before touching workspace files. |
| Website safe apply | Improved | Apply refuses to edit when checkpoint creation fails, reports later write/delete failures with checkpoint context, and blocks ignored dependency/runtime, hidden parent folders, or secret-like files before file writes. |
| Website frontend bundle | Improved | Production builds split React, icons, API calls, app utilities, and app styles into stable chunks, removing the default Vite large-chunk warning without raising the warning limit. |
| Validation detection | Improved | Core now lists safe JS test/lint/typecheck/build validation commands only when matching package scripts exist, preserves npm/pnpm/yarn/Bun package-manager conventions, surfaces root `build.ps1` guard scripts before lower-level fallbacks, ignores project files in dependency/build folders, ignores damaged root build-marker directories, distinguishes native Visual Studio/C++ solutions from .NET solutions, treats nested subprojects as validation boundaries, and avoids duplicate default-command detection during validation runs. |
| Validation execution | Improved | Core blocks unsafe custom validation commands and returns structured missing-tool/start-failed/timeout failures. |
| Validation logging | Improved | Validation output is redacted before API responses and disk writes; log write failures do not crash validation. |
| Diagnostics | Improved | Core dashboard now surfaces stale tasks and suggested actions; diagnostic log write failures do not crash health checks. |

## Verification Run

Ran during this pass:

- `python -m pytest tests -q` in Aegis Core: 51 tests passed
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
- `npm run lint` in VS Code extension: pass, including command activation parity checks
- VS Code memory-write hardening lint: pass
- VS Code rollback manifest hardening lint and package: pass
- VS Code rollback incomplete-backup hardening lint and package: pass
- `npm run package` in VS Code extension: pass, regenerated `release/aegis-local-autopilot-0.1.1.vsix` with only runtime/package metadata files
- Visual Studio package validation guards: pass, including release documentation/license source checks
- Visual Studio package validation guards: pass, including NuGet lockfile scanner parity
- Visual Studio package validation guards after Unity metadata context hardening: pass
- Visual Studio extension Release build after Unity metadata context hardening: pass
- Desktop `.\build.ps1`: pass, 0 warnings, 0 errors
- Desktop quick smoke: pass, nonblank login capture with backend reachable before and after launch
- Visual Studio extension `.\build.ps1`: pass, command table parity checked, regenerated `release/AegisLocalAgentVs.vsix`
- Visual Studio rollback hardening `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Visual Studio rollback cross-solution/path hardening `.\build.ps1`: pass, regenerated `release/AegisLocalAgentVs.vsix`
- Website frontend API tests: pass, including memory and creative asset API base discovery regressions
- Website frontend tests: 21 files / 172 tests passed
- Website frontend production build: pass, no Vite chunk-size warning
- Aegis Core JS/Python/Go/Rust/.NET/Unity metadata and simulation focused tests: 9 passed
- Aegis Core contract regression suite after Unity metadata scan hardening: 158 passed
- Website approval/autonomous/workspace-operation lockfile safety tests: 36 passed, 11 subtests passed
- Website approval/workspace/autonomous Unity metadata safety tests: 38 passed, 11 subtests passed
- Website workspace/storage and workspace-operation scan ignore tests: 74 passed
- Website workspace/storage and workspace-operation tests after generated/runtime edit guard hardening: 76 passed
- Website workspace/storage, workspace-operation, and golden workflow tests after Website secret path safety hardening: 84 passed
- VS Code package lint and extension syntax check after Unity metadata context hardening: pass
- VS Code package lint and extension syntax check after generated/runtime proposal guard hardening: pass
- VS Code package lint and extension syntax check after editor secret path guard parity: pass
- VS Code package lint and extension syntax check after dot-segment proposal path guard hardening: pass
- Visual Studio package validation guards and Release build after generated/runtime safe-edit hardening: pass
- Visual Studio package validation guards and Release build after editor secret path guard parity: pass
- Visual Studio package validation guards and Release build after scanner secret filter parity: pass
- VS Code package lint, extension syntax check, Visual Studio package validation guards, and Visual Studio Release build after editor OAuth secret redaction parity: pass
- Website backend Core bridge, project-status, and config feedback redaction tests after OAuth secret redaction parity: 27 passed
- Website backend compile check after OAuth secret redaction parity: pass
- Website backend command, validation-diagnostic, and scaffold-reporting tests after validation output secret redaction: 43 passed
- Website backend scaffold command/log/runtime and validation-outcome tests after validation output secret redaction: 21 passed
- Website backend compile check after validation output secret redaction: pass
- Website focused frontend API/runtime/task tests: 40 tests passed
- Website acceptance gate with explicit backend/frontend URLs: pass
- Website backend tests: 739 tests and 155 subtests passed
- Website workspace setup regression and helper tests for damaged `.aegis` paths: 8 tests passed
- Website validation manager damaged-marker/profile-persistence regression tests: 21 tests and 4 subtests passed
- Website model-manager damaged-log regression tests: 4 tests passed
- Website model-benchmark damaged-store regression tests: 7 tests passed
- Website checkpoint restore, apply safety, memory-note persistence, and dependency-profile tests: 60 workspace/storage tests passed
- Website backend `python -m compileall aegis_ai`: pass

## Fixes Made In This Pass

- Added VS Code setting: `aegisLocalAutopilot.coreUrl`.
- Added VS Code Core registration on startup and workspace-folder changes.
- Added VS Code Core task creation/status updates for agent proposals, approvals, and rejections.
- Added Visual Studio setting: `Aegis Core URL`.
- Added Visual Studio Core health/registration check to the native health command.
- Added Core scan cache through `.aegis/scan-cache.json`.
- Added Core dashboard stale-task detection and suggested actions.
- Hardened Core CLI shared task creation so persistence failures are actionable in scripts and do not leak tracebacks.
- Hardened shared client registry loading so malformed client records, bad capabilities, and mixed timestamp types do not break dashboard sorting.
- Hardened shared task loading so malformed local task metadata and timestamps do not break dashboard or status workflows.
- Hardened shared client/task mutations so unwritable `.aegis` roots do not report successful cross-client coordination that was never persisted.
- Hardened Core scan safety for mixed-case ignored folders, token/password/auth-like files, and Windows workspaces under temp-style parent directories.
- Hardened Core read/edit safety so files resolving outside the workspace, including symlinked files, are excluded from scans.
- Hardened Core workspace scans against malformed `package.json` dependency shapes and file stat races during recent-file sorting.
- Hardened Core framework detection so UTF-8 BOM-prefixed `package.json` files still detect React/Vite/Next dependencies.
- Hardened Core framework detection so damaged `package.json`, `Assets`, or `ProjectSettings` marker shapes do not create false Node or Unity classifications.
- Improved Core Unity scans and change simulation so package manifests, package lockfiles, project settings, and assembly-definition metadata are available as build/context files and build-impacting risk without scanning generated Unity runtime folders.
- Improved VS Code local fallback snapshots so Unity package manifests, package lockfiles, project settings, and assembly-definition metadata stay available as important context/build-risk files when Core scan is unavailable.
- Improved Visual Studio solution scans and smart context so Unity package manifests, package lockfiles, project settings, and assembly-definition metadata stay available as important context/config files without treating Unity's package lockfile as the old NuGet typo.
- Improved Website workspace profiling, watcher drift, guided approval, and autonomous dependency projections so Unity package manifests, package lockfiles, project settings, and assembly-definition metadata receive dependency/config safety treatment while generated Unity runtime folders are skipped.
- Hardened Website scan ignores so mixed-case generated/dependency directories such as `Node_Modules`, `BUILD`, `LIBRARY`, `temp`, and `LOGS` stay out of context and dependency profiling.
- Hardened Website, VS Code, and Visual Studio safe-edit guards so generated proposals cannot write into Unity `Library`, `Temp`, or `Logs` runtime folders, and Website apply blocks ignored dependency/runtime or hidden folders before file writes.
- Hardened Website workspace scan, context, read, and apply paths so `.env`, token/password, private-key, and certificate-like filenames stay out of model context and generated writes while safe names such as `.gitignore` and `tokenizer.py` remain usable.
- Aligned VS Code and Visual Studio safe-edit secret filename guards with Core and Website coverage for password, API-key, auth, SSH-key, and keystore-like files while preserving ordinary source names such as `tokenizer.py`.
- Hardened VS Code proposal path safety so dot-segment paths such as `src/../README.md` are rejected before apply.
- Aligned Visual Studio solution scanning and smart context secret filename filters with safe-edit coverage so secret-like files stay out of context without dropping ordinary names such as `tokenizer.py`.
- Hardened VS Code and Visual Studio diagnostic redaction and memory sanitization for OAuth/provider fields such as `access_token`, `refresh_token`, `client_secret`, `x-api-key`, and `private_key`.
- Hardened Website Core bridge, project-status, and feedback redaction for OAuth/provider fields such as `access_token`, `refresh_token`, `client_secret`, `x-api-key`, and `private_key`.
- Hardened Website validation command output, diagnostic formatting, and project-scaffold excerpts so provider/OAuth secret values are redacted before they reach build logs, repair prompts, or API payloads.
- Hardened Core validation detection so ignored dependency/build folders do not trigger false `.NET` build suggestions.
- Hardened Core validation detection so damaged root build-marker directories do not trigger false Cargo, Python, CMake, pnpm, or Yarn suggestions.
- Reduced Core validation startup overhead by avoiding duplicate validation-command detection.
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
- Hardened Website validation discovery so damaged project marker directories do not produce false validation or install suggestions, agent/project-builder continuation keeps root PowerShell build guards aligned with detected validation, and command execution rejects broader PowerShell invocations.
- Hardened Website validation profile updates so damaged profile paths return clear API errors and failed writes do not leave temporary files behind.
- Hardened Website memory note persistence so category-derived filenames cannot escape the memory directory, damaged memory paths degrade with clear API errors, note writes are atomic, malformed confidence input is tolerated, and same-millisecond creations get unique IDs.
- Hardened Website model-manager snapshot reads so damaged `logs/model-manager/operations.json` and model-pull summary paths cannot break the local model dashboard.
- Hardened Website model-benchmark persistence so damaged benchmark result/job JSON paths cannot break snapshots, blank job records are ignored, and failed state writes return clear API errors.
- Hardened Website dependency profiling so damaged marker directories and lockfile paths do not distort onboarding stack summaries and root build guard scripts stay aligned with validation planning.
- Hardened Core, Website, and VS Code dependency metadata handling so NuGet lockfiles and central package metadata are treated as dependency-wide drift and guarded edit surfaces.
- Hardened Website checkpoint restore so invalid checkpoint IDs, non-file manifests, and escaped backup paths fail safely before workspace files are restored or removed.
- Hardened Website checkpoint restore preflight so missing backup files fail clearly before any workspace files are restored or removed.
- Hardened Website apply changes so failed checkpoint creation stops the apply before file writes and file write/delete failures are reported as warnings tied to the checkpoint.
- Hardened Desktop backend/Core URL settings so common local inputs normalize to clean base URLs before requests are sent.
- Hardened VS Code Ollama/Core URL settings so common local inputs normalize before model scans, health checks, and shared task updates.
- Hardened VS Code local API error messages so degraded Core/Ollama calls are easier to act on.
- Hardened Visual Studio Ollama/Core URL settings so common local inputs normalize before model calls, health checks, and shared client registration.
- Hardened Desktop and Visual Studio degraded-mode handling so Core registration failures do not masquerade as full Core outages.
- Hardened Visual Studio solution scanning so NuGet `packages.lock.json` is preserved as important dependency metadata and the package validation guard catches filename drift.

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
