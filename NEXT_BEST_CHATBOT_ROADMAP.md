# Aegis Desktop ChatBot Roadmap

Last updated: 2026-04-27

This is the working plan for turning the desktop Aegis ChatBot into a modern, model-flexible assistant instead of a single-model local chat window.

The important framing: competing on "number of models" is not enough. Claude, Perplexity, OpenRouter, and similar products are really competing on routing, fallbacks, tools, context, memory, reliability, and UX. Aegis should do the same.

## Current Inventory

### Desktop App

- Native C++ Win32 / DirectX 11 / Dear ImGui app.
- Lives at `Tools/04 Runtime & Engine Tools/ChatBot`.
- Talks directly to the FastAPI backend at `http://127.0.0.1:8787`.
- Auto-starts the backend from `Website/ChatBot`.
- Current UI supports:
  - Build, Develop, Review, and Chat modes.
  - Workspace file listing.
  - Text-file preview.
  - Chat history in the current session.
  - Response, Changes, Files, Events, and Settings tabs.
  - Preview-first generated file changes.
  - Apply all generated changes.
  - Run validation.
  - Backend/model status pills.
  - Desktop settings and backend settings.

### Backend

- FastAPI app in `Website/ChatBot/backend/aegis_ai`.
- App version: `0.3.0`.
- Current API surface includes:
  - `/api/health`
  - `/api/config`
  - `/api/chat`
  - `/api/files`
  - `/api/file`
  - `/api/apply`
  - `/api/validate`
  - `/api/history`
  - `/api/memory`
  - `/api/approval/settings`
  - `/api/index/rebuild`
  - `/api/index/search`
  - `/api/diff/compare`
  - `/api/diff/apply`
  - `/api/diff/summarize`
- Existing backend strengths:
  - Local workspace guardrails.
  - Checkpoints before file changes.
  - SQLite task/event/history storage.
  - Command allowlist and timeout.
  - Memory manager.
  - Project indexing.
  - Diff engine.
  - Approval and sandbox settings.
  - Deterministic fallback engine when the model is offline.

### Current Model Setup

Live check on 2026-04-27:

- Backend is reachable.
- Ollama is running.
- Active API: `ollama`.
- Active endpoint: `http://127.0.0.1:11434`.
- Active model: `qwen2.5-coder:7b`.
- Model status: ready.
- `ollama list` currently shows one model: `qwen2.5-coder:7b`.

Current model support in code:

- One configured model at a time.
- Two API modes:
  - `ollama`
  - `openai` compatible local endpoint
- No model registry.
- No cloud provider adapters.
- No automatic fallback chain.
- No per-task model routing.
- No model picker beyond typing settings manually.
- No streaming responses in the desktop app.
- No token, cost, latency, or quality tracking.

## What We Absolutely Need

These are the non-negotiables before the chatbot can credibly feel like a next-generation assistant.

### 1. Model Provider Gateway

Build a real model layer instead of one hard-coded local model.

Required pieces:

- A model registry.
- Provider abstraction.
- Provider health checks.
- Model capability metadata.
- Fallback chains.
- Manual model override.
- Per-task routing policy.
- Secure API key handling.
- Token, cost, latency, and error telemetry.

Model registry fields:

- Internal model id.
- Display name.
- Provider.
- Provider model slug.
- Endpoint.
- API key environment variable name.
- Local or cloud.
- Enabled or disabled.
- Default role: chat, code, reasoning, search, vision, audio, image, embedding, judge, fallback.
- Supports streaming.
- Supports structured JSON.
- Supports tool/function calling.
- Supports vision.
- Supports audio.
- Supports computer use.
- Supports embeddings.
- Context window.
- Max output tokens.
- Input price.
- Output price.
- Rate limits.
- Last health check.
- Last failure.

Minimum adapter order:

