# Release Artifact Decision

Phase 20 records the local release artifact decision for the current Aegis ChatBot package candidate.

## Decision

The current generated extension release docs, VSIX files, `VERSION.json`, `scripts/build-release.ps1`, and `scripts/aegis-update.ps1` are accepted as release inputs for generating the local root `release/version-manifest.json`.

The root `release/` folder is treated as generated release output. It should be regenerated from `VERSION.json` and the current package inputs rather than edited manually.

This decision does not commit files or publish a release by itself. It only allows the final local manifest evidence step to generate root packages so checksums, sizes, update plans, and release notes can be verified against the intended artifact set.

## Unsigned Build Disclosure

The current package set is a local unsigned build candidate. Checksums are required, but signing remains optional for local builds until the distribution/signing phase is complete. Any external-alpha release notes must disclose unsigned local builds clearly.

## Evidence

Phase 20 evidence is written under:

```text
.aegis/final-release-manifest/<timestamp>/
```

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-final-release-manifest.ps1
```

Each run generates or validates:

- root `release/version-manifest.json`
- root package artifacts
- package SHA-256 and size metadata
- update-plan dry-runs for every component
- copied release helper scripts
- final release manifest evidence JSON and summary Markdown

## Remaining Promotion Boundary

After this decision, release promotion is still blocked until packaged alpha scenarios, cross-client parity, rollback/apply evidence, release notes limitations, and GitHub publish scope are attached to the external-alpha report.
