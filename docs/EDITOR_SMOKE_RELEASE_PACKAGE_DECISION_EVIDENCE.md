# Phase 39 Editor Smoke And Release Package Decision Evidence

Phase 39 turns the remaining editor/package skips into explicit evidence. It can run the VS Code extension-host smoke, classify extension-host failures, and keep Visual Studio/release package mutation scope tied to an owner decision instead of silently mutating release folders.

Machine-readable contract: `evals/phase39-editor-smoke-release-package-decision-contract.json`.

## Commands

Refresh the evidence without executing optional gates:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-editor-smoke-release-package-decision.ps1
```

Run the VS Code extension-host smoke:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-editor-smoke-release-package-decision.ps1 -AttemptVsCodeSmoke
```

Evidence is written to:

```text
.aegis/editor-smoke-release-package-decision/<timestamp>/
```

## Latest Evidence

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Phase 36 RC scoping: `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`
- Phase 37 handoff: `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- Phase 38 desktop smoke/package gates: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke/package decisions: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- Evidence ledger: `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`

## What The Evidence Proves

The Phase 39 evidence includes:

- `execution_status`
- `target_gate_observations` for `vscode-smoke`, `visual-studio-package`, `release-package-dry-run`, and `final-release-manifest-contract`
- `gate_attempts`
- `vscode_smoke_attempt`
- `package_gate_decisions`
- `owner_next_actions`
- `artifacts`
- `phase36_refresh_required`
- `phase37_refresh_required`
- `phase38_refresh_required`

Current execution status is `ready` for the first Phase 39 slice because `vscode-smoke` has been converted from skipped to retryable evidence with an attached log. Release status remains `attention` until the VS Code update mutex clears and the package mutation gates are closed or intentionally owner-blocked.

## Remaining Owner Decisions

- Run `vscode-smoke` without `-SkipSmoke` and attach extension-host log evidence.
- If VS Code smoke blocks, classify it as update mutex, dependency install, extension-host runtime, or UI readiness.
- Decide whether Visual Studio package mutation is intentional before running `visual-studio-package`.
- Decide whether release packaging and final manifest mutation are intentional before running `release-package-dry-run` or `final-release-manifest-contract`.
- Refresh Phase 36, Phase 37, Phase 38, and the evidence ledger after the next gate closes.
