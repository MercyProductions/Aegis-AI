import type { CSSProperties } from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cloud,
  Cpu,
  KeyRound,
  Loader2,
  RefreshCw,
  Settings,
  Terminal,
  Zap
} from 'lucide-react';
import { getProviderAccounts, probeProviderCliBridges } from '../../api';
import type { Palette } from '../../styles/appStyles';
import { isDarkPalette } from '../../styles/appStyles';
import type { ProviderAccountsResponse, ProviderAccountStatus } from '../../types';

interface AgentProviderDockProps {
  palette: Palette;
  variant?: 'compact' | 'panel';
  autoProbe?: boolean;
  selectedProviderId?: string;
  onSelectProvider?: (providerId: string) => void;
  onOpenAccounts?: () => void;
}

const PROVIDER_ORDER = ['openai', 'anthropic', 'google_gemini', 'ollama', 'local_openai_compatible'];
type ProviderAvailability = 'linked' | 'detected' | 'local' | 'limited' | 'setup' | 'error';

export function AgentProviderDock({
  palette,
  variant = 'panel',
  autoProbe = false,
  selectedProviderId = '',
  onSelectProvider,
  onOpenAccounts
}: AgentProviderDockProps) {
  const [snapshot, setSnapshot] = useState<ProviderAccountsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void (autoProbe ? probe() : refresh());
  }, [autoProbe]);

  const providers = useMemo(() => {
    const items = snapshot?.providers ?? [];
    return [...items].sort((left, right) => {
      const leftIndex = PROVIDER_ORDER.indexOf(left.manifest.id);
      const rightIndex = PROVIDER_ORDER.indexOf(right.manifest.id);
      const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
      const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
      return normalizedLeft - normalizedRight || left.manifest.label.localeCompare(right.manifest.label);
    });
  }, [snapshot]);

  const primaryProviders = providers.filter((provider) => PROVIDER_ORDER.includes(provider.manifest.id));
  const visibleProviders = primaryProviders.length ? primaryProviders : providers.slice(0, 5);
  const selectedProvider = providers.find((provider) => provider.manifest.id === selectedProviderId) ?? null;
  const linkedCount = providers.filter((provider) => provider.execution_ready).length;

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      setSnapshot(await getProviderAccounts());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider stack could not load.');
    } finally {
      setLoading(false);
    }
  }

  async function probe() {
    setProbing(true);
    setError('');
    try {
      setSnapshot(await probeProviderCliBridges());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider bridge probe failed.');
    } finally {
      setProbing(false);
    }
  }

  if (variant === 'compact') {
    return (
      <section style={styles.compactShell(palette)} aria-label="Agent provider stack">
        <div style={styles.compactTop}>
          <div style={styles.compactTitle(palette)}>
            <Zap size={14} />
            <span>Agent stack</span>
            <small>{loading ? 'loading' : `${linkedCount}/${providers.length || 0}`}</small>
          </div>
          <div style={styles.actionRow}>
            <button type="button" style={styles.smallIconButton(palette)} onClick={() => void probe()} disabled={probing}>
              {probing ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
              Probe
            </button>
            {onOpenAccounts ? (
              <button type="button" style={styles.iconOnlyButton(palette)} onClick={onOpenAccounts} title="Provider accounts" aria-label="Provider accounts">
                <Settings size={14} />
              </button>
            ) : null}
          </div>
        </div>

        <div style={styles.compactGrid}>
          {visibleProviders.map((provider) => (
            <ProviderChip
              key={provider.manifest.id}
              provider={provider}
              palette={palette}
              selected={selectedProviderId === provider.manifest.id}
              onSelect={onSelectProvider}
            />
          ))}
          {!visibleProviders.length ? <span style={styles.mutedText(palette)}>No providers loaded</span> : null}
        </div>
        {selectedProvider ? <SelectedProviderReadiness provider={selectedProvider} palette={palette} /> : null}
        {error ? <div style={styles.error(palette)}>{error}</div> : null}
      </section>
    );
  }

  return (
    <section style={styles.panelShell} aria-label="Agent provider stack">
      <div style={styles.panelTop}>
        <div>
          <h4 style={styles.panelHeading(palette)}>Agent Stack</h4>
          <div style={styles.panelMeta(palette)}>{loading ? 'Loading providers' : `${linkedCount} ready route(s)`}</div>
        </div>
        <div style={styles.actionRow}>
          <button type="button" style={styles.smallIconButton(palette)} onClick={() => void probe()} disabled={probing}>
            {probing ? <Loader2 size={13} className="spin" /> : <Terminal size={13} />}
            Probe
          </button>
          {onOpenAccounts ? (
            <button type="button" style={styles.smallIconButton(palette)} onClick={onOpenAccounts}>
              <KeyRound size={13} />
              Accounts
            </button>
          ) : null}
        </div>
      </div>

      <div style={styles.panelChipGrid}>
        {visibleProviders.map((provider) => (
          <ProviderChip
            key={provider.manifest.id}
            provider={provider}
            palette={palette}
            selected={selectedProviderId === provider.manifest.id}
            onSelect={onSelectProvider}
          />
        ))}
        {!visibleProviders.length ? <div style={styles.empty(palette)}>Provider stack is empty.</div> : null}
      </div>
      {selectedProvider ? <SelectedProviderReadiness provider={selectedProvider} palette={palette} /> : null}
      {error ? <div style={styles.error(palette)}>{error}</div> : null}
    </section>
  );
}

