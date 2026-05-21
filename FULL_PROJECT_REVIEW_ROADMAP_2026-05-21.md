# Full Project Review And Remaining Roadmap

Generated: 2026-05-21

Project root: `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot`

Related phase log: `CHATBOT_PROJECT_REVIEW_ROADMAP_2026-05-21.md`

## Executive Verdict

This project is now a local-first AI workspace platform, not just a chatbot. The repo contains:

- Aegis Core Python runtime and `/v1` contract layer.
- Website FastAPI backend compatibility gateway.
- React/Vite web workspace.
- Native Windows C++/Dear ImGui desktop client.
- VS Code extension.
- Visual Studio extension.
- Release, update, migration, validation, provider, memory, model routing, workflow, plugin, and dogfooding systems.

The project has strong breadth and a lot of passing validation evidence, but it is not yet release-simple. The biggest remaining risks are:

1. The worktree is too mixed to publish safely without scoped commits.
2. Core and Website still split ownership for several runtime domains.
3. The biggest UI/client/backend files are too large for low-risk iteration.
4. External-alpha trust is now conditional, with release notes and limitations evidence attached.
5. Broad alpha still needs a fresh full validation matrix plus live smoke closure.

## Current Review Snapshot

Current branch:

`codex/aegis-agent-workspace-updates-20260501`

Configured GitHub remote:

`https://github.com/MercyProductions/Aegis-AI.git`

Important publish note:

The user previously referenced `MercyProductions Video Editor`, but this checkout is connected to `MercyProductions/Aegis-AI`. Do not push broadly until the target repo and commit scope are confirmed.

Current worktree state from `git status --short`:

| Status group | Count |
| --- | ---: |
| Total status entries | 271 |
| Modified | 97 |
| Deleted | 1 |
| Untracked | 173 |

This is the top operational risk. A release or push should be split into coherent commits, not staged with `git add -A`.

Current review refresh:

- Visible project files: 832.
- Highest-risk large files remain `src/AegisChatApp.cpp`, `website/frontend/src/App.tsx`, `vscode-plugins/aegis-local-autopilot/extension.js`, `website/backend/aegis_ai/agent.py`, `website/backend/aegis_ai/storage.py`, and `aegis-core/aegis_core/contracts.py`.
- Release package dry-run evidence is now ready at `.aegis/release-package-dry-run/20260521-062833/`.
- Final root release manifest evidence is ready at `.aegis/final-release-manifest/20260521-062851/`.
- Latest preflight evidence is ready at `.aegis/release-preflight/20260521-062909/`.
- Packaged apply/rollback evidence is ready at `.aegis/release-apply-rollback/20260521-062914/`.
- Packaged alpha scenario evidence is ready at `.aegis/packaged-alpha-scenarios/20260521-064232/`.
- Cross-client parity evidence is ready at `.aegis/cross-client-parity/20260521-065519/`.
- Release notes limitations evidence is ready at `.aegis/release-notes-limitations/20260521-071150/`.
- Latest external-alpha contract evidence is at `.aegis/external-alpha-evidence/20260521-071239/` and records a conditional private external alpha decision.
- Observability/evals/CI evidence is ready at `.aegis/observability-ci/20260521-091230/`.
- Distribution/update evidence is ready at `.aegis/distribution-update/20260521-092140/`.
- Alpha readiness polish evidence is ready at `.aegis/alpha-readiness-polish/20260521-093558/`.
- Latest ledger evidence is at `.aegis/evidence-ledger/20260521-093610/` with zero runtime blockers and `attention` status because live smoke gaps remain.

## Latest Validation Evidence

Recently verified during the roadmap implementation session:

| Surface | Command | Result |
| --- | --- | --- |
| Website backend continuity | `python -m pytest tests/test_continuity.py -q` | 2 passed |
| Website backend full suite | `python -m pytest tests -q` | 905 passed, 186 subtests passed |
| Website frontend | `npm test` | 24 test files passed, 193 tests passed |
| Website frontend production build | `npm run build` | Passed |
| Native desktop source contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-desktop-contract.ps1` | Passed |
| Native desktop build | `powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1` | Release x64 build passed, 0 warnings, 0 errors |
| Native desktop smoke | `scripts\smoke-desktop.ps1 -SkipDashboard -UseIsolatedAppData` | Built executable opened and produced a nonblank login capture |
| Release package dry-run | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-package-dry-run.ps1` | Ready at `.aegis/release-package-dry-run/20260521-062833/` |
| Final release manifest | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-final-release-manifest.ps1` | Ready at `.aegis/final-release-manifest/20260521-062851/` |
| Release artifact preflight | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-artifact-preflight.ps1` | Ready with zero blockers |
| Release apply/rollback | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-apply-rollback.ps1` | Ready; all five components apply and roll back, checksum failure enters safe mode |
| Packaged alpha scenarios | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-packaged-alpha-scenarios.ps1` | Ready at `.aegis/packaged-alpha-scenarios/20260521-064232/` |
| Cross-client parity | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-cross-client-parity.ps1` | Ready at `.aegis/cross-client-parity/20260521-065519/` |
| Release notes limitations | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-notes-limitations.ps1` | Ready at `.aegis/release-notes-limitations/20260521-071150/` |
| Observability/evals/CI contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-observability-ci.ps1` | Ready at `.aegis/observability-ci/20260521-091230/` |
| Distribution/update contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-distribution-update.ps1` | Ready at `.aegis/distribution-update/20260521-092140/` |
| Alpha readiness polish contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-alpha-readiness-polish.ps1` | Ready at `.aegis/alpha-readiness-polish/20260521-093558/` |
| External alpha contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-external-alpha-contract.ps1` | Passed; decision is conditional private external alpha |
| Evidence ledger contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-evidence-ledger-contract.ps1` | Attention with zero runtime blockers at `.aegis/evidence-ledger/20260521-093610/` |
| Release contract | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-contract.ps1` | Passed |

The full ecosystem matrix should still be rerun once the worktree is intentionally scoped:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -SkipSmoke
```

Then, before a release candidate:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -IncludeDesktopSmoke -IncludeVisualStudioPackage -IncludeReleasePackaging
```

## Project Shape

Major source and product areas:

| Area | Path | Role |
| --- | --- | --- |
| Aegis Core | `aegis-core/aegis_core` | Shared runtime, contracts, memory, workflows, validation, release compatibility, platform systems |
| Website backend | `website/backend/aegis_ai` | FastAPI gateway, compatibility routes, storage, task engine, provider accounts, model execution |
| Website frontend | `website/frontend/src` | React workspace UI, app shell, panels, provider accounts, runtime diagnostics |
| Native desktop | `src` | Win32/DirectX11/Dear ImGui desktop client |
| VS Code extension | `vscode-plugins/aegis-local-autopilot` | Editor client for local agent/autopilot workflows |
| Visual Studio extension | `visual-studio-extensions/aegis-local-agent-vs` | Visual Studio client for Core/agent workflows |
| Release/update tooling | `scripts`, `VERSION.json`, `build.ps1` | Release matrix, packaging, update planning, desktop build |
| Docs | root docs, `docs`, `aegis-core/docs` | Architecture, safety, release, memory, quality, platform governance |

Large files that should drive refactoring priorities:

