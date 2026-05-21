import type { CSSProperties, ReactNode } from 'react';
import { Cloud, Gauge, RotateCcw, ShieldCheck, Timer, Wallet } from 'lucide-react';
import type { Palette } from '../../styles/appStyles';
import type { ProviderAccountStatus, ProviderRouteSafety } from '../../types';

type RouteTone = 'ok' | 'warning' | 'muted';

export type ProviderRouteReadinessCard = {
  id: 'privacy' | 'cost' | 'quota' | 'latency' | 'fallback';
  label: string;
  value: string;
  detail: string;
  tone: RouteTone;
};

interface ProviderRouteReadinessProps {
  provider: ProviderAccountStatus;
  palette: Palette;
}

export function ProviderRouteReadiness({ provider, palette }: ProviderRouteReadinessProps) {
  const cards = getProviderRouteReadinessCards(provider);
  const icons: Record<ProviderRouteReadinessCard['id'], ReactNode> = {
    privacy: <ShieldCheck size={14} />,
    cost: <Wallet size={14} />,
    quota: <Gauge size={14} />,
    latency: <Timer size={14} />,
    fallback: <RotateCcw size={14} />
  };

  return (
    <div style={styles.grid} aria-label={`${provider.manifest.label} route readiness`}>
      {cards.map((card) => (
        <div key={`${provider.manifest.id}-${card.id}`} style={styles.card(palette, card.tone)}>
          <div style={styles.cardTop(palette, card.tone)}>
            {icons[card.id] ?? <Cloud size={14} />}
            <span>{card.label}</span>
          </div>
          <strong style={styles.value(palette)}>{card.value}</strong>
          <span style={styles.detail(palette)}>{card.detail}</span>
        </div>
      ))}
    </div>
  );
}

export function getProviderRouteReadinessCards(provider: ProviderAccountStatus): ProviderRouteReadinessCard[] {
  const manifest = provider.manifest;
  const kind = String(manifest.kind || 'unknown').toLowerCase();
  const authMode = String(provider.account?.auth_mode || provider.primary_auth_mode || manifest.default_auth_mode || 'unknown');
  const quota = provider.quota_status || provider.model_limit_summary || manifest.quota_status || 'Unknown until provider telemetry is available.';
  const linked = Boolean(provider.account) || provider.execution_ready;
  const cliDelegation = authMode === 'cli_bridge' || Boolean(provider.cli_bridge?.binary_path);
  const safety = provider.route_safety;

  return [
    {
      id: 'privacy',
      label: 'Privacy',
      value: safety ? privacyBoundaryLabel(safety.privacy_boundary, kind) : kind === 'local' ? 'Local runtime' : kind === 'enterprise' ? 'Enterprise cloud' : 'Cloud route',
      detail: safeRouteText(
        safety
          ? privacyBoundaryDetail(safety, kind)
          : kind === 'local'
            ? 'Prompts stay on the configured local endpoint unless that endpoint is remote.'
            : 'Prompts and selected context may leave the machine when this route is selected.'
      ),
      tone: safety ? privacyBoundaryTone(safety.privacy_boundary, kind) : kind === 'local' ? 'ok' : 'warning'
    },
    {
      id: 'cost',
      label: 'Cost',
      value: safety ? costBoundaryLabel(safety, kind, linked) : kind === 'local' ? 'Local compute' : linked ? 'Provider billed' : 'Needs account',
      detail: safeRouteText(
        safety?.cost_boundary ||
          (kind === 'local'
            ? 'No provider API billing is expected for local model calls.'
            : 'Usage, subscription, and billing limits stay with the linked provider account.')
      ),
      tone: kind === 'local' ? 'ok' : linked ? 'warning' : 'muted'
    },
    {
      id: 'quota',
      label: 'Quota',
      value: localQuotaLabel(kind, provider),
      detail: safeRouteText(safety?.quota_boundary || quota),
      tone: provider.connection_status === 'limited' ? 'warning' : kind === 'local' || linked ? 'ok' : 'muted'
    },
    {
      id: 'latency',
      label: 'Latency',
      value: safety ? latencyBoundaryLabel(safety, kind, cliDelegation) : kind === 'local' ? 'Endpoint bound' : cliDelegation ? 'CLI bound' : 'Network bound',
      detail: safeRouteText(
        safety?.latency_boundary ||
          (cliDelegation
            ? 'Runs through the provider CLI, so startup and auth checks can affect response time.'
            : kind === 'local'
              ? 'Depends on local model size, hardware, and endpoint health.'
              : 'Depends on provider region, network, model load, and rate limits.')
      ),
      tone: 'muted'
    },
    {
      id: 'fallback',
      label: 'Fallback',
      value: provider.fallback_eligible ? 'Eligible' : 'Not eligible',
      detail: safeRouteText(
        safety?.fallback_policy ||
          (provider.fallback_eligible
            ? 'Aegis may use this route as a backup when policy allows it.'
            : 'This route will not be used as an automatic backup yet.')
      ),
      tone: provider.fallback_eligible ? 'ok' : 'muted'
    }
  ];
}

