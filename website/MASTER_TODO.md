# Auralith OS Master TODO

This is the production roadmap for Auralith OS: a private, extensible local-first AI operating environment with multi-model routing, safe tool execution, memory, project understanding, creative workflows, orchestration, and a premium desktop/web experience.

## Execution Rules

- Do not treat this as a single feature list. Treat it as a system build plan.
- Every task must produce one of: source code, schema, API contract, security policy, migration, UI surface, test plan, or operations runbook.
- Prefer modular services and typed contracts over hidden state in large files.
- Never store provider secrets in model registry notes, desktop config, transcripts, logs, or frontend state.
- Keep local/private model routes available even when cloud providers are configured.

## Current Pass Status

- Completed: provider registry records now carry first-class model identity, aliases, secret env name, cost tier, context window, rate limit, and per-million-token cost fields.
- Completed: provider adapter configs now preserve registry metadata and resolve secrets from explicit env names before falling back to provider heuristics.
- Completed: model execution planning now resolves planned attempts to registry provider model names instead of relying only on string hints or the global active model.
- Completed: desktop provider editor can author model names, aliases, secret env names, cost tiers, context windows, RPM limits, and input/output cost hints.
- Completed: `AEGIS_ROUTER_EXECUTION_ENABLED` exists as an explicit disabled-by-default setting so fallback execution can be integrated deliberately in a later pass.
- Completed: route-specific context budget profiles now shape selected files, memory, history, snippet budgets, and response-token reserves per task intent.
- Completed: model attempt planning now includes deterministic input/output token estimates, cost estimates when registry pricing exists, and context-window utilization metadata.
- Completed: context budget and model attempt planning telemetry now persist to SQLite and are readable through `/api/telemetry`.
- Completed: native desktop responses now parse task plans, context budgets, model attempts, and render a compact route timeline panel when metadata is available.
- Completed: model registry snapshots now backfill older provider records to version 2 with explicit model identity, aliases, secret env names, cost, rate, and context metadata.
- Completed: non-streaming model attempt execution is wired behind `AEGIS_ROUTER_EXECUTION_ENABLED` and can replace planned telemetry with live attempt status when enabled.
- Completed: native desktop now consumes `/api/telemetry` through a Planning History modal with recent context budgets, model attempts, privacy labels, token pressure, and estimated spend.
- Completed: provider-aware token estimator hooks now adjust planning-time input tokens by provider/model family and preserve estimator provenance in model-attempt metadata.
- Completed: `/api/telemetry/route-quality` now summarizes route reliability, fallback rate, context pressure, estimated spend, provider health, role performance, and recommendations.
- Completed: native desktop Planning History now renders route-quality rollups, provider reliability, role performance, fallback rate, estimator provenance, and routing recommendations.
- Completed: `/api/telemetry/fallback-inspector` now links recent task plans, route candidates, fallback roles, context budgets, model attempts, estimator provenance, registry resolution, and per-task recommendations.
- Completed: native desktop Planning History now consumes the fallback inspector with task summaries, candidate tables, fallback roles, registry resolution, attempt status, cost, and estimator provenance.
- Completed: planner route candidates now carry stable candidate IDs that persist into model-attempt metadata, and fallback inspection matches by ID before using legacy heuristics.
- Completed: native desktop Planning History now upgrades fallback inspection into a selectable task drilldown with all candidates, all attempts, recommendations, context metadata, candidate IDs, and attempt metadata.
- Completed: user feedback now has typed telemetry, a dedicated SQLite table, `/api/feedback`, `/api/telemetry/feedback`, route-quality scoring fields, and native desktop action events for feedback, apply, and rollback outcomes.
- Completed: feedback telemetry now emits provider, model, route-role, candidate, task-intent, target, and action attribution rollups, and native Planning History renders a compact feedback-outcomes table.
- Completed: feedback privacy controls now support shared-workspace no-excerpt mode, secret/email redaction, excerpt length limits, optional content hashing, config persistence, and native settings controls.
- Completed: feedback telemetry now includes daily trend buckets and recent event drilldowns in route-quality payloads, with native Planning History tables for trends and recent feedback events.
- Completed: web Observability now surfaces route-quality, fallback-inspector, and feedback telemetry with typed API helpers and compact dashboard panels.
- Completed: materialized telemetry snapshots now cache route-quality, fallback-inspector, and feedback payloads with freshness metadata and web refresh/read helpers.
- Completed: route-policy diff proposals now turn reliability, fallback, cost, context, and feedback telemetry into reviewable provider and role recommendations before any routing update.
- Completed: model registry audit now emits adapter health summaries from provider preflight telemetry, recent model attempts, and route cooldown signals.
- Completed: native Model Stack now renders adapter health, missing secret status, cooldowns, skip counts, latest safe error text, and the next provider setup recommendation.
- Completed: fallback inspector candidates now attach adapter health signals, so missing keys, cooldowns, preflight skips, and provider recommendations appear on the route diagnostic path.
- Completed: web Observability fallback view now surfaces adapter-health issue counts and per-candidate provider health causes.
- Completed: route-quality telemetry now includes context-pressure drilldowns with budget utilization, selected/omitted references, largest context items, notes, and tuning recommendations.
- Completed: web Observability Quality now renders recent context drilldowns so budget pressure is inspectable from the dashboard.
- Completed: native desktop Planning History now parses and renders route context-pressure rollups plus recent per-task context drilldowns.
- Completed: model registry audit now includes provider tokenizer diagnostics for exact/profiled/heuristic/missing estimator coverage, and native Model Stack renders the diagnostic table.
- Completed: provider adapters now capture reported token usage from OpenAI-compatible, Ollama, and Anthropic responses when available, and successful attempts persist usage metadata for calibration.
- Completed: model registry audit now reports tokenizer calibration status, average/worst input and output token-estimation error, reported usage sources, and calibration recommendations.
- Completed: native Model Stack now renders tokenizer calibration counts, drift/watch warnings, per-provider calibration status, and usage-source tooltips.
- Completed: `/api/telemetry/route-quality` now includes provider/model token-calibration rollups with estimated-vs-reported usage, drift status, usage sources, and tuning recommendations.
- Completed: native Planning History and web Observability now render token-calibration health so routing dashboards show whether provider/model context estimates are stable, drifting, or still unobserved.
- Completed: token calibration now includes daily trend buckets with drift status, improving/worsening/flat direction, and trend recommendations across backend, native Planning History, and web Observability.
- Completed: telemetry snapshot refresh can now apply bounded retention/pruning and returns prune telemetry so cached dashboard windows stay controlled as usage grows.
- Completed: provider adapters now expose an additive `stream_text` contract, and `/api/chat/stream` exposes the first SSE lifecycle/final-response stream without breaking `/api/chat`.
- Completed: desktop and web clients now consume `/api/chat/stream` lifecycle events, surface streamed status updates, and preserve `/api/chat` as the compatibility fallback.
- Completed: direct read-only chat turns now stream provider text deltas through `/api/chat/stream` before the final structured `AgentResponse`.
- Completed: web and native desktop clients now render partial streamed assistant text and replace it with the final structured response when the turn completes.
- Completed: structured workspace turns now use `structured-delta-final` mode with safe progress deltas before the final `AgentResponse`, while raw provider JSON and file changes stay hidden until `final.response`.
- Completed: structured coding/build streams now request provider JSON mode, extract only top-level reply-style text for live preview deltas, and keep `changes`, commands, and file content hidden until the final response.
- Completed: structured streams now emit preview reconciliation notices and carry those notes into the final response when a live model preview is superseded by deterministic fallback output or a later routed provider.
- Completed: structured preview deltas are now provider-attempt aware; failed attempt previews emit `preview_action=reset`, and web/native clients remove that preview segment before later-provider text appears.
- Completed: web and native streaming status now uses provider/model metadata from structured preview events so users can see which model is currently drafting.
- Completed: per-attempt structured preview counters now persist in model-attempt metadata and surface in web/native route diagnostics, including preview deltas, character counts, resets, retired reasons, and final-winning attempts.
- Completed: route-quality telemetry now aggregates structured preview reliability by provider/model, surfaces stable/watch/unstable status in web/native diagnostics, and feeds preview reset penalties into route-health ranking.
- Completed: explicit absolute workspace paths outside the Aegis folder are now allowed by default for user-selected project work, while filesystem roots and protected system directories remain blocked.
- Next: add daily structured-preview trend buckets so streaming reliability regressions are visible over time.

