const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { quoteForCmd } = require('./run-command');

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

const diagnosticRedactor = loadExtensionFunction(extensionText, 'redactDiagnosticText');
assertDiagnosticRedaction(
  diagnosticRedactor,
  'HTTP 401 {"api_key":"json-secret-token","message":"invalid"}',
  ['json-secret-token'],
  ['"api_key":"[redacted]"', 'invalid']
);
assertDiagnosticRedaction(
  diagnosticRedactor,
  'Provider rejected Authorization: Basic basic-secret-token via https://user:password@example.test/v1?token=query-secret',
  ['basic-secret-token', 'user:password', 'query-secret'],
  ['Authorization: [redacted]', 'https://[redacted]@example.test/v1?token=[redacted]']
);

const unsafeErrorMessagePatterns = [
  {
    pattern: /appendLine\s*\([^)]*error\.message/s,
    message: 'output.appendLine diagnostics must use safeErrorMessage(error) instead of raw error.message.'
  },
  {
    pattern: /showErrorMessage\s*\([^)]*error\.message/s,
    message: 'VS Code error notifications must use safeErrorMessage(error) instead of raw error.message.'
  },
  {
    pattern: /\bstate\.(?:status|project)\s*=\s*`[^`]*\$\{error\.message\}/s,
    message: 'webview status/project errors must use safeErrorMessage(error) instead of raw error.message.'
  },
  {
    pattern: /\baddCheck\s*\([^)]*error\.message/s,
    message: 'health-check details must use safeErrorMessage(error) instead of raw error.message.'
  },
  {
    pattern: /\boutput\s*:\s*[^,\n]*error\.message/s,
    message: 'structured diagnostic output must use safeErrorMessage(error) instead of raw error.message.'
  }
];
for (const guard of unsafeErrorMessagePatterns) {
  if (guard.pattern.test(extensionText)) {
    fail(guard.message);
  }
}
if (!/function validateAegisCoreEnvelope[\s\S]*redactDiagnosticText\(apiVersion\)[\s\S]*redactDiagnosticText\(kind\)/.test(extensionText)) {
  fail('validateAegisCoreEnvelope must redact unexpected api_version and kind values before throwing.');
}
if (!/function coreEnvelopeError[\s\S]*redactDiagnosticText\(detail\)/.test(extensionText)) {
  fail('coreEnvelopeError must redact Core error detail before returning user-visible text.');
}

for (const scriptFile of ['scripts/package-release.js', 'scripts/install-local.js', 'scripts/run-command.js']) {
  const scriptText = fs.readFileSync(path.join(root, scriptFile), 'utf8');
  if (/\bexecSync\s*\(/.test(scriptText)) {
    fail(`${scriptFile} must avoid shell command strings; use argument-array process execution.`);
  }
}

const packageReleaseText = fs.readFileSync(path.join(root, 'scripts/package-release.js'), 'utf8');
if (!/--check/.test(packageReleaseText) || !/extension\.js/.test(packageReleaseText)) {
  fail('scripts/package-release.js must compile-check extension.js before creating the VSIX.');
}

assertCmdQuoting('plain', 'plain');
assertCmdQuoting('path with spaces', '"path with spaces"');
assertCmdQuoting('C:\\Aegis^Tools\\package', '"C:\\Aegis^^Tools\\package"');
assertCmdQuoting('C:\\Aegis%TEMP%\\package', '"C:\\Aegis^%TEMP^%\\package"');

const ignoreText = fs.readFileSync(path.join(root, '.vscodeignore'), 'utf8');
for (const privateFile of ['.gitignore', 'DETECTED_MODELS.md', 'DOGFOODING_NOTES.md', 'install.ps1']) {
  const escaped = privateFile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const linePattern = new RegExp(`(^|\\r?\\n)${escaped}(\\r?\\n|$)`);
  if (!linePattern.test(ignoreText)) {
    fail(`.vscodeignore must exclude ${privateFile} from release packages.`);
  }
}

console.log(`Aegis package lint passed for ${manifest.name}@${manifest.version}.`);

function loadExtensionFunction(source, name) {
  const signature = `function ${name}`;
  const start = source.indexOf(signature);
  if (start === -1) {
    fail(`extension.js is missing ${name}.`);
  }
  const open = source.indexOf('{', start);
  if (open === -1) {
    fail(`extension.js has an invalid ${name} declaration.`);
  }
  let depth = 0;
  for (let index = open; index < source.length; index += 1) {
    const char = source[index];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        const functionSource = source.slice(start, index + 1);
        return vm.runInNewContext(`${functionSource}\n${name};`, {});
      }
    }
  }
  fail(`extension.js has an unterminated ${name} declaration.`);
}

function assertDiagnosticRedaction(redactor, sample, disallowed, required) {
  const redacted = redactor(sample, 1000);
  for (const value of disallowed) {
    if (redacted.includes(value)) {
      fail(`redactDiagnosticText leaked sensitive diagnostic value: ${value}`);
    }
  }
  for (const value of required) {
    if (!redacted.includes(value)) {
      fail(`redactDiagnosticText lost expected diagnostic context: ${value}`);
    }
  }
}

function assertCmdQuoting(input, expected) {
  const quoted = quoteForCmd(input);
  if (quoted !== expected) {
    fail(`Windows command quoting mismatch for "${input}": expected "${expected}", got "${quoted}".`);
  }
}
