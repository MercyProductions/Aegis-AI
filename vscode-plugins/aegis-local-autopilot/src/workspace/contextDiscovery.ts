// Context discovery and file selection logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');

/**
 * Extracts likely import specifiers from text.
 */
function extractImportSpecifiers(text) {
  const specs = new Set();
  const patterns = [
    /import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g,
    /require\(\s*['"]([^'"]+)['"]\s*\)/g,
    /from\s+['"]([^'"]+)['"]/g
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      specs.add(match[1]);
    }
  }
  return Array.from(specs).slice(0, 30);
}

/**
 * Generates candidate file paths for a given import base.
 */
function importCandidatePaths(base) {
  const extensions = ['', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.css', '.scss', '.json'];
  const candidates = [];
  for (const ext of extensions) {
    candidates.push(`${base}${ext}`.replace(/\\/g, '/'));
  }
  for (const ext of extensions.filter(Boolean)) {
    candidates.push(`${base}/index${ext}`.replace(/\\/g, '/'));
  }
  return candidates;
}

/**
 * Heuristic-based file relevance scoring for context selection.
 */
function selectRelevantFiles(snapshot, request, options = {}) {
  const score = new Map();
  const knownFiles = new Set((snapshot.files || []).map((file) => file.relative.replace(/\\/g, '/')));

  const add = (file, points) => {
    const normalized = String(file || '').replace(/\\/g, '/').replace(/^\/+/, '');
    if (!normalized || normalized === '.' || normalized.endsWith('/') || !knownFiles.has(normalized)) {
      return;
    }
    // Note: isBlockedRelativePath check should be done by the caller or passed in.
    if (options.isBlockedPath && options.isBlockedPath(normalized)) {
      return;
    }
    score.set(normalized, (score.get(normalized) || 0) + points);
  };

  const requestText = `${request || ''}\n${options.validationText || ''}`.toLowerCase();
  const terms = requestText
    .replace(/[^a-z0-9_./-]+/g, ' ')
    .split(/\s+/)
    .filter((term) => term.length >= 3)
    .slice(0, 80);

  for (const file of snapshot.importantFiles || []) add(file, 10);
  for (const file of snapshot.entryPoints || []) add(file, 14);
  for (const file of snapshot.configFiles || []) add(file, 8);
  for (const item of (snapshot.recentFiles || []).slice(0, 12)) add(item.path, 5);

  if (snapshot.diagnostics) {
    for (const diagnostic of snapshot.diagnostics) {
      const match = diagnostic.match(/^- ([^:]+):/);
      if (match) add(match[1], 16);
    }
  }

  for (const hintedFile of extractFileHintsFromText(options.validationText || requestText, snapshot)) {
    add(hintedFile, 18);
  }

  if (options.activeEditorPath && options.isPathInside && options.isPathInside(snapshot.target.root, options.activeEditorPath)) {
    add(path.relative(snapshot.target.root, options.activeEditorPath).replace(/\\/g, '/'), 20);
  }

  if (snapshot.files) {
    for (const file of snapshot.files) {
      const normalized = file.relative.replace(/\\/g, '/');
      const lower = normalized.toLowerCase();
      for (const term of terms) {
        if (lower.includes(term)) {
          add(normalized, 7);
        }
      }
    }
  }

  const seeds = Array.from(score.keys()).slice(0, 8);
  for (const file of inferDependencyLinks(snapshot, seeds)) {
    add(file, 6);
  }

  if (options.dependencyGraph && Array.isArray(options.dependencyGraph.edges)) {
    const seedSet = new Set(Array.from(score.keys()).slice(0, 12));
    for (const edge of options.dependencyGraph.edges) {
      if (seedSet.has(edge.from)) add(edge.to, 6);
      if (seedSet.has(edge.to)) add(edge.from, 4);
    }
  }

  if (options.symbolIndex && Array.isArray(options.symbolIndex.symbols)) {
    for (const symbol of options.symbolIndex.symbols.slice(0, 100)) {
      const haystack = `${symbol.name || ''} ${symbol.kind || ''}`.toLowerCase();
      if (terms.some((term) => haystack.includes(term))) {
        add(symbol.file, 9);
      }
    }
  }

  const focusFile = snapshot.target && snapshot.target.focusFileRelative
    ? snapshot.target.focusFileRelative.replace(/\\/g, '/').replace(/^\/+/, '')
    : '';
  const focusFolder = snapshot.target && snapshot.target.focusRelative
    ? snapshot.target.focusRelative.replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+$/, '')
    : '';

  if (focusFile) add(focusFile, 24);
  if (focusFolder && snapshot.files) {
    for (const file of snapshot.files) {
      const normalized = file.relative.replace(/\\/g, '/');
      if (normalized.startsWith(`${focusFolder}/`)) {
        add(normalized, options.isLikelyTestFile && options.isLikelyTestFile(normalized) ? 8 : 12);
      }
    }
  }

  return Array.from(score.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, options.maxFiles || 14)
    .map(([file]) => file);
}

