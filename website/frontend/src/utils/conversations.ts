import type { ChatMessage } from '../types';

export const CONVERSATION_STORAGE_KEY = 'aegis.web.conversations.v1';

export type ChatThreadPreview = {
  id: string;
  title: string;
  preview: string;
  count: number;
};

export type SavedConversation = ChatThreadPreview & {
  updatedAt: string;
  workspaceRoot: string;
  messages: ChatMessage[];
};

type ConversationStorage = Pick<Storage, 'getItem' | 'setItem'> & Partial<Pick<Storage, 'removeItem'>>;

export function createConversationId(): string {
  return `thread-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function buildConversationPreview(
  id: string,
  messages: ChatMessage[],
  workspaceRoot: string
): SavedConversation | null {
  const cleanedMessages = messages
    .filter(isChatMessage)
    .map(sanitizeSavedChatMessage)
    .filter((item) => item.content);

  if (!cleanedMessages.length) return null;

  const titleSource = summarizeConversationTitle(cleanedMessages, workspaceRoot);
  const previewSource = summarizeConversationPreview(cleanedMessages);

  return {
    id,
    title: compactText(titleSource, 54),
    preview: compactText(previewSource, 140),
    count: cleanedMessages.length,
    updatedAt: new Date().toISOString(),
    workspaceRoot,
    messages: cleanedMessages
  };
}

export function summarizeConversationTitle(messages: ChatMessage[], workspaceRoot = ''): string {
  const cleanedMessages = messages
    .filter(isChatMessage)
    .map((item) => ({ role: item.role, content: item.content.trim() }))
    .filter((item) => item.content);
  const userMessages = cleanedMessages.filter((item) => item.role === 'user').map((item) => item.content);
  const assistantMessages = cleanedMessages.filter((item) => item.role === 'assistant').map((item) => item.content);
  const latestAssistant = assistantMessages.at(-1) ?? '';
  const fileSummary = summarizeFileChanges(latestAssistant);

  if (fileSummary) return fileSummary;

  const assistantSummary = firstUsefulAssistantLine(latestAssistant);
  if (assistantSummary && (userMessages.length > 0 || !isLowSignalAssistantLine(assistantSummary))) {
    return assistantSummary;
  }

  const meaningfulUser = [...userMessages].reverse().find((content) => !isVagueFollowUp(content));
  if (meaningfulUser) return meaningfulUser;

  const leaf = workspaceLeaf(workspaceRoot);
  if (leaf) return leaf;

  return assistantSummary || cleanedMessages.at(-1)?.content || 'Auralith OS session';
}

export function summarizeConversationPreview(messages: ChatMessage[]): string {
  const cleanedMessages = messages
    .filter(isChatMessage)
    .map((item) => ({ role: item.role, content: item.content.trim() }))
    .filter((item) => item.content);
  const latestAssistant = [...cleanedMessages].reverse().find((item) => item.role === 'assistant')?.content ?? '';
  const latestUser = [...cleanedMessages].reverse().find((item) => item.role === 'user')?.content ?? '';
  const assistantPreview = firstUsefulAssistantLine(latestAssistant);

  return assistantPreview || latestUser || cleanedMessages.at(-1)?.content || 'Conversation saved.';
}

export function loadSavedConversations(storage = resolveConversationStorage()): SavedConversation[] {
  if (!storage) return [];

  try {
    const raw = storage.getItem(CONVERSATION_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      clearSavedConversationStorage(storage);
      return [];
    }

    const conversations = parsed.filter(isSavedConversation).slice(0, 50);
    if (conversations.length !== parsed.length || parsed.length > 50) {
      saveSavedConversations(conversations, storage);
    }

    return conversations;
  } catch {
    clearSavedConversationStorage(storage);
    return [];
  }
}

export function saveSavedConversations(
  conversations: SavedConversation[],
  storage = resolveConversationStorage()
) {
  if (!storage) return;

  try {
    storage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(conversations.slice(0, 50)));
  } catch {
    // Conversation history is a convenience feature; keep the UI usable if storage is unavailable.
  }
}

export function upsertSavedConversation(
  conversations: SavedConversation[],
  conversation: SavedConversation
): SavedConversation[] {
  const next = [conversation, ...conversations.filter((item) => item.id !== conversation.id)];
  return next
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 50);
}

export function deleteSavedConversation(conversations: SavedConversation[], id: string): SavedConversation[] {
  return conversations.filter((conversation) => conversation.id !== id);
}

export function buildConversationMarkdown(
  title: string,
  messages: ChatMessage[],
  workspaceRoot: string,
  exportedAt = new Date().toISOString()
): string {
  const safeTitle = compactText(title || 'Auralith OS session', 120) || 'Auralith OS session';
  const lines = [
    `# ${safeTitle}`,
    '',
    `- Exported: ${exportedAt}`,
    `- Workspace: ${workspaceRoot || 'Not set'}`,
    `- Messages: ${messages.filter(isChatMessage).length}`,
    ''
  ];

  for (const message of messages.filter(isChatMessage)) {
    const content = message.content.trim();
    if (!content) continue;
    lines.push(`## ${roleLabel(message.role)}`, '', content, '');
  }

  return `${lines.join('\n').trimEnd()}\n`;
}

