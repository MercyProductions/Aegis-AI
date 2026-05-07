# Platform Discipline

Aegis is intentionally moving from expansion to selective mastery. Platform Discipline is the read-only contract that records that choice so future work has a clear bar before it enters the product.

## Purpose

The discipline layer answers:

- where Aegis should become exceptional
- which systems are primary, secondary, or experimental
- which workflows are production-ready, beta, experimental, internal-only, or deprecated
- which stability tier a capability belongs to
- which design standards, behavior principles, performance budgets, and security foundations protect the core experience
- how the five architecture layers should depend on each other

It is not an execution engine. It does not change files, run commands, dispatch workers, alter model routing, enable plugins, or mutate memory.

## Backend

`website/backend/aegis_ai/platform_discipline.py` owns the registry and emits `PlatformDisciplineSnapshot`.

The FastAPI endpoint is:

`GET /api/platform-discipline?workspace_root=...`

The snapshot receives the current Unified Runtime and Presence/Continuity snapshots as inputs so recommendations can react to active approvals, workload, runtime capability growth, and risk signals while staying read-only.

## Stewardship Posture

The primary responsibility is stewardship.

Aegis must preserve:

- quality
- clarity
- maintainability
- trust
- performance
- cohesion
- rollback capability
- user control

Aegis must continuously improve:

- intelligence quality
- workflow quality
- context accuracy
- repair quality
- memory usefulness
- responsiveness
- explainability
- stability

Aegis must continuously reduce:

- friction
- clutter
- redundancy
- latency
- instability
- architectural drift
- feature sprawl
- telemetry noise

The product should feel calm, premium, reliable, deeply integrated, explainable, trustworthy, and powerful without feeling chaotic.

The success metric is not capability count. The success metric is whether users choose Aegis daily because it consistently improves their workflows, thinking, creativity, and productivity.

## Feature Admission Gate

The default decision is `reject_when_unclear`.

Before implementing any new feature, subsystem, workflow, plugin, provider, agent, UI surface, automation, or background job, the proposal must pass the admission gate:

- Does this strengthen the core identity?
- Does this improve a real workflow users rely on regularly?
- Does this reduce friction?
- Does this improve intelligence quality?
- Does this improve user trust?
- Is this maintainable long-term?
- Does this integrate cleanly with the runtime?
- Does this avoid harmful architectural complexity?
- Does this avoid duplicating an existing capability?
- Will users genuinely rely on this regularly?

If the answer is unclear, do not add it.

Hard no rules:

- Say no to unclear value.
- Say no to dashboard sprawl.
- Say no to uncontrolled autonomy.
- Say no to bypassing tasks, approvals, rollback, validation, telemetry, or audit.
- Say no to duplicated systems and hidden dependencies.
- Say no to background work that can degrade active user workflows.
- Say no to plugin, provider, desktop, or worker behavior without permission scopes and trust boundaries.

Promotion requires a named workflow, clear owner layer, no duplicate capability path, reviewed performance budget impact, documented security/rollback behavior, contract tests for API changes, and docs before leaving experimental status.

## Domain Choices

Primary strengths:

- AI Coding Workspace
- AI Orchestration Runtime
- AI Memory And Knowledge OS

Secondary strengths:

- AI Automation Platform
- AI Creative Studio
- AI Research Environment

Experimental areas:

- AI Desktop Operating Layer
- AI Security Workspace

These choices are deliberately unequal. Aegis should become excellent in the primary domains before pushing secondary systems deeper, and experimental systems must remain preview-first until permission, sandbox, consent, audit, and UX quality are mature.

## Roadmap Classes

Roadmap items are categorized as:

- `mvp_workflow`
- `stable_core`
- `long_term`
- `experimental`
- `deprecated`

Feature status is tracked separately:

- `production_ready`
- `beta`
- `experimental`
- `internal_only`
- `deprecated`

Deprecated entries are important. The current contract explicitly rejects uncontrolled autonomy and dashboard sprawl as product directions.

## Stability Tiers

Stable Runtime is the default user experience. It must pass validation, preserve contracts, and not degrade daily coding workflows.

Experimental Runtime can be visible with labels, but it must not block stable workflows and needs a disable or escape path.

Sandbox Features are hidden or explicitly gated capabilities that can affect files, commands, providers, desktop, workers, network, plugins, or packages.

Unsafe Or Research-Only capabilities stay blocked in normal product UX.

## Platform Layers

Layer 1: Core Runtime

Settings, FastAPI contracts, provider registry, workspace safety, filesystem, validation, storage, and health.

Layer 2: Task Engine, Memory, Orchestration

Tasks, timelines, memory, context, routing, multi-agent coordination, checkpoints, and approvals.

Layer 3: Coding, Automation, Creative

Daily workflows that users actively perform.

Layer 4: Desktop, Research, Workflow Intelligence

Advanced assistance surfaces that stay preview-first or beta until proven.

Layer 5: Distributed Runtime, Ecosystem, SDK

Workers, plugins, packages, reusable workflows, skill packs, organization policy, and distribution.

## Product Rules

- New executable work must become a task with timeline, approval state, validation, telemetry, and recovery.
- Unclear feature value defaults to no.
- New surfaces should converge into existing workflow areas unless they create a real daily workflow.
- Approval prompts must explain action, risk, and rollback state.
- Memory must stay local, inspectable, sourced, and user-reviewable.
- Telemetry must be low-overhead, local-first, and tied to workflow improvement.
- Agents communicate through structured task events, not invisible loose chat.

## Performance Budgets

The first budget set covers startup readiness, indexing, task latency, telemetry overhead, background work, context growth, and frontend bundle size. Unknown budgets are not failures; they are signals that measurement needs to be added before claiming maturity.

The frontend bundle budget is intentionally marked `watch` until Runtime surfaces are split or lazy-loaded.

## Tests

Backend coverage lives in `website/backend/tests/test_platform_discipline.py`.

Frontend API coverage lives in `website/frontend/src/api.test.ts`.