| File | Lines | Risk |
| --- | ---: | --- |
| `src/AegisChatApp.cpp` | 15,973 | Native UI changes remain hard to isolate |
| `website/frontend/src/App.tsx` | 11,071 | Web app shell still owns too much UI/state |
| `vscode-plugins/aegis-local-autopilot/extension.js` | 6,631 | Extension behavior is still concentrated in one entry file |
| `website/backend/aegis_ai/agent.py` | 6,102 | Agent planning/routing/fallback logic is too concentrated |
| `website/backend/aegis_ai/project_scaffolder.py` | 5,736 | Scaffolding behavior needs domain slices and fixture-driven tests |
| `website/backend/aegis_ai/storage.py` | 5,202 | Storage concerns should continue moving into repositories/services |
| `src/AegisClient.cpp` | 4,457 | Desktop backend/Core API client remains broad |
| `website/frontend/src/types.ts` | 4,361 | Type catalog needs generated or domain-split contracts |
| `aegis-core/aegis_core/contracts.py` | 4,154 | Core contracts need grouping and generated client outputs |
| `website/backend/aegis_ai/schemas.py` | 3,787 | Schema catalog should be split by API domain |
| `website/backend/aegis_ai/main.py` | 3,766 | API registration should keep moving into route modules |

## Key Findings

### P0: Worktree And Release State Are The Immediate Blocker

The repo has many modified, deleted, and untracked files across Core, Website, Desktop, VS Code, Visual Studio, docs, and release tooling. That is not inherently bad, but it makes push/release unsafe until grouped.

Required outcome:

- Every active change belongs to a named scope.
- Release-folder deletions are accepted, regenerated, or restored.
- `VERSION.json`, release scripts, and update scripts are reviewed before becoming authoritative.
- A GitHub push uses explicit file lists or coherent commits, never a blind whole-tree stage.

### P1: Architecture Direction Is Correct But Needs Consolidation

The docs and code are aligned around Aegis Core as the shared runtime authority, with Website preserving compatibility. That is the right target. The remaining work is to keep moving shared behavior out of Website/client-specific code into Core-owned contracts.

Required outcome:

- Core owns runtime truth.
- Website owns browser/UI compatibility and local gateway fallback.
- Desktop, VS Code, and Visual Studio become thinner clients around Core contracts.
- Shared API clients/types are generated or contract-locked.

### P2: Product Surface Is Powerful But Too Broad For A Release Without Tiers

The project includes provider accounts, model routing, memory, workspace intelligence, autopilot, distributed runtime, plugins, release/update tooling, and cross-client integrations. For alpha, not all of that should be promoted as stable.

Required outcome:

- Stable, beta, experimental, and internal-only features are clearly labeled.
- Experimental systems remain hidden or opt-in.
- Alpha workflows focus on the smallest trustworthy user loop: scan, plan, patch, validate, checkpoint, rollback, remember.

## Remaining Roadmap

### Phase 0: Stabilize Worktree And Publishing

Status:

Partially done. Inventory exists, but the tree is still mixed.

Next work:

- Split current changes into commit groups:
  - Core runtime/contracts/tests.
  - Website backend/provider/security/storage.
  - Website frontend/components/types.
  - Native desktop/Core bridge.
  - VS Code extension.
  - Visual Studio extension.
  - Release/update tooling.
  - Docs/roadmaps.
- Decide the fate of deleted `release/` docs in VS Code and Visual Studio extension folders.
- Confirm whether the target GitHub repo is `MercyProductions/Aegis-AI` or a separate Video Editor repo.
- Authenticate GitHub CLI if PR creation is expected: `gh auth login`.

Acceptance:

- `git status --short` is understandable by group.
- At least one clean scoped commit can be made without unrelated changes.
- Release packaging is not blocked by accidental deleted artifacts.

### Phase 1: Make Validation One Command

Status:

Partially done. `scripts/validate-ecosystem.ps1` now covers Core, Website backend/frontend, desktop contract/build, VS Code checks, Visual Studio validation, and optional package/smoke/release gates.

Next work:

- Rerun the full matrix and store evidence under `.aegis/release-evidence`.
- Make retryable failures explicit, especially VS Code extension-host mutex cases.
- Add a short `-Fast` mode for local development and a strict release mode for release candidates.
- Publish the matrix summary in docs with exact command recipes.

Acceptance:

- One command tells whether the project is ready for normal development.
- One stricter command tells whether a release candidate is shippable.
- Every skipped gate explains how to run it.

### Phase 2: Finish Core/Website Ownership Migration

Status:

Partially done. Ownership docs and route delegation exist, but behavior remains split.

Next work:

- Move new shared behavior to Core first.
- Keep Website `/api` routes as compatibility wrappers.
- Add source-contract tests that prevent new shared runtime behavior from being implemented only in Website.
- Expand Core client delegation tests for release, security, memory, validation, checkpoints, providers, and task workflows.

Acceptance:

- Each runtime domain has one authority.
- Compatibility wrappers are explicit and tested.
- Clients can reason about Core online/offline behavior.

### Phase 3: Backend Gateway Modularization

Status:

In progress. Some route/service/repository extraction has started.

Next work:

- Continue splitting `website/backend/aegis_ai/main.py` into route modules.
- Split `agent.py` into planner, parser, draft validation, fallback, prompt building, model orchestration, and safety modules.
- Move provider-account, command execution, project builder, memory, and runtime ownership behavior into service modules.
- Keep compatibility exports stable during refactors.

Acceptance:

- New backend API work does not require editing the monolithic app module.
- Agent behavior can be tested by subsystem.
- API route registration is readable in one pass.

### Phase 4: Storage, Schema, And Contract Boundaries

Status:

Started. Project-memory repository extraction and payload redaction are in place.

Next work:

- Split `storage.py` into repositories for tasks, events, checkpoints, memory, provider accounts, release state, diagnostics, and model registry.
- Split `schemas.py` by API domain.
- Add migration smoke tests for SQLite state.
- Decide which contract types should be generated from Core.

Acceptance:

- Storage changes are localized.
- Schema changes have focused tests.
- Backward-compatible API contracts are enforced.

### Phase 5: Frontend Architecture Extraction

Status:

Started. App header and provider readiness slices were extracted, but `App.tsx` remains very large.

Next work:

- Split `App.tsx` into feature surfaces:
  - app shell and navigation.
  - chat/workspace.
  - model/provider setup.
  - tasks/validation.
  - memory/continuity.
  - diagnostics/runtime.
  - settings.
- Split `types.ts` by domain or generate from backend/Core contracts.
- Keep component tests around each extracted surface.
- Add visual/regression screenshots for core workflows.

Acceptance:

- Normal feature work rarely touches `App.tsx`.
- UI state is owned by feature hooks or domain modules.
- Frontend test files map to product surfaces.

### Phase 6: Provider Accounts And Model Routing Productization

Status:

Foundation exists. Provider manifests, account/session metadata, secure key linking, CLI bridge probing, and route readiness UI have begun.

Next work:

- Finish provider account UX for OpenAI, Gemini, Claude-style CLIs, Ollama/local, and other supported providers.
- Add health, quota/cost, privacy, fallback, and degraded-state explanations.
- Make provider route preview authoritative and understandable.
- Add tests for missing key, bad key, CLI present, CLI absent, local-only, cloud-disabled, and fallback routing.

Acceptance:

- A user can understand why a model/provider route was selected.
- Secret handling is OS-vault-backed and never leaks raw tokens.
- Provider failures degrade into visible alternatives.

### Phase 7: Agent Safety, Approval, And Event Ledger

Status:

Improved. Task event ledger payload redaction exists.

Next work:

- Add explicit approval gates by operation class.
- Require checkpoints before risky edits.
- Surface rollback criteria and stop conditions in task state.
- Expand event ledger redaction to all tool/runtime payloads.
- Add audit views for who/what/when/why on applied changes.

Acceptance:

- No autonomous write path bypasses approval, checkpoint, validation, and audit expectations.
- Task history is useful for debugging and user trust.
- Sensitive values are redacted consistently.

### Phase 8: Memory, Autopilot, And Continuation

Status:

Improved. Continuation handoff now returns active goal, next action, source record, risk, blockers, related tasks/files, validation commands, memory refs, and resume prompt.

Next work:

