# Core Website Ownership Evidence

Generated: 2026-05-21

Phase 25 locks the boundary between Aegis Core and the Website compatibility API. The goal is not to remove every Website route. The goal is to make ownership explicit enough that duplicated runtime behavior cannot drift quietly.

Machine-readable contract: `evals/phase25-core-website-ownership-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-core-website-ownership.ps1
```

Evidence output:

```text
.aegis/core-website-ownership/<timestamp>/
```

## What It Checks

- `website/backend/aegis_ai/runtime_ownership.py` remains the ownership source of truth.
- `GET /api/runtime/ownership` exposes the same policy to Website clients.
- Core-owned domains still have Core client delegation and `/v1` server routes.
- Website route modules for apply, validation, and checkpoints stay thin compatibility adapters.
- Provider account setup remains Website-owned.
- React frontend has a typed `getRuntimeOwnership` client contract.
- Desktop, VS Code, and Visual Studio still align with their current Core or Website migration posture.

## Current Status

The required status is `ready` once the validator produces `core-website-ownership.json` and `core-website-ownership-summary.md` with no failed checks.

This evidence is also read by the Phase 16 evidence ledger so ownership drift is visible in release evidence.
