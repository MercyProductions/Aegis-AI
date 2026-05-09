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
- Hardened hybrid provider inventory and route planning so credential-store read failures are visible to clients instead of being flattened into missing cloud keys.
- Hardened hybrid provider key deletion so real OS credential-store delete failures are surfaced while missing keys remain a harmless no-op.
- Hardened Core diagnostic redaction so Google/OpenAI-style query-string keys are scrubbed from provider connection errors before clients or logs see them.
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
- Added Core predictive planning and change simulation so planned edits can be scored for impacted files, affected systems, dependency ripple, architecture drift, validation cost, rollback complexity, and safer scenario choices before implementation.
- Added Core engineering operations so release readiness, technical debt, lifecycle stage, risk monitoring, maintenance scheduling, productivity bottlenecks, and cross-project coordination can be reviewed from a single read-only dashboard.
- Added Core adaptive personal engineering intelligence so local workflow/style preferences, recurring project patterns, habit signals, context personalization, and resettable inspectable preference memory can guide clients without cloud calls or hidden persistence.
- Tightened personal preference filtering so token-like secret fields stay blocked while harmless preference names containing `key`, such as `keyboard_layout`, still persist.

Validation completed:

- Aegis Core contract test suite: pass, 83 tests.
- Aegis Core simulate CLI smoke test: pass for single forecast and scenario comparison.
- Aegis Core operations endpoint regressions: pass for single-project coordination and cross-project awareness.
- Aegis Core personal intelligence endpoint regressions: pass for read-only default behavior, explicit profile persistence, secret-like preference filtering, reset behavior, and cross-project pattern detection.
- Aegis Core personal preference filtering regression: pass for preserving safe `keyboard_layout` while dropping `api_key`.
- Aegis Core personal CLI smoke/reset: pass.
- Aegis Core compile check: pass.
- Aegis Core BOM-prefixed package framework detection regression test: pass.
- Aegis Core malformed client registry regression test: pass.
- Aegis Core malformed task record regression tests: pass.
- Aegis Core outside-workspace path and symlink scan safety regression tests: pass.
- Aegis Core workspace scan malformed package/stat-race regression tests: pass.
- Aegis Core Ollama URL normalization and malformed-health regression tests: pass.
- Aegis Core malformed Ollama model inventory regression tests: pass.
- Aegis Core provider inventory and route credential-store failure regressions: pass.
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

## 2026-05-09 - Hybrid Router Local Provider Hardening

Focus:

- Keep explicit local-provider routing local even when cloud mode is enabled.
- Preserve the local-first privacy boundary for LM Studio users.

Actions:

- Audited the Aegis Core hybrid model router local/cloud provider boundary.
- Fixed explicit local provider routing so `lm_studio` selects the local OpenAI-compatible server instead of being ignored or reinterpreted as a cloud fallback candidate.
- Added regressions covering local LM Studio routing, the actual completion provider call, and unsupported provider override fallback.

Validation completed:

- Aegis Core model router regression slice: pass, 8 tests.
- Aegis Core contract test suite: pass, 114 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Core Route CLI Parity

Focus:

- Make the local-first route planner usable from the CLI with the same provider and context controls available through `/v1/models/route`.
- Preserve sanitized context previews for command-line dry-runs.

Actions:

- Added `aegis route` flags for `--provider`, `--model`, repeated `--context-file`, and `--local-failure-reason`.
- Wired those flags into the existing hybrid model router instead of adding a separate CLI-only path.
- Added a subprocess regression proving CLI route previews keep `lm_studio` local while blocking `.env` context.

Validation completed:

- Aegis Core CLI route regression slice: pass, 2 tests.
- Aegis Core contract test suite: pass, 115 tests.
- Repository whitespace check: pass.

## 2026-05-09 - LM Studio Endpoint Compatibility

Focus:

- Keep local LM Studio completions compatible with its OpenAI-compatible API path.
- Preserve existing safe URL normalization while fixing the runtime call target.

Actions:

- Updated LM Studio completions to call `/v1/chat/completions` when settings store the local server base URL.
- Added regression coverage for the exact LM Studio request URL.

Validation completed:

- Aegis Core LM Studio/provider regression slice: pass, 4 tests.
- Aegis Core contract test suite: pass, 116 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Provider Response Failure Hardening

Focus:

- Keep malformed local/cloud provider responses from surfacing as internal parser exceptions.
- Preserve actionable provider diagnostics without exposing secrets or stack traces.

Actions:

- Converted invalid provider JSON into a clean runtime failure.
- Added shared object-shape validation before parsing OpenAI-compatible, Anthropic, or Google response payloads.
- Made provider content parsing tolerant of missing or oddly-shaped completion arrays.
- Added regressions for invalid JSON and non-object OpenAI-compatible responses.

Validation completed:

- Aegis Core provider failure regression slice: pass, 4 tests.
- Aegis Core contract test suite: pass, 118 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Website Core URL Endpoint Normalization

Focus:

- Keep the Website-to-Core adapter resilient when users paste a full Core endpoint instead of the base URL.
- Preserve reverse-proxy path prefixes while trimming known Core endpoint suffixes.

Actions:

- Hardened Website Core URL normalization to strip `/v1/...`, legacy `/health`, and legacy `/models` endpoint paths.
- Added regressions covering direct local endpoints, reverse-proxy prefixes, and path names that merely contain `v1`.
- Updated troubleshooting guidance for Website/Core URL normalization.

Validation completed:

- Website Core bridge URL normalization regression: pass, 1 test.
- Website Core bridge regression suite: pass, 15 tests.
- Website Core bridge/config sync regression slice: pass, 18 tests.
- Website backend test suite: pass, 783 tests and 155 subtests.
- Repository whitespace check: pass.

## 2026-05-09 - VS Code Core URL Prefix Preservation

Focus:

- Align VS Code Core/Ollama URL handling with Website Core bridge normalization.
- Preserve reverse-proxy path prefixes while still tolerating pasted endpoint URLs.

Actions:

- Added VS Code URL helpers that strip known Core and Ollama endpoint suffixes without discarding proxy prefixes.
- Updated Core and Ollama request builders to append API paths beneath the normalized base prefix.
- Added package-lint coverage for URL normalization and service URL joining.
- Updated VS Code and root troubleshooting docs.

Validation completed:

- VS Code extension compile check: pass.
- VS Code extension package lint: pass.
- VS Code extension lint: pass.
- VS Code extension package build: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Visual Studio Core URL Prefix Preservation

Focus:

- Align Visual Studio Core/Ollama URL handling with Website and VS Code bridge normalization.
- Preserve reverse-proxy path prefixes while still tolerating pasted endpoint URLs.

Actions:

- Updated Visual Studio settings normalization to strip known Core and Ollama endpoint suffixes without discarding proxy prefixes.
- Routed Core health/registration and Ollama model/chat requests through the shared service URL builder.
- Added build-time URL normalization guards to catch regressions before VSIX packaging.
- Updated Visual Studio and root troubleshooting docs.

Validation completed:

- Visual Studio extension build/package: pass.
- Visual Studio URL normalization build guard: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Desktop Core URL Prefix Preservation

Focus:

- Align Desktop backend/Core URL handling with Website, VS Code, and Visual Studio normalization.
- Preserve reverse-proxy path prefixes while still tolerating pasted endpoint URLs.

Actions:

- Updated the Desktop C++ URL normalizer to strip known Core and backend/Ollama endpoint suffixes without discarding proxy prefixes.
- Kept Desktop request construction on the existing `NormalizeHttpBaseUrl` plus `JoinUrl` path.
- Added a root build-time URL normalization guard before the Desktop MSBuild step.
- Updated Desktop and root troubleshooting docs.

Validation completed:

- Desktop URL normalization build guard: pass.
- Desktop Release build: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Core Local Provider URL Prefix Preservation

Focus:

- Align Aegis Core local provider URL normalization with the local clients.
- Preserve Ollama and LM Studio reverse-proxy prefixes while tolerating pasted endpoint URLs.

Actions:

- Updated Core config URL cleaning to strip known `/api/...`, `/v1/...`, `/health`, and `/models` endpoint suffixes without discarding proxy prefixes.
- Added regressions for Ollama and LM Studio proxy prefixes and path names that merely contain `v1`.
- Updated config/API troubleshooting documentation.

Validation completed:

- Aegis Core provider URL normalization regression slice: pass.
- Aegis Core contract test suite: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Core Native Solution Validation Detection

Focus:

