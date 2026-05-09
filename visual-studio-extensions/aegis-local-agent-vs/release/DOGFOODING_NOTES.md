# Visual Studio Dogfooding Notes

Date: 2026-05-08

Builds tested:

- 0.1.0 release candidate VSIX installed into Visual Studio 2022 Community instance `278075b6`
- 0.1.1 dogfooding hardening build

## Test Matrix

| Project type | Solution | Status | Notes |
| --- | --- | --- | --- |
| Small C# | Disposable C# smoke solution generated under `release/smoke-tests/CSharpSmokeSln` | Passed open/build smoke | Visual Studio automation opened the solution and build completed successfully. Smoke artifacts were removed after the test. |
| Small C# | `C:\Users\gabri\Desktop\School\School Project Tool\WindowsFormsApp1\WindowsFormsApp1.slnx` | Partial pass | Visual Studio opened the real solution and wrote an activity log. The first 0.1.1 package exposed command-resource packaging issues that were fixed before repackaging. Non-interactive solution-load command automation remained flaky and needs manual GUI follow-up. |
| C++ | `C:\Users\gabri\Desktop\Aegis\Website\ChatBot\workspace\__aegis_api_smoke_sln_20260430_043846\aegis_api_smoke_sln_20260430_043846.sln` | Needs manual GUI follow-up | Non-interactive Visual Studio open/exit smoke timed out and required process cleanup. No Aegis edits were applied. |
| Unity | Temporary Unity-shaped solution under `%TEMP%\AegisVsRcSmoke\UnitySmoke` | Needs manual GUI follow-up | Non-interactive Visual Studio open/exit smoke timed out and required process cleanup. Temp solution was removed. |
| Broken/unfinished | Pending | Not yet verified | Needs a real failing solution with visible Error List and Build Output in the IDE. |

## Commands / Workflows Checked

- VSIX install/uninstall through `VSIXInstaller.exe`: passed for 0.1.0.
- Packaged manifest registration: passed for 0.1.0; installed manifest reported version `0.1.0`, display name `Aegis Local Agent`, and package registration.
- VSIX upgrade to 0.1.1: passed after repackaging. Installed manifest and package registration report `0.1.1`.
- Ollama reachability: passed. `qwen3-coder:30b`, `qwen2.5-coder:7b`, and `granite-code:8b` were installed, and a direct `qwen3-coder:30b` test prompt returned successfully.
- Small C# solution build smoke: passed.
- Aegis command table registration: passed after `Menus.ctmenu` fix. Visual Studio DTE enumerated 21 Aegis command IDs, and GUID-based command execution loaded `AegisPackage` successfully.
- No-solution command smoke: passed. Open Agent, Run Health Check, and Rollback Last Change commands executed by command ID and exited cleanly; activity log showed `Begin package load [AegisPackage]` and `End package load [AegisPackage]`.
- Final installed 0.1.1 smoke: passed. The final packaged VSIX was installed, Open Agent / Run Health Check / Rollback Last Change were raised by command ID, and Visual Studio exited cleanly. Remaining activity-log errors were from Visual Studio C# Interactive / Copilot packages, not Aegis.
- C++ and Unity non-interactive open/exit smoke: timed out. This is treated as a reliability warning rather than proof of a command failure because Visual Studio GUI workflows were not manually exercised.

## Issues Found

### AEGIS-VS-DOGFOOD-001: Startup indexing is too aggressive for daily-driver dogfooding

Severity: High

Observed behavior:

- The 0.1.0 build defaulted `Auto Scan On Solution Open` to `true`.
- Non-interactive C++ and Unity-shaped Visual Studio open/exit tests timed out, and startup scanning is a likely contributor on real multi-folder solutions.

Risk:

- Users may perceive the extension as slow or stuck before they intentionally ask Aegis to inspect the solution.
- Large solutions are the exact place where predictable startup matters most.

Fix chosen for 0.1.1:

- Default `Auto Scan On Solution Open` to `false` for new installs.
- Keep manual scan, health check, roadmap, and context-building workflows available.
- Update documentation so manual rescan is the expected first-run indexing path.

### AEGIS-VS-DOGFOOD-002: Non-interactive command automation is not enough to prove GUI workflows

Severity: Medium

Observed behavior:

- DTE command enumeration did not reliably expose the Aegis command names during automation.
- This does not prove menu/tool-window failure, but it limits unattended dogfooding coverage.

Next manual check:

- Open Visual Studio normally, use the Tools menu and Solution Explorer context menu, then verify the tool window, Health Check, roadmap, selected-error explanation, proposal preview, reject/apply, and rollback flows in the UI.
- DTE `ExecuteCommand("Aegis.OpenAgent")` is still not reliable because Visual Studio exposes the generated command IDs but not stable canonical names for all Tools menu commands. GUID-based command execution works.

### AEGIS-VS-DOGFOOD-003: VSIX command table was not embedded

Severity: High

Observed behavior:

- Visual Studio activity logs reported Aegis package UI-resource load failures after 0.1.1 was first installed.
- The compiled assembly did not contain `Menus.ctmenu`, so Visual Studio could not reliably load the Aegis command table.

Fix:

- Added `ResourceName` metadata to the VSCT item.
- Added `VSPackage.resx` with `MergeWithCTO` so `Menus.ctmenu` is embedded into `AegisLocalAgentVs.dll`.
- Added `ProvideBindingPath` for package/dependency probing.
- Hardened `build.ps1` to fail on MSBuild errors and verify the packaged version plus embedded command resource.

Validation:

- `AegisLocalAgentVs.dll` now exposes `VSPackage.resources`.
- `VSPackage.resources` contains `Menus.ctmenu` as a byte array.
- The release VSIX contains manifest version `0.1.1` and package registration `PID=0.1.1`.

### AEGIS-VS-DOGFOOD-004: Build script could ship stale output after MSBuild errors

Severity: High

Observed behavior:

- A duplicate embedded-resource mistake caused MSBuild errors, but the script continued to package the previous output.

Fix:

- Wrapped all `dotnet msbuild` calls in an exit-code checking helper.
- Added package verification for the VSIX manifest version and embedded command resource.

## Unsafe Suggestions / Edits

- No unsafe file modifications were proposed or applied during this dogfooding pass.
- No `.env`, private key, `bin/`, `obj/`, `.vs/`, `packages/`, generated, or vendor paths were edited by Aegis.

## Performance Notes

- Startup/open behavior is the first performance concern.
- 0.1.1 intentionally avoids automatic indexing on solution open for new installs.
- Further optimization should be driven by manual timing from real C#, C++, Unity, and messy solutions after 0.1.1 is installed.

## Remaining Manual GUI Test Checklist

- Install 0.1.1 VSIX into Visual Studio 2022 Community.
- Open one small C# solution and run:
  - `Aegis: Run Health Check`
  - `Aegis: Generate Solution Roadmap`
  - `Aegis: Explain Current File`
  - `Aegis: Continue From Roadmap`
  - `Aegis: Rollback Last Change`
- Open one C++ solution and run:
  - `Aegis: Run Health Check`
  - `Aegis: Explain Build Failure`
  - `Aegis: Fix Selected Error`
- Open one Unity solution and run:
  - `Aegis: Run Health Check`
  - `Aegis: Generate Solution Roadmap`
  - `Aegis: Explain Current File`
- Open one broken/unfinished solution and run:
  - `Aegis: Fix Selected Error`
  - `Aegis: Explain Build Failure`
  - `Aegis: Continue From Roadmap`