1. Existing Ollama adapter.
2. Existing OpenAI-compatible adapter.
3. Direct OpenAI adapter.
4. Direct Anthropic adapter.
5. Direct Gemini adapter.
6. Direct Perplexity adapter for search/research.
7. Optional LiteLLM gateway adapter for broad provider coverage.
8. Optional OpenRouter adapter for broad third-party model access.

### 2. Streaming, Cancellation, and Recovery

The app needs to feel alive while the model works.

Required pieces:

- Streaming chat responses from backend to desktop.
- Stop/cancel button.
- Retry last response.
- Regenerate with another model.
- Continue generation if output is cut off.
- Clear error states with useful recovery actions.
- Preserve partial responses after failure.

### 3. Real Conversation System

The current session history is useful, but not enough.

Required pieces:

- Persistent conversations.
- Conversation titles.
- Search conversations.
- Fork/branch from any message.
- Pin important chats.
- Export conversation.
- Attach workspace, model, and mode metadata to every message.
- Show which model answered each message.
- Store tool calls and file changes as first-class message events.

### 4. Context Engine

Aegis needs to be excellent at knowing what to include.

Required pieces:

- Workspace map.
- Ignore rules for build artifacts, secrets, caches, logs, binaries, and large files.
- File relevance retrieval.
- Embedding index or hybrid keyword/vector retrieval.
- Dependency graph hints.
- Recent-change awareness.
- Open-file/current-focus awareness.
- Project memory.
- User memory.
- Prompt budget manager.
- Context preview panel so the user can see what Aegis is sending.

### 5. Tool and Action System

The chatbot must be able to do useful work safely.

Required tools:

- Read file.
- Write file through preview/apply.
- Generate patch.
- Apply patch.
- Search project.
- Run approved command.
- Validate workspace.
- Save memory.
- Retrieve memory.
- Inspect logs.
- Open generated files.

Important safety requirements:

- Every tool call should be logged.
- Dangerous commands require approval.
- Workspace writes must stay inside the selected workspace.
- Cloud providers should not receive secrets or excluded files.
- Prompt-injection warnings for web/file/tool content.
- Rollback/checkpoint before file writes.

### 6. Diff, Patch, and Apply Workflow

This is already started. It needs to become the center of coding mode.

Required pieces:

- Inline unified diff view.
- Side-by-side diff view.
- Selective apply by file.
- Selective apply by hunk.
- File create/update/delete badges.
- Checkpoint browser.
- Rollback button.
- Validation after apply.
- Repair loop after failed validation.
- Summary of changed files.
- Copy patch/export patch.

### 7. Validation and Evals

Modern model products win by measuring quality continuously.

Required app validation:

- Detect project type.
- Suggest validation command.
- Let user save validation profile.
- Run validation after apply.
- Store stdout/stderr.
- Categorize failures.
- Feed failures back into repair attempts.

Required model evals:

- Small golden task set for Aegis coding workflows.
- Instruction-following tests.
- JSON schema compliance tests.
- Tool-selection tests.
- Diff correctness tests.
- Workspace safety tests.
- Multi-model comparison runner.
- Regression report after changing prompts, routing, or models.

### 8. Observability

We need to know what happened, not guess.

Required pieces:

- Model used.
- Provider used.
- Fallbacks attempted.
- Prompt tokens.
- Output tokens.
- Total cost estimate.
- Latency.
- Time to first token.
- Tool calls.
- Tool failures.
- Validation result.
- User satisfaction signal.
- Error traces.

Useful UI:

- Model activity timeline.
- Cost/latency panel.
- Recent failures.
- Model health dashboard.
- "Why this model?" explanation for routed requests.

### 9. Security and Privacy

This needs to be designed in from the start.

Required pieces:

- API keys stored outside project files.
- Secret redaction before logs and cloud calls.
- Workspace boundary enforcement.
- File allow/deny lists.
- Configurable cloud/offline mode.
- Network access policy.
- Prompt-injection handling.
- Audit log for commands and file writes.
- Clear warning when a request will leave the machine.

### 10. Desktop UX

