# Aegis Website 0.1.0 Release Notes

Generated: 2026-05-21

## Status

The Website package is part of the conditional private external alpha candidate. It is not a standalone broad-alpha release.

Package:

```text
release/aegis-website-0.1.0.zip
```

Checksum:

```text
9183dd9e5308f035847f302f8ad9711b656976f5fee0d90a5cc5afe9e29259ab
```

Size bytes: `12201239`

## Included

- Browser UI for the local Aegis workflow.
- Backend gateway for workspace scan, proposal, apply, validation, checkpoints, diagnostics, and release compatibility.
- Release compatibility route mirroring Core compatibility state.
- Redacted diagnostics and runtime settings export support.
- Package-backed scenario evidence and cross-client parity evidence.

## Validation Evidence

- Release manifest evidence: `.aegis/final-release-manifest/20260521-062851/final-release-manifest-summary.md`
- Packaged alpha scenarios: `.aegis/packaged-alpha-scenarios/20260521-064232/packaged-alpha-scenarios-summary.md`
- Cross-client parity: `.aegis/cross-client-parity/20260521-065519/cross-client-parity-summary.md`

## Checksums And Signing

The Website package must be verified against `release/version-manifest.json` before use.

This is an unsigned local build candidate. The unsigned local build limitation is acceptable only for conditional private external alpha.

## Known Limitations

- Live provider checks, local model checks, and Ollama/provider fallback checks were not rerun.
- Memory, provider routing, and autopilot controls need tester-visible reset and privacy affordances.
- Plugin/ecosystem install, trust, update, and rollback flows remain productization work.
- Active worktree and commit grouping remain release-owner responsibilities before public publishing.

## Update And Rollback

Preview an update plan with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component website
```

Rollback with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Rollback
```
