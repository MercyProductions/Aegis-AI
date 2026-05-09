# Aegis Local Agent Install Guide

## Requirements

- Visual Studio Code 1.90 or newer
- Node.js and npm
- Ollama running locally
- Recommended model:

```powershell
ollama pull qwen3-coder:30b
```

Fallback models:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## Build

From the extension folder:

```powershell
npm run compile
npm run lint
npm run package
```

The packaged extension is written to:

```text
release/aegis-local-autopilot-0.1.1.vsix
```

## Debug Build

For extension development:

1. Open this extension folder in VS Code.
2. Run `npm run compile`.
3. Press `F5` to launch an Extension Development Host.
4. Open a separate test workspace in that host.
5. Run `Aegis: Run Health Check` before testing agent flows.

## Install Locally

```powershell
npm run install-local
```

Manual install:

```powershell
code --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
```

Clean-instance install test:

```powershell
$smoke = Join-Path $env:TEMP "aegis-vscode-rc-smoke"
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --list-extensions --show-versions
```

You can also install through VS Code:

1. Open Extensions.
2. Select the `...` menu.
3. Choose **Install from VSIX...**.
4. Pick `release/aegis-local-autopilot-0.1.1.vsix`.

## First Run

After installation, reload VS Code and open a project folder. Aegis will:

- check Ollama
- detect installed models
- ask you to choose a default model
- create `.aegis/` in the current project
- run a health check
- open a setup checklist

Run `Aegis: Run First-Run Setup` any time to repeat this flow.

## Update

Build a new VSIX, then reinstall:

```powershell
npm run install-local
```

VS Code may ask for a reload after installing.

## Uninstall

```powershell
code --uninstall-extension aegis.aegis-local-autopilot
```

## Reset Project Memory

Delete the project-local `.aegis/` folder after confirming you do not need its backups or logs. Aegis recreates memory on the next scan.

## Supported Models

Default:

```text
qwen3-coder:30b
```

Fallbacks:

```text
qwen2.5-coder:7b
granite-code:8b
```

Use `Aegis: Scan Local Models` or the sidebar model selector to choose another installed Ollama model.

## Daily Use

- Open a project folder, not just a single file.
- Run `Aegis: Run Health Check`.
- Generate or update the roadmap.
- Ask for one small task at a time.
- Review the impact analysis and diff before approving changes.
- Run validation after approved edits.
- Use `Aegis: Rollback Last Agent Change` if a result is not right.
