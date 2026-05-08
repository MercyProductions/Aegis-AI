# Aegis AI Patch Notes

## 2026-05-04 - Native Build Reliability Update

### Summary

This update fixes the native Windows validation path that could stall or fail when Aegis generated or validated C++/CMake projects from a deeply nested workspace path such as `Runtime & Engine Tools`.

### Highlights

- Adds a Visual Studio developer-command wrapper for native Windows builds when `cl.exe`/MSBuild are not already available on PATH.
- Prefers Visual Studio's bundled Ninja generator for CMake when available, with NMake as a fallback.
- Executes default Windows CMake `build` directories from a short temp root while preserving the user-facing validation command in chat and command history.
- Sanitizes only the native wrapper PATH to remove entries containing shell metacharacters such as `&`, preventing npm-inherited paths from breaking `cmd.exe`.
- Updates generated C++/CMake, DLL host-loader, and Windows internals scaffolds to avoid deep-path CMake failures.
- Adds regressions for Visual Studio wrapper generation, Ninja preference, short CMake build directories, PATH sanitization, and Windows internals scaffold imports.

### Validation

- Focused command-runner regressions passed: `18 passed`.
- Focused project-scaffolder regressions passed: `118 passed, 46 subtests passed`.
- Full web workspace validation passed: frontend `25 passed`, production build passed, backend `424 passed, 99 subtests passed`.
- Local backend stress smoke passed with API routing, C++ console solution, CMake CLI validation, DLL host loading, Windows internals/MinHook adapter, solution materialization, existing-project continuity, diagnostic extraction, command-history recovery, readiness continuation, and frontend/backend source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-04 - Backend Mission Continuity Anchor Update

### Summary

This update closes the backend half of the “repeat yourself twice” bug. Aegis now reads the mission anchor from request history and applies it before workspace resolution, route preview, direct-chat gating, stream metadata, task planning, model prompting, and completion-quality checks.

### Highlights

- Adds a backend mission-anchor parser for the frontend `Aegis mission anchor` history record.
- Converts vague follow-ups such as `continue`, `build it`, `fix it`, `repair it`, `validate it`, and autopilot continuation prompts into mission-aware backend planning input.
- Resolves workspace paths from the original anchored mission when the visible follow-up no longer contains a path.
- Prevents path-bound coding continuations from being misrouted into normal direct chat.
- Preserves normal conversational streaming when the anchored mission was not a coding/file task.
- Injects the anchor into the mutation contract so the model is told to preserve target path, stack, artifact type, and validation intent.
- Adds regressions for native/DLL continuation routing, stream metadata workspace resolution, and non-coding chat continuations.
- Extends the local stress harness with backend source-contract checks for mission-anchor parsing and mission-aware follow-up planning.

### Validation

- Focused prompt-routing regressions passed: `40 passed, 9 subtests passed`.
- Focused agent parser regressions passed: `91 passed, 10 subtests passed`.
- Full web workspace validation passed: frontend `25 passed`, production build passed, backend `415 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation with command-history recovery, diagnostic extraction, readiness continuation, generic instruction, and frontend/backend source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Frontend Mission Anchor Update

### Summary

This update keeps long coding sessions anchored to the original user mission, target path, project type, and validation intent even when the visible chat history is shortened, a message is replayed after reconnect, or autopilot sends a vague continuation prompt.

### Highlights

- Adds an invisible frontend mission anchor that follows the original path-bound or project-building request into bounded backend request history.
- Preserves the active workspace root, original artifact type, language/stack, and validation intent for follow-ups such as `continue`, `build it`, `fix it`, `repair it`, and autopilot passes.
- Stores a sanitized mission anchor inside queued outbound messages so reconnect retries do not lose the first task instruction.
- Filters duplicate mission anchors out of the visible history tail before sending a backend request.
- Keeps the anchor out of the chat UI so users see normal conversation history while the backend receives stronger continuity context.
- Adds regression coverage for mission-anchor creation, sanitization, tail-window preservation, queue replay, and invalid-anchor rejection.
- Extends the local backend stress harness with source-contract checks for the frontend mission-anchor and queued-replay path.

### Validation

- Focused frontend queue and mission-anchor regressions passed: `15 passed`.
- Full frontend regression suite passed: `25 passed`.
- Full web workspace validation passed: frontend `25 passed`, production build passed, backend `412 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation with command-history recovery, diagnostic extraction, readiness continuation, and frontend mission-anchor source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Command History Validation Recovery Update

### Summary

This update makes Aegis more resilient during long coding sessions by recovering a previously successful validation command from `.aegis/command_history.json` when the active validation profile is missing.

### Highlights

- Adds command-history-backed validation discovery below explicit project manifests but above generic filesystem guesses.
- Recovers the latest successful build/test/type-check validation command when the top-level remembered command failed.
- Refuses unsafe remembered commands such as install, publish, shell-redirection, destructive file operations, registry/system commands, and untrusted shell launches.
- Adds regressions for successful history recovery, failed-history fallback, and unsafe command-history rejection.
- Extends the local backend stress harness with a real recovery smoke that deletes a learned CMake validation profile and verifies Aegis rebuilds the profile from command history.
- Adds source-contract checks so future refactors cannot silently remove command-history validation recovery.

### Validation

- Focused validation-manager regressions passed: `18 passed`.
- Focused agent parser regressions passed: `91 passed`.
- Focused fallback, prompt-routing, and project-scaffolder regressions passed: `177 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `412 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation with command-history recovery, diagnostic extraction, readiness continuation, and source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Validation Profile Learning Update

### Summary

This update makes successful draft-discovered validation commands become remembered workspace knowledge, reducing repeat failures where Aegis has to rediscover how to build or test the same project on later turns.

### Highlights

- Saves a successful draft-proposed validation command into the workspace validation profile.
- Keeps failed draft validation commands ephemeral so bad guesses do not poison future build/repair passes.
- Leaves explicit one-turn user validation overrides temporary by default.
- Emits a `Validation command learned` activity event when Aegis promotes a successful command into project memory.
- Adds regressions for learned draft validation, temporary request overrides, and failed draft validation commands.
- Extends the stress harness source contracts for validation-learning behavior.

### Validation

- Focused backend parser regressions passed: `91 passed`.
- Focused fallback regressions passed: `24 passed`.
- Focused prompt-routing regressions passed: `37 passed`.
- Focused project-scaffolder regressions passed: `116 passed`.
- Focused validation-manager regressions passed: `14 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `408 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Draft Validation Command Recovery Update

### Summary

This update closes a build/repair gap where Aegis could display the right validation command from a model or fallback draft but still fail to run it during the actual validation loop.

### Highlights

- Promotes safe, validation-like draft command proposals into the current turn's validation recipe.
- Preserves priority order: explicit user override, saved workspace validation profile, draft-proposed validation command, then normal detector fallback.
- Keeps install/destructive command proposals out of automatic validation promotion.
- Emits a visible `Draft validation command selected` activity event so the UI can explain why a command ran.
- Reuses the same selected recipe through repair retries and rollbacks, preventing validation from switching commands mid-loop.
- Adds regressions for draft-only validation, saved-profile precedence, request override precedence, and install-command rejection.
- Adds stress-harness source contracts for the draft validation promotion path.

### Validation

- Focused backend parser regressions passed: `90 passed`.
- Focused fallback regressions passed: `24 passed`.
- Focused prompt-routing regressions passed: `37 passed`.
- Focused project-scaffolder regressions passed: `116 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `407 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Existing Project No-Change Recovery Update

### Summary

This update strengthens Aegis' recovery path when a model returns no actionable file edits for an existing project continuation request.

### Highlights

- Adds a strict existing-project continuation draft when fallback correctly refuses to generate starter files.
- Preserves the detected project stack and tells the next pass to update real source/build files directly.
- Proposes the stack-native validation command for preserved workspaces, including manifest commands and common build profiles.
- Prevents empty-patch turns from quietly drifting into unrelated website/static-app scaffolds on follow-up or autopilot passes.
- Adds parser regressions and stress-harness source contracts for the no-change recovery helper and validation-command proposal path.

### Validation

- Focused agent parser regressions passed: `86 passed`.
- Focused fallback regressions passed: `24 passed`.
- Focused prompt-routing regressions passed: `37 passed`.
- Focused project-scaffolder regressions passed: `116 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `403 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Existing Workspace Fallback Guard Update

### Summary

This update hardens the deterministic fallback layer so existing C++/DLL/native workspaces are preserved during weak-model or no-change turns instead of being replaced with unrelated starter files.

### Highlights

- Adds an existing-workspace preservation gate before fallback starter generation.
- Keeps `work on`, `refine`, `build it`, `fix`, `repair`, `validate`, and `do not make a website` follow-ups anchored to the current project shape.
- Adds a stack-native `build.py` helper for existing CMake/MSBuild projects when validation is requested and no build helper exists.
- Avoids recreating `CMakeLists.txt`, `src/main.cpp`, `index.html`, `package.json`, or web app files during existing native/DLL continuation work.
- Still allows explicit fresh rebuild requests such as `from scratch`, `fresh project`, `starter`, `scaffold`, `convert`, and `migrate`.
- Adds fallback regressions for existing DLL continuation, native follow-up validation, existing build-helper preservation, and explicit fresh rebuild behavior.
- Adds stress-harness source contracts to keep this fallback guard from regressing.

### Validation

- Focused fallback regressions passed: `24 passed`.
- Focused agent parser regressions passed: `82 passed`.
- Focused project-scaffolder regressions passed: `116 passed`.
- Focused prompt-routing regressions passed: `37 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `399 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, scaffold, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and fallback source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Mission Continuity Guardrail Update