- Add user-editable memory controls for inspect, pin, archive, delete, and reset.
- Add durable task state fields for assumptions, completion criteria, blockers, validation status, artifacts, and current step.
- Connect continuation handoff to frontend and desktop UI.
- Add autopilot stop/rollback states and visible background-work status.
- Add bounded retrieval across code, docs, memory, transcripts, task artifacts, and validation history.

Acceptance:

- "Continue" resumes the correct task without relying on chat history.
- Memory is visible and correctable.
- Autopilot can explain what it is doing and why it stopped.

### Phase 9: Native Desktop Shell Hardening

Status:

Started. Desktop/Core compatibility status is now parsed, rendered, contract-tested, and included in desktop build validation.

Next work:

- Decide the long-term shell shape: full ImGui client vs thinner Core/Website host.
- Split `AegisChatApp.cpp` into navigation, chat, workspace, model stack, settings, diagnostics, memory, runtime, and rendering modules.
- Split `AegisClient.cpp` into typed API clients by domain.
- Expand desktop smoke coverage:
  - login/setup/dashboard.
  - backend auto-start.
  - Core status.
  - chat.
  - settings.
  - model stack.
  - runtime/changes/memory.
  - blank-window detection.
  - DPI and resize.
  - crash banner.

Acceptance:

- Desktop release does not depend on manual visual inspection.
- Native UI changes have small blast radius.
- Desktop clearly blocks or warns on incompatible Core/client versions.

### Phase 10: VS Code And Visual Studio Extension Parity

Status:

Started. VS Code has unit/static gates, Visual Studio validation exists, and a root editor parity contract now checks that both clients expose the shared Core workflow families and safety primitives.

Progress added:

- Added `scripts/test-editor-parity.ps1` to validate VS Code and Visual Studio parity for command exposure, Core endpoint coverage, release compatibility, local auth-token forwarding, default Core URL settings, local `.aegis` memory support, validation helpers, rollback safety, and Core-first docs.
- Added the `editor-parity` gate to `scripts/validate-ecosystem.ps1`.
- Verified the parity gate, VS Code helper tests, VS Code lint/package guards, and Visual Studio validation guards.

Next work:

- Split VS Code `extension.js` into:
  - commands.
  - Core API client.
  - webview rendering.
  - proposal store.
  - validation.
  - memory.
  - settings.
  - provider setup.
- Confirm Visual Studio parity for:
  - scan.
  - chat.
  - propose patch.
  - apply.
  - validate.
  - roadmap.
  - memory.
  - model status.
  - provider setup.
  - approvals.
  - rollback.
  - Core health.
- Fix or retry VS Code extension-host smoke after the VS Code update mutex clears.
- Add package smoke tests for both extensions.

Acceptance:

- Editor clients do not duplicate Core workflow logic.
- Both extensions can run the same core user loop.
- Package validation is repeatable.

### Phase 11: Release, Update, Installer, And Recovery

Status:

Partially scaffolded, with release/update contract checks now in place; not release-ready yet.

Progress added:

- Hardened `scripts/build-release.ps1` and `scripts/aegis-update.ps1` path checks so release/update operations cannot treat sibling paths as workspace or install-root children.
- Added `scripts/test-release-contract.ps1` to lock the manifest, package checksum, updater safety, ecosystem validation, Core release, and documentation expectations.
- Wired the release contract guard into `scripts/validate-ecosystem.ps1` ahead of release build and update-planning gates.
- Verified the release contract, desktop update-plan dry run, and Core release infrastructure tests.
- Dirty release artifacts remain the next packaging blocker by design.

Next work:

- Resolve dirty release artifacts.
- Make `VERSION.json` the checked release authority or replace it with the chosen manifest source.
- Generate checksums, sizes, and local paths into `release/version-manifest.json`.
- Add signing policy for desktop and extensions.
- Add installer/update UX for desktop and local runtime setup.
- Add safe-mode startup and corrupted-state quarantine.
- Add rollback-path smoke tests for update failure.
- Generate release notes from component manifests and compatibility gates.

Acceptance:

- A release can be built from a clean branch with one documented command.
- Failed update can be rolled back.
- Installer and runtime recovery are testable.

### Phase 12: Observability, Evals, And Quality Gates

Status:

Broad foundations exist in Core and docs; the first release-grade quality/eval evidence contract is now in place.

Progress added:

- Added `evals/phase12-quality-contract.json` to define required golden workflows, observability signals, performance budgets, and contract files.
- Added `scripts/test-quality-contract.ps1` to write comparable `.aegis/quality-evidence` output and fail when Core, Website, telemetry, editor parity, or docs drift away from the Phase 12 contract.
- Wired the quality contract into `scripts/validate-ecosystem.ps1` as the `quality-contract` gate.
- Documented the evidence workflow and first scan/route/chat/apply/validate/frontend budgets in `docs/QUALITY_GATES.md`.
- Verified focused Core and Website quality/eval tests, including golden workflows, provider fallback planning, route preview, and storage quality helpers.

Next work:

- Define golden workflow evals:
  - existing project continuation.
  - validation repair.
  - safe patch apply/rollback.
  - provider routing.
  - memory continuation.
  - extension/client parity.
- Track quality over time in `.aegis` evidence.
- Add performance budgets for scan, route, chat, apply, validate, and frontend render paths.
- Add source-contract tests for critical prompts and safety gates.

Acceptance:

- Quality regressions are caught before release.
- Validation evidence is easy to compare run to run.
- Performance and reliability have visible thresholds.

### Phase 13: Plugin And Ecosystem Productization

Status:

Early platform exists; the first plugin/productization contract and evidence gate are now in place.

Progress added:

- Added `evals/phase13-plugin-productization-contract.json` to lock Core plugin runtime rules, permission scopes, high-risk guards, reference plugins, productization routes, ecosystem package routes, trust levels, update channels, and required files.
- Added `scripts/test-plugin-contract.ps1` to write `.aegis/plugin-evidence` output and fail when plugin runtime, productization, ecosystem, docs, or validation wiring drift from the Phase 13 contract.
- Wired the `plugin-contract` gate into `scripts/validate-ecosystem.ps1`.
- Documented the Phase 13 evidence workflow and plugin lifecycle matrix in `docs/PLUGIN_ECOSYSTEM.md`.
- Verified Core plugin runtime/ecosystem maturity tests and Website productization/ecosystem lifecycle tests.
- Disable is now documented and guarded as the current safe-removal path; physical uninstall remains future work.

Next work:

- Define plugin packaging, permissions, trust levels, update flows, and uninstall behavior.
- Add sandbox boundaries and user-facing trust prompts.
- Add plugin compatibility checks against Core contract version.
- Build at least one first-party example plugin all the way through install, run, update, and removal.

Acceptance:

- Plugins cannot silently bypass workspace safety.
- Plugin failures are isolated and diagnosable.
- Plugin lifecycle is documented and tested.

### Phase 14: Alpha Readiness And Dogfooding

Status:

First alpha-readiness contract and recovery parity guard are now in place. Not ready for broad alpha until the full scenario suite runs against real release artifacts and release/publishing/signing limitations are stabilized or clearly disclosed.

Progress added:

- Added `evals/phase14-alpha-readiness-contract.json` to lock the alpha feature tiers, Core alpha APIs, dogfooding APIs, onboarding requirements, recovery states, scenario suite, and evidence files.
- Added `scripts/test-alpha-contract.ps1` to write `.aegis/alpha-evidence` output and fail when alpha docs, Core runtime surfaces, onboarding recovery cards, Website fallback recovery parity, focused tests, or ecosystem validation wiring drift.
- Wired the `alpha-contract` gate into `scripts/validate-ecosystem.ps1`.
- Documented the Phase 14 evidence loop, alpha scenario suite, and shared recovery state ids in the controlled alpha, dogfooding, and first-run onboarding docs.
- Expanded Core and Website fallback recovery states for backend down, Core offline, model/key/provider problems, workspace/update/validation failures, disconnected extensions, and Desktop blank state.
- Verified Core alpha/dogfooding/onboarding tests and Website onboarding delegation/fallback tests.

