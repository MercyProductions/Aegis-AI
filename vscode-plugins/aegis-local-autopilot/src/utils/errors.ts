// Error-related utility functions for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

/**
 * Wraps an unknown error into a safe, redacted string for diagnostics.
 * @param {Error|string} error
 * @param {number} [maxChars=700]
 * @returns {string}
 */
function safeErrorMessage(error, maxChars = 700) {
  const raw = error && error.message ? error.message : String(error || '');
  return redactDiagnosticText(raw || 'Unknown error.', maxChars) || 'Error detail was redacted.';
}

/**
 * Strips secrets and sensitive tokens from diagnostic text before it is
 * shown in the UI, logged, or persisted.
 * @param {string} text
 * @param {number} [maxChars=700]
 * @returns {string}
 */
function redactDiagnosticText(text, maxChars = 700) {
  let cleaned = String(text || '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) {
    return '';
  }

  cleaned = cleaned
    .replace(/\b(https?:\/\/)[^/\s:@]+:[^@\s/]+@/gi, '$1[redacted]@')
    .replace(/([?&](?:x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|key|token|client[_-]?secret|secret|password|passwd|credential|authorization|private[_-]?key)=)[^&#\s]+/gi, '$1[redacted]')
    .replace(/(['"](?:x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|token|client[_-]?secret|secret|password|passwd|credential|authorization|private[_-]?key)['"]\s*:\s*['"])[^'"]+/gi, '$1[redacted]')
    .replace(/\b(Authorization\s*[:=]\s*)(?:Bearer|Basic|Digest)?\s*[A-Za-z0-9._~+/\-=]+/gi, '$1[redacted]')
    .replace(/\b(Bearer\s+)[A-Za-z0-9._~+/\-=]+/gi, '$1[redacted]')
    .replace(/\b((?:x-api-key|[A-Z0-9_-]*api[_-]?key|[A-Z0-9_-]*api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|[A-Z0-9_-]*token|client[_-]?secret|[A-Z0-9_-]*secret|password|passwd|credential|authorization|private[_-]?key)\s*[:=]\s*)[^\s&]+/gi, '$1[redacted]');

  if (maxChars > 0 && cleaned.length > maxChars) {
    return `${cleaned.slice(0, Math.max(0, maxChars - 3))}...`;
  }
  return cleaned;
}

/**
 * Removes lines containing sensitive keywords before persisting text
 * to .aegis memory files.
 * @param {string} text
 * @returns {string}
 */
function sanitizeMemoryText(text) {
  return text
    .split(/\r?\n/)
    .filter((line) => !/(x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|secret|token|password|passwd|credential|authorization|auth|private[_-]?key)/i.test(line))
    .join('\n');
}

/**
 * Truncates text from the middle, preserving the start and end.
 * @param {string} text
 * @param {number} maxChars
 * @returns {string}
 */
function truncateMiddle(text, maxChars) {
  if (!text || text.length <= maxChars) {
    return text || '';
  }
  const half = Math.floor(maxChars / 2);
  return `${text.slice(0, half)}\n\n[...truncated...]\n\n${text.slice(text.length - half)}`;
}

module.exports = {
  safeErrorMessage,
  redactDiagnosticText,
  sanitizeMemoryText,
  truncateMiddle
};
