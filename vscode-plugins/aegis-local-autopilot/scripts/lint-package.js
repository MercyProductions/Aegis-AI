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

const urlNormalizer = loadExtensionFunctions(
  extensionText,
  ['stripKnownServiceEndpointPath', 'normalizeHttpBaseUrl'],
  'normalizeHttpBaseUrl',
  { URL }
);
assertUrlNormalization(urlNormalizer, '127.0.0.1:8788', 'http://127.0.0.1:8788');
assertUrlNormalization(urlNormalizer, 'http://127.0.0.1:8788/v1/health', 'http://127.0.0.1:8788');
assertUrlNormalization(urlNormalizer, 'http://127.0.0.1:8788/health', 'http://127.0.0.1:8788');
assertUrlNormalization(urlNormalizer, 'https://proxy.local/aegis/v1/health', 'https://proxy.local/aegis');
assertUrlNormalization(urlNormalizer, 'https://proxy.local/aegis/models', 'https://proxy.local/aegis');
assertUrlNormalization(urlNormalizer, 'https://proxy.local/aegis-v1-proxy', 'https://proxy.local/aegis-v1-proxy');
assertUrlNormalization(urlNormalizer, 'https://proxy.local/ollama/api/tags', 'https://proxy.local/ollama');
assertUrlNormalization(urlNormalizer, 'http://user:secret@127.0.0.1:8788', 'http://127.0.0.1:8788');

const serviceUrlBuilder = loadExtensionFunction(extensionText, 'serviceUrl', { URL });
assertServiceUrl(serviceUrlBuilder, 'https://proxy.local/aegis', '/v1/health', 'https://proxy.local/aegis/v1/health');
assertServiceUrl(serviceUrlBuilder, 'https://proxy.local/ollama', '/api/tags', 'https://proxy.local/ollama/api/tags');
assertServiceUrl(serviceUrlBuilder, 'http://127.0.0.1:8788', '/v1/models', 'http://127.0.0.1:8788/v1/models');

const validationCommandGuard = loadExtensionFunction(extensionText, 'isSafeValidationCommand');
assertValidationCommandGuard(validationCommandGuard);
const validationCommandDetector = loadExtensionFunctions(
  extensionText,
  [
    'stripUtf8Bom',
    'parseJsonText',
    'isSafeValidationCommand',
    'pickPackageManagerFromNames',
    'pickPackageManagerForPath',
    'packageScriptCommand',
    'makeValidationCommand',
    'detectValidationCommands'
  ],
  'detectValidationCommands',
  { path, getConfig: () => ({ validationCommandPreferences: [] }) }
);
assertValidationCommandDetection(validationCommandDetector);

const projectLanguageInferrer = loadExtensionFunctions(
  extensionText,
  ['stripUtf8Bom', 'parseJsonText', 'normalizePackageManagerName', 'inferProjectLanguages'],
  'inferProjectLanguages',
  { path }
);
assertProjectLanguageInference(projectLanguageInferrer);
const projectCommandInferrer = loadExtensionFunctions(
  extensionText,
  ['stripUtf8Bom', 'parseJsonText', 'normalizePackageManagerName', 'pickPackageManagerFromNames', 'packageScriptCommand', 'inferProjectCommands'],
  'inferProjectCommands',
  { path }
);
assertProjectCommandInference(projectCommandInferrer);
const buildFileClassifier = loadExtensionFunction(extensionText, 'isLikelyBuildFile', { path });
assertBuildFileDetection(buildFileClassifier);
assertProjectRiskPattern(extensionText);
assertPythonLockfilePatterns(extensionText);
const sourceIndexing = loadExtensionFunctions(
  extensionText,
  [
    'isBlockedRelativePath',
    'isSymbolCandidate',
    'isIndexableTextFile',
    'lineNumberForIndex',
    'sanitizeMemoryText',
    'inferRouteNameFromPath',
    'extractDependencyImports',
    'extractSymbols'
  ],
  '({ isSymbolCandidate, isIndexableTextFile, extractDependencyImports, extractSymbols })',
  { BLOCKED_PATH_SEGMENTS: new Set(), SECRET_FILE_PATTERNS: [] }
);
assertProjectSourceIndexing(sourceIndexing);

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

function loadExtensionFunction(source, name, context = {}) {
  return vm.runInNewContext(`${extractExtensionFunctionSource(source, name)}\n${name};`, context);
}

function loadExtensionFunctions(source, names, exportedName, context = {}) {
  const functionSources = names.map((name) => extractExtensionFunctionSource(source, name)).join('\n');
  return vm.runInNewContext(`${functionSources}\n${exportedName};`, context);
}