Next work:

- Define the alpha feature set:
  - scan workspace.
  - chat with local/cloud provider.
  - propose patch.
  - preview diff.
  - checkpoint.
  - apply.
  - validate.
  - rollback.
  - remember/resume.
- Hide or label experimental systems.
- Create first-run onboarding for the happy path and failure path.
- Dogfood on at least three real project types:
  - web app.
  - native/desktop app.
  - extension or plugin project.
- Collect evidence and issues in one alpha report.

Acceptance:

- A new user can install, configure, run, validate, and recover.
- The alpha scope is honest and bounded.
- Known limitations are visible in product and docs.

### Phase 15: External Alpha Release Report

Status:

External alpha report structure is now in place, and the current decision is explicitly blocked/no-go until packaged artifact, validation, scenario, parity, rollback, limitation, checksum, and signing evidence exists.

Progress added:

- Added `evals/phase15-external-alpha-release-contract.json` to lock the external-alpha decision states, hard blockers, report sections, artifact matrix, validation gates, scenario suite, and required files.
- Added `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md` as the single go/no-go report with current status `blocked`.
- Added `scripts/test-external-alpha-contract.ps1` to write `.aegis/external-alpha-evidence` output and fail if the report loses required blockers, sections, artifact components, scenario entries, validation gates, or blocked/no-go decision language.
- Wired the `external-alpha-contract` gate into `scripts/validate-ecosystem.ps1`.
- Verified the new external-alpha contract plus the adjacent release and alpha contracts.

Next work:

- Run `scripts\validate-ecosystem.ps1 -SkipSmoke` and attach the release evidence folder.
- Run release packaging after release-folder decisions are intentional.
- Run update planner dry runs against the generated manifest.
- Execute the full alpha scenario suite against packaged artifacts.
- Fill the external-alpha report with real evidence links and keep the decision blocked until every hard blocker is resolved or explicitly accepted for a narrow cohort.

Acceptance:

- External alpha readiness is decided from one evidence-backed report.
- The report cannot imply readiness while hard blockers are still missing evidence.
- Any conditional alpha decision names limitations, owners, retry dates, and rollback paths.

### Phase 16: Evidence Ledger And Blocker Index

Status:

Evidence ledger contract is now in place. The current ledger is blocked and points to the latest known release, quality, plugin, alpha, and external-alpha evidence folders.

Progress added:

- Added `evals/phase16-evidence-ledger-contract.json` to lock evidence roots, ledger sources, required blocker ids, validation gate ids, required files, and ledger outputs.
- Added `docs/EVIDENCE_LEDGER.md` to document the ledger workflow and current blocked evidence state.
- Added `scripts/test-evidence-ledger-contract.ps1` to generate `.aegis/evidence-ledger` output and fail if the ledger contract, docs, external-alpha report linkage, validation matrix linkage, or validation wiring drift.
- Wired the `evidence-ledger-contract` gate into `scripts/validate-ecosystem.ps1`.
- Updated the external-alpha report and validation matrix docs to reference the ledger.
- Generated `.aegis/evidence-ledger/20260521-052745/`, which records the latest evidence folders and the remaining blockers.
- Verified the evidence ledger contract and external-alpha report contract.

Initial blockers before Phase 18:

- `release_manifest_missing`
- `release_package_dry_run_not_passed`
- `update_plan_dry_run_not_passed`
- `alpha_scenario_suite_not_attached`
- `cross_client_parity_not_attached`
- `release_notes_limitations_not_attached`

Next work:

- Generate real release packaging evidence and `release/version-manifest.json`.
- Run update planner dry runs against the generated manifest.
- Attach scenario-suite and cross-client parity evidence.
- Add release notes that quote the known limitations and unsigned-build/checksum status.
- Rerun the evidence ledger and use its blocker list as the external-alpha closeout list.

Acceptance:

- The latest evidence folders and release blockers are discoverable from one generated summary.
- Missing release evidence remains visible instead of being buried in old validation folders.

### Phase 17: Release Artifact Preflight

Status:

Release artifact preflight is now in place. It is intentionally blocked because package inputs and dry-run evidence are not complete, but the blockers are now explicit and machine-readable.

Progress added:

- Added `evals/phase17-release-artifact-preflight-contract.json` for the release package readiness contract.
- Added `docs/RELEASE_ARTIFACT_PREFLIGHT.md` to document the non-mutating preflight workflow and promotion path.
- Added `scripts/test-release-artifact-preflight.ps1` to inspect `VERSION.json`, package stage inputs, extension VSIX candidates, generated release manifest state, latest release validation gates, and release artifact Git status.
- Wired `release-artifact-preflight` into `scripts/validate-ecosystem.ps1` after `release-contract`.
- Updated `docs/RELEASE_PACKAGING_AND_UPDATES.md`, `docs/VALIDATION_MATRIX.md`, `docs/EVIDENCE_LEDGER.md`, and `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md`.
- Updated Phase 15 and Phase 16 contracts so external-alpha and ledger evidence include the preflight.
- Generated `.aegis/release-preflight/20260521-053834/` and refreshed `.aegis/evidence-ledger/20260521-053844/`.

Current blockers:

- `vscode_vsix_missing`
- `visual_studio_vsix_missing`
- `release_manifest_missing`
- `dirty_release_artifacts_need_decision`
- `release_package_dry_run_not_passed`
- `update_plan_dry_run_not_passed`
- Packaged alpha scenario and cross-client parity evidence are still not attached.

Next work:

- Resolve the deleted extension release docs and untracked release/version scripts.
- Produce the VS Code and Visual Studio VSIX artifacts named in `VERSION.json`.
- Rerun the preflight until VSIX candidates and dirty-state decisions are no longer blocking.
- Generate release packages and `release/version-manifest.json`.
- Run update-plan dry runs against the generated manifest.

Acceptance:

- Release packaging is entered only after package inputs, artifact Git state, VSIX candidates, manifest generation, and update dry-run readiness are visible in one evidence folder.

### Phase 18: Extension Package Candidate Staging

Status:

Extension package candidates are now ready. The missing VSIX blockers are cleared, but ecosystem release packaging remains blocked until release artifact Git state is intentional and `release/version-manifest.json` exists with package/update dry-run evidence.

Progress added:

- Ran `npm run package` in `vscode-plugins\aegis-local-autopilot`.
- Generated `vscode-plugins\aegis-local-autopilot\release\aegis-local-autopilot-0.1.8.vsix`.
- Ran `visual-studio-extensions\aegis-local-agent-vs\build.ps1 -ValidateOnly`.
- Ran the full Visual Studio build/package script and generated `visual-studio-extensions\aegis-local-agent-vs\release\AegisLocalAgentVs.vsix`.
- Restored current VS Code release docs for changelog, install, release notes, smoke test, and troubleshooting.
- Added `evals/phase18-extension-package-candidates-contract.json`, `docs/EXTENSION_PACKAGE_CANDIDATES.md`, and `scripts/test-extension-package-candidates.ps1`.
- Wired `extension-package-candidates` into ecosystem validation.
- Updated external-alpha and evidence-ledger contracts to include extension package candidate evidence.
- Generated `.aegis/extension-package-candidates/20260521-054609/`.
- Refreshed `.aegis/release-preflight/20260521-054609/` and `.aegis/evidence-ledger/20260521-054623/`.

Current candidate status:

- VS Code VSIX: ready.
- Visual Studio VSIX: ready.
- Extension release docs: present.
- Release manifest: generated by Phase 20.
- Release package dry run: now covered by Phase 19 evidence.
- Update-plan dry runs: now covered by Phase 19 evidence.

Next work:

