import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '../types';
import {
  CONVERSATION_STORAGE_KEY,
  buildConversationPreview,
  buildConversationMarkdown,
  compactText,
  conversationMarkdownFilename,
  deleteSavedConversation,
  loadSavedConversations,
  saveSavedConversations,
  summarizeConversationTitle,
  upsertSavedConversation,
  workspaceLeaf
} from './conversations';

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

describe('conversation utilities', () => {
  it('builds one conversation preview from multiple messages', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: '  Build a full C++ app at C:\\Projects\\Demo  ' },
      { role: 'assistant', content: 'Generated CMakeLists.txt and src/main.cpp' }
    ];

    const preview = buildConversationPreview('thread-1', messages, 'C:\\Projects\\Demo');

    expect(preview?.id).toBe('thread-1');
    expect(preview?.count).toBe(2);
    expect(preview?.title).toBe('Generated CMakeLists.txt and src/main.cpp');
    expect(preview?.preview).toBe('Generated CMakeLists.txt and src/main.cpp');
    expect(preview?.messages[0].content).toBe('Build a full C++ app at C:\\Projects\\Demo');
  });

  it('ignores empty or malformed messages when building previews', () => {
    const preview = buildConversationPreview(
      'thread-2',
      [
        { role: 'system', content: '   ' },
        { role: 'assistant', content: 'Ready.' },
        { role: 'user', content: '' }
      ],
      'C:\\Projects\\Aegis'
    );

    expect(preview?.count).toBe(1);
    expect(preview?.title).toBe('Aegis');
  });

  it('summarizes generated file sections instead of vague follow-ups', () => {
    const title = summarizeConversationTitle(
      [
        { role: 'user', content: 'build me a typescript obfuscator here C:\\Tools\\TypeScriptObfuscator' },
        { role: 'assistant', content: 'I will create the TypeScript Obfuscator as requested.' },
        { role: 'user', content: 'yes go ahead' },
        {
          role: 'assistant',
          content: [
            'Generated file changes:',
            '- src/obfuscate.ts (create, applied)',
            '- package.json (update, applied)',
            '',
            'Planning intelligence:',
            '- route: auto'
          ].join('\n')
        }
      ],
      'C:\\Tools\\TypeScriptObfuscator'
    );

    expect(title).toBe('Updated src/obfuscate.ts and package.json');
  });

  it('preserves assistant file-change metadata in saved conversations', () => {
    const preview = buildConversationPreview(
      'thread-metadata',
      [
        { role: 'user', content: 'update the app' },
        {
          role: 'assistant',
          content: 'Generated file changes:\n- src/App.tsx (update, applied)',
          metadata: {
            generatedChanges: [
              { action: 'update', path: 'src/App.tsx', content: 'next', summary: 'Update app shell' }
            ],
            applied: ['update: src/App.tsx'],
            warnings: [],
            checkpoint: 'checkpoint-1',
            workspaceRoot: 'C:\\Projects\\Aegis',
            taskId: 'task-1'
          }
        }
      ],
      'C:\\Projects\\Aegis'
    );

    expect(preview?.messages[1].metadata).toMatchObject({
      generatedChanges: [{ action: 'update', path: 'src/App.tsx', content: 'next' }],
      applied: ['update: src/App.tsx'],
      checkpoint: 'checkpoint-1',
      taskId: 'task-1'
    });
  });

  it('uses the latest useful assistant result as the preview summary', () => {
    const preview = buildConversationPreview(
      'thread-summary',
      [
        { role: 'user', content: 'first prompt should not own this forever' },
        { role: 'assistant', content: 'Ready.' },
        { role: 'user', content: 'go ahead' },
        {
          role: 'assistant',
          content: [
            'Light mode now uses readable neutral surfaces and red accents.',
            '',
            'Completion quality: ready (100%)'
          ].join('\n')
        }
      ],
      'C:\\Projects\\Aegis'
    );

    expect(preview?.title).toBe('Light mode now uses readable neutral surfaces and r...');
    expect(preview?.preview).toBe('Light mode now uses readable neutral surfaces and red accents.');
  });

  it('upserts conversations by id and keeps newest first', () => {
    const older = {
      id: 'a',
      title: 'Older',
      preview: 'older',
      count: 1,
      updatedAt: '2026-05-01T00:00:00.000Z',
      workspaceRoot: 'C:\\Old',
      messages: [{ role: 'user', content: 'old' }] as ChatMessage[]
    };
    const newer = {
      ...older,
      id: 'b',
      title: 'Newer',
      updatedAt: '2026-05-02T00:00:00.000Z',
      messages: [{ role: 'user', content: 'new' }] as ChatMessage[]
    };
    const replacement = {
      ...older,
      title: 'Older updated',
      updatedAt: '2026-05-03T00:00:00.000Z',
      messages: [{ role: 'user', content: 'updated' }] as ChatMessage[]
    };

    const result = upsertSavedConversation([older, newer], replacement);

    expect(result.map((item) => item.id)).toEqual(['a', 'b']);
    expect(result[0].title).toBe('Older updated');
    expect(result[0].messages[0].content).toBe('updated');
  });

  it('deletes a saved conversation by id without mutating the remaining chats', () => {
    const conversations = [
      {
        id: 'delete-me',
        title: 'Delete me',
        preview: 'old',
        count: 1,
        updatedAt: '2026-05-01T00:00:00.000Z',
        workspaceRoot: 'C:\\Old',
        messages: [{ role: 'user', content: 'old' }] as ChatMessage[]
      },
      {
        id: 'keep-me',
        title: 'Keep me',
        preview: 'new',
        count: 1,
        updatedAt: '2026-05-02T00:00:00.000Z',
        workspaceRoot: 'C:\\New',
        messages: [{ role: 'user', content: 'new' }] as ChatMessage[]
      }
    ];

    const result = deleteSavedConversation(conversations, 'delete-me');

    expect(result.map((item) => item.id)).toEqual(['keep-me']);
    expect(conversations).toHaveLength(2);
  });

  it('loads only valid saved conversations and tolerates malformed storage', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      CONVERSATION_STORAGE_KEY,
      JSON.stringify([
        {
          id: 'valid',
          title: 'Valid',
          preview: 'preview',
          count: 1,
          updatedAt: '2026-05-02T00:00:00.000Z',
          workspaceRoot: 'C:\\Valid',
          messages: [{ role: 'user', content: 'hello' }]
        },
        { id: 'invalid', messages: [{ role: 'bad', content: 123 }] }
      ])
    );

    expect(loadSavedConversations(storage)).toHaveLength(1);

    storage.setItem(CONVERSATION_STORAGE_KEY, '{ nope');
    expect(loadSavedConversations(storage)).toEqual([]);
  });

  it('saves at most 50 conversations', () => {
    const storage = new MemoryStorage();
    const conversations = Array.from({ length: 55 }, (_, index) => ({
      id: `thread-${index}`,
      title: `Thread ${index}`,
      preview: 'preview',
      count: 1,
      updatedAt: '2026-05-02T00:00:00.000Z',
      workspaceRoot: 'C:\\Aegis',
      messages: [{ role: 'user', content: `message ${index}` }] as ChatMessage[]
    }));

    saveSavedConversations(conversations, storage);

    const raw = storage.getItem(CONVERSATION_STORAGE_KEY);
    expect(raw ? JSON.parse(raw) : []).toHaveLength(50);
  });

  it('normalizes compact text and workspace leaf labels', () => {
    expect(compactText('  hello\n\nworld  ', 50)).toBe('hello world');
    expect(compactText('abcdefghijklmnopqrstuvwxyz', 10)).toBe('abcdefg...');
    expect(workspaceLeaf('C:\\Users\\gabri\\Desktop\\Aegis\\')).toBe('Aegis');
  });

  it('builds a portable Markdown transcript for saved sessions', () => {
    const markdown = buildConversationMarkdown(
      'Fix chatbot streaming',
      [
        { role: 'user', content: '  Please fix streaming  ' },
        { role: 'assistant', content: 'Streaming is now more robust.' },
        { role: 'system', content: 'Mission anchor' }
      ],
      'C:\\Projects\\Aegis',
      '2026-05-05T10:30:00.000Z'
    );

    expect(markdown).toContain('# Fix chatbot streaming');
    expect(markdown).toContain('- Exported: 2026-05-05T10:30:00.000Z');
    expect(markdown).toContain('- Workspace: C:\\Projects\\Aegis');
    expect(markdown).toContain('## User\n\nPlease fix streaming');
    expect(markdown).toContain('## Auralith Prime\n\nStreaming is now more robust.');
    expect(markdown).toContain('## System\n\nMission anchor');
  });

  it('creates safe Markdown transcript filenames', () => {
    expect(conversationMarkdownFilename('Fix chatbot: streaming / queue?', '2026-05-05T10:30:00.000Z')).toBe(
      '2026-05-05-fix-chatbot-streaming-queue.md'
    );
  });
});
