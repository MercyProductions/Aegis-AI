# Install Aegis Local Agent for Visual Studio

Version: `0.1.1`

## Build Locally

Run fast static package and safety guards:

```powershell
.\build.ps1 -ValidateOnly
```

Build the release VSIX:

```powershell
.\build.ps1
```

## Install VSIX

Close Visual Studio before installing or updating. For a clean install, remove any older **Aegis Local Agent** entry from **Extensions > Manage Extensions** first, then restart Visual Studio.

```powershell
& "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\VSIXInstaller.exe" .\release\AegisLocalAgentVs.vsix
```

Restart Visual Studio after installation.

## Configure Settings

Open:

```text
Tools > Options > Aegis Local Agent > General
```

Recommended defaults:

```text
Ollama URL: http://127.0.0.1:11434
Default model: qwen3-coder:30b
Fallback models: qwen2.5-coder:7b, granite-code:8b
Safety mode: Strict
Auto-scan on solution open: false
Validate after apply: true
Backup location: .aegis/backups
```

If more than one Visual Studio version is installed, target the VS2022 Community instance explicitly:

```powershell
& "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -products * -format json
& "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\VSIXInstaller.exe" /quiet /instanceIds:<instanceId> .\release\AegisLocalAgentVs.vsix
```

## First Run

1. Start Ollama.
2. Open a Visual Studio solution.
3. Run `Aegis: Open Agent`.
4. Run `Aegis: Run Health Check`.
5. Confirm the status shows `Ready`.
6. Run `Aegis: Rescan Solution Intelligence` if you want a fresh index immediately.
7. Generate a roadmap.
8. Use proposals only after reviewing the file list and safety messages.

## Smoke Test Checklist

After installing the VSIX:

1. Open a normal `.sln` or `.slnx`.
2. Run `Aegis: Run Health Check`.
3. Open the Aegis tool window.
4. Send a short chat message.
5. Run `Aegis: Generate Solution Roadmap`.
6. Select an Error List item and run `Aegis: Explain Build Failure` or `Aegis: Fix Selected Error`.
7. Generate a safe proposal and reject it or apply it to a disposable project.
8. Run `Rollback Last` if you applied a proposal.
9. Repeat open + health check + scan on one C# solution, one C++ solution, and one Unity solution before daily use.

## Uninstall

Use Visual Studio:

1. Extensions > Manage Extensions.
2. Installed.
3. Select **Aegis Local Agent**.
4. Uninstall and restart Visual Studio.

## Reset Memory

Delete the solution-local `.aegis/` folder after confirming you no longer need backups or logs.
