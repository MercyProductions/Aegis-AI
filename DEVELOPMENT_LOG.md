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
- Added Core predictive planning and change simulation so planned edits can be scored for impacted files, affected systems, dependency ripple, architecture drift, validation cost, rollback complexity, and safer scenario choices before implementation.
- Added Core engineering operations so release readiness, technical debt, lifecycle stage, risk monitoring, maintenance scheduling, productivity bottlenecks, and cross-project coordination can be reviewed from a single read-only dashboard.

Validation completed:

- Aegis Core contract test suite: pass, 79 tests.
- Aegis Core simulate CLI smoke test: pass for single forecast and scenario comparison.
- Aegis Core operations endpoint regressions: pass for single-project coordination and cross-project awareness.
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
