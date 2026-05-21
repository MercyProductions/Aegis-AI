# Release Notes Limitations Evidence

Phase 24 attaches final release notes and known-limitations evidence for the conditional private external alpha candidate.

Machine-readable contract: `evals/phase24-release-notes-limitations-contract.json`.

Fast validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-release-notes-limitations.ps1
```

Evidence output:

```text
.aegis/release-notes-limitations/<timestamp>/
```

## What It Checks

- Root tester-facing release notes exist at `docs/EXTERNAL_ALPHA_RELEASE_NOTES.md`.
- Website, Desktop, VS Code, and Visual Studio release notes are present.
- `release/version-manifest.json` is present and every component artifact, size, and SHA-256 appears in the root release notes.
- Checksums are required and the unsigned local build limitation is explicit.
- Update and rollback commands are present.
- Recovery paths for update state, safe mode, backups, and downloads are present.
- Current known limitations from `KNOWN_UNSTABLE_SURFACES.md` are reflected in tester-facing notes.
- Phase 20, Phase 21, Phase 22, and Phase 23 evidence sources are attached.

## Current Status

The current Phase 24 status is ready when `scripts\test-release-notes-limitations.ps1` passes.

This clears the `release_notes_limitations_not_attached` blocker. It does not claim broad external alpha readiness; it moves the release decision to conditional private external alpha while skipped or runtime smoke gates remain visible.
