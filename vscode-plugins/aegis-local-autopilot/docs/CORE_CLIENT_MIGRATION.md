# VS Code Core Client Migration

The VS Code extension is now a first-class Aegis Core client. Core is the preferred runtime authority for shared workflow state, proposal metadata, apply/checkpoint/rollback, validation result storage, repair workflow tracking, client sync, and workflow event streaming.

## Runtime Split

- VS Code owns editor integration: commands, selections, diff previews, approval prompts, webview rendering, and local fallback.
- Aegis Core owns shared runtime contracts: `/v1/changes/*`, `/v1/checkpoints/*`, `/v1/validation/run`, `/v1/workflows/*`, `/v1/clients/sync`, jobs, activity, and workflow event history.
- Local Ollama prompting remains in VS Code for chat and proposal generation until Core provider orchestration is mature enough to take it over.

## Core-First Flows

The extension now attempts Core first for:

- workspace scan
- roadmap generation and continuation tracking
- chat/agent workflow registration
- proposal storage and patch preview metadata
- approved apply with mandatory Core checkpoint
- rollback from Core checkpoint
- validation run and stored result capture
- repair workflow creation
- client sync dashboard and workflow event stream refresh

If Core is unreachable, the extension logs fallback mode and uses the existing local implementation where safe.

## Safety Model

Before apply, VS Code still shows diffs and requires approval. It validates proposal paths locally, then Core validates them again. Core rejections are treated as authoritative and are not retried through local fallback. Network/offline failures can fall back to local backups and local apply.

Rollback uses the Core checkpoint when an applied change was handled by Core. Older local backup manifests still use the local `.aegis/backups` restore path.

## Configuration

Set `aegisLocalAutopilot.coreUrl` to the running Core server. The default is:

```text
http://127.0.0.1:8788
```

The sidebar Runtime Status panel shows connection state, fallback mode, active workflow ID, latest validation, checkpoint availability, and recent operations.

## Remaining Migration

- Move model/provider orchestration for chat and proposal generation into Core.
- Replace older `/v1/tasks` compatibility records with workflow graph tasks everywhere.
- Use long-lived event streams with reconnection offsets instead of short refresh streams.
- Surface Core activity/jobs in richer VS Code tree views once the runtime contracts settle.
