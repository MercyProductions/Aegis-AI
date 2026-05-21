# ChatBot Project Review Roadmap

Generated: 2026-05-21

Project root: `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot`

## Executive Summary

The ChatBot project is no longer just a chatbot. It is a local-first Aegis/Auralith AI workspace made of a native Windows desktop client, React web workspace, FastAPI backend gateway, shared Aegis Core runtime, VS Code extension, Visual Studio extension, release/update tooling, provider-account integrations, model routing, memory, diagnostics, validation, safe editing, and agent workflow systems.

The project is in a strong functional state: the main Core, backend, frontend, desktop build, and VS Code static/unit gates pass locally. The main remaining risk is not missing capability. It is ecosystem complexity: very large files, duplicated ownership between Website and Core, dirty release artifacts, incomplete cross-client release evidence, and several advanced systems that need product-grade safety gates before alpha.

## Current Verified State

Commands run during this review:

```powershell
cd "C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot"

python -m pytest tests -q
cd website\backend
python -m pytest tests -q
cd ..\frontend
npm test
npm run build
cd ..\..\vscode-plugins\aegis-local-autopilot
npm run test:unit
npm run lint
npm run test:smoke
cd ..\..
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Results:

- Aegis Core tests: 309 passed.
- Website backend tests: 888 passed, 186 subtests passed.
- Website frontend tests: 22 test files passed, 190 tests passed.
- Website frontend production build: passed.
- VS Code extension helper tests: passed.
- VS Code extension compile/package lint: passed.
- Native desktop `Release|x64` build: passed with 0 warnings and 0 errors.
- VS Code extension-host smoke: failed because the downloaded VS Code test instance reported `vscode-updating` held and refused launch. This should be retried after the update mutex clears; it is not yet evidence of extension code failure.
- Release packaging was not run in this pass because the release folders are already dirty/deleted and packaging would mutate the tree further.

Current worktree condition:

- The ChatBot repo has a large dirty worktree: about 192 changed, deleted, or untracked status entries.
- Many untracked Core, docs, website, provider-account, extension, and runtime files appear to be active product work.
- Deleted VS Code and Visual Studio `release/` documentation files need a deliberate keep-delete-or-restore decision before packaging.

## Current Project Shape

Major surfaces:

- Native desktop shell: `src/`
- Website frontend: `website/frontend`
- Website backend gateway: `website/backend/aegis_ai`
- Shared Core runtime: `aegis-core/aegis_core`
- VS Code extension: `vscode-plugins/aegis-local-autopilot`
- Visual Studio extension: `visual-studio-extensions/aegis-local-agent-vs`
- Release/update scripts: `scripts/`, `build.ps1`, `VERSION.json`
- Product and platform docs: root docs plus `docs/` and `aegis-core/docs/`

Measured non-generated source/doc inventory, excluding common generated folders such as `node_modules`, `.git`, `dist`, `release`, caches, logs, and test VS Code downloads:

- Total files counted: 808.
- Python files: 330.
- Markdown files: 120.
- TypeScript files: 88.
- JSON files: 62.
- C/C++ headers and sources: 66.
- TSX files: 20.
- PowerShell scripts: 19.
- C# files: 17.

Large source files that should drive architecture work:

| Area | File | Approx lines |
| --- | --- | ---: |
| Native desktop shell | `src/AegisChatApp.cpp` | 16,981 |
| Website app shell | `website/frontend/src/App.tsx` | 11,791 |
| VS Code extension entry | `vscode-plugins/aegis-local-autopilot/extension.js` | 7,145 |
| Website backend agent | `website/backend/aegis_ai/agent.py` | 6,571 |
| Website project scaffolder | `website/backend/aegis_ai/project_scaffolder.py` | 6,251 |
| Website storage | `website/backend/aegis_ai/storage.py` | 5,543 |
| Core contracts | `aegis-core/aegis_core/contracts.py` | 4,930 |
| Native backend client | `src/AegisClient.cpp` | 4,744 |
| Frontend type catalog | `website/frontend/src/types.ts` | 4,608 |
| Website schemas | `website/backend/aegis_ai/schemas.py` | 4,446 |
| Website API app | `website/backend/aegis_ai/main.py` | 4,310 |
| Core autopilot | `aegis-core/aegis_core/autopilot.py` | 3,689 |
| Core server | `aegis-core/aegis_core/server.py` | 3,061 |
| Website model registry | `website/backend/aegis_ai/model_registry.py` | 2,974 |
| Frontend API client | `website/frontend/src/api.ts` | 2,531 |
| Provider accounts panel | `website/frontend/src/components/provider-accounts/ProviderAccountsPanel.tsx` | 2,528 |

Generated/cache files are also very large, especially `.aegis/scan-cache.json` and symbol indexes. They should be treated as runtime artifacts, not source architecture targets.

## Key Findings

### 1. The validation base is strong.

Core, backend, frontend, desktop build, and VS Code unit/static checks are all passing. This is a good baseline for refactoring. The next problem is making those checks one command with release evidence, not a set of manual commands.

### 2. Core is the right authority, but ownership is still split.

Docs correctly describe Aegis Core as the long-term authority for contracts, memory, model routing, workspace intelligence, safe editing, validation, plugins, distributed runtime, provider bridges, and workflow orchestration. Website still owns a lot of mature behavior and fallback logic. That is acceptable short term, but new work should move toward Core-owned contracts and Website/client adapters.

### 3. The frontend and native desktop shells are too large.

`App.tsx` and `AegisChatApp.cpp` are both beyond comfortable change size. They may work today, but every feature added there increases regression risk. The next frontend/native work should be extraction and surface boundaries, not another feature pass.

### 4. Backend modularization has started, but the gateway remains heavy.

The Website backend has route/service/provider-account structure, but `agent.py`, `project_scaffolder.py`, `storage.py`, `schemas.py`, and `main.py` still carry too much domain behavior. Split by domain with compatibility exports.

### 5. Extension parity and packaging are not yet release-grade.

VS Code static/unit checks pass, but extension-host smoke is currently blocked by the VS Code update mutex. Visual Studio extension build/package was not rerun in this pass. Release packaging should wait until the dirty release artifact state is resolved.

### 6. Provider account support needs a product-hardening pass.

The secure-account direction is good: OS credential storage, provider manifests, local CLI bridge probing, and local-first behavior. The missing piece is a single polished provider setup and health UX that explains secrets, auth state, privacy, cost, quota, latency, fallback, and whether the route is API-key, CLI bridge, source-drop, or local endpoint.

## Roadmap

## Phase 0: Stabilize The Current Worktree

Goal:
Create a reliable checkpoint before more large refactors.

Progress added in this phase:

- Added `WORKTREE_STABILIZATION_2026-05-21.md` with a grouped inventory of the current 192-entry dirty worktree.
- Added `KNOWN_UNSTABLE_SURFACES.md` to keep alpha limitations visible while deeper phases proceed.
- Confirmed `.gitignore` already excludes the major generated/cache surfaces: build output, frontend `dist`, `node_modules`, logs, runtime diagnostics, `.aegis`, local environment files, and native build artifacts.
- Identified release-blocking decisions around deleted extension `release/` docs, untracked release/version scripts, `VERSION.json`, `src/core/`, `package-lock.json`, and the deleted `website inspiration.png` artifact.

Work:

- Review all changed, deleted, and untracked files.
- Decide which generated artifacts should remain untracked or ignored.
- Decide whether deleted extension `release/` docs are intentionally removed or should be restored.
- Commit or checkpoint coherent groups: Core runtime, Website provider/accounts, frontend surfaces, extensions, docs, release/update, desktop.
- Keep `VERSION.json` as the release authority and verify every component version matches docs and packages.
- Add a short `KNOWN_UNSTABLE_SURFACES.md` or section in this roadmap for current alpha limitations.

Acceptance:

- Dirty tree is intentionally grouped.
- Generated/cached artifacts are ignored or quarantined.
- Release packaging is not attempted from an ambiguous state.

## Phase 1: Create A Single Validation Matrix

Goal:
Turn manual validation into one repeatable command that writes evidence.

Progress added in this phase:

- Added `scripts/validate-ecosystem.ps1` as the ecosystem validation entry point.
- Added `docs/VALIDATION_MATRIX.md` with standard usage, evidence artifacts, statuses, and opt-in packaging variants.
- The validation runner writes timestamped evidence to `.aegis/release-evidence/<timestamp>/`.
- The runner records tool versions, `git status --short`, release-artifact status, a JSON matrix, a Markdown summary, and one log per gate.
- VS Code extension-host smoke failures that match the VS Code update/mutex condition are classified as `retryable`.
- Desktop smoke, Visual Studio packaging, and release packaging are explicit opt-in gates while the current release folders remain decision-sensitive.
- Verified with `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1 -SkipSmoke`.
- Latest evidence: `.aegis/release-evidence/20260521-034859/validation-summary.md`; overall status `attention`, hard failures `0`, retryable `0`, skipped `5`.

Work:

- Add `scripts/validate-ecosystem.ps1`.
- Run Core tests, Website backend tests, Website frontend tests/build, desktop build, VS Code unit/lint, VS Code smoke, Visual Studio build/package, release packaging dry run, and update dry run.
- Capture stdout summaries and tool versions into `.aegis/release-evidence/<timestamp>/`.
- Treat VS Code extension-host mutex failures as retryable environment failures with a clear status.
- Add optional slow gates for desktop smoke, Website E2E, Visual Studio experimental instance, and live provider checks.

Acceptance:

- One command produces a pass/fail matrix.
- Every failed/skipped gate has a reason.
- Roadmap and release notes link to the latest evidence folder.

## Phase 2: Settle Core/Website Ownership Boundaries

Goal:
Make Core the long-term authority and Website a gateway/client where possible.

Progress added in this phase:

- Added `docs/CORE_WEBSITE_OWNERSHIP.md` as the human-readable source-of-truth for Core `/v1` versus Website `/api` ownership.
- Added `website/backend/aegis_ai/runtime_ownership.py` as the machine-readable ownership matrix.
- Added `GET /api/runtime/ownership` so Website clients can inspect the ownership policy without requiring Core to be online.
- Linked the new ownership source from `WEBSITE_CORE_ADAPTER.md` and `RUNTIME_CONSOLIDATION.md`.
- Added `website/backend/tests/test_runtime_ownership.py` to guard required Phase 2 domains, delegated workflow names, the new ownership endpoint, docs links, and current client migration posture.
- Verified with `python -m pytest tests/test_runtime_ownership.py -q`: 5 passed.
- Verified adjacent seam tests with `python -m pytest tests/test_runtime_ownership.py tests/test_core_runtime_delegation.py tests/test_core_bridge.py -q`: 54 passed.

Work:

- Create an ownership matrix for memory, validation, checkpoint, apply, rollback, provider routing, tasks, model registry, diagnostics, agent runtime, and workspace intelligence.
- Move new workflow logic into Core first.
- Keep Website `/api` compatibility wrappers until clients migrate.
- Add contract tests between Core `/v1`, Website `/api`, frontend `api.ts`, and extension clients.
- Mark fallback behavior explicitly: Core-owned, Website-owned, or compatibility-only.

Acceptance:

- New features have an owning layer before implementation.
- Website and clients do not grow new duplicate engines.
- Compatibility shims have deprecation notes.

## Phase 3: Finish Backend Gateway Modularization

Goal:
Make `website/backend/aegis_ai/main.py` a FastAPI assembly layer.

Progress added in this phase:

- Added `website/backend/aegis_ai/services/core_delegation.py` for Core bridge/delegation response mappers, fallback recording, apply/checkpoint/restore adapters, and Core validation response mapping.
- Updated `website/backend/aegis_ai/main.py` to import those Core delegation helpers instead of owning the mapper logic inline.
- Added `website/backend/tests/test_core_delegation_mappers.py` to cover Core object payload enforcement, error mapping, apply/restore/checkpoint response mapping, and validation-to-repair behavior.
- Added `website/backend/aegis_ai/services/project_builder_service.py` for project-builder route glue, plan caching, preview/scaffold error conversion, and scaffold cache invalidation.
- Updated project-builder route registration in `main.py` to use `ProjectBuilderService`.
- Added `website/backend/tests/test_project_builder_service.py` to cover plan-cache reuse, scaffold invalidation, and HTTP 400 conversion.
- Verified focused seam suite with `python -m pytest tests/test_core_delegation_mappers.py tests/test_project_builder_service.py tests/test_core_runtime_delegation.py tests/test_core_bridge.py tests/test_runtime_ownership.py tests/test_workspace_autopilot_status.py -q`: 69 passed.
- Verified full Website backend suite with `python -m pytest tests -q`: 902 passed, 186 subtests passed.

Work:

- Move runtime interaction helpers and endpoints into a route/service module.
- Move telemetry enrichment/pruning helpers into telemetry service code.
- Move ecosystem audit helpers into ecosystem service code.
- Move Core delegation response mappers into `services/core_client.py` or domain adapters.
- Move project-scaffold API glue away from `main.py`.
- Add focused tests for each extracted route/service.

Acceptance:

- `main.py` mostly wires app, middleware, routers, and lifecycle.
- Route domains own their private helpers.
- Backend tests still pass.

## Phase 4: Split Schemas, Storage, Contracts, And Scaffolding

Goal:
Reduce the largest Python maintenance bottlenecks.

Progress added in this phase:

- Added `website/backend/aegis_ai/repositories/` as the first storage repository package.
- Extracted project-memory persistence into `website/backend/aegis_ai/repositories/project_memory.py`.
- Kept `EventStore.remember_project_note`, `EventStore.project_memory`, `EventStore.relevant_project_memory`, and `EventStore.clear_project_memory` as compatibility wrappers, so existing imports and callers do not need to move yet.
- Added `website/backend/tests/test_project_memory_repository.py` to cover the repository seam, EventStore compatibility, project-memory upsert behavior, relevance search, clearing, and current/legacy workspace alias deduplication.
- Re-ran existing project-memory, schema, and legacy import coverage with `python -m pytest tests/test_project_memory_repository.py tests/test_workspace_and_storage.py::WorkspaceAndStorageTests::test_project_memory_upserts_and_retrieves_notes tests/test_project_intelligence.py tests/test_storage_legacy_import.py tests/test_storage_schema.py -q`: 11 passed.
- Verified full Website backend suite with `python -m pytest tests -q`: 904 passed, 186 subtests passed.

Work:

- Split `website/backend/aegis_ai/schemas.py` by domain with compatibility re-exports.
- Split `website/backend/aegis_ai/storage.py` into repositories: conversations, memory, telemetry, tasks, checkpoints, providers, releases, model registry.
- Split `aegis-core/aegis_core/contracts.py` into contract catalogs by runtime domain.
- Split `website/backend/aegis_ai/project_scaffolder.py` into planners, templates, writers, validators, and metadata.
- Add migration tests for fresh DB and upgraded DB cases.
- Add contract drift tests against frontend and extension types.

Acceptance:

- Existing imports remain compatible.
- New domain modules have focused tests.
- Schema/storage changes can be reviewed without opening 4,000 to 6,000 line files.

## Phase 5: Frontend Architecture Extraction

Goal:
Turn the Website frontend into maintainable surfaces.

Progress added in this phase:

- Added `website/frontend/src/components/app-shell/AppHeader.tsx` as the first app-shell extraction from the 11k+ line `App.tsx`.
- Replaced the inline protected-route header in `App.tsx` with `AppHeader`, keeping search, runtime status, model switcher, theme toggle, memory, approvals, settings, and account controls behavior-compatible through props.
- Added `website/frontend/src/components/app-shell/AppHeader.test.tsx` to lock the extracted header seam with server-rendered coverage.
- Verified focused header coverage with `npm test -- AppHeader`: 1 test passed.
- Verified full frontend tests with `npm test`: 23 test files passed, 191 tests passed.
- Verified production frontend build with `npm run build`.

Work:

- Split `App.tsx` into app shell, routes, providers, and surface components.
- Extract chat transcript/composer/streaming state.
- Extract generated changes/diff/apply/checkpoint panels.
- Extract workspace/project/file navigation.
- Extract model stack and provider accounts.
- Extract memory, observability, command palette, settings, runtime diagnostics, and admin surfaces.
- Split `api.ts` and `types.ts` by domain with central barrel exports.
- Add Playwright or Vitest smoke coverage for first viewport, chat streaming, model stack, provider accounts, diff/apply, memory, and runtime diagnostics.

Acceptance:

- `App.tsx` becomes orchestration, not the product.
- Major surfaces can change independently.
- Frontend tests and build pass.

## Phase 6: Provider Accounts And Model Routing Productization

Goal:
Make model/provider setup understandable and safe.

Progress added in this phase:

- Added `website/frontend/src/components/provider-accounts/ProviderRouteReadiness.tsx` to explain each provider route across privacy, cost, quota, latency, and fallback before users link credentials or launch CLI delegation.
- Wired `ProviderRouteReadiness` into `ProviderAccountsPanel` so every provider card shows local/cloud boundary, billing expectations, quota source, latency source, and fallback eligibility.
- Added `website/frontend/src/components/provider-accounts/ProviderRouteReadiness.test.tsx` with local-provider and cloud-provider coverage.
- Verified focused provider readiness coverage with `npm test -- ProviderRouteReadiness`: 2 tests passed.
- Verified full frontend tests with `npm test`: 24 test files passed, 193 tests passed.
- Verified production frontend build with `npm run build`.

Work:

- Build provider setup wizards for local endpoints, cloud API keys, official CLI bridges, and source-drop bridges.
- Support Ollama, LM Studio, llama.cpp/OpenAI-compatible endpoints, OpenAI, Anthropic, Gemini, OpenRouter, Perplexity, Codex-style CLI, Claude-style CLI, and Gemini-style CLI where applicable.
- Verify official account/subscription linking before implementing any account-based flow.
- Keep raw secrets out of logs, telemetry, registry notes, transcripts, frontend state, and diagnostics.
- Add one-click provider test prompts with redacted logs.
- Explain privacy, cost, quota, context length, latency, capability, fallback, and failure reason in the model stack UI.

Acceptance:

- A user can connect at least one local model and one cloud/API provider without editing config files.
- Secrets remain redacted end to end.
- Provider routing failures are actionable.

## Phase 7: Agent Safety, Approval, And Tool Event Ledger

Goal:
Make every meaningful action inspectable and reversible where possible.

Progress added in this phase:

- Added structured payload redaction to `website/backend/aegis_ai/diagnostic_redaction.py` via `redact_payload`.
- Updated `EventStore.record_event` in `website/backend/aegis_ai/storage.py` so durable task events redact detail text and nested payload strings before returning or persisting ledger entries.
- Preserved non-secret routing/safety metadata such as `secret_env` while redacting raw key, token, authorization, password, client secret, and private key values.
- Added `test_task_event_ledger_redacts_detail_and_nested_payload_secrets` in `website/backend/tests/test_task_engine.py` to cover provider-call event details, nested headers, callback URLs, diagnostics lists, parser wording, and persisted timeline reads.
- Verified focused safety coverage with `python -m pytest tests/test_task_engine.py tests/test_approval_and_commands.py::ApprovalAndCommandTests::test_command_output_redacts_secret_values_without_hiding_parser_token_context -q`: 7 passed.
- Verified full Website backend suite with `python -m pytest tests -q`: 905 passed, 186 subtests passed.

Work:

- Add a durable tool event ledger for reads, writes, patches, commands, provider calls, validation, browser actions, release/update steps, and extension actions.
- Define approval scopes for file read, file write, patch, command, dependency install, network, Git, browser, provider bridge, plugin, release/update.
- Enforce command policy with cwd constraints, timeouts, output limits, allow/deny patterns, and approval tiers.
- Add checkpoint enforcement before file mutation.
- Add secret and prompt-injection scans for context packets, external text, tool output, attachments, and logs.
- Add audit export for support/debugging.

Acceptance:

- The user can see what Aegis did, why, and what changed.
- Dangerous actions are consistently gated across Website, Desktop, VS Code, and Visual Studio.

## Phase 8: Memory, Autopilot, And Workspace Intelligence

Goal:
Make continuation reliable instead of dependent on chat history.

Progress added in this phase:

- Added `ContinuationHandoff` to the backend continuity schema so `/api/continuity` now returns an explicit active goal, next action, source record, confidence, risk level, blockers, related tasks/files, validation commands, memory references, context records, and a ready-to-use resume prompt.
- Updated `AegisContinuityEngine` to derive the continuation handoff from persisted unified context, prioritizing active tasks, failed tasks, and active workspace recommendations before falling back to recommended focus and memory.
- Preserved validation command handoff from task metadata while avoiding timeline-event task ids being mistaken for commands.
- Updated frontend continuity contract types in `website/frontend/src/types.ts`.
- Expanded `website/backend/tests/test_continuity.py` to verify active-goal selection, related task/file handoff, validation commands, confidence, resume prompt, and API response shape.
- Verified focused continuity coverage with `python -m pytest tests/test_continuity.py -q`: 2 passed.
- Verified full Website backend suite with `python -m pytest tests -q`: 905 passed, 186 subtests passed.
- Verified frontend contract health with `npm run build` and `npm test`: 24 test files passed, 193 tests passed.

Work:

- Store durable task state: objective, assumptions, current step, plan, blockers, artifacts, validation status, completion criteria.
- Add short-term session summaries and active-goal memory.
- Add long-term project memory with source, confidence, scope, TTL, and user edit/delete controls.
- Add hybrid retrieval for code, docs, memory, transcripts, task artifacts, and validation history.
- Add workspace architecture maps, dependency graph summaries, quality risk maps, TODO/roadmap state, and recent failure state.
- Add autopilot repair loops with stop conditions, rollback criteria, and visible state.

Acceptance:

- "Continue with the next phase" chooses the right next task from project state.
- Memory is inspectable and correctable.
- Large context stays relevant and bounded.

## Phase 9: Native Desktop Shell Hardening

Goal:
Keep the desktop client premium while reducing native-shell risk.

Progress added in this phase:

- Hardened native Desktop/Core release compatibility by adding explicit checked/compatible flags, required Core/Desktop versions, blockers, warnings, and recommendations to `DesktopRuntimeStatus`.
- Consolidated desktop client version, release schema, and Core capability advertising in `CoreApiClient` so client registration and `/v1/release/compatibility` use the same capability set.
- Updated the runtime status panel to color compatibility status and show the first blocker, warning, recommendation, and minimum release requirements.
- Added `scripts/test-desktop-contract.ps1` as a fast native source-contract guard for Core compatibility wiring, UI visibility, and CMake/MSBuild Core client inclusion.
- Wired the desktop source-contract guard into `build.ps1` and `scripts/validate-ecosystem.ps1` before native release builds, with `build.ps1` failing immediately if the contract guard fails.
- Verified `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-desktop-contract.ps1`: passed.
- Verified `powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1`: Release x64 build passed with 0 warnings and 0 errors.
- Verified `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\smoke-desktop.ps1 -SkipDashboard -UseIsolatedAppData`: built executable opened and produced a nonblank login capture.

Work:

- Decide whether desktop remains a full ImGui client or becomes a thinner Core/Website host.
- Split `src/AegisChatApp.cpp` into navigation, chat, workspace, model stack, settings, diagnostics, memory, runtime, and rendering modules.
- Split `src/AegisClient.cpp` into typed API clients by backend/Core domain.
- Expand desktop smoke coverage for startup, backend auto-start, Core status, chat, settings, model stack, runtime, changes, memory, blank-window detection, DPI, resize, and crash banner.
- Add desktop/Core/Website version compatibility checks.

Acceptance:

- Desktop release does not depend on manual visual inspection.
- Native UI changes no longer require editing one massive file.

## Phase 10: VS Code And Visual Studio Extension Parity

Goal:
Make editor integrations first-class clients of Core contracts.

Progress added in this phase:

- Added `scripts/test-editor-parity.ps1` as a repo-level editor parity contract covering VS Code and Visual Studio command exposure, Core endpoint coverage, schema compatibility, auth-token forwarding, default Core URL settings, local `.aegis` memory support, validation helpers, rollback safety, and Core-first docs.
- Wired the editor parity contract into `scripts/validate-ecosystem.ps1` as the `editor-parity` gate after VS Code unit/lint checks and before extension smoke/package validation.
- Confirmed both editor clients cover shared Core endpoints for health, release manifest, release compatibility, security status, client sync, workspace scan/intelligence/roadmap, model registry/routing, workflows, change proposal/apply, quality gates, checkpoints, validation, and autopilot start.
- Verified `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-editor-parity.ps1`: passed.
- Verified VS Code extension helpers with `npm run test:unit`: passed.
- Verified VS Code extension lint/package guards with `npm run lint`: passed.
- Verified Visual Studio extension validation guards with `powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -ValidateOnly`: passed.

Work:

- Split VS Code `extension.js` into command modules, webviews, API clients, workspace scanning, proposal store, validation, memory, provider setup, and settings.
- Treat bundled/generated extension output separately from source where possible.
- Confirm Visual Studio parity for scan, chat, propose patch, apply, validate, roadmap, memory, model status, provider setup, approvals, rollback, and Core health.
- Share generated API clients/types from Core or Website contracts.
- Add compile/package/smoke tests for both extensions.

Acceptance:

- Editor clients do not duplicate backend/Core workflow logic.
- Extension packaging and smoke tests are part of the release matrix.

## Phase 11: Release, Update, Installer, And Recovery

Goal:
Make every release repeatable, signed where needed, and reversible.

Progress added in this phase:

- Hardened release and update path boundary checks in `scripts/build-release.ps1` and `scripts/aegis-update.ps1`, so target paths must exactly match the workspace/install root or live under it with a path separator.
- Added `scripts/test-release-contract.ps1` to validate `VERSION.json`, component metadata, compatibility, update policy, checksum expectations, updater rollback/safe-mode/audit behavior, ecosystem validation gates, Core release tests, and release docs.
- Wired the new `release-contract` gate into `scripts/validate-ecosystem.ps1` before native release builds and package/update dry runs.
- Verified the release contract guard, desktop update planner dry run, and Core release infrastructure tests.
- Release packaging is still intentionally gated by dirty release artifacts until the release-folder state is resolved.

Work:

- Resolve dirty release artifact state.
- Make `VERSION.json` the checked release authority.
- Generate checksums and sizes into `release/version-manifest.json`.
- Add package signing where appropriate.
- Add installer/update UX for desktop and local runtime setup.
- Add safe-mode startup and corrupted-state quarantine.
- Add migration smoke tests for `.aegis` state and Website SQLite state.
- Add rollback-path smoke tests for component update failure.
- Generate release notes from component manifests and compatibility gates.

Acceptance:

- A release candidate cannot pass without Core, Website, Desktop, extensions, packaging, update, and rollback evidence.

## Phase 12: Observability, Evals, And Quality Gates

Goal:
Measure whether the system is getting smarter, faster, and safer.

Progress added in this phase:

- Added `evals/phase12-quality-contract.json` as the machine-readable Phase 12 contract for golden workflows, observability signals, performance budgets, and required contract files.
- Added `scripts/test-quality-contract.ps1` to validate the quality/eval contract, Core quality endpoints, Website quality delegation, telemetry surfaces, editor quality-gate parity, benchmark/report expectations, and docs.
- Wired the new `quality-contract` gate into `scripts/validate-ecosystem.ps1`, with evidence written under the active release evidence folder.
- Expanded `docs/QUALITY_GATES.md` with the Phase 12 evidence workflow and initial performance budgets for scan, route, chat, apply, validation, and frontend render paths.
- Generated quality evidence at `.aegis/quality-evidence/20260521-050247/`.
- Verified the quality contract, Core quality gates, golden workflows, storage quality helpers, provider fallback planning, and registry-backed route preview tests.

Work:

- Add golden task evals for chat, coding, review, scaffold, validation repair, model routing, provider fallback, memory, apply/rollback, and extension workflows.
- Add provider/model benchmark harness for local and cloud providers.
- Track reliability, cost, token drift, latency, fallback, route quality, preview resets, and user feedback.
- Add performance budgets for large workspaces, streaming, indexing, graph queries, memory retrieval, plugin scans, and distributed runtime.
- Add security checks for secret leakage, unsafe writes, command policy bypass, prompt injection, and provider log redaction.

Acceptance:

- Provider/model changes can be compared with evidence.
- Regressions are caught before daily users hit them.

## Phase 13: Plugin And Ecosystem Productization

Goal:
Let the system grow without editing core app code for every capability.

Progress added in this phase:

- Added `evals/phase13-plugin-productization-contract.json` as the machine-readable Phase 13 contract for Core plugin runtime rules, reference plugin manifests, lifecycle guards, productization routes, ecosystem package routes, trust levels, update channels, and required contract files.
- Added `scripts/test-plugin-contract.ps1` to validate plugin API compatibility, manifest shape, permission scopes, high-risk approval/trust gates, no-arbitrary-code execution, observability, signing/update metadata, source-drop/local provider metadata, Website productization, ecosystem marketplace/package lifecycle, shared profiles, reproducibility, audit, and docs.
- Wired the new `plugin-contract` gate into `scripts/validate-ecosystem.ps1`, with evidence written under the active release evidence folder.
- Expanded `docs/PLUGIN_ECOSYSTEM.md` with the Phase 13 evidence workflow and lifecycle matrix from discovery through validation, registration, trust, enable, run, observe, disable, update metadata, and uninstall metadata.
- Generated plugin evidence at `.aegis/plugin-evidence/20260521-050847/`.
- Verified Core plugin runtime and ecosystem maturity tests plus Website productization and ecosystem lifecycle tests.
- Uninstall remains a manifest lifecycle hook and future physical-removal workflow; disable is the current reversible safe-removal path.

Work:

- Finalize plugin manifest schema with permissions, version compatibility, signed packages, disable controls, and trust states.
- Add plugin runtime isolation tests.
- Add marketplace/catalog metadata.
- Add workflow package import/export.
- Add shared intelligence profile export/import.
- Add source-drop provider plugin format for future Codex/Claude/Gemini/local runtime updates.

Acceptance:

- Plugins can be audited, disabled, updated, rolled back, and installed safely.

## Phase 14: Alpha Readiness And Dogfooding

Goal:
Make the ecosystem usable daily without babysitting.

Progress added in this phase:

- Added `evals/phase14-alpha-readiness-contract.json` as the machine-readable Phase 14 contract for alpha feature tiers, Core alpha APIs, dogfooding APIs, onboarding requirements, recovery states, scenario-suite entries, evidence files, and required contract files.
- Added `scripts/test-alpha-contract.ps1` to validate alpha docs, Core alpha/dogfooding/onboarding runtime surfaces, Website onboarding fallback recovery parity, focused tests, and ecosystem validation wiring.
- Wired the new `alpha-contract` gate into `scripts/validate-ecosystem.ps1`, with evidence written under the active release evidence folder.
- Expanded `docs/CONTROLLED_EXTERNAL_ALPHA.md`, `docs/REAL_WORLD_DOGFOODING_AND_WORKFLOW_REFINEMENT.md`, and `docs/FIRST_RUN_ONBOARDING.md` with the Phase 14 evidence workflow, alpha scenario suite, and shared recovery ids.
- Added Core and Website fallback recovery coverage for `backend_down`, `core_offline`, `ollama_offline`, `model_unavailable`, `key_missing`, `provider_missing`, `workspace_blocked`, `update_failed`, `validation_failed`, `extension_disconnected`, and `desktop_blank_state`.
- Generated alpha evidence at `.aegis/alpha-evidence/20260521-051628/`.
- Verified the alpha contract, Core alpha/dogfooding/onboarding tests, and Website onboarding delegation/fallback tests.
- Broad external alpha is still blocked until the full scenario suite is run end-to-end against real release artifacts and remaining installer/update/signing limitations are explicit in release notes.

Work:

- Keep a daily dogfooding checklist.
- Generate known issues from telemetry, validation failures, and user feedback.
- Add first-run onboarding for local models, cloud providers, workspace permissions, and recovery.
- Add in-app recovery actions for backend down, Core down, model missing, key missing, workspace blocked, update failed, validation failed, extension disconnected, and desktop blank state.
- Run the alpha scenario suite: create app, modify app, repair validation, review code, connect provider, use local model, run VS Code extension, run Visual Studio extension, update component, roll back component.

Acceptance:

- A fresh user can install, connect at least one model route, open a project, ask for a change, review a diff, apply it, validate it, and recover from common failures.

## Phase 15: External Alpha Release Report

Goal:
Keep external-alpha readiness honest by requiring one go/no-go report that links release artifacts, validation evidence, scenario results, known limitations, and rollback evidence.

Progress added in this phase:

- Added `evals/phase15-external-alpha-release-contract.json` as the machine-readable Phase 15 contract for the external-alpha decision state, hard blockers, report sections, artifact components, validation gates, scenario suite, and required files.
- Added `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md` with the current decision set to `No-go` / `blocked`, plus required evidence sources, release artifact matrix, validation matrix, scenario table, known limitations, rollback/update notes, cross-client parity requirements, and decision log.
- Added `scripts/test-external-alpha-contract.ps1` to validate that the external-alpha report cannot silently imply readiness while package, validation, scenario, parity, rollback, limitation, checksum, or signing evidence is missing.
- Wired the new `external-alpha-contract` gate into `scripts/validate-ecosystem.ps1`, with evidence written under the active release evidence folder.
- Generated external-alpha evidence at `.aegis/external-alpha-evidence/20260521-052243/`.
- Verified the external-alpha contract plus the adjacent release and alpha contracts.

Work:

- Attach a fresh `.aegis/release-evidence/<timestamp>/validation-matrix.json`.
- Generate `release/version-manifest.json` from packaged artifacts with final checksums and sizes.
- Run the full Phase 14 scenario suite against packaged artifacts.
- Record Website, Desktop, VS Code, and Visual Studio parity evidence for the same safe workflow.
- Add release notes that include known limitations, checksum/signing status, update recovery, and rollback instructions.

Acceptance:

- External alpha cannot be marked conditional or ready unless package, validation, scenario, parity, rollback, and limitation evidence are all linked from one report.

## Phase 16: Evidence Ledger And Blocker Index

Goal:
Make the newest evidence and remaining external-alpha blockers discoverable without rereading every evidence folder by hand.

Progress added in this phase:

- Added `evals/phase16-evidence-ledger-contract.json` as the machine-readable Phase 16 contract for evidence roots, ledger sources, required blocker ids, validation gate ids, required files, and ledger outputs.
- Added `docs/EVIDENCE_LEDGER.md` to explain how the ledger indexes release, quality, plugin, alpha, and external-alpha evidence.
- Added `scripts/test-evidence-ledger-contract.ps1` to validate the ledger contract, generate `evidence-ledger.json`, generate `evidence-ledger-summary.md`, and keep the current ledger status blocked until release/package/scenario/parity/rollback evidence exists.
- Wired the new `evidence-ledger-contract` gate into `scripts/validate-ecosystem.ps1`, with evidence written under the active release evidence folder.
- Updated `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md` and `docs/VALIDATION_MATRIX.md` to reference the ledger.
- Generated evidence ledger output at `.aegis/evidence-ledger/20260521-052745/`.
- Verified the evidence ledger contract and reran the external-alpha release report contract.

Initial ledger blockers at Phase 16:

- `release_manifest_missing`
- `release_package_dry_run_not_passed`
- `update_plan_dry_run_not_passed`
- `alpha_scenario_suite_not_attached`
- `cross_client_parity_not_attached`
- `release_notes_limitations_not_attached`

Work:

- Rerun the ledger after every full validation or release packaging attempt.
- Attach the latest ledger summary to the external alpha release report.
- Use the ledger blockers as the short list for the next release-readiness work.

Acceptance:

- A maintainer can find the latest release, quality, plugin, alpha, and external-alpha evidence from one generated summary.
- The ledger keeps external-alpha status blocked while release manifest, package dry run, update dry run, scenario, parity, and release-note evidence are missing.

## Phase 17: Release Artifact Preflight

Goal:
Make release packaging blockers visible before any script mutates `release/`, `.tmp`, or extension package folders.

Progress added in this phase:

- Added `evals/phase17-release-artifact-preflight-contract.json` to lock the package-readiness checks, current blocked status, required blockers, required files, and evidence outputs.
- Added `scripts/test-release-artifact-preflight.ps1` as a non-mutating preflight that reads `VERSION.json`, stage inputs, expected VSIX candidates, latest release evidence, `release/version-manifest.json`, and release artifact Git status.
- Added `docs/RELEASE_ARTIFACT_PREFLIGHT.md` and expanded release packaging, validation matrix, evidence ledger, and external-alpha docs to reference the preflight.
- Wired `release-artifact-preflight` into `scripts/validate-ecosystem.ps1` immediately after the release contract gate.
- Expanded the evidence ledger and external-alpha contracts so the preflight is part of the release decision path.
- Generated release preflight evidence at `.aegis/release-preflight/20260521-053834/`.
- Refreshed the evidence ledger at `.aegis/evidence-ledger/20260521-053844/`.

Initial preflight findings before Phase 18:

- Core, Website, and Desktop package stage inputs are present.
- `vscode_vsix_missing`: `aegis-local-autopilot-0.1.8.vsix` is not present in either expected VS Code location.
- `visual_studio_vsix_missing`: `AegisLocalAgentVs.vsix` is not present in the Visual Studio release folder.
- `release_manifest_missing`: `release/version-manifest.json` has not been generated.
- `dirty_release_artifacts_need_decision`: deleted extension release docs plus untracked release/version scripts still need an intentional keep/delete/restore decision.
- `release_package_dry_run_not_passed` and `update_plan_dry_run_not_passed`: latest release evidence still shows both gates skipped.

Work:

- Decide and document the release-folder Git state.
- Build or place the VS Code and Visual Studio VSIX artifacts where `VERSION.json` expects them.
- Rerun `scripts\validate-ecosystem.ps1 -IncludeReleasePackaging` only after package inputs and release-folder state are intentional.
- Rerun the preflight and ledger after package generation creates `release/version-manifest.json`.

Acceptance:

- Package generation only proceeds after the preflight shows package inputs, dirty-state decisions, VSIX candidates, release manifest, and dry-run evidence are ready or explicitly accepted for a narrow release.

## Phase 18: Extension Package Candidate Staging

Goal:
Clear the missing VSIX blockers and make extension package candidates evidence-backed before the ecosystem release package dry run.

Progress added in this phase:

- Ran the VS Code package path from `vscode-plugins\aegis-local-autopilot`: `npm run package`.
- Generated `vscode-plugins\aegis-local-autopilot\release\aegis-local-autopilot-0.1.8.vsix`.
- Ran the Visual Studio validation guard and full package build.
- Generated `visual-studio-extensions\aegis-local-agent-vs\release\AegisLocalAgentVs.vsix`.
- Recreated current VS Code release-facing docs under `vscode-plugins\aegis-local-autopilot\release\`.
- Added `evals/phase18-extension-package-candidates-contract.json`.
- Added `docs/EXTENSION_PACKAGE_CANDIDATES.md`.
- Added `scripts/test-extension-package-candidates.ps1`, which verifies both VSIX artifacts, minimum sizes, release docs, validation commands, and ecosystem validation wiring.
- Wired `extension-package-candidates` into `scripts/validate-ecosystem.ps1`.
- Updated the external-alpha and evidence-ledger contracts so extension package candidates are part of the release decision path.
- Generated candidate evidence at `.aegis/extension-package-candidates/20260521-054609/`.
- Refreshed preflight evidence at `.aegis/release-preflight/20260521-054609/`.
- Refreshed ledger evidence at `.aegis/evidence-ledger/20260521-054623/`.

Current package candidate status:

- `vscode-extension`: ready; `aegis-local-autopilot-0.1.8.vsix` exists and release docs are present.
- `visual-studio-extension`: ready; `AegisLocalAgentVs.vsix` exists and release docs are present.
- The old `vscode_vsix_missing` and `visual_studio_vsix_missing` blockers are cleared.

Remaining release blockers:

- packaged alpha scenario suite evidence is not attached
- cross-client parity evidence is not attached
- final release notes/limitations evidence is not attached

Work:

- Keep extension package candidate evidence attached to the release report.
- Attach packaged alpha scenario and cross-client parity evidence.

Acceptance:

- Both extension package candidates are present, documented, and independently checkable from one evidence folder before ecosystem packaging proceeds.

## Phase 19: Release Package Dry-Run Manifest Evidence

Goal:
Prove package generation and update planning from a generated manifest without promoting the root `release/` folder yet.

Progress added in this phase:

- Added `evals/phase19-release-package-dry-run-contract.json`.
- Added `docs/RELEASE_PACKAGE_DRY_RUN.md`.
- Added `scripts/test-release-package-dry-run.ps1`.
- Wired `release-package-dry-run-contract` into `scripts/validate-ecosystem.ps1`.
- Updated release preflight and evidence ledger logic so ready Phase 19 evidence clears `release_package_dry_run_not_passed` and `update_plan_dry_run_not_passed`.
- Generated package dry-run evidence at `.aegis/release-package-dry-run/20260521-055934/`, then refreshed it after Phase 21 update/release documentation changes at `.aegis/release-package-dry-run/20260521-062833/`.
- Refreshed preflight evidence at `.aegis/release-preflight/20260521-062909/`.
- Refreshed ledger evidence at `.aegis/evidence-ledger/20260521-062938/`.

Current dry-run status:

- Package dry run: ready.
- Update-plan dry runs: ready for `aegis-core`, `website`, `desktop`, `vscode-extension`, and `visual-studio-extension`.
- Dry-run manifest: `.aegis/release-package-dry-run/20260521-062833/release/version-manifest.json`.
- Root release manifest: now generated by Phase 20.

Remaining release blockers:

- packaged alpha scenario suite evidence is not attached
- cross-client parity evidence is not attached
- final release notes/limitations evidence is not attached

Work:

- Attach packaged alpha scenario and cross-client parity evidence to the external-alpha report.

Acceptance:

- Package and update-plan dry runs are repeatable from one `.aegis/` evidence folder; final manifest promotion is now handled by Phase 20.

## Phase 20: Final Release Manifest And Artifact Decision

Goal:
Promote the intended package set into the root `release/` folder, document the dirty artifact decision, and clear the remaining release-manifest preflight blockers.

Progress added in this phase:

- Added `evals/phase20-final-release-manifest-contract.json`.
- Added `docs/RELEASE_ARTIFACT_DECISION.md`.
- Added `scripts/test-final-release-manifest.ps1`.
- Wired `final-release-manifest-contract` into `scripts/validate-ecosystem.ps1` as an opt-in release-packaging gate.
- Updated `evals/phase17-release-artifact-preflight-contract.json`, `scripts/test-release-artifact-preflight.ps1`, and `docs/RELEASE_ARTIFACT_PREFLIGHT.md` so Phase 20 evidence clears `release_manifest_missing` and `dirty_release_artifacts_need_decision`.
- Updated `evals/phase16-evidence-ledger-contract.json`, `scripts/test-evidence-ledger-contract.ps1`, and `docs/EVIDENCE_LEDGER.md` so final manifest evidence is a ledger source.
- Updated the external-alpha report/contract, validation matrix, release packaging docs, and known unstable surfaces to reflect the new manifest state.
- Refreshed package dry-run evidence at `.aegis/release-package-dry-run/20260521-062833/`.
- Generated final root manifest evidence at `.aegis/final-release-manifest/20260521-062851/`.
- Refreshed ready preflight evidence at `.aegis/release-preflight/20260521-062909/`.
- Refreshed blocked ledger evidence at `.aegis/evidence-ledger/20260521-062938/`.

Current status:

- Root `release/version-manifest.json`: generated.
- Root packages: present for Core, Website, Desktop, VS Code, and Visual Studio.
- Package hashes/sizes: stamped and verified.
- Update planner dry-runs: ready for all five components against the root manifest.
- Release preflight: ready with zero blockers.
- Evidence ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Next work:

- Attach cross-client parity evidence.
- Write final release notes with known limitations, checksum status, and unsigned-build status.

Acceptance:

- Final release manifest promotion is repeatable, evidence-backed, and no longer confused with unresolved Git dirtiness.

## Phase 21: Release Apply, Rollback, And Recovery Evidence

Goal:
Prove the shipped updater can apply, fail safely, and roll back packaged release artifacts without mutating the developer workspace.

Progress added in this phase:

- Fixed `scripts/aegis-update.ps1` rollback fidelity so backups capture target contents directly and rollback clears the target before restoring backup contents.
- Added `evals/phase21-release-apply-rollback-contract.json`.
- Added `docs/RELEASE_APPLY_ROLLBACK_EVIDENCE.md`.
- Added `scripts/test-release-apply-rollback.ps1`.
- Wired `release-apply-rollback-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger, external-alpha contract/report, validation matrix, release packaging docs, and known unstable surfaces so rollback/apply evidence is now a first-class source.
- Generated Phase 21 evidence at `.aegis/release-apply-rollback/20260521-062914/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-062933/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-062938/`.

