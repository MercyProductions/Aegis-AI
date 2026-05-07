import { describe, expect, it } from 'vitest';
import {
  activityFilterOptions,
  assistantIdentity,
  defaultAssistantMission,
  fallbackModeOptions,
  healthStatusToEventStatus,
  productName,
  reliabilityStatusToEventStatus,
  runtimeIdentity,
  severityToEventStatus,
  starterPrompts,
  taskFilterOptions,
  terminalTaskStatuses,
  thinkingStates
} from './appExperience';

describe('app experience constants', () => {
  it('keeps the public product identity centralized', () => {
    expect(productName).toBe('Auralith OS');
    expect(assistantIdentity).toBe('Auralith Prime');
    expect(runtimeIdentity).toBe('Aegis Core');
    expect(defaultAssistantMission).toContain('local-first AI operating environment');
  });

  it('keeps starter prompts, thinking states, and fallback modes available', () => {
    expect(starterPrompts).toContain('Help me debug this error');
    expect(starterPrompts.length).toBeGreaterThanOrEqual(4);
    expect(thinkingStates).toContain('Checking the workspace');
    expect(fallbackModeOptions.map((option) => option.id)).toEqual(['build', 'develop', 'review', 'chat']);
  });

  it('keeps activity and task filters stable for the app shell', () => {
    expect(activityFilterOptions.map((option) => option.value)).toEqual(['all', 'issues', 'commands']);
    expect(activityFilterOptions[0].ariaLabel).toBe('Show all activity events');
    expect(taskFilterOptions.map((option) => option.value)).toEqual(['active', 'completed', 'failed', 'all']);
  });

  it('identifies terminal task statuses used by task filtering', () => {
    expect(terminalTaskStatuses.has('completed')).toBe(true);
    expect(terminalTaskStatuses.has('failed')).toBe(true);
    expect(terminalTaskStatuses.has('canceled')).toBe(true);
    expect(terminalTaskStatuses.has('running')).toBe(false);
  });
});

describe('app experience status mapping', () => {
  it('maps recommendation severity to event status without widening labels', () => {
    expect(severityToEventStatus('critical')).toBe('error');
    expect(severityToEventStatus('high')).toBe('error');
    expect(severityToEventStatus('medium')).toBe('warning');
    expect(severityToEventStatus('low')).toBe('warning');
    expect(severityToEventStatus('info')).toBe('ok');
    expect(severityToEventStatus('HIGH')).toBe('ok');
  });

  it('maps workspace health status to event status', () => {
    expect(healthStatusToEventStatus('critical')).toBe('error');
    expect(healthStatusToEventStatus('failed')).toBe('error');
    expect(healthStatusToEventStatus('error')).toBe('error');
    expect(healthStatusToEventStatus('attention')).toBe('warning');
    expect(healthStatusToEventStatus('watch')).toBe('warning');
    expect(healthStatusToEventStatus('warning')).toBe('warning');
    expect(healthStatusToEventStatus('unknown')).toBe('warning');
    expect(healthStatusToEventStatus('skipped')).toBe('warning');
    expect(healthStatusToEventStatus('ready')).toBe('ok');
  });

  it('maps reliability status to event status', () => {
    expect(reliabilityStatusToEventStatus('degraded')).toBe('error');
    expect(reliabilityStatusToEventStatus('critical')).toBe('error');
    expect(reliabilityStatusToEventStatus('failed')).toBe('error');
    expect(reliabilityStatusToEventStatus('watch')).toBe('warning');
    expect(reliabilityStatusToEventStatus('unknown')).toBe('warning');
    expect(reliabilityStatusToEventStatus('warning')).toBe('warning');
    expect(reliabilityStatusToEventStatus('healthy')).toBe('ok');
  });
});
