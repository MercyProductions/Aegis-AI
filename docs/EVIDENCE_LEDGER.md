# Evidence Ledger

The evidence ledger is the Phase 16 bridge between contract checks and release decisions. It inventories the newest known evidence folders, summarizes what is present, and keeps the release decision honest as evidence moves from blocked to conditional.

Machine-readable contract: `evals/phase16-evidence-ledger-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-evidence-ledger-contract.ps1
```

Evidence output:

```text
.aegis/evidence-ledger/<timestamp>/
```

When the ledger runs inside `scripts\validate-ecosystem.ps1`, its output is nested under the current `.aegis/release-evidence/<timestamp>/evidence-ledger-contract/` folder.

## Sources

The ledger reads the newest available folder under:

- `.aegis/release-evidence`
- `.aegis/release-preflight`
- `.aegis/release-package-dry-run`
- `.aegis/final-release-manifest`
- `.aegis/release-apply-rollback`
- `.aegis/packaged-alpha-scenarios`
- `.aegis/cross-client-parity`
- `.aegis/release-notes-limitations`
- `.aegis/core-website-ownership`
- `.aegis/backend-modularization`
- `.aegis/frontend-extraction`
- `.aegis/desktop-shell-hardening`
- `.aegis/editor-extension-modularization`
- `.aegis/provider-secret-safety`
- `.aegis/memory-governance`
- `.aegis/plugin-lifecycle`
- `.aegis/observability-ci`
- `.aegis/distribution-update`
- `.aegis/alpha-readiness-polish`
- `.aegis/live-smoke-rc`
- `.aegis/commit-scoping-github-handoff`
- `.aegis/desktop-smoke-package-gates`
- `.aegis/editor-smoke-release-package-decision`
- `.aegis/extension-package-candidates`
- `.aegis/quality-evidence`
- `.aegis/plugin-evidence`
- `.aegis/alpha-evidence`
- `.aegis/external-alpha-evidence`

It also reads:

- `VERSION.json`
- `release/version-manifest.json` when release packaging has generated it
- `docs/RELEASE_ARTIFACT_DECISION.md`
- `KNOWN_UNSTABLE_SURFACES.md`
- `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md`

## Required Outputs

Each run writes:

- `evidence-ledger.json`
- `evidence-ledger-summary.md`

## Current Status

The current status is attention. That is intentional.

Latest refreshed ledger evidence:

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Phase 36 live smoke RC scoping: `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`
- Phase 37 commit scoping and GitHub handoff: `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- Phase 38 desktop smoke/package gates: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke/release package decisions: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- Evidence ledger: `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`

Required unresolved blockers:

- none

The ledger still tracks `release_manifest_missing`, `dirty_release_artifacts_need_decision`, `release_package_dry_run_not_passed`, `update_plan_dry_run_not_passed`, and `final_release_manifest_not_ready` when the matching evidence is missing or blocked. Ready Phase 19 package dry-run evidence plus ready Phase 20 final-manifest evidence clears those release-artifact blockers.

The ledger reports attention because release-note, ownership, backend modularization, frontend extraction, desktop shell hardening, editor extension modularization, provider secret safety, memory governance, plugin lifecycle, observability CI, distribution/update, alpha readiness polish, Phase 36 live smoke RC scoping, Phase 37 commit scoping, Phase 38 desktop smoke/package gate evidence, and Phase 39 editor smoke/release package decision evidence are attached, but the latest full release validation matrix still contains one retryable VS Code smoke gate, skipped package gates, and an attention publish handoff. Phase 21 rollback/apply evidence is read from `.aegis/release-apply-rollback/<timestamp>/`; Phase 22 packaged scenario evidence is read from `.aegis/packaged-alpha-scenarios/<timestamp>/`; Phase 23 cross-client parity evidence is read from `.aegis/cross-client-parity/<timestamp>/`; Phase 24 release notes limitations evidence is read from `.aegis/release-notes-limitations/<timestamp>/`; Phase 25 Core/Website ownership evidence is read from `.aegis/core-website-ownership/<timestamp>/`; Phase 26 backend modularization evidence is read from `.aegis/backend-modularization/<timestamp>/`; Phase 27 frontend extraction evidence is read from `.aegis/frontend-extraction/<timestamp>/`; Phase 28 native desktop shell evidence is read from `.aegis/desktop-shell-hardening/<timestamp>/`; Phase 29 editor extension modularization evidence is read from `.aegis/editor-extension-modularization/<timestamp>/`; Phase 30 provider secret safety evidence is read from `.aegis/provider-secret-safety/<timestamp>/`; Phase 31 memory governance evidence is read from `.aegis/memory-governance/<timestamp>/`; Phase 32 plugin lifecycle evidence is read from `.aegis/plugin-lifecycle/<timestamp>/`; Phase 33 observability CI evidence is read from `.aegis/observability-ci/<timestamp>/`; Phase 34 distribution/update evidence is read from `.aegis/distribution-update/<timestamp>/`; Phase 35 alpha readiness polish evidence is read from `.aegis/alpha-readiness-polish/<timestamp>/`; Phase 36 live smoke RC scoping evidence is read from `.aegis/live-smoke-rc/<timestamp>/`; Phase 37 commit scoping and GitHub handoff evidence is read from `.aegis/commit-scoping-github-handoff/<timestamp>/`; Phase 38 desktop smoke and package gate evidence is read from `.aegis/desktop-smoke-package-gates/<timestamp>/`; Phase 39 editor smoke and release package decision evidence is read from `.aegis/editor-smoke-release-package-decision/<timestamp>/`.

## How To Use

1. Run focused contract checks while working on one phase.
2. Run `scripts\validate-ecosystem.ps1 -SkipSmoke` for a full release evidence folder.
3. Run `scripts\test-evidence-ledger-contract.ps1`.
4. Link the generated ledger summary from `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md`.
5. Keep broad external alpha blocked until live smoke, signing, installer, and worktree scope gaps are resolved.