Current status:

- Update plans, applies, and rollbacks pass for `aegis-core`, `website`, `desktop`, `vscode-extension`, and `visual-studio-extension`.
- Rollback restores marker files and removes simulated stray files for every component.
- Corrupt desktop package apply fails checksum validation, records `state=failed`, sets safe mode, and writes the security audit event.
- Evidence ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Acceptance:

- Packaged apply/rollback trust is evidence-backed and no longer a blocker for the next external-alpha readiness phase.

## Phase 22: Packaged Alpha Scenario Evidence

Goal:
Attach evidence for the ten Phase 14/15 alpha scenarios against the generated release packages, without pretending this replaces cross-client parity.

Progress added in this phase:

- Added `evals/phase22-packaged-alpha-scenarios-contract.json`.
- Added `docs/PACKAGED_ALPHA_SCENARIO_EVIDENCE.md`.
- Added `scripts/test-packaged-alpha-scenarios.ps1`.
- Wired `packaged-alpha-scenarios-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the external-alpha contract/report, evidence ledger contract/docs, validation matrix, and known unstable surfaces so packaged scenario evidence is now a first-class source.
- Generated ready Phase 22 evidence at `.aegis/packaged-alpha-scenarios/20260521-064232/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-064237/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-064242/`.

Current status:

- All ten alpha scenarios have package-backed evidence: create app, modify app, repair validation, review code, connect provider, use local model, VS Code extension, Visual Studio extension, update component, and rollback component.
- All five release packages are present and match the root manifest hashes.
- Packaged text files outside test fixtures have no obvious plaintext secret markers.
- Evidence ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Acceptance:

- Packaged alpha scenario evidence is attached and the scenario-suite blocker is cleared.

## Phase 23: Cross-Client Parity Evidence

Goal:
Prove Website, native Desktop, VS Code, and Visual Studio all expose the same safe alpha workflow from source-backed and package-aware evidence.

Progress added in this phase:

- Added `evals/phase23-cross-client-parity-contract.json`.
- Added `docs/CROSS_CLIENT_PARITY_EVIDENCE.md`.
- Added `scripts/test-cross-client-parity.ps1`.
- Wired `cross-client-parity-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the external-alpha contract/report, evidence ledger contract/docs, validation matrix, and known unstable surfaces so parity is now a first-class evidence source.
- Generated ready Phase 23 evidence at `.aegis/cross-client-parity/20260521-065519/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-065525/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-065534/`.

