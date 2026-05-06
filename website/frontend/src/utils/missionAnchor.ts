import type { ChatMessage } from '../types';

export const MISSION_ANCHOR_PREFIX = 'Aegis mission anchor:';

const MAX_MISSION_TEXT = 700;
const MAX_WORKSPACE_TEXT = 260;

export function buildAgentRequestHistory(
  history: ChatMessage[],
  currentMessage: string,
  workspaceRoot: string,
  missionAnchor?: ChatMessage | null,
  maxTail = 8
): ChatMessage[] {
  const cleanHistory = sanitizeChatHistory(history).filter((item) => !isMissionAnchorMessage(item));
  const anchor = sanitizeMissionAnchor(missionAnchor) ?? createMissionAnchorMessage(cleanHistory, currentMessage, workspaceRoot);
  const tail = cleanHistory.slice(-Math.max(1, maxTail));
  return anchor ? [anchor, ...tail] : tail;
}

export function createMissionAnchorMessage(
  history: ChatMessage[],
  currentMessage: string,
  workspaceRoot: string
): ChatMessage | null {
  const mission = selectMissionSource(history, currentMessage);
  if (!mission) return null;

  const workspace = compactText(workspaceRoot, MAX_WORKSPACE_TEXT);
  const lines = [
    MISSION_ANCHOR_PREFIX,
    `- Original user mission: ${compactText(mission, MAX_MISSION_TEXT)}`,
    workspace ? `- Active workspace root: ${workspace}` : '',
    '- Continuity rule: For vague follow-ups like continue, build it, fix it, repair it, validate it, or autopilot, preserve the original target path, language/stack, artifact type, and validation intent unless the latest user explicitly switches projects or stacks.'
  ].filter(Boolean);

  return {
    role: 'system',
    content: lines.join('\n')
  };
}

export function sanitizeMissionAnchor(value: unknown): ChatMessage | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as ChatMessage;
  if (candidate.role !== 'system' || typeof candidate.content !== 'string') return null;
  const content = compactAnchorContent(candidate.content, 1400);
  if (!content.startsWith(MISSION_ANCHOR_PREFIX)) return null;
  return {
    role: 'system',
    content
  };
}

export function isMissionAnchorMessage(value: unknown): value is ChatMessage {
  return Boolean(sanitizeMissionAnchor(value));
}

function selectMissionSource(history: ChatMessage[], currentMessage: string): string {
  const userMessages = sanitizeChatHistory(history)
    .filter((item) => item.role === 'user')
    .map((item) => item.content)
    .filter(Boolean);
  const current = currentMessage.trim();
  const candidates = [...userMessages, current].filter(Boolean);
  const firstPathBound = candidates.find((item) => hasExplicitWorkspacePath(item) && !isVagueContinuation(item));
  if (firstPathBound) return firstPathBound;

  const firstProjectMission = candidates.find((item) => hasProjectMissionSignal(item) && !isVagueContinuation(item));
  if (firstProjectMission) return firstProjectMission;

  return current && !isVagueContinuation(current) ? current : '';
}

function sanitizeChatHistory(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isChatMessage)
    .map((item) => ({ role: item.role, content: item.content.trim() }))
    .filter((item) => item.content);
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as ChatMessage;
  return (
    (candidate.role === 'user' || candidate.role === 'assistant' || candidate.role === 'system') &&
    typeof candidate.content === 'string'
  );
}

function hasExplicitWorkspacePath(value: string): boolean {
  return /[a-z]:[\\/][^\n\r]+/i.test(value) || /(?:^|\s)(?:\.{1,2}[\\/]|\/(?:users|home|mnt|workspace|projects)\b)/i.test(value);
}

function hasProjectMissionSignal(value: string): boolean {
  const text = value.toLowerCase();
  return /\b(create|build|make|generate|scaffold|implement|refine|repair|fix|debug|optimize|convert|combine|split|port|test|validate)\b/.test(text)
    || /\b(project|app|application|website|web app|desktop|gui|console|cli|dll|driver|service|api|database|kernel|sln|cmake|react|next|vite|python|typescript|javascript|c\+\+|cpp|c#|dotnet|rust|go|imgui|unity|unreal)\b/.test(text);
}

function isVagueContinuation(value: string): boolean {
  const text = value.toLowerCase().replace(/[^\w+#.\\/: -]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (!text) return true;
  if (hasExplicitWorkspacePath(text)) return false;
  const words = text.split(' ').filter(Boolean);
  if (words.length > 8 && hasProjectMissionSignal(text)) return false;
  return /^(continue|continue please|keep going|go ahead|go ahead and continue|next|yes|yeah|yep|yup|sure|confirmed|confirm|ok|okay|please do|do it|do that|go for it|proceed|build it|run it|fix it|repair it|validate it|test it|finish it|autopilot|work on it|continue working|continue with your suggestions)$/.test(text)
    || /^(yes|yeah|yep|yup|sure|ok|okay)\b.*\b(go ahead|continue|do it|build it|finish it|complete it|make it|proceed)\b.*$/.test(text);
}

function compactText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 3)).trim()}...`;
}

function compactAnchorContent(value: string, maxLength: number): string {
  const normalized = value
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 3)).trim()}...`;
}
