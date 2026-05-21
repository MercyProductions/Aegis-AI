// Agent state management logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const { sanitizeMemoryText } = require('../utils/errors.ts');

/**
 * Creates a fresh agent state object.
 */
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

/**
 * Creates a fresh health check state object.
 */
function makeEmptyHealthCheckState() {
  return {
    overall: 'unknown',
    checkedAt: '',
    elapsedMs: 0,
    checks: []
  };
}

/**
 * Creates a fresh model diagnostics state object.
 */
function makeEmptyModelDiagnosticsState() {
  return {
    checkedAt: '',
    installedModels: [],
    primary: undefined,
    fallbacks: [],
    contextWarning: ''
  };
}

/**
 * Creates a fresh error info object.
 */
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

/**
 * Helper to update progress items within an agent state.
 * @param {object} state - The current agent state.
 * @param {string} label - Short progress label.
 * @param {string} [detail=''] - Detailed progress message.
 * @returns {object} - The new progressItems array.
 */
function buildProgressUpdate(state, label, detail = '') {
  const item = {
    at: new Date().toLocaleTimeString(),
    label: sanitizeMemoryText(String(label || 'Working')),
    detail: sanitizeMemoryText(String(detail || ''))
  };
  return [item, ...(state.progressItems || [])].slice(0, 8);
}

/**
 * Helper to update context files within an agent state.
 * @param {string[]} files - List of file paths.
 * @param {string} reason - Reason why these files are in context.
 * @returns {object[]} - The new contextFiles array.
 */
function buildContextFilesUpdate(files, reason) {
  return (files || []).slice(0, 18).map((file) => ({
    path: file,
    reason: sanitizeMemoryText(reason || 'Relevant to the current request.')
  }));
}

module.exports = {
  makeEmptyAgentState,
  makeEmptyHealthCheckState,
  makeEmptyModelDiagnosticsState,
  makeEmptyErrorInfo,
  buildProgressUpdate,
  buildContextFilesUpdate
};
