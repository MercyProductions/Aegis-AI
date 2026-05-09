# Aegis-AI

Native desktop chatbot workspace for Aegis AI.

## Aegis Core

Shared local-first runtime work now lives in:

```text
aegis-core/
```

Aegis Core is the consolidation layer for the Desktop App, Website, VS Code extension, and Visual Studio extension. It provides reusable Ollama integration, workspace scanning, memory, roadmap generation, validation detection, diagnostics, predictive change simulation, engineering operations intelligence, adaptive personal engineering intelligence, and plan-only agent workflows through a Python service layer, local FastAPI API, and optional `aegis` CLI.

The current integration phase adds a shared `/v1` API for cross-client memory, tasks, diagnostics, model settings, client registration, and a desktop dashboard data source at `/v1/ecosystem/dashboard`.

Start with:

```powershell
cd aegis-core
python -m aegis_core.cli health --workspace ..
python -m aegis_core.cli scan --workspace ..
python -m aegis_core.cli roadmap --workspace ..
python -m aegis_core.cli route --workspace .. --task-type hard_debugging --provider lm_studio --model local-model --context-file src/App.tsx --json
python -m aegis_core.cli simulate --workspace .. --objective "Refactor one service safely" --approach "Minimal adapter"
python -m aegis_core.cli operations --workspace ..
python -m aegis_core.cli personal --workspace .. --preference planning_depth=balanced
```

See `aegis-core/docs/SYSTEM_ARCHITECTURE.md` for the target ecosystem architecture.

Current stabilization notes live in `docs/ECOSYSTEM_STABILIZATION.md`.

Product utilization and long-term workflow refinement notes now live in `WORKFLOW_NOTES.md`.

Release candidate validation is tracked in `ECOSYSTEM_VALIDATION_REPORT.md`. The latest pass verified Core startup, Website startup, real web chat, workspace scan/setup, roadmap/memory/diagnostics contracts, validation, apply/rollback, desktop smoke screenshots, VS Code VSIX install, Visual Studio VSIX packaging, failure/degraded modes, and the full backend/frontend/Core test suites.

Install and daily dogfooding setup instructions live in `INSTALL.md`. Current daily evidence is tracked in `DOGFOODING_NOTES.md`.

## Desktop App

Native C++/Win32/DirectX11 Dear ImGui desktop client for the Aegis Coding AI chatbot. This is not a browser wrapper; it talks directly to the existing FastAPI backend over WinHTTP.

## Build

```powershell
.\build.ps1
```

Or open `AegisChatBotDesktop.sln` in Visual Studio and build `Release|x64`.

The executable is written to:

```text
x64\Release\AegisChatBotDesktop.exe
```

## Backend

By default the app connects to:

```text
http://127.0.0.1:8787
```

It auto-starts the existing website backend through the bundled Python venv without Uvicorn reload, which is better for a desktop process. If the venv is missing, it falls back to:

```text
website\scripts\start-backend.ps1
```

Desktop connection settings live in `AegisChatBot.config.ini`.

The desktop app also has an Auralith Ecosystem card that can read Aegis Core from:

```text
http://127.0.0.1:8788
```

Set `core_api_base_url` in `AegisChatBot.config.ini` if Core runs on another local port. The desktop app normalizes common local inputs such as `127.0.0.1:8788` or pasted `/v1/...` endpoint URLs back to the Core base URL.

## Web Workspace

The React/FastAPI web workspace now lives directly in this repo under:

```text
website\
```

From the repo root, launch it with:

```powershell
.\website\launch.ps1
```

The desktop app is configured to use that embedded backend by default, so the repo can be restored from GitHub without depending on the old `Website\ChatBot` folder.

For daily use, run Aegis Core on `8788` first, then run `website\launch.ps1`. The Website remains usable when Core is offline, but shared roadmap, memory, diagnostics, clients, and task state are degraded until Core comes back.

## What It Supports

- Native chat UI with Build, Develop, Review, and Chat modes.
- Workspace file listing and text-file preview.
- Direct `/api/chat`, `/api/config`, `/api/files`, `/api/file`, `/api/apply`, `/api/validate`, and `/api/history` integration.
- Preview-first generated file changes.
- One-click apply and validation.
- Backend status, local model status, task events, and recent task history.
- Desktop settings and Aegis backend settings from inside the app.