- Keep extension package candidates attached to the release report.
- Attach packaged alpha scenario and cross-client parity evidence.

Acceptance:

- Both editor package candidates exist, have release-facing docs, and are covered by repeatable evidence before the ecosystem package manifest is generated.

### Phase 19: Release Package Dry-Run Manifest Evidence

Package generation and update planning now have repeatable evidence without treating the root `release/` folder as final.

Progress added:

- Added `evals/phase19-release-package-dry-run-contract.json`, `docs/RELEASE_PACKAGE_DRY_RUN.md`, and `scripts/test-release-package-dry-run.ps1`.
- Wired `release-package-dry-run-contract` into ecosystem validation after extension package candidates and before release artifact preflight.
- Generated `.aegis/release-package-dry-run/20260521-055934/`, then refreshed it after Phase 21 update/release documentation changes at `.aegis/release-package-dry-run/20260521-062833/`.
- Verified the dry-run package manifest includes packages, SHA-256 values, and sizes for Core, Website, Desktop, VS Code, and Visual Studio.
- Verified `scripts/aegis-update.ps1` returns `planned` update dry-runs for all five components against the dry-run manifest.
- Refreshed `.aegis/release-preflight/20260521-062909/`; preflight is now ready after Phase 21.
- Refreshed `.aegis/evidence-ledger/20260521-062938/`; package, update-plan, root-manifest, dirty-artifact, and rollback/apply blockers are cleared.

Current status:

- Package dry run: ready.
- Update-plan dry runs: ready.
- Root `release/version-manifest.json`: generated by Phase 20.
- Dirty release artifacts: intentionally accepted for this local unsigned build candidate by `docs/RELEASE_ARTIFACT_DECISION.md`.
- External alpha: still blocked on cross-client parity evidence and final release notes/limitations.

Next work:

- Attach cross-client parity evidence.

Acceptance:

- Release package and update-plan dry-run readiness is evidence-backed and no longer depends on stale skipped gates in the latest broad validation folder.

## Remaining Roadmap From Current Review

The next work should move in this order. Alpha evidence comes first, then worktree stabilization, then architecture consolidation and product hardening.

### Phase 20: Final Release Manifest And Artifact Decision

Status:
Complete. The root release manifest exists, the generated artifact decision is documented, and release preflight now reports ready.

Purpose:
Promote the evidence-backed package set into the real release folder only after the dirty release artifact policy is explicit.

Progress added:

- Added `evals/phase20-final-release-manifest-contract.json`.
- Added `docs/RELEASE_ARTIFACT_DECISION.md`.
- Added `scripts/test-final-release-manifest.ps1`.
- Wired `final-release-manifest-contract` into ecosystem validation as an opt-in release-packaging gate.
- Refreshed Phase 19 package dry-run evidence at `.aegis/release-package-dry-run/20260521-062833/`.
- Generated final root release evidence at `.aegis/final-release-manifest/20260521-062851/`.
- Updated release preflight, evidence ledger, external-alpha, validation, and known-limitation docs/contracts to include the final manifest decision.
- Refreshed preflight evidence at `.aegis/release-preflight/20260521-062909/`.
- Refreshed evidence ledger at `.aegis/evidence-ledger/20260521-062938/`.

Current status:

- `release/version-manifest.json` exists with SHA-256 and size metadata for all five components.
- Root package files exist under `release/`.
- Dirty release artifact paths are accepted by `docs/RELEASE_ARTIFACT_DECISION.md` for this local unsigned build candidate.
- Preflight blockers are empty.
- Ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Done when:

- Done.

### Phase 21: Release Apply, Rollback, And Recovery Evidence

Status:
Complete. Packaged apply/rollback evidence exists and the external-alpha rollback/update blocker is cleared.

Purpose:
Prove the update system can apply, fail safely, and roll back from packaged artifacts.

Progress added:

- Fixed updater backup/rollback fidelity in `scripts/aegis-update.ps1`.
- Added `evals/phase21-release-apply-rollback-contract.json`.
- Added `docs/RELEASE_APPLY_ROLLBACK_EVIDENCE.md`.
- Added `scripts/test-release-apply-rollback.ps1`.
- Wired `release-apply-rollback-contract` into ecosystem validation.
- Attached rollback/apply evidence to the evidence ledger, external-alpha report/contract, validation matrix, release packaging docs, and known unstable surfaces.
- Generated ready evidence at `.aegis/release-apply-rollback/20260521-062914/`.

Current status:

- Every release component produces a planned update, applies into a temporary install root, and rolls back successfully.
- Rollback restores the pre-update marker and removes simulated stray files.
- A corrupt package fails checksum validation and records failed safe-mode state.
- Ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Done when:

- Done.

### Phase 22: Packaged Alpha Scenario Suite

Status:
Complete. Packaged scenario evidence exists and the scenario-suite ledger blocker is cleared.

Purpose:
Run the external-alpha scenario list against packaged artifacts, not just source tree tests.

Progress added:

- Added `evals/phase22-packaged-alpha-scenarios-contract.json`.
- Added `docs/PACKAGED_ALPHA_SCENARIO_EVIDENCE.md`.
- Added `scripts/test-packaged-alpha-scenarios.ps1`.
- Wired `packaged-alpha-scenarios-contract` into ecosystem validation.
- Attached packaged scenario evidence to the external-alpha report, evidence ledger, validation matrix, and known unstable surfaces.
- Generated ready evidence at `.aegis/packaged-alpha-scenarios/20260521-064232/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-064237/`.
- Refreshed evidence ledger at `.aegis/evidence-ledger/20260521-064242/`.

Current status:

- All ten scenarios have package-backed evidence.
- All five packages match their root manifest hashes.
- Packaged text files outside test fixtures have no obvious plaintext secret markers.
- Ledger blocker after Phase 23: `release_notes_limitations_not_attached`.

Done when:

- Done.

### Phase 23: Cross-Client Parity Evidence

Status:
Complete. Source-backed, package-aware parity evidence exists and the parity ledger blocker is cleared.

Purpose:
Prove Website, Desktop, VS Code, and Visual Studio all support the same safe workflow.

Progress added:

- Added `evals/phase23-cross-client-parity-contract.json`.
- Added `docs/CROSS_CLIENT_PARITY_EVIDENCE.md`.
- Added `scripts/test-cross-client-parity.ps1`.
- Wired `cross-client-parity-contract` into ecosystem validation.
- Attached parity evidence to the external-alpha report, evidence ledger, validation matrix, and known unstable surfaces.
- Generated ready evidence at `.aegis/cross-client-parity/20260521-065519/`.

Work:

- Done for the source/package evidence layer.
- Remaining live smoke gaps stay as release-note limitations: VS Code extension-host mutex, Visual Studio experimental instance, and desktop installer/update smoke.

Done when:

- Done.

### Phase 24: Final Release Notes And Limitations Evidence

Status:
Complete. Tester-facing release notes and Phase 24 limitations evidence are attached, and the final release-note ledger blocker is cleared.

Purpose:
Clear the final external-alpha blocker by publishing tester-facing release notes that include known limitations, checksum/signing status, update recovery, rollback instructions, and links to the Phase 20-23 evidence.

Progress added:

- Added `evals/phase24-release-notes-limitations-contract.json`.
- Added `docs/RELEASE_NOTES_LIMITATIONS_EVIDENCE.md`.
- Added `docs/EXTERNAL_ALPHA_RELEASE_NOTES.md`, `docs/WEBSITE_RELEASE_NOTES.md`, and `docs/DESKTOP_RELEASE_NOTES.md`.
- Updated VS Code and Visual Studio release notes with checksum, unsigned-build, evidence, and rollback details.
- Added `scripts/test-release-notes-limitations.ps1`.
- Wired `release-notes-limitations-contract` into `scripts/validate-ecosystem.ps1`, external-alpha evidence, and the evidence ledger.
- Generated ready Phase 24 evidence at `.aegis/release-notes-limitations/20260521-071150/`.
- Refreshed external-alpha evidence at `.aegis/external-alpha-evidence/20260521-071239/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-071243/`.

