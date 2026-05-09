# Aegis Local Agent

Local-first coding-agent command center for the folder currently opened in VS Code. It uses Ollama on `127.0.0.1:11434`, scans the active workspace, proposes safe changes, waits for approval, applies approved edits with backups, runs validation, and can propose repairs when validation fails.

## Requirements

- VS Code
- Node.js and npm for packaging/installing this extension
- Ollama running locally at `http://127.0.0.1:11434`
- Optional shared Aegis Core runtime at `http://127.0.0.1:8788`
- Recommended model installed:

```powershell
ollama pull qwen3-coder:30b
```

Fallback models:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## Build And Package

From this extension folder:

```powershell
npm run compile
npm run lint
npm run package
```

The packaged extension is created at:

```text
release/aegis-local-autopilot-0.1.1.vsix
```

## Install

From this extension folder:

```powershell
npm run install-local
```

That compiles, lints, packages a `.vsix`, and installs it into VS Code.

Manual VSIX install:

```powershell
code --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
```

You can also install through VS Code's Extensions view by choosing **Install from VSIX...** and selecting the file in `release/`.

For development, open this extension folder in VS Code and press `F5` to launch an Extension Development Host.

## First Run Setup

On first launch, Aegis runs a setup flow that:

- checks whether Ollama is reachable
- detects installed models
- asks you to choose the default model
- creates `.aegis/` for the current workspace when one is open
- runs the health check
- opens a setup checklist

Run `Aegis: Run First-Run Setup` to repeat this flow.

## Aegis Core Sync

When Aegis Core is running, the VS Code extension registers itself through `/v1/clients/register`, includes Core in health checks, and creates shared task records during Agent Mode. Those tasks are visible to the Desktop App ecosystem dashboard and other Auralith clients that point at the same workspace.

Set `aegisLocalAutopilot.coreUrl` if Core is not running on `http://127.0.0.1:8788`. If Core is offline, VS Code stays usable in degraded local mode.

Project-local `.aegis/` memory writes are best-effort. If a memory target is damaged, Aegis reports it in the output channel and keeps scans, recovery state, validation logs, decisions, and approved-change bookkeeping from crashing the workflow.

## Update And Uninstall

Update by rebuilding and reinstalling:

```powershell
npm run install-local
```

Uninstall:

```powershell
code --uninstall-extension aegis.aegis-local-autopilot
```

## Current Workspace Mode

Aegis uses the currently opened VS Code workspace folder as the default project context. If an editor file is active, it uses that file's workspace folder. If you right-click a folder in Explorer, Aegis scopes the task to that selected folder. If no folder is open, it shows a warning and does nothing.

The scanner gathers:

- top-level structure
- detected languages and frameworks
- README, TODO, package, build, and config files
- test files
- likely entry points
- recent modification dates
- likely build/test commands
- TODO/FIXME snippets
- current VS Code diagnostics
- recent local proposal history

Generated edit paths are always relative to the selected/current project folder.

## Supported Project Types

Aegis is currently tuned for:

- React/Vite and package-based frontend projects
- package-based Node workspaces
- Python/FastAPI-style projects
- C#/.NET projects and solutions
- Unity project detection signals
- large multi-folder repos where only focused context should be sent to the model

Next.js support is expected through package/build/config detection, but should be validated on a real Next.js workspace before relying on it for broad changes.

## Recommended Workflow

1. Run `Aegis: Run Health Check`.
2. Generate or update the roadmap.
3. Ask for one small task, not a broad rewrite.
4. Review the impact analysis and confidence score.
5. Open diffs and check why each file is being changed.
6. Approve only the stage or files you trust.
7. Let validation run.
8. Use rollback if the result is not what you wanted.

Best results come from concrete requests like "add validation for this endpoint" or "fix this build error" rather than "improve the app."

## Daily Workflow Examples

### Fix The Current Error

1. Open the file with the error or leave the diagnostics visible.
2. Click **Fix Current Error**.
3. Review the plan, confidence, risky-file labels, and focused context files.
4. Open the diff and approve only the changes you trust.
5. Click **Run Validation**.