- Keep Core validation discovery from recommending the wrong build command for native Visual Studio/C++ workspaces.
- Preserve .NET validation discovery for direct project files and .NET solution references.

Actions:

- Changed Core solution detection so `.sln` and `.slnx` files only trigger `dotnet build` when they reference `.csproj`, `.fsproj`, or `.vbproj` projects.
- Added regressions for native `.vcxproj` solutions and .NET solution references.
- Updated validation discovery documentation.

Validation completed:

- Aegis Core validation detection regression slice: pass.
- Aegis Core contract test suite: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Core Nested Workspace Validation Boundaries

Focus:

- Keep parent ecosystem workspaces from inheriting validation commands from nested subprojects.
- Preserve direct .NET project discovery for simple workspaces.

Actions:

- Added nested workspace boundary pruning for validation project-file discovery when child folders have their own package, Python, Rust, CMake, or solution markers.
- Added a regression for a native Desktop-style parent workspace containing a nested Visual Studio extension .NET solution.
- Updated validation discovery documentation.

Validation completed:

- Aegis Core validation detection regression slice: pass.
- Aegis Core contract test suite: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Core Package Validation Script Coverage

Focus:

- Surface safe package validation scripts used by extensions and tooling workspaces.
- Avoid adding package, install, or publish scripts to automatic validation discovery.

Actions:

- Extended Core package validation discovery from test/build-only to safe test, lint, typecheck, type-check, and build scripts.
- Added a regression for lint/typecheck-only package workspaces that ignores unsafe packaging scripts.
- Updated validation discovery documentation.

Validation completed:

- Aegis Core validation detection regression slice: pass.
- Aegis Core contract test suite: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Core PowerShell Build Validation Detection

Focus:

- Prefer project-owned Windows build guard scripts for Desktop and extension validation.
- Keep PowerShell validation execution constrained to a narrow, predictable build command.

Actions:

- Added Core validation discovery for root `build.ps1` before lower-level CMake/.NET fallback commands.
- Extended safe validation command checks to allow only exact no-profile PowerShell or PowerShell Core `build.ps1` invocations.
- Added regressions for root build script priority and unsafe PowerShell script rejection.

Validation completed:

- Aegis Core validation detection regression slice: pass.
- Aegis Core contract test suite: pass.
- Desktop root `build.ps1`: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Website PowerShell Build Validation Planning

Focus:

- Align Website validation planning with Core for Desktop and Visual Studio extension workspaces.
- Prefer project-owned PowerShell build guard scripts over lower-level native build fallbacks.

Actions:

- Added Website validation discovery for root `build.ps1` guard scripts.
- Treated PowerShell build scripts as build runners so native CMake/MSBuild fallback steps do not duplicate or bypass the script guardrails.
- Added a regression for native workspaces with both `build.ps1` and `CMakeLists.txt`.

Validation completed:

- Website validation manager regression suite: pass.
- Aegis Core contract test suite: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Completion Selected Model Guard

Focus:

- Keep completion execution aligned with the model chosen by the route planner.
- Prevent raw cloud model overrides from reaching Ollama when cloud routing is blocked or local fallback is selected.

Actions:

- Changed completion execution to use `route["selected"]["model"]` instead of the raw request model.
- Added a regression proving an OpenAI model override remains attached to the cloud fallback candidate while the actual local completion call uses the selected Ollama model.
- Documented that route previews and completion execution use the selected route model.

Validation completed:

- Aegis Core completion model override regression slice: pass, 6 tests.
- Aegis Core contract test suite: pass, 132 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Local Fallback Model Override Guard

Focus:

- Keep local-first routing from accidentally using cloud model names when cloud routing is blocked or not selected.
- Preserve explicit local LM Studio model overrides for users who choose the local OpenAI-compatible server.

Actions:

- Restricted generic model overrides from replacing the Ollama local fallback model.
- Kept cloud model overrides attached to cloud fallback candidates, where approval and credential gates still apply.
- Added a regression proving a cloud OpenAI model override does not replace the selected Ollama model in `local_only` mode.

Validation completed:

- Aegis Core routing model override regression slice: pass, 7 tests.
- Aegis Core contract test suite: pass, 131 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Settings Provider Alias Consistency

Focus:

- Keep saved hybrid provider settings consistent with route-time provider alias handling.
- Avoid surprising fallback to OpenAI when clients save display-style OpenRouter names.

Actions:

- Shared cloud provider alias normalization between settings and model routing.
- Canonicalized `open-router` and `open router` to `openrouter` when loading or saving preferred cloud provider settings.
- Added settings API regressions proving provider aliases persist canonically while invalid providers still fall back safely.

Validation completed:

- Aegis Core settings/routing provider alias regression slice: pass, 7 tests.
- Aegis Core contract test suite: pass, 130 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Provider Alias Normalization

Focus:

- Keep provider routing predictable across CLI, API, and UI clients that may send display-style provider names.
- Avoid duplicate credential targets or unexpected local fallback caused by casing, spacing, or hyphen differences.

Actions:

- Canonicalized common provider aliases before routing and provider key mutation.
- Added support for aliases such as `LM Studio`, `lm-studio`, `open-router`, and `open router`.
- Added regressions proving local LM Studio aliases stay local and OpenRouter aliases use the canonical credential target.

Validation completed:

- Aegis Core provider alias/key mutation regression slice: pass, 9 tests.
- Aegis Core contract test suite: pass, 129 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Provider Completion Shape Hardening

Focus:

- Prevent malformed provider responses from looking like successful empty model answers.
- Keep local/cloud completion failures bounded and actionable for client UIs.

Actions:

- Made OpenAI-compatible, Anthropic, and Google completion parsers reject missing choices, candidates, content parts, or completion text with clean runtime errors.
- Preserved the successful LM Studio OpenAI-compatible completion path while tightening malformed response handling.
- Added regressions for missing completion text in each provider response shape.

Validation completed:

- Aegis Core provider parsing regression slice: pass, 6 tests.
- Aegis Core contract test suite: pass, 127 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Token Diagnostic Precision

Focus:

- Preserve useful parser diagnostics after broadening provider token redaction.
- Avoid turning ordinary `unexpected token` messages into opaque redacted failures.

Actions:

- Made bare `token:` assignment redaction conditional on the value looking secret-like.
- Kept explicit fields such as `api_token`, `access_token`, `refresh_token`, and `id_token` strict across JSON, query-string, and assignment-style diagnostics.
- Added regression coverage proving `unexpected token: <` remains readable while likely token secrets are still redacted.

Validation completed:

- Aegis Core diagnostic/provider redaction and validation-log regression slice: pass, 11 tests.
- Aegis Core contract test suite: pass, 124 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Provider Auth Alias Redaction

Focus:

- Broaden provider diagnostic privacy coverage without turning useful provider failures into opaque log lines.
- Cover common OAuth and provider key field names that appear outside the exact `api_key`/`token` forms.

Actions:

- Centralized the Core inline diagnostic sensitive-field vocabulary across JSON, query-string, and assignment-style redaction patterns.
- Added coverage for `x-api-key`, `client_secret`, `access_token`, `refresh_token`, `id_token`, and `private_key` field aliases.
- Added regression coverage proving those aliases are redacted while provider failure context remains readable.

Validation completed:

- Aegis Core diagnostic/provider redaction regression slice: pass, 8 tests.
- Aegis Core contract test suite: pass, 123 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Provider Diagnostic Colon Redaction

Focus:

- Close a privacy gap in inline provider diagnostics without replacing useful provider error context.
- Keep cloud/provider failures safe when backends format secrets as colon assignments instead of JSON or query strings.

Actions:

- Extended inline diagnostic redaction to cover colon-form assignments such as `api_key: ...`, `x-api-key: ...`, and `token: ...`.
- Added regression coverage proving colon-form provider secrets are redacted while the surrounding failure context remains readable.

Validation completed:

- Aegis Core diagnostic/provider redaction regression slice: pass, 7 tests.
- Aegis Core contract test suite: pass, 122 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Settings Persistence Sanitization

Focus:

- Keep saved Core settings aligned with the sanitized values returned by `/v1/settings`.
- Avoid preserving raw invalid hybrid routing values in `.aegis/config.json` after users edit settings.

Actions:

- Normalized settings updates before persistence, including provider IDs, routing modes, local provider URLs, model lists, booleans, context limits, and workspace-local memory folder names.
- Normalized stale known settings already present on disk whenever settings are saved, while preserving unknown client-owned keys.
- Added regression coverage proving `/v1/settings` writes canonical hybrid settings to disk.

