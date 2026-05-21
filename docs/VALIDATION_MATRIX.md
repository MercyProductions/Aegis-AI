# Validation Matrix

Generated: 2026-05-21

Use `scripts\validate-ecosystem.ps1` as the single ecosystem validation entry point.

## Standard Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1
```

The script writes evidence to:

```text
.aegis\release-evidence\<timestamp>\
```

Each run includes:

- `validation-summary.md`
- `validation-matrix.json`
- `tool-versions.json`
- `tool-versions.txt`
- `git-status-short.txt`
- `release-artifact-status.txt`
- One log file per validation gate
- Contract evidence subfolders such as `extension-package-candidates`, `release-package-dry-run-contract`, `final-release-manifest-contract`, `release-apply-rollback-contract`, `packaged-alpha-scenarios-contract`, `cross-client-parity-contract`, `release-notes-limitations-contract`, `core-website-ownership-contract`, `backend-modularization-contract`, `frontend-extraction-contract`, `desktop-shell-hardening-contract`, `editor-extension-modularization-contract`, `provider-secret-safety-contract`, `memory-governance-contract`, `plugin-lifecycle-contract`, `observability-ci-contract`, `distribution-update-contract`, `alpha-readiness-polish-contract`, `live-smoke-rc-contract`, `commit-scoping-github-handoff-contract`, `desktop-smoke-package-gates-contract`, `editor-smoke-release-package-decision-contract`, `release-artifact-preflight`, `quality-contract`, `plugin-contract`, `alpha-contract`, `external-alpha-contract`, and `evidence-ledger-contract`

## Gate Statuses

- `passed`: gate completed successfully.
- `failed`: gate failed and should block release or broad refactor work.
- `retryable`: gate failed for an environment condition, such as the VS Code test instance update mutex.
- `skipped`: gate was intentionally not run, usually because it is slow, interactive, or would mutate release artifacts.

Use `-Strict` when skipped or retryable gates should also return a non-zero exit code.

## Useful Variants

```powershell
# Avoid the VS Code extension-host smoke when the test instance is updating.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1 -SkipSmoke

# Include desktop runtime smoke after the native build.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1 -IncludeDesktopSmoke

# Package the Visual Studio extension after release-folder decisions are intentional.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1 -IncludeVisualStudioPackage -AllowDirtyReleaseArtifacts

# Produce release packages under the evidence directory after release-folder decisions are intentional.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-ecosystem.ps1 -IncludeReleasePackaging -AllowDirtyReleaseArtifacts
```

The evidence ledger can also be refreshed directly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-evidence-ledger-contract.ps1
```

The release artifact preflight can be refreshed directly without mutating package outputs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-release-artifact-preflight.ps1
```

The extension package candidate evidence can be refreshed directly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-extension-package-candidates.ps1
```

The release package dry-run evidence can be refreshed directly without writing the root `release/` folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-release-package-dry-run.ps1
```

The final root release manifest evidence can be refreshed directly when root `release/` package mutation is intentional:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-final-release-manifest.ps1
```

The release apply/rollback evidence can be refreshed directly without mutating the developer workspace:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-release-apply-rollback.ps1
```

The packaged alpha scenario evidence can be refreshed directly from the root release packages:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-packaged-alpha-scenarios.ps1
```

The cross-client parity evidence can be refreshed directly from source markers, attached Phase 20/21/22 evidence, and the root release packages:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-cross-client-parity.ps1
```

The release notes limitations evidence can be refreshed directly from the root release notes, component release notes, attached evidence folders, and `release/version-manifest.json`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-release-notes-limitations.ps1
```

The Core/Website ownership evidence can be refreshed directly from the runtime ownership source, adapter routes, client contracts, and focused backend/frontend tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-core-website-ownership.ps1
```

The backend modularization evidence can be refreshed directly from the extracted service module, `main.py` orchestration markers, and focused backend tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-backend-modularization.ps1
```

The frontend extraction evidence can be refreshed directly from the extracted provider runtime helpers, `App.tsx` orchestration markers, focused Vitest coverage, and the frontend production build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-frontend-extraction.ps1
```

The native desktop shell hardening evidence can be refreshed directly from the extracted runtime status presenter, desktop source contract, and native Release x64 build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-native-desktop-shell.ps1
```

The editor extension modularization evidence can be refreshed directly from the VS Code Core envelope helper extraction, VS Code helper tests/lint, and the Visual Studio non-mutating package-validation substitute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-editor-extension-modularization.ps1
```

The provider secret safety evidence can be refreshed directly from the provider account route-safety schema, redacted backend snapshot tests, frontend route-readiness card tests, and ledger wiring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-provider-secret-safety.ps1
```

The memory governance evidence can be refreshed directly from the Website memory governance bridge, Core personal-memory controls route wiring, legacy fallback export redaction, frontend API helpers, and ledger wiring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-memory-governance.ps1
```

The plugin lifecycle evidence can be refreshed directly from the Website productization and ecosystem package update, rollback, safe-uninstall, checksum, and audit lifecycle routes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-plugin-lifecycle.ps1
```

The observability/evals/CI evidence can be refreshed directly from the GitHub Actions workflow, Phase 12 quality contract, golden workflow tests, telemetry markers, and ledger wiring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-observability-ci.ps1
```

The distribution/update evidence can be refreshed directly from the final release manifest, portable ZIP and VSIX artifacts, updater dry-runs, unsigned-build disclosure, rollback evidence, and local diagnostics export contract:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-distribution-update.ps1
```

The alpha readiness polish evidence can be refreshed directly from Core alpha handoff labels, first-run onboarding guidance, release notes limitations, distribution evidence, and focused alpha readiness tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-alpha-readiness-polish.ps1
```

The Phase 36 live smoke and release candidate scoping evidence can be refreshed directly from the latest validation matrix, upstream release evidence, live gate closure inventory, worktree scope, and GitHub target notes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-live-smoke-rc.ps1
```

The Phase 37 commit scoping and GitHub handoff evidence can be refreshed directly from `git status`, detected `origin`, commit grouping policy, deleted asset decision state, and attached Phase 36 evidence:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-commit-scoping-github-handoff.ps1
```

The Phase 38 desktop smoke and package gate evidence can be refreshed directly from the latest validation matrix, isolated desktop smoke attempts, package gate mutation decisions, screenshots/log evidence, and owner next actions:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-desktop-smoke-package-gates.ps1
```

To execute the desktop runtime smoke as part of Phase 38:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-desktop-smoke-package-gates.ps1 -AttemptDesktopSmoke
```

The Phase 39 editor smoke and release package decision evidence can be refreshed directly from the latest validation matrix, VS Code extension-host smoke attempts, package mutation scope, and owner next actions:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-editor-smoke-release-package-decision.ps1
```

To execute the VS Code extension-host smoke as part of Phase 39:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-editor-smoke-release-package-decision.ps1 -AttemptVsCodeSmoke
```

The default run avoids mutating the root `release/` folder while it remains decision-sensitive. Phase 19 package evidence is written under `.aegis/release-package-dry-run` or the current `release-package-dry-run-contract` evidence subfolder. Phase 20 final-manifest evidence is written under `.aegis/final-release-manifest` or the current `final-release-manifest-contract` evidence subfolder.
