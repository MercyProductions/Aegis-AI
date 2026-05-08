import { describe, expect, it } from 'vitest';
import type { SavedConversation } from './conversations';
import {
  buildProjectRootSummaries,
  filterProjectRootSummaries,
  latestProjectThread
} from './projectRoots';

describe('project root summaries', () => {
  it('selects the newest saved thread as the latest project thread', () => {
    const older = savedThread({
      id: 'older',
      title: 'Older task',
      updatedAt: '2026-05-01T10:00:00.000Z'
    });
    const newer = savedThread({
      id: 'newer',
      title: 'Newer task',
      updatedAt: '2026-05-02T10:00:00.000Z'
    });

    expect(latestProjectThread(null, older)).toBe(older);
    expect(latestProjectThread(older, null)).toBe(older);
    expect(latestProjectThread(older, newer)).toBe(newer);
    expect(latestProjectThread(newer, older)).toBe(newer);
  });

  it('groups saved threads by normalized workspace root and keeps the active root first', () => {
    const threads = [
      savedThread({
        id: 'thread-1',
        title: 'First API pass',
        workspaceRoot: 'C:/Projects/Auralith/',
        updatedAt: '2026-05-01T10:00:00.000Z'
      }),
      savedThread({
        id: 'thread-2',
        title: 'Latest API pass',
        workspaceRoot: 'c:/projects/auralith',
        updatedAt: '2026-05-03T10:00:00.000Z'
      }),
      savedThread({
        id: 'thread-3',
        title: 'Other workspace',
        workspaceRoot: 'D:/Sandbox',
        updatedAt: '2026-05-04T10:00:00.000Z'
      })
    ];

    const summaries = buildProjectRootSummaries(threads, 'C:/Projects/Auralith');

    expect(summaries).toHaveLength(2);
    expect(summaries[0]).toMatchObject({
      root: 'C:/Projects/Auralith',
      title: 'Latest API pass',
      count: 2,
      active: true,
      latestUpdatedAt: '2026-05-03T10:00:00.000Z'
    });
    expect(summaries[0].latestThread?.id).toBe('thread-2');
    expect(summaries[0].threads.map((thread) => thread.id)).toEqual(['thread-1', 'thread-2']);
    expect(summaries[1]).toMatchObject({
      root: 'D:/Sandbox',
      count: 1,
      active: false
    });
  });

  it('uses recency ordering when no summary is active', () => {
    const summaries = buildProjectRootSummaries(
      [
        savedThread({
          id: 'older',
          title: 'Older workspace',
          workspaceRoot: 'C:/Older',
          updatedAt: '2026-05-01T10:00:00.000Z'
        }),
        savedThread({
          id: 'newer',
          title: 'Newer workspace',
          workspaceRoot: 'C:/Newer',
          updatedAt: '2026-05-02T10:00:00.000Z'
        })
      ],
      ''
    );

    expect(summaries.map((item) => item.root)).toEqual(['C:/Newer', 'C:/Older']);
  });

  it('filters projects by title, root, latest preview, and thread previews', () => {
    const summaries = buildProjectRootSummaries(
      [
        savedThread({
          id: 'api',
          title: 'API repair',
          preview: 'fixed websocket reconnect handling',
          workspaceRoot: 'C:/Auralith',
          updatedAt: '2026-05-02T10:00:00.000Z'
        }),
        savedThread({
          id: 'ui',
          title: 'Interface polish',
          preview: 'premium spacing pass',
          workspaceRoot: 'C:/Auralith',
          updatedAt: '2026-05-01T10:00:00.000Z'
        }),
        savedThread({
          id: 'other',
          title: 'Other project',
          preview: 'unrelated work',
          workspaceRoot: 'D:/Other',
          updatedAt: '2026-05-03T10:00:00.000Z'
        })
      ],
      ''
    );

    expect(filterProjectRootSummaries(summaries, 'websocket')).toHaveLength(1);
    expect(filterProjectRootSummaries(summaries, 'premium spacing')).toHaveLength(1);
    expect(filterProjectRootSummaries(summaries, 'D:/Other')).toHaveLength(1);
    expect(filterProjectRootSummaries(summaries, 'missing')).toEqual([]);
  });
});

function savedThread(overrides: Partial<SavedConversation> = {}): SavedConversation {
  return {
    id: overrides.id ?? 'thread',
    title: overrides.title ?? 'Saved thread',
    preview: overrides.preview ?? 'Thread preview',
    count: overrides.count ?? 2,
    updatedAt: overrides.updatedAt ?? '2026-05-01T10:00:00.000Z',
    workspaceRoot: overrides.workspaceRoot ?? 'C:/Workspace',
    messages: overrides.messages ?? [],
  };
}
