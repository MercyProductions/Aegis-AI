# Development Log

## 2026-05-08 - Autonomous Stabilization Start

Focus:

- Treat Auralith/Aegis as a real long-term local-first development ecosystem.
- Prefer bug hunting, validation, documentation, and small reliability fixes over feature expansion.
- Keep Desktop, VS Code, Visual Studio, Website, and Aegis Core connected through stable shared contracts.

Actions:

- Confirmed GitHub remote: `https://github.com/MercyProductions/Aegis-AI.git`.
- Added regression tests around the Aegis Core contracts that every client is beginning to depend on.
- Hardened Aegis Core CLI shared task creation so persistence failures produce structured nonzero errors instead of tracebacks.
- Hardened shared Core safety checks for mixed-case ignored folders, token/password/auth-like files, and Windows temp-parent workspaces.
- Hardened shared Core safety checks so paths resolving outside the workspace are not treated as project-local read/edit targets.
- Hardened shared Core config parsing so malformed settings degrade to defaults.
- Hardened shared Ollama URL parsing and model health diagnostics for malformed local endpoint settings, pasted API paths, and credential-like URL text.
- Hardened Ollama model inventory parsing so malformed `/api/tags` payloads do not break shared health/model endpoints.
- Added explicit Core task-status API errors for bad statuses and missing task IDs.
- Hardened shared task record loading so malformed local task metadata and timestamps do not break dashboards or status updates.
- Hardened shared client registry loading so malformed local client records and mixed timestamp types do not break dashboard client lists.
- Hardened shared Core client/task mutations so unwritable `.aegis` memory roots return clear persistence failures or degraded plan responses instead of phantom successful writes.
- Hardened dashboard/task memory reads so corrupted or unreadable `.aegis` files do not crash shared clients.
- Tightened Core JavaScript validation detection to avoid hallucinated npm/pnpm/yarn test/build commands.
- Hardened Core validation detection so ignored dependency/build folders do not create false `.NET` validation suggestions.
- Hardened Core validation detection so damaged root build marker directories do not create false Cargo, Python, CMake, pnpm, or Yarn validation suggestions.
- Reduced Core validation startup overhead by reusing one detected default command per validation run.
- Restricted Core validation execution to known safe commands and structured failure results.
- Hardened Core validation command startup failures so OS-level launch errors are logged and returned as structured failures.
- Redacted validation logs before disk writes and made validation log write failures non-fatal.
- Redacted returned validation output and made Core diagnostic log writes non-fatal.
- Hardened Core generated-memory writes so damaged `.aegis` paths do not crash workspace scans.
- Hardened Core workspace scans against malformed `package.json` dependency fields and file stat races.
- Hardened Core framework detection so BOM-prefixed `package.json` files still preserve React/Vite/Next workspace intelligence.
- Hardened Core framework detection so damaged `package.json`, `Assets`, or `ProjectSettings` marker shapes do not create false Node or Unity classifications.
- Hardened Core settings read/write paths for damaged `.aegis/config.json` and `.aegis` paths.
- Restricted shared memory directory settings to safe workspace-local folder names.
- Hardened Core continue/repair agent endpoints against damaged roadmap and validation-log memory paths.
- Hardened VS Code workspace memory initialization so damaged `.aegis` paths are logged and skipped without startup crashes.
- Hardened VS Code memory/index/history writes so damaged `.aegis` paths stay degraded instead of breaking scans or post-apply bookkeeping.
- Hardened VS Code rollback manifest validation so corrupted backup metadata cannot restore outside the current workspace backup folder.
- Tightened VS Code rollback backup ID validation to reject dot and hidden-folder aliases.
- Hardened VS Code rollback failure handling so incomplete backup entries are skipped with output-channel details and manifest-level failures produce a clear error instead of escaping the command.
- Hardened Visual Studio solution memory reads/writes so damaged `.aegis` paths no longer crash memory-backed workflows.
- Hardened Visual Studio rollback manifests with explicit backup IDs and safe path validation for rollback entries and backup files.
- Tightened Visual Studio rollback to reject cross-solution manifests, dot/hidden backup aliases, ambiguous newest-backup fallback, and proposal paths containing traversal or secret-like segments.
- Hardened Website workspace setup so damaged `.aegis` project and validation profile paths return setup warnings instead of endpoint failures.
- Hardened Website validation discovery so damaged project marker directories do not create false validation or install suggestions.
- Hardened Website validation profile updates so damaged profile paths return clear API errors and failed writes clean up temporary files.
- Hardened Website memory note persistence so category-derived note IDs stay inside the memory directory, damaged memory paths degrade with clear API errors, writes are atomic, malformed confidence input is tolerated, and same-millisecond collisions are avoided.
- Hardened Website model-manager snapshot reads so damaged operation and pull-log JSON paths do not break the local model dashboard.
- Hardened Website model-benchmark persistence so damaged results/jobs JSON paths do not break benchmark snapshots and failed state writes return clear API errors.
- Hardened Website dependency profiling so damaged marker directories and lockfile paths do not distort onboarding stack summaries.
- Hardened Website checkpoint restore against path traversal IDs, damaged manifests, and backup paths outside the checkpoint files folder.
- Hardened Website checkpoint restore preflight so missing backup files stop the restore before any workspace files are touched.
- Hardened Website apply changes so failed checkpoint creation prevents edits and write/delete failures return warnings instead of raw endpoint failures.
- Hardened Desktop backend and Aegis Core URL handling so settings UI/config values are normalized before saving and before runtime requests.
- Hardened Desktop Core dashboard loading so shared client registration failures no longer block dashboard reads when Core is reachable.
- Hardened VS Code Ollama and Aegis Core URL handling so settings panel/config values are normalized before health checks, model scans, and shared task sync.
- Hardened VS Code local API error reporting so Core/Ollama HTTP failures show parsed, redacted details instead of raw JSON response bodies.
- Hardened Visual Studio Ollama and Aegis Core URL handling so option-page values are normalized before health checks, model calls, and shared client registration.
- Hardened Visual Studio Health Check so Core reachability and Core client registration failures are reported separately with parsed error details.
- Kept unrelated dirty worktree changes out of scope.
- Recorded workflow friction in `WORKFLOW_NOTES.md`.

