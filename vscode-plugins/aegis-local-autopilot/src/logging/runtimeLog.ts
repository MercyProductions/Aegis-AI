// Small logging adapter for runtime ownership decisions.

const { safeErrorMessage } = require('../utils/errors.ts');

function createRuntimeLogger(output) {
  return {
    info(operation, message, details = {}) {
      write(output, operation, message, details);
    },
    fallback(operation, error, details = {}) {
      write(output, operation, `Fallback to local VS Code runtime: ${safeErrorMessage(error)}`, details);
    },
    core(operation, message, details = {}) {
      write(output, operation, `Core runtime: ${message}`, details);
    }
  };
}

function write(output, operation, message, details) {
  if (!output || typeof output.appendLine !== 'function') {
    return;
  }
  const suffix = details && Object.keys(details).length
    ? ` ${JSON.stringify(sanitizeDetails(details))}`
    : '';
  output.appendLine(`[${new Date().toISOString()}] runtime:${operation}: ${message}${suffix}`);
}

function sanitizeDetails(value) {
  if (Array.isArray(value)) {
    return value.map(sanitizeDetails);
  }
  if (value && typeof value === 'object') {
    const clean = {};
    for (const [key, item] of Object.entries(value)) {
      if (/(token|secret|password|credential|api[_-]?key|authorization)/i.test(key)) {
        clean[key] = '[redacted]';
      } else {
        clean[key] = sanitizeDetails(item);
      }
    }
    return clean;
  }
  return value;
}

module.exports = {
  createRuntimeLogger,
  sanitizeDetails
};
