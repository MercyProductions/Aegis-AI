import type { ReactNode } from 'react';
import { CheckCircle2, Loader2, Pause, Play, Save, Wrench, Zap } from 'lucide-react';
import { formatBytes, formatStatusLabel } from '../utils/appUi';
import type { PluginManifest, ProductizationSnapshot, ReliabilityMetric, ToolEvent } from '../types';

type AppStyleBag = Record<string, any>;
type PaletteLike = Record<string, unknown>;

type ProductizationSurfaceProps = {
  productization: ProductizationSnapshot | null;
  productizationLoading: boolean;
  productizationStatus: string;
  productizationAction: string;
  palette: PaletteLike;
  styles: AppStyleBag;
  renderSurfaceHeader: (icon: ReactNode, title: string, description: string, actions?: ReactNode) => ReactNode;
  refreshProductizationSignals: (rootOverride?: string, forceMetrics?: boolean) => void | Promise<void>;
  validateSamplePluginManifest: () => void | Promise<void>;
  updatePluginState: (plugin: PluginManifest, action: 'enable' | 'disable' | 'trust') => void | Promise<void>;
};

export function ProductizationSurface({
  productization,
  productizationLoading,
  productizationStatus,
  productizationAction,
  palette,
  styles,
  renderSurfaceHeader,
  refreshProductizationSignals,
  validateSamplePluginManifest,
  updatePluginState
}: ProductizationSurfaceProps) {
  const snapshot = productization;
  const plugins = snapshot?.plugins ?? [];
  const stableApis = snapshot?.stable_apis ?? [];
  const metrics = snapshot?.metrics ?? [];
  const recovery = snapshot?.recovery;
  const policy = snapshot?.enterprise_policy;
  const degradedMetrics = metrics.filter((metric) => metric.status === 'degraded');
  const invalidPlugins = (snapshot?.plugin_validation ?? []).filter((item) => !item.valid);
  const sqliteSize = Number(snapshot?.performance?.sqlite_size_bytes ?? 0);

  return (
    <div style={styles.surfacePage}>
      {renderSurfaceHeader(
        <Wrench size={22} />,
        'Hardening',
        'Productization controls for stable APIs, plugins, recovery, enterprise policy, packaging, and reliability.',
        <div style={styles.surfaceActions}>
          <button
            type="button"
            style={styles.secondaryButton(palette)}
            onClick={() => void refreshProductizationSignals(undefined, false)}
            disabled={productizationLoading}
          >
            {productizationLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
            Refresh
          </button>
          <button
            type="button"
            style={styles.primaryButton(palette)}
            onClick={() => void refreshProductizationSignals(undefined, true)}
            disabled={productizationLoading}
          >
            {productizationLoading ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Snapshot
          </button>
        </div>
      )}

      <div style={styles.metricGrid}>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Stable APIs</span>
          <strong style={styles.metricValue(palette)}>{stableApis.length}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Plugins</span>
          <strong style={styles.metricValue(palette)}>{plugins.length}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Recovery</span>
          <strong style={styles.metricValue(palette)}>{recovery?.safe_shutdown_ready ? 'Ready' : 'Review'}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Reliability</span>
          <strong style={styles.metricValue(palette)}>
            {degradedMetrics.length ? `${degradedMetrics.length} degraded` : 'Healthy'}
          </strong>
        </div>
      </div>

      {productizationStatus ? (
        <div
          style={styles.eventRow(
            palette,
            productizationStatus.includes('Could not') || productizationStatus.includes('invalid') ? 'error' : 'ok'
          )}
        >
          <div>
            <strong style={styles.eventTitle(palette)}>Hardening Status</strong>
            <div style={styles.eventDetail(palette)}>{productizationStatus}</div>
          </div>
        </div>
      ) : null}

      <div style={styles.surfaceColumns}>
        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Runtime Recovery</h3>
            <span style={styles.diagnosticChip(palette, recovery?.safe_shutdown_ready ? 'ok' : 'warning')}>
              {recovery?.safe_shutdown_ready ? 'Ready' : 'Needs review'}
            </span>
          </div>
          <div style={styles.workspaceMeta(palette)}>
            <strong>SQLite</strong>
            <span>{recovery?.database_ok ? 'quick_check ok' : recovery?.database_message || 'pending'}</span>
            <strong>Database size</strong>
            <span>{formatBytes(sqliteSize)}</span>
            <strong>Open tasks</strong>
            <span>{recovery?.open_tasks ?? 0}</span>
            <strong>Checkpoints</strong>
            <span>{recovery?.checkpoint_count ?? 0}</span>
          </div>
          <div style={styles.eventList}>
            {(recovery?.recommended_actions ?? []).slice(0, 6).map((item) => (
              <div key={item} style={styles.eventRow(palette, 'warning')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>Recovery action</strong>
                  <div style={styles.eventDetail(palette)}>{item}</div>
                </div>
              </div>
            ))}
            {!recovery?.recommended_actions.length ? (
              <div style={styles.emptyPanel(palette)}>No recovery actions are pending.</div>
            ) : null}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Enterprise Controls</h3>
            <span style={styles.contextTag(palette)}>{policy?.privacy_mode ?? 'local_first'}</span>
          </div>
          <div style={styles.workspaceMeta(palette)}>
            <strong>Permission profile</strong>
            <span>{policy?.permission_profile ?? 'guided:standard'}</span>
            <strong>Audit trails</strong>
            <span>{policy?.audit_trails ? 'enabled' : 'disabled'}</span>
            <strong>Plugin signing</strong>
            <span>{policy?.plugin_signing_required ? 'required' : 'optional'}</span>
            <strong>Remote workers</strong>
            <span>{policy?.allow_remote_workers ? 'allowed' : 'disabled'}</span>
          </div>
          <div style={styles.tagWrap}>
            {(policy?.network_allowlist ?? []).map((item) => (
              <span key={item} style={styles.contextTag(palette)}>
                {item}
              </span>
            ))}
            {policy?.enforce_local_models ? <span style={styles.goodTag(palette)}>local models enforced</span> : null}
            {policy?.encrypted_workspace_storage ? <span style={styles.goodTag(palette)}>encrypted storage</span> : null}
          </div>
        </section>
      </div>

      <div style={styles.surfaceColumns}>
        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Plugin SDK</h3>
            <div style={styles.tagWrap}>
              <span style={styles.contextTag(palette)}>{invalidPlugins.length} invalid</span>
              <button
                type="button"
                style={styles.iconTextButton(palette)}
                onClick={() => void validateSamplePluginManifest()}
                disabled={Boolean(productizationAction)}
              >
                {productizationAction === 'validate-sample' ? (
                  <Loader2 size={14} className="spin" />
                ) : (
                  <CheckCircle2 size={14} />
                )}
                Validate sample
              </button>
            </div>
          </div>
          <div style={styles.modelList}>
            {plugins.map((plugin) => {
              const busy = productizationAction.endsWith(`:${plugin.id}`);
              return (
                <div key={plugin.id} style={styles.modelRow(palette, plugin.enabled)}>
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{plugin.name}</div>
                      <span style={styles.diagnosticChip(palette, plugin.enabled ? 'ok' : 'warning')}>
                        {plugin.enabled ? 'enabled' : 'disabled'}
                      </span>
                    </div>
                    <div style={styles.eventDetail(palette)}>{plugin.description || plugin.id}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{plugin.version}</span>
                      <span style={styles.contextTag(palette)}>{plugin.sandbox_profile}</span>
                      {plugin.trusted ? <span style={styles.goodTag(palette)}>trusted</span> : null}
                      {plugin.capabilities.slice(0, 4).map((item) => (
                        <span key={`${plugin.id}-${item}`} style={styles.contextTag(palette)}>
                          {formatStatusLabel(item)}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div style={styles.rowActions}>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => void updatePluginState(plugin, plugin.enabled ? 'disable' : 'enable')}
                      disabled={busy}
                    >
                      {busy ? <Loader2 size={14} className="spin" /> : plugin.enabled ? <Pause size={14} /> : <Play size={14} />}
                      {plugin.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => void updatePluginState(plugin, 'trust')}
                      disabled={plugin.trusted || busy}
                    >
                      <CheckCircle2 size={14} />
                      Trust
                    </button>
                  </div>
                </div>
              );
            })}
            {!plugins.length ? <div style={styles.emptyPanel(palette)}>No plugins are registered yet.</div> : null}
          </div>
          {(snapshot?.plugin_validation ?? []).slice(0, 4).map((result, index) => (
            <div
              key={`${result.normalized_manifest?.id ?? 'plugin'}-${index}`}
              style={styles.eventRow(palette, result.valid ? 'ok' : 'error')}
            >
              <div>
                <strong style={styles.eventTitle(palette)}>
                  {result.normalized_manifest?.name ?? 'Plugin manifest'}
                </strong>
                <div style={styles.eventDetail(palette)}>
                  {result.valid ? result.warnings.join('; ') || 'Manifest validates.' : result.errors.join('; ')}
                </div>
              </div>
            </div>
          ))}
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Stable Internal APIs</h3>
            <span style={styles.contextTag(palette)}>v{snapshot?.api_version ?? '2026.05.07'}</span>
          </div>
          <div style={styles.eventList}>
            {stableApis.map((api) => (
              <div key={api.id} style={styles.eventRow(palette, api.status === 'stable' ? 'ok' : 'warning')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>{api.name}</strong>
                  <div style={styles.eventDetail(palette)}>{api.path_prefixes.slice(0, 4).join(', ')}</div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{api.id}</span>
                    <span style={styles.contextTag(palette)}>{api.status}</span>
                  </div>
                </div>
              </div>
            ))}
            {!stableApis.length ? (
              <div style={styles.emptyPanel(palette)}>Stable API contracts will appear after refresh.</div>
            ) : null}
          </div>
        </section>
      </div>

      <div style={styles.surfaceColumns}>
        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Reliability Metrics</h3>
            <span style={styles.contextTag(palette)}>{metrics.length} metric(s)</span>
          </div>
          <div style={styles.eventList}>
            {metrics.map((metric) => (
              <div key={metric.name} style={styles.eventRow(palette, reliabilityStatusToEventStatus(metric.status))}>
                <div>
                  <strong style={styles.eventTitle(palette)}>{formatStatusLabel(metric.name)}</strong>
                  <div style={styles.eventDetail(palette)}>{metric.detail}</div>
                </div>
                <span style={styles.eventTime(palette)}>{metricLabel(metric)}</span>
              </div>
            ))}
            {!metrics.length ? (
              <div style={styles.emptyPanel(palette)}>Reliability metrics will appear after snapshot refresh.</div>
            ) : null}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Scaling, Packaging, Docs</h3>
            <span style={styles.contextTag(palette)}>{snapshot?.docs.length ?? 0} docs</span>
          </div>
          <div style={styles.workspaceMeta(palette)}>
            <strong>Monorepo</strong>
            <span>{snapshot?.scaling?.monorepo_ready ? 'ready' : 'pending'}</span>
            <strong>Distributed</strong>
            <span>{snapshot?.scaling?.distributed_runtime_ready ? 'ready' : 'pending'}</span>
            <strong>Installer</strong>
            <span>{String(snapshot?.packaging?.signed_installers ?? 'planned')}</span>
            <strong>Updates</strong>
            <span>{String(snapshot?.packaging?.auto_updates ?? 'planned')}</span>
          </div>
          <div style={styles.tagWrap}>
            {(snapshot?.docs ?? []).slice(0, 8).map((doc) => (
              <span key={doc} style={styles.contextTag(palette)}>
                {doc.replace('docs/', '')}
              </span>
            ))}
          </div>
          <div style={styles.eventList}>
            {(snapshot?.recommendations ?? []).slice(0, 6).map((item) => (
              <div key={item} style={styles.eventRow(palette, 'warning')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>Recommendation</strong>
                  <div style={styles.eventDetail(palette)}>{item}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function metricLabel(metric: Pick<ReliabilityMetric, 'value' | 'unit'>) {
  if (metric.unit === 'ratio') return `${Math.round(metric.value * 100)}%`;
  if (metric.unit === 'boolean') return metric.value >= 1 ? 'Ready' : 'No';
  if (metric.unit === 'ms') return `${Math.round(metric.value)} ms`;
  return String(metric.value);
}

function reliabilityStatusToEventStatus(status: string): ToolEvent['status'] {
  if (status === 'degraded' || status === 'critical' || status === 'failed') return 'error';
  if (status === 'watch' || status === 'unknown' || status === 'warning') return 'warning';
  return 'ok';
}