Validation completed:

- Aegis Core contract test suite: pass, 44 tests.
- Aegis Core compile check: pass.
- Aegis Core BOM-prefixed package framework detection regression test: pass.
- Aegis Core malformed client registry regression test: pass.
- Aegis Core malformed task record regression tests: pass.
- Aegis Core outside-workspace path and symlink scan safety regression tests: pass.
- Aegis Core workspace scan malformed package/stat-race regression tests: pass.
- Aegis Core Ollama URL normalization and malformed-health regression tests: pass.
- Aegis Core malformed Ollama model inventory regression tests: pass.
- Aegis Core validation startup-failure regression test: pass.
- VS Code extension lint and package: pass.
- VS Code extension memory-write hardening lint: pass.
- VS Code rollback manifest hardening lint and package: pass.
- VS Code rollback incomplete-backup hardening lint and package: pass.
- Desktop app build: pass.
- Visual Studio extension build/package: pass.
- Visual Studio rollback hardening build/package: pass.
- Visual Studio rollback cross-solution/path hardening build/package: pass.
- Website frontend tests/build and backend tests: pass.
- Website workspace setup regression tests for damaged `.aegis` paths: pass.
- Website validation manager damaged-marker/profile-persistence regression tests: pass, 21 tests and 4 subtests.
- Website model-manager damaged-log regression tests: pass, 4 tests.
- Website model-benchmark damaged-store regression tests: pass, 7 tests.
- Website checkpoint restore, apply safety, memory-note persistence, and dependency-profile regression tests: pass, 60 workspace/storage tests.
- Website backend compile check: pass.

Known next checks:

- Perform manual live UI click-through in Desktop, VS Code, and Visual Studio when an interactive session is available.

## 2026-05-09 - Autonomous Stabilization Tranche

Focus:

- Continue long-term stabilization without expanding scope.
- Validate the consolidated ecosystem before pushing updates.
- Fix only realistic reliability, release, or trust issues found during validation.

Actions:

