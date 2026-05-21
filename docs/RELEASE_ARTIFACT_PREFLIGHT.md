# Release Artifact Preflight

The release artifact preflight is the Phase 17 guard before final package promotion. It checks whether the current workspace has the inputs needed for `scripts\build-release.ps1 -SkipBuild`, whether `release/version-manifest.json` exists, whether Phase 19 package dry-run evidence proves package/update dry runs, and whether Phase 20 final-manifest evidence records the artifact decision.

Machine-readable contract: `evals/phase17-release-artifact-preflight-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-artifact-preflight.ps1
```

Evidence output:

```text
.aegis/release-preflight/<timestamp>/
```

When this gate runs inside `scripts\validate-ecosystem.ps1`, its output is nested under the current `.aegis/release-evidence/<timestamp>/release-artifact-preflight/` folder.

## What It Checks

- `VERSION.json` is present and includes Core, Website, Desktop, VS Code, and Visual Studio components.
- `scripts\build-release.ps1` and `scripts\aegis-update.ps1` are present.
- Core, Website, and Desktop stage inputs exist.
- VS Code and Visual Studio VSIX candidates exist at the locations the packaging script expects.
- `release/version-manifest.json` exists when package generation has already run.
- Latest `.aegis/release-package-dry-run/<timestamp>/release-package-dry-run.json` or nested `release-package-dry-run-contract` evidence is ready.
- Latest `.aegis/final-release-manifest/<timestamp>/final-release-manifest.json` or nested `final-release-manifest-contract` evidence is ready.
- `docs/RELEASE_ARTIFACT_DECISION.md` records the explicit dirty-state decision for generated release artifacts.

## Current Status

The current status is ready after Phase 20 final manifest promotion.

Current blockers tracked by the Phase 17 contract:

- None.

Tracked blockers that clear once package candidates and dry-run evidence are generated:

- `vscode_vsix_missing`
- `visual_studio_vsix_missing`
- `release_package_dry_run_not_passed`
- `update_plan_dry_run_not_passed`

The preflight does not create packages, copy VSIX files, write `release/version-manifest.json`, or clean Git state. It only records what is ready, what is missing, and what should happen before the release package dry run is allowed. Dirty release artifact paths are allowed only when Phase 20 final manifest evidence and `docs/RELEASE_ARTIFACT_DECISION.md` make that state intentional.

## Promotion Path

1. Keep the Phase 19 package dry-run evidence attached to the release report.
2. Keep the Phase 20 final manifest evidence and `docs/RELEASE_ARTIFACT_DECISION.md` attached to the release report.
3. Run `scripts\validate-ecosystem.ps1 -IncludeReleasePackaging` only when a fresh root release package mutation is intended.
4. Rerun this preflight and attach the summary to `docs/EXTERNAL_ALPHA_RELEASE_REPORT.md`.
