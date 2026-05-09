# Client Responsibilities

Last updated: 2026-05-09

## Purpose

This document defines what each Aegis ChatBot / Auralith OS client is responsible for owning locally and what should be delegated to Website `/api` or Aegis Core `/v1`.

## Desktop App

Owns:

- Native Win32/DX11/Dear ImGui windowing, rendering, style, keyboard/mouse behavior, local desktop preferences, local conversation persistence, and UI layout.
- Desktop-specific startup behavior for the Website backend on 8787.
- User-facing chat, workspace, model, change, validation, checkpoint, memory, telemetry, project-builder, and Creative Studio panels.
- Graceful degradation when either Website `/api` or Core `/v1` is unavailable.

Delegates to Website `/api`:

- Chat and streaming chat.
- File list/read/slice, generated changes, apply, checkpoint restore, validation, verification.
- Model registry/manager/benchmarks, routing preview, telemetry, memory CRUD, project builder, Creative Studio, tasks, approval settings.

Delegates to Core `/v1`:

- Shared client registration.
- Ecosystem dashboard, including shared clients, tasks, model status, diagnostics, roadmap, validation summary, and branding.

Do not add:

- A separate Desktop-only workspace scanner.
- A separate Desktop-only model inventory.
- A separate Desktop-only task graph.

## Website UI

Owns:

- Browser UI, auth UI, panels, navigation, client-side state, optimistic loading, and interaction design.
- Rich Auralith OS surfaces that are backed by Website `/api`.

Delegates to Website `/api`:

- All current production web functionality.
- Read-only shared runtime status through `/api/core-runtime`, which preserves Core `/v1` envelopes for health, models, settings, memory, diagnostics, and dashboard.

Future Core delegation candidates:

- Shared client registration as `auralith-website`.
- Shared dashboard display from `/v1/ecosystem/dashboard`.
- Shared settings read/write where settings should apply across Desktop, Website, VS Code, and Visual Studio.

Do not add:

- A separate browser-only definition of shared tasks, shared clients, or shared Core settings.

## VS Code Extension

Owns:

- VS Code commands, status bar, webview panel, active file/selection context, diagnostics capture, extension workspace state, proposal preview, approved apply, backups, rollback, and local extension logs.
- IDE-specific safety checks around selected files and VS Code workspace folders.

Delegates to Core `/v1`:

- Health check inclusion.
- Client registration.
- Shared task creation during Agent Mode.
- Shared task status updates while planning, waiting for approval, completing, or canceling.

Should migrate next:

- Workspace scan and roadmap to `/v1/workspaces/scan` and `/v1/workspaces/roadmap` when the extension can preserve its VS Code-specific context enrichment.
- Memory and diagnostics reads to `/v1/memory` and `/v1/diagnostics`.
- Validation summary/run to `/v1/validation` when command allowlist behavior matches the extension's safety model.

Do not add:

- Another incompatible task status vocabulary.
- Another shared dashboard file format.

## Visual Studio Extension

Owns:

- Visual Studio package/tool window lifecycle, solution/project detection, active document/selection context, Error List/build output integration, proposed changes, approval, rollback, and VS options.
- Visual Studio-specific solution intelligence and `.sln`/`.slnx` plus `.csproj`/`.fsproj`/`.vbproj`/`.vcxproj` context.

Delegates to Core `/v1`:

- Health check inclusion.
- Client registration.

Should migrate next:

- Shared tasks for build/error workflows.
- Shared diagnostics for solution health.
- Shared roadmap and validation where Core can represent Visual Studio build context without losing IDE-specific signals.

Do not add:

- A parallel shared-client registry.
- A Visual Studio-only cross-client dashboard.

## Aegis Core

Owns:

- Shared stable `/v1` API contracts.
- Workspace-local `.aegis` config, memory summaries, diagnostics, scan cache, roadmap, validation logs, clients, tasks, dashboard, branding, and plan-only continue/repair outputs.
- Ollama health and model inventory for shared local runtime visibility.

Does not own yet:

- Rich Website agent execution.
- Full project builder/scaffolding.
- Website auth.
- Website telemetry/adaptive/productization/autonomous/Creative Studio systems.

## Website Backend

Owns:

- The mature `/api` application runtime.
- Rich agent execution, local/provider routing, repair loops, model registry, model benchmarks, app task graph, app telemetry, productization, ecosystem, autonomous engineering, and Creative Studio.
- The thin Website-to-Core bridge at `/api/core-runtime`; this bridge must remain optional and degraded-mode friendly.

Should not own long term:

- Shared client registry.
- Shared dashboard aggregation.
- Shared task status needed by all clients.
- Core settings that must be consistent across clients.
