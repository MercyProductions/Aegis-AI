// Proposal safety and validation logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const { isBlockedRelativePath, LOCKFILE_PATTERNS } = require('../utils/pathSafe.ts');
const { resolveInside, parseJsonText } = require('../utils/fsSafe.ts');
const { sanitizeMemoryText, redactDiagnosticText } = require('../utils/errors.ts');

/**
 * Validates a single file edit proposal against safety rules.
 * @param {object} proposal - The full proposal object.
 * @param {object} edit - The specific file edit to validate.
 * @param {object} [config] - Extension configuration (for safetyMode).
 * @returns {object} - { ok: boolean, edit: object, target?: string, relative?: string, reason?: string }
 */
function validateProposalEdit(proposal, edit, config = {}) {
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
  if (config.safetyMode === 'strict') {
    const lowerPath = normalizedPath.toLowerCase();
    if (/\.(min\.js|min\.css|bundle\.js|\.map)$/i.test(basename) || /chunk[\w.-]*\.js$/i.test(basename)) {
      return { ok: false, edit, reason: 'Strict safety: minified bundles, chunk builds, and source maps are blocked from automatic edits.' };
    }
    if (lowerPath.includes('/.github/workflows/')) {
      return { ok: false, edit, reason: 'Strict safety: GitHub workflow files are blocked from automatic edits.' };
    }
  }
  return { ok: true, edit: Object.assign({}, edit, { path: normalizedPath }), target, relative: normalizedPath };
}

/**
 * Formats a summary of blocked edits for display in the UI.
 * @param {Array} blocked - List of blocked edit result objects.
 * @returns {string}
 */
function formatBlockedProposalEditSummary(blocked) {
  const items = Array.isArray(blocked) ? blocked.filter(Boolean) : [];
  if (!items.length) {
    return 'unknown edit blocked by safety rules';
  }
  const first = items[0];
  const rawPath = first.edit && typeof first.edit.path === 'string' ? first.edit.path : '<missing path>';
  const slashPath = rawPath.replace(/\\/g, '/');
  const absoluteLike = slashPath.startsWith('/') || /^[A-Za-z]:\//.test(slashPath);
  const normalizedPath = absoluteLike
    ? (slashPath.split('/').filter(Boolean).pop() || '<absolute path>')
    : (slashPath.replace(/^\/+/, '') || '<missing path>');
  const reason = typeof first.reason === 'string' && first.reason.trim()
    ? first.reason.trim().replace(/[.\s]+$/, '')
    : 'Blocked by safety rules';
  const remainder = items.length > 1 ? `; plus ${items.length - 1} more` : '';
  return `${normalizedPath}: ${reason}${remainder}`;
}

/**
 * Ensures confidence scores are normalized between 0.0 and 1.0.
 * @param {number|string} value
 * @returns {number}
 */
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

/**
 * Prepares a proposal for local storage by redacting secrets and stripping
 * large content fields.
 * @param {object} proposal
 * @returns {object}
 */
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

/**
 * Validates that a backup ID is safe to use in file paths.
 * @param {string} value
 * @returns {boolean}
 */
function isSafeBackupId(value) {
  return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(value);
}

module.exports = {
  validateProposalEdit,
  formatBlockedProposalEditSummary,
  normalizeConfidenceScore,
  sanitizeProposalForStorage,
  isSafeBackupId
};
