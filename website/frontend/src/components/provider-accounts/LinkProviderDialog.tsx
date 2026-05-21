import type { CSSProperties, FormEvent } from 'react';
import { useState } from 'react';
import { KeyRound, Loader2, X } from 'lucide-react';
import type { Palette } from '../../styles/appStyles';
import type { ProviderAccountStatus } from '../../types';

interface LinkProviderDialogProps {
  provider: ProviderAccountStatus;
  palette: Palette;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (apiKey: string, accountLabel: string) => Promise<void>;
}

export function LinkProviderDialog({ provider, palette, busy, error, onClose, onSubmit }: LinkProviderDialogProps) {
  const [apiKey, setApiKey] = useState('');
  const [accountLabel, setAccountLabel] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onSubmit(apiKey, accountLabel);
    setApiKey('');
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <form style={styles.dialog(palette)} onSubmit={submit} onClick={(event) => event.stopPropagation()}>
        <div style={styles.header}>
          <div>
            <div style={styles.title(palette)}>Link {provider.manifest.label}</div>
            <div style={styles.detail(palette)}>Saved to the OS credential vault, not SQLite</div>
          </div>
          <button type="button" style={styles.iconButton(palette)} onClick={onClose} aria-label="Close provider link dialog">
            <X size={16} />
          </button>
        </div>
        <label style={styles.fieldLabel(palette)}>
          <span>Account label</span>
          <input value={accountLabel} onChange={(event) => setAccountLabel(event.target.value)} style={styles.input(palette)} />
        </label>
        <label style={styles.fieldLabel(palette)}>
          <span>API key</span>
          <input
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            type="password"
            autoComplete="off"
            style={styles.input(palette)}
            required
          />
        </label>
        <div style={styles.note(palette)}>
          {provider.manifest.id === 'openai'
            ? 'OpenAI API keys use Platform billing. Codex subscription-style usage should be linked with the CLI login flow.'
            : 'Provider API keys are injected only into the selected provider process when a bridge run starts.'}
        </div>
        {error ? <div style={styles.error(palette)}>{error}</div> : null}
        <div style={styles.actions}>
          <button type="button" style={styles.secondaryButton(palette)} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" style={styles.primaryButton(palette)} disabled={busy || !apiKey.trim()}>
            {busy ? <Loader2 size={16} className="spin" /> : <KeyRound size={16} />}
            Link key
          </button>
        </div>
      </form>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 40,
    display: 'grid',
    placeItems: 'center',
    padding: 20,
    background: 'rgba(2,6,23,0.48)'
  } as CSSProperties,
  dialog: (palette: Palette): CSSProperties => ({
    width: 'min(440px, 100%)',
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.card,
    color: palette.text,
    padding: 18,
    boxShadow: '0 24px 80px rgba(2,6,23,0.28)'
  }),
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 16
  } as CSSProperties,
  title: (palette: Palette): CSSProperties => ({ color: palette.text, fontSize: 16, fontWeight: 900 }),
  detail: (palette: Palette): CSSProperties => ({ color: palette.muted, fontSize: 12, marginTop: 3 }),
  fieldLabel: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    color: palette.textSoft,
    fontSize: 12,
    fontWeight: 800,
    marginBottom: 12
  }),
  input: (palette: Palette): CSSProperties => ({
    width: '100%',
    minHeight: 38,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    color: palette.text,
    padding: '8px 10px',
    boxSizing: 'border-box'
  }),
  error: (palette: Palette): CSSProperties => ({
    color: palette.bad,
    fontSize: 12,
    fontWeight: 800,
    marginBottom: 12
  }),
  note: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 12,
    lineHeight: 1.45,
    marginBottom: 12
  }),
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,
  iconButton: (palette: Palette): CSSProperties => ({
    width: 32,
    height: 32,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),
  primaryButton: (palette: Palette): CSSProperties => ({
    minHeight: 36,
    borderRadius: 8,
    border: `1px solid ${palette.accent}`,
    background: palette.accent,
    color: '#fff',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '0 12px',
    fontWeight: 900,
    cursor: 'pointer'
  }),
  secondaryButton: (palette: Palette): CSSProperties => ({
    minHeight: 36,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.text,
    padding: '0 12px',
    fontWeight: 800,
    cursor: 'pointer'
  })
};
