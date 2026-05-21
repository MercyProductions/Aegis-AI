# Phase 37 Commit Scoping And GitHub Handoff Evidence

Generated: 2026-05-21

Phase 37 makes the dirty worktree reviewable before any GitHub push. It does not push, stage, commit, delete, or restore files. It inventories the current status, groups paths into commit-sized buckets, flags publish blockers, and records the detected GitHub remote for handoff.

Machine-readable contract: `evals/phase37-commit-scoping-github-handoff-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-commit-scoping-github-handoff.ps1
```

Evidence output:

```text
.aegis/commit-scoping-github-handoff/<timestamp>/
```

Latest generated evidence:

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Phase 37 handoff: `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- Phase 38 desktop smoke/package gates: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke/package decisions: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- Evidence ledger: `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`

## Scope

The Phase 37 evidence includes:

- `commit_groups` for roadmaps/docs, validation contracts/scripts, Core runtime, Website backend, Website frontend, native desktop, VS Code extension, Visual Studio extension, release/update artifacts, and design or miscellaneous assets
- `publish_blockers` for dirty worktree scope, deleted asset decision, GitHub target confirmation, and open release-candidate gates
- `deleted_asset_decision` for `website inspiration.png`
- `github_target` detection from `origin`
- `no_blind_stage` policy so publish work uses explicit file lists and never `git add -A`
- `release_artifact_separation` so generated packages and evidence are reviewed separately from source changes
- `handoff_status`, which remains `attention` until the deleted asset decision, target confirmation, and scoped commits are resolved

## Current Handoff Decision

Current handoff status is `attention`.

Reasons:

- the worktree contains 279 modified, deleted, and untracked paths across multiple product areas
- the deleted `website inspiration.png` file needs an owner decision before publish
- the detected remote is `https://github.com/MercyProductions/Aegis-AI.git`, but the target still needs user confirmation before push
- release artifact folders and generated package files should be reviewed as their own scope
- Phase 36 release candidate status is still `attention` while live smoke and package gates remain open

## Commit Group Policy

Use explicit file lists for each commit group:

1. `roadmaps_and_docs`
2. `evidence_contracts_and_validation`
3. `aegis_core_runtime`
4. `website_backend`
5. `website_frontend`
6. `native_desktop`
7. `vscode_extension`
8. `visual_studio_extension`
9. `release_update_artifacts`
10. `design_assets_and_misc`

Do not use a broad `git add -A` for this worktree. The repository has unrelated surfaces in flight, and a blind stage would make review and rollback painful.

## Push Boundary

Detected remote:

```text
https://github.com/MercyProductions/Aegis-AI.git
```

Expected target:

```text
MercyProductions/Aegis-AI
```

Push remains blocked until the user confirms this target and the commit groups are staged intentionally.
