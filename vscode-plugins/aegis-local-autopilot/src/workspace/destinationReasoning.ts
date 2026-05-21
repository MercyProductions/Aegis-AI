const path = require('path');

const CONFIG_FILE_RE = /(^|\/)(package\.json|tsconfig(?:\..*)?\.json|vite\.config\.|webpack\.config\.|next\.config\.|pyproject\.toml|requirements.*\.txt|cmakelists\.txt|cargo\.toml|go\.mod|.*\.(?:csproj|fsproj|vbproj|vcxproj|sln|slnx))$/i;
const TEST_FILE_RE = /(^|\/)(__tests__|tests?|specs?)\/|(?:\.test|\.spec)\.(?:js|jsx|ts|tsx|py|cs|rs|go)$/i;
const COMPONENT_FILE_RE = /(^|\/)components?\//i;
const ROUTE_FILE_RE = /(^|\/)(routes?|pages?|app|api)\//i;
const SOURCE_FILE_RE = /(^|\/)(src|lib|app|assets\/scripts)\//i;
const LOCK_FILE_RE = /(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|cargo\.lock|go\.sum|uv\.lock|poetry\.lock|pdm\.lock)$/i;

function buildDestinationReasoning(proposal, snapshot, target) {
  const edits = Array.isArray(proposal && proposal.fileEdits) ? proposal.fileEdits : [];
  const files = new Set((snapshot && Array.isArray(snapshot.files) ? snapshot.files : []).map((file) => normalizePath(file.relative || file.path || '')));
  const focusFolder = normalizePath((target && target.focusRelative) || (snapshot && snapshot.target && snapshot.target.focusRelative) || '');
  const focusFile = normalizePath((target && target.focusFileRelative) || (snapshot && snapshot.target && snapshot.target.focusFileRelative) || '');
  const selectedContext = focusFile || focusFolder;

  return edits.map((edit) => {
    const targetPath = normalizePath(edit.path || '');
    const existing = files.has(targetPath);
    const pathAdjusted = Boolean(edit.originalPath && normalizePath(edit.originalPath) !== targetPath);
    const source = inferDecisionSource(targetPath, edit.reason || '', existing, selectedContext);
    return {
      path: targetPath,
      existing,
      choiceReason: explainPathChoice(targetPath, edit.reason || '', existing, source, selectedContext),
      source,
      risk: classifyDestinationRisk(targetPath, existing),
      selectedContext,
      safety: {
        pathAdjusted,
        originalPath: pathAdjusted ? String(edit.originalPath || '') : '',
        rejected: false,
        status: pathAdjusted ? 'normalized-relative-path' : 'accepted'
      }
    };
  });
}

function normalizePath(value) {
  return String(value || '').replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+$/, '');
}

function inferDecisionSource(targetPath, reason, existing, selectedContext) {
  const lowerReason = String(reason || '').toLowerCase();
  if (lowerReason.includes('converted generated code')) {
    return 'model';
  }
  if (selectedContext && (targetPath === selectedContext || targetPath.startsWith(selectedContext + '/'))) {
    return 'user-selected folder';
  }
  if (existing) {
    return 'existing file structure';
  }
  if (CONFIG_FILE_RE.test(targetPath) || COMPONENT_FILE_RE.test(targetPath) || ROUTE_FILE_RE.test(targetPath) || TEST_FILE_RE.test(targetPath) || SOURCE_FILE_RE.test(targetPath)) {
    return 'framework convention';
  }
  return 'model';
}

function explainPathChoice(targetPath, reason, existing, source, selectedContext) {
  const base = existing
    ? 'Existing file selected because the proposal updates current project structure.'
    : 'New file proposed at this path because it matches the request and project layout.';
  const placement = placementExplanation(targetPath, selectedContext);
  const modelReason = String(reason || '').trim();
  return [base, placement, modelReason].filter(Boolean).join(' ');
}

function placementExplanation(targetPath, selectedContext) {
  if (CONFIG_FILE_RE.test(targetPath)) {
    return 'Configuration/build metadata belongs at the package or project root instead of inside an arbitrary selected folder.';
  }
  if (COMPONENT_FILE_RE.test(targetPath)) {
    return 'Component code belongs under the existing components area.';
  }
  if (ROUTE_FILE_RE.test(targetPath)) {
    return 'Route/page code belongs under the existing routing area.';
  }
  if (TEST_FILE_RE.test(targetPath)) {
    return 'Test files are placed near test conventions rather than forced into the selected folder.';
  }
  if (SOURCE_FILE_RE.test(targetPath)) {
    return 'Source files are placed under the existing source/app structure.';
  }
  if (selectedContext && (targetPath === selectedContext || targetPath.startsWith(selectedContext + '/'))) {
    return 'The selected folder matched the natural destination for this edit.';
  }
  return selectedContext ? 'The selected folder was used as context, while the write destination was chosen relative to the workspace root.' : '';
}

function classifyDestinationRisk(targetPath, existing) {
  if (LOCK_FILE_RE.test(targetPath)) {
    return 'high';
  }
  if (CONFIG_FILE_RE.test(targetPath)) {
    return existing ? 'medium' : 'low';
  }
  if (TEST_FILE_RE.test(targetPath) || /\.(md|txt)$/i.test(targetPath)) {
    return 'low';
  }
  return existing ? 'medium' : 'low';
}

module.exports = {
  buildDestinationReasoning,
  classifyDestinationRisk,
  inferDecisionSource,
  normalizePath
};
