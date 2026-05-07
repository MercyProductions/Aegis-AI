import { describe, expect, it } from 'vitest';
import {
  createValidationRepairTrailId,
  filterValidationRepairTrail,
  validationRepairTrailEventStatus,
  validationRepairTrailSearchText,
  validationRepairTrailStatusFilters,
  validationRepairTrailStatusLabel,
  type ValidationRepairTrailItem
} from './validationRepairTrail';

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
});

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
