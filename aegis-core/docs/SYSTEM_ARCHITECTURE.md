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
- Safe workflow automation and scheduled maintenance jobs
- Project quality intelligence, health trends, and risk reports
- Knowledge graph and semantic project relationship queries
- Predictive planning, change simulation, architecture drift warnings, and scenario comparison
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
- Scheduled jobs can scan, summarize, report, and recommend, but risky actions still require approval.
- Quality snapshots write generated `.aegis` observability artifacts, not source changes.
- Knowledge graph refreshes write generated `.aegis` relationship artifacts, not source changes.
- Change simulations are advisory and read-only; they do not apply edits, run risky commands, or send cloud context.

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
10. Maintenance jobs flow through `.aegis/jobs-state.json`, `.aegis/jobs-log.md`, and `/v1/jobs`.
11. Project health trends flow through `.aegis/health-history.json`, generated quality reports, and `/v1/quality`.
12. Semantic project relationships flow through `.aegis/knowledge-graph.json`, generated graph summaries, and `/v1/knowledge/*`.
13. Predictive planning forecasts flow through `/v1/simulation/*` and feed Planner Agent task ordering.
14. Agent planning and repair loops move into Core.
15. Clients keep UI approvals, diff/apply/rollback, and editor-native affordances.

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

## Workflow Automation

Maintenance job state is stored in `.aegis/jobs-state.json` and surfaced through:

```text
GET  /v1/jobs?workspace=C:/path/to/project
POST /v1/jobs/run
```

Default jobs cover daily project scan, weekly roadmap update, dependency review, build health check, stale TODO scan, documentation drift check, recent changes summary, broken references check, project health report, quality intelligence snapshot, next best task, and validation status check.

Jobs may write generated `.aegis` memory and logs, including `.aegis/jobs-log.md`. They do not edit source files, delete files, install packages, run build/test/lint commands, or send cloud context without explicit approval. Clients or a local host invoke due jobs and triggers; Core does not run a hidden background daemon.

## Quality Intelligence

Project quality state is stored in `.aegis/health-history.json` and surfaced through:

```text
GET  /v1/quality?workspace=C:/path/to/project
POST /v1/quality/snapshot
```

The dashboard reports current health score, trend, warnings, failing systems, high-risk files, complexity hotspots, cleanup tasks, and recommended next improvement. Snapshots generate `.aegis/daily-health-report.md` and `.aegis/weekly-quality-summary.md`.

Planner Agent reads this dashboard when planning supervised work, so repeated validation failures, risky files, stale docs, and untested core modules can influence task order.

## Knowledge Graph

Knowledge graph state is stored in `.aegis/knowledge-graph.json` and surfaced through:

```text
GET  /v1/knowledge/graph?workspace=C:/path/to/project
POST /v1/knowledge/graph
POST /v1/knowledge/query
```

The graph links files, symbols, systems, APIs, UI components, services, tasks, roadmap items, architecture decisions, bugs, validation failures, risks, and agent-history events. Relationships include `uses`, `depends_on`, `calls`, `implements`, `breaks`, `related_to`, `tested_by`, and `mentioned_in_roadmap`.

Desktop can later render the visualization subset for system relationships, dependency clusters, unstable modules, roadmap links, and hotspots. Agents already consume graph summaries for impacted systems, related history, and suggested context.

## Predictive Planning And Change Simulation

Change simulation is read-only strategy support before edits. It is surfaced through:

```text
POST /v1/simulation/change
POST /v1/simulation/compare
```

The engine combines workspace scan data, the knowledge graph, quality intelligence, validation logs, dependency ripple, historical repair signals, requested focus files, and the proposed approach. It predicts:

- affected systems and impacted files
- likely build risks and likely test failures
- dependency ripple and cross-system edges
- architecture drift risk
- implementation difficulty, task size, likely blockers, validation cost, and rollback complexity

The response includes UI-ready fields for impact, confidence, validation cost, rollback complexity, and top warnings. Planner Agent consumes the simulation summary during orchestration planning and adds a dedicated split-planning task when high-risk or drift-prone work should be broken down before implementation.

Simulation is advisory. Clients still own approvals, diff previews, patch application, validation execution, and rollback.

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