### Continue Existing Work

1. Open the project folder.
2. Click **Continue Current Task** to pick up the last task, or **Continue From Roadmap** to use `.aegis/roadmap.md`.
3. Keep each approved change small.
4. Use **Roll Back Last Change** if the result is not right.

### Explain Before Editing

1. Open a source file.
2. Click **Explain Current File**.
3. Ask follow-up questions in chat.
4. Attach selected code only when it is relevant.

## Command Center UI

Open **Aegis Local Agent** from the Activity Bar or run `Aegis: Chat With Local Model`.

The sidebar is organized as a local coding-agent cockpit:

- Project Overview: workspace, language/framework, validation commands, active model, health, and last validation result.
- Chat Panel: conversation history, model selector, clear chat, attach current file, and attach selected code.
- Agent Actions: continue work, review project, fix errors, generate roadmap, continue from roadmap, review current file, improve selected code, and create a feature.
- Active Plan: current task, planned steps, likely changed files, risk, and approval state.
- Diff / Approval: proposed changes with approve all, approve selected, reject, regenerate plan, and open diffs.
- Validation Console: running command output, build/test result, and repair attempt count.
- Memory Panel: one-click open buttons for `.aegis` memory files.
- Dependency Graph Summary: import edges, indexed symbols, routes/APIs, components, tests, and configs.
- Impact Analysis: likely affected files, risk, related tests, validation commands, breaking points, and rollback plan.
- Staged Plan: multi-file work split into approval gates.
- Changed Files History: recent applied agent changes plus rollback.
- Health Check: workspace, Ollama, model, storage, shell, backup, and index probes.
- Model Diagnostics: installed model list, test prompt latency, fallback testing, and context-size warning.
- Error Reporting: latest error, failed command, stack trace, likely cause, suggested fix, retry, and log access.
- Settings: Ollama URL, default model, fallback models, max context size, auto-scan on open, validation command preferences, and safety mode.

## Agent Mode

`Aegis: Run Agent Mode` and `Aegis: Continue Working On This Project` follow this loop:

1. Understand the request.
2. Inspect the current workspace.
3. Create a plan.
4. Propose file changes.
5. Show repo-wide impact analysis.
6. Show diff previews.
7. Wait for approval.
8. Apply approved changes with backups.
9. Run detected validation commands.
10. Summarize results.
11. Suggest the next step.

If validation fails, the agent captures command output, summarizes the error, inspects context again, proposes a repair, shows a diff, waits for approval, and reruns validation. Automatic repair proposals are capped at 3 attempts per request.

Detected validation commands are limited to known safe checks:

- `npm test`
- `npm run build`
- `pnpm test`
- `pnpm build`
- `yarn test`
- `yarn build`
- `dotnet build`
- `cargo check`
- `python -m pytest`
- `cmake --build build`

The extension does not run destructive commands automatically.

## Workspace Memory

Agent Mode creates local memory files in `.aegis/`:

- `project-summary.md`
- `architecture-map.md`
- `roadmap.md`
- `decisions.md`
- `known-issues.md`
- `validation-log.md`
- `extension-log.md`
- `agent-history.json`
- `file-index.json`
- `dependency-graph.json`
- `symbol-index.json`
- `change-history.json`
- `backups/`

Memory content is project-local and avoids storing secret-looking lines. Generated Markdown is written into managed sections so human notes outside those sections are preserved. In this repo, `.aegis/` is ignored by git.

If a `.aegis` memory file is accidentally replaced by a directory or another non-file path, startup leaves it untouched, logs the issue to the Aegis output channel when possible, and continues in degraded mode. Run the health check to identify the damaged path before resetting memory.

## Health Check

Run `Aegis: Run Health Check` from the Command Palette or the sidebar.

It verifies:

- a workspace folder is open
- `.aegis/` is writable
- Ollama is reachable
- the selected model exists
- fallback models exist
- VS Code extension storage works
- shell commands can run
- `.aegis/backups/` can be created
- dependency and symbol indexes can be written

The result opens as a Markdown report and is also shown in the sidebar.

