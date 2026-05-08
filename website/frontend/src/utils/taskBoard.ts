import type { TaskArtifactsResponse, TaskSummary } from '../types';
import type { TaskBoardFilter } from './appExperience';
import { terminalTaskStatuses } from './appExperience';

export function taskIsTerminal(status: string) {
  return terminalTaskStatuses.has(status);
}

export function findTaskBoardSelection(tasks: TaskSummary[], selectedTaskId: string) {
  return tasks.find((item) => item.id === selectedTaskId || item.task_id === selectedTaskId) ?? null;
}

export function filterTaskBoardTasks(tasks: TaskSummary[], filter: TaskBoardFilter) {
  return tasks.filter((item) => {
    if (filter === 'all') return true;
    if (filter === 'active') return !taskIsTerminal(item.status);
    if (filter === 'completed') return item.status === 'completed';
    return item.status === 'failed' || item.status === 'canceled';
  });
}

export function summarizeTaskBoard(tasks: TaskSummary[]) {
  return {
    active: tasks.filter((item) => !taskIsTerminal(item.status)).length,
    completed: tasks.filter((item) => item.status === 'completed').length,
    failed: tasks.filter((item) => item.status === 'failed' || item.status === 'canceled').length
  };
}

export function collectTaskArtifacts(selectedTask: TaskSummary | null, taskArtifacts: TaskArtifactsResponse | null) {
  return {
    relatedFiles: Array.from(new Set([...(selectedTask?.related_files ?? []), ...(taskArtifacts?.related_files ?? [])])),
    validationCommands: Array.from(
      new Set([...(selectedTask?.validation_commands ?? []), ...(taskArtifacts?.validation_commands ?? [])])
    ),
    checkpointIds: Array.from(new Set([...(selectedTask?.checkpoints ?? []), ...(taskArtifacts?.checkpoints ?? [])]))
  };
}
