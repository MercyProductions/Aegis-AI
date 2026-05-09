# Dogfooding Notes

## 2026-05-08 - Post-Release Dogfooding Pass

Installed release:

- Installed `release/aegis-local-autopilot-0.1.0.vsix` in normal VS Code.
- Verified VS Code reported `aegis.aegis-local-autopilot@0.1.0`.
- Dogfood harness used `qwen2.5-coder:7b` to keep the pass practical; `qwen3-coder:30b` remains the packaged default.

Projects tested:

| Project | Type | Result |
| --- | --- | --- |
| `Tools/04 Runtime & Engine Tools/Obfuscation/JavaScript Obfuscator/Samples/node-app` | Small Node sample | Health, roadmap, continue-from-roadmap, current-file review, fix-build-errors proposal, validation skip, and rollback/no-backup path all completed. |
| `Website/ChatBot/frontend` | Medium React/Vite app | Health, roadmap, continue-from-roadmap, current-file review, validation, and rollback/no-backup path completed. `npm run build` passed. |
| `Website/ChatBot/workspace/random-wallpaper-image` | Messy unfinished Electron/Vite app | Health, roadmap, continue-from-roadmap, current-file review, validation, and rollback/no-backup path completed. `npm run build` failed because `tsc` was not installed/available. |

Command timing highlights:

- Small project model-backed commands took about 37-81 seconds each.
- Medium project model-backed commands took about 41-123 seconds each.
- Messy project model-backed commands took about 29-103 seconds each.
- Validation itself was fast when dependencies existed: the medium React/Vite build passed in about 4 seconds.

Issues found:

- `Fix Build Errors` proposed dependency and lockfile edits on the medium project even though `npm run build` passed. This was a bad suggestion and hurt trust.
- The messy project validation failure was concrete (`tsc` not recognized), but the old build-error flow did not feed that failure into the model before proposing repairs.
- Impact analysis sometimes listed `.` as a likely affected file because validation command symbols used `.` as their source location.
- UTF-8 BOM encoded `package.json` files could hide scripts from framework and validation detection on Windows-created projects.
- Model-backed commands are slow enough that the UI needs continued progress clarity during normal use.
- Unsafe lockfile proposals were blocked correctly, but the user-facing warning did not name the exact blocked file in the visible message. Addressed after 0.1.1 by naming the first blocked edit in visible warnings/errors.

Fixes applied for 0.1.1:

- `Aegis: Fix Build Errors` now runs detected validation first.
- If validation passes and there are no VS Code diagnostics, it reports that there is nothing to repair and does not call the model.
- If validation fails, the actual validation output is included in the repair objective.
- JSON parsing now strips UTF-8 BOM before `JSON.parse`.
- Relevant-file selection now ignores non-files and filters candidates to files that exist in the current snapshot, removing bogus `.` impact entries.

0.1.1 packaging result:

- `npm run lint` passed.
- `npm run package` produced `release/aegis-local-autopilot-0.1.1.vsix`.
- Normal VS Code install succeeded and reported `aegis.aegis-local-autopilot@0.1.1`.
- Clean user-data/extensions-dir install also succeeded and reported `aegis.aegis-local-autopilot@0.1.1`.

Follow-up candidates:

- Improve visible blocked-edit details in the sidebar/error panel. Addressed for warnings/errors; sidebar detail remains a future polish area.
- Add clearer progress messaging for long local model calls.
- Consider a lighter roadmap model setting or a fast-mode option for dogfooding large workspaces.
- Improve build-failure classification for missing dependencies versus code errors.

Safety outcome:

- No proposed source edits were applied during dogfooding.
- Proposal previews and `.aegis` memory files were created as expected.
- Rollback was exercised in the no-backup path and did not modify project files.
