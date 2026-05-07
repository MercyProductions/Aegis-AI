import { access, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(process.env.AEGIS_E2E_ROOT || path.join(scriptDir, '..'));
const backendUrl = stripTrailingSlash(process.env.AEGIS_E2E_BACKEND_URL || 'http://127.0.0.1:8787');
const frontendUrl = stripTrailingSlash(process.env.AEGIS_E2E_FRONTEND_URL || 'http://127.0.0.1:5173');
const keepWorkspace = process.env.AEGIS_E2E_KEEP_WORKSPACE === '1';
const headed = process.env.AEGIS_E2E_HEADED === '1';
const workspaceRoot = path.join(root, '.tmp', `e2e-web-${timestamp()}-${process.pid}`);
const alternateProjectRoot = path.join(workspaceRoot, 'project-switch-fixture');
const conversationStorageKey = 'aegis.web.conversations.v1';
const composerDraftStorageKey = 'aegis.web.composerDraft.v1';
const customAgentsStorageKey = 'aegis.customAgents.v1';
const authSessionStorageKey = 'aegis.auth.session.v1';
const detailsPanelVisibleStorageKey = 'aegis.detailsPanelVisible.v1';
const detailPanelSectionsStorageKey = 'aegis.detailPanelSections.v1';

let browser;
let page;
let cleanupWorkspace = false;

try {
  await waitForJson(`${backendUrl}/api/health`, (health) => Boolean(health?.ready), 'backend health');
  await waitForHttpOk(frontendUrl, 'frontend');

  const originalConfig = await apiJson('GET', '/api/config');
  const originalWorkspace = await restoreWorkspaceValue(originalConfig.default_workspace || 'workspace');

  try {
    await prepareWorkspace(workspaceRoot);
    cleanupWorkspace = true;
    await apiJson('POST', '/api/config', { default_workspace: workspaceRoot });

    const profile = await apiJson(
      'GET',
      `/api/workspace/profile?workspace_root=${encodeURIComponent(workspaceRoot)}`
    );
    assert(
      profile.dependency_profile?.validation_commands?.includes('npm run test'),
      'BOM-prefixed package.json was not detected as an npm workspace with npm run test.'
    );

    const browserPath = await findBrowserExecutable();
    const authSession = await apiJson('POST', '/api/auth/register', {
      name: 'Auralith E2E',
      email: `auralith-e2e-${Date.now()}-${process.pid}@example.test`,
      password: 'AuralithPass123!',
      confirm_password: 'AuralithPass123!'
    });
    browser = await chromium.launch({
      executablePath: browserPath,
      headless: !headed
    });
    await exercisePublicWebsiteRoutes(browser);
    await exerciseProtectedAuthGate(browser);
    page = await browser.newPage({ acceptDownloads: true, viewport: { width: 1440, height: 1050 } });
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: frontendUrl });
    await page.addInitScript(
      ({ key, session }) => {
        window.localStorage.setItem(key, JSON.stringify(session));
      },
      { key: authSessionStorageKey, session: authSession }
    );
    const runtimeIssues = [];
    page.on('console', (message) => {
      if (['warning', 'error'].includes(message.type())) {
        if (message.text().includes('Failed to load resource')) return;
        runtimeIssues.push(`${message.type()}: ${message.text()}`);
      }
    });
    page.on('pageerror', (error) => {
      runtimeIssues.push(`pageerror: ${error.stack || error.message}`);
    });
    page.on('response', (response) => {
      if (response.status() < 400) return;

      const request = response.request();
      runtimeIssues.push(`http ${response.status()}: ${request.method()} ${response.url()}`);
    });

    await page.goto(`${frontendUrl}/app`, { waitUntil: 'domcontentloaded' });
    await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel visible on clean startup');
    await exerciseProjectHistorySwitcher(page);
    await exerciseCustomAgentEditor(page);
    await exerciseHeaderModelSwitcher(page);
    await exerciseSavedSessionDelete(page);
    await exerciseLargeSavedSessionHistory(page);
    await exerciseWorkspaceFileFilter(page);
    await exerciseDetailsPanelCollapse(page);
    await exerciseDetailsPanelVisibilityPreference(page);
    await exercisePinnedContextFiles(page);
    await exerciseGeneratedChangeApplyScopes(page);
    await exerciseManualApplyWarningStatus(page);
    await exerciseSamePathWarningPrecision(page);
    await exerciseGeneratedChangeReviewRestore(page);
    await exerciseComposerDraftRestore(page);
    await exerciseChatAutoScroll(page);
    await exerciseQueuedPromptTray(page);
    await exerciseStopActiveResponse(page);
    await exerciseResponsiveShell(page);
    await exerciseResponsiveSettingsModal(page);
    await exerciseResponsiveAuthenticatedOverlays(page);

    await clickUnique(page.getByRole('button', { name: 'Settings', exact: true }), 'Settings button');

    const setupAction = page.getByRole('button', { name: 'Set up workspace for Workspace', exact: true });
    await setupAction.waitFor({ state: 'visible', timeout: 30_000 });
    await clickUnique(setupAction, 'diagnostic setup action');
    await waitForLocatorCount(page.getByText('Workspace setup saved', { exact: false }), 1, 'workspace setup status');

    const validationAction = page.getByRole('button', { name: 'Run validation for Workspace', exact: true });
    await validationAction.waitFor({ state: 'visible', timeout: 30_000 });
    await clickUnique(validationAction, 'diagnostic validation action');
    await waitForLocatorCount(
      page.getByText('Validation completed successfully.', { exact: true }),
      1,
      'validation success status',
      60_000
    );
    await waitForLocatorCount(page.getByText('Runtime Healthy', { exact: true }), 1, 'healthy runtime status');

    const applyResult = await apiJson('POST', '/api/apply', {
      workspace_root: workspaceRoot,
      changes: [
        {
          action: 'update',
          path: 'tracked.txt',
          summary: 'Update tracked checkpoint fixture',
          content: 'after checkpoint apply\n'
        },
        {
          action: 'create',
          path: 'generated/checkpoint-created.txt',
          summary: 'Create checkpoint fixture',
          content: 'created after checkpoint\n'
        }
      ]
    });
    assert(applyResult.checkpoint, 'Apply response did not include a checkpoint id.');
    await expectWorkspaceFile('tracked.txt', 'after checkpoint apply\n');
    await expectWorkspaceFile('generated/checkpoint-created.txt', 'created after checkpoint\n');

    await clickUnique(page.getByRole('button', { name: 'Refresh checkpoints', exact: true }), 'checkpoint refresh button');
    const restoreAction = page.getByRole('button', {
      name: `Restore checkpoint ${applyResult.checkpoint}`,
      exact: true
    });
    await restoreAction.waitFor({ state: 'visible', timeout: 30_000 });
    page.once('dialog', async (dialog) => {
      assert(dialog.message().includes(applyResult.checkpoint), 'Restore confirmation did not include checkpoint id.');
      await dialog.accept();
    });
    await clickUnique(restoreAction, 'checkpoint restore action');
    await waitForLocatorCount(
      page.getByText('Restored 2 files from checkpoint.', { exact: true }),
      1,
      'checkpoint restore status',
      30_000
    );
    await expectWorkspaceFile('tracked.txt', 'before checkpoint apply\n');
    await expectWorkspaceFileMissing('generated/checkpoint-created.txt');

    const diagnosticsVisible = await page.getByText('Runtime Diagnostics', { exact: false }).count();
    assert(diagnosticsVisible > 0, 'Runtime Diagnostics panel was not visible after Settings opened.');
    assert(runtimeIssues.length === 0, `Browser console reported warning/error output:\n${runtimeIssues.join('\n')}`);

    await browser.close();
    browser = undefined;
    await restoreConfig(originalWorkspace);

    if (keepWorkspace) {
      console.log(`Auralith OS UI E2E passed. Workspace kept at ${workspaceRoot}`);
    } else {
      await removeE2eWorkspace(workspaceRoot);
      cleanupWorkspace = false;
      console.log('Auralith OS UI E2E passed. Temporary workspace cleaned up.');
    }
  } catch (error) {
    if (page) {
      await writeDebugArtifacts(page, error).catch((artifactError) => {
        console.error(`Could not write E2E debug artifacts: ${artifactError.message || artifactError}`);
      });
    }
    await restoreConfig(originalWorkspace);
    throw error;
  }
} catch (error) {
  if (browser) {
    await browser.close().catch(() => {});
  }
  if (cleanupWorkspace) {
    console.error(`Kept E2E workspace for debugging: ${workspaceRoot}`);
  }
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

async function restoreConfig(defaultWorkspace) {
  await apiJson('POST', '/api/config', { default_workspace: defaultWorkspace || 'workspace' });
}

async function writeDebugArtifacts(page, error) {
  await mkdir(workspaceRoot, { recursive: true });
  const screenshotPath = path.join(workspaceRoot, 'e2e-failure.png');
  const htmlPath = path.join(workspaceRoot, 'e2e-failure.html');
  const summaryPath = path.join(workspaceRoot, 'e2e-failure.txt');
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await writeFile(htmlPath, await page.content(), 'utf8');
  await writeFile(
    summaryPath,
    [
      `URL: ${page.url()}`,
      `Error: ${error instanceof Error ? error.stack || error.message : String(error)}`,
      ''
    ].join('\n'),
    'utf8'
  );
  console.error(`Wrote E2E debug artifacts to ${workspaceRoot}`);
}

async function exercisePublicWebsiteRoutes(browser) {
  const publicPage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const publicIssues = [];
  publicPage.on('console', (message) => {
    if (['warning', 'error'].includes(message.type())) {
      if (message.text().includes('Failed to load resource')) return;
      publicIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  publicPage.on('pageerror', (error) => {
    publicIssues.push(`pageerror: ${error.stack || error.message}`);
  });

  try {
    const routes = [
      { path: '/', text: 'Auralith OS' },
      { path: '/features', text: 'Built around workflows' },
      { path: '/pricing', text: 'Pricing' },
      { path: '/security', text: 'Designed for local-first control' },
      { path: '/login', text: 'Welcome back' },
      { path: '/register', text: 'Create account' }
    ];

    for (const route of routes) {
      await publicPage.goto(`${frontendUrl}${route.path}`, { waitUntil: 'domcontentloaded' });
      await waitForLocatorCount(publicPage.getByText(route.text, { exact: false }), 1, `public route ${route.path}`);
      const metrics = await publicPage.evaluate(() => {
        const root = document.documentElement;
        const body = document.body;
        return {
          innerWidth: window.innerWidth,
          scrollWidth: Math.max(root.scrollWidth, body.scrollWidth)
        };
      });
      assert(
        metrics.scrollWidth <= metrics.innerWidth + 4,
        `Public route ${route.path} overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
      );
    }

    assert(publicIssues.length === 0, `Public website console reported warning/error output:\n${publicIssues.join('\n')}`);
  } finally {
    await publicPage.close().catch(() => {});
  }
}

async function exerciseProtectedAuthGate(browser) {
  const authPage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const authIssues = [];
  authPage.on('console', (message) => {
    if (['warning', 'error'].includes(message.type())) {
      if (message.text().includes('Failed to load resource')) return;
      authIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  authPage.on('pageerror', (error) => {
    authIssues.push(`pageerror: ${error.stack || error.message}`);
  });

  try {
    await authPage.goto(`${frontendUrl}/app/tasks`, { waitUntil: 'domcontentloaded' });
    await waitForLocatorCount(authPage.getByRole('heading', { name: 'Login to Auralith OS', exact: true }), 1, 'protected route login gate');
    await waitForBrowserPath(authPage, '/login', 'protected route login redirect');
    await assertNoHorizontalOverflow(authPage, 'protected route login gate');

    await authPage.evaluate((key) => {
      localStorage.setItem(key, '{ this is not valid session json');
    }, authSessionStorageKey);
    await authPage.goto(`${frontendUrl}/app/settings`, { waitUntil: 'domcontentloaded' });
    await waitForLocatorCount(authPage.getByRole('heading', { name: 'Login to Auralith OS', exact: true }), 1, 'malformed auth login gate');
    await waitForBrowserPath(authPage, '/login', 'malformed auth redirect');
    const storedAuthSession = await authPage.evaluate((key) => localStorage.getItem(key), authSessionStorageKey);
    assert(storedAuthSession === null, 'Malformed auth session was not cleared from localStorage.');
    await assertNoHorizontalOverflow(authPage, 'malformed auth login gate');

    assert(authIssues.length === 0, `Auth gate console reported warning/error output:\n${authIssues.join('\n')}`);
  } finally {
    await authPage.close().catch(() => {});
  }
}

async function restoreWorkspaceValue(fallback) {
  const envValue = await readDotEnvValue('DEFAULT_WORKSPACE');
  const candidate = envValue || fallback || 'workspace';
  if (isTemporaryProbeWorkspace(candidate)) return 'workspace';
  return candidate;
}

async function readDotEnvValue(name) {
  try {
    const text = await readFile(path.join(root, '.env'), 'utf8');
    const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(`^\\s*${escapedName}\\s*=\\s*(.*)$`);
    for (const line of text.split(/\r?\n/)) {
      const match = line.match(pattern);
      if (match) return match[1].trim().replace(/^['"]|['"]$/g, '');
    }
  } catch {
    return '';
  }
  return '';
}

function isTemporaryProbeWorkspace(value) {
  const resolved = path.resolve(path.isAbsolute(value) ? value : path.join(root, value));
  const tmpRoot = path.resolve(root, '.tmp');
  const leaf = path.basename(resolved);
  return (
    resolved.startsWith(`${tmpRoot}${path.sep}`) &&
    /^(smoke|doctor|e2e-web)-/.test(leaf)
  );
}

async function prepareWorkspace(target) {
  await removeE2eWorkspace(target).catch(() => {});
  await mkdir(target, { recursive: true });
  await writeFile(
    path.join(target, 'package.json'),
    '\ufeff' +
      JSON.stringify({
        name: 'aegis-e2e-workspace',
        private: true,
        scripts: {
          test: 'node smoke.js'
        }
      }) +
      '\n',
    'utf8'
  );
  await writeFile(path.join(target, 'smoke.js'), "console.log('aegis browser e2e validation ok');\n", 'utf8');
  await writeFile(path.join(target, 'tracked.txt'), 'before checkpoint apply\n', 'utf8');
  await prepareAlternateProjectWorkspace(alternateProjectRoot);
}

async function prepareAlternateProjectWorkspace(target) {
  await mkdir(target, { recursive: true });
  await writeFile(path.join(target, 'alt-project.txt'), 'alternate project workspace ready\n', 'utf8');
  await writeFile(
    path.join(target, 'package.json'),
    JSON.stringify({
      name: 'aegis-alt-project',
      private: true,
      scripts: {
        test: 'node alt-smoke.js'
      }
    }) + '\n',
    'utf8'
  );
  await writeFile(path.join(target, 'alt-smoke.js'), "console.log('alternate project ok');\n", 'utf8');
}

async function removeE2eWorkspace(target) {
  const resolved = path.resolve(target);
  const tmpRoot = path.resolve(root, '.tmp');
  if (!resolved.startsWith(`${tmpRoot}${path.sep}`) || !path.basename(resolved).startsWith('e2e-web-')) {
    throw new Error(`Refusing to remove unexpected E2E directory: ${resolved}`);
  }
  await rm(resolved, { recursive: true, force: true });
}

async function clickUnique(locator, label) {
  const count = await locator.count();
  assert(count === 1, `Expected one ${label}, found ${count}.`);
  await locator.click({ timeout: 5_000 });
}

async function waitForLocatorEnabled(locator, label, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  let lastCount = 0;
  let lastEnabled = false;
  while (Date.now() < deadline) {
    lastCount = await locator.count();
    if (lastCount === 1) {
      lastEnabled = await locator.isEnabled();
      if (lastEnabled) return;
    }
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label} to become enabled. Last count: ${lastCount}; enabled: ${lastEnabled}.`);
}

async function readClipboard(page) {
  return page.evaluate(() => navigator.clipboard.readText());
}

function normalizeLineEndings(value) {
  return value.replace(/\r\n/g, '\n');
}

async function waitForLocatorCount(locator, minimum, label, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  let lastCount = 0;
  while (Date.now() < deadline) {
    lastCount = await locator.count();
    if (lastCount >= minimum) return lastCount;
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label}; expected at least ${minimum}, found ${lastCount}.`);
}

async function waitForLocatorExactCount(locator, expected, label, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  let lastCount = 0;
  while (Date.now() < deadline) {
    lastCount = await locator.count();
    if (lastCount === expected) return lastCount;
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label}; expected ${expected}, found ${lastCount}.`);
}

async function waitForLocatorText(locator, expectedText, label, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  let lastText = '';
  while (Date.now() < deadline) {
    const count = await locator.count();
    if (count === 1) {
      lastText = (await locator.textContent({ timeout: 1_000 })) || '';
      if (lastText.includes(expectedText)) return lastText;
    }
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label}; expected text ${JSON.stringify(expectedText)}, got ${JSON.stringify(lastText)}.`);
}

async function waitForBrowserPath(page, expectedPath, label, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  let lastPath = '';
  while (Date.now() < deadline) {
    lastPath = await page.evaluate(() => window.location.pathname);
    if (lastPath === expectedPath) return lastPath;
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label}; expected ${expectedPath}, got ${lastPath}.`);
}

async function assertNoHorizontalOverflow(page, label) {
  const metrics = await page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;
    return {
      innerWidth: window.innerWidth,
      scrollWidth: Math.max(root.scrollWidth, body.scrollWidth)
    };
  });
  assert(
    metrics.scrollWidth <= metrics.innerWidth + 4,
    `${label} overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
  );
}

async function waitForChatScrollAtBottom(page, label, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  let lastMetrics = null;
  while (Date.now() < deadline) {
    lastMetrics = await page.evaluate(() => {
      const scroll = document.querySelector('[data-testid="chat-scroll"]');
      if (!scroll) return null;
      return {
        clientHeight: scroll.clientHeight,
        scrollHeight: scroll.scrollHeight,
        scrollTop: scroll.scrollTop,
        bottomGap: scroll.scrollHeight - scroll.clientHeight - scroll.scrollTop
      };
    });

    if (lastMetrics && lastMetrics.scrollHeight > lastMetrics.clientHeight && lastMetrics.bottomGap <= 24) return;
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${label}; last metrics: ${JSON.stringify(lastMetrics)}.`);
}

async function apiJson(method, pathname, body) {
  const response = await fetch(`${backendUrl}${pathname}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${pathname} failed with ${response.status}: ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

async function expectWorkspaceFile(relativePath, expectedContent) {
  const response = await apiJson(
    'GET',
    `/api/file?workspace_root=${encodeURIComponent(workspaceRoot)}&path=${encodeURIComponent(relativePath)}`
  );
  assert(response.content === expectedContent, `${relativePath} content mismatch after checkpoint operation.`);
}

async function expectWorkspaceFileMissing(relativePath) {
  const response = await fetch(
    `${backendUrl}/api/file?workspace_root=${encodeURIComponent(workspaceRoot)}&path=${encodeURIComponent(relativePath)}`,
    { headers: { Accept: 'application/json' } }
  );
  assert(response.status === 404, `${relativePath} should have been removed by checkpoint restore, got ${response.status}.`);
}

async function expectWorkspacePreview(page, relativePath, expectedContent) {
  const preview = page.getByTestId('workspace-file-preview');
  await waitForLocatorCount(preview.getByText(relativePath, { exact: true }), 1, `${relativePath} workspace preview title`);
  await waitForLocatorCount(
    page.getByTestId('workspace-file-preview-content').getByText(expectedContent, { exact: false }),
    1,
    `${relativePath} workspace preview content`
  );
}

async function exerciseSavedSessionDelete(page) {
  await page.evaluate(
    ({ storageKey, workspaceRoot: storedWorkspaceRoot }) => {
      localStorage.setItem(
        storageKey,
        JSON.stringify([
          {
            id: 'thread-e2e-delete',
            title: 'Delete me saved session',
            preview: 'This saved session should be removed by the E2E flow.',
            count: 2,
            updatedAt: '2026-05-05T00:00:00.000Z',
            workspaceRoot: storedWorkspaceRoot,
            messages: [
              { role: 'user', content: 'Delete me saved session' },
              { role: 'assistant', content: 'This saved session should be removed by the E2E flow.' }
            ]
          }
        ])
      );
    },
    { storageKey: conversationStorageKey, workspaceRoot }
  );
  await page.reload({ waitUntil: 'domcontentloaded' });

  const savedSessionPill = page.getByRole('button', { name: 'Delete me saved session', exact: true });
  await savedSessionPill.waitFor({ state: 'visible', timeout: 30_000 });

  page.once('dialog', async (dialog) => {
    assert(dialog.message().includes('Delete me saved session'), 'Saved session delete confirmation named the wrong session.');
    await dialog.accept();
  });
  await clickUnique(
    page.getByRole('button', { name: 'Delete saved session Delete me saved session', exact: true }),
    'delete saved session button'
  );
  await waitForLocatorExactCount(savedSessionPill, 0, 'deleted saved session pill');
  await waitForLocatorCount(page.getByText('Saved session deleted.', { exact: true }), 1, 'saved session deleted status');

  const stillStored = await page.evaluate((storageKey) => {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return parsed.some((item) => item?.id === 'thread-e2e-delete');
  }, conversationStorageKey);
  assert(!stillStored, 'Deleted saved session was still present in local storage.');
}

async function exerciseLargeSavedSessionHistory(page) {
  await page.evaluate(
    ({ storageKey, workspaceRoot: storedWorkspaceRoot }) => {
      const sessions = Array.from({ length: 50 }, (_, index) => {
        const sequence = String(index + 1).padStart(2, '0');
        const isNeedle = index === 41;
        return {
          id: `thread-e2e-bulk-${sequence}`,
          title: isNeedle ? 'Needle session 42' : `Bulk session ${sequence}`,
          preview: isNeedle
            ? 'A uniquely searchable saved session for the stress path.'
            : `Saved stress session ${sequence}`,
          count: 2,
          updatedAt: `2026-05-05T00:${sequence}:00.000Z`,
          workspaceRoot: storedWorkspaceRoot,
          messages: [
            { role: 'user', content: isNeedle ? 'open the needle saved session' : `bulk user prompt ${sequence}` },
            {
              role: 'assistant',
              content: isNeedle
                ? 'Needle session restored successfully from long history.'
                : `bulk assistant reply ${sequence}`
            }
          ]
        };
      });
      localStorage.setItem(storageKey, JSON.stringify(sessions));
    },
    { storageKey: conversationStorageKey, workspaceRoot }
  );
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel after large saved session reload');
  const storedCount = await page.evaluate((storageKey) => {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return Array.isArray(parsed) ? parsed.length : 0;
  }, conversationStorageKey);
  assert(storedCount === 50, `Expected 50 stored saved sessions, found ${storedCount}.`);

  const metrics = await page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;
    const commandInput = document.querySelector('.aegis-command-input');
    const commandInputBox = commandInput?.getBoundingClientRect();
    return {
      innerWidth: window.innerWidth,
      scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
      commandInputVisible: Boolean(commandInputBox && commandInputBox.width > 120 && commandInputBox.height > 32)
    };
  });
  assert(
    metrics.scrollWidth <= metrics.innerWidth + 4,
    `Large saved session history overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
  );
  assert(metrics.commandInputVisible, 'Command input was not visible with a large saved session history.');

  const sessionSearch = page.getByPlaceholder('Search sessions');
  await sessionSearch.fill('Needle');
  const needleSession = page.getByRole('button', { name: 'Needle session 42', exact: true });
  await needleSession.waitFor({ state: 'visible', timeout: 30_000 });
  await waitForLocatorExactCount(page.getByRole('button', { name: 'Bulk session 01', exact: true }), 0, 'filtered bulk session');
  await clickUnique(needleSession, 'needle saved session button');
  await waitForLocatorCount(
    page.getByText('Needle session restored successfully from long history.', { exact: true }),
    1,
    'opened saved session content'
  );
  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after large history stress');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty state after large history stress');
}

async function exerciseProjectHistorySwitcher(page) {
  await page.evaluate(
    ({ storageKey, workspaceRoot: storedWorkspaceRoot, alternateRoot }) => {
      localStorage.setItem(
        storageKey,
        JSON.stringify([
          {
            id: 'thread-e2e-alt-project',
            title: 'Alternate workspace repair completed',
            preview: 'Generated a focused repair summary for the alternate project.',
            count: 2,
            updatedAt: '2026-05-05T19:10:00.000Z',
            workspaceRoot: alternateRoot,
            messages: [
              { role: 'user', content: 'Can you repair the alternate workspace?' },
              { role: 'assistant', content: 'Generated a focused repair summary for the alternate project.' }
            ]
          },
          {
            id: 'thread-e2e-main-project',
            title: 'Baseline e2e workspace notes',
            preview: 'Recorded the main workspace setup notes.',
            count: 2,
            updatedAt: '2026-05-05T18:55:00.000Z',
            workspaceRoot: storedWorkspaceRoot,
            messages: [
              { role: 'user', content: 'Keep notes for the baseline workspace.' },
              { role: 'assistant', content: 'Recorded the main workspace setup notes.' }
            ]
          }
        ])
      );
    },
    { storageKey: conversationStorageKey, workspaceRoot, alternateRoot: alternateProjectRoot }
  );
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel after project history reload');
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Open workspace file tracked.txt', exact: true }),
    1,
    'baseline workspace files before project switch'
  );

  await clickUnique(page.getByRole('button', { name: 'Projects', exact: true }), 'Projects sidebar entry');
  await waitForLocatorCount(page.getByRole('heading', { name: 'Projects', exact: true }), 1, 'Projects surface heading');

  const projectSearch = page.getByPlaceholder('Search projects or sessions', { exact: true });
  await projectSearch.waitFor({ state: 'visible', timeout: 30_000 });
  await projectSearch.fill('alternate project');
  await waitForLocatorCount(
    page.getByText('Alternate workspace repair completed', { exact: true }),
    1,
    'alternate project card title'
  );
  await waitForLocatorCount(
    page.getByText('Generated a focused repair summary for the alternate project.', { exact: false }),
    1,
    'alternate project latest session preview'
  );

  await clickUnique(
    page.getByRole('button', { name: 'Open workspace Alternate workspace repair completed', exact: true }),
    'alternate project workspace button'
  );

  const fileFilter = page.getByPlaceholder('Filter workspace files', { exact: true });
  await fileFilter.waitFor({ state: 'visible', timeout: 30_000 });
  await fileFilter.fill('alt-project');
  const alternateFile = page.getByRole('button', { name: 'Open workspace file alt-project.txt', exact: true });
  await waitForLocatorCount(alternateFile, 1, 'alternate project file button');
  await clickUnique(alternateFile, 'alternate project file button');
  await waitForLocatorCount(
    page.getByText('alternate project workspace ready', { exact: false }),
    1,
    'alternate project file preview'
  );

  await clickUnique(page.getByRole('button', { name: 'Projects', exact: true }), 'Projects sidebar entry after alternate open');
  const latestSessionButton = page.getByRole('button', { name: 'Open latest session', exact: false });
  await waitForLocatorCount(latestSessionButton, 1, 'alternate latest session button');
  await clickUnique(
    latestSessionButton,
    'alternate latest session button'
  );
  await waitForLocatorCount(
    page.getByText('Can you repair the alternate workspace?', { exact: true }),
    1,
    'alternate saved user message'
  );
  await waitForLocatorCount(
    page.getByText('Generated a focused repair summary for the alternate project.', { exact: true }),
    1,
    'alternate saved assistant message'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Open workspace file alt-project.txt', exact: true }),
    1,
    'alternate workspace files after session restore'
  );

  await clickUnique(page.getByRole('button', { name: 'Projects', exact: true }), 'Projects sidebar entry before returning');
  await page.getByPlaceholder('Search projects or sessions', { exact: true }).fill('');
  await clickUnique(
    page.getByRole('button', { name: 'Open workspace Baseline e2e workspace notes', exact: true }),
    'main project workspace button'
  );
  await fileFilter.waitFor({ state: 'visible', timeout: 30_000 });
  await fileFilter.fill('');
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Open workspace file tracked.txt', exact: true }),
    1,
    'main workspace restored tracked file'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Open workspace file tracked.txt', exact: true }),
    'main workspace restored tracked file button'
  );
  await waitForLocatorCount(
    page.getByText('before checkpoint apply', { exact: false }),
    1,
    'main workspace tracked file preview after project switch'
  );
}

