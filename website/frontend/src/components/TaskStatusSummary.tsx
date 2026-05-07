import type { CSSProperties, ReactNode } from 'react';
import type { TaskSummary } from '../types';

export type TaskStatusMetric = {
  id: 'active' | 'completed' | 'failed_or_canceled';
  label: string;
  value: number;
};

const terminalStatuses = new Set(['completed', 'failed', 'canceled']);

export function getTaskStatusMetrics(tasks: TaskSummary[]): TaskStatusMetric[] {
  return [
    {
      id: 'active',
      label: 'Active',
      value: tasks.filter((item) => !terminalStatuses.has(item.status)).length
    },
    {
      id: 'completed',
      label: 'Completed',
      value: tasks.filter((item) => item.status === 'completed').length
    },
    {
      id: 'failed_or_canceled',
      label: 'Failed or canceled',
      value: tasks.filter((item) => item.status === 'failed' || item.status === 'canceled').length
    }
  ];
}

export function TaskStatusSummary({
  tasks,
  style,
  renderMetric
}: {
  tasks: TaskSummary[];
  style?: CSSProperties;
  renderMetric?: (metric: TaskStatusMetric) => ReactNode;
}) {
  const metrics = getTaskStatusMetrics(tasks);

  return (
    <div style={style ?? defaultGridStyle} data-testid="task-status-summary">
      {metrics.map((metric) =>
        renderMetric ? (
          <div key={metric.id}>{renderMetric(metric)}</div>
        ) : (
          <section key={metric.id} style={defaultMetricStyle}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </section>
        )
      )}
    </div>
  );
}

const defaultGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 12
};

const defaultMetricStyle: CSSProperties = {
  display: 'grid',
  gap: 4,
  padding: 12,
  border: '1px solid currentColor',
  borderRadius: 8
};
