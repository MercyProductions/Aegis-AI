# Plugin Lifecycle Evidence

Generated: 2026-05-21

Phase 32 turns the existing plugin and ecosystem package scaffolding into a safer lifecycle surface. Website productization plugins and ecosystem packages now have explicit update, rollback, and safe-uninstall routes, checksum validation, stored previous manifests, and audit events.

Machine-readable contract: `evals/phase32-plugin-lifecycle-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-plugin-lifecycle.ps1
```

Evidence output:

```text
.aegis/plugin-lifecycle/<timestamp>/
```

## What It Checks

- Productization plugins reject mismatched manifest checksums.
- Productization plugins can update to a replacement manifest, store the previous manifest, roll back to it, and safe-uninstall by disabling runtime visibility.
- Ecosystem packages reject mismatched checksums and support the same update, rollback, and safe-uninstall flow.
- Lifecycle actions write audit identifiers and preserve reason metadata.
- Uninstall is intentionally reversible for this phase: manifests stay available for audit and rollback while the plugin/package is disabled.

## Current Status

The required status is `ready` once the validator writes `plugin-lifecycle.json` and `plugin-lifecycle-summary.md` with no failed checks.

This phase does not execute arbitrary third-party plugin code or physically remove plugin files. It productizes the reviewable lifecycle contract while preserving the manifest-only isolation boundary.
