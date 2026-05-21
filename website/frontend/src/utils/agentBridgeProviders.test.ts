import { describe, expect, it } from 'vitest';
import type { ManagedModelInfo } from '../types';
import {
  bridgeModelForProvider,
  buildBridgeProviderSummary,
  isExternalBridgeProvider,
  isLocalBridgeProvider,
  providerIdForModelRuntime,
  runtimeTargetForBridgeProvider
} from './agentBridgeProviders';

function managedModel(overrides: Partial<ManagedModelInfo>): ManagedModelInfo {
  return {
    provider_id: overrides.provider_id ?? 'local',
    label: overrides.label ?? overrides.name ?? 'Local model',
    api: overrides.api ?? 'ollama',
    endpoint: overrides.endpoint ?? 'http://127.0.0.1:11434',
    name: overrides.name ?? 'llama3.1',
    local: overrides.local ?? true,
    enabled: overrides.enabled ?? true,
    installed: overrides.installed ?? false,
    configured: overrides.configured ?? false,
    active: overrides.active ?? false,
    pullable: overrides.pullable ?? false,
    health: overrides.health ?? 'unknown',
    roles: overrides.roles ?? [],
    capabilities: overrides.capabilities ?? [],
    size_bytes: overrides.size_bytes ?? null,
    modified_at: overrides.modified_at ?? '',
    estimated_pull_bytes: overrides.estimated_pull_bytes ?? null,
    notes: overrides.notes ?? ''
  };
}

describe('agent bridge provider helpers', () => {
  it('keeps external provider model selection scoped to matching model families', () => {
    expect(bridgeModelForProvider('openai', 'gpt-5.4')).toBe('gpt-5.4');
    expect(bridgeModelForProvider('openai', 'claude-sonnet-4')).toBe('');
    expect(bridgeModelForProvider('anthropic', 'claude-sonnet-4')).toBe('claude-sonnet-4');
    expect(bridgeModelForProvider('google_gemini', 'gemini-2.5-pro')).toBe('gemini-2.5-pro');
    expect(bridgeModelForProvider('ollama', 'qwen2.5-coder')).toBe('qwen2.5-coder');
  });

  it('classifies local and external bridge providers', () => {
    expect(isExternalBridgeProvider('openai')).toBe(true);
    expect(isExternalBridgeProvider('local_openai_compatible')).toBe(false);
    expect(isLocalBridgeProvider('ollama')).toBe(true);
    expect(isLocalBridgeProvider('anthropic')).toBe(false);
  });

  it('maps model runtime settings back to the provider dock selection', () => {
    expect(providerIdForModelRuntime('ollama')).toBe('ollama');
    expect(providerIdForModelRuntime('lmstudio')).toBe('local_openai_compatible');
    expect(providerIdForModelRuntime('custom', 'http://localhost:1234/v1')).toBe('local_openai_compatible');
    expect(providerIdForModelRuntime('custom', 'https://models.example.test')).toBe('local_openai_compatible');
  });

  it('picks the best local runtime target for provider selection', () => {
    const options = [
      managedModel({ api: 'ollama', name: 'llama3', installed: true }),
      managedModel({ api: 'ollama', name: 'qwen2.5-coder', active: true }),
      managedModel({ api: 'lmstudio', name: 'local-coder', configured: true, endpoint: 'http://localhost:1234/v1' })
    ];

    expect(runtimeTargetForBridgeProvider('ollama', options)?.name).toBe('qwen2.5-coder');
    expect(runtimeTargetForBridgeProvider('local_openai_compatible', options)?.name).toBe('local-coder');
    expect(runtimeTargetForBridgeProvider('openai', options)).toBeNull();
  });

  it('builds stable labels for the selected bridge runtime', () => {
    expect(
      buildBridgeProviderSummary({
        providerId: 'anthropic',
        modelApi: 'ollama',
        modelName: 'llama3'
      })
    ).toEqual({
      external: true,
      label: 'Claude',
      model: '',
      runtimeLabel: 'CLI bridge default'
    });

    expect(
      buildBridgeProviderSummary({
        providerId: 'ollama',
        modelApi: 'ollama',
        modelName: 'qwen2.5-coder'
      })
    ).toEqual({
      external: false,
      label: 'Ollama',
      model: 'qwen2.5-coder',
      runtimeLabel: 'ollama / qwen2.5-coder'
    });
  });
});
