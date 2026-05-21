import type { CSSProperties } from 'react';
import { Gauge } from 'lucide-react';
import type { Palette } from '../../styles/appStyles';

interface ModelLimitSummaryProps {
  summary: string;
  palette: Palette;
}

export function ModelLimitSummary({ summary, palette }: ModelLimitSummaryProps) {
  return (
    <div style={styles.wrap(palette)}>
      <Gauge size={14} />
      <span>{summary || 'Unknown until provider telemetry is available.'}</span>
    </div>
  );
}

const styles = {
  wrap: (palette: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    color: palette.textSoft,
    fontSize: 12,
    lineHeight: 1.45,
    minWidth: 0
  })
};