async function exerciseCustomAgentEditor(page) {
  await page.evaluate((storageKey) => localStorage.removeItem(storageKey), customAgentsStorageKey);

  await clickUnique(page.getByRole('button', { name: 'Agents', exact: true }), 'Agents sidebar entry');
  await waitForLocatorCount(page.getByRole('heading', { name: 'Agents', exact: true }), 1, 'Agents surface heading');

  await page.getByLabel('Agent name', { exact: true }).fill('E2E Security Reviewer');
  await page
    .getByLabel('Agent perspective', { exact: true })
    .fill('Reviews workspace changes with a strict security and regression perspective.');
  await page
    .getByLabel('Agent mission', { exact: true })
    .fill('Review generated changes, require proof, and keep fixes tightly scoped.');
  await page.getByLabel('Agent mode', { exact: true }).selectOption('review');

  await clickUnique(page.getByRole('button', { name: 'Create and activate', exact: true }), 'create custom agent button');
  await waitForLocatorCount(page.getByText('E2E Security Reviewer is active.', { exact: true }), 1, 'created agent active status');
  await waitForLocatorCount(page.getByText('E2E Security Reviewer', { exact: true }), 2, 'created agent visible in current and saved sections');

  const createdAgents = await page.evaluate((storageKey) => JSON.parse(localStorage.getItem(storageKey) || '[]'), customAgentsStorageKey);
  assert(createdAgents.length === 1, `Expected one saved custom agent after create, got ${createdAgents.length}.`);
  assert(createdAgents[0].name === 'E2E Security Reviewer', 'Saved custom agent did not use the created name.');

  await page.getByPlaceholder('Search agents', { exact: true }).fill('security');
  await waitForLocatorCount(page.getByText('Reviews workspace changes with a strict security', { exact: false }), 1, 'agent search keeps matching agent visible');
  await page.getByPlaceholder('Search agents', { exact: true }).fill('');

  await clickUnique(page.getByRole('button', { name: 'Edit agent E2E Security Reviewer', exact: true }), 'edit custom agent button');
  await waitForLocatorCount(page.getByRole('heading', { name: 'Edit Agent', exact: true }), 1, 'agent form entered edit mode');
  await page.getByLabel('Agent name', { exact: true }).fill('E2E Security Reviewer Updated');
  await page
    .getByLabel('Agent perspective', { exact: true })
    .fill('Reviews security boundaries, generated diffs, and validation gaps before code is accepted.');
  await page
    .getByLabel('Agent mission', { exact: true })
    .fill('Block risky changes, ask for proof, and only approve fixes that survive behavioral tests.');
  await clickUnique(page.getByRole('button', { name: 'Save and activate', exact: true }), 'save edited custom agent button');
  await waitForLocatorCount(
    page.getByText('E2E Security Reviewer Updated is active.', { exact: true }),
    1,
    'edited agent active status'
  );
  await waitForLocatorCount(page.getByText('Block risky changes, ask for proof', { exact: false }), 1, 'edited mission visible');

  const updatedAgents = await page.evaluate((storageKey) => JSON.parse(localStorage.getItem(storageKey) || '[]'), customAgentsStorageKey);
  assert(updatedAgents.length === 1, `Expected edit to update one custom agent instead of duplicating it, got ${updatedAgents.length}.`);
  assert(updatedAgents[0].name === 'E2E Security Reviewer Updated', 'Edited custom agent name was not persisted.');

  const updatedConfig = await apiJson('GET', '/api/config');
  assert(updatedConfig.assistant_name === 'E2E Security Reviewer Updated', 'Edited custom agent was not saved as active backend config.');
  assert(updatedConfig.default_mode === 'review', 'Edited custom agent did not keep review mode active.');

  await clickUnique(page.getByRole('button', { name: 'Use Auralith Prime', exact: true }), 'restore default agent button');
  await waitForLocatorCount(page.getByText('Auralith Prime is active.', { exact: true }), 1, 'default agent restored status');
  await waitForLocatorCount(page.getByText('Auralith Prime', { exact: true }), 1, 'default agent visible after restore');
  const restoredConfig = await apiJson('GET', '/api/config');
  assert(restoredConfig.assistant_name === 'Auralith Prime', 'Default agent restore did not update backend config.');
  assert(restoredConfig.default_mode === 'build', 'Default agent restore did not return to build mode.');
}