Current status:

- `release_notes_limitations_not_attached` is cleared.
- External-alpha decision is now conditional private external alpha, not broad alpha.
- Evidence ledger has zero runtime blockers and remains `attention` because the latest full release validation matrix still contains skipped live smoke gates.

Done when:

- Done.

### Phase 25: Core/Website Ownership Completion

Purpose:
Finish moving runtime truth into Aegis Core while Website remains the browser gateway.

Progress added in this phase:

- Added `evals/phase25-core-website-ownership-contract.json`.
- Added `docs/CORE_WEBSITE_OWNERSHIP_EVIDENCE.md`.
- Added `scripts/test-core-website-ownership.ps1`.
- Added typed React ownership client support through `RuntimeOwnershipResponse` and `getRuntimeOwnership`.
- Moved `/api/routing/preview` to Core-first model routing with Website preview/fallback compatibility.
- Wired `core-website-ownership-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger contract/script/docs and validation matrix so ownership evidence is a first-class source.
- Refreshed ready Phase 25 evidence at `.aegis/core-website-ownership/20260521-072811/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-072820/`.

Current status:

- Core owns the checked domains for changes/apply, checkpoints, validation, model routing, and agent runtime.
- Website route modules for apply, checkpoints, validation, and routing remain thin compatibility adapters.
- Provider account setup remains explicitly Website-owned.
- Evidence ledger remains `attention` because full release smoke gates are still skipped, not because ownership evidence is missing.

Done when:

- Done.

### Phase 26: Backend Modularization

Purpose:
Reduce risk in the largest backend files.

Progress added in this phase:

- Extracted the Core route-preview request/response mapper from `website/backend/aegis_ai/main.py` into `website/backend/aegis_ai/services/route_preview_service.py`.
- Kept `/api/routing/preview` as a thin orchestrator that calls Core-first routing and maps the Core response through the new service.
- Added focused service coverage in `website/backend/tests/test_route_preview_service.py`.
- Added `evals/phase26-backend-modularization-contract.json`.
- Added `docs/BACKEND_MODULARIZATION_EVIDENCE.md`.
- Added `scripts/test-backend-modularization.ps1`.
- Wired `backend-modularization-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger contract/script/docs and validation matrix so backend modularization evidence is a first-class source.
- Generated ready Phase 26 evidence at `.aegis/backend-modularization/20260521-073847/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-073928/`.

Current status:

- `main.py` no longer owns the route-preview context-file, profile-id, private-context, or Core-candidate mapping helpers.
- Route-preview behavior is covered by focused mapper tests plus the existing runtime ownership tests.
- Evidence ledger can now attach Phase 26 backend modularization evidence.

Done when:

- Done for the first backend modularization slice.
- Future slices should continue with `agent.py`, `storage.py`, and `schemas.py`.

### Phase 27: Web Frontend Extraction

Purpose:
Make the React app maintainable enough for product polish.

Progress added in this phase:

- Extracted agent bridge provider/runtime selection helpers from `website/frontend/src/App.tsx` into `website/frontend/src/utils/agentBridgeProviders.ts`.
- Kept `App.tsx` responsible for selecting provider state while the new utility owns external/local provider classification, model-family matching, runtime labels, and local runtime target selection.
- Added focused coverage in `website/frontend/src/utils/agentBridgeProviders.test.ts`.
- Added `evals/phase27-frontend-extraction-contract.json`.
- Added `docs/FRONTEND_EXTRACTION_EVIDENCE.md`.
- Added `scripts/test-frontend-extraction.ps1`.
- Wired `frontend-extraction-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger contract/script/docs and validation matrix so frontend extraction evidence is a first-class source.
- Generated ready Phase 27 evidence at `.aegis/frontend-extraction/20260521-074842/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-074857/`.

Current status:

- Provider bridge routing rules are now testable outside the large app shell.
- The frontend extraction gate runs focused Vitest coverage and the production frontend build.
- Evidence ledger can now attach Phase 27 frontend extraction evidence.

Done when:

- Done for the first frontend extraction slice.
- Future slices should continue with large route surfaces and panel renderers in `App.tsx`.

### Phase 28: Native Desktop Shell Hardening

Purpose:
Make the Windows app stable and testable before broader alpha.

Progress added in this phase:

- Extracted Runtime Status release-compatibility presentation rules from `src/AegisChatApp.cpp` into `src/desktop/RuntimeStatusPresenter.cpp` and `src/desktop/RuntimeStatusPresenter.h`.
- Kept `AegisChatApp.cpp` responsible for ImGui rendering while the presenter owns service labels, service tones, Core release-compatibility tone, requirement text, and blocker/warning/note text.
- Wired the new presenter into `CMakeLists.txt`, `AegisChatBotDesktop.vcxproj`, and `AegisChatBotDesktop.vcxproj.filters`.
- Updated `scripts/test-desktop-contract.ps1` so the desktop source contract is presenter-aware.
- Added `evals/phase28-native-desktop-shell-contract.json`.
- Added `docs/NATIVE_DESKTOP_SHELL_EVIDENCE.md`.
- Added `scripts/test-native-desktop-shell.ps1`.
- Wired `desktop-shell-hardening-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger contract/script/docs and validation matrix so native desktop shell evidence is a first-class source.
- Generated ready Phase 28 evidence at `.aegis/desktop-shell-hardening/20260521-075813/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-075820/`.

Current status:

- Runtime Status release compatibility presentation is isolated from the large native shell file.
- Desktop source contract and Release x64 build both pass after the extraction.
- Evidence ledger can now attach Phase 28 native desktop shell evidence.

Done when:

- Done for the first native desktop shell hardening slice.
- Future slices should continue splitting high-risk panels, modal surfaces, and `AegisClient.cpp` API domains.

### Phase 29: Editor Extension Modularization And Smoke

Purpose:
Bring VS Code and Visual Studio clients to parity with less risk.

Progress added in this phase:

- Rewired `vscode-plugins/aegis-local-autopilot/extension.js` so Core envelope validation, data extraction, `ok=false` handling, and contract formatting delegate to `src/core/coreEnvelope.ts`.
- Removed the duplicate Core envelope helper implementations from `extension.js` while keeping the activation file as the VS Code orchestration layer.
- Extended `vscode-plugins/aegis-local-autopilot/scripts/test-extension-helpers.js` to cover `requireCoreOk`, `formatCoreContract`, contract-version formatting, and redacted Core errors.
- Updated `vscode-plugins/aegis-local-autopilot/scripts/lint-package.js` so package lint fails if `extension.js` reintroduces duplicate Core envelope helpers.
- Added `evals/phase29-editor-extension-modularization-contract.json`.
- Added `docs/EDITOR_EXTENSION_MODULARIZATION_EVIDENCE.md`.
- Added `scripts/test-editor-extension-modularization.ps1`.
- Wired `editor-extension-modularization-contract` into `scripts/validate-ecosystem.ps1`.
- Updated the evidence ledger contract/script/docs and validation matrix so editor extension modularization evidence is a first-class source.
- Generated ready Phase 29 evidence at `.aegis/editor-extension-modularization/20260521-081105/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-081112/`.

Current status:

- The VS Code Core envelope contract is shared and covered by focused helper tests plus package lint.
- The Phase 29 gate runs VS Code helper tests, VS Code lint/package guards, and the Visual Studio `build.ps1 -ValidateOnly` package-validation substitute.
- Evidence ledger can now attach Phase 29 editor extension modularization evidence.

Done when:

- Done for the first editor extension modularization and non-interactive parity slice.
- Future slices should continue extracting VS Code command registration, workspace scan, proposal/apply, validation, and webview rendering from `extension.js`.

