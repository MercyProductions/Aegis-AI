import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { getTaskStatusMetrics, TaskStatusSummary } from './TaskStatusSummary';
import type { TaskSummary } from '../types';

describe('TaskStatusSummary', () => {
  it('counts active, completed, failed, and canceled tasks', () => {
    const metrics = getTaskStatusMetrics([
      createTask({ id: 'queued', status: 'queued' }),
      createTask({ id: 'repairing', status: 'repairing' }),
      createTask({ id: 'completed', status: 'completed' }),
      createTask({ id: 'failed', status: 'failed' }),
      createTask({ id: 'canceled', status: 'canceled' })
    ]);

    expect(metrics).toEqual([
      { id: 'active', label: 'Active', value: 2 },
      { id: 'completed', label: 'Completed', value: 1 },
      { id: 'failed_or_canceled', label: 'Failed or canceled', value: 2 }
    ]);
  });

  it('renders task status metrics for the workspace Tasks view', () => {
    const html = renderToStaticMarkup(
      <TaskStatusSummary
        tasks={[
          createTask({ id: 'running', status: 'running' }),
          createTask({ id: 'completed', status: 'completed' }),
          createTask({ id: 'failed', status: 'failed' })
        ]}
      />
    );

    expect(html).toContain('data-testid="task-status-summary"');
    expect(html).toContain('Active');
    expect(html).toContain('<strong>1</strong>');
    expect(html).toContain('Failed or canceled');
  });
});

function createTask(overrides: Partial<TaskSummary>): TaskSummary {
  const id = overrides.id ?? 'task';

  return {
    id,
    task_id: id,
    project_id: 'project',
    parent_task_id: null,
    title: id,
    user_goal: 'Test task',
    created_at: '2026-05-06T00:00:00Z',
    updated_at: '2026-05-06T00:00:00Z',
    completed_at: null,
    finished_at: null,
    mode: 'develop',
    workspace_root: 'workspace',
    message: 'Test task',
    status: 'queued',
    priority: 0,
    assigned_agent_role: '',
    related_files: [],
    validation_commands: [],
    checkpoints: [],
    error_summary: '',
    final_summary: '',
    ...overrides
  };
}
