const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { quoteForCmd } = require('./run-command');

const root = path.resolve(__dirname, '..');
const manifestPath = path.join(root, 'package.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

// Phase-1 modularization: load modules for behavioral parity testing
require.extensions['.ts'] = require.extensions['.ts'] || require.extensions['.js'];
const errorsModule = require(path.join(root, 'src/utils/errors.ts'));
const pathSafeModule = require(path.join(root, 'src/utils/pathSafe.ts'));
const fsSafeModule = require(path.join(root, 'src/utils/fsSafe.ts'));
const proposalSafetyModule = require(path.join(root, 'src/proposal/proposalSafety.ts'));
const validationDetectorModule = require(path.join(root, 'src/validation/validationDetector.ts'));
const workspaceResolverModule = require(path.join(root, 'src/workspace/workspaceResolver.ts'));
const projectScannerModule = require(path.join(root, 'src/workspace/projectScanner.ts'));
const proposalParserModule = require(path.join(root, 'src/proposal/proposalParser.ts'));
const settingsModule = require(path.join(root, 'src/settings/settings.ts'));
const agentModeModule = require(path.join(root, 'src/agent/agentMode.ts'));
const contextDiscoveryModule = require(path.join(root, 'src/workspace/contextDiscovery.ts'));
const coreEnvelopeModule = require(path.join(root, 'src/core/coreEnvelope.ts'));

const sharedModuleContext = {
  _errorsModule: errorsModule,
  _pathSafeModule: pathSafeModule,
  _fsSafeModule: fsSafeModule,
  _proposalSafetyModule: proposalSafetyModule,
  _validationDetectorModule: validationDetectorModule,
  _workspaceResolverModule: workspaceResolverModule,
  _projectScannerModule: projectScannerModule,
  _proposalParserModule: proposalParserModule,
  _settingsModule: settingsModule,
  _agentModeModule: agentModeModule,
  _contextDiscoveryModule: contextDiscoveryModule,
  coreEnvelopeModule
};

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

for (const file of ['extension.js', 'README.md', 'media/aegis.svg', 'media/autopilotlogo.png', '.vscodeignore']) {
  if (!fs.existsSync(path.join(root, file))) {
    fail(`required file missing: ${file}`);
  }
}

if (manifest.icon !== 'media/autopilotlogo.png') {
  fail('package icon must use media/autopilotlogo.png.');
}

for (const file of [
  'src/extension.ts',
  'src/agent/agentMode.ts',
  'src/agent/autopilotLoop.ts',
  'src/agent/taskRunner.ts',
  'src/agent/repairLoop.ts',
  'src/proposal/proposalTypes.ts',
  'src/proposal/proposalParser.ts',
  'src/proposal/proposalPreview.ts',
  'src/proposal/proposalApply.ts',
  'src/proposal/proposalSafety.ts',
  'src/proposal/rollback.ts',
  'src/workspace/workspaceResolver.ts',
  'src/workspace/projectScanner.ts',
  'src/workspace/projectSnapshot.ts',
  'src/workspace/projectSignals.ts',
  'src/workspace/destinationReasoning.ts',
  'src/validation/validationDetector.ts',
  'src/validation/validationRunner.ts',
  'src/validation/validationTypes.ts',
  'src/core/aegisCoreClient.ts',
  'src/core/coreEnvelope.ts',
  'src/core/taskSync.ts',
  'src/models/ollamaClient.ts',
  'src/models/modelRouter.ts',
  'src/memory/aegisMemory.ts',
  'src/memory/backups.ts',
  'src/memory/logs.ts',
  'src/memory/indexes.ts',
  'src/memory/recovery.ts',
  'src/ui/LocalAutopilotViewProvider.ts',
  'src/ui/renderPanelHtml.ts',
  'src/ui/webviewMessages.ts',
  'src/ui/webviewState.ts',
  'src/settings/settings.ts',
  'src/utils/fsSafe.ts',
  'src/utils/pathSafe.ts',
  'src/utils/vscodeHelpers.ts',
  'src/utils/errors.ts'
]) {
  if (!fs.existsSync(path.join(root, file))) {
    fail(`phase-1 source module missing: ${file}`);
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
assertDiagnosticRedaction(
  diagnosticRedactor,
  'OAuth failed https://provider.test/callback?access_token=access-secret&refresh_token=refresh-secret&x-api-key=query-key {"client_secret":"json-client-secret","private_key":"json-private-key"} auth_token = assignment-token',
  ['access-secret', 'refresh-secret', 'query-key', 'json-client-secret', 'json-private-key', 'assignment-token'],
  ['access_token=[redacted]', 'refresh_token=[redacted]', 'x-api-key=[redacted]', '"client_secret":"[redacted]"', '"private_key":"[redacted]"', 'auth_token = [redacted]']
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
assertModelCallProgressInstrumentation(extensionText);

const validationCommandGuard = loadExtensionFunction(extensionText, 'isSafeValidationCommand');
assertValidationCommandGuard(validationCommandGuard);
const validationSummaryHelpers = loadExtensionFunctions(
  extensionText,
  ['truncateMiddle', 'classifyValidationFailure', 'summarizeValidation'],
  '({ classifyValidationFailure, summarizeValidation })'
);
assertValidationFailureClassification(validationSummaryHelpers);
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
const unityImportantFileClassifier = loadExtensionFunctions(
  extensionText,
  ['isUnityImportantFile', 'isImportantWorkspaceFile'],
  'isImportantWorkspaceFile',
  { path, IMPORTANT_FILE_PATTERNS: [] }
);
assertUnityImportantFileDetection(unityImportantFileClassifier);
const buildFileClassifier = loadExtensionFunctions(
  extensionText,
  ['isUnityImportantFile', 'isLikelyBuildFile'],
  'isLikelyBuildFile',
  { path }
);
assertBuildFileDetection(buildFileClassifier);
const workspaceTargetBuilder = loadExtensionFunctions(
  extensionText,
  ['isPathInside', 'makeWorkspaceTarget'],
  'makeWorkspaceTarget',
  { path }
);
assertWorkspaceTargetFocus(workspaceTargetBuilder);
assertProjectRiskPattern(extensionText);
assertPythonLockfilePatterns(extensionText);
assertGeneratedFolderSafety(extensionText);
assertRelativePathSegmentSafety(extensionText);
assertSecretFileSafety(extensionText);
const blockedProposalFormatter = loadExtensionFunction(extensionText, 'formatBlockedProposalEditSummary');
assertBlockedProposalEditSummary(blockedProposalFormatter);
assertBlockedProposalVisibleMessages(extensionText);
assertDestinationReasoningPanel(extensionText);
const proposalCodeBlockHelpers = loadExtensionFunctions(
  extensionText,
  [
    'normalizeLineEndings',
    'isBlockedRelativePath',
    'looksLikeWorkspaceChangeRequest',
    'proposalObjectFromInstructionalCodeBlocks',
    'shouldInferFileEditsFromCodeBlocks',
    'extractFencedCodeBlocks',
    'normalizeFenceLanguage',
    'inferCodeBlockPath',
    'extractFilePathHint',
    'collectFilePathCandidates',
    'normalizePotentialGeneratedPath',
    'pathLooksLikeFile',
    'isShellLanguage',
    'filePathFromLanguageAndContent',
    'firstUnusedPath',
    'extractCommandRecommendationsFromCodeBlocks',
    'isReasonableSuggestedCommand'
  ],
  '({ looksLikeWorkspaceChangeRequest, proposalObjectFromInstructionalCodeBlocks })',
  {
    path,
    BLOCKED_PATH_SEGMENTS: new Set(['.git', '.aegis', 'node_modules', 'dist', 'build', 'vendor']),
    SECRET_FILE_PATTERNS: [/^\.env(?:\.|$)/i, /(?:secret|token|password|credential|api[_-]?key)/i]
  }
);
assertWorkspaceChangeRouting(proposalCodeBlockHelpers.looksLikeWorkspaceChangeRequest);
assertInstructionalCodeBlockProposal(proposalCodeBlockHelpers.proposalObjectFromInstructionalCodeBlocks);
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
if (!/const\s*\{[\s\S]*validateCoreEnvelope[\s\S]*coreEnvelopeData[\s\S]*requireCoreOk[\s\S]*formatCoreContract[\s\S]*\}\s*=\s*require\('\.\/src\/core\/coreEnvelope\.ts'\)/.test(extensionText)) {
  fail('extension.js must import Core envelope helpers from src/core/coreEnvelope.ts.');
}
if (!/function validateAegisCoreEnvelope[\s\S]*validateCoreEnvelope\(envelope,\s*expectedKind,\s*\{\s*redactDiagnosticText\s*\}\)/.test(extensionText)) {
  fail('validateAegisCoreEnvelope must delegate to coreEnvelope.validateCoreEnvelope with extension redaction.');
}
if (!/function requireAegisCoreOk[\s\S]*requireCoreOk\(envelope,\s*action,\s*\{\s*redactDiagnosticText\s*\}\)/.test(extensionText)) {
  fail('requireAegisCoreOk must delegate to coreEnvelope.requireCoreOk with extension redaction.');
}
if (/function coreEnvelopeError\(/.test(extensionText) || /function coreEnvelopeData\(/.test(extensionText) || /function formatCoreContract\(/.test(extensionText)) {
  fail('extension.js must not retain duplicate Core envelope helper implementations.');
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

// Phase-1 modularization: verify src/ utility modules export the expected functions
// and that their implementations are consistent with the extension.js inline versions.
// Verify module implementations pass the same behavioral assertions as inline functions.
for (const [name, expectedExports] of [
  ['src/utils/errors.ts', ['safeErrorMessage', 'redactDiagnosticText', 'sanitizeMemoryText', 'truncateMiddle']],
  ['src/utils/pathSafe.ts', ['BLOCKED_PATH_SEGMENTS', 'SECRET_FILE_PATTERNS', 'LOCKFILE_PATTERNS', 'isPathInside', 'isBlockedRelativePath', 'normalizeLineEndings', 'timestampForPath']],
  ['src/utils/fsSafe.ts', ['readWorkspaceFile', 'resolveInside', 'stripUtf8Bom', 'parseJsonText', 'formatFileChunk']],
  ['src/proposal/proposalSafety.ts', ['validateProposalEdit', 'formatBlockedProposalEditSummary', 'normalizeConfidenceScore', 'sanitizeProposalForStorage', 'isSafeBackupId']],
  ['src/validation/validationDetector.ts', ['detectValidationCommands', 'pickPackageManagerForPath', 'normalizePackageManagerName', 'packageScriptCommand', 'isSafeValidationCommand']],
  ['src/workspace/workspaceResolver.ts', ['isWorkspaceTarget', 'makeWorkspaceTarget']],
  ['src/workspace/projectScanner.ts', ['inferProjectLanguages', 'inferProjectCommands', 'isLikelyTestFile', 'isLikelyConfigFile', 'isImportantWorkspaceFile']],
  ['src/proposal/proposalParser.ts', ['parseProposal', 'proposalToPlanText', 'normalizeModelImpactAnalysis', 'normalizeModelStages', 'normalizeProposalStages']],
  ['src/settings/settings.ts', ['normalizeHttpBaseUrl', 'stripKnownServiceEndpointPath', 'serviceUrl', 'boundedConfigInt', 'getNormalizedConfig']],
  ['src/core/coreEnvelope.ts', ['AEGIS_CORE_API_VERSION', 'AEGIS_CORE_CONTRACT_VERSION', 'validateCoreEnvelope', 'coreEnvelopeData', 'coreEnvelopeError', 'requireCoreOk', 'formatCoreContract', 'isCoreEnvelope']],
  ['src/agent/agentMode.ts', ['makeEmptyAgentState', 'makeEmptyHealthCheckState', 'makeEmptyModelDiagnosticsState', 'makeEmptyErrorInfo', 'buildProgressUpdate', 'buildContextFilesUpdate']]
]) {
  const mod = require(path.join(root, name));
  for (const fn of expectedExports) {
    if (mod[fn] === undefined) {
      fail(`${name} is missing expected export: ${fn}`);
    }
  }
}

// Verify module implementations pass the same behavioral assertions as inline functions.
const emptyState = agentModeModule.makeEmptyAgentState();
if (emptyState.status !== 'Idle' || !Array.isArray(emptyState.progressItems)) {
  fail('agentMode module makeEmptyAgentState failed to create correct state object.');
}
const updatedProgress = agentModeModule.buildProgressUpdate(emptyState, 'Test Progress', 'Detail');
if (updatedProgress.length !== 1 || updatedProgress[0].label !== 'Test Progress') {
  fail('agentMode module buildProgressUpdate failed.');
}
const contextUpdate = agentModeModule.buildContextFilesUpdate(['file1.ts'], 'test reason');
if (contextUpdate.length !== 1 || contextUpdate[0].path !== 'file1.ts') {
  fail('agentMode module buildContextFilesUpdate failed.');
}

if (settingsModule.normalizeHttpBaseUrl('127.0.0.1:11434', 'fallback') !== 'http://127.0.0.1:11434') {
  fail('settings module normalizeHttpBaseUrl failed to add http prefix.');
}
if (settingsModule.stripKnownServiceEndpointPath('/api/chat') !== '') {
  fail('settings module stripKnownServiceEndpointPath failed to strip /api/chat.');
}
if (settingsModule.boundedConfigInt('not-a-number', 1, 10, 5) !== 5) {
  fail('settings module boundedConfigInt failed to use fallback.');
}
const mockVscodeConfig = {
  get: (key, fallback) => fallback
};
const normConfig = settingsModule.getNormalizedConfig(mockVscodeConfig);
if (normConfig.ollamaUrl !== 'http://127.0.0.1:11434') {
  fail('settings module getNormalizedConfig returned incorrect default.');
}

// Verify module implementations pass the same behavioral assertions as inline functions.
const mockProposalJson = JSON.stringify({
  summary: 'Fix bugs',
  fileEdits: [{ path: 'app.ts', content: 'const x = 1;', reason: 'bugfix' }]
});
const parsed = proposalParserModule.parseProposal(
  `\`\`\`json\n${mockProposalJson}\n\`\`\``,
  { root: '/test', label: 'test' },
  'Fix bugs'
);
if (parsed.summary !== 'Fix bugs' || parsed.fileEdits.length !== 1) {
  fail('proposalParser module parseProposal failed to parse valid JSON proposal.');
}
if (parsed.fileEdits[0].path !== 'app.ts') {
  fail('proposalParser module parseProposal path mismatch.');
}
const planText = proposalParserModule.proposalToPlanText(parsed);
if (!planText.includes('Fix bugs') || !planText.includes('app.ts')) {
  fail('proposalParser module proposalToPlanText failed to generate plan text.');
}

// Verify module implementations pass the same behavioral assertions as inline functions.
if (!projectScannerModule.isLikelyTestFile('src/app.test.ts')) {
  fail('projectScanner module isLikelyTestFile must recognize test files.');
}
if (!projectScannerModule.isImportantWorkspaceFile('package.json')) {
  fail('projectScanner module isImportantWorkspaceFile must recognize package.json.');
}
const langInfo = projectScannerModule.inferProjectLanguages([{ relative: 'index.ts' }], []);
if (!langInfo.languages.includes('TypeScript')) {
  fail('projectScanner module inferProjectLanguages failed to detect TypeScript.');
}

// Verify module implementations pass the same behavioral assertions as inline functions.
if (!workspaceResolverModule.isWorkspaceTarget({ root: '/a', label: 'a' })) {
  fail('workspaceResolver module isWorkspaceTarget must recognize valid targets.');
}
const target = workspaceResolverModule.makeWorkspaceTarget('/test/src', { name: 'test', uri: { fsPath: '/test' } });
if (target.root !== path.resolve('/test/src') || target.workspaceFolderName !== 'test') {
  fail('workspaceResolver module makeWorkspaceTarget failed to create correct target object.');
}
if (target.label !== 'src') {
  fail(`workspaceResolver module makeWorkspaceTarget label mismatch. Expected 'src', got '${target.label}'`);
}



// Verify module implementations pass the same behavioral assertions as inline functions.
if (!validationDetectorModule.isSafeValidationCommand('npm test')) {
  fail('validationDetector module isSafeValidationCommand must allow npm test.');
}
if (validationDetectorModule.isSafeValidationCommand('rm -rf /')) {
  fail('validationDetector module isSafeValidationCommand must reject unsafe commands.');
}
if (validationDetectorModule.packageScriptCommand('npm', 'test') !== 'npm test') {
  fail('validationDetector module packageScriptCommand mismatch for npm test.');
}
if (validationDetectorModule.packageScriptCommand('pnpm', 'lint') !== 'pnpm lint') {
  fail('validationDetector module packageScriptCommand mismatch for pnpm lint.');
}
const mockSnapshot = {
  target: { root: '/test' },
  files: [{ relative: 'package.json' }, { relative: 'package-lock.json' }],
  importantContents: [{ path: 'package.json', text: '{"scripts":{"test":"vitest"}}' }],
  packageManagers: ['npm']
};
const detected = validationDetectorModule.detectValidationCommands(mockSnapshot);
if (!detected.some((c) => c.command === 'npm test')) {
  fail('validationDetector module detectValidationCommands failed to detect npm test from package.json.');
}



// Verify module implementations pass the same behavioral assertions as inline functions.
if (proposalSafetyModule.normalizeConfidenceScore(85) !== 0.85) {
  fail('proposalSafety module normalizeConfidenceScore must convert percentage to decimal.');
}
if (proposalSafetyModule.normalizeConfidenceScore('not-a-number') !== 0.55) {
  fail('proposalSafety module normalizeConfidenceScore must use default for invalid input.');
}
if (!proposalSafetyModule.isSafeBackupId('backup-2026-05-11')) {
  fail('proposalSafety module isSafeBackupId must allow valid backup IDs.');
}
if (proposalSafetyModule.isSafeBackupId('invalid/path')) {
  fail('proposalSafety module isSafeBackupId must reject invalid backup IDs.');
}
const testProposal = { workspace: '/test' };
const blockedEdit = { path: 'node_modules/pkg/index.js' };
const validateResult = proposalSafetyModule.validateProposalEdit(testProposal, blockedEdit);
if (validateResult.ok || validateResult.reason !== 'Path is blocked by safety rules.') {
  fail('proposalSafety module validateProposalEdit must block node_modules paths.');
}
const summary = proposalSafetyModule.formatBlockedProposalEditSummary([{ edit: { path: 'secret.key' }, reason: 'Secrets are blocked' }]);
if (!summary.includes('secret.key') || !summary.includes('Secrets are blocked')) {
  fail('proposalSafety module formatBlockedProposalEditSummary must format blocked edits correctly.');
}
assertDiagnosticRedaction(
  errorsModule.redactDiagnosticText,
  'HTTP 401 {"api_key":"json-secret-token","message":"invalid"}',
  ['json-secret-token'],
  ['"api_key":"[redacted]"', 'invalid']
);
assertDiagnosticRedaction(
  errorsModule.redactDiagnosticText,
  'Provider rejected Authorization: Basic basic-secret-token via https://user:password@example.test/v1?token=query-secret',
  ['basic-secret-token', 'user:password', 'query-secret'],
  ['Authorization: [redacted]', 'https://[redacted]@example.test/v1?token=[redacted]']
);
if (errorsModule.truncateMiddle('hello world', 5) === 'hello world') {
  fail('errors module truncateMiddle must truncate text longer than maxChars.');
}
if (errorsModule.truncateMiddle('ok', 100) !== 'ok') {
  fail('errors module truncateMiddle must return short text unchanged.');
}
if (!pathSafeModule.isBlockedRelativePath('.git/config')) {
  fail('pathSafe module must block .git paths.');
}
if (!pathSafeModule.isBlockedRelativePath('node_modules/pkg/index.js')) {
  fail('pathSafe module must block node_modules paths.');
}
if (pathSafeModule.isBlockedRelativePath('src/App.tsx')) {
  fail('pathSafe module must allow normal source paths.');
}
if (!pathSafeModule.isPathInside('/workspace', '/workspace/src/file.ts')) {
  fail('pathSafe module isPathInside must detect contained paths.');
}
if (pathSafeModule.isPathInside('/workspace', '/other/file.ts')) {
  fail('pathSafe module isPathInside must reject paths outside root.');
}
if (pathSafeModule.normalizeLineEndings('a\r\nb\rc') !== 'a\nb\nc') {
  fail('pathSafe module normalizeLineEndings must convert CRLF and CR to LF.');
}
if (fsSafeModule.stripUtf8Bom('\uFEFFhello') !== 'hello') {
  fail('fsSafe module stripUtf8Bom must strip BOM.');
}
if (fsSafeModule.parseJsonText('{"a":1}').a !== 1) {
  fail('fsSafe module parseJsonText must parse JSON.');
}

console.log(`Aegis package lint passed for ${manifest.name}@${manifest.version}.`);


function loadExtensionFunction(source, name, context = {}) {
  return vm.runInNewContext(`${extractExtensionFunctionSource(source, name)}\n${name};`, Object.assign({}, sharedModuleContext, context));
}

function loadExtensionFunctions(source, names, exportedName, context = {}) {
  const functionSources = names.map((name) => extractExtensionFunctionSource(source, name)).join('\n');
  return vm.runInNewContext(`${functionSources}\n${exportedName};`, Object.assign({}, sharedModuleContext, context));
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

function assertModelCallProgressInstrumentation(source) {
  const start = source.indexOf('async function askOllamaWithFallback');
  const end = source.indexOf('async function askOllama(', start);
  if (start === -1 || end === -1) {
    fail('extension.js must expose askOllamaWithFallback before askOllama.');
  }
  const body = source.slice(start, end);
  for (const required of [
    "pushProgress('Local model request started'",
    "updateAgentState({ status: 'Waiting for local model'",
    "pushProgress('Local model response ready'",
    "pushProgress(\n        'Local model fallback'",
    "updateAgentState({ status: 'Local model call failed' })"
  ]) {
    if (!body.includes(required)) {
      fail(`askOllamaWithFallback must keep model progress instrumentation: ${required}`);
    }
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

function assertValidationFailureClassification(helpers) {
  const missingTool = {
    skipped: false,
    commands: [
      {
        command: 'npm run build',
        success: false,
        output: "'tsc' is not recognized as an internal or external command"
      }
    ],
    output: "'tsc' is not recognized as an internal or external command"
  };
  const missingDependency = {
    skipped: false,
    commands: [
      {
        command: 'npm run build',
        success: false,
        output: "Error: Cannot find module 'vite'"
      }
    ],
    output: "Error: Cannot find module 'vite'"
  };
  const codeFailure = {
    skipped: false,
    commands: [
      {
        command: 'npm run build',
        success: false,
        output: "src/app.ts(1,1): error TS1005: ';' expected"
      }
    ],
    output: "src/app.ts(1,1): error TS1005: ';' expected"
  };

  if (helpers.classifyValidationFailure(missingTool).kind !== 'missing-tool') {
    fail('validation failure classifier must detect missing tool output.');
  }
  if (helpers.classifyValidationFailure(missingDependency).kind !== 'missing-dependency') {
    fail('validation failure classifier must detect missing dependency output.');
  }
  if (helpers.classifyValidationFailure(codeFailure).kind !== 'code-or-config') {
    fail('validation failure classifier must keep code/config failures distinct.');
  }
  const summary = helpers.summarizeValidation(missingTool);
  if (!summary.includes('Classification: Likely missing tool') || !summary.includes('Check PATH')) {
    fail('validation summaries must include actionable missing-tool classification.');
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

  const nativeLockResult = inferrer(
    [
      { relative: 'Cargo.lock' },
      { relative: 'go.sum' }
    ],
    []
  );
  if (!nativeLockResult.languages.includes('Rust') || !nativeLockResult.languages.includes('Go')) {
    fail('inferProjectLanguages must detect Rust and Go workspaces from native lockfiles.');
  }

  const dotnetPackageResult = inferrer(
    [
      { relative: 'packages.lock.json' },
      { relative: 'Directory.Packages.props' }
    ],
    []
  );
  if (!dotnetPackageResult.languages.includes('C#/.NET')) {
    fail('inferProjectLanguages must detect .NET workspaces from NuGet package metadata.');
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

function assertUnityImportantFileDetection(classifier) {
  for (const file of [
    'Packages/manifest.json',
    'Packages/packages-lock.json',
    'ProjectSettings/ProjectVersion.txt',
    'ProjectSettings/ProjectSettings.asset',
    'ProjectSettings/EditorBuildSettings.asset',
    'Assets/Scripts/Gameplay.asmdef',
    'Assets/Scripts/Gameplay.asmref'
  ]) {
    if (!classifier(file)) {
      fail(`isImportantWorkspaceFile must keep Unity metadata visible: ${file}.`);
    }
  }
  if (classifier('Assets/Logs/editor.log')) {
    fail('isImportantWorkspaceFile must not treat arbitrary Unity logs as important metadata.');
  }
}

function assertBuildFileDetection(classifier) {
  for (const file of [
    'Modern.slnx',
    'src/App/App.fsproj',
    'src/Tool/Tool.vbproj',
    'Native.vcxproj',
    'Native.vcxproj.filters',
    'Packages/manifest.json',
    'ProjectSettings/ProjectVersion.txt',
    'Assets/Scripts/Gameplay.asmdef'
  ]) {
    if (!classifier(file)) {
      fail(`isLikelyBuildFile must classify ${file} as a build/config file.`);
    }
  }
}

function assertWorkspaceTargetFocus(makeWorkspaceTarget) {
  const workspaceRoot = path.join('C:\\', 'AegisTest', 'Workspace');
  const folder = {
    name: 'Workspace',
    uri: { fsPath: workspaceRoot }
  };
  const selectedFolder = path.join(workspaceRoot, 'src', 'features');
  const folderTarget = makeWorkspaceTarget(workspaceRoot, folder, {
    focusPath: selectedFolder,
    focusKind: 'folder'
  });
  if (path.resolve(folderTarget.root) !== path.resolve(workspaceRoot)) {
    fail('selected-folder targets must keep the workspace root as the write root.');
  }
  if (folderTarget.focusRelative !== 'src/features') {
    fail('selected-folder targets must retain the selected folder as focus metadata.');
  }
  if (!folderTarget.label.includes('src/features')) {
    fail('selected-folder target labels must show the focused folder.');
  }

  const selectedFile = path.join(workspaceRoot, 'src', 'features', 'Widget.tsx');
  const fileTarget = makeWorkspaceTarget(workspaceRoot, folder, {
    focusPath: path.dirname(selectedFile),
    focusKind: 'file',
    focusFilePath: selectedFile
  });
  if (fileTarget.focusFileRelative !== 'src/features/Widget.tsx') {
    fail('selected-file targets must retain the selected file as focus metadata.');
  }
  if (path.resolve(fileTarget.root) !== path.resolve(workspaceRoot)) {
    fail('selected-file targets must not narrow the write root to the file directory.');
  }
}

function assertGeneratedFolderSafety(source) {
  for (const segment of ['library', 'temp', 'logs']) {
    if (!source.includes(`'${segment}'`)) {
      fail(`BLOCKED_PATH_SEGMENTS must include generated/runtime folder '${segment}'.`);
    }
  }
}

function assertRelativePathSegmentSafety(source) {
  const isBlockedRelativePath = loadExtensionFunction(source, 'isBlockedRelativePath', {
    BLOCKED_PATH_SEGMENTS: new Set(),
    SECRET_FILE_PATTERNS: []
  });
  for (const file of ['.', '..', '../README.md', 'src/../README.md', 'src/./README.md']) {
    if (!isBlockedRelativePath(file)) {
      fail(`isBlockedRelativePath must block dot-segment proposal path ${file}.`);
    }
  }
  for (const file of ['src/README.md', 'src/module.ts']) {
    if (isBlockedRelativePath(file)) {
      fail(`isBlockedRelativePath must allow ordinary relative path ${file}.`);
    }
  }
}

function assertSecretFileSafety(source) {
  const start = source.indexOf('const SECRET_FILE_PATTERNS = [');
  if (start === -1) {
    fail('extension.js must define SECRET_FILE_PATTERNS.');
  }
  const end = source.indexOf('];', start);
  if (end === -1) {
    fail('extension.js has an unterminated SECRET_FILE_PATTERNS block.');
  }
  const patternSource = source.slice(start, end + 2);
  const secretPatterns = vm.runInNewContext(`${patternSource}\nSECRET_FILE_PATTERNS;`);
  const isBlockedRelativePath = loadExtensionFunction(source, 'isBlockedRelativePath', {
    BLOCKED_PATH_SEGMENTS: new Set(),
    SECRET_FILE_PATTERNS: secretPatterns
  });
  for (const file of ['.env', '.env.example', 'id_rsa', 'service-token.json', 'prod.password.txt', 'private-key.pem', 'client_api-key.json', 'auth.json', 'local.keystore']) {
    if (!isBlockedRelativePath(file)) {
      fail(`isBlockedRelativePath must block secret-like file ${file}.`);
    }
  }
  for (const file of ['.gitignore', 'src/tokenizer.py', 'src/authenticationService.cs', 'src/privateer.cpp']) {
    if (isBlockedRelativePath(file)) {
      fail(`isBlockedRelativePath must not over-block ordinary file ${file}.`);
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
  if (!source.includes('^cargo\\.lock$') || !source.includes('^go\\.sum$')) {
    fail('extension lockfile safety patterns must include Cargo.lock and go.sum.');
  }
  for (const pattern of ['^packages\\.lock\\.json$', '^packages\\.config$', '^directory\\.packages\\.props$']) {
    if (!source.includes(pattern)) {
      fail(`extension lockfile safety patterns must include ${pattern}.`);
    }
  }
}

function assertBlockedProposalEditSummary(formatter) {
  const one = formatter([
    { edit: { path: 'package-lock.json' }, reason: 'Lockfile edits require an explicit model reason.' }
  ]);
  if (!one.includes('package-lock.json') || !one.includes('Lockfile edits require an explicit model reason')) {
    fail('blocked proposal summaries must include the blocked path and reason.');
  }
  const many = formatter([
    { edit: { path: 'uv.lock' }, reason: 'Lockfile edits require an explicit model reason.' },
    { edit: { path: 'pdm.lock' }, reason: 'Lockfile edits require an explicit model reason.' }
  ]);
  if (!many.includes('uv.lock') || !many.includes('plus 1 more')) {
    fail('blocked proposal summaries must include the first blocked path and additional count.');
  }
  const absolute = formatter([
    { edit: { path: 'C:\\Users\\demo\\workspace\\package-lock.json' }, reason: 'Absolute paths are not allowed.' }
  ]);
  if (!absolute.includes('package-lock.json') || absolute.includes('C:/Users')) {
    fail('blocked proposal summaries must avoid exposing absolute path details.');
  }
  const fallback = formatter([{ edit: {}, reason: '' }]);
  if (!fallback.includes('<missing path>') || !fallback.includes('Blocked by safety rules')) {
    fail('blocked proposal summaries must provide a safe fallback for malformed edits.');
  }
}

function assertBlockedProposalVisibleMessages(source) {
  if (!source.includes('Aegis blocked ${blocked.length} unsafe proposed edit(s): ${formatBlockedProposalEditSummary(blocked)}')) {
    fail('proposal preview blocked-edit warning must name the blocked path.');
  }
  if (!source.includes('Aegis refused to apply ${blocked.length} unsafe edit(s): ${formatBlockedProposalEditSummary(blocked)}')) {
    fail('proposal apply blocked-edit error must name the blocked path.');
  }
}

function assertDestinationReasoningPanel(source) {
  for (const required of [
    'Why Aegis chose these files',
    'destinationReasoning',
    'Source: ',
    'Safety: ',
    'Selected context: '
  ]) {
    if (!source.includes(required)) {
      fail(`webview destination reasoning panel is missing ${required}.`);
    }
  }
}

function assertWorkspaceChangeRouting(looksLikeWorkspaceChangeRequest) {
  const implementationRequests = [
    'create a small test project',
    'add a settings page',
    'fix the failing build',
    'scaffold a React app in this workspace'
  ];
  for (const request of implementationRequests) {
    if (!looksLikeWorkspaceChangeRequest(request)) {
      fail(`workspace-change intent detection missed: ${request}`);
    }
  }
  const explanationRequests = [
    'how do I create a file in VS Code?',
    'explain the current file',
    'tell me what this project does',
    'show me how to run this manually'
  ];
  for (const request of explanationRequests) {
    if (looksLikeWorkspaceChangeRequest(request)) {
      fail(`workspace-change intent detection should not capture explanation request: ${request}`);
    }
  }
}

function assertInstructionalCodeBlockProposal(proposalObjectFromInstructionalCodeBlocks) {
  const htmlResponse = [
    'Create `index.html` and paste this:',
    '```html',
    '<!doctype html>',
    '<html><body><h1>Aegis Test</h1></body></html>',
    '```',
    'Then run:',
    '```bash',
    'npm run dev',
    '```'
  ].join('\n');
  const htmlProposal = proposalObjectFromInstructionalCodeBlocks(htmlResponse, 'create a test project');
  if (!htmlProposal || htmlProposal.fileEdits.length !== 1) {
    fail('instructional HTML response must be converted into one file edit.');
  }
  if (htmlProposal.fileEdits[0].path !== 'index.html' || !htmlProposal.fileEdits[0].content.includes('<h1>Aegis Test</h1>')) {
    fail('instructional HTML response must preserve the inferred index.html content.');
  }
  if (!htmlProposal.commands.some((item) => item.command === 'npm run dev')) {
    fail('shell code blocks from instructional responses should become suggested commands, not file edits.');
  }

  const jsResponse = [
    'Use this file:',
    '```javascript',
    "document.querySelector('#app').textContent = 'Ready';",
    '```'
  ].join('\n');
  const jsProposal = proposalObjectFromInstructionalCodeBlocks(jsResponse, 'create a tiny browser app');
  if (!jsProposal || jsProposal.fileEdits[0].path !== 'script.js') {
    fail('unlabeled browser JavaScript code should infer script.js for create/app requests.');
  }

  const shellOnly = proposalObjectFromInstructionalCodeBlocks('```bash\nnpm test\n```', 'create project');
  if (shellOnly) {
    fail('shell-only instructional responses must not become file edits.');
  }

  const explanationOnly = proposalObjectFromInstructionalCodeBlocks('```html\n<div>example</div>\n```', 'explain this html');
  if (explanationOnly) {
    fail('explanation requests with code blocks must not become applyable proposals.');
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
