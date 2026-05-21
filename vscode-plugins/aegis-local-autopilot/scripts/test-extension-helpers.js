const assert = require('assert');
const path = require('path');

require.extensions['.ts'] = require.extensions['.ts'] || require.extensions['.js'];

const {
  buildDestinationReasoning,
  classifyDestinationRisk,
  inferDecisionSource
} = require('../src/workspace/destinationReasoning.ts');
const {
  AEGIS_CORE_CONTRACT_VERSION,
  validateCoreEnvelope,
  coreEnvelopeData,
  coreEnvelopeError,
  requireCoreOk,
  formatCoreContract
} = require('../src/core/coreEnvelope.ts');
const {
  normalizeCoreChanges,
  workspacePath
} = require('../src/core/aegisCoreClient.ts');
const {
  extractEditingJob,
  extractWorkflowSummary
} = require('../src/core/taskSync.ts');
const { createExtensionRuntimeState } = require('../src/extensionState.ts');

function run() {
  const workspaceRoot = path.join('C:\\', 'AegisSmoke', 'Project');
  const target = {
    root: workspaceRoot,
    workspaceRoot,
    focusRelative: 'src/features',
    focusKind: 'folder'
  };
  const snapshot = {
    target,
    files: [
      { relative: 'package.json' },
      { relative: 'src/App.tsx' },
      { relative: 'src/features/Existing.tsx' },
      { relative: 'src/components/Button.tsx' }
    ]
  };
  const proposal = {
    fileEdits: [
      { path: 'package.json', reason: 'Add project script', content: '{}' },
      { path: 'src/components/Card.tsx', reason: 'Add component', content: 'export function Card() {}' },
      { path: 'src/features/Existing.tsx', reason: 'Update selected feature', content: 'export const Existing = true;' }
    ]
  };

  const reasoning = buildDestinationReasoning(proposal, snapshot, target);
  assert.strictEqual(reasoning.length, 3);
  assert.strictEqual(reasoning[0].existing, true);
  assert.strictEqual(reasoning[0].source, 'existing file structure');
  assert.match(reasoning[0].choiceReason, /package or project root/);
  assert.strictEqual(reasoning[1].source, 'framework convention');
  assert.strictEqual(reasoning[2].source, 'user-selected folder');
  assert.strictEqual(classifyDestinationRisk('package-lock.json', true), 'high');
  assert.strictEqual(inferDecisionSource('src/pages/Home.tsx', '', false, ''), 'framework convention');

  const envelope = validateCoreEnvelope({
    api_version: 'v1',
    kind: 'changes.apply',
    ok: true,
    data: { job_id: 'job-1', checkpoint_id: 'checkpoint-1' }
  }, 'changes.apply');
  assert.strictEqual(coreEnvelopeData(envelope).job_id, 'job-1');
  assert.strictEqual(coreEnvelopeError({ data: { error: 'token=secret' } }).includes('secret'), false);
  assert.strictEqual(requireCoreOk(envelope, 'apply changes'), envelope);
  assert.throws(
    () => requireCoreOk({ api_version: 'v1', kind: 'changes.apply', ok: false, data: { error: 'Authorization: Bearer very-secret-token' } }, 'apply changes'),
    /Aegis Core could not apply changes: Authorization: \[redacted\]/
  );
  assert.strictEqual(
    formatCoreContract({ contract_version: AEGIS_CORE_CONTRACT_VERSION, stability: 'stable' }),
    `contract ${AEGIS_CORE_CONTRACT_VERSION} (stable)`
  );
  assert.match(
    formatCoreContract({ contract_version: '2026.04.01', stability: 'preview' }),
    new RegExp(`tested ${AEGIS_CORE_CONTRACT_VERSION.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)
  );

  const changes = normalizeCoreChanges([{ path: 'src/app.ts', content: 'next', reason: 'Update app' }]);
  assert.deepStrictEqual(changes[0], {
    id: 'change-1',
    action: 'update',
    path: 'src/app.ts',
    content: 'next',
    summary: 'Update app',
    selected: false
  });
  assert.strictEqual(workspacePath({ root: workspaceRoot }), workspaceRoot);

  const job = extractEditingJob({ job_id: 'job-2', checkpoint_id: 'checkpoint-2', task_id: 'task-1' });
  assert.strictEqual(job.jobId, 'job-2');
  assert.strictEqual(job.checkpointId, 'checkpoint-2');
  const workflow = extractWorkflowSummary({ workflow: { id: 'workflow-1', workflow_type: 'generate_feature', status: 'queued', progress: 20 } });
  assert.strictEqual(workflow.id, 'workflow-1');
  assert.strictEqual(workflow.progress, 20);

  const runtime = createExtensionRuntimeState();
  runtime.markCoreConnected('contract ok');
  runtime.recordOperation({ operation: 'apply', runtime: 'core', status: 'completed', checkpointId: 'checkpoint-3' });
  const runtimeSnapshot = runtime.snapshot();
  assert.strictEqual(runtimeSnapshot.coreConnected, true);
  assert.strictEqual(runtimeSnapshot.checkpointAvailable, true);
  assert.strictEqual(runtimeSnapshot.recentOperations[0].operation, 'apply');
}

run();
console.log('Aegis helper tests passed.');
