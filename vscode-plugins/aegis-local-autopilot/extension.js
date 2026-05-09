const vscode = require('vscode');
const http = require('http');
const https = require('https');
const path = require('path');
const fs = require('fs/promises');
const cp = require('child_process');

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
const snapshotCache = new Map();

const MAX_FILE_CHARS = 16000;
const MAX_CONTEXT_CHARS = 62000;
const MAX_PROJECT_SCAN_FILES = 900;
const MAX_PROJECT_SCAN_DEPTH = 7;
const MAX_GRAPH_FILES = 700;
const MAX_SYMBOL_FILES = 550;
const MAX_SYMBOLS = 2500;
const OLLAMA_CONTEXT_TOKENS = 32768;
const SNAPSHOT_CACHE_TTL_MS = 20000;
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
  'logs',
  'smoke-artifacts',
  'stress-artifacts'
]);
const SECRET_FILE_PATTERNS = [
  /^\.env(?:\.|$)/i,
  /(?:^|[._-])secret(?:s)?(?:[._-]|$)/i,
  /(?:^|[._-])credential(?:s)?(?:[._-]|$)/i,
  /(?:^|[._-])token(?:s)?(?:[._-]|$)/i,
  /(?:^|[._-])private(?:[._-]|$)/i,
  /\.(?:key|pem|pfx|p12|crt|cer)$/i
];
const LOCKFILE_PATTERNS = [
  /^package-lock\.json$/i,
  /^pnpm-lock\.yaml$/i,
  /^yarn\.lock$/i,
  /^bun\.lockb$/i,
  /^cargo\.lock$/i,
  /^poetry\.lock$/i
];
const IMPORTANT_FILE_PATTERNS = [
  /^readme(?:\..*)?$/i,
  /^todo(?:\..*)?$/i,
  /^changelog(?:\..*)?$/i,
  /^package\.json$/i,
  /^pnpm-lock\.yaml$/i,
  /^yarn\.lock$/i,
  /^package-lock\.json$/i,
  /^tsconfig(?:\..*)?\.json$/i,
  /^vite\.config\./i,
  /^next\.config\./i,
  /^webpack\.config\./i,
  /^pyproject\.toml$/i,
  /^requirements.*\.txt$/i,
  /^setup\.py$/i,
  /^cmakelists\.txt$/i,
  /^cargo\.toml$/i,
  /^go\.mod$/i,
  /^pom\.xml$/i,
  /^build\.gradle/i,
  /^dockerfile$/i,
  /^makefile$/i,
  /^projectversion\.txt$/i,
  /^packages-lock\.json$/i,
  /^.*\.(?:sln|csproj|vcxproj)$/i
];
const MAX_AGENT_REPAIR_ATTEMPTS = 3;

function activate(context) {
  extensionContext = context;
  output = vscode.window.createOutputChannel('Aegis Local Autopilot');
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

  output.appendLine('Aegis Local Autopilot activated.');
  logExtensionEvent('startup', 'Aegis Local Autopilot activated.').catch(() => {});
  initializeCurrentWorkspaceMemory().then(() => {
    registerAegisCoreClient().catch(() => {});
    refreshStatusBar().catch(() => {});
    recoverAgentStateIfNeeded().catch(reportError);
    runFirstRunSetup({ automatic: true }).catch(reportError);
  }).catch(reportError);
}

function deactivate() {
  stopAutopilot(false);
}

class LocalAutopilotViewProvider {
  constructor(extensionUri) {
    this.extensionUri = extensionUri;
    this.view = undefined;
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
        await runAutopilotOnce(message.text || '');
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
      models: []
    };

    try {
      state.models = await getOllamaModels();
      state.status = `Connected to Ollama with ${state.models.length} models.`;
      if (!latestErrorInfo.message && healthCheckState.overall !== 'fail' && agentState.status === 'Idle') {
        updateStatusBar('Ready', `Aegis connected to Ollama with ${state.models.length} model(s).`);
      }
    } catch (error) {
      state.status = `Ollama scan failed: ${error.message}`;
      updateStatusBar('Ollama Offline', state.status);
    }

    try {
      const target = await resolveWorkspaceTarget(undefined, { silent: true });
      if (target) {
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
      state.project = `Project scan failed: ${error.message}`;
    }

    this.post({ command: 'state', state });
  }
}

async function openPanel() {
  await vscode.commands.executeCommand('workbench.view.extension.aegis-local-ai');
}

async function scanModels(showPicker) {
  const models = await getOllamaModels();
  const names = models.map((model) => model.name || model.model).filter(Boolean);
  output.appendLine(`Detected ${names.length} Ollama models:`);
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
    const models = await getOllamaModels();
    modelNames = models.map((model) => model.name || model.model).filter(Boolean);
    ollamaStatus = `Ollama reachable. Found ${modelNames.length} model(s).`;
  } catch (error) {
    ollamaStatus = `Ollama check failed: ${error.message}`;
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
      detail: sanitizeMemoryText(String(detail || '')),
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
        addCheck('.aegis folder is writable', 'fail', error.message, 'Check project folder permissions and make sure antivirus is not blocking writes.');
      }
    }

    if (target) {
      try {
        await getAegisCoreHealth(target);
        addCheck('Aegis Core is reachable', 'pass', `Shared runtime responded at ${config.coreUrl}.`);
        await registerAegisCoreClient(target);
      } catch (error) {
        addCheck(
          'Aegis Core is reachable',
          'warn',
          error.message,
          'Start Aegis Core on the configured local URL to enable shared tasks, settings, diagnostics, and dashboard sync.'
        );
      }
    }

    try {
      const modelStart = Date.now();
      models = await getOllamaModels();
      addCheck('Ollama is reachable', 'pass', `Found ${models.length} installed model(s) in ${Date.now() - modelStart}ms.`);
    } catch (error) {
      addCheck('Ollama is reachable', 'fail', error.message, 'Start Ollama and confirm it is listening at the configured Ollama URL.');
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
      addCheck('VS Code extension storage works', 'fail', error.message, 'Reload VS Code or check whether extension storage is writable.');
    }

    try {
      const probe = await runShellProbe();
      addCheck('Terminal commands can run', probe.success ? 'pass' : 'fail', probe.output, probe.success ? '' : 'Check shell availability and VS Code permissions.');
    } catch (error) {
      addCheck('Terminal commands can run', 'fail', error.message, 'Check shell availability and VS Code permissions.');
    }

    if (target) {
      try {
        const backupRoot = path.join(target.workspaceRoot || target.root, '.aegis', 'backups', `health-check-${timestampForPath()}`);
        await fs.mkdir(backupRoot, { recursive: true });
        await fs.writeFile(path.join(backupRoot, 'probe.txt'), 'backup probe\n', 'utf8');
        await fs.rm(backupRoot, { recursive: true, force: true });
        addCheck('Backups can be created', 'pass', '.aegis/backups accepted a create/delete probe.');
      } catch (error) {
        addCheck('Backups can be created', 'fail', error.message, 'Check project folder permissions for .aegis/backups.');
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
        addCheck('Dependency and symbol indexes can be written', 'fail', error.message, 'Check .aegis write permissions and whether scanned files are readable.');
      }
    }
  } catch (error) {
    addCheck('Health check runner', 'fail', error.message, 'Open the Aegis output panel for details, then retry.');
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
    const models = await getOllamaModels();
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
      detail: error.message
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
        output: truncateMiddle([stdout, stderr, error ? error.message : ''].filter(Boolean).join('\n') || 'Shell probe completed.', 2000)
      });
    });
  });
}

