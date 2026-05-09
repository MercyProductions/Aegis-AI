# Aegis Local Agent for Visual Studio

Visual Studio 2022 Community extension that brings the local-first Aegis coding agent workflow into Visual Studio solutions.

Dogfooding build: `0.1.1`

## Requirements

- Visual Studio 2022 Community
- Visual Studio extension development workload / VSSDK
- .NET Framework 4.7.2 targeting pack
- Ollama running at `http://127.0.0.1:11434`
- Optional shared Aegis Core runtime at `http://127.0.0.1:8788`

Recommended model:

```powershell
ollama pull qwen3-coder:30b
```

Fallback models:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull granite-code:8b
```

## Build

From this folder:

```powershell
.\build.ps1
```

The script uses `dotnet msbuild`, then asks VSSDK BuildTools to generate the package definition and VSIX container.

The packaged VSIX is copied to:

```text
release/AegisLocalAgentVs.vsix
```

## Install

Double-click the VSIX or run:

```powershell
VSIXInstaller.exe .\release\AegisLocalAgentVs.vsix
```

If `VSIXInstaller.exe` is not on PATH, use the one under your Visual Studio install, for example:

```powershell
& "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\VSIXInstaller.exe" .\release\AegisLocalAgentVs.vsix
```

For a clean install, close Visual Studio first, uninstall any older **Aegis Local Agent** build from **Extensions > Manage Extensions**, restart Visual Studio, then install the new VSIX.

## Commands

Visual Studio Tools menu commands:

- `Aegis: Open Agent`
- `Aegis: Explain Current File`
- `Aegis: Review Selected Code`
- `Aegis: Refactor Selected Code`
- `Aegis: Fix Build Errors`
- `Aegis: Fix Selected Error`
- `Aegis: Explain Build Failure`
- `Aegis: Review Startup Project`
- `Aegis: Generate Solution Roadmap`
- `Aegis: Continue From Roadmap`
- `Aegis: Continue Current Solution`
- `Aegis: Rollback Last Change`
- `Aegis: Rescan Solution Intelligence`
- `Aegis: Run Health Check`

Solution Explorer context menu commands:

- `Aegis: Explain This File`
- `Aegis: Generate Tests For This File`
- `Aegis: Review This Project`
- `Aegis: Fix Errors In This Project`
- `Aegis: Add Feature To This Project`
- `Aegis: Create Roadmap From Solution`

## Tool Window

Open **Aegis Local Agent** from the command menu. The tool window includes:

- current solution and project overview
- current status: Ready, No Solution, Ollama Offline, Indexing, Running Agent, Build Failed, or Error
- model selector
- model status and settings summary
- chat panel
- agent action buttons
- selected Error List item panel
- build status and build output summary
- current agent mode, active plan, affected files, and repair attempt count
- solution intelligence tab with scan status, architecture map, roadmap, indexed symbols, and dependency map
- proposed changes panel
- compact diff preview
- validation/build output
- approve and rollback buttons

The UI uses a Visual Studio-friendly dark theme, compact action groups, readable output panels, and color-coded loading/error states. Aegis also writes short status updates to the Visual Studio status bar.

## Settings

Open **Tools > Options > Aegis Local Agent > General** to configure:

- Ollama URL
- Aegis Core URL
- default model
- fallback models
- max context size
- safety mode
- auto-scan on solution open
- validate-after-apply behavior
- build validation preference
- backup location

Defaults are local-first and safe:

```text
Ollama URL: http://127.0.0.1:11434
Aegis Core URL: http://127.0.0.1:8788
Default model: qwen3-coder:30b
Fallback models: qwen2.5-coder:7b, granite-code:8b
Safety mode: Strict
Auto-scan on solution open: false
Validate after apply: true
Backup location: .aegis/backups
```

The Ollama and Aegis Core URL fields normalize common local inputs. Values such as `127.0.0.1:11434`, pasted Core endpoint URLs like `http://127.0.0.1:8788/v1/health`, and pasted Ollama endpoint URLs like `/api/tags` are reduced to the usable service base before health checks, model calls, or Core registration. Reverse-proxy prefixes such as `https://proxy.local/aegis` or `https://proxy.local/ollama` are preserved.

