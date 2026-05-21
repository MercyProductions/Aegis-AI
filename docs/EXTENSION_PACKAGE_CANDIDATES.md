# Extension Package Candidates

Phase 18 turns the extension package candidates from missing blockers into explicit evidence. It verifies that the VS Code and Visual Studio VSIX files exist where `VERSION.json` and `scripts\build-release.ps1` expect them, and that release-facing extension docs are present.

Machine-readable contract: `evals/phase18-extension-package-candidates-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-extension-package-candidates.ps1
```

Evidence output:

```text
.aegis/extension-package-candidates/<timestamp>/
```

When this gate runs inside `scripts\validate-ecosystem.ps1`, its output is nested under the current `.aegis/release-evidence/<timestamp>/extension-package-candidates/` folder.

## Current Candidate Artifacts

- `vscode-plugins/aegis-local-autopilot/release/aegis-local-autopilot-0.1.8.vsix`
- `visual-studio-extensions/aegis-local-agent-vs/release/AegisLocalAgentVs.vsix`

## Validation Commands

VS Code:

```powershell
cd vscode-plugins\aegis-local-autopilot
npm run lint
npm run test:unit
npm run package
```

Visual Studio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File visual-studio-extensions\aegis-local-agent-vs\build.ps1 -ValidateOnly
powershell -NoProfile -ExecutionPolicy Bypass -File visual-studio-extensions\aegis-local-agent-vs\build.ps1
```

These candidates do not by themselves make the release ready. Release packaging still needs `release/version-manifest.json`, final checksum and size stamping, update-plan dry-run evidence, packaged scenario evidence, and cross-client parity evidence.
