# Auralith OS Local Agent Install Guide

## Requirements

- Visual Studio Code 1.90 or newer.
- Node.js and npm for local packaging.
- Ollama running locally for local-model workflows.
- Optional Aegis Core runtime at `http://127.0.0.1:8788` for shared workflow, memory, diagnostics, and compatibility checks.

Recommended local model:

```powershell
ollama pull qwen3-coder:30b
```

Fallback models:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## Build And Package

From `vscode-plugins\aegis-local-autopilot`:

```powershell
npm run compile
npm run lint
npm run test:unit
npm run package
```

The package script writes:

```text
release/aegis-local-autopilot-0.1.8.vsix
```

## Install Locally

```powershell
code --install-extension .\release\aegis-local-autopilot-0.1.8.vsix --force
```

Reload VS Code after installation if prompted.

## Clean Install Smoke

```powershell
$smoke = Join-Path $env:TEMP "aegis-vscode-0.1.8-smoke"
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --install-extension .\release\aegis-local-autopilot-0.1.8.vsix --force
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --list-extensions --show-versions
```

## First Run

1. Start Ollama.
2. Open a workspace folder.
3. Run `Aegis: Run First-Run Setup`.
4. Run `Aegis: Run Health Check`.
5. Use preview/approval flows for any generated change.

Project-local state is written under `.aegis/`.
