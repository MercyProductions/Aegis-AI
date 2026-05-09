# API Boundaries

Last updated: 2026-05-09

## Ports

| Runtime | Port | Contract | Owner |
| --- | ---: | --- | --- |
| Website backend | 8787 | `/api` plus `/health`, `/ready`, `/openapi.json` | `website/backend/aegis_ai/main.py` |
| Aegis Core | 8788 | `/v1` plus legacy Core aliases | `aegis-core/aegis_core/server.py` |
| Ollama | 11434 | Ollama API | local model server |
| Website frontend | 5173 | Vite dev UI | `website/frontend` |

`8788` is reserved for Aegis Core. A Website backend listening on 8788 is a runtime-boundary error.

## Website `/api`

Website `/api` is allowed to be broad because it backs the full Auralith OS app and Desktop client. Its stable consumer is the React UI and the native Desktop client.

Primary groups:

- `/api/health`, `/api/ready`
- `/api/core-runtime`
- `/api/auth/*`
- `/api/config`
- `/api/models`, `/api/model-registry/*`, `/api/model-manager/*`, `/api/model-benchmarks/*`
- `/api/files`, `/api/file`, `/api/file/slice`
- `/api/workspace/*`, `/api/project-intelligence/*`, `/api/workspace-intelligence/*`
- `/api/chat`, `/api/chat/stream`, `/api/routing/preview`
- `/api/apply`, `/api/checkpoints`, `/api/restore-checkpoint`
- `/api/validate`, `/api/verify`, `/api/validation/profile`
- `/api/project-builder/*`
- `/api/tasks/*`
- `/api/memory`, `/api/feedback`, `/api/approval/settings`
- `/api/distributed-runtime/*`
- `/api/telemetry/*`, `/api/adaptive-intelligence/*`
- `/api/productization/*`, `/api/ecosystem/*`, `/api/autonomous-engineering/*`
- `/api/media/*`, `/api/creative-studio/*`
- `/api/unified-runtime`, `/api/unified-context/*`, `/api/continuity`, `/api/platform-discipline`
- `/api/index/*`, `/api/diff/*`

Boundary rule:

Website `/api` may expose app-rich workflows, but any new cross-client primitive should first be considered for Core `/v1`.

`/api/core-runtime` is the exception-shaped adapter for consolidation. It is read-only, calls stable Core `/v1` endpoints, and returns Core envelopes under Website API compatibility.

## Aegis Core `/v1`

Aegis Core `/v1` is intentionally smaller. All responses use the envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "kind": "contract.kind",
  "workspace": "resolved workspace path or null",
  "data": {}
}
```

Current endpoint families:

| Endpoint | Purpose | Current client use |
| --- | --- | --- |
| `GET /v1/health` | Core, workspace, config, Ollama health | VS Code, Visual Studio, manual smoke |
| `GET /v1/models` | Shared local model inventory | validated, not yet direct client use |
| `GET /v1/settings` | Shared Core settings | validated, migration candidate |
| `POST /v1/settings` | Update shared Core settings | validated, migration candidate |
| `POST /v1/workspaces/scan` | Shared workspace scan/index | validated, migration candidate |
| `POST /v1/workspaces/roadmap` | Shared generated roadmap | validated, migration candidate |
| `GET /v1/memory` | Shared memory summary | validated, migration candidate |
| `GET /v1/diagnostics` | Shared diagnostics summary | validated, migration candidate |
| `GET /v1/branding` | Shared product/runtime/client tokens | validated, migration candidate |
| `POST /v1/clients/register` | Cross-client registration | Desktop, VS Code, Visual Studio |
| `GET /v1/clients` | Registered client list | dashboard/internal validation |
| `POST /v1/tasks` | Shared task creation | VS Code |
| `GET /v1/tasks` | Shared task listing | dashboard/internal validation |
| `POST /v1/tasks/{task_id}/status` | Shared task status update | VS Code |
| `POST /v1/validation` | Shared validation summary/run | validated, migration candidate |
| `POST /v1/agent/continue` | Plan-only continue from roadmap | validated, migration candidate |
| `POST /v1/agent/repair` | Plan-only repair from last validation | validated, migration candidate |
| `GET /v1/ecosystem/dashboard` | Shared clients/tasks/model/diagnostics dashboard | Desktop |

Boundary rule:

Core `/v1` should expose shared primitives, not full Website product surfaces.

## Current Client Calls

Code search found these direct `/v1` calls:

| Client | Direct Core calls |
| --- | --- |
| Desktop | `/v1/clients/register`, `/v1/ecosystem/dashboard` |
| VS Code | `/v1/health`, `/v1/clients/register`, `/v1/tasks`, `/v1/tasks/{task_id}/status` |
| Visual Studio | `/v1/health`, `/v1/clients/register` |
| Website frontend | none direct |
| Website backend | `/v1/health`, `/v1/models`, `/v1/settings`, `/v1/memory`, `/v1/diagnostics`, `/v1/ecosystem/dashboard` through `/api/core-runtime` |

## Migration Order

1. Keep Website `/api` stable for Website and Desktop.
2. Keep Core `/v1` stable and covered by endpoint-family tests.
3. Move shared read-only primitives first: health, models, settings, memory, diagnostics, dashboard.
4. Move shared task lifecycle next.
5. Move workspace scan, roadmap, and validation only after IDE-specific context needs are represented.
6. Leave rich app workflows in Website `/api` until there is a clear multi-client need.