/**
 * Scans text for potential file paths that exist in the project.
 */
function extractFileHintsFromText(text, snapshot) {
  if (!text) return [];
  const fileSet = new Set((snapshot.files || []).map((file) => file.relative.replace(/\\/g, '/')));
  const hints = new Set();
  const patterns = [
    /([A-Za-z0-9_./\\-]+\.(?:js|jsx|ts|tsx|py|cs|rs|go|java|cpp|c|h|hpp|json|toml|yaml|yml|md))(?::\d+)?/g,
    /File "([^"]+\.(?:py|js|ts|tsx|cs))", line \d+/g
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const raw = (match[1] || '').replace(/\\/g, '/').replace(/^[A-Za-z]:\//, '');
      const exact = Array.from(fileSet).find((file) => file === raw || raw.endsWith(`/${file}`));
      if (exact) hints.add(exact);
      if (hints.size >= 20) break;
    }
  }
  return Array.from(hints);
}

/**
 * Expands a list of files by traversing a dependency graph.
 */
function expandSelectedFilesWithGraph(graph, selectedFiles, maxFiles) {
  if (!graph || !Array.isArray(graph.edges) || selectedFiles.length >= maxFiles) {
    return selectedFiles.slice(0, maxFiles);
  }
  const selected = new Set(selectedFiles);
  const seeds = selectedFiles.slice(0, 8);
  for (const edge of graph.edges) {
    if (selected.size >= maxFiles) break;
    if (seeds.includes(edge.from) && edge.to) selected.add(edge.to);
    if (selected.size >= maxFiles) break;
    if (seeds.includes(edge.to) && edge.from) selected.add(edge.from);
  }
  return Array.from(selected).slice(0, maxFiles);
}

/**
 * Infers logical dependency links based on naming conventions and directory structure.
 */
function inferDependencyLinks(snapshot, seedFiles) {
  const linked = new Set();
  if (!snapshot.files) return [];
  const fileSet = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/')));
  for (const seed of seedFiles) {
    const dir = path.dirname(seed).replace(/\\/g, '/');
    const base = path.basename(seed, path.extname(seed)).toLowerCase();
    for (const file of fileSet) {
      const normalized = file.replace(/\\/g, '/');
      const sameDir = dir === '.' || normalized.startsWith(`${dir}/`);
      const fileBase = path.basename(normalized, path.extname(normalized)).toLowerCase();
      if (sameDir && (fileBase === `${base}.test` || fileBase === `${base}.spec` || fileBase === base)) {
        linked.add(normalized);
      }
    }
  }
  return Array.from(linked);
}

module.exports = {
  extractImportSpecifiers,
  importCandidatePaths,
  selectRelevantFiles,
  extractFileHintsFromText,
  expandSelectedFilesWithGraph,
  inferDependencyLinks
};