Validation completed:

- Aegis Core settings API regression slice: pass, 3 tests.
- Aegis Core contract test suite: pass, 121 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Hybrid Provider Setting Sanitization

Focus:

- Keep hybrid routing settings explicit and predictable when users mistype provider names.
- Avoid leaving unsupported provider IDs in effective Core config.

Actions:

- Restricted `preferred_cloud_provider` normalization to OpenAI, Anthropic, Google, and OpenRouter.
- Added a regression proving unsupported cloud provider settings fall back to the default provider.

Validation completed:

- Aegis Core hybrid settings regression slice: pass, 2 tests.
- Aegis Core contract test suite: pass, 118 tests.
- Repository whitespace check: pass.

## 2026-05-09 - Local Provider Key Storage Guard

Focus:

- Keep provider key storage aligned with the local-first provider model.
- Avoid writing unnecessary OS credential entries for local providers such as LM Studio.

Actions:

- Restricted provider key writes to cloud providers only.
- Preserved unsupported-provider errors for unknown IDs while returning a clearer local-provider key-storage error for `lm_studio`.
- Added endpoint regression coverage for local provider key write rejection.

Validation completed:

- Aegis Core provider key endpoint regression slice: pass, 3 tests.
- Aegis Core contract test suite: pass, 119 tests.
- Repository whitespace check: pass.

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
- Website frontend build: pass; at this point it still emitted the large main chunk warning that was resolved later in the day.
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
- Aegis Core contract tests: pass, 89 tests.
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

## 2026-05-09 - Website Browser E2E Project Switch Hardening

Focus:

- Turn the full browser e2e timeout into actionable validation output.
- Fix the project-switch file preview race found by the browser e2e flow.

Actions:

- Added configurable Node-side fetch timeouts to `website/scripts/e2e-web.mjs` for backend API calls and readiness probes.
- Changed website file preview loading to read from the latest workspace root reference when a project switch has just updated the active root.
- Cleaned the failed e2e debug workspace after the project-switch fix was validated.

Validation completed:

- Website e2e script syntax check: pass.
- Website focused frontend tests: pass, 32 tests.
- Website smoke test without chat and with explicit request timeout: pass.
- Website full browser e2e: pass; temporary workspace cleaned up.
- Website frontend production build: pass; at this point it still emitted the large-chunk warning that was resolved later in the day.

## 2026-05-09 - Website Frontend Chunk Budget Hardening

Focus:

- Resolve the recurring Website production build chunk warning without raising Vite's warning limit.
- Keep the change scoped to build output shape, not user-facing behavior.

Actions:

- Replaced static object chunk names in `website/frontend/vite.config.ts` with an explicit `manualChunks` function.
- Split React, icons, frontend API calls, app utilities, and app styles into stable chunks so the monolithic protected app shell no longer crosses the default warning threshold.
- Updated the current stabilization docs to reflect the new build baseline.

Validation completed:

- Website frontend production build: pass, no Vite chunk-size warning.
- Website focused frontend tests: pass, 38 tests.

## 2026-05-09 - Website Acceptance URL Propagation Hardening

Focus:

- Keep alternate-port web validation reliable when `acceptance-web.ps1` is run directly.
- Remove drift between the acceptance gate's initial live URL checks and the child doctor, smoke, and e2e scripts.

Actions:

- Updated `website/scripts/acceptance-web.ps1` to resolve and trim its `Root`, `BackendUrl`, and `FrontendUrl` parameters once.
- Changed acceptance child steps to call `doctor-web.ps1`, `smoke-web.ps1`, and `e2e-web.ps1` directly with the same root and URL parameters instead of invoking npm scripts that fall back to default ports.
- Documented the direct alternate-port acceptance command in `website/README.md`.

Validation completed:

- Website acceptance script syntax check: pass.
- Website acceptance gate with explicit trailing-slash URLs: pass; validate, doctor, real-chat smoke, and full browser e2e completed.

## 2026-05-09 - VS Code Command Activation Guard

Focus:

- Prevent VS Code extension package drift where a contributed command can ship without activation, or an activation event can point at a removed command.
- Keep release validation headless and cheap.

Actions:

- Extended `vscode-plugins/aegis-local-autopilot/scripts/lint-package.js` to compare all contributed commands with all `onCommand:` activation events.
- Kept the existing required-command checks, release metadata checks, and VSIX exclusion checks intact.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass; packaged contents remain limited to runtime files and package metadata.

## 2026-05-09 - Visual Studio Command Table Guard

Focus:

- Prevent Visual Studio extension command drift where a VSCT menu item, C# command ID, or handler registration changes without the others.
- Keep the guard inside the existing VSIX packaging path so daily release validation catches drift early.

Actions:

- Added Visual Studio command table validation to `visual-studio-extensions/aegis-local-agent-vs/build.ps1`.
- The build now checks VSCT button IDs, command `IDSymbol` values, `CommandIds.cs` constants, and `AegisCommands` registrations before packaging.

Validation completed:

- Visual Studio extension build/package: pass; command table validation ran before the VSIX was produced.

## 2026-05-09 - Validation Documentation Refresh

Focus:

- Keep the living stabilization reports aligned with the current test and packaging baseline.
- Remove stale validation wording that still described older Core test counts and the prior Website build warning.

Actions:

- Updated `docs/ECOSYSTEM_STABILIZATION.md` with the current Core, Website, Desktop, VS Code, and Visual Studio validation state.
- Updated `VALIDATION_REPORT.md` so the main validation table reflects the latest package guards and the warning-free Website production build.
- Clarified older migration-phase validation rows so superseded Website build warnings are clearly historical, not current regressions.

Validation completed:

- Aegis Core tests: pass, 51 tests.
- VS Code extension lint/package: pass.
- Website focused frontend API/runtime/task tests: pass, 40 tests.
- Website frontend production build: pass, no Vite chunk-size warning.
- Desktop Release build and quick smoke: pass.

## 2026-05-09 - Website Core Bridge Malformed JSON Handling

Focus:

- Keep Website degraded-mode reporting precise when something other than Aegis Core answers on the Core port.
- Preserve HTTP reachability/status details when Core bridge responses are malformed JSON.

Actions:

- Updated the Website Core bridge to catch JSON parsing failures after the HTTP response status is known.
- Added regression coverage for an HTTP 200 Core health response that returns HTML instead of a `/v1` JSON envelope.

Validation completed:

- Website Core bridge and runtime-health tests: pass, 11 tests.
- Website Core bridge, config, runtime-health, and model-inventory tests: pass, 23 tests.
- Website backend compile check: pass.

## 2026-05-09 - VS Code Request Diagnostic Redaction

Focus:

- Keep VS Code Core/Ollama degraded-mode messages useful without exposing local workspace query strings in timeout or invalid-JSON errors.

Actions:

- Replaced full `url.href` request diagnostics with a `formatRequestTarget` helper that keeps origin and endpoint path while dropping query parameters.
- Added a VS Code package lint guard so full request URL logging cannot be reintroduced accidentally.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass; package lint ran before archive creation.

## 2026-05-09 - Visual Studio Ollama Error Hardening

Focus:

- Make Visual Studio model detection and chat failures actionable when Ollama returns HTTP errors, empty bodies, or malformed JSON.

Actions:

- Replaced raw `EnsureSuccessStatusCode()` usage in the Visual Studio Ollama client with bounded error extraction from Ollama JSON/text responses.
- Added contextual parsing errors for empty or invalid Ollama JSON responses during model listing and chat.
- Disposed HTTP response objects consistently in the model and chat paths.

Validation completed:

- Visual Studio extension build/package: pass; command-table and VSIX metadata guards ran before packaging.

## 2026-05-09 - Desktop Runtime Error Detail Hardening

Focus:

- Keep Desktop degraded-mode messages useful across Website backend and Aegis Core error envelope shapes.

Actions:

- Expanded the shared desktop HTTP error-detail extractor to recognize top-level `error`, top-level `message`, and nested `data.error`/`data.message` fields in addition to FastAPI `detail`.
- Normalized and bounded extracted error details before they are shown in Desktop health/runtime messages.

Validation completed:

- Desktop Release build: pass, 0 warnings.

## 2026-05-09 - Aegis Core Hybrid Model Router

Focus:

- Add local-first hybrid model routing to Aegis Core without migrating existing Website or IDE workflows.
- Keep cloud providers optional, approval-gated, and unable to receive secret-like workspace context.

