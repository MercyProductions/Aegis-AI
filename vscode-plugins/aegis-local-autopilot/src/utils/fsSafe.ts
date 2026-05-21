// File system safety utility functions for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const fs = require('fs/promises');
const { isPathInside } = require('./pathSafe.ts');
const { truncateMiddle } = require('./errors.ts');

/**
 * Safely reads a file inside a workspace root. Returns empty string if the
 * file does not exist, is too large, or is outside the root.
 * @param {string} root
 * @param {string} rel - Relative path from root.
 * @returns {Promise<string>}
 */
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

/**
 * Resolves a relative path inside a root, returning undefined if the result
 * would escape the root.
 * @param {string} root
 * @param {string} relativePath
 * @returns {string|undefined}
 */
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

/**
 * Strips a UTF-8 BOM from the start of a string.
 * @param {string} text
 * @returns {string}
 */
function stripUtf8Bom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * Parses JSON text after stripping a possible UTF-8 BOM.
 * @param {string} text
 * @returns {*}
 */
function parseJsonText(text) {
  return JSON.parse(stripUtf8Bom(String(text || '')));
}

/**
 * Formats a file's content as a labeled code block for model context.
 * @param {string} rel - Label (typically the relative path).
 * @param {string} text - File content.
 * @returns {string}
 */
function formatFileChunk(rel, text) {
  return `# File: ${rel}\n\`\`\`\n${truncateMiddle(text, 16000)}\n\`\`\``;
}

module.exports = {
  readWorkspaceFile,
  resolveInside,
  stripUtf8Bom,
  parseJsonText,
  formatFileChunk
};