### Summary

This update tightens Aegis' task contract for long coding-agent work so explicit-path prompts, existing DLL/native projects, and bare `continue`/autopilot follow-ups stay anchored to the original project instead of drifting into unrelated website scaffolds.

### Highlights

- Adds a dedicated mission continuity contract block to the backend model prompt.
- Preserves manifest-backed implementation work even when the latest user prompt only says `continue`, `build`, `repair`, `validate`, or autopilot.
- Surfaces the resolved explicit workspace path and tells the model that trailing words like `at this path refine my existing DLL` are instructions, not folder-name text.
- Adds native/C++ guardrails that explicitly reject accidental `package.json`, `index.html`, `styles.css`, `app.js`, Next/Vite/Tailwind, and static-site surfaces for native/DLL work unless the user asks to convert stacks.
- Adds artifact-specific guidance for DLL/shared-library, driver, desktop, web, Python, .NET, Rust, and Go project families.
- Keeps known validation commands and entry points in the mission contract so build/repair passes stay attached to the right executable or library surface.
- Adds regressions for explicit-path DLL refinement and manifest-backed native `continue` prompts.
- Adds stress-harness source contracts so mission continuity, native/C++ drift prevention, explicit-path trailing-instruction protection, and continuation-as-file-work behavior are verified during local backend stress runs.

### Validation

- Focused agent parser regressions passed: `82 passed`.
- Focused project-scaffolder regressions passed: `116 passed`.
- Focused prompt-routing regressions passed: `37 passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `396 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, native continuity, scaffold, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and mission-contract source checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Desktop Mission Contract Update

### Summary

This update gives packaged desktop projects their own mission-contract family instead of letting Electron/Tauri-style projects fall back to a generic or plain web classification during follow-up work.

### Highlights

- Adds `stack-lock:desktop` for Electron, Tauri, Tkinter desktop, WPF desktop, and ImGui Win32 desktop presets.
- Saves desktop scaffolds with a `desktop` mission family so autopilot and repair passes know the project is a packaged app, not a normal website.
- Detects desktop host surfaces in model drafts, including Electron main/preload files, Tauri host files, WPF/XAML files, Tkinter/PySide/PyQt code, and native ImGui/Win32/DX11 code.
- Infers manifest-free Electron/Tauri/WPF workspaces as desktop projects from their actual host files.
- Rejects plain static-site drift when a saved desktop mission contract is active.
- Adds parser and scaffolder regressions for desktop stack locks, desktop manifest inference, Electron host detection, and static-site drift rejection.
- Adds stress-harness source contracts so desktop stack-lock support is checked during live backend stress runs.

### Validation

- Focused agent parser regressions passed: `80 passed, 10 subtests passed`.
- Focused project-scaffolder regressions passed: `116 passed, 46 subtests passed`.
- Focused prompt-routing regressions passed: `37 passed, 9 subtests passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `394 passed, 94 subtests passed`.
- Local backend stress smoke passed with API, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and desktop stack-lock source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Validator-Aware Stack Inference Update

### Summary

This update fixes a stack-inference bug that could misclassify manifest-free Python, .NET, or other imported workspaces as native C++ just because they contain Aegis' generic `build.py` validation helper.

### Highlights

- Stops treating `build.py` by itself as a native C++ workspace marker.
- Preserves native C++ detection through real native signals such as `CMakeLists.txt`, Visual Studio project files, and C/C++ source files.
- Keeps Python workspaces with `pyproject.toml`, Python source, tests, and `build.py` anchored to Python during continuation and repair.
- Keeps .NET workspaces with `.csproj`/`.cs` files and `build.py` anchored to .NET during continuation and repair.
- Adds regressions so Python continuation drafts are not rejected as “not native C++” when the only shared build artifact is `build.py`.
- Adds a stress-harness source contract to catch accidental reintroduction of `build.py` as a native marker.

### Validation

- Focused agent parser regressions passed after catching and fixing the validator edge: `77 passed, 10 subtests passed`.
- Focused backend routing/scaffolder regressions passed: `229 passed, 61 subtests passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `390 passed, 90 subtests passed`.
- Local backend stress smoke passed with API, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Desktop Host Drift Guard Update

### Summary

This update adds a desktop-specific quality gate so prompts that ask for a desktop app, Windows app, GUI tool, Electron/Tauri app, WPF app, or ImGui/native GUI cannot be satisfied by a plain website/static frontend draft.

### Highlights

- Recognizes explicit desktop and GUI task wording in backend draft-quality checks.
- Allows valid desktop host surfaces such as Electron main/preload files, Tauri host files, WPF/XAML files, Tkinter/PySide/PyQt code, and native ImGui/Win32/DX11 code.
- Rejects static `index.html`/CSS/JS style drafts when the prompt asked for a packaged desktop or GUI application.
- Extends completion-quality scoring so autopilot keeps repairing/regenerating instead of marking static frontend drift as acceptable progress.
- Adds focused parser regressions for static-site rejection, Electron desktop allowance, and completion-quality behavior.
- Adds stress-harness source contracts so the desktop host drift guard is checked in live stress runs.

### Validation

- Focused agent parser regressions passed: `75 passed, 10 subtests passed`.
- Focused backend routing/scaffolder regressions passed: `227 passed, 61 subtests passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `388 passed, 90 subtests passed`.
- Local backend stress smoke passed with API, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, and desktop host drift source-contract checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Task-Adherence Quality Gate Update

### Summary

This update adds a stronger backend quality gate for long coding-agent/autopilot passes so Aegis can detect when a draft starts drifting away from the requested project type before it is treated as useful progress.

### Highlights

- Treats `DLL`, `shared library`, `dynamic library`, `CMake`, `MinHook`, `ImGui`, and native tooling language as native C++ project signals.
- Normalizes punctuation in web-negation prompts, so `do not make a website.` works the same as `do not make a website`.
- Rejects generated web-stack files when the latest prompt explicitly says not to create a website or web app.
- Compares generated draft stack families against the active workspace stack when continuing existing projects.
- Adds focused regression coverage for existing DLL/native prompts that mention dashboard/UI wording but must not become web projects.
- Extends the stress harness source contracts so this task-adherence quality gate cannot be accidentally removed.

### Validation

- Focused agent parser regressions passed: `72 passed, 10 subtests passed`.
- Focused backend routing/scaffolder regressions passed: `224 passed, 61 subtests passed`.
- Full web workspace validation passed: frontend `20 passed`, production build passed, backend `385 passed, 90 subtests passed`.
- Local backend stress smoke passed with API, native continuity, C++ console solution, C++ DLL host loader, Windows internals/MinHook adapter, solution materialization, existing-project continuity, CMake validation, diagnostic extraction, and readiness continuation checks.
- Desktop Release x64 build passed with `0 Warning(s)` and `0 Error(s)`.

## 2026-05-03 - Native Path And Web-Negation Routing Update

### Summary

This update hardens Aegis against a long-task drift pattern where a native/DLL prompt with UI wording could leak into website routing, especially when the target path was followed by a natural-language refinement instruction.

### Highlights

- Stops Windows target-path parsing before action words such as `refine` even when a later comma appears in the prompt.
- Recognizes `do not make a website`, `do not make a web app`, and contraction variants as explicit web-stack negation.
- Keeps native/DLL routing clean when the user asks for a diagnostics UI inside an existing native project.
- Extends the live stress harness so existing DLL prompts with UI wording and web negation must stay on the native DLL preset.

### Validation

- Focused project-scaffolder and prompt-routing regressions passed: `152 passed, 51 subtests passed`.
- Focused agent parser regressions passed: `70 passed, 10 subtests passed`.

## 2026-05-03 - Queued Prompt Conversation Pinning Update

### Summary

This update hardens the frontend message queue so reconnect and busy-state replays keep the originating chat thread, workspace, execution options, and a sanitized history snapshot.

### Highlights

- Prevents queued prompts from landing in whichever conversation happens to be active when the backend reconnects.
- Stores a compact thread/history snapshot with each queued message while preserving workspace, mode, auto-apply, and validation settings.
- Keeps legacy queue entries readable so pending prompts from older local storage payloads are not discarded.
- Defensively re-adds the user prompt during replay if an older queued entry claimed history was recorded but did not include the original history.
- Adds a live stress contract so queue/thread replay safety is checked during the broader Aegis stress harness, not only unit tests.

### Validation

- Frontend queue regression tests passed: `20 passed`.
- Frontend TypeScript and Vite production build passed.

## 2026-05-03 - Command Parser Glued-Operator Validation Update

### Summary

This update hardens the command runner against a validation edge case common in generated build commands. Aegis now detects unquoted shell operators even when they are glued to adjacent command text, such as `cmake -S . -B build&&cmake --build build`, while leaving quoted operator text alone.

### Highlights

- Normalizes unquoted shell operators before safe command parsing.
- Allows safe `&&` chains without requiring spaces around the operator.
- Keeps unsafe glued operators like `;` and `|` blocked.
- Preserves quoted strings such as `python -c "print('one&&two')"`.
- Added command-runner regressions for glued safe chains, quoted operators, and blocked unsafe operators.
- Added stress-script source contracts so future stress runs catch accidental removal of this parser guard.

### Validation

- Command approval/runner regression tests passed: `13 passed`.
- Validation manager regression tests passed: `14 passed, 4 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.

## 2026-05-03 - Apply Layer Delete-After-Skipped-Create Safety Update

### Summary

