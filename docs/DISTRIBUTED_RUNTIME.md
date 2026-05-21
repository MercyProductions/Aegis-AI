# Distributed Runtime

Distributed Runtime keeps Aegis local-first while adding a persistent node, workload, trust, recovery, and observability layer for LAN, remote, sandbox, validation, indexing, GPU/model, and team execution.

## Current Authority

Aegis Core is now the shared runtime authority for distributed execution contracts. Core persists node registration, workload scheduling decisions, audit events, recovery state, and bootstrap metadata under the workspace `.aegis` folder:

- `.aegis/distributed-runtime.json`
- `.aegis/distributed-runtime-audit.jsonl`

The Website backend still has an older compatibility surface for `/api/distributed-runtime` consumers. That Website surface should gradually delegate to Core's `/v1/distributed-runtime/*` endpoints, the same way apply/checkpoint/validation workflows migrated to Core-first behavior. Desktop, VS Code, and Visual Studio clients should treat Core as the preferred local authority and use Website only as a compatibility gateway where needed.

## Modules

- `aegis-core/aegis_core/distributed_runtime.py` owns the Core node registry, trust checks, workload queue, capability scheduler, local execution/fallback behavior, recovery, bootstrap scripts, JSON persistence, and audit events.
- `aegis-core/aegis_core/server.py` exposes versioned `/v1/distributed-runtime/*` contracts.
- `aegis-core/scripts/bootstrap-runtime-node.ps1` is the reference worker bootstrap script.
- `website/backend/aegis_ai/distributed_runtime.py` remains the Website compatibility implementation for existing Website API consumers while migration to Core continues.
- `website/backend/aegis_ai/storage.py` persists `runtime_workers`, `execution_queue`, `worker_audit_events`, and `workspace_sync_manifests` in SQLite.
- `website/backend/aegis_ai/main.py` exposes `/api/distributed-runtime` endpoints for workers, queue operations, dispatch, model routing, sync manifests, audit events, and observability.
- `website/frontend/src/types.ts` and `website/frontend/src/api.ts` expose browser/client contracts for node-management dashboards. Future UI work should consume the Core node/workload contracts directly or through Website gateway delegation.

## Core Runtime Nodes

Core supports these node categories:

- `local`
- `trusted_remote`
- `isolated_worker`
- `validation`
- `indexing`
- `gpu_model`

Every node advertises:

- node id, node type, endpoint, status, trust level, trust scope, heartbeat time
- CPU/GPU/RAM/storage hints
- supported workflow types
- installed models and plugins
- permission scopes
- max parallel workload count
- isolation profile
- transport/auth metadata
- current workload ids and count

## Worker Runtime

The Website compatibility layer still uses `WorkerCapabilitySet`. Core's equivalent node contract tracks the same intent:

- installed SDKs and supported languages
- build tools
- available models
- GPU, RAM, and CPU hints
- validation support
- supported sandbox profiles
- supported job kinds
- max parallel jobs
- remote-sync support

The default Core `local` node is created automatically from local machine capabilities. It is always local-first, trusted, and cannot be revoked through the API. Remote nodes must register with `AEGIS_DISTRIBUTED_NODE_TOKEN`, `AEGIS_CORE_LOCAL_TOKEN`, or explicit user approval. Untrusted nodes remain visible for diagnostics but are not eligible for scheduling.

## Core Workloads

Core distributed workloads are persisted as JSON under `.aegis`. Supported workload types are:

- `workflow`
- `validation`
- `indexing`
- `model_inference`
- `plugin_tool`
- `repair`
- `build`
- `benchmark`

Workloads track priority, retries, cancellation, node assignment, required capabilities, permission scopes, dry-run state, approval state, errors, warnings, scheduling reason, results, and operation logs.

Core schedules only to nodes that match trust, status, capacity, required capabilities, supported workflow type, required permission scopes, and remote opt-in rules. Remote nodes are assigned only when the workload explicitly sets `allow_remote=true`; assignment is audit logged and the workload remains `assigned` for a future external worker callback/transport. Local execution remains deterministic and conservative.

## Command And Sandbox Safety

Core command-backed jobs, including validation and build jobs, require explicit approval and payload opt-in before process execution. Without approval, validation workloads can still run in dry-run mode to discover safe validation commands. Actual command execution delegates to Core's existing validation allowlist.

Validation failures are attached to the task timeline. A focused repair job is queued as a follow-up event, but distributed repair jobs do not modify files directly; code edits still flow through the normal task runtime, approval gates, checkpoints, validation, and rollback behavior.

Plugin tool workloads delegate only to Core's permission-checked plugin runtime. Arbitrary plugin code remains blocked until an external sandbox runner exists.

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

Core's first distributed milestone focuses on node/workload authority. Blind workspace copying is still intentionally out of scope. Any future sync layer must preserve local checkpoints, audit logs, and user-approved workspace mounts.

## Observability

Core runtime observability aggregates:

- node counts by status and trust state
- queued/active/completed/failed/cancelled workload counts
- workload counts by type
- execution duration metrics
- scheduling policy metadata
- recent audit events
- offline/recovery events

All Core node registration, heartbeat, revocation, workload creation, retry, cancel, dispatch, recovery, and local execution operations write JSONL audit events.

## Endpoint Summary

Core endpoints:

- `GET /v1/distributed-runtime`
- `GET /v1/distributed-runtime/nodes`
- `POST /v1/distributed-runtime/nodes/register`
- `POST /v1/distributed-runtime/nodes/{node_id}/heartbeat`
- `POST /v1/distributed-runtime/nodes/{node_id}/revoke`
- `GET /v1/distributed-runtime/workloads`
- `POST /v1/distributed-runtime/workloads`
- `GET /v1/distributed-runtime/workloads/{workload_id}`
- `POST /v1/distributed-runtime/workloads/{workload_id}/dispatch`
- `POST /v1/distributed-runtime/workloads/{workload_id}/retry`
- `POST /v1/distributed-runtime/workloads/{workload_id}/cancel`
- `POST /v1/distributed-runtime/dispatch`
- `POST /v1/distributed-runtime/recover`
- `GET /v1/distributed-runtime/observability`
- `GET /v1/distributed-runtime/audit`
- `GET /v1/distributed-runtime/deployment/bootstrap`

Website compatibility endpoints:

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

## Deployment Model

Core exposes `GET /v1/distributed-runtime/deployment/bootstrap` to generate a node registration script. The checked-in PowerShell reference is `aegis-core/scripts/bootstrap-runtime-node.ps1`.

Operators should:

- run Core on localhost as the authority
- set `AEGIS_DISTRIBUTED_NODE_TOKEN` on Core and trusted worker nodes
- prefer HTTPS or local tunnel endpoints for remote nodes
- keep workspace mounts read-only by default
- approve high-risk scopes before validation, plugin, model, or write-capable work
- rely on `/v1/distributed-runtime/recover` to requeue work after node disconnects

## Remaining Limitations

- Remote node transport is currently an assignment contract, not a full RPC worker protocol.
- Container sandboxing is represented in node isolation metadata but not launched by Core yet.
- Workspace sync remains manifest-oriented and should not copy arbitrary files.
- Website `/api/distributed-runtime` is still a compatibility implementation and should delegate to Core in a follow-up.
