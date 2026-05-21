import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { getPalette } from '../../styles/appStyles';
import type { ProviderAccountStatus } from '../../types';
import { getProviderRouteReadinessCards, ProviderRouteReadiness } from './ProviderRouteReadiness';

describe('ProviderRouteReadiness', () => {
  it('summarizes a local provider as private local compute with fallback eligibility', () => {
    const provider = createProvider({
      manifest: {
        id: 'ollama',
        label: 'Ollama',
        kind: 'local',
        auth_modes: ['none'],
        default_auth_mode: 'none',
        quota_status: 'Local runtime; constrained by installed models.'
      },
      primary_auth_mode: 'none',
      execution_ready: true,
      fallback_eligible: true,
      quota_status: 'Local runtime; constrained by installed models.'
    });

    const cards = getProviderRouteReadinessCards(provider);

    expect(cards.map((card) => card.value)).toContain('Local runtime');
    expect(cards.map((card) => card.value)).toContain('Local compute');
    expect(cards.map((card) => card.value)).toContain('Eligible');
  });

  it('renders cloud route caveats without requiring credentials in the test', () => {
    const provider = createProvider({
      manifest: {
        id: 'openai',
        label: 'OpenAI',
        kind: 'cloud',
        auth_modes: ['api_key', 'cli_bridge'],
        default_auth_mode: 'api_key',
        quota_status: 'Provider limits depend on the linked account.'
      },
      primary_auth_mode: 'api_key',
      execution_ready: false,
      fallback_eligible: false,
      quota_status: 'Provider limits depend on the linked account.'
    });

    const html = renderToStaticMarkup(<ProviderRouteReadiness provider={provider} palette={getPalette(false)} />);

    expect(html).toContain('OpenAI route readiness');
    expect(html).toContain('Cloud route');
    expect(html).toContain('Needs account');
    expect(html).toContain('Network bound');
    expect(html).toContain('Not eligible');
  });

  it('prefers backend route safety boundaries and redacts secret-like card text', () => {
    const provider = createProvider({
      manifest: {
        id: 'openai',
        label: 'OpenAI',
        kind: 'cloud',
        auth_modes: ['api_key', 'cli_bridge'],
        default_auth_mode: 'api_key'
      },
      execution_ready: true,
      fallback_eligible: true,
      route_safety: {
        route_type: 'api_key',
        privacy_boundary: 'cloud',
        secret_policy: 'API key stays in the OS credential store.',
        secret_storage: 'os_credential_store',
        cloud_context_requires_consent: true,
        sends_workspace_context: true,
        cost_boundary: 'Usage and billing stay with the linked provider account.',
        quota_boundary: 'Provider quota api_key=sk-front-secret-value is redacted before display.',
        latency_boundary: 'Bound to provider endpoint, network, model load, and rate limits.',
        fallback_policy: 'Eligible for policy-approved fallback routing.',
        diagnostics_safe: true,
        user_action_required: ''
      }
    });

    const cards = getProviderRouteReadinessCards(provider);
    const html = renderToStaticMarkup(<ProviderRouteReadiness provider={provider} palette={getPalette(false)} />);

    expect(cards.map((card) => card.value)).toContain('Cloud route');
    expect(cards.map((card) => card.value)).toContain('Provider billed');
    expect(html).toContain('Prompts and selected context require route consent');
    expect(html).toContain('api_key=[redacted]');
    expect(html).not.toContain('sk-front-secret-value');
  });
});

type ProviderOverride = Partial<Omit<ProviderAccountStatus, 'manifest'>> & {
  manifest?: Partial<ProviderAccountStatus['manifest']>;
};

function createProvider(overrides: ProviderOverride): ProviderAccountStatus {
  const { manifest: manifestOverride, ...statusOverrides } = overrides;
  return {
    manifest: {
      id: 'provider',
      label: 'Provider',
      kind: 'cloud',
      description: '',
      auth_modes: ['api_key'],
      default_auth_mode: 'api_key',
      credential_env_vars: [],
      capabilities: [],
      model_families: [],
      quota_status: 'unknown',
      docs_url: '',
      security_notes: [],
      cli_bridge: null,
      metadata: {},
      ...(manifestOverride ?? {})
    },
    account: null,
    cli_bridge: null,
    connection_status: 'not_configured',
    primary_auth_mode: 'api_key',
    fallback_eligible: false,
    setup_actions: [],
    execution_ready: false,
    readiness: 'setup_required',
    readiness_label: 'Setup Required',
    readiness_detail: '',
    routing_weight: 0,
    quota_status: 'unknown',
    model_limit_summary: 'Provider limits are unknown until telemetry is available.',
    ...statusOverrides
  };
}
