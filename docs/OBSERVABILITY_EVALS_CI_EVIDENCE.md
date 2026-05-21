# Observability, Evals, And CI Evidence

Generated: 2026-05-21

Phase 33 turns the existing golden workflow, telemetry, and validation contracts into a CI-backed release signal. The GitHub Actions workflow now runs the main project gates on Windows and keeps the full ecosystem matrix available as an explicit manual workflow.

Machine-readable contract: `evals/phase33-observability-ci-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-observability-ci.ps1
```

Evidence output:

```text
.aegis/observability-ci/<timestamp>/
```

## What It Checks

- GitHub Actions exists at `.github/workflows/aegis-validation.yml`.
- CI includes Core tests, Website backend tests, Website frontend tests/build, desktop contract/build, VS Code unit/lint guards, Visual Studio validation guards, release/evidence contracts, and a manual full ecosystem matrix.
- CI runs the Phase 12 quality contract, Phase 33 observability CI contract, Phase 31 memory governance contract, Phase 32 plugin lifecycle contract, and Phase 16 evidence ledger contract.
- Golden workflow evidence stays linked through `evals/phase12-quality-contract.json` and `website/backend/tests/test_golden_workflows.py`.
- Telemetry evidence keeps route quality, fallback inspector, feedback, snapshot, policy diff, token calibration, and structured preview markers.

## Current Status

The required status is `ready` once the validator writes `observability-ci.json` and `observability-ci-summary.md` with no failed checks.

This phase does not replace release-candidate smoke. It makes missing observability, eval, and CI wiring fail before a manual alpha pass.
