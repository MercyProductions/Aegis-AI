# Known Unstable Surfaces

Generated: 2026-05-21

This file tracks the current alpha limitations that should be kept visible while the ChatBot project moves through the roadmap phases.

## Worktree And Release State

- The repo has a large active worktree with generated release artifacts, docs, scripts, and roadmap updates still needing commit grouping.
- Phase 37 commit scoping tracks the dirty worktree into explicit commit groups and keeps push blocked until the owner confirms the GitHub target and deleted asset decision.
- Conditional private external alpha is allowed only with Phase 24 release-note evidence attached. Broad external alpha is still blocked until live smoke, signing/installer, and worktree scope gaps are resolved.
- The root `release/version-manifest.json` has been generated from the intended artifact set, and `docs/RELEASE_ARTIFACT_DECISION.md` records the dirty release artifact decision.
- `VERSION.json`, `scripts/aegis-update.ps1`, and `scripts/build-release.ps1` are still release-critical files that should be reviewed before publishing or pushing.

## Validation Gaps

- VS Code extension-host smoke is currently blocked by a downloaded VS Code test instance holding the `vscode-updating` mutex.
- Visual Studio extension packaging and experimental-instance smoke were not rerun in the review pass.
- Native desktop Release x64 build and desktop runtime smoke pass, but installer/update flows were not exercised.
- Release package/update-plan, final root manifest, apply/rollback, packaged alpha scenario, cross-client parity, and release notes limitations evidence can be generated under `.aegis/release-package-dry-run`, `.aegis/final-release-manifest`, `.aegis/release-apply-rollback`, `.aegis/packaged-alpha-scenarios`, `.aegis/cross-client-parity`, and `.aegis/release-notes-limitations`; installer evidence still needs focused passes.
- Phase 36 live smoke RC scoping now has `desktop-smoke` and `update-plan-dry-run` closed; `vscode-smoke` is retryable due the `vscode-updating` mutex; release candidate status remains attention until that retryable gate clears and package mutation gates are closed or intentionally owner-blocked.
- Phase 38 desktop smoke/package gate execution has passed `desktop-smoke` with screenshots/log evidence and still tracks package gate mutation decisions plus owner next actions for `visual-studio-package`, `release-package-dry-run`, and `update-plan-dry-run`.
- Phase 39 editor smoke/release package decision execution converted `vscode-smoke` from skipped to retryable evidence and still tracks `visual-studio-package`, `release-package-dry-run`, and `final-release-manifest-contract` with release artifact decision and mutation scope notes.

## Architecture Risk

- Several files are still too large for comfortable ongoing feature work: `src/AegisChatApp.cpp`, `website/frontend/src/App.tsx`, `vscode-plugins/aegis-local-autopilot/extension.js`, `website/backend/aegis_ai/agent.py`, `website/backend/aegis_ai/storage.py`, and `aegis-core/aegis_core/contracts.py`.
- Core and Website ownership boundaries are still split for routing, storage, memory, validation, safe editing, and agent runtime behavior.
- Provider-account support needs a focused security and UX pass around secrets, local CLI bridge detection, cost/quota visibility, fallback routing, and health reporting.

## Product Readiness Gaps

- Phase 35 alpha readiness polish labels the default tester path as Stable Alpha, Beta, Experimental, and Internal Only, but broad alpha is still blocked by live smoke gaps, signing/installer decisions, worktree scope, and fresh provider/local model checks.
- Phase 36 release candidate scoping keeps `intentional_release_artifact_decision`, `worktree_scope_required`, `github_target_pending`, and `broad_alpha_blocked` visible before any GitHub push or broad alpha invite.
- Phase 37 commit scoping keeps `commit_groups`, `publish_blockers`, `deleted_asset_decision`, `github_target`, `no_blind_stage`, `release_artifact_separation`, and `handoff_status` visible before publish.
- Phase 38 keeps `execution_status`, `gate_attempts`, `desktop_smoke_attempt`, `package_gate_decisions`, `owner_next_actions`, `phase36_refresh_required`, and `phase37_refresh_required` visible while the remaining package/editor gates are closed.
- Phase 39 keeps `execution_status`, `gate_attempts`, `vscode_smoke_attempt`, `package_gate_decisions`, `owner_next_actions`, `phase36_refresh_required`, `phase37_refresh_required`, and `phase38_refresh_required` visible while editor smoke and package mutation decisions are closed.
- Live provider checks, local model checks, and Ollama/provider fallback checks were not run in the project review.
- Plugin/ecosystem behavior has broad scaffolding but still needs product-grade install, trust, update, and rollback flows.
- Memory, workspace intelligence, and autopilot behavior need clear user-facing controls for what is remembered, when it is used, and how to reset it.
- Cross-client parity evidence is now source-backed and package-aware for Website, native desktop, VS Code, and Visual Studio; live smoke gaps are carried in the Phase 24 release notes limitations evidence.
