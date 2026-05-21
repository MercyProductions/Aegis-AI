# Dogfooding Notes

Last updated: 2026-05-18

Phase: Daily Dogfooding and Long-Term Workflow Refinement

Target stability release: next small stabilization release

Automation: `auralith-dogfooding-follow-up` now runs as a weekly workflow refinement review.

## Goal

Use the consolidated Auralith/Aegis ecosystem on real projects before adding more features. The daily loop should prove whether Aegis Core, the Website backend, Desktop, VS Code, and Visual Studio are reliable enough for ordinary work.

The rule for this phase is simple: fix high-impact friction found during real use, and avoid imagined features.

## Daily Stack

- Aegis Core `/v1`: `http://127.0.0.1:8788`
- Website backend `/api`: `http://127.0.0.1:8787`
- Website frontend: `http://127.0.0.1:5173`
- Desktop App: `AegisChatBotDesktop.sln`
- VS Code extension: `vscode-plugins/aegis-local-autopilot`
- Visual Studio extension: `visual-studio-extensions/aegis-local-agent-vs`
- Ollama: `http://127.0.0.1:11434`

## Target Projects

| Project | Path | Status | Notes |
| --- | --- | --- | --- |
| Aegis ChatBot | `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot` | Active | Primary dogfooding workspace. |
| ECHO//VEIL Unity project | `C:\Users\gabri\Desktop\Placeholder Name\My project` | Started | Day 1 Core scan recognized Unity/C# and ignored generated Unity/build folders. |
| Website project | `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot\website` | Active | Mature `/api` layer remains the web product layer. Day 1 smoke passed. |
| C++ desktop project | `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot\AegisChatBotDesktop.sln` | Active | Desktop smoke is the current automated coverage. |
| Broken/unfinished project | Pending selection | Not started | Needs a deliberately failing real project for repair and rollback practice. |

## Daily Checklist

- [x] Start Aegis Core.
- [x] Open Desktop App.
- [x] Open VS Code extension.
- [ ] Open Visual Studio extension in the GUI.
- [x] Generate roadmap.
- [x] Continue from roadmap.
- [x] Fix one real issue if daily use exposes a high-impact problem.
- [x] Validate build/tests.
- [x] Roll back at least one test change.
- [x] Record friction.

## Friction Categories

Track concrete examples of:

- Crashes
- Slow workflows
- Confusing UX
- Bad suggestions
- Broken sync
- Bad roadmap items
- Validation failures
- Rollback failures
- Extension bugs
- Missing docs
- Setup pain points

## Weekly Review - 2026-05-18

Scope:

- Reviewed the human workflow notes plus generated local dogfooding state under `.aegis`.
- Current generated dogfooding sample is still small: 2 events, production confidence `60`, status `needs_attention`.
- The only measured generated pain point is `validation_pain`; the broader workflow notes repeatedly point to startup probes, validation clarity, rollback trust, command/package drift guards, and maintainability as the main stabilization themes.

Repeated friction observed:

| Area | Current evidence | Decision |
| --- | --- | --- |
| Startup speed and clarity | Prior Core and Website launch hardening focused on wrong-service ports, missing timeouts, and ambiguous readiness failures. | Keep measuring individual Core, Website, Ollama, and client startup steps; avoid architecture changes until a timed bottleneck repeats. |
| Indexing speed | `.aegis/scan-cache.json`, file index, symbol index, and dependency graph are present; no new slow-index event was recorded in the latest sample. | Keep incremental indexing as the active approach; record explicit `indexing_slow` events before optimizing further. |
| Roadmap usefulness | Core roadmap generation works, but notes still require roadmap items to stay tied to scan evidence, validation state, and small safe tasks. | Treat vague roadmap output as `roadmap_unhelpful` friction in future dogfooding events. |
| Diff readability | VS Code destination reasoning improved trust, but repeated approval confidence depends on file-purpose grouping and path explanations. | Keep the “Why Aegis chose these files” panel as the current baseline; record unclear approvals as `diff_unclear` or `unclear_approval`. |
| Validation clarity | Latest generated report flags `validation_pain`; earlier notes repeatedly hardened validation route names, timeouts, URL propagation, and command allowlists. | Prioritize remembered safe validation commands and concise failure summaries before expanding repair behavior. |
| Rollback confidence | Rollback tests passed in Website and VS Code flows; confidence still depends on visible checkpoint names, affected files, and restore outcome. | No code change today; keep rollback in every release gate. |
| Diagnostics and error messages | Startup and validation fixes show ambiguous errors are a real source of wasted time. | Added dogfooding tags for `diagnostics_unclear` and `error_message_unclear` so future notes can be categorized directly. |
| Onboarding | First-run and setup friction remain important but no fresh blocking event was recorded. | Added `onboarding_friction` as a dogfooding category; defer UI changes until a concrete path repeats. |
| Maintainability | Stabilization summary still lists large client/backend modules, especially Desktop, Website `App.tsx`, and VS Code `extension.js`. | Added `maintainability_drag` as a dogfooding category; prefer module extraction plus parity guards over broad rewrites. |

Small fix shipped:

- Extended Aegis Core dogfooding friction taxonomy so weekly reviews can record startup, roadmap, diff, diagnostics, error-message, onboarding, and maintainability friction without forcing those signals into generic categories.

Validation:

- `python -m pytest tests/test_dogfooding.py`: passed, 7 tests.

Release note:

- A small stable release note is warranted if this taxonomy change ships with the current stabilization batch because it improves workflow evidence quality without changing user-facing autonomy or safety behavior.

## Day 1 - 2026-05-09

### Scope

Started with the Aegis ChatBot workspace because it exercises the full consolidated system and has recent release-candidate validation evidence.

Daily follow-up automation was created so this phase continues across several days instead of becoming a one-time validation pass.

### Startup And Client Checks

- Aegis Core `/v1/health`: passed. Core reported `ok: true`, `api_version: v1`, `contract_version: 2026.05.09`, and Ollama reachable.
- Website backend `/api/health`: passed. Backend reported `status: ready`, `model_ready: true`, and `core_runtime_status: connected`.
- Website frontend: passed with `curl.exe -I http://127.0.0.1:5173` returning HTTP `200`.
- Ollama: passed. Local model inventory was reachable and included the configured coder models.
- Desktop App: passed. `.\build.ps1 -Smoke` built `AegisChatBotDesktop.exe`, checked backend readiness before/after launch, and captured nonblank login/setup/dashboard screenshots.
- VS Code extension: passed basic daily check. `code --reuse-window .` opened the workspace and installed extension id `aegis.aegis-local-autopilot` was present.
- Visual Studio extension: package/build passed; installed manifests were detected. Visual Studio `17.0_278075b6` has Aegis Local Agent `0.1.1`; Visual Studio `18.0_9b14bbb8` has Aegis Local Agent `0.3.0`. Full GUI tool-window dogfooding is still open.

### Roadmap / Continue / Validation / Rollback

