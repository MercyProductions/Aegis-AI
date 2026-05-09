# Dogfooding Notes

Last updated: 2026-05-09

Phase: Daily Dogfooding

Target stability release: `0.1.1`

Automation: `auralith-dogfooding-follow-up`

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
