# Release Apply Rollback Evidence

Phase 21 proves the shipped release updater can operate against packaged artifacts in a temporary install root. It does not apply packages to the developer workspace.

Machine-readable contract: `evals/phase21-release-apply-rollback-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-apply-rollback.ps1
```

Evidence output:

```text
.aegis/release-apply-rollback/<timestamp>/
```

## What It Checks

- The root `release/version-manifest.json` exists.
- The shipped `release/aegis-update.ps1` is present and uses exact install-root boundary checks.
- The root release folder is copied into `.aegis/release-apply-rollback/<timestamp>/install-root/`.
- Update plans produce `planned` states for Core, Website, Desktop, VS Code, and Visual Studio.
- Each component can apply from the copied release folder into the temporary install root.
- Each component records backup state, update state, package verification, and security audit entries.
- Rollback restores the previous target content and removes stray files left after the simulated update.
- A deliberately corrupted package fails checksum validation, records failed update state, and enables safe-mode recovery state.

## Current Status

The current status is ready when `scripts\test-release-apply-rollback.ps1` passes.

This clears the external-alpha rollback/update evidence requirement for the local unsigned build candidate. It does not clear packaged alpha scenario evidence, cross-client parity evidence, or final release notes evidence.
