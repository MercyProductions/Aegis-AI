import { describe, expect, it } from 'vitest';
import type { AuthSessionResponse } from '../types';
import {
  AUTH_SESSION_STORAGE_KEY,
  clearStoredAuthSession,
  isProtectedAppRoute,
  isStoredAuthSession,
  loadStoredAuthSession,
  normalizeRoutePath,
  routeToSidebarSection,
  saveStoredAuthSession,
  sidebarSectionToRoute
} from './appRouting';

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

function session(): AuthSessionResponse {
  return {
    token: 'local-token',
    token_type: 'bearer',
    expires_at: '2026-05-07T00:00:00.000Z',
    user: {
      id: 'user-1',
      name: 'Auralith User',
      email: 'user@example.com',
      role: 'user',
      plan: 'free',
      status: 'active',
      created_at: '2026-05-07T00:00:00.000Z'
    }
  };
}

describe('app routing utilities', () => {
  it('normalizes legacy protected routes into the app shell', () => {
    expect(normalizeRoutePath('/chat')).toBe('/app/chat');
    expect(normalizeRoutePath('/workspace/')).toBe('/app/workspace');
    expect(normalizeRoutePath('/app/tasks?panel=timeline')).toBe('/app/tasks');
  });

  it('maps protected routes and sidebar sections predictably', () => {
    expect(isProtectedAppRoute('/app')).toBe(true);
    expect(isProtectedAppRoute('/app/projects')).toBe(true);
    expect(isProtectedAppRoute('/pricing')).toBe(false);
    expect(routeToSidebarSection('/app/workspace')).toBe('workspace-intelligence');
    expect(routeToSidebarSection('/app/creative-studio')).toBe('creative');
    expect(routeToSidebarSection('/unknown')).toBe('chat');
    expect(sidebarSectionToRoute('tasks')).toBe('/app/tasks');
    expect(sidebarSectionToRoute('creative')).toBe('/app/creative-studio');
  });

  it('saves, loads, and clears auth sessions', () => {
    const storage = new MemoryStorage();
    const nextSession = session();

    saveStoredAuthSession(nextSession, storage);
    expect(loadStoredAuthSession(storage)).toEqual(nextSession);

    clearStoredAuthSession(storage);
    expect(storage.getItem(AUTH_SESSION_STORAGE_KEY)).toBeNull();
  });

  it('rejects malformed auth sessions and cleans bad storage', () => {
    const storage = new MemoryStorage();

    expect(isStoredAuthSession({ token: 'x', user: { email: 'user@example.com' } })).toBe(true);
    expect(isStoredAuthSession({ token: 'x', user: {} })).toBe(false);

    storage.setItem(AUTH_SESSION_STORAGE_KEY, '{ nope');
    expect(loadStoredAuthSession(storage)).toBeNull();
    expect(storage.getItem(AUTH_SESSION_STORAGE_KEY)).toBeNull();

    storage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify({ token: 'x', user: {} }));
    expect(loadStoredAuthSession(storage)).toBeNull();
    expect(storage.getItem(AUTH_SESSION_STORAGE_KEY)).toBeNull();
  });
});
