import type { SavedConversation } from './conversations';
import { normalizeProjectRootKey } from './appStorage';

export type ProjectRootSummary = {
  root: string;
  title: string;
  count: number;
  active: boolean;
  latestThread: SavedConversation | null;
  latestUpdatedAt: string;
  threads: SavedConversation[];
};

export function latestProjectThread(
  current: SavedConversation | null,
  candidate: SavedConversation | null
): SavedConversation | null {
  if (!candidate) return current;
  if (!current) return candidate;
  return new Date(candidate.updatedAt).getTime() > new Date(current.updatedAt).getTime() ? candidate : current;
}

export function buildProjectRootSummaries(
  savedThreads: SavedConversation[],
  workspaceRoot: string
): ProjectRootSummary[] {
  const roots = new Map<string, ProjectRootSummary>();
  const activeRootKey = normalizeProjectRootKey(workspaceRoot);

  const addRoot = (root: string, title: string, thread: SavedConversation | null = null) => {
    const trimmed = root.trim();
    if (!trimmed) return;
    const key = normalizeProjectRootKey(trimmed);
    const existing = roots.get(key);
    const threads = thread ? [...(existing?.threads ?? []), thread] : existing?.threads ?? [];
    const latestThread = latestProjectThread(existing?.latestThread ?? null, thread);
    roots.set(key, {
      root: existing?.root || trimmed,
      title: latestThread?.title || existing?.title || title,
      count: (existing?.count ?? 0) + (thread ? 1 : 0),
      active: key === activeRootKey,
      latestThread,
      latestUpdatedAt: latestThread?.updatedAt || existing?.latestUpdatedAt || '',
      threads
    });
  };

  addRoot(workspaceRoot, 'Current workspace');
  for (const thread of savedThreads) {
    addRoot(thread.workspaceRoot, thread.title || 'Saved session workspace', thread);
  }
  return Array.from(roots.values()).sort((left, right) => {
    if (left.active !== right.active) return left.active ? -1 : 1;
    const leftTime = new Date(left.latestUpdatedAt || 0).getTime();
    const rightTime = new Date(right.latestUpdatedAt || 0).getTime();
    if (leftTime !== rightTime) return rightTime - leftTime;
    return left.title.localeCompare(right.title);
  });
}

export function filterProjectRootSummaries(
  projectRoots: ProjectRootSummary[],
  projectSearch: string
): ProjectRootSummary[] {
  const term = projectSearch.trim().toLowerCase();
  if (!term) return projectRoots;
  return projectRoots.filter((project) =>
    [
      project.title,
      project.root,
      project.latestThread?.title ?? '',
      project.latestThread?.preview ?? '',
      ...project.threads.flatMap((thread) => [thread.title, thread.preview])
    ]
      .join(' ')
      .toLowerCase()
      .includes(term)
  );
}