async function exerciseHeaderModelSwitcher(page) {
  let activeModel = 'qwen2.5-coder:7b';
  let configSaves = 0;

  const modelEndpoint = 'http://127.0.0.1:11434';
  const catalogModels = [
    {
      provider_id: 'ollama-qwen',
      label: 'Ollama Local',
      api: 'ollama',
      endpoint: modelEndpoint,
      name: 'qwen2.5-coder:7b',
      local: true,
      enabled: true,
      installed: true,
      configured: true,
      pullable: false,
      health: 'available',
      roles: ['code', 'debug'],
      capabilities: ['chat', 'code', 'debug', 'streaming'],
      size_bytes: 4_700_000_000,
      modified_at: '2026-05-05T00:00:00.000Z',
      estimated_pull_bytes: null,
      notes: 'Installed local coding model'
    },
    {
      provider_id: 'ollama-phi',
      label: 'Ollama Local',
      api: 'ollama',
      endpoint: modelEndpoint,
      name: 'phi4-mini:latest',
      local: true,
      enabled: true,
      installed: true,
      configured: true,
      pullable: false,
      health: 'available',
      roles: ['chat', 'reasoning'],
      capabilities: ['chat', 'code', 'reasoning', 'streaming'],
      size_bytes: 3_100_000_000,
      modified_at: '2026-05-05T00:00:00.000Z',
      estimated_pull_bytes: null,
      notes: 'Installed local reasoning model'
    }
  ];

  const modelCapabilities = {
    chat: true,
    code: true,
    debug: true,
    refactor: true,
    reasoning: true,
    research: false,
    streaming: true,
    structured_json: true,
    tools: false,
    vision: false,
    audio: false,
    embeddings: false,
    image: false,
    video: false,
    realtime: false,
    judge: false,
    computer_use: false
  };

  function activeConfig() {
    return {
      assistant_name: 'Auralith Prime',
      assistant_mission: 'A local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution.',
      default_mode: 'build',
      modes: [
        { id: 'build', label: 'Build', description: 'Build and repair from chat prompts.' },
        { id: 'chat', label: 'Chat', description: 'Answer questions without changing files.' }
      ],
      default_workspace: workspaceRoot,
      engine: `Aegis Core / ${activeModel}`,
      engine_ready: true,
      engine_message: 'ready',
      model_name: activeModel,
      model_endpoint: modelEndpoint,
      model_api: 'ollama',
      model_ready: true,
      model_message: `${activeModel} is reachable.`,
      database_path: path.join(root, 'backend', 'data', 'aegis.sqlite3'),
      command_allowlist: 'python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet',
      command_timeout_seconds: 120,
      auto_run_validation: false,
      shared_workspace_mode: true,
      feedback_capture_excerpts: false,
      feedback_redaction_enabled: true,
      feedback_max_excerpt_chars: 600,
      feedback_hash_content: true,
      env_exists: true
    };
  }

  function managedModel(item) {
    return {
      ...item,
      active: item.name === activeModel
    };
  }

  await page.route(`${backendUrl}/api/models`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        active_model: activeModel,
        active_api: 'ollama',
        active_endpoint: modelEndpoint,
        router_enabled: true,
        fallback_supported: true,
        message: 'Loaded 2 local Ollama models for the header switcher.',
        models: catalogModels.map((item) => ({
          id: item.provider_id,
          name: item.name,
          provider: item.label,
          api: item.api,
          endpoint: item.endpoint,
          local: item.local,
          configured: item.name === activeModel,
          available: item.installed,
          ready: true,
          message: item.notes,
          size: item.size_bytes,
          modified_at: item.modified_at,
          capabilities: modelCapabilities
        }))
      })
    });
  });

  await page.route(`${backendUrl}/api/model-manager`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        ok: true,
        message: '2 installed local models are ready.',
        disk: {
          drive_root: root,
          project_root: root,
          model_store_path: path.join(root, '.tmp', 'models'),
          total_bytes: 100_000_000_000,
          used_bytes: 40_000_000_000,
          free_bytes: 60_000_000_000,
          model_store_bytes: 8_000_000_000,
          free_percent: 60,
          low_space: false,
          minimum_free_bytes: 24_000_000_000
        },
        active_model: activeModel,
        active_provider_id: catalogModels.find((item) => item.name === activeModel)?.provider_id || 'ollama-qwen',
        providers_total: 2,
        local_total: 2,
        installed_total: 2,
        pullable_total: 0,
        cloud_total: 0,
        models: catalogModels.map(managedModel),
        operations: [],
        pull_logs: []
      })
    });
  });

  await page.route(`${backendUrl}/api/model-registry`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        version: 1,
        active_provider_id: catalogModels.find((item) => item.name === activeModel)?.provider_id || 'ollama-qwen',
        active_model: activeModel,
        router_enabled: true,
        fallback_supported: true,
        message: 'Mock model registry loaded.',
        providers: [],
        roles: [],
        presets: []
      })
    });
  });

  await page.route(`${backendUrl}/api/config`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }

    const payload = route.request().postDataJSON();
    activeModel = payload.model_name || activeModel;
    configSaves += 1;
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(activeConfig())
    });
  });

  const modelButton = page.getByRole('button', { name: 'Open model switcher', exact: true });
  await modelButton.waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await clickUnique(modelButton, 'header model switcher button');
  const menu = page.getByTestId('model-switcher-menu');
  await waitForLocatorCount(menu, 1, 'header model switcher menu');
  await waitForLocatorCount(menu.getByText('2 installed / 2 available', { exact: true }), 1, 'header model counts');
  await waitForLocatorCount(page.getByTestId('quick-model-phi4-mini:latest'), 1, 'alternate quick model row');

  await clickUnique(page.getByRole('button', { name: 'Use model phi4-mini:latest', exact: true }), 'use alternate header model');
  await waitForLocatorExactCount(menu, 0, 'header model switcher closes after activation');
  await waitForLocatorText(modelButton, 'phi4-mini:latest', 'header model button updates after activation');

  await clickUnique(modelButton, 'reopen header model switcher after activation');
  await waitForLocatorCount(page.getByRole('button', { name: 'Active model phi4-mini:latest', exact: true }), 1, 'new active model row');
  await clickUnique(page.getByRole('button', { name: 'Model settings', exact: true }), 'header model settings shortcut');
  await waitForLocatorCount(page.getByRole('heading', { name: 'Model Selection', exact: true }), 1, 'model settings opened from header');
  await clickUnique(page.getByRole('button', { name: 'Close settings', exact: true }), 'close model settings after header shortcut');

  await clickUnique(modelButton, 'reopen header model switcher to restore original model');
  await clickUnique(page.getByRole('button', { name: 'Use model qwen2.5-coder:7b', exact: true }), 'restore original header model');
  await waitForLocatorText(modelButton, 'qwen2.5-coder:7b', 'header model restored after quick switcher test');

  assert(configSaves === 2, `Expected two mocked model config saves, got ${configSaves}.`);
  await page.unroute(`${backendUrl}/api/models`);
  await page.unroute(`${backendUrl}/api/model-manager`);
  await page.unroute(`${backendUrl}/api/model-registry`);
  await page.unroute(`${backendUrl}/api/config`);
}

