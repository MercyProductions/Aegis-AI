# Native Desktop Shell Evidence

Generated: 2026-05-21

Phase 28 starts reducing risk in the native Windows shell. The first slice moves Runtime Status release-compatibility presentation rules out of `src/AegisChatApp.cpp` and into `src/desktop/RuntimeStatusPresenter.cpp`.

Machine-readable contract: `evals/phase28-native-desktop-shell-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-native-desktop-shell.ps1
```

Evidence output:

```text
.aegis/desktop-shell-hardening/<timestamp>/
```

## What It Checks

- `AegisChatApp.cpp` imports the runtime status presenter and remains the ImGui orchestrator for the panel.
- `RuntimeStatusPresenter` owns service labels, service tones, Core release-compatibility tone, requirement text, and blocker/warning/note text.
- CMake and Visual Studio desktop builds include the extracted presenter source and header.
- The existing desktop source contract passes with the presenter-aware checks.
- The native Release x64 build passes.

## Current Status

The required status is `ready` once the validator writes `desktop-shell-hardening.json` and `desktop-shell-hardening-summary.md` with no failed checks.

This is intentionally a narrow desktop hardening slice. The next native slices should continue splitting high-risk panels and API domains out of `AegisChatApp.cpp` and `AegisClient.cpp`.
