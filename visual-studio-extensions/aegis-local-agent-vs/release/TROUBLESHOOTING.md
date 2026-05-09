# Aegis Local Agent Troubleshooting

Applies to dogfooding build `0.1.1`.

## Extension Does Not Appear

- Confirm Visual Studio 2022 Community is installed.
- Install the VSIX, then restart Visual Studio.
- Check **Extensions > Manage Extensions > Installed** for **Aegis Local Agent**.
- Open the tool from **Tools > Aegis: Open Agent**.
- For a clean reinstall, close Visual Studio, uninstall older Aegis builds, install the new VSIX, and restart.

If VSIXInstaller reports no applicable SKUs on a machine with multiple Visual Studio versions, install by instance ID:

```powershell
& "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -products * -format json
& "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\VSIXInstaller.exe" /quiet /instanceIds:<instanceId> .\release\AegisLocalAgentVs.vsix
```

## Ollama Offline

- Start Ollama before using chat or agent actions.
- Confirm `http://127.0.0.1:11434/api/tags` responds in a browser or PowerShell.
- If you changed the endpoint, confirm **Tools > Options > Aegis Local Agent > General > Ollama URL** is correct.
- Run `Aegis: Run Health Check` after Ollama starts.

## Model Missing

Install the configured default model:

```powershell
ollama pull qwen3-coder:30b
```

Optional fallbacks:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## No Solution Detected

- Open a `.sln` file before running roadmap, review, build repair, or safe edit workflows.
- The `.aegis/` memory folder is created at the solution root.
- If the tool window is already open, run `Aegis: Rescan Solution Intelligence`.

## Indexing Looks Stale

- Run `Aegis: Rescan Solution Intelligence`.
- Auto-scan is disabled by default in 0.1.1 to keep large solutions responsive at startup. Enable it in **Tools > Options > Aegis Local Agent > General** only if you want background indexing on solution open.
- Aegis intentionally skips `.vs/`, `bin/`, `obj/`, `packages/`, generated folders, Unity `Library/`, Unity `Temp/`, and vendor folders.

## Damaged `.aegis` Memory

If `.aegis` or a memory file is accidentally replaced by a directory or blocked by permissions, Aegis skips that path and keeps the tool window usable where possible. Run Health Check to identify the failed memory/index probe, then rename or remove only the damaged `.aegis` path after confirming backups and logs are no longer needed.

## Settings Do Not Seem Applied

- Close any pending proposal before changing safety or backup settings.
- Run `Aegis: Run Health Check` to refresh the model list and settings summary.
- New model calls use the latest settings from the Visual Studio options page.

## Build Repair Does Not Find Errors

- Run a normal Visual Studio build once.
- Open **View > Error List** and confirm errors appear there.
- Run `Aegis: Fix Build Errors` again.

## Proposal Is Blocked

Aegis blocks unsafe paths by design, including `.env`, private keys, `.vs/`, `bin/`, `obj/`, `packages/`, generated folders, and vendor folders.

## Rollback

Use **Rollback Last** in the tool window. Backups are stored under:

```text
.aegis/backups/
```

If you changed the backup location in settings, use that configured path instead.

Rollback now resolves the exact backup by manifest backup ID, rejects manifests from another solution, and validates each rollback path before touching solution files. If rollback reports skipped entries, preserve the backup folder and inspect `last-change.json` plus the matching backup `manifest.json` before retrying.
