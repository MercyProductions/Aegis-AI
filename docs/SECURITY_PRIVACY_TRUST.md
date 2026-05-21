# Security, Privacy, And Trust Model

Aegis is local-first software with direct workspace access. The security model assumes every runtime workflow must be inspectable, approval-aware, checkpointed, reversible, and conservative about provider context.

## Local API Protection

Aegis Core binds to `127.0.0.1` by default and rejects non-loopback `Host` or client addresses at the app layer. Core also enforces browser origin checks, request size limits, and per-client rate limits.

Set `AEGIS_CORE_LOCAL_TOKEN` to require local bearer authentication for Core:

```powershell
$env:AEGIS_CORE_LOCAL_TOKEN = "<random local token>"
python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
```

Clients may send either `Authorization: Bearer <token>` or `X-Aegis-Local-Token`. Website, VS Code, and Visual Studio clients now forward `AEGIS_CORE_LOCAL_TOKEN` / `AEGIS_LOCAL_AUTH_TOKEN` when configured. Token enforcement remains opt-in during compatibility migration so existing clients do not break silently; `/v1/security/status` reports whether token enforcement is active.

Website backend has a matching compatibility layer:

- `AEGIS_REQUIRE_LOCAL_API_TOKEN=true`
- `AEGIS_LOCAL_API_TOKEN=<random local token>`
- `AEGIS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173`
- `AEGIS_MAX_REQUEST_BYTES=8000000`
- `AEGIS_RATE_LIMIT_PER_MINUTE=600`

## Workspace File Safety

Core-owned editing runtime rejects:

- absolute paths and path traversal
- files outside the workspace root
- ignored dependency/generated directories
- hidden directories except explicit safe `.aegis` state written by Core
- secret-like files such as `.env`, keys, certificates, and credential names
- oversized writes

Core applies file changes only after checkpoint protection unless the request is a dry-run. Checkpoint restore creates a pre-restore checkpoint so rollback stays available.

## Provider Credentials

Provider API keys must not be written to project config files. Core stores provider keys through the OS credential store: Python keyring when available, or Windows Credential Manager on Windows. Responses report status such as `key_stored` and `credential_store: "os"` without returning secret values.

Diagnostics, bridge errors, Website feedback capture, VS Code logs, and Visual Studio diagnostics redact secret-like values before storing or displaying logs.

## Privacy Controls

Core routing honors:

- `AEGIS_PRIVACY_MODE=local-first|local-only|cloud-disabled`
- `AEGIS_CLOUD_DISABLED=true`
- per-workflow `privacy_sensitive`
- route profiles such as `local_only`, `private_sensitive`, and `fallback_safe`

When cloud is disabled or a workflow is privacy-sensitive, Core forces local routing and emits route warnings. Secret-like, ignored, or outside-workspace context files are excluded before cloud calls.

## Update Trust

The update launcher validates:

- manifest version and schema
- declared component package metadata
- package artifact/path consistency
- SHA256 checksum format and value
- signature policy when local-build signature opt-out is disabled
- downgrade protection unless `-AllowDowngrade` is explicitly provided
- backup and rollback state before apply

Update failures are recorded in `.aegis/update-state.json`; security-relevant update events are appended to `.aegis/security-audit.jsonl`.

## Audit Logs

Core writes security audit events to:

```text
<workspace>/.aegis/security-audit.jsonl
```

Website writes gateway audit events to:

```text
website/.aegis/security-audit.jsonl
```

Audited event categories include unauthorized local API access, rejected browser origins, request size/rate-limit blocks, unsafe workspace paths, provider calls, validation runs, update package verification, failed update checks, approvals, and rollbacks.

## Trust Surfaces

- Core: `GET /v1/security/status`
- Website: `GET /api/security/status`
- Website UI: Agent Activity Center shows privacy/local API/secrets trust state.
- Desktop: Runtime Status panel reports local-first privacy, cloud approval, redaction, checkpoint expectations.
- VS Code and Visual Studio: Core clients can forward local auth tokens and query Core security status.

## Remaining Risks

Token enforcement is intentionally compatibility-gated until all launchers and clients share local token provisioning. Signature verification is available through Authenticode policy but local builds still allow unsigned packages unless the manifest disables that opt-out. A future pass should add automated token bootstrap, signed release channels, stronger CSRF coverage for cookie-backed Website sessions, and deeper sensitive-content classification before any cloud provider call.