function extractExtensionFunctionSource(source, name) {
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
        return source.slice(start, index + 1);
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

function assertUrlNormalization(normalizer, input, expected) {
  const normalized = normalizer(input, 'http://127.0.0.1:8788');
  if (normalized !== expected) {
    fail(`URL normalization mismatch for "${input}": expected "${expected}", got "${normalized}".`);
  }
}

function assertServiceUrl(builder, baseUrl, pathname, expected) {
  const built = builder(baseUrl, pathname).toString();
  if (built !== expected) {
    fail(`service URL mismatch for "${baseUrl}" + "${pathname}": expected "${expected}", got "${built}".`);
  }
}

function assertValidationCommandGuard(guard) {
  const safeCommands = [
    'npm test',
    'npm run build',
    'pnpm lint',
    'yarn typecheck',
    'bun run build',
    'dotnet build',
    'cargo check',
    'go test ./...',
    'python -m pytest',
    'cmake --build build'
  ];
  const unsafeCommands = [
    'npm.cmd install',
    'cmd.exe /c npm test',
    'powershell -Command Invoke-Build',
    'git reset --hard',
    'git.exe -C . clean -fd',
    '"C:\\Program Files\\Git\\cmd\\git.exe" checkout -- .',
    'python -m pytest && git reset --hard'
  ];

  for (const command of safeCommands) {
    if (!guard(command)) {
      fail(`extension validation command guard rejected safe command: ${command}`);
    }
  }
  for (const command of unsafeCommands) {
    if (guard(command)) {
      fail(`extension validation command guard allowed unsafe command: ${command}`);
    }
  }
}

function assertValidationCommandDetection(detector) {
  const nativeVisualStudioSnapshot = {
    target: { root: 'C:/demo/native' },
    files: [
      { relative: 'NativeOnly.sln' },
      { relative: 'NativeOnly.vcxproj' }
    ],
    directories: [],
    importantContents: [],
    packageManagers: []
  };
  const dotnetSnapshot = {
    target: { root: 'C:/demo/dotnet' },
    files: [
      { relative: 'Managed.sln' },
      { relative: 'src/App/App.csproj' }
    ],
    directories: [],
    importantContents: [],
    packageManagers: []
  };
  const fsharpSnapshot = {
    target: { root: 'C:/demo/fsharp' },
    files: [
      { relative: 'src/App/App.fsproj' }
    ],
    directories: [],
    importantContents: [],
    packageManagers: []
  };
  const visualBasicSnapshot = {
    target: { root: 'C:/demo/vb' },
    files: [
      { relative: 'src/App/App.vbproj' }
    ],
    directories: [],
    importantContents: [],
    packageManagers: []
  };
  const bunSnapshot = {
    target: { root: 'C:/demo/bun' },
    files: [
      { relative: 'package.json' },
      { relative: 'bun.lockb' }
    ],
    directories: [],
    importantContents: [
      {
        path: 'package.json',
        text: JSON.stringify({ scripts: { test: 'bun test', build: 'bun build ./src/index.ts' }, packageManager: 'bun@1.2.0' })
      }
    ],
    packageManagers: ['bun']
  };

  if (detector(nativeVisualStudioSnapshot).some((item) => item.command === 'dotnet build')) {
    fail('detectValidationCommands must not suggest dotnet build for native-only Visual Studio solutions.');
  }
  if (!detector(dotnetSnapshot).some((item) => item.command === 'dotnet build')) {
    fail('detectValidationCommands must suggest dotnet build when a .csproj is present.');
  }
  if (!detector(fsharpSnapshot).some((item) => item.command === 'dotnet build')) {
    fail('detectValidationCommands must suggest dotnet build when a .fsproj is present.');
  }
  if (!detector(visualBasicSnapshot).some((item) => item.command === 'dotnet build')) {
    fail('detectValidationCommands must suggest dotnet build when a .vbproj is present.');
  }
  const bunCommands = detector(bunSnapshot).map((item) => item.command);
  if (!bunCommands.includes('bun run test') || !bunCommands.includes('bun run build')) {
    fail('detectValidationCommands must preserve Bun package-manager validation commands.');
  }
}

function assertProjectLanguageInference(inferrer) {
  const result = inferrer(
    [
      { relative: 'Modern.slnx' },
      { relative: 'src/App/Program.fs' },
      { relative: 'src/App/App.fsproj' },
      { relative: 'src/Tool/Module.vb' },
      { relative: 'src/Tool/Tool.vbproj' },
      { relative: 'native/main.cxx' }
    ],
    []
  );
  for (const expected of ['C#/.NET', 'F#/.NET', 'VB.NET', 'C/C++']) {
    if (!result.languages.includes(expected)) {
      fail(`inferProjectLanguages must detect ${expected} workspaces from project/source files.`);
    }
  }

  const pythonLockResult = inferrer(
    [
      { relative: 'uv.lock' },
      { relative: 'poetry.lock' },
      { relative: 'pdm.lock' }
    ],
    []
  );
  if (!pythonLockResult.languages.includes('Python')) {
    fail('inferProjectLanguages must detect Python workspaces from Python lockfiles.');
  }
  for (const expected of ['uv', 'poetry', 'pdm']) {
    if (!pythonLockResult.packageManagers.includes(expected)) {
      fail(`inferProjectLanguages must detect ${expected} from Python lockfiles.`);
    }
  }
}

function assertProjectCommandInference(inferrer) {
  const slnxResult = inferrer(
    [],
    [
      { relative: 'Modern.slnx' },
      { relative: 'src/App/App.fsproj' }
    ]
  );
  if (!slnxResult.includes('msbuild <solution>.slnx')) {
    fail('inferProjectCommands must suggest MSBuild for .slnx workspaces.');
  }
  const bunResult = inferrer(
    [{ path: 'package.json', text: JSON.stringify({ scripts: { build: 'bun build ./src/index.ts' }, packageManager: 'bun@1.2.0' }) }],
    [
      { relative: 'package.json' },
      { relative: 'bun.lockb' }
    ]
  );
  if (!bunResult.includes('bun run build')) {
    fail('inferProjectCommands must preserve Bun package-manager commands.');
  }
}

function assertBuildFileDetection(classifier) {
  for (const file of ['Modern.slnx', 'src/App/App.fsproj', 'src/Tool/Tool.vbproj', 'Native.vcxproj', 'Native.vcxproj.filters']) {
    if (!classifier(file)) {
      fail(`isLikelyBuildFile must classify ${file} as a build/config file.`);
    }
  }
}

function assertProjectRiskPattern(source) {
  if (!source.includes('csproj|fsproj|vbproj|vcxproj|vcxproj\\\\.filters|sln|slnx')) {
    fail('webview risk badge must cover .slnx, F#/VB, and Visual Studio project files.');
  }
}

function assertPythonLockfilePatterns(source) {
  for (const lockfile of ['uv', 'poetry', 'pdm']) {
    const escaped = lockfile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!source.includes(`^${escaped}\\.lock$`)) {
      fail(`extension lockfile safety patterns must include ${lockfile}.lock.`);
    }
  }
}