## P0 Critical Tasks

| Order | Task | Dependencies | Expected Outcome |
| --- | --- | --- | --- |
| 1 | Create a canonical architecture map covering backend, desktop, web frontend, providers, tools, storage, memory, and execution boundaries. | Existing repo scan | A single source of truth for how Aegis is composed and where new systems belong. |
| 2 | Split agent responsibilities into planner, router, context builder, model client, tool executor, apply engine, validation engine, and response assembler. | Architecture map | The main agent becomes orchestration instead of a monolith. |
| 3 | Define typed request/response envelopes for planning metadata, routing decisions, tool calls, tool results, context packets, and model attempts. | Schemas | Every subsystem can evolve without fragile ad hoc dictionaries. |
| 4 | Build a model provider adapter interface with `status`, `inventory`, `complete_json`, `stream`, `estimate_cost`, and `capabilities`. | Existing `llm.py` | OpenAI, Anthropic, Ollama, OpenRouter, Perplexity, LM Studio, and future providers share one contract. |
| 5 | Add a model router that chooses task role, privacy mode, candidate providers, fallback chain, and required capabilities per request. | Provider adapter interface | Chat, code, reasoning, research, vision, creative, embeddings, judge, and fallback routes are explicit. |
| 6 | Implement fallback-chain execution with structured attempt results. | Model router | One failed model call does not kill the response. |
| 7 | Add streaming chat contracts for backend and clients. | Response assembler | Partial responses can render immediately and survive provider failure. |
| 8 | Implement a context budget manager with token estimates, priority tiers, file snippets, memory snippets, and summarization slots. | Context builder | Aegis sends the right context without dumping the whole project. |
| 9 | Add safe tool permission manifests for read, write, patch, command, dependency, network, browser, Git, and plugin actions. | Tool executor | Every tool action has an allow/deny decision and audit trail. |
| 10 | Convert all tool execution events into durable structured logs. | Event store | Every read/write/command/model attempt can be reviewed later. |
| 11 | Add workspace write policy enforcement: relative paths only, deny secrets/caches/build output, checkpoint before mutation, diff before apply. | Apply engine | File editing is safe by default. |
| 12 | Add command sandbox policy with allowlist, timeout, cwd limits, output truncation, and manual approval markers. | Command runner | Commands are useful without becoming uncontrolled shell access. |
| 13 | Add auth foundation: users, sessions, roles, workspace permissions, API tokens, and local-only mode. | API layer | The system can move beyond a single trusted local user. |
| 14 | Add rate limiting and usage accounting by user, provider, model, endpoint, and tool type. | Auth foundation | Cloud spend and abuse are controlled. |
| 15 | Add telemetry schema for latency, errors, token estimates, cost estimates, model quality rating, and tool success. | Event store | Routing can improve from observed behavior. |

