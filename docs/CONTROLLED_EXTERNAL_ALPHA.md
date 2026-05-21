# Controlled External Alpha

Auralith OS is entering a small trusted technical alpha. This is not a public launch. The alpha should validate first-run setup, local runtime stability, plugin safety, workflow reliability, rollback behavior, and whether real engineers can trust the system during daily project work.

The default alpha posture is conservative:

- Local-first execution.
- Approval required before mutation.
- Validation before apply.
- Checkpoint and rollback visibility.
- Plugin discovery allowed, high-risk plugin enablement blocked.
- Distributed runtime disabled unless a tester is explicitly in that cohort.
- External telemetry upload disabled.
- Diagnostics generated locally under `.aegis`.

## Core Alpha APIs

Aegis Core exposes the alpha readiness layer through:

- `GET /v1/alpha/readiness`
- `GET /v1/alpha/features`
- `GET /v1/alpha/feature-flags`
- `POST /v1/alpha/feature-flags`
- `GET /v1/alpha/diagnostics`
- `POST /v1/alpha/diagnostics/export`
- `POST /v1/alpha/feedback`
- `GET /v1/alpha/feedback`
- `GET /v1/alpha/observability`
- `GET /v1/alpha/release-channels`
- `GET /v1/alpha/simulations`

State is stored in the workspace `.aegis` folder:

- `.aegis/alpha-readiness.json`
- `.aegis/alpha-feature-flags.json`
- `.aegis/alpha-feedback.jsonl`
- `.aegis/alpha-diagnostics/`

## Readiness Checklist

The readiness report validates:

- Release manifest availability and package metadata.
- Update planning and rollback support.
- First-run onboarding state.
- Plugin loading and plugin failure visibility.
- Distributed runtime health, while keeping remote execution disabled by default.
- Memory persistence.
- Workflow orchestration reliability.
- Validation and quality-gate readiness.
- Crash/recovery diagnostics.
- Security and privacy posture.
- Dogfooding friction and production confidence signals.

The alpha should not be treated as ready when required checklist items are blocked. Warning states can be acceptable for a narrow cohort when the limitation is documented and visible to testers.

## Feature Classification

Phase 35 turns these classifications into tester-facing labels. Stable Alpha and Beta surfaces may appear in the default private-alpha path. Experimental surfaces require opt-in cohort context. Internal Only surfaces stay hidden from the tester path.

Stable alpha features:

- Core contract envelope.
- Local workspace scan.
- Checkpoint creation, listing, and restore.
- Validation command discovery.
- Local model registry visibility.
- Security/privacy status.
- Release compatibility checks.

Beta features:

- Auralith Engineering Workspace.
- Quality gates and evaluation reports.
- Onboarding wizard.
- Website/Core delegation fallback.
- Desktop and IDE Core-first runtime surfaces.
- Project knowledge graph.
- Dogfooding friction tracking.

Experimental features:

- Multi-agent orchestration.
- Engineering execution pipelines.
- Deployment intelligence.
- System optimization experiments.
- Personal intelligence.
- Real-time terminal orchestration.

Hidden/internal systems:

- Unrestricted autonomous execution.
- Provider credential internals.
- Raw workflow mutation endpoints.
- Internal dogfooding notes.
- Debug-only route experiments.

Disabled by default:

- Distributed remote execution.
- High-risk plugin enablement.
- Experimental workflow labs.
- Development release channel.
- External telemetry upload.
- Production deployment actions.

## Phase 35 Default Handoff Path

The private-alpha handoff should follow this path:

1. Verify package checksums against `release/version-manifest.json`.
2. Launch Aegis Core locally and check `/v1/health`.
3. Choose a disposable or backed-up workspace.
4. Keep local-only mode or complete provider setup through the credential store.
5. Confirm local model setup or show missing-model recovery.
6. Run the guided first workflow in validate-only mode.
7. Confirm checkpoint and rollback visibility before mutation.
8. Export local redacted diagnostics only when support is needed.
9. Capture alpha feedback locally.

Broad alpha remains blocked until live smoke gaps, signed installer/code-signing decisions, worktree commit scope, and fresh provider/local model health checks are resolved.

## Feature Flags

Core owns the alpha feature flag policy. Locked alpha flags ignore unsafe overrides:

- `local_only_mode`: enabled and locked.
- `approval_required_mode`: enabled and locked.
- `conservative_orchestration`: enabled and locked.
- `validation_before_apply`: enabled and locked.
- `rollback_visibility`: enabled and locked.
- `high_risk_plugin_enablement`: disabled and locked.
- `local_only_diagnostics`: enabled and locked.

Configurable alpha flags:

- `plugin_loading`
- `distributed_runtime`
- `experimental_workflows`
- `dev_release_channel`
- `telemetry_enabled`

External testers should remain on the `beta` release channel unless they are specifically validating installer or compatibility behavior.

