# Auralith Memory And Personal Intelligence

Auralith memory is the local-first layer that lets Aegis remember useful engineering context across sessions without becoming hidden surveillance. It is designed to be inspectable, editable, exportable, deletable, and scoped to the workspace unless the user explicitly exports or imports it.

## Architecture

Aegis Core owns the canonical memory runtime in `aegis-core/aegis_core/personal_memory.py`.

Workspace state is stored under `.aegis`:

```text
.aegis/auralith-memory.json
.aegis/auralith-memory-audit.jsonl
```

The Website backend keeps its existing `/api/memory` route shape for Website and Desktop compatibility. When Core is available, those routes delegate to `/v1/personal-memory`; when Core is offline, the Website backend falls back to the legacy `MemoryManager` files.

## Categories

Core supports these memory categories:

- `user_preferences`
- `workspace_preferences`
- `project_memory`
- `execution_history`
- `repair_history`
- `validation_history`
- `roadmap_history`
- `architecture_notes`
- `workflow_patterns`
- `ui_preferences`

Each category has controls for enablement, retention, orchestration inclusion, and optional encrypted-storage readiness.

## Lifecycle

The Core memory API supports:

- create
- query/search
- update
- archive
- hard delete
- export
- import
- cleanup/expiration
- pinning
- category disabling
- orchestration context retrieval
- observability and audit review

Important endpoints:

```text
GET  /v1/personal-memory
POST /v1/personal-memory/query
POST /v1/personal-memory
POST /v1/personal-memory/records/{memory_id}
POST /v1/personal-memory/records/{memory_id}/archive
POST /v1/personal-memory/records/{memory_id}/delete
POST /v1/personal-memory/export
POST /v1/personal-memory/import
POST /v1/personal-memory/controls
POST /v1/personal-memory/cleanup
GET  /v1/personal-memory/observability
POST /v1/personal-memory/context
```

## Privacy Model

Memory is local-only by default and isolated per project workspace. Secret-like text is scrubbed before persistence and redacted exports are the default.

Users and clients can:

- disable categories
- exclude categories from orchestration
- clear or archive records
- export memory for review or migration
- import memory with dry-run preview
- request local-only behavior
- request encrypted storage readiness

Current storage remains readable JSON for transparency. Core reports encrypted storage as active only when an encryption key/provider is configured; this milestone adds the contract and controls, not opaque hidden storage.

## Orchestration Integration

Workflow creation now asks Core for a bounded memory context. Agents and orchestration can use that context to improve:

- preferred workflow style
- validation command choice
- repeated repair strategy selection
- architecture decision awareness
- routing/profile defaults
- roadmap continuity
- project convention reminders

Memory is advisory. It does not bypass approvals, quality gates, checkpoints, path safety, rollback requirements, or validation requirements.

## Client Responsibilities

Website:

- keeps `/api/memory` stable
- delegates to Core when available
- falls back to legacy storage when Core is offline
- preserves the old note shape for frontend and Desktop consumers

Desktop:

- can continue using Website `/api/memory`
- should migrate to Core `/v1/personal-memory` when direct Core memory UI lands

VS Code and Visual Studio:

- should query Core memory/context contracts for project continuity
- should surface memory use before apply/repair workflows where relevant
- should not store duplicate long-term memory truth locally

## Observability

Core tracks:

- total, active, archived, pinned, stale, and deleted-placeholder counts
- record counts by category and scope
- memory file size
- retrieval counts and last retrieval timestamps
- conflicting memory fingerprints
- disabled categories
- cleanup candidates
- audit events

## Remaining Gaps

- Encrypted payload storage is a readiness contract until an encryption provider/key flow is configured.
- Website/Desktop expose compatibility memory routes today; richer memory browser/editor UI is still a follow-up.
- Cross-workspace memory is intentionally not automatic. Users must export/import or approve a future shared profile flow.
- Memory retrieval is deterministic search and scoring today. Embedding/vector retrieval can be added later through the knowledge graph and plugin contracts.
