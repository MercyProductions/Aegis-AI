# Ecosystem And Shared Intelligence

Aegis ecosystem infrastructure turns the local runtime into a platform for reusable, signed, governed intelligence without giving up local-first safety.

## Backend Modules

`website/backend/aegis_ai/ecosystem.py` owns:

- Marketplace catalog and package validation.
- Reusable workflow templates.
- Workflow-to-task-graph execution.
- Shared intelligence profile import/export.
- Organization policy defaults and enforcement helpers.
- Knowledge graph generation from Project Intelligence, task history, memory, and fix history.
- Cross-project insight generation.
- Ecosystem search over graph nodes, tasks, memory, workflows, and packages.
- Reproducibility record creation.
- Governance trust signals.

`website/backend/aegis_ai/storage.py` persists:

- `ecosystem_packages`
- `ecosystem_workflows`
- `shared_intelligence_profiles`
- `organization_policy_profiles`
- `knowledge_graph_snapshots`
- `reproducibility_records`
- `ecosystem_audit_events`

All tables store stable typed records as JSON payloads plus query columns for safe indexing.

## Package Model

An ecosystem package can represent:

- Agent pack
- Validator pack
- Scaffold pack
- Workflow pack
- Model routing profile
- Telemetry analyzer
- Workspace intelligence pack

Package manifests include API version, trust level, sandbox permissions, permission scopes, update channel, checksum, signing metadata, install state, and lifecycle state.

High-risk permissions such as workspace writes, command execution, network access, provider access, sync, and organization policy changes require sandbox isolation and trusted/signed approval before enablement.

## Workflow Model

Reusable workflows are stored as `EcosystemWorkflowDefinition` records. Each workflow defines:

- Steps
- Agent roles
- Dependencies
- Approval requirements
- Validation commands
- Package dependencies
- Trust metadata

Running a workflow creates a parent task and one subtask per workflow step. The task timeline receives workflow events, which keeps workflow execution observable through the existing task engine.

## Shared Intelligence Profiles

Shared profiles can export and import:

- Routing strategies
- Validation profiles
- Repair heuristics
- Project memory packs
- Architecture patterns
- Benchmark profiles

Exporting the current project intelligence profile serializes stack, validation commands, coding conventions, architecture map, and memory notes into a portable profile with a checksum.

## Organization Policy

Organization policy controls:

- Provider behavior
- Privacy behavior
- Approval requirements
- Validation standards
- Package restrictions
- Audit requirements
- Signed package requirements
- Collaboration mode

Policies are persisted and auditable. Local mode remains the default.

## Knowledge Graph

The graph maps:

- Project root
- Major modules
- Important files
- API routes
- Dependencies
- Decisions
- Recurring failures
- Tasks

Edges describe containment, dependency, API exposure, decisions, failures, and related task history. The graph is persisted so Aegis can reason over project structure without rereading everything each time.

## Search And Reproducibility

Advanced search scores graph nodes, task history, memory, workflows, and packages using architecture-aware lexical relevance. Timeline reconstruction can use task events when a task result is selected.

Reproducibility records capture task payloads, validation commands, timelines, subtasks, checksums, and replay notes. These records support deterministic validation snapshots and future replay comparisons.

## Frontend

The Ecosystem workspace section shows:

- Marketplace and installed packages
- Workflow manager
- Knowledge graph summary
- Advanced search
- Organization dashboard
- Shared intelligence profiles
- Cross-project insights
- Reproducibility and audit events

The UI uses existing workspace patterns and does not redesign the product shell.