Current status:

- Website, Desktop, VS Code, and Visual Studio all show source-backed support for workspace scan, model route, proposal/review, approved apply, validation, checkpoint, rollback/restore, diagnostics visibility/export, and release compatibility.
- All five release packages are present and match the root manifest hashes.
- Phase 20 final manifest, Phase 21 apply/rollback, and Phase 22 packaged scenario evidence are attached.
- Evidence ledger blockers are now only `release_notes_limitations_not_attached`.

Acceptance:

- Cross-client parity evidence is attached and the parity blocker is cleared.

## Phase 24: Final Release Notes And Limitations Evidence

Goal:
Clear the final release-note blocker by publishing tester-facing release notes with known limitations, checksum/signing status, update recovery, rollback instructions, and links to package evidence.

Progress added in this phase:

- Added `evals/phase24-release-notes-limitations-contract.json`.
- Added `docs/RELEASE_NOTES_LIMITATIONS_EVIDENCE.md`.
- Added `docs/EXTERNAL_ALPHA_RELEASE_NOTES.md`, `docs/WEBSITE_RELEASE_NOTES.md`, and `docs/DESKTOP_RELEASE_NOTES.md`.
- Updated VS Code and Visual Studio release notes with checksum, unsigned-build, evidence, limitation, and rollback details.
- Added `scripts/test-release-notes-limitations.ps1`.
- Wired `release-notes-limitations-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the external-alpha contract/report, evidence ledger contract/docs, validation matrix, and known unstable surfaces so final release notes are a first-class evidence source.
- Generated ready Phase 24 evidence at `.aegis/release-notes-limitations/20260521-071150/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-071239/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-071243/`.

Current status:

- The `release_notes_limitations_not_attached` blocker is cleared.
- The external-alpha decision is now conditional private external alpha.
- The evidence ledger has zero runtime blockers and remains `attention` because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- Final release notes and limitations evidence are attached, and the release-note blocker is cleared.

## Phase 25: Core Website Ownership Completion

Goal:
Finish moving shared runtime truth behind Aegis Core while keeping Website as the browser compatibility gateway.

Progress added in this phase:

- Added `evals/phase25-core-website-ownership-contract.json`.
- Added `docs/CORE_WEBSITE_OWNERSHIP_EVIDENCE.md`.
- Added `scripts/test-core-website-ownership.ps1`.
- Added typed frontend ownership support through `RuntimeOwnershipResponse` and `getRuntimeOwnership`.
- Moved `/api/routing/preview` to Core-first model routing while preserving `RoutePreviewResponse` compatibility and Website fallback.
- Wired `core-website-ownership-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 25 ownership evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 25 evidence at `.aegis/core-website-ownership/20260521-072811/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-072820/`.

