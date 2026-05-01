# Aegis AI Provider Stack

This desktop app is a native C++/ImGui shell around the Aegis backend. The fastest path to a stronger coding AI is not a rewrite; it is a provider router that lets the backend choose the right model lane for each task while the desktop keeps the user in control.

## Provider Lanes

| Lane | Purpose | Secret handling |
| --- | --- | --- |
| OpenAI Primary | Coding, reasoning, tools, vision, structured output, embeddings, judging | `OPENAI_API_KEY` in environment or OS credential storage |
| Anthropic Claude | Coding, review, reasoning, fallback diversity | `ANTHROPIC_API_KEY` in environment or OS credential storage |
| Ollama Local | Private project context, local fallback, offline coding loops | No cloud key |
| LM Studio Local | OpenAI-compatible local testing | No cloud key |
| OpenRouter Router | Optional model diversity and experiments | `OPENROUTER_API_KEY` in environment or OS credential storage |
| Perplexity Research | Search/research specialist lane | `PERPLEXITY_API_KEY` in environment or OS credential storage |
| Local Judge | Private local scoring and response checks | No cloud key |

## Desktop Work Added

- The Model Stack modal now shows an agent routing readiness table for chat, code, reasoning, research, vision, creative, embeddings, judge, and fallback lanes.
- The Model Stack modal now includes provider blueprints that stage common providers without storing API keys in the desktop app.
- Provider records can now carry model name, aliases, secret environment variable, cost tier, context window, RPM limit, and input/output cost hints.
- Blueprint setup notes can be copied to the clipboard for backend adapter work.
- Model API and endpoint can be staged into Settings from a blueprint, then saved intentionally.
- Chat responses now parse backend task plans, context budgets, model attempt metadata, and the router execution flag.
- The right panel now swaps Suggested Prompts for a compact Route Timeline after a planned response, showing task role, privacy mode, provider lane, context pressure, selected files/memory, and token/cost hints.
- The desktop app now has a Planning History modal backed by `/api/telemetry`, showing recent context budgets, model attempts, status, privacy, token pressure, and estimated spend.
- Planning History now consumes `/api/telemetry/route-quality` for aggregate reliability, fallback rate, context pressure, provider/role rollups, token-estimator provenance, and routing recommendations.
- Planning History now renders route-level context pressure and per-task context drilldowns with utilization, budget tokens, selected/omitted file and memory counts, largest references, and recommendations.
- Planning History now renders route-quality token-calibration rollups with provider/model drift status, calibrated sample counts, average input/output error, estimated-vs-reported usage, and source tooltips.
- Planning History now also renders daily token-calibration trends with improving/worsening/flat direction so drift can be spotted over time.
- Planning History now consumes `/api/telemetry/fallback-inspector` for task-level route candidates, fallback roles, attempt status, registry resolution, estimated cost, and estimator source.
- Planning History fallback inspection is now a selectable task drilldown with full candidate rows, full attempt rows, task recommendations, candidate IDs, context metadata, and attempt metadata.
- Model Stack now renders tokenizer diagnostics from the registry audit, including estimator source, context window, utilization, exact/profiled/heuristic/missing attempt counts, and next recommendations.
- Model Stack now also shows tokenizer calibration status from provider-reported usage, including calibrated attempt counts, average input/output drift, warning summaries, and source tooltips.
- Provider inventory now infers richer capability flags for code, reasoning, tools, vision, embeddings, audio, image, video, realtime, judge, and computer-use lanes.
- Route execution planning now requires all meaningful task capabilities before selecting a provider, preventing partial matches such as a vision-only model being chosen for a vision-plus-tools task.
- Routed execution now runs provider preflight before live calls, so disabled providers, missing model names, unsupported APIs, and missing cloud API keys are recorded as skipped attempts and the fallback chain can continue.
- Model Stack now includes adapter health rows from registry audit, showing ready, missing-secret, unconfigured, cooldown, skipped-preflight, and latest-error states per provider.
- Feedback actions now write structured telemetry through `/api/feedback`, with route-quality scoring fields for positive, negative, applied, regenerated, corrected, and rolled-back outcomes.
- Planning History now shows feedback outcome attribution by provider, model, route role, task intent, candidate, target, and action.
- Settings now expose feedback privacy controls for shared-workspace no-excerpt mode, redaction, excerpt length, and content-hash storage.
- Planning History now shows feedback trends and recent feedback events without exposing raw prompt or response content.
- Native chat now uses `/api/chat/stream` for status/final lifecycle events, with WinHTTP chunk streaming and a UI-thread status queue so progress can update while the backend works.
- Native chat now also renders streamed direct-chat deltas into a live assistant placeholder, then replaces that placeholder with the final structured response once the backend sends `final`.