function buildContextSizeWarning(config) {
  const maxChars = Number(config.maxContextChars || MAX_CONTEXT_CHARS);
  const estimatedTokens = Math.ceil(maxChars / 4);
  if (estimatedTokens > OLLAMA_CONTEXT_TOKENS * 0.85) {
    return `Configured max context is about ${estimatedTokens} tokens, close to or above the Ollama request context of ${OLLAMA_CONTEXT_TOKENS}. Lower maxContextChars if prompts fail or slow down.`;
  }
  return `Configured max context is about ${estimatedTokens} tokens, within the current Ollama request context of ${OLLAMA_CONTEXT_TOKENS}.`;
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
  const context = await collectWorkspaceContext('Panel chat context', target);
  const chatMemory = await buildChatMemoryContext(target);
  const prompt = [
    'You are Aegis Local Autopilot inside VS Code.',
    'Answer using the local project context. Be concise, specific, and practical.',
    `Current target folder: ${target.root}`,
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
  panelProvider.post({ command: 'chatResult', text: response });
  panelProvider.post({ command: 'chatHistory', chatHistory });
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
  activeCoreTaskId = await createAegisCoreTask(target, request, 'vscode-agent', request, {
    model: config.chatModel,
    safetyMode: config.safetyMode
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
  pushProgress('Inspecting workspace', 'Scanning structure, project memory, diagnostics, and validation hints.');

  await ensureWorkspaceMemory(target);
  const snapshot = await getProjectSnapshot(target);
  pushProgress('Updating project memory', `${snapshot.fileCount} files sampled for current workspace context.`);
  await updateWorkspaceMemoryFromSnapshot(target, snapshot);
  const memoryContext = await readWorkspaceMemoryContext(target);
  const dependencyGraph = await readJsonMemoryFile(target, 'dependency-graph.json', null);
  const symbolIndex = await readJsonMemoryFile(target, 'symbol-index.json', null);
  const impactAnalysis = await buildImpactAnalysis(target, snapshot, request, dependencyGraph, symbolIndex);
  lastImpactAnalysis = impactAnalysis;
  pushProgress('Building impact analysis', `${impactAnalysis.likelyAffectedFiles.length} likely affected file(s), risk ${impactAnalysis.riskLevel}.`);
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

  updateAgentState({ status: 'Creating plan' });
  pushProgress('Calling local model', `Using ${config.chatModel} to create a small approval-based plan.`);
  const proposal = await createAgentProposal(target, request, context, 0);
  enrichProposalWithRepoIntelligence(proposal, impactAnalysis);
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
  pushProgress('Waiting for approval', `${proposal.fileEdits.length} proposed file change(s) are ready for review.`);

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

  await runValidationAndRepairLoop(target, request, proposal, snapshot);
  if (!/repair paused|waiting|paused/i.test(agentState.status || '')) {
    await clearAgentRecovery(target);
  }
}

async function createAgentProposal(target, request, context, repairAttempt, validationFailure) {
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
    timeoutMs: 900000
  });
  return parseProposal(raw, target, request);
}

async function runValidationAndRepairLoop(target, request, initialProposal, initialSnapshot) {
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

  for (let attempt = 1; attempt <= MAX_AGENT_REPAIR_ATTEMPTS; attempt += 1) {
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
    const repairProposal = await createAgentProposal(target, request, context, attempt, failure);
    enrichProposalWithRepoIntelligence(repairProposal, impactAnalysis);
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

  const context = await collectWorkspaceContext(task, target);
  const prompt = buildAutopilotPrompt(task, context);
  const raw = await askOllamaWithFallback(config.chatModel, prompt, { temperature: 0.15, json: true, timeoutMs: 900000 });
  const proposal = parseProposal(raw, target, task);
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

  await showProposalPreview(proposal);

  panelProvider && panelProvider.refresh();
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
  const blocked = validations.filter((item) => !item.ok);
  if (blocked.length) {
    output.appendLine('Blocked unsafe proposal edits:');
    blocked.forEach((item) => output.appendLine(`- ${item.edit.path}: ${item.reason}`));
    vscode.window.showWarningMessage(`Aegis blocked ${blocked.length} unsafe proposed edit(s). Review the proposal document.`);
    return 'blocked';
  }

  if (options.staged && hasEditableStages(proposal)) {
    return await showStagedProposalPreview(proposal, validations, options);
  }

  await openProposalDiffs(proposal, validations);
  const answer = await vscode.window.showInformationMessage(
    options.repairAttempt
      ? `Aegis proposed repair ${options.repairAttempt} with ${proposal.fileEdits.length} file change(s). Review the diff before applying.`
      : `Aegis proposed ${proposal.fileEdits.length} file change(s). Review the diff before applying.`,
    'Apply Accepted Changes',
    'Open Diffs Again',
    'Reject'
  );
  if (answer === 'Apply Accepted Changes') {
    const applied = await applyProposal(proposal, { skipPrompt: true });
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
      const applied = await applyProposal(remainingProposal, { skipPrompt: true, stageName: 'Remaining edits' });
      appliedAny = appliedAny || applied;
    }
  }

  return appliedAny ? 'applied' : 'no-edits';
}

async function openProposalDiffs(proposal, validations) {
  const stateRoot = proposal.workspaceRoot || proposal.workspace || proposal.targetRoot;
  const previewRoot = path.join(stateRoot, '.aegis', 'vscode-autopilot', 'previews', timestampForPath());
  const safeValidations = validations.filter((item) => item.ok).slice(0, 5);

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
    vscode.window.showErrorMessage(`Aegis refused to apply ${blocked.length} unsafe edit(s). No files were changed.`);
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
      output.appendLine(`Aegis partial apply restore failed: ${restoreError.message}`);
    });
    await logExtensionEvent('apply-error', 'Apply failed; attempted to restore partial edits from backup.', {
      error: error.message,
      backupId,
      restoredFiles: manifest.files.map((file) => file.workspaceRelativePath || file.path)
    }, { workspaceRoot: stateRoot, root });
    throw error;
  }

  await fs.writeFile(path.join(backupRoot, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
  await recordChangeBackup({ workspaceRoot: stateRoot, root }, manifest);
  clearProjectSnapshotCache(root);

  vscode.window.showInformationMessage(`Applied local proposal. Backup: ${backupRoot}`);
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
  const entries = await scanProjectEntries(root, {
    maxFiles: options.fast ? 220 : MAX_PROJECT_SCAN_FILES,
    maxDepth: options.fast ? 4 : MAX_PROJECT_SCAN_DEPTH
  });
  const files = entries.filter((entry) => entry.type === 'file');
  const directories = entries.filter((entry) => entry.type === 'directory');
  const importantFiles = files
    .filter((entry) => IMPORTANT_FILE_PATTERNS.some((pattern) => pattern.test(path.basename(entry.relative))))
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
  const importantContents = [];

  for (const file of importantFiles.slice(0, options.fast ? 8 : 20)) {
    const text = await readWorkspaceFile(root, file.relative);
    if (text) {
      importantContents.push({
        path: file.relative,
        text: truncateMiddle(text, file.relative.toLowerCase().endsWith('package.json') ? 12000 : 6000)
      });
    }
  }

  const topLevel = await readTopLevel(root);
  const fileTypes = countFileTypes(files);
  const languageInfo = inferProjectLanguages(files, importantContents);
  const commandInfo = inferProjectCommands(importantContents, files);
  const todoChunks = await collectTodoContext(Math.min(getConfig().maxContextFiles, options.fast ? 5 : 12), getConfig().excludeGlob, root);
  const diagnostics = collectDiagnostics(target);

  return {
    target,
    generatedAt: new Date().toISOString(),
    files,
    directories,
    fileCount: files.length,
    directoryCount: directories.length,
    topLevel,
    fileTypes,
    importantFiles: importantFiles.map((file) => file.relative),
    testFiles,
    configFiles,
    entryPoints,
    recentFiles,
    importantContents,
    languages: languageInfo.languages,
    frameworks: languageInfo.frameworks,
    packageManagers: languageInfo.packageManagers,
    commands: commandInfo,
    todoChunks,
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
  const counts = new Map();
  for (const file of files) {
    const ext = path.extname(file.relative).toLowerCase() || '[no extension]';
    counts.set(ext, (counts.get(ext) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 16)
    .map(([ext, count]) => `${ext}: ${count}`);
}

function isLikelyTestFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  return /(^|\/)(test|tests|spec|specs|__tests__)\//.test(normalized) ||
    /\.(test|spec)\.(js|jsx|ts|tsx|py|cs|rs|go|java)$/.test(normalized) ||
    /(_test\.go|test_.*\.py|.*_test\.py)$/.test(normalized);
}

function isLikelyConfigFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  const basename = path.basename(normalized);
  return IMPORTANT_FILE_PATTERNS.some((pattern) => pattern.test(basename)) ||
    /\.(config|conf|ini|toml|yaml|yml|jsonc)$/.test(normalized) ||
    /^(\.eslintrc|\.prettierrc|\.babelrc|dockerfile|makefile)/.test(basename);
}

function detectEntryPoints(files) {
  const candidates = [
    'src/main.ts',
    'src/main.tsx',
    'src/index.ts',
    'src/index.tsx',
    'src/App.tsx',
    'src/app.tsx',
    'src/main.cpp',
    'src/main.c',
    'main.py',
    'app.py',
    'server.py',
    'Program.cs',
    'main.go',
    'src/main.rs',
    'ProjectSettings/ProjectVersion.txt',
    'Assets/Scenes/Main.unity'
  ];
  const fileSet = new Set(files.map((file) => file.relative.replace(/\\/g, '/')));
  const entries = candidates.filter((candidate) => fileSet.has(candidate));
  for (const file of files) {
    const normalized = file.relative.replace(/\\/g, '/');
    if (/^(pages|app)\/.*\.(tsx|ts|jsx|js)$/.test(normalized) && entries.length < 12) {
      entries.push(normalized);
    }
  }
  return Array.from(new Set(entries)).slice(0, 20);
}

function inferProjectLanguages(files, importantContents) {
  const languages = new Set();
  const frameworks = new Set();
  const packageManagers = new Set();
  const names = new Set(files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  const extensions = new Set(files.map((file) => path.extname(file.relative).toLowerCase()));
  const hasUnityProject = names.has('projectsettings/projectversion.txt') || names.has('packages/manifest.json') || Array.from(names).some((name) => name.startsWith('assets/') && name.endsWith('.unity'));

  if (extensions.has('.ts') || extensions.has('.tsx')) languages.add('TypeScript');
  if (extensions.has('.js') || extensions.has('.jsx') || names.has('package.json')) languages.add('JavaScript');
  if (extensions.has('.py') || names.has('pyproject.toml') || names.has('requirements.txt')) languages.add('Python');
  if (extensions.has('.cpp') || extensions.has('.cc') || extensions.has('.c') || extensions.has('.h') || extensions.has('.hpp')) languages.add('C/C++');
  if (extensions.has('.cs') || Array.from(names).some((name) => name.endsWith('.csproj') || name.endsWith('.sln'))) languages.add('C#/.NET');
  if (extensions.has('.rs') || names.has('cargo.toml')) languages.add('Rust');
  if (extensions.has('.go') || names.has('go.mod')) languages.add('Go');
  if (extensions.has('.java') || names.has('pom.xml') || Array.from(names).some((name) => name.includes('build.gradle'))) languages.add('Java/JVM');
  if (hasUnityProject) {
    languages.add('C#/.NET');
    frameworks.add('Unity');
  }

  if (names.has('pnpm-lock.yaml')) packageManagers.add('pnpm');
  if (names.has('yarn.lock')) packageManagers.add('yarn');
  if (names.has('package-lock.json')) packageManagers.add('npm');
  if (names.has('bun.lockb')) packageManagers.add('bun');
  if (names.has('package.json') && packageManagers.size === 0) packageManagers.add('npm');

  for (const item of importantContents) {
    if (path.basename(item.path).toLowerCase() !== 'package.json') {
      continue;
    }
    try {
      const pkg = parseJsonText(item.text);
      const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
      if (deps.react) frameworks.add('React');
      if (deps.next) frameworks.add('Next.js');
      if (deps.vue) frameworks.add('Vue');
      if (deps.svelte) frameworks.add('Svelte');
      if (deps.vite) frameworks.add('Vite');
      if (deps.express) frameworks.add('Express');
      if (deps.electron) frameworks.add('Electron');
      if (deps.typescript) languages.add('TypeScript');
    } catch (error) {
      // Ignore malformed package snippets; this is only a scan hint.
    }
  }

  if (names.has('vite.config.ts') || names.has('vite.config.js')) frameworks.add('Vite');
  if (names.has('next.config.js') || names.has('next.config.mjs') || names.has('next.config.ts')) frameworks.add('Next.js');
  if (names.has('cmakelists.txt')) frameworks.add('CMake');
  if (names.has('pyproject.toml')) frameworks.add('Python packaging');

  return {
    languages: Array.from(languages),
    frameworks: Array.from(frameworks),
    packageManagers: Array.from(packageManagers)
  };
}

function inferProjectCommands(importantContents, files) {
  const commands = [];
  const names = new Set(files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));

  for (const item of importantContents) {
    if (path.basename(item.path).toLowerCase() === 'package.json') {
      try {
        const pkg = parseJsonText(item.text);
        const scripts = pkg.scripts || {};
        for (const name of ['build', 'test', 'lint', 'typecheck', 'type-check', 'check', 'dev']) {
          if (scripts[name]) {
            commands.push(`npm run ${name}`);
          }
        }
      } catch (error) {
        // Ignore malformed package snippets.
      }
    }
  }

  if (names.has('cmakelists.txt')) commands.push('cmake --build build');
  if (Array.from(names).some((name) => name.endsWith('.sln'))) commands.push('msbuild <solution>.sln');
  if (names.has('pyproject.toml')) commands.push('python -m pytest');
  if (names.has('requirements.txt')) commands.push('python -m pytest');
  if (names.has('cargo.toml')) commands.push('cargo test');
  if (names.has('go.mod')) commands.push('go test ./...');

  return Array.from(new Set(commands)).slice(0, 12);
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
  chunks.push(`# Target Folder\n${snapshot.target.root}`);
  chunks.push(`# Workspace Root\n${snapshot.target.workspaceRoot || snapshot.target.root}`);
  chunks.push(`# Objective\n${objective}`);
  chunks.push('Generated file edit paths must be relative to the target folder, not absolute paths.');
  chunks.push(`# Project Summary\n${projectSnapshotSummary(snapshot)}`);
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
  const specs = new Set();
  const patterns = [
    /import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g,
    /require\(\s*['"]([^'"]+)['"]\s*\)/g,
    /from\s+['"]([^'"]+)['"]/g
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      specs.add(match[1]);
    }
  }
  return Array.from(specs).slice(0, 30);
}

function importCandidatePaths(base) {
  const extensions = ['', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.css', '.scss', '.json'];
  const candidates = [];
  for (const ext of extensions) {
    candidates.push(`${base}${ext}`.replace(/\\/g, '/'));
  }
  for (const ext of extensions.filter(Boolean)) {
    candidates.push(`${base}/index${ext}`.replace(/\\/g, '/'));
  }
  return candidates;
}

function selectRelevantFiles(snapshot, request, options = {}) {
  const score = new Map();
  const knownFiles = new Set((snapshot.files || []).map((file) => file.relative.replace(/\\/g, '/')));
  const add = (file, points) => {
    const normalized = String(file || '').replace(/\\/g, '/').replace(/^\/+/, '');
    if (!normalized || normalized === '.' || normalized.endsWith('/') || !knownFiles.has(normalized) || isBlockedRelativePath(normalized)) {
      return;
    }
    score.set(normalized, (score.get(normalized) || 0) + points);
  };
  const requestText = `${request || ''}\n${options.validationText || ''}`.toLowerCase();
  const terms = requestText
    .replace(/[^a-z0-9_./-]+/g, ' ')
    .split(/\s+/)
    .filter((term) => term.length >= 3)
    .slice(0, 80);

  for (const file of snapshot.importantFiles || []) add(file, 10);
  for (const file of snapshot.entryPoints || []) add(file, 14);
  for (const file of snapshot.configFiles || []) add(file, 8);
  for (const item of (snapshot.recentFiles || []).slice(0, 12)) add(item.path, 5);
  for (const diagnostic of snapshot.diagnostics || []) {
    const match = diagnostic.match(/^- ([^:]+):/);
    if (match) add(match[1], 16);
  }
  for (const hintedFile of extractFileHintsFromText(options.validationText || requestText, snapshot)) {
    add(hintedFile, 18);
  }

  const editor = vscode.window.activeTextEditor;
  if (editor && editor.document.uri.scheme === 'file' && isPathInside(snapshot.target.root, editor.document.uri.fsPath)) {
    add(path.relative(snapshot.target.root, editor.document.uri.fsPath).replace(/\\/g, '/'), 20);
  }

  for (const file of snapshot.files) {
    const normalized = file.relative.replace(/\\/g, '/');
    const lower = normalized.toLowerCase();
    for (const term of terms) {
      if (lower.includes(term)) {
        add(normalized, 7);
      }
    }
  }

  for (const file of inferDependencyLinks(snapshot, Array.from(score.keys()).slice(0, 8))) {
    add(file, 6);
  }
  if (options.dependencyGraph && Array.isArray(options.dependencyGraph.edges)) {
    const seeds = Array.from(score.keys()).slice(0, 12);
    const seedSet = new Set(seeds);
    for (const edge of options.dependencyGraph.edges) {
      if (seedSet.has(edge.from)) add(edge.to, 6);
      if (seedSet.has(edge.to)) add(edge.from, 4);
    }
  }
  if (options.symbolIndex && Array.isArray(options.symbolIndex.symbols)) {
    for (const symbol of options.symbolIndex.symbols.slice(0, MAX_SYMBOLS)) {
      const haystack = `${symbol.name || ''} ${symbol.kind || ''}`.toLowerCase();
      if (terms.some((term) => haystack.includes(term))) {
        add(symbol.file, 9);
      }
    }
  }

  return Array.from(score.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, options.maxFiles || 14)
    .map(([file]) => file);
}

function extractFileHintsFromText(text, snapshot) {
  if (!text) {
    return [];
  }
  const fileSet = new Set((snapshot.files || []).map((file) => file.relative.replace(/\\/g, '/')));
  const hints = new Set();
  const patterns = [
    /([A-Za-z0-9_./\\-]+\.(?:js|jsx|ts|tsx|py|cs|rs|go|java|cpp|c|h|hpp|json|toml|yaml|yml|md))(?::\d+)?/g,
    /File "([^"]+\.(?:py|js|ts|tsx|cs))", line \d+/g
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const raw = (match[1] || '').replace(/\\/g, '/').replace(/^[A-Za-z]:\//, '');
      const exact = Array.from(fileSet).find((file) => file === raw || raw.endsWith(`/${file}`));
      if (exact) {
        hints.add(exact);
      }
      if (hints.size >= 20) {
        return Array.from(hints);
      }
    }
  }
  return Array.from(hints);
}

