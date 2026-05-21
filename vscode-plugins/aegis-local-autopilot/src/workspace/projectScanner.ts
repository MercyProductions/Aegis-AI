// Project scanning and metadata inference logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const { parseJsonText } = require('../utils/fsSafe.ts');
const { normalizePackageManagerName, packageScriptCommand, pickPackageManagerFromNames } = require('../validation/validationDetector.ts');

/**
 * Patterns for files that should be considered "important" for project context.
 */
const IMPORTANT_FILE_PATTERNS = [
  /^readme(?:\..*)?$/i,
  /^todo(?:\..*)?$/i,
  /^changelog(?:\..*)?$/i,
  /^package\.json$/i,
  /^pnpm-lock\.yaml$/i,
  /^yarn\.lock$/i,
  /^bun\.lock$/i,
  /^bun\.lockb$/i,
  /^package-lock\.json$/i,
  /^tsconfig(?:\..*)?\.json$/i,
  /^vite\.config\./i,
  /^next\.config\./i,
  /^webpack\.config\./i,
  /^pyproject\.toml$/i,
  /^uv\.lock$/i,
  /^poetry\.lock$/i,
  /^pdm\.lock$/i,
  /^requirements.*\.txt$/i,
  /^setup\.py$/i,
  /^cmakelists\.txt$/i,
  /^cargo\.toml$/i,
  /^cargo\.lock$/i,
  /^go\.mod$/i,
  /^go\.sum$/i,
  /^packages\.lock\.json$/i,
  /^packages\.config$/i,
  /^directory\.packages\.props$/i,
  /^directory\.build\.(?:props|targets)$/i,
  /^pom\.xml$/i,
  /^build\.gradle/i,
  /^dockerfile$/i,
  /^makefile$/i,
  /^projectversion\.txt$/i,
  /^packages-lock\.json$/i,
  /^.*\.(?:sln|slnx|csproj|fsproj|vbproj|vcxproj|vcxproj\.filters)$/i
];

/**
 * Detects project languages, frameworks, and package managers.
 */
