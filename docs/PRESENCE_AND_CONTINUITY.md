# Presence And Continuity

Presence and Continuity is the advanced intelligence layer over Unified Context. It deepens Aegis without adding disconnected products.

It is read-first and derived from persisted local state. It does not execute autonomous actions, mutate files, run commands, install skill packs, inspect processes, or control the desktop.

## Backend

`website/backend/aegis_ai/continuity.py` owns the engine.

The API endpoints are:

- `GET /api/continuity?workspace_root=...`
- `POST /api/continuity/timeline/search`

The engine consumes `UnifiedContextSnapshot` and produces `AegisContinuitySnapshot`.

## Snapshot Sections

The snapshot includes:

- ambient presence state
- operating memory timeline
- simulation and forecast signals
- cognitive workflow-awareness state
- hardware acceleration profile
- persistent workspace state
- self-diagnostics
- skill pack metadata
- universal data source readiness
- platform SDK capabilities
- digital twin workspace model
- autonomous research lab evaluations
- memory distillation summary

## AI Companion / Presence

Presence is based on observable workflow signals:

- active tasks
- recommendations
- high-risk forecast signals
- diagnostic warnings
- context relationship volume

It adapts suggestion intensity, notification style, pacing, and verbosity. It does not infer emotions or simulate fake feelings.

## Operating Memory Timeline

The timeline is reconstructed from Unified Context records:

- tasks
- task timeline events
- workspace events
- generated media
- recommendations
- runtime jobs

Timeline replay is descriptive today. Executable replay must route back through existing task, approval, checkpoint, validation, provider, and rollback contracts.

## Forecasting

Forecasts are heuristic and explainable. Current signals include:

- architecture risk
- validation failure risk
- runtime stability watch
- memory bloat
- baseline technical-debt risk

Forecasts do not execute changes. They recommend dry runs and safer sequencing.

## Cognitive Awareness

Cognitive awareness detects workflow patterns only:

- many active workstreams
- repeated failures
- repair-loop risk
- runtime health watch

It adapts product behavior toward concise summaries, lower notification intensity, and conservative workflow pacing when load rises.

## Hardware Acceleration

The first hardware profile is conservative:

- CPU is always the safe baseline
- GPU/NPU availability is not assumed without adapter evidence
- distributed inference remains opt-in and privacy-scoped

## Persistent Workspace

Persistence is reconstructed from existing durable state:

- tasks
- timelines
- project intelligence
- workspace intelligence
- project memory
- creative media library
- operating environment state
- distributed queue state

## Skill Packs And Platform SDK

Skill packs are modeled as trusted ecosystem/plugin packages with workflows, prompts, agents, automations, memory templates, validation rules, and optional UI panels.

The initial skill pack list is metadata only. Installation and execution must go through signed, permission-scoped, sandboxed plugin/ecosystem contracts.

## Universal Data Layer

The universal data layer is currently the normalized Unified Context graph. Sources are counted and permission-scoped. Future semantic indexing should improve the search implementation without changing the API contract.

## Digital Twin

The digital twin is a semantic model derived from context records and relationships. It summarizes architecture, workflows, dependencies, preferences, recovery uses, and predictive uses.

## Research Lab

The research lab describes controlled evaluations for:

- routing
- repair quality
- prompt quality
- latency
- context efficiency

These evaluations are controlled and observable. They do not self-modify runtime logic.

## Safety Rules

- Do not execute work from the continuity layer directly.
- Do not infer emotions; adapt only from observable workflow signals.
- Do not install or enable skill packs outside trusted plugin/ecosystem flow.
- Do not assume hardware acceleration without a reporting adapter.
- Do not prune memory without user-reviewable distillation.

## Tests

Backend coverage lives in:

`website/backend/tests/test_continuity.py`

Frontend API coverage lives in:

`website/frontend/src/api.test.ts`
