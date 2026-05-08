import { describe, expect, it } from 'vitest';
import {
  connectionStateDetail,
  connectionStateLabel,
  isLikelyConnectionError
} from './connection';

describe('connection utilities', () => {
  it('labels every connection state for the status UI', () => {
    expect(connectionStateLabel('checking')).toBe('Checking');
    expect(connectionStateLabel('connected')).toBe('Connected');
    expect(connectionStateLabel('reconnecting')).toBe('Reconnecting');
    expect(connectionStateLabel('offline')).toBe('Offline');
    expect(connectionStateLabel('failed')).toBe('Failed');
  });

  it('describes queued-send behavior for reconnect states', () => {
    expect(connectionStateDetail('connected')).toContain('send now');
    expect(connectionStateDetail('reconnecting')).toContain('reconnect');
    expect(connectionStateDetail('offline')).toContain('offline');
  });

  it('classifies transport failures as retryable connection errors', () => {
    expect(isLikelyConnectionError('Failed to fetch')).toBe(true);
    expect(isLikelyConnectionError('ECONNREFUSED 127.0.0.1')).toBe(true);
    expect(isLikelyConnectionError('Request timed out while talking to backend')).toBe(true);
  });

  it('does not requeue normal validation or model errors as connection failures', () => {
    expect(isLikelyConnectionError('Validation failed: missing import in src/App.tsx')).toBe(false);
    expect(isLikelyConnectionError('Model returned invalid JSON for a draft')).toBe(false);
  });
});
