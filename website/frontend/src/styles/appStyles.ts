// frontend/src/styles/appStyles.ts
import type { CSSProperties } from 'react';
import type { FileChange, ToolEvent } from '../types';

export function getPalette(isDarkMode: boolean) {
  if (isDarkMode) {
    return {
      bgGlow:
        'radial-gradient(circle at 18% 8%, rgba(124,58,237,0.24), transparent 28%), radial-gradient(circle at 78% 2%, rgba(59,130,246,0.18), transparent 30%), radial-gradient(circle at 52% 96%, rgba(34,197,94,0.05), transparent 24%), linear-gradient(180deg, #080B17 0%, #070A14 58%, #050712 100%)',
      bg: '#080B17',
      shell: 'rgba(17,24,39,0.82)',
      shellBorder: 'rgba(255,255,255,0.06)',
      card: 'rgba(17,24,39,0.72)',
      cardAlt: 'rgba(21,26,36,0.78)',
      control: 'rgba(26,32,48,0.72)',
      sidebar: 'linear-gradient(180deg, rgba(17,24,39,0.86), rgba(8,11,23,0.94))',
      navActive: 'linear-gradient(135deg, rgba(124,58,237,0.24), rgba(59,130,246,0.12))',
      settingsRail: 'rgba(8,11,23,0.68)',
      settingsActive: 'rgba(124,58,237,0.16)',
      muted: '#8C98AD',
      text: '#F8FAFC',
      textSoft: '#CBD5E1',
      input: 'rgba(8,11,23,0.76)',
      inputBorder: 'rgba(255,255,255,0.06)',
      accent: '#7C3AED',
      accentSoft: 'rgba(124,58,237,0.14)',
      accentAlt: '#3B82F6',
      userBubble: 'rgba(26,32,48,0.88)',
      assistantBubble: 'rgba(17,24,39,0.86)',
      good: '#22c55e',
      bad: '#ef4444',
      warning: '#f59e0b',
      codeBg: 'rgba(5,7,18,0.92)'
    };
  }

  return {
    bgGlow:
      'radial-gradient(circle at 80% -10%, rgba(124,58,237,0.12), transparent 25%), linear-gradient(135deg, #f8fafc 0%, #eef2ff 58%, #f5f3ff 100%)',
    bg: '#f8fafc',
    shell: 'rgba(255,255,255,0.94)',
    shellBorder: 'rgba(15,23,42,0.12)',
    card: '#ffffff',
    cardAlt: '#f8fafc',
    control: '#ffffff',
    sidebar: 'rgba(255,255,255,0.96)',
    navActive: 'rgba(124,58,237,0.10)',
    settingsRail: 'rgba(248,250,252,0.92)',
    settingsActive: 'rgba(124,58,237,0.10)',
    muted: '#64748b',
    text: '#111827',
    textSoft: '#334155',
    input: '#ffffff',
    inputBorder: 'rgba(15,23,42,0.14)',
    accent: '#7c3aed',
    accentSoft: 'rgba(124,58,237,0.10)',
    accentAlt: '#3b82f6',
    userBubble: 'rgba(255,247,247,0.98)',
    assistantBubble: 'rgba(248,250,252,0.98)',
    good: '#16a34a',
    bad: '#dc2626',
    warning: '#b45309',
    codeBg: '#f8fafc'
  };
}


export type Palette = ReturnType<typeof getPalette>;

export function isDarkPalette(p: Palette): boolean {
  return p.bg === '#080B17';
}

