import { describe, expect, it } from 'vitest';
import {
  addPinnedContextPath,
  normalizeContextPath,
  normalizeContextPaths,
  removePinnedContextPath
} from './contextPins';

describe('context pin utilities', () => {
  it('normalizes relative workspace paths', () => {
    expect(normalizeContextPath(' .\\src\\App.tsx ')).toBe('src/App.tsx');
    expect(normalizeContextPath('@backend\\aegis_ai\\main.py')).toBe('backend/aegis_ai/main.py');
  });

  it('rejects absolute and traversal paths', () => {
    expect(normalizeContextPath('C:\\Projects\\Aegis\\src\\App.tsx')).toBe('');
    expect(normalizeContextPath('/etc/passwd')).toBe('');
    expect(normalizeContextPath('../secret.txt')).toBe('');
    expect(normalizeContextPath('src/../secret.txt')).toBe('');
  });

  it('deduplicates pinned paths while preserving order', () => {
    expect(normalizeContextPaths(['src/App.tsx', 'src\\App.tsx', 'README.md'])).toEqual([
      'src/App.tsx',
      'README.md'
    ]);
  });

  it('adds and removes pinned paths', () => {
    const pinned = addPinnedContextPath(['README.md'], 'src/App.tsx');

    expect(pinned).toEqual(['README.md', 'src/App.tsx']);
    expect(removePinnedContextPath(pinned, 'README.md')).toEqual(['src/App.tsx']);
  });
});
