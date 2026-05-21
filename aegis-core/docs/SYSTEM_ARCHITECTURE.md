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
- Engineering operations for release readiness, debt, lifecycle, maintenance, productivity, and cross-project coordination
- Adaptive personal engineering intelligence for local preference memory, workflow/style learning, reusable pattern suggestions, habit analysis, and context personalization
- Validation command detection and safe execution
- Core-owned editing runtime for proposed file changes, patch preview metadata, selected/all apply, checkpoint creation, checkpoint restore, validation result storage, operation jobs, and project activity
- Unified workflow graph runtime for long-running cross-client workflows, dependency chains, pause/resume/cancel/retry, event streams, client sync, and observability
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
- Edits are proposal-first, approval-based, workspace-local, and checkpointed before writes.
- Validation commands are explicit and non-destructive.
- Long-running workflows are persisted, inspectable, pauseable, cancellable, and resumable after restart.
- Autonomous orchestration means staged queues, specialized owner agents, and approval gates, not uncontrolled edits.
- Scheduled jobs can scan, summarize, report, and recommend, but risky actions still require approval.
- Quality snapshots write generated `.aegis` observability artifacts, not source changes.
- Knowledge graph refreshes write generated `.aegis` relationship artifacts, not source changes.
- Change simulations are advisory and read-only; they do not apply edits, run risky commands, or send cloud context.
- Engineering operations dashboards recommend coordination work but do not make release decisions or run risky actions.
- Personal engineering profiles are local, inspectable, resettable, and persisted only when explicitly requested or when explicit preferences are supplied.

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
14. Engineering operations dashboards flow through `/v1/operations/*`.
15. Adaptive personal engineering guidance flows through `/v1/personal-intelligence/*`.
16. Core-owned editing endpoints become the shared authority for proposed changes, apply, checkpoints, restore, validation result storage, operation jobs, and activity.
17. Core workflow runtime becomes the shared authority for workflow IDs, task graphs, dependencies, progress, event streams, client sync, timelines, retries, cancellation, and audit history.
18. Agent planning and repair loops move into Core.
19. Clients keep UI approvals, diff review presentation, editor APIs, IDE build/error integrations, and native affordances.

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

Core records the objective, task list, active step, pending approvals, validation results, and rollback metadata. Clients still own showing proposed diffs and collecting approval. Once approved, clients should migrate file apply, checkpointing, restore, validation result storage, and operation tracking onto the Core-owned editing runtime.

Every orchestration task has an `owner_agent`. The current roles are Planner, Architect, Coder, Reviewer, Tester, Repair, and Documentation. Agent decisions are written to `agent-history.json`.

## Core-Owned Editing Runtime

Editing runtime state is stored under the workspace `.aegis` folder:

```text
.aegis/editing-proposals.json
.aegis/operation-jobs.json
.aegis/editing-activity.json
.aegis/validation-results.json
.aegis/editing-log.md
.aegis/checkpoints/<checkpoint-id>/manifest.json
```

The first active editing contract is surfaced through:

```text
POST /v1/changes/propose
POST /v1/changes/apply
POST /v1/checkpoints/create
GET  /v1/checkpoints?workspace=C:/path/to/project
POST /v1/checkpoints/restore
POST /v1/validation/run
GET  /v1/jobs/{job_id}?workspace=C:/path/to/project
GET  /v1/projects/{project_id}/activity?workspace=C:/path/to/project
```

This makes Core the shared runtime authority for file-change application, rollback safety, validation records, and operation tracking. Website should eventually delegate its `/api/apply`, `/api/checkpoints`, `/api/restore-checkpoint`, `/api/validate`, and repair-loop write bookkeeping to these Core contracts. Desktop, VS Code, and Visual Studio should consume the same contracts after their approval UI has shown the proposed diff or preview.

The safety model is intentionally conservative:

- paths are normalized and must stay inside the workspace
- ignored, generated, dependency, hidden-directory, and secret-like paths are rejected
- dry runs return preview metadata without writing
- apply creates a checkpoint before any write or delete
- restore creates a pre-restore checkpoint before mutating files
- validation output is scrubbed and persisted as Core activity

## Unified Workflow Runtime

The workflow runtime is the next layer above editing, validation, scan, quality, and knowledge services. It is surfaced through:

```text
POST /v1/workflows
GET  /v1/workflows?workspace=C:/path/to/project
GET  /v1/workflows/{workflow_id}?workspace=C:/path/to/project
POST /v1/workflows/{workflow_id}/step
POST /v1/workflows/{workflow_id}/pause
POST /v1/workflows/{workflow_id}/resume
POST /v1/workflows/{workflow_id}/cancel
POST /v1/workflows/{workflow_id}/retry
GET  /v1/workflows/{workflow_id}/events?workspace=C:/path/to/project
GET  /v1/workflows/events?workspace=C:/path/to/project
GET  /v1/workflows/stats?workspace=C:/path/to/project
GET  /v1/workflows/agent-runtime
POST /v1/clients/sync
GET  /v1/client-sync?workspace=C:/path/to/project
POST /v1/workspaces/intelligence
```

Persistent state lives in:

```text
.aegis/workflow-runtime.json
.aegis/workflow-events.json
.aegis/client-sync.json
.aegis/workflow-audit.md
.aegis/workspace-intelligence.json
```

Workflow tasks support:

- parent/child relationships
- dependency chains
- retries and retry limits
- cancellation
- pause/resume at the workflow level
- execution statuses: `pending`, `queued`, `running`, `waiting_input`, `validating`, `repairing`, `completed`, `failed`, `cancelled`
- progress percentages
- timestamps and structured logs
- approval gates and deterministic role ownership

The first workflow types are:

- `chat_request`
- `generate_feature`
- `validate_project`
- `repair_project`
- `continue_roadmap`
- `build_project`
- `scan_workspace`
- `benchmark_models`
- `generate_media`
- `research_task`

The role runtime is deliberately plain. `planner`, `coder`, `validator`, `repair_agent`, `researcher`, and `summarizer` are task owners and audit labels. They do not imply hidden autonomy. Automatic execution is limited to deterministic local operations such as workspace intelligence refresh, roadmap refresh, and approved validation. File edits route through the Core editing runtime; provider/media/research/benchmark tasks wait for explicit approval and client-supplied results until dedicated safe executors are implemented.

Clients should subscribe to SSE streams instead of polling when they need live updates. The stream emits persisted workflow events, so a client can reconnect after restart and recover missed updates from the timeline.

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

## Autonomous Engineering Operations

Engineering operations coordinates long-term project work without taking control away from humans. It is surfaced through:

```text
GET  /v1/operations?workspace=C:/path/to/project
POST /v1/operations/dashboard
```

Operations combines current Core signals from quality intelligence, knowledge graph relationships, shared tasks, scheduled jobs, validation, roadmap memory, dependencies, and agent history. It reports:

- release readiness, milestones, implementation phases, validation checkpoints, and release notes focus
- technical debt signals, cleanup recommendations, refactor priorities, and stability tasks
- lifecycle stage and recommendation mode
- long-term risk monitoring for instability, validation failures, architecture complexity, dependency risk, and performance regressions
- maintenance scheduling for refactor windows, dependency review, validation sweeps, optimization passes, and docs refreshes
- productivity intelligence for recurring pain points, slow workflows, repeated manual tasks, bottlenecks, repeated bug categories, and automation opportunities
- cross-project awareness for shared libraries, shared tooling, architecture patterns, and repeated systems

Operations is read-only and recommendation-first. It may coordinate what should happen next, but file edits, deletions, validation/build commands, dependency installs, cloud context, and release decisions remain approval-gated.

## Adaptive Personal Engineering Intelligence

Personal intelligence is the local alignment layer for developer preferences and recurring work patterns. It is surfaced through:

```text
GET  /v1/personal-intelligence?workspace=C:/path/to/project
POST /v1/personal-intelligence/profile
POST /v1/personal-intelligence/reset
```

The default `GET` call is read-only and does not create or update profile state. `POST /v1/personal-intelligence/profile` may include explicit preferences and `persist: true`; persisted profile state lives in `.aegis/personal-engineering-profile.json`. `POST /v1/personal-intelligence/reset` deletes that local profile snapshot.

The service summarizes:

- preferred project structures, frameworks, naming conventions, architecture styles, validation workflows, and task ordering
- coding style tendencies, abstraction preferences, commenting style, error handling style, UI layout patterns, and architecture decisions
- recurring systems across projects, including API, auth, UI, agent, roadmap, persistence, validation, settings, and model-runtime patterns
- personalized recommendations, workflow optimization opportunities, engineering habit signals, and agent guidance
- context personalization for roadmap generation, diff explanations, planning depth, summaries, and validation detail

Privacy constraints are explicit: no cloud calls, no source content persistence, no credentials, no API keys, and no token-like preference keys. The output includes the local profile path and reset controls so clients can make the feature transparent.

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
