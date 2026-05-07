# Unified Context Engine

The Unified Context Engine is the convergence layer for Aegis. It prevents the product from becoming a set of disconnected apps by turning existing subsystem state into one local-first context graph.

It is read-first. It does not replace task execution, Creative Studio, Project Intelligence, Workspace Intelligence, distributed runtime, or the Operating Environment. It links them.

## Backend

`website/backend/aegis_ai/unified_context.py` builds:

- context records
- cross-module relationships
- source summaries
- workspace timeline records
- cross-module insights
- global command routing previews

The API endpoints are:

- `GET /api/unified-context?workspace_root=...`
- `POST /api/unified-context/search`
- `POST /api/global-command/preview`
- `POST /api/global-command/submit`

## Sources

The engine reads from:

- task graph records
- task timeline events
- Project Intelligence
- project memory
- fix memory
- Creative Studio jobs and assets
- Workspace Intelligence health, recommendations, and events
- Operating Environment capabilities and read-only system signals
- distributed runtime queue jobs

## Records

Records are normalized as `UnifiedContextRecord` values. They can represent:

- projects
- architecture
- files
- tasks
- timeline events
- memory
- fix memory
- media jobs
- media assets
- workflows and automation signals
- desktop/system capabilities
- runtime jobs
- recommendations

Each record carries source, reference, status, importance, tags, related files, related tasks, related assets, and metadata.

## Relationships

Relationships connect records across systems. Examples:

- task touches file
- task has timeline event
- creative job produced asset
- generated UI asset can feed project work
- recommendation concerns file
- runtime job executes task
- memory belongs to project
- Operating Environment capability belongs to workspace

This is intentionally lightweight and deterministic today. It gives Aegis one place to reason about cross-module context before deeper semantic search is added.

## Unified Search

`POST /api/unified-context/search` searches across all normalized records. It supports:

- query text
- optional scopes
- result limit
- optional relationship expansion

The current implementation is lexical and importance-weighted. It is designed as the stable contract that future semantic search can improve without changing callers.

## Global Command System

The global command router previews where a request belongs:

- chat
- task engine
- Creative Studio
- research
- automation
- Operating Environment
- memory

It also explains:

- whether a task should be created
- whether approval is required
- whether rollback applies
- whether validation is required
- which endpoint or subsystem owns execution
- which context records are relevant

`POST /api/global-command/submit` can create a tracked task for commands that should become work. It does not bypass existing subsystem safety. Execution still flows through the owning endpoint, approvals, checkpoints, validation, repair, rollback, and telemetry.

## Convergence Rule

If a command mixes creative assets with coding work, coding wins and the assets become context. For example, “refactor the UI using the latest mockup” routes to the Task Engine with Creative Studio records attached as relevant context.

## Frontend

The existing Runtime surface now shows:

- source summaries
- cross-module insights
- recommended focus
- global command preview

This keeps convergence visible without adding another dashboard.

## Tests

Backend coverage lives in:

`website/backend/tests/test_unified_context.py`

Frontend API coverage lives in:

`website/frontend/src/api.test.ts`
