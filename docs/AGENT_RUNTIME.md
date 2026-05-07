# Agent Runtime

`AgentEngine` is the public runtime facade. The current refactor keeps that import path stable while moving behavior into smaller modules.

## Modules

- `aegis_ai.agent.AgentEngine`: orchestrates a turn and preserves existing API behavior.
- `aegis_ai.agent_runtime.contracts`: shared runtime dataclasses such as `AgentDraft` and `MissionAnchor`.
- `aegis_ai.agent_runtime.response_changes`: generated file-change normalization before workspace application.
- `aegis_ai.multi_agent.MultiAgentCoordinator`: internal Planner, Architect, Code, Review, Validation, Repair, and Memory agent event recording plus handoff and iteration-limit enforcement.
- `aegis_ai.task_engine`: task graph status normalization, state transition validation, and default subtask definitions.
- `aegis_ai.project_intelligence.ProjectIntelligenceEngine`: persistent project profiling, architecture mapping, file importance scoring, memory synthesis, and smart context selection.
- `aegis_ai.workspace_operations.WorkspaceOperationsEngine`: permission-aware workspace watcher snapshots, health metrics, recommendations, scheduled job records, git summaries, and long-term project memory signals.
- `aegis_ai.distributed_runtime.DistributedRuntimeManager`: local-first worker runtime policy, execution queue selection, LAN/remote trust gates, hybrid model routing, sync manifests, and runtime observability.
- `aegis_ai.productization.ProductizationEngine`: stable API contract catalog, plugin manifest validation, enterprise policy profiles, runtime recovery snapshots, and reliability metric aggregation.
- `aegis_ai.ecosystem.EcosystemEngine`: reusable package manifests, workflow templates, workflow-to-task-graph execution, shared intelligence profiles, organization policy, knowledge graph snapshots, search, reproducibility, and governance trust signals.
- `aegis_ai.autonomous_engineering.AutonomousEngineeringEngine`: supervised objective programs, multi-phase planning records, dry-run estimates, approval gates, bounded iteration, parallel role assignment, continuous verification signals, refactor plans, goal memory, explainability, and analytics.
- `aegis_ai.routing.ModelRouter`: chooses model/provider candidates for a request.
- `aegis_ai.task_planner.TaskPlanner`: turns routing signals into planning metadata.
- `aegis_ai.context_budget.ContextBudgetManager`: ranks and budgets context files.
- `aegis_ai.model_execution.ModelExecutionPlanner`: decides model attempt strategy.
- `aegis_ai.model_attempt_executor.ModelAttemptExecutor`: executes provider attempts and fallback attempts.
- `aegis_ai.validation.ValidationManager`: discovers, stores, and runs validation recipes.
- `aegis_ai.workspace.WorkspaceManager`: enforces file safety, applies changes, and manages checkpoints.
- `aegis_ai.storage.EventStore`: records tasks, events, telemetry, repair attempts, and memory.

## Turn Flow

1. The API passes an `AgentRequest` into `AgentEngine.run`.
2. Mission anchors and history are inspected so vague follow-ups preserve the previous workspace and goal.
3. Workspace files, project metadata, validation state, memory, and saved Project Intelligence are gathered.
4. Router and planner metadata are built for model selection and task shaping.
5. The selected local/provider model returns structured JSON.
6. The payload becomes an `AgentDraft`.
7. Generated paths are normalized by `agent_runtime.response_changes`.
8. Project work creates a parent task, default subtasks, and a multi-agent chain event before moving through explicit states like `planning`, `running`, `validating`, `repairing`, and `completed`.
9. Planner Agent records the plan, risks, selected context, and handoff to Architect Agent.
10. Architect Agent records structure and boundary review, then hands off to Code Agent.
11. Code Agent records the implementation draft; Review Agent records deterministic findings before apply or validation.
12. If file application is requested, `WorkspaceManager.apply_changes` creates a checkpoint before writing, and the task records the changed files plus checkpoint id.
13. Validation Agent selects and interprets validation commands.
14. Failed validation can enter Repair Agent, which records repair attempts, approval pauses, rollback, exhausted attempts, and handoffs back to Validation Agent.
15. Memory Agent records durable outcome context before the final task summary is persisted.
16. `EventStore` records task state, events, context budgets, model attempts, fallback behavior, project memory, and Project Intelligence snapshots.

