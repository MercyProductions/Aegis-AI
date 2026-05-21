# Editor Extension Modularization Evidence

Generated: 2026-05-21

Phase 29 reduces editor-client risk by moving the VS Code Core envelope contract out of the monolithic `extension.js` orchestration path and into the shared `src/core/coreEnvelope.ts` module. The phase also records the Visual Studio package-validation substitute that covers command table, Core-first runtime, URL normalization, rollback safety, and diagnostic redaction guards without requiring an interactive Visual Studio smoke run.

Machine-readable contract: `evals/phase29-editor-extension-modularization-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-editor-extension-modularization.ps1
```

Evidence output:

```text
.aegis/editor-extension-modularization/<timestamp>/
```

## What It Checks

- `extension.js` imports and delegates to `src/core/coreEnvelope.ts` for envelope validation, `ok=false` handling, data extraction, and contract formatting.
- The old duplicate Core envelope helpers are no longer implemented inside `extension.js`.
- VS Code helper tests cover `requireCoreOk`, `formatCoreContract`, redaction, data extraction, and existing runtime state helpers.
- VS Code lint/package guards enforce the delegated helper boundary.
- Visual Studio `build.ps1 -ValidateOnly` remains the non-mutating package-validation substitute for editor smoke parity.

## Current Status

The required status is `ready` once the validator writes `editor-extension-modularization.json` and `editor-extension-modularization-summary.md` with no failed checks.

The live VS Code extension-host smoke remains an ecosystem gate, but this phase intentionally avoids depending on it because the test instance can be blocked by the VS Code update mutex.