## Diagnostics And Support

Diagnostics exports are local JSON bundles. They summarize:

- Runtime health.
- Release manifest and update state.
- Onboarding recovery cards.
- Plugin compatibility and failures.
- Distributed node status.
- Workflow statistics.
- Validation status.
- Quality-gate status.
- Crash and replay summaries.

Diagnostics must redact secrets, prompt-sensitive values, provider keys, and token-like fields before writing to `.aegis/alpha-diagnostics`.

Support tooling available through Core includes:

- Diagnostics export.
- Environment validation.
- Runtime health summary.
- Plugin compatibility report.
- Workflow trace/replay export.
- Validation failure export.
- Local feedback capture.

## Feedback Model

Alpha feedback is stored locally and can be exported by the tester. Supported categories:

- `workflow_pain`
- `orchestration_confusion`
- `plugin_issue`
- `performance_problem`
- `onboarding_friction`
- `trust_concern`
- `validation_issue`
- `update_issue`
- `distributed_runtime_issue`
- `other`

Feedback should capture actionable friction: what the user tried, what was confusing, what failed, and whether rollback/recovery worked.

## Observability Dashboard Inputs

Website and Desktop alpha dashboards should surface:

- Crash frequency.
- Failed workflows.
- Plugin failures.
- Onboarding failures.
- Rollback frequency.
- Validation failures.
- Update failures.
- Diagnostics export count.
- Feedback category counts.

The dashboard should always make privacy mode, runtime fallback mode, checkpoint status, and rollback availability visible.

## Alpha Simulations

Before inviting testers, run the simulation checklist:

- Clean machine install.
- Low-resource system.
- Plugin-heavy workspace.
- Distributed runtime disabled/offline.
- Long workflow.
- Offline workflow.
- Interrupted update.
- Stale plugin state.
- Incompatible version.
- Partial runtime failure.

For each simulation, record expected behavior, pass/fail state, and recovery notes in the alpha readiness report or release notes.

## Phase 14 Alpha Evidence Contract

Machine-readable contract: `evals/phase14-alpha-readiness-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-alpha-contract.ps1
```

The command writes local evidence under `.aegis/alpha-evidence/<timestamp>/`:

- `alpha-contract.json`
- `alpha-contract-summary.md`

This contract ties together feature tiering, Core alpha APIs, dogfooding APIs, first-run onboarding, recovery cards, support diagnostics, feedback capture, release channel visibility, and scenario-suite evidence. Passing the contract does not mean broad alpha is ready by itself. It means the alpha surfaces are connected enough to start repeatable dogfooding and collect comparable evidence.

## Alpha Scenario Suite

| Scenario | Pass Signal |
| --- | --- |
| `create_app` | A small app can be created from a prompt with approval, checkpoint, validation, and rollback evidence. |
| `modify_app` | An existing app can be changed through proposal, diff, validation target, and rollback path. |
| `repair_validation` | A validation failure leads to one bounded repair attempt and a revalidation result. |
| `review_code` | Review mode reports findings without writing files. |
| `connect_provider` | Provider setup or route preview avoids plaintext secret export. |
| `use_local_model` | Local-only routing works or shows missing-model recovery. |
| `run_vscode_extension` | VS Code extension workflows reach Core or a documented local fallback. |
| `run_visual_studio_extension` | Visual Studio extension validation uses Core contracts or documented package validation. |
| `update_component` | Component updates include manifest compatibility and validation evidence. |
| `rollback_component` | Checkpoint restore records a clear result and next action. |

## Release Artifacts

An alpha release bundle should include:

- Core service package.
- Website package.
- Desktop package or installer.
- VS Code VSIX.
- Visual Studio VSIX.
- `version-manifest.json`.
- Release notes.
- Compatibility matrix.
- Known limitations.
- Migration notes.
- Privacy/security guide.
- Troubleshooting guide.

Signed installers should be produced where possible. If signatures are not available, checksum verification and the unsigned-build limitation must be explicit in the release notes.

## Recommended Alpha Scope

Recommended initial cohort:

- Trusted technical users only.
- Local-first workflows only.
- Engineering Workspace, validation, checkpoint, rollback, onboarding, plugin discovery, and diagnostics.
- No production deployment automation.
- No unrestricted autonomous execution.
- No high-risk plugins.
- No external telemetry upload.
- Distributed runtime only for a separate opt-in cohort.

The first alpha success criteria are practical: users can install, onboard, scan a real workspace, run a safe workflow, review validation, understand what changed, roll back if needed, export diagnostics, and clearly report friction.

## Known Limitations

The controlled alpha layer validates readiness and supportability. It does not guarantee that every subsystem is production-ready. Installer signing, update interruption recovery, multi-client long-session stability, distributed runtime trust, and high-risk plugin isolation should remain explicit release risks until they pass repeated dogfooding and external simulation cycles.