- ChatBot Core scan: passed. `/v1/workspaces/scan` indexed 441 files, detected `C#/.NET`, `C++/MSBuild`, `CMake`, `Python`, and `Visual Studio Solution`, and hit the scan cache on repeat.
- ChatBot Core roadmap: passed. `/v1/workspaces/roadmap` wrote `.aegis/roadmap.md` and returned 2 roadmap tasks.
- ChatBot Core continue: passed. `/v1/agent/continue` created shared task `task-9493623f490b` with low risk and 6 plan steps.
- Core validation: passed. `/v1/validation` against `aegis-core` ran `python -m pytest` and returned code `0`.
- Website smoke: passed. `website/scripts/smoke-web.ps1` checked frontend, backend identity, config update, workspace file listing, validation profile inference, manifest setup, diff engine, generated file apply/read-back, inferred validation, readiness, and a real chat turn.
- Website/Core bridge: passed. `/api/core-runtime` reported reachable Core with contract version `2026.05.09`.
- Website rollback: passed in a disposable `.tmp` workspace. `/api/apply` updated `src/main.py`, checkpoint `20260509T053330Z-20ddc1fc` was created, and `/api/restore-checkpoint` restored the original content.
- VS Code extension compile: passed. `npm run compile` completed `node --check extension.js`.
- Visual Studio extension package: passed. `visual-studio-extensions/aegis-local-agent-vs/build.ps1` rebuilt and copied `release/AegisLocalAgentVs.vsix`.
- ECHO//VEIL Core scan: passed. `/v1/workspaces/scan` indexed 240 safe files, detected `Unity`, `C#/.NET`, and `Visual Studio Solution`, and ignored generated Unity folders such as `Library` and `Logs`.
- Website project Core scan: passed. `/v1/workspaces/scan` indexed 269 safe files and detected Python plus website package/build markers.

### Friction Log

| ID | Category | Severity | Status | Notes |
| --- | --- | --- | --- | --- |
| DOGFOOD-001 | Setup pain point | Medium | Resolved | ECHO//VEIL Unity project path found at `C:\Users\gabri\Desktop\Placeholder Name\My project`; Core scan passed. |
| DOGFOOD-002 | Coverage gap | Medium | Open | Visual Studio extension still needs manual GUI dogfooding after VSIX packaging. Prior automation verified package/build and command-resource registration but not the full interactive tool-window workflow. |
| DOGFOOD-003 | Process gap | Low | Resolved | Root dogfooding notes did not exist before this phase. This file now acts as the daily evidence log. |
| DOGFOOD-004 | Setup pain point | Medium | Open | Two Visual Studio instances have different installed Aegis extension versions: VS 2022 has `0.1.1`, VS 18 has `0.3.0`. Daily GUI checks need to state which IDE profile is under test. |
| DOGFOOD-005 | Validation friction | Low | Resolved | First validation smoke used stale route `/v1/validation/run`; current contract is `POST /v1/validation` with `run: true`. API reference was already correct, so no code change was needed. |
| DOGFOOD-006 | Tooling false positive | Low | Open | PowerShell `Invoke-WebRequest` hit a client-side null reference checking the Vite frontend, while `curl.exe -I` returned HTTP `200`. Prefer `curl.exe` for this daily frontend probe. |

### Fixes

- Added this root dogfooding log to make daily friction and stability decisions visible.
- Located and recorded the ECHO//VEIL Unity project path so daily dogfooding can include it.
- Recorded the Visual Studio profile/version mismatch as setup friction before spending time on GUI debugging.

### Next Daily Targets

- Run ECHO//VEIL roadmap generation only after reviewing the Day 1 scan output.
- Pick one broken/unfinished project for repair and rollback practice.
- Open Visual Studio 2022 with the installed `0.1.1` extension and manually verify tool window, solution detection, health, roadmap, selected-code review, build/error workflow, approval, and rollback.
- Repeat the daily checklist on Aegis ChatBot, then expand to the website project and C++ desktop project with real issues rather than synthetic feature work.

## Long-Term Refinement Transition - 2026-05-09

The ecosystem is now treated as the primary local development environment. Daily dogfooding continues, but repeated friction graduates into `WORKFLOW_NOTES.md` for long-term refinement decisions.

Operating rules:

- Do not add features because they are interesting.
- Improve startup, indexing, roadmap quality, diff readability, validation clarity, rollback confidence, diagnostics, error messages, onboarding, and maintainability because real use shows they matter.
- Keep edits approval-based, checkpointed, rollbackable, local-first, and conservative.
- Prefer a small stable release with a clear changelog over a large rewrite.