Actions:

- Added shared Core settings for `local_only`, `hybrid`, and `cloud_allowed` routing modes, local model roles, LM Studio URL, preferred cloud provider/model, max context, and cost warnings.
- Added provider inventory and route contracts for Ollama, LM Studio, OpenAI, Anthropic, Google, and OpenRouter.
- Added OS credential storage hooks for provider API keys; keys are not stored in `.aegis/config.json`.
- Added route planning that keeps normal tasks local and marks hard debugging/repo-wide planning cloud routes as approval-required until clients show sanitized context and receive approval.
- Added an experimental gated completion endpoint that rejects cloud calls without routing mode permission, approval, sanitized context, and stored credentials.
- Documented the new router contracts in Core and ecosystem API/architecture docs.

Validation completed:

- Aegis Core contract tests: pass, 56 tests.
- Aegis Core compile check: pass.

## 2026-05-09 - Aegis Core Autonomous Task Orchestration

Focus:

- Let Core organize larger goals into supervised staged work without enabling uncontrolled edits or risky commands.

Actions:

- Added `.aegis/orchestration-queue.json` and `.aegis/active-orchestration.json` state for objective, task queue, active step, approval gates, validation results, rollback metadata, and safety notes.
- Added `/v1/orchestration/plan`, `/v1/orchestration`, and `/v1/orchestration/step` contracts.
- Added CLI support through `aegis orchestrate`.
- Kept file edits, deletions, package installs, build/test/lint validation, and cloud context behind explicit approval gates.
- Wired completed orchestration tasks into `roadmap.md`, `decisions.md`, `validation-log.md`, and `agent-history.json`.

Validation completed:

- Aegis Core contract tests: pass, 61 tests.

## 2026-05-09 - Aegis Core Multi-Agent Specialization

Focus:

- Make Core orchestration feel like a small supervised local development team without loosening approval gates.

Actions:

- Added Planner, Architect, Coder, Reviewer, Tester, Repair, and Documentation agent profiles.
- Added `/v1/agents` and `aegis agents` for roster/coordination metadata.
- Assigned every orchestration queue task a single `owner_agent`.
- Added active-agent, agent-pipeline, agent-decision, and coordination-conflict fields to orchestration dashboard responses.
- Recorded agent decisions in `agent-history.json`.

Validation completed:

- Aegis Core contract tests: pass, 63 tests including agent roster, owned orchestration tasks, approval gates, and coordination-conflict reporting.

## 2026-05-09 - Aegis Core Workflow Automation

Focus:

- Let Core run safe recurring and trigger-based maintenance workflows without becoming an uncontrolled background editor.

Actions:

- Added `/v1/jobs`, `/v1/jobs/run`, and `aegis jobs`.
- Added default maintenance jobs for daily project scans, weekly roadmap updates, dependency review, build health checks, stale TODO scans, documentation drift, recent changes, broken references, project health reports, next-best-task suggestions, and validation status checks.
- Stored job state in `.aegis/jobs-state.json` and appended run history to `.aegis/jobs-log.md`.
- Kept build/test/lint execution behind explicit approval; jobs may only scan, summarize, report, recommend, and write generated `.aegis` memory/log files automatically.
- Updated contracts, API docs, architecture docs, runtime consolidation notes, and client compatibility guidance.

Validation completed:

- Aegis Core contract tests: pass, 69 tests including job dashboard, safe job run logs, due scheduled jobs, trigger execution, approval-gated build health, and broken-reference reporting.

## 2026-05-09 - Aegis Core Observability and Quality Intelligence

Focus:

- Make Core aware of local project health over time without adding unsafe automation.
- Use quality trends to guide supervised Planner Agent decisions before future work starts.

Actions:

- Added the `quality.dashboard` and `quality.snapshot` Core contracts.
- Added `/v1/quality`, `/v1/quality/snapshot`, and `aegis quality`.
- Added `.aegis/health-history.json` snapshot tracking plus generated daily and weekly quality reports.
- Added health scoring, validation/build/test/lint status extraction, dependency drift, TODO/known-bug counts, stale documentation checks, complexity hotspots, risky diff detection, repeated repair/model failure signals, and frequently changed file tracking.
- Added a safe `quality-intelligence-snapshot` maintenance job that writes only generated `.aegis` health artifacts.
- Wired Planner Agent orchestration planning to read quality data and surface risk-aware guidance.
- Updated API, architecture, runtime consolidation, client responsibility, and compatibility docs.

Validation completed:

- Aegis Core contract tests: pass, 74 tests including quality dashboard, read-only dashboard behavior, snapshot history, trend detection, quality job execution, and Planner integration.

## 2026-05-09 - Aegis Core Knowledge Graph Intelligence

Focus:

- Move Core from simple file indexing toward local semantic project understanding.
- Keep graph intelligence deterministic, local-first, and advisory instead of granting edit authority.

Actions:

- Added the `knowledge.graph` and `knowledge.query` Core contracts.
- Added `/v1/knowledge/graph`, `/v1/knowledge/query`, and `aegis knowledge`.
- Added `.aegis/knowledge-graph.json` and `.aegis/knowledge-summary.md` generated artifacts.
- Built graph nodes for files, systems, symbols, services, UI components, APIs, tasks, roadmap items, architecture decisions, bugs, validation failures, risks, and agent-history events.
- Added relationship edges for `uses`, `depends_on`, `calls`, `implements`, `breaks`, `related_to`, `tested_by`, and `mentioned_in_roadmap`.
- Added deterministic query support for dependents, unstable modules, roadmap/module links, API feature links, and historical context.
- Added graph clusters, architecture hotspots, unstable modules, and a visualization subset for future Desktop graph views.
- Wired Planner Agent orchestration planning to read graph summaries for impacted systems, related history, and suggested context.
- Updated API, architecture, runtime consolidation, client responsibility, and compatibility docs.

Validation completed:

- Aegis Core contract tests: pass, 77 tests including graph persistence, read-only graph behavior, API/file/doc/validation relationships, graph query responses, and Planner graph integration.

## 2026-05-09 - Provider Credential Delete Diagnostics

Focus:

- Keep the hybrid model router trustworthy when provider-key removal touches OS credential storage.
- Preserve harmless no-op behavior for missing keys while surfacing real credential backend failures.

Actions:

- Changed keyring-backed provider-key deletion to verify whether a key exists before deleting it.
- Kept missing provider keys as `removed: false`.
- Surfaced keyring read/delete backend failures as `CredentialStoreError`, allowing `/v1/providers/{provider_id}/key` deletes to return clear degraded `503` responses.
- Added focused regression tests for missing-key deletion and credential backend delete failure.

Validation completed:

- Aegis Core contract tests: pass, 87 tests.
- Aegis Core compile check: pass.
- VS Code extension compile smoke: pass.

## 2026-05-09 - Provider Error Secret Redaction

Focus:

- Keep optional cloud-provider diagnostics useful without exposing provider keys.
- Preserve local-first privacy controls when provider connection failures include request URLs.

Actions:

- Added inline redaction for query-string provider keys such as `?key=...`.
- Added inline redaction for common assignment-style secrets and bearer tokens before diagnostic output is returned or logged.
- Added regressions for direct diagnostic scrubbing and provider connection errors that include a Google-style API key URL.

Validation completed:

- Aegis Core contract tests: pass, 89 tests.
- Aegis Core compile check: pass.

## 2026-05-09 - Website Core Bridge Error Redaction

Focus:

- Keep Website `/api` compatibility safe when it adapts Aegis Core degraded responses.
- Ensure adapter shims preserve local-first privacy even if Core or a provider returns secret-like error text.

Actions:

- Added Website Core bridge redaction for query-string keys, bearer tokens, URL credentials, and common assignment-style secrets.
- Redacted Core `ok=false` details, deprecation text, and HTTP exception messages before they are returned through adapter results.
- Updated the Website Core adapter documentation with the new error-redaction rule.
- Added regressions for redacted Core error details, HTTP error URLs, and deprecation text.

Validation completed:

- Website Core bridge tests: pass, 12 tests.
- Website Core bridge/config/runtime-health/model-inventory tests: pass, 26 tests.
- Website backend compile check: pass.
- Aegis Core contract tests: pass, 89 tests.
- VS Code extension compile smoke: pass.

## 2026-05-09 - Desktop Diagnostic Redaction

Focus:

