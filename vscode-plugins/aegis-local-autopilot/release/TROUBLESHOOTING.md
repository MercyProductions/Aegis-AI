# Auralith OS Local Agent Troubleshooting

## VSIX Does Not Build

Run:

```powershell
npm run lint
npm run test:unit
```

Fix lint or helper-test failures before packaging. The package script runs package lint before creating the VSIX.

## VS Code Install Fails

Confirm the package exists:

```powershell
Test-Path .\release\aegis-local-autopilot-0.1.8.vsix
```

Then reinstall:

```powershell
code --install-extension .\release\aegis-local-autopilot-0.1.8.vsix --force
```

Reload VS Code after installation.

## Extension-Host Smoke Is Blocked

If smoke testing reports a VS Code update mutex or another instance conflict, close extension-host windows and rerun after the test instance finishes updating.

## Ollama Is Offline

Start Ollama and confirm:

```powershell
ollama list
```

Install the recommended model if needed:

```powershell
ollama pull qwen3-coder:30b
```

## Core Is Offline

The extension should fall back to local behavior and show recovery status when Aegis Core is unavailable. Start Core before testing shared workflow, memory, diagnostics, and compatibility flows.

## Reset Project State

Project-local state lives under `.aegis/`. Delete it only after confirming backups, logs, and rollback records are no longer needed.