function expandSelectedFilesWithGraph(graph, selectedFiles, maxFiles) {
  if (!graph || !Array.isArray(graph.edges) || selectedFiles.length >= maxFiles) {
    return selectedFiles.slice(0, maxFiles);
  }
  const selected = new Set(selectedFiles);
  const seeds = selectedFiles.slice(0, 8);
  for (const edge of graph.edges) {
    if (selected.size >= maxFiles) break;
    if (seeds.includes(edge.from) && edge.to) selected.add(edge.to);
    if (selected.size >= maxFiles) break;
    if (seeds.includes(edge.to) && edge.from) selected.add(edge.from);
  }
  return Array.from(selected).slice(0, maxFiles);
}

function inferDependencyLinks(snapshot, seedFiles) {
  const linked = new Set();
  const fileSet = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/')));
  for (const seed of seedFiles) {
    const dir = path.dirname(seed).replace(/\\/g, '/');
    const base = path.basename(seed, path.extname(seed)).toLowerCase();
    for (const file of fileSet) {
      const normalized = file.replace(/\\/g, '/');
      const sameDir = dir === '.' || normalized.startsWith(`${dir}/`);
      const fileBase = path.basename(normalized, path.extname(normalized)).toLowerCase();
      if (sameDir && (fileBase === `${base}.test` || fileBase === `${base}.spec` || fileBase === base)) {
        linked.add(normalized);
      }
    }
  }
  return Array.from(linked);
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
      output.appendLine(`Skipped TODO scan for ${uri.fsPath}: ${error.message}`);
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
    'Suggest changes first. Do not assume edits will be applied automatically.',
    'Do not invent files unless they are clearly useful. Do not include binary files, secrets, env files, build output, vendor folders, or dependencies.',
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
    'Paths in fileEdits must be relative to the target folder shown in the context.',
    'Keep fileEdits small and focused. A safe development plan with no edits is better than broad speculative rewrites.',
    'For broad requests, propose at most 1-3 files in the first step unless the user explicitly asks for a larger staged change.',
    'Only edit files included in the selected context or directly connected by imports/tests. If you must create a new file, explain why in reason.',
    'Each file edit reason must say why that file is being changed and why the change is minimal.',
    'For multi-file work, divide proposed edits into staged approvals. Every stage must be independently reviewable.',
    'When editing code, identify related tests and include test updates or test recommendations.',
    'Only include fileEdits when the complete replacement content is reasonably small and you are confident.',
    'If no safe edit is obvious, return notes and commands with an empty fileEdits array.',
    '',
    `Objective:\n${objective}`,
    '',
    `Workspace context:\n${context}`
  ].join('\n');
}

