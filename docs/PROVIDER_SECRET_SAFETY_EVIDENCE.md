# Provider Secret Safety Evidence

Generated: 2026-05-21

Phase 30 makes provider setup and route selection safer for real testers by adding a structured route-safety summary to every provider status. The summary explains whether a route is local, API-key based, delegated through an official CLI, environment-profile based, OAuth-pending, or unsupported, and records the privacy, secret-storage, context-consent, cost, quota, latency, fallback, and diagnostics boundaries for that route.

Machine-readable contract: `evals/phase30-provider-secret-safety-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-provider-secret-safety.ps1
```

Evidence output:

```text
.aegis/provider-secret-safety/<timestamp>/
```

## What It Checks

- Provider snapshots expose `route_safety` without storing raw API keys in SQLite or diagnostic payloads.
- API-key routes document OS credential-store storage and require cloud-context consent before workspace context can leave the machine.
- CLI routes document official provider CLI delegation and the no-token-import boundary.
- Local runtime routes document that no provider credential is required and cloud consent is not needed.
- Provider account, session, CLI bridge, readiness, and route-safety error details are redacted before they leave the manager.
- Frontend provider readiness cards prefer backend safety boundaries and redact secret-like fallback text before display.

## Current Status

The required status is `ready` once the validator writes `provider-secret-safety.json` and `provider-secret-safety-summary.md` with no failed checks.

This phase does not run live provider calls. It locks the local contract and regression tests that make live provider setup safer in later alpha work.
