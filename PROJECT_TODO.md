# Aegis ChatBot Master TODO

Last updated: 2026-04-27

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
- [ ] Track model latency, errors, tokens, and cost estimates.

### P0 Chat Experience

- [ ] Add streaming responses in the desktop app.
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
- [ ] Keep green accent usage intentional: active nav, primary actions, composer, online status, progress.
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
- [ ] Add streaming API endpoint.
- [ ] Add cancellation tokens or task cancellation endpoint.
- [ ] Add conversation CRUD endpoints.
- [x] Add media job list/detail endpoints.
- [x] Add validation profile endpoint to desktop client.
- [x] Add checkpoint browser endpoint.
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
- [ ] Prompt and router experiment tracker so better settings can be promoted safely.
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

- [ ] Backend streaming endpoint.
- [ ] Desktop streaming renderer.
- [ ] Stop/cancel button.
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

1. Add provider adapter interface for local, cloud, search, image, video, embeddings, audio, and judge models.
2. Add dependency-aware coding plans per project type.
3. Add memory controls for user preferences and project facts.
4. Connect routing presets to actual task routing, fallback, and provider consent.
5. Add source/citation cards for research and education mode.
6. Expand smoke checks from login/loading/dashboard into model stack, build queue, Context Preview, Creative Studio, validation profile UI, coding routes, and feedback buttons.
