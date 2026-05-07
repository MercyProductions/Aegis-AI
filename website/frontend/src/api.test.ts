import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  __resetApiBaseForTests,
  __setApiDiscoveryForTests,
  activateAdaptivePolicyProfile,
  approveAutonomousGate,
  cancelExecutionQueueItem,
  cancelAutonomousObjective,
  cancelCreativeJob,
  createExecutionQueueItem,
  createAutonomousObjective,
  createCreativeJob,
  createReproducibilityRecord,
  createRemoteSyncManifest,
  dispatchExecutionQueue,
  disableEcosystemPackage,
  disablePlugin,
  dismissWorkspaceRecommendation,
  enableEcosystemPackage,
  enablePlugin,
  exportCurrentProjectIntelligence,
  exportSharedIntelligenceProfile,
  fixWorkspaceRecommendation,
  getAdaptiveIntelligence,
  getCurrentAccount,
  getAutonomousEngineering,
  getAutonomousObjective,
  getContinuity,
  getCreativeAssetLibrary,
  getCreativeJob,
  getCreativeStudio,
  getDistributedRuntime,
  getEcosystem,
  getDistributedRuntimeAudit,
  getEnterprisePolicy,
  getKnowledgeGraph,
  getOperatingEnvironment,
  getOrganizationPolicy,
  getPlatformDiscipline,
  getProductization,
  getUnifiedContext,
  getReliabilityMetrics,
  getRuntimeRecovery,
  getRuntimeObservability,
  getUnifiedRuntime,
  getWorkspaceIntelligence,
  getWorkspaceIntelligenceEvents,
  getWorkspaceIntelligenceJobs,
  getWorkspaceRecommendations,
  importSharedIntelligenceProfile,
  iterateAutonomousObjective,
  listEcosystemAudit,
  listEcosystemMarketplace,
  listEcosystemPackages,
  listEcosystemWorkflows,
  listReproducibilityRecords,
  listSharedIntelligenceProfiles,
  listPlugins,
  listStableApis,
  listExecutionQueue,
  listAdaptiveTaskOutcomes,
  listAutonomousApprovalGates,
  listAutonomousObjectives,
  listCreativeJobs,
  listRemoteSyncManifests,
  loginAccount,
  logoutAccount,
  listRuntimeWorkers,
  pauseAutonomousObjective,
  previewGlobalCommand,
  previewOperatingEnvironmentAction,
  registerRuntimeWorker,
  registerAccount,
  registerEcosystemPackage,
  registerEcosystemWorkflow,
  registerPlugin,
  refreshEcosystem,
  refreshProductization,
  rejectAutonomousGate,
  runEcosystemWorkflow,
  replayAdaptiveTasks,
  retryExecutionQueueItem,
  requestPasswordReset,
  rollbackAdaptivePolicy,
  routeDistributedModel,
  runAdaptiveBenchmarks,
  exportCreativeJob,
  simulateAutonomousObjective,
  startAutonomousObjective,
  runWorkspaceIntelligenceJobs,
  scanWorkspaceIntelligence,
  searchContinuityTimeline,
  searchEcosystem,
  searchUnifiedContext,
  submitGlobalCommand,
  streamAgentMessage,
  trustEcosystemPackage,
  trustPlugin,
  updateOrganizationPolicy,
  updateEnterprisePolicy,
  validateEcosystemPackage,
  validatePlugin
} from './api';
import type {
  AgentRequest,
  AgentResponse,
  EcosystemPackageManifest,
  EcosystemWorkflowDefinition,
  SharedIntelligenceProfile
} from './types';

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.restoreAllMocks();
  __resetApiBaseForTests();
  globalThis.fetch = originalFetch;
});

