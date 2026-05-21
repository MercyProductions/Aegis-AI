# Phase 38 Desktop Smoke And Package Gate Evidence

Generated: 2026-05-21

Phase 38 turns the remaining runtime and package skips into explicit evidence. It can run the desktop smoke with isolated app data, classify runtime failures, and record package gate decisions without silently mutating release folders.

Machine-readable contract: `evals/phase38-desktop-smoke-package-gates-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-desktop-smoke-package-gates.ps1
```

Desktop smoke attempt command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-desktop-smoke-package-gates.ps1 -AttemptDesktopSmoke
```

Evidence output:

```text
.aegis/desktop-smoke-package-gates/<timestamp>/
```

Latest generated evidence:

- Release validation: `.aegis/release-evidence/20260521-110934/validation-summary.md`
- Phase 36 RC scoping: `.aegis/live-smoke-rc/20260521-111524/live-smoke-rc-summary.md`
- Phase 37 handoff: `.aegis/commit-scoping-github-handoff/20260521-111528/commit-scoping-github-handoff-summary.md`
- Phase 38 desktop smoke/package gates: `.aegis/desktop-smoke-package-gates/20260521-111533/desktop-smoke-package-gates-summary.md`
- Phase 39 editor smoke/package decisions: `.aegis/editor-smoke-release-package-decision/20260521-111548/editor-smoke-release-package-decision-summary.md`
- Evidence ledger: `.aegis/evidence-ledger/20260521-111627/evidence-ledger-summary.md`

## Scope

The Phase 38 evidence includes:

- `target_gate_observations` for `desktop-smoke`, `visual-studio-package`, `release-package-dry-run`, `final-release-manifest-contract`, and `update-plan-dry-run`
- `gate_attempts` for any runtime or package command executed by the phase script
- `desktop_smoke_attempt` status, screenshots/log evidence path, and failure classification
- `package_gate_decisions` for package gates that mutate release folders or need an explicit artifact decision
- `owner_next_actions` for each gate still not closed
- `phase36_refresh_required` and `phase37_refresh_required` flags after any new runtime/package evidence

## Current Execution Decision

Current execution status is `ready` for the first Phase 38 slice because `desktop-smoke` has passed with screenshots/log evidence. Release status remains `attention` until the remaining skipped editor/package gates are either executed or intentionally classified.

Package mutation remains decision-sensitive:

- `visual-studio-package` mutates extension release artifacts and needs an explicit release-artifact decision.
- `release-package-dry-run` should write under evidence output unless root release mutation is intentionally approved.
- `final-release-manifest-contract` mutates the root release folder and should remain gated.
- `update-plan-dry-run` can run from the current manifest, but any package refresh should be tied to the matching manifest evidence.

## Owner Next Actions

- Run `desktop-smoke` with isolated app data and attach screenshots/log evidence.
- If desktop smoke blocks, classify it as environment, package, backend, or UI startup.
- Decide whether Visual Studio package and root release package mutation are intentional.
- Refresh Phase 36 live smoke RC scoping after the runtime/package pass.
- Refresh Phase 37 GitHub handoff after Phase 36 has the new gate status.
