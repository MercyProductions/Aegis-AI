# Productization And Runtime Hardening

This layer turns the experimental runtime into a production-oriented operating environment without changing the existing chat, task, checkpoint, validation, provider, or desktop contracts.

Productization is paired with Platform Discipline. Productization measures hardening readiness; Platform Discipline decides which domains, stability tiers, budgets, behavior principles, and security foundations are allowed to shape the default product experience.

## Backend Module

`website/backend/aegis_ai/productization.py` owns the hardening aggregate:

- stable internal API contract catalog
- Plugin / Extension SDK manifest validation
- enterprise policy defaults and enforcement signals
- runtime recovery snapshot generation
- reliability metric aggregation
- scaling, packaging, and documentation readiness summaries

FastAPI exposes this under `/api/productization`.

`website/backend/aegis_ai/platform_discipline.py` exposes the companion governance contract under `/api/platform-discipline`. It is read-only and does not enable features or change policy by itself.

## Stable APIs

Stable APIs are described by `StableApiContract`. The contract records:

- id and version
- endpoint path prefixes
- schema names used by clients
- owner and status
- compatibility notes
- deprecation policy

The first version is `2026.05.07`. It documents the current unversioned endpoints without replacing them, so desktop C++ clients, the web frontend, launch scripts, and existing tests keep working.

## Plugin SDK

Plugins are persisted as `PluginManifest` records in SQLite and are disabled by default.

Supported capability families:

- custom agents
- validators
- providers
- scaffold templates
- telemetry processors
- workspace analyzers
- UI panels

Supported safety controls:

- explicit permission scopes
- sandbox profile declaration
- lifecycle hooks with timeouts
- signing metadata fields
- trusted/enabled flags
- enterprise policy that can require signatures

High-risk permissions such as workspace writes, command execution, network access, model access, and provider registration require an isolated, sandbox, or restricted sandbox profile. Enabled high-risk plugins must also be trusted.

## Enterprise Controls

`EnterprisePolicyProfile` captures the active production policy:

- audit trail requirement
- permission profile
- privacy mode
- encrypted workspace storage flag
- provider allow/block lists
- network allow/block lists
- local model enforcement
- remote worker permission
- telemetry retention
- plugin signing requirement
- command execution default

Policy writes are explicit through `/api/productization/enterprise-policy` and are recorded as worker audit events.

## Runtime Recovery

`RuntimeRecoverySnapshot` checks:

- SQLite `pragma quick_check`
- open and interrupted tasks
- recoverable tasks
- stale workers
- blocked/running queue items
- checkpoint count and latest checkpoint id
- safe shutdown readiness

The snapshot is read-only. It recommends actions such as reviewing interrupted tasks, reconnecting stale workers, retrying queue items, or creating a checkpoint before risky edits.

## Reliability Metrics

`ReliabilityMetric` records operational health:

- task completion rate
- validation success rate
- repair success rate
- runtime recovery readiness
- database integrity
- route reliability
- average model latency
- worker failure rate

Refreshing the productization snapshot persists metric windows in `reliability_metric_snapshots` so hardening health survives restarts.

## SQLite Tables

The productization pass adds additive tables only:

- `plugin_manifests`
- `enterprise_policy_profiles`
- `reliability_metric_snapshots`

No existing schema or endpoint contract is removed.

## Frontend Surface

The `Hardening` workspace surface in `website/frontend/src/App.tsx` shows:

- runtime recovery
- enterprise controls
- plugin SDK registrations and validation results
- stable API contracts
- reliability metrics
- scaling, packaging, and documentation readiness

It can validate a read-only sample plugin manifest and manage registered plugin trust/enablement. It does not execute plugin code.

## Safety Boundaries

- Plugin registration never grants execution by itself.
- File-changing extensions must still flow through existing workspace safety, approval, checkpoint, validation, and rollback paths.
- Enterprise policy changes are reviewable and persisted.
- Productization endpoints do not modify project files.
- Existing local-first workflows continue to run offline.

## Tests

`website/backend/tests/test_productization.py` covers plugin validation, plugin state persistence, enterprise policy persistence, recovery snapshots, reliability snapshots, and API endpoints.

`website/frontend/src/api.test.ts` covers the frontend API contract for productization snapshot reads, plugin lifecycle calls, stable API reads, recovery reads, reliability reads, and policy updates.
