# Aegis AI Patch Notes

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
