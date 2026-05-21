# Platform Stabilization and Production Readiness

Aegis is now in a stabilization phase. The goal of this phase is not to add another major runtime system. The goal is to reduce architectural risk, make contracts harder to drift, keep recovery predictable, and prepare repeatable release candidates across Core, Website, Desktop, VS Code, Visual Studio, plugins, and distributed runtimes.

## Stabilization Posture

Aegis Core remains the runtime authority for editing, checkpoints, validation, orchestration, quality gates, model routing, workspace intelligence, plugins, memory, distributed nodes, deployment intelligence, and optimization. Clients should continue to treat Website, Desktop, VS Code, and Visual Studio logic as adapters or compatibility fallbacks unless a feature has not migrated to Core yet.

During stabilization:

- No new major subsystem should be added.
- Core `/v1` contract compatibility is a release gate.
- All file mutation paths must preserve checkpoint, rollback, validation, and audit behavior.
- Experimental systems stay inspectable, approval-gated, and reversible.
- Website-owned workflow logic should remain as fallback, not the long-term source of truth.

## Core Audit API

Core exposes a production-readiness audit:

- `GET /v1/stabilization/audit`
- `GET /v1/stabilization/governance`
- `GET /v1/stabilization/roadmap`

The audit is static and conservative. It scans source modules, contract mappings, `.aegis` JSON state, duplicated runtime surfaces, possible inline secrets, recovery artifacts, test strategy, observability posture, and release candidate gates. When `persist=true`, Core writes:

- `.aegis/stabilization-audit.json`
- `.aegis/stabilization-summary.md`

## Contract Governance

Every non-schema `/v1` contract must have:

- a `ContractDescriptor`
- a response data model in `CONTRACT_DATA_MODELS`
- stable envelope metadata
- client migration notes when behavior changes

Schema-only contracts are allowed for shared DTOs, but they must be explicitly marked as `owner="schema-only"`.

## Refactor Priorities

The first production-readiness refactors should target:

- oversized frontend and desktop shells
- Website backend route/service monoliths
- extension monoliths
- large contract/schema catalogs
- duplicated model/runtime/checkpoint/validation surfaces across clients

Splits should be feature-owned and contract-driven: routers, services, persistence adapters, typed DTOs, UI panels, and focused tests.

## Recovery Rules

Core startup should remain safe when state is damaged:

- parse `.aegis` JSON before resuming workflows
- quarantine corrupt state instead of crashing the runtime
- keep Core online in safe mode
- require approval before retrying interrupted apply/update/deployment flows
- reconcile terminal jobs, distributed workloads, and stale workflow states after restart

## Release Candidate Gates

A release candidate requires evidence for:

- Core unit and contract tests
- editing/checkpoint/validation tests
- Website backend delegation and fallback tests
- Website frontend build/test smoke
- Desktop Release build and Core-offline smoke
- VS Code extension compile/package smoke
- Visual Studio VSIX build smoke
- plugin permission/isolation tests
- distributed node registration/fallback tests
- update checksum failure and rollback tests
- docs and compatibility matrix updates

## Roadmap Classification

Current classification should be reviewed before each release:

- Production-ready: Core contract envelope, editing/checkpoint runtime, validation command safety, Website Core gateway fallback.
- Experimental: orchestration, agents, workspace intelligence, quality gates, deployment intelligence, optimization, plugin ecosystem.
- Prototype: distributed remote execution, voice interaction, collaboration/session supervision.
- Deprecated: Website-owned runtime workflow ownership, client-specific model/provider truth.
- Planned: automated release matrix, installer/update smoke harness, large-workspace performance budgets.

## Recommended Freeze Priorities

1. Keep the Core contract catalog clean.
2. Preserve checkpoint/apply/validation safety.
3. Split monoliths that block reliable review.
4. Build repeatable release candidate automation.
5. Add performance budgets for large workspaces, streaming, graph queries, memory, plugins, and distributed nodes.
