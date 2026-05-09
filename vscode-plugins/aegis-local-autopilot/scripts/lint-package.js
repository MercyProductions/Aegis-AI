const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const manifestPath = path.join(root, 'package.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

const requiredTopLevel = [
  'name',
  'displayName',
  'description',
  'version',
  'publisher',
  'engines',
  'categories',
  'main',
  'activationEvents',
  'contributes'
];

const requiredCommands = [
  'aegisLocalAutopilot.openPanel',
  'aegisLocalAutopilot.runFirstRunSetup',
  'aegisLocalAutopilot.runHealthCheck',
  'aegisLocalAutopilot.runValidation',
  'aegisLocalAutopilot.chatWithLocalModel',
  'aegisLocalAutopilot.continueProject',
  'aegisLocalAutopilot.generateProjectRoadmap',
  'aegisLocalAutopilot.rollbackLastChange'
];

function fail(message) {
  console.error(`Aegis package lint failed: ${message}`);
  process.exit(1);
}

for (const key of requiredTopLevel) {
  if (!manifest[key]) {
    fail(`package.json is missing "${key}".`);
  }
}

if (!/^\d+\.\d+\.\d+$/.test(manifest.version)) {
  fail(`version must be semantic x.y.z, got "${manifest.version}".`);
}

if (!manifest.icon || !fs.existsSync(path.join(root, manifest.icon))) {
  fail(`icon is missing or not found: ${manifest.icon}`);
}

if (!manifest.repository || manifest.repository.type !== 'git') {
  fail('repository metadata must point at the GitHub git repository.');
}

if (typeof manifest.repository.url !== 'string' || !/^https:\/\/github\.com\/MercyProductions\/Aegis-AI(\.git)?$/.test(manifest.repository.url)) {
  fail(`repository URL must be the public GitHub repository, got "${manifest.repository.url || 'missing'}".`);
}

const contributedCommands = new Set((manifest.contributes.commands || []).map((item) => item.command));
const commandActivationEvents = new Set(
  (manifest.activationEvents || [])
    .filter((event) => typeof event === 'string' && event.startsWith('onCommand:'))
    .map((event) => event.slice('onCommand:'.length))
);
for (const command of requiredCommands) {
  if (!contributedCommands.has(command)) {
    fail(`missing contributed command: ${command}`);
  }
  if (!commandActivationEvents.has(command)) {
    fail(`missing activation event for command: ${command}`);
  }
}

for (const command of contributedCommands) {
  if (!commandActivationEvents.has(command)) {
    fail(`contributed command is missing activation event: ${command}`);
  }
}

for (const command of commandActivationEvents) {
  if (!contributedCommands.has(command)) {
    fail(`activation event references an uncontributed command: ${command}`);
  }
}

if (!manifest.contributes.viewsContainers || !manifest.contributes.views || !manifest.contributes.configuration) {
  fail('sidebar/webview/settings contributions are incomplete.');
}

for (const file of ['extension.js', 'README.md', 'media/aegis.svg', '.vscodeignore']) {
  if (!fs.existsSync(path.join(root, file))) {
    fail(`required file missing: ${file}`);
  }
}

const extensionText = fs.readFileSync(path.join(root, 'extension.js'), 'utf8');
if (/\burl\.href\b/.test(extensionText)) {
  fail('extension.js must not log full request URLs; use formatRequestTarget so workspace query strings stay out of diagnostics.');
}

for (const scriptFile of ['scripts/package-release.js', 'scripts/install-local.js', 'scripts/run-command.js']) {
  const scriptText = fs.readFileSync(path.join(root, scriptFile), 'utf8');
  if (/\bexecSync\s*\(/.test(scriptText)) {
    fail(`${scriptFile} must avoid shell command strings; use argument-array process execution.`);
  }
}

const ignoreText = fs.readFileSync(path.join(root, '.vscodeignore'), 'utf8');
for (const privateFile of ['.gitignore', 'DETECTED_MODELS.md', 'DOGFOODING_NOTES.md', 'install.ps1']) {
  const escaped = privateFile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const linePattern = new RegExp(`(^|\\r?\\n)${escaped}(\\r?\\n|$)`);
  if (!linePattern.test(ignoreText)) {
    fail(`.vscodeignore must exclude ${privateFile} from release packages.`);
  }
}

console.log(`Aegis package lint passed for ${manifest.name}@${manifest.version}.`);
