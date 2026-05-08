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
