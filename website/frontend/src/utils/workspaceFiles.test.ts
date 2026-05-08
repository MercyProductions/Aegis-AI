import { describe, expect, it } from 'vitest';
import type { WorkspaceFile } from '../types';
import { filterWorkspaceFiles } from './workspaceFiles';

const files: WorkspaceFile[] = [
  { path: 'package.json', size: 120, kind: 'text' },
  { path: 'src/main.ts', size: 240, kind: 'text' },
  { path: 'assets/logo.png', size: 1024, kind: 'binary' }
];

describe('workspace file utilities', () => {
  it('returns every file for a blank query', () => {
    expect(filterWorkspaceFiles(files, '   ')).toEqual(files);
  });

  it('filters by path case-insensitively', () => {
    expect(filterWorkspaceFiles(files, 'MAIN').map((file) => file.path)).toEqual(['src/main.ts']);
  });

  it('matches multiple search terms across path and kind', () => {
    expect(filterWorkspaceFiles(files, 'assets binary').map((file) => file.path)).toEqual(['assets/logo.png']);
  });

  it('returns no matches when every term is not present', () => {
    expect(filterWorkspaceFiles(files, 'src binary')).toEqual([]);
  });
});