function parseProposal(raw, target, objective) {
  let parsed;
  try {
    parsed = parseJsonText(extractJson(raw));
  } catch (error) {
    parsed = {
      summary: 'Model returned non-JSON output; saved as notes.',
      risk: 'medium',
      notes: [raw],
      fileEdits: [],
      commands: [],
      tests: []
    };
  }

  const fileEdits = Array.isArray(parsed.fileEdits) ? parsed.fileEdits : [];
  const commands = Array.isArray(parsed.commands) ? parsed.commands : [];
  const proposal = {
    objective,
    createdAt: new Date().toISOString(),
    workspace: target.root,
    targetRoot: target.root,
    targetLabel: target.label,
    workspaceRoot: target.workspaceRoot || target.root,
    summary: String(parsed.summary || '').trim(),
    risk: String(parsed.risk || 'medium').trim(),
    confidenceScore: normalizeConfidenceScore(parsed.confidenceScore),
    approachRationale: sanitizeMemoryText(String(parsed.approachRationale || parsed.rationale || '').trim()),
    notes: Array.isArray(parsed.notes) ? parsed.notes.map(String) : [],
    fileEdits: fileEdits
      .filter((edit) => edit && typeof edit.path === 'string' && typeof edit.content === 'string')
      .map((edit) => ({
        path: edit.path.replace(/\\/g, '/').replace(/^\/+/, ''),
        reason: String(edit.reason || ''),
        content: normalizeLineEndings(edit.content)
      })),
    commands: commands
      .filter((command) => command && typeof command.command === 'string')
      .map((command) => ({
        command: command.command,
        reason: String(command.reason || '')
      })),
    tests: Array.isArray(parsed.tests) ? parsed.tests.map(String) : [],
    impactAnalysis: normalizeModelImpactAnalysis(parsed.impactAnalysis),
    stages: normalizeModelStages(parsed.stages)
  };
  proposal.stages = normalizeProposalStages(proposal, proposal.impactAnalysis);
  return proposal;
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

async function getOllamaModels() {
  const json = await requestJson(new URL('/api/tags', getConfig().ollamaUrl), undefined, 120000);
  return Array.isArray(json.models) ? json.models : [];
}

async function getAegisCoreHealth(target) {
  const workspace = target && target.root ? target.root : '';
  const url = new URL('/v1/health', getConfig().coreUrl);
  if (workspace) {
    url.searchParams.set('workspace', workspace);
  }
  return requestJson(url, undefined, 120000);
}

async function registerAegisCoreClient(target) {
  const resolvedTarget = target || await resolveWorkspaceTarget(undefined, { silent: true });
  if (!resolvedTarget) {
    return false;
  }
  try {
    await requestJson(new URL('/v1/clients/register', getConfig().coreUrl), {
      workspace: resolvedTarget.root,
      client_id: 'aegis-vscode',
      client_type: 'vscode-extension',
      name: 'Aegis Local Agent for VS Code',
      version: extensionContext && extensionContext.extension && extensionContext.extension.packageJSON
        ? extensionContext.extension.packageJSON.version || 'unknown'
        : 'unknown',
      capabilities: ['workspace-scan', 'diff-preview', 'terminal-validation', 'safe-apply']
    }, 120000);
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis Core registration skipped: ${error.message}`);
    return false;
  }
}

async function createAegisCoreTask(target, title, kind, request, metadata = {}) {
  try {
    const response = await requestJson(new URL('/v1/tasks', getConfig().coreUrl), {
      workspace: target.root,
      title,
      kind,
      source_client: 'vscode-extension',
      request,
      metadata
    }, 120000);
    return response && response.data && response.data.id ? response.data.id : '';
  } catch (error) {
    output && output.appendLine(`Aegis Core task creation skipped: ${error.message}`);
    return '';
  }
}

async function updateAegisCoreTaskStatus(target, taskId, status, summary = '') {
  if (!taskId) {
    return false;
  }
  try {
    await requestJson(new URL(`/v1/tasks/${encodeURIComponent(taskId)}/status`, getConfig().coreUrl), {
      workspace: target.root,
      status,
      summary
    }, 120000);
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis Core task update skipped: ${error.message}`);
    return false;
  }
}

