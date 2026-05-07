import type { FileChange } from '../types';

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
