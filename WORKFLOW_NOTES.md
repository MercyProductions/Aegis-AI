# Auralith Workflow Notes

This is the product-utilization notebook for using Auralith as a real daily development environment.

The goal is to capture friction from actual work, then fix only the highest-impact issues. This is not a feature wishlist.

## Current Focus

- Use Aegis Core, Desktop App, VS Code Extension, and Visual Studio Extension on real projects.
- Keep shared memory, shared tasks, diagnostics, and roadmaps consistent.
- Prefer small workflow fixes over broad new systems.
- Preserve safe defaults: approval-based edits, backups, rollback, no secret editing, no destructive automation.

## Workflow Log

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
| 2026-05-08 | Website/Core boundary | Website backend and standalone Core overlap in naming and responsibilities. | Medium | Keep website on `/api`; migrate local/dev dashboard features incrementally. |
| 2026-05-08 | Manual UI confidence | Build/API checks pass, but live click-through is still needed. | Medium | Add to daily workflow checklist. |

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
10. Record friction here before adding features.

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
