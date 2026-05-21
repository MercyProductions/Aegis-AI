import type { CSSProperties } from 'react';
import type { ProviderConnectionStatus } from '../../types';
import type { Palette } from '../../styles/appStyles';

interface ProviderStatusBadgeProps {
  status: ProviderConnectionStatus;
  palette: Palette;
}

export function ProviderStatusBadge({ status, palette }: ProviderStatusBadgeProps) {
  const normalized = String(status || 'unknown').toLowerCase();
  const color =
    normalized === 'linked'
      ? palette.good
      : normalized === 'limited' || normalized === 'expired'
        ? palette.warning
        : normalized === 'error'
          ? palette.bad
          : palette.muted;

  return <span style={badgeStyle(color, palette)}>{labelForStatus(normalized)}</span>;
}

function labelForStatus(status: string): string {
  return status
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'Unknown';
}

function badgeStyle(color: string, palette: Palette): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    width: 'fit-content',
    minHeight: 24,
    borderRadius: 999,
    border: `1px solid ${color}55`,
    background: `${color}18`,
    color: palette.text,
    fontSize: 12,
    fontWeight: 800,
    padding: '2px 9px',
    whiteSpace: 'nowrap'
  };
}
