# Aegis-AI

Native desktop chatbot workspace for Aegis AI.

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

## What It Supports

- Native chat UI with Build, Develop, Review, and Chat modes.
- Workspace file listing and text-file preview.
- Direct `/api/chat`, `/api/config`, `/api/files`, `/api/file`, `/api/apply`, `/api/validate`, and `/api/history` integration.
- Preview-first generated file changes.
- One-click apply and validation.
- Backend status, local model status, task events, and recent task history.
- Desktop settings and Aegis backend settings from inside the app.
