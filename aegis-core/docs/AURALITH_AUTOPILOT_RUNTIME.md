# Auralith Autopilot Runtime

Auralith Autopilot is the supervised autonomous engineering runtime for Auralith OS. It coordinates the existing Core engineering execution pipeline, workflow graph, editing runtime, agent runtime, validation system, terminal runtime, checkpoints, memory, and replay logs.

Autopilot is not unrestricted autonomy. It is an inspectable, approval-aware coordinator that keeps Core safety systems in charge of file edits, validation, terminal execution, checkpoints, rollback, and workflow state.

## Core Responsibilities

Autopilot owns the production contract for long-running engineering work:

- Create a supervised run with an objective, mode, workflow type, constraints, target files, roadmap items, and validation commands.
- Link each run to a Core engineering execution and workflow ID.
- Track current task, active agent, pending approvals, files in scope, validation chain, repair attempts, terminal jobs, checkpoint status, rollback availability, and risk level.
- Persist run state, events, audit history, and execution memory under the workspace `.aegis` folder.
- Expose replayable timelines for diagnostics, UI supervision, and support exports.

## Execution Modes

The first formal modes are:

- `suggest_only`: analysis and proposals only. Mutating stages, validation execution, repair, checkpoint, apply, and terminal commands require approval.
- `approval_each_step`: every pipeline stage pauses for explicit approval.
- `semi_autonomous`: analysis and planning can advance; implementation, repair, terminal commands, checkpoint, and apply require approval.
- `roadmap_autopilot`: roadmap phase execution with milestone validation and checkpoint expectations.
- `repair_autopilot`: bounded validation/repair loop with apply still gated by checkpoint and approval.
- `validation_autopilot`: validation-focused mode with no file modification by default.
- `experimental_full_autopilot`: lab mode for broader supervised automation; apply still requires approval and checkpointing.

Every mode defines approval rules, autonomy limits, allowed workflow types, validation requirements, checkpoint rules, rollback rules, and terminal execution rules.

## Specialized Autopilot Systems

Autopilot now separates execution mode from workflow specialization. A mode defines autonomy boundaries; a specialization tunes orchestration, validation, repair, memory, model routing, observability, and UI supervision without weakening the mode safety rules.

Initial specializations:

- `feature_autopilot`: roadmap and feature implementation sequencing with milestone checkpoints, architecture-aware edits, targeted validation, and feature quality benchmarks.
- `repair_autopilot`: build/test failure analysis with root-cause repair loops, repeated-failure detection, dependency-aware validation, repair confidence scoring, and rollback recommendations.
- `refactor_autopilot`: conservative dependency-safe refactoring with impact analysis, symbol/reference checks, broader regression validation, and higher rollback bias.
- `deployment_autopilot`: CI/CD and release preparation with pipeline gates, dry-run deployment validation, secret/config risk handling, rollback readiness, and release reliability benchmarks.
- `workspace_intelligence_autopilot`: read-mostly architecture analysis, dependency summaries, roadmap generation, technical debt review, onboarding documentation, and indexing freshness checks.

Clients can pass `specialization` to `POST /v1/autopilot/start`. If omitted, Core infers a profile from workflow type, objective, target files, roadmap context, and metadata. Supervision payloads expose `specialization`, `execution_strategy`, `validation_strategy`, `repair_strategy`, `model_routing`, `memory_scope`, `specialized_observability`, and `specialization_benchmarks` so Website, Desktop, VS Code, and Visual Studio can explain the active strategy.

## Lifecycle

Autopilot runs follow the Core engineering pipeline:

1. Intake
2. Workspace analysis
3. Planning
4. Task decomposition
5. Implementation
6. Validation
7. Repair
8. Review
9. Approval
10. Checkpoint
11. Apply
12. Completion summary

The underlying engineering execution pipeline may pre-complete non-mutating preparation stages when enough context is already available. Autopilot still exposes the linked execution timeline so clients can replay what was completed, skipped, waiting, validating, repairing, or blocked.

## Safety Model

Autopilot preserves these invariants:

- No apply without Core editing runtime safety checks.
- No execution across Core governance policy violations.
- No apply without checkpoint and approval gates.
- No unrestricted terminal execution.
- No path traversal or workspace escape.
- No repair loops beyond configured retry limits.
- No hidden file modifications.
- No silent completion after failed validation.
- No unbounded autonomous iteration.
- No unbounded action payload/context growth.
- No hidden trust state: confidence, risk, validation confidence, repair confidence, and rollback readiness are exposed with every refreshed run.

When a run reaches a gated stage, Autopilot queues an approval request with stage, reason, required action, risk level, workflow ID, and run ID. Clients should render this queue prominently.

Autopilot also evaluates Core governance policy at run start and before risky actions. Policy violations are stored on the run under `governance`; approval-gated policy findings create a `policy_governance` approval request, and blocked policy findings stop the action from executing until the user/client resolves the violation or changes scope.

## Trust And Confidence Scoring

