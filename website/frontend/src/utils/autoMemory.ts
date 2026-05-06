import type { AgentResponse, ChatMessage, CreateMemoryNoteRequest, FileChange, MemoryNoteCategory } from '../types';
import { compactText, workspaceLeaf } from './conversations';

const AUTO_MEMORY_TAG = 'auto-captured';
const MAX_AUTO_MEMORY_CONTENT = 1800;

const vagueFollowUpPattern =
  /^(yes|yeah|yep|ok|okay|go ahead|continue|keep going|do it|please do|sounds good|sure|confirmed|that works)$/i;
const userPreferencePattern =
  /\b(remember|note|for future|i prefer|i like|i want|i need|we should|should probably|needs fixed|need fixed|default|always|never|make sure|that way|from now on|idk what|i thought|i swear)\b/i;

export function buildAutoMemoryNote(
  userMessage: string,
  response: AgentResponse,
  history: ChatMessage[]
): CreateMemoryNoteRequest | null {
  const userSummary = summarizeUserMemory(userMessage);
  const hasPreferenceSignal = userPreferencePattern.test(userMessage);
  const hasWorkspaceOutcome = response.changes.length > 0 || Boolean(response.validation);

  if (!hasPreferenceSignal && !hasWorkspaceOutcome) return null;
  if (!hasPreferenceSignal && isVagueFollowUp(userMessage) && response.changes.length === 0) return null;

  const category = memoryCategoryFor(response, hasPreferenceSignal);
  const relatedFiles = unique(response.changes.map((change) => change.path).filter(Boolean));
  const title = hasPreferenceSignal
    ? `Conversation preference: ${compactText(userSummary, 72)}`
    : `Implemented ${response.changes.length} file ${response.changes.length === 1 ? 'change' : 'changes'}`;
  const content = compactText(
    [
      'Auto-captured from chat so this workspace can be backtracked later.',
      '',
      `Workspace: ${workspaceLeaf(response.workspace_root) || response.workspace_root || 'Current workspace'}`,
      response.task_id ? `Task: ${response.task_id}` : '',
      '',
      'User signal:',
      userSummary,
      '',
      response.reply.trim() ? `Assistant outcome:\n${compactText(response.reply.trim(), 600)}` : '',
      response.changes.length ? `Files changed:\n${formatFileChanges(response.changes)}` : '',
      response.validation
        ? [
            'Validation:',
            `- ${response.validation.exit_code === 0 ? 'Passed' : 'Needs attention'}: ${response.validation.summary}`,
            response.validation.command ? `- Command: ${response.validation.command}` : ''
          ]
            .filter(Boolean)
            .join('\n')
        : '',
      latestConversationContext(history)
    ]
      .filter(Boolean)
      .join('\n\n'),
    MAX_AUTO_MEMORY_CONTENT
  );

  return {
    title: compactText(title, 96),
    content,
    category,
    tags: unique([
      AUTO_MEMORY_TAG,
      'conversation',
      hasPreferenceSignal ? 'preference' : '',
      response.changes.length ? 'files-changed' : '',
      response.validation ? 'validation' : '',
      response.mode ? `mode:${response.mode}` : ''
    ]),
    related_files: relatedFiles,
    confidence: hasPreferenceSignal ? 0.72 : 0.62,
    pinned: false
  };
}

export function autoMemoryFingerprint(userMessage: string, response: AgentResponse): string {
  const changedFiles = response.changes.map((change) => `${change.action}:${change.path}`).sort().join('|');
  const summary = `${summarizeUserMemory(userMessage)}|${changedFiles}|${response.validation?.summary ?? ''}`;
  return compactText(summary.toLowerCase().replace(/\s+/g, ' ').trim(), 360);
}

function summarizeUserMemory(userMessage: string): string {
  const normalized = userMessage.replace(/\s+/g, ' ').trim();
  if (!normalized) return 'No user note provided.';
  return compactText(normalized, 420);
}

function latestConversationContext(history: ChatMessage[]): string {
  const latestUser = [...history].reverse().find((item) => item.role === 'user')?.content.trim();
  if (!latestUser) return '';
  return `Latest chat context:\n${compactText(latestUser, 360)}`;
}

function formatFileChanges(changes: FileChange[]): string {
  return changes
    .slice(0, 12)
    .map((change) => `- ${change.path} (${change.action})${change.summary ? `: ${change.summary}` : ''}`)
    .join('\n');
}

function memoryCategoryFor(response: AgentResponse, hasPreferenceSignal: boolean): MemoryNoteCategory {
  if (response.validation && response.validation.exit_code !== 0) return 'bug';
  if (hasPreferenceSignal) return 'pattern';
  if (response.changes.length > 0) return 'feature';
  return 'insight';
}

function isVagueFollowUp(value: string): boolean {
  return vagueFollowUpPattern.test(value.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim());
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}
