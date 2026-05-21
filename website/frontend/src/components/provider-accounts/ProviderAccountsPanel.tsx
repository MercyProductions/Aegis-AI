import type { CSSProperties, FormEvent, KeyboardEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Eye, FolderOpen, KeyRound, Loader2, Plus, RefreshCw, RotateCcw, Search, Send, ShieldCheck, Square, Terminal, Trash2, X } from 'lucide-react';
import {
  cancelAgentBridgeJob,
  cancelProviderSourceRefreshJob,
  getAgentBridgeJob,
  getProviderSourceRefreshJob,
  getProviderAccounts,
  listFiles,
  listAgentBridgeJobs,
  listProviderSourceRefreshJobs,
  linkProviderApiKey,
  linkProviderCliSession,
  openProviderSourceRoot,
  preflightAgentBridge,
  probeProviderCliBridges,
  retryAgentBridgeJob,
  retryProviderSourceRefreshJob,
  startAgentBridgeJob,
  startProviderSourceRefreshJob,
  startProviderCliLogin,
  unlinkProviderAccount
} from '../../api';
import type { Palette } from '../../styles/appStyles';
import type {
  AgentBridgeExecuteRequest,
  AgentBridgePreflightResponse,
  AgentBridgeJobInfo,
  Mode,
  ProviderAccountsResponse,
  ProviderAccountStatus,
  ProviderSourceDropInfo,
  ProviderSourceRefreshJobInfo,
  ProviderSourceRootInfo,
  WorkspaceFile
} from '../../types';
import { clearProviderBridgeDraft, loadProviderBridgeDraft, saveProviderBridgeDraft } from '../../utils/appStorage';
import { filterWorkspaceFiles } from '../../utils/workspaceFiles';
import { LinkProviderDialog } from './LinkProviderDialog';
import { ModelLimitSummary } from './ModelLimitSummary';
import { ProviderRouteReadiness } from './ProviderRouteReadiness';
import { ProviderStatusBadge } from './ProviderStatusBadge';

interface ProviderAccountsPanelProps {
  palette: Palette;
  workspaceRoot?: string;
}

const BRIDGE_RUN_MODE_OPTIONS: Array<{ value: Mode; label: string }> = [
  { value: 'build', label: 'Build' },
  { value: 'develop', label: 'Develop' },
  { value: 'review', label: 'Review' },
  { value: 'chat', label: 'Chat' }
];
const BRIDGE_CONTEXT_FILE_LIMIT = 500;
const BRIDGE_RUN_PROFILE_OPTIONS = [
  {
    id: 'plan',
    label: 'Plan',
    mode: 'develop' as Mode,
    allowEdits: false,
    timeoutSeconds: 180,
    prompt: 'Plan the next implementation step from the pinned context. Return the key risks and the smallest useful change.'
  },
  {
    id: 'build',
    label: 'Build',
    mode: 'build' as Mode,
    allowEdits: true,
    timeoutSeconds: 360,
    prompt: 'Implement the requested change using the pinned context. Keep edits scoped and report verification steps.'
  },
  {
    id: 'review',
    label: 'Review',
    mode: 'review' as Mode,
    allowEdits: false,
    timeoutSeconds: 240,
    prompt: 'Review the pinned context for bugs, regressions, missing tests, and launch risks. Do not edit files.'
  },
  {
    id: 'chat',
    label: 'Chat',
    mode: 'chat' as Mode,
    allowEdits: false,
    timeoutSeconds: 120,
    prompt: 'Answer using the pinned context and call out any assumptions.'
  }
] as const;