export function conversationMarkdownFilename(title: string, exportedAt = new Date().toISOString()): string {
  const datePart = exportedAt.slice(0, 10) || 'session';
  const normalizedTitle = compactText(title || 'auralith-session', 80)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `${datePart}-${normalizedTitle || 'auralith-session'}.md`;
}

export function isSavedConversation(value: unknown): value is SavedConversation {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as SavedConversation;
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.title === 'string' &&
    typeof candidate.preview === 'string' &&
    typeof candidate.updatedAt === 'string' &&
    typeof candidate.workspaceRoot === 'string' &&
    Array.isArray(candidate.messages) &&
    candidate.messages.every(isChatMessage)
  );
}

export function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as ChatMessage;
  return (
    (candidate.role === 'user' || candidate.role === 'assistant' || candidate.role === 'system') &&
    typeof candidate.content === 'string'
  );
}

function sanitizeSavedChatMessage(item: ChatMessage): ChatMessage {
  const metadata = sanitizeChatMessageMetadata(item.metadata);
  return {
    role: item.role,
    content: item.content.trim(),
    ...(metadata ? { metadata } : {})
  };
}

function sanitizeChatMessageMetadata(metadata: ChatMessage['metadata']): ChatMessage['metadata'] | undefined {
  if (!metadata || typeof metadata !== 'object') return undefined;
  const generatedChanges = Array.isArray(metadata.generatedChanges)
    ? metadata.generatedChanges
        .filter((change) =>
          Boolean(
            change &&
              ['create', 'update', 'append', 'delete'].includes(change.action) &&
              typeof change.path === 'string'
          )
        )
        .map((change) => ({
          action: change.action,
          path: change.path,
          content: typeof change.content === 'string' || change.content === null ? change.content : null,
          summary: typeof change.summary === 'string' ? change.summary : ''
        }))
        .slice(0, 80)
    : [];

  const next = {
    generatedChanges,
    applied: Array.isArray(metadata.applied) ? metadata.applied.filter((item) => typeof item === 'string') : [],
    warnings: Array.isArray(metadata.warnings) ? metadata.warnings.filter((item) => typeof item === 'string') : [],
    checkpoint:
      typeof metadata.checkpoint === 'string' || metadata.checkpoint === null ? metadata.checkpoint : undefined,
    workspaceRoot: typeof metadata.workspaceRoot === 'string' ? metadata.workspaceRoot : undefined,
    taskId: typeof metadata.taskId === 'string' ? metadata.taskId : undefined
  };

  return next.generatedChanges.length ||
    next.applied.length ||
    next.warnings.length ||
    next.checkpoint ||
    next.workspaceRoot ||
    next.taskId
    ? next
    : undefined;
}

