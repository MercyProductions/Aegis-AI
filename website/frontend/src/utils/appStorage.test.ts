import { describe, expect, it } from 'vitest';
import {
  clearProviderBridgeDraft,
  loadProviderBridgeDraft,
  providerBridgeDraftStorageKey,
  saveProviderBridgeDraft
} from './appStorage';

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

describe('provider bridge draft storage', () => {
  it('saves, scopes, and clears drafts by workspace root', () => {
    const storage = new MemoryStorage();

    saveProviderBridgeDraft(
      'C:/Workspace/A',
      {
        providerId: 'openai',
        mode: 'review',
        model: 'gpt-5.5',
        workspaceRoot: 'C:/Workspace/A',
        message: 'review this file',
        contextPaths: ['src/App.tsx'],
        timeoutSeconds: 240,
        allowEdits: false,
        updatedAt: '2026-05-20T00:00:00.000Z'
      },
      storage
    );
    saveProviderBridgeDraft(
      'C:/Workspace/B',
      {
        providerId: 'anthropic',
        mode: 'build',
        model: 'sonnet',
        workspaceRoot: 'C:/Workspace/B',
        message: 'build this',
        contextPaths: ['README.md'],
        timeoutSeconds: 360,
        allowEdits: true,
        updatedAt: '2026-05-20T00:01:00.000Z'
      },
      storage
    );

    expect(loadProviderBridgeDraft('C:/Workspace/A', storage)).toMatchObject({
      providerId: 'openai',
      mode: 'review',
      contextPaths: ['src/App.tsx']
    });
    expect(loadProviderBridgeDraft('C:/Workspace/B', storage)).toMatchObject({
      providerId: 'anthropic',
      mode: 'build',
      allowEdits: true
    });

    clearProviderBridgeDraft('C:/Workspace/A', storage);
    expect(loadProviderBridgeDraft('C:/Workspace/A', storage)).toBeNull();
    expect(loadProviderBridgeDraft('C:/Workspace/B', storage)?.providerId).toBe('anthropic');

    clearProviderBridgeDraft('C:/Workspace/B', storage);
    expect(storage.getItem(providerBridgeDraftStorageKey)).toBeNull();
  });

  it('sanitizes malformed draft fields', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      providerBridgeDraftStorageKey,
      JSON.stringify({
        '__default__': {
          providerId: 'openai',
          mode: 'invalid',
          timeoutSeconds: 4000,
          allowEdits: true,
          contextPaths: ['src/App.tsx', 'C:/outside.txt', '../secret.txt', 'src/App.tsx']
        }
      })
    );

    expect(loadProviderBridgeDraft('', storage)).toMatchObject({
      providerId: 'openai',
      mode: 'build',
      timeoutSeconds: 900,
      allowEdits: true,
      contextPaths: ['src/App.tsx']
    });
  });
});