export function ProviderAccountsPanel({ palette, workspaceRoot = '' }: ProviderAccountsPanelProps) {
  const [snapshot, setSnapshot] = useState<ProviderAccountsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyProvider, setBusyProvider] = useState('');
  const [busySourceRoot, setBusySourceRoot] = useState('');
  const [busySourceRefresh, setBusySourceRefresh] = useState('');
  const [busySourceJob, setBusySourceJob] = useState('');
  const [bridgeJobs, setBridgeJobs] = useState<AgentBridgeJobInfo[]>([]);
  const [bridgeJobsLoading, setBridgeJobsLoading] = useState(false);
  const [busyBridgeJob, setBusyBridgeJob] = useState('');
  const [selectedRefreshJobId, setSelectedRefreshJobId] = useState('');
  const [selectedBridgeJobId, setSelectedBridgeJobId] = useState('');
  const [dialogProvider, setDialogProvider] = useState<ProviderAccountStatus | null>(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const providers = snapshot?.providers ?? [];
  const linkedCount = useMemo(
    () => providers.filter((provider) => provider.execution_ready).length,
    [providers]
  );
  const activeRefreshJobIds = useMemo(
    () =>
      (snapshot?.source_refresh_jobs ?? [])
        .filter((job) => !sourceRefreshJobTerminal(job.status))
        .map((job) => job.id)
        .join('|'),
    [snapshot?.source_refresh_jobs]
  );
  const activeBridgeJobIds = useMemo(
    () =>
      bridgeJobs
        .filter((job) => !agentBridgeJobTerminal(job.status))
        .map((job) => job.id)
        .join('|'),
    [bridgeJobs]
  );

  useEffect(() => {
    void refresh();
    void refreshBridgeJobs(true);
  }, []);

  useEffect(() => {
    if (!activeRefreshJobIds) return;
    let canceled = false;
    const poll = async () => {
      try {
        const response = await listProviderSourceRefreshJobs(8);
        if (canceled) return;
        if (response.snapshot) {
          setSnapshot(response.snapshot);
        } else {
          setSnapshot((current) => (current ? { ...current, source_refresh_jobs: response.jobs } : current));
        }
      } catch {
        // Polling is best-effort; the manual Refresh button remains available.
      }
    };
    const timer = window.setInterval(() => void poll(), 2500);
    void poll();
    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [activeRefreshJobIds]);

  useEffect(() => {
    if (!activeBridgeJobIds) return;
    let canceled = false;
    const poll = async () => {
      try {
        const response = await listAgentBridgeJobs(8);
        if (!canceled) setBridgeJobs(response.jobs);
      } catch {
        // Polling is best-effort; the manual Refresh button remains available.
      }
    };
    const timer = window.setInterval(() => void poll(), 2500);
    void poll();
    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [activeBridgeJobIds]);

  async function refresh() {
    setLoading(true);
    setError('');
    setStatus('');
    try {
      setSnapshot(await getProviderAccounts());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider accounts could not load.');
    } finally {
      setLoading(false);
    }
  }

  async function refreshBridgeJobs(quiet = false) {
    if (!quiet) setBridgeJobsLoading(true);
    setError('');
    try {
      const response = await listAgentBridgeJobs(8);
      setBridgeJobs(response.jobs);
    } catch (err) {
      if (!quiet) setError(err instanceof Error ? err.message : 'Provider execution jobs could not load.');
    } finally {
      if (!quiet) setBridgeJobsLoading(false);
    }
  }

  async function probe(providerId = '') {
    setBusyProvider(providerId || '__all__');
    setError('');
    setStatus('');
    try {
      setSnapshot(await probeProviderCliBridges(providerId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'CLI bridge probe failed.');
    } finally {
      setBusyProvider('');
    }
  }

  async function linkApiKey(provider: ProviderAccountStatus, apiKey: string, accountLabel: string) {
    setBusyProvider(provider.manifest.id);
    setError('');
    setStatus('');
    try {
      const response = await linkProviderApiKey(provider.manifest.id, { api_key: apiKey, account_label: accountLabel });
      setSnapshot(response.snapshot);
      setDialogProvider(null);
      setStatus(`${provider.manifest.label} API key linked in the OS credential vault.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider API key could not be linked.');
    } finally {
      setBusyProvider('');
    }
  }

  async function unlink(provider: ProviderAccountStatus) {
    setBusyProvider(provider.manifest.id);
    setError('');
    setStatus('');
    try {
      setSnapshot(await unlinkProviderAccount(provider.manifest.id));
      setStatus(`${provider.manifest.label} account link removed.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider account could not be removed.');
    } finally {
      setBusyProvider('');
    }
  }

  async function openCliLogin(provider: ProviderAccountStatus) {
    setBusyProvider(provider.manifest.id);
    setError('');
    setStatus('');
    try {
      const response = await startProviderCliLogin(provider.manifest.id);
      if (response.snapshot) setSnapshot(response.snapshot);
      if (!response.ok) {
        setError(response.message || `${provider.manifest.label} CLI login could not be opened.`);
      } else {
        setStatus(response.message || `${provider.manifest.label} login opened.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider CLI login could not be opened.');
    } finally {
      setBusyProvider('');
    }
  }

  async function reuseCliSession(provider: ProviderAccountStatus) {
    setBusyProvider(provider.manifest.id);
    setError('');
    setStatus('');
    try {
      const response = await linkProviderCliSession(provider.manifest.id);
      setSnapshot(response.snapshot);
      const statusLabel = response.account.status === 'limited' ? 'registered with runtime verification' : 'linked';
      setStatus(`${provider.manifest.label} CLI session ${statusLabel}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider CLI session could not be reused.');
    } finally {
      setBusyProvider('');
    }
  }

  async function openSourceRoot(path = '') {
    setBusySourceRoot(path || '__default__');
    setError('');
    setStatus('');
    try {
      const response = await openProviderSourceRoot({ path });
      if (response.snapshot) setSnapshot(response.snapshot);
      if (!response.ok) {
        setError(response.message || 'Provider source root could not be opened.');
      } else {
        setStatus(response.message || 'Provider source root opened.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider source root could not be opened.');
    } finally {
      setBusySourceRoot('');
    }
  }

  async function refreshSourceDrop(drop: ProviderSourceDropInfo, actionId: string) {
    const key = sourceRefreshKey(drop, actionId);
    setBusySourceRefresh(key);
    setError('');
    setStatus('');
    try {
      const response = await startProviderSourceRefreshJob({
        provider_id: drop.provider_id,
        action_id: actionId,
        source_root: drop.source_root,
        source_candidate: drop.source_candidate
      });
      if (response.snapshot) setSnapshot(response.snapshot);
      setSelectedRefreshJobId(response.job.id);
      setStatus(`${response.job.action_label || drop.provider_label} queued as ${response.job.id}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${drop.provider_label} source refresh failed.`);
    } finally {
      setBusySourceRefresh('');
    }
  }

  async function selectSourceJob(job: ProviderSourceRefreshJobInfo) {
    setSelectedRefreshJobId(job.id);
    setBusySourceJob(`${job.id}:details`);
    setError('');
    try {
      const response = await getProviderSourceRefreshJob(job.id);
      if (response.snapshot) {
        setSnapshot(response.snapshot);
      } else {
        setSnapshot((current) => (current ? { ...current, source_refresh_jobs: mergeSourceRefreshJob(current.source_refresh_jobs, response.job) } : current));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider source refresh job could not load.');
    } finally {
      setBusySourceJob('');
    }
  }

  async function cancelSourceJob(job: ProviderSourceRefreshJobInfo) {
    setBusySourceJob(`${job.id}:cancel`);
    setError('');
    setStatus('');
    try {
      const response = await cancelProviderSourceRefreshJob(job.id);
      if (response.snapshot) {
        setSnapshot(response.snapshot);
      } else {
        setSnapshot((current) => (current ? { ...current, source_refresh_jobs: mergeSourceRefreshJob(current.source_refresh_jobs, response.job) } : current));
      }
      setSelectedRefreshJobId(response.job.id);
      setStatus(response.job.message || `${job.action_label || 'Source refresh'} cancel requested.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider source refresh job could not be canceled.');
    } finally {
      setBusySourceJob('');
    }
  }

  async function retrySourceJob(job: ProviderSourceRefreshJobInfo) {
    setBusySourceJob(`${job.id}:retry`);
    setError('');
    setStatus('');
    try {
      const response = await retryProviderSourceRefreshJob(job.id);
      if (response.snapshot) {
        setSnapshot(response.snapshot);
      } else {
        setSnapshot((current) => (current ? { ...current, source_refresh_jobs: mergeSourceRefreshJob(current.source_refresh_jobs, response.job) } : current));
      }
      setSelectedRefreshJobId(response.job.id);
      setStatus(`${response.job.action_label || 'Source refresh'} queued as ${response.job.id}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider source refresh job could not be retried.');
    } finally {
      setBusySourceJob('');
    }
  }

  async function selectBridgeJob(job: AgentBridgeJobInfo) {
    setSelectedBridgeJobId(job.id);
    setBusyBridgeJob(`${job.id}:details`);
    setError('');
    try {
      const response = await getAgentBridgeJob(job.id);
      setBridgeJobs((current) => mergeAgentBridgeJob(current, response.job));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider execution job could not load.');
    } finally {
      setBusyBridgeJob('');
    }
  }

  async function cancelBridgeJob(job: AgentBridgeJobInfo) {
    setBusyBridgeJob(`${job.id}:cancel`);
    setError('');
    setStatus('');
    try {
      const response = await cancelAgentBridgeJob(job.id);
      setBridgeJobs((current) => mergeAgentBridgeJob(current, response.job));
      setSelectedBridgeJobId(response.job.id);
      setStatus(response.job.message || `${job.provider_label || 'Provider'} bridge cancel requested.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider execution job could not be canceled.');
    } finally {
      setBusyBridgeJob('');
    }
  }

  async function retryBridgeJob(job: AgentBridgeJobInfo) {
    setBusyBridgeJob(`${job.id}:retry`);
    setError('');
    setStatus('');
    try {
      const response = await retryAgentBridgeJob(job.id);
      setBridgeJobs((current) => mergeAgentBridgeJob(current, response.job));
      setSelectedBridgeJobId(response.job.id);
      setStatus(`${response.job.provider_label || 'Provider'} bridge queued as ${response.job.id}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider execution job could not be retried.');
    } finally {
      setBusyBridgeJob('');
    }
  }

  async function startBridgeRun(request: AgentBridgeExecuteRequest) {
    setBusyBridgeJob('__launch__');
    setError('');
    setStatus('');
    try {
      const response = await startAgentBridgeJob(request);
      setBridgeJobs((current) => mergeAgentBridgeJob(current, response.job));
      setSelectedBridgeJobId(response.job.id);
      setStatus(`${response.job.provider_label || 'Provider'} bridge queued as ${response.job.id}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider execution job could not be queued.');
    } finally {
      setBusyBridgeJob('');
    }
  }

  const sourceRoots = snapshot?.source_roots ?? [];
  const sourceDrops = snapshot?.source_drops ?? [];
  const sourceRefreshJobs = snapshot?.source_refresh_jobs ?? [];
  const selectedRefreshJob = sourceRefreshJobs.find((job) => job.id === selectedRefreshJobId) ?? null;
  const selectedBridgeJob = bridgeJobs.find((job) => job.id === selectedBridgeJobId) ?? null;

  return (
    <section style={styles.panel(palette)}>
      <div style={styles.header}>
        <div>
          <h4 style={styles.heading(palette)}>Provider Accounts</h4>
          <div style={styles.detail(palette)}>
            {linkedCount} ready / {providers.length || 0} providers
          </div>
        </div>
        <div style={styles.actions}>
          <button type="button" style={styles.iconTextButton(palette)} onClick={() => void probe()} disabled={Boolean(busyProvider)}>
            {busyProvider === '__all__' ? <Loader2 size={14} className="spin" /> : <Terminal size={14} />}
            Probe CLIs
          </button>
          <button
            type="button"
            style={styles.iconTextButton(palette)}
            onClick={() => {
              void refresh();
              void refreshBridgeJobs();
            }}
            disabled={loading || bridgeJobsLoading}
          >
            {loading ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
            Refresh
          </button>
        </div>
      </div>

      {error ? <div style={styles.error(palette)}>{error}</div> : null}
      {status ? <div style={styles.status(palette)}>{status}</div> : null}
      {snapshot ? (
        <div style={styles.vaultRow(palette)}>
          <ShieldCheck size={14} />
          <span>{snapshot.credential_store_available ? 'Credential vault available' : 'Credential vault unavailable'}</span>
        </div>
      ) : null}

      {snapshot ? (
        <SourceDropPanel
          palette={palette}
          roots={sourceRoots}
          drops={sourceDrops}
          jobs={sourceRefreshJobs}
          busyRoot={busySourceRoot}
          busyProbe={busyProvider === '__all__'}
          busyRefresh={busySourceRefresh}
          busyJob={busySourceJob}
          selectedJob={selectedRefreshJob}
          onOpenRoot={(path) => void openSourceRoot(path)}
          onProbe={() => void probe()}
          onRefresh={(drop, actionId) => void refreshSourceDrop(drop, actionId)}
          onSelectJob={(job) => void selectSourceJob(job)}
          onCancelJob={(job) => void cancelSourceJob(job)}
          onRetryJob={(job) => void retrySourceJob(job)}
          onCloseJob={() => setSelectedRefreshJobId('')}
        />
      ) : null}

      {snapshot ? (
        <AgentBridgeJobPanel
          palette={palette}
          defaultWorkspaceRoot={workspaceRoot}
          providers={providers}
          jobs={bridgeJobs}
          loading={bridgeJobsLoading}
          busyJob={busyBridgeJob}
          selectedJob={selectedBridgeJob}
          onRefresh={() => void refreshBridgeJobs()}
          onStartRun={(request) => void startBridgeRun(request)}
          onSelectJob={(job) => void selectBridgeJob(job)}
          onCancelJob={(job) => void cancelBridgeJob(job)}
          onRetryJob={(job) => void retryBridgeJob(job)}
          onCloseJob={() => setSelectedBridgeJobId('')}
        />
      ) : null}

      <div style={styles.providerGrid}>
        {providers.map((provider) => (
          <ProviderRow
            key={provider.manifest.id}
            provider={provider}
            palette={palette}
            busy={busyProvider === provider.manifest.id}
            vaultAvailable={Boolean(snapshot?.credential_store_available)}
            onLink={() => setDialogProvider(provider)}
            onUnlink={() => void unlink(provider)}
            onProbe={() => void probe(provider.manifest.id)}
            onCliLogin={() => void openCliLogin(provider)}
            onCliSession={() => void reuseCliSession(provider)}
          />
        ))}
        {!providers.length && !loading ? <div style={styles.empty(palette)}>Provider accounts are not loaded yet.</div> : null}
      </div>

      {dialogProvider ? (
        <LinkProviderDialog
          provider={dialogProvider}
          palette={palette}
          busy={busyProvider === dialogProvider.manifest.id}
          error={error}
          onClose={() => setDialogProvider(null)}
          onSubmit={(apiKey, accountLabel) => linkApiKey(dialogProvider, apiKey, accountLabel)}
        />
      ) : null}
    </section>
  );
}

interface SourceDropPanelProps {
  palette: Palette;
  roots: ProviderSourceRootInfo[];
  drops: ProviderSourceDropInfo[];
  jobs: ProviderSourceRefreshJobInfo[];
  busyRoot: string;
  busyProbe: boolean;
  busyRefresh: string;
  busyJob: string;
  selectedJob: ProviderSourceRefreshJobInfo | null;
  onOpenRoot: (path: string) => void;
  onProbe: () => void;
  onRefresh: (drop: ProviderSourceDropInfo, actionId: string) => void;
  onSelectJob: (job: ProviderSourceRefreshJobInfo) => void;
  onCancelJob: (job: ProviderSourceRefreshJobInfo) => void;
  onRetryJob: (job: ProviderSourceRefreshJobInfo) => void;
  onCloseJob: () => void;
}

function SourceDropPanel({
  palette,
  roots,
  drops,
  jobs,
  busyRoot,
  busyProbe,
  busyRefresh,
  busyJob,
  selectedJob,
  onOpenRoot,
  onProbe,
  onRefresh,
  onSelectJob,
  onCancelJob,
  onRetryJob,
  onCloseJob
}: SourceDropPanelProps) {
  const visibleRoots = roots.some((root) => root.exists) ? roots.filter((root) => root.exists) : roots;
  const defaultRoot = visibleRoots[0];
  const visibleJobs = jobs.slice(0, 4);
  return (
    <div style={styles.sourcePanel(palette)}>
      <div style={styles.sourceHeader}>
        <div>
          <div style={styles.sourceTitle(palette)}>Provider Source Drops</div>
          <div style={styles.detail(palette)}>
            {drops.length} detected / {visibleRoots.length} root{visibleRoots.length === 1 ? '' : 's'}
          </div>
        </div>
        <div style={styles.actions}>
          <button
            type="button"
            style={styles.iconTextButton(palette)}
            onClick={() => defaultRoot && onOpenRoot(defaultRoot.path)}
            disabled={!defaultRoot || Boolean(busyRoot)}
          >
            {busyRoot ? <Loader2 size={14} className="spin" /> : <FolderOpen size={14} />}
            Open folder
          </button>
          <button type="button" style={styles.iconTextButton(palette)} onClick={onProbe} disabled={busyProbe}>
            {busyProbe ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
            Rescan
          </button>
        </div>
      </div>

      {visibleRoots.length ? (
        <div style={styles.sourceRootGrid}>
          {visibleRoots.map((root) => (
            <button
              type="button"
              key={root.path}
              style={styles.sourceRootButton(palette)}
              onClick={() => onOpenRoot(root.path)}
              disabled={Boolean(busyRoot)}
              title={root.path}
            >
              <span style={styles.sourceRootTop}>
                <SourceFreshnessBadge palette={palette} freshness={root.freshness} label={root.freshness_label || (root.exists ? 'Ready' : 'Missing')} />
              </span>
              <span style={styles.sourcePath(palette)}>{root.path}</span>
              <span style={styles.sourceMeta(palette)}>
                {root.provider_labels.join(', ') || 'No providers'} / {root.child_count} item{root.child_count === 1 ? '' : 's'}
              </span>
              {root.freshness_detail ? <span style={styles.sourceMeta(palette)}>{root.freshness_detail}</span> : null}
            </button>
          ))}
        </div>
      ) : (
        <div style={styles.empty(palette)}>No source roots are declared by provider manifests.</div>
      )}

      {visibleJobs.length ? (
        <div style={styles.sourceJobList}>
          {visibleJobs.map((job) => {
            const terminal = sourceRefreshJobTerminal(job.status);
            return (
              <div key={job.id} style={styles.sourceJobRow(palette, terminal)}>
                <div style={styles.sourceJobMain}>
                  <span style={styles.sourceDropProvider(palette)}>{job.action_label || job.provider_label}</span>
                  <span style={styles.sourceMeta(palette)}>{job.message || job.id}</span>
                </div>
                <div style={styles.sourceJobActions}>
                  <span style={styles.sourceDropStatus(palette, job.status)}>{sourceRefreshJobLabel(job.status)}</span>
                  <button type="button" style={styles.sourceActionButton(palette)} onClick={() => onSelectJob(job)} disabled={busyJob === `${job.id}:details`}>
                    {busyJob === `${job.id}:details` ? <Loader2 size={13} className="spin" /> : <Eye size={13} />}
                    Details
                  </button>
                  {terminal ? (
                    <button type="button" style={styles.sourceActionButton(palette)} onClick={() => onRetryJob(job)} disabled={Boolean(busyJob)}>
                      {busyJob === `${job.id}:retry` ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />}
                      Retry
                    </button>
                  ) : (
                    <button type="button" style={styles.sourceDangerActionButton(palette)} onClick={() => onCancelJob(job)} disabled={Boolean(busyJob)}>
                      {busyJob === `${job.id}:cancel` ? <Loader2 size={13} className="spin" /> : <Square size={13} />}
                      Stop
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      {selectedJob ? (
        <SourceRefreshJobDetail
          palette={palette}
          job={selectedJob}
          busyJob={busyJob}
          onClose={onCloseJob}
          onCancel={() => onCancelJob(selectedJob)}
          onRetry={() => onRetryJob(selectedJob)}
        />
      ) : null}

      {drops.length ? (
        <div style={styles.sourceDropGrid}>
          {drops.map((drop) => (
            <div key={`${drop.provider_id}-${drop.detected_from}-${drop.display}-${drop.cwd}`} style={styles.sourceDropRow(palette)}>
              <div style={styles.sourceDropTop}>
                <span style={styles.sourceDropProvider(palette)}>{drop.provider_label}</span>
                <span style={styles.sourceDropBadges}>
                  <SourceFreshnessBadge palette={palette} freshness={drop.freshness} label={drop.freshness_label || 'Detected'} />
                  <span style={styles.sourceDropStatus(palette, drop.status)}>{drop.status}</span>
                </span>
              </div>
              <div style={styles.sourcePath(palette)}>{drop.display || drop.path}</div>
              <div style={styles.sourceMeta(palette)}>
                {[drop.detected_from.replace('_', ' '), drop.version, drop.auth_status].filter(Boolean).join(' / ')}
              </div>
              {drop.freshness_detail ? <div style={styles.sourceMeta(palette)}>{drop.freshness_detail}</div> : null}
              {(drop.refresh_actions ?? []).length ? (
                <div style={styles.sourceActionRow}>
                  {(drop.refresh_actions ?? []).slice(0, 2).map((action) => {
                    const key = sourceRefreshKey(drop, action.id);
                    const activeJob = sourceRefreshJobForAction(jobs, drop, action.id);
                    const busy = busyRefresh === key || Boolean(activeJob);
                    return (
                      <button
                        type="button"
                        key={`${drop.provider_id}-${action.id}`}
                        style={styles.sourceActionButton(palette)}
                        onClick={() => onRefresh(drop, action.id)}
                        disabled={Boolean(busyRefresh) || Boolean(activeJob) || !action.available}
                        title={action.detail || action.command}
                      >
                        {busy ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
                        {activeJob ? sourceRefreshJobLabel(activeJob.status) : action.label || 'Refresh source'}
                      </button>
                    );
                  })}
                </div>
              ) : null}
              {drop.last_error ? <div style={styles.sourceError(palette)}>{drop.last_error}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

interface AgentBridgeJobPanelProps {
  palette: Palette;
  defaultWorkspaceRoot: string;
  providers: ProviderAccountStatus[];
  jobs: AgentBridgeJobInfo[];
  loading: boolean;
  busyJob: string;
  selectedJob: AgentBridgeJobInfo | null;
  onRefresh: () => void;
  onStartRun: (request: AgentBridgeExecuteRequest) => void;
  onSelectJob: (job: AgentBridgeJobInfo) => void;
  onCancelJob: (job: AgentBridgeJobInfo) => void;
  onRetryJob: (job: AgentBridgeJobInfo) => void;
  onCloseJob: () => void;
}

function AgentBridgeJobPanel({
  palette,
  defaultWorkspaceRoot,
  providers,
  jobs,
  loading,
  busyJob,
  selectedJob,
  onRefresh,
  onStartRun,
  onSelectJob,
  onCancelJob,
  onRetryJob,
  onCloseJob
}: AgentBridgeJobPanelProps) {
  const providerOptions = useMemo(() => {
    const runnable = providers.filter(
      (provider) => provider.execution_ready || provider.manifest.kind === 'local' || Boolean(provider.cli_bridge?.binary_path)
    );
    const options = runnable.length ? runnable : providers;
    return [...options].sort((left, right) => {
      const leftReady = left.execution_ready ? 1 : 0;
      const rightReady = right.execution_ready ? 1 : 0;
      if (leftReady !== rightReady) return rightReady - leftReady;
      return left.manifest.label.localeCompare(right.manifest.label);
    });
  }, [providers]);
  const [providerId, setProviderId] = useState('');
  const [runMode, setRunMode] = useState<Mode>('build');
  const [model, setModel] = useState('');
  const [workspaceRoot, setWorkspaceRoot] = useState(defaultWorkspaceRoot);
  const [message, setMessage] = useState('');
  const [contextDraft, setContextDraft] = useState('');
  const [contextPaths, setContextPaths] = useState<string[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const [workspaceFilesRoot, setWorkspaceFilesRoot] = useState('');
  const [workspaceFilesLoading, setWorkspaceFilesLoading] = useState(false);
  const [workspaceFilesError, setWorkspaceFilesError] = useState('');
  const [contextPickerOpen, setContextPickerOpen] = useState(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState(240);
  const [allowEdits, setAllowEdits] = useState(false);
  const [preflight, setPreflight] = useState<AgentBridgePreflightResponse | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState('');
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [draftNotice, setDraftNotice] = useState('');
  const suppressNextDraftSaveRef = useRef(false);
  const visibleJobs = jobs.slice(0, 5);
  const selectedProvider = providerOptions.find((provider) => provider.manifest.id === providerId);
  const contextKey = contextPaths.join('|');
  const draftStorageRoot = defaultWorkspaceRoot || workspaceRoot;
  const preflightReady = Boolean(preflight?.ok && preflight.preflight_signature);
  const canQueue = Boolean(providerId && message.trim() && preflightReady && !busyJob && !preflightLoading);
  const canPreflight = Boolean(providerId && message.trim() && !busyJob && !preflightLoading);
  const canAddContext = Boolean(contextDraft.trim()) && contextPaths.length < 50;
  const visibleWorkspaceFiles = useMemo(
    () =>
      filterWorkspaceFiles(workspaceFiles, contextDraft)
        .filter((file) => !contextPaths.includes(file.path))
        .slice(0, 8),
    [contextDraft, contextPaths, workspaceFiles]
  );
  const launchGuardMessage = preflightReady
    ? 'Reviewed route is ready. Queueing will use this exact preflight snapshot.'
    : 'Run Preflight to review the route before queueing.';

  useEffect(() => {
    if (!providerOptions.length) return;
    if (providerId && providerOptions.some((provider) => provider.manifest.id === providerId)) return;
    setProviderId(providerOptions[0]?.manifest.id ?? '');
  }, [providerId, providerOptions]);

  useEffect(() => {
    setDraftLoaded(false);
    const directDraft = loadProviderBridgeDraft(defaultWorkspaceRoot);
    const fallbackDraft = defaultWorkspaceRoot ? loadProviderBridgeDraft('') : null;
    const draft = directDraft || fallbackDraft;
    if (defaultWorkspaceRoot && fallbackDraft && !directDraft) {
      clearProviderBridgeDraft('');
    }
    setProviderId(draft?.providerId || providerOptions[0]?.manifest.id || '');
    setRunMode(draft?.mode || 'build');
    setModel(draft?.model || '');
    setWorkspaceRoot(draft?.workspaceRoot || defaultWorkspaceRoot);
    setMessage(draft?.message || '');
    setContextDraft('');
    setContextPaths(draft?.contextPaths || []);
    setTimeoutSeconds(draft?.timeoutSeconds || 240);
    setAllowEdits(Boolean(draft?.allowEdits));
    setPreflight(null);
    setPreflightError('');
    setContextPickerOpen(false);
    setDraftNotice(draft ? `Draft restored from ${formatBridgeDraftTime(draft.updatedAt)}.` : 'Draft autosaves locally for this workspace.');
    setDraftLoaded(true);
  }, [defaultWorkspaceRoot]);

  useEffect(() => {
    if (!draftLoaded) return;
    if (suppressNextDraftSaveRef.current) {
      suppressNextDraftSaveRef.current = false;
      return;
    }
    const draft = {
      providerId,
      mode: runMode,
      model,
      workspaceRoot,
      message,
      contextPaths,
      timeoutSeconds,
      allowEdits
    };
    saveProviderBridgeDraft(draftStorageRoot, draft);
    if (!defaultWorkspaceRoot && draftStorageRoot) {
      saveProviderBridgeDraft('', draft);
    }
  }, [allowEdits, contextKey, defaultWorkspaceRoot, draftLoaded, draftStorageRoot, message, model, providerId, runMode, timeoutSeconds, workspaceRoot]);

  useEffect(() => {
    setPreflight(null);
    setPreflightError('');
  }, [allowEdits, contextKey, message, model, providerId, runMode, timeoutSeconds, workspaceRoot]);

  useEffect(() => {
    setWorkspaceFiles([]);
    setWorkspaceFilesRoot('');
    setWorkspaceFilesError('');
  }, [workspaceRoot]);

  function applyRunProfile(profileId: (typeof BRIDGE_RUN_PROFILE_OPTIONS)[number]['id']) {
    const profile = BRIDGE_RUN_PROFILE_OPTIONS.find((item) => item.id === profileId);
    if (!profile) return;
    setRunMode(profile.mode);
    setAllowEdits(profile.allowEdits);
    setTimeoutSeconds(profile.timeoutSeconds);
    setMessage((current) => (current.trim() ? current : profile.prompt));
  }

  function resetBridgeDraft() {
    suppressNextDraftSaveRef.current = true;
    clearProviderBridgeDraft(draftStorageRoot);
    if (draftStorageRoot) {
      clearProviderBridgeDraft('');
    }
    setProviderId(providerOptions[0]?.manifest.id ?? '');
    setRunMode('build');
    setModel('');
    setWorkspaceRoot(defaultWorkspaceRoot);
    setMessage('');
    setContextDraft('');
    setContextPaths([]);
    setWorkspaceFiles([]);
    setWorkspaceFilesRoot('');
    setWorkspaceFilesError('');
    setContextPickerOpen(false);
    setTimeoutSeconds(240);
    setAllowEdits(false);
    setPreflight(null);
    setPreflightError('');
    setDraftNotice('Draft reset.');
  }

  function bridgeRunRequest(): AgentBridgeExecuteRequest {
    return {
      provider_id: providerId,
      message: message.trim(),
      workspace_root: workspaceRoot.trim() || undefined,
      mode: runMode,
      model: model.trim(),
      allow_edits: allowEdits,
      timeout_seconds: timeoutSeconds,
      context_paths: contextPaths,
      preflight_signature: preflight?.preflight_signature || undefined
    };
  }

  function addContextPaths(raw = contextDraft) {
    const next = mergeBridgeContextPaths(contextPaths, raw);
    setContextPaths(next);
    setContextDraft('');
  }

  function removeContextPath(path: string) {
    setContextPaths((current) => current.filter((item) => item !== path));
  }

  function addContextFile(path: string) {
    setContextPaths((current) => mergeBridgeContextPaths(current, path));
  }

  function handleContextKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    addContextPaths();
  }

  async function previewBridgeRun() {
    if (!canPreflight) return;
    setPreflightLoading(true);
    setPreflightError('');
    try {
      const response = await preflightAgentBridge(bridgeRunRequest());
      setPreflight(response);
    } catch (error) {
      setPreflight(null);
      setPreflightError(error instanceof Error ? error.message : 'Provider preflight failed.');
    } finally {
      setPreflightLoading(false);
    }
  }

  async function refreshContextFiles() {
    setContextPickerOpen(true);
    setWorkspaceFilesLoading(true);
    setWorkspaceFilesError('');
    try {
      const response = await listFiles(workspaceRoot.trim() || undefined, BRIDGE_CONTEXT_FILE_LIMIT);
      setWorkspaceFiles(response.files);
      setWorkspaceFilesRoot(response.workspace_root);
    } catch (error) {
      setWorkspaceFiles([]);
      setWorkspaceFilesRoot('');
      setWorkspaceFilesError(error instanceof Error ? error.message : 'Workspace files could not load.');
    } finally {
      setWorkspaceFilesLoading(false);
    }
  }

  function submitBridgeRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canQueue) {
      setPreflightError('Run Preflight before queueing this provider bridge.');
      return;
    }
    onStartRun(bridgeRunRequest());
    setPreflight(null);
    setPreflightError('');
    setMessage('');
  }

  return (
    <div style={styles.sourcePanel(palette)}>
      <div style={styles.sourceHeader}>
        <div>
          <div style={styles.sourceTitle(palette)}>Provider Execution Queue</div>
          <div style={styles.detail(palette)}>
            {jobs.length} recent bridge run{jobs.length === 1 ? '' : 's'}
          </div>
        </div>
        <div style={styles.actions}>
          <button type="button" style={styles.iconTextButton(palette)} onClick={resetBridgeDraft}>
            <RotateCcw size={14} />
            Reset draft
          </button>
          <button type="button" style={styles.iconTextButton(palette)} onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
            Refresh
          </button>
        </div>
      </div>

      <form style={styles.bridgeRunForm(palette)} onSubmit={submitBridgeRun}>
        <BridgeRunProfilePresets
          palette={palette}
          mode={runMode}
          allowEdits={allowEdits}
          timeoutSeconds={timeoutSeconds}
          onApply={applyRunProfile}
        />
        <div style={styles.bridgeRunGrid}>
          <label style={styles.bridgeRunField(palette)}>
            <span>Provider</span>
            <select value={providerId} onChange={(event) => setProviderId(event.target.value)} style={styles.bridgeRunInput(palette)} disabled={!providerOptions.length}>
              {providerOptions.map((provider) => (
                <option key={provider.manifest.id} value={provider.manifest.id}>
                  {provider.manifest.label}
                </option>
              ))}
            </select>
          </label>
          <label style={styles.bridgeRunField(palette)}>
            <span>Mode</span>
            <select value={runMode} onChange={(event) => setRunMode(event.target.value as Mode)} style={styles.bridgeRunInput(palette)}>
              {BRIDGE_RUN_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={styles.bridgeRunField(palette)}>
            <span>Model</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Default" style={styles.bridgeRunInput(palette)} />
          </label>
          <label style={styles.bridgeRunField(palette)}>
            <span>Timeout</span>
            <input
              type="number"
              min={5}
              max={900}
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(Math.max(5, Math.min(900, Number(event.target.value) || 240)))}
              style={styles.bridgeRunInput(palette)}
            />
          </label>
        </div>
        <label style={styles.bridgeRunField(palette)}>
          <span>Workspace</span>
          <input value={workspaceRoot} onChange={(event) => setWorkspaceRoot(event.target.value)} placeholder="Default workspace" style={styles.bridgeRunInput(palette)} />
        </label>
        <label style={styles.bridgeRunField(palette)}>
          <span>Context</span>
          <div style={styles.bridgeContextInputRow}>
            <input
              value={contextDraft}
              onChange={(event) => setContextDraft(event.target.value)}
              onKeyDown={handleContextKeyDown}
              placeholder="@src/App.tsx, backend/aegis_ai/main.py"
              style={styles.bridgeRunInput(palette)}
            />
            <button type="button" style={styles.sourceActionButton(palette)} onClick={() => addContextPaths()} disabled={!canAddContext}>
              <Plus size={13} />
              Add
            </button>
            <button type="button" style={styles.sourceActionButton(palette)} onClick={() => void refreshContextFiles()} disabled={workspaceFilesLoading}>
              {workspaceFilesLoading ? <Loader2 size={13} className="spin" /> : <Search size={13} />}
              Browse
            </button>
          </div>
        </label>
        {contextPickerOpen ? (
          <BridgeContextFilePicker
            palette={palette}
            files={visibleWorkspaceFiles}
            loading={workspaceFilesLoading}
            error={workspaceFilesError}
            workspaceRoot={workspaceFilesRoot}
            totalFiles={workspaceFiles.length}
            onAdd={addContextFile}
            onRefresh={() => void refreshContextFiles()}
            onClose={() => setContextPickerOpen(false)}
          />
        ) : null}
        {contextPaths.length ? <BridgeContextChips palette={palette} paths={contextPaths} onRemove={removeContextPath} /> : null}
        <label style={styles.bridgeRunField(palette)}>
          <span>Prompt</span>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={`Run ${selectedProvider?.manifest.label || 'provider'} bridge`}
            rows={3}
            style={styles.bridgeRunTextarea(palette)}
          />
        </label>
        <div style={styles.bridgeRunFooter}>
          <label style={styles.bridgeRunCheck(palette)}>
            <input type="checkbox" checked={allowEdits} onChange={(event) => setAllowEdits(event.target.checked)} />
            <span>Allow edits</span>
          </label>
          <div style={styles.sourceJobActions}>
            <button type="button" style={styles.iconTextButton(palette)} disabled={!canPreflight} onClick={() => void previewBridgeRun()}>
              {preflightLoading ? <Loader2 size={14} className="spin" /> : <ShieldCheck size={14} />}
              Preflight
            </button>
            <button type="submit" style={styles.iconTextButton(palette)} disabled={!canQueue}>
              {busyJob === '__launch__' ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
              Queue reviewed run
            </button>
          </div>
        </div>
        <div style={styles.sourceMeta(palette)}>{launchGuardMessage}</div>
        <div style={styles.sourceMeta(palette)}>{draftNotice || 'Draft autosaves locally for this workspace.'}</div>
      </form>

      {preflightError ? <div style={styles.sourceError(palette)}>{preflightError}</div> : null}
      {preflight ? <AgentBridgePreflightPanel palette={palette} preflight={preflight} /> : null}

      {visibleJobs.length ? (
        <div style={styles.sourceJobList}>
          {visibleJobs.map((job) => {
            const terminal = agentBridgeJobTerminal(job.status);
            return (
              <div key={job.id} style={styles.sourceJobRow(palette, terminal)}>
                <div style={styles.sourceJobMain}>
                  <span style={styles.sourceDropProvider(palette)}>{job.provider_label || job.provider_id}</span>
                  <span style={styles.sourceMeta(palette)}>{job.message || job.command || job.id}</span>
                </div>
                <div style={styles.sourceJobActions}>
                  <span style={styles.sourceDropStatus(palette, job.status)}>{agentBridgeJobLabel(job.status)}</span>
                  <button type="button" style={styles.sourceActionButton(palette)} onClick={() => onSelectJob(job)} disabled={busyJob === `${job.id}:details`}>
                    {busyJob === `${job.id}:details` ? <Loader2 size={13} className="spin" /> : <Eye size={13} />}
                    Details
                  </button>
                  {terminal ? (
                    <button type="button" style={styles.sourceActionButton(palette)} onClick={() => onRetryJob(job)} disabled={Boolean(busyJob)}>
                      {busyJob === `${job.id}:retry` ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />}
                      Retry
                    </button>
                  ) : (
                    <button type="button" style={styles.sourceDangerActionButton(palette)} onClick={() => onCancelJob(job)} disabled={Boolean(busyJob)}>
                      {busyJob === `${job.id}:cancel` ? <Loader2 size={13} className="spin" /> : <Square size={13} />}
                      Stop
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={styles.empty(palette)}>No provider bridge runs yet.</div>
      )}

      {selectedJob ? (
        <AgentBridgeJobDetail
          palette={palette}
          job={selectedJob}
          busyJob={busyJob}
          onClose={onCloseJob}
          onCancel={() => onCancelJob(selectedJob)}
          onRetry={() => onRetryJob(selectedJob)}
        />
      ) : null}
    </div>
  );
}

function AgentBridgePreflightPanel({ palette, preflight }: { palette: Palette; preflight: AgentBridgePreflightResponse }) {
  const statusLabel = agentBridgePreflightLabel(preflight.status);
  const contextPaths = bridgeContextPathsFromMetadata(preflight.metadata);
  const modeLabel = bridgeRunModeLabel(String(preflight.metadata.mode || 'build'));
  const reviewId = preflight.preflight_signature ? preflight.preflight_signature.slice(0, 12) : 'None';
  return (
    <div style={styles.bridgePreflightPanel(palette, preflight.ok)}>
      <div style={styles.sourceDropTop}>
        <div>
          <div style={styles.sourceDropProvider(palette)}>{preflight.provider_label || preflight.provider_id}</div>
          <div style={styles.sourceMeta(palette)}>{preflight.message || statusLabel}</div>
        </div>
        <span style={styles.sourceDropStatus(palette, preflight.status)}>{statusLabel}</span>
      </div>
      <div style={styles.sourceJobMetaGrid}>
        <span>Route</span>
        <strong style={styles.sourceJobMetaValue}>{preflight.route_type || 'None'}</strong>
        <span>Review</span>
        <strong style={styles.sourceJobMetaValue}>{reviewId}</strong>
        <span>Mode</span>
        <strong style={styles.sourceJobMetaValue}>{modeLabel}</strong>
        <span>Model</span>
        <strong style={styles.sourceJobMetaValue}>{preflight.model || 'Default'}</strong>
        <span>Timeout</span>
        <strong style={styles.sourceJobMetaValue}>{preflight.timeout_seconds}s</strong>
        <span>Directory</span>
        <strong style={styles.sourceJobMetaValue}>{preflight.cwd || 'Default'}</strong>
      </div>
      {preflight.command ? <pre style={styles.bridgePreflightCommand(palette)}>{preflight.command}</pre> : null}
      {contextPaths.length ? <BridgeContextChips palette={palette} paths={contextPaths} /> : null}
      {preflight.warnings.length ? (
        <div style={styles.setupList(palette)}>
          {preflight.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function BridgeRunProfilePresets({
  palette,
  mode,
  allowEdits,
  timeoutSeconds,
  onApply
}: {
  palette: Palette;
  mode: Mode;
  allowEdits: boolean;
  timeoutSeconds: number;
  onApply: (profileId: (typeof BRIDGE_RUN_PROFILE_OPTIONS)[number]['id']) => void;
}) {
  return (
    <div style={styles.bridgeRunProfiles(palette)} aria-label="Run profiles">
      {BRIDGE_RUN_PROFILE_OPTIONS.map((profile) => {
        const active = mode === profile.mode && allowEdits === profile.allowEdits && timeoutSeconds === profile.timeoutSeconds;
        const policy = profile.allowEdits ? 'edits' : 'read-only';
        return (
          <button
            key={profile.id}
            type="button"
            style={styles.bridgeRunProfileButton(palette, active)}
            title={profile.prompt}
            onClick={() => onApply(profile.id)}
          >
            <strong>{profile.label}</strong>
            <span>
              {policy} / {profile.timeoutSeconds}s
            </span>
          </button>
        );
      })}
    </div>
  );
}

function BridgeContextFilePicker({
  palette,
  files,
  loading,
  error,
  workspaceRoot,
  totalFiles,
  onAdd,
  onRefresh,
  onClose
}: {
  palette: Palette;
  files: WorkspaceFile[];
  loading: boolean;
  error: string;
  workspaceRoot: string;
  totalFiles: number;
  onAdd: (path: string) => void;
  onRefresh: () => void;
  onClose: () => void;
}) {
  return (
    <div style={styles.bridgeContextPicker(palette)}>
      <div style={styles.sourceDropTop}>
        <div>
          <div style={styles.sourceDropProvider(palette)}>Workspace Files</div>
          <div style={styles.sourceMeta(palette)}>
            {workspaceRoot ? `${totalFiles} indexed from ${workspaceRoot}` : 'Load files from the selected workspace.'}
          </div>
        </div>
        <div style={styles.sourceJobActions}>
          <button type="button" style={styles.sourceActionButton(palette)} onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
            Refresh
          </button>
          <button type="button" style={styles.sourceActionButton(palette)} onClick={onClose} aria-label="Close workspace context picker">
            <X size={13} />
            Close
          </button>
        </div>
      </div>
      {error ? <div style={styles.sourceError(palette)}>{error}</div> : null}
      {files.length ? (
        <div style={styles.bridgeContextFileList}>
          {files.map((file) => (
            <button key={file.path} type="button" style={styles.bridgeContextFileButton(palette)} onClick={() => onAdd(file.path)} title={file.path}>
              <span style={styles.bridgeContextFilePath(palette)}>{file.path}</span>
              <span style={styles.bridgeContextFileMeta(palette)}>
                {file.kind} / {formatBridgeFileSize(file.size)}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div style={styles.empty(palette)}>{loading ? 'Loading workspace files...' : 'No matching workspace files.'}</div>
      )}
    </div>
  );
}

function BridgeContextChips({ palette, paths, onRemove }: { palette: Palette; paths: string[]; onRemove?: (path: string) => void }) {
  return (
    <div style={styles.bridgeContextChips}>
      {paths.map((path) => (
        <span key={path} style={styles.bridgeContextChip(palette)} title={path}>
          <span>{path}</span>
          {onRemove ? (
            <button type="button" style={styles.bridgeContextRemoveButton(palette)} onClick={() => onRemove(path)} aria-label={`Remove ${path}`}>
              <X size={12} />
            </button>
          ) : null}
        </span>
      ))}
    </div>
  );
}

function AgentBridgeJobDetail({
  palette,
  job,
  busyJob,
  onClose,
  onCancel,
  onRetry
}: {
  palette: Palette;
  job: AgentBridgeJobInfo;
  busyJob: string;
  onClose: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const terminal = agentBridgeJobTerminal(job.status);
  const contextPaths = bridgeContextPathsFromJob(job);
  const workspaceChanges = bridgeWorkspaceChangesFromJob(job);
  const modeLabel = bridgeRunModeLabel(String(job.mode || job.metadata.mode || 'build'));
  return (
    <div style={styles.sourceJobDetail(palette)}>
      <div style={styles.sourceDropTop}>
        <div>
          <div style={styles.sourceDropProvider(palette)}>{job.provider_label || job.provider_id}</div>
          <div style={styles.sourceMeta(palette)}>{job.id}</div>
        </div>
        <div style={styles.sourceJobActions}>
          <span style={styles.sourceDropStatus(palette, job.status)}>{agentBridgeJobLabel(job.status)}</span>
          {terminal ? (
            <button type="button" style={styles.sourceActionButton(palette)} onClick={onRetry} disabled={Boolean(busyJob)}>
              {busyJob === `${job.id}:retry` ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />}
              Retry
            </button>
          ) : (
            <button type="button" style={styles.sourceDangerActionButton(palette)} onClick={onCancel} disabled={Boolean(busyJob)}>
              {busyJob === `${job.id}:cancel` ? <Loader2 size={13} className="spin" /> : <Square size={13} />}
              Stop
            </button>
          )}
          <button type="button" style={styles.sourceActionButton(palette)} onClick={onClose} aria-label="Close provider execution job details">
            <X size={13} />
            Close
          </button>
        </div>
      </div>
      <div style={styles.sourceJobMetaGrid}>
        <span>Mode</span>
        <strong style={styles.sourceJobMetaValue}>{modeLabel}</strong>
        <span>Model</span>
        <strong style={styles.sourceJobMetaValue}>{job.model || 'Default'}</strong>
        <span>Workspace</span>
        <strong style={styles.sourceJobMetaValue}>{job.workspace_root || 'Default'}</strong>
        <span>Command</span>
        <strong style={styles.sourceJobMetaValue}>{job.command || 'Pending'}</strong>
        <span>Directory</span>
        <strong style={styles.sourceJobMetaValue}>{job.cwd || 'Default'}</strong>
        <span>Process</span>
        <strong style={styles.sourceJobMetaValue}>{job.pid ? `${job.pid}` : 'None'}</strong>
        <span>Runtime</span>
        <strong style={styles.sourceJobMetaValue}>{formatSourceRefreshDuration(job.duration_ms)}</strong>
        <span>Checkpoint</span>
        <strong style={styles.sourceJobMetaValue}>{job.checkpoint || 'None'}</strong>
        <span>Context</span>
        <strong style={styles.sourceJobMetaValue}>{contextPaths.length ? `${contextPaths.length} pinned` : 'None'}</strong>
        <span>Changes</span>
        <strong style={styles.sourceJobMetaValue}>{workspaceChanges.changedTotal ? `${workspaceChanges.changedTotal} file${workspaceChanges.changedTotal === 1 ? '' : 's'}` : 'None'}</strong>
      </div>
      {contextPaths.length ? <BridgeContextChips palette={palette} paths={contextPaths} /> : null}
      {job.warnings.length ? <BridgeJobWarnings palette={palette} warnings={job.warnings} /> : null}
      {workspaceChanges.changedTotal ? <BridgeWorkspaceChangeSummary palette={palette} changes={workspaceChanges} /> : null}
      <div style={styles.sourceMeta(palette)}>{job.message || 'No status message yet.'}</div>
      {job.reply ? (
        <div>
          <div style={styles.sourceJobOutputLabel(palette)}>reply</div>
          <pre style={styles.sourceJobOutput(palette)}>{job.reply}</pre>
        </div>
      ) : null}
      <div style={styles.sourceJobOutputGrid}>
        <div>
          <div style={styles.sourceJobOutputLabel(palette)}>stdout</div>
          <pre style={styles.sourceJobOutput(palette)}>{job.stdout || 'No stdout yet.'}</pre>
        </div>
        <div>
          <div style={styles.sourceJobOutputLabel(palette)}>stderr</div>
          <pre style={styles.sourceJobOutput(palette)}>{job.stderr || 'No stderr yet.'}</pre>
        </div>
      </div>
    </div>
  );
}

function BridgeJobWarnings({ palette, warnings }: { palette: Palette; warnings: string[] }) {
  return (
    <div style={styles.bridgeWarningPanel(palette)}>
      <div style={styles.sourceJobOutputLabel(palette)}>warnings</div>
      <div style={styles.setupList(palette)}>
        {warnings.map((warning) => (
          <span key={warning}>{warning}</span>
        ))}
      </div>
    </div>
  );
}

function BridgeWorkspaceChangeSummary({ palette, changes }: { palette: Palette; changes: BridgeWorkspaceChanges }) {
  const groups = [
    { label: 'Created', paths: changes.created, count: changes.createdCount },
    { label: 'Updated', paths: changes.updated, count: changes.updatedCount },
    { label: 'Deleted', paths: changes.deleted, count: changes.deletedCount }
  ].filter((group) => group.count || group.paths.length);
  return (
    <div style={styles.bridgeChangePanel(palette)}>
      <div style={styles.sourceDropTop}>
        <div style={styles.sourceJobOutputLabel(palette)}>workspace changes</div>
        <span style={styles.bridgeChangeCountBadge(palette)}>{changes.changedTotal}</span>
      </div>
      <div style={styles.bridgeChangeBuckets}>
        {groups.map((group) => (
          <div key={group.label} style={styles.bridgeChangeBucket(palette)}>
            <div style={styles.bridgeChangeBucketTitle(palette)}>
              <span>{group.label}</span>
              <strong>{group.count || group.paths.length}</strong>
            </div>
            {group.paths.length ? (
              <div style={styles.bridgeChangePathList}>
                {group.paths.slice(0, 8).map((path) => (
                  <span key={`${group.label}-${path}`} style={styles.bridgeChangePath(palette)} title={path}>
                    {path}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {changes.truncated ? <div style={styles.sourceMeta(palette)}>Additional changed files were truncated.</div> : null}
    </div>
  );
}

function SourceRefreshJobDetail({
  palette,
  job,
  busyJob,
  onClose,
  onCancel,
  onRetry
}: {
  palette: Palette;
  job: ProviderSourceRefreshJobInfo;
  busyJob: string;
  onClose: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const terminal = sourceRefreshJobTerminal(job.status);
  return (
    <div style={styles.sourceJobDetail(palette)}>
      <div style={styles.sourceDropTop}>
        <div>
          <div style={styles.sourceDropProvider(palette)}>{job.action_label || job.provider_label}</div>
          <div style={styles.sourceMeta(palette)}>{job.id}</div>
        </div>
        <div style={styles.sourceJobActions}>
          <span style={styles.sourceDropStatus(palette, job.status)}>{sourceRefreshJobLabel(job.status)}</span>
          {terminal ? (
            <button type="button" style={styles.sourceActionButton(palette)} onClick={onRetry} disabled={Boolean(busyJob)}>
              {busyJob === `${job.id}:retry` ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />}
              Retry
            </button>
          ) : (
            <button type="button" style={styles.sourceDangerActionButton(palette)} onClick={onCancel} disabled={Boolean(busyJob)}>
              {busyJob === `${job.id}:cancel` ? <Loader2 size={13} className="spin" /> : <Square size={13} />}
              Stop
            </button>
          )}
          <button type="button" style={styles.sourceActionButton(palette)} onClick={onClose} aria-label="Close source refresh job details">
            <X size={13} />
            Close
          </button>
        </div>
      </div>
      <div style={styles.sourceJobMetaGrid}>
        <span>Command</span>
        <strong style={styles.sourceJobMetaValue}>{job.command || 'Unknown'}</strong>
        <span>Directory</span>
        <strong style={styles.sourceJobMetaValue}>{job.cwd || 'Default'}</strong>
        <span>Process</span>
        <strong style={styles.sourceJobMetaValue}>{job.pid ? `${job.pid}` : 'None'}</strong>
        <span>Runtime</span>
        <strong style={styles.sourceJobMetaValue}>{formatSourceRefreshDuration(job.duration_ms)}</strong>
      </div>
      <div style={styles.sourceMeta(palette)}>{job.message || 'No status message yet.'}</div>
      <div style={styles.sourceJobOutputGrid}>
        <div>
          <div style={styles.sourceJobOutputLabel(palette)}>stdout</div>
          <pre style={styles.sourceJobOutput(palette)}>{job.stdout || 'No stdout yet.'}</pre>
        </div>
        <div>
          <div style={styles.sourceJobOutputLabel(palette)}>stderr</div>
          <pre style={styles.sourceJobOutput(palette)}>{job.stderr || 'No stderr yet.'}</pre>
        </div>
      </div>
    </div>
  );
}

function SourceFreshnessBadge({ palette, freshness, label }: { palette: Palette; freshness: string; label: string }) {
  return <span style={styles.sourceFreshnessBadge(palette, freshness)}>{label}</span>;
}

function mergeSourceRefreshJob(jobs: ProviderSourceRefreshJobInfo[], job: ProviderSourceRefreshJobInfo) {
  const next = jobs.filter((item) => item.id !== job.id);
  return [job, ...next].slice(0, 8);
}

function mergeAgentBridgeJob(jobs: AgentBridgeJobInfo[], job: AgentBridgeJobInfo) {
  const next = jobs.filter((item) => item.id !== job.id);
  return [job, ...next].slice(0, 8);
}

function sourceRefreshKey(drop: ProviderSourceDropInfo, actionId: string) {
  return `${drop.provider_id}:${actionId}:${drop.source_candidate || drop.display}`;
}

function sourceRefreshJobTerminal(status: string) {
  return ['completed', 'failed', 'timed_out', 'not_configured', 'unsupported', 'interrupted', 'canceled'].includes(status.toLowerCase());
}

function agentBridgeJobTerminal(status: string) {
  return ['completed', 'failed', 'timed_out', 'not_configured', 'unsupported', 'canceled'].includes(status.toLowerCase());
}

function sourceRefreshJobLabel(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === 'queued') return 'Queued';
  if (normalized === 'checkpoint') return 'Checkpoint';
  if (normalized === 'running') return 'Running';
  if (normalized === 'completed') return 'Completed';
  if (normalized === 'timed_out') return 'Timed out';
  if (normalized === 'not_configured') return 'Not configured';
  if (normalized === 'unsupported') return 'Unsupported';
  if (normalized === 'interrupted') return 'Interrupted';
  if (normalized === 'canceled') return 'Canceled';
  return normalized ? normalized.replace(/_/g, ' ') : 'Unknown';
}

function agentBridgeJobLabel(status: string) {
  return sourceRefreshJobLabel(status);
}

function agentBridgePreflightLabel(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === 'ready') return 'Ready';
  return sourceRefreshJobLabel(status);
}

function bridgeRunModeLabel(mode: string) {
  const normalized = mode.toLowerCase();
  return BRIDGE_RUN_MODE_OPTIONS.find((option) => option.value === normalized)?.label ?? (normalized ? normalized.replace(/_/g, ' ') : 'Build');
}

function mergeBridgeContextPaths(current: string[], raw: string) {
  const next = [...current];
  const seen = new Set(next);
  for (const candidate of parseBridgeContextPaths(raw)) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    next.push(candidate);
    if (next.length >= 50) break;
  }
  return next;
}

function parseBridgeContextPaths(raw: string) {
  return raw
    .split(/[\n,;]+/)
    .map((item) => normalizeBridgeContextPath(item))
    .filter((item): item is string => Boolean(item));
}

function normalizeBridgeContextPath(raw: string) {
  let candidate = raw.trim().replace(/^[`'"]+|[`'"]+$/g, '').replace(/\\/g, '/');
  candidate = candidate.replace(/^@+/, '').replace(/^\.\/+/, '').replace(/^\/+/, '');
  if (!candidate || /^[A-Za-z]:\//.test(candidate)) return '';
  const parts = candidate.split('/').filter(Boolean);
  if (!parts.length || parts.some((part) => part === '.' || part === '..')) return '';
  return parts.join('/');
}

function bridgeContextPathsFromMetadata(metadata: Record<string, unknown>) {
  return bridgeContextPathsFromValue(metadata.context_paths);
}

function bridgeContextPathsFromJob(job: AgentBridgeJobInfo) {
  const fromRequest = bridgeContextPathsFromValue(job.request?.context_paths);
  return fromRequest.length ? fromRequest : bridgeContextPathsFromMetadata(job.metadata);
}

function bridgeContextPathsFromValue(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => normalizeBridgeContextPath(String(item))).filter((item): item is string => Boolean(item));
}

interface BridgeWorkspaceChanges {
  created: string[];
  updated: string[];
  deleted: string[];
  createdCount: number;
  updatedCount: number;
  deletedCount: number;
  changedTotal: number;
  truncated: boolean;
}

function bridgeWorkspaceChangesFromJob(job: AgentBridgeJobInfo): BridgeWorkspaceChanges {
  const changes = bridgeWorkspaceChangesFromMetadata(job.metadata);
  if (changes.changedTotal) return changes;
  const changedFiles = bridgeContextPathsFromValue(job.metadata.changed_files);
  return {
    created: [],
    updated: changedFiles,
    deleted: [],
    createdCount: 0,
    updatedCount: changedFiles.length,
    deletedCount: 0,
    changedTotal: changedFiles.length,
    truncated: false
  };
}

function bridgeWorkspaceChangesFromMetadata(metadata: Record<string, unknown>): BridgeWorkspaceChanges {
  const raw = metadata.workspace_changes;
  const payload = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const created = bridgeContextPathsFromValue(payload.created);
  const updated = bridgeContextPathsFromValue(payload.updated);
  const deleted = bridgeContextPathsFromValue(payload.deleted);
  const createdCount = bridgeNumber(payload.created_count, created.length);
  const updatedCount = bridgeNumber(payload.updated_count, updated.length);
  const deletedCount = bridgeNumber(payload.deleted_count, deleted.length);
  return {
    created,
    updated,
    deleted,
    createdCount,
    updatedCount,
    deletedCount,
    changedTotal: bridgeNumber(payload.changed_total, createdCount + updatedCount + deletedCount),
    truncated: Boolean(payload.truncated)
  };
}

function bridgeNumber(value: unknown, fallback: number) {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function formatBridgeFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) return '0 B';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(size < 10 * 1024 ? 1 : 0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(size < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function formatBridgeDraftTime(value: string) {
  if (!value) return 'local storage';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'local storage';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatSourceRefreshDuration(durationMs: number) {
  if (!durationMs) return 'Pending';
  if (durationMs < 1000) return `${durationMs} ms`;
  return `${(durationMs / 1000).toFixed(durationMs < 10_000 ? 1 : 0)} s`;
}

function sourceRefreshJobForAction(jobs: ProviderSourceRefreshJobInfo[], drop: ProviderSourceDropInfo, actionId: string) {
  return jobs.find(
    (job) =>
      !sourceRefreshJobTerminal(job.status) &&
      job.provider_id === drop.provider_id &&
      job.action_id === actionId &&
      (!job.source_candidate || !drop.source_candidate || job.source_candidate === drop.source_candidate)
  );
}

interface ProviderRowProps {
  provider: ProviderAccountStatus;
  palette: Palette;
  busy: boolean;
  vaultAvailable: boolean;
  onLink: () => void;
  onUnlink: () => void;
  onProbe: () => void;
  onCliLogin: () => void;
  onCliSession: () => void;
}

function ProviderRow({ provider, palette, busy, vaultAvailable, onLink, onUnlink, onProbe, onCliLogin, onCliSession }: ProviderRowProps) {
  const manifest = provider.manifest;
  const supportsApiKey = manifest.auth_modes.includes('api_key');
  const hasCli = Boolean(manifest.cli_bridge);
  const cliDetected = Boolean(provider.cli_bridge?.binary_path);
  const hasCliLogin = Boolean(manifest.cli_bridge?.login_args.length || provider.cli_bridge?.metadata?.login_command);
  const cliStatus = String(provider.cli_bridge?.status || '').toLowerCase();
  const cliAuthStatus = String(provider.cli_bridge?.auth_status || '').toLowerCase();
  const hasCliAccount = provider.account?.auth_mode === 'cli_bridge';
  const hasEphemeralLocalAccount =
    provider.account?.auth_mode === 'none' || provider.account?.metadata?.auth_boundary === 'local_runtime';
  const canReuseCli =
    hasCli &&
    cliDetected &&
    !['not_configured', 'error'].includes(cliStatus) &&
    !['not_configured', 'error'].includes(cliAuthStatus);

  return (
    <div style={styles.providerRow(palette)}>
      <div style={styles.rowTop}>
        <div style={styles.providerTitleWrap}>
          <div style={styles.providerTitle(palette)}>{manifest.label}</div>
          <div style={styles.detail(palette)}>{provider.account?.account_label || manifest.kind}</div>
        </div>
        <ProviderStatusBadge status={provider.connection_status} palette={palette} />
      </div>

      <ExecutionReadinessSummary provider={provider} palette={palette} />
      <ModelLimitSummary summary={provider.model_limit_summary} palette={palette} />
      <ProviderRouteReadiness provider={provider} palette={palette} />

      <div style={styles.tagWrap}>
        {manifest.auth_modes.map((mode) => (
          <span key={`${manifest.id}-${mode}`} style={styles.tag(palette)}>
            {mode.replace('_', ' ')}
          </span>
        ))}
        {provider.fallback_eligible ? <span style={styles.tag(palette)}>fallback</span> : null}
        {cliDetected ? <span style={styles.tag(palette)}>CLI detected</span> : null}
        {provider.account ? (
          <span style={styles.tag(palette)}>{hasEphemeralLocalAccount ? 'no credentials' : provider.account.auth_mode.replace('_', ' ')}</span>
        ) : null}
      </div>

      {provider.cli_bridge ? (
        <div style={styles.cliBox(palette)}>
          <Terminal size={14} />
          <span>{provider.cli_bridge.cli_name}</span>
          <span>{provider.cli_bridge.auth_status}</span>
          {provider.cli_bridge.version ? <span>{provider.cli_bridge.version}</span> : null}
        </div>
      ) : null}

      {provider.setup_actions.length ? (
        <div style={styles.setupList(palette)}>
          {provider.setup_actions.slice(0, 3).map((action) => (
            <span key={`${manifest.id}-${action}`}>{action}</span>
          ))}
        </div>
      ) : null}

      <div style={styles.rowActions}>
        {supportsApiKey ? (
          <button type="button" style={styles.iconTextButton(palette)} onClick={onLink} disabled={busy || !vaultAvailable}>
            {busy ? <Loader2 size={14} className="spin" /> : <KeyRound size={14} />}
            Link key
          </button>
        ) : null}
        {hasCli ? (
          <button type="button" style={styles.iconTextButton(palette)} onClick={onProbe} disabled={busy}>
            {busy ? <Loader2 size={14} className="spin" /> : <Terminal size={14} />}
            Probe
          </button>
        ) : null}
        {hasCli && cliDetected ? (
          <button type="button" style={styles.iconTextButton(palette)} onClick={onCliSession} disabled={busy || !canReuseCli}>
            {busy ? <Loader2 size={14} className="spin" /> : <ShieldCheck size={14} />}
            {hasCliAccount ? 'Refresh CLI' : 'Use CLI'}
          </button>
        ) : null}
        {hasCli && hasCliLogin ? (
          <button type="button" style={styles.iconTextButton(palette)} onClick={onCliLogin} disabled={busy}>
            {busy ? <Loader2 size={14} className="spin" /> : <Terminal size={14} />}
            Open login
          </button>
        ) : null}
        {provider.account && !hasEphemeralLocalAccount ? (
          <button type="button" style={styles.dangerButton(palette)} onClick={onUnlink} disabled={busy}>
            {busy ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
            Unlink
          </button>
        ) : null}
      </div>
    </div>
  );
}

function ExecutionReadinessSummary({ provider, palette }: { provider: ProviderAccountStatus; palette: Palette }) {
  const color = provider.execution_ready
    ? palette.good
    : provider.connection_status === 'error' || provider.readiness === 'cli_error'
      ? palette.bad
      : palette.warning;
  const Icon = provider.execution_ready ? CheckCircle2 : AlertTriangle;
  return (
    <div style={styles.readinessBox(palette, color)}>
      <Icon size={14} />
      <strong>{provider.readiness_label || (provider.execution_ready ? 'Ready' : 'Setup Required')}</strong>
      <span>{provider.readiness_detail || 'Provider route readiness has not been probed yet.'}</span>
    </div>
  );
}

const styles = {
  panel: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 12,
    color: palette.text
  }),
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap'
  } as CSSProperties,
  heading: (palette: Palette): CSSProperties => ({
    margin: 0,
    color: palette.text,
    fontSize: 15,
    fontWeight: 900
  }),
  detail: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 12,
    lineHeight: 1.4
  }),
  actions: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,
  providerGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: 10
  } as CSSProperties,
  sourcePanel: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.cardAlt,
    padding: 12,
    minWidth: 0
  }),
  sourceHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10,
    flexWrap: 'wrap'
  } as CSSProperties,
  sourceTitle: (palette: Palette): CSSProperties => ({
    color: palette.text,
    fontSize: 13,
    fontWeight: 950
  }),
  sourceRootGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: 8
  } as CSSProperties,
  sourceRootButton: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 4,
    textAlign: 'left',
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    color: palette.text,
    padding: 10,
    cursor: 'pointer',
    minWidth: 0
  }),
  sourceRootTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    minWidth: 0
  } as CSSProperties,
  sourcePath: (palette: Palette): CSSProperties => ({
    color: palette.textSoft,
    fontSize: 11,
    lineHeight: 1.35,
    overflowWrap: 'anywhere'
  }),
  sourceMeta: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 11,
    lineHeight: 1.35,
    overflowWrap: 'anywhere'
  }),
  sourceDropGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 8
  } as CSSProperties,
  sourceDropRow: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 5,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    padding: 10,
    minWidth: 0
  }),
  sourceDropTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,
  sourceDropBadges: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,
  sourceActionRow: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap'
  } as CSSProperties,
  bridgeRunForm: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    padding: 10,
    minWidth: 0
  }),
  bridgeRunGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(96px, 1fr))',
    gap: 8,
    minWidth: 0
  } as CSSProperties,
  bridgeRunProfiles: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(92px, 1fr))',
    gap: 6,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.control,
    padding: 6,
    minWidth: 0
  }),
  bridgeRunProfileButton: (palette: Palette, active: boolean): CSSProperties => ({
    display: 'grid',
    gap: 2,
    minHeight: 42,
    minWidth: 0,
    borderRadius: 8,
    border: `1px solid ${active ? palette.accent : palette.inputBorder}`,
    background: active ? `${palette.accent}1f` : palette.input,
    color: active ? palette.text : palette.textSoft,
    padding: '6px 8px',
    textAlign: 'left',
    cursor: 'pointer',
    fontSize: 11,
    lineHeight: 1.2
  }),
  bridgeRunField: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 4,
    color: palette.muted,
    fontSize: 10,
    fontWeight: 950,
    minWidth: 0,
    textTransform: 'uppercase'
  }),
  bridgeRunInput: (palette: Palette): CSSProperties => ({
    width: '100%',
    minWidth: 0,
    minHeight: 32,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.control,
    color: palette.text,
    padding: '0 9px',
    fontSize: 12,
    fontWeight: 750
  }),
  bridgeRunTextarea: (palette: Palette): CSSProperties => ({
    width: '100%',
    minWidth: 0,
    minHeight: 72,
    resize: 'vertical',
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.control,
    color: palette.text,
    padding: 9,
    fontSize: 12,
    lineHeight: 1.4
  }),
  bridgeContextInputRow: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto auto',
    alignItems: 'center',
    gap: 6,
    minWidth: 0
  } as CSSProperties,
  bridgeContextChips: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    minWidth: 0
  } as CSSProperties,
  bridgeContextChip: (palette: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    maxWidth: '100%',
    borderRadius: 999,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.textSoft,
    padding: '3px 6px 3px 8px',
    fontSize: 11,
    fontWeight: 850,
    lineHeight: 1.2,
    overflowWrap: 'anywhere'
  }),
  bridgeContextRemoveButton: (palette: Palette): CSSProperties => ({
    width: 18,
    height: 18,
    borderRadius: 999,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    color: palette.textSoft,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 0,
    cursor: 'pointer',
    flex: '0 0 auto'
  }),
  bridgeContextPicker: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    padding: 8,
    minWidth: 0
  }),
  bridgeContextFileList: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 6,
    minWidth: 0
  } as CSSProperties,
  bridgeContextFileButton: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 3,
    minHeight: 48,
    minWidth: 0,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.input,
    color: palette.text,
    textAlign: 'left',
    padding: 8,
    cursor: 'pointer'
  }),
  bridgeContextFilePath: (palette: Palette): CSSProperties => ({
    color: palette.textSoft,
    fontSize: 11,
    fontWeight: 850,
    lineHeight: 1.25,
    overflowWrap: 'anywhere'
  }),
  bridgeContextFileMeta: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 10,
    fontWeight: 750,
    lineHeight: 1.25,
    overflowWrap: 'anywhere'
  }),
  bridgeWarningPanel: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    borderRadius: 8,
    border: `1px solid ${palette.warning}55`,
    background: `${palette.warning}10`,
    padding: 8,
    minWidth: 0
  }),
  bridgeChangePanel: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    padding: 8,
    minWidth: 0
  }),
  bridgeChangeBuckets: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: 8,
    minWidth: 0
  } as CSSProperties,
  bridgeChangeBucket: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    minWidth: 0,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.input,
    padding: 8
  }),
  bridgeChangeBucketTitle: (palette: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    color: palette.textSoft,
    fontSize: 11,
    fontWeight: 950,
    textTransform: 'uppercase'
  }),
  bridgeChangePathList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 5,
    minWidth: 0
  } as CSSProperties,
  bridgeChangePath: (palette: Palette): CSSProperties => ({
    borderRadius: 999,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.cardAlt,
    color: palette.textSoft,
    padding: '2px 7px',
    fontSize: 10,
    fontWeight: 850,
    lineHeight: 1.25,
    overflowWrap: 'anywhere'
  }),
  bridgeChangeCountBadge: (palette: Palette): CSSProperties => ({
    color: palette.good,
    border: `1px solid ${palette.good}55`,
    background: `${palette.good}14`,
    borderRadius: 999,
    padding: '2px 7px',
    fontSize: 10,
    fontWeight: 950,
    whiteSpace: 'nowrap'
  }),
  bridgeRunFooter: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,
  bridgePreflightPanel: (palette: Palette, ok: boolean): CSSProperties => {
    const color = ok ? palette.good : palette.warning;
    return {
      display: 'grid',
      gap: 8,
      borderRadius: 8,
      border: `1px solid ${color}55`,
      background: `${color}10`,
      padding: 10,
      minWidth: 0
    };
  },
  bridgePreflightCommand: (palette: Palette): CSSProperties => ({
    margin: '2px 0 0',
    minHeight: 34,
    maxHeight: 96,
    overflow: 'auto',
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.codeBg,
    color: palette.textSoft,
    padding: 8,
    fontSize: 11,
    lineHeight: 1.35,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),
  bridgeRunCheck: (palette: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    color: palette.textSoft,
    fontSize: 12,
    fontWeight: 850
  }),
  sourceActionButton: (palette: Palette): CSSProperties => ({
    minHeight: 28,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.textSoft,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '0 8px',
    fontSize: 11,
    fontWeight: 900,
    cursor: 'pointer'
  }),
  sourceDangerActionButton: (palette: Palette): CSSProperties => ({
    minHeight: 28,
    borderRadius: 8,
    border: `1px solid ${palette.bad}55`,
    background: `${palette.bad}14`,
    color: palette.textSoft,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '0 8px',
    fontSize: 11,
    fontWeight: 900,
    cursor: 'pointer'
  }),
  sourceJobList: {
    display: 'grid',
    gap: 6
  } as CSSProperties,
  sourceJobRow: (palette: Palette, terminal: boolean): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: terminal ? palette.input : palette.control,
    padding: '8px 10px',
    minWidth: 0
  }),
  sourceJobMain: {
    display: 'grid',
    gap: 2,
    minWidth: 0
  } as CSSProperties,
  sourceJobActions: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 6,
    flexWrap: 'wrap'
  } as CSSProperties,
  sourceJobDetail: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.input,
    padding: 10,
    minWidth: 0
  }),
  sourceJobMetaGrid: {
    display: 'grid',
    gridTemplateColumns: 'minmax(56px, auto) minmax(0, 1fr)',
    gap: '4px 10px',
    fontSize: 11,
    lineHeight: 1.35,
    minWidth: 0
  } as CSSProperties,
  sourceJobMetaValue: {
    minWidth: 0,
    overflowWrap: 'anywhere'
  } as CSSProperties,
  sourceJobOutputGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 8,
    minWidth: 0
  } as CSSProperties,
  sourceJobOutputLabel: (palette: Palette): CSSProperties => ({
    color: palette.muted,
    fontSize: 10,
    fontWeight: 950,
    textTransform: 'uppercase'
  }),
  sourceJobOutput: (palette: Palette): CSSProperties => ({
    margin: '4px 0 0',
    minHeight: 70,
    maxHeight: 180,
    overflow: 'auto',
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.codeBg,
    color: palette.textSoft,
    padding: 8,
    fontSize: 11,
    lineHeight: 1.35,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),
  sourceDropProvider: (palette: Palette): CSSProperties => ({
    color: palette.text,
    fontSize: 12,
    fontWeight: 950
  }),
  sourceDropStatus: (palette: Palette, status: string): CSSProperties => {
    const normalized = status.toLowerCase();
    const color =
      normalized === 'linked' || normalized === 'completed' || normalized === 'ready'
        ? palette.good
        : ['error', 'failed', 'timed_out', 'not_configured', 'unsupported', 'interrupted'].includes(normalized)
          ? palette.bad
          : palette.warning;
    return {
      color,
      border: `1px solid ${color}55`,
      background: `${color}14`,
      borderRadius: 999,
      padding: '2px 7px',
      fontSize: 10,
      fontWeight: 950,
      whiteSpace: 'nowrap'
    };
  },
  sourceFreshnessBadge: (palette: Palette, freshness: string): CSSProperties => {
    const normalized = freshness.toLowerCase();
    const color =
      normalized === 'current'
        ? palette.good
        : normalized === 'changed' || normalized === 'needs_probe'
          ? palette.warning
          : normalized === 'missing'
            ? palette.bad
            : palette.muted;
    return {
      color,
      border: `1px solid ${color}55`,
      background: `${color}14`,
      borderRadius: 999,
      padding: '2px 7px',
      fontSize: 10,
      fontWeight: 950,
      whiteSpace: 'nowrap'
    };
  },
  sourceError: (palette: Palette): CSSProperties => ({
    color: palette.bad,
    fontSize: 11,
    lineHeight: 1.35,
    overflowWrap: 'anywhere'
  }),
  providerRow: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    borderRadius: 8,
    border: `1px solid ${palette.shellBorder}`,
    background: palette.cardAlt,
    padding: 12,
    minWidth: 0
  }),
  rowTop: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10
  } as CSSProperties,
  providerTitleWrap: {
    display: 'grid',
    gap: 2,
    minWidth: 0
  } as CSSProperties,
  providerTitle: (palette: Palette): CSSProperties => ({
    color: palette.text,
    fontSize: 14,
    fontWeight: 900
  }),
  tagWrap: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6
  } as CSSProperties,
  readinessBox: (palette: Palette, color: string): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '16px auto minmax(0, 1fr)',
    alignItems: 'center',
    gap: 8,
    borderRadius: 8,
    border: `1px solid ${color}33`,
    background: `${color}12`,
    color: palette.textSoft,
    fontSize: 12,
    lineHeight: 1.4,
    padding: '7px 9px'
  }),
  tag: (palette: Palette): CSSProperties => ({
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.textSoft,
    borderRadius: 999,
    padding: '2px 8px',
    fontSize: 11,
    fontWeight: 800,
    whiteSpace: 'nowrap'
  }),
  cliBox: (palette: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    minHeight: 30,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    color: palette.textSoft,
    background: palette.input,
    padding: '6px 8px',
    fontSize: 12,
    minWidth: 0
  }),
  rowActions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8
  } as CSSProperties,
  iconTextButton: (palette: Palette): CSSProperties => ({
    minHeight: 32,
    borderRadius: 8,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.control,
    color: palette.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    padding: '0 10px',
    fontSize: 12,
    fontWeight: 900,
    cursor: 'pointer'
  }),
  dangerButton: (palette: Palette): CSSProperties => ({
    minHeight: 32,
    borderRadius: 8,
    border: `1px solid ${palette.bad}55`,
    background: `${palette.bad}16`,
    color: palette.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    padding: '0 10px',
    fontSize: 12,
    fontWeight: 900,
    cursor: 'pointer'
  }),
  vaultRow: (palette: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: palette.textSoft,
    fontSize: 12,
    fontWeight: 800
  }),
  error: (palette: Palette): CSSProperties => ({
    color: palette.bad,
    fontSize: 12,
    fontWeight: 800
  }),
  status: (palette: Palette): CSSProperties => ({
    color: palette.good,
    fontSize: 12,
    fontWeight: 800
  }),
  setupList: (palette: Palette): CSSProperties => ({
    display: 'grid',
    gap: 4,
    color: palette.muted,
    fontSize: 11,
    lineHeight: 1.35
  }),
  empty: (palette: Palette): CSSProperties => ({
    borderRadius: 8,
    border: `1px dashed ${palette.inputBorder}`,
    color: palette.muted,
    padding: 14,
    fontSize: 13
  })
};
