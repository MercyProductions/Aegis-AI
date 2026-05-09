# Changelog

## 0.1.1 - Visual Studio Dogfooding Hardening

- Repackaged the Visual Studio extension after dogfooding install/open smoke tests.
- Changed the default `Auto Scan On Solution Open` setting to `false` for new installs, reducing startup friction on large C++, Unity, and multi-project solutions.
- Fixed VSCT command-resource packaging so Visual Studio can load the Aegis Tools menu and command table after VSIX install.
- Hardened `build.ps1` so MSBuild failures stop packaging and the generated VSIX is checked for matching manifest version plus embedded `Menus.ctmenu` resources.
- Hardened solution memory reads and writes so damaged `.aegis` paths degrade safely instead of crashing roadmap, context, build-log, or history workflows.
- Hardened rollback manifests with explicit backup IDs and rollback path validation so corrupted metadata cannot restore from ambiguous or escaped paths.
- Tightened rollback for shared backup locations so manifests from another solution, hidden/dot backup IDs, ambiguous newest-backup fallback, and traversal or secret-like proposed paths are rejected.
- Hardened Ollama/Core URL settings so host:port inputs, pasted endpoint paths, and invalid values normalize before model calls or shared Core registration.
- Updated install and troubleshooting documentation to make manual rescan the expected first-run indexing workflow.
- Added `DOGFOODING_NOTES.md` to track real-solution test coverage, observed issues, and remaining manual GUI gaps.

## 0.1.0 - Visual Studio Release Candidate

- Packaged Aegis Local Agent as a Visual Studio 2022 Community VSIX.
- Added the `Aegis Local Agent` tool window with solution overview, model status, chat, agent actions, active plan, proposal preview, validation output, rollback, and solution intelligence panels.
- Added Visual Studio Tools menu and Solution Explorer context menu commands for opening the agent, explaining files, reviewing code/projects, fixing build errors, generating roadmaps, continuing from roadmap, rescanning intelligence, and rollback.
- Added local Ollama integration with configurable URL, default model, fallback models, model detection, and health checks.
- Added native `Tools > Options > Aegis Local Agent > General` settings for Ollama, context size, safety mode, auto-scan, validation preference, and backup location.
- Added solution scanning for `.sln`, `.csproj`, `.vcxproj`, project references, packages, source files, tests, config files, README/TODO files, WPF XAML, C++ header/source pairs, and Unity project signals.
- Added persistent `.aegis/` memory: `solution-summary.md`, `architecture-map.md`, `roadmap.md`, `known-issues.md`, `decisions.md`, `build-log.md`, `agent-history.json`, `symbol-index.json`, and `dependency-map.json`.
- Added safe approval-based edits with blocked paths, compact diff preview, backups before apply, build validation, bounded repair attempts, and rollback.
- Added release documentation: `README.md`, `INSTALL.md`, `RELEASE_NOTES.md`, and `TROUBLESHOOTING.md`.

## Known RC Limitations

- The compact diff viewer is text-based inside the tool window.
- Visual Studio Error List and Build Output capture depends on what the active Visual Studio instance exposes through automation APIs.
- The model can still suggest incorrect code; review every proposed file edit before approving.
- Full GUI workflows must be smoke-tested manually inside Visual Studio after install.
