import { describe, expect, it } from 'vitest';
import {
  MAX_QUEUED_MESSAGES,
  QUEUED_MESSAGES_STORAGE_KEY,
  appendQueuedMessage,
  createQueuedMessage,
  clearQueuedMessages,
  loadQueuedMessages,
  moveQueuedMessage,
  removeQueuedMessage,
  saveQueuedMessages,
  shouldQueueOutboundMessage
} from './messageQueue';
import type { QueuedMessage } from './messageQueue';

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }

  removeItem(key: string) {
    this.values.delete(key);
  }
}

describe('message queue utilities', () => {
  it('creates a queued message while preserving execution options', () => {
    const message = createQueuedMessage('  build this project  ', {
      id: 'queued-1',
      threadId: 'thread-1',
      createdAt: '2026-05-02T00:00:00.000Z',
      workspaceRoot: 'C:\\Projects\\Aegis',
      mode: 'develop',
      applyChanges: true,
      runValidation: true,
      contextPaths: ['src\\App.tsx', 'src/App.tsx', '../secret.txt'],
      historyRecorded: true,
      history: [
        { role: 'user', content: '  original request  ' },
        { role: 'assistant', content: 'working' },
        { role: 'assistant', content: '   ' }
      ]
    });

    expect(message).toEqual({
      id: 'queued-1',
      threadId: 'thread-1',
      content: 'build this project',
      createdAt: '2026-05-02T00:00:00.000Z',
      workspaceRoot: 'C:\\Projects\\Aegis',
      mode: 'develop',
      applyChanges: true,
      runValidation: true,
      contextPaths: ['src/App.tsx'],
      historyRecorded: true,
      missionAnchor: null,
      history: [
        { role: 'user', content: 'original request' },
        { role: 'assistant', content: 'working' }
      ]
    });
  });

  it('does not queue blank messages', () => {
    expect(createQueuedMessage('   ')).toBeNull();
  });

  it('deduplicates queued messages by id and keeps the newest version', () => {
    const first = createQueuedMessage('first', { id: 'same' });
    const second = createQueuedMessage('second', { id: 'same' });

    expect(first && second ? appendQueuedMessage([first], second) : []).toMatchObject([
      { id: 'same', content: 'second' }
    ]);
  });

  it('limits the queue to the most recent messages', () => {
    const messages = Array.from({ length: MAX_QUEUED_MESSAGES + 3 }, (_, index) =>
      createQueuedMessage(`message ${index}`, { id: `queued-${index}` })
    ).filter((item): item is NonNullable<typeof item> => Boolean(item));

    const result = messages.reduce<QueuedMessage[]>(
      (current, message) => appendQueuedMessage(current, message),
      []
    );

    expect(result).toHaveLength(MAX_QUEUED_MESSAGES);
    expect(result[0].id).toBe('queued-3');
  });

  it('removes one queued message by id without disturbing the others', () => {
    const first = createQueuedMessage('first', { id: 'first' });
    const second = createQueuedMessage('second', { id: 'second' });

    const result = first && second ? removeQueuedMessage([first, second], 'first') : [];

    expect(result).toMatchObject([{ id: 'second', content: 'second' }]);
  });

  it('moves queued messages earlier or later without changing their payloads', () => {
    const first = createQueuedMessage('first', { id: 'first', runValidation: true });
    const second = createQueuedMessage('second', { id: 'second', applyChanges: true });
    const third = createQueuedMessage('third', { id: 'third' });
    const queue = first && second && third ? [first, second, third] : [];

    const earlier = moveQueuedMessage(queue, 'third', 'up');
    expect(earlier.map((item) => item.id)).toEqual(['first', 'third', 'second']);
    expect(earlier[2]).toMatchObject({ id: 'second', applyChanges: true });

    const later = moveQueuedMessage(earlier, 'first', 'down');
    expect(later.map((item) => item.id)).toEqual(['third', 'first', 'second']);
    expect(later[1]).toMatchObject({ id: 'first', runValidation: true });
  });

  it('leaves queue order unchanged when a move is not possible', () => {
    const first = createQueuedMessage('first', { id: 'first' });
    const second = createQueuedMessage('second', { id: 'second' });
    const queue = first && second ? [first, second] : [];

    expect(moveQueuedMessage(queue, 'missing', 'up')).toBe(queue);
    expect(moveQueuedMessage(queue, 'first', 'up')).toBe(queue);
    expect(moveQueuedMessage(queue, 'second', 'down')).toBe(queue);
  });

  it('clears all queued messages', () => {
    const queued = createQueuedMessage('queued', { id: 'queued' });

    expect(clearQueuedMessages()).toEqual([]);
    expect(queued ? clearQueuedMessages().concat(queued) : []).toHaveLength(queued ? 1 : 0);
  });

  it('loads only valid queue entries and tolerates malformed storage', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      QUEUED_MESSAGES_STORAGE_KEY,
      JSON.stringify([
        {
          id: 'valid',
          threadId: 'thread-valid',
          content: 'continue',
          createdAt: '2026-05-02T00:00:00.000Z',
          workspaceRoot: 'C:\\Projects\\Aegis',
          mode: 'build',
          applyChanges: true,
          runValidation: false,
          contextPaths: ['README.md'],
          historyRecorded: false,
          missionAnchor: {
            role: 'system',
            content:
              'Aegis mission anchor:\n- Original user mission: create a C++ console app at C:\\Projects\\Aegis'
          },
          history: [{ role: 'user', content: 'first request' }]
        },
        {
          id: 'invalid',
          threadId: 'thread-invalid',
          content: '',
          createdAt: '2026-05-02T00:00:00.000Z',
          workspaceRoot: 'C:\\Projects\\Aegis',
          mode: 'invalid',
          applyChanges: true,
          runValidation: false,
          historyRecorded: false,
          history: []
        }
      ])
    );

    expect(loadQueuedMessages(storage)).toMatchObject([
      {
        id: 'valid',
        threadId: 'thread-valid',
        contextPaths: ['README.md'],
        missionAnchor: {
          role: 'system',
          content:
            'Aegis mission anchor:\n- Original user mission: create a C++ console app at C:\\Projects\\Aegis'
        },
        history: [{ role: 'user', content: 'first request' }]
      }
    ]);
    const cleanedRaw = storage.getItem(QUEUED_MESSAGES_STORAGE_KEY);
    expect(cleanedRaw ? JSON.parse(cleanedRaw) : []).toHaveLength(1);

    storage.setItem(QUEUED_MESSAGES_STORAGE_KEY, '{ nope');
    expect(loadQueuedMessages(storage)).toEqual([]);
    expect(storage.getItem(QUEUED_MESSAGES_STORAGE_KEY)).toBeNull();
  });

  it('clears non-array queued message payloads during recovery', () => {
    const storage = new MemoryStorage();
    storage.setItem(QUEUED_MESSAGES_STORAGE_KEY, JSON.stringify({ id: 'wrong-shape' }));

    expect(loadQueuedMessages(storage)).toEqual([]);
    expect(storage.getItem(QUEUED_MESSAGES_STORAGE_KEY)).toBeNull();
  });

  it('keeps legacy queued messages without thread snapshots valid', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      QUEUED_MESSAGES_STORAGE_KEY,
      JSON.stringify([
        {
          id: 'legacy',
          content: 'continue old work',
          createdAt: '2026-05-02T00:00:00.000Z',
          workspaceRoot: 'C:\\Projects\\Aegis',
          mode: 'build',
          applyChanges: false,
          runValidation: true,
          contextPaths: ['src\\legacy.ts'],
          historyRecorded: false
        }
      ])
    );

    expect(loadQueuedMessages(storage)).toMatchObject([
      {
        id: 'legacy',
        content: 'continue old work',
        contextPaths: ['src/legacy.ts']
      }
    ]);
  });

  it('keeps legacy queued messages without pinned context valid', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      QUEUED_MESSAGES_STORAGE_KEY,
      JSON.stringify([
        {
          id: 'legacy-no-pins',
          content: 'continue old work',
          createdAt: '2026-05-02T00:00:00.000Z',
          workspaceRoot: 'C:\\Projects\\Aegis',
          mode: 'build',
          applyChanges: false,
          runValidation: true,
          historyRecorded: false
        }
      ])
    );

    expect(loadQueuedMessages(storage)).toMatchObject([
      {
        id: 'legacy-no-pins',
        content: 'continue old work',
        contextPaths: []
      }
    ]);
  });

  it('caps queued history snapshots to the newest useful context', () => {
    const history = Array.from({ length: 20 }, (_, index) => ({
      role: 'user' as const,
      content: `message ${index}`
    }));

    const message = createQueuedMessage('continue', { history });

    expect(message?.history).toHaveLength(16);
    expect(message?.history[0].content).toBe('message 4');
    expect(message?.history.at(-1)?.content).toBe('message 19');
  });

  it('preserves only sanitized mission anchors for queued replay', () => {
    const anchor = {
      role: 'system' as const,
      content:
        'Aegis mission anchor:\n- Original user mission: refine the existing DLL at C:\\Projects\\NativeTool'
    };

    const message = createQueuedMessage('continue', { missionAnchor: anchor });
    const invalid = createQueuedMessage('continue', {
      missionAnchor: { role: 'user', content: anchor.content }
    });

    expect(message?.missionAnchor).toEqual(anchor);
    expect(invalid?.missionAnchor).toBeNull();
  });

  it('saves at most the queue limit', () => {
    const storage = new MemoryStorage();
    const messages = Array.from({ length: MAX_QUEUED_MESSAGES + 5 }, (_, index) =>
      createQueuedMessage(`message ${index}`, { id: `queued-${index}` })
    ).filter((item): item is NonNullable<typeof item> => Boolean(item));

    saveQueuedMessages(messages, storage);

    const raw = storage.getItem(QUEUED_MESSAGES_STORAGE_KEY);
    expect(raw ? JSON.parse(raw) : []).toHaveLength(MAX_QUEUED_MESSAGES);
  });

  it('queues new outbound messages while busy or disconnected', () => {
    expect(shouldQueueOutboundMessage(true, 'connected', null)).toBe(true);
    expect(shouldQueueOutboundMessage(false, 'reconnecting', null)).toBe(true);
    expect(shouldQueueOutboundMessage(false, 'offline', null)).toBe(true);
    expect(shouldQueueOutboundMessage(false, 'failed', null)).toBe(true);
    expect(shouldQueueOutboundMessage(false, 'checking', null)).toBe(true);
    expect(shouldQueueOutboundMessage(false, 'connected', null)).toBe(false);
  });

  it('allows queued replays to send once connected', () => {
    const queued = createQueuedMessage('continue', {
      id: 'queued-replay',
      workspaceRoot: 'C:\\Projects\\Aegis',
      mode: 'build'
    });

    expect(queued).not.toBeNull();
    expect(shouldQueueOutboundMessage(false, 'connected', queued)).toBe(false);
    expect(shouldQueueOutboundMessage(true, 'connected', queued)).toBe(true);
  });
});
