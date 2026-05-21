# Aegis Desktop 0.2.0 Release Notes

Generated: 2026-05-21

## Status

The Desktop package is a portable conditional private external alpha candidate. It is not a signed installer and is not ready for broad distribution.

Package:

```text
release/aegis-desktop-0.2.0-portable.zip
```

Checksum:

```text
331a7ee0c548644d483d39bc619c930dfaa8b0f83f382acd8dc5586201fd23dd
```

Size bytes: `1276809`

## Included

- Native desktop client for the local Aegis safe workflow.
- Core compatibility checks.
- Workspace scan, proposal/apply, validation, checkpoint, rollback, and diagnostics surfaces.
- Packaged scenario evidence and cross-client parity evidence.
- Release apply and rollback evidence through the shipped updater.

## Validation Evidence

- Release manifest evidence: `.aegis/final-release-manifest/20260521-062851/final-release-manifest-summary.md`
- Apply and rollback evidence: `.aegis/release-apply-rollback/20260521-062914/release-apply-rollback-summary.md`
- Cross-client parity: `.aegis/cross-client-parity/20260521-065519/cross-client-parity-summary.md`

## Checksums And Signing

The Desktop package must be verified against `release/version-manifest.json` before use.

This is an unsigned local build candidate. The unsigned local build limitation is acceptable only for conditional private external alpha.

## Known Limitations

- Desktop runtime smoke, desktop installer, and installer/update flows were not fully exercised.
- The package should be treated as portable and test-only.
- Cross-client parity is source-backed and package-aware, but live smoke gaps remain release-note limitations.
- Active worktree and commit grouping remain release-owner responsibilities before public publishing.

## Update And Rollback

Preview an update plan with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component desktop
```

Rollback with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Rollback
```

Recovery state is written to `.aegis/update-state.json`, `.aegis/safe-mode.json`, `.aegis/updates/backups`, and `.aegis/updates/downloads`.
