import type { CommandRun, FileChange, ValidateResponse } from '../types';

export type ValidationRunClipboardContext = {
  changes: Array<Pick<FileChange, 'action' | 'path'>>;
};

export type ValidationRepairBriefStatus = 'sent' | 'passed' | 'failed';

export type ValidationRepairBrief = {
  command: string;
  status: ValidationRepairBriefStatus;
  sourceSummary: string;
  sourceReason: string;
  sourceExitCode: number | null;
  contextChanges: Array<Pick<FileChange, 'action' | 'path'>>;
  contextPaths: string[];
  resultSummary: string;
  resultExitCode: number | null;
  responseTaskId: string;
  prompt: string;
  followUpPrompt: string;
};

export function validationResultStatus(result: ValidateResponse): string {
  if (result.warnings.length) return result.warnings.join(' ');
  if (result.validation?.exit_code === 0) return 'Validation completed successfully.';
  if (result.validation) return `Validation finished with exit code ${result.validation.exit_code}.`;
  return 'Validation finished without a configured command.';
}

export function combinedApplyValidationStatus(applyStatus: string, validationStatus: string): string {
  const cleanApplyStatus = applyStatus.trim();
  const cleanValidationStatus = validationStatus.trim();

  if (!cleanApplyStatus) return cleanValidationStatus;
  if (!cleanValidationStatus) return cleanApplyStatus;
  return `${cleanApplyStatus} ${cleanValidationStatus}`;
}

export function validationRunClipboardText(validation: CommandRun, context?: ValidationRunClipboardContext): string {
  const validatedChanges = context?.changes.length
    ? [
        `Validated changes: ${context.changes.length}`,
        ...context.changes.map((change) => `- ${change.action}: ${change.path}`)
      ]
    : [];
  const lines = [
    'Validation result',
    ...validatedChanges,
    validation.command ? `Command: ${validation.command}` : 'Command: (not configured)',
    validation.cwd ? `CWD: ${validation.cwd}` : 'CWD: (not set)',
    `Exit code: ${validation.exit_code ?? 'n/a'}`,
    validation.timed_out ? 'Timed out: yes' : '',
    validation.allowed ? '' : 'Allowed: no',
    validation.category ? `Category: ${validation.category}` : '',
    validation.summary ? `Summary: ${validation.summary}` : '',
    validation.reason ? `Reason: ${validation.reason}` : '',
    validation.stdout ? `Stdout:\n${validation.stdout.trimEnd()}` : '',
    validation.stderr ? `Stderr:\n${validation.stderr.trimEnd()}` : ''
  ].filter(Boolean);

  return `${lines.join('\n')}\n`;
}

export function validationRepairBriefClipboardText(item: ValidationRepairBrief): string {
  const targets = item.contextChanges.length
    ? item.contextChanges.map((change) => `- ${change.action}: ${change.path}`)
    : item.contextPaths.length
      ? item.contextPaths.map((path) => `- ${path}`)
      : ['- No validation targets captured.'];
  const followUpResult =
    item.resultExitCode === null
      ? item.resultSummary || 'Waiting for follow-up validation.'
      : `exit ${item.resultExitCode} / ${item.resultSummary || 'Validation result available.'}`;
  const lines = [
    'Validation repair brief',
    `Status: ${repairBriefStatusLabel(item.status)}`,
    `Command: ${item.command || 'validation'}`,
    `Source validation: exit ${item.sourceExitCode ?? 'n/a'} / ${item.sourceSummary || 'Validation failed.'}`,
    item.sourceReason ? `Source reason: ${item.sourceReason}` : '',
    'Targets:',
    ...targets,
    `Follow-up validation: ${followUpResult}`,
    item.responseTaskId ? `Response task: ${item.responseTaskId}` : '',
    '',
    'Repair prompt:',
    item.prompt.trim() || '(not available)'
  ].filter((line) => line !== '');

  const followUpPrompt = item.followUpPrompt.trim();
  if (followUpPrompt) {
    lines.push('Next follow-up prompt:', followUpPrompt);
  }

  return `${lines.join('\n')}\n`;
}

function repairBriefStatusLabel(status: ValidationRepairBriefStatus): string {
  if (status === 'passed') return 'Passed';
  if (status === 'failed') return 'Failed';
  return 'Sent';
}

export function validationRepairPromptText(validation: CommandRun, context?: ValidationRunClipboardContext): string {
  const output = [validation.stderr, validation.stdout].map((item) => item.trim()).filter(Boolean).join('\n\n');
  const changes = context?.changes.length
    ? context.changes.map((change) => `- ${change.action}: ${change.path}`).join('\n')
    : '- No generated change context was captured.';
  const lines = [
    'Please repair the failed validation from the last generated changes.',
    '',
    'Validated changes:',
    changes,
    '',
    'Validation result:',
    validation.command ? `Command: ${validation.command}` : 'Command: (not configured)',
    validation.cwd ? `CWD: ${validation.cwd}` : 'CWD: (not set)',
    `Exit code: ${validation.exit_code ?? 'n/a'}`,
    validation.timed_out ? 'Timed out: yes' : '',
    validation.allowed ? '' : 'Allowed: no',
    validation.summary ? `Summary: ${validation.summary}` : '',
    validation.reason ? `Reason: ${validation.reason}` : '',
    output ? `Output:\n${output}` : '',
    '',
    'Update only the files needed to fix this validation failure, then run validation again.'
  ].filter((line) => line !== '');

  return `${lines.join('\n')}\n`;
}

export function validationRepairFollowUpPromptText(
  originalPrompt: string,
  validation: CommandRun,
  context?: ValidationRunClipboardContext
): string {
  const output = [validation.stderr, validation.stdout].map((item) => item.trim()).filter(Boolean).join('\n\n');
  const changes = context?.changes.length
    ? context.changes.map((change) => `- ${change.action}: ${change.path}`).join('\n')
    : '- No generated change context was captured.';
  const lines = [
    'Please continue repairing this validation failure. The previous repair attempt also failed.',
    '',
    'Original repair request:',
    originalPrompt.trim() || '(not available)',
    '',
    'Validated changes:',
    changes,
    '',
    'Follow-up validation result:',
    validation.command ? `Command: ${validation.command}` : 'Command: (not configured)',
    validation.cwd ? `CWD: ${validation.cwd}` : 'CWD: (not set)',
    `Exit code: ${validation.exit_code ?? 'n/a'}`,
    validation.timed_out ? 'Timed out: yes' : '',
    validation.allowed ? '' : 'Allowed: no',
    validation.summary ? `Summary: ${validation.summary}` : '',
    validation.reason ? `Reason: ${validation.reason}` : '',
    output ? `Output:\n${output}` : '',
    '',
    'Keep the same repair scope. Update only the files needed to fix this validation failure, then run validation again.'
  ].filter((line) => line !== '');

  return `${lines.join('\n')}\n`;
}
