import { Component, type CSSProperties, type ReactNode } from 'react';

type LazyPanelBoundaryProps = {
  children: ReactNode;
  title: string;
  detail?: string;
  resetKey?: string | number;
  style?: CSSProperties;
};

type LazyPanelBoundaryState = {
  error: Error | null;
};

export class LazyPanelBoundary extends Component<LazyPanelBoundaryProps, LazyPanelBoundaryState> {
  state: LazyPanelBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): LazyPanelBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(`${this.props.title}: ${error.message}`);
  }

  componentDidUpdate(previousProps: LazyPanelBoundaryProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div role="alert" style={{ ...fallbackStyle, ...this.props.style }}>
        <strong>{this.props.title}</strong>
        <span>{this.props.detail || 'This surface could not load. Retry after the workspace settles.'}</span>
        <button type="button" style={retryButtonStyle} onClick={() => this.setState({ error: null })}>
          Retry
        </button>
      </div>
    );
  }
}

const fallbackStyle: CSSProperties = {
  minHeight: 120,
  display: 'grid',
  alignContent: 'center',
  justifyItems: 'start',
  gap: 10,
  padding: 18,
  borderRadius: 18,
  border: '1px solid rgba(255,255,255,0.08)',
  background:
    'linear-gradient(180deg, rgba(17,24,39,0.84), rgba(8,11,23,0.94)), radial-gradient(circle at top left, rgba(124,58,237,0.18), transparent 46%)',
  color: '#F8FAFC',
  boxShadow: '0 24px 70px rgba(2,6,23,0.34), inset 0 1px 0 rgba(255,255,255,0.05)'
};

const retryButtonStyle: CSSProperties = {
  minHeight: 34,
  padding: '0 14px',
  borderRadius: 999,
  border: '1px solid rgba(124,58,237,0.30)',
  background: 'rgba(124,58,237,0.16)',
  color: '#F8FAFC',
  cursor: 'pointer',
  fontWeight: 800
};