Current status:

- Ownership source: `website/backend/aegis_ai/runtime_ownership.py`.
- Runtime endpoint: `GET /api/runtime/ownership`.
- Core-owned domains are contract-checked for apply, checkpoints, validation, model routing, and agent runtime.
- Website-owned provider-account setup remains explicit.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- Core/Website ownership evidence is attached and the ownership boundary is contract-locked for future full validation runs.

## Phase 26: Backend Modularization

Goal:
Reduce backend review risk by moving route-preview mapping behavior out of the large FastAPI orchestrator.

Progress added in this phase:

- Extracted Core route-preview request and response mapping into `website/backend/aegis_ai/services/route_preview_service.py`.
- Kept `website/backend/aegis_ai/main.py` responsible for orchestration while the new service owns context-file, profile-id, private-context, and Core-candidate mapping details.
- Added `website/backend/tests/test_route_preview_service.py`.
- Added `evals/phase26-backend-modularization-contract.json`.
- Added `docs/BACKEND_MODULARIZATION_EVIDENCE.md`.
- Added `scripts/test-backend-modularization.ps1`.
- Wired `backend-modularization-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 26 backend modularization evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 26 evidence at `.aegis/backend-modularization/20260521-073847/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-073928/`.

Current status:

- Route-preview backend behavior is isolated behind a focused service and test file.
- The backend modularization gate runs `python -m pytest tests/test_route_preview_service.py tests/test_runtime_ownership.py -q`.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- The first backend modularization slice is extracted, contract-checked, documented, and attached as evidence.

## Phase 27: Web Frontend Extraction

Goal:
Reduce React shell risk by moving agent bridge provider selection logic out of the large app component.

Progress added in this phase:

- Extracted provider/runtime helper logic into `website/frontend/src/utils/agentBridgeProviders.ts`.
- Kept `website/frontend/src/App.tsx` responsible for state orchestration while the new utility owns external/local provider classification, model-family matching, runtime labels, and local runtime target selection.
- Added `website/frontend/src/utils/agentBridgeProviders.test.ts`.
- Added `evals/phase27-frontend-extraction-contract.json`.
- Added `docs/FRONTEND_EXTRACTION_EVIDENCE.md`.
- Added `scripts/test-frontend-extraction.ps1`.
- Wired `frontend-extraction-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 27 frontend extraction evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 27 evidence at `.aegis/frontend-extraction/20260521-074842/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-074857/`.

