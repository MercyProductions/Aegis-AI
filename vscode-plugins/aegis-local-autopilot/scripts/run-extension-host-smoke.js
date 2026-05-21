const fs = require('fs');
const os = require('os');
const path = require('path');
const { runTests } = require('@vscode/test-electron');

const root = path.resolve(__dirname, '..');
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-vscode-smoke-'));
const extensionRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-vscode-extension-'));
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-vscode-user-data-'));
const extensionsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-vscode-extensions-'));
fs.mkdirSync(path.join(workspace, 'src', 'features'), { recursive: true });
fs.writeFileSync(path.join(workspace, 'package.json'), JSON.stringify({ scripts: { test: 'node -e "process.exit(0)"' } }, null, 2));
fs.writeFileSync(path.join(workspace, 'src', 'features', 'seed.txt'), 'seed\n');

copyForSmoke(root, extensionRoot);
fs.writeFileSync(path.join(extensionRoot, '.aegis-devtools'), 'enabled for smoke tests only\n');

const env = Object.assign({}, process.env, {
  AEGIS_EXTENSION_DEVTOOLS: '1',
  AEGIS_SMOKE_WORKSPACE: workspace
});
process.env.AEGIS_EXTENSION_DEVTOOLS = '1';
process.env.AEGIS_SMOKE_WORKSPACE = workspace;

runTests({
  extensionDevelopmentPath: extensionRoot,
  extensionTestsPath: path.join(extensionRoot, 'test', 'smoke', 'suite.js'),
  launchArgs: ['--user-data-dir', userDataDir, '--extensions-dir', extensionsDir, workspace],
  extensionTestsEnv: env
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

function copyForSmoke(sourceRoot, targetRoot) {
  for (const name of ['extension.js', 'package.json', 'LICENSE.txt']) {
    fs.copyFileSync(path.join(sourceRoot, name), path.join(targetRoot, name));
  }
  for (const dir of ['media', 'src', 'test']) {
    fs.cpSync(path.join(sourceRoot, dir), path.join(targetRoot, dir), { recursive: true });
  }
}
