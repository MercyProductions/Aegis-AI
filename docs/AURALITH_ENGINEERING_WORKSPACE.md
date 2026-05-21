# Auralith Engineering Workspace

Auralith Engineering Workspace is the flagship vertical for Auralith OS: a local-first AI engineering environment for real software work. It narrows the product around feature implementation, bug fixing, refactoring, architecture exploration, validation review, deployment preparation, rollback, and long-running workflow continuity.

This milestone should deepen daily engineering quality instead of broadening Auralith into a generic assistant platform.

## Core Contract

Aegis Core exposes the Engineering Workspace surface through `/v1`:

- `GET /v1/engineering-workspace`
- `GET /v1/engineering-workspace/map`
- `POST /v1/engineering-workspace/search`
- `GET /v1/engineering-workspace/validation`
- `GET /v1/engineering-workspace/continuity`
- `GET /v1/engineering-workspace/benchmarks`

These endpoints compose existing Core systems:

- workspace scanning
- persistent knowledge graph
- architecture summary
- impact analysis
- quality dashboard
- quality gates
- validation command discovery
- deployment intelligence
- workflow statistics
- dogfooding friction signals
- benchmark history

The contract is read-first. It does not silently edit files, run commands, apply changes, deploy, or bypass approval gates.

## Flagship Workflows

### Feature Implementation

Start from architecture context, impacted systems, target files, validation gates, checkpoint requirements, and rollback readiness.

### Bug Fixing

Prioritize failing systems, root-cause candidates, recurring repair areas, focused validation commands, and smallest safe repair scope.

### Refactoring

Use dependency-aware search, symbol relationships, impact visualization, technical-debt indicators, and quality gates before editing shared modules.

### Architecture Exploration

Navigate project maps, entry points, service relationships, runtime boundaries, build systems, dependency edges, and impact hotspots.

### Deployment Preparation

Review pipeline risk, release readiness, secrets/config boundaries, validation gates, environment health, and rollback plans before staging or production work.

## Architecture Navigation

The project map includes:

- language mix
- frameworks
- entry points
- build files
- service/module/runtime nodes
- dependency edges
- relationship edge types
- impact hotspots
- knowledge indexing status

Clients should render this as a compact engineering map, not as a broad dashboard maze.

## Advanced Search

Engineering search supports these modes:

- `semantic`
- `dependency`
- `architecture`
- `workflow`
- `symbol`

Current search is graph/lexical and semantic-ready. Future embedding providers should plug into the same response shape without changing client workflow behavior.

## Validation UX

Validation review returns:

- detected commands
- fast-first prioritization
- latest quality gate result
- blockers
- root-cause candidates
- repair explanations
- regression indicators
- recommended next validation

The UX goal is to make validation faster to understand and cheaper to rerun.

## Large-Project Handling

Core flags large-project traits:

- `large_project`
- `mixed_language_repo`
- `large_cpp_ready`
- `monorepo_or_multi_package`
- `partial_language_coverage`

Large workspaces should default to scoped search, incremental indexing, package/service selection, and dependency-scoped context instead of full-workspace prompts.

## Continuity

Workflow continuity exposes:

- active workflow count
- resume candidates
- interrupted work
- roadmap continuation hints
- branch-aware diff signals
- checkpoint-linking requirements

Every feature, repair, refactor, and deployment workflow should be resumable, checkpointed, and explainable.

## Benchmarks

Engineering benchmark comparisons track:

- workflow speed
- validation reliability
- repair quality
- indexing performance
- orchestration efficiency

These are product-quality signals, not marketing numbers. Use them to decide where to polish next.

## Client Responsibilities

Website, Desktop, VS Code, and Visual Studio should consume these Core contracts for engineering views instead of recreating local project maps, validation summaries, or workflow continuity state.

IDE clients should keep their native strengths:

- inline actions
- keyboard-first commands
- selected code context
- build output integration
- startup project awareness
- low-latency navigation

Core should remain the shared runtime source of truth.

## Remaining Pain Points

- Search is graph/lexical until optional embeddings are connected.
- UI visualizations still need client-specific rendering.
- Benchmark data needs repeated real engineering sessions.
- Large C++ and monorepo handling should be validated against real projects.
- Distributed validation workers are represented by surrounding runtime contracts, but this layer only summarizes their engineering value.