## Logs

Aegis writes project-local extension logs to:

```text
.aegis/extension-log.md
```

The log includes startup events, indexing, model calls, validation attempts, file writes, health checks, retries, and errors. Secret-looking lines are filtered before logging.

## Model Diagnostics

Use the sidebar model diagnostics buttons to:

- list installed Ollama models
- send a small test prompt to the selected model
- measure latency
- test fallback models
- see a context-size warning when `maxContextChars` is close to the configured Ollama request context

Common Ollama fixes:

```powershell
ollama serve
ollama list
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

If Aegis reports Ollama offline, verify `aegisLocalAutopilot.ollamaUrl` matches the local server URL. The default is `http://127.0.0.1:11434`.

## Repo-Wide Intelligence

Aegis maintains two local indexes for larger tasks:

- `.aegis/dependency-graph.json` tracks imports, exports, entry points, config/build files, routes/pages/components, APIs/services, tests, and reverse dependencies.
- `.aegis/symbol-index.json` tracks classes, functions, interfaces/types, components, routes, API endpoints, VS Code commands, package scripts, validation commands, and config objects.

These indexes are lightweight project intelligence files, not a compiler. They help Aegis pick focused context, estimate impact, locate related tests, and avoid changing architecture blindly.

## Impact Analysis

Before proposing code changes, Agent Mode now builds an impact analysis showing:

- files likely affected
- related imports/dependents
- nearby tests
- detected validation commands
- risk level
- possible breaking points
- rollback plan

This analysis is shown in the sidebar and included in the local model prompt so larger tasks stay scoped and reviewable.

## Staged Multi-File Edits

For larger changes, Aegis asks the model for a staged plan:

- Stage 1: architecture/prep
- Stage 2: implementation
- Stage 3: tests/validation
- Stage 4: cleanup/docs

Each stage is previewed in VS Code diffs and requires approval before it is applied. If you pause after a stage, Aegis runs validation on the current workspace state and keeps the remaining work pending.

## Project Roadmap

Run `Aegis: Generate/Update Project Roadmap` to refresh `.aegis/roadmap.md` with:

- current project state
- completed features
- missing features
- bugs and risks
- next best tasks
- recommended priority order

Run `Aegis: Continue From Roadmap` to read `.aegis/roadmap.md`, choose the highest-value safe next task, create a plan, propose diffs, and wait for approval before applying anything.

## Context Selection

Aegis does not send the entire project blindly. It builds focused model context from:

- the user request or roadmap task
- the active file
- selected relevant configs and entry points
- test files and related files
- import/require links from selected files
- reverse dependencies from the local dependency graph
- related symbols from the symbol index
- recent VS Code diagnostics and validation output
- recent modifications and project memory

## Practical Limitations

- Aegis indexes source text with lightweight heuristics, not a full compiler or language server.
- Large repositories are sampled to stay fast; use folder-scoped commands for better precision.
- It can still propose files that are technically valid but not architecturally ideal; review the rationale and diff.
- Validation commands are intentionally conservative and may miss custom project checks.
- Unity and Next.js should be validated on real local projects before broad use.
- Model quality depends on the installed Ollama model and the amount of focused context available.

## Real-World Hardening Notes

Project-local findings are tracked in:

```text
.aegis/real-world-testing.md
```

Use that file to record bad plans, hallucinated files, failed edits, unsafe proposals, model failures, and validation gaps discovered during real project use.

## Rollback Workflow

Before every approved apply, Aegis creates a snapshot in `.aegis/backups/<timestamp>/` and records the changed files in `.aegis/change-history.json`.

Use `Aegis: Rollback Last Agent Change` or the sidebar **Rollback Last** button to restore the previous contents from the latest Aegis backup. If a file was newly created by the agent, rollback removes that file. Rollback only touches files recorded in a valid backup manifest for the current workspace, skips missing or unreadable backup entries with output-channel details, and reports manifest-level failures clearly.

## Failure Handling And Recovery

When an operation fails, Aegis records the latest error in the sidebar with:

- failed command
- stack trace when available
- likely cause
- suggested fix
- retry button