- Keep Desktop backend/Core health and API failure messages useful without exposing credential-like details.
- Align Desktop diagnostics with the redaction behavior now shared by Core, Website, VS Code, and Visual Studio surfaces.

Actions:

- Added a native Desktop diagnostic redactor for query-string keys, bearer tokens, URL credentials, and assignment-style secrets.
- Routed Desktop JSON error envelope extraction, backend health failures, transport errors, and Core `ok=false` envelope details through the redactor.
- Kept diagnostic messages bounded to 240 characters.

Validation completed:

- Desktop Release build: pass, 0 warnings.
- Aegis Core contract tests: pass, 89 tests.
- VS Code extension compile smoke: pass.

## 2026-05-09 - Visual Studio Diagnostic Redaction

Focus:

- Keep Visual Studio Health Check, Core sync, and Ollama failure messages useful without exposing credential-like details.
- Align the Visual Studio client with the Core and Website adapter redaction behavior.

Actions:

- Added a shared Visual Studio diagnostic redactor for query-string keys, bearer tokens, URL credentials, and assignment-style secrets.
- Routed Aegis Core HTTP errors, Core `ok=false` envelope details, Core deprecation text, and Ollama HTTP errors through the redactor.
- Updated Visual Studio extension changelog and release notes.

Validation completed:

- Visual Studio extension Release build: pass, 0 warnings.
- Aegis Core contract tests: pass, 89 tests.
- VS Code extension compile smoke: pass.

## 2026-05-09 - VS Code Output Diagnostic Redaction

Focus:

- Keep VS Code degraded-mode, rollback, model, and memory diagnostics useful without leaking credential-like values.
- Avoid hiding legitimate parser/model messages such as `unexpected token` while still redacting actual key, token, password, and authorization values.

Actions:

- Added a diagnostic redactor separate from the conservative memory-context sanitizer.
- Routed VS Code output-channel fallback messages, rollback failures, model failures, memory-write failures, and extension error state through the redactor.
- Kept Core/Ollama HTTP error details bounded while preserving non-secret diagnostic wording.

Validation completed:

- VS Code extension lint: pass.
- Aegis Core contract tests: pass, 89 tests.

## 2026-05-09 - VS Code Diagnostic Lint Guard

Focus:

- Prevent user-visible VS Code diagnostics from drifting back to raw exception text.
- Keep health-check and status-panel errors both readable and redacted.

Actions:

- Routed VS Code health-check, setup checklist, status-panel, shell-probe, and validation fallback errors through `safeErrorMessage`.
- Switched health-check detail cleanup from the memory-context sanitizer to the diagnostic redactor so normal parser wording remains visible.
- Extended VS Code package lint to fail if raw `error.message` is interpolated into output-channel, notification, status, health-check, or structured diagnostic output paths.

Validation completed:

- VS Code extension lint: pass.

## 2026-05-09 - Visual Studio Health Diagnostic Guard

Focus:

- Keep Visual Studio health-check, rollback, and command failure diagnostics readable without exposing credential-like exception details.
- Add a release-build guard so these user-visible paths cannot drift back to raw exception messages.

Actions:

- Routed Visual Studio health-check failures for `.aegis`, Core registration/reachability, Ollama reachability, and build integration through `DiagnosticRedactor`.
- Redacted command-level exception output and rollback manifest read failures before they are shown in the tool window.
- Extended the Visual Studio VSIX build script to fail if health-check, command error, or rollback paths reintroduce raw exception text.
- Updated Visual Studio extension changelog and release notes.

Validation completed:

- Visual Studio extension Release build/package: pass, 0 warnings.
- Aegis Core contract tests: pass, 89 tests.

## 2026-05-09 - Authorization Header Redaction Parity

Focus:

- Close a redaction ordering gap where `Authorization: Bearer/Basic/Digest ...` diagnostics could redact the auth scheme but leave the trailing credential visible.
- Keep Website `/api` adapter errors and Visual Studio diagnostics aligned with the Desktop and VS Code redaction behavior.

Actions:

- Added full authorization-header redaction to the Website Core bridge adapter before generic assignment-style redaction runs.
- Added full authorization-header redaction to the Visual Studio diagnostic redactor before bearer and assignment-style redaction.
- Extended the Visual Studio VSIX build guard so the authorization-header redaction pattern and ordering are checked during packaging.
- Added a Website Core bridge regression for `Authorization: Basic ...` error details.

Validation completed:

- Website Core bridge tests: pass, 13 tests.
- Visual Studio extension Release build/package: pass, 0 warnings.
- Aegis Core contract tests: pass, 89 tests.

## 2026-05-09 - Aegis Core Provider Error Redaction Parity

Focus:

- Preserve useful hybrid-provider diagnostics without leaking authorization headers, JSON key fields, URL credentials, or provider query keys.
- Keep validation and memory logs on the stricter whole-line scrubber so secret-like command output stays hidden.

Actions:

- Added a Core inline diagnostic redactor for provider-facing error messages.
- Routed hybrid model router HTTP and connection failures through inline redaction while keeping shared `scrub()` behavior conservative.
- Added regressions for authorization headers, JSON API key fields, URL credentials, provider query keys, and strict validation-log redaction.

Validation completed:

- Aegis Core contract tests: pass, 92 tests.

## 2026-05-09 - VS Code JSON Diagnostic Redaction Guard

Focus:

- Prevent VS Code Core/Ollama error bodies from leaking JSON-shaped provider secrets such as `"api_key":"..."`.
- Keep the extension packaging lint tied to the actual redaction function so release checks catch future drift.

Actions:

- Extended VS Code diagnostic redaction to cover quoted JSON secret fields while preserving non-secret error details.
- Added package-lint redaction smoke checks for JSON key fields, authorization headers, URL credentials, and query-string tokens.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass.

## 2026-05-09 - Cross-Client JSON Diagnostic Redaction Parity

Focus:

- Keep Website, Desktop, and Visual Studio error diagnostics aligned with the Core and VS Code JSON secret-field redaction behavior.
- Preserve useful provider/Core error context while redacting quoted JSON fields such as `"api_key":"..."`.

Actions:

- Added JSON-shaped secret-field redaction to the Website Core bridge.
- Added JSON-shaped secret-field redaction to the Desktop diagnostic redactor.
- Added JSON-shaped secret-field redaction to the Visual Studio diagnostic redactor and strengthened the VSIX build guard.
- Added a Website Core bridge regression for JSON secret-field redaction.

Validation completed:

- Website Core bridge redaction tests: pass, 3 tests.
- Visual Studio extension Release build/package: pass.
- Desktop Release build: pass, 0 warnings.

## 2026-05-09 - VS Code Release Command Quoting Hardening

Focus:

- Keep VS Code package/install scripts reliable from Windows workspaces with unusual but valid path characters.
- Prevent `cmd.exe` from expanding `%...%` path segments or treating caret characters as escapes when invoking `npx` and `code` command shims.

Actions:

- Escaped percent and caret characters in the shared VS Code release command runner.
- Exported the command-quoting helper and added package-lint assertions for plain, spaced, percent-containing, and caret-containing arguments.

Validation completed:

- VS Code extension lint: pass.
- VS Code VSIX package: pass.

## 2026-05-09 - Visual Studio Release Folder Hygiene

Focus:

- Keep the Visual Studio release folder aligned with the stricter VSIX archive hygiene checks.
- Prevent stale internal files from surviving in `release/` after an older or manual packaging pass.

Actions:

- Replaced one-off `DOGFOODING_NOTES.md` cleanup with a source-only release-file cleanup list.
- Removed stale internal dogfooding notes, local detected-model inventories, and repository-only `.gitignore` files before each build/package run.
- Updated the root and Visual Studio changelogs with the release hygiene guard.

Validation completed:

- Visual Studio extension Release build/package: pass.
- Stale release-folder cleanup smoke: pass for `DOGFOODING_NOTES.md`, `DETECTED_MODELS.md`, and `.gitignore`.

## 2026-05-09 - Website E2E Wrapper Normalization

Focus:

- Keep the Website browser E2E wrapper aligned with the doctor and backend smoke wrappers.
- Avoid confusing failures from relative project roots or trailing slashes in custom backend/frontend URLs.

Actions:

- Normalized `Root` with `Resolve-Path -LiteralPath` before deriving the Playwright script path, lock name, and environment variables.
- Trimmed trailing slashes from `BackendUrl` and `FrontendUrl` before health probes and E2E environment setup.

Validation completed:

- Website UI E2E wrapper normalization smoke: pass with relative `Root` and trailing-slash backend/frontend URLs.

