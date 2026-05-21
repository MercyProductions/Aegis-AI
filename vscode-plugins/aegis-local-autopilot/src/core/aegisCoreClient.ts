// Typed-ish Aegis Core /v1 client for the VS Code extension.

const http = require('http');
const https = require('https');
const { serviceUrl } = require('../settings/settings.ts');
const {
  validateCoreEnvelope,
  coreEnvelopeData,
  requireCoreOk
} = require('./coreEnvelope.ts');
const { safeErrorMessage, redactDiagnosticText } = require('../utils/errors.ts');

const DEFAULT_CLIENT_ID = 'aegis-vscode';
const DEFAULT_CLIENT_TYPE = 'vscode-extension';
const DEFAULT_CLIENT_NAME = 'Aegis Local Agent for VS Code';

function createAegisCoreClient(options = {}) {
  const baseUrl = String(options.baseUrl || 'http://127.0.0.1:8788').replace(/\/+$/, '');
  const clientId = options.clientId || DEFAULT_CLIENT_ID;
  const clientType = options.clientType || DEFAULT_CLIENT_TYPE;
  const name = options.name || DEFAULT_CLIENT_NAME;
  const version = options.version || 'unknown';
  const output = options.output;
  const timeoutMs = Number(options.timeoutMs) || 120000;
  const userAgent = `Aegis-Local-Agent-VSCode/${version}`;
  const localAuthToken = String(options.localAuthToken || process.env.AEGIS_CORE_LOCAL_TOKEN || process.env.AEGIS_LOCAL_AUTH_TOKEN || '').trim();

  const log = (message) => {
    if (output && typeof output.appendLine === 'function') {
      output.appendLine(message);
    }
  };

  const urlFor = (pathname, workspace, query = {}) => {
    const url = serviceUrl(baseUrl, pathname);
    if (workspace) {
      url.searchParams.set('workspace', workspacePath(workspace));
    }
    for (const [key, value] of Object.entries(query || {})) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
    return url;
  };

  const getEnvelope = async (pathname, workspace, expectedKind, requestTimeoutMs = timeoutMs, query = {}) => {
    const envelope = await requestJson(urlFor(pathname, workspace, query), undefined, requestTimeoutMs, userAgent, localAuthToken);
    return validateCoreEnvelope(envelope, expectedKind, { redactDiagnosticText });
  };

  const postEnvelope = async (pathname, body, expectedKind, requestTimeoutMs = timeoutMs) => {
    const envelope = await requestJson(urlFor(pathname), body, requestTimeoutMs, userAgent, localAuthToken);
    return validateCoreEnvelope(envelope, expectedKind, { redactDiagnosticText });
  };

  return {
    baseUrl,
    clientId,
    clientType,
    name,
    version,

    requestJson: (pathname, body, requestTimeoutMs) =>
      requestJson(urlFor(pathname), body, requestTimeoutMs || timeoutMs, userAgent, localAuthToken),

    getEnvelope,
    postEnvelope,

    async health(workspace) {
      return getEnvelope('/v1/health', workspace, 'health');
    },

    releaseManifest(workspace) {
      return getEnvelope('/v1/release/manifest', workspace, 'release.manifest');
    },

    securityStatus(workspace) {
      return getEnvelope('/v1/security/status', workspace, 'security.status');
    },

    checkCompatibility(workspace, options = {}) {
      return postEnvelope('/v1/release/compatibility', {
        workspace: workspacePath(workspace),
        client_type: options.clientType || clientType,
        client_version: options.clientVersion || version,
        schema_version: options.schemaVersion || '2026.05.12',
        capabilities: options.capabilities || defaultCapabilities()
      }, 'release.compatibility');
    },

    async models(workspace) {
      try {
        const envelope = await getEnvelope('/v1/models/registry', workspace, 'model.registry');
        const data = coreEnvelopeData(envelope);
        const models = Array.isArray(data.models)
          ? data.models
              .filter((model) => model && model.provider_id === 'ollama')
              .map((model) => ({
                name: model.model_id || model.display_name || '',
                model: model.model_id || model.display_name || '',
                displayName: model.display_name || model.model_id || '',
                source: 'aegis-core-registry',
                providerId: model.provider_id || 'ollama',
                availabilityStatus: model.availability_status || 'unknown',
                contextWindow: model.context_window || null,
                capabilities: Array.isArray(model.capabilities) ? model.capabilities : []
              }))
              .filter((model) => model.name)
          : [];
        const selected = data.selected_model && typeof data.selected_model === 'object' ? data.selected_model : {};
        const ollamaStatus = Array.isArray(data.provider_status)
          ? data.provider_status.find((provider) => provider && provider.provider_id === 'ollama')
          : null;
        return {
          envelope,
          registry: data,
          models,
          reachable: Boolean(ollamaStatus ? ollamaStatus.provider_reachable : models.length),
          selectedModel: selected.model_id || selected.display_name || '',
          missingModels: [],
          error: '',
          routeProfile: data.active_profile || '',
          providerStatus: Array.isArray(data.provider_status) ? data.provider_status : [],
          routingProfiles: Array.isArray(data.routing_profiles) ? data.routing_profiles : []
        };
      } catch (registryError) {
        log(`Aegis Core model registry unavailable; trying legacy model inventory: ${safeErrorMessage(registryError)}`);
        const envelope = await getEnvelope('/v1/models', workspace, 'models');
        const data = coreEnvelopeData(envelope);
        return {
          envelope,
          models: Array.isArray(data.installed_models)
            ? data.installed_models.map((model) => ({ name: model, model, source: 'aegis-core' }))
            : [],
          reachable: Boolean(data.reachable),
          selectedModel: data.selected_model || '',
          missingModels: Array.isArray(data.missing_models) ? data.missing_models : [],
          error: data.error || ''
        };
      }
    },

    modelRegistry(workspace) {
      return getEnvelope('/v1/models/registry', workspace, 'model.registry');
    },

    routingProfiles() {
      return getEnvelope('/v1/models/routing-profiles', undefined, 'model.routing_profiles');
    },

    routeModel(workspace, options = {}) {
      return postEnvelope('/v1/models/route', {
        workspace: workspacePath(workspace),
        task_type: options.taskType || 'chat',
        workflow_type: options.workflowType || null,
        difficulty: options.difficulty || null,
        route_profile: options.routeProfile || null,
        required_capabilities: options.requiredCapabilities || [],
        privacy_sensitive: Boolean(options.privacySensitive),
        provider_id: options.providerId || null,
        model: options.model || null,
        allow_cloud: Boolean(options.allowCloud),
        cloud_approved: Boolean(options.cloudApproved),
        context_files: options.contextFiles || [],
        local_failure_reason: options.localFailureReason || null
      }, 'model.route');
    },

    settings(workspace) {
      return getEnvelope('/v1/settings', workspace, 'settings');
    },

    memory(workspace) {
      return getEnvelope('/v1/memory', workspace, 'memory.summary');
    },

    diagnostics(workspace) {
      return getEnvelope('/v1/diagnostics', workspace, 'diagnostics.summary');
    },

    validationSummary(workspace) {
      return postEnvelope('/v1/validation', { workspace: workspacePath(workspace), run: false }, 'validation');
    },

    workspaceScan(workspace) {
      return postEnvelope('/v1/workspaces/scan', { workspace: workspacePath(workspace) }, 'workspace.scan', 180000);
    },

    workspaceIntelligence(workspace, options = {}) {
      return postEnvelope('/v1/workspaces/intelligence', {
        workspace: workspacePath(workspace),
        persist: options.persist !== false,
        refresh: Boolean(options.refresh)
      }, 'workspace.intelligence', 240000);
    },

    roadmap(workspace) {
      return postEnvelope('/v1/workspaces/roadmap', { workspace: workspacePath(workspace) }, 'workspace.roadmap', 180000);
    },

    async registerClient(workspace, options = {}) {
      const body = {
        workspace: workspacePath(workspace),
        client_id: options.clientId || clientId,
        client_type: options.clientType || clientType,
        name: options.name || name,
        version: options.version || version,
        capabilities: options.capabilities || defaultCapabilities(),
        active_workflow_id: options.activeWorkflowId || null,
        status: options.status || 'active',
        metadata: options.metadata || {}
      };
      try {
        const envelope = await postEnvelope('/v1/clients/sync', body, 'client.sync');
        return { envelope, data: coreEnvelopeData(envelope), mode: 'sync' };
      } catch (syncError) {
        log(`Aegis Core client sync unavailable; trying registration fallback: ${safeErrorMessage(syncError)}`);
        const fallback = await postEnvelope('/v1/clients/register', body, 'client.registered');
        return { envelope: fallback, data: coreEnvelopeData(fallback), mode: 'register', syncError: safeErrorMessage(syncError) };
      }
    },

    clientSyncDashboard(workspace, options = {}) {
      return getEnvelope('/v1/client-sync', workspace, 'client.sync.dashboard', timeoutMs, { limit: options.limit || 50 });
    },

    createWorkflow(workspace, workflowType, objective, options = {}) {
      return postEnvelope('/v1/workflows', {
        workspace: workspacePath(workspace),
        workflow_type: workflowType,
        objective: objective || '',
        source_client: options.sourceClient || clientType,
        context_files: options.contextFiles || [],
        metadata: options.metadata || {}
      }, 'workflow.created', 180000);
    },

    listWorkflows(workspace, options = {}) {
      return getEnvelope('/v1/workflows', workspace, 'workflows.list', timeoutMs, {
        include_completed: options.includeCompleted === false ? 'false' : 'true',
        limit: options.limit || 50
      });
    },

    workflowDashboard(workspace, workflowId) {
      return getEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}`, workspace, 'workflow.dashboard');
    },

    workflowStats(workspace) {
      return getEnvelope('/v1/workflows/stats', workspace, 'workflow.statistics');
    },

    agentRuntime() {
      return getEnvelope('/v1/workflows/agent-runtime', undefined, 'agent.runtime');
    },

    stepWorkflow(workspace, workflowId, options = {}) {
      return postEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/step`, {
        workspace: workspacePath(workspace),
        action: options.action || 'record_log',
        task_id: options.taskId || null,
        approval: Boolean(options.approval),
        summary: options.summary || '',
        payload: options.payload || {}
      }, 'workflow.step', 180000);
    },

    pauseWorkflow(workspace, workflowId, summary = '') {
      return postEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/pause`, {
        workspace: workspacePath(workspace),
        summary
      }, 'workflow.step');
    },

    resumeWorkflow(workspace, workflowId, summary = '') {
      return postEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/resume`, {
        workspace: workspacePath(workspace),
        summary
      }, 'workflow.step');
    },

    cancelWorkflow(workspace, workflowId, summary = '') {
      return postEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/cancel`, {
        workspace: workspacePath(workspace),
        summary
      }, 'workflow.step');
    },

    retryWorkflow(workspace, workflowId, taskId, summary = '') {
      return postEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/retry`, {
        workspace: workspacePath(workspace),
        task_id: taskId,
        summary
      }, 'workflow.step');
    },

    workflowEvents(workspace, options = {}) {
      const path = options.workflowId
        ? `/v1/workflows/${encodeURIComponent(options.workflowId)}/events`
        : '/v1/workflows/events';
      return requestSse(urlFor(path, workspace, {
        since: options.since || 0,
        limit: options.limit || 100,
        follow: options.follow ? 'true' : 'false',
        max_seconds: options.maxSeconds || 30
      }), {
        timeoutMs: options.timeoutMs || ((Number(options.maxSeconds) || 30) + 10) * 1000,
        userAgent,
        localAuthToken,
        onEvent: options.onEvent
      });
    },

    proposeChanges(workspace, changes, options = {}) {
      return postEnvelope('/v1/changes/propose', {
        workspace: workspacePath(workspace),
        changes: normalizeCoreChanges(changes),
        summary: options.summary || '',
        source_task_id: options.sourceTaskId || null,
        source_client: options.sourceClient || clientType,
        risk: options.risk || 'unknown',
        repair_attempt: options.repairAttempt || null
      }, 'changes.proposal', 180000);
    },

    applyChanges(workspace, options = {}) {
      return postEnvelope('/v1/changes/apply', {
        workspace: workspacePath(workspace),
        proposal_id: options.proposalId || null,
        changes: normalizeCoreChanges(options.changes || []),
        change_ids: options.changeIds || [],
        paths: options.paths || [],
        apply_all: options.applyAll !== false,
        dry_run: Boolean(options.dryRun),
        summary: options.summary || '',
        task_id: options.taskId || null,
        source_client: options.sourceClient || clientType,
        repair_attempt: options.repairAttempt || null,
        approval: Boolean(options.approval),
        validation_required: Boolean(options.validationRequired),
        quality_gate_required: options.qualityGateRequired !== false,
        max_files_changed: options.maxFilesChanged || null,
        allow_quality_override: Boolean(options.allowQualityOverride)
      }, 'changes.apply', 240000);
    },

    createCheckpoint(workspace, options = {}) {
      return postEnvelope('/v1/checkpoints/create', {
        workspace: workspacePath(workspace),
        changes: normalizeCoreChanges(options.changes || []),
        paths: options.paths || [],
        summary: options.summary || '',
        source_task_id: options.sourceTaskId || null,
        source_client: options.sourceClient || clientType
      }, 'checkpoints.create', 180000);
    },

    listCheckpoints(workspace, options = {}) {
      return getEnvelope('/v1/checkpoints', workspace, 'checkpoints.list', timeoutMs, { limit: options.limit || 50 });
    },

    restoreCheckpoint(workspace, checkpointId, options = {}) {
      return postEnvelope('/v1/checkpoints/restore', {
        workspace: workspacePath(workspace),
        checkpoint_id: checkpointId,
        dry_run: Boolean(options.dryRun),
        source_client: options.sourceClient || clientType,
        task_id: options.taskId || null
      }, 'checkpoints.restore', 240000);
    },

    runValidation(workspace, options = {}) {
      return postEnvelope('/v1/validation/run', {
        workspace: workspacePath(workspace),
        command: options.command || null,
        timeout_seconds: options.timeoutSeconds || 300,
        dry_run: Boolean(options.dryRun),
        source_client: options.sourceClient || clientType,
        task_id: options.taskId || null,
        repair_attempt: options.repairAttempt || null
      }, 'validation.run', (options.timeoutSeconds ? (options.timeoutSeconds + 30) * 1000 : 360000));
    },

    qualityGates(workspace, options = {}) {
      return getEnvelope('/v1/quality-gates', workspace, 'quality.gates', timeoutMs, {
        limit: options.limit || 50
      });
    },

    evaluateQualityGates(workspace, options = {}) {
      return postEnvelope('/v1/quality-gates/evaluate', {
        workspace: workspacePath(workspace),
        workflow_id: options.workflowId || null,
        proposal_id: options.proposalId || null,
        changes: normalizeCoreChanges(options.changes || []),
        validation_id: options.validationId || null,
        validation: options.validation || null,
        checkpoint_id: options.checkpointId || null,
        approval: Boolean(options.approval),
        dry_run: options.dryRun !== false,
        persist: options.persist !== false,
        max_files_changed: options.maxFilesChanged || null,
        validation_required: Boolean(options.validationRequired),
        source_client: options.sourceClient || clientType,
        metadata: options.metadata || {}
      }, 'quality.gates.evaluate', 180000);
    },

    workflowQuality(workspace, workflowId) {
      return getEnvelope(`/v1/workflows/${encodeURIComponent(workflowId)}/quality`, workspace, 'workflow.quality');
    },

    qualityBenchmarks(workspace, options = {}) {
      return getEnvelope('/v1/benchmarks', workspace, 'quality.benchmarks', timeoutMs, {
        limit: options.limit || 50
      });
    },

    runQualityBenchmark(workspace, options = {}) {
      return postEnvelope('/v1/benchmarks/run', {
        workspace: workspacePath(workspace),
        suite_ids: options.suiteIds || (options.suiteId ? [options.suiteId] : ['validation_success']),
        workflow_id: options.workflowId || null,
        metadata: options.metadata || {}
      }, 'quality.benchmark.run', 180000);
    },

    autopilotModes() {
      return getEnvelope('/v1/autopilot/modes', undefined, 'autopilot.modes');
    },

    startAutopilot(workspace, options = {}) {
      return postEnvelope('/v1/autopilot/start', {
        workspace: workspacePath(workspace),
        objective: options.objective || options.goal || '',
        mode: options.mode || 'semi_autonomous',
        workflow_type: options.workflowType || 'generate_feature',
        roadmap: options.roadmap || [],
        target_files: options.targetFiles || [],
        constraints: options.constraints || [],
        validation_commands: options.validationCommands || [],
        execution_plan: options.executionPlan || {},
        specialization: options.specialization || options.autopilotSpecialization || null,
        client_id: options.clientId || clientId,
        approval: Boolean(options.approval),
        metadata: options.metadata || {}
      }, 'autopilot.run', 240000);
    },

    listAutopilotRuns(workspace, options = {}) {
      return getEnvelope('/v1/autopilot/runs', workspace, 'autopilot.runs', timeoutMs, {
        status: options.status || null,
        mode: options.mode || null,
        workflow_type: options.workflowType || null,
        limit: options.limit || 50
      });
    },

    autopilotRun(workspace, autopilotId) {
      return getEnvelope(`/v1/autopilot/runs/${encodeURIComponent(autopilotId)}`, workspace, 'autopilot.dashboard');
    },

    autopilotAction(workspace, autopilotId, options = {}) {
      return postEnvelope(`/v1/autopilot/runs/${encodeURIComponent(autopilotId)}/action`, {
        workspace: workspacePath(workspace),
        action: options.action || 'advance',
        approval: Boolean(options.approval),
        summary: options.summary || '',
        payload: options.payload || {},
        client_id: options.clientId || clientId
      }, 'autopilot.action', 240000);
    },

    autopilotReplay(workspace, autopilotId) {
      return getEnvelope(`/v1/autopilot/runs/${encodeURIComponent(autopilotId)}/replay`, workspace, 'autopilot.replay');
    },

    autopilotSupervision(workspace, options = {}) {
      return getEnvelope('/v1/autopilot/supervision', workspace, 'autopilot.supervision', timeoutMs, {
        autopilot_id: options.autopilotId || null
      });
    },

    autopilotObservability(workspace) {
      return getEnvelope('/v1/autopilot/observability', workspace, 'autopilot.observability');
    },

    autopilotMemory(workspace) {
      return getEnvelope('/v1/autopilot/memory', workspace, 'autopilot.memory');
    },

    autopilotClientHooks() {
      return getEnvelope('/v1/autopilot/client-hooks', undefined, 'autopilot.client_hooks');
    },

    getJob(workspace, jobId) {
      return getEnvelope(`/v1/jobs/${encodeURIComponent(jobId)}`, workspace, 'core.job');
    },

    projectActivity(workspace, projectId, options = {}) {
      return getEnvelope(`/v1/projects/${encodeURIComponent(projectId)}/activity`, workspace, 'project.activity', timeoutMs, {
        limit: options.limit || 50
      });
    },

    requireOk(envelope, action) {
      return requireCoreOk(envelope, action, { redactDiagnosticText });
    }
  };
}

