const vscode = require('vscode');
const http = require('http');
const https = require('https');
const path = require('path');
const fsSync = require('fs');
const fs = require('fs/promises');
const cp = require('child_process');
require.extensions['.ts'] = require.extensions['.ts'] || require.extensions['.js'];
const { buildDestinationReasoning } = require('./src/workspace/destinationReasoning.ts');
const _errorsModule = require('./src/utils/errors.ts');
const _pathSafeModule = require('./src/utils/pathSafe.ts');
const _fsSafeModule = require('./src/utils/fsSafe.ts');
const _proposalSafetyModule = require('./src/proposal/proposalSafety.ts');
const _validationDetectorModule = require('./src/validation/validationDetector.ts');
const _workspaceResolverModule = require('./src/workspace/workspaceResolver.ts');
const _projectScannerModule = require('./src/workspace/projectScanner.ts');
const _proposalParserModule = require('./src/proposal/proposalParser.ts');
const _settingsModule = require('./src/settings/settings.ts');
const _agentModeModule = require('./src/agent/agentMode.ts');
const _contextDiscoveryModule = require('./src/workspace/contextDiscovery.ts');
const {
  AEGIS_CORE_CONTRACT_VERSION,
  validateCoreEnvelope,
  coreEnvelopeData,
  requireCoreOk,
  formatCoreContract
} = require('./src/core/coreEnvelope.ts');
const { createAegisCoreClient, defaultCapabilities, normalizeCoreChanges } = require('./src/core/aegisCoreClient.ts');
const { createWorkflowClient } = require('./src/workflowClient.ts');
const { createExtensionRuntimeState } = require('./src/extensionState.ts');
const { extractWorkflowSummary, extractEditingJob } = require('./src/core/taskSync.ts');
const { createRuntimeLogger } = require('./src/logging/runtimeLog.ts');

let output;
let autopilotTimer;
let autopilotTarget;
let lastProposal;
let panelProvider;
let extensionContext;
let statusBarItem;
let agentState = makeEmptyAgentState();
let chatHistory = [];
let attachedContext = [];
let lastAgentRequest = '';
let lastImpactAnalysis;
let changedFilesHistory = [];
let healthCheckState = makeEmptyHealthCheckState();
let modelDiagnosticsState = makeEmptyModelDiagnosticsState();
let latestErrorInfo = makeEmptyErrorInfo();
let lastFailedCommand = '';
let activeCoreTaskId = '';
let activeCoreWorkflowId = '';
let coreClient;
let workflowClient;
let runtimeLogger;
const runtimeState = createExtensionRuntimeState();
const snapshotCache = new Map();

const MAX_FILE_CHARS = 16000;
const MAX_CONTEXT_CHARS = 62000;
const MAX_PROJECT_SCAN_FILES = 900;
const MAX_PROJECT_SCAN_DEPTH = 7;
const MAX_GRAPH_FILES = 700;
const MAX_SYMBOL_FILES = 550;
const MAX_SYMBOLS = 2500;
const SNAPSHOT_CACHE_TTL_MS = 20000;
const OLLAMA_MODELS_CACHE_MS = 12000;
let ollamaModelsListCache = { key: '', models: null, until: 0 };

function invalidateOllamaModelsCache() {
  ollamaModelsListCache = { key: '', models: null, until: 0 };
}

function getEffectiveOllamaNumCtx(config) {
  const cfg = config || getConfig();
  const maxChars = Number(cfg.maxContextChars) || MAX_CONTEXT_CHARS;
  const estimated = Math.ceil(maxChars / 3) + 8192;
  return Math.min(131072, Math.max(4096, estimated));
}
const BLOCKED_PATH_SEGMENTS = new Set([
  '.git',
  '.hg',
  '.svn',
  '.aegis',
  '.vs',
  '.vscode-test',
  'node_modules',
  'vendor',
  'vendors',
  'third_party',
  'third-party',
  '.venv',
  'venv',
  'env',
  'build',
  'dist',
  'out',
  'target',
  'coverage',
  'x64',
  'debug',
  'release',
  'bin',
  'obj',
  'cmakefiles',
  '.tmp',
  'tmp',
  'library',
  'temp',
  'logs',
  'smoke-artifacts',
  'stress-artifacts'
]);
const SECRET_FILE_PATTERNS = [
  /^\.env(?:\.|$)/i,
  /^id_(?:rsa|dsa|ecdsa|ed25519)$/i,
  /(?:^|[._\-\s])(?:secret(?:s)?|credential(?:s)?|password|passwd|token(?:s)?|private(?:[._\-\s]?key)?|api[_-]?key|auth)(?:[._\-\s]|$)/i,
  /\.(?:key|pem|pfx|p12|keystore|crt|cer)$/i
];
const LOCKFILE_PATTERNS = [
  /^package-lock\.json$/i,
  /^pnpm-lock\.yaml$/i,
  /^yarn\.lock$/i,
  /^bun\.lock$/i,
  /^bun\.lockb$/i,
  /^cargo\.lock$/i,
  /^go\.sum$/i,
  /^packages\.lock\.json$/i,
  /^packages\.config$/i,
  /^directory\.packages\.props$/i,
  /^uv\.lock$/i,
  /^poetry\.lock$/i,
  /^pdm\.lock$/i
];
const IMPORTANT_FILE_PATTERNS = [
  /^readme(?:\..*)?$/i,
  /^todo(?:\..*)?$/i,
  /^changelog(?:\..*)?$/i,
  /^package\.json$/i,
  /^pnpm-lock\.yaml$/i,
  /^yarn\.lock$/i,
  /^bun\.lock$/i,
  /^bun\.lockb$/i,
  /^package-lock\.json$/i,
  /^tsconfig(?:\..*)?\.json$/i,
  /^vite\.config\./i,
  /^next\.config\./i,
  /^webpack\.config\./i,
  /^pyproject\.toml$/i,
  /^uv\.lock$/i,
  /^poetry\.lock$/i,
  /^pdm\.lock$/i,
  /^requirements.*\.txt$/i,
  /^setup\.py$/i,
  /^cmakelists\.txt$/i,
  /^cargo\.toml$/i,
  /^cargo\.lock$/i,
  /^go\.mod$/i,
  /^go\.sum$/i,
  /^packages\.lock\.json$/i,
  /^packages\.config$/i,
  /^directory\.packages\.props$/i,
  /^directory\.build\.(?:props|targets)$/i,
  /^pom\.xml$/i,
  /^build\.gradle/i,
  /^dockerfile$/i,
  /^makefile$/i,
  /^projectversion\.txt$/i,
  /^packages-lock\.json$/i,
  /^.*\.(?:sln|slnx|csproj|fsproj|vbproj|vcxproj|vcxproj\.filters)$/i
];
const MAX_AGENT_REPAIR_ATTEMPTS = 3;

function activate(context) {
  extensionContext = context;
  output = vscode.window.createOutputChannel('Aegis Local Autopilot');
  runtimeLogger = createRuntimeLogger(output);
  refreshCoreRuntimeClients();
  panelProvider = new LocalAutopilotViewProvider(context.extensionUri);
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = 'aegisLocalAutopilot.openPanel';
  updateStatusBar('Indexing', 'Aegis is starting and scanning the workspace.');

  context.subscriptions.push(output);
  context.subscriptions.push(statusBarItem);
  context.subscriptions.push(vscode.window.registerWebviewViewProvider('aegisLocalAutopilot.panel', panelProvider));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.openPanel', () => openPanel()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.runFirstRunSetup', () => runFirstRunSetup({ force: true })));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.chatWithLocalModel', () => openPanel()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.scanModels', () => scanModels(true)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.runHealthCheck', () => runHealthCheck()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.runValidation', (resource) => runValidationForCurrentWorkspace(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.explainActiveFile', () => explainActiveFile()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.explainProject', (resource) => explainProject(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.fixBuildErrors', (resource) => fixBuildErrors(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.reviewActiveFile', () => reviewActiveFile()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.improveSelectedCode', () => improveSelectedCode()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.generateTodoRoadmap', (resource) => generateTodoRoadmap(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.generateProjectRoadmap', (resource) => generateProjectRoadmap(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.continueFromRoadmap', (resource) => continueFromRoadmap(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.createFeature', (resource) => createFeature(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.runAgentMode', (resource) => runAgentMode('', resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.proposePatch', (resource) => proposePatch(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.continueProject', (resource) => continueProject(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.workOnCurrentFolder', (resource) => workOnCurrentFolder(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.previewLastProposal', () => previewLastProposal()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.applyLastProposal', () => applyLastProposal()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.rollbackLastChange', () => rollbackLastAgentChange()));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.runAutopilot', (resource) => runAutopilotOnce('', resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.startAutopilot', (resource) => startAutopilot(resource)));
  context.subscriptions.push(vscode.commands.registerCommand('aegisLocalAutopilot.stopAutopilot', () => stopAutopilot()));
  context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(() => {
    invalidateOllamaModelsCache();
    initializeCurrentWorkspaceMemory().then(() => registerAegisCoreClient().catch(() => {})).catch(reportError);
    refreshStatusBar().catch(() => {});
  }));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((document) => {
    if (document.uri && document.uri.scheme === 'file') {
      const folder = vscode.workspace.getWorkspaceFolder(document.uri);
      if (folder) {
        clearProjectSnapshotCache(folder.uri.fsPath);
      }
    }
  }));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('aegisLocalAutopilot')) {
      invalidateOllamaModelsCache();
      refreshCoreRuntimeClients();
      panelProvider && panelProvider.refresh().catch(() => {});
    }
  }));

  output.appendLine('Aegis Local Autopilot activated.');
  logExtensionEvent('startup', 'Aegis Local Autopilot activated.').catch(() => {});
  initializeCurrentWorkspaceMemory().then(() => {
    registerAegisCoreClient().catch(() => {});
    refreshStatusBar().catch(() => {});
    recoverAgentStateIfNeeded().catch(reportError);
    runFirstRunSetup({ automatic: true }).catch(reportError);
  }).catch(reportError);
  return exportedApi;
}

function deactivate() {
  stopAutopilot(false);
}

class LocalAutopilotViewProvider {
  constructor(extensionUri) {
    this.extensionUri = extensionUri;
    this.view = undefined;
    this.refreshRunning = false;
    this.refreshQueued = false;
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri]
    };
    webviewView.webview.html = renderPanelHtml();
    webviewView.webview.onDidReceiveMessage((message) => this.handleMessage(message));
    this.refresh();
  }

  async handleMessage(message) {
    try {
      if (message.command === 'refresh') {
        await this.refresh();
      } else if (message.command === 'chat') {
        await panelChat(message.text || '', message.model || '');
      } else if (message.command === 'runHealthCheck') {
        await runHealthCheck();
      } else if (message.command === 'runValidation') {
        await runValidationForCurrentWorkspace();
      } else if (message.command === 'runFirstRunSetup') {
        await runFirstRunSetup({ force: true });
      } else if (message.command === 'testModelPrompt') {
        await runModelDiagnostics({ includeFallbacks: false });
      } else if (message.command === 'testFallbackModels') {
        await runModelDiagnostics({ includeFallbacks: true });
      } else if (message.command === 'retryLastAction') {
        await retryLastAction();
      } else if (message.command === 'clearChat') {
        chatHistory = [];
        attachedContext = [];
        await this.refresh();
      } else if (message.command === 'attachCurrentFile') {
        await attachCurrentFile();
        await this.refresh();
      } else if (message.command === 'attachSelectedCode') {
        await attachSelectedCode();
        await this.refresh();
      } else if (message.command === 'explainProject') {
        await explainProject();
      } else if (message.command === 'runAgentMode') {
        await runAgentMode(message.text || '');
      } else if (message.command === 'explainActiveFile') {
        await explainActiveFile();
      } else if (message.command === 'reviewCurrentFile') {
        await reviewActiveFile();
      } else if (message.command === 'improveSelectedCode') {
        await improveSelectedCode();
      } else if (message.command === 'runAutopilot') {
        await runAutopilotOnce(message.text || '');
      } else if (message.command === 'continueProject') {
        await continueProject();
      } else if (message.command === 'continueCurrentTask') {
        await continueCurrentTask();
      } else if (message.command === 'workOnCurrentFolder') {
        await workOnCurrentFolderFromPanel(message.text || '');
      } else if (message.command === 'fixBuildErrors') {
        await fixBuildErrors();
      } else if (message.command === 'generateTodoRoadmap') {
        await generateTodoRoadmap();
      } else if (message.command === 'generateProjectRoadmap') {
        await generateProjectRoadmap();
      } else if (message.command === 'continueFromRoadmap') {
        await continueFromRoadmap();
      } else if (message.command === 'createFeature') {
        await createFeature();
      } else if (message.command === 'previewLastProposal') {
        await previewLastProposal();
      } else if (message.command === 'approveProposal') {
        await approveProposalFromPanel(message.indexes);
      } else if (message.command === 'rejectProposal') {
        await rejectProposalFromPanel();
      } else if (message.command === 'regeneratePlan') {
        await regeneratePlanFromPanel();
      } else if (message.command === 'rollbackLastChange') {
        await rollbackLastAgentChange();
      } else if (message.command === 'openMemory') {
        await openMemoryFromPanel(message.file || '');
      } else if (message.command === 'saveSettings') {
        await saveSettingsFromPanel(message.settings || {});
        await this.refresh();
      } else if (message.command === 'startAutopilot') {
        await startAutopilot();
      } else if (message.command === 'stopAutopilot') {
        stopAutopilot();
      } else if (message.command === 'applyLastProposal') {
        await applyLastProposal();
      }
    } catch (error) {
      reportError(error);
    }
  }

  post(message) {
    if (this.view) {
      this.view.webview.postMessage(message);
    }
  }

  async refresh() {
    if (this.refreshRunning) {
      this.refreshQueued = true;
      return;
    }
    this.refreshRunning = true;
    try {
    const state = {
      config: getConfigSnapshot(),
      running: Boolean(autopilotTimer),
      lastProposalSummary: lastProposal ? lastProposal.summary || 'Proposal ready' : '',
      lastProposalFileCount: lastProposal && Array.isArray(lastProposal.fileEdits) ? lastProposal.fileEdits.length : 0,
      proposal: proposalStateSnapshot(),
      agent: agentState,
      chatHistory,
      attachments: attachedContext.map((item) => ({ label: item.label, chars: item.text.length })),
      memoryFiles: memoryFileNames(),
      dependencyGraph: emptyDependencyGraphSummary(),
      impactAnalysis: impactAnalysisStateSnapshot(),
      stagedPlan: stagedPlanStateSnapshot(),
      changedFilesHistory,
      health: healthCheckState,
      modelDiagnostics: Object.assign({}, modelDiagnosticsState, {
        contextWarning: buildContextSizeWarning(getConfig())
      }),
      errorInfo: latestErrorInfo,
      runtime: runtimeState.snapshot(),
      models: []
    };

    try {
      const target = await resolveWorkspaceTarget(undefined, { silent: true });
      state.models = await getOllamaModels({ target, reportFallback: false });
      const source = state.models.some((model) => isCoreModelSource(model.source)) ? 'Aegis Core' : 'Ollama';
      state.status = `Connected to ${source} model inventory with ${state.models.length} model(s).`;
      if (!latestErrorInfo.message && healthCheckState.overall !== 'fail' && agentState.status === 'Idle') {
        updateStatusBar('Ready', `Aegis connected to ${source} with ${state.models.length} model(s).`);
      }
    } catch (error) {
      state.status = `Model inventory scan failed: ${safeErrorMessage(error)}`;
      updateStatusBar('Models Offline', state.status);
    }

    try {
      const target = await resolveWorkspaceTarget(undefined, { silent: true });
      if (target) {
        await refreshCoreRuntimeDashboard(target).catch(() => {});
        state.runtime = runtimeState.snapshot();
        const snapshot = await getProjectSnapshot(target, { fast: true });
        state.project = projectSnapshotSummary(snapshot);
        state.projectOverview = await buildProjectOverviewState(target, snapshot, state.models);
        state.dependencyGraph = await buildDependencyGraphSummary(target);
        state.impactAnalysis = impactAnalysisStateSnapshot(target);
        state.stagedPlan = stagedPlanStateSnapshot();
        state.changedFilesHistory = await readChangedFilesHistory(target);
      } else {
        state.project = 'No VS Code workspace folder is open.';
        state.projectOverview = emptyProjectOverview();
        updateStatusBar('No Workspace', 'Open a VS Code folder to use Aegis project context.');
      }
    } catch (error) {
      state.project = `Project scan failed: ${safeErrorMessage(error)}`;
    }

    this.post({ command: 'state', state });
    } finally {
      this.refreshRunning = false;
      if (this.refreshQueued) {
        this.refreshQueued = false;
        await this.refresh();
      }
    }
  }
}

async function openPanel() {
  await vscode.commands.executeCommand('workbench.view.extension.aegis-local-ai');
}

async function scanModels(showPicker) {
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  const models = await getOllamaModels({ target, reportFallback: true, bypassModelCache: true });
  const names = models.map((model) => model.name || model.model).filter(Boolean);
  const source = models.some((model) => isCoreModelSource(model.source)) ? 'Aegis Core' : 'Ollama';
  output.appendLine(`Detected ${names.length} local model(s) via ${source}:`);
  names.forEach((name) => output.appendLine(`- ${name}`));
  output.show(true);
  panelProvider && panelProvider.refresh();

  if (showPicker) {
    const selected = await vscode.window.showQuickPick(names, {
      title: 'Aegis Local Models',
      placeHolder: 'Pick a model to set as the primary local coding model'
    });
    if (selected) {
      await vscode.workspace.getConfiguration('aegisLocalAutopilot').update('chatModel', selected, vscode.ConfigurationTarget.Workspace);
      vscode.window.showInformationMessage(`Aegis primary local model set to ${selected}.`);
      panelProvider && panelProvider.refresh();
    }
  }
  return models;
}

async function runFirstRunSetup(options = {}) {
  if (!extensionContext) {
    return;
  }
  const completed = extensionContext.globalState.get('aegis.firstRunSetupComplete', false);
  if (completed && !options.force) {
    return;
  }

  await logExtensionEvent('setup', 'First-run setup started.');
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  let modelNames = [];
  let ollamaStatus = 'Ollama not checked yet.';
  try {
    const models = await getOllamaModels({ target, reportFallback: true, bypassModelCache: true });
    modelNames = models.map((model) => model.name || model.model).filter(Boolean);
    const source = models.some((model) => isCoreModelSource(model.source)) ? 'Aegis Core' : 'Ollama';
    ollamaStatus = `${source} model inventory reachable. Found ${modelNames.length} model(s).`;
  } catch (error) {
    ollamaStatus = `Model inventory check failed: ${safeErrorMessage(error)}`;
  }

  if (modelNames.length) {
    const config = getConfig();
    const preferred = modelNames.includes(config.chatModel) ? config.chatModel : modelNames[0];
    const selected = await vscode.window.showQuickPick(modelNames, {
      title: 'Aegis First-Run Setup: Choose Default Local Model',
      placeHolder: `Current default: ${preferred}`
    });
    if (selected) {
      await vscode.workspace.getConfiguration('aegisLocalAutopilot').update('chatModel', selected, vscode.ConfigurationTarget.Workspace);
      await logExtensionEvent('setup', `Default model selected: ${selected}.`, {}, target);
    }
  } else if (!options.automatic) {
    vscode.window.showWarningMessage('Aegis could not find Ollama models. Install one with ollama pull qwen3-coder:30b.');
  }

  if (target) {
    await ensureWorkspaceMemory(target);
    await logExtensionEvent('setup', '.aegis folder ensured for first-run setup.', { workspace: target.root }, target);
  }

  const health = await runHealthCheck({ silent: true });
  await openSetupChecklist(target, modelNames, ollamaStatus, health);
  await extensionContext.globalState.update('aegis.firstRunSetupComplete', true);
  await logExtensionEvent('setup', 'First-run setup completed.', { health: health.overall }, target);
}

async function openSetupChecklist(target, modelNames, ollamaStatus, health) {
  const config = getConfig();
  const lines = [
    '# Aegis Local Agent Setup Checklist',
    '',
    `Generated: ${new Date().toISOString()}`,
    '',
    '## Setup Status',
    '',
    `- Workspace: ${target ? target.root : 'No workspace folder open'}`,
    `- Ollama: ${ollamaStatus}`,
    `- Default model: ${config.chatModel}`,
    `- Fallback models: ${(config.fallbackModels || []).join(', ') || 'none'}`,
    `- Health check: ${health.overall}`,
    '',
    '## Checklist',
    '',
    `- [${target ? 'x' : ' '}] Open a VS Code workspace folder.`,
    `- [${modelNames.length ? 'x' : ' '}] Start Ollama and install at least one coding model.`,
    `- [${modelNames.includes(config.chatModel) ? 'x' : ' '}] Choose an installed default model.`,
    `- [${target ? 'x' : ' '}] Create project-local .aegis memory folder.`,
    `- [${health.overall === 'pass' ? 'x' : ' '}] Run health check successfully.`,
    '- [ ] Open the Aegis Local Agent sidebar from the Activity Bar.',
    '- [ ] Try a short chat with the selected local model.',
    '- [ ] Generate or update the project roadmap.',
    '',
    '## Useful Commands',
    '',
    '- Aegis: Run Health Check',
    '- Aegis: Scan Local Models',
    '- Aegis: Chat With Local Model',
    '- Aegis: Generate/Update Project Roadmap',
    '- Aegis: Continue Working On This Project',
    '',
    '## Health Details',
    '',
    ...((health.checks || []).map((check) => `- ${check.status.toUpperCase()} - ${check.name}: ${check.detail}${check.fix ? ` Suggested fix: ${check.fix}` : ''}`))
  ];
  await openMarkdownResult('Aegis Setup Checklist', lines.join('\n'));
  panelProvider && panelProvider.refresh();
}

async function runHealthCheck(options = {}) {
  updateStatusBar('Running', 'Running Aegis health check.');
  await logExtensionEvent('health-check', 'Health check started.');
  const started = Date.now();
  const checks = [];
  const config = getConfig();
  const addCheck = (name, status, detail, fix = '') => {
    checks.push({
      name,
      status,
      detail: redactDiagnosticText(detail),
      fix: sanitizeMemoryText(String(fix || ''))
    });
  };

  let target;
  let models = [];

  try {
    target = await resolveWorkspaceTarget(undefined, { silent: true });
    addCheck(
      'Workspace is open',
      target ? 'pass' : 'fail',
      target ? target.root : 'No VS Code workspace folder is open.',
      target ? '' : 'Open the project folder in VS Code, then run the health check again.'
    );

    if (target) {
      try {
        await ensureWorkspaceMemory(target);
        const probePath = path.join(target.workspaceRoot || target.root, '.aegis', 'health-check.tmp');
        await fs.writeFile(probePath, `Aegis health check ${new Date().toISOString()}\n`, 'utf8');
        await fs.readFile(probePath, 'utf8');
        await fs.rm(probePath, { force: true });
        addCheck('.aegis folder is writable', 'pass', '.aegis accepted a write/read/delete probe.');
      } catch (error) {
        addCheck('.aegis folder is writable', 'fail', safeErrorMessage(error), 'Check project folder permissions and make sure antivirus is not blocking writes.');
      }
    }

    if (target) {
      try {
        const healthEnvelope = await getAegisCoreHealth(target);
        addCheck(
          'Aegis Core is reachable',
          'pass',
          `Shared runtime responded at ${config.coreUrl} with ${formatCoreContract(healthEnvelope)}.`
        );
        await registerAegisCoreClient(target);

        const coreChecks = [
          {
            name: 'Aegis Core models contract',
            run: () => getAegisCoreModels(target),
            detail: (result) => `Core reported ${result.models.length} installed model(s); selected ${result.selectedModel || 'none'}.`
          },
          {
            name: 'Aegis Core settings contract',
            run: () => getAegisCoreSettings(target),
            detail: (envelope) => `Core settings available with ${formatCoreContract(envelope)}.`
          },
          {
            name: 'Aegis Core memory contract',
            run: () => getAegisCoreMemory(target),
            detail: (envelope) => `${Object.keys(coreEnvelopeData(envelope).entries || {}).length} shared memory entries visible.`
          },
          {
            name: 'Aegis Core diagnostics contract',
            run: () => getAegisCoreDiagnostics(target),
            detail: (envelope) => `${Object.keys(coreEnvelopeData(envelope).logs || {}).length} shared diagnostic log(s) visible.`
          },
          {
            name: 'Aegis Core validation contract',
            run: () => getAegisCoreValidationSummary(target),
            detail: (envelope) => `${(coreEnvelopeData(envelope).commands || []).length} validation command(s) detected by Core.`
          },
          {
            name: 'Aegis Core release compatibility',
            run: () => getCoreRuntimeClient().checkCompatibility(target, {
              schemaVersion: AEGIS_CORE_CONTRACT_VERSION,
              capabilities: defaultCapabilities()
            }),
            detail: (envelope) => {
              const data = coreEnvelopeData(envelope);
              const fallback = Array.isArray(data.recommendations) ? data.recommendations[0] || '' : '';
              return `Compatibility ${data.status || 'unknown'} for ${data.client_type || 'vscode-extension'} ${data.client_version || ''}. ${fallback}`.trim();
            }
          }
        ];
        for (const item of coreChecks) {
          try {
            const result = await item.run();
            addCheck(item.name, 'pass', item.detail(result));
          } catch (error) {
            addCheck(item.name, 'warn', safeErrorMessage(error), 'VS Code will use the existing local fallback for this workflow.');
          }
        }
      } catch (error) {
        addCheck(
          'Aegis Core is reachable',
          'warn',
          safeErrorMessage(error),
          'Start Aegis Core on the configured local URL to enable shared tasks, settings, diagnostics, and dashboard sync.'
        );
      }
    }

    try {
      const modelStart = Date.now();
      models = await getOllamaModels({ target, reportFallback: true, bypassModelCache: true });
      const source = models.some((model) => isCoreModelSource(model.source)) ? 'Aegis Core' : 'Ollama';
      addCheck('Model inventory is reachable', 'pass', `${source} reported ${models.length} installed model(s) in ${Date.now() - modelStart}ms.`);
    } catch (error) {
      addCheck('Model inventory is reachable', 'fail', safeErrorMessage(error), 'Start Aegis Core and Ollama, or confirm Ollama is listening at the configured URL.');
    }

    const modelNames = models.map((model) => model.name || model.model).filter(Boolean);
    addCheck(
      'Selected model exists',
      modelNames.includes(config.chatModel) ? 'pass' : 'fail',
      modelNames.includes(config.chatModel) ? config.chatModel : `${config.chatModel} was not found.`,
      modelNames.includes(config.chatModel) ? '' : `Run: ollama pull ${config.chatModel}`
    );

    const missingFallbacks = (config.fallbackModels || []).filter((name) => !modelNames.includes(name));
    addCheck(
      'Fallback models exist',
      missingFallbacks.length ? 'warn' : 'pass',
      missingFallbacks.length ? `Missing fallback model(s): ${missingFallbacks.join(', ')}` : (config.fallbackModels || []).join(', '),
      missingFallbacks.length ? `Run: ${missingFallbacks.map((name) => `ollama pull ${name}`).join(' && ')}` : ''
    );

    try {
      if (!extensionContext) {
        throw new Error('Extension context is not available.');
      }
      const value = new Date().toISOString();
      await extensionContext.workspaceState.update('aegis.healthCheck', value);
      const stored = extensionContext.workspaceState.get('aegis.healthCheck');
      addCheck('VS Code extension storage works', stored === value ? 'pass' : 'fail', stored === value ? 'Workspace storage round-trip succeeded.' : 'Workspace storage did not return the expected value.');
    } catch (error) {
      addCheck('VS Code extension storage works', 'fail', safeErrorMessage(error), 'Reload VS Code or check whether extension storage is writable.');
    }

    try {
      const probe = await runShellProbe();
      addCheck('Terminal commands can run', probe.success ? 'pass' : 'fail', probe.output, probe.success ? '' : 'Check shell availability and VS Code permissions.');
    } catch (error) {
      addCheck('Terminal commands can run', 'fail', safeErrorMessage(error), 'Check shell availability and VS Code permissions.');
    }

    if (target) {
      try {
        const backupRoot = path.join(target.workspaceRoot || target.root, '.aegis', 'backups', `health-check-${timestampForPath()}`);
        await fs.mkdir(backupRoot, { recursive: true });
        await fs.writeFile(path.join(backupRoot, 'probe.txt'), 'backup probe\n', 'utf8');
        await fs.rm(backupRoot, { recursive: true, force: true });
        addCheck('Backups can be created', 'pass', '.aegis/backups accepted a create/delete probe.');
      } catch (error) {
        addCheck('Backups can be created', 'fail', safeErrorMessage(error), 'Check project folder permissions for .aegis/backups.');
      }

      try {
        updateStatusBar('Indexing', 'Health check is writing dependency and symbol indexes.');
        const snapshot = await getProjectSnapshot(target, { fast: true });
        const dependencyGraph = await buildDependencyGraph(target, snapshot);
        const symbolIndex = await buildSymbolIndex(target, snapshot, dependencyGraph);
        const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
        await fs.writeFile(path.join(memoryRoot, 'dependency-graph.json'), JSON.stringify(dependencyGraph, null, 2), 'utf8');
        await fs.writeFile(path.join(memoryRoot, 'symbol-index.json'), JSON.stringify(symbolIndex, null, 2), 'utf8');
        addCheck('Dependency and symbol indexes can be written', 'pass', `Wrote ${dependencyGraph.nodes.length} graph node(s), ${dependencyGraph.edges.length} edge(s), and ${symbolIndex.symbols.length} symbol(s).`);
      } catch (error) {
        addCheck('Dependency and symbol indexes can be written', 'fail', safeErrorMessage(error), 'Check .aegis write permissions and whether scanned files are readable.');
      }
    }
  } catch (error) {
    addCheck('Health check runner', 'fail', safeErrorMessage(error), 'Open the Aegis output panel for details, then retry.');
    reportError(error, { failedCommand: 'Aegis: Run Health Check', retryCommand: 'healthCheck' });
  }

  const overall = checks.some((check) => check.status === 'fail')
    ? 'fail'
    : (checks.some((check) => check.status === 'warn') ? 'warn' : 'pass');
  healthCheckState = {
    overall,
    checkedAt: new Date().toISOString(),
    elapsedMs: Date.now() - started,
    checks
  };
  await logExtensionEvent('health-check', `Health check finished: ${overall}.`, {
    elapsedMs: healthCheckState.elapsedMs,
    checks: checks.map((check) => `${check.status}: ${check.name}`)
  }, target);
  updateStatusBar(overall === 'pass' ? 'Ready' : (overall === 'warn' ? 'Ready' : 'Error'), `Health check ${overall}.`);
  panelProvider && panelProvider.refresh();

  if (!options.silent) {
    await openMarkdownResult('Aegis Health Check', healthCheckToMarkdown(healthCheckState));
  }
  return healthCheckState;
}

async function runModelDiagnostics(options = {}) {
  updateStatusBar('Running', 'Testing local model diagnostics.');
  await logExtensionEvent('model-diagnostics', 'Model diagnostics started.', { includeFallbacks: Boolean(options.includeFallbacks) });
  const config = getConfig();
  const diagnostics = {
    checkedAt: new Date().toISOString(),
    installedModels: [],
    primary: undefined,
    fallbacks: [],
    contextWarning: buildContextSizeWarning(config)
  };

  try {
    const target = await resolveWorkspaceTarget(undefined, { silent: true });
    const models = await getOllamaModels({ target, reportFallback: true, bypassModelCache: true });
    diagnostics.installedModels = models.map((model) => model.name || model.model).filter(Boolean);
    diagnostics.primary = await testSingleModel(config.chatModel);
    if (options.includeFallbacks) {
      for (const model of config.fallbackModels || []) {
        diagnostics.fallbacks.push(await testSingleModel(model));
      }
    }
    modelDiagnosticsState = diagnostics;
    await logExtensionEvent('model-diagnostics', 'Model diagnostics finished.', {
      primary: diagnostics.primary ? diagnostics.primary.status : 'not-tested',
      fallbacks: diagnostics.fallbacks.map((item) => `${item.model}:${item.status}`)
    });
    updateStatusBar(diagnostics.primary && diagnostics.primary.status === 'pass' ? 'Ready' : 'Error', diagnostics.primary ? diagnostics.primary.detail : 'Model diagnostics finished.');
    panelProvider && panelProvider.refresh();
  } catch (error) {
    reportError(error, { failedCommand: 'Model diagnostics', retryCommand: 'modelDiagnostics' });
  }
}

async function testSingleModel(model) {
  const started = Date.now();
  try {
    const response = await askOllama(model, 'Reply with exactly: Aegis model diagnostics ok.', {
      temperature: 0,
      timeoutMs: 120000
    });
    return {
      model,
      status: /Aegis model diagnostics ok/i.test(response) ? 'pass' : 'warn',
      latencyMs: Date.now() - started,
      detail: truncateMiddle(response, 400)
    };
  } catch (error) {
    return {
      model,
      status: 'fail',
      latencyMs: Date.now() - started,
      detail: safeErrorMessage(error, 400)
    };
  }
}

function healthCheckToMarkdown(state) {
  const lines = [
    `Overall: ${state.overall}`,
    `Checked: ${state.checkedAt}`,
    `Elapsed: ${state.elapsedMs}ms`,
    '',
    '## Checks'
  ];
  for (const check of state.checks || []) {
    lines.push(`- ${check.status.toUpperCase()} - ${check.name}: ${check.detail || 'No detail.'}`);
    if (check.fix) {
      lines.push(`  Suggested fix: ${check.fix}`);
    }
  }
  return lines.join('\n');
}

function runShellProbe() {
  const command = process.platform === 'win32'
    ? 'cmd /d /c echo aegis-health'
    : 'sh -c "echo aegis-health"';
  return new Promise((resolve) => {
    cp.exec(command, {
      timeout: 30000,
      windowsHide: true,
      maxBuffer: 1024 * 256
    }, (error, stdout, stderr) => {
      resolve({
        success: !error && /aegis-health/.test(stdout || ''),
        output: truncateMiddle([stdout, stderr, error ? safeErrorMessage(error) : ''].filter(Boolean).join('\n') || 'Shell probe completed.', 2000)
      });
    });
  });
}

function buildContextSizeWarning(config) {
  const maxChars = Number(config.maxContextChars || MAX_CONTEXT_CHARS);
  const numCtx = getEffectiveOllamaNumCtx(config);
  const estimatedTokens = Math.ceil(maxChars / 4);
  if (estimatedTokens > numCtx * 0.85) {
    return `Configured max context is about ${estimatedTokens} estimated tokens, close to the Ollama num_ctx of ${numCtx}. Lower maxContextChars if prompts fail or slow down.`;
  }
  return `Configured max context is about ${estimatedTokens} estimated tokens; Ollama requests use num_ctx ${numCtx} (derived from maxContextChars).`;
}

async function retryLastAction() {
  await logExtensionEvent('retry', 'Retry requested from Aegis error panel.', latestErrorInfo);
  if (latestErrorInfo.retryCommand === 'healthCheck') {
    await runHealthCheck();
    return;
  }
  if (latestErrorInfo.retryCommand === 'modelDiagnostics') {
    await runModelDiagnostics({ includeFallbacks: true });
    return;
  }
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  if (lastAgentRequest && target) {
    latestErrorInfo = makeEmptyErrorInfo();
    await runAgentMode(lastAgentRequest, target);
    return;
  }
  await runHealthCheck();
}

