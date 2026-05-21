# Engineering Execution Pipeline

Last updated: 2026-05-12

## Purpose

Aegis Core now owns the shared engineering execution contract. Website, Desktop, VS Code, and Visual Studio can use the same local-first runtime to plan, track, validate, repair, approve, checkpoint, apply, and summarize software work.

This is intentionally supervised. Core does not secretly edit files, install packages, call cloud providers, or run arbitrary commands. Clients still present context, diffs, approvals, and editor-specific UX.

## Lifecycle

The Core pipeline stages are:

1. `intake`
2. `workspace_analysis`
3. `planning`
4. `task_decomposition`
5. `implementation`
6. `validation`
7. `repair`
8. `review`
9. `approval`
10. `checkpoint`
11. `apply`
12. `completion_summary`

Checkpoint is before apply by design. Apply must go through the Core editing runtime, which creates checkpoints, normalizes paths, rejects unsafe paths, supports dry runs, stores validation/repair metadata, and records operation jobs/activity.

## Stored State

Core stores execution state under the workspace `.aegis` folder:

- `engineering-executions.json`
- `engineering-events.json`
- `engineering-journal.json`
- `engineering-memory.json`
- `engineering-memory.md`
- `engineering-audit.md`

The execution record contains:

- goal, constraints, mode, source client, and target files
- estimated risk and safety controls
- knowledge graph impact analysis for target files when a persisted graph is available
- stage graph and task dependency graph
- validation checkpoints and repair checkpoints
- rollback strategy and checkpoint references
- approvals, rollbacks, modified files, warnings, and errors
- validation chain and repair history
- execution metrics and journal entries

## Execution Modes

- `safe_assisted`: default mode; implementation, validation, checkpoint, and apply stay approval-gated.
- `approval_every_step`: every stage waits for approval.
- `semi_autonomous`: non-mutating stages can advance; file mutation still requires approval/checkpoint.
- `autonomous_validate_only`: Core may run validation loops but skips implementation/apply.
- `roadmap_execution`: links execution to roadmap phase/item metadata.
- `repair_only`: focuses on validation failure capture and bounded repair attempts.

## Safety Model

Core enforces:

- checkpoint before apply
- workspace-local normalized relative paths
- restricted directory and secret-like path rejection
- binary file protection
- max file modification limits
- diff preview/dry-run support through editing proposals
- validation result storage
- repair retry limits
- rollback and audit history

Execution planning uses `/v1/knowledge/impact-analysis` where possible to identify affected files, riskier dependency surfaces, validation targets, and repair scope. If the graph is missing or stale, Core still creates a conservative execution plan and records the knowledge warning rather than blocking the workflow.

Repair loops stop when validation passes, the repair attempt limit is reached, the execution is cancelled/failed, or a stage waits for approval/input.

## API Surface

- `GET /v1/engineering/modes`
- `POST /v1/engineering/executions`
- `GET /v1/engineering/executions`
- `GET /v1/engineering/executions/{execution_id}`
- `POST /v1/engineering/executions/{execution_id}/step`
- `GET /v1/engineering/executions/{execution_id}/timeline`
- `GET /v1/engineering/memory`
- `POST /v1/engineering/memory`
- `GET /v1/engineering/metrics`
- `POST /v1/engineering/roadmap/execute`

## Client Responsibilities

Clients should:

- register with Core and attach active workflow/execution IDs
- show plan, risk, target files, validation requirements, and rollback strategy
- preview proposed diffs before apply
- collect approvals for validation, checkpoint, and apply
- call Core editing endpoints for file mutation
- show validation/repair loop state from Core timeline contracts
- preserve editor-specific context, such as solution/startup project awareness in Visual Studio

## Website Migration Path

Website remains the compatibility gateway for React and product-specific APIs. Its autonomous engineering route now attempts to create a linked Core engineering execution and falls back to the existing Website engine if Core is offline.

Next migrations should move Website objective iteration, validation/repair loops, and apply/checkpoint orchestration onto Core execution IDs while preserving the existing `/api/autonomous-engineering/*` response models.