## 2026-05-09 - Aegis Core Startup Port Conflict Clarity

Focus:

- Keep Core startup failures actionable when port `8788` is occupied by a hung or non-HTTP local process.
- Avoid falling through to a noisy Uvicorn bind failure after the HTTP health probe times out.

Actions:

- Added a bounded TCP occupancy probe after the `/v1/health` HTTP probe.
- Reported occupied but non-responsive `8788` listeners as explicit port conflicts before launching Core.
- Reused shared Core host/port variables in startup status and conflict messages.

Validation completed:

- Aegis Core start script live-port probe: pass; existing Core on `8788` was identified without launching a duplicate server.

## 2026-05-09 - Core Validation Windows Shim Compatibility

Focus:

- Keep Core validation compatible with Windows package-manager shims while preserving the safe command allow-list.
- Avoid blocking legitimate `npm.cmd`, `pnpm.cmd`, `yarn.cmd`, `dotnet.exe`, or `cmake.exe` validation requests from clients.

Actions:

- Normalized known `.cmd`, `.bat`, and `.exe` validation executable names before allow-list checks.
- Updated Windows package-manager shim resolution so `npm.cmd` can resolve through the same guarded path as `npm`.
- Added Core regressions for safe Windows shim commands and blocked unsafe package-manager actions.

Validation completed:

- Aegis Core focused validation tests: pass, 11 tests.
- Aegis Core contract suite: pass, 93 tests.

## 2026-05-09 - Website Core Contract Field Redaction

Focus:

- Keep Website degraded-mode Core adapter errors useful without leaking secret-like values from malformed contract fields.
- Close the remaining gap between redacted Core error details and raw `api_version`/`kind` mismatch text.

Actions:

- Redacted unexpected Core `api_version` values before returning contract mismatch errors.
- Redacted unexpected Core `kind` values before returning contract mismatch errors.
- Added Website Core bridge regressions for secret-like `api_version` and `kind` mismatch fields.

Validation completed:

- Website Core bridge tests: pass, 15 tests.

## 2026-05-09 - Native Core Contract Field Redaction

Focus:

- Keep Desktop and Visual Studio degraded-mode Core contract errors aligned with Website adapter redaction.
- Prevent malformed local Core responses from echoing secret-like `api_version` or `kind` values into native client diagnostics.

Actions:

- Redacted unexpected Desktop Core `api_version` and `kind` mismatch values through the existing C++ diagnostic redactor.
- Redacted unexpected Visual Studio Core `api_version` and `kind` mismatch values through `DiagnosticRedactor`.
- Extended the Visual Studio packaging guard so AegisCoreClient contract mismatch diagnostics must remain redacted.

Validation completed:

- Visual Studio extension Release build/package: pass.
- Desktop C++ Release build: pass, 0 warnings.

## 2026-05-09 - VS Code Core Envelope Redaction Guard

Focus:

- Make VS Code Core envelope diagnostics redacted by construction, not only by caller-side error wrappers.
- Keep Core contract mismatch and `ok=false` details safe if they are surfaced through health checks, fallbacks, or output-channel paths.

Actions:

- Redacted unexpected Core `api_version` and `kind` values inside `validateAegisCoreEnvelope`.
- Redacted Core `ok=false` error/message/deprecation details inside `coreEnvelopeError`.
- Added package-lint guards for both envelope mismatch redaction and Core envelope error-detail redaction.

Validation completed:

- VS Code package lint: pass via `node scripts/lint-package.js`.
- VS Code VSIX package: pass; package lint ran before archive creation.

## 2026-05-09 - VS Code Package Lint Alias

Focus:

- Remove a small validation workflow papercut found during stabilization.
- Make the package-lint release gate directly runnable through npm without remembering the script path.

Actions:

- Added `npm run lint:package` as a direct alias for `node scripts/lint-package.js`.
- Documented the alias in the root changelog and development log.

Validation completed:

- VS Code package lint alias: pass via `npm run lint:package`.
- VS Code lint: pass.
- VS Code VSIX package: pass; package lint ran before archive creation.

## 2026-05-09 - Website Generated Workspace Ignore Hygiene

Focus:

- Keep release status clean after Website config-update and smoke-style validation runs.
- Prevent generated throwaway workspace roots from surfacing as untracked source files if future runs create more than `.aegis` metadata.

Actions:

- Added `new-workspace/`, `workspace-two/`, and `fallback-workspace/` to `website/.gitignore`.
- Kept the ignore scope limited to known generated Website validation roots instead of ignoring arbitrary workspace names.

Validation completed:

- Website config update tests: pass, 3 tests.
- Git ignore check: pass for generated `new-workspace/`, `workspace-two/`, and `fallback-workspace/` files.

## 2026-05-09 - VS Code Package Lint Documentation

Focus:

- Keep daily release documentation aligned with the direct package-lint npm alias.
- Make the command easy to discover from the root install guide, extension README, and release install guide.

Actions:

- Added `npm run lint:package` to the VS Code build/package command examples.
- Clarified that package and install-local flows also run the package lint gate before VSIX creation.

Validation completed:

- VS Code package lint alias: pass via `npm run lint:package`.
- VS Code VSIX package: pass; package lint ran before archive creation.
- Git diff whitespace check: pass.

## 2026-05-09 - VS Code Package Compile Guard

Focus:

- Keep `npm run package` and `npm run install-local` from shipping a VSIX when `extension.js` has a syntax error.
- Align the release script with the documented install-local behavior.

Actions:

- Added an explicit `node --check extension.js` gate to `scripts/package-release.js` before package lint and VSIX creation.
- Added a package-lint guard so the compile check cannot silently drift out of the release script.

Validation completed:

- VS Code extension lint: pass, including compile and package lint guards.
- VS Code VSIX package: pass; `package-release.js` syntax-checked `extension.js` before linting and packaging.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Settings Persistence Failure Handling

Focus:

- Avoid phantom-success settings saves when `.aegis/config.json` is damaged or blocked.
- Keep settings reads resilient while making failed writes explicit and actionable.

Actions:

- Added `ConfigPersistenceError` for failed Core settings writes.
- Updated `/v1/settings` writes to return `503` when settings cannot be persisted.
- Documented the troubleshooting path for damaged `.aegis/config.json` targets.

Validation completed:

- Core settings/config focused tests: pass, 6 tests.
- Aegis Core contract tests: pass, 93 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Job Persistence Failure Handling

Focus:

- Avoid phantom-success scheduled job runs when `.aegis/jobs-state.json` cannot be persisted.
- Keep blocked jobs-log writes visible without failing otherwise safe scan/report work.

Actions:

- Added `JobPersistenceError` for failed scheduled job state writes.
- Updated `/v1/jobs/run` and the Core CLI to report job persistence failures cleanly.
- Added a warning path when `.aegis/jobs-log.md` cannot be written.

Validation completed:

- Core job focused tests: pass, 9 tests.
- Aegis Core contract tests: pass, 95 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Orchestration Persistence Failure Handling

Focus:

- Avoid silently losing staged autonomous task queues when orchestration state paths are damaged.
- Keep plan creation and step advancement honest if queue or active-plan JSON cannot persist.

Actions:

- Added `OrchestrationPersistenceError` for failed queue and active-plan writes.
- Verified `.aegis/orchestration-queue.json` and `.aegis/active-orchestration.json` after writes.
- Updated API, CLI, troubleshooting, and regression coverage for damaged orchestration state paths.

Validation completed:

- Core orchestration focused tests: pass, 6 tests.
- Aegis Core contract tests: pass, 97 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Credential Error Redaction

Focus:

- Keep optional cloud provider key handling private even when the OS credential backend returns a verbose failure.
- Prevent echoed API keys, bearer tokens, or authorization details from reaching API clients through credential-store errors.

Actions:

- Added credential backend error sanitization in `CredentialStore`.
- Redacted sensitive values echoed by provider key write failures.
- Added regression coverage for read, write, and provider-key endpoint failures.

Validation completed:

- Core credential/provider-key focused tests: pass, 9 tests.
- Aegis Core contract tests: pass, 100 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Quality History Persistence Failure Handling

Focus:

- Avoid false successful quality snapshots when `.aegis/health-history.json` cannot be written.
- Keep long-term health trends trustworthy before daily and weekly reports are generated.

Actions:

- Added `QualityPersistenceError` for failed health-history writes.
- Verified health-history persistence before generating quality reports.
- Updated API, CLI, scheduled quality job behavior, troubleshooting, and regression coverage.

