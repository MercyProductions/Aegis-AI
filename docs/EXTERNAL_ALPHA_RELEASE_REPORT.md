# External Alpha Release Report

Current decision: Conditional private external alpha

Status: conditional

This report is the single external-alpha decision record. It does not replace the validation matrix or release notes. It collects their evidence and keeps the alpha decision honest while the packaged build, update path, rollback path, cross-client workflow, and known limitations are visible to testers.

Machine-readable contract: `evals/phase15-external-alpha-release-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-external-alpha-contract.ps1
```

Evidence output:

```text
.aegis/external-alpha-evidence/<timestamp>/
```

## Go/No-Go Summary

The current release can be invited only into a narrow, trusted, private external alpha cohort. It should not be invited into broad external alpha.

Hard blockers:

- `release_artifact_matrix`: root release packages and `release/version-manifest.json` now have Phase 20 checksum, size, and unsigned-build disclosure evidence attached to release notes.
- `ecosystem_validation_evidence`: a fresh `.aegis/release-evidence/<timestamp>/validation-matrix.json` must be attached to this report.
- `alpha_scenario_suite_evidence`: Phase 22 packaged scenario evidence now exists; keep the generated summary attached and carry its limitations into release notes.
- `cross_client_parity_evidence`: Phase 23 source-backed, package-aware parity evidence now exists for Website, Desktop, VS Code, and Visual Studio; keep the generated summary attached and carry remaining runtime smoke limitations into release notes.
- `rollback_update_dry_run`: package, update-plan, and Phase 21 apply/rollback evidence now exist for the local unsigned build candidate; keep this evidence attached to the release notes.
- `known_limitations_release_notes`: Phase 24 release notes now include the current known limitations from `KNOWN_UNSTABLE_SURFACES.md`.
- `signing_checksum_disclosure`: checksums are required, and any unsigned-build limitation must be explicit.

Promotion beyond conditional requires live smoke gaps, signing/installer decisions, and worktree commit grouping to be resolved or narrowed further with owner approval.

Phase 36 release-candidate scoping is tracked in `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`. Its `release_candidate_status` remains `attention` until `vscode-smoke`, `visual-studio-package`, and release-package mutation gates are closed in fresh release validation evidence.

Phase 37 commit scoping and GitHub handoff is tracked in `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`. Its `handoff_status` remains `attention` until commit groups are staged intentionally, `website inspiration.png` has an owner decision, and the GitHub target is confirmed.

Phase 38 desktop smoke and package gate execution is tracked in `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`. Its `execution_status` is `ready` for the desktop-smoke slice; release status remains `attention` until the remaining editor/package skips are closed or intentionally classified.

Phase 39 editor smoke and release package decision execution is tracked in `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`. Its first target, `vscode-smoke`, is retryable because the VS Code test instance still holds the `vscode-updating` mutex; package mutation gates remain decision-sensitive until the release owner approves mutation scope.

## Evidence Index

Required evidence sources:

- `.aegis/release-evidence/<timestamp>/validation-summary.md`
- `.aegis/release-evidence/<timestamp>/validation-matrix.json`
- `.aegis/release-evidence/<timestamp>/release-artifact-status.txt`
- `.aegis/release-preflight/<timestamp>/release-artifact-preflight-summary.md`
- `.aegis/release-package-dry-run/<timestamp>/release-package-dry-run-summary.md`
- `.aegis/final-release-manifest/<timestamp>/final-release-manifest-summary.md`
- `.aegis/release-apply-rollback/<timestamp>/release-apply-rollback-summary.md`
- `.aegis/packaged-alpha-scenarios/<timestamp>/packaged-alpha-scenarios-summary.md`
- `.aegis/cross-client-parity/<timestamp>/cross-client-parity-summary.md`
- `.aegis/release-notes-limitations/<timestamp>/release-notes-limitations-summary.md`
- `.aegis/live-smoke-rc/<timestamp>/live-smoke-rc-summary.md`
- `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- `.aegis/extension-package-candidates/<timestamp>/extension-package-candidates-summary.md`
- `.aegis/alpha-evidence/<timestamp>/alpha-contract-summary.md`
- `.aegis/external-alpha-evidence/<timestamp>/external-alpha-contract-summary.md`
- `.aegis/evidence-ledger/<timestamp>/evidence-ledger-summary.md`
- `VERSION.json`
- `release/version-manifest.json`
- `docs/RELEASE_ARTIFACT_DECISION.md`
- `KNOWN_UNSTABLE_SURFACES.md`
- `docs/EVIDENCE_LEDGER.md`
- `docs/CONTROLLED_EXTERNAL_ALPHA.md`
- `docs/RELEASE_ARTIFACT_PREFLIGHT.md`
- `docs/RELEASE_PACKAGE_DRY_RUN.md`
- `docs/RELEASE_APPLY_ROLLBACK_EVIDENCE.md`
- `docs/PACKAGED_ALPHA_SCENARIO_EVIDENCE.md`
- `docs/CROSS_CLIENT_PARITY_EVIDENCE.md`
- `docs/RELEASE_NOTES_LIMITATIONS_EVIDENCE.md`
- `docs/DESKTOP_SMOKE_PACKAGE_GATES_EVIDENCE.md`
- `docs/EXTERNAL_ALPHA_RELEASE_NOTES.md`
- `docs/WEBSITE_RELEASE_NOTES.md`
- `docs/DESKTOP_RELEASE_NOTES.md`
- `docs/EXTENSION_PACKAGE_CANDIDATES.md`
- `docs/RELEASE_PACKAGING_AND_UPDATES.md`

## Release Artifact Matrix

| Component | Required Artifact | Required Evidence | Current State |
| --- | --- | --- | --- |
| `aegis-core` | `aegis-core-<version>.zip` | version, checksum, size, compatibility | Phase 20 final manifest and Phase 22 packaged scenario evidence attached. |
| `website` | `aegis-website-<version>.zip` | version, checksum, size, compatibility | Phase 20 final manifest and Phase 22 packaged scenario evidence attached. |
| `desktop` | `aegis-desktop-<version>-portable.zip` or installer | version, checksum, size, compatibility, signing status | Phase 20 final manifest evidence and Phase 38 desktop smoke evidence attached; installer/update smoke still needs evidence. |
| `vscode-extension` | `aegis-local-autopilot-<version>.vsix` | version, checksum, size, compatibility | Phase 20 final manifest evidence attached; extension-host smoke still needs fresh evidence. |
| `visual-studio-extension` | `AegisLocalAgentVs.vsix` | version, checksum, size, compatibility | Phase 20 final manifest evidence attached; experimental-instance smoke still needs fresh evidence. |

## Validation Matrix

Required gate evidence comes from `scripts/validate-ecosystem.ps1`:

- `core-tests`
- `website-backend-tests`
- `website-frontend-tests`
- `website-frontend-build`
- `desktop-contract`
- `release-contract`
- `release-artifact-preflight`
- `extension-package-candidates`
- `release-package-dry-run-contract`
- `final-release-manifest-contract`
- `release-apply-rollback-contract`
- `packaged-alpha-scenarios-contract`
- `cross-client-parity-contract`
- `release-notes-limitations-contract`
- `quality-contract`
- `plugin-contract`
- `alpha-contract`
- `external-alpha-contract`
- `desktop-release-build`
- `vscode-unit`
- `vscode-lint`
- `editor-parity`
- `visual-studio-validate`
- `release-package-dry-run`
- `update-plan-dry-run`
- `live-smoke-rc-contract`
- `commit-scoping-github-handoff-contract`
- `desktop-smoke-package-gates-contract`
- `editor-smoke-release-package-decision-contract`

Skipped and retryable gates can support a narrow private dogfood build, but they cannot support broad external alpha without an explicit limitation, owner, and retry date.

## Alpha Scenario Suite

| Scenario | Required Evidence | Current State |
| --- | --- | --- |
| `create_app` | Packaged app creates a small app with checkpoint and validation evidence. | Phase 22 package-backed evidence attached. |
| `modify_app` | Existing app change shows proposal, diff, validation, and rollback. | Phase 22 package-backed evidence attached. |
| `repair_validation` | Validation failure produces one bounded repair attempt and revalidation. | Phase 22 package-backed evidence attached. |
| `review_code` | Review mode reports findings without writing files. | Phase 22 package-backed evidence attached. |
| `connect_provider` | Provider route avoids plaintext secret export and shows key recovery. | Phase 22 package-backed evidence attached, including packaged text secret-marker scan. |
| `use_local_model` | Local-only routing works or shows missing-model recovery. | Phase 22 package-backed evidence attached. |
| `run_vscode_extension` | VS Code extension runs the safe workflow through Core or documented fallback. | Phase 22 package evidence and Phase 23 parity evidence attached; extension-host smoke remains a runtime limitation. |
| `run_visual_studio_extension` | Visual Studio extension validates Core contract behavior or package validation. | Phase 22 package evidence and Phase 23 parity evidence attached; experimental-instance smoke remains a runtime limitation. |
| `update_component` | Component update plan shows compatibility and validation evidence. | Phase 22 attaches Phase 21 packaged update evidence. |
| `rollback_component` | Checkpoint or update rollback records a clear result. | Phase 22 attaches Phase 21 packaged rollback evidence. |

## Known Issues And Limitations

Known limitations have been copied into `docs/EXTERNAL_ALPHA_RELEASE_NOTES.md` and component release notes before any external tester invite:

- Worktree commit grouping is still decision-sensitive.
- Root release manifest, artifact decision, apply/rollback evidence, packaged scenario evidence, cross-client parity evidence, checksum status, and unsigned-build status are attached to release notes.
- VS Code extension-host smoke can be blocked by the VS Code update mutex.
- Visual Studio packaging and experimental-instance smoke need fresh evidence.
- Desktop runtime smoke passed in Phase 38; installer and update flows still need fresh evidence.
- Phase 38 desktop smoke/package gates have attached desktop-smoke execution evidence; package mutation decisions remain open.
- Phase 39 editor smoke/release package decision evidence has attached retryable VS Code smoke evidence; package mutation decisions remain open.
- Cross-client parity evidence exists from Phase 23 source/package validation; live client smoke gaps remain visible in release notes.
- Plugin/ecosystem install, trust, update, and rollback flows remain productization work.
- Memory, provider routing, and autopilot controls need tester-visible reset and privacy affordances.

Source of truth: `KNOWN_UNSTABLE_SURFACES.md`.

## Recovery And Rollback

External alpha release notes now include:

- how to run `scripts\aegis-update.ps1 -Component desktop`
- how to run `scripts\aegis-update.ps1 -Rollback`
- where `.aegis/update-state.json`, `.aegis/safe-mode.json`, `.aegis/updates/backups`, and `.aegis/updates/downloads` are written
- checksum requirement status
- signing status or unsigned-build limitation

Phase 24 release notes evidence is attached at `.aegis/release-notes-limitations/20260521-071150/release-notes-limitations-summary.md`.

## Cross-Client Parity

Phase 23 parity evidence is attached at `.aegis/cross-client-parity/<timestamp>/cross-client-parity-summary.md`.

The source-backed and package-aware parity run verifies the same workflow capability set in:

- Website
- Desktop
- VS Code
- Visual Studio

The checked workflow is workspace scan, model route, proposal or review, approved apply, validation, checkpoint, rollback or restore, diagnostics export, and release compatibility. This clears the parity-evidence blocker, but it does not replace the remaining VS Code extension-host, Visual Studio experimental-instance, or desktop installer/update smoke limitations.

## Decision Log

| Date | Decision | Evidence |
| --- | --- | --- |
| 2026-05-21 | No-go: external alpha report structure exists, but packaged artifact and scenario evidence are missing. | Phase 15 contract and this report. |
| 2026-05-21 | No-go maintained: root release manifest and artifact decision evidence exist; rollback/apply, alpha scenario, parity, and final release-note evidence are still missing. | Phase 20 final manifest contract and this report. |
| 2026-05-21 | No-go maintained: release apply/rollback evidence exists; packaged alpha scenario, parity, and final release-note evidence are still missing. | Phase 21 release apply rollback contract and this report. |
| 2026-05-21 | No-go maintained: packaged alpha scenario evidence exists; cross-client parity and final release-note evidence are still missing. | Phase 22 packaged alpha scenario contract and this report. |
| 2026-05-21 | No-go maintained: cross-client parity evidence exists; final release-note evidence is still missing. | Phase 23 cross-client parity contract and this report. |
| 2026-05-21 | Conditional private external alpha: final release notes and limitations evidence exists; broad alpha remains blocked on live smoke, signing/installer, and worktree scope gaps. | Phase 24 release notes limitations contract and this report. |
| 2026-05-21 | Conditional private external alpha maintained: Phase 36 release-candidate scoping exists, but release_candidate_status remains attention until live smoke and package gates close. | Phase 36 live smoke RC scoping contract and this report. |
| 2026-05-21 | Conditional private external alpha maintained: Phase 37 commit scoping exists, but handoff_status remains attention until publish target, deleted asset, and commit groups are resolved. | Phase 37 commit scoping GitHub handoff contract and this report. |
| 2026-05-21 | Conditional private external alpha maintained: Phase 38 desktop smoke/package gate evidence closes `desktop-smoke`, but package mutation gates and editor smoke remain attention. | Phase 38 desktop smoke package gates contract and this report. |
| 2026-05-21 | Phase 39 opened to close editor smoke first and keep release package mutation under explicit owner decision. | Phase 39 editor smoke release package decision contract and this report. |
| 2026-05-21 | Phase 39 first slice completed: `vscode-smoke` is retryable due the `vscode-updating` mutex; package mutation gates remain decision-sensitive. | `.aegis/editor-smoke-release-package-decision/20260521-111548/` and `.aegis/release-evidence/20260521-110934/`. |
