# Aegis Local Agent for Visual Studio 0.1.1

This dogfooding build keeps the 0.1.0 feature set frozen and focuses on real-use reliability.

## What Changed Since 0.1.0

- Visual Studio is now a Core-first client for shared runtime workflows. Core handles client sync, workflow IDs, proposal records, Core apply, checkpoints, rollback, roadmap generation, workspace intelligence, validation records, and operation/job tracking when available.
- The extension keeps Visual Studio-native fallback logic for solution/project awareness, startup project detection, selected-code flows, context menu commands, Error List parsing, MSBuild output, local previews, and local safe-edit backups.
- The tool window now includes a Runtime Authority panel that shows Core connection, fallback mode, active workflow, pending proposal, latest checkpoint, latest validation result, and recent runtime operations.
- Apply and rollback prefer Core-owned checkpoints and operation jobs. Local rollback remains available for local-only fallback applies.
- Build validation keeps Visual Studio diagnostics, and records validation activity back to Core when Core is online.
- Repackaged the VSIX as version `0.1.1`.
- Disabled automatic scan on solution open by default for new installs, after dogfooding showed startup/open automation can be fragile on larger C++ and Unity-shaped solutions.
- Fixed command-table packaging so the Aegis menu commands have an embedded `Menus.ctmenu` resource.
- Hardened the release build script to stop on MSBuild errors and validate packaged manifest/resource consistency.
- Hardened solution memory reads and writes so damaged `.aegis` paths are skipped and reported through Health Check instead of crashing memory-backed workflows.
- Hardened rollback so backup manifests include explicit IDs and unsafe or incomplete rollback entries are skipped before solution files are touched.
- Hardened Ollama/Core diagnostics so secret-like HTTP error details are redacted before display.
- Hardened health-check, rollback, and command error diagnostics so user-visible exception details are redacted, with a build guard to prevent regression.
- Hardened authorization header redaction so `Authorization: Bearer/Basic/Digest ...` values cannot leave trailing credentials visible in diagnostics.
- Updated setup guidance so first-run indexing happens through health check, roadmap generation, or manual rescan.

## What Is Included

- Installable VSIX package for Visual Studio 2022 Community.
- Native Visual Studio tool window called **Aegis Local Agent**.
- Local Ollama model integration using `http://127.0.0.1:11434` by default.
- Default model: `qwen3-coder:30b`.
- Fallback models: `qwen2.5-coder:7b`, `granite-code:8b`.
- Solution-aware project scanning, symbol indexing, dependency mapping, roadmap generation, and persistent `.aegis/` memory.
- Approval-based safe edit workflow with backups, validation, bounded repair attempts, and rollback.
- Visual Studio settings page under **Tools > Options > Aegis Local Agent > General**.
- Health check command for solution state, `.aegis` writes, Ollama/model availability, backup creation, build integration, and index writing.

## External Alpha Status

This VSIX is part of the conditional private external alpha candidate. Broad external alpha remains blocked until live smoke, signing, installer, and worktree commit grouping decisions are complete.

Package evidence:

- Root package path: `release/AegisLocalAgentVs.vsix`
- SHA-256: `33bf11d7296e8d69415f1e9745a06c4f988668714c609a25e39b2d1cbc7f4529`
- Size bytes: `216454`
- Final release manifest: `.aegis/final-release-manifest/20260521-062851/final-release-manifest-summary.md`
- Packaged alpha scenarios: `.aegis/packaged-alpha-scenarios/20260521-064232/packaged-alpha-scenarios-summary.md`
- Cross-client parity: `.aegis/cross-client-parity/20260521-065519/cross-client-parity-summary.md`

Checksums are required and must match `release/version-manifest.json`.

This is an unsigned local build candidate. The unsigned local build limitation is accepted only for conditional private external alpha.

## Install

Close Visual Studio, then install:

```powershell
& "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\VSIXInstaller.exe" .\release\AegisLocalAgentVs.vsix
```

Restart Visual Studio after installation.

## Recommended Smoke Test

1. Open a C# solution.
2. Run `Aegis: Open Agent`.
3. Run `Aegis: Run Health Check`.
4. Send a short chat message.
5. Run `Aegis: Generate Solution Roadmap`.
6. Build the solution and verify build output appears in the Aegis tool window.
7. Generate a proposal on a disposable project or branch.
8. Verify preview/diff output appears before applying.
9. Apply only after review, then run rollback.
10. Repeat basic scan/open/health-check flow on one C++ solution and one Unity solution.

## Safety Notes

Aegis blocks `.env`, secret-looking files, private keys, `.vs/`, `bin/`, `obj/`, `packages/`, generated folders, and vendor folders. All edits require approval and write backups before changing files.

## Known Limitations

- Visual Studio UI workflows require manual validation inside the IDE.
- Visual Studio experimental-instance smoke still needs a fresh runtime pass.
- The proposal diff viewer is compact text output, not a full Visual Studio merge editor.
- Build/Error List data depends on Visual Studio automation APIs and the active IDE state.

## Update And Rollback

Preview an update plan:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Component visual-studio-extension
```

Rollback:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aegis-update.ps1 -Rollback
```