Validation completed:

- Core quality focused tests: pass, 7 tests.
- Aegis Core contract tests: pass, 102 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Knowledge Graph Persistence Failure Handling

Focus:

- Avoid false successful knowledge graph recordings when graph or summary artifacts cannot be written.
- Keep saved project-intelligence relationships trustworthy for later queries and planning.

Actions:

- Added `KnowledgePersistenceError` for failed graph and summary writes.
- Verified persisted `knowledge-graph.json` and `knowledge-summary.md` after recording.
- Updated API, CLI, troubleshooting, and regression coverage for damaged knowledge artifact paths.

Validation completed:

- Core knowledge graph focused tests: pass, 5 tests.
- Aegis Core contract tests: pass, 104 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Personal Intelligence Profile Persistence Handling

Focus:

- Avoid false successful personal profile saves when `.aegis/personal-engineering-profile.json` cannot be written.
- Keep personal workflow memory transparent, local, inspectable, and resettable.

Actions:

- Added `PersonalIntelligencePersistenceError` for failed profile writes.
- Verified the persisted personal profile after explicit save requests before reporting success.
- Made reset report a structured failure when the profile path is damaged instead of claiming reset success.
- Updated API, CLI, troubleshooting, and regression coverage for damaged personal profile paths.

Validation completed:

- Core personal intelligence focused tests: pass, 4 tests.
- Aegis Core contract tests: pass, 106 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Roadmap Persistence Failure Handling

Focus:

- Avoid false successful roadmap generation when `.aegis/roadmap.md` cannot be written.
- Preserve safe plan-only agent continuation when roadmap persistence is damaged.

Actions:

- Added `RoadmapPersistenceError` for failed roadmap writes.
- Verified generated roadmap markdown after writes before returning persisted roadmap paths.
- Updated API, CLI, troubleshooting, and regression coverage for damaged roadmap paths.
- Kept agent continuation resilient by surfacing roadmap persistence failures as memory warnings.

Validation completed:

- Core roadmap and continuation focused tests: pass, 4 tests.
- Aegis Core contract tests: pass, 108 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Validation Log Persistence Visibility

Focus:

- Avoid silent loss of validation evidence when `.aegis/validation-log.md` cannot be appended.
- Keep command results usable while making damaged validation history visible to clients.

Actions:

- Added `validation_log` result metadata for persisted validation-log status.
- Added `memory_warning` when a validation run cannot append its log entry.
- Kept direct `append_validation_log` callers non-throwing while returning a structured persistence status.
- Updated contract metadata, troubleshooting, changelog, and regression coverage for damaged validation-log paths.

Validation completed:

- Core validation focused tests: pass, 12 tests.
- Aegis Core contract tests: pass, 109 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Agent Plan Persistence Warnings

Focus:

- Avoid silent loss of active continue/repair plan handoffs when their `.aegis` JSON paths are damaged.
- Preserve safe plan-only behavior while making memory persistence issues visible to clients.

Actions:

- Added verified active-plan writes for continue and repair agent plans.
- Surfaced damaged `active-agent-plan.json` and `active-repair-plan.json` paths as plan memory warnings.
- Updated contract metadata, troubleshooting, changelog, and regression coverage for damaged active-plan paths.

Validation completed:

- Core continue/repair agent focused tests: pass, 6 tests.
- Aegis Core contract tests: pass, 111 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Core Workspace Scan Artifact Persistence Metadata

Focus:

- Avoid silent loss of workspace scan artifacts when `.aegis` index, cache, summary, or architecture-map paths are damaged.
- Keep scans usable while making memory artifact health visible to clients.

Actions:

- Added per-artifact `memory_artifacts` persistence metadata to persisted workspace scans.
- Added `memory_warnings` when scan artifacts cannot be written or verified.
- Verified JSON and generated Markdown scan artifacts after writes.
- Updated workspace scan contracts, troubleshooting, changelog, and regression coverage for damaged scan artifact paths.

Validation completed:

- Core workspace scan focused tests: pass, 7 tests.
- Aegis Core contract tests: pass, 111 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website Dependency Profile Build Guard Parity

Focus:

- Keep Website dependency profiles aligned with validation planning for native Desktop and extension workspaces.
- Prefer project-owned root build guard scripts over lower-level native fallback commands in project intelligence.

Actions:

- Added root `build.py` and `build.ps1` detection to Website dependency-profile validation commands.
- Suppressed CMake and MSBuild native fallback validation commands when a root build guard script is present while preserving CMake/MSBuild metadata.
- Added regression coverage for root PowerShell build guard parity in native dependency profiles.

Validation completed:

- Website dependency-profile focused tests: pass, 6 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Website workspace/storage regression suite: pass, 62 tests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website Agent PowerShell Build Guard Parity

Focus:

- Keep Website agent continuation aligned with Website validation discovery for existing projects.
- Avoid falling back to CMake/MSBuild suggestions when an existing workspace already owns a root PowerShell build guard.

Actions:

- Taught existing-project no-change continuation to recognize PowerShell module surfaces and propose the safe root `build.ps1` validation command.
- Treated `build.ps1` as a native build surface during draft stack-adherence checks.
- Allowed exact no-profile `powershell` / `pwsh` root `build.ps1` commands to be promoted as draft validation commands even when the command reason is blank.
- Added agent parser regressions for root PowerShell continuation and draft validation promotion.

Validation completed:

- Website agent parser focused PowerShell continuation/draft-validation tests: pass, 11 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Website agent parser regression suite: pass, 96 tests and 10 subtests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website Project Builder PowerShell Guard Parity

Focus:

- Keep Website project-builder existing-project validation aligned with validation discovery and agent continuation.
- Avoid running CMake/MSBuild fallbacks when an existing workspace already provides a root PowerShell build guard.

Actions:

- Updated existing-project validation command selection to prefer root `build.ps1` before Visual Studio or CMake fallback commands.
- Preserved CMake/Visual Studio preset continuity while using the workspace-owned PowerShell guard for validation.
- Added continuity detection for existing PowerShell module workspaces with `build.ps1` and module source files.
- Added project-builder plan regressions for CMake projects with PowerShell guards and existing PowerShell modules.

Validation completed:

- Project-builder focused existing guard planning tests: pass, 4 tests.
- Website dependency-profile focused tests: pass, 6 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Website project-scaffolder regression suite: pass, 120 tests and 46 subtests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website PowerShell Guard History Recovery

Focus:

- Keep validation-history recovery aligned with the narrowed Website PowerShell execution contract.
- Preserve successful local-first `build.ps1` guard workflows without accepting broad PowerShell history entries.

Actions:

- Reused the shared PowerShell guard matcher when recovering validation commands from `.aegis/command_history.json`.
- Kept `powershell`, `powershell.exe`, `pwsh`, and `pwsh.exe` history commands blocked unless they match the exact no-profile root `build.ps1` guard.
- Added regression coverage for recovering a Windows-style `.\build.ps1` guard command and rejecting successful but broad `-Command` PowerShell entries.

Validation completed:

- Website validation manager regression suite: pass, 23 tests and 4 subtests.

## 2026-05-09 - Website Command History Launcher Alias Filtering

Focus:

- Prevent Windows executable aliases from bypassing Website command-history safety filtering.
- Keep previously successful install, shell, publishing, and destructive commands out of recovered validation suggestions.

Actions:

- Added executable-name normalization for command-history safety checks, including `.exe`, `.cmd`, and `.bat` launcher forms.
- Blocked launcher aliases for install commands, shell execution, destructive Git operations, package publishing, network fetch tools, Docker, and Windows system mutation commands.
- Added regression coverage for `cmd.exe /c`, `npm.cmd install`, and `git.exe reset --hard` history entries.

Validation completed:

- Website validation manager regression suite: pass, 23 tests and 4 subtests.

## 2026-05-09 - Website Agent Draft Validation Alias Filtering

Focus:

- Keep agent-proposed draft validation commands aligned with Website command-history safety filtering.
- Prevent validation-like command reasons from promoting install or destructive Windows launcher aliases.

Actions:

- Moved the validation launcher-alias filter into the shared validation command helper module.
- Reused the validation command alias and PowerShell guard checks before accepting agent draft validation commands.
- Added regressions for blocked `cmd.exe /c npm install`, `npm.cmd install`, and `git.exe reset --hard` draft commands.
- Added a positive regression showing safe Windows launcher validation such as `npm.cmd test` can still be promoted when the command reason is validation-oriented.