async function exerciseWorkspaceFileFilter(page) {
  const filterInput = page.getByPlaceholder('Filter workspace files', { exact: true });
  await filterInput.waitFor({ state: 'visible', timeout: 30_000 });

  const packageFile = page.getByRole('button', { name: 'Open workspace file package.json', exact: true });
  const trackedFile = page.getByRole('button', { name: 'Open workspace file tracked.txt', exact: true });
  await trackedFile.waitFor({ state: 'visible', timeout: 30_000 });
  assert((await packageFile.count()) >= 1, 'Expected package.json before applying the file filter.');

  await filterInput.fill('tracked');
  await waitForLocatorExactCount(packageFile, 0, 'package.json hidden by workspace file filter');
  await waitForLocatorCount(trackedFile, 1, 'tracked.txt visible after workspace file filter');
  await clickUnique(trackedFile, 'filtered tracked.txt file button');
  await waitForLocatorCount(
    page.getByText('before checkpoint apply', { exact: false }),
    1,
    'filtered tracked.txt preview content'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Copy workspace file path tracked.txt', exact: true }),
    'copy workspace file path button'
  );
  await waitForLocatorCount(
    page.getByText('Copied workspace file path to clipboard.', { exact: true }),
    1,
    'copy workspace path status'
  );
  assert(
    (await readClipboard(page)) === 'tracked.txt',
    'Copy workspace path did not place the selected workspace file path on the clipboard.'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Copy workspace file content tracked.txt', exact: true }),
    'copy workspace file content button'
  );
  await waitForLocatorCount(
    page.getByText('Copied workspace file content to clipboard.', { exact: true }),
    1,
    'copy workspace content status'
  );
  const copiedWorkspaceContent = await readClipboard(page);
  assert(
    normalizeLineEndings(copiedWorkspaceContent) === 'before checkpoint apply\n',
    `Copy workspace content did not place the selected workspace file content on the clipboard. Got ${JSON.stringify(copiedWorkspaceContent)}.`
  );

  await filterInput.fill('');
  await waitForLocatorCount(packageFile, 1, 'package.json visible after clearing workspace file filter');
}

async function exerciseDetailsPanelCollapse(page) {
  const fileFilter = page.getByPlaceholder('Filter workspace files', { exact: true });
  await waitForLocatorCount(fileFilter, 1, 'workspace file filter before collapsing panel');
  await waitForLocatorCount(page.getByTestId('workspace-file-preview'), 1, 'workspace preview before collapsing panel');

  await clickUnique(page.getByRole('button', { name: 'Collapse Workspace panel', exact: true }), 'collapse workspace panel');
  await waitForLocatorExactCount(fileFilter, 0, 'workspace file filter hidden after collapse');
  await waitForLocatorExactCount(page.getByTestId('workspace-panel-body'), 0, 'workspace panel body hidden after collapse');

  const collapsedSections = await page.evaluate(
    (storageKey) => JSON.parse(localStorage.getItem(storageKey) || '[]'),
    detailPanelSectionsStorageKey
  );
  assert(collapsedSections.includes('workspace'), 'Collapsed workspace panel was not saved to local storage.');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel after workspace collapse reload');
  await waitForLocatorExactCount(fileFilter, 0, 'workspace file filter still hidden after collapse reload');
  await waitForLocatorExactCount(
    page.getByTestId('workspace-panel-body'),
    0,
    'workspace panel body still hidden after collapse reload'
  );

  await clickUnique(page.getByRole('button', { name: 'Expand Workspace panel', exact: true }), 'expand workspace panel');
  await waitForLocatorCount(fileFilter, 1, 'workspace file filter visible after expand');
  await waitForLocatorCount(page.getByTestId('workspace-file-preview'), 1, 'workspace preview restored after expand');

  const expandedSections = await page.evaluate(
    (storageKey) => JSON.parse(localStorage.getItem(storageKey) || '[]'),
    detailPanelSectionsStorageKey
  );
  assert(!expandedSections.includes('workspace'), 'Expanded workspace panel was still saved as collapsed.');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel after workspace expand reload');
  await waitForLocatorCount(fileFilter, 1, 'workspace file filter still visible after expand reload');
  await waitForLocatorCount(page.getByTestId('workspace-file-preview'), 1, 'workspace preview restored after expand reload');
  await waitForLocatorCount(
    page.getByText('before checkpoint apply', { exact: false }),
    1,
    'workspace preview content preserved after collapse expand reload'
  );
}

async function exerciseDetailsPanelVisibilityPreference(page) {
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel before hiding');
  await clickUnique(page.getByRole('button', { name: 'Hide details panel', exact: true }), 'hide details panel');
  await waitForLocatorExactCount(page.getByTestId('details-panel'), 0, 'details panel hidden');

  const hiddenPreference = await page.evaluate(
    (storageKey) => JSON.parse(localStorage.getItem(storageKey) || 'true'),
    detailsPanelVisibleStorageKey
  );
  assert(hiddenPreference === false, 'Hidden details panel preference was not saved.');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorExactCount(page.getByTestId('details-panel'), 0, 'details panel stays hidden after reload');

  await clickUnique(page.getByRole('button', { name: 'Show details panel', exact: true }), 'show details panel');
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel visible after showing');

  const visiblePreference = await page.evaluate(
    (storageKey) => JSON.parse(localStorage.getItem(storageKey) || 'false'),
    detailsPanelVisibleStorageKey
  );
  assert(visiblePreference === true, 'Visible details panel preference was not saved.');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel stays visible after reload');
  await waitForLocatorCount(page.getByTestId('workspace-file-preview'), 1, 'workspace preview after details panel restore');
}

