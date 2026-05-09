# Memory System

Aegis Core stores local project memory in each workspace:

```text
.aegis/
```

## Files

- `config.json`: workspace-local Core config overrides
- `project-summary.md`: generated workspace summary
- `architecture-map.md`: generated architecture overview
- `roadmap.md`: generated roadmap and task priorities
- `decisions.md`: append-only decision log
- `known-issues.md`: user/Core-known issue notes
- `validation-log.md`: validation command history and excerpts
- `agent-history.json`: append-only shared agent/task event history
- `clients.json`: registered Auralith clients and last-seen timestamps
- `tasks.json`: shared task list visible across clients
- `active-agent-plan.json`: current plan-only continuation workflow
- `active-repair-plan.json`: current plan-only repair workflow
- `file-index.json`: indexed files and metadata
- `dependency-graph.json`: import/include/dependency relationships
- `symbol-index.json`: classes, functions, components, methods, and related symbols
- `scan-cache.json`: last Core scan result and practical workspace fingerprint for faster repeated scans
- `core-log.md`: sanitized local Core diagnostics

## Generated Sections

Markdown files use generated markers:

```text
<!-- AEGIS_CORE:GENERATED START -->
...
<!-- AEGIS_CORE:GENERATED END -->
```

Aegis Core replaces only the generated section. Human-written notes outside the generated section are preserved.

## Privacy Rules

Core should not store:

- `.env` content
- private keys
- credentials
- secret-looking values
- password/token/auth files
- generated build outputs
- vendor dependencies

Diagnostics pass through a simple redaction layer before being written to `core-log.md`.

## Reset

To reset memory for a project, delete `.aegis/` after confirming backups and logs are no longer needed.

Future installers should expose a safer reset flow with backup preservation.

## Cross-Client Memory

All clients should read memory through:

```text
GET /v1/memory?workspace=<path>
```

Clients may open the files directly for editor-native display, but Core should remain the source for summaries, diagnostics redaction, task creation, and generated-section updates.

Shared tasks live in `.aegis/tasks.json`, but clients should create and update them through `/v1/tasks` so the event history stays consistent.
