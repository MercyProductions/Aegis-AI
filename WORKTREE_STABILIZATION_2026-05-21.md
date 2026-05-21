# Worktree Stabilization

Generated: 2026-05-21

Project root: `C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot`

## Purpose

This is the Phase 0 checkpoint for the ChatBot roadmap. The current tree contains a lot of active product work across Core, website, desktop, extensions, docs, and release tooling. The immediate goal is not to delete or restore anything blindly. The goal is to make the worktree understandable enough that the next phases can proceed in coherent groups.

## Validation Baseline

The following checks were already run during the project review:

| Surface | Command | Result |
| --- | --- | --- |
| Aegis Core | `python -m pytest tests -q` | 309 passed |
| Website backend | `python -m pytest tests -q` | 888 passed, 186 subtests passed |
| Website frontend | `npm test` | 22 test files passed, 190 tests passed |
| Website frontend | `npm run build` | Passed |
| VS Code extension | `npm run test:unit` | Passed |
| VS Code extension | `npm run lint` | Passed |
| VS Code extension | `npm run test:smoke` | Blocked by VS Code `vscode-updating` mutex |
| Native desktop | `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1` | Release x64 build passed with 0 warnings, 0 errors |

Release packaging was intentionally not run because the `release/` artifact folders are already dirty/deleted.

## Current Status Inventory

`git status --short` currently reports 192 entries.

| Group | Entries | Shape |
| --- | ---: | --- |
| `aegis-core` package, docs, tests | 76 | 15 modified, 61 untracked |
| Website backend | 21 | 14 modified, 7 untracked |
| Visual Studio extension | 19 | 13 modified, 6 deleted |
| VS Code extension | 18 | 6 modified, 5 deleted, 7 untracked |
| Repo docs | 17 | 1 modified, 16 untracked |
| Website frontend | 15 | 12 modified, 3 untracked |
| Root docs, version, roadmap | 12 | 10 modified, 2 untracked |
| Native desktop app | 9 | 8 modified, 1 untracked |
| Release/update scripts | 2 | 2 untracked |
| Shared extension assets | 2 | 2 untracked |
| Design artifact | 1 | 1 deleted |

## Decision Queue

These items should be resolved deliberately before release packaging or broad refactors:

- Deleted Visual Studio release docs: `visual-studio-extensions/aegis-local-agent-vs/release/CHANGELOG.md`, `INSTALL.md`, `LICENSE.txt`, `README.md`, `RELEASE_NOTES.md`, `TROUBLESHOOTING.md`.
- Deleted VS Code release docs: `vscode-plugins/aegis-local-autopilot/release/CHANGELOG.md`, `INSTALL.md`, `RELEASE_NOTES.md`, `SMOKE_TEST.md`, `TROUBLESHOOTING.md`.
- Deleted design artifact: `website inspiration.png`.
- Untracked release authority: `VERSION.json`.
- Untracked release/update scripts: `scripts/aegis-update.ps1`, `scripts/build-release.ps1`.
- Untracked native desktop Core bridge directory: `src/core/`.
- Untracked VS Code package lock: `vscode-plugins/aegis-local-autopilot/package-lock.json`.

## Generated And Ignored Surfaces

The root `.gitignore` already excludes common generated output:

- Native/build output: `x64/`, `build/`, `out/`, `dist/`, `.vs/`, CMake output.
- Web runtime output: `node_modules/`, `website/frontend/dist/`, website logs/data/workspace, Python caches.
- Runtime diagnostics: `smoke-artifacts/`, `stress-artifacts/`, `logs/`, `crash-dumps/`, `.aegis/`.
- Local secrets and environment files: `.env`, `.env.*`, private key/certificate files, local overrides.

No generated ignored artifacts need to be force-added as part of Phase 0.

## Recommended Checkpoint Groups

Use these groups when committing or otherwise checkpointing the current work:

1. Core runtime and tests: `aegis-core/aegis_core`, `aegis-core/docs`, `aegis-core/tests`, `aegis-core/example-plugins`.
2. Website backend provider/account/security work: `website/backend/aegis_ai`, `website/backend/tests`.
3. Website frontend provider/account/workspace surfaces: `website/frontend/src`, `website/frontend/vite.config.ts`, `website/frontend/index.html`.
4. Native desktop shell and Core bridge: `src/`, `AegisChatBotDesktop.vcxproj`, `AegisChatBotDesktop.vcxproj.filters`, `CMakeLists.txt`.
5. VS Code extension: `vscode-plugins/aegis-local-autopilot`.
6. Visual Studio extension: `visual-studio-extensions/aegis-local-agent-vs`.
7. Release/update/version tooling: `VERSION.json`, `scripts/`, root release docs.
8. Product/platform docs: root docs plus `docs/`.

## Phase 0 Acceptance Status

- Dirty tree inventory: complete.
- Generated artifact policy: checked against `.gitignore`.
- Release artifact decision queue: complete.
- Known unstable surfaces note: created separately in `KNOWN_UNSTABLE_SURFACES.md`.
- Release packaging: still blocked until release-folder deletions are accepted or restored.
