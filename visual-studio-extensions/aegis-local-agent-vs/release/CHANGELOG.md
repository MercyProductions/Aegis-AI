# Changelog

## 0.1.1 - Visual Studio Dogfooding Hardening

- Repackaged the Visual Studio extension after dogfooding install/open smoke tests.
- Replaced localhost VSIX MoreInfo metadata with the GitHub repository URL.
- Removed internal dogfooding notes from the packaged VSIX archive.
- Changed the default `Auto Scan On Solution Open` setting to `false` for new installs, reducing startup friction on large C++, Unity, and multi-project solutions.
- Fixed VSCT command-resource packaging so Visual Studio can load the Aegis Tools menu and command table after VSIX install.
- Hardened `build.ps1` so MSBuild failures stop packaging and the generated VSIX is checked for matching manifest version plus embedded `Menus.ctmenu` resources.
- Hardened `build.ps1` to reject localhost placeholder metadata and internal note/model-inventory files in packaged VSIX archives.
- Hardened `build.ps1` release-folder cleanup so stale internal dogfooding notes, detected-model inventories, and repository-only `.gitignore` files are removed before packaging.
- Hardened release bundling so distributable documentation sources are validated and `LICENSE.txt` is copied beside the packaged VSIX.
- Added `build.ps1 -ValidateOnly` for fast package/safety guard checks without requiring a full VSIX build.
- Hardened solution memory reads and writes so damaged `.aegis` paths degrade safely instead of crashing roadmap, context, build-log, or history workflows.
- Hardened rollback manifests with explicit backup IDs and rollback path validation so corrupted metadata cannot restore from ambiguous or escaped paths.
- Hardened rollback resolution so the manifest `backupId` is required and `createdAt` can no longer be used as a fallback backup folder selector.
- Tightened rollback for shared backup locations so manifests from another solution, hidden/dot backup IDs, ambiguous newest-backup fallback, and traversal or secret-like proposed paths are rejected.
- Hardened Ollama/Core URL settings so host:port inputs, pasted endpoint paths, and invalid values normalize before model calls or shared Core registration.
- Hardened Core/Ollama URL normalization to preserve reverse-proxy path prefixes while trimming pasted endpoint paths.
- Hardened Ollama/Core diagnostic details so HTTP errors redact query-string keys, bearer tokens, URL credentials, and assignment-style secrets before they are shown in Visual Studio.
- Hardened health-check, rollback, and command error diagnostics so user-visible exception details are redacted, and packaging now fails if those paths drift back to raw exception messages.
- Hardened authorization header redaction so `Authorization: Bearer/Basic/Digest ...` values cannot leave trailing credentials visible in diagnostics.
- Hardened Aegis Core contract mismatch diagnostics so unexpected `api_version` and `kind` values are redacted, and packaging now fails if those paths drift back to raw values.
- Improved solution scanning and smart context indexing for `.fsproj`, `.vbproj`, `.slnx`, F#/Visual Basic symbols/imports, Visual Basic XAML code-behind, and newer C++ source/header suffixes.
- Fixed solution scanning so NuGet `packages.lock.json` is treated as important dependency metadata, and package validation now rejects the invalid `packages-lock.json` typo.
- Hardened solution scanning and smart context secret filters for password, API-key, auth, SSH-key, and keystore-like filenames while preserving ordinary source names such as `tokenizer.py`.
- Updated install and troubleshooting documentation to make manual rescan the expected first-run indexing workflow.
- Kept `DOGFOODING_NOTES.md` in the source tree to track real-solution test coverage, observed issues, and remaining manual GUI gaps.

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
