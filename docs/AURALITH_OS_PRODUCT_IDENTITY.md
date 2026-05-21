# Auralith OS Product Identity

Auralith OS is a local-first AI engineering operating environment. Aegis Core is the shared runtime authority inside it. Auralith Prime is the assistant identity users interact with.

This productization phase narrows the ecosystem from a broad engineering platform into a coherent product with visible modes, stable workflows, and clear launch boundaries.

## What It Is

- A local-first workspace for understanding, changing, validating, and recovering software projects.
- A shared runtime where Website, Desktop, VS Code, and Visual Studio clients consume the same Core contracts.
- An approval-aware workflow environment for scan, roadmap, change proposal, validation, repair, checkpoint, deploy validation, and rollback.
- A privacy-forward product that prefers local models and makes cloud routing explicit.
- A persistent project intelligence layer with inspectable memory and workspace knowledge.

## What It Is Not

- Not a cloud-first SaaS conversion.
- Not an unrestricted autonomous coding system.
- Not a replacement for source control, CI, or human review.
- Not a bot that deploys to production without explicit approval.
- Not a pile of unrelated labs, panels, and agents.

## Naming Rules

- Product: Auralith OS.
- Assistant: Auralith Prime.
- Runtime: Aegis Core.
- User-facing agents: Auralith agents.
- IDE/legacy package aliases may keep Aegis naming temporarily, but UI copy should gradually move to Auralith OS and Auralith Prime.
- Experimental systems belong under Experimental Labs unless they have stable workflows, tests, recovery behavior, and documentation.

## Product Modes

Basic Local Assistant is the first-run mode. It should show local model setup, chat, explain, workspace open, and runtime status without automatic file writes.

Engineering Workspace is the daily mode. It should center Workspace, Plan, Changes, Validate, Memory, and Runtime.

Autonomous Engineering is advanced. It exposes workflow graphs, agents, quality gates, repair loops, and approval queues only when safety state is visible.

Distributed Runtime is experimental. Trusted nodes are opt-in and must show trust level, permissions, workload status, and fallback state.

Experimental Labs is hidden by default. Plugins, voice, optimization, collaboration sessions, and media generation should stay there until they have clear product workflows.

## Feature Classification

Core product features:

- local assistant chat
- workspace scan
- architecture summary
- roadmap generation
- safe apply
- checkpoint and rollback
- validation
- Core model registry
- runtime status

Advanced features:

- quality gates
- engineering execution pipeline
- agent supervision
- knowledge graph
- deployment validation

Experimental systems:

- distributed runtime
- plugin ecosystem
- system optimization
- voice interaction
- collaboration sessions

Developer/internal systems:

- stabilization audit
- release packaging and update flow
- security hardening checks
- benchmark suites

Deprecated systems:

- Website-owned runtime workflow authority
- client-owned model/provider truth
- extension monolith runtime ownership

## Coherent Workflow Spine

The product should make this path feel intentional:

1. Open workspace.
2. Scan project.
3. Explain architecture or generate roadmap.
4. Propose a small change.
5. Review diff and risk.
6. Create checkpoint.
7. Apply approved changes.
8. Validate.
9. Repair if validation fails.
10. Deploy validation when relevant.
11. Roll back when needed.

## UX Simplification

Primary navigation should be:

- Workspace
- Plan
- Changes
- Validate
- Memory
- Runtime

Advanced surfaces can include Agents, Quality, Deployment, Plugins, Labs, and Diagnostics. Duplicate panels should collapse into the nearest primary workflow. Runtime controls should distinguish applied changes from proposed changes at all times.

## Launch Scope

Recommended launch scope:

- Basic Local Assistant
- Engineering Workspace
- supervised subset of Autonomous Engineering

Exclude from default launch:

- Distributed Runtime
- Experimental Labs
- voice interaction
- untrusted plugin execution
- production deployment execution

The launch promise should be safety, continuity, and local control rather than full autonomy.

## Showcase Workflows

- Generate a small feature safely.
- Repair a failing build.
- Explain architecture.
- Execute one roadmap item.
- Validate deployment readiness.
- Roll back after failure.

Each showcase should visibly include status, safety state, validation evidence, and recovery path.

## Stable API Direction

Stable launch workflows should lock Core contracts for:

- product identity and modes
- workspace scan
- roadmap
- proposed changes
- checkpoints
- apply
- validation
- repair job tracking
- quality gate results
- model routing
- runtime status
- workflow events

Experimental contracts may remain versioned but hidden from default UI.

## Roadmap Governance

A feature moves toward stable only when it has:

- a named user workflow
- a safety model
- tests
- docs
- recovery behavior
- client ownership
- clear Core contract ownership

Research ideas and future concepts should stay out of the default product until they pass that gate.
