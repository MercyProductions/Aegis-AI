import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { Activity, BarChart3, GitBranch, RefreshCw, TrendingUp } from 'lucide-react';

import {
  getFallbackInspector,
  getFeedbackTelemetry,
  getRouteQuality,
  getRoutePolicyDiff,
  getTelemetrySnapshot,
  refreshTelemetrySnapshot
} from '../api';
import type {
  FallbackInspectorResponse,
  FeedbackTelemetryResponse,
  RouteQualityResponse,
  RoutePolicyDiffResponse,
  TelemetrySnapshotPruneInfo,
  TelemetrySnapshotStatus
} from '../types';

type ObservabilityView = 'quality' | 'fallback' | 'feedback' | 'policy';

type PaletteLike = {
  shell: string;
  shellBorder: string;
  card: string;
  cardAlt: string;
  input: string;
  inputBorder: string;
  text: string;
  textSoft: string;
  muted: string;
  accent: string;
  accentSoft: string;
  accentAlt: string;
  good: string;
  bad: string;
  warning: string;
  codeBg: string;
};

interface ObservabilityPanelProps {
  workspaceRoot: string;
  palette: PaletteLike;
}

export function ObservabilityPanel({ workspaceRoot, palette }: ObservabilityPanelProps) {
  const [activeView, setActiveView] = useState<ObservabilityView>('quality');
  const [routeQuality, setRouteQuality] = useState<RouteQualityResponse | null>(null);
  const [fallbackInspector, setFallbackInspector] = useState<FallbackInspectorResponse | null>(null);
  const [feedbackTelemetry, setFeedbackTelemetry] = useState<FeedbackTelemetryResponse | null>(null);
  const [policyDiff, setPolicyDiff] = useState<RoutePolicyDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const loadObservability = useCallback(async (refreshSnapshot = false) => {
    const root = workspaceRoot.trim();

    if (!root) {
      setRouteQuality(null);
      setFallbackInspector(null);
      setFeedbackTelemetry(null);
      setPolicyDiff(null);
      setStatus('');
      return;
    }

    setLoading(true);
    setStatus('Loading telemetry...');

    const snapshotFailures: string[] = [];
    try {
      const snapshotResult = refreshSnapshot
        ? await refreshTelemetrySnapshot(root)
        : await getTelemetrySnapshot(root);
      if (snapshotResult.snapshot) {
        const snapshot = snapshotResult.snapshot;
        setRouteQuality(snapshot.route_quality);
        setFallbackInspector(snapshot.fallback_inspector);
        setFeedbackTelemetry(snapshot.feedback);
        let policyWarning = '';
        try {
          setPolicyDiff(await getRoutePolicyDiff(root));
        } catch (error) {
          policyWarning = readFailure(error, 'Policy diff unavailable');
        }
        const pruneStatus = snapshotPruneStatus(snapshotResult.prune);
        setStatus(
          `${snapshotStatus(snapshotResult.cache_status, snapshot.age_seconds, snapshot.is_stale)}${pruneStatus ? ` ${pruneStatus}` : ''}${policyWarning ? ` ${policyWarning}` : ''}`
        );
        setLoading(false);
        return;
      }
      if (snapshotResult.recommendations.length) {
        snapshotFailures.push(snapshotResult.recommendations[0]);
      }
    } catch (error) {
      snapshotFailures.push(readFailure(error, 'Telemetry snapshot unavailable'));
    }

    const [qualityResult, fallbackResult, feedbackResult, policyResult] = await Promise.allSettled([
      getRouteQuality(root),
      getFallbackInspector(root),
      getFeedbackTelemetry(root),
      getRoutePolicyDiff(root, { useSnapshot: false })
    ] as const);

    const failures: string[] = [...snapshotFailures];

    if (qualityResult.status === 'fulfilled') {
      setRouteQuality(qualityResult.value);
    } else {
      failures.push(readFailure(qualityResult.reason, 'Route quality unavailable'));
    }

    if (fallbackResult.status === 'fulfilled') {
      setFallbackInspector(fallbackResult.value);
    } else {
      failures.push(readFailure(fallbackResult.reason, 'Fallback inspector unavailable'));
    }

    if (feedbackResult.status === 'fulfilled') {
      setFeedbackTelemetry(feedbackResult.value);
    } else {
      failures.push(readFailure(feedbackResult.reason, 'Feedback telemetry unavailable'));
    }

    if (policyResult.status === 'fulfilled') {
      setPolicyDiff(policyResult.value);
    } else {
      failures.push(readFailure(policyResult.reason, 'Policy diff unavailable'));
    }

    setStatus(failures.length ? failures.join(' ') : `Updated ${formatClock(new Date())}`);
    setLoading(false);
  }, [workspaceRoot]);

  useEffect(() => {
    void loadObservability();
  }, [loadObservability]);

  const fallbackSummary = useMemo(() => {
    const tasks = fallbackInspector?.tasks ?? [];
    const candidates = tasks.reduce((sum, task) => sum + task.candidates.length, 0);
    const unresolved = tasks.filter((task) => task.status !== 'completed' && task.status !== 'ok').length;
    const fallbackRoles = new Set(tasks.flatMap((task) => task.fallback_roles));
    const adapterIssues = tasks.reduce(
      (sum, task) =>
        sum + task.candidates.filter((candidate) => candidate.adapter_status && candidate.adapter_status !== 'ready').length,
      0
    );

    return { tasks: tasks.length, candidates, unresolved, fallbackRoles: fallbackRoles.size, adapterIssues };
  }, [fallbackInspector]);

  const feedbackSummary = feedbackTelemetry?.summary;
  const overview = routeQuality?.overview;

  return (
    <section style={styles.panel(palette)}>
      <div style={styles.header(palette)}>
        <div style={styles.titleWrap}>
          <Activity size={16} />
          <h3 style={styles.title(palette)}>Observability</h3>
        </div>
        <button
          type="button"
          onClick={() => void loadObservability(true)}
          disabled={loading || !workspaceRoot.trim()}
          style={styles.iconButton(palette, loading || !workspaceRoot.trim())}
          title="Refresh observability"
          aria-label="Refresh observability"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div style={styles.body}>
        <div style={styles.summaryStrip}>
          <MetricCard
            palette={palette}
            label="Reliability"
            value={overview ? formatScore(overview.reliability_score) : 'n/a'}
            tone={scoreTone(overview?.reliability_score)}
          />
          <MetricCard
            palette={palette}
            label="Fallback"
            value={overview ? formatRate(overview.fallback_rate) : 'n/a'}
            tone={overview && overview.fallback_rate > 0.25 ? 'warning' : 'good'}
          />
          <MetricCard
            palette={palette}
            label="Feedback"
            value={feedbackSummary ? formatNumber(feedbackSummary.feedback_count) : '0'}
            tone="neutral"
          />
        </div>

        <div style={styles.tabs(palette)} role="tablist" aria-label="Observability views">
          <TabButton
            active={activeView === 'quality'}
            label="Quality"
            onClick={() => setActiveView('quality')}
            palette={palette}
          />
          <TabButton
            active={activeView === 'fallback'}
            label="Fallback"
            onClick={() => setActiveView('fallback')}
            palette={palette}
          />
          <TabButton
            active={activeView === 'feedback'}
            label="Feedback"
            onClick={() => setActiveView('feedback')}
            palette={palette}
          />
          <TabButton
            active={activeView === 'policy'}
            label="Policy"
            onClick={() => setActiveView('policy')}
            palette={palette}
          />
        </div>

        {status ? <div style={styles.statusText(palette)}>{loading ? 'Loading telemetry...' : status}</div> : null}

        {activeView === 'quality' ? renderQuality(routeQuality, palette) : null}
        {activeView === 'fallback' ? renderFallback(fallbackInspector, fallbackSummary, palette) : null}
        {activeView === 'feedback' ? renderFeedback(feedbackTelemetry, palette) : null}
        {activeView === 'policy' ? renderPolicy(policyDiff, palette) : null}
      </div>
    </section>
  );
}