function localQuotaLabel(kind: string, provider: ProviderAccountStatus): string {
  if (kind === 'local') return 'Local limits';
  if (provider.connection_status === 'limited') return 'Limited';
  if (provider.execution_ready || provider.account) return 'Tracked by provider';
  return 'Unknown';
}

function privacyBoundaryLabel(boundary: string, kind: string): string {
  if (boundary === 'local' || kind === 'local') return 'Local runtime';
  if (boundary === 'enterprise_cloud') return 'Enterprise cloud';
  if (boundary === 'provider_cli') return 'Provider CLI';
  if (boundary === 'cloud') return 'Cloud route';
  return 'Unknown';
}

function privacyBoundaryDetail(safety: ProviderRouteSafety, kind: string): string {
  if (safety.privacy_boundary === 'local' || kind === 'local') {
    return safety.secret_policy || 'Prompts stay on the configured local endpoint unless that endpoint is remote.';
  }
  if (safety.cloud_context_requires_consent) {
    return 'Prompts and selected context require route consent before leaving the machine.';
  }
  return safety.secret_policy || 'Prompts and selected context may leave the machine when this route is selected.';
}

function privacyBoundaryTone(boundary: string, kind: string): RouteTone {
  if (boundary === 'local' || kind === 'local') return 'ok';
  if (boundary === 'unknown') return 'muted';
  return 'warning';
}

function costBoundaryLabel(safety: ProviderRouteSafety, kind: string, linked: boolean): string {
  if (kind === 'local' || safety.route_type === 'local_endpoint') return 'Local compute';
  if (!linked && safety.user_action_required) return 'Needs account';
  if (safety.route_type === 'unsupported') return 'Unknown';
  return 'Provider billed';
}

function latencyBoundaryLabel(safety: ProviderRouteSafety, kind: string, cliDelegation: boolean): string {
  if (kind === 'local' || safety.route_type === 'local_endpoint') return 'Endpoint bound';
  if (cliDelegation || safety.route_type === 'cli_bridge') return 'CLI bound';
  if (safety.route_type === 'unsupported') return 'Unknown';
  return 'Network bound';
}

function safeRouteText(value: string): string {
  return String(value || '')
    .replace(/\b(api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|client[_-]?secret|secret|password|credential)(\s*[:=]\s*)[^\s&]+/gi, '$1$2[redacted]')
    .replace(/\b(Bearer\s+)[A-Za-z0-9._~+/\-=]+/gi, '$1[redacted]');
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))',
    gap: 7,
    minWidth: 0
  } as CSSProperties,
  card: (palette: Palette, tone: RouteTone): CSSProperties => {
    const color = toneColor(palette, tone);
    return {
      display: 'grid',
      gap: 4,
      minWidth: 0,
      borderRadius: 8,
      border: `1px solid ${color}33`,
      background: `${color}0f`,
      padding: 8
    };
  },
  cardTop: (palette: Palette, tone: RouteTone): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    color: toneColor(palette, tone),
    fontSize: 10,
    fontWeight: 950,
    textTransform: 'uppercase',
    lineHeight: 1.2,
    minWidth: 0
  }),
  value: (palette: Palette): CSSProperties => ({
    color: palette.text,
    fontSize: 12,
    lineHeight: 1.2,
    overflowWrap: 'anywhere'
  }),
  detail: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 10,
    lineHeight: 1.3,
    overflowWrap: 'anywhere'
  })
};

function toneColor(palette: Palette, tone: RouteTone): string {
  if (tone === 'ok') return palette.good;
  if (tone === 'warning') return palette.warning;
  return palette.muted;
}
