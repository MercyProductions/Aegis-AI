import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { AppHeader } from './AppHeader';
import { getPalette } from '../../styles/appStyles';

describe('AppHeader', () => {
  it('renders search, runtime status, model switcher, and account controls', () => {
    const html = renderToStaticMarkup(
      <AppHeader
        palette={getPalette(false)}
        compactLayout={false}
        narrowLayout={false}
        productName="Auralith"
        searchValue="diagnostics"
        onSearchChange={() => undefined}
        connectionLabel="Connected"
        connectionConnected
        modelSwitcher={<button type="button">Model switcher</button>}
        isDarkMode={false}
        onToggleDarkMode={() => undefined}
        onOpenMemory={() => undefined}
        onOpenApprovals={() => undefined}
        onOpenSettings={() => undefined}
        accountName="Auralith User"
        accountPlan="Local Plan"
        onLogout={() => undefined}
      />
    );

    expect(html).toContain('Search Auralith... (Ctrl + K)');
    expect(html).toContain('diagnostics');
    expect(html).toContain('Connected');
    expect(html).toContain('Model switcher');
    expect(html).toContain('Auralith User');
    expect(html).toContain('Local Plan');
    expect(html).toContain('Memory Editor');
    expect(html).toContain('Approval Settings');
  });
});
