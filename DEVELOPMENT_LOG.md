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
- Website checkpoint restore, apply safety, memory-note persistence, and dependency-profile regression tests: pass, 60 workspace/storage tests.
- Website backend compile check: pass.

Known next checks:

- Perform manual live UI click-through in Desktop, VS Code, and Visual Studio when an interactive session is available.
