export const COMPOSER_DRAFT_STORAGE_KEY = 'aegis.web.composerDraft.v1';
export const MAX_COMPOSER_DRAFT_CHARS = 20000;

export type ComposerDraft = {
  content: string;
  updatedAt: string;
};

type ComposerDraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export function createComposerDraft(content: string, updatedAt = new Date().toISOString()): ComposerDraft | null {
  if (!content.trim()) return null;

  return {
    content: content.slice(0, MAX_COMPOSER_DRAFT_CHARS),
    updatedAt
  };
}

export function loadComposerDraft(storage = resolveComposerDraftStorage()): ComposerDraft | null {
  if (!storage) return null;

  try {
    const raw = storage.getItem(COMPOSER_DRAFT_STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!isComposerDraft(parsed)) return null;

    return createComposerDraft(parsed.content, parsed.updatedAt);
  } catch {
    return null;
  }
}

export function saveComposerDraft(content: string, storage = resolveComposerDraftStorage()) {
  if (!storage) return;

  const draft = createComposerDraft(content);
  if (!draft) {
    clearComposerDraft(storage);
    return;
  }

  try {
    storage.setItem(COMPOSER_DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Draft persistence is best-effort; never block typing if storage is unavailable.
  }
}

export function clearComposerDraft(storage = resolveComposerDraftStorage()) {
  if (!storage) return;

  try {
    storage.removeItem(COMPOSER_DRAFT_STORAGE_KEY);
  } catch {
    try {
      storage.setItem(COMPOSER_DRAFT_STORAGE_KEY, '');
    } catch {
      // Keep the composer usable if storage is unavailable.
    }
  }
}

function isComposerDraft(value: unknown): value is ComposerDraft {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as ComposerDraft;
  return (
    typeof candidate.content === 'string' &&
    candidate.content.trim().length > 0 &&
    typeof candidate.updatedAt === 'string'
  );
}

function resolveComposerDraftStorage(): ComposerDraftStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}