## Web Work Added

- The web client now has typed telemetry API helpers for route-quality, fallback-inspector, and feedback telemetry endpoints.
- The web chat client now posts to `/api/chat/stream`, consumes SSE meta/status/final events, and falls back to the stable `/api/chat` request path when browser streaming is unavailable.
- Web chat now renders `delta` events inline for direct read-only chat turns and reconciles the message with `final.response` when the stream finishes.
- The web sidebar now includes an Observability panel with quality, fallback, and feedback tabs that match the backend telemetry contracts.
- Web route quality now shows reliability, success, latency, cost, provider health, route roles, context pressure, and recommendations.
- Web route quality now includes context drilldowns with utilization, selected/omitted file counts, memory counts, largest context references, and tuning recommendations.
- Web route quality now includes token-calibration cards so provider/model token drift is visible alongside reliability and context pressure.
- Web route quality now includes token-calibration trend cards for recent daily drift movement.
- Web fallback inspection now shows recent routed tasks, candidate counts, fallback roles, candidate status, provider/model labels, reasons, and errors.
- Web feedback telemetry now shows positive/negative rates, revised/applied counts, trend buckets, attribution rollups, and recent privacy-preserving feedback events.
- Web observability now prefers materialized telemetry snapshots and falls back to live endpoint reads when no snapshot exists yet.
- Web observability now includes a Policy tab for reviewable provider promotion, deprioritization, and route-role proposal summaries.
- Web fallback inspection now displays adapter-health issue counts and per-candidate health causes from the enriched fallback inspector payload.
- Native Planning History now has an Apply Safe Policy action that sends reviewed policy diffs through a guarded backend apply endpoint.
- Apply Safe Policy now opens a native confirmation modal with actionable provider/role summaries before the registry is changed.
- Native Project Builder now adds chat auto-detection, prompt planning, and previewable checkpointed scaffold creation for Next.js, Vite React, Python CLI, FastAPI, Express TypeScript, C++ CMake, Electron desktop, Expo React Native, Django, Rust CLI, Go HTTP API, ASP.NET Core C# Web API, and Tauri React desktop projects, including backend presets, validation profile setup, generated file summaries, and one-click workspace switching.
- Every generated project now includes `AGENTS.md` plus `.aegis/project.json`, giving future Aegis coding passes a stack manifest, install/validation commands, first-pass checklist, and safety notes.
- Native Workspace now consumes `/api/workspace/profile` and shows the active project manifest with stack, tags, install/validation commands, first-pass handoff, safety notes, and command copy actions.
- Native Workspace now also shows inferred dependency profile data, including languages, frameworks, package managers, build systems, config files, database tools, scripts, runtime dependencies, dev dependencies, and inferred install/validation command copy actions.
- Native composer now turns the active workspace manifest into quick actions for first-pass prompts, stack-aware coding routes, install command copy, and validation command staging.
- Route previews now include workspace-manifest recommendations so the desktop can show stack-aware routing hints before a prompt is sent.
- Native route timelines and fallback drilldowns now parse route-profile metadata from task plans and model attempts.
- Route profiles now include database, native binary, kernel-driver, and authorized reverse-engineering profiles for broader coding-bot coverage.
- Native Settings and Command Palette now expose Full Verify, including install-step and continue-after-failure controls, a verification step table, first-failure summary, failure-output copy support, targeted repair, automatic Full Verify rerun after the targeted command passes, controlled multi-step repair chaining, a verification-repair activity timeline, copyable verification reports, Markdown report export, reports-folder access, a recent report browser, attach-latest report context, and report pruning controls.

## Backend Work Added