describe('streamAgentMessage', () => {
  it('accepts a final SSE frame even when the stream closes without a trailing blank line', async () => {
    const finalResponse = createAgentResponse({ reply: 'finished without trailing separator' });
    const onFinal = vi.fn();

    mockStreamResponse([
      sseFrame('meta', { type: 'meta', stream_mode: 'test' }),
      `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
    ]);

    await expect(streamAgentMessage(createAgentRequest(), { onFinal })).resolves.toMatchObject({
      reply: 'finished without trailing separator'
    });
    expect(onFinal).toHaveBeenCalledWith(expect.objectContaining({ response: finalResponse }));
  });

  it('parses frames split across network chunks and emits deltas before final', async () => {
    const finalResponse = createAgentResponse({ reply: 'split chunks done' });
    const onDelta = vi.fn();

    mockStreamResponse([
      'event: delta\ndata: {"type":"delta","delta":"split"',
      ',"source":"direct"}\n\n',
      `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
    ]);

    await expect(streamAgentMessage(createAgentRequest(), { onDelta })).resolves.toMatchObject({
      reply: 'split chunks done'
    });
    expect(onDelta).toHaveBeenCalledWith(expect.objectContaining({ delta: 'split' }));
  });

  it('surfaces an unterminated SSE error frame instead of reporting a missing final response', async () => {
    mockStreamResponse(['event: error\ndata: {"type":"error","message":"provider disconnected"}']);

    await expect(streamAgentMessage(createAgentRequest())).rejects.toThrow('provider disconnected');
  });

  it('passes an abort signal through to the streaming fetch request', async () => {
    const abortController = new AbortController();
    const finalResponse = createAgentResponse({ reply: 'abort signal wired' });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
      new Response(createStreamBody([
        `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
      ]), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(streamAgentMessage(createAgentRequest(), { signal: abortController.signal })).resolves.toMatchObject({
      reply: 'abort signal wired'
    });
    expect(fetchMock.mock.calls[0]?.[1]?.signal).toBe(abortController.signal);
  });

  it('rejects with AbortError when the provided signal is aborted', async () => {
    const abortController = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener(
              'abort',
              () => reject(new DOMException('The operation was aborted.', 'AbortError')),
              { once: true }
            );
          })
      )
    );

    const result = streamAgentMessage(createAgentRequest(), { signal: abortController.signal });
    abortController.abort();

    await expect(result).rejects.toMatchObject({ name: 'AbortError' });
  });
});

describe('auth api', () => {
  it('discovers the current Auralith backend before accepting a legacy healthy local process', async () => {
    __setApiDiscoveryForTests(true);
    const session = createAuthSession();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ ok: true, ready: true, app: 'Aegis Coding AI' }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, ready: true, app: 'Aegis Coding AI' }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, ready: true, app: 'Auralith OS' }))
      .mockResolvedValueOnce(jsonResponse(session));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      registerAccount({
        name: 'Gabriel',
        email: 'gabriel@example.com',
        password: 'password123',
        confirm_password: 'password123'
      })
    ).resolves.toMatchObject({ token: 'aegis_test_token' });

    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
      '/api/health',
      'http://127.0.0.1:8787/api/health',
      'http://127.0.0.1:8793/api/health',
      'http://127.0.0.1:8793/api/auth/register'
    ]);
  });

  it('falls through stale local API bases when register is missing on an older backend', async () => {
    const session = createAuthSession();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not Found' }, 404, 'Not Found'))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not Found' }, 404, 'Not Found'))
      .mockResolvedValueOnce(jsonResponse(session));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      registerAccount({
        name: 'Gabriel',
        email: 'gabriel@example.com',
        password: 'password123',
        confirm_password: 'password123'
      })
    ).resolves.toMatchObject({ token: 'aegis_test_token' });

    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
      '/api/auth/register',
      'http://127.0.0.1:8787/api/auth/register',
      'http://127.0.0.1:8793/api/auth/register'
    ]);
  });

  it('does not hide real auth validation errors behind API base fallback', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: 'Passwords do not match.' }, 400, 'Bad Request'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      registerAccount({
        name: 'Gabriel',
        email: 'gabriel@example.com',
        password: 'password123',
        confirm_password: 'different'
      })
    ).rejects.toThrow('Passwords do not match.');

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('creates sessions, sends bearer tokens, and requests password recovery', async () => {
    const session = createAuthSession();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/logout')) {
        return jsonResponse({ message: 'Signed out.' });
      }
      if (url.includes('/forgot-password')) {
        return jsonResponse({ message: 'If the account exists, a recovery flow has been started.' });
      }
      return jsonResponse(session);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      registerAccount({
        name: 'Gabriel',
        email: 'gabriel@example.com',
        password: 'password123',
        confirm_password: 'password123'
      })
    ).resolves.toMatchObject({ token: 'aegis_test_token' });
    await expect(loginAccount({ email: 'gabriel@example.com', password: 'password123', remember_me: true })).resolves.toMatchObject({
      user: { email: 'gabriel@example.com' }
    });
    await expect(getCurrentAccount('aegis_test_token')).resolves.toMatchObject({
      user: { name: 'Gabriel' }
    });
    await expect(logoutAccount('aegis_test_token')).resolves.toMatchObject({ message: 'Signed out.' });
    await expect(requestPasswordReset({ email: 'gabriel@example.com' })).resolves.toHaveProperty('message');

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/auth/register');
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({
        name: 'Gabriel',
        email: 'gabriel@example.com',
        password: 'password123',
        confirm_password: 'password123'
      })
    });
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/auth/login');
    expect(fetchMock.mock.calls[2]?.[1]?.headers).toMatchObject({ Authorization: 'Bearer aegis_test_token' });
    expect(fetchMock.mock.calls[3]?.[1]?.headers).toMatchObject({ Authorization: 'Bearer aegis_test_token' });
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain('/api/auth/forgot-password');
  });
});

describe('workspace intelligence api', () => {
  it('loads snapshot, events, recommendations, and scheduled jobs with workspace query parameters', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/events')) {
        return jsonResponse([]);
      }
      if (url.includes('/recommendations')) {
        return jsonResponse([]);
      }
      if (url.includes('/jobs')) {
        return jsonResponse([createScheduledJob()]);
      }
      return jsonResponse(createWorkspaceOperationsSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getWorkspaceIntelligence('C:/project root')).resolves.toMatchObject({
      workspace_root: 'C:/project root'
    });
    await expect(getWorkspaceIntelligenceEvents('C:/project root', 12)).resolves.toEqual([]);
    await expect(getWorkspaceRecommendations('C:/project root', true)).resolves.toEqual([]);
    await expect(getWorkspaceIntelligenceJobs('C:/project root')).resolves.toHaveLength(1);

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/workspace-intelligence?workspace_root=C%3A%2Fproject+root');
    expect(urls[1]).toContain('/api/workspace-intelligence/events?limit=12&workspace_root=C%3A%2Fproject+root');
    expect(urls[2]).toContain('/api/workspace-intelligence/recommendations?include_dismissed=true&workspace_root=C%3A%2Fproject+root');
    expect(urls[3]).toContain('/api/workspace-intelligence/jobs?workspace_root=C%3A%2Fproject+root');
  });

  it('posts scan, recommendation action, and scheduled job requests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith('/scan')) {
        return jsonResponse(createWorkspaceOperationsSnapshot());
      }
      if (url.endsWith('/dismiss') || url.endsWith('/fix')) {
        return jsonResponse({
          recommendation: createRecommendation(),
          task: null,
          event: null,
          message: 'recorded'
        });
      }
      if (url.endsWith('/jobs/run')) {
        return jsonResponse({
          workspace_root: 'C:/project root',
          jobs: [createScheduledJob()],
          snapshot: createWorkspaceOperationsSnapshot(),
          warnings: []
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    await scanWorkspaceIntelligence({ workspace_root: 'C:/project root', include_git: true });
    await dismissWorkspaceRecommendation('rec-1', { reason: 'later' });
    await fixWorkspaceRecommendation('rec-1', { reason: 'now', create_task: true });
    await runWorkspaceIntelligenceJobs({ workspace_root: 'C:/project root', job_ids: ['validation_snapshot'] });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', include_git: true })
    });
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/workspace-intelligence/recommendations/rec-1/dismiss');
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('/api/workspace-intelligence/recommendations/rec-1/fix');
    expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', job_ids: ['validation_snapshot'] })
    });
  });
});

describe('distributed runtime api', () => {
  it('loads runtime, observability, workers, queue, audit, and sync manifests with expected query parameters', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/observability')) {
        return jsonResponse(createRuntimeObservability());
      }
      if (url.includes('/workers')) {
        return jsonResponse([createWorker()]);
      }
      if (url.includes('/queue')) {
        return jsonResponse([createQueueItem()]);
      }
      if (url.includes('/audit')) {
        return jsonResponse([createAuditEvent()]);
      }
      if (url.includes('/sync/manifests')) {
        return jsonResponse([createSyncManifest()]);
      }
      return jsonResponse(createDistributedRuntimeSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getDistributedRuntime('C:/project root')).resolves.toMatchObject({ execution_mode: 'local' });
    await expect(getRuntimeObservability('C:/project root')).resolves.toMatchObject({ workers_total: 1 });
    await expect(listRuntimeWorkers('C:/project root')).resolves.toHaveLength(1);
    await expect(listExecutionQueue('C:/project root', { status: 'queued', limit: 5 })).resolves.toHaveLength(1);
    await expect(getDistributedRuntimeAudit({ workerId: 'local-runtime', limit: 7 })).resolves.toHaveLength(1);
    await expect(listRemoteSyncManifests('C:/project root', 3)).resolves.toHaveLength(1);

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/distributed-runtime?workspace_root=C%3A%2Fproject+root');
    expect(urls[1]).toContain('/api/distributed-runtime/observability?workspace_root=C%3A%2Fproject+root');
    expect(urls[2]).toContain('/api/distributed-runtime/workers?workspace_root=C%3A%2Fproject+root');
    expect(urls[3]).toContain('/api/distributed-runtime/queue?limit=5&workspace_root=C%3A%2Fproject+root&status=queued');
    expect(urls[4]).toContain('/api/distributed-runtime/audit?limit=7&worker_id=local-runtime');
    expect(urls[5]).toContain('/api/distributed-runtime/sync/manifests?limit=3&workspace_root=C%3A%2Fproject+root');
  });

  it('posts worker, queue, dispatch, route, retry, cancel, and sync requests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/workers/register')) {
        return jsonResponse(createWorker({ worker_id: 'remote-1', kind: 'remote' }));
      }
      if (url.endsWith('/queue')) {
        return jsonResponse(createQueueItem({ id: 'job-1' }));
      }
      if (url.endsWith('/dispatch')) {
        return jsonResponse({ jobs: [createQueueItem({ id: 'job-1', status: 'succeeded' })], workers: [createWorker()], events: [createAuditEvent()], warnings: [] });
      }
      if (url.endsWith('/route')) {
        return jsonResponse(createRouteDecision());
      }
      if (url.endsWith('/retry')) {
        return jsonResponse(createQueueItem({ id: 'job-1', status: 'retrying' }));
      }
      if (url.endsWith('/cancel')) {
        return jsonResponse(createQueueItem({ id: 'job-1', status: 'canceled' }));
      }
      if (url.endsWith('/sync/export')) {
        return jsonResponse(createSyncManifest());
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    await registerRuntimeWorker({ worker_id: 'remote-1', name: 'Remote', kind: 'remote' });
    await createExecutionQueueItem({ workspace_root: 'C:/project root', kind: 'validation', title: 'Validate' });
    await dispatchExecutionQueue({ workspace_root: 'C:/project root', allow_commands: false });
    await routeDistributedModel({ workspace_root: 'C:/project root', privacy: 'local_only' });
    await retryExecutionQueueItem('job-1', { reason: 'try again' });
    await cancelExecutionQueueItem('job-1', { reason: 'stop' });
    await createRemoteSyncManifest({ workspace_root: 'C:/project root', sections: ['settings'] });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', kind: 'validation', title: 'Validate' })
    });
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', allow_commands: false })
    });
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain('/api/distributed-runtime/queue/job-1/retry');
    expect(String(fetchMock.mock.calls[5]?.[0])).toContain('/api/distributed-runtime/queue/job-1/cancel');
    expect(String(fetchMock.mock.calls[6]?.[0])).toContain('/api/distributed-runtime/sync/export');
  });
});

describe('unified runtime api', () => {
  it('loads the unified runtime map with workspace query parameters', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse(createUnifiedRuntimeSnapshot())
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getUnifiedRuntime('C:/project root')).resolves.toMatchObject({
      runtime_name: 'Auralith Runtime',
      mode: 'local-first'
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/unified-runtime?workspace_root=C%3A%2Fproject+root');
  });
});

describe('operating environment api', () => {
  it('loads capability map and previews guarded actions', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/actions/preview')) {
        return jsonResponse({
          request_id: 'op-preview-1',
          capability_id: 'desktop_control',
          action: 'launch_app',
          status: 'blocked',
          allowed: false,
          approval_required: true,
          reason: 'Execution is blocked.',
          summary: 'Desktop control is blocked.',
          required_permissions: ['keyboard_mouse'],
          rollback_supported: false,
          safety_notes: ['No desktop mutation is performed.'],
          event: null
        });
      }
      return jsonResponse(createOperatingEnvironmentSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getOperatingEnvironment('C:/project root')).resolves.toMatchObject({
      runtime_name: 'Auralith OS',
      execution_mode: 'control-plane'
    });
    await expect(
      previewOperatingEnvironmentAction({
        workspace_root: 'C:/project root',
        capability_id: 'desktop_control',
        action: 'launch_app',
        parameters: { app: 'notepad' }
      })
    ).resolves.toMatchObject({ status: 'blocked', allowed: false });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/operating-environment?workspace_root=C%3A%2Fproject+root');
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/operating-environment/actions/preview');
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({
        workspace_root: 'C:/project root',
        capability_id: 'desktop_control',
        action: 'launch_app',
        parameters: { app: 'notepad' }
      })
    });
  });
});

describe('unified context and global command api', () => {
  it('loads context, searches records, and previews global commands', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/unified-context/search')) {
        const context = createUnifiedContextSnapshot();
        return jsonResponse({
          query: 'mockup',
          workspace_root: 'C:/project root',
          generated_at: '2026-05-07T00:00:00Z',
          results: [
            {
              record: context.records[1],
              score: 1,
              matched_fields: ['summary'],
              relationships: []
            }
          ],
          scope_summary: { media_asset: 1 },
          suggestions: ['generated assets']
        });
      }
      if (url.includes('/global-command/')) {
        return jsonResponse(createGlobalCommandResponse());
      }
      return jsonResponse(createUnifiedContextSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getUnifiedContext('C:/project root')).resolves.toMatchObject({
      workspace_root: 'C:/project root',
      records: expect.any(Array)
    });
    await expect(searchUnifiedContext({ workspace_root: 'C:/project root', query: 'mockup', limit: 5 })).resolves.toMatchObject({
      query: 'mockup',
      results: expect.any(Array)
    });
    await expect(
      previewGlobalCommand({
        workspace_root: 'C:/project root',
        command: 'Refactor using the latest mockup',
        entrypoint: 'command_palette'
      })
    ).resolves.toMatchObject({ route: { target_system: 'task_engine' } });
    await expect(
      submitGlobalCommand({
        workspace_root: 'C:/project root',
        command: 'Refactor using the latest mockup',
        create_task: true
      })
    ).resolves.toMatchObject({ route: { creates_task: true } });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/unified-context?workspace_root=C%3A%2Fproject+root');
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/unified-context/search');
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('/api/global-command/preview');
    expect(String(fetchMock.mock.calls[3]?.[0])).toContain('/api/global-command/submit');
  });
});

describe('continuity api', () => {
  it('loads presence continuity and searches the operating timeline', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/timeline/search')) {
        const continuity = createContinuitySnapshot();
        return jsonResponse({
          query: 'validate',
          workspace_root: 'C:/project root',
          generated_at: '2026-05-07T00:00:00Z',
          results: continuity.timeline.entries,
          suggestions: ['validation failures']
        });
      }
      return jsonResponse(createContinuitySnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getContinuity('C:/project root')).resolves.toMatchObject({
      presence: { status: 'focused' },
      workspace_state: { restore_readiness: 'ready' }
    });
    await expect(searchContinuityTimeline({ workspace_root: 'C:/project root', query: 'validate', limit: 5 })).resolves.toMatchObject({
      query: 'validate',
      results: expect.any(Array)
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/continuity?workspace_root=C%3A%2Fproject+root');
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/continuity/timeline/search');
  });
});

describe('platform discipline api', () => {
  it('loads the platform discipline contract with workspace query parameters', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse(createPlatformDisciplineSnapshot())
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getPlatformDiscipline('C:/project root')).resolves.toMatchObject({
      core_identity: expect.stringContaining('local-first'),
      stewardship: {
        id: 'platform_stewardship',
        preserve: expect.arrayContaining(['trust'])
      },
      feature_admission: {
        default_decision: 'reject_when_unclear',
        hard_no_rules: expect.arrayContaining(['Say no to unclear value.'])
      },
      primary_domains: expect.arrayContaining([expect.objectContaining({ id: 'coding_workspace' })]),
      stability_tiers: expect.arrayContaining([expect.objectContaining({ id: 'stable_runtime' })]),
      deprecated_count: 2
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/platform-discipline?workspace_root=C%3A%2Fproject+root');
  });
});

describe('adaptive intelligence api', () => {
  it('loads adaptive snapshots and outcomes with workspace query parameters', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/outcomes')) {
        return jsonResponse([createAdaptiveOutcome()]);
      }
      return jsonResponse(createAdaptiveSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getAdaptiveIntelligence('C:/project root', { limit: 12, refresh: true })).resolves.toMatchObject({
      workspace_root: 'C:/project root'
    });
    await expect(listAdaptiveTaskOutcomes('C:/project root', { limit: 8, refresh: true })).resolves.toHaveLength(1);

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/adaptive-intelligence?limit=12&workspace_root=C%3A%2Fproject+root&refresh=true');
    expect(urls[1]).toContain('/api/adaptive-intelligence/outcomes?limit=8&workspace_root=C%3A%2Fproject+root&refresh=true');
  });

  it('posts profile activation, rollback, benchmark, and replay requests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/benchmarks/run')) {
        return jsonResponse([createAdaptiveBenchmark()]);
      }
      if (url.includes('/replay')) {
        return jsonResponse([createAdaptiveReplay()]);
      }
      return jsonResponse(createAdaptiveSnapshot({ active_profile: createAdaptivePolicyProfile({ id: 'balanced_hybrid', name: 'Balanced Hybrid', active: true }) }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await activateAdaptivePolicyProfile('balanced_hybrid', { reason: 'try hybrid' }, 'C:/project root');
    await rollbackAdaptivePolicy({ checkpoint_id: 'checkpoint-1', reason: 'undo' });
    await runAdaptiveBenchmarks({ workspace_root: 'C:/project root', suite_ids: ['reasoning'] });
    await replayAdaptiveTasks({ workspace_root: 'C:/project root', limit: 3 });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/adaptive-intelligence/policies/balanced_hybrid/activate');
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ reason: 'try hybrid' })
    });
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/adaptive-intelligence/policies/rollback');
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ checkpoint_id: 'checkpoint-1', reason: 'undo' })
    });
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', suite_ids: ['reasoning'] })
    });
    expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ workspace_root: 'C:/project root', limit: 3 })
    });
  });
});

describe('productization api', () => {
  it('loads hardening snapshot, stable APIs, recovery, metrics, plugins, and policy', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/stable-apis')) {
        return jsonResponse([createStableApi()]);
      }
      if (url.includes('/recovery')) {
        return jsonResponse(createRuntimeRecovery());
      }
      if (url.includes('/reliability')) {
        return jsonResponse([createReliabilityMetric()]);
      }
      if (url.includes('/plugins')) {
        return jsonResponse([createPluginManifest()]);
      }
      if (url.includes('/enterprise-policy')) {
        return jsonResponse(createEnterprisePolicy());
      }
      return jsonResponse(createProductizationSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getProductization('C:/project root', { refreshMetrics: true })).resolves.toMatchObject({
      api_version: '2026.05.07'
    });
    await expect(refreshProductization({ workspace_root: 'C:/project root', refresh_metrics: true })).resolves.toMatchObject({
      workspace_root: 'C:/project root'
    });
    await expect(listStableApis()).resolves.toHaveLength(1);
    await expect(getRuntimeRecovery('C:/project root')).resolves.toMatchObject({ safe_shutdown_ready: true });
    await expect(getReliabilityMetrics('C:/project root')).resolves.toHaveLength(1);
    await expect(listPlugins(false)).resolves.toHaveLength(1);
    await expect(getEnterprisePolicy()).resolves.toMatchObject({ id: 'local_first_default' });

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/productization?workspace_root=C%3A%2Fproject+root&refresh_metrics=true');
    expect(urls[1]).toContain('/api/productization/refresh');
    expect(urls[2]).toContain('/api/productization/stable-apis');
    expect(urls[3]).toContain('/api/productization/recovery?workspace_root=C%3A%2Fproject+root');
    expect(urls[4]).toContain('/api/productization/reliability?workspace_root=C%3A%2Fproject+root');
    expect(urls[5]).toContain('/api/productization/plugins?include_disabled=false');
    expect(urls[6]).toContain('/api/productization/enterprise-policy');
  });

  it('posts plugin lifecycle and enterprise policy requests', async () => {
    const plugin = createPluginManifest();
    const policy = createEnterprisePolicy({ plugin_signing_required: true });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/validate')) {
        return jsonResponse(createPluginValidation());
      }
      if (url.includes('/enterprise-policy')) {
        return jsonResponse(policy);
      }
      return jsonResponse(plugin);
    });
    vi.stubGlobal('fetch', fetchMock);

    await validatePlugin({ manifest: plugin });
    await registerPlugin({ manifest: plugin, enable: false, trust: false, reason: 'test' });
    await enablePlugin(plugin.id, { reason: 'enable' });
    await disablePlugin(plugin.id, { reason: 'disable' });
    await trustPlugin(plugin.id, { reason: 'trust' });
    await updateEnterprisePolicy({ profile: policy, reason: 'lock down' });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ manifest: plugin })
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ manifest: plugin, enable: false, trust: false, reason: 'test' })
    });
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain(`/api/productization/plugins/${plugin.id}/enable`);
    expect(String(fetchMock.mock.calls[3]?.[0])).toContain(`/api/productization/plugins/${plugin.id}/disable`);
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain(`/api/productization/plugins/${plugin.id}/trust`);
    expect(fetchMock.mock.calls[5]?.[1]).toMatchObject({
      method: 'PUT',
      body: JSON.stringify({ profile: policy, reason: 'lock down' })
    });
  });
});

describe('ecosystem api', () => {
  it('loads ecosystem snapshot, marketplace, workflows, graph, policy, reproducibility, and audit', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/marketplace')) return jsonResponse([createEcosystemPackage()]);
      if (url.includes('/packages?')) return jsonResponse([createEcosystemPackage()]);
      if (url.includes('/workflows')) return jsonResponse([createEcosystemWorkflow()]);
      if (url.includes('/shared-profiles?')) return jsonResponse([createSharedProfile()]);
      if (url.includes('/org-policy')) return jsonResponse(createOrganizationPolicy());
      if (url.includes('/knowledge-graph')) return jsonResponse(createKnowledgeGraph());
      if (url.includes('/reproducibility?')) return jsonResponse([createReproducibilityRecordFixture()]);
      if (url.includes('/audit')) return jsonResponse([createEcosystemAuditEvent()]);
      return jsonResponse(createEcosystemSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getEcosystem('C:/project root', { rebuildGraph: true, query: 'api route' })).resolves.toMatchObject({
      api_version: '2026.05.07'
    });
    await expect(refreshEcosystem({ workspace_root: 'C:/project root', rebuild_graph: true })).resolves.toMatchObject({
      workspace_root: 'C:/project root'
    });
    await expect(listEcosystemMarketplace()).resolves.toHaveLength(1);
    await expect(listEcosystemPackages(false)).resolves.toHaveLength(1);
    await expect(listEcosystemWorkflows(false)).resolves.toHaveLength(1);
    await expect(listSharedIntelligenceProfiles('validation_profile')).resolves.toHaveLength(1);
    await expect(getOrganizationPolicy()).resolves.toMatchObject({ id: 'local_organization_policy' });
    await expect(getKnowledgeGraph('C:/project root', true)).resolves.toMatchObject({ modules_total: 1 });
    await expect(listReproducibilityRecords('C:/project root')).resolves.toHaveLength(1);
    await expect(listEcosystemAudit(10)).resolves.toHaveLength(1);

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/ecosystem?workspace_root=C%3A%2Fproject+root&rebuild_graph=true&query=api+route');
    expect(urls[1]).toContain('/api/ecosystem/refresh');
    expect(urls[2]).toContain('/api/ecosystem/marketplace');
    expect(urls[3]).toContain('/api/ecosystem/packages?include_disabled=false');
    expect(urls[4]).toContain('/api/ecosystem/workflows?include_disabled=false');
    expect(urls[5]).toContain('/api/ecosystem/shared-profiles?limit=50&kind=validation_profile');
    expect(urls[6]).toContain('/api/ecosystem/org-policy');
    expect(urls[7]).toContain('/api/ecosystem/knowledge-graph?rebuild=true&workspace_root=C%3A%2Fproject+root');
    expect(urls[8]).toContain('/api/ecosystem/reproducibility?limit=20&workspace_root=C%3A%2Fproject+root');
    expect(urls[9]).toContain('/api/ecosystem/audit?limit=10');
  });

  it('posts package lifecycle, workflow, shared profile, policy, search, and reproducibility requests', async () => {
    const packageManifest = createEcosystemPackage();
    const workflow = createEcosystemWorkflow();
    const shared = createSharedProfile();
    const policy = createOrganizationPolicy({ require_signed_packages: true });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/packages/validate')) return jsonResponse(createEcosystemValidation());
      if (url.includes('/workflows/debugging_pipeline/run')) return jsonResponse(createWorkflowRun());
      if (url.includes('/shared-profiles/export-current')) return jsonResponse(createSharedProfileExport());
      if (url.includes('/shared-profiles/') && url.endsWith('/export')) return jsonResponse(createSharedProfileExport());
      if (url.includes('/shared-profiles/import')) return jsonResponse(shared);
      if (url.includes('/org-policy')) return jsonResponse(policy);
      if (url.includes('/search')) return jsonResponse(createEcosystemSearch());
      if (url.includes('/reproducibility')) return jsonResponse(createReproducibilityRecordFixture());
      if (url.includes('/workflows/register')) return jsonResponse(workflow);
      return jsonResponse(packageManifest);
    });
    vi.stubGlobal('fetch', fetchMock);

    await validateEcosystemPackage({ manifest: packageManifest });
    await registerEcosystemPackage({ manifest: packageManifest, enable: false, trust_level: 'reviewed', reason: 'test' });
    await enableEcosystemPackage(packageManifest.id, { reason: 'enable' });
    await disableEcosystemPackage(packageManifest.id, { reason: 'disable' });
    await trustEcosystemPackage(packageManifest.id, { trust_level: 'trusted', reason: 'trust' });
    await registerEcosystemWorkflow(workflow);
    await runEcosystemWorkflow('debugging_pipeline', { workspace_root: 'C:/project root', user_goal: 'Debug API' });
    await importSharedIntelligenceProfile({ profile: shared, reason: 'test' });
    await exportSharedIntelligenceProfile(shared.id);
    await exportCurrentProjectIntelligence('C:/project root');
    await updateOrganizationPolicy({ profile: policy, reason: 'lock down' });
    await searchEcosystem({ workspace_root: 'C:/project root', query: 'api route' });
    await createReproducibilityRecord({ workspace_root: 'C:/project root', task_id: 'task-1' });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ manifest: packageManifest })
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ manifest: packageManifest, enable: false, trust_level: 'reviewed', reason: 'test' })
    });
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain(`/api/ecosystem/packages/${packageManifest.id}/enable`);
    expect(String(fetchMock.mock.calls[3]?.[0])).toContain(`/api/ecosystem/packages/${packageManifest.id}/disable`);
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain(`/api/ecosystem/packages/${packageManifest.id}/trust`);
    expect(fetchMock.mock.calls[5]?.[1]).toMatchObject({ method: 'POST', body: JSON.stringify(workflow) });
    expect(String(fetchMock.mock.calls[6]?.[0])).toContain('/api/ecosystem/workflows/debugging_pipeline/run');
    expect(String(fetchMock.mock.calls[9]?.[0])).toContain('/api/ecosystem/shared-profiles/export-current?workspace_root=C%3A%2Fproject+root');
    expect(fetchMock.mock.calls[10]?.[1]).toMatchObject({
      method: 'PUT',
      body: JSON.stringify({ profile: policy, reason: 'lock down' })
    });
    expect(String(fetchMock.mock.calls[11]?.[0])).toContain('/api/ecosystem/search');
    expect(String(fetchMock.mock.calls[12]?.[0])).toContain('/api/ecosystem/reproducibility');
  });
});

describe('autonomous engineering api', () => {
  it('loads autonomous snapshots, objectives, gates, and objective details', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/approval-gates')) return jsonResponse([createAutonomousGate()]);
      if (url.includes('/objectives?')) return jsonResponse([createAutonomousObjectiveFixture()]);
      if (url.includes('/objectives/objective-1')) return jsonResponse(createAutonomousObjectiveDetail());
      return jsonResponse(createAutonomousSnapshot());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getAutonomousEngineering('C:/project root')).resolves.toMatchObject({
      api_version: '2026.05.07'
    });
    await expect(listAutonomousObjectives('C:/project root', { includeCompleted: false, limit: 12 })).resolves.toHaveLength(1);
    await expect(listAutonomousApprovalGates('C:/project root', 8)).resolves.toHaveLength(1);
    await expect(getAutonomousObjective('objective-1')).resolves.toMatchObject({
      objective: { id: 'objective-1' }
    });

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/autonomous-engineering?workspace_root=C%3A%2Fproject+root');
    expect(urls[1]).toContain('/api/autonomous-engineering/objectives?include_completed=false&limit=12&workspace_root=C%3A%2Fproject+root');
    expect(urls[2]).toContain('/api/autonomous-engineering/approval-gates?limit=8&workspace_root=C%3A%2Fproject+root');
    expect(urls[3]).toContain('/api/autonomous-engineering/objectives/objective-1');
  });

  it('posts autonomous objective lifecycle and approval gate actions', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/simulate')) return jsonResponse(createAutonomousSimulation());
      return jsonResponse(createAutonomousObjectiveDetail());
    });
    vi.stubGlobal('fetch', fetchMock);

    await createAutonomousObjective({
      workspace_root: 'C:/project root',
      title: 'Improve test coverage',
      user_goal: 'Improve test coverage safely',
      dry_run: true
    });
    await startAutonomousObjective('objective-1', { reason: 'start' });
    await iterateAutonomousObjective('objective-1', { reason: 'advance', max_steps: 2, allow_repairs: true });
    await simulateAutonomousObjective('objective-1');
    await pauseAutonomousObjective('objective-1', { reason: 'pause' });
    await cancelAutonomousObjective('objective-1', { reason: 'cancel' });
    await approveAutonomousGate('gate-1', { reason: 'ok', resolved_by: 'tester' });
    await rejectAutonomousGate('gate-1', { reason: 'too risky' });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({
        workspace_root: 'C:/project root',
        title: 'Improve test coverage',
        user_goal: 'Improve test coverage safely',
        dry_run: true
      })
    });
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/autonomous-engineering/objectives/objective-1/start');
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ reason: 'advance', max_steps: 2, allow_repairs: true })
    });
    expect(String(fetchMock.mock.calls[3]?.[0])).toContain('/api/autonomous-engineering/objectives/objective-1/simulate');
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain('/api/autonomous-engineering/objectives/objective-1/pause');
    expect(String(fetchMock.mock.calls[5]?.[0])).toContain('/api/autonomous-engineering/objectives/objective-1/cancel');
    expect(String(fetchMock.mock.calls[6]?.[0])).toContain('/api/autonomous-engineering/approval-gates/gate-1/approve');
    expect(fetchMock.mock.calls[6]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ reason: 'ok', resolved_by: 'tester' })
    });
    expect(String(fetchMock.mock.calls[7]?.[0])).toContain('/api/autonomous-engineering/approval-gates/gate-1/reject');
  });
});

describe('creative studio api', () => {
  it('loads capabilities, jobs, asset library, and job detail', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/assets')) return jsonResponse(createMediaAssetLibrary());
      if (url.includes('/jobs/job-1')) return jsonResponse(createMediaJob());
      if (url.includes('/jobs?')) return jsonResponse([createMediaJob()]);
      return jsonResponse(createCreativeCapabilities());
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(getCreativeStudio()).resolves.toMatchObject({ can_iterate_from_previous: true });
    await expect(listCreativeJobs({ limit: 8, kind: 'image' })).resolves.toHaveLength(1);
    await expect(getCreativeAssetLibrary({ limit: 12, format: 'png' })).resolves.toMatchObject({ total_assets: 1 });
    await expect(getCreativeJob('job-1')).resolves.toMatchObject({ id: 'job-1' });

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toContain('/api/creative-studio');
    expect(urls[1]).toContain('/api/creative-studio/jobs?limit=8&kind=image');
    expect(urls[2]).toContain('/api/creative-studio/assets?limit=12&format=png');
    expect(urls[3]).toContain('/api/creative-studio/jobs/job-1');
  });

  it('posts creative generation, cancel, and export requests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/export')) return jsonResponse(createMediaExport());
      return jsonResponse(createMediaJob());
    });
    vi.stubGlobal('fetch', fetchMock);

    await createCreativeJob({
      prompt: 'Create a premium mockup',
      kind: 'product_mockup',
      studio: 'image',
      provider_id: 'local_creative_renderer',
      output_formats: ['png', 'svg']
    });
    await cancelCreativeJob('job-1');
    await exportCreativeJob('job-1', { format: 'zip', include_metadata: true });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({
        prompt: 'Create a premium mockup',
        kind: 'product_mockup',
        studio: 'image',
        provider_id: 'local_creative_renderer',
        output_formats: ['png', 'svg']
      })
    });
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/creative-studio/jobs/job-1/cancel');
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('/api/creative-studio/jobs/job-1/export');
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ format: 'zip', include_metadata: true })
    });
  });
});

function createMediaAsset(overrides: Record<string, unknown> = {}) {
  return {
    id: 'job-1:preview.png',
    path: 'C:/project root/workspace/creative_media/job-1/preview.png',
    kind: 'product_mockup',
    format: 'png',
    role: 'raster preview',
    mime_type: 'image/png',
    editable: true,
    derived_from: '',
    thumbnail_path: 'C:/project root/workspace/creative_media/job-1/preview.png',
    metadata: { size_bytes: 1234 },
    ...overrides
  };
}

function createMediaJob(overrides: Record<string, unknown> = {}) {
  return {
    id: 'job-1',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:01Z',
    completed_at: '2026-05-06T00:00:01Z',
    kind: 'product_mockup',
    studio: 'image',
    operation: 'generate',
    status: 'completed',
    provider_id: 'local_creative_renderer',
    provider_name: 'Local Creative Renderer',
    prompt: 'Create a premium mockup',
    effective_prompt: 'Create a premium mockup',
    negative_prompt: '',
    feedback: '',
    previous_job_id: '',
    source_asset_id: '',
    theme_color: '#26dd7b',
    palette: ['#26dd7b', '#7af0ae'],
    aspect_ratio: '16:9',
    style: 'premium',
    seed: 123,
    settings: {},
    output_path: 'C:/project root/workspace/creative_media/job-1',
    cost_estimate_usd: 0,
    time_taken_seconds: 0.2,
    error: '',
    timeline: [createToolEvent({ kind: 'media.job.completed', title: 'Generation completed' })],
    plan: ['Render preview'],
    assets: [createMediaAsset()],
    warnings: [],
    next_actions: [],
    job_dir: 'C:/project root/workspace/creative_media/job-1',
    ...overrides
  };
}

function createCreativeCapabilities() {
  return {
    supported_kinds: ['image', 'product_mockup', 'music_beat', 'voiceover'],
    local_formats: ['png', 'svg', 'wav', 'midi', 'zip'],
    provider_formats: ['png', 'jpg', 'mp4', 'mp3'],
    providers: [
      {
        id: 'local_creative_renderer',
        name: 'Local Creative Renderer',
        category: 'image',
        location: 'local',
        supports: ['image', 'product_mockup'],
        output_formats: ['png', 'svg', 'zip'],
        paid: false,
        gpu_intensive: false,
        requires_approval: false,
        available: true,
        notes: 'Local previews.'
      }
    ],
    prompt_presets: [
      {
        id: 'premium-product-mockup',
        name: 'Premium Product Mockup',
        studio: 'image',
        kind: 'product_mockup',
        prompt_template: 'Create a premium product mockup for {product}',
        negative_prompt: '',
        default_settings: {},
        tags: ['image']
      }
    ],
    can_iterate_from_previous: true,
    theme_inference: true,
    psd_template_strategy: 'Layer manifest plus JSX.',
    local_renderers: { pillow: true, wav_preview: true },
    recommendations: []
  };
}

function createMediaAssetLibrary() {
  return {
    generated_at: '2026-05-06T00:00:00Z',
    base_dir: 'C:/project root/workspace/creative_media',
    jobs: [createMediaJob()],
    assets: [createMediaAsset()],
    total_assets: 1,
    formats: ['png'],
    kinds: ['product_mockup']
  };
}

function createMediaExport() {
  return {
    id: 'export-1',
    created_at: '2026-05-06T00:00:00Z',
    job_id: 'job-1',
    format: 'zip',
    path: 'C:/project root/workspace/creative_media/job-1/exports/export-1.zip',
    assets: [createMediaAsset({ format: 'zip', role: 'exported asset pack' })],
    warnings: []
  };
}

function createAutonomousSafetyLimits(overrides: Record<string, unknown> = {}) {
  return {
    max_iterations: 6,
    max_parallel_agents: 3,
    token_budget: 120000,
    max_file_changes: 20,
    max_dependency_changes: 1,
    max_repair_attempts: 2,
    approval_checkpoint_interval: 1,
    rollback_required: true,
    protected_file_zones: ['.git', 'aegis_config.json'],
    stop_on_validation_failure: true,
    allow_dependency_changes: false,
    allow_destructive_actions: false,
    metadata: {},
    ...overrides
  };
}

function createAutonomousGoalMemory(overrides: Record<string, unknown> = {}) {
  return {
    objective_history: ['Objective created from dry run.'],
    completed_phases: [],
    failed_approaches: [],
    successful_patterns: [],
    remaining_work: ['Approve gated implementation before changes.'],
    user_preferences: ['Prefer dry-run first.'],
    updated_at: '2026-05-06T00:00:00Z',
    ...overrides
  };
}

function createAutonomousObjectiveFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'objective-1',
    workspace_root: 'C:/project root',
    title: 'Improve test coverage',
    user_goal: 'Improve test coverage safely',
    status: 'needs_approval',
    priority: 0,
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    completed_at: '',
    current_phase: 'discovery',
    iteration_count: 0,
    repair_count: 0,
    assigned_agent_roles: ['planner', 'architect', 'code', 'validation'],
    task_ids: ['task-1'],
    phase_ids: ['phase-discovery'],
    approval_gate_ids: ['gate-1'],
    simulation_ids: ['simulation-1'],
    safety_limits: createAutonomousSafetyLimits(),
    goal_memory: createAutonomousGoalMemory(),
    final_summary: '',
    error_summary: '',
    metadata: {},
    ...overrides
  };
}

function createAutonomousPhase(overrides: Record<string, unknown> = {}) {
  return {
    id: 'phase-discovery',
    objective_id: 'objective-1',
    workspace_root: 'C:/project root',
    kind: 'discovery',
    title: 'Discovery',
    status: 'queued',
    summary: 'Inspect project state before planning.',
    started_at: '',
    completed_at: '',
    task_ids: [],
    agent_roles: ['planner', 'architect'],
    validation_commands: [],
    approval_required: false,
    iteration_count: 0,
    error_summary: '',
    metadata: {},
    ...overrides
  };
}

function createAutonomousGate(overrides: Record<string, unknown> = {}) {
  return {
    id: 'gate-1',
    objective_id: 'objective-1',
    phase_id: 'phase-discovery',
    kind: 'architecture_change',
    title: 'Review objective before implementation',
    reason: 'Long-running objectives require explicit supervision before code changes.',
    status: 'pending',
    required: true,
    created_at: '2026-05-06T00:00:00Z',
    resolved_at: '',
    resolved_by: '',
    metadata: {},
    ...overrides
  };
}

function createAutonomousAgent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'agent-planner-objective-1',
    objective_id: 'objective-1',
    phase_id: 'phase-discovery',
    role: 'planner',
    status: 'queued',
    task_id: 'task-1',
    summary: 'Planner will define supervised objective phases.',
    started_at: '',
    completed_at: '',
    metadata: {},
    ...overrides
  };
}

function createAutonomousVerification(overrides: Record<string, unknown> = {}) {
  return {
    id: 'verification-1',
    objective_id: 'objective-1',
    phase_id: 'phase-validation',
    kind: 'continuous_verification',
    command: 'npm run validate',
    status: 'queued',
    detail: 'Validation will run before objective completion.',
    created_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  };
}

function createAutonomousSimulation(overrides: Record<string, unknown> = {}) {
  return {
    id: 'simulation-1',
    objective_id: 'objective-1',
    workspace_root: 'C:/project root',
    created_at: '2026-05-06T00:00:00Z',
    estimated_impact: 'medium',
    predicted_validation_risk: 0.35,
    projected_file_changes: ['src/app.ts'],
    projected_dependency_changes: [],
    projected_token_cost: 48000,
    projected_iterations: 3,
    dry_run_plan: ['Discover', 'Plan', 'Validate'],
    approval_gates: [createAutonomousGate()],
    warnings: ['Dry run only; no files changed.'],
    metadata: {},
    ...overrides
  };
}

function createAutonomousRefactorPlan(overrides: Record<string, unknown> = {}) {
  return {
    id: 'refactor-1',
    objective_id: 'objective-1',
    kind: 'coverage_expansion',
    title: 'Expand focused tests',
    target_patterns: ['tests/**/*.py'],
    projected_files: ['tests/test_app.py'],
    safety_notes: ['Checkpoint before edits.'],
    approval_required: true,
    status: 'draft',
    metadata: {},
    ...overrides
  };
}

function createAutonomousExplanation(overrides: Record<string, unknown> = {}) {
  return {
    id: 'explain-1',
    objective_id: 'objective-1',
    created_at: '2026-05-06T00:00:00Z',
    category: 'routing',
    title: 'Dry run selected',
    detail: 'The objective starts in simulation mode so projected impact is visible before changes.',
    evidence: {},
    ...overrides
  };
}

function createAutonomousMetric(overrides: Record<string, unknown> = {}) {
  return {
    name: 'objective_completion_rate',
    value: 1,
    unit: 'ratio',
    status: 'healthy',
    detail: 'Completed objectives are healthy.',
    trend: 'stable',
    metadata: {},
    ...overrides
  };
}

function createAutonomousObjectiveDetail(overrides: Record<string, unknown> = {}) {
  return {
    objective: createAutonomousObjectiveFixture(),
    phases: [createAutonomousPhase()],
    approval_gates: [createAutonomousGate()],
    simulations: [createAutonomousSimulation()],
    agents: [createAutonomousAgent()],
    verification: [createAutonomousVerification()],
    refactor_plans: [createAutonomousRefactorPlan()],
    explanations: [createAutonomousExplanation()],
    task_events: [createToolEvent()],
    ...overrides
  };
}

function createAutonomousSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    api_version: '2026.05.07',
    objectives: [createAutonomousObjectiveFixture()],
    active_objectives: [createAutonomousObjectiveFixture()],
    phases: [createAutonomousPhase()],
    approval_gates: [createAutonomousGate()],
    simulations: [createAutonomousSimulation()],
    agents: [createAutonomousAgent()],
    verification: [createAutonomousVerification()],
    refactor_plans: [createAutonomousRefactorPlan()],
    explanations: [createAutonomousExplanation()],
    analytics: [createAutonomousMetric()],
    recommendations: ['Approve the objective before implementation.'],
    warnings: [],
    ...overrides
  };
}

function mockStreamResponse(chunks: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(createStreamBody(chunks), {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' }
    }))
  );
}

function jsonResponse(payload: unknown, status = 200, statusText = 'OK') {
  return new Response(JSON.stringify(payload), {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' }
  });
}

function createAuthSession() {
  return {
    token: 'aegis_test_token',
    token_type: 'bearer',
    expires_at: '2026-05-08T00:00:00Z',
    user: {
      id: 'user-1',
      name: 'Gabriel',
      email: 'gabriel@example.com',
      plan: 'pro',
      role: 'user',
      status: 'active',
      created_at: '2026-05-07T00:00:00Z'
    }
  };
}

function createStreamBody(chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    }
  });
}

function sseFrame(event: string, payload: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}

function createAgentRequest(): AgentRequest {
  return {
    message: 'test',
    history: [],
    apply_changes: false,
    run_validation: false
  };
}

function createAgentResponse(overrides: Partial<AgentResponse> = {}): AgentResponse {
  return {
    task_id: 'stream-test',
    reply: 'done',
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
    workspace_root: 'workspace',
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

function createAdaptivePolicyProfile(overrides: Record<string, unknown> = {}) {
  return {
    id: 'local_privacy_first',
    name: 'Local Privacy-First',
    description: 'Prefer local routes.',
    privacy_mode: 'local-first',
    routing_strategy: 'privacy',
    cost_priority: 0.7,
    latency_priority: 0.5,
    reasoning_bias: 0.45,
    max_context_pressure: 0.8,
    allow_cloud: false,
    allow_remote_workers: false,
    auto_apply_policy: false,
    review_required: true,
    active: true,
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    score_weights: { success: 0.4 },
    metadata: {},
    ...overrides
  };
}

function createAdaptiveOutcome(overrides: Record<string, unknown> = {}) {
  return {
    id: 'outcome-task-1',
    task_id: 'task-1',
    project_id: 'C:/project root',
    workspace_root: 'C:/project root',
    title: 'Refactor module',
    status: 'completed',
    outcome: 'success',
    success: true,
    repair_count: 0,
    validation_runs: 1,
    validation_passes: 1,
    validation_failures: 0,
    validation_pass_rate: 1,
    retry_count: 0,
    approval_count: 1,
    rejection_count: 0,
    rollback_count: 0,
    completion_time_seconds: 12,
    input_tokens: 1000,
    output_tokens: 400,
    estimated_cost_usd: 0,
    model_used: 'qwen2.5-coder:7b',
    provider_id: 'local-code',
    route_role: 'code',
    routing_path: ['local-code'],
    context_files: ['src/app.ts'],
    memory_refs: ['memory:style'],
    checkpoints: ['checkpoint-1'],
    error_summary: '',
    final_summary: 'Done',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:01:00Z',
    completed_at: '2026-05-06T00:01:00Z',
    metadata: {},
    ...overrides
  };
}

function createAdaptiveBenchmark(overrides: Record<string, unknown> = {}) {
  return {
    id: 'benchmark-1',
    workspace_root: 'C:/project root',
    created_at: '2026-05-06T00:00:00Z',
    suite_id: 'reasoning',
    suite_label: 'Reasoning',
    status: 'passed',
    baseline_score: 0.8,
    candidate_score: 0.82,
    regression_detected: false,
    reproducibility_key: 'abc123',
    metrics: { task_success_rate: 1 },
    recommendations: [],
    warnings: [],
    ...overrides
  };
}

function createAdaptiveReplay(overrides: Record<string, unknown> = {}) {
  return {
    id: 'replay-1',
    workspace_root: 'C:/project root',
    created_at: '2026-05-06T00:00:00Z',
    source_task_id: 'task-1',
    status: 'matched',
    previous_score: 0.84,
    replay_score: 0.85,
    regression_detected: false,
    previous_route: ['local-code'],
    replay_route: ['local-code'],
    differences: [],
    recommendations: [],
    metadata: {},
    ...overrides
  };
}

function createAdaptiveSnapshot(overrides: Record<string, unknown> = {}) {
  const activeProfile = createAdaptivePolicyProfile();
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    active_profile: activeProfile,
    profiles: [activeProfile, createAdaptivePolicyProfile({ id: 'balanced_hybrid', name: 'Balanced Hybrid', active: false })],
    outcomes: [createAdaptiveOutcome()],
    quality_scores: [
      {
        dimension: 'task_completion',
        key: '',
        label: 'Task Completion',
        score: 1,
        confidence: 0.5,
        sample_size: 1,
        trend: 'stable',
        reasons: ['1 of 1 succeeded.'],
        recommendations: [],
        metadata: {}
      }
    ],
    route_recommendations: [
      {
        provider_id: 'local-code',
        provider_label: 'Local Code',
        model: 'qwen2.5-coder:7b',
        role: 'code',
        profile_id: 'local_privacy_first',
        action: 'prefer',
        score: 0.9,
        confidence: 0.5,
        reasons: ['High success rate.'],
        risks: [],
        metadata: {}
      }
    ],
    repair_insights: [],
    context_insights: [],
    feedback_insights: [],
    benchmark_reports: [createAdaptiveBenchmark()],
    replay_results: [createAdaptiveReplay()],
    policy_checkpoints: [
      {
        id: 'checkpoint-1',
        created_at: '2026-05-06T00:00:00Z',
        reason: 'before change',
        active_profile_id: 'local_privacy_first',
        profiles: [activeProfile]
      }
    ],
    recommendations: [],
    warnings: [],
    ...overrides
  };
}

function createTaskSummary(overrides: Record<string, unknown> = {}) {
  return {
    id: 'task-1',
    task_id: 'task-1',
    project_id: 'C:/project root',
    parent_task_id: null,
    title: 'Validate workspace',
    user_goal: 'Validate workspace',
    mode: 'develop',
    workspace_root: 'C:/project root',
    message: 'Validate workspace',
    status: 'completed',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:01:00Z',
    finished_at: '2026-05-06T00:01:00Z',
    completed_at: '2026-05-06T00:01:00Z',
    priority: 0,
    assigned_agent_role: 'validation',
    related_files: [],
    validation_commands: ['npm run validate'],
    checkpoints: ['checkpoint-1'],
    error_summary: '',
    final_summary: 'Done',
    ...overrides
  };
}

function createStableApi(overrides: Record<string, unknown> = {}) {
  return {
    id: 'backend.rest.v1',
    name: 'Backend REST API',
    version: '2026.05.07',
    status: 'stable',
    owner: 'core',
    path_prefixes: ['/api/chat'],
    schema_refs: ['AgentRequest'],
    compatibility_notes: ['No breaking changes.'],
    deprecation_policy: 'Versioned successor required.',
    ...overrides
  };
}

function createPluginManifest(overrides: Record<string, unknown> = {}) {
  return {
    id: 'sample-observability-panel',
    name: 'Sample Observability Panel',
    version: '0.1.0',
    api_version: '2026.05.07',
    description: 'Read-only sample panel.',
    author: 'Aegis',
    capabilities: ['ui_panel', 'telemetry_processor'],
    permissions: ['ui_panel', 'telemetry'],
    sandbox_profile: 'isolated',
    signature: '',
    signing_key_fingerprint: '',
    lifecycle_hooks: [],
    entrypoint: '',
    ui_panel_route: '/plugins/sample-observability-panel',
    enabled: false,
    trusted: false,
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  };
}

function createPluginValidation(overrides: Record<string, unknown> = {}) {
  return {
    valid: true,
    errors: [],
    warnings: ['Plugin signing metadata is missing.'],
    normalized_manifest: createPluginManifest(),
    ...overrides
  };
}

function createEnterprisePolicy(overrides: Record<string, unknown> = {}) {
  return {
    id: 'local_first_default',
    name: 'Local-First Default',
    description: 'Production baseline.',
    active: true,
    audit_trails: true,
    permission_profile: 'guided:standard',
    privacy_mode: 'local_first',
    encrypted_workspace_storage: false,
    provider_allowlist: [],
    provider_blocklist: [],
    network_allowlist: ['127.0.0.1', 'localhost'],
    network_blocklist: [],
    enforce_local_models: true,
    allow_remote_workers: false,
    telemetry_retention_days: 30,
    plugin_signing_required: false,
    command_execution_default: 'approval_required',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  };
}

function createRuntimeRecovery(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: '2026-05-06T00:00:00Z',
    database_path: 'C:/project root/data/aegis.sqlite3',
    database_ok: true,
    database_message: 'ok',
    open_tasks: 0,
    interrupted_tasks: [],
    recoverable_tasks: [],
    stale_workers: [],
    queue_recovery_items: [],
    checkpoint_count: 1,
    latest_checkpoint_id: 'checkpoint-1',
    safe_shutdown_ready: true,
    recommended_actions: [],
    ...overrides
  };
}

function createReliabilityMetric(overrides: Record<string, unknown> = {}) {
  return {
    name: 'task_completion_rate',
    value: 1,
    unit: 'ratio',
    status: 'healthy',
    target: 0.8,
    detail: '1 completed / 1 terminal task.',
    trend: 'stable',
    metadata: {},
    ...overrides
  };
}

function createProductizationSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    api_version: '2026.05.07',
    stable_apis: [createStableApi()],
    plugins: [createPluginManifest()],
    plugin_validation: [createPluginValidation()],
    enterprise_policy: createEnterprisePolicy(),
    recovery: createRuntimeRecovery(),
    metrics: [createReliabilityMetric()],
    performance: { sqlite_size_bytes: 4096 },
    scaling: { monorepo_ready: true, distributed_runtime_ready: true },
    packaging: { signed_installers: 'planned', auto_updates: 'planned' },
    docs: ['docs/PRODUCTIZATION_AND_HARDENING.md'],
    recommendations: ['Keep plugins signed for enterprise use.'],
    warnings: [],
    ...overrides
  };
}

function createEcosystemPackage(overrides: Partial<EcosystemPackageManifest> = {}): EcosystemPackageManifest {
  return {
    id: 'sample-debug-workflow-pack',
    name: 'Sample Debug Workflow Pack',
    kind: 'workflow',
    version: '0.1.0',
    api_version: '2026.05.07',
    description: 'A reusable debugging workflow pack.',
    author: 'Aegis',
    compatibility: { api_version: '2026.05.07' },
    trust_level: 'reviewed',
    sandbox_permissions: ['isolated'],
    permission_scopes: ['task_graph', 'approval', 'run_validation'],
    update_channel: 'stable',
    signature: 'signed',
    signing_key_fingerprint: 'sample-key',
    checksum: 'abc123',
    entrypoint: '',
    homepage: '',
    enabled: false,
    installed: true,
    installed_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  } as EcosystemPackageManifest;
}

function createEcosystemValidation(overrides: Record<string, unknown> = {}) {
  return {
    valid: true,
    errors: [],
    warnings: [],
    trust_score: 0.8,
    normalized_manifest: createEcosystemPackage(),
    ...overrides
  };
}

function createEcosystemWorkflow(overrides: Partial<EcosystemWorkflowDefinition> = {}): EcosystemWorkflowDefinition {
  return {
    id: 'debugging_pipeline',
    name: 'Debugging Pipeline',
    version: '1.0.0',
    api_version: '2026.05.07',
    category: 'debugging',
    description: 'Reproduce, repair, validate, and remember a failure.',
    steps: [
      {
        id: 'inspect',
        title: 'Inspect failure context',
        kind: 'inspect',
        agent_role: 'planner',
        description: '',
        depends_on: [],
        validation_commands: [],
        approval_required: false,
        max_attempts: 1,
        metadata: {}
      }
    ],
    required_agents: ['planner', 'repair', 'validation'],
    approvals: [],
    validation_commands: ['npm run validate'],
    package_dependencies: [],
    signed: false,
    signature: '',
    trust_level: 'reviewed',
    enabled: true,
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  } as EcosystemWorkflowDefinition;
}

function createWorkflowRun() {
  return {
    workflow: createEcosystemWorkflow(),
    task: createTaskSummary({ id: 'task-1', task_id: 'task-1', title: 'Debugging Pipeline' }),
    subtasks: [createTaskSummary({ id: 'task-2', task_id: 'task-2', parent_task_id: 'task-1' })],
    events: [createToolEvent()],
    message: 'Workflow created task task-1.'
  };
}

function createSharedProfile(overrides: Partial<SharedIntelligenceProfile> = {}): SharedIntelligenceProfile {
  return {
    id: 'shared-validation-profile',
    name: 'Shared Validation Profile',
    kind: 'validation_profile',
    version: '1.0.0',
    description: 'Reusable validation commands.',
    source: 'local',
    exported_at: '2026-05-06T00:00:00Z',
    imported_at: '2026-05-06T00:00:00Z',
    trust_level: 'reviewed',
    payload: { commands: ['npm run validate'] },
    checksum: 'abc123',
    signature: '',
    metadata: {},
    ...overrides
  } as SharedIntelligenceProfile;
}

function createSharedProfileExport() {
  return {
    profile: createSharedProfile(),
    export_format: 'aegis.shared-intelligence+json',
    checksum: 'abc123'
  };
}

function createOrganizationPolicy(overrides: Record<string, unknown> = {}) {
  return {
    id: 'local_organization_policy',
    name: 'Local Organization Policy',
    active: true,
    provider_policies: { default: 'local-first' },
    privacy_policies: { workspace_sync: 'opt_in' },
    approval_requirements: { write_workspace: true },
    validation_standards: { before_completion: true },
    package_restrictions: { allowed_update_channels: ['stable', 'local'] },
    audit_requirements: { ecosystem_events: true },
    require_signed_packages: false,
    allow_community_packages: true,
    collaboration_mode: 'local',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    metadata: {},
    ...overrides
  };
}

function createKnowledgeGraph(overrides: Record<string, unknown> = {}) {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    nodes: [
      {
        id: 'api-1',
        kind: 'api',
        label: 'GET /api/items',
        path: 'backend/main.py',
        summary: 'Detected API route.',
        importance: 0.9,
        metadata: {}
      }
    ],
    edges: [{ source: 'file-1', target: 'api-1', kind: 'exposes', weight: 1, summary: 'File exposes API route.', metadata: {} }],
    modules_total: 1,
    api_routes_total: 1,
    dependencies_total: 2,
    decisions_total: 0,
    recurring_failures_total: 0,
    recommendations: [],
    ...overrides
  };
}

function createCrossProjectInsight() {
  return {
    id: 'single-project-baseline',
    title: 'Cross-project baseline pending',
    category: 'reuse',
    severity: 'low',
    projects: ['Demo'],
    related_files: [],
    detail: 'More indexed projects will unlock comparisons.',
    recommendation: 'Index additional workspaces.',
    evidence: {}
  };
}

function createEcosystemSearch() {
  return {
    query: 'api route',
    generated_at: '2026-05-06T00:00:00Z',
    results: [
      {
        id: 'api-1',
        kind: 'graph.api',
        title: 'GET /api/items',
        detail: 'Detected API route.',
        reference: 'backend/main.py',
        score: 2.2,
        metadata: {}
      }
    ],
    scope_summary: { graph: 1 },
    reconstruction: []
  };
}

function createReproducibilityRecordFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'repro-1',
    workspace_root: 'C:/project root',
    task_id: 'task-1',
    created_at: '2026-05-06T00:00:00Z',
    deterministic_hash: 'hash123456789',
    status: 'ready',
    artifacts: [{ kind: 'task', reference: 'task-1', checksum: 'abc123', payload: {} }],
    replay_notes: ['Replay captured task payload and timeline.'],
    metadata: { artifact_count: 1 },
    ...overrides
  };
}

function createEcosystemAuditEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'audit-ecosystem-1',
    created_at: '2026-05-06T00:00:00Z',
    actor: 'local-user',
    action: 'package.registered',
    subject_id: 'sample-debug-workflow-pack',
    status: 'ok',
    detail: 'Package registered.',
    metadata: {},
    ...overrides
  };
}

function createGovernanceSignal(overrides: Record<string, unknown> = {}) {
  return {
    id: 'package-validation',
    label: 'Package Validation',
    status: 'trusted',
    score: 1,
    detail: 'All installed package manifests validate.',
    evidence: {},
    ...overrides
  };
}

function createToolEvent(overrides: Record<string, unknown> = {}) {
  return {
    kind: 'workflow.created',
    title: 'Workflow created',
    status: 'ok',
    detail: 'Workflow created.',
    payload: {},
    created_at: '2026-05-06T00:00:00Z',
    ...overrides
  };
}

function createEcosystemSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    api_version: '2026.05.07',
    marketplace_catalog: [createEcosystemPackage({ installed: false })],
    packages: [createEcosystemPackage()],
    package_validation: [createEcosystemValidation()],
    workflows: [createEcosystemWorkflow()],
    shared_profiles: [createSharedProfile()],
    team: {
      mode: 'local',
      shared_task_count: 0,
      shared_checkpoint_count: 0,
      shared_architecture_notes: 0,
      pending_approvals: 0,
      collaborators: [],
      telemetry_dashboards: [],
      status: 'disabled',
      notes: []
    },
    organization_policy: createOrganizationPolicy(),
    knowledge_graph: createKnowledgeGraph(),
    cross_project_insights: [createCrossProjectInsight()],
    search: createEcosystemSearch(),
    reproducibility: [createReproducibilityRecordFixture()],
    governance: [createGovernanceSignal()],
    audit_events: [createEcosystemAuditEvent()],
    recommendations: ['Install trusted ecosystem packages before sharing workflows.'],
    warnings: [],
    ...overrides
  };
}

function createWorkspaceOperationsSnapshot() {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-06T00:00:00Z',
    watcher: {
      workspace_root: 'C:/project root',
      scanned_at: '2026-05-06T00:00:00Z',
      file_count: 1,
      fingerprint: 'fingerprint',
      dependency_fingerprint: 'dependency',
      file_states: [],
      events: [],
      validation_drift: [],
      git: createGitSummary()
    },
    health: {
      workspace_root: 'C:/project root',
      generated_at: '2026-05-06T00:00:00Z',
      score: 96,
      status: 'healthy',
      metrics: [],
      top_risks: []
    },
    recommendations: [],
    scheduled_jobs: [createScheduledJob()],
    git: createGitSummary(),
    long_term_memory: [],
    recent_events: []
  };
}

function createGitSummary() {
  return {
    is_repository: true,
    branch: 'main',
    upstream: '',
    branch_count: 1,
    branches: ['main'],
    changed_files: [],
    staged_files: [],
    untracked_files: [],
    deleted_files: [],
    risky_diffs: [],
    change_heatmap: [],
    recent_commits: [],
    task_commit_links: [],
    summary: 'Clean workspace.'
  };
}

function createRecommendation() {
  return {
    id: 'rec-1',
    workspace_root: 'C:/project root',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    dismissed_at: '',
    severity: 'medium',
    category: 'health',
    title: 'Review this file',
    detail: 'A file needs review.',
    rationale: 'A file needs review.',
    status: 'active',
    related_files: ['src/app.ts'],
    related_tasks: [],
    evidence: {},
    fix_prompt: 'Review src/app.ts',
    fix_task_id: ''
  };
}

function createScheduledJob() {
  return {
    id: 'validation_snapshot',
    name: 'Validation snapshot',
    kind: 'validation',
    schedule_label: 'Hourly',
    enabled: true,
    safe_by_default: true,
    last_run_at: '',
    next_run_hint: 'Next eligible hourly maintenance window.',
    status: 'idle',
    summary: ''
  };
}

function createCapabilitySet(overrides: Record<string, unknown> = {}) {
  return {
    installed_sdks: ['python'],
    build_tools: ['python'],
    supported_languages: ['python'],
    available_models: ['qwen2.5-coder:7b'],
    gpu_available: false,
    ram_gb: 16,
    cpu_cores: 8,
    validation_support: true,
    sandbox_profiles: ['safe', 'standard'],
    supported_job_kinds: ['task', 'validation', 'build', 'indexing', 'repair', 'benchmark', 'telemetry', 'sync'],
    supports_remote_sync: true,
    max_parallel_jobs: 1,
    ...overrides
  };
}

function createWorker(overrides: Record<string, unknown> = {}) {
  return {
    worker_id: 'local-runtime',
    name: 'Local runtime',
    kind: 'local',
    endpoint: 'C:/project root',
    status: 'available',
    trust_state: 'trusted',
    trust_scope: 'local',
    registered_at: '2026-05-06T00:00:00Z',
    last_heartbeat_at: '2026-05-06T00:00:00Z',
    capabilities: createCapabilitySet(),
    current_jobs: 0,
    total_jobs: 1,
    failed_jobs: 0,
    average_latency_ms: 10,
    public_key_fingerprint: 'local',
    permission_scopes: ['read', 'task', 'validation'],
    isolation_level: 'process',
    metadata: {},
    ...overrides
  };
}

function createQueueItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'job-1',
    task_id: 'task-1',
    workspace_root: 'C:/project root',
    kind: 'validation',
    title: 'Validate',
    user_goal: 'Validate workspace',
    status: 'queued',
    priority: 0,
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    assigned_worker_id: '',
    attempts: 0,
    max_attempts: 3,
    depends_on: [],
    required_capabilities: [],
    permission_scope: 'validation',
    sandbox_profile: 'safe',
    payload: {},
    error_summary: '',
    result_summary: '',
    lease_expires_at: '',
    ...overrides
  };
}

function createAuditEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'audit-1',
    created_at: '2026-05-06T00:00:00Z',
    worker_id: 'local-runtime',
    job_id: 'job-1',
    event_type: 'job.finished',
    status: 'ok',
    detail: 'done',
    metadata: {},
    ...overrides
  };
}

function createRuntimeObservability() {
  return {
    generated_at: '2026-05-06T00:00:00Z',
    workers_total: 1,
    workers_available: 1,
    workers_busy: 0,
    workers_offline: 0,
    workers_untrusted: 0,
    queued_jobs: 1,
    running_jobs: 0,
    failed_jobs: 0,
    succeeded_jobs: 1,
    task_throughput: { validation: 1 },
    token_usage: {},
    model_latency_ms: { 'local-runtime': 10 },
    validation_success_rate: 1,
    repair_loop_statistics: {},
    queue_latency_ms: 50
  };
}

function createRouteDecision() {
  return {
    selected: {
      provider_id: 'local:ollama',
      worker_id: '',
      model: 'qwen2.5-coder:7b',
      location: 'local',
      privacy_mode: 'local-first',
      estimated_latency_ms: 350,
      estimated_cost_usd: 0,
      reasoning_fit: 0.7,
      selected: true,
      reason: 'Local provider.'
    },
    candidates: [],
    fallback_order: ['local:ollama'],
    privacy_mode: 'local-first',
    summary: 'Selected local model.',
    warnings: []
  };
}

function createSyncManifest() {
  return {
    id: 'sync-1',
    workspace_root: 'C:/project root',
    created_at: '2026-05-06T00:00:00Z',
    encrypted: true,
    encryption_label: 'local-manifest-hash',
    included_sections: ['settings'],
    manifest_hash: 'abc123',
    payload: {}
  };
}

function createDistributedRuntimeSnapshot() {
  return {
    generated_at: '2026-05-06T00:00:00Z',
    execution_mode: 'local',
    workers: [createWorker()],
    queue: [createQueueItem()],
    observability: createRuntimeObservability(),
    audit_events: [createAuditEvent()],
    routing: createRouteDecision(),
    sync_manifests: [createSyncManifest()],
    security_summary: ['Local-first execution remains available.']
  };
}

function createUnifiedRuntimeSnapshot() {
  return {
    generated_at: '2026-05-06T00:00:00Z',
    api_version: '2026.05.07',
    workspace_root: 'C:/project root',
    runtime_name: 'Auralith Runtime',
    mode: 'local-first',
    pillars: [
      {
        id: 'conversation_reasoning',
        name: 'Conversation And Reasoning',
        status: 'partial',
        summary: 'Chat, memory, and task awareness are active.',
        privacy_scope: 'local-first',
        modules: ['agent.py'],
        endpoints: ['/api/chat'],
        primary_surfaces: ['Home'],
        active_items: 1,
        signals: ['1 task'],
        next_workflows: ['Improve memory ranking'],
        safety_notes: ['Local memory.']
      },
      {
        id: 'creative_studio',
        name: 'Creative Studio',
        status: 'ready',
        summary: 'Local creative generation is active.',
        privacy_scope: 'local-first',
        modules: ['creative_media.py'],
        endpoints: ['/api/creative-studio'],
        primary_surfaces: ['Creative'],
        active_items: 1,
        signals: ['1 asset'],
        next_workflows: [],
        safety_notes: ['Assets stay local.']
      }
    ],
    modalities: [
      {
        id: 'text',
        label: 'Text',
        status: 'ready',
        input_supported: true,
        output_supported: true,
        analyzers: ['intent'],
        generators: ['chat'],
        formats: ['md'],
        notes: []
      }
    ],
    tools: [
      {
        id: 'filesystem',
        name: 'Filesystem',
        category: 'workspace',
        status: 'ready',
        permission_scope: 'workspace',
        approval_required: true,
        sandboxed: true,
        rollback_supported: true,
        timeout_seconds: 0,
        tracked_by_tasks: true,
        endpoints: ['/api/apply'],
        notes: []
      }
    ],
    workflows: [
      {
        id: 'daily_coding',
        name: 'Daily Coding Loop',
        category: 'coding',
        status: 'ready',
        trigger: 'manual',
        description: 'Ask, plan, edit, validate.',
        endpoints: ['/api/chat'],
        safety_profile: 'approval-gated',
        task_tracked: true
      }
    ],
    memory_summary: { continuity_status: 'ready' },
    safety_summary: ['Local-first execution is the default.'],
    active_counts: { tasks: 1, creative_assets: 1 },
    recommendations: [],
    warnings: []
  };
}

function createOperatingEnvironmentSnapshot() {
  return {
    generated_at: '2026-05-07T00:00:00Z',
    api_version: '2026.05.07',
    workspace_root: 'C:/project root',
    runtime_name: 'Auralith OS',
    mode: 'local-first',
    execution_mode: 'control-plane',
    capabilities: [
      {
        id: 'desktop_control',
        name: 'AI Desktop Control Layer',
        category: 'desktop',
        status: 'blocked',
        summary: 'Desktop actions are blocked by default.',
        permission_scope: 'desktop_control',
        approval_required: true,
        sandbox_required: true,
        rollback_supported: false,
        task_tracked: true,
        telemetry_enabled: true,
        adapter_ids: ['desktop_automation_adapter'],
        endpoints: ['/api/operating-environment/actions/preview'],
        surfaces: ['Runtime'],
        safety_notes: ['No desktop mutation is performed.'],
        next_steps: ['Approve trusted adapter']
      },
      {
        id: 'system_intelligence',
        name: 'AI System Intelligence',
        category: 'system',
        status: 'partial',
        summary: 'Read-only system signals are available.',
        permission_scope: 'system_read',
        approval_required: false,
        sandbox_required: false,
        rollback_supported: false,
        task_tracked: false,
        telemetry_enabled: true,
        adapter_ids: ['readonly_system_probe'],
        endpoints: ['/api/operating-environment'],
        surfaces: ['Runtime'],
        safety_notes: ['Read-only.'],
        next_steps: []
      }
    ],
    adapters: [
      {
        id: 'readonly_system_probe',
        name: 'Read-Only System Probe',
        category: 'system',
        status: 'ready',
        provider: 'local',
        enabled: true,
        permission_scope: 'system_read',
        capabilities: ['system_intelligence'],
        approval_required: false,
        sandboxed: false,
        reason: '',
        notes: ['Read-only.'],
        last_seen_at: '2026-05-07T00:00:00Z'
      }
    ],
    system_signals: [
      {
        id: 'os',
        label: 'Operating System',
        category: 'host',
        status: 'ok',
        value: 'Windows',
        detail: 'Windows desktop',
        updated_at: '2026-05-07T00:00:00Z'
      }
    ],
    permissions_summary: {
      ready_capabilities: 0,
      approval_or_adapter_gated: 1,
      enabled_adapters: 1,
      disabled_adapters: 1,
      desktop_control_default: 'blocked'
    },
    safety_summary: ['Desktop control is blocked by default.'],
    recommended_next_actions: ['Use previews before adapters.'],
    warnings: []
  };
}

function createUnifiedContextSnapshot() {
  const task = createTaskSummary();
  const record = {
    id: 'task:task-1',
    kind: 'task',
    title: task.title,
    summary: task.final_summary,
    source: 'task_engine',
    reference: task.id,
    workspace_root: 'C:/project root',
    created_at: task.created_at,
    updated_at: task.updated_at,
    status: task.status,
    importance: 0.82,
    tags: ['task', 'validation'],
    related_files: ['src/App.tsx'],
    related_tasks: [task.id],
    related_assets: [],
    metadata: {}
  };
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-07T00:00:00Z',
    api_version: '2026.05.07',
    records: [
      record,
      {
        id: 'media_asset:mockup',
        kind: 'media_asset',
        title: 'UI mockup',
        summary: 'Generated UI mockup asset.',
        source: 'creative_studio',
        reference: 'creative_media/mockup.png',
        workspace_root: 'C:/project root',
        created_at: '',
        updated_at: '',
        status: 'png',
        importance: 0.6,
        tags: ['asset', 'ui_mockup'],
        related_files: [],
        related_tasks: [],
        related_assets: ['mockup'],
        metadata: {}
      }
    ],
    relationships: [
      {
        source_id: 'task:task-1',
        target_id: 'file:src/App.tsx',
        kind: 'touches_file',
        strength: 0.8,
        summary: 'Task references this file.',
        evidence: []
      }
    ],
    source_summaries: [
      { source: 'task_engine', records: 1, ready: true, summary: 'Tasks and outcomes.' },
      { source: 'creative_studio', records: 1, ready: true, summary: 'Creative assets.' }
    ],
    timeline: [record],
    cross_module_insights: ['Creative assets are visible to coding, project, and workflow planning.'],
    command_entrypoints: ['chat', 'command_palette', 'desktop_overlay', 'voice', 'mobile', 'api'],
    recommended_focus: ['Continue active tasks before creating parallel work.'],
    warnings: []
  };
}

function createGlobalCommandResponse() {
  const context = createUnifiedContextSnapshot();
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-07T00:00:00Z',
    command: 'Refactor using the latest mockup',
    entrypoint: 'command_palette',
    route: {
      intent: 'coding',
      target_system: 'task_engine',
      task_kind: 'coding',
      confidence: 0.88,
      creates_task: true,
      approval_required: true,
      rollback_supported: true,
      validation_required: true,
      endpoint: '/api/tasks',
      reason: 'The command asks for project or code work.',
      safety_notes: ['File edits go through approvals, checkpoints, validation, repair, and rollback.']
    },
    plan: ['Classify the request.', 'Create or continue a tracked task before execution.'],
    context_results: [
      {
        record: context.records[0],
        score: 1.2,
        matched_fields: ['title'],
        relationships: context.relationships
      }
    ],
    task: null,
    event: null,
    warnings: []
  };
}

function createContinuitySnapshot() {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-07T00:00:00Z',
    api_version: '2026.05.07',
    presence: {
      status: 'focused',
      active_focus: 'Validate workspace',
      workload_level: 'steady',
      suggestion_intensity: 'quiet',
      notification_style: 'subtle',
      continuity_summary: '2 context records, 1 relationship, 1 active task.',
      proactive_suggestions: ['Continue the current active task.'],
      active_signals: ['1 active task'],
      session_handoff: ['Review task timeline']
    },
    timeline: {
      workspace_root: 'C:/project root',
      generated_at: '2026-05-07T00:00:00Z',
      entries: [
        {
          id: 'timeline:task-1',
          kind: 'task',
          title: 'Validate workspace',
          summary: 'Done',
          source: 'task_engine',
          reference: 'task-1',
          occurred_at: '2026-05-06T00:00:00Z',
          status: 'completed',
          importance: 0.8,
          related_records: ['task:task-1'],
          related_files: ['src/App.tsx'],
          related_tasks: ['task-1'],
          related_assets: [],
          replay_hint: 'Open task timeline.',
          metadata: {}
        }
      ],
      source_counts: { task_engine: 1 },
      reconstruction_notes: ['Timeline is reconstructed.'],
      replay_supported: true,
      search_supported: true
    },
    forecasts: {
      generated_at: '2026-05-07T00:00:00Z',
      risk_score: 0.22,
      signals: [
        {
          id: 'baseline',
          kind: 'technical_debt',
          severity: 'info',
          score: 0.18,
          title: 'Baseline Risk',
          summary: 'No strong instability pattern.',
          evidence: [],
          projected_impact: 'Normal validation is enough.',
          recommended_action: 'Keep task tracking.',
          dry_run_available: true,
          confidence: 0.58
        }
      ],
      dry_run_modes: ['architecture'],
      assumptions: ['Heuristic forecast.']
    },
    cognitive: {
      load_level: 'steady',
      detected_patterns: [],
      pacing: 'normal',
      verbosity: 'balanced',
      notification_intensity: 'quiet',
      workflow_aggressiveness: 'conservative',
      recommendation_style: 'calm',
      safeguards: ['Do not infer emotions.']
    },
    hardware: {
      status: 'partial',
      cpu_logical: 16,
      gpu_available: false,
      npu_available: false,
      accelerators: ['CPU'],
      local_model_optimizations: ['quantized routing'],
      routing_notes: ['CPU baseline.'],
      power_profile: 'unknown',
      warnings: []
    },
    workspace_state: {
      workspace_root: 'C:/project root',
      restore_readiness: 'ready',
      persisted_sections: ['tasks', 'memory'],
      active_task_count: 1,
      active_workflow_count: 0,
      memory_record_count: 1,
      media_asset_count: 1,
      checkpoint_references: 1,
      recovery_notes: ['Reconstructed from persisted state.']
    },
    self_diagnostics: [
      {
        id: 'routing-health',
        category: 'routing',
        status: 'healthy',
        title: 'Routing Health',
        summary: 'Preview-first.',
        evidence: [],
        recommendation: 'Keep previews visible.'
      }
    ],
    skill_packs: [
      {
        id: 'nextjs',
        name: 'Next.js Pack',
        category: 'web',
        status: 'planned',
        trust_level: 'metadata',
        capabilities: ['validators'],
        included_assets: ['workflows'],
        permission_scopes: ['workspace_read'],
        lifecycle: ['validate'],
        notes: []
      }
    ],
    universal_data_sources: [
      {
        id: 'files',
        name: 'Files',
        category: 'workspace',
        status: 'partial',
        records_indexed: 2,
        semantic_index_ready: false,
        permission_scope: 'workspace',
        connectors: ['project_intelligence'],
        notes: []
      }
    ],
    platform_sdk: [
      {
        id: 'plugins',
        name: 'Plugins',
        status: 'partial',
        api_version: '2026.05.07',
        permission_scoped: true,
        sandboxed: true,
        signing_supported: true,
        lifecycle_hooks: ['install'],
        docs: ['docs/PRODUCTIZATION_AND_HARDENING.md']
      }
    ],
    digital_twin: {
      workspace_root: 'C:/project root',
      model_version: '2026.05.07',
      confidence: 0.5,
      modeled_entities: { task: 1 },
      architecture_summary: '1 file entity.',
      workflow_summary: '1 task.',
      dependency_summary: 'Derived from context.',
      preference_summary: '1 memory.',
      recovery_uses: ['resume tasks'],
      predictive_uses: ['validation risk']
    },
    research_lab: [
      {
        id: 'routing_eval',
        name: 'Routing Evaluation',
        category: 'routing',
        status: 'partial',
        metric: 'route agreement',
        last_result: 'preview-only',
        next_run_hint: 'compare outcomes',
        controlled: true
      }
    ],
    memory_distillation: {
      generated_at: '2026-05-07T00:00:00Z',
      raw_memory_records: 1,
      distilled_themes: ['decision: 1'],
      archive_candidates: [],
      compression_ratio_estimate: 0,
      pruning_recommendations: ['Memory manageable.'],
      continuity_preserved: true
    },
    recommendations: ['Keep convergence in Runtime.'],
    warnings: []
  };
}

function createPlatformDisciplineSnapshot() {
  return {
    workspace_root: 'C:/project root',
    generated_at: '2026-05-07T00:00:00Z',
    api_version: '2026.05.07',
    core_identity: 'Aegis is a unified local-first AI operating environment for real daily work.',
    stewardship: {
      id: 'platform_stewardship',
      name: 'Platform Stewardship',
      summary: 'Preserve quality, clarity, maintainability, trust, performance, and cohesion.',
      preserve: ['quality', 'clarity', 'trust'],
      improve: ['intelligence quality', 'responsiveness'],
      reduce: ['friction', 'clutter'],
      product_feel: ['calm', 'premium', 'powerful without feeling chaotic'],
      operating_rules: ['Do not chase trends blindly.'],
      success_metric: 'Users choose Aegis daily.',
      review_cadence: 'Every roadmap change.'
    },
    feature_admission: {
      id: 'feature_admission_gate',
      name: 'Feature Admission Gate',
      default_decision: 'reject_when_unclear',
      summary: 'New features are rejected by default when value is unclear.',
      criteria: [
        {
          id: 'core_identity',
          question: 'Does this strengthen the core identity?',
          pass_requirement: 'It improves a primary workflow.',
          reject_when: 'The proposal mainly broadens scope.',
          protects: ['cohesion'],
          required: true
        }
      ],
      hard_no_rules: ['Say no to unclear value.', 'Say no to uncontrolled autonomy.'],
      promotion_requirements: ['Named workflow and user value.'],
      review_cadence: 'Apply before implementation.'
    },
    primary_domains: [
      {
        id: 'coding_workspace',
        name: 'AI Coding Workspace',
        focus: 'primary',
        rationale: 'Strongest daily workflow.',
        mastery_goal: 'Make code changes trustworthy.',
        success_metrics: ['validation pass rate'],
        active_systems: ['Task Engine'],
        boundaries: ['No writes outside approved workspace paths.']
      }
    ],
    secondary_domains: [
      {
        id: 'automation_platform',
        name: 'AI Automation Platform',
        focus: 'secondary',
        rationale: 'Useful when it extends repeated workflows.',
        mastery_goal: 'Task-track repeated workflows.',
        success_metrics: ['automation completion rate'],
        active_systems: ['Workspace Operations'],
        boundaries: ['No silent writes.']
      }
    ],
    experimental_domains: [
      {
        id: 'desktop_operating_layer',
        name: 'AI Desktop Operating Layer',
        focus: 'experimental',
        rationale: 'Powerful and risky.',
        mastery_goal: 'Preview-first desktop assistance.',
        success_metrics: ['permission clarity'],
        active_systems: ['Operating Environment'],
        boundaries: ['No desktop action without approval.']
      }
    ],
    roadmap: [
      {
        id: 'daily_coding_loop',
        title: 'Daily Coding Loop',
        category: 'mvp_workflow',
        status: 'production_ready',
        domain: 'coding_workspace',
        summary: 'Ask, plan, edit, validate, repair.',
        owner_layer: 'layer_3_domain_systems',
        exit_criteria: ['validation passes'],
        blocked_by: [],
        complexity_cost: 'medium',
        ux_impact: 'positive'
      },
      {
        id: 'uncontrolled_autonomy',
        title: 'Uncontrolled Autonomy',
        category: 'deprecated',
        status: 'deprecated',
        domain: 'all',
        summary: 'No silent code changes or unbounded loops.',
        owner_layer: 'layer_1_core_runtime',
        exit_criteria: ['blocked by policy'],
        blocked_by: [],
        complexity_cost: 'high',
        ux_impact: 'risky'
      }
    ],
    stability_tiers: [
      {
        id: 'stable_runtime',
        name: 'Stable Runtime',
        description: 'Default user experience.',
        allowed_statuses: ['production_ready', 'beta'],
        entry_requirements: ['regression tests'],
        release_rules: ['visible by default'],
        user_visibility: 'default'
      }
    ],
    feedback_loops: [
      {
        id: 'workflow_success',
        name: 'Workflow Success Tracking',
        status: 'partial',
        signal: 'completed tasks',
        metric: 'task completion rate',
        source: 'Task Engine',
        cadence: 'per task',
        improvement_rule: 'Improve real workflows.',
        current_value: 1,
        target_value: null,
        notes: []
      }
    ],
    design_standards: [
      {
        id: 'surface_convergence',
        category: 'ui',
        rule: 'New intelligence appears in existing workflow surfaces.',
        rationale: 'Prevents dashboard sprawl.',
        applies_to: ['Runtime'],
        enforcement: 'review_required'
      }
    ],
    behavior_principles: [
      {
        id: 'calm',
        principle: 'Calm By Default',
        do: ['Use concise updates.'],
        avoid: ['noisy autonomy'],
        enforcement: 'Suggestion intensity is capped.'
      }
    ],
    performance_budgets: [
      {
        id: 'startup',
        name: 'Startup Readiness',
        category: 'startup',
        target: 'Usable within 3 seconds.',
        warning_threshold: '5 seconds',
        hard_limit: '8 seconds',
        measurement: '/api/health',
        status: 'unknown',
        rationale: 'Aegis should feel fast before it feels powerful.'
      }
    ],
    security_foundations: [
      {
        id: 'rollback',
        name: 'Rollback Guarantees',
        status: 'ready',
        policy: 'Workspace writes checkpoint before mutation.',
        enforcement_points: ['WorkspaceManager'],
        gaps: []
      }
    ],
    layers: [
      {
        id: 'layer_1_core_runtime',
        name: 'Layer 1: Core Runtime',
        responsibility: 'Settings, contracts, providers, workspace safety, storage, health.',
        systems: ['main.py'],
        allowed_dependencies: [],
        forbidden_dependencies: ['experimental adapters'],
        stability_expectation: 'stable_runtime'
      }
    ],
    maintainability_practices: [
      {
        id: 'large_file_control',
        practice: 'Keep large files shrinking.',
        cadence: 'each feature slice',
        signal: 'App.tsx size',
        expected_outcome: 'Faster reviews.'
      }
    ],
    production_ready_count: 1,
    beta_count: 0,
    experimental_count: 1,
    deprecated_count: 2,
    recommendations: ['Invest first in coding, orchestration, and memory quality.'],
    warnings: []
  };
}
