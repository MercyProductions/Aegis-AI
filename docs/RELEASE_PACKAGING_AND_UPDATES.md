# Release Packaging And Updates

Aegis now has a local-first release layer that makes Core, Website, Desktop, VS Code, and Visual Studio versioned as one ecosystem. Core exposes the release contract, clients check compatibility before relying on Core-owned workflows, and packaging scripts create recoverable local artifacts.

## Version Manifest

The root `VERSION.json` is the source manifest.

It records:

- `schema_version`: release/config/state schema, currently `2026.05.12`.
- `components`: Core, Website, Desktop, VS Code extension, and Visual Studio extension versions.
- `compatibility`: minimum Core and minimum client versions.
- `update_policy`: checksum, backup, rollback, and safe-mode requirements.
- `components.*.package`: artifact name, relative package path, SHA256, and size after packaging.

Core serves the manifest through:

- `GET /v1/release/manifest`
- `POST /v1/release/compatibility`
- `GET /v1/release/migrations`
- `POST /v1/release/migrations/run`
- `POST /v1/release/update-plan`

Website mirrors compatibility for UI/API consumers through:

- `GET /api/release/manifest`
- `GET /api/release/compatibility`

## Compatibility Rules

Clients should identify themselves as:

- `website`
- `desktop`
- `vscode-extension`
- `visual-studio-extension`

Compatibility checks compare:

- client version against `compatibility.minimum_clients`
- reported schema version against `schema_version`
- reported or manifest Core version against `minimum_core_version`
- advertised capabilities such as `release-compatibility`

Blocked compatibility should prevent update/apply operations. Warning compatibility can continue with fallback behavior and visible status.

## Package Build

Run a full release build:

```powershell
.\scripts\build-release.ps1
```

Create packages from already-built outputs:

```powershell
.\scripts\build-release.ps1 -SkipBuild
```

Outputs are written to `release/`:

- `aegis-core-<version>.zip`
- `aegis-website-<version>.zip`
- `aegis-desktop-<version>-portable.zip`
- `aegis-local-autopilot-<version>.vsix`
- `AegisLocalAgentVs.vsix`
- `version-manifest.json`

The generated manifest stamps package SHA256 and size fields.

## Phase 34 Distribution Decision

The current private-alpha distribution mode is intentionally conservative:

- Core, Website, and Desktop ship as checksummed portable ZIP packages.
- VS Code and Visual Studio ship as VSIX packages.
- The Desktop package is portable, not a signed installer.
- The current package set is an unsigned local build candidate.
- Signed installers are required before broad release.
- Testers verify checksums against `release/version-manifest.json` before install or update.

Distribution evidence is checked by:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-distribution-update.ps1
```

The script writes `.aegis/distribution-update/<timestamp>/` evidence and runs non-mutating update plan dry-runs for every component.

## Release Artifact Preflight

Before creating or mutating packages, run the non-mutating preflight:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-artifact-preflight.ps1
```

The preflight writes evidence to `.aegis/release-preflight/<timestamp>/` and records whether `VERSION.json`, stage inputs, VSIX candidates, `release/version-manifest.json`, release dry-run evidence, update dry-run evidence, and release artifact Git status are ready. It does not create packages, copy VSIX files, or write `release/version-manifest.json`.

Confirm extension package candidates:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-extension-package-candidates.ps1
```

This writes `.aegis/extension-package-candidates/<timestamp>/` evidence for the VS Code and Visual Studio VSIX files and their release-facing docs.

## Release Package Dry-Run Evidence

Before promoting the root `release/` folder, generate package evidence under `.aegis/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-package-dry-run.ps1
```

This writes `.aegis/release-package-dry-run/<timestamp>/` evidence, creates a controlled `release/version-manifest.json` inside that evidence folder, verifies package sizes and SHA-256 values, and runs update planner dry-runs for Core, Website, Desktop, VS Code, and Visual Studio components.

This dry-run evidence clears the package and update-plan dry-run blockers. It does not make the root `release/version-manifest.json` final and does not decide whether dirty release artifacts should be committed, regenerated, or discarded.

## Final Release Manifest Evidence

After the release artifact decision is intentional, generate and validate the root `release/` folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-final-release-manifest.ps1
```

