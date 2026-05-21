// Path safety utility functions for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');

/**
 * Blocked directory segment names. Files under these directories are never
 * scanned, proposed, or applied by the extension.
 */
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

/**
 * Filename patterns that indicate sensitive/secret files which must never
 * be proposed for edits.
 */
const SECRET_FILE_PATTERNS = [
  /^\.env(?:\.|$)/i,
  /^id_(?:rsa|dsa|ecdsa|ed25519)$/i,
  /(?:^|[._\-\s])(?:secret(?:s)?|credential(?:s)?|password|passwd|token(?:s)?|private(?:[._\-\s]?key)?|api[_-]?key|auth)(?:[._\-\s]|$)/i,
  /\.(?:key|pem|pfx|p12|keystore|crt|cer)$/i
];

/**
 * Lockfile basename patterns. Edits to lockfiles require explicit model
 * reasoning or they are blocked.
 */
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

/**
 * Checks whether a candidate path is inside a given root directory.
 * @param {string} root
 * @param {string} candidate
 * @returns {boolean}
 */
function isPathInside(root, candidate) {
  const normalizedRoot = path.resolve(root).toLowerCase();
  const normalizedCandidate = path.resolve(candidate).toLowerCase();
  return normalizedCandidate === normalizedRoot || normalizedCandidate.startsWith(normalizedRoot + path.sep);
}

/**
 * Returns true if the relative path touches a blocked segment or a
 * secret file pattern.
 * @param {string} relativePath
 * @returns {boolean}
 */
function isBlockedRelativePath(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').replace(/^\/+/, '');
  const segments = normalized.split('/').filter(Boolean);
  if (!segments.length) {
    return true;
  }
  for (const segment of segments) {
    if (segment === '.' || segment === '..') {
      return true;
    }
    if (BLOCKED_PATH_SEGMENTS.has(segment.toLowerCase())) {
      return true;
    }
  }
  const basename = segments[segments.length - 1] || '';
  return SECRET_FILE_PATTERNS.some((pattern) => pattern.test(basename));
}

/**
 * Normalizes line endings to Unix-style LF.
 * @param {string} text
 * @returns {string}
 */
function normalizeLineEndings(text) {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

/**
 * Creates an ISO timestamp suitable for use in file/directory names.
 * @returns {string}
 */
function timestampForPath() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

module.exports = {
  BLOCKED_PATH_SEGMENTS,
  SECRET_FILE_PATTERNS,
  LOCKFILE_PATTERNS,
  isPathInside,
  isBlockedRelativePath,
  normalizeLineEndings,
  timestampForPath
};