## Multi-Agent Events

Internal agents communicate through `ToolEvent` rows, not free-form chat. Event kinds are structured as `agent.chain`, `agent.handoff`, `agent.planner`, `agent.architect`, `agent.code`, `agent.review`, `agent.validation`, `agent.repair`, `agent.memory`, `agent.approval`, and `agent.control`. Payloads include role names, iteration counts, max iterations, selected files, changed paths, commands, checkpoints, failures, and approval paths.

Normal chat remains a single-agent fallback. A multi-agent chain is created only when the turn tracks project work, applies changes, requests validation, or auto-validation is enabled.

## Project Intelligence Context

The runtime treats Project Intelligence as a cached understanding layer, not as a replacement for file reads. When a snapshot exists, `AgentEngine` uses it to bias context toward main entry files, high-importance files, risk-sensitive files, known API routes, validation requirements, coding conventions, prior failures, and project memories. If no snapshot exists yet, normal workspace scanning and context budgeting still work; the API can build a snapshot lazily through workspace profile or re-index requests.

## Workspace Operations Context

Workspace Operations is adjacent to the turn runtime. It can observe files, dependencies, git state, validation drift, prior tasks, and memory over time, then persist recommendations that later become tracked tasks. It does not bypass the runtime: recommendation fixes enter the task graph, use normal multi-agent handoff if executed, and retain approval/checkpoint/validation/repair behavior.

## Distributed Execution Context

Distributed Runtime is also adjacent to the turn runtime. It does not replace `AgentEngine.run`; it gives task, validation, build, indexing, telemetry, benchmark, repair, and sync work a persistent queue plus worker assignment metadata. Local jobs can execute in-process through existing validation, command, telemetry, benchmark, and Project Intelligence helpers. Remote jobs are assigned only after explicit dispatch permission and trusted worker registration.

When a queued job references a task id, the runtime writes structured timeline events for job start, validation start, command execution, repair queueing, and job finish. It does not silently apply file edits. Repair jobs created by validation failure are follow-up queue records and task events; actual code repair still goes through the normal approval, checkpoint, validation, and memory flow.

## Ecosystem Workflow Context

Reusable ecosystem workflows are task graph templates. Running a workflow creates a parent task plus one subtask per workflow step, records `workflow.created` and `workflow.step.created` timeline events, and preserves approval requirements as task state instead of bypassing the runtime. Workflow packages and shared intelligence profiles can influence future planning and validation, but file edits still flow through the normal agent, approval, checkpoint, validation, repair, and memory path.

## Autonomous Objective Context

Controlled autonomous objectives sit above the task graph rather than replacing it. An objective stores the long-running goal, current phase, iteration counts, safety limits, approval gate ids, linked task ids, simulation ids, and goal memory. Its phases follow discovery, planning, implementation, validation, review, optimization, and finalization.

Iteration advances phase records, writes objective timeline events, creates related task graph entries when useful, records verification signals, and updates explainability. Approval gates pause the objective in `needs_approval`; approving a gate lets the next iteration continue, while rejection pauses the objective with a clear reason. The objective engine does not write files directly. Code changes remain owned by the task runtime and must pass the existing approval, checkpoint, validation, repair, and rollback path.

## Task Timeline

Task timeline events are regular `ToolEvent` rows scoped by `task_id`. State transitions emit events such as plan creation, execution start, approval wait, validation start, repair start, completion, failure, cancel, approval, and retry. Multi-agent execution adds role-specific events and handoffs to the same timeline. Task artifacts are read through `EventStore.task_artifacts`, which combines task columns with command, validation, and repair records.

## Refactor Rule

New modules should be imported by `agent.py` and exposed through existing public behavior first. Direct endpoint behavior, `AgentResponse` shape, file safety, telemetry payloads, and repair semantics must stay stable while code moves.