### Phase 30: Provider, Model Routing, And Secret Safety

Purpose:
Make provider accounts and routing safe enough for real testers.

Progress added in this phase:

- Added `ProviderRouteSafety` to provider account snapshots with route type, privacy boundary, secret-storage boundary, cloud-context consent, workspace-context behavior, cost, quota, latency, fallback policy, diagnostics safety, and user action state.
- Populated route-safety summaries in `ProviderAccountManager` for local endpoints, API-key routes, official CLI delegation, environment-profile routes, OAuth-pending routes, and unsupported routes.
- Redacted provider account, session, CLI bridge, readiness, and route-safety error text before it leaves the manager.
- Extended backend provider account tests for API-key OS credential-store boundaries, local no-secret routing, CLI no-token-import routing, and secret-like readiness error redaction.
- Extended frontend provider route-readiness types and cards to prefer backend route-safety boundaries and redact secret-like card text before display.
- Added `evals/phase30-provider-secret-safety-contract.json`.
- Added `docs/PROVIDER_SECRET_SAFETY_EVIDENCE.md`.
- Added `scripts/test-provider-secret-safety.ps1`.
- Wired `provider-secret-safety-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 30 provider secret safety evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 30 evidence at `.aegis/provider-secret-safety/20260521-082837/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-082848/`.

Current status:

- Provider status payloads now expose machine-readable privacy, consent, secret storage, cost, quota, latency, and fallback boundaries.
- The Phase 30 gate runs backend provider account tests and frontend provider route-readiness tests.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the first provider route-safety and secret-redaction slice.
- Future slices should add live provider health checks, model mismatch/fallback tests, and explicit launch-time cloud consent before workspace context leaves the machine.

### Phase 31: Memory, Privacy, And Governance Controls

Purpose:
Make durable memory trustworthy.

Progress added in this phase:

- Added Core-delegated Website backend support for memory governance, export, and controls while preserving the legacy local-memory fallback path.
- Added `GET /api/memory/governance`, `POST /api/memory/export`, and `POST /api/memory/controls`.
- Extended memory note responses with governance, privacy, control, delegation, and runtime metadata.
- Added local-only fallback governance, storage-boundary reporting, and secret-like redaction for legacy memory exports.
- Extended frontend memory API types and client helpers for governance, export, and control updates.
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

- Users and clients can inspect memory mode, storage boundary, category controls, audit availability, export/delete support, and cloud-context consent requirements.
- Legacy Website memory remains local-only and exportable with secret-like content redacted by default.
- The Phase 31 gate runs backend Core runtime delegation tests and frontend memory API tests.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the first memory governance, export, control, and legacy-redaction slice.
- Future slices should add prompt-injection scanning for files, tool output, copied text, imported docs, and future web/PDF imports, plus a broader tool-event ledger for reads, writes, commands, exports, generation jobs, and memory writes.

### Phase 32: Plugin Ecosystem Productization

Purpose:
Turn plugin scaffolding into a safe ecosystem.

Progress added in this phase:

- Added productization plugin lifecycle request/response schemas for update, rollback, and safe-uninstall actions.
- Added ecosystem package lifecycle request/response schemas for update, rollback, and safe-uninstall actions.
- Added checksum fields to productization plugin manifests and checksum mismatch validation to productization and ecosystem package manifests.
- Added `POST /api/productization/plugins/{plugin_id}/update`, `/rollback`, and `/uninstall`.
- Added `POST /api/ecosystem/packages/{package_id}/update`, `/rollback`, and `/uninstall`.
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

- Website plugin/package lifecycle now has auditable update, rollback, and safe-uninstall flows.
- Checksums are machine-validated for replacement manifests before saving.
- The Phase 32 gate runs backend productization and ecosystem tests.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the first reversible plugin/package lifecycle productization slice.
- Future slices should add artifact-level signature verification, real package download/install staging, and a rendered first-party plugin UI surface.

### Phase 33: Observability, Evals, And CI

Purpose:
Keep quality from depending on manual memory.

Progress added in this phase:

- Added `.github/workflows/aegis-validation.yml` with Windows CI jobs for Core tests, Website backend tests, Website frontend tests/build, desktop contract/build, VS Code unit/lint guards, Visual Studio validation guards, release/evidence contracts, and a manual full ecosystem matrix.
- Added `evals/phase33-observability-ci-contract.json`.
- Added `docs/OBSERVABILITY_EVALS_CI_EVIDENCE.md`.
- Added `scripts/test-observability-ci.ps1`.
- Wired `observability-ci-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 33 observability CI evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 33 evidence at `.aegis/observability-ci/20260521-091230/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-091239/`.

Current status:

- The workflow now covers the main CI surfaces plus a manual `validate-ecosystem.ps1 -SkipSmoke` job.
- The Phase 33 gate runs the Phase 12 quality contract and `website/backend/tests/test_golden_workflows.py`.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the first observability/evals/CI evidence slice.
- Future slices should add rendered dashboards or uploaded CI artifacts for route quality, fallback reliability, token/cost drift, and scenario regressions.

### Completed Phase 34: Distribution, Installer, Signing, And Auto-Update

Purpose:
Make installation and updates real.

Progress added in this phase:

- Added `docs/DISTRIBUTION_INSTALLER_UPDATE_EVIDENCE.md`.
- Added `evals/phase34-distribution-update-contract.json`.
- Added `scripts/test-distribution-update.ps1`.
- Documented the private-alpha distribution decision in `docs/RELEASE_PACKAGING_AND_UPDATES.md`: portable ZIP packages for Core/Website/Desktop, VSIX packages for editor extensions, signed installers deferred until broad release, and unsigned local builds disclosed explicitly.
- Verified `release/version-manifest.json` package paths, sizes, SHA-256 values, component versions, update policy, shipped updater, rollback/safe-mode markers, and local-only redacted diagnostics export.
- Ran non-mutating updater plans for `aegis-core`, `website`, `desktop`, `vscode-extension`, and `visual-studio-extension`; all returned `planned` with checksums required.
- Wired `distribution-update-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 34 distribution/update evidence to the evidence ledger contract, script, docs, and validation matrix.
- Generated ready Phase 34 evidence at `.aegis/distribution-update/20260521-092140/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-092406/`.

Current status:

- The current private-alpha package path is auditable and checksum-backed.
- Signed installer readiness is intentionally not claimed yet.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the current private-alpha portable ZIP and VSIX distribution evidence slice.
- Future distribution slices should select installer technology, configure signing, add installer smoke evidence, expose open-logs/diagnostics affordances in the clients, and run live update/rollback on a clean install target.

### Completed Phase 35: Alpha Readiness Polish

Purpose:
Make the first external build feel intentional.

Progress added in this phase:

- Added `alpha_handoff_summary()` to `aegis-core/aegis_core/alpha.py` and included it in the Core alpha readiness payload.
- Labeled tester-facing surfaces as Stable Alpha, Beta, Experimental, and Internal Only with default visibility rules.
- Added a default alpha path for checksum verification, local Core launch, workspace selection, provider setup, local model setup, validate-only first workflow, checkpoint/rollback confirmation, diagnostics export, and feedback capture.
- Added `evals/phase35-alpha-readiness-polish-contract.json`.
- Added `docs/ALPHA_READINESS_POLISH_EVIDENCE.md`.
- Added `scripts/test-alpha-readiness-polish.ps1`.
- Updated controlled alpha, first-run onboarding, external alpha release notes, known unstable surfaces, validation matrix, and evidence ledger docs.
- Extended Core alpha readiness tests to cover the Phase 35 handoff summary.
- Wired `alpha-readiness-polish-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 35 alpha readiness polish evidence to the evidence ledger contract and script.
- Generated ready Phase 35 evidence at `.aegis/alpha-readiness-polish/20260521-093558/`.
- Refreshed evidence-ledger output at `.aegis/evidence-ledger/20260521-093610/`.

