# Governance, Policy, And Compliance Runtime

The Governance Policy Runtime gives Aegis Core one local-first place to evaluate execution boundaries, approval requirements, deployment restrictions, plugin permission risk, runtime node trust, provider privacy, memory access, and audit/compliance exports.

This is workflow governance, not generic enterprise bloat. Policies are deterministic records, evaluations are inspectable, and all state remains under the workspace `.aegis` folder by default.

## State And Audit

Core stores governance state in:

- `.aegis/governance-policies.json`
- `.aegis/governance-audit.jsonl`
- `.aegis/governance-export-*.json`

The runtime also reads existing local audit sources when building compliance exports:

- security audit
- collaboration approvals
- distributed runtime audit
- deployment audit
- plugin observability
- memory audit

## Policy Scopes

Supported scopes:

- `global`
- `workspace`
- `project`
- `runtime_node`
- `workflow_type`
- `deployment`

Policies target practical execution areas:

- workflow execution
- deployments
- plugin permissions
- runtime node access
- provider usage
- memory access
- validation requirements
- approval requirements
- command execution
- file access

## Default Boundaries

Initial default policies include:

- dangerous command blocking
- unrestricted shell approval
- sensitive path blocking
- production deployment signoff
- validation before apply/completion
- high-risk plugin permission approval
- remote runtime trust isolation
- cloud provider privacy approval
- sensitive memory access approval
- high-risk workflow escalation

Policy outcomes are `allowed`, `needs_approval`, or `blocked`. Blocking policies stop execution. Approval policies produce role requirements and reasons that clients can render as approval gates.

## Autopilot Integration

Autopilot evaluates governance when a run starts and before risky actions such as terminal execution, checkpoint/apply-like actions, rollback, and completion.

When policy requires review, Autopilot:

- pauses in `waiting_approval`
- records `policy_governance` in the approval queue
- stores policy violations on the run
- appends a decision-log entry
- emits an `autopilot_policy_paused` replay event

Approval does not bypass blocked command rules. Dangerous command tokens remain blocked; approval only satisfies policies marked as approval-gated.

## Runtime Trust Levels

The governance runtime exposes trust labels that clients can use for distributed runtime UI:

- `trusted`
- `restricted`
- `isolated_validation`
- `deployment_authorized`
- `experimental`

Distributed runtime scheduling still owns actual workload assignment. Governance provides shared policy evaluation and visibility over why a node or workload should be blocked or escalated.

## Plugin Governance

Plugins are checked by permission scope. High-risk scopes include:

- `filesystem_write`
- `network_access`
- `process_execution`
- `validation_execution`
- `provider_credentials`

Plugins requesting high-risk permissions require approval and trusted metadata before enablement or execution. Arbitrary plugin code remains blocked unless an isolated execution path exists.

## APIs

```text
GET  /v1/governance
GET  /v1/governance/policies
POST /v1/governance/policies
POST /v1/governance/evaluate
GET  /v1/governance/audit
POST /v1/governance/compliance/export
```

Website mirrors the dashboard/evaluation/export operations under `/api/governance/*` as a Core gateway. Mutating operations fail closed when Core is offline.

## Client Responsibilities

Website and Desktop should show:

- policy status
- recent violations
- approval requirements
- deployment restrictions
- runtime trust warnings
- plugin permission risk
- audit/compliance export availability

IDE clients should call policy evaluation before risky commands, provider calls, plugin tool execution, apply-like actions, and deployment steps.

## Current Limits

- Policies are local JSON records, not centralized organization SaaS policy.
- Policy evaluation is deterministic and rule-based; there is no hidden model judgment.
- Compliance exports are local files; sharing them is a user/client action.
- The runtime provides governance decisions, but source-control branch protection and external CI policy remain outside Core.
