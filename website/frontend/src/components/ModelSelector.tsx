import type { CSSProperties, ReactNode } from 'react';

import type { ManagedModelInfo } from '../types';
import { modelOptionKey } from '../utils/appUi';

interface ModelSelectorProps {
  label: string;
  value: Pick<ManagedModelInfo, 'api' | 'endpoint' | 'name'>;
  options: ManagedModelInfo[];
  onSelect: (target: ManagedModelInfo) => void;
  labelStyle: CSSProperties;
  selectStyle: CSSProperties;
  optionKeyPrefix: string;
  renderOptionLabel: (item: ManagedModelInfo) => ReactNode;
}

export function ModelSelector({
  label,
  value,
  options,
  onSelect,
  labelStyle,
  selectStyle,
  optionKeyPrefix,
  renderOptionLabel
}: ModelSelectorProps) {
  return (
    <label style={labelStyle}>
      <span>{label}</span>
      <select
        value={modelOptionKey(value)}
        onChange={(event) => {
          const target = options.find((item) => modelOptionKey(item) === event.target.value);
          if (target) onSelect(target);
        }}
        style={selectStyle}
      >
        {options.map((item) => (
          <option key={`${optionKeyPrefix}-${modelOptionKey(item)}`} value={modelOptionKey(item)}>
            {renderOptionLabel(item)}
          </option>
        ))}
      </select>
    </label>
  );
}
