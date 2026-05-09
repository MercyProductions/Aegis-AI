# System Architecture

Auralith is moving from disconnected standalone tools to a shared local-first runtime.

```text
                Aegis Core
         local runtime / service layer
                     |
     +---------------+---------------+---------------+
     |               |               |               |
 Desktop App       Website        VS Code       Visual Studio
 Auralith UI       Web client      Extension     Extension
```

## Aegis Core Role

Aegis Core owns reusable intelligence and workflow services:

- Ollama integration and model routing
- Shared configuration
- Workspace scanning
- Project and solution memory
- File indexing, dependency graphs, and symbol indexes
- Roadmap generation
- Supervised autonomous task orchestration
- Specialized local agent roles
- Validation command detection and safe execution
- Agent planning, repair planning, rollback metadata, and approval contracts
- Diagnostics and logs

Core exposes these services through:

- A Python service layer
- A local FastAPI API
- An optional `aegis` CLI
- A versioned `/v1` integration contract for all clients

## Client Role

Clients should stop reimplementing shared intelligence. They should keep only the parts that are specific to their surface:

- Desktop App: primary Auralith UI, dashboards, orchestration, memory visualization
- Website: downloads, docs, accounts, licensing, future cloud features
- VS Code Extension: editor actions, selections, lightweight project workflows
- Visual Studio Extension: solution/project/Error List/Build Output integration

## Local-First Privacy Boundary

Aegis Core is designed to run on `127.0.0.1`. Project content stays local unless a future cloud feature is explicitly introduced and enabled.

Default assumptions:

- Local Ollama models are preferred.
- Secrets and protected paths are not read or edited.
- Edits are proposal-first and approval-based.
- Validation commands are explicit and non-destructive.
- Autonomous orchestration means staged queues, specialized owner agents, and approval gates, not uncontrolled edits.

## Migration Strategy

1. Clients call Core health/model APIs instead of directly duplicating Ollama logic.
2. Clients register themselves through `/v1/clients/register` when they start.
3. Clients call Core workspace scan and memory APIs.
4. Roadmap generation moves into Core.
5. Validation detection and logs move into Core.
6. Shared tasks flow through `.aegis/tasks.json` and `/v1/tasks`.
7. The Desktop App reads `/v1/ecosystem/dashboard` for connected clients, active projects, model status, diagnostics, roadmap summaries, and recent activity.
8. Specialized agent roles are exposed through `/v1/agents`.
9. Supervised goal queues flow through `.aegis/orchestration-queue.json` and `/v1/orchestration/*`.
10. Agent planning and repair loops move into Core.
11. Clients keep UI approvals, diff/apply/rollback, and editor-native affordances.

## Shared API Layer

New integrations should use `/v1` endpoints. Responses use a stable envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "kind": "workspace.scan",
  "workspace": "C:/path/to/project",
  "data": {}
}
```

The unversioned endpoints remain available during migration for compatibility with earlier local experiments.

## Shared Task Visibility

Tasks are stored in `.aegis/tasks.json` and surfaced through `/v1/tasks`. A task created from VS Code can be shown in the Desktop App dashboard and continued from Visual Studio as long as all clients point at the same workspace root.

Task statuses are intentionally plain:

- `planned`
- `running`
- `waiting_for_approval`
- `pending`
- `in_progress`
- `needs_approval`
- `validating`
- `blocked`
- `completed`
- `failed`
- `cancelled`
- `rolled_back`

## Supervised Orchestration

Orchestration state is stored in `.aegis/orchestration-queue.json` and surfaced through:

```text
POST /v1/orchestration/plan
GET  /v1/orchestration?workspace=C:/path/to/project
POST /v1/orchestration/step
```

Core records the objective, task list, active step, pending approvals, validation results, and rollback metadata. Clients still own showing proposed diffs, collecting approval, applying files, and restoring checkpoints.

Every orchestration task has an `owner_agent`. The current roles are Planner, Architect, Coder, Reviewer, Tester, Repair, and Documentation. Agent decisions are written to `agent-history.json`.

## Desktop Ecosystem Dashboard Contract

The Desktop App should use:

```text
GET /v1/ecosystem/dashboard?workspace=C:/path/to/project
```

The response includes:

- connected clients
- active projects
- active tasks
- model status
- diagnostics/log summaries
- roadmap excerpt
- validation commands
- recent activity
- shared branding tokens

This keeps the desktop dashboard as the orchestration surface without duplicating Core logic.

## Current Phase

This phase is ecosystem integration. It intentionally avoids a giant rewrite. The goal is stable communication, shared memory, shared task visibility, and consistent diagnostics while clients migrate incrementally.