async function exercisePinnedContextFiles(page) {
  let pinnedRequestPayload = null;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    pinnedRequestPayload = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: 'e2e-pinned-context',
            reply: 'Pinned context complete.',
            context_files: [{ path: 'tracked.txt', size: 24, kind: 'text' }]
          })
        })}`
      ].join('\n')
    });
  });

  await clickUnique(
    page.getByRole('button', { name: 'Pin tracked.txt to next prompt', exact: true }),
    'pin tracked.txt to next prompt button'
  );
  await waitForLocatorCount(page.getByLabel('Pinned context files'), 1, 'pinned context files bar');
  await waitForLocatorCount(page.getByText('tracked.txt', { exact: true }), 1, 'tracked.txt pinned context chip');

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill('summarize the pinned context file');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send pinned context prompt button');
  await waitForLocatorCount(
    page.getByTestId('chat-scroll').getByText('Pinned context complete.', { exact: true }),
    1,
    'pinned context final chat response'
  );
  await waitForLocatorExactCount(page.getByLabel('Pinned context files'), 0, 'pinned context cleared after send');

  assert(pinnedRequestPayload, 'Pinned context chat request was not captured.');
  assert(
    Array.isArray(pinnedRequestPayload.context_paths) && pinnedRequestPayload.context_paths.includes('tracked.txt'),
    `Expected pinned context_paths to include tracked.txt, got ${JSON.stringify(pinnedRequestPayload.context_paths)}.`
  );
  await page.unroute(`${backendUrl}/api/chat/stream`);

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after pinned context test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after pinned context test');
}

async function exerciseGeneratedChangeApplyScopes(page) {
  let applyScopeRequests = 0;
  const repairRequestPayloads = [];
  let manualApplyValidationRequests = 0;
  const applyScopeChanges = [
    {
      action: 'create',
      path: 'generated/selected-only.txt',
      summary: 'Selected apply fixture',
      content: 'selected change applied\n'
    },
    {
      action: 'create',
      path: 'generated/apply-all-only.txt',
      summary: 'Apply all fixture',
      content: 'all change applied\n'
    }
  ];
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    applyScopeRequests += 1;
    const payload = JSON.parse(route.request().postData() || '{}');
    const message = String(payload.message || '');
    const isRepairRequest =
      message.includes('Please repair the failed validation from the last generated changes.') ||
      message.includes('Please continue repairing this validation failure.');
    if (isRepairRequest) {
      repairRequestPayloads.push(payload);
    }
    const repairAttempt = repairRequestPayloads.length;
    const repairPassed = isRepairRequest && repairAttempt > 1;

    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: isRepairRequest ? 'e2e-repair-request-test' : 'e2e-apply-scope-test',
            reply: isRepairRequest
              ? repairPassed
                ? 'Follow-up repair request received.'
                : 'Repair attempt needs another pass.'
              : 'Generated apply scope fixtures.',
            changes: applyScopeChanges,
            applied: isRepairRequest ? ['create: generated/selected-only.txt'] : [],
            events: isRepairRequest
              ? [
                  {
                    kind: 'validation',
                    title: 'Repair validation complete',
                    status: repairPassed ? 'ok' : 'error',
                    detail: repairPassed ? 'Repair validation passed.' : 'Repair validation still failing.',
                    payload: {},
                    created_at: '2026-05-05T00:00:00.000Z'
                  }
                ]
              : [],
            validation: isRepairRequest
              ? {
                  command: 'npm run test',
                  cwd: workspaceRoot,
                  allowed: true,
                  exit_code: repairPassed ? 0 : 2,
                  stdout: repairPassed ? 'repair validation ok' : 'repair validation failed',
                  stderr: repairPassed ? '' : 'follow-up assertion is still missing',
                  timed_out: false,
                  reason: repairPassed ? '' : 'Type check failed.',
                  category: 'test',
                  summary: repairPassed ? 'Repair validation passed.' : 'Repair validation still failing.'
                }
              : null,
            validation_profile: isRepairRequest
              ? {
                  command: 'npm run test',
                  label: 'npm run test',
                  source: 'e2e',
                  updated_at: '2026-05-05T00:00:00.000Z',
                  notes: ''
                }
              : null
          })
        })}`
      ].join('\n')
    });
  });
  await page.route(`${backendUrl}/api/validate`, async (route) => {
    manualApplyValidationRequests += 1;
    const validationFailed = manualApplyValidationRequests === 1;
    const validationSummary = validationFailed ? 'Manual apply validation failed.' : 'Manual apply validation passed.';
    const payload = JSON.parse(route.request().postData() || '{}');
    assert(
      payload.workspace_root === workspaceRoot,
      `Manual apply validation used the wrong workspace root: ${JSON.stringify(payload)}.`
    );
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify({
        task_id: `e2e-manual-apply-validation-${manualApplyValidationRequests}`,
        workspace_root: workspaceRoot,
        events: [
          {
            kind: 'validation',
            title: 'Validation complete',
            status: validationFailed ? 'error' : 'ok',
            detail: validationSummary,
            payload: {
              command: 'npm run test',
              cwd: workspaceRoot,
              allowed: true,
              exit_code: validationFailed ? 1 : 0,
              stdout: validationFailed ? 'manual apply validation failed' : 'manual apply validation ok',
              stderr: validationFailed ? 'selected generated fixture is missing a required assertion' : '',
              timed_out: false,
              reason: validationFailed ? 'Tests failed.' : '',
              category: 'test',
              summary: validationSummary,
              build_log_path: '.aegis/build_logs/e2e-validation.md'
            },
            created_at: '2026-05-05T00:00:00.000Z'
          },
          ...Array.from({ length: 8 }, (_, index) => ({
            kind: 'workspace',
            title: `Extra activity ${index + 1}`,
            status: 'ok',
            detail: `Additional activity event ${index + 1}`,
            payload: { index: index + 1 },
            created_at: `2026-05-05T00:00:0${index + 1}.000Z`
          }))
        ],
        validation: {
          command: 'npm run test',
          cwd: workspaceRoot,
          allowed: true,
          exit_code: validationFailed ? 1 : 0,
          stdout: validationFailed ? 'manual apply validation failed' : 'manual apply validation ok',
          stderr: validationFailed ? 'selected generated fixture is missing a required assertion' : '',
          timed_out: false,
          reason: validationFailed ? 'Tests failed.' : '',
          category: 'test',
          summary: validationSummary
        },
        validation_profile: {
          command: 'npm run test',
          label: 'npm run test',
          source: 'e2e',
          updated_at: '2026-05-05T00:00:00.000Z',
          notes: ''
        },
        warnings: []
      })
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByLabel('Apply changes automatically', { exact: true }).uncheck();
  const runValidationToggle = page.getByLabel('Run validation', { exact: true });
  await runValidationToggle.check();
  await composer.fill('generate two apply scope fixture files');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send apply scope prompt button');
  await waitForLocatorCount(page.getByText('Generated apply scope fixtures.', { exact: true }), 1, 'apply scope final response');

  await clickUnique(
    page.getByRole('button', { name: 'Copy generated change path generated/selected-only.txt', exact: true }),
    'copy selected generated change path button'
  );
  await waitForLocatorCount(
    page.getByText('Copied generated file path to clipboard.', { exact: true }),
    1,
    'copy generated path status'
  );
  assert(
    (await readClipboard(page)) === 'generated/selected-only.txt',
    'Copy generated path did not place the selected generated file path on the clipboard.'
  );

  await clickUnique(
    page.getByRole('button', { name: 'Copy generated change content generated/selected-only.txt', exact: true }),
    'copy selected generated change content button'
  );
  await waitForLocatorCount(
    page.getByText('Copied generated file content to clipboard.', { exact: true }),
    1,
    'copy generated content status'
  );
  const copiedGeneratedContent = await readClipboard(page);
  assert(
    normalizeLineEndings(copiedGeneratedContent) === 'selected change applied\n',
    `Copy generated content did not place the selected generated file content on the clipboard. Got ${JSON.stringify(copiedGeneratedContent)}.`
  );

  const copyGeneratedDiffButton = page.getByRole('button', {
    name: 'Copy generated change diff generated/selected-only.txt',
    exact: true
  });
  await waitForLocatorEnabled(copyGeneratedDiffButton, 'copy selected generated change diff button');
  await clickUnique(copyGeneratedDiffButton, 'copy selected generated change diff button');
  await waitForLocatorCount(
    page.getByText('Copied generated diff to clipboard.', { exact: true }),
    1,
    'copy generated diff status'
  );
  const copiedGeneratedDiff = normalizeLineEndings(await readClipboard(page));
  assert(
    copiedGeneratedDiff.includes('--- /dev/null') &&
      copiedGeneratedDiff.includes('+++ b/generated/selected-only.txt') &&
      copiedGeneratedDiff.includes('+selected change applied'),
    `Copy generated diff did not place the expected patch on the clipboard. Got ${JSON.stringify(copiedGeneratedDiff)}.`
  );

  await clickUnique(
    page.getByRole('button', { name: 'Apply selected generated change generated/selected-only.txt', exact: true }),
    'apply selected generated change button'
  );
  await waitForLocatorCount(
    page.getByText('Applied 1 selected change. Validation finished with exit code 1.', { exact: true }),
    1,
    'selected apply failed validation status'
  );
  await waitForLocatorCount(
    page.getByText('Validation checked 1 selected generated change.', { exact: true }),
    1,
    'validation generated change context summary'
  );
  await waitForLocatorCount(page.getByTestId('activity-event-0'), 1, 'activity event with validation payload');
  await clickUnique(
    page.getByRole('button', { name: 'Show activity details Validation complete', exact: true }),
    'show validation activity details'
  );
  const activityDetails = page.getByTestId('activity-event-details-0');
  await waitForLocatorCount(activityDetails.getByText('npm run test', { exact: true }), 1, 'activity command detail');
  await waitForLocatorCount(activityDetails.getByText(workspaceRoot, { exact: true }), 1, 'activity cwd detail');
  await waitForLocatorCount(activityDetails.getByText('selected generated fixture is missing a required assertion', { exact: false }), 1, 'activity stderr detail');
  await waitForLocatorCount(activityDetails.getByText('manual apply validation failed', { exact: false }), 1, 'activity stdout detail');
  await clickUnique(
    page.getByRole('button', { name: 'Hide activity details Validation complete', exact: true }),
    'hide validation activity details'
  );
  await waitForLocatorExactCount(page.getByTestId('activity-event-details-0'), 0, 'activity details collapsed after hide');
  await waitForLocatorExactCount(page.getByTestId('activity-event-7'), 0, 'activity logs are clipped before full log view');
  await clickUnique(page.getByRole('button', { name: 'View full activity logs', exact: true }), 'view full activity logs');
  await waitForLocatorCount(page.getByTestId('activity-event-8').getByText('Extra activity 8', { exact: true }), 1, 'full activity log final row');
  await clickUnique(page.getByRole('button', { name: 'Show latest activity logs', exact: true }), 'show latest activity logs');
  await waitForLocatorExactCount(page.getByTestId('activity-event-7'), 0, 'activity logs clipped again after showing latest');
  await clickUnique(
    page.getByRole('button', { name: 'Show issue activity events', exact: true }),
    'filter issue activity events'
  );
  await waitForLocatorCount(
    page.getByTestId('activity-event-0').getByText('Validation complete', { exact: true }),
    1,
    'issue activity shows validation failure'
  );
  await waitForLocatorExactCount(
    page.getByTestId('activity-event-1'),
    0,
    'issue activity hides ok workspace event'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Show command activity events', exact: true }),
    'filter command activity events'
  );
  await waitForLocatorCount(
    page.getByTestId('activity-event-0').getByText('Validation complete', { exact: true }),
    1,
    'command activity shows validation command'
  );
  await waitForLocatorExactCount(
    page.getByTestId('activity-event-1'),
    0,
    'command activity hides non-command event'
  );
  await clickUnique(page.getByRole('button', { name: 'Show all activity events', exact: true }), 'filter all activity events');
  await waitForLocatorCount(
    page.getByTestId('activity-event-1').getByText('Extra activity 1', { exact: true }),
    1,
    'all activity restores ok workspace event'
  );
  await clickUnique(
    page.getByTestId('generated-change-create:generated/apply-all-only.txt'),
    'select other generated change before validation review'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Copy generated change path generated/apply-all-only.txt', exact: true }),
    1,
    'other generated change selected before validation review'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Review generated change generated/selected-only.txt', exact: true }),
    'review failed validation generated change button'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Copy generated change path generated/selected-only.txt', exact: true }),
    1,
    'failed validation review selected generated change'
  );
  await waitForLocatorCount(
    page.getByText('Reviewing validation target generated/selected-only.txt.', { exact: true }),
    1,
    'failed validation review status'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Copy validation output npm run test', exact: true }),
    'copy manual apply validation output button'
  );
  await waitForLocatorCount(
    page.getByText('Copied validation output to clipboard.', { exact: true }),
    1,
    'copy validation output status'
  );
  const copiedValidationOutput = normalizeLineEndings(await readClipboard(page));
  assert(
    copiedValidationOutput.includes('Validated changes: 1') &&
      copiedValidationOutput.includes('- create: generated/selected-only.txt') &&
      copiedValidationOutput.includes('Command: npm run test') &&
      copiedValidationOutput.includes(`CWD: ${workspaceRoot}`) &&
      copiedValidationOutput.includes('Exit code: 1') &&
      copiedValidationOutput.includes('Summary: Manual apply validation failed.') &&
      copiedValidationOutput.includes('Reason: Tests failed.') &&
      copiedValidationOutput.includes('Stdout:\nmanual apply validation failed') &&
      copiedValidationOutput.includes('Stderr:\nselected generated fixture is missing a required assertion'),
    `Copy validation output did not place the expected validation details on the clipboard. Got ${JSON.stringify(copiedValidationOutput)}.`
  );
  await clickUnique(
    page.getByRole('button', { name: 'Draft repair prompt for npm run test', exact: true }),
    'draft repair prompt from failed validation button'
  );
  await waitForLocatorCount(
    page.getByText('Drafted repair prompt with 1 validation target pinned.', { exact: true }),
    1,
    'draft repair prompt status'
  );
  await waitForLocatorCount(page.getByLabel('Pinned context files'), 1, 'repair prompt pinned context bar');
  await waitForLocatorCount(
    page.getByLabel('Pinned context files').getByText('generated/selected-only.txt', { exact: true }),
    1,
    'repair prompt pinned generated file'
  );
  const repairDraft = normalizeLineEndings(await composer.inputValue());
  assert(
    repairDraft.includes('Please repair the failed validation from the last generated changes.') &&
      repairDraft.includes('- create: generated/selected-only.txt') &&
      repairDraft.includes('Command: npm run test') &&
      repairDraft.includes('Exit code: 1') &&
      repairDraft.includes('Summary: Manual apply validation failed.') &&
      repairDraft.includes('Reason: Tests failed.') &&
      repairDraft.includes('Output:\nselected generated fixture is missing a required assertion') &&
      repairDraft.includes('manual apply validation failed'),
    `Draft repair prompt did not include the expected validation repair context. Got ${JSON.stringify(repairDraft)}.`
  );
  await clickUnique(
    page.getByRole('button', { name: 'Send repair prompt for npm run test', exact: true }),
    'send repair prompt from failed validation button'
  );
  await waitForLocatorCount(
    page.getByText('Repair attempt needs another pass.', { exact: true }),
    1,
    'failed repair request final response'
  );
  await waitForLocatorExactCount(page.getByLabel('Pinned context files'), 0, 'repair context cleared after send');
  const repairTrail = page.getByTestId('validation-repair-trail');
  await waitForLocatorCount(repairTrail, 1, 'validation repair trail');
  const repairSearchInput = page.getByLabel('Search repair requests', { exact: true });
  await waitForLocatorCount(repairSearchInput, 1, 'repair request search input');
  await repairSearchInput.fill('selected-only');
  await waitForLocatorCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 1, 'searched repair trail row');
  await repairSearchInput.fill('does-not-match-repairs');
  await waitForLocatorExactCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 0, 'filtered-out repair trail row');
  await waitForLocatorCount(
    repairTrail.getByText('No repair requests match this filter.', { exact: true }),
    1,
    'empty repair trail search result'
  );
  await clickUnique(page.getByRole('button', { name: 'Clear repair request search', exact: true }), 'clear repair request search button');
  await waitForLocatorCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 1, 'repair row after clearing search');
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Show passed repair requests', exact: true }),
    'passed repair status filter button'
  );
  await waitForLocatorExactCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 0, 'failed repair hidden by passed filter');
  await waitForLocatorCount(
    repairTrail.getByText('No repair requests match this filter.', { exact: true }),
    1,
    'empty repair trail status result'
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Show failed repair requests', exact: true }),
    'failed repair status filter button'
  );
  await waitForLocatorCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 1, 'failed repair trail title');
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Show all repair requests', exact: true }),
    'all repair status filter button'
  );
  await waitForLocatorCount(repairTrail.getByText('npm run test / Failed', { exact: true }), 1, 'failed repair trail title after all filter');
  await waitForLocatorCount(
    repairTrail.getByText('Failed validation: exit 1 / Manual apply validation failed.', { exact: true }),
    1,
    'repair trail failed source'
  );
  await waitForLocatorCount(
    repairTrail.getByText('Reason: Tests failed.', { exact: true }),
    1,
    'repair trail failed reason'
  );
  await waitForLocatorCount(
    repairTrail.getByRole('button', { name: 'Review repair target generated/selected-only.txt', exact: true }),
    1,
    'repair trail review target button'
  );
  await waitForLocatorCount(
    repairTrail.getByText('Follow-up: exit 2 / Repair validation still failing.', { exact: true }),
    1,
    'repair trail failed follow-up'
  );
  await waitForLocatorCount(
    repairTrail.getByRole('button', { name: 'Draft follow-up repair prompt npm run test', exact: true }),
    1,
    'draft failed repair follow-up button'
  );
  await waitForLocatorCount(
    repairTrail.getByRole('button', { name: 'Send follow-up repair prompt npm run test', exact: true }),
    1,
    'send failed repair follow-up button'
  );
  await clickUnique(
    page.getByTestId('generated-change-create:generated/apply-all-only.txt'),
    'select other generated change before repair target review'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Copy generated change path generated/apply-all-only.txt', exact: true }),
    1,
    'other generated change selected before repair target review'
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Review repair target generated/selected-only.txt', exact: true }),
    'review repair trail generated change button'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Copy generated change path generated/selected-only.txt', exact: true }),
    1,
    'repair target review selected generated change'
  );
  await waitForLocatorCount(
    page.getByText('Reviewing repair target generated/selected-only.txt.', { exact: true }),
    1,
    'repair target review status'
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Copy repair target files npm run test', exact: true }),
    'copy repair trail targets button'
  );
  await waitForLocatorCount(
    page.getByText('Copied repair target files to clipboard.', { exact: true }),
    1,
    'copy repair trail targets status'
  );
  const copiedRepairTargets = normalizeLineEndings(await readClipboard(page));
  assert(
    copiedRepairTargets === 'generated/selected-only.txt\n',
    `Repair target copy did not match expected target list. Got ${JSON.stringify(copiedRepairTargets)}.`
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Copy repair brief npm run test', exact: true }),
    'copy failed repair brief button'
  );
  await waitForLocatorCount(
    page.getByText('Copied repair brief to clipboard.', { exact: true }),
    1,
    'copy failed repair brief status'
  );
  const copiedRepairBrief = normalizeLineEndings(await readClipboard(page));
  assert(
    copiedRepairBrief.includes('Validation repair brief') &&
      copiedRepairBrief.includes('Status: Failed') &&
      copiedRepairBrief.includes('Command: npm run test') &&
      copiedRepairBrief.includes('Source validation: exit 1 / Manual apply validation failed.') &&
      copiedRepairBrief.includes('Source reason: Tests failed.') &&
      copiedRepairBrief.includes('Targets:\n- create: generated/selected-only.txt') &&
      copiedRepairBrief.includes('Follow-up validation: exit 2 / Repair validation still failing.') &&
      copiedRepairBrief.includes('Response task: e2e-repair-request-test') &&
      copiedRepairBrief.includes('Repair prompt:\nPlease repair the failed validation from the last generated changes.') &&
      copiedRepairBrief.includes('Next follow-up prompt:\nPlease continue repairing this validation failure.'),
    `Repair brief copy did not include the expected failed repair details. Got ${JSON.stringify(copiedRepairBrief)}.`
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Reopen repair prompt npm run test', exact: true }),
    'reopen repair trail prompt button'
  );
  await waitForLocatorCount(
    page.getByText('Reopened repair prompt with 1 validation target pinned.', { exact: true }),
    1,
    'reopen repair trail prompt status'
  );
  await waitForLocatorCount(page.getByLabel('Pinned context files'), 1, 'reopened repair prompt pinned context bar');
  await waitForLocatorCount(
    page.getByLabel('Pinned context files').getByText('generated/selected-only.txt', { exact: true }),
    1,
    'reopened repair prompt pinned generated file'
  );
  const reopenedRepairDraft = normalizeLineEndings(await composer.inputValue());
  assert(
    reopenedRepairDraft.includes('Please repair the failed validation from the last generated changes.') &&
      reopenedRepairDraft.includes('- create: generated/selected-only.txt') &&
      reopenedRepairDraft.includes('Command: npm run test') &&
      reopenedRepairDraft.includes('Exit code: 1') &&
      reopenedRepairDraft.includes('Summary: Manual apply validation failed.') &&
      reopenedRepairDraft.includes('Reason: Tests failed.') &&
      reopenedRepairDraft.includes('Output:\nselected generated fixture is missing a required assertion') &&
      reopenedRepairDraft.includes('manual apply validation failed'),
    `Reopened repair prompt did not restore expected repair context. Got ${JSON.stringify(reopenedRepairDraft)}.`
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Draft follow-up repair prompt npm run test', exact: true }),
    'draft failed repair follow-up button'
  );
  await waitForLocatorCount(
    page.getByText('Drafted follow-up repair prompt with 1 validation target pinned.', { exact: true }),
    1,
    'draft failed repair follow-up status'
  );
  await waitForLocatorCount(page.getByLabel('Pinned context files'), 1, 'follow-up repair prompt pinned context bar');
  await waitForLocatorCount(
    page.getByLabel('Pinned context files').getByText('generated/selected-only.txt', { exact: true }),
    1,
    'follow-up repair prompt pinned generated file'
  );
  const followUpRepairDraft = normalizeLineEndings(await composer.inputValue());
  assert(
    followUpRepairDraft.includes('Please continue repairing this validation failure. The previous repair attempt also failed.') &&
      followUpRepairDraft.includes('Original repair request:') &&
      followUpRepairDraft.includes('Please repair the failed validation from the last generated changes.') &&
      followUpRepairDraft.includes('- create: generated/selected-only.txt') &&
      followUpRepairDraft.includes('Follow-up validation result:') &&
      followUpRepairDraft.includes('Command: npm run test') &&
      followUpRepairDraft.includes('Exit code: 2') &&
      followUpRepairDraft.includes('Summary: Repair validation still failing.') &&
      followUpRepairDraft.includes('Reason: Type check failed.') &&
      followUpRepairDraft.includes('Output:\nfollow-up assertion is still missing\n\nrepair validation failed'),
    `Drafted failed repair follow-up prompt did not include the expected context. Got ${JSON.stringify(followUpRepairDraft)}.`
  );
  await clickUnique(
    repairTrail.getByRole('button', { name: 'Send follow-up repair prompt npm run test', exact: true }),
    'send failed repair follow-up button'
  );
  await waitForLocatorCount(
    page.getByText('Follow-up repair request received.', { exact: true }),
    1,
    'follow-up repair request final response'
  );
  await waitForLocatorExactCount(page.getByLabel('Pinned context files'), 0, 'follow-up repair context cleared after send');
  await waitForLocatorCount(repairTrail.getByText('npm run test / Passed', { exact: true }), 1, 'passed repair trail title');
  await waitForLocatorCount(
    repairTrail.getByText('Follow-up: exit 0 / Repair validation passed.', { exact: true }),
    1,
    'repair trail passed follow-up'
  );
  await waitForLocatorExactCount(
    repairTrail.getByRole('button', { name: 'Draft follow-up repair prompt npm run test', exact: true }),
    0,
    'hidden draft follow-up button after repair passes'
  );
  assert(repairRequestPayloads.length === 2, `Expected two repair request payloads, got ${repairRequestPayloads.length}.`);
  const [repairRequestPayload, followUpRepairRequestPayload] = repairRequestPayloads;
  assert(
    repairRequestPayload.apply_changes === false,
    `Repair request should keep auto-apply disabled, got ${JSON.stringify(repairRequestPayload.apply_changes)}.`
  );
  assert(
    repairRequestPayload.run_validation === true,
    `Repair request should ask the backend to validate the repair, got ${JSON.stringify(repairRequestPayload.run_validation)}.`
  );
  assert(
    repairRequestPayload.mode === 'develop',
    `Repair request should use develop mode, got ${JSON.stringify(repairRequestPayload.mode)}.`
  );
  assert(
    Array.isArray(repairRequestPayload.context_paths) &&
      repairRequestPayload.context_paths.includes('generated/selected-only.txt'),
    `Repair request context_paths did not include the validated generated file: ${JSON.stringify(repairRequestPayload.context_paths)}.`
  );
  const repairMessage = normalizeLineEndings(String(repairRequestPayload.message || ''));
  assert(
    repairMessage.includes('Please repair the failed validation from the last generated changes.') &&
      repairMessage.includes('- create: generated/selected-only.txt') &&
      repairMessage.includes('Command: npm run test') &&
      repairMessage.includes('Exit code: 1') &&
      repairMessage.includes('selected generated fixture is missing a required assertion') &&
      repairMessage.includes('manual apply validation failed'),
    `Repair request message did not include the expected validation context. Got ${JSON.stringify(repairMessage)}.`
  );
  assert(
    followUpRepairRequestPayload.apply_changes === false,
    `Follow-up repair request should keep auto-apply disabled, got ${JSON.stringify(followUpRepairRequestPayload.apply_changes)}.`
  );
  assert(
    followUpRepairRequestPayload.run_validation === true,
    `Follow-up repair request should ask the backend to validate the repair, got ${JSON.stringify(followUpRepairRequestPayload.run_validation)}.`
  );
  assert(
    followUpRepairRequestPayload.mode === 'develop',
    `Follow-up repair request should use develop mode, got ${JSON.stringify(followUpRepairRequestPayload.mode)}.`
  );
  assert(
    Array.isArray(followUpRepairRequestPayload.context_paths) &&
      followUpRepairRequestPayload.context_paths.includes('generated/selected-only.txt'),
    `Follow-up repair request context_paths did not include the validated generated file: ${JSON.stringify(followUpRepairRequestPayload.context_paths)}.`
  );
  const followUpRepairMessage = normalizeLineEndings(String(followUpRepairRequestPayload.message || ''));
  assert(
    followUpRepairMessage.includes('Please continue repairing this validation failure. The previous repair attempt also failed.') &&
      followUpRepairMessage.includes('Original repair request:') &&
      followUpRepairMessage.includes('Please repair the failed validation from the last generated changes.') &&
      followUpRepairMessage.includes('Exit code: 2') &&
      followUpRepairMessage.includes('follow-up assertion is still missing') &&
      followUpRepairMessage.includes('repair validation failed'),
    `Follow-up repair request message did not include the failed repair context. Got ${JSON.stringify(followUpRepairMessage)}.`
  );
  await expectWorkspaceFile('generated/selected-only.txt', 'selected change applied\n');
  await expectWorkspacePreview(page, 'generated/selected-only.txt', 'selected change applied');
  await expectWorkspaceFileMissing('generated/apply-all-only.txt');

  await clickUnique(
    page.getByRole('button', { name: 'Apply remaining 1 generated changes', exact: true }),
    'apply remaining generated change button'
  );
  await waitForLocatorCount(
    page.getByText('Applied 1 remaining change. Validation completed successfully.', { exact: true }),
    1,
    'apply remaining validation status'
  );
  await expectWorkspaceFile('generated/selected-only.txt', 'selected change applied\n');
  await expectWorkspaceFile('generated/apply-all-only.txt', 'all change applied\n');
  await expectWorkspacePreview(page, 'generated/apply-all-only.txt', 'all change applied');
  await waitForLocatorExactCount(
    page.getByText('skipped create because the file already exists', { exact: false }),
    0,
    'duplicate create warning after apply remaining',
    1_000
  );

  assert(applyScopeRequests === 3, `Expected one apply scope request and two repair requests, got ${applyScopeRequests}.`);
  assert(
    manualApplyValidationRequests === 2,
    `Expected validation after each manual apply operation, got ${manualApplyValidationRequests}.`
  );
  await page.unroute(`${backendUrl}/api/chat/stream`);
  await page.unroute(`${backendUrl}/api/validate`);
  await runValidationToggle.uncheck();

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after apply scope test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after apply scope test');
}

