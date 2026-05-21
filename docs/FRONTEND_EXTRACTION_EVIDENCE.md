# Frontend Extraction Evidence

Generated: 2026-05-21

Phase 27 starts reducing risk in the large Website React shell. The first slice moves agent bridge provider/runtime selection logic out of `website/frontend/src/App.tsx` and into `website/frontend/src/utils/agentBridgeProviders.ts`.

Machine-readable contract: `evals/phase27-frontend-extraction-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-frontend-extraction.ps1
```

Evidence output:

```text
.aegis/frontend-extraction/<timestamp>/
```

## What It Checks

- `App.tsx` imports bridge-provider helpers instead of owning provider classification and runtime-target selection.
- `agentBridgeProviders.ts` owns external/local provider classification, model-family matching, runtime labels, and local runtime target selection.
- Focused Vitest coverage locks the provider routing decisions used by the agent workspace provider dock.
- The production frontend build still passes after the extraction.

## Current Status

The required status is `ready` once the validator writes `frontend-extraction.json` and `frontend-extraction-summary.md` with no failed checks.

This is intentionally a narrow frontend extraction slice. The next frontend slices should continue moving large route surfaces and panel renderers out of `App.tsx` into focused feature components.
