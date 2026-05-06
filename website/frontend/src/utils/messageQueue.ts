import type { ChatMessage, Mode } from '../types';
import type { ConnectionState } from './connection';
import { normalizeContextPaths } from './contextPins';
import { sanitizeMissionAnchor } from './missionAnchor';

export const QUEUED_MESSAGES_STORAGE_KEY = 'aegis.web.queuedMessages.v1';
export const MAX_QUEUED_MESSAGES = 10;

export type QueuedMessage = {
  id: string;
  threadId: string;
  content: string;
  createdAt: string;
  workspaceRoot: string;
  mode: Mode;
  applyChanges: boolean;
  runValidation: boolean;
  contextPaths: string[];
  historyRecorded: boolean;
  missionAnchor: ChatMessage | null;
  history: ChatMessage[];
};

export type QueuedMessageDraft = Partial<QueuedMessage> & {
  content?: string;
};

type QueueStorage = Pick<Storage, 'getItem' | 'setItem'>;

export function createQueuedMessage(
  content: string,
  options: QueuedMessageDraft = {}
): QueuedMessage | null {
  const normalizedContent = (options.content ?? content).trim();
  if (!normalizedContent) return null;

  return {
    id: options.id ?? createQueueId(),
    threadId: options.threadId ?? '',
    content: normalizedContent,
    createdAt: options.createdAt ?? new Date().toISOString(),
    workspaceRoot: options.workspaceRoot ?? '',
    mode: options.mode ?? 'build',
    applyChanges: options.applyChanges ?? false,
    runValidation: options.runValidation ?? false,
    contextPaths: normalizeContextPaths(options.contextPaths ?? []),
    historyRecorded: options.historyRecorded ?? false,
    missionAnchor: sanitizeMissionAnchor(options.missionAnchor),
    history: sanitizeHistory(options.history)
  };
}

export function appendQueuedMessage(
  current: QueuedMessage[],
  message: QueuedMessage,
  maxQueuedMessages = MAX_QUEUED_MESSAGES
): QueuedMessage[] {
  const next = [...current.filter((item) => item.id !== message.id), message];
  return next.slice(-Math.max(1, maxQueuedMessages));
}

export function removeQueuedMessage(current: QueuedMessage[], id: string): QueuedMessage[] {
  return current.filter((item) => item.id !== id);
}

export function moveQueuedMessage(current: QueuedMessage[], id: string, direction: 'up' | 'down'): QueuedMessage[] {
  const index = current.findIndex((item) => item.id === id);
  if (index < 0) return current;

  const targetIndex = direction === 'up' ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= current.length) return current;

  const next = [...current];
  [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
  return next;
}

export function clearQueuedMessages(): QueuedMessage[] {
  return [];
}

export function shouldQueueOutboundMessage(
  loading: boolean,
  connectionState: ConnectionState,
  queuedReplay: QueuedMessage | null | undefined
): boolean {
  return loading || (!queuedReplay && connectionState !== 'connected');
}

export function loadQueuedMessages(storage = resolveQueueStorage()): QueuedMessage[] {
  if (!storage) return [];

  try {
    const raw = storage.getItem(QUEUED_MESSAGES_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isQueuedMessage).map(normalizeQueuedMessage).slice(-MAX_QUEUED_MESSAGES);
  } catch {
    return [];
  }
}

export function saveQueuedMessages(messages: QueuedMessage[], storage = resolveQueueStorage()) {
  if (!storage) return;

  try {
    storage.setItem(QUEUED_MESSAGES_STORAGE_KEY, JSON.stringify(messages.slice(-MAX_QUEUED_MESSAGES)));
  } catch {
    // Queued prompts are best-effort; keep the composer usable if storage is unavailable.
  }
}

export function isQueuedMessage(value: unknown): value is QueuedMessage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as QueuedMessage;
  return (
    typeof candidate.id === 'string' &&
    (typeof candidate.threadId === 'string' || candidate.threadId === undefined) &&
    typeof candidate.content === 'string' &&
    candidate.content.trim().length > 0 &&
    typeof candidate.createdAt === 'string' &&
    typeof candidate.workspaceRoot === 'string' &&
    isMode(candidate.mode) &&
    typeof candidate.applyChanges === 'boolean' &&
    typeof candidate.runValidation === 'boolean' &&
    (Array.isArray(candidate.contextPaths) ? candidate.contextPaths.every((item) => typeof item === 'string') : candidate.contextPaths === undefined) &&
    typeof candidate.historyRecorded === 'boolean' &&
    (sanitizeMissionAnchor(candidate.missionAnchor) !== null || candidate.missionAnchor === null || candidate.missionAnchor === undefined) &&
    (Array.isArray(candidate.history) ? candidate.history.every(isQueueChatMessage) : candidate.history === undefined)
  );
}

function sanitizeHistory(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isQueueChatMessage)
    .map((item) => ({ role: item.role, content: item.content.trim() }))
    .filter((item) => item.content)
    .slice(-16);
}

function isQueueChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as ChatMessage;
  return (
    (candidate.role === 'user' || candidate.role === 'assistant' || candidate.role === 'system') &&
    typeof candidate.content === 'string'
  );
}

function isMode(value: unknown): value is Mode {
  return value === 'build' || value === 'develop' || value === 'review' || value === 'chat';
}

function normalizeQueuedMessage(message: QueuedMessage): QueuedMessage {
  return {
    ...message,
    threadId: message.threadId ?? '',
    contextPaths: normalizeContextPaths(message.contextPaths ?? []),
    missionAnchor: sanitizeMissionAnchor(message.missionAnchor),
    history: sanitizeHistory(message.history)
  };
}

function createQueueId(): string {
  return `queued-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function resolveQueueStorage(): QueueStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}
