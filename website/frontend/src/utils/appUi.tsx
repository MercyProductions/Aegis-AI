import { Play, Wrench, Zap } from 'lucide-react';
import type {
  AgentResponse,
  ManagedModelInfo,
  ModelInfo,
  ValidationRecipe,
  WorkspaceProfileResponse
} from '../types';
import { isGeneratedChangeApplied } from './generatedChanges';
import type { RuntimeDiagnosticActionKind } from './runtimeDiagnostics';

export function buildAssistantSummary(response: AgentResponse): string {
  const parts: string[] = [];

  if (response.reply.trim()) {
    parts.push(response.reply.trim());
  }

  if (response.changes.length) {
    const pendingCount = response.changes.filter((change) => !isGeneratedChangeApplied(change, response.applied)).length;
    const generatedLabel = pendingCount
      ? 'Pending generated file changes (not written yet):'
      : 'Generated file changes:';
    parts.push(
      [
        generatedLabel,
        ...response.changes.map((change) => {
          const state = isGeneratedChangeApplied(change, response.applied) ? 'applied' : 'pending';
          return `- ${change.path} (${change.action}, ${state})`;
        })
      ].join('\n')
    );
  }

  if (response.applied.length) {
    parts.push(['Applied changes:', ...response.applied.map((item) => `- ${item}`)].join('\n'));
  }

  if (response.validation) {
    const validationOutput = [response.validation.stdout, response.validation.stderr]
      .map((item) => item.trim())
      .filter(Boolean)
      .join('\n');
    const validationLines = [
      `Validation: ${response.validation.exit_code === 0 ? 'passed' : 'needs attention'}`,
      response.validation.summary,
      response.validation.command ? `Command: ${response.validation.command}` : '',
      validationOutput ? ['Output:', '```shell', validationOutput, '```'].join('\n') : ''
    ].filter(Boolean);
    parts.push(validationLines.join('\n'));
  }

  if (response.task_plan) {
    parts.push(
      [
        'Planning intelligence:',
        `- route: ${routeProfileLabel(response.task_plan)}`,
        `- scale: ${response.task_plan.complexity}`,
        `- estimated slices: ${response.task_plan.estimated_slices}`,
        `- pass budget hint: ${response.task_plan.pass_budget_hint}`
      ].join('\n')
    );
  }

  if (response.completion_quality) {
    const qualityLines = [
      `Completion quality: ${response.completion_quality.status} (${Math.round(response.completion_quality.score * 100)}%)`,
      ...response.completion_quality.reasons.slice(0, 3).map((reason) => `- ${reason}`)
    ];
    parts.push(qualityLines.join('\n'));
  }

  return parts.join('\n\n');
}

export function routeProfileLabel(plan: { route_profile?: Record<string, unknown> } | null | undefined): string {
  const profile = plan?.route_profile ?? {};
  const label = profile.label;
  const id = profile.id;
  if (typeof label === 'string' && label.trim()) return label;
  if (typeof id === 'string' && id.trim()) return id;
  return 'auto';
}

