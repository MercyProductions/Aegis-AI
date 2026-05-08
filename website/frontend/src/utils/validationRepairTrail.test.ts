import { describe, expect, it } from 'vitest';
import {
  applyValidationRepairResult,
  buildValidationRepairSubmission,
  createValidationRepairTrailItem,
  createValidationRepairTrailId,
  filterValidationRepairTrail,
  markValidationRepairFollowUpSent,
  updateValidationRepairTrailFollowUpSent,
  updateValidationRepairTrailResult,
  validationRepairTrailEventStatus,
  validationRepairTrailSearchText,
  validationRepairTrailStatusFilters,
  validationRepairTrailStatusLabel,
  type ValidationRepairTrailItem
} from './validationRepairTrail';
import type { CommandRun } from '../types';

describe('validation repair trail helpers', () => {
  it('labels repair states for the UI', () => {
    expect(validationRepairTrailStatusLabel('sent')).toBe('Sent');
    expect(validationRepairTrailStatusLabel('passed')).toBe('Passed');
    expect(validationRepairTrailStatusLabel('failed')).toBe('Failed');
  });

  it('maps repair states to event severity', () => {
    expect(validationRepairTrailEventStatus('sent')).toBe('warning');
    expect(validationRepairTrailEventStatus('passed')).toBe('ok');
    expect(validationRepairTrailEventStatus('failed')).toBe('error');
  });

  it('keeps status filters stable for segmented controls', () => {
    expect(validationRepairTrailStatusFilters).toEqual([
      { value: 'all', label: 'All' },
      { value: 'sent', label: 'Sent' },
      { value: 'failed', label: 'Failed' },
      { value: 'passed', label: 'Passed' }
    ]);
  });

  it('filters repair trail items by status and searchable context', () => {
    const items = [
      createTrailItem({
        id: 'failed-repair',
        status: 'failed',
        command: 'npm run validate',
        sourceReason: 'TypeScript compile failed.',
        contextChanges: [{ action: 'update', path: 'src/App.tsx' }]
      }),
      createTrailItem({
        id: 'passed-repair',
        status: 'passed',
        command: 'go test ./...',
        resultSummary: 'Repair validation passed.',
        contextPaths: ['internal/router.go']
      })
    ];

    expect(filterValidationRepairTrail(items, 'typescript', 'all').map((item) => item.id)).toEqual([
      'failed-repair'
    ]);
    expect(filterValidationRepairTrail(items, 'repair validation', 'passed').map((item) => item.id)).toEqual([
      'passed-repair'
    ]);
    expect(filterValidationRepairTrail(items, '', 'failed').map((item) => item.id)).toEqual(['failed-repair']);
  });

  it('includes result, exit, task, path, and change fields in search text', () => {
    const searchText = validationRepairTrailSearchText(
      createTrailItem({
        responseTaskId: 'task-123',
        sourceExitCode: 1,
        resultExitCode: 2,
        contextPaths: ['src/repair.ts'],
        contextChanges: [{ action: 'create', path: 'src/created.ts' }]
      })
    );

    expect(searchText).toContain('task-123');
    expect(searchText).toContain('exit 1');
    expect(searchText).toContain('exit 2');
    expect(searchText).toContain('src/repair.ts');
    expect(searchText).toContain('create src/created.ts');
  });

  it('creates repair-prefixed ids', () => {
    expect(createValidationRepairTrailId()).toMatch(/^repair-[a-z0-9]+-[a-z0-9]{6}$/);
  });

  it('builds repair submissions from validation output and generated change context', () => {
    const validation = createCommandRun({
      stderr: 'missing semicolon',
      summary: 'Build failed.',
      reason: 'TypeScript failed.'
    });

    const submission = buildValidationRepairSubmission(validation, true, {
      changes: [{ action: 'update', path: 'src/App.tsx' }]
    });

    expect(submission).toMatchObject({
      contextChanges: [{ action: 'update', path: 'src/App.tsx' }],
      contextPaths: ['src/App.tsx']
    });
    expect(submission?.prompt).toContain('Please repair the failed validation');
    expect(submission?.prompt).toContain('- update: src/App.tsx');
    expect(submission?.prompt).toContain('Output:\nmissing semicolon');
  });

  it('does not build repair submissions when validation is unavailable or already healthy', () => {
    expect(buildValidationRepairSubmission(null, true)).toBeNull();
    expect(buildValidationRepairSubmission(createCommandRun({ exit_code: 0 }), false)).toBeNull();
  });

  it('creates repair trail items from a repair submission', () => {
    const validation = createCommandRun({
      command: '',
      summary: '',
      reason: 'Validation command failed.'
    });
    const submission = {
      prompt: 'repair prompt',
      contextChanges: [{ action: 'create' as const, path: 'src/new.ts' }],
      contextPaths: ['src/new.ts']
    };

    expect(
      createValidationRepairTrailItem({
        id: 'repair-1',
        createdAt: '2026-05-07T09:30:00.000Z',
        validation,
        submission
      })
    ).toMatchObject({
      id: 'repair-1',
      command: 'validation',
      prompt: 'repair prompt',
      sourceSummary: 'Validation failed.',
      sourceReason: 'Validation command failed.',
      contextPaths: ['src/new.ts'],
      status: 'sent',
      resultSummary: 'Repair request sent. Waiting for follow-up validation.'
    });
  });

  it('records repair responses without follow-up validation', () => {
    expect(
      applyValidationRepairResult(createTrailItem({ id: 'repair-1' }), {
        task_id: 'task-no-validation',
        validation: null
      })
    ).toMatchObject({
      id: 'repair-1',
      status: 'sent',
      resultSummary: 'Repair response finished without follow-up validation.',
      responseTaskId: 'task-no-validation'
    });
  });

  it('records failed repair validation and prepares follow-up prompts', () => {
    const item = createTrailItem({
      prompt: 'Original repair prompt',
      contextChanges: [{ action: 'update', path: 'src/App.tsx' }]
    });
    const updated = applyValidationRepairResult(item, {
      task_id: 'task-failed',
      validation: createCommandRun({
        exit_code: 2,
        stderr: 'still broken',
        summary: 'Repair still failed.'
      })
    });

    expect(updated.status).toBe('failed');
    expect(updated.resultExitCode).toBe(2);
    expect(updated.resultSummary).toBe('Repair still failed.');
    expect(updated.followUpPrompt).toContain('Please continue repairing this validation failure.');
    expect(updated.followUpPrompt).toContain('- update: src/App.tsx');
    expect(updated.responseTaskId).toBe('task-failed');
  });

  it('records passed repair validation without a follow-up prompt', () => {
    const updated = applyValidationRepairResult(createTrailItem({ followUpPrompt: 'previous follow up' }), {
      task_id: 'task-passed',
      validation: createCommandRun({
        exit_code: 0,
        summary: 'Validation passed.'
      })
    });

    expect(updated.status).toBe('passed');
    expect(updated.resultSummary).toBe('Validation passed.');
    expect(updated.followUpPrompt).toBe('');
    expect(updated.responseTaskId).toBe('task-passed');
  });

  it('updates only the matching repair trail item when recording results', () => {
    const items = [
      createTrailItem({ id: 'target' }),
      createTrailItem({ id: 'other', resultSummary: 'unchanged' })
    ];

    expect(
      updateValidationRepairTrailResult(items, 'target', {
        task_id: 'task-target',
        validation: createCommandRun({ exit_code: 0, summary: 'Passed.' })
      }).map((item) => [item.id, item.resultSummary])
    ).toEqual([
      ['target', 'Passed.'],
      ['other', 'unchanged']
    ]);
  });

  it('marks follow-up repair prompts as sent', () => {
    const item = createTrailItem({
      id: 'repair-follow-up',
      prompt: 'Original prompt',
      followUpPrompt: 'Follow-up prompt',
      status: 'failed',
      resultSummary: 'Still failed.',
      resultExitCode: 2,
      responseTaskId: 'task-failed'
    });

    expect(markValidationRepairFollowUpSent(item)).toMatchObject({
      id: 'repair-follow-up',
      prompt: 'Follow-up prompt',
      followUpPrompt: '',
      status: 'sent',
      resultSummary: 'Follow-up repair request sent. Waiting for validation.',
      resultExitCode: null,
      responseTaskId: ''
    });
  });

  it('updates only the matching repair trail item when sending follow-up prompts', () => {
    const items = [
      createTrailItem({ id: 'target', followUpPrompt: 'Target follow-up' }),
      createTrailItem({ id: 'other', prompt: 'Other prompt', followUpPrompt: 'Other follow-up' })
    ];

    expect(updateValidationRepairTrailFollowUpSent(items, 'target').map((item) => [item.id, item.prompt])).toEqual([
      ['target', 'Target follow-up'],
      ['other', 'Other prompt']
    ]);
  });
});

function createCommandRun(overrides: Partial<CommandRun> = {}): CommandRun {
  return {
    command: 'npm run validate',
    cwd: 'workspace',
    allowed: true,
    exit_code: 1,
    stdout: '',
    stderr: '',
    timed_out: false,
    reason: '',
    category: 'test',
    summary: '',
    ...overrides
  };
}

function createTrailItem(overrides: Partial<ValidationRepairTrailItem> = {}): ValidationRepairTrailItem {
  return {
    id: 'repair-id',
    createdAt: '2026-05-07T09:00:00.000Z',
    command: 'npm test',
    prompt: 'Please repair the failed validation.',
    followUpPrompt: 'Please continue repairing this validation failure.',
    sourceSummary: 'Validation failed.',
    sourceReason: 'Tests failed.',
    sourceExitCode: 1,
    contextChanges: [],
    contextPaths: [],
    status: 'sent',
    resultSummary: 'Waiting for follow-up validation.',
    resultExitCode: null,
    responseTaskId: '',
    ...overrides
  };
}
