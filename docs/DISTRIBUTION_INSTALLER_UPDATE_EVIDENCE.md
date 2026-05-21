# Distribution, Installer, Signing, And Auto-Update Evidence

Generated: 2026-05-21

Phase 34 records the current distribution decision for the controlled private alpha candidate. The project ships as checksummed portable ZIP packages plus VSIX packages for this phase. Signed installers remain a broad-release requirement, not a private-alpha claim.

Machine-readable contract: `evals/phase34-distribution-update-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-distribution-update.ps1
```

Evidence output:

```text
.aegis/distribution-update/<timestamp>/
```

## Current Distribution Decision

- Distribution mode: portable ZIP packages for Core, Website, and Desktop; VSIX packages for VS Code and Visual Studio.
- Installer status: deferred. A signed installer is required before broad release.
- Signing status: unsigned local build candidate. Checksums are mandatory for every package.
- Update status: non-mutating update plans must pass for every component before tester handoff.
- Recovery status: apply/rollback evidence must remain attached, with safe-mode and backup state available.
- Diagnostics support: Core diagnostics export is local-only, redacted, and manually attachable by testers.

## What It Checks

- `release/version-manifest.json` exists and matches real package files, SHA-256 values, and sizes.
- `VERSION.json` remains the source manifest and keeps checksum, backup, rollback, and safe-mode update policy requirements.
- `scripts\aegis-update.ps1` and shipped `release\aegis-update.ps1` retain checksum verification, signature policy handling, backup, rollback, safe mode, and security audit markers.
- Update plan dry-runs return `planned` for `aegis-core`, `website`, `desktop`, `vscode-extension`, and `visual-studio-extension`.
- Release packaging, final manifest, apply/rollback, release notes limitations, and observability CI evidence are attached.
- Core diagnostics export remains local-only and redacted through `/v1/alpha/diagnostics/export`.

## Release Boundary

This phase makes the current private-alpha package path auditable. It does not claim signed installer readiness. Broad distribution remains blocked until installer technology is selected, signing is configured, live smoke gates are refreshed, and the worktree is scoped for publishing.