The desktop app should become the serious daily driver.

Required pieces:

- Model picker with grouped providers.
- Model health badges.
- Streaming message area.
- Stop/retry/regenerate controls.
- Conversation sidebar.
- Better file tree.
- Better diff viewer.
- Tool timeline.
- Memory panel.
- Approval panel.
- Provider settings panel.
- Validation panel.
- Clear onboarding for local model setup.

### 11. Packaging and Reliability

Required pieces:

- One launcher for desktop, backend, and model server checks.
- Clear service status.
- Log viewer.
- Dependency checks.
- Repair button for missing backend dependencies.
- Desktop build script that verifies output.
- Version number shown in the app.
- Portable config migration.
- Crash-safe writes.

### 12. Tests

Required tests:

- Backend unit tests.
- Backend API tests.
- Model adapter tests with mocked provider responses.
- Router fallback tests.
- JSON extraction tests.
- Workspace safety tests.
- Diff/apply tests.
- Desktop compile check.
- Smoke test for `/api/health`, `/api/config`, and `/api/chat`.

## Model Strategy

Do not chase "30 models" as a vanity metric. Use model roles.

### Recommended Roles

- Local default: private, offline, cheap, fast enough.
- Fast cloud: low-cost everyday chat and small edits.
- Frontier reasoning: hard planning, architecture, bug hunts, long tasks.
- Coding specialist: repo edits, refactors, code review.
- Search/research model: web-grounded answers with citations.
- Vision model: screenshots, diagrams, image understanding.
- Audio/realtime model: voice assistant mode.
- Embedding model: local/project retrieval.
- Judge model: evals, answer grading, patch review.
- Fallback model: reliability when the preferred model fails.

### Practical Initial Lineup

Current local:

- `qwen2.5-coder:7b` through Ollama.

Next local candidates:

- A stronger local coder model that fits the machine.
- A small fast chat model for cheap everyday responses.
- A local embedding model for retrieval.
- Optional OpenAI-compatible local server support through Ollama, llama.cpp, vLLM, or SGLang.

Cloud candidates to support through adapters:

- OpenAI current frontier/coding models.
- Anthropic Claude Sonnet/Opus family.
- Google Gemini 3/2.5 family.
- Perplexity Sonar and Agent API models for research/search.
- OpenRouter or LiteLLM for broad provider coverage if we want many models quickly.

### Routing Examples

Default chat:

1. Local fast model.
2. Cloud fast model if local confidence is low or user allows cloud.
3. Frontier model if task is hard.

Coding task:

1. Local coder for draft.
2. Frontier coder for review or repair.
3. Judge model for final patch sanity check.

Research task:

1. Perplexity or a web-grounded model.
2. Frontier model for synthesis.
3. Local model for final formatting if privacy matters.

Validation repair:

1. Original model attempts repair.
2. Different model reviews failure.
3. Router picks the cheapest model that passes the eval threshold.

## Additional Suggestions

These are the features that can make Aegis feel genuinely ahead, not just caught up.

### A. Auto Router

Add a "Best available" model option.

It should choose based on:

- User mode.
- Task difficulty.
- Required tools.
- Needed context length.
- Local/cloud privacy setting.
- Latency target.
- Cost budget.
- Recent provider failures.
- Eval scores.

### B. Multi-Model Compare

Let the user ask one question and compare two or three model answers.

Good for:

- Planning.
- Code review.
- Debugging.
- Research.
- High-stakes decisions.

### C. Consensus Mode

For important tasks, have:

1. Primary model draft.
2. Critic model review.
3. Primary model revise.
4. Judge model score.

### D. Deep Research Mode

Add a mode that:

- Searches the web.
- Tracks sources.
- Summarizes source quality.
- Separates facts from guesses.
- Produces citations.
- Saves useful findings to memory.

### E. Agent Workspace Mode

Make coding mode feel like an IDE assistant:

