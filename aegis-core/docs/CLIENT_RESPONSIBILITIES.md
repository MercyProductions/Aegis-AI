# Client Responsibilities

## Aegis Core Owns

- Model detection and fallback routing
- Workspace scanning and indexing
- Memory file creation and generated-section updates
- Roadmap generation
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
- shared diagnostics

Minimum integration:

- Register on launch with `/v1/clients/register`.
- Read `/v1/ecosystem/dashboard` for the command-center dashboard.
- Create user-visible tasks with `/v1/tasks`.
- Use `/v1/branding` for shared naming and visual tokens where practical.

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
- Core owns shared plan data, memory, diagnostics, model status, and settings.
- Clients should not write directly to `.aegis/tasks.json` unless Core is unavailable and the user explicitly accepts degraded local mode.
