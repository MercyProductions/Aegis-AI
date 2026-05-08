import { describe, expect, it } from 'vitest';
import {
  appliedChangeRef,
  appliedChangeStatus,
  applyStatusWithWarnings,
  changesForApply,
  generatedChangeApplyIntent,
  generatedChangeId,
  generatedValidationContextStatus,
  isGeneratedChangeBlocked,
  isGeneratedChangeApplied,
  mergeAppliedChangeRefs,
  mergeApplyWarnings,
  parseGeneratedChangeTranscript,
  previewPathForApplyResult,
  remainingGeneratedChanges,
  summarizeGeneratedDiffStats,
  summarizeGeneratedChangeReview,
  unresolvedGeneratedChangeWarnings,
  warningsForGeneratedChange
} from './generatedChanges';
import type { FileChange } from '../types';

const changes: FileChange[] = [
  {
    action: 'create',
    path: 'src/first.ts',
    content: 'first',
    summary: 'Create first'
  },
  {
    action: 'update',
    path: 'src/second.ts',
    content: 'second',
    summary: 'Update second'
  }
];

const samePathChanges: FileChange[] = [
  {
    action: 'create',
    path: 'src/shared.ts',
    content: 'seed',
    summary: 'Create shared file'
  },
  {
    action: 'append',
    path: 'src/shared.ts',
    content: 'tail',
    summary: 'Append shared file'
  }
];

