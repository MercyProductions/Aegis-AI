const assert = require('assert');
const fs = require('fs/promises');
const path = require('path');
const vscode = require('vscode');

async function run() {
  const extension = vscode.extensions.all.find((item) =>
    item.id === 'aegis.aegis-local-autopilot' &&
    String(item.extensionPath || '').toLowerCase().includes('aegis-vscode-extension-')
  ) || vscode.extensions.getExtension('aegis.aegis-local-autopilot');
  assert(extension, 'Aegis extension must be discoverable in the Extension Host.');
  await extension.activate();
  const api = extension.exports;
  assert(api && api.__dev, 'Smoke tests require dev exports. Loaded: ' + extension.id + ' from ' + extension.extensionPath + '. Available Aegis extensions: ' + vscode.extensions.all.filter((item) => item.id.includes('aegis')).map((item) => item.id + '@' + item.extensionPath).join('; '));

  await vscode.commands.executeCommand('aegisLocalAutopilot.openPanel');
  await vscode.commands.executeCommand('aegisLocalAutopilot.runHealthCheck');

  const workspaceRoot = process.env.AEGIS_SMOKE_WORKSPACE || (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0].uri.fsPath);
  assert(workspaceRoot, 'Smoke workspace must be open.');
  await vscode.workspace.getConfiguration('aegisLocalAutopilot').update('safetyMode', 'standard', vscode.ConfigurationTarget.Workspace);
  const folder = vscode.workspace.workspaceFolders[0];
  const target = api.__dev.makeWorkspaceTarget(workspaceRoot, folder, {
    focusPath: path.join(workspaceRoot, 'src', 'features'),
    focusKind: 'folder'
  });
  assert.strictEqual(path.resolve(target.root), path.resolve(workspaceRoot));
  assert.strictEqual(target.focusRelative, 'src/features');

  const raw = JSON.stringify({
    summary: 'Smoke edit',
    risk: 'low',
    fileEdits: [
      {
        path: 'src/generated-smoke.txt',
        reason: 'Smoke-test generated file in workspace root apply flow.',
        content: 'smoke\n'
      }
    ],
    commands: [],
    tests: []
  });
  const proposal = api.__dev.parseProposal(raw, target, 'create a smoke file');
  proposal.destinationReasoning = api.__dev.buildDestinationReasoning(proposal, {
    target,
    files: [{ relative: 'package.json' }, { relative: 'src/features/seed.txt' }]
  }, target);
  assert.strictEqual(proposal.destinationReasoning.length, 1);

  const validation = api.__dev.validateProposalEdit(proposal, proposal.fileEdits[0]);
  assert.strictEqual(validation.ok, true);
  const applied = await api.__dev.applyProposal(proposal, { skipPrompt: true });
  assert.strictEqual(applied, true);
  const generatedPath = path.join(workspaceRoot, 'src', 'generated-smoke.txt');
  assert.strictEqual(await fs.readFile(generatedPath, 'utf8'), 'smoke\n');

  await api.__dev.rollbackLastAgentChange(target, { skipPrompt: true });
  await assert.rejects(() => fs.readFile(generatedPath, 'utf8'));

  await vscode.workspace.getConfiguration('aegisLocalAutopilot').update('safetyMode', 'review-only', vscode.ConfigurationTarget.Workspace);
  const blocked = await api.__dev.applyProposal(proposal, { skipPrompt: true });
  assert.strictEqual(blocked, false);
  await vscode.workspace.getConfiguration('aegisLocalAutopilot').update('safetyMode', 'standard', vscode.ConfigurationTarget.Workspace);
}

module.exports = { run };
