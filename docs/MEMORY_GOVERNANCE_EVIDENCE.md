# Memory Governance Evidence

Generated: 2026-05-21

Phase 31 makes Website memory routes carry the Core personal-memory governance contract instead of flattening everything into legacy notes. The Website compatibility API now exposes memory policy, privacy, export, and controls surfaces while preserving the old list/create/update/delete shape.

Machine-readable contract: `evals/phase31-memory-governance-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-memory-governance.ps1
```

Evidence output:

```text
.aegis/memory-governance/<timestamp>/
```

## What It Checks

- `/api/memory` list responses include governance, privacy, controls, runtime, and delegation metadata.
- `/api/memory/governance` exposes local-only/cloud-sharing state, consent requirements, category controls, audit availability, retention, export/delete affordances, and storage boundary.
- `/api/memory/export` delegates to Core when available and redacts secret-like legacy fallback content before export.
- `/api/memory/controls` delegates category and local-only control updates to Core personal-memory controls.
- Legacy Website memory fallback remains local-only and inspectable while clearly reporting that category-control writes require Core.
- Frontend API/types include governance, export, and controls helpers for the memory UI to consume.

## Current Status

The required status is `ready` once the validator writes `memory-governance.json` and `memory-governance-summary.md` with no failed checks.

This phase does not redesign the Memory UI. It establishes the typed backend and frontend contract needed for the next UI pass to show memory privacy controls safely.
