const cp = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const releaseDir = path.join(root, 'release');
const outFile = path.join(releaseDir, `${manifest.name}-${manifest.version}.vsix`);

fs.mkdirSync(releaseDir, { recursive: true });
for (const file of fs.readdirSync(releaseDir)) {
  if (file.startsWith(`${manifest.name}-`) && file.endsWith('.vsix')) {
    fs.rmSync(path.join(releaseDir, file), { force: true });
  }
}

cp.execSync(`npx --yes @vscode/vsce package --no-dependencies --out ${JSON.stringify(outFile)}`, {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true,
  shell: true
});

console.log(`Packaged ${outFile}`);
