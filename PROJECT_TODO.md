# Aegis ChatBot Master TODO

Last updated: 2026-04-29

This is the working build list for the Aegis desktop chatbot. Use it as the execution board: first stabilize the native desktop app, then build the model gateway, then expand into creative generation, coding workflows, memory, evals, and release polish.

## Current Snapshot

- Native C++ Win32 / DirectX 11 / Dear ImGui desktop app.
- Frameless custom window chrome.
- Login screen, setup/loading screen, and premium dashboard shell.
- Backend auto-start through the configured FastAPI app.
- FastAPI backend with chat, config, files, apply, validate, history, memory, index, diff, model inventory, and creative media endpoints.
- Current desktop model config is local-first through Ollama or OpenAI-compatible endpoints.
- Backend model inventory endpoint exists at `/api/models`.
- Creative media first slice exists for images, video packages, animations, GIFs, PSD template packages, theme inference, and revision jobs.
- Desktop smoke test exists at `scripts/smoke-desktop.ps1`; `build.ps1 -Smoke` compiles and captures login/setup/dashboard for blank-render checks.
- Desktop command palette exists for fast access to chat, creative, coding, model, validation, settings, runtime, and roadmap actions.
- Desktop Project Builder now opens from Coding Routes, chat auto-detection, or the command palette, can turn a plain project prompt into a preset-backed plan, previews planned files, loads thirteen backend scaffold presets, creates checkpointed starter projects with Aegis handoff manifests, saves validation profiles, and can switch the active workspace to the generated project.
- Backend workspace intelligence now reads `.aegis/project.json`, exposes `/api/workspace/profile`, prefers manifest validation commands, and injects project stack/handoff metadata into model context.
- Backend task planning and route previews now use `.aegis/project.json` so broad continuation prompts can route as stack-aware project work instead of generic chat.
- Backend route planning now derives stack route profiles from manifests, including web app, desktop app, mobile app, API service, data tool, and systems/CLI profiles, and stores them in task-plan/model-attempt metadata.
- Backend route profiles now also cover database/schema work, native DLL/EXE binaries, kernel/driver/firmware work, and authorized reverse-engineering analysis with explicit safety and validation expectations.
- Backend workspace profiles now infer dependency stacks from `package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `.csproj`, `CMakeLists.txt`, Maven/Gradle manifests, Prisma schemas, migrations, and SQL files.
- Backend task planning and model prompts now include dependency languages, frameworks, package managers, build systems, install commands, validation commands, package scripts, and key dependencies.
- Native Workspace tab now displays the inferred dependency profile with copy actions for inferred install and validation commands.
- Backend provider routing now infers richer model capabilities, including tools, vision, embeddings, audio, image, video, realtime, code, reasoning, and judge tags, then requires all meaningful task capabilities before selecting a provider.
- Routed model execution now performs provider preflight checks for disabled providers, missing models, unsupported APIs, and missing cloud secret environment variables before attempting a live request.
- Backend validation discovery now covers broader build systems including CMake/CTest, Visual C++ MSBuild, Make, Maven, Gradle, Prisma schema validation, and SQL linting in addition to Node, Python, Rust, Go, .NET, and TypeScript.
- Backend validation now respects Node package managers from `packageManager` and lockfiles, so npm, pnpm, yarn, and bun projects get matching script and install commands.
- Backend verification now exposes `/api/verify`, plans ordered install/configure/build/typecheck/database/lint/test/validate steps, runs them through the command safety layer, captures the first failure, and reports per-step status for future repair loops.
- Native desktop now has a Full Verify action backed by `/api/verify`, with include-install/continue-after-failure controls, per-step status table, first-failure copy action, command-palette access, and repair-loop handoff from the first failed command.
- Full Verify reports can now be exported, browsed, copied, attached back into the next chat as context, and pruned with keep-latest retention controls.
- Full Verify repair can now run as a controlled chain: repair the current first failure, rerun the full pipeline, queue the next failure, and stop when clean, blocked, or the repair-pass limit is reached.
- Native Workspace tab now loads `/api/workspace/profile` and displays Aegis project manifest details, install/validation commands, tags, first-pass handoff, and safety notes with copy actions.
- Native composer now uses workspace manifest metadata for quick actions: first-pass prompt loading, stack-aware coding route launch, install command copy, and validation command staging.
- Creative Studio now has an in-app asset preview strip with selected asset, type, path, open/copy actions, theme/palette copy helpers, real DirectX/WIC raster previews for PNG/JPEG/GIF/BMP/TIFF/WebP when Windows has a decoder, in-app audio preview playback for beat/audio assets, and pre-generation controls for kind, prompt, revision feedback, theme, aspect ratio, size, duration, FPS, style, and output formats.
- Desktop toast notifications now surface backend, settings, validation, Creative Studio, copy, and error states without relying only on the top bar.
- Workspace and change-preview panels now include open file/open folder controls with workspace-aware path resolution.
- Dashboard runtime banner now keeps backend/model/startup problems visible with retry, settings, and model-stack actions.
- First-run Setup Check modal now verifies backend root, backend app file, Python venv/start script, API base, backend handshake, model readiness, workspace folder, and validation profile guidance from inside the desktop app.
- Desktop model stack now lets users select a discovered model directly from the live inventory and saves provider/name/endpoint back through `/api/config`.
- Assistant messages now show the answering model/runtime label, which prepares the chat UI for routing, fallback, comparison, and judge-model workflows.
- Desktop chat now saves the latest local conversation to app data and restores it on launch, including per-message model/runtime labels.
- Regenerate/retry now replaces the last assistant response using the currently selected model without duplicating the user message in the transcript.
- Composer attachment tray now attaches selected workspace text files as explicit context for the next message, with remove controls and command-palette access.
- Desktop stop/cancel now lets users cancel an active chat response and suppresses stale assistant output when the backend call returns.
- Current conversation can now export to a Markdown transcript from Chat Info or the command palette.
- Desktop conversations now save into a local conversation library with generated titles, search, pin/unpin, archive/restore, delete, load, and folder access.
- Composer now shows an obvious cloud-context warning when the active model target appears non-local and workspace or attachment context may be sent.
- Context Preview now reviews the active model target, attachments, workspace files, last response context, and memory signals before sending.
- Context Preview now includes an approximate token budget planner for composer text, attachments, chat history, workspace index context, previous response context, and memory/task signals.
- Backend model registry foundation now persists provider entries, routing roles, and routing presets through `/api/model-registry`, with provider create/update/delete endpoints.
- Desktop Model Stack now shows provider registry, routing roles, privacy/routing presets, and an editable provider registry form for local/cloud/creative/search/audio/judge providers.
- Desktop Planning History now reads `/api/telemetry` and shows recent context budgets, model attempts, privacy labels, token pressure, status, and estimated spend.
- Desktop Planning History now shows route-level context pressure and per-task context drilldowns with budget utilization, selected/omitted references, largest context items, and tuning recommendations.
- Web ChatBot now has an Observability sidebar panel with route-quality, fallback-inspector, and feedback tabs backed by typed telemetry API helpers.
- Backend telemetry can now materialize route-quality, fallback-inspector, and feedback snapshots for cached dashboard reads.
- Backend route-policy diff proposals now explain provider promotion, deprioritization, and role-routing changes before policy updates are applied.
- Backend and native Planning History now support a guarded Apply Safe Policy workflow for confident, non-high-risk route-policy updates.
- Apply Safe Policy now uses a native confirmation modal with provider/role summaries before writing registry changes.
- Model Stack now shows provider tokenizer diagnostics from registry audit, including estimator source, context window, context utilization, exact/profiled/heuristic/missing attempt counts, and tuning recommendations.
- Model Stack now shows tokenizer calibration health from provider-reported token usage, including calibrated attempt counts, input/output drift percentages, and warning tooltips.
- Route-quality telemetry, native Planning History, and web Observability now show provider/model token-calibration rollups with estimated-vs-reported usage, drift/watch/stable status, source provenance, and tuning recommendations.
- Route-quality telemetry, native Planning History, and web Observability now also show daily token-calibration trend buckets with improving/worsening/flat direction.
- Telemetry snapshots now support retention pruning, return prune summaries in the API response, and show retention status in web Observability.
- Backend provider adapters now have a streaming text contract, and `/api/chat/stream` exposes server-sent lifecycle events with the final structured response.
- Web ChatBot and native desktop chat now consume `/api/chat/stream` lifecycle events, surface streamed backend status, and retain `/api/chat` as a compatibility fallback.
- Direct read-only chat prompts now use `chat-delta-final` streaming with provider text deltas, inline web rendering, native desktop live assistant placeholders, and final structured-response reconciliation.
- Structured coding/build prompts now use `structured-delta-final` streaming with safe progress deltas while raw provider JSON, file changes, validation state, and apply metadata stay hidden until the final structured response.
- Structured coding/build streams now also request provider JSON mode and render only sanitized top-level reply preview deltas, keeping generated file content and command metadata hidden until final reconciliation.
- Structured streams now explain final-response handoffs when a live preview is superseded by deterministic fallback files or by a later provider attempt, and that explanation is preserved after the final response replaces the temporary stream.
- Structured preview events now carry provider-attempt metadata plus append/reset actions, and web/native clients remove failed attempt preview text before showing the next provider's draft.
- Web and native streaming status now names the provider/model currently producing structured preview text.
- Model-attempt metadata now records structured preview telemetry for deltas, character counts, reset count, retired reason, and final-winning attempts, and web/native diagnostics surface those counters.
- Route-quality telemetry now aggregates structured preview reliability by provider/model, native Planning History renders the rollup, web Observability shows preview status, and route-health penalties can deprioritize providers with repeated preview resets.
- Backend workspace policy now accepts explicit absolute project paths outside the Aegis folder by default, so prompts like "work in C:\path\to\project" can route there, while drive roots and protected system directories remain blocked.
- Context Preview now runs a pre-send safety scan for likely secrets, sensitive paths, noisy dependency/cache paths, and prompt-injection markers in visible context.
- Desktop chat now restores the saved workspace with the saved conversation and keeps runtime refreshes from snapping back to the default workspace.
- Create/build prompts that include an explicit Windows path now select that workspace, show a working/applying state, and auto-apply low-risk generated files.
- Backend workspaces can now live anywhere under the configured `AEGIS_WORKSPACE_ROOT` (default: the main Aegis folder) while generated file writes still stay inside the selected workspace.
- Composer controls now expose Auto Apply and Validate directly where the user sends messages.
- Task Snapshot and Changes now distinguish preview-only changes from changes already written to the workspace.
- Changes can now be copied or exported as a patch package from the Changes tab or command palette.
- Applied file writes now return checkpoints, and the desktop app can roll back the latest apply from Task Snapshot, Changes, or the command palette.
- Changes tab now has an inline diff view with old/new line numbers, colored additions/removals, and a raw generated-content tab.
- Changes tab now has a side-by-side diff view that compares the current file against the proposed generated result.
- Changes tab now supports applying only the selected generated file, and applied files are labeled in the change list.
- Changes tab now detects diff hunks and can apply only the selected hunk through the normal safe apply/checkpoint pipeline.
- Desktop now has a Checkpoint Browser backed by `/api/checkpoints`, with checkpoint file counts, manifest inspection, folder access, command-palette access, and restore-selected support.
- Desktop validation repair UI now surfaces failed validation clearly, exposes repair-attempt counts, adds a Fix Validation button, parses backend repair attempts, and lets users set automatic repair attempts from the composer.
- Desktop coding routes and validation settings now infer project-specific test/build commands from visible workspace files and include a dedicated Test Generation route.
- Desktop Memory Center now lets users inspect, create, edit, pin, search, copy, and delete workspace memory notes from the native app.
- Creative Studio can export selected job packages and individual generated assets into the local app exports folder, with buttons in the modal and command-palette access.

Runtime note: if the desktop app shows a model inventory warning or `/api/models` returns 404, restart the FastAPI backend so the running process matches the current backend code.

## North Star Capability Pillars

The app should become a practical AI command center, not just a chat window. Every feature below should eventually route through the model/provider registry, produce visible tool events, preserve revision history, and improve from user feedback.

- Visual creation: image generation, video generation, video editing, animation, GIFs, thumbnails, icon packs, sticker packs, brand kits, PSD/Photoshop templates, asset variants, and revision-aware creative jobs.
- Coding: web, mobile, desktop, macOS, Linux, Windows, scripts, cloud apps, data tools, game tooling, systems code, kernel/driver-level guidance, code review, testing, debugging, packaging, and release work.
- Music and audio: beat creation, song structure, drums, bass, melody, chords, MIDI/stem planning, WAV previews, sound design, mix notes, mastering guidance, podcast/voice cleanup later.
- General knowledge and education: tutoring, study plans, explanations, research summaries, citations, document analysis, quizzes, flashcards, and guided learning paths.
- Continuous learning and training: user preference memory, project memory, fix memory, feedback scoring, eval sets, model comparison, self-checking, and searchable knowledge that grows with use.
- Personal productivity: saved workflows, prompt templates, workspace profiles, task planning, diagnostics, exportable reports, and eventually voice input/output.

## Absolutely Needed

These are non-negotiable before the app can feel like a serious next-generation chatbot.

### P0 Desktop Stability

- [ ] Never open to a black window.
- [ ] Never assert/crash from ImGui cursor or child-window misuse.
- [ ] Root ImGui canvas must match the real host window on DPI-scaled Windows displays.
- [ ] Login, loading, dashboard, settings, and modals must remain centered and readable from minimum size through large desktop size.
- [ ] No accidental scrollbars on the main dashboard unless content truly overflows.
- [ ] Preserve frameless resize, drag, minimize, maximize, and close behavior.
- [x] Add a persistent crash/error banner instead of silent failure when backend, model, or render startup fails.
- [x] Add a lightweight smoke-test script that launches the exe, captures login/setup/dashboard, and checks for non-black pixels.

### P0 Model Foundation

- [x] Desktop model picker must show real `/api/models` inventory.
- [ ] Model records need provider, endpoint, ready state, configured state, capabilities, and last error.
- [x] Add model selection from the desktop app instead of manually typing model names.
- [x] Add provider registry foundation rather than one hard-coded local model.
- [ ] Add provider adapter interface for local, cloud, search, image, video, embeddings, and judge models.
- [ ] Add fallback chain so one bad model does not kill the response.
- [ ] Add per-task routing: chat, code, reasoning, research, vision, creative, embedding, judge, fallback.
- [ ] Add secure API key handling through environment variables or OS credential storage.
- [x] Track model latency, errors, tokens, and cost estimates through planning/model-attempt telemetry.
- [x] Add provider-aware token estimator hooks for OpenAI, Claude, Perplexity, Qwen, DeepSeek, local open-weight, OpenRouter, and local-compatible routes.
- [x] Capture provider-reported token usage from routed attempts and compare it against planning-time token estimates.
- [x] Add backend route-quality rollups for provider reliability, fallback rate, estimated spend, context pressure, and routing recommendations.
- [x] Surface route-quality rollups in native Planning History with reliability, fallback, provider, role, estimator, and recommendation views.
- [x] Surface route-quality context pressure and per-task context drilldowns in native Planning History.
- [x] Add backend fallback/candidate inspector telemetry that links task plans, route candidates, fallback roles, context budgets, model attempts, estimator provenance, and registry resolution.
- [x] Surface fallback/candidate inspection in native Planning History with task summaries, candidate tables, registry status, fallback roles, cost, and estimator provenance.
- [x] Add stable route candidate IDs that persist from planner payloads into model-attempt metadata and native fallback-inspector rows.
- [x] Upgrade native fallback inspection into a selectable task drilldown with all candidates, all attempts, recommendations, context metadata, and candidate/attempt metadata.
- [x] Add capability-aware route matching so providers missing required tools, vision, embeddings, audio, image, video, or realtime support are skipped before execution.
- [x] Add provider preflight checks so disabled providers, missing models, unsupported APIs, and missing API keys are skipped cleanly in fallback-chain telemetry.
- [x] Add structured user feedback telemetry for liked, rejected, copied, applied, rolled-back, regenerated, and corrected outcomes so route quality can learn from real usage.
- [x] Add feedback attribution rollups for provider, model, route role, candidate, task intent, target, and action outcomes in native Planning History.
- [x] Add feedback privacy controls for shared-workspace no-excerpt mode, redaction, excerpt limits, and optional content hashing.
- [x] Add feedback trend buckets and recent feedback event drilldowns to native Planning History.
- [x] Add web route-quality, fallback-inspector, and feedback observability panels.
- [x] Add cached/materialized telemetry snapshots before expanding dashboard windows beyond recent history.
- [x] Add retention/pruning controls for materialized telemetry snapshots.
- [x] Add route-policy diff proposals for provider and role routing changes before applying policy updates.
- [x] Add a checkpointed apply workflow for safe route-policy proposals.
- [x] Add provider tokenizer diagnostics to the backend registry audit and native Model Stack.
- [x] Add route-quality token-calibration rollups to backend telemetry, native Planning History, and web Observability.
- [x] Add route-quality token-calibration trend buckets to backend telemetry, native Planning History, and web Observability.

### P0 Chat Experience

- [x] Add streaming responses in the desktop app.
- [x] Add backend SSE streaming contract and provider adapter stream hooks without breaking normal `/api/chat` responses.
- [x] Wire web and desktop clients to the backend chat stream lifecycle endpoint.
- [x] Stream direct read-only chat answer deltas and replace the live text with the final structured response.
- [x] Stream safe structured-task progress deltas without exposing raw JSON or file-change payloads before final response reconciliation.
- [x] Stream sanitized structured reply previews from provider JSON mode while keeping generated files, command suggestions, and raw provider JSON hidden until final.
- [x] Reset failed provider preview text before later-provider text appears.
- [x] Persist structured preview counters into model-attempt telemetry and show them in route diagnostics.
- [x] Aggregate structured preview reliability into route-quality diagnostics and route-health ranking.
- [x] Show visible working/applying status for create/build prompts.
- [x] Add composer-level Auto Apply and Validate controls.
- [x] Add stop/cancel generation.
- [x] Add retry last message.
- [x] Add regenerate with selected model.
- [ ] Preserve partial response if generation fails.
- [x] Show which model answered each assistant message.
- [x] Save conversations persistently.
- [x] Restore the saved workspace with the latest local conversation.
- [x] Export current conversation to Markdown.
- [x] Add local conversation titles, search, pinning, delete/archive, and a desktop conversation browser.

### P0 Tool Safety

- [ ] Every read, write, command, validation, and creative generation action must be logged as a tool event.
- [ ] Dangerous shell commands require approval.
- [ ] Writes must stay inside the selected workspace.
- [ ] Exclude secrets, `.env`, keys, caches, build artifacts, binaries, logs, and huge files from model context by default.
- [x] Show an obvious warning when sending workspace context to cloud providers.
- [x] Keep checkpoints before file writes.
- [x] Provide rollback from checkpoints.
- [x] Add checkpoint browser with restore point inspection.

### P0 Coding Workflow

- [x] Inline diff view.
- [x] Side-by-side diff view.
- [x] Selective apply by file.
- [x] Selective apply by hunk.
- [x] Validation profile detection and saving.
- [x] Auto-repair loop after validation failure.
- [x] Clear generated/applied file summary for the latest task.
- [x] Auto-apply low-risk file creation when a create/build prompt names an explicit workspace path.
- [x] Copy/export patch.
- [x] Add specialist coding routes for web, mobile, desktop, macOS, Linux, Windows, game tooling, and data work.
- [x] Add high-risk coding guardrails for kernel, driver, firmware, security-sensitive, and destructive system changes.
- [x] Add test-generation and validation suggestions per project type.
- [x] Add a checkpointed New Project Builder with preview mode and deterministic presets for web, API, Python, TypeScript, and C++ starter projects.
- [x] Add prompt-to-project planning that selects a scaffold preset, project name, target folder, install command, and validation command before writing files.
- [x] Auto-route normal chat prompts for new/full/from-scratch projects into Project Builder plan + preview instead of free-form model code.
- [x] Expand Project Builder presets to include Electron desktop, Expo React Native mobile, Django web, and Rust CLI starters.
- [x] Expand Project Builder presets to include Go HTTP API, ASP.NET Core C# Web API, and Tauri React desktop starters.
- [x] Generate `AGENTS.md` and `.aegis/project.json` in every scaffold so future agent passes know the stack, commands, first-pass plan, and safety notes.
- [x] Read `.aegis/project.json` back into backend workspace profiles, validation discovery, and model prompt context.
- [x] Surface workspace profile metadata in the native Workspace tab so users can inspect stack, commands, and handoff state without opening files manually.
- [x] Use workspace profile metadata to suggest route presets, validation defaults, and project-specific quick actions in the composer.
- [x] Infer dependency profiles from common project manifests and feed them into task planning, prompt context, workspace UI, validation suggestions, and verification install steps.
- [x] Use workspace profile metadata in backend task planning and route preview so broad continuation prompts stay stack-aware.
- [x] Add stack route profiles so manifest-backed work can bias planning, route previews, model-attempt metadata, and native route timeline display by project type.
- [x] Add high-coverage coding route profiles for databases, native DLL/EXE work, kernel drivers, firmware-adjacent work, and authorized reverse-engineering analysis.
- [x] Expand validation discovery for native, JVM, SQL/database, and CMake-style projects so syntax/build/test checks are easier to run before repair loops.
- [x] Add a full backend verification pipeline that can chain install, configure, build, type-check, database validation, lint, test, and final validation steps.
- [x] Add native Full Verify controls and result display for the backend verification pipeline.
- [x] Feed the first Full Verify failure into the repair loop with a one-turn validation-command override, then automatically rerun Full Verify after the targeted command passes.
- [x] Add a native verification-repair activity timeline that tracks Full Verify start/completion, targeted repair, command pass/fail, and automatic reruns.
- [x] Add copyable Full Verify reports with workspace, first failure, pipeline steps, warnings, and repair activity.
- [x] Add Markdown file export and reports-folder access for Full Verify reports from the panel and command palette.
- [x] Add an in-panel recent verification report browser with open/copy actions for exported Markdown reports.
- [x] Add attach-latest verification report support so exported diagnostics can be sent back into the next repair prompt as explicit context.
- [x] Add verification report pruning/retention controls so long-running coding sessions do not accumulate stale reports forever.
- [x] Add controlled multi-step Full Verify repair chaining with an auto-repair toggle, repair-pass limit, stop control, activity tracking, and command-palette entry.

### P0 Creative Workflow

- [x] Add backend support for image, video package, animation, GIF, and PSD template packages.
- [x] Add backend support for music/beat package generation.
- [x] Add backend support for video editing package generation.
- [x] Desktop job browser for generated image/video/GIF/animation/PSD packages.
- [x] Asset preview strip inside the desktop app for generated Creative Studio packages.
- [x] Real raster thumbnails inside the desktop app through a DirectX/WIC texture loader.
- [x] Revise-last flow wired to the previous media job.
- [x] Theme/palette display and copy controls.
- [x] In-app beat/audio preview playback for Creative Studio audio assets.
- [x] Theme/palette edit controls before generation.
- [x] Aspect ratio, duration, FPS, size, and output format controls.
- [x] Asset opening/copy buttons.
- [x] Asset export buttons.
- [ ] Provider registry for real image and video model adapters.
- [ ] Provider registry for real music/audio, speech, and stem model adapters.
- [ ] Local render pipeline for GIF, HTML animation, SVG, template previews, and packaged Photoshop scripts.
- [ ] Revision engine that can modify a previous creative package without restarting when only color, pacing, text, or arrangement changes.
- [ ] Theme inference that assumes a good palette when the user does not specify one.

### P0 Learning And Knowledge

- [x] Persistent user preference memory with visible edit/delete controls.
- [x] Project knowledge base that grows from chats, files, fixes, generated assets, and user feedback.
- [x] Feedback capture on assistant answers.
- [x] Feedback capture on code changes and creative jobs.
- [ ] Evaluation runner that tests core skills before releases.
- [ ] Research mode with source tracking, citation display, and freshness warnings.
- [ ] Education mode with study plans, quizzes, flashcards, and step-by-step tutoring.
- [ ] Memory privacy controls for local-only, project-only, and cloud-allowed modes.

## Improvements Needed

### Desktop UX

- [x] Add model stack modal with inventory, capabilities, and routing status.
- [x] Add project roadmap modal with the current build queue.
- [x] Add command palette for common actions.
- [x] Add keyboard shortcuts for send, new chat, command palette/search, settings, regenerate, and validation-oriented workflows.
- [x] Add stop/cancel generation before assigning a true stop shortcut.
- [x] Add real file attachment workflow before assigning an attach shortcut.
- [x] Add composer-level Auto Apply and Validate toggles.
- [ ] Add compact/mobile-ish layout for narrow windows.
- [x] Add first-run setup that checks backend path, venv, model server, and workspace.
- [x] Add status toasts for saved settings, model failures, backend startup, media job completion, and validation.
- [x] Add copy buttons that actually copy assistant message text to clipboard.
- [x] Add copy buttons for file paths and commands.
- [ ] Add drag-and-drop file attachment.
- [x] Add open file/folder buttons for generated assets and workspace paths.

### Visual Polish

- [ ] Match `goal.png` colors and spacing as the base dashboard theme.
- [ ] Keep red accent usage intentional: active nav, primary actions, composer, online status, progress.
- [ ] Avoid green borders around every card.
- [ ] Make all card heights stable so labels and animations cannot create scrollbars.
- [ ] Add hover, press, disabled, loading, and selected states for every custom widget.
- [ ] Add consistent icon sizing and alignment.
- [ ] Add text clipping/wrapping helpers for long model names, paths, and task titles.
- [ ] Add modal polish: dim backdrop, consistent headers, footer actions, and scroll behavior.

### Backend

- [x] Turn current model inventory into a real model registry foundation.
- [x] Add CRUD endpoints for model registry entries.
- [ ] Add model health checks and periodic refresh.
- [x] Add streaming API endpoint.
- [ ] Add cancellation tokens or task cancellation endpoint.
- [ ] Add conversation CRUD endpoints.
- [x] Add media job list/detail endpoints.
- [x] Add validation profile endpoint to desktop client.
- [x] Add checkpoint browser endpoint.
- [x] Add full verification endpoint for ordered multi-step build/test pipelines.
- [ ] Add provider-specific rate limit and quota handling.
- [ ] Add better structured error envelopes.

### Memory And Context

- [ ] Hybrid retrieval: keyword plus vector embeddings.
- [ ] Workspace map summary.
- [ ] Dependency graph hints.
- [ ] Recent-change awareness.
- [x] User preference memory.
- [x] Project decision memory.
- [ ] Fix/error memory with confidence.
- [x] Context preview panel showing files and memories being sent.
- [x] Token budget planner.
- [x] Desktop pre-send secret and prompt-injection scan for visible composer, attachment, workspace, and previous context signals.
- [ ] Full prompt-injection guardrails for files, web pages, and tool outputs.

### Validation And Evals

- [ ] Golden test set for coding tasks.
- [ ] JSON schema compliance tests.
- [ ] Diff correctness tests.
- [ ] Tool selection tests.
- [ ] Workspace safety tests.
- [ ] Multi-model comparison runner.
- [ ] Desktop UI screenshot regression checks.
- [x] Basic desktop smoke captures for login, setup, and dashboard.
- [ ] Backend endpoint smoke tests.
- [ ] Creative output manifest tests.

### Distribution

- [ ] Installer or portable release package.
- [ ] Version stamp in UI and exe metadata.
- [ ] Release notes.
- [ ] Git repository initialized for ChatBot with a configured GitHub remote.
- [ ] Push every verified desktop-app change after build and smoke tests pass.
- [ ] Branch naming convention for feature work, fixes, and release candidates.
- [ ] PR template with summary, validation, screenshots, and rollback notes.
- [ ] GitHub Actions CI for desktop build, backend tests, and smoke screenshots.
- [ ] Artifact upload for Release exe, config, logs, and smoke captures.
- [ ] Auto-update plan.
- [ ] Local logs folder with "Open Logs" button.
- [ ] Diagnostics bundle export.
- [ ] Signed executable when ready.

## Suggestions To Make It Feel Like The Next Best Thing

### Multi-Model Strategy

- [ ] Do not compete only on "number of models"; compete on routing, speed, reliability, and UX.
- [ ] Add a router that chooses models by task type.
- [ ] Add specialist roles: fast chat, deep reasoning, coding, code review, web research, vision, image, video, embeddings, judge.
- [ ] Add fallback models for every role.
- [ ] Add model comparison mode: ask 2-4 models, then synthesize.
- [ ] Add judge mode to critique outputs before showing final answer.
- [ ] Add "cheap/fast/balanced/best" routing presets.
- [ ] Add privacy presets: local-only, hybrid, cloud-allowed.

### Creative Studio

- [ ] Image generation with provider adapters and local editable fallbacks.
- [ ] Video generation with storyboards, provider adapters, and export packages.
- [ ] Video editing assistant with edit decision lists, captions, pacing, transitions, sound design, and export targets.
- [ ] Music/beat generator with BPM/key inference, arrangement JSON, WAV preview, MIDI/stem plans, and revision notes.
- [ ] Brand kit generator.
- [ ] Thumbnail generator.
- [ ] Ad creative generator with variants.
- [ ] Product mockup generator.
- [ ] Icon set generator.
- [ ] Sticker/transparent asset generator.
- [ ] Lottie JSON export.
- [ ] Sprite sheet export.
- [ ] MP4/WebM render through ffmpeg.
- [ ] Photoshop JSX plus layered asset package.
- [ ] Before/after revision viewer.
- [ ] Branchable creative directions.
- [ ] Creative critique mode that checks composition, readability, color, and export readiness before delivery.

### Research, Knowledge, And Education

- [ ] Research mode that tracks sources, dates, and freshness warnings.
- [ ] Source card UI with title, URL/path, author/publisher, publish date, retrieval date, and confidence.
- [ ] Citation-aware summaries for web, PDFs, documents, codebases, and generated reports.
- [ ] General knowledge mode with model self-checking and uncertainty labels.
- [ ] Education mode with tutoring, study plans, quizzes, flashcards, drills, and progress tracking.
- [ ] Lesson builder that converts files, chats, or projects into step-by-step learning paths.
- [ ] Knowledge import pipeline for docs, PDFs, repos, notes, generated assets, and previous task history.
- [ ] Knowledge decay and refresh reminders for facts likely to become outdated.

### Training And Continuous Learning

- [ ] Preference memory with visible add/edit/delete controls.
- [ ] Project memory with explicit approvals before storing durable rules.
- [ ] Feedback scoring for liked, rejected, revised, copied, exported, applied, and rolled-back outputs.
- [ ] Revision memory that learns what changed between first draft and accepted result.
- [ ] Eval suites for chat, coding, creative, research, education, and safety workflows.
- [ ] Model benchmark dashboard comparing quality, speed, cost, context length, reliability, and privacy posture.
- [x] Guarded route-policy apply path so better settings can be promoted safely.
- [ ] Prompt and router experiment tracker for named experiments, cohorts, and rollback notes.
- [ ] Local training data export bundle with privacy filters and provenance metadata.

### Privacy, Safety, And Governance

- [ ] Local-only, hybrid, and cloud-allowed privacy modes.
- [ ] Per-provider consent prompts before sending workspace files, memories, or generated assets to cloud APIs.
- [ ] Secret scanner for `.env`, API keys, certificates, SSH keys, tokens, browser cookies, and private configs.
- [x] Pre-send secret scanner for composer text, attachments, workspace file paths, and last response context paths.
- [x] Pre-send prompt-injection scanner for composer text and attached file contents.
- [ ] Prompt-injection scanner for full workspace files, websites, PDFs, copied text, and tool output.
- [ ] Tool-event ledger for file reads, writes, commands, web calls, generation jobs, exports, and memory writes.
- [ ] Approval policy editor for dangerous commands, destructive file operations, external uploads, and paid model calls.
- [ ] Cost and quota guardrails with per-provider daily/monthly limits.
- [ ] Diagnostics report that redacts secrets before export.

### Platform And Runtime Reach

- [ ] Native Windows packaging first, then portable ZIP.
- [ ] macOS app plan with native packaging, notarization, and platform-specific path handling.
- [ ] Linux AppImage/deb/rpm plan with GPU/runtime checks.
- [ ] Cross-platform backend launcher with venv detection and repair.
- [ ] Plugin architecture for providers, tools, local renderers, validators, and project templates.
- [ ] Offline mode with local models, local docs, local memory, and queued cloud jobs.
- [ ] GPU/runtime diagnostics for Ollama, CUDA, DirectML, ffmpeg, ImageMagick, Photoshop scripts, and audio tools.

### Coding Agent

- [ ] Agent workspace planner.
- [ ] File tree relevance panel.
- [ ] "Explain this change" button.
- [ ] "Generate tests" button.
- [x] "Fix validation" button.
- [x] "Rollback last apply" button.
- [x] "Open changed file" buttons.
- [ ] "Commit summary" generator.
- [ ] PR description generator.
- [x] Platform presets for web, mobile, desktop, macOS, Linux, Windows, and kernel/system work.
- [ ] Dependency-aware coding plans that understand project layout and validation commands.

### Personal Assistant

- [ ] User profile and preferences.
- [ ] Tone/style presets.
- [ ] Saved prompt templates.
- [ ] Reusable workflows.
- [ ] Local calendar/tasks later if desired.
- [ ] Voice input/output later if desired.

### Learning Engine

- [x] Feedback loop that records liked, disliked, and copied assistant responses.
- [x] Feedback loop that records liked/rejected code changes and creative outputs.
- [ ] Feedback loop that records successful revisions as a separate learning signal.
- [ ] Skill cards for repeatable tasks: coding, creative, research, education, music, and operations.
- [ ] Model eval dashboard comparing quality, speed, cost, and reliability.
- [ ] Knowledge import pipeline for documents, repos, generated assets, and saved notes.
- [ ] "Teach Aegis" panel where the user can add rules, preferences, and project facts.

## Execution Sprints

### Sprint 1: Desktop Trust And Model Visibility

- [x] Fix black-window render target startup.
- [x] Fix ImGui cursor assertion.
- [x] Center login with real host window sizing.
- [x] Clean dashboard scrollbars and accidental green borders.
- [x] Create master project TODO.
- [x] Wire `/api/models` into desktop model picker.
- [x] Add model stack modal.
- [x] Add roadmap/build queue modal.
- [x] Add screenshot smoke check script.
- [x] Add first-run setup diagnostics for backend path, venv/start script, model server, workspace, and validation readiness.

### Sprint 2: Conversation And Streaming

- [x] Backend streaming endpoint.
- [x] Desktop streaming renderer.
- [x] Stop/cancel button.
- [x] Persistent conversation storage.
- [ ] Conversation list/detail endpoints.
- [x] Desktop conversation browser.

### Sprint 3: Model Router

- [x] Registry storage.
- [x] Registry API.
- [x] Desktop model selection from live inventory.
- [x] Desktop registry editor.
- [ ] Provider adapter interface.
- [ ] Local Ollama adapter as first registry provider.
- [ ] OpenAI-compatible adapter as second provider.
- [ ] Routing policy config.
- [ ] Fallback chain.

### Sprint 4: Creative Studio UI

- [x] Music/beat backend package writer.
- [x] Video-edit backend package writer.
- [x] Media job list endpoint.
- [x] Media job detail endpoint.
- [x] Desktop creative browser.
- [x] Asset preview strip.
- [x] Real raster thumbnails.
- [x] Beat/audio playback controls.
- [x] Feedback/revise UI.
- [x] Open/copy generated asset paths.
- [x] Export generated assets from desktop.

### Sprint 5: Coding Workflow Upgrade

- [x] Diff viewer.
- [x] Selective apply.
- [x] Validation profile UI.
- [x] Copy/export patch.
- [x] Checkpoint browser.
- [x] Rollback.
- [x] Repair loop UI.

## Immediate Next Moves

1. Add adapter health summaries to the Model Stack and fallback inspector using provider preflight telemetry.
2. Add dependency-aware coding plans per project type.
3. Connect routing presets to actual task routing, fallback, and provider consent.
4. Expand smoke checks from login/loading/dashboard into model stack, build queue, Context Preview, Creative Studio, validation profile UI, coding routes, and feedback buttons.
5. Add desktop smoke coverage for Full Verify and verification-result rendering.
6. Add verification-result snapshots that can be replayed in the desktop UI without rerunning commands.