export function formatEventTime(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatDateTime(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export function modelOptionKey(item: Pick<ManagedModelInfo, 'api' | 'endpoint' | 'name'>): string {
  return `${item.api || 'ollama'}::${item.endpoint || ''}::${item.name || ''}`;
}

export function managedModelFromConfig(
  api: string,
  endpoint: string,
  name: string,
  ready: boolean,
  message: string
): ManagedModelInfo {
  const nextApi = api.trim() || 'ollama';
  const nextEndpoint = endpoint.trim() || (nextApi === 'ollama' ? 'http://127.0.0.1:11434' : '');
  const nextName = name.trim() || 'qwen2.5-coder:7b';

  return {
    provider_id: `active-${nextApi}-${nextName}`,
    label: 'Active configuration',
    api: nextApi,
    endpoint: nextEndpoint,
    name: nextName,
    local: ['ollama', 'lmstudio'].includes(nextApi),
    enabled: true,
    installed: ready,
    configured: true,
    active: true,
    pullable: false,
    health: ready ? 'available' : message || 'configured',
    roles: [],
    capabilities: [],
    size_bytes: null,
    modified_at: '',
    estimated_pull_bytes: null,
    notes: message || 'Current configured model target'
  };
}

export function findManagedModelByName(models: ManagedModelInfo[], modelName: string): ManagedModelInfo | null {
  const normalized = modelName.trim().toLowerCase();
  if (!normalized) return null;
  return (
    models.find((item) => item.name.toLowerCase() === normalized) ||
    models.find((item) => `${item.name}:latest`.toLowerCase() === normalized) ||
    models.find((item) => item.name.replace(/:latest$/i, '').toLowerCase() === normalized.replace(/:latest$/i, '')) ||
    null
  );
}

export function modelInventoryToManagedModels(models: ModelInfo[]): ManagedModelInfo[] {
  return models.map((item) => ({
    provider_id: item.id,
    label: item.provider,
    api: item.api,
    endpoint: item.endpoint,
    name: item.name,
    local: item.local,
    enabled: true,
    installed: item.available,
    configured: item.configured,
    active: item.configured,
    pullable: false,
    health: item.ready ? 'available' : item.message || 'unavailable',
    roles: capabilityNames(item.capabilities),
    capabilities: capabilityNames(item.capabilities),
    size_bytes: item.size,
    modified_at: item.modified_at,
    estimated_pull_bytes: null,
    notes: item.message
  }));
}

export function capabilityNames(capabilities: ModelInfo['capabilities']): string[] {
  return Object.entries(capabilities)
    .filter(([, enabled]) => Boolean(enabled))
    .map(([name]) => name);
}

export function mergeById<T extends { id: string }>(priority: T[], fallback: T[]): T[] {
  const merged = new Map<string, T>();

  for (const item of priority) {
    merged.set(item.id, item);
  }

  for (const item of fallback) {
    if (!merged.has(item.id)) {
      merged.set(item.id, item);
    }
  }

  return Array.from(merged.values());
}

export function taskStatusToEventStatus(status: string): 'ok' | 'warning' | 'error' {
  const normalized = status.toLowerCase();
  if (
    normalized.includes('error') ||
    normalized.includes('failure') ||
    normalized === 'failed' ||
    normalized === 'canceled'
  ) {
    return 'error';
  }
  if (
    normalized.includes('running') ||
    normalized.includes('warning') ||
    normalized === 'queued' ||
    normalized === 'planning' ||
    normalized === 'validating' ||
    normalized === 'repairing' ||
    normalized === 'blocked' ||
    normalized === 'needs_approval'
  ) {
    return 'warning';
  }
  return 'ok';
}

export function readinessStatusToEventStatus(status: string): 'ok' | 'warning' | 'error' {
  if (status === 'ready') return 'ok';
  if (status === 'needs_repair') return 'error';
  return 'warning';
}

export function diagnosticStatusToEventStatus(status: 'ok' | 'warning' | 'error'): 'ok' | 'warning' | 'error' {
  return status;
}

export function runtimeDiagnosticActionIcon(kind: RuntimeDiagnosticActionKind) {
  if (kind === 'setup_workspace') return <Wrench size={14} />;
  if (kind === 'run_validation') return <Play size={14} />;
  return <Zap size={14} />;
}

export function formatStatusLabel(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function shouldOfferWorkspaceSetup(
  profile: WorkspaceProfileResponse | null,
  recipe: ValidationRecipe | null
): boolean {
  if (!profile) return false;
  if (!profile.has_manifest) return true;
  return !recipe?.command && profile.dependency_profile.validation_commands.length === 0;
}

export function shouldOfferReadinessValidation(
  profile: WorkspaceProfileResponse | null,
  recipe: ValidationRecipe | null
): boolean {
  if (!profile) return false;
  if (!['needs_validation', 'needs_repair'].includes(profile.readiness.status)) return false;
  return Boolean(recipe?.command || profile.dependency_profile.validation_commands.length);
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const candidate = error as { name?: unknown; message?: unknown };
  return candidate.name === 'AbortError' || candidate.message === 'Chat request stopped.';
}
