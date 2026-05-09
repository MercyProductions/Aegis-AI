# Changelog

## 0.1.1 - Post-Release Dogfooding

- Dogfooded the extension against a small Node sample, a medium React/Vite frontend, and a messy unfinished Electron/Vite workspace.
- Fixed `Aegis: Fix Build Errors` so it validates first and returns a no-op when there are no diagnostics and validation already passes.
- Improved build-repair grounding by passing actual validation failure output into Agent Mode.
- Fixed UTF-8 BOM JSON parsing so Windows-created `package.json` files still expose scripts, frameworks, and validation commands.
- Fixed impact analysis context selection so non-file placeholders such as `.` are not shown as likely affected files.
- Hardened `.aegis` memory initialization so damaged memory paths are logged and skipped instead of breaking startup scans.
- Hardened index, managed memory, recovery, validation-log, decision-log, and dogfooding-note writes so damaged `.aegis` targets do not break scans or post-apply bookkeeping.
- Hardened rollback manifest validation so corrupted backup IDs, mismatched workspace roots, or unsafe backup file paths cannot restore outside the current workspace backup folder.
- Tightened rollback backup ID validation to reject dot and hidden-folder aliases.
- Hardened rollback failure handling so missing or unreadable backup files are skipped with output details and manifest-level rollback failures show a clear error.
- Hardened Ollama/Core URL settings so host:port inputs, pasted endpoint paths, and invalid values normalize before model or shared-runtime requests.
- Hardened Core/Ollama URL normalization to preserve reverse-proxy path prefixes while trimming pasted endpoint paths.
- Hardened package lint with validation-command guard regressions so unsafe shell launchers, installs, chained commands, and destructive Git aliases cannot drift into the fallback validation runner.
- Hardened fallback validation detection so native-only Visual Studio solutions are no longer mislabeled as `dotnet build` workspaces; .NET project files still trigger `dotnet build`.
- Improved Unity local fallback snapshots so package manifests, package lockfiles, key `ProjectSettings` metadata, and assembly-definition files are treated as important context/build files.
- Hardened proposal path safety so Unity `Library` and `Temp` folders are blocked alongside `Logs` and other generated/dependency folders.
- Hardened secret proposal path safety for password, API-key, auth, SSH-key, and keystore-like filenames while avoiding false positives such as `tokenizer.py`.

## 0.1.0 - Release Candidate

- Added the Aegis Local Agent sidebar command center for the current VS Code workspace.
- Added Ollama backend support with local model detection, model picker, default `qwen3-coder:30b`, and fallbacks for `qwen2.5-coder:7b` and `granite-code:8b`.
- Added current-workspace and folder-scoped commands for chat, project explanation, current-file review, selected-code improvement, feature creation, roadmap generation, and continue-from-roadmap.
- Added Agent Mode with planning, impact analysis, staged diff previews, approval gates, backups, validation, repair proposals, and rollback.
- Added persistent `.aegis/` project memory, including project summary, architecture map, roadmap, decisions, known issues, validation log, agent history, file index, dependency graph, symbol index, logs, backups, and changed-file history.
- Added focused context selection so the model sees active files, related imports, tests, diagnostics, memory, and roadmap context instead of the full repository.
- Added health checks, status bar states, extension logs, model diagnostics, error reporting, retries, and recovery prompts after reload.
- Added package metadata, packaging scripts, install script, release folder, install guide, troubleshooting guide, and smoke-test checklist.
- Hardened prompts and UI defaults for small approval-based edits, reduced rescans with lightweight caching, and improved validation and proposal summaries for daily-driver use.
