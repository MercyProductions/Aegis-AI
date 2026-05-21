// Shared Aegis Core envelope helpers for the VS Code client.

const AEGIS_CORE_API_VERSION = 'v1';
const AEGIS_CORE_CONTRACT_VERSION = '2026.05.12';

function defaultRedactor(text, maxChars = 700) {
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
    .replace(/\b(Authorization\s*[:=]\s*)(?:Bearer|Basic|Digest)?\s*[A-Za-z0-9._~+/\-=]+/gi, '$1[redacted]')
    .replace(/\b((?:x-api-key|[A-Z0-9_-]*api[_-]?key|[A-Z0-9_-]*api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|[A-Z0-9_-]*token|client[_-]?secret|[A-Z0-9_-]*secret|password|passwd|credential|authorization|private[_-]?key)\s*[:=]\s*)[^\s&]+/gi, '$1[redacted]');
  if (maxChars > 0 && cleaned.length > maxChars) {
    return `${cleaned.slice(0, Math.max(0, maxChars - 3))}...`;
  }
  return cleaned;
}

function redactorFrom(options) {
  return options && typeof options.redactDiagnosticText === 'function'
    ? options.redactDiagnosticText
    : defaultRedactor;
}

function validateCoreEnvelope(envelope, expectedKind, options = {}) {
  const redact = redactorFrom(options);
  if (!envelope || typeof envelope !== 'object') {
    throw new Error('Aegis Core response was not a JSON object.');
  }
  const apiVersion = typeof envelope.api_version === 'string' ? envelope.api_version : '';
  if (apiVersion !== AEGIS_CORE_API_VERSION) {
    throw new Error(`Aegis Core response used unexpected api_version: ${apiVersion ? redact(apiVersion) : 'missing'}.`);
  }
  const kind = typeof envelope.kind === 'string' ? envelope.kind : '';
  if (expectedKind && kind !== expectedKind) {
    throw new Error(`Aegis Core response kind mismatch: expected ${expectedKind}, got ${kind ? redact(kind) : 'missing'}.`);
  }
  return envelope;
}

function coreEnvelopeData(envelope) {
  return envelope && envelope.data && typeof envelope.data === 'object' ? envelope.data : {};
}

function coreEnvelopeError(envelope, options = {}) {
  const redact = redactorFrom(options);
  const data = coreEnvelopeData(envelope);
  const detail = data.error || data.message || (Array.isArray(envelope && envelope.deprecations) && envelope.deprecations.join('; ')) || '';
  return detail ? redact(detail) || 'Core returned ok=false.' : 'Core returned ok=false.';
}

function requireCoreOk(envelope, action, options = {}) {
  if (envelope && envelope.ok === false) {
    throw new Error(`Aegis Core could not ${action || 'complete the operation'}: ${coreEnvelopeError(envelope, options)}`);
  }
  return envelope;
}

function formatCoreContract(envelope, testedVersion = AEGIS_CORE_CONTRACT_VERSION) {
  const version = envelope && envelope.contract_version ? envelope.contract_version : 'unknown contract';
  const stability = envelope && envelope.stability ? envelope.stability : 'unknown stability';
  const compatibility = version !== testedVersion ? `; tested ${testedVersion}` : '';
  return `contract ${version} (${stability}${compatibility})`;
}

function isCoreEnvelope(value, kind) {
  return Boolean(value && typeof value === 'object' && value.api_version === AEGIS_CORE_API_VERSION && (!kind || value.kind === kind));
}

module.exports = {
  AEGIS_CORE_API_VERSION,
  AEGIS_CORE_CONTRACT_VERSION,
  validateCoreEnvelope,
  coreEnvelopeData,
  coreEnvelopeError,
  requireCoreOk,
  formatCoreContract,
  isCoreEnvelope
};
