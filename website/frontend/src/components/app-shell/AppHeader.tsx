import type { ReactNode } from 'react';
import { Brain, Moon, Search, Settings, Sun, User, Wrench } from 'lucide-react';
import { styles, type Palette } from '../../styles/appStyles';

export type AppHeaderProps = {
  palette: Palette;
  compactLayout: boolean;
  narrowLayout: boolean;
  productName: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  connectionLabel: string;
  connectionConnected: boolean;
  modelSwitcher: ReactNode;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  onOpenMemory: () => void;
  onOpenApprovals: () => void;
  onOpenSettings: () => void;
  accountName: string;
  accountPlan: string;
  onLogout: () => void;
};

export function AppHeader({
  palette,
  compactLayout,
  narrowLayout,
  productName,
  searchValue,
  onSearchChange,
  connectionLabel,
  connectionConnected,
  modelSwitcher,
  isDarkMode,
  onToggleDarkMode,
  onOpenMemory,
  onOpenApprovals,
  onOpenSettings,
  accountName,
  accountPlan,
  onLogout
}: AppHeaderProps) {
  return (
    <header style={styles.header(palette, compactLayout, narrowLayout)}>
      <div style={styles.topSearch(palette, compactLayout)} className="aegis-search-surface">
        <Search size={17} />
        <input
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={`Search ${productName}... (Ctrl + K)`}
          aria-label={`Search ${productName}`}
          style={styles.searchInput(palette)}
        />
      </div>

      <div style={styles.headerActions(narrowLayout)}>
        <span style={styles.topStatusPill(palette, connectionConnected)}>
          <span style={styles.statusDot(palette, connectionConnected)} />
          {connectionLabel}
        </span>
        {modelSwitcher}
        <button
          type="button"
          style={styles.iconButton(palette)}
          onClick={onToggleDarkMode}
          title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button type="button" style={styles.iconButton(palette)} onClick={onOpenMemory} title="Memory Editor">
          <Brain size={18} />
        </button>
        <button type="button" style={styles.iconButton(palette)} onClick={onOpenApprovals} title="Approval Settings">
          <Wrench size={18} />
        </button>
        <button type="button" style={styles.iconButton(palette)} onClick={onOpenSettings} title="Settings">
          <Settings size={18} />
        </button>
        <button type="button" style={styles.accountPill(palette)} onClick={onLogout} title="Sign out">
          <User size={16} />
          <span>{accountName}</span>
          <small style={styles.accountPlanText(palette)}>{accountPlan}</small>
        </button>
      </div>
    </header>
  );
}
