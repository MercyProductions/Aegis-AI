# Changelog

## Unreleased

### Stabilization

- Added focused Aegis Core regression tests for `/v1` client registration, shared tasks, dashboard contracts, scan caching, and flexible CLI JSON output.
- Improved the Aegis Core CLI so `--json` works before or after the subcommand.
- Hardened Aegis Core path safety so ignored folders and secret-like filenames are handled case-insensitively and relative to the workspace before scanning.
- Hardened Aegis Core config loading so malformed shared settings fall back safely instead of breaking startup/health checks.
- Hardened shared Ollama URL settings so common local URLs are normalized, API-path pastes are reduced to base URLs, credential-like endpoint text is rejected, and malformed URLs report model health failures instead of breaking diagnostics.
- Hardened Ollama model inventory parsing so malformed `/api/tags` payloads become health diagnostics instead of client-visible exceptions.
- Improved `/v1/tasks/{task_id}/status` error responses for missing tasks and unsupported statuses.
- Made Core dashboard/task memory reads resilient when `.aegis` JSON or markdown files are unreadable.
- Improved Core JavaScript validation detection so npm/pnpm/yarn test/build commands are listed only when matching package scripts exist.
- Restricted Core validation execution to a safe command allow-list and added structured blocked/missing/timeout failure results.
- Hardened Core validation startup failures so OS-level command launch errors return structured results instead of escaping to shared clients.
- Redacted secret-like validation output before writing `.aegis/validation-log.md` and made validation log write failures non-fatal.
- Redacted validation API output before returning it to clients and made Core diagnostic log writes non-fatal.
- Made Core memory writes best-effort and atomic where possible so damaged `.aegis` files do not crash scans or generated-memory updates.
- Hardened Core workspace scans against malformed `package.json` dependency shapes and file stat races during recent-file sorting.
- Hardened Core config reads and writes so damaged `.aegis/config.json` paths do not crash health or settings APIs.
- Restricted Core memory directory settings to a single workspace-local folder name so shared config cannot point memory outside the project.
- Hardened Core agent continue/repair planning so damaged roadmap or validation-log paths return safe responses instead of server errors.
- Hardened VS Code workspace memory initialization so damaged `.aegis` files are reported and skipped instead of breaking startup scans.
- Hardened VS Code memory/index/history writes so damaged `.aegis` files do not break scans, recovery state, validation logs, or post-apply bookkeeping.
- Hardened Visual Studio solution memory reads and writes so damaged `.aegis` paths degrade safely and Health Check can report them.
- Hardened Visual Studio rollback so backups carry explicit IDs and rollback skips unsafe or incomplete manifest entries instead of restoring from ambiguous paths.
- Hardened Website workspace setup so damaged `.aegis` project and validation profile paths return warnings instead of breaking setup.
- Hardened Website checkpoint restore so checkpoint IDs stay folder-local and damaged manifests or backup paths return clean errors instead of unsafe restores or server failures.
- Hardened Website apply changes so checkpoint creation failures stop the apply before files are touched and later write/delete failures return warnings with checkpoint context.
- Added product-utilization workflow notes for daily Auralith dogfooding.
- Documented the current stabilization and validation pass.

### Validation

- Aegis Core pytest, compile, CLI/API smoke checks pass.
- Desktop App build passes.
- VS Code extension lint and VSIX packaging pass.
- Visual Studio extension build and VSIX packaging pass.
- Website frontend tests/build and backend test suite pass.
- Full validation notes are tracked in `docs/ECOSYSTEM_STABILIZATION.md`.