Changing settings affects new model calls and new agent workflows. Existing pending proposals should be reviewed or rejected before changing safety-related settings.

Relative backup paths are kept inside the current solution. Use an absolute path only when you intentionally want backups outside the solution folder.

Rollback metadata includes an explicit backup ID. During rollback, Aegis validates that the manifest belongs to the current solution, resolves only the explicit backup folder, checks manifest and backup file paths before touching solution files, and reports skipped entries if metadata is incomplete or unsafe.

## Health Check

Run `Aegis: Run Health Check` after installation or when something feels off. It verifies:

- a solution is open
- `.aegis/` is writable
- `symbol-index.json` and `dependency-map.json` can be written
- backup location can create and delete a probe file
- Aegis Core is reachable, and whether this Visual Studio client can register for shared sync
- Ollama is reachable
- default and fallback models are installed
- Visual Studio build/Error List integration can be read

## Visual Studio Integration

Aegis reads the active solution, startup project, active document, selected code, selected Solution Explorer item, current Error List, and Build output pane. Error workflows group diagnostics by file and can target the selected error, the selected project, or the whole solution.

## Agent Workflow

Agent modes are:

- Fix selected error
- Fix current project
- Continue current solution
- Implement feature
- Refactor selected code
- Explain build failure
- Generate tests

Each editing mode follows the same safe loop:

1. Inspect the current solution, project, active document, selected code, Error List, and Build output when relevant.
2. Create a clear plan and affected-file list.
3. Propose file edits as previewable diffs.
4. Wait for approval.
5. Apply approved edits with backups under `.aegis/backups/`.
6. Validate with Visual Studio build tools.
7. If validation fails, propose one minimal repair diff.
8. Stop after 3 repair attempts unless you explicitly allow another repair.

## Build Validation

The tool window can run:

- Build Solution
- Build Startup Project
- Build Selected Project
- Clean Solution, only after confirmation
- Rebuild Solution, only after confirmation

Validation captures compiler errors, linker errors, warnings, failed project names, file/line diagnostics, Error List items, and MSBuild Build output where Visual Studio exposes them.

## Solution Intelligence

Aegis can scan the solution and refresh persistent local memory. For daily-driver reliability on large C++, Unity, and multi-project solutions, automatic scan on solution open is disabled by default. Run `Aegis: Rescan Solution Intelligence`, `Aegis: Run Health Check`, or use the **Rescan Intelligence** button in the tool window when you want to refresh the index. You can re-enable automatic scans in **Tools > Options > Aegis Local Agent > General**.

The scanner reads:

- the `.sln` / `.slnx` file and all detected `.csproj` / `.fsproj` / `.vbproj` / `.vcxproj` files
- project references, assembly references, target frameworks, NuGet packages, include paths, and C++ configurations
- startup project, active project, active document, selected code, and Solution Explorer selection
- README, TODO, config, XAML, test, source, and project files
- Unity `Assets/`, `Packages/manifest.json`, `Packages/packages-lock.json`, key `ProjectSettings/` metadata, and `.asmdef` / `.asmref` files while ignoring generated runtime folders

The index is incremental inside the running Visual Studio session. Unchanged files are reused from cache, changed files are reparsed, and a manual rescan forces a fresh index.