async function explainActiveFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('Open a file first.');
    return;
  }

  const fileContext = activeEditorContext(editor);
  const prompt = [
    'Explain this file for a developer joining the Aegis project.',
    'Focus on responsibilities, important functions, data flow, and likely next edits.',
    '',
    fileContext
  ].join('\n');

  const response = await askOllamaWithFallback(getConfig().fastModel, prompt, { temperature: 0.2 });
  await openMarkdownResult('Aegis Local Explain', response);
}

async function explainProject(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before explaining the project.');
    return;
  }

  const snapshot = await getProjectSnapshot(target);
  const context = projectSnapshotToContext(snapshot, 'Explain this project.');
  const prompt = [
    'Explain the currently opened VS Code project for a developer.',
    'Cover purpose, structure, detected language/framework, build/test entry points, important files, and likely risks.',
    'Keep it practical and grounded in the project scan.',
    '',
    context
  ].join('\n');

  const response = await askOllamaWithFallback(getConfig().fastModel, prompt, { temperature: 0.2 });
  await openMarkdownResult('Aegis Project Explanation', response);
  panelProvider && panelProvider.post({ command: 'chatResult', text: response });
}

async function reviewActiveFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('Open a file first.');
    return;
  }

  const fileContext = activeEditorContext(editor);
  const prompt = [
    'Review this file like a senior engineer.',
    'Prioritize bugs, safety risks, maintainability issues, missing validation, and concrete improvements.',
    'Return concise findings with file-relative references when possible.',
    '',
    fileContext
  ].join('\n');

  const response = await askOllamaWithFallback(getConfig().chatModel, prompt, { temperature: 0.15 });
  await openMarkdownResult('Aegis Local Review', response);
}

async function fixBuildErrors(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before fixing build errors.');
    return;
  }

  const snapshot = await getProjectSnapshot(target, { fast: true });
  const diagnostics = collectDiagnostics(target);
  const validation = await runDetectedValidation(target, snapshot);
  await recordValidationResult(target, validation);
  if (!diagnostics.length && validation.success) {
    const message = validation.skipped
      ? 'No build/test validation command was detected, and VS Code has no diagnostics to repair.'
      : 'Detected validation passed, and VS Code has no diagnostics to repair.';
    updateAgentState({
      status: 'No build errors detected',
      validationOutput: summarizeValidation(validation)
    });
    vscode.window.showInformationMessage(message);
    return;
  }

  const objective = diagnostics.length
    ? `Fix the current build/type/lint errors reported by VS Code diagnostics. Diagnostics:\n${diagnostics.join('\n')}`
    : `Fix the validation failure in this project. Inspect only the relevant files and propose the smallest safe correction.\n\nValidation output:\n${summarizeValidation(validation)}`;
  await runAgentMode(objective, target);
}

async function improveSelectedCode() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('Open a file and select code before asking Aegis to improve it.');
    return;
  }
  if (editor.selection.isEmpty) {
    vscode.window.showWarningMessage('Select the code you want improved first.');
    return;
  }

  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open this file inside a VS Code workspace folder first.');
    return;
  }

  const rel = path.relative(target.root, editor.document.uri.fsPath);
  const selection = editor.document.getText(editor.selection);
  const fullFile = editor.document.getText();
  const context = [
    projectSnapshotToContext(await getProjectSnapshot(target, { fast: true }), 'Improve selected code.'),
    '',
    `# Active File\n${rel}`,
    `# Selected Range\n${editor.selection.start.line + 1}:${editor.selection.start.character + 1}-${editor.selection.end.line + 1}:${editor.selection.end.character + 1}`,
    formatFileChunk(`SELECTED:${rel}`, selection),
    formatFileChunk(`FULL_FILE:${rel}`, fullFile)
  ].join('\n\n');

  const prompt = buildAutopilotPrompt(
    `Improve only the selected code in ${rel}. Return the complete replacement content for ${rel}; do not rewrite unrelated files.`,
    context
  );
  const raw = await askOllamaWithFallback(getConfig().chatModel, prompt, { temperature: 0.12, json: true, timeoutMs: 900000 });
  const proposal = parseProposal(raw, target, `Improve selected code in ${rel}`);
  lastProposal = proposal;
  await saveProposal(proposal);
  await showProposalPreview(proposal);
}

async function generateTodoRoadmap(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before generating a TODO roadmap.');
    return;
  }

  const snapshot = await getProjectSnapshot(target);
  const prompt = [
    'Generate a practical TODO roadmap for the currently opened project.',
    'Use the project scan, TODO comments, README/build files, and diagnostics.',
    'Group work into small safe milestones. Do not invent broad rewrites.',
    '',
    projectSnapshotToContext(snapshot, 'Generate TODO roadmap.')
  ].join('\n');

  const response = await askOllamaWithFallback(getConfig().chatModel, prompt, { temperature: 0.2 });
  await openMarkdownResult('Aegis TODO Roadmap', response);
  panelProvider && panelProvider.post({ command: 'chatResult', text: response });
}

async function generateProjectRoadmap(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before generating a project roadmap.');
    return;
  }

  await ensureWorkspaceMemory(target);
  const coreRoadmap = await tryGenerateAegisCoreRoadmap(target);
  if (coreRoadmap) {
    await openMemoryDocument(target, 'roadmap.md');
    panelProvider && panelProvider.post({ command: 'chatResult', text: coreRoadmap.markdown || 'Aegis Core updated the project roadmap.' });
    return;
  }

  const snapshot = await getProjectSnapshot(target);
  await updateWorkspaceMemoryFromSnapshot(target, snapshot);
  const memoryContext = await readWorkspaceMemoryContext(target);
  const prompt = [
    'Generate or update the local project roadmap for this VS Code workspace.',
    'Create these sections: current project state, completed features, missing features, bugs/risks, next best tasks, recommended priority order.',
    'Be concrete and safe. Prefer small tasks that can be validated. Preserve human-written notes by returning only the managed generated roadmap section content.',
    '',
    await buildFocusedProjectContext(snapshot, 'Generate/update project roadmap.', { includeMemory: false }),
    memoryContext ? `# Existing Project Memory\n${memoryContext}` : ''
  ].filter(Boolean).join('\n\n');

  const roadmap = await askOllamaWithFallback(getConfig().chatModel, prompt, { temperature: 0.2, timeoutMs: 900000 });
  await writeManagedSection(target, 'roadmap.md', 'Aegis Generated Roadmap', roadmap);
  await updateWorkspaceMemoryFromSnapshot(target, snapshot);
  await openMemoryDocument(target, 'roadmap.md');
  panelProvider && panelProvider.post({ command: 'chatResult', text: roadmap });
}

async function continueFromRoadmap(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before continuing from roadmap.');
    return;
  }
  await ensureWorkspaceMemory(target);
  const roadmap = await readMemoryFile(target, 'roadmap.md');
  if (!roadmap.trim()) {
    vscode.window.showWarningMessage('No roadmap found yet. Run "Aegis: Generate/Update Project Roadmap" first.');
    return;
  }
  try {
    const workflow = await getWorkflowRuntimeClient().continueRoadmap(target, 'Continue from the current VS Code project roadmap.', {
      command: 'continueFromRoadmap',
      model: getConfig().fastModel,
      safetyMode: getConfig().safetyMode
    });
    activeCoreWorkflowId = workflow.id || activeCoreWorkflowId;
    runtimeState.setActiveWorkflow(workflow.summary);
    recordRuntimeOperation('continue-roadmap', 'core', 'started', 'Roadmap continuation registered with Aegis Core.', {
      workflowId: activeCoreWorkflowId
    });
    startCoreWorkflowEventRefresh(target, activeCoreWorkflowId);
  } catch (error) {
    recordCoreDisconnected(error, 'continue-roadmap');
  }

  const prompt = [
    'Read this project roadmap and pick the highest-value safe next task.',
    'Choose one task only. Prefer small, reviewable, validation-friendly work.',
    'Return the task as one concise instruction for Agent Mode.',
    '',
    sanitizeMemoryText(roadmap)
  ].join('\n');
  const selectedTask = await askOllamaWithFallback(getConfig().fastModel, prompt, { temperature: 0.15 });
  await runAgentMode(`Continue from roadmap: ${selectedTask}`, target);
}

async function createFeature(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before creating a feature.');
    return;
  }
  const feature = await vscode.window.showInputBox({
    title: 'Create feature in current project',
    prompt: `Describe the feature to create in ${target.label}.`,
    placeHolder: 'Example: add a settings screen for local model selection'
  });
  if (!feature) {
    return;
  }
  await runAgentMode(`Create this feature in the current project: ${feature}`, target);
}

async function proposePatch(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before drafting a patch.');
    return;
  }
  const task = await vscode.window.showInputBox({
    title: 'Draft a local Aegis patch',
    prompt: `What should the local model work on in ${target.label}?`,
    placeHolder: 'Example: tighten model registry health handling'
  });
  if (!task) {
    return;
  }
  await runAutopilotOnce(task, target);
}

async function continueProject(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before continuing work.');
    return;
  }
  await runAgentMode('', target);
}

async function continueCurrentTask() {
  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before continuing the current task.');
    return;
  }
  const request = lastAgentRequest && lastAgentRequest.trim()
    ? `Continue the current task with the smallest safe next step: ${lastAgentRequest}`
    : 'Continue the current project task with the smallest safe next step.';
  await runAgentMode(request, target);
}

async function runValidationForCurrentWorkspace(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before running validation.');
    return;
  }
  pushProgress('Running validation', 'Detected safe project checks and started validation.');
  await logExtensionEvent('validation', 'Manual validation requested from Aegis.', { target: target.root }, target);
  const snapshot = await getProjectSnapshot(target, { fast: true });
  const validation = await runDetectedValidation(target, snapshot);
  await recordValidationResult(target, validation);
  recordRuntimeOperation('rollback', 'local', 'completed', 'Rolled back with VS Code local backup manifest.', {
    checkpointId: manifest.backupId,
    workflowId: activeCoreWorkflowId || ''
  });
  updateAgentState({
    status: validation.success ? 'Validation passed' : 'Validation failed',
    validationOutput: summarizeValidation(validation)
  });
  if (!validation.success) {
    await recordRealWorldFinding('Manual Validation Failure', [
      `Workspace: ${target.root}`,
      `Output: ${summarizeValidation(validation)}`
    ], target);
  }
  return validation;
}

async function workOnCurrentFolder(resource) {
  const target = await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open or select a folder before assigning a task.');
    return;
  }
  const task = await vscode.window.showInputBox({
    title: `Aegis task in ${target.label}`,
    prompt: 'Tell the local model what to do from this folder.',
    placeHolder: 'Example: add tests for the backend model registry endpoints'
  });
  if (!task) {
    return;
  }
  await runAgentMode(task, target);
}

async function workOnCurrentFolderFromPanel(promptText) {
  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before assigning a task.');
    return;
  }
  const trimmed = String(promptText || '').trim();
  const task = trimmed || await vscode.window.showInputBox({
    title: `Aegis task in ${target.label}`,
    prompt: 'Tell the local model what to do from this folder.',
    placeHolder: 'Example: add tests for the backend model registry endpoints'
  });
  if (!task) {
    return;
  }
  await runAgentMode(task, target);
}

async function panelChat(text, model) {
  const trimmed = text.trim();
  if (!trimmed) {
    return;
  }
  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before chatting with local context.');
    return;
  }
  try {
    const workflow = await getWorkflowRuntimeClient().startChat(target, trimmed, {
      command: 'panelChat',
      model: model || getConfig().chatModel,
      safetyMode: getConfig().safetyMode
    });
    activeCoreWorkflowId = workflow.id || activeCoreWorkflowId;
    runtimeState.setActiveWorkflow(workflow.summary);
    recordRuntimeOperation('chat', 'core', 'tracked', 'Chat request registered as a Core workflow.', {
      workflowId: activeCoreWorkflowId
    });
    startCoreWorkflowEventRefresh(target, activeCoreWorkflowId);
  } catch (error) {
    recordCoreDisconnected(error, 'chat');
  }
  if (looksLikeWorkspaceChangeRequest(trimmed)) {
    const handoff = 'This looks like a workspace change, so Aegis is drafting an applyable proposal with file edits instead of leaving paste-and-save instructions in chat.';
    chatHistory.push({ role: 'user', text: trimmed, at: new Date().toISOString() });
    chatHistory.push({ role: 'assistant', text: handoff, at: new Date().toISOString() });
    chatHistory = chatHistory.slice(-30);
    panelProvider && panelProvider.post({ command: 'chatResult', text: handoff });
    panelProvider && panelProvider.post({ command: 'chatHistory', chatHistory });
    await runAgentMode(trimmed, target);
    return;
  }
  const context = await collectWorkspaceContext('Panel chat context', target);
  const chatMemory = await buildChatMemoryContext(target);
  const prompt = [
    'You are Aegis Local Autopilot inside VS Code.',
    'Answer using the local project context. Be concise, specific, and practical.',
    `Current target folder: ${target.root}`,
    target.focusRelative ? `Selected folder focus: ${target.focusRelative}` : '',
    target.focusFileRelative ? `Selected file focus: ${target.focusFileRelative}` : '',
    '',
    chatMemory,
    context,
    attachedContext.length ? `# Attached Context\n${attachedContext.map((item) => formatFileChunk(item.label, item.text)).join('\n\n')}` : '',
    chatHistory.length ? `# Recent Conversation\n${chatHistory.slice(-8).map((item) => `${item.role}: ${item.text}`).join('\n\n')}` : '',
    '',
    `User request:\n${trimmed}`
  ].filter(Boolean).join('\n');

  chatHistory.push({ role: 'user', text: trimmed, at: new Date().toISOString() });
  const response = await askOllamaWithFallback(model || getConfig().chatModel, prompt, { temperature: 0.25 });
  chatHistory.push({ role: 'assistant', text: response, at: new Date().toISOString() });
  chatHistory = chatHistory.slice(-30);
  panelProvider && panelProvider.post({ command: 'chatResult', text: response });
  panelProvider && panelProvider.post({ command: 'chatHistory', chatHistory });
  output.appendLine(response);
  output.show(true);
}

async function buildChatMemoryContext(target) {
  const chunks = [];
  if (agentState.currentTask || lastAgentRequest) {
    chunks.push(`# Current Task\n${sanitizeMemoryText(agentState.currentTask || lastAgentRequest)}`);
  }
  const editor = vscode.window.activeTextEditor;
  if (editor && editor.document.uri.scheme === 'file' && isPathInside(target.root, editor.document.uri.fsPath)) {
    chunks.push(`# Active File\n${path.relative(target.root, editor.document.uri.fsPath).replace(/\\/g, '/')}`);
  }
  if (latestErrorInfo.message) {
    chunks.push(`# Recent Error\n${sanitizeMemoryText(latestErrorInfo.message)}\nLikely cause: ${sanitizeMemoryText(latestErrorInfo.likelyCause || '')}`);
  }
  const history = await readChangedFilesHistory(target);
  if (history.length) {
    const latest = history[0];
    chunks.push(`# Recent Approval\n${sanitizeMemoryText(latest.summary || 'Aegis change')}\nFiles: ${(latest.files || []).slice(0, 8).join(', ')}`);
  }
  const roadmap = await readMemoryFile(target, 'roadmap.md');
  if (roadmap.trim()) {
    const roadmapLines = sanitizeMemoryText(roadmap).split(/\r?\n/).filter((line) => line.trim()).slice(0, 12).join('\n');
    chunks.push(`# Current Roadmap Goal\n${roadmapLines}`);
  }
  return chunks.join('\n\n');
}

async function attachCurrentFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== 'file') {
    vscode.window.showWarningMessage('Open a file before attaching it.');
    return;
  }
  const label = vscode.workspace.asRelativePath(editor.document.uri, false);
  attachedContext.push({ label: `Current file: ${label}`, text: truncateMiddle(editor.document.getText(), 24000) });
  attachedContext = attachedContext.slice(-6);
}

async function attachSelectedCode() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== 'file') {
    vscode.window.showWarningMessage('Open a file and select code before attaching it.');
    return;
  }
  if (editor.selection.isEmpty) {
    vscode.window.showWarningMessage('Select code before attaching it.');
    return;
  }
  const label = vscode.workspace.asRelativePath(editor.document.uri, false);
  const range = `${editor.selection.start.line + 1}:${editor.selection.start.character + 1}-${editor.selection.end.line + 1}:${editor.selection.end.character + 1}`;
  attachedContext.push({ label: `Selected code: ${label} ${range}`, text: truncateMiddle(editor.document.getText(editor.selection), 16000) });
  attachedContext = attachedContext.slice(-6);
}

function isCancellationError(error) {
  if (error instanceof vscode.CancellationError) {
    return true;
  }
  const msg = error && error.message ? String(error.message) : '';
  return /cancelled/i.test(msg);
}

async function handleAgentCancellation(target, request) {
  updateAgentState({
    status: 'Cancelled',
    currentTask: request || '',
    activePlan: 'Agent Mode cancelled.',
    validationOutput: ''
  });
  await writeAgentRecovery(target, {
    status: 'cancelled',
    request: request || lastAgentRequest || '',
    summary: 'User cancelled Agent Mode.'
  }).catch(() => {});
  if (activeCoreTaskId) {
    await updateAegisCoreTaskStatus(target, activeCoreTaskId, 'cancelled', 'User cancelled in VS Code.').catch(() => {});
    activeCoreTaskId = '';
  }
  if (activeCoreWorkflowId) {
    await getWorkflowRuntimeClient().cancel(target, activeCoreWorkflowId, 'User cancelled in VS Code.').catch(() => {});
    recordRuntimeOperation('workflow', 'core', 'cancelled', 'Active workflow cancelled from VS Code.', {
      workflowId: activeCoreWorkflowId
    });
    activeCoreWorkflowId = '';
  }
  panelProvider && panelProvider.refresh();
}

async function runAgentMode(objective, targetOrResource) {
  const config = getConfig();
  const target = isWorkspaceTarget(targetOrResource)
    ? targetOrResource
    : await resolveWorkspaceTarget(targetOrResource);
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before running Agent Mode.');
    return;
  }

  const request = objective && objective.trim()
    ? objective.trim()
    : 'Continue working on this project. Choose the safest useful next step from the current workspace state.';
  lastAgentRequest = request;
  resetAgentState(target, config.chatModel);
  latestErrorInfo = makeEmptyErrorInfo();
  await writeAgentRecovery(target, {
    status: 'running',
    request,
    model: config.chatModel,
    currentTask: request
  });
  await logExtensionEvent('agent', 'Agent Mode started.', { request, target: target.root }, target);
  try {
    const workflow = await getWorkflowRuntimeClient().startFeature(target, request, {
      command: 'runAgentMode',
      model: config.chatModel,
      safetyMode: config.safetyMode
    });
    activeCoreWorkflowId = workflow.id || '';
    runtimeState.setActiveWorkflow(workflow.summary);
    recordRuntimeOperation('agent-workflow', 'core', 'started', 'Agent Mode workflow registered with Aegis Core.', {
      workflowId: activeCoreWorkflowId
    });
    startCoreWorkflowEventRefresh(target, activeCoreWorkflowId);
  } catch (error) {
    output && output.appendLine(`Aegis Core workflow creation skipped: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'agent-workflow');
  }
  activeCoreTaskId = await createAegisCoreTask(target, request, 'vscode-agent', request, {
    model: config.chatModel,
    safetyMode: config.safetyMode,
    workflowId: activeCoreWorkflowId || ''
  });
  if (activeCoreTaskId) {
    await updateAegisCoreTaskStatus(target, activeCoreTaskId, 'running', 'VS Code agent is inspecting workspace context.');
  }
  updateAgentState({
    status: 'Inspecting workspace',
    currentTask: request,
    activePlan: `Request: ${request}`,
    validationOutput: '',
    pendingDiffs: [],
    repairAttempts: 0
  });
  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Aegis Agent Mode',
        cancellable: true
      },
      async (progress, token) => {
        const report = (message, detail) =>
          progress.report({
            message: detail ? `${message}: ${detail}` : message
          });
        report('Inspecting workspace', 'Scanning structure, project memory, diagnostics, and validation hints.');
        await ensureWorkspaceMemory(target);
        if (token.isCancellationRequested) {
          throw new vscode.CancellationError();
        }
        const snapshot = await getProjectSnapshot(target);
        report('Updating project memory', `${snapshot.fileCount} files sampled for current workspace context.`);
        await updateWorkspaceMemoryFromSnapshot(target, snapshot);
        if (token.isCancellationRequested) {
          throw new vscode.CancellationError();
        }
        const memoryContext = await readWorkspaceMemoryContext(target);
        const dependencyGraph = await readJsonMemoryFile(target, 'dependency-graph.json', null);
        const symbolIndex = await readJsonMemoryFile(target, 'symbol-index.json', null);
        const impactAnalysis = await buildImpactAnalysis(target, snapshot, request, dependencyGraph, symbolIndex);
        lastImpactAnalysis = impactAnalysis;
        report('Building impact analysis', `${impactAnalysis.likelyAffectedFiles.length} likely affected file(s), risk ${impactAnalysis.riskLevel}.`);
        updateAgentState({
          status: 'Impact analysis ready',
          activePlan: impactAnalysisToPlanText(impactAnalysis)
        });
        const context = await buildFocusedProjectContext(snapshot, request, {
          memoryContext,
          dependencyGraph,
          symbolIndex,
          impactAnalysis
        });
        if (token.isCancellationRequested) {
          throw new vscode.CancellationError();
        }
        updateAgentState({ status: 'Creating plan' });
        report('Calling local model', `Using ${config.chatModel} to create a small approval-based plan.`);
        const proposal = await createAgentProposal(target, request, context, 0, undefined, token);
        enrichProposalWithRepoIntelligence(proposal, impactAnalysis);
        attachDestinationReasoning(proposal, snapshot, target);
        lastProposal = proposal;
        await saveProposal(proposal);
        await writeAgentRecovery(target, {
          status: 'waiting-approval',
          request,
          summary: proposal.summary,
          files: proposal.fileEdits.map((edit) => edit.path)
        });
        if (activeCoreTaskId) {
          await updateAegisCoreTaskStatus(target, activeCoreTaskId, 'waiting_for_approval', proposal.summary || 'Proposal ready for approval.');
        }
        await appendAgentHistory(target, {
          type: 'proposal',
          request,
          summary: proposal.summary,
          files: proposal.fileEdits.map((edit) => edit.path),
          risk: proposal.risk
        });

        updateAgentState({
          status: 'Waiting for approval',
          activePlan: proposalToPlanText(proposal),
          pendingDiffs: proposal.fileEdits.map((edit) => edit.path)
        });
        report('Waiting for approval', `${proposal.fileEdits.length} proposed file change(s) are ready for review.`);

        const previewResult = await showProposalPreview(proposal, { allowApply: true, staged: true });
        if (previewResult !== 'applied') {
          updateAgentState({
            status: previewResult === 'rejected' ? 'Rejected' : 'Waiting',
            validationOutput: 'No files were changed. Review the proposal or run Agent Mode again with a narrower request.'
          });
          await appendAgentHistory(target, {
            type: 'proposal-not-applied',
            request,
            result: previewResult,
            summary: proposal.summary
          });
          await writeAgentRecovery(target, {
            status: 'paused',
            request,
            result: previewResult,
            summary: proposal.summary
          });
          return;
        }

        await runValidationAndRepairLoop(target, request, proposal, snapshot, token);
        if (!/repair paused|waiting|paused/i.test(agentState.status || '')) {
          await clearAgentRecovery(target);
        }
      }
    );
  } catch (error) {
    if (error instanceof vscode.CancellationError || isCancellationError(error)) {
      await handleAgentCancellation(target, request);
      return;
    }
    throw error;
  }
}

async function createAgentProposal(target, request, context, repairAttempt, validationFailure, cancelToken) {
  const repairText = validationFailure
    ? [
        '# Validation Failure To Repair',
        validationFailure.summary,
        '',
        validationFailure.output
      ].join('\n')
    : '';
  const prompt = buildAutopilotPrompt(
    repairAttempt > 0
      ? `Repair validation failure for this request: ${request}. This is repair attempt ${repairAttempt} of ${MAX_AGENT_REPAIR_ATTEMPTS}.`
      : request,
    [context, repairText].filter(Boolean).join('\n\n')
  );
  const raw = await askOllamaWithFallback(getConfig().chatModel, prompt, {
    temperature: repairAttempt > 0 ? 0.08 : 0.15,
    json: true,
    timeoutMs: 900000,
    cancellationToken: cancelToken
  });
  return parseProposal(raw, target, request);
}

async function runValidationAndRepairLoop(target, request, initialProposal, initialSnapshot, cancelToken) {
  if (cancelToken && cancelToken.isCancellationRequested) {
    throw new vscode.CancellationError();
  }
  let currentProposal = initialProposal;
  let snapshot = initialSnapshot;
  await writeAgentRecovery(target, { status: 'validating', request, summary: currentProposal.summary });
  let validation = await runDetectedValidation(target, snapshot);
  await recordValidationResult(target, validation);
  await appendDecisionRecord(target, currentProposal, validation, validation.success ? 'Continue with the next roadmap item.' : 'Inspect validation failure and propose a focused repair.');
  await appendAgentHistory(target, {
    type: 'validation',
    request,
    success: validation.success,
    commands: validation.commands.map((item) => item.command)
  });

  if (validation.success) {
    updateAgentState({
      status: 'Validation passed',
      validationOutput: summarizeValidation(validation),
      activePlan: `${proposalToPlanText(currentProposal)}\n\nNext step: continue with the next small roadmap item or ask for a specific feature.`
    });
    vscode.window.showInformationMessage('Aegis Agent Mode applied changes and validation passed.');
    await writeAgentRecovery(target, { status: 'completed', request, validation: 'passed' });
    return;
  }
  await recordRealWorldFinding('Validation Failure', [
    `Request: ${request}`,
    `Summary: ${currentProposal.summary || 'No proposal summary'}`,
    `Output: ${summarizeValidation(validation)}`
  ], target);
  try {
    const repairWorkflow = await getWorkflowRuntimeClient().startRepair(target, `Repair validation failure for: ${request}`, {
      command: 'repair_project',
      model: getConfig().chatModel,
      safetyMode: getConfig().safetyMode,
      metadata: {
        parent_workflow_id: activeCoreWorkflowId || '',
        validation_summary: summarizeValidation(validation)
      }
    });
    activeCoreWorkflowId = repairWorkflow.id || activeCoreWorkflowId;
    runtimeState.setActiveWorkflow(repairWorkflow.summary);
    recordRuntimeOperation('repair', 'core', 'started', 'Repair workflow registered with Aegis Core.', {
      workflowId: activeCoreWorkflowId
    });
    startCoreWorkflowEventRefresh(target, activeCoreWorkflowId);
  } catch (error) {
    output && output.appendLine(`Aegis Core repair workflow creation skipped: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'repair');
  }

  for (let attempt = 1; attempt <= MAX_AGENT_REPAIR_ATTEMPTS; attempt += 1) {
    if (cancelToken && cancelToken.isCancellationRequested) {
      throw new vscode.CancellationError();
    }
    await writeAgentRecovery(target, {
      status: 'repairing',
      request,
      repairAttempts: attempt,
      validationSummary: summarizeValidation(validation)
    });
    updateAgentState({
      status: `Repair attempt ${attempt} of ${MAX_AGENT_REPAIR_ATTEMPTS}`,
      repairAttempts: attempt,
      validationOutput: summarizeValidation(validation)
    });

    const failure = {
      summary: summarizeValidation(validation),
      output: validation.output
    };
    snapshot = await getProjectSnapshot(target);
    const memoryContext = await readWorkspaceMemoryContext(target);
    const dependencyGraph = await readJsonMemoryFile(target, 'dependency-graph.json', null);
    const symbolIndex = await readJsonMemoryFile(target, 'symbol-index.json', null);
    const impactAnalysis = await buildImpactAnalysis(target, snapshot, request, dependencyGraph, symbolIndex, {
      validationText: validation.output
    });
    lastImpactAnalysis = impactAnalysis;
    const context = [
      await buildFocusedProjectContext(snapshot, request, {
        memoryContext,
        validationText: validation.output,
        dependencyGraph,
        symbolIndex,
        impactAnalysis
      }),
      `# Previous Proposal\n${proposalToPlanText(currentProposal)}`
    ].filter(Boolean).join('\n\n');
    const repairProposal = await createAgentProposal(target, request, context, attempt, failure, cancelToken);
    enrichProposalWithRepoIntelligence(repairProposal, impactAnalysis);
    attachDestinationReasoning(repairProposal, snapshot, target);
    currentProposal = repairProposal;
    lastProposal = repairProposal;
    await saveProposal(repairProposal);
    await writeAgentRecovery(target, {
      status: 'waiting-repair-approval',
      request,
      repairAttempts: attempt,
      summary: repairProposal.summary,
      files: repairProposal.fileEdits.map((edit) => edit.path)
    });
    await appendAgentHistory(target, {
      type: 'repair-proposal',
      request,
      attempt,
      summary: repairProposal.summary,
      files: repairProposal.fileEdits.map((edit) => edit.path)
    });

    updateAgentState({
      status: 'Waiting for repair approval',
      activePlan: proposalToPlanText(repairProposal),
      pendingDiffs: repairProposal.fileEdits.map((edit) => edit.path)
    });

    const result = await showProposalPreview(repairProposal, { allowApply: true, repairAttempt: attempt, staged: true });
    if (result !== 'applied') {
      updateAgentState({
        status: 'Repair paused',
        validationOutput: `Validation failed, and repair proposal was not applied.\n\n${summarizeValidation(validation)}`
      });
      await appendAgentHistory(target, {
        type: 'repair-not-applied',
        request,
        attempt,
        result
      });
      await writeAgentRecovery(target, {
        status: 'repair-paused',
        request,
        repairAttempts: attempt,
        result
      });
      return;
    }

    await writeAgentRecovery(target, { status: 'validating-repair', request, repairAttempts: attempt });
    validation = await runDetectedValidation(target, snapshot);
    await recordValidationResult(target, validation);
    await appendDecisionRecord(target, repairProposal, validation, validation.success ? 'Continue with the next roadmap item.' : 'Validation still fails; inspect output before another change.');
    await appendAgentHistory(target, {
      type: 'repair-validation',
      request,
      attempt,
      success: validation.success,
      commands: validation.commands.map((item) => item.command)
    });

    if (validation.success) {
      updateAgentState({
        status: 'Validation passed after repair',
        validationOutput: summarizeValidation(validation),
        activePlan: `${proposalToPlanText(repairProposal)}\n\nNext step: continue with the next small roadmap item.`
      });
      vscode.window.showInformationMessage(`Aegis repair attempt ${attempt} passed validation.`);
      await writeAgentRecovery(target, { status: 'completed', request, validation: 'passed-after-repair', repairAttempts: attempt });
      return;
    }
  }

  updateAgentState({
    status: 'Validation still failing',
    validationOutput: `${summarizeValidation(validation)}\n\nStopped after ${MAX_AGENT_REPAIR_ATTEMPTS} repair attempts.`
  });
  vscode.window.showWarningMessage(`Aegis stopped after ${MAX_AGENT_REPAIR_ATTEMPTS} repair attempts. Review validation output before continuing.`);
  await writeAgentRecovery(target, {
    status: 'stopped-after-repairs',
    request,
    repairAttempts: MAX_AGENT_REPAIR_ATTEMPTS,
    validationSummary: summarizeValidation(validation)
  });
}

async function runAutopilotOnce(objective, targetOrResource) {
  const config = getConfig();
  const target = isWorkspaceTarget(targetOrResource)
    ? targetOrResource
    : await resolveWorkspaceTarget(targetOrResource);
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before running autopilot.');
    return;
  }

  const task = objective && objective.trim()
    ? objective.trim()
    : 'Continue working on this project from the current folder. Use recent local proposals, TODOs, diagnostics, and project notes to choose one small, safe, high-value next step.';

  output.appendLine('');
  output.appendLine(`[${new Date().toLocaleString()}] Running local autopilot with ${config.chatModel}`);
  output.appendLine(`Target folder: ${target.root}`);
  output.appendLine(`Objective: ${task}`);
  output.show(true);
  panelProvider && panelProvider.post({ command: 'busy', text: `Running local autopilot in ${target.label}...` });

  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Aegis Local Autopilot',
        cancellable: true
      },
      async (progress, token) => {
        progress.report({ message: 'Gathering workspace context...' });
        const context = await collectWorkspaceContext(task, target);
        if (token.isCancellationRequested) {
          throw new vscode.CancellationError();
        }
        progress.report({ message: 'Calling local model...' });
        const prompt = buildAutopilotPrompt(task, context);
        const raw = await askOllamaWithFallback(config.chatModel, prompt, {
          temperature: 0.15,
          json: true,
          timeoutMs: 900000,
          cancellationToken: token
        });
        const proposal = parseProposal(raw, target, task);
        attachDestinationReasoning(proposal, await getProjectSnapshot(target, { fast: true }), target);
        lastProposal = proposal;
        await saveProposal(proposal);

        output.appendLine(`Proposal: ${proposal.summary || 'No summary returned.'}`);
        output.appendLine(`File edits: ${proposal.fileEdits.length}`);
        output.appendLine(`Suggested commands: ${proposal.commands.length}`);
        panelProvider && panelProvider.post({
          command: 'proposal',
          summary: proposal.summary || 'Proposal ready',
          proposal
        });

        const previewOptions = {};
        if (config.autopilotWriteMode === 'apply' && config.safetyMode !== 'review-only') {
          previewOptions.autoApplyIfUnblocked = true;
        }
        progress.report({ message: 'Opening proposal preview...' });
        await showProposalPreview(proposal, previewOptions);
      }
    );
  } catch (error) {
    if (error instanceof vscode.CancellationError || isCancellationError(error)) {
      output.appendLine('Local autopilot run cancelled.');
    } else {
      reportError(error);
    }
  } finally {
    panelProvider && panelProvider.post({ command: 'busy', text: '' });
    panelProvider && panelProvider.refresh();
  }
}

async function startAutopilot(resource) {
  if (autopilotTimer) {
    vscode.window.showInformationMessage('Aegis local autopilot is already running.');
    return;
  }

  autopilotTarget = await resolveWorkspaceTarget(resource);
  if (!autopilotTarget) {
    vscode.window.showWarningMessage('Open a project folder before starting autopilot.');
    return;
  }

  const minutes = Math.max(2, Number(getConfig().autopilotIntervalMinutes) || 15);
  autopilotTimer = setInterval(() => {
    runAutopilotOnce('', autopilotTarget).catch(reportError);
  }, minutes * 60 * 1000);

  vscode.window.showInformationMessage(`Aegis local autopilot started for ${autopilotTarget.label}. Interval: ${minutes} minutes.`);
  output.appendLine(`Autopilot loop started for ${autopilotTarget.root} with ${minutes} minute interval.`);
  panelProvider && panelProvider.refresh();
  await runAutopilotOnce('', autopilotTarget);
}

function stopAutopilot(showMessage = true) {
  if (autopilotTimer) {
    clearInterval(autopilotTimer);
    autopilotTimer = undefined;
    autopilotTarget = undefined;
    output && output.appendLine('Autopilot loop stopped.');
    panelProvider && panelProvider.refresh();
    if (showMessage) {
      vscode.window.showInformationMessage('Aegis local autopilot stopped.');
    }
  }
}

async function applyLastProposal() {
  if (!lastProposal) {
    vscode.window.showWarningMessage('No local proposal is available yet.');
    return;
  }
  await applyProposal(lastProposal);
}

async function previewLastProposal() {
  if (!lastProposal) {
    vscode.window.showWarningMessage('No local proposal is available yet.');
    return;
  }
  await showProposalPreview(lastProposal);
}