function defaultCapabilities() {
  return [
    'core-contracts',
    'workflow_runtime',
    'editing_runtime',
    'event_streaming',
    'client_sync',
    'core-models',
    'core-model-registry',
    'core-model-routing',
    'core-workspace-scan',
    'core-roadmap',
    'core-memory',
    'core-diagnostics',
    'core-validation',
    'core-quality-gates',
    'core-evaluation-reports',
    'core-autopilot-runtime',
    'autopilot-specializations',
    'autopilot-supervision',
    'autopilot-approval-hooks',
    'autopilot-replay',
    'release-compatibility',
    'release-manifest',
    'core-security-status',
    'core-apply',
    'core-checkpoints',
    'diff-preview',
    'safe-apply',
    'local-fallbacks'
  ];
}

function normalizeCoreChanges(changes) {
  return (Array.isArray(changes) ? changes : []).map((change, index) => ({
    id: change.id || `change-${index + 1}`,
    action: normalizeAction(change.action),
    path: String(change.path || ''),
    content: change.content === undefined ? null : change.content,
    summary: change.summary || change.reason || '',
    selected: Boolean(change.selected)
  }));
}

function normalizeAction(action) {
  const value = String(action || '').toLowerCase();
  if (value === 'create' || value === 'update' || value === 'append' || value === 'delete') {
    return value;
  }
  return 'update';
}

