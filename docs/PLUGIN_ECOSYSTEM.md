# Plugin And Tool Ecosystem

Aegis Core now owns the first real plugin runtime contract. The current implementation is intentionally conservative: Core discovers and validates plugin manifests, exposes tool and UI contracts, applies permission gates, records observability, and executes only whitelisted built-in handlers. It does not import arbitrary plugin code yet.

## Architecture

Plugins are local-first packages with a manifest named one of:

```text
aegis-plugin.json
plugin.json
manifest.json
```

Core discovers manifests from:

- built-in reference plugins under `aegis-core/example-plugins`
- workspace plugins under `<workspace>/.aegis/plugins`

Plugin enable, disable, trust, and approval state is stored in:

```text
<workspace>/.aegis/plugin-state.json
```

Plugin load and tool execution observations are appended to:

```text
<workspace>/.aegis/plugin-observability.jsonl
```

## Manifest Shape

Required fields:

- `id`
- `name`
- `version`
- `api_version`
- `category`
- `capabilities`
- `permission_scopes`

Common optional fields:

- `dependencies`
- `runtime_compatibility`
- `tools`
- `workflow_extensions`
- `analyzer_extensions`
- `provider_extensions`
- `ui_extensions`
- `observability`
- `package`

## Categories

Initial categories:

- `model_providers`
- `workflow_types`
- `analyzers`
- `validators`
- `repair_strategies`
- `project_templates`
- `media_generators`
- `ide_integrations`
- `deployment_tools`
- `observability_tools`

## Permission Scopes

Current scopes:

- `filesystem_read`
- `filesystem_write`
- `network_access`
- `model_access`
- `workspace_scan`
- `process_execution`
- `validation_execution`
- `ui_extension`
- `observability_read`
- `provider_credentials`

High-risk scopes require explicit approval before enabling or running affected tools:

- `filesystem_write`
- `network_access`
- `process_execution`
- `validation_execution`
- `provider_credentials`

File-changing plugins still must go through Core editing, checkpoints, validation, quality gates, approval, and rollback. Plugins do not bypass workspace safety.

## Tool Contracts

Tools declare:

- `name`
- `description`
- `input_schema`
- `output_schema`
- `safety_level`
- `supported_workflow_types`
- `execution_timeout_seconds`
- `retry_policy`
- `required_permissions`
- `handler`

Only these handlers run today:

- `builtin.echo`
- `builtin.validation_hint`
- `builtin.architecture_summary`
- `builtin.roadmap_hint`
- `builtin.provider_status`
- `builtin.observability_snapshot`

Non-built-in handlers are surfaced in the catalog but blocked at execution time until an isolated external sandbox exists.

## Workflow Hooks

Plugins can contribute:

- workflow stages
- validators
- repair strategies
- roadmap analyzers
- architecture analyzers

Hooks are metadata contracts. The workflow runtime can inspect them, schedule tasks around them, and show user approval gates. Hook execution still flows through declared tool contracts and permission checks.

## UI Extension Contracts

Plugins can declare:

- panels
- dashboard widgets
- workflow visualizers
- observability tools
- provider configuration panels

UI extension entries include placement, route, data contract, and required permissions. The Website, Desktop, VS Code, and Visual Studio clients can render these contracts later without Core embedding client-specific UI.

## API

Core endpoints:

```text
GET  /v1/plugins?workspace=<path>
POST /v1/plugins/state
GET  /v1/plugins/hooks?workspace=<path>&workflow_type=<type>
POST /v1/plugins/tools/run
```

Contracts:

- `plugin.dashboard`
- `plugin.state`
- `plugin.hooks`
- `plugin.tool.run`

## Packaging

Package metadata supports:

- checksum
- signature
- signing key fingerprint
- update channel
- update URL
- release notes URL
- dependencies
- runtime compatibility

The current local examples use built-in signatures and checksums. Future external packages should use real signatures and update metadata, and release infrastructure should verify artifacts before installation.

## Phase 13 Productization Contract

The machine-readable productization contract lives in `evals/phase13-plugin-productization-contract.json`. It is checked by:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-plugin-contract.ps1
```

The script writes comparable evidence to `.aegis/plugin-evidence/<timestamp>/` by default. When it runs inside `scripts\validate-ecosystem.ps1`, its evidence is nested under the current `.aegis/release-evidence/<timestamp>/plugin-contract/` folder.

The contract locks:

- Core plugin API version, runtime compatibility, manifest names, required fields, categories, permission scopes, high-risk scopes, and built-in handlers.
- Reference plugin manifests for validators, analyzers, local provider adapters, roadmap helpers, and observability widgets.
- Productization routes for validation, registration, trust, enable, and disable.
- Ecosystem marketplace routes for package validation, registration, trust, enable, disable, workflow runs, shared profile import/export, reproducibility, and audit.
- Safety guards for high-risk permissions, signing metadata, compatibility checks, checksum checks, no arbitrary code execution, and local observability.

## Lifecycle Matrix

| Stage | Current behavior | Safety rule |
| --- | --- | --- |
| Discover | Core reads built-in and workspace manifests. | Manifest-only; no plugin code is imported. |
| Validate | Core checks required fields, permissions, runtime compatibility, tools, dependencies, and package metadata. | Invalid manifests stay rejected or disabled. |
| Register | Website productization and ecosystem APIs persist metadata. | Registration does not grant execution. |
| Trust | User or organization policy can mark reviewed packages as trusted. | High-risk permissions require trust, signing policy, or explicit approval. |
| Enable | Plugin or package becomes visible to runtime catalog surfaces. | Enabled high-risk entries must be trusted and sandbox-scoped. |
| Run | Core can run whitelisted built-in handlers. | Non-built-in handlers are blocked until an isolated external sandbox exists. |
| Observe | State changes and tool runs write local evidence. | Events stay under `.aegis` unless explicitly exported. |
| Disable | Runtime catalog stops exposing the plugin/package as active. | Disable is the safe removal path for this phase. |
| Update | Website productization and ecosystem package routes accept replacement manifests, validate checksums, and store the previous manifest. | Updates are auditable and rollback-ready before the replacement becomes current. |
| Rollback | Stored previous manifests can be restored through lifecycle routes. | Rollback preserves the current trust/enable state and writes audit metadata. |
| Uninstall | Lifecycle routes safe-uninstall by disabling runtime visibility while preserving manifests. | Physical removal remains future work; disabling plus audit is the current reversible path. |

## Reference Plugins

Reference manifests live under `aegis-core/example-plugins`:

- `aegis-custom-validator`
- `aegis-architecture-analyzer`
- `aegis-local-provider-adapter`
- `aegis-roadmap-enhancement`
- `aegis-observability-widget`

These prove the manifest shape, hook model, UI descriptors, provider extension metadata, safe tool execution, and permission gates without adding arbitrary code loading.

## Current Limits

- No arbitrary Python, JavaScript, native, or shell plugin code is loaded.
- No network/plugin process sandbox exists yet.
- UI extensions are descriptors only; clients need follow-up work to render plugin panels and widgets.
- Provider adapters are metadata contracts only; real provider calls still use Core model routing.
- Dependency resolution reports missing dependencies but does not install them.

## Phase 32 Lifecycle Evidence

The plugin lifecycle productization contract lives in `evals/phase32-plugin-lifecycle-contract.json`. It is checked by:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-plugin-lifecycle.ps1
```

The script writes evidence to `.aegis/plugin-lifecycle/<timestamp>/` and validates checksum rejection, update, rollback, safe-uninstall, previous-manifest preservation, route wiring, and audit visibility for Website productization plugins and ecosystem packages.