This update closes a destructive sibling of the append-after-skipped-create guard. If a malformed batch tried to `create` a file that already existed and then `delete` that same path, Aegis would skip the unsafe create but could still delete the original file. The apply layer now treats skipped seed creates as blocked delete targets for the rest of that batch.

### Highlights

- Blocks `delete` actions after a skipped seed `create` for the same normalized path.
- Preserves normal delete behavior when the batch intentionally deletes an existing file without a failed seed create.
- Reuses the normalized, case-folded batch path keying already used by the append guard.
- Added workspace regression coverage for:
  - create existing file with Windows-style slashes
  - follow-up delete with POSIX-style slashes
  - original file remains untouched
  - normal delete still succeeds
- Added live stress-script source contracts so future integration stress catches accidental removal of this destructive batch guard.

### Validation

- Workspace/storage regression tests passed: `47 passed`.
- Fallback engine regression tests passed: `21 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `378 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Apply Layer Normalized Batch Path Contract Update

### Summary

This update adds adversarial coverage around the batch path normalization that protects workspace writes. Aegis now has explicit regressions proving that skipped seed creates still block later appends when the model mixes Windows backslashes, POSIX slashes, or different path casing inside the same apply batch.

### Highlights

- Added regression coverage for mixed `generated\\monolith.cpp` and `generated/monolith.cpp` paths in one apply batch.
- Added regression coverage for mixed-case batch paths like `Generated/Monolith.cpp` followed by `generated/monolith.cpp`.
- Verified the existing apply-layer batch keying uses normalized, case-folded target paths.
- Added live stress-script source contracts for `skipped_create_paths` and `casefold` so future stress runs catch accidental removal of normalized batch tracking.
- Preserved the existing behavior for valid large generated-file chunking.

### Validation

- Workspace/storage regression tests passed: `45 passed`.
- Fallback engine regression tests passed: `21 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `376 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Apply Layer Append-After-Skipped-Create Safety Update

### Summary

This update closes a second-order batch mutation bug in the workspace apply layer. If a model or tool produced a `create` action for a file that already existed, Aegis correctly skipped the create; however, a later `append` to that same path in the same batch could still append onto the old file. Aegis now treats a skipped seed create as a blocked append target for the rest of that apply batch.

### Highlights

- Tracks skipped `create` actions during `WorkspaceManager.apply_changes`.
- Blocks later `append` actions to the same path when the seed `create` did not apply.
- Preserves normal large-file chunking when the seed `create` succeeds.
- Preserves normal append behavior for files that already existed when the batch intentionally starts with `append`.
- Added workspace regression coverage for:
  - existing file receives skipped `create`
  - follow-up `append` to that same file is also skipped
  - original file content remains untouched
- Added live stress-script source contracts so future integration stress catches accidental removal of the batch guard.

### Validation

- Workspace/storage regression tests passed: `43 passed`.
- Fallback engine regression tests passed: `21 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `374 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Apply Layer Append-Seed Safety Update

### Summary

This update closes the last loose edge in the workspace file-action contract. Aegis already distinguishes `create` from `update`; now `append` is also explicit. Append actions can extend files that already exist, including files created earlier in the same apply batch, but they can no longer create brand-new files by accident.

### Highlights

- Hardened `WorkspaceManager.apply_changes` so `append` requires the target file to exist.
- Added a clear apply warning: missing append targets require a seed `create` before `append`.
- Preserved large generated-file chunking where a batch starts with `create` and follows with `append`.
- Added workspace regression coverage for a standalone append targeting a missing generated file.
- Added live stress-script source contracts so future integration stress catches accidental removal of the append guard.

### Validation

- Workspace/storage regression tests passed: `42 passed`.
- Fallback engine regression tests passed: `21 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `373 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Apply Layer Missing-Update Safety Update

### Summary

This update tightens the opposite side of the file-change contract. Aegis already refuses to run `create` over an existing file; now it also refuses to run `update` against a file that does not exist. That prevents malformed model drafts, replayed apply calls, or future tools from quietly creating new files while claiming to modify an existing project.

### Highlights

- Hardened `WorkspaceManager.apply_changes` so `update` can only modify files that already exist.
- Added a clear apply warning: missing files require `create` instead of `update`.
- Preserved valid batch behavior where a file can be `create`d and then `update`d later in the same apply batch.
- Updated the Next.js fallback starter so it chooses `create` or `update` from the scanned workspace surface instead of hard-coding update actions.
- Added workspace regression coverage for:
  - `update` targeting missing `src/missing.cpp` leaves the filesystem untouched
  - `create` followed by `update` on the same path in one batch still succeeds
- Added fallback coverage to verify existing Next.js files are modified with `update` while new component files use `create`.
- Added live stress-script source contracts so future integration stress catches accidental removal of the missing-file update guard.

### Validation

- Workspace/storage regression tests passed: `41 passed`.
- Fallback engine regression tests passed: `21 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `372 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Apply Layer Create-Overwrite Safety Update

### Summary

This update adds a lower-level workspace safety net under the model-draft guards. Even if a future tool, replayed draft, direct `/api/apply` call, or malformed model response bypasses the agent-level create-overwrite detector, the workspace apply layer now refuses to run a `create` action over a file that already exists. Existing files must be modified through `update`, which keeps continuation work explicit and prevents silent source replacement.

### Highlights

- Hardened `WorkspaceManager.apply_changes` so `create` never overwrites an existing file.
- Added a clear apply warning: existing files require `update` instead of `create`.
- Preserved normal `update` behavior for existing files.
- Preserved `create` followed by `append` chunking for large generated files when the file did not exist at the start of the batch.
- Added workspace regression coverage for:
  - `create` targeting an existing `src/main.cpp` leaves the original file untouched
  - `update` targeting that same file still edits it successfully
- Added live stress-script source contracts so future integration stress catches accidental removal of the apply-layer guard.

### Validation

- Workspace/storage regression tests passed: `39 passed`.
- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `370 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Existing File Overwrite Guard Update

### Summary

This update closes another high-risk coding-agent failure mode: a model draft can use `create` for a file that already exists, which is valid JSON but wrong behavior for continuation work. Aegis now treats that as a suspicious overwrite attempt unless the latest user request explicitly asks to replace, overwrite, recreate, reset, or rebuild the project.

### Highlights

- Added an existing-file overwrite detector for model drafts.
- Blocked `create` actions that target existing important files during continuation work, including source, build, config, manifest, and `.aegis` memory files.
- Kept explicit replacement workflows allowed when the user clearly asks for `replace`, `overwrite`, `recreate`, `reset`, `from scratch`, or similar fresh-start wording.
- Wired overwrite detection into completion-quality scoring so autopilot keeps correcting the pass instead of marking a risky overwrite as ready.
- Wired overwrite detection into model-draft acceptance so Aegis can swap risky create-as-overwrite drafts for safer continuation patches.
- Added safe rejection messaging that tells the next pass to use `update`, not `create`, for existing files.
- Added adversarial parser regressions for:
  - continuation prompts that create an existing `src/main.cpp`
  - explicit replacement prompts that are still allowed
  - autopilot quality scoring when an existing file would be overwritten
- Added stress-script source contracts so future stress runs catch accidental removal of the create-as-overwrite guard.

### Validation

- Focused agent/parser regression tests passed: `70 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `368 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Existing Project Starter-Drift Guard Update

### Summary

This update closes another realistic long-task failure mode: when Aegis is already working inside an existing project and the user says `continue`, `keep going`, `fix it`, `build it`, or `improve this`, a model draft should not quietly drop a fresh starter scaffold into the workspace. Aegis now detects that pattern and marks the pass as needing correction before files are accepted as complete.

### Highlights

- Added an existing-project surface detector that recognizes manifests, build files, solution/project files, and source-root layouts.
- Added a fresh-starter scaffold detector for root starter files such as:
  - `README.md`, `.gitignore`, `package.json`, `index.html`, `CMakeLists.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `build.py`
  - starter entry points like `src/main.cpp`, `src/main.py`, `src/app.tsx`, `app/page.tsx`, and `app/globals.css`
- Added prompt-aware allowance for explicit fresh starts such as `rebuild from scratch`, `new project`, `scaffold`, `starter`, `reset`, `convert`, and `migrate`.
- Wired starter-drift reasons into completion-quality scoring so autopilot keeps working instead of treating a fresh starter as a valid continuation.
- Replaced starter-drift model drafts with safer continuation patches when a safe fallback is available.
- Added a safe rejection path when no safe continuation patch is available.
- Added adversarial parser regressions for:
  - broad continuation accidentally generating a fresh C++ starter
  - explicit rebuild-from-scratch still being allowed
  - completion quality catching starter drift for autopilot
- Added stress-script source contracts so future stress runs catch accidental removal of the starter-drift guard.

### Validation

- Focused agent/parser regression tests passed: `67 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `365 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Destructive Draft Safety Update

### Summary

This update adds another guardrail for long-running coding-agent work: Aegis now detects model drafts that try to delete files or empty important source/build files without the latest prompt explicitly asking for destructive cleanup. This protects native apps, DLLs, drivers, web apps, and other project work from accidental model drift where a valid-looking JSON draft could remove core files during autopilot or a vague `continue` turn.

### Highlights

- Added prompt-aware destructive-change detection for model drafts.
- Blocked unrequested deletes of important project files such as:
  - `src/`, `app/`, `components/`, `driver/`, `controller/`, `host/`, `library/`, `include/`
  - `CMakeLists.txt`, `.sln`, `.vcxproj`, `.csproj`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, and related config/build files
  - `.aegis/` project memory files
