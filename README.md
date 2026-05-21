# Aegis-AI

Native desktop chatbot workspace for Aegis AI.

## Aegis Core

Shared local-first runtime work now lives in:

```text
aegis-core/
```

Aegis Core is the consolidation layer for the Desktop App, Website, VS Code extension, and Visual Studio extension. It provides reusable Ollama integration, workspace scanning, memory, roadmap generation, validation detection/run storage, diagnostics, safe editing runtime contracts, workflow orchestration, predictive change simulation, engineering operations intelligence, adaptive personal engineering intelligence, and agent workflow records through a Python service layer, local FastAPI API, and optional `aegis` CLI.

The current integration phase makes Core the preferred authority for Website apply/checkpoint/restore/validation workflows while preserving Website `/api` compatibility. The Website backend delegates to Core when available and falls back to its existing local implementation when Core is offline or missing a delegated route.

The Website backend now includes the first provider-account foundation slice. It adds provider manifests, secure API-key linking through the OS credential vault, account/session metadata in SQLite without raw secrets, and safe official-CLI bridge probing for Codex, Gemini, and Claude-style local CLIs. Existing CLI logins are detected and reused by delegation only; Aegis does not read provider token files.

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

Core quality gate architecture, scoring, blockers, benchmark suites, and client responsibilities are documented in `docs/QUALITY_GATES.md`.

Release packaging, ecosystem version manifests, compatibility checks, update flow, rollback, safe mode, and migration behavior are documented in `docs/RELEASE_PACKAGING_AND_UPDATES.md`.

First-run setup, environment diagnostics, safe guided first workflow, settings import/export, and recovery guidance are documented in `docs/FIRST_RUN_ONBOARDING.md`.

Plugin and tool ecosystem architecture, permission scopes, packaging format, extension hooks, and current sandbox limits are documented in `docs/PLUGIN_ECOSYSTEM.md`.

The Auralith Memory and Personal Intelligence layer, including local-first memory lifecycle, privacy controls, Website/Desktop compatibility behavior, and orchestration usage, is documented in `docs/AURALITH_MEMORY_AND_PERSONAL_INTELLIGENCE.md`.

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

Set `core_api_base_url` in `AegisChatBot.config.ini` if Core runs on another local port. The desktop app normalizes common local inputs such as `127.0.0.1:8788`, pasted `/v1/...` endpoint URLs, and legacy `/health` or `/models` endpoints. Reverse-proxy prefixes such as `https://proxy.local/aegis` are preserved.

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

For daily use, run Aegis Core on `8788` first, then run `website\launch.ps1`. The Website remains usable when Core is offline, but shared roadmap, memory, diagnostics, clients, workflow orchestration, Core-owned editing, checkpoint, validation, and repair workflow state are degraded until Core comes back.

## What It Supports

- Native chat UI with Build, Develop, Review, and Chat modes.
- Workspace file listing and text-file preview.
- Direct `/api/chat`, `/api/config`, `/api/files`, `/api/file`, `/api/apply`, `/api/validate`, and `/api/history` integration.
- Preview-first generated file changes.
- One-click apply and validation.
- Backend status, local model status, task events, and recent task history.
- Desktop settings and Aegis backend settings from inside the app.