function SelectedProviderReadiness({ provider, palette }: { provider: ProviderAccountStatus; palette: Palette }) {
  const availability = providerAvailability(provider);
  const Icon = provider.execution_ready ? CheckCircle2 : provider.connection_status === 'error' ? AlertTriangle : Settings;
  return (
    <div style={styles.selectedReadiness(palette, availability)} title={providerTitle(provider)}>
      <Icon size={14} />
      <span>{provider.readiness_label || availabilityLabel(availability)}</span>
      <small>{provider.readiness_detail || provider.model_limit_summary}</small>
    </div>
  );
}

function ProviderChip({
  provider,
  palette,
  selected = false,
  onSelect
}: {
  provider: ProviderAccountStatus;
  palette: Palette;
  selected?: boolean;
  onSelect?: (providerId: string) => void;
}) {
  const availability = providerAvailability(provider);
  const Icon = providerIcon(provider);
  return (
    <button
      type="button"
      style={styles.chip(palette, availability, selected)}
      title={providerTitle(provider)}
      onClick={() => onSelect?.(provider.manifest.id)}
      aria-pressed={selected}
    >
      <Icon size={14} />
      <span>{shortProviderLabel(provider)}</span>
      <span style={styles.dot(palette, availability)} />
    </button>
  );
}