Current status:

- Agent bridge routing decisions are now covered by focused Vitest tests.
- The frontend extraction gate runs `npm test -- src/utils/agentBridgeProviders.test.ts` and `npm run build`.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- The first frontend extraction slice is extracted, contract-checked, documented, and attached as evidence.

## Phase 28: Native Desktop Shell Hardening

Goal:
Reduce native shell risk by moving Runtime Status release-compatibility presentation rules out of the large ImGui app component.

Progress added in this phase:

- Extracted Runtime Status presentation logic into `src/desktop/RuntimeStatusPresenter.cpp` and `src/desktop/RuntimeStatusPresenter.h`.
- Kept `src/AegisChatApp.cpp` responsible for ImGui rendering while the new presenter owns service labels, service tones, Core release-compatibility tone, requirement text, and blocker/warning/note text.
- Wired the presenter into `CMakeLists.txt`, `AegisChatBotDesktop.vcxproj`, and `AegisChatBotDesktop.vcxproj.filters`.
- Updated `scripts/test-desktop-contract.ps1` so the existing desktop source contract checks the extracted presenter.
- Added `evals/phase28-native-desktop-shell-contract.json`.
- Added `docs/NATIVE_DESKTOP_SHELL_EVIDENCE.md`.
- Added `scripts/test-native-desktop-shell.ps1`.
- Wired `desktop-shell-hardening-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 28 native desktop shell evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 28 evidence at `.aegis/desktop-shell-hardening/20260521-075813/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-075820/`.

Current status:

- Runtime Status release compatibility presentation is isolated from the large native shell file.
- The desktop shell gate runs `scripts\test-desktop-contract.ps1` and `build.ps1`.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- The first native desktop shell hardening slice is extracted, contract-checked, compiled, documented, and attached as evidence.

## Phase 29: Editor Extension Modularization And Smoke

Goal:
Reduce editor-client risk by moving Core contract helpers out of the VS Code activation file and recording non-interactive Visual Studio validation parity.

Progress added in this phase:

- Rewired `vscode-plugins/aegis-local-autopilot/extension.js` so Core envelope validation, data extraction, `ok=false` handling, and contract formatting delegate to `src/core/coreEnvelope.ts`.
- Removed the duplicate Core envelope helper implementations from `extension.js` while keeping the activation file responsible for VS Code orchestration.
- Extended `vscode-plugins/aegis-local-autopilot/scripts/test-extension-helpers.js` to cover `requireCoreOk`, `formatCoreContract`, contract-version formatting, and redacted Core errors.
- Updated `vscode-plugins/aegis-local-autopilot/scripts/lint-package.js` so package lint fails if `extension.js` reintroduces duplicate Core envelope helpers.
- Added `evals/phase29-editor-extension-modularization-contract.json`.
- Added `docs/EDITOR_EXTENSION_MODULARIZATION_EVIDENCE.md`.
- Added `scripts/test-editor-extension-modularization.ps1`.
- Wired `editor-extension-modularization-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 29 editor extension modularization evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 29 evidence at `.aegis/editor-extension-modularization/20260521-081105/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-081112/`.