- File tree.
- Open tabs.
- Diff viewer.
- Terminal output.
- Task plan.
- Tool events.
- Validation status.
- Apply/rollback controls.

### F. Voice and Realtime Mode

Add optional voice:

- Push-to-talk.
- Read responses aloud.
- Realtime interruption.
- Meeting-style notes.
- Voice command shortcuts.

### G. Image and Screen Understanding

Add:

- Screenshot upload.
- Screenshot-to-task.
- UI bug explanation.
- Diagram explanation.
- Image generation only when useful.

### H. Personal Memory

Memory should become first-class:

- User preferences.
- Project conventions.
- Repeated fixes.
- Architecture notes.
- "Never do this again" notes.
- Editable memory with confidence and source.

### I. Skills and Plugins

Add a plugin/skill interface for:

- Coding stacks.
- Document workflows.
- Spreadsheets.
- Presentations.
- Browser automation.
- Business-specific workflows.

### J. Model Bench/Arena

Add a local benchmark screen:

- Run same prompt across selected models.
- Compare latency.
- Compare cost.
- Compare JSON validity.
- Compare patch validity.
- Save winner to routing policy.

## First Implementation Tickets

Start here.

### Ticket 1: Backend Model Registry

Status: first inventory slice started. The backend now has a `/api/models` endpoint that reports the active local model, discovered models from the configured local server, and basic model capabilities. Next step is turning this into a persistent registry with multiple providers and routing policy.

Add:

- `ModelProvider`
- `ModelDefinition`
- `ModelCapability`
- `ModelHealth`
- `ModelUsage`
- Persistent config for enabled models.

Expose:

- `GET /api/models`
- `POST /api/models/test`
- `PUT /api/models/default`

### Ticket 2: Model Router

Add:

- `ModelRouter`
- Routing policy.
- Fallback chain.
- Provider error normalization.
- Latency and usage logging.

Keep the existing Ollama/OpenAI-compatible client working as the first adapter.

### Ticket 3: Desktop Model Panel

Add UI for:

- Available models.
- Active default model.
- Provider health.
- Test model button.
- "Best available" toggle.
- Cloud permission toggle.

### Ticket 4: Streaming Chat

Add:

- Backend streaming endpoint.
- Desktop streaming reader.
- Stop button.
- Partial response preservation.

### Ticket 5: Eval Harness

Add:

- `backend/evals`.
- Golden prompts.
- Expected schema checks.
- Router comparison report.
- Command to run evals.

### Ticket 6: Better Diff UI

Add:

- File-level selective apply.
- Hunk-level selective apply later.
- Side-by-side preview later.

## What Not To Do

- Do not add 30 model names as hard-coded dropdown text and call it done.
- Do not send workspace files to cloud providers without a visible privacy control.
- Do not store API keys in source files.
- Do not let the model execute arbitrary shell commands without approval and logging.
- Do not skip evals. Without evals, routing becomes vibes.
- Do not make the desktop app depend on a browser UI.

## Research Notes

Official docs checked on 2026-04-27:

- Perplexity Agent API supports presets, direct model selection, and fallback chains: https://docs.perplexity.ai/docs/agent-api/models
- Perplexity model list endpoint uses OpenAI-style model objects for Agent API models: https://docs.perplexity.ai/api-reference/models-get
- Anthropic announced Claude Sonnet 4.6 as available on Claude plans, Claude Code, API, and major cloud platforms: https://www.anthropic.com/research/claude-sonnet-4-6
- OpenAI model docs list modern frontier models, tool support, context windows, and specialized models: https://platform.openai.com/docs/models
- Google Gemini docs list Gemini 3.1, Gemini 2.5, media, audio, and tool/agent models: https://ai.google.dev/gemini-api/docs/models
- LiteLLM provides a unified interface across many providers, retry/fallback routing, spend tracking, and proxy mode: https://docs.litellm.ai/
- Ollama supports OpenAI-compatible APIs including Responses API support in newer versions: https://docs.ollama.com/api/openai-compatibility