- Provider adapters now share a registry/config contract instead of relying only on active settings.
- Model execution plans now resolve concrete registry provider model names when a route matches a provider.
- `AEGIS_ROUTER_EXECUTION_ENABLED` is available as a disabled-by-default gate for future live fallback-chain execution.
- Backend registry records preserve explicit secret env names so API keys stay out of notes and desktop state.
- Existing model registry files now backfill to version 2 with explicit provider model identity, aliases, secret env names, cost tier, context window, RPM limits, and pricing fields.
- When `AEGIS_ROUTER_EXECUTION_ENABLED` is enabled, the backend can execute the planned non-streaming provider fallback chain and replace planned model-attempt telemetry with live statuses.
- Planning-time token and cost estimates now use provider/model-family tokenizer profiles and record estimator provenance in model-attempt metadata.
- `/api/telemetry/route-quality` now returns aggregate reliability, fallback, spend, context-pressure, provider, role, and recommendation rollups.
- `/api/telemetry/route-quality` now returns context drilldowns for recent budget pressure, selected and omitted references, largest context items, and route-specific tuning recommendations.
- `/api/telemetry/fallback-inspector` now returns recent task plans, route candidates, fallback roles, context budgets, model attempts, registry resolution, estimator provenance, and per-task recommendations.
- Planner route candidates now carry stable candidate IDs that persist into model-attempt metadata, making fallback-inspector matching deterministic for new telemetry.
- `/api/telemetry/feedback` now exposes structured feedback events and summary counts so future policy updates can compare route quality against real user outcomes.
- `/api/telemetry/feedback` and `/api/telemetry/route-quality` now include feedback attribution rollups joined against model attempts and context budgets.
- `/api/feedback` now applies backend feedback privacy policy before writing project-memory excerpts or content hashes.
- `/api/telemetry/feedback` and `/api/telemetry/route-quality` now include daily feedback trend buckets, and route quality includes a capped recent feedback event drilldown.
- `/api/telemetry/snapshot` and `/api/telemetry/snapshot/refresh` now expose materialized route-quality, fallback-inspector, and feedback payloads with cache freshness metadata.
- `/api/telemetry/policy-diff` now returns read-only route-policy proposals from reliability, fallback, cost, context-pressure, and feedback signals.
- `/api/model-registry/apply-policy-diff` now checkpoints the registry, applies confident non-high-risk policy proposals, and refreshes route primaries/fallbacks without disabling providers automatically.
- `/api/project-builder/presets`, `/api/project-builder/plan`, `/api/project-builder/preview`, and `/api/project-builder/scaffold` now expose deterministic project planning and creation through the backend workspace/checkpoint system instead of relying on a free-form chat response.
- `/api/workspace/profile` now reads `.aegis/project.json`; validation discovery prefers the manifest command, and routed model prompts include the generated stack, install/validation commands, first-pass handoff, and safety notes.
- `/api/workspace/profile` now includes dependency-stack inference from Node, Python, Rust, Go, .NET, CMake, Maven, Gradle, Prisma, migration, and SQL manifests, and the planner injects that structured profile into routing context and model prompts.
- Backend task planning now uses `.aegis/project.json` during intent/routing, so broad continuation prompts in generated projects route as stack-aware implementation work.
- Backend task planning now derives route profiles from manifests for web, desktop, mobile, API, data, and systems/CLI stacks, then carries those profiles into route previews and model-attempt metadata.
- Backend task planning now detects database/schema, DLL/EXE/native binary, kernel-driver/firmware, and authorized reverse-engineering prompts even without a manifest.
- Validation discovery now proposes commands for CMake/CTest, Visual C++ MSBuild, Make, Maven, Gradle, Prisma, and SQLFluff alongside the existing Node/Python/Rust/Go/.NET/TypeScript checks.
- Validation discovery now respects npm, pnpm, yarn, and bun package managers and can infer install steps when Full Verify includes install without a manifest command.
- `/api/verify` now builds an ordered verification pipeline across install, configure, build, type-check, database validation, lint, test, and final validation phases, with per-step status and first-failure reporting.
- Chat repair requests can now carry a one-turn validation command override, allowing the desktop to repair the exact first failed Full Verify command without permanently changing the saved validation profile.
- `/api/model-registry/audit` now accepts an optional workspace root and returns adapter health summaries from recent model attempts, provider preflight skips, missing secret checks, disabled/unconfigured providers, and route cooldown signals.
- `/api/telemetry/fallback-inspector` and telemetry snapshot responses now enrich route candidates with matching adapter-health status, preflight skip counts, secret env names, cooldown flags, and provider recommendations.
- `/api/model-registry/audit` now also returns tokenizer diagnostics that classify each provider as exact, profiled, heuristic, missing, mixed, or unobserved based on recent model-attempt estimator metadata.
- Provider adapters now capture reported token usage from OpenAI-compatible, Ollama, and Anthropic responses when those APIs return usage fields.
- Successful routed attempts now persist provider-reported token usage metadata so registry audit can compare planning estimates against actual provider usage.
- `/api/model-registry/audit` tokenizer diagnostics now include calibration status, calibrated attempt count, average/worst input and output token-estimation error, reported usage sources, and calibration recommendations.
- `/api/telemetry/route-quality` now emits token-calibration rollups that compare estimated and provider-reported usage by provider/model, classify drift, and feed route-quality recommendations.
- `/api/telemetry/route-quality` now emits daily token-calibration trend buckets with status, direction, sample counts, and tuning recommendations.
- `/api/telemetry/snapshot` can now prune stale or over-capacity materialized snapshots and returns retention telemetry for observability clients.
- Web Observability now reports snapshot retention/pruning status after cached snapshot reads and refreshes.
- Provider adapters now expose a `stream_text` contract with lifecycle, delta, metadata, and done events for OpenAI-compatible, Ollama, Anthropic, and emulated fallback streams.
- `/api/chat/stream` now serves an SSE contract that streams meta/status/final/error/done events while preserving `/api/chat` as the stable compatibility endpoint.
- `/api/chat/stream` now switches safe conversation turns into `chat-delta-final` mode, streams provider text deltas, records route/model telemetry, and still finishes with a normal `AgentResponse`.
- `/api/chat/stream` now switches structured workspace turns into `structured-delta-final` mode, streams safe progress deltas, keeps raw JSON/file-change payloads internal, and reconciles everything through the final `AgentResponse`.
- Structured workspace streams now request provider JSON mode and pass chunks through a top-level reply extractor, so coding/build turns can show live assistant preview text without exposing `changes`, command suggestions, or generated file content.
- Structured streams now emit reconciliation notices when a live preview is replaced by deterministic fallback output or by a later provider in the route chain, and the note is preserved in the final `AgentResponse`.
- Structured preview events now include provider-attempt metadata and `preview_action=append|reset`, allowing clients to retire failed-provider preview text before appending the next provider's draft.
- Web and native streaming status now names the provider/model currently producing structured preview text.
- Model-attempt metadata now records structured preview telemetry (`delta_count`, `char_count`, resets, retired reason, final winner), and web/native route diagnostics surface those counters.
- `/api/telemetry/route-quality` now includes structured-preview reliability rollups, and route-health penalties can demote providers that repeatedly retire/reset structured preview streams.

## Backend Work Next

1. Add exact tokenizer adapters once prompt-packet assembly exposes raw text safely.
2. Add daily trend buckets for structured-preview reliability so regressions are visible before a provider is promoted or demoted.
3. Add scheduled snapshot refresh policy for larger telemetry windows.
4. Keep cloud-context consent tied to the desktop Context Preview warning and privacy presets.
5. Add a stricter policy-review modal for high-risk route changes that should never apply automatically.
6. Add team/workspace policy presets for local-only, hybrid, and cloud-assisted routing.
7. Add richer verification progress snapshots for long native/JVM/database pipelines.

## Desktop Work Next

1. Add desktop smoke coverage for Full Verify repair and verification-result rendering.
2. Add verification-result snapshots that can be replayed in desktop smoke tests without rerunning expensive commands.
3. Add richer calibration trend charts once the dashboard has a dedicated observability canvas.
4. Keep Suggested Prompts available as a quick-start state when no route metadata exists yet.

The bundled `claude.zip` should be treated as reference material only. Do not copy proprietary source into Aegis; study interaction patterns, then implement original code through Aegis' own provider and tool architecture.
