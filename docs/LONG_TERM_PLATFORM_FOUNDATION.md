# Long-Term Platform Foundation

Auralith OS is now treated as a long-lived local-first engineering platform. This phase exists to keep the platform maintainable over years: fewer compatibility surprises, clearer subsystem ownership, safer migrations, healthier plugin evolution, and better recovery when state or releases drift.

## Core Platform APIs

Aegis Core exposes the sustainability layer through:

- `GET /v1/platform/governance`
- `GET /v1/platform/migrations`
- `POST /v1/platform/migrations/run`
- `POST /v1/platform/compatibility/validate`
- `GET /v1/platform/ownership`
- `GET /v1/platform/dependencies`
- `GET /v1/platform/release-engineering`
- `GET /v1/platform/health`
- `GET /v1/platform/tooling`
- `GET /v1/platform/roadmap`
- `POST /v1/platform/archive`
- `POST /v1/platform/sustainability`

State is workspace-local under `.aegis`:

- `.aegis/platform-state.json`
- `.aegis/platform-migrations.json`
- `.aegis/platform-compatibility-report.json`
- `.aegis/platform-health.json`
- `.aegis/platform-sustainability.json`
- `.aegis/platform-archives/`

## Governance Guarantees

Stable `/v1` contracts do not remove or rename response fields inside the compatibility window. Experimental contracts may add optional fields, but breaking changes need explicit descriptor notes and migration guidance. Deprecated contracts stay callable for at least one minor release and must document replacement routes.

Plugin compatibility is manifest-first. Plugin discovery, permission scopes, tool contracts, runtime compatibility metadata, and load failures are handled by Core. High-risk plugin scopes remain approval-gated and disabled by default in alpha/beta channels.

Security review is required for:

- filesystem writes
- process execution
- network access
- provider credentials
- remote node trust
- plugin permission-scope expansion
- update package verification
- migrations that rewrite state

## Migration Lifecycle

Platform migrations are idempotent and dry-run capable. The first migration generation creates anchors for:

- `.aegis` platform state
- memory manifests
- workflow history manifests
- plugin manifest indexes
- orchestration state manifests
- knowledge graph storage manifests
- checkpoint format manifests

Run a dry run first:

```powershell
python -m pytest .\tests\test_platform_foundation.py -q
```

Then call `POST /v1/platform/migrations/run` with `dry_run=false` once the workspace state is writable and an archive exists for important projects.

## Compatibility Validation

`POST /v1/platform/compatibility/validate` checks:

- plugin compatibility
- client compatibility
- Core API contract/data-model mapping
- orchestration compatibility
- runtime compatibility

The validator returns `pass`, `warning`, or `blocked` checks plus recommended actions. Release packaging should run this before producing artifacts, and clients should show blocked compatibility before attempting apply/update workflows.

## Subsystem Ownership

Core owns runtime state and durable contracts. Clients own presentation, authentication surfaces, and client-specific ergonomics.

Boundaries:

- Stable Core runtime: contracts, editing, checkpoints, validation, release compatibility.
- Orchestration: workflows, task graph, execution pipelines, agent supervision.
- Plugins: manifest loading, permission scopes, tool contracts, extension hooks.
- Deployment/runtime infrastructure: CI/CD intelligence, runtime nodes, workload routing.
- IDE integrations: Core clients, fallback behavior, IDE-specific context.
- Observability: workflow traces, quality gates, alpha diagnostics, runtime health.
- Website gateway: auth, UI-facing compatibility, Core delegation fallback.
- Desktop client: native runtime panel, Core-first operations, Website fallback.

Experimental systems cannot become defaults until tests, docs, recovery behavior, migration behavior, and ownership are present.

## Dependency Management

The dependency report tracks:

- plugin dependency chains
- provider dependency status
- runtime component compatibility
- update compatibility risks

Plugin dependency cycles or missing dependencies should keep the plugin disabled. Provider failures should route through local-first fallback profiles. Runtime incompatibility should block update/apply operations until the client or Core is upgraded.

## Release Engineering

Release engineering status reports:

- reproducible build scripts
- release verification policy
- package checksum presence
- rollback requirements
- compatibility matrix
- staged rollout channels

Release channels:

- `stable`: release-candidate-tested builds only
- `beta`: trusted external alpha/beta users
- `experimental`: opt-in subsystem validation
- `dev`: internal development only

Every release candidate should include a compatibility matrix, known limitations, migration notes, and rollback instructions.

## Platform Health Analytics

Platform health tracks:

- subsystem reliability
- compatibility blockers and warnings
- migration success rate
- plugin failure count
- workflow count and active workflows
- runtime job count
- distributed node count
- regression watchlist

This is intentionally local-first. It is a diagnostic view and does not upload telemetry.

## Ecosystem Tooling

The tooling catalog exposes:

- plugin SDK manifest rules
- permission scope catalog
- high-risk scope list
- plugin compatibility validator
- client compatibility validator
- API contract validator
- workflow schema validator
- platform migration validator
- diagnostics and replay export hooks

This gives plugin authors and client maintainers a single place to understand compatibility expectations.

## Roadmap Governance

Roadmaps are separated into:

- production roadmap
- experimental roadmap
- research initiatives
- deprecated systems
- ecosystem initiatives

A system moves toward production only after tests, docs, ownership, migration behavior, rollback behavior, and compatibility contracts are all present.

## Archival And Recovery

`POST /v1/platform/archive` creates a local recovery manifest under `.aegis/platform-archives`. It can include:

- memory files
- workflow/orchestration state
- knowledge graph/index files
- checkpoint metadata when explicitly requested

Archives are not an automatic restore mechanism. They are inspectable recovery snapshots. Restore individual files only after reviewing `manifest.json`, then rerun platform compatibility and migration checks.

## Validation

Focused validation:

```powershell
python -m pytest .\tests\test_platform_foundation.py -q -p no:cacheprovider
python -m py_compile .\aegis_core\platform_foundation.py .\aegis_core\contracts.py .\aegis_core\server.py
```

Recommended release-candidate validation:

- migration stress tests
- compatibility tests
- plugin ecosystem tests
- long-upgrade-chain tests
- rollback/recovery tests
- distributed runtime disconnect tests
- corrupted `.aegis` state recovery tests

## Current Sustainability Risks

The largest remaining risks are compatibility debt in client fallbacks, plugin ecosystem fragmentation once real third-party plugins appear, distributed runtime trust/isolation, large-upgrade-chain coverage, and corrupted-state recovery in user workspaces with damaged or locked `.aegis` paths.
