# Release Package Dry-Run Evidence

Phase 19 proves the release package builder and updater can agree on one generated manifest before the root `release/` folder is promoted as final.

Run the contract from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-package-dry-run.ps1
```

The script creates a timestamped evidence folder under:

```text
.aegis/release-package-dry-run/<timestamp>/
```

Each run writes:

- `release/`: generated package set and dry-run `version-manifest.json`.
- `build-release.log`: captured `scripts/build-release.ps1 -SkipBuild` output.
- `update-plan-<component>.json`: dry-run updater plans for every manifest component.
- `release-package-dry-run.json`: machine-readable contract result.
- `release-package-dry-run-summary.md`: human-readable status summary.

This evidence manifest is intentionally separate from the root `release/version-manifest.json`. A ready Phase 19 run clears the package dry-run and update-plan dry-run blockers, but it does not declare the root release folder final or decide whether existing dirty release artifacts should be committed, regenerated, or discarded.

## Contract Checks

The Phase 19 contract requires:

- `scripts/build-release.ps1 -SkipBuild` to finish successfully against a controlled `.aegis/` output directory.
- All required core, website, desktop, VS Code, and Visual Studio package artifacts to be present.
- Every generated manifest package entry to include `artifact`, `path`, `sha256`, and `size_bytes`.
- File size and SHA-256 values on disk to match the generated manifest.
- `scripts/aegis-update.ps1` to produce a `planned` dry-run state for every component in the generated manifest.
- Release helper scripts to be copied into the generated package folder.

## Release Promotion Boundary

Use this evidence to decide whether package assembly and updater planning are healthy. Promote or publish the root `release/` folder only after:

- The final root `release/version-manifest.json` is generated from the intended artifact set.
- Dirty release artifact changes are explicitly accepted or regenerated.
- External alpha evidence, parity checks, and release limitations are attached to the release report.
