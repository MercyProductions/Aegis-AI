# Changelog

## Unreleased

### Stabilization

- Added focused Aegis Core regression tests for `/v1` client registration, shared tasks, dashboard contracts, scan caching, and flexible CLI JSON output.
- Improved the Aegis Core CLI so `--json` works before or after the subcommand.
- Hardened Aegis Core path safety so ignored folders and secret-like filenames are handled case-insensitively and relative to the workspace before scanning.
- Hardened Aegis Core config loading so malformed shared settings fall back safely instead of breaking startup/health checks.
- Improved `/v1/tasks/{task_id}/status` error responses for missing tasks and unsupported statuses.
- Made Core dashboard/task memory reads resilient when `.aegis` JSON or markdown files are unreadable.
- Improved Core JavaScript validation detection so npm/pnpm/yarn test/build commands are listed only when matching package scripts exist.
- Restricted Core validation execution to a safe command allow-list and added structured blocked/missing/timeout failure results.
- Added product-utilization workflow notes for daily Auralith dogfooding.
- Documented the current stabilization and validation pass.

### Validation

- Aegis Core pytest, compile, CLI/API smoke checks pass.
- Desktop App build passes.
- VS Code extension lint and VSIX packaging pass.
- Visual Studio extension build and VSIX packaging pass.
- Website frontend tests/build and backend test suite pass.
- Full validation notes are tracked in `docs/ECOSYSTEM_STABILIZATION.md`.