Current status:

- VS Code Core envelope behavior is now covered by a shared helper module, focused helper tests, and lint guards.
- The editor extension modularization gate runs `npm run test:unit`, `npm run lint`, and the Visual Studio `build.ps1 -ValidateOnly` package-validation substitute.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- The first editor extension modularization slice is extracted, contract-checked, documented, and attached as evidence.

## Phase 30: Provider Route Safety And Secret Redaction

Make provider setup understandable and secret-safe before broader tester use.

Progress added in this phase:

- Added `ProviderRouteSafety` to backend provider account snapshots so every provider route reports route type, privacy boundary, secret-storage boundary, cloud-context consent, workspace-context behavior, cost, quota, latency, fallback policy, diagnostics safety, and user action state.
- Populated route-safety summaries for local endpoints, API-key routes, official CLI delegation, environment-profile routes, OAuth-pending routes, and unsupported routes.
- Redacted provider account, session, CLI bridge, readiness, and route-safety error text before manager snapshots leave the backend.
- Extended backend provider account tests for OS credential-store API-key routing, local no-secret routing, CLI no-token-import routing, and secret-like readiness error redaction.
- Extended frontend provider route-readiness types/cards to consume backend safety boundaries and redact secret-like card text before rendering.
- Added `evals/phase30-provider-secret-safety-contract.json`.
- Added `docs/PROVIDER_SECRET_SAFETY_EVIDENCE.md`.
- Added `scripts/test-provider-secret-safety.ps1`.
- Wired `provider-secret-safety-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 30 provider secret safety evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 30 evidence at `.aegis/provider-secret-safety/20260521-082837/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-082848/`.

Current status:

- Provider status payloads now expose machine-readable safety boundaries for privacy, consent, secrets, cost, quota, latency, and fallback.
- The Phase 30 gate runs `python -m pytest tests/test_provider_accounts.py -q` and `npm test -- ProviderRouteReadiness`.
- Ledger status remains `attention` because full release validation still has skipped live smoke gates.

Acceptance:

- The first provider route-safety and secret-redaction slice is contract-checked, documented, and attached as evidence.

## Phase 31: Memory, Privacy, And Governance Controls

Make durable memory inspectable, exportable, and governable before broader tester use.

Progress added in this phase:

- Added Core-delegated Website backend support for memory governance, export, and controls with a safe legacy local-memory fallback.
- Added `GET /api/memory/governance`, `POST /api/memory/export`, and `POST /api/memory/controls`.
- Extended memory note responses with governance, privacy, control, delegation, and runtime metadata.
- Added local-only fallback governance, storage-boundary reporting, and secret-like redaction for legacy memory exports.
- Extended frontend memory API types and helpers for governance, export, and control updates.
- Extended backend Core delegation tests for delegated governance/export/control behavior and offline legacy fallback redaction.
- Extended frontend API tests for the new memory governance/export/control endpoints.
- Added `evals/phase31-memory-governance-contract.json`.
- Added `docs/MEMORY_GOVERNANCE_EVIDENCE.md`.
- Added `scripts/test-memory-governance.ps1`.
- Wired `memory-governance-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 31 memory governance evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 31 evidence at `.aegis/memory-governance/20260521-084434/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-084545/`.

