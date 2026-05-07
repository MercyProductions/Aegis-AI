# AI Operating Environment

The AI Operating Environment is the permission-scoped control plane for expanding Aegis beyond a coding assistant without weakening the product's safety model.

It does not grant uncontrolled desktop automation. It registers OS-level, creative, research, workflow, learning, security, simulation, memory, and distributed runtime capabilities in one observable map, then keeps risky actions blocked or approval-gated until a trusted adapter exists.

## Backend

`website/backend/aegis_ai/operating_environment.py` owns the registry.

It emits:

- `OperatingEnvironmentSnapshot`
- `OperatingEnvironmentCapability`
- `OperatingEnvironmentAdapter`
- `OperatingSystemSignal`
- `OperatingEnvironmentActionResponse`

The API endpoints are:

- `GET /api/operating-environment?workspace_root=...`
- `POST /api/operating-environment/actions/preview`

The preview endpoint never executes desktop automation. It answers whether an action is previewable, blocked, or needs approval, and returns the permission scopes and safety notes that would apply.

## Capability Families

The registry covers:

- desktop control
- live screen understanding
- AI overlay
- automation studio
- AI IDE/editor engine
- system intelligence
- learning/training
- research
- story/world engine
- game/simulation engine
- environment builder
- security analysis workspace
- personal memory
- runtime personality modes
- Creative Studio
- distributed runtime
- knowledge graph

Each capability declares status, permission scope, approval requirements, sandbox requirements, rollback support, task tracking, adapters, endpoints, UI surfaces, safety notes, and next steps.

## Adapters

Adapters are explicit and named. Ready adapters include:

- read-only system probe
- workspace file adapter
- local creative media adapter
- distributed worker adapter

Blocked or planned adapters include:

- desktop automation adapter
- screen capture and OCR adapter
- network research adapter
- security lab adapter

Future executable adapters must be permission-scoped, approval-gated, task-tracked, and audited.

## System Signals

The first implementation exposes read-only signals:

- OS version
- host architecture
- logical CPU count
- Python runtime
- workspace disk availability

These signals do not mutate files, processes, windows, clipboard, keyboard/mouse state, or system settings.

## Safety Defaults

Blocked by default:

- keyboard/mouse automation
- app launching
- window and monitor layout mutation
- clipboard mutation
- screen capture
- OCR over screen content
- dependency installs
- environment variable changes
- security tracing
- process/network inspection

Preview-first by default:

- action planning
- permission explanation
- adapter requirements
- safety notes

Read-only by default:

- coarse host/runtime/storage signals

## Frontend

The Runtime surface shows:

- operating-environment capability readiness
- gated capability count
- adapter status
- read-only system signals

This intentionally lives inside Runtime instead of becoming another dashboard. The product rule is: expose control and trust first, then add action buttons only when an adapter is real, safe, and useful.

## Tests

Backend coverage lives in:

`website/backend/tests/test_operating_environment.py`

Frontend API coverage lives in:

`website/frontend/src/api.test.ts`
