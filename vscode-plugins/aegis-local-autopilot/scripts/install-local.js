const cp = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const vsix = path.join(root, 'release', `${manifest.name}-${manifest.version}.vsix`);

if (!fs.existsSync(vsix)) {
  console.error(`VSIX not found: ${vsix}`);
  process.exit(1);
}

cp.execSync(`code --install-extension ${JSON.stringify(vsix)} --force`, {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true,
  shell: true
});

console.log(`Installed ${path.basename(vsix)} into VS Code.`);