function workspacePath(value) {
  if (!value) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  return value.root || value.workspaceRoot || value.workspace || '';
}

function requestJson(url, body, timeoutMs, userAgent, localAuthToken = '') {
  return new Promise((resolve, reject) => {
    const isHttps = url.protocol === 'https:';
    const data = body ? Buffer.from(JSON.stringify(body), 'utf8') : undefined;
    const headers = body
      ? {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'Content-Length': data.length,
          'User-Agent': userAgent
        }
      : {
          Accept: 'application/json',
          'User-Agent': userAgent
        };
    if (localAuthToken) {
      headers.Authorization = `Bearer ${localAuthToken}`;
      headers['X-Aegis-Local-Token'] = localAuthToken;
    }
    const req = (isHttps ? https : http).request({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port,
      path: `${url.pathname}${url.search}`,
      method: body ? 'POST' : 'GET',
      headers
    }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error(formatHttpError(response.statusCode, text)));
          return;
        }
        try {
          resolve(text.trim() ? JSON.parse(text) : {});
        } catch (error) {
          reject(new Error(`Invalid JSON from ${formatRequestTarget(url)}: ${error.message}`));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs || 120000, () => req.destroy(new Error(`Timed out calling ${formatRequestTarget(url)}`)));
    if (data) {
      req.write(data);
    }
    req.end();
  });
}