- Confirmed the working tree was clean and the GitHub remote is `https://github.com/MercyProductions/Aegis-AI.git`.
- Ran high-signal validation across Aegis Core, Website backend/frontend, Desktop, VS Code extension, and Visual Studio extension.
- Found a VS Code release packaging hygiene issue: the generated VSIX included repository-only files, dogfooding notes, and local detected model inventory.
- Updated `.vscodeignore` to exclude `.gitignore`, `DETECTED_MODELS.md`, and `DOGFOODING_NOTES.md` from VSIX archives.
- Added a package lint guard so those release-only exclusions are required.
- Made the VS Code package script run package lint before creating the VSIX.
- Left the source notes in the repo; only the release archive contents changed.

Validation completed:

- Aegis Core tests: pass, 51 tests.
- Website backend tests: pass, 776 tests and 155 subtests.
- Website frontend tests: pass, 21 files and 169 tests.
- Website frontend build: pass, with the existing large main chunk warning.
- Website smoke script: pass, including frontend/backend checks, workspace setup, generated file apply/read-back, validation, readiness, and real chat.
- Desktop smoke build/launch: pass, with nonblank login/setup/dashboard captures.
- VS Code extension compile: pass.
- VS Code extension lint: pass, including release exclusion guard.
- VS Code VSIX package: pass; archive contents now exclude local model inventory and dogfooding notes.
- Visual Studio extension build/package: pass.

Friction recorded:

- `npm test -- --runInBand` is a Jest habit and not valid for this Vitest project. The project command is `npm test`.
- VS Code packaging reports `extension.js` as large at about 250 KB. This is a warning, not a release blocker, but future maintainability work should consider splitting only when it pays for itself.

## 2026-05-09 - Extension Release Metadata Follow-up

Focus:

- Keep extension release packages professional and free of local placeholders.
- Add build-time checks so packaging hygiene does not depend on memory.

Actions:

- Replaced the VS Code extension `repository.url` value from `file:../..` to `https://github.com/MercyProductions/Aegis-AI.git`.
- Extended VS Code package lint so release metadata must point to the GitHub repository.
- Replaced the Visual Studio VSIX `MoreInfo` placeholder `https://localhost/aegis-local-agent` with the GitHub repository URL in both manifest sources.
- Removed `DOGFOODING_NOTES.md` from the Visual Studio VSIX content list and from the generated release folder.
- Extended the Visual Studio build script to reject packaged VSIX archives containing localhost placeholder URLs, internal dogfooding notes, local detected model inventory, or repository-only `.gitignore` files.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass; repository metadata points to GitHub.
- Visual Studio extension build/package: pass.
- Visual Studio VSIX archive inspection: pass; MoreInfo points to GitHub and internal notes/model inventory/repository-only files are absent.

## 2026-05-09 - VS Code Package Content Follow-up

Focus:

- Keep the VS Code VSIX archive limited to runtime files and package metadata.
- Avoid shipping source-tree helper scripts that are useful before installation but confusing after packaging.

Actions:

- Excluded `install.ps1` from the VS Code VSIX archive.
- Extended VS Code package lint so `install.ps1` remains source-only.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass.
- VSIX archive inspection: pass; the package contains only `extension.vsixmanifest`, `[Content_Types].xml`, readme, package metadata, license, `extension.js`, and media icons.

## 2026-05-09 - VS Code Release Script Hardening

Focus:

- Make the VS Code package and local install scripts reliable from Windows workspaces with spaces or shell metacharacters in the path.
- Keep release automation small and testable.

Actions:

- Replaced shell-string package/install calls with a shared argument-array command runner.
- Passed relative VSIX paths to `vsce` and `code` so the full repository path is not reparsed through nested Windows command layers.
- Added a package lint guard that rejects `execSync` shell command strings in the release scripts.

Validation completed:

- VS Code extension lint: pass.
- VS Code package script: pass.
- VS Code local install script: pass.
- VSIX archive inspection: pass; the package still contains only runtime files and package metadata.

## 2026-05-09 - VS Code Installer Wrapper Hardening

Focus:

- Avoid maintaining two separate local install flows for the VS Code extension.
- Keep the human-facing PowerShell installer aligned with the validated npm/Node packaging path.

Actions:

- Changed `install.ps1` to call `npm run install-local` instead of separately packaging, discovering the newest VSIX, and invoking `code` directly.
- Added an explicit npm availability check with a setup-oriented error message.