Current status:

- The private-alpha tester handoff is now contract-checked and documented.
- Experimental and Internal Only surfaces are explicitly opt-in or hidden from the default alpha path.
- Ledger status remains `attention` only because the latest full release validation matrix still has skipped live smoke gates.

Done when:

- Done for the first tester-facing alpha readiness polish slice.
- Broader alpha still requires live smoke/package closure and scoped release commits.

### Completed Phase 36: Live Smoke Closure And Release Candidate Scoping

Purpose:
Turn the current evidence-backed private alpha into a release candidate with fewer skipped gates.

Progress added in this phase:

- Added `evals/phase36-live-smoke-rc-contract.json`.
- Added `docs/LIVE_SMOKE_RC_SCOPING_EVIDENCE.md`.
- Added `scripts/test-live-smoke-rc.ps1`.
- Wired `live-smoke-rc-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 36 live smoke RC scoping to validation matrix docs, evidence ledger docs, evidence ledger contract/script, external alpha release notes, external alpha report, and known unstable surfaces.
- Added a live gate closure inventory for `desktop-smoke`, `vscode-smoke`, `visual-studio-package`, `release-package-dry-run`, and `update-plan-dry-run`.
- Kept the contract `status` separate from `release_candidate_status`, so scoping evidence can be ready while the candidate remains `attention`.
- Captured release publish scope as `intentional_release_artifact_decision`, `worktree_scope_required`, `github_target_pending`, and `broad_alpha_blocked`.
- Generated fresh release validation evidence at `.aegis/release-evidence/20260521-095247/`.
- Generated ready Phase 36 evidence at `.aegis/live-smoke-rc/20260521-095750/`.
- Refreshed evidence ledger output at `.aegis/evidence-ledger/20260521-095800/`.

Current status:

- Phase 36 evidence can now be attached under `.aegis/live-smoke-rc/<timestamp>/`.
- The release candidate remains `attention` until fresh validation closes the live smoke/package gates.
- The next publish step is worktree/commit scoping, not a broad push.

Done when:

- Done for the first release-candidate scoping slice.
- Future Phase 36 closure still needs VS Code, Visual Studio, release package, and installer/update runtime evidence.

### Completed Phase 37: Commit Scoping And GitHub Handoff

Purpose:
Make the dirty worktree safe to publish.

Progress added in this phase:

- Added `evals/phase37-commit-scoping-github-handoff-contract.json`.
- Added `docs/COMMIT_SCOPING_GITHUB_HANDOFF_EVIDENCE.md`.
- Added `scripts/test-commit-scoping-github-handoff.ps1`.
- Wired `commit-scoping-github-handoff-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 37 commit scoping to validation matrix docs, evidence ledger docs, evidence ledger contract/script, external alpha release notes, external alpha report, and known unstable surfaces.
- Added commit groups for docs, evidence/validation, Core, Website backend, Website frontend, native desktop, VS Code, Visual Studio, release/update artifacts, and design/misc assets.
- Added publish blockers for dirty worktree scope, `website inspiration.png`, GitHub target confirmation, and Phase 36 release candidate attention state.
- Preserved the no blind stage rule: future publishing must use explicit file lists, not `git add -A`.
- Refreshed evidence at `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`, `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`, and `.aegis/release-evidence/20260521-110934/validation-summary.md`.

Done when:

- Done for the first publish handoff slice.
- Future Phase 37 closure still needs user confirmation of target repo, deleted asset decision, and scoped commits.

### Completed Phase 38: Desktop Smoke And Package Gate Execution

Purpose:
Convert one or more skipped runtime/package gates into real evidence.

Progress:

- Added `evals/phase38-desktop-smoke-package-gates-contract.json`.
- Added `docs/DESKTOP_SMOKE_PACKAGE_GATES_EVIDENCE.md`.
- Added `scripts/test-desktop-smoke-package-gates.ps1`.
- Wired `desktop-smoke-package-gates-contract` into `scripts/validate-ecosystem.ps1`.
- Added Phase 38 to validation matrix docs, external alpha release notes/report, known unstable surfaces, evidence ledger docs, and evidence ledger contract/script.
- Ran isolated desktop runtime smoke and attached screenshot/log evidence in `.aegis/desktop-smoke-package-gates/20260521-111533/`.
- Ran `scripts\validate-ecosystem.ps1 -SkipSmoke -IncludeDesktopSmoke`; desktop smoke passed while the overall matrix stayed `attention` due 4 intentional editor/package skips.
- Fixed the Core runtime state save race on Windows by using unique temp files and retrying replace on `PermissionError`.
- Refreshed Phase 36 RC scoping, Phase 37 handoff, Phase 38 package gates, and the evidence ledger.

Done when:

- Done for the first desktop smoke/package gate execution slice.
- Remaining closure work: VS Code extension-host smoke, Visual Studio package, release-package dry run, and final release manifest mutation decisions.

### Completed Phase 39: Editor Smoke And Release Package Decision Execution

Purpose:
Close the next skipped editor/package gate without blurring release artifact scope.

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

### Phase 40: Package Mutation Decision And Artifact Gate Execution

Purpose:
Close the next package mutation gate with the release artifact decision attached.

Work:

- Confirm whether Visual Studio extension release artifacts, root release artifacts, or both may be mutated in this checkout.
- Run `visual-studio-package`, `release-package-dry-run`, or `final-release-manifest-contract` only under the explicit mutation scope.
- Rerun VS Code extension-host smoke after the `vscode-updating` mutex clears.
- Refresh Phase 36, Phase 37, Phase 38, Phase 39, and ledger evidence after the next gate status changes.

Done when:

- At least one package mutation gate is converted to passed, retryable, or owner-blocked evidence with mutation scope recorded.

## Immediate Next 10 Tasks

1. Confirm GitHub target repo and decide whether this checkout should push to `MercyProductions/Aegis-AI` or another repo.
2. Decide whether the deleted `website inspiration.png` is intentionally removed.
3. Split future commits by explicit file groups; do not broad-stage the generated release folder with unrelated source edits.
4. Start Phase 40 by deciding Visual Studio/root release package mutation scope.
5. Rerun VS Code extension-host smoke after the `vscode-updating` mutex clears.
6. Run Visual Studio package/experimental-instance smoke or release-package dry run with that decision attached.
7. Refresh Phase 36, Phase 37, Phase 38, Phase 39, and ledger evidence after the next gate closes.
8. Continue backend modularization with `website/backend/aegis_ai/agent.py`, `storage.py`, and `schemas.py`.
9. Continue frontend extraction after the smoke/package gate status is updated.
10. Continue editor extension extraction with the VS Code smoke result in hand.

## Recommended Commit Groups

Use these groups to reduce review risk:

1. Roadmaps and review docs.
2. Phase 9 desktop compatibility and desktop contract guard.
3. Website backend continuation/storage/redaction/provider work.
4. Website frontend app-shell/provider-readiness work.
5. Aegis Core runtime/contracts/tests.
6. VS Code extension source/package changes.
7. Visual Studio extension source/package changes.
8. Release/update/version tooling.

## Definition Of Done For The Platform

The project should be considered ready for serious external alpha only when:

- The worktree is clean or intentionally scoped.
- Full validation matrix passes or has documented retryable skips.
- Release packaging and rollback dry runs pass.
- Desktop, Website, VS Code, and Visual Studio all demonstrate the same safe workflow.
- Core/Website ownership is documented and contract-tested.
- Backend service extraction is contract-tested as route slices move out of large orchestrator files.
- Memory, provider routing, and autopilot have user-visible controls.
- Experimental systems are labeled or hidden.
- A new user can recover from setup, provider, validation, and update failures.