## P1 High Priority Tasks

| Order | Task | Dependencies | Expected Outcome |
| --- | --- | --- | --- |
| 16 | Add short-term conversation memory with turn summaries, active goals, open decisions, and pending actions. | Context budget manager | Long sessions stay coherent. |
| 17 | Add long-term project memory with confidence, source, file links, tags, and expiration rules. | Memory store | Aegis remembers durable project facts without overfitting every chat turn. |
| 18 | Add vector/RAG indexing for source files, docs, transcripts, and memory notes. | Project indexer | Retrieval improves beyond keyword matching. |
| 19 | Add context compression that summarizes older turns and large files into scoped packets. | Memory + indexing | Big projects fit into model context windows. |
| 20 | Add planning modes: quick answer, inspect first, propose patch, apply patch, validate, repair, research, creative. | Task planner | The agent chooses a workflow before generating text. |
| 21 | Add multi-step task state: objective, assumptions, steps, blockers, artifacts, current step, and completion criteria. | Planner | Complex work can resume and be inspected. |
| 22 | Add self-evaluation pass using a judge route for risky code, long answers, and multi-file changes. | Router + judge provider | Aegis catches more errors before the user sees them. |
| 23 | Add patch generation as the default edit format, with full-file fallback only when safer. | Diff engine | Smaller edits, clearer review, fewer accidental rewrites. |
| 24 | Add project-wide search API with filename, symbol, text, and semantic modes. | Indexer | The agent can inspect code quickly and explain what it found. |
| 25 | Add dependency manager tools for npm, pnpm, pip, uv, cargo, go, dotnet with dry-run planning. | Command policy | Package changes become explicit and reviewable. |
| 26 | Add GitHub integration for repo import, issue context, PR summaries, branch status, and review comments. | Auth + tool permissions | Aegis becomes useful in real development workflows. |
| 27 | Add plugin system with signed manifests, permission scopes, versioning, disable controls, and event logs. | Tool permissions | Third-party extensions can exist without owning the host app. |
| 28 | Add API modules by domain: chat, models, tools, files, memory, projects, auth, telemetry, admin. | Backend refactor | Endpoints stop accumulating in one file. |
| 29 | Add structured error envelopes with user message, developer detail, code, retryable flag, and correlation id. | API modules | Frontends can handle failure cleanly. |
| 30 | Add background worker abstraction for indexing, long validations, embeddings, media jobs, and repo sync. | Storage + queues | Slow tasks stop blocking chat endpoints. |

