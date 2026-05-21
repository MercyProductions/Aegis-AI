// Validation command detection logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const { parseJsonText } = require('../utils/fsSafe.ts');

/**
 * Detects project validation commands (test, lint, build, etc.) based on
 * project snapshots.
 * @param {object} snapshot - The project snapshot.
 * @param {string[]} [preferences=[]] - User preferences for validation commands.
 * @returns {object[]} - Array of { command: string, cwd: string, relativeCwd: string }
 */
function detectValidationCommands(snapshot, preferences = []) {
  const files = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  const commands = [];
  const packageJsonItems = snapshot.importantContents.filter((item) => path.basename(item.path).toLowerCase() === 'package.json');

  for (const item of packageJsonItems) {
    let pkg;
    try {
      pkg = parseJsonText(item.text);
    } catch (error) {
      continue;
    }
    const scripts = pkg.scripts || {};
    const dir = path.dirname(item.path);
    const cwd = dir === '.' ? snapshot.target.root : path.join(snapshot.target.root, dir);
    const relativeCwd = dir === '.' ? '' : dir;
    const packageManager = pickPackageManagerForPath(snapshot, item.path);
    if (scripts.test) {
      commands.push(makeValidationCommand(packageScriptCommand(packageManager, 'test'), cwd, relativeCwd));
    }
    if (scripts.lint) {
      commands.push(makeValidationCommand(packageScriptCommand(packageManager, 'lint'), cwd, relativeCwd));
    }
    const typeScriptCheck = scripts.typecheck || scripts['type-check'];
    if (typeScriptCheck) {
      commands.push(makeValidationCommand(packageScriptCommand(packageManager, scripts.typecheck ? 'typecheck' : 'type-check'), cwd, relativeCwd));
    }
    if (scripts.build) {
      commands.push(makeValidationCommand(packageScriptCommand(packageManager, 'build'), cwd, relativeCwd));
    }
  }

  if (Array.from(files).some((name) => name.endsWith('.csproj') || name.endsWith('.fsproj') || name.endsWith('.vbproj'))) {
    commands.push(makeValidationCommand('dotnet build', snapshot.target.root, ''));
  }
  if (files.has('cargo.toml')) {
    commands.push(makeValidationCommand('cargo check', snapshot.target.root, ''));
  }
  if (files.has('pyproject.toml') || files.has('pytest.ini') || files.has('requirements.txt') || Array.from(files).some((name) => name.startsWith('tests/') && name.endsWith('.py'))) {
    commands.push(makeValidationCommand('python -m pytest', snapshot.target.root, ''));
  }
  if (files.has('go.mod')) {
    commands.push(makeValidationCommand('go test ./...', snapshot.target.root, ''));
  }
  if (files.has('cmakelists.txt') && snapshot.directories.some((dir) => dir.relative.replace(/\\/g, '/').toLowerCase() === 'build')) {
    commands.push(makeValidationCommand('cmake --build build', snapshot.target.root, ''));
  }

  const seen = new Set();
  const prefs = Array.isArray(preferences) ? preferences : [];
  return commands.filter((item) => {
    const key = `${item.cwd}|${item.command}`;
    if (seen.has(key) || !isSafeValidationCommand(item.command)) {
      return false;
    }
    if (prefs.length && !prefs.some((pref) => item.command.startsWith(pref) || item.command === pref)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 6);
}

/**
 * Determines the appropriate package manager for a given package.json path.
 */
function pickPackageManagerForPath(snapshot, packagePath) {
  const names = new Set(snapshot.files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  const fromNames = pickPackageManagerFromNames(names, packagePath);
  if (fromNames) return fromNames;
  if (snapshot.packageManagers && snapshot.packageManagers.includes('bun')) return 'bun';
  if (snapshot.packageManagers && snapshot.packageManagers.includes('pnpm')) return 'pnpm';
  if (snapshot.packageManagers && snapshot.packageManagers.includes('yarn')) return 'yarn';
  return 'npm';
}

/**
 * Picks package manager based on lockfile proximity.
 */
function pickPackageManagerFromNames(names, packagePath) {
  const dir = path.dirname(packagePath).replace(/\\/g, '/');
  const prefix = dir === '.' ? '' : `${dir}/`;
  if (names.has(`${prefix}bun.lock`) || names.has(`${prefix}bun.lockb`)) return 'bun';
  if (names.has(`${prefix}pnpm-lock.yaml`)) return 'pnpm';
  if (names.has(`${prefix}yarn.lock`)) return 'yarn';
  if (names.has(`${prefix}package-lock.json`)) return 'npm';
  return '';
}

/**
 * Normalizes package manager names from strings.
 */
function normalizePackageManagerName(value) {
  const text = String(value || '').trim().toLowerCase();
  if (text.startsWith('bun@')) return 'bun';
  if (text.startsWith('pnpm@')) return 'pnpm';
  if (text.startsWith('yarn@')) return 'yarn';
  if (text.startsWith('npm@')) return 'npm';
  return '';
}

/**
 * Returns the command string for a given script and package manager.
 */
function packageScriptCommand(packageManager, script) {
  if (packageManager === 'npm') {
    return script === 'test' ? 'npm test' : `npm run ${script}`;
  }
  if (packageManager === 'bun') {
    return `bun run ${script}`;
  }
  return `${packageManager} ${script}`;
}

/**
 * Creates a validation command descriptor.
 */
function makeValidationCommand(command, cwd, relativeCwd) {
  return { command, cwd, relativeCwd };
}

/**
 * Checks whether a command string is in the whitelist of safe validation commands.
 */
function isSafeValidationCommand(command) {
  return /^(npm test|npm run build|npm run lint|npm run typecheck|npm run type-check|pnpm test|pnpm build|pnpm lint|pnpm typecheck|pnpm type-check|yarn test|yarn build|yarn lint|yarn typecheck|yarn type-check|bun run test|bun run build|bun run lint|bun run typecheck|bun run type-check|dotnet build|cargo check|go test \.\/\.\.\.|python -m pytest|cmake --build build)$/.test(command);
}

/**
 * Classifies a validation failure into categories like missing-tool, missing-dependency, etc.
 */
function classifyValidationFailure(validation) {
  const output = (validation.output || '').toLowerCase();
  if (output.includes('not recognized') || output.includes('command not found') || output.includes('cannot find executable')) {
    return { kind: 'missing-tool', detail: 'The required build or test tool is not installed or not in PATH.' };
  }
  if (output.includes('cannot find module') || output.includes('module not found') || output.includes('failed to resolve') || output.includes('is not a known package')) {
    return { kind: 'missing-dependency', detail: 'A required library or package is missing. Try running install.' };
  }
  return { kind: 'code-or-config', detail: 'The failure appears to be caused by code errors or project configuration.' };
}

/**
 * Generates a human-readable summary of a validation result.
 */
function summarizeValidation(validation) {
  if (validation.skipped) {
    return 'Validation was skipped.';
  }
  const classification = classifyValidationFailure(validation);
  const parts = [];
  parts.push(`Status: ${validation.success ? 'PASSED' : 'FAILED'}`);
  if (!validation.success) {
    parts.push(`Classification: Likely ${classification.kind.replace(/-/g, ' ')}`);
    parts.push(`Advice: ${classification.detail}`);
    if (classification.kind === 'missing-tool') {
      parts.push('Check PATH and environment.');
    }
  }
  return parts.join('\n');
}

module.exports = {
  detectValidationCommands,
  pickPackageManagerForPath,
  pickPackageManagerFromNames,
  normalizePackageManagerName,
  packageScriptCommand,
  makeValidationCommand,
  isSafeValidationCommand,
  classifyValidationFailure,
  summarizeValidation
};