Ignored folders include `.git/`, `.vs/`, `.aegis/`, `bin/`, `obj/`, NuGet `packages/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `Generated/`, Unity `Library/`, Unity `Temp/`, `Logs/`, and C++ `ipch/`. Unity's top-level `Packages/` folder remains readable for package metadata. Proposed edits also reject leaf filenames that look like `.env` files, tokens, passwords, API keys, auth files, private keys, SSH keys, certificates, or keystores while allowing ordinary source names such as `tokenizer.py`.

## Architecture Awareness

Aegis writes:

- `.aegis/symbol-index.json` for classes, methods, interfaces, namespaces, enums, structs, XAML views, C++ symbols, and Unity `MonoBehaviour` signals
- `.aegis/dependency-map.json` for project references, file relationships, C# `using` dependencies, C++ includes, XAML code-behind links, header/source pairs, and likely test relationships
- `.aegis/architecture-map.md` for solution overview, project roles, major systems, entry points, build flow, and risk areas

Generated sections in memory files are replaced safely, while your handwritten notes outside those generated sections are preserved.

## Context Selection

Aegis does not send the whole solution to the model. For chat, review, roadmap, and proposal workflows, it builds a focused context from:

- active document and selected code
- selected/startup project metadata
- relevant symbols and related dependencies
- nearby tests and config files
- current Error List / Build output when relevant
- persistent `.aegis` memory

This keeps model prompts smaller, reduces hallucinated file edits, and helps the agent preserve existing C#, F#, Visual Basic, C++, WPF, ASP.NET, and Unity architecture.

## Roadmap Workflow

`Aegis: Generate Solution Roadmap` updates `.aegis/roadmap.md` with current state, missing features, bugs/risks, technical debt, recommended next tasks, priority order, and validation commands.

`Aegis: Continue From Roadmap` reads that roadmap, chooses one safe high-value task, creates a plan, proposes diffs, and waits for approval before applying anything.

## Supported Project Workflows

- C#/.NET: reads `.csproj`, target frameworks, NuGet `PackageReference` entries, namespaces, classes, and WPF XAML files.
- F# and Visual Basic: recognizes `.fsproj` and `.vbproj` projects, indexes modules/types/functions/imports, and keeps managed project validation hints available.
- C++: reads `.vcxproj`, header/source pairs, include paths, project configurations, common `.cpp` / `.cc` / `.cxx` and header suffixes, and linker/compiler diagnostics from Visual Studio output.
- Unity: recognizes `Assets/`, package manifests and lockfiles, key `ProjectSettings/` metadata, `.asmdef` / `.asmref` files, avoids `Library/` and `Temp/`, and flags `MonoBehaviour` scripts for Unity-safe planning.

## Safety Model

Aegis does not rewrite files automatically. The Visual Studio version follows this loop:

1. Inspect the open solution.
2. Build focused solution context.
3. Ask the local Ollama model for a plan and proposed edits.
4. Show the proposal in the tool window.
5. Wait for approval.
6. Create backups under `.aegis/backups/`.
7. Apply approved changes.
8. Build the solution.
9. Log validation and decisions.

Blocked paths include `.env`, secret-looking files, private keys, `.vs/`, `bin/`, `obj/`, `packages/`, generated files, and vendor folders.

## Project Memory

The extension writes local memory at the solution root:

```text
.aegis/
  solution-summary.md
  roadmap.md
  architecture-map.md
  decisions.md
  known-issues.md
  build-log.md
  agent-history.json
  symbol-index.json
  dependency-map.json
  backups/
```

Secret-looking lines are filtered before writing generated memory.

If `.aegis` or one of its memory files is damaged, blocked, or accidentally replaced by a directory, Aegis skips that path and keeps the tool window usable where possible. Run Health Check to surface the degraded memory/index state before resetting or repairing `.aegis`.

## Current Limitations

- First release focuses on Visual Studio 2022 Community and classic VSSDK.
- Diff preview is compact in the tool window, with generated preview files under `.aegis/visual-studio-agent/previews/`.
- Build integration uses Visual Studio `SolutionBuild` and Error List where available.
- The model can still suggest bad edits; review every proposal before approval.
- See `TROUBLESHOOTING.md` if the extension, Ollama connection, model detection, or rollback workflow needs attention.
