# Smoke Test Checklist

Use this after building `release/aegis-local-autopilot-0.1.1.vsix`.

## Automated/CLI Checks

```powershell
npm run compile
npm run lint
npm run package
code --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
code --list-extensions --show-versions | Select-String aegis
```

Clean-instance install check:

```powershell
$smoke = Join-Path $env:TEMP "aegis-vscode-rc-smoke"
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --install-extension .\release\aegis-local-autopilot-0.1.1.vsix --force
code --user-data-dir "$smoke\user" --extensions-dir "$smoke\extensions" --list-extensions --show-versions | Select-String aegis
```

Expected installed extension:

```text
aegis.aegis-local-autopilot@0.1.1
```

## Manual VS Code Checks

1. Open a new workspace folder in VS Code.
2. Confirm the Aegis status bar item appears.
3. Open the **Aegis Local Agent** Activity Bar view.
4. Run `Aegis: Run Health Check`.
5. Confirm `.aegis/` is created in the workspace.
6. Use **Test Prompt** in Model Diagnostics.
7. Send a short chat message.
8. Run `Aegis: Generate/Update Project Roadmap`.
9. Ask for a small safe change and confirm a diff preview appears.
10. Approve the change.
11. Run `Aegis: Rollback Last Agent Change`.
12. Confirm the changed file returns to its previous contents.

## Notes

Avoid testing against a project with uncommitted critical work unless you have a separate backup. Aegis is approval-based, but smoke tests should still be done on a disposable or low-risk workspace first.
