# Multi-Agent Engineering Runtime

Last updated: 2026-05-12

## Purpose

Aegis Core now exposes a formal multi-agent engineering runtime for workflow coordination. Agents are deterministic execution roles with explicit ownership, scoped memory, routing profiles, structured outputs, approval gates, retry limits, and persisted history.

This is not unbounded autonomous spawning. Agents do not secretly edit files, run commands, call cloud providers, or chat with each other in freeform loops. They coordinate through workflow tasks, handoff records, structured messages, and Core safety contracts.

## Initial Agents

- `planner_agent`: intake, task decomposition, dependency scheduling, approval planning, roadmap execution.
- `coder_agent`: change proposal, patch preview metadata, implementation notes, safe apply handoff.
- `validator_agent`: validation planning, command execution, result capture, failure classification.
- `repair_agent`: failure analysis, bounded repair planning, repair recommendations, escalation.
- `researcher_agent`: research questions, source synthesis, structured findings.
- `summarizer_agent`: completion summaries, memory updates, handoff summaries, timeline summaries.
- `architecture_agent`: architecture review, boundary analysis, impact analysis, dependency risk assessment.
- `routing_agent`: model route selection, capability matching, privacy review, fallback chain selection.

Each agent record includes capabilities, supported workflow types, preferred model profile, execution limits, memory scope, task ownership, status, and recent execution history.

## Lifecycle

1. A client creates a Core workflow with `POST /v1/workflows`.
2. Core materializes deterministic tasks and assigns each task a formal `agent_id`.
3. Core attaches memory-scope policy, context policy, communication contract, and model profile to each task.
4. Tasks advance through dependency order with approval checkpoints for file edits, validation commands, provider calls, and cloud context.
5. Agent handoffs are recorded when dependencies advance or a client delegates a task.
6. Validation failures create structured failure escalation records and queue repair roles where applicable.
7. Clients inspect active agents, handoff chains, context snapshots, and supervision state with `GET /v1/workflows/{workflow_id}/agents`.

## Coordination Rules

- Every workflow task has one explicit owner agent.
- Handoffs follow dependency order and are persisted in workflow logs/events.
- Agents exchange structured records: findings, validation reports, repair recommendations, architecture notes, risk assessments, and summaries.
- Agents receive scoped memory contexts instead of unrestricted workspace context.
- Routing is policy-driven through Core model profiles and `/v1/models/route`.
- File mutation, validation commands, provider calls, and cloud context remain approval-gated.

## Scoped Memory

Core records these task context policies:

- task-specific context
- file-scoped context
- dependency-scoped context
- roadmap-linked context
- workflow memory snapshots

Knowledge graph hooks provide architecture summaries, impact-analysis targets, project memory paths, and previous execution-history references. Context snapshots are generated for dashboards without requiring clients to ship the whole workspace to a model.

## Safety And Supervision

Core prevents runaway execution with:

- bounded retry counts
- bounded repair attempts
- max agents per workflow
- no recursive agent spawning
- approval gates for mutating or provider-backed actions
- unsafe-operation blocking
- persisted audit history
- structured failure escalation

Delegation into mutating agents or approval-gated tasks records a `waiting_input` checkpoint until the client passes explicit approval.

## APIs

- `GET /v1/agents/runtime`
- `GET /v1/workflows/agent-runtime`
- `GET /v1/workflows/{workflow_id}/agents`
- `POST /v1/workflows/{workflow_id}/agents/delegate`
- `POST /v1/workflows/{workflow_id}/step` with `action: "delegate_task"`

## Observability

Agent observability tracks:

- owned tasks
- completed and failed tasks
- waiting-input tasks
- retry counts
- validation success/failure counts
- repair success/failure counts
- model profile usage
- handoff count
- escalation frequency
- failure patterns

Token usage is represented in the contract but remains provider-dependent until model providers return reliable usage metadata.

## Client Responsibilities

Clients should display:

- active workflow and active agent
- task owner and handoff chain
- approval checkpoints
- scoped context preview
- validation and repair reports
- model routing explanation
- rollback/checkpoint availability for mutating workflows

Clients still own UX-specific context selection, diff preview, editor affordances, and user approvals.
