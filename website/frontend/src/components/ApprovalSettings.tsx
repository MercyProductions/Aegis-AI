// frontend/src/components/ApprovalSettings.tsx
import React, { useState, useEffect } from 'react';
import { Save, X } from 'lucide-react';

import { getApprovalSettings, updateApprovalSettings } from '../api';

interface ApprovalSettingsProps {
  workspaceRoot: string;
  onClose: () => void;
  palette: any;
}

export function ApprovalSettings({ workspaceRoot, onClose, palette }: ApprovalSettingsProps) {
  const [approvalTier, setApprovalTier] = useState('guided');
  const [sandboxProfile, setSandboxProfile] = useState('standard');
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadSettings();
  }, [workspaceRoot]);

  async function loadSettings() {
    try {
      setLoading(true);
      setError('');
      const data = await getApprovalSettings(workspaceRoot);
      setApprovalTier(data.approval_tier);
      setSandboxProfile(data.sandbox_profile);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load approval settings');
    } finally {
      setLoading(false);
    }
  }

  async function saveSettings() {
    try {
      setSaved(false);
      setError('');
      await updateApprovalSettings(workspaceRoot, {
        approval_tier: approvalTier,
        sandbox_profile: sandboxProfile
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to save approval settings');
    }
  }

  const styles = {
    container: {
      position: 'fixed' as const,
      inset: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1001
    },
    modal: {
      background: palette.shell,
      borderRadius: 16,
      border: `1px solid ${palette.shellBorder}`,
      width: '90%',
      maxWidth: 500,
      padding: 24
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 20
    },
    title: {
      fontSize: 20,
      fontWeight: 700,
      color: palette.text
    },
    section: {
      marginBottom: 20
    },
    label: {
      fontSize: 14,
      fontWeight: 600,
      color: palette.text,
      marginBottom: 8,
      display: 'block'
    },
    select: {
      width: '100%',
      padding: '10px 12px',
      borderRadius: 8,
      border: `1px solid ${palette.shellBorder}`,
      background: palette.cardAlt,
      color: palette.text,
      fontSize: 14
    },
    description: {
      fontSize: 12,
      color: palette.muted,
      marginTop: 6,
      marginBottom: 16
    },
    footer: {
      display: 'flex',
      gap: 12,
      marginTop: 24
    },
    button: {
      padding: '10px 16px',
      borderRadius: 8,
      border: 'none',
      background: palette.accent,
      color: '#fff',
      cursor: 'pointer',
      fontSize: 14,
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      flex: 1,
      justifyContent: 'center'
    },
    secondaryButton: {
      background: palette.cardAlt,
      border: `1px solid ${palette.shellBorder}`,
      color: palette.text
    },
    errorMsg: {
      fontSize: 12,
      color: palette.bad,
      marginTop: 12
    },
    successMsg: {
      fontSize: 12,
      color: '#10b981',
      marginTop: 12
    }
  };

  const approvalTierDescriptions = {
    manual: 'Require explicit approval for all command execution',
    prompt: 'Ask for confirmation before running commands',
    guided: 'Suggest safe commands, validate dangerous ones',
    autonomous: 'Execute all approved command patterns automatically'
  };

  const sandboxDescriptions = {
    restricted: 'Minimal filesystem access, no network',
    safe: 'Read-only workspace access, sandboxed network',
    standard: 'Full workspace access with safety checks',
    permissive: 'Unrestricted execution (use with caution)'
  };

  return (
    <div style={styles.container} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <div style={styles.title}>Approval & Sandbox Settings</div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: palette.text }}
          >
            <X size={24} />
          </button>
        </div>

        {loading ? (
          <div style={{ color: palette.muted }}>Loading settings...</div>
        ) : (
          <>
            <div style={styles.section}>
              <label style={styles.label}>Approval Tier</label>
              <select
                value={approvalTier}
                onChange={(e) => setApprovalTier(e.target.value)}
                style={styles.select}
              >
                <option value="manual">Manual Approval</option>
                <option value="prompt">Prompt Before Execution</option>
                <option value="guided">Guided Mode</option>
                <option value="autonomous">Autonomous</option>
              </select>
              <div style={styles.description}>
                {approvalTierDescriptions[approvalTier as keyof typeof approvalTierDescriptions]}
              </div>
            </div>

            <div style={styles.section}>
              <label style={styles.label}>Sandbox Profile</label>
              <select
                value={sandboxProfile}
                onChange={(e) => setSandboxProfile(e.target.value)}
                style={styles.select}
              >
                <option value="restricted">Restricted</option>
                <option value="safe">Safe</option>
                <option value="standard">Standard</option>
                <option value="permissive">Permissive</option>
              </select>
              <div style={styles.description}>
                {sandboxDescriptions[sandboxProfile as keyof typeof sandboxDescriptions]}
              </div>
            </div>

            <div style={styles.footer}>
              <button style={{ ...styles.button, ...styles.secondaryButton }} onClick={onClose}>
                Cancel
              </button>
              <button style={styles.button} onClick={saveSettings}>
                <Save size={16} />
                Save Settings
              </button>
            </div>

            {error ? <div style={styles.errorMsg}>{error}</div> : null}
            {saved ? <div style={styles.successMsg}>Settings saved successfully.</div> : null}
          </>
        )}
      </div>
    </div>
  );
}
