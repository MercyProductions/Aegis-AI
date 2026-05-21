# Collaborative Engineering Runtime

The Collaborative Engineering Runtime lets multiple users, clients, workflows, repositories, and runtime nodes coordinate through Aegis Core while keeping the local workspace as the authority.

This is not a generic social layer. It is engineering governance for shared work: ownership, role-scoped visibility, approval chains, roadmap assignment, deployment/rollback authorization, runtime visibility, and auditability.

## Core Concepts

- Shared workflows track owner, assignee, participants, reviewers, repository, roadmap links, approval status, and ownership history.
- Roles define what a participant can approve or see: `owner`, `maintainer`, `reviewer`, `observer`, `deployment_approver`, and `validation_reviewer`.
- Approval chains can be staged for workflow review, validation signoff, deployment approval, runtime delegation, repair approval, and rollback authorization.
- Roadmap items can be assigned to owners/assignees, linked to collaborative workflows, milestones, blockers, and approval gates.
- Repository records connect multiple repositories to runtime nodes and validation infrastructure.
- Audit logs record who created workflows, delegated work, approved or rejected gates, requested rollback, registered repositories, and assigned roadmap items.

## Local-First Governance

All collaboration state is stored under the workspace `.aegis` folder:

- `.aegis/collaboration-runtime.json`
- `.aegis/collaboration-audit.jsonl`

Core remains the local authority for approvals, checkpoint expectations, rollback readiness, deployment governance, and runtime fallback. No cloud sync is enabled by default.

The runtime is intentionally identity-light for now. User IDs, roles, and client IDs are explicit local records, not SaaS accounts. External auth, invitation flows, notification delivery, and organization policy can be layered on later without changing the Core workflow and approval records.

## Approval Model

Approval gates include:

- `target_type`
- `target_id`
- `approval_type`
- `stage`
- `required_roles`
- `required_count`
- `risk_level`
- decision history

Approvals complete when either all required roles have signed off or `required_count` unique approvers have approved. Any rejection marks the gate rejected and blocks the linked workflow.

Deployment and rollback approvals are intentionally stricter. They require owner, maintainer, or deployment approver authority.

## Workflow Ownership And Delegation

Shared workflows carry:

- `owner_id` and `owner_role`
- `assignee_id` and optional `assignee_role`
- `participants` and `reviewers`
- `repository_id`
- linked roadmap item IDs
- `ownership_history`

Owners and maintainers can delegate, pause, resume, cancel, complete, block, and request rollback through `POST /v1/collaboration/workflows/{workflow_id}/action`. Every mutation updates ownership history and writes an audit event.

Autopilot and task-graph runners should treat a collaborative workflow as a governance wrapper. Execution can continue only when required approvals have passed, and risky actions should re-enter `waiting_approval` rather than silently continuing.

## Roadmaps, Repositories, And Runtime Coordination

Roadmap items support milestone, owner, assignee, blocked reason, validation state, deployment state, and approval-required metadata. They can be linked to collaborative workflows so roadmap execution, checkpointing, validation, and deployment signoff remain traceable.

Repository records allow one workspace dashboard to coordinate multiple repositories and runtime resources. Each record can list runtime nodes and validation infrastructure. Distributed execution remains governed by the distributed runtime trust model; collaboration only makes ownership and visibility explicit.

## Privacy And Visibility

The default privacy controls are:

- local-first authority
- workspace isolation
- private memory scopes
- restricted deployment visibility
- role-scoped observability
- cloud sync disabled

Observer roles receive redacted private/restricted workflow metadata and restricted deployment details. Clients should still enforce their own workspace permission checks before opening files, launching commands, or showing sensitive provider/config material.

## Autopilot Integration

Autopilot can receive collaboration metadata through `metadata.collaboration` or `metadata.collaboration_workflow_id`. When a matching collaborative workflow has pending approvals, Autopilot adds a `collaboration_approval` gate and pauses until role-eligible reviewers approve through Core.

Clients should surface:

- active collaborative workflow
- pending approval chain
- required roles
- workflow owner and assignee
- runtime/deployment visibility
- audit history

## APIs

```text
GET  /v1/collaboration
GET  /v1/collaboration/roles
POST /v1/collaboration/members
POST /v1/collaboration/repositories
POST /v1/collaboration/workflows
POST /v1/collaboration/workflows/{workflow_id}/action
POST /v1/collaboration/approvals
POST /v1/collaboration/approvals/{approval_id}/decision
POST /v1/collaboration/roadmap/items
GET  /v1/collaboration/audit
```

Website and Desktop surfaces should treat this as a command-center signal: pending approvals, shared workflows, roadmap ownership, repository/runtime coordination, and governance warnings should be visible without hiding the normal local approval and rollback controls.

Website exposes compatibility gateway routes under `/api/collaboration/*` for dashboard, member registration, repository registration, workflow creation, workflow actions, approval creation/decision, and roadmap assignment. These routes delegate to Core and return service-unavailable errors for mutating operations when Core is offline, because Website should not become a second collaboration authority.

Desktop currently consumes the Core dashboard as supervision metadata. Native controls should continue to use the same Core route family for approval queues, delegation, rollback authorization, and shared roadmap ownership.

## Current Limits

- This is local-first coordination state, not multi-tenant SaaS identity.
- Reviewer notifications are represented as inspectable metadata; push delivery is still a client responsibility.
- Runtime node cooperation is visible through distributed runtime summaries; remote execution remains gated by existing distributed-runtime trust rules.
- Conflict resolution is conservative: Core records ownership and approvals, but source-control merges and branch policy remain the responsibility of Git and the client UI.
