import type { WorkspaceFile } from '../types';

export function filterWorkspaceFiles(files: WorkspaceFile[], query: string): WorkspaceFile[] {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);

  if (!terms.length) return files;

  return files.filter((file) => {
    const haystack = `${file.path} ${file.kind}`.toLowerCase();
    return terms.every((term) => haystack.includes(term));
  });
}
