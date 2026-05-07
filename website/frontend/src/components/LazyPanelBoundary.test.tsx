import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { LazyPanelBoundary } from './LazyPanelBoundary';

describe('LazyPanelBoundary', () => {
  it('renders children while the wrapped surface is healthy', () => {
    const boundary = new LazyPanelBoundary({
      title: 'Panel failed',
      children: <span>Healthy panel</span>
    });

    const html = renderToStaticMarkup(boundary.render());

    expect(html).toContain('Healthy panel');
    expect(html).not.toContain('Panel failed');
  });

  it('renders a retryable fallback after an error is captured', () => {
    const boundary = new LazyPanelBoundary({
      title: 'Panel failed',
      detail: 'Try again after telemetry settles.',
      children: <span>Healthy panel</span>
    });
    boundary.state = LazyPanelBoundary.getDerivedStateFromError(new Error('chunk failed'));

    const html = renderToStaticMarkup(boundary.render());

    expect(html).toContain('role="alert"');
    expect(html).toContain('Panel failed');
    expect(html).toContain('Try again after telemetry settles.');
    expect(html).toContain('Retry');
    expect(html).not.toContain('Healthy panel');
  });
});
