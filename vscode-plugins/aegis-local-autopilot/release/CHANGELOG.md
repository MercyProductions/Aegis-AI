# Auralith OS Local Agent Changelog

## 0.1.8

- Adds Core-first workflow and release-compatibility surfaces for the VS Code client.
- Keeps local-first workspace scanning, proposal preview, validation detection, backup, and rollback behavior.
- Expands package lint coverage for command drift, private-file leaks, generated output, secret-like paths, and validation command safety.
- Includes the current package guard scripts and modular helper sources in the VSIX.
- Packages as `aegis-local-autopilot-0.1.8.vsix`.

## Known Release Notes

- External alpha is still blocked until the full ecosystem release manifest, update dry-run evidence, packaged scenario suite, and cross-client parity evidence are attached.
- Smoke testing can be blocked by a VS Code extension-host update mutex. Rerun after the test instance finishes updating.
