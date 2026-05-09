# Troubleshooting Notes

## Health Check

Run:

```text
Aegis: Run Health Check
```

The health check verifies workspace access, `.aegis/` writes, Ollama, selected and fallback models, VS Code storage, shell command execution, backups, and index writes.

## Ollama Offline

Start Ollama and confirm the API is available:

```powershell
ollama serve
ollama list
```

The default URL is:

```text
http://127.0.0.1:11434
```

Change `aegisLocalAutopilot.ollamaUrl` in VS Code settings if your local server is elsewhere.

## Missing Model

Install the default model:

```powershell
ollama pull qwen3-coder:30b
```

Install fallbacks:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

Then run `Aegis: Scan Local Models`.

## Logs

Project-local logs are written to:

```text
.aegis/extension-log.md
```

Validation logs are written to:

```text
.aegis/validation-log.md
```

## Damaged `.aegis` Memory

If a memory file is accidentally replaced by a directory or another non-file path, Aegis leaves that path untouched and continues in degraded mode where possible. Run Health Check, inspect the Aegis output channel, then rename or remove only the damaged `.aegis` path after confirming backups and logs are no longer needed.

Indexing, recovery, validation logging, decision logging, and dogfooding-note writes are best-effort. If the output channel says a memory write was skipped, fix that specific `.aegis` file path and rerun the command; approved file edits and backups remain the priority.

## Recovery

If VS Code reloads mid-task, Aegis reads:

```text
.aegis/agent-recovery.json
```

It will prompt you to resume, discard, or rollback the last change.

## Rollback

Use:

```text
Aegis: Rollback Last Agent Change
```

Backups are stored under:

```text
.aegis/backups/
```

Rollback only touches files listed in a valid latest backup manifest for the current workspace. If the manifest has an unsafe backup ID, hidden/dot-folder backup ID, mismatched workspace root, or backup file path outside `.aegis/backups/`, Aegis refuses or skips that restore path. Missing or unreadable backup files are skipped with details in the Aegis output channel so one damaged entry does not hide the rest of the rollback result.

## Safety Model

Aegis is approval-based. It proposes diffs first, creates backups before approved edits, and blocks secret, credential, dependency, vendor, generated build, cache, and VCS paths. Lockfile edits require an explicit reason in the proposal.

## Known Limitations

- Repository analysis uses lightweight source heuristics, not a full compiler.
- Large repositories are sampled for speed; folder-scoped commands are more precise.
- Validation detection is conservative and may miss custom project scripts.
- Model quality depends on the local Ollama model and the focused context Aegis can gather.
- Unity and large monorepos should be tested with small tasks before broad edits.

## Common Commands

- `Aegis: Run Health Check`
- `Aegis: Chat With Local Model`
- `Aegis: Generate/Update Project Roadmap`
- `Aegis: Continue From Roadmap`
- `Aegis: Continue Working On This Project`
- `Aegis: Run Validation`
- `Aegis: Rollback Last Agent Change`

## Recovery Steps

1. Run `Aegis: Run Health Check`.
2. Open `.aegis/extension-log.md` and `.aegis/validation-log.md`.
3. If a task was interrupted, choose resume, discard, or rollback from the recovery prompt.
4. If the prompt does not appear, inspect `.aegis/agent-recovery.json`.
5. Use rollback before retrying a failed apply.
