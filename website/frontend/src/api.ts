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
  MemoryNoteResponse,
  ModelOperationInfo,
  ModelPullRequest,
  ModelRegistryResponse,
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
  RuntimeObservabilitySnapshot,
  RuntimeRecoverySnapshot,
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
const IS_TEST_MODE = import.meta.env.MODE === 'test';

let resolvedApiBase = EXPLICIT_API_BASE;
let apiBaseDiscovered = Boolean(EXPLICIT_API_BASE);
let apiDiscoveryEnabledForTests = false;

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

async function discoverApiBase(): Promise<void> {
  if (!shouldDiscoverApiBase()) return;

  let firstHealthyBase: string | null = null;

  for (const base of DEFAULT_API_BASES) {
    try {
      const response = await fetch(apiUrl(base, '/api/health'), {
        headers: { Accept: 'application/json' }
      });

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
}

export function __setApiDiscoveryForTests(enabled: boolean): void {
  apiDiscoveryEnabledForTests = enabled;
}

export function getResolvedApiBase(): string {
  return resolvedApiBase;
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

export function getModels(): Promise<ModelInventoryResponse> {
  return jsonFetch<ModelInventoryResponse>('/api/models');
}

export function getModelRegistry(): Promise<ModelRegistryResponse> {
  return jsonFetch<ModelRegistryResponse>('/api/model-registry');
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

export function getChatStreamContract(): Promise<ChatStreamContractResponse> {
  return jsonFetch<ChatStreamContractResponse>('/api/chat/stream/contract');
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