Approved edits are backed up before file writes. If an apply operation fails midway, Aegis attempts to restore already-touched files from the partial backup and preserves the backup for inspection.

If VS Code reloads while an agent task is unfinished, Aegis looks for `.aegis/agent-recovery.json` on startup and prompts you to:

- resume the task
- discard the recovery state
- rollback the last agent change

## Reset Project Memory

To reset memory for a project, close VS Code or stop the agent, then delete the project-local `.aegis/` folder. The extension will recreate fresh memory on the next scan or Agent Mode run.

## Commands

- `Aegis: Continue Working On This Project`
- `Aegis: Run First-Run Setup`
- `Aegis: Explain This Project`
- `Aegis: Fix Build Errors`
- `Aegis: Review Current File`
- `Aegis: Improve Selected Code`
- `Aegis: Generate TODO Roadmap`
- `Aegis: Generate/Update Project Roadmap`
- `Aegis: Continue From Roadmap`
- `Aegis: Create Feature In Current Project`
- `Aegis: Run Agent Mode`
- `Aegis: Chat With Local Model`
- `Aegis: Run Health Check`
- `Aegis: Run Validation`
- `Aegis: Scan Local Models`
- `Aegis: Preview Last Local Proposal`
- `Aegis: Apply Last Local Proposal`
- `Aegis: Rollback Last Agent Change`

The Explorer context menu also exposes folder-scoped Aegis actions.

## Safety Rules

Aegis never rewrites the whole project automatically. Model output becomes a proposal first.

Before applying edits, the extension:

- opens proposed file diffs
- asks for approval
- creates backups in `.aegis/vscode-autopilot/checkpoints`
- creates rollback snapshots in `.aegis/backups`
- validates rollback manifests before restore, including timestamp-like backup IDs, workspace roots, and backup file paths
- stores proposal history in `.aegis/vscode-autopilot/proposals`
- refuses absolute paths and writes outside the project folder
- blocks `.env`, secret, credential, token, key, certificate, dependency, vendor, build, dist, cache, and VCS paths
- blocks lockfile edits unless the proposal explicitly explains why a lockfile must change

`.aegis/` is ignored by git in this repo.

## Settings

- `aegisLocalAutopilot.ollamaUrl`: default `http://127.0.0.1:11434`
- `aegisLocalAutopilot.chatModel`: default `qwen3-coder:30b`
- `aegisLocalAutopilot.fastModel`: default `qwen2.5-coder:7b`
- `aegisLocalAutopilot.fallbackModels`: default `qwen2.5-coder:7b`, `granite-code:8b`
- `aegisLocalAutopilot.embeddingModel`: default `mxbai-embed-large:latest`
- `aegisLocalAutopilot.maxContextFiles`: TODO/context scan cap
- `aegisLocalAutopilot.maxContextChars`: focused prompt context size
- `aegisLocalAutopilot.autoScanOnOpen`: scan memory when a workspace opens
- `aegisLocalAutopilot.validationCommandPreferences`: optional validation command allow-list
- `aegisLocalAutopilot.safetyMode`: `standard`, `strict`, or `review-only`
- `aegisLocalAutopilot.excludeGlob`: VS Code file scan exclusions

## Troubleshooting

- **No Workspace**: open the project folder in VS Code, not just an individual file.
- **Ollama Offline**: start Ollama, confirm `ollama list` works, then run the health check.
- **Selected Model Missing**: pull the model or choose one from the sidebar model selector.
- **Slow Model Calls**: use a smaller task, lower `maxContextChars`, or switch to `qwen2.5-coder:7b`.
- **Write Failures**: check permissions for the workspace and `.aegis/`.
- **Damaged `.aegis` Memory**: run Health Check, inspect the Aegis output channel, then rename or remove only the damaged `.aegis` path after confirming backups/logs are no longer needed.
- **Validation Fails**: review the validation console, then let Aegis propose a repair or run rollback.
- **Stuck State After Reload**: use the recovery prompt, or delete `.aegis/agent-recovery.json` after confirming no task should resume.
