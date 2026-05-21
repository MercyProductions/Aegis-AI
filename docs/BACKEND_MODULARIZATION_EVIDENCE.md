# Backend Modularization Evidence

Generated: 2026-05-21

Phase 26 starts reducing risk in the largest Website backend files. The first slice moves Core route-preview request shaping and response mapping out of `website/backend/aegis_ai/main.py` and into `website/backend/aegis_ai/services/route_preview_service.py`.

Machine-readable contract: `evals/phase26-backend-modularization-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-backend-modularization.ps1
```

Evidence output:

```text
.aegis/backend-modularization/<timestamp>/
```

## What It Checks

- `main.py` remains the route orchestrator and imports the route-preview service.
- Core route-preview mapping functions live in `services/route_preview_service.py`.
- The old private helper block no longer lives in `main.py`.
- Focused service tests cover Core route payload shaping, Core route response mapping, fallback preservation, and ownership alignment.

## Current Status

The required status is `ready` once the validator writes `backend-modularization.json` and `backend-modularization-summary.md` with no failed checks.

This is intentionally a narrow modularization slice. The next backend slices should continue extracting planning, streaming, storage, repair, and provider-account behavior into bounded service modules.
