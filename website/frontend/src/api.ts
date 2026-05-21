// frontend/src/api.ts
import type {
  AdaptiveBenchmarkReport,
  AdaptiveBenchmarkRunRequest,
  AdaptiveIntelligenceRefreshRequest,
  AdaptiveIntelligenceSnapshot,
  AdaptivePolicyProfileUpdateRequest,
  AdaptivePolicyRollbackRequest,
  AdaptiveReplayRequest,
  AegisContinuitySnapshot,
  AgentRequest,
  AgentResponse,
  AgentBridgeExecuteRequest,
  AgentBridgeExecuteResponse,
  AgentBridgeJobResponse,
  AgentBridgeJobsResponse,
  AgentBridgePreflightResponse,
  AgentBridgeStreamPayload,
  AgentSupervisionActionRequest,
  AgentSupervisionActionResponse,
  AgentSupervisionDelegationRequest,
  AgentSupervisionSnapshot,
  ApprovalSettingsResponse,
  AppConfig,
  ApplyRequest,
  ApplyResponse,
  AuthForgotPasswordRequest,
  AuthLoginRequest,
  AuthMessageResponse,
  AuthRegisterRequest,
  AuthSessionResponse,
  AutonomousApprovalActionRequest,
  AutonomousApprovalGate,
  AutonomousEngineeringSnapshot,
  AutonomousObjective,
  AutonomousObjectiveActionRequest,
  AutonomousObjectiveCreateRequest,
  AutonomousObjectiveDetail,
  AutonomousObjectiveIterationRequest,
  AutonomousSimulationEstimate,
  CheckpointListResponse,
  ChatStreamContractResponse,
  ChatStreamPayload,
  ConfigUpdateRequest,
  CreateMemoryNoteRequest,
  DeleteMemoryNoteResponse,
  DiffCompareRequest,
  DiffCompareResponse,
  DistributedRuntimeSnapshot,
  EcosystemAuditEvent,
  EcosystemPackageActionRequest,
  EcosystemPackageManifest,
  EcosystemPackageRegistrationRequest,
  EcosystemPackageValidationRequest,
  EcosystemPackageValidationResult,
  EcosystemRefreshRequest,
  EcosystemSearchRequest,
  EcosystemSearchResponse,
  EcosystemSnapshot,
  EcosystemWorkflowDefinition,
  EnterprisePolicyProfile,
  EnterprisePolicyUpdateRequest,
  EvaluationReportsResponse,
  ExecutionDispatchRequest,
  ExecutionDispatchResponse,
  ExecutionQueueActionRequest,
  ExecutionQueueCreateRequest,
  ExecutionQueueItem,
  FileContentResponse,
  FilesResponse,
  FallbackInspectorResponse,
  FeedbackTelemetryResponse,
  EvaluationReplayResult,
  GlobalCommandRequest,
  GlobalCommandResponse,
  HealthResponse,
  HistoryResponse,
  HybridRouteDecision,
  HybridRouteRequest,
  IntelligencePolicyProfile,
  KnowledgeGraphSnapshot,
  MediaAssetLibraryResponse,
  MediaCapabilitiesResponse,
  MediaCreativeRequest,
  MediaExportRequest,
  MediaExportResponse,
  MediaJobResponse,
  MediaPromptPreset,
  MediaProviderInfo,
  ModelDeleteRequest,
  ModelInventoryResponse,
  ModelManagerResponse,
  MemoryControlsResponse,
  MemoryControlsUpdateRequest,
  MemoryExportRequest,
  MemoryExportResponse,
  MemoryGovernanceResponse,
  MemoryNoteResponse,
  MemoryNotesResponse,
  ModelOperationInfo,
  ModelPullRequest,
  ModelRegistryResponse,
  ProviderAccountLinkResponse,
  ProviderAccountsResponse,
  ProviderApiKeyLinkRequest,
  ProviderCliLoginResponse,
  ProviderSourceRefreshRequest,
  ProviderSourceRefreshJobResponse,
  ProviderSourceRefreshJobsResponse,
  ProviderSourceRefreshResponse,
  ProviderSourceRootOpenRequest,
  ProviderSourceRootOpenResponse,
  QualityBenchmarkDashboard,
  QualityBenchmarkRunRequest,
  QualityGateEvaluation,
  QualityGateEvaluationRequest,
  QualityGateSnapshot,
  PluginActionRequest,
  PluginManifest,
  PluginRegistrationRequest,
  PluginValidationRequest,
  PluginValidationResult,
  OperatingEnvironmentActionRequest,
  OperatingEnvironmentActionResponse,
  OperatingEnvironmentSnapshot,
  OrganizationPolicyProfile,
  OrganizationPolicyUpdateRequest,
  OnboardingFirstWorkflowRequest,
  OnboardingFirstWorkflowResponse,
  OnboardingStatusResponse,
  OnboardingUpdateRequest,
  PlatformDisciplineSnapshot,
  ProjectContextSelectionRequest,
  ProjectContextSelectionResponse,
  ProjectIntelligenceReindexRequest,
  ProjectIntelligenceSnapshot,
  ProductizationRefreshRequest,
  ProductizationSnapshot,
  ReproducibilityRecord,
  ReproducibilityRequest,
  RecommendationActionRequest,
  RecommendationFixRequest,
  RecommendationFixResponse,
  RemoteWorkspaceSyncManifest,
  RemoteWorkspaceSyncRequest,
  RestoreCheckpointRequest,
  RestoreCheckpointResponse,
  ReliabilityMetric,
  RouteQualityResponse,
  RoutePolicyDiffOptions,
  RoutePolicyDiffResponse,
  RuntimeInteractionSnapshot,
  RuntimeJobActionRequest,
  RuntimeJobMutationResponse,
  RuntimeObservabilitySnapshot,
  RuntimeOwnershipResponse,
  RuntimeRecoverySnapshot,
  RuntimeReplayResponse,
  RuntimeSessionMutationResponse,
  RuntimeSessionRequest,
  RuntimeSessionSyncRequest,
  RuntimeSettingsExportResponse,
  RuntimeSettingsImportRequest,
  RuntimeSettingsImportResponse,
  RuntimeStreamsResponse,
  RuntimeTerminalJobRequest,
  RuntimeVoiceCommandRequest,
  RuntimeVoiceCommandResponse,
  RuntimeVoiceResponse,
  StableApiContract,
  TaskActionRequest,
  TaskActionResponse,
  TaskArtifactsResponse,
  TaskCreateRequest,
  TaskDetailResponse,
  TaskListResponse,
  TaskOutcomeRecord,
  TaskTimelineResponse,
  ScheduledIntelligenceJob,
  ScheduledJobRunRequest,
  ScheduledJobRunResponse,
  SharedIntelligenceProfile,
  SharedIntelligenceProfileExportResponse,
  SharedIntelligenceProfileImportRequest,
  TelemetrySnapshotOptions,
  TelemetrySnapshotResponse,
  TimelineSearchRequest,
  TimelineSearchResponse,
  UnifiedContextSearchRequest,
  UnifiedContextSearchResponse,
  UnifiedContextSnapshot,
  UnifiedRuntimeSnapshot,
  UpdateMemoryNoteRequest,
  UpdateApprovalSettingsRequest,
  ValidationProfileResponse,
  ValidationProfileUpdateRequest,
  ValidateRequest,
  ValidateResponse,
  WorkspaceOperationsScanRequest,
  WorkspaceOperationsSnapshot,
  WorkspaceRecommendation,
  WorkspaceWatchEvent,
  WorkspaceProfileResponse,
  WorkspaceSetupRequest,
  WorkspaceSetupResponse,
  WorkerActionRequest,
  WorkerAuditEvent,
  WorkerHeartbeatRequest,
  WorkerRegistrationRequest,
  WorkerRuntimeInfo,
  WorkflowRunRequest,
  WorkflowRunResponse
} from './types';

const EXPLICIT_API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/+$/, '');
const DEFAULT_API_BASES = ['', 'http://127.0.0.1:8787', 'http://127.0.0.1:8793'];
const API_DISCOVERY_TIMEOUT_MS = 3000;
const IS_TEST_MODE = import.meta.env.MODE === 'test';

let resolvedApiBase = EXPLICIT_API_BASE;
let apiBaseDiscovered = Boolean(EXPLICIT_API_BASE);
let apiDiscoveryEnabledForTests = false;
let apiDiscoveryPromise: Promise<void> | null = null;

function apiBaseCandidates(): string[] {
  if (EXPLICIT_API_BASE) return [EXPLICIT_API_BASE];

  return [resolvedApiBase, ...DEFAULT_API_BASES].filter((base, index, bases) => bases.indexOf(base) === index);
}

