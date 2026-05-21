# Desktop Core Client Runtime

Aegis Desktop is now a first-class Aegis Core client for runtime workflows. The native C++ app still keeps Website API compatibility, but the preferred local runtime path for migrated workflows is Core.

## Runtime Ownership

- Aegis Core is the local authority for file-change application, checkpoint restore, validation runs, workflow registration, client sync, and workspace scans.
- The Website backend remains a compatibility gateway for chat, streaming chat, model registry write/benchmark surfaces, Creative Studio, memory, telemetry, and product-specific APIs that have not moved fully into Core yet.
- Desktop records which runtime handled each operation so fallback behavior is visible instead of hidden.

## Desktop Core API Layer

The Core client lives in:

- `src/core/CoreApiClient.h`
- `src/core/CoreApiClient.cpp`

The existing `AegisClient` public API remains stable for the UI. For migrated workflows, `AegisClient` now tries Core first and falls back to Website when Core is offline or does not support the operation.

Core-first workflows:

- workspace scan through `/v1/workspaces/scan`
- client registration through `/v1/clients/sync`
- ecosystem dashboard through `/v1/ecosystem/dashboard`
- shared model/provider registry through `/v1/models/registry`
- apply generated changes through `/v1/changes/apply`
- checkpoint list through `/v1/checkpoints`
- checkpoint restore through `/v1/checkpoints/restore`
- validation through `/v1/validation/run`
- repair workflow creation through `/v1/workflows` with `repair_project`
- roadmap workflow creation through `/v1/workflows` with `continue_roadmap`

Website fallback remains in place for the same Desktop-facing methods. Core safety rejections such as unsafe paths, secret-like paths, and workspace escape attempts are not bypassed by fallback.

## Runtime Status UI

The Desktop right rail includes a Runtime Status panel showing:

- Core connection state
- Website API connection state
- Ollama/model runtime state
- registered Desktop client ID
- active workflow ID when Core reports one
- last operation and runtime handler
- fallback mode and last fallback reason
- recent operation log entries

## Manual Smoke Checklist

1. Launch Aegis Core on `http://127.0.0.1:8788`.
2. Launch the Desktop app with the Website backend online.
3. Confirm the Runtime Status panel shows Core, Website, and Ollama states.
4. Apply a generated change and confirm the last operation is `changes.apply / core`.
5. Open Checkpoint Browser and restore a checkpoint.
6. Run Validation and confirm the result is captured without crashing on failed validation.
7. Stop Aegis Core and repeat apply/checkpoint/validation; Desktop should use Website fallback and show fallback mode.
8. Stop the Website backend with Core online; Desktop should still show Core connected and keep Core-owned workflows available.

## Remaining Website-Owned Areas

These Desktop surfaces still primarily use Website APIs until later migration slices:

- chat and streaming chat
- model registry writes, model manager, and benchmark/policy application
- model benchmarks
- memory notes
- Creative Studio media jobs
- route telemetry and policy diff
- full verification pipeline
- project builder/scaffolding

The next migration should move chat workflow creation, validation repair execution, full verification, model registry writes/benchmark application, and Creative Studio job orchestration behind Core contracts while keeping the existing Desktop UI stable.