- Blocked empty rewrites of important project/source files unless the user clearly asks for a reset/rewrite/delete-style action.
- Allowed explicit destructive work when the latest prompt clearly asks to delete, remove, replace, split, move, merge, or rebuild from scratch.
- Wired destructive-draft reasons into completion-quality scoring so autopilot treats risky drafts as `needs_work` instead of ready.
- Replaced destructive model drafts with safer additive deterministic fallbacks when a good fallback is available.
- Added a safe rejection path when no safe fallback exists, preventing risky changes from being applied.
- Expanded implementation intent detection for realistic wording like `improving`, `optimizing`, and `fixing`.
- Added adversarial parser regressions for unrequested source deletion, explicit deletion, and autopilot quality scoring.
- Added stress-script source contracts so future stress runs detect if destructive draft protection is removed.

### Validation

- Focused agent/parser regression tests passed: `64 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `362 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Agent Draft Contract Guard Update

### Summary

This update hardens the structured coding-agent path after the model returns a draft. Aegis now checks whether a proposed patch contains real source work and whether it matches the saved workspace mission contract before the files are accepted for apply/validation. This targets the failure class where a native C++/DLL/CMake project could receive a stale or accidental website starter after a follow-up prompt mentioned words like `dashboard` or `frontend-style`.

### Highlights

- Added a concrete source-surface guard so implementation drafts made only of metadata/config files do not count as a complete project pass.
- Added manifest-aware stack-family detection for saved mission contracts:
  - native C++/CMake
  - .NET/C#
  - Python
  - Rust
  - Go
  - web/frontend
- Added a draft contract mismatch guard that rejects off-stack drafts when the workspace manifest says to preserve the original mission.
- Replaced off-stack model drafts with the stack-aware deterministic fallback when a safe fallback is available.
- Added a safe rejection path so a bad off-stack draft is not applied if no better fallback can be produced.
- Expanded model context with the saved mission contract, original task, and an explicit rule to preserve the stack unless the latest prompt asks to convert, migrate, or switch stacks.
- Added adversarial regressions for native workspaces receiving accidental web drafts and project drafts with no source files.
- Added stress-script source contracts so future stress runs catch mission-contract draft guards.

### Validation

- Focused agent/parser regression tests passed: `61 passed, 10 subtests passed`.
- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `359 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Mission Contract Continuity Update

### Summary

This update hardens Aegis for long-running coding tasks where the user gives a project once, then sends short follow-ups like `continue`, `add a dashboard`, or `make it production ready`. New scaffolds now save a persistent mission contract in `.aegis/project.json`, and the planner reuses that contract to keep the original stack, framework, validation command, and project family unless the user clearly asks for a new project, rewrite, migration, or stack conversion.

### Highlights

- Added a `.aegis/project.json` `mission_contract` with:
  - selected preset id and label
  - stack family
  - stack-lock signals
  - framework, language, package manager
  - original prompt
  - install and validation commands
  - continuity policy
- Added a mission-continuity guard so ambiguous follow-ups with words like `frontend` or `dashboard` do not silently convert native/DLL work into a web stack.
- Kept explicit stack changes working when the prompt clearly asks for a new project, conversion, rewrite, migration, or fresh scaffold.
- Added planner support for manifests where the main `preset_id` is missing but the mission contract still has the selected preset.
- Added live stress coverage for the exact drift class that previously caused C++/DLL/native work to wander into website-style files.

### Validation

- Project-scaffolder regression tests passed: `114 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `356 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Existing Project Continuation Drift Update

### Summary

This update fixes another realistic multi-turn coding-agent failure: after Aegis has already identified an existing native project, vague follow-ups such as `continue`, `continue building this`, or `keep going and make it production ready` should not create starter files or drift into a generic web scaffold. Aegis now treats those continuation prompts as existing-project validation/repair work when build files or an Aegis manifest are present, and it preserves the current native stack when the user asks for a settings UI or dashboard while explicitly saying not to make a website.

### Highlights

- Routed bare continuation prompts into existing-project validation when the target already has a manifest or build files:
  - `continue`
  - `continue building this`
  - `keep going and make it production ready`
  - `make it complete`
- Preserved C++ DLL/shared-library continuity for follow-ups like `add a settings UI but do not turn it into a website`.
- Preserved native/solution continuity for dashboard wording like `add a dashboard to show logs without making a website`.
- Expanded web-negation handling for `without making a website` and related phrasing.
- Added unit regressions and live HTTP stress contracts for the no-starter-file/no-web-drift continuation path.

### Validation

- Project-scaffolder regression tests passed: `112 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Adversarial planner sweep passed for C++ DLL, Visual Studio solution, and no-manifest CMake continuation scenarios.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `354 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Instruction-Like Folder Name Path Update

### Summary

This update fixes another first-prompt reliability issue found through adversarial path testing. Some legitimate Windows folder names contain words that also look like instructions, such as `With Tests`, `Using CMake`, `And Then Some`, `For Me`, or `Launch Tool`. Aegis could trim those words out of the target path before planning the project, which risked creating or modifying the wrong sibling folder. The path planner now preserves those folder names while still cutting off real follow-up instructions like `with CMake and validate it` or repeated location phrases like `at this path`.

### Highlights

- Preserved instruction-like words inside explicit Windows folder names:
  - `C:\...\Aegis Tool With Tests`
  - `C:\...\Aegis Built Using CMake`
  - `C:\...\Aegis Game And Then Some`
  - `C:\...\Aegis Project For Me`
  - `C:\...\New Launch Tool`
- Kept repeated prompt-location text out of workspace names, such as `C:\...\Aegis Game Dumper at this path create...`.
- Improved action-boundary selection so Aegis prefers the real follow-up action without shortening the requested folder.
- Added regressions for folder names that contain instruction-like words and for connector prompts that should still stop at the instruction boundary.
- Added live stress-script contracts so the HTTP project planner keeps these paths intact.

### Validation

- Project-scaffolder regression tests passed: `108 passed, 42 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Adversarial planner sweep passed for instruction-like folder names, repeated location phrases, and build-validation intent.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `350 passed, 90 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, arbitrary instruction files, and prompt contract checks.

## 2026-05-03 - Windows Path Wrapper Punctuation Update

### Summary

This update fixes another prompt-to-workspace reliability issue found during adversarial path testing. Windows folders commonly include wrapper punctuation from downloads, archives, and versioned copies, such as `Project (1)`, `Tool [Beta]`, or `Build {Draft}`. Aegis previously treated some trailing wrapper characters as dangling prompt punctuation and could drop them from the parsed workspace path. That could make the agent work in the wrong folder or create a sibling folder with the wrong name.

### Highlights

- Preserved balanced wrapper punctuation in explicit Windows paths:
  - `C:\...\Aegis Tool (1)`
  - `C:\...\Aegis Tool [Beta]`
  - `C:\...\Aegis Tool {Draft}`
- Preserved apostrophes inside unquoted folder names, such as `Rick Culler's Website`.
- Kept cleanup for truly dangling prompt wrappers, such as `(at this path C:\...\Aegis Tool)`.
- Added regressions for balanced punctuation, apostrophes, and dangling prompt wrappers.
- Added live stress-script contracts so the API path planner keeps wrapper and apostrophe paths intact.

### Validation

- Project-scaffolder regression tests passed: `106 passed, 37 subtests passed`.
- Focused prompt routing and intent tests passed: `40 passed, 34 subtests passed`.
- Adversarial punctuation sweep passed for parentheses, brackets, braces, apostrophes, quoted paths, and trailing slashes.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `348 passed, 85 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, generic instruction files, and prompt contract checks.

## 2026-05-03 - Failed Build Follow-Up Repair Update

### Summary

This update hardens the follow-up behavior after a generated or existing project fails validation. Real user prompts like `continue from the last failed build`, `rerun the build`, or `try building again` should not create more starter files or wait for the user to repeat the original request. Aegis now treats those phrases as build/repair intent, keeps the active workspace pinned, and routes existing projects into validation mode.

### Highlights

- Expanded the shared validation-intent phrase matrix for failed-build continuations:
  - `continue from the last failed build`
  - `rerun the build`
  - `rerun validation`
  - `try building again`
  - `run it again`
- Fixed a stress-found case where `continue from the last failed build` reused the workspace but did not enable validation.
- Added regression coverage for existing CMake workspaces without an Aegis manifest, so build-file detection alone is enough to continue validation.
- Added live stress-script contracts to keep failed-build follow-ups pinned to the active workspace and validation loop.
- Rechecked quoted paths, trailing slashes, and path labels such as `Path: "C:\...\Project" - refine...`; those flows remained healthy.

### Validation

- Prompt-intent tests passed: `4 passed, 25 subtests passed`.
- Project-scaffolder regression tests passed: `104 passed, 33 subtests passed`.
- Prompt-routing regression tests passed: `36 passed, 9 subtests passed`.
- Adversarial follow-up sweep passed for `you didnt build it?`, `fix the build error and run it again`, `continue from the last failed build`, `rerun the build`, and `try building again`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `346 passed, 81 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, generic instruction files, and prompt contract checks.

## 2026-05-03 - Instruction Separator Path Parsing Update

### Summary

This update fixes another realistic first-prompt path parsing edge case. When a user wrote an explicit path followed by punctuation, such as `C:\...\Aegis Native DLL - refine my existing DLL project`, Aegis could keep the separator as part of the folder name. That small path leak could make the planner miss the intended workspace and later drift into the wrong stack. Aegis now recognizes instruction separators after explicit Windows paths while still preserving legitimate folder names like `Aegis-Optimize-Tools` and `Aegis Cleanup Tool`.

