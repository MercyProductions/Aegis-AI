import { describe, expect, it } from 'vitest';
import type { RepairAttempt, TaskArtifactsResponse, TaskSummary, ToolEvent } from '../types';
import {
  collectTaskArtifacts,
  filterTaskBoardTasks,
  findTaskBoardSelection,
  summarizeTaskBoard,
  taskIsTerminal
} from './taskBoard';

function task(overrides: Partial<TaskSummary>): TaskSummary {
  return {
    id: 'task-1',
    task_id: 'task-public-1',
    project_id: 'project',
    parent_task_id: null,
    title: 'Implement validation repair',
    user_goal: 'Make validation actionable',
    created_at: '2026-05-07T12:00:00Z',
    updated_at: '2026-05-07T12:01:00Z',
    completed_at: null,
    finished_at: null,
    mode: 'build',
    workspace_root: 'C:/workspace',
    message: 'repair validation',
    status: 'running',
    priority: 1,
    assigned_agent_role: 'builder',
    related_files: [],
    validation_commands: [],
    checkpoints: [],
    error_summary: '',
    final_summary: '',
    ...overrides
  };
}

function toolEvent(overrides: Partial<ToolEvent> = {}): ToolEvent {
  return {
    kind: 'info',
    title: 'Task event',
    status: 'ok',
    detail: '',
    payload: {},
    created_at: '2026-05-07T12:02:00Z',
    ...overrides
  };
}

function repairAttempt(overrides: Partial<RepairAttempt> = {}): RepairAttempt {
  return {
    attempt: 1,
    category: 'validation',
    outcome: 'improved',
    checkpoint: null,
    summary: 'Reduced failure surface',
    before_signature: 'before',
    after_signature: 'after',
    created_at: '2026-05-07T12:03:00Z',
    ...overrides
  };
}

function artifacts(overrides: Partial<TaskArtifactsResponse>): TaskArtifactsResponse {
  return {
    task_id: 'task-1',
    related_files: [],
    validation_commands: [],
    checkpoints: [],
    repair_attempts: [],
    command_events: [],
    validation_events: [],
    ...overrides
  };
}

describe('task board helpers', () => {
  it('recognizes terminal task statuses used by cancellation and filtering', () => {
    expect(taskIsTerminal('completed')).toBe(true);
    expect(taskIsTerminal('failed')).toBe(true);
    expect(taskIsTerminal('canceled')).toBe(true);
    expect(taskIsTerminal('running')).toBe(false);
  });

  it('selects a task by internal id or public task id', () => {
    const tasks = [task({ id: 'a', task_id: 'public-a' }), task({ id: 'b', task_id: 'public-b' })];

    expect(findTaskBoardSelection(tasks, 'a')?.id).toBe('a');
    expect(findTaskBoardSelection(tasks, 'public-b')?.id).toBe('b');
    expect(findTaskBoardSelection(tasks, 'missing')).toBeNull();
  });

  it('filters tasks using the existing active, completed, failed, and all buckets', () => {
    const tasks = [
      task({ id: 'queued', status: 'queued' }),
      task({ id: 'running', status: 'running' }),
      task({ id: 'completed', status: 'completed' }),
      task({ id: 'failed', status: 'failed' }),
      task({ id: 'canceled', status: 'canceled' })
    ];

    expect(filterTaskBoardTasks(tasks, 'active').map((item) => item.id)).toEqual(['queued', 'running']);
    expect(filterTaskBoardTasks(tasks, 'completed').map((item) => item.id)).toEqual(['completed']);
    expect(filterTaskBoardTasks(tasks, 'failed').map((item) => item.id)).toEqual(['failed', 'canceled']);
    expect(filterTaskBoardTasks(tasks, 'all')).toEqual(tasks);
  });

  it('summarizes active, completed, and repair-needed task counts', () => {
    expect(
      summarizeTaskBoard([
        task({ status: 'queued' }),
        task({ status: 'running' }),
        task({ status: 'completed' }),
        task({ status: 'failed' }),
        task({ status: 'canceled' })
      ])
    ).toEqual({ active: 2, completed: 1, failed: 2 });
  });

  it('merges selected task and artifact metadata in display order without duplicates', () => {
    const selectedTask = task({
      related_files: ['src/App.tsx', 'src/api.ts'],
      validation_commands: ['npm test'],
      checkpoints: ['before-edit']
    });
    const taskArtifacts = artifacts({
      related_files: ['src/api.ts', 'src/utils/taskBoard.ts'],
      validation_commands: ['npm test', 'npm run build'],
      checkpoints: ['before-edit', 'after-validation'],
      repair_attempts: [repairAttempt()],
      command_events: [toolEvent()],
      validation_events: [toolEvent({ kind: 'validation' })]
    });

    expect(collectTaskArtifacts(selectedTask, taskArtifacts)).toEqual({
      relatedFiles: ['src/App.tsx', 'src/api.ts', 'src/utils/taskBoard.ts'],
      validationCommands: ['npm test', 'npm run build'],
      checkpointIds: ['before-edit', 'after-validation']
    });
  });

  it('handles missing selected task and task artifacts safely', () => {
    expect(collectTaskArtifacts(null, null)).toEqual({
      relatedFiles: [],
      validationCommands: [],
      checkpointIds: []
    });
  });
});
