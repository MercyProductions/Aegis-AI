import { describe, expect, it } from 'vitest';
import type { AgentResponse } from '../types';
import { autoMemoryFingerprint, buildAutoMemoryNote } from './autoMemory';

describe('auto memory capture', () => {
  it('captures preference-style conversation notes', () => {
    const note = buildAutoMemoryNote(
      'we should summarize recent chats instead of using the first prompt',
      responseFixture({ reply: 'Recent chats now summarize the latest useful outcome.' }),
      [{ role: 'user', content: 'we should summarize recent chats instead of using the first prompt' }]
    );

    expect(note?.title).toContain('Conversation preference');
    expect(note?.category).toBe('pattern');
    expect(note?.tags).toContain('preference');
    expect(note?.content).toContain('summarize recent chats');
  });

  it('records changed files as related memory for backtracking', () => {
    const note = buildAutoMemoryNote(
      'go ahead',
      responseFixture({
        changes: [
          { action: 'update', path: 'frontend/src/App.tsx', content: 'next', summary: 'Fix light mode' },
          {
            action: 'create',
            path: 'frontend/src/utils/autoMemory.ts',
            content: 'export {}',
            summary: 'Capture useful notes'
          }
        ]
      }),
      [{ role: 'user', content: 'go ahead' }]
    );

    expect(note?.title).toBe('Implemented 2 file changes');
    expect(note?.category).toBe('feature');
    expect(note?.related_files).toEqual(['frontend/src/App.tsx', 'frontend/src/utils/autoMemory.ts']);
    expect(note?.tags).toContain('files-changed');
  });

  it('ignores empty vague follow-ups with no useful outcome', () => {
    const note = buildAutoMemoryNote('yes', responseFixture(), [{ role: 'user', content: 'yes' }]);

    expect(note).toBeNull();
  });

  it('creates stable fingerprints for duplicate avoidance', () => {
    const first = autoMemoryFingerprint(
      'Please make sure the chat auto-scrolls',
      responseFixture({ changes: [{ action: 'update', path: 'src/App.tsx', content: null, summary: '' }] })
    );
    const second = autoMemoryFingerprint(
      '  Please   make sure the chat auto-scrolls  ',
      responseFixture({ changes: [{ action: 'update', path: 'src/App.tsx', content: null, summary: '' }] })
    );

    expect(first).toBe(second);
  });
});

function responseFixture(overrides: Partial<AgentResponse> = {}): AgentResponse {
  return {
    task_id: 'task-1',
    reply: '',
    plan: [],
    changes: [],
    applied: [],
    checkpoint: null,
    warnings: [],
    events: [],
    validation: null,
    validation_profile: null,
    task_plan: null,
    context_budget: null,
    model_attempts: [],
    assistant_name: 'Auralith Prime',
    mode: 'build',
    engine: 'Aegis Core',
    workspace_root: 'C:\\Projects\\Aegis',
    workspace_files: [],
    context_files: [],
    memory_hits: [],
    project_memory_hits: [],
    recent_tasks: [],
    repair_attempts: [],
    completion_quality: null,
    ...overrides
  };
}
