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

Desktop, Website, VS Code, and Visual Studio backend/Core URL settings are normalized before use. Inputs like `127.0.0.1:8788`, pasted `/v1/ecosystem/dashboard` URLs, and legacy Core endpoints such as `/health` or `/models` are reduced to a clean Core base URL, while empty values fall back to the local defaults. Website, VS Code, and Visual Studio preserve reverse-proxy path prefixes such as `https://proxy.local/aegis` and append Core API paths under that prefix.

If saving Core settings returns `Could not persist Aegis Core settings`, inspect the project `.aegis` path. The settings file must be a writable `.aegis/config.json` file, not a directory or a blocked path.

If a scheduled job reports `Could not persist maintenance job state` or `Could not write jobs log`, repair `.aegis/jobs-state.json` and `.aegis/jobs-log.md` so they are writable files. Safe scan/report jobs may still finish, but their history is not trustworthy until those paths are fixed.

If orchestration planning or step advancement reports `Could not persist orchestration state`, repair `.aegis/orchestration-queue.json` and `.aegis/active-orchestration.json` so they are writable JSON files before continuing staged autonomous work.

If recording quality snapshots reports `Could not persist quality health history`, repair `.aegis/health-history.json` so it is a writable JSON file before relying on health trends, daily reports, or weekly quality summaries.

If recording the knowledge graph reports `Could not persist knowledge graph` or `Could not persist knowledge summary`, repair `.aegis/knowledge-graph.json` and `.aegis/knowledge-summary.md` so they are writable files before relying on saved dependency and architecture relationships.

If saving or resetting personal intelligence reports `Could not persist personal engineering profile` or `Could not reset personal engineering profile`, repair `.aegis/personal-engineering-profile.json` so it is a writable JSON file. Personal workflow preferences remain local, explicit, and user-controlled, but the profile is not trustworthy until that path is fixed.

If roadmap generation reports `Could not persist roadmap`, repair `.aegis/roadmap.md` so it is a writable Markdown file. Agent continuation can still produce a plan-only fallback, but saved roadmap-driven workflows should not be trusted until the file path is fixed.

If validation results include a `validation_log.persisted: false` status or a `Could not persist validation log` warning, repair `.aegis/validation-log.md` so it is a writable Markdown file. The command result is still useful, but repair planning, quality trends, and historical failure analysis will miss that run until logging is fixed.

If continue or repair agent responses include `Could not persist agent plan`, repair `.aegis/active-agent-plan.json` or `.aegis/active-repair-plan.json` so they are writable JSON files. The returned plan is still plan-only and approval-gated, but later clients may not find the saved handoff until the damaged path is fixed.

If workspace scans include `memory_warnings` or a `memory_artifacts` entry with `persisted: false`, repair the named `.aegis` artifact path. The scan result is still usable for the current request, but cached scans, project summaries, architecture maps, dependency graphs, and symbol indexes may be stale or missing until those paths are fixed.

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
- Confirm the configured Ollama URL includes a valid host and port. `127.0.0.1:11434` is normalized to `http://127.0.0.1:11434`, and pasted paths such as `/api/tags` are trimmed to the base URL. VS Code and Visual Studio preserve reverse-proxy prefixes such as `https://proxy.local/ollama`.
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

If the Website reports Core as reachable but degraded with `Core response was not valid JSON`, port `8788` is answering HTTP but not serving the expected Aegis Core `/v1` envelope. Stop the process on that port and restart Aegis Core, then confirm `http://127.0.0.1:8788/v1/health` returns JSON with `api_version: v1`.

Expected degraded behavior when Core is offline:

- VS Code: logs Core registration/task/model/scan/roadmap/validation warnings and falls back to local or direct Ollama paths where available.
- Visual Studio: reports Core health/registration as a warning and keeps local solution/review/build workflows available.
- Desktop: keeps Website `/api` workflows available and marks the shared Core dashboard as unavailable.
- Website: keeps `/api` health, chat, file, apply, validation, memory, and task workflows available; `/api/health` reports `core_runtime_status: unavailable` until Core returns.

If the Website backend is offline while the Vite frontend is still running, the browser shell may continue to load from `http://127.0.0.1:5173`, but API-backed panels should show checking/offline/degraded states. Restart with:

```powershell
.\website\scripts\start-backend.ps1
```

Invalid or uncreatable workspace roots should return a `400` response with a useful detail message. If you see a `500` stack trace for a bad workspace path, rerun the backend tests around `WorkspaceManager.resolve_workspace`.

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

The web UI E2E harness expects API mocks to catch both direct backend URLs and the Vite `/api` proxy. If model-switcher or stream mocks stop matching after API base discovery changes, use the shared route helper in `website/scripts/e2e-web.mjs` instead of hard-coding only `http://127.0.0.1:8787`.