async function exerciseManualApplyWarningStatus(page) {
  const retryPath = 'retry-target.txt';
  const retryExistingContent = 'existing retry target\n';
  const retryGeneratedContent = 'created after warning retry\n';
  await writeFile(path.join(workspaceRoot, retryPath), retryExistingContent, 'utf8');

  let warningStatusRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    warningStatusRequests += 1;
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: 'e2e-apply-warning-status-test',
            reply: 'Generated unsafe create fixture.',
            changes: [
              {
                action: 'create',
                path: retryPath,
                summary: 'Unsafe create over an existing file',
                content: retryGeneratedContent
              }
            ]
          })
        })}`
      ].join('\n')
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByLabel('Apply changes automatically', { exact: true }).uncheck();
  await composer.fill('generate unsafe create over an existing retry target');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send warning status prompt button');
  await waitForLocatorCount(page.getByText('Generated unsafe create fixture.', { exact: true }), 1, 'warning status final response');
  const reviewSummary = page.getByTestId('generated-change-summary');
  await waitForLocatorCount(reviewSummary.getByText('1 file', { exact: true }), 1, 'initial generated change file summary');
  await waitForLocatorCount(reviewSummary.getByText('0 applied', { exact: true }), 1, 'initial generated change applied summary');
  await waitForLocatorCount(reviewSummary.getByText('1 remaining', { exact: true }), 1, 'initial generated change remaining summary');
  await waitForLocatorCount(reviewSummary.getByText('0 skipped', { exact: true }), 1, 'initial generated change skipped summary');
  await waitForLocatorCount(
    page.getByRole('button', { name: `Apply selected generated change ${retryPath}`, exact: true }),
    1,
    'initial apply selected generated change button'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: 'Apply remaining 1 generated changes', exact: true }),
    1,
    'initial apply remaining button for unapplied generated change'
  );

  await clickUnique(
    page.getByRole('button', { name: `Apply selected generated change ${retryPath}`, exact: true }),
    'apply unsafe create warning button'
  );
  const expectedWarning = `No changes were applied. Warning: ${retryPath}: skipped create because the file already exists; use update to modify existing files`;
  const warningText = `${retryPath}: skipped create because the file already exists; use update to modify existing files`;
  await waitForLocatorCount(page.getByText(expectedWarning, { exact: true }), 1, 'manual apply warning status');
  await waitForLocatorCount(reviewSummary.getByText('0 remaining', { exact: true }), 1, 'blocked generated change remaining summary');
  await waitForLocatorCount(reviewSummary.getByText('1 skipped', { exact: true }), 1, 'updated generated change skipped summary');
  await waitForLocatorExactCount(
    page.getByRole('button', { name: 'Apply remaining 1 generated changes', exact: true }),
    0,
    'hidden apply remaining button after generated change is skipped'
  );
  await waitForLocatorCount(
    page.getByRole('button', { name: `Retry selected generated change ${retryPath}`, exact: true }),
    1,
    'retry selected button after generated change is skipped'
  );
  await waitForLocatorCount(
    page.getByTestId(`generated-change-warning-create:${retryPath}`).getByText('Skipped', { exact: true }),
    1,
    'per-change skipped warning badge'
  );
  await waitForLocatorCount(
    page.getByTestId('selected-change-warning').getByText(warningText, { exact: true }),
    1,
    'selected generated change warning detail'
  );
  await waitForLocatorCount(page.locator('li').filter({ hasText: warningText }), 1, 'manual apply warning box entry');
  await expectWorkspaceFile(retryPath, retryExistingContent);
  await expectWorkspacePreview(page, retryPath, retryExistingContent.trim());

  await clickUnique(
    page.getByRole('button', { name: `Retry selected generated change ${retryPath}`, exact: true }),
    'repeat unsafe create warning button'
  );
  await waitForLocatorCount(page.getByText(expectedWarning, { exact: true }), 1, 'repeated manual apply warning status');
  await waitForLocatorExactCount(
    page.locator('li').filter({ hasText: warningText }),
    1,
    'deduplicated manual apply warning box entry'
  );
  await waitForLocatorExactCount(
    page.getByTestId(`generated-change-warning-create:${retryPath}`).getByText('Skipped', { exact: true }),
    1,
    'deduplicated per-change skipped warning badge'
  );
  await waitForLocatorExactCount(
    reviewSummary.getByText('1 skipped', { exact: true }),
    1,
    'deduplicated generated change skipped summary'
  );
  await expectWorkspaceFile(retryPath, retryExistingContent);

  await rm(path.join(workspaceRoot, retryPath), { force: true });
  await clickUnique(
    page.getByRole('button', { name: `Retry selected generated change ${retryPath}`, exact: true }),
    'successful retry after removing conflicting file'
  );
  await waitForLocatorCount(page.getByText('Applied 1 selected change.', { exact: true }), 1, 'successful retry status');
  await waitForLocatorCount(reviewSummary.getByText('1 applied', { exact: true }), 1, 'resolved warning applied summary');
  await waitForLocatorCount(reviewSummary.getByText('0 skipped', { exact: true }), 1, 'resolved warning skipped summary');
  await waitForLocatorExactCount(page.getByTestId('selected-change-warning'), 0, 'resolved selected warning detail');
  await waitForLocatorExactCount(page.locator('li').filter({ hasText: warningText }), 0, 'resolved warning panel entry');
  await waitForLocatorExactCount(
    page.getByTestId(`generated-change-warning-create:${retryPath}`).getByText('Skipped', { exact: true }),
    0,
    'resolved per-change skipped warning badge'
  );
  await expectWorkspaceFile(retryPath, retryGeneratedContent);

  assert(warningStatusRequests === 1, `Expected one warning status stream request, got ${warningStatusRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after warning status test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after warning status test');
}

