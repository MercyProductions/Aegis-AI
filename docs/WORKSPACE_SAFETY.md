# Workspace Safety

Workspace safety is layered. Aegis rejects unsafe paths as early as possible and repeats checks at the write boundary.

## Safety Layers

- `FileChange` schema validation rejects absolute paths, parent-directory escapes, empty paths, and paths outside the workspace contract.
- `WorkspaceManager.resolve_workspace` resolves the active workspace against configured allowed roots.
- `WorkspaceManager._ensure_within_allowed_roots` prevents workspace roots from drifting outside configured roots unless explicit workspace paths are enabled and considered safe.
- `WorkspaceManager._safe_path` resolves every file operation against the workspace root and rejects paths that escape after normalization, ignored dependency/runtime folders, hidden parent folders, and secret-like filenames.
- Workspace scans and context assembly skip secret-like filenames such as `.env`, token/password files, private keys, and key/certificate files before model context is built.
- `WorkspaceManager.apply_changes` catches unsafe runtime changes, records warnings, and skips writes.
- `WorkspaceManager._create_checkpoint` runs the same safety checks before creating backup entries.

## Checkpoints

Before applying file changes, Aegis creates `.aegis/checkpoints/<id>/manifest.json`. Existing files are copied under `files/`; new files are tracked as missing so rollback can delete them. `restore_checkpoint` uses the manifest and `_safe_path` to restore or delete each tracked path.

## Autonomous Operations Boundary

Workspace Intelligence is read-first. Watcher scans, health checks, git summaries, recommendation generation, and scheduled intelligence job records may persist observations in SQLite, but they do not modify workspace files.

The `fix now` path for a recommendation creates a queued task and records a `recommendation.fix_requested` timeline event. Actual file edits still have to flow through the normal task, approval, `FileChange`, `WorkspaceManager.apply_changes`, checkpoint, validation, repair, and rollback path. Command-backed scheduled jobs are skipped unless the request explicitly allows command execution.

## Distributed Runtime Boundary

Distributed execution is opt-in and audit-first. The default local worker can run safe queue jobs, but command-backed validation/build jobs require `allow_commands=true` at dispatch time and still use `CommandRunner`, the allowlist, approval settings, and the selected sandbox profile. LAN and remote workers are ignored unless the dispatch request sets `allow_remote=true` and the worker registration is trusted.

The Website `CommandRunner` treats the command allowlist as a tool-name contract, not permission to run any executable with the same basename. Normal tools should be launched through `PATH` with bare names such as `npm test` or `python -m pytest`; the only explicit path wrappers accepted are local `./gradlew` and `./mvnw` project wrappers.

Remote sync exports store manifests and payload hashes in SQLite; they do not copy files to a remote machine by themselves. Distributed repair jobs created after validation failure are timeline and queue records only. They do not write project files directly and must hand off to the normal task runtime for approved code changes, checkpoints, validation, and rollback.

## Plugin Boundary

The Plugin / Extension SDK is permission-scoped. Registering a plugin manifest persists metadata only; it does not execute plugin code. High-risk permissions such as workspace writes, command execution, network access, model access, and provider registration require an isolated, sandbox, or restricted sandbox profile, and enabled high-risk plugins must be explicitly trusted. Enterprise policy can require plugin signatures before trust.

Plugin-driven file changes must still use the normal workspace write path: approval, `FileChange`, `WorkspaceManager.apply_changes`, checkpoint creation, validation, repair, and rollback.

## Ecosystem Boundary

Ecosystem packages are also permission-scoped metadata until a trusted runtime component consumes them. Agent packs, validator packs, scaffold packs, workflow packs, routing profiles, telemetry analyzers, and workspace intelligence packs declare sandbox permissions, update channels, trust levels, checksums, and signing metadata.

Enabled high-risk ecosystem packages require isolated sandbox permissions and trusted, organization-approved, or signed status. Running a reusable workflow creates normal task graph records and timeline events; workflow execution does not silently edit files or bypass approval, checkpoint, validation, repair, or rollback.

