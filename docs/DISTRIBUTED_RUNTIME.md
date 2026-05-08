# Distributed Runtime

Distributed Runtime keeps Aegis local-first while adding a persistent worker and queue layer for future LAN, remote, sandbox, and team execution.

## Modules

- `website/backend/aegis_ai/distributed_runtime.py` owns worker capability policy, trust checks, runnable-job selection, worker assignment, hybrid model routing, sync manifest hashing, audit event creation, and runtime observability aggregation.
- `website/backend/aegis_ai/storage.py` persists `runtime_workers`, `execution_queue`, `worker_audit_events`, and `workspace_sync_manifests` in SQLite.
- `website/backend/aegis_ai/main.py` exposes `/api/distributed-runtime` endpoints for workers, queue operations, dispatch, model routing, sync manifests, audit events, and observability.
- `website/frontend/src/types.ts` and `website/frontend/src/api.ts` expose typed browser/client contracts for future desktop, browser, mobile, and remote dashboards.

## Worker Runtime

Every runtime worker advertises a `WorkerCapabilitySet`:

- installed SDKs and supported languages
- build tools
- available models
- GPU, RAM, and CPU hints
- validation support
- supported sandbox profiles
- supported job kinds
- max parallel jobs
- remote-sync support

The default `local-runtime` worker is created automatically from local machine capabilities. It is always local-first, trusted, and cannot be revoked through the API. LAN and remote workers must register with a deterministic signature over worker id, name, trust scope, and public key. Invalid signatures persist as untrusted workers and are not eligible for dispatch.

## Execution Queue

Execution jobs are persisted as `ExecutionQueueItem` rows. Supported kinds are:

- `task`
- `validation`
- `build`
- `indexing`
- `repair`
- `benchmark`
- `telemetry`
- `sync`

The queue supports priority ordering, dependency ordering, retries, cancellation, worker assignment, permission scope checks, sandbox profile selection, attempts, error summaries, and result summaries. Runnable jobs are selected only when dependencies have succeeded and attempts remain below `max_attempts`.

Local and sandbox workers execute synchronously through the backend process. LAN and remote workers are assigned only when the dispatch request explicitly sets `allow_remote=true`; assignment is audit logged and the job remains `assigned` for a future worker callback/heartbeat flow.

## Command And Sandbox Safety

Command-backed jobs, including validation and build jobs, require `allow_commands=true` at dispatch time. The queue still delegates to the existing `CommandRunner`, allowlist, approval settings, and sandbox profiles. A blocked command becomes a `blocked` job instead of running silently.

Validation failures are attached to the task timeline. A focused repair job is queued as a follow-up event, but distributed repair jobs do not modify files directly; code edits still flow through the normal task runtime, approval gates, checkpoints, validation, and rollback behavior.

## Hybrid Model Routing

`HybridRouteRequest` evaluates local worker models, LAN/remote worker models, and provider registry models. Routing considers:

- privacy mode: local only, local first, hybrid, or cloud allowed
- workspace sensitivity
- context size
- latency priority
- cost priority
- reasoning difficulty
- required capabilities

High-sensitivity work avoids cloud providers unless cloud use is explicitly allowed. Local-only requests filter out every non-local candidate.

## Remote Sync

Remote workspace sync is currently a manifest/export layer, not a blind file copier. A sync manifest can include:

- task history
- checkpoints
- project memory
- architecture maps
- validation profiles
- non-secret settings

The manifest stores included sections, a payload, an encrypted flag, and a deterministic hash over the canonical payload. The current `encryption_label` records the local manifest-hash mode so future encrypted transport can be layered without changing the API shape.

## Observability

`RuntimeObservabilitySnapshot` aggregates:

- worker counts by status and trust state
- queued/running/failed/succeeded job counts
- throughput by job kind
- model latency by worker
- validation success rate
- repair-loop counts
- queue latency

All worker registration, heartbeat, revocation, queue creation, retry, cancel, dispatch, model route, and sync manifest operations write `WorkerAuditEvent` rows.

## Endpoint Summary

- `GET /api/distributed-runtime`
- `GET /api/distributed-runtime/observability`
- `GET /api/distributed-runtime/workers`
- `POST /api/distributed-runtime/workers/register`
- `POST /api/distributed-runtime/workers/{worker_id}/heartbeat`
- `POST /api/distributed-runtime/workers/{worker_id}/revoke`
- `GET /api/distributed-runtime/queue`
- `POST /api/distributed-runtime/queue`
- `GET /api/distributed-runtime/queue/{job_id}`
- `POST /api/distributed-runtime/queue/{job_id}/cancel`
- `POST /api/distributed-runtime/queue/{job_id}/retry`
- `POST /api/distributed-runtime/dispatch`
- `POST /api/distributed-runtime/route`
- `GET /api/distributed-runtime/audit`
- `GET /api/distributed-runtime/sync/manifests`
- `POST /api/distributed-runtime/sync/export`

## Compatibility Rules

- Local execution must keep working fully offline.
- Remote dispatch must be opt-in per dispatch request.
- Remote/LAN workers must be trusted before assignment.
- Command-backed jobs must require explicit command permission.
- Distributed repair must not silently modify workspace files.
- Queue and worker changes must be audit logged.
- Existing task, validation, checkpoint, rollback, provider registry, and desktop API behavior remains the compatibility baseline.