## P2 Medium Priority Tasks

| Order | Task | Dependencies | Expected Outcome |
| --- | --- | --- | --- |
| 31 | Add Next.js/TSX web app shell with chat, project file explorer, editor/diff viewer, settings, memory, and model stack. | API modules | A modern web client can coexist with the native desktop. |
| 32 | Add streaming markdown renderer with code copy, file references, collapsible reasoning summaries, and tool timeline. | Streaming API | Chat feels immediate and readable. |
| 33 | Add Monaco or CodeMirror editor with readonly preview, proposed patch mode, and apply controls. | File/diff APIs | Users can review generated code professionally. |
| 34 | Add model selection UI with provider health, roles, privacy labels, cost hints, and fallback chain preview. | Model registry | Users understand where prompts go. |
| 35 | Add memory management UI for pin, edit, delete, confidence, scope, and source trace. | Memory APIs | Memory becomes inspectable and trustworthy. |
| 36 | Add premium design system: dense layout, clean typography, precise spacing, restrained color, keyboard shortcuts, and responsive states. | Frontend shell | Aegis feels like a serious engineering tool. |
| 37 | Add project dashboard with active task, recent files, validation state, model health, memory highlights, and open risks. | Telemetry + APIs | Users start each session oriented. |
| 38 | Add admin settings for provider keys through OS credential storage or server-side secret manager only. | Auth + provider adapters | Secrets are managed intentionally. |
| 39 | Add caching for provider status, model inventory, file index, embeddings, and static project metadata. | Telemetry + storage | Lower latency and fewer provider calls. |
| 40 | Add horizontal scaling readiness: stateless API workers, shared DB, object storage, queue, and websocket/session coordination. | Background workers | Aegis can grow beyond one local process. |

## P3 Lower Priority Tasks

| Order | Task | Dependencies | Expected Outcome |
| --- | --- | --- | --- |
| 41 | Add browser automation tool with explicit domain allowlist and screenshot auditing. | Tool permissions | Aegis can inspect local/web UIs safely. |
| 42 | Add terminal session layer with persistent shell sessions, transcript capture, and approval gates. | Command policy | Interactive workflows become manageable. |
| 43 | Add repo intelligence: dependency graph, call graph, architecture map, ownership map, and risk map. | Indexing | Aegis understands more than file text. |
| 44 | Add prompt library and reusable agent workflows for review, refactor, test generation, migration, docs, and release prep. | Planner | Common workflows become repeatable. |
| 45 | Add eval harness with golden tasks, model comparisons, regression checks, and quality dashboards. | Judge route + telemetry | Intelligence upgrades become measurable. |
| 46 | Add collaboration features: shared projects, comments, approvals, task handoff, audit history. | Auth + storage | Teams can use Aegis together. |
| 47 | Add marketplace-ready plugin packaging, signing, update checks, and compatibility constraints. | Plugin system | Extensions become distributable. |
| 48 | Add mobile/tablet read-only companion for monitoring tasks and approving safe actions. | API auth | Users can supervise long tasks remotely. |

## Core System Backlog

### Chat Engine

- Define chat session aggregate: id, title, participants, model route, created time, updated time, pinned state, archive state.
- Add response lifecycle states: queued, planning, retrieving context, calling model, streaming, tool pending, applying changes, validating, completed, failed, canceled.
- Add cancellation tokens that propagate to model calls, tool calls, and background jobs.
- Preserve partial assistant output if a stream fails.
- Store message provenance: provider, model, route, tool events, context ids, memory ids, token/cost estimates.
- Add conversation branch and regenerate flows.
- Add attachment normalization and per-attachment risk scanning.