function renderQuality(routeQuality: RouteQualityResponse | null, palette: PaletteLike) {
  if (!routeQuality) {
    return <EmptyState palette={palette} message="No route telemetry has been captured for this workspace yet." />;
  }

  const overview = routeQuality.overview;
  const providers = routeQuality.providers.slice(0, 4);
  const roles = routeQuality.roles.slice(0, 4);
  const contexts = routeQuality.contexts.slice(0, 3);
  const drilldowns = (routeQuality.context_drilldowns ?? []).slice(0, 4);
  const calibrations = (routeQuality.token_calibration ?? []).slice(0, 4);
  const calibrationTrends = (routeQuality.token_calibration_trends ?? []).slice(0, 4);
  const structuredPreview = (routeQuality.structured_preview ?? []).slice(0, 4);

  return (
    <div style={styles.viewStack}>
      <div style={styles.metricGrid}>
        <MetricCard palette={palette} label="Success" value={formatRate(overview.success_rate)} tone="good" />
        <MetricCard palette={palette} label="Attempts" value={formatNumber(overview.model_attempt_count)} tone="neutral" />
        <MetricCard palette={palette} label="Avg Latency" value={formatLatency(overview.average_latency_ms)} tone="neutral" />
        <MetricCard palette={palette} label="Cost" value={formatCost(overview.estimated_cost_usd)} tone="neutral" />
      </div>

      <RecommendationList items={routeQuality.recommendations} palette={palette} />

      {calibrations.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<Activity size={14} />} label="Token Calibration" palette={palette} />
          {calibrations.map((calibration) => {
            const source =
              calibration.reported_token_sources[0] ||
              calibration.token_estimator_sources[0] ||
              'telemetry pending';
            return (
              <div
                key={`${calibration.provider_id}-${calibration.model}`}
                style={styles.row(palette)}
                title={calibration.recommendation || source}
              >
                <div style={styles.rowMain}>
                  <strong style={styles.rowTitle(palette)}>
                    {calibration.provider_label || calibration.provider_id || 'Provider'}
                  </strong>
                  <span style={styles.rowMeta(palette)}>
                    {calibration.model || 'model'} - {calibration.calibrated_attempts}/{calibration.attempts} samples - error{' '}
                    {formatRate(calibration.average_input_token_error)} in / {formatRate(calibration.average_output_token_error)} out
                  </span>
                  <span style={styles.rowMeta(palette)}>
                    estimated/reported {formatNumber(calibration.estimated_input_tokens)}/{formatNumber(calibration.reported_input_tokens)} in -{' '}
                    {formatNumber(calibration.estimated_output_tokens)}/{formatNumber(calibration.reported_output_tokens)} out - {source}
                  </span>
                </div>
                <StatusPill
                  palette={palette}
                  label={calibration.calibration_status || 'insufficient'}
                  tone={calibrationTone(calibration.calibration_status)}
                />
              </div>
            );
          })}
        </div>
      ) : null}

      {calibrationTrends.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<TrendingUp size={14} />} label="Calibration Trend" palette={palette} />
          {calibrationTrends.map((trend) => (
            <div
              key={`${trend.provider_id}-${trend.model}-${trend.period_start}`}
              style={styles.row(palette)}
              title={trend.recommendation}
            >
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>
                  {trend.period_start || 'unknown'} - {trend.provider_label || trend.provider_id || 'Provider'}
                </strong>
                <span style={styles.rowMeta(palette)}>
                  {trend.model || 'model'} - {trend.calibrated_attempts}/{trend.attempts} samples - error{' '}
                  {formatRate(trend.average_input_token_error)} in / {formatRate(trend.average_output_token_error)} out
                </span>
              </div>
              <StatusPill
                palette={palette}
                label={trend.trend_direction || trend.calibration_status || 'baseline'}
                tone={calibrationTrendTone(trend.trend_direction, trend.calibration_status)}
              />
            </div>
          ))}
        </div>
      ) : null}

      {structuredPreview.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<Activity size={14} />} label="Structured Preview" palette={palette} />
          {structuredPreview.map((preview) => {
            const providerLabel = preview.provider_label || preview.provider_id || 'Provider';
            const reason = preview.retired_reasons[0] ? ` - ${preview.retired_reasons[0]}` : '';
            return (
              <div
                key={`${preview.provider_id}-${preview.model}`}
                style={styles.row(palette)}
                title={preview.recommendation || preview.retired_reasons.join(', ')}
              >
                <div style={styles.rowMain}>
                  <strong style={styles.rowTitle(palette)}>{providerLabel}</strong>
                  <span style={styles.rowMeta(palette)}>
                    {preview.model || 'model'} - {preview.final_winning_attempts}/{preview.previewed_attempts} final -{' '}
                    {preview.retired_attempts} retired - {preview.reset_count} resets{reason}
                  </span>
                  <span style={styles.rowMeta(palette)}>
                    {formatNumber(preview.delta_count)} deltas - {formatNumber(preview.char_count)} chars - avg{' '}
                    {formatNumber(preview.average_preview_chars)} chars
                  </span>
                </div>
                <StatusPill
                  palette={palette}
                  label={preview.preview_status || 'insufficient'}
                  tone={structuredPreviewTone(preview.preview_status)}
                />
              </div>
            );
          })}
        </div>
      ) : null}

      {providers.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<BarChart3 size={14} />} label="Provider Quality" palette={palette} />
          {providers.map((provider) => (
            <div
              key={`${provider.provider_id}-${provider.model}`}
              style={styles.row(palette)}
            >
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>
                  {provider.provider_label || provider.provider_id || 'Provider'}
                </strong>
                <span style={styles.rowMeta(palette)}>
                  {provider.model || 'model'} - {provider.attempts} attempts - {formatLatency(provider.average_latency_ms)}
                </span>
              </div>
              <StatusPill palette={palette} label={formatRate(provider.success_rate)} tone={provider.success_rate >= 0.8 ? 'good' : 'warning'} />
            </div>
          ))}
        </div>
      ) : null}

      {roles.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<GitBranch size={14} />} label="Route Roles" palette={palette} />
          <div style={styles.chipGrid}>
            {roles.map((role) => (
              <div key={role.role} style={styles.compactChip(palette)}>
                <strong>{role.role}</strong>
                <span>{formatRate(role.success_rate)} - {role.attempts} attempts</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {contexts.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<TrendingUp size={14} />} label="Context Pressure" palette={palette} />
          {contexts.map((context) => (
            <div key={`${context.route_role}-${context.intent}`} style={styles.row(palette)}>
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>{context.route_role || 'route'}</strong>
                <span style={styles.rowMeta(palette)}>
                  {context.intent || 'general'} - {formatNumber(context.average_context_tokens)} tokens -{' '}
                  {formatNumber(context.average_selected_files)} files
                </span>
              </div>
              <StatusPill
                palette={palette}
                label={formatRate(context.average_budget_utilization)}
                tone={context.average_budget_utilization && context.average_budget_utilization > 0.72 ? 'warning' : 'neutral'}
              />
            </div>
          ))}
        </div>
      ) : null}

      {drilldowns.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<Activity size={14} />} label="Context Drilldowns" palette={palette} />
          {drilldowns.map((drilldown) => (
            <div key={`${drilldown.task_id}-${drilldown.created_at}`} style={styles.taskBlock(palette)}>
              <div style={styles.rowHeader}>
                <div style={styles.rowMain}>
                  <strong style={styles.rowTitle(palette)}>
                    {drilldown.route_role || 'route'} - {drilldown.intent || 'context'}
                  </strong>
                  <span style={styles.rowMeta(palette)}>
                    {formatNumber(drilldown.estimated_context_tokens)} context tokens - {formatNumber(drilldown.reserve_response_tokens)} reserved -{' '}
                    {formatDateTime(drilldown.created_at)}
                  </span>
                </div>
                <StatusPill
                  palette={palette}
                  label={formatRate(drilldown.utilization)}
                  tone={drilldown.utilization && drilldown.utilization > 0.82 ? 'bad' : drilldown.utilization && drilldown.utilization > 0.68 ? 'warning' : 'good'}
                />
              </div>
              <div style={styles.snippet(palette)}>
                {drilldown.selected_file_count} selected file(s), {drilldown.omitted_file_count} omitted file(s),{' '}
                {drilldown.selected_memory_count + drilldown.selected_project_memory_count} memory item(s)
              </div>
              {drilldown.recommendations[0] ? (
                <div style={styles.riskText(palette)}>{drilldown.recommendations[0]}</div>
              ) : null}
              {drilldown.largest_refs.length ? (
                <div style={styles.refList(palette)}>
                  {drilldown.largest_refs.slice(0, 3).map((ref) => (
                    <span key={ref}>{shorten(ref, 96)}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderFallback(
  fallbackInspector: FallbackInspectorResponse | null,
  summary: { tasks: number; candidates: number; unresolved: number; fallbackRoles: number; adapterIssues: number },
  palette: PaletteLike
) {
  if (!fallbackInspector) {
    return <EmptyState palette={palette} message="No fallback telemetry has been captured for this workspace yet." />;
  }

  const tasks = fallbackInspector.tasks.slice(0, 5);

  return (
    <div style={styles.viewStack}>
      <div style={styles.metricGrid}>
        <MetricCard palette={palette} label="Tasks" value={formatNumber(summary.tasks)} tone="neutral" />
        <MetricCard palette={palette} label="Candidates" value={formatNumber(summary.candidates)} tone="neutral" />
        <MetricCard palette={palette} label="Roles" value={formatNumber(summary.fallbackRoles)} tone="neutral" />
        <MetricCard
          palette={palette}
          label="Adapter"
          value={formatNumber(summary.adapterIssues)}
          tone={summary.adapterIssues ? 'warning' : 'good'}
        />
      </div>

      <RecommendationList items={fallbackInspector.recommendations} palette={palette} />

      {tasks.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<GitBranch size={14} />} label="Recent Routes" palette={palette} />
          {tasks.map((task) => (
            <div key={task.task_id} style={styles.taskBlock(palette)}>
              <div style={styles.rowHeader}>
                <div style={styles.rowMain}>
                  <strong style={styles.rowTitle(palette)}>
                    {task.mode || 'task'} - {task.status || 'unknown'}
                  </strong>
                  <span style={styles.rowMeta(palette)}>{formatDateTime(task.created_at)}</span>
                </div>
                <StatusPill
                  palette={palette}
                  label={`${task.candidates.length} candidates`}
                  tone={task.fallback_roles.length ? 'warning' : 'neutral'}
                />
              </div>
              <div style={styles.snippet(palette)}>{shorten(task.message || task.summary || task.task_id, 180)}</div>

              {task.candidates.slice(0, 3).map((candidate) => (
                <div key={`${task.task_id}-${candidate.index}`} style={styles.candidateRow(palette)}>
                  <div style={styles.rowMain}>
                    <strong style={styles.rowTitle(palette)}>
                      {candidate.provider_label || candidate.provider_id || candidate.provider_hint || candidate.role}
                    </strong>
                    <span style={styles.rowMeta(palette)}>
                      {candidate.model || 'model'} - {candidate.role} -{' '}
                      {candidate.adapter_recommendation ||
                        candidate.adapter_message ||
                        candidate.adapter_latest_error ||
                        candidate.reason ||
                        candidate.error ||
                        'candidate'}
                    </span>
                  </div>
                  <StatusPill
                    palette={palette}
                    label={candidate.adapter_status && candidate.adapter_status !== 'ready' ? candidate.adapter_status : candidate.status || 'planned'}
                    tone={candidate.adapter_status && candidate.adapter_status !== 'ready'
                      ? adapterHealthTone(candidate.adapter_status)
                      : candidate.status === 'succeeded'
                        ? 'good'
                        : candidate.status === 'failed'
                          ? 'bad'
                          : 'neutral'}
                  />
                </div>
              ))}

              {task.attempts
                .map((entry) => ({ entry, preview: previewMetadataLabel(entry.attempt.metadata) }))
                .filter((item) => item.preview)
                .slice(0, 3)
                .map(({ entry, preview }) => (
                  <div key={`${task.task_id}-preview-${entry.attempt.attempt}`} style={styles.candidateRow(palette)}>
                    <div style={styles.rowMain}>
                      <strong style={styles.rowTitle(palette)}>
                        {entry.attempt.provider_label || entry.attempt.provider_id || entry.attempt.role}
                      </strong>
                      <span style={styles.rowMeta(palette)}>
                        {entry.attempt.model || 'model'} - {preview}
                      </span>
                    </div>
                    <StatusPill
                      palette={palette}
                      label={entry.attempt.metadata.structured_preview_final_winner ? 'stream winner' : 'preview'}
                      tone={entry.attempt.metadata.structured_preview_retired ? 'warning' : 'good'}
                    />
                  </div>
                ))}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState palette={palette} message="No routed tasks are available yet." />
      )}
    </div>
  );
}

function renderFeedback(feedbackTelemetry: FeedbackTelemetryResponse | null, palette: PaletteLike) {
  if (!feedbackTelemetry) {
    return <EmptyState palette={palette} message="No feedback telemetry has been captured for this workspace yet." />;
  }

  const summary = feedbackTelemetry.summary;
  const trends = feedbackTelemetry.trends.slice(-7);
  const rollups = feedbackTelemetry.rollups.slice(0, 5);
  const events = feedbackTelemetry.events.slice(0, 5);

  return (
    <div style={styles.viewStack}>
      <div style={styles.metricGrid}>
        <MetricCard palette={palette} label="Positive" value={formatRate(summary.positive_rate)} tone="good" />
        <MetricCard palette={palette} label="Negative" value={formatRate(summary.negative_rate)} tone={summary.negative_rate > 0.25 ? 'bad' : 'neutral'} />
        <MetricCard palette={palette} label="Revised" value={formatNumber(summary.revised_count)} tone="neutral" />
        <MetricCard palette={palette} label="Applied" value={formatNumber(summary.applied_count)} tone="good" />
      </div>

      <RecommendationList items={feedbackTelemetry.recommendations} palette={palette} />

      {trends.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<TrendingUp size={14} />} label="Feedback Trend" palette={palette} />
          <div style={styles.trendStack}>
            {trends.map((trend) => (
              <div key={trend.period_start} style={styles.trendRow}>
                <span style={styles.trendLabel(palette)}>{formatShortDate(trend.period_start)}</span>
                <div style={styles.trendTrack(palette)}>
                  <div
                    style={{
                      ...styles.trendFill(palette, 'good'),
                      width: `${Math.max(4, Math.round(trend.positive_rate * 100))}%`
                    }}
                  />
                </div>
                <span style={styles.trendValue(palette)}>{trend.feedback_count}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {rollups.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<BarChart3 size={14} />} label="Attribution" palette={palette} />
          {rollups.map((rollup) => (
            <div key={`${rollup.dimension}-${rollup.key}`} style={styles.row(palette)}>
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>{rollup.label || rollup.key || rollup.dimension}</strong>
                <span style={styles.rowMeta(palette)}>
                  {rollup.dimension} - {rollup.feedback_count} events - {rollup.task_count} tasks
                </span>
              </div>
              <StatusPill palette={palette} label={formatRate(rollup.positive_rate)} tone="good" />
            </div>
          ))}
        </div>
      ) : null}

      {events.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<Activity size={14} />} label="Recent Feedback" palette={palette} />
          {events.map((event) => (
            <div key={event.id} style={styles.row(palette)}>
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>
                  {event.sentiment} - {event.action}
                </strong>
                <span style={styles.rowMeta(palette)}>
                  {event.model_label || event.route_role || 'route'} - {event.target || 'output'} - {formatDateTime(event.created_at)}
                </span>
              </div>
              <StatusPill palette={palette} label={event.route_role || 'route'} tone={sentimentTone(event.sentiment)} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState palette={palette} message="Feedback controls are ready; no events are recorded yet." />
      )}
    </div>
  );
}

function renderPolicy(policyDiff: RoutePolicyDiffResponse | null, palette: PaletteLike) {
  if (!policyDiff) {
    return <EmptyState palette={palette} message="No route-policy proposal is available for this workspace yet." />;
  }

  const promoted = policyDiff.provider_proposals.filter((proposal) => proposal.action === 'promote').length;
  const deprioritized = policyDiff.provider_proposals.filter((proposal) => proposal.action === 'deprioritize').length;
  const roleChanges = policyDiff.role_proposals.filter((proposal) => proposal.action !== 'keep').length;
  const providerProposals = policyDiff.provider_proposals.slice(0, 5);
  const roleProposals = policyDiff.role_proposals.filter((proposal) => proposal.action !== 'keep').slice(0, 4);

  return (
    <div style={styles.viewStack}>
      <div style={styles.metricGrid}>
        <MetricCard palette={palette} label="Promote" value={formatNumber(promoted)} tone={promoted ? 'good' : 'neutral'} />
        <MetricCard
          palette={palette}
          label="Deprioritize"
          value={formatNumber(deprioritized)}
          tone={deprioritized ? 'warning' : 'neutral'}
        />
        <MetricCard palette={palette} label="Role Diffs" value={formatNumber(roleChanges)} tone={roleChanges ? 'warning' : 'neutral'} />
        <MetricCard
          palette={palette}
          label="Source"
          value={policyDiff.source_snapshot_stale ? 'stale' : policyDiff.source}
          tone={policyDiff.source_snapshot_stale ? 'warning' : 'neutral'}
        />
      </div>

      <RecommendationList items={[...policyDiff.recommendations, ...policyDiff.warnings].slice(0, 4)} palette={palette} />

      {providerProposals.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<BarChart3 size={14} />} label="Provider Proposals" palette={palette} />
          {providerProposals.map((proposal) => (
            <div key={`${proposal.provider_id}-${proposal.model}-${proposal.observed_rank}`} style={styles.taskBlock(palette)}>
              <div style={styles.rowHeader}>
                <div style={styles.rowMain}>
                  <strong style={styles.rowTitle(palette)}>
                    {proposal.provider_label || proposal.provider_id || proposal.model || 'provider'}
                  </strong>
                  <span style={styles.rowMeta(palette)}>
                    rank {proposal.observed_rank} to {proposal.proposed_rank} - score {proposal.score.toFixed(1)} - confidence{' '}
                    {formatRate(proposal.confidence)}
                  </span>
                </div>
                <StatusPill palette={palette} label={proposal.action} tone={policyActionTone(proposal.action)} />
              </div>
              <div style={styles.snippet(palette)}>{proposal.reasons[0] || 'No reason recorded.'}</div>
              {proposal.risks.length ? <div style={styles.riskText(palette)}>{proposal.risks[0]}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {roleProposals.length ? (
        <div style={styles.stack}>
          <SectionLabel icon={<GitBranch size={14} />} label="Role Diffs" palette={palette} />
          {roleProposals.map((proposal) => (
            <div key={proposal.role} style={styles.row(palette)}>
              <div style={styles.rowMain}>
                <strong style={styles.rowTitle(palette)}>
                  {proposal.role} - {proposal.action}
                </strong>
                <span style={styles.rowMeta(palette)}>
                  {proposal.observed_primary_provider || 'unknown'} to {proposal.proposed_primary_provider || 'review'} - delta{' '}
                  {proposal.score_delta.toFixed(1)}
                </span>
              </div>
              <StatusPill palette={palette} label={formatRate(proposal.confidence)} tone={policyActionTone(proposal.action)} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState palette={palette} message="No route-role changes are recommended for this telemetry window." />
      )}
    </div>
  );
}

function RecommendationList({ items, palette }: { items: string[]; palette: PaletteLike }) {
  if (!items.length) return null;

  return (
    <div style={styles.recommendationBox(palette)}>
      {items.slice(0, 3).map((item) => (
        <div key={item} style={styles.recommendationItem(palette)}>
          {item}
        </div>
      ))}
    </div>
  );
}

function SectionLabel({ icon, label, palette }: { icon: ReactNode; label: string; palette: PaletteLike }) {
  return (
    <div style={styles.sectionLabel(palette)}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function TabButton({
  active,
  label,
  onClick,
  palette
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  palette: PaletteLike;
}) {
  return (
    <button type="button" onClick={onClick} style={styles.tab(palette, active)}>
      {label}
    </button>
  );
}

function MetricCard({
  label,
  value,
  tone,
  palette
}: {
  label: string;
  value: string;
  tone: 'good' | 'bad' | 'warning' | 'neutral';
  palette: PaletteLike;
}) {
  return (
    <div style={styles.metricCard(palette, tone)}>
      <span style={styles.metricLabel(palette)}>{label}</span>
      <strong style={styles.metricValue(palette)}>{value}</strong>
    </div>
  );
}

function StatusPill({
  label,
  tone,
  palette
}: {
  label: string;
  tone: 'good' | 'bad' | 'warning' | 'neutral';
  palette: PaletteLike;
}) {
  return <span style={styles.statusPill(palette, tone)}>{label}</span>;
}

function EmptyState({ message, palette }: { message: string; palette: PaletteLike }) {
  return <div style={styles.empty(palette)}>{message}</div>;
}

function readFailure(reason: unknown, fallback: string): string {
  return reason instanceof Error && reason.message ? reason.message : fallback;
}

function previewMetadataLabel(metadata: Record<string, unknown>): string {
  if (!metadata.structured_preview_emitted) return '';
  const deltas = typeof metadata.structured_preview_delta_count === 'number' ? metadata.structured_preview_delta_count : 0;
  const chars = typeof metadata.structured_preview_char_count === 'number' ? metadata.structured_preview_char_count : 0;
  const parts = [`preview ${formatNumber(deltas)} deltas`, `${formatNumber(chars)} chars`];
  if (metadata.structured_preview_final_winner) parts.push('final winner');
  if (metadata.structured_preview_retired) {
    const reason = typeof metadata.structured_preview_retired_reason === 'string' ? metadata.structured_preview_retired_reason : '';
    parts.push(reason ? `reset (${reason})` : 'reset');
  }
  return parts.join(' - ');
}

function snapshotStatus(status: TelemetrySnapshotStatus, ageSeconds: number, isStale: boolean): string {
  const age = ageSeconds >= 60 ? `${Math.round(ageSeconds / 60)}m old` : `${ageSeconds}s old`;
  if (status === 'refreshed') return `Snapshot refreshed (${age})`;
  return isStale ? `Snapshot loaded but stale (${age})` : `Snapshot loaded (${age})`;
}

function snapshotPruneStatus(prune?: TelemetrySnapshotPruneInfo): string {
  if (!prune || prune.retention_max_snapshots <= 0) return '';
  if (prune.deleted_count > 0) {
    return `Pruned ${prune.deleted_count} stale snapshot${prune.deleted_count === 1 ? '' : 's'}.`;
  }
  return `Snapshot retention ${prune.retained_count}/${prune.retention_max_snapshots}.`;
}

function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? 'n/a' : `${Math.round(value)}%`;
}

function formatRate(value: number | null | undefined): string {
  return value === null || value === undefined ? 'n/a' : `${Math.round(value * 100)}%`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0';
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1);
}

function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined || value <= 0) return '$0.00';
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
}

function formatLatency(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a';
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${Math.round(value)}ms`;
}

function formatClock(value: Date): string {
  return value.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function formatShortDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function shorten(value: string, maxLength: number): string {
  const clean = value.replace(/\s+/g, ' ').trim();
  return clean.length > maxLength ? `${clean.slice(0, maxLength - 1)}...` : clean;
}

function scoreTone(value: number | null | undefined): 'good' | 'bad' | 'warning' | 'neutral' {
  if (value === null || value === undefined) return 'neutral';
  if (value >= 82) return 'good';
  if (value < 60) return 'bad';
  return 'warning';
}

function sentimentTone(sentiment: string): 'good' | 'bad' | 'warning' | 'neutral' {
  if (['liked', 'accepted', 'copied', 'applied'].includes(sentiment)) return 'good';
  if (['disliked', 'rejected', 'rolled_back'].includes(sentiment)) return 'bad';
  if (['revised', 'regenerated', 'corrected'].includes(sentiment)) return 'warning';
  return 'neutral';
}

function adapterHealthTone(status: string): 'good' | 'bad' | 'warning' | 'neutral' {
  if (status === 'ready') return 'good';
  if (['missing_secret', 'missing_model', 'unsupported_api', 'unconfigured'].includes(status)) return 'bad';
  if (['cooldown', 'degraded', 'disabled'].includes(status)) return 'warning';
  return 'neutral';
}

function calibrationTone(status: string | null | undefined): 'good' | 'bad' | 'warning' | 'neutral' {
  if (status === 'stable') return 'good';
  if (status === 'drift') return 'bad';
  if (status === 'watch') return 'warning';
  return 'neutral';
}

function calibrationTrendTone(
  direction: string | null | undefined,
  status: string | null | undefined
): 'good' | 'bad' | 'warning' | 'neutral' {
  if (direction === 'improving') return 'good';
  if (direction === 'worsening') return 'bad';
  if (direction === 'flat' || direction === 'baseline') return 'warning';
  return calibrationTone(status);
}

function structuredPreviewTone(status: string | null | undefined): 'good' | 'bad' | 'warning' | 'neutral' {
  if (status === 'stable') return 'good';
  if (status === 'unstable') return 'bad';
  if (status === 'watch') return 'warning';
  return 'neutral';
}

function policyActionTone(action: string): 'good' | 'bad' | 'warning' | 'neutral' {
  if (action === 'promote') return 'good';
  if (action === 'deprioritize') return 'bad';
  if (action === 'switch_primary' || action === 'strengthen_fallback' || action === 'rebalance') return 'warning';
  return 'neutral';
}

function toneColor(palette: PaletteLike, tone: 'good' | 'bad' | 'warning' | 'neutral') {
  if (tone === 'good') return palette.good;
  if (tone === 'bad') return palette.bad;
  if (tone === 'warning') return palette.warning;
  return palette.accent;
}

const styles = {
  panel: (palette: PaletteLike): CSSProperties => ({
    borderRadius: 24,
    background: palette.card,
    border: `1px solid ${palette.shellBorder}`,
    boxShadow: '0 24px 70px rgba(15, 23, 42, 0.12)',
    overflow: 'hidden'
  }),
  header: (palette: PaletteLike): CSSProperties => ({
    padding: '16px 18px',
    borderBottom: `1px solid ${palette.shellBorder}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12
  }),
  titleWrap: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,
  title: (palette: PaletteLike): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: palette.text
  }),
  iconButton: (palette: PaletteLike, disabled: boolean): CSSProperties => ({
    width: 32,
    height: 32,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    border: `1px solid ${palette.inputBorder}`,
    background: disabled ? palette.cardAlt : palette.input,
    color: disabled ? palette.muted : palette.text,
    cursor: disabled ? 'not-allowed' : 'pointer'
  }),
  body: {
    padding: 16,
    display: 'grid',
    gap: 14
  } as CSSProperties,
  summaryStrip: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
    gap: 8
  } as CSSProperties,
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 8
  } as CSSProperties,
  metricCard: (palette: PaletteLike, tone: 'good' | 'bad' | 'warning' | 'neutral'): CSSProperties => ({
    minWidth: 0,
    display: 'grid',
    gap: 4,
    padding: 10,
    borderRadius: 14,
    border: `1px solid ${palette.inputBorder}`,
    background: palette.cardAlt,
    boxShadow: `inset 3px 0 0 ${toneColor(palette, tone)}`
  }),
  metricLabel: (palette: PaletteLike): CSSProperties => ({
    color: palette.muted,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),
  metricValue: (palette: PaletteLike): CSSProperties => ({
    color: palette.text,
    fontSize: 16,
    lineHeight: 1.2,
    overflowWrap: 'anywhere'
  }),
  tabs: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    padding: 4,
    gap: 4,
    borderRadius: 14,
    background: palette.cardAlt,
    border: `1px solid ${palette.inputBorder}`
  }),
  tab: (palette: PaletteLike, active: boolean): CSSProperties => ({
    minHeight: 30,
    border: 'none',
    borderRadius: 10,
    background: active ? palette.accent : 'transparent',
    color: active ? '#fff' : palette.textSoft,
    fontWeight: 700,
    fontSize: 12,
    cursor: 'pointer'
  }),
  statusText: (palette: PaletteLike): CSSProperties => ({
    color: palette.muted,
    fontSize: 12
  }),
  viewStack: {
    display: 'grid',
    gap: 14
  } as CSSProperties,
  stack: {
    display: 'grid',
    gap: 8
  } as CSSProperties,
  sectionLabel: (palette: PaletteLike): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: palette.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),
  row: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 10,
    alignItems: 'center',
    padding: 10,
    borderRadius: 14,
    background: palette.cardAlt,
    border: `1px solid ${palette.inputBorder}`
  }),
  rowHeader: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 10,
    alignItems: 'center'
  } as CSSProperties,
  rowMain: {
    minWidth: 0,
    display: 'grid',
    gap: 4
  } as CSSProperties,
  rowTitle: (palette: PaletteLike): CSSProperties => ({
    color: palette.text,
    fontSize: 13,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }),
  rowMeta: (palette: PaletteLike): CSSProperties => ({
    color: palette.muted,
    fontSize: 12,
    lineHeight: 1.4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }),
  statusPill: (palette: PaletteLike, tone: 'good' | 'bad' | 'warning' | 'neutral'): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 26,
    maxWidth: 120,
    padding: '0 8px',
    borderRadius: 999,
    background: `${toneColor(palette, tone)}22`,
    color: toneColor(palette, tone),
    fontSize: 11,
    fontWeight: 800,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  }),
  chipGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 8
  } as CSSProperties,
  compactChip: (palette: PaletteLike): CSSProperties => ({
    minWidth: 0,
    display: 'grid',
    gap: 4,
    padding: 10,
    borderRadius: 14,
    background: palette.cardAlt,
    border: `1px solid ${palette.inputBorder}`,
    color: palette.text,
    fontSize: 12
  }),
  taskBlock: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gap: 8,
    padding: 10,
    borderRadius: 14,
    background: palette.cardAlt,
    border: `1px solid ${palette.inputBorder}`
  }),
  snippet: (palette: PaletteLike): CSSProperties => ({
    color: palette.textSoft,
    fontSize: 12,
    lineHeight: 1.45
  }),
  riskText: (palette: PaletteLike): CSSProperties => ({
    color: palette.warning,
    fontSize: 12,
    lineHeight: 1.45
  }),
  refList: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gap: 4,
    color: palette.muted,
    fontSize: 11,
    lineHeight: 1.4,
    overflowWrap: 'anywhere'
  }),
  candidateRow: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 8,
    alignItems: 'center',
    padding: '8px 0',
    borderTop: `1px solid ${palette.inputBorder}`
  }),
  recommendationBox: (palette: PaletteLike): CSSProperties => ({
    display: 'grid',
    gap: 8,
    padding: 10,
    borderRadius: 14,
    background: palette.accentSoft,
    border: `1px solid ${palette.inputBorder}`
  }),
  recommendationItem: (palette: PaletteLike): CSSProperties => ({
    color: palette.text,
    fontSize: 12,
    lineHeight: 1.45
  }),
  trendStack: {
    display: 'grid',
    gap: 8
  } as CSSProperties,
  trendRow: {
    display: 'grid',
    gridTemplateColumns: '54px minmax(0, 1fr) 28px',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,
  trendLabel: (palette: PaletteLike): CSSProperties => ({
    color: palette.muted,
    fontSize: 11
  }),
  trendTrack: (palette: PaletteLike): CSSProperties => ({
    height: 8,
    borderRadius: 999,
    background: palette.cardAlt,
    border: `1px solid ${palette.inputBorder}`,
    overflow: 'hidden'
  }),
  trendFill: (palette: PaletteLike, tone: 'good' | 'bad' | 'warning' | 'neutral'): CSSProperties => ({
    height: '100%',
    borderRadius: 999,
    background: toneColor(palette, tone)
  }),
  trendValue: (palette: PaletteLike): CSSProperties => ({
    color: palette.text,
    fontSize: 11,
    fontWeight: 800,
    textAlign: 'right'
  }),
  empty: (palette: PaletteLike): CSSProperties => ({
    padding: 12,
    borderRadius: 14,
    border: `1px dashed ${palette.inputBorder}`,
    color: palette.muted,
    background: palette.cardAlt,
    fontSize: 13,
    lineHeight: 1.5
  })
};