async function showProposalPreview(proposal, options = {}) {
  await openProposalDocument(proposal);
  panelProvider && panelProvider.post({
    command: 'proposal',
    summary: proposal.summary || 'Proposal ready',
    proposal
  });

  if (!proposal.fileEdits.length) {
    vscode.window.showInformationMessage('Aegis created a plan with no file edits. Review the proposal document for next steps.');
    return 'no-edits';
  }

  const validations = proposal.fileEdits.map((edit) => validateProposalEdit(proposal, edit));
  markDestinationSafetyFromValidations(proposal, validations);
  const blocked = validations.filter((item) => !item.ok);
  if (blocked.length) {
    output.appendLine('Blocked unsafe proposal edits:');
    blocked.forEach((item) => output.appendLine(`- ${item.edit.path}: ${item.reason}`));
    vscode.window.showWarningMessage(`Aegis blocked ${blocked.length} unsafe proposed edit(s): ${formatBlockedProposalEditSummary(blocked)}. Review the proposal document.`);
    return 'blocked';
  }

  await syncProposalWithCore(proposal, validations).catch((error) => {
    output && output.appendLine(`Aegis Core proposal sync unavailable; VS Code will keep local proposal state: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'proposal-sync');
  });

  if (options.staged && hasEditableStages(proposal)) {
    return await showStagedProposalPreview(proposal, validations, options);
  }

  await openProposalDiffs(proposal, validations);
  if (options.autoApplyIfUnblocked && getConfig().safetyMode !== 'review-only') {
    const applied = await applyProposal(proposal, { skipPrompt: true, userApproved: false });
    if (applied) {
      vscode.window.showInformationMessage('Aegis applied the proposal (Autopilot write mode: apply).');
    }
    return applied ? 'applied' : 'not-applied';
  }
  const answer = await vscode.window.showInformationMessage(
    options.repairAttempt
      ? `Aegis proposed repair ${options.repairAttempt} with ${proposal.fileEdits.length} file change(s). Review the diff before applying.`
      : `Aegis proposed ${proposal.fileEdits.length} file change(s). Review the diff before applying.`,
    'Apply Accepted Changes',
    'Open Diffs Again',
    'Reject'
  );
  if (answer === 'Apply Accepted Changes') {
    const applied = await applyProposal(proposal, { skipPrompt: true, userApproved: true });
    return applied ? 'applied' : 'not-applied';
  } else if (answer === 'Open Diffs Again') {
    await openProposalDiffs(proposal, validations);
    return 'previewed';
  } else if (answer === 'Reject') {
    vscode.window.showInformationMessage('Aegis proposal rejected. No files were changed.');
    return 'rejected';
  }
  return 'deferred';
}

function hasEditableStages(proposal) {
  return Array.isArray(proposal.stages) &&
    proposal.stages.filter((stage) => Array.isArray(stage.files) && stage.files.length).length > 1 &&
    Array.isArray(proposal.fileEdits) &&
    proposal.fileEdits.length > 1;
}

async function showStagedProposalPreview(proposal, validations, options = {}) {
  const stages = normalizeProposalStages(proposal, proposal.impactAnalysis);
  const allEdits = new Map((proposal.fileEdits || []).map((edit) => [edit.path.replace(/\\/g, '/'), edit]));
  let appliedAny = false;

  for (let index = 0; index < stages.length; index += 1) {
    const stage = stages[index];
    const stageFiles = new Set((stage.files || []).map((file) => file.replace(/\\/g, '/')));
    const stageEdits = (proposal.fileEdits || []).filter((edit) => stageFiles.has(edit.path.replace(/\\/g, '/')));
    if (!stageEdits.length) {
      continue;
    }

    const stageProposal = Object.assign({}, proposal, {
      summary: `${proposal.summary || 'Aegis staged proposal'}\n\nStage ${index + 1}: ${stage.name || stage.title || 'Stage'}`,
      fileEdits: stageEdits,
      stages: [stage]
    });
    const stageValidations = stageEdits
      .map((edit) => validations.find((item) => item.edit.path === edit.path) || validateProposalEdit(stageProposal, edit))
      .filter(Boolean);

    updateAgentState({
      status: `Waiting for Stage ${index + 1} approval`,
      activePlan: stageToPlanText(stage, index, stages.length, proposal),
      pendingDiffs: stageEdits.map((edit) => edit.path)
    });

    let decision = 'Open Diffs Again';
    while (decision === 'Open Diffs Again') {
      await openProposalDiffs(stageProposal, stageValidations);
      decision = await vscode.window.showInformationMessage(
        `Stage ${index + 1}/${stages.length}: ${stage.name || stage.title || 'Apply staged changes'} (${stageEdits.length} file change(s)).`,
        { modal: true },
        'Apply Stage',
        'Open Diffs Again',
        'Pause'
      );
    }

    if (decision !== 'Apply Stage') {
      updateAgentState({
        status: appliedAny ? 'Paused after staged apply' : 'Waiting',
        validationOutput: appliedAny
          ? 'Some staged changes were applied. Validation will run on the current workspace state.'
          : 'No staged changes were applied.'
      });
      return appliedAny ? 'applied' : 'deferred';
    }

    const applied = await applyProposal(stageProposal, {
      skipPrompt: true,
      userApproved: true,
      stageName: stage.name || stage.title || `Stage ${index + 1}`,
      stageIndex: index + 1
    });
    appliedAny = appliedAny || applied;

    for (const file of stageFiles) {
      allEdits.delete(file);
    }
  }

  if (allEdits.size) {
    const remainingProposal = Object.assign({}, proposal, {
      summary: `${proposal.summary || 'Aegis proposal'}\n\nUnstaged remaining edits`,
      fileEdits: Array.from(allEdits.values())
    });
    updateAgentState({
      status: 'Waiting for remaining edit approval',
      activePlan: `${proposal.summary || 'Aegis proposal'}\n\nRemaining unstaged edits:\n${remainingProposal.fileEdits.map((edit) => `- ${edit.path}`).join('\n')}`,
      pendingDiffs: remainingProposal.fileEdits.map((edit) => edit.path)
    });
    const answer = await vscode.window.showInformationMessage(
      `Apply ${remainingProposal.fileEdits.length} remaining unstaged change(s)?`,
      { modal: true },
      'Apply Remaining',
      'Pause'
    );
    if (answer === 'Apply Remaining') {
      const applied = await applyProposal(remainingProposal, { skipPrompt: true, userApproved: true, stageName: 'Remaining edits' });
      appliedAny = appliedAny || applied;
    }
  }

  return appliedAny ? 'applied' : 'no-edits';
}

async function openProposalDiffs(proposal, validations) {
  const stateRoot = proposal.workspaceRoot || proposal.workspace || proposal.targetRoot;
  const previewRoot = path.join(stateRoot, '.aegis', 'vscode-autopilot', 'previews', timestampForPath());
  const maxDiffTabs = Math.min(25, Math.max(1, Number(getConfig().maxProposalDiffTabs) || 12));
  const safeValidations = validations.filter((item) => item.ok).slice(0, maxDiffTabs);

  for (const item of safeValidations) {
    const originalPreview = path.join(previewRoot, 'original', item.relative);
    const proposedPreview = path.join(previewRoot, 'proposed', item.relative);
    await fs.mkdir(path.dirname(originalPreview), { recursive: true });
    await fs.mkdir(path.dirname(proposedPreview), { recursive: true });

    let existing = '';
    let leftUri = vscode.Uri.file(originalPreview);
    try {
      existing = await fs.readFile(item.target, 'utf8');
      leftUri = vscode.Uri.file(item.target);
    } catch (error) {
      if (error.code !== 'ENOENT') {
        throw error;
      }
      existing = '';
      await fs.writeFile(originalPreview, '', 'utf8');
    }

    if (leftUri.fsPath === originalPreview) {
      await fs.writeFile(originalPreview, existing, 'utf8');
    }
    await fs.writeFile(proposedPreview, item.edit.content, 'utf8');
    await vscode.commands.executeCommand(
      'vscode.diff',
      leftUri,
      vscode.Uri.file(proposedPreview),
      `Aegis Proposal: ${item.relative}`
    );
  }

  if (proposal.fileEdits.length > safeValidations.length) {
    vscode.window.showInformationMessage(`Opened first ${safeValidations.length} proposal diff(s). Remaining edits are in the JSON proposal.`);
  }
}

async function syncProposalWithCore(proposal, validations = []) {
  const root = coreWorkspaceRootForProposal(proposal);
  if (!root || !proposal || !Array.isArray(proposal.fileEdits) || !proposal.fileEdits.length) {
    runtimeState.setPendingProposal(proposal || null);
    return null;
  }
  if (proposal.coreProposalId) {
    runtimeState.setPendingProposal(proposal);
    return proposal.coreProposalId;
  }
  const validEdits = validations.length
    ? validations.filter((item) => item && item.ok).map((item) => item.edit)
    : proposal.fileEdits;
  if (!validEdits.length) {
    runtimeState.setPendingProposal(proposal);
    return null;
  }
  const envelope = await getCoreRuntimeClient().proposeChanges(root, validEdits.map((edit, index) => ({
    id: edit.id || `vscode-${index + 1}`,
    action: edit.action || inferCoreChangeAction(edit, root, coreRelativePathForEdit(proposal, edit)),
    path: coreRelativePathForEdit(proposal, edit),
    content: edit.content,
    summary: edit.reason || proposal.summary || '',
    selected: true
  })), {
    summary: proposal.summary || lastAgentRequest || 'VS Code proposal',
    sourceTaskId: activeCoreTaskId || null,
    risk: proposal.risk || 'unknown',
    repairAttempt: proposal.repairAttempt || null
  });
  const data = coreEnvelopeData(envelope);
  const proposalRecord = data.proposal || {};
  proposal.coreProposalId = proposalRecord.id || data.proposal_id || '';
  proposal.coreJobId = data.job_id || '';
  proposal.coreTaskId = data.task_id || '';
  proposal.coreProjectId = data.project_id || '';
  proposal.corePreview = Array.isArray(data.preview) ? data.preview : [];
  if (lastProposal === proposal) {
    await saveProposal(proposal).catch(() => {});
  }
  runtimeState.setPendingProposal(proposal);
  recordRuntimeOperation('proposal', 'core', 'stored', 'Proposal metadata stored in Aegis Core.', {
    jobId: proposal.coreJobId,
    workflowId: activeCoreWorkflowId || '',
    proposalId: proposal.coreProposalId
  });
  return proposal.coreProposalId;
}

function coreWorkspaceRootForProposal(proposal) {
  return proposal && (proposal.workspaceRoot || proposal.workspace || proposal.targetRoot) || '';
}

function coreRelativePathForEdit(proposal, edit) {
  const editPath = String(edit && edit.path || '').replace(/\\/g, '/');
  const workspaceRoot = proposal && proposal.workspaceRoot ? path.resolve(proposal.workspaceRoot) : '';
  const targetRoot = proposal && (proposal.workspace || proposal.targetRoot) ? path.resolve(proposal.workspace || proposal.targetRoot) : workspaceRoot;
  if (workspaceRoot && targetRoot && targetRoot !== workspaceRoot && isPathInside(workspaceRoot, targetRoot)) {
    return path.relative(workspaceRoot, path.join(targetRoot, editPath)).replace(/\\/g, '/');
  }
  return editPath;
}

function inferCoreChangeAction(edit, workspaceRoot, relativePath) {
  const explicit = String(edit && edit.action || '').toLowerCase();
  if (explicit === 'create' || explicit === 'update' || explicit === 'append' || explicit === 'delete') {
    return explicit;
  }
  const relative = relativePath || (edit && edit.path ? edit.path : '');
  const fullPath = resolveInside(workspaceRoot, relative);
  if (fullPath && !fsSync.existsSync(fullPath)) {
    return 'create';
  }
  return 'update';
}

function coreChangesForProposalEdits(proposal, edits, stateRoot) {
  return (Array.isArray(edits) ? edits : []).map((edit, index) => ({
    id: edit.id || `vscode-${index + 1}`,
    action: edit.action || inferCoreChangeAction(edit, stateRoot, coreRelativePathForEdit(proposal, edit)),
    path: coreRelativePathForEdit(proposal, edit),
    content: edit.content,
    summary: edit.reason || proposal.summary || '',
    selected: true
  }));
}

function qualityGateBlockedMessage(evaluation) {
  const blockers = evaluation && Array.isArray(evaluation.blockers) ? evaluation.blockers : [];
  const failedGates = evaluation && Array.isArray(evaluation.gates)
    ? evaluation.gates.filter((gate) => gate && gate.status === 'failed').map((gate) => gate.name || gate.id).filter(Boolean)
    : [];
  const details = blockers.length ? blockers : failedGates;
  return details.length ? details.slice(0, 5).join('; ') : (evaluation && evaluation.summary) || 'Core quality gate did not allow apply.';
}

async function evaluateProposalQualityWithCore(proposal, validEdits, options = {}) {
  const stateRoot = proposal.workspaceRoot || proposal.workspace || proposal.targetRoot;
  const changes = coreChangesForProposalEdits(proposal, validEdits, stateRoot);
  const evaluationEnvelope = await getCoreRuntimeClient().evaluateQualityGates(stateRoot, {
    workflowId: activeCoreWorkflowId || null,
    proposalId: proposal.coreProposalId || null,
    changes,
    approval: Boolean(options.userApproved),
    dryRun: true,
    persist: true,
    maxFilesChanged: 25,
    validationRequired: Boolean(options.validationRequired),
    metadata: {
      source: 'vscode-extension',
      stageName: options.stageName || '',
      stageIndex: options.stageIndex || null,
      summary: proposal.summary || ''
    }
  });
  const evaluation = coreEnvelopeData(evaluationEnvelope);
  runtimeState.setQualityGates({ data: { current_evaluation: evaluation } });
  const allowed = evaluationEnvelope.ok !== false && evaluation.apply_allowed !== false;
  recordRuntimeOperation('quality-gate', 'core', allowed ? 'passed' : 'blocked', evaluation.summary || qualityGateBlockedMessage(evaluation), {
    workflowId: activeCoreWorkflowId || '',
    proposalId: proposal.coreProposalId || '',
    jobId: evaluation.job_id || ''
  });
  if (!allowed) {
    throw new Error(`Quality gate blocked apply: ${qualityGateBlockedMessage(evaluation)}`);
  }
  return evaluation;
}

async function tryApplyProposalWithCore(proposal, validations, options = {}) {
  const root = proposal.workspace || proposal.targetRoot;
  const stateRoot = proposal.workspaceRoot || root;
  const validEdits = validations.map((item) => item.edit);
  if (!validEdits.length) {
    return false;
  }
  await syncProposalWithCore(proposal, validations);
  const coreChanges = coreChangesForProposalEdits(proposal, validEdits, stateRoot);
  await evaluateProposalQualityWithCore(proposal, validEdits, options);
  const applyEnvelope = await getCoreRuntimeClient().applyChanges(stateRoot, {
    proposalId: proposal.coreProposalId || null,
    changes: proposal.coreProposalId ? [] : coreChanges,
    paths: proposal.coreProposalId ? validEdits.map((edit) => coreRelativePathForEdit(proposal, edit)) : [],
    applyAll: !proposal.coreProposalId,
    dryRun: Boolean(options.dryRun),
    summary: options.stageName || proposal.summary || 'VS Code approved proposal',
    taskId: activeCoreTaskId || null,
    repairAttempt: proposal.repairAttempt || (options.repairAttempt ? { attempt: options.repairAttempt } : null),
    approval: Boolean(options.userApproved),
    qualityGateRequired: true,
    maxFilesChanged: 25
  });
  const applyData = coreEnvelopeData(applyEnvelope);
  const job = extractEditingJob(applyData);
  if (applyEnvelope.ok === false || applyData.ok === false) {
    const gate = applyData.quality_gate || {};
    runtimeState.setQualityGates({ data: { current_evaluation: gate } });
    throw new Error(`Aegis Core apply returned ok=false: ${(applyData.warnings || []).join('; ') || qualityGateBlockedMessage(gate) || 'no detail'}`);
  }
  const applied = Array.isArray(applyData.applied) ? applyData.applied : [];
  const checkpointId = applyData.checkpoint_id || job.checkpointId || '';
  const manifest = {
    version: 2,
    backupId: checkpointId || `core-${timestampForPath()}`,
    coreCheckpointId: checkpointId,
    coreProposalId: proposal.coreProposalId || '',
    coreJobId: job.jobId || applyData.job_id || '',
    coreTaskId: job.taskId || applyData.task_id || activeCoreTaskId || '',
    createdAt: new Date().toISOString(),
    workspaceRoot: stateRoot,
    targetRoot: root,
    summary: sanitizeMemoryText(proposal.summary || 'Aegis Core change'),
    stageName: options.stageName || '',
    stageIndex: options.stageIndex || null,
    files: validEdits.map((edit) => ({
      path: coreRelativePathForEdit(proposal, edit),
      workspaceRelativePath: coreRelativePathForEdit(proposal, edit),
      existed: true,
      backupPath: '',
      reason: sanitizeMemoryText(String(edit.reason || '')),
      restoredBy: 'aegis-core'
    }))
  };
  await recordChangeBackup({ workspaceRoot: stateRoot, root }, manifest);
  clearProjectSnapshotCache(root);
  updateAgentState({ pendingDiffs: [] });
  if (activeCoreTaskId) {
    await updateAegisCoreTaskStatus({ workspaceRoot: stateRoot, root }, activeCoreTaskId, 'completed', `Core applied ${validEdits.length} approved file change(s).`);
    activeCoreTaskId = '';
  }
  if (activeCoreWorkflowId) {
    await getWorkflowRuntimeClient().recordLog({ workspaceRoot: stateRoot, root }, activeCoreWorkflowId, 'VS Code approved changes were applied by Core.', {
      checkpoint_id: checkpointId,
      applied
    }).catch(() => {});
  }
  recordRuntimeOperation('apply', 'core', 'completed', `Core applied ${validEdits.length} approved file change(s).`, {
    jobId: job.jobId || applyData.job_id || '',
    checkpointId,
    workflowId: activeCoreWorkflowId || ''
  });
  runtimeState.setCheckpoints(checkpointId ? [{ id: checkpointId }] : []);
  await logExtensionEvent('apply', 'Aegis Core applied approved proposal.', {
    checkpointId,
    jobId: job.jobId || applyData.job_id || '',
    files: validEdits.map((edit) => edit.path)
  }, { workspaceRoot: stateRoot, root });
  vscode.window.showInformationMessage(checkpointId
    ? `Applied proposal through Aegis Core. Checkpoint: ${checkpointId}`
    : 'Applied proposal through Aegis Core.');
  panelProvider && panelProvider.refresh();
  return true;
}

function shouldFallbackFromCoreApply(error) {
  const message = String(error && error.message ? error.message : error || '').toLowerCase();
  return /econnrefused|timed out|timeout|fetch failed|connect|socket|core.*unavailable|http 404|http 405|not found/.test(message);
}

async function applyProposal(proposal, options = {}) {
  if (getConfig().safetyMode === 'review-only') {
    vscode.window.showWarningMessage('Safety mode is review-only. Proposal was not applied.');
    return false;
  }
  const root = proposal.workspace || proposal.targetRoot;
  if (!root) {
    vscode.window.showWarningMessage('Open a workspace before applying a proposal.');
    return false;
  }

  if (!proposal.fileEdits.length) {
    vscode.window.showInformationMessage('The last proposal has no file edits to apply.');
    return false;
  }

  const validations = proposal.fileEdits.map((edit) => validateProposalEdit(proposal, edit));
  const blocked = validations.filter((item) => !item.ok);
  if (blocked.length) {
    output.appendLine('Refusing to apply unsafe proposal edits:');
    blocked.forEach((item) => output.appendLine(`- ${item.edit.path}: ${item.reason}`));
    output.show(true);
    vscode.window.showErrorMessage(`Aegis refused to apply ${blocked.length} unsafe edit(s): ${formatBlockedProposalEditSummary(blocked)}. No files were changed.`);
    return false;
  }

  if (!options.skipPrompt) {
    const answer = await vscode.window.showWarningMessage(
      `Apply ${proposal.fileEdits.length} generated file edit(s)? A checkpoint backup will be created first.`,
      { modal: true },
      'Apply'
    );
    if (answer !== 'Apply') {
      return false;
    }
    options.userApproved = true;
  }

  try {
    const appliedByCore = await tryApplyProposalWithCore(proposal, validations, options);
    if (appliedByCore) {
      return true;
    }
  } catch (error) {
    if (!shouldFallbackFromCoreApply(error)) {
      output && output.appendLine(`Aegis Core refused to apply proposal; local fallback is disabled for this error: ${safeErrorMessage(error)}`);
      vscode.window.showErrorMessage(`Aegis Core refused to apply the proposal: ${safeErrorMessage(error)}`);
      return false;
    }
    output && output.appendLine(`Aegis Core apply unavailable; using VS Code local apply fallback: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'apply');
  }

  const stateRoot = proposal.workspaceRoot || root;
  const checkpointRoot = path.join(stateRoot, '.aegis', 'vscode-autopilot', 'checkpoints', timestampForPath());
  const backupId = timestampForPath();
  const backupRoot = path.join(stateRoot, '.aegis', 'backups', backupId);
  const backupFilesRoot = path.join(backupRoot, 'files');
  const manifest = {
    version: 1,
    backupId,
    createdAt: new Date().toISOString(),
    workspaceRoot: stateRoot,
    targetRoot: root,
    summary: sanitizeMemoryText(proposal.summary || 'Aegis agent change'),
    stageName: options.stageName || '',
    stageIndex: options.stageIndex || null,
    files: []
  };
  await fs.mkdir(checkpointRoot, { recursive: true });
  await fs.mkdir(backupFilesRoot, { recursive: true });
  await writeAgentRecovery({ workspaceRoot: stateRoot, root }, {
    status: 'applying',
    request: proposal.objective || lastAgentRequest || '',
    summary: proposal.summary,
    backupId,
    files: proposal.fileEdits.map((edit) => edit.path)
  });
  await logExtensionEvent('apply', 'Applying approved proposal.', {
    summary: proposal.summary || '',
    backupId,
    files: proposal.fileEdits.map((edit) => edit.path)
  }, { workspaceRoot: stateRoot, root });

  try {
    for (const item of validations) {
      const edit = item.edit;
      const target = item.target;
      const relative = item.relative;
      const backupRelative = isPathInside(stateRoot, target) ? path.relative(stateRoot, target) : relative;
      const backupPath = path.join(checkpointRoot, backupRelative);
      const aegisBackupPath = path.join(backupFilesRoot, backupRelative);
      await fs.mkdir(path.dirname(backupPath), { recursive: true });
      await fs.mkdir(path.dirname(aegisBackupPath), { recursive: true });
      const manifestFile = {
        path: relative,
        workspaceRelativePath: backupRelative.replace(/\\/g, '/'),
        existed: true,
        backupPath: path.relative(backupRoot, aegisBackupPath).replace(/\\/g, '/'),
        reason: sanitizeMemoryText(String(edit.reason || ''))
      };
      try {
        const existing = await fs.readFile(target);
        await fs.writeFile(backupPath, existing);
        await fs.writeFile(aegisBackupPath, existing);
      } catch (error) {
        if (error.code !== 'ENOENT') {
          throw error;
        }
        manifestFile.existed = false;
        manifestFile.backupPath = '';
        await fs.writeFile(`${backupPath}.missing`, 'File did not exist before this proposal.\n', 'utf8');
        await fs.writeFile(`${aegisBackupPath}.missing`, 'File did not exist before this proposal.\n', 'utf8');
      }

      await fs.mkdir(path.dirname(target), { recursive: true });
      manifest.files.push(manifestFile);
      await fs.writeFile(target, edit.content, 'utf8');
      await logExtensionEvent('file-write', `Applied ${relative}`, {
        backupId,
        stageName: options.stageName || '',
        reason: edit.reason || ''
      }, { workspaceRoot: stateRoot, root });
      output.appendLine(`Applied ${relative}`);
    }
  } catch (error) {
    await fs.writeFile(path.join(backupRoot, 'manifest.partial.json'), JSON.stringify(manifest, null, 2), 'utf8').catch(() => {});
    await restoreFromManifest(backupRoot, manifest, { workspaceRoot: stateRoot }).catch((restoreError) => {
      output.appendLine(`Aegis partial apply restore failed: ${safeErrorMessage(restoreError)}`);
    });
    await logExtensionEvent('apply-error', 'Apply failed; attempted to restore partial edits from backup.', {
      error: safeErrorMessage(error),
      backupId,
      restoredFiles: manifest.files.map((file) => file.workspaceRelativePath || file.path)
    }, { workspaceRoot: stateRoot, root });
    throw error;
  }

  await fs.writeFile(path.join(backupRoot, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
  await recordChangeBackup({ workspaceRoot: stateRoot, root }, manifest);
  clearProjectSnapshotCache(root);

  vscode.window.showInformationMessage(`Applied local proposal. Backup: ${backupRoot}`);
  recordRuntimeOperation('apply', 'local', 'completed', 'Applied with VS Code local fallback.', {
    checkpointId: backupId,
    workflowId: activeCoreWorkflowId || ''
  });
  updateAgentState({ pendingDiffs: [] });
  if (activeCoreTaskId) {
    await updateAegisCoreTaskStatus({ workspaceRoot: stateRoot, root }, activeCoreTaskId, 'completed', `Applied ${manifest.files.length} approved file change(s).`);
    activeCoreTaskId = '';
  }
  panelProvider && panelProvider.refresh();
  return true;
}

async function collectWorkspaceContext(objective, target) {
  const resolvedTarget = target || await resolveWorkspaceTarget();
  if (!resolvedTarget) {
    return 'No workspace folder is open.';
  }

  const snapshot = await getProjectSnapshot(resolvedTarget);
  const chunks = [await buildFocusedProjectContext(snapshot, objective)];

  const recentProposals = await readRecentProposalSummaries(resolvedTarget);
  if (recentProposals.length) {
    chunks.push(`# Recent Local Autopilot Proposals\n${recentProposals.join('\n')}`);
  }

  const editor = vscode.window.activeTextEditor;
  if (editor && editor.document.uri.scheme === 'file') {
    const rel = path.relative(resolvedTarget.root, editor.document.uri.fsPath);
    if (rel && isPathInside(resolvedTarget.root, editor.document.uri.fsPath)) {
      chunks.push(formatFileChunk(`ACTIVE:${rel}`, editor.document.getText()));
    }
  }

  const diagnostics = collectDiagnostics(resolvedTarget);
  if (diagnostics.length) {
    chunks.push(`# Diagnostics\n${diagnostics.join('\n')}`);
  }

  return truncateMiddle(chunks.join('\n\n'), getConfig().maxContextChars || MAX_CONTEXT_CHARS);
}

async function buildProjectSnapshot(target, options = {}) {
  const root = target.root;
  let coreScan = null;
  let coreScanWarning = '';
  if (!options.localOnly) {
    try {
      coreScan = await getAegisCoreWorkspaceScan(target);
    } catch (error) {
      coreScanWarning = safeErrorMessage(error);
      output && output.appendLine(`Aegis Core workspace scan unavailable; using VS Code local scan fallback: ${coreScanWarning}`);
      recordCoreDisconnected(error, 'workspace-scan');
    }
  }
  const entries = await scanProjectEntries(root, {
    maxFiles: options.fast ? 220 : MAX_PROJECT_SCAN_FILES,
    maxDepth: options.fast ? 4 : MAX_PROJECT_SCAN_DEPTH
  });
  const files = entries.filter((entry) => entry.type === 'file');
  const directories = entries.filter((entry) => entry.type === 'directory');
  const importantFiles = files
    .filter((entry) => isImportantWorkspaceFile(entry.relative))
    .slice(0, options.fast ? 20 : 60);
  const testFiles = files
    .filter((entry) => isLikelyTestFile(entry.relative))
    .slice(0, options.fast ? 20 : 80)
    .map((entry) => entry.relative);
  const configFiles = files
    .filter((entry) => isLikelyConfigFile(entry.relative))
    .slice(0, options.fast ? 20 : 80)
    .map((entry) => entry.relative);
  const entryPoints = detectEntryPoints(files);
  const recentFiles = files
    .filter((entry) => entry.mtimeMs)
    .sort((a, b) => b.mtimeMs - a.mtimeMs)
    .slice(0, options.fast ? 20 : 60)
    .map((entry) => ({
      path: entry.relative,
      modified: entry.modifiedAt,
      size: entry.size || 0
    }));
  const importantSlice = importantFiles.slice(0, options.fast ? 8 : 20);
  const importantContents = (
    await Promise.all(
      importantSlice.map(async (file) => {
        const text = await readWorkspaceFile(root, file.relative);
        if (!text) {
          return null;
        }
        return {
          path: file.relative,
          text: truncateMiddle(text, file.relative.toLowerCase().endsWith('package.json') ? 12000 : 6000)
        };
      })
    )
  )
    .filter(Boolean)
    .sort((a, b) => a.path.localeCompare(b.path));

  const topLevel = await readTopLevel(root);
  const fileTypes = countFileTypes(files);
  const languageInfo = inferProjectLanguages(files, importantContents);
  const commandInfo = inferProjectCommands(importantContents, files);
  const todoChunks = await collectTodoContext(Math.min(getConfig().maxContextFiles, options.fast ? 5 : 12), getConfig().excludeGlob, root);
  const diagnostics = collectDiagnostics(target);
  const coreData = coreScan ? coreEnvelopeData(coreScan) : null;
  const coreLanguageNames = coreData && coreData.languages && typeof coreData.languages === 'object'
    ? Object.keys(coreData.languages)
    : [];

  return {
    target,
    generatedAt: new Date().toISOString(),
    coreScan,
    coreScanWarning,
    files,
    directories,
    fileCount: coreData && Number.isFinite(Number(coreData.file_count)) ? Number(coreData.file_count) : files.length,
    directoryCount: directories.length,
    topLevel,
    fileTypes,
    importantFiles: mergeUniqueStrings(
      importantFiles.map((file) => file.relative),
      coreData ? [].concat(coreData.build_files || [], coreData.readmes || []) : []
    ),
    testFiles: mergeUniqueStrings(testFiles, coreData ? coreData.test_files || [] : []),
    configFiles,
    entryPoints: mergeUniqueStrings(entryPoints, coreData ? coreData.entry_points || [] : []),
    recentFiles: mergeRecentFiles(recentFiles, coreData ? coreData.recent_files || [] : []),
    importantContents,
    languages: mergeUniqueStrings(languageInfo.languages, coreLanguageNames),
    frameworks: mergeUniqueStrings(languageInfo.frameworks, coreData ? coreData.frameworks || [] : []),
    packageManagers: languageInfo.packageManagers,
    commands: commandInfo,
    todoChunks: mergeUniqueStrings(todoChunks, coreTodoChunks(coreData)),
    diagnostics
  };
}

async function getProjectSnapshot(target, options = {}) {
  const root = path.resolve(target.root);
  const mode = options.fast ? 'fast' : 'full';
  const key = `${root}|${mode}`;
  const cached = snapshotCache.get(key);
  if (cached && Date.now() - cached.at < SNAPSHOT_CACHE_TTL_MS) {
    return cached.snapshot;
  }
  const snapshot = await buildProjectSnapshot(target, options);
  snapshotCache.set(key, { at: Date.now(), snapshot });
  return snapshot;
}

function mergeUniqueStrings(...groups) {
  const seen = new Set();
  const merged = [];
  for (const group of groups) {
    if (!Array.isArray(group)) {
      continue;
    }
    for (const value of group) {
      const text = String(value || '').trim();
      const key = text.toLowerCase();
      if (text && !seen.has(key)) {
        seen.add(key);
        merged.push(text);
      }
    }
  }
  return merged;
}

function mergeRecentFiles(localRecent, coreRecent) {
  const normalizedCore = Array.isArray(coreRecent)
    ? coreRecent.map((value) => ({
        path: String(value || ''),
        modified: '',
        size: 0
      }))
    : [];
  const byPath = new Map();
  for (const item of [...(localRecent || []), ...normalizedCore]) {
    const key = String(item.path || '').replace(/\\/g, '/').toLowerCase();
    if (key && !byPath.has(key)) {
      byPath.set(key, item);
    }
  }
  return Array.from(byPath.values()).slice(0, 80);
}

function coreTodoChunks(coreData) {
  const todos = coreData && Array.isArray(coreData.todo_comments) ? coreData.todo_comments : [];
  return todos
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const file = String(item.file || item.path || '');
      const line = item.line ? `:${item.line}` : '';
      const text = String(item.text || '').trim();
      return file && text ? `${file}${line} ${text}` : text;
    })
    .filter(Boolean);
}

function clearProjectSnapshotCache(root) {
  if (!root) {
    snapshotCache.clear();
    return;
  }
  const resolved = path.resolve(root).toLowerCase();
  for (const key of Array.from(snapshotCache.keys())) {
    if (key.toLowerCase().startsWith(resolved)) {
      snapshotCache.delete(key);
    }
  }
}

async function scanProjectEntries(root, options) {
  const results = [];
  const queue = [{ dir: root, depth: 0 }];
  let fileCount = 0;

  while (queue.length && fileCount < options.maxFiles) {
    const current = queue.shift();
    let children;
    try {
      children = await fs.readdir(current.dir, { withFileTypes: true });
    } catch (error) {
      continue;
    }

    children.sort((a, b) => a.name.localeCompare(b.name));
    for (const child of children) {
      const full = path.join(current.dir, child.name);
      const relative = path.relative(root, full);
      if (!relative || isBlockedRelativePath(relative)) {
        continue;
      }
      if (child.isDirectory()) {
        results.push({ type: 'directory', relative });
        if (current.depth + 1 <= options.maxDepth) {
          queue.push({ dir: full, depth: current.depth + 1 });
        }
      } else if (child.isFile()) {
        let size = 0;
        let mtimeMs = 0;
        let modifiedAt = '';
        try {
          const stat = await fs.stat(full);
          size = stat.size;
          mtimeMs = stat.mtimeMs;
          modifiedAt = stat.mtime.toISOString();
        } catch (error) {
          // Metadata is useful but not required for indexing.
        }
        results.push({ type: 'file', relative, size, mtimeMs, modifiedAt });
        fileCount += 1;
        if (fileCount >= options.maxFiles) {
          break;
        }
      }
    }
  }

  return results;
}

async function readTopLevel(root) {
  try {
    const children = await fs.readdir(root, { withFileTypes: true });
    return children
      .filter((child) => !isBlockedRelativePath(child.name))
      .sort((a, b) => a.name.localeCompare(b.name))
      .slice(0, 80)
      .map((child) => `${child.isDirectory() ? '[dir]' : '[file]'} ${child.name}`);
  } catch (error) {
    return [];
  }
}

function countFileTypes(files) {
  return _projectScannerModule.countFileTypes(files);
}

function isLikelyTestFile(relativePath) {
  return _projectScannerModule.isLikelyTestFile(relativePath);
}

function isLikelyConfigFile(relativePath) {
  return _projectScannerModule.isLikelyConfigFile(relativePath);
}

function isUnityImportantFile(relativePath) {
  return _projectScannerModule.isUnityImportantFile(relativePath);
}

function isImportantWorkspaceFile(relativePath) {
  return _projectScannerModule.isImportantWorkspaceFile(relativePath);
}

function detectEntryPoints(files) {
  return _projectScannerModule.detectEntryPoints(files);
}

function inferProjectLanguages(files, importantContents) {
  return _projectScannerModule.inferProjectLanguages(files, importantContents);
}

function inferProjectCommands(importantContents, files) {
  return _projectScannerModule.inferProjectCommands(importantContents, files);
}

function projectSnapshotSummary(snapshot) {
  const parts = [
    `Folder: ${snapshot.target.label}`,
    `Files scanned: ${snapshot.fileCount}`,
    `Languages: ${snapshot.languages.length ? snapshot.languages.join(', ') : 'unknown'}`,
    `Frameworks: ${snapshot.frameworks.length ? snapshot.frameworks.join(', ') : 'unknown'}`
  ];
  if (snapshot.commands.length) {
    parts.push(`Commands: ${snapshot.commands.slice(0, 4).join(', ')}`);
  }
  return parts.join('\n');
}

function projectSnapshotToContext(snapshot, objective) {
  const chunks = [];
  chunks.push(`# Workspace Write Root\n${snapshot.target.root}`);
  chunks.push(`# Workspace Root\n${snapshot.target.workspaceRoot || snapshot.target.root}`);
  if (snapshot.target.focusRelative || snapshot.target.focusFileRelative) {
    chunks.push([
      '# Selected Explorer Context',
      `Type: ${snapshot.target.focusKind || 'folder'}`,
      `Path: ${snapshot.target.focusPath || snapshot.target.root}`,
      snapshot.target.focusRelative ? `Folder relative to workspace: ${snapshot.target.focusRelative}` : '',
      snapshot.target.focusFileRelative ? `File relative to workspace: ${snapshot.target.focusFileRelative}` : '',
      'Use the selected folder or file as a context hint, not as a forced output directory.',
      'Place new files where they best fit the existing project structure: package root for project config, src/app folders for source, components folders for components, pages/routes folders for routes, and nearby tests for tests.'
    ].filter(Boolean).join('\n'));
  }
  chunks.push(`# Objective\n${objective}`);
  chunks.push('Generated file edit paths must be relative to the workspace write root, not absolute paths. Do not blindly place every new file in the selected folder.');
  chunks.push(`# Project Summary\n${projectSnapshotSummary(snapshot)}`);
  if (snapshot.coreScan && coreEnvelopeData(snapshot.coreScan).cache_hit !== undefined) {
    chunks.push(`# Aegis Core Workspace Scan\nContract: ${formatCoreContract(snapshot.coreScan)}\nCache hit: ${Boolean(coreEnvelopeData(snapshot.coreScan).cache_hit)}`);
  } else if (snapshot.coreScanWarning) {
    chunks.push(`# Aegis Core Workspace Scan\nUnavailable; VS Code local scan fallback used. ${sanitizeMemoryText(snapshot.coreScanWarning)}`);
  }
  if (snapshot.topLevel.length) {
    chunks.push(`# Top-Level Structure\n${snapshot.topLevel.join('\n')}`);
  }
  if (snapshot.fileTypes.length) {
    chunks.push(`# File Types\n${snapshot.fileTypes.join('\n')}`);
  }
  if (snapshot.importantFiles.length) {
    chunks.push(`# Important Files Found\n${snapshot.importantFiles.join('\n')}`);
  }
  if (snapshot.entryPoints && snapshot.entryPoints.length) {
    chunks.push(`# Likely Entry Points\n${snapshot.entryPoints.join('\n')}`);
  }
  if (snapshot.testFiles && snapshot.testFiles.length) {
    chunks.push(`# Test Files\n${snapshot.testFiles.slice(0, 30).join('\n')}`);
  }
  if (snapshot.configFiles && snapshot.configFiles.length) {
    chunks.push(`# Config Files\n${snapshot.configFiles.slice(0, 30).join('\n')}`);
  }
  if (snapshot.recentFiles && snapshot.recentFiles.length) {
    chunks.push(`# Recently Modified Files\n${snapshot.recentFiles.slice(0, 20).map((item) => `${item.modified} ${item.path}`).join('\n')}`);
  }
  if (snapshot.commands.length) {
    chunks.push(`# Likely Commands\n${snapshot.commands.join('\n')}`);
  }
  if (snapshot.diagnostics.length) {
    chunks.push(`# Current VS Code Diagnostics\n${snapshot.diagnostics.join('\n')}`);
  }
  if (snapshot.todoChunks.length) {
    chunks.push(`# TODO/FIXME Snippets\n${snapshot.todoChunks.join('\n\n')}`);
  }
  for (const item of snapshot.importantContents) {
    if (chunks.join('\n').length > (getConfig().maxContextChars || MAX_CONTEXT_CHARS)) {
      break;
    }
    chunks.push(formatFileChunk(item.path, item.text));
  }
  return truncateMiddle(chunks.join('\n\n'), getConfig().maxContextChars || MAX_CONTEXT_CHARS);
}

async function buildFocusedProjectContext(snapshot, objective, options = {}) {
  const chunks = [projectSnapshotToContext(Object.assign({}, snapshot, { importantContents: [] }), objective)];
  const dependencyGraph = options.dependencyGraph || await readJsonMemoryFile(snapshot.target, 'dependency-graph.json', null);
  const symbolIndex = options.symbolIndex || await readJsonMemoryFile(snapshot.target, 'symbol-index.json', null);
  const memoryContext = options.memoryContext === undefined && options.includeMemory !== false
    ? await readWorkspaceMemoryContext(snapshot.target)
    : options.memoryContext;
  if (memoryContext) {
    chunks.push(`# Workspace Memory\n${memoryContext}`);
  }
  if (options.validationText) {
    chunks.push(`# Recent Validation Output\n${truncateMiddle(sanitizeMemoryText(options.validationText), 16000)}`);
  }
  if (options.impactAnalysis) {
    chunks.push(formatImpactAnalysisContext(options.impactAnalysis));
  }

  let selectedFiles = selectRelevantFiles(snapshot, objective, {
    validationText: options.validationText || '',
    maxFiles: options.maxFiles || 14,
    dependencyGraph,
    symbolIndex
  });
  selectedFiles = expandSelectedFilesWithGraph(dependencyGraph, selectedFiles, options.maxFiles || 14);
  selectedFiles = await expandSelectedFilesWithImports(snapshot, selectedFiles, options.maxFiles || 14);
  if (selectedFiles.length) {
    chunks.push(`# Selected Context Files\n${selectedFiles.join('\n')}`);
    setContextFiles(selectedFiles, 'Selected from active file, request terms, imports, tests, diagnostics, and project memory.');
    pushProgress('Reading focused context', `Reading ${selectedFiles.length} relevant file(s), not the whole repository.`);
  }
  if (dependencyGraph) {
    chunks.push(formatDependencyGraphContext(dependencyGraph, selectedFiles));
  }
  if (symbolIndex) {
    chunks.push(formatSymbolIndexContext(symbolIndex, selectedFiles));
  }
  for (const rel of selectedFiles) {
    if (chunks.join('\n').length > (getConfig().maxContextChars || MAX_CONTEXT_CHARS)) {
      break;
    }
    const text = await readWorkspaceFile(snapshot.target.root, rel);
    if (text) {
      chunks.push(formatFileChunk(rel, text));
    }
  }
  return truncateMiddle(chunks.join('\n\n'), getConfig().maxContextChars || MAX_CONTEXT_CHARS);
}

async function expandSelectedFilesWithImports(snapshot, selectedFiles, maxFiles) {
  const selected = new Set(selectedFiles);
  const fileSet = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/')));
  for (const rel of selectedFiles.slice(0, 6)) {
    const text = await readWorkspaceFile(snapshot.target.root, rel);
    const dir = path.dirname(rel).replace(/\\/g, '/');
    for (const imported of extractImportSpecifiers(text)) {
      if (!imported.startsWith('.')) {
        continue;
      }
      const base = path.posix.normalize(path.posix.join(dir === '.' ? '' : dir, imported));
      for (const candidate of importCandidatePaths(base)) {
        if (fileSet.has(candidate)) {
          selected.add(candidate);
          break;
        }
      }
      if (selected.size >= maxFiles) {
        return Array.from(selected).slice(0, maxFiles);
      }
    }
  }
  return Array.from(selected).slice(0, maxFiles);
}

function extractImportSpecifiers(text) {
  return _contextDiscoveryModule.extractImportSpecifiers(text);
}

function importCandidatePaths(base) {
  return _contextDiscoveryModule.importCandidatePaths(base);
}

function selectRelevantFiles(snapshot, request, options = {}) {
  const activeEditor = vscode.window.activeTextEditor;
  const activeEditorPath = activeEditor && activeEditor.document.uri.scheme === 'file' ? activeEditor.document.uri.fsPath : undefined;

  return _contextDiscoveryModule.selectRelevantFiles(snapshot, request, Object.assign({}, options, {
    activeEditorPath,
    isBlockedPath: (p) => _pathSafeModule.isBlockedRelativePath(p),
    isPathInside: (root, candidate) => _pathSafeModule.isPathInside(root, candidate),
    isLikelyTestFile: (p) => _projectScannerModule.isLikelyTestFile(p)
  }));
}

function extractFileHintsFromText(text, snapshot) {
  return _contextDiscoveryModule.extractFileHintsFromText(text, snapshot);
}

function expandSelectedFilesWithGraph(graph, selectedFiles, maxFiles) {
  return _contextDiscoveryModule.expandSelectedFilesWithGraph(graph, selectedFiles, maxFiles);
}

function inferDependencyLinks(snapshot, seedFiles) {
  return _contextDiscoveryModule.inferDependencyLinks(snapshot, seedFiles);
}

async function collectTodoContext(maxFiles, excludeGlob, root) {
  const files = await vscode.workspace.findFiles('**/*.{md,txt,js,jsx,ts,tsx,py,cpp,h,hpp,cs,json,ps1}', excludeGlob, Math.max(20, maxFiles * 5));
  const chunks = [];

  for (const uri of files) {
    if (root && !isPathInside(root, uri.fsPath)) {
      continue;
    }
    try {
      const bytes = await vscode.workspace.fs.readFile(uri);
      const text = Buffer.from(bytes).toString('utf8');
      const lines = text.split(/\r?\n/);
      const hits = [];
      for (let i = 0; i < lines.length; i += 1) {
        if (/\b(TODO|FIXME|HACK|NEXT|ROADMAP)\b/i.test(lines[i])) {
          hits.push(`${i + 1}: ${lines[i].trim()}`);
        }
        if (hits.length >= 8) {
          break;
        }
      }
      if (hits.length) {
        const rel = root ? path.relative(root, uri.fsPath) : vscode.workspace.asRelativePath(uri, false);
        chunks.push(`## ${rel}\n${hits.join('\n')}`);
        if (chunks.length >= maxFiles) {
          break;
        }
      }
    } catch (error) {
      output.appendLine(`Skipped TODO scan for ${uri.fsPath}: ${safeErrorMessage(error)}`);
    }
  }

  return chunks;
}

function collectDiagnostics(target) {
  const root = target.root;
  const rows = [];
  for (const [uri, diagnostics] of vscode.languages.getDiagnostics()) {
    if (uri.scheme !== 'file' || !isPathInside(root, uri.fsPath)) {
      continue;
    }
    const rel = path.relative(root, uri.fsPath);
    for (const diagnostic of diagnostics.slice(0, 5)) {
      const line = diagnostic.range.start.line + 1;
      rows.push(`- ${rel}:${line}: ${diagnostic.message}`);
      if (rows.length >= 30) {
        return rows;
      }
    }
  }
  return rows;
}

function buildAutopilotPrompt(objective, context) {
  return [
    'You are Aegis Local Autopilot, a local coding agent running inside VS Code.',
    'Use only the currently opened workspace context. Pick a small safe improvement if the objective is broad.',
    'First reason about project structure, language/framework, README/TODO/build files, diagnostics, and likely next steps.',
    'Prefer maintainable edits that match the current project direction. Never rewrite the whole project.',
    'Prefer the smallest useful change. Avoid broad refactors, new frameworks, clever abstractions, or touching files unrelated to the request.',
    'If the existing architecture is unclear, return a plan or questions with no file edits instead of guessing.',
    'Return concrete fileEdits for requested implementation work. Aegis previews and applies those edits after approval, so do not tell the user to create, paste, or save files manually.',
    'A selected folder or file is a focus hint for context, not a mandatory output directory. Place each generated file where it best fits the existing project structure.',
    'Do not invent files unless they are clearly useful. Do not include binary files, secrets, env files, build output, vendor folders, or dependencies.',
    'When the user asks to create, scaffold, or set up a new project or feature, include every necessary small text file as complete fileEdits instead of tutorial instructions. Keep the result minimal and runnable.',
    'Return strict JSON only. No Markdown fence.',
    '',
    'Schema:',
    '{',
    '  "summary": "short summary",',
    '  "risk": "low|medium|high",',
    '  "confidenceScore": 0.0,',
    '  "approachRationale": "why this approach fits the existing project",',
    '  "notes": ["important notes"],',
    '  "fileEdits": [',
    '    { "path": "relative/target-folder/path", "reason": "why this edit helps", "content": "complete replacement file content" }',
    '  ],',
    '  "commands": [',
    '    { "command": "validation command to run manually", "reason": "why" }',
    '  ],',
    '  "tests": ["test or verification notes"],',
    '  "impactAnalysis": {',
    '    "likelyAffectedFiles": ["relative/path"],',
    '    "riskLevel": "low|medium|high",',
    '    "relatedValidation": ["safe command"],',
    '    "possibleBreakingPoints": ["what might break"],',
    '    "rollbackPlan": "how to recover using Aegis backups"',
    '  },',
    '  "stages": [',
    '    { "name": "Stage 1: architecture/prep", "goal": "what this stage does", "files": ["relative/path"], "risk": "low|medium|high", "approvalRequired": true },',
    '    { "name": "Stage 2: implementation", "goal": "what this stage does", "files": ["relative/path"], "risk": "low|medium|high", "approvalRequired": true },',
    '    { "name": "Stage 3: tests/validation", "goal": "what this stage does", "files": ["relative/path"], "risk": "low|medium|high", "approvalRequired": true },',
    '    { "name": "Stage 4: cleanup/docs", "goal": "what this stage does", "files": ["relative/path"], "risk": "low|medium|high", "approvalRequired": true }',
    '  ]',
    '}',
    '',
    'Paths in fileEdits must be relative to the workspace write root shown in the context.',
    'Keep fileEdits small and focused. A safe development plan with no edits is better than broad speculative rewrites.',
    'For broad requests, propose at most 1-3 files in the first step unless the user explicitly asks for a larger staged change.',
    'Only edit files included in the selected context or directly connected by imports/tests. For empty or new-project requests, create the minimal new files needed and explain why in reason.',
    'For selected-folder work, use existing conventions before the selected path: package.json belongs at the package root, app entry points belong in src/app roots, components belong in components folders, and tests belong near the code under test.',
    'Each file edit reason must say why that file is being changed and why the change is minimal.',
    'For multi-file work, divide proposed edits into staged approvals. Every stage must be independently reviewable.',
    'When editing code, identify related tests and include test updates or test recommendations.',
    'For explicit implementation, create, scaffold, or fix requests, prefer complete fileEdits over notes whenever the change is safe and reasonably small.',
    'If no safe edit is obvious, return notes and commands with an empty fileEdits array.',
    '',
    `Objective:\n${objective}`,
    '',
    `Workspace context:\n${context}`
  ].join('\n');
}

function parseProposal(raw, target, objective) {
  return _proposalParserModule.parseProposal(raw, target, objective);
}

function attachDestinationReasoning(proposal, snapshot, target) {
  if (!proposal || !Array.isArray(proposal.fileEdits)) {
    return proposal;
  }
  try {
    proposal.destinationReasoning = buildDestinationReasoning(proposal, snapshot || {}, target || {});
  } catch (error) {
    output && output.appendLine(`Destination reasoning unavailable: ${safeErrorMessage(error)}`);
    proposal.destinationReasoning = [];
  }
  return proposal;
}

function markDestinationSafetyFromValidations(proposal, validations) {
  if (!proposal || !Array.isArray(proposal.destinationReasoning) || !Array.isArray(validations)) {
    return proposal;
  }
  const byPath = new Map(validations.map((item) => [
    item && item.edit && typeof item.edit.path === 'string' ? item.edit.path.replace(/\\/g, '/').replace(/^\/+/, '') : '',
    item
  ]));
  proposal.destinationReasoning = proposal.destinationReasoning.map((entry) => {
    const validation = byPath.get(entry.path);
    if (!validation) {
      return entry;
    }
    const safety = Object.assign({}, entry.safety || {});
    safety.rejected = !validation.ok;
    safety.status = validation.ok
      ? (safety.status || 'accepted')
      : `rejected: ${validation.reason || 'blocked by safety rules'}`;
    return Object.assign({}, entry, { safety });
  });
  return proposal;
}

function looksLikeWorkspaceChangeRequest(text) {
  const normalized = String(text || '').trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  if (/^(how|what|why|where|when|which|explain|describe|tell me|show me)\b/.test(normalized)) {
    return false;
  }
  if (/\b(do not|don't|without changing|no changes|just explain|only explain|question only)\b/.test(normalized)) {
    return false;
  }
  const changeVerb = /\b(create|build|make|implement|add|generate|scaffold|set up|setup|write|fix|change|update|refactor|convert|remove|rename|wire|hook up)\b/;
  const workspaceNoun = /\b(project|app|application|file|files|component|page|screen|feature|test|tests|code|script|function|class|endpoint|api|route|website|game|extension|plugin|workspace|build|error|bug|issue|failure)\b/;
  return changeVerb.test(normalized) && (workspaceNoun.test(normalized) || /^(create|build|make|scaffold|generate)\b/.test(normalized));
}

function proposalObjectFromInstructionalCodeBlocks(raw, objective) {
  const blocks = extractFencedCodeBlocks(raw);
  if (!blocks.length || !shouldInferFileEditsFromCodeBlocks(raw, objective, blocks)) {
    return null;
  }

  const usedPaths = new Set();
  const fileEdits = [];
  for (const block of blocks) {
    const inferredPath = inferCodeBlockPath(raw, block, objective, usedPaths, blocks.length);
    if (!inferredPath) {
      continue;
    }
    usedPaths.add(inferredPath.toLowerCase());
    fileEdits.push({
      path: inferredPath,
      reason: 'Converted generated code into an Aegis file edit so the extension can create the file after approval.',
      content: normalizeLineEndings(block.content.replace(/\s+$/, '')) + '\n'
    });
  }

  if (!fileEdits.length) {
    return null;
  }

  return {
    summary: `Create ${fileEdits.length} generated file${fileEdits.length === 1 ? '' : 's'} for the requested workspace change.`,
    risk: fileEdits.length > 4 ? 'medium' : 'low',
    confidenceScore: 0.62,
    approachRationale: 'The local model returned instructional code blocks. Aegis converted safe file-looking blocks into proposal edits instead of asking the user to paste files manually.',
    notes: [
      'Fallback parser used because the model response did not provide strict proposal JSON with fileEdits.',
      'Review the diff before applying; inferred file paths come from nearby filename hints or language-based defaults.'
    ],
    fileEdits,
    commands: extractCommandRecommendationsFromCodeBlocks(blocks),
    tests: ['Review generated files, apply the proposal, then run the detected validation command or project start command.'],
    impactAnalysis: {
      likelyAffectedFiles: fileEdits.map((edit) => edit.path),
      riskLevel: fileEdits.length > 4 ? 'medium' : 'low',
      relatedValidation: [],
      possibleBreakingPoints: ['Inferred filenames may need adjustment if the model did not label each code block.'],
      rollbackPlan: 'Use the Aegis checkpoint backup created before applying the proposal.'
    },
    stages: [{
      name: 'Stage 1: generated project files',
      goal: 'Create the requested files from the generated implementation.',
      files: fileEdits.map((edit) => edit.path),
      risk: fileEdits.length > 4 ? 'medium' : 'low',
      approvalRequired: true
    }]
  };
}

function shouldInferFileEditsFromCodeBlocks(raw, objective, blocks) {
  if (!blocks.some((block) => !isShellLanguage(block.language))) {
    return false;
  }
  if (looksLikeWorkspaceChangeRequest(objective)) {
    return true;
  }
  return /(?:create|save|copy|paste|put|place).*?(?:file|folder|project|app)|(?:filename|path|save as)/i.test(String(raw || ''));
}

function extractFencedCodeBlocks(raw) {
  const blocks = [];
  const pattern = /```([^\n`]*)\n([\s\S]*?)```/g;
  let match;
  while ((match = pattern.exec(String(raw || ''))) !== null) {
    const info = String(match[1] || '').trim();
    const content = String(match[2] || '');
    if (!content.trim()) {
      continue;
    }
    blocks.push({
      info,
      language: normalizeFenceLanguage(info),
      content,
      start: match.index,
      end: pattern.lastIndex
    });
  }
  return blocks;
}

function normalizeFenceLanguage(info) {
  const first = String(info || '').trim().split(/\s+/)[0].toLowerCase();
  const aliases = {
    javascript: 'js',
    typescript: 'ts',
    html5: 'html',
    shell: 'sh',
    bash: 'sh',
    powershell: 'ps1',
    text: ''
  };
  return aliases[first] === undefined ? first : aliases[first];
}

function inferCodeBlockPath(raw, block, objective, usedPaths, blockCount) {
  const fromFence = extractFilePathHint(block.info);
  if (fromFence && !usedPaths.has(fromFence.toLowerCase())) {
    return fromFence;
  }

  const before = String(raw || '').slice(Math.max(0, block.start - 700), block.start);
  const fromContext = extractFilePathHint(before);
  if (fromContext && !usedPaths.has(fromContext.toLowerCase())) {
    return fromContext;
  }

  if (isShellLanguage(block.language)) {
    return '';
  }
  const fallback = filePathFromLanguageAndContent(block.language, block.content, objective, usedPaths, blockCount);
  return fallback || '';
}

function extractFilePathHint(text) {
  const lines = String(text || '').split(/\r?\n/).slice(-10).reverse();
  for (const line of lines) {
    const candidates = collectFilePathCandidates(line);
    for (const candidate of candidates) {
      const normalized = normalizePotentialGeneratedPath(candidate);
      if (normalized) {
        return normalized;
      }
    }
  }
  return '';
}

function collectFilePathCandidates(line) {
  const candidates = [];
  const extensionPattern = '(?:html|css|scss|sass|less|js|jsx|ts|tsx|mjs|cjs|json|jsonc|md|txt|py|cs|java|go|rs|toml|yaml|yml|xml|xaml|sln|slnx|csproj|fsproj|vbproj|props|targets|ps1|sh|bat|cmd|sql|svg)';
  const patterns = [
    new RegExp('[`"\']([^`"\']+\\.' + extensionPattern + ')[`"\']', 'gi'),
    new RegExp('(?:file|path|filename|save as|create(?: file)?|add|update|write|in)\\s*:?\\s*([A-Za-z0-9_.@/\\\\-]+\\.' + extensionPattern + ')', 'gi'),
    new RegExp('(?:^|\\s)([A-Za-z0-9_.@/\\\\-]+\\.' + extensionPattern + ')(?=\\s|$|:)', 'gi')
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(line)) !== null) {
      candidates.push(match[1]);
    }
  }
  return candidates;
}

