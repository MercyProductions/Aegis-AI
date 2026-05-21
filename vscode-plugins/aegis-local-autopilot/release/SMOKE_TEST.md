# Auralith OS Local Agent Smoke Test

## Package Smoke

From `vscode-plugins\aegis-local-autopilot`:

```powershell
npm run lint
npm run test:unit
npm run package
```

Confirm the VSIX exists:

```powershell
Test-Path .\release\aegis-local-autopilot-0.1.8.vsix
```

## Clean Extension Install

```powershell
$smoke = Join-Path $env:TEMP "aegis-vscode-0.1.8-smoke"
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --install-extension .\release\aegis-local-autopilot-0.1.8.vsix --force
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --list-extensions --show-versions
```

Expected extension id:

```text
aegis.aegis-local-autopilot
```

## Runtime Smoke

1. Start Ollama.
2. Open a small test workspace.
3. Run `Aegis: Run First-Run Setup`.
4. Run `Aegis: Run Health Check`.
5. Generate a project roadmap.
6. Ask for one small preview-only change.
7. Confirm the proposal shows file reasons before applying.
8. Apply only after reviewing the diff.
9. Run validation.
10. Confirm rollback is available.

Record any skipped smoke reason in the release evidence folder.
