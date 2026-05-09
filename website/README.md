# Auralith OS

Auralith OS is a local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution. It runs a FastAPI backend and a React UI, with one built-in engine: `Aegis Core`.

The public product identity is `Auralith OS`, the assistant identity is `Auralith Prime`, and the runtime/engine layer remains `Aegis Core`.

The current Phase 1 agent spine adds:

- local model runtime wiring through an owned `Aegis Core` client
- Ollama or OpenAI-compatible local inference endpoints
- structured task/event logging in SQLite
- guarded command validation with an allowlist and timeout
- workspace-scoped file reads and writes
- checkpoint folders before file changes
- repair-attempt history with rollback-aware checkpoints
- project-note memory for constraints, preferences, architecture, and environment notes
- UI visibility for local model status, task timeline, validation output, and workspace memory

## Quick Launch

From this folder, run:

```powershell
.\launch.ps1
```

Root-level web workspace scripts are also available from this folder:

```powershell
npm test -- --run
npm run build
npm run backend:test
npm run validate
npm run doctor:web
npm run smoke:web
npm run e2e:web
npm run acceptance:web
```

Use `npm run validate` for the offline frontend/backend test suite. Use `npm run doctor:web`,
`npm run smoke:web`, and `npm run e2e:web` once the app is running from `.\launch.ps1`.
Use `npm run acceptance:web` before calling a web change done; it runs the offline validation,
runtime doctor, backend smoke flow, and real browser e2e flow in sequence.

Or double-click:

```text
Launch Auralith OS.cmd
```

The launcher now:

- creates `.env` from `.env.example` if it does not exist
- installs backend and frontend dependencies when needed
- starts the backend and frontend only if they are not already running
- waits for both services to become reachable
- writes service logs into `logs/`

## Aegis Core

The built-in engine is `Aegis Core`. It is a self-contained local workflow engine for:

- session continuity and direction setting
- workspace review
- starter generation
- preview-first file changes
- local model-backed drafting when a configured model server is reachable
- validation command execution when enabled

During ecosystem stabilization, the standalone shared Aegis Core runtime can also run at:

```text
http://127.0.0.1:8788
```

The website remains on its existing `/api` backend for daily use. Local/dev dashboard features should migrate to the shared `/v1` Core contracts incrementally after the Desktop, VS Code, and Visual Studio clients have dogfooded that path.

The UI lets you set:

- your Aegis assistant name
- your Aegis mission
- the default working mode
- the workspace root

## Local Model Runtime

By default Aegis looks for an Ollama-compatible local runtime:

```text
AEGIS_MODEL_API=ollama
AEGIS_MODEL_ENDPOINT=http://127.0.0.1:11434
AEGIS_MODEL_NAME=qwen2.5-coder:7b
```

This machine has been set up with:

```text
Ollama 0.21.0
qwen2.5-coder:7b
```

Useful local model commands:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen2.5-coder:7b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

The launcher will try to start the Ollama server automatically when the app is configured for the default local Ollama endpoint.

For llama.cpp, vLLM, SGLang, or another OpenAI-compatible local server, use:

```text
AEGIS_MODEL_API=openai
AEGIS_MODEL_ENDPOINT=http://127.0.0.1:8000/v1
AEGIS_MODEL_NAME=your-local-model-name
```

If the model server is offline, the backend stays available and falls back to the deterministic local starter/review engine. The UI shows backend status and model status separately.

## Validation Loop

When `Run validation` is enabled in the UI and changes are applied, Aegis tries to infer a validation command from the workspace:

- `package.json` with `build` or `test`
- `Cargo.toml`
- `go.mod`
- `pyproject.toml` or `requirements.txt`
- Vite/TypeScript config files

Commands are constrained by:

```text
AEGIS_COMMAND_ALLOWLIST=python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet
AEGIS_COMMAND_TIMEOUT_SECONDS=120
```

Every task, event, command result, and validated repair memory is stored in:

```text
data/aegis.sqlite3
```

If an older install wrote task history into `backend/data/aegis.sqlite3`, Aegis now imports that legacy data into the repo-root database automatically.

## Modes

- `Build` creates the next starter or first slice.
- `Develop` focuses on extending the current workspace.
- `Review` inspects what exists and proposes the next move.
- `Chat` keeps the interaction conversational and planning-led.

## Workspace

By default, Aegis writes into:

```text
workspace/
```

You can change the workspace path in the UI. All file changes stay constrained to that selected workspace.
If an older install wrote files into `backend/workspace/`, Aegis now migrates that legacy workspace forward into the repo-root `workspace/` folder when the new workspace is empty.

Workspace setup stores project and validation metadata under `.aegis/` in the selected workspace. If those memory paths are damaged, setup now stays usable and reports warnings so you can repair the paths before running setup again.

Checkpoint restore validates checkpoint folder names, manifests, and backup paths before touching workspace files. Damaged checkpoint metadata returns a clear restore error instead of attempting an unsafe rollback.

## Project Layout

```text
backend/      FastAPI Aegis engine
frontend/     React + Vite Aegis interface
scripts/      Service launch helpers
workspace/    Default generated-project workspace
logs/         Backend and frontend logs
```