### Memory Systems

- Short-term memory: rolling session summary, active task goals, current constraints, unresolved questions.
- Long-term memory: project facts, user preferences, architecture decisions, rejected approaches, recurring bugs.
- Vector memory: chunk source/docs/messages, embed, retrieve, rerank, cite.
- Memory governance: confidence score, source, scope, TTL, user edit/delete, privacy mode.
- Memory ingestion: accepted code changes, user corrections, validations, PR summaries, docs.

### Model Abstraction And Routing

- Provider adapter base class with consistent errors and capability declarations.
- Per-provider adapters for Ollama, OpenAI-compatible, OpenAI cloud, Anthropic, OpenRouter, Perplexity, embeddings, judge.
- Router policy inputs: task type, privacy mode, capabilities, latency, health, cost, context size, user preference.
- Router policy outputs: primary provider, fallback chain, max attempts, response mode, tool allowance.
- Provider health cache and degraded-mode flags.
- Cost and token estimator per model family.

### Tool And Agent System

- Tool registry with id, description, input schema, output schema, permission scopes, risk tier.
- Tool planner that decides inspect, edit, validate, research, or ask.
- Tool executor that records every action before and after execution.
- Tool result summarizer for long outputs.
- Approval policy engine for reads, writes, commands, network, Git, and plugins.
- Agent workflows: coder, reviewer, researcher, planner, judge, creative, memory curator.

### Coding Agent Features

- Read file, list files, search text, search symbols, inspect dependencies, inspect tests.
- Generate unified diffs and apply hunks selectively.
- Create checkpoints before writes and restore on failure.
- Detect project type and validation commands.
- Propose dependency changes with manifest diffs.
- Support safe command execution with timeout and output limits.
- Add repair loop with max attempts, failure categorization, and rollback criteria.

### Backend Architecture

- Split `main.py` into routers: `chat`, `models`, `tools`, `files`, `memory`, `projects`, `validation`, `media`, `admin`.
- Split `agent.py` into orchestration plus domain services.
- Add DB migrations and typed repositories.
- Add request id middleware and structured logging.
- Add auth middleware and role checks.
- Add rate limit middleware.
- Add OpenAPI tags and stable response envelopes.

### Frontend

- Chat shell with streaming response area, composer, attachments, mode selector, stop/regenerate.
- Left project rail with file explorer, search, recent files, Git status.
- Right context rail with model route, memory, tool timeline, validation, cost estimate.
- Diff viewer with per-file and per-hunk approval.
- Settings for providers, routing presets, privacy, tools, workspace, validation.
- Keyboard shortcuts and command palette.
- Empty/loading/error states for every panel.

### Security And Safety

- Deny secret files by default: `.env`, keys, tokens, credential stores, caches, build outputs.
- Redact secrets in logs, events, context previews, provider payload previews.
- Validate all model-returned file paths before applying.
- Validate all tool inputs with schemas.
- Require manual approval for destructive writes, broad deletes, network commands, dependency installs, and Git pushes.
- Add audit log export.

### Performance And Scaling

- Cache model inventory and provider status.
- Incrementally index workspaces.
- Use background jobs for embeddings, scans, media, validation, long commands.
- Stream tokens and tool events separately.
- Add DB indexes for task history, events, memory, project files.
- Design for multiple API workers behind a load balancer.

### Integrations

- GitHub OAuth/App integration for repo, issues, PRs, comments, checks.
- Terminal access through sandboxed sessions.
- External API connectors via plugin manifests.
- Local model manager integrations for Ollama, LM Studio, llama.cpp, vLLM.
- Browser inspection for localhost apps with screenshots and DOM snapshots.

### Dev Infrastructure

- Monorepo layout documentation.
- Environment templates for local, staging, production.
- CI jobs: lint, typecheck, unit tests, integration tests, security scan, build artifacts.
- Code style: Python typing, TS strict mode, C++ warnings, formatter configs.
- Release checklist and migration checklist.
- Architecture decision records in `docs/adr`.

## Current Execution Pass

### Completed In Pass 001