function inferProjectLanguages(files, importantContents) {
  const languages = new Set();
  const frameworks = new Set();
  const packageManagers = new Set();
  const names = new Set(files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));
  const extensions = new Set(files.map((file) => path.extname(file.relative).toLowerCase()));
  const hasUnityProject = names.has('projectsettings/projectversion.txt') || names.has('packages/manifest.json') || Array.from(names).some((name) => name.startsWith('assets/') && name.endsWith('.unity'));
  const hasPythonLockfile = names.has('uv.lock') || names.has('poetry.lock') || names.has('pdm.lock');
  const hasDotnetProject = Array.from(names).some((name) => name.endsWith('.csproj') || name.endsWith('.sln') || name.endsWith('.slnx'));
  const hasDotnetNugetMetadata = names.has('packages.lock.json') || names.has('packages.config') || names.has('directory.packages.props');

  if (extensions.has('.ts') || extensions.has('.tsx')) languages.add('TypeScript');
  if (extensions.has('.js') || extensions.has('.jsx') || names.has('package.json')) languages.add('JavaScript');
  if (extensions.has('.py') || names.has('pyproject.toml') || names.has('requirements.txt') || hasPythonLockfile) languages.add('Python');
  if (extensions.has('.cpp') || extensions.has('.cc') || extensions.has('.cxx') || extensions.has('.c') || extensions.has('.h') || extensions.has('.hpp')) languages.add('C/C++');
  if (extensions.has('.cs') || hasDotnetProject || hasDotnetNugetMetadata) languages.add('C#/.NET');
  if (extensions.has('.fs') || extensions.has('.fsi') || extensions.has('.fsx') || Array.from(names).some((name) => name.endsWith('.fsproj'))) languages.add('F#/.NET');
  if (extensions.has('.vb') || Array.from(names).some((name) => name.endsWith('.vbproj'))) languages.add('VB.NET');
  if (extensions.has('.rs') || names.has('cargo.toml') || names.has('cargo.lock')) languages.add('Rust');
  if (extensions.has('.go') || names.has('go.mod') || names.has('go.sum')) languages.add('Go');
  if (extensions.has('.java') || names.has('pom.xml') || Array.from(names).some((name) => name.includes('build.gradle'))) languages.add('Java/JVM');
  if (hasUnityProject) {
    languages.add('C#/.NET');
    frameworks.add('Unity');
  }

  if (names.has('pnpm-lock.yaml')) packageManagers.add('pnpm');
  if (names.has('yarn.lock')) packageManagers.add('yarn');
  if (names.has('package-lock.json')) packageManagers.add('npm');
  if (names.has('bun.lock') || names.has('bun.lockb')) packageManagers.add('bun');
  if (names.has('uv.lock')) packageManagers.add('uv');
  if (names.has('poetry.lock')) packageManagers.add('poetry');
  if (names.has('pdm.lock')) packageManagers.add('pdm');

  for (const item of importantContents) {
    if (path.basename(item.path).toLowerCase() !== 'package.json') {
      continue;
    }
    try {
      const pkg = parseJsonText(item.text);
      const declaredPackageManager = normalizePackageManagerName(pkg.packageManager);
      if (declaredPackageManager) packageManagers.add(declaredPackageManager);
      const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
      if (deps.react) frameworks.add('React');
      if (deps.next) frameworks.add('Next.js');
      if (deps.vue) frameworks.add('Vue');
      if (deps.svelte) frameworks.add('Svelte');
      if (deps.vite) frameworks.add('Vite');
      if (deps.express) frameworks.add('Express');
      if (deps.electron) frameworks.add('Electron');
      if (deps.typescript) languages.add('TypeScript');
    } catch (error) {
      // Ignore malformed package snippets.
    }
  }

  if (names.has('package.json') && packageManagers.size === 0) packageManagers.add('npm');

  if (names.has('vite.config.ts') || names.has('vite.config.js')) frameworks.add('Vite');
  if (names.has('next.config.js') || names.has('next.config.mjs') || names.has('next.config.ts')) frameworks.add('Next.js');
  if (names.has('cmakelists.txt')) frameworks.add('CMake');
  if (names.has('pyproject.toml')) frameworks.add('Python packaging');

  return {
    languages: Array.from(languages),
    frameworks: Array.from(frameworks),
    packageManagers: Array.from(packageManagers)
  };
}

/**
 * Infers likely project commands (build, test, etc.) from project info.
 */
function inferProjectCommands(importantContents, files) {
  const commands = [];
  const names = new Set(files.map((file) => file.relative.replace(/\\/g, '/').toLowerCase()));

  for (const item of importantContents) {
    if (path.basename(item.path).toLowerCase() === 'package.json') {
      try {
        const pkg = parseJsonText(item.text);
        const scripts = pkg.scripts || {};
        const packageManager = normalizePackageManagerName(pkg.packageManager) || pickPackageManagerFromNames(names, item.path) || 'npm';
        for (const name of ['build', 'test', 'lint', 'typecheck', 'type-check', 'check', 'dev']) {
          if (scripts[name]) {
            commands.push(packageScriptCommand(packageManager, name));
          }
        }
      } catch (error) {
        // Ignore malformed package snippets.
      }
    }
  }

  if (names.has('cmakelists.txt')) commands.push('cmake --build build');
  const hasSlnSolution = Array.from(names).some((name) => name.endsWith('.sln'));
  const hasSlnxSolution = Array.from(names).some((name) => name.endsWith('.slnx'));
  if (hasSlnSolution || hasSlnxSolution) commands.push(hasSlnSolution ? 'msbuild <solution>.sln' : 'msbuild <solution>.slnx');
  if (names.has('pyproject.toml')) commands.push('python -m pytest');
  if (names.has('requirements.txt')) commands.push('python -m pytest');
  if (names.has('cargo.toml')) commands.push('cargo test');
  if (names.has('go.mod')) commands.push('go test ./...');

  return Array.from(new Set(commands)).slice(0, 12);
}

