// Extension settings and configuration logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const MAX_CONTEXT_CHARS = 100000;

/**
 * Normalizes a base URL for HTTP services (Ollama, Aegis Core).
 */
function normalizeHttpBaseUrl(value, fallback) {
  const defaultBase = String(fallback || '').trim();
  const raw = String(value || '').trim();
  if (!raw || /\s/.test(raw)) {
    return defaultBase;
  }

  let candidate = raw;
  const lowered = candidate.toLowerCase();
  if (!lowered.startsWith('http://') && !lowered.startsWith('https://')) {
    if (candidate.includes('://')) {
      return defaultBase;
    }
    candidate = `http://${candidate}`;
  }

  try {
    const url = new URL(candidate);
    if (!url.hostname || url.username || url.password) {
      return defaultBase;
    }
    return `${url.protocol}//${url.host}${stripKnownServiceEndpointPath(url.pathname)}`;
  } catch (error) {
    return defaultBase;
  }
}

/**
 * Removes known API version or endpoint suffixes from a URL path.
 */
function stripKnownServiceEndpointPath(pathname) {
  const cleaned = String(pathname || '').replace(/\/+$/, '');
  if (!cleaned || cleaned === '/') {
    return '';
  }

  const segments = cleaned.split('/').filter(Boolean);
  const lowered = segments.map((segment) => segment.toLowerCase());
  const v1Index = lowered.indexOf('v1');
  if (v1Index !== -1) {
    return v1Index ? `/${segments.slice(0, v1Index).join('/')}` : '';
  }

  const apiIndex = lowered.indexOf('api');
  const ollamaEndpoint = apiIndex === -1 ? '' : lowered[apiIndex + 1] || '';
  const ollamaEndpointPaths = ['chat', 'embeddings', 'generate', 'ps', 'show', 'tags', 'version'];
  if (apiIndex !== -1 && ollamaEndpointPaths.includes(ollamaEndpoint)) {
    return apiIndex ? `/${segments.slice(0, apiIndex).join('/')}` : '';
  }

  const lastSegment = lowered[lowered.length - 1];
  if (lastSegment === 'health' || lastSegment === 'models') {
    return segments.length > 1 ? `/${segments.slice(0, -1).join('/')}` : '';
  }

  return cleaned;
}

/**
 * Constructs a service URL from a base and a path.
 */
function serviceUrl(baseUrl, pathname) {
  const url = new URL(baseUrl);
  const basePath = url.pathname.replace(/\/+$/, '');
  const suffix = String(pathname || '').replace(/^\/+/, '');
  url.pathname = `${basePath}/${suffix}`.replace(/\/+/g, '/');
  url.search = '';
  url.hash = '';
  return url;
}

/**
 * Ensures a numeric config value is within bounds.
 */
function boundedConfigInt(value, min, max, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.floor(n)));
}

/**
 * Extracts and normalizes settings from a vscode.WorkspaceConfiguration object.
 */
function getNormalizedConfig(config) {
  const reader = config && typeof config.get === 'function'
    ? config
    : { get: (_key, fallback) => fallback };
  return {
    ollamaUrl: normalizeHttpBaseUrl(reader.get('ollamaUrl', 'http://127.0.0.1:11434'), 'http://127.0.0.1:11434'),
    coreUrl: normalizeHttpBaseUrl(reader.get('coreUrl', 'http://127.0.0.1:8788'), 'http://127.0.0.1:8788'),
    chatModel: reader.get('chatModel', 'qwen3-coder:30b'),
    fastModel: reader.get('fastModel', 'qwen2.5-coder:7b'),
    fallbackModels: reader.get('fallbackModels', ['qwen2.5-coder:7b', 'granite-code:8b']),
    embeddingModel: reader.get('embeddingModel', 'mxbai-embed-large:latest'),
    autopilotIntervalMinutes: reader.get('autopilotIntervalMinutes', 15),
    autopilotWriteMode: reader.get('autopilotWriteMode', 'preview'),
    maxContextFiles: reader.get('maxContextFiles', 12),
    maxContextChars: reader.get('maxContextChars', MAX_CONTEXT_CHARS),
    maxProposalDiffTabs: boundedConfigInt(reader.get('maxProposalDiffTabs', 12), 1, 25, 12),
    autoScanOnOpen: reader.get('autoScanOnOpen', true),
    validationCommandPreferences: reader.get('validationCommandPreferences', []),
    safetyMode: reader.get('safetyMode', 'standard'),
    excludeGlob: reader.get('excludeGlob', '{**/node_modules/**,**/.git/**,**/.venv/**,**/x64/**,**/build/**,**/dist/**,**/.tmp/**,**/smoke-artifacts/**,**/stress-artifacts/**}')
  };
}

module.exports = {
  normalizeHttpBaseUrl,
  stripKnownServiceEndpointPath,
  serviceUrl,
  boundedConfigInt,
  getNormalizedConfig,
  MAX_CONTEXT_CHARS
};
