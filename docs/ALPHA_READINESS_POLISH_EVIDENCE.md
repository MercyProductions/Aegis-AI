# Alpha Readiness Polish Evidence

Generated: 2026-05-21

Phase 35 makes the private-alpha handoff intentional. It does not broaden the release. It labels the default tester path, keeps experimental and internal-only systems out of the normal flow, and verifies that onboarding, release notes, limitations, distribution evidence, and diagnostics all point to the same support posture.

Machine-readable contract: `evals/phase35-alpha-readiness-polish-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-alpha-readiness-polish.ps1
```

Evidence output:

```text
.aegis/alpha-readiness-polish/<timestamp>/
```

## Feature Labels

- Stable Alpha: visible by default. Core contracts, local workspace scan, checkpoints, validation, rollback, local model visibility, release compatibility, and diagnostics export.
- Beta: visible with label. Engineering Workspace, onboarding, quality gates, Core delegation fallback, client runtime surfaces, knowledge graph, and dogfooding feedback.
- Experimental: opt-in only. Advanced orchestration, engineering execution pipelines, deployment intelligence, system optimization experiments, personal intelligence, and real-time terminal orchestration.
- Internal Only: hidden from the tester path. Credential internals, unrestricted autonomy, raw mutation surfaces, internal dogfooding notes, and debug route experiments.

## Default Alpha Path

1. Verify package checksums against `release/version-manifest.json`.
2. Launch Aegis Core locally and check `/v1/health`.
3. Choose a disposable or backed-up workspace.
4. Keep local-only mode or complete provider setup through the credential store.
5. Confirm local model setup or show missing-model recovery.
6. Run the first workflow in validate-only mode.
7. Confirm checkpoint and rollback visibility before any mutation.
8. Export local redacted diagnostics when support is needed.
9. Capture friction through local alpha feedback.

## Broad Alpha Blockers

- The latest full validation matrix still has skipped live smoke/package gates.
- Signed installer and code-signing decisions are still deferred.
- The worktree still needs scoped commit grouping before publish.
- Live provider and local model health checks need a fresh pass.
- Client open-logs and diagnostics affordances need visible UI polish.

## Evidence Chain

This phase depends on ready or passed evidence from Phase 14 alpha readiness, Phase 24 release-note limitations, Phase 33 observability CI, and Phase 34 distribution/update. The ledger attaches Phase 35 evidence as another source, but the ledger remains `attention` until the skipped live smoke gates are closed.