### Highlights

- Added separator-aware Windows path parsing for:
  - `C:\...\Project - refine...`
  - `C:\...\Project: optimize...`
  - `C:\...\Project; clean up...`
  - `C:\...\Project, improve...`
- Protected hyphenated and action-word folder names so project names are not shortened accidentally.
- Added focused regressions for separator-delimited DLL, CMake, C++ solution, and website prompts.
- Expanded the stress script with a live API contract for separator-based native DLL refinement.

### Validation

- Project-scaffolder regression tests passed: `103 passed, 33 subtests passed`.
- Prompt-routing regression tests passed: `36 passed, 9 subtests passed`.
- Adversarial separator sweep passed for DLL refinement, CMake optimization, C++ solution cleanup, website improvement, hyphenated folders, and long C++ SLN instructions with commas.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `345 passed, 76 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, generic instruction files, and prompt contract checks.

## 2026-05-03 - Natural Refinement Path Boundary Update

### Summary

This update fixes another first-prompt adherence issue found during adversarial, user-style testing. Prompts such as `at this path C:\...\Aegis Native DLL refine my existing DLL project and build it` could still let natural refinement verbs become part of the parsed folder path. That caused the deterministic planner to miss the real existing project, pick the wrong preset, or require the user to repeat the request. Aegis now treats `refine`, `optimize`, `clean up`, `polish`, `modernize`, and `improve` as contextual instruction boundaries after explicit Windows paths.

### Highlights

- Hardened explicit path parsing for natural project-maintenance prompts:
  - `refine my existing DLL project`
  - `optimize this existing C++ CMake project`
  - `clean up this C++ solution`
  - `improve this existing website`
- Preserved folder names that legitimately contain those words, such as `Aegis Optimize Tools`.
- Expanded negated-web detection for wording like `without converting it to a website`.
- Fixed DLL/plugin preset scoring so `DLL plugin` plus `native` stays on the C++ DLL/shared-library preset instead of drifting to a generic CMake CLI.
- Added focused regression tests and live stress-script contracts for the natural refinement path parser and native DLL/plugin scoring.

### Validation

- Project-scaffolder regression tests passed: `101 passed, 29 subtests passed`.
- Prompt-routing regression tests passed: `36 passed, 9 subtests passed`.
- Adversarial prompt sweep passed for existing DLL refinement, CMake optimization, C++ solution cleanup, WPF modernization without website conversion, website improvement, build follow-up, path-based project Q&A, and native DLL plugin prompts.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `343 passed, 72 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, generic instruction files, and prompt contract checks.

## 2026-05-03 - Prompt Adherence Stress Hardening Update

### Summary

This update tightens Aegis around the exact failure pattern found during realistic bug hunting: first prompts that include a path, a stack, and natural language such as `design and build...` must keep the selected folder and requested project type pinned from the start. Aegis now avoids swallowing instruction words into Windows paths, avoids letting negated website wording poison native/DLL routing, and keeps pure technical questions in chat mode without advertising a fake coding route.

### Highlights

- Fixed Windows path extraction for prompts like `at this path C:\...\Designed DLL design and build a C++ DLL project`.
- Preserved folder names that legitimately contain `Design`, such as `Aegis Design Tools`.
- Hardened the planner so `design and build...` is implementation work, while explicit `plan the architecture...` remains planning.
- Prevented phrases like `without turning it into a website` from switching native/DLL work to a web route.
- Cleared specialist route-profile metadata for plain conversational questions such as `what is a DLL?`, keeping the UI route/status panel aligned with direct chat behavior.
- Added stress-script contracts for the design-path parser, negated-web suppression, and conversational DLL question routing.

### Validation

- Project-scaffolder regression tests passed: `99 passed, 24 subtests passed`.
- Prompt-routing regression tests passed: `35 passed, 9 subtests passed`.
- Adversarial prompt sweep passed for C++ SLN, C++ DLL, ImGui Win32/DX11, static website, existing DLL refinement, solution merge, design-word folder names, and plain DLL questions.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `340 passed, 67 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, readiness continuation, generic instruction files, and prompt contract checks.

## 2026-05-03 - Natural Developer Prompt Routing Update

### Summary

This update fixes a first-message adherence bug found during realistic user-style stress testing. Natural coding prompts such as `refine my existing DLL project`, `work on my existing DLL project`, `optimize this native project`, and `clean up this C++ project` were too easy for Aegis to treat as normal chat, which meant the structured coding-agent path could be skipped unless the user repeated themselves. Aegis now recognizes those developer verbs as code-changing intent when they are attached to a project, file, DLL, tool, native app, or other build artifact.

### Highlights

- Expanded direct-chat safeguards so natural implementation verbs route into the structured agent instead of a lightweight chat stream.
- Updated the task planner so `refine`, `work on`, `optimize`, `clean up`, `polish`, `modernize`, `repair`, and related wording are classified as implementation work when paired with code/project terms.
- Updated deterministic fallback routing so local/offline passes treat existing native and DLL refinement as project work rather than plain Q&A.
- Added regressions for existing C++/DLL/native prompts that previously needed repeated user instructions.
- Added a live stress-script contract for the agent, planner, and fallback layers so natural developer prompt routing stays protected outside unit tests.
- Preserved normal chat behavior for plain questions such as `what is a DLL?`.

### Validation

- Reproduced the original failure before patching: natural DLL/native prompts incorrectly allowed direct chat.
- Confirmed the fixed behavior: existing DLL/native refinement prompts now return `direct_stream=False`, while plain conceptual questions still return `direct_stream=True`.
- Prompt-routing tests passed: `32 passed, 6 subtests passed`.
- Project-scaffolder plus streaming contract tests passed: `107 passed, 24 subtests passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `335 passed, 64 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration and scaffold smoke coverage for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, and readiness continuation.
- Local backend stress re-ran after the stress contract update and passed with `backend_natural_prompt_contract_smoke=true`.

## 2026-05-03 - Visual Studio Solution Routing Update

### Summary

This update fixes a first-prompt routing bug found during user-style stress testing. Prompts such as `at this path C:\...\Solution Tool combine two Visual Studio sln projects...` could be parsed as one giant folder path, which stripped the real instruction from the prompt and caused Aegis to fall back to a generic web starter. Aegis now stops explicit Windows paths before solution merge/split/extract instructions, preserves action words inside real folder names, and routes Visual Studio solution refactor work into the correct tool preset.

### Highlights

- Added contextual path-boundary handling for `combine`, `merge`, `split`, `separate`, and `extract`.
- Added a `stack-lock:solution-refactor` signal so solution merge/split prompts cannot silently drift into web scaffolds.
- Preserved target-folder names like `Aegis Merge Tool` when the action word is part of the folder name.
- Added regressions for Visual Studio solution merge and split prompts.
- Expanded live stress coverage so the backend API now checks solution-refactor prompt routing.

### Validation

- Prompt drift stress passed for C++ SLN, DLL refinement, solution merge/split, ImGui, action-word folders, static websites, and WPF desktop prompts.
- Targeted project-scaffolder tests passed: `97 passed, 24 subtests passed`.
- Prompt-routing plus streaming tests passed: `40 passed`.
- Root web validation passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `333 passed, 58 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed with `1/1` API iteration.
- Scaffold smoke passed for C++ SLN, C++ DLL host loading, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, CMake validation, diagnostic extraction, and readiness continuation.

## 2026-05-03 - Web Workspace Validation Wrapper Update

### Summary

This update fixes a developer workflow gap found during stress validation. The web app lives under `website/frontend`, so running `npm test` or `npm run build` from the `website` workspace root failed even though the frontend itself was healthy. Aegis now has root-level web workspace scripts that delegate to the frontend and backend, making the copied/moved web workspace easier to validate from one stable folder.

### Highlights

- Added `website/package.json` with root-level scripts for:
  - `npm test -- --run`
  - `npm run build`
  - `npm run backend:test`
  - `npm run validate`
- Documented the root-level web validation commands in the web workspace README.
- Added a real `AgentEngine` regression for prompt-selected stream metadata.
- Confirmed stream metadata resolves explicit prompt paths without creating preview-only target folders.

### Validation

- Prompt-routing plus streaming tests passed: `40 passed`.
- Root web test wrapper passed from `website`: `3 files`, `18 tests`.
- Root web validation wrapper passed from `website`: frontend tests, frontend production build, and backend tests.
- Full backend regression suite passed through the wrapper: `331 passed, 58 subtests passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed on `http://127.0.0.1:8797` with `1/1` API iteration, prompt-workspace stream metadata contracts, native continuity command smoke, generic instruction smoke, and backend child cleanup.

## 2026-05-03 - Prompt Workspace Stream Metadata Update

### Summary

This update fixes a streaming contract mismatch found during continuation stress testing. Aegis already executed explicit-path prompts inside the folder named by the user, but the first server-sent `meta` event could still report the previously selected workspace. The desktop UI now receives the agent's effective prompt-selected workspace from the first streamed event, keeping the visible active workspace aligned with the files Aegis is actually planning, editing, validating, and repairing.

### Highlights

- Added a lightweight agent resolver for stream metadata workspace selection.
- Updated chat streaming `meta` events to report the same effective workspace that the structured agent will use.
- Preserved fallback behavior for fake/test agents and resolver failures.
- Added an SSE regression proving prompt-selected workspaces beat stale selected workspaces in stream metadata.
- Expanded the stress source contracts so future stress runs fail if prompt-aware stream metadata is removed.

### Validation

