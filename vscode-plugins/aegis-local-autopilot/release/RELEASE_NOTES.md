# Auralith OS Local Agent 0.1.8 Release Notes

This package is the VS Code client candidate for the local-first Auralith OS/Aegis workspace agent.

## Highlights

- VS Code activity-bar panel for local agent workflows.
- Core-aware client registration and compatibility checks.
- Workspace scanning, project memory, roadmap generation, proposal preview, validation detection, and rollback support.
- Package lint and unit helper checks before VSIX creation.
- Local model defaults for Ollama with explicit fallback model configuration.

## Package

```text
release/aegis-local-autopilot-0.1.8.vsix
```

## Validation

Run from `vscode-plugins\aegis-local-autopilot`:

```powershell
npm run lint
npm run test:unit
npm run package
```

## External Alpha Status

This VSIX is part of the conditional private external alpha candidate. Broad external alpha remains blocked until live smoke, signing, installer, and worktree commit grouping decisions are complete.

Package evidence:

- Root package path: `release/aegis-local-autopilot-0.1.8.vsix`
- SHA-256: `13394f306497687afa299d677973cb0b87cf7fc4b7f53550cbc173aaef24705f`
- Size bytes: `998347`
- Final release manifest: `.aegis/final-release-manifest/20260521-062851/final-release-manifest-summary.md`
- Packaged alpha scenarios: `.aegis/packaged-alpha-scenarios/20260521-064232/packaged-alpha-scenarios-summary.md`
- Cross-client parity: `.aegis/cross-client-parity/20260521-065519/cross-client-parity-summary.md`

Checksums are required and must match `release/version-manifest.json`.

This is an unsigned local build candidate. The unsigned local build limitation is accepted only for conditional private external alpha.

## Known Limitations

- VS Code extension-host smoke can be blocked by a VS Code update mutex or `vscode-updating` mutex.
- Core offline, Ollama offline, missing model, missing provider, and validation failure paths must stay visible to testers.
- The package should be tested against real workspaces before broad external use.
- Cross-client parity evidence is source-backed and package-aware, but live editor smoke still needs a clean retry before broad alpha.

## Update And Rollback

Preview an update plan:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component vscode-extension
```

Rollback:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Rollback
```