1. Critical: Add task planning and route recommendation primitives.
   - Dependencies: existing `AgentEngine`, schemas, provider registry.
   - Expected outcome: each request gets a structured task plan and route metadata before model calls.
2. Critical: Keep the current runtime path compatible.
   - Dependencies: planner primitives.
   - Expected outcome: planning metadata is emitted as tool events and prompt context, without requiring the frontend to change immediately.
3. High: Prepare future provider adapter split.
   - Dependencies: current `llm.py`.
   - Expected outcome: routes can point at provider roles before live execution is fully replaced.

### Completed In Pass 002

1. Critical: Promote task planning and routing metadata into stable API schemas.
   - Dependencies: planner primitives from Pass 001.
   - Expected outcome: desktop and web clients can render `task_plan` directly.
2. Critical: Add model attempt contracts for future fallback-chain execution.
   - Dependencies: routing decisions and response schemas.
   - Expected outcome: every request can expose planned model attempts before live execution is implemented.
3. High: Wire response assembly to expose `task_plan` and `model_attempts`.
   - Dependencies: `AgentResponse`, `TaskPlanInfo`, `ModelAttemptInfo`.
   - Expected outcome: planned route metadata is a first-class API field, not just a generic event payload.

### Completed In Pass 003

1. Critical: Introduce provider adapter protocol and active-provider registry.
   - Dependencies: `llm.py`, settings, provider env keys.
   - Expected outcome: provider-specific HTTP formatting and response parsing move behind clean adapter classes.
2. Critical: Preserve current agent compatibility.
   - Dependencies: existing `LocalModelClient` imports.
   - Expected outcome: the existing agent can keep calling `status`, `inventory`, and `complete_json` while adapter internals evolve.
3. High: Resolve planned model attempts against model registry providers.
   - Dependencies: model registry, `ModelExecutionPlanner`.
   - Expected outcome: model attempts prefer enabled/configured registry providers that match task roles or capabilities.

### Completed In Pass 004

1. Critical: Add provider adapter factory for arbitrary registry providers.
   - Dependencies: provider adapter protocol, `ModelRegistryProvider`, active settings.
   - Expected outcome: Aegis can instantiate adapters from active settings, registry providers, or planned attempts.
2. Critical: Add non-streaming model attempt executor service.
   - Dependencies: `ModelExecutionPlan`, provider adapter factory.
   - Expected outcome: a fallback chain can be executed as structured planned attempts without changing the current chat path yet.
3. High: Add structured provider errors.
   - Dependencies: provider adapters.
   - Expected outcome: provider failures carry code, retryable flag, status code, provider label, and safe user message.

### Completed In Pass 005

1. Critical: Add first-class provider model identity and cost metadata.
   - Dependencies: `ModelRegistryProvider`, provider adapter config, desktop model provider editor.
   - Expected outcome: provider records store model names, aliases, secret env names, context windows, rate limits, and cost hints explicitly.
2. Critical: Preserve safe secret handling in registry-backed adapters.
   - Dependencies: provider factory and registry manager.
   - Expected outcome: adapters resolve explicit secret env names without copying keys into config, notes, transcripts, or desktop state.
3. High: Expose router execution as a disabled-by-default feature gate.
   - Dependencies: settings and `/api/config`.
   - Expected outcome: future live fallback-chain execution can be integrated deliberately.

### Completed In Pass 006

1. Critical: Add route-specific context budget profiles.
   - Dependencies: task planner, router, workspace context builder.
   - Expected outcome: implementation, repair, review, architecture, research, and chat routes receive different context mixes.
2. Critical: Return context budget metadata as a stable API field.
   - Dependencies: response schemas and `AgentEngine`.
   - Expected outcome: clients can inspect selected context strategy, token estimates, file counts, memory counts, omissions, and notes.
3. High: Add deterministic token and cost estimates to planned model attempts.
   - Dependencies: registry model metadata and context budget output.
   - Expected outcome: planned attempts carry input/output token estimates, cost estimates where pricing exists, and context-window utilization hints.

### Completed In Pass 007

1. Critical: Persist planning telemetry.
   - Dependencies: event store, task ids, `ContextBudgetInfo`, `ModelAttemptInfo`.
   - Expected outcome: context budget snapshots and model attempt snapshots are stored durably per workspace.