function assertProjectSourceIndexing(indexing) {
  for (const file of ['src/App/Program.fs', 'src/App/Program.fsi', 'src/App/Script.fsx', 'src/Tool/Module.vb', 'src/App/MainWindow.xaml']) {
    if (!indexing.isSymbolCandidate(file, 512)) {
      fail(`isSymbolCandidate must include ${file}.`);
    }
    if (!indexing.isIndexableTextFile(file)) {
      fail(`isIndexableTextFile must include ${file}.`);
    }
  }

  const fsharpText = [
    'open Aegis.Core',
    'module Aegis.Feature',
    'type Runner = class end',
    'let run value = value'
  ].join('\n');
  const fsharpImports = indexing.extractDependencyImports(fsharpText, 'src/App/Feature.fs');
  const fsharpSymbols = indexing.extractSymbols(fsharpText, 'src/App/Feature.fs', {});
  if (!fsharpImports.some((item) => item.kind === 'fsharp-open' && item.specifier === 'Aegis.Core')) {
    fail('extractDependencyImports must capture F# open dependencies.');
  }
  if (!fsharpSymbols.some((item) => item.kind === 'module' && item.name === 'Aegis.Feature')) {
    fail('extractSymbols must capture F# modules.');
  }
  if (!fsharpSymbols.some((item) => item.kind === 'function' && item.name === 'run')) {
    fail('extractSymbols must capture F# let-bound functions.');
  }

  const vbText = [
    'Imports Aegis.Core',
    'Public Module Tooling',
    'Public Function Run() As Integer',
    'Return 0',
    'End Function',
    'End Module'
  ].join('\n');
  const vbImports = indexing.extractDependencyImports(vbText, 'src/Tool/Tooling.vb');
  const vbSymbols = indexing.extractSymbols(vbText, 'src/Tool/Tooling.vb', {});
  if (!vbImports.some((item) => item.kind === 'vb-imports' && item.specifier === 'Aegis.Core')) {
    fail('extractDependencyImports must capture Visual Basic Imports dependencies.');
  }
  if (!vbSymbols.some((item) => item.kind === 'class' && item.name === 'Tooling')) {
    fail('extractSymbols must capture Visual Basic modules/classes.');
  }
  if (!vbSymbols.some((item) => item.kind === 'function' && item.name === 'Run')) {
    fail('extractSymbols must capture Visual Basic functions.');
  }

  const jsSymbols = indexing.extractSymbols('let ordinaryValue = 1;', 'src/app.js', {});
  if (jsSymbols.some((item) => item.name === 'ordinaryValue')) {
    fail('extractSymbols must not treat JavaScript let variables as F# functions.');
  }
}

function assertCmdQuoting(input, expected) {
  const quoted = quoteForCmd(input);
  if (quoted !== expected) {
    fail(`Windows command quoting mismatch for "${input}": expected "${expected}", got "${quoted}".`);
  }
}
