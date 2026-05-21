# Aegis ChatBot External Alpha Release Notes

Generated: 2026-05-21

## Status

This is a conditional private external alpha candidate for trusted technical testers only. It is not a broad public alpha.

The release is local-first, unsigned, checksum-verified, and evidence-backed. Tester invites must include these notes, `KNOWN_UNSTABLE_SURFACES.md`, the root `release/version-manifest.json`, and the Phase 24 evidence summary.

## Tester Scope

Use this candidate to validate the local Aegis safe-edit workflow across Core, Website, Desktop, VS Code, and Visual Studio:

- workspace scan
- model route selection
- proposal or review
- approved apply
- validation
- checkpoint
- rollback or restore
- diagnostics visibility
- release compatibility

Do not use this build on irreplaceable workspaces without a separate backup. Keep tests to disposable branches, sample projects, or workspaces that can be restored.

## Package Manifest

Source manifest: `release/version-manifest.json`.

| Component | Version | Artifact | Size Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `aegis-core` | `0.1.0` | `release/aegis-core-0.1.0.zip` | 1774434 | `9df59ecf74524ef5fb076e33b2da761d4a5e480e20f5c4e3902f1f785b99dd45` |
| `website` | `0.1.0` | `release/aegis-website-0.1.0.zip` | 12201239 | `9183dd9e5308f035847f302f8ad9711b656976f5fee0d90a5cc5afe9e29259ab` |
| `desktop` | `0.2.0` | `release/aegis-desktop-0.2.0-portable.zip` | 1276809 | `331a7ee0c548644d483d39bc619c930dfaa8b0f83f382acd8dc5586201fd23dd` |
| `vscode-extension` | `0.1.8` | `release/aegis-local-autopilot-0.1.8.vsix` | 998347 | `13394f306497687afa299d677973cb0b87cf7fc4b7f53550cbc173aaef24705f` |
| `visual-studio-extension` | `0.1.1` | `release/AegisLocalAgentVs.vsix` | 216454 | `33bf11d7296e8d69415f1e9745a06c4f988668714c609a25e39b2d1cbc7f4529` |

Compatibility floor:

- Core API: `v1`
- Core contract: `2026.05.12`
- Minimum Core: `0.1.0`
- Website: `0.1.0`
- Desktop: `0.2.0`
- VS Code extension: `0.1.8`
- Visual Studio extension: `0.1.1`

## Validation Evidence

Attach these evidence folders with tester handoff notes:

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Release preflight: `.aegis/release-preflight/20260521-062909/release-artifact-preflight-summary.md`
- Package dry run: `.aegis/release-package-dry-run/20260521-062833/release-package-dry-run-summary.md`
- Final release manifest: `.aegis/final-release-manifest/20260521-062851/final-release-manifest-summary.md`
- Apply and rollback: `.aegis/release-apply-rollback/20260521-062914/release-apply-rollback-summary.md`
- Packaged alpha scenarios: `.aegis/packaged-alpha-scenarios/20260521-064232/packaged-alpha-scenarios-summary.md`
- Cross-client parity: `.aegis/cross-client-parity/20260521-065519/cross-client-parity-summary.md`
- Distribution/update: `.aegis/distribution-update/20260521-092140/distribution-update-summary.md`
- Alpha readiness polish: `.aegis/alpha-readiness-polish/<timestamp>/alpha-readiness-polish-summary.md`
- Phase 36 live smoke RC scoping: `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`
- Phase 37 commit scoping and GitHub handoff: `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- Phase 38 desktop smoke and package gate evidence: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke and release package decision evidence: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`

The latest release validation folder, `.aegis/release-evidence/20260521-110934/`, is still `attention`, not a clean broad-alpha pass, because one editor smoke gate is retryable and three package gates were intentionally skipped or need dedicated mutation decisions.

## Phase 35 Tester Handoff

Use these labels in tester notes and support triage:

- Stable Alpha: default-visible Core contracts, local workspace scan, checkpoints, validation, rollback, local model visibility, release compatibility, and diagnostics export.
- Beta: default-visible with label for Engineering Workspace, onboarding, quality gates, Core delegation fallback, client runtime surfaces, knowledge graph, and dogfooding feedback.
- Experimental: opt-in only for advanced orchestration, distributed/runtime labs, deployment intelligence, personal intelligence, and real-time terminal orchestration.
- Internal Only: hidden from tester handoff for credential internals, unrestricted autonomy, raw mutation surfaces, internal dogfooding notes, and debug route experiments.

The default first-run path is checksum verification, local Core launch, workspace selection, provider setup or local-only confirmation, local model setup, validate-only first workflow, checkpoint/rollback confirmation, diagnostics export, and feedback capture.

## Phase 36 Release Candidate Scope

The release candidate status remains `attention` until `vscode-smoke`, `visual-studio-package`, and release-package mutation gates are closed in fresh validation evidence. `desktop-smoke` and `update-plan-dry-run` are closed in `.aegis/release-evidence/20260521-110934/`; `vscode-smoke` is retryable because the VS Code test instance still holds the `vscode-updating` mutex. Any GitHub push still requires scoped commits and confirmation of the target repository, currently expected to be `MercyProductions/Aegis-AI`.

## Phase 37 Commit Scoping

The publish handoff status remains `attention` until commit groups are staged with explicit file lists, `website inspiration.png` is confirmed as intentionally deleted or restored, and the GitHub target is confirmed. Do not use a broad `git add -A` for this worktree.

## Phase 38 Desktop Smoke And Package Gates

