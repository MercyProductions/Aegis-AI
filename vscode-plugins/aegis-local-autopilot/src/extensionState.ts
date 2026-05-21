// Runtime state shared by the VS Code sidebar and command handlers.

function createExtensionRuntimeState() {
  let state = emptyRuntimeState();

  function snapshot() {
    return JSON.parse(JSON.stringify(state));
  }

  function update(patch) {
    state = Object.assign({}, state, patch || {}, {
      updatedAt: new Date().toISOString()
    });
    return snapshot();
  }

  function recordOperation(operation) {
    const item = Object.assign({
      at: new Date().toISOString(),
      runtime: 'core',
      operation: 'unknown',
      status: 'info',
      detail: '',
      workflowId: '',
      jobId: '',
      checkpointId: ''
    }, operation || {});
    state.recentOperations = [item].concat(state.recentOperations || []).slice(0, 25);
    state.lastOperation = item;
    if (item.runtime === 'local') {
      state.fallbackMode = true;
      state.fallbackReason = item.detail || state.fallbackReason;
    } else if (item.runtime === 'core' && item.status !== 'failed') {
      state.fallbackMode = false;
      state.fallbackReason = '';
    }
    if (item.workflowId) {
      state.activeWorkflowId = item.workflowId;
    }
    if (item.checkpointId) {
      state.checkpointAvailable = true;
      state.lastCheckpointId = item.checkpointId;
    }
    state.updatedAt = new Date().toISOString();
    return snapshot();
  }

  return {
    snapshot,

    update,

    configure(baseUrl) {
      return update({ coreUrl: baseUrl || state.coreUrl });
    },

    markCoreConnected(detail = '') {
      return update({
        coreConnected: true,
        coreLastSeen: new Date().toISOString(),
        coreStatus: detail || 'Connected',
        lastCoreError: ''
      });
    },

    markCoreDisconnected(error) {
      return update({
        coreConnected: false,
        coreStatus: 'Disconnected',
        lastCoreError: String(error || ''),
        fallbackMode: true,
        fallbackReason: String(error || 'Core unavailable')
      });
    },

    setWebsiteFallback(active, detail = '') {
      return update({
        websiteFallback: Boolean(active),
        fallbackMode: Boolean(active) || state.fallbackMode,
        fallbackReason: detail || state.fallbackReason
      });
    },

    setActiveWorkflow(workflow) {
      const info = normalizeWorkflow(workflow);
      return update({
        activeWorkflowId: info.id,
        activeWorkflowType: info.workflowType,
        activeWorkflowStatus: info.status,
        activeWorkflowProgress: info.progress
      });
    },

    setLatestValidation(validation) {
      return update({
        latestValidation: validation || null,
        latestValidationStatus: validation ? (validation.success || validation.ok ? 'passed' : 'failed') : ''
      });
    },

    setQualityGates(snapshot) {
      const data = snapshot && snapshot.data ? snapshot.data : (snapshot || {});
      const current = data.current_evaluation || data.evaluation || null;
      const scorecard = current && current.scorecard ? current.scorecard : {};
      const gates = current && Array.isArray(current.gates) ? current.gates : [];
      return update({
        qualityGate: current,
        qualityGateStatus: current ? (current.apply_allowed === false ? 'blocked' : 'clear') : '',
        qualityConfidenceScore: typeof scorecard.confidence_score === 'number' ? scorecard.confidence_score : null,
        qualityValidationScore: typeof scorecard.validation_score === 'number' ? scorecard.validation_score : null,
        qualityRiskScore: typeof scorecard.risk_score === 'number' ? scorecard.risk_score : null,
        qualityBlockers: current && Array.isArray(current.blockers) ? current.blockers.slice(0, 8) : [],
        qualityWarnings: current && Array.isArray(current.warnings) ? current.warnings.slice(0, 8) : [],
        qualityGateCount: gates.length,
        qualityUpdatedAt: current ? (current.created_at || new Date().toISOString()) : state.qualityUpdatedAt
      });
    },

    setPendingProposal(proposal) {
      const edits = proposal && Array.isArray(proposal.fileEdits) ? proposal.fileEdits : [];
      return update({
        pendingProposalCount: edits.length,
        pendingProposalSummary: proposal ? proposal.summary || '' : '',
        coreProposalId: proposal ? proposal.coreProposalId || proposal.proposalId || '' : ''
      });
    },

    setCheckpoints(checkpoints) {
      const list = Array.isArray(checkpoints) ? checkpoints : [];
      return update({
        checkpointAvailable: list.length > 0,
        lastCheckpointId: list.length ? list[0].id || list[0].checkpoint_id || '' : state.lastCheckpointId,
        checkpointCount: list.length
      });
    },

    mergeClientSyncDashboard(dashboard) {
      const data = dashboard && dashboard.data ? dashboard.data : (dashboard || {});
      const active = Array.isArray(data.active_workflows) ? data.active_workflows : [];
      const clients = Array.isArray(data.active_clients) ? data.active_clients : [];
      const feed = Array.isArray(data.workspace_activity_feed) ? data.workspace_activity_feed : [];
      const latest = active[0] || {};
      return update({
        activeClients: clients.slice(0, 12),
        syncedWorkflowCount: active.length,
        workspaceActivityFeed: feed.slice(0, 20),
        activeWorkflowId: state.activeWorkflowId || latest.id || '',
        activeWorkflowType: state.activeWorkflowType || latest.workflow_type || '',
        activeWorkflowStatus: state.activeWorkflowStatus || latest.status || ''
      });
    },

    appendWorkflowEvents(events) {
      const normalized = (Array.isArray(events) ? events : []).map((event) => event && event.data ? event.data : event).filter(Boolean);
      state.workflowEvents = normalized.concat(state.workflowEvents || []).slice(0, 50);
      state.updatedAt = new Date().toISOString();
      return snapshot();
    },

    recordOperation
  };
}

function emptyRuntimeState() {
  return {
    coreUrl: '',
    coreConnected: false,
    coreStatus: 'Not checked',
    coreLastSeen: '',
    lastCoreError: '',
    fallbackMode: false,
    fallbackReason: '',
    websiteFallback: false,
    activeWorkflowId: '',
    activeWorkflowType: '',
    activeWorkflowStatus: '',
    activeWorkflowProgress: 0,
    latestValidation: null,
    latestValidationStatus: '',
    qualityGate: null,
    qualityGateStatus: '',
    qualityConfidenceScore: null,
    qualityValidationScore: null,
    qualityRiskScore: null,
    qualityBlockers: [],
    qualityWarnings: [],
    qualityGateCount: 0,
    qualityUpdatedAt: '',
    pendingProposalCount: 0,
    pendingProposalSummary: '',
    coreProposalId: '',
    checkpointAvailable: false,
    checkpointCount: 0,
    lastCheckpointId: '',
    lastOperation: null,
    recentOperations: [],
    activeClients: [],
    syncedWorkflowCount: 0,
    workspaceActivityFeed: [],
    workflowEvents: [],
    updatedAt: new Date().toISOString()
  };
}

function normalizeWorkflow(workflow) {
  const item = workflow && workflow.workflow ? workflow.workflow : (workflow || {});
  return {
    id: item.id || item.workflow_id || '',
    workflowType: item.workflow_type || item.workflowType || '',
    status: item.status || '',
    progress: typeof item.progress === 'number' ? item.progress : 0
  };
}

module.exports = {
  createExtensionRuntimeState,
  emptyRuntimeState,
  normalizeWorkflow
};
