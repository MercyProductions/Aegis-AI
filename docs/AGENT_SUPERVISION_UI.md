# Agent Supervision UI

Aegis Core is the runtime authority for agent-owned workflows. The Website and Desktop app now expose supervision surfaces that read Core workflow state instead of recreating orchestration locally.

## Website

The Website frontend uses `/api/agent-supervision` compatibility routes from the Website backend. Those routes delegate to Core `/v1` contracts when Core is reachable and return safe degraded snapshots when it is not.

Primary backend routes:

- `GET /api/agent-supervision`
- `GET /api/agent-supervision/workflows/{workflow_id}/agents`
- `POST /api/agent-supervision/workflows/{workflow_id}/step`
- `POST /api/agent-supervision/workflows/{workflow_id}/agents/delegate`
- `GET /api/agent-supervision/workflows/{workflow_id}/events`

The Agents page now includes an Agent Activity Center with:

- Core connection and fallback visibility
- active workflow and current task
- agent cards
- workflow timeline
- approval queue controls
- pause, resume, cancel, request revision, and rollback entry points
- diff/risk review using generated changes and Core task metadata
- quality gate status with score breakdown, blockers, warnings, benchmark status, and report history
- filters for workflow, agent, status, risk, file, and validation state
- Core event streaming through Server-Sent Events with polling fallback

## Desktop

The native Desktop client now calls Core directly for supervision data:

- `CoreApiClient::GetAgentSupervision`
- `CoreApiClient::StepWorkflow`
- `AegisClient::GetAgentSupervision`
- `AegisClient::StepCoreWorkflow`

The right rail includes an Agent Supervision panel showing active workflow status, current task, approvals, validation status, rollback availability, recent timeline events, and active agents. It also includes quality gate status, confidence/validation/risk scores, blockers, warnings, and latest benchmark/report evidence. Controls delegate workflow actions to Core while preserving Website fallback behavior elsewhere in the app.

## Safety Model

The UI always distinguishes proposed work from applied work. Apply and rollback remain checkpoint-based. Approval controls submit explicit Core workflow actions rather than directly mutating files. Rollback opens the existing checkpoint browser so the user can inspect and choose a restore point.

## Remaining Gaps

- The Website panel consumes Core event streams but still refreshes full snapshots after events.
- Desktop uses manual refresh rather than a persistent SSE/WebSocket event stream.
- Approval controls are generic Core workflow actions; future UI should render typed approval payloads as Core contracts become richer.
- The diff panel can only show detailed generated diffs when the active session already has proposed file changes.
