import type { ManagedModelInfo } from '../types';

const EXTERNAL_BRIDGE_PROVIDER_IDS = new Set(['openai', 'anthropic', 'google_gemini']);
const LOCAL_BRIDGE_PROVIDER_IDS = new Set(['ollama', 'local_openai_compatible']);
const LOCAL_COMPATIBLE_MODEL_APIS = new Set(['lmstudio', 'openai-compatible', 'local_openai_compatible']);

export interface BridgeProviderSummary {
  external: boolean;
  label: string;
  model: string;
  runtimeLabel: string;
}

export function isExternalBridgeProvider(providerId: string): boolean {
  return EXTERNAL_BRIDGE_PROVIDER_IDS.has(providerId);
}

export function isLocalBridgeProvider(providerId: string): boolean {
  return LOCAL_BRIDGE_PROVIDER_IDS.has(providerId);
}

export function bridgeModelForProvider(providerId: string, activeModelName: string): string {
  const value = activeModelName.trim();
  if (!value) return '';
  const lower = value.toLowerCase();
  if (providerId === 'openai') {
    return /^(gpt-|o\d|o-|codex|chatgpt)/.test(lower) ? value : '';
  }
  if (providerId === 'anthropic') {
    return /(claude|sonnet|opus|haiku)/.test(lower) ? value : '';
  }
  if (providerId === 'google_gemini') {
    return lower.includes('gemini') ? value : '';
  }
  return value;
}

export function providerIdForModelRuntime(api: string, endpoint = ''): string {
  const normalizedApi = api.trim().toLowerCase();
  if (normalizedApi === 'ollama') return 'ollama';
  if (LOCAL_COMPATIBLE_MODEL_APIS.has(normalizedApi)) {
    return 'local_openai_compatible';
  }
  if (isLocalModelEndpoint(endpoint)) return 'local_openai_compatible';
  return 'local_openai_compatible';
}

export function isLocalModelEndpoint(endpoint: string): boolean {
  const value = endpoint.trim().toLowerCase();
  return Boolean(
    value &&
      (value.includes('localhost') ||
        value.includes('127.0.0.1') ||
        value.includes('::1') ||
        value.startsWith('http://0.0.0.0'))
  );
}

export function bridgeLabelForProvider(providerId: string): string {
  if (providerId === 'openai') return 'Codex';
  if (providerId === 'anthropic') return 'Claude';
  if (providerId === 'google_gemini') return 'Gemini';
  if (providerId === 'ollama') return 'Ollama';
  return 'Local';
}

export function buildBridgeProviderSummary({
  providerId,
  modelApi,
  modelName
}: {
  providerId: string;
  modelApi: string;
  modelName: string;
}): BridgeProviderSummary {
  const external = isExternalBridgeProvider(providerId);
  const model = bridgeModelForProvider(providerId, modelName);
  return {
    external,
    label: bridgeLabelForProvider(providerId),
    model,
    runtimeLabel: external ? (model ? `CLI bridge / ${model}` : 'CLI bridge default') : `${modelApi || 'local'} / ${modelName || 'Auto'}`
  };
}

export function runtimeTargetForBridgeProvider(
  providerId: string,
  selectableModelOptions: readonly ManagedModelInfo[]
): ManagedModelInfo | null {
  if (!isLocalBridgeProvider(providerId)) return null;

  const candidates = selectableModelOptions.filter((item) => modelMatchesBridgeProvider(providerId, item));
  return (
    candidates.find((item) => item.active) ||
    candidates.find((item) => item.installed) ||
    candidates.find((item) => item.configured) ||
    candidates[0] ||
    null
  );
}

function modelMatchesBridgeProvider(providerId: string, item: ManagedModelInfo): boolean {
  const api = item.api.trim().toLowerCase();
  if (providerId === 'ollama') return api === 'ollama';
  return api !== 'ollama' && (LOCAL_COMPATIBLE_MODEL_APIS.has(api) || isLocalModelEndpoint(item.endpoint));
}