function ProviderRow({ provider, palette }: { provider: ProviderAccountStatus; palette: Palette }) {
  const availability = providerAvailability(provider);
  const Icon = providerIcon(provider);
  const bridgeLabel = bridgeOriginLabel(provider);
  const version = provider.cli_bridge?.version || '';
  const modelFamilies = provider.manifest.model_families.slice(0, 3);

  return (
    <div style={styles.row(palette, availability)}>
      <div style={styles.rowIcon(palette, availability)}>
        <Icon size={15} />
      </div>
      <div style={styles.rowMain}>
        <div style={styles.rowTitle(palette)}>
          <span>{shortProviderLabel(provider)}</span>
          <span style={styles.statusLabel(palette, availability)}>{availabilityLabel(availability)}</span>
        </div>
        <div style={styles.rowMeta(palette)}>
          {bridgeLabel}
          {version ? ` / ${version}` : ''}
        </div>
        <div style={styles.tagRow}>
          {modelFamilies.map((family) => (
            <span key={`${provider.manifest.id}-${family}`} style={styles.tag(palette)}>
              {family}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function providerAvailability(provider: ProviderAccountStatus): ProviderAvailability {
  if (provider.execution_ready) {
    if (provider.manifest.kind === 'local') return 'local';
    return provider.readiness === 'runtime_verified' ? 'limited' : 'linked';
  }
  if (provider.manifest.kind === 'local') {
    if (provider.connection_status === 'linked' || provider.account?.metadata?.active === true) return 'local';
    if (provider.account) return 'detected';
    return 'setup';
  }
  if (provider.connection_status === 'linked') return 'linked';
  if (provider.connection_status === 'error' && !provider.cli_bridge?.binary_path) return 'error';
  if (provider.cli_bridge?.binary_path) return provider.cli_bridge.status === 'error' ? 'detected' : 'linked';
  if (provider.account) return 'linked';
  return 'setup';
}

function providerIcon(provider: ProviderAccountStatus) {
  if (provider.manifest.kind === 'local') return Cpu;
  if (provider.cli_bridge?.binary_path) return Terminal;
  if (provider.manifest.auth_modes.includes('api_key')) return KeyRound;
  if (provider.connection_status === 'error') return AlertTriangle;
  return provider.manifest.kind === 'cloud' ? Cloud : Bot;
}

function shortProviderLabel(provider: ProviderAccountStatus): string {
  if (provider.manifest.id === 'openai') return 'Codex';
  if (provider.manifest.id === 'anthropic') return 'Claude';
  if (provider.manifest.id === 'google_gemini') return 'Gemini';
  if (provider.manifest.id === 'local_openai_compatible') return 'Local';
  return provider.manifest.label;
}

function bridgeOriginLabel(provider: ProviderAccountStatus): string {
  if (provider.manifest.kind === 'local') {
    const accountLabel = provider.account?.account_label?.trim();
    if (accountLabel) return accountLabel;
    const modelName = String(provider.account?.metadata?.model_name || '').trim();
    const endpoint = String(provider.account?.metadata?.model_endpoint || '').trim();
    if (modelName && endpoint) return `${modelName} / ${endpoint}`;
    return modelName || provider.manifest.label;
  }
  const detectedFrom = String(provider.cli_bridge?.metadata?.detected_from || '');
  if (detectedFrom === 'source_drop') return 'Source drop';
  if (provider.cli_bridge?.binary_path) return 'Official CLI';
  if (provider.account) return provider.account.auth_mode.replace('_', ' ');
  return provider.primary_auth_mode.replace('_', ' ');
}

function providerTitle(provider: ProviderAccountStatus): string {
  const origin = bridgeOriginLabel(provider);
  const version = provider.cli_bridge?.version ? ` ${provider.cli_bridge.version}` : '';
  return `${provider.manifest.label} / ${origin}${version}`;
}

function availabilityLabel(value: ProviderAvailability): string {
  if (value === 'linked') return 'linked';
  if (value === 'detected') return 'detected';
  if (value === 'local') return 'local';
  if (value === 'limited') return 'runtime';
  if (value === 'error') return 'error';
  return 'setup';
}

function availabilityColor(palette: Palette, value: ProviderAvailability): string {
  if (value === 'linked' || value === 'local') return palette.good;
  if (value === 'detected' || value === 'limited') return palette.warning;
  if (value === 'error') return palette.bad;
  return palette.muted;
}

const styles = {
  compactShell: (palette: Palette): CSSProperties => ({
    width: 'min(100%, 920px)',
    display: 'grid',
    gap: 10,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: isDarkPalette(palette) ? 'rgba(18,18,18,0.68)' : palette.cardAlt,
    padding: 10,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),
  compactTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    flexWrap: 'wrap'
  } as CSSProperties,
  compactTitle: (palette: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: palette.textSoft,
    fontSize: 12,
    fontWeight: 850
  }),
  compactGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(112px, 1fr))',
    gap: 8
  } as CSSProperties,
  chip: (palette: Palette, availability: ProviderAvailability, selected = false): CSSProperties => ({
    minHeight: 34,
    borderRadius: 8,
    border: `1px solid ${selected ? availabilityColor(palette, availability) : palette.inputBorder}`,
    background: isDarkPalette(palette) ? 'rgba(31,31,31,0.86)' : palette.input,
    color: palette.text,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    padding: '0 10px',
    fontSize: 12,
    fontWeight: 850,
    cursor: 'pointer',
    boxShadow: selected
      ? `0 0 0 1px ${availabilityColor(palette, availability)}44, inset 0 0 0 1px ${availabilityColor(palette, availability)}22`
      : `inset 0 0 0 1px ${availabilityColor(palette, availability)}12`
  }),
  dot: (palette: Palette, availability: ProviderAvailability): CSSProperties => ({
    width: 7,
    height: 7,
    borderRadius: 999,
    background: availabilityColor(palette, availability),
    boxShadow: `0 0 14px ${availabilityColor(palette, availability)}88`,
    flexShrink: 0
  }),
  panelShell: {
    display: 'grid',
    gap: 12
  } as CSSProperties,
  panelTop: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10,
    flexWrap: 'wrap'
  } as CSSProperties,
  panelHeading: (palette: Palette): CSSProperties => ({
    margin: 0,
    color: palette.text,
    fontSize: 15,
    fontWeight: 900
  }),
  panelMeta: (palette: Palette): CSSProperties => ({
    marginTop: 3,
    color: palette.muted,
    fontSize: 12
  }),
  actionRow: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    flexWrap: 'wrap'
  } as CSSProperties,
  smallIconButton: (palette: Palette): CSSProperties => ({
    minHeight: 30,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '0 9px',
    fontSize: 12,
    fontWeight: 850,
    cursor: 'pointer'
  }),
  iconOnlyButton: (palette: Palette): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),
  panelRows: {
    display: 'grid',
    gap: 8
  } as CSSProperties,
  panelChipGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(92px, 1fr))',
    gap: 8
  } as CSSProperties,
  selectedReadiness: (palette: Palette, availability: ProviderAvailability): CSSProperties => ({
    minHeight: 30,
    borderRadius: 8,
    border: `1px solid ${availabilityColor(palette, availability)}33`,
    background: `${availabilityColor(palette, availability)}12`,
    color: palette.textSoft,
    display: 'grid',
    gridTemplateColumns: '16px auto minmax(0, 1fr)',
    alignItems: 'center',
    gap: 8,
    padding: '6px 9px',
    fontSize: 11,
    lineHeight: 1.35
  }),
  row: (palette: Palette, availability: ProviderAvailability): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '34px minmax(0, 1fr)',
    gap: 10,
    alignItems: 'start',
    minHeight: 74,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: isDarkPalette(palette) ? 'rgba(18,18,18,0.62)' : palette.cardAlt,
    padding: 10,
    boxShadow: `inset 2px 0 0 ${availabilityColor(palette, availability)}`
  }),
  rowIcon: (palette: Palette, availability: ProviderAvailability): CSSProperties => ({
    width: 34,
    height: 34,
    borderRadius: 8,
    display: 'grid',
    placeItems: 'center',
    color: availabilityColor(palette, availability),
    background: `${availabilityColor(palette, availability)}18`,
    border: `1px solid ${availabilityColor(palette, availability)}28`
  }),
  rowMain: {
    display: 'grid',
    gap: 5,
    minWidth: 0
  } as CSSProperties,
  rowTitle: (palette: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    color: palette.text,
    fontSize: 13,
    fontWeight: 900
  }),
  rowMeta: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 12,
    lineHeight: 1.4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }),
  statusLabel: (palette: Palette, availability: ProviderAvailability): CSSProperties => ({
    color: availabilityColor(palette, availability),
    fontSize: 11,
    fontWeight: 900,
    textTransform: 'uppercase'
  }),
  tagRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 5
  } as CSSProperties,
  tag: (palette: Palette): CSSProperties => ({
    minHeight: 20,
    borderRadius: 999,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.textSoft,
    padding: '1px 7px',
    fontSize: 10,
    fontWeight: 800
  }),
  mutedText: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 12
  }),
  error: (palette: Palette): CSSProperties => ({
    color: palette.bad,
    fontSize: 12,
    fontWeight: 800
  }),
  empty: (palette: Palette): CSSProperties => ({
    borderRadius: 8,
    border: `1px dashed ${palette.inputBorder}`,
    color: palette.muted,
    padding: 12,
    fontSize: 12
  })
};
