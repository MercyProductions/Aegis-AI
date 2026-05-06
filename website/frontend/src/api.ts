// frontend/src/api.ts
import type {
  AgentRequest,
  AgentResponse,
  ApprovalSettingsResponse,
  AppConfig,
  ApplyRequest,
  ApplyResponse,
  CheckpointListResponse,
  ChatStreamContractResponse,
  ChatStreamPayload,
  ConfigUpdateRequest,
  CreateMemoryNoteRequest,
  DiffCompareRequest,
  DiffCompareResponse,
  FileContentResponse,
  FilesResponse,
  FallbackInspectorResponse,
  FeedbackTelemetryResponse,
  HealthResponse,
  HistoryResponse,
  ModelDeleteRequest,
  ModelInventoryResponse,
  ModelManagerResponse,
  MemoryNoteResponse,
  ModelOperationInfo,
  ModelPullRequest,
  ModelRegistryResponse,
  RestoreCheckpointRequest,
  RestoreCheckpointResponse,
  RouteQualityResponse,
  RoutePolicyDiffOptions,
  RoutePolicyDiffResponse,
  TelemetrySnapshotOptions,
  TelemetrySnapshotResponse,
  UpdateApprovalSettingsRequest,
  ValidationProfileResponse,
  ValidationProfileUpdateRequest,
  ValidateRequest,
  ValidateResponse,
  WorkspaceProfileResponse,
  WorkspaceSetupRequest,
  WorkspaceSetupResponse
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8787').replace(/\/+$/, '');

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
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
      throw new Error(payload.message || payload.detail || 'Aegis streaming request failed');
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
  throw new Error('Aegis stream ended before a final response was received');
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
