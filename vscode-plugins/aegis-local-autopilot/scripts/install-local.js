const fs = require('fs');
const path = require('path');
const { runCommand } = require('./run-command');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const vsixName = `${manifest.name}-${manifest.version}.vsix`;
const vsixArg = path.join('release', vsixName);
const vsix = path.join(root, vsixArg);

if (!fs.existsSync(vsix)) {
  console.error(`VSIX not found: ${vsix}`);
  process.exit(1);
}

runCommand('code', ['--install-extension', vsixArg, '--force'], {
  cwd: root,
  errorHint: 'Make sure the VS Code command-line launcher is installed and available on PATH.'
});

console.log(`Installed ${vsixName} into VS Code.`);