async function exerciseSamePathWarningPrecision(page) {
  const samePath = 'same-path-action-warning.txt';
  const createdContent = 'created same path fixture\n';
  const appendWarning =
    `${samePath}: skipped append because the seed create for this file did not apply; use update to modify existing files`;
  await writeFile(path.join(workspaceRoot, samePath), createdContent, 'utf8');

  let samePathRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    samePathRequests += 1;
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: 'e2e-same-path-warning-precision-test',
            reply: 'Generated same-path warning fixture.',
            changes: [
              {
                action: 'create',
                path: samePath,
                summary: 'Create a same-path fixture',
                content: createdContent
              },
              {
                action: 'append',
                path: samePath,
                summary: 'Append to the same-path fixture',
                content: 'appended same path fixture\n'
              }
            ],
            applied: [`create: ${samePath}`],
            warnings: [appendWarning]
          })
        })}`
      ].join('\n')
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill('show a same-path generated change warning');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send same-path warning prompt button');
  await waitForLocatorCount(
    page.getByText('Generated same-path warning fixture.', { exact: true }),
    1,
    'same-path warning final response'
  );

  const reviewSummary = page.getByTestId('generated-change-summary');
  await waitForLocatorCount(reviewSummary.getByText('2 files', { exact: true }), 1, 'same-path generated change file summary');
  await waitForLocatorCount(reviewSummary.getByText('1 applied', { exact: true }), 1, 'same-path applied summary');
  await waitForLocatorCount(reviewSummary.getByText('0 remaining', { exact: true }), 1, 'same-path remaining summary');
  await waitForLocatorCount(reviewSummary.getByText('1 skipped', { exact: true }), 1, 'same-path skipped summary');
  await waitForLocatorExactCount(
    page.getByTestId(`generated-change-warning-create:${samePath}`),
    0,
    'same-path create change should not inherit append warning'
  );
  await waitForLocatorCount(
    page.getByTestId(`generated-change-warning-append:${samePath}`).getByText('Skipped', { exact: true }),
    1,
    'same-path append change warning badge'
  );
  await waitForLocatorExactCount(
    page.getByTestId('selected-change-warning'),
    0,
    'same-path applied create should not show append warning detail'
  );
  await waitForLocatorCount(page.locator('li').filter({ hasText: appendWarning }), 1, 'same-path warning panel entry');

  await clickUnique(
    page.getByTestId(`generated-change-append:${samePath}`),
    'select append same-path generated change'
  );
  await waitForLocatorCount(
    page.getByTestId('selected-change-warning').getByText(appendWarning, { exact: true }),
    1,
    'same-path selected append warning detail'
  );
  await waitForLocatorExactCount(
    page.getByRole('button', { name: 'Apply remaining 1 generated changes', exact: true }),
    0,
    'same-path blocked append should not be offered in apply remaining'
  );

  assert(samePathRequests === 1, `Expected one same-path warning stream request, got ${samePathRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after same-path warning test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after same-path warning test');
}

async function exerciseGeneratedChangeReviewRestore(page) {
  const checkpoint = 'e2e-restored-review-checkpoint';
  const updatePath = 'restored-review.txt';
  const createPath = 'generated/restored-review-new.ts';
  const oldContent = 'alpha\nremove me\nkeep\n';
  const updateContent = 'alpha\nkeep\nadded from saved review\n';
  const createContent = 'export const savedReview = true;\nconsole.log(savedReview);\n';
  const checkpointFilesRoot = path.join(workspaceRoot, '.aegis', 'checkpoints', checkpoint, 'files');

  await writeFile(path.join(workspaceRoot, updatePath), oldContent, 'utf8');
  await mkdir(checkpointFilesRoot, { recursive: true });
  await mkdir(path.dirname(path.join(checkpointFilesRoot, createPath)), { recursive: true });
  await writeFile(path.join(checkpointFilesRoot, updatePath), oldContent, 'utf8');

  let restoreRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    restoreRequests += 1;
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: 'e2e-restored-generated-review-test',
            reply: 'Restored review fixture generated.\n\n```ts\nexport const savedReview = true;\n```',
            changes: [
              {
                action: 'update',
                path: updatePath,
                summary: 'Update a file with one added and one removed line',
                content: updateContent
              },
              {
                action: 'create',
                path: createPath,
                summary: 'Create a saved review fixture',
                content: createContent
              }
            ],
            applied: [`update: ${updatePath}`],
            checkpoint
          })
        })}`
      ].join('\n')
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByLabel('Apply changes automatically', { exact: true }).uncheck();
  await composer.fill('generate a saved review fixture');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send saved review fixture prompt');
  await waitForLocatorCount(
    page.getByText('Restored review fixture generated.', { exact: true }),
    1,
    'saved review final response'
  );
  await waitForLocatorCount(
    page.getByTestId('chat-scroll').getByText('export const savedReview = true;', { exact: true }),
    1,
    'saved review code block'
  );

  const inlineReview = page.getByTestId('inline-change-review');
  await waitForLocatorCount(inlineReview.getByText('2 files changed', { exact: true }), 1, 'live inline review file count');
  await waitForLocatorCount(inlineReview.getByText('+3', { exact: true }), 1, 'live inline review added count');
  await waitForLocatorCount(inlineReview.getByText('-1', { exact: true }), 1, 'live inline review removed count');
  await waitForLocatorExactCount(page.getByTestId('inline-change-list'), 0, 'live inline review file list collapsed by default');
  await clickUnique(page.getByRole('button', { name: 'Show generated file list', exact: true }), 'show live inline file list');
  await waitForLocatorCount(page.getByTestId('inline-change-list'), 1, 'live inline review file list expanded');
  await waitForLocatorCount(
    page.getByTestId(`inline-change-stat-update:${updatePath}`).getByText('+1', { exact: true }),
    1,
    'live inline update added count'
  );
  await waitForLocatorCount(
    page.getByTestId(`inline-change-stat-update:${updatePath}`).getByText('-1', { exact: true }),
    1,
    'live inline update removed count'
  );
  await clickUnique(page.getByRole('button', { name: 'Hide generated file list', exact: true }), 'hide live inline file list');
  await waitForLocatorExactCount(page.getByTestId('inline-change-list'), 0, 'live inline review file list collapsed after hiding');

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after saved review response');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after saving review thread');

  const savedThread = await page.evaluate(
    ({ storageKey, taskId }) => {
      const threads = JSON.parse(localStorage.getItem(storageKey) || '[]');
      return (
        threads.find((thread) =>
          thread?.messages?.some((message) => message?.metadata?.taskId === taskId)
        ) || null
      );
    },
    { storageKey: conversationStorageKey, taskId: 'e2e-restored-generated-review-test' }
  );
  assert(savedThread, 'Generated review thread was not saved to local storage.');
  const savedAssistant = savedThread.messages.find(
    (message) => message?.metadata?.taskId === 'e2e-restored-generated-review-test'
  );
  assert(
    savedAssistant?.metadata?.generatedChanges?.length === 2,
    'Saved assistant message did not preserve generated change metadata.'
  );
  assert(
    savedAssistant.metadata.checkpoint === checkpoint,
    'Saved assistant message did not preserve the generated change checkpoint.'
  );

  await page.reload({ waitUntil: 'domcontentloaded' });
  const savedChatButton = page.getByRole('button', { name: savedThread.title, exact: true });
  await savedChatButton.waitFor({ state: 'visible', timeout: 30_000 });
  await clickUnique(savedChatButton, 'restored saved generated review session');
  await waitForLocatorCount(
    page.getByText('Restored review fixture generated.', { exact: true }),
    1,
    'restored saved review assistant message'
  );

  const restoredInlineReview = page.getByTestId('inline-change-review');
  await waitForLocatorCount(
    restoredInlineReview.getByText('2 files changed', { exact: true }),
    1,
    'restored inline review file count'
  );
  await waitForLocatorCount(restoredInlineReview.getByText('+3', { exact: true }), 1, 'restored inline added count');
  await waitForLocatorCount(restoredInlineReview.getByText('-1', { exact: true }), 1, 'restored inline removed count');
  await waitForLocatorExactCount(page.getByTestId('inline-change-list'), 0, 'restored inline review file list collapsed by default');
  await clickUnique(
    page.getByRole('button', { name: 'Review generated file changes', exact: true }),
    'open restored generated change review'
  );
  const restoredSummary = page.getByTestId('generated-change-summary');
  await waitForLocatorCount(restoredSummary.getByText('2 files', { exact: true }), 1, 'restored review summary files');
  await waitForLocatorCount(restoredSummary.getByText('1 applied', { exact: true }), 1, 'restored review applied count');
  await waitForLocatorCount(page.getByText('+1 / -1', { exact: true }), 1, 'restored selected change diff counts');
  await waitForLocatorCount(
    page.getByText('+added from saved review', { exact: false }),
    1,
    'restored selected change diff content'
  );

  assert(restoreRequests === 1, `Expected one saved review stream request, got ${restoreRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after restore review test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after restore review test');
}

async function exerciseComposerDraftRestore(page) {
  const draftText = 'restore this composer draft after reload';
  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill(draftText);

  await page.reload({ waitUntil: 'domcontentloaded' });
  const restoredComposer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await restoredComposer.waitFor({ state: 'visible', timeout: 30_000 });
  assert((await restoredComposer.inputValue()) === draftText, 'Composer draft was not restored after page reload.');

  const storedDraft = await page.evaluate((storageKey) => {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw).content : '';
  }, composerDraftStorageKey);
  assert(storedDraft === draftText, 'Composer draft was not saved to local storage.');

  let draftRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    draftRequests += 1;
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({ task_id: 'e2e-draft-test', reply: 'Draft send complete.' })
        })}`
      ].join('\n')
    });
  });

  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send restored draft button');
  await waitForLocatorCount(
    page.getByTestId('chat-scroll').getByText('Draft send complete.', { exact: true }),
    1,
    'draft send final chat response'
  );
  await exerciseCurrentChatExport(page, draftText, 'Draft send complete.');

  const remainingDraft = await page.evaluate((storageKey) => localStorage.getItem(storageKey), composerDraftStorageKey);
  assert(remainingDraft === null, 'Composer draft was not cleared after sending.');
  assert(draftRequests === 1, `Expected one draft stream request, got ${draftRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);
}

async function exerciseCurrentChatExport(page, userMessage, assistantMessage) {
  const exportButton = page.getByRole('button', { name: 'Export session transcript', exact: true });
  await exportButton.waitFor({ state: 'visible', timeout: 10_000 });

  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 10_000 }),
    clickUnique(exportButton, 'export session transcript button')
  ]);
  const suggestedFilename = download.suggestedFilename();
  assert(suggestedFilename.endsWith('.md'), `Expected Markdown transcript filename, got ${suggestedFilename}.`);

  const downloadPath = await download.path();
  assert(downloadPath, 'Transcript download did not produce a readable file path.');
  const markdown = await readFile(downloadPath, 'utf8');
  assert(markdown.includes(`# ${assistantMessage}`), 'Transcript markdown did not include the summarized chat title.');
  assert(markdown.includes('## User'), 'Transcript markdown did not include the user section.');
  assert(markdown.includes(userMessage), 'Transcript markdown did not include the user message.');
  assert(markdown.includes('## Auralith Prime'), 'Transcript markdown did not include the assistant section.');
  assert(markdown.includes(assistantMessage), 'Transcript markdown did not include the assistant message.');
  await waitForLocatorCount(page.getByText('Exported transcript', { exact: false }), 1, 'transcript export status');
}

async function exerciseChatAutoScroll(page) {
  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session before auto-scroll test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session before auto-scroll test');
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel visible before auto-scroll test');

  const longReply = [
    ...Array.from({ length: 90 }, (_, index) => `Auto scroll line ${index + 1}`),
    'Auto scroll final marker'
  ].join('\n');

  let autoScrollRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    autoScrollRequests += 1;
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({ task_id: 'e2e-auto-scroll-test', reply: longReply })
        })}`
      ].join('\n')
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill('make a long response for auto scroll');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send auto-scroll prompt button');
  await waitForLocatorCount(page.getByText('Auto scroll final marker', { exact: false }), 1, 'auto-scroll final marker');
  await waitForChatScrollAtBottom(page, 'chat auto-scroll after long response');

  assert(autoScrollRequests === 1, `Expected one auto-scroll stream request, got ${autoScrollRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);

  await clickUnique(page.getByRole('button', { name: 'New session', exact: true }), 'new session after auto-scroll test');
  await waitForLocatorCount(page.getByText('Welcome to Auralith OS', { exact: true }), 1, 'empty session after auto-scroll test');
}