Every run now exposes a `trust_scorecard` with:

- `confidence_score`: overall execution confidence after risk, validation, repair, terminal, approval, and iteration signals.
- `validation_confidence`: confidence in the latest validation coverage/result.
- `repair_confidence`: confidence in the current repair loop and whether it is repeating failed patterns.
- `regression_risk`: risk score from target files, sensitive paths, failed validation, repair failures, and rollback readiness.
- `rollback_readiness`: checkpoint/rollback availability score.
- `execution_risk_level`: normalized `low`, `medium`, or `high` risk label.

The scorecard is deterministic and inspectable. It is not a model judgment. It is computed from Core runtime state so Website, Desktop, VS Code, and Visual Studio can show the same trust status.

## Bounded Autonomy

Autopilot enforces per-mode limits for:

- autonomous iterations
- repair attempts
- file modification scope
- terminal command count
- action payload/context size

When a limit is reached, Autopilot records a blocked action, queues approval, and keeps the run inspectable through replay. Repetitive failed repairs are detected by root-cause metadata and escalated before the loop can keep producing similar attempts.

## Explainability And Prediction

Runs expose:

- `predictions`: likely duration, likely validation targets, rollback need, and failure hotspots.
- `validation_intelligence`: targeted validation plan, coverage state, recommended order, and escalation reason.
- `deep_engineering_intelligence`: read-only graph-aware and memory-aware planning context with architecture reasoning, selected context, validation priorities, repair strategy, roadmap decomposition, workflow risk prediction, benchmark scores, and explainability decisions.
- `checkpoint_intelligence`: milestone/risk-triggered checkpoint recommendations and checkpoint health.
- `explanations`: user-facing reasons for task selection, risk, file scope, validation failure, and pauses.
- `decision_log`: audit-ready decisions for approvals, blocked actions, simulation, validation, repair, checkpoint, terminal jobs, rollback, and completion.

## Simulation

Clients can call the existing action endpoint with `action: "simulate"` to produce a dry-run preview. Simulation reports remaining stages, files in scope, validation targets, blocked conditions, confidence, regression risk, rollback readiness, and recommended next actions. It never modifies files or runs commands.

## Repair Loops

Repair is structured and bounded:

- Validation failures can move a run into `repairing`.
- Repair attempts are recorded with metadata and linked to the validation chain.
- Each mode has a `max_repair_attempts` limit.
- After the limit, Autopilot escalates to `waiting_approval`.
- Repeated failed repair patterns escalate early with a rollback recommendation when appropriate.
- Applying repair output still requires checkpoint and approval.

## Terminal Runtime

Autopilot can launch supervised terminal jobs through the Core runtime interaction layer. Terminal commands:

- Require approval.
- Use the runtime command safety checker.
- Capture stdout/stderr, status, timeout, and exit code.
- Are linked to workflow ID, execution ID, and Autopilot run ID.
- Default to dry-run unless the client explicitly requests execution.

## Persistent Memory

Autopilot writes local project memory to `.aegis/autopilot-memory.json`.

Tracked categories include:

- Completed roadmap phases
- Prior failures
- Repair outcomes
- Preferred execution strategies
- Validation history
- Workflow outcomes
- Per-specialization workflow, repair, validation, roadmap, deployment, and architecture memories

This memory is local-first, inspectable, editable as JSON, and not cloud-synced by Core.

## API Endpoints

New Core endpoints:

- `GET /v1/autopilot/modes`
- `POST /v1/autopilot/start`
- `GET /v1/autopilot/runs`
- `GET /v1/autopilot/runs/{autopilot_id}`
- `POST /v1/autopilot/runs/{autopilot_id}/action`
- `GET /v1/autopilot/runs/{autopilot_id}/replay`
- `GET /v1/autopilot/supervision`
- `GET /v1/autopilot/observability`
- `GET /v1/autopilot/memory`
- `GET /v1/autopilot/client-hooks`

## Client Responsibilities

Website and Desktop should present Autopilot Center views:

- Active workflow
- Active agent
- Current task
- Roadmap progress
- Execution graph
- Approval queue
- Validation chain
- Repair history
- Live logs
- Runtime status
- Rollback availability
- Confidence, regression risk, validation confidence, and rollback readiness
- Active safety restrictions and blocked actions

VS Code and Visual Studio should expose integration hooks:

- Start Autopilot
- Pause/resume/cancel
- Approve/reject
- Inspect diffs
- Review validation results
- Roll back checkpoints

Clients must keep approval and rollback controls visible whenever a run can modify state.

## Known Limitations

- Autopilot currently coordinates existing deterministic Core systems; it does not yet perform model-generated coding by itself.
- Desktop, Website, VS Code, and Visual Studio UI surfaces still need richer native Autopilot Center implementations.
- Terminal execution is wired through Core runtime interaction, but remote/distributed terminal offload should remain conservative until trust and node policies mature further.
- Multi-hour real-world Autopilot sessions still need dogfooding and stress validation beyond focused unit coverage.
