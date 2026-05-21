# Real-World Dogfooding and Workflow Refinement

Auralith OS should now be used as a daily engineering environment. This phase is not about adding broad new architecture. It is about finding friction through real use and tightening the workflows that already matter.

## Dogfooding Rule

Use Auralith OS for real work, then record friction whenever a workflow is slow, unclear, repetitive, noisy, abandoned, or hard to trust.

Core stores dogfooding signals locally under `.aegis`:

- `.aegis/dogfooding-events.jsonl`
- `.aegis/dogfooding-report.json`
- `.aegis/dogfooding-summary.md`

Events are local-first. Notes and metadata are redacted before storage.

## Core APIs

- `GET /v1/dogfooding`
- `POST /v1/dogfooding/events`
- `GET /v1/dogfooding/friction`
- `GET /v1/dogfooding/confidence`
- `GET /v1/dogfooding/workflows`
- `GET /v1/dogfooding/long-session-plan`

Use these contracts from Website, Desktop, VS Code, and Visual Studio when adding dogfooding surfaces.

## Workflows To Dogfood

Feature development:

1. Open workspace.
2. Scan project.
3. Generate or select roadmap item.
4. Propose change.
5. Review risk and diff.
6. Checkpoint.
7. Apply.
8. Validate.
9. Record friction.

Bug fixing:

1. Run validation or build.
2. Capture failure.
3. Ask Auralith Prime for targeted repair.
4. Review proposal.
5. Apply after approval.
6. Revalidate.
7. Stop after bounded repair attempts.

Roadmap tracking:

1. Generate roadmap.
2. Mark completed, in-progress, and blocked work.
3. Execute one roadmap item.
4. Link checkpoint and validation result.
5. Record dead ends or duplicate actions.

Deployment validation:

1. Scan CI/CD and environment files.
2. Review risk and secret boundaries.
3. Generate dry-run deployment plan.
4. Confirm rollback readiness.
5. Do not deploy production without explicit approval gates.

Plugin development:

1. Create or inspect plugin manifest.
2. Review permissions and compatibility.
3. Run validator.
4. Observe load failures and diagnostics.
5. Record permission or discovery confusion.

## Friction Tags

Use these tags consistently:

- `too_many_clicks`
- `confusing_terminology`
- `duplicate_action`
- `unclear_approval`
- `noisy_panel`
- `workflow_dead_end`
- `overwhelming_configuration`
- `setup_friction`
- `startup_slow`
- `slow_workflow`
- `validation_pain`
- `repair_loop`
- `rollback_unclear`
- `roadmap_unhelpful`
- `diff_unclear`
- `diagnostics_unclear`
- `error_message_unclear`
- `onboarding_friction`
- `model_routing_unclear`
- `plugin_confusion`
- `interrupted_stream`
- `indexing_slow`
- `maintainability_drag`

## Production Confidence Metrics

Core summarizes:

- crash-free sessions
- successful workflow completion
- rollback recovery success
- validation reliability
- orchestration stability
- update reliability

These metrics should guide polish priorities before new feature work.

## UX Refinement Priorities

Prefer improvements that reduce real friction:

- keyboard-driven scan, validate, checkpoint, apply, rollback, and continue-roadmap actions
- one approval panel that names files, risk, validation state, checkpoint state, and rollback path
- low-noise default panels centered on the active workflow
- local-only onboarding with fewer choices
- progress visibility for slow indexing, validation, and model calls
- retry/revise/rollback/log actions after failures

## Long-Session Tests

Run these before release candidates:

- multi-hour daily-driver session
- large-project indexing and navigation session
- many-workflow session
- plugin-heavy session
- trusted distributed-node session

Pass condition:

No crash, no lost state, clear rollback path, and no workflow dead end without a next action.

## Systems To Simplify First

- Website protected app shell
- Desktop command surface
- VS Code extension monolith
- Website runtime fallback paths
- Experimental Labs surfaces

## Reporting Cadence

At the end of each dogfooding cycle, report:

- biggest workflow pain points
- UX simplifications shipped
- performance bottlenecks
- systems removed or simplified
- trust improvements
- recommended polish priorities

Weekly reviews should classify friction with the most specific tag available. For example, use `startup_slow` for launch readiness delays, `indexing_slow` for scan/index delays, `roadmap_unhelpful` for vague or stale roadmap output, `diff_unclear` for hard-to-review proposals, `diagnostics_unclear` or `error_message_unclear` for failures without a clear next action, `onboarding_friction` for first-run setup pain, and `maintainability_drag` when implementation coupling slows safe fixes.

## Phase 14 Evidence Loop

Machine-readable contract: `evals/phase14-alpha-readiness-contract.json`.

Run the fast alpha contract before and after each dogfooding cycle:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-alpha-contract.ps1
```

The command writes `.aegis/alpha-evidence/<timestamp>/alpha-contract.json` and `alpha-contract-summary.md`. Attach that evidence to the dogfooding report when a cycle changes onboarding, recovery cards, alpha feature scope, feedback categories, release channels, diagnostics export, or the scenario suite.

The product should become calmer and faster through use, not broader through speculation.