function requestSse(url, options = {}) {
  return new Promise((resolve, reject) => {
    const isHttps = url.protocol === 'https:';
    const events = [];
    let buffer = '';
    const headers = {
      Accept: 'text/event-stream',
      'User-Agent': options.userAgent || 'Aegis-Local-Agent-VSCode'
    };
    if (options.localAuthToken) {
      headers.Authorization = `Bearer ${options.localAuthToken}`;
      headers['X-Aegis-Local-Token'] = options.localAuthToken;
    }
    const req = (isHttps ? https : http).request({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port,
      path: `${url.pathname}${url.search}`,
      method: 'GET',
      headers
    }, (response) => {
      if (response.statusCode < 200 || response.statusCode >= 300) {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => reject(new Error(formatHttpError(response.statusCode, Buffer.concat(chunks).toString('utf8')))));
        return;
      }
      response.setEncoding('utf8');
      response.on('data', (chunk) => {
        buffer += chunk;
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() || '';
        for (const part of parts) {
          const event = parseSseEvent(part);
          if (event) {
            events.push(event);
            if (typeof options.onEvent === 'function') {
              options.onEvent(event);
            }
          }
        }
      });
      response.on('end', () => {
        const event = parseSseEvent(buffer);
        if (event) {
          events.push(event);
          if (typeof options.onEvent === 'function') {
            options.onEvent(event);
          }
        }
        resolve(events);
      });
    });
    req.on('error', reject);
    req.setTimeout(options.timeoutMs || 45000, () => req.destroy(new Error(`Timed out calling ${formatRequestTarget(url)}`)));
    req.end();
  });
}

