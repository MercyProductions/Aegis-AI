import type { FileChange } from '../types';

export type ApplyChangeScope = 'selected' | 'remaining';
export type GeneratedChangeValidationContext = {
  scope: ApplyChangeScope;
  changes: Array<Pick<FileChange, 'action' | 'path'>>;
};
const changeActions: FileChange['action'][] = ['create', 'update', 'append', 'delete'];

export function generatedChangeId(change: Pick<FileChange, 'action' | 'path'>): string {
  return `${change.action}:${change.path}`;
}

export function appliedChangeRef(change: Pick<FileChange, 'action' | 'path'>): string {
  return `${change.action}: ${change.path}`;
}

export function isGeneratedChangeApplied(change: Pick<FileChange, 'action' | 'path'>, applied: string[]): boolean {
  const refs = new Set(applied.map((item) => item.trim()));
  return refs.has(appliedChangeRef(change)) || refs.has(generatedChangeId(change));
}

export function warningsForGeneratedChange(
  change: Pick<FileChange, 'path'> & Partial<Pick<FileChange, 'action'>>,
  warnings: string[]
): string[] {
  return warnings
    .map((warning) => warning.trim())
    .filter((warning) => warningMatchesGeneratedChange(change, warning));
}

export function unresolvedGeneratedChangeWarnings(changes: FileChange[], applied: string[], warnings: string[]): string[] {
  const appliedChanges = changes.filter((change) => isGeneratedChangeApplied(change, applied));

  return warnings
    .map((warning) => warning.trim())
    .filter(Boolean)
    .filter((warning) => {
      const pathMatches = changes.filter((change) => warningMatchesPath(change.path, warning));
      if (!skippedActionForWarning(warning) && pathMatches.length > 1) {
        return !pathMatches.every((change) => isGeneratedChangeApplied(change, applied));
      }

      return !appliedChanges.some((change) => warningMatchesGeneratedChange(change, warning));
    });
}

export function isGeneratedChangeBlocked(change: Pick<FileChange, 'action' | 'path'>, applied: string[], warnings: string[]): boolean {
  return !isGeneratedChangeApplied(change, applied) && warningsForGeneratedChange(change, warnings).length > 0;
}

export type GeneratedChangeApplyIntent = 'apply' | 'retry' | 'applied';

export function generatedChangeApplyIntent(
  change: Pick<FileChange, 'action' | 'path'>,
  applied: string[],
  warnings: string[]
): GeneratedChangeApplyIntent {
  if (isGeneratedChangeApplied(change, applied)) return 'applied';
  return warningsForGeneratedChange(change, warnings).length ? 'retry' : 'apply';
}

export function remainingGeneratedChanges(changes: FileChange[], applied: string[], warnings: string[] = []): FileChange[] {
  return changes.filter(
    (change) => !isGeneratedChangeApplied(change, applied) && !warningsForGeneratedChange(change, warnings).length
  );
}

export type GeneratedChangeReviewSummary = {
  total: number;
  applied: number;
  remaining: number;
  skipped: number;
};

export type GeneratedChangeDiffStats = {
  added: number;
  removed: number;
  modified: number;
  ready: number;
  total: number;
};

export type ParsedGeneratedChangeTranscript = {
  changes: FileChange[];
  applied: string[];
};

export function summarizeGeneratedChangeReview(
  changes: FileChange[],
  applied: string[],
  warnings: string[]
): GeneratedChangeReviewSummary {
  const appliedCount = changes.filter((change) => isGeneratedChangeApplied(change, applied)).length;
  const skippedCount = changes.filter((change) => isGeneratedChangeBlocked(change, applied, warnings)).length;

  return {
    total: changes.length,
    applied: appliedCount,
    remaining: Math.max(changes.length - appliedCount - skippedCount, 0),
    skipped: skippedCount
  };
}

export function summarizeGeneratedDiffStats(
  changes: Array<Pick<FileChange, 'action' | 'path'>>,
  diffs: Record<string, { added_lines: number; removed_lines: number; modified_lines: number } | undefined>
): GeneratedChangeDiffStats {
  return changes.reduce<GeneratedChangeDiffStats>(
    (summary, change) => {
      const diff = diffs[generatedChangeId(change)];
      if (!diff) return summary;
      return {
        ...summary,
        ready: summary.ready + 1,
        added: summary.added + Math.max(0, diff.added_lines),
        removed: summary.removed + Math.max(0, diff.removed_lines),
        modified: summary.modified + Math.max(0, diff.modified_lines)
      };
    },
    { added: 0, removed: 0, modified: 0, ready: 0, total: changes.length }
  );
}