/**
 * Detects likely entry point files for the project.
 */
function detectEntryPoints(files) {
  const candidates = [
    'src/main.ts',
    'src/main.tsx',
    'src/index.ts',
    'src/index.tsx',
    'src/App.tsx',
    'src/app.tsx',
    'src/main.cpp',
    'src/main.c',
    'main.py',
    'app.py',
    'server.py',
    'Program.cs',
    'main.go',
    'src/main.rs',
    'ProjectSettings/ProjectVersion.txt',
    'Assets/Scenes/Main.unity'
  ];
  const fileSet = new Set(files.map((file) => file.relative.replace(/\\/g, '/')));
  const entries = candidates.filter((candidate) => fileSet.has(candidate));
  for (const file of files) {
    const normalized = file.relative.replace(/\\/g, '/');
    if (/^(pages|app)\/.*\.(tsx|ts|jsx|js)$/.test(normalized) && entries.length < 12) {
      entries.push(normalized);
    }
  }
  return Array.from(new Set(entries)).slice(0, 20);
}

/**
 * Counts occurrences of file extensions in the scanned project.
 */
function countFileTypes(files) {
  const counts = new Map();
  for (const file of files) {
    const ext = path.extname(file.relative).toLowerCase() || '[no extension]';
    counts.set(ext, (counts.get(ext) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 16)
    .map(([ext, count]) => `${ext}: ${count}`);
}

function isLikelyTestFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  return /(^|\/)(test|tests|spec|specs|__tests__)\//.test(normalized) ||
    /\.(test|spec)\.(js|jsx|ts|tsx|py|cs|rs|go|java)$/.test(normalized) ||
    /(_test\.go|test_.*\.py|.*_test\.py)$/.test(normalized);
}

function isLikelyConfigFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  const basename = path.basename(normalized);
  return isImportantWorkspaceFile(normalized) ||
    /\.(config|conf|ini|toml|yaml|yml|jsonc)$/.test(normalized) ||
    /^(\.eslintrc|\.prettierrc|\.babelrc|dockerfile|makefile)/.test(basename);
}

function isUnityImportantFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  return normalized === 'packages/manifest.json' ||
    normalized === 'packages/packages-lock.json' ||
    /^projectsettings\/(?:projectversion\.txt|projectsettings\.asset|editorbuildsettings\.asset|editorsettings\.asset|inputmanager\.asset|tagsmanager\.asset)$/.test(normalized) ||
    /\.(?:asmdef|asmref)$/i.test(normalized);
}

function isImportantWorkspaceFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase();
  const basename = path.basename(normalized);
  return isUnityImportantFile(normalized) || IMPORTANT_FILE_PATTERNS.some((pattern) => pattern.test(basename));
}

function isLikelyBuildFile(relativePath) {
  if (isUnityImportantFile(relativePath)) {
    return true;
  }
  const basename = path.basename(relativePath).toLowerCase();
  return [
    'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lock', 'bun.lockb',
    'tsconfig.json', 'vite.config.ts', 'vite.config.js', 'next.config.js', 'next.config.mjs',
    'pyproject.toml', 'requirements.txt', 'uv.lock', 'poetry.lock', 'pdm.lock', 'setup.py',
    'cargo.toml', 'cargo.lock', 'go.mod', 'go.sum', 'cmakelists.txt', 'makefile', 'dockerfile',
    'pom.xml', 'build.gradle', 'packages.config', 'packages.lock.json', 'directory.packages.props'
  ].includes(basename) || /\.(csproj|fsproj|vbproj|sln|slnx|vcxproj|vcxproj\.filters|asmdef|asmref)$/i.test(basename);
}

module.exports = {
  IMPORTANT_FILE_PATTERNS,
  inferProjectLanguages,
  inferProjectCommands,
  detectEntryPoints,
  countFileTypes,
  isLikelyTestFile,
  isLikelyConfigFile,
  isUnityImportantFile,
  isImportantWorkspaceFile,
  isLikelyBuildFile
};