This writes `.aegis/final-release-manifest/<timestamp>/` evidence, regenerates `release/version-manifest.json`, verifies all root package files, SHA-256 values, package sizes, release-relative paths, copied helper scripts, and update planner dry-runs for every component.

The artifact decision record is `docs/RELEASE_ARTIFACT_DECISION.md`. Current local builds are unsigned unless separately signed; checksums are required for every package.

## Apply And Rollback Evidence

After the root release manifest is generated, prove the shipped updater in a temporary install root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-apply-rollback.ps1
```

This writes `.aegis/release-apply-rollback/<timestamp>/` evidence. It copies the root `release/` folder into an evidence-local install root, runs update plans, applies every component, rolls every component back, verifies stray files are removed during rollback, and confirms a corrupt package fails checksum validation with failed safe-mode state.

## Update Flow

Inspect an update plan:

```powershell
.\scripts\aegis-update.ps1 -Component desktop
```

Apply an update:

```powershell
.\scripts\aegis-update.ps1 -Component desktop -Apply
```

The updater:

1. Loads the release manifest.
2. Copies or downloads the package into `.aegis/updates/downloads`.
3. Verifies SHA256.
4. Backs up the current component into `.aegis/updates/backups`.
5. Writes `.aegis/update-state.json` as `pending`.
6. Applies the package.
7. Marks the update as `success`.

VSIX packages are copied into their release folders. ZIP packages are expanded and overlaid onto the component target.

## Rollback And Recovery

Rollback:

```powershell
.\scripts\aegis-update.ps1 -Rollback
```

Safe mode marker:

```powershell
.\scripts\aegis-update.ps1 -Component desktop -SafeMode
```

Recovery state lives in:

- `.aegis/update-state.json`
- `.aegis/safe-mode.json`
- `.aegis/updates/backups`
- `.aegis/updates/downloads`

If apply fails, the updater records `failed_update_detected = true` and leaves the backup path for rollback.

## Diagnostics Export

Core exposes a local-only diagnostics bundle for tester support:

- `GET /v1/alpha/diagnostics`
- `POST /v1/alpha/diagnostics/export`

The export is written under the workspace `.aegis/alpha-diagnostics/` folder, redacts provider secrets and raw prompt-like values, and is never uploaded automatically. Testers attach it manually when requested.

## Migrations

Core migrations are idempotent and workspace-local:

```powershell
python -m aegis_core.cli release --workspace . --migrate
```

They create:

- `.aegis/release-state.json`
- `.aegis/config.json`
- `.aegis/model-registry-state.json`
- `.aegis/database-migrations.json`
- `.aegis/release-migrations.json`

Website database migrations now include `release_migrations` and `release_update_audit` tables. The Website backend remains responsible for SQLite schema initialization while Core records ecosystem compatibility state.

## Validation Checklist

Before publishing a release:

- Run Core tests.
- Run Website backend tests.
- Run frontend tests/build.
- Run Desktop Release build.
- Run VS Code compile and VSIX packaging.
- Run Visual Studio VSIX build/package validation.
- Run `scripts\test-release-package-dry-run.ps1` and inspect the generated `.aegis/release-package-dry-run/<timestamp>/release/version-manifest.json`.
- After the release-folder decision is intentional, run `scripts\test-final-release-manifest.ps1` and inspect the final root `release/version-manifest.json`.
- Run update plans with `.\scripts\aegis-update.ps1 -Component <component>` against the final manifest.
- Run `scripts\test-release-apply-rollback.ps1` and attach the generated `.aegis/release-apply-rollback/<timestamp>/release-apply-rollback-summary.md`.
- Run `scripts\test-release-notes-limitations.ps1` and attach `.aegis/release-notes-limitations/<timestamp>/release-notes-limitations-summary.md` before any external tester invite.

## Migration Path

Core is the release authority for manifest, compatibility, migration status, and update planning. Website remains the gateway for UI-facing compatibility endpoints. Desktop, VS Code, and Visual Studio report compatibility directly to Core and show the result in their runtime status surfaces.