export function compactText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 3)).trim()}...`;
}

export function workspaceLeaf(value: string): string {
  const trimmed = value.trim().replace(/[\\/]+$/, '');
  if (!trimmed) return '';
  const parts = trimmed.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? '';
}

function roleLabel(role: ChatMessage['role']): string {
  if (role === 'user') return 'User';
  if (role === 'assistant') return 'Auralith Prime';
  return 'System';
}

function summarizeFileChanges(content: string): string {
  const lines = normalizedContentLines(content);
  const sectionIndex = lines.findIndex((line) =>
    /^(pending generated file changes|generated file changes|generated files|applied changes):/i.test(line)
  );
  if (sectionIndex < 0) return '';

  const files: string[] = [];
  for (const line of lines.slice(sectionIndex + 1)) {
    if (/^[A-Z][A-Za-z ]+:/.test(line) && !line.startsWith('- ')) break;
    const match = line.match(/^-\s+(.+?)(?:\s+\((create|update|append|delete|applied|pending)[^)]+\))?$/i);
    if (!match) continue;
    const candidate = match[1].trim();
    if (!candidate || candidate.startsWith('route:') || candidate.startsWith('scale:')) continue;
    files.push(candidate);
  }

  if (files.length === 1) return `Updated ${shortPath(files[0])}`;
  if (files.length === 2) return `Updated ${shortPath(files[0])} and ${shortPath(files[1])}`;
  if (files.length > 2) return `Updated ${files.length} files: ${shortPath(files[0])}`;

  return '';
}

function firstUsefulAssistantLine(content: string): string {
  const lines = normalizedContentLines(content);
  const stopIndex = lines.findIndex((line) =>
    /^(planning intelligence|completion quality|generated files|generated file changes|pending generated file changes|applied changes):/i.test(
      line
    )
  );
  const usefulLines = (stopIndex >= 0 ? lines.slice(0, stopIndex) : lines)
    .filter((line) => !/^note: the live preview/i.test(line))
    .filter((line) => !/^(route|scale|estimated slices|pass budget hint):/i.test(line.replace(/^-\s*/, '')))
    .filter((line) => !isLowSignalAssistantLine(line));

  return usefulLines[0] ?? '';
}

function normalizedContentLines(content: string): string[] {
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function shortPath(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\s+\((create|update|append|delete|applied|pending).*$/i, '');
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length <= 2) return parts.join('/');
  return parts.slice(-2).join('/');
}

function isLowSignalAssistantLine(value: string): boolean {
  const normalized = value.toLowerCase().replace(/\s+/g, ' ').trim();
  return (
    normalized === 'ready.' ||
    normalized === 'done.' ||
    normalized === 'completed.' ||
    normalized === 'i will create the requested files.' ||
    normalized === 'i will make those changes.'
  );
}

function isVagueFollowUp(value: string): boolean {
  const normalized = value
    .toLowerCase()
    .replace(/[^a-z0-9\s']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return /^(yes|yeah|yep|ok|okay|go ahead|continue|keep going|do it|please do|sounds good|sure|confirm|confirmed|that works|yes im aware go ahead)$/.test(
    normalized
  );
}

function resolveConversationStorage(): ConversationStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function clearSavedConversationStorage(storage: ConversationStorage) {
  try {
    if (storage.removeItem) {
      try {
        storage.removeItem(CONVERSATION_STORAGE_KEY);
        return;
      } catch {
        storage.setItem(CONVERSATION_STORAGE_KEY, '[]');
        return;
      }
    }

    storage.setItem(CONVERSATION_STORAGE_KEY, '[]');
  } catch {
    // Broken persisted history should never prevent the app shell from opening.
  }
}
