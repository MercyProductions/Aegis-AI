# Cross-Client Parity Evidence

Phase 23 proves that Website, native Desktop, VS Code, and Visual Studio all expose the same safe alpha workflow from source and packaged release evidence.

Machine-readable contract: `evals/phase23-cross-client-parity-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-cross-client-parity.ps1
```

Evidence output:

```text
.aegis/cross-client-parity/<timestamp>/
```

## Workflow

The parity contract checks the same representative workflow in every client:

- workspace scan or open
- model route selection
- proposal or review
- approved apply path
- validation
- checkpoint
- rollback or restore
- diagnostics export or redacted diagnostics visibility
- release compatibility status

## Evidence Model

This is source-backed and package-aware parity evidence. It does not claim that every interactive smoke test has been rerun.

The validator reads the root `release/version-manifest.json`, verifies all five packages are present and match their SHA-256 hashes, attaches the latest Phase 20, Phase 21, and Phase 22 evidence, then inspects the client source files for the workflow capabilities above.

## Current Limitations

- VS Code extension-host smoke can still be blocked by the VS Code update mutex.
- Visual Studio experimental-instance smoke still needs a dedicated runtime pass.
- Desktop installer/update smoke is separate from this source-backed parity contract.

Those limitations remain release-note items until the final alpha release notes are attached.
