export const MAX_PINNED_CONTEXT_FILES = 8;

export function normalizeContextPath(path: string): string {
  const normalized = path.trim().replace(/\\/g, '/').replace(/^@+/, '').replace(/^\.\/+/, '');
  if (!normalized || normalized.startsWith('/') || /^[a-zA-Z]:\//.test(normalized)) return '';

  const parts = normalized.split('/').filter(Boolean);
  if (!parts.length || parts.some((part) => part === '.' || part === '..')) return '';

  return parts.join('/');
}

export function normalizeContextPaths(paths: string[], maxPinned = MAX_PINNED_CONTEXT_FILES): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const path of paths) {
    const nextPath = normalizeContextPath(path);
    if (!nextPath || seen.has(nextPath)) continue;
    seen.add(nextPath);
    normalized.push(nextPath);
  }

  return normalized.slice(0, Math.max(1, maxPinned));
}

export function addPinnedContextPath(
  current: string[],
  path: string,
  maxPinned = MAX_PINNED_CONTEXT_FILES
): string[] {
  const nextPath = normalizeContextPath(path);
  if (!nextPath) return normalizeContextPaths(current, maxPinned);

  return normalizeContextPaths([...current.filter((item) => normalizeContextPath(item) !== nextPath), nextPath], maxPinned);
}

export function removePinnedContextPath(current: string[], path: string): string[] {
  const target = normalizeContextPath(path);
  if (!target) return normalizeContextPaths(current);
  return normalizeContextPaths(current.filter((item) => normalizeContextPath(item) !== target));
}
