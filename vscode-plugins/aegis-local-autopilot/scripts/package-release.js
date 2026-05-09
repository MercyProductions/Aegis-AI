const cp = require('child_process');
const fs = require('fs');
const path = require('path');
const { runCommand } = require('./run-command');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const releaseDir = path.join(root, 'release');
const outName = `${manifest.name}-${manifest.version}.vsix`;
const outFile = path.join(releaseDir, outName);
const outArg = path.join('release', outName);

cp.execFileSync(process.execPath, ['--check', path.join(root, 'extension.js')], {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true
});

cp.execFileSync(process.execPath, [path.join(root, 'scripts', 'lint-package.js')], {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true
});

fs.mkdirSync(releaseDir, { recursive: true });
for (const file of fs.readdirSync(releaseDir)) {
  if (file.startsWith(`${manifest.name}-`) && file.endsWith('.vsix')) {
    fs.rmSync(path.join(releaseDir, file), { force: true });
  }
}

runCommand('npx', ['--yes', '@vscode/vsce', 'package', '--no-dependencies', '--out', outArg], { cwd: root });

console.log(`Packaged ${outFile}`);