describe('generated change helpers', () => {
  it('builds stable ids from action and path', () => {
    expect(generatedChangeId(changes[1])).toBe('update:src/second.ts');
    expect(appliedChangeRef(changes[1])).toBe('update: src/second.ts');
  });

  it('returns only the selected change for selected apply scope', () => {
    expect(changesForApply(changes, 'update:src/second.ts', 'selected')).toEqual([changes[1]]);
  });

  it('falls back to the first change when selected id is stale', () => {
    expect(changesForApply(changes, 'missing:src/missing.ts', 'selected')).toEqual([changes[0]]);
  });

  it('does not return selected changes that were already applied', () => {
    expect(changesForApply(changes, 'update:src/second.ts', 'selected', ['update: src/second.ts'])).toEqual([]);
  });

  it('returns only unapplied generated changes for remaining apply scope', () => {
    expect(changesForApply(changes, 'update:src/second.ts', 'remaining', ['create: src/first.ts'])).toEqual([
      changes[1]
    ]);
    expect(remainingGeneratedChanges(changes, ['create:src/first.ts'])).toEqual([changes[1]]);
  });

  it('keeps skipped changes out of batch apply while allowing selected retry', () => {
    const warnings = ['src/first.ts: skipped create because the file already exists'];

    expect(isGeneratedChangeBlocked(changes[0], [], warnings)).toBe(true);
    expect(remainingGeneratedChanges(changes, [], warnings)).toEqual([changes[1]]);
    expect(changesForApply(changes, 'src/first.ts', 'remaining', [], warnings)).toEqual([changes[1]]);
    expect(changesForApply(changes, 'create:src/first.ts', 'selected', [], warnings)).toEqual([changes[0]]);
  });

  it('labels generated change apply intent as apply retry or applied', () => {
    expect(generatedChangeApplyIntent(changes[0], [], [])).toBe('apply');
    expect(generatedChangeApplyIntent(changes[0], [], ['src/first.ts: skipped create'])).toBe('retry');
    expect(generatedChangeApplyIntent(changes[0], ['create: src/first.ts'], ['src/first.ts: skipped create'])).toBe(
      'applied'
    );
  });

  it('describes selected and batch apply results clearly', () => {
    expect(appliedChangeStatus(1, 'selected')).toBe('Applied 1 selected change.');
    expect(appliedChangeStatus(2, 'remaining')).toBe('Applied 2 remaining changes.');
    expect(appliedChangeStatus(0, 'selected')).toBe('No changes were applied.');
  });

  it('describes which generated changes validation checked', () => {
    expect(generatedValidationContextStatus({ scope: 'selected', changes: [changes[0]] })).toBe(
      'Validation checked 1 selected generated change.'
    );
    expect(generatedValidationContextStatus({ scope: 'remaining', changes })).toBe(
      'Validation checked 2 remaining generated changes.'
    );
  });

  it('selects the first applied path for workspace preview after apply', () => {
    expect(previewPathForApplyResult(changes, ['update: src/second.ts'])).toBe('src/second.ts');
    expect(previewPathForApplyResult(changes, [])).toBe('src/first.ts');
    expect(previewPathForApplyResult([], [])).toBe('');
  });

  it('keeps apply warnings visible in the status text', () => {
    expect(applyStatusWithWarnings('No changes were applied.', ['src/main.ts: skipped create'])).toBe(
      'No changes were applied. Warning: src/main.ts: skipped create'
    );
    expect(applyStatusWithWarnings('Applied 1 selected change.', ['first warning', 'second warning'])).toBe(
      'Applied 1 selected change. Warnings: first warning second warning'
    );
  });

  it('detects applied changes and merges applied references without duplicates', () => {
    expect(isGeneratedChangeApplied(changes[0], ['create: src/first.ts'])).toBe(true);
    expect(isGeneratedChangeApplied(changes[0], ['create:src/first.ts'])).toBe(true);
    expect(isGeneratedChangeApplied(changes[1], ['create: src/first.ts'])).toBe(false);
    expect(mergeAppliedChangeRefs(['create: src/first.ts'], ['create: src/first.ts', 'update: src/second.ts'])).toEqual([
      'create: src/first.ts',
      'update: src/second.ts'
    ]);
  });

  it('merges repeated apply warnings without duplicating panel entries', () => {
    expect(mergeApplyWarnings(['tracked.txt: skipped create'], ['tracked.txt: skipped create', ''])).toEqual([
      'tracked.txt: skipped create'
    ]);
    expect(mergeApplyWarnings(['first warning'], ['second warning', 'first warning'])).toEqual([
      'first warning',
      'second warning'
    ]);
  });

  it('matches apply warnings back to the generated change path', () => {
    expect(
      warningsForGeneratedChange(changes[0], [
        'src/first.ts: skipped create because the file already exists',
        'src/second.ts: skipped update because the file does not exist'
      ])
    ).toEqual(['src/first.ts: skipped create because the file already exists']);
    expect(warningsForGeneratedChange(changes[0], ['src/first.tsx: unrelated prefix should not match'])).toEqual([]);
  });

  it('matches same-path warnings to the generated change action when the warning names one', () => {
    const appendWarning =
      'src/shared.ts: skipped append because the seed create for this file did not apply; use update to modify existing files';

    expect(warningsForGeneratedChange(samePathChanges[0], [appendWarning])).toEqual([]);
    expect(warningsForGeneratedChange(samePathChanges[1], [appendWarning])).toEqual([appendWarning]);
    expect(isGeneratedChangeBlocked(samePathChanges[0], [], [appendWarning])).toBe(false);
    expect(isGeneratedChangeBlocked(samePathChanges[1], [], [appendWarning])).toBe(true);
    expect(remainingGeneratedChanges(samePathChanges, [], [appendWarning])).toEqual([samePathChanges[0]]);
  });

  it('hides generated change warnings after the matching change is applied', () => {
    expect(
      unresolvedGeneratedChangeWarnings(changes, ['create: src/first.ts'], [
        'src/first.ts: skipped create because the file already exists',
        'src/second.ts: skipped update because the file does not exist',
        'General warning'
      ])
    ).toEqual(['src/second.ts: skipped update because the file does not exist', 'General warning']);
  });

  it('keeps unresolved same-path warnings when a different generated action was applied', () => {
    const createWarning = 'src/shared.ts: skipped create because the file already exists';
    const appendWarning =
      'src/shared.ts: skipped append because the seed create for this file did not apply; use update to modify existing files';

    expect(
      unresolvedGeneratedChangeWarnings(samePathChanges, ['create: src/shared.ts'], [createWarning, appendWarning])
    ).toEqual([appendWarning]);
    expect(unresolvedGeneratedChangeWarnings(samePathChanges, ['append: src/shared.ts'], [appendWarning])).toEqual([]);
  });

  it('keeps ambiguous same-path warnings until every same-path generated change is applied', () => {
    const ambiguousWarning = 'src/shared.ts: skipped because the path needs a manual review';

    expect(unresolvedGeneratedChangeWarnings(samePathChanges, ['create: src/shared.ts'], [ambiguousWarning])).toEqual([
      ambiguousWarning
    ]);
    expect(
      unresolvedGeneratedChangeWarnings(samePathChanges, ['create: src/shared.ts', 'append: src/shared.ts'], [
        ambiguousWarning
      ])
    ).toEqual([]);
  });

  it('summarizes generated change review progress', () => {
    expect(
      summarizeGeneratedChangeReview(changes, ['create: src/first.ts'], [
        'src/second.ts: skipped update because the file does not exist'
      ])
    ).toEqual({
      total: 2,
      applied: 1,
      remaining: 0,
      skipped: 1
    });
  });

  it('summarizes aggregate diff statistics for generated changes', () => {
    expect(
      summarizeGeneratedDiffStats(changes, {
        'create:src/first.ts': { added_lines: 12, removed_lines: 0, modified_lines: 0 },
        'update:src/second.ts': { added_lines: 4, removed_lines: 2, modified_lines: 1 }
      })
    ).toEqual({
      total: 2,
      ready: 2,
      added: 16,
      removed: 2,
      modified: 1
    });
  });

  it('parses generated changes from saved assistant transcript text', () => {
    expect(
      parseGeneratedChangeTranscript(
        [
          'Done.',
          '',
          'Generated file changes:',
          '- src/App.tsx (update, applied)',
          '- src/new.ts (create, pending)',
          '',
          'Applied changes:',
          '- update: src/App.tsx',
          '',
          'Validation: passed'
        ].join('\n')
      )
    ).toEqual({
      changes: [
        { action: 'update', path: 'src/App.tsx', content: null, summary: '' },
        { action: 'create', path: 'src/new.ts', content: null, summary: '' }
      ],
      applied: ['update: src/App.tsx']
    });
  });
});