Validation completed:

- VS Code extension lint: pass.
- VS Code PowerShell installer: pass; it packages and installs the VSIX through the hardened local install path.
- VSIX archive inspection: pass; packaged contents remain limited to runtime files and package metadata.

## 2026-05-09 - Website Launcher Probe Hardening

Focus:

- Keep daily website startup responsive when a local backend, frontend, or Ollama endpoint is half-responsive.
- Preserve the existing launch flow while tightening readiness probes.

Actions:

- Added explicit short timeouts to `website/launch.ps1` HTTP readiness and JSON probes.
- Added an `Accept: application/json` header to launcher JSON probes.

Validation completed:

- Website launcher PowerShell syntax check: pass.
- Website launch script: pass; Auralith OS reported ready at `http://127.0.0.1:5173`.
- Website smoke test without chat: pass; frontend/backend identity, partial config, workspace setup, diff/apply/readback, validation, and readiness checks completed.

## 2026-05-09 - Website Launch Port-Conflict Hardening

Focus:

- Avoid starting duplicate backend or frontend processes when ports `8787` or `5173` are already occupied by a non-ready or wrong service.
- Keep launch failures understandable during daily startup.

Actions:

- Added backend blocked-port detection after mismatched-backend restart attempts.
- Added frontend blocked-port detection after mismatched-frontend checks.
- Kept the existing ownership checks that restart Aegis instances from the wrong project folder.

Validation completed:

- Website launcher PowerShell syntax check: pass.
- Mocked backend/frontend blocked-port probes: pass.
- Website launch script: pass; Auralith OS reported ready at `http://127.0.0.1:5173`.
- Website smoke test without chat: pass.

## 2026-05-09 - Website Validation Timeout Hardening

Focus:

- Keep website smoke/e2e validation from hanging indefinitely when local services are wedged.
- Preserve the existing validation workflows and only bound their HTTP calls.

Actions:

- Added configurable request timeouts to `website/scripts/smoke-web.ps1`.
- Added a separate longer chat timeout for the optional real-model smoke leg.
- Added timeout handling to the e2e wrapper's backend/frontend reachability probes.

Validation completed:

- Website smoke/e2e PowerShell syntax checks: pass.
- Website smoke test without chat with explicit request timeout: pass.
- Direct backend/frontend readiness probes with 5 second timeouts: pass.

Remaining risk:

- Full browser e2e exceeded the 180 second command budget during this pass and should be investigated separately; no fresh e2e temp workspace was created by that timed-out run.

## 2026-05-09 - Aegis Core Starter Hardening

Focus:

- Make the shared Core runtime starter fail clearly when port `8788` is occupied by the wrong service.
- Prefer the project virtual environment when one exists.

Actions:

- Updated `aegis-core/scripts/start-core.ps1` to verify the `/v1/health` envelope has `api_version: v1` and `kind: health` before accepting an already-running service.
- Added contract-version reporting for already-running Core instances.
- Added Python resolution that prefers `.venv\Scripts\python.exe` and falls back to `python` on PATH with clearer setup errors.
- Added an import preflight for `aegis_core.server` and `uvicorn` before starting the server.

Validation completed:

- Aegis Core start script syntax check: pass.
- Aegis Core import preflight: pass.
- Aegis Core start script against an already-running Core instance: pass; reported contract `2026.05.09`.
- Aegis Core contract tests: pass, 51 tests.
- Aegis Core compile check: pass.

## 2026-05-09 - Aegis Core Starter Edge-Case Hardening

Focus:

- Keep Core startup errors clear when port `8788` is occupied by a non-Core service that returns HTTP 200 with a malformed body.

Actions:

- Split the start script's HTTP reachability check from JSON envelope parsing.
- Added explicit probe reasons for HTTP errors, invalid JSON, unexpected envelopes, and unexpected status responses.
- Included the probe reason in the wrong-service error message.

Validation completed:

- Aegis Core start script syntax check: pass.
- Aegis Core start script against an already-running Core instance: pass; reported contract `2026.05.09`.
- Mocked malformed JSON probe: pass; reported `invalid_json` while keeping the port marked reachable.
- Aegis Core contract tests: pass, 51 tests.
- Aegis Core compile check: pass.