- Streaming contract tests passed: `10 passed`.
- Prompt-routing plus streaming tests passed: `39 passed`.
- Full backend regression suite passed: `330 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed on `http://127.0.0.1:8797` with `1/1` API iteration, prompt-workspace stream metadata contracts, native continuity command smoke, generic instruction smoke, and backend child cleanup.

## 2026-05-03 - Action Word Path Parsing And Native Adherence Update

### Summary

This update fixes another prompt-path edge case found during hands-on bug hunting. Folder names that contain action-like words, such as `Aegis Build Tools New`, could be trimmed too aggressively because the parser treated `build` as the beginning of the instruction instead of part of the folder name. Aegis now uses contextual action-word boundaries so explicit path prompts keep the intended folder name while still stopping correctly before real instructions like `create`, `run`, `validate`, and `work on`.

### Highlights

- Hardened Windows path extraction for folder names containing words such as `Build`, `Run`, `Tools`, or `New`.
- Shared the improved deterministic project-builder path parser with the normal chat/agent path resolver.
- Added contextual action-boundary detection so path parsing checks the word after verbs before deciding that the path ended.
- Preserved explicit-path behavior for suffix wording such as `Aegis Game Dumper at this path`.
- Added a native DLL/CMake regression proving an existing native project at an action-word path stays native and does not get converted into web files.
- Expanded stress source contracts so future stress runs fail if the contextual path boundary helper is removed.

### Validation

- Action-word prompt-path stress passed for existing folders, new folders, quoted paths, `at this path`, and `at this location`.
- Targeted project-scaffolder tests passed: `95 passed, 24 subtests passed`.
- Targeted prompt-routing tests passed: `29 passed`.
- Full backend regression suite passed: `329 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed on `http://127.0.0.1:8797` with `1/1` API iteration, native continuity command smoke, generic instruction smoke, prompt-workspace/source contracts, and backend child cleanup.

## 2026-05-03 - Explicit Prompt Workspace Targeting Update

### Summary

This update fixes a real prompt-to-filesystem bug found during user-style stress testing. When the UI had one active workspace selected but the user prompt named a different path, the regular chat/agent path could still write into the selected workspace instead of the path inside the prompt. Aegis now resolves explicit Windows paths from build/develop/validation prompts as the effective workspace before scanning, planning, writing files, applying changes, or running validation.

### Highlights

- Added prompt-aware workspace resolution to the core agent path used by normal chat runs.
- Applied the same prompt workspace selection to route preview and direct-stream eligibility checks.
- Prevented first-pass build prompts from writing generated files into the wrong selected/base workspace.
- Improved Windows path trimming so phrases such as `at this path`, `at this location`, `in this folder`, `build`, `run`, `validate`, and `work on` are not accidentally captured as part of the folder name.
- Added a live workspace event when Aegis switches to a user-specified path from the prompt.
- Updated chat cache invalidation so the originally selected workspace and the actual prompt-selected workspace are both refreshed after a run.
- Added regressions proving explicit target folders are used for generated C++ projects and route preview does not create preview-only folders.

### Validation

- Explicit-path engine stress passed: a C++ solution request with a selected base workspace created and built inside the nested prompt target path, while the base workspace stayed clean.
- Targeted prompt-routing tests passed: `27 passed`.
- Targeted scaffold/fallback/parser regressions passed: `173 passed, 34 subtests passed`.
- Explicit path-preview stress passed for DLL/native, website, and C++ prompt variants.
- Local backend live stress passed on `http://127.0.0.1:8797` with `1/1` API iteration, prompt-workspace source contracts, native continuity command smoke, generic instruction smoke, and backend child cleanup.
- Full backend regression suite passed: `326 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-03 - Task Contract And Stack Drift Hardening Update

### Summary

This update targets the biggest real-world reliability issue found during hands-on prompt stress testing: Aegis could sometimes require a second instruction before creating the requested project, or could drift from the assigned stack after reading stale workspace memory. The planner, deterministic scaffolder, fallback engine, and agent contract now treat the newest explicit user prompt as the authoritative source for target path, language, artifact type, and validation intent.

### Highlights

- Added current-prompt stack override detection so stale `.aegis/project.json` memory cannot turn a fresh C++, DLL, desktop, or native request into a web scaffold.
- Added preset stack-lock comparison for web, desktop, native C++, C++ DLL, C#/.NET, Python, and Rust project families.
- Reordered deterministic fallback routing so explicit native/C++/DLL prompts beat existing Next/Vite workspace shape.
- Fixed Electron project continuity to reuse the valid `electron-react-ts` preset instead of an invalid continuity id.
- Strengthened the full-build contract context so the latest user request stays authoritative for:
  - target path
  - language and stack
  - artifact type
  - build/run/test validation
  - overwrite/repair behavior
- Preserved existing project continuity for follow-up prompts such as `continue`, `fix the errors`, and `run validation again` without allowing continuity to migrate the project into another stack.
- Added regression coverage for stale-web-to-native prompts, fresh DLL creation inside old web workspaces, first-pass C++ solution creation, and valid Electron continuation.
- Expanded the stress script with source-contract checks and a stale web manifest API stress case.

### Validation

- Hard prompt-adherence stress passed: first-pass C++ solution creation, native follow-up continuity, stale web manifest to C++ DLL override, stale native manifest to website override, and fallback native-over-web routing.
- Targeted project-scaffolder tests passed: `94 passed, 24 subtests passed`.
- Targeted fallback-engine tests passed: `21 passed`.
- Targeted agent-parser tests passed: `58 passed, 10 subtests passed`.
- Full backend regression suite passed: `324 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Large Project And Giant File Readiness Update

### Summary

This update adds structured support for very large coding tasks, including monolithic source files that can reach hundreds of thousands of lines. Aegis now detects giant text files during workspace scan, indexes them through bounded samples, includes safe large-file summaries in model context, exposes targeted line-slice reads, and supports staged append changes so huge generated files do not require one unsafe whole-file rewrite.

### Highlights

- Added large-file metadata to workspace file entries:
  - `is_large`
  - `estimated_lines`
  - `large_file_strategy`
- Added large text file detection for million-byte source files and line-count estimation for very large files.
- Added sampled context blocks for giant files with head/tail excerpts, estimated line counts, and explicit guidance to avoid whole-file rewrites.
- Added `/api/file/slice` so the UI/agent can request targeted line ranges from giant files instead of reading the full file.
- Updated the project indexer so large files are sampled and searchable instead of skipped.
- Updated task planning so 500k-line/single-file/large-file prompts activate a chunked large-task protocol.
- Added a large-file inventory section to model prompts so Aegis can reason about monoliths and long-running refactor work.
- Added an `append` file-change action for staged generation or extension of large files across multiple passes.
- Expanded frontend/backend shared file-change typing so append operations remain type-safe.

### Validation

- Focused large-file and append-diff tests passed: `5 passed`.
- Full backend regression suite passed: `320 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Local backend live stress passed on `http://127.0.0.1:8797` with `1/1` API iteration, native continuity command smoke, generic instruction smoke, source contract checks, and backend child cleanup.

## 2026-05-02 - Verification Chain Completion And Strict Backend Identity Update

### Summary

This update fixes a subtle verification edge case found by the live backend scaffold stress suite and hardens desktop/backend identity checks. Safe chained build commands, such as CMake configure plus build, now stay together once selected so Aegis cannot run only the configure half and incorrectly treat the workspace as verified. The desktop launcher also refuses stale or foreign health responses that omit `project_root` or report a different project root.

### Highlights

- Updated the verification planner to complete a selected safe `&&` command chain even when the caller requested a very small step budget.
- Added regression coverage proving a CMake workspace still runs both `cmake -S . -B build` and `cmake --build build` when `max_steps=1`.
- Strengthened the CMake live stress smoke to require both `verification:configure` and `verification:build` history entries.
- Added a local backend stress wrapper that starts the checked-out `website` backend on an isolated port, verifies the reported `project_root`, runs the full smoke suite, and cleans up child backend processes afterward.
- Hardened the desktop health gate so `ready` responses without `project_root`, or invalid health JSON, cannot be accepted as the configured backend.
- Hardened the local stress wrapper so a foreign service on the preferred port is skipped instead of being trusted or overwritten.
- Added `-RunForeignHealthSmoke` to the local backend stress wrapper so stale/foreign health collisions can be reproduced without ad hoc shell jobs.
- Added `-RunForeignProjectRootSmoke` to reproduce a more realistic stale-backend collision where `/api/health` is ready and valid-looking but belongs to a different checkout/project root.
- Added cleanup safeguards so fake health collision jobs are stopped even when port selection fails early.
- Added per-iteration health-root assertions to the live stress script so root drift is caught during long runs, not only at startup.
- Updated the backend start script to accept `-Port`, `-HostName`, and `-Reload` so desktop/local stress runs can honor the configured API URL instead of hardcoding port `8787`.
- Updated desktop backend launch command construction so a custom `api_base_url` port is passed to the PowerShell backend launcher.

### Validation

