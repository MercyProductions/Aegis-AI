# Packaged Alpha Scenario Evidence

Phase 22 attaches package-backed evidence for the ten Phase 14 alpha scenarios. It verifies the released artifacts, not only the source tree, and records which packaged files and prior evidence folders support each scenario.

Machine-readable contract: `evals/phase22-packaged-alpha-scenarios-contract.json`.

Validation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-packaged-alpha-scenarios.ps1
```

Evidence output:

```text
.aegis/packaged-alpha-scenarios/<timestamp>/
```

The gate checks:

- `release/version-manifest.json` exists and lists all five release components.
- every package listed in the root manifest exists and matches its SHA-256.
- the Core, Website, Desktop, VS Code, and Visual Studio packages contain the runtime files needed by the ten alpha scenarios.
- Phase 21 apply/rollback evidence is attached for update and rollback scenarios.
- obvious plaintext secret markers are not present in packaged text files.
- `packaged-alpha-scenarios.json` and `packaged-alpha-scenarios-summary.md` can be linked from the external-alpha report and evidence ledger.

This evidence clears the scenario-suite attachment blocker. It does not replace cross-client parity screenshots/logs or final release notes; those remain separate release-readiness blockers.
