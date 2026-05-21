import type { Mode } from '../types';

export type DetailPanelSection = 'generated' | 'workspace' | 'memory';
export type CustomAgent = {
  id: string;
  name: string;
  perspective: string;
  mission: string;
  mode: Mode;
  modelName: string;
  createdAt: string;
};
export type ProviderBridgeDraft = {
  providerId: string;
  mode: Mode;
  model: string;
  workspaceRoot: string;
  message: string;
  contextPaths: string[];
  timeoutSeconds: number;
  allowEdits: boolean;
  updatedAt: string;
};
type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const defaultAgentId = 'aegis-default';
export const detailPanelSectionOptions: DetailPanelSection[] = ['generated', 'workspace', 'memory'];
export const defaultAgentPerspective =
  'Direct, practical coding agent focused on planning, building, reviewing, and repairing this workspace.';

const customAgentsStorageKey = 'aegis.customAgents.v1';
const autoMemoryFingerprintStorageKey = 'aegis.autoMemoryFingerprints.v1';
const detailsPanelVisibleStorageKey = 'aegis.detailsPanelVisible.v1';
const detailPanelSectionsStorageKey = 'aegis.detailPanelSections.v1';
const selectedWorkspaceFileStorageKey = 'aegis.selectedWorkspaceFile.v1';
const queueAutoSendPausedStorageKey = 'aegis.queueAutoSendPaused.v1';
export const providerBridgeDraftStorageKey = 'aegis.providerBridgeDrafts.v1';

export function loadDetailsPanelVisible(): boolean {
  try {
    const raw = window.localStorage.getItem(detailsPanelVisibleStorageKey);
    if (!raw) return true;
    return JSON.parse(raw) !== false;
  } catch {
    return true;
  }
}

export function saveDetailsPanelVisible(visible: boolean) {
  try {
    window.localStorage.setItem(detailsPanelVisibleStorageKey, JSON.stringify(visible));
  } catch {
    // Layout preferences should never keep the app from opening.
  }
}

export function loadQueueAutoSendPaused(): boolean {
  try {
    const raw = window.localStorage.getItem(queueAutoSendPausedStorageKey);
    return raw ? JSON.parse(raw) === true : false;
  } catch {
    return false;
  }
}

export function saveQueueAutoSendPaused(paused: boolean) {
  try {
    window.localStorage.setItem(queueAutoSendPausedStorageKey, JSON.stringify(paused));
  } catch {
    // Queue preferences should never block chatting.
  }
}

export function loadCollapsedDetailSections(): DetailPanelSection[] {
  try {
    const raw = window.localStorage.getItem(detailPanelSectionsStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is DetailPanelSection =>
      detailPanelSectionOptions.includes(item as DetailPanelSection)
    );
  } catch {
    return [];
  }
}

export function saveCollapsedDetailSections(sections: DetailPanelSection[]) {
  try {
    const validSections = detailPanelSectionOptions.filter((section) => sections.includes(section));
    window.localStorage.setItem(detailPanelSectionsStorageKey, JSON.stringify(validSections));
  } catch {
    // Layout preferences are nice to keep, but should never block the app.
  }
}

export function loadSelectedWorkspaceFile(root: string): string {
  try {
    const rootKey = normalizeProjectRootKey(root);
    if (!rootKey) return '';
    const raw = window.localStorage.getItem(selectedWorkspaceFileStorageKey);
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return '';
    const value = (parsed as Record<string, unknown>)[rootKey];
    return typeof value === 'string' ? value : '';
  } catch {
    return '';
  }
}

export function saveSelectedWorkspaceFile(root: string, filePath: string) {
  try {
    const rootKey = normalizeProjectRootKey(root);
    if (!rootKey) return;
    const raw = window.localStorage.getItem(selectedWorkspaceFileStorageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    const selections = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};

    if (filePath.trim()) {
      (selections as Record<string, string>)[rootKey] = filePath;
    } else {
      delete (selections as Record<string, string>)[rootKey];
    }

    window.localStorage.setItem(selectedWorkspaceFileStorageKey, JSON.stringify(selections));
  } catch {
    // File preview memory should stay invisible if storage is unavailable.
  }
}