- Targeted verification tests passed: `16 passed, 4 subtests passed`.
- Full backend regression suite passed: `315 passed, 58 subtests passed`.
- Foreign health simulation passed through `-RunForeignHealthSmoke`: a fake `ready` server on `http://127.0.0.1:8797` without `project_root` was rejected, and the local backend stress wrapper moved to `http://127.0.0.1:8798`.
- Foreign health plus scaffold smoke passed through `-RunForeignHealthSmoke -RunScaffoldSmoke`, including backend child cleanup and no lingering jobs/listeners afterward.
- Foreign project-root simulation passed through `-RunForeignProjectRootSmoke`: a fake `ready` server on `http://127.0.0.1:8797` reported `C:\Users\gabri\AppData\Local\Temp\aegis-foreign-project-root-smoke`, was rejected, and the local backend stress wrapper moved to `http://127.0.0.1:8798`.
- Foreign project-root plus scaffold smoke passed through `-RunForeignProjectRootSmoke -RunScaffoldSmoke`, including CMake, MSVC solution, DLL host loader, MinHook adapter, existing-project continuity, diagnostic extraction, and readiness continuation coverage.
- Local backend live scaffold stress passed on `http://127.0.0.1:8797` with CMake, MSVC console solution, C++ DLL host loader, Windows internals MinHook adapter, Visual Studio solution materialization, existing-project continuity, diagnostic extraction, and readiness continuation smoke coverage.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Backend Identity And Intent Stress Update

### Summary

This update prevents the desktop app from silently connecting to an older Aegis backend on the same port and fixes a prompt-intent edge case found during live stress testing. Aegis now verifies that `/api/health` belongs to the configured local backend root before accepting the connection, and validation intent matching now handles punctuation-heavy prompts such as `tests, and validation`.

### Highlights

- Added desktop backend identity validation against the health endpoint's reported `project_root`.
- Added fail-fast startup messaging when a stale backend is already running on the configured API URL.
- Added client-side health rejection so reconnect/refresh flows cannot mark the wrong backend as connected.
- Updated the stress script to prefer the local `website/backend` sources instead of the legacy `Aegis/Website/ChatBot` copy.
- Improved shared prompt-intent normalization so punctuation around `tests`, `validation`, and `build/run` no longer hides validation intent.
- Added prompt-intent regression coverage for full-stack validation wording and slash-separated build/run wording.

### Validation

- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Full backend regression suite passed: `314 passed, 58 subtests passed`.
- Prompt-intent targeted tests passed: `4 passed, 20 subtests passed`.
- Project-scaffolder validation/full-stack targeted tests passed: `21 passed, 70 deselected, 4 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Local backend live stress run passed on `http://127.0.0.1:8797` with `1/1` API iteration, required presets verified, local backend source contracts verified, and no failures.

## 2026-05-02 - Scaffolder Verification Plan Alignment Update

### Summary

This update closes a reliability gap between Aegis' dynamic verification planner and the deterministic project scaffolder. Generated `.aegis/validation_plan.json` files now preserve safe chained command segments exactly, including quoted Windows tool paths, and label CMake configure/build phases correctly for future repair and autopilot passes.

### Highlights

- Updated deterministic scaffold validation-plan generation to use quote-aware safe `&&` splitting.
- Preserved quoted Windows executable paths exactly instead of rebuilding command text from shell tokens.
- Added configure/build phase labels to generated validation-plan steps.
- Added explicit step ids such as `configure-1` and `build-2` for generated native/CMake plans.
- Kept malformed or unsafe shell chains as one unsplit command so blocked syntax is not accidentally trusted as separate safe steps.
- Added regression coverage for:
  - generated CMake validation-plan phases;
  - quoted Windows CMake executable paths;
  - malformed and unsafe chain syntax;
  - generated `.aegis/validation_plan.json` content.

### Validation

- Targeted scaffolder CMake/validation-plan tests passed: `7 passed, 84 deselected, 4 subtests passed`.
- Targeted validation manager tests passed: `13 passed, 4 subtests passed`.
- Full backend regression suite passed: `314 passed, 58 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Transparent Verification Chain Update

### Summary

This update makes Aegis' build and repair workflow clearer for native and multi-step projects. Safe chained verification commands are now expanded into visible configure/build/test steps, so the activity feed, validation planner, and repair loop can show exactly which part of a build pipeline is running or failing.

### Highlights

- Split safe `&&` verification chains into individual planner steps.
- Replaced token-rebuilt splitting with a quote-aware scanner so pinned Windows paths like `"C:\Program Files\CMake\bin\cmake.exe"` are preserved exactly.
- Added chain metadata to verification steps:
  - original source command;
  - current chain index;
  - total chain length.
- Improved CMake phase labeling so `cmake -S . -B build` appears as configure work and `cmake --build build` appears as build work.
- Improved quoted CMake executable detection so custom pinned CMake profiles still show configure/build phases correctly.
- Preserved command safety behavior for unsafe shell operators; blocked or unsupported shell syntax is not silently flattened into trusted steps.
- Kept the backend command runner's existing safe sequential execution support intact while making the planned work easier to display and debug.

### Validation

- Targeted validation manager and command-chain tests passed: `23 passed, 4 subtests passed`.
- Targeted agent parser validation/command tests passed: `17 passed, 41 deselected`.
- Targeted autopilot, scaffolder, and prompt-intent tests passed: `99 passed, 40 subtests passed`.
- Full backend regression suite passed: `312 passed, 54 subtests passed`.
- Frontend UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Shared Prompt Intent Reliability Update

### Summary

This update centralizes Aegis' execution-intent language so the chat agent and deterministic project builder agree on when a prompt means build, run, launch, validate, repair, or stay in normal explanation chat.

### Highlights

- Added a shared prompt-intent matcher for execution/validation phrases.
- Expanded validation wording for `verify the build`, `check for errors`, `ensure there are no errors`, and `compile the app`.
- Moved agent validation-intent detection onto the shared matcher.
- Moved project-scaffolder validation intent onto the shared matcher while keeping scaffold-specific `with tests` and validation extras.
- Added explanatory-prompt protection to existing-project validation planning.
- Hardened embedded Windows path parsing so trailing action words like `launch`, `start`, `run`, `verify`, `check`, and `ensure` are treated as instructions without chopping real folder names such as `Existing Launch App`.
- Added stronger new-project path parsing so folder names with action-looking words, such as `New Launch Tool`, do not get shortened before the scaffold verb.
- Added a prompt-intent regression matrix covering:
  - build/run/launch/start/execute/verify/compile/fix phrases;
  - normal creation prompts that should not auto-run validation;
  - explanatory prompts such as `how do I launch it?`;
  - scaffolder-specific extra validation phrases.

### Validation

- Prompt-intent matrix tests passed.
- Targeted backend launch/run validation intent tests passed.
- Targeted project-scaffolder launch/existing-project validation tests passed.
- Synthetic embedded-path action sweep passed for launch/start/execute/run/validate/verify/compile/test/check/ensure prompts.
- Full backend regression suite passed: `310 passed`.
- Frontend queue/UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Prompt-Driven Launch Intent Expansion

### Summary

This update teaches Aegis to treat `launch`, `start`, and `execute` wording as build/run validation intent when a workspace is active, while still leaving explanatory prompts in normal chat.

### Highlights

- Added launch/start/execute phrasing to the backend validation-intent detector.
- Added matching launch/start/execute detection to the deterministic project scaffolder.
- Existing-project planning now keeps `launch the app`, `start the project`, and `execute it` in validate-existing mode instead of falling back to fresh starter scaffolds.
- Added explanatory-prompt guards to the scaffolder so prompts like `how do I launch it?` do not accidentally run validation.
- Added regression coverage for launch/start/execute intent detection across both the agent and scaffolder paths.

### Validation

- Targeted backend launch/start/execute intent tests passed.
- Targeted project-scaffolder validation/existing-project launch tests passed.
- Full backend regression suite passed: `304 passed`.
- Frontend queue/UI tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Prompt-Driven Run Intent Expansion

### Summary

This update expands the prompt-driven validation lane so Aegis treats `run it`, `run this`, `run the project`, `build and run`, and `verify this` as coding-agent validation work when a workspace is active.

### Highlights

- Added run/verify phrasing to the backend validation-intent detector.
- Structured agent execution now handles `run it please` without requiring the UI validation toggle.
- Direct chat streaming is bypassed for run/verify/build execution prompts so they do not get answered as plain conversation.
- Added false-positive guards so explanatory prompts like `how do I run it?` can still be treated as normal questions.
- Added regression coverage for:
  - run-intent validation without the UI toggle;
  - direct-chat bypass for run-intent prompts;
  - build-and-run and verify phrase detection;
  - avoiding false positives on explanation prompts.

### Validation

- Targeted backend run/validation-intent tests passed.
- Targeted project-scaffolder validation/run tests passed.
- Full backend regression suite passed: `301 passed`.
- Frontend queue tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Prompt-Driven Validation Intent Update

### Summary

This update makes Aegis respect validation intent directly from the user's prompt. If the user says to build, compile, validate, test, or fix build errors, the backend now treats that as a request to run validation even when the UI validation toggle was left off.

### Highlights

- Added prompt-level validation intent detection to the structured agent path.
- Prompts such as `build it`, `compile this`, `run the build`, `make sure there are no errors`, and `you didn't build it` now force the validation path.
- Direct chat streaming is bypassed for prompt-driven validation work so build/test requests stay in the structured coding-agent flow.
- Kept creation prompts separate from validation prompts, so `build a website` still means create the project instead of only running validation.
- Added regression tests for:
  - no-change validation passes;
  - prompt-driven validation without the UI toggle;
  - validation-intent phrase detection;
  - avoiding false positives for normal creation/explanation prompts.

### Validation

- Targeted backend validation-intent tests passed.
- Backend command/validation manager tests passed.
- Full backend regression suite passed: `300 passed`.
- Frontend queue tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Busy Composer Queue Update

### Summary

This update keeps the embedded web composer usable while Aegis is actively working, reconnecting, or recovering from a backend interruption. Instead of forcing the user to wait for the current pass to finish, follow-up instructions can now be queued directly from the prompt box.

### Highlights

