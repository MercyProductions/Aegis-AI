import type { AuthSessionResponse } from '../types';

export type SidebarSection =
  | 'chat'
  | 'projects'
  | 'intelligence'
  | 'workspace-intelligence'
  | 'runtime'
  | 'adaptive'
  | 'hardening'
  | 'ecosystem'
  | 'autonomous'
  | 'creative'
  | 'tasks'
  | 'agents'
  | 'models';

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const AUTH_SESSION_STORAGE_KEY = 'aegis.auth.session.v1';

const legacyProtectedRoutes: Record<string, string> = {
  '/chat': '/app/chat',
  '/workspace': '/app/workspace',
  '/projects': '/app/projects',
  '/tasks': '/app/tasks',
  '/agents': '/app/agents',
  '/models': '/app/models',
  '/automation': '/app/automation',
  '/research': '/app/research',
  '/creative-studio': '/app/creative-studio',
  '/memory': '/app/memory',
  '/settings': '/app/settings'
};

const protectedSectionRoutes: Record<SidebarSection, string> = {
  chat: '/app/chat',
  projects: '/app/projects',
  intelligence: '/app/research',
  'workspace-intelligence': '/app/workspace',
  runtime: '/app/runtime',
  adaptive: '/app/adaptive',
  hardening: '/app/hardening',
  ecosystem: '/app/ecosystem',
  autonomous: '/app/automation',
  creative: '/app/creative-studio',
  tasks: '/app/tasks',
  agents: '/app/agents',
  models: '/app/models'
};

const protectedRouteSections: Record<string, SidebarSection> = {
  '/app': 'chat',
  '/app/chat': 'chat',
  '/app/workspace': 'workspace-intelligence',
  '/app/projects': 'projects',
  '/app/tasks': 'tasks',
  '/app/agents': 'agents',
  '/app/models': 'models',
  '/app/automation': 'autonomous',
  '/app/research': 'intelligence',
  '/app/creative-studio': 'creative',
  '/app/memory': 'chat',
  '/app/settings': 'chat',
  '/app/runtime': 'runtime',
  '/app/intelligence': 'intelligence',
  '/app/adaptive': 'adaptive',
  '/app/hardening': 'hardening',
  '/app/ecosystem': 'ecosystem',
  '/app/autonomous': 'autonomous'
};

export function normalizeRoutePath(path: string) {
  const cleanPath = (path || '/').split(/[?#]/)[0].replace(/\/+$/, '') || '/';
  return legacyProtectedRoutes[cleanPath] ?? cleanPath;
}

export function currentBrowserRoute() {
  if (typeof window === 'undefined') return '/';
  return normalizeRoutePath(window.location.pathname);
}

export function currentViewportSize() {
  if (typeof window === 'undefined') return { width: 1440, height: 900 };
  return { width: window.innerWidth, height: window.innerHeight };
}

export function isProtectedAppRoute(path: string) {
  const route = normalizeRoutePath(path);
  return route === '/app' || route.startsWith('/app/');
}

export function routeToSidebarSection(path: string): SidebarSection {
  return protectedRouteSections[normalizeRoutePath(path)] ?? 'chat';
}

export function sidebarSectionToRoute(section: SidebarSection) {
  return protectedSectionRoutes[section] ?? '/app/chat';
}

export function isStoredAuthSession(value: unknown): value is AuthSessionResponse {
  if (!value || typeof value !== 'object') return false;
  const session = value as Partial<AuthSessionResponse>;
  return Boolean(session.token && session.user && typeof session.user.email === 'string');
}

export function loadStoredAuthSession(storage = browserStorage()): AuthSessionResponse | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(AUTH_SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (isStoredAuthSession(parsed)) return parsed;
    storage.removeItem(AUTH_SESSION_STORAGE_KEY);
    return null;
  } catch {
    storage.removeItem(AUTH_SESSION_STORAGE_KEY);
    return null;
  }
}

export function saveStoredAuthSession(session: AuthSessionResponse, storage = browserStorage()) {
  if (!storage) return;
  storage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredAuthSession(storage = browserStorage()) {
  if (!storage) return;
  storage.removeItem(AUTH_SESSION_STORAGE_KEY);
}

function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage;
}
