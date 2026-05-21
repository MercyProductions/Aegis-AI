# Deep Engineering Intelligence

Auralith engineering intelligence is the Core-owned quality layer that improves workflow reasoning before agents, Autopilot, or clients execute work. It is deterministic and local-first: it reads workspace scan data, the knowledge graph, validation history, quality gates, and `.aegis` memory, then returns inspectable guidance. It does not call model providers, edit source files, run commands, or bypass approvals.

## Purpose

The layer focuses on engineering quality rather than platform expansion:

- Architecture reasoning across runtime boundaries, API relationships, service interactions, dependency hotspots, and project-wide impact.
- Context assembly that ranks files by target scope, dependency distance, validation value, entry-point relevance, and memory relevance.
- Validation intelligence that prioritizes targeted checks, build/test/lint/type gates, dependency-aware validation, flaky signals, and escalation rules.
- Repair intelligence that extracts root-cause candidates, selects repair strategies, detects repeated failed repair patterns, scopes changes by impact, and recommends rollback when confidence drops.
- Roadmap intelligence that decomposes work into ordered phases, predicts milestones, estimates risk, and identifies blockers.
- Workflow prediction for execution risk, likely failures, validation scope, rollback probability, deployment risk, duration, and reliability.
- Benchmark scoring for feature quality, repair quality, validation accuracy, roadmap quality, orchestration efficiency, rollback reduction, execution reliability, and memory relevance.

## Architecture

`aegis_core.engineering_intelligence` composes existing Core systems:

- `WorkspaceScanner` for file inventory, frameworks, build files, test files, entry points, and validation command discovery.
- Knowledge graph APIs for relationships, impact analysis, symbol/API/service context, and architecture summaries.
- Quality and quality-gate dashboards for current risks, blockers, validation history, and flaky signals.
- Project memory files under `.aegis` for prior workflow, repair, validation, roadmap, Autopilot, and personal-intelligence signals.
- Safety path normalization for target files and context previews.

The output is stored under `.aegis` when `persist` is enabled:

- `.aegis/engineering-intelligence.json`
- `.aegis/engineering-context-assembly.json`
- `.aegis/engineering-intelligence-benchmarks.json`

## Context Assembly

Context assembly is intentionally bounded. Direct targets are ranked first, then impact-analysis neighbors, validation targets, entry points, tests, build configs, README files, graph semantic matches, and relevant memories. Each selected file includes:

- path
- score
- reasons
- sources
- roles
- estimated size
- safe text preview

The `token_budget` controls how much context is selected. Excluded files are retained with an exclusion reason so clients can explain why a file was not loaded.

## Validation Intelligence

Validation planning combines detected commands, impact-analysis validation targets, quality risks, and workflow profile rules. It returns:

- detected commands
- prioritized validations
- regression prediction
- flaky-test candidates
- confidence score
- escalation rules
- human-readable explanation

This is advisory. Actual command execution remains under the validation runtime, terminal safety rules, approval gates, and quality gates.

## Repair Intelligence

Repair planning uses latest validation output, impact analysis, quality blockers, and repair history. It returns:

- root-cause candidates
- selected repair strategies
- repeated failed-repair detection
- architecture-aware repair scope
- rollback recommendation
- repair confidence
- stopping conditions

The repair plan is designed to stop repetitive loops early. When the same root-cause signature repeats or repair scope expands beyond the impact area, Autopilot should escalate to the user instead of continuing.

## Autopilot Integration

Autopilot run creation now captures a read-only `deep_engineering_intelligence` snapshot. Supervision payloads expose the same field so Website, Desktop, VS Code, and Visual Studio can show:

- selected context and context budget usage
- architecture reasoning
- validation and repair strategies
- roadmap decomposition
- workflow risk and duration prediction
- benchmark scores
- reasoning and decision explanations

This snapshot does not replace the existing Autopilot trust scorecard. It enriches it with graph-aware and memory-aware engineering signals.

## Endpoints

```text
GET  /v1/engineering-intelligence
POST /v1/engineering-intelligence/analyze
POST /v1/engineering-intelligence/context
POST /v1/engineering-intelligence/validation-plan
POST /v1/engineering-intelligence/repair-plan
POST /v1/engineering-intelligence/roadmap-plan
POST /v1/engineering-intelligence/predict
POST /v1/engineering-intelligence/benchmarks/run
GET  /v1/engineering-intelligence/benchmarks
```

All endpoints return standard Core envelopes and preserve local-first behavior. Clients should treat the output as planning and supervision context, not as authorization to apply changes.

## Current Limitations

- The layer is deterministic and heuristic. It improves model inputs and workflow decisions but does not prove semantic correctness by itself.
- Relationship quality depends on the current knowledge graph analyzers and may be shallow for unsupported language features.
- Flaky-test detection uses available quality-gate history and slow/failing signals; it is not yet a full statistical flake detector.
- Benchmarks score the quality of Core intelligence signals, not external model output quality.
- Context previews are intentionally bounded and may omit large files unless they are direct targets.
