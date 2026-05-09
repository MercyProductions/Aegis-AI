# Install

Last updated: 2026-05-09

This project is a local-first Auralith/Aegis ecosystem. The daily dogfooding stack is:

- Aegis Core `/v1` on `http://127.0.0.1:8788`
- Website backend `/api` on `http://127.0.0.1:8787`
- Website frontend on `http://127.0.0.1:5173`
- Native desktop app built from `AegisChatBotDesktop.sln`
- VS Code extension packaged from `vscode-plugins/aegis-local-autopilot`
- Visual Studio extension packaged from `visual-studio-extensions/aegis-local-agent-vs`

## Prerequisites

- Windows with PowerShell.
- Python 3.10 or newer.
- Node.js and npm.
- Visual Studio with C++ desktop tools for the desktop app.
- .NET SDK and Visual Studio extension tooling for the Visual Studio extension.
- VS Code for local VSIX installation.
- Ollama on `http://127.0.0.1:11434` for local model calls.

Recommended local models:

```powershell
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## Start The Daily Stack

Start Aegis Core:

```powershell
cd aegis-core
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-core.ps1
```

From the repository root, start the Website backend and frontend:

```powershell
.\website\launch.ps1
```

The launcher prepares the Website virtual environment, starts the backend on `8787`, starts the frontend on `5173`, and opens the web app.

## Build And Install Clients

Desktop app:

```powershell
.\build.ps1
```

Desktop smoke:

```powershell
.\build.ps1 -Smoke
```

VS Code extension:

```powershell
cd vscode-plugins\aegis-local-autopilot
npm run lint
npm run package
code --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
```

Visual Studio extension:

```powershell
cd visual-studio-extensions\aegis-local-agent-vs
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The packaged VSIX is copied to:

```text
visual-studio-extensions\aegis-local-agent-vs\release\AegisLocalAgentVs.vsix
```

## Validate

High-value release candidate checks:

```powershell
cd aegis-core
python -m pytest tests -q
python -m pip wheel . -w dist
python -m aegis_core.cli health --workspace .
```

```powershell
cd website\backend
python -m pytest tests -q
```

```powershell
cd website\frontend
npm test
npm run build
```

```powershell
cd website
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-web.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\e2e-web.ps1
```

See `ECOSYSTEM_VALIDATION_REPORT.md` for the latest full validation result.