function normalizePotentialGeneratedPath(value) {
  let cleaned = String(value || '').trim();
  cleaned = cleaned.replace(/^[`'"\s]+|[`'"\s,.;:]+$/g, '').replace(/[)\]]+$/g, '');
  cleaned = cleaned.replace(/\\/g, '/');
  if (!cleaned || /^[A-Za-z]:\//.test(cleaned) || cleaned.startsWith('~') || cleaned.includes('://')) {
    return '';
  }
  cleaned = cleaned.replace(/^\.?\//, '').replace(/^\/+/, '');
  if (!pathLooksLikeFile(cleaned)) {
    return '';
  }
  const segments = cleaned.split('/').filter(Boolean);
  if (!segments.length || segments.some((segment) => segment === '.' || segment === '..' || /\s/.test(segment))) {
    return '';
  }
  if (isBlockedRelativePath(cleaned)) {
    return '';
  }
  return cleaned;
}

function pathLooksLikeFile(relativePath) {
  const normalized = String(relativePath || '').replace(/\\/g, '/');
  if (!normalized || normalized.length > 180 || normalized.endsWith('/')) {
    return false;
  }
  const basename = path.posix.basename(normalized);
  return /^[A-Za-z0-9_.@+-]+\.(?:html|css|scss|sass|less|js|jsx|ts|tsx|mjs|cjs|json|jsonc|md|txt|py|cs|java|go|rs|toml|yaml|yml|xml|xaml|sln|slnx|csproj|fsproj|vbproj|props|targets|ps1|sh|bat|cmd|sql|svg)$/i.test(basename);
}

function isShellLanguage(language) {
  return /^(sh|zsh|fish|ps1|cmd|bat|console|terminal|powershell|shell|bash|diff)$/i.test(String(language || '').trim());
}

function filePathFromLanguageAndContent(language, content, objective, usedPaths, blockCount) {
  const lang = normalizeFenceLanguage(language);
  const text = String(content || '').trim();
  const objectiveText = String(objective || '').toLowerCase();
  const candidates = [];
  const hasJsx = /<[A-Z][A-Za-z0-9]*(?:\s|>)|<>\s*[\s\S]*<\/>/m.test(text);
  const startsWithJsonObject = text.charCodeAt(0) === 123;

  if (lang === 'html' || /<!doctype html/i.test(text) || /<html[\s>]/i.test(text)) {
    candidates.push('index.html');
  } else if (lang === 'css' || lang === 'scss' || lang === 'sass' || lang === 'less') {
    candidates.push('styles.css', 'src/styles.css');
  } else if (lang === 'json') {
    if (/"scripts"\s*:|"(dependencies|devDependencies)"\s*:/i.test(text) || (startsWithJsonObject && /"name"\s*:/i.test(text))) {
      candidates.push('package.json');
    } else if (/"compilerOptions"\s*:/i.test(text)) {
      candidates.push('tsconfig.json');
    } else {
      candidates.push('data.json');
    }
  } else if (lang === 'md' || lang === 'markdown') {
    candidates.push('README.md');
  } else if (lang === 'py' || lang === 'python') {
    candidates.push('main.py', 'app.py');
  } else if (lang === 'cs' || lang === 'csharp') {
    candidates.push('Program.cs');
  } else if (lang === 'tsx') {
    candidates.push(/createRoot|ReactDOM/i.test(text) ? 'src/main.tsx' : 'src/App.tsx');
  } else if (lang === 'jsx' || hasJsx) {
    candidates.push(/createRoot|ReactDOM/i.test(text) ? 'src/main.jsx' : 'src/App.jsx');
  } else if (lang === 'ts') {
    candidates.push('src/index.ts', 'index.ts');
  } else if (lang === 'js' || lang === 'mjs' || lang === 'cjs' || (!lang && /function|const|let|document\.|import\s|export\s/.test(text))) {
    if (/express\s*\(/i.test(text)) {
      candidates.push('server.js');
    } else if (/document\.|addEventListener|querySelector/i.test(text)) {
      candidates.push('script.js', 'src/main.js');
    } else if (/react|jsx|createRoot|ReactDOM/i.test(text) || objectiveText.includes('react')) {
      candidates.push('src/App.jsx', 'src/main.jsx');
    } else {
      candidates.push('index.js');
    }
  }

  if (!candidates.length && blockCount === 1 && looksLikeWorkspaceChangeRequest(objective)) {
    candidates.push('index.txt');
  }
  return firstUnusedPath(candidates, usedPaths);
}

function firstUnusedPath(candidates, usedPaths) {
  for (const candidate of candidates) {
    const normalized = normalizePotentialGeneratedPath(candidate);
    if (normalized && !usedPaths.has(normalized.toLowerCase())) {
      return normalized;
    }
  }
  return '';
}

function extractCommandRecommendationsFromCodeBlocks(blocks) {
  const commands = [];
  for (const block of blocks) {
    if (!isShellLanguage(block.language)) {
      continue;
    }
    for (const rawLine of block.content.split(/\r?\n/)) {
      const command = rawLine.replace(/^\s*\$\s*/, '').trim();
      if (isReasonableSuggestedCommand(command)) {
        commands.push({
          command,
          reason: 'Suggested by the generated implementation response.'
        });
      }
      if (commands.length >= 5) {
        return commands;
      }
    }
  }
  return commands;
}

function isReasonableSuggestedCommand(command) {
  if (!command || command.length > 180 || /^\s*(#|\/\/)/.test(command)) {
    return false;
  }
  return !/\b(rm\s+-rf|del\s+\/[fsq]|format\s+|shutdown|reboot)\b/i.test(command);
}

async function openProposalDocument(proposal) {
  const content = JSON.stringify(proposal, null, 2);
  const document = await vscode.workspace.openTextDocument({ language: 'json', content });
  await vscode.window.showTextDocument(document, { preview: false });
}

async function openMarkdownResult(title, content) {
  const document = await vscode.workspace.openTextDocument({
    language: 'markdown',
    content: `# ${title}\n\n${content}`
  });
  await vscode.window.showTextDocument(document, { preview: false });
}

async function getOllamaModels(options = {}) {
  const cfg = getConfig();
  const target = options.target !== undefined ? options.target : await resolveWorkspaceTarget(undefined, { silent: true });
  const cacheKey = `${cfg.ollamaUrl}|${cfg.coreUrl}|${target && target.root ? target.root : ''}|${options.skipCore ? 'direct' : 'core'}`;
  if (!options.bypassModelCache && ollamaModelsListCache.models && ollamaModelsListCache.key === cacheKey && Date.now() < ollamaModelsListCache.until) {
    return ollamaModelsListCache.models;
  }

  if (!options.skipCore) {
    try {
      const coreModels = await getAegisCoreModels(target);
      if (coreModels.reachable || coreModels.models.length) {
        const models = coreModels.models;
        if (!options.bypassModelCache) {
          ollamaModelsListCache = { key: cacheKey, models: models.slice(), until: Date.now() + OLLAMA_MODELS_CACHE_MS };
        }
        return models;
      }
      throw new Error(coreModels.error || 'Aegis Core model contract reported that Ollama is unreachable.');
    } catch (error) {
      if (options.reportFallback !== false) {
        output && output.appendLine(`Aegis Core model inventory unavailable; using direct Ollama fallback: ${safeErrorMessage(error)}`);
      }
    }
  }

  const json = await requestJson(serviceUrl(cfg.ollamaUrl, '/api/tags'), undefined, 120000);
  const models = Array.isArray(json.models) ? json.models.map((model) => Object.assign({ source: 'ollama' }, model)) : [];
  if (!options.bypassModelCache) {
    ollamaModelsListCache = { key: cacheKey, models: models.slice(), until: Date.now() + OLLAMA_MODELS_CACHE_MS };
  }
  return models;
}

function isCoreModelSource(source) {
  return String(source || '').startsWith('aegis-core');
}

function refreshCoreRuntimeClients() {
  const config = getConfig();
  const version = extensionContext && extensionContext.extension && extensionContext.extension.packageJSON
    ? extensionContext.extension.packageJSON.version || 'unknown'
    : 'unknown';
  coreClient = createAegisCoreClient({
    baseUrl: config.coreUrl,
    output,
    version,
    clientId: 'aegis-vscode',
    clientType: 'vscode-extension',
    name: 'Aegis Local Agent for VS Code'
  });
  workflowClient = createWorkflowClient(coreClient, { sourceClient: 'vscode-extension' });
  runtimeState.configure(config.coreUrl);
  return coreClient;
}

function getCoreRuntimeClient() {
  if (!coreClient || coreClient.baseUrl !== getConfig().coreUrl) {
    return refreshCoreRuntimeClients();
  }
  return coreClient;
}

function getWorkflowRuntimeClient() {
  if (!workflowClient || !coreClient || coreClient.baseUrl !== getConfig().coreUrl) {
    refreshCoreRuntimeClients();
  }
  return workflowClient;
}

function recordRuntimeOperation(operation, runtime, status, detail, metadata = {}) {
  const snapshot = runtimeState.recordOperation(Object.assign({
    operation,
    runtime,
    status,
    detail: redactDiagnosticText(detail || '')
  }, metadata));
  if (runtimeLogger) {
    if (runtime === 'local') {
      runtimeLogger.fallback(operation, detail || 'Core unavailable', metadata);
    } else {
      runtimeLogger.core(operation, `${status}: ${detail || ''}`, metadata);
    }
  }
  panelProvider && panelProvider.post({ command: 'runtime', runtime: snapshot });
  return snapshot;
}

function recordCoreConnected(envelope, detail) {
  const text = detail || formatCoreContract(envelope);
  const snapshot = runtimeState.markCoreConnected(text);
  panelProvider && panelProvider.post({ command: 'runtime', runtime: snapshot });
  return snapshot;
}

function recordCoreDisconnected(error, operation = 'core') {
  const message = safeErrorMessage(error);
  const snapshot = runtimeState.markCoreDisconnected(message);
  recordRuntimeOperation(operation, 'local', 'fallback', message);
  panelProvider && panelProvider.post({ command: 'runtime', runtime: snapshot });
  return snapshot;
}

async function refreshCoreRuntimeDashboard(target) {
  if (!target) {
    return runtimeState.snapshot();
  }
  try {
    const client = getCoreRuntimeClient();
    const dashboard = await client.clientSyncDashboard(target, { limit: 30 });
    runtimeState.mergeClientSyncDashboard(dashboard);
    const checkpoints = await client.listCheckpoints(target, { limit: 10 }).catch(() => null);
    if (checkpoints) {
      runtimeState.setCheckpoints(coreEnvelopeData(checkpoints).checkpoints || []);
    }
    const quality = await client.qualityGates(target, { limit: 20 }).catch(() => null);
    if (quality) {
      runtimeState.setQualityGates(quality);
    }
    recordCoreConnected(dashboard, 'Client sync dashboard connected.');
  } catch (error) {
    runtimeState.markCoreDisconnected(safeErrorMessage(error));
  }
  return runtimeState.snapshot();
}

function startCoreWorkflowEventRefresh(target, workflowId) {
  if (!target || !workflowId) {
    return;
  }
  getWorkflowRuntimeClient().events(target, {
    workflowId,
    follow: true,
    limit: 25,
    maxSeconds: 5,
    timeoutMs: 15000,
    onEvent: (event) => {
      runtimeState.appendWorkflowEvents([event]);
      const summary = event && event.data ? event.data : event;
      if (summary && typeof summary === 'object') {
        runtimeState.setActiveWorkflow({
          id: summary.workflow_id || workflowId,
          workflow_type: summary.workflow_type || runtimeState.snapshot().activeWorkflowType,
          status: summary.status || runtimeState.snapshot().activeWorkflowStatus
        });
      }
      panelProvider && panelProvider.post({ command: 'runtime', runtime: runtimeState.snapshot() });
    }
  }).then((events) => {
    if (events && events.length) {
      runtimeState.appendWorkflowEvents(events);
      panelProvider && panelProvider.post({ command: 'runtime', runtime: runtimeState.snapshot() });
    }
  }).catch((error) => {
    output && output.appendLine(`Aegis Core workflow event stream unavailable: ${safeErrorMessage(error)}`);
  });
}

function coreUrl(pathname, target) {
  const url = serviceUrl(getConfig().coreUrl, pathname);
  if (target && target.root) {
    url.searchParams.set('workspace', target.root);
  }
  return url;
}

async function getAegisCoreEnvelope(pathname, target, expectedKind, timeoutMs = 120000) {
  const envelope = await requestJson(coreUrl(pathname, target), undefined, timeoutMs);
  return validateAegisCoreEnvelope(envelope, expectedKind);
}

async function postAegisCoreEnvelope(pathname, body, expectedKind, timeoutMs = 120000) {
  const envelope = await requestJson(coreUrl(pathname), body, timeoutMs);
  return validateAegisCoreEnvelope(envelope, expectedKind);
}

function validateAegisCoreEnvelope(envelope, expectedKind) {
  return validateCoreEnvelope(envelope, expectedKind, { redactDiagnosticText });
}

function requireAegisCoreOk(envelope, action) {
  return requireCoreOk(envelope, action, { redactDiagnosticText });
}

async function getAegisCoreHealth(target) {
  const envelope = await getCoreRuntimeClient().health(target);
  recordCoreConnected(envelope);
  return envelope;
}

async function getAegisCoreModels(target) {
  const result = await getCoreRuntimeClient().models(target);
  recordCoreConnected(result.envelope);
  return result;
}

async function getAegisCoreSettings(target) {
  return getCoreRuntimeClient().settings(target);
}

async function getAegisCoreWorkspaceScan(target) {
  const envelope = await getCoreRuntimeClient().workspaceScan(target);
  recordRuntimeOperation('workspace-scan', 'core', 'completed', 'Workspace scan delegated to Aegis Core.');
  return envelope;
}

async function getAegisCoreMemory(target) {
  return getCoreRuntimeClient().memory(target);
}

async function getAegisCoreDiagnostics(target) {
  return getCoreRuntimeClient().diagnostics(target);
}

async function getAegisCoreValidationSummary(target) {
  return getCoreRuntimeClient().validationSummary(target);
}

async function tryGenerateAegisCoreRoadmap(target) {
  try {
    updateStatusBar('Indexing', 'Aegis Core is generating the shared roadmap.');
    const roadmapWorkflow = await getWorkflowRuntimeClient().continueRoadmap(target, 'Generate or update the shared project roadmap.', {
      command: 'generateProjectRoadmap',
      model: getConfig().chatModel,
      safetyMode: getConfig().safetyMode
    }).catch(() => null);
    if (roadmapWorkflow && roadmapWorkflow.id) {
      activeCoreWorkflowId = roadmapWorkflow.id;
      runtimeState.setActiveWorkflow(roadmapWorkflow.summary);
    }
    const envelope = await getCoreRuntimeClient().roadmap(target);
    const data = coreEnvelopeData(envelope);
    output && output.appendLine(`Aegis Core updated roadmap via ${formatCoreContract(envelope)}.`);
    recordRuntimeOperation('roadmap', 'core', 'completed', 'Project roadmap delegated to Aegis Core.', {
      workflowId: activeCoreWorkflowId
    });
    return {
      envelope,
      roadmapPath: data.roadmap_path || '',
      markdown: data.markdown || ''
    };
  } catch (error) {
    output && output.appendLine(`Aegis Core roadmap unavailable; using VS Code local roadmap fallback: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'roadmap');
    vscode.window.showWarningMessage('Aegis Core roadmap generation is unavailable, so VS Code will use its local model fallback.');
    return null;
  }
}

async function runAegisCoreValidation(target) {
  const summaryEnvelope = await getAegisCoreValidationSummary(target);
  const summary = coreEnvelopeData(summaryEnvelope);
  const commands = Array.isArray(summary.commands) ? summary.commands : [];
  if (!commands.length) {
    return {
      success: true,
      skipped: true,
      commands: [],
      output: 'Aegis Core did not detect a safe project validation command.',
      source: 'aegis-core'
    };
  }

  const first = commands[0];
  const commandParts = Array.isArray(first.command) ? first.command.map(String) : String(first.command || '').split(/\s+/).filter(Boolean);
  updateAgentState({
    status: 'Running validation',
    validationOutput: `$ ${commandParts.join(' ')}\nAegis Core is running shared validation.`
  });

  const runEnvelope = await getCoreRuntimeClient().runValidation(target, {
    command: commandParts,
    timeoutSeconds: 300,
    taskId: activeCoreTaskId || null
  });
  const runData = coreEnvelopeData(runEnvelope);
  const result = runData.validation || {};
  const outputText = [result.stdout, result.stderr].filter(Boolean).join('\n') || (result.ok ? 'Validation passed.' : 'Validation failed.');
  const commandText = Array.isArray(result.command) ? result.command.join(' ') : commandParts.join(' ');
  const commandResult = {
    command: commandText,
    cwd: target.root,
    success: Boolean(result.ok),
    exitCode: result.returncode === undefined ? null : result.returncode,
    output: truncateMiddle(outputText, 24000),
    source: 'aegis-core'
  };
  if (!commandResult.success) {
    lastFailedCommand = commandText;
  }
  runtimeState.setLatestValidation({
    ok: commandResult.success,
    success: commandResult.success,
    command: commandText,
    source: 'aegis-core'
  });
  recordRuntimeOperation('validation', 'core', commandResult.success ? 'completed' : 'failed', commandResult.success ? 'Validation passed in Core.' : 'Validation failed in Core.', {
    jobId: runData.job_id || '',
    workflowId: activeCoreWorkflowId || ''
  });
  return {
    success: commandResult.success,
    skipped: false,
    commands: [commandResult],
    output: validationResultsToOutput([commandResult]),
    source: 'aegis-core'
  };
}

async function registerAegisCoreClient(target) {
  const resolvedTarget = target || await resolveWorkspaceTarget(undefined, { silent: true });
  if (!resolvedTarget) {
    return false;
  }
  try {
    const registration = await getCoreRuntimeClient().registerClient(resolvedTarget, {
      activeWorkflowId: activeCoreWorkflowId || activeCoreTaskId || null,
      capabilities: defaultCapabilities(),
      metadata: {
        active_task_id: activeCoreTaskId || '',
        safety_mode: getConfig().safetyMode,
        fallback_mode: runtimeState.snapshot().fallbackMode
      }
    });
    requireAegisCoreOk(registration.envelope, 'register the VS Code client');
    recordCoreConnected(registration.envelope, `VS Code client ${registration.mode === 'sync' ? 'synced' : 'registered'} with Core.`);
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis Core registration skipped: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'client-registration');
    return false;
  }
}

async function createAegisCoreTask(target, title, kind, request, metadata = {}) {
  try {
    const envelope = await requestJson(coreUrl('/v1/tasks'), {
      workspace: target.root,
      title,
      kind,
      source_client: 'vscode-extension',
      request,
      metadata
    }, 120000);
    const response = requireAegisCoreOk(validateAegisCoreEnvelope(envelope, 'task.created'), 'create a shared task');
    return response && response.data && response.data.id ? response.data.id : '';
  } catch (error) {
    output && output.appendLine(`Aegis Core task creation skipped: ${safeErrorMessage(error)}`);
    return '';
  }
}

async function updateAegisCoreTaskStatus(target, taskId, status, summary = '') {
  if (!taskId) {
    return false;
  }
  try {
    const envelope = await requestJson(coreUrl(`/v1/tasks/${encodeURIComponent(taskId)}/status`), {
      workspace: target.root,
      status,
      summary
    }, 120000);
    requireAegisCoreOk(validateAegisCoreEnvelope(envelope, 'task.updated'), 'update a shared task');
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis Core task update skipped: ${safeErrorMessage(error)}`);
    return false;
  }
}

async function askOllamaWithFallback(model, prompt, options = {}) {
  const config = getConfig();
  const candidates = [model || config.chatModel, ...config.fallbackModels].filter(Boolean);
  const uniqueCandidates = Array.from(new Set(candidates));
  let lastError;

  for (let index = 0; index < uniqueCandidates.length; index += 1) {
    if (options.cancellationToken && options.cancellationToken.isCancellationRequested) {
      updateAgentState({ status: 'Local model call failed' });
      throw new Error('Aegis request was cancelled.');
    }
    const candidate = uniqueCandidates[index];
    const started = Date.now();
    const attemptLabel = uniqueCandidates.length > 1 ? `model ${index + 1}/${uniqueCandidates.length}` : 'primary model';
    pushProgress('Local model request started', `Waiting on ${candidate} (${attemptLabel}).`);
    updateAgentState({ status: 'Waiting for local model', model: candidate });
    try {
      const response = await askOllama(candidate, prompt, options);
      const elapsed = ((Date.now() - started) / 1000).toFixed(1);
      pushProgress('Local model response ready', `${candidate} completed in ${elapsed}s.`);
      updateAgentState({ status: 'Processing local model response', model: candidate });
      return response;
    } catch (error) {
      lastError = error;
      output.appendLine(`Ollama model ${candidate} failed: ${safeErrorMessage(error)}`);
      pushProgress(
        'Local model fallback',
        index + 1 < uniqueCandidates.length
          ? `${candidate} failed; trying ${uniqueCandidates[index + 1]}.`
          : `${candidate} failed; no fallback model remains.`
      );
      logExtensionEvent('model-call', `Ollama model ${candidate} failed.`, { error: safeErrorMessage(error) }).catch(() => {});
    }
  }

  updateAgentState({ status: 'Local model call failed' });
  throw lastError || new Error('No local Ollama models were available.');
}

async function askOllama(model, prompt, options = {}) {
  const selectedModel = model || getConfig().chatModel;
  const body = {
    model: selectedModel,
    stream: false,
    messages: [
      {
        role: 'system',
        content: 'You are a precise local coding assistant for the Aegis project.'
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    options: {
      temperature: options.temperature === undefined ? 0.2 : options.temperature,
      num_ctx: getEffectiveOllamaNumCtx(getConfig())
    }
  };

  if (options.json) {
    body.format = 'json';
  }

  const started = Date.now();
  logExtensionEvent('model-call', `Calling Ollama model ${selectedModel}.`, {
    json: Boolean(options.json),
    promptChars: typeof prompt === 'string' ? prompt.length : 0
  }).catch(() => {});
  const json = await requestJson(
    serviceUrl(getConfig().ollamaUrl, '/api/chat'),
    body,
    options.timeoutMs || 600000,
    options.cancellationToken
  );
  const elapsed = ((Date.now() - started) / 1000).toFixed(1);
  const content = json && json.message && typeof json.message.content === 'string' ? json.message.content : JSON.stringify(json);
  output.appendLine(`Ollama ${selectedModel} completed in ${elapsed}s.`);
  logExtensionEvent('model-call', `Ollama ${selectedModel} completed.`, {
    elapsedSeconds: elapsed,
    responseChars: content.length
  }).catch(() => {});
  return content.trim();
}

function requestJson(url, body, timeoutMs, cancellationToken) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let cancelDisposable;
    const finish = (kind, value) => {
      if (settled) {
        return;
      }
      settled = true;
      if (cancelDisposable) {
        cancelDisposable.dispose();
        cancelDisposable = undefined;
      }
      if (kind === 'resolve') {
        resolve(value);
      } else {
        reject(value);
      }
    };

    if (cancellationToken && cancellationToken.isCancellationRequested) {
      finish('reject', new Error('Aegis request was cancelled.'));
      return;
    }
    if (cancellationToken) {
      cancelDisposable = cancellationToken.onCancellationRequested(() => {
        if (httpReq && !httpReq.destroyed) {
          httpReq.destroy(new Error('Aegis request was cancelled.'));
        }
      });
    }

    const isHttps = url.protocol === 'https:';
    const data = body ? Buffer.from(JSON.stringify(body), 'utf8') : undefined;
    const extVer = extensionContext && extensionContext.extension && extensionContext.extension.packageJSON
      ? extensionContext.extension.packageJSON.version || '0'
      : '0';
    const baseHeaders = {
      Accept: 'application/json',
      'User-Agent': `Aegis-Local-Agent-VSCode/${extVer}`
    };
    const httpReq = (isHttps ? https : http).request({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port,
      path: `${url.pathname}${url.search}`,
      method: body ? 'POST' : 'GET',
      headers: body
        ? Object.assign({}, baseHeaders, {
            'Content-Type': 'application/json',
            'Content-Length': data.length
          })
        : baseHeaders
    }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        if (response.statusCode < 200 || response.statusCode >= 300) {
          finish('reject', new Error(formatHttpError(response.statusCode, text)));
          return;
        }
        try {
          finish('resolve', parseJsonText(text));
        } catch (error) {
          finish('reject', new Error(`Invalid JSON from ${formatRequestTarget(url)}: ${error.message}`));
        }
      });
    });

    httpReq.on('error', (err) => finish('reject', err));
    httpReq.setTimeout(timeoutMs, () => {
      httpReq.destroy(new Error(`Timed out calling ${formatRequestTarget(url)}`));
    });

    if (data) {
      httpReq.write(data);
    }
    httpReq.end();
  });
}

function formatRequestTarget(url) {
  const pathname = url && url.pathname ? url.pathname : '/';
  const origin = url && url.origin && url.origin !== 'null'
    ? url.origin
    : `${url.protocol || 'http:'}//${url.host || 'unknown-host'}`;
  return `${origin}${pathname}`;
}

function formatHttpError(statusCode, responseText) {
  const detail = extractHttpErrorDetail(responseText);
  if (detail) {
    return `HTTP ${statusCode}: ${detail}`;
  }
  const fallback = sanitizeHttpErrorText(responseText);
  return fallback ? `HTTP ${statusCode}: ${fallback}` : `HTTP ${statusCode}`;
}

function extractHttpErrorDetail(responseText) {
  if (!responseText || !String(responseText).trim()) {
    return '';
  }
  try {
    const parsed = parseJsonText(responseText);
    if (typeof parsed.detail === 'string') {
      return sanitizeHttpErrorText(parsed.detail);
    }
    if (Array.isArray(parsed.detail)) {
      const messages = parsed.detail
        .map((item) => (item && typeof item.msg === 'string' ? item.msg : String(item || '').trim()))
        .filter(Boolean);
      if (messages.length) {
        return sanitizeHttpErrorText(messages.join('; '));
      }
    }
    for (const key of ['error', 'message']) {
      if (typeof parsed[key] === 'string') {
        return sanitizeHttpErrorText(parsed[key]);
      }
    }
  } catch (error) {
    return '';
  }
  return '';
}

function sanitizeHttpErrorText(text) {
  const cleaned = redactDiagnosticText(text);
  return cleaned.length > 700 ? `${cleaned.slice(0, 697)}...` : cleaned;
}

function safeErrorMessage(error, maxChars = 700) {
  return _errorsModule.safeErrorMessage(error, maxChars);
}

function redactDiagnosticText(text, maxChars = 700) {
  return _errorsModule.redactDiagnosticText(text, maxChars);
}

function activeEditorContext(editor) {
  const rel = vscode.workspace.asRelativePath(editor.document.uri, false);
  const text = editor.document.getText();
  return formatFileChunk(rel, text);
}

async function readWorkspaceFile(root, rel) {
  return _fsSafeModule.readWorkspaceFile(root, rel);
}

function formatFileChunk(rel, text) {
  return `# File: ${rel}\n\`\`\`\n${truncateMiddle(text, MAX_FILE_CHARS)}\n\`\`\``;
}

function truncateMiddle(text, maxChars) {
  return _errorsModule.truncateMiddle(text, maxChars);
}

function extractJson(raw) {
  return _proposalParserModule.extractJson(raw);
}

function parseJsonText(text) {
  return _fsSafeModule.parseJsonText(text);
}

function stripUtf8Bom(text) {
  return _fsSafeModule.stripUtf8Bom(text);
}

function normalizeLineEndings(text) {
  return _pathSafeModule.normalizeLineEndings(text);
}

function resolveInside(root, relativePath) {
  return _fsSafeModule.resolveInside(root, relativePath);
}

function validateProposalEdit(proposal, edit) {
  return _proposalSafetyModule.validateProposalEdit(proposal, edit);
}

function formatBlockedProposalEditSummary(blocked) {
  return _proposalSafetyModule.formatBlockedProposalEditSummary(blocked);
}

function isBlockedRelativePath(relativePath) {
  return _pathSafeModule.isBlockedRelativePath(relativePath);
}

function timestampForPath() {
  return _pathSafeModule.timestampForPath();
}

function isSafeBackupId(value) {
  return _proposalSafetyModule.isSafeBackupId(value);
}

async function saveProposal(proposal) {
  const stateRoot = proposal.workspaceRoot || proposal.workspace || proposal.targetRoot;
  if (!stateRoot) {
    return;
  }
  const proposalRoot = path.join(stateRoot, '.aegis', 'vscode-autopilot', 'proposals');
  await fs.mkdir(proposalRoot, { recursive: true });
  const fileName = `${timestampForPath()}.json`;
  await fs.writeFile(path.join(proposalRoot, fileName), JSON.stringify(sanitizeProposalForStorage(proposal), null, 2), 'utf8');
}

function sanitizeProposalForStorage(proposal) {
  return _proposalSafetyModule.sanitizeProposalForStorage(proposal);
}

async function readRecentProposalSummaries(target) {
  const stateRoot = target.workspaceRoot || target.root;
  const proposalRoot = path.join(stateRoot, '.aegis', 'vscode-autopilot', 'proposals');
  try {
    const names = await fs.readdir(proposalRoot);
    const jsonNames = names.filter((name) => name.endsWith('.json')).sort().reverse().slice(0, 6);
    const rows = [];
    const targetIsWorkspaceRoot = path.resolve(target.root) === path.resolve(target.workspaceRoot || target.root);
    for (const name of jsonNames) {
      const raw = await fs.readFile(path.join(proposalRoot, name), 'utf8');
      const proposal = parseJsonText(raw);
      if (!targetIsWorkspaceRoot && proposal.targetRoot && proposal.targetRoot !== target.root && proposal.workspace !== target.root) {
        continue;
      }
      const files = Array.isArray(proposal.fileEdits) ? proposal.fileEdits.map((edit) => edit.path).join(', ') : '';
      rows.push(`- ${proposal.createdAt || name}: ${proposal.summary || 'No summary'}${files ? ` (files: ${files})` : ''}`);
      if (rows.length >= 4) {
        break;
      }
    }
    return rows;
  } catch (error) {
    return [];
  }
}

async function recordChangeBackup(target, manifest) {
  await ensureWorkspaceMemory(target);
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  const backupsRoot = path.join(memoryRoot, 'backups');
  await fs.mkdir(backupsRoot, { recursive: true });
  const lastPath = path.join(backupsRoot, 'last-change.json');
  const historyPath = path.join(memoryRoot, 'change-history.json');
  const history = await readChangedFilesHistory(target);
  const entry = {
    backupId: manifest.backupId,
    createdAt: manifest.createdAt,
    summary: manifest.summary,
    stageName: manifest.stageName || '',
    files: manifest.files.map((file) => file.workspaceRelativePath || file.path),
    backupRoot: path.join(backupsRoot, manifest.backupId)
  };
  const nextHistory = [entry, ...history].slice(0, 50);
  changedFilesHistory = nextHistory;
  await writeMemoryFileBestEffort(lastPath, JSON.stringify(manifest, null, 2), 'last backup manifest');
  await writeMemoryFileBestEffort(historyPath, JSON.stringify(nextHistory, null, 2), 'change history');
}

async function writeAgentRecovery(target, patch) {
  if (!target) {
    return;
  }
  await ensureWorkspaceMemory(target);
  const recoveryPath = path.join(target.workspaceRoot || target.root, '.aegis', 'agent-recovery.json');
  let existing = {};
  try {
    existing = parseJsonText(await fs.readFile(recoveryPath, 'utf8'));
  } catch (error) {
    existing = {};
  }
  const next = sanitizeHistoryEvent(Object.assign({}, existing, patch || {}, {
    version: 1,
    updatedAt: new Date().toISOString(),
    workspaceRoot: target.workspaceRoot || target.root,
    targetRoot: target.root
  }));
  await writeMemoryFileBestEffort(recoveryPath, JSON.stringify(next, null, 2), 'agent recovery state');
}

async function clearAgentRecovery(target) {
  if (!target) {
    return;
  }
  const recoveryPath = path.join(target.workspaceRoot || target.root, '.aegis', 'agent-recovery.json');
  try {
    await fs.rm(recoveryPath, { force: true });
  } catch (error) {
    output.appendLine(`Could not clear Aegis recovery state: ${safeErrorMessage(error)}`);
  }
}

async function recoverAgentStateIfNeeded() {
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  if (!target) {
    updateStatusBar('No Workspace', 'Open a VS Code folder to use Aegis.');
    return;
  }
  const recoveryPath = path.join(target.workspaceRoot || target.root, '.aegis', 'agent-recovery.json');
  let recovery;
  try {
    recovery = parseJsonText(await fs.readFile(recoveryPath, 'utf8'));
  } catch (error) {
    return;
  }
  if (!recovery || /completed|discarded/i.test(recovery.status || '')) {
    await clearAgentRecovery(target);
    return;
  }
  await logExtensionEvent('recovery', 'Detected unfinished Aegis agent task.', recovery, target);
  const action = await vscode.window.showWarningMessage(
    `Aegis found an unfinished agent task: ${recovery.request || recovery.summary || recovery.status}.`,
    { modal: true },
    'Resume',
    'Discard',
    'Rollback Last Change'
  );
  if (action === 'Resume') {
    latestErrorInfo = makeEmptyErrorInfo();
    await runAgentMode(recovery.request || lastAgentRequest || 'Resume the unfinished Aegis task.', target);
  } else if (action === 'Rollback Last Change') {
    await rollbackLastAgentChange(target);
  } else if (action === 'Discard') {
    await clearAgentRecovery(target);
    await logExtensionEvent('recovery', 'Discarded unfinished Aegis agent task.', recovery, target);
  }
}

async function readChangedFilesHistory(target) {
  const historyPath = path.join(target.workspaceRoot || target.root, '.aegis', 'change-history.json');
  try {
    const parsed = parseJsonText(await fs.readFile(historyPath, 'utf8'));
    if (Array.isArray(parsed)) {
      changedFilesHistory = parsed.slice(0, 50);
      return changedFilesHistory;
    }
  } catch (error) {
    // Missing history is expected for projects without applied agent changes.
  }
  changedFilesHistory = [];
  return [];
}

async function rollbackLastAgentChange(resource, options = {}) {
  const target = isWorkspaceTarget(resource) ? resource : await resolveWorkspaceTarget(resource);
  if (!target) {
    vscode.window.showWarningMessage('Open a VS Code folder before rolling back an Aegis change.');
    return;
  }
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  const lastPath = path.join(memoryRoot, 'backups', 'last-change.json');
  let manifest;
  try {
    manifest = parseJsonText(await fs.readFile(lastPath, 'utf8'));
  } catch (error) {
    vscode.window.showInformationMessage('No Aegis change backup is available to roll back.');
    return;
  }
  if (!manifest || !Array.isArray(manifest.files) || !manifest.files.length) {
    vscode.window.showInformationMessage('The last Aegis backup has no file entries to restore.');
    return;
  }
  if (!isSafeBackupId(manifest.backupId)) {
    vscode.window.showErrorMessage('The last Aegis backup manifest has an unsafe backup id. Rollback was not started.');
    return;
  }

  if (!options.skipPrompt) {
    const rollbackSource = manifest.coreCheckpointId
      ? `Core checkpoint ${manifest.coreCheckpointId}`
      : '.aegis/backups';
    const answer = await vscode.window.showWarningMessage(
      `Rollback last Aegis change from ${manifest.createdAt || manifest.backupId}? This restores ${manifest.files.length} file(s) from ${rollbackSource}.`,
      { modal: true },
      'Rollback'
    );
    if (answer !== 'Rollback') {
      return;
    }
  }

  if (manifest.coreCheckpointId) {
    try {
      const restoreEnvelope = await getCoreRuntimeClient().restoreCheckpoint(target, manifest.coreCheckpointId, {
        taskId: activeCoreTaskId || null
      });
      const data = coreEnvelopeData(restoreEnvelope);
      const restored = Array.isArray(data.restored) ? data.restored : [];
      const validation = {
        success: true,
        skipped: true,
        commands: [],
        output: `Rolled back last Aegis Core change.\n${restored.map((file) => `- ${file}`).join('\n')}`
      };
      await appendAgentHistory(target, {
        type: 'rollback',
        backupId: manifest.backupId,
        coreCheckpointId: manifest.coreCheckpointId,
        files: restored
      });
      clearProjectSnapshotCache(target.root);
      await recordValidationResult(target, validation);
      runtimeState.setCheckpoints([{ id: data.pre_restore_checkpoint_id || manifest.coreCheckpointId }]);
      recordRuntimeOperation('rollback', 'core', 'completed', `Restored Core checkpoint ${manifest.coreCheckpointId}.`, {
        jobId: data.job_id || '',
        checkpointId: manifest.coreCheckpointId,
        workflowId: activeCoreWorkflowId || ''
      });
      updateAgentState({
        status: 'Rolled back last Core change',
        pendingDiffs: [],
        validationOutput: validation.output
      });
      panelProvider && panelProvider.refresh();
      vscode.window.showInformationMessage(`Rolled back ${restored.length} file operation(s) through Aegis Core.`);
      return;
    } catch (error) {
      reportError(error, { failedCommand: 'Aegis: Rollback Last Agent Change', retryCommand: 'rollbackLastChange' });
      vscode.window.showErrorMessage(`Aegis Core rollback could not be completed: ${safeErrorMessage(error)}`);
      return;
    }
  }

  const workspaceRoot = target.workspaceRoot || target.root;
  const backupsRoot = path.join(memoryRoot, 'backups');
  const backupRoot = resolveInside(backupsRoot, manifest.backupId);
  if (!backupRoot) {
    vscode.window.showErrorMessage('The last Aegis backup path is outside the workspace backup folder. Rollback was not started.');
    return;
  }
  const restored = [];
  try {
    restored.push(...await restoreFromManifest(backupRoot, manifest, { workspaceRoot }));
  } catch (error) {
    reportError(error, { failedCommand: 'Aegis: Rollback Last Agent Change', retryCommand: 'rollbackLastChange' });
    vscode.window.showErrorMessage(`Aegis rollback could not be completed: ${safeErrorMessage(error)}`);
    return;
  }

  const validation = {
    success: true,
    skipped: true,
    commands: [],
    output: `Rolled back last Aegis change.\n${restored.map((file) => `- ${file}`).join('\n')}`
  };
  await appendAgentHistory(target, {
    type: 'rollback',
    backupId: manifest.backupId,
    files: restored
  });
  clearProjectSnapshotCache(target.root);
  await recordValidationResult(target, validation);
  updateAgentState({
    status: 'Rolled back last change',
    pendingDiffs: [],
    validationOutput: validation.output
  });
  panelProvider && panelProvider.refresh();
  vscode.window.showInformationMessage(`Rolled back ${restored.length} file(s) from the last Aegis change.`);
}

async function restoreFromManifest(backupRoot, manifest, options = {}) {
  const expectedWorkspaceRoot = options.workspaceRoot ? path.resolve(options.workspaceRoot) : '';
  const workspaceRoot = manifest && manifest.workspaceRoot
    ? path.resolve(manifest.workspaceRoot)
    : expectedWorkspaceRoot;
  if (!workspaceRoot) {
    throw new Error('Rollback manifest is missing a workspace root.');
  }
  if (expectedWorkspaceRoot && workspaceRoot !== expectedWorkspaceRoot) {
    throw new Error('Rollback manifest workspace does not match the current workspace.');
  }
  const restored = [];
  for (const file of manifest.files || []) {
    const workspaceRelative = file.workspaceRelativePath || file.path;
    const targetPath = resolveInside(workspaceRoot, workspaceRelative);
    if (!targetPath) {
      output.appendLine(`Skipped restore path outside workspace: ${workspaceRelative}`);
      continue;
    }
    if (file.existed) {
      const backupPath = resolveInside(backupRoot, file.backupPath || '');
      if (!backupPath) {
        output.appendLine(`Skipped unsafe backup file path for restore: ${file.backupPath || '<missing>'}`);
        continue;
      }
      let backupBytes;
      try {
        backupBytes = await fs.readFile(backupPath);
      } catch (error) {
        output.appendLine(`Skipped missing or unreadable backup file for restore: ${file.backupPath || '<missing>'} (${safeErrorMessage(error)})`);
        continue;
      }
      await fs.mkdir(path.dirname(targetPath), { recursive: true });
      await fs.writeFile(targetPath, backupBytes);
      restored.push(workspaceRelative);
    } else {
      try {
        const stat = await fs.stat(targetPath);
        if (stat.isFile()) {
          await fs.rm(targetPath, { force: true });
          restored.push(`${workspaceRelative} (removed)`);
        }
      } catch (error) {
        if (error.code !== 'ENOENT') {
          throw error;
        }
      }
    }
  }
  return restored;
}

async function initializeCurrentWorkspaceMemory() {
  if (!getConfig().autoScanOnOpen) {
    return;
  }
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  if (!target) {
    updateStatusBar('No Workspace', 'Open a VS Code folder to use Aegis.');
    return;
  }
  updateStatusBar('Indexing', `Updating Aegis memory for ${target.label}.`);
  await logExtensionEvent('indexing', 'Workspace memory scan started.', { target: target.root }, target);
  await ensureWorkspaceMemory(target);
  const snapshot = await getProjectSnapshot(target, { fast: true });
  await updateWorkspaceMemoryFromSnapshot(target, snapshot);
  await logExtensionEvent('indexing', 'Workspace memory scan finished.', {
    files: snapshot.fileCount,
    languages: snapshot.languages,
    frameworks: snapshot.frameworks
  }, target);
  updateStatusBar('Ready', `Aegis ready for ${target.label}.`);
}

async function readMemoryFile(target, name) {
  try {
    return await fs.readFile(path.join(target.workspaceRoot || target.root, '.aegis', name), 'utf8');
  } catch (error) {
    return '';
  }
}

async function openMemoryDocument(target, name) {
  const filePath = path.join(target.workspaceRoot || target.root, '.aegis', name);
  const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
  await vscode.window.showTextDocument(document, { preview: false });
}

async function writeManagedSection(target, name, sectionName, content) {
  await ensureWorkspaceMemory(target);
  const filePath = path.join(target.workspaceRoot || target.root, '.aegis', name);
  let existing = '';
  try {
    existing = await fs.readFile(filePath, 'utf8');
  } catch (error) {
    existing = `# ${sectionName}\n\n`;
  }
  const start = `<!-- AEGIS:${sectionName}:START -->`;
  const end = `<!-- AEGIS:${sectionName}:END -->`;
  const block = `${start}\n${content.trim()}\n${end}`;
  const pattern = new RegExp(`${escapeRegExp(start)}[\\s\\S]*?${escapeRegExp(end)}`);
  const next = pattern.test(existing)
    ? existing.replace(pattern, block)
    : `${existing.trimEnd()}\n\n${block}\n`;
  await writeMemoryFileBestEffort(filePath, next, `managed section ${name}`);
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function makeEmptyAgentState() {
  return _agentModeModule.makeEmptyAgentState();
}

function makeEmptyHealthCheckState() {
  return _agentModeModule.makeEmptyHealthCheckState();
}

function makeEmptyModelDiagnosticsState() {
  return _agentModeModule.makeEmptyModelDiagnosticsState();
}

function makeEmptyErrorInfo() {
  return _agentModeModule.makeEmptyErrorInfo();
}

function resetAgentState(target, model) {
  agentState = makeEmptyAgentState();
  agentState.status = 'Starting';
  agentState.model = model || '';
  agentState.workspace = target ? target.root : '';
  updateStatusBar('Running', 'Aegis Agent Mode is starting.');
  panelProvider && panelProvider.refresh();
}

function updateAgentState(patch) {
  agentState = Object.assign({}, agentState, patch || {});
  if (/index/i.test(agentState.status || '')) {
    updateStatusBar('Indexing', agentState.status);
  } else if (/running|creating|repair|validation|waiting|starting|inspect/i.test(agentState.status || '')) {
    updateStatusBar('Running', agentState.status);
  } else if (/error|fail/i.test(agentState.status || '')) {
    updateStatusBar('Error', agentState.status);
  } else if (/passed|idle|ready|rolled back/i.test(agentState.status || '')) {
    updateStatusBar('Ready', agentState.status);
  }
  panelProvider && panelProvider.post({ command: 'agentState', agent: agentState });
}

function pushProgress(label, detail = '') {
  const progressItems = _agentModeModule.buildProgressUpdate(agentState, label, detail);
  updateAgentState({ progressItems });
}

function setContextFiles(files, reason) {
  const contextFiles = _agentModeModule.buildContextFilesUpdate(files, reason);
  updateAgentState({ contextFiles });
}

function proposalToPlanText(proposal) {
  return _proposalParserModule.proposalToPlanText(proposal);
}

async function ensureWorkspaceMemory(target) {
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  try {
    await fs.mkdir(memoryRoot, { recursive: true });
  } catch (error) {
    output && output.appendLine(`Aegis memory folder is not writable: ${memoryRoot} (${safeErrorMessage(error)})`);
    return memoryRoot;
  }
  const files = {
    'project-summary.md': '# Project Summary\n\nNot scanned yet.\n',
    'architecture-map.md': '# Architecture Map\n\nAdd human architecture notes here. Aegis updates its managed section below.\n',
    'roadmap.md': '# Roadmap\n\n- Keep changes small, reviewable, and validated.\n',
    'decisions.md': '# Decisions\n\n- Local agent changes require preview and approval before apply.\n',
    'known-issues.md': '# Known Issues\n\nAdd human issue notes here. Aegis updates its managed section below.\n',
    'real-world-testing.md': '# Real-World Testing\n\nTrack real project hardening findings here.\n',
    'validation-log.md': '# Validation Log\n\n',
    'extension-log.md': '# Extension Log\n\n',
    'agent-history.json': '[]\n',
    'file-index.json': '{\n  "version": 1,\n  "files": []\n}\n',
    'dependency-graph.json': '{\n  "version": 1,\n  "nodes": [],\n  "edges": []\n}\n',
    'symbol-index.json': '{\n  "version": 1,\n  "symbols": []\n}\n',
    'change-history.json': '[]\n'
  };

  for (const [name, content] of Object.entries(files)) {
    await ensureMemoryFile(memoryRoot, name, content);
  }
  return memoryRoot;
}

async function ensureMemoryFile(memoryRoot, name, content) {
  const targetPath = path.join(memoryRoot, name);
  try {
    const stat = await fs.stat(targetPath);
    if (!stat.isFile()) {
      output && output.appendLine(`Aegis memory file is not a regular file; leaving it untouched: ${targetPath}`);
    }
    return;
  } catch (error) {
    if (error.code !== 'ENOENT') {
      output && output.appendLine(`Aegis memory file check failed: ${targetPath} (${safeErrorMessage(error)})`);
      return;
    }
  }

  await writeMemoryFileBestEffort(targetPath, content, `initialize ${name}`);
}

async function writeMemoryFileBestEffort(filePath, content, label = 'memory file') {
  let tempPath = '';
  try {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    try {
      const stat = await fs.stat(filePath);
      if (!stat.isFile()) {
        output && output.appendLine(`Aegis ${label} is not a regular file; leaving it untouched: ${filePath}`);
        return false;
      }
    } catch (error) {
      if (error.code !== 'ENOENT') {
        output && output.appendLine(`Aegis ${label} check failed: ${filePath} (${safeErrorMessage(error)})`);
        return false;
      }
    }
    tempPath = path.join(path.dirname(filePath), `.${path.basename(filePath)}.${process.pid}.${Date.now()}.${Math.random().toString(16).slice(2)}.tmp`);
    await fs.writeFile(tempPath, content, 'utf8');
    await fs.rename(tempPath, filePath);
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis ${label} write skipped: ${filePath} (${safeErrorMessage(error)})`);
    if (tempPath) {
      await fs.rm(tempPath, { force: true }).catch(() => {});
    }
    return false;
  }
}

async function appendMemoryFileBestEffort(filePath, content, label = 'memory file') {
  try {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    try {
      const stat = await fs.stat(filePath);
      if (!stat.isFile()) {
        output && output.appendLine(`Aegis ${label} is not a regular file; leaving it untouched: ${filePath}`);
        return false;
      }
    } catch (error) {
      if (error.code !== 'ENOENT') {
        output && output.appendLine(`Aegis ${label} check failed: ${filePath} (${safeErrorMessage(error)})`);
        return false;
      }
    }
    await fs.appendFile(filePath, content, 'utf8');
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis ${label} append skipped: ${filePath} (${safeErrorMessage(error)})`);
    return false;
  }
}

async function updateWorkspaceMemoryFromSnapshot(target, snapshot) {
  await ensureWorkspaceMemory(target);
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  if (snapshot.coreScan) {
    const data = coreEnvelopeData(snapshot.coreScan);
    pushProgress('Synced with Aegis Core', `Core scan indexed ${data.file_count || snapshot.fileCount || 0} file(s).`);
  }
  const indexSignature = snapshotSignature(snapshot);
  const existingIndex = await readJsonMemoryFile(target, 'file-index.json', null);
  let dependencyGraph = null;
  let symbolIndex = null;
  const canReuseIndexes = existingIndex &&
    existingIndex.indexSignature === indexSignature &&
    existingIndex.indexedRoot === target.root;
  if (canReuseIndexes) {
    dependencyGraph = await readJsonMemoryFile(target, 'dependency-graph.json', null);
    symbolIndex = await readJsonMemoryFile(target, 'symbol-index.json', null);
    if (dependencyGraph && symbolIndex) {
      pushProgress('Using cached index', 'Project files have not changed since the last memory index.');
    }
  }
  if (!dependencyGraph || !symbolIndex) {
    pushProgress('Indexing workspace', 'Updating dependency graph and symbol index for changed project files.');
    dependencyGraph = await buildDependencyGraph(target, snapshot);
    symbolIndex = await buildSymbolIndex(target, snapshot, dependencyGraph);
  }
  const summary = [
    `Updated: ${new Date().toISOString()}`,
    '',
    `Workspace: ${target.root}`,
    '',
    `Files scanned: ${snapshot.fileCount}`,
    `Languages: ${snapshot.languages.length ? snapshot.languages.join(', ') : 'unknown'}`,
    `Frameworks: ${snapshot.frameworks.length ? snapshot.frameworks.join(', ') : 'unknown'}`,
    `Package managers: ${snapshot.packageManagers.length ? snapshot.packageManagers.join(', ') : 'unknown'}`,
    '',
    '## Important Files',
    ...(snapshot.importantFiles.length ? snapshot.importantFiles.map((file) => `- ${file}`) : ['- None detected']),
    '',
    '## Entry Points',
    ...(snapshot.entryPoints.length ? snapshot.entryPoints.map((file) => `- ${file}`) : ['- None detected']),
    '',
    '## Tests',
    ...(snapshot.testFiles.length ? snapshot.testFiles.slice(0, 40).map((file) => `- ${file}`) : ['- None detected']),
    '',
    '## Likely Validation Commands',
    ...(detectValidationCommands(snapshot).length ? detectValidationCommands(snapshot).map((item) => `- ${item.command}`) : ['- None detected'])
  ].join('\n');
  await writeManagedSection(target, 'project-summary.md', 'Aegis Project Summary', summary);

  const architecture = [
    `Updated: ${new Date().toISOString()}`,
    '',
    '## Top-Level Structure',
    ...(snapshot.topLevel.length ? snapshot.topLevel.map((item) => `- ${item}`) : ['- None detected']),
    '',
    '## Languages And Frameworks',
    `- Languages: ${snapshot.languages.length ? snapshot.languages.join(', ') : 'unknown'}`,
    `- Frameworks: ${snapshot.frameworks.length ? snapshot.frameworks.join(', ') : 'unknown'}`,
    '',
    '## Entry Points',
    ...(snapshot.entryPoints.length ? snapshot.entryPoints.map((file) => `- ${file}`) : ['- None detected']),
    '',
    '## Config Files',
    ...(snapshot.configFiles.length ? snapshot.configFiles.slice(0, 50).map((file) => `- ${file}`) : ['- None detected']),
    '',
    '## Repo-Wide Intelligence',
    `- Dependency graph nodes: ${dependencyGraph.nodes.length}`,
    `- Dependency graph edges: ${dependencyGraph.edges.length}`,
    `- Indexed symbols: ${symbolIndex.symbols.length}`,
    `- API/route signals: ${symbolIndex.summary.routes + symbolIndex.summary.apiEndpoints}`,
    `- Component signals: ${symbolIndex.summary.components}`
  ].join('\n');
  await writeManagedSection(target, 'architecture-map.md', 'Aegis Architecture Map', architecture);

  const issues = [
    `Updated: ${new Date().toISOString()}`,
    '',
    '## Diagnostics',
    ...(snapshot.diagnostics.length ? snapshot.diagnostics.slice(0, 40).map((item) => `- ${item.replace(/^- /, '')}`) : ['- None currently reported by VS Code']),
    '',
    '## TODO/FIXME Signals',
    ...(snapshot.todoChunks.length ? snapshot.todoChunks.slice(0, 12).map((item) => `- ${item.replace(/\n/g, '\n  ')}`) : ['- None detected in scanned files'])
  ].join('\n');
  await writeManagedSection(target, 'known-issues.md', 'Aegis Known Issues', issues);

  const roadmapSeed = [
    `Updated: ${new Date().toISOString()}`,
    '',
    '- Keep validation commands passing.',
    '- Address current diagnostics before broad feature work.',
    '- Prefer small file-scoped changes with diff review.'
  ].join('\n');
  await writeManagedSection(target, 'roadmap.md', 'Aegis Detected Next Steps', roadmapSeed);

  const index = {
    version: 1,
    updatedAt: new Date().toISOString(),
    workspace: target.root,
    indexedRoot: target.root,
    indexSignature,
    fileCount: snapshot.fileCount,
    languages: snapshot.languages,
    frameworks: snapshot.frameworks,
    packageManagers: snapshot.packageManagers,
    entryPoints: snapshot.entryPoints,
    importantFiles: snapshot.importantFiles,
    testFiles: snapshot.testFiles,
    configFiles: snapshot.configFiles,
    recentFiles: snapshot.recentFiles,
    files: snapshot.files.map((file) => ({
      path: file.relative,
      size: file.size || 0,
      modified: file.modifiedAt || ''
    }))
  };
  await writeMemoryFileBestEffort(path.join(memoryRoot, 'file-index.json'), JSON.stringify(index, null, 2), 'file index');
  await writeMemoryFileBestEffort(
    path.join(memoryRoot, 'dependency-graph.json'),
    JSON.stringify(dependencyGraph, null, 2),
    'dependency graph'
  );
  await writeMemoryFileBestEffort(path.join(memoryRoot, 'symbol-index.json'), JSON.stringify(symbolIndex, null, 2), 'symbol index');
}

async function buildDependencyGraph(target, snapshot) {
  const root = target.root;
  const sourceFiles = snapshot.files
    .filter((file) => isGraphCandidate(file.relative, file.size || 0))
    .slice(0, MAX_GRAPH_FILES);
  const fileSet = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/')));
  const nodes = [];
  const edges = [];
  const reverseDependencies = {};

  for (const file of sourceFiles) {
    const rel = file.relative.replace(/\\/g, '/');
    const text = await readWorkspaceFile(root, rel);
    const roles = classifyFileRoles(rel, text, snapshot);
    const imports = text ? extractDependencyImports(text, rel) : [];
    const exports = text ? extractExports(text, rel) : [];
    const resolvedImports = [];

    for (const item of imports) {
      const resolved = resolveImportSpecifier(rel, item.specifier, fileSet);
      const importRecord = {
        specifier: item.specifier,
        line: item.line,
        resolved
      };
      resolvedImports.push(importRecord);
      if (resolved) {
        edges.push({
          from: rel,
          to: resolved,
          specifier: item.specifier,
          kind: item.kind || 'import'
        });
        if (!reverseDependencies[resolved]) {
          reverseDependencies[resolved] = [];
        }
        reverseDependencies[resolved].push(rel);
      }
    }

    nodes.push({
      path: rel,
      roles,
      imports: resolvedImports.slice(0, 40),
      exports: exports.slice(0, 40),
      size: file.size || 0,
      modified: file.modifiedAt || ''
    });
  }

  const graph = {
    version: 1,
    updatedAt: new Date().toISOString(),
    workspace: root,
    summary: {
      filesScanned: sourceFiles.length,
      nodes: nodes.length,
      edges: edges.length,
      entryPoints: snapshot.entryPoints.length,
      configFiles: snapshot.configFiles.length,
      testFiles: snapshot.testFiles.length,
      components: nodes.filter((node) => node.roles.component).length,
      routes: nodes.filter((node) => node.roles.route || node.roles.page).length,
      apis: nodes.filter((node) => node.roles.api).length,
      services: nodes.filter((node) => node.roles.service).length
    },
    entryPoints: snapshot.entryPoints,
    configFiles: snapshot.configFiles,
    buildFiles: nodes.filter((node) => node.roles.build).map((node) => node.path),
    testFiles: snapshot.testFiles,
    nodes,
    edges: edges.slice(0, 5000),
    reverseDependencies
  };
  return graph;
}

async function buildSymbolIndex(target, snapshot, dependencyGraph) {
  const root = target.root;
  const sourceFiles = snapshot.files
    .filter((file) => isSymbolCandidate(file.relative, file.size || 0))
    .slice(0, MAX_SYMBOL_FILES);
  const symbols = [];
  const byFile = {};

  for (const file of sourceFiles) {
    const rel = file.relative.replace(/\\/g, '/');
    const text = await readWorkspaceFile(root, rel);
    if (!text) {
      continue;
    }
    const roles = dependencyGraph && Array.isArray(dependencyGraph.nodes)
      ? (dependencyGraph.nodes.find((node) => node.path === rel) || {}).roles || classifyFileRoles(rel, text, snapshot)
      : classifyFileRoles(rel, text, snapshot);
    const fileSymbols = extractSymbols(text, rel, roles).slice(0, 80);
    if (fileSymbols.length) {
      byFile[rel] = fileSymbols.map((symbol) => ({
        kind: symbol.kind,
        name: symbol.name,
        line: symbol.line
      }));
      symbols.push(...fileSymbols);
    }
  }

  const commandSymbols = extractCommandSymbols(snapshot);
  symbols.push(...commandSymbols);

  const limited = symbols.slice(0, MAX_SYMBOLS);
  return {
    version: 1,
    updatedAt: new Date().toISOString(),
    workspace: root,
    summary: summarizeSymbols(limited),
    symbols: limited,
    byFile,
    commands: commandSymbols,
    routes: limited.filter((symbol) => symbol.kind === 'route' || symbol.kind === 'api-endpoint').slice(0, 200),
    components: limited.filter((symbol) => symbol.kind === 'component').slice(0, 200)
  };
}

function isGraphCandidate(relativePath, size) {
  if (size > 512000 || isBlockedRelativePath(relativePath)) {
    return false;
  }
  return isIndexableTextFile(relativePath) || isLikelyConfigFile(relativePath) || isImportantWorkspaceFile(relativePath);
}

function isSymbolCandidate(relativePath, size) {
  if (size > 512000 || isBlockedRelativePath(relativePath)) {
    return false;
  }
  return /\.(js|jsx|ts|tsx|mjs|cjs|py|cs|fs|fsi|fsx|vb|xaml|rs|go|java|cpp|cc|cxx|c|h|hpp)$/i.test(relativePath);
}

function isIndexableTextFile(relativePath) {
  return /\.(js|jsx|ts|tsx|mjs|cjs|py|cs|fs|fsi|fsx|vb|xaml|rs|go|java|cpp|cc|cxx|c|h|hpp|json|jsonc|toml|yaml|yml|md)$/i.test(relativePath);
}

function classifyFileRoles(relativePath, text, snapshot) {
  const normalized = relativePath.replace(/\\/g, '/');
  const lower = normalized.toLowerCase();
  const base = path.basename(normalized);
  const ext = path.extname(normalized).toLowerCase();
  const entryPoints = new Set((snapshot.entryPoints || []).map((item) => item.replace(/\\/g, '/')));
  return {
    entryPoint: entryPoints.has(normalized),
    config: isLikelyConfigFile(normalized),
    build: isLikelyBuildFile(normalized),
    test: isLikelyTestFile(normalized),
    route: /(^|\/)(routes|router|pages|app)\//i.test(normalized) || hasRouteSignals(text),
    page: /(^|\/)(pages|app)\//i.test(normalized) && /\.(jsx|tsx|js|ts|mdx)$/i.test(normalized),
    component: /(^|\/)components?\//i.test(normalized) || ((ext === '.tsx' || ext === '.jsx') && /^[A-Z]/.test(base)),
    api: /(^|\/)(api|apis|controllers?|endpoints?)\//i.test(normalized) || hasApiSignals(text),
    service: /(^|\/)(services?|clients?|repositories?)\//i.test(normalized) || /(?:service|client|repository)\.(ts|tsx|js|jsx|py|cs)$/i.test(base),
    style: /\.(css|scss|sass|less)$/i.test(normalized)
  };
}

function isLikelyBuildFile(relativePath) {
  return _projectScannerModule.isLikelyBuildFile(relativePath);
}

function hasRouteSignals(text) {
  return Boolean(text && /(?:app|router|server)\.(?:get|post|put|patch|delete|options|head)\s*\(/.test(text));
}

function hasApiSignals(text) {
  return Boolean(text && (
    /(?:app|router|server)\.(?:get|post|put|patch|delete|options|head)\s*\(/.test(text) ||
    /@(?:app|router)\.(?:get|post|put|patch|delete)\s*\(/.test(text) ||
    /\bexport\s+async\s+function\s+(?:GET|POST|PUT|PATCH|DELETE)\b/.test(text)
  ));
}

function extractDependencyImports(text, relativePath) {
  const imports = [];
  const patterns = [
    { regex: /import\s+(?:type\s+)?(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g, kind: 'import' },
    { regex: /export\s+[^'"]+\s+from\s+['"]([^'"]+)['"]/g, kind: 'export-from' },
    { regex: /require\(\s*['"]([^'"]+)['"]\s*\)/g, kind: 'require' },
    { regex: /^\s*from\s+([A-Za-z0-9_.$]+)\s+import\s+/gm, kind: 'python-from' },
    { regex: /^\s*import\s+([A-Za-z0-9_.$]+)/gm, kind: 'python-import' },
    { regex: /^\s*#include\s+[<"]([^>"]+)[>"]/gm, kind: 'include' },
    { regex: /^\s*using\s+([A-Za-z0-9_.]+)\s*;/gm, kind: 'using' },
    { regex: /^\s*open\s+([A-Za-z0-9_.]+)\s*$/gm, kind: 'fsharp-open' },
    { regex: /^\s*Imports\s+([A-Za-z0-9_.]+)\s*$/gim, kind: 'vb-imports' }
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      imports.push({
        specifier: match[1],
        kind: pattern.kind,
        line: lineNumberForIndex(text, match.index)
      });
      if (imports.length >= 120) {
        return imports;
      }
    }
  }
  if (/\.py$/i.test(relativePath)) {
    for (const item of imports) {
      if (!item.specifier.startsWith('.') && item.kind.startsWith('python')) {
        item.specifier = item.specifier.replace(/\./g, '/');
      }
    }
  }
  return imports;
}

function extractExports(text, relativePath) {
  const exports = [];
  const patterns = [
    { regex: /\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type)\s+([A-Za-z_$][\w$]*)/g, kind: 'export' },
    { regex: /\bmodule\.exports\s*=\s*([A-Za-z_$][\w$]*)?/g, kind: 'module.exports' },
    { regex: /\bexports\.([A-Za-z_$][\w$]*)\s*=/g, kind: 'exports' },
    { regex: /^\s*(?:def|class)\s+([A-Za-z_][\w]*)/gm, kind: 'python-public' }
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      exports.push({
        name: match[1] || 'default',
        kind: pattern.kind,
        line: lineNumberForIndex(text, match.index)
      });
      if (exports.length >= 80) {
        return exports;
      }
    }
  }
  if (/\.rs$/i.test(relativePath)) {
    let match;
    const rustPattern = /\bpub\s+(?:fn|struct|enum|trait)\s+([A-Za-z_][\w]*)/g;
    while ((match = rustPattern.exec(text)) !== null && exports.length < 80) {
      exports.push({ name: match[1], kind: 'rust-public', line: lineNumberForIndex(text, match.index) });
    }
  }
  return exports;
}

function resolveImportSpecifier(fromFile, specifier, fileSet) {
  if (!specifier) {
    return '';
  }
  if (specifier.startsWith('.')) {
    const dir = path.posix.dirname(fromFile.replace(/\\/g, '/'));
    const base = path.posix.normalize(path.posix.join(dir === '.' ? '' : dir, specifier));
    for (const candidate of importCandidatePaths(base)) {
      if (fileSet.has(candidate)) {
        return candidate;
      }
    }
  }
  if (/^[A-Za-z0-9_./-]+$/.test(specifier)) {
    const candidates = importCandidatePaths(specifier.replace(/\./g, '/'));
    for (const candidate of candidates) {
      if (fileSet.has(candidate)) {
        return candidate;
      }
      if (fileSet.has(`src/${candidate}`)) {
        return `src/${candidate}`;
      }
    }
  }
  return '';
}

function extractSymbols(text, relativePath, roles) {
  const symbols = [];
  const add = (kind, name, index, detail = '') => {
    if (!name || symbols.length >= 120) {
      return;
    }
    symbols.push({
      kind,
      name,
      file: relativePath,
      line: lineNumberForIndex(text, index),
      detail: sanitizeMemoryText(detail || '')
    });
  };
  const patterns = [
    { kind: 'class', regex: /\bclass\s+([A-Za-z_$][\w$]*)/g },
    { kind: 'function', regex: /\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g },
    { kind: 'function', regex: /\b(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>/g },
    { kind: 'interface', regex: /\b(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)/g },
    { kind: 'type', regex: /\b(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=/g },
    { kind: 'config-object', regex: /\b(?:module\.exports|export\s+default|defineConfig|const\s+config)\b/g },
    { kind: 'command', regex: /registerCommand\(\s*['"]([^'"]+)['"]/g }
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      const name = match[1] || pattern.kind;
      const kind = pattern.kind === 'function' && roles.component && /^[A-Z]/.test(name) ? 'component' : pattern.kind;
      add(kind, name, match.index);
    }
  }

  const pyPatterns = [
    { kind: 'class', regex: /^\s*class\s+([A-Za-z_][\w]*)/gm },
    { kind: 'function', regex: /^\s*(?:async\s+)?def\s+([A-Za-z_][\w]*)\s*\(/gm },
    { kind: 'api-endpoint', regex: /^\s*@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]/gm }
  ];
  for (const pattern of pyPatterns) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      add(pattern.kind, pattern.kind === 'api-endpoint' ? `${match[1].toUpperCase()} ${match[2]}` : match[1], match.index);
    }
  }

  const isFSharpFile = /\.(fs|fsi|fsx)$/i.test(relativePath);
  const isVisualBasicFile = /\.vb$/i.test(relativePath);
  const fsharpPatterns = [
    { kind: 'module', regex: /^\s*module\s+([A-Za-z_][\w.]*)/gm },
    { kind: 'type', regex: /^\s*type\s+([A-Za-z_][\w]*)\b/gm },
    { kind: 'function', regex: /^\s*let\s+(?:rec\s+)?([A-Za-z_][\w']*)\b/gm }
  ];
  const visualBasicPatterns = [
    { kind: 'class', regex: /^\s*(?:Public\s+|Private\s+|Friend\s+|Partial\s+)*(?:Class|Module)\s+([A-Za-z_][\w]*)/gim },
    { kind: 'function', regex: /^\s*(?:Public\s+|Private\s+|Friend\s+|Protected\s+|Shared\s+|Async\s+|Overrides\s+)*(?:Sub|Function)\s+([A-Za-z_][\w]*)\b/gim }
  ];
  for (const pattern of isFSharpFile ? fsharpPatterns : []) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      add(pattern.kind, match[1], match.index);
    }
  }
  for (const pattern of isVisualBasicFile ? visualBasicPatterns : []) {
    let match;
    while ((match = pattern.regex.exec(text)) !== null) {
      add(pattern.kind, match[1], match.index);
    }
  }

  const routePattern = /\b(?:app|router|server)\.(get|post|put|patch|delete|options|head)\s*\(\s*['"`]([^'"`]+)['"`]/g;
  let routeMatch;
  while ((routeMatch = routePattern.exec(text)) !== null) {
    add('api-endpoint', `${routeMatch[1].toUpperCase()} ${routeMatch[2]}`, routeMatch.index);
  }

  const nextRoutePattern = /\bexport\s+async\s+function\s+(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b/g;
  let nextMatch;
  while ((nextMatch = nextRoutePattern.exec(text)) !== null) {
    add('api-endpoint', nextMatch[1], nextMatch.index, 'Next.js route handler');
  }

  if (roles.route || roles.page) {
    add(roles.page ? 'route' : 'route', inferRouteNameFromPath(relativePath), 0);
  }
  return symbols;
}

function extractCommandSymbols(snapshot) {
  const symbols = [];
  for (const item of snapshot.importantContents || []) {
    if (path.basename(item.path).toLowerCase() !== 'package.json') {
      continue;
    }
    try {
      const pkg = parseJsonText(item.text);
      const scripts = pkg.scripts || {};
      for (const [name, command] of Object.entries(scripts)) {
        symbols.push({
          kind: 'command',
          name: `npm run ${name}`,
          file: item.path,
          line: 1,
          detail: sanitizeMemoryText(String(command || ''))
        });
      }
    } catch (error) {
      // Package scripts are optional index hints.
    }
  }
  for (const item of detectValidationCommands(snapshot)) {
    symbols.push({
      kind: 'validation-command',
      name: item.command,
      file: item.relativeCwd || '.',
      line: 1,
      detail: 'Detected safe validation command'
    });
  }
  return symbols.slice(0, 120);
}

function summarizeSymbols(symbols) {
  const summary = {
    total: symbols.length,
    classes: 0,
    functions: 0,
    interfaces: 0,
    components: 0,
    routes: 0,
    apiEndpoints: 0,
    commands: 0,
    configObjects: 0
  };
  for (const symbol of symbols) {
    if (symbol.kind === 'class') summary.classes += 1;
    if (symbol.kind === 'function') summary.functions += 1;
    if (symbol.kind === 'interface' || symbol.kind === 'type') summary.interfaces += 1;
    if (symbol.kind === 'component') summary.components += 1;
    if (symbol.kind === 'route') summary.routes += 1;
    if (symbol.kind === 'api-endpoint') summary.apiEndpoints += 1;
    if (symbol.kind === 'command' || symbol.kind === 'validation-command') summary.commands += 1;
    if (symbol.kind === 'config-object') summary.configObjects += 1;
  }
  return summary;
}

function inferRouteNameFromPath(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/');
  return normalized
    .replace(/\.(tsx|ts|jsx|js|mdx)$/i, '')
    .replace(/^src\//, '')
    .replace(/\/(page|route|index)$/, '/')
    .replace(/^app\//, '/')
    .replace(/^pages\//, '/')
    .replace(/\/+/g, '/');
}

function lineNumberForIndex(text, index) {
  return text.slice(0, Math.max(0, index)).split(/\r?\n/).length;
}

async function readJsonMemoryFile(target, name, fallback) {
  try {
    const raw = await fs.readFile(path.join(target.workspaceRoot || target.root, '.aegis', name), 'utf8');
    return parseJsonText(raw);
  } catch (error) {
    return fallback;
  }
}

async function buildImpactAnalysis(target, snapshot, request, dependencyGraph, symbolIndex, options = {}) {
  const graph = dependencyGraph || await readJsonMemoryFile(target, 'dependency-graph.json', null);
  const symbols = symbolIndex || await readJsonMemoryFile(target, 'symbol-index.json', null);
  let seeds = selectRelevantFiles(snapshot, request, {
    validationText: options.validationText || '',
    dependencyGraph: graph,
    symbolIndex: symbols,
    maxFiles: 12
  });
  seeds = expandSelectedFilesWithGraph(graph, seeds, 18);
  const likelyAffected = new Set(seeds);
  const dependents = [];
  if (graph && graph.reverseDependencies) {
    for (const file of seeds) {
      for (const dependent of graph.reverseDependencies[file] || []) {
        likelyAffected.add(dependent);
        dependents.push(dependent);
      }
    }
  }

  const relatedTests = findRelatedTests(snapshot, Array.from(likelyAffected));
  relatedTests.forEach((file) => likelyAffected.add(file));
  const validationCommands = detectValidationCommands(snapshot).map((item) => item.command);
  const breakingPoints = inferBreakingPoints(Array.from(likelyAffected), snapshot, graph, symbols);
  const riskLevel = inferImpactRisk(Array.from(likelyAffected), breakingPoints, graph);
  const stages = buildDefaultStages(Array.from(likelyAffected), relatedTests, riskLevel);

  return {
    generatedAt: new Date().toISOString(),
    workspaceRoot: target.workspaceRoot || target.root,
    targetRoot: target.root,
    request: sanitizeMemoryText(request || ''),
    likelyAffectedFiles: Array.from(likelyAffected).slice(0, 40),
    directlyRelevantFiles: seeds.slice(0, 18),
    relatedTests: relatedTests.slice(0, 20),
    relatedValidation: validationCommands,
    riskLevel,
    possibleBreakingPoints: breakingPoints.slice(0, 12),
    rollbackPlan: 'Aegis creates a snapshot under .aegis/backups before approved edits. Use "Aegis: Rollback Last Agent Change" or the sidebar rollback button to restore the last applied agent change.',
    stagedPlan: stages,
    dependencyNotes: summarizeGraphImpact(graph, seeds)
  };
}

function findRelatedTests(snapshot, files) {
  const allTests = new Set(snapshot.testFiles || []);
  const results = new Set();
  const normalizedFiles = files.map((file) => file.replace(/\\/g, '/'));
  for (const file of normalizedFiles) {
    const dir = path.posix.dirname(file);
    const parts = file.split('/');
    const base = path.posix.basename(file, path.posix.extname(file)).replace(/\.(test|spec)$/i, '').toLowerCase();
    for (const test of allTests) {
      const normalizedTest = test.replace(/\\/g, '/');
      const testBase = path.posix.basename(normalizedTest, path.posix.extname(normalizedTest)).toLowerCase();
      const mirrorsPath = parts.length > 1 && normalizedTest.toLowerCase().includes(parts.slice(-2).join('/').toLowerCase().replace(path.posix.extname(file).toLowerCase(), ''));
      const sameFeature = dir !== '.' && normalizedTest.startsWith(`${dir}/`);
      const siblingTest = testBase.includes(base) || base.includes(testBase.replace(/\.(test|spec)$/i, ''));
      if (siblingTest || sameFeature || mirrorsPath) {
        results.add(normalizedTest);
      }
    }
  }
  return Array.from(results).slice(0, 30);
}

function inferBreakingPoints(files, snapshot, graph, symbolIndex) {
  const points = new Set();
  const configSet = new Set((snapshot.configFiles || []).map((file) => file.replace(/\\/g, '/')));
  const entrySet = new Set((snapshot.entryPoints || []).map((file) => file.replace(/\\/g, '/')));
  const testSet = new Set((snapshot.testFiles || []).map((file) => file.replace(/\\/g, '/')));
  for (const file of files) {
    if (configSet.has(file) || isLikelyBuildFile(file)) points.add('Build/config changes can affect the whole workspace.');
    if (entrySet.has(file)) points.add('Entry point changes can affect startup behavior.');
    if (testSet.has(file)) points.add('Test changes can hide or reveal regressions.');
  }
  if (graph && Array.isArray(graph.nodes)) {
    for (const file of files) {
      const node = graph.nodes.find((item) => item.path === file);
      if (!node) continue;
      if (node.roles && node.roles.api) points.add('API/service changes may break callers or route contracts.');
      if (node.roles && node.roles.component) points.add('Component changes may affect UI rendering and props.');
      if (node.exports && node.exports.length) points.add('Exported symbols may have downstream dependents.');
      if (graph.reverseDependencies && (graph.reverseDependencies[file] || []).length > 3) {
        points.add('One or more files has several reverse dependencies.');
      }
    }
  }
  if (symbolIndex && Array.isArray(symbolIndex.symbols)) {
    const touchedSymbols = symbolIndex.symbols.filter((symbol) => files.includes(symbol.file));
    if (touchedSymbols.some((symbol) => symbol.kind === 'api-endpoint' || symbol.kind === 'route')) {
      points.add('Route/API endpoint behavior may change.');
    }
    if (touchedSymbols.some((symbol) => symbol.kind === 'command' || symbol.kind === 'validation-command')) {
      points.add('Command/config behavior may change.');
    }
  }
  if (!findRelatedTests(snapshot, files).length) {
    points.add('No nearby tests were detected for the likely affected files.');
  }
  return Array.from(points);
}

function inferImpactRisk(files, breakingPoints, graph) {
  if (files.length > 12 || breakingPoints.length >= 4) {
    return 'high';
  }
  if (files.length > 5 || breakingPoints.length >= 2) {
    return 'medium';
  }
  if (graph && Array.isArray(graph.edges) && files.some((file) => (graph.reverseDependencies && (graph.reverseDependencies[file] || []).length > 4))) {
    return 'medium';
  }
  return 'low';
}

function buildDefaultStages(files, relatedTests, riskLevel) {
  const unique = Array.from(new Set(files.map((file) => file.replace(/\\/g, '/'))));
  const tests = new Set(relatedTests || []);
  const docs = unique.filter((file) => /\.(md|txt)$/i.test(file));
  const configs = unique.filter((file) => isLikelyConfigFile(file) || isLikelyBuildFile(file));
  const testFiles = unique.filter((file) => tests.has(file) || isLikelyTestFile(file));
  const implementation = unique.filter((file) => !docs.includes(file) && !configs.includes(file) && !testFiles.includes(file));
  return [
    {
      name: 'Stage 1: architecture/prep',
      goal: 'Adjust configuration, contracts, or scaffolding needed before implementation.',
      files: configs.slice(0, 12),
      risk: configs.length ? riskLevel : 'low',
      approvalRequired: true
    },
    {
      name: 'Stage 2: implementation',
      goal: 'Make the main code changes in the smallest coherent set of files.',
      files: implementation.slice(0, 20),
      risk: riskLevel,
      approvalRequired: true
    },
    {
      name: 'Stage 3: tests/validation',
      goal: 'Update or add tests and run detected validation commands.',
      files: testFiles.slice(0, 16),
      risk: testFiles.length ? 'medium' : 'low',
      approvalRequired: true
    },
    {
      name: 'Stage 4: cleanup/docs',
      goal: 'Update docs, TODOs, or cleanup notes after code and validation are stable.',
      files: docs.slice(0, 12),
      risk: 'low',
      approvalRequired: true
    }
  ];
}

function normalizeModelImpactAnalysis(value) {
  return _proposalParserModule.normalizeModelImpactAnalysis(value);
}

function normalizeConfidenceScore(value) {
  return _proposalSafetyModule.normalizeConfidenceScore(value);
}

function normalizeModelStages(value) {
  return _proposalParserModule.normalizeModelStages(value);
}

function normalizeProposalStages(proposal, impactAnalysis) {
  return _proposalParserModule.normalizeProposalStages(proposal, impactAnalysis);
}

function enrichProposalWithRepoIntelligence(proposal, impactAnalysis) {
  const normalizedImpact = Object.assign({}, impactAnalysis || {}, proposal.impactAnalysis || {});
  if (impactAnalysis && proposal.impactAnalysis) {
    normalizedImpact.likelyAffectedFiles = Array.from(new Set([
      ...(impactAnalysis.likelyAffectedFiles || []),
      ...(proposal.impactAnalysis.likelyAffectedFiles || [])
    ])).slice(0, 40);
    normalizedImpact.relatedValidation = Array.from(new Set([
      ...(impactAnalysis.relatedValidation || []),
      ...(proposal.impactAnalysis.relatedValidation || [])
    ])).slice(0, 10);
    normalizedImpact.possibleBreakingPoints = Array.from(new Set([
      ...(impactAnalysis.possibleBreakingPoints || []),
      ...(proposal.impactAnalysis.possibleBreakingPoints || [])
    ])).slice(0, 12);
    normalizedImpact.riskLevel = proposal.impactAnalysis.riskLevel || impactAnalysis.riskLevel;
    normalizedImpact.rollbackPlan = proposal.impactAnalysis.rollbackPlan || impactAnalysis.rollbackPlan;
  }
  proposal.impactAnalysis = normalizedImpact;
  proposal.stages = normalizeProposalStages(proposal, normalizedImpact);
  lastImpactAnalysis = normalizedImpact;
  return proposal;
}

function impactAnalysisToLines(impact) {
  if (!impact) {
    return ['- Not available yet.'];
  }
  const lines = [];
  lines.push(`- Risk level: ${impact.riskLevel || impact.risk || 'unknown'}`);
  if (impact.likelyAffectedFiles && impact.likelyAffectedFiles.length) {
    lines.push(`- Likely affected: ${impact.likelyAffectedFiles.slice(0, 12).join(', ')}`);
  }
  if (impact.relatedTests && impact.relatedTests.length) {
    lines.push(`- Related tests: ${impact.relatedTests.slice(0, 8).join(', ')}`);
  }
  if (impact.relatedValidation && impact.relatedValidation.length) {
    lines.push(`- Validation: ${impact.relatedValidation.join(', ')}`);
  }
  if (impact.possibleBreakingPoints && impact.possibleBreakingPoints.length) {
    lines.push(`- Breaking points: ${impact.possibleBreakingPoints.slice(0, 4).join('; ')}`);
  }
  if (impact.rollbackPlan) {
    lines.push(`- Rollback: ${impact.rollbackPlan}`);
  }
  return lines;
}

function impactAnalysisToPlanText(impact) {
  return ['Impact analysis before proposing changes:', ...impactAnalysisToLines(impact)].join('\n');
}

function formatImpactAnalysisContext(impact) {
  return [
    '# Impact Analysis',
    ...impactAnalysisToLines(impact),
    impact && impact.stagedPlan && impact.stagedPlan.length
      ? `# Suggested Stages\n${impact.stagedPlan.map((stage, index) => `${index + 1}. ${stage.name}: ${stage.goal}\nFiles: ${(stage.files || []).join(', ') || 'none detected yet'}`).join('\n')}`
      : ''
  ].filter(Boolean).join('\n');
}

function formatDependencyGraphContext(graph, selectedFiles) {
  if (!graph || !Array.isArray(graph.nodes)) {
    return '';
  }
  const selected = new Set(selectedFiles || []);
  const rows = [];
  for (const node of graph.nodes) {
    if (!selected.has(node.path)) {
      continue;
    }
    const roles = Object.entries(node.roles || {}).filter(([, value]) => value).map(([key]) => key).join(', ') || 'source';
    const imports = (node.imports || []).filter((item) => item.resolved).slice(0, 8).map((item) => item.resolved).join(', ');
    const dependents = (graph.reverseDependencies && graph.reverseDependencies[node.path] || []).slice(0, 8).join(', ');
    rows.push(`- ${node.path} [${roles}] imports: ${imports || 'none'} dependents: ${dependents || 'none'}`);
  }
  return rows.length ? `# Dependency Graph Focus\n${rows.join('\n')}` : '';
}

function formatSymbolIndexContext(symbolIndex, selectedFiles) {
  if (!symbolIndex || !Array.isArray(symbolIndex.symbols)) {
    return '';
  }
  const selected = new Set(selectedFiles || []);
  const rows = symbolIndex.symbols
    .filter((symbol) => selected.has(symbol.file))
    .slice(0, 80)
    .map((symbol) => `- ${symbol.file}:${symbol.line} ${symbol.kind} ${symbol.name}`);
  return rows.length ? `# Related Symbols\n${rows.join('\n')}` : '';
}

function summarizeGraphImpact(graph, seedFiles) {
  if (!graph || !Array.isArray(graph.edges)) {
    return [];
  }
  const rows = [];
  for (const file of seedFiles.slice(0, 8)) {
    const imports = graph.edges.filter((edge) => edge.from === file).slice(0, 5).map((edge) => edge.to);
    const dependents = graph.reverseDependencies && graph.reverseDependencies[file] ? graph.reverseDependencies[file].slice(0, 5) : [];
    rows.push({
      file,
      imports,
      dependents
    });
  }
  return rows;
}

async function buildDependencyGraphSummary(target) {
  const graph = await readJsonMemoryFile(target, 'dependency-graph.json', null);
  const symbols = await readJsonMemoryFile(target, 'symbol-index.json', null);
  if (!graph || !graph.summary) {
    return emptyDependencyGraphSummary();
  }
  return {
    nodes: graph.summary.nodes || 0,
    edges: graph.summary.edges || 0,
    entryPoints: graph.summary.entryPoints || 0,
    tests: graph.summary.testFiles || 0,
    configs: graph.summary.configFiles || 0,
    routes: graph.summary.routes || 0,
    apis: graph.summary.apis || 0,
    services: graph.summary.services || 0,
    components: graph.summary.components || 0,
    symbols: symbols && symbols.summary ? symbols.summary.total || 0 : 0,
    updatedAt: graph.updatedAt || ''
  };
}

function emptyDependencyGraphSummary() {
  return {
    nodes: 0,
    edges: 0,
    entryPoints: 0,
    tests: 0,
    configs: 0,
    routes: 0,
    apis: 0,
    services: 0,
    components: 0,
    symbols: 0,
    updatedAt: ''
  };
}

async function readWorkspaceMemoryContext(target) {
  try {
    const envelope = await getAegisCoreMemory(target);
    const data = coreEnvelopeData(envelope);
    const entries = data.entries && typeof data.entries === 'object' ? data.entries : {};
    const pieces = [];
    for (const name of ['project_summary', 'architecture_map', 'roadmap', 'decisions', 'known_issues']) {
      const entry = entries[name];
      if (entry && entry.excerpt) {
        pieces.push(formatFileChunk(`Core memory:${name}`, sanitizeMemoryText(String(entry.excerpt))));
      }
    }
    if (pieces.length) {
      return truncateMiddle(pieces.join('\n\n'), 24000);
    }
  } catch (error) {
    output && output.appendLine(`Aegis Core memory unavailable; using local .aegis memory fallback: ${safeErrorMessage(error)}`);
  }

  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  const pieces = [];
  for (const name of ['project-summary.md', 'architecture-map.md', 'roadmap.md', 'decisions.md', 'known-issues.md']) {
    try {
      const text = await fs.readFile(path.join(memoryRoot, name), 'utf8');
      pieces.push(formatFileChunk(`.aegis/${name}`, sanitizeMemoryText(text)));
    } catch (error) {
      // Missing memory files are fine; ensureWorkspaceMemory creates them during agent runs.
    }
  }
  return truncateMiddle(pieces.join('\n\n'), 24000);
}

function snapshotSignature(snapshot) {
  const parts = [
    snapshot.fileCount,
    snapshot.directoryCount,
    ...(snapshot.recentFiles || []).slice(0, 80).map((item) => `${item.path}:${item.modified}:${item.size}`),
    ...(snapshot.importantFiles || []).slice(0, 80),
    ...(snapshot.configFiles || []).slice(0, 80)
  ];
  return simpleHash(parts.join('|'));
}

function simpleHash(text) {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16);
}

function sanitizeMemoryText(text) {
  return text
    .split(/\r?\n/)
    .filter((line) => !/(x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|secret|token|password|passwd|credential|authorization|auth|private[_-]?key)/i.test(line))
    .join('\n');
}

async function appendAgentHistory(target, event) {
  await ensureWorkspaceMemory(target);
  const historyPath = path.join(target.workspaceRoot || target.root, '.aegis', 'agent-history.json');
  let history = [];
  try {
    history = parseJsonText(await fs.readFile(historyPath, 'utf8'));
    if (!Array.isArray(history)) {
      history = [];
    }
  } catch (error) {
    history = [];
  }
  history.push(sanitizeHistoryEvent(Object.assign({ at: new Date().toISOString() }, event)));
  history = history.slice(-100);
  await writeMemoryFileBestEffort(historyPath, JSON.stringify(history, null, 2), 'agent history');
}

function sanitizeHistoryEvent(value) {
  if (typeof value === 'string') {
    return sanitizeMemoryText(value);
  }
  if (Array.isArray(value)) {
    return value.map(sanitizeHistoryEvent);
  }
  if (value && typeof value === 'object') {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      result[key] = sanitizeHistoryEvent(item);
    }
    return result;
  }
  return value;
}

async function recordValidationResult(target, validation) {
  await ensureWorkspaceMemory(target);
  const logPath = path.join(target.workspaceRoot || target.root, '.aegis', 'validation-log.md');
  const entry = [
    `## ${new Date().toISOString()} - ${validation.success ? 'PASS' : 'FAIL'}`,
    '',
    ...validation.commands.map((item) => `- \`${item.command}\`: ${item.success ? 'PASS' : 'FAIL'} (${item.exitCode === null ? 'no exit code' : `exit ${item.exitCode}`})`),
    '',
    '```text',
    truncateMiddle(sanitizeMemoryText(validation.output || 'No validation output.'), 12000),
    '```',
    ''
  ].join('\n');
  await appendMemoryFileBestEffort(logPath, entry, 'validation log');
}

async function appendDecisionRecord(target, proposal, validation, nextRecommendation) {
  await ensureWorkspaceMemory(target);
  const decisionsPath = path.join(target.workspaceRoot || target.root, '.aegis', 'decisions.md');
  const files = Array.isArray(proposal.fileEdits) ? proposal.fileEdits.map((edit) => edit.path) : [];
  const reasons = Array.isArray(proposal.fileEdits)
    ? proposal.fileEdits.map((edit) => edit.reason).filter(Boolean)
    : [];
  const entry = [
    '',
    `## ${new Date().toISOString()} - ${sanitizeMemoryText(proposal.summary || 'Agent change')}`,
    '',
    `- What changed: ${sanitizeMemoryText(proposal.summary || 'Applied an agent proposal.')}`,
    `- Why: ${sanitizeMemoryText(reasons.join('; ') || (proposal.notes || []).join('; ') || 'Requested by the local agent workflow.')}`,
    `- Affected files: ${files.length ? files.map((file) => `\`${file}\``).join(', ') : 'None'}`,
    `- Validation result: ${validation.skipped ? 'Skipped' : (validation.success ? 'Passed' : 'Failed')}`,
    `- Validation commands: ${validation.commands.length ? validation.commands.map((item) => `\`${item.command}\``).join(', ') : 'None detected'}`,
    `- Next recommendation: ${sanitizeMemoryText(nextRecommendation || 'Review roadmap and continue with a small validated task.')}`,
    ''
  ].join('\n');
  await appendMemoryFileBestEffort(decisionsPath, entry, 'decisions log');
}

function memoryFileNames() {
  return [
    'project-summary.md',
    'roadmap.md',
    'architecture-map.md',
    'known-issues.md',
    'real-world-testing.md',
    'decisions.md',
    'validation-log.md',
    'extension-log.md',
    'dependency-graph.json',
    'symbol-index.json',
    'change-history.json'
  ];
}

function proposalStateSnapshot() {
  if (!lastProposal) {
    return {
      summary: '',
      risk: '',
      confidenceScore: 0,
      approachRationale: '',
      files: [],
      notes: [],
      approvalStatus: 'none'
    };
  }
  return {
    summary: lastProposal.summary || '',
    risk: lastProposal.risk || '',
    confidenceScore: normalizeConfidenceScore(lastProposal.confidenceScore),
    approachRationale: lastProposal.approachRationale || '',
    files: (lastProposal.fileEdits || []).map((edit, index) => ({
      index,
      path: edit.path,
      reason: edit.reason || '',
      chars: typeof edit.content === 'string' ? edit.content.length : 0
    })),
    destinationReasoning: Array.isArray(lastProposal.destinationReasoning) ? lastProposal.destinationReasoning.slice(0, 30) : [],
    notes: Array.isArray(lastProposal.notes) ? lastProposal.notes.slice(0, 8) : [],
    impactAnalysis: lastProposal.impactAnalysis || lastImpactAnalysis || null,
    stages: Array.isArray(lastProposal.stages) ? lastProposal.stages : [],
    coreProposalId: lastProposal.coreProposalId || '',
    coreJobId: lastProposal.coreJobId || '',
    corePreview: Array.isArray(lastProposal.corePreview) ? lastProposal.corePreview : [],
    approvalStatus: lastProposal.fileEdits && lastProposal.fileEdits.length ? 'pending' : 'plan-only'
  };
}

function impactAnalysisStateSnapshot(target) {
  const impact = lastImpactAnalysis;
  if (!impact) {
    return {
      riskLevel: '',
      likelyAffectedFiles: [],
      relatedTests: [],
      relatedValidation: [],
      possibleBreakingPoints: [],
      rollbackPlan: ''
    };
  }
  if (target && impact.workspaceRoot && path.resolve(impact.workspaceRoot) !== path.resolve(target.workspaceRoot || target.root)) {
    return {
      riskLevel: '',
      likelyAffectedFiles: [],
      relatedTests: [],
      relatedValidation: [],
      possibleBreakingPoints: [],
      rollbackPlan: ''
    };
  }
  return {
    riskLevel: impact.riskLevel || impact.risk || '',
    likelyAffectedFiles: Array.isArray(impact.likelyAffectedFiles) ? impact.likelyAffectedFiles.slice(0, 18) : [],
    relatedTests: Array.isArray(impact.relatedTests) ? impact.relatedTests.slice(0, 12) : [],
    relatedValidation: Array.isArray(impact.relatedValidation) ? impact.relatedValidation.slice(0, 8) : [],
    possibleBreakingPoints: Array.isArray(impact.possibleBreakingPoints) ? impact.possibleBreakingPoints.slice(0, 8) : [],
    rollbackPlan: impact.rollbackPlan || ''
  };
}

function stagedPlanStateSnapshot() {
  const stages = lastProposal && Array.isArray(lastProposal.stages) ? lastProposal.stages : [];
  return stages.map((stage, index) => ({
    index: index + 1,
    name: stage.name || stage.title || `Stage ${index + 1}`,
    goal: stage.goal || '',
    files: Array.isArray(stage.files) ? stage.files.slice(0, 16) : [],
    risk: stage.risk || '',
    approvalRequired: stage.approvalRequired !== false
  }));
}

function stageToPlanText(stage, index, total, proposal) {
  return [
    proposal.summary || 'Aegis staged proposal',
    '',
    `Stage ${index + 1} of ${total}: ${stage.name || stage.title || 'Stage'}`,
    `Goal: ${stage.goal || 'Apply a focused set of approved changes.'}`,
    `Risk: ${stage.risk || proposal.risk || 'medium'}`,
    '',
    'Files in this stage:',
    ...((stage.files || []).length ? stage.files.map((file) => `- ${file}`) : ['- No files listed'])
  ].join('\n');
}

function emptyProjectOverview() {
  return {
    workspaceName: 'No workspace',
    workspacePath: '',
    languages: [],
    frameworks: [],
    commands: [],
    activeModel: getConfig().chatModel,
    health: 'No folder open',
    lastValidation: 'No validation yet'
  };
}

async function buildProjectOverviewState(target, snapshot, models) {
  const lastValidation = await readLastValidationResult(target);
  const commandItems = detectValidationCommands(snapshot).map((item) => item.relativeCwd ? `${item.command} (${item.relativeCwd})` : item.command);
  const hasModel = models.some((model) => (model.name || model.model) === getConfig().chatModel);
  const health = lastValidation.includes('FAIL')
    ? 'Needs attention'
    : (lastValidation.includes('PASS') ? 'Healthy' : (snapshot.diagnostics.length ? 'Diagnostics present' : 'Ready'));
  return {
    workspaceName: target.label || target.workspaceFolderName,
    workspacePath: target.root,
    languages: snapshot.languages,
    frameworks: snapshot.frameworks,
    commands: commandItems,
    activeModel: getConfig().chatModel,
    modelReady: hasModel,
    health,
    lastValidation
  };
}

async function readLastValidationResult(target) {
  const text = await readMemoryFile(target, 'validation-log.md');
  if (!text.trim()) {
    return 'No validation yet';
  }
  const headings = text.match(/^## .+$/gm);
  return headings && headings.length ? headings[headings.length - 1].replace(/^##\s*/, '') : 'Validation log exists';
}

async function approveProposalFromPanel(indexes) {
  if (!lastProposal) {
    vscode.window.showWarningMessage('No proposal is pending.');
    return;
  }
  if (Array.isArray(indexes) && indexes.length === 0) {
    vscode.window.showWarningMessage('Select at least one proposed file change first.');
    return;
  }
  if (Array.isArray(indexes) && indexes.length) {
    const selected = new Set(indexes.map((item) => Number(item)));
    const subset = Object.assign({}, lastProposal, {
      fileEdits: (lastProposal.fileEdits || []).filter((_, index) => selected.has(index))
    });
    const applied = await applyProposal(subset);
    if (applied) {
      const remainingEdits = (lastProposal.fileEdits || []).filter((_, index) => !selected.has(index));
      if (remainingEdits.length) {
        lastProposal = Object.assign({}, lastProposal, { fileEdits: remainingEdits });
        try {
          const snapTarget = {
            root: lastProposal.targetRoot || lastProposal.workspace,
            workspaceRoot: lastProposal.workspaceRoot || lastProposal.workspace,
            label: lastProposal.targetLabel || ''
          };
          attachDestinationReasoning(lastProposal, await getProjectSnapshot(snapTarget, { fast: true }), snapTarget);
        } catch (error) {
          output && output.appendLine(`Destination reasoning refresh skipped: ${safeErrorMessage(error)}`);
        }
      } else {
        lastProposal = undefined;
      }
      vscode.window.showInformationMessage(`Applied ${subset.fileEdits.length} selected change(s).`);
    }
  } else {
    await applyProposal(lastProposal);
  }
}

async function rejectProposalFromPanel() {
  if (!lastProposal) {
    vscode.window.showInformationMessage('No proposal is pending.');
    return;
  }
  await appendAgentHistory({ workspaceRoot: lastProposal.workspaceRoot || lastProposal.workspace || lastProposal.targetRoot, root: lastProposal.workspace || lastProposal.targetRoot }, {
    type: 'proposal-rejected',
    summary: lastProposal.summary || ''
  }).catch(() => {});
  if (activeCoreTaskId) {
    await updateAegisCoreTaskStatus(
      { workspaceRoot: lastProposal.workspaceRoot || lastProposal.workspace || lastProposal.targetRoot, root: lastProposal.workspace || lastProposal.targetRoot },
      activeCoreTaskId,
      'cancelled',
      'Proposal rejected in VS Code.'
    );
    activeCoreTaskId = '';
  }
  if (activeCoreWorkflowId) {
    await getWorkflowRuntimeClient().cancel(
      { workspaceRoot: lastProposal.workspaceRoot || lastProposal.workspace || lastProposal.targetRoot, root: lastProposal.workspace || lastProposal.targetRoot },
      activeCoreWorkflowId,
      'Proposal rejected in VS Code.'
    ).catch(() => {});
    recordRuntimeOperation('workflow', 'core', 'cancelled', 'Proposal rejection cancelled the active Core workflow.', {
      workflowId: activeCoreWorkflowId
    });
    activeCoreWorkflowId = '';
  }
  lastProposal = undefined;
  runtimeState.setPendingProposal(null);
  updateAgentState({ pendingDiffs: [], activePlan: 'Proposal rejected.', status: 'Rejected' });
  panelProvider && panelProvider.refresh();
}

async function regeneratePlanFromPanel() {
  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before regenerating a plan.');
    return;
  }
  await runAgentMode(lastAgentRequest || 'Regenerate a safe plan for the current project.', target);
}

async function openMemoryFromPanel(name) {
  if (!memoryFileNames().includes(name)) {
    vscode.window.showWarningMessage('Unknown Aegis memory file.');
    return;
  }
  const target = await resolveWorkspaceTarget();
  if (!target) {
    vscode.window.showWarningMessage('Open a project folder before opening memory.');
    return;
  }
  await ensureWorkspaceMemory(target);
  await openMemoryDocument(target, name);
}

async function saveSettingsFromPanel(settings) {
  const config = vscode.workspace.getConfiguration('aegisLocalAutopilot');
  const writeMode = settings.autopilotWriteMode === 'apply' ? 'apply' : settings.autopilotWriteMode === 'preview' ? 'preview' : undefined;
  const updates = [
    ['ollamaUrl', normalizeHttpBaseUrl(settings.ollamaUrl, 'http://127.0.0.1:11434')],
    ['coreUrl', normalizeHttpBaseUrl(settings.coreUrl, 'http://127.0.0.1:8788')],
    ['chatModel', typeof settings.chatModel === 'string' ? settings.chatModel.trim() : undefined],
    ['fastModel', typeof settings.fastModel === 'string' ? settings.fastModel.trim() : undefined],
    ['fallbackModels', typeof settings.fallbackModels === 'string' ? settings.fallbackModels.split(',').map((item) => item.trim()).filter(Boolean) : settings.fallbackModels],
    ['maxContextChars', boundedConfigInt(settings.maxContextChars, 16000, 200000, undefined)],
    ['maxContextFiles', boundedConfigInt(settings.maxContextFiles, 3, 40, undefined)],
    ['maxProposalDiffTabs', boundedConfigInt(settings.maxProposalDiffTabs, 1, 25, undefined)],
    ['autopilotIntervalMinutes', boundedConfigInt(settings.autopilotIntervalMinutes, 2, 1440, undefined)],
    ['autopilotWriteMode', writeMode],
    ['excludeGlob', typeof settings.excludeGlob === 'string' && settings.excludeGlob.trim() ? settings.excludeGlob.trim() : undefined],
    ['autoScanOnOpen', typeof settings.autoScanOnOpen === 'boolean' ? settings.autoScanOnOpen : undefined],
    ['validationCommandPreferences', Array.isArray(settings.validationCommandPreferences) ? settings.validationCommandPreferences : String(settings.validationCommandPreferences || '').split(',').map((item) => item.trim()).filter(Boolean)],
    ['safetyMode', settings.safetyMode === 'standard' || settings.safetyMode === 'strict' || settings.safetyMode === 'review-only' ? settings.safetyMode : undefined]
  ];
  for (const [key, value] of updates) {
    if (value === undefined) {
      continue;
    }
    if (typeof value === 'boolean' || Array.isArray(value)) {
      await config.update(key, value, vscode.ConfigurationTarget.Workspace);
      continue;
    }
    if (value !== '') {
      await config.update(key, value, vscode.ConfigurationTarget.Workspace);
    }
  }
  vscode.window.showInformationMessage('Aegis Local Agent settings saved.');
}

function detectValidationCommands(snapshot) {
  return _validationDetectorModule.detectValidationCommands(snapshot);
}

function pickPackageManagerForPath(snapshot, packagePath) {
  return _validationDetectorModule.pickPackageManagerForPath(snapshot, packagePath);
}

function pickPackageManagerFromNames(names, packagePath) {
  return _validationDetectorModule.pickPackageManagerFromNames(names, packagePath);
}

function normalizePackageManagerName(value) {
  return _validationDetectorModule.normalizePackageManagerName(value);
}

function packageScriptCommand(packageManager, script) {
  return _validationDetectorModule.packageScriptCommand(packageManager, script);
}

function makeValidationCommand(command, cwd, relativeCwd) {
  return { command, cwd, relativeCwd };
}

function isSafeValidationCommand(command) {
  return _validationDetectorModule.isSafeValidationCommand(command);
}

async function runDetectedValidation(target, snapshot) {
  const resolvedSnapshot = snapshot || await getProjectSnapshot(target, { fast: true });
  try {
    const coreValidation = await runAegisCoreValidation(target);
    if (coreValidation) {
      updateAgentState({ validationOutput: coreValidation.output });
      return coreValidation;
    }
  } catch (error) {
    output && output.appendLine(`Aegis Core validation unavailable; using VS Code local validation fallback: ${safeErrorMessage(error)}`);
    recordCoreDisconnected(error, 'validation');
  }

  const commands = detectValidationCommands(resolvedSnapshot);
  if (!commands.length) {
    const result = {
      success: true,
      skipped: true,
      commands: [],
      output: 'No project validation command was detected.'
    };
    updateAgentState({ status: 'Validation skipped', validationOutput: result.output });
    return result;
  }

  updateAgentState({
    status: 'Running validation',
    validationOutput: commands.map((item) => `$ ${item.command}${item.relativeCwd ? ` (cwd: ${item.relativeCwd})` : ''}`).join('\n')
  });

  const results = [];
  for (const item of commands) {
    const result = await runValidationCommand(item);
    results.push(result);
    const aggregate = validationResultsToOutput(results);
    updateAgentState({ validationOutput: aggregate });
    if (!result.success) {
      break;
    }
  }

  const localValidation = {
    success: results.every((item) => item.success),
    skipped: false,
    commands: results,
    output: validationResultsToOutput(results)
  };
  runtimeState.setLatestValidation(localValidation);
  recordRuntimeOperation('validation', 'local', localValidation.success ? 'completed' : 'failed', localValidation.success ? 'Local validation passed.' : 'Local validation failed.', {
    workflowId: activeCoreWorkflowId || ''
  });
  return localValidation;
}

function runValidationCommand(item) {
  return new Promise((resolve) => {
    if (!isSafeValidationCommand(item.command)) {
      lastFailedCommand = item.command;
      logExtensionEvent('validation', `Blocked unsafe validation command: ${item.command}`, { cwd: item.cwd }).catch(() => {});
      resolve({
        command: item.command,
        cwd: item.cwd,
        success: false,
        exitCode: null,
        output: `Blocked unsafe validation command: ${item.command}`
      });
      return;
    }

    logExtensionEvent('validation', `Running validation command: ${item.command}`, {
      cwd: item.cwd,
      relativeCwd: item.relativeCwd || ''
    }).catch(() => {});
    cp.exec(item.command, {
      cwd: item.cwd,
      timeout: 5 * 60 * 1000,
      maxBuffer: 1024 * 1024 * 4,
      windowsHide: true
    }, (error, stdout, stderr) => {
      const outputText = [stdout, stderr].filter(Boolean).join('\n');
      resolve({
        command: item.command,
        cwd: item.cwd,
        success: !error,
        exitCode: error && typeof error.code === 'number' ? error.code : (error ? null : 0),
        output: truncateMiddle(outputText || (error ? safeErrorMessage(error) : 'No output.'), 24000)
      });
      if (error) {
        lastFailedCommand = item.command;
      }
      logExtensionEvent('validation', `Validation command finished: ${item.command}`, {
        success: !error,
        exitCode: error && typeof error.code === 'number' ? error.code : (error ? null : 0)
      }).catch(() => {});
    });
  });
}

function validationResultsToOutput(results) {
  return results.map((result) => [
    `$ ${result.command}`,
    `Status: ${result.success ? 'PASS' : 'FAIL'}${result.exitCode === null ? '' : ` (exit ${result.exitCode})`}`,
    result.output
  ].join('\n')).join('\n\n');
}

function summarizeValidation(validation) {
  return _validationDetectorModule.summarizeValidation(validation);
}

function classifyValidationFailure(validation) {
  return _validationDetectorModule.classifyValidationFailure(validation);
}

function isWorkspaceTarget(value) {
  return _workspaceResolverModule.isWorkspaceTarget(value);
}

async function resolveWorkspaceTarget(resource, options = {}) {
  const resourceUri = extractResourceUri(resource);
  if (resourceUri && resourceUri.scheme === 'file') {
    return targetFromUri(resourceUri);
  }

  const folders = vscode.workspace.workspaceFolders || [];
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const editorFolder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
    if (editorFolder) {
      return makeWorkspaceTarget(editorFolder.uri.fsPath, editorFolder);
    }
  }

  if (folders.length === 1) {
    return makeWorkspaceTarget(folders[0].uri.fsPath, folders[0]);
  }

  if (folders.length > 1) {
    if (options.silent) {
      return makeWorkspaceTarget(folders[0].uri.fsPath, folders[0]);
    }
    const picked = await vscode.window.showQuickPick(
      folders.map((folder) => ({
        label: folder.name,
        description: folder.uri.fsPath,
        folder
      })),
      { title: 'Choose the folder Aegis should work from' }
    );
    return picked ? makeWorkspaceTarget(picked.folder.uri.fsPath, picked.folder) : undefined;
  }

  return undefined;
}

function extractResourceUri(resource) {
  if (!resource) {
    return undefined;
  }
  if (resource instanceof vscode.Uri) {
    return resource;
  }
  if (resource.uri instanceof vscode.Uri) {
    return resource.uri;
  }
  return undefined;
}

async function targetFromUri(uri) {
  const resourcePath = uri.fsPath;
  let focusPath = resourcePath;
  let focusKind = 'folder';
  let focusFilePath = '';
  try {
    const stat = await fs.stat(resourcePath);
    if (!stat.isDirectory()) {
      focusKind = 'file';
      focusFilePath = resourcePath;
      focusPath = path.dirname(resourcePath);
    }
  } catch (error) {
    focusKind = 'file';
    focusFilePath = resourcePath;
    focusPath = path.dirname(resourcePath);
  }
  const folder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(focusPath)) || findWorkspaceFolderForPath(focusPath);
  const root = folder ? folder.uri.fsPath : focusPath;
  return makeWorkspaceTarget(root, folder, {
    focusPath,
    focusKind,
    focusFilePath
  });
}

function findWorkspaceFolderForPath(filePath) {
  const folders = vscode.workspace.workspaceFolders || [];
  return folders.find((folder) => isPathInside(folder.uri.fsPath, filePath));
}

function makeWorkspaceTarget(root, workspaceFolder, options) {
  return _workspaceResolverModule.makeWorkspaceTarget(root, workspaceFolder, options);
}

function isPathInside(root, candidate) {
  return _pathSafeModule.isPathInside(root, candidate);
}

function boundedConfigInt(value, min, max, fallback) {
  return _settingsModule.boundedConfigInt(value, min, max, fallback);
}

function getConfig() {
  return _settingsModule.getNormalizedConfig(vscode.workspace.getConfiguration('aegisLocalAutopilot'));
}

function normalizeHttpBaseUrl(value, fallback) {
  return _settingsModule.normalizeHttpBaseUrl(value, fallback);
}

function stripKnownServiceEndpointPath(pathname) {
  return _settingsModule.stripKnownServiceEndpointPath(pathname);
}

function serviceUrl(baseUrl, pathname) {
  return _settingsModule.serviceUrl(baseUrl, pathname);
}

function getConfigSnapshot() {
  const config = getConfig();
  return {
    ollamaUrl: config.ollamaUrl,
    coreUrl: config.coreUrl,
    chatModel: config.chatModel,
    fastModel: config.fastModel,
    fallbackModels: config.fallbackModels,
    embeddingModel: config.embeddingModel,
    autopilotIntervalMinutes: config.autopilotIntervalMinutes,
    autopilotWriteMode: config.autopilotWriteMode,
    maxContextFiles: config.maxContextFiles,
    maxContextChars: config.maxContextChars,
    maxProposalDiffTabs: config.maxProposalDiffTabs,
    excludeGlob: config.excludeGlob,
    autoScanOnOpen: config.autoScanOnOpen,
    validationCommandPreferences: config.validationCommandPreferences,
    safetyMode: config.safetyMode
  };
}

function updateStatusBar(state, tooltip) {
  if (!statusBarItem) {
    return;
  }
  const labels = {
    Ready: 'Aegis: Ready',
    'No Workspace': 'Aegis: No Workspace',
    'Ollama Offline': 'Aegis: Ollama Offline',
    Indexing: 'Aegis: Indexing',
    Running: 'Aegis: Running',
    Error: 'Aegis: Error'
  };
  statusBarItem.text = labels[state] || `Aegis: ${state || 'Ready'}`;
  statusBarItem.tooltip = tooltip || 'Open Aegis Local Agent';
  statusBarItem.show();
}

async function refreshStatusBar() {
  const target = await resolveWorkspaceTarget(undefined, { silent: true });
  if (!target) {
    updateStatusBar('No Workspace', 'Open a VS Code folder to use Aegis.');
    return;
  }
  if (latestErrorInfo.message) {
    updateStatusBar('Error', latestErrorInfo.message);
    return;
  }
  if (agentState.status && !/^Idle$/i.test(agentState.status)) {
    updateAgentState({});
    return;
  }
  updateStatusBar('Ready', `Aegis ready for ${target.label}.`);
}

async function logExtensionEvent(kind, message, details = {}, target) {
  const line = `[${new Date().toISOString()}] ${kind}: ${sanitizeMemoryText(String(message || ''))}`;
  output && output.appendLine(line);
  let resolvedTarget = target;
  if (!resolvedTarget) {
    try {
      resolvedTarget = await resolveWorkspaceTarget(undefined, { silent: true });
    } catch (error) {
      resolvedTarget = undefined;
    }
  }
  if (!resolvedTarget) {
    return;
  }
  try {
    const memoryRoot = path.join(resolvedTarget.workspaceRoot || resolvedTarget.root, '.aegis');
    await fs.mkdir(memoryRoot, { recursive: true });
    const detailText = formatLogDetails(details);
    const entry = [
      `## ${new Date().toISOString()} - ${sanitizeMemoryText(String(kind || 'event'))}`,
      '',
      sanitizeMemoryText(String(message || '')),
      detailText ? `\n${detailText}` : '',
      ''
    ].join('\n');
    await fs.appendFile(path.join(memoryRoot, 'extension-log.md'), entry, 'utf8');
  } catch (error) {
    output && output.appendLine(`Aegis log write failed: ${safeErrorMessage(error)}`);
  }
}

async function recordRealWorldFinding(title, lines, target) {
  let resolvedTarget = target;
  if (!resolvedTarget) {
    try {
      resolvedTarget = await resolveWorkspaceTarget(undefined, { silent: true });
    } catch (error) {
      resolvedTarget = undefined;
    }
  }
  if (!resolvedTarget) {
    return;
  }
  await ensureWorkspaceMemory(resolvedTarget);
  const filePath = path.join(resolvedTarget.workspaceRoot || resolvedTarget.root, '.aegis', 'real-world-testing.md');
  const entry = [
    '',
    `## ${new Date().toISOString()} - ${sanitizeMemoryText(title)}`,
    '',
    ...[].concat(lines || []).map((line) => `- ${sanitizeMemoryText(String(line))}`),
    ''
  ].join('\n');
  await appendMemoryFileBestEffort(filePath, entry, 'real-world testing log');
}

function formatLogDetails(details) {
  if (!details || (typeof details === 'object' && !Object.keys(details).length)) {
    return '';
  }
  const safe = sanitizeLogValue(details);
  if (Array.isArray(safe)) {
    return safe.map((item) => `- ${item}`).join('\n');
  }
  if (safe && typeof safe === 'object') {
    return Object.entries(safe)
      .map(([key, value]) => `- ${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
      .join('\n');
  }
  return String(safe);
}

function sanitizeLogValue(value) {
  if (typeof value === 'string') {
    return sanitizeMemoryText(value);
  }
  if (Array.isArray(value)) {
    return value.map(sanitizeLogValue);
  }
  if (value && typeof value === 'object') {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (/(api[_-]?key|secret|token|password|credential|private[_-]?key)/i.test(key)) {
        result[key] = '[redacted]';
      } else {
        result[key] = sanitizeLogValue(item);
      }
    }
    return result;
  }
  return value;
}

function reportError(error, context = {}) {
  const message = safeErrorMessage(error);
  const diagnosis = diagnoseError(error, context);
  latestErrorInfo = {
    at: new Date().toISOString(),
    message,
    failedCommand: context.failedCommand || lastFailedCommand || '',
    stack: error && error.stack ? redactDiagnosticText(error.stack, 4000) : '',
    likelyCause: diagnosis.likelyCause,
    suggestedFix: diagnosis.suggestedFix,
    retryCommand: context.retryCommand || ''
  };
  output.appendLine(`Error: ${message}`);
  output.show(true);
  updateStatusBar('Error', message);
  logExtensionEvent('error', message, latestErrorInfo).catch(() => {});
  recordRealWorldFinding('Extension Error', [
    `Failed command: ${latestErrorInfo.failedCommand || 'unknown'}`,
    `Message: ${message}`,
    `Likely cause: ${latestErrorInfo.likelyCause}`,
    `Suggested fix: ${latestErrorInfo.suggestedFix}`
  ]).catch(() => {});
  panelProvider && panelProvider.post({ command: 'error', text: message, errorInfo: latestErrorInfo });
  panelProvider && panelProvider.refresh();
  vscode.window.showErrorMessage(`Aegis Local Autopilot: ${message}`);
}

function diagnoseError(error, context = {}) {
  const message = `${error && error.message ? error.message : error || ''}\n${context.failedCommand || ''}`.toLowerCase();
  if (/econnrefused|ollama|11434|fetch failed|connect/.test(message)) {
    return {
      likelyCause: 'Ollama is offline, unreachable, or using a different URL.',
      suggestedFix: 'Start Ollama, verify the configured Ollama URL, then run Aegis: Run Health Check.'
    };
  }
  if (/model.*not found|not found/.test(message) && /qwen|granite|model|ollama/.test(message)) {
    return {
      likelyCause: 'The selected local model is not installed.',
      suggestedFix: 'Run ollama list, install the missing model with ollama pull, or choose another model in the Aegis sidebar.'
    };
  }
  if (/eacces|eperm|permission|access is denied|readonly/.test(message)) {
    return {
      likelyCause: 'The workspace or .aegis folder is not writable.',
      suggestedFix: 'Check folder permissions and antivirus/file-locking tools, then retry the operation.'
    };
  }
  if (/timed out|timeout/.test(message)) {
    return {
      likelyCause: 'A local model or validation command took too long.',
      suggestedFix: 'Try a smaller task, use a faster model, or run the health check to isolate the slow step.'
    };
  }
  if (/json|parse|unexpected token/.test(message)) {
    return {
      likelyCause: 'The local model returned malformed JSON for an agent proposal.',
      suggestedFix: 'Retry the request or use a narrower task so the model can return a smaller proposal.'
    };
  }
  if (/no workspace|open a .*folder/.test(message)) {
    return {
      likelyCause: 'No VS Code workspace folder is open.',
      suggestedFix: 'Open the project folder in VS Code and run the command again.'
    };
  }
  return {
    likelyCause: 'The extension hit an unexpected runtime error.',
    suggestedFix: 'Open .aegis/extension-log.md and the Aegis output channel, then retry or run the health check.'
  };
}

function renderPanelHtml() {
  const nonce = String(Date.now());
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aegis Local Agent</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 14px;
      color: #d7e2ea;
      background: #080d12;
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }
    .shell { display: flex; flex-direction: column; gap: 12px; }
    .hero {
      padding: 14px;
      border: 1px solid rgba(70, 220, 235, 0.22);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(7, 20, 27, 0.98), rgba(28, 8, 14, 0.92));
      box-shadow: 0 0 0 1px rgba(255,255,255,0.02), 0 12px 28px rgba(0,0,0,0.25);
    }
    .title { margin: 0; font-size: 16px; letter-spacing: 0; color: #effaff; }
    .subtitle { margin: 6px 0 0; color: #8ea3ad; line-height: 1.4; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 12px; }
    .card {
      border: 1px solid rgba(135, 158, 170, 0.18);
      border-radius: 8px;
      background: #101820;
      overflow: hidden;
    }
    .cardHeader {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-bottom: 1px solid rgba(135, 158, 170, 0.14);
      background: #111d26;
    }
    .cardTitle { margin: 0; font-size: 12px; color: #9eeefa; text-transform: uppercase; letter-spacing: 0; }
    .cardBody { padding: 12px; }
    .muted { color: #8da1ac; }
    .statGrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .stat {
      min-height: 58px;
      padding: 8px;
      border-radius: 6px;
      background: #0b1218;
      border: 1px solid rgba(135, 158, 170, 0.12);
    }
    .statLabel { color: #78909c; font-size: 11px; }
    .statValue { margin-top: 4px; color: #e8f7fb; line-height: 1.35; word-break: break-word; }
    button, select, textarea, input {
      width: 100%;
      font: inherit;
      border-radius: 4px;
    }
    button {
      border: 1px solid rgba(80, 221, 235, 0.28);
      background: #12333d;
      color: #dffbff;
      padding: 7px 8px;
      cursor: pointer;
    }
    button:hover { background: #164858; }
    button.secondary { border-color: rgba(160, 178, 188, 0.2); background: #151f29; color: #d6e4ea; }
    button.danger { border-color: rgba(255, 84, 104, 0.45); background: #3a1219; color: #ffdfe4; }
    button.good { border-color: rgba(68, 226, 185, 0.35); background: #0f352d; color: #d9fff6; }
    select, textarea, input {
      color: #e7f1f5;
      background: #0b1218;
      border: 1px solid rgba(135, 158, 170, 0.22);
      padding: 8px;
    }
    textarea { min-height: 88px; resize: vertical; }
    .row { display: flex; gap: 8px; margin-top: 8px; }
    .row > * { min-width: 0; }
    .actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .history {
      max-height: 260px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-right: 2px;
    }
    .message {
      padding: 8px;
      border-radius: 6px;
      line-height: 1.4;
      white-space: pre-wrap;
      background: #0b1218;
      border: 1px solid rgba(135, 158, 170, 0.12);
    }
    .message.user { border-left: 3px solid #46dceb; }
    .message.assistant { border-left: 3px solid #ff5168; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip {
      border: 1px solid rgba(70, 220, 235, 0.22);
      color: #9eeefa;
      background: #09151b;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 11px;
    }
    .pre {
      white-space: pre-wrap;
      overflow: auto;
      max-height: 280px;
      line-height: 1.45;
      color: #d7e2ea;
    }
    .fileList { display: flex; flex-direction: column; gap: 6px; }
    .fileRow {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;
      align-items: start;
      padding: 8px;
      border: 1px solid rgba(135, 158, 170, 0.14);
      border-radius: 6px;
      background: #0b1218;
    }
    .risk { color: #ff9aac; }
    .ok { color: #74f0d0; }
    .warn { color: #ffd38a; }
    .memoryGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
    .settingsGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
    .settingsWide { grid-column: 1 / -1; }
    label { display: flex; flex-direction: column; gap: 4px; color: #8da1ac; }
    @media (max-width: 520px) {
      .grid { grid-template-columns: 1fr; }
      .actions { grid-template-columns: 1fr; }
      .row { flex-direction: column; }
      .statGrid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1 class="title">Aegis Local Agent</h1>
      <p class="subtitle">Local-first coding cockpit for workspace intelligence, planning, diffs, validation, repair, and memory.</p>
    </section>

    <section class="card">
      <div class="cardHeader"><h2 class="cardTitle">Project Overview</h2><button class="secondary" id="refresh">Refresh</button></div>
      <div class="cardBody">
        <div class="statGrid" id="overview"></div>
      </div>
    </section>

    <section class="grid">
      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Health Check</h2><button class="secondary" id="runHealth">Run</button></div>
        <div class="cardBody">
          <div class="row">
            <button class="secondary" id="setupChecklist">Setup Checklist</button>
          </div>
          <div class="statGrid" id="healthSummary"></div>
          <div class="fileList" id="healthChecks"></div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Model Diagnostics</h2><span class="muted">Ollama</span></div>
        <div class="cardBody">
          <div class="row">
            <button id="testModel">Test Prompt</button>
            <button class="secondary" id="testFallbacks">Test Fallbacks</button>
          </div>
          <div class="pre" id="modelDiagnostics">No model diagnostics yet.</div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Runtime Status</h2><span id="runtimeMode" class="muted">Core not checked</span></div>
        <div class="cardBody">
          <div class="statGrid" id="runtimeSummary"></div>
          <div class="fileList" id="runtimeOps"></div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Quality Gates</h2><span id="qualityMode" class="muted">No gate run</span></div>
        <div class="cardBody">
          <div class="statGrid" id="qualitySummary"></div>
          <div class="fileList" id="qualityDetails"></div>
        </div>
      </section>
    </section>

    <section class="grid">
      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Dependency Graph Summary</h2><span class="muted">repo-wide</span></div>
        <div class="cardBody">
          <div class="statGrid" id="graphSummary"></div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Impact Analysis</h2><span id="impactRisk" class="muted">No analysis yet</span></div>
        <div class="cardBody">
          <div class="pre" id="impactAnalysis">Run Agent Mode to generate impact analysis.</div>
        </div>
      </section>
    </section>

    <section class="grid">
      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Chat Panel</h2><button class="secondary" id="clearChat">Clear</button></div>
        <div class="cardBody">
          <select id="model"></select>
          <div class="history" id="chatHistory"></div>
          <div class="chips" id="attachments"></div>
          <textarea id="prompt" placeholder="Ask the local model or give Agent Mode a task."></textarea>
          <div class="row">
            <button id="chat">Send</button>
            <button class="secondary" id="runAgentPrompt" title="Plan, diffs, approval, apply, validation">Run Agent Mode</button>
            <button class="secondary" id="runAutopilotDraft" title="One autopilot proposal from the prompt below">Draft Once</button>
            <button class="secondary" id="attachFile">Attach File</button>
            <button class="secondary" id="attachSelection">Attach Selection</button>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Agent Actions</h2><span class="muted">Safe approvals</span></div>
        <div class="cardBody actions">
          <button id="fixBuild" title="Inspect diagnostics and validation output, then propose a safe fix.">Fix Current Error</button>
          <button id="explainFile" title="Explain the active editor file without changing it.">Explain Current File</button>
          <button id="improveSelection" title="Improve only the currently selected code after showing a diff.">Improve Selected Code</button>
          <button id="continueCurrentTask" title="Continue the latest task with a small approval-based next step.">Continue Current Task</button>
          <button id="runValidation" title="Run detected safe build/test/lint commands.">Run Validation</button>
          <button class="danger" id="rollbackQuick" title="Restore files from the last Aegis backup.">Roll Back Last Change</button>
          <button id="continue" title="Choose the next safe task from workspace memory and context.">Continue Project</button>
          <button id="explainProject" title="Review project structure and likely risks without editing.">Review Project</button>
          <button id="projectRoadmap">Generate Roadmap</button>
          <button id="continueRoadmap">Continue From Roadmap</button>
          <button id="reviewFile">Review Current File</button>
          <button id="feature">Create Feature</button>
          <button class="secondary" id="startAutopilotBtn" title="Run autopilot on a timer">Start Autopilot Loop</button>
          <button class="secondary" id="stopAutopilotBtn" title="Stop the background autopilot timer">Stop Autopilot Loop</button>
        </div>
      </section>
    </section>

    <section class="grid">
      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Active Plan</h2><span id="approvalStatus" class="muted">No approval pending</span></div>
        <div class="cardBody">
          <div class="statGrid">
            <div class="stat"><div class="statLabel">Current Task</div><div class="statValue" id="currentTask">None</div></div>
            <div class="stat"><div class="statLabel">Risk Level</div><div class="statValue risk" id="riskLevel">Unknown</div></div>
            <div class="stat"><div class="statLabel">Confidence</div><div class="statValue" id="confidenceScore">Unknown</div></div>
            <div class="stat"><div class="statLabel">Undo Visibility</div><div class="statValue" id="undoVisibility">Backups before apply</div></div>
          </div>
          <div class="pre" id="activePlan">No active plan.</div>
          <div class="fileList" id="progressItems"></div>
          <div class="fileList" id="contextFiles"></div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Staged Plan</h2><span class="muted">approval gates</span></div>
        <div class="cardBody">
          <div class="fileList" id="stagedPlan">No staged plan yet.</div>
        </div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Diff / Approval</h2><button class="secondary" id="preview">Open Diffs</button></div>
        <div class="cardBody">
          <div class="fileList" id="proposalFiles"></div>
          <div class="row">
            <button class="good" id="approveAll">Approve All</button>
            <button class="secondary" id="approveSelected">Approve Selected</button>
            <button class="danger" id="reject">Reject</button>
          </div>
          <div class="row">
            <button class="secondary" id="regenerate">Regenerate Plan</button>
          </div>
        </div>
      </section>
    </section>

    <section class="card">
      <div class="cardHeader"><h2 class="cardTitle">Why Aegis chose these files</h2><span class="muted">workspace-root safe writes</span></div>
      <div class="cardBody">
        <div class="fileList" id="destinationReasoning">No pending file destinations.</div>
      </div>
    </section>

    <section class="card">
      <div class="cardHeader"><h2 class="cardTitle">Validation Console</h2><span id="repairCount" class="muted">Repairs: 0</span></div>
      <div class="cardBody">
        <div class="pre" id="validationOutput">No validation output yet.</div>
      </div>
    </section>

    <section class="card">
      <div class="cardHeader"><h2 class="cardTitle">Error Reporting</h2><button class="secondary" id="retryError">Retry</button></div>
      <div class="cardBody">
        <div class="pre" id="errorPanel">No extension errors recorded.</div>
        <div class="row">
          <button class="secondary" id="openLogs">Open Logs</button>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="cardHeader"><h2 class="cardTitle">Changed Files History</h2><button class="danger" id="rollbackLast">Rollback Last</button></div>
      <div class="cardBody">
        <div class="fileList" id="changeHistory">No agent changes applied yet.</div>
      </div>
    </section>

    <section class="grid">
      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Memory Panel</h2><span class="muted">.aegis</span></div>
        <div class="cardBody memoryGrid" id="memoryLinks"></div>
      </section>

      <section class="card">
        <div class="cardHeader"><h2 class="cardTitle">Settings</h2><button class="secondary" id="saveSettings">Save</button></div>
        <div class="cardBody">
          <div class="settingsGrid">
            <label>Ollama URL<input id="settingOllama" /></label>
            <label>Aegis Core URL<input id="settingCore" /></label>
            <label>Default Model<input id="settingModel" /></label>
            <label>Fast Model<input id="settingFastModel" /></label>
            <label>Fallback Models<input id="settingFallbacks" /></label>
            <label>Max Context Size<input id="settingContext" type="number" /></label>
            <label>Max Context Files<input id="settingMaxFiles" type="number" min="3" max="40" /></label>
            <label>Autopilot Interval (min)<input id="settingAutopilotMin" type="number" min="2" /></label>
            <label>Autopilot Write Mode<select id="settingWriteMode"><option>preview</option><option>apply</option></select></label>
            <label>Max Diff Tabs<input id="settingDiffTabs" type="number" min="1" max="25" /></label>
            <label>Validation Preferences<input id="settingValidation" /></label>
            <label>Safety Mode<select id="settingSafety"><option>standard</option><option>strict</option><option>review-only</option></select></label>
            <label class="settingsWide">Exclude Glob<input id="settingExcludeGlob" /></label>
          </div>
          <div class="row">
            <label><input id="settingAutoScan" type="checkbox" /> Auto-scan on open</label>
          </div>
        </div>
      </section>
    </section>
  </main>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    let currentState = {};
    const model = document.getElementById('model');
    const prompt = document.getElementById('prompt');
    const byId = (id) => document.getElementById(id);

    document.getElementById('chat').addEventListener('click', () => {
      vscode.postMessage({ command: 'chat', text: prompt.value, model: model.value });
    });
    document.getElementById('runAgentPrompt').addEventListener('click', () => vscode.postMessage({ command: 'runAgentMode', text: prompt.value }));
    document.getElementById('runAutopilotDraft').addEventListener('click', () => vscode.postMessage({ command: 'runAutopilot', text: prompt.value }));
    document.getElementById('runHealth').addEventListener('click', () => vscode.postMessage({ command: 'runHealthCheck' }));
    document.getElementById('setupChecklist').addEventListener('click', () => vscode.postMessage({ command: 'runFirstRunSetup' }));
    document.getElementById('testModel').addEventListener('click', () => vscode.postMessage({ command: 'testModelPrompt' }));
    document.getElementById('testFallbacks').addEventListener('click', () => vscode.postMessage({ command: 'testFallbackModels' }));
    document.getElementById('retryError').addEventListener('click', () => vscode.postMessage({ command: 'retryLastAction' }));
    document.getElementById('openLogs').addEventListener('click', () => vscode.postMessage({ command: 'openMemory', file: 'extension-log.md' }));
    document.getElementById('continue').addEventListener('click', () => {
      vscode.postMessage({ command: 'continueProject' });
    });
    document.getElementById('continueCurrentTask').addEventListener('click', () => {
      vscode.postMessage({ command: 'continueCurrentTask' });
    });
    document.getElementById('runValidation').addEventListener('click', () => vscode.postMessage({ command: 'runValidation' }));
    document.getElementById('rollbackQuick').addEventListener('click', () => vscode.postMessage({ command: 'rollbackLastChange' }));
    document.getElementById('explainProject').addEventListener('click', () => {
      vscode.postMessage({ command: 'explainProject' });
    });
    document.getElementById('explainFile').addEventListener('click', () => vscode.postMessage({ command: 'explainActiveFile' }));
    document.getElementById('fixBuild').addEventListener('click', () => {
      vscode.postMessage({ command: 'fixBuildErrors' });
    });
    document.getElementById('projectRoadmap').addEventListener('click', () => {
      vscode.postMessage({ command: 'generateProjectRoadmap' });
    });
    document.getElementById('continueRoadmap').addEventListener('click', () => {
      vscode.postMessage({ command: 'continueFromRoadmap' });
    });
    document.getElementById('feature').addEventListener('click', () => {
      vscode.postMessage({ command: 'createFeature' });
    });
    document.getElementById('startAutopilotBtn').addEventListener('click', () => vscode.postMessage({ command: 'startAutopilot' }));
    document.getElementById('stopAutopilotBtn').addEventListener('click', () => vscode.postMessage({ command: 'stopAutopilot' }));
    document.getElementById('reviewFile').addEventListener('click', () => vscode.postMessage({ command: 'reviewCurrentFile' }));
    document.getElementById('improveSelection').addEventListener('click', () => vscode.postMessage({ command: 'improveSelectedCode' }));
    document.getElementById('attachFile').addEventListener('click', () => vscode.postMessage({ command: 'attachCurrentFile' }));
    document.getElementById('attachSelection').addEventListener('click', () => vscode.postMessage({ command: 'attachSelectedCode' }));
    document.getElementById('clearChat').addEventListener('click', () => vscode.postMessage({ command: 'clearChat' }));
    document.getElementById('preview').addEventListener('click', () => {
      vscode.postMessage({ command: 'previewLastProposal' });
    });
    document.getElementById('approveAll').addEventListener('click', () => vscode.postMessage({ command: 'approveProposal' }));
    document.getElementById('approveSelected').addEventListener('click', () => {
      const indexes = Array.from(document.querySelectorAll('.proposalCheck:checked')).map((node) => Number(node.value));
      vscode.postMessage({ command: 'approveProposal', indexes });
    });
    document.getElementById('reject').addEventListener('click', () => vscode.postMessage({ command: 'rejectProposal' }));
    document.getElementById('regenerate').addEventListener('click', () => vscode.postMessage({ command: 'regeneratePlan' }));
    document.getElementById('rollbackLast').addEventListener('click', () => vscode.postMessage({ command: 'rollbackLastChange' }));
    document.getElementById('refresh').addEventListener('click', () => {
      vscode.postMessage({ command: 'refresh' });
    });
    document.getElementById('saveSettings').addEventListener('click', () => {
      vscode.postMessage({
        command: 'saveSettings',
        settings: {
          ollamaUrl: byId('settingOllama').value,
          coreUrl: byId('settingCore').value,
          chatModel: byId('settingModel').value,
          fastModel: byId('settingFastModel').value,
          fallbackModels: byId('settingFallbacks').value,
          maxContextChars: byId('settingContext').value,
          maxContextFiles: byId('settingMaxFiles').value,
          autopilotIntervalMinutes: byId('settingAutopilotMin').value,
          autopilotWriteMode: byId('settingWriteMode').value,
          maxProposalDiffTabs: byId('settingDiffTabs').value,
          excludeGlob: byId('settingExcludeGlob').value,
          validationCommandPreferences: byId('settingValidation').value,
          safetyMode: byId('settingSafety').value,
          autoScanOnOpen: byId('settingAutoScan').checked
        }
      });
    });

    window.addEventListener('message', (event) => {
      const message = event.data;
      if (message.command === 'state') {
        currentState = message.state || {};
        renderState(currentState);
      } else if (message.command === 'busy') {
        byId('validationOutput').textContent = message.text;
      } else if (message.command === 'chatResult') {
        appendTransientAssistant(message.text);
      } else if (message.command === 'proposal') {
        byId('approvalStatus').textContent = message.summary || 'Proposal ready';
      } else if (message.command === 'agentState') {
        renderAgent(message.agent);
      } else if (message.command === 'runtime') {
        renderRuntime(message.runtime || {});
        renderQuality(message.runtime || {});
      } else if (message.command === 'chatHistory') {
        renderChat(message.chatHistory || []);
      } else if (message.command === 'error') {
        byId('validationOutput').textContent = message.text;
        renderError(message.errorInfo || {});
      }
    });

    function renderState(state) {
      renderModels(state);
      renderOverview(state.projectOverview || {});
      renderHealth(state.health || {});
      renderModelDiagnostics(state.modelDiagnostics || {});
      renderRuntime(state.runtime || {});
      renderQuality(state.runtime || {});
      renderError(state.errorInfo || {});
      renderChat(state.chatHistory || []);
      renderAttachments(state.attachments || []);
      renderAgent(state.agent || {});
      renderProposal(state.proposal || {});
      renderRepoWide(state);
      renderMemory(state.memoryFiles || []);
      renderSettings(state.config || {});
    }

    function renderModels(state) {
      const configured = state.config ? state.config.chatModel : '';
      model.innerHTML = '';
      const names = (state.models || []).map((item) => item.name || item.model).filter(Boolean);
      if (configured && !names.includes(configured)) names.unshift(configured);
      names.forEach((name) => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        option.selected = name === configured;
        model.appendChild(option);
      });
    }

    function renderOverview(overview) {
      const commands = overview.commands && overview.commands.length ? overview.commands.join('\\n') : 'None detected';
      const items = [
        ['Workspace', overview.workspaceName || 'No workspace'],
        ['Language / Framework', [(overview.languages || []).join(', '), (overview.frameworks || []).join(', ')].filter(Boolean).join('\\n') || 'Unknown'],
        ['Build / Test Commands', commands],
        ['Active Model', (overview.activeModel || '') + (overview.modelReady === false ? ' (not detected)' : '')],
        ['Health', overview.health || 'Unknown'],
        ['Last Validation', overview.lastValidation || 'No validation yet']
      ];
      byId('overview').innerHTML = items.map((item) => '<div class="stat"><div class="statLabel">' + escapeHtml(item[0]) + '</div><div class="statValue">' + escapeHtml(item[1]) + '</div></div>').join('');
    }

    function renderHealth(health) {
      const checks = health.checks || [];
      const summary = [
        ['Overall', health.overall || 'unknown'],
        ['Checked', health.checkedAt || 'never'],
        ['Elapsed', health.elapsedMs ? health.elapsedMs + 'ms' : ''],
        ['Failures', checks.filter((check) => check.status === 'fail').length]
      ];
      byId('healthSummary').innerHTML = summary.map((item) => '<div class="stat"><div class="statLabel">' + escapeHtml(item[0]) + '</div><div class="statValue">' + escapeHtml(item[1]) + '</div></div>').join('');
      byId('healthChecks').innerHTML = checks.length ? checks.map((check) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(check.status) + '</span>',
        '<span><strong>' + escapeHtml(check.name) + '</strong><br/><span class="muted">' + escapeHtml(check.detail || '') + '</span>' + (check.fix ? '<br/><span class="warn">' + escapeHtml(check.fix) + '</span>' : '') + '</span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">Run a health check to inspect setup.</div>';
    }

    function renderModelDiagnostics(diagnostics) {
      const lines = [];
      if ((diagnostics.installedModels || []).length) {
        lines.push('Installed models:');
        lines.push((diagnostics.installedModels || []).map((name) => '- ' + name).join('\\n'));
      }
      if (diagnostics.contextWarning) {
        lines.push('Context: ' + diagnostics.contextWarning);
      }
      if (diagnostics.primary) {
        lines.push('Primary: ' + diagnostics.primary.model + ' - ' + diagnostics.primary.status + ' - ' + diagnostics.primary.latencyMs + 'ms');
        lines.push(diagnostics.primary.detail || '');
      }
      if ((diagnostics.fallbacks || []).length) {
        lines.push('Fallbacks:');
        lines.push((diagnostics.fallbacks || []).map((item) => '- ' + item.model + ' - ' + item.status + ' - ' + item.latencyMs + 'ms: ' + item.detail).join('\\n'));
      }
      byId('modelDiagnostics').textContent = lines.length ? lines.join('\\n\\n') : 'No model diagnostics yet.';
    }

    function renderRuntime(runtime) {
      const mode = runtime.coreConnected
        ? (runtime.fallbackMode ? 'Core connected with fallback' : 'Core primary')
        : (runtime.fallbackMode ? 'Local fallback' : 'Core not checked');
      byId('runtimeMode').textContent = mode;
      const latest = runtime.latestValidation || {};
      const items = [
        ['Core', runtime.coreConnected ? 'Connected' : 'Disconnected'],
        ['Fallback', runtime.fallbackMode ? (runtime.fallbackReason || 'Active') : 'Inactive'],
        ['Active Workflow', runtime.activeWorkflowId ? runtime.activeWorkflowId + '\\n' + (runtime.activeWorkflowStatus || '') : 'None'],
        ['Provider', runtime.coreConnected ? 'Aegis Core /v1' : 'VS Code local'],
        ['Validation', runtime.latestValidationStatus || (latest.command ? latest.command : 'No result yet')],
        ['Checkpoint', runtime.checkpointAvailable ? (runtime.lastCheckpointId || 'Available') : 'None recorded']
      ];
      byId('runtimeSummary').innerHTML = items.map((item) => '<div class="stat"><div class="statLabel">' + escapeHtml(item[0]) + '</div><div class="statValue">' + escapeHtml(item[1]) + '</div></div>').join('');
      const operations = runtime.recentOperations || [];
      byId('runtimeOps').innerHTML = operations.length ? operations.slice(0, 8).map((item) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(item.runtime || '') + '</span>',
        '<span><strong>' + escapeHtml(item.operation || 'operation') + ' - ' + escapeHtml(item.status || '') + '</strong>',
        '<br/><span class="muted">' + escapeHtml(item.detail || '') + '</span>',
        (item.workflowId ? '<br/><span class="muted">Workflow: ' + escapeHtml(item.workflowId) + '</span>' : ''),
        (item.jobId ? '<br/><span class="muted">Job: ' + escapeHtml(item.jobId) + '</span>' : ''),
        (item.checkpointId ? '<br/><span class="muted">Checkpoint: ' + escapeHtml(item.checkpointId) + '</span>' : ''),
        '</span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">No runtime operations recorded yet.</div>';
    }

    function renderQuality(runtime) {
      const gate = runtime.qualityGate || {};
      const status = runtime.qualityGateStatus || (gate.apply_allowed === false ? 'blocked' : (gate.id ? 'clear' : 'not checked'));
      byId('qualityMode').textContent = status === 'blocked' ? 'Blocked' : (status === 'clear' ? 'Clear' : 'No gate run');
      const pct = (value) => typeof value === 'number' ? Math.round(value * 100) + '%' : 'Unknown';
      const blockers = runtime.qualityBlockers || [];
      const warnings = runtime.qualityWarnings || [];
      const items = [
        ['Apply Status', gate.apply_allowed === false ? 'Blocked' : (gate.id ? 'Allowed' : 'Not checked')],
        ['Confidence', pct(runtime.qualityConfidenceScore)],
        ['Validation', pct(runtime.qualityValidationScore)],
        ['Risk', pct(runtime.qualityRiskScore)],
        ['Gate Count', runtime.qualityGateCount || 0],
        ['Updated', runtime.qualityUpdatedAt || 'Never']
      ];
      byId('qualitySummary').innerHTML = items.map((item) => '<div class="stat"><div class="statLabel">' + escapeHtml(item[0]) + '</div><div class="statValue">' + escapeHtml(item[1]) + '</div></div>').join('');
      const gates = Array.isArray(gate.gates) ? gate.gates : [];
      const rows = [];
      blockers.slice(0, 4).forEach((item) => rows.push({ status: 'blocked', name: 'Blocker', detail: item }));
      warnings.slice(0, 3).forEach((item) => rows.push({ status: 'warn', name: 'Warning', detail: item }));
      gates.slice(0, 6).forEach((item) => rows.push({ status: item.status || 'unknown', name: item.name || item.id || 'Gate', detail: item.summary || item.detail || '' }));
      byId('qualityDetails').innerHTML = rows.length ? rows.map((item) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(item.status) + '</span>',
        '<span><strong>' + escapeHtml(item.name) + '</strong><br/><span class="muted">' + escapeHtml(item.detail || '') + '</span></span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">Run or apply a proposal to evaluate Core quality gates.</div>';
    }

    function renderError(error) {
      if (!error || !error.message) {
        byId('errorPanel').textContent = 'No extension errors recorded.';
        return;
      }
      byId('errorPanel').textContent = [
        'Latest error: ' + (error.message || ''),
        'Time: ' + (error.at || ''),
        'Failed command: ' + (error.failedCommand || 'unknown'),
        'Likely cause: ' + (error.likelyCause || ''),
        'Suggested fix: ' + (error.suggestedFix || ''),
        '',
        'Stack:',
        error.stack || 'No stack trace available.'
      ].join('\\n');
    }

    function renderChat(history) {
      if (!history.length) {
        byId('chatHistory').innerHTML = '<div class="message assistant">No conversation yet. Ask a question or attach context.</div>';
        return;
      }
      byId('chatHistory').innerHTML = history.map((item) => '<div class="message ' + escapeHtml(item.role) + '">' + escapeHtml(item.text) + '</div>').join('');
    }

    function appendTransientAssistant(text) {
      if (!text) return;
      const existing = currentState.chatHistory || [];
      renderChat(existing.concat([{ role: 'assistant', text }]));
    }

    function renderAttachments(items) {
      byId('attachments').innerHTML = items.length
        ? items.map((item) => '<span class="chip">' + escapeHtml(item.label) + ' - ' + item.chars + ' chars</span>').join('')
        : '<span class="chip">No attachments</span>';
    }

    function renderAgent(agent) {
      if (!agent) {
        byId('activePlan').textContent = 'No active plan.';
        byId('validationOutput').textContent = 'No validation output yet.';
        return;
      }
      byId('currentTask').textContent = agent.currentTask || agent.status || 'Idle';
      byId('activePlan').textContent = agent.activePlan || 'No active plan.';
      byId('validationOutput').textContent = agent.validationOutput || 'No validation output yet.';
      byId('repairCount').textContent = 'Repairs: ' + (agent.repairAttempts || 0);
      const progress = agent.progressItems || [];
      byId('progressItems').innerHTML = progress.length ? progress.map((item) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(item.at || '') + '</span>',
        '<span><strong>' + escapeHtml(item.label || 'Working') + '</strong><br/><span class="muted">' + escapeHtml(item.detail || '') + '</span></span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">No active progress yet.</div>';
      const contextFiles = agent.contextFiles || [];
      byId('contextFiles').innerHTML = contextFiles.length ? contextFiles.map((item) => [
        '<div class="fileRow">',
        '<span class="chip">read</span>',
        '<span><strong>' + escapeHtml(item.path || '') + '</strong><br/><span class="muted">' + escapeHtml(item.reason || '') + '</span></span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">Focused context files will appear here while Aegis plans.</div>';
    }

    function renderProposal(proposal) {
      byId('riskLevel').textContent = proposal.risk || 'Unknown';
      byId('confidenceScore').textContent = proposal.confidenceScore ? Math.round(proposal.confidenceScore * 100) + '%' : 'Unknown';
      byId('undoVisibility').textContent = proposal.coreProposalId
        ? 'Rollback: Core checkpoint before apply'
        : 'Rollback: Aegis backs up approved edits before apply';
      byId('approvalStatus').textContent = proposal.approvalStatus || 'none';
      const files = proposal.files || [];
      byId('proposalFiles').innerHTML = files.length ? files.map((file) => [
        '<label class="fileRow">',
        '<input class="proposalCheck" type="checkbox" value="' + file.index + '" checked />',
        '<span><strong>' + escapeHtml(file.path) + '</strong>' + (isRiskyFile(file.path) ? ' <span class="risk">risky</span>' : '') + '<br/><span class="muted">' + escapeHtml(file.reason || 'Proposed change') + '</span><br/><span class="muted">' + escapeHtml(file.chars || 0) + ' replacement chars</span></span>',
        '</label>'
      ].join('')).join('') : '<div class="muted">No pending file diffs.</div>';
      const destinations = proposal.destinationReasoning || [];
      byId('destinationReasoning').innerHTML = destinations.length ? destinations.map((item) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(item.existing ? 'existing' : 'new') + '</span>',
        '<span><strong>' + escapeHtml(item.path || '') + '</strong>',
        '<br/><span class="muted">Source: ' + escapeHtml(item.source || 'model') + ' · Risk: ' + escapeHtml(item.risk || 'unknown') + '</span>',
        '<br/><span class="muted">Safety: ' + escapeHtml((item.safety && item.safety.status) || 'accepted') + (item.safety && item.safety.rejected ? ' · rejected' : '') + '</span>',
        item.selectedContext ? '<br/><span class="muted">Selected context: ' + escapeHtml(item.selectedContext) + '</span>' : '',
        '<br/><span class="muted">' + escapeHtml(item.choiceReason || 'Aegis selected this path from proposal and workspace context.') + '</span>',
        '</span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">No pending file destinations.</div>';
    }

    function isRiskyFile(filePath) {
      return /(^|\\/)(package\\.json|.*\\.(?:csproj|fsproj|vbproj|vcxproj|vcxproj\\.filters|sln|slnx)|vite\\.config\\.|webpack\\.config\\.|next\\.config\\.|tsconfig|pyproject\\.toml|requirements|cmakelists\\.txt)/i.test(filePath || '') || /lock/i.test(filePath || '');
    }

    function renderRepoWide(state) {
      const graph = state.dependencyGraph || {};
      const graphItems = [
        ['Graph Nodes', graph.nodes || 0],
        ['Import Edges', graph.edges || 0],
        ['Symbols', graph.symbols || 0],
        ['Routes / APIs', (graph.routes || 0) + ' / ' + (graph.apis || 0)],
        ['Components', graph.components || 0],
        ['Tests / Configs', (graph.tests || 0) + ' / ' + (graph.configs || 0)]
      ];
      byId('graphSummary').innerHTML = graphItems.map((item) => '<div class="stat"><div class="statLabel">' + escapeHtml(item[0]) + '</div><div class="statValue">' + escapeHtml(item[1]) + '</div></div>').join('');

      const impact = state.impactAnalysis || {};
      byId('impactRisk').textContent = impact.riskLevel ? 'Risk: ' + impact.riskLevel : 'No analysis yet';
      const impactLines = [];
      if ((impact.likelyAffectedFiles || []).length) impactLines.push('Likely affected files:\\n' + impact.likelyAffectedFiles.map((file) => '- ' + file).join('\\n'));
      if ((impact.relatedTests || []).length) impactLines.push('Related tests:\\n' + impact.relatedTests.map((file) => '- ' + file).join('\\n'));
      if ((impact.relatedValidation || []).length) impactLines.push('Validation:\\n' + impact.relatedValidation.map((cmd) => '- ' + cmd).join('\\n'));
      if ((impact.possibleBreakingPoints || []).length) impactLines.push('Possible breaking points:\\n' + impact.possibleBreakingPoints.map((point) => '- ' + point).join('\\n'));
      if (impact.rollbackPlan) impactLines.push('Rollback:\\n' + impact.rollbackPlan);
      byId('impactAnalysis').textContent = impactLines.length ? impactLines.join('\\n\\n') : 'Run Agent Mode to generate impact analysis.';

      const stages = state.stagedPlan || [];
      byId('stagedPlan').innerHTML = stages.length ? stages.map((stage) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml(stage.index) + '</span>',
        '<span><strong>' + escapeHtml(stage.name) + '</strong><br/><span class="muted">' + escapeHtml(stage.goal || 'Approval required') + '</span><br/><span class="muted">Files: ' + escapeHtml((stage.files || []).join(', ') || 'none listed') + '</span></span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">No staged plan yet.</div>';

      const history = state.changedFilesHistory || [];
      byId('changeHistory').innerHTML = history.length ? history.slice(0, 8).map((item) => [
        '<div class="fileRow">',
        '<span class="chip">' + escapeHtml((item.files || []).length) + '</span>',
        '<span><strong>' + escapeHtml(item.summary || 'Aegis change') + '</strong><br/><span class="muted">' + escapeHtml(item.createdAt || '') + '</span><br/><span class="muted">' + escapeHtml((item.files || []).slice(0, 6).join(', ')) + '</span></span>',
        '</div>'
      ].join('')).join('') : '<div class="muted">No agent changes applied yet.</div>';
    }

    function renderMemory(files) {
      byId('memoryLinks').innerHTML = files.map((file) => '<button class="secondary memoryBtn" data-file="' + escapeHtml(file) + '">' + escapeHtml(file) + '</button>').join('');
      Array.from(document.querySelectorAll('.memoryBtn')).forEach((button) => {
        button.addEventListener('click', () => vscode.postMessage({ command: 'openMemory', file: button.getAttribute('data-file') }));
      });
    }

    function renderSettings(config) {
      byId('settingOllama').value = config.ollamaUrl || '';
      byId('settingCore').value = config.coreUrl || '';
      byId('settingModel').value = config.chatModel || '';
      byId('settingFastModel').value = config.fastModel || '';
      byId('settingFallbacks').value = (config.fallbackModels || []).join(', ');
      byId('settingContext').value = config.maxContextChars || 62000;
      byId('settingMaxFiles').value = config.maxContextFiles != null ? config.maxContextFiles : 12;
      byId('settingAutopilotMin').value = config.autopilotIntervalMinutes != null ? config.autopilotIntervalMinutes : 15;
      byId('settingWriteMode').value = config.autopilotWriteMode || 'preview';
      byId('settingDiffTabs').value = config.maxProposalDiffTabs != null ? config.maxProposalDiffTabs : 12;
      byId('settingExcludeGlob').value = config.excludeGlob || '';
      byId('settingValidation').value = (config.validationCommandPreferences || []).join(', ');
      byId('settingSafety').value = config.safetyMode || 'standard';
      byId('settingAutoScan').checked = config.autoScanOnOpen !== false;
    }

    function escapeHtml(value) {
      return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    vscode.postMessage({ command: 'refresh' });
  </script>
</body>
</html>`;
}

const exportedApi = {
  activate,
  deactivate
};

if (process.env.AEGIS_EXTENSION_DEVTOOLS === '1' || fsSync.existsSync(path.join(__dirname, '.aegis-devtools'))) {
  exportedApi.__dev = {
    buildProjectSnapshot,
    getProjectSnapshot,
    detectValidationCommands,
    buildDependencyGraph,
    buildSymbolIndex,
    buildImpactAnalysis,
    buildFocusedProjectContext,
    projectSnapshotSummary,
    normalizeHttpBaseUrl,
    parseProposal,
    proposalObjectFromInstructionalCodeBlocks,
    validateProposalEdit,
    isBlockedRelativePath,
    makeWorkspaceTarget,
    applyProposal,
    rollbackLastAgentChange,
    detectValidationCommands,
    renderPanelHtml,
    buildDestinationReasoning,
    getEffectiveOllamaNumCtx,
    invalidateOllamaModelsCache
  };
}

module.exports = exportedApi;
