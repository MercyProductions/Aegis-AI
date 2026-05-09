# Aegis Local Agent 0.1.1 Release Notes

This release candidate packages Aegis Local Agent as a local-first VS Code extension for safe Ollama-assisted coding inside the currently opened workspace.

## Highlights

- Current-workspace project scanning and `.aegis/` project memory.
- Ollama model detection, model picker, default `qwen3-coder:30b`, and configured fallbacks.
- Sidebar command center with project overview, chat, actions, plans, diffs, validation output, memory links, settings, diagnostics, and error reporting.
- Agent workflow with planning, impact analysis, diff preview, approval, backups, validation, repair proposals, and rollback.
- Dependency graph and symbol index files for focused context and multi-file impact analysis.
- Health check, status bar states, extension logs, first-run setup, and recovery behavior.

## Install

```powershell
npm run package
code --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
```

## Recommended First Run

1. Start Ollama.
2. Open a project folder in VS Code.
3. Run `Aegis: Run First-Run Setup`.
4. Run `Aegis: Run Health Check`.
5. Generate a roadmap.
6. Try a small safe change and approve only after reviewing the diff.

## Safety Notes

Aegis does not rewrite projects automatically. It blocks secret and generated paths, writes backups before approved edits, keeps logs under `.aegis/`, and can roll back the latest agent change from its backup manifest.

## Known Limitations

- It uses lightweight indexing and validation detection, so review plans on large or unusual projects.
- It cannot guarantee architectural correctness; use the impact analysis and file-change reasons before approval.
- UI-only flows still require manual VS Code verification after CLI packaging tests.

## 0.1.1 Dogfooding Fixes

- `Aegis: Fix Build Errors` now runs detected validation first and stops when validation already passes.
- Failed validation output is included in the build-repair request so the model is grounded in the actual error.
- JSON parsing now handles UTF-8 BOM files, including Windows-created `package.json` files.
- Impact analysis filters non-file symbol placeholders so `.` no longer appears as a likely affected file.
- Workspace memory initialization now leaves damaged `.aegis` paths untouched, reports them, and continues in degraded mode.
- Later `.aegis` index, history, validation-log, decision-log, and recovery writes also skip damaged targets instead of interrupting scans or approved-change bookkeeping.
