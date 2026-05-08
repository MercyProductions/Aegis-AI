import { describe, expect, it } from 'vitest';
import {
  combinedApplyValidationStatus,
  validationRepairBriefClipboardText,
  validationRepairFollowUpPromptText,
  validationRepairPromptText,
  validationResultStatus,
  validationRunClipboardText
} from './validationStatus';
import type { ValidateResponse } from '../types';

describe('validation status helpers', () => {
  it('summarizes successful validation', () => {
    expect(validationResultStatus(createValidateResponse({ exit_code: 0 }))).toBe(
      'Validation completed successfully.'
    );
  });

  it('keeps warning messages as the highest-priority status', () => {
    expect(
      validationResultStatus(
        createValidateResponse({ exit_code: 0 }, ['Validation command was inferred from package.json.'])
      )
    ).toBe('Validation command was inferred from package.json.');
  });

  it('summarizes non-zero validation exits and missing commands', () => {
    expect(validationResultStatus(createValidateResponse({ exit_code: 2 }))).toBe(
      'Validation finished with exit code 2.'
    );
    expect(validationResultStatus(createValidateResponse(null))).toBe(
      'Validation finished without a configured command.'
    );
  });

  it('combines apply and validation statuses without losing either result', () => {
    expect(
      combinedApplyValidationStatus('Applied 1 selected change.', 'Validation completed successfully.')
    ).toBe('Applied 1 selected change. Validation completed successfully.');
  });

  it('formats validation runs for clipboard review', () => {
    const response = createValidateResponse({ exit_code: 1 });
    response.validation!.stdout = 'unit stdout\n';
    response.validation!.stderr = 'unit stderr\n';
    response.validation!.summary = 'Validation failed.';
    response.validation!.reason = 'Tests failed.';

    expect(validationRunClipboardText(response.validation!)).toBe(
      [
        'Validation result',
        'Command: npm run test',
        'CWD: workspace',
        'Exit code: 1',
        'Category: test',
        'Summary: Validation failed.',
        'Reason: Tests failed.',
        'Stdout:',
        'unit stdout',
        'Stderr:',
        'unit stderr',
        ''
      ].join('\n')
    );
  });

  it('includes validated generated changes in clipboard review text', () => {
    const response = createValidateResponse({ exit_code: 1 });

    expect(
      validationRunClipboardText(response.validation!, {
        changes: [
          {
            action: 'create',
            path: 'src/generated.ts'
          }
        ]
      })
    ).toContain(['Validation result', 'Validated changes: 1', '- create: src/generated.ts'].join('\n'));
  });

  it('drafts a repair prompt with validation output and generated change context', () => {
    const response = createValidateResponse({ exit_code: 1 });
    response.validation!.stderr = 'missing assertion\n';
    response.validation!.summary = 'Validation failed.';
    response.validation!.reason = 'Tests failed.';

    const prompt = validationRepairPromptText(response.validation!, {
      changes: [
        {
          action: 'update',
          path: 'src/generated.ts'
        }
      ]
    });

    expect(prompt).toContain('Please repair the failed validation from the last generated changes.');
    expect(prompt).toContain('- update: src/generated.ts');
    expect(prompt).toContain('Command: npm run test');
    expect(prompt).toContain('Exit code: 1');
    expect(prompt).toContain('Summary: Validation failed.');
    expect(prompt).toContain('Reason: Tests failed.');
    expect(prompt).toContain('Output:\nmissing assertion');
  });

  it('drafts a follow-up repair prompt from a failed repair validation result', () => {
    const response = createValidateResponse({ exit_code: 2 });
    response.validation!.stdout = 'still failing stdout\n';
    response.validation!.stderr = 'still failing stderr\n';
    response.validation!.summary = 'Repair validation still failed.';
    response.validation!.reason = 'Follow-up tests failed.';

    const prompt = validationRepairFollowUpPromptText(
      'Please repair the failed validation from the last generated changes.\n',
      response.validation!,
      {
        changes: [
          {
            action: 'create',
            path: 'src/generated.ts'
          }
        ]
      }
    );

    expect(prompt).toContain('Please continue repairing this validation failure. The previous repair attempt also failed.');
    expect(prompt).toContain('Original repair request:\nPlease repair the failed validation from the last generated changes.');
    expect(prompt).toContain('- create: src/generated.ts');
    expect(prompt).toContain('Follow-up validation result:');
    expect(prompt).toContain('Command: npm run test');
    expect(prompt).toContain('Exit code: 2');
    expect(prompt).toContain('Summary: Repair validation still failed.');
    expect(prompt).toContain('Reason: Follow-up tests failed.');
    expect(prompt).toContain('Output:\nstill failing stderr\n\nstill failing stdout');
  });

  it('formats a repair trail brief for clipboard debugging', () => {
    expect(
      validationRepairBriefClipboardText({
        command: 'npm run test',
        status: 'failed',
        sourceSummary: 'Manual apply validation failed.',
        sourceReason: 'Tests failed.',
        sourceExitCode: 1,
        contextChanges: [{ action: 'create', path: 'src/generated.ts' }],
        contextPaths: ['src/generated.ts'],
        resultSummary: 'Repair validation still failing.',
        resultExitCode: 2,
        responseTaskId: 'repair-task-1',
        prompt: 'Please repair the failed validation from the last generated changes.\n',
        followUpPrompt: 'Please continue repairing this validation failure.\n'
      })
    ).toBe(
      [
        'Validation repair brief',
        'Status: Failed',
        'Command: npm run test',
        'Source validation: exit 1 / Manual apply validation failed.',
        'Source reason: Tests failed.',
        'Targets:',
        '- create: src/generated.ts',
        'Follow-up validation: exit 2 / Repair validation still failing.',
        'Response task: repair-task-1',
        'Repair prompt:',
        'Please repair the failed validation from the last generated changes.',
        'Next follow-up prompt:',
        'Please continue repairing this validation failure.',
        ''
      ].join('\n')
    );
  });
});

function createValidateResponse(
  validation: Pick<NonNullable<ValidateResponse['validation']>, 'exit_code'> | null,
  warnings: string[] = []
): ValidateResponse {
  return {
    task_id: 'validation-status-test',
    workspace_root: 'workspace',
    events: [],
    validation: validation
      ? {
          command: 'npm run test',
          cwd: 'workspace',
          allowed: true,
          exit_code: validation.exit_code,
          stdout: '',
          stderr: '',
          timed_out: false,
          reason: '',
          category: 'test',
          summary: ''
        }
      : null,
    validation_profile: null,
    warnings
  };
}
