# Unified Multi-Modal Runtime

The unified runtime is the consolidation layer for Aegis. It does not add a new autonomous subsystem. It maps existing capabilities into one local-first operating model so the product can grow without becoming a pile of disconnected dashboards.

## Purpose

The runtime map answers:

- what Aegis can do today
- which modalities are supported
- which tool contracts exist
- which workflows are safe and task-tracked
- where approvals, sandboxing, rollback, and logging apply
- what remains planned instead of pretending everything is complete

## Backend

`website/backend/aegis_ai/unified_runtime.py` owns the registry. It emits a `UnifiedRuntimeSnapshot` with:

- capability pillars
- modality support
- tool contracts
- workflow entries
- memory and safety summaries
- active runtime counts
- recommendations

The API endpoint is:

`GET /api/unified-runtime?workspace_root=...`

The snapshot aggregates counts from tasks, project memory, fix memory, Creative Studio jobs/assets, distributed workers/queue jobs, autonomous objectives, approval gates, recommendations, and Project Intelligence readiness.

## Pillars

The registry currently tracks:

- conversation and reasoning
- multi-modal input/output
- tool execution
- web and research
- Creative Studio
- voice assistant
- agent runtime
- project and knowledge intelligence
- automation platform
- distributed execution
- personal memory
- security and safety
- clients, plugins, and UX
- operating environment

Each pillar is marked `ready`, `partial`, `planned`, `blocked`, or `disabled`.

## Operating Environment

The unified runtime now links to the AI Operating Environment control plane:

`GET /api/operating-environment?workspace_root=...`

This is where desktop control, screen understanding, overlays, automation, system intelligence, learning, research, environment setup, security analysis, story/simulation, personal memory, creative generation, distributed execution, and knowledge graph capabilities are registered.

The operating-environment layer is intentionally preview-first. Risky actions are blocked or approval-gated until a trusted adapter exists.

## Frontend

The existing Runtime surface now starts with the unified runtime map, modalities, tool contracts, and runtime guidance before showing distributed worker/queue details. This keeps the product coherent: the Runtime area is the spine, not another isolated dashboard.

The same Runtime surface also shows operating-environment capability readiness, adapter trust state, and read-only system signals.

It also shows the Unified Context Engine source summaries, cross-module insights, recommended focus, global command preview, and Presence and Continuity signals. Runtime is therefore both the capability map and the convergence map, not another disconnected dashboard.

Runtime also shows the Platform Discipline contract from `/api/platform-discipline`: stewardship posture, primary, secondary, and experimental domains; stability tiers; performance budgets; behavior principles; and design standards. This keeps product focus visible beside runtime capability state and discourages adding new surfaces for unproven ideas.

## Product Rule

Do not implement future pillars by adding random panels. Add or refine a capability only when it improves a real workflow, exposes a clear tool contract, obeys safety rules, and can be tested.

The Platform Discipline feature admission gate now defaults to `reject_when_unclear`. A new capability must strengthen the core identity, improve a real workflow, reduce friction, improve intelligence quality or trust, fit the runtime, avoid duplication, and stay maintainable. Otherwise the answer is no.

The stewardship posture is the standing operating rule: preserve quality, clarity, maintainability, trust, performance, and cohesion; improve intelligence and workflow quality; reduce friction, clutter, latency, instability, architectural drift, and feature sprawl.

## Tests

Backend coverage lives in `website/backend/tests/test_unified_runtime.py` and `website/backend/tests/test_platform_discipline.py`. Frontend API coverage lives in `website/frontend/src/api.test.ts`.