function apiUrl(base: string, path: string): string {
  return `${base}${path}`;
}

function shouldRetryApiBase(response: Response): boolean {
  return !EXPLICIT_API_BASE && [404, 502, 503, 504].includes(response.status);
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

function shouldRetryFetchError(error: unknown): boolean {
  return !EXPLICIT_API_BASE && !isAbortError(error);
}

function shouldDiscoverApiBase(): boolean {
  return !EXPLICIT_API_BASE && !apiBaseDiscovered && (!IS_TEST_MODE || apiDiscoveryEnabledForTests);
}

function isAuralithHealthPayload(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') return false;

  const candidate = payload as { app?: unknown; runtime_name?: unknown; product?: unknown };
  return [candidate.app, candidate.runtime_name, candidate.product].some(
    (value) => typeof value === 'string' && value.toLowerCase().includes('auralith')
  );
}

async function fetchDiscoveryHealth(base: string): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_DISCOVERY_TIMEOUT_MS);

  try {
    return await fetch(apiUrl(base, '/api/health'), {
      headers: { Accept: 'application/json' },
      signal: controller.signal
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

async function runApiBaseDiscovery(): Promise<void> {
  let firstHealthyBase: string | null = null;

  for (const base of DEFAULT_API_BASES) {
    try {
      const response = await fetchDiscoveryHealth(base);

      if (!response.ok) continue;
      const payload = (await response.json().catch(() => null)) as unknown;

      if (firstHealthyBase === null) {
        firstHealthyBase = base;
      }

      if (isAuralithHealthPayload(payload)) {
        resolvedApiBase = base;
        apiBaseDiscovered = true;
        return;
      }
    } catch {
      // Try the next local candidate.
    }
  }

  resolvedApiBase = firstHealthyBase ?? '';
  apiBaseDiscovered = true;
}

async function discoverApiBase(): Promise<void> {
  if (!shouldDiscoverApiBase()) return;

  apiDiscoveryPromise ??= runApiBaseDiscovery().finally(() => {
    apiDiscoveryPromise = null;
  });
  await apiDiscoveryPromise;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  let lastResponse: Response | null = null;
  let lastError: unknown = null;

  await discoverApiBase();

  if (init?.signal?.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError');
  }

  for (const base of apiBaseCandidates()) {
    try {
      const response = await fetch(apiUrl(base, path), init);

      if (response.ok || !shouldRetryApiBase(response)) {
        resolvedApiBase = base;
        return response;
      }

      lastResponse = response;
    } catch (error) {
      lastError = error;
      if (!shouldRetryFetchError(error)) {
        throw error;
      }
    }
  }

  if (lastResponse) return lastResponse;

  if (lastError instanceof Error) {
    throw lastError;
  }

  throw new Error('Aegis Core API is not reachable');
}

export function __resetApiBaseForTests(): void {
  resolvedApiBase = EXPLICIT_API_BASE;
  apiBaseDiscovered = Boolean(EXPLICIT_API_BASE);
  apiDiscoveryEnabledForTests = false;
  apiDiscoveryPromise = null;
}

export function __setApiDiscoveryForTests(enabled: boolean): void {
  apiDiscoveryEnabledForTests = enabled;
}

export function getResolvedApiBase(): string {
  return resolvedApiBase;
}

export function apiResourceUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const base = resolvedApiBase || EXPLICIT_API_BASE;
  return `${base}${normalizedPath}`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    try {
      const payload = (await response.json()) as { detail?: unknown };

      if (typeof payload.detail === 'string' && payload.detail.trim()) {
        return payload.detail;
      }

      if (Array.isArray(payload.detail) && payload.detail.length > 0) {
        return payload.detail
          .map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
              return item.msg;
            }
            return JSON.stringify(item);
          })
          .join('; ');
      }

      return `${response.status} ${response.statusText}`;
    } catch {
      return `${response.status} ${response.statusText}`;
    }
  }

  const text = await response.text();
  return text || `${response.status} ${response.statusText}`;
}

export function getHealth(): Promise<HealthResponse> {
  return jsonFetch<HealthResponse>('/api/health');
}

export function getRuntimeOwnership(workspaceRoot?: string): Promise<RuntimeOwnershipResponse> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  const suffix = query.toString();
  return jsonFetch<RuntimeOwnershipResponse>(`/api/runtime/ownership${suffix ? `?${suffix}` : ''}`);
}