async function askOllamaWithFallback(model, prompt, options = {}) {
  const config = getConfig();
  const candidates = [model || config.chatModel, ...config.fallbackModels].filter(Boolean);
  const uniqueCandidates = Array.from(new Set(candidates));
  let lastError;

  for (const candidate of uniqueCandidates) {
    try {
      return await askOllama(candidate, prompt, options);
    } catch (error) {
      lastError = error;
      output.appendLine(`Ollama model ${candidate} failed: ${error.message}`);
      logExtensionEvent('model-call', `Ollama model ${candidate} failed.`, { error: error.message }).catch(() => {});
    }
  }

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
      num_ctx: 32768
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
  const json = await requestJson(new URL('/api/chat', getConfig().ollamaUrl), body, options.timeoutMs || 600000);
  const elapsed = ((Date.now() - started) / 1000).toFixed(1);
  const content = json && json.message && typeof json.message.content === 'string' ? json.message.content : JSON.stringify(json);
  output.appendLine(`Ollama ${selectedModel} completed in ${elapsed}s.`);
  logExtensionEvent('model-call', `Ollama ${selectedModel} completed.`, {
    elapsedSeconds: elapsed,
    responseChars: content.length
  }).catch(() => {});
  return content.trim();
}

function requestJson(url, body, timeoutMs) {
  return new Promise((resolve, reject) => {
    const isHttps = url.protocol === 'https:';
    const data = body ? Buffer.from(JSON.stringify(body), 'utf8') : undefined;
    const request = (isHttps ? https : http).request({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port,
      path: `${url.pathname}${url.search}`,
      method: body ? 'POST' : 'GET',
      headers: body
        ? {
            'Content-Type': 'application/json',
            'Content-Length': data.length
          }
        : {}
    }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error(`HTTP ${response.statusCode}: ${text}`));
          return;
        }
        try {
          resolve(parseJsonText(text));
        } catch (error) {
          reject(new Error(`Invalid JSON from ${url.href}: ${error.message}`));
        }
      });
    });

    request.on('error', reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`Timed out calling ${url.href}`));
    });

    if (data) {
      request.write(data);
    }
    request.end();
  });
}

function activeEditorContext(editor) {
  const rel = vscode.workspace.asRelativePath(editor.document.uri, false);
  const text = editor.document.getText();
  return formatFileChunk(rel, text);
}

async function readWorkspaceFile(root, rel) {
  const target = resolveInside(root, rel);
  if (!target) {
    return '';
  }
  try {
    const stat = await fs.stat(target);
    if (!stat.isFile() || stat.size > 512000) {
      return '';
    }
    return await fs.readFile(target, 'utf8');
  } catch (error) {
    return '';
  }
}

function formatFileChunk(rel, text) {
  return `# File: ${rel}\n\`\`\`\n${truncateMiddle(text, MAX_FILE_CHARS)}\n\`\`\``;
}

function truncateMiddle(text, maxChars) {
  if (!text || text.length <= maxChars) {
    return text || '';
  }
  const half = Math.floor(maxChars / 2);
  return `${text.slice(0, half)}\n\n[...truncated...]\n\n${text.slice(text.length - half)}`;
}

function extractJson(raw) {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced) {
    return fenced[1].trim();
  }
  const first = raw.indexOf('{');
  const last = raw.lastIndexOf('}');
  if (first !== -1 && last !== -1 && last > first) {
    return raw.slice(first, last + 1);
  }
  return raw;
}

function parseJsonText(text) {
  return JSON.parse(stripUtf8Bom(String(text || '')));
}

function stripUtf8Bom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

