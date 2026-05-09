# Aegis VS Code Plugins

Local VS Code extensions for Aegis development workflows.

## Extensions

- `aegis-local-autopilot`: a local-first VS Code coding agent that talks to Ollama, uses the currently opened workspace, drafts safe project changes, validates approved edits, and supports rollback.

Each extension lives in its own folder so it can be packaged, tested, or installed independently.

Packaged release artifacts live under each extension's `release/` folder. For Aegis Local Agent:

```powershell
cd .\aegis-local-autopilot
npm run lint
npm run package
npm run install-local
```
