# Auralith Workflow Notes

This is the product-utilization notebook for using Auralith as the primary local development environment.

The goal is to capture friction from actual work, then fix only the highest-impact issues. This is not a feature wishlist or a place to invent speculative systems.

## Current Focus

- Use Aegis Core, Desktop App, VS Code Extension, and Visual Studio Extension on real projects.
- Keep shared memory, shared tasks, diagnostics, and roadmaps consistent.
- Prefer small workflow fixes over broad new systems.
- Preserve safe defaults: approval-based edits, backups, rollback, no secret editing, no destructive automation.
- Optimize for speed, usability, trust, reliability, practical workflow fit, and maintainability.
- Let repeated friction, not imagination, decide what gets simplified next.

## Long-Term Refinement Rules

- Keep the stable daily workflow boring: start, scan, roadmap, plan, preview, approve, validate, rollback when needed, record friction.
- Improve existing features before adding new ones.
- When the same annoyance appears twice, record it as a candidate for simplification.
- When a workflow takes more than three manual hops, either document the hops clearly or remove one safe hop.
- When validation fails unclearly, improve diagnostics before changing prompts.
- When rollback feels uncertain, improve preview, checkpoint naming, restore output, or docs before expanding autonomy.
- When startup or indexing feels slow, measure the slow step before changing architecture.
- Keep website `/api` compatibility, Core `/v1` contracts, client fallbacks, and local-first privacy intact.
- Ship small stable releases with clear changelog entries instead of waiting for large rewrites.

## Refinement Cadence

- Daily dogfooding notes stay in `DOGFOODING_NOTES.md`.
- This file tracks repeated pain points and decisions that should influence future small releases.
- A weekly workflow refinement review is attached to this thread under automation `auralith-dogfooding-follow-up`.
- Each review should ask: what slowed us down, what confused us, what reduced trust, what broke, and what is the smallest safe fix?

## Workflow Log

### 2026-05-09 - Long-Term Workflow Refinement Start

Context:
- Treated Auralith/Aegis as the primary local development environment rather than a release candidate experiment.
- Ran a lightweight self-check against Core, Website frontend, VS Code extension installation, roadmap generation, dashboard state, and validation-summary discovery.
- Updated the active follow-up automation into a weekly workflow refinement review so repeated friction is revisited without creating another thread automation.

What worked:
- Core `/v1/health` returned contract version `2026.05.09`.
- Core dashboard was reachable and showed registered clients plus active shared task state.
- Core roadmap generation returned focused roadmap items for the ChatBot workspace.
- Core validation summary for `aegis-core` found `python -m pytest`.
- Website frontend returned HTTP `200` through `curl.exe`.
- VS Code extension id `aegis.aegis-local-autopilot` is installed.

Friction found:
- PowerShell `Invoke-WebRequest` is unreliable as the daily Vite frontend probe in this environment; `curl.exe -I` is clearer.
- Visual Studio extension checks still need explicit profile targeting because multiple Visual Studio instances have different Aegis versions installed.
- Long-term refinement needed one canonical ledger so day-to-day fixes do not turn into a scattered wishlist.

Fixes applied:
- Promoted `WORKFLOW_NOTES.md` into the long-term refinement ledger.
- Updated the follow-up automation to perform weekly refinement reviews focused on repeated friction and small safe fixes.

### 2026-05-08 - Product Utilization Kickoff

Context:
- Used Aegis Core against the Auralith/ChatBot workspace itself.
- Checked shared dashboard state, registered clients, roadmap, diagnostics, and validation commands.
- Validated that all four clients are visible through the Core dashboard: Desktop, VS Code, Visual Studio, Website local/dev.

What worked:
- `aegis dashboard --workspace ..` returns connected clients, model status, roadmap excerpt, diagnostics, and validation commands.
- Shared clients are visible in `.aegis/clients.json`.
- Shared tasks are visible in `.aegis/tasks.json`.
- Aegis Core reports no active or stale tasks.
- Ollama model routing is healthy with `qwen3-coder:30b`.