function normalizeLineEndings(text) {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function resolveInside(root, relativePath) {
  if (!relativePath || path.isAbsolute(relativePath)) {
    return undefined;
  }
  const target = path.resolve(root, relativePath);
  const normalizedRoot = path.resolve(root);
  if (isPathInside(normalizedRoot, target)) {
    return target;
  }
  return undefined;
}

function validateProposalEdit(proposal, edit) {
  const root = proposal.workspace || proposal.targetRoot;
  if (!root) {
    return { ok: false, edit, reason: 'Proposal has no target workspace root.' };
  }
  if (!edit || typeof edit.path !== 'string') {
    return { ok: false, edit: edit || { path: '<missing>' }, reason: 'Proposal edit is missing a relative path.' };
  }
  if (path.isAbsolute(edit.path)) {
    return { ok: false, edit, reason: 'Absolute paths are not allowed.' };
  }
  const normalizedPath = edit.path.replace(/\\/g, '/').replace(/^\/+/, '');
  if (isBlockedRelativePath(normalizedPath)) {
    return { ok: false, edit, reason: 'Path is blocked by safety rules.' };
  }
  const basename = path.basename(normalizedPath);
  if (LOCKFILE_PATTERNS.some((pattern) => pattern.test(basename)) && !/lockfile|dependency resolution|required|explicit/i.test(edit.reason || '')) {
    return { ok: false, edit, reason: 'Lockfile edits require an explicit model reason.' };
  }
  if (typeof edit.content !== 'string') {
    return { ok: false, edit, reason: 'Proposal edit is missing replacement content.' };
  }
  if (edit.content.length > 500000) {
    return { ok: false, edit, reason: 'Replacement content is too large for safe apply.' };
  }
  const target = resolveInside(root, normalizedPath);
  if (!target) {
    return { ok: false, edit, reason: 'Path would write outside the current project folder.' };
  }
  return { ok: true, edit: Object.assign({}, edit, { path: normalizedPath }), target, relative: normalizedPath };
}

function isBlockedRelativePath(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').replace(/^\/+/, '');
  const segments = normalized.split('/').filter(Boolean);
  if (!segments.length) {
    return true;
  }
  for (const segment of segments) {
    if (BLOCKED_PATH_SEGMENTS.has(segment.toLowerCase())) {
      return true;
    }
  }
  const basename = segments[segments.length - 1] || '';
  return SECRET_FILE_PATTERNS.some((pattern) => pattern.test(basename));
}

function timestampForPath() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function isSafeBackupId(value) {
  return typeof value === 'string' && /^[A-Za-z0-9_.-]+$/.test(value) && value.length <= 120;
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
  return Object.assign({}, proposal, {
    approachRationale: sanitizeMemoryText(String(proposal.approachRationale || '')),
    confidenceScore: normalizeConfidenceScore(proposal.confidenceScore),
    notes: Array.isArray(proposal.notes) ? proposal.notes.map((note) => sanitizeMemoryText(String(note))).slice(0, 12) : [],
    fileEdits: Array.isArray(proposal.fileEdits)
      ? proposal.fileEdits.map((edit) => ({
          path: edit.path,
          reason: sanitizeMemoryText(String(edit.reason || '')),
          contentLength: typeof edit.content === 'string' ? edit.content.length : 0,
          content: '[not stored in local history]'
        }))
      : []
  });
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
    output.appendLine(`Could not clear Aegis recovery state: ${error.message}`);
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

async function rollbackLastAgentChange(resource) {
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

  const answer = await vscode.window.showWarningMessage(
    `Rollback last Aegis change from ${manifest.createdAt || manifest.backupId}? This restores ${manifest.files.length} file(s) from .aegis/backups.`,
    { modal: true },
    'Rollback'
  );
  if (answer !== 'Rollback') {
    return;
  }

  const workspaceRoot = target.workspaceRoot || target.root;
  const backupsRoot = path.join(memoryRoot, 'backups');
  const backupRoot = resolveInside(backupsRoot, manifest.backupId);
  if (!backupRoot) {
    vscode.window.showErrorMessage('The last Aegis backup path is outside the workspace backup folder. Rollback was not started.');
    return;
  }
  const restored = [];
  restored.push(...await restoreFromManifest(backupRoot, manifest, { workspaceRoot }));

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
      const backupBytes = await fs.readFile(backupPath);
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
  return {
    status: 'Idle',
    model: '',
    workspace: '',
    currentTask: '',
    activePlan: '',
    pendingDiffs: [],
    validationOutput: '',
    repairAttempts: 0,
    progressItems: [],
    contextFiles: []
  };
}

function makeEmptyHealthCheckState() {
  return {
    overall: 'unknown',
    checkedAt: '',
    elapsedMs: 0,
    checks: []
  };
}

function makeEmptyModelDiagnosticsState() {
  return {
    checkedAt: '',
    installedModels: [],
    primary: undefined,
    fallbacks: [],
    contextWarning: ''
  };
}

function makeEmptyErrorInfo() {
  return {
    at: '',
    message: '',
    failedCommand: '',
    stack: '',
    likelyCause: '',
    suggestedFix: '',
    retryCommand: ''
  };
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
  const item = {
    at: new Date().toLocaleTimeString(),
    label: sanitizeMemoryText(String(label || 'Working')),
    detail: sanitizeMemoryText(String(detail || ''))
  };
  const progressItems = [item, ...(agentState.progressItems || [])].slice(0, 8);
  updateAgentState({ progressItems });
}

function setContextFiles(files, reason) {
  updateAgentState({
    contextFiles: (files || []).slice(0, 18).map((file) => ({
      path: file,
      reason: sanitizeMemoryText(reason || 'Relevant to the current request.')
    }))
  });
}

function proposalToPlanText(proposal) {
  const lines = [];
  lines.push(proposal.summary || 'No summary returned.');
  if (proposal.risk) {
    lines.push(`Risk: ${proposal.risk}`);
  }
  if (proposal.confidenceScore !== undefined) {
    lines.push(`Confidence: ${Math.round(normalizeConfidenceScore(proposal.confidenceScore) * 100)}%`);
  }
  if (proposal.approachRationale) {
    lines.push(`Approach: ${proposal.approachRationale}`);
  }
  if (proposal.notes && proposal.notes.length) {
    lines.push('');
    lines.push('Notes:');
    proposal.notes.slice(0, 8).forEach((note) => lines.push(`- ${note}`));
  }
  if (proposal.impactAnalysis) {
    lines.push('');
    lines.push('Impact analysis:');
    lines.push(...impactAnalysisToLines(proposal.impactAnalysis));
  }
  if (proposal.stages && proposal.stages.length) {
    lines.push('');
    lines.push('Staged plan:');
    proposal.stages.forEach((stage, index) => {
      lines.push(`- ${index + 1}. ${stage.name || stage.title || 'Stage'}${stage.risk ? ` (${stage.risk})` : ''}: ${stage.goal || 'Review and approve this stage.'}`);
      if (stage.files && stage.files.length) {
        lines.push(`  Files: ${stage.files.slice(0, 8).join(', ')}`);
      }
    });
  }
  if (proposal.fileEdits && proposal.fileEdits.length) {
    lines.push('');
    lines.push('Proposed file changes:');
    proposal.fileEdits.forEach((edit) => lines.push(`- ${edit.path}${edit.reason ? `: ${edit.reason}` : ''}`));
  }
  if (proposal.commands && proposal.commands.length) {
    lines.push('');
    lines.push('Suggested commands:');
    proposal.commands.forEach((item) => lines.push(`- ${item.command}${item.reason ? `: ${item.reason}` : ''}`));
  }
  if (proposal.tests && proposal.tests.length) {
    lines.push('');
    lines.push('Validation notes:');
    proposal.tests.forEach((item) => lines.push(`- ${item}`));
  }
  return lines.join('\n');
}

async function ensureWorkspaceMemory(target) {
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
  try {
    await fs.mkdir(memoryRoot, { recursive: true });
  } catch (error) {
    output && output.appendLine(`Aegis memory folder is not writable: ${memoryRoot} (${error.message})`);
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
      output && output.appendLine(`Aegis memory file check failed: ${targetPath} (${error.message})`);
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
        output && output.appendLine(`Aegis ${label} check failed: ${filePath} (${error.message})`);
        return false;
      }
    }
    tempPath = path.join(path.dirname(filePath), `.${path.basename(filePath)}.${process.pid}.${Date.now()}.${Math.random().toString(16).slice(2)}.tmp`);
    await fs.writeFile(tempPath, content, 'utf8');
    await fs.rename(tempPath, filePath);
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis ${label} write skipped: ${filePath} (${error.message})`);
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
        output && output.appendLine(`Aegis ${label} check failed: ${filePath} (${error.message})`);
        return false;
      }
    }
    await fs.appendFile(filePath, content, 'utf8');
    return true;
  } catch (error) {
    output && output.appendLine(`Aegis ${label} append skipped: ${filePath} (${error.message})`);
    return false;
  }
}

async function updateWorkspaceMemoryFromSnapshot(target, snapshot) {
  await ensureWorkspaceMemory(target);
  const memoryRoot = path.join(target.workspaceRoot || target.root, '.aegis');
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
  return isIndexableTextFile(relativePath) || isLikelyConfigFile(relativePath) || IMPORTANT_FILE_PATTERNS.some((pattern) => pattern.test(path.basename(relativePath)));
}

function isSymbolCandidate(relativePath, size) {
  if (size > 512000 || isBlockedRelativePath(relativePath)) {
    return false;
  }
  return /\.(js|jsx|ts|tsx|mjs|cjs|py|cs|rs|go|java|cpp|cc|cxx|c|h|hpp)$/i.test(relativePath);
}

function isIndexableTextFile(relativePath) {
  return /\.(js|jsx|ts|tsx|mjs|cjs|py|cs|rs|go|java|cpp|cc|cxx|c|h|hpp|json|jsonc|toml|yaml|yml|md)$/i.test(relativePath);
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
  const basename = path.basename(relativePath).toLowerCase();
  return basename === 'package.json' ||
    basename === 'cmakelists.txt' ||
    basename === 'makefile' ||
    basename === 'cargo.toml' ||
    basename === 'go.mod' ||
    basename === 'pyproject.toml' ||
    basename.endsWith('.csproj') ||
    basename.endsWith('.sln') ||
    basename.startsWith('vite.config') ||
    basename.startsWith('webpack.config') ||
    basename.startsWith('next.config') ||
    basename.startsWith('build.gradle');
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
    { regex: /^\s*using\s+([A-Za-z0-9_.]+)\s*;/gm, kind: 'using' }
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
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  return {
    likelyAffectedFiles: Array.isArray(value.likelyAffectedFiles) ? value.likelyAffectedFiles.map(String).slice(0, 40) : [],
    riskLevel: String(value.riskLevel || value.risk || '').trim(),
    relatedValidation: Array.isArray(value.relatedValidation) ? value.relatedValidation.map(String).slice(0, 10) : [],
    possibleBreakingPoints: Array.isArray(value.possibleBreakingPoints) ? value.possibleBreakingPoints.map(String).slice(0, 12) : [],
    rollbackPlan: String(value.rollbackPlan || '').trim()
  };
}

function normalizeConfidenceScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0.55;
  }
  if (numeric > 1 && numeric <= 100) {
    return Math.max(0, Math.min(1, numeric / 100));
  }
  return Math.max(0, Math.min(1, numeric));
}

function normalizeModelStages(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((stage) => stage && typeof stage === 'object')
    .map((stage, index) => ({
      name: String(stage.name || stage.title || `Stage ${index + 1}`).trim(),
      goal: String(stage.goal || stage.summary || '').trim(),
      files: Array.isArray(stage.files) ? stage.files.map((file) => String(file).replace(/\\/g, '/').replace(/^\/+/, '')).filter(Boolean).slice(0, 30) : [],
      risk: String(stage.risk || '').trim(),
      approvalRequired: stage.approvalRequired !== false
    }));
}

function normalizeProposalStages(proposal, impactAnalysis) {
  const edits = Array.isArray(proposal.fileEdits) ? proposal.fileEdits.map((edit) => edit.path.replace(/\\/g, '/')) : [];
  const knownFiles = new Set(edits);
  const existing = normalizeModelStages(proposal.stages).map((stage) => Object.assign({}, stage, {
    files: stage.files.filter((file) => knownFiles.size ? knownFiles.has(file) : true)
  }));
  const stagedFiles = new Set(existing.flatMap((stage) => stage.files || []));
  const missing = edits.filter((file) => !stagedFiles.has(file));
  let stages = existing.length ? existing : [];
  if (!stages.length && impactAnalysis && Array.isArray(impactAnalysis.stagedPlan)) {
    stages = impactAnalysis.stagedPlan.map((stage) => Object.assign({}, stage, {
      files: (stage.files || []).filter((file) => knownFiles.has(file))
    }));
  }
  if (missing.length) {
    const defaults = buildDefaultStages(missing, impactAnalysis ? impactAnalysis.relatedTests || [] : [], proposal.risk || 'medium');
    for (const fallback of defaults) {
      const fallbackFiles = fallback.files.filter((file) => missing.includes(file));
      if (fallbackFiles.length) {
        stages.push(Object.assign({}, fallback, { files: fallbackFiles }));
      }
    }
  }
  if (!stages.length && edits.length) {
    stages = [{
      name: 'Stage 2: implementation',
      goal: 'Apply the proposed implementation changes.',
      files: edits,
      risk: proposal.risk || 'medium',
      approvalRequired: true
    }];
  }
  return stages.filter((stage) => stage.files && stage.files.length);
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
    .filter((line) => !/(api[_-]?key|secret|token|password|credential|private[_-]?key)/i.test(line))
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
    notes: Array.isArray(lastProposal.notes) ? lastProposal.notes.slice(0, 8) : [],
    impactAnalysis: lastProposal.impactAnalysis || lastImpactAnalysis || null,
    stages: Array.isArray(lastProposal.stages) ? lastProposal.stages : [],
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
  lastProposal = undefined;
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
  const updates = [
    ['ollamaUrl', settings.ollamaUrl],
    ['coreUrl', settings.coreUrl],
    ['chatModel', settings.chatModel],
    ['fallbackModels', typeof settings.fallbackModels === 'string' ? settings.fallbackModels.split(',').map((item) => item.trim()).filter(Boolean) : settings.fallbackModels],
    ['maxContextChars', Number(settings.maxContextChars) || undefined],
    ['autoScanOnOpen', Boolean(settings.autoScanOnOpen)],
    ['validationCommandPreferences', Array.isArray(settings.validationCommandPreferences) ? settings.validationCommandPreferences : String(settings.validationCommandPreferences || '').split(',').map((item) => item.trim()).filter(Boolean)],
    ['safetyMode', settings.safetyMode]
  ];
  for (const [key, value] of updates) {
    if (value !== undefined && value !== '') {
      await config.update(key, value, vscode.ConfigurationTarget.Workspace);
    }
  }
  vscode.window.showInformationMessage('Aegis Local Agent settings saved.');
}

function detectValidationCommands(snapshot) {
  const files = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  const commands = [];
  const packageJsonItems = snapshot.importantContents.filter((item) => path.basename(item.path).toLowerCase() === 'package.json');

  for (const item of packageJsonItems) {
    let pkg;
    try {
      pkg = parseJsonText(item.text);
    } catch (error) {
      continue;
    }
    const scripts = pkg.scripts || {};
    const dir = path.dirname(item.path);
    const cwd = dir === '.' ? snapshot.target.root : path.join(snapshot.target.root, dir);
    const relativeCwd = dir === '.' ? '' : dir;
    const packageManager = pickPackageManagerForPath(snapshot, item.path);
    if (scripts.test) {
      commands.push(makeValidationCommand(packageManager === 'npm' ? 'npm test' : `${packageManager} test`, cwd, relativeCwd));
    }
    if (scripts.lint) {
      commands.push(makeValidationCommand(packageManager === 'npm' ? 'npm run lint' : `${packageManager} lint`, cwd, relativeCwd));
    }
    const typeScriptCheck = scripts.typecheck || scripts['type-check'];
    if (typeScriptCheck) {
      commands.push(makeValidationCommand(packageManager === 'npm' ? `npm run ${scripts.typecheck ? 'typecheck' : 'type-check'}` : `${packageManager} ${scripts.typecheck ? 'typecheck' : 'type-check'}`, cwd, relativeCwd));
    }
    if (scripts.build) {
      commands.push(makeValidationCommand(packageManager === 'npm' ? 'npm run build' : `${packageManager} build`, cwd, relativeCwd));
    }
  }

  if (Array.from(files).some((name) => name.endsWith('.sln') || name.endsWith('.csproj'))) {
    commands.push(makeValidationCommand('dotnet build', snapshot.target.root, ''));
  }
  if (files.has('cargo.toml')) {
    commands.push(makeValidationCommand('cargo check', snapshot.target.root, ''));
  }
  if (files.has('pyproject.toml') || files.has('pytest.ini') || files.has('requirements.txt') || Array.from(files).some((name) => name.startsWith('tests/') && name.endsWith('.py'))) {
    commands.push(makeValidationCommand('python -m pytest', snapshot.target.root, ''));
  }
  if (files.has('go.mod')) {
    commands.push(makeValidationCommand('go test ./...', snapshot.target.root, ''));
  }
  if (files.has('cmakelists.txt') && snapshot.directories.some((dir) => dir.relative.replace(/\\/g, '/').toLowerCase() === 'build')) {
    commands.push(makeValidationCommand('cmake --build build', snapshot.target.root, ''));
  }

  const seen = new Set();
  const preferences = getConfig().validationCommandPreferences;
  return commands.filter((item) => {
    const key = `${item.cwd}|${item.command}`;
    if (seen.has(key) || !isSafeValidationCommand(item.command)) {
      return false;
    }
    if (preferences.length && !preferences.some((pref) => item.command.startsWith(pref) || item.command === pref)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 6);
}

function pickPackageManagerForPath(snapshot, packagePath) {
  const dir = path.dirname(packagePath).replace(/\\/g, '/');
  const prefix = dir === '.' ? '' : `${dir}/`;
  const names = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  if (names.has(`${prefix}pnpm-lock.yaml`)) return 'pnpm';
  if (names.has(`${prefix}yarn.lock`)) return 'yarn';
  if (names.has(`${prefix}package-lock.json`)) return 'npm';
  if (snapshot.packageManagers.includes('pnpm')) return 'pnpm';
  if (snapshot.packageManagers.includes('yarn')) return 'yarn';
  return 'npm';
}

function makeValidationCommand(command, cwd, relativeCwd) {
  return { command, cwd, relativeCwd };
}

function isSafeValidationCommand(command) {
  return /^(npm test|npm run build|npm run lint|npm run typecheck|npm run type-check|pnpm test|pnpm build|pnpm lint|pnpm typecheck|pnpm type-check|yarn test|yarn build|yarn lint|yarn typecheck|yarn type-check|dotnet build|cargo check|go test \.\/\.\.\.|python -m pytest|cmake --build build)$/.test(command);
}

async function runDetectedValidation(target, snapshot) {
  const commands = detectValidationCommands(snapshot || await getProjectSnapshot(target, { fast: true }));
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

  return {
    success: results.every((item) => item.success),
    skipped: false,
    commands: results,
    output: validationResultsToOutput(results)
  };
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
        output: truncateMiddle(outputText || (error ? error.message : 'No output.'), 24000)
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
  if (validation.skipped) {
    return validation.output;
  }
  const failed = validation.commands.find((item) => !item.success);
  if (!failed) {
    return `Validation passed.\n\n${validation.output}`;
  }
  return `Validation failed at \`${failed.command}\`.\n\n${truncateMiddle(failed.output, 12000)}`;
}

function isWorkspaceTarget(value) {
  return Boolean(value && typeof value.root === 'string' && typeof value.label === 'string');
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
  let root = uri.fsPath;
  try {
    const stat = await fs.stat(root);
    if (!stat.isDirectory()) {
      root = path.dirname(root);
    }
  } catch (error) {
    root = path.dirname(root);
  }
  const folder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(root)) || findWorkspaceFolderForPath(root);
  return makeWorkspaceTarget(root, folder);
}