Current status:

- Memory governance now reports mode, storage boundary, category controls, audit availability, export/delete support, sensitive-export defaults, and cloud-context consent requirements.
- Legacy memory fallback remains local-only and redacts secret-like values from exports.
- The Phase 31 gate runs `python -m pytest tests/test_core_runtime_delegation.py -q` and `npm test -- api.test.ts`.
- Ledger status remains `attention` because full release validation still has skipped live smoke gates.

Acceptance:

- The first memory governance/export/control slice is contract-checked, documented, and attached as evidence.

## Phase 32: Plugin Ecosystem Productization

Make plugin and ecosystem package lifecycle actions reversible, auditable, and checksum-checked before broader tester use.

Progress added in this phase:

- Added productization plugin lifecycle request/response schemas for update, rollback, and safe-uninstall actions.
- Added ecosystem package lifecycle request/response schemas for update, rollback, and safe-uninstall actions.
- Added checksum fields to productization plugin manifests and checksum mismatch validation to productization and ecosystem package manifests.
- Added productization plugin lifecycle routes: `POST /api/productization/plugins/{plugin_id}/update`, `/rollback`, and `/uninstall`.
- Added ecosystem package lifecycle routes: `POST /api/ecosystem/packages/{package_id}/update`, `/rollback`, and `/uninstall`.
- Stored previous manifests before updates and safe-uninstalls so rollback can restore the prior manifest.
- Preserved the no-arbitrary-code plugin boundary: uninstall is reversible `safe_disable`, not physical deletion.
- Added worker/ecosystem audit events for plugin/package update, rollback, and uninstall actions.
- Extended productization and ecosystem backend tests for checksum rejection, update, rollback, safe-uninstall, metadata, and audit visibility.
- Added `evals/phase32-plugin-lifecycle-contract.json`.
- Added `docs/PLUGIN_LIFECYCLE_EVIDENCE.md`.
- Added `scripts/test-plugin-lifecycle.ps1`.
- Updated `docs/PLUGIN_ECOSYSTEM.md`, validation matrix docs, ecosystem validation, and the evidence ledger for Phase 32.
- Generated ready Phase 32 evidence at `.aegis/plugin-lifecycle/20260521-090234/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-090245/`.

Current status:

- Plugin/package lifecycle update, rollback, and safe-uninstall flows are route-backed, tested, audited, and ledger-attached.
- The Phase 32 gate runs `python -m pytest tests/test_productization.py -q` and `python -m pytest tests/test_ecosystem.py -q`.
- Ledger status remains `attention` because full release validation still has skipped live smoke gates.

Acceptance:

- The first plugin/package lifecycle productization slice is contract-checked, documented, and attached as evidence.

## Phase 33: Observability, Evals, And CI

Make quality reproducible before broader tester use.

Progress added in this phase:

- Added `.github/workflows/aegis-validation.yml` with Windows jobs for Core tests, Website backend tests, Website frontend tests/build, desktop contract/build, VS Code unit/lint guards, Visual Studio validation guards, release/evidence contracts, and a manual full ecosystem matrix.
- Added `evals/phase33-observability-ci-contract.json`.
- Added `docs/OBSERVABILITY_EVALS_CI_EVIDENCE.md`.
- Added `scripts/test-observability-ci.ps1`.
- Wired `observability-ci-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 33 observability CI evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 33 evidence at `.aegis/observability-ci/20260521-091230/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-091239/`.

Current status:

- CI now has a checked-in workflow covering the main local validation families.
- The Phase 33 gate runs the existing Phase 12 quality contract and the backend golden workflow tests.
- Ledger status remains `attention` because full release validation still has skipped live smoke gates.

Acceptance:

- The first observability/evals/CI slice is contract-checked, documented, and attached as evidence.

## Phase 34: Distribution, Installer, Signing, And Auto-Update

Make the current package path auditable before broader tester use.

Progress added in this phase:

- Added `docs/DISTRIBUTION_INSTALLER_UPDATE_EVIDENCE.md`.
- Added `evals/phase34-distribution-update-contract.json`.
- Added `scripts/test-distribution-update.ps1`.
- Updated `docs/RELEASE_PACKAGING_AND_UPDATES.md` with the private-alpha distribution decision: portable ZIP packages for Core/Website/Desktop, VSIX packages for VS Code and Visual Studio, unsigned local-build disclosure, required checksums, and signed installer deferral until broad release.
- Verified `VERSION.json` and `release/version-manifest.json` package metadata, component versions, artifact paths, sizes, SHA-256 values, and update policy.
- Verified source and shipped updater coverage for checksum validation, signature policy, backup, rollback, safe mode, security audit state, downgrade protection, and `.aegis\updates`.
- Verified local-only redacted Core diagnostics export through `/v1/alpha/diagnostics/export`.
- Ran non-mutating update plans for `aegis-core`, `website`, `desktop`, `vscode-extension`, and `visual-studio-extension`; all returned `planned` with checksums required.
- Wired `distribution-update-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 34 distribution/update evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 34 evidence at `.aegis/distribution-update/20260521-092140/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-092406/`.