export function parseGeneratedChangeTranscript(content: string): ParsedGeneratedChangeTranscript | null {
  const lines = content.split(/\r?\n/).map((line) => line.trim());
  const changes: FileChange[] = [];
  const applied = new Set<string>();
  let section: 'generated' | 'applied' | '' = '';

  for (const line of lines) {
    if (/^(pending generated file changes|generated file changes|generated files):/i.test(line)) {
      section = 'generated';
      continue;
    }
    if (/^applied changes:/i.test(line)) {
      section = 'applied';
      continue;
    }
    if (/^[A-Z][A-Za-z ]+:/.test(line) && !line.startsWith('- ')) {
      section = '';
      continue;
    }

    if (section === 'generated') {
      const match = line.match(/^-\s+(.+?)\s+\((create|update|append|delete),\s*(applied|pending)\)$/i);
      if (!match) continue;
      const action = match[2].toLowerCase() as FileChange['action'];
      const path = match[1].trim();
      changes.push({ action, path, content: null, summary: '' });
      if (match[3].toLowerCase() === 'applied') {
        applied.add(appliedChangeRef({ action, path }));
      }
    }

    if (section === 'applied') {
      const match = line.match(/^-\s+(create|update|append|delete):\s+(.+)$/i);
      if (!match) continue;
      const action = match[1].toLowerCase() as FileChange['action'];
      const path = match[2].trim();
      applied.add(appliedChangeRef({ action, path }));
      if (!changes.some((change) => generatedChangeId(change) === generatedChangeId({ action, path }))) {
        changes.push({ action, path, content: null, summary: '' });
      }
    }
  }

  if (!changes.length) return null;
  return { changes, applied: Array.from(applied) };
}

export function changesForApply(
  changes: FileChange[],
  selectedChangeId: string,
  scope: ApplyChangeScope,
  applied: string[] = [],
  warnings: string[] = []
): FileChange[] {
  if (scope === 'remaining') return remainingGeneratedChanges(changes, applied, warnings);
  if (!changes.length) return [];

  const selected = changes.find((change) => generatedChangeId(change) === selectedChangeId);
  const target = selected ?? changes[0];
  return isGeneratedChangeApplied(target, applied) ? [] : [target];
}

export function previewPathForApplyResult(changes: FileChange[], applied: string[]): string {
  return changes.find((change) => isGeneratedChangeApplied(change, applied))?.path ?? changes[0]?.path ?? '';
}

export function mergeAppliedChangeRefs(current: string[], next: string[]): string[] {
  return mergeUniqueText(current, next);
}

export function mergeApplyWarnings(current: string[], next: string[]): string[] {
  return mergeUniqueText(current, next);
}

function mergeUniqueText(current: string[], next: string[]): string[] {
  const merged: string[] = [];
  const seen = new Set<string>();

  for (const item of [...current, ...next]) {
    const normalized = item.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    merged.push(normalized);
  }

  return merged;
}

function warningMatchesGeneratedChange(
  change: Pick<FileChange, 'path'> & Partial<Pick<FileChange, 'action'>>,
  warning: string
): boolean {
  if (!warningMatchesPath(change.path, warning)) return false;

  const warningAction = skippedActionForWarning(warning);
  return !warningAction || !change.action || warningAction === change.action;
}

function warningMatchesPath(path: string, warning: string): boolean {
  const pathPrefix = `${path}:`;
  return warning === path || warning.startsWith(pathPrefix);
}

function skippedActionForWarning(warning: string): FileChange['action'] | null {
  const message = warning.toLowerCase();
  return changeActions.find((action) => message.includes(`skipped ${action}`)) ?? null;
}

export function appliedChangeStatus(appliedCount: number, scope: ApplyChangeScope): string {
  if (!appliedCount) return 'No changes were applied.';
  if (scope === 'selected') {
    return `Applied ${appliedCount} selected change${appliedCount === 1 ? '' : 's'}.`;
  }
  return `Applied ${appliedCount} remaining change${appliedCount === 1 ? '' : 's'}.`;
}

export function generatedValidationContextStatus(context: GeneratedChangeValidationContext): string {
  const count = context.changes.length;
  if (!count) return 'Validation is not tied to generated changes.';

  const scopeLabel = context.scope === 'selected' ? 'selected' : 'remaining';
  return `Validation checked ${count} ${scopeLabel} generated change${count === 1 ? '' : 's'}.`;
}

export function applyStatusWithWarnings(status: string, warnings: string[]): string {
  const cleanStatus = status.trim();
  const cleanWarnings = warnings.map((warning) => warning.trim()).filter(Boolean);

  if (!cleanWarnings.length) return cleanStatus;

  const warningPrefix = cleanWarnings.length === 1 ? 'Warning' : 'Warnings';
  const warningText = `${warningPrefix}: ${cleanWarnings.join(' ')}`;

  return cleanStatus ? `${cleanStatus} ${warningText}` : warningText;
}