function parseSseEvent(chunk) {
  const lines = String(chunk || '').split(/\r?\n/);
  let event = 'message';
  const data = [];
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim() || event;
    } else if (line.startsWith('data:')) {
      data.push(line.slice('data:'.length).trimStart());
    }
  }
  if (!data.length) {
    return null;
  }
  const raw = data.join('\n');
  let parsed = raw;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    parsed = raw;
  }
  return { event, data: parsed };
}

function formatRequestTarget(url) {
  const pathname = url && url.pathname ? url.pathname : '/';
  const origin = url && url.origin && url.origin !== 'null'
    ? url.origin
    : `${url.protocol || 'http:'}//${url.host || 'unknown-host'}`;
  return `${origin}${pathname}`;
}

function formatHttpError(statusCode, responseText) {
  const text = String(responseText || '').trim();
  if (!text) {
    return `HTTP ${statusCode}`;
  }
  try {
    const parsed = JSON.parse(text);
    const detail = parsed.detail || parsed.error || parsed.message;
    if (typeof detail === 'string' && detail.trim()) {
      return `HTTP ${statusCode}: ${redactDiagnosticText(detail)}`;
    }
  } catch (error) {
    // Plain text server errors are fine; keep the bounded redacted form.
  }
  return `HTTP ${statusCode}: ${redactDiagnosticText(text, 700)}`;
}

module.exports = {
  createAegisCoreClient,
  defaultCapabilities,
  normalizeCoreChanges,
  workspacePath,
  requestJson,
  requestSse
};