async function exerciseQueuedPromptTray(page) {
  await page.evaluate(() => localStorage.removeItem('aegis.queueAutoSendPaused.v1'));

  let streamRequests = 0;
  const streamMessages = [];
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    streamRequests += 1;
    const payload = JSON.parse(route.request().postData() || '{}');
    streamMessages.push(payload.message);
    const isActivePrompt = streamRequests === 1;
    const reply = isActivePrompt ? 'Queue active prompt complete.' : `Queued prompt sent: ${payload.message}`;
    await delay(isActivePrompt ? 7_000 : 500);
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache'
      },
      body: [
        'event: meta',
        'data: {"type":"meta","schema_version":"aegis.chat.stream.v1","stream_mode":"e2e-queue"}',
        '',
        'event: delta',
        `data: ${JSON.stringify({ type: 'delta', delta: reply, source: 'direct' })}`,
        '',
        'event: final',
        `data: ${JSON.stringify({
          type: 'final',
          response: queueTestResponse({
            task_id: `e2e-queue-test-${streamRequests}`,
            reply
          })
        })}`
      ].join('\n')
    });
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill('start a slow queue tray test');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send prompt button');

  const queueComposer = page.getByPlaceholder('Message Auralith Prime... next prompt will be queued', { exact: true });
  await queueComposer.waitFor({ state: 'visible', timeout: 5_000 });
  await queueComposer.fill('first queued prompt should wait');
  await clickUnique(page.getByRole('button', { name: 'Queue prompt', exact: true }), 'queue prompt button');
  await queueComposer.fill('second queued prompt should go next');
  await clickUnique(page.getByRole('button', { name: 'Queue prompt', exact: true }), 'queue second prompt button');

  await clickUnique(page.getByRole('button', { name: '2 queued', exact: true }), 'queued prompt tray toggle');
  await waitForLocatorCount(page.getByLabel('Queued messages'), 1, 'queued messages tray');
  await waitForLocatorCount(
    page.getByTestId('queued-message-1').getByText('first queued prompt should wait', { exact: true }),
    1,
    'first queued prompt starts first'
  );
  await waitForLocatorCount(
    page.getByTestId('queued-message-2').getByText('second queued prompt should go next', { exact: true }),
    1,
    'second queued prompt starts second'
  );
  await clickUnique(page.getByRole('button', { name: 'Pause queued prompts', exact: true }), 'pause queued prompts');
  await waitForLocatorCount(page.getByText('Queued prompts paused.', { exact: true }), 1, 'queue paused status');
  await waitForLocatorCount(
    page.getByText('Auto-send paused. Resume when you are ready.', { exact: true }),
    1,
    'queue paused tray meta'
  );

  await clickUnique(
    page.getByRole('button', { name: 'Move queued message 2 earlier', exact: true }),
    'move second queued prompt earlier'
  );
  await waitForLocatorCount(page.getByText('Queued message moved earlier.', { exact: true }), 1, 'queue moved earlier status');
  await waitForLocatorCount(
    page.getByTestId('queued-message-1').getByText('second queued prompt should go next', { exact: true }),
    1,
    'second queued prompt moved to first'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Move queued message 1 later', exact: true }),
    'move queued prompt later'
  );
  await waitForLocatorCount(page.getByText('Queued message moved later.', { exact: true }), 1, 'queue moved later status');
  await waitForLocatorCount(
    page.getByTestId('queued-message-1').getByText('first queued prompt should wait', { exact: true }),
    1,
    'first queued prompt restored first'
  );
  await clickUnique(
    page.getByRole('button', { name: 'Move queued message 2 earlier', exact: true }),
    'move second queued prompt earlier before auto-send'
  );

  await clickUnique(page.getByRole('button', { name: 'Discard queued message 2', exact: true }), 'discard trailing queued prompt button');
  await waitForLocatorCount(page.getByText('Queued message discarded.', { exact: true }), 1, 'queue discard status');
  await waitForLocatorCount(page.getByRole('button', { name: '1 queued', exact: true }), 1, 'queued count after discard');
  await waitForLocatorExactCount(page.getByTestId('queued-message-2'), 0, 'only one queued prompt remains after discard');

  await waitForLocatorCount(page.getByText('Queue active prompt complete.', { exact: true }), 1, 'active queued stream final response');
  await waitForLocatorCount(page.getByRole('button', { name: '1 queued', exact: true }), 1, 'paused queued prompt remains after active response');
  await waitForLocatorExactCount(
    page.getByText('Queued prompt sent: second queued prompt should go next', { exact: true }),
    0,
    'paused queue does not auto-send after active response'
  );
  assert(streamRequests === 1, `Expected only the active prompt to stream while queue is paused, got ${streamRequests} stream requests.`);

  await clickUnique(page.getByRole('button', { name: 'Resume queued prompts', exact: true }), 'resume queued prompts');
  await waitForLocatorCount(
    page.getByText('Queued prompt sent: second queued prompt should go next', { exact: true }),
    1,
    'reordered queued prompt sends after active response'
  );
  await waitForLocatorExactCount(page.getByRole('button', { name: '1 queued', exact: true }), 0, 'queued count clears after replay');
  assert(streamRequests === 2, `Expected the active prompt and one reordered queued prompt to stream, got ${streamRequests} stream requests.`);
  assert(
    streamMessages.join(' | ') === 'start a slow queue tray test | second queued prompt should go next',
    `Queued prompts streamed in the wrong order: ${streamMessages.join(' | ')}`
  );
  await page.unroute(`${backendUrl}/api/chat/stream`);
}

async function exerciseStopActiveResponse(page) {
  let stopRequests = 0;
  await page.route(`${backendUrl}/api/chat/stream`, async (route) => {
    stopRequests += 1;
    await delay(1_200);
    await route
      .fulfill({
        status: 200,
        headers: {
          'content-type': 'text/event-stream; charset=utf-8',
          'cache-control': 'no-cache'
        },
        body: [
          'event: final',
          `data: ${JSON.stringify({
            type: 'final',
            response: queueTestResponse({ reply: 'late stopped response should not appear' })
          })}`
        ].join('\n')
      })
      .catch(() => {});
  });

  const composer = page.getByPlaceholder('Message Auralith Prime...', { exact: true });
  await composer.waitFor({ state: 'visible', timeout: 30_000 });
  await composer.fill('start a response that I will stop');
  await clickUnique(page.getByRole('button', { name: 'Send prompt', exact: true }), 'send prompt button for stop test');

  const stopButton = page.getByRole('button', { name: 'Stop current response', exact: true });
  await stopButton.waitFor({ state: 'visible', timeout: 5_000 });
  await clickUnique(stopButton, 'stop current response button');

  await waitForLocatorCount(page.getByText('Session request stopped.', { exact: true }), 1, 'stopped response status');
  await waitForLocatorExactCount(stopButton, 0, 'stop response button after abort', 10_000);
  await delay(1_500);
  await waitForLocatorExactCount(
    page.getByText('late stopped response should not appear', { exact: false }),
    0,
    'late stopped response text',
    1_000
  );
  assert(stopRequests === 1, `Expected one stopped stream request, got ${stopRequests}.`);
  await page.unroute(`${backendUrl}/api/chat/stream`);
}

async function exerciseResponsiveShell(page) {
  const desktopViewport = { width: 1440, height: 1050 };
  const responsiveViewports = [
    { label: 'laptop', width: 1024, height: 820 },
    { label: 'mobile', width: 390, height: 844 }
  ];

  for (const viewport of responsiveViewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await delay(700);
    const metrics = await page.evaluate(() => {
      const root = document.documentElement;
      const body = document.body;
      const commandInput = document.querySelector('.aegis-command-input');
      const commandInputBox = commandInput?.getBoundingClientRect();
      return {
        innerWidth: window.innerWidth,
        scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
        commandInputVisible: Boolean(commandInputBox && commandInputBox.width > 80 && commandInputBox.height > 32),
        detailsPanelCount: document.querySelectorAll('[data-testid="details-panel"]').length
      };
    });

    assert(
      metrics.scrollWidth <= metrics.innerWidth + 4,
      `${viewport.label} layout overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
    );
    assert(metrics.commandInputVisible, `${viewport.label} command input was not visible after resizing.`);
    assert(
      metrics.detailsPanelCount === 0,
      `${viewport.label} layout should suppress the details panel on compact viewports.`
    );
  }

  await page.setViewportSize(desktopViewport);
  await delay(700);
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel restored after responsive checks');
}

async function exerciseResponsiveSettingsModal(page) {
  const desktopViewport = { width: 1440, height: 1050 };
  const responsiveViewports = [
    { label: 'tablet', width: 768, height: 1024 },
    { label: 'mobile', width: 390, height: 844 }
  ];

  for (const viewport of responsiveViewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await delay(700);
    await clickUnique(page.getByRole('button', { name: 'Settings', exact: true }), `${viewport.label} settings button`);
    await waitForLocatorCount(page.getByRole('heading', { name: 'Settings', exact: true }), 1, `${viewport.label} settings modal`);
    await waitForLocatorCount(page.getByLabel('Settings sections'), 1, `${viewport.label} settings rail`);
    const metrics = await page.evaluate(() => {
      const root = document.documentElement;
      const body = document.body;
      const heading = Array.from(document.querySelectorAll('h3')).find((item) => item.textContent === 'Settings');
      const modal = heading?.parentElement?.parentElement;
      const modalBox = modal?.getBoundingClientRect();
      return {
        innerWidth: window.innerWidth,
        scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
        modalVisible: Boolean(modalBox && modalBox.width > 240 && modalBox.height > 220)
      };
    });
    assert(
      metrics.scrollWidth <= metrics.innerWidth + 4,
      `${viewport.label} settings modal overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
    );
    assert(metrics.modalVisible, `${viewport.label} settings modal was not visibly sized.`);
    await clickUnique(page.getByRole('button', { name: 'Close settings', exact: true }), `${viewport.label} close settings button`);
    await waitForLocatorExactCount(
      page.getByRole('heading', { name: 'Settings', exact: true }),
      0,
      `${viewport.label} settings modal closed`
    );
  }

  await page.setViewportSize(desktopViewport);
  await delay(700);
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel restored after responsive settings checks');
}

async function exerciseResponsiveAuthenticatedOverlays(page) {
  const desktopViewport = { width: 1440, height: 1050 };
  const responsiveViewports = [
    { label: 'tablet', width: 768, height: 1024 },
    { label: 'mobile', width: 390, height: 844 }
  ];

  for (const viewport of responsiveViewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await delay(700);

    await clickUnique(page.getByRole('button', { name: 'Memory Editor', exact: true }), `${viewport.label} Memory Editor button`);
    await waitForLocatorCount(page.getByText('Memory Editor', { exact: true }), 1, `${viewport.label} Memory Editor overlay`);
    await assertOverlayViewportFit(page, `${viewport.label} Memory Editor`, 'Close Memory Editor');
    await clickUnique(page.getByRole('button', { name: 'Close Memory Editor', exact: true }), `${viewport.label} close Memory Editor`);
    await waitForLocatorExactCount(page.getByText('Memory Editor', { exact: true }), 0, `${viewport.label} Memory Editor closed`);

    await clickUnique(page.getByRole('button', { name: 'Approval Settings', exact: true }), `${viewport.label} Approval Settings button`);
    await waitForLocatorCount(
      page.getByText('Approval & Sandbox Settings', { exact: true }),
      1,
      `${viewport.label} Approval Settings overlay`
    );
    await assertOverlayViewportFit(page, `${viewport.label} Approval Settings`, 'Close Approval Settings');
    await clickUnique(
      page.getByRole('button', { name: 'Close Approval Settings', exact: true }),
      `${viewport.label} close Approval Settings`
    );
    await waitForLocatorExactCount(
      page.getByText('Approval & Sandbox Settings', { exact: true }),
      0,
      `${viewport.label} Approval Settings closed`
    );
  }

  await page.setViewportSize(desktopViewport);
  await delay(700);
  await waitForLocatorCount(page.getByTestId('details-panel'), 1, 'details panel restored after responsive overlay checks');
}

async function assertOverlayViewportFit(page, label, closeButtonLabel) {
  const metrics = await page.evaluate((buttonLabel) => {
    const root = document.documentElement;
    const body = document.body;
    const closeButton = document.querySelector(`button[aria-label="${buttonLabel}"]`);
    const closeButtonBox = closeButton?.getBoundingClientRect();
    return {
      innerWidth: window.innerWidth,
      scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
      closeButtonVisible: Boolean(closeButtonBox && closeButtonBox.width > 20 && closeButtonBox.height > 20)
    };
  }, closeButtonLabel);

  assert(
    metrics.scrollWidth <= metrics.innerWidth + 4,
    `${label} overflowed horizontally: scrollWidth ${metrics.scrollWidth}, viewport ${metrics.innerWidth}.`
  );
  assert(metrics.closeButtonVisible, `${label} close button was not visibly sized.`);
}

function queueTestResponse(overrides = {}) {
  return {
    task_id: 'e2e-queue-test',
    reply: 'Queue test complete.',
    plan: [],
    changes: [],
    applied: [],
    checkpoint: null,
    warnings: [],
    events: [],
    validation: null,
    validation_profile: null,
    task_plan: null,
    context_budget: null,
    model_attempts: [],
    assistant_name: 'Auralith Prime',
    mode: 'chat',
    engine: 'Aegis Core',
    workspace_root: workspaceRoot,
    workspace_files: [],
    context_files: [],
    memory_hits: [],
    project_memory_hits: [],
    recent_tasks: [],
    repair_attempts: [],
    completion_quality: null,
    ...overrides
  };
}

async function waitForJson(url, predicate, label) {
  const deadline = Date.now() + 30_000;
  let lastError = '';
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      const payload = await response.json();
      if (predicate(payload)) return payload;
      lastError = JSON.stringify(payload);
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${label}: ${lastError}`);
}

async function waitForHttpOk(url, label) {
  const deadline = Date.now() + 30_000;
  let lastStatus = '';
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastStatus = String(response.status);
    } catch (error) {
      lastStatus = error instanceof Error ? error.message : String(error);
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${label}: ${lastStatus}`);
}

async function findBrowserExecutable() {
  if (process.env.AEGIS_E2E_BROWSER_PATH) {
    await access(process.env.AEGIS_E2E_BROWSER_PATH);
    return process.env.AEGIS_E2E_BROWSER_PATH;
  }

  const candidates = [
    path.join(process.env.ProgramFiles || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    path.join(process.env['ProgramFiles(x86)'] || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    path.join(process.env.ProgramFiles || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    path.join(process.env['ProgramFiles(x86)'] || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe')
  ];

  for (const candidate of candidates) {
    if (!candidate || candidate.includes(`${path.sep}${path.sep}`)) continue;
    try {
      await access(candidate);
      return candidate;
    } catch {
      // Try the next installed browser.
    }
  }

  throw new Error('No Chrome or Edge executable was found. Set AEGIS_E2E_BROWSER_PATH to run UI E2E.');
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function stripTrailingSlash(value) {
  return value.replace(/\/+$/, '');
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, '').replace(/\..+$/, '').replace('T', '-');
}