- The message input stays editable during active agent work.
- The send button switches into a queue action when Aegis is busy, reconnecting, offline, or failed.
- Follow-up prompts entered during active work are saved to the same durable prompt queue used for backend outages.
- Queued replay messages are protected from being sent twice while a prior turn is still running.
- Added a shared queue-decision helper so the UI and tests use the same busy/reconnect behavior.
- Added regression coverage for:
  - queuing new outbound prompts while busy;
  - queuing new outbound prompts while disconnected;
  - sending queued prompts only after the backend is connected and idle;
  - keeping queued prompts queued if the agent is still busy.

### Validation

- Frontend queue tests passed: `3 files`, `18 tests`.
- Frontend production build passed.
- Full backend regression suite passed: `298 passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Persistent Prompt Queue Update

### Summary

This update makes the web workspace safer during backend outages, refreshes, or desktop restarts by persisting queued prompts instead of keeping them only in React memory.

### Highlights

- Added a persistent queued-message utility module for the embedded web workspace.
- Queued prompts now reload from browser storage when the web UI starts.
- Queue changes are saved automatically as prompts are added, retried, or drained.
- Queued prompts preserve:
  - original prompt text;
  - workspace root;
  - mode;
  - auto-apply setting;
  - validation setting;
  - whether the user message was already recorded in chat history.
- Added queue regression tests for:
  - blank prompt rejection;
  - option preservation;
  - deduping by queue id;
  - max queue length;
  - malformed storage recovery;
  - saving only the newest queued prompts.

### Validation

- Frontend utility tests passed: `3 files`, `16 tests`.
- Frontend production build passed.
- Full backend regression suite passed: `298 passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Frontend Reliability Test Harness Update

### Summary

This update makes the web workspace reliability layer easier to maintain by moving fragile UI-state helpers into focused utility modules with regression tests. The goal is to prevent future changes from breaking saved conversations, reconnect states, or queued prompt behavior without being caught.

### Highlights

- Extracted conversation persistence helpers into a dedicated frontend utility module.
- Extracted backend connection-state helpers into a dedicated frontend utility module.
- Added a Vitest test harness for the embedded web workspace.
- Added regression coverage for:
  - grouping multiple chat messages into one saved conversation;
  - trimming and compacting saved conversation previews;
  - rejecting malformed saved conversation data;
  - limiting saved conversations to 50 entries;
  - deduplicating updated conversation threads;
  - detecting backend/network failures that should be re-queued;
  - avoiding false-positive requeues for normal validation/model errors.
- Fixed the frontend test script to run correctly from Windows folders containing `&` by calling Vitest directly through Node.

### Validation

- Frontend utility tests passed: `2 files`, `10 tests`.
- Frontend production build passed.
- Full backend regression suite passed: `298 passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Connection Queue Reliability Update

### Summary

This update improves long-session reliability in the embedded web workspace. Aegis now tracks backend connection state more explicitly and protects prompts from being lost during backend reconnects or busy agent turns.

### Highlights

- Added explicit backend connection states in the web UI: `Checking`, `Connected`, `Reconnecting`, `Offline`, and `Failed`.
- Added queued prompt handling for times when:
  - the backend is offline or reconnecting;
  - the agent is already busy with another request;
  - a request fails due to a likely backend/network connection issue.
- Queued prompts now auto-send once the backend health check reports that Aegis is connected again.
- Added a visible queued-message badge in the chat status row.
- Preserved queued prompt workspace/mode/apply/validation settings so the resumed request keeps the user's original intent.
- Prevented repeated failed reconnect attempts from silently discarding a user prompt.

### Validation

- Frontend production build passed after the connection-state and queue changes.
- Full backend regression suite passed: `298 passed`.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.

## 2026-05-02 - Web Workspace Continuity Update

### Summary

This update tightens the embedded web workspace for longer coding sessions. The focus is conversation continuity, clearer long-task telemetry, and making the UI expose the planner/autopilot intelligence that the backend already generates.

### Highlights

- Fixed the web conversation rail so a conversation is saved as one thread instead of treating every user message like a separate chat.
- Added browser-local saved conversation persistence with defensive recovery if saved data is missing or malformed.
- Added working conversation restore behavior, including restoring the prior message history and workspace path.
- Preserved New Chat behavior while making sure the previous conversation is saved before a fresh thread starts.
- Added visible Planning Intelligence in the response panel:
  - route profile;
  - task scale;
  - estimated slices;
  - pass-budget hint;
  - selected context file counts;
  - completion-quality score;
  - large-task protocol notes.
- Expanded assistant summaries so saved conversations now retain validation, route scale, and completion-quality context instead of only raw file-change lists.

### Validation

- Frontend production build passed.
- The saved-conversation storage path is guarded against corrupted localStorage payloads.
- UI typing and routing metadata compiled cleanly against the expanded backend response schema.

## 2026-05-02 - Large Task Readiness Update

### Summary

This update expands Aegis for longer, bigger, multi-slice coding work. The focus is to help Aegis stay oriented during full app builds, existing-project refinement, multi-stack work, and autopilot continuation instead of falling back into small placeholder scaffolds.

### Highlights

- Added planner scale metadata: `focused`, `standard`, `large`, and `epic`.
- Added estimated slice counts and pass-budget hints so big jobs can be decomposed before editing.
- Added a large-task protocol to the model prompt context:
  - keep the target path, language, and stack pinned;
  - work in vertical slices;
  - prefer usable project slices over placeholders;
  - update roadmap/TODO/checklist state;
  - capture validation output and blockers.
- Expanded context budgets for large and epic coding work so Aegis can keep more files, memory, validation context, and project decisions in view.
- Raised the default backend context ceiling with `AEGIS_MAX_CONTEXT_CHARS=128000`.
- Added `AEGIS_MAX_WRITE_BYTES` and `AEGIS_MAX_CONTEXT_CHARS` to the generated env template and web workspace example env.
- Added autopilot large-task mode for workspaces with many open instruction items or broad stack signals.
- Increased autopilot pass budgets for large/epic work while keeping normal small-task budgets unchanged.
- Added execution-lane reporting for autopilot, such as `frontend`, `backend`, `database`, `native`, `validation`, and `roadmap`.
- Fixed a routing edge where full-stack prompts containing `database` could be classified as database-only. Full-stack app work now routes as `full-stack-app` instead of losing the frontend/backend scope.

### User Impact

Aegis should now handle prompts like:

```txt
Build a full blown production-grade app with frontend, backend, auth, database, tests, and validation.
```

with a bigger planning envelope:

- full-stack route profile;
- large/epic scale;
- more context files;
- longer autopilot runway;
- explicit slice protocol;
- validation-aware continuation.

Existing native/DLL/C++ prompts still stay on native routes and do not get converted into websites.

### Validation

- Frontend production build passed.
- Desktop Release x64 build passed with `0 errors` and `0 warnings`.
- Full backend regression suite passed: `298 passed, 23 subtests passed`.
- Targeted large-task planner/autopilot tests passed.
- Synthetic stress sweep confirmed:
  - full-stack product prompts route to `full-stack-app`;
  - native/DLL solution prompts route to `native-binary`;
  - large autopilot continuation receives large-task scale and expanded context.

## 2026-05-01 - Native Workspace Continuity Update

### Summary

This update focuses on making Aegis behave more like a reliable coding-agent workspace when the user points it at an existing native project, DLL, library, or tool. The main goal is to prevent Aegis from drifting into unrelated website scaffolds when the prompt is actually asking it to refine an existing C++/DLL workspace.

### Highlights

- Fixed custom desktop window controls so minimize, maximize/restore, and close are handled by the Aegis titlebar buttons.
- Improved Windows path extraction so phrases like `at this path` after a folder name do not become part of the workspace path.
- Added desktop-side routing protection for existing DLL/native refinement prompts.
- Added backend detection for DLL/shared-library artifacts, DynamicLibrary `.vcxproj` projects, `DllMain`, and `__declspec(dllexport)` patterns.
- Added planner continuity for existing DLL/native work so the backend recognizes the target as native code instead of selecting a generic web scaffold.
- Added anti-web intent handling so prompts like `without turning it into a website` no longer add web stack-lock signals.
- Expanded stress contracts so future changes must preserve window chrome behavior, path parsing, stack-drift protection, and DLL/native continuity.

### User Impact

Prompts like the following should now stay focused on the existing native workspace:

```txt
C:\Users\gabri\Desktop\Aegis Game Dumper at this path work on my existing DLL that I already made and refine it
```

Aegis should now:

- Resolve the workspace as `C:\Users\gabri\Desktop\Aegis Game Dumper`.
- Treat the request as existing native/DLL work.
- Preserve the project stack instead of converting it into a website.
- Continue using the selected workspace during autopilot passes.

### Validation

- Desktop release build passed with `0 errors`.
- Focused backend continuity tests passed.
- Full backend regression suite passed: `296 passed`.
- Live planner smoke confirmed an existing DLL refinement prompt selects `cpp-cmake-dll`, keeps `stack-lock:native-library`, and avoids `stack-lock:web`.
- Stress harness passed against the live backend with API checks, scaffold smoke, MSVC console build, C++ DLL host-loader validation, Windows internals/MinHook adapter validation, solution materialization, CMake validation, diagnostic extraction, and readiness continuation checks.

### Known Follow-Up

The desktop C++ app is tracked in the Aegis AI GitHub repository. The Python backend currently lives outside this Git checkout under `C:\Users\gabri\Desktop\Aegis\Website\ChatBot`, so backend runtime changes should be moved into the Git-backed project or into a dedicated backend repository for complete crash-safe restoration.