export function loadProviderBridgeDraft(root: string, storage: StorageLike | null = browserStorage()): ProviderBridgeDraft | null {
  try {
    if (!storage) return null;
    const rootKey = providerBridgeDraftRootKey(root);
    const raw = storage.getItem(providerBridgeDraftStorageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    const draft = (parsed as Record<string, unknown>)[rootKey];
    if (!draft || typeof draft !== 'object' || Array.isArray(draft)) return null;
    return sanitizeProviderBridgeDraft(draft as Partial<ProviderBridgeDraft>);
  } catch {
    storage?.removeItem(providerBridgeDraftStorageKey);
    return null;
  }
}

export function saveProviderBridgeDraft(
  root: string,
  draft: Omit<ProviderBridgeDraft, 'updatedAt'> & { updatedAt?: string },
  storage: StorageLike | null = browserStorage()
) {
  try {
    if (!storage) return;
    const rootKey = providerBridgeDraftRootKey(root);
    const raw = storage.getItem(providerBridgeDraftStorageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    const drafts = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    (drafts as Record<string, ProviderBridgeDraft>)[rootKey] = {
      providerId: draft.providerId || '',
      mode: normalizeProviderBridgeDraftMode(draft.mode),
      model: draft.model || '',
      workspaceRoot: draft.workspaceRoot || '',
      message: (draft.message || '').slice(0, 120_000),
      contextPaths: normalizeProviderBridgeDraftPaths(draft.contextPaths),
      timeoutSeconds: normalizeProviderBridgeDraftTimeout(draft.timeoutSeconds),
      allowEdits: Boolean(draft.allowEdits),
      updatedAt: draft.updatedAt || new Date().toISOString()
    };
    storage.setItem(providerBridgeDraftStorageKey, JSON.stringify(drafts));
  } catch {
    // Provider launch drafts should never block the settings surface.
  }
}

export function clearProviderBridgeDraft(root: string, storage: StorageLike | null = browserStorage()) {
  try {
    if (!storage) return;
    const rootKey = providerBridgeDraftRootKey(root);
    const raw = storage.getItem(providerBridgeDraftStorageKey);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    const drafts = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    delete (drafts as Record<string, unknown>)[rootKey];
    if (Object.keys(drafts).length) {
      storage.setItem(providerBridgeDraftStorageKey, JSON.stringify(drafts));
    } else {
      storage.removeItem(providerBridgeDraftStorageKey);
    }
  } catch {
    storage?.removeItem(providerBridgeDraftStorageKey);
  }
}

export function loadCustomAgents(): CustomAgent[] {
  try {
    const raw = window.localStorage.getItem(customAgentsStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Partial<CustomAgent>[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is CustomAgent => Boolean(item?.id && item.name))
      .map((item) => {
        const nextMode =
          typeof item.mode === 'string' && ['build', 'develop', 'review', 'chat'].includes(item.mode)
            ? (item.mode as Mode)
            : 'build';
        return {
          id: item.id,
          name: item.name,
          perspective: item.perspective || defaultAgentPerspective,
          mission: item.mission || defaultAgentPerspective,
          mode: nextMode,
          modelName: item.modelName || '',
          createdAt: item.createdAt || new Date().toISOString()
        };
      });
  } catch {
    return [];
  }
}

export function saveCustomAgents(agents: CustomAgent[]) {
  try {
    window.localStorage.setItem(customAgentsStorageKey, JSON.stringify(agents));
  } catch {
    // Browser storage can be unavailable in private contexts.
  }
}

export function loadAutoMemoryFingerprints(): string[] {
  try {
    if (typeof window === 'undefined') return [];
    const raw = window.localStorage.getItem(autoMemoryFingerprintStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === 'string' && Boolean(item.trim())).slice(0, 120);
  } catch {
    return [];
  }
}

export function saveAutoMemoryFingerprints(fingerprints: string[]) {
  try {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(autoMemoryFingerprintStorageKey, JSON.stringify(fingerprints.slice(-120)));
  } catch {
    // Conversation memory is helpful, but storage failures should never block chat.
  }
}

export function normalizeProjectRootKey(value: string): string {
  return value.trim().replace(/[\\/]+$/, '').toLowerCase();
}

function providerBridgeDraftRootKey(root: string): string {
  return normalizeProjectRootKey(root) || '__default__';
}

function sanitizeProviderBridgeDraft(draft: Partial<ProviderBridgeDraft>): ProviderBridgeDraft | null {
  if (!draft || typeof draft !== 'object') return null;
  return {
    providerId: typeof draft.providerId === 'string' ? draft.providerId.slice(0, 80) : '',
    mode: normalizeProviderBridgeDraftMode(draft.mode),
    model: typeof draft.model === 'string' ? draft.model.slice(0, 160) : '',
    workspaceRoot: typeof draft.workspaceRoot === 'string' ? draft.workspaceRoot : '',
    message: typeof draft.message === 'string' ? draft.message.slice(0, 120_000) : '',
    contextPaths: normalizeProviderBridgeDraftPaths(draft.contextPaths),
    timeoutSeconds: normalizeProviderBridgeDraftTimeout(draft.timeoutSeconds),
    allowEdits: Boolean(draft.allowEdits),
    updatedAt: typeof draft.updatedAt === 'string' && draft.updatedAt.trim() ? draft.updatedAt : ''
  };
}

function normalizeProviderBridgeDraftMode(mode: unknown): Mode {
  return typeof mode === 'string' && ['build', 'develop', 'review', 'chat'].includes(mode) ? (mode as Mode) : 'build';
}

function normalizeProviderBridgeDraftTimeout(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed)) return 240;
  return Math.max(5, Math.min(900, Math.round(parsed)));
}

function normalizeProviderBridgeDraftPaths(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const paths: string[] = [];
  for (const item of value) {
    const path = String(item || '').trim().replace(/\\/g, '/');
    if (!path || /^[A-Za-z]:\//.test(path) || path.startsWith('/') || path.split('/').some((part) => part === '..' || part === '.')) {
      continue;
    }
    if (seen.has(path)) continue;
    seen.add(path);
    paths.push(path);
    if (paths.length >= 50) break;
  }
  return paths;
}

function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage;
}