function findWorkspaceFolderForPath(filePath) {
  const folders = vscode.workspace.workspaceFolders || [];
  return folders.find((folder) => isPathInside(folder.uri.fsPath, filePath));
}

function makeWorkspaceTarget(root, workspaceFolder) {
  const resolvedRoot = path.resolve(root);
  const workspaceRoot = workspaceFolder ? path.resolve(workspaceFolder.uri.fsPath) : resolvedRoot;
  const relative = workspaceRoot !== resolvedRoot && isPathInside(workspaceRoot, resolvedRoot)
    ? path.relative(workspaceRoot, resolvedRoot)
    : '';
  return {
    root: resolvedRoot,
    workspaceRoot,
    label: relative || (workspaceFolder ? workspaceFolder.name : path.basename(resolvedRoot)),
    workspaceFolderName: workspaceFolder ? workspaceFolder.name : path.basename(resolvedRoot)
  };
}

function isPathInside(root, candidate) {
  const normalizedRoot = path.resolve(root).toLowerCase();
  const normalizedCandidate = path.resolve(candidate).toLowerCase();
  return normalizedCandidate === normalizedRoot || normalizedCandidate.startsWith(`${normalizedRoot}${path.sep}`);
}

function getConfig() {
  const config = vscode.workspace.getConfiguration('aegisLocalAutopilot');
  return {
    ollamaUrl: config.get('ollamaUrl', 'http://127.0.0.1:11434'),
    coreUrl: config.get('coreUrl', 'http://127.0.0.1:8788'),
    chatModel: config.get('chatModel', 'qwen3-coder:30b'),
    fastModel: config.get('fastModel', 'qwen2.5-coder:7b'),
    fallbackModels: config.get('fallbackModels', ['qwen2.5-coder:7b', 'granite-code:8b']),
    embeddingModel: config.get('embeddingModel', 'mxbai-embed-large:latest'),
    autopilotIntervalMinutes: config.get('autopilotIntervalMinutes', 15),
    autopilotWriteMode: config.get('autopilotWriteMode', 'preview'),
    maxContextFiles: config.get('maxContextFiles', 12),
    maxContextChars: config.get('maxContextChars', MAX_CONTEXT_CHARS),
    autoScanOnOpen: config.get('autoScanOnOpen', true),
    validationCommandPreferences: config.get('validationCommandPreferences', []),
    safetyMode: config.get('safetyMode', 'standard'),
    excludeGlob: config.get('excludeGlob', '{**/node_modules/**,**/.git/**,**/.venv/**,**/x64/**,**/build/**,**/dist/**,**/.tmp/**,**/smoke-artifacts/**,**/stress-artifacts/**}')
  };
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
    maxContextChars: config.maxContextChars,
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
    output && output.appendLine(`Aegis log write failed: ${error.message}`);
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
  const message = error && error.message ? error.message : String(error);
  const diagnosis = diagnoseError(error, context);
  latestErrorInfo = {
    at: new Date().toISOString(),
    message,
    failedCommand: context.failedCommand || lastFailedCommand || '',
    stack: error && error.stack ? sanitizeMemoryText(error.stack) : '',
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
            <label>Fallback Models<input id="settingFallbacks" /></label>
            <label>Max Context Size<input id="settingContext" type="number" /></label>
            <label>Validation Preferences<input id="settingValidation" /></label>
            <label>Safety Mode<select id="settingSafety"><option>standard</option><option>strict</option><option>review-only</option></select></label>
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
          fallbackModels: byId('settingFallbacks').value,
          maxContextChars: byId('settingContext').value,
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
      byId('undoVisibility').textContent = 'Rollback: Aegis backs up approved edits before apply';
      byId('approvalStatus').textContent = proposal.approvalStatus || 'none';
      const files = proposal.files || [];
      byId('proposalFiles').innerHTML = files.length ? files.map((file) => [
        '<label class="fileRow">',
        '<input class="proposalCheck" type="checkbox" value="' + file.index + '" checked />',
        '<span><strong>' + escapeHtml(file.path) + '</strong>' + (isRiskyFile(file.path) ? ' <span class="risk">risky</span>' : '') + '<br/><span class="muted">' + escapeHtml(file.reason || 'Proposed change') + '</span><br/><span class="muted">' + escapeHtml(file.chars || 0) + ' replacement chars</span></span>',
        '</label>'
      ].join('')).join('') : '<div class="muted">No pending file diffs.</div>';
    }

    function isRiskyFile(filePath) {
      return /(^|\\/)(package\\.json|.*\\.csproj|.*\\.sln|vite\\.config\\.|webpack\\.config\\.|next\\.config\\.|tsconfig|pyproject\\.toml|requirements|cmakelists\\.txt)/i.test(filePath || '') || /lock/i.test(filePath || '');
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
      byId('settingFallbacks').value = (config.fallbackModels || []).join(', ');
      byId('settingContext').value = config.maxContextChars || 62000;
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

if (process.env.AEGIS_EXTENSION_DEVTOOLS === '1') {
  exportedApi.__dev = {
    buildProjectSnapshot,
    getProjectSnapshot,
    detectValidationCommands,
    buildDependencyGraph,
    buildSymbolIndex,
    buildImpactAnalysis,
    buildFocusedProjectContext,
    projectSnapshotSummary
  };
}

module.exports = exportedApi;
