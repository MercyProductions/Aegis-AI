import { describe, expect, it } from 'vitest';
import type { ToolEvent } from '../types';
import {
  activityEventHasDetails,
  activityEventId,
  activityOutputText,
  clipActivityText,
  filterActivityEvents,
  payloadValueText
} from './activityEvents';

function event(overrides: Partial<ToolEvent>): ToolEvent {
  return {
    kind: 'info',
    title: 'Workspace scanned',
    status: 'ok',
    detail: '7 files found',
    payload: {},
    created_at: '2026-05-07T12:00:00Z',
    ...overrides
  };
}

describe('activity event helpers', () => {
  it('builds stable event IDs with a fallback timestamp label', () => {
    expect(activityEventId(event({}), 2)).toBe('2026-05-07T12:00:00Z|info|Workspace scanned|2');
    expect(activityEventId(event({ created_at: '' }), 0)).toBe('event|info|Workspace scanned|0');
  });

  it('detects whether events have expandable payload details', () => {
    expect(activityEventHasDetails(event({ payload: { command: 'npm test' } }))).toBe(true);
    expect(activityEventHasDetails(event({ payload: {} }))).toBe(false);
  });

  it('filters activity events by issue and command views', () => {
    const events = [
      event({ kind: 'info', status: 'ok', title: 'Ready' }),
      event({ kind: 'warning', status: 'warning', title: 'Needs attention' }),
      event({ kind: 'command', status: 'ok', title: 'Validation command' }),
      event({ kind: 'info', status: 'ok', title: 'Command payload', payload: { command: 'npm run validate' } })
    ];

    expect(filterActivityEvents(events, 'all')).toEqual(events);
    expect(filterActivityEvents(events, 'issues').map((item) => item.title)).toEqual(['Needs attention']);
    expect(filterActivityEvents(events, 'commands').map((item) => item.title)).toEqual([
      'Validation command',
      'Command payload'
    ]);
  });

  it('coerces command payload values for display without rendering objects', () => {
    const payload = {
      command: 'npm test',
      exit_code: 1,
      cached: false,
      reason: null,
      metadata: { nested: true }
    };

    expect(payloadValueText(payload, 'command')).toBe('npm test');
    expect(payloadValueText(payload, 'exit_code')).toBe('1');
    expect(payloadValueText(payload, 'cached')).toBe('false');
    expect(payloadValueText(payload, 'reason')).toBe('n/a');
    expect(payloadValueText(payload, 'metadata')).toBe('');
    expect(payloadValueText(payload, 'missing')).toBe('');
  });

  it('formats command output in the same stderr, stdout, reason order', () => {
    expect(activityOutputText({ stderr: 'failed', stdout: 'done', reason: 'exit 1' })).toBe(
      'Stderr:\nfailed\n\nStdout:\ndone\n\nReason:\nexit 1'
    );
    expect(activityOutputText({ stderr: '', stdout: 'done', reason: '' })).toBe('Stdout:\ndone');
  });

  it('clips long activity text only after the requested limit', () => {
    expect(clipActivityText('short', 10)).toBe('short');
    expect(clipActivityText('0123456789abc', 10)).toBe('0123456789\n... output truncated ...');
  });
});