## Controlled Autonomous Engineering Boundary

Autonomous objectives are supervised orchestration records, not direct write permissions. The objective engine can create phases, simulations, approval gates, linked tasks, agent assignments, verification signals, refactor plans, explainability entries, and analytics. It cannot silently modify project files.

Risky objective work is paused behind approval gates for large file changes, dependency changes, architecture changes, destructive actions, and production-impacting actions. Default safety limits require rollback, cap iterations, cap repair attempts, cap projected file and dependency changes, and protect configured file zones. When an objective needs real code changes, it must create or link a task and use the normal approval, `FileChange`, checkpoint, validation, repair, and rollback path.

## Creative Studio Boundary

Creative Studio writes only inside the local media library at `workspace/creative_media`. Asset file reads are served only when the requested path resolves inside that library. Local image, motion, beat, and voice drafts are safe draft-generation jobs and do not modify source code.

Paid media providers, large GPU or long-video jobs, copyright-sensitive style prompts, and voice cloning require explicit approval flags. Provider adapters are metadata seams until a provider implementation is installed and approved.

## Unified Runtime Boundary

The unified runtime map is read-only metadata. It summarizes pillars, modalities, tools, workflows, memory status, safety notes, and active counts. It does not execute tools, change files, dispatch workers, run providers, or alter permissions.

## Operating Environment Boundary

The AI Operating Environment is also read-first. It registers desktop control, live screen understanding, overlay, automation, IDE, system intelligence, learning, research, story/simulation, environment builder, security analysis, personal memory, personality, creative, distributed runtime, and knowledge graph capabilities as metadata with explicit permission scopes.

`/api/operating-environment` returns capability and adapter state plus read-only host signals. `/api/operating-environment/actions/preview` returns whether an action is previewable, blocked, or approval-gated. It does not execute desktop actions. App launch, window layout changes, keyboard/mouse automation, clipboard mutation, screen capture, OCR, process inspection, network inspection, dependency installation, environment mutation, and security tracing stay blocked until a trusted adapter and explicit approval path exist.

## Unified Context Boundary

The Unified Context Engine is read-first. It normalizes tasks, task events, Project Intelligence, memory, fix memory, Creative Studio assets, Workspace Intelligence, Operating Environment state, and distributed runtime jobs into searchable records and relationships.

`/api/global-command/preview` routes a command and explains the required task, approval, rollback, validation, and owning endpoint. `/api/global-command/submit` may create a tracked task, but it does not execute the underlying action or bypass the owning subsystem. File edits, creative generation, automation, research, desktop/system work, validation, repair, and rollback still flow through their existing safety contracts.

## Presence And Continuity Boundary

Presence and Continuity is also read-first. It derives ambient presence, operating memory timeline, forecasts, cognitive workflow-awareness, self-diagnostics, hardware routing notes, persistent workspace state, skill pack metadata, universal data source readiness, platform SDK status, digital twin state, research lab evaluations, and memory distillation from Unified Context.

`/api/continuity` and `/api/continuity/timeline/search` do not execute work. They do not install skill packs, prune memory, run evaluations, change routing, control hardware, inspect processes, control the desktop, run commands, or mutate files. Any executable work must be routed through the owning task/tool endpoint.

## Platform Discipline Boundary

Platform Discipline is read-only governance metadata. It classifies stewardship posture, domains, roadmap items, stability tiers, feedback loops, design standards, behavior principles, performance budgets, security foundations, architecture layers, and maintainability practices.

`/api/platform-discipline` does not execute work, change task state, enable features, dispatch workers, update plugins, alter memory, change model routing, or write files. It can recommend focus changes, but executable work still has to flow through the owning task/tool endpoint with approvals, checkpoints, validation, repair, rollback, logging, and tests.

The feature admission gate defaults to `reject_when_unclear`. A recommendation, plugin, agent, workflow, UI surface, provider, desktop adapter, or worker capability does not become product work unless it passes the admission questions and avoids the hard no rules.

