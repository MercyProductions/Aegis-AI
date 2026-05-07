import type { ModeOption, ToolEvent } from '../types';

export const starterPrompts = [
  'Help me debug this error',
  'Write a function to parse JSON safely in TypeScript',
  'Refactor this code to be more efficient',
  'Explain how this code works',
  'Create a batch script that prints hello world to the console',
  'Create a project from scratch in this directory'
];

export const thinkingStates = [
  'Analyzing your request',
  'Generating a solution',
  'Preparing file changes',
  'Checking the workspace',
  'Finalizing the response'
];

export const fallbackModeOptions: ModeOption[] = [
  { id: 'build', label: 'Build', description: 'Plan and make workspace changes.' },
  { id: 'develop', label: 'Develop', description: 'Iterate on code and repair issues.' },
  { id: 'review', label: 'Review', description: 'Inspect code, risks, and tests.' },
  { id: 'chat', label: 'Chat', description: 'Answer questions without a build bias.' }
];

export const productName = 'Auralith OS';
export const assistantIdentity = 'Auralith Prime';
export const runtimeIdentity = 'Aegis Core';
export const defaultAssistantMission =
  'A local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution.';

export type ActivityFilter = 'all' | 'issues' | 'commands';
export type TaskBoardFilter = 'active' | 'completed' | 'failed' | 'all';

export const activityFilterOptions: Array<{ value: ActivityFilter; label: string; ariaLabel: string }> = [
  { value: 'all', label: 'All', ariaLabel: 'Show all activity events' },
  { value: 'issues', label: 'Issues', ariaLabel: 'Show issue activity events' },
  { value: 'commands', label: 'Commands', ariaLabel: 'Show command activity events' }
];

export const taskFilterOptions: Array<{ value: TaskBoardFilter; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'all', label: 'All' }
];

export const terminalTaskStatuses = new Set(['completed', 'failed', 'canceled']);

export function severityToEventStatus(severity: string): ToolEvent['status'] {
  if (severity === 'critical' || severity === 'high') return 'error';
  if (severity === 'medium' || severity === 'low') return 'warning';
  return 'ok';
}

export function healthStatusToEventStatus(status: string): ToolEvent['status'] {
  if (status === 'critical' || status === 'failed' || status === 'error') return 'error';
  if (
    status === 'attention' ||
    status === 'watch' ||
    status === 'warning' ||
    status === 'unknown' ||
    status === 'skipped'
  ) {
    return 'warning';
  }
  return 'ok';
}

export function reliabilityStatusToEventStatus(status: string): ToolEvent['status'] {
  if (status === 'degraded' || status === 'critical' || status === 'failed') return 'error';
  if (status === 'watch' || status === 'unknown' || status === 'warning') return 'warning';
  return 'ok';
}
