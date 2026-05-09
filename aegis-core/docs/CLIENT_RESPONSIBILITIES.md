# Client Responsibilities

## Aegis Core Owns

- Model detection and fallback routing
- Workspace scanning and indexing
- Memory file creation and generated-section updates
- Roadmap generation
- Supervised orchestration queue state
- Specialized agent roster and ownership metadata
- Safe maintenance job catalog, schedule state, trigger mapping, and job logs
- Project quality score, health trends, risk reports, and generated daily/weekly quality summaries
- Knowledge graph nodes, relationships, graph queries, generated knowledge summaries, and Planner graph guidance
- Validation command detection
- Validation log normalization
- Agent plan and repair plan contracts
- Shared safety rules
- Shared configuration defaults
- Diagnostics and local logs

## Desktop App

The Desktop App is the primary Auralith interface.

It should own:

- Rich chat and workflow UI
- Project dashboards
- Memory browsing and visualization
- Multi-step orchestration screens
- Installer/update surfaces
- User-level preferences

It should call Aegis Core for:

- model status
- workspace scan
- roadmap
- validation
- agent plans
- memory data
- ecosystem dashboard data
- shared task visibility
- supervised orchestration state
- current owner agent and agent pipeline state
- maintenance job dashboard and explicit job run/approval state
- quality dashboard, health trend, high-risk file warnings, and explicit snapshot state
- knowledge graph visualization data, impact queries, dependency clusters, roadmap links, and unstable module summaries
- shared diagnostics

Minimum integration:

- Register on launch with `/v1/clients/register`.
- Read `/v1/ecosystem/dashboard` for the command-center dashboard.
- Create user-visible tasks with `/v1/tasks`.
- Use `/v1/branding` for shared naming and visual tokens where practical.
- Use `/v1/orchestration` for staged goal state, pending approvals, validation summaries, and rollback metadata when building autonomous workflow UI.
- Use `/v1/jobs` for proactive maintenance visibility and `/v1/jobs/run` only from explicit user action, due-job runner, or known safe trigger.
- Use `/v1/quality` for project health/risk visibility and `/v1/quality/snapshot` only for explicit or safe scheduled generated-report updates.
- Use `/v1/knowledge/graph` and `/v1/knowledge/query` for relationship visualization and impact/context questions.

## VS Code Extension

The VS Code extension should stay lightweight.

It should own:

- active workspace detection
- active file and selection capture
- editor diff preview
- approval/reject controls
- VS Code terminal integration
- VS Code status bar and sidebar UI

It should call Aegis Core for:

- scanning
- model checks
- roadmap generation
- validation detection
- agent planning
- shared memory
- shared settings
- shared tasks
- supervised orchestration state
- owner-agent metadata for staged tasks
- maintenance triggers such as project opened and many files changed
- quality dashboard and risk warnings before editing high-risk files
- knowledge graph queries for impact analysis and context selection
- diagnostics

## Visual Studio Extension

The Visual Studio extension should remain Visual Studio-native.

It should own:

- solution/project detection
- selected document/code detection
- Solution Explorer context
- Error List reading
- Build Output reading
- Visual Studio build execution
- tool window UI

It should call Aegis Core for:

- model checks
- memory format
- dependency/symbol indexing where possible
- roadmap and architecture summaries
- shared safety/configuration
- plan/repair contracts
- shared task status
- supervised orchestration state
- owner-agent metadata for staged tasks
- maintenance triggers such as solution opened, build failed, and test failed
- quality dashboard and risk warnings before changing unstable files
- knowledge graph queries for solution impact and build-error context
- shared diagnostics

## Website

The website should not become the local agent brain.

It should own:

- downloads
- documentation
- accounts
- licensing
- release notes
- future cloud dashboards

It can call Aegis Core only for local dashboard features when running on the user's machine.

## Cross-Client Rules

- Every client should use the same workspace root when sharing memory and tasks.
- Every client should register itself with a stable `client_id`.
- Approval remains client-owned because each UI has different diff and editor affordances.
- Diff preview, patch apply, and rollback execution remain client-owned even when Core owns orchestration queue state.
- Clients should display `owner_agent`, `active_agent`, and pending approval metadata instead of inventing separate agent ownership.
- Clients should surface `jobs.run` results that return `needs_approval`; build/test/lint jobs must not run silently.
- Clients should treat quality snapshots as generated `.aegis` health artifacts and must not infer permission to edit source files from a quality recommendation.
- Clients should treat knowledge graph recommendations as context/risk signals only; approval is still required before edits, commands, or cloud calls.
- Core owns shared plan data, memory, diagnostics, model status, and settings.
- Clients should not write directly to `.aegis/tasks.json` unless Core is unavailable and the user explicitly accepts degraded local mode.