Current status:

- The current private-alpha portable ZIP and VSIX distribution path is contract-checked and ledger-attached.
- Signed installer readiness remains deferred until installer technology and code signing are selected.
- Ledger status remains `attention` because the latest full release validation matrix still has skipped live smoke gates.

Acceptance:

- The first distribution/update slice is documented, checksum-backed, dry-run planned, and attached as evidence.

## Phase 35: Alpha Readiness Polish

Make the first external build feel intentional instead of merely assembled.

Progress added in this phase:

- Added `alpha_handoff_summary()` to `aegis-core/aegis_core/alpha.py` and included it in the existing Core alpha readiness payload.
- Added Stable Alpha, Beta, Experimental, and Internal Only labels with default visibility rules.
- Added a default alpha path for checksum verification, local Core launch, workspace selection, provider setup, local model setup, validate-only first workflow, checkpoint/rollback confirmation, diagnostics export, and feedback capture.
- Added `evals/phase35-alpha-readiness-polish-contract.json`.
- Added `docs/ALPHA_READINESS_POLISH_EVIDENCE.md`.
- Added `scripts/test-alpha-readiness-polish.ps1`.
- Updated controlled alpha docs, first-run onboarding, external alpha release notes, known unstable surfaces, validation matrix, and evidence ledger docs.
- Extended Core alpha readiness tests for the Phase 35 handoff summary.
- Wired `alpha-readiness-polish-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 35 alpha readiness polish evidence to the evidence ledger contract and script.
- Generated ready Phase 35 evidence at `.aegis/alpha-readiness-polish/20260521-093558/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-093610/`.

Current status:

- The private-alpha tester handoff is contract-checked and ledger-attached.
- Experimental and Internal Only surfaces are out of the default path.
- Ledger status remains `attention` because full release validation still has skipped live smoke gates.

Acceptance:

- The first alpha readiness polish slice is documented, tested, and attached as evidence.

## Phase 36: Live Smoke Closure And Release Candidate Scoping

Make skipped live smoke and release package gates explicit before calling anything a release candidate.

Progress added in this phase:

- Added `evals/phase36-live-smoke-rc-contract.json`.
- Added `docs/LIVE_SMOKE_RC_SCOPING_EVIDENCE.md`.
- Added `scripts/test-live-smoke-rc.ps1`.
- Wired `live-smoke-rc-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 36 live smoke RC scoping to validation matrix docs, external alpha release notes, external alpha report, known unstable surfaces, evidence ledger docs, and the evidence ledger contract/script.
- The Phase 36 evidence separates contract `status` from `release_candidate_status`, so the evidence can be ready while the candidate remains `attention`.
- The live gate closure inventory tracks `desktop-smoke`, `vscode-smoke`, `visual-studio-package`, `release-package-dry-run`, and `update-plan-dry-run`.
- Release candidate scope now keeps `intentional_release_artifact_decision`, `worktree_scope_required`, `github_target_pending`, and `broad_alpha_blocked` visible.
- Generated fresh release validation evidence at `.aegis/release-evidence/20260521-095247/`.
- Generated ready Phase 36 evidence at `.aegis/live-smoke-rc/20260521-095750/`.
- Refreshed evidence ledger output at `.aegis/evidence-ledger/20260521-095800/`.

Current status:

- Phase 36 can now be refreshed as standalone evidence under `.aegis/live-smoke-rc/<timestamp>/`.
- Broad alpha remains blocked until the live smoke/package gates close in fresh validation evidence.
- GitHub publishing still requires scoped commits and target confirmation.

Acceptance:

- The first release-candidate scoping slice is contract-checked, documented, and attached as evidence.

## Phase 37: Commit Scoping And GitHub Handoff

Turn the large dirty worktree into reviewable publish units.

Progress added in this phase:

- Added `evals/phase37-commit-scoping-github-handoff-contract.json`.
- Added `docs/COMMIT_SCOPING_GITHUB_HANDOFF_EVIDENCE.md`.
- Added `scripts/test-commit-scoping-github-handoff.ps1`.
- Wired `commit-scoping-github-handoff-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 37 commit scoping to validation matrix docs, evidence ledger docs, evidence ledger contract/script, external alpha release notes, external alpha report, and known unstable surfaces.
- Added commit groups, publish blockers, deleted asset decision tracking, GitHub target detection, no blind stage policy, and release artifact separation.
- Kept handoff status at `attention` until target confirmation, deleted asset decision, and scoped commits are resolved.
- Refreshed evidence at `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`, `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`, and `.aegis/release-evidence/20260521-110934/validation-summary.md`.

Done when:

- Done for the first publish handoff slice.
- Future closure still needs scoped staging and user confirmation before push.

## Completed Phase 38: Desktop Smoke And Package Gate Execution

Convert skipped runtime/package gates into concrete evidence.

Progress:

- Added `evals/phase38-desktop-smoke-package-gates-contract.json`.
- Added `docs/DESKTOP_SMOKE_PACKAGE_GATES_EVIDENCE.md`.
- Added `scripts/test-desktop-smoke-package-gates.ps1`.
- Wired `desktop-smoke-package-gates-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 38 to validation matrix docs, external alpha release notes/report, known unstable surfaces, evidence ledger docs, and evidence ledger contract/script.
- Ran isolated desktop runtime smoke and attached screenshot/log evidence in `.aegis/desktop-smoke-package-gates/20260521-111533/`.
- Ran `scripts\validate-ecosystem.ps1 -SkipSmoke -IncludeDesktopSmoke`; desktop smoke passed, 0 hard failures, 0 retryable failures, and 4 intentional editor/package skips remained.
- Fixed the Core runtime state save race on Windows by using unique temp files and retrying replace on `PermissionError`.
- Refreshed Phase 36, Phase 37, Phase 38, and evidence ledger outputs.

Done when:

- Done for the first desktop smoke/package gate execution slice.
- Remaining closure work: VS Code extension-host smoke, Visual Studio package, release-package dry run, and final release manifest mutation decisions.

## Completed Phase 39: Editor Smoke And Release Package Decision Execution

Close the next skipped editor/package gate with explicit evidence.

Progress:

- Added `evals/phase39-editor-smoke-release-package-decision-contract.json`.
- Added `docs/EDITOR_SMOKE_RELEASE_PACKAGE_DECISION_EVIDENCE.md`.
- Added `scripts/test-editor-smoke-release-package-decision.ps1`.
- Wired `editor-smoke-release-package-decision-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 39 to validation matrix docs, external alpha notes/report, known unstable surfaces, and evidence ledger docs/contract/script.
- Fixed native stderr handling in validation wrappers so VS Code test progress output does not become a false terminating exception.
- Ran VS Code extension-host smoke; it is `retryable` because the VS Code test instance still holds the `vscode-updating` mutex.
- Refreshed release validation and downstream Phase 36/37/38/39/ledger evidence.

Done when:

- Done for the first editor smoke/release package decision slice.
- Remaining closure work: rerun VS Code smoke after the mutex clears, then close Visual Studio and release package mutation gates.

## Phase 40: Package Mutation Decision And Artifact Gate Execution

Close the next package mutation gate with explicit owner scope.

Planned work:

- Confirm whether Visual Studio extension release artifacts, root release artifacts, or both may be mutated in this checkout.
- Run `visual-studio-package`, `release-package-dry-run`, or `final-release-manifest-contract` only under the explicit mutation scope.
- Rerun VS Code extension-host smoke after the `vscode-updating` mutex clears.
- Refresh Phase 36, Phase 37, Phase 38, Phase 39, and ledger evidence after the next gate status changes.

Done when:

- At least one package mutation gate is converted to passed, retryable, or owner-blocked evidence with mutation scope recorded.

## Recommended Next Implementation Pass

1. Confirm the GitHub target before any push.
2. Decide whether `website inspiration.png` should stay deleted or be restored.
3. Freeze and group future commits into explicit commit sets.
4. Start Phase 40 by deciding Visual Studio/root release package mutation scope.
5. Rerun VS Code extension-host smoke after the `vscode-updating` mutex clears.
6. Run Visual Studio package/experimental-instance smoke or release-package dry run with that decision attached.
7. Refresh Phase 36, Phase 37, Phase 38, Phase 39, and ledger evidence after the next gate closes.
8. Continue backend modularization with `website/backend/aegis_ai/agent.py`, `storage.py`, and `schemas.py`.
9. Continue editor extension extraction with VS Code command registration, workspace scan, proposal/apply, validation, and webview rendering modules.
10. Continue frontend extraction after the smoke/package gate status is updated.

## Definition Of Done For Future Phases

A phase is complete only when:

- The owning layer is clear.
- Existing tests pass.
- New or moved behavior has focused tests.
- Contracts and docs are updated.
- Security/privacy impact is checked.
- Release/compatibility impact is known.
- Evidence is written to a stable folder.
- The next phase can continue without rediscovering project context.