export function registerAccount(request: AuthRegisterRequest): Promise<AuthSessionResponse> {
  return jsonFetch<AuthSessionResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function loginAccount(request: AuthLoginRequest): Promise<AuthSessionResponse> {
  return jsonFetch<AuthSessionResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getCurrentAccount(token: string): Promise<AuthSessionResponse> {
  return jsonFetch<AuthSessionResponse>('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function logoutAccount(token: string): Promise<AuthMessageResponse> {
  return jsonFetch<AuthMessageResponse>('/api/auth/logout', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function requestPasswordReset(request: AuthForgotPasswordRequest): Promise<AuthMessageResponse> {
  return jsonFetch<AuthMessageResponse>('/api/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getConfig(): Promise<AppConfig> {
  return jsonFetch<AppConfig>('/api/config');
}

export function getOnboardingStatus(workspaceRoot?: string): Promise<OnboardingStatusResponse> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  const suffix = query.toString();
  return jsonFetch<OnboardingStatusResponse>(`/api/onboarding/status${suffix ? `?${suffix}` : ''}`);
}

export function updateOnboarding(request: OnboardingUpdateRequest): Promise<OnboardingStatusResponse> {
  return jsonFetch<OnboardingStatusResponse>('/api/onboarding', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function runOnboardingFirstWorkflow(
  request: OnboardingFirstWorkflowRequest
): Promise<OnboardingFirstWorkflowResponse> {
  return jsonFetch<OnboardingFirstWorkflowResponse>('/api/onboarding/first-workflow', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function exportRuntimeSettings(workspaceRoot?: string): Promise<RuntimeSettingsExportResponse> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  const suffix = query.toString();
  return jsonFetch<RuntimeSettingsExportResponse>(`/api/settings/export${suffix ? `?${suffix}` : ''}`);
}

export function importRuntimeSettings(request: RuntimeSettingsImportRequest): Promise<RuntimeSettingsImportResponse> {
  return jsonFetch<RuntimeSettingsImportResponse>('/api/settings/import', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getModels(): Promise<ModelInventoryResponse> {
  return jsonFetch<ModelInventoryResponse>('/api/models');
}

export function getModelRegistry(): Promise<ModelRegistryResponse> {
  return jsonFetch<ModelRegistryResponse>('/api/model-registry');
}

export function getProviderAccounts(): Promise<ProviderAccountsResponse> {
  return jsonFetch<ProviderAccountsResponse>('/api/provider-accounts');
}

export function linkProviderApiKey(
  providerId: string,
  request: ProviderApiKeyLinkRequest
): Promise<ProviderAccountLinkResponse> {
  return jsonFetch<ProviderAccountLinkResponse>(`/api/provider-accounts/${encodeURIComponent(providerId)}/api-key`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function unlinkProviderAccount(providerId: string): Promise<ProviderAccountsResponse> {
  return jsonFetch<ProviderAccountsResponse>(`/api/provider-accounts/${encodeURIComponent(providerId)}`, {
    method: 'DELETE'
  });
}

export function startProviderCliLogin(providerId: string): Promise<ProviderCliLoginResponse> {
  return jsonFetch<ProviderCliLoginResponse>(`/api/provider-accounts/${encodeURIComponent(providerId)}/cli-login`, {
    method: 'POST'
  });
}

export function linkProviderCliSession(providerId: string): Promise<ProviderAccountLinkResponse> {
  return jsonFetch<ProviderAccountLinkResponse>(`/api/provider-accounts/${encodeURIComponent(providerId)}/cli-session`, {
    method: 'POST'
  });
}

export function openProviderSourceRoot(
  request: ProviderSourceRootOpenRequest = {}
): Promise<ProviderSourceRootOpenResponse> {
  return jsonFetch<ProviderSourceRootOpenResponse>('/api/provider-accounts/source-root/open', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function refreshProviderSourceDrop(
  request: ProviderSourceRefreshRequest
): Promise<ProviderSourceRefreshResponse> {
  return jsonFetch<ProviderSourceRefreshResponse>('/api/provider-accounts/source-drops/refresh', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function startProviderSourceRefreshJob(
  request: ProviderSourceRefreshRequest
): Promise<ProviderSourceRefreshJobResponse> {
  return jsonFetch<ProviderSourceRefreshJobResponse>('/api/provider-accounts/source-drops/refresh-jobs', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listProviderSourceRefreshJobs(limit = 25): Promise<ProviderSourceRefreshJobsResponse> {
  const query = new URLSearchParams();
  query.set('limit', String(limit));
  return jsonFetch<ProviderSourceRefreshJobsResponse>(`/api/provider-accounts/source-drops/refresh-jobs?${query.toString()}`);
}

export function getProviderSourceRefreshJob(jobId: string): Promise<ProviderSourceRefreshJobResponse> {
  return jsonFetch<ProviderSourceRefreshJobResponse>(
    `/api/provider-accounts/source-drops/refresh-jobs/${encodeURIComponent(jobId)}`
  );
}

export function cancelProviderSourceRefreshJob(jobId: string): Promise<ProviderSourceRefreshJobResponse> {
  return jsonFetch<ProviderSourceRefreshJobResponse>(
    `/api/provider-accounts/source-drops/refresh-jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: 'POST' }
  );
}

export function retryProviderSourceRefreshJob(jobId: string): Promise<ProviderSourceRefreshJobResponse> {
  return jsonFetch<ProviderSourceRefreshJobResponse>(
    `/api/provider-accounts/source-drops/refresh-jobs/${encodeURIComponent(jobId)}/retry`,
    { method: 'POST' }
  );
}

export function probeProviderCliBridges(providerId = ''): Promise<ProviderAccountsResponse> {
  return jsonFetch<ProviderAccountsResponse>('/api/provider-accounts/cli-bridges/probe', {
    method: 'POST',
    body: JSON.stringify({ provider_id: providerId })
  });
}

export function getModelManager(): Promise<ModelManagerResponse> {
  return jsonFetch<ModelManagerResponse>('/api/model-manager');
}

export function pullModel(request: ModelPullRequest): Promise<ModelOperationInfo> {
  return jsonFetch<ModelOperationInfo>('/api/model-manager/pull', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function deleteModel(request: ModelDeleteRequest): Promise<ModelOperationInfo> {
  return jsonFetch<ModelOperationInfo>('/api/model-manager/delete', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function saveConfig(request: ConfigUpdateRequest): Promise<AppConfig> {
  return jsonFetch<AppConfig>('/api/config', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listFiles(workspaceRoot?: string, maxFiles = 120): Promise<FilesResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  query.set('max_files', String(maxFiles));

  return jsonFetch<FilesResponse>(`/api/files?${query.toString()}`);
}

export function readFile(workspaceRoot: string | undefined, path: string): Promise<FileContentResponse> {
  const query = new URLSearchParams({ path });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<FileContentResponse>(`/api/file?${query.toString()}`);
}

export function sendAgentMessage(request: AgentRequest): Promise<AgentResponse> {
  return jsonFetch<AgentResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function executeAgentBridge(request: AgentBridgeExecuteRequest): Promise<AgentBridgeExecuteResponse> {
  return jsonFetch<AgentBridgeExecuteResponse>('/api/agent-bridges/execute', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function preflightAgentBridge(request: AgentBridgeExecuteRequest): Promise<AgentBridgePreflightResponse> {
  return jsonFetch<AgentBridgePreflightResponse>('/api/agent-bridges/preflight', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function startAgentBridgeJob(request: AgentBridgeExecuteRequest): Promise<AgentBridgeJobResponse> {
  return jsonFetch<AgentBridgeJobResponse>('/api/agent-bridges/jobs', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listAgentBridgeJobs(limit = 25): Promise<AgentBridgeJobsResponse> {
  const query = new URLSearchParams({ limit: String(limit) });
  return jsonFetch<AgentBridgeJobsResponse>(`/api/agent-bridges/jobs?${query.toString()}`);
}

export function getAgentBridgeJob(jobId: string): Promise<AgentBridgeJobResponse> {
  return jsonFetch<AgentBridgeJobResponse>(`/api/agent-bridges/jobs/${encodeURIComponent(jobId)}`);
}

export function cancelAgentBridgeJob(jobId: string): Promise<AgentBridgeJobResponse> {
  return jsonFetch<AgentBridgeJobResponse>(`/api/agent-bridges/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST'
  });
}

export function retryAgentBridgeJob(jobId: string): Promise<AgentBridgeJobResponse> {
  return jsonFetch<AgentBridgeJobResponse>(`/api/agent-bridges/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST'
  });
}

export async function streamAgentBridge(
  request: AgentBridgeExecuteRequest,
  handlers: {
    onMeta?: (payload: AgentBridgeStreamPayload) => void;
    onStatus?: (payload: AgentBridgeStreamPayload) => void;
    onDelta?: (payload: AgentBridgeStreamPayload) => void;
    onFinal?: (payload: AgentBridgeStreamPayload) => void;
    signal?: AbortSignal;
  } = {}
): Promise<AgentBridgeExecuteResponse> {
  const response = await apiFetch('/api/agent-bridges/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    signal: handlers.signal,
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    return executeAgentBridge(request);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: AgentBridgeExecuteResponse | null = null;

  const processFrame = (frame: string) => {
    const parsed = parseStreamFrame(frame);
    if (!parsed) return;
    const { event, payload } = parsed;
    const bridgePayload = payload as AgentBridgeStreamPayload;

    if (event === 'meta') {
      handlers.onMeta?.(bridgePayload);
    } else if (event === 'status') {
      handlers.onStatus?.(bridgePayload);
    } else if (event === 'delta') {
      handlers.onDelta?.(bridgePayload);
    } else if (event === 'final') {
      handlers.onFinal?.(bridgePayload);
      if (bridgePayload.bridge_response) {
        finalResponse = bridgePayload.bridge_response;
      }
    } else if (event === 'error') {
      throw new Error(bridgePayload.message || bridgePayload.detail || 'Provider bridge streaming request failed');
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? '';

    for (const frame of frames) {
      processFrame(frame);
    }

    if (done) {
      processFrame(buffer);
      break;
    }
  }

  if (finalResponse) return finalResponse;
  throw new Error('Provider bridge stream ended before a final response was received');
}

export function getChatStreamContract(): Promise<ChatStreamContractResponse> {
  return jsonFetch<ChatStreamContractResponse>('/api/chat/stream/contract');
}

export function getAgentSupervision(
  workspaceRoot?: string,
  workflowId?: string,
  limit = 30
): Promise<AgentSupervisionSnapshot> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (workflowId?.trim()) {
    query.set('workflow_id', workflowId.trim());
  }

  return jsonFetch<AgentSupervisionSnapshot>(`/api/agent-supervision?${query.toString()}`);
}

export function getAutopilotModes(): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/autopilot/modes');
}

export function getAutopilotSupervision(
  workspaceRoot?: string,
  autopilotId?: string
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (autopilotId?.trim()) {
    query.set('autopilot_id', autopilotId.trim());
  }

  return jsonFetch<Record<string, unknown>>(`/api/autopilot/supervision?${query.toString()}`);
}

export function startAutopilot(request: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/autopilot/start', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function sendAutopilotAction(
  autopilotId: string,
  request: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>(`/api/autopilot/runs/${encodeURIComponent(autopilotId)}/action`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getAutopilotReplay(workspaceRoot: string | undefined, autopilotId: string): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<Record<string, unknown>>(`/api/autopilot/runs/${encodeURIComponent(autopilotId)}/replay?${query.toString()}`);
}

export function getAutopilotObservability(workspaceRoot?: string): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<Record<string, unknown>>(`/api/autopilot/observability?${query.toString()}`);
}

export function getAutopilotMemory(workspaceRoot?: string): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<Record<string, unknown>>(`/api/autopilot/memory?${query.toString()}`);
}

export function getCollaborationDashboard(
  workspaceRoot?: string,
  options: { userId?: string; role?: string; limit?: number } = {}
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.userId?.trim()) {
    query.set('user_id', options.userId.trim());
  }
  if (options.role?.trim()) {
    query.set('role', options.role.trim());
  }
  if (options.limit) {
    query.set('limit', String(options.limit));
  }
  return jsonFetch<Record<string, unknown>>(`/api/collaboration?${query.toString()}`);
}

export function getGovernanceDashboard(
  workspaceRoot?: string,
  options: { includeAudit?: boolean; limit?: number } = {}
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.includeAudit !== undefined) {
    query.set('include_audit', String(options.includeAudit));
  }
  if (options.limit) {
    query.set('limit', String(options.limit));
  }
  return jsonFetch<Record<string, unknown>>(`/api/governance?${query.toString()}`);
}

export function registerCollaborationMember(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/collaboration/members', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function registerCollaborationRepository(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/collaboration/repositories', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function createCollaborationWorkflow(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/collaboration/workflows', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function collaborationWorkflowAction(
  workflowId: string,
  payload: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>(`/api/collaboration/workflows/${encodeURIComponent(workflowId)}/action`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function createCollaborationApproval(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/collaboration/approvals', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function decideCollaborationApproval(
  approvalId: string,
  payload: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>(`/api/collaboration/approvals/${encodeURIComponent(approvalId)}/decision`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function assignCollaborationRoadmapItem(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/collaboration/roadmap/items', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function stepAgentWorkflow(
  workflowId: string,
  request: AgentSupervisionActionRequest
): Promise<AgentSupervisionActionResponse> {
  return jsonFetch<AgentSupervisionActionResponse>(
    `/api/agent-supervision/workflows/${encodeURIComponent(workflowId)}/step`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function delegateAgentWorkflowTask(
  workflowId: string,
  request: AgentSupervisionDelegationRequest
): Promise<AgentSupervisionActionResponse> {
  return jsonFetch<AgentSupervisionActionResponse>(
    `/api/agent-supervision/workflows/${encodeURIComponent(workflowId)}/agents/delegate`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function agentSupervisionEventsUrl(workflowId: string, workspaceRoot?: string, since = 0): string {
  const query = new URLSearchParams({ follow: 'true', since: String(Math.max(0, since)) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return apiResourceUrl(`/api/agent-supervision/workflows/${encodeURIComponent(workflowId)}/events?${query.toString()}`);
}

export function getQualityGates(workspaceRoot?: string, limit = 50): Promise<QualityGateSnapshot> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<QualityGateSnapshot>(`/api/quality-gates?${query.toString()}`);
}

export function evaluateQualityGates(request: QualityGateEvaluationRequest): Promise<QualityGateEvaluation> {
  return jsonFetch<QualityGateEvaluation>('/api/quality-gates/evaluate', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getWorkflowQualityGates(workflowId: string, workspaceRoot?: string): Promise<QualityGateSnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<QualityGateSnapshot>(
    `/api/quality-gates/workflows/${encodeURIComponent(workflowId)}?${query.toString()}`
  );
}

export function getQualityBenchmarks(workspaceRoot?: string, limit = 50): Promise<QualityBenchmarkDashboard> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<QualityBenchmarkDashboard>(`/api/benchmarks?${query.toString()}`);
}

export function runQualityBenchmark(request: QualityBenchmarkRunRequest): Promise<Record<string, unknown>> {
  return jsonFetch<Record<string, unknown>>('/api/benchmarks/run', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getEvaluationReports(
  workspaceRoot?: string,
  workflowId?: string,
  limit = 50
): Promise<EvaluationReportsResponse> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (workflowId?.trim()) {
    query.set('workflow_id', workflowId.trim());
  }
  return jsonFetch<EvaluationReportsResponse>(`/api/evaluation-reports?${query.toString()}`);
}

export async function streamAgentMessage(
  request: AgentRequest,
  handlers: {
    onMeta?: (payload: ChatStreamPayload) => void;
    onStatus?: (payload: ChatStreamPayload) => void;
    onDelta?: (payload: ChatStreamPayload) => void;
    onFinal?: (payload: ChatStreamPayload) => void;
    signal?: AbortSignal;
  } = {}
): Promise<AgentResponse> {
  const response = await apiFetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    signal: handlers.signal,
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    return sendAgentMessage(request);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: AgentResponse | null = null;

  const processFrame = (frame: string) => {
    const parsed = parseStreamFrame(frame);
    if (!parsed) return;
    const { event, payload } = parsed;

    if (event === 'meta') {
      handlers.onMeta?.(payload);
    } else if (event === 'status') {
      handlers.onStatus?.(payload);
    } else if (event === 'delta') {
      handlers.onDelta?.(payload);
    } else if (event === 'final') {
      handlers.onFinal?.(payload);
      if (payload.response) {
        finalResponse = payload.response;
      }
    } else if (event === 'error') {
      throw new Error(payload.message || payload.detail || 'Auralith Prime streaming request failed');
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? '';

    for (const frame of frames) {
      processFrame(frame);
    }

    if (done) {
      processFrame(buffer);
      break;
    }
  }

  if (finalResponse) return finalResponse;
  throw new Error('Auralith Prime stream ended before a final response was received');
}

function parseStreamFrame(frame: string): { event: string; payload: ChatStreamPayload } | null {
  const lines = frame.split(/\r?\n/);
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (!dataLines.length) return null;

  try {
    return { event, payload: JSON.parse(dataLines.join('\n')) as ChatStreamPayload };
  } catch {
    return {
      event,
      payload: {
        type: event,
        message: dataLines.join('\n')
      }
    };
  }
}

export function applyFileChanges(request: ApplyRequest): Promise<ApplyResponse> {
  return jsonFetch<ApplyResponse>('/api/apply', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getCheckpoints(workspaceRoot?: string, limit = 8): Promise<CheckpointListResponse> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<CheckpointListResponse>(`/api/checkpoints?${query.toString()}`);
}

export function restoreCheckpoint(request: RestoreCheckpointRequest): Promise<RestoreCheckpointResponse> {
  return jsonFetch<RestoreCheckpointResponse>('/api/restore-checkpoint', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function runWorkspaceValidation(request: ValidateRequest): Promise<ValidateResponse> {
  return jsonFetch<ValidateResponse>('/api/validate', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getWorkspaceHistory(workspaceRoot?: string, limit = 8): Promise<HistoryResponse> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<HistoryResponse>(`/api/history?${query.toString()}`);
}

export function listTasks(
  workspaceRoot?: string,
  options: { status?: string; includeSubtasks?: boolean; limit?: number } = {}
): Promise<TaskListResponse> {
  const query = new URLSearchParams({
    limit: String(options.limit ?? 50),
    include_subtasks: String(options.includeSubtasks ?? false)
  });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  if (options.status?.trim()) {
    query.set('status', options.status.trim());
  }

  return jsonFetch<TaskListResponse>(`/api/tasks?${query.toString()}`);
}

export function createTask(request: TaskCreateRequest): Promise<TaskDetailResponse> {
  return jsonFetch<TaskDetailResponse>('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getTask(taskId: string): Promise<TaskDetailResponse> {
  return jsonFetch<TaskDetailResponse>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function cancelTask(taskId: string, request: TaskActionRequest = {}): Promise<TaskActionResponse> {
  return jsonFetch<TaskActionResponse>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function approveTaskAction(taskId: string, request: TaskActionRequest): Promise<TaskActionResponse> {
  return jsonFetch<TaskActionResponse>(`/api/tasks/${encodeURIComponent(taskId)}/approve`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function retryTask(taskId: string, request: TaskActionRequest = {}): Promise<TaskActionResponse> {
  return jsonFetch<TaskActionResponse>(`/api/tasks/${encodeURIComponent(taskId)}/retry`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getTaskTimeline(taskId: string): Promise<TaskTimelineResponse> {
  return jsonFetch<TaskTimelineResponse>(`/api/tasks/${encodeURIComponent(taskId)}/timeline`);
}

export function getTaskArtifacts(taskId: string): Promise<TaskArtifactsResponse> {
  return jsonFetch<TaskArtifactsResponse>(`/api/tasks/${encodeURIComponent(taskId)}/artifacts`);
}

export function getCreativeStudio(): Promise<MediaCapabilitiesResponse> {
  return jsonFetch<MediaCapabilitiesResponse>('/api/creative-studio');
}

export function listCreativeProviders(): Promise<MediaProviderInfo[]> {
  return jsonFetch<MediaProviderInfo[]>('/api/creative-studio/providers');
}

export function listCreativePromptPresets(): Promise<MediaPromptPreset[]> {
  return jsonFetch<MediaPromptPreset[]>('/api/creative-studio/prompt-presets');
}

export function listCreativeJobs(options: { limit?: number; kind?: string } = {}): Promise<MediaJobResponse[]> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 50) });
  if (options.kind?.trim()) {
    query.set('kind', options.kind.trim());
  }
  return jsonFetch<MediaJobResponse[]>(`/api/creative-studio/jobs?${query.toString()}`);
}

export function getCreativeJob(jobId: string): Promise<MediaJobResponse> {
  return jsonFetch<MediaJobResponse>(`/api/creative-studio/jobs/${encodeURIComponent(jobId)}`);
}

export function createCreativeJob(request: MediaCreativeRequest): Promise<MediaJobResponse> {
  return jsonFetch<MediaJobResponse>('/api/creative-studio/jobs', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function cancelCreativeJob(jobId: string): Promise<MediaJobResponse> {
  return jsonFetch<MediaJobResponse>(`/api/creative-studio/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST'
  });
}

export function getCreativeAssetLibrary(
  options: { limit?: number; kind?: string; format?: string } = {}
): Promise<MediaAssetLibraryResponse> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 100) });
  if (options.kind?.trim()) query.set('kind', options.kind.trim());
  if (options.format?.trim()) query.set('format', options.format.trim());
  return jsonFetch<MediaAssetLibraryResponse>(`/api/creative-studio/assets?${query.toString()}`);
}

export function exportCreativeJob(jobId: string, request: MediaExportRequest): Promise<MediaExportResponse> {
  return jsonFetch<MediaExportResponse>(`/api/creative-studio/jobs/${encodeURIComponent(jobId)}/export`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getUnifiedRuntime(workspaceRoot?: string): Promise<UnifiedRuntimeSnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<UnifiedRuntimeSnapshot>(`/api/unified-runtime?${query.toString()}`);
}

export function getOperatingEnvironment(workspaceRoot?: string): Promise<OperatingEnvironmentSnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<OperatingEnvironmentSnapshot>(`/api/operating-environment?${query.toString()}`);
}

export function previewOperatingEnvironmentAction(
  request: OperatingEnvironmentActionRequest
): Promise<OperatingEnvironmentActionResponse> {
  return jsonFetch<OperatingEnvironmentActionResponse>('/api/operating-environment/actions/preview', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getUnifiedContext(workspaceRoot?: string): Promise<UnifiedContextSnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<UnifiedContextSnapshot>(`/api/unified-context?${query.toString()}`);
}

export function searchUnifiedContext(request: UnifiedContextSearchRequest): Promise<UnifiedContextSearchResponse> {
  return jsonFetch<UnifiedContextSearchResponse>('/api/unified-context/search', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function previewGlobalCommand(request: GlobalCommandRequest): Promise<GlobalCommandResponse> {
  return jsonFetch<GlobalCommandResponse>('/api/global-command/preview', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function submitGlobalCommand(request: GlobalCommandRequest): Promise<GlobalCommandResponse> {
  return jsonFetch<GlobalCommandResponse>('/api/global-command/submit', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getContinuity(workspaceRoot?: string): Promise<AegisContinuitySnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<AegisContinuitySnapshot>(`/api/continuity?${query.toString()}`);
}

export function getPlatformDiscipline(workspaceRoot?: string): Promise<PlatformDisciplineSnapshot> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<PlatformDisciplineSnapshot>(`/api/platform-discipline?${query.toString()}`);
}

export function searchContinuityTimeline(request: TimelineSearchRequest): Promise<TimelineSearchResponse> {
  return jsonFetch<TimelineSearchResponse>('/api/continuity/timeline/search', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getDistributedRuntime(workspaceRoot?: string): Promise<DistributedRuntimeSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<DistributedRuntimeSnapshot>(`/api/distributed-runtime?${query.toString()}`);
}

export function getRuntimeInteraction(workspaceRoot?: string, limit = 100): Promise<RuntimeInteractionSnapshot> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RuntimeInteractionSnapshot>(`/api/runtime-interaction?${query.toString()}`);
}

export function createRuntimeTerminalJob(request: RuntimeTerminalJobRequest): Promise<RuntimeJobMutationResponse> {
  return jsonFetch<RuntimeJobMutationResponse>('/api/runtime-interaction/jobs', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function cancelRuntimeTerminalJob(
  jobId: string,
  request: RuntimeJobActionRequest
): Promise<RuntimeJobMutationResponse> {
  return jsonFetch<RuntimeJobMutationResponse>(`/api/runtime-interaction/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function retryRuntimeTerminalJob(
  jobId: string,
  request: RuntimeJobActionRequest
): Promise<RuntimeJobMutationResponse> {
  return jsonFetch<RuntimeJobMutationResponse>(`/api/runtime-interaction/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getRuntimeInteractionStreams(
  workspaceRoot?: string,
  options: { jobId?: string; workflowId?: string; since?: number; limit?: number } = {}
): Promise<RuntimeStreamsResponse> {
  const query = new URLSearchParams({
    since: String(Math.max(0, options.since ?? 0)),
    limit: String(options.limit ?? 100)
  });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.jobId?.trim()) {
    query.set('job_id', options.jobId.trim());
  }
  if (options.workflowId?.trim()) {
    query.set('workflow_id', options.workflowId.trim());
  }

  return jsonFetch<RuntimeStreamsResponse>(`/api/runtime-interaction/streams?${query.toString()}`);
}

export function runtimeInteractionEventsUrl(
  workspaceRoot?: string,
  options: { jobId?: string; workflowId?: string; since?: number; limit?: number; maxSeconds?: number } = {}
): string {
  const query = new URLSearchParams({
    follow: 'true',
    since: String(Math.max(0, options.since ?? 0)),
    limit: String(options.limit ?? 100),
    max_seconds: String(options.maxSeconds ?? 30)
  });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.jobId?.trim()) {
    query.set('job_id', options.jobId.trim());
  }
  if (options.workflowId?.trim()) {
    query.set('workflow_id', options.workflowId.trim());
  }

  return apiResourceUrl(`/api/runtime-interaction/events?${query.toString()}`);
}

export function createRuntimeSession(request: RuntimeSessionRequest): Promise<RuntimeSessionMutationResponse> {
  return jsonFetch<RuntimeSessionMutationResponse>('/api/runtime-interaction/sessions', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function syncRuntimeSession(
  sessionId: string,
  request: RuntimeSessionSyncRequest
): Promise<RuntimeSessionMutationResponse> {
  return jsonFetch<RuntimeSessionMutationResponse>(`/api/runtime-interaction/sessions/${encodeURIComponent(sessionId)}/sync`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getRuntimeVoice(workspaceRoot?: string): Promise<RuntimeVoiceResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RuntimeVoiceResponse>(`/api/runtime-interaction/voice?${query.toString()}`);
}

export function routeRuntimeVoiceCommand(request: RuntimeVoiceCommandRequest): Promise<RuntimeVoiceCommandResponse> {
  return jsonFetch<RuntimeVoiceCommandResponse>('/api/runtime-interaction/voice/command', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getRuntimeReplay(
  workspaceRoot?: string,
  options: { workflowId?: string; jobId?: string; limit?: number } = {}
): Promise<RuntimeReplayResponse> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 200) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.workflowId?.trim()) {
    query.set('workflow_id', options.workflowId.trim());
  }
  if (options.jobId?.trim()) {
    query.set('job_id', options.jobId.trim());
  }

  return jsonFetch<RuntimeReplayResponse>(`/api/runtime-interaction/replay?${query.toString()}`);
}

export function getRuntimeObservability(workspaceRoot?: string): Promise<RuntimeObservabilitySnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RuntimeObservabilitySnapshot>(`/api/distributed-runtime/observability?${query.toString()}`);
}

export function listRuntimeWorkers(workspaceRoot?: string): Promise<WorkerRuntimeInfo[]> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<WorkerRuntimeInfo[]>(`/api/distributed-runtime/workers?${query.toString()}`);
}

export function registerRuntimeWorker(request: WorkerRegistrationRequest): Promise<WorkerRuntimeInfo> {
  return jsonFetch<WorkerRuntimeInfo>('/api/distributed-runtime/workers/register', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function heartbeatRuntimeWorker(workerId: string, request: WorkerHeartbeatRequest): Promise<WorkerRuntimeInfo> {
  return jsonFetch<WorkerRuntimeInfo>(`/api/distributed-runtime/workers/${encodeURIComponent(workerId)}/heartbeat`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function revokeRuntimeWorker(workerId: string, request: WorkerActionRequest = {}): Promise<WorkerRuntimeInfo> {
  return jsonFetch<WorkerRuntimeInfo>(`/api/distributed-runtime/workers/${encodeURIComponent(workerId)}/revoke`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listExecutionQueue(
  workspaceRoot?: string,
  options: { status?: string; limit?: number } = {}
): Promise<ExecutionQueueItem[]> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 100) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  if (options.status?.trim()) {
    query.set('status', options.status.trim());
  }

  return jsonFetch<ExecutionQueueItem[]>(`/api/distributed-runtime/queue?${query.toString()}`);
}

export function createExecutionQueueItem(request: ExecutionQueueCreateRequest): Promise<ExecutionQueueItem> {
  return jsonFetch<ExecutionQueueItem>('/api/distributed-runtime/queue', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getExecutionQueueItem(jobId: string): Promise<ExecutionQueueItem> {
  return jsonFetch<ExecutionQueueItem>(`/api/distributed-runtime/queue/${encodeURIComponent(jobId)}`);
}

export function cancelExecutionQueueItem(
  jobId: string,
  request: ExecutionQueueActionRequest = {}
): Promise<ExecutionQueueItem> {
  return jsonFetch<ExecutionQueueItem>(`/api/distributed-runtime/queue/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function retryExecutionQueueItem(
  jobId: string,
  request: ExecutionQueueActionRequest = {}
): Promise<ExecutionQueueItem> {
  return jsonFetch<ExecutionQueueItem>(`/api/distributed-runtime/queue/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function dispatchExecutionQueue(request: ExecutionDispatchRequest): Promise<ExecutionDispatchResponse> {
  return jsonFetch<ExecutionDispatchResponse>('/api/distributed-runtime/dispatch', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function routeDistributedModel(request: HybridRouteRequest): Promise<HybridRouteDecision> {
  return jsonFetch<HybridRouteDecision>('/api/distributed-runtime/route', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getDistributedRuntimeAudit(
  options: { workerId?: string; jobId?: string; limit?: number } = {}
): Promise<WorkerAuditEvent[]> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 100) });

  if (options.workerId?.trim()) {
    query.set('worker_id', options.workerId.trim());
  }

  if (options.jobId?.trim()) {
    query.set('job_id', options.jobId.trim());
  }

  return jsonFetch<WorkerAuditEvent[]>(`/api/distributed-runtime/audit?${query.toString()}`);
}

export function listRemoteSyncManifests(workspaceRoot?: string, limit = 20): Promise<RemoteWorkspaceSyncManifest[]> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RemoteWorkspaceSyncManifest[]>(`/api/distributed-runtime/sync/manifests?${query.toString()}`);
}

export function createRemoteSyncManifest(request: RemoteWorkspaceSyncRequest): Promise<RemoteWorkspaceSyncManifest> {
  return jsonFetch<RemoteWorkspaceSyncManifest>('/api/distributed-runtime/sync/export', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getRouteQuality(workspaceRoot?: string, limit = 200): Promise<RouteQualityResponse> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RouteQualityResponse>(`/api/telemetry/route-quality?${query.toString()}`);
}

export function getFallbackInspector(workspaceRoot?: string, limit = 20): Promise<FallbackInspectorResponse> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<FallbackInspectorResponse>(`/api/telemetry/fallback-inspector?${query.toString()}`);
}

export function getFeedbackTelemetry(workspaceRoot?: string, limit = 100): Promise<FeedbackTelemetryResponse> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<FeedbackTelemetryResponse>(`/api/telemetry/feedback?${query.toString()}`);
}

function telemetrySnapshotQuery(workspaceRoot: string | undefined, options: TelemetrySnapshotOptions): URLSearchParams {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  query.set('route_quality_limit', String(options.routeQualityLimit ?? 200));
  query.set('fallback_limit', String(options.fallbackLimit ?? 20));
  query.set('feedback_limit', String(options.feedbackLimit ?? 100));
  query.set('stale_after_seconds', String(options.staleAfterSeconds ?? 900));

  if (options.prune !== undefined) {
    query.set('prune', String(options.prune));
  }
  if (options.maxSnapshots !== undefined) {
    query.set('max_snapshots', String(options.maxSnapshots));
  }
  if (options.retentionDays !== undefined) {
    query.set('retention_days', String(options.retentionDays));
  }
  if (options.refresh) {
    query.set('refresh', 'true');
  }

  return query;
}

export function getTelemetrySnapshot(
  workspaceRoot?: string,
  options: TelemetrySnapshotOptions = {}
): Promise<TelemetrySnapshotResponse> {
  const query = telemetrySnapshotQuery(workspaceRoot, options);
  return jsonFetch<TelemetrySnapshotResponse>(`/api/telemetry/snapshot?${query.toString()}`);
}

export function refreshTelemetrySnapshot(
  workspaceRoot?: string,
  options: TelemetrySnapshotOptions = {}
): Promise<TelemetrySnapshotResponse> {
  const query = telemetrySnapshotQuery(workspaceRoot, options);
  return jsonFetch<TelemetrySnapshotResponse>(`/api/telemetry/snapshot/refresh?${query.toString()}`, {
    method: 'POST'
  });
}

export function getRoutePolicyDiff(
  workspaceRoot?: string,
  options: RoutePolicyDiffOptions = {}
): Promise<RoutePolicyDiffResponse> {
  const query = new URLSearchParams({
    limit: String(options.limit ?? 200),
    use_snapshot: String(options.useSnapshot ?? true),
    stale_after_seconds: String(options.staleAfterSeconds ?? 900),
    min_attempts: String(options.minAttempts ?? 3)
  });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RoutePolicyDiffResponse>(`/api/telemetry/policy-diff?${query.toString()}`);
}

export function getAdaptiveIntelligence(
  workspaceRoot?: string,
  options: { limit?: number; refresh?: boolean } = {}
): Promise<AdaptiveIntelligenceSnapshot> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 200) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.refresh) {
    query.set('refresh', 'true');
  }

  return jsonFetch<AdaptiveIntelligenceSnapshot>(`/api/adaptive-intelligence?${query.toString()}`);
}

export function refreshAdaptiveIntelligence(
  request: AdaptiveIntelligenceRefreshRequest
): Promise<AdaptiveIntelligenceSnapshot> {
  return jsonFetch<AdaptiveIntelligenceSnapshot>('/api/adaptive-intelligence/refresh', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listAdaptiveTaskOutcomes(
  workspaceRoot?: string,
  options: { limit?: number; refresh?: boolean } = {}
): Promise<TaskOutcomeRecord[]> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 200) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.refresh) {
    query.set('refresh', 'true');
  }

  return jsonFetch<TaskOutcomeRecord[]>(`/api/adaptive-intelligence/outcomes?${query.toString()}`);
}

export function listAdaptivePolicyProfiles(): Promise<IntelligencePolicyProfile[]> {
  return jsonFetch<IntelligencePolicyProfile[]>('/api/adaptive-intelligence/policies');
}

export function saveAdaptivePolicyProfile(
  request: AdaptivePolicyProfileUpdateRequest
): Promise<IntelligencePolicyProfile> {
  return jsonFetch<IntelligencePolicyProfile>('/api/adaptive-intelligence/policies', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function activateAdaptivePolicyProfile(
  profileId: string,
  request: TaskActionRequest = {},
  workspaceRoot?: string
): Promise<AdaptiveIntelligenceSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<AdaptiveIntelligenceSnapshot>(
    `/api/adaptive-intelligence/policies/${encodeURIComponent(profileId)}/activate?${query.toString()}`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function rollbackAdaptivePolicy(
  request: AdaptivePolicyRollbackRequest
): Promise<AdaptiveIntelligenceSnapshot> {
  return jsonFetch<AdaptiveIntelligenceSnapshot>('/api/adaptive-intelligence/policies/rollback', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function runAdaptiveBenchmarks(request: AdaptiveBenchmarkRunRequest): Promise<AdaptiveBenchmarkReport[]> {
  return jsonFetch<AdaptiveBenchmarkReport[]>('/api/adaptive-intelligence/benchmarks/run', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listAdaptiveBenchmarks(workspaceRoot?: string, limit = 20): Promise<AdaptiveBenchmarkReport[]> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<AdaptiveBenchmarkReport[]>(`/api/adaptive-intelligence/benchmarks?${query.toString()}`);
}

export function replayAdaptiveTasks(request: AdaptiveReplayRequest): Promise<EvaluationReplayResult[]> {
  return jsonFetch<EvaluationReplayResult[]>('/api/adaptive-intelligence/replay', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listAdaptiveReplayResults(workspaceRoot?: string, limit = 20): Promise<EvaluationReplayResult[]> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<EvaluationReplayResult[]>(`/api/adaptive-intelligence/replay?${query.toString()}`);
}

export function getProductization(
  workspaceRoot?: string,
  options: { refreshMetrics?: boolean } = {}
): Promise<ProductizationSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.refreshMetrics) {
    query.set('refresh_metrics', 'true');
  }

  return jsonFetch<ProductizationSnapshot>(`/api/productization?${query.toString()}`);
}

export function refreshProductization(request: ProductizationRefreshRequest): Promise<ProductizationSnapshot> {
  return jsonFetch<ProductizationSnapshot>('/api/productization/refresh', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listStableApis(): Promise<StableApiContract[]> {
  return jsonFetch<StableApiContract[]>('/api/productization/stable-apis');
}

export function getRuntimeRecovery(workspaceRoot?: string): Promise<RuntimeRecoverySnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<RuntimeRecoverySnapshot>(`/api/productization/recovery?${query.toString()}`);
}

export function getReliabilityMetrics(workspaceRoot?: string): Promise<ReliabilityMetric[]> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ReliabilityMetric[]>(`/api/productization/reliability?${query.toString()}`);
}

export function listPlugins(includeDisabled = true): Promise<PluginManifest[]> {
  const query = new URLSearchParams({ include_disabled: includeDisabled ? 'true' : 'false' });
  return jsonFetch<PluginManifest[]>(`/api/productization/plugins?${query.toString()}`);
}

export function validatePlugin(request: PluginValidationRequest): Promise<PluginValidationResult> {
  return jsonFetch<PluginValidationResult>('/api/productization/plugins/validate', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function registerPlugin(request: PluginRegistrationRequest): Promise<PluginManifest> {
  return jsonFetch<PluginManifest>('/api/productization/plugins/register', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function enablePlugin(pluginId: string, request: PluginActionRequest = {}): Promise<PluginManifest> {
  return jsonFetch<PluginManifest>(`/api/productization/plugins/${encodeURIComponent(pluginId)}/enable`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function disablePlugin(pluginId: string, request: PluginActionRequest = {}): Promise<PluginManifest> {
  return jsonFetch<PluginManifest>(`/api/productization/plugins/${encodeURIComponent(pluginId)}/disable`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function trustPlugin(pluginId: string, request: PluginActionRequest = {}): Promise<PluginManifest> {
  return jsonFetch<PluginManifest>(`/api/productization/plugins/${encodeURIComponent(pluginId)}/trust`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getEnterprisePolicy(): Promise<EnterprisePolicyProfile> {
  return jsonFetch<EnterprisePolicyProfile>('/api/productization/enterprise-policy');
}

export function updateEnterprisePolicy(request: EnterprisePolicyUpdateRequest): Promise<EnterprisePolicyProfile> {
  return jsonFetch<EnterprisePolicyProfile>('/api/productization/enterprise-policy', {
    method: 'PUT',
    body: JSON.stringify(request)
  });
}

export function getEcosystem(
  workspaceRoot?: string,
  options: { rebuildGraph?: boolean; query?: string } = {}
): Promise<EcosystemSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (options.rebuildGraph !== undefined) {
    query.set('rebuild_graph', String(options.rebuildGraph));
  }
  if (options.query?.trim()) {
    query.set('query', options.query.trim());
  }

  return jsonFetch<EcosystemSnapshot>(`/api/ecosystem?${query.toString()}`);
}

export function refreshEcosystem(request: EcosystemRefreshRequest): Promise<EcosystemSnapshot> {
  return jsonFetch<EcosystemSnapshot>('/api/ecosystem/refresh', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listEcosystemMarketplace(): Promise<EcosystemPackageManifest[]> {
  return jsonFetch<EcosystemPackageManifest[]>('/api/ecosystem/marketplace');
}

export function listEcosystemPackages(includeDisabled = true): Promise<EcosystemPackageManifest[]> {
  return jsonFetch<EcosystemPackageManifest[]>(`/api/ecosystem/packages?include_disabled=${includeDisabled}`);
}

export function validateEcosystemPackage(
  request: EcosystemPackageValidationRequest
): Promise<EcosystemPackageValidationResult> {
  return jsonFetch<EcosystemPackageValidationResult>('/api/ecosystem/packages/validate', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function registerEcosystemPackage(
  request: EcosystemPackageRegistrationRequest
): Promise<EcosystemPackageManifest> {
  return jsonFetch<EcosystemPackageManifest>('/api/ecosystem/packages/register', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function enableEcosystemPackage(
  packageId: string,
  request: EcosystemPackageActionRequest = {}
): Promise<EcosystemPackageManifest> {
  return jsonFetch<EcosystemPackageManifest>(`/api/ecosystem/packages/${encodeURIComponent(packageId)}/enable`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function disableEcosystemPackage(
  packageId: string,
  request: EcosystemPackageActionRequest = {}
): Promise<EcosystemPackageManifest> {
  return jsonFetch<EcosystemPackageManifest>(`/api/ecosystem/packages/${encodeURIComponent(packageId)}/disable`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function trustEcosystemPackage(
  packageId: string,
  request: EcosystemPackageActionRequest = {}
): Promise<EcosystemPackageManifest> {
  return jsonFetch<EcosystemPackageManifest>(`/api/ecosystem/packages/${encodeURIComponent(packageId)}/trust`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listEcosystemWorkflows(includeDisabled = true): Promise<EcosystemWorkflowDefinition[]> {
  return jsonFetch<EcosystemWorkflowDefinition[]>(`/api/ecosystem/workflows?include_disabled=${includeDisabled}`);
}

export function registerEcosystemWorkflow(
  workflow: EcosystemWorkflowDefinition
): Promise<EcosystemWorkflowDefinition> {
  return jsonFetch<EcosystemWorkflowDefinition>('/api/ecosystem/workflows/register', {
    method: 'POST',
    body: JSON.stringify(workflow)
  });
}

export function runEcosystemWorkflow(workflowId: string, request: WorkflowRunRequest): Promise<WorkflowRunResponse> {
  return jsonFetch<WorkflowRunResponse>(`/api/ecosystem/workflows/${encodeURIComponent(workflowId)}/run`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listSharedIntelligenceProfiles(kind?: string, limit = 50): Promise<SharedIntelligenceProfile[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (kind?.trim()) {
    query.set('kind', kind.trim());
  }
  return jsonFetch<SharedIntelligenceProfile[]>(`/api/ecosystem/shared-profiles?${query.toString()}`);
}

export function importSharedIntelligenceProfile(
  request: SharedIntelligenceProfileImportRequest
): Promise<SharedIntelligenceProfile> {
  return jsonFetch<SharedIntelligenceProfile>('/api/ecosystem/shared-profiles/import', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function exportSharedIntelligenceProfile(profileId: string): Promise<SharedIntelligenceProfileExportResponse> {
  return jsonFetch<SharedIntelligenceProfileExportResponse>(
    `/api/ecosystem/shared-profiles/${encodeURIComponent(profileId)}/export`
  );
}

export function exportCurrentProjectIntelligence(workspaceRoot?: string): Promise<SharedIntelligenceProfileExportResponse> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<SharedIntelligenceProfileExportResponse>(`/api/ecosystem/shared-profiles/export-current?${query.toString()}`, {
    method: 'POST'
  });
}

export function getOrganizationPolicy(): Promise<OrganizationPolicyProfile> {
  return jsonFetch<OrganizationPolicyProfile>('/api/ecosystem/org-policy');
}

export function updateOrganizationPolicy(request: OrganizationPolicyUpdateRequest): Promise<OrganizationPolicyProfile> {
  return jsonFetch<OrganizationPolicyProfile>('/api/ecosystem/org-policy', {
    method: 'PUT',
    body: JSON.stringify(request)
  });
}

export function getKnowledgeGraph(workspaceRoot?: string, rebuild = false): Promise<KnowledgeGraphSnapshot> {
  const query = new URLSearchParams({ rebuild: String(rebuild) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<KnowledgeGraphSnapshot>(`/api/ecosystem/knowledge-graph?${query.toString()}`);
}

export function searchEcosystem(request: EcosystemSearchRequest): Promise<EcosystemSearchResponse> {
  return jsonFetch<EcosystemSearchResponse>('/api/ecosystem/search', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function createReproducibilityRecord(request: ReproducibilityRequest): Promise<ReproducibilityRecord> {
  return jsonFetch<ReproducibilityRecord>('/api/ecosystem/reproducibility', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listReproducibilityRecords(workspaceRoot?: string, limit = 20): Promise<ReproducibilityRecord[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<ReproducibilityRecord[]>(`/api/ecosystem/reproducibility?${query.toString()}`);
}

export function listEcosystemAudit(limit = 50): Promise<EcosystemAuditEvent[]> {
  return jsonFetch<EcosystemAuditEvent[]>(`/api/ecosystem/audit?limit=${limit}`);
}

export function getAutonomousEngineering(workspaceRoot?: string): Promise<AutonomousEngineeringSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<AutonomousEngineeringSnapshot>(`/api/autonomous-engineering?${query.toString()}`);
}

export function listAutonomousObjectives(
  workspaceRoot?: string,
  options: { includeCompleted?: boolean; limit?: number } = {}
): Promise<AutonomousObjective[]> {
  const query = new URLSearchParams({
    include_completed: String(options.includeCompleted ?? true),
    limit: String(options.limit ?? 50)
  });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<AutonomousObjective[]>(`/api/autonomous-engineering/objectives?${query.toString()}`);
}

export function createAutonomousObjective(
  request: AutonomousObjectiveCreateRequest
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>('/api/autonomous-engineering/objectives', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getAutonomousObjective(objectiveId: string): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(`/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}`);
}

export function simulateAutonomousObjective(objectiveId: string): Promise<AutonomousSimulationEstimate> {
  return jsonFetch<AutonomousSimulationEstimate>(
    `/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}/simulate`,
    { method: 'POST' }
  );
}

export function startAutonomousObjective(
  objectiveId: string,
  request: AutonomousObjectiveActionRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}/start`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function pauseAutonomousObjective(
  objectiveId: string,
  request: AutonomousObjectiveActionRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}/pause`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function cancelAutonomousObjective(
  objectiveId: string,
  request: AutonomousObjectiveActionRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}/cancel`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function iterateAutonomousObjective(
  objectiveId: string,
  request: AutonomousObjectiveIterationRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/objectives/${encodeURIComponent(objectiveId)}/iterate`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function listAutonomousApprovalGates(workspaceRoot?: string, limit = 100): Promise<AutonomousApprovalGate[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<AutonomousApprovalGate[]>(`/api/autonomous-engineering/approval-gates?${query.toString()}`);
}

export function approveAutonomousGate(
  gateId: string,
  request: AutonomousApprovalActionRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/approval-gates/${encodeURIComponent(gateId)}/approve`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function rejectAutonomousGate(
  gateId: string,
  request: AutonomousApprovalActionRequest = {}
): Promise<AutonomousObjectiveDetail> {
  return jsonFetch<AutonomousObjectiveDetail>(
    `/api/autonomous-engineering/approval-gates/${encodeURIComponent(gateId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function getApprovalSettings(workspaceRoot?: string): Promise<ApprovalSettingsResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ApprovalSettingsResponse>(`/api/approval/settings?${query.toString()}`);
}

export function updateApprovalSettings(
  workspaceRoot: string | undefined,
  request: UpdateApprovalSettingsRequest
): Promise<ApprovalSettingsResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ApprovalSettingsResponse>(`/api/approval/settings?${query.toString()}`, {
    method: 'PUT',
    body: JSON.stringify(request)
  });
}

export function compareDiff(request: DiffCompareRequest): Promise<DiffCompareResponse> {
  return jsonFetch<DiffCompareResponse>('/api/diff/compare', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getValidationProfile(workspaceRoot?: string): Promise<ValidationProfileResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ValidationProfileResponse>(`/api/validation/profile?${query.toString()}`);
}

export function updateValidationProfile(
  workspaceRoot: string | undefined,
  request: ValidationProfileUpdateRequest
): Promise<ValidationProfileResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ValidationProfileResponse>(`/api/validation/profile?${query.toString()}`, {
    method: 'PUT',
    body: JSON.stringify(request)
  });
}

export function getWorkspaceProfile(workspaceRoot?: string): Promise<WorkspaceProfileResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<WorkspaceProfileResponse>(`/api/workspace/profile?${query.toString()}`);
}

export function getProjectIntelligence(workspaceRoot?: string): Promise<ProjectIntelligenceSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ProjectIntelligenceSnapshot>(`/api/project-intelligence?${query.toString()}`);
}

export function reindexProjectIntelligence(
  request: ProjectIntelligenceReindexRequest
): Promise<ProjectIntelligenceSnapshot> {
  return jsonFetch<ProjectIntelligenceSnapshot>('/api/project-intelligence/reindex', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function selectProjectContext(
  request: ProjectContextSelectionRequest
): Promise<ProjectContextSelectionResponse> {
  return jsonFetch<ProjectContextSelectionResponse>('/api/project-intelligence/context', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getWorkspaceIntelligence(workspaceRoot?: string): Promise<WorkspaceOperationsSnapshot> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<WorkspaceOperationsSnapshot>(`/api/workspace-intelligence?${query.toString()}`);
}

export function scanWorkspaceIntelligence(
  request: WorkspaceOperationsScanRequest
): Promise<WorkspaceOperationsSnapshot> {
  return jsonFetch<WorkspaceOperationsSnapshot>('/api/workspace-intelligence/scan', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function getWorkspaceIntelligenceEvents(workspaceRoot?: string, limit = 80): Promise<WorkspaceWatchEvent[]> {
  const query = new URLSearchParams({ limit: String(limit) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<WorkspaceWatchEvent[]>(`/api/workspace-intelligence/events?${query.toString()}`);
}

export function getWorkspaceRecommendations(
  workspaceRoot?: string,
  includeDismissed = false
): Promise<WorkspaceRecommendation[]> {
  const query = new URLSearchParams({ include_dismissed: String(includeDismissed) });

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<WorkspaceRecommendation[]>(`/api/workspace-intelligence/recommendations?${query.toString()}`);
}

export function dismissWorkspaceRecommendation(
  recommendationId: string,
  request: RecommendationActionRequest = {}
): Promise<RecommendationFixResponse> {
  return jsonFetch<RecommendationFixResponse>(
    `/api/workspace-intelligence/recommendations/${encodeURIComponent(recommendationId)}/dismiss`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function fixWorkspaceRecommendation(
  recommendationId: string,
  request: RecommendationFixRequest = {}
): Promise<RecommendationFixResponse> {
  return jsonFetch<RecommendationFixResponse>(
    `/api/workspace-intelligence/recommendations/${encodeURIComponent(recommendationId)}/fix`,
    {
      method: 'POST',
      body: JSON.stringify(request)
    }
  );
}

export function getWorkspaceIntelligenceJobs(workspaceRoot?: string): Promise<ScheduledIntelligenceJob[]> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<ScheduledIntelligenceJob[]>(`/api/workspace-intelligence/jobs?${query.toString()}`);
}

export function runWorkspaceIntelligenceJobs(request: ScheduledJobRunRequest): Promise<ScheduledJobRunResponse> {
  return jsonFetch<ScheduledJobRunResponse>('/api/workspace-intelligence/jobs/run', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function setupWorkspace(request: WorkspaceSetupRequest): Promise<WorkspaceSetupResponse> {
  return jsonFetch<WorkspaceSetupResponse>('/api/workspace/setup', {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function createMemoryNote(
  workspaceRoot: string | undefined,
  request: CreateMemoryNoteRequest
): Promise<MemoryNoteResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<MemoryNoteResponse>(`/api/memory?${query.toString()}`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function listMemoryNotes(workspaceRoot?: string, category?: string): Promise<MemoryNotesResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  if (category?.trim()) {
    query.set('category', category.trim());
  }

  return jsonFetch<MemoryNotesResponse>(`/api/memory?${query.toString()}`);
}

export function getMemoryGovernance(workspaceRoot?: string): Promise<MemoryGovernanceResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<MemoryGovernanceResponse>(`/api/memory/governance?${query.toString()}`);
}

export function exportMemoryNotes(
  workspaceRoot: string | undefined,
  request: MemoryExportRequest = {}
): Promise<MemoryExportResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<MemoryExportResponse>(`/api/memory/export?${query.toString()}`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function updateMemoryControls(
  workspaceRoot: string | undefined,
  request: MemoryControlsUpdateRequest
): Promise<MemoryControlsResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<MemoryControlsResponse>(`/api/memory/controls?${query.toString()}`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
}

export function updateMemoryNote(
  workspaceRoot: string | undefined,
  noteId: string,
  request: UpdateMemoryNoteRequest
): Promise<MemoryNoteResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<MemoryNoteResponse>(`/api/memory/${encodeURIComponent(noteId)}?${query.toString()}`, {
    method: 'PUT',
    body: JSON.stringify(request)
  });
}

export function deleteMemoryNote(
  workspaceRoot: string | undefined,
  noteId: string
): Promise<DeleteMemoryNoteResponse> {
  const query = new URLSearchParams();

  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }

  return jsonFetch<DeleteMemoryNoteResponse>(`/api/memory/${encodeURIComponent(noteId)}?${query.toString()}`, {
    method: 'DELETE'
  });
}

export function getReleaseManifest(workspaceRoot?: string): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<Record<string, unknown>>(`/api/release/manifest?${query.toString()}`);
}

export function getReleaseCompatibility(workspaceRoot?: string): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  if (workspaceRoot?.trim()) {
    query.set('workspace_root', workspaceRoot.trim());
  }
  return jsonFetch<Record<string, unknown>>(`/api/release/compatibility?${query.toString()}`);
}
