// Workspace target resolution logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const { isPathInside } = require('../utils/pathSafe.ts');

/**
 * Checks whether a value looks like a valid WorkspaceTarget.
 */
function isWorkspaceTarget(value) {
  return Boolean(value && typeof value.root === 'string' && typeof value.label === 'string');
}

/**
 * Creates a WorkspaceTarget object from root and workspace folder info.
 * @param {string} root - The target root directory.
 * @param {object} [workspaceFolder] - Optional info about the VS Code workspace folder.
 * @param {object} [options] - Focus options (focusPath, focusKind, focusFilePath).
 * @returns {object}
 */
function makeWorkspaceTarget(root, workspaceFolder, options = {}) {
  const resolvedRoot = path.resolve(root);
  // workspaceFolder might be a vscode.WorkspaceFolder or a simple object with { name, uri: { fsPath } }
  const wsRootPath = (workspaceFolder && workspaceFolder.uri) ? workspaceFolder.uri.fsPath : (workspaceFolder ? workspaceFolder.root : undefined);
  const workspaceRoot = wsRootPath ? path.resolve(wsRootPath) : resolvedRoot;
  const workspaceName = workspaceFolder ? workspaceFolder.name : path.basename(resolvedRoot);

  const relative = workspaceRoot !== resolvedRoot && isPathInside(workspaceRoot, resolvedRoot)
    ? path.relative(workspaceRoot, resolvedRoot)
    : '';

  const focusPath = options.focusPath ? path.resolve(options.focusPath) : '';
  const focusFilePath = options.focusFilePath ? path.resolve(options.focusFilePath) : '';

  const focusRelative = focusPath && workspaceRoot !== focusPath && isPathInside(workspaceRoot, focusPath)
    ? path.relative(workspaceRoot, focusPath).replace(/\\/g, '/')
    : '';

  const focusFileRelative = focusFilePath && isPathInside(workspaceRoot, focusFilePath)
    ? path.relative(workspaceRoot, focusFilePath).replace(/\\/g, '/')
    : '';

  const focusedLabel = focusFileRelative || focusRelative;

  return {
    root: resolvedRoot,
    workspaceRoot,
    label: focusedLabel
      ? workspaceName + ' / ' + focusedLabel
      : (relative || workspaceName),
    workspaceFolderName: workspaceName,
    focusPath,
    focusKind: options.focusKind || (focusFilePath ? 'file' : (focusPath ? 'folder' : 'workspace')),
    focusRelative,
    focusFileRelative
  };
}

module.exports = {
  isWorkspaceTarget,
  makeWorkspaceTarget
};
