# Aegis Local Agent for Visual Studio 0.1.1

This dogfooding build keeps the 0.1.0 feature set frozen and focuses on real-use reliability.

## What Changed Since 0.1.0

- Repackaged the VSIX as version `0.1.1`.
- Disabled automatic scan on solution open by default for new installs, after dogfooding showed startup/open automation can be fragile on larger C++ and Unity-shaped solutions.
- Fixed command-table packaging so the Aegis menu commands have an embedded `Menus.ctmenu` resource.
- Hardened the release build script to stop on MSBuild errors and validate packaged manifest/resource consistency.
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
- The proposal diff viewer is compact text output, not a full Visual Studio merge editor.
- Build/Error List data depends on Visual Studio automation APIs and the active IDE state.
