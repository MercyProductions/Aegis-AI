import { describe, expect, it } from 'vitest';
import {
  MISSION_ANCHOR_PREFIX,
  buildAgentRequestHistory,
  createMissionAnchorMessage,
  isMissionAnchorMessage,
  sanitizeMissionAnchor
} from './missionAnchor';
import type { ChatMessage } from '../types';

describe('mission anchor utilities', () => {
  it('anchors vague follow-ups to the first explicit path-bound mission', () => {
    const history: ChatMessage[] = [
      {
        role: 'user',
        content:
          'at this path C:\\Users\\gabri\\Desktop\\NativeTool create a C++ DLL with CMake and build it'
      },
      { role: 'assistant', content: 'I created the project.' },
      { role: 'user', content: 'continue' }
    ];

    const requestHistory = buildAgentRequestHistory(history, 'continue', 'C:\\Users\\gabri\\Desktop\\NativeTool');

    expect(requestHistory[0].role).toBe('system');
    expect(requestHistory[0].content).toContain(MISSION_ANCHOR_PREFIX);
    expect(requestHistory[0].content).toContain('C++ DLL');
    expect(requestHistory[0].content).toContain('C:\\Users\\gabri\\Desktop\\NativeTool');
    expect(requestHistory.at(-1)?.content).toBe('continue');
  });

  it('treats confirmation replies as vague follow-ups to the active mission', () => {
    const history: ChatMessage[] = [
      {
        role: 'user',
        content:
          'build me a TypeScript obfuscator here C:\\Users\\gabri\\Desktop\\Aegis\\Tools\\Obfuscation\\TypeScriptObfuscator'
      },
      { role: 'assistant', content: 'Please confirm the settings.' }
    ];

    const requestHistory = buildAgentRequestHistory(
      history,
      'yes im aware go ahead',
      'C:\\Users\\gabri\\Desktop\\Aegis\\Tools\\Obfuscation\\TypeScriptObfuscator'
    );

    expect(requestHistory[0].role).toBe('system');
    expect(requestHistory[0].content).toContain(MISSION_ANCHOR_PREFIX);
    expect(requestHistory[0].content).toContain('TypeScript obfuscator');
    expect(requestHistory[0].content).toContain('TypeScriptObfuscator');
  });

  it('does not duplicate existing mission anchors in the request tail', () => {
    const anchor = createMissionAnchorMessage(
      [{ role: 'user', content: 'create a desktop app at C:\\Projects\\DeskApp' }],
      'continue',
      'C:\\Projects\\DeskApp'
    );
    const history: ChatMessage[] = [
      anchor as ChatMessage,
      { role: 'user', content: 'create a desktop app at C:\\Projects\\DeskApp' },
      { role: 'assistant', content: 'working' },
      { role: 'user', content: 'continue' }
    ];

    const requestHistory = buildAgentRequestHistory(history, 'continue', 'C:\\Projects\\DeskApp', anchor);

    expect(requestHistory.filter(isMissionAnchorMessage)).toHaveLength(1);
    expect(requestHistory[0]).toEqual(anchor);
  });

  it('sanitizes only valid system mission anchors', () => {
    const valid = {
      role: 'system' as const,
      content: `${MISSION_ANCHOR_PREFIX}\n- Original user mission: build a CLI`
    };

    expect(sanitizeMissionAnchor(valid)).toEqual(valid);
    expect(sanitizeMissionAnchor({ role: 'user', content: valid.content })).toBeNull();
    expect(sanitizeMissionAnchor({ role: 'system', content: 'plain system message' })).toBeNull();
  });

  it('keeps the mission anchor even when the original prompt falls outside the tail window', () => {
    const history: ChatMessage[] = [
      { role: 'user', content: 'at this path C:\\Projects\\BigApp build a complete desktop app' },
      ...Array.from({ length: 14 }, (_, index) => ({
        role: (index % 2 === 0 ? 'assistant' : 'user') as ChatMessage['role'],
        content: index % 2 === 0 ? `progress ${index}` : 'continue'
      }))
    ];

    const requestHistory = buildAgentRequestHistory(history, 'continue', 'C:\\Projects\\BigApp');

    expect(requestHistory).toHaveLength(9);
    expect(requestHistory[0].content).toContain('complete desktop app');
    expect(requestHistory.slice(1).some((item) => item.content.includes('complete desktop app'))).toBe(false);
  });
});