2. Critical: Add client-readable telemetry endpoint.
   - Dependencies: telemetry tables and response schemas.
   - Expected outcome: `/api/telemetry` exposes recent context budgets and model attempts without scraping generic event payloads.
3. High: Keep telemetry analytics ready for later routing quality loops.
   - Dependencies: SQLite indexes and structured payloads.
   - Expected outcome: future dashboards can analyze estimated spend, context efficiency, and model reliability.

### Completed In Pass 008

1. Critical: Parse planning metadata in the native desktop client.
   - Dependencies: backend `task_plan`, `context_budget`, and `model_attempts` response fields.
   - Expected outcome: C++ client state can carry route, context, and model attempt metadata for UI rendering.
2. High: Add a compact desktop route timeline card.
   - Dependencies: parsed desktop response metadata and existing right-panel card layout.
   - Expected outcome: the right panel shows task role, privacy mode, provider lane, context budget, file/memory selection, model attempts, token estimates, and cost hints when available.
3. Medium: Preserve uncluttered dashboard behavior.
   - Dependencies: existing suggested prompts card.
   - Expected outcome: suggested prompts remain visible before metadata exists; route details only occupy that space after a response includes planning data.

### Completed In Pass 009

1. Critical: Add registry versioned backfill.
   - Dependencies: `ModelRegistryManager`, default registry records, provider metadata schemas.
   - Expected outcome: existing `model_registry.json` payloads are upgraded to registry version 2 and saved once during snapshot loading.
2. Critical: Materialize provider metadata defaults.
   - Dependencies: active model settings, endpoint locality detection, provider secret-env inference.
   - Expected outcome: older providers receive explicit `model_name`, `model_aliases`, `secret_env`, `cost_tier`, `context_window`, `rate_limit_rpm`, and per-million-token cost fields.
3. High: Preserve user intent while migrating defaults.
   - Dependencies: provider delete/upsert behavior.
   - Expected outcome: missing default providers, roles, and presets are added during version migration, but user-deleted defaults are not re-added after the registry is already current.

### Completed In Pass 010

1. Critical: Wire non-streaming fallback-chain execution behind a disabled default flag.
   - Dependencies: `ModelAttemptExecutor`, model execution plans, provider adapter factory, `AEGIS_ROUTER_EXECUTION_ENABLED`.
   - Expected outcome: when the flag is off, the existing local model path remains unchanged; when it is on, Aegis walks the planned provider chain.
2. Critical: Return first successful routed JSON draft.
   - Dependencies: provider adapters and shared model prompt messages.
   - Expected outcome: the first successful provider attempt becomes the draft payload, while failed attempts continue through the fallback chain.
3. High: Replace planned model telemetry with live attempt status.
   - Dependencies: model attempt telemetry storage.
   - Expected outcome: routed runs can record succeeded, failed, skipped, latency, retryability, provider/model identity, and safe error details for the task.
4. Medium: Keep deterministic fallback as the final safety path.
   - Dependencies: fallback engine.
   - Expected outcome: if routed execution crashes or all attempts fail, Aegis still returns a usable deterministic draft with warnings.

### Next Execution Pass

1. High: Add desktop telemetry history panels for `/api/telemetry`.
   - Dependencies: telemetry endpoint and native client models.
   - Expected outcome: users can inspect recent route budgets and model attempt history for the active workspace.
2. High: Add provider-specific token estimator hooks.
   - Dependencies: provider adapters and attempt records.
   - Expected outcome: token estimates improve while deterministic character-based estimation remains the fallback.
3. Medium: Add aggregate telemetry views.
   - Dependencies: telemetry persistence and client history panels.
   - Expected outcome: route success, estimated spend, model reliability, and context efficiency are visible over time.
4. Medium: Add streaming protocol contracts for provider adapters.
   - Dependencies: response lifecycle states and provider adapter interface.
   - Expected outcome: streaming can be added without reshaping core planning and telemetry contracts.
5. Medium: Add web route/context panels matching the native desktop route timeline.
   - Dependencies: stable response metadata and future web app shell.
   - Expected outcome: the Next.js client gets the same planner transparency as the desktop client.
6. Medium: Add route-quality policy updates from telemetry and user feedback.
   - Dependencies: aggregate telemetry and feedback records.
   - Expected outcome: routing can eventually prefer providers with better observed reliability and usefulness.