export const styles = {
  appShell: (p: Palette): CSSProperties => ({
    minHeight: '100vh',
    position: 'relative',
    overflow: 'hidden',
    background: p.bgGlow,
    color: p.text,
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: 12
  }),

  routeFallback: (p: Palette): CSSProperties => ({
    minHeight: '100vh',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    background: p.bgGlow,
    color: p.text,
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontSize: 14,
    fontWeight: 800
  }),

  routeBoundary: {
    minHeight: '100vh',
    borderRadius: 0,
    padding: 24
  } as CSSProperties,

  backdrop: (p: Palette): CSSProperties => ({
    position: 'absolute',
    inset: 0,
    background:
      `${p.bgGlow}, radial-gradient(circle at 50% 42%, rgba(255,255,255,0.035), transparent 42%), radial-gradient(circle at 50% 115%, rgba(0,0,0,0.55), transparent 42%)`,
    zIndex: 0
  }),

  frame: (compact: boolean): CSSProperties => ({
    position: 'relative',
    zIndex: 1,
    maxWidth: 'none',
    margin: '0 auto',
    height: 'calc(100vh - 24px)',
    display: 'grid',
    gridTemplateColumns: compact ? 'minmax(0, 1fr)' : '260px minmax(0, 1fr)',
    gridTemplateRows: compact ? 'auto minmax(112px, 220px) minmax(0, 1fr)' : '54px minmax(0, 1fr)',
    gap: compact ? 10 : 12
  }),

  header: (p: Palette, compact = false, narrow = false): CSSProperties => ({
    gridColumn: compact ? '1 / 2' : '2 / 3',
    gridRow: '1 / 2',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: narrow ? 'stretch' : 'center',
    gap: 16,
    flexWrap: narrow ? 'wrap' : 'nowrap',
    padding: 0,
    borderRadius: 0,
    background: 'transparent',
    border: 'none',
    boxShadow: 'none'
  }),

  topSearch: (p: Palette, compact = false): CSSProperties => ({
    width: compact ? '100%' : 'min(620px, 52vw)',
    flex: compact ? '1 1 320px' : '0 1 auto',
    height: 46,
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.58)' : 'rgba(255,255,255,0.82)',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 16px',
    color: p.muted,
    backdropFilter: 'blur(24px)',
    boxShadow: isDarkPalette(p)
      ? '0 18px 48px rgba(2,6,23,0.26), inset 0 1px 0 rgba(255,255,255,0.04)'
      : '0 18px 48px rgba(15,23,42,0.08), inset 0 1px 0 rgba(255,255,255,0.82)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  brandWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    minWidth: 0
  } as CSSProperties,

  brandIcon: (p: Palette): CSSProperties => ({
    width: 40,
    height: 40,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: `linear-gradient(135deg, rgba(8,11,23,0.92), rgba(26,32,48,0.76))`,
    border: `1px solid rgba(139,92,246,0.28)`,
    color: p.text,
    flexShrink: 0,
    overflow: 'hidden',
    boxShadow: '0 16px 42px rgba(124,58,237,0.24), 0 0 34px rgba(59,130,246,0.10), inset 0 1px 0 rgba(255,255,255,0.10)'
  }),

  brandIconImage: {
    width: '84%',
    height: '84%',
    objectFit: 'contain',
    objectPosition: '50% 50%',
    filter: 'saturate(1.18) contrast(1.05)'
  } as CSSProperties,

  brandTitle: (p: Palette): CSSProperties => ({
    fontSize: 19,
    fontWeight: 900,
    letterSpacing: 1.2,
    color: p.text,
    lineHeight: 1.1
  }),

  brandSubtitle: (p: Palette): CSSProperties => ({
    marginTop: 4,
    fontSize: 13,
    color: p.muted,
    maxWidth: 800,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  }),

  headerActions: (narrow = false): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: narrow ? 'flex-start' : 'flex-end',
    gap: 8,
    flexWrap: 'wrap',
    minWidth: 0
  }),

  topStatusPill: (p: Palette, ok: boolean): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: ok ? 'rgba(34,197,94,0.10)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 9,
    fontSize: 13,
    fontWeight: 800,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  accountPill: (p: Palette): CSSProperties => ({
    minHeight: 40,
    maxWidth: 230,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.66)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    cursor: 'pointer',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  accountPlanText: (p: Palette): CSSProperties => ({
    color: p.accent,
    fontSize: 11,
    fontWeight: 850,
    whiteSpace: 'nowrap'
  }),

  statusDot: (p: Palette, ok: boolean): CSSProperties => ({
    width: 9,
    height: 9,
    borderRadius: 999,
    background: ok ? p.good : p.bad,
    boxShadow: `0 0 18px ${ok ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'}`
  }),

  modelSwitcher: {
    position: 'relative',
    display: 'inline-flex'
  } as CSSProperties,

  modelPill: (p: Palette, active = false): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: active ? p.settingsActive : isDarkPalette(p) ? 'rgba(17,24,39,0.62)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    fontWeight: 800,
    cursor: 'pointer',
    maxWidth: 240,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  modelPillLabel: {
    maxWidth: 160,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  } as CSSProperties,

  modelMenu: (p: Palette): CSSProperties => ({
    position: 'absolute',
    top: 48,
    right: 0,
    zIndex: 70,
    width: 380,
    maxWidth: 'calc(100vw - 32px)',
    border: `1px solid ${p.shellBorder}`,
    borderRadius: 14,
    background: p.shell,
    boxShadow: '0 24px 70px rgba(0,0,0,0.36)',
    padding: 12,
    display: 'grid',
    gap: 10
  }),

  modelMenuHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    padding: '4px 4px 10px',
    borderBottom: `1px solid ${p.shellBorder}`
  }),

  modelMenuList: {
    display: 'grid',
    gap: 8,
    maxHeight: 360,
    overflowY: 'auto'
  } as CSSProperties,

  modelMenuRow: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    borderRadius: 12,
    background: active ? p.settingsActive : p.card,
    color: p.text,
    cursor: active ? 'default' : 'pointer',
    padding: '10px 12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    textAlign: 'left'
  }),

  modelMenuName: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    color: p.text,
    fontWeight: 800,
    overflowWrap: 'anywhere'
  }),

  modelMenuFooter: (p: Palette): CSSProperties => ({
    paddingTop: 10,
    borderTop: `1px solid ${p.shellBorder}`,
    display: 'flex',
    justifyContent: 'flex-end'
  }),

  iconButton: (p: Palette): CSSProperties => ({
    width: 40,
    height: 40,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.64)' : p.card,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  utilityBar: (p: Palette, compact = false): CSSProperties => ({
    gridColumn: '1 / 2',
    gridRow: compact ? '2 / 3' : '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    alignItems: 'stretch',
    minHeight: 0,
    maxHeight: compact ? 220 : undefined,
    padding: 12,
    borderRadius: 18,
    background: p.sidebar,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 28px 80px rgba(2,6,23,0.34), inset 0 1px 0 rgba(255,255,255,0.04)',
    overflowX: 'hidden',
    overflowY: 'auto',
    scrollbarWidth: 'thin',
    backdropFilter: 'blur(28px)'
  }),

  utilityActions: (compact = false): CSSProperties => ({
    display: 'flex',
    flexDirection: compact ? 'row' : 'column',
    alignItems: 'center',
    gap: 8
  }),

  sidebarBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minHeight: 54,
    padding: '4px 4px 10px'
  } as CSSProperties,

  primaryUtilityButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 48,
    padding: '0 16px',
    borderRadius: 14,
    border: 'none',
    background: `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: '#fff',
    fontWeight: 850,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 10,
    cursor: 'pointer',
    boxShadow: '0 18px 42px rgba(124,58,237,0.30), inset 0 1px 0 rgba(255,255,255,0.18)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  utilityActionButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 40,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.72)' : p.cardAlt,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  sidebarNav: (compact = false): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: compact ? 'repeat(auto-fit, minmax(132px, 1fr))' : undefined,
    gap: 6
  }),

  sidebarNavItem: (p: Palette, active: boolean, compact = false): CSSProperties => ({
    width: '100%',
    minHeight: 42,
    borderRadius: 12,
    border: active ? '1px solid rgba(139,92,246,0.20)' : '1px solid transparent',
    background: active ? p.navActive : 'transparent',
    color: p.text,
    display: 'flex',
    alignItems: 'center',
    justifyContent: compact ? 'center' : 'flex-start',
    gap: 12,
    padding: '0 12px',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: active ? 800 : 650,
    textAlign: 'left',
    boxShadow: active ? '0 12px 30px rgba(124,58,237,0.13), inset 0 1px 0 rgba(255,255,255,0.05)' : 'none',
    transition: 'background 180ms ease, border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease'
  }),

  sidebarSectionLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    padding: '8px 8px 0'
  }),

  searchWrap: (p: Palette): CSSProperties => ({
    minHeight: 40,
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.56)' : p.cardAlt,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 14px',
    color: p.muted,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  searchInput: (p: Palette): CSSProperties => ({
    width: '100%',
    border: 'none',
    outline: 'none',
    background: 'transparent',
    color: p.text,
    fontSize: 14
  }),

  inlineIconButton: (p: Palette): CSSProperties => ({
    width: 28,
    height: 28,
    borderRadius: 10,
    border: 'none',
    background: 'transparent',
    color: p.muted,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    flex: '0 0 auto'
  }),

  historyRail: {
    display: 'grid',
    gap: 4,
    flex: '0 0 auto',
    alignContent: 'start',
    overflowY: 'visible',
    minHeight: 'auto',
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  threadPill: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    minHeight: 36,
    padding: '0 10px',
    borderRadius: 10,
    border: active ? '1px solid rgba(139,92,246,0.18)' : '1px solid transparent',
    background: active ? 'rgba(124,58,237,0.14)' : 'transparent',
    color: p.text,
    whiteSpace: 'normal',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: active ? 750 : 500,
    transition: 'background 180ms ease, border-color 180ms ease'
  }),

  threadGroup: (p: Palette): CSSProperties => ({
    minHeight: 36,
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    alignItems: 'center',
    gap: 4,
    padding: '0 4px 0 0',
    borderRadius: 6,
    border: 'none',
    background: 'transparent',
    flex: '0 0 auto',
    width: '100%'
  }),

  sidebarUserCard: (p: Palette): CSSProperties => ({
    marginTop: 8,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(135deg, rgba(26,32,48,0.72), rgba(17,24,39,0.58))'
      : p.card,
    boxShadow: isDarkPalette(p)
      ? '0 18px 44px rgba(2,6,23,0.22), inset 0 1px 0 rgba(255,255,255,0.04)'
      : '0 18px 44px rgba(15,23,42,0.08)'
  }),

  sidebarUserName: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 13
  }),

  sidebarUserPlan: (p: Palette): CSSProperties => ({
    color: p.accent,
    fontWeight: 800,
    fontSize: 12,
    marginTop: 2
  }),

  threadDeleteButton: (p: Palette): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 999,
    border: 'none',
    background: 'transparent',
    color: p.muted,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    position: 'relative',
    zIndex: 1
  }),

  mainGrid: (detailsVisible: boolean, compact = false): CSSProperties => ({
    gridColumn: compact ? '1 / 2' : '2 / 3',
    gridRow: compact ? '3 / 4' : '2 / 3',
    display: 'grid',
    gridTemplateColumns: detailsVisible && !compact ? 'minmax(0, 1fr) 360px' : 'minmax(0, 1fr)',
    gap: 12,
    height: '100%',
    minHeight: 0
  }),

  chatCard: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateRows: '1fr auto auto auto',
    minHeight: 0,
    borderRadius: 18,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(17,24,39,0.84), rgba(8,11,23,0.96)), radial-gradient(circle at 50% 4%, rgba(124,58,237,0.16), transparent 38%)'
      : p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 32px 100px rgba(2,6,23,0.42), inset 0 1px 0 rgba(255,255,255,0.05)',
    overflow: 'hidden',
    backdropFilter: 'blur(28px)'
  }),

  chatScroll: {
    overflowY: 'auto',
    padding: '22px',
    minHeight: 0,
    background:
      'radial-gradient(circle at 50% 18%, rgba(124,58,237,0.10), transparent 34%), radial-gradient(circle at 78% 42%, rgba(59,130,246,0.06), transparent 26%), linear-gradient(180deg, rgba(255,255,255,0.015), transparent 34%)'
  } as CSSProperties,

  surfacePage: {
    display: 'grid',
    gap: 16,
    alignContent: 'start',
    minHeight: '100%'
  } as CSSProperties,

  surfaceHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
    padding: 18,
    borderRadius: 18,
    background: isDarkPalette(p)
      ? 'linear-gradient(135deg, rgba(26,32,48,0.72), rgba(17,24,39,0.64))'
      : p.card,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: '0 18px 48px rgba(2,6,23,0.18), inset 0 1px 0 rgba(255,255,255,0.05)'
  }),

  surfaceTitleWrap: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 14,
    minWidth: 0
  } as CSSProperties,

  surfaceIcon: (p: Palette): CSSProperties => ({
    width: 44,
    height: 44,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: `linear-gradient(135deg, rgba(124,58,237,0.22), rgba(59,130,246,0.12))`,
    border: `1px solid rgba(139,92,246,0.20)`,
    color: p.text,
    flexShrink: 0,
    boxShadow: '0 14px 32px rgba(124,58,237,0.12)'
  }),

  surfaceTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    color: p.text,
    fontSize: 24,
    lineHeight: 1.2
  }),

  surfaceSubtitle: (p: Palette): CSSProperties => ({
    margin: '6px 0 0',
    color: p.muted,
    lineHeight: 1.5,
    maxWidth: 760
  }),

  surfaceActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  surfaceColumns: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 0.9fr) minmax(320px, 1.1fr)',
    gap: 16,
    alignItems: 'start'
  } as CSSProperties,

  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 12
  } as CSSProperties,

  metricCard: (p: Palette): CSSProperties => ({
    minHeight: 88,
    display: 'grid',
    gap: 8,
    alignContent: 'center',
    padding: 14,
    borderRadius: 16,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(26,32,48,0.66), rgba(17,24,39,0.62))'
      : p.card,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: '0 14px 34px rgba(2,6,23,0.16), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  metricLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  metricValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 18,
    lineHeight: 1.25,
    overflowWrap: 'anywhere'
  }),

  emptyState: {
    minHeight: '100%',
    display: 'grid',
    alignContent: 'center',
    justifyItems: 'center',
    textAlign: 'center',
    padding: '32px 12px',
    position: 'relative'
  } as CSSProperties,

  emptyLogo: (p: Palette): CSSProperties => ({
    width: 76,
    height: 76,
    borderRadius: 24,
    display: 'grid',
    placeItems: 'center',
    marginBottom: 22,
    background: `linear-gradient(135deg, rgba(8,11,23,0.96), rgba(26,32,48,0.74))`,
    color: p.text,
    border: '1px solid rgba(139,92,246,0.22)',
    overflow: 'hidden',
    boxShadow: '0 28px 70px rgba(124,58,237,0.22), 0 0 80px rgba(59,130,246,0.10), inset 0 1px 0 rgba(255,255,255,0.12)'
  }),

  emptyLogoImage: {
    width: '86%',
    height: '86%',
    objectFit: 'contain',
    objectPosition: '50% 50%',
    filter: 'saturate(1.18) contrast(1.06)'
  } as CSSProperties,

  emptyTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 34,
    lineHeight: 1.1,
    color: p.text,
    textShadow: '0 18px 50px rgba(124,58,237,0.22)'
  }),

  emptyText: (p: Palette): CSSProperties => ({
    maxWidth: 700,
    margin: '12px auto 0',
    fontSize: 15,
    lineHeight: 1.7,
    color: p.muted
  }),

  promptGrid: {
    marginTop: 30,
    width: '100%',
    maxWidth: 860,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 12
  } as CSSProperties,

  promptCard: (p: Palette): CSSProperties => ({
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(145deg, rgba(26,32,48,0.78), rgba(17,24,39,0.58)), radial-gradient(circle at 0% 0%, rgba(124,58,237,0.12), transparent 38%)'
      : p.card,
    color: p.text,
    padding: '18px 18px',
    textAlign: 'left',
    fontSize: 14,
    lineHeight: 1.5,
    cursor: 'pointer',
    boxShadow: '0 18px 42px rgba(2,6,23,0.20), inset 0 1px 0 rgba(255,255,255,0.05)',
    transition: 'transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  workspaceSignalGrid: {
    marginTop: 22,
    width: '100%',
    maxWidth: 860,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
    gap: 12
  } as CSSProperties,

  workspaceSignalCard: (p: Palette): CSSProperties => ({
    minHeight: 122,
    display: 'grid',
    gap: 10,
    alignContent: 'start',
    padding: 16,
    borderRadius: 18,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(17,24,39,0.58), rgba(8,11,23,0.52)), radial-gradient(circle at 16% 0%, rgba(59,130,246,0.08), transparent 42%)'
      : p.cardAlt,
    textAlign: 'left',
    boxShadow: '0 18px 44px rgba(2,6,23,0.18), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  workspaceSignalTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 10
  } as CSSProperties,

  workspaceSignalIcon: (p: Palette, tone: 'purple' | 'blue' | 'green'): CSSProperties => {
    const color = tone === 'green' ? p.good : tone === 'blue' ? '#3B82F6' : p.accent;
    return {
      width: 34,
      height: 34,
      borderRadius: 12,
      display: 'grid',
      placeItems: 'center',
      background: `${color}1F`,
      color,
      border: `1px solid ${color}33`,
      boxShadow: `0 10px 28px ${color}1F`
    };
  },

  workspaceSignalLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 850,
    textTransform: 'uppercase'
  }),

  workspaceSignalValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 15,
    lineHeight: 1.35,
    overflowWrap: 'anywhere'
  }),

  workspaceSignalMeta: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    lineHeight: 1.5,
    overflowWrap: 'anywhere'
  }),

  messageRow: (isUser: boolean): CSSProperties => ({
    display: 'flex',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
    gap: 12,
    marginBottom: 18,
    alignItems: 'flex-start'
  }),

  avatar: (p: Palette, isUser: boolean): CSSProperties => ({
    width: 36,
    height: 36,
    minWidth: 36,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: isUser ? p.accentSoft : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    color: p.text,
    order: isUser ? 2 : 0
  }),

  messageBubble: (p: Palette, isUser: boolean): CSSProperties => ({
    maxWidth: 'min(820px, 84%)',
    padding: '14px 16px',
    borderRadius: 22,
    border: `1px solid ${p.inputBorder}`,
    background: isUser ? p.userBubble : p.assistantBubble,
    color: p.text,
    boxShadow: isUser
      ? '0 18px 48px rgba(124,58,237,0.12), inset 0 1px 0 rgba(255,255,255,0.05)'
      : '0 18px 48px rgba(2,6,23,0.20), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  messageRole: (p: Palette): CSSProperties => ({
    fontSize: 12,
    fontWeight: 700,
    color: p.muted,
    marginBottom: 8,
    letterSpacing: 0.2
  }),

  messageText: (p: Palette): CSSProperties => ({
    whiteSpace: 'pre-wrap',
    lineHeight: 1.7,
    fontSize: 15,
    color: p.text
  }),

  messageContentStack: {
    display: 'grid',
    gap: 12
  } as CSSProperties,

  chatCodeFrame: (p: Palette): CSSProperties => ({
    border: `1px solid ${p.inputBorder}`,
    borderRadius: 12,
    overflow: 'hidden',
    background: p.codeBg
  }),

  chatCodeHeader: (p: Palette): CSSProperties => ({
    minHeight: 34,
    padding: '0 10px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    borderBottom: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.muted,
    fontSize: 12,
    fontWeight: 800
  }),

  chatCodeCopyButton: (p: Palette): CSSProperties => ({
    marginLeft: 'auto',
    minHeight: 26,
    padding: '0 8px',
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 800
  }),

  chatCodeBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 14,
    maxHeight: 360,
    overflow: 'auto',
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre',
    tabSize: 2
  }),

  inlineChangeReview: (p: Palette): CSSProperties => ({
    marginTop: 14,
    border: `1px solid ${p.inputBorder}`,
    borderRadius: 14,
    overflow: 'hidden',
    background: p.cardAlt
  }),

  inlineChangeHeader: {
    minHeight: 48,
    padding: '0 14px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12
  } as CSSProperties,

  inlineChangeTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    minWidth: 0,
    color: p.text,
    fontWeight: 850,
    fontSize: 14
  }),

  inlineChangeActions: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  reviewChangesButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850,
    whiteSpace: 'nowrap'
  }),

  addedLines: {
    color: '#22c55e',
    fontWeight: 900
  } as CSSProperties,

  removedLines: {
    color: '#ef4444',
    fontWeight: 900
  } as CSSProperties,

  inlineChangeStatus: (p: Palette): CSSProperties => ({
    padding: '0 14px 10px',
    color: p.muted,
    fontSize: 12,
    fontWeight: 650
  }),

  inlineChangeList: {
    display: 'grid'
  } as CSSProperties,

  inlineChangeItem: (p: Palette): CSSProperties => ({
    width: '100%',
    minHeight: 42,
    padding: '8px 14px',
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto auto',
    alignItems: 'center',
    gap: 10,
    border: 'none',
    borderTop: `1px solid ${p.inputBorder}`,
    background: 'transparent',
    color: p.text,
    cursor: 'pointer',
    textAlign: 'left'
  }),

  inlineChangePath: (p: Palette): CSSProperties => ({
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: p.textSoft,
    fontSize: 13,
    fontWeight: 750
  }),

  inlineChangeAction: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase'
  }),

  inlineChangeDelta: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minWidth: 58,
    justifyContent: 'flex-end',
    fontSize: 12
  } as CSSProperties,

  inlineChangePending: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontWeight: 800
  }),

  thinkingInline: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    color: p.textSoft,
    fontSize: 14,
    flexWrap: 'wrap'
  }),

  retryBadge: (p: Palette): CSSProperties => ({
    marginLeft: 6,
    padding: '4px 8px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700
  }),

  inlineQueuePanel: (p: Palette): CSSProperties => ({
    width: 'min(820px, 88%)',
    margin: '0 0 18px 48px',
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    overflow: 'hidden'
  }),

  inlineQueueHeader: (p: Palette): CSSProperties => ({
    minHeight: 42,
    padding: '0 12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    borderBottom: `1px solid ${p.inputBorder}`,
    color: p.muted,
    fontSize: 12,
    fontWeight: 850
  }),

  inlineQueueTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.text
  }),

  inlineQueueList: {
    display: 'grid'
  } as CSSProperties,

  inlineQueueItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) 34px',
    gap: 10,
    alignItems: 'center',
    minHeight: 42,
    padding: '8px 10px',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  inlineQueueIndex: (p: Palette): CSSProperties => ({
    width: 24,
    height: 24,
    borderRadius: 999,
    display: 'grid',
    placeItems: 'center',
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 900
  }),

  inlineQueueText: (p: Palette): CSSProperties => ({
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: p.textSoft,
    fontSize: 13,
    fontWeight: 700
  }),

  inlineQueueDiscard: (p: Palette): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.muted,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),

  queueButton: (p: Palette, active: boolean): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    height: 34,
    padding: '0 12px',
    borderRadius: 999,
    background: active ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.12)',
    color: p.warning,
    border: '1px solid rgba(251,191,36,0.22)',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer'
  }),

  queueTray: (p: Palette): CSSProperties => ({
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.88), rgba(8,11,23,0.94))' : p.shell,
    padding: '14px 20px',
    display: 'grid',
    gap: 12
  }),

  queueTrayHeader: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    alignItems: 'center',
    gap: 12
  } as CSSProperties,

  queueTrayTitle: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 14
  }),

  queueTrayMeta: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    marginTop: 3
  }),

  queueTrayActions: {
    display: 'flex',
    gap: 8,
    alignItems: 'center'
  } as CSSProperties,

  queueList: {
    display: 'grid',
    gap: 10,
    maxHeight: 250,
    overflowY: 'auto'
  } as CSSProperties,

  queueItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 12,
    alignItems: 'center',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  queueItemActions: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  queueMoveButton: (p: Palette, disabled: boolean): CSSProperties => ({
    width: 32,
    height: 32,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: disabled ? p.shell : p.card,
    color: disabled ? p.muted : p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1
  }),

  queueItemMain: {
    display: 'grid',
    gap: 7,
    minWidth: 0
  } as CSSProperties,

  queueItemTop: (p: Palette): CSSProperties => ({
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    color: p.muted,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase'
  }),

  queueItemText: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 13,
    lineHeight: 1.45,
    overflow: 'hidden',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
    overflowWrap: 'anywhere'
  }),

  statusRow: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    padding: '14px 20px',
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.58), rgba(8,11,23,0.64))' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  statusCluster: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap'
  } as CSSProperties,

  statusChip: (p: Palette, ok: boolean): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    height: 34,
    padding: '0 12px',
    borderRadius: 999,
    background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.12)',
    color: ok ? p.good : p.bad,
    border: `1px solid ${ok ? 'rgba(34,197,94,0.18)' : 'rgba(248,113,113,0.18)'}`,
    fontSize: 13,
    fontWeight: 700,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  diagnosticChip: (p: Palette, status: 'ok' | 'warning' | 'error'): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    minHeight: 34,
    padding: '0 12px',
    borderRadius: 999,
    background:
      status === 'ok'
        ? 'rgba(34,197,94,0.12)'
        : status === 'warning'
          ? 'rgba(251,191,36,0.12)'
          : 'rgba(248,113,113,0.12)',
    color: status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad,
    border: `1px solid ${
      status === 'ok'
        ? 'rgba(34,197,94,0.18)'
        : status === 'warning'
          ? 'rgba(251,191,36,0.22)'
          : 'rgba(248,113,113,0.18)'
    }`,
    fontSize: 13,
    fontWeight: 700
  }),

  errorStatus: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.bad,
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'right'
  }),

  metaStatus: (p: Palette): CSSProperties => ({
    fontSize: 13,
    color: p.muted,
    textAlign: 'right'
  }),

  composerWrap: (p: Palette): CSSProperties => ({
    padding: 16,
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(8,11,23,0.76), rgba(8,11,23,0.94)), radial-gradient(circle at 50% 0%, rgba(124,58,237,0.12), transparent 45%)'
      : p.card,
    boxShadow: '0 -20px 70px rgba(2,6,23,0.34), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  contextPinBar: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 14,
    padding: 10,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.68)' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  contextPinLead: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  contextPin: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 28,
    maxWidth: '100%',
    padding: '0 8px 0 10px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700,
    overflowWrap: 'anywhere'
  }),

  contextPinRemove: (p: Palette): CSSProperties => ({
    width: 20,
    height: 20,
    borderRadius: 999,
    border: 'none',
    background: 'transparent',
    color: p.text,
    cursor: 'pointer',
    display: 'grid',
    placeItems: 'center',
    padding: 0
  }),

  composerOptions: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
    marginBottom: 12,
    padding: '0 2px',
    color: p.muted
  }),

  optionGroup: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap',
    alignItems: 'center'
  } as CSSProperties,

  checkboxLabel: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: p.textSoft
  }),

  composerForm: {
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 14,
    alignItems: 'end'
  } as CSSProperties,

  composerInput: (p: Palette): CSSProperties => ({
    minHeight: 76,
    maxHeight: 180,
    resize: 'vertical',
    width: '100%',
    borderRadius: 20,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(8,11,23,0.72)' : p.input,
    color: p.text,
    padding: '18px 20px',
    outline: 'none',
    fontSize: 15,
    lineHeight: 1.5,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 50px rgba(2,6,23,0.18)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  sendButton: (p: Palette, disabled: boolean): CSSProperties => ({
    width: 58,
    height: 58,
    borderRadius: 18,
    border: 'none',
    background: disabled ? p.cardAlt : `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: disabled ? p.muted : '#fff',
    display: 'grid',
    placeItems: 'center',
    cursor: disabled ? 'not-allowed' : 'pointer',
    boxShadow: disabled ? 'inset 0 1px 0 rgba(255,255,255,0.04)' : '0 18px 42px rgba(124,58,237,0.28), inset 0 1px 0 rgba(255,255,255,0.16)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  sidebar: {
    display: 'grid',
    gap: 12,
    minHeight: 0,
    overflowY: 'auto',
    alignContent: 'start',
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  panelCard: (p: Palette): CSSProperties => ({
    minHeight: 0,
    borderRadius: 18,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.74), rgba(8,11,23,0.86))' : p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 22px 64px rgba(2,6,23,0.26), inset 0 1px 0 rgba(255,255,255,0.04)',
    overflow: 'hidden',
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    backdropFilter: 'blur(22px)'
  }),

  panelHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    padding: '15px 16px',
    borderBottom: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(26,32,48,0.58), rgba(17,24,39,0.42))' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  panelTitleWrap: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,

  panelTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: p.text,
    fontWeight: 850
  }),

  panelHeaderActions: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 8,
    flexShrink: 0
  } as CSSProperties,

  panelCollapseButton: (p: Palette, collapsed: boolean): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: collapsed ? p.accentSoft : p.card,
    color: p.text,
    cursor: 'pointer',
    display: 'inline-grid',
    placeItems: 'center',
    transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
    transition: 'background 160ms ease, transform 160ms ease'
  }),

  counterBadge: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 28,
    height: 28,
    padding: '0 10px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700
  }),

  panelBody: {
    padding: 16,
    overflow: 'visible',
    display: 'grid',
    gap: 16,
    alignContent: 'start'
  } as CSSProperties,

  replyCard: (p: Palette): CSSProperties => ({
    padding: 16,
    borderRadius: 18,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.62)' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  replyText: (p: Palette): CSSProperties => ({
    color: p.text,
    lineHeight: 1.65,
    whiteSpace: 'pre-wrap'
  }),

  sectionBlock: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  sectionHeaderInline: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap'
  } as CSSProperties,

  repairTrailControls: {
    display: 'flex',
    gap: 10,
    alignItems: 'center',
    flexWrap: 'wrap'
  } as CSSProperties,

  repairTrailSearch: {
    flex: '1 1 240px',
    minWidth: 220
  } as CSSProperties,

  segmentedControl: (p: Palette): CSSProperties => ({
    minHeight: 40,
    padding: 4,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap'
  }),

  segmentedButton: (p: Palette, active: boolean): CSSProperties => ({
    minHeight: 30,
    padding: '0 10px',
    borderRadius: 10,
    border: 'none',
    background: active ? p.accent : 'transparent',
    color: active ? '#fff' : p.text,
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: 12
  }),

  reviewSummary: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,

  sectionLabel: (p: Palette): CSSProperties => ({
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    color: p.muted
  }),

  planList: (p: Palette): CSSProperties => ({
    margin: 0,
    paddingLeft: 18,
    color: p.text,
    lineHeight: 1.7
  }),

  changeList: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  changeButton: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    textAlign: 'left',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    cursor: 'pointer',
    display: 'grid',
    gap: 8
  }),

  changeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  changeActionBadge: (p: Palette, action: FileChange['action']): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 64,
    height: 24,
    padding: '0 8px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 800,
    textTransform: 'uppercase',
    color: action === 'create' ? p.good : action === 'update' ? p.warning : p.bad,
    background:
      action === 'create'
        ? 'rgba(34,197,94,0.12)'
        : action === 'update'
          ? 'rgba(251,191,36,0.16)'
          : 'rgba(248,113,113,0.12)'
  }),

  changePath: (p: Palette): CSSProperties => ({
    color: p.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }),

  changeSummary: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 13,
    lineHeight: 1.5
  }),

  previewCard: (p: Palette): CSSProperties => ({
    borderRadius: 18,
    overflow: 'hidden',
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  previewHeader: (p: Palette): CSSProperties => ({
    padding: 14,
    borderBottom: `1px solid ${p.inputBorder}`,
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'center',
    flexWrap: 'wrap'
  }),

  previewTitle: (p: Palette): CSSProperties => ({
    fontSize: 14,
    fontWeight: 700,
    color: p.text
  }),

  previewMeta: (p: Palette): CSSProperties => ({
    marginTop: 4,
    fontSize: 12,
    color: p.muted
  }),

  previewTabs: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 14px 0',
    flexWrap: 'wrap'
  } as CSSProperties,

  previewTab: (p: Palette, active: boolean): CSSProperties => ({
    height: 32,
    padding: '0 12px',
    borderRadius: 999,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    color: active ? p.text : p.muted,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 700
  }),

  diffMeta: (p: Palette): CSSProperties => ({
    marginLeft: 'auto',
    color: p.muted,
    fontSize: 12,
    fontWeight: 700
  }),

  codeBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 360,
    overflow: 'auto',
    background: p.codeBg,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  diffBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 360,
    overflow: 'auto',
    background: `linear-gradient(180deg, ${p.codeBg}, ${p.cardAlt})`,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  tagWrap: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8
  } as CSSProperties,

  goodTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 999,
    background: 'rgba(34,197,94,0.12)',
    color: p.good,
    fontSize: 12,
    fontWeight: 700
  }),

  warningTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 999,
    background: 'rgba(251,191,36,0.14)',
    color: p.warning,
    fontSize: 12,
    fontWeight: 700
  }),

  contextTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    minHeight: 30,
    padding: '0 10px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.textSoft,
    fontSize: 12,
    fontWeight: 600
  }),

  warningBox: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    padding: 14,
    borderRadius: 18,
    background: 'rgba(251,191,36,0.10)',
    border: `1px solid ${p.inputBorder}`
  }),

  inlineWarning: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    padding: '10px 14px',
    borderBottom: `1px solid ${p.inputBorder}`,
    background: 'rgba(251,191,36,0.10)',
    color: p.text,
    fontSize: 12,
    lineHeight: 1.5
  }),

  warningTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.warning,
    fontWeight: 700
  }),

  warningList: (p: Palette): CSSProperties => ({
    margin: 0,
    paddingLeft: 18,
    color: p.text,
    lineHeight: 1.6
  }),

  validationCard: (p: Palette, ok: boolean): CSSProperties => ({
    borderRadius: 18,
    border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : p.inputBorder}`,
    background: p.cardAlt,
    overflow: 'hidden'
  }),

  validationMeta: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 4,
    padding: 14,
    borderBottom: `1px solid ${p.inputBorder}`,
    color: p.text
  }),

  validationSummary: (p: Palette): CSSProperties => ({
    padding: '14px 14px 0',
    color: p.textSoft,
    fontSize: 13,
    lineHeight: 1.5
  }),

  validationContext: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    margin: '12px 14px 0',
    padding: 12,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.textSoft,
    fontSize: 12,
    lineHeight: 1.4
  }),

  contextButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6
  }),

  consoleBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 280,
    overflow: 'auto',
    background: p.codeBg,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  eventList: {
    display: 'grid',
    gap: 8
  } as CSSProperties,

  activityFilterBar: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
    gap: 4,
    padding: 4,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.54)' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  activityFilterButton: (p: Palette, active: boolean): CSSProperties => ({
    minHeight: 30,
    borderRadius: 10,
    border: 'none',
    background: active ? `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})` : 'transparent',
    color: active ? '#fff' : p.textSoft,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850,
    transition: 'background 160ms ease, color 160ms ease'
  }),

  eventRow: (p: Palette, status: ToolEvent['status']): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 12,
    alignItems: 'start',
    padding: 12,
    borderRadius: 14,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.56)' : p.cardAlt,
    borderLeft: `3px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    borderTop: `1px solid ${p.inputBorder}`,
    borderRight: `1px solid ${p.inputBorder}`,
    borderBottom: `1px solid ${p.inputBorder}`,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  eventTitle: (p: Palette): CSSProperties => ({
    color: p.text
  }),

  eventDetail: (p: Palette): CSSProperties => ({
    marginTop: 4,
    color: p.muted,
    fontSize: 13,
    lineHeight: 1.5
  }),

  eventTime: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    whiteSpace: 'nowrap'
  }),

  eventActions: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 8
  } as CSSProperties,

  liveBadge: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    minHeight: 24,
    padding: '0 9px',
    borderRadius: 999,
    color: p.good,
    background: 'rgba(34,197,94,0.10)',
    border: '1px solid rgba(34,197,94,0.18)',
    fontSize: 12,
    fontWeight: 900
  }),

  activityRow: (p: Palette, status: 'ok' | 'warning' | 'error'): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '54px 1fr',
    gap: 10,
    padding: '10px 10px 10px 12px',
    borderLeft: `2px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    color: p.text,
    borderRadius: 12,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.34)' : p.card
  }),

  activityContent: {
    display: 'grid',
    gap: 8,
    minWidth: 0
  } as CSSProperties,

  activityToggleButton: (p: Palette): CSSProperties => ({
    width: '100%',
    border: 'none',
    background: 'transparent',
    color: p.text,
    padding: 0,
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 8,
    alignItems: 'start',
    textAlign: 'left',
    cursor: 'pointer'
  }),

  activityTextStack: {
    display: 'grid',
    gap: 2,
    minWidth: 0
  } as CSSProperties,

  activityChevron: (expanded: boolean): CSSProperties => ({
    marginTop: 2,
    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
    transition: 'transform 160ms ease'
  }),

  activityDetails: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    padding: 10,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  activityDetailGrid: {
    display: 'grid',
    gap: 6
  } as CSSProperties,

  activityDetailItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 2,
    minWidth: 0,
    color: p.text,
    fontSize: 12
  }),

  activityDetailLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 11,
    textTransform: 'uppercase',
    fontWeight: 800
  }),

  activityDetailValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 12,
    overflowWrap: 'anywhere'
  }),

  activityOutputBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 10,
    maxHeight: 220,
    overflow: 'auto',
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.codeBg,
    color: p.text,
    fontSize: 12,
    lineHeight: 1.55,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  activityLogToggle: (p: Palette): CSSProperties => ({
    width: '100%',
    minHeight: 36,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850
  }),

  activityTime: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    lineHeight: 1.5
  }),

  emptyPanel: (p: Palette): CSSProperties => ({
    padding: 14,
    borderRadius: 18,
    border: `1px dashed ${p.inputBorder}`,
    color: p.muted,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.48)' : p.cardAlt,
    lineHeight: 1.6,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  workspaceMeta: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    padding: 12,
    borderRadius: 16,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.52)' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    color: p.text
  }),

  modelList: {
    display: 'grid',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  modelRow: (p: Palette, active: boolean): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 14,
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    background: active ? p.accentSoft : p.card,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    minWidth: 0
  }),

  taskListItem: (p: Palette, active: boolean): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 14,
    alignItems: 'center',
    width: '100%',
    padding: 14,
    borderRadius: 12,
    background: active ? p.accentSoft : p.card,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    color: p.text,
    textAlign: 'left',
    cursor: 'pointer',
    minWidth: 0
  }),

  modelRowMain: {
    display: 'grid',
    gap: 8,
    minWidth: 0
  } as CSSProperties,

  modelRowTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  rowActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  compactCard: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 12,
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`,
    minWidth: 0
  }),

  cardTitle: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 14,
    overflowWrap: 'anywhere'
  }),

  agentHero: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr)',
    gap: 12,
    padding: 14,
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`
  }),

  formGridTwo: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 12
  } as CSSProperties,

  fieldButtonSlot: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'flex-start'
  } as CSSProperties,

  fileList: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  fileButton: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    textAlign: 'left',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    cursor: 'pointer',
    display: 'grid',
    gap: 8
  }),

  fileButtonTop: {
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 10,
    alignItems: 'center'
  } as CSSProperties,

  filePath: (p: Palette): CSSProperties => ({
    color: p.text,
    overflowWrap: 'anywhere'
  }),

  fileSize: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12
  }),

  fileKind: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  modalOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(2,6,23,0.52)',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    zIndex: 20
  } as CSSProperties,

  modalCard: (p: Palette): CSSProperties => ({
    width: 'min(1060px, 100%)',
    maxHeight: '86vh',
    overflow: 'hidden',
    borderRadius: 20,
    background: p.shell,
    border: `1px solid ${p.shellBorder}`,
    backdropFilter: 'blur(28px)',
    boxShadow: '0 30px 100px rgba(2,6,23,0.30)',
    display: 'grid',
    gridTemplateRows: 'auto minmax(0, 1fr) auto auto'
  }),

  modalHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 22px',
    borderBottom: `1px solid ${p.inputBorder}`
  }),

  modalTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    color: p.text,
    fontSize: 20
  }),

  closeButton: (p: Palette): CSSProperties => ({
    width: 38,
    height: 38,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    display: 'grid',
    placeItems: 'center'
  }),

  modalBody: {
    display: 'grid',
    gap: 16,
    padding: 22
  } as CSSProperties,

  settingsShell: (narrow = false): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : '220px minmax(0, 1fr)',
    gridTemplateRows: narrow ? 'auto minmax(0, 1fr)' : undefined,
    minHeight: 0,
    overflow: 'hidden'
  }),

  settingsRail: (p: Palette, narrow = false): CSSProperties => ({
    display: narrow ? 'flex' : 'grid',
    alignContent: 'start',
    flexWrap: narrow ? 'wrap' : undefined,
    gap: 6,
    padding: narrow ? 12 : 18,
    borderRight: narrow ? 'none' : `1px solid ${p.inputBorder}`,
    borderBottom: narrow ? `1px solid ${p.inputBorder}` : 'none',
    background: p.settingsRail,
    overflowX: narrow ? 'auto' : undefined
  }),

  settingsTabButton: (p: Palette, active: boolean, narrow = false): CSSProperties => ({
    width: narrow ? 'auto' : '100%',
    minHeight: 46,
    flex: narrow ? '1 1 120px' : undefined,
    borderRadius: 10,
    border: 'none',
    background: active ? p.settingsActive : 'transparent',
    color: p.text,
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '0 12px',
    cursor: 'pointer',
    fontWeight: active ? 800 : 650,
    fontSize: 14,
    textAlign: 'left'
  }),

  settingsPane: {
    display: 'grid',
    gap: 16,
    alignContent: 'start',
    padding: 20,
    overflowY: 'auto',
    minHeight: 0,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  settingsSection: (p: Palette): CSSProperties => ({
    borderRadius: 18,
    padding: 18,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(21,26,36,0.70), rgba(17,24,39,0.58))' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    display: 'grid',
    gap: 14,
    boxShadow: '0 14px 36px rgba(2,6,23,0.14), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  settingsHeading: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: p.text
  }),

  fieldLabel: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    fontSize: 13,
    color: p.muted
  }),

  fieldInput: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 44,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.input,
    color: p.text,
    padding: '0 14px',
    outline: 'none',
    fontSize: 14
  }),

  fieldTextarea: (p: Palette): CSSProperties => ({
    width: '100%',
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.input,
    color: p.text,
    padding: '12px 14px',
    outline: 'none',
    fontSize: 14,
    lineHeight: 1.5,
    resize: 'vertical'
  }),

  settingsRow: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) minmax(180px, auto)',
    gap: 12,
    alignItems: 'center',
    padding: '12px 0',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  modalFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 12,
    padding: '0 22px 22px'
  } as CSSProperties,

  primaryButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: 'none',
    background: `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: '0 14px 34px rgba(124,58,237,0.22), inset 0 1px 0 rgba(255,255,255,0.14)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  warningActionButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: 'none',
    background: 'linear-gradient(135deg, #b45309, #d97706)',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: `0 0 0 1px ${p.inputBorder}`
  }),

  secondaryButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: `1px solid ${p.shellBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.56)' : p.shell,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 600,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  iconTextButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: 12,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6
  }),

  saveStatus: (p: Palette): CSSProperties => ({
    padding: '0 22px 22px',
    fontSize: 13,
    color: p.muted
  }),

  inlineStatus: (p: Palette): CSSProperties => ({
    fontSize: 13,
    color: p.muted
  })
};
