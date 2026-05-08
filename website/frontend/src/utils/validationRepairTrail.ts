import type { AgentResponse, CommandRun, FileChange } from '../types';
import { validationRepairFollowUpPromptText, validationRepairPromptText } from './validationStatus';

export type ValidationRepairTrailStatus = 'sent' | 'passed' | 'failed';
export type ValidationRepairTrailStatusFilter = 'all' | ValidationRepairTrailStatus;
export type ValidationRepairTrailChange = Pick<FileChange, 'action' | 'path'>;

export type ValidationRepairTrailItem = {
  id: string;
  createdAt: string;
  command: string;
  prompt: string;
  followUpPrompt: string;
  sourceSummary: string;
  sourceReason: string;
  sourceExitCode: number | null;
  contextChanges: ValidationRepairTrailChange[];
  contextPaths: string[];
  status: ValidationRepairTrailStatus;
  resultSummary: string;
  resultExitCode: number | null;
  responseTaskId: string;
};

export type ValidationRepairSubmission = {
  prompt: string;
  contextChanges: ValidationRepairTrailChange[];
  contextPaths: string[];
};

export type ValidationRepairSubmissionContext = {
  changes: ValidationRepairTrailChange[];
};

export const validationRepairTrailStatusFilters: Array<{
  value: ValidationRepairTrailStatusFilter;
  label: string;
}> = [
  { value: 'all', label: 'All' },
  { value: 'sent', label: 'Sent' },
  { value: 'failed', label: 'Failed' },
  { value: 'passed', label: 'Passed' }
];

export function validationRepairTrailStatusLabel(status: ValidationRepairTrailStatus): string {
  if (status === 'passed') return 'Passed';
  if (status === 'failed') return 'Failed';
  return 'Sent';
}

export function validationRepairTrailEventStatus(
  status: ValidationRepairTrailStatus
): 'ok' | 'warning' | 'error' {
  if (status === 'passed') return 'ok';
  if (status === 'failed') return 'error';
  return 'warning';
}

export function filterValidationRepairTrail(
  items: ValidationRepairTrailItem[],
  search: string,
  statusFilter: ValidationRepairTrailStatusFilter
): ValidationRepairTrailItem[] {
  const term = search.trim().toLowerCase();

  return items.filter((item) => {
    if (statusFilter !== 'all' && item.status !== statusFilter) return false;
    if (!term) return true;
    return validationRepairTrailSearchText(item).includes(term);
  });
}

export function validationRepairTrailSearchText(item: ValidationRepairTrailItem): string {
  return [
    item.command,
    validationRepairTrailStatusLabel(item.status),
    item.prompt,
    item.followUpPrompt,
    item.sourceSummary,
    item.sourceReason,
    item.resultSummary,
    item.resultExitCode === null ? '' : `exit ${item.resultExitCode}`,
    item.sourceExitCode === null ? '' : `exit ${item.sourceExitCode}`,
    item.responseTaskId,
    ...item.contextPaths,
    ...item.contextChanges.map((change) => `${change.action} ${change.path}`)
  ]
    .filter(Boolean)
    .join('\n')
    .toLowerCase();
}

export function createValidationRepairTrailId(): string {
  return `repair-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function buildValidationRepairSubmission(
  validation: CommandRun | null,
  validationNeedsRepair: boolean,
  activeContext?: ValidationRepairSubmissionContext | null
): ValidationRepairSubmission | null {
  if (!validation || !validationNeedsRepair) return null;

  const contextChanges =
    activeContext?.changes.map((change) => ({
      action: change.action,
      path: change.path
    })) ?? [];
  const context = contextChanges.length ? { changes: contextChanges } : undefined;

  return {
    prompt: validationRepairPromptText(validation, context),
    contextChanges,
    contextPaths: contextChanges.map((change) => change.path)
  };
}

export function createValidationRepairTrailItem(input: {
  id: string;
  createdAt: string;
  validation: CommandRun;
  submission: ValidationRepairSubmission;
}): ValidationRepairTrailItem {
  return {
    id: input.id,
    createdAt: input.createdAt,
    command: input.validation.command || 'validation',
    prompt: input.submission.prompt,
    followUpPrompt: '',
    sourceSummary: input.validation.summary || 'Validation failed.',
    sourceReason: input.validation.reason,
    sourceExitCode: input.validation.exit_code,
    contextChanges: input.submission.contextChanges,
    contextPaths: input.submission.contextPaths,
    status: 'sent',
    resultSummary: 'Repair request sent. Waiting for follow-up validation.',
    resultExitCode: null,
    responseTaskId: ''
  };
}

export function applyValidationRepairResult(
  item: ValidationRepairTrailItem,
  response: Pick<AgentResponse, 'task_id' | 'validation'>
): ValidationRepairTrailItem {
  const validationResult = response.validation;
  if (!validationResult) {
    return {
      ...item,
      resultSummary: 'Repair response finished without follow-up validation.',
      responseTaskId: response.task_id
    };
  }

  const passed = validationResult.allowed && !validationResult.timed_out && validationResult.exit_code === 0;
  const followUpPrompt = passed
    ? ''
    : validationRepairFollowUpPromptText(
        item.prompt,
        validationResult,
        item.contextChanges.length ? { changes: item.contextChanges } : undefined
      );

  return {
    ...item,
    status: passed ? 'passed' : 'failed',
    resultSummary:
      validationResult.summary ||
      validationResult.reason ||
      validationResult.stderr ||
      validationResult.stdout ||
      'Validation result available.',
    resultExitCode: validationResult.exit_code,
    followUpPrompt,
    responseTaskId: response.task_id
  };
}

export function updateValidationRepairTrailResult(
  items: ValidationRepairTrailItem[],
  repairTrailId: string,
  response: Pick<AgentResponse, 'task_id' | 'validation'>
): ValidationRepairTrailItem[] {
  return items.map((item) =>
    item.id === repairTrailId ? applyValidationRepairResult(item, response) : item
  );
}

export function markValidationRepairFollowUpSent(item: ValidationRepairTrailItem): ValidationRepairTrailItem {
  return {
    ...item,
    prompt: item.followUpPrompt,
    followUpPrompt: '',
    status: 'sent',
    resultSummary: 'Follow-up repair request sent. Waiting for validation.',
    resultExitCode: null,
    responseTaskId: ''
  };
}

export function updateValidationRepairTrailFollowUpSent(
  items: ValidationRepairTrailItem[],
  repairTrailId: string
): ValidationRepairTrailItem[] {
  return items.map((item) => (item.id === repairTrailId ? markValidationRepairFollowUpSent(item) : item));
}
