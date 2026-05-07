import type { ToolEvent } from '../types';
import type { ActivityFilter } from './appExperience';

export function activityEventId(item: ToolEvent, index: number) {
  return `${item.created_at || 'event'}|${item.kind}|${item.title}|${index}`;
}

export function activityEventHasDetails(item: ToolEvent) {
  return Object.keys(item.payload || {}).length > 0;
}

export function filterActivityEvents(events: ToolEvent[], filter: ActivityFilter) {
  if (filter === 'issues') {
    return events.filter((item) => item.status !== 'ok');
  }
  if (filter === 'commands') {
    return events.filter((item) => item.kind === 'command' || Boolean(payloadValueText(item.payload, 'command')));
  }
  return events;
}

export function payloadValueText(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  if (value === null) return 'n/a';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
}

export function activityOutputText(parts: { stdout: string; stderr: string; reason: string }) {
  return [
    parts.stderr ? `Stderr:\n${parts.stderr}` : '',
    parts.stdout ? `Stdout:\n${parts.stdout}` : '',
    parts.reason ? `Reason:\n${parts.reason}` : ''
  ]
    .filter(Boolean)
    .join('\n\n');
}

export function clipActivityText(text: string, limit = 5000) {
  return text.length > limit ? `${text.slice(0, limit)}\n... output truncated ...` : text;
}
