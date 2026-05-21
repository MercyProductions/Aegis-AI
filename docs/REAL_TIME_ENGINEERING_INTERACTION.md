# Real-Time Engineering Interaction

Real-time engineering interaction makes Aegis Core the local authority for live workflow visibility, terminal orchestration, workflow interruption, collaboration sessions, replay, and voice-command foundations.

This layer is intentionally local-first and approval-aware. It does not turn Aegis into a remote shell without guardrails. Core records every launched process, stdout/stderr chunk, exit code, timeout, approval decision, session sync, and voice command under the workspace `.aegis` folder.

## Core Authority

Core owns the canonical implementation in:

```text
aegis-core/aegis_core/runtime_interaction.py
```

Workspace state is persisted as:

```text
.aegis/runtime-interaction.json
```

The Website backend exposes compatibility/gateway routes under `/api/runtime-interaction/*`. Desktop reads the same Core runtime status through its Core client. Future VS Code and Visual Studio panels should consume the same `/v1/runtime/*` contracts instead of inventing local terminal/job state.

## Runtime Capabilities

Core now supports:

- live workflow and terminal event streams
- terminal jobs associated with workflows and tasks
- stdout/stderr capture and replay
- exit-code and timeout tracking
- process cancellation and retry
- collaboration sessions with participants, spectators, and approval delegates
- voice command routing from client-submitted transcripts
- execution replay for workflow timelines, terminal output, repair chains, approval history, and sessions

## Terminal Safety

Terminal orchestration is conservative by design:

- commands run with `shell=false`
- command cwd must stay inside the workspace
- safe validation commands can run without extra approval
- commands outside the validation allow-list require explicit approval
- dangerous command tokens are blocked even with approval
- timeouts are required and capped
- stdout/stderr is scrubbed before persistence
- running jobs can be terminated through Core
- Website fallback never executes terminal commands if Core is offline

Blocked tokens include destructive or high-risk commands such as `Remove-Item`, `rm -rf`, `format`, `shutdown`, `Invoke-Expression`, `diskpart`, `curl`, and `wget`.

## Core Endpoints

```text
GET  /v1/runtime/terminals
GET  /v1/runtime/jobs
POST /v1/runtime/jobs
GET  /v1/runtime/jobs/{job_id}
POST /v1/runtime/jobs/{job_id}/cancel
POST /v1/runtime/jobs/{job_id}/retry
GET  /v1/runtime/streams
GET  /v1/runtime/processes
GET  /v1/runtime/sessions
POST /v1/runtime/sessions
POST /v1/runtime/sessions/{session_id}/sync
GET  /v1/runtime/voice
POST /v1/runtime/voice/command
GET  /v1/runtime/replay
```

`GET /v1/runtime/streams` returns server-sent events by default. Clients can pass `as_sse=false` to fetch a bounded JSON event list for polling or tests.

## Website Gateway

The Website backend exposes:

```text
GET  /api/runtime-interaction
GET  /api/runtime-interaction/jobs
POST /api/runtime-interaction/jobs
GET  /api/runtime-interaction/jobs/{job_id}
POST /api/runtime-interaction/jobs/{job_id}/cancel
POST /api/runtime-interaction/jobs/{job_id}/retry
GET  /api/runtime-interaction/streams
GET  /api/runtime-interaction/events
GET  /api/runtime-interaction/sessions
POST /api/runtime-interaction/sessions
POST /api/runtime-interaction/sessions/{session_id}/sync
GET  /api/runtime-interaction/voice
POST /api/runtime-interaction/voice/command
GET  /api/runtime-interaction/replay
```

The Website UI Runtime surface now shows live terminals, terminal jobs, event stream activity, collaboration sessions, and voice foundation status. It uses the Website gateway so existing auth/UI assumptions stay intact while Core remains the runtime authority.

## Desktop Visibility

The native Desktop app registers `runtime-interaction` as a Core capability and reads the live-runtime snapshot during runtime probing. The Runtime Status panel now reports terminal counts, active jobs, active processes, the latest runtime event, voice runtime status, and shared session count.

Desktop does not yet launch arbitrary terminal jobs from the UI. That is deliberate; native controls should be added only with a full approval and risk-review UX.

## Voice Foundations

Core does not record audio. Clients own push-to-talk capture and can submit transcripts to `/v1/runtime/voice/command`.

The current contract routes transcript intents such as:

- summarize workflow
- pause workflow
- resume workflow
- cancel workflow
- run validation
- explain failure

Speech-to-text and text-to-speech providers remain optional and local-first. Cloud voice providers must require explicit provider approval before use.

## Collaboration Sessions

Sessions are local coordination records, not SaaS multi-tenancy. They are intended for shared workflow supervision, spectators, approval delegation, and collaborative roadmap review inside an explicitly connected environment.

The first implementation stores:

- workflow id
- owner client id
- participants
- spectators
- approval delegates
- session status
- last sync time

## Replay

Replay combines Core runtime-interaction events with workflow events stored under `.aegis`. It is meant to support future timeline views for:

- workflow progress
- validation logs
- terminal output
- repair chains
- approvals
- collaboration sessions

## Remaining Limitations

- Streaming is SSE only; WebSocket transport can be layered later if clients need bidirectional low-latency interaction.
- Process isolation is subprocess-based. Container/sandbox execution is represented as a future extension point.
- Collaboration sessions are local records and do not include full multi-user identity, permissions, or network transport yet.
- Voice support is a command-routing foundation, not an audio pipeline.
- Desktop visibility is read-only for this milestone.
