import { describe, expect, it } from 'vitest';
import {
  COMPOSER_DRAFT_STORAGE_KEY,
  MAX_COMPOSER_DRAFT_CHARS,
  clearComposerDraft,
  createComposerDraft,
  loadComposerDraft,
  saveComposerDraft
} from './composerDraft';

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

describe('composer draft utilities', () => {
  it('creates a draft while preserving useful whitespace and timestamp', () => {
    expect(createComposerDraft('  build this next  ', '2026-05-05T00:00:00.000Z')).toEqual({
      content: '  build this next  ',
      updatedAt: '2026-05-05T00:00:00.000Z'
    });
  });

  it('does not create blank drafts', () => {
    expect(createComposerDraft('   ')).toBeNull();
  });

  it('saves, loads, and clears a draft', () => {
    const storage = new MemoryStorage();

    saveComposerDraft('continue the chatbot work', storage);
    expect(loadComposerDraft(storage)?.content).toBe('continue the chatbot work');

    clearComposerDraft(storage);
    expect(loadComposerDraft(storage)).toBeNull();
  });

  it('clears storage when saving a blank draft', () => {
    const storage = new MemoryStorage();
    saveComposerDraft('temporary draft', storage);
    saveComposerDraft('   ', storage);

    expect(storage.getItem(COMPOSER_DRAFT_STORAGE_KEY)).toBeNull();
  });

  it('tolerates malformed storage and caps oversized drafts', () => {
    const storage = new MemoryStorage();
    storage.setItem(COMPOSER_DRAFT_STORAGE_KEY, '{ nope');
    expect(loadComposerDraft(storage)).toBeNull();

    const largeDraft = 'x'.repeat(MAX_COMPOSER_DRAFT_CHARS + 20);
    saveComposerDraft(largeDraft, storage);
    expect(loadComposerDraft(storage)?.content).toHaveLength(MAX_COMPOSER_DRAFT_CHARS);
  });
});