The desktop smoke/package execution status is `ready` for the first Phase 38 slice because `desktop-smoke` has passed with screenshots/log evidence. Package gates that mutate release folders still need an explicit release-artifact decision before they run.

## Phase 39 Editor Smoke And Release Package Decisions

Phase 39 tracks `vscode-smoke`, `visual-studio-package`, `release-package-dry-run`, and `final-release-manifest-contract`. The first target, VS Code extension-host smoke, has attached retryable evidence because the VS Code test instance still holds the `vscode-updating` mutex. Visual Studio and release package gates still require an explicit release artifact decision and mutation scope before execution.

## Checksums And Signing

Checksums are required for every package. Verify each artifact against `release/version-manifest.json` before install or update.

This package set is an unsigned local build candidate. The unsigned local build limitation is accepted only for conditional private external alpha. Signed installers and broad distribution remain future work.

## Update And Rollback

Preview an update plan:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component desktop
```

Rollback the latest applied update:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Rollback
```

Recovery state is written to:

- `.aegis/update-state.json`
- `.aegis/safe-mode.json`
- `.aegis/updates/backups`
- `.aegis/updates/downloads`

If checksum validation fails, the updater must stop before applying the package and leave safe-mode evidence for recovery.

## Component Notes

Core provides the local release contract, compatibility endpoints, migrations, update planning, checkpoint records, and safe workflow state.

Website exposes the browser UI and backend gateway for workspace, proposal, validation, diagnostics, and release compatibility workflows. See `docs/WEBSITE_RELEASE_NOTES.md`.

Desktop is a portable native candidate with Core compatibility checks, workspace scan, proposal/apply, validation, checkpoint, rollback, and diagnostics surfaces. See `docs/DESKTOP_RELEASE_NOTES.md`.

VS Code extension `0.1.8` is the packaged editor client candidate. See `vscode-plugins/aegis-local-autopilot/release/RELEASE_NOTES.md`.

Visual Studio extension `0.1.1` is the packaged Visual Studio client candidate. See `visual-studio-extensions/aegis-local-agent-vs/release/RELEASE_NOTES.md`.

## Known Limitations

| Limitation | Tester Impact | Owner | Retry Or Exit Criteria | Recovery Path |
| --- | --- | --- | --- | --- |
| Active worktree and commit grouping are still decision-sensitive. | Release artifacts, docs, and source edits need scoped commit grouping before a public push. | Release owner | Before GitHub publishing or broad alpha. | Keep tester distribution to the attached package manifest and evidence folders. |
| VS Code extension-host smoke can be blocked by the `vscode-updating` mutex. | VS Code may need a retry after the test instance finishes updating. | Editor owner | Rerun extension-host smoke after mutex clears. | Use packaged scenario and parity evidence, then retry smoke before broad alpha. |
| Visual Studio experimental-instance smoke still needs a fresh runtime pass. | Visual Studio UI workflows require manual IDE validation. | Editor owner | Run experimental-instance smoke on the target Visual Studio 2022 build. | Use rollback command and Visual Studio uninstall if the extension blocks local work. |
| Desktop runtime smoke passed, but desktop installer and installer/update flows were not fully exercised. | Desktop should be treated as portable and test-only. | Desktop owner | Complete installer/update pass. | Use `scripts\aegis-update.ps1 -Rollback` and restore from `.aegis/updates/backups`. |
| Live provider checks, local model checks, and Ollama/provider fallback checks were not rerun. | Provider and local model setup can fail and should stay visible to testers. | Runtime owner | Add live provider/local model health evidence. | Use local-only mode or retry after provider/model setup is repaired. |
| Plugin/ecosystem install, trust, update, and rollback flows remain productization work. | Plugin behavior should not be treated as production-grade. | Platform owner | Finish plugin trust/update/rollback evidence. | Disable plugins or test only first-party reference flows. |
| Memory, provider routing, and autopilot controls need tester-visible reset and privacy affordances. | Testers need explicit control over what is remembered or routed. | Product owner | Add reset, privacy, and route visibility controls. | Clear workspace `.aegis` state or use disposable workspaces. |
| Cross-client parity is source-backed and package-aware, but not a replacement for every live smoke test. | Website, Desktop, VS Code, and Visual Studio have evidence parity, while runtime smoke gaps remain. | Release owner | Complete live smoke matrix before broad alpha. | Treat failures as alpha feedback and use rollback/checkpoint restore. |
| Phase 36 release candidate status is still attention. | The build can support a narrow private alpha handoff but not broad release. | Release owner | Rerun `vscode-smoke` after the mutex clears, then close `visual-studio-package` and release-package mutation gates in fresh evidence. | Keep tester distribution tied to the current manifest and evidence ledger. |
| Phase 37 publish handoff status is still attention. | Source, docs, release artifacts, and generated outputs need explicit commit grouping before push. | Release owner | Confirm target repo, resolve `website inspiration.png`, and stage by commit group. | Do not push until the handoff evidence is ready. |
| Phase 38 desktop smoke/package gate status is ready for the first slice. | Package skips still need owner decisions and mutation scope. | Release owner | Decide package mutation scope and run the remaining package gates. | Keep package installs tied to checksum manifest and rollback guidance. |
| Phase 39 editor smoke/release package decision evidence is ready for the first slice. | VS Code smoke is retryable due the update mutex; package gates still need owner decisions. | Release owner | Rerun VS Code extension-host smoke after the mutex clears, then decide package mutation scope. | Keep editor smoke logs attached before promoting testers. |

## Conditional Alpha Decision

This release can move from no-go to conditional private external alpha only with these notes attached. Broad alpha stays blocked until live smoke gaps, signing/installer decisions, and worktree commit grouping are resolved.
