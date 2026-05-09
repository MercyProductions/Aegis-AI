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
  "contract_version": "2026.05.09",
  "contract_versions": {
    "health": "2026.05.09",
    "models": "2026.05.09"
  },
  "workspace": "C:/path/to/project",
  "ownership": {
    "shared_runtime": "aegis-core",
    "application_runtime": "website-backend",
    "migration_phase": "unified-contract-client-compatibility-phase"
  },
  "health": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "health", "data": {}},
  "models": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "models", "data": {}},
  "settings": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "settings", "data": {}},
  "memory": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "memory.summary", "data": {}},
  "diagnostics": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "diagnostics.summary", "data": {}},
  "dashboard": {"ok": true, "api_version": "v1", "contract_version": "2026.05.09", "kind": "ecosystem.dashboard", "data": {}},
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
  "contract_version": "2026.05.09",
  "kind": "contract.kind",
  "workspace": "C:/path/to/project",
  "data": {},
  "stability": "stable",
  "deprecated": false,
  "deprecations": []
}
```

Client parsing rules:

- Validate `api_version` before trusting the response. Current clients expect `v1`.
- Validate `kind` against the endpoint contract listed below.
- Treat unknown top-level or `data` fields as additive and safe to ignore.
- Treat missing optional `data` fields as a degraded or empty state, not a parser crash.
- For sync/mutation calls, treat `ok: false` as a useful Core error and surface `data.error`, `data.message`, or `deprecations` when present.

Endpoint families:

| Endpoint | Contract kind | Stability | Purpose |
| --- | --- | --- | --- |
| `GET /v1/health` | `health` | stable | Shared Core, workspace, config, and Ollama health |
| `GET /v1/models` | `models` | stable | Shared local model inventory |
| `GET /v1/settings` | `settings` | stable | Shared Core settings |
| `POST /v1/settings` | `settings.updated` | stable | Update shared Core settings |
| `POST /v1/workspaces/scan` | `workspace.scan` | stable | Shared workspace scan/index |
| `POST /v1/workspaces/roadmap` | `workspace.roadmap` | stable | Shared roadmap generation |
| `GET /v1/memory` | `memory.summary` | stable | Shared memory summary |
| `GET /v1/diagnostics` | `diagnostics.summary` | stable | Shared diagnostics summary |
| `GET /v1/branding` | `branding.tokens` | experimental | Shared product/runtime/client tokens |
| `POST /v1/clients/register` | `client.registered` | stable | Cross-client registration |
| `GET /v1/clients` | `clients.list` | stable | Cross-client list |
| `POST /v1/tasks` | `task.created` | stable | Shared task creation |
| `GET /v1/tasks` | `tasks.list` | stable | Shared task list |
| `POST /v1/tasks/{task_id}/status` | `task.updated` | stable | Shared task status update |
| `POST /v1/validation` | `validation` | stable | Shared validation summary/run |
| `POST /v1/agent/continue` | `agent.continue.plan` | experimental | Plan-only continue from roadmap |
| `POST /v1/agent/repair` | `agent.repair.plan` | experimental | Plan-only repair from validation log |
| `GET /v1/ecosystem/dashboard` | `ecosystem.dashboard` | stable | Shared clients/tasks/model/diagnostics dashboard |

Schema-only experimental contracts are defined in `aegis-core/aegis_core/contracts.py` for `patch.proposal`, `rollback.entry`, and `rollback.result`. They are intentionally not active write endpoints yet.

See `aegis-core/docs/API_REFERENCE.md` for the Core-only details and examples.
