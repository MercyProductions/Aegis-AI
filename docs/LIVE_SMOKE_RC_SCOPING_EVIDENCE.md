# Phase 36 Live Smoke Closure And Release Candidate Scoping Evidence

Generated: 2026-05-21

Phase 36 turns the remaining release ambiguity into a tracked release-candidate scope. It does not claim broad-alpha readiness by default. It records whether the live smoke and release-package gates are closed, skipped with an intentional reason, retryable because of the environment, or still not observed.

Machine-readable contract: `evals/phase36-live-smoke-rc-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-live-smoke-rc.ps1
```

Evidence output:

```text
.aegis/live-smoke-rc/<timestamp>/
```

## Scope

The Phase 36 evidence includes:

- latest release validation inventory from `.aegis/release-evidence/<timestamp>/validation-matrix.json`
- `live_gate_closure` inventory for `desktop-smoke`, `vscode-smoke`, `visual-studio-package`, `release-package-dry-run`, and `update-plan-dry-run`
- upstream evidence attachment for alpha readiness polish, distribution/update, release package dry run, final release manifest, and release apply/rollback
- explicit release-candidate status: `attention` until live smoke/package gaps close, `ready` only when the release validation matrix proves the gates are closed
- publish scoping flags for intentional release artifact mutation, worktree grouping, GitHub target confirmation, and broad-alpha blocking

## Current Release-Candidate Decision

Current release candidate status is `attention`.

Reasons:

- desktop runtime smoke still needs a focused pass with the current package set
- VS Code extension-host smoke can still be blocked by the `vscode-updating` mutex
- Visual Studio package or experimental-instance smoke still requires an intentional package/run decision
- release packaging and update planner should be re-run only after the release-artifact mutation decision is intentional
- worktree scope and GitHub target must be confirmed before any push

Latest evidence generated in this phase:

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Phase 36 RC scoping: `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`
- Phase 38 desktop smoke/package gates: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke/package decisions: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- Evidence ledger refresh: `.aegis/evidence-ledger/20260521-095800/evidence-ledger-summary.md`

## Closure Commands

Use these commands when the environment is ready:

```powershell
# Fresh non-mutating release evidence with known smoke skips visible.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -SkipSmoke

# Desktop runtime smoke after the native build is available.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -IncludeDesktopSmoke

# VS Code extension-host smoke after the update mutex clears.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1

# Visual Studio package after release-folder mutation is intentional.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -IncludeVisualStudioPackage -AllowDirtyReleaseArtifacts

# Release package and update-planner dry run after release artifact mutation is intentional.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate-ecosystem.ps1 -IncludeReleasePackaging -AllowDirtyReleaseArtifacts
```

## Release Candidate Rules

- `status` in `live-smoke-rc.json` means the Phase 36 evidence contract itself passed.
- `release_candidate_status` is separate and remains `attention` while any required live gate is skipped, retryable, failed, or not observed.
- Broad alpha remains blocked until live smoke gaps, signing/installer decisions, provider/local model health checks, and worktree publish scope are resolved.
- Pushing to GitHub requires scoped commits and confirmation of the target repository, currently expected to be `MercyProductions/Aegis-AI`.

## Evidence Ledger

The evidence ledger reads Phase 36 from `.aegis/live-smoke-rc/<timestamp>/live-smoke-rc.json`. The ledger can remain `attention` even when Phase 36 evidence is `ready`, because the release candidate itself is not `ready` until live smoke and package gates are closed.