Validation completed:

- Website agent parser focused draft-validation tests: pass, 8 tests.
- Website agent parser regression suite: pass, 98 tests and 13 subtests.
- Website validation manager regression suite: pass, 23 tests and 4 subtests.
- Website command-runner safety suite: pass, 21 tests.
- Website backend compile check: pass.

## 2026-05-09 - Website Readiness Remembered Validation Safety

Focus:

- Keep workspace readiness and autopilot summaries from surfacing unsafe remembered validation commands as runnable next actions.
- Share the remembered-validation safety contract across discovery, readiness scoring, and status summaries.

Actions:

- Added a shared `is_safe_remembered_validation_command` helper for command-history recovery and readiness consumers.
- Filtered unsafe `command_history.validation_command` fallbacks before readiness scoring, repair briefs, and autopilot status summaries use them.
- Fixed readiness classification so detected config files without a safe validation command no longer fall through to a ready state.
- Added regressions proving unsafe remembered launcher aliases are skipped while earlier safe validation history can still drive status.

Validation completed:

- Website workspace autopilot helper tests: pass, 10 tests.
- Website agent parser focused readiness/history/repair tests: pass, 9 tests.
- Website agent parser regression suite: pass, 99 tests and 13 subtests.
- Website command-runner safety suite: pass, 21 tests.
- Website backend compile check: pass.

## 2026-05-09 - Website Quoted Launcher Validation Filtering

Focus:

- Close the Windows `Program Files` launcher-path gap in remembered validation command filtering.
- Keep quoted executable paths usable for safe validation commands while blocking quoted install and destructive aliases.

Actions:

- Parsed remembered validation launcher commands with Windows-preserving shell tokenization before extracting the executable name.
- Added helper coverage for quoted and unquoted `npm.cmd`, `git.exe`, and `cmd.exe` paths.
- Extended validation-manager and agent draft-validation regressions to cover quoted Windows launcher install commands.

Validation completed:

- Website validation command helper tests: pass, 2 tests and 5 subtests.
- Website validation manager regression suite: pass, 23 tests and 4 subtests.
- Website agent parser focused draft-validation tests: pass, 8 tests.
- Website agent parser regression suite: pass, 99 tests and 14 subtests.
- Website workspace autopilot helper tests: pass, 10 tests.
- Website command-runner safety suite: pass, 21 tests.
- Website backend compile check: pass.

## 2026-05-09 - Website Command Runner Destructive Alias Blocking

Focus:

- Prevent destructive commands from bypassing Website execution safeguards through executable aliases.
- Keep explicit command allowlists from turning `git.exe reset --hard` or quoted Git paths into runnable commands.

Actions:

- Added argv-level destructive-command detection after command parsing and executable normalization.
- Blocked destructive Git subcommands and Windows deletion/system mutation executables by normalized executable name.
- Added command-runner regressions for plain, `.exe`, and quoted Git reset aliases when `git` is explicitly allowlisted.

Validation completed:

- Website command-runner safety suite: pass, 22 tests and 3 subtests.
- Website validation command helper tests: pass, 2 tests and 5 subtests.
- Website backend compile check: pass.

## 2026-05-09 - Website Command Runner Git Option Safety

Focus:

- Prevent destructive Git subcommands from bypassing Website execution safeguards behind global Git options.
- Keep explicit `git` allowlists safe for validation contexts that should never reset, clean, or checkout workspace files.

Actions:

- Added Git subcommand extraction that skips global options with or without option values.
- Extended destructive-command detection to block `reset`, `clean`, and `checkout` after options such as `-C`, `-c`, and `--work-tree`.
- Added command-runner regressions for `git -C . reset --hard`, `git.exe -c ... clean -fd`, and quoted Git paths with `--work-tree`.

Validation completed:

- Website command-runner safety suite: pass, 22 tests and 6 subtests.
- Website validation command helper suite: pass, 2 tests and 5 subtests.
- Website backend compile check: pass.
- Repository whitespace check: pass.

## 2026-05-09 - VS Code Validation Guard Package Lint

Focus:

- Keep the VS Code local fallback validation runner limited to exact known-safe commands.
- Prevent future package releases from accidentally permitting shell launchers, install commands, chained commands, or destructive Git aliases.
- Align extension documentation with the actual validation command allowlist.

Actions:

- Added package-lint regressions for `isSafeValidationCommand` covering representative safe validation commands and unsafe launcher/destructive/chained forms.
- Updated VS Code extension documentation to include lint, typecheck, and Go validation commands already supported by the fallback runner.
- Documented the fallback validation safety contract in the root changelog, extension release changelog, and troubleshooting guide.

Validation completed:

- VS Code extension lint: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Aegis Core Custom Validation Shim Safety

Focus:

- Prevent Core custom validation commands from running workspace-local or arbitrary-path executable shims that only look safe by basename.
- Preserve normal detected validation behavior for bare tool names and standard Windows `.cmd`/`.exe` shims.

Actions:

- Blocked path-qualified validation executables unless they are the current Python interpreter path.
- Stopped treating `.bat` aliases as safe validation shims.
- Added Core validation regressions for workspace-relative shims, absolute shim paths, `.bat` aliases, arbitrary Python executable paths, and the allowed current Python interpreter.
- Documented the custom validation shim safety contract in Core docs, root troubleshooting, and the changelog.

Validation completed:

- Aegis Core validation runner focused tests: pass.
- Aegis Core contract suite: pass, 139 tests.
- Aegis Core package compile check: pass.
- Repository whitespace check: pass.

## 2026-05-09 - Website PowerShell Guard Windows Path Compatibility

Focus:

- Keep the documented PowerShell module validation command usable in Website command execution.
- Preserve the narrow root `build.ps1` safety contract while accepting the Windows-style `.\build.ps1` spelling users see in generated README files.

Actions:

- Extended the shared Website PowerShell guard matcher to recognize exact `.\build.ps1` and bare `build.ps1` root guard forms.
- Normalized accepted PowerShell guard commands to `./build.ps1` before execution so shell parsing does not turn `.\build.ps1` into `.build.ps1`.
- Added command-runner coverage for the documented Windows-style root guard command.

Validation completed:

- Website command-runner safety suite: pass, 21 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Website project-builder/PowerShell-template focused tests: pass, 7 tests.
- Website agent parser focused PowerShell validation tests: pass, 7 tests.
- Website backend compile check: pass.
- Website project-scaffolder regression suite: pass, 120 tests and 46 subtests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website PowerShell Command Execution Narrowing

Focus:

- Keep the Website `build.ps1` validation guard usable without exposing broad PowerShell command execution.
- Align command execution safety with the narrow command shape emitted by validation discovery, agent continuation, and project-builder planning.

Actions:

- Blocked Website `powershell` and `pwsh` commands unless they exactly invoke root `build.ps1` with `-NoProfile -ExecutionPolicy Bypass -File`.
- Added command-runner regressions for blocked `-Command` / escaped-path PowerShell invocations and the allowed root guard command.
- Documented the narrow PowerShell validation contract in troubleshooting and stabilization notes.

Validation completed:

- Website command-runner safety suite: pass, 20 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Project-builder focused PowerShell guard tests: pass, 3 tests.
- Website project-scaffolder regression suite: pass, 120 tests and 46 subtests.
- Website agent parser focused validation tests: pass, 12 tests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.

## 2026-05-09 - Website PowerShell Guard Contract Consolidation

Focus:

- Reduce drift risk across Website validation discovery, dependency profiling, agent continuation, project-builder planning, and command execution.
- Keep the root `build.ps1` contract represented in one small shared helper module.

Actions:

- Added `aegis_ai.validation_commands` with the canonical PowerShell guard command and safe matcher helpers.
- Reused the shared command constant in validation discovery, dependency profiling, project presets, project-builder existing validation, and agent draft validation promotion.
- Reused the shared argv matcher in command execution safety checks.

Validation completed:

- Website command-runner safety suite: pass, 20 tests.
- Website validation manager regression suite: pass, 22 tests and 4 subtests.
- Website dependency-profile focused tests: pass, 6 tests.
- Project-builder focused PowerShell guard tests: pass, 3 tests.
- Website agent parser focused validation tests: pass, 12 tests.
- Website backend compile check: pass.
- Website project-scaffolder regression suite: pass, 120 tests and 46 subtests.
- Aegis Core contract tests: pass, 138 tests.
- Git diff whitespace check: pass.
