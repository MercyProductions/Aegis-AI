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

## Safe Apply And Rollback

All clients should keep approval-based edits on by default. Before applying generated edits:

- Review the diff.
- Confirm no secrets or generated folders are touched.
- Confirm a backup will be written under `.aegis/backups/`.

If an apply fails, use the client's rollback command first, then inspect `.aegis/backups/`.

Website checkpoint restore accepts only checkpoint folder names and validates manifest/backup paths before touching workspace files. If restore fails with a checkpoint safety error, inspect `.aegis/checkpoints/<id>/manifest.json` and preserve the checkpoint before repairing or removing damaged metadata.

## Website

The Website currently uses its own mature `/api` backend. Do not force it onto standalone Core `/v1` APIs during stabilization unless a specific workflow proves the migration is needed.

If workspace setup warns that `.aegis/project.json` or `.aegis/validation_profile.json` could not be written, inspect those paths in the selected workspace. Preserve anything useful, then repair the damaged file/directory path and run setup again.
