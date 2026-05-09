# Troubleshooting

## Aegis Core

Start Core from `aegis-core/`:

```powershell
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

Check health:

```powershell
python -m aegis_core.cli health --workspace . --json
```

If `--json` appears to fail, update to the latest CLI. It should work before or after the subcommand.

If `aegis tasks --create ... --json` returns `ok: false` with a persistence error, repair the workspace `.aegis` folder before retrying. The CLI should return a nonzero exit code and a structured JSON error instead of a Python traceback.

If validation reports `Validation command failed to start`, the command passed the safety allow-list but the OS could not launch it. Check that the tool is installed, available on `PATH`, and allowed by local permissions, then rerun the health check or validation command.

Desktop and VS Code backend/Core URL settings are normalized before use. Inputs like `127.0.0.1:8788` or pasted `/v1/ecosystem/dashboard` URLs are reduced to a clean `http://host:port` base URL, while empty values fall back to the local defaults.

## Ollama

Default local endpoint:

```text
http://127.0.0.1:11434
```

Recommended models:

```powershell
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

If model calls fail:

- Confirm `ollama list` works.
- Confirm the configured model is installed.
- Confirm the configured Ollama URL includes a valid host and port. `127.0.0.1:11434` is normalized to `http://127.0.0.1:11434`, and pasted paths such as `/api/tags` are trimmed to the base URL.
- Run the relevant client health check.
- Check `.aegis/core-log.md`, `.aegis/extension-log.md`, and `.aegis/validation-log.md`.

## Shared Client Sync

Expected Core clients:

- `auralith-desktop`
- `aegis-vscode`
- `aegis-visual-studio`
- `auralith-website`

Check the shared dashboard:

```powershell
python -m aegis_core.cli dashboard --workspace . --json
```

If a client is missing:

- Open that client and run its health check.
- Confirm its Aegis Core URL is `http://127.0.0.1:8788`.
- Confirm `.aegis/clients.json` is writable.

If Core is reachable but registration is skipped, the client should keep local workflows usable and report shared sync as degraded. Repair the workspace `.aegis` path, especially if `.aegis` or `.aegis/clients.json` was accidentally replaced by a file or directory with the wrong shape.

VS Code and Visual Studio try to show the parsed Core error detail for failed shared sync calls. If the message mentions persistence, repair the workspace `.aegis` folder before retrying client registration or task sync.

If a client reports an unexpected Core `api_version` or response `kind`, it is usually talking to an old Core process or the wrong base URL. Restart Core on `http://127.0.0.1:8788`, confirm `/v1/health` returns `api_version: v1`, and remove any pasted endpoint path from the client setting so only the base URL remains.

Expected degraded behavior when Core is offline:

- VS Code: logs Core registration/task/model/scan/roadmap/validation warnings and falls back to local or direct Ollama paths where available.
- Visual Studio: reports Core health/registration as a warning and keeps local solution/review/build workflows available.
- Desktop: keeps Website `/api` workflows available and marks the shared Core dashboard as unavailable.

## Safe Apply And Rollback

All clients should keep approval-based edits on by default. Before applying generated edits:

- Review the diff.
- Confirm no secrets or generated folders are touched.
- Confirm a backup will be written under `.aegis/backups/`.

If an apply fails, use the client's rollback command first, then inspect `.aegis/backups/`.

Website checkpoint restore accepts only checkpoint folder names and validates manifest/backup paths before touching workspace files. If restore fails with a checkpoint safety error, inspect `.aegis/checkpoints/<id>/manifest.json` and preserve the checkpoint before repairing or removing damaged metadata.

Website apply requires checkpoint creation before file edits. If apply returns a checkpoint warning and no files changed, repair `.aegis/checkpoints/` or the selected workspace permissions before retrying.

## Website

The Website currently uses its own mature `/api` backend. Do not force it onto standalone Core `/v1` APIs during stabilization unless a specific workflow proves the migration is needed.

If workspace setup warns that `.aegis/project.json` or `.aegis/validation_profile.json` could not be written, inspect those paths in the selected workspace. Preserve anything useful, then repair the damaged file/directory path and run setup again.