The stewardship posture also does not execute work. It is a standing constraint: preserve trust, performance, clarity, maintainability, and cohesion before expanding scope.

## Compatibility Rules

- Do not write outside the workspace root.
- Do not scan, read, or write secret-like files through generated workspace context or `FileChange` proposals.
- Do not bypass `FileChange` or `WorkspaceManager.apply_changes` for agent-generated edits.
- Do not let autonomous watcher, recommendation, or scheduled-job code write project files directly.
- Do not let autonomous objectives write project files directly or skip approval gates for risky work.
- Do not let Creative Studio write outside `workspace/creative_media` or serve asset files outside that library.
- Do not dispatch paid, long-running, copyright-sensitive, or voice-cloning creative providers without explicit approval.
- Do not let operating-environment previews perform actual desktop, screen, process, network, install, environment, or security actions.
- Do not enable desktop/screen/security/environment adapters without explicit permission scopes, approval gates, sandboxing where possible, task tracking, and audit logs.
- Do not let unified context or global command routing execute subsystem work directly; route into the owning task/tool endpoint.
- Do not let global command task creation bypass approvals, checkpoints, validation, repair, rollback, provider restrictions, or adapter trust.
- Do not let presence/continuity execute forecasts, prune memory, install skill packs, enable SDK extensions, or change hardware/model routing directly.
- Do not infer or simulate emotions from cognitive-awareness signals; adapt only from observable workflow patterns.
- Do not let platform discipline recommendations enable capabilities, bypass stability tiers, or promote experimental systems without tests and documented safety gates.
- Do not treat stewardship text as permission to mutate files, run commands, enable plugins, or change task state.
- Do not add unclear, duplicate, or speculative features when the admission gate says no.
- Do not let distributed queue, remote worker assignment, or sync manifest code silently modify project files.
- Do not dispatch LAN/remote workers without trusted registration and explicit remote permission.
- Do not run command-backed distributed jobs without explicit command permission.
- Do not execute plugin lifecycle hooks or plugin file changes outside declared permissions and sandbox policy.
- Do not enable high-risk ecosystem packages without isolated sandbox permissions and trusted/signed review.
- Do not let reusable workflows modify files outside the task, approval, checkpoint, validation, and rollback path.
- Do not change checkpoint manifest shape without a migration and endpoint documentation.
- Do not delete user changes outside the explicit checkpoint restore path.
- Preserve warnings for skipped unsafe changes; callers depend on them for UI feedback.

## Regression Coverage

`website/backend/tests/test_golden_workflows.py` locks both schema-level rejection and runtime write-boundary rejection. `test_workspace_and_storage.py` covers checkpoint creation, restore behavior, skipped writes, mixed slash normalization, secret-like scan/apply exclusions, safe dotfile handling, and append/update/delete edge cases. `test_workspace_operations.py` covers recommendation fix permission gating, skipped command-backed scheduled jobs, and checkpoint rollback after an approved simulated autonomous task write. `test_distributed_runtime.py` covers trusted worker registration, remote dispatch permission, command gating, queue retry/cancel, sync integrity, routing privacy, and validation failure repair queueing. `test_autonomous_engineering.py` covers dry-run objective creation, approval gate persistence, capped iteration, verification signal recording, pause/reject behavior, API lifecycle, and snapshot analytics. `test_creative_studio.py` covers local asset generation, beat/MIDI/voice outputs, asset-library/export behavior, provider approval gates, and Creative Studio API lifecycle. `test_operating_environment.py` covers capability registration, blocked desktop-control preview behavior, and read-only operating-environment API responses. `test_unified_context.py` covers cross-module context records, relationships, unified search, global command routing, and task creation through the command submit endpoint. `test_continuity.py` covers ambient presence, timeline reconstruction/search, forecasting, diagnostics, skill pack metadata, universal data source readiness, digital twin state, and continuity API responses. `test_platform_discipline.py` covers the primary/secondary/experimental domain choices, stability tiers, performance budgets, security foundations, deprecated paths, and read-only API response.