Friction found:
- Running `python -m aegis_core.cli dashboard --workspace .. --json` failed because `--json` only worked before the subcommand.
- Website still uses its mature internal `/api` backend; moving it too quickly to the standalone `/v1` Core path would be risky.
- Manual live UI testing still needs to happen in the actual Desktop, VS Code, and Visual Studio windows, not only through build/API smoke checks.

Fixes applied:
- Made the Aegis Core CLI accept `--json` before or after the subcommand.
- Kept website integration as documented incremental migration rather than forcing a risky rewrite.

## Friction Tracker

| Date | Area | Friction | Impact | Action |
| --- | --- | --- | --- | --- |
| 2026-05-08 | Aegis Core CLI | `--json` only worked before the subcommand. | Medium | Fixed. |
| 2026-05-08 | Aegis Core safety | Ignored folder checks were case-sensitive and inspected absolute parent paths, so Windows temp-parent workspaces could be over-blocked. Core also blocked fewer secret-like filenames than editor clients. | High | Fixed with regression coverage. |
| 2026-05-08 | Website/Core boundary | Website backend and standalone Core overlap in naming and responsibilities. | Medium | Keep website on `/api`; migrate local/dev dashboard features incrementally. |
| 2026-05-08 | Manual UI confidence | Build/API checks pass, but live click-through is still needed. | Medium | Add to daily workflow checklist. |
| 2026-05-09 | Workflow refinement | Daily dogfooding evidence existed, but long-term repeated-friction rules were implicit. | Medium | Added long-term refinement rules and weekly review cadence. |
| 2026-05-09 | Frontend probe | `Invoke-WebRequest` produced a local null-reference false alarm while the Vite frontend was healthy. | Low | Prefer `curl.exe -I --max-time 5` for daily frontend reachability checks. |
| 2026-05-09 | Visual Studio profile targeting | VS 2022 and VS 18 have different Aegis extension versions installed. | Medium | Daily GUI checks must name the exact Visual Studio instance/profile under test. |
| 2026-05-09 | VS Code packaging | VSIX archive included repository-only dogfooding notes and local detected model inventory. | Medium | Excluded those files from packaging and added a lint guard. |

## Daily Workflow Checklist

Use this checklist when dogfooding Auralith on a real project:

1. Start Ollama and Aegis Core.
2. Open the project in the primary client: Desktop, VS Code, or Visual Studio.
3. Run health check.
4. Scan or refresh project memory.
5. Generate or review roadmap.
6. Pick one small task.
7. Ask for a plan and proposed diffs.
8. Review the diff and apply only approved changes.
9. Run validation.
10. Roll back at least one safe test change when validating write workflows.
11. Record friction here before adding features.

## Small Release Gate

Cut a small stable release only when:

- The change fixes repeated friction, a trust issue, a reliability bug, or documentation that blocks setup.
- The rollback and approval story is unchanged or stronger.
- Focused tests or smoke checks match the changed surface.
- `CHANGELOG.md` explains the practical user benefit.
- Known risks are recorded before the release is packaged.

## Project Types To Exercise

- Unity project
- C++ project
- Next.js project
- FastAPI backend
- ImGui desktop tool
- Visual Studio solution
- Broken/debugging workflow

## Quality Rules

- Fix repeated friction before adding new capabilities.
- If a workflow takes more than three manual hops, note it.
- If a client shows different memory/task state than Core, note it.
- If validation fails for unclear reasons, improve diagnostics before improving model prompts.
- If a proposed edit feels unsafe, improve safety/preview/rollback before agent autonomy.

## Long-Term Direction Notes

No product direction decision yet.

Options to evaluate after sustained real use:
- personal/private tool
- open-source ecosystem
- commercial platform
- hybrid model

Decision criteria:
- daily usefulness
- setup friction
- reliability on real projects
- local privacy value
- maintenance burden
- whether other developers can understand and trust it
