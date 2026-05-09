# API Reference

Last updated: 2026-05-09

This repository currently exposes two API layers:

- Website backend `/api` on `http://127.0.0.1:8787`
- Aegis Core `/v1` on `http://127.0.0.1:8788`

The Website backend is the product/application API. Aegis Core is the shared runtime API.

## Website `/api`

Website `/api` remains backwards compatible for the React UI and Desktop app.

Stable product groups:

- `GET /api/health`, `GET /api/ready`
- `GET/POST /api/config`
- `GET /api/models`
- `GET /api/files`, `GET /api/file`, `GET /api/file/slice`
- `POST /api/chat`, `POST /api/chat/stream`
- `POST /api/routing/preview`
- `POST /api/apply`
- `GET /api/checkpoints`, `POST /api/restore-checkpoint`
- `POST /api/validate`, `POST /api/verify`
- `GET/PUT /api/validation/profile`
- `GET/POST /api/tasks` and task actions/timeline/artifacts
- `GET/POST/PUT/DELETE /api/memory`
- `POST /api/feedback`
- `GET/PUT /api/approval/settings`
- `POST /api/project-builder/plan`, `/preview`, `/scaffold`

Product/advanced groups that stay Website-owned for now:

- model registry, model manager, model benchmarks
- workspace/project intelligence
- unified runtime/context, continuity, platform discipline
- distributed runtime, adaptive intelligence, productization, ecosystem, autonomous engineering
- Creative Studio/media
- auth/session APIs

## Website-to-Core Bridge

`GET /api/core-runtime`

Query:

- `workspace_root`: optional Website workspace path

Returns a Website wrapper around stable Core `/v1` envelopes:

```json
{
  "ok": true,
  "reachable": true,
  "core_url": "http://127.0.0.1:8788",
  "api_version": "v1",
  "workspace": "C:/path/to/project",
  "ownership": {
    "shared_runtime": "aegis-core",
    "application_runtime": "website-backend",
    "migration_phase": "runtime-consolidation-phase-1"
  },
  "health": {"ok": true, "api_version": "v1", "kind": "health", "data": {}},
  "models": {"ok": true, "api_version": "v1", "kind": "models", "data": {}},
  "settings": {"ok": true, "api_version": "v1", "kind": "settings", "data": {}},
  "memory": {"ok": true, "api_version": "v1", "kind": "memory.summary", "data": {}},
  "diagnostics": {"ok": true, "api_version": "v1", "kind": "diagnostics.summary", "data": {}},
  "dashboard": {"ok": true, "api_version": "v1", "kind": "ecosystem.dashboard", "data": {}},
  "errors": []
}
```

This endpoint is read-only. It is the first compatibility adapter for moving shared runtime reads toward Aegis Core without breaking Website `/api`.

## Aegis Core `/v1`

All Core `/v1` responses use this envelope:

```json
{
  "ok": true,
  "api_version": "v1",
  "kind": "contract.kind",
  "workspace": "C:/path/to/project",
  "data": {}
}
```

Endpoint families:

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health` | Shared Core, workspace, config, and Ollama health |
| `GET /v1/models` | Shared local model inventory |
| `GET /v1/settings` | Shared Core settings |
| `POST /v1/settings` | Update shared Core settings |
| `POST /v1/workspaces/scan` | Shared workspace scan/index |
| `POST /v1/workspaces/roadmap` | Shared roadmap generation |
| `GET /v1/memory` | Shared memory summary |
| `GET /v1/diagnostics` | Shared diagnostics summary |
| `GET /v1/branding` | Shared product/runtime/client tokens |
| `POST /v1/clients/register` | Cross-client registration |
| `GET /v1/clients` | Cross-client list |
| `POST /v1/tasks` | Shared task creation |
| `GET /v1/tasks` | Shared task list |
| `POST /v1/tasks/{task_id}/status` | Shared task status update |
| `POST /v1/validation` | Shared validation summary/run |
| `POST /v1/agent/continue` | Plan-only continue from roadmap |
| `POST /v1/agent/repair` | Plan-only repair from validation log |
| `GET /v1/ecosystem/dashboard` | Shared clients/tasks/model/diagnostics dashboard |

See `aegis-core/docs/API_REFERENCE.md` for the Core-only details and examples.
